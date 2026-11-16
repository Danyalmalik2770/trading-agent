"""ConsensusAgent — the council chair.

This is where the whole crew thinks TOGETHER. For every symbol it
blends the StrategyAgent's call, the HistoryAgent's proven edge on old
data, and the RegimeAgent's market bias into ONE consensus score.
Then it compares all symbols and picks only the single BEST trade of
the round — if nothing clears the bar, the council's decision is: no
trade. Cash is a position too.
"""


class ConsensusAgent:
    def __init__(self, config):
        c = config["consensus"]
        self.w_strategy = c["w_strategy"]
        self.w_history = c["w_history"]
        self.w_pattern = c["w_pattern"]
        self.w_regime = c["w_regime"]
        self.min_consensus = c["min_consensus"]
        # Strong-uptrend participation: the bar for a BUY drops by
        # this factor when the symbol's own regime is a strong
        # uptrend (see config). Cash earns nothing in a bull run.
        self.uptrend_threshold_factor = config.get(
            "uptrend_threshold_factor", 1.0)

    def evaluate(self, symbol, strategy_decision, history, regime,
                 pattern_score=0.0, trust=1.0):
        score = (self.w_strategy * strategy_decision["blended_score"]
                 + self.w_history * history["edge"]
                 + self.w_pattern * pattern_score
                 + self.w_regime * regime["bias"])
        score *= trust  # LearningAgent: proven symbols get more backing
        return {"symbol": symbol, "consensus": round(score, 3),
                "strategy_action": strategy_decision["action"],
                "strategy_score": strategy_decision["blended_score"],
                "history_edge": history["edge"], "regime": regime["regime"],
                "regime_bias": regime["bias"],
                "pattern_score": pattern_score}

    def pick_best(self, evaluations, actionable):
        """actionable: {symbol: 'BUY'|'SELL'} — what may be traded now.
        Returns the single strongest consensus trade, or None."""
        best = None
        for ev in evaluations:
            action = actionable.get(ev["symbol"])
            if action is None:
                continue
            strength = ev["consensus"] if action == "BUY" else -ev["consensus"]
            bar = self.min_consensus
            boost = False
            if action == "BUY" and ev.get("regime") == "strong_uptrend":
                # Riding a strong trend: a slightly lower bar, and the
                # pick is flagged so RiskAgent may size it bigger.
                bar = self.min_consensus * self.uptrend_threshold_factor
                boost = True
            if strength < bar:
                continue
            if best is None or strength > best["strength"]:
                best = {"symbol": ev["symbol"], "action": action,
                        "strength": round(strength, 3), "consensus": ev["consensus"],
                        "regime": ev["regime"], "history_edge": ev["history_edge"],
                        "uptrend_boost": boost}
        return best
