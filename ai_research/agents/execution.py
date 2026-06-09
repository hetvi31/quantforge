import os
import requests
from loguru import logger

class ExecutionAgent:
    def __init__(self):
        # Read API Gateway target
        self.gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8000")

    def execute(self, risk_report: dict) -> dict:
        """
        Submits the validated order to the API Gateway.
        """
        symbol = risk_report["symbol"]
        qty = risk_report["approved_quantity"]
        approved = risk_report["approved"]
        
        # If not approved or qty is 0, do not execute
        if not approved or qty <= 0:
            return {
                "agent": "Execution Agent",
                "status": "SKIPPED",
                "detail": "Order was not approved by Risk Analyst or quantity is zero."
            }

        payload = {
            "symbol": symbol,
            "side": "B", # Default to BUY for research triggers, or we can parse from parent steps
            "type": "L", # Limit order
            "price": 100.00, # Base price for mock, wait, let's fetch current price or use a dummy
            "quantity": qty
        }

        # Let's check if there is an action defined in the chain
        # If we need to sell, change side
        action = risk_report.get("reasoning", "").upper()
        if "SELL" in action:
            payload["side"] = "S"

        logger.info(f"[ExecutionAgent] Dispatching order to Gateway: {payload}")
        
        try:
            url = f"{self.gateway_url}/api/v1/orders/create"
            response = requests.post(url, json=payload, timeout=5)
            if response.status_code == 200:
                result = response.json()
                return {
                    "agent": "Execution Agent",
                    "status": "EXECUTED",
                    "order_id": result.get("order_id"),
                    "payload": payload,
                    "detail": "Order placed successfully through API Gateway."
                }
            else:
                return {
                    "agent": "Execution Agent",
                    "status": "FAILED",
                    "detail": f"Gateway returned error: {response.text}"
                }
        except Exception as e:
            logger.error(f"Execution Agent connection failed: {e}")
            return {
                "agent": "Execution Agent",
                "status": "FAILED",
                "detail": f"Could not reach API Gateway at {self.gateway_url}: {e}"
            }
