"""ExecutionAgent — the hands.

Places PAPER orders only: fills are simulated at the latest price
with the configured fee and slippage, and booked into the Portfolio.
There is deliberately no broker connection in this class — wiring a
real broker later means replacing `execute()` and nothing else.
"""


class ExecutionAgent:
    def __init__(self, config, portfolio):
        self.cfg = config
        self.portfolio = portfolio
        self.fills = []

    def execute(self, symbol, side, qty, price, reason=""):
        if qty <= 0:
            return None
        slip = price * self.cfg["slippage_pct"] / 100
        fill_price = price + slip if side == "BUY" else price - slip
        fee = qty * fill_price * self.cfg["fee_pct"] / 100
        if side == "BUY":
            if qty * fill_price + fee > self.portfolio.cash:
                return None
            self.portfolio.apply_buy(symbol, qty, round(fill_price, 2), round(fee, 2))
        else:
            if not self.portfolio.apply_sell(symbol, qty, round(fill_price, 2), round(fee, 2)):
                return None
        fill = {"symbol": symbol, "side": side, "qty": qty,
                "price": round(fill_price, 2), "fee": round(fee, 2), "reason": reason}
        self.fills.append(fill)
        return fill
