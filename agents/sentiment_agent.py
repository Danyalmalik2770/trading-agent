"""SentimentAgent — the mood reader.

Scores market mood from REAL headlines: Yahoo Finance's public RSS
feed per symbol, scored with a simple word lexicon into -1..+1.
If the feed is unreachable the honest answer is neutral (0.0) —
this agent never invents headlines.
"""
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

POSITIVE = {"surge", "rally", "beat", "beats", "growth", "record", "upgrade",
            "bullish", "profit", "gains", "soars", "strong", "wins", "deal",
            "jumps", "rises", "boost", "optimism", "breakthrough"}
NEGATIVE = {"crash", "plunge", "miss", "misses", "loss", "downgrade", "bearish",
            "falls", "drops", "weak", "lawsuit", "probe", "cuts", "fears",
            "slump", "warning", "recall", "fraud", "decline", "tumbles"}

_CACHE = {}
_CACHE_TTL = 900  # seconds


class SentimentAgent:
    def headlines(self, symbol):
        now = time.time()
        hit = _CACHE.get(symbol)
        if hit and now - hit[0] < _CACHE_TTL:
            return hit[1]
        titles = []
        try:
            url = ("https://feeds.finance.yahoo.com/rss/2.0/headline"
                   f"?s={urllib.parse.quote(symbol)}&region=US&lang=en-US")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                root = ET.fromstring(r.read())
            titles = [t.text for t in root.iter("title")
                      if t.text and len(t.text) > 15][:10]
        except Exception:
            titles = []
        _CACHE[symbol] = (now, titles)
        return titles

    def analyse(self, symbol):
        heads = self.headlines(symbol)
        if not heads:
            return {"score": 0.0, "headlines": [], "source": "none (neutral)"}
        total, scored = 0.0, []
        for h in heads:
            words = {w.strip(".,:;!?\"'()").lower() for w in h.split()}
            s = len(words & POSITIVE) - len(words & NEGATIVE)
            total += s
            scored.append((h, s))
        score = max(-1.0, min(1.0, total / 6.0))
        return {"score": round(score, 3), "headlines": scored,
                "source": "Yahoo Finance RSS"}
