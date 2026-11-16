"""PressureAgent — the candle reader.

Reads who is actually pushing the price right now, candle by candle:
  * body — a candle that opens low and closes high was carried by buyers
  * wicks — a long lower wick means sellers pushed down and buyers
    defended; a long upper wick means buyers pushed up and sellers
    rejected them
  * close position — closing near the high vs near the low
  * volume — a big move on big volume counts more than a quiet drift

Returns a pressure score from -1 (sellers in total control) to +1
(buyers in total control).
"""


class PressureAgent:
    def score(self, candles, lookback=8):
        window = candles[-lookback:]
        if not window:
            return 0.0
        avg_vol = sum(c["volume"] for c in window) / len(window) or 1
        total_w, acc = 0.0, 0.0
        for c in window:
            rng = c["high"] - c["low"]
            if rng <= 0:
                continue
            body = (c["close"] - c["open"]) / rng
            lower_wick = (min(c["open"], c["close"]) - c["low"]) / rng
            upper_wick = (c["high"] - max(c["open"], c["close"])) / rng
            wick_signal = lower_wick - upper_wick
            close_pos = (c["close"] - c["low"]) / rng * 2 - 1
            s = 0.50 * body + 0.25 * wick_signal + 0.25 * close_pos
            w = 0.5 + c["volume"] / avg_vol  # volume-weighted
            acc += s * w
            total_w += w
        if total_w == 0:
            return 0.0
        return max(-1.0, min(1.0, acc / total_w))

    def label(self, score):
        if score > 0.45:
            return "buyers strong"
        if score > 0.15:
            return "buyers"
        if score < -0.45:
            return "sellers strong"
        if score < -0.15:
            return "sellers"
        return "balanced"
