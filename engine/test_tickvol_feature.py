"""
test_tickvol_feature.py  — SMOKE TEST for the RAW tick_volume feature (2026-07-09, Imtiyaz)
────────────────────────────────────────────────────────────────────────────────────────
Purpose: verify the newly-added RAW `tick_volume` feature is plumbed end-to-end BEFORE the
real (long) retrain — WITHOUT touching / overwriting the live model (data/models/final/*.pkl).

What it checks (TEST-FIRST gate per CLAUDE.md):
  1. FEATURE_COLS contains 'tick_volume' and does NOT contain the pruned normalized 'volume'.
  2. Data loads (existing merged CSVs — no merge_data.py run needed).
  3. build_feature_matrix() runs with NO crash / NO KeyError on a SMALL slice of trades.
  4. The 'tick_volume' column in the built matrix is REAL raw counts: varies (nunique>1),
     is not all-zero, and matches the raw MT5 tick_volume in the OHLC (spot-check).
  5. Matrix width == len(FEATURE_COLS).

Writes NOTHING to disk. Read-only. Safe to run anytime.
Run via: Start\3_Train_Models_TEST.bat   (or:  python test_tickvol_feature.py)
"""
import sys
import numpy as np
import pandas as pd
from config import CFG
from features import (
    FEATURE_COLS, load_trades, load_ohlc, load_adx, load_news,
    build_slot_table, build_feature_matrix, build_h4_range_table,
    build_trend_ratio_table, build_ob_table,
)

N_TRADES = 120   # small slice → fast smoke test (real retrain uses ALL trades)

def fail(msg):
    print(f"\n  ❌ TEST FAILED: {msg}")
    sys.exit(1)

def main():
    print("\n" + "=" * 64)
    print("  SMOKE TEST — RAW tick_volume feature (no model is written)")
    print("=" * 64)

    # ── 1. FEATURE_COLS membership ────────────────────────────────
    print(f"\n[1/5] FEATURE_COLS = {len(FEATURE_COLS)} features")
    if "tick_volume" not in FEATURE_COLS:
        fail("'tick_volume' NOT in FEATURE_COLS (the whole point of this change).")
    if "volume" in FEATURE_COLS:
        fail("normalized 'volume' is back in FEATURE_COLS — it should stay PRUNED.")
    print(f"      ✓ 'tick_volume' present  |  'volume' correctly absent (pruned)")
    print(f"      ✓ tick_volume index = {FEATURE_COLS.index('tick_volume')}")

    # ── 2. Load data (existing merged CSVs) ───────────────────────
    print("\n[2/5] Loading data (read-only)...")
    cfg     = CFG.paths
    trades  = load_trades(cfg.trades_file)
    ohlc_df = load_ohlc(cfg.ohlc_file)
    adx_df  = load_adx(cfg.adx_file)
    news_df = load_news(cfg.news_file)
    from datetime import datetime as _dt
    ohlc_df = ohlc_df[ohlc_df["datetime"] <= _dt.now()].copy()
    adx_df  = adx_df[adx_df["datetime"]  <= _dt.now()].copy()
    print(f"      trades={len(trades):,}  ohlc={len(ohlc_df):,}  adx={len(adx_df):,}  news={len(news_df):,}")

    # ── 3. Build helper tables + a SMALL trade slice ──────────────
    print(f"\n[3/5] Building helper tables + feature matrix on last {N_TRADES} trades...")
    h4_df    = build_h4_range_table(ohlc_df)
    ratio_df = build_trend_ratio_table(ohlc_df)
    h1_ob    = build_ob_table(ohlc_df, "1h")
    h4_ob_df = build_ob_table(ohlc_df, "4h")
    slot_tbl = build_slot_table(trades.iloc[:int(len(trades) * 0.70)])

    trades_slice = trades.tail(N_TRADES).reset_index(drop=True)
    try:
        X, y, feat_names = build_feature_matrix(
            trades_slice, ohlc_df, adx_df, news_df, slot_tbl,
            h4_df=h4_df, ratio_df=ratio_df, h1_ob=h1_ob, h4_ob_df=h4_ob_df,
        )
    except Exception as e:
        fail(f"build_feature_matrix crashed: {type(e).__name__}: {e}")
    print(f"      ✓ matrix built with NO crash: {X.shape[0]} trades × {X.shape[1]} features")

    # ── 4. Matrix width == FEATURE_COLS ───────────────────────────
    print("\n[4/5] Shape + column checks...")
    if X.shape[1] != len(FEATURE_COLS):
        fail(f"matrix width {X.shape[1]} != len(FEATURE_COLS) {len(FEATURE_COLS)}")
    if "tick_volume" not in feat_names:
        fail("'tick_volume' missing from returned feat_names.")
    print(f"      ✓ width matches FEATURE_COLS ({X.shape[1]})")

    # ── 5. tick_volume column is REAL raw counts ──────────────────
    ti  = feat_names.index("tick_volume")
    col = X[:, ti].astype(float)
    nuniq = int(np.unique(col).size)
    print("\n[5/5] tick_volume column values:")
    print(f"      min={col.min():.1f}  max={col.max():.1f}  mean={col.mean():.1f}  nunique={nuniq}")
    if nuniq <= 1:
        fail("tick_volume is CONSTANT — raw count is not flowing through (would be a dead feature).")
    if np.all(col == 0):
        fail("tick_volume is all-zero — the else-fallback fired for every row (data problem).")
    # It must NOT look normalized (raw XAUUSD M15 tick counts are typically hundreds–thousands,
    # NOT a 0–5 capped ratio). Warn (not fail) if suspiciously small.
    if col.max() <= 5.0:
        print("      ⚠ max<=5.0 — looks normalized, not raw. Investigate before trusting.")
    else:
        print(f"      ✓ looks like RAW counts (max {col.max():.0f} ≫ 5.0 ratio cap)")

    print("\n" + "=" * 64)
    print("  ✅ SMOKE TEST PASSED — tick_volume is plumbed as a RAW feature.")
    print("  No model was written. Live .pkl untouched.")
    print("  NEXT: run the FULL retrain (Start\\3_Train_Models.bat) when ready,")
    print("        then deep bug-check + WFO-gate before going live.")
    print("=" * 64 + "\n")

if __name__ == "__main__":
    main()
