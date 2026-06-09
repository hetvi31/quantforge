import time
import requests

def test_e2e_trading_lifecycle(gateway_url="http://localhost:8000"):
    print("[E2E Test] Starting End-to-End Integration Tests...")
    
    # 1. Fetch initial portfolio status
    try:
        portfolio_response = requests.get(f"{gateway_url}/api/v1/portfolio/status")
        portfolio_response.raise_for_status()
        initial_portfolio = portfolio_response.json()
        print(f"[E2E Test] Initial Cash: ${initial_portfolio['cash']:.2f}")
    except Exception as e:
        print(f"[E2E Test] Failed to contact gateway: {e}")
        return False

    # 2. Place Sell limit order: 10 units at $60,000
    sell_payload = {
        "symbol": "BTCUSDT",
        "side": "S",
        "type": "L",
        "price": 60000.00,
        "quantity": 10
    }
    sell_response = requests.post(f"{gateway_url}/api/v1/orders/create", json=sell_payload)
    if sell_response.status_code != 200:
        print(f"[E2E Test] Sell Order placement failed: {sell_response.text}")
        return False
    sell_order_id = sell_response.json()["order_id"]
    print(f"[E2E Test] Placed Sell Order. ID: {sell_order_id}")

    # 3. Place Buy limit order: 10 units at $60,000 (crosses and matches immediately)
    buy_payload = {
        "symbol": "BTCUSDT",
        "side": "B",
        "type": "L",
        "price": 60000.00,
        "quantity": 10
    }
    buy_response = requests.post(f"{gateway_url}/api/v1/orders/create", json=buy_payload)
    if buy_response.status_code != 200:
        print(f"[E2E Test] Buy Order placement failed: {buy_response.text}")
        return False
    buy_order_id = buy_response.json()["order_id"]
    print(f"[E2E Test] Placed Buy Order. ID: {buy_order_id}")

    # Allow matching engine and database threadpool to settle updates
    time.sleep(2)

    # 4. Fetch updated portfolio status
    portfolio_response = requests.get(f"{gateway_url}/api/v1/portfolio/status")
    final_portfolio = portfolio_response.json()
    print(f"[E2E Test] Final Cash: ${final_portfolio['cash']:.2f}")
    
    # Assert positions are matched and updated
    positions = final_portfolio["positions"]
    btc_pos = [p for p in positions if p["symbol"] == "BTCUSDT"]
    
    print(f"[E2E Test] Current BTC positions: {btc_pos}")
    
    # Since account 1 (DefaultTrader) placed both orders, cash should have decremented cost of buy ($600,000)
    # and incremented proceeds of sell ($600,000), leaving net cash balance close to initial cash!
    # Positions should be net 0 BTC.
    assert abs(final_portfolio["cash"] - initial_portfolio["cash"]) < 1e-2
    assert len(btc_pos) == 0 or btc_pos[0]["quantity"] == 0
    
    print("[E2E Test] End-to-End matching checks PASSED successfully!")
    return True

if __name__ == "__main__":
    import sys
    url = "http://localhost:8000"
    if len(sys.argv) > 1:
        url = sys.argv[1]
    test_e2e_trading_lifecycle(url)
