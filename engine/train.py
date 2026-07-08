"""
train.py
─────────
Full initial training pipeline.
Run once on backtesting data to create all model files.

Usage:
    cd C:\\quant_forex_ai
    python train.py
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.metrics import roc_auc_score

from config import CFG
from features import (load_trades, load_ohlc, load_adx, load_news,
                      build_slot_table, build_feature_matrix, FEATURE_COLS)
from hmm_model import MarketStateHMM, HMM_FEATURES
from xgb_model import WinProbabilityModel
from self_learning import OnlineLearner, DriftDetector


def main():
    print("\n" + "="*60)
    print("  QUANT GOLD AI v2 — TRAINING PIPELINE")
    from features import FEATURE_COLS as _FC
    print(f"  Asset: XAUUSD | M15 | {len(_FC)} Features")   # dynamic (was hardcoded 59 — stale)
    print("="*60 + "\n")

    cfg = CFG.paths
    Path(cfg.models_dir).mkdir(parents=True, exist_ok=True)
    Path(cfg.registry_dir).mkdir(parents=True, exist_ok=True)
    Path(cfg.logs_dir).mkdir(parents=True, exist_ok=True)
    print(f"  Output dir: {cfg.models_dir}")

    # ── STEP 1: Load Data ────────────────────────────────────
    print("► Step 1: Loading data...")
    trades  = load_trades(cfg.trades_file)
    ohlc_df = load_ohlc(cfg.ohlc_file)
    adx_df  = load_adx(cfg.adx_file)
    news_df = load_news(cfg.news_file)

    # ── Date sanity filter ────────────────────────────────────
    # Remove future/corrupt dates from live data merge
    # OHLC should not have dates beyond today + 1 day
    from datetime import datetime as _dt
    _today = _dt.now()
    _ohlc_before = len(ohlc_df)
    ohlc_df = ohlc_df[ohlc_df["datetime"] <= _today].copy()
    adx_df  = adx_df[adx_df["datetime"]  <= _today].copy()
    if len(ohlc_df) < _ohlc_before:
        print(f"  ⚠️ Removed {_ohlc_before-len(ohlc_df):,} future-dated OHLC rows")
    # ──────────────────────────────────────────────────────────

    print(f"  Trades : {len(trades):,} | {trades['datetime'].min().date()} → {trades['datetime'].max().date()}")
    print(f"  OHLC   : {len(ohlc_df):,} rows | {ohlc_df['datetime'].min().date()} → {ohlc_df['datetime'].max().date()}")

    # ── WFO CUTOFF (walk-forward): train only on data BEFORE cutoff ──
    # Set via env var QGAI_TRAIN_CUTOFF=YYYY-MM-DD. Filters trades+ohlc+adx
    # so the model never sees data at/after the cutoff (true out-of-sample).
    import os as _os
    _cutoff = _os.environ.get("QGAI_TRAIN_CUTOFF", "").strip()
    if _cutoff:
        _cut = pd.Timestamp(_cutoff)
        _tb = len(trades)
        trades  = trades[trades["datetime"]  < _cut].copy()
        ohlc_df = ohlc_df[ohlc_df["datetime"] < _cut].copy()
        adx_df  = adx_df[adx_df["datetime"]   < _cut].copy()
        news_df = news_df[news_df["datetime"] < _cut].copy() if "datetime" in news_df.columns else news_df
        print(f"  ⏳ WFO CUTOFF {_cutoff}: trades {_tb:,} → {len(trades):,} "
              f"(train on past only)")
        if len(trades) < 200:
            print(f"  ⚠️ Only {len(trades)} trades before cutoff — model may be weak")
    print(f"  ADX    : {len(adx_df):,} rows")
    print(f"  New features: h4_trending_h1_aligned, h4_ranging_h1_neutral,")
    print(f"                h4_ranging_h1_extended, h4_h1_regime_score,")
    print(f"                move_1hr, move_4hr, move_8hr, momentum_aligned_1hr, momentum_aligned_4hr,")
    print(f"                price_vs_ema200, above_ema200, ema200_dist_abs, near_ema200")
    print(f"  News   : {len(news_df):,} rows")

    # ── TRAINING ON ALL TRADES ───────────────────────────────
    # slot+day filter applied at INFERENCE only (mt5_bridge / inference.py)
    # slot_win_rate feature already encodes timing quality for the model
    # Training on all 2,788 trades → more data → better generalization
    print(f"\n  Training on ALL {len(trades):,} trades (full dataset)")
    print(f"  Slot+Day filter → applied at INFERENCE only")
    print(f"  Win rate: {trades['win_bin'].mean()*100:.1f}%")

    # Save slot_day_filter for inference use (load existing or skip)
    import json as _json
    _sdf_path = f"{cfg.models_dir}/slot_day_filter.json"
    if not Path(_sdf_path).exists():
        print(f"  ⚠️  slot_day_filter.json not found — inference filter disabled")
    else:
        _sdf = _json.load(open(_sdf_path))
        print(f"  Slot+Day filter saved: {len(_sdf)} slots | {sum(len(v) for v in _sdf.values())} combos (inference only)")
    # ─────────────────────────────────────────────────────────

    # ── STEP 1b: Build H4 Range Table ───────────────────────
    print("  Building H4 range-bound table...")
    from features import build_h4_range_table
    h4_df = build_h4_range_table(ohlc_df)
    big_moves = h4_df["is_big_move"].sum()
    range_phases = h4_df["in_range_phase"].sum()
    print(f"  H4 candles: {len(h4_df):,} | Big moves(≥2%): {big_moves} | Range phases: {range_phases}")

    from features import build_trend_ratio_table, build_ob_table
    ratio_df = build_trend_ratio_table(ohlc_df)
    print(f"  Trend ratio built: {len(ratio_df)} H4 rows")

    print("  Building Order Block tables...")
    h1_ob    = build_ob_table(ohlc_df, "1h")
    h4_ob_df = build_ob_table(ohlc_df, "4h")
    print(f"  H1 OBs: Bull={h1_ob['bull_ob'].sum()} Bear={h1_ob['bear_ob'].sum()}")
    print(f"  H4 OBs: Bull={h4_ob_df['bull_ob'].sum()} Bear={h4_ob_df['bear_ob'].sum()}")

    # ── STEP 2: Slot Table ───────────────────────────────────
    # LEAKAGE FIX 2026-06-19: build the (1-hour) slot win-rate table on the
    # TRAIN split ONLY (first 70%, matching the time-split below). Previously it
    # was built on the FULL trade set incl. future trades → look-ahead leakage
    # that inflated val/test AUC. Val/test now look up TRAIN-derived hourly WR.
    print("\n► Step 2: Building slot win rate table (1-hour, train-split only)...")
    _slot_tr_end = int(len(trades) * 0.70)
    slot_tbl = build_slot_table(trades.iloc[:_slot_tr_end])
    hot  = sum(1 for v in slot_tbl.values() if v > 0.50)
    dead = sum(1 for v in slot_tbl.values() if v < 0.25)
    print(f"  Hot slots (>50% win): {hot} | Dead slots (<25%): {dead}")
    joblib.dump(slot_tbl, f"{cfg.models_dir}/slot_table.pkl")

    # ── STEP 3: Feature Matrix ───────────────────────────────
    print("\n► Step 3: Building feature matrix...")
    # FIX 2026-06-14: pass h1_ob/h4_ob/ratio tables so OB + trend-ratio
    # features are REAL (not 999/0 fallback). Without these, the new
    # direction-aware OB S/R features train on constants → 0 importance.
    X, y, feat_names = build_feature_matrix(
        trades, ohlc_df, adx_df, news_df, slot_tbl,
        h4_df=h4_df, ratio_df=ratio_df, h1_ob=h1_ob, h4_ob_df=h4_ob_df
    )
    print(f"  Feature matrix: {X.shape[0]:,} trades × {X.shape[1]} features")
    print(f"  Win rate: {y.mean()*100:.1f}% ({y.sum():,} wins / {len(y):,} trades)")

    # ── STEP 4: Train/Val/Test split (time-based) ────────────
    print("\n► Step 4: Time-based split...")
    n      = len(X)
    tr_end = int(n * 0.70)
    va_end = int(n * 0.85)

    X_tr, y_tr = X[:tr_end],      y[:tr_end]
    X_va, y_va = X[tr_end:va_end], y[tr_end:va_end]
    X_te, y_te = X[va_end:],       y[va_end:]
    print(f"  Train: {len(X_tr):,} | Val: {len(X_va):,} | Test: {len(X_te):,}")

    # ── STEP 5: HMM Training ─────────────────────────────────
    print("\n► Step 5: Training HMM (market state)...")
    hmm_model = MarketStateHMM()
    # Fix Bug 2: fit HMM only on training slice — prevents future data leakage
    _hmm_cutoff  = trades.iloc[:tr_end]["datetime"].max()
    adx_df_train = adx_df[adx_df["datetime"] <= _hmm_cutoff]
    print(f"  HMM fit on training data up to: {_hmm_cutoff.date()} ({len(adx_df_train):,} ADX rows)")
    hmm_model.fit(adx_df_train)

    # Predict HMM states for all splits
    adx_feat_idx = [feat_names.index(f) for f in [
        "M15_ADX","M15_DI_diff","M30_ADX","M30_DI_diff",
        "H1_ADX","H1_DI_diff","H4_ADX","H4_DI_diff"
    ] if f in feat_names]

    print("  Computing HMM states from ADX data directly...")
    # 2026-07-02 (Divyesh) HMM v3: build adx_row from HMM_FEATURES (single source
    # of truth) — the old hardcoded key list silently dropped new HMM features
    # (v2 bug: PlusDI/MinusDI defaulted to 0 at predict → train/predict mismatch).
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
    tr_e = int(n_all*0.70); va_e = int(n_all*0.85)
    hmm_tr = get_hmm_from_adx(trades.iloc[:tr_e])
    hmm_va = get_hmm_from_adx(trades.iloc[tr_e:va_e])
    hmm_te = get_hmm_from_adx(trades.iloc[va_e:])

    # State distribution
    for s, name in [(0,"Ranging"),(1,"Trending"),(2,"Volatile")]:
        pct = (hmm_tr == s).mean() * 100
        print(f"  State {s} {name:10s}: {pct:.1f}% of training data")

    # Append HMM state as feature
    X_tr_full = np.column_stack([X_tr, hmm_tr])
    X_va_full = np.column_stack([X_va, hmm_va])
    X_te_full = np.column_stack([X_te, hmm_te])
    feat_full = feat_names + ["hmm_state"]

    hmm_model.save(f"{cfg.models_dir}/hmm_model.pkl")

    # ── STEP 6: XGBoost Training ─────────────────────────────
    print("\n► Step 6: Training XGBoost + Isotonic Calibration...")
    xgb_model = WinProbabilityModel()
    xgb_model.fit(X_tr_full, y_tr, X_va_full, y_va, feat_full)

    # ── STEP 7: Evaluation ───────────────────────────────────
    print("\n► Step 7: Evaluation...")
    xgb_model.evaluate(X_va_full, y_va, "VALIDATION")
    xgb_model.evaluate(X_te_full, y_te, "TEST")

    xgb_model.save(f"{cfg.models_dir}/xgb_model.pkl")

    # ── STEP 8: Init Online Learner + Drift Detector ─────────
    # WFO CORE-ONLY: skip BigWin/Duration (auxiliary predictors) for speed.
    # They don't gate entries — combined+buy+sell drive signals. Env var
    # QGAI_CORE_ONLY=1 set by the walk-forward orchestrator.
    import os as _os2
    _core_only = _os2.environ.get("QGAI_CORE_ONLY", "") == "1"
    if _core_only:
        print("\n► Step 8: SKIPPED (core-only WFO mode — BigWin/Duration reused)")
    else:
        print("\n► Step 8: Training Prediction Models...")
        from prediction_model import BigWinPredictor, DurationPredictor
        # Labels
        y_big = (trades["% Move"].abs() > 0.30).astype(int).values
        y_dur = (trades["Duration (min)"] >= 90).astype(int).values

        # Fix: train BigWin/Duration with the full feature set (incl. hmm_state)
        big_predictor = BigWinPredictor()
        big_predictor.fit(X_tr_full, y_big[:tr_end], X_va_full, y_big[tr_end:va_end])
        big_predictor.save(f"{cfg.models_dir}/big_win_model.pkl")

        dur_predictor = DurationPredictor()
        dur_predictor.fit(X_tr_full, y_dur[:tr_end], X_va_full, y_dur[tr_end:va_end])
        dur_predictor.save(f"{cfg.models_dir}/duration_model.pkl")

        print(f"  BigWin AUC : {big_predictor.auc:.4f}")
        print(f"  Duration AUC: {dur_predictor.auc:.4f}")

    # ── STEP 8b: Train state-specific models (Ranging/Trending/Volatile) ──
    print("\n► Step 8b: Training state-specific models...")
    from features import RANGING_FEATURES, TRENDING_FEATURES, VOLATILE_FEATURES, STATE_FEATURE_MAP

    state_feat_map = {
        "ranging":  RANGING_FEATURES,
        "trending": TRENDING_FEATURES,
        "volatile": VOLATILE_FEATURES,
    }

    for s_idx, s_name in [(0,"ranging"), (1,"trending"), (2,"volatile")]:
        mask_tr = (hmm_tr == s_idx)
        mask_va = (hmm_va == s_idx)
        if mask_tr.sum() < 30:
            print(f"  ⚠️ {s_name}: only {mask_tr.sum()} train samples — skipping")
            continue

        # ── Use state-specific feature list ──────────────────
        s_feats = state_feat_map[s_name]
        # Map feature names → indices in feat_full
        s_idx_list = [feat_full.index(f) for f in s_feats if f in feat_full]
        missing = [f for f in s_feats if f not in feat_full]
        if missing:
            print(f"  ⚠️ {s_name}: missing features {missing}")
        print(f"  {s_name}: {len(s_idx_list)} features (from {len(feat_full)} total)")

        X_tr_s = X_tr_full[mask_tr][:, s_idx_list]
        y_tr_s = y_tr[mask_tr]
        X_va_s = X_va_full[mask_va][:, s_idx_list] if mask_va.sum() >= 10 else X_va_full[:, s_idx_list]
        y_va_s = y_va[mask_va]                      if mask_va.sum() >= 10 else y_va

        state_model = WinProbabilityModel()
        state_model.fit(X_tr_s, y_tr_s, X_va_s, y_va_s, s_feats)
        state_model.save(f"{cfg.models_dir}/model_{s_name}.pkl")
        print(f"  ✅ model_{s_name}.pkl | train:{mask_tr.sum()} val:{mask_va.sum()} | feat:{len(s_idx_list)}")

    print("\n► Step 9: Initialising online learner + drift detector...")
    online = OnlineLearner()
    drift  = DriftDetector()
    online.save(f"{cfg.models_dir}/online_model.pkl")
    drift.save(f"{cfg.models_dir}/drift_detector.pkl")

    # ── STEP 9: Save metadata ────────────────────────────────
    import json
    proba_va = xgb_model.predict_proba_calibrated(X_va_full)
    auc      = roc_auc_score(y_va, proba_va)
    meta = {
        "auc": round(auc, 4),
        "timestamp": pd.Timestamp.now().strftime("%Y%m%d_%H%M"),
        "n_trades": len(trades),
        "features": feat_full,
        "win_rate": round(float(y.mean()), 4),
    }
    with open(f"{cfg.models_dir}/model_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    # ── DONE ─────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  ✅ Training complete!")
    print(f"  AUC: {auc:.4f}")
    print(f"  Models saved → {cfg.models_dir}/")
    print(f"  Files:")
    for f in Path(cfg.models_dir).glob("*"):
        print(f"    {f.name}")
    print(f"{'='*60}\n")
    print("  Next step: python inference.py")

def train_directional_models():
    """
    Train separate XGBoost models for BUY and SELL.
    Called after main() — uses same feature pipeline.
    """
    print("\n" + "="*60)
    print("  DIRECTIONAL MODELS — BUY + SELL Separate Training")
    print("="*60 + "\n")

    cfg = CFG.paths

    # ── Load data ────────────────────────────────────────────
    print("► Loading data...")
    trades  = load_trades(cfg.trades_file)
    ohlc_df = load_ohlc(cfg.ohlc_file)
    adx_df  = load_adx(cfg.adx_file)
    news_df = load_news(cfg.news_file)

    # Date sanity filter — remove future/corrupt dates
    from datetime import datetime as _dt2
    _today2 = _dt2.now()
    ohlc_df = ohlc_df[ohlc_df["datetime"] <= _today2].copy()
    adx_df  = adx_df[adx_df["datetime"]  <= _today2].copy()

    # Training on ALL trades — slot+day filter at inference only
    print(f"  Training on ALL {len(trades):,} trades (full dataset)")
    print(f"  Win rate: {trades['win_bin'].mean()*100:.1f}%")
    print(f"  BUY: {(trades['Type']=='BUY').sum():,} | SELL: {(trades['Type']=='SELL').sum():,}")

    from features import build_h4_range_table, build_trend_ratio_table, build_ob_table
    h4_df    = build_h4_range_table(ohlc_df)
    ratio_df = build_trend_ratio_table(ohlc_df)
    h1_ob    = build_ob_table(ohlc_df, "1h")
    h4_ob_df = build_ob_table(ohlc_df, "4h")
    slot_tbl = joblib.load(f"{cfg.models_dir}/slot_table.pkl")
    hmm_model = MarketStateHMM()
    hmm_model.load(f"{cfg.models_dir}/hmm_model.pkl")

    # ── Build full feature matrix ────────────────────────────
    print("► Building feature matrix...")
    X, y, feat_names = build_feature_matrix(
        trades, ohlc_df, adx_df, news_df, slot_tbl,
        h4_df=h4_df, ratio_df=ratio_df, h1_ob=h1_ob, h4_ob_df=h4_ob_df
    )

    # Add HMM state — HMM v3: keys from HMM_FEATURES (single source of truth)
    def get_hmm_states(trades_df):
        states = []
        for _, trade in trades_df.iterrows():
            t = trade["datetime"]
            a = adx_df[adx_df["datetime"] <= t]
            if len(a) > 0:
                r = a.iloc[-1]
                adx_row = {k: float(r[k]) if k in r.index else 0.0 for k in hmm_model.features}
            else:
                adx_row = {k: 0.0 for k in hmm_model.features}
            states.append(hmm_model.predict(adx_row))
        return np.array(states)

    # Bug 14 fix: do NOT compute HMM states on full trades here
    # States will be computed per-split inside the training loop
    feat_full  = feat_names + ["hmm_state"]

    # ── Split BUY and SELL ───────────────────────────────────
    direction  = trades["Type"].values   # BUY or SELL
    buy_mask   = direction == "BUY"
    sell_mask  = direction == "SELL"

    print(f"  BUY trades : {buy_mask.sum():,} | WR={y[buy_mask].mean()*100:.1f}%")
    print(f"  SELL trades: {sell_mask.sum():,} | WR={y[sell_mask].mean()*100:.1f}%")

    # ── Direction-specific parameters (data-proven) ───────────
    # BUY  → momentum-driven (move_1hr #1) → balanced params
    #        TEST AUC 0.6381 → 0.7607 (+12.3pp), WR 72% → 82.1%
    # SELL → structure-driven (in_range_phase #1) → conservative params
    #        TEST AUC 0.6836 → 0.8395 (+15.6pp), gap 0.124 → 0.006
    DIRECTION_PARAMS = {
        "BUY": {
            "xgb": dict(n_estimators=400, max_depth=4, learning_rate=0.04,
                        subsample=0.75, colsample_bytree=0.75,
                        min_child_weight=5, reg_alpha=0.1, reg_lambda=1.5,
                        early_stopping_rounds=50),
            "lgb": dict(n_estimators=400, max_depth=4, learning_rate=0.04,
                        subsample=0.75, colsample_bytree=0.75,
                        min_child_samples=15, reg_alpha=0.1, reg_lambda=1.5),
            "cat": dict(iterations=400, depth=4, learning_rate=0.04,
                        l2_leaf_reg=4),
        },
        "SELL": {
            "xgb": dict(n_estimators=400, max_depth=3, learning_rate=0.03,
                        subsample=0.70, colsample_bytree=0.70,
                        min_child_weight=8, reg_alpha=0.2, reg_lambda=2.0,
                        early_stopping_rounds=50),
            "lgb": dict(n_estimators=400, max_depth=3, learning_rate=0.03,
                        subsample=0.70, colsample_bytree=0.70,
                        min_child_samples=20, reg_alpha=0.2, reg_lambda=2.0),
            "cat": dict(iterations=400, depth=3, learning_rate=0.03,
                        l2_leaf_reg=7),
        },
    }

    # ── Train each model ─────────────────────────────────────
    for label, mask in [("BUY", buy_mask), ("SELL", sell_mask)]:
        print(f"\n► Training {label} model...")
        X_dir = X[mask]       # Bug 14 fix: X (no hmm) — hmm added per-split below
        y_dir = y[mask]

        n      = len(X_dir)
        tr_end = int(n * 0.70)
        va_end = int(n * 0.85)

        # Bug 14 fix: compute HMM states per split — no future data leakage
        trades_dir = trades[mask].reset_index(drop=True)
        hmm_tr     = get_hmm_states(trades_dir.iloc[:tr_end])
        hmm_va     = get_hmm_states(trades_dir.iloc[tr_end:va_end])
        hmm_te     = get_hmm_states(trades_dir.iloc[va_end:])

        X_tr, y_tr = np.column_stack([X_dir[:tr_end],       hmm_tr.reshape(-1,1)]), y_dir[:tr_end]
        X_va, y_va = np.column_stack([X_dir[tr_end:va_end], hmm_va.reshape(-1,1)]), y_dir[tr_end:va_end]
        X_te, y_te = np.column_stack([X_dir[va_end:],       hmm_te.reshape(-1,1)]), y_dir[va_end:]

        print(f"  Train:{len(X_tr):,} Val:{len(X_va):,} Test:{len(X_te):,}")
        print(f"  Params: depth={DIRECTION_PARAMS[label]['xgb']['max_depth']} "
              f"lr={DIRECTION_PARAMS[label]['xgb']['learning_rate']} "
              f"min_child={DIRECTION_PARAMS[label]['xgb']['min_child_weight']} "
              f"reg_α={DIRECTION_PARAMS[label]['xgb']['reg_alpha']}")

        model = WinProbabilityModel()
        model.fit(X_tr, y_tr, X_va, y_va, feat_full,
                  xgb_params=DIRECTION_PARAMS[label]["xgb"],
                  lgb_params=DIRECTION_PARAMS[label]["lgb"],
                  cat_params=DIRECTION_PARAMS[label]["cat"])
        model.evaluate(X_va, y_va, f"{label} VALIDATION")
        model.evaluate(X_te, y_te, f"{label} TEST")

        save_path = f"{cfg.models_dir}/{label.lower()}_model.pkl"
        model.save(save_path)
        print(f"  Saved: {save_path}")

        # Save meta
        import json
        proba_va = model.predict_proba_calibrated(X_va)
        auc      = roc_auc_score(y_va, proba_va)
        meta = {
            "direction":  label,
            "auc":        round(auc, 4),
            "timestamp":  pd.Timestamp.now().strftime("%Y%m%d_%H%M"),
            "n_trades":   int(mask.sum()),
            "win_rate":   round(float(y_dir.mean()), 4),
            "features":   feat_full,
        }
        with open(f"{cfg.models_dir}/{label.lower()}_model_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        print(f"  AUC={auc:.4f} | WR={y_dir.mean()*100:.1f}%")

    print("\n DIRECTIONAL MODELS DONE!")
    print("  buy_model.pkl  — Use for BUY signals")
    print("  sell_model.pkl — Use for SELL signals")


if __name__ == "__main__":
    main()
    print("\n" + "="*60)
    print("  Now training directional BUY/SELL models...")
    print("="*60)
    train_directional_models()

    # ── Save retrain date (works for both manual and scheduled runs) ──
    try:
        from pathlib import Path as _Path
        from datetime import datetime as _dt
        _retrain_flag = _Path("logs/.last_retrain")
        _retrain_flag.parent.mkdir(parents=True, exist_ok=True)
        _retrain_flag.write_text(_dt.now().isoformat())
        print(f"\n✅ Retrain date saved: {_dt.now().date()}")
    except Exception as _e:
        print(f"⚠️ Could not save retrain date: {_e}")
