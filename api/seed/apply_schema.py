"""
Apply seed/schema.sql to the PostgreSQL database in DATABASE_URL.

WARNING: schema.sql is drop-and-recreate - this wipes all existing data.

Usage (from api/):
    export DATABASE_URL="<your Postgres connection string>"
    python -m seed.apply_schema
"""

from __future__ import annotations

import os
import sys

SEED_DIR = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    import psycopg

    conn_str = os.environ.get("DATABASE_URL", "") or os.environ.get("AZURE_SQL_CONNECTION_STRING", "")
    if not conn_str:
        print("ERROR: DATABASE_URL environment variable is not set.")
        sys.exit(1)

    with open(os.path.join(SEED_DIR, "schema.sql"), encoding="utf-8") as f:
        sql = f.read()

    with psycopg.connect(conn_str, connect_timeout=30) as conn:
        # No parameters -> psycopg uses the simple query protocol, which
        # allows the multi-statement script to run in one call.
        conn.execute(sql)
    print("Schema applied.")


if __name__ == "__main__":
    main()
