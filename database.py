import os
import sqlite3
from pathlib import Path

from items import ITEMS

DATABASE_PATH = Path(__file__).parent / "store.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

CATEGORY_ORDER = [
    "Electronics",
    "Apparel",
    "Kitchen & Drinkware",
    "Fitness",
    "Home & Office",
    "Accessories",
]

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

UPSERT_SQL = """
    INSERT INTO items (id, name, category, price, image_url, image_alt, lead, description)
    VALUES (:id, :name, :category, :price, :image_url, :image_alt, :lead, :description)
    ON CONFLICT(id) DO UPDATE SET
        name = excluded.name,
        category = excluded.category,
        price = excluded.price,
        image_url = excluded.image_url,
        image_alt = excluded.image_alt,
        lead = excluded.lead,
        description = excluded.description
"""

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


def _use_postgres() -> bool:
    return DATABASE_URL.startswith(("postgres://", "postgresql://"))


def get_connection():
    if _use_postgres():
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(DATABASE_URL, row_factory=dict_row)

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "price": row["price"],
        "image_url": row["image_url"],
        "image_alt": row["image_alt"],
        "lead": row["lead"],
        "description": row["description"],
    }


def ensure_schema(conn):
    if _use_postgres():
        conn.execute(
            """
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
        )
        return

    conn.execute(
        """
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
    )
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()
    }
    if "category" not in columns:
        conn.execute(
            "ALTER TABLE items ADD COLUMN category TEXT NOT NULL DEFAULT 'Uncategorized'"
        )


def upsert_items(items):
    """Insert or update items in the database. Returns number of rows processed."""
    with get_connection() as conn:
        ensure_schema(conn)
        for item in items:
            if _use_postgres():
                conn.execute(UPSERT_POSTGRES_SQL, item)
            else:
                conn.execute(UPSERT_SQL, item)
        conn.commit()
    return len(items)


def init_db():
    upsert_items(ITEMS)
    try:
        from search_index import sync_inventory_index

        sync_inventory_index(get_all_items())
    except Exception:
        pass


def get_all_items():
    with get_connection() as conn:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT id, name, category, price, image_url, image_alt, lead, description
            FROM items
            ORDER BY category, id
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_categories():
    return list(CATEGORY_ORDER)


def get_price_bounds():
    """Return (min_price, max_price) as floats from all items."""
    prices = [parse_price(item["price"]) for item in get_all_items()]
    if not prices:
        return 0.0, 0.0
    return min(prices), max(prices)


def parse_price(price):
    """Convert a display price like '$89.00' to a float."""
    return float(str(price).replace("$", "").replace(",", "").strip())


def keyword_search_items(query):
    """Find items whose text fields contain the query (case-insensitive)."""
    needle = query.lower().strip()
    if not needle:
        return []

    matches = []
    for item in get_all_items():
        searchable = " ".join(
            [
                item["name"],
                item["category"],
                item["lead"],
                item["description"],
                item["image_alt"],
            ]
        ).lower()
        if needle in searchable:
            matches.append(item)
    return matches


def group_items_by_category(items):
    grouped = {}
    for item in items:
        category = item["category"] or "Uncategorized"
        grouped.setdefault(category, []).append(item)

    ordered = []
    for category in CATEGORY_ORDER:
        if category in grouped:
            ordered.append((category, grouped.pop(category)))

    for category in sorted(grouped.keys()):
        ordered.append((category, grouped[category]))

    return ordered


def get_items_grouped_by_category():
    return group_items_by_category(get_all_items())


def get_item_by_id(item_id):
    with get_connection() as conn:
        ensure_schema(conn)
        if _use_postgres():
            row = conn.execute(
                """
                SELECT id, name, category, price, image_url, image_alt, lead, description
                FROM items WHERE id = %s
                """,
                (item_id,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT id, name, category, price, image_url, image_alt, lead, description
                FROM items WHERE id = ?
                """,
                (item_id,),
            ).fetchone()
    return _row_to_dict(row) if row else None
