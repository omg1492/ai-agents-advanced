## MCP Public Farmer Tools (FastMCP)

A minimal MCP server implemented with FastMCP. It exposes a few demo tools to validate MCP wiring and provide a foundation for future farmer-related tools.

### Features

- Single-file server (`main.py`) using FastMCP 2.0
- HTTP transport (streamable) by default; MCP endpoint at `/mcp/`
- Tools:
	- `echo(text: string)` → echoes text back
	- `get_current_time()` → string UTC time ISO 8601
	- `get_seasonal_tips()` → up to 10 typical seasonal products (mocked by month)
	- `get_weather(country: string, city: string)` → mocked JSON weather
- Wildcard CORS enabled by default (override via `MCP_CORS_ORIGINS`)
- Simple Bearer token auth using `MCP_API_KEY`
- Runs locally with uv; Dockerfile and GHCR publishing workflow included

### Run locally

Prereqs: Python 3.12+, uv installed.

Copy `.env.template` to `.env` and set `MCP_API_KEY`.

```
uv sync
uv run python main.py
```

This starts a FastMCP server over HTTP (streamable). MCP endpoint is `http://localhost:8012/mcp/` and health is `http://localhost:8012/health`.

### Docker

Build and run locally:

```
docker build -t mcp-public-farmer-tools:local .
docker run --rm -it -e MCP_API_KEY=dev-secret-key -p 8012:8012 mcp-public-farmer-tools:local
```

GitHub Actions workflow `build-mcp-public-farmer-tools.yml` builds and publishes `ghcr.io/<owner>/<repo>/mcp-public-farmer-tools:latest` on push changes under this folder or on manual dispatch.

### Notes

- Use with OpenAI Responses API: include the server as an MCP tool and pass the header
	`Authorization: Bearer <MCP_API_KEY>`; server URL should be `https://your.host/mcp/`.
- For local testing behind a tunnel (e.g., ngrok), ensure the `/mcp/` path is reachable and the `Authorization` header is forwarded.
- Expand tools as the Dream Farm lessons progress (RAG, stock, knowledge graph).
- Keep code simple and documented with docstrings per repository standards.

### Testing

You can add this MCP server for example to GitHub Copilot and test it. Here is configuration:

```json
"farmer-tools": {
	"url": "https://farmer-tools.tomasdemo.org/mcp",
	"type": "http",
	"headers": {
		"Authorization": "Bearer yourkey"
	}
}
```

### Tool Notes

- `get_seasonal_tips` is a mocked, northern-hemisphere seasonal list.
- `get_weather` returns deterministic random values per (country, city) per day, with reasonable seasonal ranges:
	- temperature_c, humidity_pct, wind_kmh, precipitation_mm, timestamp
