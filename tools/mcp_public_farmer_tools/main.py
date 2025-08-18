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
import hashlib
import random
from typing import Dict, List, Optional

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

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """Validate a static bearer token from env and return an access token.

        Returns an AccessToken instance with minimal claims required by
        FastMCP's auth middleware: token, client_id, and scopes.
        """
        if token and token == self._token:
            return AccessToken(
                token=token,
                client_id="api-key-user",
                scopes=["read:tools"],
            )
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
    def get_seasonal_tips() -> List[str]:
        """Return up to 10 typical seasonal products for the current period (mocked)."""
        month = datetime.utcnow().month
        # Simple northern-hemisphere season mapping
        if month in (12, 1, 2):
            items = [
                "Citrus (oranges, mandarins)",
                "Kale",
                "Brussels sprouts",
                "Leeks",
                "Cabbage",
                "Parsnips",
                "Beets",
                "Winter squash",
                "Turnips",
                "Swiss chard",
            ]
        elif month in (3, 4, 5):
            items = [
                "Asparagus",
                "Radishes",
                "Spinach",
                "Spring onions",
                "Peas",
                "Rhubarb",
                "Lettuce",
                "Strawberries",
                "New potatoes",
            ]
        elif month in (6, 7, 8):
            items = [
                "Strawberries",
                "Tomatoes",
                "Cucumbers",
                "Zucchini",
                "Bell peppers",
                "Green beans",
                "Basil",
                "Sweet corn",
                "Blueberries",
                "Peaches",
            ]
        else:  # 9,10,11
            items = [
                "Apples",
                "Pears",
                "Pumpkin",
                "Butternut squash",
                "Carrots",
                "Broccoli",
                "Cauliflower",
                "Mushrooms",
                "Cranberries",
            ]
        return items[:10]

    @mcp.tool
    def get_current_time() -> str:
        """Return server time in ISO 8601 format (UTC)."""
        return datetime.utcnow().isoformat() + "Z"

    def _daily_rng(key: str) -> random.Random:
        """Create a deterministic RNG seeded by key and current UTC date for stable daily mocks."""
        seed_src = f"{key}-{datetime.utcnow().date()}"
        seed = int(hashlib.sha256(seed_src.encode("utf-8")).hexdigest()[:16], 16)
        return random.Random(seed)

    @mcp.tool
    def get_weather(country: str, city: str) -> Dict[str, float | int | str]:
        """Return mocked current weather for the given location.

        Values are randomized within reasonable ranges and stable for a given
        day/location (deterministic per UTC date).
        """
        month = datetime.utcnow().month
        rng = _daily_rng(f"{country}:{city}")

        # Very simple seasonal temperature bands (Celsius), northern hemisphere
        if month in (12, 1, 2):
            t_min, t_max = (-8.0, 8.0)
        elif month in (3, 4, 5):
            t_min, t_max = (4.0, 20.0)
        elif month in (6, 7, 8):
            t_min, t_max = (18.0, 34.0)
        else:  # 9,10,11
            t_min, t_max = (5.0, 22.0)

        temperature_c = round(rng.uniform(t_min, t_max), 1)
        humidity_pct = int(rng.uniform(35, 90))
        wind_kmh = round(rng.uniform(0, 40), 1)
        precipitation_mm = round(rng.uniform(0, 15), 1)

        return {
            "country": country,
            "city": city,
            "temperature_c": temperature_c,
            "humidity_pct": humidity_pct,
            "wind_kmh": wind_kmh,
            "precipitation_mm": precipitation_mm,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

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
