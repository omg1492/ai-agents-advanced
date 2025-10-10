"""MCP server for chef and catering services using FastMCP (HTTP transport).

Features
- Mock data for chefs, services, availability with deterministic IDs
- Streamable HTTP transport (default)
- Wildcard CORS (configurable)
- Simple static API key auth via Authorization: Bearer <TOKEN>
- Tools: search_chefs, search_services, check_availability, calculate_pricing, place_order

Environment variables
- HOST (default: 0.0.0.0)
- PORT (default: 8013)
- MCP_CORS_ORIGINS (default: "*" or comma-separated list)
- MCP_API_KEY (required; static bearer token for auth)
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from fastmcp.server.auth.auth import AccessToken, TokenVerifier
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from typing import Callable, Awaitable
import asyncio

# Import mock data and helper functions
from mock_data import (
    MOCK_CHEFS,
    MOCK_SERVICES,
    MOCK_AVAILABILITY,
    get_next_order_id,
    parse_date,
    is_date_available,
    get_next_available_date,
)


# ============================================================================
# Auth & Middleware (copied from farmer_tools pattern)
# ============================================================================

class DeferDeleteMiddleware:
    """ASGI middleware that intercepts DELETE /mcp and responds 200 immediately.

    This is a pragmatic workaround for clients that may prematurely close MCP
    sessions. By short-circuiting DELETE, we keep FastMCP's in-memory session
    alive so follow-up POSTs within a short window can still succeed.
    """

    def __init__(self, app: Callable[..., Awaitable], target_path: str = "/mcp"):
        self.app = app
        self._target_path = target_path.rstrip("/")
        try:
            self._defer_seconds = int(os.getenv("MCP_DEFER_DELETE_SECONDS", "60"))
        except ValueError:
            self._defer_seconds = 60

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and self._defer_seconds > 0:
            path = (scope.get("path") or "").rstrip("/")
            method = scope.get("method") or ""
            if method.upper() == "DELETE" and path == self._target_path:
                print(
                    f"MCP DELETE intercepted at {scope.get('path')}; deferring close for {self._defer_seconds}s"
                )
                orig_headers = scope.get("headers") or []
                scheme = scope.get("scheme", "http")
                server = scope.get("server")
                client = scope.get("client")
                http_version = scope.get("http_version", "1.1")
                body_chunks: list[bytes] = []
                more = True
                try:
                    while more:
                        msg = await receive()
                        if msg.get("type") != "http.request":
                            break
                        data = msg.get("body") or b""
                        if data:
                            body_chunks.append(data)
                        more = msg.get("more_body", False)
                except Exception:
                    body_chunks = []
                buffered_body = b"".join(body_chunks)

                async def _drain_send(_message):
                    return

                async def _body_receive():
                    nonlocal buffered_body
                    b = buffered_body
                    buffered_body = b""
                    return {"type": "http.request", "body": b, "more_body": False}

                async def _delayed_invoke():
                    try:
                        await asyncio.sleep(self._defer_seconds)
                        delayed_scope = {
                            "type": "http",
                            "asgi": {"version": "3.0"},
                            "http_version": http_version,
                            "method": "DELETE",
                            "scheme": scheme,
                            "path": self._target_path,
                            "raw_path": self._target_path.encode("utf-8"),
                            "query_string": b"",
                            "headers": orig_headers,
                            "server": server,
                            "client": client,
                        }
                        await self.app(delayed_scope, _body_receive, _drain_send)
                    except Exception as ex:
                        print(f"Deferred MCP DELETE failed: {ex}")

                asyncio.create_task(_delayed_invoke())
                headers = [(b"content-type", b"text/plain; charset=utf-8")]
                await send({"type": "http.response.start", "status": 200, "headers": headers})
                await send({"type": "http.response.body", "body": b"OK"})
                return
        await self.app(scope, receive, send)


class EnvAPIKeyVerifier(TokenVerifier):
    """Very simple static bearer token verifier based on environment variable.

    This is suitable for basic protection only. For production-grade auth,
    prefer JWT verification or OAuth (see FastMCP auth docs).
    """

    def __init__(self, required_token: str):
        super().__init__(base_url=None)
        self._token = required_token

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """Validate a static bearer token from env and return an access token."""
        if token and token == self._token:
            return AccessToken(
                token=token,
                client_id="api-key-user",
                scopes=["*"],
            )
        return None


def _get_cors_origins(raw: str | None) -> list[str] | str:
    if not raw or raw.strip() == "*":
        return "*"
    return [o.strip() for o in raw.split(",") if o.strip()]


# ============================================================================
# Server & Tools
# ============================================================================

def build_server() -> tuple[FastMCP, object]:
    """Create FastMCP server and ASGI app configured for HTTP, CORS, and auth."""

    api_key = os.getenv("MCP_API_KEY")
    if not api_key:
        print("ERROR: MCP_API_KEY is required for server authentication.", file=sys.stderr)
        sys.exit(2)

    auth = EnvAPIKeyVerifier(api_key)
    mcp = FastMCP("Chef Services", auth=auth)

    # Health check route at "/health"
    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    # TODO: Add MCP tools here (will be added in next steps)

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
    app = DeferDeleteMiddleware(app, target_path="/mcp")
    return mcp, app


def main() -> None:
    """Run the server in HTTP transport with configured host/port."""
    load_dotenv()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8013"))
    mcp, _ = build_server()
    print(f"Starting Chef Services MCP Server on {host}:{port}")
    print(f"Health endpoint: http://{host}:{port}/health")
    print(f"MCP endpoint: http://{host}:{port}/mcp/")
    mcp.run(transport="http", host=host, port=port)


# ASGI application entrypoint for uvicorn/gunicorn
load_dotenv()
_mcp, app = build_server()

if __name__ == "__main__":
    main()
