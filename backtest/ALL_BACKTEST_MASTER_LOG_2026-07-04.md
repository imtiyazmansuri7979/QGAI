# QGAI All Backtest Master Log - 2026-07-04

## Purpose

This is the single master log for the current QGAI backtest and research loop.

It combines:

- Baseline full backtest.
- Exit improvement research.
- BUY/SELL entry timing research.
- SELL early-entry real replay.
- Entry + exit combined replay.
- Entry variant 3-way test.
- Stopped/rejected tests.
- Exit TP-cap sweep setup.

Important:

- Live trading code was not changed by this research.
- Main period: 2025-06-29 to 2026-06-29.
- Starting equity: $10,000.
- Fixed lot: 0.01.
- Replay risk setting: 3%.
- Results below are fixed-lot replay results unless stated otherwise.

## Main Result Ranking

| Rank | Test | Rule / Change | Trades | WR | PF | Avg R | Total R | Real Amount | Max DD | Decision |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | Entry A | SELL early confirm2 TV + TRAIL_CONFIRM_2BAR + max_open=2 | 1128 | 63.9% | 3.74 | +0.618R | +697.3R | +$18,445.2 | 1.7% | Best performance candidate; needs risk validation |
| 2 | Combo | SELL early confirm2 TV + TRAIL_CONFIRM_2BAR + max_open=1 | 621 | 62.5% | 3.45 | +0.603R | +374.7R | +$9,755.6 | 1.1% | Safe/simple improvement |
| 3 | Exit only | TRAIL_CONFIRM_2BAR | 636 | 62.6% | 3.33 | +0.579R | +368.4R | +$9,727.5 | 1.1% | Accepted exit candidate |
| 4 | Entry only | SELL early confirm2 TV | 629 | 62.5% | 3.36 | +0.580R | +364.6R | +$9,495.3 | 0.9% | Passed first entry replay |
| 5 | Baseline | Original system | 644 | 62.3% | 3.23 | +0.544R | +350.2R | +$9,400.9 | 0.9% | Reference |
| 6 | Entry B | Volatile SELL early only + win_prob >= 0.60 | 636 | 62.6% | 3.33 | +0.579R | +368.4R | +$9,727.5 | 1.1% | Reject / not better than combo |
| 7 | Profit lock 1.00->0.25R | Lock +0.25R after +1.00R MFE | 685 | 63.8% | 3.01 | +0.475R | +325.4R | +$8,948.1 | 0.9% | Reject |
| 8 | Profit lock 0.75->0.10R | Lock +0.10R after +0.75R MFE | 688 | 65.6% | 3.08 | +0.465R | +320.1R | +$8,912.6 | 0.9% | Reject |

## Baseline

Folder:

`C:\QGAI\backtest\results\fullbt_hmm_10k_lot001`

Summary:

- Trades: 644.
- Wins / losses: 401 / 243.
- Win rate: 62.3%.
- Profit factor: 3.23.
- Avg R: +0.544R.
- Total R: +350.2R.
- Real amount: +$9,400.9.
- Capture efficiency: 8.5%.
- Max DD: 0.9%.

Direction split:

- BUY: 301 trades, +190.7R, avg +0.633R, +$4,609.5.
- SELL: 343 trades, +159.6R, avg +0.465R, +$4,791.3.

Decision:

- Baseline is the clean reference for all comparisons.
- SELL side was weaker by avg R, so SELL entry timing became the first target.

## Exit Research

Folder:

`C:\QGAI\backtest\results\available_move_vs_captured_move_research`

Accepted candidate:

`TRAIL_CONFIRM_2BAR`

Result:

- Trades: 636.
- Win rate: 62.6%.
- Profit factor: 3.33.
- Avg R: +0.579R.
- Total R: +368.4R.
- Real amount: +$9,727.5.
- Capture efficiency: 8.8%.
- Max DD: 1.1%.

