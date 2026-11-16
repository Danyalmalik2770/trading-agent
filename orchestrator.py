"""Orchestrator — the manager.

Runs the full council pipeline, in three modes:

BACKTEST (run): step through history candle by candle.
LIVE (run_live): a real-time engine — a fresh candle streams in for
every symbol each round and the crew analyses it immediately.
LEARN (run_forever): day after day of live sessions that NEVER reset
the brain — every closed trade teaches the LearningAgent, the brain
is saved daily, and each new day starts with everything learned so
far. Runs until stopped (Ctrl+C); nothing learned is ever lost.

Every round works the same:
    Data -> Technical + Sentiment -> Strategy (per symbol)
         -> History edge (7 years of old data, blended with the
            LearningAgent's lived experience) + Regime + Trust
         -> Consensus: ONE council score per symbol, and only the
            single BEST trade of the round is taken
         -> Risk (final veto + sizing) -> Execution -> Portfolio
         -> every closed trade is recorded into the brain
Open positions are watched every round: the stop-loss always stands,
and reaching the take-profit ARMS a trailing stop under the peak
price instead of selling, so winners can run with profits locked.
"""
import time

from agents.data_agent import DataAgent
from agents.technical_agent import TechnicalAgent
from agents.sentiment_agent import SentimentAgent
from agents.strategy_agent import StrategyAgent
from agents.history_agent import HistoryAgent
from agents.regime_agent import RegimeAgent
from agents.pattern_agent import PatternAgent
from agents.consensus_agent import ConsensusAgent
from agents.learning_agent import LearningAgent
from agents.risk_agent import RiskAgent
from agents.portfolio_agent import PortfolioAgent
from agents.execution_agent import ExecutionAgent
from agents.reporter_agent import ReporterAgent


