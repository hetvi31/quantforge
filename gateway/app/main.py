import os
import time
import socket
import threading
import asyncio
from typing import Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from loguru import logger
import psycopg2
from psycopg2.extras import RealDictCursor
from prometheus_client import make_asgi_app, Counter, Histogram, Gauge

from app.db.init_db import init_pool, init_database, get_db_connection, release_db_connection
from app.risk import RiskEngine
from app import protocol

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
ENGINE_HOST = os.getenv("FEED_HOST", "127.0.0.1")
ENGINE_PORT = int(os.getenv("FEED_TCP_PORT", 9001))
ACCOUNT_ID = 1

# API key gates all mutating/admin endpoints. Empty string disables auth (local dev).
API_KEY = os.getenv("API_KEY", "quantforge-dev-key")

# CORS is restricted to known terminal origins instead of a wildcard.
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS", "http://localhost:3001,http://localhost:5173"
).split(",") if o.strip()]

risk_engine = RiskEngine()

app = FastAPI(title="QuantForge API Gateway", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# --------------------------------------------------------------------------- #
# Prometheus metrics
# --------------------------------------------------------------------------- #
ORDER_COUNT = Counter("quantforge_orders_total", "Total orders accepted", ["side", "type"])
REJECT_COUNT = Counter("quantforge_orders_rejected_total", "Orders rejected by pre-trade risk")
EXECUTION_COUNT = Counter("quantforge_executions_total", "Total executions filled")
LATENCY_HIST = Histogram(
    "quantforge_order_roundtrip_seconds",
    "Order submit -> engine acknowledgement round-trip latency",
    buckets=(0.00005, 0.0001, 0.00025, 0.0005, 0.001, 0.0025, 0.005, 0.01, 0.05, 0.1),
)
LAST_LATENCY_US = Gauge("quantforge_last_order_latency_microseconds", "Most recent order round-trip (us)")
ACTIVE_CONNECTIONS = Gauge("quantforge_active_websockets", "Active WebSocket connections")

app.mount("/metrics", make_asgi_app())

# --------------------------------------------------------------------------- #
# Shared state
# --------------------------------------------------------------------------- #
engine_socket: Optional[socket.socket] = None
engine_lock = threading.Lock()

websocket_clients: Set[WebSocket] = set()
ws_lock = threading.Lock()

order_id_counter = 0
order_id_lock = threading.Lock()

# order_id -> monotonic send time (ns), for round-trip latency measurement.
order_send_times: dict = {}
measured_orders: set = set()
send_times_lock = threading.Lock()

# The asyncio loop the app runs on; captured at startup so background threads
# can schedule WebSocket sends safely with run_coroutine_threadsafe.
MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class OrderRequest(BaseModel):
    symbol: str
    side: str   # "B" or "S"
    type: str   # "L" or "M"
    price: float
    quantity: int

    @field_validator("side")
    @classmethod
    def _side(cls, v):
        if v not in ("B", "S"):
            raise ValueError("side must be 'B' or 'S'")
        return v

    @field_validator("type")
    @classmethod
    def _type(cls, v):
        if v not in ("L", "M"):
            raise ValueError("type must be 'L' or 'M'")
        return v

    @field_validator("quantity")
    @classmethod
    def _qty(cls, v):
        if v <= 0:
            raise ValueError("quantity must be positive")
        return v


class CancelRequest(BaseModel):
    symbol: str
    order_id: int


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# --------------------------------------------------------------------------- #
# Database helper (pooled)
# --------------------------------------------------------------------------- #
def db_query(query: str, params: tuple = (), commit: bool = False, fetch: bool = True):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, params)
        result = cur.fetchall() if fetch else None
        if commit:
            conn.commit()
        cur.close()
        return result
    except Exception as e:
        conn.rollback()
        logger.error(f"Database query error: {e}")
        raise
    finally:
        release_db_connection(conn)