Delta vs baseline:

- +18.2R.
- +$326.6.
- PF improved from 3.23 to 3.33.
- Capture improved from 8.5% to 8.8%.
- Max DD increased from 0.9% to 1.1%.

Rejected:

- `PROFIT_LOCK_0.75R_TO_0.10R`: -30.1R vs baseline.
- `PROFIT_LOCK_1.00R_TO_0.25R`: -24.8R vs baseline.

Decision:

- Accept `TRAIL_CONFIRM_2BAR`.
- Reject profit-lock variants because they improved win rate but reduced total R, avg R, PF, dollars, and capture efficiency.

## Entry Timing Research

Folder:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research`

Phase findings:

- BUY avg 8-bar price-late edge: +0.943R.
- SELL avg 8-bar price-late edge: +0.941R.
- BUY first same-signal edge: +0.320R.
- SELL first same-signal edge: +0.365R.
- Main practical blocker was active trade slot / `max_open=1`.

First real candidate:

`SELL_EARLY_SIGNAL_CONFIRM_2_TV`

Rule:

- SELL only.
- Wait for 2 consecutive clean SELL signals.
- HMM state must be Trending or Volatile.
- No live code change.

Entry-only result:

- Trades: 629.
- Win rate: 62.5%.
- Profit factor: 3.36.
- Avg R: +0.580R.
- Total R: +364.6R.
- Real amount: +$9,495.3.
- Max DD: 0.9%.

Delta vs baseline:

- +14.4R.
- +$94.4.
- PF improved from 3.23 to 3.36.
- Max DD flat.

Direction split:

- BUY: 278 trades, +188.0R.
- SELL: 351 trades, +176.6R.
- SELL improved by +17.0R vs baseline.

Decision:

- Entry-only candidate passed first replay.
- Keep for combo testing.

## Combo Entry + Exit

Folder:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\combo_sell_early_trail_confirm2_fullbt`

Rule:

- Entry: `SELL_EARLY_SIGNAL_CONFIRM_2_TV`.
- Exit: `TRAIL_CONFIRM_2BAR`.
- max_open=1.

Result:

- Trades: 621.
- Win rate: 62.5%.
- Profit factor: 3.45.
- Avg R: +0.603R.
- Total R: +374.7R.
- Real amount: +$9,755.6.
- Capture efficiency: 8.8%.
- Max DD: 1.1%.

Delta vs baseline:

- +24.5R.
- +$354.7.
- PF improved from 3.23 to 3.45.
- Avg R improved from +0.544R to +0.603R.

Direction split:

- BUY: 278 trades, +198.6R, +$4,694.9.
- SELL: 343 trades, +176.1R, +$5,060.7.

Decision:

- Combo is better than baseline.
- Combo is the safer/simple improvement because it keeps max_open=1.

## Entry Variant 3-Way Test

Runner:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\RUN_ENTRY_VARIANT_3WAY_FULL_BACKTEST.bat`

All variants included:

- `TRAIL_CONFIRM_2BAR`

### A - max_open=2

Folder:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\entrytest_A_maxopen2_fullbt`

Result:

- Trades: 1128.
- Win rate: 63.9%.
- Profit factor: 3.74.
- Avg R: +0.618R.
- Total R: +697.3R.
- Real amount: +$18,445.2.
- Capture efficiency: 16.6%.
- Max DD: 1.7%.

Split:

- BUY: 505 trades, +370.3R, +$8,901.0.
- SELL: 623 trades, +326.9R, +$9,544.2.
- SELL early trades: 286.

Decision:

- Current best performance candidate.
- Confirms `max_open=1` was a major blocker.
- Needs extra risk validation because max_open=2 increases exposure.

