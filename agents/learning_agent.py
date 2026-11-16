"""LearningAgent — the student who never graduates.

Owns the system's BRAIN (a JSON file on disk). Every closed trade is
recorded here forever: which symbol, which market regime, whether the
Strategy voice or the History voice called it right, and the result.

From that experience it continuously adjusts three things:
  1. TRUST per symbol — symbols it keeps losing on get traded more
     cautiously; proven symbols get more backing.
  2. The EDGE used by the council — the HistoryAgent's study of old
     data is blended with what the system itself has lived through.
  3. The COUNCIL WEIGHTS — if the History voice keeps out-predicting
     the Strategy voice (or the reverse), its weight slowly grows.

The brain is saved after every session and every learn-mode day, and
loaded on every start: day by day, the system begins smarter than it
was. Delete brain.json to reset it to a beginner.
"""
import json
import os

VOICES = ("strategy", "history", "pattern", "regime")

# The full roster: (brain key or None, display name, one-line job).
# Voice agents are scored on their calls; the rest are ranked on service.
ROSTER = [
    ("data", "DataAgent", "brings the real market data"),
    ("technical", "TechnicalAgent", "reads the chart"),
    ("sentiment", "SentimentAgent", "listens to market mood"),
    ("strategy", "StrategyAgent", "VOICE — decides from chart + mood"),
    ("history", "HistoryAgent", "VOICE — 7 years of old-data experience"),
    ("regime", "RegimeAgent", "VOICE — reads the market weather"),
    ("pressure", "PressureAgent", "reads candle pressure"),
    ("pattern", "PatternAgent", "VOICE — recognises winning setups"),
    ("consensus", "ConsensusAgent", "council chair — one best decision"),
    ("learning", "LearningAgent", "everyone's record + learning"),
    ("risk", "RiskAgent", "risk + veto"),
    ("portfolio", "PortfolioAgent", "keeps the accounts"),
    ("execution", "ExecutionAgent", "places the trades"),
    ("reporter", "ReporterAgent", "writes the report"),
]
VOICE_KEYS = {"strategy", "history", "pattern", "regime"}


def _blank_symbol():
    return {"trades": 0, "wins": 0, "pnl_sum": 0.0}


def _service_rank(days):
    for limit, name in ((700, "Legend"), (365, "Master"), (180, "Expert"),
                        (90, "Senior"), (30, "Analyst"), (7, "Junior")):
        if days >= limit:
            return name
    return "Recruit"


def _voice_rank(calls, accuracy):
    """Rank rises with experience AND with being right — past Analyst,
    a voice must earn its promotions with accuracy."""
    if calls < 25:
        return "Recruit"
    rank = "Junior"
    for need_calls, need_acc, name in ((75, 0.45, "Analyst"), (150, 0.48, "Senior"),
                                       (300, 0.52, "Expert"), (600, 0.55, "Master"),
                                       (1200, 0.58, "Legend")):
        if calls >= need_calls and accuracy >= need_acc:
            rank = name
    return rank


