# QGAI v2 — Changelog #4 (2026-06-19 → 06-23)

Continues FIXES_CHANGELOG / 2 / 3. Same convention: changes tagged in code with
dated comments (search files for `2026-06-19` / `2026-06-22`). All config flags
are reversible (old values noted inline). **Test on DEMO before live.**

Worked on by Anisa via Cowork. Shared PC / shared folder — this file is the history record.

---

## 2026-07-09 — Dashboard Audit (Ideal vs Current vs Fix) → `docs/DASHBOARD_AUDIT_2026-07-09.md`
Requested standalone audit (Fable-style prompt). Rating **RISKY**. Top risks: (1) leaky feature
`corr_imp_ratio` (Step-2 = Critical, future H4 candles) shown on board as `corr_ratio`; (2) backtest
sizing ≠ live — **confirmed** fixed_lot 0.01 in `step4_monthly_set1_36/backtest_summary_st-htf.csv`
(66 trades, max_dd 0.9%), so $/DD not live-equivalent; (3) WFO "too good" — full run = **53 weeks /
768 trades / +444.7R, pos=51 neg=1** (part2 52/0, hmm 52/0) = leakage signature, while leaky features
still in the set; (4) "STRENGTH" panel implies the ADX6 gate that is OFF + old formula cancelled ADX/slope;
(5) no provenance (git-commit/config-hash/data-range) on any output. **F-10 (new):** the clean-set control
(Set-2, 34-feat = current minus the 2 leaky feats) — the one test that would prove edge-vs-leakage — was
started but left unfinished (`step4_set2_clean_34/` has only 1 train log) → finish it first. Also:
`BY_REGIME` per-regime R exists in the backtest CSV but is not surfaced on any board.
*(Self-correction: an earlier draft cited "~4 trades/wk / max_dd 0.3%" — that was a truncated early-weeks
slice; the numbers above are the full-run reality.)* Full findings + KPI/mismatch/integrity tables +
roadmap in the linked doc. No code changed.

---

## 2026-07-09 — SIGNAL box mirrors the LOG + entry price atop BUY/SELL bars (Imtiyaz req)
Imtiyaz flag: SIGNAL LOG's newest row = SELL, but the big SIGNAL box showed SKIP (box's
State/Direction matched the current SKIP bar → backend freeze/bootstrap not active in the running
bridge). Verified `_bootstrap_last_trade_signal()` DOES find the last BUY/SELL in signals_all.csv
(864 actionable rows; last = 05:30 BUY 4080.41) → backend fix is correct, just needs the bridge
restarted with the new code. Added a **restart-independent frontend safety net** so the box can
never disagree with the log:
- **Frontend** `dashboard.html`:
  - `_parseSig()` now also captures `state_prob` + `dir_prob`; `window._liveSigData` exposed.
  - `update()`: when `d.last_signal` isn't an actionable BUY/SELL, the box falls back to the most
    recent BUY/SELL from `window._liveSigData` — the SAME signals_all.csv the SIGNAL LOG is drawn
    from → box mirrors the log's latest signal. EV/GRADE recomputed from win_prob when backend sends
    null. Shows the dim "🕒 last @ HH:MM" hint. **Ctrl+F5 only, no restart needed.**
  - `drawSigChart()`: entry price now printed **atop each BUY/SELL bar** — horizontal, bold 9px,
    black-outlined for contrast (earlier 7px rotated label was unreadable). Chart height `44→60px`,
    canvas internal height matches CSS for crisp text. SKIP bars unchanged.
