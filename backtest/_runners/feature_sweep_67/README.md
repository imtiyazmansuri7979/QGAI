# 67-Feature Validation Sweep Registry

Use this folder for the organized 67-feature validation sweep.
Every runner has a permanent registry ID. The same ID appears in the BAT
filename, result folder name, summary CSV, and per-feature trade/signal CSVs.
Per-feature CSVs also include a sort number: `000` is baseline, then
`001`, `002`, ... follow the test order. This keeps the view clean if all
CSVs are copied into one folder and sorted by name.

Root result folder:

`C:\QGAI\backtest\results\feature_sweep_67`

Models are trained only in:

`C:\QGAI\data\models\test_workspace`

The live model folder `data\models\final` is not touched.

## Registry

| ID | Runner | Result folder | Summary |
|---|---|---|---|
| `FS67-09` | `..\Run_FeatureSweep_TEST.bat` | `FS67-09_sanity_active2` | `FS67-09_sanity_active2_SUMMARY.csv` |
| `FS67-01` | `FS67-01_RUN_PriorityBatch.bat` | `FS67-01_priority_batch` | `FS67-01_priority_batch_SUMMARY.csv` |
| `FS67-02` | `FS67-02_RUN_Tier1_Active.bat` | `FS67-02_tier1_active` | `FS67-02_tier1_active_SUMMARY.csv` |
| `FS67-03` | `FS67-03_RUN_Tier2_HighProbability.bat` | `FS67-03_tier2_high_probability` | `FS67-03_tier2_high_probability_SUMMARY.csv` |
| `FS67-04` | `FS67-04_RUN_Tier3_Remaining.bat` | `FS67-04_tier3_remaining` | `FS67-04_tier3_remaining_SUMMARY.csv` |
| `FS67-11` | `FS67-11_RUN_PriorityBatch_OOS1YConfirm.bat` | `FS67-11_priority_batch_oos1y_confirm` | `FS67-11_priority_batch_oos1y_confirm_SUMMARY.csv` |
| `FS67-12` | `FS67-12_RUN_h4_support_OOS1YConfirm.bat` | `FS67-12_h4_support_oos1y_confirm` | `FS67-12_h4_support_oos1y_confirm_SUMMARY.csv` |

Optional all-in-one:

`FS67-00_RUN_ALL.bat`

This runs all stages in order and stops if any stage fails.

## Stage Gate

`FS67-01` to `FS67-04` are 3-month clean OOS screening tests only.
They use a local 3-month baseline.

Baseline reuse rule:

- `FS67-01` creates the 3-month baseline.
- `FS67-02`, `FS67-03`, and `FS67-04` reuse:
  `C:\QGAI\backtest\results\feature_sweep_67\FS67-01_priority_batch\baseline\result.json`
- If that baseline file is missing, run `FS67-01` first.

`FS67-11` is the OOS1Y confirmation runner for the priority batch. It uses
the same train cutoff and backtest window as `OOS1Y-01`:

- train cutoff: `2025-06-28`
- backtest: `2025-06-29 -> 2026-06-29`

Any feature that looks useful still needs:

1. Clean 1-year confirmation
2. WFO confirmation
3. Final live/demo check
