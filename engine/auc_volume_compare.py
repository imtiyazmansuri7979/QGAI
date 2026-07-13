"""
auc_volume_compare.py
─────────────────────
Quick AUC comparison: current features (no volume) vs with volume/tick_volume added.
Same data, same splits, same model — only feature set differs.
"""

import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import roc_auc_score

from config import CFG
from features import (load_trades, load_ohlc, load_adx, load_news,
                      build_slot_table, build_feature_matrix, FEATURE_COLS)
from hmm_model import MarketStateHMM
from xgb_model import WinProbabilityModel

# ── Load data (same as train.py) ──
print("\n" + "="*60)
print("  AUC COMPARISON: volume feature effect")
print("="*60 + "\n")

cfg = CFG.paths
trades  = load_trades(cfg.trades_file)
ohlc_df = load_ohlc(cfg.ohlc_file)
adx_df  = load_adx(cfg.adx_file)
news_df = load_news(cfg.news_file)

from datetime import datetime as _dt
_today = _dt.now()
ohlc_df = ohlc_df[ohlc_df["datetime"] <= _today].copy()
adx_df  = adx_df[adx_df["datetime"]  <= _today].copy()

print(f"  Trades: {len(trades):,}")
print(f"  OHLC  : {len(ohlc_df):,}")

# ── Build auxiliary tables ──
from features import build_h4_range_table, build_trend_ratio_table, build_ob_table
h4_df    = build_h4_range_table(ohlc_df)
ratio_df = build_trend_ratio_table(ohlc_df)
h1_ob    = build_ob_table(ohlc_df, "1h")
h4_ob_df = build_ob_table(ohlc_df, "4h")

# ── Slot table (train-split only) ──
_slot_tr_end = int(len(trades) * 0.70)
slot_tbl = build_slot_table(trades.iloc[:_slot_tr_end])

# ── Feature matrix (full — includes volume+tick_volume columns) ──
X_all, y, feat_names_all = build_feature_matrix(
    trades, ohlc_df, adx_df, news_df, slot_tbl,
    h4_df=h4_df, ratio_df=ratio_df, h1_ob=h1_ob, h4_ob_df=h4_ob_df
)

print(f"  Feature matrix: {X_all.shape[0]:,} x {X_all.shape[1]}")
print(f"  Features: {feat_names_all}")

# ── Split ──
n = len(X_all)
tr_end = int(n * 0.70)
va_end = int(n * 0.85)

y_tr = y[:tr_end]
y_va = y[tr_end:va_end]
y_te = y[va_end:]

# ── HMM (same for both) ──
hmm_model = MarketStateHMM()
_hmm_cutoff  = trades.iloc[:tr_end]["datetime"].max()
adx_df_train = adx_df[adx_df["datetime"] <= _hmm_cutoff]
hmm_model.fit(adx_df_train)

def get_hmm_from_adx(trades_subset):
    states = []
    for _, trade in trades_subset.iterrows():
        t = trade["datetime"]
        a = adx_df[adx_df["datetime"] <= t]
        if len(a) > 0:
            r = a.iloc[-1]
            adx_row = {k: float(r[k]) if k in r.index else 0.0 for k in hmm_model.features}
        else:
            adx_row = {k: 0.0 for k in hmm_model.features}
        states.append(hmm_model.predict(adx_row))
    return np.array(states)

n_all = len(trades)
tr_e = int(n_all * 0.70); va_e = int(n_all * 0.85)
hmm_tr = get_hmm_from_adx(trades.iloc[:tr_e])
hmm_va = get_hmm_from_adx(trades.iloc[tr_e:va_e])
hmm_te = get_hmm_from_adx(trades.iloc[va_e:])

# ── Scenario definitions ──
# Current FEATURE_COLS (already pruned — no volume/tick_volume)
current_feats = list(FEATURE_COLS)

# Check if volume/tick_volume are in the full feature matrix
has_volume     = "volume" in feat_names_all
has_tick_vol   = "tick_volume" in feat_names_all

print(f"\n  volume in matrix: {has_volume}")
print(f"  tick_volume in matrix: {has_tick_vol}")

# Since build_feature_matrix uses the pruned FEATURE_COLS, volume may not be
# in the matrix. We need to rebuild with volume included.
# Temporarily patch FEATURE_COLS to include volume features
import features as _feat_mod

