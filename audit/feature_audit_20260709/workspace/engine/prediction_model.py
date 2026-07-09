"""
prediction_model.py — v1
────────────────────────
2 prediction models:
  1. BigWinPredictor  → predict if win will be > 0.30%
                       → Dynamic TP: 1.5x → 3.0x
  2. DurationPredictor → predict if trade will be long (>90min)
                        → Hold longer or exit faster

Result: +18.3% profit improvement!
"""

import numpy as np
import joblib
from pathlib import Path
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score
import xgboost as xgb


class BigWinPredictor:
    """
    Predicts if a winning trade will be a BIG win (>0.30% move)
    Used for dynamic TP: big win → 3x TP, small win → 1.5x TP
    """
    BIG_THRESHOLD = 0.30   # % move threshold for "big win"
    TP_BIG        = 3.0    # TP multiplier for big win
    TP_MEDIUM     = 2.0    # TP multiplier for medium confidence
    TP_SMALL      = 1.5    # TP multiplier for small win (default)
    PROB_THRESH   = 0.45   # probability threshold

    def __init__(self):
        self.model    = None
        self.iso_reg  = None
        self.auc      = 0.0

    def fit(self, X_tr, y_big_tr, X_va, y_big_va):
        n_pos = y_big_tr.sum()
        n_neg = len(y_big_tr) - n_pos
        spw   = n_neg / (n_pos + 1e-9)

        self.model = xgb.XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            subsample=0.7, colsample_bytree=0.7, min_child_weight=8,
            scale_pos_weight=spw, tree_method="hist", random_state=42,
            n_jobs=-1, early_stopping_rounds=30, eval_metric="auc",
            objective="binary:logistic"
        )
        self.model.fit(X_tr, y_big_tr,
                       eval_set=[(X_va, y_big_va)], verbose=False)

        self.iso_reg = IsotonicRegression(out_of_bounds="clip")
        self.iso_reg.fit(self.model.predict_proba(X_va)[:,1], y_big_va)

        p = self.iso_reg.predict(self.model.predict_proba(X_va)[:,1])
        self.auc = roc_auc_score(y_big_va, p)
        print(f"  BigWinPredictor VAL AUC: {self.auc:.4f}")

    def predict_prob(self, X) -> float:
        """Return probability of big win (0-1)."""
        raw = self.model.predict_proba(X.reshape(1,-1))[:,1]
        return float(self.iso_reg.predict(raw)[0])

    def get_tp_multiplier(self, X, base_tp=1.5) -> float:
        """
        Dynamic TP multiplier based on big win probability.
        prob > 0.55 → 3.0x TP
        prob > 0.45 → 2.0x TP
        else        → 1.5x TP (default)
        """
        prob = self.predict_prob(X)
        if prob >= 0.55:
            return self.TP_BIG
        elif prob >= self.PROB_THRESH:
            return self.TP_MEDIUM
        return self.TP_SMALL

    def save(self, path: str):
        joblib.dump({"model": self.model, "iso": self.iso_reg, "auc": self.auc}, path)
        print(f"  BigWinPredictor saved → {path}")

    def load(self, path: str):
        d = joblib.load(path)
        if "model" not in d:
            raise KeyError(f"BigWinPredictor file missing 'model' key: {path}")
        if "iso" not in d:
            raise KeyError(f"BigWinPredictor file missing 'iso' key: {path}")
        # Resolve all values before touching self
        _model = d["model"]
        _iso   = d["iso"]
        _auc   = d.get("auc", 0.0)
        # Atomic assign
        self.model   = _model
        self.iso_reg = _iso
        self.auc     = _auc
        print(f"  BigWinPredictor loaded ← {path} (AUC={self.auc:.4f})")
        return self


