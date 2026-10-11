import os
import time

DELAY_SECONDS = float(os.getenv("INVENTORY_DELAY_SECONDS", "0"))

from flask import Flask, request, jsonify

app = Flask(__name__)

STOCK = {
    "notebook": 10,
    "pen": 20,
}


@app.post("/inventory/check")
def check_inventory():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(message="Request must be a JSON object"), 400

    item_id = data.get("item_id")
    quantity = data.get("quantity")

    if not isinstance(item_id, str) or not item_id.strip():
        return jsonify(message="item_id must be a nonempty string"), 400

    if type(quantity) is not int or quantity <= 0:
        return jsonify(message="quantity must be a positive integer"), 400

    if DELAY_SECONDS > 0:
        app.logger.warning(
            "Delaying inventory response by %s seconds",
            DELAY_SECONDS,
        )
        time.sleep(DELAY_SECONDS)

    if item_id not in STOCK:
        return jsonify(
            available=False,
            message="Item not found",
        ), 404

    available_quantity = STOCK[item_id]

    if quantity > available_quantity:
        return jsonify(
            available=False,
            available_quantity=available_quantity,
            message="Insufficient stock",
        ), 409

    return jsonify(
        item_id=item_id,
        quantity=quantity,
        available=True,
        available_quantity=available_quantity,
        message="Inventory available",
    ), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)