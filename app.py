from flask import Flask, render_template, request

from items import ITEMS, ITEMS_BY_ID

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    added_item = None
    if request.method == "POST":
        item_id = request.form.get("item_id", type=int)
        added_item = ITEMS_BY_ID.get(item_id)
    return render_template("index.html", items=ITEMS, added_item=added_item)


if __name__ == "__main__":
    app.run(debug=True)
