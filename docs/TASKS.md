# QGAI — Tasks (priority order)

---

## 🔴 TOP PRIORITY — Exit Improvement (Fable-5 opinion, 2026-07-17)

**Problem:** system reaches 1,103R peak profit over 1 year but captures only 339R (30.7%
MFE-capture). 70% of peak profit is given back before exit. TRAIL exits are the worst
offender: avg peak +0.92R but exit at -0.25R = 1.17R giveback per trade (-37.3R total).

**EXIT01 + EXIT01b DONE (2026-07-17):** TP cap audit (1-year, 220 TPCAP trades: +28R left
on table but dependent on 3 trades — big-winner test FAIL) + skip-move analysis (80% time
in-trade, skip is not the problem). EXIT02 (partial-exit-at-cap) NOT recommended by Fable-5.

### Step 1 — Peak-Ratchet Profit Lock ⏳ (highest impact, +15 to +30R/yr)
When trade reaches peak ≥ trigger_R, lock a virtual floor at floor_R so profit can never
fall below that level. Example: peak hits 1.0R → floor locks at 0.4R minimum.
68 trades in OOS1Y reached 1R+ peak but exited below 0.4R → gross ~+36R recovery.
**A/B test:** 9 arms — trigger {0.8, 1.0, 1.2} × floor {0.2, 0.4, 0.6}.
Implement in `backtest_replay.py` (config-gated), build TEST + FULL bat files.
Runner ID: `EXIT03` (in `backtest/_runners/exit_workstream/`).

### Step 2 — Two-Speed Trail (after Step 1 measured, +5 to +15R/yr)
Peak < threshold → keep H1 2-SMMA trail (current). Peak ≥ threshold → switch to tighter
trail (M30 SMMA or tighter H1 offset). TRAIL bucket = -37.3R, break-even alone = +37R.
Blocked on Step 1 result (overlap — same 29 trades).

### Step 3 — MFE-Capture Metric Adoption
Replace bar-range-sum capture% (5%, misleading denominator) with MFE-capture (30.7%).
Target: 34-36%. No code change needed — metric/reporting only.

---

### DONE — 2026-07-17 Wilder ADX removed everywhere, replaced with EMA ADX(14)
Imtiyaz flagged "you use wilder adx for all calculation it wong." Investigation found
`adx_merged.csv` (`M15/H1/H4_ADX`, `*_DI_diff`) was always EMA-based — the bug was isolated
to `h4_adx_roll`/`h1_adx_roll`/`h4_adx_slope`/`h1_adx_slope`/`ts_adx_switch_trend`
(`features.py:_wilder_adx()`). Ground truth confirmed via the live EA's actual `iADX()` call
(not `iADXWilder()`). Fixed in `features.py`, `fresh_reload.py` (also fixed a hidden landmine —
false docstring claim of EMA parity), and both `research_smma_adx_*.py` scripts (git commit
`e1ce9fc`). `indicators_merged.csv` regenerated + verified, model retrained
(2026-07-17T20:15:55, sane feature importances). Per Imtiyaz's explicit "start from first, full
enterprise migration" request: full backup (`C:\QGAI_BACKUPS\PRE_EMA_ADX_MIGRATION_20260717_203557`),
read-only Wilder-era archive with SHA-256 hashes on 10,965 files
(`C:\QGAI_ARCHIVE\ADX_WILDER\WILDER-REG-001`), new categorized project scaffold
(`C:\QGAI_EMA_ADX`), full audit + migration report (`C:\QGAI_MIGRATION\`). Detail:
`docs/BUG_LOG.md` §S, `docs/FIXES_CHANGELOG4.md` 2026-07-17.
**Remaining:** MT5 live-terminal ADX parity confirmation (toolkit built at
`C:\QGAI_EMA_ADX\11_runners\EADX-002_RUN_MT5ParityTest_Step1_PythonExport.bat`, needs Imtiyaz
to run the `.mq5` half), fresh 3-month OOS backtest on the retrained model + `BACKTEST_RESULT_AUDIT.md`
pass before any keep/drop decision.

---

### âœ… DONE â€” 2026-07-17 Manual-trade risk: CUT-based protection (v2)
Imtiyaz changed approach from hedge-based (v1, same day) to CUT-based: excess
manual lot is partial-closed DIRECTLY from the manual positions (largest first),
no opposite-side hedge orders. `bridge_manual.py`: removed `_manage_hedge()`,
new `_enforce_risk_cap()` + `_cleanup_stale_hedges()`. `manual_floating()` now
only sums magic=0. Config RESTORED: `risk_pct`/`manual_risk_pct`/
`manual_copy_max_risk_pct` = **3.0**, `daily_loss_limit_pct` = **9.0**.
`py_compile` clean. Full detail:
`docs/FILTERS_MASTER.md` CHANGE LOG + `docs/FIXES_CHANGELOG4.md` (2026-07-17).
**ACTION REQUIRED: restart live bridge to load this change.**

### DONE - 2026-07-16 LIVE SAFETY FIX: manual vSL enforcement
Manual BUY had dashboard vSL `4022.08`, but bridge heartbeat later showed price `4016.61` and no close fired. Root cause: `bridge_manual.py` enforced vSL only when a fresh ratchet line was available; if line read failed, the previously displayed vSL was not checked. Fixed by enforcing previous stored vSL every tick before recalculating the fresh line. Also changed `bridge_main.py` so manual-manager errors are logged instead of silently ignored. Compile check passed.

**ACTION REQUIRED:** restart live bridge to load this fix. Full notice: `docs/LIVE_SAFETY_NOTICE_2026-07-16_MANUAL_VSL.md`.

### âœ… DONE â€” 2026-07-16 (Signal History "moves to bottom on refresh" fix)
Root cause: `_gsResponsiveColumns()` (`dashboard.html` ~line 4676)
switches GridStack's column count based on viewport width and compacts
the whole grid, but its init-time call had no re-pin afterward â€” on any
page load under ~1200px effective CSS viewport width (common with
125%/150% Windows display scaling on normal laptop monitors), the column
switch fired with nothing re-asserting Signal History's position below
Signal/Signal Log. Fixed by re-running the fit+pin sequence inside
`_gsResponsiveColumns()` itself whenever it changes columns, plus a
belt-and-braces re-pin after the init-time call. Verified live via
`serve.py` + real bridge data in the browser preview: forced a 1100px
viewport (confirmed the column switch actually fires), confirmed correct
positioning before/after, no console errors, screenshot matches the
reported desired layout. Detail: `FIXES_CHANGELOG4.md` 2026-07-16.
**Browser hard-refresh only â€” no bridge restart needed.**

### âœ… DONE â€” 2026-07-16 (FS67-13 OOS1Y result + live feature drop) â€” Imtiyaz approved
FS67-13 result: 4 of 6 `DROP_CANDIDATE` features (from FS67-02's 3-month
screen) FLIPPED to `CORE_KEEP` on the OOS1Y window (`ts_bars_since_flip`,
`M15_DI_diff`, `slot_cos`, `mins_to_next_3star` â€” none dropped). Only
`15_min_slot` and `M15_ADX` stayed `DROP_CANDIDATE` on both windows.
**Dropped both from live** â€” `features.py` `_MANUAL_PRUNE` updated,
`FEATURE_COLS` 27â†’25, verified via direct interpreter check, `py_compile`
clean. Detail + full 6-feature R comparison: `FIXES_CHANGELOG4.md` +
`FILTERS_MASTER.md` Â§CHANGE LOG (both 2026-07-16).

**âš ï¸ NEXT â€” RETRAIN REQUIRED:** run `Start/3_Train_Models.bat` â€” the live
`.pkl` still expects both dropped columns until retrained; the bot will
mismatch on inference otherwise.

**ðŸŸ  PENDING â€” parallel WFO due-diligence:** new runner
`backtest/_runners/feature_sweep_67/FS67-22_RUN_15minSlot_M15ADX_WFO6M.bat`
(2 arms: with-features vs. live-dropped, same 6-month window as
`FS67-21`) â€” **DONE 2026-07-16.** Result (26 weeks, 484/486 trades, full
post-backtest audit in chat): Arm A (with features) +90.8R vs Arm B
(live, dropped) +75.6R â€” **features OUT cost ~15.2R (-16.7%) over 6
months on this WFO**, contradicting the FS67-02/FS67-13 DROP verdict
above. Arm A cross-checked byte-for-byte identical, week-by-week, to the
registry's separate `wfo_current_live_28feat_20260714` baseline (that
baseline pre-dates the 2026-07-16 prune, so it still had both features
in) â€” confirms Arm A's +90.8R is reproducible/real, not a harness
fluke, which makes the contradiction with the static-split screens more
real, not less. Delta concentrated in BUY side (SELL nearly identical
between arms) and in Ranging/Trending regimes (Volatile ~unaffected).
**Root cause traced 2026-07-17 (Fable-5):** confirmed real conflict, not
a stale-window effect (FS67-13's own H2-only slice still says DROP:
+5.9R/+6.8R per feature). Found 3 confounded config differences between
FS67-13 (static sweep) and FS67-22 (WFO): `--skip-counter-trend`
(WFO-only), spread ($0.20 WFO vs $0.13 sweep default), joint-drop (WFO)
vs individual-ablate (FS67-13). Also: both deltas are statistically
weak (FS67-22 weekly paired t=1.36, p≈0.19; FS67-13's effect is only
~1.9% of its 338.5R baseline) â€” likely noise on both sides, not a real
edge either way.

**✅ DONE — FS67-23 isolation run (2026-07-17):** Baseline (with features)
+103.6R / 512 trades vs candidate (live, dropped) +82.9R / 475 trades →
**delta -20.7R, same direction as FS67-22**. Confirms retrain frequency is
NOT the cause — the joint-drop interaction effect is. Post-backtest Tier A+B
audit completed.
**⚠️ Imtiyaz decision (2026-07-17): revert NAHI — પહેલાં family group test
કરો, noise ઘટાડવા test-first approach. 15_min_slot + M15_ADX live માં
dropped રહેશે જ્યાં સુધી group test result ના આવે.**

**✅ DONE — Pipeline flaw root-cause + fix (2026-07-17, Fable-5):**
`--skip-counter-trend` = dead code (no-op). Spread $0.13→$0.20 gap =
~1.1R (minor). Real cause = joint-drop interaction: features that individually
test as safe become harmful when removed together. **Fix shipped: family-based
group ablation (`--mode group`) added to `run_feature_sweep.py`, `FEATURE_FAMILIES`
dict added to `features.py`, BT_ARGS spread fixed to $0.20.**
Standing rule: multi-feature drop → combined confirmation run mandatory.

**✅ DONE — FS67-24 corrected + 3 new runners built (Imtiyaz objection + Fable-5, 2026-07-17):**
Imtiyaz correctly flagged that whole-family ablation (original FS67-24 design)
is a trivial test — removing 7-11 correlated features will always show a big
loss, that's family signal mass, not evidence `15_min_slot`+`M15_ADX`-style
specific pairwise interaction. Fable-5 confirmed and proposed 3 replacement
runners, all built:
- `FS67-24` (revised) — whole-family ABLATE arms removed, kept restore-value
  arms only (unprune dropped Timing/ADX_DI members — a real question).
- `FS67-25` — zero-retrain SHAP interaction screen (`analyze_feature_interactions.py`,
  new). XGBoost native `pred_interactions`, ranks ALL feature pairs by
  interaction strength from the already-trained live model. No retrain needed.
- `FS67-26` — noise floor calibration. 3 seeds (`QGAI_SEED` env var added to
  `xgb_model.py`), same feature set, measures how much total_R varies from
  randomness alone. **No prior sweep decision has ever been checked against this.**
- `FS67-27` — cumulative restore test. All 32 restorable `_MANUAL_PRUNE`
  features (excl. `corr_imp_ratio`, no-op) restored together vs current live —
  tests the actual shipped cumulative-pruning decision directly.

**✅ DONE — FS67-26 noise floor calibration (2026-07-17):** 3 seeds
(42/43/44), same 25-feature live model, same H2 window. `total_R` =
82.9R / 70.1R / 87.3R (mean 80.1R). **NOISE FLOOR = 17.2R** (range).
**⚠️ This is close to FS67-22's -15.2R and FS67-23's -20.7R deltas for
dropping `15_min_slot`+`M15_ADX`** — those deltas can no longer be
treated as clearly-signal without a same-seed comparison. Do not treat
the drop-cost as settled. See README §Backtest Timing Reference /
registry section for full detail.

**✅ DONE — FS67-25 SHAP interaction screen (2026-07-17), + bug fix:**
Script initially failed (missing `hmm_state` — the script skipped
train.py's separate HMM-state-append step; fixed by mirroring it,
loading the existing `hmm_model.pkl`, no refit). After the fix: 26
active features, 325 pairs ranked. `interaction_matrix_flagged.csv`
came back empty — **by design, not a bug**: SHAP interactions can only
be computed for features actually IN the model, so already-dropped
features (`15_min_slot`/`M15_ADX`) can never appear in a flagged pair.
**Real finding:** 9 of the top 40 pairs cross Timing (`slot_win_rate`,
`day_of_week`) with ADX_DI (`H4_DI_diff`, `h4_adx_slope`, etc.) —
the same Timing↔ADX_DI pattern Imtiyaz originally flagged via
`15_min_slot`+`M15_ADX`, recurring among the surviving family members.
Strengthens the case for `FS67-24`. Full detail in README registry.

**🔴 PRIORITY — run order (remaining):**
1. ~~`FS67-26` (noise floor)~~ ✅ DONE — 17.2R noise floor established
2. ~~`FS67-25` (SHAP screen)~~ ✅ DONE — Timing↔ADX_DI pattern confirmed recurring
3. `FS67-24` (revised, restore-value) — Timing/ADX_DI dropped-member restore test
4. `FS67-27` (cumulative restore) — validates the full pruning decision; bisect if it fails
**House rule: TEST-run first where a _TEST.bat exists (FS67-24 has one).**

### âœ… DONE â€” 2026-07-16 (Ticker + Signal Log border audit, Fable-5 follow-up) â€” Imtiyaz approved
Follow-up to the same-day border-consistency audit â€” owner flagged 4 more
specific symptoms (top ticker too heavy, bottom ticker border invisible,
3 tickers inconsistent with each other + dashboard, Signal Log same
issue). All fixed (detail in `FIXES_CHANGELOG4.md`): F-T1 removed
border-in-border on `.bb-item`/`.bb-label` ticker pills (changes the
2026-07-11 pill-in-pill spec â€” confirmed); F-T2 restored
`#panel_ai_market`'s border (reverses the earlier same-day audit's F7
"intentional, leave alone" call â€” confirmed); F-T3 gave the top ticker
(`.risk-strip`) the same gradient/border/radius/glow treatment as every
other `.tcard` panel; F-S1 unified Signal Log's 4 different separator
colors to 2 standard tokens; F-S2 fixed a last-row double bottom line;
F-S3 removed a redundant inset ring on filter buttons. Verified: JS
parses clean, CSS braces balance 506/506. **Browser hard-refresh only â€”
no bridge restart needed.**

