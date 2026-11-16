"""Trading Agents — web GUI (AFK-style pro terminal).

    python3 gui.py            opens the dashboard in your browser
    python3 gui.py --no-open  serve only, print the address
    python3 gui.py --port 9000

Standard library only — nothing to install, same promise as the rest
of this repo. The dashboard runs on YOUR machine only (127.0.0.1):
it reads brain.json, draws the chart from real Yahoo Finance candles,
and its buttons run the same commands you would type in a terminal
(main.py learn / backtest) and stream their output live.

Paper trading only — simulated money, no broker connected.
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.join(HERE, "brain.json")
LOGO = os.path.join(HERE, "docs", "logo.png")

try:
    from config import CONFIG
    SYMBOLS = CONFIG.get("symbols", [])
except Exception:
    SYMBOLS = []
if not SYMBOLS:
    SYMBOLS = ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN",
               "GOOGL", "META", "AMD", "NFLX", "JPM"]

# ---------------------------------------------------------------- state
_lock = threading.Lock()
_proc = None            # running main.py subprocess, or None
_proc_label = ""
_log_lines = []         # last 300 lines of subprocess output
_candle_cache = {}      # symbol -> (fetched_at, payload)


def _read_brain():
    try:
        with open(BRAIN) as f:
            return json.load(f)
    except Exception:
        return {}


def state_payload():
    b = _read_brain()
    acc = b.get("account", {}) or {}
    pos = acc.get("positions", {}) or {}
    last = acc.get("last_prices", {}) or {}
    risk = acc.get("open_risk", {}) or {}
    positions = []
    pos_value = 0.0
    for sym, p in pos.items():
        lp = last.get(sym)
        if lp is None:
            continue
        val = p["qty"] * lp
        pos_value += val
        r = risk.get(sym, {}) or {}
        positions.append({
            "symbol": sym, "qty": p["qty"], "avg": p["avg_price"],
            "last": lp, "value": val,
            "stop": r.get("stop_loss"), "target": r.get("take_profit"),
            "entry": r.get("entry"),
        })
    cash = acc.get("cash", 0.0)
    with _lock:
        running = _proc is not None and _proc.poll() is None
        label = _proc_label if running else ""
        log = list(_log_lines[-60:])
    return {
        "cash": cash,
        "equity": cash + pos_value,
        "pnl": acc.get("realised_pnl", 0.0),
        "days": b.get("days_learned", 0),
        "trades": b.get("total_trades", 0),
        "positions": positions,
        "prices": last,
        "weights": b.get("weights", {}),
        "boss": b.get("boss", {}),
        "symbols": SYMBOLS,
        "running": running,
        "running_label": label,
        "log": log,
    }


TIMEFRAMES = {
    "5m": ("5d", "5m", 400),
    "1h": ("3mo", "60m", 400),
    "1d": ("6mo", "1d", 120),
}


def candles_payload(symbol, tf="5m"):
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        symbol = SYMBOLS[0]
    if tf not in TIMEFRAMES:
        tf = "5m"
    rng, interval, keep = TIMEFRAMES[tf]
    now = time.time()
    key = (symbol, tf)
    hit = _candle_cache.get(key)
    if hit and now - hit[0] < 60:
        return hit[1]
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{symbol}?range={rng}&interval={interval}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = json.load(resp)
    result = raw["chart"]["result"][0]
    q = result["indicators"]["quote"][0]
    rows = []
    for t, o, h, l, c, v in zip(result["timestamp"], q["open"], q["high"],
                                q["low"], q["close"], q["volume"]):
        if None in (o, h, l, c):
            continue
        rows.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v or 0})
    payload = {"symbol": symbol, "tf": tf, "rows": rows[-keep:]}
    _candle_cache[key] = (now, payload)
    return payload


# ------------------------------------------------------------ processes
def _pump(proc):
    global _proc
    try:
        for line in proc.stdout:
            with _lock:
                _log_lines.append(line.rstrip())
                del _log_lines[:-300]
    except Exception:
        pass
    finally:
        with _lock:
            if _proc is proc:
                _proc = None


def start_process(args, label):
    global _proc, _proc_label
    with _lock:
        if _proc is not None and _proc.poll() is None:
            return False, "already running: " + _proc_label
        _log_lines.append(f"--- {label}: {' '.join(args)} ---")
    proc = subprocess.Popen(
        [sys.executable, os.path.join(HERE, "main.py")] + args,
        cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1)
    with _lock:
        _proc, _proc_label = proc, label
    threading.Thread(target=_pump, args=(proc,), daemon=True).start()
    return True, label + " started"


def stop_process():
    global _proc
    with _lock:
        proc = _proc
    if proc is None or proc.poll() is not None:
        return False, "nothing is running"
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except Exception:
        proc.kill()
    with _lock:
        _log_lines.append("--- stopped by user (brain is saved; nothing is lost) ---")
    return True, "stopped"


# ---------------------------------------------------------------- page
PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>TRADING AGENTS · terminal</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
:root{--bg:#0d0e10;--bg2:#08090b;--panel:#121316;--line:#1e2024;--tx:#e8e9eb;--mut:#8b8e94;--up:#3fbf8f;--dn:#e5534b;--acc:#6d7cff;--btn:#1f3a2e;box-sizing:border-box;color-scheme:dark}
*,*::before,*::after{box-sizing:inherit}
body{margin:0;background:var(--bg);font:14px/1.3 Inter,system-ui,sans-serif;color:var(--tx);padding:0}
.mono{font-family:"JetBrains Mono",ui-monospace,monospace}
.up{color:var(--up)}.dn{color:var(--dn)}.mut{color:var(--mut)}
.app{width:100%;min-height:100vh;margin:0;background:var(--bg);overflow:hidden;display:flex;flex-direction:column}
header{display:flex;align-items:center;gap:28px;padding:14px 20px;background:var(--bg2);flex-wrap:wrap}
.logo{font-weight:800;font-size:22px;letter-spacing:-1px;display:flex;align-items:center;gap:10px}
.logo img{height:36px;width:auto;border-radius:6px}
nav{display:flex;gap:26px;color:var(--mut);flex-wrap:wrap}
nav a{cursor:pointer}nav a:hover{color:var(--tx)}
.hr{margin-left:auto;display:flex;gap:10px;align-items:center}
.pill{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:9px 14px;color:var(--mut);white-space:nowrap}
.pill.t{color:var(--tx)}
.ticker{display:flex;gap:24px;padding:10px 20px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);overflow-x:auto;white-space:nowrap;font-size:13px;scrollbar-width:none}
.ticker span{display:flex;align-items:center;gap:6px;cursor:pointer}
.av{width:20px;height:20px;border-radius:5px;display:inline-block}
.main{display:grid;grid-template-columns:1fr 380px}
.info{display:flex;align-items:center;gap:28px;padding:14px 20px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.tok{display:flex;gap:14px;align-items:center}
.tokimg{width:56px;height:56px;border-radius:8px;background:#000;border:1px solid var(--up);display:grid;place-items:center;overflow:hidden}
.tokimg img{width:100%;height:100%;object-fit:contain}
.big{font-size:30px;font-weight:600}
.stat small{display:block;color:var(--mut);margin-bottom:4px}.stat b{font-weight:500;font-size:15px}
.sp{margin-left:auto;display:flex;gap:28px}
.tf{display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid var(--line);border-left:1px solid var(--line);text-align:center;padding:18px 0}
.tf div{color:var(--mut);cursor:pointer}.tf b{display:block;margin-top:6px;font-weight:500}
.tf div.on{color:var(--tx)}.tf div.on span{color:var(--acc)}
.tb{display:flex;gap:18px;align-items:center;padding:12px 20px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.tb .r{margin-left:auto;display:flex;gap:18px;align-items:center}
.tb span.a{color:var(--acc)}
.tb .tfl{cursor:pointer}.tb .tfl.on{color:var(--acc)}
.chartwrap{display:flex;height:520px;position:relative}
.tools{width:50px;display:flex;flex-direction:column;gap:8px;align-items:center;padding:10px 0;color:var(--mut);font-size:18px}
.tools i{font-style:normal;width:34px;height:34px;display:grid;place-items:center;border-radius:6px;cursor:pointer}.tools i:hover{background:var(--panel);color:var(--tx)}
.cv{flex:1;position:relative;min-width:0}
canvas{position:absolute;inset:0;width:100%;height:100%}
.leg{position:absolute;left:14px;top:8px;z-index:2;font-size:15px}
.leg .o span{margin-right:8px;font-size:13px}
.tfoot{display:flex;gap:16px;padding:10px 70px 10px 58px;border-top:1px solid var(--line);color:var(--mut);align-items:center}
.tfoot .r{margin-left:auto}
.tabs{display:flex;gap:28px;padding:16px 20px 0;border-top:1px solid var(--line);color:var(--mut);align-items:center;flex-wrap:wrap}
.tabs .on{color:var(--tx);border-bottom:2px solid var(--tx);padding-bottom:12px}
.tabs .r{margin-left:auto;display:flex;gap:8px;padding-bottom:10px}
.tag{padding:6px 10px;border-radius:6px;font-size:12px;font-weight:600}
.tag.g{background:#10261d;color:var(--up)}.tag.y{background:#2b2410;color:#e7b94d}
.tblw{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:720px}
th{text-align:left;color:var(--mut);font-weight:400;padding:12px 20px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);font-size:13px}
td{padding:16px 20px}
tbody tr:nth-child(even){background:#101114}
.log{background:var(--bg2);border-top:1px solid var(--line);padding:12px 20px;font-family:"JetBrains Mono",ui-monospace,monospace;font-size:12.5px;color:#c9d4de;height:140px;overflow-y:auto;white-space:pre-wrap}
aside{border-left:1px solid var(--line);padding:0}
.side{padding:16px}
.seg{display:grid;grid-template-columns:1fr 1fr;background:var(--panel);border-radius:8px;padding:3px;gap:3px;color:var(--mut);text-align:center;font-size:13px}
.seg div{padding:8px;border-radius:6px;cursor:pointer}.seg .on{background:#25272b;color:var(--tx)}
.bs{margin-top:12px}.bs div{padding:12px;font-size:15px}.bs .on{background:var(--btn);color:var(--up)}
.in{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px;margin-top:12px;display:flex;justify-content:space-between;color:var(--mut)}
.q{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:10px}
.q button{background:var(--panel);border:1px solid var(--line);color:var(--tx);border-radius:6px;padding:10px 0;font:inherit;cursor:pointer;font-size:12px}
.q button:hover{border-color:var(--up)}
.go{margin-top:14px;background:var(--btn);color:var(--up);border:1px solid #2b5642;border-radius:8px;padding:14px;display:flex;justify-content:space-between;cursor:pointer;width:100%;font:inherit}
.fees{display:flex;gap:14px;color:var(--mut);margin:14px 0;font-size:13px;align-items:center}
.fees .r{margin-left:auto}
.row{display:flex;align-items:center;gap:8px;margin-top:8px}
.box{flex:1;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px;display:flex;justify-content:space-between;color:var(--mut)}
.box b{color:var(--tx);font-weight:400}
.sec{display:flex;justify-content:space-between;padding:16px;border-top:1px solid var(--line);margin-top:6px}
.sim{margin:0 16px 16px;background:var(--panel);border-radius:8px;padding:10px;display:flex;gap:12px;align-items:center}
.sim .tokimg{width:48px;height:48px;font-size:16px}
footer{display:flex;gap:22px;align-items:center;padding:12px 20px;background:var(--bg2);color:var(--mut);border-top:1px solid var(--line);flex-wrap:wrap}
footer .r{margin-left:auto;display:flex;gap:18px;align-items:center}
.sw{width:42px;height:22px;border-radius:12px;background:#25272b;display:inline-block;vertical-align:middle;margin-right:8px;position:relative}.sw::after{content:"";position:absolute;left:3px;top:3px;width:16px;height:16px;border-radius:50%;background:#111}
@media(max-width:1000px){.main{grid-template-columns:1fr}aside{border-left:0;border-top:1px solid var(--line)}.sp{margin-left:0}.chartwrap{height:420px}.tools{display:none}.tfoot{padding:10px 16px}}
@media(max-width:600px){body{padding:6px}nav{display:none}.big{font-size:24px}}
</style>
</head>
<body>
<div class="app">
  <header>
    <div class="logo"><img src="/logo.png" alt="logo">TRADING AGENTS</div>
    <nav><a>Dashboard</a><a>Learn</a><a>Backtest</a><a>Live</a><a>Council</a></nav>
    <div class="hr"><div class="pill">Day <b id="daychip" style="color:var(--tx)">–</b></div><div class="pill t" id="eqpill">Equity –</div><div class="pill t">Danyal Malik</div></div>
  </header>
  <div class="ticker mono" id="tk"></div>

  <div class="main">
    <section>
      <div class="info">
        <div class="tok"><div class="tokimg"><img src="/logo.png" alt="logo"></div><div><b style="font-size:16px" id="symname">AAPL</b> <span class="mut">held by the crew</span><div class="mut" style="margin-top:6px">Yahoo Finance · real data</div></div></div>
        <div class="big" id="bigprice">$–</div>
        <div class="stat"><small>Cash</small><b id="st-cash">–</b></div>
        <div class="stat"><small>Equity</small><b id="st-eq">–</b></div>
        <div class="stat"><small>Realised P&amp;L</small><b id="st-pnl">–</b></div>
        <div class="sp">
          <div class="stat"><small>Experience</small><b id="st-trades">–</b></div>
          <div class="stat"><small>Positions</small><b id="st-pos">–</b></div>
          <div class="stat"><small>Boss</small><b id="st-boss">–</b></div>
        </div>
      </div>
      <div class="tb">
        <span class="tfl on" data-tf="5m" onclick="setTF('5m')">5m</span><span class="tfl" data-tf="1h" onclick="setTF('1h')">1h</span><span class="tfl" data-tf="1d" onclick="setTF('1d')">1d</span><span>|</span><span>ƒx Indicators</span><span>▾ Display Options</span><span>Council view</span>
        <div class="r"><span>Yahoo Finance</span><span class="up">● Live</span></div>
      </div>
      <div class="chartwrap">
        <div class="tools"><i style="color:var(--acc)">+</i><i>╱</i><i>≡</i><i>⌖</i><i>≣</i><i>T</i><i>⊕</i><i>∩</i></div>
        <div class="cv"><div class="leg"><div><span id="ct">AAPL/USD · 5m · Yahoo Finance</span> <span class="up">●</span> <span class="o mono" id="ohlc"></span></div><div class="mut" style="margin-top:6px">Volume <span class="up mono" id="volspan">–</span></div></div><canvas id="c"></canvas></div>
      </div>
      <div class="tfoot"><span>5m</span><span>1h</span><span>1d</span><span>6mo</span><span class="r mono" id="clk">–</span></div>
      <div class="tabs"><span class="on">Positions</span><span>Orders</span><span>History</span><div class="r"><span class="tag g" id="statustag">OPERATIONAL</span><span class="tag y">PAPER TRADING ONLY</span></div></div>
      <div class="tblw"><table class="mono">
        <thead><tr><th>Symbol</th><th>Qty</th><th>Avg price</th><th>Last</th><th>Value</th><th>Stop</th><th>Target</th></tr></thead>
        <tbody id="posbody"></tbody></table></div>
      <div class="log" id="log">Press START LEARNING — the crew's output will stream here, exactly like the terminal.</div>
    </section>

    <aside>
      <div class="tf"><div class="on" data-tf="5m" onclick="setTF('5m')"><span>5m</span><b id="tf-5m">–</b></div><div data-tf="1h" onclick="setTF('1h')"><span>1h</span><b id="tf-1h">–</b></div><div data-tf="1d" onclick="setTF('1d')"><span>1d</span><b id="tf-1d">–</b></div><div><span>Day</span><b id="tf-day" style="color:var(--tx)">–</b></div></div>
      <div class="side">
        <div class="seg"><div class="on">Council</div><div>Risk Guard</div></div>
        <div class="seg bs"><div class="on" id="btn-start" onclick="act('start')">START LEARNING</div><div id="btn-stop" onclick="act('stop')">Stop</div></div>
        <div style="margin-top:14px">Council vote today</div>
        <div class="in"><span id="bossline">Boss — strategy</span><span id="bosspct" style="color:var(--tx)">–</span></div>
        <div class="q" id="wchips"></div>
        <button class="go" id="btn-bt" onclick="act('backtest')"><span>Run Backtest</span><span>full history</span></button>
        <div class="fees"><span>Paper mode</span><span>No broker</span><span>Real data</span><span class="r pill" style="padding:4px 8px">Stdlib only</span></div>
        <div class="row"><span>Risk guard — selected position</span></div>
        <div class="row"><div class="box"><span>Entry</span><b id="rg-entry">–</b></div><div class="box"><span>Qty</span><b id="rg-qty">–</b></div></div>
        <div class="row"><div class="box"><span>↑ TP</span><b id="rg-target">–</b></div><div class="box"><span>Value</span><b id="rg-value">–</b></div></div>
        <div class="row"><div class="box"><span>↓ SL</span><b id="rg-stop">–</b></div><div class="box"><span>Avg</span><b id="rg-avg">–</b></div></div>
      </div>
      <div class="sec"><span>Held by the crew</span><span class="mut">⌄</span></div>
      <div id="simlist"></div>
      <div class="sec"><span>Council of 14 agents</span><span class="mut">⌄</span></div>
    </aside>
  </div>
  <footer><span>Trading Agents</span><span class="up" id="footstatus">● Operational — idle</span><span>▪ Council paper terminal</span>
    <div class="r"><span><i class="sw"></i>Paper</span><span>No broker connected</span><span>Real Yahoo data</span></div></footer>
</div>

<script>
let SYM = 'AAPL', TF = '5m', STATE = null;
const $ = id => document.getElementById(id);
const money = n => '$' + Math.round(n).toLocaleString('en-US');
const COLORS = ['#d8ff3d','#e0a33a','#6a8','#b66','#58a','#777','#ccc','#e94','#999','#a85'];

async function loadState() {
  const s = await (await fetch('/api/state')).json();
  STATE = s;
  $('daychip').textContent = s.days;
  $('eqpill').textContent = 'Equity ' + money(s.equity);
  $('st-cash').textContent = money(s.cash);
  $('st-eq').textContent = money(s.equity);
  const pnl = $('st-pnl');
  pnl.textContent = (s.pnl >= 0 ? '+' : '−') + money(Math.abs(s.pnl)).slice(0);
  pnl.textContent = (s.pnl >= 0 ? '+' : '-') + money(Math.abs(s.pnl)).replace('$-', '-$');
  pnl.className = s.pnl >= 0 ? 'up' : 'dn';
  $('st-trades').textContent = s.trades + ' trades';
  $('st-pos').textContent = s.positions.length;
  const bossName = (s.boss && s.boss.name) || '–';
  $('st-boss').textContent = bossName;
  $('tf-day').textContent = s.days;
  $('bossline').textContent = 'Boss — ' + bossName;
  const w = s.weights || {};
  const wv = k => w['w_' + k];
  $('bosspct').textContent = wv('strategy') ? Math.round(wv('strategy') * 100) + '% of the vote' : '–';
  $('wchips').innerHTML = ['strategy','history','pattern','regime','pressure'].map(k =>
    `<button>${k.slice(0,4).toUpperCase()} ${wv(k) ? Math.round(wv(k) * 100) + '%' : '–'}</button>`).join('');
  $('tk').innerHTML = s.symbols.map((sym, i) => {
    const p = s.prices[sym];
    const held = s.positions.some(x => x.symbol === sym);
    return `<span onclick="setSYM('${sym}')"><b style="font-weight:500;font-family:Inter;${held ? 'color:var(--up)' : ''}">${sym}</b><span class="mut">${p ? '$' + p.toFixed(2) : '–'}</span></span>`;
  }).join('');
  const fx = v => v == null ? '–' : '$' + v.toFixed(2);
  const pos = s.positions.find(x => x.symbol === SYM) || s.positions[0];
  if (pos) {
    $('rg-entry').textContent = fx(pos.entry);
    $('rg-qty').textContent = pos.qty;
    $('rg-target').textContent = fx(pos.target);
    $('rg-stop').textContent = fx(pos.stop);
    $('rg-avg').textContent = fx(pos.avg);
    $('rg-value').textContent = money(pos.value);
  }
  $('posbody').innerHTML = s.positions.map(p =>
    `<tr><td><b style="font-weight:500">${p.symbol}</b></td><td class="mut">${p.qty}</td><td class="mut">${fx(p.avg)}</td><td class="mut">${fx(p.last)}</td><td>$${Math.round(p.value).toLocaleString('en-US')}</td><td class="mut">${fx(p.stop)}</td><td class="mut">${fx(p.target)}</td></tr>`).join('');
  $('simlist').innerHTML = s.positions.map(p =>
    `<div class="sim"><div class="tokimg" style="font-size:13px;border-color:#333;color:var(--tx);font-weight:800">${p.symbol.slice(0, 2)}</div><div><div>${p.symbol} <span class="mut">${p.qty} shares</span></div><div class="up" style="margin-top:4px">${money(p.value)}</div></div></div>`).join('');
  const last = s.prices[SYM];
  if (last) $('bigprice').textContent = '$' + last.toFixed(2);
  $('symname').textContent = SYM;
  const run = s.running;
  $('statustag').textContent = run ? 'RUNNING' : 'OPERATIONAL';
  $('footstatus').textContent = run ? '● Operational — ' + s.running_label + ' running' : '● Operational — idle';
  $('btn-start').textContent = run ? 'RUNNING…' : 'START LEARNING';
  if (s.log && s.log.length) {
    const el = $('log');
    el.textContent = s.log.join('\n');
    el.scrollTop = el.scrollHeight;
  }
}
function setSYM(sym) { SYM = sym; loadChart(); loadState(); }
function setTF(tf) {
  TF = tf;
  document.querySelectorAll('.tfl').forEach(e => e.classList.toggle('on', e.dataset.tf === tf));
  document.querySelectorAll('.tf div[data-tf]').forEach(e => e.classList.toggle('on', e.dataset.tf === tf));
  loadChart();
}
async function act(what) {
  await fetch('/api/' + what, {method: 'POST'});
  setTimeout(loadState, 600);
}
async function tfChange(tf) {
  try {
    const d = await (await fetch('/api/candles?symbol=' + SYM + '&tf=' + tf)).json();
    const rows = d.rows; if (rows.length < 2) return null;
    return (rows[rows.length - 1].c - rows[0].o) / rows[0].o * 100;
  } catch (e) { return null; }
}
async function loadTfStrip() {
  for (const tf of ['5m', '1h', '1d']) {
    const ch = await tfChange(tf);
    const el = $('tf-' + tf);
    if (ch === null) { el.textContent = '–'; continue; }
    el.textContent = (ch >= 0 ? '+' : '') + ch.toFixed(1) + '%';
    el.className = ch >= 0 ? 'up' : 'dn';
  }
}
async function loadChart() {
  const data = await (await fetch('/api/candles?symbol=' + SYM + '&tf=' + TF)).json();
  const rows = data.rows; if (!rows.length) return;
  const last = rows[rows.length - 1];
  $('ct').textContent = SYM + '/USD · ' + TF + ' · Yahoo Finance';
  const chg = (last.c - rows[0].o) / rows[0].o * 100;
  $('ohlc').innerHTML = `<span>O ${last.o.toFixed(2)}</span><span>H ${last.h.toFixed(2)}</span><span>L ${last.l.toFixed(2)}</span><span>C ${last.c.toFixed(2)}</span><span class="${chg >= 0 ? 'up' : 'dn'}">${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%</span>`;
  $('volspan').textContent = last.v ? last.v.toLocaleString('en-US') : '–';
  const cv = $('c'), x = cv.getContext('2d');
  const r = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  cv.width = r.width * dpr; cv.height = r.height * dpr;
  x.setTransform(dpr, 0, 0, dpr, 0, 0);
  const W = r.width, H = r.height, pr = 70, pb = 34, cw = W - pr, ch = H - pb;
  let hi = Math.max(...rows.map(d => d.h)), lo = Math.min(...rows.map(d => d.l));
  const pad = (hi - lo) * 0.07; hi += pad; lo -= pad;
  const Y = v => (hi - v) / (hi - lo) * ch;
  x.font = '12px Inter,sans-serif'; x.textAlign = 'left';
  x.strokeStyle = '#1a1c1f'; x.fillStyle = '#b4b7bc'; x.lineWidth = 1;
  const steps = Math.max(5, Math.floor(ch / 52));
  for (let i = 0; i <= steps; i++) {
    const p = lo + (hi - lo) * i / steps, y = Y(p);
    x.beginPath(); x.moveTo(0, y); x.lineTo(cw, y); x.stroke();
    x.fillText(p.toFixed(0), cw + 12, y + 4);
  }
  const bw = cw / rows.length, vh = ch * 0.16;
  const vmax = Math.max(...rows.map(d => d.v));
  rows.forEach((d, i) => {
    const px = i * bw + bw / 2, up = d.c >= d.o;
    x.fillStyle = up ? 'rgba(63,191,143,.5)' : 'rgba(229,83,75,.45)';
    const hgt = vmax ? d.v / vmax * vh : 0;
    x.fillRect(px - bw * 0.32, ch - hgt, Math.max(1, bw * 0.64), hgt);
    const col = up ? '#3fbf8f' : '#e5534b';
    x.strokeStyle = col; x.fillStyle = col;
    x.beginPath(); x.moveTo(px, Y(d.h)); x.lineTo(px, Y(d.l)); x.stroke();
    const t = Y(Math.max(d.o, d.c)), b = Y(Math.min(d.o, d.c));
    x.fillRect(px - bw * 0.32, t, Math.max(1, bw * 0.64), Math.max(1, b - t));
  });
  const ly = Y(last.c);
  x.setLineDash([2, 3]); x.strokeStyle = '#3fbf8f';
  x.beginPath(); x.moveTo(0, ly); x.lineTo(cw, ly); x.stroke(); x.setLineDash([]);
  x.fillStyle = '#3fbf8f'; x.fillRect(cw + 4, ly - 11, pr - 8, 22);
  x.fillStyle = '#fff'; x.font = '600 12px Inter'; x.fillText(last.c.toFixed(2), cw + 10, ly + 4);
  x.fillStyle = '#8b8e94'; x.font = '11px Inter'; x.textAlign = 'center';
  const every = Math.ceil(rows.length / 8);
  rows.forEach((d, i) => {
    if (i % every) return;
    const dt = new Date(d.t * 1000);
    const lbl = TF === '1d' ? dt.toLocaleDateString('en-GB', {day: '2-digit', month: 'short'})
      : dt.toLocaleTimeString('en-GB', {hour: '2-digit', minute: '2-digit'});
    x.fillText(lbl, i * bw + bw / 2, H - 10);
  });
}
setInterval(() => {
  const d = new Date(), f = n => String(n).padStart(2, '0');
  const off = -d.getTimezoneOffset() / 60;
  $('clk').textContent = `${f(d.getHours())}:${f(d.getMinutes())}:${f(d.getSeconds())} (UTC${off >= 0 ? '+' : ''}${off})  |  % log auto`;
}, 1000);
addEventListener('resize', loadChart);
loadState().then(() => { loadChart(); loadTfStrip(); });
setInterval(loadState, 3000);
setInterval(() => { loadChart(); loadTfStrip(); }, 60000);
</script>
</body>
</html>
"""


