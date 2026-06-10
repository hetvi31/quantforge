import os
import time
import requests

API_KEY = os.getenv("API_KEY", "quantforge-dev-key")
HEADERS = {"X-API-Key": API_KEY}


def _post(url, payload):
    return requests.post(url, json=payload, headers=HEADERS, timeout=10)


def test_e2e_trading_lifecycle(gateway_url="http://localhost:8000"):
    print("[E2E] Starting end-to-end integration tests...")

    # 1. Initial portfolio.
    try:
        initial = requests.get(f"{gateway_url}/api/v1/portfolio/status", timeout=10).json()
        print(f"[E2E] Initial cash: ${initial['cash']:.2f}")
    except Exception as e:
        print(f"[E2E] Failed to contact gateway: {e}")
        return False

    # 2. Crossing pair that fully matches (sell then buy, same price/qty).
    sell = _post(f"{gateway_url}/api/v1/orders/create",
                 {"symbol": "BTCUSDT", "side": "S", "type": "L", "price": 60000.00, "quantity": 10})
    if sell.status_code != 200:
        print(f"[E2E] Sell placement failed: {sell.text}")
        return False
    print(f"[E2E] Placed sell order {sell.json()['order_id']}")

    buy = _post(f"{gateway_url}/api/v1/orders/create",
                {"symbol": "BTCUSDT", "side": "B", "type": "L", "price": 60000.00, "quantity": 10})
    if buy.status_code != 200:
        print(f"[E2E] Buy placement failed: {buy.text}")
        return False
    print(f"[E2E] Placed buy order {buy.json()['order_id']}")

    time.sleep(2)

    final = requests.get(f"{gateway_url}/api/v1/portfolio/status", timeout=10).json()
    print(f"[E2E] Final cash: ${final['cash']:.2f}")
    btc = [p for p in final["positions"] if p["symbol"] == "BTCUSDT"]

    # Buy/sell of equal size and price -> net flat, cash conserved.
    assert abs(final["cash"] - initial["cash"]) < 1e-2, "Cash not conserved on round trip"
    assert len(btc) == 0 or btc[0]["quantity"] == 0, "Position should be flat"
    print("[E2E] Matching / cash-conservation checks PASSED.")

    # 3. Cancel regression: a resting order must actually leave the book.
    resting = _post(f"{gateway_url}/api/v1/orders/create",
                    {"symbol": "ETHUSDT", "side": "B", "type": "L", "price": 1000.00, "quantity": 5})
    assert resting.status_code == 200, resting.text
    resting_id = resting.json()["order_id"]
    print(f"[E2E] Placed resting order {resting_id}")
    time.sleep(1)

    cancel = _post(f"{gateway_url}/api/v1/orders/cancel",
                   {"symbol": "ETHUSDT", "order_id": resting_id})
    assert cancel.status_code == 200, cancel.text
    time.sleep(1)

    active = requests.get(f"{gateway_url}/api/v1/orders/active", timeout=10).json()
    assert all(o["order_id"] != resting_id for o in active), \
        "Cancelled order is still working — cancel path is broken!"
    print("[E2E] Cancel regression PASSED — order left the book.")

    # 4. Auth must be enforced on writes.
    unauth = requests.post(f"{gateway_url}/api/v1/orders/create",
                           json={"symbol": "BTCUSDT", "side": "B", "type": "M",
                                 "price": 0, "quantity": 1}, timeout=10)
    assert unauth.status_code == 401, f"Expected 401 without API key, got {unauth.status_code}"
    print("[E2E] Auth enforcement PASSED.")

    print("[E2E] ALL END-TO-END CHECKS PASSED!")
    return True


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    ok = test_e2e_trading_lifecycle(url)
    raise SystemExit(0 if ok else 1)