Risk validation report:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\A_MAXOPEN2_RISK_VALIDATION_2026-07-04.md`

Key risk findings:

- Max simultaneous open trades observed: 2.
- Time with exactly 2 open trades: 3,363.8 hours.
- Share of replay time with 2 open trades: 38.8%.
- Share of replay time with 3+ open trades: 0.0%.
- Two-open direction mix:
  - BUY+BUY: 57.0%.
  - SELL+SELL: 42.3%.
  - BUY+SELL: 0.7%.
- Worst overlapping pair: BUY+BUY, combined -5.597R / -$99.0.
- Every 100-trade blocks were all positive; weakest block was trades 1101-1128 with +11.7R.
- Monthly results were all positive; weakest month was 2025-06 with +0.8R.

Risk validation decision:

- A remains the best performance candidate.
- A is not live-ready until max_open=2 policy is decided.
- The next research should test whether the second trade should be:
  - any direction,
  - same direction only,
  - or one BUY + one SELL only.

### B - Strong Volatile SELL Only

Folder:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\entrytest_B_strong_volatile_win060_fullbt`

Rule:

- SELL early only in Volatile state.
- win_prob >= 0.60.
- max_open=1.

Result:

- Trades: 636.
- Win rate: 62.6%.
- Profit factor: 3.33.
- Avg R: +0.579R.
- Total R: +368.4R.
- Real amount: +$9,727.5.
- Max DD: 1.1%.
- SELL early trades: 25.

Decision:

- Reject for now.
- Too strict; it blocks most early-entry benefit.
- Weaker than combo.

### C - Replace Weak Open Trade

Folder:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\entrytest_C_replace_weak025_fullbt`

Rule:

- max_open=1.
- If a new early SELL appears while one trade is open, close the current weak trade if current R <= +0.25R.
- Then allow early SELL.

Status when stopped:

- Progress: 1,999 / 23,607 bars, about 8.5%.
- Closed trades: 44.
- Equity: $10,208.06.
- Total so far: +15.9R / +$208.1.
- Max DD so far: 0.32%.
- Early SELL triggers: 100.
- Replacement count: 30.

Partial split:

- BUY: 7 trades, +11.2R, avg +1.599R.
- SELL: 37 trades, +4.7R, avg +0.127R.
- SELL WR: 51.4%.

Exit reasons so far:

- `REPLACE_EARLY_SELL_R<=0.25`: 30.
- `FLIP`: 9.
- `TPCAP`: 3.
- `SL`: 1.
- `TRAIL_CONFIRM_2BAR`: 1.

Decision:

- Stopped and rejected for now.
- Reason: too much churn. The +0.25R replacement threshold is too aggressive.

Future alternative:

- Retest with stricter threshold such as `<= 0.00R` or `<= -0.10R`.

## Exit TP-Cap Sweep Setup

Runner:

`C:\QGAI\backtest\results\available_move_vs_captured_move_research\RUN_EXIT_TP_CAP_SWEEP_050_TO_300.bat`

Purpose:

- Sweep fixed TP-cap exit from 0.50% to 3.00%, step 0.10%.
- Total 26 tests.
- Helps create intuition and labels for future Exit AI model.

Important:

- Regime TP is OFF for this sweep.
- Only `--tp-cap` changes.
- Live code is not changed.
- Run after entry variant decision is stable.

Output:

`C:\QGAI\backtest\results\available_move_vs_captured_move_research\exit_tp_cap_sweep_050_to_300`

Status:

- Runner and summary script created.
- Full 26-test sweep not yet completed.

## Current Working Decision

Current ranking:

1. `A max_open=2`: best performance candidate; needs risk validation.
2. `Combo max_open=1`: safer/simple improvement.
3. `TRAIL_CONFIRM_2BAR`: accepted exit building block.
4. `SELL_EARLY_SIGNAL_CONFIRM_2_TV`: passed entry-only replay.
5. `B strong volatile win>=0.60`: reject.
6. `C replace weak <= +0.25R`: stopped/reject for now.
7. Profit-lock exit variants: reject.

## Signal Log Entry Diagnosis

Report:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\SIGNAL_LOG_ENTRY_PROBLEM_DIAGNOSIS_2026-07-04.md`

