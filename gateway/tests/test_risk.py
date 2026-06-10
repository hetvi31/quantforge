"""Unit tests for the pre-trade RiskEngine using a fake DB cursor."""
from app.risk import RiskEngine


class FakeCursor:
    """Minimal cursor stub: returns a scripted balance then position quantity."""
    def __init__(self, balance=100000.0, position_qty=0):
        self._balance = balance
        self._position_qty = position_qty
        self._last = None

    def execute(self, query, params=()):
        if "FROM accounts" in query:
            self._last = ("balance",)
        elif "FROM positions" in query:
            self._last = ("position",)
        else:
            self._last = None

    def fetchone(self):
        if self._last == ("balance",):
            return (self._balance,)
        if self._last == ("position",):
            return (self._position_qty,)
        return None


def test_accepts_normal_order():
    # Buy 1 BTC @ $50k = $50k cost, fits in $100k balance.
    ok, reason = RiskEngine().check_order(FakeCursor(), 1, "BTCUSDT", "B", 50000.0, 1)
    assert ok and reason == ""


def test_rejects_oversized_order():
    ok, reason = RiskEngine(max_order_qty=100).check_order(FakeCursor(), 1, "BTCUSDT", "B", 50000.0, 500)
    assert not ok and "maximum order size" in reason


def test_rejects_nonpositive_quantity():
    ok, _ = RiskEngine().check_order(FakeCursor(), 1, "BTCUSDT", "B", 50000.0, 0)
    assert not ok


def test_rejects_on_drawdown():
    # Balance dropped 15% below the 100k initial -> over the 10% limit.
    ok, reason = RiskEngine().check_order(FakeCursor(balance=85000.0), 1, "BTCUSDT", "B", 50000.0, 10)
    assert not ok and "drawdown" in reason


def test_rejects_position_breach():
    # Use a low price so buying-power passes; only position limit should fire.
    re = RiskEngine(max_position_qty=1000)
    ok, reason = re.check_order(FakeCursor(position_qty=995), 1, "BTCUSDT", "B", 10.0, 10)
    assert not ok and "position" in reason.lower()


def test_allows_short_within_limit():
    re = RiskEngine(max_position_qty=1000)
    ok, _ = re.check_order(FakeCursor(position_qty=0), 1, "BTCUSDT", "S", 50000.0, 10)
    assert ok


# ---------------------------------------------------------------------------
# Buying-power tests (Fix 5)
# ---------------------------------------------------------------------------

def test_rejects_buy_with_insufficient_funds():
    # balance=95000 -> drawdown 5% (passes), but 10 @ $10000 = $100k > $95k.
    ok, reason = RiskEngine().check_order(
        FakeCursor(balance=95000.0), 1, "BTCUSDT", "B", 10000.0, 10
    )
    assert not ok
    assert "insufficient funds" in reason.lower()


def test_accepts_buy_exactly_at_balance():
    # Balance exactly covers the order: 10 units @ $9500 = $95k == balance.
    ok, _ = RiskEngine().check_order(
        FakeCursor(balance=95000.0), 1, "BTCUSDT", "B", 9500.0, 10
    )
    assert ok


def test_sell_is_not_subject_to_buying_power():
    # Sells don't require buying power — use a near-initial balance so drawdown
    # check also passes, and verify only position limits apply.
    ok, _ = RiskEngine(max_position_qty=1000).check_order(
        FakeCursor(balance=95000.0), 1, "BTCUSDT", "S", 50000.0, 10
    )
    assert ok
