"""
QuantForge binary wire protocol (Python side).

This is the exact mirror of shared/cpp/WireProtocol.hpp. Any change to the
struct layouts there MUST be reflected here. Both sides are little-endian with
1-byte packing. Prices travel as integer ticks (fixed-point), never floats.
"""

import struct

# Fixed-point scale for on-the-wire prices (must equal wire::PRICE_SCALE in C++).
PRICE_SCALE = 100

# Action bytes carried in the order packet.
ACTION_LIMIT = b"L"
ACTION_MARKET = b"M"
ACTION_CANCEL = b"C"

# Gateway -> engine:  id, symbol[16], side, action, price_ticks(int64), quantity
ORDER_FMT = "<Q16sccqQ"
ORDER_SIZE = struct.calcsize(ORDER_FMT)

# Engine -> gateway:  order_id, symbol[16], side, status, price_ticks(int64),
#                     last_qty, cum_qty, rem_qty, timestamp, reject_reason[64]
REPORT_FMT = "<Q16sccqQQQQ64s"
REPORT_SIZE = struct.calcsize(REPORT_FMT)


def to_ticks(price: float) -> int:
    """Convert a decimal price to integer ticks."""
    return int(round(price * PRICE_SCALE))


def to_price(ticks: int) -> float:
    """Convert integer ticks back to a decimal price."""
    return ticks / PRICE_SCALE


def pack_order(order_id: int, symbol: str, side: str, action: bytes,
               price: float, quantity: int) -> bytes:
    return struct.pack(
        ORDER_FMT,
        order_id,
        symbol.encode("utf-8")[:16],
        side.encode("utf-8"),
        action,
        to_ticks(price),
        quantity,
    )


def pack_cancel(order_id: int, symbol: str) -> bytes:
    # Side is irrelevant for a cancel; the engine resolves it from its book.
    return struct.pack(
        ORDER_FMT, order_id, symbol.encode("utf-8")[:16], b"B", ACTION_CANCEL, 0, 0
    )


def unpack_report(packet: bytes) -> dict:
    f = struct.unpack(REPORT_FMT, packet)
    return {
        "order_id": f[0],
        "symbol": f[1].decode("utf-8", "ignore").rstrip("\x00"),
        "side": f[2].decode("utf-8", "ignore"),
        "status": f[3].decode("utf-8", "ignore"),
        "price": to_price(f[4]),
        "last_quantity": f[5],
        "cumulative_quantity": f[6],
        "remaining_quantity": f[7],
        "timestamp": f[8],
        "reject_reason": f[9].decode("utf-8", "ignore").rstrip("\x00"),
    }