# --------------------------------------------------------------------------- #
# Matching-engine TCP client
# --------------------------------------------------------------------------- #
def connect_to_engine():
    global engine_socket
    while True:
        try:
            logger.info(f"Connecting to C++ matching engine at {ENGINE_HOST}:{ENGINE_PORT}...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((ENGINE_HOST, ENGINE_PORT))
            with engine_lock:
                engine_socket = s
            logger.info("Connected to C++ matching engine.")
            threading.Thread(target=read_from_engine, args=(s,), daemon=True).start()
            return
        except Exception as e:
            logger.warning(f"Engine connect failed: {e}. Retrying in 2s...")
            time.sleep(2)


def read_from_engine(s: socket.socket):
    global engine_socket
    buffer = b""
    while True:
        try:
            data = s.recv(8192)
            if not data:
                logger.warning("Engine disconnected.")
                break
            buffer += data
            while len(buffer) >= protocol.REPORT_SIZE:
                packet, buffer = buffer[:protocol.REPORT_SIZE], buffer[protocol.REPORT_SIZE:]
                report = protocol.unpack_report(packet)
                latency_us = record_latency(report["order_id"], report["status"])
                process_execution_report(report, latency_us)
        except Exception as e:
            logger.error(f"Error reading from engine socket: {e}")
            break

    with engine_lock:
        if engine_socket is s:
            engine_socket = None
    connect_to_engine()


def record_latency(order_id: int, status: str) -> Optional[float]:
    """Measure submit->ack round-trip once per order; returns microseconds."""
    now = time.monotonic_ns()
    with send_times_lock:
        t0 = order_send_times.get(order_id)
        already = order_id in measured_orders
        if status in ("F", "C", "R"):
            order_send_times.pop(order_id, None)
            measured_orders.discard(order_id)
        elif t0 is not None and not already:
            measured_orders.add(order_id)
    if t0 is None or already:
        return None
    latency_us = (now - t0) / 1000.0
    LATENCY_HIST.observe(latency_us / 1e6)
    LAST_LATENCY_US.set(latency_us)
    return latency_us


def process_execution_report(report: dict, latency_us: Optional[float]):
    order_id = report["order_id"]
    symbol = report["symbol"]
    side = report["side"]
    status = report["status"]
    price = report["price"]
    last_qty = report["last_quantity"]

    # All mutations for one execution report run in a single transaction on one
    # connection. The trade_id includes cumulative_quantity so two partial fills
    # of the same order in the same millisecond produce distinct keys. The
    # SELECT-before-INSERT provides idempotency: if the gateway restarts and
    # re-receives a report, the second pass is a no-op for the ledger.
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            "UPDATE orders SET remaining_quantity = %s, status = %s WHERE order_id = %s",
            (report["remaining_quantity"], status, order_id),
        )

        if last_qty > 0 and status in ("P", "F"):
            trade_id = (
                f"{symbol}_{report['timestamp']}_{order_id}"
                f"_{report['cumulative_quantity']}"
            )

            cur.execute("SELECT 1 FROM executions WHERE trade_id = %s", (trade_id,))
            already_settled = cur.fetchone() is not None

            if not already_settled:
                cur.execute(
                    "INSERT INTO executions (order_id, trade_id, price, quantity, timestamp) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (order_id, trade_id, price, last_qty, report["timestamp"]),
                )
                EXECUTION_COUNT.inc()

                cur.execute(
                    "SELECT account_id FROM orders WHERE order_id = %s", (order_id,)
                )
                row = cur.fetchone()
                if row:
                    account_id = row["account_id"]
                    cost = price * last_qty
                    if side == "B":
                        cur.execute(
                            "UPDATE accounts SET balance = balance - %s WHERE account_id = %s",
                            (cost, account_id),
                        )
                        cur.execute(
                            """
                            INSERT INTO positions (account_id, symbol, quantity, average_price)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (account_id, symbol) DO UPDATE
                            SET average_price = CASE
                                    WHEN positions.quantity + EXCLUDED.quantity = 0 THEN 0
                                    ELSE ((positions.quantity * positions.average_price)
                                          + EXCLUDED.quantity * EXCLUDED.average_price)
                                         / (positions.quantity + EXCLUDED.quantity)
                                END,
                                quantity = positions.quantity + EXCLUDED.quantity
                            """,
                            (account_id, symbol, last_qty, price),
                        )
                    else:
                        cur.execute(
                            "UPDATE accounts SET balance = balance + %s WHERE account_id = %s",
                            (cost, account_id),
                        )
                        cur.execute(
                            "UPDATE positions SET quantity = quantity - %s "
                            "WHERE account_id = %s AND symbol = %s",
                            (last_qty, account_id, symbol),
                        )
                        cur.execute(
                            "DELETE FROM positions "
                            "WHERE account_id = %s AND symbol = %s AND quantity = 0",
                            (account_id, symbol),
                        )

        conn.commit()
        cur.close()
    except Exception as e:
        conn.rollback()
        logger.error(f"Settlement error for order {order_id}: {e}")
    finally:
        release_db_connection(conn)

    broadcast_to_websockets({
        "type": "EXECUTION",
        "order_id": order_id,
        "symbol": symbol,
        "side": side,
        "status": status,
        "price": price,
        "last_quantity": last_qty,
        "cumulative_quantity": report["cumulative_quantity"],
        "remaining_quantity": report["remaining_quantity"],
        "timestamp": report["timestamp"],
        "reject_reason": report["reject_reason"],
        "latency_us": round(latency_us, 1) if latency_us is not None else None,
    })


