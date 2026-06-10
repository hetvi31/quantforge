class RiskAnalystAgent:
    """
    Rule-based gate on the portfolio manager's proposal. Deterministic: enforces
    a hard research-trade size cap and passes HOLD through untouched.
    """

    def __init__(self, max_allowed_qty: int = 100):
        self.max_allowed_qty = max_allowed_qty

    def validate_proposal(self, portfolio_proposal: dict) -> dict:
        symbol = portfolio_proposal["symbol"]
        side = portfolio_proposal.get("side")
        qty = portfolio_proposal["target_quantity"]
        action = portfolio_proposal["recommended_action"]

        if qty > self.max_allowed_qty:
            approved, reason = False, (f"Proposed size {qty} exceeds maximum research "
                                       f"trade size {self.max_allowed_qty}.")
        else:
            approved, reason = True, "Proposal within research safety margins."

        return {
            "agent": "Risk Analyst Agent",
            "method": "rule-based",
            "symbol": symbol,
            "side": side,
            "action": action,
            "approved": approved,
            "approved_quantity": qty if approved else 0,
            "reasoning": f"Reviewed {action} {qty} {symbol}: approved={approved}. {reason}",
        }
