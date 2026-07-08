# QGAI v2 — Bug Fix Changelog (2026-06-11)

All fixes are tagged in code comments as `FIX #N`. Search any file for "FIX #" to see them inline.

## CRITICAL
- **#1 bridge_dashboard.py** — `signal` NameError silently killed dashboard.json writes whenever win_prob > 0. Now reads `sig.get("signal")`.
- **#2 inference.py** — BUY/SELL latency cache never cleared on a new bar → stale previous-bar signal could be returned and traded. Both caches now invalidated per bar.
- **#3 scheduler.py** — launched non-existent `mt5_bridge.py`; bridge could never auto-start. Now `bridge_main.py`.
- **#4/#4b bridge_session.py** — Trade-2 Equity SL condition was logically impossible (`trades_today != 1` vs anchor set at ==2) → never fired. Fixed + anchor reset when flat. Unit-tested ✅
- **#5 bridge_main/bridge_session** — `on_trade_closed()` / `record_trade_result()` were never called: online learning, drift detection, auto-retrain, live_trades.csv were all dead in live trading. Now wired per closed trade.
- **#22 features/inference/bridge_main** — Live OHLC ("time" col) and live ADX (no datetime col) were DISCARDED by `drop_duplicates("datetime")`; signals ran on the startup CSV only. Live data now normalized + merged + re-engineered with the SAME `engineer_ohlc()` pipeline as training.

## HIGH
- **#6 bridge_main.py** — 60s sleep after each bar left virtual SL unmonitored for a full minute right after entry (broker SL is 3×). Loop now ticks every 2s.
- **#7 bridge_core.py** — removed malformed placeholder `order_send({action: DEAL})` fired at the broker after every fill.
- **#8 bridge_main/bridge_constants** — signals were computed on the just-opened forming bar (seconds old). Now evaluated on the LAST CLOSED bar (`USE_CLOSED_BAR = True`, set False to revert).
- **#9/#9b bridge_core/bridge_main** — numpy array truthiness crash in ATR fallback / pre-pop.
- **#10 scheduler.py** — model-exists check used wrong relative path → full retrain on every scheduler start. Now uses `CFG.paths.models_dir`.
- **#11 bridge_main.py** — `.reload_requested` flag now actually read: models hot-reload after weekly retrain.

## MEDIUM
- **#12 serve.py (NEW)** — dashboard server handling POST `/mode` and `/feedback` (plain http.server rejected POST; mode toggle & AI feedback silently failed). Feedback stored in `logs/feedback.jsonl`.
- **#13 QGAI_START.bat** — opens dashboard via `http://localhost:8000` (file:// could not fetch dashboard.json) and auto-starts serve.py.
- **#14 dashboard.html** — broker clock/heatmap offset now derived dynamically from dashboard.json (DST-safe; was hardcoded UTC+3). Local time remains strictly Broker + 2:30.
- **scheduler.py** — data-gap freshness check now compares broker-time vs broker-time (was utcnow vs broker → 3h blind spot).
- **#15 bridge_dashboard.py** — `news_near` no longer hardcoded False; derived from `is_pre_news` / `mins_to_3star`.
- **#16 bridge_core/bridge_main** — real lot size logged to DB/CSV (was hardcoded 0.02).
- **#18 bridge_risk.py** — `calc_lot` uses SYMBOL constant (was hardcoded "XAUUSD.pc").
- **#19 bridge_session.py** — deal dedupe is ticket-based (count-based could skip deals across day rollover); restart-safe.
- **#21 inference.py** — missing-feature warnings now also go to bridge.log.

## ⚠️ IMPORTANT AFTER UPDATE
1. **Fix #22 + #8 change live signal inputs** (real live data, closed bars). Run in MONITOR mode for 2–3 days and compare win_prob distribution vs old logs before going live.
2. **SECURITY: rotate the MT5 password** — config_mt5.py with live credentials was inside the shared zip.
3. Delete old `__pycache__` folders on the laptop before first run.

