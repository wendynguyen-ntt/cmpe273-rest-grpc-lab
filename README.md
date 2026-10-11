# CMPE273 Lab: REST vs. gRPC

This Python lab implements the same Order → Inventory interaction using REST/HTTP and gRPC. An order contains an `item_id` and a `quantity`, Inventory checks whether that quantity is available.

Both versions use two separately running services. Inventory starts with 10 notebooks and 20 pens. The lab checks availability only: it does not reserve stock, deduct stock, or persist orders.

Both versions require a nonempty string `item_id` and an integer `quantity` from 1 through 2147483647, matching the gRPC contract's `int32` range.

## Service interfaces

| Version | Order interface | Order → Inventory communication |
| --- | --- | --- |
| REST | `POST http://127.0.0.1:5002/orders` | HTTP POST to `http://127.0.0.1:5001/inventory/check`, using JSON |
| gRPC | `POST http://127.0.0.1:5002/orders` | gRPC `InventoryService.CheckInventory` on `127.0.0.1:50051`, using Protocol Buffers |

The gRPC version keeps Order's public HTTP endpoint so it can be tested with curl. Its internal Order → Inventory call is a real gRPC call as defined in `grpc_version/inventory.proto`. Order includes the actual RPC status in its JSON response as `grpc_status`.

Order also exposes `GET /health` in both versions. Because the two Order implementations use the same port, stop one version before starting the other.

## Files

| File | Purpose |
| --- | --- |
| `rest/inventory_service.py` | REST Inventory implementation |
| `rest/order_service.py` | REST Order implementation and HTTP client |
| `grpc_version/inventory.proto` | Inventory RPC contract and message definitions |
| `grpc_version/inventory_pb2.py` | Generated Protocol Buffer message classes |
| `grpc_version/inventory_pb2_grpc.py` | Generated gRPC client/server interfaces |
| `grpc_version/inventory_service.py` | gRPC Inventory implementation |
| `grpc_version/order_service.py` | Order implementation and gRPC client |
| `requirements.txt` | Python dependency versions |

## Setup

Tested on macOS with Python 3.9.6 and gRPC 1.76.0. Run the following from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Activate `.venv` in each terminal that runs a Python service. The curl commands can run in a separate terminal without activating it.

The macOS Python used for these tests printed a `NotOpenSSLWarning` when importing Requests because it uses LibreSSL. All REST calls in this lab use local HTTP without TLS and completed successfully.

## Run and test REST

### Start the services

Terminal 1, from the repository root:

```bash
source .venv/bin/activate
python rest/inventory_service.py
```

Terminal 2, from the repository root:

```bash
source .venv/bin/activate
python rest/order_service.py
```

### Successful order

Terminal 3:

```bash
curl -i -X POST http://127.0.0.1:5002/orders \
  -H "Content-Type: application/json" \
  -d '{"item_id":"notebook","quantity":3}'
```

Recorded response excerpt:

```text
HTTP/1.1 200 OK

{"inventory":{"available":true,"available_quantity":10,"item_id":"notebook","message":"Inventory available","quantity":3},"status":"accepted"}
```

Inventory can also be tested directly using the same JSON body at `http://127.0.0.1:5001/inventory/check`.

### Insufficient stock

```bash
curl -i -X POST http://127.0.0.1:5002/orders \
  -H "Content-Type: application/json" \
  -d '{"item_id":"notebook","quantity":11}'
```

Recorded response excerpt:

```text
HTTP/1.1 409 CONFLICT

{"inventory":{"available":false,"available_quantity":10,"message":"Insufficient stock"},"status":"rejected"}
```

Inventory returns `400` for invalid JSON or invalid fields, `404` for an unknown item, and `409` for insufficient stock. Order passes these statuses back to its caller. Communication failures return `503`, a timeout returns `504`, and an unexpected upstream response returns `502`.

### REST timeout evidence

Order sets `timeout=2` on its HTTP request to Inventory. This configures connection and read timeouts, it is not a single total-duration deadline for arbitrary HTTP responses.

In Terminal 1, press Control+C to stop only Inventory, then restart it with a five-second delay:

```bash
INVENTORY_DELAY_SECONDS=5 python rest/inventory_service.py
```

Keep Order running in Terminal 2. In Terminal 3:

```bash
curl -i -w '\nTotal time: %{time_total} seconds\n' \
  -X POST http://127.0.0.1:5002/orders \
  -H "Content-Type: application/json" \
  -d '{"item_id":"notebook","quantity":3}'
```

Recorded response excerpt:

```text
HTTP/1.1 504 GATEWAY TIMEOUT

{"message":"Inventory request timed out","status":"error"}

Total time: 2.009491 seconds
```

Inventory delayed before sending its response, so Order's read timeout occurred after about two seconds. Order caught `requests.exceptions.Timeout` and returned a controlled JSON error.

### Order remained running after the REST timeout

Without restarting Order, run:

```bash
curl -i http://127.0.0.1:5002/health
```

Recorded response excerpt:

```text
HTTP/1.1 200 OK

{"service":"order","status":"ok"}
```

In Terminal 1, stop delayed Inventory with Control+C and restart it normally:

```bash
python rest/inventory_service.py
```

Repeat the successful-order curl command in Terminal 3, still without restarting Order. Recorded response excerpt:

```text
HTTP/1.1 200 OK

{"inventory":{"available":true,"available_quantity":10,"item_id":"notebook","message":"Inventory available","quantity":3},"status":"accepted"}
```

