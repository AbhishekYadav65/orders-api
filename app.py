from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uuid import uuid4
import time

app = FastAPI()

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)

# -----------------------------
# Assignment values
# -----------------------------
TOTAL_ORDERS = 44
RATE_LIMIT = 17
WINDOW = 10  # seconds

# -----------------------------
# Memory storage
# -----------------------------
idempotency_store = {}

client_requests = {}

orders = [
    {
        "id": i,
        "item": f"Item {i}"
    }
    for i in range(1, TOTAL_ORDERS + 1)
]

# -----------------------------
# Request model
# -----------------------------
class OrderRequest(BaseModel):
    product: str = "sample"
    quantity: int = 1


# ==========================================================
# POST /orders
# ==========================================================
@app.post("/orders", status_code=201)
def create_order(
    order: OrderRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key")
):

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    created = {
        "id": str(uuid4()),
        "product": order.product,
        "quantity": order.quantity
    }

    idempotency_store[idempotency_key] = created

    return created


# ==========================================================
# GET /orders
# ==========================================================
@app.get("/orders")
def list_orders(limit: int = 10, cursor: str | None = None):

    start = int(cursor) if cursor else 0

    end = min(start + limit, TOTAL_ORDERS)

    items = orders[start:end]

    next_cursor = str(end) if end < TOTAL_ORDERS else None

    return {
        "items": items,
        "next_cursor": next_cursor
    }


# ==========================================================
# Middleware for Rate Limiting
# ==========================================================
@app.middleware("http")
async def rate_limit(request, call_next):

    client = request.headers.get("X-Client-Id")

    if client:

        now = time.time()

        history = client_requests.get(client, [])

        history = [t for t in history if now - t < WINDOW]

        if len(history) >= RATE_LIMIT:

            retry = WINDOW - (now - history[0])

            response = Response(
                content="Too Many Requests",
                status_code=429
            )

            response.headers["Retry-After"] = str(int(retry) + 1)

            return response

        history.append(now)

        client_requests[client] = history

    response = await call_next(request)

    return response


@app.get("/")
def home():
    return {
        "status": "running"
    }