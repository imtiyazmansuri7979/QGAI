"""
hmm_model.py
─────────────
Market State Detection using GaussianMixture (sklearn).
Works on ALL Python versions including 3.14+.
No hmmlearn dependency.

3 Market States:
  0 = Ranging    (low ADX, unclear direction)
  1 = Trending   (high ADX, strong DI alignment)
  2 = Volatile   (high ADX, conflicting DI)
"""

import os
import numpy as np
import joblib
from pathlib import Path
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from config import CFG


# 2026-07-02 (Divyesh) v3: [ADX, DI_diff, band_width_pct] per TF.
# History of the "flat market reads Volatile" fix:
#   v1 (raw +DI/-DI): GMM clustered by DIRECTION (up/down/flat) — BAD.
#   v2 (di_sum + clarity): di_sum nearly constant across clusters (~40-43) so it
#      did NOT discriminate volatility (65% Volatile / 0.6% Ranging, unstable).
#      ALSO: predict paths only pass ADX/DI_diff keys, so PlusDI/MinusDI silently
#      defaulted to 0 at inference — train/predict mismatch.
#   v3 (this): add a REAL, lag-free volatility feature: {TF}_band_width_pct
#      = (SMMA2(High)-SMMA2(Low))/close*100 (trend_signal.py band; NOT ATR — lagging).
#      Clarity = |DI_diff| (== |+DI - -DI|, but DI_diff is already plumbed through
#      every predict path). Wide band + low clarity = Volatile; narrow band = Ranging
#      (quiet); high clarity = Trending.
# Requires the new columns in ADX data (regen_adx_di.py / mt5_data_updater.py)
# + HMM retrain.
#
# A/B VARIANTS (2026-07-02, WFO-both decision by Divyesh):
#   QGAI_HMM_VARIANT=spec : [ADX, DI_diff(|.|), band_width_pct]  — literal spec.
#       Sandbox check: Volatile cluster NOT high-band; chop reads Trending;
#       ~48% of quiet bars read Volatile; train/full distribution drifts.
#   QGAI_HMM_VARIANT=rel  : [ADX, di_eff, band_rel]  — DEFAULT (recommended).
#       di_eff   = 100*|+DI - -DI|/(+DI + -DI)  (instantaneous DX — lag-free
#                  direction clarity; smoothed ADX/DI_diff stay high in
#                  post-trend chop, di_eff drops immediately)
#       band_rel = band_width_pct / trailing 30-day mean  (gold's absolute
#                  vol drifted 2022→2026 — raw band %% is non-stationary;
#                  numerator stays lag-free, denominator is slow context)
#       Sandbox check: Volatile=1.65x band_rel / Ranging=0.79x; flat 07-02
#       window 18 Ranging/4 Trending/0 Volatile; train≈full distribution.
# The trained pkl stores its own feature list — predict always uses the
# pkl's list, so the live bridge cannot mismatch the env var.
#   QGAI_HMM_VARIANT=legacy : ORIGINAL 8-feature model [ADX, DI_diff] x4 (raw,
#       no engineering; labeling: lowest-ADX=Ranging, then |M15 DI_diff| high=
#       Trending / low=Volatile — restored from engine_backup_0612 for the
#       FIX-1 honest re-baseline A/B on leak-free as-of data, 2026-07-02).
_VARIANT = os.environ.get("QGAI_HMM_VARIANT", "rel").strip().lower()
if _VARIANT not in ("spec", "rel", "legacy"):
    _VARIANT = "rel"
_TFS = ("M15", "M30", "H1", "H4")
if _VARIANT == "spec":
    HMM_FEATURES = [f"{tf}_{c}" for tf in _TFS
                    for c in ("ADX", "DI_diff", "band_width_pct")]
elif _VARIANT == "legacy":
    HMM_FEATURES = [f"{tf}_{c}" for tf in _TFS
                    for c in ("ADX", "DI_diff")]
else:
    HMM_FEATURES = [f"{tf}_{c}" for tf in _TFS
                    for c in ("ADX", "di_eff", "band_rel")]

STATE_NAMES = {0: "Ranging", 1: "Trending", 2: "Volatile"}


