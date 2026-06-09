class RiskAnalystAgent:
    def __init__(self, max_allowed_qty: int = 100):
        self.max_allowed_qty = max_allowed_qty

    def validate_proposal(self, portfolio_proposal: dict) -> dict:
        """
        Validates recommended portfolio trades against risk limits.
        """
        symbol = portfolio_proposal["symbol"]
        qty = portfolio_proposal["target_quantity"]
        action = portfolio_proposal["recommended_action"]
        
        approved = True
        reason = "Trade proposal is within standard safety margins."

        if qty > self.max_allowed_qty:
            approved = False
            reason = f"Proposed size {qty} exceeds maximum allowed research trade size {self.max_allowed_qty}."
        elif action == "HOLD":
            approved = True
            reason = "No trade actions proposed. Safety checks passed."

        return {
            "agent": "Risk Analyst Agent",
            "symbol": symbol,
            "approved": approved,
            "approved_quantity": qty if approved else 0,
            "reasoning": f"Reviewed proposal to {action} {qty} {symbol}. Decision: Approved={approved}. Reason: {reason}"
        }
