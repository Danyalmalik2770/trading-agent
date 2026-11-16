"""ReporterAgent — the narrator.

Turns the crew's activity into one plain-language report: what was
decided, what was traded, what was vetoed, and where the account
stands. This is the text a human reads at the end of the day.
"""


class ReporterAgent:
    def report(self, decisions, fills, vetoes, portfolio_summary, period_label="run", picks=None, learning=None, top_setups=None, staff=None, data_source=None, boss=None, creator=None, mission=None, benchmark=None):
        lines = [f"=== Trading Agents report ({period_label}) ==="]
        if creator:
            lines.append(f"Creator: {creator} — this whole system was built "
                         f"by him; every agent knows it.")
        if mission:
            lines.append(f"Mission: {mission}")
        if data_source:
            lines.append(f"Data: {data_source}")
        if boss:
            names = {"strategy": "StrategyAgent", "history": "HistoryAgent",
                     "pattern": "PatternAgent", "regime": "RegimeAgent"}
            if boss.get("current"):
                b = boss["current"]
                lines.append(f"BOSS: {names[b['name']]} (term {b['term']} — 2-year "
                             f"results: accuracy {b['accuracy']}% over {b['calls']} calls). "
                             f"Next Award Day: day {boss['next_award_day']}.")
            else:
                lines.append(f"BOSS: none yet — the first Award Day is on day "
                             f"{boss['next_award_day']}.")
            lines.append("The Boss rule: the chair is earned by RESULTS, not rank — "
                         "junior or legend, whoever's 2-year record is best leads "
                         "next. Everyone here is competing for that chair by doing "
                         "their work well.")
        lines.append(f"Decisions made: {len(decisions)} | Trades executed: {len(fills)} | Risk vetoes: {len(vetoes)}")
        if picks is not None:
            lines.append(f"Consensus picks (single best trade per round): {len(picks)}")
        for f in fills:
            lines.append(f"  TRADE  {f['side']:4s} {f['qty']:>5} x {f['symbol']} @ ${f['price']:.2f} (fee ${f['fee']:.2f}) — {f['reason']}")
        grouped = {}
        for v in vetoes:
            key = (v["symbol"], v["reason"])
            grouped[key] = grouped.get(key, 0) + 1
        for (sym, reason), count in grouped.items():
            suffix = f" (x{count})" if count > 1 else ""
            lines.append(f"  VETO   {sym}: {reason}{suffix}")
        ps = portfolio_summary
        lines.append(f"Cash: ${ps['cash']:,.2f} | Equity: ${ps['equity']:,.2f} | "
                     f"Return: {ps['total_return_pct']:+.2f}% | Realised P&L: ${ps['realised_pnl']:+,.2f}")
        if benchmark is not None:
            diff = ps['total_return_pct'] - benchmark
            lines.append(f"Benchmark (buy & hold the same stocks, same period): "
                         f"{benchmark:+.2f}% | System vs benchmark: {diff:+.2f}%")
        if ps["positions"]:
            for sym, p in ps["positions"].items():
                lines.append(f"  OPEN   {sym}: {p['qty']} units @ avg ${p['avg_price']:.2f}")
        else:
            lines.append("  No open positions.")
        if learning:
            w = learning["weights"]
            lines.append(f"Brain: {learning['days_learned']} days learned | "
                         f"{learning['total_trades']} trades of experience | "
                         f"council weights strategy {w['w_strategy']:.2f} / "
                         f"history {w['w_history']:.2f} / pattern {w.get('w_pattern', 0):.2f}")
            for sym, t in learning["trust"].items():
                exp = learning["expectancy"].get(sym)
                lines.append(f"  TRUST  {sym}: {t:.2f} (lived expectancy {exp:+.2f}%/trade)")
        if top_setups:
            lines.append("Best proven setups (from the setup library):")
            for s in top_setups:
                lines.append(f"  SETUP  {s['setup']} — win {s['win_rate']}% | "
                             f"{s['expectancy_pct']:+.2f}%/trade over {s['trades']} samples")
        if staff:
            lines.append("--- Staff board (ranks rise with experience + being right) ---")
            for r in staff:
                lines.append(f"  {r['name']:<18} rank {r['rank']:<8} {r['record']:<28} {r['status']}")
        return "\n".join(lines)
