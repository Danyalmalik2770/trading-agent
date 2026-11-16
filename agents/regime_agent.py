"""RegimeAgent — the weather reader.

Classifies what kind of market this is right now (strong uptrend,
uptrend, sideways, volatile, downtrend, strong downtrend) from trend
gap and volatility. Its bias feeds the ConsensusAgent: buying into a
strong downtrend gets damped, buying with a strong uptrend gets
backed. Same signal, different weather, different decision.
"""


class RegimeAgent:
    def analyse(self, candles):
        closes = [c["close"] for c in candles]
        if len(closes) < 35:
            return {"regime": "unknown", "bias": 0.0, "volatility_pct": 0.0}
        sma10 = sum(closes[-10:]) / 10
        sma30 = sum(closes[-30:]) / 30
        gap_pct = (sma10 - sma30) / sma30 * 100
        returns = [(closes[i] - closes[i - 1]) / closes[i - 1] * 100
                   for i in range(1, len(closes))]
        recent = returns[-30:]
        mean = sum(recent) / len(recent)
        vol = (sum((r - mean) ** 2 for r in recent) / len(recent)) ** 0.5
        if vol > 2.2:
            regime, bias = "volatile", -0.2
        elif gap_pct > 1.5:
            regime, bias = "strong_uptrend", 0.8
        elif gap_pct > 0.4:
            regime, bias = "uptrend", 0.4
        elif gap_pct < -1.5:
            regime, bias = "strong_downtrend", -0.9
        elif gap_pct < -0.4:
            regime, bias = "downtrend", -0.5
        else:
            regime, bias = "sideways", 0.0
        return {"regime": regime, "bias": bias,
                "volatility_pct": round(vol, 2), "trend_gap_pct": round(gap_pct, 2)}
