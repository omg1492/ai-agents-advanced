"""Pytest configuration for DreamFarm Agent tests.

Responsibilities:
1. Load environment variables from .env (non‑destructive)
2. Provide dependency overrides (e.g. auth) so tests stay fast & isolated
"""
from typing import Dict, Any, Tuple
import pytest
from dotenv import load_dotenv


# Load environment variables from .env at session start (non-destructive)
load_dotenv()


@pytest.fixture(scope="session", autouse=True)
def override_auth_dependency():
	"""Override the auth dependency so tests don't need real JWT tokens.

	This keeps unit/integration tests deterministic while production code
	still enforces JWT validation. The override supplies a synthetic user.
	"""
	try:
		from src.main import app, _require_user  # type: ignore
	except Exception:  # pragma: no cover - import failure would surface in tests anyway
		return

	def _test_user_override() -> Tuple[str, bool, Dict[str, Any]]:  # matches expected return structure
		return "test-user", False, {"preferred_username": "test-user", "realm_access": {"roles": []}}

	# Apply override
	app.dependency_overrides[_require_user] = _test_user_override
	yield
	# Cleanup (not strictly required, but keeps state clean for potential future dynamic tests)
	app.dependency_overrides.pop(_require_user, None)
