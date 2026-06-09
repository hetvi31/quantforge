import os
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from analytics.metrics import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_value_at_risk,
    calculate_conditional_value_at_risk
)

class BacktestEngine:
    def __init__(self, initial_capital: float = 100000.00):
        self.initial_capital = initial_capital

    def run(self, df: pd.DataFrame, strategy_instance: Any) -> Dict[str, Any]:
        """
        Replays historical bar data.
        df must have index or columns: 'timestamp' or 'date', and 'open', 'high', 'low', 'close', 'volume'.
        strategy_instance must implement:
            generate_signal(self, current_bar: dict, position: float) -> str ('BUY', 'SELL', 'HOLD')
        """
        # Ensure column names are standardized to lowercase
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]

        if 'timestamp' not in df.columns and 'date' in df.columns:
            df.rename(columns={'date': 'timestamp'}, inplace=True)
        
        # Sort by timestamp
        if 'timestamp' in df.columns:
            df.sort_values('timestamp', inplace=True)
            df.reset_index(drop=True, inplace=True)

        cash = self.initial_capital
        position = 0.0
        portfolio_value = self.initial_capital
        
        trades = []
        equity_curve = []
        daily_returns = []
        last_portfolio_value = self.initial_capital

        for idx, row in df.iterrows():
            bar = row.to_dict()
            close_price = bar['close']
            timestamp = bar.get('timestamp', idx)

            # 1. Evaluate strategy signal
            signal = strategy_instance.generate_signal(bar, position)

            # 2. Simulate fills (assume immediate execution at close price)
            trade_filled = False
            trade_info = {}
            
            if signal == 'BUY' and position == 0:
                # Buy maximum possible units given current cash
                qty = int(cash / close_price)
                if qty > 0:
                    cost = qty * close_price
                    cash -= cost
                    position += qty
                    trade_filled = True
                    trade_info = {
                        "timestamp": timestamp,
                        "action": "BUY",
                        "price": close_price,
                        "quantity": qty,
                        "cash_remaining": cash
                    }
            elif signal == 'SELL' and position > 0:
                # Sell all positions
                revenue = position * close_price
                cash += revenue
                trade_filled = True
                trade_info = {
                    "timestamp": timestamp,
                    "action": "SELL",
                    "price": close_price,
                    "quantity": position,
                    "cash_remaining": cash
                }
                position = 0.0

            if trade_filled:
                trades.append(trade_info)

            # Calculate current portfolio value
            portfolio_value = cash + (position * close_price)
            equity_curve.append(portfolio_value)

            # Daily return tracking
            daily_return = (portfolio_value - last_portfolio_value) / last_portfolio_value
            daily_returns.append(daily_return)
            last_portfolio_value = portfolio_value

        # Metrics summary
        equity_series = pd.Series(equity_curve)
        returns_series = pd.Series(daily_returns)

        total_return = (portfolio_value - self.initial_capital) / self.initial_capital
        max_dd = calculate_max_drawdown(equity_series)
        sharpe = calculate_sharpe_ratio(returns_series)
        sortino = calculate_sortino_ratio(returns_series)
        var_95 = calculate_value_at_risk(returns_series, 0.95)
        cvar_95 = calculate_conditional_value_at_risk(returns_series, 0.95)

        # Win rate logic (positive trade profits)
        wins = 0
        total_trades = 0
        current_buy = None
        for t in trades:
            if t['action'] == 'BUY':
                current_buy = t
            elif t['action'] == 'SELL' and current_buy is not None:
                profit = (t['price'] - current_buy['price']) * current_buy['quantity']
                if profit > 0:
                    wins += 1
                total_trades += 1
                current_buy = None

        win_rate = (wins / total_trades) if total_trades > 0 else 0.0

        return {
            "total_return": total_return,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown": max_dd,
            "value_at_risk_95": var_95,
            "conditional_value_at_risk_95": cvar_95,
            "total_trades": len(trades),
            "win_rate": win_rate,
            "final_value": portfolio_value,
            "trades": trades,
            "equity_curve": equity_curve
        }
