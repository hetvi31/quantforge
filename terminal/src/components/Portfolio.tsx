import React from 'react';

interface Position { symbol: string; quantity: number; average_price: number; }
interface ActiveOrder {
  order_id: number; symbol: string; side: string; type: string;
  price: number; quantity: number; remaining_quantity: number; status: string; created_at: string;
}
interface Props {
  cash: number;
  margin: number;
  positions: Position[];
  activeOrders: ActiveOrder[];
  onCancelOrder: (orderId: number, symbol: string) => void;
}

const money = (n: number) =>
  n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const Portfolio: React.FC<Props> = ({ cash, margin, positions, activeOrders, onCancelOrder }) => (
  <div className="col" style={{ flex: 1 }}>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, flex: '0 0 auto' }}>
      <div className="metric">
        <span className="label">Cash Balance</span>
        <div className="val amber">${money(cash)}</div>
      </div>
      <div className="metric">
        <span className="label">Margin Used</span>
        <div className="val">${money(margin)}</div>
      </div>
    </div>

    <div className="panel" style={{ flex: 1 }}>
      <div className="panel__head">
        <span className="panel__title">Positions</span>
        <span className="panel__sub">{positions.length} open</span>
      </div>
      <div className="panel__body">
        <table className="tbl">
          <thead>
            <tr><th>Symbol</th><th>Qty</th><th>Avg Px</th><th>Notional</th></tr>
          </thead>
          <tbody>
            {positions.map((p, i) => (
              <tr key={i}>
                <td className="amber">{p.symbol}</td>
                <td className={p.quantity >= 0 ? 'up' : 'down'}>{p.quantity}</td>
                <td>{p.average_price.toFixed(2)}</td>
                <td className="dim">{money(p.quantity * p.average_price)}</td>
              </tr>
            ))}
            {positions.length === 0 && (
              <tr><td colSpan={4} className="empty">No open positions</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>

    <div className="panel" style={{ flex: 1.1 }}>
      <div className="panel__head">
        <span className="panel__title">Working Orders</span>
        <span className="panel__sub">{activeOrders.length} live</span>
      </div>
      <div className="panel__body">
        <table className="tbl">
          <thead>
            <tr><th>Symbol</th><th>Side</th><th>Px</th><th>Filled</th><th>Action</th></tr>
          </thead>
          <tbody>
            {activeOrders.map((o) => (
              <tr key={o.order_id}>
                <td className="amber">{o.symbol}</td>
                <td><span className={`tag ${o.side === 'B' ? 'tag--buy' : 'tag--sell'}`}>{o.side === 'B' ? 'BUY' : 'SELL'}</span></td>
                <td>{o.price > 0 ? o.price.toFixed(2) : 'MKT'}</td>
                <td className="dim">{o.quantity - o.remaining_quantity}/{o.quantity}</td>
                <td><button className="btn--xs" onClick={() => onCancelOrder(o.order_id, o.symbol)}>CXL</button></td>
              </tr>
            ))}
            {activeOrders.length === 0 && (
              <tr><td colSpan={5} className="empty">No working orders</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  </div>
);
