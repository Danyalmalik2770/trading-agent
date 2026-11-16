<p align="center">
  <img src="docs/logo-banner.png" alt="Trading Agents logo" width="560">
</p>

<h1 align="center">Trading Agents</h1>

<p align="center">
  <strong>A council of 14 AI agents that study 7 years of real market data,<br>
  take only the single best trade — and learn from every one of them.</strong>
</p>

<p align="center">
  <a href="#run-it-on-your-pc">Run it</a> &nbsp;|&nbsp;
  <a href="#how-it-works">How it works</a> &nbsp;|&nbsp;
  <a href="#the-crew">The Crew</a> &nbsp;|&nbsp;
  <a href="#watch-how-to-run-it-video">Watch</a> &nbsp;|&nbsp;
  <a href="#measured-results--paper-money-only">Results</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Agents-14-blueviolet" alt="14 agents">
  <img src="https://img.shields.io/badge/Paper%20Trading-Only-orange" alt="Paper trading only">
  <img src="https://img.shields.io/badge/Data-Yahoo%20Finance%20(real)-teal" alt="Real Yahoo Finance data">
</p>

---
**Mission:** earn a name in the world through good work. This project is
**open source (MIT License — see `LICENSE`)**. The crew's work is
public, which is exactly why it has to be good.

A crew of **14 specialised agents** that trade together as a council —
each agent has exactly one job, they study **7 years of real market
data** before deciding, they take only the **single best trade** at a
time, and they **learn from every trade, every day, without stopping**.
It is a **paper-trading** system: the prices are real, the money is
simulated, no broker is connected and no real order can be placed.

---

## How it works

### 1. First, they study — 7 years of old data
Before any decision, the crew loads ~1,764 daily candles (7 years) per
stock from Yahoo Finance's public API. The `HistoryAgent` replays its
strategy over that history and scores each stock's proven edge — where
this strategy made money before, and where it lost. That edge is then
**re-verified on the newest 25% of the data**: if recent trading
contradicts the old edge, it is cut hard; if it agrees, recent data
still gets 40% of the say. An edge earned in a market that no longer
exists does not speak at full volume.

### 2. Every market moment gets a fingerprint
The `PatternAgent` turns each moment into a **setup**: trend + RSI zone
+ candle pressure (the `PressureAgent` reads bodies, wicks, close
position and volume to say whether buyers or sellers are pushing) +
position versus the trend line. Seven years of history are mined into
a **setup library**: for every setup, what a trade taken at that
moment would have done — win rate and average result. That library is
the crew's memory of *how its wins happened* and *where the win rate
is highest*. When a familiar setup appears again, it is **re-verified
on the newest 25% of the data** first — a setup that has stopped
working loses its voice.

### 3. The council decides — one best trade only
Every round, four voices score every stock:

| Voice | What it judges |
|---|---|
| **Strategy** | The chart (SMA/EMA, RSI, Bollinger) + market mood |
| **History** | The proven edge on 7 years of old data |
| **Pattern** | The current setup's library record, re-verified |
| **Regime** | The market weather — uptrend, downtrend, sideways, volatile |

The `ConsensusAgent` blends the four into one score per stock and
picks only the **single best trade of the round** — if nothing clears
the bar, the decision is *no trade*. Cash is a position too.

One exception, earned by the weather: when a stock's own regime is a
**strong uptrend**, the council lowers its bar slightly (×0.75) and
flags the pick for a bigger size — in a proven bull run, sitting in
cash waiting for a perfect setup costs more than riding the trend.

### 4. The bodyguard checks every trade
The `RiskAgent` sizes each trade from fixed risk rules (max 1% of the
account risked per trade, max 20% in one position — 30% for a flagged
strong-uptrend pick, trading halts after a −3% day — a limit that
resets every trading day — and total risk across all open positions
capped at 4% of equity) and can **veto** anything. Stop-loss and take-profit are **volatility-aware**: the
stop sits at 1.5× the stock's typical daily move (target twice as
far) — the crew's own library proved a flat 2% stop gets shaken out
by ordinary noise on real stocks.

