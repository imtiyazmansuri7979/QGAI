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
| `EXIT01` | `EXIT01_RUN_PostCapContinuationAudit.bat` | `EXIT01_post_cap_continuation_audit` | ⏳ built, not yet run |

Reserved (not yet built — will be added here once implemented, per the
sequencing in `docs/TASKS.md`):

- `EXIT02` — TP-cap-as-trail-tighten redesign + WFO A/B (blocked on `EXIT01`'s result)
- `EXIT03` — switch north-star metric to MFE-capture (methodology change, no runner of its own)
- `EXIT04` — grow trade sample (longer backtest windows / more regimes)
- `EXIT05` — exit-AI phase 1 binary gating classifier (blocked on EXIT01-04)

## Stage Gate

`EXIT01` is read-only (no model, no retrain, no live/demo impact) and is the
decision gate for the whole work stream: if it shows real money left on the
table after the TP-cap (positive continuation R, small giveback), `EXIT02` is
worth building. If giveback is large relative to extra R, the cap is already
doing its job — retire the capture% target instead of chasing it with a
redesign.

Per Fable-5's sample-size warning: do not start any exit-AI model training
(`EXIT05`) below ~500-1000 trades (effective N for an exit model is trade
count, not bar count — in-trade bars are heavily autocorrelated).
