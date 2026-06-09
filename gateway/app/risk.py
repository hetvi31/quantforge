from loguru import logger
import psycopg2
from app.db.init_db import get_db_connection

class RiskEngine:
    def __init__(self, max_order_qty: int = 500, max_position_qty: int = 1000, max_daily_drawdown_pct: float = 0.10):
        self.max_order_qty = max_order_qty
        self.max_position_qty = max_position_qty
        self.max_daily_drawdown_pct = max_daily_drawdown_pct
        self.initial_balance = 100000.00 # Seeded default balance

    def check_order(self, account_id: int, symbol: str, side: str, price: float, quantity: int) -> (bool, str):
        """
        Runs pre-trade risk checks.
        Returns (True, "") if check passes, else (False, "rejection reason").
        """
        # 1. Size check
        if quantity > self.max_order_qty:
            return False, f"Order quantity {quantity} exceeds maximum allowed order size {self.max_order_qty}"

        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # 2. Daily Drawdown check
            cur.execute("SELECT balance FROM accounts WHERE account_id = %s", (account_id,))
            account = cur.fetchone()
            if not account:
                return False, "Account not found"
            
            current_balance = float(account[0])
            drawdown = (self.initial_balance - current_balance) / self.initial_balance
            if drawdown >= self.max_daily_drawdown_pct:
                return False, f"Account drawdown {drawdown*100:.2f}% exceeds maximum allowed limit {self.max_daily_drawdown_pct*100:.2f}%"

            # 3. Position limit check
            cur.execute("SELECT quantity FROM positions WHERE account_id = %s AND symbol = %s", (account_id, symbol))
            pos = cur.fetchone()
            current_position_qty = int(pos[0]) if pos else 0

            if side == "B":
                potential_qty = current_position_qty + quantity
                if potential_qty > self.max_position_qty:
                    return False, f"Total position {potential_qty} would exceed maximum limit {self.max_position_qty}"
            elif side == "S":
                potential_qty = current_position_qty - quantity
                # Allow shorting up to maximum position limit in negative direction
                if abs(potential_qty) > self.max_position_qty:
                    return False, f"Total short position {potential_qty} would exceed maximum limit {self.max_position_qty}"

            return True, ""
        except Exception as e:
            logger.error(f"Risk Check Database Exception: {e}")
            return False, f"Risk check failed due to system error: {e}"
        finally:
            cur.close()
            conn.close()
