import os
import sys
import time
import socket
import struct
import threading
import asyncio
from typing import List, Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
from prometheus_client import make_asgi_app, Counter, Histogram, Gauge

# Import DB creation utility
from app.db.init_db import get_db_connection, init_database
from app.risk import RiskEngine

risk_engine = RiskEngine()

app = FastAPI(title="QuantForge API Gateway", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus Metrics
ORDER_COUNT = Counter("quantforge_orders_total", "Total count of orders placed", ["side", "type"])
EXECUTION_COUNT = Counter("quantforge_executions_total", "Total count of executions filled")
LATENCY_HIST = Histogram("quantforge_order_latency_seconds", "Matching engine execution latency")
ACTIVE_CONNECTIONS = Gauge("quantforge_active_websockets", "Active WebSocket connections")

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Environment Configurations
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
ENGINE_HOST = os.getenv("FEED_HOST", "127.0.0.1")
ENGINE_PORT = int(os.getenv("FEED_TCP_PORT", 9001))

# Global states
engine_socket = None
engine_lock = threading.Lock()
websocket_clients: Set[WebSocket] = set()
order_id_counter = int(time.time() * 1000)
order_id_lock = threading.Lock()

# Pydantic schemas
class OrderRequest(BaseModel):
    symbol: str
    side: str  # "B" or "S"
    type: str  # "L" or "M"
    price: float
    quantity: int

class CancelRequest(BaseModel):
    symbol: str
    order_id: int

# Database Queries Helpers
def db_query(query: str, params: tuple = (), commit: bool = False, fetch: bool = True):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(query, params)
        if commit:
            conn.commit()
        if fetch:
            return cur.fetchall()
        return None
    except Exception as e:
        logger.error(f"Database Query Error: {e}")
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

# TCP client to C++ engine
def connect_to_engine():
    global engine_socket
    while True:
        try:
            logger.info(f"Connecting to C++ Matching Engine at {ENGINE_HOST}:{ENGINE_PORT}...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((ENGINE_HOST, ENGINE_PORT))
            with engine_lock:
                engine_socket = s
            logger.info("Connected to C++ Matching Engine successfully!")
            
            # Start reader thread
            threading.Thread(target=read_from_engine, args=(s,), daemon=True).start()
            break
        except Exception as e:
            logger.warning(f"Failed to connect to matching engine: {e}. Retrying in 2 seconds...")
            time.sleep(2)

def read_from_engine(s: socket.socket):
    global engine_socket
    buffer = b""
    # Struct format: uint64_t, char[16], char, char, double, uint64_t, uint64_t, uint64_t, uint64_t, char[64]
    struct_format = "<Q16sccdQQQQ64s"
    struct_size = struct.calcsize(struct_format)

    while True:
        try:
            data = s.recv(4096)
            if not data:
                logger.warning("Engine disconnected.")
                break
            
            buffer += data
            while len(buffer) >= struct_size:
                packet = buffer[:struct_size]
                buffer = buffer[struct_size:]
                
                # Unpack Execution Report
                fields = struct.unpack(struct_format, packet)
                order_id = fields[0]
                symbol = fields[1].decode('utf-8').rstrip('\x00')
                side = fields[2].decode('utf-8')
                status = fields[3].decode('utf-8')
                price = fields[4]
                last_qty = fields[5]
                cum_qty = fields[6]
                rem_qty = fields[7]
                timestamp = fields[8]
                reject_reason = fields[9].decode('utf-8').rstrip('\x00')

                logger.info(f"[Execution] Order ID: {order_id}, Status: {status}, Price: {price}, Qty: {last_qty}")

                # Process report asynchronously in python db
                process_execution_report(
                    order_id, symbol, side, status, price, last_qty, cum_qty, rem_qty, timestamp, reject_reason
                )
        except Exception as e:
            logger.error(f"Error reading from engine socket: {e}")
            break
            
    with engine_lock:
        if engine_socket == s:
            engine_socket = None
    connect_to_engine()

def process_execution_report(order_id, symbol, side, status, price, last_qty, cum_qty, rem_qty, timestamp, reject_reason):
    # Update Order Table
    db_query(
        "UPDATE orders SET remaining_quantity = %s, status = %s WHERE order_id = %s",
        (rem_qty, status, order_id),
        commit=True,
        fetch=False
    )

    # Insert execution if trade filled
    if last_qty > 0 and status in ('P', 'F'):
        trade_id = f"{symbol}_{timestamp}_{order_id}"
        try:
            db_query(
                "INSERT INTO executions (order_id, trade_id, price, quantity, timestamp) VALUES (%s, %s, %s, %s, %s)",
                (order_id, trade_id, price, last_qty, timestamp),
                commit=True,
                fetch=False
            )
            EXECUTION_COUNT.inc()
        except psycopg2.errors.UniqueViolation:
            pass # Skip duplicate records if dual reporting matches
        
        # Resolve Account Balance & Positions
        orders = db_query("SELECT account_id FROM orders WHERE order_id = %s", (order_id,))
        if orders:
            account_id = orders[0]['account_id']
            cost = price * last_qty

            if side == 'B':
                # BUY: deduct cash balance, add position
                db_query(
                    "UPDATE accounts SET balance = balance - %s WHERE account_id = %s",
                    (cost, account_id),
                    commit=True,
                    fetch=False
                )
                db_query(
                    """
                    INSERT INTO positions (account_id, symbol, quantity, average_price)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (account_id, symbol) DO UPDATE
                    SET average_price = ((positions.quantity * positions.average_price) + EXCLUDED.quantity * EXCLUDED.average_price) / (positions.quantity + EXCLUDED.quantity),
                        quantity = positions.quantity + EXCLUDED.quantity;
                    """,
                    (account_id, symbol, last_qty, price),
                    commit=True,
                    fetch=False
                )
            else:
                # SELL: credit cash balance, deduct position
                db_query(
                    "UPDATE accounts SET balance = balance + %s WHERE account_id = %s",
                    (cost, account_id),
                    commit=True,
                    fetch=False
                )
                db_query(
                    """
                    UPDATE positions SET quantity = quantity - %s WHERE account_id = %s AND symbol = %s;
                    """,
                    (last_qty, account_id, symbol),
                    commit=True,
                    fetch=False
                )
                # Clean zero quantity positions
                db_query(
                    "DELETE FROM positions WHERE account_id = %s AND symbol = %s AND quantity = 0",
                    (account_id, symbol),
                    commit=True,
                    fetch=False
                )

    # Broadcast update to web clients
    payload = {
        "type": "EXECUTION",
        "order_id": order_id,
        "symbol": symbol,
        "side": side,
        "status": status,
        "price": price,
        "last_quantity": last_qty,
        "cumulative_quantity": cum_qty,
        "remaining_quantity": rem_qty,
        "timestamp": timestamp,
        "reject_reason": reject_reason
    }
    broadcast_to_websockets(payload)

# Websocket manager helper
def broadcast_to_websockets(message: dict):
    # Retrieve active event loop or run threadsafe
    loop = asyncio.get_event_loop()
    for ws in websocket_clients:
        loop.create_task(ws.send_json(message))

# Redis subscription in thread
def start_redis_subscription():
    logger.info("Initializing Redis market data sub listener...")
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe("market_data")
    
    # Run loop
    for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                # Broadcast real-time tick to websocket
                payload = {
                    "type": "MARKET_TICK",
                    "data": message['data']
                }
                broadcast_to_websockets(payload)
            except Exception as e:
                logger.error(f"Redis Broadcast Error: {e}")

# Startup & Shutdown Lifecycles
@app.on_event("startup")
def startup_event():
    # 1. Initialize SQL schemas
    init_database()
    
    # 2. Connect to C++ Matching Engine
    connect_to_engine()
    
    # 3. Start Redis listener in separate background thread
    threading.Thread(target=start_redis_subscription, daemon=True).start()

# REST Endpoints
@app.post("/api/v1/orders/create")
def place_order(order: OrderRequest):
    global order_id_counter
    
    # Perform pre-flight check on socket connection to matching engine
    with engine_lock:
        if engine_socket is None:
            raise HTTPException(status_code=503, detail="Matching engine is not reachable.")

    # 1. Assign unique Order ID
    with order_id_lock:
        order_id_counter += 1
        order_id = order_id_counter

    account_id = 1

    # 2. Risk check
    passed, reason = risk_engine.check_order(
        account_id=account_id,
        symbol=order.symbol,
        side=order.side,
        price=order.price,
        quantity=order.quantity
    )

    if not passed:
        # Save as rejected order in the database
        db_query(
            """
            INSERT INTO orders (order_id, account_id, symbol, side, type, price, quantity, remaining_quantity, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 'R')
            """,
            (order_id, account_id, order.symbol, order.side, order.type, order.price, order.quantity),
            commit=True,
            fetch=False
        )
        raise HTTPException(status_code=400, detail=f"Order rejected by pre-trade risk checks: {reason}")

    # 3. Insert as pending/NEW in Postgres
    db_query(
        """
        INSERT INTO orders (order_id, account_id, symbol, side, type, price, quantity, remaining_quantity, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'N')
        """,
        (order_id, account_id, order.symbol, order.side, order.type, order.price, order.quantity, order.quantity),
        commit=True,
        fetch=False
    )
    
    # 4. Create binary struct and send to C++ engine
    # struct format: uint64_t (order_id), char[16] (symbol), char (side), char (type), double (price), uint64_t (quantity)
    side_char = order.side.encode('utf-8')
    type_char = order.type.encode('utf-8')
    symbol_bytes = order.symbol.encode('utf-8')

    order_packet = struct.pack("<Q16sccdQ", order_id, symbol_bytes, side_char, type_char, order.price, order.quantity)
    
    with engine_lock:
        try:
            engine_socket.sendall(order_packet)
            ORDER_COUNT.labels(side=order.side, type=order.type).inc()
        except Exception as e:
            logger.error(f"Failed to send order to matching engine: {e}")
            raise HTTPException(status_code=500, detail="Failed to transmit order to engine.")

    return {"status": "SUCCESS", "order_id": order_id}

@app.post("/api/v1/orders/cancel")
def cancel_order(req: CancelRequest):
    # Perform cancellation. For matching engine cancellation, send a delete request package.
    # In this simplified model, cancel request uses type='C' in binary. We can define:
    # A cancel is sent as an order packet with quantity = 0, type = 'C' (cancel).
    with engine_lock:
        if engine_socket is None:
            raise HTTPException(status_code=503, detail="Matching engine is not reachable.")

    # Send cancel order packet:
    order_packet = struct.pack(
        "<Q16sccdQ", 
        req.order_id, 
        req.symbol.encode('utf-8'), 
        b'B', # default side
        b'C', # C for Cancel
        0.0,  # Price
        0     # Qty
    )

    with engine_lock:
        try:
            engine_socket.sendall(order_packet)
        except Exception as e:
            logger.error(f"Failed to send cancel to matching engine: {e}")
            raise HTTPException(status_code=500, detail="Failed to transmit cancellation.")

    return {"status": "CANCEL_SENT", "order_id": req.order_id}

@app.get("/api/v1/portfolio/status")
def get_portfolio():
    # Account 1 defaults
    account = db_query("SELECT balance, margin_utilization FROM accounts WHERE account_id = 1;")
    positions = db_query("SELECT symbol, quantity, average_price FROM positions WHERE account_id = 1;")
    
    if not account:
        return {"cash": 0.0, "margin": 0.0, "positions": []}
        
    return {
        "cash": float(account[0]['balance']),
        "margin": float(account[0]['margin_utilization']),
        "positions": [
            {
                "symbol": p['symbol'],
                "quantity": p['quantity'],
                "average_price": float(p['average_price'])
            }
            for p in positions
        ]
    }

@app.get("/api/v1/orders/active")
def get_active_orders():
    # Returns orders still working ('N' or 'P')
    orders = db_query("SELECT order_id, symbol, side, type, price, quantity, remaining_quantity, status, created_at FROM orders WHERE status IN ('N', 'P') ORDER BY created_at DESC;")
    return [
        {
            "order_id": o['order_id'],
            "symbol": o['symbol'],
            "side": o['side'],
            "type": o['type'],
            "price": float(o['price']) if o['price'] else 0.0,
            "quantity": o['quantity'],
            "remaining_quantity": o['remaining_quantity'],
            "status": o['status'],
            "created_at": o['created_at'].isoformat()
        }
        for o in orders
    ]

@app.post("/api/v1/admin/killswitch")
def trigger_killswitch():
    # Select all working orders, place cancel command for each
    orders = db_query("SELECT order_id, symbol FROM orders WHERE status IN ('N', 'P');")
    cancelled_count = 0
    
    with engine_lock:
        if engine_socket is None:
            raise HTTPException(status_code=503, detail="Matching engine is not reachable.")

    for o in orders:
        order_packet = struct.pack(
            "<Q16sccdQ", 
            o['order_id'], 
            o['symbol'].encode('utf-8'), 
            b'B',
            b'C',
            0.0,
            0
        )
        with engine_lock:
            try:
                engine_socket.sendall(order_packet)
                cancelled_count += 1
            except Exception:
                pass

    return {"status": "KILLSWITCH_TRIGGERED", "cancelled_orders_sent": cancelled_count}

# WebSockets Endpoint
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_clients.add(websocket)
    ACTIVE_CONNECTIONS.inc()
    logger.info(f"WebSocket client connected! Total clients: {len(websocket_clients)}")
    
    try:
        while True:
            # Keep connection alive, listen for client-sent data (if any)
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket exception: {e}")
    finally:
        websocket_clients.remove(websocket)
        ACTIVE_CONNECTIONS.dec()