Key findings:

- A max_open=2 is mostly same-direction repeat/add-on trades, not a clean entry fix.
- A overlap add-ons:
  - Any overlap add-ons: 444 trades, +253.2R.
  - Same-direction add-ons: 426 trades, +240.8R.
  - Opposite-direction add-ons: 18 trades, +12.4R.
- Same-direction add-ons happen quickly:
  - <= 1 M15 bar: 286 trades, +165.6R.
  - <= 4 M15 bars: 356 trades, +206.6R.
- Baseline signal-cluster first-bar entries are strongest:
  - First signal bar: 383 trades, +287.8R, avg +0.751R.
  - Later cluster entries have weaker average R.

Updated interpretation:

- `max_open=2` is a position-scaling/add-on candidate.
- It should not be treated as the entry-timing solution.
- The real entry-timing solution should use signal clusters with `max_open=1`.

Recommended next research:

- `SIGNAL_CLUSTER_EARLY_ENTRY_V1`
- Keep `max_open=1`.
- Allow only one trade per signal cluster.
- Test first-cluster signal and 2-bar confirmation for BUY/SELL.

## Recommended Next Work

Before live consideration:

- Decide max_open=2 policy using A validation:
  - any two trades,
  - one BUY + one SELL only,
  - same-direction add only,
  - or limited by account/risk state.

Then:

- Run the exit TP-cap sweep if still needed for Exit AI model groundwork.
- Build Exit AI dataset only after final entry behavior is chosen.

## Entry max_open=2 Policy Tests

Runner:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\RUN_ENTRY_MAXOPEN2_POLICY_TESTS.bat`

Purpose:

- Decide how the second open trade should be allowed.
- A current reference allows any second trade.
- Risk validation showed two-open time is mostly same-direction:
  - BUY+BUY: 57.0%.
  - SELL+SELL: 42.3%.
  - BUY+SELL: 0.7%.

New policy tests:

- P1: `same_direction_only`
- P2: `opposite_direction_only`
- P3: `any` direction, but block same-direction add within 4 M15 bars.

Output summary:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\ENTRY_MAXOPEN2_POLICY_COMPARISON_2026-07-04.md`

Status:

- Runner created.
- 1-week smoke test passed for `same_direction_only`.
- Full policy tests not yet completed.

## Resume Rule

Long backtests are resume-able:

- If checkpoint exists, run the same BAT again to resume.
- If report exists and no checkpoint exists, the BAT normally skips.
- For a fresh rerun, delete only that specific output folder/report.

## ADX6 Strength Soft Entry Tests

Runner:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\RUN_ADX6_STRENGTH_SOFT_TESTS.bat`

Purpose:

- Replace/compare the current hard counter-trend-fade entry block with a softer H1/H4 strength score.
- Entry timing remains M15.
- H1/H4 ADX context is used only as strength confirmation, not as the primary timing trigger.

Score design:

- Uses the existing 6 parameters:
  - `H1_ADX`
  - `H4_ADX`
  - `H1_DI_diff`
  - `H4_DI_diff`
  - `h1_adx_slope`
  - `h4_adx_slope`
- BUY strength: ADX + positive DI_diff + positive ADX slope.
- SELL strength: ADX + negative DI_diff + positive ADX slope.
- Margin = trade-side strength minus opposite-side strength.

Test variants:

- S1: hard CTF OFF, H1/H4 weights `40/60`, ADX6 adverse margin `<= -10`, threshold `+0.05`.
- S2: hard CTF OFF, H1/H4 weights `35/65`, ADX6 adverse margin `<= -10`, threshold `+0.05`.
- S3: hard CTF OFF, H1/H4 weights `50/50`, ADX6 adverse margin `<= -10`, threshold `+0.05`.

Output summary:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\ADX6_STRENGTH_SOFT_COMPARISON_2026-07-04.md`

