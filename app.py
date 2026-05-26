import os

from flask import Flask, abort, render_template, request, url_for

from database import (
    get_categories,
    get_item_by_id,
    get_items_grouped_by_category,
    get_price_bounds,
    init_db,
    parse_price,
)
from search import hybrid_search, rebuild_search_index

# Set on Linode: APPLICATION_ROOT=/onlinestore (leave unset for local dev at /)
APPLICATION_ROOT = os.environ.get("APPLICATION_ROOT", "").strip().rstrip("/")
if APPLICATION_ROOT and not APPLICATION_ROOT.startswith("/"):
    APPLICATION_ROOT = "/" + APPLICATION_ROOT


class ScriptNameMiddleware:
    """Tell Flask it is mounted under a subpath so url_for includes the prefix."""

    def __init__(self, app, script_name: str):
        self.app = app
        self.script_name = (script_name or "").rstrip("/")

    def __call__(self, environ, start_response):
        script_name = self.script_name
        forwarded = environ.get("HTTP_X_FORWARDED_PREFIX", "")
        script_prefix = environ.get("HTTP_X_SCRIPT_PREFIX", "")
        if forwarded:
            script_name = forwarded.split(",")[0].strip().rstrip("/")
        elif script_prefix:
            script_name = script_prefix.strip().rstrip("/")

        if script_name:
            if not script_name.startswith("/"):
                script_name = "/" + script_name
            environ["SCRIPT_NAME"] = script_name
            path_info = environ.get("PATH_INFO", "") or ""
            if path_info.startswith(script_name):
                environ["PATH_INFO"] = path_info[len(script_name) :] or "/"

        return self.app(environ, start_response)


app = Flask(__name__)
init_db()

try:
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
except ImportError:
    pass

# Always install so nginx X-Script-Prefix / X-Forwarded-Prefix work without env on Linode.
app.wsgi_app = ScriptNameMiddleware(app.wsgi_app, APPLICATION_ROOT)


def resolve_image_url(image_url):
    if not image_url:
        return ""
    if image_url.startswith(("http://", "https://")):
        return image_url
    if image_url.startswith("/static/"):
        return url_for("static", filename=image_url.removeprefix("/static/"))
    if image_url.startswith("static/"):
        return url_for("static", filename=image_url.removeprefix("static/"))
    return url_for("static", filename=f"images/{image_url}")


def prepare_item(item):
    if item is None:
        return None
    prepared = dict(item)
    prepared["image_url"] = resolve_image_url(prepared["image_url"])
    prepared["price_value"] = parse_price(prepared["price"])
    return prepared


def get_active_filters():
    category = request.values.get("category", "").strip()
    if category in ("", "all"):
        category = None

    min_price = request.values.get("min_price", type=float)
    max_price = request.values.get("max_price", type=float)

    if min_price is not None and min_price < 0:
        min_price = None
    if max_price is not None and max_price < 0:
        max_price = None
    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        min_price, max_price = max_price, min_price

    return {
        "category": category,
        "min_price": min_price,
        "max_price": max_price,
    }


def get_search_query():
    return request.values.get("q", "").strip()


def filters_to_query(filters, search_query=""):
    query = {}
    if search_query:
        query["q"] = search_query
    if filters["category"]:
        query["category"] = filters["category"]
    if filters["min_price"] is not None:
        query["min_price"] = filters["min_price"]
    if filters["max_price"] is not None:
        query["max_price"] = filters["max_price"]
    return query


def apply_filters_to_items(items, filters):
    filtered = []
    for item in items:
        if filters["category"] and item["category"] != filters["category"]:
            continue
        price = parse_price(item["price"])
        if filters["min_price"] is not None and price < filters["min_price"]:
            continue
        if filters["max_price"] is not None and price > filters["max_price"]:
            continue
        filtered.append(item)
    return filtered


def filter_grouped(items_by_category, filters):
    filtered_groups = []
    for category, category_items in items_by_category:
        matching = apply_filters_to_items(category_items, filters)
        if matching:
            filtered_groups.append((category, matching))
    return filtered_groups


def apply_filters(items_by_category, filters):
    filtered = []
    for category, category_items in items_by_category:
        if filters["category"] and category != filters["category"]:
            continue

        matching_items = apply_filters_to_items(category_items, filters)
        if matching_items:
            filtered.append((category, matching_items))

    return filtered


@app.route("/", methods=["GET", "POST"])
def index():
    filters = get_active_filters()
    search_query = get_search_query()
    filter_query = filters_to_query(filters, search_query)
    added_item = None

    if request.method == "POST":
        item_id = request.form.get("item_id", type=int)
        added_item = prepare_item(get_item_by_id(item_id))

    if search_query:
        search_items = apply_filters_to_items(hybrid_search(search_query), filters)
        grouped = [("Search results", search_items)] if search_items else []
    else:
        grouped = apply_filters(get_items_grouped_by_category(), filters)

    items_by_category = [
        (category, [prepare_item(item) for item in category_items])
        for category, category_items in grouped
    ]
    item_count = sum(len(category_items) for _, category_items in items_by_category)
    price_min_bound, price_max_bound = get_price_bounds()
    filters_active = any(
        [
            filters["category"],
            filters["min_price"] is not None,
            filters["max_price"] is not None,
        ]
    )

    return render_template(
        "index.html",
        items_by_category=items_by_category,
        item_count=item_count,
        added_item=added_item,
        categories=get_categories(),
        filters=filters,
        filter_query=filter_query,
        price_min_bound=price_min_bound,
        price_max_bound=price_max_bound,
        filters_active=filters_active,
        search_query=search_query,
    )


@app.route("/item", methods=["GET", "POST"])
def item_detail():
    item_id = request.args.get("id", type=int)
    if item_id is None:
        abort(400, description="Missing or invalid item id. Use /item?id=<item_id>")

    item = prepare_item(get_item_by_id(item_id))
    if item is None:
        abort(404, description=f"Item {item_id} not found")

    added_to_cart = False
    if request.method == "POST":
        added_to_cart = True

    return render_template(
        "item.html",
        item=item,
        added_to_cart=added_to_cart,
    )


if __name__ == "__main__":
    init_db()
    try:
        rebuild_search_index()
    except Exception:
        pass
    app.run(debug=True)
