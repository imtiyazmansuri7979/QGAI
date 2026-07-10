"""
test_ablation_10.py — 10-test ablation study on Clean-34 base model
───────────────────────────────────────────────────────────────────
Base = current 36 features minus in_range_phase and corr_imp_ratio (= 34).
Each test removes specific features from the 34 and measures impact.
No models saved, no rules changed, no thresholds tuned.
"""
import sys, os, time, json, warnings
sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import roc_auc_score

from config import CFG
from features import (load_trades, load_ohlc, load_adx, load_news,
                      build_slot_table, build_feature_matrix, FEATURE_COLS,
                      build_h4_range_table, build_trend_ratio_table, build_ob_table)
from xgb_model import WinProbabilityModel

T0 = time.time()
print("\n" + "="*70)
print("  ABLATION STUDY — 10 tests on Clean-34 base model")
print("  Base = 36 feat minus in_range_phase, corr_imp_ratio")
print("="*70)

# ── Load data ────────────────────────────────────────────────────
cfg = CFG.paths
trades  = load_trades(cfg.trades_file)
ohlc_df = load_ohlc(cfg.ohlc_file)
adx_df  = load_adx(cfg.adx_file)
news_df = load_news(cfg.news_file)

from datetime import datetime as _dt
ohlc_df = ohlc_df[ohlc_df["datetime"] <= _dt.now()].copy()
adx_df  = adx_df[adx_df["datetime"]  <= _dt.now()].copy()

h4_df    = build_h4_range_table(ohlc_df)
ratio_df = build_trend_ratio_table(ohlc_df)
h1_ob    = build_ob_table(ohlc_df, "1h")
h4_ob_df = build_ob_table(ohlc_df, "4h")

_slot_tr_end = int(len(trades) * 0.70)
slot_tbl = build_slot_table(trades.iloc[:_slot_tr_end])

print("\n> Building feature matrix...")
X, y, feat_names = build_feature_matrix(
    trades, ohlc_df, adx_df, news_df, slot_tbl,
    h4_df=h4_df, ratio_df=ratio_df, h1_ob=h1_ob, h4_ob_df=h4_ob_df
)
print(f"  Full matrix: {X.shape[0]:,} x {X.shape[1]} features")

# ── Time split ───────────────────────────────────────────────────
n      = len(X)
tr_end = int(n * 0.70)
va_end = int(n * 0.85)
X_tr, y_tr = X[:tr_end],       y[:tr_end]
X_va, y_va = X[tr_end:va_end], y[tr_end:va_end]
X_te, y_te = X[va_end:],       y[va_end:]
print(f"  Train: {len(X_tr):,} | Val: {len(X_va):,} | Test: {len(X_te):,}")

# ── Clean-34 base: remove in_range_phase + corr_imp_ratio ────────
ALWAYS_DROP = ["in_range_phase", "corr_imp_ratio"]
base_keep = [i for i, f in enumerate(feat_names) if f not in ALWAYS_DROP]
base_names = [feat_names[i] for i in base_keep]
print(f"\n  Clean-34 base: {len(base_names)} features")
print(f"  Dropped from 36: {[f for f in ALWAYS_DROP if f in feat_names]}")

# ── Define 10 ablation tests ────────────────────────────────────
TESTS = [
    ("T0) Clean-34 BASELINE",                    []),
    ("T1) -slot_win_rate",                        ["slot_win_rate"]),
    ("T2) -tick_volume",                          ["tick_volume"]),
    ("T3) -hmm_state",                            ["hmm_state"]),
    ("T4) -h4_ob_strength -h1_ob_strength",       ["h4_ob_strength", "h1_ob_strength"]),
    ("T5) -h4_resist_dist -h4_support_dist",      ["h4_resist_dist", "h4_support_dist"]),
    ("T6) -h1_resist_dist -h1_support_dist",      ["h1_resist_dist", "h1_support_dist"]),
    ("T7) -ALL OB/SR (6 feat)",                   ["h4_resist_dist", "h4_support_dist",
                                                    "h4_ob_strength", "h1_resist_dist",
                                                    "h1_support_dist", "h1_ob_strength"]),
    ("T8) -news timing (2 feat)",                 ["mins_to_next_3star", "mins_since_last_3star"]),
    ("T9) -momentum alignment (3 feat)",          ["momentum_aligned_1hr", "momentum_aligned_2hr",
                                                    "momentum_aligned_4hr"]),
    ("T10) -trend-signal (2 feat)",               ["ts_bars_since_flip", "ts_htf_agreement"]),
]

