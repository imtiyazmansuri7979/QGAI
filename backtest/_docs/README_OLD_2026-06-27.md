# QGAI — Backtest folder INDEX / backtest folder ની INDEX

**Updated 2026-06-27.** Everything backtest/validation lives here. Old/superseded files are in `_archive_bats/`
and `results/_archive/` (nothing deleted — just moved). EN below, ગુજરાતી નીચે દરેક વિભાગમાં.

---

## ACTIVE bats / ચાલુ bats  (double-click to run; each cd's to `C:\QGAI\engine` and uses the full Python path)

**Data / training prep:**
| Bat | What it does |
|-----|--------------|
| `Run_Relabel_Trades.bat` | Relabel the training xlsx outcomes under the live exit (Option B) |
| `Run_Rebuild_Trainset.bat` | Rebuild the training ENTRY set from 2-SMMA flips, full history (Option A, parked) |

**Backtest reports (fast, single replay, real model):**
New: `Run_Live_Buffer_015_CSV.bat` = live-style 0.15% buffer replay. Output folder: `backtest/results/live_buffer_015/`; writes both trades CSV and signals CSV.
| Bat | What it does |
|-----|--------------|
| `Run_Backtest_Report.bat` | Full report: WR/PF/Avg R + BY REGIME/HOUR/MONTH |
| `Run_Backtest_FullHistory.bat` | 2022→2026 total dataset, global TP vs regime-adaptive (parked) |
| `Run_Capture_Analysis.bat` | Captured/Available move (exit-leak diagnostic) |

**TP studies:**
| Bat | What it does |
|-----|--------------|
| `Run_TP_Sweep.bat` / `_TEST` | 13-TP cap sweep (0.5→3.0) |
| `Run_TP_Regime.bat` / `_TEST` | Regime-adaptive TP (Rng 2.0 / Trn 1.0 / Vol 0.8) |

**WFO (walk-forward OOS — weekly retrain, slow ~1.5-2 hr, fixed 0.01 lot = clean R):**
| Bat | What it does |
|-----|--------------|
| `Run_WFO_TEST.bat` | 3-week smoke test (global + regime) — run FIRST |
| `Run_WFO_FULL.bat` | Full WFO, global TP (relabel baseline) |
| `Run_WFO_TPREGIME.bat` | Full WFO, regime-adaptive TP |
| `Run_WFO_OOS.bat` | First-4-weeks OOS quick run |
| `Run_WFO_Analyze.bat` | $10k weekly/monthly analysis of a WFO run |

**GU:** ઉપરના = ચાલુ bats. **Data prep** (relabel/rebuild) · **Reports** (full report / full-history / capture) ·
**TP studies** (sweep / regime) · **WFO** (OOS validation — પહેલા `Run_WFO_TEST`, પછી FULL + TPREGIME).
WFO બધા **fixed 0.01 lot** વાપરે (clean R). દરેક bat `C:\QGAI\engine` માં cd કરી full Python path વાપરે.

---

## RESULTS map / results ક્યાં જાય  (`backtest/results/`)

| Folder | Holds |
|--------|-------|
| `backtests/` | TP sweep + regime backtests (`tp_*`, `tp_regime`) |
| `wfo_results/` | Main WFO output (global TP baseline) |
| `wfo_tpregime/` | Regime-adaptive WFO (created when run) |
| `report/` | `Run_Backtest_Report` output |
| `replay_logs/` | Per-run trade/signal CSVs from replays |
| `baseline/` | Reference baseline trade log |
| `fullhistory/` | Full-history backtest (created when run) |
| `_archive/` | Old/superseded runs (old_runs/ · engine_tp_outputs/ · loose_txt/) |

**GU:** active results ઉપર; જૂના બધા `results/_archive/` માં (old_runs = જૂના folders, engine_tp_outputs =
engine માંથી ખસેડેલા TP outputs, loose_txt = છૂટા txt). કંઈ delete નથી થયું — ફક્ત move.

---

## ARCHIVE / આર્કાઇવ
- `_archive_bats/` — 17 superseded bats (trail variants, ablation, fixes A/B, all-backtests, reset).
  These ideas are DONE (trail modes tied; CTF/HTF now in config). Kept for history.
- `results/_archive/` — old result folders + the 21 stray `results_tp_*.txt` / `trades_tp_*.csv` that
  used to clutter `engine/`.
- `results/_archive/WRONG_WFO_tpEq3_DO_NOT_USE/` — ⛔ 15 INVALID WFO/sweep runs (all `--tp-equity 3`
  TP-bypass bug and/or pre-relabel). **Never quote their numbers** (incl. the old "PF 1.55 / +144R").
  Valid replacement = fresh `wfo_results/` + `wfo_tpregime/` (`--tp-equity 0`, relabeled). See that folder's README.

## NOTE — research scripts still in `engine/` / engine માં બાકી research scripts
One-off analysis scripts (not part of the live pipeline, not run by any bat) still sit in `engine/`:
`exit_backtest_1year.py`, `smart_exit_backtest.py`, `backtest_exits_tp.py`, `monte_carlo.py`,
`monte_carlo_segmented.py`, `tp_complete_analysis.py`. Left in place because they `import` engine modules
(`config`, `features`) and would break if moved. They are reference-only.
**GU:** આ one-off scripts engine/ માં જ રાખ્યા (engine modules import કરે છે, ખસેડે તો break થાય). ફક્ત reference.
