"""Enrich / upsert user profiles from raw conversations + conversation summaries.

Workflow per user (idempotent):
 1. Collect conversation summaries (newest first).
 2. Collect raw conversation messages (newest first) and flatten into an ordered stream of
    message objects (role, content, conv_updated_at, thread_id).
 3. Apply a global character budget (default 100_000) over the combined summaries + messages
    (summaries first for compressed signal, then raw messages) to keep prompt bounded.
 4. Fetch existing profile JSON (if any) from `user_profiles`.
 5. Send model a JSON payload containing existing_profile (or null), conversation_summaries,
    and recent_messages. Model instructed to MERGE and return ONLY a single JSON object
    representing the updated profile (no code fences or commentary).
 6. Parse model output; on valid JSON upsert into `user_profiles` (INSERT .. ON CONFLICT UPDATE).

Profile is schemaless but we encourage a semi-structured convention so downstream tooling
can rely on stable keys when present. Suggested top-level keys (model instruction mirrors this):
  - style: { tone: "friendly|professional|concise|detailed", verbosity: "brief|moderate|elaborate", formality: "casual|neutral|formal" }
  - preferences: { favorite_cuisines: [], favorite_ingredients: [], disliked_items: [], flavor_profile: [], preparation_styles: [] }
  - diet: { restrictions: [], allergens: [], goals: [] }  # goals can also live under top-level goals[] if clearer
  - goals: []  # user articulated longer-term aims ("eat more seasonal vegetables", "gain muscle", etc.)
  - favorite_dishes: []
  - household: { has_kids: bool, notes: "...", other_members: [ { relation: "partner|child|roommate", preferences: [] } ] }
  - health: { conditions: [], notes: "..." }
  - notes: "Free-form additional relevant context (avoid redundancy)."

Rules stressed to the model:
  - Never hallucinate (include only facts explicitly implied by data). If uncertain, omit.
  - Merge with existing: preserve still-valid info, update conflicting facts with latest consistent evidence.
  - Deduplicate arrays (case-insensitive), keep stable ordering (recently reinforced items can appear earlier but no duplicates).
  - Remove items explicitly contradicted by newer evidence.
  - Exclude ephemeral conversational fluff (greetings, thanks, jokes) unless they encode persistent preference.
  - Output VALID JSON ONLY, no markdown, no preambles.
  - If no substantive info, return existing_profile unchanged or {} if none.

CLI usage examples:
  uv run python data/scripts/enrich_user_profiles.py --user-id user1
  uv run python data/scripts/enrich_user_profiles.py --dry-run
  uv run python data/scripts/enrich_user_profiles.py --max-chars 60000
  uv run python data/scripts/enrich_user_profiles.py  # processes all users seen in either table

Exit code 0 on success (all processed), 1 if any user failed.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import psycopg2
from dotenv import load_dotenv
from openai import OpenAI, APIStatusError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

load_dotenv()
log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
_log_level = getattr(logging, log_level_name, logging.INFO)
logging.basicConfig(level=_log_level, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("openai").setLevel(logging.WARNING)


@dataclass
class SummaryRow:
    thread_id: str
    summary: str
    updated_at: str


@dataclass
class MessageRow:
    thread_id: str
    role: str
    content: str
    conversation_updated_at: str


# ---------------------------- DB Helpers ----------------------------

def _conn_params() -> dict:
    load_dotenv()
    return {
        "host": os.getenv("PGHOST", "localhost"),
        "port": int(os.getenv("PGPORT", 5432)),
        "database": os.getenv("PGDATABASE", "aidb"),
        "user": os.getenv("PGUSER", "admin"),
        "password": os.getenv("PGPASSWORD", "Admin12345678"),
    }


def _openai_client() -> OpenAI:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    base_url = os.getenv("OPENAI_BASE_URL")
    api_version = os.getenv("OPENAI_API_VERSION") or "2024-10-21"
    default_query = {"api-version": api_version} if base_url else None
    return OpenAI(api_key=api_key, base_url=base_url, default_query=default_query)


def _target_model() -> str:
    return os.getenv("OPENAI_MODEL") or "gpt-4o-mini"


def _fetch_user_ids(params: dict, specific: Optional[str]) -> List[str]:
    if specific:
        return [specific]
    sql = """
        SELECT DISTINCT user_id FROM conversations_raw
        UNION
        SELECT DISTINCT user_id FROM conversation_summaries
        UNION
        SELECT DISTINCT user_id FROM user_profiles
        ORDER BY 1
    """
    conn = psycopg2.connect(**params)
    cur = conn.cursor()
    try:
        cur.execute(sql)
        return [r[0] for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def _fetch_summaries(params: dict, user_id: str, limit: int | None = None) -> List[SummaryRow]:
    sql = (
        "SELECT thread_id, summary, to_char(updated_at, 'YYYY-MM-DD" "T" "HH24:MI:SSZ') "
        "FROM conversation_summaries WHERE user_id=%s ORDER BY updated_at DESC"
    )
    if limit:
        sql += " LIMIT %s"
    conn = psycopg2.connect(**params)
    cur = conn.cursor()
    rows: List[SummaryRow] = []
    try:
        if limit:
            cur.execute(sql, (user_id, limit))
        else:
            cur.execute(sql, (user_id,))
        for thread_id, summary, updated_at in cur.fetchall():
            rows.append(SummaryRow(thread_id=thread_id, summary=summary, updated_at=updated_at))
    finally:
        cur.close()
        conn.close()
    return rows


def _fetch_messages(params: dict, user_id: str) -> List[MessageRow]:
    sql = (
        "SELECT thread_id, messages, to_char(updated_at, 'YYYY-MM-DD" "T" "HH24:MI:SSZ') "
        "FROM conversations_raw WHERE user_id=%s ORDER BY updated_at DESC"
    )
    conn = psycopg2.connect(**params)
    cur = conn.cursor()
    out: List[MessageRow] = []
    try:
        cur.execute(sql, (user_id,))
        for thread_id, messages, updated_at in cur.fetchall():
            # messages is a list[dict]
            if not isinstance(messages, list):
                continue
            for msg in messages:  # type: ignore[assignment]
                role = msg.get("role")
                content = msg.get("content")
                if not role or content is None:
                    continue
                out.append(
                    MessageRow(
                        thread_id=thread_id,
                        role=str(role),
                        content=str(content),
                        conversation_updated_at=updated_at,
                    )
                )
    finally:
        cur.close()
        conn.close()
    return out


def _fetch_existing_profile(params: dict, user_id: str) -> Optional[Dict[str, Any]]:
    sql = "SELECT profile FROM user_profiles WHERE user_id=%s"
    conn = psycopg2.connect(**params)
    cur = conn.cursor()
    try:
        cur.execute(sql, (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        profile = row[0]
        if isinstance(profile, dict):
            return profile
        try:
            return json.loads(profile) if isinstance(profile, str) else None
        except Exception:
            return None
    finally:
        cur.close()
        conn.close()


def _upsert_profile(params: dict, user_id: str, profile: Dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        logger.info("(dry-run) Would upsert profile for user_id=%s", user_id)
        return
    conn = psycopg2.connect(**params)
    cur = conn.cursor()
    payload = json.dumps(profile, ensure_ascii=False)
    try:
        cur.execute(
            """
            INSERT INTO user_profiles (user_id, profile)
            VALUES (%s, %s::jsonb)
            ON CONFLICT (user_id) DO UPDATE
              SET profile=EXCLUDED.profile, updated_at=now()
            """,
            (user_id, payload),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ---------------------------- LLM Interaction ----------------------------
SYSTEM_PROMPT = """
You are a precise user profile enrichment engine.
You receive JSON containing: existing_profile (object or null), conversation_summaries (array newest first), recent_messages (flattened messages newest first).
Your job: Produce a SINGLE merged, up-to-date JSON object capturing durable, personalization-relevant facts ONLY.

