"""Trading Agents — central configuration.

Everything the crew of agents shares lives here: symbols, starting
capital, and the risk limits the RiskAgent enforces.
"""

CONFIG = {
    # Identity — the crew knows who made them. Shown in every report
    # and written into the brain itself. Their mission is also fixed:
    # earn a name in the world through good work. This system is OPEN
    # SOURCE (MIT License, GitHub) — the whole world can watch how
    # they work, which is exactly why the work must be good.
    "creator": "Danyal Malik",
    "mission": ("Earn a name in the world through good work. This system "
                "is open source — everyone can see how we work, so the "
                "work has to be the best."),

    # Instruments the crew watches (demo names — plug in real symbols
    # when a live data source is connected).
    "symbols": ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN",
                "GOOGL", "META", "AMD", "NFLX", "JPM"],

    # Paper-trading account. This is SIMULATED money.
    "starting_cash": 100_000.0,
    "currency": "USD",

    # Risk rules (RiskAgent enforces these on every trade)
    "max_risk_per_trade_pct": 1.0,   # risk at most 1% of cash per trade
    "max_position_pct": 20.0,        # one position <= 20% of the account
    "daily_loss_limit_pct": 3.0,     # stop trading after -3% in a day
    "max_open_risk_pct": 4.0,        # TOTAL risk across ALL open
                                     # positions <= 4% of the account —
                                     # per-trade limits alone let
                                     # correlated stocks stack into
                                     # one big bet on the same move
    # Stop-loss / take-profit are VOLATILITY-AWARE: the stop sits at
    # `stop_vol_multiple` x the stock's typical daily move, floored at
    # stop_min_pct and capped at stop_max_pct; the target is
    # `reward_risk` x the stop. (A flat 2% stop on real stocks gets
    # shaken out by ordinary daily noise — the crew's own 7-year
    # library proved that, so the levels now breathe with the market.)
    "stop_min_pct": 2.0,
    "stop_max_pct": 6.0,
    "stop_vol_multiple": 1.5,
    "reward_risk": 2.0,

    # Trailing stop: when a trade reaches its take-profit level it is
    # NOT sold. The exit starts trailing the highest price seen, one
    # stop-distance below the peak, so a winning trend can run while
    # most of the profit stays locked in. (A fixed target was capping
    # every winner at +2R while buy & hold rode the whole move — the
    # benchmark comparison exposed that.)
    "trailing_stop": True,
    "trailing_horizon": 60,      # history simulation: max candles a
                                 # trailing trade may run (vs 20 flat)

    # Uptrend participation: in a STRONG uptrend the council lowers
    # its bar a little and the RiskAgent may size the best pick
    # bigger — riding a proven trend beats sitting in cash waiting
    # for a perfect setup that never comes.
    "uptrend_threshold_factor": 0.75,
    "uptrend_size_multiple": 1.5,

    # Execution costs (ExecutionAgent applies these to paper fills)
    "fee_pct": 0.05,                 # commission per trade
    "slippage_pct": 0.02,            # price slippage per fill

    # Strategy thresholds (StrategyAgent)
    "min_confidence": 0.55,          # below this, the decision is HOLD

    # Demo data
    "demo_candles": 220,             # history length for the demo feed
    "demo_seed": 42,

    # Where candles come from: "yahoo" = REAL market data from Yahoo
    # Finance's public API (no key). If it is unreachable the system
    # falls back to the demo feed and the report says so.
    "data_source": "yahoo",

    # HistoryAgent: how much OLD data to study before trading.
    # 7 years of daily candles = 7 x 252 trading days.
    "history_candles": 1764,

    # The crew's service rules: a 2-year term, a formal review every
    # 30 days, and a voice agent whose calls stay below the accuracy
    # bar (with enough record to judge fairly) RETIRES itself — its
    # weight goes to zero and it never speaks in the council again.
    "service": {
        "term_days": 730,            # 2 years
        "review_every_days": 30,
        "retire_min_calls": 50,      # need this much record to judge
        "retire_accuracy": 0.40,     # below 40% right = retirement
        # Succession: a retired voice's chair is never left empty. A
        # fresh trainee (next generation) takes the chair on PROBATION:
        # its calls are scored in shadow (weight zero — heard, not
        # obeyed) for `probation_calls` calls; at review it is promoted
        # with a starter weight if it clears `probation_accuracy`,
        # otherwise it is replaced by the next trainee.
        "probation_calls": 25,
        "probation_accuracy": 0.45,
        "starter_weight": 0.10,
        # AWARD DAY + BOSS: two days before the 2-year term ends, the
        # voice with the best TERM results (accuracy over the whole
        # term — rank is NOT considered; a Junior can beat a Legend)
        # is crowned BOSS for the next 2-year term. The Boss leads the
        # council: its voice carries a weight bonus all term long.
        "award_before_term_end": 2,
        "boss_min_calls": 50,        # term calls needed to be eligible
        "boss_weight_bonus": 1.5,
    },

    # LearningAgent: the system's memory. Everything it learns from
    # closed trades is saved here and reloaded on every start, so each
    # day begins smarter than the last. Delete the file to reset it.
    "brain_file": "brain.json",
    "learn_rounds_per_day": 40,     # ticks per day in (old) live sessions
    "replay_days": 800,             # learn mode replays this many REAL
                                    # market days, one per system day

    # ConsensusAgent: how the council weighs each voice, and the bar
    # a trade must clear before the crew takes it (only the best one).
    # Strategy / History / Pattern weights are ADAPTIVE — the
    # LearningAgent shifts them toward whichever voice predicts best.
    "consensus": {
        "w_strategy": 0.35,          # StrategyAgent (chart + mood)
        "w_history": 0.25,           # HistoryAgent (proven edge on old data)
        "w_pattern": 0.25,           # PatternAgent (winning setups, re-verified)
        "w_regime": 0.15,            # RegimeAgent (market weather)
        "min_consensus": 0.30,       # below this strength: NO trade
    },

    # Live engine
    "live_rounds": 60,               # ticks per demo live session
}
