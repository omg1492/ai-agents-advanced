"""Conversation persistence service.

Stores per-thread conversation messages in PostgreSQL table `conversations_raw`.

Schema (see data/scripts/sql/tables/07_create_conversations_raw.sql):
    id serial PK
    thread_id text unique
    user_id text
    messages jsonb (ordered array of message objects)
    summary_status text (pending|processing|done|error)
    created_at timestamptz default now()
    updated_at timestamptz default now()
    expires_at timestamptz default now()+interval '7 days'

Design:
    - Append-only semantics at logical level: we replace full JSONB array each update.
    - Each turn (user + assistant) triggers an upsert ensuring durability even if client disconnects
        after user message or before assistant message; we persist after each message separately.
    - Persisted message JSON is intentionally minimal: {"role": "user|assistant", "content": str}.
        (Timestamps / mode flags are *not* stored to keep storage lean and reproducible. Any runtime
        timestamp needs are handled in-memory; ordering relies on array order + row updated_at.)
    - All methods are async-compatible but use sync SQLAlchemy engine (lightweight writes).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.services.config_service import ConfigService, AppConfig

logger = logging.getLogger(__name__)


class ConversationStore:
    """Handle persistence of conversation transcripts in conversations_raw."""

    def __init__(self, config: AppConfig | None = None):
        cfg_service = ConfigService()
        self._config = config or cfg_service.config
        db = self._config.db
        url = f"postgresql://{quote_plus(db.user)}:{quote_plus(db.password)}@{db.host}:{db.port}/{db.database}?sslmode={db.sslmode}"
        self.engine: Engine = create_engine(url, echo=False, pool_pre_ping=True)
        logger.info("ConversationStore initialized (db=%s)", db.database)

    def _utcnow(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_thread(self, thread_id: str, user_id: str, title: str) -> None:
        """Create an empty conversation row immediately when a thread is created.

        Idempotent: if row already exists (rare – e.g. retry) it leaves existing messages intact.
        """
        with self.engine.begin() as conn:
            # Try insert first; on unique violation fall back silently (let caller proceed)
            try:
                conn.execute(
                    text(
                        """
                        INSERT INTO conversations_raw (thread_id, user_id, title, messages)
                        VALUES (:thread_id, :user_id, :title, '[]'::jsonb)
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    {"thread_id": thread_id, "user_id": user_id, "title": title},
                )
            except Exception as e:  # pragma: no cover
                logger.warning("create_thread insert failed thread=%s: %s", thread_id, e)

    def upsert_message(self, thread_id: str, user_id: str, message: Dict[str, Any]) -> None:
        """Append a message, inserting row if it doesn't yet exist.

        Uses two-phase logic (UPDATE then INSERT) to avoid ON CONFLICT syntax/
        casting issues seen with some driver param styles on Windows dev env.
        """
        append_json = json.dumps([message])
        with self.engine.begin() as conn:
            upd = text(
                """
                UPDATE conversations_raw
                SET messages = messages || CAST(:append AS jsonb),
                    updated_at = now()
                WHERE thread_id = :thread_id AND user_id = :user_id
                """
            )
            res = conn.execute(upd, {"append": append_json, "thread_id": thread_id, "user_id": user_id})
            if res.rowcount == 0:
                ins = text(
                    """
                    INSERT INTO conversations_raw (thread_id, user_id, title, messages)
                    VALUES (:thread_id, :user_id, 'Untitled conversation', CAST(:messages AS jsonb))
                    """
                )
                conn.execute(ins, {"thread_id": thread_id, "user_id": user_id, "messages": append_json})
        logger.debug("Persisted message role=%s thread=%s", message.get("role"), thread_id)

    def replace_messages(self, thread_id: str, user_id: str, messages: List[Dict[str, Any]]) -> None:
        """Replace entire message array (idempotent)."""
        msgs_json = json.dumps(messages)
        with self.engine.begin() as conn:
            upd = text(
                """
                UPDATE conversations_raw
                SET messages = CAST(:messages AS jsonb),
                    updated_at = now()
                WHERE thread_id = :thread_id AND user_id = :user_id
                """
            )
            res = conn.execute(upd, {"messages": msgs_json, "thread_id": thread_id, "user_id": user_id})
            if res.rowcount == 0:
                ins = text(
                    """
                    INSERT INTO conversations_raw (thread_id, user_id, title, messages)
                    VALUES (:thread_id, :user_id, 'Untitled conversation', CAST(:messages AS jsonb))
                    """
                )
                conn.execute(ins, {"thread_id": thread_id, "user_id": user_id, "messages": msgs_json})
        logger.debug("Replaced messages thread=%s count=%d", thread_id, len(messages))

    def fetch_messages(self, thread_id: str, user_id: str) -> List[Dict[str, Any]]:
        sql = text("SELECT messages FROM conversations_raw WHERE thread_id=:tid AND user_id=:uid")
        with self.engine.connect() as conn:
            row = conn.execute(sql, {"tid": thread_id, "uid": user_id}).fetchone()
        if not row:
            return []
        return row.messages  # type: ignore[attr-defined]

    def delete_conversation(self, thread_id: str, user_id: str) -> int:
        sql = text("DELETE FROM conversations_raw WHERE thread_id=:tid AND user_id=:uid")
        with self.engine.begin() as conn:
            result = conn.execute(sql, {"tid": thread_id, "uid": user_id})
        return result.rowcount if result else 0

    def list_threads(self, user_id: str, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        """Return paginated list of thread metadata for a user ordered by updated_at desc."""
        sql = text(
            """
            SELECT thread_id, title, created_at, updated_at, jsonb_array_length(messages) AS message_count
            FROM conversations_raw
            WHERE user_id = :uid
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(sql, {"uid": user_id, "limit": limit, "offset": offset}).mappings().all()
        return [dict(r) for r in rows]

    def get_thread_metadata(self, thread_id: str, user_id: str) -> dict[str, Any] | None:
        sql = text(
            """
            SELECT thread_id, title, created_at, updated_at, jsonb_array_length(messages) AS message_count
            FROM conversations_raw
            WHERE thread_id=:tid AND user_id=:uid
            """
        )
        with self.engine.connect() as conn:
            row = conn.execute(sql, {"tid": thread_id, "uid": user_id}).mappings().first()
        return dict(row) if row else None

    def hydrate_messages_if_missing(self, thread_id: str, user_id: str) -> list[dict[str, Any]]:
        """Helper used by API to load messages when not in memory (server restart, cache miss)."""
        return self.fetch_messages(thread_id, user_id)

    def build_message(self, role: str, content: str) -> Dict[str, Any]:
        """Return minimal persisted message structure.

        Only role and content are stored (no per-message timestamp or mode). This keeps
        the DB representation stable and small; temporal ordering is derived from array
        position and `updated_at` column on the parent row.
        """
        return {"role": role, "content": content}

    def rename_thread(self, thread_id: str, user_id: str, new_title: str) -> int:
        """Rename a thread title. Returns number of rows updated (0 if not found)."""
        if not new_title:
            return 0
        with self.engine.begin() as conn:
            res = conn.execute(
                text(
                    """
                    UPDATE conversations_raw
                    SET title = :title, updated_at = now()
                    WHERE thread_id = :tid AND user_id = :uid
                    """
                ),
                {"title": new_title, "tid": thread_id, "uid": user_id},
            )
        return res.rowcount if res else 0
