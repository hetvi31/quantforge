import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, ISeriesApi } from 'lightweight-charts';

interface ChartProps {
  symbol: string;
  ticks: { price: number; timestamp: number }[];
}

export const Chart: React.FC<ChartProps> = ({ symbol, ticks }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Create TradingView Chart
    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: '#12141c' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
      },
      width: containerRef.current.clientWidth,
      height: 380,
    });

    const series = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    chartRef.current = chart;
    seriesRef.current = series;

    // Handle resize
    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  // Update chart data whenever ticks or symbol changes
  useEffect(() => {
    if (!seriesRef.current || ticks.length === 0) return;

    // Group ticks into candles (1-minute intervals or similar)
    const candles: any[] = [];
    let currentCandle: any = null;

    ticks.forEach((t) => {
      // Round timestamp to minute boundaries
      const minute = Math.floor(t.timestamp / 60000) * 60;

      if (!currentCandle || currentCandle.time !== minute) {
        if (currentCandle) {
          candles.push(currentCandle);
        }
        currentCandle = {
          time: minute,
          open: t.price,
          high: t.price,
          low: t.price,
          close: t.price,
        };
      } else {
        currentCandle.high = Math.max(currentCandle.high, t.price);
        currentCandle.low = Math.min(currentCandle.low, t.price);
        currentCandle.close = t.price;
      }
    });

    if (currentCandle) {
      candles.push(currentCandle);
    }

    if (candles.length > 0) {
      seriesRef.current.setData(candles);
    }
  }, [ticks, symbol]);

  return (
    <div className="panel-card" style={{ flex: 1.5 }}>
      <div className="panel-header">
        <div className="panel-title">{symbol} Market Chart</div>
        <div style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: 'var(--color-primary)' }}>
          Real-time Feed
        </div>
      </div>
      <div className="panel-content" style={{ padding: '8px', background: '#12141c' }}>
        <div ref={containerRef} style={{ width: '100%', height: '380px' }} />
      </div>
    </div>
  );
};