Reaching the target does **not** sell the trade. It arms a **trailing
stop**: the exit then follows one stop-distance below the highest
price the trade has reached, so a winner can run with the trend while
its profit stays locked in. The hard stop-loss stands guard the whole
time. The HistoryAgent's replay and the setup library score every
trade with these same exit rules, so the crew's memory describes the
system that actually trades. Measured on the same ~180-trading-day
bull window, version by version: the original system returned
**+2.4%**; adding the trailing stop and uptrend participation took
it to **+20.6%**; then a pro-trader audit round fixed five flaws —
the daily loss limit never reset (it now resets every trading day),
the account was not saved (cash and open positions now live in the
brain and survive restarts — verified by a stop/restart test),
historical tests were scored using today's headlines (sentiment is
now neutral in backtest/replay; live headlines only in live mode),
exits were checked only at the close (they now trigger on the day's
low/high, exactly like the library simulation), and there was no cap
on total open risk (now 4% of equity) — and the system returned
**+27.6%** against the +22.5% buy & hold benchmark, ahead by 5
points, while in a falling crypto market the council still refused
every trade for 10 straight days. One window is evidence, not
proof; the learner keeps testing it on new real days.

### 5. They learn — every day, without stopping
Every closed trade is written into a persistent **brain**
(`brain.json`): which stock, which setup, which regime, which voices
called it right. The brain also carries the account itself — cash,
open positions and their stop/trailing state — so a restart never
loses a trade in progress. In `learn` mode each system day is **one real market
day, replayed in order**: the crew studies only the data up to that
day (no look-ahead), trades on that day's real candles, and lets
positions ride until a later day's stop or trailing exit. When the replay
catches up with the present, it waits for genuinely new trading days
and continues on those. From that experience the `LearningAgent`
continuously:

- adjusts each stock's **trust** (proven stocks get backing, losers get caution),
- blends lived experience into the History edge,
- grows the setup library with real lived trades,
- slowly shifts the council's weights toward the voice that predicts best.

The brain is saved after every day and reloaded on every start — each
day begins with everything learned so far. **Delete `brain.json` to
reset the system to a beginner.**

### 6. Ranks, reviews, retirement — and the Boss
Every agent has a **rank** (Recruit → Junior → Analyst → Senior →
Expert → Master → Legend) on the staff board in every report. Ranks
rise with experience; for the four voices, promotions past Analyst
also require accuracy. The crew serves a **2-year term (730 days)**
with a formal **review every 30 days**:

- A voice whose calls stay below **40% accuracy** (over at least 50
  scored calls) **retires itself** — record archived, weight zero.
- The chair is never empty: a fresh **trainee** takes it on
  **probation**, scored in shadow (heard, not obeyed) for 25 calls.
  Clear 45% and it is promoted; fail and the next trainee tries.
- Two days before the term ends comes **Award Day**: the term
  scoreboard is read out and the voice with the **best 2-year
  results** — rank is never consulted — is crowned **Boss** for the
  next term, with a 1.5× weight bonus in the council.

The working agents (data, risk, accounting, execution, reporting)
never retire — only opinion chairs rotate.

## The crew

| Agent | Its one job |
|---|---|
| `DataAgent` | Fetches real OHLCV candles from Yahoo Finance (demo feed as an honestly-labelled fallback) |
| `TechnicalAgent` | Reads the chart — SMA/EMA trend, RSI, Bollinger Bands — and votes with reasons |
| `SentimentAgent` | Scores market mood from **real** Yahoo Finance headlines (−1 to +1); no headlines, no opinion — never invented |
| `StrategyAgent` | Combines chart + mood into BUY / SELL / HOLD with a confidence level |
| `HistoryAgent` | Studies old data: replays the strategy over 7 years per symbol and scores its proven edge |
| `RegimeAgent` | Reads the market weather and biases decisions accordingly |
| `PressureAgent` | Reads candle pressure — who is actually pushing the price, buyers or sellers |
| `PatternAgent` | Remembers how the wins happened: setup fingerprints, the library, re-verification |
| `ConsensusAgent` | **The council chair.** Blends the four voices and picks the single best trade — or none |
| `LearningAgent` | **The student who never graduates.** Owns the brain: trust, weights, ranks, reviews, retirements, the Boss |
| `RiskAgent` | Sizes every trade, sets volatility-aware stop/target, and can **veto** any trade |
| `PortfolioAgent` | The accountant: cash, positions, equity, realised P&L |
| `ExecutionAgent` | Places paper fills with fees + slippage (the only class a real broker would ever replace) |
| `ReporterAgent` | Writes the plain-language report, including the staff board |

---

## Watch: how to run it (video)

