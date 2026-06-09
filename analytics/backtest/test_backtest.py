import pandas as pd
import numpy as np
from analytics.backtest.engine import BacktestEngine

class MomentumStrategy:
    """
    Simple momentum strategy:
    - BUY when current close price is higher than close price 3 bars ago.
    - SELL when current close price is lower than close price 3 bars ago.
    """
    def __init__(self, window: int = 3):
        self.window = window
        self.prices = []

    def generate_signal(self, current_bar: dict, position: float) -> str:
        self.prices.append(current_bar['close'])
        if len(self.prices) <= self.window:
            return 'HOLD'
            
        prev_price = self.prices[-self.window - 1]
        curr_price = self.prices[-1]

        if curr_price > prev_price:
            return 'BUY'
        elif curr_price < prev_price:
            return 'SELL'
        return 'HOLD'

def test_backtest_engine():
    # 1. Create dummy dataset (upward trend with some pullbacks)
    data = {
        'date': pd.date_range(start='2026-01-01', periods=10, freq='D'),
        'open':  [100.0, 102.0, 101.0, 105.0, 108.0, 107.0, 110.0, 115.0, 114.0, 120.0],
        'high':  [101.0, 103.0, 102.0, 106.0, 109.0, 108.0, 111.0, 116.0, 115.0, 121.0],
        'low':   [99.0,  101.0, 100.0, 104.0, 107.0, 106.0, 109.0, 114.0, 113.0, 119.0],
        'close': [100.0, 102.0, 101.0, 105.0, 108.0, 107.0, 110.0, 115.0, 114.0, 120.0],
        'volume': [1000] * 10
    }
    df = pd.DataFrame(data)

    # 2. Run Backtest
    strategy = MomentumStrategy()
    engine = BacktestEngine(initial_capital=10000.00)
    result = engine.run(df, strategy)

    # 3. Assertions
    print(f"Backtest completed successfully!")
    print(f"Final Value: {result['final_value']}")
    print(f"Total return: {result['total_return']*100:.2f}%")
    print(f"Total trades: {result['total_trades']}")
    print(f"Sharpe Ratio: {result['sharpe_ratio']}")
    print(f"Max Drawdown: {result['max_drawdown']*100:.2f}%")
    
    assert result['final_value'] > 10000.00
    assert len(result['trades']) > 0
    assert -1.0 <= result['max_drawdown'] <= 0.0
    print("All backtest test assertions PASSED!")

if __name__ == "__main__":
    test_backtest_engine()