# Save original prune set
_orig_prune = _feat_mod._ZERO_IMP.copy()

scenarios = {}

# ── Scenario A: Current (no volume) ──
print("\n" + "─"*60)
print("  SCENARIO A: Current (no volume/tick_volume)")
print("─"*60)

# Already have X_all with current features
X_tr_a = X_all[:tr_end]
X_va_a = X_all[tr_end:va_end]
X_te_a = X_all[va_end:]

X_tr_af = np.column_stack([X_tr_a, hmm_tr])
X_va_af = np.column_stack([X_va_a, hmm_va])
X_te_af = np.column_stack([X_te_a, hmm_te])
feat_a = feat_names_all + ["hmm_state"]

model_a = WinProbabilityModel()
model_a.fit(X_tr_af, y_tr, X_va_af, y_va, feat_a)
proba_va_a = model_a.predict_proba_calibrated(X_va_af)
proba_te_a = model_a.predict_proba_calibrated(X_te_af)
auc_va_a = roc_auc_score(y_va, proba_va_a)
auc_te_a = roc_auc_score(y_te, proba_te_a)
print(f"  VAL AUC : {auc_va_a:.4f}")
print(f"  TEST AUC: {auc_te_a:.4f}")
print(f"  Features: {len(feat_names_all)}")
scenarios["A_no_volume"] = {"val": auc_va_a, "test": auc_te_a, "n_feat": len(feat_names_all)}


# ── Rebuild feature matrix WITH volume features ──
# Remove volume/tick_volume from the prune set
_feat_mod._ZERO_IMP = _orig_prune - {"volume", "tick_volume"}
# Rebuild FEATURE_COLS-like list
_base_cols = [f for f in _feat_mod.FEATURE_COLS]  # current (no vol)

# We need to rebuild the full feature matrix including volume
# The simplest way: rebuild with the volume features un-pruned
# Reset the module-level lists
_all_possible = list(_feat_mod.FEATURE_COLS) + ["volume", "tick_volume"]
# But build_feature_matrix uses FEATURE_COLS internally...
# So we temporarily add them back

_saved_FC = _feat_mod.FEATURE_COLS[:]
_feat_mod.FEATURE_COLS = _all_possible

print("\n  Rebuilding feature matrix with volume + tick_volume...")
X_vol, y_vol, feat_names_vol = build_feature_matrix(
    trades, ohlc_df, adx_df, news_df, slot_tbl,
    h4_df=h4_df, ratio_df=ratio_df, h1_ob=h1_ob, h4_ob_df=h4_ob_df
)
print(f"  Feature matrix: {X_vol.shape[0]:,} x {X_vol.shape[1]}")

# Restore
_feat_mod.FEATURE_COLS = _saved_FC

# ── Scenario B: + volume (normalized) only ──
print("\n" + "─"*60)
print("  SCENARIO B: Current + volume (normalized)")
print("─"*60)

vol_idx = feat_names_vol.index("volume") if "volume" in feat_names_vol else None
if vol_idx is not None:
    # Current features + volume
    base_idx = [feat_names_vol.index(f) for f in feat_names_all if f in feat_names_vol]
    b_idx = base_idx + [vol_idx]
    X_b = X_vol[:, b_idx]
    feat_b = [feat_names_vol[i] for i in b_idx]

    X_tr_b = np.column_stack([X_b[:tr_end], hmm_tr])
    X_va_b = np.column_stack([X_b[tr_end:va_end], hmm_va])
    X_te_b = np.column_stack([X_b[va_end:], hmm_te])
    feat_bf = feat_b + ["hmm_state"]

    model_b = WinProbabilityModel()
    model_b.fit(X_tr_b, y_tr, X_va_b, y_va, feat_bf)
    proba_va_b = model_b.predict_proba_calibrated(X_va_b)
    proba_te_b = model_b.predict_proba_calibrated(X_te_b)
    auc_va_b = roc_auc_score(y_va, proba_va_b)
    auc_te_b = roc_auc_score(y_te, proba_te_b)
    print(f"  VAL AUC : {auc_va_b:.4f}")
    print(f"  TEST AUC: {auc_te_b:.4f}")
    print(f"  Features: {len(feat_b)}")
    scenarios["B_plus_volume"] = {"val": auc_va_b, "test": auc_te_b, "n_feat": len(feat_b)}