- **Backend** `bridge_dashboard.py` → `get_signal_history()`: added `price` to the SELECT + output
  dict (feeds the chart's price labels). **Needs bridge restart.** Display-only, no filter/logic change.

---

## 2026-07-09 — `_gDate is not defined` crash + ADX vs MT5 explained (Imtiyaz flags)

**(1) `_gDate is not defined (line 1947)` — render crash.** The signal box showed no date, missing
WIN PROB/EV/GRADE/State/Direction, AND the Signal History chart was blank — ALL from ONE JS error.
`_gDate()` was defined INSIDE the live-signal-log IIFE (`<script>` at ~652), but the main `update()`
loop in a SEPARATE `<script>` block called it at line ~1947 → ReferenceError → every render step after
that line aborted (date, signal-box fields, `drawSigChart` at ~2438 all downstream). **Fix:** exposed it
globally — `window._gDate=_gDate;` right after the definition (dashboard.html ~673). Frontend-only →
needs a browser hard-refresh (Ctrl+F5), no bridge restart.

**(2) Dashboard ADX ≠ MT5 chart ADX — investigated (flag), NOT a bug.** STRENGTH showed H1 16.5 / H4 34.2
while MT5 read H1 12.92 / H4 28.19. Confirmed the box value = engine's live per-bar ADX (dashboard.json
04:00 bar: H1_ADX 16.49, H4_ADX 34.18 → rounds to 16.5/34.2), not frozen. Root cause = **smoothing method**:
the engine computes ADX with `ewm(span=14)` (alpha≈0.133; `regen_adx_di.compute_adx_tf`,
`mt5_data_updater.compute_adx_tf`, `regen_adx_asof.asof_tf` all identical) — MT5 uses **Wilder** smoothing
(alpha=1/14≈0.071), ~2× slower → engine reads higher in a rising-ADX phase. Secondary: (a) as-of convention
= last-CLOSED H1/H4 bars' EWM state + one step folding the **forming** (partial) bar, updated every M15 bar
(not tick like MT5's right edge); (b) pandas-resample bar boundaries vs MT5 broker-server-time bars; (c) MT5
ships two indicators (ADX vs ADX Wilder). **Live == training** (same `compute_adx_tf`), so the model is
self-consistent; its thresholds (H4>30 trending, <20 ranging) were learned on THIS EWM-ADX. **Decision: keep
as-is (option A)** — switching to Wilder would need a full retrain + backtest≠live re-verify. Added a
clarifying tooltip on the STRENGTH H1/H4 ADX pills (dashboard.html `pill()` gained an optional `tip` arg).
To compare on MT5, use **ADX Wilder, period 14**.

## 2026-07-09 — Decision box: BOOTSTRAP last BUY/SELL on fresh restart (was stuck on SKIP)

**Symptom (Imtiyaz):** after the "freeze box to last BUY/SELL" change + bridge restart, the signal box
still showed **SKIP** with WIN PROB / EV / GRADE / State / Direction all `--` and no date.

**Cause:** `_remember_last_trade_signal()` only cached a BUY/SELL when one arrived *after* restart, and
persisted it to `logs/last_trade_signal.json`. On the FIRST restart that file didn't exist yet, and only
SKIP bars had occurred since → `_LAST_TRADE_SIG` stayed `None` → box kept showing the live SKIP
(`signal_is_cached=False`). It would have self-healed only on the next live BUY/SELL (possibly hours).

**Fix (`bridge_dashboard.py`):** added `_bootstrap_last_trade_signal()` — when no persisted cache exists
on first load, it reads the most recent BUY/SELL row from `signals_all.csv` and seeds `_LAST_TRADE_SIG`.
Numeric columns (`_LTS_NUM_COLS`) are coerced to `float` so the decision block's arithmetic
(`ev_r = wp*tp_m …`, `round(state_prob,4)`) never hits a `str × float` TypeError. The block *computes*
eff_prob / ev_r / risk_grade / market-structure from raw fields (win_prob, state_prob, dir_prob, hmm_state,
atr20_pct …), all present in the CSV, so a CSV row is enough for a coherent box. Verified on the live file:
last BUY `2026-07-09 03:15` 54.44% → ev_r 0.361, GRADE B. Display-only; no filter/trade logic touched.
**Needs a bridge restart to load.**

## 2026-07-09 — Signal ↔ Trade DECOUPLE (Imtiyaz architecture) + new `trade_action` column

**Imtiyaz spec:** System = signal PROVIDER, MT5 = signal RECEIVER. A pure/virtual engine signal
(BUY/SELL/SKIP by threshold — exactly like backtest) must be logged on EVERY bar, regardless of
whether a trade is placed (system or manual) or whether an account is even connected. Signal must
NEVER stop, and trade-execution filters must NOT overwrite it.

**Root problem (verified):** in `bridge_main.py`, 11 trade-execution paths each called
`log_signal(bar_time, "SKIP", …)` — overwriting the engine's real BUY/SELL to "SKIP". This is
exactly why a high-prob (e.g. 78.59%) BUY showed **SKIP** in the log when a position was already
open (single-position HOLD) — backtest≠live in the signal column.

**Fix — two decoupled columns (logging only; NO trade-logic change):**

| Column | Meaning | Values |
|--------|---------|--------|
| `signal` | PURE engine decision — every bar, backtest-identical | BUY / SELL / SKIP |
| `trade_action` (**NEW**) | what the RECEIVER (MT5) did | EXECUTED · EXEC_FAILED · HOLD_IN_TRADE · OPPOSITE_HANDLED · MONITOR · BLOCK_SLOT · BLOCK_RANGE · BLOCK_CTF · BLOCK_PULLBACK · BLOCK_SMMA · BLOCK_ADX · RESUME_SKIP · NO_TRADE |

- `bridge_main.py`: all 11 `log_signal()` sites now pass the **real `signal`** + a `trade_action=`.
  Execute path logs `EXECUTED` if a lot came back else `EXEC_FAILED` (so a no-account / AutoTrading-OFF
  / retcode-10027 failure no longer hides the signal). Control flow / filter blocking logic **unchanged**.
- `bridge_data.py`: `log_signal(..., trade_action="")` new param; new trailing `trade_action` column in
  CSV, `signals_complete.csv`, and SQLite (`ALTER TABLE signals ADD COLUMN trade_action`, one-time).
  `_ensure_signal_columns()` migrates old CSVs (blank for old rows).
- **Test:** `Test_Decouple_Signal.bat` → `engine/test_decouple_signal.py` (offline, TEMP db+csv, live
  files untouched). 10/10 checks PASS incl. the 78.59%→HOLD_IN_TRADE case + old-file migration.

**Dashboard (done same day):** `dashboard.html` SIGNAL LOG (`_parseSig` + `_liveSigRender`) now parses
the new `trade_action` column and shows a colored badge per row (EXECUTED=green · EXEC_FAILED=red ·
HOLD_IN_TRADE=cyan · BLOCK_*=orange · MONITOR=blue · OPPOSITE_HANDLED=purple; NO_TRADE hidden as
redundant on SKIP rows). So a high-prob BUY that MT5 held now reads `BUY … HOLD_IN_TRADE`, not SKIP.

**Remaining:** restart bridge + dashboard server to activate (new column populates on next bar).

---

## 2026-07-09 — SIGNAL LOG: virtual entry→exit→move on EVERY BUY/SELL (Imtiyaz)

**Imtiyaz spec:** in the SIGNAL LOG, every BUY/SELL must show its price move — e.g. `buy 4076 → exit
4100 = +$24` — **whether or not a real trade was placed** (system = signal provider, like backtest).
Exit-price calc "seemed to be missing" → make it visible + complete.

**Root cause (verified — nothing was actually broken in the engine):** the exit-price calc already
exists — `shadow_ledger.py` paper-trades EVERY BUY/SELL signal from `signals_all.csv` with the live
exit rules (HTF-H1 stop + flip, ratchet buffer, far TP) and writes `logs/shadow_trades.csv`
(entry_price, exit_price, exit_reason, R, pnl). Scheduler refreshes it every 15 min (`scheduler.py`
`shadow_ledger.py`, 821 signals: 42 real + 779 paper). What was missing was **display**: the old
badge (a) only showed for non-real signals (real rows used the `move` col, which is blank on older
rows → "WIN" with no price → looked like "no exit calc"), and (b) never showed the entry→exit prices
inline, only the move number.

**Fix (dashboard-only — NO engine / data-path / trade-logic change):** `dashboard.html`
`_liveSigRender()` rewritten so that:
- **Every BUY/SELL row** now renders the SIGNAL's virtual result inline from the shadow ledger:
  `4076.00→4100.00  +$24.00  +2.5R  TPᵛ` (green profit / red loss, dashed border, ᵛ = virtual).
  Shown whether or not a real trade was placed (matches the provider/backtest spec).
- If a **real trade also closed** on that bar, an extra solid `WIN/LOSS +$move REAL` chip is appended
  (real account result kept SEPARATE from the virtual signal result — no contradiction).
- Tooltip gives full detail (entry, exit, move, R, exit reason, real-vs-paper, account outcome).

No new CSV columns, no bridge change. **Activation: just hard-refresh the dashboard browser**
(shadow_trades.csv is already produced by the scheduler). Very recent BUY/SELL show the badge once the
trade exits + next shadow refresh (≤15 min) — same as backtest (exit unknown until it happens).

---

## 2026-07-09 — Decision area shows the LAST BUY/SELL signal (not a SKIP bar) + SKIP win% dim

**Imtiyaz spec:** the signal box must show the **last placed signal** (last BUY/SELL) with ALL its
params, and the **AI DECISION SUMMARY** + **MARKET INTELLIGENCE** boxes above must show data for that
SAME signal — a plain SKIP bar should not overwrite/blank the decision area.

**Fix (backend `bridge_dashboard.py` — display only, NO trade-logic change):** the whole decision
block (hmm/state/dir prob, `market_structure`, `eff_prob`, `ev_r`, `risk_grade`, `ai_summary`,
`market_intel`, win/big-win/duration inside `sig`) is all derived from one `sig` dict. Added a
last-actionable-signal cache — `_remember_last_trade_signal()` — that returns the most recent BUY/SELL
signal (persisted to `logs/last_trade_signal.json`, survives restart). `write_dashboard()` now freezes
`sig` to that at line ~508, so the entire block stays coherent on the last real signal. **Live price /
spread / session / open-trades / countdown come from `tick` (not `sig`) → they stay live.** When a
cached (past) signal is shown, `signal_confirmed` is forced True (renders directly, not "forming") and
a new `signal_is_cached` flag is sent.
- `dashboard.html`: the `sig_confirmed_tag` span now shows a dim **🕒 last @ HH:MM** hint (the signal's
  own bar time) whenever `signal_is_cached` — so a frozen past signal isn't mistaken for the live bar.

**Also (same day) — SIGNAL LOG win% colour:** on a **SKIP** row the win_prob no longer shows gold; it
stays dim like the SKIP text. Gold only for an actual BUY/SELL ≥45%. (`dashboard.html` `_liveSigRender`.)

**Also (same day) — date format + signal-box date/time:** new `_gDate()` helper →
`2026-07-09 23:15` renders as **`9 Jul 26 23:15`** (day + 3-char English month + 2-digit year). Applied to
(a) the SIGNAL LOG time column (was `MM-DD HH:MM`), and (b) the SIGNAL BOX — which previously showed
NO date/time (the old `signal_bar_time` element didn't exist); added a `signal_datetime` span in the
card header showing the signal's full date+time. (`dashboard.html`, frontend — browser refresh only.)

**Activation:** signal-box/AI/intel change is BACKEND → needs a **bridge restart**. The SKIP-colour +
virtual-move badges are frontend → just a browser hard-refresh.

---

## 2026-07-08 — Deep bug check + FORMING/CONFIRMED signal fix

**7 bugs found and fixed across 3 files:**

| # | File | Severity | Bug | Fix |
|---|------|----------|-----|-----|
| 1 | dashboard.html | CRITICAL | `_isConf` TDZ error — AI Decision Summary never rendered (silently swallowed by try/catch) | Moved `const _isConf` declaration before first use |
| 2 | bridge_main.py | CRITICAL | `import sys` missing — `sys.exit(1)` in news-stale guard throws NameError, bridge continues with stale calendar | Added `import sys` |
| 3 | bridge_main.py | MODERATE | SMMA/ADX block SKIP double-logged — guard at line 681 didn't check `_smma_block`/`_adx_block` | Added both to the elif guard |
| 4 | backtest_replay.py | CRITICAL | EOD-closed trades missing from `trades_out` — equity changed but trade invisible in CSV | Added full record dict + append for EOD trades |
| 5 | backtest_replay.py | CRITICAL (latent) | `sl_dist` undefined when `--ratchet off` → NameError on first trade | Added fallback `sl_dist` for non-ratchet mode |
| 6 | backtest_replay.py | MODERATE | REVERSAL trade records always had None for win_prob/hmm_state — accessed `_tr.win_prob` instead of `_tr.sig.get("win_prob")` | Fixed to `_tr.sig.get(...)` |
| 7 | backtest_replay.py | MODERATE | NaN ADX bars reset death streak to 0 instead of leaving unchanged | Changed init to -1, skip streak update on -1 |

**FORMING/CONFIRMED signal fix (Imtiyaz request):**
- Dashboard now suppresses forming-bar BUY/SELL — shows SKIP until bar-close confirmed
- AI Decision Summary also suppressed — ✅/⏳ icon on SIGNAL pill
- Both main signal card and summary card stay consistent

---

## 2026-07-08 — ADX-death exit rule (Imtiyaz idea + Fable-5 design)

**Insight (Imtiyaz):** ADX slope falling across TFs during hold = trend dying = give-back coming.
Data: 0 TFs falling = +1.34R avg, 4 falling = −0.23R avg. Strongest exit signal found this session.

**Rule (Fable-5 design):** At each M15 bar close: if K≥3 of 4 TF ADX slopes ≤0 for N≥3 consecutive
bars AND unrealized profit ≥0.5R → exit at bar close, reason `ADX_DEATH`.
Slopes: M15=diff(1), M30=diff(2), H1=diff(4), H4=diff(16).

**Changes:**
- `engine/config.py`: FilterConfig + `adx_death_enabled=False, _k=3, _n=3, _min_r=0.5`
- `engine/backtest_replay.py`: precompute 4-TF ADX slope arrays from ohlc before bar loop;
  in trade mgmt loop after ratchet_bar, track per-trade death-streak + exit check
- Env overrides: `QGAI_ADX_DEATH=1`, `QGAI_ADX_DEATH_K`, `_N`, `_MIN_R`
- Default **OFF** → live unchanged until sweep + WFO validation

**Test bats:**
- `backtest/_runners/Run_ADXDeath_TEST.bat` — 2-week smoke test
- `backtest/_runners/Run_ADXDeath_Sweep.bat` — 18-cell K{2,3}×N{2,3,4}×X{0.3,0.5,1.0} + baseline

**Gate:** WFO ≥+444.7R AND Trending R not down AND avg-winner-R down <5% AND median R-saved >0

---

## 2026-07-07 — FIX-3 parity (Fable-5 #1): reversal-close modeled in backtest
Worked on by Claude via Cowork (Imtiyaz). Fable-5 ranked this #1 ("stop adding gains you can't collect").

**Gap:** live `bridge_core.handle_opposite_signal` closes an open trade EARLY on an opposite
signal (in LOSS → exit if new_prob≥0.45; in PROFIT → exit if new_prob≥0.60) and re-enters.
The backtest NEVER modeled this → a major source of the ~12% live-vs-backtest entry overlap
(live cuts trades the backtest holds to SL/TP/flip). (The forming-H1-bar gap turned out already
handled — `backtest_replay.py:356-362` added forming parity 2026-06-30.)

**Fix:** `backtest_replay.py` — after the signal is picked, if an open trade is OPPOSITE and the
live exit thresholds are met, close it (`exit_reason="REVERSAL"`) and let the new entry proceed.
Flag-gated `QGAI_BT_REVERSAL=1` (default OFF → +444.7R baseline unchanged). Smoke (30-day):
18→79 trades, 11 REVERSAL exits fired, no crash.

**RESULT (2026-07-08, Fable-5 re-read):** Reversal-close is NOT the main gap. Reconcile over the
live period (2026-06-09→07-07) vs shadow: overlap 13.6%→15.2% (+1.6pp only). Full-year reversal ON
= 903 tr / WR 62%→50% / +406.6R = low-quality re-entry churn → keep OFF. **The "12% overlap" is
dominantly a SHADOW-ENGINE ARTIFACT, not live≠backtest:** `shadow_ledger.py` enforces NO max_open
(sims all 143 signals in parallel) while backtest+live hold 1 position. Verified: shadow's 154
entries collapse to 44 under a 1-position lock (vs backtest 66) — the entry gap is blocked-signal
artifact + exit-hold-time, not missed trades. On matched trades backtest books 0.6R LESS than
shadow → **if +444.7R is biased it's PESSIMISTIC, not optimistic.** **FIX-3 REDEFINED:** drop the
shadow-overlap metric (confounded); the real task = `backtest_replay` ↔ `bridge_core` (live truth)
**exit/trail/flip/TP parity via code diff**. Entry-count + exit-mix + matched-R gaps are all
downstream of the trail logic. Keep demo running as the final entry-side arbiter. `adx_fs_div` etc.
Reversal flag stays wired (OFF) for reference.

**⚠️ Caught during this work:** the PART-2 `Run_Part2_ADXComposite_FULL.bat` retrains composite
models INTO `data/models/final` — after the (rejected) PART-2 WFO it left composite-31 models on
disk (ts 20260708_0000). Restored validated raw-36 from `_backup_part1_raw35`. Live bot memory was
still raw-36 (safe); the restore makes the next restart safe too. **RESOLUTION: both PART-2 bats
DELETED (`Run_Part2_ADXComposite_TEST/FULL.bat`) so the composite model can never be accidentally
retrained into the live folder again.** The composite feature code + `QGAI_ADX_MODE` toggle stay
dormant in `features.py` (default raw, harmless — like the other parked gates). To restore raw-36
if ever needed: `xcopy /E /I /Y "C:\QGAI\data\models\_backup_part1_raw35" "C:\QGAI\data\models\final"`.

---

## 2026-07-07 — Dashboard upgrade + tooling (Fable-5 dashboard review)
Worked on by Claude via Cowork (Imtiyaz).

**Dashboard (`engine/dashboard.html` + `engine/bridge_dashboard.py`):**
- **Config badges** (System Settings card): CTF Fade / Range Skip / DD Brake / Reversal Gate /
  ADX Mode — color-coded ON/OFF, live from config.
- **🛡️ Account Health & Risk State card** (Fable-5 #1/#2): per-account rows (PRIMARY/MIRROR ·
  balance · DD% · brake-scale · last-order FILLED/REJECTED) with red-highlight on a mirror reject
  while primary filled (would have caught the DD-brake silent-reject bug in one trade); full-width
  **DD-BRAKE HALT banner**; open-trade **$ at risk** (vSL distance × lot); **daily-SL headroom**
  ($used/$limit, color-escalating). Data via new `bridge_multi.ACCOUNT_HEALTH` tracker
  (`get_account_health()`) recorded at connect/order/skip. All render wrapped in try/catch +
  null-guards (JS-crash history); node-validated.
- **Deferred (Fable-5 #3, investor-prereq):** sim/live visual split + DEMO watermark + `n=` labels.

**Signal log:** `signals_complete.csv` was stale at 2026-07-03 (dashboard SIGNAL LOG stuck at
~25k). Rebuilt via `build_signal_log.py` → 97,908 bars through 2026-07-07. New one-click
`backtest/_runners/Rebuild_SignalLog.bat` (uses the correct Python312, not the uv python).

**Master launcher:** `Start/0_START_ALL.bat` — one-click cold-start: data update → chart refresh →
shadow ledger → signal-log rebuild → bridge (own minimized window) → dashboard server :8000 (own
minimized window) → open browser. So every dashboard tab has fresh data on launch. **Training is
deliberately EXCLUDED** (stays manual `3_Train_Models.bat`) — auto-retrain on startup is exactly
what caused today's model mismatch; training must stay a conscious, WFO-gated decision.

**Config-print (`bridge_main.py`):** RUNNING CONFIG now prints ENTRY GATES (range/CTF/reversal) +
DD BRAKE + vSL-persist state on every restart for verification.

---

## 2026-07-07 — Feature PART 1: drop 6 dead EA-threshold-combo features (needs retrain)
Worked on by Claude via Cowork (Imtiyaz). Fable-5 feature audit.

**Context:** `data/models/final/feature_importance.csv` shows 6 features at EXACTLY 0.0000
importance — all hand-crafted EA-threshold combos of raw ADX/DI features the tree already
has (XGB rebuilds the interactions). Fable-5: "DROP NOW, high confidence." Prior turn's data
also confirmed every EA-threshold ADX feature (19/20/25/30 cutoffs) is dead — the model uses
raw continuous ADX/DI (M15_DI_diff #5, M15_ADX #6, H4_DI_diff #10 are top levers) not the EA
cutoffs.

**Dropped (added to `features.py::_MANUAL_PRUNE`):** `adx_trend_count`, `h4_trending_h1_aligned`,
`h4_ranging_h1_neutral`, `h4_h1_regime_score`, `h4_in_ob_zone`, `trade_direction`.
Main model 41 → **35 features** (+ hmm_state = 36). Hybrid: Ranging 28, Trending 24, Volatile 16.

**Validation: ✅ ADOPTED 2026-07-07.** Retrained on 35-feat, WFO over live period (53 weeks):
**Total R = +444.7R vs +393.7R honest baseline = +51.0R (+13%)**, 51/53 positive weeks
(1 negative), avg +8.39R/week, 768 trades. The dead features were adding overfit noise, not
just neutral weight — dropping them IMPROVED OOS R materially. Result: `wfo_part1_prune35`.
Backup at `data/models/_backup_pre_part1_prune`. Live now 35-feat (bridge restart to load).

**Feature reference:** full per-feature importance + redundancy analysis (what each feature does,
tier ranking, which are dead) → `docs/FEATURE_DETAILS_2026-07-07.md`.

**PART 2 (❌ REJECTED 2026-07-07):** ONE-shot ADX consolidation — 10 raw ADX/DI → 5 tanh composites
(`adx_dir_fast/slow`, `adx_str_fast/slow`, `adx_fs_div`), env `QGAI_ADX_MODE=composite`, model 35→30.
TEST passed (AUC 0.677→0.705, all 5 composites alive). **FULL WFO = +405.6R vs +444.7R baseline =
−39R (−8.8%), 52/53 positive weeks.** Higher AUC but LOWER total R — accuracy ≠ profit; the raw
per-TF ADX/DI features carry information the 5 composites lose. Fable P(beats)≈30% was correct.
**DECISION: keep PART-1 raw-36 (validated, live). Never set `QGAI_ADX_MODE=composite`.** Composite
model discarded; live already on raw-36. Bats kept for the record. Lesson: a cleaner/simpler
feature set with higher AUC can still lose R — always WFO-gate on total R, not AUC.

---

## 2026-07-07 — FAB audit batch 2: S-1, S-3, H6, H8, H9, M11, M12, M14 fixed
Worked on by Claude via Cowork (Imtiyaz). Fable-5 system audit follow-through.
Each finding re-verified against code before change (S-2 was a false positive → all verified first).

- **FAB-M11 (picker, prime-directive):** `bridge_main.py` + `backtest_replay.py` picker now
  prefers any actionable BUY/SELL over a higher-`win_prob` SKIP (was: blind max(win_prob) →
  a tradable signal could be silently dropped when the other side's SKIP had higher prob).
  Mirrored in backtest for parity. Behavior-neutral on smoke week (rare edge case).

- **FAB-H8 (checkpoint resume):** `_resume_sig` now folds `sorted(QGAI_* env)` + model `.pkl`
  mtimes. Changing an env toggle or retraining → signature mismatch → fresh run (kills the
  WFO-cache class bug, BUG_LOG #H ghost).

- **FAB-H9 (ADX gate live wire):** `adx_strength_soft_block` + combined SMMA+ADX penalty cap
  (≤0.08, required ≤0.60) wired into `bridge_main` dormant (default OFF) so live==backtest if
  `adx_strength_soft`/`QGAI_ADX_STRENGTH` is ever enabled. Init `_sm={'penalty':0.0}` guards
  the SMMA-off path.

- **FAB-H6 (replay ADX lookahead):** `get_live_adx()` now truncates history to bars
  at-or-before `bar_dt` (true as-of) instead of always computing today's latest and merely
  labeling the row. Overnight replay passes `bar_dt` per bar → BACKFILL/shadow rows no longer
  lookahead-tainted. Live loop bar_dt≈now → no-op.

- **FAB-S3 (live DD brake):** NEW `engine/dd_brake.py` — persists peak equity
  (`logs/dd_peak.json`), `risk_scale(equity)` returns {1.0,0.5,0.25,0.0} by drawdown band
  (dd>10%→½, >20%→¼, >30%→halt). Wired into `bridge_risk.calc_lot` (scales raw lot); 0-lot
  halt band → `bridge_core.execute` skips new entry. Protective only → prime-directive safe.
  **2026-07-07: `enable_live_dd_brake` set True (Imtiyaz) — ON for real capital.**
  **⚠️ BUGFIX same day (live-caught):** first version used ONE global peak → the bridge's
  mirror SECONDARY accounts ($2k/$10k) were compared against the PRIMARY's $1.1M peak →
  99% false-drawdown → risk ×0.0 → secondary orders rejected (10014). Fixed to PER-ACCOUNT:
  peak keyed by `mt5.account_info().login`, so each account tracks its own peak (old flat
  schema auto-migrates). Verified: primary/cent/onefunded all ×1.0 at their own equity;
  primary −15% → ×0.5. **Needs bridge restart to load (running bot has old global-peak code).**

- **FAB-S1 (reversal filter bypass):** `handle_opposite_signal` reversal RE-ENTRY historically
  called `execute()` directly, bypassing every entry filter. New config `gate_reversal_entries`
  (default **OFF** = legacy behavior). When True: closes the losing side, returns False → the
  main loop re-evaluates the same bar's signal through the full filter stack and opens only if
  it passes. Enable after a backtest that also models close-on-opposite (parity TODO, tracked
  in FILTERS_MASTER §PARITY GAPS #2).

- **FAB-M14 (config re-enable trap):** SMMA gate comment rewritten to "🔴 PROVEN HARMFUL, DO
  NOT FLIP" (was "flip to True after DEMO"). Dead session keys (`use_time_filter`,
  `enable_ny_session`, `enable_morning_session`, `window1/2_*`) verified 0 readers → marked
  ⚰️ DEAD and flipped to False (no behavior change).

- **FAB-M12 (parity-gap doc):** 7-gap table written to `docs/FILTERS_MASTER.md §PARITY GAPS`
  with per-gap status. NOTE: `manual_risk_pct=6.0` (lines 106/110) vs 3.0 (255) is **INTENTIONAL
  design** (Imtiyaz) — a manual trade open by the user caps at 6%. Claude briefly "fixed" it to
  3.0 then REVERTED on owner correction. Do NOT unify. Lesson: confirm before changing any
  risk/trading setting.

**Deferred (with reason, tracked in TASKS.md):** S-5 (forming-bar — profit tradeoff, needs
forming-replay backtest, don't silently flip Anisa's setting), H-7 (backtest daily-SL
mark-to-market — would shift the +350.2R baseline, flag-gate first), M-10 (HMM hysteresis —
stateful behavior change, needs backtest before live), L-15 (is_dead_hour — retrain cycle),
L-16 (backtest exit spread — would shift baseline).

**Verification:** AST syntax OK on all 9 touched files; `dd_brake`/`vsl_persist`/`news_updater`
round-trip tested; full backtest smoke (1 week) = +11.1R, no crash. Live changes effective on
next bridge restart.

---

## 2026-07-07 — FAB-S2: News calendar false-positive + defensive staleness check installed
Worked on by Claude via Cowork (Imtiyaz). Fable-5 audit claim reviewed on real file.

**Fable-5 claim:** `news_all_2024_to_now_pure_cleaned.csv` last event 2026-05-15;
`is_pre_news`/`is_post_news` always 0; bot silently trading NFP/CPI at Volatile 0.42.

**Reality check (2026-07-07):** file has **33,134 events, earliest 2024-01-01, latest
2026-12-05**. Last 30 days: 628 low + 306 med + **65 high-impact** events (including
CPI 2026-12-05, Core CPI, 10-Year Note Auction). Calendar is NOT stale.

**Root of the false positive:** Claude previously showed Fable `tail -3` of the file
which happened to land on 2026-05-15 CFTC rows (alphabetically-sorted within same date
chunk). Fable took this as "last event" — actually the file continues 5 months into
future.

**Defensive check installed anyway** (real risk if file *does* age out):
1. **NEW `engine/news_updater.py`** — `check_staleness(max_days=N)` returns snapshot
   `{last_event, next_event, days_old, stale, reason}`. `refresh(force)` tries
   `investpy`; falls back to manual instructions if lib missing.
2. **`bridge_main.py` startup assertion** — after news load, runs staleness check.
   If stale: ERROR banner with last/next/days_old + fix instructions. If
   `pause_if_news_stale=True` (default False): `sys.exit(1)` to refuse startup.
3. **Config keys added** (`config.py::FilterConfig`): `news_max_stale_days=7`,
   `pause_if_news_stale=False`.

**Test:** `check_staleness()` returns `stale=False, last=2026-12-05 21:00, next=
2026-08-01 00:10, age=0.0d`. Startup log will print `News calendar OK ...` on
next restart. AST syntax check on all touched files: OK.

**Files:** `engine/news_updater.py` (NEW), `engine/bridge_main.py` (startup check),
`engine/config.py` (2 new keys). Live change effective on next bridge restart.

**Meta lesson:** shared summaries with Fable — quote a `head` + `tail` + full-file
`wc -l` at minimum. `tail -3` alone can mislead when the CSV is sorted by day+
event-name (multiple events share a timestamp).

---

## 2026-07-07 — FAB-S4: vSL persistence + broker-SL tighten (Fable-5 audit fix)
Worked on by Claude via Cowork (Imtiyaz). Fable-5 audit finding.

**Bug:** On bridge restart, `bridge_core.recover_open_trades()` (formerly line 626-637) tried
to read `VSL=`/`SL=` regex tags from the position comment. Comment format is now
`QuantEdge AI | {phase}` (line 225) — has no tags. **Every restart fell to the broker-SL
fallback** which reconstructed vSL from `broker_sl / 3.0` = entry-level vSL. Any trailed
gain was silently forfeited. If `pos.sl==0`, an invented `sl_dist=15.0` was used, giving
random risk. Also, disaster broker SL was 3× vSL_dist = ~9% account risk if the bridge
died mid-trade — larger than the 9% daily-SL halt.

**Fix:**
1. **New module `engine/vsl_persist.py`** — JSON round-trip of per-ticket vSL state at
   `logs/vsl_state.json` (atomic tmp+rename write). Schema: `virtual_sl`, `sl_dist`,
   `direction`, `entry`, `breakeven`, `trailing`, `updated` (ISO8601 UTC).
2. **`bridge_risk.py::VirtualTrade.check_ratchet()`** — persist after every trail update
   (line ~110). Import guarded with `try/except ImportError`.
3. **`bridge_core.py::execute()`** — persist immediately on trade open (line ~276) so
   a crash-right-after-open keeps entry-level vSL, not the fallback.
4. **`bridge_core.py::_partial_close()`** — persist after partial + BE flag update.
5. **`bridge_core.py::recover_open_trades()`** — priority: (1) persist file (has TRAILED
   vSL) → (2) legacy VSL=/SL= regex → (3) broker-SL fallback (WARNING now). Also
   restores `breakeven`/`trailing` flags so ratchet doesn't reset them.
6. **`bridge_core.py::__init__` + `_forget_ticket(ticket)`** — new helper that dels from
   in-memory dict AND removes from persist file. All 6 `del self.virtual_trades[...]`
   sites converted to `self._forget_ticket(...)`. Idempotent.
7. **Stale prune** at end of `recover_open_trades()`: drop persist entries for tickets
   the broker no longer holds (closed while bridge was down).
8. **Broker SL tightened `3.0 → 1.5×`** (`bridge_core.py:215/221` + last-resort
   reconstruction divisor). Fable-5 recommendation. Halves disaster-crash risk.

**Test:** `vsl_persist` round-trip save/get/remove verified. AST-syntax check on all
touched files passes. **Live change effective on next bridge restart** — existing open
positions will follow the legacy fallback until they close; new opens are persisted.

**Files:** `engine/vsl_persist.py` (NEW), `engine/bridge_risk.py`, `engine/bridge_core.py`
(6 del-sites converted, execute/partial/recover updated, broker-SL divisor changed 2x).

**Rollback:** Delete `engine/vsl_persist.py` + revert bridge_core / bridge_risk. The
`try/except ImportError` guards mean the system still works if `vsl_persist.py` is missing
(falls back to legacy regex + broker-SL reconstruction — the pre-fix behavior).

---

## 2026-07-07 — LIVE CONFIG CHANGE: Counter-trend-fade DISABLED (Path-A +34.3R proven)
Worked on by Claude via Cowork (Imtiyaz). Independent Fable-5 audit.

**Change:** `config.py:74` `skip_counter_trend_fade: True → False`.

**Why:** Path-A live-parity full-year backtest (2025-06-29 → 2026-06-29, `backtest_replay.py`):
- Baseline (CTF ON): 644 tr / +350.2R / WR 62.3% / PF 3.23 / DD 0.9%
- CTF OFF: **673 tr / +384.5R / WR 62.7% / PF 3.43 / DD 1.1%** = **+34.3R (+9.8%)**

**Root cause (Fable-5):** CTF was a pure EA rule with zero ML input — blocking trades against
the dominant TF (H1/H4 higher-ADX) when that ADX slope was falling. Prior blocked-trade audit
established that alignment ANTI-correlates with profit: 0/3 SMMA-aligned = WR 77% (best),
3/3 aligned = WR 60% (worst). CTF was cutting exactly the 77%-WR counter-aligned cohort that
IS this pullback/mean-reversion-flavored system's edge. 29 extra trades taken, mostly winners
(WR +0.4pp on more trades). DD +0.2% is acceptable.

**Reversible:** set `skip_counter_trend_fade=True` OR env `QGAI_CTF_FADE=1`. Backtest can
force via `--ctf-fade` or the env flag. Bridge restart required to load new config.

**Files:** `engine/config.py:74`, `docs/FILTERS_MASTER.md` (#4 status + change-log row).

**Fable-5 predicted range:** +5 to +25R. Actual +34.3R exceeded upper bound — CTF was cutting
more edge than estimated.

---

## 2026-07-03 — ET1: trend-following PULLBACK entry (fix late "buy-the-top") — flag-gated, sweep-ready
Worked on by Claude via Cowork (Imtiyaz). Design → `docs/ENTRY_TIMING_REDESIGN.md`. Independent Fable-5 review.

**Problem (Imtiyaz flagged):** entry is 100% ML `win_prob`-gated (`inference.py:733`). On the 02-03 Jul gold
rally (`signals_all.csv`) HTF ADX/DI aligned bullish for hours (H4 DI_diff +24) while `dir_prob` stayed
~0.32 → all SKIP; only the 04:00 breakout candle (+29 pts, 4147→4176) flipped `dir_prob` to 0.625 → BUY
fired at 4176, top at 04:15 = 4187. `dir_prob` is a **coincident/breakout-confirming** signal → buys the top.
(Confirmed owner saw it in the signal-log/dashboard, NOT a live trade — those rows were BACKFILL, bot offline
overnight.) Threshold/filter tuning can't fix a lagging trigger → structural fix.

**Fix (structural, ATR-free) — split DIRECTION from TIMING.** New shared gate `trend_pullback_block(sig,cfg)`
in `inference.py` (used by BOTH live `bridge_main.py` AND `backtest_replay.py` → parity by construction):
DIRECTION = HTF `ts_adx_switch_trend` matches trade + `ts_htf_agreement` ≥ min + ADX rising (`h1/h4_adx_slope`);
TIMING/anti-chase = `ts_line_dist_pct` (signed % of price from the active ratchet line — ALL already-computed
features, no new indicators; ATR stays removed since 2026-06-19). Block if not reclaimed (sdist<0), if chased
(sdist>chase_max), or established-trend-not-pulled-back (sdist>pb_near unless `ts_flip_recent`). ML kept as a
future quality-veto (Sweep B); Sweep A is deterministic, ML-veto OFF, runaway OFF. Ground-truth correction:
`band_rel` is a band-WIDTH/vol ratio (`regen_adx_asof.py:107`), NOT price-to-line distance — so `ts_line_dist_pct`
is used, not band_rel.

**Files:** `config.py` (FilterConfig: `trend_pullback_entry`=False master flag + `pb_near_pct`/`chase_max_pct`/
`htf_agreement_min`; env overrides `QGAI_PB_ENTRY/NEAR/CHASE/AGREE`), `inference.py` (gate fn + `ts_*` exposed in
result dict), `bridge_main.py` (live `_pb_block` wired after ctf), `backtest_replay.py` (same gate + `blocked_by=pullback`
+ `ts_*` in signals CSV), `run_wfo.py` (`--sweep-pb-entry` → `do_pb_entry_sweep`: baseline + 18 combos, one weekly
retrain shared, exit fixed live-faithful htf+regime, ranked `PBSWEEP_SUMMARY.csv` with vs_baseline + WINNER/REJECT
verdict). Bats: `backtest/Run_PBEntrySweep_AsOf_TEST.bat` (--weeks 2) + `_FULL.bat` (full year), as-of leak-free workdir.

**DEFAULT OFF → live behaviour unchanged.** Smoke test (1 wk direct backtest): flag-OFF baseline = unchanged path
(13 tr/+41.55%); flag-ON default = gate active (89 signals blocked, 4 tr/+9.31% — default params too tight in that
window, expected; the sweep decides). Compile-clean, `_pb_combos()` = baseline+18 verified. **ACCEPTANCE:** adopt the
combo with highest total R that BEATS baseline; if none, REJECT. PENDING: run TEST bat → FULL sweep → (Sweep B: ML
re-train veto + runaway) → DEMO → live. Reversible: `trend_pullback_entry=False`.

**OUTCOME (same day) — PARKED, baseline kept.** Sweep-A TEST (2 wk, as-of) ran clean (plumbing verified: 19 combos
ranked, verdict + `PBSWEEPT_SUMMARY.csv`). Result: **NO combo beat baseline** — baseline +12.8R/14tr vs best pullback
+7.7R (a1_n*_c030) /5-7tr; total R fell monotonically as the gate tightened (c030>c025>c020, a1≥a3), i.e. the block
cut *winners* in that window. Structural takeaway: a block-only filter can only REMOVE trades, never re-time them —
it can help only when the blocked trades are net-negative (that window they weren't). Imtiyaz chose to **keep baseline**;
FULL-year sweep NOT run. Live unchanged (`trend_pullback_entry` stays False, gate dormant). Code kept for a future
revisit (run `_FULL.bat`, or redesign to GENERATE pullback entries rather than block).

**v2 GENERATE mode (same day) — the real fix, built + promising.** Per the block-only limitation above (a filter can
only REMOVE trades, never re-time them), Imtiyaz chose to build the GENERATE version: **create an early entry** in the
dominant HTF trend direction when the ML SKIPs but price pulls back to the ratchet line — so we enter EARLY on the dip
instead of at the late ML top-signal. Refactored the pullback logic into a shared `_pullback_ok(sig,d,cfg)` (single
source of truth) used by BOTH `trend_pullback_block()` (v1) and new `trend_pullback_generate(sig,cfg)` (v2, returns
BUY/SELL to enter from `ts_adx_switch_trend` dominant direction). Wired into `bridge_main.py` + `backtest_replay.py`
right after the ML signal is picked: if signal==SKIP and generate fires → override to that entry (parity). Config
`trend_pullback_generate`=False / env `QGAI_PB_GEN`; `run_wfo.py --sweep-pb-gen` (mode="gen", reuses the harness);
bats `Run_PBGenSweep_AsOf_TEST/_FULL.bat`. Compile-clean; unit test of the gate correct (pullback→BUY, extended/top→None,
no-trend→None, off→None). **Smoke test (1 wk, window where baseline=+41.55%/13tr): GENERATE = +48.48%/11tr → BEATS
baseline** (opposite of v1 block which lost). Not a verdict (1 wk) — run the `--sweep-pb-gen` TEST then FULL to confirm
on total R over the year. DEFAULT OFF → live still baseline. Reversible: `trend_pullback_generate=False`.

**Fable-5 review of v2 (endorsed GENERATE as the correct pivot) + actions:** (1) Flaw to close — if a GEN entry
stops out mid-leg the late ML entry can still fire at the top (whipsaw + top-chase); fix = per-LEG lock (suppress ML
entry in that direction until the HTF trend flips), TODO after the first sweep shows promise. (2) Leakage watch — the
GEN trigger depends on `win_prob<threshold` i.e. the weekly retrain; the as-of leak-free WFO (per-week cutoff,
next-bar-open fill, last-closed ts_*) already handles this — spot-verify. (3) "Loosest combo won" is a luck flag
(likely just more exposure) → ADDED `worst_wk_r` (worst weekly fold) + `avg_r_trade` + a "MOST ROBUST" line to the
sweep summary/CSV; accept only a combo that beats baseline on total R AND holds worst-week + R/trade. (4) Choppy-regime
guard — the existing range-veto (`in_range_phase`) already gates GEN; an ADX floor is an easy add if the sweep shows
chop losses. Summary enhancement compiled clean.

**backtest_replay.py — ETA/timing added (house rule) + $10k/0.01-lot full-BT bats (2026-07-03).** Per the "every
long run prints timing" rule, the per-100-bar progress line now also shows elapsed min, est. min remaining, and finish
ETA HH:MM; and the report ends with `⏱ DONE — run time X min (N bars) | finished HH:MM:SS`. New bats
`backtest/Run_FullBT_HMM_10k_lot001_TEST.bat` (1 wk) + `_FULL` variant (`Run_FullBT_HMM_10k_lot001.bat`, 1 yr): current
corrected rel HMM, $10k equity, fixed 0.01 lot, live-faithful (htf trail + regime-TP + buf 0.15), one-folder-per-run
output = backtest_report.txt + backtest_signals_*.csv (every bar) + backtest_trades_*.csv (each trade + f_* features) +
backtest_summary_*.csv. NOTE: single-model IN-SAMPLE (OOS honest baseline stays the WFO wfo_asof_rel +393.7R). Verified:
1-wk TEST clean ($10k→$10,042, MaxDD 0.0%, timing lines + DONE mark print).

**AI DECISION SUMMARY box — dashboard, every bar (2026-07-03, Imtiyaz).** One always-visible box on the dashboard
(above the tab bar) that refreshes every 15-min bar with the model-transparency digest Imtiyaz asked for ("don't
just ask BUY/SELL — ask why/confidence/regime/risk/invalidation/past-similar"). Shows: signal + final win_prob vs
threshold, regime (HMM), the 4 model probs (Main/State/Direction/BigWin), a **5-model AGREEMENT score** (Main≥thr,
State≥thr, Dir≥thr, HMM-actionable, BigWin≥0.5 → X/5 → LOW/MEDIUM/HIGH/VERY-HIGH), expected $ move + suggested SL/TP
(from the move/MAE models), **"signals like this" history** (WR/PF/avgR/maxDD for the current prob-band, regime-specific
when >60%), why, and invalidation. Build: `engine/build_prob_buckets.py` → `logs/prob_bucket_stats.json` (WR/PF per
prob-band + regime from the full backtest — re-run after each fresh backtest); `bridge_dashboard.build_ai_summary()`
(read-only, fully try/except-guarded, never touches the live decision path) → adds `ai_summary` to `dashboard.json`;
`dashboard.html` `renderAISummary()` + `#ai_summary_box`. Fable-5 architecture (read-only, decoupled, snapshot pattern)
+ its metric guidance (per-regime buckets, grey-out on small n) followed. Compile/JS-syntax clean; sample injected from
the real last_signal renders correctly (SKIP/Ranging/1-of-5/LOW). Activates on next bridge write (restart to load).
UI iterated per Imtiyaz: grouped rounded bubbles (label-up/value-down), centered, big headings, per-model VOTES merged
into MODELS (prob + ✓/✗), full green/red color-coding (signal/prob/regime/WR/PF/avgR/votes), SKIP=yellow, title+invalidation
on one row. **MARKET INTELLIGENCE box added below it** (`bridge_dashboard.build_market_intel()` → `market_intel` in
dashboard.json; `dashboard.html` `renderMarketIntel()` + `#market_intel_box`, cyan theme) — CONTEXT groups TREND (M15/H1/H4
SMMA + HTF agree + line-dist), STRENGTH (H1/H4 ADX + DI), STRUCTURE (H4/H1 S/R + in-OB), FLOW (phase/imbalance/corr), CONTEXT
(vol/session/news). Deliberately NON-duplicative of the AI box (no signal/prob/HMM-regime/models/history). Needs `ts_trend_m15/h1/h4`
now also exposed in inference.py result dict. Both boxes refresh every 15-min bar (per new signal).

## 2026-07-02 — HMM v3 (flat≠Volatile fix, A/B), CSV output rules, system audit + fix tools
Worked on by Claude via Cowork (Divyesh). Full audit detail → `docs/AUDIT_2026-07-02/`.

**HMM v3 — "flat market reads Volatile" fix (A/B, WFO running):** v1 (+DI/−DI raw) and v2
(di_sum/clarity) both failed; v2 ALSO had a predict-path bug — PlusDI/MinusDI keys were never
passed at inference → silently 0 (train≠predict). v3: two variants behind env `QGAI_HMM_VARIANT`:
`spec` = [ADX, |DI_diff|, band_width_pct] (literal plan — fails own acceptance in sandbox) vs
`rel` = [ADX, di_eff(=inst. DX), band_rel(=band/trailing-30d mean)] (passes all: flat 07-02 window
18 Ranging/4 Trending/0 Volatile; train≈full distribution; Volatile=1.65× band_rel). Root causes
found: gold vol drift 2022→26 makes raw band % non-stationary (flat window = p88-92 globally but
p21-53 vs last 30d), and smoothed ADX/|DI_diff| stay high in post-trend chop. Code: `regen_adx_di.py`
+ `mt5_data_updater.py` + `fresh_reload.py` write band_width_pct/di_eff/band_rel per TF;
`hmm_model.py` v3 (pkl stores its own feature list → env-proof predict; missing-key warning);
`features.py`/`inference.py`/`train.py`/`self_learning.py` key-lists now driven from model.features
(kills the silent-zero class of bug; self_learning positional-column bug also fixed);
`verify_hmm_window.py` NEW acceptance script. Bats: `Run_HMM_AB_WFO.bat` (regen+freeze+launch both),
`Run_HMM_WFO_A_spec/B_rel.bat`, `Run_HMM_v3_Deploy.bat`. Regen ran clean (DI_diff parity Δ=0.000).
Gate: adopt winner ONLY if ≥ +483.1R. Bridge NOT restarted. (Bat gotcha fixed: `|`/`>=` inside
title/REM lines are parsed by cmd — pipes/redirects fired; all bats sanitized.)

**Output rules (Divyesh):** every backtest/WFO (bat OR direct python) also saves CSV results in the
SAME run folder — `run_wfo.py` → `_WFO_SUMMARY.csv`, `backtest_replay.py` → `backtest_summary*.csv`;
run documents live in that same folder too (one folder per run). Report format rule CHANGED same
evening: reports/analyses in **.md only** (replaces the morning's "all three formats" rule).
Documentation rule: all changes go into the 3 living docs (GUIDE / this CHANGELOG / TASKS) — no new
per-change documents unless explicitly asked.

**Independent system audit (docs/AUDIT_2026-07-02/):** verdict **D — Experimental (borderline C−)**,
readiness 41/100, leakage risk 38/100. Three key findings: (1) CONFIRMED intra-bar HTF lookahead —
M30/H1/H4 ADX-DI columns on the M15 grid embed full-bar (future) data; H4 drift vs honest partial-bar
mean 0.60 / max 2.02 ADX pts → all backtest/WFO numbers incl. +483.1R are upper bounds; (2) entry-ML
is not the edge — 89% of OOS profit is TPCAP exits; win_prob NOT calibrated (<50% bucket won 67.1%,
+113.7R); 10/42 features zero importance; TRAIL bucket value-destroying (peak +0.94R → exit −0.15R);
(3) live≠backtest — June 2026: WFO +48.1R/66.7% WR vs shadow −1.9R/29.4% WR (109 trades); entry
overlap only 8/66 (12%); live TRAIL 49% of exits vs 11% backtest; real live n=18: top-3 wins +$158.7k,
other 15 = −$21.5k, lots 0.89→15.58. **Fix tools shipped:** `engine/regen_adx_asof.py` (leak-free
as-of rebuild, validated err=0.0 vs brute force) + `backtest/Run_Fix1_AsOf_Regen.bat` (run AFTER A/B
WFO; new WFO after apply = new HONEST baseline, +483.1R retired); `engine/reconcile_shadow.py`
(weekly shadow-vs-backtest reconciliation, ±20% scaling gate); plan: prune dead features, retire
failed SELL move-model, rolling-OOS recalibration + threshold sweep, `--sweep-trails` on as-of data.
Master sequence → `docs/AUDIT_2026-07-02/SOLUTIONS_1_2_3_2026-07-02.md`.

**2026-07-03 — FIX-1 APPLIED + HMM v3 `rel` DEPLOYED.** A/B WFO (leak-world): spec +470.4R
degenerate REJECT; rel +481.7R ≈ baseline. Honest (as-of) A/B: legacy +407.6R vs rel +393.7R —
paired t=−0.69 = tie; rel maxDD 5.2R vs 7.0R (−26%), 0 negative weeks vs 2 → **Divyesh chose rel.**
Leak-inflation confirmed ~15-18% (483→408). `Run_HMM_v3_Deploy.bat`: models backup
(`_backup_pre_hmm_v3`) + as-of adx_merged applied (`.bak_preasof_20260703_104235`) + full retrain
(combined AUC 0.677 val / 0.669 test; SELL test 0.743) + **verify ALL CHECKS PASSED** (flat 07-02
window 18 Ranging/4 Trending/0 Volatile; stability 45/35/20 train≈full). `mt5_data_updater.py`
now writes as-of rows (updates stay leak-free). `run_wfo.py`: `_WFO_SUMMARY.csv` + per-week ⏱
ETA/countdown; `backtest_replay.py`: `backtest_summary*.csv`. Legacy variant (original 8-feat)
preserved in hmm_model.py behind `QGAI_HMM_VARIANT=legacy` (restored from engine_backup_0612).
**Bridge-start crash FIXED (2026-07-03 ~11:00):** first demo start crashed every bar —
`get_signal failed: Input X contains NaN` (GaussianMixture). Root cause: `bridge_main.get_live_adx()`
built live-appended ADX rows with ONLY {TF}_ADX+{TF}_DI_diff → the new HMM columns
(di_eff/band_rel/band_width_pct/PlusDI/MinusDI) were NaN on merged live rows. WORSE (pre-existing
live≠train drift): the old inline calc used UNSMOOTHED DX as "ADX" and last-CLOSED HTF bars —
neither matched training. Fix: get_live_adx now pulls ~5000 M15 bars and computes EVERY column via
`regen_adx_asof.asof_tf` (train==live by construction) + NaN row guard; `hmm_model.predict/
predict_batch` got a NaN neutral-fill guard (band_rel→1.0, else 0) so a feature gap can never kill
the trading loop again. Requires bridge restart to load.
**Direction-swap LOG bug FIXED (2026-07-03, flagged by Divyesh):** backtest evaluates BUY then
SELL per bar; `backtest_replay` logged `engine._last_features` = always the LAST call (SELL) — so
when BUY won the pick, the trade's f_* columns described the SELL evaluation (131/308 OOS BUY rows
had f_trade_direction=−1). **Decisions/probabilities were always correct** (each get_signal computes
its own features; online-learner path protected by the trade_type guard in on_trade_closed) — only
the LOGGED analysis columns were corrupted. Fix: per-direction feature cache in inference
(`_last_features_buy/_sell`) + backtest takes the winning direction's dict. ⚠ Any PAST analysis
built from backtest f_* columns of BUY trades is suspect. Re trade_direction importance 0.0:
training data was CORRECT (features recomputed per trade Type at train time); the 0 is redundancy —
direction-awareness lives in ts_htf_agreement (#2) + momentum_aligned_1hr (#4), which are
direction-SIGNED features. trade_direction stays a FIX-2 prune candidate.
**NEW HONEST BASELINE = wfo_asof_rel +393.7R.** Honest-data feature importances shifted
(hmm_state 0→0.0305 #6; only h4_trending_h1_aligned/trade_direction + direction-specific zeros
remain dead) → FIX-2 prune-list must be rebuilt from the new feature_importance.csv. Next: bridge
start on DEMO config → watch flat-hour states → FIX-2/FIX-3 per audit plan.

---

## 2026-07-01 — stuck-trade protect + graduated hedge, vSL-recovery/retry-loop bugs, backtest resume, mojibake, formatting
Worked on by Claude via Cowork. Full detail → `TASKS.md` DONE table (2026-07-01 rows) + `BUG_LOG.md`
(bugs N/O/Q/R + the earlier same-day entries). This is a summary index.

**Live-incident fixes (early in the day):** win_prob frozen 75+ min (`inference.py` OHLC-merge staleness
guard silently failing — now `log.error`s + a `_ohlc_stale_bars` counter); 10027 close-fail (AutoTrading
off) surfaced as a one-line `[ERROR]` only — led to the stuck-trade-protect feature below; mojibake console
output (`Start\*.bat` missing `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8` — added to all 5); dashboard.html
fixes (Imtiyaz's own edits: duplicate `sig_history_chart` canvas ID, missing MODEL confidence box);
win-prob/all-% displays standardized to 2 decimals (~35 spots across 8 files).

**Stuck-trade manual-protect (`bridge_session.py`, NEW):** `_close_position()` tracks consecutive
close-failures per ticket; past `stuck_close_fail_threshold` (3) escalates a repeating `🚨 STUCK` alert +
(if `stuck_trade_hedge_enabled=True`, enabled today) opens a FULL-lot protective hedge on a dedicated
`stuck_hedge_magic` (202698) — deliberately NOT L13's `manual_hedge_magic` (202699), whose cleanup sweep
would otherwise silently close it. Auto-unwinds once the original close succeeds.

**Bug N (open) — vSL-recovery fallback = hardcoded $15 guess:** Imtiyaz flagged leftover trade
#1519547791's vSL not matching the live H1 line. Traced to `recover_open_trades()`'s fallback (no comment
VSL/SL + no broker SL → hardcoded `sl_dist=15.0`) discarding the real trailed vSL on every restart. See
BUG_LOG.md #N for the full trace.

**Bug O (fixed) — close-retry-loop was broken:** found while investigating bug N. All 5 `_close_position()`
call sites in `bridge_core.py` did `del virtual_trades[ticket]` **unconditionally**, even on a FAILED
close — silently abandoning live monitoring after one failure (its own alert claimed "will keep retrying",
which was false). `_close_position()` now returns True/False; callers only delete on confirmed success —
threaded the trade's real `virtual_sl` through too (`_close_position(ticket, vsl=...)`).

**Graduated stuck-trade excess-hedge (Imtiyaz's idea, NEW, `leftover_excess_hedge_enabled=False` by
default):** `bridge_session._stuck_risk_hedge()` — stretch risk from `risk_pct` (3%) to
`leftover_risk_cap_pct` (6%) and hedge only the excess lot once real slippage (price past the trade's
actual vSL, via bug O's fix) exceeds the stretched budget, instead of an immediate full-lot freeze.
Not yet enabled or fire-tested.

**bridge_main.py mojibake — per-glyph, not blanket:** ~680 pre-existing corrupted log-message
glyphs found file-wide; a first blanket-fix pass was explicitly reverted per Imtiyaz ("only remove
[the one he flagged]"), then re-applied one glyph at a time as he pointed each one out: 💓⚙️──👁📋📊🚀💰✅—·.

**backtest_replay.py: checkpoint/resume + unbuffered-console fix, NEW:** `_checkpoint_pkl` existed in code
but was never read/written (dead) — a stopped run lost all progress. Now saves every 500 bars + on
Ctrl+C (config-signature-gated, `--no-resume` to force fresh), auto-deletes on success. Also fixed
`stdout`/`stderr` not being line-buffered (progress prints sat unflushed, long runs looked frozen) —
`line_buffering=True` + `flush=True` + 100-bar progress interval + `PYTHONUNBUFFERED=1` in
`Run_Live_Buffer_015_CSV*.bat`. ⚠️ Bash sandbox mount was stuck serving a 3+ hr stale cached copy this
session — could not `py_compile`-verify automatically, did a full manual line-by-line review instead.

**`Run_Live_Buffer_015_CSV.bat` (full 1-year, $10k/3% dynamic compounding) deep-parity-checked** against
live config (buffer 0.15%, TP-regime values, TP-equity-bypass avoidance, HTF SL/flip/forming auto-sync via
CFG import, entry-SL sizing, risk%, no-lookahead) before trusting it — all ✅. 1-week smoke test passed
first (`_TEST.bat`). Full run kicked off by Imtiyaz, in progress.

---

## 2026-06-29 — L13 MANUAL-TRADE MANAGER + L11 BACKFILL + signal-log + L8 fix + cent account
All reversible. Most live-config flags unchanged; new work is config-gated.

**L13 Manual-trade Manager (`engine/bridge_manual.py`, NEW) — final design (approach A, COMBINED vSL):**
- Treats ALL manual XAUUSD trades (magic 0; bot=202600) as ONE combined net position: sums net lots,
  takes the volume-weighted average entry, runs ONE ratcheting vSL for the whole group.
- **Risk = SEPARATE 3% pool** (`manual_risk_pct=3`, independent of the bot's `risk_pct=3` → 3%+3%=6%
  total, two budgets on the same equity). On first detect, sets a 3% broker SL on every leg; if combined
  lot > 3%-equivalent volume, HEDGES the excess (magic 202699).
- **ONE ratcheting vSL** up the 2-SMMA line (HTF/H1 per `ratchet_htf_sl`), one-way, capped at the 3%
  floor — trailed as a **VISIBLE broker SL on every leg** (logs 🔼). Breach (trend turns) → close ALL
  manual legs + hedges (🔻). **No flip-hedge** — the vSL handles reversal (FLIP_CLOSE hook in
  `bridge_core.py` left as comment only).
- **Target TP** (`manual_target_tp_pct=2%`) on combined avg → close ALL (🎯).
- Mixed-direction nets out; fully self-hedged (net 0) → no vSL. Also manages trades already open at start.
- **L8 isolation:** `manual_floating()` subtracts manual+hedge P&L from the bot's daily ratchet/TP.
- **DEMO (primary) only** — cent extension rejected (would clash with mirror-trading replication).
  Config: `manual_manager_enabled=True` (demo test), `manual_risk_pct=3` (separate pool), `manual_sl_pct=1`,
  `manual_target_tp_pct=2`, `manual_hedge_magic=202699`. Master switch reversible (set False to disable).
- ⚠️ `bridge_manual.py` hit mount-write null-byte corruption twice — stripped + re-verified both times
  (would crash import). If import errors / "null bytes" ever appear, re-strip the file.

**L11 startup gap-backfill (`bridge_main._overnight_replay`):** on start, logs any missing signal bars
(`mode=BACKFILL`) using a `_logged_bar_times()` set so the signal log is continuous after downtime.

**Signal-log overhaul:** `build_signal_log.py` merges full-history regime backtest (every bar + `$move`)
+ live `signals_all.csv` → `engine/logs/signals_complete.csv` (bat: `backtest/Run_BuildSignalLog.bat`).
`bridge_data.log_signal` got a dedupe guard (one row/bar+mode) + `equity` + `move` columns;
`write_outcome` now writes the real `$move = (exit−entry)·dir` and backfills offline-closed outcomes.
`dashboard.html` rebuilt to ONE date+time-sorted log (history cached + live 15s) with WIN/LOSS + $move.

**L8 false daily-SL halt FIXED (`bridge_session._net_balance_flow_today`):** was using local time → MT5
returned lifetime deposits as "today's flow" → bridge halted all day. Now broker-time filtered + 50%-of-
day-open safety guard + warn-once. Live-confirmed fixed.

**L8 COMPLETED (remaining 3 pieces, 2026-06-29):** (1) **lot-sizing flow-adjusted** — `bridge_core.execute`
now sizes off `equity − today's flow − manual_floating` (an intraday deposit/withdrawal or the manual leg
can no longer grow/shrink the bot's 3% lot). (2) **signal-log `trading_equity` column** —
`bridge_session.trading_equity()` = equity minus net external flow since a fixed anchor (2026-06-29);
written on every live/monitor signal (`log_signal(..., trading_equity=)`); pre-L8 CSVs auto-migrate via
`_ensure_teq_column` (trailing column, old rows blank). (3) **flow-event logging** —
`session.log_new_balance_ops()` (called each bar) announces each NEW deposit/withdrawal once → bridge log +
`logs/balance_flows.csv`. All three fall back safely (raw equity / no-op) on any MT5 error. Files touched:
`bridge_core.py`, `bridge_session.py`, `bridge_data.py`, `bridge_main.py` (0 null bytes; bash py_compile
shows false last-line errors = mount truncation, Read-tool verified complete). DEMO-verify next.

**Accounts (`config_mt5.py`):** added cent-live `29453256` (VantageMarkets-Live 21, `XAUUSD.pc`,
secondary), disabled TradeQuo `125926628`. VantageDemo `25334572` stays PRIMARY. Backup
`config_mt5.py.bak_20260629`. ⚠️ holds real passwords — never commit/expose.

**Bug A + Bug F — verified ALREADY DONE (docs were stale):** (A) secondaries are flattened on every daily-SL/
TP halt path (`bridge_main:360-365`, `bridge_core:369-372/377-380`), transition-guarded. (F) `backtest_replay`
defaults `TRAIL_MODE` to the live config (`htf` if `ratchet_htf_sl` else `line`, line 243-249) + Bug J entry-SL
+ H1 flip. No code change — just ticked off in TASKS L4.

**L7b (partial) — dead `bridge_risk` code REMOVED:** dep-traced that every live `VirtualTrade` is `ratchet=True`
(a non-ratchet trade is skipped at `execute()`), so the non-ratchet path was unreachable. Removed `_update_buy`,
`_update_sell`, `_smart_exit_check`; `update()` now always routes to `_update_ratchet`; trimmed the now-unused
PBE/BE/SMART_EXIT imports. `__init__` + `status()` fields kept (dashboard uses them). Compile-OK; mount-write
null-byte corruption hit the file (5661 nulls) → stripped + re-verified (0 nulls, would otherwise crash import).
**Feature removal — `ts_line_dist_pct` dropped from the model (Anisa, explicit request):** investigation of
`BASELINE_trades_tp_1.00.csv` (1303 trades) showed entry distance-from-line is the strongest outcome signal
(near-line +0.392R/50% win vs far/chasing +0.034R/43%) — this is the mechanism behind the "system enters at
the bottom" observation (late/chasing entries barely break even). A distance-from-line ENTRY FILTER tested
in-sample lifted PF 1.74→2.25 (≤0.40% cutoff), but Anisa declined the filter AND the feature. `ts_line_dist_pct`
(rank #2, imp 0.0484) was added to `_MANUAL_PRUNE` (features.py) → excluded from all model feature sets
(main + ranging/trending/volatile). ⚠️ **Requires `3_Train_Models.bat` retrain before next bridge restart**
(live .pkl=44 feat vs code=43 → mismatch). Flagged that it's a top feature (removal likely lowers PF/AUC);
recommend a post-retrain WFO. REVERT: delete the `_MANUAL_PRUNE` line.

**L7b ATR — REMAINING cleanup done (2026-06-29, bot stopped):** with the bot stopped, removed the last
ATR vestiges: `bridge_main` atr20_pct/atr20/tr compute deleted; `inference.py` vol_regime → constant
"normal" (was ATR-derived, display-only) + atr14/atr20_pct result-dict keys removed + move-model
normalization → fixed 0.2; `train_move_model.py` atr_usd → fixed 0.2 (matches inference; atr20_pct was
always the 0.2 default, so net-identical — no retrain needed). ADX-internal `atr14` (Wilder TR for ADX/DI)
KEPT (real indicator math). SQLite/CSV `atr20_pct` column LEFT nullable (logs 0) — dropping = DB migration
+ dashboard-parity risk, not worth it. inference+bridge_main hit mount null-corruption (82+327 nulls) →
stripped + COMPILE_OK. Bot safe to restart (behavior-neutral).

**L7b ATR — SAFE SUBSET removed (live-neutral):** ATR confirmed fully vestigial (out of FEATURE_COLS since
06-19; reads use default constants; `execute()`'s `atr20_pct` param unused; `vol_regime` informational-only).
Removed the `📐 Live ATR20` per-bar log + `result["atr20_pct"]` threading (`bridge_main`) and the unused
`atr20_pct` param from `execute()`/`handle_opposite_signal()` (`bridge_core`). 0 nulls, Read-verified.
Deferred (need bot stopped): SQLite `atr20_pct` column (kept nullable → logs 0, no live migration), the
`inference.py vol_regime` constant, the `df["atr20_pct"]` compute, and `train_move_model.py atr_usd`.

---

## 2026-06-27 — REPO REORGANISATION (docs + backtest tidy-up; nothing deleted)
Big housekeeping pass — files were scattered across root / `engine/` / `bug_review/` / `engine/docs/`.
All MOVES, nothing deleted; everything is reversible.

**Docs → one folder `docs/`:**
- Active docs now in `docs/`: `QGAI_GUIDE.md` (master hub), `WORKING_NOTES.md`, `TASKS.md`, `STRATEGY.md`,
  `RULEBOOK.md`, `SYSTEM_OVERVIEW.md`, `FEATURES.md`, `BUG_LOG.md`, `FIXES_CHANGELOG4.md` (this file).
- Old docs → `docs/archive/`: SESSION_NOTES, BACKTEST_SUMMARY, the two *2026-06-22 reviews, CHANGELOG 1-3,
  GPT guides, and 5 old engine/docs txt (README_INSTALL, THIRD_PARTY_REVIEW, bug_audit ×2, buf0.06_current).
- `CLAUDE.md` STAYS at repo root (auto-loaded memory) and now points to `docs/`. Cross-references in
  `CLAUDE.md` + `QGAI_GUIDE.md` updated to the new paths. No code/bat references docs → nothing broke.
- Empty `bug_review/` dir + `engine/docs/` (2 live logs left) couldn't be rmdir'd via the mount — delete the
  empty `bug_review/` in Explorer if desired.

**Backtest tidy-up (`backtest/`):**
- New `backtest/README.md` = bilingual INDEX of all bats + results map.
- 31 bats → 14 ACTIVE (kept) + 17 superseded → `backtest/_archive_bats/` (trail variants, ablation,
  fixes A/B, all-backtests, reset — those ideas are done).
- `engine/` cleaned of 21 stray backtest outputs (`results_tp_*.txt` ×11, `trades_tp_*.csv` ×10,
  TP_SWEEP_SUMMARY) → `backtest/results/_archive/engine_tp_outputs/`.
- 15 old result folders (sweep_*, wfo_results_*, ablate, trail_compare, _OLD_GARBAGE…) → `results/_archive/old_runs/`;
  loose result txt → `results/_archive/loose_txt/`. Active result folders untouched (backtests, wfo_results,
  report, replay_logs, baseline).
- 6 one-off research .py LEFT in `engine/` (they import engine modules; would break if moved) — documented in README.

**New layout:** `CLAUDE.md` (root) · `docs/` (all docs) · `backtest/` (bats + README + results) · `engine/` (live code).

---

## 2026-06-26 — Regime-adaptive TP + CLOSED-LOOP RELABEL (train=backtest=live)

### A. REGIME-ADAPTIVE TP cap (backtest, config-gated, default OFF)
- 13-TP sweep (`backtest/results/backtests/tp_*`) showed each HMM regime wants a different TP cap.
  `backtest_replay.py`: new `--tp-regime` flag + `_TP_BY_REGIME` map (Ranging 2.0 / Trending 1.0 /
  Volatile 0.8), switched on the trade's HMM state at entry. Reversible (omit the flag = old behaviour).
- Bats: `Run_TP_Regime_TEST.bat` (smoke) + `Run_TP_Regime.bat` (full) + `Run_Backtest_FullHistory.bat`
  (2022→2026 total dataset, global vs adaptive). Full 9-mo A/B: **regime-adaptive WON** — Total R
  257.7→**310.2 (+20%)**, PF 2.52→2.56, avg R 0.384→0.436, DD 1.7→2.0% (Ranging the driver +34R).
- ⚠️ IN-SAMPLE. NOT in the live bridge yet — gated on WFO OOS + full-history checks first.

### B. 🔥 CLOSED-LOOP RELABEL — model now trains on LIVE-EXIT labels (Imtiyaz's concern, fixed)
- **Problem:** the win-prob model trained on `Back_testing_data_final_cleaned.xlsx`, whose Win/Loss
  came from an OLD external backtest's exit — NOT the live exit (ratchet + HTF H1 SL/flip + TP cap).
  So the model predicted "win" for the WRONG exit definition.
- **Fix:** `engine/relabel_trades.py` (+ `backtest/Run_Relabel_Trades.bat`) replays every entry through
  the live HTF exit engine (reuses `analyze_capture.py` line/flip construction), leakage-safe (each trade
  forward-simulated on its own future bars only). Recomputes Win/R/$Move/exit + adds R + exit_reason cols.
- **Result:** 2,743/2,788 relabeled (45 unmatched at data edges). **744 labels CHANGED (27.1%)** even
  though aggregate WR is coincidentally identical (37.7%→37.7%) → the model HAD ~27% labels disagreeing
  with live. Exit mix FLIP 1050 / TRAIL 679 / TP 543 / SL 471. Output:
  `data/Back_testing_data_final_cleaned_RELABELED.xlsx`.
- **`config.py trades_file` switched to the RELABELED file** (reversible — comment holds old name).
  NEXT: `3_Train_Models.bat` retrain → WFO-validate vs PF 1.55 → keep only if equal/better.

---

## 2026-06-23 (evening) — Signal Log, Virtual Ledger, CAPTURE leak + two fixes
Big session. Dashboard signal-log overhaul, a virtual paper-trade ledger surfaced, and a
data-driven hunt for WHY the system misses clean trend moves → two reversible fixes.

### A. DASHBOARD — Signal Log (live, on the dashboard, works even when bridge is OFF)
- **`signals.html`** (new) — standalone Signal Log viewer; reads `logs/signals_all.csv` directly,
  so it shows even when the trading bridge is stopped. Filters (All / BUY-SELL), 15s refresh.
- **`dashboard.html`** — inline **📋 SIGNAL LOG** panel placed **below ▸ RISK & SESSION** (COL 3),
  styled like the old 🌙 panel (Trending/Ranging/Volatile HMM badge + replay-row look) + filter
  buttons (All / BUY-SELL / ↻). CSV-based. Columns shown: Time · Signal · **Price** · Win% ·
  Regime · **H4 RANGE** · **BW%** (big-win prob) · **lot** · **WIN/LOSS** (real outcome) ·
  **virtual WIN/LOSS+R** (from shadow ledger, dashed badge = paper) · **equity** (at signal time).
- Old duplicate 🌙 Signal Log widget removed; 📈 CHART + 📒 LEDGER tabs added.
- Label clarity: orange **"H4 RANGE"** (H4 in_range_phase flag) vs HMM **"Ranging"** regime —
  were confusing; now distinct + tooltips. (H4 RANGE = 4-h move <0.5%; HMM = 15-min state.)

### B. DEDUPE + EQUITY in the signal log
- **Bug: same M15 bar logged 2-3×** in signals_all.csv. Cause: no dedupe + a range-block
  double-log. Fix: `bridge_data.log_signal` now writes **one row per (bar_time, mode)**
  (module guard `_last_sig_key`); `bridge_main` range-block path `else`→`elif not _range_block`.
  Cleaned 44 existing dup rows (backup `.bak_20260623`).
- **`equity` column added** to log_signal (CSV) — account equity **at signal-generation time**,
  logged for EVERY signal (executed or not). All 6 call sites pass `equity=_cur_equity`
  (`_acct.equity` captured each bar). Existing CSV migrated (`.bak_eq_20260623`).
- `serve.py` chart_data.json write wrapped in try/except (silences harmless WinError 10053).

### C. VIRTUAL TRADE LEDGER (shadow) — see all trades, real OR monitor, even when off
- System already had `shadow_ledger.py` (simulates every BUY/SELL signal forward with the live
  exit rules → R, $, exit-reason, real_executed). It had not run since 06-19 → regenerated
  (712 paper trades). **`shadow.html`** (new) — the Virtual Trade Ledger viewer the
  `6_Shadow_Ledger.bat` referenced but which never existed: entry/exit, why-exit, R, $, %,
  WIN/LOSS, **REAL/VIRT** tag, summary stats + filters. **📒 LEDGER** tab added to dashboard.
- Signal-log panel **merges** the shadow outcome → BUY/SELL show virtual WIN/LOSS even in MONITOR.
- **`scheduler.py`**: auto-refresh shadow ledger **every 15 min** (`_shadow_sec`) so the virtual
  log stays current without manual runs.

### D. 🔥 CAPTURE LEAK found — "Captured Move / Available Move" (Anisa's framing)
- New metric: `engine/analyze_capture.py` + `backtest/Run_Capture_Analysis.bat`. Re-simulates
  real signals under 4 exit rules. Also added a **Captured/Available** line to the
  backtest_replay **report**.
- **Finding:** 18-23 Jun = 318-pt downtrend available, system **captured −61 pts (−19%)** —
  14/18 trades exited via **FLIP at ~−8 pts each = M15-line whipsaw**.
- Variant test (738 signals): **HTF H1-flip = 2× captured move, +33% total R** (+223→+297R).
  The M15 flip whipsaw is the leak; HTF (H1 line, farther) rides the trend. (This is the HTF
  exit we built then reverted on 06-23 afternoon — data says re-enable.) flip-confirm = runner-up.

### E. 🔥 ENTRY fix — COUNTER-TREND-FADE block (Anisa's "dominant-TF" insight)
- Tested entry filters 5 ways; only this works: block a trade **against the DOMINANT timeframe
  momentum** (H1 or H4 — **whichever ADX is higher**) **when that dominant ADX slope is FALLING**
  (trend real but fading = whipsaw zone). In-sample (1303 trades): **+15R, PF 1.74→1.89**;
  blocked group = net-loser (PF 0.67). Counter-trend in a RISING trend is fine (kept).
- Implemented config-gated (default OFF): `config.skip_counter_trend_fade`;
  `inference.py` now exposes H1/H4 ADX/DI/slope in the result dict; filter in
  `backtest_replay.py` (`--ctf-fade` CLI) and `bridge_main.py`. Lookahead-free.

### F. BACKTEST INFRASTRUCTURE
- `backtest_replay.py`: `backtest_signals*.csv` now has **`blocked_by`** (range/ctf_fade) +
  H1/H4 ADX/DI/slope → audit which signals were blocked and why. Trades CSV already carries
  entry/exit/why (reason+exit_reason)/price_move + full 55 `f_*` features for research.
- `backtest/Run_Backtest_Fixes.bat` (+ `_TEST`): A/B **baseline / +CTF / +HTF / +BOTH**,
  **0.01 fixed lot**, **resumable** (skips runs with an existing report). New backtests save
  **separately** under `backtest\results\backtests\` (WFO stays in `backtest\results\wfo_*`).
- TEST (26 May–12 Jun) PASSED, no errors: BOTH best (PF 4.58 vs 3.84). Full 9-mo run pending.

### ✅ ENABLED (2026-06-23 evening) after full backtest confirmed BOTH best:
Full 9-mo backtest (0.01 lot, real engine): BOTH = PF **2.29→2.52**, WR 53→**55.5%**, Total R
+252→**+258**, MaxDD 4.2→**3.6%**. CTF is the main driver; HTF adds lower DD on top. (TP=1.00 caps
the HTF "trend-ride" gain, so Total R rise is modest +2.4% — but quality/DD clearly better.)
Set in `config.py`: `ratchet_htf_sl=True`, `ratchet_htf_flip=True`, `skip_counter_trend_fade=True`.
All reversible (set False). ⚠️ In-sample → watch the live/demo equity curve closely; revert if it
behaves worse than backtest. Restart `1_Start_Trading.bat` (+ `5_Dashboard.bat`) to load.

---

## 2026-06-23 (afternoon) — TP=1.00 revert + RANGE-PHASE filter (data-driven)
Data showed the OLD **TP=1.00 + partial/BE** config was the best result (backtest_replay real
model: +287R / PF 1.74; TPCAP is the profit engine = +352R, 100% win). Far-TP we switched to
earlier actually CUT profit (winners went to FLIP/TRAIL ≈ $0 instead of the 1% TP). So reverted:
- **config.py:** `ratchet_tp_cap_pct` 10.0 → **1.00** (TP at 1%); `ratchet_htf_sl` True → **False**;
  `ratchet_htf_flip` True → **False** (M15 ratchet, matches trades_tp_1.00). Reversible (comments hold old values).
- **🔥 RANGE-PHASE ENTRY FILTER (new, strongest lever):** `skip_range_phase_entry = True` +
  `range_phase_min_prob`. Skips entries when H4 in_range_phase==1 (chop). Data: range trades net
  −43R / PF 0.76 vs trend PF 2.62; skipping → PF **1.74→2.62**, +43R, +$1,283 move. Trend-following
  whipsaws in ranges. in_range_phase is lookahead-free (last completed H4 bar). Implemented in
  config.py + backtest_replay.py (entry gate) + bridge_main.py (skip + "⏭ SKIP (range-phase)" log).
- **`price_move` column** added to backtest trade CSV = (exit−entry)×dir = actual $ gold move captured;
  report shows "Price move ($): Total | avg". Baseline file: backtest/results/baseline/BASELINE_trades_tp_1.00.csv.
- **serve.py:** wrapped chart_data.json write in try/except (ConnectionAborted/Reset/BrokenPipe) —
  silences harmless WinError 10053 when the browser refreshes mid-response.
- Retrained → 44 features (volume removed), AUC Main 0.7594/0.7470, BUY 0.80, SELL 0.75 — healthy.
- **Data-driven "chasing" pattern found:** losers concentrate in range-phase (in_range 0.52 vs 0.30),
  high M15_ADX (≥45 PF 1.21 vs <25 PF 2.52), and FAR from the 2-SMMA line (PF 1.14 vs CLOSE 2.96).
  Same lesson: late/extended entry = bad; early/clean trend entry = good (PF up to 5.5). M15_ADX and
  ts_line_dist_pct are TOP features — USE them as filters, do NOT remove. (See STRATEGY.md.)

## EXIT LOGIC (config.py + bridge_core/ratchet/risk)
- **HTF H1 exit (NEW, LIVE ON)** — `ratchet_htf_sl=True`, `ratchet_htf_flip=True`, `ratchet_htf_tf="H1"`.
  Problem: 15-min SMMA(2) line sat near entry → SL cut by 15-min noise → 3× re-entry whipsaw
  even when 4h/1h/30m all agreed. Fix: SL + flip now ride the **H1 line** (farther). Entry
  stays 15-min; lot auto-shrinks so 1R still = `risk_pct`% equity. `get_htf_state()` added in
  bridge_ratchet (reuses compute_trend on H1/M30/H4 bars). `ratchet_htf_max_risk_pct=2.5`
  (if H1 line is farther than this, fall back to the 15-min line).
  Backtest (H1, no-TP, $0.30 cost, aligned): +61.7R, PF 1.17, $10k→$33k vs M15 ~breakeven.
- **Buffer 0.09% → 0.20%** (`ratchet_buf_pct`) — buffer-sweep: same profit ($33k) but max DD
  61%→55%, PF 1.18. SL = H1 line ∓ (price × 0.20%).
- **TP set far** (`ratchet_tp_cap_pct=10`, ~no TP) — flip is the exit. h1_tp_sweep: tight 1R TP = PF 1.00
  (kills edge); far/none = PF 1.21. `tp_equity_pct=0` (price-based TP path).
- **Min SL** fixed $8 → `ratchet_sl_min_pct=0.18%`; **breakeven buf** $2 → `breakeven_buf_pct=0.05%` (%-of-price).

## RISK / DAILY (bridge_session.py + backtest_replay.py)
- **Daily RATCHET rule (NEW)** — replaced fixed −9% daily SL with a trailing floor:
  floor = day-peak-equity − 9%. Loss-cap −9% at open; as profit grows the floor trails up
  (peak +9% → break-even, peak +12% → +3% locked). State: `day_peak_equity` (init/reset/preload).
  $10k-sim: at 2% risk RATCHET beat fixed (+1,589% vs +1,461%, DD 22%).
- **Trade-2 Equity SL — REMOVED COMPLETELY** (not disabled) from bridge_core, bridge_session,
  bridge_dashboard, bridge_constants. It halted the whole day at −3%, conflicting with the
  9% daily SL. Now clean: per-trade 3% (vSL=1R) + daily 9% only. (grep-verified, no leftovers.)

## ML / FEATURES (features.py + train.py + xgb_model.py)
- **ATR removed** — `atr14_pct` / `atr20_pct` no longer computed or in any feature list.
  2-SMMA already captures volatility (redundant + lagging). ADX's internal True-Range untouched
  (ADX uses the standard Wilder formula, computes its own TR).
- **slot_win_rate fixed** — (1) was 15-min slots (96, ~29 trades each, noisy) → now **1-hour**
  (24 slots, ~116 each); (2) **look-ahead leakage FIXED** — slot table now built on the
  train-split only (was full data → past trades saw future outcomes).
- **Volume removed entirely (2026-06-23, like ATR).** vol_spike was already pruned; `volume` (imp 0.02)
  added to _MANUAL_PRUNE. Data showed volume is not a useful lever (entry + exit filters both failed,
  every rolling version hurt) — SL-hunting noise the model barely used. Model now has ZERO volume
  dependency. Retrain to apply; AUC expected unchanged. Reversible (remove "volume" from _MANUAL_PRUNE).
- **Ablation toggle added** (features.py): env `QGAI_ABLATE="f1,f2"` drops extra features for one test
  WFO without touching committed lists. Bats: Run_Ablate_TEST/FULL.bat (default removes H1-alignment).
- **23 features pruned** (67→45) — 13 zero-importance + 10 manual, data-backed via
  `feature_importance.csv` (now dumped each retrain by xgb_model.evaluate). Kept: hmm_state
  (regime selector), trade_direction, M30 ADX/DI (cross-model useful). AUC unchanged → safe.
- Prune sets `_ZERO_IMP` / `_MANUAL_PRUNE` in features.py (delete a name to restore).

## VALIDATION (backtest/ + run_wfo.py)
- **Walk-forward OOS (true): PF 1.55, avgR +0.139, 33/40 green weeks (82%), 9/10 green months.**
  Weekly retrain on past only, trade next week unseen. Edge is REAL (survives OOS) — the
  +279,000% backtest headline is compounding fantasy; judge by PF.
- In-sample vs OOS on real ML trades: PF 1.74 vs 1.68 — small drop = not overfit.
- **TRAIL finding** — exit-mix: FLIP carries profit (+148R); TRAIL net-negative (−7R, win 32%).
  By regime: Ranging −0.10 / Trending −0.05 (trail hurts) ; Volatile +0.05 (trail helps).
- **`--trail-mode` flag added** to backtest_replay + run_wfo: `line` (current) / `off` /
  `after1r` / `be` / `htf` / `regime`. Each has a `Run_WFO_*.bat` → separate results folder,
  resumable, comparable. Trail-variant WFOs ran 06-21 (wfo_results_after1r/be/fliponly/regime).

## ENVIRONMENT
- Python 3.12.10 + MetaTrader5, pandas, scipy, scikit-learn, xgboost, lightgbm, catboost,
  hmmlearn, river, joblib, openpyxl. (Dropped Python 3.14 — hmmlearn needed C++ build tools.)
- `.bat` launchers (Start/ + backtest/) use the full Python path since PATH isn't set.

## ⚠️ MUST REMEMBER — Stage 2 TP
When running the WINNER's realistic WFO (Stage 2, real 3%-equity volume sizing):
use **FAR TP** (`--tp-equity 0`, price-cap far) — NOT `--tp-equity 3`. Reason:
equity-TP% ÷ risk% = R-multiple, so equity-TP 3% with 3% risk = exactly **1R**
(tight TP) which kills the edge AND mismatches live (live has tp_equity_pct=0,
ratchet_tp_cap_pct=10 = far). Stage 1 sweep uses fixed-lot 0.01 so equity-TP 3%
rarely fires (≈ far, fine for the trail comparison) — the trap is only Stage 2.

## PENDING (next steps)
1. Run trail-variant WFOs (Stage 1, fixed-lot, clean R) → pick best trail mode → Stage 2 (winner, real 3% volume, FAR TP) → implement live.
2. Populate `MT5_PRIMARIES` (3 accounts) in config_mt5.py → activate failover (code wired, list empty).
3. Bug C — set live SYMBOL from the connected primary (matters once failover is on).
4. Restart bridge on DEMO, forward-test 3–7 days, then live.

## NOTE
- config_mt5.py (real passwords) is gitignored / untracked — keep it that way.
- The bash file-mount in Cowork serves stale copies intermittently; all edits were verified via
  the ground-truth file reader (a known artifact, not a code bug).
