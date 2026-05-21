from flask import Flask, abort, render_template, request, url_for

from database import get_all_items, get_item_by_id, init_db

app = Flask(__name__)
init_db()


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
    return prepared


@app.route("/", methods=["GET", "POST"])
def index():
    added_item = None
    if request.method == "POST":
        item_id = request.form.get("item_id", type=int)
        added_item = prepare_item(get_item_by_id(item_id))

    items = [prepare_item(item) for item in get_all_items()]
    return render_template("index.html", items=items, added_item=added_item)


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
    app.run(debug=True)
