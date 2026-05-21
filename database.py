import sqlite3
from pathlib import Path

from items import ITEMS

DATABASE_PATH = Path(__file__).parent / "store.db"


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "price": row["price"],
        "image_url": row["image_url"],
        "image_alt": row["image_alt"],
        "lead": row["lead"],
        "description": row["description"],
    }


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                price TEXT NOT NULL,
                image_url TEXT NOT NULL,
                image_alt TEXT NOT NULL,
                lead TEXT NOT NULL,
                description TEXT NOT NULL
            )
            """
        )
        for item in ITEMS:
            conn.execute(
                """
                INSERT INTO items (id, name, price, image_url, image_alt, lead, description)
                VALUES (:id, :name, :price, :image_url, :image_alt, :lead, :description)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    price = excluded.price,
                    image_url = excluded.image_url,
                    image_alt = excluded.image_alt,
                    lead = excluded.lead,
                    description = excluded.description
                """,
                item,
            )
        conn.commit()


def get_all_items():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, price, image_url, image_alt, lead, description FROM items ORDER BY id"
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_item_by_id(item_id):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, name, price, image_url, image_alt, lead, description
            FROM items WHERE id = ?
            """,
            (item_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None