class MarketStateHMM:
    """
    GaussianMixture-based market regime detector.
    Drop-in replacement for HMM — same interface.
    Works on Python 3.14+ (no hmmlearn needed).
    """

    def __init__(self):
        self.model = GaussianMixture(
            n_components     = CFG.hmm.n_states,
            covariance_type  = "full",
            n_init           = 5,
            max_iter         = 200,
            random_state     = CFG.hmm.random_state,
        )
        self.scaler    = StandardScaler()
        self.state_map = {}   # raw cluster → named state (0/1/2)
        self.features  = list(HMM_FEATURES)   # per-instance; overwritten by load()
        self.variant   = _VARIANT

    @staticmethod
    def _engineer(X):
        """Per-TF blocks [ADX, clarity, vol] -> [ADX, |clarity|, vol].
        Middle col is made DIRECTION-AGNOSTIC via abs(): needed for the 'spec'
        variant (signed DI_diff made the GMM cluster by up/down/flat); no-op for
        the 'rel' variant (di_eff is already >= 0). 2026-07-02 (Divyesh) v3."""
        X = np.asarray(X, dtype=float)
        if X.shape[1] == 8:                       # legacy [ADX, DI_diff]x4 — raw (original)
            return X.copy()
        out = np.empty_like(X)
        for b in range(4):                        # 4 TFs, blocks of [adx, clarity, vol]
            out[:, b*3]   = X[:, b*3]             # ADX
            out[:, b*3+1] = np.abs(X[:, b*3+1])   # di_clarity (|DI_diff| or di_eff)
            out[:, b*3+2] = X[:, b*3+2]           # volatility (band or band_rel)
        return out

    def fit(self, adx_df):
        """Train on ADX dataframe."""
        print(f"    HMM variant: {self.variant} | features: {self.features[:3]}... (x4 TF)")
        X_raw = adx_df[self.features].dropna().values
        # Bug 30 fix: guard against empty array — crash prevention
        # Can happen if: sparse training slice, corrupt CSV, all-NaN features
        if len(X_raw) < 30:
            raise ValueError(
                f"HMM fit failed: only {len(X_raw)} valid rows after dropna() "
                f"(minimum 30 required). Check ADX data for NaN/missing values."
            )
        X = self.scaler.fit_transform(self._engineer(X_raw))
        self.model.fit(X)

        # ── LEGACY (original 8-feature) labeling — restored for FIX-1 A/B ──
        if len(self.features) == 8:
            means   = self.scaler.inverse_transform(self.model.means_)
            avg_adx = means[:, 0]                 # M15_ADX
            avg_di  = np.abs(means[:, 1])         # |M15_DI_diff|
            sorted_by_adx = np.argsort(avg_adx)
            self.state_map[int(sorted_by_adx[0])] = 0          # lowest ADX = Ranging
            remaining = sorted_by_adx[1:]
            di_vals   = [avg_di[s] for s in remaining]
            self.state_map[int(remaining[int(np.argmax(di_vals))])] = 1  # high DI = Trending
            self.state_map[int(remaining[int(np.argmin(di_vals))])] = 2  # low DI  = Volatile
            labels = self.model.predict(X)
            for raw, named in self.state_map.items():
                pct = (labels == raw).mean() * 100
                print(f"    Cluster {raw} → {STATE_NAMES[named]:10s}: {pct:.1f}% "
                      f"(avg M15_ADX={avg_adx[raw]:.1f}, |DI_diff|={avg_di[raw]:.1f})")
            return self

        # 2026-07-02 (Divyesh) v3: label on [ADX, clarity, vol] cluster means,
        # averaged across all 4 TFs (more robust than M15-only).
        #   clarity = |DI_diff| (spec) or di_eff (rel) → how CLEAR the direction is
        #   vol     = band_width_pct (spec) or band_rel (rel) → ACTUAL volatility
        # Trending = clearest direction. Of the two low-clarity clusters:
        #   wide vol   → Volatile  (genuinely churny / wide-range)
        #   narrow vol → Ranging   (quiet/slow — NO LONGER mislabeled Volatile)
        means      = self.scaler.inverse_transform(self.model.means_)  # cols: [ADX, clarity, vol]*4
        avg_adx    = means[:, [0, 3, 6, 9]].mean(axis=1)
        di_clarity = means[:, [1, 4, 7, 10]].mean(axis=1)
        vol_width  = means[:, [2, 5, 8, 11]].mean(axis=1)

        trend_c = int(np.argmax(di_clarity))
        self.state_map[trend_c] = 1  # clearest direction = Trending
        remaining = [c for c in range(len(avg_adx)) if c != trend_c]
        if vol_width[remaining[0]] >= vol_width[remaining[1]]:
            self.state_map[int(remaining[0])] = 2  # wide vol   = Volatile
            self.state_map[int(remaining[1])] = 0  # narrow vol = Ranging
        else:
            self.state_map[int(remaining[1])] = 2
            self.state_map[int(remaining[0])] = 0

        # State distribution + cluster stats (VERIFY: Volatile vol HIGH, Ranging LOW)
        labels = self.model.predict(X)
        for raw, named in self.state_map.items():
            pct = (labels == raw).mean() * 100
            print(f"    Cluster {raw} → {STATE_NAMES[named]:10s}: {pct:.1f}% "
                  f"(ADX={avg_adx[raw]:.1f}, clarity={di_clarity[raw]:.1f}, "
                  f"vol={vol_width[raw]:.4f}, M15vol={means[raw, 2]:.4f})")

        return self

    def predict(self, adx_row: dict) -> int:
        """Predict market state for single row. Returns 0/1/2."""
        # v2 bug guard: silently defaulting missing features to 0 caused a
        # train/predict mismatch. Warn ONCE if the caller's dict is incomplete.
        missing = [f for f in self.features if f not in adx_row]
        if missing and not getattr(self, "_warned_missing", False):
            print(f"  ⚠ HMM predict: missing features {missing} → defaulting to 0. "
                  f"Check di_eff/band_rel/band_width_pct plumbing (features.py / adx data).")
            self._warned_missing = True
        x_raw = np.array([[adx_row.get(f, 0) for f in self.features]], dtype=float)
        # 2026-07-03 NaN guard: a NaN feature must NEVER kill the trading loop
        # (GaussianMixture raises on NaN). Fill neutral + warn once.
        if np.isnan(x_raw).any():
            if not getattr(self, "_warned_nan", False):
                bad = [f for f, v in zip(self.features, x_raw[0]) if np.isnan(v)]
                print(f"  ⚠ HMM predict: NaN in {bad} → neutral fill (0 / band_rel=1). "
                      f"Check live feature plumbing!")
                self._warned_nan = True
            for j, f in enumerate(self.features):
                if np.isnan(x_raw[0, j]):
                    x_raw[0, j] = 1.0 if f.endswith("band_rel") else 0.0
        x     = self.scaler.transform(self._engineer(x_raw))
        raw   = int(self.model.predict(x)[0])
        return self.state_map.get(raw, 0)

    def predict_state(self, feat_dict: dict) -> str:
        """Predict state name from feature dict. Returns 'Ranging'/'Trending'/'Volatile'."""
        state_int = self.predict(feat_dict)
        return STATE_NAMES.get(state_int, "Ranging")

    def predict_batch(self, adx_df) -> np.ndarray:
        """Predict states for full dataframe."""
        # NaN guard (2026-07-03): band_rel neutral is 1.0, everything else 0.
        _fill = {f: (1.0 if f.endswith("band_rel") else 0.0) for f in self.features}
        X_raw = adx_df[self.features].fillna(_fill).values
        X     = self.scaler.transform(self._engineer(X_raw))
        raw   = self.model.predict(X)
        return np.array([self.state_map.get(int(r), 0) for r in raw])

    def predict_proba(self, adx_row: dict) -> np.ndarray:
        """Return state probability vector (3,)."""
        x_raw = np.array([[adx_row.get(f, 0) for f in self.features]])
        x     = self.scaler.transform(self._engineer(x_raw))
        proba = self.model.predict_proba(x)[0]
        # Reorder to match state_map
        out = np.zeros(3)
        for raw, named in self.state_map.items():
            out[named] = proba[raw]
        return out

    def state_name(self, state: int) -> str:
        return STATE_NAMES.get(state, "Unknown")

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "model":     self.model,
            "scaler":    self.scaler,
            "state_map": self.state_map,
            "features":  self.features,   # v3: pkl carries its own feature list
            "variant":   self.variant,
        }, path)
        print(f"  Market state model saved → {path}")

    def load(self, path: str):
        data = joblib.load(path)
        if "model" not in data:
            raise KeyError(f"HMM file missing 'model' key: {path}")
        if "scaler" not in data:
            raise KeyError(f"HMM file missing 'scaler' key: {path}")
        if "state_map" not in data:
            raise KeyError(f"HMM file missing 'state_map' key: {path}")
        _model     = data["model"]
        _scaler    = data["scaler"]
        _state_map = data["state_map"]
        self.model     = _model
        self.scaler    = _scaler
        self.state_map = _state_map
        # v3: predict always uses the pkl's own feature list (env-var-proof).
        if "features" in data:
            self.features = list(data["features"])
            self.variant  = data.get("variant", "?")
        else:
            print(f"  ⚠ Old HMM pkl (no feature list) — assuming current "
                  f"HMM_FEATURES ({_VARIANT}). Retrain to embed features.")
            self.features = list(HMM_FEATURES)
        print(f"  Market state model loaded ← {path} "
              f"(variant={getattr(self, 'variant', '?')})")
        return self
