# Exit-Model / Exit-AI Work Stream Registry

Use this folder for the exit-side work stream (Fable-5's 4th opinion, 2026-07-13:
smart Exit-AI vs rule-based exits). Same registry convention as
`backtest/_runners/feature_sweep_67`: every runner has a permanent ID, and the
same ID appears in the BAT filename, the result folder name, and the summary
CSV/report files inside it.

Root result folder:

`C:\QGAI\backtest\results\exit_workstream`

Current priority: this work stream is **TOP PRIORITY** as of 2026-07-16 — see
`docs\TASKS.md` top section ("Exit Model / Exit-AI work stream") for the full
5-step plan and current status of each step.

## Registry

| ID | Runner | Result folder | Status |
|---|---|---|---|
| `EXIT01` | `EXIT01_RUN_PostCapContinuationAudit.bat` | `EXIT01_post_cap_continuation_audit` (3-mo) + `EXIT01_post_cap_continuation_audit_OOS1Y` (1-yr) | DONE 2026-07-17 |
| `EXIT01b` | `EXIT01b_RUN_SkipAvailableMove_OOS1Y.bat` | `EXIT01b_skip_available_move_OOS1Y` | DONE 2026-07-17 |
| `EXIT03` | `EXIT03_RUN_PeakRatchetLock_TEST.bat` (2-wk, 2 arms) + `EXIT03_RUN_PeakRatchetLock_OOS3M.bat` (3-mo, 10 arms) | `EXIT03_peak_ratchet_lock_TEST` / `EXIT03_peak_ratchet_lock_OOS3M` | READY — run TEST first |

Reserved (not yet built):

- `EXIT02` — partial-exit-at-cap (rejected by Fable-5: big-winner-dependency FAIL on 1Y data)
- `EXIT04` — two-speed trailing SL (tighter trail in Ranging, wider in Volatile)
- `EXIT05` — exit-AI phase 1 binary gating classifier (blocked on EXIT03-04)

## Stage Gate

`EXIT01` is read-only (no model, no retrain, no live/demo impact) and is the
decision gate for the whole work stream.

### EXIT01 Results (2026-07-17)

**3-month OOS (131 trades, 42 TPCAP):**
- 33% favorable / 67% unfavorable
- Total: **-5.53R** (cap correct on small sample)

**1-year OOS (1130 trades, 220 TPCAP):**
- 38% favorable / 62% unfavorable
- Total: **+28.28R** left on table (cap leaving money)
- Median: -11.30 pts (typical trade reverses)
- Avg giveback: +46.49 pts (volatile after cap)
- Exit mix: TRAIL_SL 182, HTF_FLIP 38

**Interpretation:** majority of trades reverse after cap (62%), but the 38%
that continue carry such large profits that the NET is +28R. Median is
negative = typical trade is better off with cap. This is a fat-tail pattern:
partial-exit-at-cap (EXIT02) is the natural next step — take some profit at
cap, let the rest trail for the big continuations.

Per Fable-5's sample-size warning: do not start any exit-AI model training
(`EXIT05`) below ~500-1000 trades (effective N for an exit model is trade
count, not bar count — in-trade bars are heavily autocorrelated).
