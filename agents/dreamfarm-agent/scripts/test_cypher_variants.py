"""Standalone diagnostic script to probe Apache AGE cypher() invocation variants.

Usage (from agents/dreamfarm-agent/):
  uv run scripts/test_cypher_variants.py --graph dreamfarm

It attempts several call signatures and prints success/failure plus
any error messages to help pinpoint why the service BFS/DFS calls fail.
"""
from __future__ import annotations
import argparse
import os
import sys
import psycopg2

VARIANTS = [
    ("v1_2arg_text", "SELECT val FROM cypher(%(g)s, $$RETURN 1 AS val$$) AS (val agtype)"),
    ("v2_2arg_name", "SELECT val FROM cypher((%(g)s)::name, $$RETURN 1 AS val$$) AS (val agtype)"),
    ("v3_3arg_text", "SELECT val FROM cypher(%(g)s, $$RETURN 1 AS val$$, $$) AS (val agtype)"),
    ("v4_3arg_name", "SELECT val FROM cypher((%(g)s)::name, $$RETURN 1 AS val$$, $$) AS (val agtype)"),
    # Explicit cstring cast variants:
    ("v5_2arg_text_cstring", "SELECT val FROM cypher(%(g)s, ($$RETURN 1 AS val$$)::cstring) AS (val agtype)"),
    ("v6_2arg_name_cstring", "SELECT val FROM cypher((%(g)s)::name, ($$RETURN 1 AS val$$)::cstring) AS (val agtype)"),
]


def load_age(cur):
    try:
        cur.execute("LOAD 'age';")
    except Exception as e:  # noqa: PIE786
        print(f"[WARN] LOAD 'age' failed (maybe already loaded): {e}")
    try:
        cur.execute("SET search_path = ag_catalog, public;")
    except Exception as e:  # noqa: PIE786
        print(f"[WARN] SET search_path failed: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("PGHOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5432")))
    parser.add_argument("--db", default=os.getenv("PGDATABASE", "postgres"))
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    parser.add_argument("--password", default=os.getenv("PGPASSWORD", ""))
    parser.add_argument("--graph", default=os.getenv("AGE_GRAPH_NAME", "dreamfarm"))
    args = parser.parse_args()

    dsn = f"host={args.host} port={args.port} dbname={args.db} user={args.user} password={args.password}"
    print(f"[INFO] Connecting: {dsn}")
    try:
        conn = psycopg2.connect(dsn)
    except Exception as e:  # noqa: PIE786
        print(f"[FATAL] Connection failed: {e}")
        return 1
    conn.autocommit = True
    cur = conn.cursor()
    load_age(cur)
    print("[INFO] Probing cypher variants (graph='" + args.graph + "'):")
    for name, sql in VARIANTS:
        fmt_sql = sql.replace("%(g)s", "%s")
        try:
            cur.execute(fmt_sql, (args.graph,))
            row = cur.fetchone()
            print(f"  [OK] {name}: row={row}")
        except Exception as e:  # noqa: PIE786
            print(f"  [FAIL] {name}: {e}")
    print("\n[HINT] If only *name* variants succeed (v2/v4/v6), keep (::name). If only 3‑arg succeeds, include empty $$.")
    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
