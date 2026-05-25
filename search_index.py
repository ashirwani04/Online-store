"""ChromaDB vector index for semantic product search."""

from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "inventory"


def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    embedding_fn = embedding_functions.DefaultEmbeddingFunction()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )


def item_to_document(item):
    return (
        f"{item['name']}. Category: {item['category']}. "
        f"{item['lead']} {item['description']}"
    )


def sync_inventory_index(items):
    """Embed and upsert all items into ChromaDB. Returns number of indexed items."""
    collection = _get_collection()
    if not items:
        return 0

    collection.upsert(
        ids=[str(item["id"]) for item in items],
        documents=[item_to_document(item) for item in items],
        metadatas=[
            {"name": item["name"], "category": item["category"]}
            for item in items
        ],
    )
    return len(items)


def semantic_search_ranked(query, n_results=30):
    """
    Return (item_id, distance) pairs sorted by relevance.
    Lower distance means a closer semantic match in ChromaDB.
    """
    query = query.strip()
    if not query:
        return []

    collection = _get_collection()
    total = collection.count()
    if total == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, total),
        include=["distances"],
    )
    ids = results["ids"][0]
    distances = results["distances"][0]
    return [(int(item_id), float(distance)) for item_id, distance in zip(ids, distances)]


def semantic_search_ids(query, n_results=15):
    """Return item ids ranked by semantic similarity to the query."""
    return [item_id for item_id, _ in semantic_search_ranked(query, n_results=n_results)]
