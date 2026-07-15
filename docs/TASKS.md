# QGAI — Tasks (priority order)

### ✅ DONE — 2026-07-15
| # | Task | Result |
|---|------|--------|
| **Current 28-feature config — 53-week WFO OOS** | **DONE.** Runner: `backtest/_runners/Run_CurrentLiveModel_WFO_FULL.bat`; results: `backtest/results/wfo_current_live_28feat_20260714/`. Final `_WFO_SUMMARY.csv`: **+282.7R / 53 weeks / 1009 trades / 48 positive weeks / 5 negative weeks / avg +5.33R per week**. This is the honest OOS retraining benchmark for the current live feature config. Old `current_live_28feat_backtest_1yr_20260714` remains **in-sample reference only** (`--allow-in-sample`, leakage check FAIL, +474.4R) and must not be used as keep/reject proof. |
| **Clean single-training OOS 1-year backtest** | **DONE 2026-07-15.** Registry ID: `OOS1Y-01`. Runner: `backtest/_runners/OOS1Y-01_RUN_CurrentConfig_CleanOOS_1yr.bat`; results: `backtest/results/OOS1Y-01_current_config_clean_oos_1yr_20260715/`; summary: `OOS1Y-01_current_config_clean_oos_1yr_20260715_001_summary_st-htf.csv`. Retrained to `data/models/test_workspace` only, live `data/models/final` not touched. Cutoff proof in model meta: `requested_training_cutoff=2025-06-28`, `effective_training_cutoff=2025-06-28`; backtest period `2025-06-29 -> 2026-06-29` with no `--allow-in-sample`. Result: **+338.5R / 1130 trades / WR 52.8% / PF 1.95 / avg +0.300R / max DD 2.6% / fixed 0.01 lot / 3% risk reference return +80.02%**. Regime split: Ranging +206.9R, Trending +52.6R, Volatile +79.0R. This is clean single-training OOS, below old in-sample +474.4R but above current 53-week WFO +282.7R. |
| **FS67-12 h4_support_dist OOS1Y confirmation** | **DONE 2026-07-15 — REJECT / keep dropped.** Runner: `backtest/_runners/feature_sweep_67/FS67-12_RUN_h4_support_OOS1YConfirm.bat`; results: `backtest/results/feature_sweep_67/FS67-12_h4_support_oos1y_confirm/`. Baseline matched `OOS1Y-01`: **+338.5R / 1130 trades / PF 1.95 / WR 52.8% / DD 2.6%**. Adding `h4_support_dist` gave **+323.2R / 1130 trades / PF 1.95 / WR 52.3% / DD 2.1%**, delta **-15.3R**, captured pts **8002 -> 7885**, negative weeks **4 -> 8**. It helped in the 3-month FS67-01 screen (+8.1R) but failed the 1-year clean OOS confirmation. Decision: do **not** re-add; no WFO needed unless a future redesigned S/R feature replaces it. |
| **FS67-21 h4_support_dist 6-month WFO confirmation** | **BUILT, optional due diligence.** Runner: `backtest/_runners/feature_sweep_67/FS67-21_RUN_h4_support_WFO6M.bat`. It does **candidate-only** weekly WFO with `QGAI_UNPRUNE=h4_support_dist` over `2025-12-29 -> 2026-06-29`, retraining in `data/models/test_workspace` only. Baseline is **not rerun**; compare against existing current-model WFO summary `backtest/results/wfo_current_live_28feat_20260714/_WFO_SUMMARY.csv` for the same weeks. Purpose: extra 6-month WFO proof after FS67-12 already rejected the feature on clean OOS1Y. |

### ⏳ VALIDATION PLAN — Yearly 2022→2026 Train/Backtest/WFO
| # | Task | Detail |
|---|------|--------|
| **Yearly validation ladder** | **Plan only, not started.** Goal: validate the current feature/config across 2022-2026 without leakage using a full ladder: data audit -> yearly single-training OOS backtests -> yearly WFO -> comparison report -> final live retrain only if gates pass. This is the macro robustness check after the current 53-week WFO. |
| **Stage A — Data audit** | Check 2022-2026 coverage for OHLC, ADX, news/calendar, and trade-label data. Record each file's start/end date, missing candles, duplicate timestamps, timestamp mismatches, and whether every feature can be calculated from data available at signal time. Leakage guard must remain active. |
| **Stage B — Yearly single-training OOS backtests** | Use isolated `data/models/test_workspace` only, never `data/models/final`. No `--allow-in-sample`. Each fold must print `Leakage check PASS`. Folds: **Y1** train cutoff `2022-12-31`, test `2023-01-01 -> 2023-12-31`; **Y2** train cutoff `2023-12-31`, test `2024-01-01 -> 2024-12-31`; **Y3** train cutoff `2024-12-31`, test `2025-01-01 -> 2025-12-31`; **Y4** train cutoff `2025-12-31`, test `2026-01-01 -> latest closed period`. Same risk, TP/SL, ratchet buffer, spread/slippage assumptions, max-open, and feature set across all folds. |
| **Stage C — Yearly WFO** | For each year 2023, 2024, 2025, 2026, run WFO inside that year: retrain before each fold and test the next unseen fold. Weekly WFO = detailed proof; monthly WFO = faster macro proof. Keep all retrains in `test_workspace`. Save per-year folders and combined `ALL_OOS_trades.csv`/summary. |
| **Stage D — Comparison report** | Build one report with: Year, single-training R, WFO R, trades, WR, PF, avg R, max DD, positive folds, worst fold/month, best fold/month, BUY/SELL split, regime split, probability buckets, and top-trade concentration. Compare yearly single-training vs yearly WFO; flag any year where single-training looks strong but WFO collapses. |
| **Stage E — Pass/fail gate** | Pass only if at least **3/4 years positive**, total 4-year WFO positive, PF > 1.2, avg R positive, drawdown acceptable, no one year/regime dominates all profit, BUY and SELL are explainable, and WFO broadly agrees with single-training direction. If any year collapses, mark HOLD/REVISE instead of live scaling. |
| **Stage F — Final live train** | Only after the yearly validation ladder passes: train final live model on all available clean data (`2022 -> latest closed date`), save to `data/models/final` with backup, record feature list/model hash/data cutoff, and reference the WFO/yearly validation proof. Then demo/forward test before larger live size. |

> Always sorted by priority. P1 = do first. Full detail/history → WORKING_NOTES.md + FIXES_CHANGELOG4.md.
> **DECISION (2026-06-26): confirm all ideas on the CURRENT period first. Full-history is PARKED until then.**
>
> **▶ NEXT PRIORITY (2026-06-29, Anisa+Claude): edge is proven (regime-TP beats global on full-history**
> **AND WFO OOS). The remaining unknowns before scaling REAL money are DRAWDOWN + operational safety —**
> **NOT more edge-validation. Order: (1) P2b — measure real 3% drawdown ($10k sim; fixed-lot DD 1.7% is**
> **NOT the real figure, could be ~28-39%); (2) finish L8 safety + watch the L8 bug-fix holds on demo;**
> **(3) run demo 1-2 weeks on the locked config; (4) then scale real money small (consider risk 1-2% if**
> **DD high). PARK research (L2 A/B, more TP/buffer sweeps, ADX/news studies) until live is stable — don't**
> **add variables mid-validation. Global WFO re-run = optional/low-priority (regime already wins). DO LATER.**
>
> **TESTING STAGE-GATE (2026-07-12): Every feature/strategy result must be tagged by stage before it is trusted.**
> **Loop: Stage 1 = 3-month retrain backtest -> Stage 2 = 1-year single-training backtest -> Stage 3 = WFO ->**
> **Monte Carlo -> forward/demo -> small live. A 3-month result is screening only, never final proof.**
> **Checklist: `docs/STRATEGY_TESTING_STAGE_GATE.md`.**

### ✅ થઈ ગયું (DONE — 2026-07-13)
| # | Task (કામ) | પરિણામ |
|---|------------|--------|
| **Data-leakage guard** (Imtiyaz flagged: 07-12 backtests train/test overlap) | Hard-block permanent fix — `engine/leakage_guard.py` (NEW) reads a `*_meta.json` sidecar per model (main/buy/sell/state/HMM/slot-table), takes MAX exposure date across all, raises (not warns) if `>= backtest --from`. `train.py` writes sidecars for every model (previously only main+buy+sell had any) + atomic temp-dir swap (crash-safe, old models kept at `final_prev`). `backtest_replay.py` hard-exits unless clean or `--allow-in-sample` explicitly passed (loud banner, never default). `run_wfo.py` 1-day fold-boundary overlap also fixed (`QGAI_TRAIN_CUTOFF = week_start − 1 day`, not `week_start`). 9 automated tests (`engine/tests/test_leakage_guard.py`) — all pass. Real (non-synthetic) smoke-verified — **independently re-run by Imtiyaz on his own PC**: overlapping window correctly BLOCKED (leakage report + hard error), clean window correctly PASSED (+2.9R real backtest), live models correctly auto-restored after. Delivered as `.bat` (house rule): `Run_LeakageGuard_UnitTests.bat` + `Run_LeakageGuard_Smoke_TEST.bat`. Detail: `docs/FIXES_CHANGELOG4.md` 2026-07-13. |
| **Root cause found** | Training trades file (`Back_testing_data_final_cleaned_RELABELED.xlsx`) ends **2026-04-29 20:00** (2743 rows); 07-12's `*_TEST.bat`/`*_RETRAIN_TEST.bat` (OB redundancy, RemovedFeature-10, RawMove, RegimeScore, InRange sweep, LeakFix-P1P2P3, Legacy-CTFOFF) called `train.py` with no `QGAI_TRAIN_CUTOFF` then backtested `--from 2026-04-01` → Apr 1-29 (164 trades) in-sample. WFO-based bats (`run_wfo.py`) were already correct (own per-fold cutoff) except the newly-found 1-day boundary overlap, now also fixed. |
| **TP-cap/regime training-label parity bug — FIXED (code), retrain judged NOT worth it** | Imtiyaz's hypothesis confirmed: `relabel_trades.py`/`rebuild_trainset.py`/`shadow_ledger.py` used a flat 1.00% TP cap for every regime while live has used regime-adaptive TP (Ranging 2.0/Trending 1.0/Volatile 0.8) since 06-27. Cheap no-retrain diagnostic (Fable-5's recommended gate) measured **0.62% total label flips** (17/2,743 — Ranging 0.37%, Volatile 1.83%, Trending 0%), well under the 3%/5-7% retrain-justification gate — and win-prob models train on binary Win/Loss only (R never enters training), so 17 flips can't move an XGBoost boundary. **Full relabel+retrain+WFO explicitly NOT done** (Fable-5: ROI negative). **Code fix DONE anyway** (correctness + parity, esp. for `shadow_ledger.py`'s live-vs-shadow checks): added `CFG.filters.tp_by_regime` as the single source of truth in `config.py` (was duplicated as a literal in 4 files); `backtest_replay.py` now imports it (values unchanged, refactor-only); `relabel_trades.py`/`rebuild_trainset.py` now retro-classify each historical entry's regime via the EXISTING production `hmm_model.pkl` (no refit) and apply the matching regime TP cap; `shadow_ledger.py` reuses its already-logged `hmm_state` per signal (no HMM call needed there). All 5 touched files re-compiled clean. **Found + fixed a real bug along the way**: the new diagnostic/audit scripts (`diagnose_tp_cap_regime_labels.py`, `analyze_post_cap_continuation.py`) crashed with `ValueError: I/O operation on closed file` from a double `sys.stdout` UTF-8-wrap (they wrapped stdout themselves AND imported `analyze_capture.py`, which does the same wrap — the first wrapper's garbage collection closed the shared buffer); fixed by removing the redundant wrap in both. Detail: `docs/FIXES_CHANGELOG4.md`, `docs/FILTERS_MASTER.md` §CHANGE LOG, both 2026-07-13 (night). |

