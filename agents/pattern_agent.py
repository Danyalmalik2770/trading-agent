"""PatternAgent — the one who remembers HOW the wins happened.

Every market moment gets a SIGNATURE — a fingerprint of its conditions:
trend, RSI zone, candle pressure, and position versus the trend line.
The HistoryAgent mines 7 years of data and records, for every
signature, what a trade taken at that moment would have done. That
SETUP LIBRARY is the system's memory of "where the win rate is high"
— and where it is terrible.

When a familiar signature appears again, this agent does not trust
the old memory blindly: it RE-TESTS the setup on the most recent
quarter of the data. If the setup still wins there, it is VERIFIED
and speaks with full weight in the council. If recent data says the
setup has stopped working, its voice is cut down. Memory, verified.
"""
from agents.technical_agent import _rsi
from agents.pressure_agent import PressureAgent

MIN_SAMPLES = 8  # a setup needs at least this much history to be trusted


class PatternAgent:
    def __init__(self):
        self.pressure = PressureAgent()
        self.setups = {}        # library mined from the older 75% of history
        self.verify_setups = {}  # library mined from the newest 25%

    # ---------- fingerprints ----------
    def signature(self, candles):
        closes = [c["close"] for c in candles]
        price = closes[-1]
        sma10 = sum(closes[-10:]) / 10
        sma30 = sum(closes[-30:]) / 30
        sma20 = sum(closes[-20:]) / 20
        gap = (sma10 - sma30) / sma30 * 100
        if gap > 1.5:
            trend = "strong uptrend"
        elif gap > 0.4:
            trend = "uptrend"
        elif gap < -1.5:
            trend = "strong downtrend"
        elif gap < -0.4:
            trend = "downtrend"
        else:
            trend = "flat"
        rsi = _rsi(closes)
        if rsi < 30:
            rsi_zone = "oversold"
        elif rsi < 45:
            rsi_zone = "low"
        elif rsi <= 55:
            rsi_zone = "mid"
        elif rsi <= 70:
            rsi_zone = "high"
        else:
            rsi_zone = "overbought"
        pressure = self.pressure.label(self.pressure.score(candles))
        mom = (price - sma20) / sma20 * 100
        if mom > 3:
            momentum = "far above trend"
        elif mom > 0.8:
            momentum = "above trend"
        elif mom < -3:
            momentum = "far below trend"
        elif mom < -0.8:
            momentum = "below trend"
        else:
            momentum = "at trend"
        return {"trend": trend, "rsi": rsi_zone,
                "pressure": pressure, "momentum": momentum}

    @staticmethod
    def key(sig):
        return "|".join(sig[k] for k in ("trend", "rsi", "pressure", "momentum"))

    @staticmethod
    def describe(key):
        return " + ".join(key.split("|"))

    # ---------- judgement ----------
    def evaluate(self, candles):
        """Score the current moment from the setup library, re-verified
        against recent data. Returns the council-facing pattern view."""
        sig = self.signature(candles)
        k = self.key(sig)
        entry = self.setups.get(k)
        if not entry or entry["trades"] < MIN_SAMPLES:
            return {"signature": sig, "key": k, "score": 0.0,
                    "samples": 0 if not entry else entry["trades"],
                    "win_rate": None, "verified": None}
        expectancy = entry["pnl_sum"] / entry["trades"]
        raw = max(-1.0, min(1.0, expectancy / 2.0))
        win_rate = entry["wins"] / entry["trades"] * 100
        recent = self.verify_setups.get(k)
        if recent and recent["trades"] >= 3:
            recent_exp = recent["pnl_sum"] / recent["trades"]
            if (recent_exp > 0) == (expectancy > 0) and recent_exp != 0:
                return {"signature": sig, "key": k, "score": round(raw, 3),
                        "samples": entry["trades"],
                        "win_rate": round(win_rate, 1), "verified": True}
            return {"signature": sig, "key": k, "score": round(raw * 0.25, 3),
                    "samples": entry["trades"],
                    "win_rate": round(win_rate, 1), "verified": False}
        return {"signature": sig, "key": k, "score": round(raw * 0.6, 3),
                "samples": entry["trades"],
                "win_rate": round(win_rate, 1), "verified": None}

    def top_setups(self, limit=5):
        """The best proven setups in the library — where the win rate
        and expectancy are highest, with enough samples to believe."""
        rows = []
        for k, e in self.setups.items():
            if e["trades"] >= MIN_SAMPLES:
                rows.append({"setup": self.describe(k), "trades": e["trades"],
                             "win_rate": round(e["wins"] / e["trades"] * 100, 1),
                             "expectancy_pct": round(e["pnl_sum"] / e["trades"], 2)})
        rows.sort(key=lambda r: (r["expectancy_pct"], r["win_rate"]), reverse=True)
        return rows[:limit]