STRICT RULES:
- Output ONLY valid JSON (no markdown fences, no comments).
- Do NOT invent or speculate. If information is unclear, omit it.
- Preserve still-valid fields from existing_profile.
- Update or remove fields contradicted by newer evidence (recency wins).
- Include only persistent preferences or traits: styles, diet, allergens, restrictions, goals, household context, favorite/disliked items, cuisines, ingredients, flavor or cooking style preferences, notable constraints (budget, time, equipment) if explicitly stated.
- Exclude transient greetings, generic compliments, filler, apologies.
- Keep arrays unique (case-insensitive), concise; use snake_case keys.
- If no substantive data and existing_profile is null, return {}.

SUGGESTED STRUCTURE (optional – adapt to evidence):
{
  "style": { "tone": str, "verbosity": str, "formality": str },
  "diet": { "restrictions": [], "allergens": [], "goals": [] },
  "preferences": { "favorite_cuisines": [], "favorite_ingredients": [], "disliked_items": [], "flavor_profile": [], "preparation_styles": [] },
  "favorite_dishes": [],
  "goals": [],
  "household": { "has_kids": bool, "other_members": [ { "relation": str, "preferences": [] } ], "notes": str },
  "health": { "conditions": [], "notes": str },
  "notes": str
}

Return ONLY the merged JSON object.
"""
# Re-evaluate debug flag now that SYSTEM_PROMPT exists
# (Removed PROFILE_ENRICH_DEBUG; rely on logger.isEnabledFor(logging.DEBUG))
if logger.isEnabledFor(logging.DEBUG):
    logger.debug("[DEBUG] SYSTEM PROMPT BEGIN\n%s\n[DEBUG] SYSTEM PROMPT END", SYSTEM_PROMPT)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=45),
    retry=retry_if_exception_type((RateLimitError, APIStatusError)),
    reraise=True,
)
def _generate_profile(client: OpenAI, model: str, payload: dict) -> Optional[Dict[str, Any]]:
    """Generate profile with a simple two-pass JSON validation.

    Pass 1: Ask model for JSON. If parseable -> return.
    Pass 2 (repair): If invalid, send raw text back asking strictly for corrected JSON only.
    If still invalid -> return None (caller may skip update).
    """
    user_content = json.dumps(payload, ensure_ascii=False)
    if logger.isEnabledFor(logging.DEBUG):
        # Truncate very large payloads to avoid log flooding (keep first 8000 chars)
        _trunc_limit = 8000
        _shown = user_content[:_trunc_limit]
        if len(user_content) > _trunc_limit:
            _shown += f"\n...[TRUNCATED {len(user_content)-_trunc_limit} CHARS]"
        logger.debug(
            "[DEBUG] Outbound user payload length=%d chars before sending to model:\n%s",
            len(user_content),
            _shown,
        )
    # Pass 1
    resp1 = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        max_output_tokens=8000,
    )
    raw1 = getattr(resp1, "output_text", None)  # type: ignore[attr-defined]
    if logger.isEnabledFor(logging.DEBUG):
        try:
            logger.debug("[DEBUG] Raw response pass1: %s", json.dumps(resp1.model_dump(), ensure_ascii=False)[:4000])  # type: ignore[attr-defined]
        except Exception:
            logger.debug("[DEBUG] Could not serialize pass1 response")
    if raw1:
        text1 = str(raw1).strip()
        if text1.startswith("```") or text1.startswith("```json"):
            lines = [line for line in text1.splitlines() if not line.strip().startswith("```")]
            text1 = "\n".join(lines).strip()
        try:
            data = json.loads(text1)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        # Pass 2 repair
        repair_instructions = (
            "The previous output was not valid JSON or not a JSON object. "
            "Please output ONLY corrected JSON (no markdown, no comments). If content is unrecoverable, output {}."
        )
        resp2 = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
                {"role": "user", "content": f"Previous invalid output:\n{text1}"},
                {"role": "user", "content": repair_instructions},
            ],
            max_output_tokens=800,
        )
        if logger.isEnabledFor(logging.DEBUG):
            try:
                logger.debug("[DEBUG] Raw response pass2: %s", json.dumps(resp2.model_dump(), ensure_ascii=False)[:4000])  # type: ignore[attr-defined]
            except Exception:
                logger.debug("[DEBUG] Could not serialize pass2 response")
        raw2 = getattr(resp2, "output_text", None)  # type: ignore[attr-defined]
        if not raw2:
            for item in getattr(resp2, "output", []) or []:  # type: ignore[attr-defined]
                if getattr(item, "type", None) == "output_text":
                    txt = getattr(item, "text", None)
                    if txt:
                        raw2 = txt
                        break
        if raw2:
            text2 = str(raw2).strip()
            if text2.startswith("```") or text2.startswith("```json"):
                lines = [line for line in text2.splitlines() if not line.strip().startswith("```")]
                text2 = "\n".join(lines).strip()
            try:
                data2 = json.loads(text2)
                if isinstance(data2, dict):
                    return data2
            except Exception:
                return None
    return None


# ---------------------------- Core Processing ----------------------------

def _cap_char_budget(summaries: List[SummaryRow], messages: List[MessageRow], max_chars: int) -> tuple[List[SummaryRow], List[MessageRow]]:
    used = 0
    kept_summaries: List[SummaryRow] = []
    for s in summaries:
        chunk_len = len(s.summary)
        if used + chunk_len > max_chars:
            break
        kept_summaries.append(s)
        used += chunk_len
    kept_messages: List[MessageRow] = []
    for m in messages:
        chunk_len = len(m.content)
        if used + chunk_len > max_chars:
            break
        kept_messages.append(m)
        used += chunk_len
    return kept_summaries, kept_messages


def _build_payload(existing: Optional[Dict[str, Any]], summaries: List[SummaryRow], messages: List[MessageRow]) -> dict:
    return {
        "existing_profile": existing if existing is not None else None,
        "conversation_summaries": [
            {"thread_id": s.thread_id, "updated_at": s.updated_at, "summary": s.summary}
            for s in summaries
        ],
        "recent_messages": [
            {
                "thread_id": m.thread_id,
                "role": m.role,
                "content": m.content,
                "conversation_updated_at": m.conversation_updated_at,
            }
            for m in messages
        ],
    }


def _process_user(user_id: str, params: dict, client: OpenAI, model: str, max_chars: int, dry_run: bool) -> bool:
    summaries = _fetch_summaries(params, user_id)
    messages = _fetch_messages(params, user_id)
    if not summaries and not messages:
        logger.info("No data for user_id=%s (skipping)", user_id)
        return True
    summaries_capped, messages_capped = _cap_char_budget(summaries, messages, max_chars)
    existing = _fetch_existing_profile(params, user_id)
    payload = _build_payload(existing, summaries_capped, messages_capped)
    logger.info(
        "Building profile for user_id=%s (existing=%s, summaries_used=%d/%d, messages_used=%d/%d, char_budget=%d)",
        user_id,
        "yes" if existing else "no",
        len(summaries_capped),
        len(summaries),
        len(messages_capped),
        len(messages),
        max_chars,
    )
    try:
        profile = _generate_profile(client, model, payload)
    except Exception as e:  # pragma: no cover
        logger.exception("Generation error for user_id=%s: %s", user_id, e)
        return False
    if profile is None:
        logger.warning("Skipping update for user_id=%s (no valid JSON after repair)", user_id)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("No valid JSON after repair for user_id=%s", user_id)
        return True
    if dry_run:
        print(f"\n=== GENERATED PROFILE user_id={user_id} ===\n{json.dumps(profile, indent=2, ensure_ascii=False)}\n")
    _upsert_profile(params, user_id, profile, dry_run)
    logger.info("Profile upserted for user_id=%s (keys=%s)", user_id, ",".join(sorted(profile.keys())[:10]))
    return True


# ---------------------------- CLI ----------------------------

def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Enrich user profiles from conversations & summaries")
    p.add_argument("--user-id", help="Process only this user_id")
    p.add_argument("--max-chars", type=int, default=100_000, help="Max combined character budget (default 100000)")
    p.add_argument("--dry-run", action="store_true", help="Print profile instead of writing DB")
    return p.parse_args()


def main() -> bool:
    args = _args()
    params = _conn_params()
    client = _openai_client()
    model = _target_model()
    user_ids = _fetch_user_ids(params, args.user_id)
    if not user_ids:
        logger.info("No users found to process.")
        return True
    failures = 0
    for uid in user_ids:
        if not _process_user(uid, params, client, model, args.max_chars, args.dry_run):
            failures += 1
    if failures:
        logger.error("Completed with %d failure(s)", failures)
    else:
        logger.info("All profiles processed successfully")
    return failures == 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(0 if main() else 1)
