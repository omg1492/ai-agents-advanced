"""Batch summarize pending conversations into `conversation_summaries`.

Updated approach (2025-09-14): we now feed the ORIGINAL JSON message array directly
to the model instead of constructing a text transcript. Each conversation row
contains `messages` as an array of objects: `{ "role": "user"|"assistant", "content": "..." }`.

Workflow:
 1. Select rows from `conversations_raw` with `summary_status='pending'` (respecting
     minimum message count and limit).
 2. Pass raw JSON array (no extra framing text) to the model. The system prompt
     explains the structure and instructs the model to output ONLY a pure summary.
 3. Model produces a neutral, detailed recap (<= 250 words) capturing: user intents,
     explicit preferences (diet, allergens, likes/dislikes, goals), product interests,
     constraints, assistant recommendations, any decisions / agreements / resolutions,
     and unresolved follow‑ups. Ignore greetings / pleasantries.
 4. Embed summary (2000‑d) and UPSERT into `conversation_summaries`.
 5. Mark source as `done` or `error`.

Design notes:
 - Idempotent: summaries overwritten via ON CONFLICT.
 - Simplicity: no intermediate transcript construction (reduces accidental truncation / bias).
 - Output MUST be only the summary text (no JSON, no preamble, no commentary).
 - Word cap enforced by instructions (<=250 words) plus a generous token ceiling.

Usage examples:
  uv run python data/scripts/process_conversations.py                # default (limit 20)
  uv run python data/scripts/process_conversations.py --limit 5
  uv run python data/scripts/process_conversations.py --dry-run

Exit code 0 on full success; 1 if any conversation failed (still attempts all).
"""
from __future__ import annotations

import argparse
import logging
import os
import json
from dataclasses import dataclass
from typing import List

import psycopg2
from dotenv import load_dotenv
from openai import OpenAI, APIStatusError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("openai").setLevel(logging.WARNING)


@dataclass
class ConversationRow:
    thread_id: str
    user_id: str
    title: str
    messages: list[dict]


def _conn_params() -> dict:
    load_dotenv()
    return {
        "host": os.getenv("PGHOST", "localhost"),
        "port": int(os.getenv("PGPORT", 5432)),
        "database": os.getenv("PGDATABASE", "aidb"),
        "user": os.getenv("PGUSER", "admin"),
        "password": os.getenv("PGPASSWORD", "Admin12345678"),
    }


def _openai_client() -> tuple[OpenAI, str, str]:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    base_url = os.getenv("OPENAI_BASE_URL")
    api_version = os.getenv("OPENAI_API_VERSION") or "2024-10-21"
    model = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL") or "text-embedding-3-large"
    default_query = {"api-version": api_version} if base_url else None
    client = OpenAI(api_key=api_key, base_url=base_url, default_query=default_query)
    return client, model, embedding_model


