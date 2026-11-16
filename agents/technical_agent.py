"""TechnicalAgent — the chart reader.

Computes classic indicators (SMA, EMA, RSI, Bollinger Bands) and votes
BUY / SELL / HOLD with a strength score and a human-readable reason.
It never places trades — it only reports what the chart says.
"""


def _sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return ema


def volatility_pct(candles, lookback=30):
    """Typical daily move (%) — standard deviation of recent returns."""
    closes = [c["close"] for c in candles]
    if len(closes) < 3:
        return 1.0
    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] * 100
               for i in range(1, len(closes))][-lookback:]
    mean = sum(returns) / len(returns)
    return (sum((r - mean) ** 2 for r in returns) / len(returns)) ** 0.5


def _rsi(closes, period=14):
    if len(closes) <= period:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


class TechnicalAgent:
    def analyse(self, candles):
        closes = [c["close"] for c in candles]
        price = closes[-1]
        votes, reasons, score = [], [], 0.0

        sma_fast, sma_slow = _sma(closes, 10), _sma(closes, 30)
        ema_fast = _ema(closes, 12)
        if sma_fast and sma_slow:
            if sma_fast > sma_slow and price > sma_fast:
                votes.append("BUY"); score += 0.35
                reasons.append(f"uptrend: SMA10 {sma_fast:.2f} > SMA30 {sma_slow:.2f}")
            elif sma_fast < sma_slow and price < sma_fast:
                votes.append("SELL"); score -= 0.35
                reasons.append(f"downtrend: SMA10 {sma_fast:.2f} < SMA30 {sma_slow:.2f}")
            else:
                votes.append("HOLD")
                reasons.append("moving averages mixed — no clear trend")
        if ema_fast:
            if price > ema_fast:
                score += 0.10; reasons.append("price above EMA12 (short-term strength)")
            else:
                score -= 0.10; reasons.append("price below EMA12 (short-term weakness)")

        rsi = _rsi(closes)
        if rsi is not None:
            if rsi < 30:
                votes.append("BUY"); score += 0.25
                reasons.append(f"RSI {rsi:.0f} — oversold, bounce likely")
            elif rsi > 70:
                votes.append("SELL"); score -= 0.25
                reasons.append(f"RSI {rsi:.0f} — overbought, pullback likely")
            else:
                reasons.append(f"RSI {rsi:.0f} — neutral zone")

        mid = _sma(closes, 20)
        if mid:
            window = closes[-20:]
            sd = (sum((x - mid) ** 2 for x in window) / 20) ** 0.5
            upper, lower = mid + 2 * sd, mid - 2 * sd
            if price <= lower:
                score += 0.15; reasons.append("price at lower Bollinger band — cheap vs range")
            elif price >= upper:
                score -= 0.15; reasons.append("price at upper Bollinger band — expensive vs range")

        score = max(-1.0, min(1.0, score))
        signal = "BUY" if score > 0.2 else "SELL" if score < -0.2 else "HOLD"
        return {"signal": signal, "score": round(score, 3),
                "rsi": None if rsi is None else round(rsi, 1),
                "reasons": reasons}
