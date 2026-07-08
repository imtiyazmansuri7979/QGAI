# QGAI — System Overview & Workflow

How the QGAI XAUUSD (gold) M15 auto-trading system is built, and how to run it.
Read with **RULEBOOK.md** (the do's/don'ts) and `engine/docs/FIXES_CHANGELOG*.md` (what changed).

---

## 1. What it is
An automated trading system for **XAUUSD on the M15 timeframe**. A machine-learning
model scores each new 15-minute bar; if the win-probability is high enough it opens a
trade, manages the exit with a trend-following "ratchet" stop, and replicates the
trade across multiple broker accounts. It retrains itself weekly on its own outcomes.

---

## 2. How it's built (layers)

### A. Data layer
- **mt5_data_updater.py** — pulls fresh OHLC + ADX from MetaTrader 5 for the configured symbol.
- **merge_data.py** — merges historical + live data (fresh live wins on overlap → `data/merged/`).
- **build_indicators.py / features.py** — engineers the model features (ADX/DI, momentum, EMA200,
  order-block S/R, news timers, 2-SMMA trend state, HMM regime, slots, etc.).
- **trend_signal.py** — the **2-SMMA (period 2) ratchet line** — the heart of entries AND exits
  (gives `buy_line`, `sell_line`, `flip`). Volatility comes from this, not ATR.

### B. ML / "brain" layer
- **train.py** — trains everything on a **time-based split** (no shuffle → no look-ahead):
  - **HMM market-state** model → labels each bar Ranging / Trending / Volatile.
  - **Ensemble** (XGBoost + LightGBM + CatBoost) + isotonic calibration → win-probability.
  - **State-specific** models (one per regime) + **directional** BUY / SELL models.
  - Helper predictors: BigWin, Duration, move-size & SL quantiles.
- **xgb_model.py** — the ensemble class (also dumps `feature_importance.csv` each retrain).
- **inference.py** — at runtime loads all models, builds the live feature vector, and outputs
  one signal per bar: BUY / SELL / SKIP + win_prob + regime + extra info.
- **self_learning.py** — online learner + drift detector (updates from closed trades).

### C. Live-trading layer (the "bridge")
- **bridge_main.py** — the main loop: every second heartbeat; on each new closed M15 bar it asks
  inference for a signal, decides, and monitors open trades. Writes the dashboard every second.
- **bridge_core.py** — connect/feed, order execution, `monitor_virtual_sl` (the live exit manager).
- **bridge_risk.py** — `VirtualTrade` + the **ratchet exit engine** (trail / flip logic, bar-by-bar).
- **bridge_ratchet.py** — higher-timeframe (H1/M30/H4) trend state for HTF stop/flip.
- **bridge_session.py** — daily rules (the **9% daily ratchet** loss-floor + profit-lock); also owns
  `_close_position()` (the single choke point every exit funnels through) and the **stuck-trade protect**
  subsystem (2026-07-01): escalating alerts + a protective hedge when the broker keeps rejecting a close
  (e.g. AutoTrading off) — full-lot freeze by default (`stuck_trade_hedge_enabled`), or an optional
  graduated 3%→6% risk-stretch partial hedge (`leftover_excess_hedge_enabled`, off by default).
- **bridge_multi.py** — one shared MT5 terminal, replicates trades across accounts + failover.
- **bridge_dashboard.py / bridge_data.py / bridge_constants.py** — dashboard JSON, logging (SQLite + CSV), constants.

### D. Dashboard
- **serve.py** — tiny web server (port 8000) that serves the page + handles mode/feedback.
- **dashboard.html** — live view (price, signal, open trade, vSL ticker, stats), polls `logs/dashboard.json`.

### E. Research / backtest
- **backtest_replay.py** — replays the model bar-by-bar with the real exit rules (the truth-teller).
  2026-07-01: supports checkpoint/resume (auto-saves every 500 bars + on Ctrl+C, keyed to the exact config
  so it never resumes a mismatched run — `--no-resume` to force fresh) and live progress every 100 bars.
- **run_wfo.py** — walk-forward: retrain weekly on past, trade next week unseen (honest OOS).
  `--sweep-trails` compares all stop-trail modes from ONE weekly retrain.
