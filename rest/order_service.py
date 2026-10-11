import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

INVENTORY_URL = "http://127.0.0.1:5001/inventory/check"
TIMEOUT_SECONDS = 2


@app.post("/orders")
def create_order():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            status="rejected",
            message="Request must be a JSON object",
        ), 400

    try:
        response = requests.post(
            INVENTORY_URL,
            json=data,
            timeout=TIMEOUT_SECONDS,
        )

    except requests.exceptions.Timeout:
        app.logger.warning("Inventory request timed out")
        return jsonify(
            status="error",
            message="Inventory request timed out",
        ), 504

    except requests.exceptions.RequestException:
        app.logger.warning("Could not contact Inventory")
        return jsonify(
            status="error",
            message="Inventory service is unreachable",
        ), 503

    try:
        inventory_result = response.json()

    except requests.exceptions.JSONDecodeError:
        return jsonify(
            status="error",
            message="Inventory returned invalid JSON",
        ), 502

    if response.status_code == 200:
        return jsonify(
            status="accepted",
            inventory=inventory_result,
        ), 200

    if response.status_code in (400, 404, 409):
        return jsonify(
            status="rejected",
            inventory=inventory_result,
        ), response.status_code

    return jsonify(
        status="error",
        message="Inventory returned an unexpected response",
    ), 502


@app.get("/health")
def health():
    return jsonify(service="order", status="ok"), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002)