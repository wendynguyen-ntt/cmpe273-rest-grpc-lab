import logging

import grpc
from flask import Flask, request, jsonify

import inventory_pb2
import inventory_pb2_grpc

app = Flask(__name__)

DEADLINE_SECONDS = 2

channel = grpc.insecure_channel("127.0.0.1:50051")
stub = inventory_pb2_grpc.InventoryServiceStub(channel)

HTTP_STATUS_BY_GRPC = {
    grpc.StatusCode.INVALID_ARGUMENT: 400,
    grpc.StatusCode.NOT_FOUND: 404,
    grpc.StatusCode.FAILED_PRECONDITION: 409,
    grpc.StatusCode.DEADLINE_EXCEEDED: 504,
    grpc.StatusCode.UNAVAILABLE: 503,
}


@app.post("/orders")
def create_order():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            status="rejected",
            message="Request must be a JSON object",
        ), 400

    item_id = data.get("item_id")
    quantity = data.get("quantity")

    if not isinstance(item_id, str) or not item_id.strip():
        return jsonify(
            status="rejected",
            message="item_id must be a nonempty string",
        ), 400

    if type(quantity) is not int or not 0 < quantity <= 2147483647:
        return jsonify(
            status="rejected",
            message="quantity must be a positive int32 integer",
        ), 400

    try:
        result, rpc = stub.CheckInventory.with_call(
            inventory_pb2.InventoryRequest(
                item_id=item_id,
                quantity=quantity,
            ),
            timeout=DEADLINE_SECONDS,
        )

    except grpc.RpcError as error:
        code = error.code()
        http_status = HTTP_STATUS_BY_GRPC.get(code, 502)

        app.logger.warning(
            "Inventory gRPC call failed: %s",
            code.name,
        )

        return jsonify(
            status="rejected" if http_status in (400, 404, 409) else "error",
            grpc_status=code.name,
            message=error.details(),
        ), http_status

    app.logger.info(
        "Inventory gRPC call succeeded: %s",
        rpc.code().name,
    )

    return jsonify(
        status="accepted",
        grpc_status=rpc.code().name,
        inventory={
            "available": result.available,
            "available_quantity": result.available_quantity,
            "message": result.message,
            "item_id": result.item_id,
            "quantity": result.quantity,
        },
    ), 200


@app.get("/health")
def health():
    return jsonify(service="order", status="ok"), 200


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )
    app.run(host="127.0.0.1", port=5002)