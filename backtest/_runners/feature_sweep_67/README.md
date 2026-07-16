# 67-Feature Validation Sweep Registry

Use this folder for the organized 67-feature validation sweep.
Every runner has a permanent registry ID. The same ID appears in the BAT
filename, result folder name, summary CSV, and per-feature trade/signal CSVs.
Per-feature CSVs also include a sort number: `000` is baseline, then
`001`, `002`, ... follow the test order. This keeps the view clean if all
CSVs are copied into one folder and sorted by name.

Main operator guide:

`C:\QGAI\docs\RUNNER_REGISTRY_GUIDE.md`

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
| `FS67-13` | `FS67-13_RUN_Tier1DropCandidates_OOS1YConfirm.bat` (+ `_TEST.bat`) | `FS67-13_tier1_drop_candidates_oos1y_confirm` (+ `_TEST`) | `FS67-13_tier1_drop_candidates_oos1y_confirm_SUMMARY.csv` |
| `FS67-21` | `FS67-21_RUN_h4_support_WFO6M.bat` | `FS67-21_h4_support_wfo6m_20251229_20260629` | `_WFO_SUMMARY.csv` |

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

`FS67-13` is the OOS1Y confirmation runner for the 6 `DROP_CANDIDATE`
features found by `FS67-02`'s 3-month screen (`ts_bars_since_flip`,
`15_min_slot`, `M15_DI_diff`, `slot_cos`, `mins_to_next_3star`, `M15_ADX`).
Same `OOS1Y-01` window/cutoff as `FS67-11`/`FS67-12`. `in_range_phase` was
also a `DROP_CANDIDATE` on FS67-02 but is deliberately excluded — already
decided (2026-07-16) to keep it as-is.

Run `FS67-13_RUN_Tier1DropCandidates_OOS1YConfirm_TEST.bat` first (house
rule: test-run before any long run) — it tests only 1 feature (`M15_ADX`)
in an isolated `_TEST` result folder to confirm no crash / leakage-guard
PASS / correct output location before committing to the full 6-feature
run in `FS67-13_RUN_Tier1DropCandidates_OOS1YConfirm.bat`.

Any feature that looks useful still needs:

1. Clean 1-year confirmation
2. WFO confirmation
3. Final live/demo check
