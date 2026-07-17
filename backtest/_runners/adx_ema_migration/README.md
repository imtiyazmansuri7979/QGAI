# ADX Wilder → EMA Migration — Registry

Same registry convention as `exit_workstream/` and `feature_sweep_67/`:
every runner has a permanent ID, and the same ID appears in the BAT
filename, the result folder name, and the summary/report files inside it.

**Background:** Imtiyaz flagged (2026-07-17) "you use wilder adx for all
calculation it wong." Investigation found the bug was real but narrower
than first assumed — `adx_merged.csv` (`M15/H1/H4_ADX`, `*_DI_diff`) was
always EMA-based; only `h4_adx_slope`/`h1_adx_slope`/`ts_adx_switch_trend`
(via `features.py:_wilder_adx()`) used Wilder smoothing. Ground truth:
the live MT5 EA calls `iADX()` (EMA-style), not `iADXWilder()`. Fixed in
git commit `e1ce9fc` — see `docs/BUG_LOG.md` §S and
`docs/FIXES_CHANGELOG4.md` (2026-07-17) for full detail.

`indicators_merged.csv` regenerated + verified, model retrained same day
(`model_created_at: 2026-07-17T20:15:55`).

## Registry

| ID | Runner | Result folder | Status |
|---|---|---|---|
| `ADXMIG-01` | `ADXMIG-01_RUN_MT5ParityTest.bat` | `ADXMIG-01_mt5_parity_test` | Step 1 (Python export) automated; step 2 (MT5-terminal script) requires Imtiyaz to run manually |
| `ADXMIG-02` | *(not yet built)* | *(reserved)* | 3-month OOS backtest on the retrained model — next action |

## Pre-fix reference archive

The full pre-fix codebase snapshot, retrained-over model set, and every
historical backtest/WFO/feature-sweep result folder generated under the
old Wilder-scale slope features were archived (SHA-256 hashed, read-only)
before the fix, per Imtiyaz's request for a full enterprise-style
migration record:

```
C:\OLD_QGAI\QGAI_ARCHIVE\ADX_WILDER\WILDER-REG-001\   — Wilder-era archive (read-only, DO NOT reuse)
C:\OLD_QGAI\QGAI_BACKUPS\                              — full pre-migration C:\QGAI backup
C:\OLD_QGAI\QGAI_MIGRATION\                            — audit report + final migration report
```

These live OUTSIDE the active `C:\QGAI` project (they are historical
records, not part of the working codebase) — see
`C:\OLD_QGAI\QGAI_MIGRATION\WILDER_TO_EMA_MIGRATION_REPORT.md` for the
full account of what was archived and why.

## Stage gate

`ADXMIG-01` (MT5 parity) and `ADXMIG-02` (3-month OOS backtest +
`docs/BACKTEST_RESULT_AUDIT.md` pass) must both complete before any
keep/live decision on the retrained model, per standing house rule
(current validation stage is 3-month OOS only — do not skip to
1-year/WFO).
