"""Authentication utilities for validating Keycloak-issued JWTs.

Dev‑focused minimal validator: verifies signature (RS256), issuer and audience,
then extracts username and VIP role. Designed to be dependency-light and
idempotent. Caches JWKS for a short period (in-memory only).
"""
from __future__ import annotations
import logging
from typing import Any, Dict, Tuple
import jwt
from jwt import PyJWKClient, InvalidTokenError

logger = logging.getLogger(__name__)


class AuthService:
    """Service handling JWT validation against Keycloak JWKS."""

    def __init__(self, issuer: str, audience: str, jwks_url: str):
        self.issuer = issuer.rstrip('/')
        self.audience = audience
        self.jwks_url = jwks_url
        self._jwk_client = PyJWKClient(jwks_url)

    def validate(self, token: str) -> Dict[str, Any]:
        """Validate JWT and return claims.

        Raises:
            ValueError: On invalid/expired token.
        """
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat"], "verify_aud": True},
            )
            return claims
        except InvalidTokenError as e:  # pragma: no cover - relied upon in runtime
            raise ValueError(f"Invalid token: {e}")

    @staticmethod
    def extract_identity(claims: Dict[str, Any]) -> Tuple[str, bool]:
        """Extract (username, is_vip) from claims.

        VIP detection checks realm roles and possible custom attributes.
        """
        username = (
            claims.get("preferred_username")
            or claims.get("email")
            or claims.get("sub")
            or "unknown"
        )
        roles = []
        realm_access = claims.get("realm_access", {}) or {}
        if isinstance(realm_access, dict):
            roles = realm_access.get("roles", []) or []
        is_vip = False
        if isinstance(roles, list) and "vip" in roles:
            is_vip = True
        elif claims.get("vip") is True:
            is_vip = True
        elif claims.get("is_vip") is True:
            is_vip = True
        elif isinstance(claims.get("is_vip"), list) and "true" in claims.get("is_vip"):
            is_vip = True
        return username, is_vip
