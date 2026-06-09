class PortfolioManagerAgent:
    def __init__(self, default_qty: int = 10):
        self.default_qty = default_qty

    def rebalance(self, analyst_report: dict) -> dict:
        """
        Calculates target portfolio adjustment based on analyst report bias.
        """
        symbol = analyst_report["symbol"]
        bias = analyst_report["market_bias"]
        
        target_qty = 0
        action = "HOLD"
        
        if bias == "BULLISH":
            action = "BUY"
            target_qty = self.default_qty
        elif bias == "BEARISH":
            action = "SELL"
            target_qty = self.default_qty

        return {
            "agent": "Portfolio Manager Agent",
            "symbol": symbol,
            "recommended_action": action,
            "target_quantity": target_qty,
            "reasoning": f"Based on Market Analyst's {bias} bias, recommending to {action} {target_qty} units of {symbol}."
        }
