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
from urllib.parse import quote_plus
import json
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.services.config_service import AppConfig, ConfigService

logger = logging.getLogger(__name__)


class UserProfileService:
    """Service to fetch and update user profile JSON stored in PostgreSQL.

    Write path supports a constrained JSON "patch" merge to reduce reliance on
    the model producing a full correct document. Patch structure (validated
    lightly):

    {
        "set": {"key": value, ...},          # create/overwrite simple fields or objects
        "append": {"arrayField": [..]},      # append unique primitive values to arrays
        "remove": ["field1", "field2"],     # delete top-level fields (optional)
    }

    Merge rules:
    - If no existing profile -> start from empty dict.
    - set: deep merge (dict values merged recursively, primitives overwrite).
    - append: for each target array create if missing; only append values not already present (primitive only).
    - remove: drop listed top-level keys if present.
    - Silently ignore malformed patch parts; never raise to caller (model robustness).
    """

    def __init__(self, app_config: AppConfig | None = None):
        cfg_service = ConfigService()
        self._app_config: AppConfig = app_config or cfg_service.config
        db = self._app_config.db
        url = f"postgresql://{quote_plus(db.user)}:{quote_plus(db.password)}@{db.host}:{db.port}/{db.database}?sslmode={db.sslmode}"
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

    # ---------------- write / merge operations ---------------- #
    def apply_patch(self, user_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """Apply a constrained patch to the user's profile and persist.

        Args:
            user_id: profile owner
            patch: patch dict (see class docstring)
        Returns:
            The updated profile dict after merge (empty dict if creation)
        """
        try:
            current = self.get_profile(user_id) or {}
            if not isinstance(current, dict):  # safety
                current = {}
            if not isinstance(patch, dict):
                patch = {}
            set_block = patch.get("set") if isinstance(patch.get("set"), dict) else {}
            append_block = patch.get("append") if isinstance(patch.get("append"), dict) else {}
            remove_block = patch.get("remove") if isinstance(patch.get("remove"), (list, tuple)) else []

            def deep_merge(dst: dict, src: dict):
                for k, v in src.items():
                    if isinstance(v, dict) and isinstance(dst.get(k), dict):
                        deep_merge(dst[k], v)  # type: ignore[index]
                    else:
                        dst[k] = v

            # set
            deep_merge(current, set_block)
            # append
            for field, values in append_block.items():
                if not isinstance(values, list):
                    continue
                arr = current.get(field)
                if not isinstance(arr, list):
                    arr = []
                # only primitives
                for val in values:
                    if isinstance(val, (str, int, float, bool)) and val not in arr:
                        arr.append(val)
                current[field] = arr
            # remove
            for field in remove_block:
                if field in current:
                    try:
                        del current[field]
                    except Exception:
                        pass

            # persist (UPSERT)
            upsert_sql = text(
                """
                INSERT INTO user_profiles (user_id, profile)
                VALUES (:uid, CAST(:profile AS jsonb))
                ON CONFLICT (user_id) DO UPDATE SET profile = EXCLUDED.profile, updated_at = now()
                """
            )
            with self.engine.begin() as conn:
                conn.execute(upsert_sql, {"uid": user_id, "profile": json.dumps(current, ensure_ascii=False)})
            return current
        except Exception as e:  # pragma: no cover
            logger.warning("User profile patch failed user_id=%s err=%s", user_id, e)
            return self.get_profile(user_id) or {}

    # Verbose variant returning diagnostics for tool feedback
    def apply_patch_with_report(self, user_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """Apply patch and return detailed report.

        Report structure:
        {
          "applied": bool,
          "touched": [...],                # fields attempted (set/append/remove)
          "updated": [...],                # fields actually changed
          "not_found": [...],              # remove targets missing
          "ignored": {                     # invalid segments ignored
              "append": {field: reason},
              "set": {field: reason}
          },
          "errors": ["..."],              # unexpected exceptions collected
          "current": {subset},             # subset of updated fields
          "full_profile": {...}            # full profile ONLY when some operation failed or ignored to help model retry
        }
        """
        report = {
            "applied": False,
            "touched": [],
            "updated": [],
            "not_found": [],
            "ignored": {"append": {}, "set": {}},
            "errors": [],
            "current": {},
        }
        try:
            current_before = self.get_profile(user_id) or {}
            if not isinstance(current_before, dict):
                current_before = {}
            current = json.loads(json.dumps(current_before))  # shallow clone via roundtrip
            if not isinstance(patch, dict):
                report["errors"].append("patch_not_dict")
                patch = {}
            set_block = patch.get("set") if isinstance(patch.get("set"), dict) else {}
            append_block = patch.get("append") if isinstance(patch.get("append"), dict) else {}
            remove_block = patch.get("remove") if isinstance(patch.get("remove"), (list, tuple)) else []
            report["touched"] = list(set_block.keys()) + list(append_block.keys()) + list(remove_block)

            def deep_merge(dst: dict, src: dict):
                for k, v in src.items():
                    if isinstance(v, dict) and isinstance(dst.get(k), dict):
                        deep_merge(dst[k], v)  # type: ignore[index]
                    else:
                        dst[k] = v
            # Track before for updated detection
            before_snapshot = json.loads(json.dumps(current))
            # set
            deep_merge(current, set_block)
            # append
            for field, values in append_block.items():
                if not isinstance(values, list):
                    report["ignored"]["append"][field] = "not_list"
                    continue
                arr = current.get(field)
                if not isinstance(arr, list):
                    arr = []
                added = False
                for val in values:
                    if isinstance(val, (str, int, float, bool)):
                        if val not in arr:
                            arr.append(val)
                            added = True
                    else:
                        report["ignored"]["append"][field] = "non_primitive_value"
                current[field] = arr
                if added and field not in report["updated"]:
                    report["updated"].append(field)
            # remove
            for field in remove_block:
                if field in current:
                    try:
                        del current[field]
                        report["updated"].append(field)
                    except Exception:
                        report["errors"].append(f"remove_failed:{field}")
                else:
                    report["not_found"].append(field)
            # Determine updated fields from set (deep compare top-level changed)
            for k in set_block.keys():
                if before_snapshot.get(k) != current.get(k) and k not in report["updated"]:
                    report["updated"].append(k)
            # Persist
            upsert_sql = text(
                """
                INSERT INTO user_profiles (user_id, profile)
                VALUES (:uid, CAST(:profile AS jsonb))
                ON CONFLICT (user_id) DO UPDATE SET profile = EXCLUDED.profile, updated_at = now()
                """
            )
            with self.engine.begin() as conn:
                conn.execute(upsert_sql, {"uid": user_id, "profile": json.dumps(current, ensure_ascii=False)})
            report["applied"] = True
            # subset = only touched fields that still exist
            subset = {k: current.get(k) for k in report["touched"] if k in current}
            report["current"] = subset
            # Provide full profile only when something was ignored, not_found or errors
            if report["ignored"]["append"] or report["ignored"]["set"] or report["not_found"] or report["errors"]:
                report["full_profile"] = current
            return report
        except Exception as e:  # pragma: no cover
            logger.warning("User profile verbose patch failed user_id=%s err=%s", user_id, e)
            report["errors"].append("exception")
            existing = self.get_profile(user_id) or {}
            report["full_profile"] = existing
            return report

__all__ = ["UserProfileService"]
