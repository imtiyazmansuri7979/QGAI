# QGAI Session Notes
**Date:** 19-Jun-2026  
**Updated by:** Imtiyaz (via Claude AI)  
**For:** Anisa — review what was changed and what's pending

---

## ✅ COMPLETED THIS SESSION

### 1. Dashboard (dashboard.html) — Major Compact Redesign
All changes are in `C:\QGAI\engine\dashboard.html`

- **3-column layout** (Signal | Market Structure | Market Intelligence) made compact with `align-items:stretch`
- **Global padding reduced:** `.tcard-hdr` → `4px 10px`, font `0.75rem` | `.trow` → `3px 10px` | `.r-cell` → `3px 5px`
- **Open Trades card** — collapses to chip `● AI monitoring every bar...` when no trades open; expands to full table when trades exist
- **Signal Log + Risk & Session** now side by side (50/50 grid) instead of stacked — saves vertical space
- **Market Intelligence** rows changed to 2-column grid (14 rows → 7 rows tall)
- **Session + Today Stats mini-card** added in col 1 (below VSL tracker) with:
  - Active session pill (ASIAN / LONDON / NY highlighted)
  - Countdown to session end
  - W/L today, P&L today, streak, next bar timer

### 2. Engine Bug Fixes (previous session, pushed to GitHub)
- **`bridge_core.py`** — `recover_open_trades()` now passes `ratchet=RATCHET_EXIT` correctly
- **`bridge_multi.py`** — Added `close_secondary_accounts()` function; called in 4 places after `_close_position()`
- **RATCHET_FLIP_EXIT** — confirmed working; VirtualTrade.ratchet must be True for flip exit

---

## ⚠️ PENDING / NEEDS ATTENTION

### 1. Dashboard Layout Choice — NOT DONE YET
Imtiyaz needs to pick one of 3 layout options for:
**Market Structure | Market Intelligence | Risk & Session**

- **Option 1:** MS + MI stacked left column, Risk & Session full right column
- **Option 2:** All 3 as equal columns in a full-width 3-col strip (most compact)
- **Option 3:** MS collapses to slim header bar, MI + Risk side by side below

**Waiting for Imtiyaz to choose.**

### 2. backtest_replay.py — UnicodeEncodeError (cp1252 bug)
File: `C:\QGAI\engine\backtest_replay.py`

The `⚡` emoji on line 208 (`print("⚡ QGAI AI REPLAY BACKTEST")`) causes crash on Windows when output is redirected to a file (cp1252 codec).

**Result:** `results_tp_2.00.txt` and `results_tp_4.00.txt` contain only the traceback — no actual results.

**Fix needed:** Add UTF-8 stdout wrapper at top of `backtest_replay.py` (like Anisa already did in `scheduler.py`):
```python
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
```
Then re-run: `python backtest_replay.py --tp 2.00` and `--tp 4.00`

### 3. TP_SWEEP_SUMMARY.txt — Empty
File: `C:\QGAI\engine\TP_SWEEP_SUMMARY.txt`  
The sweep script wrote section headers but no data inside them. Summary needs to be compiled manually or the sweep re-run after fixing the cp1252 bug above.

---

## 📊 TP SWEEP RESULTS (what we have so far)

| TP% | Trades | WR | PF | Avg R | Net Return | Max DD |
|-----|--------|----|----|-------|-----------|--------|
| 0.60 | 1578 | 44.7% | 1.29 | +0.159 | +101,754% | 24.9% |
| 1.00 | 1303 | 44.7% | 1.51 | +0.221 | +279,162% | 27.8% |
| (last report) | 1270 | 44.7% | 1.45 | +0.221 | +227,577% | 27.0% |

**Best so far: TP=1.00%** — highest PF (1.51) and return (+279k%) with acceptable DD.

Exit breakdown at TP=1.00: TRAIL 558 | FLIP 415 | TPCAP 165 | SL 140

---

## 🔴 LIVE TRADING STATUS (as of 18-Jun-2026 22:44)

From `logs/bridge.log`:
- Balance: $84,650.25 | Equity: $112,864.47
- Running config: XAUUSD M15 | 3% risk | max 1 open
- RATCHET ON | TP cap **0.5%** | FLIP True | SMART EXIT True
- PARTIAL: 50% @ 1.5R | TRAIL after 1.0R
- DAILY SL: 9% | DAILY TP: 8% (off)
- Last signal: SKIP prob=15.10% (no trade taken)

**Note:** Live TP cap is 0.5% — different from backtest sweep which tested 0.60% to 4.00%. Backtest shows 1.00% is better — discuss with Imtiyaz whether to change live TP cap.

---

## 📁 Anisa's Files (from git commits)

Added by Anisa (anisaimtiyazmansuri@gmail.com):
- `smart_exit_backtest.py` — backtests 4 exit strategies: time-based, momentum, structure, full hybrid
- `scheduler.py` — fixed UTF-8 encoding issue (already working ✅)
- `backtest_exits_tp.py` — exit analysis per TP level
- `exit_backtest_1year.py` — 1-year exit backtest runner

**To run smart exit backtest:**
```
cd C:\QGAI\engine
python smart_exit_backtest.py
```

---

## 🔒 SECURITY REMINDER
`config_mt5.py` is in `.gitignore` — NEVER commit to GitHub. Contains live MT5 credentials.

---

## NEXT STEPS (priority order)
1. Fix `backtest_replay.py` cp1252 bug → re-run TP 2.00 and 4.00 sweeps
2. Imtiyaz to pick dashboard layout Option 1/2/3
3. Review `smart_exit_backtest.py` results
4. Consider changing live TP cap from 0.5% → 1.0% based on sweep results