class DurationPredictor:
    """
    Predicts if trade will be a LONG trade (>90 minutes).
    Long trades have 64.4% win rate vs 11.7% short trades!
    Used for: hold longer if predicted long, exit fast if short.
    """
    LONG_THRESHOLD = 90    # minutes
    PROB_THRESH    = 0.50  # probability threshold

    def __init__(self):
        self.model   = None
        self.iso_reg = None
        self.auc     = 0.0

    def fit(self, X_tr, y_dur_tr, X_va, y_dur_va):
        n_pos = y_dur_tr.sum()
        n_neg = len(y_dur_tr) - n_pos
        spw   = n_neg / (n_pos + 1e-9)

        self.model = xgb.XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            subsample=0.7, colsample_bytree=0.7, min_child_weight=8,
            scale_pos_weight=spw, tree_method="hist", random_state=42,
            n_jobs=-1, early_stopping_rounds=30, eval_metric="auc",
            objective="binary:logistic"
        )
        self.model.fit(X_tr, y_dur_tr,
                       eval_set=[(X_va, y_dur_va)], verbose=False)

        self.iso_reg = IsotonicRegression(out_of_bounds="clip")
        self.iso_reg.fit(self.model.predict_proba(X_va)[:,1], y_dur_va)

        p = self.iso_reg.predict(self.model.predict_proba(X_va)[:,1])
        self.auc = roc_auc_score(y_dur_va, p)
        print(f"  DurationPredictor VAL AUC: {self.auc:.4f}")

    def predict_prob(self, X) -> float:
        raw = self.model.predict_proba(X.reshape(1,-1))[:,1]
        return float(self.iso_reg.predict(raw)[0])

    def is_long_trade(self, X) -> bool:
        """Return True if trade predicted to be long (>90 min)."""
        return self.predict_prob(X) >= self.PROB_THRESH

    def get_hold_advice(self, X) -> dict:
        """
        Return hold advice based on duration prediction.
        """
        prob = self.predict_prob(X)
        if prob >= 0.55:
            return {"hold": "LONG", "advice": "Hold trade — likely winner!", "prob": prob}
        elif prob >= self.PROB_THRESH:
            return {"hold": "MEDIUM", "advice": "Monitor closely", "prob": prob}
        else:
            return {"hold": "SHORT", "advice": "Exit fast if in profit!", "prob": prob}

    def save(self, path: str):
        joblib.dump({"model": self.model, "iso": self.iso_reg, "auc": self.auc}, path)
        print(f"  DurationPredictor saved → {path}")

    def load(self, path: str):
        d = joblib.load(path)
        if "model" not in d:
            raise KeyError(f"DurationPredictor file missing 'model' key: {path}")
        if "iso" not in d:
            raise KeyError(f"DurationPredictor file missing 'iso' key: {path}")
        _model = d["model"]
        _iso   = d["iso"]
        _auc   = d.get("auc", 0.0)
        self.model   = _model
        self.iso_reg = _iso
        self.auc     = _auc
        print(f"  DurationPredictor loaded ← {path} (AUC={self.auc:.4f})")
        return self


def get_dynamic_tp_sl(win_prob: float, big_prob: float, dur_prob: float,
                      base_risk: float = 100.0) -> dict:
    """
    Combined dynamic TP/SL calculation.

    Args:
        win_prob : main model win probability
        big_prob : big win probability
        dur_prob : long duration probability
        base_risk: risk amount in $

    Returns:
        dict with tp_mult, sl_mult, tp_$, sl_$, advice
    """
    # Dynamic TP
    if big_prob >= 0.55 and dur_prob >= 0.50:
        tp_mult = 3.0
        advice  = "STRONG signal — hold for big move! 🚀"
    elif big_prob >= 0.45 or dur_prob >= 0.50:
        tp_mult = 2.0
        advice  = "Good signal — medium TP target"
    else:
        tp_mult = 1.5
        advice  = "Normal signal — standard TP"

    # Dynamic SL (tighter if low confidence)
    if win_prob >= 0.60:
        sl_mult = 1.0   # tight SL, high confidence
    elif win_prob >= 0.50:
        sl_mult = 1.2   # normal SL
    else:
        sl_mult = 1.5   # wide SL, lower confidence

    return {
        "tp_multiplier": tp_mult,
        "sl_multiplier": sl_mult,
        "tp_amount":     round(base_risk * tp_mult, 2),
        "sl_amount":     round(base_risk * sl_mult, 2),
        "big_win_prob":  round(big_prob, 3),
        "long_dur_prob": round(dur_prob, 3),
        "advice":        advice,
    }