# --------------------------------------------------------------------------- #
# WebSocket fan-out (thread-safe)
# --------------------------------------------------------------------------- #
async def _send_safe(ws: WebSocket, message: dict):
    try:
        await ws.send_json(message)
    except Exception:
        with ws_lock:
            websocket_clients.discard(ws)


def broadcast_to_websockets(message: dict):
    loop = MAIN_LOOP
    if loop is None:
        return
    with ws_lock:
        clients = list(websocket_clients)
    for ws in clients:
        asyncio.run_coroutine_threadsafe(_send_safe(ws, message), loop)


# --------------------------------------------------------------------------- #
# Redis market-data + order-book subscription
# --------------------------------------------------------------------------- #
def start_redis_subscription():
    import redis as redis_lib
    logger.info("Subscribing to Redis market_data and order_book channels...")
    while True:
        try:
            r = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            pubsub = r.pubsub()
            pubsub.subscribe("market_data", "order_book")
            for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                channel = message["channel"]
                if channel == "market_data":
                    broadcast_to_websockets({"type": "MARKET_TICK", "data": message["data"]})
                elif channel == "order_book":
                    broadcast_to_websockets({"type": "ORDER_BOOK", "data": message["data"]})
        except Exception as e:
            logger.error(f"Redis subscription error: {e}. Reconnecting in 2s...")
            time.sleep(2)


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #
@app.on_event("startup")
async def startup_event():
    global MAIN_LOOP, order_id_counter
    MAIN_LOOP = asyncio.get_running_loop()
    init_pool()
    init_database()

    rows = db_query("SELECT COALESCE(MAX(order_id), 0) AS m FROM orders")
    seeded = int(rows[0]["m"]) if rows else 0
    # Monotonic and collision-free across restarts.
    order_id_counter = max(seeded, int(time.time() * 1000))

    threading.Thread(target=connect_to_engine, daemon=True).start()
    threading.Thread(target=start_redis_subscription, daemon=True).start()


# --------------------------------------------------------------------------- #
# REST endpoints
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    try:
        db_query("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    with engine_lock:
        engine_ok = engine_socket is not None
    if not db_ok:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok" if engine_ok else "degraded",
            "database": db_ok, "matching_engine": engine_ok}