else:
    print("  ⚠️ volume not found in rebuilt matrix")


# ── Scenario C: + tick_volume (raw) only ──
print("\n" + "─"*60)
print("  SCENARIO C: Current + tick_volume (raw)")
print("─"*60)

tv_idx = feat_names_vol.index("tick_volume") if "tick_volume" in feat_names_vol else None
if tv_idx is not None:
    base_idx = [feat_names_vol.index(f) for f in feat_names_all if f in feat_names_vol]
    c_idx = base_idx + [tv_idx]
    X_c = X_vol[:, c_idx]
    feat_c = [feat_names_vol[i] for i in c_idx]

    X_tr_c = np.column_stack([X_c[:tr_end], hmm_tr])
    X_va_c = np.column_stack([X_c[tr_end:va_end], hmm_va])
    X_te_c = np.column_stack([X_c[va_end:], hmm_te])
    feat_cf = feat_c + ["hmm_state"]

    model_c = WinProbabilityModel()
    model_c.fit(X_tr_c, y_tr, X_va_c, y_va, feat_cf)
    proba_va_c = model_c.predict_proba_calibrated(X_va_c)
    proba_te_c = model_c.predict_proba_calibrated(X_te_c)
    auc_va_c = roc_auc_score(y_va, proba_va_c)
    auc_te_c = roc_auc_score(y_te, proba_te_c)
    print(f"  VAL AUC : {auc_va_c:.4f}")
    print(f"  TEST AUC: {auc_te_c:.4f}")
    print(f"  Features: {len(feat_c)}")
    scenarios["C_plus_tick_volume"] = {"val": auc_va_c, "test": auc_te_c, "n_feat": len(feat_c)}
else:
    print("  ⚠️ tick_volume not found in rebuilt matrix")


# ── Scenario D: + both volume + tick_volume ──
print("\n" + "─"*60)
print("  SCENARIO D: Current + volume + tick_volume (both)")
print("─"*60)

if vol_idx is not None and tv_idx is not None:
    base_idx = [feat_names_vol.index(f) for f in feat_names_all if f in feat_names_vol]
    d_idx = base_idx + [vol_idx, tv_idx]
    X_d = X_vol[:, d_idx]
    feat_d = [feat_names_vol[i] for i in d_idx]

    X_tr_d = np.column_stack([X_d[:tr_end], hmm_tr])
    X_va_d = np.column_stack([X_d[tr_end:va_end], hmm_va])
    X_te_d = np.column_stack([X_d[va_end:], hmm_te])
    feat_df = feat_d + ["hmm_state"]

    model_d = WinProbabilityModel()
    model_d.fit(X_tr_d, y_tr, X_va_d, y_va, feat_df)
    proba_va_d = model_d.predict_proba_calibrated(X_va_d)
    proba_te_d = model_d.predict_proba_calibrated(X_te_d)
    auc_va_d = roc_auc_score(y_va, proba_va_d)
    auc_te_d = roc_auc_score(y_te, proba_te_d)
    print(f"  VAL AUC : {auc_va_d:.4f}")
    print(f"  TEST AUC: {auc_te_d:.4f}")
    print(f"  Features: {len(feat_d)}")
    scenarios["D_plus_both"] = {"val": auc_va_d, "test": auc_te_d, "n_feat": len(feat_d)}
else:
    print("  ⚠️ volume features not found")


# ── Summary ──
print("\n" + "="*60)
print("  SUMMARY: Volume Effect on AUC")
print("="*60)
print(f"  {'Scenario':<30} {'Val AUC':>9} {'Test AUC':>10} {'#Feat':>6}")
print("  " + "─"*57)
for name, s in scenarios.items():
    print(f"  {name:<30} {s['val']:>9.4f} {s['test']:>10.4f} {s['n_feat']:>6}")

baseline_te = scenarios.get("A_no_volume", {}).get("test", 0)
print("\n  Delta vs baseline (Test AUC):")
for name, s in scenarios.items():
    if name == "A_no_volume":
        continue
    delta = s["test"] - baseline_te
    sign = "+" if delta >= 0 else ""
    print(f"    {name:<28} {sign}{delta:.4f}")

print("\n  DONE.")
