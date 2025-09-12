"""Ad-hoc diagnostic: probe Apache AGE cypher() invocation variants.

Rules (see general instructions):
- Prefixed with adhoc_test_ (temporary troubleshooting aid).
- Loads .env so local PG* and AGE_GRAPH_NAME vars are honored.
- Prints a concise success/failure matrix for each tested variant.

Run from repo root or service dir:
  uv run agents/dreamfarm-agent/src/adhoc_test_cypher_variants.py --graph dreamfarm

Remove once root cause is solved and documented in CommonErrors.md.
"""
from __future__ import annotations
import argparse
import os
import sys
import psycopg2  # type: ignore
from dotenv import load_dotenv

VARIANTS: list[tuple[str, str]] = [
    ("v1_2arg_text", "SELECT val FROM cypher(%(g)s, $$RETURN 1 AS val$$) AS (val agtype)"),
    ("v2_2arg_name", "SELECT val FROM cypher((%(g)s)::name, $$RETURN 1 AS val$$) AS (val agtype)"),
    ("v3_3arg_text", "SELECT val FROM cypher(%(g)s, $$RETURN 1 AS val$$, $$) AS (val agtype)"),
    ("v4_3arg_name", "SELECT val FROM cypher((%(g)s)::name, $$RETURN 1 AS val$$, $$) AS (val agtype)"),
    ("v5_2arg_text_cstring", "SELECT val FROM cypher(%(g)s, ($$RETURN 1 AS val$$)::cstring) AS (val agtype)"),
    ("v6_2arg_name_cstring", "SELECT val FROM cypher((%(g)s)::name, ($$RETURN 1 AS val$$)::cstring) AS (val agtype)"),
]


def _load_age(cur) -> None:  # pragma: no cover
    try:
        cur.execute("LOAD 'age';")
    except Exception as e:  # noqa: PIE786
        print(f"[WARN] LOAD 'age' failed: {e}")
    try:
        cur.execute("SET search_path = ag_catalog, public;")
    except Exception as e:  # noqa: PIE786
        print(f"[WARN] SET search_path failed: {e}")


def main() -> int:  # pragma: no cover
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", default=os.getenv("AGE_GRAPH_NAME", "dreamfarm"))
    parser.add_argument("--host", default=os.getenv("PGHOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5432")))
    parser.add_argument("--db", default=os.getenv("PGDATABASE", "postgres"))
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    parser.add_argument("--password", default=os.getenv("PGPASSWORD", ""))
    args = parser.parse_args()

    dsn = f"host={args.host} port={args.port} dbname={args.db} user={args.user} password={args.password}"
    print(f"[INFO] DSN: {dsn}")
    try:
        conn = psycopg2.connect(dsn)
    except Exception as e:  # noqa: PIE786
        print(f"[FATAL] Connection failed: {e}")
        return 1
    conn.autocommit = True
    cur = conn.cursor()
    _load_age(cur)
    print(f"[INFO] Probing cypher variants against graph '{args.graph}'\n")
    successes: list[str] = []
    for name, sql in VARIANTS:
        try:
            cur.execute(sql, {"g": args.graph})
            row = cur.fetchone()
            print(f"  [OK]   {name:22s} -> {row}")
            successes.append(name)
        except Exception as e:  # noqa: PIE786
            print(f"  [FAIL] {name:22s} -> {e}")
    print("\n[SUMMARY] Successful variants: " + (", ".join(successes) if successes else "NONE"))
    if not successes:
        print("[NEXT] Verify: CREATE EXTENSION age;  Graph exists; search_path includes ag_catalog; psql manual call.")
    else:
        print("[HINT] Use the *first stable* variant above inside GraphSearchService._build_cypher_sql.")
    cur.close()
    conn.close()
    return 0 if successes else 2


if __name__ == "__main__":
    sys.exit(main())
