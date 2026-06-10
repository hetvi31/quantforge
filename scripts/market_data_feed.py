"""
Real-time market data feed powered by yfinance.

Drop-in replacement for market_simulator.py that anchors prices to live
market data instead of an unconstrained random walk.

How it works
------------
1. At startup (and every --fetch-interval seconds) prices are refreshed
   from yfinance using the last 1-minute bar — giving a real anchor price.
2. Between fetches the script adds tiny microstructure noise (configurable)
   so the order book doesn't appear frozen between API calls.
3. Each tick is packed into the same binary struct as market_simulator.py
   and sent over UDP to the feed handler, which publishes it to Redis.

Usage
-----
# Point at the feed handler (Docker):
python scripts/market_data_feed.py feed-handler

# Point at localhost (local dev):
python scripts/market_data_feed.py

# Override interval and tick rate:
python scripts/market_data_feed.py localhost --fetch-interval 10 --tick-rate 0.05

The script also accepts --symbols to override the default set:
python scripts/market_data_feed.py --symbols BTCUSDT ETHUSDT
"""

import argparse
import socket
import struct
import sys
import time
import random
import logging

logging.basicConfig(level=logging.INFO, format="[DataFeed] %(message)s")
log = logging.getLogger(__name__)

try:
    import yfinance as yf
    _HAS_YFINANCE = True
except ImportError:
    _HAS_YFINANCE = False
    log.warning("yfinance not installed — falling back to random walk.")
    log.warning("Install it with:  pip install yfinance")

# ---------------------------------------------------------------------------
# Symbol / price configuration
# ---------------------------------------------------------------------------

# QuantForge symbol (bytes, padded to 16) → yfinance ticker
_SYMBOL_MAP: dict[bytes, str] = {
    b"BTCUSDT": "BTC-USD",
    b"ETHUSDT": "ETH-USD",
    b"SOLUSDT": "SOL-USD",
    b"NIFTY":   "^NSEI",
}

# Sensible seed prices used before the first yfinance fetch
_SEED_PRICES: dict[bytes, float] = {
    b"BTCUSDT": 62000.00,
    b"ETHUSDT": 3100.00,
    b"SOLUSDT": 150.00,
    b"NIFTY":   22500.00,
}

# Live prices — updated by _refresh_prices()
_live_prices: dict[bytes, float] = dict(_SEED_PRICES)

# Binary struct that matches feed_handler/src/main.cpp RawTick
#   char symbol[16], double price, uint64 qty, uint64 timestamp, char side
_STRUCT_FMT = "<16sdQQc"


# ---------------------------------------------------------------------------
# yfinance helpers
# ---------------------------------------------------------------------------

def _refresh_prices(symbols: list[bytes]) -> None:
    """Fetch the latest close price for each symbol from yfinance."""
    if not _HAS_YFINANCE:
        return
    for sym_bytes in symbols:
        yf_sym = _SYMBOL_MAP.get(sym_bytes)
        if yf_sym is None:
            continue
        try:
            ticker = yf.Ticker(yf_sym)
            # fast_info is a lightweight call; falls back to history if needed
            price = None
            try:
                price = ticker.fast_info.last_price
            except Exception:
                pass
            if not price or price <= 0:
                hist = ticker.history(period="1d", interval="1m", auto_adjust=True)
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
            if price and price > 0:
                old = _live_prices.get(sym_bytes, 0)
                _live_prices[sym_bytes] = float(price)
                sym_str = sym_bytes.rstrip(b"\x00").decode()
                if old:
                    pct = (float(price) - old) / old * 100
                    log.info(f"{sym_str} -> {price:.4f}  ({pct:+.2f}% vs last fetch)")
                else:
                    log.info(f"{sym_str} -> {price:.4f}  (initial fetch)")
        except Exception as exc:
            log.warning(f"Could not fetch {yf_sym}: {exc}")


# ---------------------------------------------------------------------------
# Main feed loop
# ---------------------------------------------------------------------------

