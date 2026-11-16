#!/usr/bin/env python3
"""CALL TEST — note what the council says, then check if it was right.

Walk-forward, no cheating: for each of the last N days, the council
sees ONLY the data up to that day (its 7-year study and setup library
are rebuilt from that slice), makes its calls on BTC/ETH/SOL, and we
then score those calls against what the market actually did the
NEXT day. Also tracks the council's single best pick per day — the
trade it would really have taken (only on days it clears its bar).
"""
import sys, json
sys.path.insert(0, '.')
from config import CONFIG
from agents.data_agent import DataAgent
from agents.technical_agent import TechnicalAgent
from agents.sentiment_agent import SentimentAgent
from agents.strategy_agent import StrategyAgent
from agents.history_agent import HistoryAgent
from agents.regime_agent import RegimeAgent
from agents.pattern_agent import PatternAgent
from agents.consensus_agent import ConsensusAgent

SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD"]
N = 10

cfg = json.loads(json.dumps(CONFIG))
cfg["symbols"] = SYMBOLS
full = {s: DataAgent(cfg).history(s) for s in SYMBOLS}
tech, sent = TechnicalAgent(), SentimentAgent()
strat, regime = StrategyAgent(cfg), RegimeAgent()

rows = []
for back in range(N, 0, -1):
    evaluations = []
    for sym in SYMBOLS:
        candles = full[sym][:-back]           # only data up to day T
        history, pattern = HistoryAgent(cfg), PatternAgent()
        study = history.study(sym, candles)
        split = int(len(candles) * 0.75)
        main_lib, verify_lib = {}, {}
        for dst, chunk in ((main_lib, candles[:split]),
                           (verify_lib, candles[split - 40:])):
            for k, e in history.mine_setups(chunk, pattern).items():
                row = dst.setdefault(k, {"trades": 0, "wins": 0, "pnl_sum": 0.0})
                row["trades"] += e["trades"]; row["wins"] += e["wins"]
                row["pnl_sum"] += e["pnl_sum"]
        pattern.setups, pattern.verify_setups = main_lib, verify_lib
        decision = strat.decide(sym, tech.analyse(candles), sent.analyse(sym))
        pat = pattern.evaluate(candles)
        evaluations.append(ConsensusAgent(cfg).evaluate(
            sym, decision, study, regime.analyse(candles),
            pattern_score=pat["score"], trust=1.0))
    pick = ConsensusAgent(cfg).pick_best(evaluations, {s: "BUY" for s in SYMBOLS})
    day = {"date": full[SYMBOLS[0]][-back - 1].get("date", f"T-{back}"),
           "calls": {}, "pick": None}
    for ev in evaluations:
        series = full[ev["symbol"]]
        nxt = series[-back]["close"] / series[-back - 1]["close"] - 1
        said_up = ev["consensus"] > 0
        day["calls"][ev["symbol"]] = {
            "score": ev["consensus"], "said": "UP" if said_up else "DOWN",
            "actual_pct": round(nxt * 100, 2),
            "right": said_up == (nxt > 0)}
    if pick:
        p = day["calls"][pick["symbol"]]
        day["pick"] = {"symbol": pick["symbol"], "strength": pick["strength"],
                       "actual_pct": p["actual_pct"], "right": p["right"]}
    rows.append(day)

total = right = 0
pick_days = pick_right = 0
for d in rows:
    parts = []
    for sym, c in d["calls"].items():
        total += 1; right += 1 if c["right"] else 0
        parts.append(f"{sym.split('-')[0]} said {c['said']} "
                     f"({c['score']:+.2f}) -> {c['actual_pct']:+.2f}% "
                     f"{'RIGHT' if c['right'] else 'wrong'}")
    ptxt = "no trade (council refused)"
    if d["pick"]:
        pick_days += 1; pick_right += 1 if d["pick"]["right"] else 0
        ptxt = (f"PICK {d['pick']['symbol']} strength {d['pick']['strength']} "
                f"-> {d['pick']['actual_pct']:+.2f}% "
                f"{'RIGHT' if d['pick']['right'] else 'wrong'}")
    print(f"{str(d['date'])[:10]} | " + " | ".join(parts) + f" | {ptxt}")
print(f"\nALL CALLS: {right}/{total} right")
print(f"BEST PICK: {pick_right}/{pick_days} right (pick appeared on "
      f"{pick_days} of {len(rows)} days)")
