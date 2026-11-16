#!/usr/bin/env python3
"""REAL-MONEY MICRO TEST — optional, advanced, read this first.

This runs the SAME council (Strategy + History + Pattern + Regime)
on crypto (BTC / ETH / SOL) and places REAL orders on Binance spot
with a hard-capped test amount. It is a mechanics test — proof that
the system can trade real money and report every fill honestly —
not a promise of profit. On $10, one position of about $5 is all
that fits; fees and the minimum order size are the real opponents.

SAFETY RAILS (built in, not optional):
- One order is never more than $5.50. Only BTCUSDT, ETHUSDT, SOLUSDT.
- It REFUSES to trade if your API key allows withdrawals. Create the
  key with "Enable Spot Trading" ON and withdrawals OFF — then even
  a stolen key cannot take money out, it can only trade.
- Keys live in a local file `.env.local` next to this script. They
  are never printed, never committed (see .gitignore), never sent
  anywhere except Binance itself.
- `check` mode never places an order. `trade` mode is the only way
  an order can happen.

WHERE IT RUNS: on YOUR PC. Binance blocks some regions' networks
(for example, Muse's own US-side connection gets HTTP 451), while
the account holder's own connection works normally. Your keys also
stay on your machine, which is the safest place for them.

Setup:
  1. Binance account -> deposit a small test amount (e.g. $10 USDT).
  2. API Management -> create a key: Spot Trading ON, Withdrawals OFF.
  3. Create `.env.local` with two lines:
       BINANCE_API_KEY=your_key
       BINANCE_API_SECRET=your_secret
  4. python3 real_test.py check    # balances, key safety, council pick
     python3 real_test.py trade    # at most ONE real order, if the
                                   # council says buy and rails pass
Every real fill is appended to real_log.jsonl and open positions are
tracked in real_state.json (entry, stop, target). Run `trade` again
later and it first checks exits (stop-loss / take-profit) before it
even thinks about a new entry.
"""
import hashlib, hmac, json, sys, time
import urllib.error, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from config import CONFIG
from agents.data_agent import DataAgent
from agents.technical_agent import TechnicalAgent, volatility_pct
from agents.sentiment_agent import SentimentAgent
from agents.strategy_agent import StrategyAgent
from agents.history_agent import HistoryAgent
from agents.regime_agent import RegimeAgent
from agents.pattern_agent import PatternAgent
from agents.consensus_agent import ConsensusAgent

BASE = "https://api.binance.com"
PAIRS = {"BTC-USD": "BTCUSDT", "ETH-USD": "ETHUSDT", "SOL-USD": "SOLUSDT"}
MAX_ORDER_USD = 5.00        # one real order is never bigger than this
MIN_USDT_FREE = 5.60        # need at least this much free USDT to enter
STATE = HERE / "real_state.json"
LOG = HERE / "real_log.jsonl"


# ---------------------------------------------------------------- keys
def load_keys():
    env = HERE / ".env.local"
    keys = {}
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                keys[k.strip()] = v.strip()
    return keys.get("BINANCE_API_KEY"), keys.get("BINANCE_API_SECRET")


# ---------------------------------------------------------------- binance
class Binance:
    def __init__(self, key=None, secret=None):
        self.key, self.secret = key, secret

    def _req(self, method, path, params=None, signed=False):
        params = dict(params or {})
        url = BASE + path
        headers = {}
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            qs = urllib.parse.urlencode(params)
            sig = hmac.new(self.secret.encode(), qs.encode(),
                           hashlib.sha256).hexdigest()
            url += "?" + qs + "&signature=" + sig
            headers["X-MBX-APIKEY"] = self.key
        elif params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            if e.code == 451:
                raise RuntimeError(
                    "Binance refused this network (restricted location). "
                    "Run this on your own PC — your connection is fine, "
                    "this machine's is blocked.") from None
            raise RuntimeError(f"Binance HTTP {e.code}: {body}") from None

    def price(self, pair):
        return float(self._req("GET", "/api/v3/ticker/price",
                               {"symbol": pair})["price"])

    def restrictions(self):
        return self._req("GET", "/sapi/v1/account/apiRestrictions", signed=True)

    def balances(self):
        acc = self._req("GET", "/api/v3/account", signed=True)
        return {b["asset"]: {"free": float(b["free"]), "locked": float(b["locked"])}
                for b in acc["balances"] if float(b["free"]) + float(b["locked"]) > 0}

    def buy_usd(self, pair, usd):
        return self._req("POST", "/api/v3/order",
                         {"symbol": pair, "side": "BUY", "type": "MARKET",
                          "quoteOrderQty": f"{usd:.2f}"}, signed=True)

    def sell_usd(self, pair, usd):
        return self._req("POST", "/api/v3/order",
                         {"symbol": pair, "side": "SELL", "type": "MARKET",
                          "quoteOrderQty": f"{usd:.2f}"}, signed=True)


# ---------------------------------------------------------------- council
def council():
    """The crew's real analysis on crypto daily candles (Yahoo data)."""
    cfg = json.loads(json.dumps(CONFIG))
    cfg["symbols"] = list(PAIRS.keys())
    data, history, pattern = DataAgent(cfg), HistoryAgent(cfg), PatternAgent()
    tech, sent = TechnicalAgent(), SentimentAgent()
    strat, regime, consensus = StrategyAgent(cfg), RegimeAgent(), ConsensusAgent(cfg)
    books, evaluations = {}, []
    for sym in cfg["symbols"]:
        candles = data.history(sym)
        books[sym] = candles
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
        evaluations.append(consensus.evaluate(
            sym, decision, study, regime.analyse(candles),
            pattern_score=pat["score"], trust=1.0))
    actionable = {s: "BUY" for s in cfg["symbols"]}
    return consensus.pick_best(evaluations, actionable), evaluations, books


