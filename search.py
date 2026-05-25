"""Hybrid keyword + semantic search over the inventory."""

from database import (
    get_all_items,
    get_item_by_id,
    group_items_by_category,
    keyword_search_items,
)
from search_index import semantic_search_ranked, sync_inventory_index

# Lower score = better match. Keyword hits get a small boost (distance reduction).
KEYWORD_BOOST = 0.2


def rebuild_search_index():
    items = get_all_items()
    return sync_inventory_index(items)


def hybrid_search(query, semantic_limit=30):
    """
    Combine keyword and semantic matches, then sort by relevance.
    ChromaDB distance drives ordering; keyword matches receive a ranking boost.
    """
    query = query.strip()
    if not query:
        return []

    keyword_items = keyword_search_items(query)
    keyword_ids = {item["id"] for item in keyword_items}

    try:
        ranked_semantic = semantic_search_ranked(query, n_results=semantic_limit)
    except Exception:
        ranked_semantic = []

    semantic_distance = {item_id: distance for item_id, distance in ranked_semantic}
    semantic_ids = set(semantic_distance)

    items_by_id = {item["id"]: item for item in get_all_items()}
    candidate_ids = semantic_ids | keyword_ids
    if not candidate_ids:
        return []

    max_semantic = max(semantic_distance.values()) if semantic_distance else 1.0
    keyword_only_base = max_semantic + 0.5

    scored = []
    for item_id in candidate_ids:
        item = items_by_id.get(item_id) or get_item_by_id(item_id)
        if not item:
            continue

        if item_id in semantic_distance:
            score = semantic_distance[item_id]
        else:
            score = keyword_only_base

        if item_id in keyword_ids:
            score -= KEYWORD_BOOST

        enriched = dict(item)
        enriched["relevance_score"] = score
        if item_id in keyword_ids and item_id in semantic_ids:
            enriched["match_type"] = "keyword + semantic"
        elif item_id in keyword_ids:
            enriched["match_type"] = "keyword"
        else:
            enriched["match_type"] = "semantic"
        scored.append((score, enriched))

    scored.sort(key=lambda pair: pair[0])
    return [item for _, item in scored]


def hybrid_search_grouped(query, semantic_limit=30):
    """Group search results by category while preserving relevance order within each group."""
    items = hybrid_search(query, semantic_limit=semantic_limit)
    return group_items_by_category(items)
