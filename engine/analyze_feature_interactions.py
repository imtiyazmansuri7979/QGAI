#!/usr/bin/env python3
"""
analyze_feature_interactions.py  (FS67-25, registry: feature_sweep_67)
────────────────────────────────────────────────────────────────────
Zero-retrain feature INTERACTION screen using XGBoost's native
pred_interactions (SHAP interaction values, built into xgboost — no
separate `shap` package needed).

WHY THIS EXISTS (Fable-5, 2026-07-17, Imtiyaz's correction to FS67-24):
whole-family ablation ("drop 7 correlated features, see if it hurts")
is a trivial test that will almost always show a big loss — it proves
a family carries signal, not that any TWO specific features interact.
The real, cheap way to find "does feature X specifically depend on
feature Y" is to score the ALREADY-TRAINED model's interaction
structure directly — one forward pass, no retrain.

This does NOT replace real ablation-backtest confirmation. It is a
RANKING/TRIAGE step: run this first (free), then only spend real
retrain+backtest budget confirming the top-ranked pairs (FS67-27 or a
manual QGAI_ABLATE run).

Usage:
    python analyze_feature_interactions.py
    python analyze_feature_interactions.py --model xgb_model.pkl --top 30
    python analyze_feature_interactions.py --sample 2000   (subsample rows for speed)

Output: backtest/results/feature_sweep_67/FS67-25_shap_interactions/
  interaction_matrix_full.csv   — every pair, ranked by mean |interaction|
  interaction_matrix_flagged.csv — subset where BOTH features are
                                    "individually safe" (dropped, or
                                    active+low importance) — these are
                                    the pairs most likely to hide a
                                    15_min_slot+M15_ADX-style surprise
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ENGINE = Path(__file__).parent
sys.path.insert(0, str(ENGINE))

from config import CFG
from features import (load_trades, load_ohlc, load_adx, load_news,
                       build_slot_table, build_feature_matrix, build_h4_range_table,
                       build_ob_table, FEATURE_ALIASES, FEATURE_FAMILIES, _ZERO_IMP)
from xgb_model import WinProbabilityModel

RESULT_DIR = ENGINE.parent / "backtest" / "results" / "feature_sweep_67" / "FS67-25_shap_interactions"


def _family_of(feat):
    for fam, members in FEATURE_FAMILIES.items():
        if feat in members:
            return fam
    return "?"


def build_matrix_for_analysis():
    """Rebuild the exact same feature matrix train.py uses, on the FULL
    committed dataset (no QGAI_TRAIN_CUTOFF — we want the same distribution
    the live model was actually trained on)."""
    cfg = CFG.paths
    print("Loading data (same pipeline as train.py)...")
    trades = load_trades(cfg.trades_file)
    ohlc_df = load_ohlc(cfg.ohlc_file)
    adx_df = load_adx(cfg.adx_file)
    news_df = load_news(cfg.news_file)

    print("Building H4 range + Order Block tables...")
    h4_df = build_h4_range_table(ohlc_df)
    h1_ob = build_ob_table(ohlc_df, "1h")
    h4_ob_df = build_ob_table(ohlc_df, "4h")

    slot_tr_end = int(len(trades) * 0.70)
    slot_tbl = build_slot_table(trades.iloc[:slot_tr_end])

    print("Building feature matrix...")
    X, y, feat_names = build_feature_matrix(
        trades, ohlc_df, adx_df, news_df, slot_tbl,
        h4_df=h4_df, h1_ob=h1_ob, h4_ob_df=h4_ob_df
    )
    print(f"  {X.shape[0]:,} rows x {X.shape[1]} features")
    return X, feat_names


def main():
    ap = argparse.ArgumentParser(description="FS67-25: XGBoost native SHAP interaction screen")
    ap.add_argument("--model", default="xgb_model.pkl",
                     help="which live model file to analyze (default: xgb_model.pkl, the main directional model)")
    ap.add_argument("--models-dir", default=None,
                     help="override models dir (default: CFG.paths.models_dir / live)")
    ap.add_argument("--top", type=int, default=40, help="how many top pairs to print/save")
    ap.add_argument("--sample", type=int, default=3000,
                     help="subsample this many rows for the interaction pass (0 = all rows, slower)")
    args = ap.parse_args()

    models_dir = Path(args.models_dir) if args.models_dir else Path(CFG.paths.models_dir)
    model_path = models_dir / args.model
    if not model_path.exists():
        print(f"Model not found: {model_path}")
        return 1

    print(f"Loading model: {model_path}")
    wpm = WinProbabilityModel()
    wpm.load(str(model_path))
    feat_names = wpm.feature_names
    if not feat_names:
        print("Model has no stored feature_names — cannot map interaction indices to feature names.")
        return 1
    print(f"  Model has {len(feat_names)} features")

    X, built_names = build_matrix_for_analysis()
    if list(built_names) != list(feat_names):
        # Align by name — the live model's FEATURE_COLS may differ from the
        # currently-committed one (e.g. this model predates a later prune).
        missing = [f for f in feat_names if f not in built_names]
        if missing:
            print(f"Model expects features not in current build_feature_matrix output: {missing}")
            print("This model is stale vs current features.py — retrain first, or point --model at a fresh one.")
            return 1
        idx = [built_names.index(f) for f in feat_names]
        X = X[:, idx]

    if args.sample and args.sample < X.shape[0]:
        rng = np.random.default_rng(42)
        sel = rng.choice(X.shape[0], size=args.sample, replace=False)
        X_sample = X[sel]
        print(f"  Subsampled {args.sample:,} / {X.shape[0]:,} rows for interaction scoring")
    else:
        X_sample = X

    print("Scaling features (using model's fitted scaler)...")
    X_scaled = wpm.scaler.transform(X_sample)

    print("Computing SHAP interaction values (XGBoost native, no retrain)...")
    import xgboost as xgb
    booster = wpm.xgb_model.get_booster()
    dmat = xgb.DMatrix(X_scaled, feature_names=list(feat_names))
    # Shape: (n_samples, n_features+1, n_features+1) — last row/col is the bias term
    interactions = booster.predict(dmat, pred_interactions=True)
    interactions = interactions[:, :-1, :-1]  # drop bias term
    mean_abs = np.mean(np.abs(interactions), axis=0)  # (n_features, n_features)
    print(f"  Interaction matrix: {mean_abs.shape}")

    n = len(feat_names)
    rows = []
    for i in range(n):
        for j in range(i + 1, n):
            fi, fj = feat_names[i], feat_names[j]
            fam_i, fam_j = _family_of(fi), _family_of(fj)
            safe_i = fi in _ZERO_IMP
            safe_j = fj in _ZERO_IMP
            rows.append({
                "feature_a": fi, "feature_b": fj,
                "alias_a": FEATURE_ALIASES.get(fi, (fi, "?"))[0],
                "alias_b": FEATURE_ALIASES.get(fj, (fj, "?"))[0],
                "family_a": fam_i, "family_b": fam_j,
                "same_family": fam_i == fam_j,
                "mean_abs_interaction": round(float(mean_abs[i, j]), 6),
                "a_currently_dropped": safe_i,
                "b_currently_dropped": safe_j,
                "both_flagged_safe_or_dropped": safe_i or safe_j,
            })

    df = pd.DataFrame(rows).sort_values("mean_abs_interaction", ascending=False).reset_index(drop=True)

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    full_path = RESULT_DIR / "interaction_matrix_full.csv"
    df.to_csv(full_path, index=False, encoding="utf-8-sig")
    print(f"\nFull ranked interaction matrix saved: {full_path}")

    flagged = df[df["both_flagged_safe_or_dropped"]].head(args.top)
    flagged_path = RESULT_DIR / "interaction_matrix_flagged.csv"
    flagged.to_csv(flagged_path, index=False, encoding="utf-8-sig")
    print(f"Flagged pairs (>=1 side dropped/low-importance) saved: {flagged_path}")

    print(f"\nTop {min(args.top, len(df))} pairs overall (by mean |interaction|):")
    print(f"{'feature_a':22s} {'feature_b':22s} {'family_a':14s} {'family_b':14s} {'interaction':>12s}")
    for _, r in df.head(args.top).iterrows():
        print(f"{r['feature_a']:22s} {r['feature_b']:22s} {r['family_a']:14s} {r['family_b']:14s} {r['mean_abs_interaction']:12.5f}")

    print("\nHow to use this:")
    print("  1. Pairs high on this list AND where at least one side is currently")
    print("     dropped/low-importance are candidates for a 15_min_slot+M15_ADX-style")
    print("     hidden interaction (individually looked safe, jointly may not be).")
    print("  2. This is a TRIAGE ranking, not proof — confirm top ~5 with a real")
    print("     joint-ablation backtest (QGAI_ABLATE=\"featA,featB\") before acting.")
    print("  3. Cross-check against FS67-27 (cumulative joint-drop of the pruned set) —")
    print("     if that comes back clean, hidden pairs here are lower priority.")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
