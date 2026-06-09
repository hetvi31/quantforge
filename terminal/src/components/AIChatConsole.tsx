import React, { useState } from 'react';

interface TraceStep {
  agent: string;
  symbol?: string;
  sentiment_score?: number;
  market_bias?: string;
  recommended_action?: string;
  target_quantity?: number;
  approved?: boolean;
  approved_quantity?: number;
  status?: string;
  order_id?: number;
  reasoning?: string;
  detail?: string;
}

interface AIChatConsoleProps {
  onOrderPlaced: () => void;
}

export const AIChatConsole: React.FC<AIChatConsoleProps> = ({ onOrderPlaced }) => {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [newsText, setNewsText] = useState(
    'Company registers massive profits this quarter. Retail demand surging, bullish indicators suggest long run.'
  );
  const [loading, setLoading] = useState(false);
  const [trace, setTrace] = useState<TraceStep[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleRunPipeline = async () => {
    setLoading(true);
    setError(null);
    setTrace([]);

    try {
      const response = await fetch('http://localhost:8001/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, news: newsText })
      });

      if (!response.ok) {
        throw new Error(`AI Gateway error: ${response.statusText}`);
      }

      const data = await response.json();
      setTrace(data.pipeline_trace);
      
      // Notify parent to refresh positions/orders
      onOrderPlaced();
    } catch (e: any) {
      setError(e.message || 'Failed to complete agent analysis pipeline.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel-card" style={{ height: '100%' }}>
      <div className="panel-header">
        <div className="panel-title">
          <span style={{ color: 'var(--color-purple)' }}>★</span>
          AI Research Agent Swarm
        </div>
      </div>

      <div className="panel-content" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <div style={{ flex: 1 }}>
            <label className="stat-label">Symbol</label>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="input-field"
              placeholder="BTCUSDT"
            />
          </div>
        </div>

        <div>
          <label className="stat-label">News / Sentiment Input</label>
          <textarea
            value={newsText}
            onChange={(e) => setNewsText(e.target.value)}
            className="input-field"
            style={{ height: '80px', resize: 'none', fontFamily: 'var(--font-sans)', marginTop: '4px' }}
            placeholder="Paste news headline or earnings text here..."
          />
        </div>

        <button
          onClick={handleRunPipeline}
          disabled={loading}
          className="btn-primary"
          style={{ background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)', color: '#fff' }}
        >
          {loading ? 'Analyzing Swarm Consensus...' : 'Execute Agent Research'}
        </button>

        {error && (
          <div style={{ padding: '8px 12px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '6px', color: 'var(--color-ask)', fontSize: '0.8rem' }}>
            {error}
          </div>
        )}

        {/* Pipeline Trace Output */}
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
          {trace.map((step, idx) => (
            <div
              key={idx}
              style={{
                background: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                padding: '10px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <span style={{ fontWeight: 600, fontSize: '0.75rem', color: 'var(--color-purple)', textTransform: 'uppercase' }}>
                  {step.agent}
                </span>
                {step.market_bias && (
                  <span style={{
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    color: step.market_bias === 'BULLISH' ? 'var(--color-bid)' : step.market_bias === 'BEARISH' ? 'var(--color-ask)' : 'var(--text-secondary)'
                  }}>
                    {step.market_bias}
                  </span>
                )}
                {step.approved !== undefined && (
                  <span style={{
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    color: step.approved ? 'var(--color-bid)' : 'var(--color-ask)'
                  }}>
                    {step.approved ? 'APPROVED' : 'BLOCKED'}
                  </span>
                )}
                {step.status && (
                  <span style={{
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    color: step.status === 'EXECUTED' ? 'var(--color-bid)' : 'var(--color-ask)'
                  }}>
                    {step.status}
                  </span>
                )}
              </div>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: '1.3' }}>
                {step.reasoning || step.detail}
              </p>
              {step.order_id && (
                <div style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)', color: 'var(--color-primary)', marginTop: '4px' }}>
                  Order ID: {step.order_id}
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              <span className="status-indicator status-connecting" style={{ marginRight: '6px' }}></span>
              Market Analyst compiling sentiment reports...
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