### âœ… DONE â€” 2026-07-16 (Dashboard border-consistency audit, Fable-5) â€” Imtiyaz approved
Full read-only CSS audit of `dashboard.html`'s border rules. Root cause:
up to 4 overlapping edge-render mechanisms (`border`+`outline`+inset
`box-shadow`+pseudo-element gradients) used in different combinations
across components. All fixes applied (detail in `FIXES_CHANGELOG4.md`):
new standardized border token set in `:root`; F1 main-cause fix (30+
selector "four-side separators" group reduced to border-color+outer-glow
only); F2 removed `.tcard::before/::after` double decorative layer; F3
fixed Signal Log double-line (two different-colored borders on one shared
edge); F4 consolidated `.r-cell`/`.sig-hero-mini` triple-declared
border/radius; F5 stopped 3 elements from changing border-WIDTH on state
change (was causing 1px content jitter); F8 replaced 6 hardcoded colors
with border tokens; F10 unified accent-bar widths to the dominant 3px;
F11 removed dead CSS (unused Signal-Card-v1 selectors, duplicate
`.lc-panel`, no-op rule, renamed a duplicate `@keyframes pulse` that was
silently breaking the `.live` dot's intended animation).

**ðŸŸ¡ NOT applied â€” F6 (GridStack sub-pixel/scroll border-clipping):**
deliberately skipped. Fable-5's own report flagged this as needing
panel-by-panel testing, citing real prior regression history in this
exact area (the 2026-07-15 scrollbar-bug fixes for `signal`/`signal_log`
live at this same code spot). Follow-up task, not bundled into this pass.

Verified: all JS `<script>` blocks parse clean, CSS braces balance
(506/506). **Browser hard-refresh only â€” no backend files touched, no
bridge restart needed.**

### âœ… DONE â€” 2026-07-16 (Dashboard audit, Fable-5)
Full read-only technical audit of `dashboard.html` + `bridge_dashboard.py`.
Verdict: "Major Fixes Required" â€” not just visual, real data/functionality
risk (engine itself trades independently of dashboard, so trade execution
was never at risk). All 6 CRITICAL (P0) findings fixed same day â€” detail in
`FIXES_CHANGELOG4.md`:
- P0-1 Closed Trades/Session-W-L/AI-Feedback panels permanently empty (key mismatch `closed_trades` vs `closed_history`) â€” fixed, backend alias added.
- P0-2 Protection badges (Virtual SL/Trailing/Slot/News/Directional/Test Mode) always showed OFF, 6 keys never sent â€” fixed, all 6 keys added.
- P0-3 Keyboard `M` silently flipped LIVEâ†”MONITOR mode, no confirmation â€” fixed, confirm() dialog + shortcut changed to Ctrl+Shift+M.
- P0-4 Hours Heatmap = hardcoded June-2026 backtest data with no "static" label â€” fixed, label added.
- P0-5 Polling race condition (stale response could overwrite fresh one) â€” fixed, monotonic broker_epoch guard added.
- P0-6 TRADES ticker double-counted an open trade (session.trades_today opened-counter + open_count summed together) â€” fixed, dashboard-display value now pure closed-today count.

**ðŸŸ  PENDING â€” P1 (10 items) from same audit, not yet actioned:** per-regime AUC cells always `--` (keys missing); spread-color ternary bug (RED branch unreachable, `dashboard.html:2631`); refresh-interval selector shows wrong default (2s label vs actual 1s); Settings tab half hardcoded/stale (Daily SL shows wrong 8% vs real 9%, 3â˜…/NFP % hardcoded, fake AUC fallback values); `signals_all.csv` (~98k rows) full re-fetch+parse every 15s (perf); light theme has invisible yellow text on several elements; duplicate `@keyframes pulse` silently changed `.live` dot's animation; session-window definitions differ in 3 places (backend vs frontend strip vs heatmap); mobile/tablet header overflow â€” **zero `@media` queries in the whole file**.

**ðŸŸ¡ PENDING â€” P2/P3 (lower priority):** ~500 lines dead JS (old fit/drag/resize system, canvases for sparkline/donut that don't exist in DOM, dead render-blocks); ~30 unique font sizes, unreadable 0.42rem labels, meaningless `--orb`/`--mono` design tokens (both = Arial); threshold logic duplicated in 3 places in `bridge_dashboard.py` (comment itself says "keep in sync!"); ~90+ `!important` uses.

**â³ NEXT (Fable-5 roadmap):** responsive breakpoints (separate commit, verify at 1920/1600/1366/1280/125%/150%/tablet/mobile) and dead-code cleanup (**separate test branch**, full visual regression before merge) â€” not bundled with the P0 fixes above. Bridge + dashboard restart + browser hard-refresh needed to see the P0 fixes live.

### âœ… DONE â€” 2026-07-15
| # | Task | Result |
|---|------|--------|
| **Deep bug audit (Imtiyaz asked "find deep bug")** | **DONE â€” 2 live bugs fixed, several latent found (not fixed, logged).** Two parallel full-engine reviews (core trading/risk + inference/backtest), every finding re-verified by direct code read before acting. **Fixed:** (1) `bridge_core.py` broker-TP-fill close path was the only exit path NOT calling `bridge_multi.close_secondary_accounts()` â€” secondary/slave positions could survive unmanaged after the primary's TP filled on its own; (2) `bridge_core.py recover_open_trades()` last-resort vSL-reconstruction fallback used a hardcoded `/1.5` divisor that went stale when `broker_sl_open_mult` was widened to 3.0 on 07-14 â€” was silently reconstructing a 2x-too-wide vSL on restart-recovered positions with no persist file/comment tag; now reads the live config value. `py_compile` clean, takes effect on next bridge restart. **Not fixed (dormant/latent, logged for awareness):** `manage_secondary_manual_accounts()` primary-reconnect-skip bug (currently dormant â€” the function returns early since `slave_manual_manager_enabled=False`); `in_range_phase` train/serve skew (regime-aware live threshold never applied during training); backtest ratchet-trail bar-i lookahead bias; `corr_imp_ratio` latent double-lookahead (already pruned); `dd_brake.py` 500-ticket applied-deals cap could double-count on very high balance-op-frequency accounts. Detail: `FIXES_CHANGELOG4.md` 2026-07-15. **Follow-up (Imtiyaz): dashboard trade-close confirmation added** â€” `bridge_multi.close_secondary_accounts()` now verifies (re-queries) every secondary is actually flat and returns a summary; `bridge_core.py`'s broker-TP-fill path logs a `ðŸ§¾ TRADE SUMMARY` line and records it via new `bridge_dashboard.record_trade_close_summary()` (persisted `logs/last_trade_close.json`, 15min freshness); dashboard shows a new green/amber `#trade_close_banner` confirming "all accounts flat, no trade open" or flagging a secondary still open. `py_compile` + Node script-syntax check clean; live browser check pending next real broker-TP close. |
| **Current 28-feature config â€” 53-week WFO OOS** | **DONE.** Runner: `backtest/_runners/Run_CurrentLiveModel_WFO_FULL.bat`; results: `backtest/results/wfo_current_live_28feat_20260714/`. Final `_WFO_SUMMARY.csv`: **+282.7R / 53 weeks / 1009 trades / 48 positive weeks / 5 negative weeks / avg +5.33R per week**. This is the honest OOS retraining benchmark for the current live feature config. Old `current_live_28feat_backtest_1yr_20260714` remains **in-sample reference only** (`--allow-in-sample`, leakage check FAIL, +474.4R) and must not be used as keep/reject proof. |
| **Clean single-training OOS 1-year backtest** | **DONE 2026-07-15.** Registry ID: `OOS1Y-01`. Runner: `backtest/_runners/OOS1Y-01_RUN_CurrentConfig_CleanOOS_1yr.bat`; results: `backtest/results/OOS1Y-01_current_config_clean_oos_1yr_20260715/`; summary: `OOS1Y-01_current_config_clean_oos_1yr_20260715_001_summary_st-htf.csv`. Retrained to `data/models/test_workspace` only, live `data/models/final` not touched. Cutoff proof in model meta: `requested_training_cutoff=2025-06-28`, `effective_training_cutoff=2025-06-28`; backtest period `2025-06-29 -> 2026-06-29` with no `--allow-in-sample`. Result: **+338.5R / 1130 trades / WR 52.8% / PF 1.95 / avg +0.300R / max DD 2.6% / fixed 0.01 lot / 3% risk reference return +80.02%**. Regime split: Ranging +206.9R, Trending +52.6R, Volatile +79.0R. This is clean single-training OOS, below old in-sample +474.4R but above current 53-week WFO +282.7R. |
| **FS67-12 h4_support_dist OOS1Y confirmation** | **DONE 2026-07-15 â€” REJECT / keep dropped.** Runner: `backtest/_runners/feature_sweep_67/FS67-12_RUN_h4_support_OOS1YConfirm.bat`; results: `backtest/results/feature_sweep_67/FS67-12_h4_support_oos1y_confirm/`. Baseline matched `OOS1Y-01`: **+338.5R / 1130 trades / PF 1.95 / WR 52.8% / DD 2.6%**. Adding `h4_support_dist` gave **+323.2R / 1130 trades / PF 1.95 / WR 52.3% / DD 2.1%**, delta **-15.3R**, captured pts **8002 -> 7885**, negative weeks **4 -> 8**. It helped in the 3-month FS67-01 screen (+8.1R) but failed the 1-year clean OOS confirmation. Decision: do **not** re-add; no WFO needed unless a future redesigned S/R feature replaces it. |
| **FS67-21 h4_support_dist 6-month WFO confirmation** | **DONE 2026-07-15 â€” REJECT / keep dropped.** Runner: `backtest/_runners/feature_sweep_67/FS67-21_RUN_h4_support_WFO6M.bat`; results: `backtest/results/FS67-21_h4_support_wfo6m_20251229_20260629/`. Candidate-only weekly WFO with `QGAI_UNPRUNE=h4_support_dist` over `2025-12-29 -> 2026-06-29`, retraining in `data/models/test_workspace` only. Existing baseline WFO for the same 26 weeks (`backtest/results/wfo_current_live_28feat_20260714/_WFO_SUMMARY.csv`) = **+90.8R / 484 trades / 21 positive weeks / 5 negative weeks / avg +3.49R per week**. Candidate = **+89.3R / 456 trades / 23 positive weeks / 3 negative weeks / avg +3.43R per week**, delta **-1.5R** and **-28 trades**. It reduced negative weeks, but did not beat baseline total R; combined with FS67-12 OOS1Y failure (**-15.3R**), decision remains: do **not** re-add `h4_support_dist`; design cleaner S/R features later instead. |
| **DD brake made deposit/withdrawal-aware** | **DONE, live, verified.** Imtiyaz flagged VantageCentLive ($3,640, lot 0.05) trading a bigger lot than TradeQuo-001 ($5,046, lot 0.04) â€” inverted. Root cause: TradeQuo's peak-equity brake read an **$814 profit withdrawal** as a 14.7% "drawdown" (MT5 history confirmed net trading result was +$814, zero real drawdown). `dd_brake.py`'s `risk_scale()` now reads MT5 balance-operation deals each call and shifts the peak by the same amount, so only genuine trading losses trigger the brake. Offline test (5 scenarios) all PASS. Bridge restarted 18:03, confirmed live: TradeQuo re-anchored to full risk, no errors. Detail: `FIXES_CHANGELOG4.md` + `FILTERS_MASTER.md` Â§CHANGE LOG, both 2026-07-15. |
| **Slave manual-trade vSL ratchet fixed (wrong symbol on secondary accounts)** | **DONE, live, verified.** Imtiyaz added a manual trade on TradeQuo (symbol `XAUUSDs`, differs from primary `XAUUSD`). Manager detected it and set the 3%-floor correctly, but `bridge_ratchet.get_state()`/`get_htf_state()` hard-coded the PRIMARY symbol in `copy_rates_from_pos`, so the slave's ratchet line was always `None` (`copy_rates failed â€” no state` every cycle) â€” the vSL never trailed, only the wide floor protected it. Fixed: both functions now take an optional `symbol` param (primary callers unaffected, default unchanged) with a per-symbol cache; `bridge_manual.manage()` passes its own connected symbol through. Offline test (6 assertions) all PASS. Bridge restarted, confirmed live: `ðŸ”¼ [XAUUSDs] COMBINED vSL ratchet -> 4020.09` now appears, `copy_rates failed` warning gone. Detail: `FIXES_CHANGELOG4.md` 2026-07-15. |
| **Dashboard UI polish batch** | **DONE.** SIGNAL + SIGNAL LOG equal-height in GridStack (root-caused a `grid-stack-animate` height-transition lock); unified borders across heat-cells/ticker-pills/stat-boxes/edit-mode vs view-mode; fixed an orphaned `.lsf-btn` style block that was silently deleted on every page load (buttons had always rendered as unstyled native buttons); removed a native scrollbar + a hardcoded pixel-offset overlap bug; added viewport meta tag; added a proactive AutoTrading-off dashboard banner (`mt5.terminal_info().trade_allowed`, doesn't wait for an order to fail first). All verified live via browser JS checks, no console errors. Commit `674aa48`, pushed to `origin/main`. Detail: `FIXES_CHANGELOG4.md`, many 2026-07-15 entries. |

### ðŸ¥‡ TOP PRIORITY (Imtiyaz, 2026-07-16) â€” Exit Model / Exit-AI work stream
**Everything else below (bug-audit P0, manual-copy P1, feature-sweep, validation ladder) is now
SECOND priority â€” this is the thing to work on first.** Full background/detail already exists
below at "â³ PLAN â€” smart Exit-AI vs rule-based exits" (2026-07-13 night entry) and "â–¶ Post-cap
continuation audit" â€” not repeated here, just elevated + turned into concrete next steps.
| # | Step | àª¸à«àªŸà«‡àªŸàª¸ | Detail |
|---|------|--------|--------|
| **1** | **Post-cap continuation audit** (registry ID `EXIT01`) | â³ **NEXT â€” run this first** | `engine/analyze_post_cap_continuation.py` + `backtest/_runners/exit_workstream/EXIT01_RUN_PostCapContinuationAudit.bat` â€” built 2026-07-13, organized into the new `exit_workstream` registry (same ID-in-filename + ID-in-result-folder convention as `feature_sweep_67`) 2026-07-16, never run yet. Read-only, no retrain, runs in seconds off the existing `active_baseline` trades CSV. Output now goes to `backtest/results/exit_workstream/EXIT01_post_cap_continuation_audit/`. Measures how far price kept moving after each of the 44 TPCAP-capped trades hit their cap â€” this number is the whole decision gate: if there's real money left on the table after the cap, the redesign below is worth doing; if not, exit-AI work stops here and effort goes elsewhere. |
| **2** | **TP-cap-as-trail-tighten redesign + WFO A/B** | â³ Blocked on #1 | Fable-5's main recommendation: stop hard-closing at the TP cap â€” instead either partial-exit 50-70% at the cap and let the rest trail, or switch to a much tighter trail (M15-line/0.05-0.08% buffer) at the cap-touch moment. Insight: the TP cap's real job is "giveback insurance," not "profit ceiling" â€” trail-tightening gives the same insurance without capping upside. Needs a proper WFO A/B before adoption, same as every other filter change (per CLAUDE.md parity rule). |
| **3** | **Switch north-star metric to MFE-capture** | â³ Not started | Retire the "% of total path length" capture metric (ill-posed â€” denominator shrinks/grows with bar granularity). Switch to per-trade MFE-capture ratio (realized profit Ã· Maximum Favorable Excursion) as the real target for judging any exit-side change from here on. |
| **4** | **Grow trade sample** | â³ Not started | Exit-model effective N â‰ˆ trade count (currently ~131), not bar count â€” Fable-5: do not start exit-AI training below ~500-1000 trades. Longer backtest windows / more regimes needed before #5 is viable. |
| **5** | **Exit-AI phase 1 (only after 1-4)** | â³ Blocked | If still worth pursuing after the above: keep it narrow â€” a binary gating classifier (p(continuation)) invoked ONLY at 2 decision points (cap-touch, HTF-flip-moment), never a free-running per-bar policy or RL agent. Labels via triple-barrier method (LÃ³pez de Prado), features strictly â‰¤ t, trade-episode-level CV grouping, purge+embargo at fold boundaries, evaluate via OOS total $ replay only (never classifier AUC alone). |

> **Immediate action:** run `backtest/_runners/exit_workstream/EXIT01_RUN_PostCapContinuationAudit.bat` â€” it's the fastest, lowest-risk
> step (read-only, seconds to run) and its result determines whether step 2 is worth building at all.

### ðŸŸ  PENDING CONFIRMATION â€” `backtest\_runners\` folder cleanup (Claude flagged, 2026-07-16, awaiting Imtiyaz go-ahead)
**Do NOT execute without explicit confirmation â€” Imtiyaz is away 3-4 days and this touches ~109 files
referenced across ~5 months of changelog history.**

**Found:** `backtest\_runners\` root has **109 loose `.bat` files** with zero organization, plus only
2 organized registry subfolders (`feature_sweep_67`, `exit_workstream`) built so far, plus **1 stray
0-byte file** (`WFO`, no extension, dated 2026-07-07 â€” looks like an accidental empty file, not a
real runner).

**Themes identified in the 109 loose files (~15 groups):** WFO variants (~20: `Run_WFO_*`,
`Run_HMM_*_WFO*`, `Run_AsOf_WFO_*`, `Run_Ablation_T10_WFO*`), HMM (~7), feature ablation/removal
(~15: `Run_OB_*`, `Run_RemovedFeature_*`, `Run_RegimeScore_*`, `Run_RawMove_*`, `Run_Active27_*`),
old pre-registry feature-sweep (~5: `Run_FeatureSweep_*` â€” likely superseded by `feature_sweep_67/
FS67-*` but not deleted, needs a decision), filter A/B tests (~8: `Run_Range_AB_*`,
`Run_PreNews_AB_*`, `Run_EarlyDiscount_AB_*`, `Run_Threshold_AB_*`, `Run_InRange_*`), TP/regime/CTF
(~6), SMMA/ADX (~6), PBEntry/PBGen sweeps (~4), full-history baselines (~6: `Run_Backtest_
FullHistory`, `Run_FullBT_*`, `Run_CurrentLiveModel_*`), master/overnight batches (~4:
`Run_PathA_MASTER`, `Run_Overnight_*`), signal-log/data maintenance (~6), diagnostics (~6:
`Run_LeakageGuard_*`, `Run_HTFAlignmentSkipRate_TEST`, `Run_Capture_Analysis`), legacy retrain (~2).

**Recommended approach (Claude's proposal, not yet actioned):**
1. **Move only, do NOT rename** the 109 existing bats into theme subfolders (e.g. `_runners\wfo\`,
   `_runners\hmm\`, `_runners\feature_ablation\`, `_runners\filters_ab\`, `_runners\smma_adx\`,
   `_runners\diagnostics\`, `_runners\legacy\`, ...) â€” keeping filenames identical means every
   existing changelog reference (`FIXES_CHANGELOG4.md` and older) still names the right file, just
   under a new path prefix.
2. Delete the stray 0-byte `WFO` file (confirm it's really junk first â€” looks like it, but check
   before deleting).
3. Decide what to do with the 5 old pre-registry `Run_FeatureSweep_*` bats â€” keep as legacy
   reference, move to `legacy/`, or delete now that `feature_sweep_67/FS67-*` replaces them.
4. Add a short `README.md` per new subfolder listing what's inside (same style as
   `feature_sweep_67/README.md` / `exit_workstream/README.md`).

**â³ NEXT: get Imtiyaz's go-ahead on the approach (and the FeatureSweep-legacy decision) before
touching any of the 109 files.**

### ðŸ”´ P0 â€” DO FIRST TOMORROW (2026-07-15 deep bug audit â€” all 7 bugs found, priority order)
| # | Bug | àª«àª¾àªˆàª²:àª²àª¾àªˆàª¨ | àª¸à«àªŸà«‡àªŸàª¸ | àª•à«‡àª® àªªàª¹à«‡àª²àª¾ | Action |
|---|-----|-----------|--------|----------|--------|
| **1** | **`in_range_phase` train/serve skew** | `inference.py:753` vs `train.py`'s `compute_features()` call | âŒ **REVERTED 2026-07-16 â€” was NOT a bug** | Flagged 2026-07-15 as an unintended train/serve skew (~10% of Volatile-regime bars served a feature value the model wasn't trained on). Fixed same day by flipping `QGAI_REGIME_INRANGE` default `"1"`â†’`"0"`. **Imtiyaz corrected this 2026-07-16: this train/serve mismatch was already known and deliberately accepted when the feature was built 2026-07-12 â€” not a bug.** | **Reverted same day:** `inference.py` â€” `QGAI_REGIME_INRANGE` default restored to `"1"` (ON), comment rewritten to record that this mismatch is intentional and not to be "fixed" again without confirming first. `py_compile` clean. Detail: `FIXES_CHANGELOG4.md` + `FILTERS_MASTER.md` (both 2026-07-16). **FS67-02 is NOT stale after all** â€” it ran under the default that was actually the accepted live behavior all along, so its 2026-07-16 baseline/ablation numbers stand; the earlier "stale, re-run" flag on FS67-02 is withdrawn. The separate 2026-07-12 full-year A/B finding (OFF beat ON by 1.7R) still stands as a real, honest result on record â€” Imtiyaz's point is that the difference was small enough not to act on, not that the A/B test was wrong. |
| **2** | **Backtest ratchet-trail bar-`i` lookahead** | `backtest_replay.py:563` | âœ… **INVESTIGATED 2026-07-16 â€” NOT A BUG (false positive)** | Original audit claim: bar `i`'s trail line uses bar `i`'s own close, applied to bar `i`'s own low/high = lookahead. | **Verified false by reading `trend_signal.py::compute_trend()` + `SimTrade.update()`/`ratchet_bar()` line-by-line:** `ratchet_bar()` computes the new line (using bar `i`'s close to pick BUY/SELL direction) and only **stores** it into `self.virtual_sl` â€” it never checks bar `i`'s own low/high against that new value. The low/high check happens in `update()`, called BEFORE `ratchet_bar()` each bar, always against the OLD `virtual_sl` set by a prior bar. The new line only gets tested starting bar `i+1`. This exactly matches live's bar-close-driven update cycle â€” no lookahead. HTF line variant also checked: uses `merge_asof(direction="backward")` with an explicit forming/non-forming timestamp offset (comment at line 387 already says "NO lookahead"). **No code change needed; past WFO/backtest numbers are NOT affected by this â€” the original P0 audit finding is retracted.** |
| **3** | **`manage_secondary_manual_accounts()` primary-reconnect-skip** | `bridge_multi.py:514,541` | âœ… **FIXED 2026-07-16** | Was dormant (`slave_manual_manager_enabled=False`) so zero live risk, but cheap to fix while fresh. | Done: removed the `touched` flag entirely â€” `_reconnect_primary()` now runs unconditionally after the secondary loop, regardless of whether any secondary succeeded. Still a no-op today (function returns early on the disabled flag) but safe if that flag is ever re-enabled. `py_compile` clean. |
| **4** | **`dd_brake.py` 500-ticket applied-deals cap** | `dd_brake.py:185` | âœ… **FIXED 2026-07-16** | Low probability (needs >500 balance-type deals in 120 days on one account) but silently double-counts a deposit/withdrawal into the DD-brake peak if it fires. | Done: replaced the count-based cap (`sorted(applied)[-500:]`) with a window-based prune â€” `applied` is now intersected with whatever `_balance_ops()` currently returns (i.e. still inside its 120-day window) whenever that read is trustworthy (`_connection_matches(key)` True this cycle); falls back to a generous 2000-ticket defensive cap only when the connection didn't match this cycle (so there's no reliable window snapshot to prune against). Anything that ages out of the 120-day window can never reappear in `ops` again, so pruning it is always safe â€” no double-count risk regardless of how many balance ops an account posts. `py_compile` clean. |
| **5** | **`corr_imp_ratio` latent double-lookahead** | `features.py` (was 492-585) | âœ… **DEAD CODE DELETED 2026-07-16 (Imtiyaz: option B)** | Already pruned from the live model â€” zero current impact. Only mattered if someone set `QGAI_UNPRUNE=corr_imp_ratio` for research (the leaky code was still present, just unused). | **Fully removed the leaky computation** (Imtiyaz chose full cleanup over leaving it dormant): deleted `build_trend_ratio_table()` + `get_trend_ratio_features()` from `features.py`; `compute_features()`/`build_feature_matrix()` now hardcode `corr_imp_ratio=1.0` instead of computing a real (leaky) value. Removed the now-dead `ratio_df` parameter/plumbing from `inference.py` (2 call sites + init), `train.py` (2 build+pass sites), `build_feature_snapshot.py`, and `run_feature_sweep.py`'s `HIGH_PROB_TIER` test list (unpruning it is now a no-op). Fixed 2 historical diagnostic scripts still reachable via active `Start\` bats (`test_leakage_auc.py` â†’ `Start\6_Test_Leakage_AUC.bat`, `test_ablation_10.py` â†’ `Start\7_Ablation_10_Tests.bat`) so they don't crash if re-run, with a printed note that their corr_imp_ratio comparison is no longer a fresh measurement. **Left untouched (not on any active bat, would break if re-run):** `auc_volume_compare.py`, `test_tickvol_feature.py`. **Side-effect (cosmetic only):** `bridge_dashboard.py`'s "Market Structure" panel `phase_score` loses its occasional Ã—1.2 multiplier (was `if corr_imp_ratio<0.5`, now always constant 1.0 so the condition never fires) â€” display-only, not a trading decision. `py_compile` clean on all 11 touched `.py` files. Detail: `FIXES_CHANGELOG4.md` 2026-07-16. |
| **6** | **Broker TP-fill never closed secondary/slave accounts** | `bridge_core.py:619` | âœ… **FIXED 2026-07-15** | Was the only exit path (of vSL/FLIP/SMART_CLOSE/daily-SL/daily-TP/opposite-signal) not calling `bridge_multi.close_secondary_accounts()` â€” a secondary could stay open+unmanaged after the primary's broker TP filled on its own. | Done: added the missing `close_secondary_accounts()` call, PLUS a same-day follow-up (Imtiyaz) â€” the call now re-verifies (re-queries) every secondary is actually flat and the dashboard shows a `#trade_close_banner` confirming it. Listed here for a complete 7-bug record; no further action unless the banner shows a problem on its first real trigger. |
| **7** | **Restart-recovery vSL fallback `/1.5` divisor** | `bridge_core.py:761` | âŒ **REVERTED 2026-07-16 â€” was NOT a bug** | Originally flagged 2026-07-15 as "stale, should track `broker_sl_open_mult` (now 3.0)". **Imtiyaz corrected this 2026-07-16: the 1.5 divisor here is INTENTIONAL, kept separate from `broker_sl_open_mult` on purpose â€” SL-hunt protection for the app's own reconstructed vSL in this rare no-persist/no-tag fallback.** History check confirmed it: the 2026-07-07 FAB-S4 entry (`FIXES_CHANGELOG4.md`) shows this exact divisor was tightened 3.0â†’1.5 alongside the trade-open broker-SL mult, on Fable-5's recommendation; the 2026-07-14 change that widened `broker_sl_open_mult` back to 3.0 for the BROKER-visible stop deliberately did not touch this recovery-only divisor. | **Reverted same day:** code changed back to the hardcoded `/1.5`, with an expanded comment explaining the history + the explicit "do not sync to `broker_sl_open_mult` without confirming first" warning, so this doesn't get "fixed" again by mistake. `py_compile` clean. **Lesson reinforced:** an audit finding that "config X and Y should match" can be wrong when X and Y serve deliberately different purposes â€” confirm with Imtiyaz before touching, exactly as the standing CLAUDE.md rule already says. |

> Full original write-up with concrete before/after examples for all 7: `FIXES_CHANGELOG4.md` 2026-07-15 ("Deep bug audit") + 2026-07-16 follow-up entries. **âœ… 6 of 7 items closed as of 2026-07-16** â€” #1/#3/#4/#5 fixed, #2 investigated and retracted (false positive, no bug), #6 fixed 2026-07-15. **#7 REVERTED 2026-07-16 â€” was NOT a bug** (Imtiyaz: intentional SL-hunt protection, confirmed via 2026-07-07 history). 2 of the original 7 "bugs" (#2, #7) turned out not to be bugs on closer investigation â€” both retracted honestly rather than left mis-recorded.

### ðŸ”´ P0 â€” Final bug audit (2026-07-16, round 2)
| # | Bug | àª«àª¾àªˆàª²:àª²àª¾àªˆàª¨ | àª¸à«àªŸà«‡àªŸàª¸ |
|---|-----|-----------|--------|
| **B8** | Dashboard `write_dashboard()` exception swallowed at `log.debug` level â€” crash invisible in production | `bridge_dashboard.py:928` | âœ… **FIXED** â€” `log.debug` â†’ `log.warning` |
| **B9** | DD brake `_save()` peak persist failure silent (`pass`) â€” restart after failure = peak lost = DD brake bypassed | `dd_brake.py:105` | âœ… **FIXED** â€” bare `pass` â†’ `log.warning(...)` |
| **B10** | DD brake `_balance_ops()` failure silent â€” deposits/withdrawals ignored = phantom drawdown | `dd_brake.py:129` | âœ… **FIXED** â€” silent `return []` â†’ `log.warning(...)` + `return []` |
| **B11** | Dead constants imported in config dump (`TRAIL_AFTER_R`, `BREAKEVEN_BUFFER`, `PARTIAL_CLOSE_*`, `SMART_EXIT_ENABLED`, `TP_MULT`) â€” removed in L7b but still imported | `bridge_main.py:279-284` | âœ… **FIXED** â€” dead imports removed (log output was already correct since 2026-06-30 fix) |

### ðŸ”´ P1 â€” HIGH PRIORITY (Imtiyaz, 2026-07-15)
| # | Task | Spec |
|---|------|------|
| **ðŸ”´ P1 â€” Mirror PRIMARY manual trades to SLAVE accounts at each slave's own 3% risk** | **âœ… CODE BUILT 2026-07-15 (same day) â€” â³ NOW NEEDS: DEMO-TEST â†’ then enable live.** All 6 pieces below are implemented and offline-tested **11/11 PASS** (mocked MT5, no real orders): separate magic 202697 (collision guard), open hook, close hooks on all 4 exit paths, restart/duplicate guard (asks the BROKER, not in-memory state), SL basis (`manual_copy_sl_basis="floor"` = the manual's real max-loss distance), and the leg-change limitation is documented-not-solved. Files: `config.py`, `bridge_multi.py`, `bridge_manual.py`, `bridge_main.py`. Detail: `FIXES_CHANGELOG4.md` + `FILTERS_MASTER.md` (2026-07-15). <br><br>**â³ REMAINING (this is the actual next step):** `manual_copy_to_slaves_enabled` is **False** (default OFF â€” zero live effect right now). To use it: (1) **DEMO-test** â€” open a manual trade on the primary DEMO, confirm both slaves get a correctly-sized copy with magic 202697, then close the manual and confirm both copies close; (2) restart the bridge with the flag True; (3) confirm with Imtiyaz before enabling on funded accounts. **Known gap to decide later:** adding a 2nd manual leg does NOT resize/re-mirror the existing slave copies. <br><br>**Original spec kept below for reference.** <br><br>**âœ… Already existed (reused, not rebuilt):** `bridge_multi._execute_on_account(acct, direction, sl_dist, tp_p, comment)` already sizes each secondary independently via `calc_lot(equity, sl_p, si)` = that account's OWN equity Ã— 3% risk â€” this is exactly the sizing Imtiyaz wants (proven live: Vantage $3.6kâ†’0.05 lot, TradeQuo $5kâ†’0.08 lot). `bridge_manual.manage()` already knows when a combined manual position is NEW (`st is None` branch), its net direction + avg entry, and all 4 ways it ends (floor breach / vSL breach / target TP / user closed it themselves â†’ the `if not manual:` branch). <br><br>**âš ï¸ Must build (6 pieces):** **(1) SEPARATE MAGIC** â€” add e.g. `manual_copy_magic = 202697` to `config.py`. **CRITICAL:** `bridge_multi.close_secondary_accounts()` closes ALL `magic == MAGIC` (202600) positions on secondaries and is called every time the primary BOT closes its own trade â€” so if manual-copies reuse 202600, **the bot closing its own trade would wrongly also close Imtiyaz's manual copies.** `_execute_on_account()` currently hardcodes `"magic": MAGIC` (bridge_multi.py ~line 261) â†’ needs a magic parameter. **(2) Open hook** â€” in `bridge_manual.manage()`'s `st is None` branch (primary only), call a new `bridge_multi.execute_manual_copy_to_secondaries(direction, sl_dist, tp_p, magic=manual_copy_magic)`. **(3) Close hook** â€” all 4 exit paths in `bridge_manual.manage()` must call a new `bridge_multi.close_manual_copies_on_secondaries()` that closes ONLY `magic == manual_copy_magic` (mirror of `close_secondary_accounts()` but magic-scoped). **(4) ðŸš¨ RESTART-SAFETY (most dangerous)** â€” `bridge_manual._managed` is an in-memory dict; after a bridge restart `st is None` fires again for an ALREADY-mirrored manual trade â†’ **would open DUPLICATE real positions on the slaves.** Fix by either persisting mirror state to disk (like `vsl_persist.py` does for vSL) OR, before mirroring, checking whether the slave already holds a `manual_copy_magic` position. **(5) SL-distance policy** â€” decide what `sl_dist` to pass for slave sizing: `manual_sl_pct` (1.0%, the manual manager's sizing SL) vs `manual_risk_pct` (3.0%, its hard floor). These give very different slave lots â€” pick deliberately and document. **(6) Leg-change policy** â€” if Imtiyaz adds a 2nd manual leg (net volume + avg entry change), `st` stays non-None so no re-mirror fires â†’ slave copies go stale. Decide: ignore, resize, or re-mirror. <br><br>**Context:** `slave_manual_manager_enabled` was set **False** on 2026-07-15 (Imtiyaz) â€” slave-side manual trades get no bot management. That's a SEPARATE switch and does not block this task (this is primaryâ†’slave copying, not slave-side managing), but note a mirrored copy on a slave will NOT be vSL/floor-managed there â€” its protection comes from the primary's manual manager triggering the close hook (3). <br><br>**âš ï¸ House rules for this task:** places **REAL orders on funded accounts** â†’ **DEMO-TEST HEAVILY first** (CLAUDE.md: "Always test on DEMO before live"). Ship behind a config flag defaulting **OFF**. Confirm with Imtiyaz before enabling live. Precedent worth heeding: on 2026-07-15 a same-day dd_brake "fix" regressed and silently blocked a real live SELL â€” it was caught only because Imtiyaz was watching. Update `FIXES_CHANGELOG4.md` + `FILTERS_MASTER.md` (both) on any config/filter change, per standing rules. |

### â³ VALIDATION PLAN â€” Yearly 2022â†’2026 Train/Backtest/WFO
| # | Task | Detail |
|---|------|--------|
| **Yearly validation ladder** | **Plan only, not started.** Goal: validate the current feature/config across 2022-2026 without leakage using a full ladder: data audit -> yearly single-training OOS backtests -> yearly WFO -> comparison report -> final live retrain only if gates pass. This is the macro robustness check after the current 53-week WFO. |
| **Stage A â€” Data audit** | Check 2022-2026 coverage for OHLC, ADX, news/calendar, and trade-label data. Record each file's start/end date, missing candles, duplicate timestamps, timestamp mismatches, and whether every feature can be calculated from data available at signal time. Leakage guard must remain active. |
| **Stage B â€” Yearly single-training OOS backtests** | Use isolated `data/models/test_workspace` only, never `data/models/final`. No `--allow-in-sample`. Each fold must print `Leakage check PASS`. Folds: **Y1** train cutoff `2022-12-31`, test `2023-01-01 -> 2023-12-31`; **Y2** train cutoff `2023-12-31`, test `2024-01-01 -> 2024-12-31`; **Y3** train cutoff `2024-12-31`, test `2025-01-01 -> 2025-12-31`; **Y4** train cutoff `2025-12-31`, test `2026-01-01 -> latest closed period`. Same risk, TP/SL, ratchet buffer, spread/slippage assumptions, max-open, and feature set across all folds. |
| **Stage C â€” Yearly WFO** | For each year 2023, 2024, 2025, 2026, run WFO inside that year: retrain before each fold and test the next unseen fold. Weekly WFO = detailed proof; monthly WFO = faster macro proof. Keep all retrains in `test_workspace`. Save per-year folders and combined `ALL_OOS_trades.csv`/summary. |
| **Stage D â€” Comparison report** | Build one report with: Year, single-training R, WFO R, trades, WR, PF, avg R, max DD, positive folds, worst fold/month, best fold/month, BUY/SELL split, regime split, probability buckets, and top-trade concentration. Compare yearly single-training vs yearly WFO; flag any year where single-training looks strong but WFO collapses. |
| **Stage E â€” Pass/fail gate** | Pass only if at least **3/4 years positive**, total 4-year WFO positive, PF > 1.2, avg R positive, drawdown acceptable, no one year/regime dominates all profit, BUY and SELL are explainable, and WFO broadly agrees with single-training direction. If any year collapses, mark HOLD/REVISE instead of live scaling. |
| **Stage F â€” Final live train** | Only after the yearly validation ladder passes: train final live model on all available clean data (`2022 -> latest closed date`), save to `data/models/final` with backup, record feature list/model hash/data cutoff, and reference the WFO/yearly validation proof. Then demo/forward test before larger live size. |

> Always sorted by priority. P1 = do first. Full detail/history â†’ WORKING_NOTES.md + FIXES_CHANGELOG4.md.
> **DECISION (2026-06-26): confirm all ideas on the CURRENT period first. Full-history is PARKED until then.**
>
> **â–¶ NEXT PRIORITY (2026-06-29, Anisa+Claude): edge is proven (regime-TP beats global on full-history**
> **AND WFO OOS). The remaining unknowns before scaling REAL money are DRAWDOWN + operational safety â€”**
> **NOT more edge-validation. Order: (1) P2b â€” measure real 3% drawdown ($10k sim; fixed-lot DD 1.7% is**
> **NOT the real figure, could be ~28-39%); (2) finish L8 safety + watch the L8 bug-fix holds on demo;**
> **(3) run demo 1-2 weeks on the locked config; (4) then scale real money small (consider risk 1-2% if**
> **DD high). PARK research (L2 A/B, more TP/buffer sweeps, ADX/news studies) until live is stable â€” don't**
> **add variables mid-validation. Global WFO re-run = optional/low-priority (regime already wins). DO LATER.**
>
> **TESTING STAGE-GATE (2026-07-12): Every feature/strategy result must be tagged by stage before it is trusted.**
> **Loop: Stage 1 = 3-month retrain backtest -> Stage 2 = 1-year single-training backtest -> Stage 3 = WFO ->**
> **Monte Carlo -> forward/demo -> small live. A 3-month result is screening only, never final proof.**
> **Checklist: `docs/STRATEGY_TESTING_STAGE_GATE.md`.**

### âœ… àª¥àªˆ àª—àª¯à«àª‚ (DONE â€” 2026-07-13)
| # | Task (àª•àª¾àª®) | àªªàª°àª¿àª£àª¾àª® |
|---|------------|--------|
| **Data-leakage guard** (Imtiyaz flagged: 07-12 backtests train/test overlap) | Hard-block permanent fix â€” `engine/leakage_guard.py` (NEW) reads a `*_meta.json` sidecar per model (main/buy/sell/state/HMM/slot-table), takes MAX exposure date across all, raises (not warns) if `>= backtest --from`. `train.py` writes sidecars for every model (previously only main+buy+sell had any) + atomic temp-dir swap (crash-safe, old models kept at `final_prev`). `backtest_replay.py` hard-exits unless clean or `--allow-in-sample` explicitly passed (loud banner, never default). `run_wfo.py` 1-day fold-boundary overlap also fixed (`QGAI_TRAIN_CUTOFF = week_start âˆ’ 1 day`, not `week_start`). 9 automated tests (`engine/tests/test_leakage_guard.py`) â€” all pass. Real (non-synthetic) smoke-verified â€” **independently re-run by Imtiyaz on his own PC**: overlapping window correctly BLOCKED (leakage report + hard error), clean window correctly PASSED (+2.9R real backtest), live models correctly auto-restored after. Delivered as `.bat` (house rule): `Run_LeakageGuard_UnitTests.bat` + `Run_LeakageGuard_Smoke_TEST.bat`. Detail: `docs/FIXES_CHANGELOG4.md` 2026-07-13. |
| **Root cause found** | Training trades file (`Back_testing_data_final_cleaned_RELABELED.xlsx`) ends **2026-04-29 20:00** (2743 rows); 07-12's `*_TEST.bat`/`*_RETRAIN_TEST.bat` (OB redundancy, RemovedFeature-10, RawMove, RegimeScore, InRange sweep, LeakFix-P1P2P3, Legacy-CTFOFF) called `train.py` with no `QGAI_TRAIN_CUTOFF` then backtested `--from 2026-04-01` â†’ Apr 1-29 (164 trades) in-sample. WFO-based bats (`run_wfo.py`) were already correct (own per-fold cutoff) except the newly-found 1-day boundary overlap, now also fixed. |
| **TP-cap/regime training-label parity bug â€” FIXED (code), retrain judged NOT worth it** | Imtiyaz's hypothesis confirmed: `relabel_trades.py`/`rebuild_trainset.py`/`shadow_ledger.py` used a flat 1.00% TP cap for every regime while live has used regime-adaptive TP (Ranging 2.0/Trending 1.0/Volatile 0.8) since 06-27. Cheap no-retrain diagnostic (Fable-5's recommended gate) measured **0.62% total label flips** (17/2,743 â€” Ranging 0.37%, Volatile 1.83%, Trending 0%), well under the 3%/5-7% retrain-justification gate â€” and win-prob models train on binary Win/Loss only (R never enters training), so 17 flips can't move an XGBoost boundary. **Full relabel+retrain+WFO explicitly NOT done** (Fable-5: ROI negative). **Code fix DONE anyway** (correctness + parity, esp. for `shadow_ledger.py`'s live-vs-shadow checks): added `CFG.filters.tp_by_regime` as the single source of truth in `config.py` (was duplicated as a literal in 4 files); `backtest_replay.py` now imports it (values unchanged, refactor-only); `relabel_trades.py`/`rebuild_trainset.py` now retro-classify each historical entry's regime via the EXISTING production `hmm_model.pkl` (no refit) and apply the matching regime TP cap; `shadow_ledger.py` reuses its already-logged `hmm_state` per signal (no HMM call needed there). All 5 touched files re-compiled clean. **Found + fixed a real bug along the way**: the new diagnostic/audit scripts (`diagnose_tp_cap_regime_labels.py`, `analyze_post_cap_continuation.py`) crashed with `ValueError: I/O operation on closed file` from a double `sys.stdout` UTF-8-wrap (they wrapped stdout themselves AND imported `analyze_capture.py`, which does the same wrap â€” the first wrapper's garbage collection closed the shared buffer); fixed by removing the redundant wrap in both. Detail: `docs/FIXES_CHANGELOG4.md`, `docs/FILTERS_MASTER.md` Â§CHANGE LOG, both 2026-07-13 (night). |

