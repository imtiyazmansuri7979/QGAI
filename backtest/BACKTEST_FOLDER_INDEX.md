# QGAI Backtest Folder Index

Updated: 2026-07-04

## Start Here

Use this menu for normal work:

`C:\QGAI\backtest\RUN_BACKTEST_MENU.bat`

## Folder Layout

| Folder | Purpose |
|---|---|
| `_runners` | Main/root backtest BAT runners moved from the root folder. |
| `_docs` | Workflow reports and generated docs from root. |
| `_scripts` | Older loose analysis/backtest Python utilities from root. |
| `_archive_bats` | Older archived BAT files that were already archived. |
| `results` | All output folders and active research folders. |

## Current Important Runners

| Task | File |
|---|---|
| SELL early-entry real backtest | `results\buy_sell_entry_timing_research\RUN_SELL_EARLY_CONFIRM2_TV_FULL_BACKTEST.bat` |
| Baseline full backtest + BUY/SELL entry research | `results\buy_sell_entry_timing_research\RUN_FULL_BACKTEST_THEN_BUY_SELL_ENTRY_RESEARCH.bat` |
| Baseline full HMM 10k lot001 only | `_runners\Run_FullBT_HMM_10k_lot001.bat` |
| Exit Phase 3 research menu | `results\available_move_vs_captured_move_research\RUN_PHASE3_RESEARCH_MENU.bat` |
| Combined entry + exit real backtest | `results\buy_sell_entry_timing_research\RUN_COMBO_SELL_EARLY_PLUS_TRAIL_CONFIRM2_FULL_BACKTEST.bat` |
| Entry variant 3-way full backtest | `results\buy_sell_entry_timing_research\RUN_ENTRY_VARIANT_3WAY_FULL_BACKTEST.bat` |
| Entry max_open=2 policy tests | `results\buy_sell_entry_timing_research\RUN_ENTRY_MAXOPEN2_POLICY_TESTS.bat` |
| Exit TP-cap sweep 0.50 to 3.00 | `results\available_move_vs_captured_move_research\RUN_EXIT_TP_CAP_SWEEP_050_TO_300.bat` |
| WFO live-match buffer 0.15 | `_runners\Run_WFO_LiveMatch_Buf015.bat` |

## Important Results

| Result | Folder |
|---|---|
| All backtest master log | `ALL_BACKTEST_MASTER_LOG_2026-07-04.md` |
| Baseline full backtest | `results\fullbt_hmm_10k_lot001` |
| BUY/SELL entry timing research | `results\buy_sell_entry_timing_research` |
| SELL early-entry candidate result | `results\buy_sell_entry_timing_research\sell_early_confirm2_tv_fullbt` |
| Combined entry + exit candidate result | `results\buy_sell_entry_timing_research\combo_sell_early_trail_confirm2_fullbt` |
| Entry variant A/B/C results | `results\buy_sell_entry_timing_research\entrytest_*_fullbt` |
| Entry variant A/B/C decision log | `results\buy_sell_entry_timing_research\ENTRY_VARIANT_3WAY_DECISION_LOG_2026-07-04.md` |
| A max_open=2 risk validation | `results\buy_sell_entry_timing_research\A_MAXOPEN2_RISK_VALIDATION_2026-07-04.md` |
| Entry max_open=2 policy comparison | `results\buy_sell_entry_timing_research\ENTRY_MAXOPEN2_POLICY_COMPARISON_2026-07-04.md` |
| Signal-log entry problem diagnosis | `results\buy_sell_entry_timing_research\SIGNAL_LOG_ENTRY_PROBLEM_DIAGNOSIS_2026-07-04.md` |
| Available move vs captured move research | `results\available_move_vs_captured_move_research` |
| Exit TP-cap sweep results | `results\available_move_vs_captured_move_research\exit_tp_cap_sweep_050_to_300` |
| Live buffer 0.15 comparison | `results\live_buffer_015` |

## Resume Rule

Long backtests are resume-able now:

- If a checkpoint exists, run the same BAT again and it resumes.
- If report already exists and no checkpoint exists, the main BAT skips rerun.
- For a fresh rerun, delete the specific output folder/report first.

## Gujarati Quick Guide

- Normal કામ માટે `RUN_BACKTEST_MENU.bat` ચલાવો.
- Fresh baseline ફરી ચલાવવાની જરૂર નથી જો `results\fullbt_hmm_10k_lot001\backtest_report.txt` છે.
- SELL early-entry test માટે option 1 ચલાવો.
- Result આવ્યા પછી baseline vs candidate compare કરવું.
