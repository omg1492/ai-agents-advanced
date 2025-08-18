"""
api_stock FastAPI application exposing read-only stock lookup.

Single-file variant for simplicity.

Environment variables (unified across repo):
- PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
- LOG_LEVEL (optional, default INFO)

Run locally:
  uv run uvicorn main:app --reload --port 8011
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
from uuid import UUID

import psycopg2
import psycopg2.pool
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field


# -------------------------
# Models
# -------------------------


class StockRequest(BaseModel):
    """Request payload containing productId list to fetch current stock for."""

    productIds: List[UUID] = Field(..., min_length=1, description="Array of product UUIDs")


class StockItem(BaseModel):
    """Single product stock item in the response."""

    productId: str
    producerId: Optional[str] = None
    onStock: int
    updatedAt: Optional[str] = None


class StockResponse(BaseModel):
    """Response containing stock items for requested productIds."""

    items: List[StockItem]


class HealthResponse(BaseModel):
    """Simple health check response."""

    status: str
    timestamp: str


# -------------------------
# Config & DB
# -------------------------


class Config:
    """Configuration reader for PostgreSQL and logging."""

    def __init__(self) -> None:
        load_dotenv()
        self.pg_host = os.getenv("PGHOST", "localhost")
        self.pg_port = int(os.getenv("PGPORT", "5432"))
        self.pg_db = os.getenv("PGDATABASE", "aidb")
        self.pg_user = os.getenv("PGUSER", "admin")
        self.pg_password = os.getenv("PGPASSWORD", "Admin12345678")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    def to_dsn(self) -> Dict[str, object]:
        return {
            "host": self.pg_host,
            "port": self.pg_port,
            "dbname": self.pg_db,
            "user": self.pg_user,
            "password": self.pg_password,
        }


class DBPool:
    """Simple psycopg2 connection pool wrapper."""

    def __init__(self, minconn: int, maxconn: int, dsn_kwargs: Dict[str, object]):
        self._pool = psycopg2.pool.SimpleConnectionPool(
            minconn, maxconn, cursor_factory=RealDictCursor, **dsn_kwargs
        )

    def get(self):  # noqa: ANN001
        return self._pool.getconn()

    def put(self, conn) -> None:  # noqa: ANN001
        self._pool.putconn(conn)

    def closeall(self) -> None:
        self._pool.closeall()


config = Config()
logging.basicConfig(level=getattr(logging, config.log_level, logging.INFO))
logger = logging.getLogger("api_stock")
pool: psycopg2.pool.SimpleConnectionPool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Manage DB connection pool lifecycle.

    If PostgreSQL is unavailable at startup, keep `pool` as None so health endpoint still works.
    """

    global pool  # noqa: PLW0603
    pool = None
    try:
        try:
            pool = DBPool(minconn=1, maxconn=5, dsn_kwargs=config.to_dsn())
            logger.info("DB pool initialized")
        except Exception as e:  # noqa: BLE001
            logger.warning("DB pool not initialized at startup: %s", e)
        yield
    finally:
        try:
            if pool:
                pool.closeall()
                logger.info("DB pool closed")
        except Exception:  # noqa: BLE001
            pass


app = FastAPI(title="api-stock", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    import datetime as dt

    return HealthResponse(status="healthy", timestamp=dt.datetime.now(dt.UTC).isoformat())


@app.post("/stock", response_model=StockResponse)
def get_stock(req: StockRequest) -> StockResponse:
    """Return current stock for provided productIds.

    The `stock` table schema follows docs: composite PK (producer_id, product_id), on_stock int, updated_at timestamptz.
    """

    if len(req.productIds) > 500:
        raise HTTPException(status_code=400, detail="Too many productIds (max 500)")

    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    conn = None
    try:
        conn = pool.get()
        with conn.cursor() as cur:
            ids = [str(x) for x in req.productIds]
            cur.execute(
                """
                SELECT product_id, producer_id, on_stock, updated_at
                FROM stock
                WHERE product_id = ANY(%s::uuid[])
                """,
                (ids,),
            )
            rows = cur.fetchall()

        items = [
            StockItem(
                productId=row["product_id"],
                producerId=row.get("producer_id"),
                onStock=int(row["on_stock"]),
                updatedAt=(row["updated_at"].isoformat() if row.get("updated_at") else None),
            )
            for row in rows
        ]
        return StockResponse(items=items)
    except psycopg2.Error as e:  # Database error
        logger.exception("Database error during /stock")
        raise HTTPException(status_code=500, detail=f"Database error: {e.pgerror or str(e)}")
    finally:
        if conn is not None:
            pool.put(conn)


def main() -> None:
    """Run the FastAPI app with uvicorn when executed as a script.

    Honors optional env vars: PORT (default 8011), RELOAD (true/false).
    """

    import uvicorn

    port = int(os.getenv("PORT", "8011"))
    reload = os.getenv("RELOAD", "true").lower() == "true"
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=reload)


if __name__ == "__main__":
    main()
