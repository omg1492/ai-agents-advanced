"""Seed a set of example conversation threads for summarization testing.

Updates:
 - All conversations now belong to a single configurable *user_id* (default 'user1').
 - Added richer multi‑turn transcripts (some 6+ turns) to better exercise summarizer.

Behavior:
 - First clears ALL existing records in `conversations_raw` (dev reset) then inserts
     N demo conversations with `summary_status='pending'`.
 - Skips any thread already present (idempotent). Thread IDs are random UUIDs each run;
     therefore re-running will typically insert a fresh set unless limited via --max.

Configuration:
    Environment (loaded via .env):
        PGHOST / PGPORT / PGDATABASE / PGUSER / PGPASSWORD  (Postgres connection)
        GEN_CONV_USER_ID (override default user id; defaults to 'user1')

CLI:
    --user-id VALUE   Override user id (takes precedence over env)
    --max INT         Limit number of scenario conversations inserted (<= total scenarios)

Usage examples:
    uv run python data/scripts/gen_conversations.py
    uv run python data/scripts/gen_conversations.py --user-id demo --max 3

Exit code: 0 success, 1 failure.
WARNING: This script truncates the entire conversations_raw table (dev only). Do not
         run against production data.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
import argparse
from datetime import datetime, timezone  # retained if timestamps reintroduced later
from typing import List, Dict, Any, Sequence

import psycopg2
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _conn_params() -> dict:
    load_dotenv()
    return {
        "host": os.getenv("PGHOST", "localhost"),
        "port": int(os.getenv("PGPORT", 5432)),
        "database": os.getenv("PGDATABASE", "aidb"),
        "user": os.getenv("PGUSER", "admin"),
        "password": os.getenv("PGPASSWORD", "Admin12345678"),
    }


def _utc() -> str:  # kept for possible future enrichment; unused after simplification
    return datetime.now(timezone.utc).isoformat()


def _scenario_definitions() -> List[tuple[str, Sequence[tuple[str, str]]]]:
    """Return list of (title, turns) scenario definitions.

    Each turns sequence is multi‑turn where reasonable to exercise summarizer nuance.
    """
    return [
        (
            "Greeting / capabilities",
            [
                ("user", "Hi, what can you help me with today?"),
                ("assistant", "I can answer questions about local farm products, availability context, general food ideas, and help remember your preferences."),
                ("user", "Great, let's start then."),
            ],
        ),
        (
            "Goat cheese inquiry multi-turn",
            [
                ("user", "I'm looking for fresh goat cheese."),
                ("assistant", "I can look up goat cheese options and styles available in the catalog."),
                ("user", "Prefer something mild and maybe herb coated."),
                ("assistant", "Noted: mild preference and herb coating. I will surface those first when you ask to list them."),
                ("user", "Cool, remind me later if I forget I said mild."),
            ],
        ),
        (
            "Diet preference setup (ovo-vegetarian)",
            [
                ("user", "I'm mostly vegetarian but I still eat eggs; please remember that."),
                ("assistant", "I'll store a preference: vegetarian with eggs allowed. I won't include meat unless you explicitly ask."),
                ("user", "If I ask for protein ideas later, consider eggs acceptable."),
                ("assistant", "Understood. I'll bias toward plant-based plus eggs as protein sources."),
            ],
        ),
        (
            "Stock pattern curiosity",
            [
                ("user", "Do organic carrots usually sell out before weekends?"),
                ("assistant", "They can move faster ahead of large meals, but I only confirm specific availability when you request a product."),
                ("user", "Ok, I'll ask specifically later."),
            ],
        ),
        (
            "Tomato basil recipe idea",
            [
                ("user", "I have tomatoes and basil from the farm box. Any quick idea?"),
                ("assistant", "Slice tomatoes, add chopped basil, olive oil, and a pinch of salt for a simple salad."),
                ("user", "Maybe I'll add mozzarella."),
                ("assistant", "That would turn it into a caprese-style salad—great addition."),
            ],
        ),
        (
            "Follow-up preference reinforcement",
            [
                ("user", "Remember I'm avoiding very spicy items right now."),
                ("assistant", "Got it. I'll note a temporary preference to avoid highly spicy products unless you opt in."),
                ("user", "Thanks. Also keep seasonal suggestions concise."),
                ("assistant", "Will keep seasonal tips brief and relevant."),
            ],
        ),
    ]


def _build_conversations(user_id: str, max_count: int | None = None) -> List[Dict[str, Any]]:
    data: List[Dict[str, Any]] = []
    scenarios = _scenario_definitions()
    if max_count is not None:
        scenarios = scenarios[: max(0, min(max_count, len(scenarios)))]
    for title, turns in scenarios:
        thread_id = str(uuid.uuid4())
        # Simplified message objects: only role + content (per new requirement)
        messages = [
            {"role": role, "content": content}
            for role, content in turns
        ]
        data.append(
            {
                "user_id": user_id,
                "thread_id": thread_id,
                "title": title,
                "messages": messages,
            }
        )
    return data


def _insert(convos: List[Dict[str, Any]], params: dict) -> int:
    conn = psycopg2.connect(**params)
    cur = conn.cursor()
    inserted = 0
    try:
        # Dev reset: remove all existing raw conversations (cascades to summaries)
        cur.execute("TRUNCATE TABLE conversations_raw CASCADE;")
        logger.info("Truncated conversations_raw (dev reset)")
        for c in convos:
            cur.execute(
                """INSERT INTO conversations_raw (thread_id, user_id, title, messages, summary_status)
                    VALUES (%s,%s,%s,%s::jsonb,'pending')""",
                (
                    c["thread_id"],
                    c["user_id"],
                    c["title"],
                    json.dumps(c["messages"]),
                ),
            )
            inserted += 1
        conn.commit()
        return inserted
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            cur.close()
        finally:
            conn.close()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate sample conversations for memory summarization")
    p.add_argument("--user-id", help="Override user id (env GEN_CONV_USER_ID else 'user1')")
    p.add_argument("--max", type=int, help="Max number of scenarios to insert")
    return p.parse_args()


def main() -> bool:
    args = _parse_args()
    try:
        env_user = os.getenv("GEN_CONV_USER_ID") or "user1"
        user_id = args.user_id or env_user
        params = _conn_params()
        convos = _build_conversations(user_id=user_id, max_count=args.max)
        count = _insert(convos, params)
        logger.info(
            "Reset + inserted %d conversations for user_id=%s.", count, user_id
        )
        return True
    except Exception as e:  # pragma: no cover - defensive
        logger.exception("Generation failed: %s", e)
        return False


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(0 if main() else 1)