### ðŸŸ¡ àª¬àª¾àª•à«€ (REMAINING â€” BUY-signal audit follow-up, added 2026-07-13)
| # | Task | àªµàª¿àª—àª¤ |
|---|------|------|
| **Model-version logging** | âœ… DONE 2026-07-13 â€” every signal now logs `model_version` (main model's `model_created_at`+`data_hash`) via `inference.py _make_result` + `bridge_data.log_signal` (CSV + SQLite migration, mirrors the `trade_action` column pattern). Verified via isolated smoke test (scratch files only). Closes the exact reproducibility gap the 04:30 BUY-signal audit hit. |
| **Volatile counter-HTF gate** âŒ REJECTED 2026-07-13 (night) | Signal-audit + Fable-5 second opinion found: honest 53-week WFO baseline shows Volatile-regime trades in the 42-48% win_prob band that go AGAINST dominant HTF direction are net-losing (n=38, -1.9R, PF 0.88) vs the same band aligned WITH HTF (n=48, +18.9R, PF 3.78). Confirmed NOT a time/slot confound. **CAVEAT found same day:** re-measured with raw ADX-DI instead of the SMMA-based `ts_htf_agreement` the gate actually uses â€” the "against" bucket flips to PROFITABLE (+1.57R) â€” flagged as possibly fragile/noise. **3-month WFO A/B (12wk, `Run_VolHTFGate_AB_WFO_TEST.bat`) CONFIRMED the caveat: Config A (gate OFF) +32.5R/207 trades/9-of-12 positive weeks vs Config B (gate ON) +17.1R/183 trades/8-of-12 positive weeks â€” B is -15.4R (-47%) WORSE than A, every week from 2026-05-04 onward.** Per the bat's own decision rule (B>=A required to proceed to the 53-week FULL WFO), **B<A â†’ REJECTED, `Run_VolHTFGate_AB_WFO_FULL.bat` not needed.** `QGAI_VOL_HTF_GATE` stays OFF by default in `inference.py` (already env-gated, zero live impact â€” no revert needed). The SMMA-based `ts_htf_agreement` finding is confirmed fragile/noise, not a real edge. Results: `backtest/results/volhtfgate_wfo_TEST_A_off/_WFO_SUMMARY.txt`, `volhtfgate_wfo_TEST_B_on/_WFO_SUMMARY.txt`. |
| **67-feature validation sweep â€” 3-stage plan (Imtiyaz, detailed spec 2026-07-13)** | `engine/run_feature_sweep.py` redesigned around Imtiyaz's exact priority plan and now supports registry folders, cutoff/window overrides, and baseline reuse via `QGAI_SWEEP_BASELINE_JSON`. Organized runners live in `backtest/_runners/feature_sweep_67/`; organized results live in `backtest/results/feature_sweep_67/`. Screening runners: `FS67-01_RUN_PriorityBatch.bat` -> `FS67-01_priority_batch`; `FS67-02_RUN_Tier1_Active.bat` -> `FS67-02_tier1_active`; `FS67-03_RUN_Tier2_HighProbability.bat` -> `FS67-03_tier2_high_probability`; `FS67-04_RUN_Tier3_Remaining.bat` -> `FS67-04_tier3_remaining`. **Baseline rule:** `FS67-01` creates the 3-month baseline; `FS67-02/03/04` reuse `FS67-01_priority_batch/baseline/result.json` and do not rerun baseline. OOS1Y confirmation runner: `FS67-11_RUN_PriorityBatch_OOS1YConfirm.bat` -> `FS67-11_priority_batch_oos1y_confirm`, same cutoff/window as `OOS1Y-01` (`2025-06-28`, `2025-06-29 -> 2026-06-29`). Priority batch features: `h4_support_dist, h1_resist_dist, move_2hr, ts_line_dist_pct, tick_volume, H4_DI_diff, h4_adx_slope, move_4hr, momentum_aligned_2hr, h1_support_dist`. Optional all-in-one screening runner: `FS67-00_RUN_ALL.bat`. Each feature auto-routed to ablate (if active) or unprune (if dropped), computes BUY/SELL split, regime split, week consistency, capture-efficiency, and verdict. **Best decision flow: FS67-01 quick 3-month screen -> OOS1Y confirm for candidates -> WFO before live adoption.** **âš ï¸ 2026-07-15: FS67-02 failed TWICE that day (08:52, 16:32) with `TRAINING LOCKED` -- `train.py`'s lock file (`data/models/.training_lock`) is shared across ALL sweep runners AND the live retrain (not scoped per test_workspace despite the folder name).** **âœ… FS67-02 completed 2026-07-16 06:25** â€” baseline +18.3R/131tr/PF1.78/WR52.7%, 7 DROP_CANDIDATEs (`ts_bars_since_flip` +4.5R, `in_range_phase` +4.0R, `15_min_slot` +3.1R, `M15_DI_diff` +3.3R, `slot_cos` +2.3R, `mins_to_next_3star` +1.5R, `M15_ADX` +0.8R), `H4_ADX` = clean CORE_KEEP, `day_of_week` = NEUTRAL_REDUNDANT. **âœ… NOT stale after all (correction 2026-07-16):** briefly flagged as stale because it ran with the `in_range_phase` regime-aware override still ON, treating that as a bug to be fixed. Imtiyaz corrected same day: that override being ON in live/backtest is the deliberately-accepted, intended behavior (see P0 item #1's reverted status) â€” so FS67-02's numbers were measured under the SAME setting that's actually meant to be live. No re-run needed for this reason. Its `in_range_phase` DROP_CANDIDATE verdict (+4.0R if removed) can be read at face value alongside the usual 3-month-screen-only caveat (needs OOS1Y + WFO confirmation before any adoption decision, same as every other feature here). **â³ NEXT: FS67-03/FS67-04 one at a time (training-lock caveat â€” confirm no other train.py active first).** **âœ… 2026-07-16: FS67-02's 6 `DROP_CANDIDATE` features (`ts_bars_since_flip` +4.5R, `15_min_slot` +3.1R, `M15_DI_diff` +3.3R, `slot_cos` +2.3R, `mins_to_next_3star` +1.5R, `M15_ADX` +0.8R) now have an OOS1Y confirmation runner built: `backtest/_runners/feature_sweep_67/FS67-13_RUN_Tier1DropCandidates_OOS1YConfirm.bat` -> `FS67-13_tier1_drop_candidates_oos1y_confirm/`, same `OOS1Y-01` window (train cutoff `2025-06-28`, backtest `2025-06-29 -> 2026-06-29`) as `FS67-11`/`FS67-12`. `in_range_phase` (also a FS67-02 DROP_CANDIDATE, +4.0R) is deliberately excluded â€” already decided 2026-07-16 to keep as-is, not re-litigated here. **House-rule test-first companion built:** `FS67-13_RUN_Tier1DropCandidates_OOS1YConfirm_TEST.bat` â€” 1-feature (`M15_ADX`) isolated `_TEST` result folder, run this FIRST to confirm no crash / leakage-guard PASS / correct output location before the full 6-feature run. **Not run yet â€” training-lock caveat applies (confirm no other train.py active first).** A feature that flips to KEEP on the 1-year window should not be dropped even though the 3-month screen liked it; only a feature that stays DROP_CANDIDATE on both windows proceeds to a full WFO confirmation before any live adoption.** |
| **â–¶ Post-cap continuation audit â€” FIRST step of the exit-work stream (Fable-5, 2026-07-13 night)** | `engine/analyze_post_cap_continuation.py` (NEW) + `Run_PostCapContinuationAudit_TEST.bat` â€” for every TPCAP-exited trade in the existing `active_baseline` feature-sweep run, replays forward using the SAME H1-line trail + HTF-flip exit already live, measures extra pts/R gained or given back had the cap not force-closed the trade. Read-only, no retrain, runs in seconds off the trades CSV already on disk. **This is the decision gate for the whole smart-Exit-AI question (see plan row below) â€” its result decides whether TP-cap-as-trail-tighten redesign is worth doing at all.** **Sequencing (Imtiyaz, 2026-07-13 night): run this AFTER the 67-feature validation sweep (row above) finishes its nightly runs â€” this audit is the first task of the SEPARATE exit-side work stream, starts once feature-sweep work is done.** â³ NEXT: run `Run_PostCapContinuationAudit_TEST.bat` (fast, can run any night feature-sweep isn't using the PC). **2026-07-16: renamed/moved to registry ID `EXIT01` â€” now `backtest/_runners/exit_workstream/EXIT01_RUN_PostCapContinuationAudit.bat`, see the TOP PRIORITY section at the top of this file.** |
| **BUY/SELL blend-weight asymmetry** | Fable-5 flagged: `dir_weight` is 0.35 for BUY vs 0.45 for SELL (`inference.py` routing block) â€” SELL leans harder on its directional model. Reason for the asymmetry not yet investigated â€” pending. |
| **Volatile 0.42% threshold contradictory evidence** | Fable-5 flagged: code comments cite two different Volatile win-rate stats (70.2% vs 37.7%) as the basis for the threshold discount. Needs reconciling â€” pending. |
| **â³ PLAN (not started, now UNBLOCKED) â€” Volatile-state model: add raw H1/H4 DI + SMMA 1h/4h trend features** (Imtiyaz, 2026-07-13) | Confirmed on the 04:30 signal (both `H1_DI_diff=-19.79`/`H4_DI_diff=-17.01` AND `ts_trend_h1=-1`/`ts_trend_h4=-1` genuinely agreed bearish â€” not a fragile/divergent case) that `model_volatile.pkl`'s 17-feature list has neither raw ADX/DI nor the SMMA `ts_trend_h1/h4` features â€” it only sees momentum/EMA/slot stats, so it can't down-weight a signal that both HTF systems call bearish. **The VolHTFGate WFO A/B (row above) is now DONE â€” REJECTED (B<A), so this plan is no longer blocked, but note the gate's rejection + the fragile-vs-raw-ADX caveat found alongside it are a reason for EXTRA caution here: the underlying "counter-HTF is bad in Volatile" signal did not hold up OOS, so this feature-addition plan should not assume that premise â€” treat it as an open feature-engineering experiment, not a confirmed-edge implementation.** (1) add `H1_DI_diff`, `H4_DI_diff` (and consider `H1_ADX`/`H4_ADX`) + `ts_trend_h1`, `ts_trend_h4` to `VOLATILE_FEATURES` in `engine/features.py`. (2) Full retrain (not core-only) so `model_volatile.pkl` actually gets the new columns. (3) Check feature-importance output â€” confirm the model actually USES the new features (not just present-but-ignored). (4) Full stage-gate: 3-month screen â†’ 1-year â†’ WFO (leakage-guard-safe cutoffs this time, unlike 07-12's in-sample mistake) â€” compare Volatile-regime R/PF/DD vs current baseline. (5) Adopt only if WFO doesn't hurt Volatile regime's current +36.5R/PF 1.89 baseline. Related: [[project_htf_direction_architecture_rethink]] memory â€” this is the first concrete, scoped piece of that bigger architecture question. **Status: plan only, nothing implemented.** |
| **Feature-sweep: capture-efficiency tracking** âœ… DONE 2026-07-13 (night) | 3rd Fable-5 opinion (goal: find profitable features while capturing 10-20% of available move, not just +R): `run_feature_sweep.py` now parses `captured_pts`/`available_pts`/`efficiency_pct` from each backtest report, flags any feature where captured points drop >10% vs baseline even if R improved (catches "R up but capturing less of the move"), and writes 3 new columns to every tier's `*_SUMMARY.csv`. Fable-5's other point (HTF H1-flip exit as the bigger lever) checked against `config.py` â€” **already live** since 06-23/26/30, no action needed there. Detail: `docs/FIXES_CHANGELOG4.md` 2026-07-13 (night). |
| **Capture-audit refresh: 2.9% vs 5.7% explained** âœ… RESOLVED 2026-07-13 (night) â€” NOT a bug. Both `analyze_capture.py` (5.7%, 06-23) and `backtest_replay.py` (2.9%, current) compute "available path" identically. Real cause: `ratchet_tp_cap_pct` was 10.0% (near-unconstrained) at the 06-23 measurement, then tightened to 1.00% (06-26) and made regime-adaptive down to 0.8% in Volatile (06-27, `ratchet_tp_regime=True`) â€” both deliberate profit-optimizing choices (best in-sample R/PF). Proof: current `active_baseline` report exit-mix = 44/131 (34%) trades exit via TPCAP, capping profit at 0.8-2.0% regardless of further move. **Real trade-off, not fixable for free:** wide/no TP cap â†’ more path captured, worse R/PF; tight regime-TP â†’ less path captured, better R/PF (per existing 06-26/27 evidence). Recovering 10-20% capture would need a new dedicated wide-TP-vs-tight-TP A/B â€” not yet run, would need to re-litigate the 06-26/27 TP decision. Detail: `docs/FIXES_CHANGELOG4.md` 2026-07-13 (night). |
| **â³ PLAN â€” smart Exit-AI vs rule-based exits (4th Fable-5 opinion, 2026-07-13 night)** | Imtiyaz asked: could a dedicated exit-ML-model capture more move AND stay smart (not give back profit)? Fable-5's independent verdict, in priority order (detail: `docs/FIXES_CHANGELOG4.md`): **(1) pushback on the capture% metric itself** â€” "% of total path length (sum of all bar-to-bar moves)" is an ill-posed denominator (shrinks/grows with bar granularity); recommends switching to **per-trade MFE-capture ratio** (realized profit Ã· Maximum Favorable Excursion) as the real target, retiring the "10-20% of path" framing. **(2) Exit-AI is NOT the right first lever** â€” 3 cheaper steps come first: (a) a same-day "post-cap continuation audit" (measure how far price kept moving in-trade-direction after the 44 TPCAP-capped trades hit their cap, before the eventual HTF-flip â€” this alone tells us if there's real money left on the table); (b) **main recommendation: stop hard-closing at the TP cap â€” instead either partial-exit 50-70% at the cap and let the rest trail, or switch to a MUCH tighter trail (e.g. M15-line/0.05-0.08% buffer instead of H1-line/0.20%) at the cap-touch moment.** Fable's core insight: the TP cap's real job is "giveback insurance," not "profit ceiling" â€” trail-tightening gives the same insurance without capping the upside, so the R/PF-vs-capture conflict found earlier may be an artifact of the current binary (hard-close) design, not fundamental; (c) re-check whether the current single/regime TP-cap % itself is overfit to a thin 131-trade sample before trusting it further. **(3) If exit-AI is still pursued after (2):** keep it narrow â€” a binary gating classifier (p(continuation)) invoked ONLY at 2 decision points (cap-touch, HTF-flip-moment), never a free-running per-bar policy or RL agent (over-engineered, leakage-prone, unsupported by sample size). **(4) Biggest risk flagged: sample size** â€” entry model has ~98k bars, but an exit model's effective N â‰ˆ trade count (131) since in-trade bars are heavily autocorrelated; Fable says do not start exit-AI training below ~500-1000 trades. **(5) Labels:** triple-barrier method (LÃ³pez de Prado) â€” ATR-scaled favorable/adverse barriers over a forward window, features strictly â‰¤ t, trade-episode-level CV grouping (never split one trade's bars across train/test), purge+embargo at fold boundaries, evaluate via OOS total $ replay â€” never via classifier AUC alone. **Status: opinion only, nothing implemented. Recommended sequence: (a) post-cap continuation audit first â†’ (b) TP-cap-as-trail-tighten redesign + WFO A/B â†’ (c) switch north-star metric to MFE-capture â†’ (d) grow trade sample â†’ (e) only then consider exit-AI phase 1.** |

