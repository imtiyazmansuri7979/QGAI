# QGAI Runner Registry Guide

This file is the operator guide for BAT runners.

## Global Rules

- Registry-style BATs must have a stable ID in the BAT name, result folder, and summary file.
- Use `000` for baseline files and `001`, `002`, ... for test files when multiple CSVs are produced.
- If a runner says live model is not touched, it must write models to `data\models\test_workspace`.
- If a runner uses `--allow-in-sample`, it is display-only or diagnostic only, not OOS/profit proof.
- Never delete `.training_lock` until Task Manager or PowerShell confirms no `train.py`, `run_wfo.py`, `run_feature_sweep.py`, or `backtest_replay.py` process is running.
- If `signals_complete.csv` already has full history, do not rebuild it from an empty folder.

## Signal History

Full dashboard signal history is stored in:

- `engine/logs/signals_complete.csv`
- `backtest/results/fullhistory_regime/backtest_signals_st-htf.csv`
- `backtest/results/fullhistory_regime/backtest_trades_st-htf.csv`

`Start/0_START_ALL.bat` must preserve existing `signals_complete.csv` if full-history files are missing.

To rebuild dashboard history intentionally:

`Start/Rebuild_Dashboard_Signal_History.bat`

This uses `--allow-in-sample` and is display-only.

## Feature Sweep

- `FS67-01` creates the 3-month baseline.
- `FS67-02`, `FS67-03`, and `FS67-04` reuse `FS67-01` baseline and must not rerun baseline.
- `FS67-12` confirms `h4_support_dist` on OOS1Y.
- `FS67-21` is an optional 6-month WFO due-diligence run for `h4_support_dist`; baseline is not rerun.

## OOS Proof Order

1. 3-month clean screen
2. 1-year clean OOS confirmation
3. WFO
4. Demo/forward check

Do not adopt features from a 3-month screen alone.