# ── Run all tests ────────────────────────────────────────────────
results = []

for label, drop_list in TESTS:
    t1 = time.time()
    print(f"\n{'━'*70}")
    print(f"  {label}")
    print(f"{'━'*70}")

    keep_idx = [i for i, f in enumerate(feat_names)
                if f not in ALWAYS_DROP and f not in drop_list]
    keep_names = [feat_names[i] for i in keep_idx]
    dropped = [f for f in drop_list if f in base_names]
    not_found = [f for f in drop_list if f not in base_names]
    n_feat = len(keep_names)
    print(f"  Features: {n_feat} (dropped: {dropped or 'none'})")
    if not_found:
        print(f"  ⚠️  NOT in active FEATURE_COLS (already pruned or hybrid-only): {not_found}")

    Xtr = X_tr[:, keep_idx]
    Xva = X_va[:, keep_idx]
    Xte = X_te[:, keep_idx]

    # Train
    model = WinProbabilityModel()
    model.fit(Xtr, y_tr, Xva, y_va, keep_names)

    # AUC
    p_va = model.predict_proba_calibrated(Xva)
    p_te = model.predict_proba_calibrated(Xte)
    auc_va = roc_auc_score(y_va, p_va)
    auc_te = roc_auc_score(y_te, p_te)

    # CV AUC from model's internal walk-forward
    cv_auc = 0.0
    # Extract from xgb_model internals — we already printed it during fit

    # Filtered metrics at threshold 0.45 (regime base)
    THRESHOLD = 0.45
    mask_va = p_va >= THRESHOLD
    mask_te = p_te >= THRESHOLD
    filt_count_va = mask_va.sum()
    filt_count_te = mask_te.sum()
    filt_wr_va = y_va[mask_va].mean() * 100 if filt_count_va > 0 else 0
    filt_wr_te = y_te[mask_te].mean() * 100 if filt_count_te > 0 else 0

    # Feature importance (XGB component)
    imp_data = []
    if hasattr(model, 'xgb_model') and hasattr(model.xgb_model, 'feature_importances_'):
        imp = model.xgb_model.feature_importances_
        order = np.argsort(imp)[::-1]
        for rank, i in enumerate(order[:20], 1):
            if i < len(keep_names):
                imp_data.append((rank, keep_names[i], float(imp[i])))

    elapsed = time.time() - t1

    r = {
        "label": label,
        "n_feat": n_feat,
        "dropped": dropped,
        "val_auc": round(auc_va, 4),
        "test_auc": round(auc_te, 4),
        "filt_count_va": int(filt_count_va),
        "filt_count_te": int(filt_count_te),
        "filt_wr_va": round(filt_wr_va, 1),
        "filt_wr_te": round(filt_wr_te, 1),
        "importance_top20": imp_data,
        "elapsed": round(elapsed, 1),
    }
    results.append(r)

    print(f"\n  Val AUC:  {auc_va:.4f} | Test AUC: {auc_te:.4f}")
    print(f"  Filtered (≥{THRESHOLD}): val {filt_count_va} trades WR {filt_wr_va:.1f}%"
          f" | test {filt_count_te} trades WR {filt_wr_te:.1f}%")
    print(f"  Top-5 importance: ", end="")
    for rank, fname, imp_val in imp_data[:5]:
        print(f"{fname}({imp_val:.3f}) ", end="")
    print(f"\n  ⏱ {elapsed:.0f}s")