class Orchestrator:
    def __init__(self, config):
        self.cfg = config
        self.data = DataAgent(config)
        self.technical = TechnicalAgent()
        self.sentiment = SentimentAgent()
        self.strategy = StrategyAgent(config)
        self.history = HistoryAgent(config)
        self.regime = RegimeAgent()
        self.pattern = PatternAgent()
        self.consensus = ConsensusAgent(config)
        self.learning = LearningAgent(config)
        self.portfolio = PortfolioAgent(config)
        self.risk = RiskAgent(config)
        self.execution = ExecutionAgent(config, self.portfolio)
        self.reporter = ReporterAgent()
        self.decisions, self.vetoes, self.picks = [], [], []
        self.open_risk = {}
        self.open_context = {}   # symbol -> entry context, for learning
        self.base_studies = {}
        # Historical modes (backtest + day replay) judge old days
        # WITHOUT today's information: sentiment stays neutral there.
        # Only the live session reads real headlines.
        self.historical = False
        self._restore_account()
        self._sync_weights()

    # ---- account persistence ----
    # The brain carries the ACCOUNT as well as the lessons: cash,
    # open positions and their stop/trailing state are saved with it
    # and restored on start, so a restart (crash, watchdog, upgrade)
    # never vaporizes an open trade or silently resets the account.
    def _persist_account(self):
        p = self.portfolio
        self.learning.brain["account"] = {
            "cash": p.cash, "realised_pnl": p.realised_pnl,
            "positions": {s: dict(pos) for s, pos in p.positions.items()},
            "last_prices": dict(p.last_prices),
            "open_risk": {s: dict(v) for s, v in self.open_risk.items()},
            "open_context": {s: dict(v) for s, v in self.open_context.items()}}

    def _restore_account(self):
        acct = self.learning.brain.get("account")
        if not acct:
            return
        p = self.portfolio
        p.cash = float(acct.get("cash", p.cash))
        p.realised_pnl = float(acct.get("realised_pnl", 0.0))
        p.positions = {s: {"qty": int(pos["qty"]),
                           "avg_price": float(pos["avg_price"])}
                       for s, pos in acct.get("positions", {}).items()}
        p.last_prices = {s: float(v)
                         for s, v in acct.get("last_prices", {}).items()}
        self.open_risk = {s: dict(v)
                          for s, v in acct.get("open_risk", {}).items()}
        self.open_context = {s: dict(v)
                             for s, v in acct.get("open_context", {}).items()}

    # ---- learning glue ----
    def _sync_weights(self):
        w = dict(self.learning.weights())
        boss = self.learning.boss_name()
        if boss and self.learning.is_active(boss):
            # The Boss leads the council: its voice carries the bonus.
            w["w_" + boss] = round(w["w_" + boss] * self.cfg["service"]["boss_weight_bonus"], 3)
            active = [n for n in ("strategy", "history", "pattern", "regime")
                      if self.learning.is_active(n)]
            total = sum(w["w_" + n] for n in active)
            if total > 0:
                for n in active:
                    w["w_" + n] = round(w["w_" + n] / total, 3)
        for name in ("strategy", "history", "pattern", "regime"):
            setattr(self.consensus, "w_" + name,
                    w["w_" + name] if self.learning.is_active(name) else 0.0)

    @staticmethod
    def _merge_library(dst, src):
        for k, e in src.items():
            row = dst.setdefault(k, {"trades": 0, "wins": 0, "pnl_sum": 0.0})
            row["trades"] += e["trades"]
            row["wins"] += e["wins"]
            row["pnl_sum"] += e["pnl_sum"]

    def _prepare(self, books_hist=None):
        # 7 years of old data: per-symbol edge study + the setup library.
        # The library is mined on the older 75%; the newest 25% is mined
        # separately and used only to RE-VERIFY setups before trusting
        # them (test it again — is the result still the same?).
        # books_hist (replay mode) supplies slices that end TODAY —
        # the crew then studies only what it could really have known.
        main_lib, verify_lib = {}, {}
        for s in self.cfg["symbols"]:
            hist = books_hist[s] if books_hist else self.data.history(s)
            self.base_studies[s] = self.history.study(s, hist)
            split = int(len(hist) * 0.75)
            self._merge_library(main_lib, self.history.mine_setups(hist[:split], self.pattern))
            self._merge_library(verify_lib, self.history.mine_setups(hist[split - 40:], self.pattern))
        # setups the system itself has lived through join the library
        self._merge_library(main_lib, self.learning.brain["setups"])
        self.pattern.setups = main_lib
        self.pattern.verify_setups = verify_lib
        self._sync_weights()

    def _effective_study(self, symbol):
        study = dict(self.base_studies[symbol])
        study["edge"] = self.learning.blend_edge(symbol, study["edge"])
        return study

    def _record_close(self, symbol, exit_price):
        ctx = self.open_context.pop(symbol, None)
        if ctx is None:
            return
        pnl_pct = (exit_price - ctx["entry"]) / ctx["entry"] * 100
        self.learning.record(symbol, pnl_pct, ctx["strategy_score"],
                             ctx["history_edge"], ctx["regime"],
                             pattern_score=ctx.get("pattern_score", 0.0),
                             setup_key=ctx.get("setup_key"),
                             regime_bias=ctx.get("regime_bias", 0.0))
        if ctx.get("setup_key"):
            row = self.pattern.setups.setdefault(
                ctx["setup_key"], {"trades": 0, "wins": 0, "pnl_sum": 0.0})
            row["trades"] += 1
            row["wins"] += 1 if pnl_pct > 0 else 0
            row["pnl_sum"] += pnl_pct

    # ---- shared round logic ----
    def _round(self, books):
        evaluations, prices = [], {}
        for symbol in self.cfg["symbols"]:
            candles = books[symbol]
            price = candles[-1]["close"]
            prices[symbol] = price
            self.portfolio.mark(symbol, price)
            self._watch_exits(symbol, candles[-1])
        for symbol in self.cfg["symbols"]:
            candles = books[symbol]
            tech = self.technical.analyse(candles)
            if self.historical:
                # Point-in-time honesty: an old day is judged without
                # today's headlines — the mood score stays neutral.
                sent = {"score": 0.0, "headlines": [],
                        "source": "neutral (historical mode)"}
            else:
                sent = self.sentiment.analyse(symbol)
            decision = self.strategy.decide(symbol, tech, sent)
            self.decisions.append(decision)
            regime = self.regime.analyse(candles)
            pattern = self.pattern.evaluate(candles)
            evaluations.append(self.consensus.evaluate(
                symbol, decision, self._effective_study(symbol), regime,
                pattern_score=pattern["score"],
                trust=self.learning.trust(symbol)))
            evaluations[-1]["pattern"] = pattern
        actionable = {}
        for symbol in self.cfg["symbols"]:
            actionable[symbol] = ("SELL" if self.portfolio.position_qty(symbol) > 0
                                  else "BUY")
        pick = self.consensus.pick_best(evaluations, actionable)
        if pick is None:
            return
        self.picks.append(pick)
        decision = {"symbol": pick["symbol"], "action": pick["action"],
                    "confidence": pick["strength"],
                    "uptrend_boost": bool(pick.get("uptrend_boost"))}
        verdict = self.risk.check(decision, prices[pick["symbol"]], self.portfolio,
                                  candles=books[pick["symbol"]],
                                  open_risk=self.open_risk)
        if verdict["approved"]:
            fill = self.execution.execute(
                pick["symbol"], pick["action"], verdict["qty"], prices[pick["symbol"]],
                reason=(f"consensus pick {pick['strength']:.2f} "
                        f"(regime {pick['regime']}, history edge {pick['history_edge']:+.2f}); "
                        f"{verdict['reason']}"))
            if fill and pick["action"] == "BUY" and verdict.get("stop_loss"):
                self.open_risk[pick["symbol"]] = {
                    "stop_loss": verdict["stop_loss"],
                    "take_profit": verdict["take_profit"],
                    "entry": prices[pick["symbol"]],
                    "peak": prices[pick["symbol"]],
                    "stop_pct": verdict.get("stop_pct"),
                    "trailing": False}
                ev = next(e for e in evaluations if e["symbol"] == pick["symbol"])
                self.open_context[pick["symbol"]] = {
                    "entry": prices[pick["symbol"]],
                    "strategy_score": ev["strategy_score"],
                    "history_edge": ev["history_edge"],
                    "regime": ev["regime"],
                    "pattern_score": ev["pattern_score"],
                    "regime_bias": ev["regime_bias"],
                    "setup_key": ev["pattern"]["key"]}
            if fill and pick["action"] == "SELL":
                self.open_risk.pop(pick["symbol"], None)
                self._record_close(pick["symbol"], prices[pick["symbol"]])
        else:
            self.vetoes.append({"symbol": pick["symbol"], "reason": verdict["reason"]})

    def _watch_exits(self, symbol, candle):
        """Exits are checked the way a real stop actually triggers:
        against the day's LOW and HIGH, not just the close — the same
        rules the HistoryAgent's library simulation uses, so the
        backtest and the crew's memory finally agree. A gap through
        a level fills at the open (worse); an intraday touch fills
        at the level."""
        levels = self.open_risk.get(symbol)
        qty = self.portfolio.position_qty(symbol)
        if not levels or qty <= 0:
            return
        close = candle["close"]
        low = candle.get("low", close)
        high = candle.get("high", close)
        opening = candle.get("open", close)
        # The hard stop always stands guard first.
        if low <= levels["stop_loss"]:
            fill = opening if opening < levels["stop_loss"] \
                else levels["stop_loss"]
            self.execution.execute(symbol, "SELL", qty, fill, reason="stop-loss hit")
            del self.open_risk[symbol]
            self._record_close(symbol, fill)
            return
        if not self.cfg.get("trailing_stop", False) or not levels.get("stop_pct"):
            if high >= levels["take_profit"]:
                self.execution.execute(symbol, "SELL", qty, levels["take_profit"],
                                       reason="take-profit hit")
                del self.open_risk[symbol]
                self._record_close(symbol, levels["take_profit"])
            return
        # Trailing mode: an armed trail is checked against the peak
        # BEFORE today's high is added (the exit cannot use a peak
        # the day has not proven yet when its low came first).
        if levels.get("trailing"):
            trail_level = levels["peak"] * (1 - levels["stop_pct"] / 100)
            if low <= trail_level:
                fill = opening if opening < trail_level else trail_level
                self.execution.execute(
                    symbol, "SELL", qty, fill,
                    reason=f"trailing stop hit (peak ${levels['peak']:.2f} — profit locked)")
                del self.open_risk[symbol]
                self._record_close(symbol, fill)
                return
        # Follow the peak; reaching the old target ARMS the trail
        # instead of selling — the winner keeps running, and the exit
        # sits one stop-distance below the highest price seen, so
        # most of the profit stays locked in.
        levels["peak"] = max(levels.get("peak", close), high)
        if not levels.get("trailing") and high >= levels["take_profit"]:
            levels["trailing"] = True

    def _close_all(self, books):
        for symbol in self.cfg["symbols"]:
            qty = self.portfolio.position_qty(symbol)
            if qty > 0:
                price = books[symbol][-1]["close"]
                self.execution.execute(symbol, "SELL", qty, price, reason="session end — flat overnight")
                self.open_risk.pop(symbol, None)
                self._record_close(symbol, price)

    def _report(self, label):
        days = self.learning.brain["days_learned"]
        term = self.cfg["service"]["term_days"]
        next_award = ((days // term) + 1) * term - self.cfg["service"]["award_before_term_end"]
        return self.reporter.report(
            self.decisions, self.execution.fills, self.vetoes,
            self.portfolio.summary(), picks=self.picks,
            learning=self.learning.summary(),
            top_setups=self.pattern.top_setups(),
            staff=self.learning.staff_board(),
            boss={"current": self.learning.brain.get("boss"),
                  "next_award_day": next_award},
            creator=self.cfg.get("creator"),
            mission=self.cfg.get("mission"),
            benchmark=getattr(self, "_benchmark_pct", None),
            data_source=self.data.source_used, period_label=label)

    # ---- backtest mode ----
    def run(self, warmup=40):
        self.historical = True
        self._prepare()
        books = {s: self.data.fetch(s) for s in self.cfg["symbols"]}
        n = min(len(h) for h in books.values())
        live_books = {s: [] for s in self.cfg["symbols"]}
        for i in range(n):
            for s in self.cfg["symbols"]:
                live_books[s].append(books[s][i])
            if i + 1 >= warmup:
                # Each candle is a new trading DAY: the RiskAgent's
                # daily loss limit gets its fresh start here. (This
                # call was missing — the "daily" halt once measured
                # against the first day's equity forever and, once
                # tripped, vetoed every trade until the process died.)
                self.risk.new_day()
                self._round(live_books)
        # The honest scoreboard: what simply buying & holding the same
        # stocks over the same window would have done.
        self._benchmark_pct = round(
            sum(books[s][n - 1]["close"] / books[s][warmup - 1]["close"] - 1
                for s in self.cfg["symbols"]) / len(self.cfg["symbols"]) * 100, 2)
        self._persist_account()
        self.learning.save()
        return self._report(f"backtest, {n - warmup} rounds")

    # ---- real-time mode ----
    def run_live(self, rounds=None):
        rounds = rounds or self.cfg["live_rounds"]
        self._prepare()
        books, streams = {}, {}
        for s in self.cfg["symbols"]:
            hist = self.data.fetch(s)
            books[s] = list(hist[-120:])
            streams[s] = self.data.stream(s, hist[-1]["close"])
        for _ in range(rounds):
            for s in self.cfg["symbols"]:
                books[s].append(next(streams[s]))
            self._round(books)
        self._persist_account()
        self.learning.save()
        return self._report(f"LIVE session, {rounds} rounds (streamed ticks)")

    # ---- never-ending learning mode: REAL days, replayed ----
    def run_forever(self, days=None, log=print, pace_seconds=0.0):
        """Day after day of REAL market history, replayed in order.
        Each system day is one actual trading day: the crew studies
        only the data up to that day (no look-ahead), trades its paper
        portfolio on that day's real candles, positions ride until
        their stop or target is hit on a later real day, and the brain
        saves everything. When the replay catches up with the present,
        forever mode waits for genuinely new trading days and then
        continues on them. `days=None` means never stop."""
        cfg = self.cfg
        self.historical = True
        hist = {s: self.data.history(s) for s in cfg["symbols"]}
        shortest = min(len(h) for h in hist.values())
        replay_total = min(cfg.get("replay_days", 800), shortest - 500)
        brain = self.learning.brain
        done_total = brain.get("replay_done", 0)
        if "bench_start" not in brain:
            brain["bench_start"] = {
                s: hist[s][len(hist[s]) - replay_total]["close"]
                for s in cfg["symbols"]}
        day = brain["days_learned"]
        done = 0
        slices = None
        waited = False
        try:
            while days is None or done < days:
                if done_total >= replay_total:
                    if days is not None:
                        break
                    if not waited:
                        log("Caught up with real market history — waiting "
                            "for new trading days.")
                        waited = True
                    time.sleep(600)
                    fresh = {s: self.data.history(s) for s in cfg["symbols"]}
                    new_shortest = min(len(h) for h in fresh.values())
                    if new_shortest > shortest:
                        replay_total += new_shortest - shortest
                        shortest = new_shortest
                        hist = fresh
                        waited = False
                    continue
                day += 1
                done += 1
                done_total += 1
                slices = {s: hist[s][: len(hist[s]) - replay_total + done_total]
                          for s in cfg["symbols"]}
                self._prepare(slices)
                fills_before = len(self.execution.fills)
                trades_before = brain["total_trades"]
                self.risk.new_day()   # a real new day: daily limits reset
                self._round(slices)
                brain["replay_done"] = done_total
                bs = brain["bench_start"]
                self._benchmark_pct = round(
                    sum(slices[s][-1]["close"] / bs[s] - 1
                        for s in cfg["symbols"]) / len(cfg["symbols"]) * 100, 2)
                self._persist_account()
                self.learning.end_of_day(day)
                service = self.cfg["service"]
                if day % service["review_every_days"] == 0:
                    events = self.learning.review(day, service)
                    if not events:
                        log(f"Day {day} REVIEW: no voice has reached "
                            f"{service['retire_min_calls']} scored calls yet — everyone stays ACTIVE")
                    for e in events:
                        display = {"strategy": "StrategyAgent", "history": "HistoryAgent",
                                   "pattern": "PatternAgent", "regime": "RegimeAgent"}[e["agent"]]
                        if e["action"] == "RETIRED":
                            log(f"Day {day} REVIEW: {display} (gen {e['generation']}) RETIRED — "
                                f"accuracy {e['accuracy']}% over {e['calls']} calls (bar "
                                f"{service['retire_accuracy'] * 100:.0f}%). The chair is not "
                                f"empty: a new trainee has taken it on PROBATION — it will "
                                f"be tested in shadow for {service['probation_calls']} calls.")
                        elif e["action"] == "PROMOTED":
                            log(f"Day {day} REVIEW: {display} trainee (gen {e['generation']}) "
                                f"PROMOTED — probation accuracy {e['accuracy']}% over "
                                f"{e['calls']} calls. It may now speak in the council.")
                        elif e["action"] == "REPLACED":
                            log(f"Day {day} REVIEW: {display} trainee FAILED probation "
                                f"(accuracy {e['accuracy']}%) — removed, and a gen "
                                f"{e['generation']} trainee has taken the chair.")
                        else:
                            log(f"Day {day} REVIEW: {display} PASSED — accuracy "
                                f"{e['accuracy']}% over {e['calls']} calls")
                if day % service["term_days"] == service["term_days"] - service["award_before_term_end"]:
                    ev = self.learning.award_day(day, service)
                    log(f"Day {day} *** AWARD DAY *** — 2 days left in the 2-year "
                        f"term. Final results of term {ev['term_ended']}:")
                    for s in ev["standings"]:
                        dn = {"strategy": "StrategyAgent", "history": "HistoryAgent",
                              "pattern": "PatternAgent", "regime": "RegimeAgent"}[s["agent"]]
                        log(f"    {dn}: accuracy {s['accuracy']}% over {s['calls']} calls")
                    if ev["winner"]:
                        dn = {"strategy": "StrategyAgent", "history": "HistoryAgent",
                              "pattern": "PatternAgent", "regime": "RegimeAgent"}[ev["winner"]]
                        log(f"*** NEW BOSS: {dn} *** — accuracy {ev['accuracy']}% "
                            f"({ev['calls']} calls). Rank was not consulted, only "
                            f"results. It will lead the council for the next 2 "
                            f"years; its voice carries the most weight.")
                    else:
                        log("*** No one's record this term was enough for the "
                            "chair — it stays empty until the next Award Day. ***")
                self._sync_weights()
                summary = self.learning.summary()
                log(f"Day {day} (real market day {done_total}/{replay_total}): "
                    f"{len(self.execution.fills) - fills_before} fills | "
                    f"{self.learning.brain['total_trades'] - trades_before} trades learned | "
                    f"experience {summary['total_trades']} trades | "
                    f"weights strategy {summary['weights']['w_strategy']:.2f} / "
                    f"history {summary['weights']['w_history']:.2f} | "
                    f"trust " + ", ".join(f"{s} {t:.2f}" for s, t in summary["trust"].items()))
                if pace_seconds:
                    time.sleep(pace_seconds)
        except KeyboardInterrupt:
            self._persist_account()
            self.learning.save()
            log("Stopped — brain saved. Nothing learned was lost.")
        if days is not None and slices:
            self._close_all(slices)
            self._persist_account()
            self.learning.save()
        return self._report(f"learn mode — REAL day replay, {done} day(s)")
