# Identity Provisioning

Utilities to bootstrap local Keycloak for development.

## Setup
1. Copy `.env.template` to `.env` and adjust credentials if needed.
2. Ensure Keycloak container is running (see `deploy/local/docker-compose.yml`).

## Provision
```powershell
uv run python identity/provision_keycloak.py
```
Creates / updates:
- Realm (KEYCLOAK_REALM)
- VIP role (KEYCLOAK_VIP_ROLE)
- Public frontend client (PKCE) with redirect URIs
- Demo users (last user marked VIP: role + is_vip attribute)
- Client registration for dreamfarm-frontend

Re-run safely: operations are idempotent. The script auto-loads `identity/.env` using python-dotenv; you can still override vars via the shell environment.

## Environment Variables
Defined in `.env.template` with sensible local defaults. Runtime reads from process env.

## Notes
- Passwords are simple `<username>123` for demo only.
- Do not use this script for production; build Terraform or operator-based provisioning instead.
