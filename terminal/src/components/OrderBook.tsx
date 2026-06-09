import React from 'react';

interface BookLevel {
  price: number;
  qty: number;
}

interface OrderBookProps {
  symbol: string;
  bids: BookLevel[];
  asks: BookLevel[];
  onSymbolChange: (symbol: string) => void;
}

export const OrderBook: React.FC<OrderBookProps> = ({ symbol, bids, asks, onSymbolChange }) => {
  // Sort asks: low to high for spread view, but we display the top 8 levels
  const displayedAsks = [...asks].sort((a, b) => b.price - a.price).slice(-8);
  const displayedBids = [...bids].sort((a, b) => b.price - a.price).slice(0, 8);

  const maxQty = Math.max(
    ...bids.map((b) => b.qty),
    ...asks.map((a) => a.qty),
    1
  );

  const bestBid = bids.length > 0 ? Math.max(...bids.map(b => b.price)) : null;
  const bestAsk = asks.length > 0 ? Math.min(...asks.map(a => a.price)) : null;
  const spread = bestBid && bestAsk ? bestAsk - bestBid : 0.0;
  const midPrice = bestBid && bestAsk ? (bestBid + bestAsk) / 2.0 : 0.0;

  return (
    <div className="panel-card" style={{ height: '100%' }}>
      <div className="panel-header">
        <div className="panel-title">
          <span className="status-indicator status-active"></span>
          Order Book
        </div>
        <select
          value={symbol}
          onChange={(e) => onSymbolChange(e.target.value)}
          className="input-field"
          style={{ width: '120px', padding: '4px 8px' }}
        >
          <option value="BTCUSDT">BTCUSDT</option>
          <option value="ETHUSDT">ETHUSDT</option>
          <option value="SOLUSDT">SOLUSDT</option>
          <option value="NIFTY">NIFTY</option>
        </select>
      </div>

      <div className="panel-content" style={{ display: 'flex', flexDirection: 'column', padding: '12px' }}>
        {/* Table header */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', padding: '4px 8px', borderBottom: '1px solid var(--border-color)', fontSize: '0.7rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          <div>Price ({symbol.includes('USDT') ? 'USDT' : 'INR'})</div>
          <div style={{ textAlign: 'right' }}>Size</div>
        </div>

        {/* Asks (Sells) - Render on Top */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', minHeight: '160px', margin: '4px 0' }}>
          {displayedAsks.map((level, i) => {
            const widthPct = (level.qty / maxQty) * 100;
            return (
              <div
                key={`ask-${i}`}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  padding: '4px 8px',
                  fontSize: '0.8rem',
                  fontFamily: 'var(--font-mono)',
                  position: 'relative',
                  overflow: 'hidden'
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    right: 0,
                    top: 0,
                    bottom: 0,
                    width: `${widthPct}%`,
                    background: 'rgba(239, 68, 68, 0.08)',
                    zIndex: 0
                  }}
                />
                <span style={{ color: 'var(--color-ask)', zIndex: 1 }}>{level.price.toFixed(2)}</span>
                <span style={{ textAlign: 'right', zIndex: 1 }}>{level.qty}</span>
              </div>
            );
          })}
          {displayedAsks.length === 0 && (
            <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)' }}>No Asks</div>
          )}
        </div>

        {/* Spread info */}
        <div
          style={{
            background: 'rgba(255, 255, 255, 0.02)',
            borderTop: '1px solid var(--border-color)',
            borderBottom: '1px solid var(--border-color)',
            padding: '8px 12px',
            margin: '6px 0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '0.8rem'
          }}
        >
          <div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>MID PRICE</div>
            <div style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: '0.9rem' }}>
              {midPrice > 0 ? midPrice.toFixed(2) : '-'}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>SPREAD</div>
            <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              {spread > 0 ? spread.toFixed(2) : '-'}
            </div>
          </div>
        </div>

        {/* Bids (Buys) - Render on Bottom */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: '160px', margin: '4px 0' }}>
          {displayedBids.map((level, i) => {
            const widthPct = (level.qty / maxQty) * 100;
            return (
              <div
                key={`bid-${i}`}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  padding: '4px 8px',
                  fontSize: '0.8rem',
                  fontFamily: 'var(--font-mono)',
                  position: 'relative',
                  overflow: 'hidden'
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    right: 0,
                    top: 0,
                    bottom: 0,
                    width: `${widthPct}%`,
                    background: 'rgba(16, 185, 129, 0.08)',
                    zIndex: 0
                  }}
                />
                <span style={{ color: 'var(--color-bid)', zIndex: 1 }}>{level.price.toFixed(2)}</span>
                <span style={{ textAlign: 'right', zIndex: 1 }}>{level.qty}</span>
              </div>
            );
          })}
          {displayedBids.length === 0 && (
            <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)' }}>No Bids</div>
          )}
        </div>
      </div>
    </div>
  );
};
