"""
xgb_model.py — v2 IMPROVED
────────────────────────────
4 Improvements:
1. Walk-Forward Training (no data leakage)
2. Ensemble: XGBoost + LightGBM + CatBoost
3. Feature Selection (top 20 by importance)
4. Time-Series Cross-Validation

Result: TEST AUC 0.51 → 0.65+ expected
"""

import os
import numpy as np
import joblib
from pathlib import Path
from sklearn.preprocessing import RobustScaler
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.feature_selection import SelectFromModel
import xgboost as xgb
import lightgbm as lgb
import catboost as cb
from config import CFG

# Noise-floor calibration (Fable-5, 2026-07-17, FS67-26): set QGAI_SEED to
# override the hardcoded random_state=42 for one calibration retrain, so the
# spread of total_R across seeds on an UNCHANGED feature set measures the
# backtest's noise floor. Unset/empty = original behaviour (seed 42 always).
_SEED = int(os.environ.get("QGAI_SEED", "42"))


class WinProbabilityModel:

    def __init__(self):
        self.scaler         = RobustScaler()
        self.iso_reg        = None
        self.calibrated     = None
        self.feature_names  = None
        self.selected_features = None   # top features after selection
        self.selector       = None

        # ── 3 Base Models ────────────────────────────────────
        xc = CFG.xgb
        self.xgb_model = xgb.XGBClassifier(
            n_estimators          = 200,
            max_depth             = 4,
            learning_rate         = 0.05,
            subsample             = 0.7,
            colsample_bytree      = 0.7,
            min_child_weight      = 8,
            gamma                 = 0.0,
            reg_alpha             = 0.0,
            reg_lambda            = 1.0,
            early_stopping_rounds = 30,
            objective             = "binary:logistic",
            eval_metric           = ["logloss","auc"],
            tree_method           = "hist",
            random_state          = _SEED,
            n_jobs                = -1,
        )

        self.lgb_model = lgb.LGBMClassifier(
            n_estimators      = 300,
            max_depth         = 4,
            learning_rate     = 0.03,
            subsample         = 0.7,
            colsample_bytree  = 0.7,
            min_child_samples = 20,
            reg_alpha         = 0.3,
            reg_lambda        = 2.0,
            random_state      = _SEED,
            n_jobs            = -1,
            verbose           = -1,
        )

        self.cat_model = cb.CatBoostClassifier(
            iterations        = 300,
            depth             = 4,
            learning_rate     = 0.03,
            l2_leaf_reg       = 5,
            random_seed       = _SEED,
            verbose           = 0,
        )

        # Ensemble weights (XGB slightly more trusted)
        self.weights = [0.40, 0.35, 0.25]   # XGB, LGB, CAT — Original best

    # ─────────────────────────────────────────────────────────
    # WALK-FORWARD TRAINING
    # ─────────────────────────────────────────────────────────
    def fit(self, X_train, y_train, X_val, y_val, feature_names=None,
            xgb_params=None, lgb_params=None, cat_params=None):
        self.feature_names = feature_names

        # Override model params if provided
        if xgb_params:
            self.xgb_model.set_params(**xgb_params)
        if lgb_params:
            self.lgb_model.set_params(**lgb_params)
        if cat_params:
            self.cat_model.set_params(**cat_params)

        # Scale
        X_tr = self.scaler.fit_transform(X_train)
        X_va = self.scaler.transform(X_val)

        # Class weight
        n_pos = y_train.sum()
        n_neg = len(y_train) - n_pos
        scale_pos = n_neg / (n_pos + 1e-9)
        print(f"  scale_pos_weight = {scale_pos:.2f}")

        # ── STEP 1: Use ALL features — no selection ───────────
        print(f"  Step 1: Using all {X_tr.shape[1]} features (no selection)...")
        self.selected_features = np.arange(X_tr.shape[1])  # all indices

        X_tr_sel = X_tr
        X_va_sel = X_va

        if feature_names:
            print(f"  All {len(feature_names)} features: {feature_names}")

        # ── STEP 2: Walk-Forward Validation ──────────────────
        print(f"  Step 2: Walk-forward cross-validation...")
        n = len(X_tr_sel)
        fold_size = n // 5
        cv_aucs = []

        for fold in range(3):  # 3 walk-forward folds
            train_end = fold_size * (fold + 3)
            val_start = train_end
            val_end   = min(val_start + fold_size, n)

            # Skip fold if val set is too small (causes AUC=1.0 on tiny samples)
            MIN_VAL_SIZE = 30
            if (val_end - val_start) < MIN_VAL_SIZE:
                print(f"    Fold {fold+1}: skipped (val_size={val_end-val_start} < {MIN_VAL_SIZE})")
                break

            X_fold_tr = X_tr_sel[:train_end]
            y_fold_tr = y_train[:train_end]
            X_fold_va = X_tr_sel[val_start:val_end]
            y_fold_va = y_train[val_start:val_end]

            if len(np.unique(y_fold_va)) < 2:
                print(f"    Fold {fold+1}: skipped (only one class in val set)")
                continue

            tmp = xgb.XGBClassifier(
                n_estimators=200, max_depth=4, learning_rate=0.05,
                tree_method="hist", random_state=_SEED, n_jobs=-1
            )
            tmp.fit(X_fold_tr, y_fold_tr,
                    eval_set=[(X_fold_va, y_fold_va)],
                    verbose=False)
            proba = tmp.predict_proba(X_fold_va)[:, 1]
            auc = roc_auc_score(y_fold_va, proba)
            cv_aucs.append(auc)
            print(f"    Fold {fold+1}: AUC = {auc:.4f}")

        if cv_aucs:
            print(f"  CV AUC: {np.mean(cv_aucs):.4f} ± {np.std(cv_aucs):.4f}")

        # ── STEP 3: Train all 3 models ────────────────────────
        print(f"\n  Step 3: Training ensemble (XGB + LGB + CAT)...")

        # XGBoost
        print(f"  Training XGBoost...")
        self.xgb_model.set_params(scale_pos_weight=scale_pos)
        self.xgb_model.fit(
            X_tr_sel, y_train,
            eval_set=[(X_va_sel, y_val)],
            verbose=50,
        )

        # LightGBM
        print(f"\n  Training LightGBM...")
        self.lgb_model.set_params(scale_pos_weight=scale_pos)
        import pandas as pd
        feat_sel_names = [f"f{i}" for i in range(X_tr_sel.shape[1])]
        X_tr_lgb = pd.DataFrame(X_tr_sel, columns=feat_sel_names)
        X_va_lgb = pd.DataFrame(X_va_sel, columns=feat_sel_names)
        self.lgb_model.fit(
            X_tr_lgb, y_train,
            eval_set=[(X_va_lgb, y_val)],
            callbacks=[lgb.early_stopping(30, verbose=False),
                       lgb.log_evaluation(50)],
        )

        # CatBoost
        print(f"\n  Training CatBoost...")
        self.cat_model.set_params(class_weights={0:1.0, 1:scale_pos})
        self.cat_model.fit(
            X_tr_sel, y_train,
            eval_set=(X_va_sel, y_val),
            early_stopping_rounds=30,
        )

        # ── STEP 4: Isotonic Calibration on ensemble ──────────
        print(f"\n  Step 4: Calibrating ensemble...")
        raw_proba = self._ensemble_raw(X_va_sel)
        self.iso_reg = IsotonicRegression(out_of_bounds="clip")
        self.iso_reg.fit(raw_proba, y_val)
        print(f"  Calibration done on {len(y_val)} val samples ✅")

    def _ensemble_raw(self, X) -> np.ndarray:
        """Weighted average of 3 models — raw (uncalibrated)."""
        import pandas as pd
        import warnings
        p_xgb = self.xgb_model.predict_proba(X)[:, 1]
        feat_names = [f"f{i}" for i in range(X.shape[1])]
        X_lgb = pd.DataFrame(X, columns=feat_names)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            p_lgb = self.lgb_model.predict_proba(X_lgb)[:, 1]
        p_cat = self.cat_model.predict_proba(X)[:, 1]
        return (self.weights[0]*p_xgb +
                self.weights[1]*p_lgb +
                self.weights[2]*p_cat)

    def predict_proba_calibrated(self, X) -> np.ndarray:
        """Calibrated ensemble probability — uses all features."""
        X_sc = self.scaler.transform(X)
        raw  = self._ensemble_raw(X_sc)
        return self.iso_reg.predict(raw)

    def predict_win_prob(self, x_row: np.ndarray) -> float:
        """Single row inference — safe NaN/Inf handling."""
        x = np.nan_to_num(x_row.reshape(1,-1), nan=0.0, posinf=0.0, neginf=0.0)
        return float(self.predict_proba_calibrated(x)[0])

    def evaluate(self, X, y, split_name=""):
        proba = self.predict_proba_calibrated(X)
        preds = (proba >= CFG.filters.min_win_prob).astype(int)

        auc    = roc_auc_score(y, proba)
        brier  = brier_score_loss(y, proba)

        print(f"\n{'─'*55}")
        print(f"  Ensemble Evaluation [{split_name}]")
        print(f"  AUC        : {auc:.4f}")
        print(f"  Brier Score: {brier:.4f}")
        print(f"  Filtered (prob>{CFG.filters.min_win_prob}): {preds.sum()} / {len(preds)}")

        if preds.sum() > 0:
            fwr = y[preds==1].mean()
            print(f"  Win rate (filtered): {fwr*100:.1f}%")
            print(f"  Win rate (all)     : {y.mean()*100:.1f}%")

        # Feature importance from XGBoost — FULL ranked list + saved to CSV
        # (2026-06-19: was Top-5 only; now dumps every feature so low-importance
        # ones — e.g. the OB-structure block — can be reviewed/pruned data-driven.)
        if self.feature_names and self.selected_features is not None:
            imp = self.xgb_model.feature_importances_
            sel_names = [self.feature_names[i] for i in self.selected_features]
            order = np.argsort(imp)[::-1]
            print(f"\n  Feature importance (XGB, ranked — all {len(order)}):")
            _lines = ["rank,feature,importance"]
            for rank, i in enumerate(order, 1):
                if i < len(sel_names):
                    print(f"    {rank:>2}. {sel_names[i]:<30} {imp[i]:.4f}")
                    _lines.append(f"{rank},{sel_names[i]},{imp[i]:.6f}")
            try:
                from pathlib import Path as _P
                _fp = _P(CFG.paths.models_dir) / "feature_importance.csv"
                _fp.write_text("\n".join(_lines), encoding="utf-8")
                print(f"  -> full importance saved to {_fp}")
            except Exception as _e:
                print(f"  (could not save feature_importance.csv: {_e})")

    def get_sl_multiplier(self, features: dict) -> float:
        sl   = CFG.sl
        mult = sl.normal
        hour = features.get("hour", 12)

        if features.get("london_adx_filtered", 0) == 1:
            mult = max(mult, sl.london_adx)
        if features.get("is_dead_slot", 0) == 1:
            mult = max(mult, sl.dead_slot)
        if features.get("mins_to_next_3star", 999) < 30:
            mult = max(mult, sl.before_event)

        m_since_eia = features.get("mins_since_last_eia", 999)
        if m_since_eia < 15 and sl.after_eia_0_15:
            return -1.0
        if 15 <= m_since_eia < 60:
            mult = max(mult, sl.after_eia_15_60)

        return mult

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "xgb":              self.xgb_model,
            "lgb":              self.lgb_model,
            "cat":              self.cat_model,
            "iso_reg":          self.iso_reg,
            "calibrated":       None,
            "scaler":           self.scaler,
            "feature_names":    self.feature_names,
            "selected_features":self.selected_features,
            "weights":          self.weights,
        }, path)
        print(f"  Ensemble model saved → {path}")

    def load(self, path: str):
        # ── Atomic load: validate ALL keys before touching self ──
        # If joblib.load() or any key access fails, self stays clean
        data = joblib.load(path)

        # Validate required keys exist before any assignment
        if "xgb" not in data:
            raise KeyError(f"Model file missing 'xgb' key: {path}")
        if "scaler" not in data:
            raise KeyError(f"Model file missing 'scaler' key: {path}")

        # All checks passed — now assign atomically
        _xgb    = data["xgb"]
        _lgb    = data.get("lgb", data.get("base"))
        _cat    = data.get("cat")
        _iso    = data.get("iso_reg")
        _scaler = data["scaler"]
        _fnames = data.get("feature_names")
        _sfeat  = data.get("selected_features")
        _wts    = data.get("weights", [0.40, 0.35, 0.25])

        # Backward compat: old single model
        if _cat is None:
            _cat = _xgb
            _lgb = _xgb
            _wts = [1.0, 0.0, 0.0]

        # Assign only after all values resolved
        self.xgb_model         = _xgb
        self.lgb_model         = _lgb
        self.cat_model         = _cat
        self.iso_reg           = _iso
        self.calibrated        = data.get("calibrated")
        self.scaler            = _scaler
        self.feature_names     = _fnames
        self.selected_features = _sfeat
        self.weights           = _wts

        print(f"  Ensemble model loaded ← {path}")
        return self
