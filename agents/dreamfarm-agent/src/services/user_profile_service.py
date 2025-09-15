"""User profile retrieval service.

Provides a simple DB accessor to fetch a user's consolidated JSON profile from
`user_profiles` table. Returns a Python dict if present, else None.

Design notes:
- Read-only for now (enrichment pipeline writes profiles externally).
- Uses same SQLAlchemy engine pattern as other services (RAG, memory search).
- Lightweight: single query per request; no caching (profiles assumed small).
"""
from __future__ import annotations

from typing import Any, Optional
import json
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.services.config_service import AppConfig, ConfigService

logger = logging.getLogger(__name__)


class UserProfileService:
    """Service to fetch user profile JSON from PostgreSQL."""

    def __init__(self, app_config: AppConfig | None = None):
        cfg_service = ConfigService()
        self._app_config: AppConfig = app_config or cfg_service.config
        db = self._app_config.db
        url = f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.database}"
        self.engine: Engine = create_engine(url, echo=False, pool_pre_ping=True)
        logger.info("Initialized UserProfileService")

    def get_profile(self, user_id: str) -> Optional[dict[str, Any]]:
        sql = text("SELECT profile FROM user_profiles WHERE user_id = :uid")
        try:
            with self.engine.connect() as conn:
                row = conn.execute(sql, {"uid": user_id}).fetchone()
            if not row:
                return None
            profile_obj = row[0]
            if isinstance(profile_obj, dict):
                return profile_obj  # already JSONB mapped to dict
            if isinstance(profile_obj, str):
                try:
                    return json.loads(profile_obj)
                except Exception:
                    logger.warning("Failed to parse profile JSON string for user_id=%s", user_id)
                    return None
            return None
        except Exception as e:  # pragma: no cover
            logger.warning("User profile fetch failed user_id=%s err=%s", user_id, e)
            return None

__all__ = ["UserProfileService"]
