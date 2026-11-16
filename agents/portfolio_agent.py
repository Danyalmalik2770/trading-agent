"""PortfolioAgent — the accountant.

Tracks cash, open positions (quantity + average entry) and realised
P&L. Every other agent reads the truth from here.
"""


class PortfolioAgent:
    def __init__(self, config):
        self.cash = float(config["starting_cash"])
        self.starting_cash = self.cash
        self.positions = {}   # symbol -> {"qty": int, "avg_price": float}
        self.last_prices = {} # symbol -> latest known price (for equity)
        self.realised_pnl = 0.0

    def mark(self, symbol, price):
        self.last_prices[symbol] = price

    def position_qty(self, symbol):
        return self.positions.get(symbol, {}).get("qty", 0)

    def equity(self):
        total = self.cash
        for sym, pos in self.positions.items():
            total += pos["qty"] * self.last_prices.get(sym, pos["avg_price"])
        return total

    def apply_buy(self, symbol, qty, price, fee):
        cost = qty * price + fee
        self.cash -= cost
        pos = self.positions.get(symbol)
        if pos:
            new_qty = pos["qty"] + qty
            pos["avg_price"] = (pos["avg_price"] * pos["qty"] + price * qty) / new_qty
            pos["qty"] = new_qty
        else:
            self.positions[symbol] = {"qty": qty, "avg_price": price}
        self.last_prices[symbol] = price

    def apply_sell(self, symbol, qty, price, fee):
        pos = self.positions.get(symbol)
        if not pos or pos["qty"] < qty:
            return False
        self.cash += qty * price - fee
        self.realised_pnl += (price - pos["avg_price"]) * qty - fee
        pos["qty"] -= qty
        if pos["qty"] == 0:
            del self.positions[symbol]
        self.last_prices[symbol] = price
        return True

    def summary(self):
        return {
            "cash": round(self.cash, 2),
            "equity": round(self.equity(), 2),
            "total_return_pct": round((self.equity() - self.starting_cash) / self.starting_cash * 100, 2),
            "realised_pnl": round(self.realised_pnl, 2),
            "positions": {s: dict(p) for s, p in self.positions.items()},
        }
