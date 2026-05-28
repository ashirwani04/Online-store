"""
Upsert catalog item(s) into PostgreSQL (or SQLite if DATABASE_URL is unset).

Requires DATABASE_URL in the environment or a .env file in the project root.

Usage:
  export DATABASE_URL='postgresql://...'
  python add_item_to_postgres.py              # upsert item id 31 from items.py
  python add_item_to_postgres.py --sync-search  # also refresh ChromaDB index
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
NEW_ITEM_ID = 31


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Add item(s) to the configured database.")
    parser.add_argument(
        "--item-id",
        type=int,
        default=NEW_ITEM_ID,
        help=f"Item id to upsert from items.py (default: {NEW_ITEM_ID}).",
    )
    parser.add_argument(
        "--sync-search",
        action="store_true",
        help="Rebuild ChromaDB semantic search index after insert.",
    )
    args = parser.parse_args()

    _load_dotenv()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgres://", "postgresql://")):
        print(
            "Set DATABASE_URL in the environment or in .env, then run again.",
            file=sys.stderr,
        )
        return 1

    os.environ["DATABASE_URL"] = database_url

    from items import ITEMS

    item = next((row for row in ITEMS if row["id"] == args.item_id), None)
    if item is None:
        print(f"No item with id={args.item_id} in items.py", file=sys.stderr)
        return 1

    import database

    if not database._use_postgres():
        print("DATABASE_URL is set but database module is not using Postgres.", file=sys.stderr)
        return 1

    database.upsert_items([item])
    print(f"Upserted item id={item['id']}: {item['name']!r}")

    import psycopg

    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            "SELECT id, name, category, price FROM items WHERE id = %s",
            (args.item_id,),
        ).fetchone()

    if row:
        print(f"Verified in Postgres: id={row[0]} name={row[1]!r} category={row[2]!r} price={row[3]}")
    else:
        print("Warning: item not found after upsert.", file=sys.stderr)
        return 1

    if args.sync_search:
        from search_index import sync_inventory_index

        count = sync_inventory_index(database.get_all_items())
        print(f"Synced {count} items to ChromaDB search index.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
