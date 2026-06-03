#!/bin/sh
set -e

if [ -n "${DATABASE_URL}" ]; then
  echo "Waiting for PostgreSQL..."
  python - <<'PY'
import os
import sys
import time

import psycopg

url = os.environ["DATABASE_URL"]
for attempt in range(1, 31):
    try:
        with psycopg.connect(url):
            print("PostgreSQL is ready.")
            sys.exit(0)
    except Exception as exc:
        print(f"Attempt {attempt}/30: {exc}", flush=True)
        time.sleep(1)

print("PostgreSQL did not become ready in time.", file=sys.stderr)
sys.exit(1)
PY
fi

echo "Initializing database and search index..."
python - <<'PY'
from database import init_db

init_db()

try:
    from search import rebuild_search_index

    rebuild_search_index()
except Exception as exc:
    print(f"Search index init warning: {exc}")

try:
    from search_index import semantic_search_ranked

    semantic_search_ranked("warmup", n_results=1)
    print("Search model pre-warmed.")
except Exception as exc:
    print(f"Search pre-warm warning: {exc}")
PY

exec "$@"