## DASHBOARD FIXES (round 2 — from live screenshot, 2026-06-11)
- **D1 dashboard.html** — LIVE TRADE strip P&L always showed +0.00: JS read `floating_pnl`/`profit` but backend sends `pnl_$`. Now reads the correct key.
- **D2 dashboard.html** — NEXT BAR countdown was reset to the stale JSON value on every 2s poll (never counted down). Now computed live from the clock: `900 − (epoch % 900)`.
- **D3 bridge_dashboard.py** — "Why This Signal?" panel read `d.why_signal`, a key that was never sent → MODEL/MARKET/VOL CONF stuck at "--". Backend now sends it (alias of market_structure, which has all required fields).
- **D4 dashboard.html** — MICRO showed impossible 0/100: JS read `micro_score`, backend sends `phase_score`.
- **D5 bridge_dashboard.py + dashboard.html** — On SKIP, Risk Grade was "--" but EV still showed a value. EV now null on SKIP, and JS renders "--" safely (no toFixed-on-null crash).
- **D6 dashboard.html** — "to SL: 18.62 pts" used the wrong unit: the value is dollars. Now "$18.62".
- *(Not a bug)* OB DIST "9.395" in the screenshot is actually "9.39$" — the font's $ glyph resembles a 5.

## DASHBOARD FIXES (round 3 — stale-cache crash, 2026-06-11)
- **B1 serve.py** — browser could keep running an OLD cached dashboard.html (pre-FIX-D5 JS → `ev_r.toFixed`-on-null crash on every SKIP signal) even after the file on disk was fixed. Server now sends `Cache-Control: no-store` on everything.
- **B2 dashboard.html** — build stamp `QGAI_BUILD` shown in footer + every error message, so you can always verify which version the browser runs. Render errors now show the line number and full stack in the console. Added global error trap for errors outside `load()`. Added safe `fmtN()` formatter; `fmtP()` and `ftc_r` hardened.
- **NOTE:** the page never reloads itself — it only re-fetches dashboard.json. After updating dashboard.html, always close the tab and reopen (or Ctrl+F5).
- **B3 bridge_dashboard.py + dashboard.html** — SYSTEM HEALTH panel showed a permanent false "❌ ERROR" with empty rows: the JS read `d.system_health`, a key the backend never sent (same class as D3). Backend now builds it every write — real file ages for data CSVs (OK <25h / STALE 25-72h / OLD+MISSING), model PKLs (weekly cycle: OK <8d / STALE <14d), and last-retrain age from `logs/.last_retrain`. Frontend shows neutral "— N/A" + restart hint if the key is absent (old bridge still running). **Requires bridge restart to take effect.**
- **B4 bridge_dashboard.py + dashboard.html** — "Today's Trading Slots" drew 33 active-looking slot pills while `use_slot_day_filter = False` (trading ignored them): `get_today_slots()` never checked the flag. Now returns an empty list when OFF → panel shows the honest "🤖 AI probability filter active — no fixed slots needed" message; grid returns automatically if the flag is turned ON. Also fixed `slot_filter_lbl2` stuck at "--" (JS wrote a different element ID). **Requires bridge restart.**
- **B5 bridge_dashboard.py + inference.py + dashboard.html** — three dead/false ANALYSIS-tab panels, all reading keys the backend never sent: (1) SIGNAL LOG + SIGNAL HISTORY read `d.signal_history` → "No signals yet" forever while SQLite had 2,863 rows; backend now sends the last 40 live/monitor signals incl. per-row effective threshold. (2) NEWS FILTER read `news_status`/`news_min_prob`/`effective_min_prob` → showed a hardcoded fake "Min: 52%"; backend now sends the real numbers (base 45%; Ranging 48% / Trending 45% / Volatile 42%; pre-news +5%) mirroring inference.py, and the JS fallback now uses `d.min_win_prob` instead of 0.52. (3) MARKET INTELLIGENCE: "3★ Dev Sign" — `last_3star_dev_sign` exists as a model feature but was never copied into the signal dict (added in inference.py `_make_result`); "H4 Since Big" row removed — `sig.h4_since_big` never existed anywhere in the pipeline. **Requires bridge restart.**

