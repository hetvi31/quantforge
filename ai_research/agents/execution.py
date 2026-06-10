import os
import requests
from loguru import logger


class ExecutionAgent:
    """
    Submits an approved research trade to the API Gateway. Uses a MARKET order so
    no synthetic limit price is invented — the live engine determines the fill
    price against the resting book.
    """

    def __init__(self):
        self.gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8000")
        self.api_key = os.getenv("API_KEY", "quantforge-dev-key")

    def execute(self, risk_report: dict) -> dict:
        symbol = risk_report["symbol"]
        side = risk_report.get("side")
        qty = risk_report["approved_quantity"]
        approved = risk_report["approved"]

        if not approved or not side or qty <= 0:
            return {
                "agent": "Execution Agent",
                "status": "SKIPPED",
                "detail": "Not approved by risk, or no actionable side/quantity.",
            }

        payload = {"symbol": symbol, "side": side, "type": "M", "price": 0.0, "quantity": qty}
        logger.info(f"[ExecutionAgent] Dispatching {side} {qty} {symbol} (MARKET) to gateway.")

        try:
            resp = requests.post(
                f"{self.gateway_url}/api/v1/orders/create",
                json=payload,
                headers={"X-API-Key": self.api_key},
                timeout=5,
            )
            if resp.status_code == 200:
                return {
                    "agent": "Execution Agent",
                    "status": "EXECUTED",
                    "order_id": resp.json().get("order_id"),
                    "payload": payload,
                    "detail": "Order placed through API Gateway.",
                }
            return {
                "agent": "Execution Agent",
                "status": "FAILED",
                "detail": f"Gateway returned {resp.status_code}: {resp.text}",
            }
        except Exception as e:
            logger.error(f"Execution agent connection failed: {e}")
            return {
                "agent": "Execution Agent",
                "status": "FAILED",
                "detail": f"Could not reach gateway at {self.gateway_url}: {e}",
            }
