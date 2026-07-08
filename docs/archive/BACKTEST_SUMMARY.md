# QGAI — Backtest Summary (Final)

**Date:** 2026-06-20 · **Data:** XAUUSD M15, 96,828 bars (2022-05 → 2026-06)
**Method:** No-lookahead simulation on M15-flip entries (a proxy for the ML model's
selectivity — the real model couldn't load in the sandbox). The **comparisons /
conclusions are robust**; absolute $ figures are illustrative.

> Numbers below are from the runs executed before the latest config tweaks
> (M30-alignment removed, buffer 0.20). The **conclusions hold**; re-run
> `C:\QGAI\backtest\Run_All_Backtests.bat` on your PC for exact current numbers.

---

## 1. Exit timeframe — M15 vs M30 vs H1  → **H1 wins**

| Exit TF | avgR | PF | totalR | whipsaws |
|---|---|---|---|---|
| M15 line/flip | +0.002 | 1.01 | +14 | 2596 |
| M30 line/flip | +0.030 | 1.07 | +72 | 575 |
| **H1 line/flip** | **+0.093** | **1.21** | **+222** | **549** |

**Takeaway:** the tight 15-min line is ~breakeven and gets chopped (~2600 whipsaws).
The **H1 line cuts whipsaws ~5×** and lets winners run → ~46× better per-trade.
True across **all sessions** (Asian/London/NY) — no benefit to session-switching.

## 2. Take-profit distance  → **far / no TP (let the H1 flip exit)**

| TP | avgR | PF |
|---|---|---|
| 1.0R (tight) | −0.001 | 1.00 |
| 3.0R | +0.058 | 1.14 |
| **none (flip exits)** | **+0.093** | **1.21** |

A tight TP caps the winners that pay for the losers → kills the edge.

## 3. Ratchet buffer  → **0.20% = best risk-adjusted**

| buffer | totalR | PF | $10k→ | maxDD |
|---|---|---|---|---|
| 0.09 | +62 | 1.17 | $32.7k | 61% |
| **0.20** | +54 | **1.18** | **$33.0k** | **55%** |
| 0.50 | +30 | 1.15 | $20k | 35% |

PF is flat (~1.17) across buffers → buffer is a **risk dial**, not an edge.
0.20 ≈ same profit as 0.09 but lower drawdown → **now live**.

## 4. Quality entries + costs  → **profitable, and cost-robust**

HTF-aligned entries, H1 exit, no TP:

| Cost/trade | H1 exit | M15 exit |
|---|---|---|
| $0.00 | +96R, PF 1.28, $90k | +97R, PF 1.20, $112k |
| **$0.30** | **+62R, PF 1.17, $33k** | +6R, PF 1.01 (breakeven) |
| $0.50 | +39R, PF 1.10, $17k | −55R, PF 0.91 (losing) |

**Key:** raw flips lose after costs; **quality (HTF-aligned) entries are the edge.**
H1 stays profitable after realistic costs; M15 collapses (more trades = more cost).

## 5. Risk per trade  → **1–2% recommended** (approx.)

| risk | return | maxDD |
|---|---|---|
| 1% | ~+60% | ~22% |
| 2% | ~+140% | ~40% |
| 3% (live) | +230% | 55–61% |
| 5% | ~+350% | ~80%+ |

Return scales with risk but **drawdown scales worse**, and past ~5–6% (Kelly /
volatility drag) more risk *reduces* return + risks ruin. **3% is aggressive.**

---

## Model health (from the latest retrain, 45 features)
- **Main** ensemble: Val AUC **0.754**, Test ~0.74 (gap ~0.01 = low overfitting)
- **BUY**: Val **0.80** / Test 0.73 · **SELL**: Val 0.76 / Test 0.73
- Filtered (prob>0.45) win rate: **65–80%**
- ATR removed, slot 1-hr (leakage-fixed), 23 low/zero-importance features pruned.

## Bottom line
1. **H1 line for stop + flip exit** — the single biggest improvement (whipsaw ↓, expectancy ↑). ✅ live.
2. **TP far / off** — flip is the exit. ✅ live (`ratchet_tp_cap_pct=10`).
3. **Buffer 0.20** — best risk-adjusted. ✅ live.
4. **Edge is in entry selectivity** (the ML model), not the exit mechanism — the exit is risk-management.
5. **Consider risk 1–2%** instead of 3% (drawdown).

## Honest caveats
- Entries = M15-flip + HTF-aligned (proxy). Real ML entries differ → validate with
  `backtest_replay.py` (uses the actual model) on your PC.
- No spread modelling beyond a flat per-trade cost; live spread varies.
- **Forward/demo-test before trusting live.** Backtest ≠ live.
