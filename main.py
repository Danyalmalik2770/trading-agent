"""Run the crew.

    python3 main.py            backtest over history, then a short LIVE session
    python3 main.py live       real-time session only (streamed ticks)
    python3 main.py backtest   backtest only
    python3 main.py learn      learn forever, day after day (Ctrl+C stops;
                               the brain is saved daily, nothing is lost)
    python3 main.py learn 5    learn for exactly 5 days, then report

Paper trading only — simulated money. No broker is connected and no
real order can be placed from this code.
"""
import sys

from config import CONFIG
from orchestrator import Orchestrator

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "learn":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else None
        # Forever mode replays REAL market days in order: one real
        # trading day every ~5 seconds until it catches up with the
        # present, then it waits for genuinely new days. A fixed day
        # count runs at full speed for testing.
        pace = 5.0 if days is None else 0.0
        print(Orchestrator(CONFIG).run_forever(days=days, pace_seconds=pace))
    else:
        if mode in ("all", "backtest"):
            print(Orchestrator(CONFIG).run())
        if mode in ("all", "live"):
            print()
            print(Orchestrator(CONFIG).run_live(rounds=30 if mode == "all" else None))
