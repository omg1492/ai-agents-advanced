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
  - Message format mirrors LLM usage: {"role": "user|assistant", "content": str, "created_at": iso, "mode": "chat"}.
  - All methods are async-compatible but use sync SQLAlchemy engine (lightweight writes).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

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
        url = f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.database}"
        self.engine: Engine = create_engine(url, echo=False, pool_pre_ping=True)
        logger.info("ConversationStore initialized (db=%s)", db.database)

    def _utcnow(self) -> str:
        return datetime.now(timezone.utc).isoformat()

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
                    INSERT INTO conversations_raw (thread_id, user_id, messages)
                    VALUES (:thread_id, :user_id, CAST(:messages AS jsonb))
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
                    INSERT INTO conversations_raw (thread_id, user_id, messages)
                    VALUES (:thread_id, :user_id, CAST(:messages AS jsonb))
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

    def build_message(self, role: str, content: str, mode: str = "chat") -> Dict[str, Any]:
        return {
            "role": role,
            "content": content,
            "created_at": self._utcnow(),
            "mode": mode,
        }
