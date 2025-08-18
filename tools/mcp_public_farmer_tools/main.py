"""MCP server for public farmer tools using FastMCP (HTTP transport).

Features
- Streamable HTTP transport (default)
- Wildcard CORS (configurable)
- Simple static API key auth via Authorization: Bearer <TOKEN>
- Single-file server exposing demo tools and a health endpoint

Environment variables
- HOST (default: 0.0.0.0)
- PORT (default: 8012)
- MCP_CORS_ORIGINS (default: "*" or comma-separated list)
- MCP_API_KEY (required; static bearer token for auth)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from fastmcp.server.auth.auth import AccessToken, TokenVerifier
from starlette.requests import Request
from starlette.responses import PlainTextResponse


class EnvAPIKeyVerifier(TokenVerifier):
    """Very simple static bearer token verifier based on environment variable.

    This is suitable for basic protection only. For production-grade auth,
    prefer JWT verification or OAuth (see FastMCP auth docs).
    """

    def __init__(self, required_token: str):
        self._token = required_token
        # FastMCP expects this attribute on AuthProviders for HTTP metadata; keep None
        self.resource_server_url: Optional[str] = None

    def verify_token(self, token: str) -> Optional[AccessToken]:
        if token and token == self._token:
            # Minimal access token; add claims as needed
            return AccessToken(subject="api-key-user")
        return None


def _get_cors_origins(raw: str | None) -> list[str] | str:
    if not raw or raw.strip() == "*":
        return "*"
    return [o.strip() for o in raw.split(",") if o.strip()]


def build_server() -> tuple[FastMCP, object]:
    """Create FastMCP server and ASGI app configured for HTTP, CORS, and auth."""

    api_key = os.getenv("MCP_API_KEY")
    if not api_key:
        print("ERROR: MCP_API_KEY is required for server authentication.", file=sys.stderr)
        sys.exit(2)

    auth = EnvAPIKeyVerifier(api_key)
    mcp = FastMCP("Public Farmer Tools", auth=auth)

    # Tools
    @mcp.tool
    def echo(text: str) -> str:
        """Echo back the provided text for simple connectivity checks."""
        return text

    @mcp.tool
    def list_produce() -> List[str]:
        """Return a static demo list of seasonal produce."""
        return [
            "Tomatoes",
            "Cucumbers",
            "Zucchini",
            "Bell peppers",
            "Basil",
        ]

    @mcp.tool
    def server_time() -> str:
        """Return server time in ISO 8601 format (UTC)."""
        return datetime.utcnow().isoformat() + "Z"

    # Health check route at "/health"
    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    # Build ASGI app and attach CORS
    app = mcp.http_app()
    allow_origins = _get_cors_origins(os.getenv("MCP_CORS_ORIGINS", "*"))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins if isinstance(allow_origins, list) else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    return mcp, app


def main() -> None:
    """Run the server in HTTP transport with configured host/port."""
    # Load .env first for local dev
    load_dotenv()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8012"))
    mcp, _ = build_server()
    # Streamable HTTP is the recommended remote transport
    mcp.run(transport="http", host=host, port=port)


"""ASGI application entrypoint for uvicorn/gunicorn.

This allows running the app without starting via mcp.run(), which is useful
when you want to inject middlewares (like CORS) and run under uvicorn.
"""

# Build at import-time for container runtimes
load_dotenv()
_mcp, app = build_server()

if __name__ == "__main__":
    main()
