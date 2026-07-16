"""
test_leakage_auc.py — AUC impact test for removing leaky features
─────────────────────────────────────────────────────────────────
Builds full feature matrix once, then trains 3 XGBoost variants:
  A) ALL features (current baseline)
  B) Without corr_imp_ratio only
  C) Without corr_imp_ratio + in_range_phase

Prints AUC comparison table. No models saved — test only.
"""
import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.metrics import roc_auc_score

from config import CFG
from features import (load_trades, load_ohlc, load_adx, load_news,
                      build_slot_table, build_feature_matrix, FEATURE_COLS,
                      build_h4_range_table, build_ob_table)
from xgb_model import WinProbabilityModel

t0 = time.time()
print("\n" + "="*60)
print("  LEAKAGE AUC TEST — feature removal impact")
print("="*60)

cfg = CFG.paths
trades  = load_trades(cfg.trades_file)
ohlc_df = load_ohlc(cfg.ohlc_file)
adx_df  = load_adx(cfg.adx_file)
news_df = load_news(cfg.news_file)

from datetime import datetime as _dt
_today = _dt.now()
ohlc_df = ohlc_df[ohlc_df["datetime"] <= _today].copy()
adx_df  = adx_df[adx_df["datetime"]  <= _today].copy()

print(f"  Trades: {len(trades):,} | OHLC: {len(ohlc_df):,}")

# Build tables
h4_df    = build_h4_range_table(ohlc_df)
h1_ob    = build_ob_table(ohlc_df, "1h")
h4_ob_df = build_ob_table(ohlc_df, "4h")

# Slot table (train-split only, same as train.py)
_slot_tr_end = int(len(trades) * 0.70)
slot_tbl = build_slot_table(trades.iloc[:_slot_tr_end])

# Build full feature matrix
print("\n► Building feature matrix...")
print("  ⚠️ NOTE (2026-07-16): corr_imp_ratio's computation was deleted from features.py —")
print("  it is now a hardcoded 1.0 constant. Variants B/C below (dropping it) will show")
print("  ZERO difference vs A/D for that reason alone, not as a fresh confirmation of low")
print("  impact. The original 2026-07-09 finding (-0.014 AUC) is already recorded in")
print("  FIXES_CHANGELOG4.md and is not reproducible by re-running this script.")
X, y, feat_names = build_feature_matrix(
    trades, ohlc_df, adx_df, news_df, slot_tbl,
    h4_df=h4_df, h1_ob=h1_ob, h4_ob_df=h4_ob_df
)
print(f"  Matrix: {X.shape[0]:,} × {X.shape[1]} features")

# Time-based split (same as train.py)
n      = len(X)
tr_end = int(n * 0.70)
va_end = int(n * 0.85)
X_tr, y_tr = X[:tr_end],       y[:tr_end]
X_va, y_va = X[tr_end:va_end], y[tr_end:va_end]
X_te, y_te = X[va_end:],       y[va_end:]
print(f"  Train: {len(X_tr):,} | Val: {len(X_va):,} | Test: {len(X_te):,}")

# Define variants
DROP_SETS = {
    "A) ALL features (baseline)":         [],
    "B) Without corr_imp_ratio":          ["corr_imp_ratio"],
    "C) Without corr_imp_ratio + in_range_phase": ["corr_imp_ratio", "in_range_phase"],
    "D) Without in_range_phase only":     ["in_range_phase"],
}

results = []

for label, drop_list in DROP_SETS.items():
    print(f"\n{'─'*50}")
    print(f"  {label}")

    # Get column indices to KEEP
    keep_idx = [i for i, f in enumerate(feat_names) if f not in drop_list]
    keep_names = [feat_names[i] for i in keep_idx]
    dropped = [f for f in drop_list if f in feat_names]

    print(f"  Features: {len(keep_names)} (dropped: {dropped or 'none'})")

    Xtr = X_tr[:, keep_idx]
    Xva = X_va[:, keep_idx]
    Xte = X_te[:, keep_idx]

    # Train
    model = WinProbabilityModel()
    model.fit(Xtr, y_tr, Xva, y_va, keep_names)

    # AUC on val + test
    p_va = model.predict_proba_calibrated(Xva)
    p_te = model.predict_proba_calibrated(Xte)
    auc_va = roc_auc_score(y_va, p_va)
    auc_te = roc_auc_score(y_te, p_te)

    print(f"  Val AUC:  {auc_va:.4f}")
    print(f"  Test AUC: {auc_te:.4f}")

    results.append({
        "variant": label,
        "features": len(keep_names),
        "dropped": ", ".join(dropped) or "none",
        "val_auc": round(auc_va, 4),
        "test_auc": round(auc_te, 4),
    })

# Summary table
elapsed = time.time() - t0
print(f"\n{'='*60}")
print(f"  AUC COMPARISON TABLE")
print(f"{'='*60}")
print(f"  {'Variant':<45} {'Feat':>4}  {'Val AUC':>8}  {'Test AUC':>8}")
print(f"  {'─'*45} {'─'*4}  {'─'*8}  {'─'*8}")
baseline_va = results[0]["val_auc"]
baseline_te = results[0]["test_auc"]
for r in results:
    d_va = r["val_auc"] - baseline_va
    d_te = r["test_auc"] - baseline_te
    delta = "" if r == results[0] else f"  ({d_va:+.4f} / {d_te:+.4f})"
    print(f"  {r['variant']:<45} {r['features']:>4}  {r['val_auc']:.4f}    {r['test_auc']:.4f}{delta}")

print(f"\n  ⏱ Total time: {elapsed:.0f}s")
print(f"  Note: No models saved — test only.")
print(f"{'='*60}\n")
