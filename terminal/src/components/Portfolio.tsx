import React from 'react';

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

interface PortfolioProps {
  cash: number;
  margin: number;
  positions: Position[];
  activeOrders: ActiveOrder[];
  onCancelOrder: (orderId: number, symbol: string) => void;
}

export const Portfolio: React.FC<PortfolioProps> = ({ cash, margin, positions, activeOrders, onCancelOrder }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', height: '100%' }}>
      {/* Account Balances Summary */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <div className="panel-card" style={{ padding: '16px' }}>
          <div className="stat-label" style={{ alignSelf: 'flex-start' }}>Cash Balance</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--color-primary)', fontFamily: 'var(--font-mono)' }}>
            ${cash.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="panel-card" style={{ padding: '16px' }}>
          <div className="stat-label" style={{ alignSelf: 'flex-start' }}>Margin Utilization</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--color-warning)', fontFamily: 'var(--font-mono)' }}>
            ${margin.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
      </div>

      {/* Positions Table */}
      <div className="panel-card" style={{ flex: 1 }}>
        <div className="panel-header">
          <div className="panel-title">Active Positions</div>
        </div>
        <div className="panel-content" style={{ padding: 0 }}>
          <table className="custom-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Qty</th>
                <th>Avg Price</th>
                <th style={{ textAlign: 'right' }}>Total Value</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((pos, idx) => (
                <tr key={`pos-${idx}`}>
                  <td style={{ fontWeight: 600 }}>{pos.symbol}</td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>{pos.quantity}</td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>${pos.average_price.toFixed(2)}</td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>
                    ${(pos.quantity * pos.average_price).toFixed(2)}
                  </td>
                </tr>
              ))}
              {positions.length === 0 && (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    No active positions.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Active Orders Table */}
      <div className="panel-card" style={{ flex: 1.2 }}>
        <div className="panel-header">
          <div className="panel-title">Working Orders</div>
        </div>
        <div className="panel-content" style={{ padding: 0 }}>
          <table className="custom-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Price</th>
                <th>Qty</th>
                <th style={{ textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {activeOrders.map((ord) => (
                <tr key={ord.order_id}>
                  <td style={{ fontWeight: 600 }}>{ord.symbol}</td>
                  <td>
                    <span
                      style={{
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontSize: '0.7rem',
                        fontWeight: 600,
                        background: ord.side === 'B' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                        color: ord.side === 'B' ? 'var(--color-bid)' : 'var(--color-ask)'
                      }}
                    >
                      {ord.side === 'B' ? 'BUY' : 'SELL'}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>
                    {ord.price > 0 ? `$${ord.price.toFixed(2)}` : 'MARKET'}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>
                    {ord.remaining_quantity} / {ord.quantity}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      onClick={() => onCancelOrder(ord.order_id, ord.symbol)}
                      style={{
                        background: 'rgba(239, 68, 68, 0.1)',
                        border: '1px solid rgba(239, 68, 68, 0.2)',
                        borderRadius: '4px',
                        color: 'var(--color-ask)',
                        cursor: 'pointer',
                        fontSize: '0.7rem',
                        padding: '4px 8px',
                        transition: 'background 0.2s'
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)')}
                    >
                      Cancel
                    </button>
                  </td>
                </tr>
              ))}
              {activeOrders.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    No working orders.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