[![How to run this repo on your PC](https://files.catbox.moe/pooqkv.png)](https://files.catbox.moe/oxh6nx.mp4)

A 76-second 2D explainer with narration: install Python, download the
repo, open a terminal, run it, watch it learn. **Click the image to
play the video.**

## Run it on your PC

### The web terminal (recommended)

```bash
python gui.py
```

Your browser opens a pro-style trading terminal: a live ticker tape
of the crew's symbols, a real candlestick chart (Yahoo Finance data,
click any symbol on the tape to switch), the council panel with
**Start Learning / Backtest / Stop** buttons that run the same
commands as the terminal below and stream their output live, the
risk guard for the selected position, and the full positions table —
all read live from `brain.json`. Standard library only, runs on
`127.0.0.1` on your own machine. `python gui.py --no-open` serves
without opening a browser; `--port 9000` changes the port.

### Or the plain terminal

You only need **Python 3.10 or newer**. There is nothing to install —
the system uses only Python's standard library — and an internet
connection (for the real price data).

### Windows

1. Install Python from [python.org/downloads](https://www.python.org/downloads/)
   — on the first install screen, **tick "Add python.exe to PATH"**,
   then finish the install.
2. Download this project: green **Code** button (top of this page) →
   **Download ZIP** → unzip it anywhere, e.g. your Desktop.
3. Open the unzipped `trading-agent` folder, click the address bar in
   Explorer, type `powershell` and press Enter — a terminal opens
   right inside the folder. (Or open PowerShell and `cd` to the folder.)
4. Run a command from the table below, e.g.:

```powershell
python main.py learn 5
```

### Mac / Linux

1. Python 3 is usually already installed; check with `python3 --version`
   (otherwise install it from python.org or your package manager).
2. Clone or download this repo, open a terminal in the folder:

```bash
cd trading-agent
python3 main.py learn 5
```

### The commands

| Command | What it does |
|---|---|
| `python main.py` | A backtest over real history, then a short live session |
| `python main.py backtest` | Backtest only — the crew trades through the last ~220 real trading days, candle by candle |
| `python main.py live` | One real-time session — a fresh candle streams in every round and is analysed at once |
| `python main.py learn` | **Learn forever**: replays real market days in order (the most recent ~800 trading days), one day every ~5 seconds, brain saved daily — then waits for and trades each genuinely new day. `Ctrl+C` stops it — nothing learned is lost |
| `python main.py learn 30` | Learn for exactly 30 days (at full speed), then print the full report — day 30 includes the first formal **review** |

(Use `python3` instead of `python` on Mac/Linux.)

### What you will see

During `learn`, one line per day — fills, trades learned, total
experience, the council's current weights and each stock's trust:

```
Day 30: 8 fills | 4 trades learned | experience 213 trades | weights strategy 0.33 / history 0.25 | trust AAPL 1.25, MSFT 1.25, TSLA 0.60
Day 30 REVIEW: PatternAgent PASSED — accuracy 78.0% over 123 calls
```

Every run ends with a full report: the trades taken and why, cash /
equity / return, the brain's state, the **best proven setups** from
the library, and the **staff board** — every agent's rank, record and
status (including who is on probation, and who is Boss). Every report
also prints the honest scoreboard: a **buy & hold benchmark** for the
same stocks over the same period, next to the system's return — the
system is only doing well if it beats doing nothing.

### If it stops

Just run the same command again. The brain file carries everything
the crew has learned, so the system continues from where it stopped —
same day count, same trust, same weights, same ranks.

### Settings

Everything shared lives in `config.py`: the stock symbols
(10 large US stocks by default: AAPL, MSFT, TSLA, NVDA, AMZN, GOOGL,
META, AMD, NFLX, JPM), starting cash ($100,000 paper),
risk limits, the council weights, and the service rules (term length,
review day, retirement and probation bars, Award Day). Edit, save,
run again.

---

## Data

Prices are **real**: daily candles come from Yahoo Finance's public
chart API, no account or key needed. A sanity filter drops freak
bad ticks by comparing each candle to its own ±60-day neighbourhood
— never to today's price level: judging old prices against the
recent median silently erased real history (NVDA's feed began in
2023 instead of 2019, and AMD's April-2025 crash days were deleted
outright). With the local band, every symbol's full 7 years load. Headlines for the mood score
come from Yahoo Finance's public RSS feeds; if they are unreachable
the mood score is an honest neutral 0, never an invented headline.
If the price feed is unreachable, the system falls back to a built-in
simulated feed **and the report says so** (`Data: demo feed`) — it
never presents demo numbers as real. The `live` mode's streamed ticks
are simulated from the last real close (a demo session); `learn`
mode uses only real daily candles, replayed in order.

## Measured results — paper money only

Every number below is **simulated money** on historical data,
measured with this system's own test discipline: the crew studies
only data up to each window's end (no look-ahead), sentiment is
neutral in historical tests, exits trigger intraday, and every
window is scored against simply buying and holding the same 10
stocks over the same days.

| Market window | System | Buy & hold | Difference |
|---|---|---|---|
| Rising market (recent ~180 trading days) | **+20.7%** | +22.5% | −1.7 pts |
| Sideways market (Jun 2024 – Mar 2025; basket net +1.6%) | **+22.2%** | +1.6% | +20.6 pts |
| Crash-filled window (Jul 2024 – Apr 2025; two sharp crashes inside) | **+3.2%** | +3.0% | +0.2 pts |
| Bear market (calendar 2022) | **−8.7%** | −44.6% | +35.9 pts |

Read the bear-market row carefully: the system **lost money**
there. It took only 32 trades all year and sat mostly in cash,
which is why it lost about five times less than holding. This is a
long-only system; in a falling market its job is protection, not
profit.

These are historical paper results on the windows stated. They are
not a promise, a prediction, or evidence of what real money would
do — see [Honest limits](#honest-limits) and
[Testing with real money? Read this first](#testing-with-real-money-read-this-first).

## Honest limits

- This is **paper trading** for learning and research — simulated
  money, **not financial advice**, and not a promise of profit. No
  trading system can guarantee returns; anyone who says otherwise is
  lying to you.
- A good backtest on one period does not predict the next period.
  That is exactly why the crew keeps learning, keeps verifying its
  setups on recent data, and retires what stops working.

## Verify the council's calls (`call_test.py`)

`python3 call_test.py` scores the council itself: for each of the
last 10 days it rebuilds the crew's knowledge using **only** data up
to that day, notes every call on BTC/ETH/SOL, and checks the calls
against what the market actually did the next day — walk-forward,
no cheating. It also reports how the council's single best pick (the
trade it would really have taken) performed.

## Testing with real money? Read this first

This project is a **paper-trading and research tool**. It was built
to study how a council of simple agents behaves in real markets with
simulated money, and that is the only use its authors endorse.

**The authors do not recommend trading real money with this system.**
Nothing in this repository is financial advice, and no result shown
here — backtest, paper session, or otherwise — is a promise or a
prediction of future performance.

If, despite that, you decide to experiment with real money (for
example through `real_test.py` below), understand that:

- You do so **entirely at your own risk and on your own
  responsibility.** Any losses are yours alone.
- The authors and contributors accept **no liability** for any
  financial loss, damage, or other consequence arising from
  real-money use of this code, in any amount, under any
  circumstances.
- Markets are risky. Never trade money you cannot afford to lose
  completely, and consider speaking to a licensed financial adviser
  before risking real capital.

### Share what you learn — please

Real-world feedback is how this system gets better, and it is
genuinely welcome — whether your results were good, bad, or
somewhere in between. If you test the system (on paper or with real
money) and are willing to share, please open a
[GitHub Issue](https://github.com/Emberstore/trading-agent/issues)
with:

- what you ran, on which symbols and settings, and for how long,
- your results — honestly, including the losses,
- any problem, bug, or confusing behaviour you noticed,
- any suggestion you have for improving the system.

Sharing is completely voluntary. Please share only what you are
comfortable making public, and never post account numbers, API
keys, or other personal financial details. Honest negative reports
are just as valuable as positive ones — often more so.

## Optional: a real-money micro test (`real_test.py`)

For anyone who wants to watch the council trade **real** money at
toy scale before trusting it with more: `real_test.py` runs the same
four voices on crypto (BTC/ETH/SOL) and places real Binance spot
orders capped at **$5 per order**, with hard safety rails — it
refuses keys that allow withdrawals, keeps keys in a local
`.env.local` file that is never committed, and its `check` mode
places no orders at all. It runs on **your** PC (Binance blocks some
networks by region; the account holder's own connection works).
Every real fill is logged to `real_log.jsonl`. This is a mechanics
test, not a profit strategy: at $5 a trade, minimum order sizes and
fees dominate, and nothing here is financial advice. Before even
considering it, read
[Testing with real money? Read this first](#testing-with-real-money-read-this-first)
above.

## License

MIT — see `LICENSE`.