### ðŸŸ¡ àª¬àª¾àª•à«€ (REMAINING â€” leakage-guard follow-up, added 2026-07-13)
| # | Task | àªµàª¿àª—àª¤ |
|---|------|------|
| **Re-run 07-12 in-sample results** | ~30 result folders (`ob_redundancy_*`, `removed_feature_*`, `regimescore_*`, `rawmove_ab_*`, `individual_ab_*`, `combo_b3b4_*`, `inrange_sweep_*`) were produced BEFORE the guard existed â€” in-sample-contaminated. Re-run with a real `QGAI_TRAIN_CUTOFF` before the backtest start (guard now enforces this) before trusting any KEEP/REJECT decision drawn from them. |
| **Re-validate the already-committed B3-only prune** (commit `10fad5f`) | This was adopted live based purely on in-sample 1-month A/B (`individual_ab_B1-B4`, `combo_b3b4`), no WFO gate. Re-run clean (cutoff before backtest start) + WFO before trusting it stays the right call. |

### ðŸŸ¡ àª¬àª¾àª•à«€ (REMAINING â€” original live-conservatism concern, Fable-5's recommended next step, 2026-07-13 night)
| # | Task | àªµàª¿àª—àª¤ |
|---|------|------|
| **âœ… DONE 2026-07-13 (night) â€” win_prob calibration diagnostic built** | `engine/diagnose_win_prob_calibration.py` (NEW) + `Run_WinProbCalibration_TEST.bat` â€” uses the ALREADY-EXISTING 3-month WFO OOS trades (`volhtfgate_wfo_TEST_A_off/ALL_OOS_trades.csv`, 207 real executed trades â€” no new model inference needed, `win_prob` + realized `r_achieved` + the raw `f_H1_DI_diff`/`f_H4_DI_diff`/`f_ts_trend_h1`/`f_ts_trend_h4` features are all already in that file). For each trade, counts how many of the 4 HTF-direction signals agree with the direction actually traded â†’ buckets `aligned_strong` (4/4 agree) / `aligned_weak` (3/4) / `mixed_disagree` (â‰¤2/4), then compares **avg PREDICTED win_prob vs REALIZED win-rate** per bucket. A clear positive gap in `aligned_strong` (realized notably above predicted) would confirm systematic underconfidence exactly when ADX+SMMA agree â€” the concern that triggered this whole investigation. **Caveat noted in the report itself:** this dataset is EXECUTED trades only (already passed threshold) â€” it can show whether the model is honest about trades it takes, but can't directly prove good trades were wrongly SKIPPED; if a real gap shows up, Fable-5's Step 3 (shadow-simulating skipped bars too, for missed-profit $) is the next-more-expensive step, not a feature-architecture change yet. Read-only, no training, `py_compile` clean, bat checked for non-ASCII chars (none). Not run â€” Imtiyaz runs it on his own PC. **â³ NEXT: run the bat, read the gap per bucket.** |

### âœ… àª¥àªˆ àª—àª¯à«àª‚ (DONE â€” 2026-07-11)
| # | Task (àª•àª¾àª®) | àªªàª°àª¿àª£àª¾àª® |
|---|------------|--------|
| **in_range_phase REGIME-SWAP A/B FULL YEAR** REJECTED (2026-07-12) | Full-year A/B replay: A=`QGAI_REGIME_INRANGE=0` OFF vs B=`QGAI_REGIME_INRANGE=1` ON | **A OFF = +206.6R BEST**, B ON = +204.9R (`-1.7R`). Trades/WR/PF/DD same: 808 trades, 56.1% WR, PF 1.89, max DD 3.8%. Difference only in Volatile regime: A +84.0R vs B +82.3R. Runner rule says B >= A confirms; B < A means revert. **Decision: keep `QGAI_REGIME_INRANGE=0`; do not adopt regime-swap ON.** Results: `backtest/results/inrange_regimeswap_FULL_A_off/` and `backtest/results/inrange_regimeswap_FULL_B_on/`. |
| **ADX-Death WFO NO-VOLUME** âŒ REJECTED (2026-07-11) | 53-week OOS WFO (NO-VOLUME model): baseline + K3N4X1.0 + K3N4X0.3 | **Baseline (OFF) = +80.5R BEST.** K3N4X1.0 = +73.6R (âˆ’6.9R). K3N4X0.3 = +60.8R (âˆ’19.7R). ADX-Death filter hurts OOS profit â€” blocks profitable trades. Gate +444.7R nowhere near. Results: `backtest/results/wfo_adxdeath_novol_*_20260710/`. Bat: `Run_ADXDeath_WFO_Validate.bat`. |
| **Volume AUC comparison** (2026-07-11) | AUC effect of volume/tick_volume features on model | A (no volume) Test AUC 0.6167 baseline. B (+volume norm) 0.6164 (âˆ’0.0003). **C (+tick_volume raw) 0.6219 (+0.0052 best)**. D (+both) 0.6057 (âˆ’0.011 hurt). tick_volume raw = marginal AUC gain but WFO profit negative â†’ volume features stay EXCLUDED. Script: `engine/auc_volume_compare.py`. |
| **RAW-VOL feature** âŒ CLOSED (2026-07-11) | tick_volume raw feature â€” full evaluation complete | AUC: +0.005 marginal. WFO NO-VOLUME model (+80.5R) outperforms volume model. ADX-Death + volume combos all worse. **Decision: volume features (both raw + normalized) permanently excluded from model.** Remove `tick_volume` from `_MANUAL_PRUNE` comment "keep out" â†’ confirmed correct. |
| **ET1** â¸ï¸ PARKED (2026-07-11) | Entry-timing redesign â€” trend-following pullback entry (ATR-free) | **v1 BLOCK** â†’ REJECT (block only REMOVES trades, cuts winners). **v2 GENERATE** â†’ 96 signals fire but `max_open=1` â†’ 0 net new trades, 7 combos baseline-identical. **Nil impact under max_open=1.** Both flags OFF, live=baseline, reversible. Revisit only if `max_open=2` adopted or GEN gated to flat+SKIP only. Design: `docs/ENTRY_TIMING_REDESIGN.md`. |

