"""StrategyAgent — the decision maker.

Combines the TechnicalAgent's chart signal and the SentimentAgent's
mood score into one decision (BUY / SELL / HOLD) with a confidence
level. It proposes — the RiskAgent still has the final veto.
"""


class StrategyAgent:
    def __init__(self, config):
        self.min_confidence = config["min_confidence"]

    def decide(self, symbol, technical, sentiment):
        # Chart speaks louder than mood: 75% technical, 25% sentiment.
        blended = technical["score"] * 0.75 + sentiment["score"] * 0.25
        confidence = abs(blended)
        if blended > 0.2 and confidence >= self.min_confidence * 0.4:
            action = "BUY"
        elif blended < -0.2 and confidence >= self.min_confidence * 0.4:
            action = "SELL"
        else:
            action = "HOLD"
        if confidence < self.min_confidence * 0.4:
            action = "HOLD"
        return {
            "symbol": symbol, "action": action,
            "confidence": round(min(1.0, confidence), 3),
            "blended_score": round(blended, 3),
            "technical": technical, "sentiment": sentiment,
        }
