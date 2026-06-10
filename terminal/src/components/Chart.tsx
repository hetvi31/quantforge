import React, { useEffect, useRef, memo } from 'react';
import { createChart, IChartApi, ISeriesApi } from 'lightweight-charts';

interface Props {
  symbol: string;
  ticks: { price: number; timestamp: number }[];
}

type Candle = { time: number; open: number; high: number; low: number; close: number };

function buildCandles(ticks: { price: number; timestamp: number }[]): Candle[] {
  const candles: Candle[] = [];
  let cur: Candle | null = null;
  for (const t of ticks) {
    const bucket = Math.floor(t.timestamp / 5000) * 5; // 5-second bars
    if (!cur || cur.time !== bucket) {
      if (cur) candles.push(cur);
      cur = { time: bucket, open: t.price, high: t.price, low: t.price, close: t.price };
    } else {
      if (t.price > cur.high) cur.high = t.price;
      if (t.price < cur.low) cur.low = t.price;
      cur.close = t.price;
    }
  }
  if (cur) candles.push(cur);
  return candles;
}

export const Chart: React.FC<Props> = memo(({ symbol, ticks }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef    = useRef<IChartApi | null>(null);
  const seriesRef   = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const prevSymbol  = useRef<string>('');

  // Create chart once on mount.
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: '#0b0c0e' },
        textColor: '#8b9097',
        fontFamily: 'JetBrains Mono, monospace',
      },
      grid: {
        vertLines: { color: '#16181d' },
        horzLines: { color: '#16181d' },
      },
      rightPriceScale: { borderColor: '#2a2d33' },
      timeScale: { borderColor: '#2a2d33', timeVisible: true, secondsVisible: false },
      crosshair: { vertLine: { color: '#ffa028' }, horzLine: { color: '#ffa028' } },
      width:  containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      handleScroll: true,
      handleScale:  true,
    });

    const series = chart.addCandlestickSeries({
      upColor: '#1fcf5b', downColor: '#ff4d42',
      borderVisible: false,
      wickUpColor: '#1fcf5b', wickDownColor: '#ff4d42',
    });

    chartRef.current  = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width:  containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    ro.observe(containerRef.current);
    return () => { ro.disconnect(); chart.remove(); };
  }, []);

  // Update chart data.
  // - Symbol change  →  full setData reset (clears old instrument's history).
  // - Same symbol    →  series.update(lastCandle) only — O(1), zero flicker.
  //   lightweight-charts update() either mutates the current open bar in-place
  //   or appends a new bar; the canvas never redraws from scratch.
  useEffect(() => {
    if (!seriesRef.current || ticks.length === 0) return;

    const candles = buildCandles(ticks);
    if (candles.length === 0) return;

    if (symbol !== prevSymbol.current) {
      seriesRef.current.setData(candles as never);
      prevSymbol.current = symbol;
    } else {
      // Only push the current (last, still-forming) candle.
      seriesRef.current.update(candles[candles.length - 1] as never);
    }
  }, [ticks, symbol]);

  return (
    <div className="panel" style={{ flex: '1 1 55%', minHeight: 0 }}>
      <div className="panel__head">
        <span className="panel__title">{symbol} · Price</span>
        <span className="panel__sub">5s candles · live feed</span>
      </div>
      <div className="panel__body" style={{ padding: 0 }}>
        <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      </div>
    </div>
  );
});