## M1 — MOVE-SIZE PREDICTOR (2026-06-11)
- **train_move_model.py (new)** — LightGBM quantile models (P25/P50/P75) predicting MFE in ATR units over next 12 bars. Chronological 70/30 split, holdout calibration: BUY Spearman 0.340 (+6.7% vs naive), SELL 0.325 (+5.0%), coverage honest. Both PASS.
- **inference.py** — loads move_model_*.pkl, ships pred_move_p25/50/75 (_atr + _pct) in every signal. Info-only; missing models = feature silently off.
- **dashboard.html** — new "Exp Move (3h)" row in Market Intelligence.
- **backtest_replay.py** — new `--tp-mode predicted`: TP1 = P50 move, TP2 = P75 move (floors: TP1 ≥ 0.6R, TP2 ≥ 1.2×TP1). A/B on Jan–Mar 2026 (move-model holdout, the collapse window): fixed → WR 39.1%, PF 0.89, −13.1R, DD 58.5% | predicted → WR 48.0%, PF 1.05, +13.9R, DD 38.5%.

## M2 — PREDICTED SL + TRAILING (2026-06-11)
- **train_move_model.py** — now also trains MAE (adverse move) quantile models per direction: sl_model_{buy,sell}_q{50,75}.pkl. Holdout calibration: BUY Spearman 0.335, P75 coverage 75% (perfect); SELL 0.341, coverage 71%.
- **inference.py** — loads SL models, ships pred_mae_p50/p75 (_atr + _pct) in every signal alongside pred_move_*.
- **backtest_replay.py** — new flags: `--sl-mode predicted` (SL = MAE-P75 × 1.1 buffer, clamped 0.5–2.0× ATR SL) and `--trail-mode predicted` (trail dist = MAE-P50, clamped 0.4–1.0× SL). Output files get mode suffix.
- **A/B/C on Jan–Mar 2026 (collapse window, move-model holdout):**
  fixed all → WR 39.1%, PF 0.89, −13.1R, DD 58.5%, −$1,097
  pred TP → WR 48.0%, PF 1.05, +13.9R, DD 38.5%, +$638
  pred TP+SL → WR 60.6%, PF 1.20, +22.2R, DD 20.5%, +$1,974

## M3 — FIXED-LOT FORWARD TEST + %-ONLY MEASUREMENT (2026-06-11)
- **config.py** — new switches: `use_fixed_lot = True`, `fixed_lot = 0.01`. Forward-test mode: every live trade exactly 0.01 lot (≈0.22% risk on $10k), %-risk sizing bypassed. Set False to return to risk_pct sizing.
- **bridge_risk.py** — `calc_lot()` honors the fixed-lot switch (respects broker min/step/max).
- **backtest_replay.py** — all reporting converted to % and R (no dollar amounts): net return %, avg/total R, avg win/loss in R, regime/hour/month tables in R. New `--dd-brake` flag: %-based drawdown brake (dd>10% = half size, >20% = quarter, >30% = halt).

## M4 — DIRECTION-AWARE PREDICTED MODE (2026-06-11)
- Full-data calibration (user machine, 27,374 bars): BUY PASS (Spearman 0.342, +7.4%, 89% monotonic). SELL FAIL (+2.9% < 3.0% threshold, P75 coverage 20% — too optimistic). Cause: gold's 2025 uptrend makes sell-side moves structurally harder to predict.
- **backtest_replay.py** — new `--pred-dirs` flag (default BUY,SELL): only listed directions use predicted TP/SL/trail geometry; others keep fixed live rules. For current models use `--pred-dirs BUY`.

## M5 — HYBRID RUNNER MODE (2026-06-11)
- Validation verdict (user runs, P1 Apr–Sep + P2 Oct–Dec 2025): predicted TP+SL wins quality everywhere (WR ~63% vs ~48%, DD halved); fixed trailing wins trend capture in Q4 (avg win +1.34R vs +0.80R). Combined honest holdouts: predicted +64.2R vs fixed +38.6R at ⅓ drawdown.
- **backtest_replay.py** — `--tp-mode hybrid`: partial close at predicted P50, runner UNCAPPED (no TP2), exits by trailing — keeps predicted protection + fixed mode's trend riding. (Equivalent: `--runner trail`.)
