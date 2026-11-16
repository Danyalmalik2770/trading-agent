"""RiskAgent — the bodyguard.

Every proposed trade passes through here. It sizes the position from
the risk rules, sets stop-loss / take-profit, and can VETO any trade
that breaks a rule (too big, daily loss limit hit, no room left).
A veto is final — the ExecutionAgent never sees a vetoed trade.

Stop and target levels are volatility-aware (see stop_take_pct):
placed outside the stock's ordinary daily noise, wider for wild
stocks, tighter for calm ones, always with the target twice as far
as the stop.
"""
from agents.technical_agent import volatility_pct


def stop_take_pct(candles, cfg):
    """(stop_pct, take_pct) for this market right now."""
    vol = volatility_pct(candles)
    stop = vol * cfg["stop_vol_multiple"]
    stop = max(cfg["stop_min_pct"], min(cfg["stop_max_pct"], stop))
    return round(stop, 2), round(stop * cfg["reward_risk"], 2)


class RiskAgent:
    def __init__(self, config):
        self.cfg = config
        self.day_start_equity = None
        self.trading_halted = False

    def check(self, decision, price, portfolio, candles=None, open_risk=None):
        if decision["action"] == "HOLD":
            return {"approved": False, "reason": "strategy says HOLD", "qty": 0}
        equity = portfolio.equity()
        if self.day_start_equity is None:
            self.day_start_equity = equity
        day_pnl_pct = (equity - self.day_start_equity) / self.day_start_equity * 100
        if day_pnl_pct <= -self.cfg["daily_loss_limit_pct"]:
            self.trading_halted = True
            return {"approved": False, "qty": 0,
                    "reason": f"daily loss limit hit ({day_pnl_pct:.1f}%) — trading halted"}
        if self.trading_halted:
            return {"approved": False, "reason": "trading halted for today", "qty": 0}

        if decision["action"] == "SELL":
            held = portfolio.position_qty(decision["symbol"])
            if held <= 0:
                return {"approved": False, "reason": "no position to sell (no shorting)", "qty": 0}
            return {"approved": True, "qty": held, "reason": "closing full position",
                    "stop_loss": None, "take_profit": None}

        # BUY: size from risk. Risk budget = % of equity; distance to stop
        # decides how many units that budget can buy. The stop distance
        # breathes with the stock's own volatility.
        stop_pct, take_pct = (stop_take_pct(candles, self.cfg) if candles
                              else (self.cfg["stop_min_pct"],
                                    self.cfg["stop_min_pct"] * self.cfg["reward_risk"]))
        risk_budget = equity * self.cfg["max_risk_per_trade_pct"] / 100
        stop_distance = price * stop_pct / 100
        qty_by_risk = int(risk_budget / stop_distance) if stop_distance > 0 else 0
        max_pct = self.cfg["max_position_pct"]
        if decision.get("uptrend_boost"):
            # Strong-uptrend participation: the council flagged this
            # pick as riding a proven trend, so the size cap rises —
            # the per-trade RISK budget (1%) still binds as before.
            max_pct *= self.cfg.get("uptrend_size_multiple", 1.0)
        max_value = equity * max_pct / 100
        qty_by_size = int(max_value / price)
        qty = min(qty_by_risk, qty_by_size)
        affordable = int(portfolio.cash / price)
        qty = min(qty, affordable)
        # Portfolio-level guard: the TOTAL risk of every open position
        # (last price down to its effective stop — the trailing level
        # once a trail is armed) plus this trade's risk may not exceed
        # max_open_risk_pct of equity. Per-trade limits alone let six
        # correlated tech positions stack into one 6% bet on the same
        # market move; this cap is what keeps a bad week survivable.
        cap_note = ""
        if open_risk:
            cap_pct = self.cfg.get("max_open_risk_pct", 100.0)
            existing = 0.0
            for sym, lv in open_risk.items():
                q = portfolio.position_qty(sym)
                if q <= 0 or not lv.get("stop_loss"):
                    continue
                last = portfolio.last_prices.get(sym, lv["stop_loss"])
                eff_stop = lv["stop_loss"]
                if lv.get("trailing") and lv.get("stop_pct"):
                    eff_stop = max(eff_stop, lv.get("peak", last)
                                   * (1 - lv["stop_pct"] / 100))
                existing += q * max(0.0, last - eff_stop)
            room = equity * cap_pct / 100 - existing
            qty_by_cap = int(room / stop_distance) \
                if stop_distance > 0 and room > 0 else 0
            if qty_by_cap < qty:
                qty = qty_by_cap
                cap_note = (f" | open-risk cap {cap_pct:.0f}% applied "
                            f"(${existing:,.0f} already at risk)")
            if qty <= 0:
                return {"approved": False, "qty": 0,
                        "reason": (f"portfolio open-risk cap reached — "
                                   f"${existing:,.0f} already at risk "
                                   f"({cap_pct:.0f}% of equity)")}
        if qty <= 0:
            return {"approved": False, "reason": "risk rules leave room for 0 units", "qty": 0}
        return {
            "approved": True, "qty": qty,
            "reason": (f"sized by risk: {qty} units, risk budget ${risk_budget:.0f} "
                       f"(volatility stop -{stop_pct:.1f}% / target +{take_pct:.1f}%)"
                       + (" | strong-uptrend participation: size cap raised"
                          if decision.get("uptrend_boost") else "")
                       + cap_note),
            "stop_loss": round(price * (1 - stop_pct / 100), 2),
            "take_profit": round(price * (1 + take_pct / 100), 2),
            # The trailing-stop engine works in percentages, so the
            # verdict carries them alongside the price levels.
            "stop_pct": stop_pct, "take_pct": take_pct,
        }

    def new_day(self):
        self.day_start_equity = None
        self.trading_halted = False
