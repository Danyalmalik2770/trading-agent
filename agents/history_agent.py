"""HistoryAgent — the elder.

Studies OLD data before anyone trades: it replays the strategy over a
long history for each symbol and measures how that strategy actually
performed there — win rate and expectancy per trade. Symbols where the
strategy historically lost money get a negative "edge" score, so the
ConsensusAgent can avoid them. Old data first, opinions second.
"""
from agents.technical_agent import TechnicalAgent
from agents.risk_agent import stop_take_pct


class HistoryAgent:
    def __init__(self, config):
        self.cfg = config
        self.technical = TechnicalAgent()
        self.cache = {}

    def _simulate_exit(self, candles, i, entry, stop_pct, take_pct):
        """Walk forward from candle i exactly the way the live engine
        exits a trade, so the library scores the system that actually
        trades: the hard stop stands first; reaching the target ARMS
        a trailing stop one stop-distance under the running peak
        instead of selling, and a trailing trade may run up to
        `trailing_horizon` candles; an untriggered trade still exits
        at market after 20 candles. Returns (outcome_pct, exit_i)."""
        n = len(candles)
        stop_level = entry * (1 - stop_pct / 100)
        take_level = entry * (1 + take_pct / 100)
        horizon = self.cfg.get("trailing_horizon", 60) \
            if self.cfg.get("trailing_stop", False) else 20
        trailing = False
        peak = entry
        last = min(i + 20, n - 1)
        j = i + 1
        while j <= last:
            low, high = candles[j]["low"], candles[j]["high"]
            if low <= stop_level:
                return -stop_pct, j
            if trailing:
                trail_level = peak * (1 - stop_pct / 100)
                if low <= trail_level:
                    return (trail_level - entry) / entry * 100, j
                peak = max(peak, high)
            elif high >= take_level:
                trailing = True
                peak = max(peak, high)
                last = min(i + horizon, n - 1)
            j += 1
        return (candles[last]["close"] - entry) / entry * 100, last

    def _replay(self, candles):
        """Replay strategy trades over one slice of candles.
        Returns (expectancy_pct, win_rate_pct, trades)."""
        results, i, n = [], 40, len(candles)
        while i < n - 1:
            window = candles[: i + 1]
            signal = self.technical.analyse(window)
            if signal["signal"] != "BUY":
                i += 1
                continue
            entry = candles[i]["close"]
            stop_pct, take_pct = stop_take_pct(window, self.cfg)
            outcome, i = self._simulate_exit(candles, i, entry,
                                             stop_pct, take_pct)
            results.append(outcome)
            i += 1
        if results:
            wins = sum(1 for r in results if r > 0)
            expectancy = sum(results) / len(results)
            win_rate = wins / len(results) * 100
        else:
            expectancy, win_rate = 0.0, 0.0
        return expectancy, win_rate, len(results)

    @staticmethod
    def _to_edge(expectancy):
        # Scale expectancy (-2%..+2% per trade) into a -1..+1 edge.
        return max(-1.0, min(1.0, expectancy / 2.0))

    def study(self, symbol, candles):
        """The proven edge — with a RECENCY CHECK. The full-history
        edge is re-verified on the newest 25% of the data, the same
        discipline the setup library uses: if recent data contradicts
        the old edge, the edge is cut hard; if it agrees, recent data
        still gets 40% of the say. An edge earned in a market that no
        longer exists must not speak at full volume."""
        if symbol in self.cache:
            return self.cache[symbol]
        exp_full, win_full, n_full = self._replay(candles)
        edge_full = self._to_edge(exp_full)
        split = int(len(candles) * 0.75)
        exp_recent, _, n_recent = self._replay(candles[split - 40:])
        edge_recent = self._to_edge(exp_recent)
        if n_recent >= 8 and edge_full != 0 and \
                (edge_recent > 0) != (edge_full > 0):
            edge, verified = 0.35 * edge_full, False   # contradicted: cut
        elif n_recent >= 8:
            edge, verified = 0.6 * edge_full + 0.4 * edge_recent, True
        else:
            edge, verified = edge_full, "unproven"
        study = {"symbol": symbol, "trades_tested": n_full,
                 "win_rate": round(win_full, 1),
                 "expectancy_pct": round(exp_full, 3),
                 "edge": round(edge, 3),
                 "edge_full": round(edge_full, 3),
                 "edge_recent": round(edge_recent, 3),
                 "edge_verified": verified}
        self.cache[symbol] = study
        return study

    def mine_setups(self, candles, pattern_agent):
        """Replay history and record, for every setup signature, what a
        trade taken at that moment would have done. Returns the setup
        library: {signature_key: {trades, wins, pnl_sum}}."""
        library, i, n = {}, 40, len(candles)
        while i < n - 1:
            window = candles[: i + 1]
            key = pattern_agent.key(pattern_agent.signature(window))
            entry_price = candles[i]["close"]
            stop_pct, take_pct = stop_take_pct(window, self.cfg)
            outcome, i = self._simulate_exit(candles, i, entry_price,
                                             stop_pct, take_pct)
            row = library.setdefault(key, {"trades": 0, "wins": 0, "pnl_sum": 0.0})
            row["trades"] += 1
            row["wins"] += 1 if outcome > 0 else 0
            row["pnl_sum"] += outcome
            i += 1
        return library
