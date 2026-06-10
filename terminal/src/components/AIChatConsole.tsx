import React, { useState, useEffect } from 'react';
import { AI_BASE } from '../config';

interface TraceStep {
  agent: string;
  method?: string;
  symbol?: string;
  sentiment_score?: number;
  market_bias?: string;
  recommended_action?: string;
  approved?: boolean;
  status?: string;
  order_id?: number;
  reasoning?: string;
  detail?: string;
}

interface Props {
  defaultSymbol: string;
  onOrderPlaced: () => void;
}

export const AIChatConsole: React.FC<Props> = ({ defaultSymbol, onOrderPlaced }) => {
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [newsText, setNewsText] = useState(
    'Company reports record quarterly profit; retail demand surging, guidance raised.');
  const [loading, setLoading] = useState(false);
  const [trace, setTrace] = useState<TraceStep[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setSymbol(defaultSymbol), [defaultSymbol]);

  const run = async () => {
    setLoading(true); setError(null); setTrace([]);
    try {
      const res = await fetch(`${AI_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, news: newsText }),
      });
      if (!res.ok) throw new Error(`AI service ${res.status}`);
      const data = await res.json();
      setTrace(data.pipeline_trace);
      onOrderPlaced();
    } catch (e) {
      setError((e as Error).message || 'Agent pipeline failed.');
    } finally {
      setLoading(false);
    }
  };

  const badge = (s: TraceStep) => {
    if (s.market_bias) return { text: s.market_bias, cls: s.market_bias === 'BULLISH' ? 'up' : s.market_bias === 'BEARISH' ? 'down' : 'dim' };
    if (s.approved !== undefined) return { text: s.approved ? 'APPROVED' : 'BLOCKED', cls: s.approved ? 'up' : 'down' };
    if (s.status) return { text: s.status, cls: s.status === 'EXECUTED' ? 'up' : 'down' };
    return null;
  };

  return (
    <div className="panel" style={{ height: '100%' }}>
      <div className="panel__head">
        <span className="panel__title">AI Research Pipeline</span>
        <span className="panel__sub">analyst → pm → risk → exec</span>
      </div>
      <div className="panel__body panel__body--pad" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div>
          <span className="label">Symbol</span>
          <input className="field" value={symbol} onChange={(e) => setSymbol(e.target.value)} />
        </div>
        <div>
          <span className="label">News / Sentiment Input</span>
          <textarea className="field" style={{ height: 70, resize: 'none' }}
                    value={newsText} onChange={(e) => setNewsText(e.target.value)} />
        </div>
        <button className="btn btn--ai" onClick={run} disabled={loading}>
          {loading ? 'Running Pipeline…' : 'Run Agent Pipeline'}
        </button>

        {error && <div className="down" style={{ fontSize: 10.5 }}>{error}</div>}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, overflowY: 'auto' }}>
          {trace.map((s, i) => {
            const b = badge(s);
            return (
              <div className="trace" key={i}>
                <div className="trace__head">
                  <span className="trace__agent">{s.agent}</span>
                  {b && <span className={`trace__badge ${b.cls}`}>{b.text}</span>}
                </div>
                <div className="trace__body">{s.reasoning || s.detail}</div>
                <div className="trace__meta">
                  {s.method && <span>method: {s.method}</span>}
                  {s.order_id && <span> · order #{s.order_id}</span>}
                  {typeof s.sentiment_score === 'number' && <span> · score {s.sentiment_score.toFixed(2)}</span>}
                </div>
              </div>
            );
          })}
          {!trace.length && !loading && (
            <div className="empty">Submit news to run the 4-agent research pipeline.</div>
          )}
        </div>
      </div>
    </div>
  );
};
