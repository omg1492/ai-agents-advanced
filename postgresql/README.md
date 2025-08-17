This directory contains a Dockerfile to build a PostgreSQL 17 image for local/test deployments with added binaries for required extensions:

- pgvector (from the base image)
- Apache AGE (compiled from source during build)

Image is built from `pgvector/pgvector:pg17` and adds Apache AGE, so you can enable both vector search and openCypher graph queries in the same Postgres instance.

How to use:

1) Build locally (optional)

```pwsh
docker build --build-arg AGE_REF=v1.5.0 -t ghcr.io/<owner>/<repo>/postgres:dev .\postgresql
```

2) Enable extensions in your DB (once, as superuser)

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
-- optional: SELECT create_graph('dreamfarm');
```

3) Docker Compose integration

In `deploy/local/docker-compose.yml` set the Postgres image to your published GHCR image, for example:

```yaml
services:
	postgres:
		image: ghcr.io/<owner>/<repo>/postgres:latest
		# ...existing config...
```

GitHub Actions

There is a workflow at `.github/workflows/build-postgres-image.yml` that you can trigger manually (workflow_dispatch). It builds the image and publishes it to GHCR under `ghcr.io/<owner>/<repo>/postgres:<tag>`.

Inputs:
- `image_tag` (default: `latest`)
- `age_ref` (default: `master`) — use a stable AGE tag for reproducible builds (e.g., `v1.5.0`).

Notes

- The build installs temporary packages (build-essential, postgresql-server-dev-17) and removes them after installing AGE to keep the final image small.
- AGE installs to `/usr/lib/postgresql/17/lib/age.so` and `/usr/share/postgresql/17/extension/age*.sql`.