# -------------------------------------------------------------- handler
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path == "/":
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif u.path == "/api/state":
                self._send(200, json.dumps(state_payload()))
            elif u.path == "/api/candles":
                q = parse_qs(u.query)
                sym = (q.get("symbol") or [SYMBOLS[0]])[0]
                tf = (q.get("tf") or ["5m"])[0]
                self._send(200, json.dumps(candles_payload(sym, tf)))
            elif u.path == "/logo.png":
                with open(LOGO, "rb") as f:
                    self._send(200, f.read(), "image/png")
            else:
                self._send(404, json.dumps({"error": "not found"}))
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}))

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/start":
            ok, msg = start_process(["learn"], "learn (forever)")
        elif u.path == "/api/backtest":
            ok, msg = start_process(["backtest"], "backtest")
        elif u.path == "/api/stop":
            ok, msg = stop_process()
        else:
            self._send(404, json.dumps({"error": "not found"}))
            return
        self._send(200, json.dumps({"ok": ok, "message": msg}))


def main():
    port = 8765
    open_browser = True
    args = sys.argv[1:]
    if "--no-open" in args:
        open_browser = False
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"Trading Agents GUI: {url}")
    print("Paper trading only. Ctrl+C stops the dashboard "
          "(a running learner started from the page keeps its own window rules — stop it from the page first).")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGUI closed.")


if __name__ == "__main__":
    main()
