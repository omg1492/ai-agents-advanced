api-stock (Read-only Stock API)
================================

FastAPI service that returns current stock info for given product IDs from PostgreSQL.

APIs
----
- GET `/health` → `{ status, timestamp }`
- POST `/stock` → body: `{ "productIds": ["<uuid>", ...] }` → `{ "items": [{ "productId", "producerId", "onStock", "updatedAt" }] }`

OpenAPI
-------
Specs are in `docs/openapi.json` and `docs/openapi.yaml`.

Run
---
1) Copy `.env.template` to `.env` and set PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD.
2) Install deps and start the service:

```pwsh
uv sync
uv run main.py
```

Optional env:
- `PORT` (default 8011)
- `RELOAD` (default true)

Test
----
Integration tests hit a real PostgreSQL and will skip if it’s unavailable:

```pwsh
uv run pytest -m integration -q
```