def run_feed(
    host: str = "localhost",
    port: int = 9002,
    symbols: list[bytes] | None = None,
    fetch_interval: float = 5.0,
    tick_rate: float = 0.1,
    noise_pct: float = 0.02,
) -> None:
    """
    Stream market ticks over UDP.

    host           : feed handler hostname or IP.
    port           : UDP port (must match feed_handler, default 9002).
    symbols        : list of 16-byte-padded symbol keys to stream.
    fetch_interval : seconds between yfinance price refreshes.
    tick_rate      : seconds between UDP ticks (0.1 = 10 ticks/s).
    noise_pct      : max ±% noise added between real-data fetches (0.02 = 0.02%).
    """
    if symbols is None:
        symbols = list(_SYMBOL_MAP.keys())

    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror:
        ip = "127.0.0.1"

    sym_names = [s.rstrip(b"\x00").decode() for s in symbols]
    log.info(f"Starting -> {ip}:{port}  symbols={sym_names}")
    log.info(f"fetch_interval={fetch_interval}s  tick_rate={tick_rate}s  noise=+/-{noise_pct}%")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    last_fetch: float = 0.0

    # Initial fetch so the first ticks carry real prices
    _refresh_prices(symbols)
    last_fetch = time.time()

    while True:
        now = time.time()

        if now - last_fetch >= fetch_interval:
            _refresh_prices(symbols)
            last_fetch = now

        sym = random.choice(symbols)
        base = _live_prices.get(sym, _SEED_PRICES.get(sym, 1.0))

        # Microstructure noise: very small random walk around the real anchor
        noise = random.uniform(-noise_pct / 100.0, noise_pct / 100.0)
        price = base * (1.0 + noise)

        qty = random.randint(1, 15)
        timestamp = int(time.time() * 1000)
        side = random.choice([b"B", b"A"])

        packet = struct.pack(_STRUCT_FMT, sym, price, qty, timestamp, side)
        try:
            sock.sendto(packet, (ip, port))
        except Exception as exc:
            log.error(f"UDP send error: {exc}")

        time.sleep(tick_rate)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_symbol(s: str) -> bytes:
    """Convert a symbol string to a 16-byte padded key."""
    encoded = s.upper().encode("ascii")[:16]
    # Find the matching key in _SYMBOL_MAP
    for key in _SYMBOL_MAP:
        if key.rstrip(b"\x00") == encoded:
            return key
    # Unknown symbol — pad to 16 bytes and add to live prices
    padded = encoded.ljust(16, b"\x00")
    _SYMBOL_MAP[padded] = s.upper()  # forward as-is to yfinance
    _live_prices[padded] = 100.0
    return padded


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Real-time market data feed (yfinance → UDP → feed handler)"
    )
    parser.add_argument("host", nargs="?", default="localhost",
                        help="Feed handler host (default: localhost)")
    parser.add_argument("--port", type=int, default=9002,
                        help="UDP port (default: 9002)")
    parser.add_argument("--symbols", nargs="+", default=None,
                        help="Symbols to stream, e.g. BTCUSDT ETHUSDT")
    parser.add_argument("--fetch-interval", type=float, default=5.0,
                        help="Seconds between yfinance refreshes (default: 5)")
    parser.add_argument("--tick-rate", type=float, default=0.1,
                        help="Seconds between UDP ticks (default: 0.1 = 10/s)")
    parser.add_argument("--noise-pct", type=float, default=0.02,
                        help="Max ±%% noise between refreshes (default: 0.02)")
    args = parser.parse_args()

    chosen_symbols = (
        [_parse_symbol(s) for s in args.symbols] if args.symbols
        else list(_SYMBOL_MAP.keys())
    )

    try:
        run_feed(
            host=args.host,
            port=args.port,
            symbols=chosen_symbols,
            fetch_interval=args.fetch_interval,
            tick_rate=args.tick_rate,
            noise_pct=args.noise_pct,
        )
    except KeyboardInterrupt:
        log.info("Stopped.")
