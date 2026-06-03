def post_worker_init(worker):
    try:
        from search_index import semantic_search_ranked

        semantic_search_ranked("warmup", n_results=1)
    except Exception:
        pass
