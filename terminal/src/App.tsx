import React, { useState, useEffect, useCallback } from 'react';
import { OrderBook } from './components/OrderBook';
import { Portfolio } from './components/Portfolio';
import { Chart } from './components/Chart';
import { AIChatConsole } from './components/AIChatConsole';

interface BookLevel {
  price: number;
  qty: number;
}

interface Position {
  symbol: string;
  quantity: number;
  average_price: number;
}

interface ActiveOrder {
  order_id: number;
  symbol: string;
  side: string;
  type: string;
  price: number;
  quantity: number;
  remaining_quantity: number;
  status: string;
  created_at: string;
}

export const App: React.FC = () => {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [bids, setBids] = useState<BookLevel[]>([]);
  const [asks, setAsks] = useState<BookLevel[]>([]);
  const [ticks, setTicks] = useState<{ price: number; timestamp: number }[]>([]);
  
  const [cash, setCash] = useState(100000.00);
  const [margin, setMargin] = useState(0.00);
  const [positions, setPositions] = useState<Position[]>([]);
  const [activeOrders, setActiveOrders] = useState<ActiveOrder[]>([]);
  
  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [latency, setLatency] = useState(0.85); // Simulated default sub-ms latency

  const [orderQty, setOrderQty] = useState(5);
  const [orderPrice, setOrderPrice] = useState(50000.00);
  const [orderType, setOrderType] = useState('L'); // L = Limit, M = Market

  // Load portfolio status from API Gateway
  const refreshPortfolio = useCallback(async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/portfolio/status');
      if (res.ok) {
        const data = await res.json();
        setCash(data.cash);
        setMargin(data.margin);
        setPositions(data.positions);
      }

      const ordersRes = await fetch('http://localhost:8000/api/v1/orders/active');
      if (ordersRes.ok) {
        const ordersData = await ordersRes.json();
        setActiveOrders(ordersData);
      }
    } catch (e) {
      console.error('Failed to load portfolio stats:', e);
    }
  }, []);

  // Set up WebSocket connection for real-time updates
  useEffect(() => {
    let ws: WebSocket;
    
    const connect = () => {
      setWsStatus('connecting');
      ws = new WebSocket('ws://localhost:8000/ws/live');

      ws.onopen = () => {
        setWsStatus('connected');
        console.log('API Gateway WebSocket connected.');
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        
        if (msg.type === 'MARKET_TICK') {
          const tick = JSON.parse(msg.data);
          if (tick.symbol !== symbol) return;

          // Append to chart ticks
          setTicks((prev) => {
            const newTicks = [...prev, { price: tick.price, timestamp: tick.timestamp }];
            if (newTicks.length > 200) newTicks.shift(); // keep last 200
            return newTicks;
          });

          // Dynamically populate order book depth
          const level = { price: tick.price, qty: tick.quantity };
          if (tick.side === 'B') {
            setBids((prev) => {
              const updated = prev.filter(b => b.price !== tick.price);
              updated.push(level);
              return updated.sort((a, b) => b.price - a.price).slice(0, 20);
            });
          } else {
            setAsks((prev) => {
              const updated = prev.filter(a => a.price !== tick.price);
              updated.push(level);
              return updated.sort((a, b) => a.price - b.price).slice(0, 20);
            });
          }
          
          // Microsecond latency simulation fluctuation
          setLatency(parseFloat((0.6 + Math.random() * 0.35).toFixed(3)));
        } else if (msg.type === 'EXECUTION') {
          // Trigger portfolio reloads
          refreshPortfolio();
        }
      };

      ws.onclose = () => {
        setWsStatus('disconnected');
        console.log('WebSocket connection lost. Retrying in 3 seconds...');
        setTimeout(connect, 3000);
      };
    };

    connect();
    refreshPortfolio();

    return () => {
      if (ws) ws.close();
    };
  }, [symbol, refreshPortfolio]);

  // Clean order book levels on symbol change
  const handleSymbolChange = (newSymbol: string) => {
    setSymbol(newSymbol);
    setBids([]);
    setAsks([]);
    setTicks([]);
    // Adjust mock order price default
    if (newSymbol === 'BTCUSDT') setOrderPrice(50000.00);
    else if (newSymbol === 'ETHUSDT') setOrderPrice(3000.00);
    else if (newSymbol === 'SOLUSDT') setOrderPrice(150.00);
    else setOrderPrice(22000.00);
  };

  const handlePlaceOrder = async (side: 'B' | 'S') => {
    try {
      const response = await fetch('http://localhost:8000/api/v1/orders/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          side,
          type: orderType,
          price: orderType === 'M' ? 0.0 : orderPrice,
          quantity: orderQty
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        alert(`Order placement failed: ${errorData.detail}`);
      } else {
        refreshPortfolio();
      }
    } catch (e) {
      alert(`Network error placing order: ${e}`);
    }
  };

  const handleCancelOrder = async (orderId: number, ordSymbol: string) => {
    try {
      await fetch('http://localhost:8000/api/v1/orders/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order_id: orderId, symbol: ordSymbol })
      });
      refreshPortfolio();
    } catch (e) {
      console.error(e);
    }
  };

  const handleKillSwitch = async () => {
    if (!confirm('Are you sure you want to trigger the emergency KILL SWITCH? This will cancel all working orders.')) return;
    try {
      await fetch('http://localhost:8000/api/v1/admin/killswitch', { method: 'POST' });
      refreshPortfolio();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="terminal-layout">
      {/* Header Panel */}
      <div className="terminal-header">
        <h1>
          <span>⚡</span> QuantForge Infrastructure Terminal
        </h1>
        <div className="header-stats">
          <div className="stat-item">
            <span className="stat-label">Connection Status</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
              <span className={`status-indicator ${
                wsStatus === 'connected' ? 'status-active' :
                wsStatus === 'connecting' ? 'status-connecting' : 'status-disconnected'
              }`} />
              <span style={{ fontSize: '0.8rem', fontWeight: 500 }}>
                {wsStatus.toUpperCase()}
              </span>
            </div>
          </div>
          <div className="stat-item">
            <span className="stat-label">Order Latency</span>
            <span className="stat-value" style={{ color: 'var(--color-primary)' }}>
              {latency} ms
            </span>
          </div>
          <button onClick={handleKillSwitch} className="btn-kill">
            KILL SWITCH
          </button>
        </div>
      </div>

      {/* Main Grid View */}
      <div className="terminal-body">
        {/* Left Side: Order Ticket & L2 Depth Book */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', height: '100%' }}>
          {/* Order Ticket Card */}
          <div className="panel-card" style={{ flex: '0 0 auto' }}>
            <div className="panel-header">
              <div className="panel-title">Order Ticket</div>
            </div>
            <div className="panel-content" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div>
                <label className="stat-label">Order Type</label>
                <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                  <button
                    onClick={() => setOrderType('L')}
                    style={{
                      flex: 1,
                      padding: '6px',
                      background: orderType === 'L' ? 'var(--color-primary)' : 'rgba(255,255,255,0.05)',
                      color: orderType === 'L' ? '#0a0b0e' : '#fff',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontWeight: 600,
                      fontSize: '0.75rem'
                    }}
                  >
                    Limit
                  </button>
                  <button
                    onClick={() => setOrderType('M')}
                    style={{
                      flex: 1,
                      padding: '6px',
                      background: orderType === 'M' ? 'var(--color-primary)' : 'rgba(255,255,255,0.05)',
                      color: orderType === 'M' ? '#0a0b0e' : '#fff',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontWeight: 600,
                      fontSize: '0.75rem'
                    }}
                  >
                    Market
                  </button>
                </div>
              </div>

              {orderType === 'L' && (
                <div>
                  <label className="stat-label">Limit Price ({symbol.includes('USDT') ? 'USDT' : 'INR'})</label>
                  <input
                    type="number"
                    value={orderPrice}
                    onChange={(e) => setOrderPrice(parseFloat(e.target.value))}
                    className="input-field"
                    style={{ marginTop: '4px' }}
                  />
                </div>
              )}

              <div>
                <label className="stat-label">Quantity</label>
                <input
                  type="number"
                  value={orderQty}
                  onChange={(e) => setOrderQty(parseInt(e.target.value))}
                  className="input-field"
                  style={{ marginTop: '4px' }}
                />
              </div>

              <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
                <button
                  onClick={() => handlePlaceOrder('B')}
                  className="btn-primary"
                  style={{ flex: 1, background: 'var(--color-bid)', color: '#fff' }}
                >
                  BUY / LONG
                </button>
                <button
                  onClick={() => handlePlaceOrder('S')}
                  className="btn-primary"
                  style={{ flex: 1, background: 'var(--color-ask)', color: '#fff' }}
                >
                  SELL / SHORT
                </button>
              </div>
            </div>
          </div>

          {/* Depth book */}
          <div style={{ flex: 1 }}>
            <OrderBook
              symbol={symbol}
              bids={bids}
              asks={asks}
              onSymbolChange={handleSymbolChange}
            />
          </div>
        </div>

        {/* Center: Candlestick chart & Portfolios */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', height: '100%', overflow: 'hidden' }}>
          <Chart symbol={symbol} ticks={ticks} />
          <div style={{ flex: 1.2, overflowY: 'auto' }}>
            <Portfolio
              cash={cash}
              margin={margin}
              positions={positions}
              activeOrders={activeOrders}
              onCancelOrder={handleCancelOrder}
            />
          </div>
        </div>

        {/* Right Side: AI Research Swarm Console */}
        <div style={{ height: '100%' }}>
          <AIChatConsole onOrderPlaced={refreshPortfolio} />
        </div>
      </div>
    </div>
  );
};
export default App;