### 🟡 બાકી (REMAINING — BUY-signal audit follow-up, added 2026-07-13)
| # | Task | વિગત |
|---|------|------|
| **Model-version logging** | ✅ DONE 2026-07-13 — every signal now logs `model_version` (main model's `model_created_at`+`data_hash`) via `inference.py _make_result` + `bridge_data.log_signal` (CSV + SQLite migration, mirrors the `trade_action` column pattern). Verified via isolated smoke test (scratch files only). Closes the exact reproducibility gap the 04:30 BUY-signal audit hit. |
| **Volatile counter-HTF gate** ❌ REJECTED 2026-07-13 (night) | Signal-audit + Fable-5 second opinion found: honest 53-week WFO baseline shows Volatile-regime trades in the 42-48% win_prob band that go AGAINST dominant HTF direction are net-losing (n=38, -1.9R, PF 0.88) vs the same band aligned WITH HTF (n=48, +18.9R, PF 3.78). Confirmed NOT a time/slot confound. **CAVEAT found same day:** re-measured with raw ADX-DI instead of the SMMA-based `ts_htf_agreement` the gate actually uses — the "against" bucket flips to PROFITABLE (+1.57R) — flagged as possibly fragile/noise. **3-month WFO A/B (12wk, `Run_VolHTFGate_AB_WFO_TEST.bat`) CONFIRMED the caveat: Config A (gate OFF) +32.5R/207 trades/9-of-12 positive weeks vs Config B (gate ON) +17.1R/183 trades/8-of-12 positive weeks — B is -15.4R (-47%) WORSE than A, every week from 2026-05-04 onward.** Per the bat's own decision rule (B>=A required to proceed to the 53-week FULL WFO), **B<A → REJECTED, `Run_VolHTFGate_AB_WFO_FULL.bat` not needed.** `QGAI_VOL_HTF_GATE` stays OFF by default in `inference.py` (already env-gated, zero live impact — no revert needed). The SMMA-based `ts_htf_agreement` finding is confirmed fragile/noise, not a real edge. Results: `backtest/results/volhtfgate_wfo_TEST_A_off/_WFO_SUMMARY.txt`, `volhtfgate_wfo_TEST_B_on/_WFO_SUMMARY.txt`. |
| **67-feature validation sweep — 3-stage plan (Imtiyaz, detailed spec 2026-07-13)** | `engine/run_feature_sweep.py` redesigned around Imtiyaz's exact priority plan and now supports registry folders, cutoff/window overrides, and baseline reuse via `QGAI_SWEEP_BASELINE_JSON`. Organized runners live in `backtest/_runners/feature_sweep_67/`; organized results live in `backtest/results/feature_sweep_67/`. Screening runners: `FS67-01_RUN_PriorityBatch.bat` -> `FS67-01_priority_batch`; `FS67-02_RUN_Tier1_Active.bat` -> `FS67-02_tier1_active`; `FS67-03_RUN_Tier2_HighProbability.bat` -> `FS67-03_tier2_high_probability`; `FS67-04_RUN_Tier3_Remaining.bat` -> `FS67-04_tier3_remaining`. **Baseline rule:** `FS67-01` creates the 3-month baseline; `FS67-02/03/04` reuse `FS67-01_priority_batch/baseline/result.json` and do not rerun baseline. OOS1Y confirmation runner: `FS67-11_RUN_PriorityBatch_OOS1YConfirm.bat` -> `FS67-11_priority_batch_oos1y_confirm`, same cutoff/window as `OOS1Y-01` (`2025-06-28`, `2025-06-29 -> 2026-06-29`). Priority batch features: `h4_support_dist, h1_resist_dist, move_2hr, ts_line_dist_pct, tick_volume, H4_DI_diff, h4_adx_slope, move_4hr, momentum_aligned_2hr, h1_support_dist`. Optional all-in-one screening runner: `FS67-00_RUN_ALL.bat`. Each feature auto-routed to ablate (if active) or unprune (if dropped), computes BUY/SELL split, regime split, week consistency, capture-efficiency, and verdict. **Best decision flow: FS67-01 quick 3-month screen -> OOS1Y confirm for candidates -> WFO before live adoption.** **⏳ NEXT: run `backtest/_runners/feature_sweep_67/FS67-02_RUN_Tier1_Active.bat` (baseline reused).** |
| **▶ Post-cap continuation audit — FIRST step of the exit-work stream (Fable-5, 2026-07-13 night)** | `engine/analyze_post_cap_continuation.py` (NEW) + `Run_PostCapContinuationAudit_TEST.bat` — for every TPCAP-exited trade in the existing `active_baseline` feature-sweep run, replays forward using the SAME H1-line trail + HTF-flip exit already live, measures extra pts/R gained or given back had the cap not force-closed the trade. Read-only, no retrain, runs in seconds off the trades CSV already on disk. **This is the decision gate for the whole smart-Exit-AI question (see plan row below) — its result decides whether TP-cap-as-trail-tighten redesign is worth doing at all.** **Sequencing (Imtiyaz, 2026-07-13 night): run this AFTER the 67-feature validation sweep (row above) finishes its nightly runs — this audit is the first task of the SEPARATE exit-side work stream, starts once feature-sweep work is done.** ⏳ NEXT: run `Run_PostCapContinuationAudit_TEST.bat` (fast, can run any night feature-sweep isn't using the PC). |
| **BUY/SELL blend-weight asymmetry** | Fable-5 flagged: `dir_weight` is 0.35 for BUY vs 0.45 for SELL (`inference.py` routing block) — SELL leans harder on its directional model. Reason for the asymmetry not yet investigated — pending. |
| **Volatile 0.42% threshold contradictory evidence** | Fable-5 flagged: code comments cite two different Volatile win-rate stats (70.2% vs 37.7%) as the basis for the threshold discount. Needs reconciling — pending. |
| **⏳ PLAN (not started, now UNBLOCKED) — Volatile-state model: add raw H1/H4 DI + SMMA 1h/4h trend features** (Imtiyaz, 2026-07-13) | Confirmed on the 04:30 signal (both `H1_DI_diff=-19.79`/`H4_DI_diff=-17.01` AND `ts_trend_h1=-1`/`ts_trend_h4=-1` genuinely agreed bearish — not a fragile/divergent case) that `model_volatile.pkl`'s 17-feature list has neither raw ADX/DI nor the SMMA `ts_trend_h1/h4` features — it only sees momentum/EMA/slot stats, so it can't down-weight a signal that both HTF systems call bearish. **The VolHTFGate WFO A/B (row above) is now DONE — REJECTED (B<A), so this plan is no longer blocked, but note the gate's rejection + the fragile-vs-raw-ADX caveat found alongside it are a reason for EXTRA caution here: the underlying "counter-HTF is bad in Volatile" signal did not hold up OOS, so this feature-addition plan should not assume that premise — treat it as an open feature-engineering experiment, not a confirmed-edge implementation.** (1) add `H1_DI_diff`, `H4_DI_diff` (and consider `H1_ADX`/`H4_ADX`) + `ts_trend_h1`, `ts_trend_h4` to `VOLATILE_FEATURES` in `engine/features.py`. (2) Full retrain (not core-only) so `model_volatile.pkl` actually gets the new columns. (3) Check feature-importance output — confirm the model actually USES the new features (not just present-but-ignored). (4) Full stage-gate: 3-month screen → 1-year → WFO (leakage-guard-safe cutoffs this time, unlike 07-12's in-sample mistake) — compare Volatile-regime R/PF/DD vs current baseline. (5) Adopt only if WFO doesn't hurt Volatile regime's current +36.5R/PF 1.89 baseline. Related: [[project_htf_direction_architecture_rethink]] memory — this is the first concrete, scoped piece of that bigger architecture question. **Status: plan only, nothing implemented.** |
| **Feature-sweep: capture-efficiency tracking** ✅ DONE 2026-07-13 (night) | 3rd Fable-5 opinion (goal: find profitable features while capturing 10-20% of available move, not just +R): `run_feature_sweep.py` now parses `captured_pts`/`available_pts`/`efficiency_pct` from each backtest report, flags any feature where captured points drop >10% vs baseline even if R improved (catches "R up but capturing less of the move"), and writes 3 new columns to every tier's `*_SUMMARY.csv`. Fable-5's other point (HTF H1-flip exit as the bigger lever) checked against `config.py` — **already live** since 06-23/26/30, no action needed there. Detail: `docs/FIXES_CHANGELOG4.md` 2026-07-13 (night). |
| **Capture-audit refresh: 2.9% vs 5.7% explained** ✅ RESOLVED 2026-07-13 (night) — NOT a bug. Both `analyze_capture.py` (5.7%, 06-23) and `backtest_replay.py` (2.9%, current) compute "available path" identically. Real cause: `ratchet_tp_cap_pct` was 10.0% (near-unconstrained) at the 06-23 measurement, then tightened to 1.00% (06-26) and made regime-adaptive down to 0.8% in Volatile (06-27, `ratchet_tp_regime=True`) — both deliberate profit-optimizing choices (best in-sample R/PF). Proof: current `active_baseline` report exit-mix = 44/131 (34%) trades exit via TPCAP, capping profit at 0.8-2.0% regardless of further move. **Real trade-off, not fixable for free:** wide/no TP cap → more path captured, worse R/PF; tight regime-TP → less path captured, better R/PF (per existing 06-26/27 evidence). Recovering 10-20% capture would need a new dedicated wide-TP-vs-tight-TP A/B — not yet run, would need to re-litigate the 06-26/27 TP decision. Detail: `docs/FIXES_CHANGELOG4.md` 2026-07-13 (night). |
| **⏳ PLAN — smart Exit-AI vs rule-based exits (4th Fable-5 opinion, 2026-07-13 night)** | Imtiyaz asked: could a dedicated exit-ML-model capture more move AND stay smart (not give back profit)? Fable-5's independent verdict, in priority order (detail: `docs/FIXES_CHANGELOG4.md`): **(1) pushback on the capture% metric itself** — "% of total path length (sum of all bar-to-bar moves)" is an ill-posed denominator (shrinks/grows with bar granularity); recommends switching to **per-trade MFE-capture ratio** (realized profit ÷ Maximum Favorable Excursion) as the real target, retiring the "10-20% of path" framing. **(2) Exit-AI is NOT the right first lever** — 3 cheaper steps come first: (a) a same-day "post-cap continuation audit" (measure how far price kept moving in-trade-direction after the 44 TPCAP-capped trades hit their cap, before the eventual HTF-flip — this alone tells us if there's real money left on the table); (b) **main recommendation: stop hard-closing at the TP cap — instead either partial-exit 50-70% at the cap and let the rest trail, or switch to a MUCH tighter trail (e.g. M15-line/0.05-0.08% buffer instead of H1-line/0.20%) at the cap-touch moment.** Fable's core insight: the TP cap's real job is "giveback insurance," not "profit ceiling" — trail-tightening gives the same insurance without capping the upside, so the R/PF-vs-capture conflict found earlier may be an artifact of the current binary (hard-close) design, not fundamental; (c) re-check whether the current single/regime TP-cap % itself is overfit to a thin 131-trade sample before trusting it further. **(3) If exit-AI is still pursued after (2):** keep it narrow — a binary gating classifier (p(continuation)) invoked ONLY at 2 decision points (cap-touch, HTF-flip-moment), never a free-running per-bar policy or RL agent (over-engineered, leakage-prone, unsupported by sample size). **(4) Biggest risk flagged: sample size** — entry model has ~98k bars, but an exit model's effective N ≈ trade count (131) since in-trade bars are heavily autocorrelated; Fable says do not start exit-AI training below ~500-1000 trades. **(5) Labels:** triple-barrier method (López de Prado) — ATR-scaled favorable/adverse barriers over a forward window, features strictly ≤ t, trade-episode-level CV grouping (never split one trade's bars across train/test), purge+embargo at fold boundaries, evaluate via OOS total $ replay — never via classifier AUC alone. **Status: opinion only, nothing implemented. Recommended sequence: (a) post-cap continuation audit first → (b) TP-cap-as-trail-tighten redesign + WFO A/B → (c) switch north-star metric to MFE-capture → (d) grow trade sample → (e) only then consider exit-AI phase 1.** |

### 🟡 બાકી (REMAINING — leakage-guard follow-up, added 2026-07-13)
| # | Task | વિગત |
|---|------|------|
| **Re-run 07-12 in-sample results** | ~30 result folders (`ob_redundancy_*`, `removed_feature_*`, `regimescore_*`, `rawmove_ab_*`, `individual_ab_*`, `combo_b3b4_*`, `inrange_sweep_*`) were produced BEFORE the guard existed — in-sample-contaminated. Re-run with a real `QGAI_TRAIN_CUTOFF` before the backtest start (guard now enforces this) before trusting any KEEP/REJECT decision drawn from them. |
| **Re-validate the already-committed B3-only prune** (commit `10fad5f`) | This was adopted live based purely on in-sample 1-month A/B (`individual_ab_B1-B4`, `combo_b3b4`), no WFO gate. Re-run clean (cutoff before backtest start) + WFO before trusting it stays the right call. |

### 🟡 બાકી (REMAINING — original live-conservatism concern, Fable-5's recommended next step, 2026-07-13 night)
| # | Task | વિગત |
|---|------|------|
| **✅ DONE 2026-07-13 (night) — win_prob calibration diagnostic built** | `engine/diagnose_win_prob_calibration.py` (NEW) + `Run_WinProbCalibration_TEST.bat` — uses the ALREADY-EXISTING 3-month WFO OOS trades (`volhtfgate_wfo_TEST_A_off/ALL_OOS_trades.csv`, 207 real executed trades — no new model inference needed, `win_prob` + realized `r_achieved` + the raw `f_H1_DI_diff`/`f_H4_DI_diff`/`f_ts_trend_h1`/`f_ts_trend_h4` features are all already in that file). For each trade, counts how many of the 4 HTF-direction signals agree with the direction actually traded → buckets `aligned_strong` (4/4 agree) / `aligned_weak` (3/4) / `mixed_disagree` (≤2/4), then compares **avg PREDICTED win_prob vs REALIZED win-rate** per bucket. A clear positive gap in `aligned_strong` (realized notably above predicted) would confirm systematic underconfidence exactly when ADX+SMMA agree — the concern that triggered this whole investigation. **Caveat noted in the report itself:** this dataset is EXECUTED trades only (already passed threshold) — it can show whether the model is honest about trades it takes, but can't directly prove good trades were wrongly SKIPPED; if a real gap shows up, Fable-5's Step 3 (shadow-simulating skipped bars too, for missed-profit $) is the next-more-expensive step, not a feature-architecture change yet. Read-only, no training, `py_compile` clean, bat checked for non-ASCII chars (none). Not run — Imtiyaz runs it on his own PC. **⏳ NEXT: run the bat, read the gap per bucket.** |

### ✅ થઈ ગયું (DONE — 2026-07-11)
| # | Task (કામ) | પરિણામ |
|---|------------|--------|
| **in_range_phase REGIME-SWAP A/B FULL YEAR** REJECTED (2026-07-12) | Full-year A/B replay: A=`QGAI_REGIME_INRANGE=0` OFF vs B=`QGAI_REGIME_INRANGE=1` ON | **A OFF = +206.6R BEST**, B ON = +204.9R (`-1.7R`). Trades/WR/PF/DD same: 808 trades, 56.1% WR, PF 1.89, max DD 3.8%. Difference only in Volatile regime: A +84.0R vs B +82.3R. Runner rule says B >= A confirms; B < A means revert. **Decision: keep `QGAI_REGIME_INRANGE=0`; do not adopt regime-swap ON.** Results: `backtest/results/inrange_regimeswap_FULL_A_off/` and `backtest/results/inrange_regimeswap_FULL_B_on/`. |
| **ADX-Death WFO NO-VOLUME** ❌ REJECTED (2026-07-11) | 53-week OOS WFO (NO-VOLUME model): baseline + K3N4X1.0 + K3N4X0.3 | **Baseline (OFF) = +80.5R BEST.** K3N4X1.0 = +73.6R (−6.9R). K3N4X0.3 = +60.8R (−19.7R). ADX-Death filter hurts OOS profit — blocks profitable trades. Gate +444.7R nowhere near. Results: `backtest/results/wfo_adxdeath_novol_*_20260710/`. Bat: `Run_ADXDeath_WFO_Validate.bat`. |
| **Volume AUC comparison** (2026-07-11) | AUC effect of volume/tick_volume features on model | A (no volume) Test AUC 0.6167 baseline. B (+volume norm) 0.6164 (−0.0003). **C (+tick_volume raw) 0.6219 (+0.0052 best)**. D (+both) 0.6057 (−0.011 hurt). tick_volume raw = marginal AUC gain but WFO profit negative → volume features stay EXCLUDED. Script: `engine/auc_volume_compare.py`. |
| **RAW-VOL feature** ❌ CLOSED (2026-07-11) | tick_volume raw feature — full evaluation complete | AUC: +0.005 marginal. WFO NO-VOLUME model (+80.5R) outperforms volume model. ADX-Death + volume combos all worse. **Decision: volume features (both raw + normalized) permanently excluded from model.** Remove `tick_volume` from `_MANUAL_PRUNE` comment "keep out" → confirmed correct. |
| **ET1** ⏸️ PARKED (2026-07-11) | Entry-timing redesign — trend-following pullback entry (ATR-free) | **v1 BLOCK** → REJECT (block only REMOVES trades, cuts winners). **v2 GENERATE** → 96 signals fire but `max_open=1` → 0 net new trades, 7 combos baseline-identical. **Nil impact under max_open=1.** Both flags OFF, live=baseline, reversible. Revisit only if `max_open=2` adopted or GEN gated to flat+SKIP only. Design: `docs/ENTRY_TIMING_REDESIGN.md`. |

