"""
self_learning.py
─────────────────
Two-layer self-learning:

A) Online Learning (River — HoeffdingTreeClassifier)
   → Updates after EVERY closed trade instantly

B) Periodic Retrain (XGBoost)
   → Runs every Sunday automatically
   → New model replaces old only if better

C) Drift Detector
   → Monitors last 50 trades win rate
   → If < 30% → triggers immediate retrain + alert
"""

import numpy as np
import pandas as pd
import joblib
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent  # dynamic path — no hardcoding
from datetime import datetime
try:
    from river import tree, preprocessing, metrics
    RIVER_AVAILABLE = True
except ImportError:
    RIVER_AVAILABLE = False
    tree = None
    preprocessing = None
    metrics = None
    print("  ⚠️  river not installed — online learning disabled. Run: pip install river")
from config import CFG


# ─────────────────────────────────────────────
# A. ONLINE LEARNING — River HoeffdingTree
# ─────────────────────────────────────────────

class OnlineLearner:
    """
    Updates after every closed trade.
    Lightweight — complements XGBoost.
    """

    def __init__(self):
        self.scaler = preprocessing.StandardScaler()
        self.model  = tree.HoeffdingTreeClassifier(
            grace_period     = 10,
            delta            = 1e-5,
            tau              = 0.05,
            leaf_prediction  = "mc",
        )
        self.metric      = metrics.Accuracy()
        self.n_trained   = 0
        self.recent_wins = []

    def update(self, features: dict, label: int):
        """
        Call after each trade closes.
        features = feature dict
        label    = 1 (Win) or 0 (Loss)
        """
        # River requires plain Python int — numpy.int64 causes crash
        label = int(label)

        x = self.scaler.learn_one(features)
        x = self.scaler.transform_one(features)

        pred = self.model.predict_one(x)
        self.model.learn_one(x, label)

        if pred is not None:
            self.metric.update(label, pred)

        self.n_trained  += 1
        self.recent_wins.append(label)
        if len(self.recent_wins) > 50:
            self.recent_wins.pop(0)

    def predict(self, features: dict) -> float:
        """Returns win probability from online model."""
        x = self.scaler.transform_one(features)
        proba = self.model.predict_proba_one(x)
        return proba.get(1, 0.5) if proba else 0.5

    def recent_win_rate(self) -> float:
        """Win rate of last N trades."""
        if not self.recent_wins:
            return 0.372
        return sum(self.recent_wins) / len(self.recent_wins)

    def accuracy(self) -> float:
        return self.metric.get()

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "scaler":       self.scaler,
            "model":        self.model,
            "n_trained":    self.n_trained,
            "recent_wins":  self.recent_wins,
        }, path)

    def load(self, path: str):
        if Path(path).exists():
            data            = joblib.load(path)
            self.scaler     = data["scaler"]
            self.model      = data["model"]
            self.n_trained  = data["n_trained"]
            self.recent_wins= data["recent_wins"]
            print(f"  Online model loaded ← {path} ({self.n_trained} trades)")
        return self


# ─────────────────────────────────────────────
# B. PERIODIC RETRAIN
# ─────────────────────────────────────────────