class LearningAgent:
    def __init__(self, config):
        self.path = config.get("brain_file", "brain.json")
        self._creator = config.get("creator", "")
        c = config.get("consensus", {})
        self._default_weights = {"w_strategy": c.get("w_strategy", 0.35),
                                 "w_history": c.get("w_history", 0.25),
                                 "w_pattern": c.get("w_pattern", 0.25),
                                 "w_regime": c.get("w_regime", 0.15)}
        self.brain = self._load()

    # ---------- persistence ----------
    def _load(self):
        brain = None
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    brain = json.load(f)
            except (ValueError, OSError):
                brain = None
        if brain is None:
            brain = {"days_learned": 0, "total_trades": 0,
                     "symbols": {}, "regimes": {}, "setups": {},
                     "components": {}, "weights": {}}
        # normalise — older/smaller brains gain the new organs safely
        if self._creator:
            brain.setdefault("creator", self._creator)
        brain.setdefault("days_learned", 0)
        brain.setdefault("total_trades", 0)
        brain.setdefault("symbols", {})
        brain.setdefault("regimes", {})
        brain.setdefault("setups", {})
        brain.setdefault("agents", {})
        # The term scoreboard: every voice's results for the CURRENT
        # 2-year term, across generations — this (and only this)
        # decides the Boss on Award Day. Plus the boss record itself.
        brain.setdefault("term", {"number": 1, "scores": {}})
        brain.setdefault("boss", None)
        brain.setdefault("boss_history", [])
        for name in VOICES:
            brain["term"]["scores"].setdefault(name, {"right": 0, "wrong": 0})
        for name in VOICES:
            brain.setdefault("components", {}).setdefault(
                name, {"right": 0, "wrong": 0})
            row = brain["agents"].setdefault(
                name, {"status": "ACTIVE", "retired_day": None,
                       "reviews_passed": 0, "generation": 1,
                       "past_generations": []})
            row.setdefault("generation", 1)
            row.setdefault("past_generations", [])
        for k, v in self._default_weights.items():
            brain.setdefault("weights", {}).setdefault(k, v)
        return brain

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.brain, f, indent=1)

    # ---------- recording experience ----------
    def record(self, symbol, pnl_pct, strategy_score, history_edge, regime,
               pattern_score=0.0, setup_key=None, regime_bias=0.0):
        b = self.brain
        b["total_trades"] += 1
        for table, key in ((b["symbols"], symbol), (b["regimes"], regime)):
            row = table.setdefault(key, _blank_symbol())
            row["trades"] += 1
            row["wins"] += 1 if pnl_pct > 0 else 0
            row["pnl_sum"] += pnl_pct
        if setup_key:
            # HOW this trade's moment looked — the setup library learns
            # from lived trades too, not only from mined history.
            row = b["setups"].setdefault(
                setup_key, {"trades": 0, "wins": 0, "pnl_sum": 0.0})
            row["trades"] += 1
            row["wins"] += 1 if pnl_pct > 0 else 0
            row["pnl_sum"] += pnl_pct
        won = pnl_pct > 0
        for name, voice in (("strategy", strategy_score),
                            ("history", history_edge),
                            ("pattern", pattern_score),
                            ("regime", regime_bias)):
            if voice == 0:
                continue  # the voice had no opinion on this trade
            if (voice > 0) == won:
                b["components"][name]["right"] += 1
                b["term"]["scores"][name]["right"] += 1
            else:
                b["components"][name]["wrong"] += 1
                b["term"]["scores"][name]["wrong"] += 1
        # Adapt slowly: judge the voices once every 10 trades, not on
        # every single one — otherwise one hot streak lets a single
        # voice swallow the whole council.
        if b["total_trades"] % 10 == 0:
            self._adapt_weights()

    def is_retired(self, name):
        return self.brain["agents"].get(name, {}).get("status") == "RETIRED"

    def is_active(self, name):
        """Only ACTIVE voices speak in the council. A voice on
        probation is scored in shadow — heard, never obeyed."""
        return self.brain["agents"].get(name, {}).get("status", "ACTIVE") == "ACTIVE"

    def _adapt_weights(self):
        """Shift weight from the worst-predicting voice to the best,
        slowly (0.02 at a time), once every voice has enough record.
        Retired voices are never given weight again; the active
        voices' weights are renormalised to sum to 1."""
        comp = self.brain["components"]
        rates = {}
        for name in VOICES:
            if not self.is_active(name):
                continue
            c = comp[name]
            total = c["right"] + c["wrong"]
            if total < 10:
                return
            rates[name] = c["right"] / total
        if len(rates) < 2:
            return
        best = max(rates, key=rates.get)
        worst = min(rates, key=rates.get)
        w = self.brain["weights"]
        if rates[best] - rates[worst] > 0.10:
            w["w_" + best] = round(min(0.55, w["w_" + best] + 0.02), 2)
            w["w_" + worst] = round(max(0.05, w["w_" + worst] - 0.02), 2)
        active = [n for n in VOICES if self.is_active(n)]
        total_w = sum(w["w_" + n] for n in active)
        if total_w > 0:
            for n in active:
                w["w_" + n] = round(w["w_" + n] / total_w, 3)
            drift = round(1.0 - sum(w["w_" + n] for n in active), 3)
            w["w_" + active[0]] = round(w["w_" + active[0]] + drift, 3)

    # ---------- service, reviews, retirement, succession ----------
    def _archive_generation(self, name, day, accuracy, total):
        row = self.brain["agents"][name]
        row["past_generations"].append(
            {"generation": row["generation"], "accuracy": round(accuracy * 100, 1),
             "calls": total, "ended_day": day})
        row["generation"] += 1
        row["retired_day"] = day
        self.brain["components"][name] = {"right": 0, "wrong": 0}
        self.brain["weights"]["w_" + name] = 0.0

    def review(self, day, service_cfg):
        """The 30-day review — and the succession that follows it.

        * An ACTIVE voice whose calls stay below the accuracy bar
          (with enough record to judge fairly) retires: its record is
          archived and a fresh trainee of the same role takes the
          chair on PROBATION — scored in shadow, weight zero.
        * A trainee with enough shadow calls is judged: clear the
          probation bar and it is promoted with a starter weight;
          fail, and it is replaced by the next trainee.
        * The last ACTIVE voice never retires — the council must
          always have someone left to judge."""
        events = []
        agents = self.brain["agents"]
        for name in VOICES:
            row = agents[name]
            c = self.brain["components"][name]
            total = c["right"] + c["wrong"]
            accuracy = c["right"] / total if total else 0.0
            if row["status"] == "PROBATION":
                if total < service_cfg["probation_calls"]:
                    continue
                if accuracy >= service_cfg["probation_accuracy"]:
                    row["status"] = "ACTIVE"
                    self.brain["weights"]["w_" + name] = service_cfg["starter_weight"]
                    events.append({"agent": name, "action": "PROMOTED",
                                   "accuracy": round(accuracy * 100, 1), "calls": total,
                                   "generation": row["generation"]})
                else:
                    self._archive_generation(name, day, accuracy, total)
                    row["status"] = "PROBATION"  # next trainee, same chair
                    events.append({"agent": name, "action": "REPLACED",
                                   "accuracy": round(accuracy * 100, 1), "calls": total,
                                   "generation": row["generation"]})
                continue
            # ACTIVE voice
            if total < service_cfg["retire_min_calls"]:
                continue
            active_count = sum(1 for n in VOICES if self.is_active(n))
            if accuracy < service_cfg["retire_accuracy"] and active_count > 1:
                gen = row["generation"]
                self._archive_generation(name, day, accuracy, total)
                row["status"] = "PROBATION"  # chair refilled at once
                events.append({"agent": name, "action": "RETIRED",
                               "accuracy": round(accuracy * 100, 1), "calls": total,
                               "generation": gen})
            else:
                row["reviews_passed"] += 1
                events.append({"agent": name, "action": "PASSED",
                               "accuracy": round(accuracy * 100, 1), "calls": total})
        self.save()
        return events

    # ---------- Award Day & the Boss ----------
    def boss_name(self):
        return self.brain["boss"]["name"] if self.brain.get("boss") else None

    def award_day(self, day, service_cfg):
        """Two days before the term ends: the voice with the best
        2-year TERM results is crowned Boss for the next term.
        Rank is never consulted — only the term scoreboard: accuracy
        first, total calls as the tiebreak. A Junior with the best
        results beats a Legend with worse ones, every time."""
        scores = self.brain["term"]["scores"]
        eligible = []
        for name in VOICES:
            s = scores[name]
            total = s["right"] + s["wrong"]
            if total >= service_cfg["boss_min_calls"]:
                eligible.append((name, s["right"] / total, total))
        event = {"day": day, "term_ended": self.brain["term"]["number"],
                 "standings": [{"agent": n, "accuracy": round(a * 100, 1), "calls": t}
                               for n, a, t in sorted(eligible, key=lambda x: (-x[1], -x[2]))]}
        if not eligible:
            event["winner"] = None
            self.save()
            return event
        winner, acc, total = max(eligible, key=lambda x: (x[1], x[2]))
        self.brain["boss"] = {"name": winner, "accuracy": round(acc * 100, 1),
                              "calls": total, "crowned_day": day,
                              "term": self.brain["term"]["number"] + 1}
        self.brain["boss_history"].append(dict(self.brain["boss"]))
        event["winner"] = winner
        event["accuracy"] = round(acc * 100, 1)
        event["calls"] = total
        # the new term starts with a clean scoreboard
        self.brain["term"] = {"number": self.brain["term"]["number"] + 1,
                              "scores": {n: {"right": 0, "wrong": 0} for n in VOICES}}
        self.save()
        return event

    def staff_board(self):
        """Every agent's rank, record and status — the staff board."""
        days = self.brain["days_learned"]
        rows = []
        for key, display, role in ROSTER:
            if key in VOICE_KEYS:
                c = self.brain["components"][key]
                total = c["right"] + c["wrong"]
                acc = c["right"] / total if total else 0.0
                agent = self.brain["agents"][key]
                status = agent["status"]
                if self.boss_name() == key and status == "ACTIVE":
                    status = "BOSS — council leader (this term)"
                elif status == "PROBATION":
                    status = f"PROBATION (gen {agent['generation']}, being tested)"
                elif agent["generation"] > 1:
                    status = f"ACTIVE (gen {agent['generation']})"
                rows.append({"name": display, "role": role,
                             "rank": _voice_rank(total, acc),
                             "record": (f"right calls {acc * 100:.0f}% "
                                        f"({total} calls)"),
                             "status": status})
            else:
                rows.append({"name": display, "role": role,
                             "rank": _service_rank(days),
                             "record": f"service day {days}",
                             "status": "ACTIVE"})
        return rows

    def end_of_day(self, day_number):
        self.brain["days_learned"] = max(self.brain["days_learned"], day_number)
        self.save()

    # ---------- what the council consults ----------
    def weights(self):
        return self.brain["weights"]

    def expectancy(self, symbol):
        row = self.brain["symbols"].get(symbol)
        if not row or row["trades"] == 0:
            return None
        return row["pnl_sum"] / row["trades"]

    def trust(self, symbol):
        exp = self.expectancy(symbol)
        row = self.brain["symbols"].get(symbol)
        if exp is None or row["trades"] < 3:
            return 1.0
        return max(0.6, min(1.25, 1.0 + exp / 5.0))

    def blend_edge(self, symbol, studied_edge):
        """Blend the HistoryAgent's old-data study with lived experience."""
        exp = self.expectancy(symbol)
        row = self.brain["symbols"].get(symbol)
        if exp is None or row["trades"] < 5:
            return studied_edge
        lived_edge = max(-1.0, min(1.0, exp / 2.0))
        return round(0.6 * studied_edge + 0.4 * lived_edge, 3)

    def summary(self):
        b = self.brain
        return {"days_learned": b["days_learned"],
                "total_trades": b["total_trades"],
                "weights": dict(b["weights"]),
                "trust": {s: round(self.trust(s), 2) for s in b["symbols"]},
                "expectancy": {s: (None if self.expectancy(s) is None
                                   else round(self.expectancy(s), 2))
                               for s in b["symbols"]}}