def _fetch_pending(limit: int, min_messages: int, params: dict) -> List[ConversationRow]:
    sql = (
        "SELECT thread_id, user_id, title, messages "
        "FROM conversations_raw WHERE summary_status='pending' "
        "AND jsonb_array_length(messages) >= %s ORDER BY updated_at ASC LIMIT %s"
    )
    conn = psycopg2.connect(**params)
    cur = conn.cursor()
    rows: List[ConversationRow] = []
    try:
        cur.execute(sql, (min_messages, limit))
        for thread_id, user_id, title, messages in cur.fetchall():
            rows.append(
                ConversationRow(
                    thread_id=thread_id,
                    user_id=user_id,
                    title=title,
                    messages=messages,  # type: ignore[arg-type]
                )
            )
    finally:
        cur.close()
        conn.close()
    return rows


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=45),
    retry=retry_if_exception_type((RateLimitError, APIStatusError)),
    reraise=True,
)
def _summarize(client: OpenAI, model: str, messages: list[dict]) -> str:
    """Summarize a raw conversation message array.

    The model receives:
      - System prompt: detailed instructions & required fields
      - User content: EXACT JSON array of {"role", "content"} objects (no wrapper text)

    Returns plain summary text (no metadata)."""
    system = """
You are a specialized summarizer for chat transcripts.

INPUT FORMAT:
- The user message you receive is a JSON array. Each element is an object with keys: role ("user" or "assistant") and content (string).
- Do NOT assume hidden context. Use only what appears explicitly.

TASK:
Produce a NEUTRAL, FACTUAL summary (<= 250 words) capturing:
  1. Main user intents / questions (group related intents succinctly).
  2. Explicit user preferences or constraints (diet, allergens, likes/dislikes, goals, quantities, budget hints).
  3. Products, ingredients or categories the user showed interest in (only if mentioned).
  4. Assistant recommendations / guidance (what was suggested and why, if stated).
  5. Decisions, confirmations, agreements or resolutions reached (what both sides converged on).
  6. Outstanding follow‑ups or unresolved questions (if any).

STYLE & RULES:
- Omit greetings, pleasantries, small talk, apologies unless they materially change intent.
- No speculation, fabrication, or PII extraction. If something is uncertain, leave it out.
- Do not quote large verbatim passages; paraphrase concisely.
- Output MUST be ONLY the summary text (no preface like "Summary:", no JSON, no bullet label headers).
- Use 1–3 compact paragraphs (no bullet marks, no numbering in output).
- If the conversation is empty or has no substantive content, output: "No substantive content to summarize." (exactly).

FOCUS:
- Strong emphasis on what the user wants + any preferences that could inform future personalization.
- Capture final resolution with enough detail that a future agent can understand context without rereading the raw transcript.
""".strip()

    raw_json = json.dumps(messages, ensure_ascii=False)
    try:
        resp = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": raw_json},
            ],
            max_output_tokens=600,
        )
    except Exception:
        raise
    # Iterate response output items; SDK may return pydantic model objects (no dict .get)
    for item in getattr(resp, "output", []) or []:  # type: ignore[attr-defined]
        item_type = getattr(item, "type", None)
        if not item_type and isinstance(item, dict):  # defensive fallback
            item_type = item.get("type")
        if item_type == "output_text":
            text_val = getattr(item, "text", None)
            if text_val is None and isinstance(item, dict):
                text_val = item.get("text")
            if text_val:
                summary_text = str(text_val).strip()
                # Enforce <=250 words hard cap (truncate gracefully)
                words = summary_text.split()
                if len(words) > 250:
                    summary_text = " ".join(words[:250])
                return summary_text
        # Ignore reasoning items silently
    # Fallback aggregate convenience attribute
    if getattr(resp, "output_text", None):  # type: ignore[attr-defined]
        summary_text = str(resp.output_text).strip()
        words = summary_text.split()
        if len(words) > 250:
            summary_text = " ".join(words[:250])
        return summary_text
    return "(empty summary)"


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=45),
    retry=retry_if_exception_type((RateLimitError, APIStatusError)),
    reraise=True,
)
def _embed(client: OpenAI, model: str, text_value: str) -> list[float]:
    emb = client.embeddings.create(model=model, input=[text_value], dimensions=2000)
    return emb.data[0].embedding  # type: ignore[return-value]


def _upsert_summary(row: ConversationRow, summary: str, embedding: list[float], params: dict, dry_run: bool) -> None:
    if dry_run:
        logger.info("(dry-run) Would upsert summary for thread_id=%s", row.thread_id)
        return
    conn = psycopg2.connect(**params)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO conversation_summaries (thread_id, user_id, summary, embedding)
            VALUES (%s,%s,%s,%s::vector)
            ON CONFLICT (user_id, thread_id) DO UPDATE
              SET summary=EXCLUDED.summary, embedding=EXCLUDED.embedding, updated_at=now()
            """,
            (row.thread_id, row.user_id, summary, f"[{','.join(str(float(v)) for v in embedding)}]"),
        )
        cur.execute(
            "UPDATE conversations_raw SET summary_status='done' WHERE thread_id=%s",
            (row.thread_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        try:
            cur.execute(
                "UPDATE conversations_raw SET summary_status='error' WHERE thread_id=%s",
                (row.thread_id,),
            )
            conn.commit()
        finally:
            raise
    finally:
        try:
            cur.close()
        finally:
            conn.close()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize pending conversations into conversation_summaries")
    p.add_argument("--limit", type=int, default=20, help="Max conversations to process (default 20)")
    p.add_argument("--min-messages", type=int, default=2, help="Minimum message count to summarize (default 2)")
    p.add_argument("--dry-run", action="store_true", help="Run without writing summaries")
    return p.parse_args()


def main() -> bool:
    args = _parse_args()
    params = _conn_params()
    client, model, embedding_model = _openai_client()
    rows = _fetch_pending(args.limit, args.min_messages, params)
    if not rows:
        logger.info("No pending conversations found (limit=%d).", args.limit)
        return True
    logger.info("Processing %d pending conversation(s)...", len(rows))
    failures = 0
    for r in rows:
        try:
            summary = _summarize(client, model, r.messages)
            embedding = _embed(client, embedding_model, summary)
            logger.info("Summarized thread_id=%s (summary len=%d chars)", r.thread_id, len(summary))
            if args.dry_run:
                print("\n=== SUMMARY (thread_id=%s) ===\n%s\n" % (r.thread_id, summary))
            _upsert_summary(r, summary, embedding, params, args.dry_run)
        except Exception as e:  # pragma: no cover - defensive
            failures += 1
            logger.exception("Failed to summarize thread_id=%s: %s", r.thread_id, e)
    if failures:
        logger.error("Completed with %d failure(s)", failures)
    else:
        logger.info("All summaries processed successfully")
    return failures == 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(0 if main() else 1)
