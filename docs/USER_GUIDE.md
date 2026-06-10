# QuantForge — Complete User Guide

This guide explains everything you need to get QuantForge running, understand what
each part does, and use every feature from placing your first order to running a
backtest with real market data.

---

## Table of Contents

1. [What is QuantForge?](#1-what-is-quantforge)
2. [System Overview](#2-system-overview)
3. [Prerequisites](#3-prerequisites)
4. [Environment Setup](#4-environment-setup)
5. [Running with Docker (Recommended)](#5-running-with-docker-recommended)
6. [The Trading Terminal — Panel by Panel](#6-the-trading-terminal--panel-by-panel)
7. [Placing Orders](#7-placing-orders)
8. [The AI Research Pipeline](#8-the-ai-research-pipeline)
9. [Market Data — Simulated vs Real (yfinance)](#9-market-data--simulated-vs-real-yfinance)
10. [Running Backtests with Real Data](#10-running-backtests-with-real-data)
11. [Monitoring with Grafana & Prometheus](#11-monitoring-with-grafana--prometheus)
12. [REST API Reference](#12-rest-api-reference)
13. [Running Tests](#13-running-tests)
14. [Local Development (without Docker)](#14-local-development-without-docker)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. What is QuantForge?

QuantForge is a **simulated electronic-trading platform** that mirrors the architecture of a real
low-latency trading venue. It is designed for learning and portfolio demonstration — it does
**not** connect to any real exchange or handle real money.

It has five main components that talk to each other:

| Component | Language | What it does |
|---|---|---|
| **Matching Engine** | C++ | Receives orders over TCP, matches them with price-time priority, sends back execution reports |
| **Feed Handler** | C++ | Receives market-data ticks over UDP and publishes them to Redis |
| **API Gateway** | Python / FastAPI | Pre-trade risk, order routing, REST API, WebSocket fan-out, Postgres persistence |
| **AI Research Pipeline** | Python | Analyses sentiment, proposes trades, gates them through rule-based risk, and submits them |
| **Web Terminal** | React / TypeScript | Bloomberg-style browser UI with live order book, chart, portfolio, and AI console |

---

## 2. System Overview

```
   Market Data Source
   (yfinance or simulator)
          │ UDP :9002
          ▼
   Feed Handler (C++)  ─── PUBLISH market_data ──▶  Redis
                                                        │
   Web Terminal ◀──── WebSocket ────┐                  │ SUBSCRIBE
        │                          │                   ▼
        └─── REST (X-API-Key) ───▶ API Gateway ◀─────────────────────────────┐
                                     │   │                                    │
                          binary TCP │   │ SQL        Matching Engine (C++)   │
                          :9001      │   ▼            ──── PUBLISH order_book ┘
                                  ┌──▼  PostgreSQL
                                  │  Matching Engine
                                  └──▶  exec reports ──▶ API Gateway
                                  
   AI Research ─── REST (X-API-Key) ──▶ API Gateway

   Prometheus ◀─── scrape ─── API Gateway
   Grafana    ◀─── query  ─── Prometheus
```

---

## 3. Prerequisites

### For Docker (easiest path)

| Requirement | Minimum version |
|---|---|
| Docker Desktop | 24+ |
| Docker Compose (included with Desktop) | v2.20+ |
| 4 GB free RAM | — |
| 2 GB free disk | — |

### For local development

| Requirement | Version |
|---|---|
| CMake | 3.22+ |
| GCC or Clang | C++20 capable (GCC 11+ / Clang 14+) |
| Python | 3.11+ |
| Node.js | 20+ |

### For real market data (yfinance)

```bash
pip install yfinance
```

---

## 4. Environment Setup

**This is the only mandatory configuration step.**

```bash
cp .env.example .env
```

Open `.env` and change the three **must-change** values:

```dotenv
# MUST CHANGE — used by gateway and AI service
API_KEY=your-secret-key-here

# MUST CHANGE — must match API_KEY so the terminal can place orders
VITE_API_KEY=your-secret-key-here

# MUST CHANGE — Grafana admin password
GRAFANA_PASSWORD=your-grafana-password
```

Everything else has sensible defaults for local Docker use. If you want the AI pipeline
to use a real LLM instead of the heuristic fallback, also set:

```dotenv
GROQ_API_KEY=gsk_...          # get a free key at console.groq.com
GROQ_MODEL=llama-3.1-8b-instant  # fast and free tier
```

---

## 5. Running with Docker (Recommended)

### Start everything

```bash
docker compose up --build
```

The first build takes 2–4 minutes (it compiles the C++ engine and installs Python/Node
deps). Subsequent starts are fast because the images are cached.

### URLs once running

| Service | URL | Notes |
|---|---|---|
| **Trading Terminal** | http://localhost:3001 | Main UI |
| **API Gateway docs** | http://localhost:8000/docs | Interactive REST docs (Swagger) |
| **Gateway health** | http://localhost:8000/health | JSON health check |
| **Prometheus** | http://localhost:9090 | Raw metrics |
| **Grafana** | http://localhost:3000 | Dashboards (admin / your GRAFANA_PASSWORD) |

### Start market data

The Docker stack runs the matching engine and feed handler, but does **not** automatically
stream market ticks. Open a separate terminal and run one of:

```bash
# Option A — Real prices from yfinance (recommended)
python scripts/market_data_feed.py localhost

# Option B — Random walk (no internet required)
python scripts/market_simulator.py localhost
```

Leave that terminal running while you use the terminal UI.

### Run the end-to-end test suite

```bash
python scripts/e2e_integration_test.py
```

This places real orders through the full stack, checks cash conservation, verifies
cancel works, and asserts that auth is enforced.

### Stop everything

```bash
docker compose down          # stops containers, keeps data volumes
docker compose down -v       # stops and deletes all data (fresh start)
```

---

## 6. The Trading Terminal — Panel by Panel

Open http://localhost:3001 in your browser.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ QUANTFORGE // TRADING TERMINAL  [symbol] ··· ENGINE LIVE  FEED CONNECTED   │  ← Command Bar
│             LATENCY 145 µs   14:32:07              [KILL SWITCH]            │
├─────────────────────────────────────────────────────────────────────────────┤
│ BTCUSDT  LAST 62104.50  CHG +104.50 (+0.17%)  BID 62100  ASK 62108         │  ← Ticker Strip
├───────────────────┬─────────────────────────────┬────────────────────────── │
│  Order Ticket     │                             │  AI Research Pipeline     │
│  ─────────────    │   Price Chart               │  ─────────────────────    │
│  Type: [Limit]    │   (live ticks)              │  Symbol input             │
│        [Market]   │                             │  News text input          │
│  Price: 62000     │                             │  [Run Agent Pipeline]     │
│  Qty:   5         │                             │                           │
│  [BUY] [SELL]     ├─────────────────────────────│  ── Pipeline trace ──     │
│                   │   Portfolio                 │  Market Analyst           │
│  Order Book       │   Cash: $100,000            │  Portfolio Manager        │
│  ─────────────    │   Positions: —              │  Risk Analyst             │
│  ASK 62108  30    │   Active Orders             │  Execution Agent          │
│  ASK 62104  12    │                             │                           │
│  ─ SPREAD ─       │                             │                           │
│  BID 62100  25    │                             │                           │
│  BID 62095  18    │                             │                           │
└───────────────────┴─────────────────────────────┴───────────────────────────┘
│ QUANTFORGE v2.0  SYM BTCUSDT  BOOK 5×5  MSG/S 18  ENGINE RTT 145µs         │  ← Status Bar
└─────────────────────────────────────────────────────────────────────────────┘
```

### Command Bar (top strip)

- **Symbol selector** — switch between BTCUSDT, ETHUSDT, SOLUSDT, NIFTY
- **ENGINE LIVE / DOWN** — green = matching engine reachable; red = disconnected
- **FEED CONNECTED** — WebSocket to gateway; reconnects automatically if dropped
- **LATENCY** — real measured round-trip time from the moment your order is sent to
  when the engine acknowledges it. This is a real nanosecond timer, not simulated.
- **Clock** — live UTC time
- **KILL SWITCH** — cancels every open order in one click (prompts for confirmation)

### Ticker Strip

Shows last price, session change (+ or −), best bid, best ask, and spread for the
selected symbol. Updates on every market tick.

### Order Ticket (left panel, top)

Where you submit orders. See [§7 Placing Orders](#7-placing-orders).

### Order Book (left panel, bottom)

The **real** order book from the matching engine — not a fabricated one. The engine
publishes authoritative depth snapshots to Redis after every match; the gateway
forwards them over WebSocket.

- Ask levels (red) — prices sellers are willing to accept, best first
- Bid levels (green) — prices buyers are willing to pay, best first

### Chart (centre panel, top)

Candlestick chart of market data ticks for the selected symbol. Data comes from the
feed handler (UDP ticks → Redis → WebSocket). Keeps the last 240 ticks in memory.

### Portfolio (centre panel, bottom)

- **Cash** — current account balance (starts at $100,000)
- **Positions** — open positions with average entry price
- **Active Orders** — resting limit orders with a Cancel button per order

### AI Research Pipeline (right panel)

See [§8 The AI Research Pipeline](#8-the-ai-research-pipeline).

### Status Bar (bottom)

- **BOOK N×M** — number of bid levels × ask levels in the current order book
- **MSG/S** — WebSocket messages per second (shows how busy the feed is)
- **ENGINE RTT** — same as the latency readout in the command bar

---

## 7. Placing Orders

### Limit Order

1. Make sure the symbol selector shows the instrument you want.
2. In the Order Ticket, click **Limit** (the default).
3. Enter the **Limit Price** — the price you're willing to pay (buy) or accept (sell).
4. Enter the **Quantity**.
5. Click **Buy / Long** or **Sell / Short**.

A limit buy rests in the order book until a matching sell arrives at or below your
price. A limit sell rests until a matching buy arrives at or above your price.

### Market Order

1. Click **Market** in the Order Ticket.
2. Enter the **Quantity** (price input disappears — market orders execute immediately
   at the best available price).
3. Click **Buy / Long** or **Sell / Short**.

A market order sweeps the book: it matches against all resting limit orders from best
price inward until fully filled. If the book is thin, part of the order may be
cancelled unfilled.

### Cancelling an Order

Find the order in the **Active Orders** table in the Portfolio panel and click the
**×** button next to it.

### Kill Switch

The red **KILL SWITCH** button in the top-right cancels **all** open orders at once.
Useful in an emergency. It asks for confirmation before sending.

### Risk Limits (pre-trade checks)

The gateway enforces these checks before any order reaches the engine:

| Check | Limit | What happens if breached |
|---|---|---|
| Order size | 500 units max | Rejected with reason |
| Cash / buying power | Must have enough cash for a buy order | Rejected |
| Position size | ±1000 units per symbol | Rejected |
| Daily drawdown | Account must not be down >10% from $100k | Rejected |

A rejected order shows a red flash in the Order Ticket with the rejection reason.

---

## 8. The AI Research Pipeline

The AI panel lets you run a 4-stage research pipeline on any instrument.

### How it works

```
You provide: symbol + news text
         │
         ▼
  ┌─────────────────────────────────────────────────────┐
  │ Stage 1: Market Analyst Agent                       │
  │ Scores the news text for sentiment (-1.0 to +1.0).  │
  │ If GROQ_API_KEY is set: uses Groq LLM.             │
  │ Otherwise: heuristic word-count scorer (fast,       │
  │ no internet required).                              │
  │ Output: BULLISH / BEARISH / NEUTRAL + score         │
  └────────────────────────┬────────────────────────────┘
                           ▼
  ┌─────────────────────────────────────────────────────┐
  │ Stage 2: Portfolio Manager Agent                    │
  │ Maps the bias to an action and quantity.            │
  │ BULLISH → BUY 10, BEARISH → SELL 10, NEUTRAL → HOLD│
  └────────────────────────┬────────────────────────────┘
                           ▼
  ┌─────────────────────────────────────────────────────┐
  │ Stage 3: Risk Analyst Agent                         │
  │ Checks the proposed size against a hard cap (100).  │
  │ If size ≤ 100: APPROVED. Otherwise: BLOCKED.        │
  └────────────────────────┬────────────────────────────┘
                           ▼
  ┌─────────────────────────────────────────────────────┐
  │ Stage 4: Execution Agent                            │
  │ If approved: submits a MARKET order to the gateway  │
  │ using the server-side API key.                      │
  │ If blocked or HOLD: SKIPPED (no order placed).      │
  └─────────────────────────────────────────────────────┘
```

### Step-by-step

1. Change the **Symbol** input if needed (defaults to the symbol selected in the main
   terminal).
2. Replace the example text in **News / Sentiment Input** with real headlines or any
   financial text about the instrument.
3. Click **Run Agent Pipeline**.
4. Each stage result appears in the trace below — agent name, decision badge
   (BULLISH/APPROVED/EXECUTED etc.), and the agent's reasoning text.

### Example inputs

**Bullish example:**
```
Company reports record quarterly profit; revenue surged 40%, guidance raised.
Analysts upgraded to outperform; dividend increased.
```

**Bearish example:**
```
Firm warns of significant earnings shortfall; debt risk elevated.
CEO departure, declining market share, regulatory probe underway.
```

**Neutral example:**
```
Company releases routine product update with minor feature changes.
No material guidance revision. Market reaction muted.
```

### Using a real LLM (Groq)

Set `GROQ_API_KEY` in your `.env`. Groq offers a free tier at https://console.groq.com.
The default model (`llama-3.1-8b-instant`) is fast and free. The terminal shows
`method: llm` in the analyst trace when the LLM is in use.

---

## 9. Market Data — Simulated vs Real (yfinance)

### The problem with the default simulator

`scripts/market_simulator.py` generates a **random walk** starting from seed prices.
After a few minutes the prices bear no relation to real markets. The order book fills
with synthetic orders at synthetic prices.

### Using real market data

`scripts/market_data_feed.py` uses **yfinance** to anchor prices to real market data:

```bash
# Install yfinance if not already installed
pip install yfinance

# Run against a local stack
python scripts/market_data_feed.py

# Run against Docker
python scripts/market_data_feed.py localhost

# Custom refresh rate (fetch from yfinance every 10s, send ticks every 50ms)
python scripts/market_data_feed.py --fetch-interval 10 --tick-rate 0.05

# Only stream Bitcoin and Ethereum
python scripts/market_data_feed.py --symbols BTCUSDT ETHUSDT
```

### How the feed works

1. On startup it fetches the latest price for each symbol from yfinance.
2. Every `--fetch-interval` seconds it re-fetches to update the anchor.
3. Between refreshes it adds very small noise (±0.02% by default) so the chart shows
   movement rather than a flat line.
4. Each tick is packed into the same binary UDP struct as `market_simulator.py`, so the
   feed handler, Redis, and terminal all work identically.

### Symbol mapping

| QuantForge symbol | yfinance ticker | Notes |
|---|---|---|
| BTCUSDT | BTC-USD | Bitcoin vs USD |
| ETHUSDT | ETH-USD | Ethereum vs USD |
| SOLUSDT | SOL-USD | Solana vs USD |
| NIFTY | ^NSEI | NIFTY 50 index |

Crypto prices are available 24/7. `^NSEI` is only available during Indian market hours
(09:15–15:30 IST); outside those hours the last close is used.

---

## 10. Running Backtests with Real Data

The `analytics` module provides a backtest engine and a yfinance data fetcher.

### Install analytics dependencies

```bash
pip install -r analytics/requirements.txt
```

### Fetch historical data

```python
from analytics.data.fetcher import fetch_historical

# 1 year of daily BTC data
df = fetch_historical("BTCUSDT", period="1y", interval="1d")
print(df.head())
#    timestamp        open         high          low        close     volume
# 0 2025-06-10  62000.123  63100.456  61500.789  62800.012  18500000
```

### Run a backtest

```python
from analytics.data.fetcher import fetch_historical
from analytics.backtest.engine import BacktestEngine

# Write a strategy with a generate_signal(bar, position) method
class SimpleMomentum:
    def __init__(self, window=5):
        self.window = window
        self.closes = []

    def generate_signal(self, bar, position):
        self.closes.append(bar["close"])
        if len(self.closes) <= self.window:
            return "HOLD"
        if self.closes[-1] > self.closes[-self.window - 1]:
            return "BUY"
        elif self.closes[-1] < self.closes[-self.window - 1]:
            return "SELL"
        return "HOLD"

# Fetch real data
df = fetch_historical("BTCUSDT", period="1y", interval="1d")

# Run backtest
engine = BacktestEngine(initial_capital=100_000)
result = engine.run(df, SimpleMomentum(window=5))

print(f"Total return:  {result['total_return']*100:.2f}%")
print(f"Sharpe ratio:  {result['sharpe_ratio']:.2f}")
print(f"Max drawdown:  {result['max_drawdown']*100:.2f}%")
print(f"Win rate:      {result['win_rate']*100:.1f}%")
print(f"Total trades:  {result['total_trades']}")
```

### Available metrics

The backtest result dict contains:

| Key | Description |
|---|---|
| `total_return` | Overall P&L as a fraction (0.15 = +15%) |
| `sharpe_ratio` | Annualised Sharpe ratio |
| `sortino_ratio` | Annualised Sortino ratio (penalises downside only) |
| `max_drawdown` | Maximum peak-to-trough drawdown (negative number) |
| `value_at_risk_95` | 1-day 95% VaR |
| `conditional_value_at_risk_95` | Expected loss beyond VaR |
| `win_rate` | Fraction of round-trip trades that were profitable |
| `total_trades` | Number of completed round-trip trades |
| `final_value` | Portfolio value at end |
| `trades` | List of individual trade dicts |
| `equity_curve` | List of portfolio values at each bar |

### Supported periods and intervals

```
period:   1d  5d  1mo  3mo  6mo  1y  2y  5y  max
interval: 1m  2m  5m  15m  30m  60m  1h  1d  1wk  1mo

Note: intervals shorter than 1d only work for the last 60 days.
```

---

## 11. Monitoring with Grafana & Prometheus

### Opening Grafana

1. Go to http://localhost:3000
2. Log in: username `admin`, password = your `GRAFANA_PASSWORD` from `.env`
3. Click **Dashboards** → **QuantForge** to see the pre-provisioned dashboard

### What the dashboard shows

| Panel | Description |
|---|---|
| Orders total | Cumulative orders accepted, broken down by side and type |
| Orders rejected | Orders blocked by pre-trade risk |
| Executions filled | Fills per second |
| Round-trip latency | Histogram of gateway→engine→gateway latency |
| Last order latency | Most recent order round-trip in microseconds |
| Active WebSocket connections | Number of connected browser sessions |

### Prometheus metrics endpoint

All metrics are also available in raw Prometheus format at http://localhost:8000/metrics.

### Key metrics

| Metric | Description |
|---|---|
| `quantforge_orders_total` | Counter, labelled `side` and `type` |
| `quantforge_orders_rejected_total` | Counter |
| `quantforge_executions_total` | Counter |
| `quantforge_order_roundtrip_seconds` | Histogram (real measured latency) |
| `quantforge_last_order_latency_microseconds` | Gauge |
| `quantforge_active_websockets` | Gauge |

---

## 12. REST API Reference

The gateway exposes its API at http://localhost:8000. Interactive docs at `/docs`.

All **write** endpoints require an `X-API-Key` header matching the `API_KEY` in your
`.env`. Read endpoints (portfolio, active orders, health) do not require a key.

### Place an order

```http
POST /api/v1/orders/create
X-API-Key: your-secret-key

{
  "symbol":   "BTCUSDT",
  "side":     "B",          // "B" = buy, "S" = sell
  "type":     "L",          // "L" = limit, "M" = market
  "price":    62000.00,     // ignored for market orders (send 0)
  "quantity": 5
}
```

Response:
```json
{ "status": "SUCCESS", "order_id": 1720000000001 }
```

### Cancel an order

```http
POST /api/v1/orders/cancel
X-API-Key: your-secret-key

{ "symbol": "BTCUSDT", "order_id": 1720000000001 }
```

### Get portfolio

```http
GET /api/v1/portfolio/status
```

```json
{
  "cash": 99500.00,
  "margin": 0.00,
  "positions": [
    { "symbol": "BTCUSDT", "quantity": 1, "average_price": 500.00 }
  ]
}
```

### Get active orders

```http
GET /api/v1/orders/active
```

Returns a list of orders with status `N` (new) or `P` (partially filled).

### Kill switch

```http
POST /api/v1/admin/killswitch
X-API-Key: your-secret-key
```

Cancels all open orders. Response includes how many cancel messages were sent.

### Health check

```http
GET /health
```

```json
{ "status": "ok", "database": true, "matching_engine": true }
```

`status` is `"ok"` when both DB and engine are reachable. `"degraded"` means the engine
is down but the gateway is still running (orders will be queued or rejected).

### WebSocket

Connect to `ws://localhost:8000/ws/live` to receive a stream of JSON messages:

| `type` | When sent | Key fields |
|---|---|---|
| `MARKET_TICK` | Every UDP tick from the feed | `data` (JSON string) with `symbol`, `price`, `quantity`, `side`, `timestamp` |
| `ORDER_BOOK` | After every match (engine publishes) | `data` (JSON string) with `symbol`, `bids`, `asks`, `timestamp` |
| `EXECUTION` | Every execution report | `order_id`, `symbol`, `side`, `status`, `price`, `last_quantity`, `latency_us` |

---

## 13. Running Tests

### C++ unit tests

```bash
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
./build/bin/test_matching
```

Expected output:
```
[Test] Running testLimitOrderMatching... PASSED!
[Test] Running testFIFOAndPricePriority... PASSED!
[Test] Running testOrderCancellation... PASSED!
[Test] Running testMarketOrderSweepsBook... PASSED!
[Test] All C++ OrderBook unit tests passed successfully!
```

### Matching engine benchmark

```bash
./build/bin/bench_matching 1000000
```

This submits 1M orders in-process (no network) and prints latency percentiles.

### Python unit tests (gateway)

```bash
cd gateway
pip install -r requirements.txt
python -m pytest tests -q
```

The test suite covers:
- Wire protocol round-trip and struct size lock
- Pre-trade risk engine (all 9 cases including buying-power)
- Settlement idempotency and double-fill prevention
- Partial fills at the same millisecond getting distinct trade IDs

### End-to-end integration test

Requires the full Docker stack to be running:

```bash
# Start the stack first
docker compose up -d

# Start market data
python scripts/market_data_feed.py &

# Run e2e tests
python scripts/e2e_integration_test.py
```

Tests: matching round-trip, cash conservation, cancel regression, auth enforcement.

---

## 14. Local Development (without Docker)

If you want to modify code and see changes without rebuilding Docker images:

### C++ engine + feed handler

```bash
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build -j

# Start the matching engine (requires Redis on localhost:6379)
./build/bin/quantforge_matching_engine

# Start the feed handler
./build/bin/quantforge_feed_handler
```

### Redis and Postgres (still using Docker)

```bash
docker compose up postgres redis -d
```

### Gateway

```bash
cd gateway
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag watches for file changes and restarts automatically.

### AI research service

```bash
cd ai_research
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

### Terminal

```bash
cd terminal
npm install --legacy-peer-deps
npm run dev
```

The dev server starts at http://localhost:5173 with hot-module reload.

### Market data

```bash
# Real prices
python scripts/market_data_feed.py

# Or random walk
python scripts/market_simulator.py
```

---

## 15. Troubleshooting

### "ENGINE DOWN" badge in the terminal

The gateway cannot reach the matching engine. Check:

```bash
docker compose logs matching-engine
```

Common causes: the engine is still starting (it takes a few seconds to compile on first
run), or Redis was not ready when the engine started.

### Terminal shows no order book or chart

The market data feed is not running. Start it in a separate terminal:

```bash
python scripts/market_data_feed.py localhost   # for Docker
python scripts/market_data_feed.py             # for local dev
```

### "Invalid or missing API key" on order placement

The terminal was built without `VITE_API_KEY`, or the key doesn't match the gateway's
`API_KEY`. A red banner at the top of the terminal also indicates this.

Fix: make sure both values in `.env` match, then rebuild the terminal:

```bash
docker compose up --build terminal
```

### AI pipeline returns "AI service 401"

The `X-API-Key` sent by the terminal doesn't match `API_KEY`. The AI service shares
the same key as the gateway. After updating `.env`, restart both:

```bash
docker compose restart ai-research gateway
```

### yfinance returns empty data

- For `^NSEI` (NIFTY): this ticker only has data during Indian market hours. Outside
  those hours you'll get yesterday's close.
- For crypto: try a longer period — `fetch_historical("BTCUSDT", period="5d")`.
- yfinance sometimes rate-limits; wait 30 seconds and retry.

### Grafana shows "No data"

Prometheus needs at least one order to have been placed before most panels populate.
Place one limit order from the terminal and the panels should start showing data.

### Docker out of disk space

```bash
docker system prune -f       # remove stopped containers and dangling images
docker volume prune -f       # remove unused volumes (DELETES DATABASE DATA)
```

### Resetting the database

```bash
docker compose down -v       # destroys all volumes including pgdata
docker compose up --build    # fresh start with empty database ($100k account seeded)
```
