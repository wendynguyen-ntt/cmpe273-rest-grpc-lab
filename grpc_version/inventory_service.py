import logging
import os
import time
from concurrent import futures

import grpc
import inventory_pb2
import inventory_pb2_grpc

STOCK = {
    "notebook": 10,
    "pen": 20,
}

DELAY_SECONDS = float(os.getenv("INVENTORY_DELAY_SECONDS", "0"))


class InventoryService(inventory_pb2_grpc.InventoryServiceServicer):
    def CheckInventory(self, request, context):
        logging.info(
            "CheckInventory item=%s quantity=%s",
            request.item_id,
            request.quantity,
        )

        if not request.item_id.strip():
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "item_id must be a nonempty string",
            )

        if request.quantity <= 0:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "quantity must be a positive integer",
            )

        if DELAY_SECONDS > 0:
            logging.info(
                "Delaying inventory response by %s seconds",
                DELAY_SECONDS,
            )
            time.sleep(DELAY_SECONDS)

        if request.item_id not in STOCK:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                "Item not found",
            )

        available_quantity = STOCK[request.item_id]

        if request.quantity > available_quantity:
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                "Insufficient stock",
            )

        return inventory_pb2.InventoryResponse(
            available=True,
            available_quantity=available_quantity,
            message="Inventory available",
            item_id=request.item_id,
            quantity=request.quantity,
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(
        InventoryService(),
        server,
    )

    server.add_insecure_port("127.0.0.1:50051")
    server.start()
    logging.info("gRPC Inventory running on 127.0.0.1:50051")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0).wait()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )
    serve()