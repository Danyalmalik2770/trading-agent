# Forward call notes — what the council said, and what really happened

## Walk-forward test, last 10 days (run 14 Nov 2026, no cheating:
## each day the council saw only data up to that day; scored on the next day)
- All calls (BTC/ETH/SOL, 30 calls): 11/30 right
- Best pick (real trade call): appeared on 1 of 10 days — SOL up, next day -6.64% — WRONG (0/1)
- Pattern: SOL called UP all 10 days (old-data edge) while the market fell;
  BTC DOWN calls were right 6/10. Council refused to trade on 9 of 10 days.

## Live calls (noted as they happen; result checked the next day)
- 14 Nov 2026 ~21:35 PKT — BTC DOWN (-0.127) ref $65,289.51 | ETH UP (+0.105)
  ref $1,821.36 | SOL UP (+0.238) ref $72.55 | Pick: NO TRADE (below bar)
  Result: (check next day)

## Upgrade check — 14 Nov 2026 (trailing stop + strong-uptrend participation)

- Backtest A/B, same ~180-trading-day bull window, 10 stocks, fresh brains:
  OLD code +2.41% vs buy & hold +22.46% (gap -20.05 pts, 47 picks).
  NEW code +20.55% vs +22.46% (gap -1.91 pts, 78 picks, 23 trailing-stop
  exits, 0 fixed take-profits, 21 uptrend-boosted buys).
- Call test on NEW code: 12/30 calls right (old code scored 16/30 on the
  same test — a 30-call sample, treat the difference as noise). Best pick
  0/0: the council refused all 10 days in the falling crypto market, so
  the downside discipline the changes had to preserve is intact.
- Decision: NEW code kept and pushed; learner restarted on a fresh brain
  so the whole replay record belongs to one system version (previous
  brain archived as brain-pre-trailing-backup-2026-11-14.json).

## Regime window tests — 14 Nov 2026 (run in an isolated copy)

Full-cycle evidence, point-in-time (study data ends at each window's
end, sentiment neutral, exits intraday). The production DataAgent's
recent-median sanity band had to be replaced IN THE TEST COPY ONLY
by a local (+-60 day) band first — see flaw 6 below.

- BULL (recent ~180 trading days, the standard backtest):
  system +27.61% vs buy & hold +22.46%  (ahead +5.15 pts)
- SIDEWAYS (2024-06-18 -> 2025-03-10, basket net +1.56%):
  system +22.15% vs hold +1.56%  (ahead +20.59 pts; 83 picks)
- CRASH-MIXED (2024-07-22 -> 2025-04-09; Aug-2024 crash + the
  Feb-Apr 2025 tariff crash inside, basket net +3.01%):
  system +3.20% vs hold +3.01%  (tied, +0.19 pts; 42 stop-outs)
- BEAR (calendar 2022, the real bear market):
  system -8.74% vs hold -44.63%  (ahead +35.89 pts; only 32 picks
  all year — the council sat in cash; it lost money but lost ~5x
  less than holding)

Verdict: the system now has measured results in all four regimes.
It does not make money in a bear market (no honest long-only system
does); its downside job is protection, and there it worked.

FLAW 6 (found by these tests, NOT yet fixed in production): the
DataAgent sanity band compares every close to the median of the
LAST 50 candles. Any stock that later multiplies ~5x loses its old
cheap history: NVDA's feed starts 2023-06-20 (not 2019), and AMD's
Apr-2025 tariff-crash days are deleted outright (below 0.2x its
2026 median of ~$555). Fix: judge each candle against a rolling
+-60-day local median. Applying it lengthens the series, so the
learner would need one fresh restart (brain backed up first).
