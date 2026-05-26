import argparse
import os
import sqlite3
from pathlib import Path


ITEM_COLUMNS = (
    "id",
    "name",
    "category",
    "price",
    "image_url",
    "image_alt",
    "lead",
    "description",
)


UPSERT_POSTGRES_SQL = """
INSERT INTO items (id, name, category, price, image_url, image_alt, lead, description)
VALUES (%(id)s, %(name)s, %(category)s, %(price)s, %(image_url)s, %(image_alt)s, %(lead)s, %(description)s)
ON CONFLICT(id) DO UPDATE SET
    name = excluded.name,
    category = excluded.category,
    price = excluded.price,
    image_url = excluded.image_url,
    image_alt = excluded.image_alt,
    lead = excluded.lead,
    description = excluded.description
"""


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Uncategorized',
    price TEXT NOT NULL,
    image_url TEXT NOT NULL,
    image_alt TEXT NOT NULL,
    lead TEXT NOT NULL,
    description TEXT NOT NULL
)
"""


def _load_sqlite_rows(sqlite_path: Path) -> list[dict]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, name, category, price, image_url, image_alt, lead, description
            FROM items
            ORDER BY id
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy items from SQLite store.db into PostgreSQL (DigitalOcean) using upserts."
    )
    parser.add_argument(
        "--sqlite",
        default="store.db",
        help="Path to SQLite database file (default: store.db)",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "").strip(),
        help="PostgreSQL connection URL (or set DATABASE_URL env var).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print how many rows would be migrated.",
    )
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.is_file():
        raise FileNotFoundError(f"SQLite DB not found: {sqlite_path}")

    rows = _load_sqlite_rows(sqlite_path)
    if args.dry_run:
        print(f"Would migrate {len(rows)} rows from {sqlite_path}")
        return 0

    database_url = args.database_url
    if not database_url.startswith(("postgres://", "postgresql://")):
        raise ValueError(
            "Missing/invalid Postgres DATABASE_URL. Expected postgres:// or postgresql://"
        )

    import psycopg

    with psycopg.connect(database_url) as pg:
        pg.execute(CREATE_TABLE_SQL)
        for row in rows:
            pg.execute(UPSERT_POSTGRES_SQL, row)
        pg.commit()

    print(f"Migrated {len(rows)} rows into Postgres.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

