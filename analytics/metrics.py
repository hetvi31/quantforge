import numpy as np
import pandas as pd

def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """
    Calculates annualized Sharpe Ratio. Assumes daily returns.
    """
    if len(returns) < 2:
        return 0.0
    mean_excess = returns.mean() - (risk_free_rate / 252.0)
    std_dev = returns.std()
    if std_dev == 0 or np.isnan(std_dev):
        return 0.0
    return float(mean_excess / std_dev * np.sqrt(252.0))

def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """
    Calculates annualized Sortino Ratio. Assumes daily returns.
    Only considers negative downside deviations.
    """
    if len(returns) < 2:
        return 0.0
    mean_excess = returns.mean() - (risk_free_rate / 252.0)
    downside_returns = returns[returns < 0]
    if len(downside_returns) < 2:
        return 0.0
    downside_std = downside_returns.std()
    if downside_std == 0 or np.isnan(downside_std):
        return 0.0
    return float(mean_excess / downside_std * np.sqrt(252.0))

def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """
    Calculates Maximum Drawdown of an equity curve series.
    """
    if len(equity_curve) < 1:
        return 0.0
    running_max = equity_curve.cummax()
    drawdowns = (equity_curve - running_max) / running_max
    return float(drawdowns.min())

def calculate_value_at_risk(returns: pd.Series, confidence_level: float = 0.95) -> float:
    """
    Calculates Value at Risk (VaR) using historical simulation.
    """
    if len(returns) < 1:
        return 0.0
    alpha = 1.0 - confidence_level
    return float(np.percentile(returns, alpha * 100))

def calculate_conditional_value_at_risk(returns: pd.Series, confidence_level: float = 0.95) -> float:
    """
    Calculates Conditional Value at Risk (CVaR), representing the expected loss beyond VaR.
    """
    if len(returns) < 1:
        return 0.0
    var = calculate_value_at_risk(returns, confidence_level)
    tail_returns = returns[returns <= var]
    if len(tail_returns) < 1:
        return var
    return float(tail_returns.mean())