The health check and successful new order demonstrate that Order continued serving requests after the timeout.

## Run and test gRPC

Stop both REST services with Control+C before switching versions.

### Generate the Python contract files

From the repository root, with `.venv` activated:

```bash
python -m grpc_tools.protoc \
  -I grpc_version \
  --python_out=grpc_version \
  --grpc_python_out=grpc_version \
  grpc_version/inventory.proto
```

This generates `inventory_pb2.py` and `inventory_pb2_grpc.py`. The contract defines a unary `CheckInventory` RPC taking an `InventoryRequest` and returning an `InventoryResponse`. Request fields are `item_id` (string) and `quantity` (int32).

### Start the services

Terminal 1, from the repository root:

```bash
source .venv/bin/activate
python grpc_version/inventory_service.py
```

Terminal 2, from the repository root:

```bash
source .venv/bin/activate
python grpc_version/order_service.py
```

### Successful gRPC-backed order

Terminal 3:

```bash
curl -i -X POST http://127.0.0.1:5002/orders \
  -H "Content-Type: application/json" \
  -d '{"item_id":"notebook","quantity":3}'
```

Order constructs an `InventoryRequest` and calls the generated gRPC stub's `CheckInventory.with_call(...)` method. The Inventory response fields and actual RPC status are then presented as JSON to the HTTP caller.

Recorded response excerpt:

```text
HTTP/1.1 200 OK

{"grpc_status":"OK","inventory":{"available":true,"available_quantity":10,"item_id":"notebook","message":"Inventory available","quantity":3},"status":"accepted"}
```

### Unavailable inventory: gRPC error evidence

```bash
curl -i -X POST http://127.0.0.1:5002/orders \
  -H "Content-Type: application/json" \
  -d '{"item_id":"notebook","quantity":11}'
```

Recorded response excerpt:

```text
HTTP/1.1 409 CONFLICT

{"grpc_status":"FAILED_PRECONDITION","message":"Insufficient stock","status":"rejected"}
```

Inventory aborts the RPC with `FAILED_PRECONDITION` because the current stock cannot satisfy the order. Order catches `grpc.RpcError`, reads its status, and maps it to HTTP `409` for its public endpoint.

| gRPC status | Meaning | HTTP status returned by Order |
| --- | --- | --- |
| `OK` | Inventory check succeeded | `200` |
| `INVALID_ARGUMENT` | Invalid request fields | `400` |
| `NOT_FOUND` | Unknown item | `404` |
| `FAILED_PRECONDITION` | Insufficient stock | `409` |
| `DEADLINE_EXCEEDED` | RPC exceeded its deadline | `504` |
| `UNAVAILABLE` | Inventory cannot be reached | `503` |

Order validates public JSON input before constructing the typed request. Those validation errors return HTTP `400` without making an RPC. Unexpected gRPC errors map to HTTP `502`.

### gRPC deadline evidence

Order passes `timeout=2` to the RPC method, setting a two-second gRPC deadline for the entire call.

In Terminal 1, stop only gRPC Inventory with Control+C and restart with the five-second delay:

```bash
INVENTORY_DELAY_SECONDS=5 python grpc_version/inventory_service.py
```

Keep gRPC Order running in Terminal 2. In Terminal 3:

```bash
curl -i -w '\nTotal time: %{time_total} seconds\n' \
  -X POST http://127.0.0.1:5002/orders \
  -H "Content-Type: application/json" \
  -d '{"item_id":"notebook","quantity":3}'
```

Recorded response excerpt:

```text
HTTP/1.1 504 GATEWAY TIMEOUT

{"grpc_status":"DEADLINE_EXCEEDED","message":"Deadline Exceeded","status":"error"}

Total time: 2.009160 seconds
```

Order caught `grpc.RpcError` with `DEADLINE_EXCEEDED` and returned a controlled JSON error after about two seconds. The deliberate `time.sleep(5)` in Inventory may finish later, deadline expiration does not interrupt that Python sleep.

### Order remained running after the gRPC deadline

Without restarting Order, run:

```bash
curl -i http://127.0.0.1:5002/health
```

Recorded response excerpt:

```text
HTTP/1.1 200 OK

{"service":"order","status":"ok"}
```

In Terminal 1, stop delayed Inventory with Control+C and restart normally:

```bash
python grpc_version/inventory_service.py
```

Repeat the successful-order curl command in Terminal 3, still without restarting Order. Recorded response excerpt:

```text
HTTP/1.1 200 OK

{"grpc_status":"OK","inventory":{"available":true,"available_quantity":10,"item_id":"notebook","message":"Inventory available","quantity":3},"status":"accepted"}
```

The health check and successful new RPC-backed order demonstrate that Order continued serving requests after the exceeded deadline.

## REST vs. gRPC comparison

REST used a JSON endpoint that I could test directly with curl. gRPC required a `.proto` contract and generated Python files but gave Order a typed `CheckInventory` client method. Both implementations still needed business validation such as checking that quantity was positive and enough stock existed. REST reported insufficient stock with HTTP `409`, whereas, gRPC reported `FAILED_PRECONDITION`, which Order translated into HTTP `409` for its public endpoint. The Requests timeout limited connection and read waits while the gRPC deadline limited the entire RPC. With a five-second Inventory delay, both versions returned controlled errors after about two seconds, and Order stayed running and accepted another order after Inventory recovered.