class PeriodicRetrainer:
    """
    Merges live_trades.csv with original backtesting data.
    Retrains XGBoost + HMM.
    Saves new model only if better than old.
    """

    def retrain(self,
                original_trades_path: str,
                live_log_path:        str,
                ohlc_path:            str,
                adx_path:             str,
                news_path:            str,
                models_dir:           str,
                registry_dir:         str):
        """Full retrain pipeline."""
        from features import (load_trades, load_ohlc, load_adx, load_news,
                              build_slot_table, build_feature_matrix, FEATURE_COLS)
        from hmm_model import MarketStateHMM, HMM_FEATURES
        from xgb_model import WinProbabilityModel
        from sklearn.model_selection import train_test_split

        print("\n" + "="*55)
        print("  PERIODIC RETRAIN STARTED")
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("="*55)

        # Load original data
        trades = load_trades(original_trades_path)

        # Merge live trades if available
        live_path = Path(live_log_path)
        if live_path.exists():
            live = pd.read_csv(live_path)
            live["datetime"] = pd.to_datetime(live["datetime"])
            live["win_bin"]  = live["label"].astype(int)
            print(f"  Live trades added: {len(live)} rows")
            # Only keep columns that match trades
            common = set(trades.columns) & set(live.columns)
            trades = pd.concat([trades, live[list(common)]], ignore_index=True)
            trades = trades.sort_values("datetime").reset_index(drop=True)

        print(f"  Total training trades: {len(trades)}")

        ohlc_df = load_ohlc(ohlc_path)
        adx_df  = load_adx(adx_path)
        news_df = load_news(news_path)
        slot_tbl= build_slot_table(trades)

        # Feature matrix
        X, y, feat_names = build_feature_matrix(trades, ohlc_df, adx_df, news_df, slot_tbl)

        # Time-based split (no shuffle)
        split = int(len(X) * 0.85)
        X_tr, X_va = X[:split], X[split:]
        y_tr, y_va = y[:split], y[split:]

        # Train HMM
        hmm_model = MarketStateHMM()
        hmm_model.fit(adx_df)

        # Add HMM state to features.
        # 2026-07-02 (Divyesh) HMM v3 fix: the old code mapped X columns 0-7 to ADX
        # feature names BY POSITION — wrong values fed to the HMM (X column order is
        # FEATURE_COLS, not the ADX list). Look up the ADX row by trade datetime
        # instead, keys from HMM_FEATURES (same as train.py).
        def _hmm_states_for(trades_slice):
            states = []
            for _, _tr in trades_slice.iterrows():
                a = adx_df[adx_df["datetime"] <= _tr["datetime"]]
                if len(a) > 0:
                    r = a.iloc[-1]
                    row = {k: float(r[k]) if k in r.index else 0.0 for k in hmm_model.features}
                else:
                    row = {k: 0.0 for k in hmm_model.features}
                states.append(hmm_model.predict(row))
            return np.array(states)
        hmm_states_tr = _hmm_states_for(trades.iloc[:split])
        hmm_states_va = _hmm_states_for(trades.iloc[split:])
        X_tr_full = np.column_stack([X_tr, hmm_states_tr])
        X_va_full = np.column_stack([X_va, hmm_states_va])
        feat_names_full = feat_names + ["hmm_state"]

        # Train XGBoost
        xgb_model = WinProbabilityModel()
        xgb_model.fit(X_tr_full, y_tr, X_va_full, y_va, feat_names_full)
        xgb_model.evaluate(X_va_full, y_va, "VAL (new model)")

        # Compare with old model
        old_auc = self._get_old_auc(models_dir)
        from sklearn.metrics import roc_auc_score
        new_proba = xgb_model.predict_proba_calibrated(X_va_full)
        new_auc   = roc_auc_score(y_va, new_proba)

        print(f"\n  Old AUC: {old_auc:.4f} | New AUC: {new_auc:.4f}")

        if new_auc >= old_auc:
            # Save new model
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            Path(registry_dir).mkdir(parents=True, exist_ok=True)
            hmm_model.save(f"{registry_dir}/hmm_{ts}.pkl")
            xgb_model.save(f"{registry_dir}/xgb_{ts}.pkl")
            # Replace current
            hmm_model.save(f"{models_dir}/hmm_model.pkl")
            xgb_model.save(f"{models_dir}/xgb_model.pkl")
            self._save_meta(models_dir, new_auc, ts, len(trades))
            print(f"  ✅ New model deployed (AUC {new_auc:.4f})")
        else:
            print(f"  ⚠️  New model worse — keeping old model (rollback)")

    def _get_old_auc(self, models_dir: str) -> float:
        meta_path = Path(models_dir) / "model_meta.json"
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                return json.load(f).get("auc", 0.0)
        return 0.0

    def _save_meta(self, models_dir, auc, ts, n_trades):
        meta = {"auc": auc, "timestamp": ts, "n_trades": n_trades}
        with open(Path(models_dir) / "model_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)


# ─────────────────────────────────────────────
# C. DRIFT DETECTOR
# ─────────────────────────────────────────────

class DriftDetector:
    """
    Monitors last N trades win rate.
    Triggers retrain if win rate drops below threshold.
    """

    def __init__(self):
        self.threshold  = CFG.filters.drift_threshold
        self.window     = CFG.filters.drift_window
        self.history    = []
        self.n_retrains = 0

    def add(self, label: int):
        """Add trade result (1=win, 0=loss)."""
        self.history.append(label)
        if len(self.history) > self.window:
            self.history.pop(0)

    def is_drifting(self) -> bool:
        """Returns True if win rate dropped below threshold."""
        if len(self.history) < 20:
            return False
        wr = sum(self.history) / len(self.history)
        return wr < self.threshold

    def current_win_rate(self) -> float:
        if not self.history:
            return 0.372
        return sum(self.history) / len(self.history)

    def check_and_alert(self) -> str:
        """Returns alert message if drifting."""
        wr = self.current_win_rate()
        if self.is_drifting():
            msg = (f"⚠️  DRIFT DETECTED! "
                   f"Last {len(self.history)} trades win rate = {wr*100:.1f}% "
                   f"(threshold {self.threshold*100:.0f}%) — RETRAIN TRIGGERED")
            print(msg)
            return msg
        return ""

    def save(self, path: str):
        joblib.dump({"history": self.history, "n_retrains": self.n_retrains}, path)

    def load(self, path: str):
        if Path(path).exists():
            data = joblib.load(path)
            self.history    = data["history"]
            self.n_retrains = data["n_retrains"]
        return self