# ── COMPARISON TABLE ─────────────────────────────────────────────
total_elapsed = time.time() - T0
base = results[0]

print(f"\n\n{'='*100}")
print(f"  ABLATION COMPARISON TABLE (base = Clean-34)")
print(f"{'='*100}")
print(f"  {'Test':<42} {'Feat':>4}  {'Val':>7}  {'Test':>7}  {'ΔVal':>7}  {'ΔTest':>7}  {'FiltVa':>6} {'WR%':>5}  {'FiltTe':>6} {'WR%':>5}")
print(f"  {'─'*42} {'─'*4}  {'─'*7}  {'─'*7}  {'─'*7}  {'─'*7}  {'─'*6} {'─'*5}  {'─'*6} {'─'*5}")

for r in results:
    d_va = r["val_auc"] - base["val_auc"]
    d_te = r["test_auc"] - base["test_auc"]
    delta_va = f"{d_va:+.4f}" if r != base else "  base"
    delta_te = f"{d_te:+.4f}" if r != base else "  base"
    print(f"  {r['label']:<42} {r['n_feat']:>4}  {r['val_auc']:.4f}  {r['test_auc']:.4f}  "
          f"{delta_va:>7}  {delta_te:>7}  {r['filt_count_va']:>6} {r['filt_wr_va']:>4.1f}%  "
          f"{r['filt_count_te']:>6} {r['filt_wr_te']:>4.1f}%")

# ── RANKING (by test AUC) ───────────────────────────────────────
print(f"\n{'='*70}")
print(f"  RANKING (by Test AUC, best → worst)")
print(f"{'='*70}")
ranked = sorted(results, key=lambda r: r["test_auc"], reverse=True)
for i, r in enumerate(ranked, 1):
    d_te = r["test_auc"] - base["test_auc"]
    verdict = "BASELINE" if r == base else ("KEEP ✓" if d_te < -0.005 else "REMOVABLE ?" if d_te >= 0 else "KEEP ✓")
    print(f"  {i:>2}. {r['label']:<42} AUC {r['test_auc']:.4f} ({d_te:+.4f})  → {verdict}")

# ── FEATURE IMPORTANCE: per-test top 20 ──────────────────────────
print(f"\n{'='*70}")
print(f"  FEATURE IMPORTANCE — Top 20 per test")
print(f"{'='*70}")
for r in results:
    print(f"\n  {r['label']} ({r['n_feat']} feat):")
    for rank, fname, imp_val in r["importance_top20"]:
        bar = "█" * int(imp_val * 200)
        print(f"    {rank:>2}. {fname:<28} {imp_val:.4f} {bar}")

# ── RECOMMENDATIONS ──────────────────────────────────────────────
print(f"\n{'='*70}")
print(f"  RECOMMENDATIONS")
print(f"{'='*70}")
for r in results[1:]:  # skip baseline
    d_te = r["test_auc"] - base["test_auc"]
    d_wr = r["filt_wr_te"] - base["filt_wr_te"]
    if d_te >= 0:
        print(f"  🟢 {r['label']}: REMOVABLE — test AUC {d_te:+.4f}, WR {d_wr:+.1f}%")
    elif d_te > -0.01:
        print(f"  🟡 {r['label']}: MARGINAL — test AUC {d_te:+.4f}, WR {d_wr:+.1f}%")
    else:
        print(f"  🔴 {r['label']}: KEEP — test AUC {d_te:+.4f}, WR {d_wr:+.1f}%")

print(f"\n  ⏱ Total time: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
print(f"  Note: No models saved, no rules changed.")
print(f"{'='*70}\n")

# ── Save results JSON ────────────────────────────────────────────
out_path = Path(cfg.models_dir).parent / "ablation_results_clean34.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, default=str)
print(f"  Results saved: {out_path}")
