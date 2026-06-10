from loguru import logger


class RiskEngine:
    """
    Pre-trade risk checks. The caller passes in an open cursor so the risk
    evaluation and the subsequent order insert run against the same connection
    and transaction snapshot (removing the check-then-act race that existed when
    risk opened its own separate connection).
    """

    def __init__(self, max_order_qty: int = 500, max_position_qty: int = 1000,
                 max_daily_drawdown_pct: float = 0.10, initial_balance: float = 100000.00):
        self.max_order_qty = max_order_qty
        self.max_position_qty = max_position_qty
        self.max_daily_drawdown_pct = max_daily_drawdown_pct
        self.initial_balance = initial_balance

    def check_order(self, cur, account_id: int, symbol: str, side: str,
                    price: float, quantity: int) -> tuple[bool, str]:
        # 0. Basic input sanity.
        if quantity <= 0:
            return False, "Order quantity must be positive"
        if side not in ("B", "S"):
            return False, f"Invalid side '{side}'"

        # 1. Size check.
        if quantity > self.max_order_qty:
            return False, f"Order quantity {quantity} exceeds maximum order size {self.max_order_qty}"

        try:
            # 2. Daily drawdown check.
            cur.execute("SELECT balance FROM accounts WHERE account_id = %s", (account_id,))
            account = cur.fetchone()
            if not account:
                return False, "Account not found"

            current_balance = float(account[0])
            drawdown = (self.initial_balance - current_balance) / self.initial_balance
            if drawdown >= self.max_daily_drawdown_pct:
                return False, (f"Account drawdown {drawdown * 100:.2f}% exceeds "
                               f"limit {self.max_daily_drawdown_pct * 100:.2f}%")

            # 3. Buying-power check (buy orders only).
            if side == "B":
                order_value = price * quantity
                if current_balance < order_value:
                    return False, (
                        f"Insufficient funds: ${current_balance:.2f} available, "
                        f"order requires ${order_value:.2f}"
                    )

            # 4. Position limit check.
            cur.execute(
                "SELECT quantity FROM positions WHERE account_id = %s AND symbol = %s",
                (account_id, symbol),
            )
            pos = cur.fetchone()
            current_position_qty = int(pos[0]) if pos else 0

            if side == "B":
                potential_qty = current_position_qty + quantity
            else:  # "S"
                potential_qty = current_position_qty - quantity

            if abs(potential_qty) > self.max_position_qty:
                return False, (f"Resulting position {potential_qty} would exceed "
                               f"limit {self.max_position_qty}")

            return True, ""
        except Exception as e:
            logger.error(f"Risk check database exception: {e}")
            return False, f"Risk check failed due to system error: {e}"
