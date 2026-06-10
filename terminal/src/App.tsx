import React, { useState, useEffect, useCallback, useRef } from 'react';
import { OrderBook } from './components/OrderBook';
import { Portfolio } from './components/Portfolio';
import { Chart } from './components/Chart';
import { AIChatConsole } from './components/AIChatConsole';
import { API_BASE, WS_URL, SYMBOLS, apiGet, apiPost, quoteCcy, API_KEY_MISSING } from './config';

interface BookLevel { price: number; qty: number; }
interface Position { symbol: string; quantity: number; average_price: number; }
interface ActiveOrder {
  order_id: number; symbol: string; side: string; type: string;
  price: number; quantity: number; remaining_quantity: number; status: string; created_at: string;
}
type WsStatus = 'connecting' | 'connected' | 'disconnected';

export const App: React.FC = () => {
  const [symbol, setSymbol] = useState<string>('BTCUSDT');
  const [bids, setBids] = useState<BookLevel[]>([]);
  const [asks, setAsks] = useState<BookLevel[]>([]);
  const [ticks, setTicks] = useState<{ price: number; timestamp: number }[]>([]);
  const [lastPrice, setLastPrice] = useState<number>(0);
  const [sessionOpen, setSessionOpen] = useState<number>(0);

  const [cash, setCash] = useState(100000);
  const [margin, setMargin] = useState(0);
  const [positions, setPositions] = useState<Position[]>([]);
  const [activeOrders, setActiveOrders] = useState<ActiveOrder[]>([]);

  const [wsStatus, setWsStatus] = useState<WsStatus>('connecting');
  const [engineUp, setEngineUp] = useState<boolean>(false);
  const [latencyUs, setLatencyUs] = useState<number | null>(null);
  const [msgRate, setMsgRate] = useState<number>(0);
  const [clock, setClock] = useState<string>('');

  const [orderQty, setOrderQty] = useState(5);
  const [orderPrice, setOrderPrice] = useState(50000);
  const [orderType, setOrderType] = useState<'L' | 'M'>('L');
  const [notice, setNotice] = useState<{ kind: 'err' | 'ok'; text: string } | null>(null);

  const msgCounter = useRef(0);
  const symbolRef = useRef(symbol);
  symbolRef.current = symbol;
  // Tick buffering: WS messages accumulate here; flushed to React state at 4 Hz
  // so the chart re-renders at most 4×/s instead of 10-20×/s.
  const tickBufferRef = useRef<{ price: number; timestamp: number }[]>([]);
  const pendingPriceRef = useRef<number>(0);

  const refreshPortfolio = useCallback(async () => {
    try {
      const p = await apiGet<{ cash: number; margin: number; positions: Position[] }>(
        '/api/v1/portfolio/status');
      setCash(p.cash); setMargin(p.margin); setPositions(p.positions);
      const o = await apiGet<ActiveOrder[]>('/api/v1/orders/active');
      setActiveOrders(o);
    } catch { /* gateway briefly unavailable */ }
  }, []);

  // Clock + message-rate sampler.
  useEffect(() => {
    const t = setInterval(() => {
      setClock(new Date().toLocaleTimeString('en-GB'));
      setMsgRate(msgCounter.current);
      msgCounter.current = 0;
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // Flush buffered ticks to state at 4 Hz — reduces chart render frequency.
  useEffect(() => {
    const id = setInterval(() => {
      const buf = tickBufferRef.current.splice(0);
      if (buf.length === 0) return;
      setLastPrice(pendingPriceRef.current);
      setTicks((prev) => {
        const next = [...prev, ...buf];
        return next.length > 240 ? next.slice(next.length - 240) : next;
      });
    }, 250);
    return () => clearInterval(id);
  }, []);

  // Health poll for engine/db status.
  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const r = await fetch(`${API_BASE}/health`);
        const j = await r.json();
        if (alive) setEngineUp(Boolean(j.matching_engine));
      } catch { if (alive) setEngineUp(false); }
    };
    poll();
    const t = setInterval(poll, 5000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  // WebSocket: real order book, market ticks, executions, measured latency.
  useEffect(() => {
    let ws: WebSocket;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      setWsStatus('connecting');
      ws = new WebSocket(WS_URL);

      ws.onopen = () => setWsStatus('connected');

      ws.onmessage = (event) => {
        msgCounter.current += 1;
        const msg = JSON.parse(event.data);

        if (msg.type === 'MARKET_TICK') {
          const tick = JSON.parse(msg.data);
          if (tick.symbol !== symbolRef.current) return;
          pendingPriceRef.current = tick.price;
          setSessionOpen((o) => (o === 0 ? tick.price : o));
          tickBufferRef.current.push({ price: tick.price, timestamp: tick.timestamp });
        } else if (msg.type === 'ORDER_BOOK') {
          const book = JSON.parse(msg.data);
          if (book.symbol !== symbolRef.current) return;
          setBids((book.bids as [number, number][]).map(([price, qty]) => ({ price, qty })));
          setAsks((book.asks as [number, number][]).map(([price, qty]) => ({ price, qty })));
        } else if (msg.type === 'EXECUTION') {
          if (typeof msg.latency_us === 'number') setLatencyUs(msg.latency_us);
          refreshPortfolio();
        }
      };

      ws.onclose = () => { setWsStatus('disconnected'); retry = setTimeout(connect, 2500); };
      ws.onerror = () => ws.close();
    };

    connect();
    refreshPortfolio();
    return () => { clearTimeout(retry); if (ws) ws.close(); };
  }, [refreshPortfolio]);

  const handleSymbolChange = (next: string) => {
    setSymbol(next);
    tickBufferRef.current = [];
    pendingPriceRef.current = 0;
    setBids([]); setAsks([]); setTicks([]); setLastPrice(0); setSessionOpen(0);
    if (next === 'BTCUSDT') setOrderPrice(50000);
    else if (next === 'ETHUSDT') setOrderPrice(3000);
    else if (next === 'SOLUSDT') setOrderPrice(150);
    else setOrderPrice(22000);
  };

  const flash = (kind: 'err' | 'ok', text: string) => {
    setNotice({ kind, text });
    setTimeout(() => setNotice(null), 4000);
  };

  const placeOrder = async (side: 'B' | 'S') => {
    try {
      const r = await apiPost<{ order_id: number }>('/api/v1/orders/create', {
        symbol, side, type: orderType,
        price: orderType === 'M' ? 0 : orderPrice, quantity: orderQty,
      });
      flash('ok', `${side === 'B' ? 'BUY' : 'SELL'} ${orderQty} ${symbol} sent · #${r.order_id}`);
      refreshPortfolio();
    } catch (e) {
      flash('err', (e as Error).message);
    }
  };

  const cancelOrder = async (orderId: number, ordSymbol: string) => {
    try { await apiPost('/api/v1/orders/cancel', { order_id: orderId, symbol: ordSymbol }); refreshPortfolio(); }
    catch (e) { flash('err', (e as Error).message); }
  };

  const killSwitch = async () => {
    if (!confirm('Trigger KILL SWITCH? This cancels all working orders.')) return;
    try {
      const r = await apiPost<{ cancelled_orders_sent: number }>('/api/v1/admin/killswitch', {});
      flash('ok', `Kill switch sent · ${r.cancelled_orders_sent} cancels`);
      refreshPortfolio();
    } catch (e) { flash('err', (e as Error).message); }
  };

  const change = sessionOpen > 0 ? lastPrice - sessionOpen : 0;
  const changePct = sessionOpen > 0 ? (change / sessionOpen) * 100 : 0;
  const bestBid = bids.length ? bids[0].price : 0;
  const bestAsk = asks.length ? asks[0].price : 0;
  const spread = bestBid && bestAsk ? bestAsk - bestBid : 0;
  const ccy = quoteCcy(symbol);

  return (
    <div className="app">
      {/* Top bar: command bar + optional config-error banner — single grid cell */}
      <div>
      <div className="cmdbar">
        <div className="brand">QUANTFORGE <span>// TRADING TERMINAL</span></div>
        <select className="field" style={{ width: 130, padding: '3px 6px' }}
                value={symbol} onChange={(e) => handleSymbolChange(e.target.value)}>
          {SYMBOLS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <div className="cmdbar__spacer" />
        <span className="chip">
          <span className={`dot ${engineUp ? 'dot--up' : 'dot--down'}`} />ENGINE <b>{engineUp ? 'LIVE' : 'DOWN'}</b>
        </span>
        <span className="chip">
          <span className={`dot ${wsStatus === 'connected' ? 'dot--up' : wsStatus === 'connecting' ? 'dot--warn' : 'dot--down'}`} />
          FEED <b>{wsStatus.toUpperCase()}</b>
        </span>
        <span className="chip">LATENCY <b className="amber">{latencyUs != null ? `${latencyUs.toFixed(0)} µs` : '—'}</b></span>
        <span className="chip"><b>{clock}</b></span>
        <button className="btn--kill" onClick={killSwitch}>KILL SWITCH</button>
      </div>

      {/* Config-error banner — shown when VITE_API_KEY was not set at build time */}
      {API_KEY_MISSING && (
        <div style={{
          background: '#7c1a1a', color: '#ffb3b3', fontSize: 11, padding: '4px 12px',
          borderBottom: '1px solid #a33', letterSpacing: '0.04em',
        }}>
          CONFIGURATION ERROR — VITE_API_KEY is not set. Mutating actions (orders, cancels) will
          be rejected. Set VITE_API_KEY in your .env and rebuild.
        </div>
      )}

      </div>{/* end top bar wrapper */}

      {/* Ticker strip */}
      <div className="ticker">
        <span className="ticker__sym">{symbol}</span>
        <span className="ticker__item">LAST <b>{lastPrice ? lastPrice.toFixed(2) : '—'}</b></span>
        <span className="ticker__item">CHG{' '}
          <b className={change >= 0 ? 'up' : 'down'}>
            {sessionOpen ? `${change >= 0 ? '+' : ''}${change.toFixed(2)} (${changePct.toFixed(2)}%)` : '—'}
          </b>
        </span>
        <span className="ticker__item">BID <b className="up">{bestBid ? bestBid.toFixed(2) : '—'}</b></span>
        <span className="ticker__item">ASK <b className="down">{bestAsk ? bestAsk.toFixed(2) : '—'}</b></span>
        <span className="ticker__item">SPREAD <b>{spread ? spread.toFixed(2) : '—'}</b></span>
        <span className="ticker__item">CCY <b>{ccy}</b></span>
      </div>

      {/* Workspace */}
      <div className="workspace">
        {/* Left: order ticket + depth */}
        <div className="col">
          <div className="panel" style={{ flex: '0 0 auto' }}>
            <div className="panel__head"><span className="panel__title">Order Ticket</span></div>
            <div className="panel__body panel__body--pad" style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
              <div>
                <span className="label">Type</span>
                <div className="seg">
                  <button className={orderType === 'L' ? 'active' : ''} onClick={() => setOrderType('L')}>Limit</button>
                  <button className={orderType === 'M' ? 'active' : ''} onClick={() => setOrderType('M')}>Market</button>
                </div>
              </div>
              {orderType === 'L' && (
                <div>
                  <span className="label">Limit Price ({ccy})</span>
                  <input className="field" type="number" value={orderPrice}
                         onChange={(e) => setOrderPrice(parseFloat(e.target.value) || 0)} />
                </div>
              )}
              <div>
                <span className="label">Quantity</span>
                <input className="field" type="number" value={orderQty}
                       onChange={(e) => setOrderQty(parseInt(e.target.value) || 0)} />
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn--buy" style={{ flex: 1 }} onClick={() => placeOrder('B')}>Buy / Long</button>
                <button className="btn btn--sell" style={{ flex: 1 }} onClick={() => placeOrder('S')}>Sell / Short</button>
              </div>
              {notice && (
                <div className={notice.kind === 'err' ? 'down' : 'up'}
                     style={{ fontSize: 10.5, borderTop: '1px solid var(--border)', paddingTop: 6 }}>
                  {notice.text}
                </div>
              )}
            </div>
          </div>
          <div className="panel" style={{ flex: 1 }}>
            <OrderBook symbol={symbol} ccy={ccy} bids={bids} asks={asks} />
          </div>
        </div>

        {/* Center: chart + portfolio */}
        <div className="col">
          <Chart symbol={symbol} ticks={ticks} />
          <Portfolio cash={cash} margin={margin} positions={positions}
                     activeOrders={activeOrders} onCancelOrder={cancelOrder} />
        </div>

        {/* Right: AI console */}
        <div className="col">
          <AIChatConsole defaultSymbol={symbol} onOrderPlaced={refreshPortfolio} />
        </div>
      </div>

      {/* Status bar */}
      <div className="statusbar">
        <span>QUANTFORGE v2.0</span>
        <span>SYM <b>{symbol}</b></span>
        <span>BOOK <b>{bids.length}×{asks.length}</b></span>
        <span>MSG/S <b>{msgRate}</b></span>
        <span className="seg-r">ENGINE RTT <b>{latencyUs != null ? `${latencyUs.toFixed(0)}µs` : 'n/a'}</b></span>
        <span>FEED <b>{wsStatus.toUpperCase()}</b></span>
      </div>
    </div>
  );
};

export default App;
