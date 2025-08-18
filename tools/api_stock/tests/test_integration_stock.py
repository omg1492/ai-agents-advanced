"""
Integration tests for api_stock using a real PostgreSQL database.

These tests require a running PostgreSQL instance with the `stock` table.
They will skip gracefully if connection or table is missing.
"""
from __future__ import annotations

import os
import uuid

import psycopg2
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from main import app


pytestmark = pytest.mark.integration


def _connect():
    load_dotenv()
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", 5432)),
        database=os.getenv("PGDATABASE", "aidb"),
        user=os.getenv("PGUSER", "admin"),
        password=os.getenv("PGPASSWORD", "Admin12345678"),
    )


def ensure_stock_table_exists():
    try:
        conn = _connect()
    except Exception:
        pytest.skip("PostgreSQL is not available; skipping integration tests")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS stock (
                    producer_id uuid NOT NULL,
                    product_id uuid NOT NULL,
                    on_stock integer NOT NULL DEFAULT 0,
                    updated_at timestamptz DEFAULT now(),
                    PRIMARY KEY (producer_id, product_id)
                );
                """
            )
        conn.commit()
    finally:
        conn.close()


def test_health():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"


def test_stock_lookup_happy_path():
    ensure_stock_table_exists()

    pid = uuid.uuid4()
    prod = uuid.uuid4()

    # Insert one row
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM stock WHERE product_id = %s",
                (str(pid),),
            )
            cur.execute(
                "INSERT INTO stock (producer_id, product_id, on_stock) VALUES (%s, %s, %s)",
                (str(prod), str(pid), 7),
            )
        conn.commit()
    finally:
        conn.close()

    with TestClient(app) as client:
        r = client.post("/stock", json={"productIds": [str(pid)]})
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["productId"] == str(pid)
    assert item["producerId"] == str(prod)
    assert item["onStock"] == 7


def test_stock_empty_array_rejected():
    with TestClient(app) as client:
        r = client.post("/stock", json={"productIds": []})
    assert r.status_code == 422  # validation error from pydantic


def test_stock_too_many_ids():
    with TestClient(app) as client:
        ids = [str(uuid.uuid4()) for _ in range(501)]
        r = client.post("/stock", json={"productIds": ids})
    assert r.status_code == 400
    assert "Too many productIds" in r.text
