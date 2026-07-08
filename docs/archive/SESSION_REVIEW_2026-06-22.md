# QGAI — Session Review (for Imtiyaz)

**Worked with:** Anisa (via Cowork) · **Date:** 2026-06-22
**Scope:** Exit logic, risk rules, ML feature cleanup, OOS validation, environment setup.
**⚠️ Live-trading code. Test on DEMO before going live. All config changes are reversible.**

---

## 1. Exit logic changes (config.py)

| Change | From → To | Why | Status |
|---|---|---|---|
| HTF exit | OFF → **ON** (`ratchet_htf_sl=True`, `ratchet_htf_flip=True`, `ratchet_htf_tf="H1"`) | 15-min line cut SL near entry → whipsaw. H1 line = ~5× fewer whipsaws, avgR +0.093 vs +0.002 | ✅ live |
| Ratchet buffer | 0.09% → **0.20%** | Same profit, max DD 61%→55% (better risk-adjusted) | ✅ live |
| TP cap | tight → **far** (`ratchet_tp_cap_pct=10`) | Tight TP kills edge (PF 1.00). Far/none = PF 1.21. Flip is the exit | ✅ live |
| Min SL | fixed $8 → `ratchet_sl_min_pct=0.18%` | %-of-price (golden rule) | ✅ live |
| Breakeven buf | fixed $2 → `breakeven_buf_pct=0.05%` | %-of-price | ✅ live |

**SL on H1 line WITH buffer:** `vSL = H1_line ∓ (price × 0.20%)`. Entry stays 15-min; SL/risk/flip on H1; lot auto-shrinks so 1R = 3% equity regardless of stop width.

---

## 2. Risk rules

- **Per-trade:** 3% of equity (vSL = 1R, `risk_pct=3.0`), dynamic compounding (`use_fixed_lot=False`).
- **Daily:** RATCHET rule (NEW) — loss-floor −9% + profit-lock (floor trails 9% below day-peak; peak +12% → +3% locked). Implemented in `bridge_session.py` + `backtest_replay.py`.
- **Trade-2 equity SL: REMOVED completely** (was halting the whole day at −3%, conflicting with the 9% daily). Removed from 4 files (`bridge_core`, `bridge_session`, `bridge_dashboard`, `bridge_constants`) — grep clean, no leftovers.

Risk kept at **3%** per Anisa (OOS ~+5,766%/yr, DD ~30% with ratchet). 1–2% is safer (DD 15%/22%) if ever desired.

---

## 3. ML / feature cleanup (features.py)

- **ATR removed** — 2-SMMA already captures volatility (redundant + lagging). ADX's internal TR untouched.
- **slot_win_rate** → 1-hour base (was 15-min, ~29 trades/slot noisy) + **look-ahead leakage FIXED** (slot table now built on train-split only, not full data).
- **23 features pruned** (67 → 45): 13 zero-importance + 10 manual (data-backed, via `feature_importance.csv` each retrain). `hmm_state`, `trade_direction`, M30 ADX/DI kept (cross-model useful).

**Retrain done.** Models healthy: Main AUC 0.75, BUY 0.80/0.73, SELL 0.76/0.73, low overfit.

---

## 4. Validation — Walk-Forward OOS (the important proof)

True walk-forward (weekly retrain on past only, trade next week unseen), 41 weeks, 1036 trades:

| Metric | OOS | (in-sample) |
|---|---|---|
| Profit Factor | **1.55** | 1.74 |
| avg R/trade | +0.139 | +0.221 |
| Green weeks | **33/40 (82%)** | — |
| Green months | **9/10** | — |

**Verdict: edge is real, survives OOS** (not overfit illusion). The +279,000% headline figure is compounding fantasy — judge by PF 1.55.

---

## 5. TRAIL exit finding (in progress)

Exit-reason breakdown (OOS): FLIP carries all profit (+148R); **TRAIL is net-negative (−7R, win 32%)**. By regime:
- Ranging: TRAIL −0.10 ❌ → trail OFF
- Trending: TRAIL −0.05 ❌ → trail OFF
- Volatile: TRAIL +0.05 ✅ → trail ON

**Built (backtest only, `--trail-mode` flag): line / off / after1r / be / htf / regime.** Each has its own `Run_WFO_*.bat` → separate results folder, resumable, comparable.

**PENDING:** run the trail-variant WFOs (REGIME ⭐ recommended), pick the best, then implement in live bridge.

---

## 6. Environment

- Python 3.12.10 + MetaTrader5, pandas, xgboost, lightgbm, catboost, hmmlearn, river, etc. (Python 3.14 dropped — hmmlearn needed C++ build tools).
- `.bat` launchers use full Python path (PATH not set) — Start/ + backtest/.

---

## 7. Open / recommended

1. **Run trail-variant WFOs** → choose best trail mode → implement live.
2. **Configure `MT5_PRIMARIES`** (3 accounts) in `config_mt5.py` → activate failover (code wired, list empty).
3. **Bug C** (SYMBOL vs failover-primary mismatch) — fix once failover configured.
4. **Restart bridge on DEMO** to apply all changes; forward-test 3–7 days before live.

---

## Files changed this session
`config.py` · `features.py` · `xgb_model.py` · `train.py` · `bridge_core.py` · `bridge_session.py` · `bridge_risk.py` · `bridge_ratchet.py` · `bridge_dashboard.py` · `bridge_constants.py` · `backtest_replay.py` · `run_wfo.py` · plus new `backtest/*.py` + `Run_WFO_*.bat`.

*All edits verified via ground-truth file reader (bash mount serves stale copies intermittently — known artifact, not a code bug).*