### ✅ થઈ ગયું (DONE — 2026-07-09)
| # | Task (કામ) | પરિણામ |
|---|------------|--------|
| **Feature leakage fix** (2026-07-09, Imtiyaz flagged) | `corr_imp_ratio` PRUNED + `in_range_phase` H4 lookahead fixed | **`corr_imp_ratio`** (rank #28, 0.022): swing detection uses future bars (i+1,i+2,i+3 = 12h+ lookahead). AUC test: −0.014 test AUC (negligible) → added to `_MANUAL_PRUNE` + removed from `RANGING_FEATURES`. **`in_range_phase`** (rank #1, 0.071): `get_range_features()` included incomplete H4 candle (~3.75h future M15 data). AUC test: removing = −0.074 (too valuable to drop). Fix: `searchsorted(datetime+4h)` → only COMPLETED H4 candles. Fable-5 confirmed both leakage paths. Test bat: `Start/6_Test_Leakage_AUC.bat`. **⚠️ NEEDS RETRAIN + WFO-GATE** (now 35 features, honest `in_range_phase`). |
| **Signal↔Trade DECOUPLE** | Imtiyaz architecture: signal = pure engine (BUY/SELL/SKIP) દરેક bar, backtest જેવું; trade execution ને signal સાથે કોઈ સંબંધ નહીં; account ના હોય તોય signal બંધ ન થાય | `bridge_main.py` 11 log_signal sites હવે real `signal` + નવો `trade_action=` (EXECUTED/EXEC_FAILED/HOLD_IN_TRADE/BLOCK_*/MONITOR/NO_TRADE...). `bridge_data.py` નવો `trade_action` column (CSV+SQLite+migration). 78.59%→SKIP bug fixed → હવે signal=BUY, trade_action=HOLD_IN_TRADE. Test: `Test_Decouple_Signal.bat` **10/10 PASS** (offline, live files untouched). Trade-logic UNCHANGED. Dashboard SIGNAL LOG માં `trade_action` colored badge ઉમેર્યો (EXECUTED/HOLD_IN_TRADE/BLOCK_*/EXEC_FAILED...). **NEXT: bridge + dashboard restart કરી activate કરવું.** |
| **Decision area = છેલ્લો BUY/SELL signal** | Imtiyaz: signal box + AI summary + Market Intelligence માં latest SKIP bar નહીં પણ **છેલ્લો પડેલો signal** (BUY/SELL) એના દરેક param સાથે દેખાય | Backend `bridge_dashboard.py`: `_remember_last_trade_signal()` cache (persist `logs/last_trade_signal.json`, restart-safe); `write_dashboard` line ~508 પર `sig` ને છેલ્લા BUY/SELL થી freeze — આખો decision block (prob/market_structure/ev_r/risk_grade/ai_summary/market_intel) એમાંથી derive થાય એટલે coherent. Live price/session/countdown `tick` માંથી → live રહે. Cached signal પર `signal_confirmed=True` + નવો `signal_is_cached` flag. Frontend `dashboard.html`: 🕒 last @ HH:MM hint. **Activation: bridge restart (backend).** |
| **SIGNAL LOG win% dim on SKIP** | Imtiyaz: SKIP row પર win% gold ના દેખાય, SKIP-text જેવો dim | `dashboard.html _liveSigRender`: gold ફક્ત BUY/SELL ≥45% પર. Browser refresh. |
| **SIGNAL LOG: virtual entry→exit→move દરેક BUY/SELL પર** | Imtiyaz: log માં દરેક buy/sell નો price move (દા.ત. 4076→4100 = +$24) દેખાવો જોઈએ — trade પડ્યો હોય કે ના — અને exit price calc દેખાય | Root: exit calc પહેલેથી છે (`shadow_ledger.py` દરેક signal ને live exit rules થી paper-trade કરી entry/exit/R/pnl કાઢે; scheduler દર 15min refresh; 821 signals). ખૂટતું હતું display. Fix (**dashboard-only, engine untouched**): `dashboard.html _liveSigRender()` હવે દરેક BUY/SELL પર shadow માંથી inline `4076.00→4100.00 +$24.00 +2.5R TPᵛ` (green/red, dashed) બતાવે — trade પડે કે ના પડે. Real trade close થયો હોય તો extra `WIN/LOSS +$move REAL` solid chip અલગ. **Activation: dashboard browser hard-refresh (bridge restart જરૂરી નથી).** |
| **SIGNAL LOG: HOLD → EXIT lifecycle** (2026-07-09, Imtiyaz idea — "buy hold exit / sell hold exit") | Log માં દરેક bar પર નવો independent BUY/SELL/SKIP row આવે, ભલે એક trade already ખુલ્લું ચાલતું હોય — Imtiyaz ને trade lifecycle story જોઈતી હતી (entry → holding → final result), rows ની noise નહીં | **Option A પસંદ કરી** (Fable-5 second-opinion લીધો — Option B "live decision-logic માં HOLD" સાફ ના પાડ્યું: Signal↔Trade DECOUPLE architecture ને undo કરે, flip-mechanism તોડે, backtest≠live parity તોડે — rejected). **Implemented (dashboard-only, additive, engine/signals_all.csv અડ્યા વગર):** `dashboard.html` — `_loadShadow()` હવે `shadow_trades.csv` માંથી `exit_time`+`direction` પણ પાર્સ કરે, દરેક entry માટે `[entry_time, exit_time)` "open window" બનાવે (`_shadowWindows`). `_liveSigRender()` માં નવા હેલ્પર `_holdWindowFor(bt)`/`_exitWindowsFor(bt)`: entry-exit ની વચ્ચેના bars પર 🔒 `HOLD <dir> @<entry_price>` badge (dotted, dim) ઉમેરાય — **raw signal (BUY/SELL/SKIP) hide નથી થતું**, ડાબે એમ જ દેખાય (Fable-5 ની ચેતવણી પ્રમાણે, નહીંતર flip debug અશક્ય બને); exit bar પર 🏁 `EXIT WIN/LOSS ±R ← entry-time` badge. Node.js વડે sandbox simulation (synthetic shadow+signal CSV) થી verify કર્યું: BUY@10:00 → SKIP@10:15 બતાવે 🔒HOLD BUY badge → SKIP@10:30 બતાવે 🏁EXIT WIN +1R badge — બરાબર ઈચ્છિત narrative. Real trade (`real_executed=1`) ના entries માટે tooltip માં "REAL trade also placed" દેખાય. Multiple concurrent shadow trades (shadow ledger no max_open) હોય તો સૌથી તાજું-ખૂલેલું window પસંદ થાય (display simplification, ledger નહીં). **Activation: dashboard browser hard-refresh (bridge restart જરૂરી નથી).** |
| **SIGNAL box/AI SUMMARY = SKIP while LOG = BUY (Imtiyaz-flagged mismatch)** | SIGNAL box + 🧠 AI DECISION SUMMARY બંને SKIP બતાવે, SIGNAL LOG નો એ જ bar BUY બતાવે — છતાં EV +1.05R/Grade A/AI-summary votes બધા BUY ના જ (SKIP માટે એ `--`/null હોવા જોઈએ) | Live data થી root-cause confirm કર્યો: `signals_all.csv` છેલ્લો row `signal=BUY, trade_action=HOLD_IN_TRADE` (legitimate, block નહીં); `dashboard.json` એ જ ક્ષણે `signal_confirmed:false` છતાં `ev_r:1.05` (non-null — proof backend એ ખરેખર BUY જ decide કર્યું). Root: `bridge_main.py`નું intra-bar heartbeat write (દર ~30s, bar close વચ્ચે) `core._last_signal` (already-decided) એ જ dict ફરી મોકલે પણ hardcode `signal_confirmed=False` — frontend (`dashboard.html` signal box + `renderAISummary():1556`) એને "gate-blocked" સમજી SKIP બતાવે, ~15 મિનિટ સુધી (next bar close સુધી), page refresh થાય ત્યારે ખાસ દેખાય. **Fix:** [bridge_main.py:361-364](../engine/bridge_main.py:361) — `signal_confirmed=bool(core._last_signal.get("signal"))` (hardcoded False ની જગ્યાએ). `_pre_pop_dashboard`ના genuine startup-probe `False` calls અડક્યા નથી. `py_compile` clean. Dashboard-display only, live trading logic અડકતું નથી. **Activation: bridge restart (backend Python ફેરફાર).** |
| **SIGNAL box: SKIP → HOLD when a real trade is already open+profitable** (2026-07-09, Imtiyaz — "i need hold instead of skip becuse already buy in profit") | Real bar-close SKIP (genuine, win_prob 39.26% < threshold — not the bug above) છતાં bot નું real BUY position ખુલ્લું+profit માં ચાલે છે — "SKIP" શબ્દ "કંઈ થતું નથી" જેવો misleading લાગે | **Display-only** (`dashboard.html`, engine/`signals_all.csv` અડ્યા વગર): નવો `_openPos`/`_holdNow` check (`d.open_trades` માંથી — પહેલેથી dashboard.json માં મોકલાય છે) — actionable signal SKIP હોય **અને** real position ખુલ્લું હોય તો SIGNAL box + AI DECISION SUMMARY બંનેમાં headline **"HOLD <BUY/SELL>"** (cyan) બતાવે, tag માં `🔒 holding BUY +2.41R` (direction+profit_R, color green/red પ્રમાણે). Real SKIP with કોઈ open trade ના હોય તો plain "SKIP" જ રહે (unchanged). CSS: `.sig-big.HOLD`/`.sig-dir-block.HOLD` ઉમેર્યા. Node.js sandbox unit-test: real-SKIP-no-trade → "SKIP" ✓, SKIP+open-BUY+2.41R → "HOLD BUY" cyan ✓. `signals_all.csv`/live trading logic બિલકુલ અડ્યું નથી. **Activation: dashboard browser hard-refresh (bridge restart જરૂરી નથી).** |

### ✅ થઈ ગયું (DONE — 2026-07-08)
| # | Task (કામ) | પરિણામ |
|---|------------|--------|
| **ADX-death exit** ❌ REJECTED | Imtiyaz idea + Fable-5 design: K/4 TF ADX slopes ≤0 for N bars + profit ≥ X×R → exit | Code DONE. **18-cell sweep DONE (2026-07-09):** in-sample top-2 K3N4X1.0 +409.1R, K3N4X0.3 +404.7R. **NO-VOLUME WFO validation (2026-07-11):** 53-week OOS baseline (OFF) **+80.5R best**, K3N4X1.0 +73.6R (−6.9R), K3N4X0.3 +60.8R (−19.7R). **Filter hurts OOS — REJECTED.** Results: `backtest/results/wfo_adxdeath_novol_*_20260710/`. |
| **Ablation AUC study** | 10-test Clean-34 feature ablation (AUC impact, no model saved) | **DONE (2026-07-09).** Results: `data/ablation_results_clean34.json`. Bat: `Start/7_Ablation_10_Tests.bat`. Key: trend-signal BEST removal (AUC +0.013), tick_volume removable (+0.008), ALL OB/SR removable (+0.008), slot_win_rate KEEP (AUC −0.013). hmm_state NOT in main FEATURE_COLS (hybrid-only, no effect). **Feature removal = one-by-one with WFO per step → see RUNNING "Ablation".** |
| **PART 2 composite REJECTED** | 10 raw ADX → 5 tanh composites | WFO +405.6R vs +444.7R = −39R. Higher AUC but lower R → "accuracy ≠ profit." Bats DELETED. |
| **max_open=2 REJECTED** | User caught R-unit measurement artifact | Fixed-lot 0.01×2 = double risk. Dollar return at 3% total: max_open=1 beats max_open=2 (6.85M% vs 4.95M%). 95% same-direction overlap = correlated bet. |
| **Volume-exit DEAD** | Non-monotonic, tautological, broker tick_volume = noise | Conditional table: within each ADX-death bucket, volume adds nothing. Permanently closed. |
| **TP-sweep in-sample** | Wider TPs win: Rng2.8/Trn1.4/Vol1.0 | In-sample done. WFO validation pending (do AFTER ADX-death). |

### ✅ થઈ ગયું (DONE — 2026-07-07 major session)
| # | Task (કામ) | પરિણામ |
|---|------------|--------|
| **CTF-OFF** | `skip_counter_trend_fade` True→False (LIVE) | Path-A live-parity BT: CTF-OFF **+384.5R vs +350.2R = +34.3R (+9.8%)**, WR +0.4pp, PF +0.20. CTF blocked 0/3-aligned 77%-WR edge. Reversible: `QGAI_CTF_FADE=1`. |
| **Feature PART 1** | drop 6 dead EA-combo features (41→35) + retrain | Static full BT first gave **+393.4R**; weekly-retrained WFO then gave **+444.7R = +51.3R (+13.0%) lift**, 51/53 positive weeks, worst -0.4R. New honest WFO baseline = +444.7R. |
| **FAB-S4** | vSL persistence (`vsl_persist.py`) | trailed vSL survives restart (was reset to entry). Verified live 4× (4119→4142). Broker SL 3×→1.5×. |
| **FAB-S3** | live DD brake (`dd_brake.py`) PER-ACCOUNT | dd>10%→½/20%→¼/30%→halt. Enabled live. **Bugfix same-day:** global peak poisoned mirror accounts → per-account (login-keyed) fix. |
| **FAB-S1** | reversal-entry gating (flag, default OFF) | reversal re-entry passes filter stack when `gate_reversal_entries=True`. |
| **FAB-S2** | news staleness check (`news_updater.py`) | startup banner if calendar stale; was false-positive (file OK through Dec 2026). |
| **FAB-H6/H8/H9** | replay-ADX as-of · checkpoint sig env+mtimes · ADX-gate live-wire | parity/integrity fixes (details FIXES_CHANGELOG4). |
| **FAB-M11** | picker prefers non-SKIP over higher-prob SKIP | prime-directive fix (live+backtest). |
| **FAB-M12/M14** | parity-gap doc table · config re-enable-trap cleanup | SMMA "PROVEN HARMFUL" comment; dead session keys marked. |
| **Dashboard** | config badges + Account-Health/Risk-State panels + Signal-log rebuild | per-account fill status, DD band, vSL $ risk, daily-SL headroom (Fable-5 review). `Rebuild_SignalLog.bat`. |
| **Master launcher** | `Start/0_START_ALL.bat` | one-click cold-start (data+chart+shadow+signal-log+bridge+dashboard, minimized). Training deliberately EXCLUDED (stays `3_Train_Models.bat`). |
| **Model-mismatch** | fixed (composite→raw restore) | PART 2 composite retrain + env-leak caused live train/serve skew; restored validated raw-36 (`_backup_part1_raw35`). Verified match. |

### ✅ થઈ ગયું (DONE)
| # | Task (કામ) | પરિણામ |
|---|------------|--------|
| P1 | Relabeled data પર model retrain | model 06-28, 2743 trades |
| P2 | WFO OOS — **regime-TP adopt** કર્યું | +266R / PF 3.35 / 60% WR (HTF, live-matched) |
| P2b | $10k 3% sim — Max DD | **REFINED 2026-07-03: real leak-free OOS max DD = 14.6%** (`wfo_asof_rel`, 723 tr, +393.9R, WR 63.2%, dynamic 3% compounding, stitched OOS curve; baseline `wfo_live_match_015` = 11.5%). NOT the feared 28-39%. Raw/un-braked (cross-week DD-brake not applied → live brake keeps it lower). Caveat: every OOS month positive = optimistic; assumes backtest fills=live, real slippage/news can deepen it. → 3% DD-tolerable; watch actual DD on demo. Script: scratchpad/oos_dd.py. |
| P3 | Regime-TP ને live bridge માં wire | config-gated ✅ reversible |
| L1 | Full-history backtest 2022→2026 | **edge OOS confirmed** (2022-24 unseen, PF 2.8-3.5) |
| L4 | Open bugs **A + F** | fixed |
| L7 | Stale labels (ATR/counts/hybrid) | labels fixed |
| L8 | Deposit/withdrawal-aware equity | **safety fix** (false-trip ટાળે) |
| L9 | Complete signal log (`signals_complete.csv`) | દરેક candle + $/% @0.01 lot |
| L10 | `live_trades.csv` schema | corruption fixed |
| — | **Bug fixes** F·G·H·I·J·K | બધા fixed (backtest=live) |
| — | **Validation docs** | client `.docx` + `VALIDATION_RESULTS.md` |

### 🔄 અત્યારે ચાલે છે (RUNNING / NOW)

> **🧭 KEY FINDING (2026-07-12): the old +444R/+384R were LOOKAHEAD-INFLATED** (in_range_phase leak pre-07-09 + ADX leak pre-07-03, both now fixed). **Honest WFO baseline ≈ +80R and it is TRUSTWORTHY** — full leakage audit (`docs/LEAKAGE_AUDIT_20260712.md`) verified ADX + trend-signal families are leak-free (drift 0.0000). So R must be raised by GENUINE signal, NOT by un-fixing leaks. Priorities below.

#### 🥇 Priority track (2026-07-12, after leakage audit)
| P | Task | Why / detail | Effort | R effect |
|---|------|--------------|--------|----------|
| **P1** | ✅ CODE DONE 2026-07-12 — **DROPPED `corr_imp_ratio`** (chose drop over gate-fix: honestly-gated = 16h-stale near-useless; redundant with honest ts_trend_h4/h4_ADX/in_range_phase). 35→34 feat. **⏳ awaiting retrain + WFO gate** (bat below). | Double leak: swing reads 3 future H4 (`iloc[i+j]`) + gate ~16h early. LOW impact. | small | ~neutral (cleans leak) |
| **P2** | ✅ CODE DONE 2026-07-12 — **`ob_strength` confirm `shift(-1)`→`shift(-2)`** (impulse candle fully closed before OB visible). **⏳ same retrain+WFO.** | Partial-candle leak; 2 model features. Zones already safe. | small | tiny |
| **P3** | ✅ CODE DONE 2026-07-12 — **`dev_norm` → expanding past-only z-score** (no future event releases). Unit-checked. **⏳ same retrain+WFO.** | Global-stats leak; news only. | small | tiny |
| **P1-3 GATE** | ✅ NOT NEEDED SEPARATELY (2026-07-12) — P1 (corr_imp_ratio) already in `_MANUAL_PRUNE`, P2 (ob_strength shift-2) + P3 (dev_norm expanding) already in code. Fresh 33-feat retrain (`3_Train_Models.bat`) automatically includes all 3 fixes. No separate WFO gate bat required. | — | — | — |
| **RANGE** | ✅ REMOVED (config) 2026-07-12 (Imtiyaz) — `skip_range_phase_entry` True→False. Was the #1 entry-stopper (~63% of actionable BUY/SELL on honest model), added post-hoc w/o a gate. **1-month A/B smoke (honest model): OFF = +8.9R / 63 tr / 60.3% WR / PF 1.95 vs ON = +0.9R / 29 tr / 55.2% / PF 1.45 → OFF ~10× better, WR UP.** Filter was blocking WINNERS. Confirms removal. Reverses old leaky in-sample (+10R ON). **⏳ NEXT: `Run_Range_AB_Backtest.bat` full-year confirm, then WFO.** | small | **+8R (1mo smoke)** |
| **Filter #2 pre-news** | ✅ REMOVED 2026-07-12 — pre-news +0.05 penalty → 0.0 (inference.py default). 1-month A/B = identical +8.9R/63tr (0 pre-news trades hit — rare). Philosophy-driven ("model over filters"), reversible env `QGAI_PRENEWS_PENALTY=0.05`. Full-year read unmeasured. | small | nil (1mo) |
| **Filter #4 early-discount** | ✅ STAYS OFF 2026-07-12 — 1-month A/B = identical +8.9R/63tr. Nil impact under max_open=1 (like ET1). Parked. | small | nil |
| **Filter #3 ratchet-line** | ⛔ DEFERRED 2026-07-12 — NOT a clean entry-filter A/B: "skip when no ratchet line" is tied to the whole ratchet-exit system (`_ratchet_on`); removing = no trailing SL = different strategy, not a filter toggle. Skip. | — | — |
| **Filter #1 min_win_prob** | ⏳ LATER (Imtiyaz: test #2/#3/#4 first) — lower regime thresholds (0.42-0.48 −0.05) = more trades, trust model more. Biggest lever. Build A/B after #2/#4. | small | TBD |
| **🧹 FILTER CODE-CLEANUP** (Imtiyaz 2026-07-12) | ✅ DONE 2026-07-12 (per Imtiyaz — without waiting for range full-year) — deleted filter code, net −87 lines, git-reversible: (a) **RANGE** — `backtest_replay.py` range block → `_range_block=False` const + `--no-range-skip` arg removed; `bridge_main.py` BLOCK_RANGE block → const. Range config keys KEPT (dashboard/log-banner read them). (b) **#2 PRE-NEWS** — inference.py pre-news penalty collapsed to plain regime threshold + `QGAI_PRENEWS_PENALTY` gone. (c) **#4 EARLY-DISCOUNT** — inference.py block deleted (`_ed_disc=0.0` kept) + config keys removed + `QGAI_EARLY_DISCOUNT`/`QGAI_ED_*` gone. Downstream compound conditions + CSV/dashboard schema untouched. | small | — |
| **🐛 BUG-CHECK after filter removals** | ✅ CODE-LEVEL DONE 2026-07-12: 4 files syntax OK, imports OK, NO dangling refs (only REVERT comments), range cfg-key present (dashboard safe), early_entry_discount key gone. **⏳ PARITY smoke:** `Run_FilterRemoval_Parity_TEST.bat` MUST = +8.9R/63tr (range_ab_TEST_OFF). Diff → bug. | small | — |
| **RAW-MOVE feature fix** | ❌ REJECTED 2026-07-12 — raw `h4_move_pct`+`cum3_move_pct` tested both ways: single-backtest B +6.8R vs A +8.9R (WR 54.5% vs 60.3%) AND WFO ~5wk B +8.9R vs A +11.7R. Model did NOT learn/improve from raw in WFO either — added noise, not signal. Binary `in_range_phase` is cleaner. Removed from FEATURE_COLS; baseline model restored (`_backup_pre_rawmove_20260712`, 35-feat +8.9R). | small | neg (rejected) |
| **Per-model importance check** | ✅ DONE 2026-07-12 (Imtiyaz observation: "0.0000 in training importance ≠ useless — may matter in another model") — checked all 6 models (main/buy/sell/ranging/trending/volatile) for every current + PART-1-pruned feature. **Confirmed the hypothesis for 2 features**: `h4_h1_regime_score` = 0.0622 in VOLATILE (vs 0.0265 in main, was pruned on main-only 0.0), `h4_ranging_h1_neutral` = 0.0369 in BUY (0.0 in main). Others (`h4_trending_h1_aligned`, `trade_direction`) genuinely ~0 everywhere — stay pruned. | — | — |
| **in_range_phase REGIME-AWARE cutoff** | ✅ APPLIED 2026-07-12 (Imtiyaz) — 1-month threshold sweep (0.3-0.7%) showed per-regime optimum differs: Trending peaks 0.5% (+5.2R), Volatile peaks 0.6% (+8.5R), Ranging noisy (kept 0.5%). Global 0.5% was hiding this trade-off. Implemented in `inference.py` right after `hmm_state_name` is known (before model routing) — overrides `feat_dict["in_range_phase"]` using the regime-specific cutoff on raw `h4_move_pct`. Applies to BOTH live and backtest (same `LiveInferenceEngine.decide()`). No retrain needed (in_range_phase stays a binary model input). Master toggle: env `QGAI_REGIME_INRANGE=0` reverts to old global-0.5% behaviour. | small | +4.9R (1mo, sum of per-regime deltas) |
| **⏳ PENDING: in_range_phase regime-swap FULL-YEAR + WFO confirm** | 1-month evidence only (13-46 trades/regime — noise possible). **RUN before trusting live:** full-year backtest (regime-aware ON vs OFF) + then WFO gate. If full-year confirms → keep; if it reverses → `QGAI_REGIME_INRANGE=0` (or revert the inference.py block). | small | TBD |
| **RESTORE 4 PART-1 features** | ✅ DONE 2026-07-12 — Individual A/B (1mo): B3 `h4_h1_regime_score` +14.8R (best), B4 `trade_direction` +12.3R, B1 `h4_trending_h1_aligned` +10.6R, B2 `h4_ranging_h1_neutral` +10.2R vs baseline +8.9R. **Combo B3+B4 = +8.8R (FLAT, interference).** Decision: **KEEP ONLY B3** (`h4_h1_regime_score`), drop B1/B2/B4 (overfeed — B3 already encodes B1+B2 as gradient score, B4 interferes). 35→36 feat. | small | +5.9R (B3 alone) |
| **ADX redundancy prune** | ✅ DONE 2026-07-12 — Individual ablation: D1 `h4_ranging_h1_extended` =baseline (B3 score=-1 covers it), D2 `M30_ADX` +15.3R (+0.5R), **D3 `H1_ADX` +18.0R (+22% gain, PF 2.55, DD 0.5%)**. All 3 confirmed redundant/overfeed. Dropped to `_MANUAL_PRUNE`. 36→33 feat. **⏳ WFO gate pending.** | small | +3.2R (D3 alone) |
| **Hardcoded-threshold audit** | ✅ DONE 2026-07-12 — 16 hardcoded cutoffs in features; 15 already OK (binary pruned + raw in model, e.g. ADX≥19→raw H4_ADX). Only `in_range_phase` (0.5%) lacked a raw counterpart → RAW-MOVE fix above. | — | — |
| **P4** | **🎯 REAL R-WORK (the actual upside)** — raise honest ~+80R by genuine signal: honest feature R&D, threshold/model tuning on the +80R baseline, entry/exit/risk logic. This is where PROFIT (prime directive) comes from — P1–P3 are correctness cleanups, not profit. | Audit shows no hidden leak props up +80R, so gains here are real & live-transferable. | large | **the real gain** |

| # | Task | સ્થિતિ |
|---|------|--------|
| ~~**RESTORE+RETRAIN** (+444R recover)~~ ✅ RESOLVED 2026-07-12 | `corr_imp_ratio` restored 07-11 + retrained (honest in_range) → WFO partial ≈ +46R@30wk (tracks ~+80R, NOT +444R). **Proved +444R was leak-inflated, not corr_imp_ratio.** → see P1 for the corr_imp_ratio decision. | DONE (finding logged; superseded by P1) |
| **`in_range_phase` LEGACY toggle** | `QGAI_INRANGE_LEGACY=1` reproduces old leaky behaviour for backtest-only (default honest). Legacy retrain bats exist. **Full legacy run = SKIP (pointless — fake number).** | Toggle kept for audits; live stays honest |
| **tick_volume ADD+TEST** | Add `tick_volume` raw to model → retrain → WFO gate. If profit drops → properly remove (full WFO evidence). If profit holds/rises → keep. | Currently pruned. Do AFTER corr_imp_ratio restore verified. |
| **Ablation** | Feature removal one-by-one with WFO test per removal. Ablation AUC done (10 tests). Order: T10 trend-signal first, then T2 tick_volume, T7 OB/SR, T8 news, T9 momentum. KEEP: slot_win_rate, h1 S/R dist. Each removal = retrain + WFO gate. | AUC results: `data/ablation_results_clean34.json` |
| **P3'** | DEMO forward-test (relabel+HTF+regime-TP, 3%) | ચાલે છે — **real proof** |
| **L2** | REBUILT trainset A/B | **model backup થઈ ગયું ✅**, full-history પછી run |

### ✅ થઈ ગયું (DONE — 2026-06-30 / 2026-07-01)
| # | Task | પરિણામ |
|---|------|--------|
| FF-RM | **REMOVE flip-fix / hysteresis code** (Divyesh, 2026-07-02) | DONE. Rejected on PROFIT grounds — every clean-parity test showed hysteresis LOWERED total R: June sweeps (−6.5/−7.2/−9.9R), yesterday 07-01 (+4.08R→+1.26R), and **WFO true-OOS full year: baseline +360.1R vs hyst +314.2R = −45.9R (−12.7%)** despite dir_flips −75% (726→183) and flat WR/PF. It blocks profitable flips (esp. Trending). Removed from `config.py` (hysteresis_margin field), `bridge_main.py` (pick block), `backtest_replay.py` (env FF block + `import os as _os`); deleted helper scripts `flipfix_*.py` + all `Run_FlipFix_*.bat`. Result folders + BUFFER_015_BacktestVsWFO / BUFFER_FLIPFIX_WORKFLOW reports kept as record. Live = clean baseline max-prob pick (restart to load). |
| L5 | Buffer sweep (global) — `Run_Buffer_Sweep.bat` 0.10/0.15/0.20/0.25/0.30%, 1yr, 42-feat+forming-line+regime-TP, fixed-lot 0.01 | Ran 2026-06-30 (`backtest/results/bufsweep/buf_0.*.txt`). **0.15 best balance: PF 3.87, +430.70% net, Max DD 2.9%** (vs 0.20: PF lower, DD similar). **APPLIED to live 2026-07-01** — `config.py ratchet_buf_pct: 0.20→0.15` (reversible, old value in comment). ⚠️ Regime-wise breakdown (best buffer PER Ranging/Trending/Volatile) not yet done — global sweep only; regime-adaptive buffer still open if wanted later. |
| Bug | **win_prob frozen 75+ min live (12:15→13:30) — inference.py silent stale-feed** | Imtiyaz flagged (WinProb stuck at 27%). Traced via `logs/signals_all.csv`: win_prob/state_prob/dir_prob/hmm_state bit-identical across 6 bars while price moved — `get_signal()`'s OHLC-merge staleness-guard silently failed to refresh `self.ohlc_df`, and the failure path was a bare `print()` invisible in `bridge.log`. **FIXED:** merge failures now also `log.error(...)`; added a `_ohlc_stale_bars` counter that alarms in bridge.log after 2 consecutive bars with no fresh candle merged. Needs bridge restart to load; not yet live-verified. |
| Live | **🔴 vSL close failed, retcode 10027 (AutoTrading disabled)** | Imtiyaz's live log showed both primary (VantageDemo) and secondary (VantageCentLive #29453256, REAL money) close orders rejected with 10027 = MT5 terminal AutoTrading OFF. **Not a code bug** — told Imtiyaz to enable AutoTrading in the MT5 terminal immediately (stops aren't actually protective until then). Recommend (not yet built): an explicit alert (not just an `[ERROR]` log line) when any close fails. |
| Bug | **Mojibake emoji in console (`ðŸ’“` etc.)** | `Start\1-5` bats never set `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8` (unlike `6_Shadow_Ledger`/`7_Refresh_Chart`/all backtest bats) → Windows console fell back to legacy codepage. Display-only, no logic impact. **FIXED:** added both env-vars to all 5 `Start\*.bat`. Takes effect on next restart of each. |
| Check | **"Did Codex break something today?" (Imtiyaz asked)** | Audited every file with a 2026-07-01 mtime (`bridge_main.py`, `bridge_data.py`, `chart_data.py`, `chart_live_ohlc.py`, `config.py`, `backtest_replay.py`, `shadow_ledger.py`) — all compile clean, no unexplained/undocumented changes found. The win_prob-freeze bug traces to `inference.py` (not touched today) and the 10027 error is an MT5 terminal setting, not code. **No evidence of a Codex-introduced mistake.** |
| Dash | **dashboard.html fixes (Imtiyaz's own edits, Claude-verified)** | Duplicate `id="sig_history_chart"` (dead bottom panel) removed; mojibake header fixed; missing "MODEL" confidence box restored (`conf_model_val`). Verified: 0 duplicate IDs, div-balanced, JS syntax clean. |
| Fmt | **Win-prob / all-% displays → 2 decimals everywhere** | ~35 spots across `dashboard.html`, `inference.py`, `bridge_main.py`, `bridge_dashboard.py`, `chart_data.py`, `signals.html`, `shadow.html`, `QGAI_Live_Panel.html` changed from `.0%`/`.1%`/`toFixed(0)`/`toFixed(1)` → `.2%`/`toFixed(2)`, for every probability/rate/gauge % (win_prob, state/dir prob, win rate, slot WR, daily-loss/eq gauges, regime distribution, etc). Left non-% numbers (prices, $ amounts, R-values, spread pts, SVG coords, hours-ago) untouched. |
| Feat | **Stuck-trade manual-protect (Imtiyaz's spec, 2026-07-01) — ENABLED** | New: `bridge_session._close_position()` tracks consecutive close-failures per ticket (`_CLOSE_FAIL_COUNTS`). Past `stuck_close_fail_threshold` (default 3) it logs a loud repeating `🚨 STUCK` alert every retry (was: one `[ERROR]` line, easy to miss — this is what happened with #1519547791 today, retcode 10027 AutoTrading-off). `stuck_trade_hedge_enabled=True` (Imtiyaz turned it on 2026-07-01) — opens a protective opposite-direction hedge to freeze further P&L movement while the close keeps retrying; auto-unwinds once the original close finally succeeds. **Bug caught + fixed before it could bite:** first draft reused L13's `manual_hedge_magic` (202699) — but `bridge_manual.py`'s cleanup sweeps/closes EVERY position on that magic whenever its OWN floor/vSL/TP fires (magic-only filter, no comment check), which would've silently closed a stuck-trade's protective hedge out from under it the next time a manual trade's floor/vSL/TP happened to fire. **Fixed:** stuck-trade hedges now use a brand-new dedicated `stuck_hedge_magic` (202698), fully isolated from L13's pool — confirmed via code read (`bridge_manual.py _positions()` only matches its own magic). Bot keeps the ORIGINAL trade's own magic (202600) — MT5 doesn't allow re-tagging an existing position's magic, so "treat as manual" is a code-level bookkeeping flag only, confirmed OK with Imtiyaz. ⚠️ Not yet DEMO-verified end-to-end (places a real order) — watch the first time it actually fires. |
| Bug | **vSL recovery fallback = hardcoded $15 guess, disconnected from real ratchet** (Imtiyaz flagged: leftover #1519547791 vSL showed 4016.42, doesn't match H1 line ~3975) | Traced via `bridge.log`: real vSL at open was 4012.35, trailed once to **4015.11** (22:30). Comments are a clean brand-tag by design (no embedded VSL/SL) and this trade has no broker-side SL (pure-virtual design) → `recover_open_trades()` fallback (`bridge_core.py`) hits `broker_sl_dist=0` → hardcoded `sl_dist=15.0` → `entry−15.0=4016.42`, matching the observed value exactly (bug confirmed, not coincidence). **Root cause of why it kept resetting:** separately found `_close_position()` callers in `bridge_core.py` were doing `del self.virtual_trades[ticket]` **unconditionally** after every close attempt — even on FAILURE — so the moment a close failed once, the trade silently dropped out of live vSL monitoring for the rest of that session (contradicting the "bot will keep retrying every check" alert text) and only ever got picked back up via `recover_open_trades()`'s lossy fallback on the next restart (08:30/09:25/15:21 today). **FIXED (2026-07-01):** `_close_position()` now returns True/False (True = confirmed closed); all 5 call sites in `bridge_core.py` only `del` the VirtualTrade on True — a failed close now correctly keeps retrying every tick with the REAL vSL intact, no restart needed. Real vSL-persistence-across-restart (so recovery never needs to guess) still NOT done — lower priority now that the trade stays tracked live without restarting. |
| Bug | **bridge_main.py heartbeat log — mojibake heart emoji (Imtiyaz's spec: fix ONLY this, nothing else)** | Imtiyaz flagged one broken heart emoji in the heartbeat log line (`💓 heartbeat — ...`, the one Codex apparently introduced). Investigating turned up ~680 MORE mojibake instances throughout the rest of the file's log messages (pre-existing, unrelated) — a full-file sweep was done first, but Imtiyaz clarified he only wanted the ONE heartbeat-line instance touched, not the rest. **Reverted the full sweep**, re-applied the fix to ONLY `bridge_main.py:334-335` (the `_hb_state` string + the `log.info(f"💓 heartbeat — ...")` line) — verified via scan that these are the ONLY 2 lines in the file using clean (non-mojibake) emoji/dash chars now; everything else intentionally left as before. `py_compile` clean. |
| Feat | **backtest_replay.py checkpoint/resume (Imtiyaz's spec, 2026-07-01)** | `_checkpoint_pkl` existed but was dead/unused code (no save or load anywhere) — a stopped/interrupted backtest lost ALL progress, had to restart from bar 0. **Built:** saves state (equity, open trades, trades/signals so far, daily-loss tracking) every 500 bars AND on Ctrl+C (flag-checked at the next bar boundary, not exception-based, so it can't corrupt a half-written record). Checkpoint is keyed by a full config signature (date range, risk%, buffer%, TP-regime, all ratchet/filter flags) — a checkpoint is ONLY ever reused for the byte-for-byte SAME config, same paranoia as the WFO-cache Bug H precedent (never silently resume into a mismatched run). New `--no-resume` flag forces a clean restart. Auto-deletes the checkpoint on successful completion. Confirmed the engine has no cross-bar online-learning state in replay mode (no `.fit()`/partial_fit calls found), so skipping already-done bars on resume is behaviorally identical to a full run. ⚠️ Could not get an automated `py_compile` check this session (bash sandbox mount stuck serving a 3+ hour stale cached copy of the file, confirmed via `stat` mtime — known documented issue) — verified instead via full manual line-by-line Read-tool review of every edited section + docstring-balance check. Should be spot-checked on the NEXT backtest run (current running full-year backtest is unaffected — already loaded the old code into memory). |
| Bug | **backtest_replay.py console looked frozen/blank during long runs** | Imtiyaz flagged the console showing nothing for long stretches. Root cause: `sys.stdout`/`stderr` were wrapped in a plain `io.TextIOWrapper` (no `line_buffering`), so `print()` output sat in Python's internal buffer and only flushed once it filled or the process exited — a long backtest LOOKED stuck even while working correctly. **FIXED:** added `line_buffering=True` to both wrappers + `flush=True` on the progress print, progress interval tightened 500→100 bars (with a running % complete), and `PYTHONUNBUFFERED=1` added to both `Run_Live_Buffer_015_CSV.bat`/`_TEST.bat` as a belt-and-suspenders fix for Windows console pipe buffering. |
| Feat | **Graduated stuck-trade excess-hedge, 3%→6% risk stretch (Imtiyaz's idea, 2026-07-01) — built, OFF by default** | New `bridge_session._stuck_risk_hedge()`: instead of freezing the FULL lot the instant a stuck trade's close fails (old `_place_stuck_hedge`, still available), let risk stretch from `risk_pct` (3%) up to `leftover_risk_cap_pct` (6%, new config) and hedge ONLY the excess lot once **unprotected slippage** (price moved past the trade's REAL vSL — passed in from the live `VirtualTrade`, not reconstructed — while close keeps failing) pushes risk past that stretched band; tops up incrementally if slippage keeps growing, never exceeds `pos.volume`. Reuses L13's `_contract_size`/excess-hedge math pattern (`bridge_manual.py`). Gated by new `leftover_excess_hedge_enabled` (default **False**) — takes priority over `stuck_trade_hedge_enabled`'s full-lot hedge when ON. Depends on the retry-loop fix above (needs the trade to stay live-tracked to keep re-evaluating). ⚠️ Not yet enabled or tested — Imtiyaz to confirm before flipping the flag. |

### ✅ થઈ ગયું (DONE — 2026-06-29)
| # | Task | પરિણામ |
|---|------|--------|
| L1b | Full-history **GLOBAL vs REGIME** TP compare (2022→2026, HTF+CTF, 0.01 lot) | **Regime wins:** PF 2.35→**2.47**, WR 59.2→**59.9%**, Total **+676→+708R**, same DD 1.7%, ~47/50 months green incl. unseen 2022-24. Results: `results/signal_log_full` (global) vs `results/fullhistory_regime` (regime). |
| P3✓ | regime-TP confirmed LIVE-wired | `ratchet_tp_regime=True` (config) + `bridge_core.py:170`. Rng 2.0/Trn 1.0/Vol 0.8. |
| 🔴 L8-bug | **balance-flow FALSE daily-SL halt** (Anisa flagged via live log) | FIXED: `_net_balance_flow_today` used LOCAL time → counted LIFETIME deposits ($906k) as today → equity looked $68k → halt all day. Now broker-time filter + 50% safety guard. (BUG_LOG 06-29.) |
| Bug | **offline-closed trades blank in signal log** | FIXED: `preload` now calls `write_outcome` → backfills WIN/LOSS for trades closed while bridge OFF. |
| Bug | signal-log **duplicate rows** (same bar 2-3×) | FIXED: dedupe guard in `log_signal` (one row/bar+mode); 44 dup rows cleaned. |
| L9 | **Complete signal log** (full-history backtest + live, $ move) | `build_signal_log.py` rewritten → merges regime full-history (every bar, move) + live → `logs/signals_complete.csv` (97,322 bars). Dashboard reads it (history+live merged, live overrides). Bat: `Run_BuildSignalLog.bat`. |
| L11 | startup **gap-backfill** (overnight signals → dashboard) | `_overnight_replay` now logs missing bars (mode=BACKFILL) → dashboard shows overnight history. Resume-prompt was already built (config-gated). |
| Dash | **signal log overhaul** | one complete log (date+time sorted, price, win%, regime, H4-RANGE, BW%, lot, WIN/LOSS REAL, $ move, equity, reason). Removed dup Signal-History table + SLOT DISCOVERY panel; kept chart. equity/move columns added to `log_signal`. |
| L13 | **Manual-trade Manager** (Anisa spec) | BUILT + ENABLED on DEMO (`bridge_manual.py`, config-gated). **Final design (approach A, combined vSL):** combines ALL manual trades (magic 0) into ONE net position (sum lots, vol-weighted avg entry) → ONE **ratcheting vSL** on the 2-SMMA line (HTF/H1), trailed as a **VISIBLE broker SL on every leg**; breach → close ALL; **SEPARATE 3% risk pool** (`manual_risk_pct=3`, independent of bot's `risk_pct=3` → 3%+3%=6% total) broker-SL backstop + **excess-hedge** if combined lot > 3%-equiv; **target-TP** (`manual_target_tp_pct=2%`) → close all; flip-hedge REMOVED (vSL handles reversal). L8-isolates manual P&L from the bot's daily ratchet. Bot entry-guard counts only magic 202600 → manual trade does NOT block a same-direction system trade (room to trade). **DEMO (primary) only** — cent extension rejected (would conflict with mirror-trading). Config: `manual_manager_enabled=True` (demo test). Verified live: detects existing trades, sets 3% SL + vSL. |
| Cfg | accounts | Added **Vantage CENT LIVE 29453256** (secondary, XAUUSD.pc, pass to fill); **disabled TradeQuo 125926628**. |
| L11+ | **Resume-prompt — REMOVED (Anisa, 06-30)** | Built + enabled, but it fired on the first NEW bar (loop), not the exact startup moment → felt like "asking while running." Anisa removed it: `resume_prompt_on_start=False`. Reason: the bot now MANAGES manual trades, so the user just opens a trade manually when wanted (bot handles it) — no need to ask the bot to take a signal. Bot auto-trades its own signals. Code stays (config-gated off). |
| Feat | **Feature removals + RETRAIN** | (1) `ts_line_dist_pct` removed (was rank #2). (2) `vol_spike` removed completely. Retrained 23:22 → **44→43 features**. AUC **0.6791→0.6881** (held); SELL test AUC **0.7557** (WR 67%). HTF-align importance jumped (h4_h1_regime_score 0→0.0329, h4_trending_h1_aligned #2) — model now weighs HTF trend. ⚠️ **run WFO** before trusting live. REVERT: delete `_MANUAL_PRUNE` line + restore vol_spike + retrain. |
| EMA200 | **EMA200 S/R / exit / entry — INVESTIGATED, no change** | M15 EMA200 = decent short-term S/R (~80% bounce/2h). Exit/tighten → cuts winners (R −12%) ❌. Cross → no reversal edge ❌. Hard entry filter → misses big moves (Anisa declined) ❌. KEY: "SELL below EMA" = worst (39.5% win) = bottom-chasing confirmed. Keep EMA200 as SOFT model features (already in the 43). |
| L7b | **Vestigial code remove — DONE** | dead `bridge_risk` (PBE/partial/BE/smart-exit) removed; **ATR removed completely** (safe-subset + rest, bot stopped): bridge_main atr20_pct compute, inference vol_regime→constant + move-model fixed 0.2, train_move_model fixed 0.2, dashboard labels. ADX-internal atr14 kept (indicator math). SQLite/CSV `atr20_pct` column LEFT nullable (logs 0 — drop = migration risk). |
| Dash | **Stale TP/SL/ATR labels FIXED** (Anisa flagged) | header TP→regime cap, SL→Ratchet, ATR(info) removed; `atr_mult` dropped from backend. `dashboard.html`+`bridge_dashboard.py`, 0 nulls. |
| BugChk | **4-round bug-check (Anisa, 06-30)** | Found + fixed the only real issue: **stale RUNNING CONFIG display** — printed PARTIAL/TRAIL/BE/SMART-EXIT + "TP cap 1.0%"/"maxrisk 1.2%" as active, but those are removed (L7b) / regime-TP+HTF actually used. Now shows pure-ratchet + regime-TP + HTF-forming + %·line buffer. (bridge_main.py:233-249). Feature count OK (41+hmm=42). No functional bug. Minor edges noted: manual vSL not persisted on restart; manual buf fixed-vs-%·line. |
| Manual-vSL | **Manual SL → PURE VIRTUAL + indicator-match (Anisa, 06-30)** | No broker SL on the terminal (don't expose the stop to the market). bridge_manual: removed all `_set_sl` calls; vSL tracked internally + logged `🔼 [VIRTUAL]`; bot closes ALL on breach (vSL/floor) — tracked like the bot's own trades, combined. **Buffer now = 0.20%·LIVE line** (was fixed avg·0.20%) → fully matches the chart indicator + bot. Line uses forming H1 (via get_htf_state). Floor stays entry-based (risk cap). ⚠️ bot OFF = no protection (explicit). 0 nulls, verified. Restart to apply. |
| L13-fix | Manual mgr **line-independent floor-breach close** | bridge_manual.py:157-169 — before `if line:`, if price past the 3% floor → close ALL manual + hedges (🔻). Enforces the cap even when the ratchet line is unavailable. Read-verified, 0 nulls. Effect on restart. |
| EMA200-cut | **Keep ONLY price_vs_ema200** (Anisa, 06-30) | Removed `ema200_dist_abs` (rank-37) + `above_ema200` + `near_ema200` via `_MANUAL_PRUNE` + cleaned computations/loops; `price_vs_ema200` kept. **RETRAINED 2026-06-30 10:17 → 42 features** (verified: price_vs_ema200 in, 3 out). AUC **0.6881→0.6807** (tiny drop, still > original 0.6791). Bot restart-safe (42-feat). re-WFO pending. |
| WFO✓ | **43-feat retrain OOS VALIDATED → KEEP** | 2026-06-30 `wfo_results` (global-TP): **+255.4R / 41 wks / 38 green (93%) / +6.23R-wk / maxDD −3.0R**. OLD 44-feat regime-TP +266.2R (global≈global). AUC 0.6791→0.6881. ts_line_dist_pct + vol_spike removal = **harmless**, model held → KEEP. Optional `Run_WFO_TPREGIME.bat` for exact regime match. |
| vSL-parity | **backtest_replay parity for vSL change** | 2026-06-30: backtest now matches live — forming-H1-line (vf=bar-open when `ratchet_htf_forming`, lookahead-safe) + trail buffer = 0.20%·line. Trade carries `ratchet_buf_pct`. 0 nulls, Read-verified. → WFO/backtest now faithful to live config. |
| vSL-live | **vSL trails the LIVE H1 line + %-buffer** (Anisa, 06-30) | (1) `ratchet_htf_forming=True` — uses the FORMING (current) H1 bar's line = matches the chart indicator's live value (3979.55, not last-closed 3988.03) → no hourly lag, less profit give-back. `bridge_ratchet.get_htf_state` includes the forming bar + skips the cache. (2) trail buffer now = **0.20%·line recomputed per bar** (bridge_risk:105), not fixed-$-from-entry. ENABLED on demo. ⚠️ backtest parity + WFO pending (see REMAINING vSL-parity) before real money. |
| Bugs | **A · F · B · E resolved; C still open (corrected 2026-07-01)** | A (secondaries flatten on daily-SL) ✅ · F (backtest_replay HTF config-aware) ✅ · E (UTF-8 wrapper) ✅ · B ✅ (open_time reconstructed on restart — still used by `bridge_dashboard.py:259` for elapsed-time display, NOT moot) · **C still 🔶 open** (SYMBOL not refreshed after failover; dormant since MT5_PRIMARIES unset — was wrongly marked N/A here). **D open** (subprocess refactor, being investigated 2026-07-01) — M fixed, see below. |
| M | **Bug M fixed (2026-07-01)** | `run_wfo.py --trail-mode` default changed `"line"` → `None`; forward guard changed to `if args.trail_mode is not None`. No flag → follows `backtest_replay.py`'s own config-aware default (htf today, matches live) same as before, now correct-by-design not accidental. Explicit `--trail-mode line` now genuinely forces literal M15-line mode (previously silently ignored and ran htf instead). `py_compile` clean. |
| L9b | Signal-log panel | `QGAI_Live_Panel.html` (localhost:8000). |
| L10b | Live Periods panel (Today/Week/Month/Year) | same panel. |

### ✅ થઈ ગયું (DONE — 2026-07-02/03: HMM v3 + audit FIX-1)
| # | Task | પરિણામ |
|---|------|--------|
| HMM-DI | **HMM "Volatile" mislabel — v3 `rel` DEPLOYED (2026-07-03)** | 3 variants A/B'd WFO-gated: spec reject (degenerate 92% Trending), leak-world rel +481.7R ≈ baseline; **honest (as-of) A/B: legacy +407.6R vs rel +393.7R = tie (paired t=−0.69), rel DD −26% (5.2R vs 7.0R) + 0 negative weeks → Divyesh chose rel.** Deploy verify: **ALL CHECKS PASSED** — flat 07-02 window 18 Ranging/4 Trending/**0 Volatile**, stability train≈full (45/35/20). Bonus: honest data પર hmm_state importance 0→0.0305 (#6). Revert: `_backup_pre_hmm_v3` + `.bak_preasof_20260703_104235`. |
| FIX-1 | **Audit Fix 1 — intra-bar HTF lookahead leak REMOVED (2026-07-03)** | `regen_adx_asof.py` (as-of = live-updater semantics, validated err=0.0) **APPLIED** to adx_merged; `mt5_data_updater.py` also as-of convention (future updates consistent). Leak drift measured: M30 mean 0.28/max 12.8, H1 0.45/11.5, H4 0.58/10.1 ADX pts (M15=0 ✓ sanity). Leak-inflation ~15-18% પુષ્ટિ (483→408 legacy). **નવો HONEST baseline = wfo_asof_rel +393.7R** — હવે પછીની દરેક સરખામણી આની સામે; જૂના +483.1R/+481.7R આંકડા retired. |

### 🟡 બાકી (REMAINING — parked / pending)

#### ▶ TOP NEXT (2026-07-07, priority order — Fable-5 ranked)
| # | Task | વિગત |
|---|------|------|
| ~~**RAW-VOL retrain**~~ ❌ CLOSED 2026-07-11 | `tick_volume` raw feature — fully evaluated | AUC: +0.005 marginal (Test 0.6219 vs 0.6167). WFO NO-VOLUME model +80.5R beats volume model. ADX-Death+volume combos all worse. **Volume features permanently excluded.** Pre-tick_volume model backup: `data/models/backups/models_PRE_TICKVOL_20260709_1105/final/`. |
| ~~**PART 2 decision**~~ ❌ REJECTED 2026-07-07 | ADX 10-raw → 5-composite consolidation | **FULL WFO = +405.6R vs +444.7R = −39R (−8.8%). FAILED the gate.** Composite lost per-TF info the raw features carry (AUC 0.705 was higher but total R lower — accuracy≠profit). 52/53 positive weeks (good stability) couldn't offset the R loss. Fable P≈30% correct. **DECISION: keep PART-1 raw-36 (live). Never set `QGAI_ADX_MODE=composite`.** `adx_fs_div` late-entry lever was alive but didn't save total R. Composite model discarded. |
| **FIX-3 parity** (Fable's #1, REDEFINED 2026-07-08) | backtest↔bridge_core EXIT-logic parity | Reversal-close TESTED = not the gap (overlap 13.6→15.2%). The "12% overlap" is a SHADOW-ENGINE ARTIFACT — `shadow_ledger.py` has no max_open (154 entries → 44 when locked, vs backtest 66). **+444.7R is trustworthy (pessimistic if anything — backtest under-trails 0.6R/trade).** NEXT: code-diff `bridge_core.py` (live truth) trail/flip/TP vs `backtest_replay.py`, make backtest match live exactly, re-run. Key Q: does live trail unconditionally or regime-gated? Drop shadow-overlap as a metric. Keep demo running (final entry-side arbiter). |
| **max_open=2** (only path to +50% goal) | 2 concurrent positions | Research +347R in-sample but 2× exposure/DD → needs dynamic-risk demo validation AFTER FIX-3. Not a switch-flip. |
| **Goal reality** | +20-50% R (target +420-525R) | PART-1 already banked +13% (+444.7R WFO). No single safe lever reaches +50%; only max_open=2 does, and only responsibly after FIX-3. Honest ceiling without it ≈ +10-15%. |

#### 🚨 Fable-5 SYSTEM AUDIT 2026-07-07 — 16 findings (fix after Path A backtest)

**SEVERE (live-critical — Path A પછી તરત):**
| # | Task | વિગત |
|---|------|------|
| ~~**FAB-S1**~~ ✅ DONE 2026-07-07 (flag-gated, default OFF) — reversal re-entry now passes full filter stack when `gate_reversal_entries=True`; close-on-opposite backtest port still pending (see M12). | 🚨 **Live reversal path bypasses all entry filters + backtest doesn't model reversal** | `bridge_main.py:500-509` opposite-signal handler bધા range/CTF/pullback/SMMA blocks પહેલાં ચાલે. `bridge_core.py:543-601` `handle_opposite_signal` → `execute()` direct, zero filter check. Backtest માં reversal code છે જ નહીં. **સૌથી મોટું FIX-3 12%-overlap gap explanation.** Fix: (a) reversal path ને same gate stack માંથી પસાર કરો, અથવા (b) `handle_opposite_signal` નું backtest port કરો; દરેક reversal separately log કરો measurement માટે. |
| ~~**FAB-S2**~~ ✅ DONE 2026-07-07 (FALSE POSITIVE + defensive check installed) | 🚨 **News calendar DEAD 2026-05-15 થી (~7 weeks silent)** | `news_all_2024_to_now_pure_cleaned.csv` last event = May 15. **કોઈ auto-updater નથી.** `mins_to_next_3star=240` (pegged), `is_pre_news`/`is_post_news=0` હંમેશા → pre-news +0.05 threshold bump OFF, news-model routing OFF. Bot NFP/CPI માં 0.42 Volatile threshold પર trade કરે. Feature-distribution drift (training vs live) પણ silent. Fix: automated weekly calendar pull + startup/hourly staleness assertion ("newest future event < now → ERROR banner + optional trading pause"). |
| ~~**FAB-S3**~~ ✅ DONE 2026-07-07 (`engine/dd_brake.py` NEW + `calc_lot` wired; config `enable_live_dd_brake` default OFF — turn ON for real capital) | 🚨 **DD brake live code માં EXISTS નથી** | `grep dd_brake` → માત્ર `backtest_replay.py:471,937` hit. Live risk = per-trade 3% + daily 9% only; NO peak-equity tracking anywhere. `TASKS.md` P2b's "live brake keeps it lower" = **false**. Multi-day losing streak = full 3%/trade indefinitely compound. P2b's 14.6% DD lower bound only. Fix: `bridge_core.execute()` / `calc_lot()` માં peak-equity tracking + 10/20/30% scaler implement. |
| ~~**FAB-S4**~~ ✅ DONE 2026-07-07 | 🚨 **Disaster SL = 3× vSL + restart trailed stop entry-level પર reset** | `bridge_core.py:215/221` broker_sl = vSL_dist × 3.0. `bridge_core.py:626-637` recovery regex `VSL=` શોધે, પણ comment હવે "QuantEdge AI | {phase}" (line 224-225) → **હંમેશા fallback broker_sl/3 = entry-level vSL**. `pos.sl==0` તો invents `sl_dist=15.0`. Restart while +2R trailing → vSL entry પર snap back → locked profit ગુમ; bridge death → માત્ર 3×-wide broker SL. Fix: per-ticket vSL state SQLite માં persist કરો, restart પર restore; broker SL ≤1.5× tighten કરો. |
| **FAB-S5** ⏸️ DEFERRED (profit tradeoff — do NOT silently flip) | 🚨 **HTF forming-bar line/flip: live ≠ backtest (root of TRAIL 49% vs 11%)** | Live `bridge_ratchet.py:96-106` FORMING H1 bar જુએ (flip appears/vanishes intra-hour, M15 close પર evaluate). Backtest `backtest_replay.py:339-353` COMPLETED bar mapping (flip bar-open થી known — mild lookahead, line stable). Live unconfirmed forming flips પર exit; backtest confirmed flips પર "hour early" exit. Entry SL sizing પણ diverge. Config comment પોતે "needs backtest parity + WFO before live" કહેતો હતો — never done. Fix: true forming-line replay build કરો (H1 SMMA per M15 sub-bar recompute) OR `ratchet_htf_forming=False` set કરો till parity proven. |

**HIGH (data integrity / parity):**
| # | Task | વિગત |
|---|------|------|
| ~~**FAB-H6**~~ ✅ DONE 2026-07-07 — `get_live_adx()` now truncates history to `bar_dt` (true as-of); overnight replay passes `bar_dt` per bar. | Overnight replay TODAY's ADX past bars માં inject કરે → BACKFILL rows lookahead-tainted | `bridge_main.py:677` `get_live_adx(50)` without `bar_dt`; `inference.py:640-641` replayed timestamp stamp કરે, merge કરે. BACKFILL rows in `signals_all.csv` + shadow ledger lookahead-tainted. FIX-3 shadow −1.9R metric partly ledger પર rest કરે. Fix: `bar_dt` per replayed bar pass કરો OR replay દરમિયાન ADX merge skip; `mode=BACKFILL` rows metrics માંથી exclude. |
| **FAB-H7** ⏸️ DEFERRED (backtest-side; would shift +350.2R baseline → flag-gate before enabling) | Daily-SL semantics live≠backtest | Live `bridge_core.py:378-391` `check_daily_sl_intrabar` — floating equity પર halt + force-close all. Backtest `backtest_replay.py:454-474` `daily_stopped=True` — only new entries block, open trades ride on; equity update only at trade close → floating DD trip નહીં થાય. Fix: backtest_replay માં mark-to-market equity per bar simulate + force-close at floor. |
| ~~**FAB-H8**~~ ✅ DONE 2026-07-07 — `_resume_sig` now folds `sorted(QGAI_* env)` + model .pkl mtimes. Env-toggle / retrain forces fresh run. | Backtest checkpoint resume signature env vars + model mtimes omit કરે | `backtest_replay.py:276-283` `_resume_sig` — `QGAI_CTF_FADE`, `QGAI_SKIP_RANGE`, `QGAI_RANGE_MIN_PROB`, `QGAI_PB_*`, `QGAI_ED_*`, `QGAI_HMM_VARIANT`, model pkl mtimes omit. Env toggle change / model retrain → same CLI re-run → half-old/half-new resume = plausible-wrong results (WFO-cache class bug, Bug-H ghost). Fix: signature માં `sorted(os.environ QGAI_*)` + model file hashes fold કરો. |
| ~~**FAB-H9**~~ ✅ DONE 2026-07-07 — `adx_strength_soft_block` + combined SMMA+ADX cap wired into `bridge_main` (dormant, default OFF) → live==backtest if ever enabled. | ADX-strength gate + combined SMMA+ADX cap backtest only, live માં નથી | `backtest_replay.py:619-635` `adx_strength_soft_block` call + combined-penalty cap; `bridge_main.py` બંને missing. `adx_strength_soft=True` OR `QGAI_ADX_STRENGTH=1` adopt થાય એ દિવસે live behavior WFO winner match ના કરે — structural parity break guaranteed. Fix: identical block `bridge_main` માં wire કરો (dormant behind same flag). |

**MEDIUM (behavior / cleanup):**
| # | Task | વિગત |
|---|------|------|
| **FAB-M10** ⏸️ DEFERRED (stateful behavior change — needs backtest before live; don't half-implement) | HMM regime zero hysteresis — noise flip threshold 0.48↔0.42 બદલે | Per-bar GMM argmax (`inference.py:712-714, 895-899`) — Ranging→Volatile એક noise bar પર marginal 0.43-prob signal fire કરે. Fix: 2 consecutive bars require OR `predict_proba` margin threshold check before switch. |
| ~~**FAB-M11**~~ ✅ DONE 2026-07-07 — picker now prefers any actionable BUY/SELL over higher-prob SKIP; mirrored in backtest for parity. | Best-of-BUY/SELL picker higher-prob SKIP ને lower non-SKIP કરતાં prefer કરી શકે (**prime directive violation**) | `bridge_main.py:445` picker win_prob comparison — SKIP result higher prob હોય તો select થાય, જ્યારે opposite direction lower-prob non-SKIP હોય. Trades silently lost. Fix: any non-SKIP ને SKIP કરતાં prefer કરો. |
| ~~**FAB-M12**~~ ✅ DONE 2026-07-07 — parity-gap table written to `docs/FILTERS_MASTER.md` §PARITY GAPS (7 gaps, status each). `manual_risk_pct=6.0` footgun noted. | 7 explicit live-only parity gaps List | (1) spread guard, (2) opposite-signal reversal [S-1], (3) manual manager `bridge_manual.py` real orders own 3% pool, (4) stuck-trade hedge magic 202698, (5) forming-H1 line [S-5], (6) DD brake inverse [S-3], (7) daily-SL floating semantics [H-7]. Note: `bridge_manual.py:106` `manual_risk_pct=6.0` default vs line 255 `3.0` — dormant footgun. Manual loss = 9% daily halt trip → bot day stop, backtest ne model નથી. Fix: single reconciliation report table + `manual_risk_pct` default fix. |
| **FAB-M13** 🟡 PARTIAL 2026-07-07 — CTF re-audited via Path A: DISABLED (+34.3R, live config changed). Range-phase re-audit (soften 0.55) tested = flat +2R → kept ON. Both now post-leak-fix validated. | Range-phase + CTF-fade blockers pre-leak-fix evidence પર justified — never re-audited under profit directive | Config comments in-sample numbers (−43R range, +15R CTF) HMM leak-fix + relabel પહેલાં measured. A/B hooks (`--no-range-skip`, `QGAI_CTF_FADE`) exist પણ post-2026-07-03 rerun TASKS માં recorded નથી. **SMMA-gate જેવો risk profile — hard blocks on stale evidence.** Path A આ address કરે છે — post-Path-A verdict લખો. |
| ~~**FAB-M14**~~ ✅ DONE 2026-07-07 — SMMA comment rewritten "PROVEN HARMFUL, do not flip"; dead session keys (use_time_filter/enable_ny_session/window*/enable_morning_session) marked ⚰️ DEAD + flipped False (0 readers verified). | Config comments accepted findings ને contradict કરે — re-enable trap | `config.py:89-100` SMMA gate "+51R, flip to True after DEMO" સેલ કરે છે જોકે proven −3.7R/PARKED. `use_time_filter=True` + `enable_morning_session`/`enable_ny_session`/`window1_*`/`window2_*` બધા dead (grep zero readers) છતાં live દેખાય. **Future session config.py વાંચી proven-harmful gate re-arm કરી શકે.** Fix: dead keys delete, SMMA comment "PARKED — proven harmful (−3.7R live parity, blocked 33 profitable trades)" કરો. |

**LOW (retrain-cycle cleanup):**
| # | Task | વિગત |
|---|------|------|
| **FAB-L15** | `is_dead_hour` 57-59% WR hours ને dead label કરે | `features.py:611` (comment પોતે admit કરે). Mislabeled feature training માં baked. Retrain cycle પર cleanup candidate. |
| **FAB-L16** | Backtest exit prices spread + slippage ignore કરે | Spread only entry પર charge; exits exact vSL/TP touch પર fill (`SimTrade._close`). Live exits bid/ask + 30s spread-wait entry delay. Small per-trade, systematic 700+ trades over. Fix: exit spread modeling `backtest_replay.py` માં add. |

---

| **DOW-AUDIT** | **Dow Theory Base Audit — full system audit against Dow Theory principles** (Imtiyaz, 2026-07-12) | Comprehensive audit: (1) 6 Dow principles vs system implementation, (2) market structure detection (HH/HL/LH/LL, swing, BOS, CHoCH), (3) trend classification (3 trends × 3 phases), (4) MTF hierarchy (primary/secondary/minor), (5) entry/exit logic vs Dow rules, (6) indicator redundancy audit, (7) ML layer alignment, (8) look-ahead/leakage check, (9) volume confirmation gap, (10) backtest quality, (11) contradiction audit, (12) Dow Authenticity Score 0-100. Output = full report + gap table + priority action plan. **DO NOT implement changes — report only, then separate implementation plan.** |
| **EA-TS-REMOVE** | **Remove `ts_adx_switch_trend` feature IF scoring-system adopted** (Imtiyaz, 2026-07-07) | Legacy EA rule (H4 dir if H4_ADX≥19 else H1 dir). Currently used as XGBoost feature (`features.py:1339`) + ratchet trailing already uses fixed H1 (not the switch) + early-entry v2 optionally uses it via `QGAI_ED_HTF_RULE=adx_switch`. **Policy: KEEP as feature TODAY, never as a live decision rule.** **Trigger to remove: if/when a data-tuned SCORING system (SMMA/ADX/other) replaces the EA-19 rule everywhere.** Then: drop from `FEATURE_COLS` (features.py:1183/1255/1339) + retrain models + WFO-gate ≥ baseline. Blocked by: scoring system must first prove real edge (P(worth-it) currently 0.15-0.35 per Fable-5). |
| L2 | REBUILT trainset A/B (12,976 flips, full history) | model experiment — **AFTER current config locked** (buffer-sweep + re-WFO of 42-feat+forming-line+%-buffer first; don't mix variables). REBUILT format ✅ train.py-compatible. Plan: backup 42-feat model → config `trades_file`→REBUILT → retrain → WFO vs +255.4R → keep/restore. |
| L3 | ML Exit/TP-predictor model (13-sweep માંથી) | research |
| L6 | ADX encoding study (level vs +DI/-DI vs slope) | research |
| L12 | News ablation + calendar pipeline fix | research |
| D | Bug D — one-subprocess-per-MT5-terminal refactor (root of multi-account fragility) | **2026-07-01: reviewed with Imtiyaz — design (one primary decides, secondaries mirror as slaves) IS intentional; confirmed no change wanted.** Symptom already mitigated (warm-up fix + primary failover). Stays parked/dormant, revisit only if a new live symptom traces back here. |
| N2 | Run `Run_WFO_LiveMatch_Buf015.bat` (new, 2026-07-01) — walk-forward OOS over the SAME period as `live_buffer_015` (2025-06-29→2026-06-29), buf 0.15 + tp-regime + tp-equity 0 + risk 3 (matches current live config exactly). Needs the user's own machine (real train.py + xgboost/lightgbm/catboost/hmmlearn) — cannot run in Claude's sandbox. Purpose: fair OOS check against `live_buffer_015`'s in-sample PF 4.27 / DD 10.77%. |
| **FIX-2** | **Audit Fix 2 — entry gate cleanup** (updated 2026-07-03 honest-data importances પછી): **(a) feature prune — PARKED (Divyesh):** honest data પર જૂની "10 dead" list ખોટી પડી (hmm_state હવે #6, momentum_aligned_1hr #4!); ફક્ત **2 જ સંપૂર્ણ મરેલી**: `h4_trending_h1_aligned` + `trade_direction` (ત્રણેય models માં 0.0000; direction-માહિતી ts_htf_agreement #2 + momentum_aligned_1hr #4 માં જીવે છે). momentum_aligned_4hr રાખવી (SELL #22, combined #23). Prune = trail sweep પછીના retrain cycle માં, WFO-gate ≥ +393.7R. **(b)** failed SELL move-model retire/regate (ρ=0.25). **(c)** calibration rolling-OOS + threshold sweep 0.35/0.42/0.50 (threshold આંધળો વધારવો નહીં — profit-first). **(d) ACTIVE NEXT: TRAIL sweep** — peak +0.94R → exit −0.15R (1.09R giveback/trade); bats તૈયાર: `Run_TrailSweep_AsOf_TEST.bat` → `Run_TrailSweep_AsOf_FULL.bat` (as-of workdir, demo સાથે parallel-safe), પરિણામ SWEEPASOF_SUMMARY.csv → "trail sweep done" કહેવું. |
| **FIX-3** | **Audit Fix 3 — live≠backtest divergence + scaling gate** (ongoing process): June 2026 quantified — entry overlap માત્ર 8/66 (12%), live TRAIL 49% vs backtest 11%, shadow −1.9R vs WFO +48.1R same month. TOOL READY: `engine/reconcile_shadow.py` (weekly ચલાવવી, output એક folder માં: reconcile_summary/matched_pairs/backtest_only/shadow_only CSVs). Attack order: FIX-1 → HMM v3 deploy → trail parity check → fill audit (demo fills vs modeled). **Scaling gate: 4–8 week સુધી weekly R gap ±20% ની અંદર + overlap ઊંચો — ત્યાં સુધી capital વધારવું નહીં**; ઓછું risk (1–1.5%) + hard lot cap ની audit ભલામણ (live માં 15.58 lots જોવાયા) — નિર્ણય Imtiyaz/Divyesh નો. |
---

## P1 — Retrain model on RELABELED data (current period)
Config `trades_file` → `Back_testing_data_final_cleaned_RELABELED.xlsx` (same Dec24→Apr26 entries,
labels recomputed under live HTF exit — 27% changed). Model still on OLD labels until retrained.
- [ ] Run `Start\3_Train_Models.bat`.
**Revert:** `config.py` `trades_file` → old `Back_testing_data_final_cleaned.xlsx` (one line).

## P2 — WFO OOS validation (confirm relabel + regime-adaptive TP) — on the current period
Gate before any live change. Both need P1 retrain first; run BOTH on the same (relabeled) data.
- [ ] `Run_WFO_FULL.bat` → `wfo_results` (global TP, relabel baseline) — compare PF vs old 1.55.
- [ ] `Run_WFO_TPREGIME.bat` → `wfo_tpregime` (regime-adaptive TP). Compare vs the global baseline.
- [ ] Keep relabel / regime-TP ONLY if each holds OOS (PF, avgR, Total R, green-week %). Else revert.
~1.5–2 hr each, resume-safe. Then tell Claude "WFO done".
**Backtest already WON in-sample:** regime-TP Total R 257.7→310.2 (+20%), PF 2.52→2.56 — now needs OOS proof.

## P2-REDO — Re-run WFO after the Bug F/J HTF fix (🔴 the validation must be redone)
**Why:** `backtest_replay` was fixed so backtest HTF = live HTF (config-aware default + H1 flip + H1 entry SL,
BUG_LOG #F/#J). The previous WFO +321R/PF3.28 used `stop-trail=line` (M15 trail/flip) — a DIFFERENT strategy
than live. So that number is INVALID. Must re-run to get the true HTF-matched OOS validation.
**Steps:**
- [ ] Archive the stale HTF-mismatched results (`wfo_results`, `wfo_tpregime`, `signal_log_full`, any run made
      before 2026-06-27 code fix) → `results/_archive/WRONG_*` (don't trust their numbers).
- [ ] Clear the results-dir (Bug H cache won't auto-invalidate) then re-run `Run_WFO_FULL.bat`
      (now config-aware → HTF automatically) + `Run_WFO_TPREGIME.bat`.
- [ ] The currently-running full-history backtest is on OLD code (started before the fix) → its output is stale; re-run.
- [ ] Compare the NEW HTF-matched WFO vs old PF 1.55 baseline; re-decide relabel + regime-TP on the CORRECT numbers.
- [ ] THEN P2b ($10k sim) + P3' (DEMO) on the real validated config.
**Status:** code fixed 2026-06-27; runs pending on PC. **Logged:** 2026-06-27.

## P2b — Check real return + DD under 3% DYNAMIC sizing ($10k Stage-2 sim)
**Why:** WFO uses **fixed 0.01 lot** = clean R / honest edge proof (3% dynamic compounding would distort
PF & total-R via compounding + trade-ordering). So WFO answers "is the edge real?", NOT "what does 3% do?".
After P2 confirms the edge, run the $10k 3%-dynamic-compounding sim to see the LIVE-realistic return + drawdown.
- [ ] Run the $10k Stage-2 sim on the OOS trade log (3% dynamic, FAR TP — `--tp-equity 0`, NOT 3; see RULEBOOK).
- [ ] Read off real return + **Max DD** (expect ~28-39% at 3%). Confirm DD is tolerable; 1-2% if not.
- [ ] This is ALSO the only place the daily 9% ratchet rule binds (fixed-lot WFO never triggers it) — verify it.
**Status:** pending P2. **Logged:** 2026-06-27.

## P3 — Wire regime-adaptive TP into the LIVE bridge + DEMO  (only after P2 confirms)
Currently only in `backtest_replay.py --tp-regime`, NOT in the live bridge.
- [ ] Add regime→TP map (Rng 2.0 / Trn 1.0 / Vol 0.8) to `config.py` + bridge exit path
      (`bridge_core.py`/ratchet), switched on HMM state at entry. Reversible flag to fall back to global TP.
- [ ] DEMO forward-test before live.

---

## LATER — PARKED until the ideas above are confirmed (Imtiyaz's call 2026-06-26)

### L1 — Full-history backtest (2022→2026, honest OOS)
`Run_Backtest_FullHistory.bat` (DONE/ready) — 2 variants (global vs regime-adaptive) over 97k bars.
Tells if the edge holds on the 2022-24 unseen regime. Run AFTER the current-period ideas confirm.

### L2 — REBUILT trainset (full-history entry set) — Option A
`engine/rebuild_trainset.py` (DONE, RAN): every 2-SMMA flip = candidate entry over 2022-2026, labeled
under live exit → `data/Back_testing_trainset_REBUILT.xlsx` (12,976 trades, ~4.6x data, win 36.9%,
stable by year incl. 2022-24). NOT adopted — bigger change (entry universe). After P2, A/B vs RELABELED
via retrain + WFO; keep only if AUC/OOS PF holds or improves. (Reproduce: `Run_Rebuild_Trainset.bat`.)

### L5 — Line + buffer sweep backtest (GLOBAL **and REGIME-WISE**)
**Why:** the ratchet SL/trail = the 2-SMMA **line** ∓ a **buffer** (`ratchet_buf_pct`, currently **0.20** global).
Set once (0.09→0.20: same profit, lower DD). Just like TP, the best buffer is probably **different per HMM
regime** — Volatile likely wants a WIDER buffer (avoid whipsaw), Ranging/Trending maybe tighter. So sweep
buffer GLOBALLY first, then BY REGIME, on the CURRENT (relabeled) model.
**Plan:**
- [ ] **Global buffer sweep:** `backtest_replay.py --ratchet-buf-pct X` for
      X ∈ {0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50} → compare PF / Total R / **Max DD** / whipsaw
      (FLIP/SL counts). Confirm/replace 0.20. (Old tool `backtest/h1_buffer_sweep.py` — adapt.)
- [ ] **REGIME-WISE:** read each sweep report's BY-REGIME block → best buffer per Ranging / Trending /
      Volatile. If they differ meaningfully, build a **regime-adaptive buffer** (same pattern as the
      regime-adaptive TP: a `_BUF_BY_REGIME` map switched on HMM state at entry, config-gated, default OFF).
- [ ] **Line check (optional):** line = SMMA(2). Test SMMA period {2,3} / buffer floor (`ratchet_sl_min_pct` 0.18).
- [ ] Best global/regime buffer that holds → **WFO-validate OOS** → then DEMO. Reversible.
**Note:** small buffer = tight stop (more SL/whipsaw, less give-back); large = looser (rides pullbacks, bigger
losers). Sweet spot balances DD vs capture, and that balance differs by regime. Do AFTER P1-P3 (don't add
variables mid-validation). Pairs naturally with the regime-adaptive TP work.
**Status:** not started. **Logged:** 2026-06-27.

### L6 — ADX representation study (is the ADX level worth it, or use +DI/-DI / slope?)
**Question (Imtiyaz):** the model currently uses the **ADX LEVEL** on 4 TFs (`M15_ADX`, `M30_ADX`, `H1_ADX`,
`H4_ADX`) PLUS direction (`*_DI_diff` = +DI−−DI on each TF), `adx_trend_count`, and slopes (`h4_adx_slope`,
`h1_adx_slope`). Is the raw ADX level pulling its weight, or would **only ADX**, or **+DI/−DI with slope**,
work better? (ADX level = trend STRENGTH, no direction; DI_diff = DIRECTION + strength; slope = is it rising/fading.)
**How (don't guess — ablation decides; importance is per-model, never remove blindly — RULEBOOK):**
- [ ] Baseline = current features. Use the `QGAI_ABLATE="f1,f2"` env hook (`features.py`) to drop a group
      for ONE WFO without touching committed lists. (Old `Run_Ablate_*.bat` are in `backtest/_archive_bats/`.)
- [ ] Variant A — drop the 4 raw `*_ADX` levels, keep DI_diff + slopes → WFO. Does OOS PF/avgR hold or improve?
- [ ] Variant B — drop DI_diff, keep ADX levels → WFO.
- [ ] Variant C — add explicit +DI/−DI separately and/or more slopes (M15/M30) → WFO.
- [ ] Keep a change ONLY if OOS (PF, avgR, green-week%) improves vs baseline. Watch cross-model redistribution
      (a feature 0-importance in SELL can be #1 in BUY).
**Context:** STRATEGY.md already finds **M15_ADX is a top feature** and a useful FILTER (high ADX = late/chasing
entry = worse; low ADX = clean trend = better). So ADX clearly matters — the question is the best ENCODING,
not whether to use it. Do AFTER P1-P3.
**Status:** not started. **Logged:** 2026-06-27.

### L7 — Fix STALE labels / displays across the system (Imtiyaz flagged)
The code/dashboard still SHOW things that no longer match reality after ATR/volume removal, the 44-feature
prune, and the relabel. Misleading (not all bugs, but must be corrected). Known so far — AUDIT for more:
- [ ] `train.py:33` print `"... | 59 Features"` → wrong (now ~44). Make it dynamic (`len(FEATURE_COLS)`).
- [ ] `inference.py:477` comment `"Compute 46 features"` → stale → dynamic/correct.
- [ ] `train.py:243` comment `"full 43 features"` → stale.
- [ ] **Dashboard/log shows `Live ATR20: 0.1594% ($6.49)`** though ATR is NOT used in any decision
      (display-only; ADX keeps its own internal TR). Either REMOVE the ATR readout or label it clearly
      `(display only — not used by the model)`. Same for any other vestigial readout (volume, etc.).
- [ ] **Hybrid feature-set counts** `Ranging=34 | Trending=30 | Volatile=20` (features.py:1364, state-specific
      RANGING/TRENDING/VOLATILE_FEATURES) — verify these lists are current (no pruned features, consistent with
      the 44-feature universe) and that the printed counts are right.
- [ ] **Full sweep:** grep the codebase + dashboard.html for other hardcoded counts / removed-feature labels
      / outdated strings and fix or make dynamic. ("many more like this" — Imtiyaz.)
- [ ] **Dead code / misleading comments (from 2026-06-27 4-round parity check):** in `bridge_risk.py` the
      PBE / partial-close / full-breakeven logic in `_update_buy`/`_update_sell` is UNREACHABLE in ratchet mode
      (`update()` routes to `_update_ratchet` when `self.ratchet`), yet `PARTIAL_CLOSE_ENABLED=True` and the
      line-47 comment says "NO PBE/partial/BE". Remove or clearly gate the dead PBE/partial/BE/smart-exit code so
      it can't confuse future reviews (it's NOT a behavioral bug — just dead + misleading). Smart-exit
      (`_smart_exit_check`, `SMART_CLOSE`, the Bug-B open_time restore) is likewise vestigial in ratchet mode.
**Why it matters:** wrong labels erode trust in the dashboard and mislead future debugging. Low-risk (mostly
display/comments) — do opportunistically, NOT mid-validation. **Status:** not started. **Logged:** 2026-06-27.

### L8 — Deposit/withdrawal-aware equity (Imtiyaz flagged — 🔴 safety + clean signal log)
**Problem:** the bot reads WHOLE-account equity, but the account gets manual **deposits & withdrawals**.
The bridge does NOT detect balance operations (`DEAL_TYPE_BALANCE`), so:
- A **withdrawal** drops equity → looks like a loss → can **FALSELY TRIGGER the daily-SL / 9% ratchet halt** (🔴 safety).
- A **deposit** raises equity → looks like profit → inflates % sizing + raises the daily ratchet floor falsely.
- The **signal-log `equity` column** (and shadow ledger, $10k analysis) jumps on every flow → polluted analysis.
**Good news:** model TRAINING is immune — it learns on R (price/risk), never equity/balance. Verified. So no
"false training"; this is purely a LIVE-equity + logging issue.
**Permanent solution:**
- [ ] Poll MT5 `history_deals_get` for `DEAL_TYPE_BALANCE` deals → maintain `net_external_flow` (deposits +, withdrawals −).
- [ ] **Daily ratchet/sizing:** when a flow occurs intraday, adjust `day_open` + `day_peak_equity` (and the sizing
      base) by the flow amount so deposits/withdrawals never trip the daily halt or distort lot size.
- [ ] **Signal log (permanent fix):** log a flow-adjusted **`trading_equity`** (= equity − cumulative net flow from
      a fixed start) instead of / alongside raw equity; optionally log flow events to their own line. Then the
      equity column reflects TRADING only and analysis is clean across deposits/withdrawals.
- [ ] (related, already known) manual trades on the account also move whole-account equity — same flow-adjusted
      base helps, but the bot still can't tell manual-trade P&L from its own; document the limitation.
**Priority:** the withdrawal→false-halt path is a real safety bug — do this BEFORE scaling live / before relying
on the equity-based daily ratchet with active deposits/withdrawals.
**Status:** ✅ DONE 2026-06-29 (was partial). (1) daily-SL/TP flow-adjust: `_net_balance_flow_today` +
broker-time fix + 50% guard (06-27/06-29). (2) **lot-sizing base** now flow-adjusted: `bridge_core.execute`
sizes off `equity − today's flow − manual_floating` (intraday deposit/withdrawal or manual leg can't distort
lot). (3) **signal-log `trading_equity` column**: `bridge_session.trading_equity()` = equity − net flow since
a fixed anchor (2026-06-29); logged on every live/monitor signal via `log_signal(..., trading_equity=)`;
old CSV auto-migrated (`_ensure_teq_column`). (4) **flow-event logging**: `log_new_balance_ops()` announces
each new deposit/withdrawal once → `logs/balance_flows.csv`. Optional follow-up: surface `trading_equity` on
the dashboard + add the column to `signals_complete.csv`. DEMO-verify. **Logged:** 2026-06-27, done 2026-06-29.

### L9 — ✅ DONE 2026-06-29 (see DONE table) — Complete signal log: EVERY M15 candle, visible offline, with $/% move + win/loss (Imtiyaz)
**Problem:** `logs/signals_all.csv` only has rows for bars the bridge actually ran (3,747 rows over 18 mo —
far short of ~96/day × ~390d ≈ 37k candles). So the dashboard shows gaps when the system was off, and there's
no per-signal **$ move / % move**, and `outcome` (win/loss) is only on executed trades.
**Want:** every M15 candle (all 96/day) shown — BUY / SELL / **SKIP** (+ reason) — with win/loss, **$ move**
and **% move**, viewable even when the bridge is OFF.
**Solution (backfill + keep current):**
- [ ] Backfill script (model needed → runs on PC): replay the model over EVERY M15 bar (backtest_replay already
      emits `backtest_signals.csv` = per-bar BUY/SELL/SKIP + probs + reason + blocked_by). Join each BUY/SELL with
      its exit outcome (from the exit sim / shadow_ledger) to add `win/loss`, **`move_$`**, **`move_%`**.
- [ ] Write a dashboard-ready `logs/signals_complete.csv` (or fill gaps in `signals_all.csv`) covering all candles.
- [ ] Add `move_$` and `move_%` columns to `bridge_data.log_signal` so the LIVE log captures them going forward too.
- [ ] Point `signals.html` / dashboard Signal Log at the complete file (it already reads the CSV, so offline view
      works once the CSV is complete).
- [ ] Schedule the backfill (after `2_Update_Data`, or a scheduled task) so the log stays complete when the bridge is off.
**Note:** ties into L7 (drop/relabel the stale `atr20_pct`/`vol_spike` columns in the log) and L8 (log
flow-adjusted equity). Do together for one clean signal-log pass.
**IMPORTANT clarification (Imtiyaz asked "won't the model fail to learn from old data?"):** NO — the model
does NOT learn from `signals_all.csv`. The batch model trains on COMPLETE OHLC (97,235 bars) + the trades
file; the online model learns from `live_trades.csv`. The signal log is **display/audit only**. So an
incomplete signal log does NOT starve the model. The mechanism for "model learns from EVERY signal across
ALL history" is **L2 (REBUILT trainset)** — every flip-candidate over 2022-2026, labeled. L9 here is purely
about DASHBOARD VISIBILITY. **Status:** not started. **Logged:** 2026-06-27.

### L11 — ✅ DONE 2026-06-29 (gap-backfill + resume-prompt; see DONE table) — Startup gap-backfill + "trade the last signal?" resume prompt (Imtiyaz's spec)
**Goal:** make the system robust to the terminal being off. On startup it backfills every missed signal,
shows them on the dashboard at 0.01 lot, and asks whether to act on the latest one.
**Flow (on `1_Start_Trading.bat` startup, after the data download/update step):**
1. **Backfill the gap:** replay the model over every M15 bar from the last logged signal → the latest closed
   bar. Log EVERY signal (BUY/SELL/SKIP) into the signal log, with outcome + **$/% at 0.01 lot** → dashboard
   shows the complete overnight history (ties to L9).
2. **Resume prompt:** identify the LATEST signal (most recent completed bar). If it's BUY/SELL and still fresh,
   ASK the user (console y/n, or a dashboard button): *"Take a trade on the last signal? [BUY/SELL @ price]"*.
   - **Yes** → execute at the normal **3% risk** sizing.
   - **No** → skip it, continue the live loop waiting for the next new signal.
3. Then carry on with normal live trading.
**⚠️ Key rule:** ONLY the latest/fresh signal is tradeable. All the older overnight signals are **LOG-ONLY**
(record + 0.01-lot P&L for the dashboard) — they cannot be traded because the price has moved on (no trading
the past). This matches Imtiyaz's "trade on the LAST signal" + "overnight signals just update the log".
**Touches:** `bridge_main.py` (startup sequence + the prompt + gap detection), `bridge_data.log_signal`
(backfill writes), dashboard. **Depends on / overlaps:** L9 (complete log), L10 (clean live log).
**Status:** not started. **Logged:** 2026-06-27.

### L12 — News / economic-calendar: prove usefulness (ablation) + fix the data pipeline
**Two parts.** (a) Is news actually adding edge? (b) The data is stale/unused.
**Findings (2026-06-27 check of `Economi calandar data/`):**
- Model uses 2 news features (`mins_to_next_3star`, `mins_since_last_3star`) + a pre-news threshold bump
  in inference. So news IS integrated — but its EDGE is UNTESTED (volume + ATR were both intuitive yet
  failed ablation and were removed; news could be the same or genuinely useful).
- Model's news file `data/news_all_2024_to_now_pure_cleaned.csv` ends **2026-05-15** (~6 wks stale) and starts
  2024-01 (so the 2022-2023 full-history backtest runs with news=0).
- The rich `Economi calandar data/ForexFactory_Calendar_3yr.csv` (2023-06→2026-06, currency/impact/
  forecast/previous/revision, 15k rows) is **UNUSED** by the model. Plus duplicate sources (Neex / vinteg, both 3.9MB).
**Plan:**
- [ ] **Ablation:** drop the news features via `QGAI_ABLATE` → WFO. OOS PF drops → news useful (keep + freshen);
      OOS PF flat/up → news redundant → remove (leaner model). Same method as volume/ATR.
- [ ] If KEEP: fix the pipeline — feed the model from the fresh ForexFactory calendar (refresh on each data
      update), extend coverage back to 2022 if possible, dedupe Neex/vinteg, stop the news file going stale.
**Do AFTER P2-REDO (don't add variables mid-validation).** **Status:** not started. **Logged:** 2026-06-27.

### L13 — ✅ BUILT 2026-06-29 (code done, config-gated default OFF, DEMO-test pending) — Manual-trade MANAGER: alert + auto-manage Imtiyaz's manual trades (Imtiyaz's spec)
**Account = MT5 HEDGING mode (confirmed 2026-06-27)** → opposite positions co-exist (hedge), don't net off.
**Want:** Imtiyaz manually piles onto the bot's BUY/SELL signal for more profit; the system then auto-manages
that manual leg.
**Part A — signal alert:** dashboard "🟢 BUY NOW @ price (win%/regime)" / "🔴 SELL NOW" lights up on a fresh
signal (+ optional sound) so Imtiyaz can open the manual trade. Ties to L9/L11.
**Part B — auto-manage the manual leg (new "manual-trade manager" subsystem):**
- [ ] **Detect** a manual trade (non-bot-MAGIC XAUUSD position; may need a dedicated "manual" tag/magic to
      tell it apart from Anisa's other manual trades).
- [ ] **On manual open → cap effective risk at 6%.** Compute the lot that = 6% account risk for the current
      SL distance (`risk6_lot = equity*6% / (100*sl_dist)`). If the manual lot ≤ risk6_lot → just set a 6% SL.
      If the manual lot > risk6_lot → **immediately HEDGE the EXCESS** (`manual_lot − risk6_lot`, opposite dir)
      so the NET at-risk volume = the 6%-equivalent lot; the excess is neutralised. Manage the net 6% leg with the 6% SL.
      Example: risk6_lot 0.50, manual 0.80 → hedge 0.30 now → net 0.50 at risk; on flip, hedge the remaining 0.50 (full lock).
- [ ] **On the bot's FLIP exit → open a HEDGE** (opposite direction, SAME size) against the manual leg →
      manual net risk = ZERO (P&L locked). Hedging account makes this possible.
- [ ] **On profit → at a TARGET TP (not the daily-equity TP) → close BOTH legs** (manual + its hedge / + bot),
      OR open the hedge against the manual leg to lock it.
**⚠️ Caveats / must-do:**
- Auto-opening hedge positions = real money moves → **DEMO-test heavily** before live; keep a master ON/OFF flag.
- The bot reads WHOLE-account equity → the manual leg's floating P&L can falsely trip the daily 9% ratchet →
  **needs L8 (manual-trade-aware / flow-adjusted equity) FIRST or together** so the bot isolates its own P&L.
- 6% manual SL + the extra leg = much higher total exposure/drawdown (Imtiyaz's choice).
- Define precisely which position is "the manual trade" (tag/magic) to avoid managing the wrong one.
**Status:** not started — design captured. **Logged:** 2026-06-27. **Depends on:** L8 (safety/equity), L9/L11.

### L7b — REMOVE vestigial code cleanly (Imtiyaz: "why label, just remove it") — AFTER DEMO
Labels were the safe interim (L7). Proper end-goal = delete the dead/unused code. NOT trivial — hidden deps:
- **ATR (`atr20_pct`)** is threaded through: `backtest_replay` predicted-TP scaling (`atr_usd`), `bridge_core.execute()`
  signature, `bridge_data` signal-log + **SQLite DB schema columns**, dashboard. Removing = ~6 files + a schema
  migration + handling the predicted-TP path. (ATR is NOT used in any live decision, only the info-only predicted path.)
- **Dead PBE / partial-close / full-breakeven / smart-exit** in `bridge_risk._update_buy/_sell` — ✅ **DONE
  2026-06-29:** dep-traced (every live VirtualTrade is `ratchet=True`; a non-ratchet trade is skipped at
  `execute()` line 191), then REMOVED `_update_buy`, `_update_sell`, `_smart_exit_check`; `update()` now always
  routes to `_update_ratchet`; trimmed the now-unused imports; `status()` fields kept (used by dashboard).
  Compile-OK, 0 nulls (mount-write corruption hit + stripped). `__init__`/`status` unchanged.
- **ATR (`atr20_pct`) removal — SAFE SUBSET DONE 2026-06-29 (live-neutral); DB/model parts deferred.**
  Established ATR is fully vestigial (dropped from FEATURE_COLS 2026-06-19; every read uses a default constant;
  `execute()`'s `atr20_pct` param was never used; `vol_regime` is "informational only, no filtering").
  REMOVED (behavior-neutral): the per-bar `📐 Live ATR20` display log + `result["atr20_pct"]` threading
  (`bridge_main`), and the unused `atr20_pct` parameter from `execute()` / `handle_opposite_signal()`
  (`bridge_core`). Both Read-verified complete (bash py_compile shows false truncation errors), 0 nulls.
  LEFT IN PLACE deliberately (need a stopped bot): the SQLite `atr20_pct` column (nullable — now logs 0, no
  live-DB migration), `inference.py` `vol_regime` constant, the `df["atr20_pct"]` compute, and
  `train_move_model.py` `atr_usd` (only matters on retrain). Finish these when the bot is stopped.
**How (do AFTER DEMO is stable — not mid-validation):**
- [ ] 4-round dep-trace each item (grep every usage; confirm no live path touches it).
- [ ] Remove + migrate the signal-log/DB schema (drop atr columns or keep nullable) without breaking logging.
- [ ] DEMO re-test the bridge after removal (no exceptions, signals still log, dashboard still renders).
**Why parked:** mid-DEMO removal of live code risks bugs in the running validation; labels are zero-risk for now.
**Status:** parked. **Logged:** 2026-06-28.

### L3 — ML Exit/TP-predictor model (Imtiyaz's idea)
Per-trade personalized TP from entry features, learned from the 13-TP sweep R(TP) curves + `peak_r`.
One-pass simulator → matched R(TP) table → label best TP (regression) → train small → WFO vs regime-TP.
Do only after the simple regime-TP is confirmed live.

### L4 — Fix OPEN bugs (from BUG_LOG.md / GUIDE §5b)
Six high-priority bugs already fixed; these remain open. Fix order:
- [x] **A 🔴 — ✅ DONE (verified 2026-06-29):** secondaries now flattened on EVERY daily-SL/TP halt path,
      guarded to fire ONLY on the fresh False→True transition (sticky flag would otherwise reconnect/close
      every poll): `bridge_main.py:360-365` (check_closed realized-loss halt), `bridge_core.py:369-372`
      (`check_daily_sl_intrabar` ratchet floor, 2s), `bridge_core.py:377-380` (`check_daily_tp_intrabar`).
      Plus all per-trade exits (flip/vSL/TP) already call `close_secondary_accounts()`. No code change needed.
      (Minor residual edge: on RESTART when daily-SL was already breached pre-restart, preload sets the sticky
      flag so no re-flatten — but those secondary trades were already closed when the SL first fired live.)
- [x] **F 🟡 — ✅ DONE (verified 2026-06-29; implemented 2026-06-27):** `backtest_replay.py:243-249` defaults
      `TRAIL_MODE` to the live config — when `--stop-trail` is omitted, uses `"htf"` if `ratchet_htf_sl` else
      `"line"`, so every default backtest/WFO matches live's HTF exit. Includes Bug J entry-SL match (H1 line,
      2.5% cap, lines 486-494) + H1 flip (315, 383-385). No code change needed.
- [x] **B 🟠 — ✅ DONE (found already fixed, verified 2026-07-01):** `bridge_core.py:649-654` — `recover_open_trades()`
      now reconstructs `open_time` from the real open duration (`tick.time − pos.time`), comment tags it
      "Bug B fix". Docs here were stale; code already had the fix.
- [x] **E 🟡 — ✅ DONE (found already fixed, verified 2026-07-01):** `backtest_replay.py:26-27` wraps
      `sys.stdout`/`sys.stderr` in a UTF-8 `TextIOWrapper` — the cp1252 emoji crash is handled. Docs here were stale.
- [ ] C 🟠 set live `SYMBOL` from the connected primary (matters once `MT5_PRIMARIES` failover is used).
      **Still open, confirmed 2026-07-01** — `bridge_constants.py:43` sets `SYMBOL` once at import from
      `MT5_ACCOUNTS[0]`; `connect_primary()` (bridge_multi.py) never updates it after a failover switch.
      Dormant only because `MT5_PRIMARIES` is currently unconfigured (no failover in use).
- [ ] D 🟠 (big refactor) one subprocess per MT5 terminal — root of the multi-account fragility. Later.
- [x] **M 🟠 — ✅ FIXED 2026-07-01:** `engine/run_wfo.py` — `--trail-mode` default was `"line"`, and
      `bt_cmd += ["--stop-trail", args.trail_mode]` only fired `if args.trail_mode != "line"`. Since Bug F
      made `backtest_replay.py` default to a **config-aware** trail (htf when live `ratchet_htf_sl=True`),
      omitting `--stop-trail` no longer meant literal M15-line — it meant "whatever config says" (htf).
      So `run_wfo.py --trail-mode line` (default or typed explicitly) silently ran HTF, not line.
      **Fix applied:** default changed `"line"` → `None`; forward condition changed to
      `if args.trail_mode is not None:`. Now: no flag → `None` → nothing forwarded → `backtest_replay.py`'s
      own config-aware default applies (htf today) — same result as before, now correct-by-design instead
      of accidental. Explicit `--trail-mode line` now genuinely FORCES line mode (previously silently ignored).
      `py_compile` clean. No other reference to `args.trail_mode` elsewhere in the file.
**Detail:** `docs/BUG_LOG.md`. Do C opportunistically; D is a project (see below, Imtiyaz flagged 2026-07-01).

---
*Logged 2026-06-26. Update status as runs complete.*

---

### Future Research Task - Clean Support / Resistance Features

| # | Task | Detail |
|---|------|--------|
| **SR-REDESIGN** | Build cleaner support/resistance feature candidates to replace weak OB/SR model inputs | Keep as research task only until validated. Candidate features: previous day high/low distance, weekly high/low distance, confirmed-only swing high/low distance, liquidity-zone distance, round-number distance, session high/low distance, and HTF structure levels based on BOS/CHOCH. Rules: no future candle, closed/confirmed levels only, no live trading rule until retrain + 3-month test + WFO gate. |
