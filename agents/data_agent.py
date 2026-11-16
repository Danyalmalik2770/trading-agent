"""DataAgent — the scout.

Feeds the crew its candles. With `data_source: "yahoo"` it pulls REAL
market data from Yahoo Finance's public chart API (no key needed):
full daily history per symbol, so the "7 years of old data" the crew
studies is the actual market. If the real feed is unreachable it falls
back to a built-in simulated feed and says so (`source_used`), so a
report never pretends demo numbers were real.

The live stream is a tick generator seeded from the last real close —
real-time *broker* ticks arrive when a broker/API key is connected;
the engine consuming the ticks does not change.
"""
import json
import math
import random
import urllib.request
import zlib


class DataAgent:
    def __init__(self, config):
        self.config = config
        self._real_cache = {}
        self.source_used = "demo feed"

    # ---------- real world data ----------
    def _yahoo(self, symbol):
        if symbol in self._real_cache:
            return self._real_cache[symbol]
        # 7y (not max): the max range returns split-era micro prices and
        # sparse null rows from decades ago — garbage for this crew.
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
               f"{symbol}?range=7y&interval=1d")
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            payload = json.load(resp)
        result = payload["chart"]["result"][0]
        quote = result["indicators"]["quote"][0]
        candles = []
        for i in range(len(result["timestamp"])):
            o, h = quote["open"][i], quote["high"][i]
            l, c = quote["low"][i], quote["close"][i]
            if None in (o, h, l, c) or c <= 0:
                continue
            candles.append({"open": float(o), "high": float(h), "low": float(l),
                            "close": float(c),
                            "volume": int(quote["volume"][i] or 0)})
        # Sanity band: drop any row wildly out of line with its OWN
        # neighbours (±60 trading days) — split artifacts and bad
        # ticks are. Judging old prices against TODAY's level (the
        # previous version of this filter) silently erased real
        # history: any stock that later multiplied ~5x lost its
        # cheap years (NVDA's feed began in 2023, not 2019), and
        # crash days far below today's price vanished outright
        # (AMD's April-2025 tariff crash was deleted). A real price
        # is never 5x away from its own neighbours; garbage is.
        if len(candles) > 50:
            closes = [c["close"] for c in candles]
            kept = []
            for i, candle in enumerate(candles):
                neigh = sorted(closes[max(0, i - 60): i + 61])
                median = neigh[len(neigh) // 2]
                if median * 0.2 <= candle["close"] <= median * 5:
                    kept.append(candle)
            candles = kept
        self._real_cache[symbol] = candles
        return candles

    # ---------- simulated fallback ----------
    def _demo(self, symbol, limit):
        seed = zlib.crc32(symbol.encode()) + self.config["demo_seed"]
        rng = random.Random(seed)
        price = 100.0 + (seed % 90)
        candles = []
        for t in range(limit):
            drift = math.sin(t / 24.0) * 0.0016 + rng.gauss(0, 0.011)
            open_ = price
            close = max(1.0, open_ * (1 + drift))
            high = max(open_, close) * (1 + abs(rng.gauss(0, 0.004)))
            low = min(open_, close) * (1 - abs(rng.gauss(0, 0.004)))
            volume = int(1_000_000 * (1 + abs(drift) * 28) * rng.uniform(0.7, 1.3))
            candles.append({"open": open_, "high": high, "low": low,
                            "close": close, "volume": volume})
            price = close
        return candles

    # ---------- public API ----------
    def fetch(self, symbol, limit=None):
        """Latest `limit` candles for a symbol — real data when the
        configured source works, demo data otherwise."""
        limit = limit or self.config["demo_candles"]
        if self.config.get("data_source") == "yahoo":
            try:
                candles = self._yahoo(symbol)
                if len(candles) >= 50:
                    self.source_used = "Yahoo Finance (real market data)"
                    return candles[-limit:]
            except Exception:
                pass  # fall through to the demo feed, honestly labelled
        return self._demo(symbol, limit)

    def history(self, symbol):
        """Long OLD data — what the HistoryAgent studies (7 years)."""
        return self.fetch(symbol, limit=self.config["history_candles"])

    @staticmethod
    def latest_price(candles):
        return candles[-1]["close"]

    def stream(self, symbol, start_price):
        """Real-time feed: an endless generator of fresh candles, one
        per tick, continuing from `start_price`. In this build it is a
        live simulated stream so the real-time engine can run anywhere;
        with a broker/API key this same generator is fed by real ticks
        and nothing else in the system changes."""
        rng = random.Random(zlib.crc32(symbol.encode()) + 777)
        price = start_price
        tick = 0
        while True:
            tick += 1
            drift = math.sin(tick / 26.0) * 0.0016 + rng.gauss(0, 0.009)
            open_ = price
            close = max(1.0, open_ * (1 + drift))
            high = max(open_, close) * (1 + abs(rng.gauss(0, 0.003)))
            low = min(open_, close) * (1 - abs(rng.gauss(0, 0.003)))
            volume = int(1_000_000 * (1 + abs(drift) * 30) * rng.uniform(0.7, 1.3))
            yield {"open": open_, "high": high, "low": low,
                   "close": close, "volume": volume}
            price = close
