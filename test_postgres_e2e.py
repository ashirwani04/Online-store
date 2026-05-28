"""
End-to-end check: app uses PostgreSQL (not SQLite) after store.db is removed.

Requires DATABASE_URL (env var or .env file in project root).

Usage:
  export DATABASE_URL='postgresql://...'
  python test_postgres_e2e.py

  python test_postgres_e2e.py --keep   # leave test row in DO for console verification
  python test_postgres_e2e.py --cleanup  # delete test row after checks (default)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
STORE_DB = PROJECT_ROOT / "store.db"
TEST_ITEM_ID = 99999

TEST_ITEM = {
    "id": TEST_ITEM_ID,
    "name": "Postgres Cloud Test Item",
    "category": "Accessories",
    "price": "$1.00",
    "image_url": "backpack.png",
    "image_alt": "E2E test item for PostgreSQL verification",
    "lead": "Temporary row inserted by test_postgres_e2e.py.",
    "description": (
        "If you see this row in DigitalOcean Postgres (items table), "
        "the store is using DATABASE_URL correctly."
    ),
}


def _load_dotenv() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _require_database_url(explicit: str) -> str:
    url = (explicit or os.environ.get("DATABASE_URL", "")).strip()
    if not url.startswith(("postgres://", "postgresql://")):
        raise SystemExit(
            "Missing DATABASE_URL. Set it in the environment or in a .env file:\n"
            "  DATABASE_URL=postgresql://user:pass@host:25060/dbname?sslmode=require"
        )
    os.environ["DATABASE_URL"] = url
    return url


def _delete_sqlite() -> None:
    if STORE_DB.is_file():
        STORE_DB.unlink()
        print(f"Deleted {STORE_DB.name}")
    else:
        print(f"No {STORE_DB.name} to delete")


def _assert_sqlite_gone() -> None:
    if STORE_DB.is_file():
        raise SystemExit(f"FAIL: {STORE_DB.name} was recreated — app may be using SQLite.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Postgres-only operation.")
    parser.add_argument(
        "--database-url",
        default="",
        help="Postgres URL (overrides DATABASE_URL / .env).",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the test row in Postgres for DigitalOcean console inspection.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove the test row after checks (default when --keep is not set).",
    )
    args = parser.parse_args()

    _load_dotenv()
    database_url = _require_database_url(args.database_url)
    cleanup = args.cleanup or not args.keep

    _delete_sqlite()

    # Import after DATABASE_URL is set (database.py reads it at import time).
    import psycopg

    import database

    if not database._use_postgres():
        raise SystemExit("FAIL: database module is not using Postgres.")

    print("OK: database module is configured for Postgres")

    with database.get_connection() as conn:
        database.ensure_schema(conn)
    database.upsert_items([TEST_ITEM])
    print(f"OK: inserted test item id={TEST_ITEM_ID}")

    fetched = database.get_item_by_id(TEST_ITEM_ID)
    if not fetched or fetched["name"] != TEST_ITEM["name"]:
        raise SystemExit("FAIL: get_item_by_id did not return the test item")

    print("OK: get_item_by_id returned the test item")

    _assert_sqlite_gone()

    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            "SELECT id, name, category FROM items WHERE id = %s",
            (TEST_ITEM_ID,),
        ).fetchone()
        count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    if not row:
        raise SystemExit("FAIL: test item not found via direct Postgres query")

    print(f"OK: direct Postgres query found id={row[0]} name={row[1]!r}")
    print(f"OK: items table row count = {count}")

    # Flask: import app after DB is configured; init_db upserts catalog from items.py.
    import app as app_module

    client = app_module.app.test_client()
    response = client.get("/")
    if response.status_code != 200:
        raise SystemExit(f"FAIL: GET / returned {response.status_code}")

    body = response.get_data(as_text=True)
    if TEST_ITEM["name"] not in body:
        raise SystemExit("FAIL: test item name not found on homepage HTML")

    print("OK: homepage includes the test item")

    _assert_sqlite_gone()

    if cleanup:
        with psycopg.connect(database_url) as conn:
            conn.execute("DELETE FROM items WHERE id = %s", (TEST_ITEM_ID,))
            conn.commit()
        print(f"OK: removed test item id={TEST_ITEM_ID} from Postgres")
    else:
        print()
        print("Test row kept in DigitalOcean. In the SQL console, run:")
        print(f"  SELECT * FROM items WHERE id = {TEST_ITEM_ID};")
        print("Delete it when done:")
        print(f"  DELETE FROM items WHERE id = {TEST_ITEM_ID};")

    print()
    print("All checks passed — store works with Postgres and without store.db.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
