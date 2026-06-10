class PortfolioManagerAgent:
    """
    Rule-based position sizer. Maps the analyst's directional bias to a concrete
    BUY/SELL/HOLD action and a target size. Deterministic by design.
    """

    def __init__(self, default_qty: int = 10):
        self.default_qty = default_qty

    def rebalance(self, analyst_report: dict) -> dict:
        symbol = analyst_report["symbol"]
        bias = analyst_report["market_bias"]

        if bias == "BULLISH":
            action, side, target_qty = "BUY", "B", self.default_qty
        elif bias == "BEARISH":
            action, side, target_qty = "SELL", "S", self.default_qty
        else:
            action, side, target_qty = "HOLD", None, 0

        return {
            "agent": "Portfolio Manager Agent",
            "method": "rule-based",
            "symbol": symbol,
            "side": side,
            "recommended_action": action,
            "target_quantity": target_qty,
            "reasoning": f"Analyst bias is {bias}; recommending {action} {target_qty} {symbol}.",
        }
