"""Unit tests for the binary wire protocol (no database / network needed)."""
import struct

from app import protocol as p


def test_struct_sizes_match_cpp():
    # Must match shared/cpp/WireProtocol.hpp packed layouts exactly.
    assert p.ORDER_SIZE == 42
    assert p.REPORT_SIZE == 130


def test_tick_conversion_roundtrip():
    assert p.to_ticks(50000.00) == 5000000
    assert p.to_price(5000000) == 50000.00
    assert p.to_ticks(62000.55) == 6200055
    assert p.to_price(6200055) == 62000.55


def test_pack_order_layout():
    pkt = p.pack_order(7, "BTCUSDT", "B", p.ACTION_LIMIT, 62000.50, 5)
    assert len(pkt) == p.ORDER_SIZE
    oid, sym, side, action, price_ticks, qty = struct.unpack(p.ORDER_FMT, pkt)
    assert oid == 7
    assert sym.rstrip(b"\x00") == b"BTCUSDT"
    assert side == b"B" and action == p.ACTION_LIMIT
    assert price_ticks == 6200050 and qty == 5


def test_pack_cancel_uses_cancel_action():
    pkt = p.pack_cancel(99, "ETHUSDT")
    _, _, _, action, _, qty = struct.unpack(p.ORDER_FMT, pkt)
    assert action == p.ACTION_CANCEL
    assert qty == 0


def test_unpack_report():
    raw = struct.pack(p.REPORT_FMT, 7, b"BTCUSDT", b"B", b"F", 6200050, 5, 5, 0, 1234, b"")
    d = p.unpack_report(raw)
    assert d["order_id"] == 7
    assert d["symbol"] == "BTCUSDT"
    assert d["side"] == "B" and d["status"] == "F"
    assert d["price"] == 62000.50
