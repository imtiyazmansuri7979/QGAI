# QGAI — VALIDATION RESULTS (the evidence record) · 2026-06-28

Single source for "is the edge real?" — the numbers behind the client report (`QGAI_Validation_Report.docx`).
All figures are BACKTEST/simulation (fixed 0.01 lot, spread modelled). **DEMO forward-test = the real proof.**
**Reminder (RULEBOOK §0): these numbers are only valid because backtest == live config (HTF entry-SL + H1
flip + regime-TP), verified after the Bug F/J fix. Pre-fix numbers (e.g. the old "+321R") are VOID.**

## 1. Walk-forward OOS (41 weeks, Sep2025→Jun2026, weekly retrain, live config)
- **Regime-adaptive TP (LIVE config): PF 3.35 · WR 60.0% · +266.1R · 39/41 green weeks · avg +6.5R/wk.**
- Global TP 1.0 (comparison): +254.9R / 556 trades / 39 green. → regime WON, so it is ADOPTED.
- $10k 3% dynamic sim: Max DD ~18.7% (1%→6.6%, 2%→12.8%). Optimistic (in-distribution); real DD higher.

## 2. Full-history / OUT-OF-DISTRIBUTION (2022-2026) — the strongest evidence
Model trained only on Dec-2024+, so **2022/2023/2024 are TRULY UNSEEN**. Profitable EVERY year:

| Year | Trades | Win% | PF | Total R |
|------|--------|------|-----|---------|
| 2022 (unseen) | 176 | 58% | **2.81** | +77 |
| 2023 (unseen) | 224 | 60% | **3.10** | +110 |
| 2024 (unseen) | 281 | 61% | **3.53** | +150 |
| 2025 | 386 | 62% | 3.84 | +217 |
| 2026 H1 | 372 | 55% | 2.22 | +121 |
| **ALL** | **1,439** | 59% | ~2.4–3.0 | **+676R** |

→ Edge holds out-of-distribution across $1,700→$4,700 gold. **Structural, not overfit.**
Sanity check: the single-model full-history (+196R on the 9-mo window) is LOWER than the walk-forward WFO
(+255R) → NOT lookahead-inflated; if anything conservative. So the OOS years are trustworthy.

## 3. Consistency
- ~58 months tested, **only 3 modestly negative** — rest profitable.
- **Every weekday profitable** in every year. Best hours = Europe + NY sessions (16:00 dominant) every year.
- Full grids: `backtest/results/signal_log_full/TEMPORAL_BREAKDOWN.txt` + `QGAI_Trade_Analysis.xlsx`.

## 4. Trade statistics (1,439 trades)
WR 59.2% · expectancy +0.47R · avg win +1.18R · avg loss −0.56R (capped −1R) · best +4.71R.
Exit engine: **TPCAP 516 trades, 100% win, +843R**. SL −150R, TRAIL −101R (drag), FLIP +83R.
Max win streak 13 · **max loss streak 10** (~−26% at 3% — the real DD risk).

## 5. Honest caveats (always state to clients)
- Past performance ≠ future. Backtest/sim, not live.
- 3% risk = aggressive → ~19% sim DD, ~26% streak DD. 1-2% safer.
- WFO has mild in-distribution optimism; the 2022-24 OOS test is the conservative, reliable one.
- DEMO forward-test (in progress) is the final confirmation before scaling.

## 6. Trade-count reconciliation (common question)
Same 9-mo window: full-history subset 520 ≈ WFO regime 525 (consistent). The "386" = 2025 CALENDAR year
(different span). The old "725" = the VOID M15 run. Counts depend on TP cap (tighter=more), entry-SL
(M15=more), filters — all config, nothing missing.

---
*Deliverable: `QGAI_Validation_Report.docx` (client). Data: `backtest/results/signal_log_full/`,
`wfo_results/`, `wfo_tpregime/`, `QGAI_Trade_Analysis.xlsx`. Update when re-validated.*
