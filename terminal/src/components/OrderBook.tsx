import React from 'react';

interface BookLevel { price: number; qty: number; }
interface Props {
  symbol: string;
  ccy: string;
  bids: BookLevel[]; // best (highest) first
  asks: BookLevel[]; // best (lowest) first
}

const LEVELS = 9;

export const OrderBook: React.FC<Props> = ({ symbol, ccy, bids, asks }) => {
  const topAsks = asks.slice(0, LEVELS);
  const topBids = bids.slice(0, LEVELS);

  const maxQty = Math.max(1, ...topAsks.map((a) => a.qty), ...topBids.map((b) => b.qty));
  const bestBid = bids.length ? bids[0].price : 0;
  const bestAsk = asks.length ? asks[0].price : 0;
  const mid = bestBid && bestAsk ? (bestBid + bestAsk) / 2 : 0;
  const spread = bestBid && bestAsk ? bestAsk - bestBid : 0;

  let bidCum = 0;

  return (
    <>
      <div className="panel__head">
        <span className="panel__title">Order Book · L2</span>
        <span className="panel__sub">{symbol} · {ccy}</span>
      </div>
      <div className="panel__body">
        <div className="ladder">
          <div className="ladder__head"><span>Price</span><span>Size</span><span>Total</span></div>

          {/* Asks: rendered worst→best so the best ask sits just above the mid */}
          <div className="ladder__rows">
            {[...topAsks].reverse().map((lvl, i) => {
              const cum = topAsks.slice(0, topAsks.length - i).reduce((s, l) => s + l.qty, 0);
              return (
                <div className="ladder__row ladder__row--ask" key={`a${i}`}>
                  <div className="ladder__bar" style={{ width: `${(lvl.qty / maxQty) * 100}%` }} />
                  <span className="px">{lvl.price.toFixed(2)}</span>
                  <span>{lvl.qty}</span>
                  <span className="dim">{cum}</span>
                </div>
              );
            })}
            {topAsks.length === 0 && <div className="empty">No asks</div>}
          </div>

          <div className="ladder__mid">
            <div>
              <div className="lbl">Mid</div>
              <div className="px">{mid ? mid.toFixed(2) : '—'}</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="lbl">Spread</div>
              <div className="spread">{spread ? spread.toFixed(2) : '—'}</div>
            </div>
          </div>

          {/* Bids: best→worst below the mid */}
          <div className="ladder__rows">
            {topBids.map((lvl, i) => {
              bidCum = topBids.slice(0, i + 1).reduce((s, l) => s + l.qty, 0);
              return (
                <div className="ladder__row ladder__row--bid" key={`b${i}`}>
                  <div className="ladder__bar" style={{ width: `${(lvl.qty / maxQty) * 100}%` }} />
                  <span className="px">{lvl.price.toFixed(2)}</span>
                  <span>{lvl.qty}</span>
                  <span className="dim">{bidCum}</span>
                </div>
              );
            })}
            {topBids.length === 0 && <div className="empty">No bids</div>}
          </div>
        </div>
      </div>
    </>
  );
};