def stop_target(candles, price):
    r = CONFIG["risk"]
    vol = volatility_pct(candles)
    stop_pct = min(r["stop_max_pct"], max(r["stop_min_pct"],
                                          r["stop_vol_multiple"] * vol))
    return (round(price * (1 - stop_pct / 100), 4),
            round(price * (1 + r["reward_risk"] * stop_pct / 100), 4),
            round(stop_pct, 2))


# ---------------------------------------------------------------- state/log
def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"positions": []}


def save_state(state):
    STATE.write_text(json.dumps(state, indent=1))


def log_event(event):
    event["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG.open("a") as f:
        f.write(json.dumps(event) + "\n")
    print("LOGGED:", json.dumps(event))


# ---------------------------------------------------------------- commands
def cmd_check():
    key, secret = load_keys()
    print("=== REAL-MONEY TEST — CHECK (no orders are placed) ===")
    print(f"API key present: {'yes' if key else 'NO — create .env.local first'}")
    pick, evaluations, _ = council()
    for ev in evaluations:
        print(f"  {ev['symbol']:<8} council {ev['consensus']:+.3f} "
              f"(regime {ev['regime']}, history edge {ev['history_edge']:+.2f})")
    print("Council pick:", (f"{pick['action']} {pick['symbol']} "
                            f"(strength {pick['strength']})") if pick else "no trade")
    if not key:
        return
    b = Binance(key, secret)
    try:
        restr = b.restrictions()
        print(f"Key can withdraw: {restr.get('enableWithdrawals')} "
              f"(must be False to trade)")
        bals = b.balances()
        print("Balances:", {a: v["free"] for a, v in bals.items()})
        state = load_state()
        for pos in state["positions"]:
            px = b.price(pos["pair"])
            pnl = (px - pos["entry"]) / pos["entry"] * 100
            print(f"  OPEN {pos['pair']}: {pos['qty']} @ {pos['entry']} "
                  f"now {px} ({pnl:+.2f}%) stop {pos['stop']} target {pos['target']}")
    except RuntimeError as e:
        print("Binance:", e)


def cmd_trade():
    key, secret = load_keys()
    if not key:
        print("No API keys yet — create .env.local first (see the header).")
        return
    b = Binance(key, secret)
    print("=== REAL-MONEY TEST — TRADE (at most one entry, rails on) ===")
    restr = b.restrictions()
    if restr.get("enableWithdrawals"):
        print("REFUSED: this API key allows WITHDRAWALS. Turn withdrawals "
              "OFF for the key, then run again. Safety first.")
        return
    state = load_state()
    # 1) exits first — stop-loss / take-profit on open positions
    still_open = []
    for pos in state["positions"]:
        px = b.price(pos["pair"])
        if px <= pos["stop"] or px >= pos["target"]:
            why = "take-profit" if px >= pos["target"] else "stop-loss"
            res = b.sell_usd(pos["pair"], pos["qty"] * px * 0.999)
            got = float(res["cummulativeQuoteQty"])
            pnl = (px - pos["entry"]) / pos["entry"] * 100
            log_event({"event": "SELL", "pair": pos["pair"], "reason": why,
                       "qty": float(res["executedQty"]), "usd": round(got, 4),
                       "price": px, "pnl_pct": round(pnl, 2)})
        else:
            still_open.append(pos)
            print(f"HOLD {pos['pair']}: now {px}, stop {pos['stop']}, "
                  f"target {pos['target']}")
    state["positions"] = still_open
    save_state(state)
    # 2) one entry, only if the council says buy and the rails pass
    if still_open:
        print("A position is already open — no new entry this run.")
        return
    bals = b.balances()
    usdt = bals.get("USDT", {}).get("free", 0.0)
    pick, _, books = council()
    if not pick:
        print(f"No trade: the council picked nothing (free USDT ${usdt:.2f}).")
        return
    if usdt < MIN_USDT_FREE:
        print(f"No trade: free USDT ${usdt:.2f} is below the ${MIN_USDT_FREE} "
              f"needed for one ${MAX_ORDER_USD:.0f} test order plus headroom.")
        return
    pair = PAIRS[pick["symbol"]]
    res = b.buy_usd(pair, MAX_ORDER_USD)
    qty = float(res["executedQty"]); spent = float(res["cummulativeQuoteQty"])
    avg = spent / qty if qty else 0.0
    stop, target, stop_pct = stop_target(books[pick["symbol"]], avg)
    pos = {"pair": pair, "yahoo": pick["symbol"], "qty": qty, "entry": round(avg, 4),
           "stop": stop, "target": target, "opened": time.strftime("%Y-%m-%d %H:%M")}
    state["positions"].append(pos)
    save_state(state)
    log_event({"event": "BUY", "pair": pair, "qty": qty, "usd": round(spent, 4),
               "price": round(avg, 4), "stop": stop, "target": target,
               "stop_pct": stop_pct, "strength": pick["strength"],
               "regime": pick["regime"], "history_edge": pick["history_edge"]})


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode == "trade":
        cmd_trade()
    else:
        cmd_check()