- **monte_carlo_resample.py / risk_sweep / *_backtest.py** — risk, drawdown, ruin, parameter studies.
- **shadow_ledger.py** — turns the bridge's real signals into a paper-trade ledger (entry/exit/$/%/real-flag).

### F. Orchestration
- **scheduler.py** — auto pipeline: data update (daily) → retrain (weekly) → run bridge → stop/report.
- **Start/*.bat** — one-click launchers (Start Trading, Update Data, Train, Scheduler, Dashboard, Shadow Ledger).

---

## 3. How a trade flows (live)
```
MT5 feed ─► data updater ─► merge ─► features ─► inference (ensemble + HMM)
                                                        │
                                          signal: BUY / SELL / SKIP + win_prob
                                                        │
                        win_prob ≥ threshold & filters? ─┴─► open trade (primary)
                                                              └─► replicate to secondary accounts
                                                                       │
                                  monitor each closed M15 bar (ratchet engine):
                                    • stop = H1 ratchet line ∓ buffer (0.20%)
                                    • trail one-way as the H1 line moves
                                    • exit on H1 FLIP, or stop hit, or far TP
                                                                       │
                                              close ─► record outcome (SQLite/CSV)
                                                                       │
                                          weekly retrain learns from outcomes
```
**Risk:** lot = equity × 3% / stop-distance → a stop hit = 1R ≈ 3% of equity.
**Daily:** 9% ratchet (loss-floor −9%, profit-lock as the day's peak grows).

---

## 4. Strategy in one paragraph
The 2-SMMA(2) line defines trend direction and the trailing stop. The ML ensemble (chosen by the
HMM regime, refined by BUY/SELL models) only lets through high-probability setups. Entries are 15-min;
the **stop and the flip-exit ride the H1 line** (so 15-min noise doesn't shake the trade out). Take-profit
is kept **far** — the trade runs until the H1 trend flips. Each trade risks 3% of equity; the day halts at
a 9% trailing drawdown.

---

## 5. Operating workflow (day-to-day)
**Auto (recommended):** run `Start/4_Auto_Scheduler.bat` — it updates data, retrains weekly, runs the bridge, reports.
**Manual:**
1. `Start/2_Update_Data.bat` — refresh data from MT5.
2. `Start/3_Train_Models.bat` — retrain (after any feature change, or weekly).
3. `Start/5_Dashboard.bat` — start the dashboard server (open http://localhost:8000/dashboard.html).
4. `Start/1_Start_Trading.bat` — start the live bridge. **(Demo account first.)**
(Don't run the scheduler AND the standalone bridge together — they'd fight over one MT5 terminal.)

## 6. Research → live workflow (changing the strategy)
```
1. Idea ─► backtest_replay.py (quick single-period check)
2. ─► run_wfo.py walk-forward OOS (honest test; --weeks 2 quick-test FIRST)
3. ─► Stage 1: trail/param sweep with fixed-lot (clean R) → pick the best
4. ─► Stage 2: winner with real $10k + 3% volume + FAR TP → realistic $/DD
5. ─► set the winner in config.py ─► retrain ─► DEMO forward-test a few days
6. ─► go live small, monitor the dashboard
7. ─► note WHAT changed in FIXES_CHANGELOG, any new trap in RULEBOOK
```

---

## 7. Where things live
```
C:\QGAI\
├── engine\         code + LIVE logs (logs\: bridge.log, dashboard.json, qgai.db, live_trades.csv)
│   └── docs\       FIXES_CHANGELOG 1–4  (what changed, by date)
├── backtest\       backtest scripts + bats
│   └── results\    ALL backtest output (wfo_results*, sweep_*, trail_compare, replay_logs)
├── data\           OHLC/ADX CSVs + merged\  + models\final\ (trained models)
├── Start\          one-click .bat launchers
├── RULEBOOK.md     do's / don'ts / traps  ← read before changing things
└── SYSTEM_OVERVIEW.md   ← this file
```
**Ground truth for current settings = `engine/config.py`** (docs can drift; code can't).
**`config_mt5.py`** holds real passwords — gitignored, never commit/push.