@app.post("/api/v1/orders/create", dependencies=[Depends(require_api_key)])
def place_order(order: OrderRequest):
    global order_id_counter

    with engine_lock:
        if engine_socket is None:
            raise HTTPException(status_code=503, detail="Matching engine is not reachable.")

    with order_id_lock:
        order_id_counter += 1
        order_id = order_id_counter

    # Risk check and order persistence share one connection/transaction snapshot.
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        passed, reason = risk_engine.check_order(
            cur, ACCOUNT_ID, order.symbol, order.side, order.price, order.quantity
        )
        if not passed:
            cur.execute(
                "INSERT INTO orders (order_id, account_id, symbol, side, type, price, "
                "quantity, remaining_quantity, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 'R')",
                (order_id, ACCOUNT_ID, order.symbol, order.side, order.type,
                 order.price, order.quantity),
            )
            conn.commit()
            cur.close()
            REJECT_COUNT.inc()
            raise HTTPException(status_code=400,
                                detail=f"Order rejected by pre-trade risk checks: {reason}")

        cur.execute(
            "INSERT INTO orders (order_id, account_id, symbol, side, type, price, "
            "quantity, remaining_quantity, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'N')",
            (order_id, ACCOUNT_ID, order.symbol, order.side, order.type,
             order.price, order.quantity, order.quantity),
        )
        conn.commit()
        cur.close()
    finally:
        release_db_connection(conn)

    action = protocol.ACTION_MARKET if order.type == "M" else protocol.ACTION_LIMIT
    packet = protocol.pack_order(order_id, order.symbol, order.side, action,
                                 order.price, order.quantity)

    with send_times_lock:
        order_send_times[order_id] = time.monotonic_ns()

    with engine_lock:
        try:
            engine_socket.sendall(packet)
            ORDER_COUNT.labels(side=order.side, type=order.type).inc()
        except Exception as e:
            with send_times_lock:
                order_send_times.pop(order_id, None)
            logger.error(f"Failed to send order to engine: {e}")
            raise HTTPException(status_code=500, detail="Failed to transmit order to engine.")

    return {"status": "SUCCESS", "order_id": order_id}


@app.post("/api/v1/orders/cancel", dependencies=[Depends(require_api_key)])
def cancel_order(req: CancelRequest):
    with engine_lock:
        if engine_socket is None:
            raise HTTPException(status_code=503, detail="Matching engine is not reachable.")
        try:
            engine_socket.sendall(protocol.pack_cancel(req.order_id, req.symbol))
        except Exception as e:
            logger.error(f"Failed to send cancel: {e}")
            raise HTTPException(status_code=500, detail="Failed to transmit cancellation.")
    return {"status": "CANCEL_SENT", "order_id": req.order_id}


@app.post("/api/v1/admin/killswitch", dependencies=[Depends(require_api_key)])
def trigger_killswitch():
    orders = db_query("SELECT order_id, symbol FROM orders WHERE status IN ('N', 'P')")
    sent = 0
    with engine_lock:
        if engine_socket is None:
            raise HTTPException(status_code=503, detail="Matching engine is not reachable.")
        for o in orders:
            try:
                engine_socket.sendall(protocol.pack_cancel(o["order_id"], o["symbol"]))
                sent += 1
            except Exception:
                pass
    return {"status": "KILLSWITCH_TRIGGERED", "cancelled_orders_sent": sent}


@app.get("/api/v1/portfolio/status")
def get_portfolio():
    account = db_query("SELECT balance, margin_utilization FROM accounts WHERE account_id = 1;")
    positions = db_query("SELECT symbol, quantity, average_price FROM positions WHERE account_id = 1;")
    if not account:
        return {"cash": 0.0, "margin": 0.0, "positions": []}
    return {
        "cash": float(account[0]["balance"]),
        "margin": float(account[0]["margin_utilization"]),
        "positions": [
            {"symbol": p["symbol"], "quantity": p["quantity"],
             "average_price": float(p["average_price"])}
            for p in positions
        ],
    }


@app.get("/api/v1/orders/active")
def get_active_orders():
    orders = db_query(
        "SELECT order_id, symbol, side, type, price, quantity, remaining_quantity, status, "
        "created_at FROM orders WHERE status IN ('N', 'P') ORDER BY created_at DESC;"
    )
    return [
        {
            "order_id": o["order_id"], "symbol": o["symbol"], "side": o["side"],
            "type": o["type"], "price": float(o["price"]) if o["price"] else 0.0,
            "quantity": o["quantity"], "remaining_quantity": o["remaining_quantity"],
            "status": o["status"], "created_at": o["created_at"].isoformat(),
        }
        for o in orders
    ]


# --------------------------------------------------------------------------- #
# WebSocket
# --------------------------------------------------------------------------- #
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    with ws_lock:
        websocket_clients.add(websocket)
    ACTIVE_CONNECTIONS.inc()
    logger.info(f"WebSocket connected. Total clients: {len(websocket_clients)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket exception: {e}")
    finally:
        with ws_lock:
            websocket_clients.discard(websocket)
        ACTIVE_CONNECTIONS.dec()