Status:

- Runner created.
- Summary script created.
- Smoke test passed and verified `adx6_*`, `adx6_weight_h1`, and `adx6_weight_h4` audit columns in `backtest_signals_st-htf.csv`.
- Full ADX6 tests not yet completed.

## SMMA MTF Score Entry Tests

Runner:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\RUN_SMMA_MTF_SCORE_TESTS.bat`

Purpose:

- Test 2-SMMA multi-timeframe alignment as a soft 0-100 score, not a hard block.
- Entry timing remains M15.
- H1/H4 are context/background.
- Current hard CTF filter is forced OFF for clean comparison.

Score design:

- Main recommended weights: M15 = 25, H1 = 35, H4 = 40.
- Extra variants test H4-strong `20/35/45` and balanced `33/33/34`.
- If a timeframe's 2-SMMA trend aligns with the trade direction, it contributes its weight.
- Score range: 0 to 100.

Test variants:

- S1 HTF recommended: M15/H1/H4 `25/35/40`; score `< 30` -> threshold `+0.05`; score `< 50` -> threshold `+0.03`.
- S2 HTF strong: M15/H1/H4 `20/35/45`; score `< 30` -> threshold `+0.05`; score `< 50` -> threshold `+0.03`.
- S3 balanced: M15/H1/H4 `33/33/34`; score `< 30` -> threshold `+0.05`; score `< 50` -> threshold `+0.03`.

Output summary:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\SMMA_MTF_SCORE_COMPARISON_2026-07-04.md`

Status:

- Runner created.
- Summary script created.
- Smoke test passed with SMMA `25/35/40` and ADX `40/60`; verified SMMA/ADX audit columns in `backtest_signals_st-htf.csv`.
- Full SMMA MTF tests not yet completed.

## Overnight SMMA + ADX Full Test Runner

Runner:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\RUN_OVERNIGHT_SMMA_ADX_FULL_TESTS.bat`

Purpose:

- One no-pause BAT for full night run.
- Runs SMMA MTF score tests first, then ADX6 strength tests.
- Resume-safe:
  - If `backtest_checkpoint_st-htf.pkl` exists, the test resumes.
  - If `backtest_report.txt` exists, the test is skipped.
- This is research-only; live trading code is not changed.

Current detected partial run:

- `smma_mtf_w25_35_40_fullbt` has a checkpoint and no final report, so the overnight runner will resume this first.

## Continuous Score Full Tests

Runner:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\RUN_CONTINUOUS_SCORE_FULL_TESTS.bat`

Summary:

`C:\QGAI\backtest\results\buy_sell_entry_timing_research\CONTINUOUS_SCORE_COMPARISON_2026-07-05.md`

Purpose:

- Run after the last bucket/weight test is complete.
- Test whether SMMA/ADX score differences produce real entry differences when the penalty is gradual instead of bucket-based.
- Resume-safe and no-pause for night run.
- Research-only; live trading code is not changed.

New audit columns in signal log:

- `adx6_penalty`
- `adx6_penalty_mode`
- `smma_penalty`
- `smma_penalty_mode`

Test variants:

- SMMA linear W25/35/40, target 70, max threshold penalty `+0.06`.
- SMMA linear W25/35/40, target 80, max threshold penalty `+0.06`.
- SMMA linear W10/30/60, target 70, max threshold penalty `+0.06`.
- ADX linear W40/60, adverse margin scale 30, max threshold penalty `+0.06`.
- ADX linear W25/75, adverse margin scale 30, max threshold penalty `+0.06`.
- ADX linear W50/50, adverse margin scale 20, max threshold penalty `+0.06`.

Status:

- Runner created.
- Summary script created.
- Smoke test passed and verified continuous penalty columns in `backtest_signals_st-htf.csv`.