### âœ… àª¥àªˆ àª—àª¯à«àª‚ (DONE â€” 2026-07-09)
| # | Task (àª•àª¾àª®) | àªªàª°àª¿àª£àª¾àª® |
|---|------------|--------|
| **Feature leakage fix** (2026-07-09, Imtiyaz flagged) | `corr_imp_ratio` PRUNED + `in_range_phase` H4 lookahead fixed | **`corr_imp_ratio`** (rank #28, 0.022): swing detection uses future bars (i+1,i+2,i+3 = 12h+ lookahead). AUC test: âˆ’0.014 test AUC (negligible) â†’ added to `_MANUAL_PRUNE` + removed from `RANGING_FEATURES`. **`in_range_phase`** (rank #1, 0.071): `get_range_features()` included incomplete H4 candle (~3.75h future M15 data). AUC test: removing = âˆ’0.074 (too valuable to drop). Fix: `searchsorted(datetime+4h)` â†’ only COMPLETED H4 candles. Fable-5 confirmed both leakage paths. Test bat: `Start/6_Test_Leakage_AUC.bat`. **âš ï¸ NEEDS RETRAIN + WFO-GATE** (now 35 features, honest `in_range_phase`). |
| **Signalâ†”Trade DECOUPLE** | Imtiyaz architecture: signal = pure engine (BUY/SELL/SKIP) àª¦àª°à«‡àª• bar, backtest àªœà«‡àªµà«àª‚; trade execution àª¨à«‡ signal àª¸àª¾àª¥à«‡ àª•à«‹àªˆ àª¸àª‚àª¬àª‚àª§ àª¨àª¹à«€àª‚; account àª¨àª¾ àª¹à«‹àª¯ àª¤à«‹àª¯ signal àª¬àª‚àª§ àª¨ àª¥àª¾àª¯ | `bridge_main.py` 11 log_signal sites àª¹àªµà«‡ real `signal` + àª¨àªµà«‹ `trade_action=` (EXECUTED/EXEC_FAILED/HOLD_IN_TRADE/BLOCK_*/MONITOR/NO_TRADE...). `bridge_data.py` àª¨àªµà«‹ `trade_action` column (CSV+SQLite+migration). 78.59%â†’SKIP bug fixed â†’ àª¹àªµà«‡ signal=BUY, trade_action=HOLD_IN_TRADE. Test: `Test_Decouple_Signal.bat` **10/10 PASS** (offline, live files untouched). Trade-logic UNCHANGED. Dashboard SIGNAL LOG àª®àª¾àª‚ `trade_action` colored badge àª‰àª®à«‡àª°à«àª¯à«‹ (EXECUTED/HOLD_IN_TRADE/BLOCK_*/EXEC_FAILED...). **NEXT: bridge + dashboard restart àª•àª°à«€ activate àª•àª°àªµà«àª‚.** |
| **Decision area = àª›à«‡àª²à«àª²à«‹ BUY/SELL signal** | Imtiyaz: signal box + AI summary + Market Intelligence àª®àª¾àª‚ latest SKIP bar àª¨àª¹à«€àª‚ àªªàª£ **àª›à«‡àª²à«àª²à«‹ àªªàª¡à«‡àª²à«‹ signal** (BUY/SELL) àªàª¨àª¾ àª¦àª°à«‡àª• param àª¸àª¾àª¥à«‡ àª¦à«‡àª–àª¾àª¯ | Backend `bridge_dashboard.py`: `_remember_last_trade_signal()` cache (persist `logs/last_trade_signal.json`, restart-safe); `write_dashboard` line ~508 àªªàª° `sig` àª¨à«‡ àª›à«‡àª²à«àª²àª¾ BUY/SELL àª¥à«€ freeze â€” àª†àª–à«‹ decision block (prob/market_structure/ev_r/risk_grade/ai_summary/market_intel) àªàª®àª¾àª‚àª¥à«€ derive àª¥àª¾àª¯ àªàªŸàª²à«‡ coherent. Live price/session/countdown `tick` àª®àª¾àª‚àª¥à«€ â†’ live àª°àª¹à«‡. Cached signal àªªàª° `signal_confirmed=True` + àª¨àªµà«‹ `signal_is_cached` flag. Frontend `dashboard.html`: ðŸ•’ last @ HH:MM hint. **Activation: bridge restart (backend).** |
| **SIGNAL LOG win% dim on SKIP** | Imtiyaz: SKIP row àªªàª° win% gold àª¨àª¾ àª¦à«‡àª–àª¾àª¯, SKIP-text àªœà«‡àªµà«‹ dim | `dashboard.html _liveSigRender`: gold àª«àª•à«àª¤ BUY/SELL â‰¥45% àªªàª°. Browser refresh. |
| **SIGNAL LOG: virtual entryâ†’exitâ†’move àª¦àª°à«‡àª• BUY/SELL àªªàª°** | Imtiyaz: log àª®àª¾àª‚ àª¦àª°à«‡àª• buy/sell àª¨à«‹ price move (àª¦àª¾.àª¤. 4076â†’4100 = +$24) àª¦à«‡àª–àª¾àªµà«‹ àªœà«‹àªˆàª â€” trade àªªàª¡à«àª¯à«‹ àª¹à«‹àª¯ àª•à«‡ àª¨àª¾ â€” àª…àª¨à«‡ exit price calc àª¦à«‡àª–àª¾àª¯ | Root: exit calc àªªàª¹à«‡àª²à«‡àª¥à«€ àª›à«‡ (`shadow_ledger.py` àª¦àª°à«‡àª• signal àª¨à«‡ live exit rules àª¥à«€ paper-trade àª•àª°à«€ entry/exit/R/pnl àª•àª¾àª¢à«‡; scheduler àª¦àª° 15min refresh; 821 signals). àª–à«‚àªŸàª¤à«àª‚ àª¹àª¤à«àª‚ display. Fix (**dashboard-only, engine untouched**): `dashboard.html _liveSigRender()` àª¹àªµà«‡ àª¦àª°à«‡àª• BUY/SELL àªªàª° shadow àª®àª¾àª‚àª¥à«€ inline `4076.00â†’4100.00 +$24.00 +2.5R TPáµ›` (green/red, dashed) àª¬àª¤àª¾àªµà«‡ â€” trade àªªàª¡à«‡ àª•à«‡ àª¨àª¾ àªªàª¡à«‡. Real trade close àª¥àª¯à«‹ àª¹à«‹àª¯ àª¤à«‹ extra `WIN/LOSS +$move REAL` solid chip àª…àª²àª—. **Activation: dashboard browser hard-refresh (bridge restart àªœàª°à«‚àª°à«€ àª¨àª¥à«€).** |
| **SIGNAL LOG: HOLD â†’ EXIT lifecycle** (2026-07-09, Imtiyaz idea â€” "buy hold exit / sell hold exit") | Log àª®àª¾àª‚ àª¦àª°à«‡àª• bar àªªàª° àª¨àªµà«‹ independent BUY/SELL/SKIP row àª†àªµà«‡, àª­àª²à«‡ àªàª• trade already àª–à«àª²à«àª²à«àª‚ àªšàª¾àª²àª¤à«àª‚ àª¹à«‹àª¯ â€” Imtiyaz àª¨à«‡ trade lifecycle story àªœà«‹àªˆàª¤à«€ àª¹àª¤à«€ (entry â†’ holding â†’ final result), rows àª¨à«€ noise àª¨àª¹à«€àª‚ | **Option A àªªàª¸àª‚àª¦ àª•àª°à«€** (Fable-5 second-opinion àª²à«€àª§à«‹ â€” Option B "live decision-logic àª®àª¾àª‚ HOLD" àª¸àª¾àª« àª¨àª¾ àªªàª¾àª¡à«àª¯à«àª‚: Signalâ†”Trade DECOUPLE architecture àª¨à«‡ undo àª•àª°à«‡, flip-mechanism àª¤à«‹àª¡à«‡, backtestâ‰ live parity àª¤à«‹àª¡à«‡ â€” rejected). **Implemented (dashboard-only, additive, engine/signals_all.csv àª…àª¡à«àª¯àª¾ àªµàª—àª°):** `dashboard.html` â€” `_loadShadow()` àª¹àªµà«‡ `shadow_trades.csv` àª®àª¾àª‚àª¥à«€ `exit_time`+`direction` àªªàª£ àªªàª¾àª°à«àª¸ àª•àª°à«‡, àª¦àª°à«‡àª• entry àª®àª¾àªŸà«‡ `[entry_time, exit_time)` "open window" àª¬àª¨àª¾àªµà«‡ (`_shadowWindows`). `_liveSigRender()` àª®àª¾àª‚ àª¨àªµàª¾ àª¹à«‡àª²à«àªªàª° `_holdWindowFor(bt)`/`_exitWindowsFor(bt)`: entry-exit àª¨à«€ àªµàªšà«àªšà«‡àª¨àª¾ bars àªªàª° ðŸ”’ `HOLD <dir> @<entry_price>` badge (dotted, dim) àª‰àª®à«‡àª°àª¾àª¯ â€” **raw signal (BUY/SELL/SKIP) hide àª¨àª¥à«€ àª¥àª¤à«àª‚**, àª¡àª¾àª¬à«‡ àªàª® àªœ àª¦à«‡àª–àª¾àª¯ (Fable-5 àª¨à«€ àªšà«‡àª¤àªµàª£à«€ àªªà«àª°àª®àª¾àª£à«‡, àª¨àª¹à«€àª‚àª¤àª° flip debug àª…àª¶àª•à«àª¯ àª¬àª¨à«‡); exit bar àªªàª° ðŸ `EXIT WIN/LOSS Â±R â† entry-time` badge. Node.js àªµàª¡à«‡ sandbox simulation (synthetic shadow+signal CSV) àª¥à«€ verify àª•àª°à«àª¯à«àª‚: BUY@10:00 â†’ SKIP@10:15 àª¬àª¤àª¾àªµà«‡ ðŸ”’HOLD BUY badge â†’ SKIP@10:30 àª¬àª¤àª¾àªµà«‡ ðŸEXIT WIN +1R badge â€” àª¬àª°àª¾àª¬àª° àªˆàªšà«àª›àª¿àª¤ narrative. Real trade (`real_executed=1`) àª¨àª¾ entries àª®àª¾àªŸà«‡ tooltip àª®àª¾àª‚ "REAL trade also placed" àª¦à«‡àª–àª¾àª¯. Multiple concurrent shadow trades (shadow ledger no max_open) àª¹à«‹àª¯ àª¤à«‹ àª¸à«Œàª¥à«€ àª¤àª¾àªœà«àª‚-àª–à«‚àª²à«‡àª²à«àª‚ window àªªàª¸àª‚àª¦ àª¥àª¾àª¯ (display simplification, ledger àª¨àª¹à«€àª‚). **Activation: dashboard browser hard-refresh (bridge restart àªœàª°à«‚àª°à«€ àª¨àª¥à«€).** |
| **SIGNAL box/AI SUMMARY = SKIP while LOG = BUY (Imtiyaz-flagged mismatch)** | SIGNAL box + ðŸ§  AI DECISION SUMMARY àª¬àª‚àª¨à«‡ SKIP àª¬àª¤àª¾àªµà«‡, SIGNAL LOG àª¨à«‹ àª àªœ bar BUY àª¬àª¤àª¾àªµà«‡ â€” àª›àª¤àª¾àª‚ EV +1.05R/Grade A/AI-summary votes àª¬àª§àª¾ BUY àª¨àª¾ àªœ (SKIP àª®àª¾àªŸà«‡ àª `--`/null àª¹à«‹àªµàª¾ àªœà«‹àªˆàª) | Live data àª¥à«€ root-cause confirm àª•àª°à«àª¯à«‹: `signals_all.csv` àª›à«‡àª²à«àª²à«‹ row `signal=BUY, trade_action=HOLD_IN_TRADE` (legitimate, block àª¨àª¹à«€àª‚); `dashboard.json` àª àªœ àª•à«àª·àª£à«‡ `signal_confirmed:false` àª›àª¤àª¾àª‚ `ev_r:1.05` (non-null â€” proof backend àª àª–àª°à«‡àª–àª° BUY àªœ decide àª•àª°à«àª¯à«àª‚). Root: `bridge_main.py`àª¨à«àª‚ intra-bar heartbeat write (àª¦àª° ~30s, bar close àªµàªšà«àªšà«‡) `core._last_signal` (already-decided) àª àªœ dict àª«àª°à«€ àª®à«‹àª•àª²à«‡ àªªàª£ hardcode `signal_confirmed=False` â€” frontend (`dashboard.html` signal box + `renderAISummary():1556`) àªàª¨à«‡ "gate-blocked" àª¸àª®àªœà«€ SKIP àª¬àª¤àª¾àªµà«‡, ~15 àª®àª¿àª¨àª¿àªŸ àª¸à«àª§à«€ (next bar close àª¸à«àª§à«€), page refresh àª¥àª¾àª¯ àª¤à«àª¯àª¾àª°à«‡ àª–àª¾àª¸ àª¦à«‡àª–àª¾àª¯. **Fix:** [bridge_main.py:361-364](../engine/bridge_main.py:361) â€” `signal_confirmed=bool(core._last_signal.get("signal"))` (hardcoded False àª¨à«€ àªœàª—à«àª¯àª¾àª). `_pre_pop_dashboard`àª¨àª¾ genuine startup-probe `False` calls àª…àª¡àª•à«àª¯àª¾ àª¨àª¥à«€. `py_compile` clean. Dashboard-display only, live trading logic àª…àª¡àª•àª¤à«àª‚ àª¨àª¥à«€. **Activation: bridge restart (backend Python àª«à«‡àª°àª«àª¾àª°).** |
| **SIGNAL box: SKIP â†’ HOLD when a real trade is already open+profitable** (2026-07-09, Imtiyaz â€” "i need hold instead of skip becuse already buy in profit") | Real bar-close SKIP (genuine, win_prob 39.26% < threshold â€” not the bug above) àª›àª¤àª¾àª‚ bot àª¨à«àª‚ real BUY position àª–à«àª²à«àª²à«àª‚+profit àª®àª¾àª‚ àªšàª¾àª²à«‡ àª›à«‡ â€” "SKIP" àª¶àª¬à«àª¦ "àª•àª‚àªˆ àª¥àª¤à«àª‚ àª¨àª¥à«€" àªœà«‡àªµà«‹ misleading àª²àª¾àª—à«‡ | **Display-only** (`dashboard.html`, engine/`signals_all.csv` àª…àª¡à«àª¯àª¾ àªµàª—àª°): àª¨àªµà«‹ `_openPos`/`_holdNow` check (`d.open_trades` àª®àª¾àª‚àª¥à«€ â€” àªªàª¹à«‡àª²à«‡àª¥à«€ dashboard.json àª®àª¾àª‚ àª®à«‹àª•àª²àª¾àª¯ àª›à«‡) â€” actionable signal SKIP àª¹à«‹àª¯ **àª…àª¨à«‡** real position àª–à«àª²à«àª²à«àª‚ àª¹à«‹àª¯ àª¤à«‹ SIGNAL box + AI DECISION SUMMARY àª¬àª‚àª¨à«‡àª®àª¾àª‚ headline **"HOLD <BUY/SELL>"** (cyan) àª¬àª¤àª¾àªµà«‡, tag àª®àª¾àª‚ `ðŸ”’ holding BUY +2.41R` (direction+profit_R, color green/red àªªà«àª°àª®àª¾àª£à«‡). Real SKIP with àª•à«‹àªˆ open trade àª¨àª¾ àª¹à«‹àª¯ àª¤à«‹ plain "SKIP" àªœ àª°àª¹à«‡ (unchanged). CSS: `.sig-big.HOLD`/`.sig-dir-block.HOLD` àª‰àª®à«‡àª°à«àª¯àª¾. Node.js sandbox unit-test: real-SKIP-no-trade â†’ "SKIP" âœ“, SKIP+open-BUY+2.41R â†’ "HOLD BUY" cyan âœ“. `signals_all.csv`/live trading logic àª¬àª¿àª²àª•à«àª² àª…àª¡à«àª¯à«àª‚ àª¨àª¥à«€. **Activation: dashboard browser hard-refresh (bridge restart àªœàª°à«‚àª°à«€ àª¨àª¥à«€).** |

### âœ… àª¥àªˆ àª—àª¯à«àª‚ (DONE â€” 2026-07-08)
| # | Task (àª•àª¾àª®) | àªªàª°àª¿àª£àª¾àª® |
|---|------------|--------|
| **ADX-death exit** âŒ REJECTED | Imtiyaz idea + Fable-5 design: K/4 TF ADX slopes â‰¤0 for N bars + profit â‰¥ XÃ—R â†’ exit | Code DONE. **18-cell sweep DONE (2026-07-09):** in-sample top-2 K3N4X1.0 +409.1R, K3N4X0.3 +404.7R. **NO-VOLUME WFO validation (2026-07-11):** 53-week OOS baseline (OFF) **+80.5R best**, K3N4X1.0 +73.6R (âˆ’6.9R), K3N4X0.3 +60.8R (âˆ’19.7R). **Filter hurts OOS â€” REJECTED.** Results: `backtest/results/wfo_adxdeath_novol_*_20260710/`. |
| **Ablation AUC study** | 10-test Clean-34 feature ablation (AUC impact, no model saved) | **DONE (2026-07-09).** Results: `data/ablation_results_clean34.json`. Bat: `Start/7_Ablation_10_Tests.bat`. Key: trend-signal BEST removal (AUC +0.013), tick_volume removable (+0.008), ALL OB/SR removable (+0.008), slot_win_rate KEEP (AUC âˆ’0.013). hmm_state NOT in main FEATURE_COLS (hybrid-only, no effect). **Feature removal = one-by-one with WFO per step â†’ see RUNNING "Ablation".** |
| **PART 2 composite REJECTED** | 10 raw ADX â†’ 5 tanh composites | WFO +405.6R vs +444.7R = âˆ’39R. Higher AUC but lower R â†’ "accuracy â‰  profit." Bats DELETED. |
| **max_open=2 REJECTED** | User caught R-unit measurement artifact | Fixed-lot 0.01Ã—2 = double risk. Dollar return at 3% total: max_open=1 beats max_open=2 (6.85M% vs 4.95M%). 95% same-direction overlap = correlated bet. |
| **Volume-exit DEAD** | Non-monotonic, tautological, broker tick_volume = noise | Conditional table: within each ADX-death bucket, volume adds nothing. Permanently closed. |
| **TP-sweep in-sample** | Wider TPs win: Rng2.8/Trn1.4/Vol1.0 | In-sample done. WFO validation pending (do AFTER ADX-death). |

### âœ… àª¥àªˆ àª—àª¯à«àª‚ (DONE â€” 2026-07-07 major session)
| # | Task (àª•àª¾àª®) | àªªàª°àª¿àª£àª¾àª® |
|---|------------|--------|
| **CTF-OFF** | `skip_counter_trend_fade` Trueâ†’False (LIVE) | Path-A live-parity BT: CTF-OFF **+384.5R vs +350.2R = +34.3R (+9.8%)**, WR +0.4pp, PF +0.20. CTF blocked 0/3-aligned 77%-WR edge. Reversible: `QGAI_CTF_FADE=1`. |
| **Feature PART 1** | drop 6 dead EA-combo features (41â†’35) + retrain | Static full BT first gave **+393.4R**; weekly-retrained WFO then gave **+444.7R = +51.3R (+13.0%) lift**, 51/53 positive weeks, worst -0.4R. New honest WFO baseline = +444.7R. |
| **FAB-S4** | vSL persistence (`vsl_persist.py`) | trailed vSL survives restart (was reset to entry). Verified live 4Ã— (4119â†’4142). Broker SL 3Ã—â†’1.5Ã—. |
| **FAB-S3** | live DD brake (`dd_brake.py`) PER-ACCOUNT | dd>10%â†’Â½/20%â†’Â¼/30%â†’halt. Enabled live. **Bugfix same-day:** global peak poisoned mirror accounts â†’ per-account (login-keyed) fix. |
| **FAB-S1** | reversal-entry gating (flag, default OFF) | reversal re-entry passes filter stack when `gate_reversal_entries=True`. |
| **FAB-S2** | news staleness check (`news_updater.py`) | startup banner if calendar stale; was false-positive (file OK through Dec 2026). |
| **FAB-H6/H8/H9** | replay-ADX as-of Â· checkpoint sig env+mtimes Â· ADX-gate live-wire | parity/integrity fixes (details FIXES_CHANGELOG4). |
| **FAB-M11** | picker prefers non-SKIP over higher-prob SKIP | prime-directive fix (live+backtest). |
| **FAB-M12/M14** | parity-gap doc table Â· config re-enable-trap cleanup | SMMA "PROVEN HARMFUL" comment; dead session keys marked. |
| **Dashboard** | config badges + Account-Health/Risk-State panels + Signal-log rebuild | per-account fill status, DD band, vSL $ risk, daily-SL headroom (Fable-5 review). `Rebuild_SignalLog.bat`. |
| **Master launcher** | `Start/0_START_ALL.bat` | one-click cold-start (data+chart+shadow+signal-log+bridge+dashboard, minimized). Training deliberately EXCLUDED (stays `3_Train_Models.bat`). |
| **Model-mismatch** | fixed (compositeâ†’raw restore) | PART 2 composite retrain + env-leak caused live train/serve skew; restored validated raw-36 (`_backup_part1_raw35`). Verified match. |

### âœ… àª¥àªˆ àª—àª¯à«àª‚ (DONE)
| # | Task (àª•àª¾àª®) | àªªàª°àª¿àª£àª¾àª® |
|---|------------|--------|
| P1 | Relabeled data àªªàª° model retrain | model 06-28, 2743 trades |
| P2 | WFO OOS â€” **regime-TP adopt** àª•àª°à«àª¯à«àª‚ | +266R / PF 3.35 / 60% WR (HTF, live-matched) |
| P2b | $10k 3% sim â€” Max DD | **REFINED 2026-07-03: real leak-free OOS max DD = 14.6%** (`wfo_asof_rel`, 723 tr, +393.9R, WR 63.2%, dynamic 3% compounding, stitched OOS curve; baseline `wfo_live_match_015` = 11.5%). NOT the feared 28-39%. Raw/un-braked (cross-week DD-brake not applied â†’ live brake keeps it lower). Caveat: every OOS month positive = optimistic; assumes backtest fills=live, real slippage/news can deepen it. â†’ 3% DD-tolerable; watch actual DD on demo. Script: scratchpad/oos_dd.py. |
| P3 | Regime-TP àª¨à«‡ live bridge àª®àª¾àª‚ wire | config-gated âœ… reversible |
| L1 | Full-history backtest 2022â†’2026 | **edge OOS confirmed** (2022-24 unseen, PF 2.8-3.5) |
| L4 | Open bugs **A + F** | fixed |
| L7 | Stale labels (ATR/counts/hybrid) | labels fixed |
| L8 | Deposit/withdrawal-aware equity | **safety fix** (false-trip àªŸàª¾àª³à«‡) |
| L9 | Complete signal log (`signals_complete.csv`) | àª¦àª°à«‡àª• candle + $/% @0.01 lot |
| L10 | `live_trades.csv` schema | corruption fixed |
| â€” | **Bug fixes** FÂ·GÂ·HÂ·IÂ·JÂ·K | àª¬àª§àª¾ fixed (backtest=live) |
| â€” | **Validation docs** | client `.docx` + `VALIDATION_RESULTS.md` |

### ðŸ”„ àª…àª¤à«àª¯àª¾àª°à«‡ àªšàª¾àª²à«‡ àª›à«‡ (RUNNING / NOW)

> **ðŸ§­ KEY FINDING (2026-07-12): the old +444R/+384R were LOOKAHEAD-INFLATED** (in_range_phase leak pre-07-09 + ADX leak pre-07-03, both now fixed). **Honest WFO baseline â‰ˆ +80R and it is TRUSTWORTHY** â€” full leakage audit (`docs/LEAKAGE_AUDIT_20260712.md`) verified ADX + trend-signal families are leak-free (drift 0.0000). So R must be raised by GENUINE signal, NOT by un-fixing leaks. Priorities below.

#### ðŸ¥‡ Priority track (2026-07-12, after leakage audit)
| P | Task | Why / detail | Effort | R effect |
|---|------|--------------|--------|----------|
| **P1** | âœ… CODE DONE 2026-07-12 â€” **DROPPED `corr_imp_ratio`** (chose drop over gate-fix: honestly-gated = 16h-stale near-useless; redundant with honest ts_trend_h4/h4_ADX/in_range_phase). 35â†’34 feat. **â³ awaiting retrain + WFO gate** (bat below). | Double leak: swing reads 3 future H4 (`iloc[i+j]`) + gate ~16h early. LOW impact. | small | ~neutral (cleans leak) |
| **P2** | âœ… CODE DONE 2026-07-12 â€” **`ob_strength` confirm `shift(-1)`â†’`shift(-2)`** (impulse candle fully closed before OB visible). **â³ same retrain+WFO.** | Partial-candle leak; 2 model features. Zones already safe. | small | tiny |
| **P3** | âœ… CODE DONE 2026-07-12 â€” **`dev_norm` â†’ expanding past-only z-score** (no future event releases). Unit-checked. **â³ same retrain+WFO.** | Global-stats leak; news only. | small | tiny |
| **P1-3 GATE** | âœ… NOT NEEDED SEPARATELY (2026-07-12) â€” P1 (corr_imp_ratio) already in `_MANUAL_PRUNE`, P2 (ob_strength shift-2) + P3 (dev_norm expanding) already in code. Fresh 33-feat retrain (`3_Train_Models.bat`) automatically includes all 3 fixes. No separate WFO gate bat required. | â€” | â€” | â€” |
| **RANGE** | âœ… REMOVED (config) 2026-07-12 (Imtiyaz) â€” `skip_range_phase_entry` Trueâ†’False. Was the #1 entry-stopper (~63% of actionable BUY/SELL on honest model), added post-hoc w/o a gate. **1-month A/B smoke (honest model): OFF = +8.9R / 63 tr / 60.3% WR / PF 1.95 vs ON = +0.9R / 29 tr / 55.2% / PF 1.45 â†’ OFF ~10Ã— better, WR UP.** Filter was blocking WINNERS. Confirms removal. Reverses old leaky in-sample (+10R ON). **â³ NEXT: `Run_Range_AB_Backtest.bat` full-year confirm, then WFO.** | small | **+8R (1mo smoke)** |
| **Filter #2 pre-news** | âœ… REMOVED 2026-07-12 â€” pre-news +0.05 penalty â†’ 0.0 (inference.py default). 1-month A/B = identical +8.9R/63tr (0 pre-news trades hit â€” rare). Philosophy-driven ("model over filters"), reversible env `QGAI_PRENEWS_PENALTY=0.05`. Full-year read unmeasured. | small | nil (1mo) |
| **Filter #4 early-discount** | âœ… STAYS OFF 2026-07-12 â€” 1-month A/B = identical +8.9R/63tr. Nil impact under max_open=1 (like ET1). Parked. | small | nil |
| **Filter #3 ratchet-line** | â›” DEFERRED 2026-07-12 â€” NOT a clean entry-filter A/B: "skip when no ratchet line" is tied to the whole ratchet-exit system (`_ratchet_on`); removing = no trailing SL = different strategy, not a filter toggle. Skip. | â€” | â€” |
| **Filter #1 min_win_prob** | â³ LATER (Imtiyaz: test #2/#3/#4 first) â€” lower regime thresholds (0.42-0.48 âˆ’0.05) = more trades, trust model more. Biggest lever. Build A/B after #2/#4. | small | TBD |
| **ðŸ§¹ FILTER CODE-CLEANUP** (Imtiyaz 2026-07-12) | âœ… DONE 2026-07-12 (per Imtiyaz â€” without waiting for range full-year) â€” deleted filter code, net âˆ’87 lines, git-reversible: (a) **RANGE** â€” `backtest_replay.py` range block â†’ `_range_block=False` const + `--no-range-skip` arg removed; `bridge_main.py` BLOCK_RANGE block â†’ const. Range config keys KEPT (dashboard/log-banner read them). (b) **#2 PRE-NEWS** â€” inference.py pre-news penalty collapsed to plain regime threshold + `QGAI_PRENEWS_PENALTY` gone. (c) **#4 EARLY-DISCOUNT** â€” inference.py block deleted (`_ed_disc=0.0` kept) + config keys removed + `QGAI_EARLY_DISCOUNT`/`QGAI_ED_*` gone. Downstream compound conditions + CSV/dashboard schema untouched. | small | â€” |
| **ðŸ› BUG-CHECK after filter removals** | âœ… CODE-LEVEL DONE 2026-07-12: 4 files syntax OK, imports OK, NO dangling refs (only REVERT comments), range cfg-key present (dashboard safe), early_entry_discount key gone. **â³ PARITY smoke:** `Run_FilterRemoval_Parity_TEST.bat` MUST = +8.9R/63tr (range_ab_TEST_OFF). Diff â†’ bug. | small | â€” |
| **RAW-MOVE feature fix** | âŒ REJECTED 2026-07-12 â€” raw `h4_move_pct`+`cum3_move_pct` tested both ways: single-backtest B +6.8R vs A +8.9R (WR 54.5% vs 60.3%) AND WFO ~5wk B +8.9R vs A +11.7R. Model did NOT learn/improve from raw in WFO either â€” added noise, not signal. Binary `in_range_phase` is cleaner. Removed from FEATURE_COLS; baseline model restored (`_backup_pre_rawmove_20260712`, 35-feat +8.9R). | small | neg (rejected) |
| **Per-model importance check** | âœ… DONE 2026-07-12 (Imtiyaz observation: "0.0000 in training importance â‰  useless â€” may matter in another model") â€” checked all 6 models (main/buy/sell/ranging/trending/volatile) for every current + PART-1-pruned feature. **Confirmed the hypothesis for 2 features**: `h4_h1_regime_score` = 0.0622 in VOLATILE (vs 0.0265 in main, was pruned on main-only 0.0), `h4_ranging_h1_neutral` = 0.0369 in BUY (0.0 in main). Others (`h4_trending_h1_aligned`, `trade_direction`) genuinely ~0 everywhere â€” stay pruned. | â€” | â€” |
| **in_range_phase REGIME-AWARE cutoff** | âœ… APPLIED 2026-07-12 (Imtiyaz) â€” 1-month threshold sweep (0.3-0.7%) showed per-regime optimum differs: Trending peaks 0.5% (+5.2R), Volatile peaks 0.6% (+8.5R), Ranging noisy (kept 0.5%). Global 0.5% was hiding this trade-off. Implemented in `inference.py` right after `hmm_state_name` is known (before model routing) â€” overrides `feat_dict["in_range_phase"]` using the regime-specific cutoff on raw `h4_move_pct`. Applies to BOTH live and backtest (same `LiveInferenceEngine.decide()`). No retrain needed (in_range_phase stays a binary model input). Master toggle: env `QGAI_REGIME_INRANGE=0` reverts to old global-0.5% behaviour. | small | +4.9R (1mo, sum of per-regime deltas) |
| ~~**PENDING: in_range_phase regime-swap FULL-YEAR + WFO confirm**~~ âœ… RESOLVED â€” this row is stale, superseded by the "in_range_phase REGIME-SWAP A/B FULL YEAR REJECTED (2026-07-12)" row above (DONE table, 2026-07-11 section): the full-year test WAS run, A (OFF) beat B (ON) by +1.7R, and the decision was "keep `QGAI_REGIME_INRANGE=0`." **ðŸ”´ But that decision was never actually wired into the code â€” `inference.py`'s default stayed `"1"` (ON) for 4 days** (nothing sets this env var anywhere except the A/B bat itself â€” confirmed via full-repo grep). Live bridge and every backtest run since 2026-07-12 (`OOS1Y-01` +338.5R, the 53-week WFO +282.7R, `FS67-01`, `FS67-02`) ran with the REJECTED ON setting active. **Fixed 2026-07-16** (as part of the unrelated train/serve-skew bug fix, item #1 above) â€” the default flip to `"0"` happens to also finally apply this 2026-07-12 decision. No further action needed on this specific item; the numbers above stand as historical record with this caveat attached, not as something to re-run for this reason alone (FS67-02 is being re-run anyway for the skew-bug reason). | â€” | DONE (via bug #1 fix) |
| **RESTORE 4 PART-1 features** | âœ… DONE 2026-07-12 â€” Individual A/B (1mo): B3 `h4_h1_regime_score` +14.8R (best), B4 `trade_direction` +12.3R, B1 `h4_trending_h1_aligned` +10.6R, B2 `h4_ranging_h1_neutral` +10.2R vs baseline +8.9R. **Combo B3+B4 = +8.8R (FLAT, interference).** Decision: **KEEP ONLY B3** (`h4_h1_regime_score`), drop B1/B2/B4 (overfeed â€” B3 already encodes B1+B2 as gradient score, B4 interferes). 35â†’36 feat. | small | +5.9R (B3 alone) |
| **ADX redundancy prune** | âœ… DONE 2026-07-12 â€” Individual ablation: D1 `h4_ranging_h1_extended` =baseline (B3 score=-1 covers it), D2 `M30_ADX` +15.3R (+0.5R), **D3 `H1_ADX` +18.0R (+22% gain, PF 2.55, DD 0.5%)**. All 3 confirmed redundant/overfeed. Dropped to `_MANUAL_PRUNE`. 36â†’33 feat. **â³ WFO gate pending.** | small | +3.2R (D3 alone) |
| **Hardcoded-threshold audit** | âœ… DONE 2026-07-12 â€” 16 hardcoded cutoffs in features; 15 already OK (binary pruned + raw in model, e.g. ADXâ‰¥19â†’raw H4_ADX). Only `in_range_phase` (0.5%) lacked a raw counterpart â†’ RAW-MOVE fix above. | â€” | â€” |
| **P4** | **ðŸŽ¯ REAL R-WORK (the actual upside)** â€” raise honest ~+80R by genuine signal: honest feature R&D, threshold/model tuning on the +80R baseline, entry/exit/risk logic. This is where PROFIT (prime directive) comes from â€” P1â€“P3 are correctness cleanups, not profit. | Audit shows no hidden leak props up +80R, so gains here are real & live-transferable. | large | **the real gain** |

| # | Task | àª¸à«àª¥àª¿àª¤àª¿ |
|---|------|--------|
| ~~**RESTORE+RETRAIN** (+444R recover)~~ âœ… RESOLVED 2026-07-12 | `corr_imp_ratio` restored 07-11 + retrained (honest in_range) â†’ WFO partial â‰ˆ +46R@30wk (tracks ~+80R, NOT +444R). **Proved +444R was leak-inflated, not corr_imp_ratio.** â†’ see P1 for the corr_imp_ratio decision. | DONE (finding logged; superseded by P1) |
| **`in_range_phase` LEGACY toggle** | `QGAI_INRANGE_LEGACY=1` reproduces old leaky behaviour for backtest-only (default honest). Legacy retrain bats exist. **Full legacy run = SKIP (pointless â€” fake number).** | Toggle kept for audits; live stays honest |
| **tick_volume ADD+TEST** | Add `tick_volume` raw to model â†’ retrain â†’ WFO gate. If profit drops â†’ properly remove (full WFO evidence). If profit holds/rises â†’ keep. | Currently pruned. Do AFTER corr_imp_ratio restore verified. |
| **Ablation** | Feature removal one-by-one with WFO test per removal. Ablation AUC done (10 tests). Order: T10 trend-signal first, then T2 tick_volume, T7 OB/SR, T8 news, T9 momentum. KEEP: slot_win_rate, h1 S/R dist. Each removal = retrain + WFO gate. | AUC results: `data/ablation_results_clean34.json` |
| **P3'** | DEMO forward-test (relabel+HTF+regime-TP, 3%) | àªšàª¾àª²à«‡ àª›à«‡ â€” **real proof** |
| **L2** | REBUILT trainset A/B | **model backup àª¥àªˆ àª—àª¯à«àª‚ âœ…**, full-history àªªàª›à«€ run |

### âœ… àª¥àªˆ àª—àª¯à«àª‚ (DONE â€” 2026-06-30 / 2026-07-01)
| # | Task | àªªàª°àª¿àª£àª¾àª® |
|---|------|--------|
| FF-RM | **REMOVE flip-fix / hysteresis code** (Divyesh, 2026-07-02) | DONE. Rejected on PROFIT grounds â€” every clean-parity test showed hysteresis LOWERED total R: June sweeps (âˆ’6.5/âˆ’7.2/âˆ’9.9R), yesterday 07-01 (+4.08Râ†’+1.26R), and **WFO true-OOS full year: baseline +360.1R vs hyst +314.2R = âˆ’45.9R (âˆ’12.7%)** despite dir_flips âˆ’75% (726â†’183) and flat WR/PF. It blocks profitable flips (esp. Trending). Removed from `config.py` (hysteresis_margin field), `bridge_main.py` (pick block), `backtest_replay.py` (env FF block + `import os as _os`); deleted helper scripts `flipfix_*.py` + all `Run_FlipFix_*.bat`. Result folders + BUFFER_015_BacktestVsWFO / BUFFER_FLIPFIX_WORKFLOW reports kept as record. Live = clean baseline max-prob pick (restart to load). |
| L5 | Buffer sweep (global) â€” `Run_Buffer_Sweep.bat` 0.10/0.15/0.20/0.25/0.30%, 1yr, 42-feat+forming-line+regime-TP, fixed-lot 0.01 | Ran 2026-06-30 (`backtest/results/bufsweep/buf_0.*.txt`). **0.15 best balance: PF 3.87, +430.70% net, Max DD 2.9%** (vs 0.20: PF lower, DD similar). **APPLIED to live 2026-07-01** â€” `config.py ratchet_buf_pct: 0.20â†’0.15` (reversible, old value in comment). âš ï¸ Regime-wise breakdown (best buffer PER Ranging/Trending/Volatile) not yet done â€” global sweep only; regime-adaptive buffer still open if wanted later. |
| Bug | **win_prob frozen 75+ min live (12:15â†’13:30) â€” inference.py silent stale-feed** | Imtiyaz flagged (WinProb stuck at 27%). Traced via `logs/signals_all.csv`: win_prob/state_prob/dir_prob/hmm_state bit-identical across 6 bars while price moved â€” `get_signal()`'s OHLC-merge staleness-guard silently failed to refresh `self.ohlc_df`, and the failure path was a bare `print()` invisible in `bridge.log`. **FIXED:** merge failures now also `log.error(...)`; added a `_ohlc_stale_bars` counter that alarms in bridge.log after 2 consecutive bars with no fresh candle merged. Needs bridge restart to load; not yet live-verified. |
| Live | **ðŸ”´ vSL close failed, retcode 10027 (AutoTrading disabled)** | Imtiyaz's live log showed both primary (VantageDemo) and secondary (VantageCentLive #29453256, REAL money) close orders rejected with 10027 = MT5 terminal AutoTrading OFF. **Not a code bug** â€” told Imtiyaz to enable AutoTrading in the MT5 terminal immediately (stops aren't actually protective until then). Recommend (not yet built): an explicit alert (not just an `[ERROR]` log line) when any close fails. |
| Bug | **Mojibake emoji in console (`Ã°Å¸â€™â€œ` etc.)** | `Start\1-5` bats never set `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8` (unlike `6_Shadow_Ledger`/`7_Refresh_Chart`/all backtest bats) â†’ Windows console fell back to legacy codepage. Display-only, no logic impact. **FIXED:** added both env-vars to all 5 `Start\*.bat`. Takes effect on next restart of each. |
| Check | **"Did Codex break something today?" (Imtiyaz asked)** | Audited every file with a 2026-07-01 mtime (`bridge_main.py`, `bridge_data.py`, `chart_data.py`, `chart_live_ohlc.py`, `config.py`, `backtest_replay.py`, `shadow_ledger.py`) â€” all compile clean, no unexplained/undocumented changes found. The win_prob-freeze bug traces to `inference.py` (not touched today) and the 10027 error is an MT5 terminal setting, not code. **No evidence of a Codex-introduced mistake.** |
| Dash | **dashboard.html fixes (Imtiyaz's own edits, Claude-verified)** | Duplicate `id="sig_history_chart"` (dead bottom panel) removed; mojibake header fixed; missing "MODEL" confidence box restored (`conf_model_val`). Verified: 0 duplicate IDs, div-balanced, JS syntax clean. |
| Fmt | **Win-prob / all-% displays â†’ 2 decimals everywhere** | ~35 spots across `dashboard.html`, `inference.py`, `bridge_main.py`, `bridge_dashboard.py`, `chart_data.py`, `signals.html`, `shadow.html`, `QGAI_Live_Panel.html` changed from `.0%`/`.1%`/`toFixed(0)`/`toFixed(1)` â†’ `.2%`/`toFixed(2)`, for every probability/rate/gauge % (win_prob, state/dir prob, win rate, slot WR, daily-loss/eq gauges, regime distribution, etc). Left non-% numbers (prices, $ amounts, R-values, spread pts, SVG coords, hours-ago) untouched. |
| Feat | **Stuck-trade manual-protect (Imtiyaz's spec, 2026-07-01) â€” ENABLED** | New: `bridge_session._close_position()` tracks consecutive close-failures per ticket (`_CLOSE_FAIL_COUNTS`). Past `stuck_close_fail_threshold` (default 3) it logs a loud repeating `ðŸš¨ STUCK` alert every retry (was: one `[ERROR]` line, easy to miss â€” this is what happened with #1519547791 today, retcode 10027 AutoTrading-off). `stuck_trade_hedge_enabled=True` (Imtiyaz turned it on 2026-07-01) â€” opens a protective opposite-direction hedge to freeze further P&L movement while the close keeps retrying; auto-unwinds once the original close finally succeeds. **Bug caught + fixed before it could bite:** first draft reused L13's `manual_hedge_magic` (202699) â€” but `bridge_manual.py`'s cleanup sweeps/closes EVERY position on that magic whenever its OWN floor/vSL/TP fires (magic-only filter, no comment check), which would've silently closed a stuck-trade's protective hedge out from under it the next time a manual trade's floor/vSL/TP happened to fire. **Fixed:** stuck-trade hedges now use a brand-new dedicated `stuck_hedge_magic` (202698), fully isolated from L13's pool â€” confirmed via code read (`bridge_manual.py _positions()` only matches its own magic). Bot keeps the ORIGINAL trade's own magic (202600) â€” MT5 doesn't allow re-tagging an existing position's magic, so "treat as manual" is a code-level bookkeeping flag only, confirmed OK with Imtiyaz. âš ï¸ Not yet DEMO-verified end-to-end (places a real order) â€” watch the first time it actually fires. |
| Bug | **vSL recovery fallback = hardcoded $15 guess, disconnected from real ratchet** (Imtiyaz flagged: leftover #1519547791 vSL showed 4016.42, doesn't match H1 line ~3975) | Traced via `bridge.log`: real vSL at open was 4012.35, trailed once to **4015.11** (22:30). Comments are a clean brand-tag by design (no embedded VSL/SL) and this trade has no broker-side SL (pure-virtual design) â†’ `recover_open_trades()` fallback (`bridge_core.py`) hits `broker_sl_dist=0` â†’ hardcoded `sl_dist=15.0` â†’ `entryâˆ’15.0=4016.42`, matching the observed value exactly (bug confirmed, not coincidence). **Root cause of why it kept resetting:** separately found `_close_position()` callers in `bridge_core.py` were doing `del self.virtual_trades[ticket]` **unconditionally** after every close attempt â€” even on FAILURE â€” so the moment a close failed once, the trade silently dropped out of live vSL monitoring for the rest of that session (contradicting the "bot will keep retrying every check" alert text) and only ever got picked back up via `recover_open_trades()`'s lossy fallback on the next restart (08:30/09:25/15:21 today). **FIXED (2026-07-01):** `_close_position()` now returns True/False (True = confirmed closed); all 5 call sites in `bridge_core.py` only `del` the VirtualTrade on True â€” a failed close now correctly keeps retrying every tick with the REAL vSL intact, no restart needed. Real vSL-persistence-across-restart (so recovery never needs to guess) still NOT done â€” lower priority now that the trade stays tracked live without restarting. |
| Bug | **bridge_main.py heartbeat log â€” mojibake heart emoji (Imtiyaz's spec: fix ONLY this, nothing else)** | Imtiyaz flagged one broken heart emoji in the heartbeat log line (`ðŸ’“ heartbeat â€” ...`, the one Codex apparently introduced). Investigating turned up ~680 MORE mojibake instances throughout the rest of the file's log messages (pre-existing, unrelated) â€” a full-file sweep was done first, but Imtiyaz clarified he only wanted the ONE heartbeat-line instance touched, not the rest. **Reverted the full sweep**, re-applied the fix to ONLY `bridge_main.py:334-335` (the `_hb_state` string + the `log.info(f"ðŸ’“ heartbeat â€” ...")` line) â€” verified via scan that these are the ONLY 2 lines in the file using clean (non-mojibake) emoji/dash chars now; everything else intentionally left as before. `py_compile` clean. |
| Feat | **backtest_replay.py checkpoint/resume (Imtiyaz's spec, 2026-07-01)** | `_checkpoint_pkl` existed but was dead/unused code (no save or load anywhere) â€” a stopped/interrupted backtest lost ALL progress, had to restart from bar 0. **Built:** saves state (equity, open trades, trades/signals so far, daily-loss tracking) every 500 bars AND on Ctrl+C (flag-checked at the next bar boundary, not exception-based, so it can't corrupt a half-written record). Checkpoint is keyed by a full config signature (date range, risk%, buffer%, TP-regime, all ratchet/filter flags) â€” a checkpoint is ONLY ever reused for the byte-for-byte SAME config, same paranoia as the WFO-cache Bug H precedent (never silently resume into a mismatched run). New `--no-resume` flag forces a clean restart. Auto-deletes the checkpoint on successful completion. Confirmed the engine has no cross-bar online-learning state in replay mode (no `.fit()`/partial_fit calls found), so skipping already-done bars on resume is behaviorally identical to a full run. âš ï¸ Could not get an automated `py_compile` check this session (bash sandbox mount stuck serving a 3+ hour stale cached copy of the file, confirmed via `stat` mtime â€” known documented issue) â€” verified instead via full manual line-by-line Read-tool review of every edited section + docstring-balance check. Should be spot-checked on the NEXT backtest run (current running full-year backtest is unaffected â€” already loaded the old code into memory). |
| Bug | **backtest_replay.py console looked frozen/blank during long runs** | Imtiyaz flagged the console showing nothing for long stretches. Root cause: `sys.stdout`/`stderr` were wrapped in a plain `io.TextIOWrapper` (no `line_buffering`), so `print()` output sat in Python's internal buffer and only flushed once it filled or the process exited â€” a long backtest LOOKED stuck even while working correctly. **FIXED:** added `line_buffering=True` to both wrappers + `flush=True` on the progress print, progress interval tightened 500â†’100 bars (with a running % complete), and `PYTHONUNBUFFERED=1` added to both `Run_Live_Buffer_015_CSV.bat`/`_TEST.bat` as a belt-and-suspenders fix for Windows console pipe buffering. |
| Feat | **Graduated stuck-trade excess-hedge, 3%â†’6% risk stretch (Imtiyaz's idea, 2026-07-01) â€” built, OFF by default** | New `bridge_session._stuck_risk_hedge()`: instead of freezing the FULL lot the instant a stuck trade's close fails (old `_place_stuck_hedge`, still available), let risk stretch from `risk_pct` (3%) up to `leftover_risk_cap_pct` (6%, new config) and hedge ONLY the excess lot once **unprotected slippage** (price moved past the trade's REAL vSL â€” passed in from the live `VirtualTrade`, not reconstructed â€” while close keeps failing) pushes risk past that stretched band; tops up incrementally if slippage keeps growing, never exceeds `pos.volume`. Reuses L13's `_contract_size`/excess-hedge math pattern (`bridge_manual.py`). Gated by new `leftover_excess_hedge_enabled` (default **False**) â€” takes priority over `stuck_trade_hedge_enabled`'s full-lot hedge when ON. Depends on the retry-loop fix above (needs the trade to stay live-tracked to keep re-evaluating). âš ï¸ Not yet enabled or tested â€” Imtiyaz to confirm before flipping the flag. |

### âœ… àª¥àªˆ àª—àª¯à«àª‚ (DONE â€” 2026-06-29)
| # | Task | àªªàª°àª¿àª£àª¾àª® |
|---|------|--------|
| L1b | Full-history **GLOBAL vs REGIME** TP compare (2022â†’2026, HTF+CTF, 0.01 lot) | **Regime wins:** PF 2.35â†’**2.47**, WR 59.2â†’**59.9%**, Total **+676â†’+708R**, same DD 1.7%, ~47/50 months green incl. unseen 2022-24. Results: `results/signal_log_full` (global) vs `results/fullhistory_regime` (regime). |
| P3âœ“ | regime-TP confirmed LIVE-wired | `ratchet_tp_regime=True` (config) + `bridge_core.py:170`. Rng 2.0/Trn 1.0/Vol 0.8. |
| ðŸ”´ L8-bug | **balance-flow FALSE daily-SL halt** (Anisa flagged via live log) | FIXED: `_net_balance_flow_today` used LOCAL time â†’ counted LIFETIME deposits ($906k) as today â†’ equity looked $68k â†’ halt all day. Now broker-time filter + 50% safety guard. (BUG_LOG 06-29.) |
| Bug | **offline-closed trades blank in signal log** | FIXED: `preload` now calls `write_outcome` â†’ backfills WIN/LOSS for trades closed while bridge OFF. |
| Bug | signal-log **duplicate rows** (same bar 2-3Ã—) | FIXED: dedupe guard in `log_signal` (one row/bar+mode); 44 dup rows cleaned. |
| L9 | **Complete signal log** (full-history backtest + live, $ move) | `build_signal_log.py` rewritten â†’ merges regime full-history (every bar, move) + live â†’ `logs/signals_complete.csv` (97,322 bars). Dashboard reads it (history+live merged, live overrides). Bat: `Run_BuildSignalLog.bat`. |
| L11 | startup **gap-backfill** (overnight signals â†’ dashboard) | `_overnight_replay` now logs missing bars (mode=BACKFILL) â†’ dashboard shows overnight history. Resume-prompt was already built (config-gated). |
| Dash | **signal log overhaul** | one complete log (date+time sorted, price, win%, regime, H4-RANGE, BW%, lot, WIN/LOSS REAL, $ move, equity, reason). Removed dup Signal-History table + SLOT DISCOVERY panel; kept chart. equity/move columns added to `log_signal`. |
| L13 | **Manual-trade Manager** (Anisa spec) | BUILT + ENABLED on DEMO (`bridge_manual.py`, config-gated). **Final design (approach A, combined vSL):** combines ALL manual trades (magic 0) into ONE net position (sum lots, vol-weighted avg entry) â†’ ONE **ratcheting vSL** on the 2-SMMA line (HTF/H1), trailed as a **VISIBLE broker SL on every leg**; breach â†’ close ALL; **SEPARATE 3% risk pool** (`manual_risk_pct=3`, independent of bot's `risk_pct=3` â†’ 3%+3%=6% total) broker-SL backstop + **excess-hedge** if combined lot > 3%-equiv; **target-TP** (`manual_target_tp_pct=2%`) â†’ close all; flip-hedge REMOVED (vSL handles reversal). L8-isolates manual P&L from the bot's daily ratchet. Bot entry-guard counts only magic 202600 â†’ manual trade does NOT block a same-direction system trade (room to trade). **DEMO (primary) only** â€” cent extension rejected (would conflict with mirror-trading). Config: `manual_manager_enabled=True` (demo test). Verified live: detects existing trades, sets 3% SL + vSL. |
| Cfg | accounts | Added **Vantage CENT LIVE 29453256** (secondary, XAUUSD.pc, pass to fill); **disabled TradeQuo 125926628**. |
| L11+ | **Resume-prompt â€” REMOVED (Anisa, 06-30)** | Built + enabled, but it fired on the first NEW bar (loop), not the exact startup moment â†’ felt like "asking while running." Anisa removed it: `resume_prompt_on_start=False`. Reason: the bot now MANAGES manual trades, so the user just opens a trade manually when wanted (bot handles it) â€” no need to ask the bot to take a signal. Bot auto-trades its own signals. Code stays (config-gated off). |
| Feat | **Feature removals + RETRAIN** | (1) `ts_line_dist_pct` removed (was rank #2). (2) `vol_spike` removed completely. Retrained 23:22 â†’ **44â†’43 features**. AUC **0.6791â†’0.6881** (held); SELL test AUC **0.7557** (WR 67%). HTF-align importance jumped (h4_h1_regime_score 0â†’0.0329, h4_trending_h1_aligned #2) â€” model now weighs HTF trend. âš ï¸ **run WFO** before trusting live. REVERT: delete `_MANUAL_PRUNE` line + restore vol_spike + retrain. |
| EMA200 | **EMA200 S/R / exit / entry â€” INVESTIGATED, no change** | M15 EMA200 = decent short-term S/R (~80% bounce/2h). Exit/tighten â†’ cuts winners (R âˆ’12%) âŒ. Cross â†’ no reversal edge âŒ. Hard entry filter â†’ misses big moves (Anisa declined) âŒ. KEY: "SELL below EMA" = worst (39.5% win) = bottom-chasing confirmed. Keep EMA200 as SOFT model features (already in the 43). |
| L7b | **Vestigial code remove â€” DONE** | dead `bridge_risk` (PBE/partial/BE/smart-exit) removed; **ATR removed completely** (safe-subset + rest, bot stopped): bridge_main atr20_pct compute, inference vol_regimeâ†’constant + move-model fixed 0.2, train_move_model fixed 0.2, dashboard labels. ADX-internal atr14 kept (indicator math). SQLite/CSV `atr20_pct` column LEFT nullable (logs 0 â€” drop = migration risk). |
| Dash | **Stale TP/SL/ATR labels FIXED** (Anisa flagged) | header TPâ†’regime cap, SLâ†’Ratchet, ATR(info) removed; `atr_mult` dropped from backend. `dashboard.html`+`bridge_dashboard.py`, 0 nulls. |
| BugChk | **4-round bug-check (Anisa, 06-30)** | Found + fixed the only real issue: **stale RUNNING CONFIG display** â€” printed PARTIAL/TRAIL/BE/SMART-EXIT + "TP cap 1.0%"/"maxrisk 1.2%" as active, but those are removed (L7b) / regime-TP+HTF actually used. Now shows pure-ratchet + regime-TP + HTF-forming + %Â·line buffer. (bridge_main.py:233-249). Feature count OK (41+hmm=42). No functional bug. Minor edges noted: manual vSL not persisted on restart; manual buf fixed-vs-%Â·line. |
| Manual-vSL | **Manual SL â†’ PURE VIRTUAL + indicator-match (Anisa, 06-30)** | No broker SL on the terminal (don't expose the stop to the market). bridge_manual: removed all `_set_sl` calls; vSL tracked internally + logged `ðŸ”¼ [VIRTUAL]`; bot closes ALL on breach (vSL/floor) â€” tracked like the bot's own trades, combined. **Buffer now = 0.20%Â·LIVE line** (was fixed avgÂ·0.20%) â†’ fully matches the chart indicator + bot. Line uses forming H1 (via get_htf_state). Floor stays entry-based (risk cap). âš ï¸ bot OFF = no protection (explicit). 0 nulls, verified. Restart to apply. |
| L13-fix | Manual mgr **line-independent floor-breach close** | bridge_manual.py:157-169 â€” before `if line:`, if price past the 3% floor â†’ close ALL manual + hedges (ðŸ”»). Enforces the cap even when the ratchet line is unavailable. Read-verified, 0 nulls. Effect on restart. |
| EMA200-cut | **Keep ONLY price_vs_ema200** (Anisa, 06-30) | Removed `ema200_dist_abs` (rank-37) + `above_ema200` + `near_ema200` via `_MANUAL_PRUNE` + cleaned computations/loops; `price_vs_ema200` kept. **RETRAINED 2026-06-30 10:17 â†’ 42 features** (verified: price_vs_ema200 in, 3 out). AUC **0.6881â†’0.6807** (tiny drop, still > original 0.6791). Bot restart-safe (42-feat). re-WFO pending. |
| WFOâœ“ | **43-feat retrain OOS VALIDATED â†’ KEEP** | 2026-06-30 `wfo_results` (global-TP): **+255.4R / 41 wks / 38 green (93%) / +6.23R-wk / maxDD âˆ’3.0R**. OLD 44-feat regime-TP +266.2R (globalâ‰ˆglobal). AUC 0.6791â†’0.6881. ts_line_dist_pct + vol_spike removal = **harmless**, model held â†’ KEEP. Optional `Run_WFO_TPREGIME.bat` for exact regime match. |
| vSL-parity | **backtest_replay parity for vSL change** | 2026-06-30: backtest now matches live â€” forming-H1-line (vf=bar-open when `ratchet_htf_forming`, lookahead-safe) + trail buffer = 0.20%Â·line. Trade carries `ratchet_buf_pct`. 0 nulls, Read-verified. â†’ WFO/backtest now faithful to live config. |
| vSL-live | **vSL trails the LIVE H1 line + %-buffer** (Anisa, 06-30) | (1) `ratchet_htf_forming=True` â€” uses the FORMING (current) H1 bar's line = matches the chart indicator's live value (3979.55, not last-closed 3988.03) â†’ no hourly lag, less profit give-back. `bridge_ratchet.get_htf_state` includes the forming bar + skips the cache. (2) trail buffer now = **0.20%Â·line recomputed per bar** (bridge_risk:105), not fixed-$-from-entry. ENABLED on demo. âš ï¸ backtest parity + WFO pending (see REMAINING vSL-parity) before real money. |
| Bugs | **A Â· F Â· B Â· E resolved; C still open (corrected 2026-07-01)** | A (secondaries flatten on daily-SL) âœ… Â· F (backtest_replay HTF config-aware) âœ… Â· E (UTF-8 wrapper) âœ… Â· B âœ… (open_time reconstructed on restart â€” still used by `bridge_dashboard.py:259` for elapsed-time display, NOT moot) Â· **C still ðŸ”¶ open** (SYMBOL not refreshed after failover; dormant since MT5_PRIMARIES unset â€” was wrongly marked N/A here). **D open** (subprocess refactor, being investigated 2026-07-01) â€” M fixed, see below. |
| M | **Bug M fixed (2026-07-01)** | `run_wfo.py --trail-mode` default changed `"line"` â†’ `None`; forward guard changed to `if args.trail_mode is not None`. No flag â†’ follows `backtest_replay.py`'s own config-aware default (htf today, matches live) same as before, now correct-by-design not accidental. Explicit `--trail-mode line` now genuinely forces literal M15-line mode (previously silently ignored and ran htf instead). `py_compile` clean. |
| L9b | Signal-log panel | `QGAI_Live_Panel.html` (localhost:8000). |
| L10b | Live Periods panel (Today/Week/Month/Year) | same panel. |

### âœ… àª¥àªˆ àª—àª¯à«àª‚ (DONE â€” 2026-07-02/03: HMM v3 + audit FIX-1)
| # | Task | àªªàª°àª¿àª£àª¾àª® |
|---|------|--------|
| HMM-DI | **HMM "Volatile" mislabel â€” v3 `rel` DEPLOYED (2026-07-03)** | 3 variants A/B'd WFO-gated: spec reject (degenerate 92% Trending), leak-world rel +481.7R â‰ˆ baseline; **honest (as-of) A/B: legacy +407.6R vs rel +393.7R = tie (paired t=âˆ’0.69), rel DD âˆ’26% (5.2R vs 7.0R) + 0 negative weeks â†’ Divyesh chose rel.** Deploy verify: **ALL CHECKS PASSED** â€” flat 07-02 window 18 Ranging/4 Trending/**0 Volatile**, stability trainâ‰ˆfull (45/35/20). Bonus: honest data àªªàª° hmm_state importance 0â†’0.0305 (#6). Revert: `_backup_pre_hmm_v3` + `.bak_preasof_20260703_104235`. |
| FIX-1 | **Audit Fix 1 â€” intra-bar HTF lookahead leak REMOVED (2026-07-03)** | `regen_adx_asof.py` (as-of = live-updater semantics, validated err=0.0) **APPLIED** to adx_merged; `mt5_data_updater.py` also as-of convention (future updates consistent). Leak drift measured: M30 mean 0.28/max 12.8, H1 0.45/11.5, H4 0.58/10.1 ADX pts (M15=0 âœ“ sanity). Leak-inflation ~15-18% àªªà«àª·à«àªŸàª¿ (483â†’408 legacy). **àª¨àªµà«‹ HONEST baseline = wfo_asof_rel +393.7R** â€” àª¹àªµà«‡ àªªàª›à«€àª¨à«€ àª¦àª°à«‡àª• àª¸àª°àª–àª¾àª®àª£à«€ àª†àª¨à«€ àª¸àª¾àª®à«‡; àªœà«‚àª¨àª¾ +483.1R/+481.7R àª†àª‚àª•àª¡àª¾ retired. |

### ðŸŸ¡ àª¬àª¾àª•à«€ (REMAINING â€” parked / pending)

#### â–¶ TOP NEXT (2026-07-07, priority order â€” Fable-5 ranked)
| # | Task | àªµàª¿àª—àª¤ |
|---|------|------|
| ~~**RAW-VOL retrain**~~ âŒ CLOSED 2026-07-11 | `tick_volume` raw feature â€” fully evaluated | AUC: +0.005 marginal (Test 0.6219 vs 0.6167). WFO NO-VOLUME model +80.5R beats volume model. ADX-Death+volume combos all worse. **Volume features permanently excluded.** Pre-tick_volume model backup: `data/models/backups/models_PRE_TICKVOL_20260709_1105/final/`. |
| ~~**PART 2 decision**~~ âŒ REJECTED 2026-07-07 | ADX 10-raw â†’ 5-composite consolidation | **FULL WFO = +405.6R vs +444.7R = âˆ’39R (âˆ’8.8%). FAILED the gate.** Composite lost per-TF info the raw features carry (AUC 0.705 was higher but total R lower â€” accuracyâ‰ profit). 52/53 positive weeks (good stability) couldn't offset the R loss. Fable Pâ‰ˆ30% correct. **DECISION: keep PART-1 raw-36 (live). Never set `QGAI_ADX_MODE=composite`.** `adx_fs_div` late-entry lever was alive but didn't save total R. Composite model discarded. |
| **FIX-3 parity** (Fable's #1, REDEFINED 2026-07-08) | backtestâ†”bridge_core EXIT-logic parity | Reversal-close TESTED = not the gap (overlap 13.6â†’15.2%). The "12% overlap" is a SHADOW-ENGINE ARTIFACT â€” `shadow_ledger.py` has no max_open (154 entries â†’ 44 when locked, vs backtest 66). **+444.7R is trustworthy (pessimistic if anything â€” backtest under-trails 0.6R/trade).** NEXT: code-diff `bridge_core.py` (live truth) trail/flip/TP vs `backtest_replay.py`, make backtest match live exactly, re-run. Key Q: does live trail unconditionally or regime-gated? Drop shadow-overlap as a metric. Keep demo running (final entry-side arbiter). |
| **max_open=2** (only path to +50% goal) | 2 concurrent positions | Research +347R in-sample but 2Ã— exposure/DD â†’ needs dynamic-risk demo validation AFTER FIX-3. Not a switch-flip. |
| **Goal reality** | +20-50% R (target +420-525R) | PART-1 already banked +13% (+444.7R WFO). No single safe lever reaches +50%; only max_open=2 does, and only responsibly after FIX-3. Honest ceiling without it â‰ˆ +10-15%. |

#### ðŸš¨ Fable-5 SYSTEM AUDIT 2026-07-07 â€” 16 findings (fix after Path A backtest)

**SEVERE (live-critical â€” Path A àªªàª›à«€ àª¤àª°àª¤):**
| # | Task | àªµàª¿àª—àª¤ |
|---|------|------|
| ~~**FAB-S1**~~ âœ… DONE 2026-07-07 (flag-gated, default OFF) â€” reversal re-entry now passes full filter stack when `gate_reversal_entries=True`; close-on-opposite backtest port still pending (see M12). | ðŸš¨ **Live reversal path bypasses all entry filters + backtest doesn't model reversal** | `bridge_main.py:500-509` opposite-signal handler bàª§àª¾ range/CTF/pullback/SMMA blocks àªªàª¹à«‡àª²àª¾àª‚ àªšàª¾àª²à«‡. `bridge_core.py:543-601` `handle_opposite_signal` â†’ `execute()` direct, zero filter check. Backtest àª®àª¾àª‚ reversal code àª›à«‡ àªœ àª¨àª¹à«€àª‚. **àª¸à«Œàª¥à«€ àª®à«‹àªŸà«àª‚ FIX-3 12%-overlap gap explanation.** Fix: (a) reversal path àª¨à«‡ same gate stack àª®àª¾àª‚àª¥à«€ àªªàª¸àª¾àª° àª•àª°à«‹, àª…àª¥àªµàª¾ (b) `handle_opposite_signal` àª¨à«àª‚ backtest port àª•àª°à«‹; àª¦àª°à«‡àª• reversal separately log àª•àª°à«‹ measurement àª®àª¾àªŸà«‡. |
| ~~**FAB-S2**~~ âœ… DONE 2026-07-07 (FALSE POSITIVE + defensive check installed) | ðŸš¨ **News calendar DEAD 2026-05-15 àª¥à«€ (~7 weeks silent)** | `news_all_2024_to_now_pure_cleaned.csv` last event = May 15. **àª•à«‹àªˆ auto-updater àª¨àª¥à«€.** `mins_to_next_3star=240` (pegged), `is_pre_news`/`is_post_news=0` àª¹àª‚àª®à«‡àª¶àª¾ â†’ pre-news +0.05 threshold bump OFF, news-model routing OFF. Bot NFP/CPI àª®àª¾àª‚ 0.42 Volatile threshold àªªàª° trade àª•àª°à«‡. Feature-distribution drift (training vs live) àªªàª£ silent. Fix: automated weekly calendar pull + startup/hourly staleness assertion ("newest future event < now â†’ ERROR banner + optional trading pause"). |
| ~~**FAB-S3**~~ âœ… DONE 2026-07-07 (`engine/dd_brake.py` NEW + `calc_lot` wired; config `enable_live_dd_brake` default OFF â€” turn ON for real capital) | ðŸš¨ **DD brake live code àª®àª¾àª‚ EXISTS àª¨àª¥à«€** | `grep dd_brake` â†’ àª®àª¾àª¤à«àª° `backtest_replay.py:471,937` hit. Live risk = per-trade 3% + daily 9% only; NO peak-equity tracking anywhere. `TASKS.md` P2b's "live brake keeps it lower" = **false**. Multi-day losing streak = full 3%/trade indefinitely compound. P2b's 14.6% DD lower bound only. Fix: `bridge_core.execute()` / `calc_lot()` àª®àª¾àª‚ peak-equity tracking + 10/20/30% scaler implement. |
| ~~**FAB-S4**~~ âœ… DONE 2026-07-07 | ðŸš¨ **Disaster SL = 3Ã— vSL + restart trailed stop entry-level àªªàª° reset** | `bridge_core.py:215/221` broker_sl = vSL_dist Ã— 3.0. `bridge_core.py:626-637` recovery regex `VSL=` àª¶à«‹àª§à«‡, àªªàª£ comment àª¹àªµà«‡ "QuantEdge AI | {phase}" (line 224-225) â†’ **àª¹àª‚àª®à«‡àª¶àª¾ fallback broker_sl/3 = entry-level vSL**. `pos.sl==0` àª¤à«‹ invents `sl_dist=15.0`. Restart while +2R trailing â†’ vSL entry àªªàª° snap back â†’ locked profit àª—à«àª®; bridge death â†’ àª®àª¾àª¤à«àª° 3Ã—-wide broker SL. Fix: per-ticket vSL state SQLite àª®àª¾àª‚ persist àª•àª°à«‹, restart àªªàª° restore; broker SL â‰¤1.5Ã— tighten àª•àª°à«‹. |
| **FAB-S5** â¸ï¸ DEFERRED (profit tradeoff â€” do NOT silently flip) | ðŸš¨ **HTF forming-bar line/flip: live â‰  backtest (root of TRAIL 49% vs 11%)** | Live `bridge_ratchet.py:96-106` FORMING H1 bar àªœà«àª (flip appears/vanishes intra-hour, M15 close àªªàª° evaluate). Backtest `backtest_replay.py:339-353` COMPLETED bar mapping (flip bar-open àª¥à«€ known â€” mild lookahead, line stable). Live unconfirmed forming flips àªªàª° exit; backtest confirmed flips àªªàª° "hour early" exit. Entry SL sizing àªªàª£ diverge. Config comment àªªà«‹àª¤à«‡ "needs backtest parity + WFO before live" àª•àª¹à«‡àª¤à«‹ àª¹àª¤à«‹ â€” never done. Fix: true forming-line replay build àª•àª°à«‹ (H1 SMMA per M15 sub-bar recompute) OR `ratchet_htf_forming=False` set àª•àª°à«‹ till parity proven. |

**HIGH (data integrity / parity):**
| # | Task | àªµàª¿àª—àª¤ |
|---|------|------|
| ~~**FAB-H6**~~ âœ… DONE 2026-07-07 â€” `get_live_adx()` now truncates history to `bar_dt` (true as-of); overnight replay passes `bar_dt` per bar. | Overnight replay TODAY's ADX past bars àª®àª¾àª‚ inject àª•àª°à«‡ â†’ BACKFILL rows lookahead-tainted | `bridge_main.py:677` `get_live_adx(50)` without `bar_dt`; `inference.py:640-641` replayed timestamp stamp àª•àª°à«‡, merge àª•àª°à«‡. BACKFILL rows in `signals_all.csv` + shadow ledger lookahead-tainted. FIX-3 shadow âˆ’1.9R metric partly ledger àªªàª° rest àª•àª°à«‡. Fix: `bar_dt` per replayed bar pass àª•àª°à«‹ OR replay àª¦àª°àª®àª¿àª¯àª¾àª¨ ADX merge skip; `mode=BACKFILL` rows metrics àª®àª¾àª‚àª¥à«€ exclude. |
| **FAB-H7** â¸ï¸ DEFERRED (backtest-side; would shift +350.2R baseline â†’ flag-gate before enabling) | Daily-SL semantics liveâ‰ backtest | Live `bridge_core.py:378-391` `check_daily_sl_intrabar` â€” floating equity àªªàª° halt + force-close all. Backtest `backtest_replay.py:454-474` `daily_stopped=True` â€” only new entries block, open trades ride on; equity update only at trade close â†’ floating DD trip àª¨àª¹à«€àª‚ àª¥àª¾àª¯. Fix: backtest_replay àª®àª¾àª‚ mark-to-market equity per bar simulate + force-close at floor. |
| ~~**FAB-H8**~~ âœ… DONE 2026-07-07 â€” `_resume_sig` now folds `sorted(QGAI_* env)` + model .pkl mtimes. Env-toggle / retrain forces fresh run. | Backtest checkpoint resume signature env vars + model mtimes omit àª•àª°à«‡ | `backtest_replay.py:276-283` `_resume_sig` â€” `QGAI_CTF_FADE`, `QGAI_SKIP_RANGE`, `QGAI_RANGE_MIN_PROB`, `QGAI_PB_*`, `QGAI_ED_*`, `QGAI_HMM_VARIANT`, model pkl mtimes omit. Env toggle change / model retrain â†’ same CLI re-run â†’ half-old/half-new resume = plausible-wrong results (WFO-cache class bug, Bug-H ghost). Fix: signature àª®àª¾àª‚ `sorted(os.environ QGAI_*)` + model file hashes fold àª•àª°à«‹. |
| ~~**FAB-H9**~~ âœ… DONE 2026-07-07 â€” `adx_strength_soft_block` + combined SMMA+ADX cap wired into `bridge_main` (dormant, default OFF) â†’ live==backtest if ever enabled. | ADX-strength gate + combined SMMA+ADX cap backtest only, live àª®àª¾àª‚ àª¨àª¥à«€ | `backtest_replay.py:619-635` `adx_strength_soft_block` call + combined-penalty cap; `bridge_main.py` àª¬àª‚àª¨à«‡ missing. `adx_strength_soft=True` OR `QGAI_ADX_STRENGTH=1` adopt àª¥àª¾àª¯ àª àª¦àª¿àªµàª¸à«‡ live behavior WFO winner match àª¨àª¾ àª•àª°à«‡ â€” structural parity break guaranteed. Fix: identical block `bridge_main` àª®àª¾àª‚ wire àª•àª°à«‹ (dormant behind same flag). |

**MEDIUM (behavior / cleanup):**
| # | Task | àªµàª¿àª—àª¤ |
|---|------|------|
| **FAB-M10** â¸ï¸ DEFERRED (stateful behavior change â€” needs backtest before live; don't half-implement) | HMM regime zero hysteresis â€” noise flip threshold 0.48â†”0.42 àª¬àª¦àª²à«‡ | Per-bar GMM argmax (`inference.py:712-714, 895-899`) â€” Rangingâ†’Volatile àªàª• noise bar àªªàª° marginal 0.43-prob signal fire àª•àª°à«‡. Fix: 2 consecutive bars require OR `predict_proba` margin threshold check before switch. |
| ~~**FAB-M11**~~ âœ… DONE 2026-07-07 â€” picker now prefers any actionable BUY/SELL over higher-prob SKIP; mirrored in backtest for parity. | Best-of-BUY/SELL picker higher-prob SKIP àª¨à«‡ lower non-SKIP àª•àª°àª¤àª¾àª‚ prefer àª•àª°à«€ àª¶àª•à«‡ (**prime directive violation**) | `bridge_main.py:445` picker win_prob comparison â€” SKIP result higher prob àª¹à«‹àª¯ àª¤à«‹ select àª¥àª¾àª¯, àªœà«àª¯àª¾àª°à«‡ opposite direction lower-prob non-SKIP àª¹à«‹àª¯. Trades silently lost. Fix: any non-SKIP àª¨à«‡ SKIP àª•àª°àª¤àª¾àª‚ prefer àª•àª°à«‹. |
| ~~**FAB-M12**~~ âœ… DONE 2026-07-07 â€” parity-gap table written to `docs/FILTERS_MASTER.md` Â§PARITY GAPS (7 gaps, status each). `manual_risk_pct=6.0` footgun noted. | 7 explicit live-only parity gaps List | (1) spread guard, (2) opposite-signal reversal [S-1], (3) manual manager `bridge_manual.py` real orders own 3% pool, (4) stuck-trade hedge magic 202698, (5) forming-H1 line [S-5], (6) DD brake inverse [S-3], (7) daily-SL floating semantics [H-7]. Note: `bridge_manual.py:106` `manual_risk_pct=6.0` default vs line 255 `3.0` â€” dormant footgun. Manual loss = 9% daily halt trip â†’ bot day stop, backtest ne model àª¨àª¥à«€. Fix: single reconciliation report table + `manual_risk_pct` default fix. |
| **FAB-M13** ðŸŸ¡ PARTIAL 2026-07-07 â€” CTF re-audited via Path A: DISABLED (+34.3R, live config changed). Range-phase re-audit (soften 0.55) tested = flat +2R â†’ kept ON. Both now post-leak-fix validated. | Range-phase + CTF-fade blockers pre-leak-fix evidence àªªàª° justified â€” never re-audited under profit directive | Config comments in-sample numbers (âˆ’43R range, +15R CTF) HMM leak-fix + relabel àªªàª¹à«‡àª²àª¾àª‚ measured. A/B hooks (`--no-range-skip`, `QGAI_CTF_FADE`) exist àªªàª£ post-2026-07-03 rerun TASKS àª®àª¾àª‚ recorded àª¨àª¥à«€. **SMMA-gate àªœà«‡àªµà«‹ risk profile â€” hard blocks on stale evidence.** Path A àª† address àª•àª°à«‡ àª›à«‡ â€” post-Path-A verdict àª²àª–à«‹. |
| ~~**FAB-M14**~~ âœ… DONE 2026-07-07 â€” SMMA comment rewritten "PROVEN HARMFUL, do not flip"; dead session keys (use_time_filter/enable_ny_session/window*/enable_morning_session) marked âš°ï¸ DEAD + flipped False (0 readers verified). | Config comments accepted findings àª¨à«‡ contradict àª•àª°à«‡ â€” re-enable trap | `config.py:89-100` SMMA gate "+51R, flip to True after DEMO" àª¸à«‡àª² àª•àª°à«‡ àª›à«‡ àªœà«‹àª•à«‡ proven âˆ’3.7R/PARKED. `use_time_filter=True` + `enable_morning_session`/`enable_ny_session`/`window1_*`/`window2_*` àª¬àª§àª¾ dead (grep zero readers) àª›àª¤àª¾àª‚ live àª¦à«‡àª–àª¾àª¯. **Future session config.py àªµàª¾àª‚àªšà«€ proven-harmful gate re-arm àª•àª°à«€ àª¶àª•à«‡.** Fix: dead keys delete, SMMA comment "PARKED â€” proven harmful (âˆ’3.7R live parity, blocked 33 profitable trades)" àª•àª°à«‹. |

**LOW (retrain-cycle cleanup):**
| # | Task | àªµàª¿àª—àª¤ |
|---|------|------|
| **FAB-L15** | `is_dead_hour` 57-59% WR hours àª¨à«‡ dead label àª•àª°à«‡ | `features.py:611` (comment àªªà«‹àª¤à«‡ admit àª•àª°à«‡). Mislabeled feature training àª®àª¾àª‚ baked. Retrain cycle àªªàª° cleanup candidate. |
| **FAB-L16** | Backtest exit prices spread + slippage ignore àª•àª°à«‡ | Spread only entry àªªàª° charge; exits exact vSL/TP touch àªªàª° fill (`SimTrade._close`). Live exits bid/ask + 30s spread-wait entry delay. Small per-trade, systematic 700+ trades over. Fix: exit spread modeling `backtest_replay.py` àª®àª¾àª‚ add. |

---

| **DOW-AUDIT** | **Dow Theory Base Audit â€” full system audit against Dow Theory principles** (Imtiyaz, 2026-07-12) | Comprehensive audit: (1) 6 Dow principles vs system implementation, (2) market structure detection (HH/HL/LH/LL, swing, BOS, CHoCH), (3) trend classification (3 trends Ã— 3 phases), (4) MTF hierarchy (primary/secondary/minor), (5) entry/exit logic vs Dow rules, (6) indicator redundancy audit, (7) ML layer alignment, (8) look-ahead/leakage check, (9) volume confirmation gap, (10) backtest quality, (11) contradiction audit, (12) Dow Authenticity Score 0-100. Output = full report + gap table + priority action plan. **DO NOT implement changes â€” report only, then separate implementation plan.** |
| **EA-TS-REMOVE** | **Remove `ts_adx_switch_trend` feature IF scoring-system adopted** (Imtiyaz, 2026-07-07) | Legacy EA rule (H4 dir if H4_ADXâ‰¥19 else H1 dir). Currently used as XGBoost feature (`features.py:1339`) + ratchet trailing already uses fixed H1 (not the switch) + early-entry v2 optionally uses it via `QGAI_ED_HTF_RULE=adx_switch`. **Policy: KEEP as feature TODAY, never as a live decision rule.** **Trigger to remove: if/when a data-tuned SCORING system (SMMA/ADX/other) replaces the EA-19 rule everywhere.** Then: drop from `FEATURE_COLS` (features.py:1183/1255/1339) + retrain models + WFO-gate â‰¥ baseline. Blocked by: scoring system must first prove real edge (P(worth-it) currently 0.15-0.35 per Fable-5). |
| L2 | REBUILT trainset A/B (12,976 flips, full history) | model experiment â€” **AFTER current config locked** (buffer-sweep + re-WFO of 42-feat+forming-line+%-buffer first; don't mix variables). REBUILT format âœ… train.py-compatible. Plan: backup 42-feat model â†’ config `trades_file`â†’REBUILT â†’ retrain â†’ WFO vs +255.4R â†’ keep/restore. |
| L3 | ML Exit/TP-predictor model (13-sweep àª®àª¾àª‚àª¥à«€) | research |
| L6 | ADX encoding study (level vs +DI/-DI vs slope) | research |
| L12 | News ablation + calendar pipeline fix | research |
| D | Bug D â€” one-subprocess-per-MT5-terminal refactor (root of multi-account fragility) | **2026-07-01: reviewed with Imtiyaz â€” design (one primary decides, secondaries mirror as slaves) IS intentional; confirmed no change wanted.** Symptom already mitigated (warm-up fix + primary failover). Stays parked/dormant, revisit only if a new live symptom traces back here. |
| N2 | Run `Run_WFO_LiveMatch_Buf015.bat` (new, 2026-07-01) â€” walk-forward OOS over the SAME period as `live_buffer_015` (2025-06-29â†’2026-06-29), buf 0.15 + tp-regime + tp-equity 0 + risk 3 (matches current live config exactly). Needs the user's own machine (real train.py + xgboost/lightgbm/catboost/hmmlearn) â€” cannot run in Claude's sandbox. Purpose: fair OOS check against `live_buffer_015`'s in-sample PF 4.27 / DD 10.77%. |
| **FIX-2** | **Audit Fix 2 â€” entry gate cleanup** (updated 2026-07-03 honest-data importances àªªàª›à«€): **(a) feature prune â€” PARKED (Divyesh):** honest data àªªàª° àªœà«‚àª¨à«€ "10 dead" list àª–à«‹àªŸà«€ àªªàª¡à«€ (hmm_state àª¹àªµà«‡ #6, momentum_aligned_1hr #4!); àª«àª•à«àª¤ **2 àªœ àª¸àª‚àªªà«‚àª°à«àª£ àª®àª°à«‡àª²à«€**: `h4_trending_h1_aligned` + `trade_direction` (àª¤à«àª°àª£à«‡àª¯ models àª®àª¾àª‚ 0.0000; direction-àª®àª¾àª¹àª¿àª¤à«€ ts_htf_agreement #2 + momentum_aligned_1hr #4 àª®àª¾àª‚ àªœà«€àªµà«‡ àª›à«‡). momentum_aligned_4hr àª°àª¾àª–àªµà«€ (SELL #22, combined #23). Prune = trail sweep àªªàª›à«€àª¨àª¾ retrain cycle àª®àª¾àª‚, WFO-gate â‰¥ +393.7R. **(b)** failed SELL move-model retire/regate (Ï=0.25). **(c)** calibration rolling-OOS + threshold sweep 0.35/0.42/0.50 (threshold àª†àª‚àª§àª³à«‹ àªµàª§àª¾àª°àªµà«‹ àª¨àª¹à«€àª‚ â€” profit-first). **(d) ACTIVE NEXT: TRAIL sweep** â€” peak +0.94R â†’ exit âˆ’0.15R (1.09R giveback/trade); bats àª¤à«ˆàª¯àª¾àª°: `Run_TrailSweep_AsOf_TEST.bat` â†’ `Run_TrailSweep_AsOf_FULL.bat` (as-of workdir, demo àª¸àª¾àª¥à«‡ parallel-safe), àªªàª°àª¿àª£àª¾àª® SWEEPASOF_SUMMARY.csv â†’ "trail sweep done" àª•àª¹à«‡àªµà«àª‚. |
| **FIX-3** | **Audit Fix 3 â€” liveâ‰ backtest divergence + scaling gate** (ongoing process): June 2026 quantified â€” entry overlap àª®àª¾àª¤à«àª° 8/66 (12%), live TRAIL 49% vs backtest 11%, shadow âˆ’1.9R vs WFO +48.1R same month. TOOL READY: `engine/reconcile_shadow.py` (weekly àªšàª²àª¾àªµàªµà«€, output àªàª• folder àª®àª¾àª‚: reconcile_summary/matched_pairs/backtest_only/shadow_only CSVs). Attack order: FIX-1 â†’ HMM v3 deploy â†’ trail parity check â†’ fill audit (demo fills vs modeled). **Scaling gate: 4â€“8 week àª¸à«àª§à«€ weekly R gap Â±20% àª¨à«€ àª…àª‚àª¦àª° + overlap àªŠàª‚àªšà«‹ â€” àª¤à«àª¯àª¾àª‚ àª¸à«àª§à«€ capital àªµàª§àª¾àª°àªµà«àª‚ àª¨àª¹à«€àª‚**; àª“àª›à«àª‚ risk (1â€“1.5%) + hard lot cap àª¨à«€ audit àª­àª²àª¾àª®àª£ (live àª®àª¾àª‚ 15.58 lots àªœà«‹àªµàª¾àª¯àª¾) â€” àª¨àª¿àª°à«àª£àª¯ Imtiyaz/Divyesh àª¨à«‹. |
---

## P1 â€” Retrain model on RELABELED data (current period)
Config `trades_file` â†’ `Back_testing_data_final_cleaned_RELABELED.xlsx` (same Dec24â†’Apr26 entries,
labels recomputed under live HTF exit â€” 27% changed). Model still on OLD labels until retrained.
- [ ] Run `Start\3_Train_Models.bat`.
**Revert:** `config.py` `trades_file` â†’ old `Back_testing_data_final_cleaned.xlsx` (one line).

## P2 â€” WFO OOS validation (confirm relabel + regime-adaptive TP) â€” on the current period
Gate before any live change. Both need P1 retrain first; run BOTH on the same (relabeled) data.
- [ ] `Run_WFO_FULL.bat` â†’ `wfo_results` (global TP, relabel baseline) â€” compare PF vs old 1.55.
- [ ] `Run_WFO_TPREGIME.bat` â†’ `wfo_tpregime` (regime-adaptive TP). Compare vs the global baseline.
- [ ] Keep relabel / regime-TP ONLY if each holds OOS (PF, avgR, Total R, green-week %). Else revert.
~1.5â€“2 hr each, resume-safe. Then tell Claude "WFO done".
**Backtest already WON in-sample:** regime-TP Total R 257.7â†’310.2 (+20%), PF 2.52â†’2.56 â€” now needs OOS proof.

## P2-REDO â€” Re-run WFO after the Bug F/J HTF fix (ðŸ”´ the validation must be redone)
**Why:** `backtest_replay` was fixed so backtest HTF = live HTF (config-aware default + H1 flip + H1 entry SL,
BUG_LOG #F/#J). The previous WFO +321R/PF3.28 used `stop-trail=line` (M15 trail/flip) â€” a DIFFERENT strategy
than live. So that number is INVALID. Must re-run to get the true HTF-matched OOS validation.
**Steps:**
- [ ] Archive the stale HTF-mismatched results (`wfo_results`, `wfo_tpregime`, `signal_log_full`, any run made
      before 2026-06-27 code fix) â†’ `results/_archive/WRONG_*` (don't trust their numbers).
- [ ] Clear the results-dir (Bug H cache won't auto-invalidate) then re-run `Run_WFO_FULL.bat`
      (now config-aware â†’ HTF automatically) + `Run_WFO_TPREGIME.bat`.
- [ ] The currently-running full-history backtest is on OLD code (started before the fix) â†’ its output is stale; re-run.
- [ ] Compare the NEW HTF-matched WFO vs old PF 1.55 baseline; re-decide relabel + regime-TP on the CORRECT numbers.
- [ ] THEN P2b ($10k sim) + P3' (DEMO) on the real validated config.
**Status:** code fixed 2026-06-27; runs pending on PC. **Logged:** 2026-06-27.

## P2b â€” Check real return + DD under 3% DYNAMIC sizing ($10k Stage-2 sim)
**Why:** WFO uses **fixed 0.01 lot** = clean R / honest edge proof (3% dynamic compounding would distort
PF & total-R via compounding + trade-ordering). So WFO answers "is the edge real?", NOT "what does 3% do?".
After P2 confirms the edge, run the $10k 3%-dynamic-compounding sim to see the LIVE-realistic return + drawdown.
- [ ] Run the $10k Stage-2 sim on the OOS trade log (3% dynamic, FAR TP â€” `--tp-equity 0`, NOT 3; see RULEBOOK).
- [ ] Read off real return + **Max DD** (expect ~28-39% at 3%). Confirm DD is tolerable; 1-2% if not.
- [ ] This is ALSO the only place the daily 9% ratchet rule binds (fixed-lot WFO never triggers it) â€” verify it.
**Status:** pending P2. **Logged:** 2026-06-27.

## P3 â€” Wire regime-adaptive TP into the LIVE bridge + DEMO  (only after P2 confirms)
Currently only in `backtest_replay.py --tp-regime`, NOT in the live bridge.
- [ ] Add regimeâ†’TP map (Rng 2.0 / Trn 1.0 / Vol 0.8) to `config.py` + bridge exit path
      (`bridge_core.py`/ratchet), switched on HMM state at entry. Reversible flag to fall back to global TP.
- [ ] DEMO forward-test before live.

---

## LATER â€” PARKED until the ideas above are confirmed (Imtiyaz's call 2026-06-26)

### L1 â€” Full-history backtest (2022â†’2026, honest OOS)
`Run_Backtest_FullHistory.bat` (DONE/ready) â€” 2 variants (global vs regime-adaptive) over 97k bars.
Tells if the edge holds on the 2022-24 unseen regime. Run AFTER the current-period ideas confirm.

### L2 â€” REBUILT trainset (full-history entry set) â€” Option A
`engine/rebuild_trainset.py` (DONE, RAN): every 2-SMMA flip = candidate entry over 2022-2026, labeled
under live exit â†’ `data/Back_testing_trainset_REBUILT.xlsx` (12,976 trades, ~4.6x data, win 36.9%,
stable by year incl. 2022-24). NOT adopted â€” bigger change (entry universe). After P2, A/B vs RELABELED
via retrain + WFO; keep only if AUC/OOS PF holds or improves. (Reproduce: `Run_Rebuild_Trainset.bat`.)

### L5 â€” Line + buffer sweep backtest (GLOBAL **and REGIME-WISE**)
**Why:** the ratchet SL/trail = the 2-SMMA **line** âˆ“ a **buffer** (`ratchet_buf_pct`, currently **0.20** global).
Set once (0.09â†’0.20: same profit, lower DD). Just like TP, the best buffer is probably **different per HMM
regime** â€” Volatile likely wants a WIDER buffer (avoid whipsaw), Ranging/Trending maybe tighter. So sweep
buffer GLOBALLY first, then BY REGIME, on the CURRENT (relabeled) model.
**Plan:**
- [ ] **Global buffer sweep:** `backtest_replay.py --ratchet-buf-pct X` for
      X âˆˆ {0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50} â†’ compare PF / Total R / **Max DD** / whipsaw
      (FLIP/SL counts). Confirm/replace 0.20. (Old tool `backtest/h1_buffer_sweep.py` â€” adapt.)
- [ ] **REGIME-WISE:** read each sweep report's BY-REGIME block â†’ best buffer per Ranging / Trending /
      Volatile. If they differ meaningfully, build a **regime-adaptive buffer** (same pattern as the
      regime-adaptive TP: a `_BUF_BY_REGIME` map switched on HMM state at entry, config-gated, default OFF).
- [ ] **Line check (optional):** line = SMMA(2). Test SMMA period {2,3} / buffer floor (`ratchet_sl_min_pct` 0.18).
- [ ] Best global/regime buffer that holds â†’ **WFO-validate OOS** â†’ then DEMO. Reversible.
**Note:** small buffer = tight stop (more SL/whipsaw, less give-back); large = looser (rides pullbacks, bigger
losers). Sweet spot balances DD vs capture, and that balance differs by regime. Do AFTER P1-P3 (don't add
variables mid-validation). Pairs naturally with the regime-adaptive TP work.
**Status:** not started. **Logged:** 2026-06-27.

### L6 â€” ADX representation study (is the ADX level worth it, or use +DI/-DI / slope?)
**Question (Imtiyaz):** the model currently uses the **ADX LEVEL** on 4 TFs (`M15_ADX`, `M30_ADX`, `H1_ADX`,
`H4_ADX`) PLUS direction (`*_DI_diff` = +DIâˆ’âˆ’DI on each TF), `adx_trend_count`, and slopes (`h4_adx_slope`,
`h1_adx_slope`). Is the raw ADX level pulling its weight, or would **only ADX**, or **+DI/âˆ’DI with slope**,
work better? (ADX level = trend STRENGTH, no direction; DI_diff = DIRECTION + strength; slope = is it rising/fading.)
**How (don't guess â€” ablation decides; importance is per-model, never remove blindly â€” RULEBOOK):**
- [ ] Baseline = current features. Use the `QGAI_ABLATE="f1,f2"` env hook (`features.py`) to drop a group
      for ONE WFO without touching committed lists. (Old `Run_Ablate_*.bat` are in `backtest/_archive_bats/`.)
- [ ] Variant A â€” drop the 4 raw `*_ADX` levels, keep DI_diff + slopes â†’ WFO. Does OOS PF/avgR hold or improve?
- [ ] Variant B â€” drop DI_diff, keep ADX levels â†’ WFO.
- [ ] Variant C â€” add explicit +DI/âˆ’DI separately and/or more slopes (M15/M30) â†’ WFO.
- [ ] Keep a change ONLY if OOS (PF, avgR, green-week%) improves vs baseline. Watch cross-model redistribution
      (a feature 0-importance in SELL can be #1 in BUY).
**Context:** STRATEGY.md already finds **M15_ADX is a top feature** and a useful FILTER (high ADX = late/chasing
entry = worse; low ADX = clean trend = better). So ADX clearly matters â€” the question is the best ENCODING,
not whether to use it. Do AFTER P1-P3.
**Status:** not started. **Logged:** 2026-06-27.

### L7 â€” Fix STALE labels / displays across the system (Imtiyaz flagged)
The code/dashboard still SHOW things that no longer match reality after ATR/volume removal, the 44-feature
prune, and the relabel. Misleading (not all bugs, but must be corrected). Known so far â€” AUDIT for more:
- [ ] `train.py:33` print `"... | 59 Features"` â†’ wrong (now ~44). Make it dynamic (`len(FEATURE_COLS)`).
- [ ] `inference.py:477` comment `"Compute 46 features"` â†’ stale â†’ dynamic/correct.
- [ ] `train.py:243` comment `"full 43 features"` â†’ stale.
- [ ] **Dashboard/log shows `Live ATR20: 0.1594% ($6.49)`** though ATR is NOT used in any decision
      (display-only; ADX keeps its own internal TR). Either REMOVE the ATR readout or label it clearly
      `(display only â€” not used by the model)`. Same for any other vestigial readout (volume, etc.).
- [ ] **Hybrid feature-set counts** `Ranging=34 | Trending=30 | Volatile=20` (features.py:1364, state-specific
      RANGING/TRENDING/VOLATILE_FEATURES) â€” verify these lists are current (no pruned features, consistent with
      the 44-feature universe) and that the printed counts are right.
- [ ] **Full sweep:** grep the codebase + dashboard.html for other hardcoded counts / removed-feature labels
      / outdated strings and fix or make dynamic. ("many more like this" â€” Imtiyaz.)
- [ ] **Dead code / misleading comments (from 2026-06-27 4-round parity check):** in `bridge_risk.py` the
      PBE / partial-close / full-breakeven logic in `_update_buy`/`_update_sell` is UNREACHABLE in ratchet mode
      (`update()` routes to `_update_ratchet` when `self.ratchet`), yet `PARTIAL_CLOSE_ENABLED=True` and the
      line-47 comment says "NO PBE/partial/BE". Remove or clearly gate the dead PBE/partial/BE/smart-exit code so
      it can't confuse future reviews (it's NOT a behavioral bug â€” just dead + misleading). Smart-exit
      (`_smart_exit_check`, `SMART_CLOSE`, the Bug-B open_time restore) is likewise vestigial in ratchet mode.
**Why it matters:** wrong labels erode trust in the dashboard and mislead future debugging. Low-risk (mostly
display/comments) â€” do opportunistically, NOT mid-validation. **Status:** not started. **Logged:** 2026-06-27.

### L8 â€” Deposit/withdrawal-aware equity (Imtiyaz flagged â€” ðŸ”´ safety + clean signal log)
**Problem:** the bot reads WHOLE-account equity, but the account gets manual **deposits & withdrawals**.
The bridge does NOT detect balance operations (`DEAL_TYPE_BALANCE`), so:
- A **withdrawal** drops equity â†’ looks like a loss â†’ can **FALSELY TRIGGER the daily-SL / 9% ratchet halt** (ðŸ”´ safety).
- A **deposit** raises equity â†’ looks like profit â†’ inflates % sizing + raises the daily ratchet floor falsely.
- The **signal-log `equity` column** (and shadow ledger, $10k analysis) jumps on every flow â†’ polluted analysis.
**Good news:** model TRAINING is immune â€” it learns on R (price/risk), never equity/balance. Verified. So no
"false training"; this is purely a LIVE-equity + logging issue.
**Permanent solution:**
- [ ] Poll MT5 `history_deals_get` for `DEAL_TYPE_BALANCE` deals â†’ maintain `net_external_flow` (deposits +, withdrawals âˆ’).
- [ ] **Daily ratchet/sizing:** when a flow occurs intraday, adjust `day_open` + `day_peak_equity` (and the sizing
      base) by the flow amount so deposits/withdrawals never trip the daily halt or distort lot size.
- [ ] **Signal log (permanent fix):** log a flow-adjusted **`trading_equity`** (= equity âˆ’ cumulative net flow from
      a fixed start) instead of / alongside raw equity; optionally log flow events to their own line. Then the
      equity column reflects TRADING only and analysis is clean across deposits/withdrawals.
- [ ] (related, already known) manual trades on the account also move whole-account equity â€” same flow-adjusted
      base helps, but the bot still can't tell manual-trade P&L from its own; document the limitation.
**Priority:** the withdrawalâ†’false-halt path is a real safety bug â€” do this BEFORE scaling live / before relying
on the equity-based daily ratchet with active deposits/withdrawals.
**Status:** âœ… DONE 2026-06-29 (was partial). (1) daily-SL/TP flow-adjust: `_net_balance_flow_today` +
broker-time fix + 50% guard (06-27/06-29). (2) **lot-sizing base** now flow-adjusted: `bridge_core.execute`
sizes off `equity âˆ’ today's flow âˆ’ manual_floating` (intraday deposit/withdrawal or manual leg can't distort
lot). (3) **signal-log `trading_equity` column**: `bridge_session.trading_equity()` = equity âˆ’ net flow since
a fixed anchor (2026-06-29); logged on every live/monitor signal via `log_signal(..., trading_equity=)`;
old CSV auto-migrated (`_ensure_teq_column`). (4) **flow-event logging**: `log_new_balance_ops()` announces
each new deposit/withdrawal once â†’ `logs/balance_flows.csv`. Optional follow-up: surface `trading_equity` on
the dashboard + add the column to `signals_complete.csv`. DEMO-verify. **Logged:** 2026-06-27, done 2026-06-29.

### L9 â€” âœ… DONE 2026-06-29 (see DONE table) â€” Complete signal log: EVERY M15 candle, visible offline, with $/% move + win/loss (Imtiyaz)
**Problem:** `logs/signals_all.csv` only has rows for bars the bridge actually ran (3,747 rows over 18 mo â€”
far short of ~96/day Ã— ~390d â‰ˆ 37k candles). So the dashboard shows gaps when the system was off, and there's
no per-signal **$ move / % move**, and `outcome` (win/loss) is only on executed trades.
**Want:** every M15 candle (all 96/day) shown â€” BUY / SELL / **SKIP** (+ reason) â€” with win/loss, **$ move**
and **% move**, viewable even when the bridge is OFF.
**Solution (backfill + keep current):**
- [ ] Backfill script (model needed â†’ runs on PC): replay the model over EVERY M15 bar (backtest_replay already
      emits `backtest_signals.csv` = per-bar BUY/SELL/SKIP + probs + reason + blocked_by). Join each BUY/SELL with
      its exit outcome (from the exit sim / shadow_ledger) to add `win/loss`, **`move_$`**, **`move_%`**.
- [ ] Write a dashboard-ready `logs/signals_complete.csv` (or fill gaps in `signals_all.csv`) covering all candles.
- [ ] Add `move_$` and `move_%` columns to `bridge_data.log_signal` so the LIVE log captures them going forward too.
- [ ] Point `signals.html` / dashboard Signal Log at the complete file (it already reads the CSV, so offline view
      works once the CSV is complete).
- [ ] Schedule the backfill (after `2_Update_Data`, or a scheduled task) so the log stays complete when the bridge is off.
**Note:** ties into L7 (drop/relabel the stale `atr20_pct`/`vol_spike` columns in the log) and L8 (log
flow-adjusted equity). Do together for one clean signal-log pass.
**IMPORTANT clarification (Imtiyaz asked "won't the model fail to learn from old data?"):** NO â€” the model
does NOT learn from `signals_all.csv`. The batch model trains on COMPLETE OHLC (97,235 bars) + the trades
file; the online model learns from `live_trades.csv`. The signal log is **display/audit only**. So an
incomplete signal log does NOT starve the model. The mechanism for "model learns from EVERY signal across
ALL history" is **L2 (REBUILT trainset)** â€” every flip-candidate over 2022-2026, labeled. L9 here is purely
about DASHBOARD VISIBILITY. **Status:** not started. **Logged:** 2026-06-27.

### L11 â€” âœ… DONE 2026-06-29 (gap-backfill + resume-prompt; see DONE table) â€” Startup gap-backfill + "trade the last signal?" resume prompt (Imtiyaz's spec)
**Goal:** make the system robust to the terminal being off. On startup it backfills every missed signal,
shows them on the dashboard at 0.01 lot, and asks whether to act on the latest one.
**Flow (on `1_Start_Trading.bat` startup, after the data download/update step):**
1. **Backfill the gap:** replay the model over every M15 bar from the last logged signal â†’ the latest closed
   bar. Log EVERY signal (BUY/SELL/SKIP) into the signal log, with outcome + **$/% at 0.01 lot** â†’ dashboard
   shows the complete overnight history (ties to L9).
2. **Resume prompt:** identify the LATEST signal (most recent completed bar). If it's BUY/SELL and still fresh,
   ASK the user (console y/n, or a dashboard button): *"Take a trade on the last signal? [BUY/SELL @ price]"*.
   - **Yes** â†’ execute at the normal **3% risk** sizing.
   - **No** â†’ skip it, continue the live loop waiting for the next new signal.
3. Then carry on with normal live trading.
**âš ï¸ Key rule:** ONLY the latest/fresh signal is tradeable. All the older overnight signals are **LOG-ONLY**
(record + 0.01-lot P&L for the dashboard) â€” they cannot be traded because the price has moved on (no trading
the past). This matches Imtiyaz's "trade on the LAST signal" + "overnight signals just update the log".
**Touches:** `bridge_main.py` (startup sequence + the prompt + gap detection), `bridge_data.log_signal`
(backfill writes), dashboard. **Depends on / overlaps:** L9 (complete log), L10 (clean live log).
**Status:** not started. **Logged:** 2026-06-27.

### L12 â€” News / economic-calendar: prove usefulness (ablation) + fix the data pipeline
**Two parts.** (a) Is news actually adding edge? (b) The data is stale/unused.
**Findings (2026-06-27 check of `Economi calandar data/`):**
- Model uses 2 news features (`mins_to_next_3star`, `mins_since_last_3star`) + a pre-news threshold bump
  in inference. So news IS integrated â€” but its EDGE is UNTESTED (volume + ATR were both intuitive yet
  failed ablation and were removed; news could be the same or genuinely useful).
- Model's news file `data/news_all_2024_to_now_pure_cleaned.csv` ends **2026-05-15** (~6 wks stale) and starts
  2024-01 (so the 2022-2023 full-history backtest runs with news=0).
- The rich `Economi calandar data/ForexFactory_Calendar_3yr.csv` (2023-06â†’2026-06, currency/impact/
  forecast/previous/revision, 15k rows) is **UNUSED** by the model. Plus duplicate sources (Neex / vinteg, both 3.9MB).
**Plan:**
- [ ] **Ablation:** drop the news features via `QGAI_ABLATE` â†’ WFO. OOS PF drops â†’ news useful (keep + freshen);
      OOS PF flat/up â†’ news redundant â†’ remove (leaner model). Same method as volume/ATR.
- [ ] If KEEP: fix the pipeline â€” feed the model from the fresh ForexFactory calendar (refresh on each data
      update), extend coverage back to 2022 if possible, dedupe Neex/vinteg, stop the news file going stale.
**Do AFTER P2-REDO (don't add variables mid-validation).** **Status:** not started. **Logged:** 2026-06-27.

### L13 â€” âœ… BUILT 2026-06-29 (code done, config-gated default OFF, DEMO-test pending) â€” Manual-trade MANAGER: alert + auto-manage Imtiyaz's manual trades (Imtiyaz's spec)
**Account = MT5 HEDGING mode (confirmed 2026-06-27)** â†’ opposite positions co-exist (hedge), don't net off.
**Want:** Imtiyaz manually piles onto the bot's BUY/SELL signal for more profit; the system then auto-manages
that manual leg.
**Part A â€” signal alert:** dashboard "ðŸŸ¢ BUY NOW @ price (win%/regime)" / "ðŸ”´ SELL NOW" lights up on a fresh
signal (+ optional sound) so Imtiyaz can open the manual trade. Ties to L9/L11.
**Part B â€” auto-manage the manual leg (new "manual-trade manager" subsystem):**
- [ ] **Detect** a manual trade (non-bot-MAGIC XAUUSD position; may need a dedicated "manual" tag/magic to
      tell it apart from Anisa's other manual trades).
- [ ] **On manual open â†’ cap effective risk at 6%.** Compute the lot that = 6% account risk for the current
      SL distance (`risk6_lot = equity*6% / (100*sl_dist)`). If the manual lot â‰¤ risk6_lot â†’ just set a 6% SL.
      If the manual lot > risk6_lot â†’ **immediately HEDGE the EXCESS** (`manual_lot âˆ’ risk6_lot`, opposite dir)
      so the NET at-risk volume = the 6%-equivalent lot; the excess is neutralised. Manage the net 6% leg with the 6% SL.
      Example: risk6_lot 0.50, manual 0.80 â†’ hedge 0.30 now â†’ net 0.50 at risk; on flip, hedge the remaining 0.50 (full lock).
- [ ] **On the bot's FLIP exit â†’ open a HEDGE** (opposite direction, SAME size) against the manual leg â†’
      manual net risk = ZERO (P&L locked). Hedging account makes this possible.
- [ ] **On profit â†’ at a TARGET TP (not the daily-equity TP) â†’ close BOTH legs** (manual + its hedge / + bot),
      OR open the hedge against the manual leg to lock it.
**âš ï¸ Caveats / must-do:**
- Auto-opening hedge positions = real money moves â†’ **DEMO-test heavily** before live; keep a master ON/OFF flag.
- The bot reads WHOLE-account equity â†’ the manual leg's floating P&L can falsely trip the daily 9% ratchet â†’
  **needs L8 (manual-trade-aware / flow-adjusted equity) FIRST or together** so the bot isolates its own P&L.
- 6% manual SL + the extra leg = much higher total exposure/drawdown (Imtiyaz's choice).
- Define precisely which position is "the manual trade" (tag/magic) to avoid managing the wrong one.
**Status:** not started â€” design captured. **Logged:** 2026-06-27. **Depends on:** L8 (safety/equity), L9/L11.

### L7b â€” REMOVE vestigial code cleanly (Imtiyaz: "why label, just remove it") â€” AFTER DEMO
Labels were the safe interim (L7). Proper end-goal = delete the dead/unused code. NOT trivial â€” hidden deps:
- **ATR (`atr20_pct`)** is threaded through: `backtest_replay` predicted-TP scaling (`atr_usd`), `bridge_core.execute()`
  signature, `bridge_data` signal-log + **SQLite DB schema columns**, dashboard. Removing = ~6 files + a schema
  migration + handling the predicted-TP path. (ATR is NOT used in any live decision, only the info-only predicted path.)
- **Dead PBE / partial-close / full-breakeven / smart-exit** in `bridge_risk._update_buy/_sell` â€” âœ… **DONE
  2026-06-29:** dep-traced (every live VirtualTrade is `ratchet=True`; a non-ratchet trade is skipped at
  `execute()` line 191), then REMOVED `_update_buy`, `_update_sell`, `_smart_exit_check`; `update()` now always
  routes to `_update_ratchet`; trimmed the now-unused imports; `status()` fields kept (used by dashboard).
  Compile-OK, 0 nulls (mount-write corruption hit + stripped). `__init__`/`status` unchanged.
- **ATR (`atr20_pct`) removal â€” SAFE SUBSET DONE 2026-06-29 (live-neutral); DB/model parts deferred.**
  Established ATR is fully vestigial (dropped from FEATURE_COLS 2026-06-19; every read uses a default constant;
  `execute()`'s `atr20_pct` param was never used; `vol_regime` is "informational only, no filtering").
  REMOVED (behavior-neutral): the per-bar `ðŸ“ Live ATR20` display log + `result["atr20_pct"]` threading
  (`bridge_main`), and the unused `atr20_pct` parameter from `execute()` / `handle_opposite_signal()`
  (`bridge_core`). Both Read-verified complete (bash py_compile shows false truncation errors), 0 nulls.
  LEFT IN PLACE deliberately (need a stopped bot): the SQLite `atr20_pct` column (nullable â€” now logs 0, no
  live-DB migration), `inference.py` `vol_regime` constant, the `df["atr20_pct"]` compute, and
  `train_move_model.py` `atr_usd` (only matters on retrain). Finish these when the bot is stopped.
**How (do AFTER DEMO is stable â€” not mid-validation):**
- [ ] 4-round dep-trace each item (grep every usage; confirm no live path touches it).
- [ ] Remove + migrate the signal-log/DB schema (drop atr columns or keep nullable) without breaking logging.
- [ ] DEMO re-test the bridge after removal (no exceptions, signals still log, dashboard still renders).
**Why parked:** mid-DEMO removal of live code risks bugs in the running validation; labels are zero-risk for now.
**Status:** parked. **Logged:** 2026-06-28.

### L3 â€” ML Exit/TP-predictor model (Imtiyaz's idea)
Per-trade personalized TP from entry features, learned from the 13-TP sweep R(TP) curves + `peak_r`.
One-pass simulator â†’ matched R(TP) table â†’ label best TP (regression) â†’ train small â†’ WFO vs regime-TP.
Do only after the simple regime-TP is confirmed live.

### L4 â€” Fix OPEN bugs (from BUG_LOG.md / GUIDE Â§5b)
Six high-priority bugs already fixed; these remain open. Fix order:
- [x] **A ðŸ”´ â€” âœ… DONE (verified 2026-06-29):** secondaries now flattened on EVERY daily-SL/TP halt path,
      guarded to fire ONLY on the fresh Falseâ†’True transition (sticky flag would otherwise reconnect/close
      every poll): `bridge_main.py:360-365` (check_closed realized-loss halt), `bridge_core.py:369-372`
      (`check_daily_sl_intrabar` ratchet floor, 2s), `bridge_core.py:377-380` (`check_daily_tp_intrabar`).
      Plus all per-trade exits (flip/vSL/TP) already call `close_secondary_accounts()`. No code change needed.
      (Minor residual edge: on RESTART when daily-SL was already breached pre-restart, preload sets the sticky
      flag so no re-flatten â€” but those secondary trades were already closed when the SL first fired live.)
- [x] **F ðŸŸ¡ â€” âœ… DONE (verified 2026-06-29; implemented 2026-06-27):** `backtest_replay.py:243-249` defaults
      `TRAIL_MODE` to the live config â€” when `--stop-trail` is omitted, uses `"htf"` if `ratchet_htf_sl` else
      `"line"`, so every default backtest/WFO matches live's HTF exit. Includes Bug J entry-SL match (H1 line,
      2.5% cap, lines 486-494) + H1 flip (315, 383-385). No code change needed.
- [x] **B ðŸŸ  â€” âœ… DONE (found already fixed, verified 2026-07-01):** `bridge_core.py:649-654` â€” `recover_open_trades()`
      now reconstructs `open_time` from the real open duration (`tick.time âˆ’ pos.time`), comment tags it
      "Bug B fix". Docs here were stale; code already had the fix.
- [x] **E ðŸŸ¡ â€” âœ… DONE (found already fixed, verified 2026-07-01):** `backtest_replay.py:26-27` wraps
      `sys.stdout`/`sys.stderr` in a UTF-8 `TextIOWrapper` â€” the cp1252 emoji crash is handled. Docs here were stale.
- [ ] C ðŸŸ  set live `SYMBOL` from the connected primary (matters once `MT5_PRIMARIES` failover is used).
      **Still open, confirmed 2026-07-01** â€” `bridge_constants.py:43` sets `SYMBOL` once at import from
      `MT5_ACCOUNTS[0]`; `connect_primary()` (bridge_multi.py) never updates it after a failover switch.
      Dormant only because `MT5_PRIMARIES` is currently unconfigured (no failover in use).
- [ ] D ðŸŸ  (big refactor) one subprocess per MT5 terminal â€” root of the multi-account fragility. Later.
- [x] **M ðŸŸ  â€” âœ… FIXED 2026-07-01:** `engine/run_wfo.py` â€” `--trail-mode` default was `"line"`, and
      `bt_cmd += ["--stop-trail", args.trail_mode]` only fired `if args.trail_mode != "line"`. Since Bug F
      made `backtest_replay.py` default to a **config-aware** trail (htf when live `ratchet_htf_sl=True`),
      omitting `--stop-trail` no longer meant literal M15-line â€” it meant "whatever config says" (htf).
      So `run_wfo.py --trail-mode line` (default or typed explicitly) silently ran HTF, not line.
      **Fix applied:** default changed `"line"` â†’ `None`; forward condition changed to
      `if args.trail_mode is not None:`. Now: no flag â†’ `None` â†’ nothing forwarded â†’ `backtest_replay.py`'s
      own config-aware default applies (htf today) â€” same result as before, now correct-by-design instead
      of accidental. Explicit `--trail-mode line` now genuinely FORCES line mode (previously silently ignored).
      `py_compile` clean. No other reference to `args.trail_mode` elsewhere in the file.
**Detail:** `docs/BUG_LOG.md`. Do C opportunistically; D is a project (see below, Imtiyaz flagged 2026-07-01).

---
*Logged 2026-06-26. Update status as runs complete.*

---

### Future Research Task - Clean Support / Resistance Features

| # | Task | Detail |
|---|------|--------|
| **SR-REDESIGN** | Build cleaner support/resistance feature candidates to replace weak OB/SR model inputs | **KEEP IN TASKS / NOT STARTED.** Reason: old OB/SR distance feature `h4_support_dist` looked good in the 3-month screen, but failed clean OOS1Y and 6-month WFO vs baseline, so it stays dropped. Next design should create cleaner S/R candidates instead of reusing the weak OB/SR inputs. Candidate features: previous day high/low distance, weekly high/low distance, confirmed-only swing high/low distance, liquidity-zone distance, round-number distance, session high/low distance, and HTF structure levels based on BOS/CHOCH. Rules: no future candle, closed/confirmed levels only, no live trading rule until retrain + 3-month test + OOS1Y + WFO gate. |


