"""
Import product inventory from a CSV file into store.db.

CSV must include a header row with these columns:
  id, name, category, price, image_url, image_alt, lead, description

Usage:
  python import_items.py new_items.csv
  python import_items.py new_items.csv --dry-run
  python import_items.py items_export.csv --replace-all
"""

import argparse
import csv
import sys
from pathlib import Path

from database import ITEM_COLUMNS, DATABASE_PATH, get_connection, upsert_items
from items import ITEMS

REQUIRED_COLUMNS = set(ITEM_COLUMNS)


def load_items_from_csv(csv_path):
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")

    items = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV file is empty or missing a header row.")

        headers = {name.strip() for name in reader.fieldnames}
        missing = REQUIRED_COLUMNS - headers
        if missing:
            raise ValueError(
                f"CSV is missing required columns: {', '.join(sorted(missing))}"
            )

        for line_number, row in enumerate(reader, start=2):
            if not any(value and str(value).strip() for value in row.values()):
                continue

            try:
                item = {
                    "id": int(row["id"]),
                    "name": row["name"].strip(),
                    "category": row["category"].strip(),
                    "price": row["price"].strip(),
                    "image_url": row["image_url"].strip(),
                    "image_alt": row["image_alt"].strip(),
                    "lead": row["lead"].strip(),
                    "description": row["description"].strip(),
                }
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid data on line {line_number}: {exc}") from exc

            if not all(
                item[field]
                for field in (
                    "name",
                    "category",
                    "price",
                    "image_url",
                    "image_alt",
                    "lead",
                    "description",
                )
            ):
                raise ValueError(f"Line {line_number} has empty required fields.")

            items.append(item)

    if not items:
        raise ValueError("No items found in CSV.")

    ids = [item["id"] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("CSV contains duplicate item ids.")

    return items


def clear_inventory():
    with get_connection() as conn:
        conn.execute("DELETE FROM items")
        conn.commit()


def main():
    parser = argparse.ArgumentParser(
        description="Import items from a CSV file into the SQLite inventory."
    )
    parser.add_argument(
        "csv_file",
        nargs="?",
        help="Path to CSV file (required unless --seed is used)",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Load the built-in inventory from items.py instead of a CSV file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the CSV and print items without writing to the database",
    )
    parser.add_argument(
        "--replace-all",
        action="store_true",
        help="Delete all existing items before importing (use with care)",
    )
    args = parser.parse_args()

    if args.seed:
        items = ITEMS
        source = "items.py"
    elif args.csv_file:
        items = load_items_from_csv(args.csv_file)
        source = args.csv_file
    else:
        parser.error("Provide a csv_file path or use --seed to load items.py")

    print(f"Source: {source}")
    print(f"Items to import: {len(items)}")
    print(f"Database: {DATABASE_PATH}")

    if args.dry_run:
        for item in items:
            print(f"  [{item['id']}] {item['name']} ({item['price']})")
        print("Dry run complete. No changes were made.")
        return 0

    if args.replace_all:
        clear_inventory()
        print("Cleared existing inventory.")

    count = upsert_items(items)
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    try:
        from search import rebuild_search_index

        indexed = rebuild_search_index()
        print(f"Search index updated ({indexed} items in ChromaDB).")
    except Exception as error:
        print(f"Warning: could not update search index: {error}")

    print(f"Imported/updated {count} item(s).")
    print(f"Total items in database: {total}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
