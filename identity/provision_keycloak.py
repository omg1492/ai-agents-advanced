"""Provision Keycloak realm, client, roles, and demo users (dev only).

Idempotent operations; safe to re-run. Reads configuration from environment (.env in this folder).

Vars:
- KEYCLOAK_URL (default http://localhost:8080)
- KEYCLOAK_REALM (default dreamfarm)
- KEYCLOAK_ADMIN / KEYCLOAK_ADMIN_PASSWORD (required)
- KEYCLOAK_DEMO_CLIENT_ID (default dreamfarm-frontend)
- KEYCLOAK_DEMO_REDIRECT_URIS (comma list, default http://localhost:3000/*)
- KEYCLOAK_DEMO_USERS (comma list, last becomes VIP; default user1,user2,vipuser)
- KEYCLOAK_VIP_ROLE (default vip)

Usage:
  uv run python identity/provision_keycloak.py
"""
from __future__ import annotations
import os
import sys
import json
import httpx
from typing import List
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def env(name: str, default: str | None = None, required: bool = False) -> str:
    val = os.getenv(name, default)
    if required and (val is None or val == ""):
        print(f"Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)
    return val  # type: ignore

BASE_URL = env("KEYCLOAK_URL", "http://localhost:8080")
ADMIN_USER = env("KEYCLOAK_ADMIN", required=True)
ADMIN_PASSWORD = env("KEYCLOAK_ADMIN_PASSWORD", required=True)
REALM = env("KEYCLOAK_REALM", "dreamfarm")
VIP_ROLE = env("KEYCLOAK_VIP_ROLE", "vip")
CLIENT_ID = env("KEYCLOAK_DEMO_CLIENT_ID", "dreamfarm-frontend")
REDIRECT_URIS = [u.strip() for u in env("KEYCLOAK_DEMO_REDIRECT_URIS", "http://localhost:3000/*").split(",") if u.strip()]
USER_NAMES = [u.strip() for u in env("KEYCLOAK_DEMO_USERS", "user1,user2,vipuser").split(",") if u.strip()]


def get_admin_token() -> str:
    url = f"{BASE_URL}/realms/master/protocol/openid-connect/token"
    data = {
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": ADMIN_USER,
        "password": ADMIN_PASSWORD,
    }
    r = httpx.post(url, data=data, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def realm_exists(token: str) -> bool:
    r = httpx.get(f"{BASE_URL}/admin/realms/{REALM}", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    return r.status_code == 200


def create_realm(token: str) -> None:
    payload = {"realm": REALM, "enabled": True}
    r = httpx.post(f"{BASE_URL}/admin/realms", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=payload, timeout=30)
    if r.status_code not in (201, 409):
        print(f"Realm create failed: {r.status_code} {r.text}", file=sys.stderr)
        r.raise_for_status()


def ensure_realm(token: str) -> None:
    if realm_exists(token):
        print(f"Realm '{REALM}' exists")
    else:
        print(f"Creating realm '{REALM}'")
        create_realm(token)


def get_roles(token: str) -> List[dict]:
    r = httpx.get(f"{BASE_URL}/admin/realms/{REALM}/roles", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    return r.json()


def ensure_role(token: str, role_name: str) -> dict:
    for rj in get_roles(token):
        if rj.get("name") == role_name:
            print(f"Role '{role_name}' exists")
            return rj
    payload = {"name": role_name}
    r = httpx.post(f"{BASE_URL}/admin/realms/{REALM}/roles", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=payload, timeout=30)
    if r.status_code not in (201, 409):
        print(f"Create role failed: {r.status_code} {r.text}", file=sys.stderr)
        r.raise_for_status()
    print(f"Role '{role_name}' created")
    return ensure_role(token, role_name)


def get_clients(token: str) -> List[dict]:
    r = httpx.get(f"{BASE_URL}/admin/realms/{REALM}/clients", headers={"Authorization": f"Bearer {token}"}, params={"clientId": CLIENT_ID}, timeout=30)
    r.raise_for_status()
    return r.json()


def ensure_client(token: str) -> dict:
    clients = get_clients(token)
    if clients:
        client = clients[0]
        print(f"Client '{CLIENT_ID}' exists")
    else:
        payload = {
            "clientId": CLIENT_ID,
            "publicClient": True,
            "directAccessGrantsEnabled": True,
            "standardFlowEnabled": True,
            "redirectUris": REDIRECT_URIS,
            "webOrigins": list({u.split("/*")[0] for u in REDIRECT_URIS}),
            "attributes": {"pkce.code.challenge.method": "S256"},
        }
        r = httpx.post(f"{BASE_URL}/admin/realms/{REALM}/clients", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=payload, timeout=30)
        if r.status_code not in (201, 409):
            print(f"Create client failed: {r.status_code} {r.text}", file=sys.stderr)
            r.raise_for_status()
        print(f"Client '{CLIENT_ID}' created")
        clients = get_clients(token)
        client = clients[0]
    cid = client["id"]
    update = {
        "redirectUris": REDIRECT_URIS,
        "webOrigins": list({u.split("/*")[0] for u in REDIRECT_URIS}),
        "attributes": {"pkce.code.challenge.method": "S256"},
        "publicClient": True,
        "standardFlowEnabled": True,
    }
    r2 = httpx.put(f"{BASE_URL}/admin/realms/{REALM}/clients/{cid}", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json={**client, **update}, timeout=30)
    if r2.status_code not in (204,):
        print(f"Update client failed: {r2.status_code} {r2.text}", file=sys.stderr)
        r2.raise_for_status()
    return client


def find_user(token: str, username: str) -> dict | None:
    r = httpx.get(f"{BASE_URL}/admin/realms/{REALM}/users", headers={"Authorization": f"Bearer {token}"}, params={"username": username, "exact": True}, timeout=30)
    r.raise_for_status()
    users = r.json()
    return users[0] if users else None


def create_user(token: str, username: str, password: str, vip: bool) -> dict:
    payload = {
        "username": username,
        "enabled": True,
        "credentials": [{"type": "password", "value": password, "temporary": False}],
        "attributes": {"is_vip": [str(vip).lower()]},
    }
    r = httpx.post(f"{BASE_URL}/admin/realms/{REALM}/users", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=payload, timeout=30)
    if r.status_code not in (201, 409):
        print(f"Create user {username} failed: {r.status_code} {r.text}", file=sys.stderr)
        r.raise_for_status()
    if r.status_code == 409:
        print(f"User '{username}' already exists")
    else:
        print(f"User '{username}' created")
    return find_user(token, username)  # type: ignore


def ensure_user_role(token: str, user: dict, role: dict, assign: bool) -> None:
    if not assign:
        return
    uid = user["id"]
    r = httpx.get(f"{BASE_URL}/admin/realms/{REALM}/users/{uid}/role-mappings/realm", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    if any(rj.get("name") == role["name"] for rj in r.json()):
        print(f"User '{user['username']}' already has role '{role['name']}'")
        return
    r2 = httpx.post(
        f"{BASE_URL}/admin/realms/{REALM}/users/{uid}/role-mappings/realm",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=[{"id": role["id"], "name": role["name"]}],
        timeout=30,
    )
    if r2.status_code not in (204,):
        print(f"Assign role failed: {r2.status_code} {r2.text}", file=sys.stderr)
        r2.raise_for_status()
    print(f"Assigned role '{role['name']}' to user '{user['username']}'")


def main() -> None:
    token = get_admin_token()
    ensure_realm(token)
    role = ensure_role(token, VIP_ROLE)
    client = ensure_client(token)
    for idx, username in enumerate(USER_NAMES):
        vip = idx == len(USER_NAMES) - 1
        password = f"{username}123"
        user = find_user(token, username) or create_user(token, username, password, vip)
        ensure_user_role(token, user, role, vip)
    summary = {
        "realm": REALM,
        "clientId": CLIENT_ID,
        "users": USER_NAMES,
        "vip_role": VIP_ROLE,
        "vip_user": USER_NAMES[-1] if USER_NAMES else None,
        "redirectUris": REDIRECT_URIS,
        "client_uuid": client.get("id"),
        "base_url": BASE_URL,
    }
    print("\n=== Provision Summary ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
