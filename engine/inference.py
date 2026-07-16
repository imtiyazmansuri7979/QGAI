"""
inference.py
─────────────
Live signal engine — loads all models and produces
a trade signal for each new M15 candle.

Also handles:
  - Online learning update after each closed trade
  - Drift detection
  - Auto-retrain trigger

Usage (standalone test):
    python inference.py

MT5 bridge calls get_signal() for each candle.
"""

import hashlib
import json
import os
import numpy as np
import pandas as pd
import joblib
import csv
from pathlib import Path
from datetime import datetime

from config import CFG


# ══════════════════════════════════════════════════════════════════════
# TREND-FOLLOWING PULLBACK ENTRY GATE (ET1, 2026-07-03)
# Shared by LIVE (bridge_main) and BACKTEST (backtest_replay) → parity by
# construction. Pure function of the signal dict (all last-closed ts_*
# features, no lookahead). Sweep A = deterministic gate, ML-veto OFF.
# ══════════════════════════════════════════════════════════════════════
def _pb_param(env_key, cfg_val):
    """Env override (for the per-combo sweep) → else config value."""
    v = os.environ.get(env_key)
    if v is None or v == "":
        return cfg_val
    try:
        return float(v)
    except (TypeError, ValueError):
        return cfg_val


def _pullback_ok(sig, d, cfg=CFG):
    """Core trend-following pullback conditions for direction d (+1 BUY / -1 SELL).
    Returns (ok: bool, reason: str). ok=True → a valid pullback entry for d.
    SINGLE source of truth — both the BLOCK (filter ML signals) and the GENERATE
    (create early entries) modes call this, so live/backtest stay identical.
    DIRECTION (leading): HTF ADX-switch trend matches d, HTF agreement ≥ min in d,
      ADX rising. TIMING (anti-chase, ATR-free) via ts_line_dist_pct=(price-line)/price*100:
      sdist=d*dist ; sdist<0 not reclaimed ; sdist>chase_max chased ; established trend
      & sdist>pb_near not pulled back ; fresh flip → allowed up to chase_max."""
    agree  = float(sig.get("ts_htf_agreement", 0) or 0)      # -3..+3
    switch = float(sig.get("ts_adx_switch_trend", 0) or 0)   # +1 / -1
    h1s    = float(sig.get("h1_adx_slope", 0) or 0)
    h4s    = float(sig.get("h4_adx_slope", 0) or 0)
    amin   = float(_pb_param("QGAI_PB_AGREE", getattr(cfg.filters, "htf_agreement_min", 3)))

    if switch != d:
        return (False, "pb: HTF trend not in trade direction")
    if d * agree < amin:
        return (False, f"pb: HTF agreement {agree:+.0f} < {d*amin:+.0f}")
    if h1s <= 0 and h4s <= 0:
        return (False, "pb: ADX not rising (trend fading)")

    dist  = float(sig.get("ts_line_dist_pct", 0) or 0)       # signed (price-line)/price*100
    sdist = d * dist                                          # >0 = extended on trade side
    pb_near   = float(_pb_param("QGAI_PB_NEAR",  getattr(cfg.filters, "pb_near_pct",   0.075)))
    chase_max = float(_pb_param("QGAI_PB_CHASE", getattr(cfg.filters, "chase_max_pct", 0.25)))

    if sdist < 0:
        return (False, f"pb: not reclaimed (dist {sdist:.3f}%)")
    if sdist > chase_max:
        return (False, f"pb: chase — extended {sdist:.3f}% > {chase_max:.3f}%")
    fresh = float(sig.get("ts_flip_recent", 0) or 0) >= 1.0
    if not fresh and sdist > pb_near:
        return (False, f"pb: established trend, not pulled back ({sdist:.3f}% > {pb_near:.3f}%)")
    return (True, "")


def trend_pullback_block(sig, cfg=CFG):
    """BLOCK mode (v1): veto an ML BUY/SELL that is NOT a valid pullback entry.
    Returns (block, reason). (False, "") when the flag is OFF or signal isn't BUY/SELL."""
    on = _pb_param("QGAI_PB_ENTRY", 1.0 if getattr(cfg.filters, "trend_pullback_entry", False) else 0.0)
    if float(on) < 0.5:
        return (False, "")
    signal = sig.get("signal")
    if signal not in ("BUY", "SELL"):
        return (False, "")
    d = 1 if signal == "BUY" else -1
    ok, reason = _pullback_ok(sig, d, cfg)
    return (not ok, reason)


def trend_pullback_generate(sig, cfg=CFG):
    """GENERATE mode (v2, the real fix): CREATE an early entry in the dominant HTF
    trend direction when price pulls back to the ratchet line — regardless of the
    (late) ML win_prob. Returns "BUY"/"SELL" to enter, or None. Uses the SAME
    _pullback_ok conditions as the block. Direction = ts_adx_switch_trend (dominant TF).
    `sig` = any result dict (ts_*/ADX market features are direction-independent)."""
    on = _pb_param("QGAI_PB_GEN", 1.0 if getattr(cfg.filters, "trend_pullback_generate", False) else 0.0)
    if float(on) < 0.5:
        return None
    switch = float(sig.get("ts_adx_switch_trend", 0) or 0)   # +1 / -1 / 0
    if switch == 0:
        return None
    d = 1 if switch > 0 else -1
    ok, _ = _pullback_ok(sig, d, cfg)
    return ("BUY" if d > 0 else "SELL") if ok else None


def _fnum(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def smma_mtf_soft_block(sig, base_threshold, cfg=CFG):
    """SMMA MTF soft gate (2026-07-06, research-confirmed +51R live baseline / +27R Combo,
    4/4 quarters OOS win). LINEAR mode only (only mode wired live). Raises the win_prob
    threshold when M15/H1/H4 SMMA-2 trends aren't aligned with the trade direction.
    Returns (block, reason, meta). meta has score/required_threshold/penalty for logging.
    Lookahead-free (last-closed ts_trend_*). No-op when cfg.filters.smma_mtf_soft=False."""
    signal = sig.get("signal")
    meta = {"score": 0.0, "penalty": 0.0, "required_threshold": float(base_threshold),
            "base_threshold": float(base_threshold), "aligned_count": 0,
            "m15_aligned": 0, "h1_aligned": 0, "h4_aligned": 0}
    on = os.environ.get("QGAI_SMMA_MTF")
    if on:
        on = float(on) >= 0.5
    else:
        on = bool(getattr(cfg.filters, "smma_mtf_soft", False))
    if not on:
        return (False, "", meta)
    if signal not in ("BUY", "SELL"):
        return (False, "", meta)
    d = 1.0 if signal == "BUY" else -1.0
    w_m15 = float(getattr(cfg.filters, "smma_weight_m15", 0.25))
    w_h1  = float(getattr(cfg.filters, "smma_weight_h1",  0.35))
    w_h4  = float(getattr(cfg.filters, "smma_weight_h4",  0.40))
    total_w = max(w_m15, 0.0) + max(w_h1, 0.0) + max(w_h4, 0.0) or 1.0
    a_m15 = 1 if _fnum(sig.get("ts_trend_m15", 0)) * d > 0 else 0
    a_h1  = 1 if _fnum(sig.get("ts_trend_h1",  0)) * d > 0 else 0
    a_h4  = 1 if _fnum(sig.get("ts_trend_h4",  0)) * d > 0 else 0
    score = 100.0 * (w_m15 * a_m15 + w_h1 * a_h1 + w_h4 * a_h4) / total_w
    target = max(float(getattr(cfg.filters, "smma_linear_target", 70.0)), 0.0001)
    maxpen = max(float(getattr(cfg.filters, "smma_max_penalty",   0.06)), 0.0)
    penalty = min(maxpen, maxpen * max(target - score, 0.0) / target)
    required = float(base_threshold) + penalty
    meta.update({"score": round(score, 2), "penalty": round(penalty, 4),
                 "required_threshold": round(required, 4),
                 "aligned_count": a_m15 + a_h1 + a_h4,
                 "m15_aligned": a_m15, "h1_aligned": a_h1, "h4_aligned": a_h4})
    prob = _fnum(sig.get("win_prob", 0.0))
    if required > float(base_threshold) and prob < required:
        return (True,
                f"smma mtf soft: score {score:.0f}/100; prob {prob:.2%} < raised threshold {required:.2%}",
                meta)
    return (False, "", meta)


def adx_strength_soft_block(sig, base_threshold, cfg=CFG):
    """Fable-5 REDESIGN (2026-07-07): direction-agnostic ADX STRENGTH gate.
    Old ADX6 formula was mislabeled (margin=d*DI_diff cancelled ADX/slope).
    This version uses H1/H4 ADX LEVEL + positive slope only — no direction terms.
    Complements smma_mtf_soft_block (which handles direction alignment).
    Same shape: (block, reason, meta). No-op when cfg.filters.adx_strength_soft=False."""
    meta = {"score": 0.0, "penalty": 0.0,
            "required_threshold": float(base_threshold),
            "base_threshold": float(base_threshold),
            "lvl_h1": 0.0, "lvl_h4": 0.0, "slp_h1": 0.0, "slp_h4": 0.0}
    on = os.environ.get("QGAI_ADX_STRENGTH")
    if on:
        on = float(on) >= 0.5
    else:
        on = bool(getattr(cfg.filters, "adx_strength_soft", False))
    if not on or sig.get("signal") not in ("BUY", "SELL"):
        return (False, "", meta)
    lo  = float(getattr(cfg.filters, "adx_strength_lo", 15.0))
    hi  = float(getattr(cfg.filters, "adx_strength_hi", 35.0))
    sdv = max(float(getattr(cfg.filters, "adx_strength_slope_div", 1.5)), 0.0001)
    lvl_h1 = min(max((_fnum(sig.get("H1_ADX", 0)) - lo) / max(hi - lo, 0.0001), 0.0), 1.0)
    lvl_h4 = min(max((_fnum(sig.get("H4_ADX", 0)) - lo) / max(hi - lo, 0.0001), 0.0), 1.0)
    slp_h1 = min(max(_fnum(sig.get("h1_adx_slope", 0)) / sdv, 0.0), 1.0)
    slp_h4 = min(max(_fnum(sig.get("h4_adx_slope", 0)) / sdv, 0.0), 1.0)
    score = 100.0 * min(0.35 * lvl_h1 + 0.40 * lvl_h4 + 0.10 * slp_h1 + 0.15 * slp_h4, 1.0)
    target = max(float(getattr(cfg.filters, "adx_strength_linear_target", 55.0)), 0.0001)
    maxpen = max(float(getattr(cfg.filters, "adx_strength_max_penalty", 0.04)), 0.0)
    penalty = min(maxpen, maxpen * max(target - score, 0.0) / target)
    required = float(base_threshold) + penalty
    meta.update({"score": round(score, 2), "penalty": round(penalty, 4),
                 "required_threshold": round(required, 4),
                 "lvl_h1": round(lvl_h1, 3), "lvl_h4": round(lvl_h4, 3),
                 "slp_h1": round(slp_h1, 3), "slp_h4": round(slp_h4, 3)})
    prob = _fnum(sig.get("win_prob", 0.0))
    if required > float(base_threshold) and prob < required:
        return (True,
                f"adx strength soft: score {score:.0f}/100; prob {prob:.2%} < raised threshold {required:.2%}",
                meta)
    return (False, "", meta)


from features import (compute_features, load_ohlc, load_adx,
                      load_news, build_h4_range_table,
                      build_ob_table,
                      FEATURE_COLS, STATE_FEATURE_MAP)
from hmm_model import MarketStateHMM
from xgb_model import WinProbabilityModel
from prediction_model import BigWinPredictor, DurationPredictor, get_dynamic_tp_sl
try:
    from self_learning import OnlineLearner, DriftDetector, PeriodicRetrainer
    ONLINE_LEARNING = True
except ImportError:
    OnlineLearner = None
    DriftDetector = None
    PeriodicRetrainer = None
    ONLINE_LEARNING = False
    print("  ⚠️  self_learning/river not available — online learning disabled")


class LiveInferenceEngine:
    """
    Main engine for live trading.
    Call get_signal() for each new M15 candle.
    Call on_trade_closed() when a trade closes.
    """

    def __init__(self):
        cfg = CFG.paths
        print("\n  Loading models...")

        # ── safe_load helper — 3-layer protection ────────────
        # Layer 1: fresh object per call — no partial-state corruption
        # Layer 2: return value captured — works regardless of load() style
        # Layer 3: post-load validation — dummy predict ensures usable
        def safe_load(model_class, path, label="model"):
            p = Path(path)
            if not p.exists():
                print(f"  ❌ Missing {label}: {p.name} — run python train.py")
                return None
            try:
                # Fresh object — isolated from any prior state
                obj    = model_class()
                result = obj.load(str(p))
                # Use whichever is the loaded object
                target = result if result is not None else obj

                # Post-load validation — can it actually predict?
                _n = len(target.feature_names) if getattr(target, "feature_names", None) else 60
                _x = np.zeros(_n, dtype=np.float32)
                target.predict_win_prob(_x)

                print(f"  ✅ {label} loaded + verified")
                return target
            except Exception as e:
                print(f"  ❌ {label} load/verify failed: {e}")
                return None   # clean None — partial object never returned

        # ── safe_load_pred: for BigWin / Duration (predict_prob not predict_win_prob) ──
        def safe_load_pred(model_class, path, label="model"):
            p = Path(path)
            if not p.exists():
                print(f"  ❌ Missing {label}: {p.name} — run python train.py")
                return None
            try:
                obj    = model_class()
                result = obj.load(str(p))
                target = result if result is not None else obj
                # Validate
                _n = 60
                _x = np.zeros(_n, dtype=np.float32)
                target.predict_prob(_x)
                print(f"  ✅ {label} loaded + verified")
                return target
            except Exception as e:
                print(f"  ❌ {label} load/verify failed: {e}")
                return None

        # ── safe_load_hmm: HMM uses predict(dict) not predict_win_prob ──
        def safe_load_hmm(path, label="HMM"):
            p = Path(path)
            if not p.exists():
                print(f"  ❌ Missing {label}: {p.name} — run python train.py")
                return None
            try:
                obj    = MarketStateHMM()
                result = obj.load(str(p))
                target = result if result is not None else obj
                # Validate with dummy ADX row — 2026-07-03: use the MODEL'S OWN
                # feature list (the old hardcoded 8-key dict fired the
                # missing-features warning on every v3 load; band_rel neutral=1).
                _dummy = {k: (1.0 if k.endswith("band_rel") else 0.0)
                          for k in getattr(target, "features", [])}
                target.predict(_dummy)
                print(f"  ✅ {label} loaded + verified")
                return target
            except Exception as e:
                print(f"  ❌ {label} load/verify failed: {e}")
                return None

        # Load core models — CRITICAL (None = system disabled)
        self.hmm = safe_load_hmm(f"{cfg.models_dir}/hmm_model.pkl",  "HMM")
        self.xgb = safe_load(WinProbabilityModel, f"{cfg.models_dir}/xgb_model.pkl",  "XGB ensemble")
        if self.hmm is None or self.xgb is None:
            raise RuntimeError("❌ Critical models missing — run: python train.py")

        # ── model_version (2026-07-13, signal-audit fix #1) ───────────────
        # Every signal logged from here on carries this identifier (see
        # _make_result + bridge_data.log_signal) so a past signal can always
        # be traced back to the EXACT model snapshot that produced it — an
        # audit of the 2026-07-13 04:30 BUY signal hit a dead end trying to
        # reproduce the exact logged probability because the live model had
        # moved on and the in-progress snapshot wasn't recoverable.
        try:
            _mm = json.load(open(f"{cfg.models_dir}/model_meta.json", encoding="utf-8"))
            self.model_version = f"{_mm.get('model_created_at') or _mm.get('timestamp') or '?'}_{_mm.get('data_hash') or '?'}"
        except Exception:
            self.model_version = "unknown"
        try:
            _model_path = Path(cfg.models_dir) / "xgb_model.pkl"
            self.model_file_name = _model_path.name
            self.model_hash = hashlib.sha256(_model_path.read_bytes()).hexdigest()[:16]
        except Exception:
            self.model_file_name = "xgb_model.pkl"
            self.model_hash = "unknown"

        # Load directional BUY/SELL models — optional
        self.xgb_buy  = safe_load(WinProbabilityModel, f"{cfg.models_dir}/buy_model.pkl",  "BUY model")
        self.xgb_sell = safe_load(WinProbabilityModel, f"{cfg.models_dir}/sell_model.pkl", "SELL model")
        if self.xgb_buy and self.xgb_sell:
            print("  Directional models loaded: buy_model + sell_model")
        else:
            self.xgb_buy  = None
            self.xgb_sell = None
            print("  Directional models: NOT found — using combined model (run train.py)")

        # Load state-specific models — optional
        self.xgb_state = {}
        for state_name in ["ranging", "trending", "volatile"]:
            m = safe_load(WinProbabilityModel, f"{cfg.models_dir}/model_{state_name}.pkl", f"{state_name} model")
            if m is not None:
                self.xgb_state[state_name] = m
        if self.xgb_state:
            print(f"  State models loaded: {list(self.xgb_state.keys())} ✅")
        else:
            print("  State models: NOT found — using combined model")

        # Load news-specific models — optional
        self.xgb_normal = None
        self.xgb_news   = None
        norm_path = Path(cfg.models_dir) / "model_normal.pkl"
        news_path = Path(cfg.models_dir) / "model_news.pkl"
        self.xgb_normal = safe_load(WinProbabilityModel, str(norm_path), "normal model") if norm_path.exists() else None
        self.xgb_news   = safe_load(WinProbabilityModel, str(news_path), "news model")   if news_path.exists() else None
        if self.xgb_normal and self.xgb_news:
            print(f"  News models loaded: model_normal + model_news ✅")
        else:
            print(f"  News models: NOT found — using combined model (run train.py)")

        # Online learning — only if river is installed
        if ONLINE_LEARNING:
            self.online    = None
            self.drift     = None
            if OnlineLearner and Path(f"{cfg.models_dir}/online_model.pkl").exists():
                try:
                    _ol = OnlineLearner()
                    _ol.load(f"{cfg.models_dir}/online_model.pkl")
                    self.online = _ol
                    print(f"  Online model loaded ← {cfg.models_dir}/online_model.pkl ✅")
                except Exception as e:
                    print(f"  ⚠️ Online model skipped: {e}")
            if DriftDetector and Path(f"{cfg.models_dir}/drift_detector.pkl").exists():
                try:
                    _dd = DriftDetector()
                    _dd.load(f"{cfg.models_dir}/drift_detector.pkl")
                    self.drift = _dd
                except Exception as e:
                    print(f"  ⚠️ Drift detector skipped: {e}")
            self.retrainer = PeriodicRetrainer()
        else:
            self.online    = None
            self.drift     = None
            self.retrainer = None
            print(f"  Online learning: DISABLED (river not installed)")
        _slot_path = Path(cfg.models_dir) / "slot_table.pkl"
        self.slot_tbl = joblib.load(str(_slot_path)) if _slot_path.exists() else None
        if self.slot_tbl is None:
            print("  ⚠️ slot_table.pkl not found — slot_win_rate feature will be 0")

        # Bug #1 fix: Load BigWin + Duration prediction models
        big_path = Path(cfg.models_dir) / "big_win_model.pkl"
        dur_path = Path(cfg.models_dir) / "duration_model.pkl"
        self.big_predictor = BigWinPredictor().load(str(big_path)) if big_path.exists() else None
        self.dur_predictor = DurationPredictor().load(str(dur_path)) if dur_path.exists() else None
        # M1: Move-size quantile models (info-only) — predict MFE in ATR units
        # over the next 12 bars. Trained by train_move_model.py. Missing = off.
        self.move_models = {}
        self.sl_models = {}
        for _d in ("buy", "sell"):
            for _q in (25, 50, 75):
                _mp = Path(cfg.models_dir) / f"move_model_{_d}_q{_q}.pkl"
                if _mp.exists():
                    try:
                        self.move_models[(_d, _q)] = joblib.load(str(_mp))
                    except Exception as _e:
                        print(f"  ⚠️ move_model_{_d}_q{_q} load failed: {_e}")
            # M2: adverse-move (MAE) models for predicted SL / trailing
            for _q in (50, 75):
                _sp = Path(cfg.models_dir) / f"sl_model_{_d}_q{_q}.pkl"
                if _sp.exists():
                    try:
                        self.sl_models[(_d, _q)] = joblib.load(str(_sp))
                    except Exception as _e:
                        print(f"  ⚠️ sl_model_{_d}_q{_q} load failed: {_e}")
        if self.move_models:
            print(f"  Move-size models loaded: {len(self.move_models)}/6 ✅"
                  + (f" | SL models: {len(self.sl_models)}/4 ✅" if self.sl_models else ""))
        if self.big_predictor and self.dur_predictor:
            print("  Prediction models loaded: BigWin + Duration ✅")
        else:
            print("  Prediction models: NOT found (BigWin/Duration disabled)")

        # Load data files for live feature computation
        print("  Loading data files for live inference...")

        # ── Data file existence check ─────────────────────────
        for label, path in [("OHLC", cfg.ohlc_file), ("ADX", cfg.adx_file), ("News", cfg.news_file)]:
            if not Path(path).exists():
                raise FileNotFoundError(f"❌ {label} data file missing: {path}\n"
                                        f"   Run: python merge_data.py")

        self.ohlc_df  = load_ohlc(cfg.ohlc_file)
        self.adx_df   = load_adx(cfg.adx_file)
        self.news_df  = load_news(cfg.news_file)

        # ── Data validation ───────────────────────────────────
        # 1. Empty check
        if self.ohlc_df.empty:
            raise ValueError("❌ OHLC data is empty — run: python merge_data.py")
        if self.adx_df.empty:
            raise ValueError("❌ ADX data is empty — run: python merge_data.py")

        # 2. Size sanity check (must have reasonable history)
        MIN_OHLC_ROWS = 1000
        if len(self.ohlc_df) < MIN_OHLC_ROWS:
            raise ValueError(f"❌ OHLC too few rows ({len(self.ohlc_df)} < {MIN_OHLC_ROWS}) — corrupted data?")

        # 3. Date range check — data must be recent
        import pandas as _pd
        ohlc_last = self.ohlc_df["datetime"].max()
        days_stale = (_pd.Timestamp.now() - ohlc_last).days
        if days_stale > 30:
            print(f"  ⚠️  OHLC data is {days_stale} days old (last: {ohlc_last.date()}) — run fill_data_gap.py")
        else:
            print(f"  OHLC   : {len(self.ohlc_df):,} rows | last: {ohlc_last.date()} ({days_stale}d ago) ✅")

        # 4. ADX row count check — ADX may have more rows than OHLC (normal after merge)
        ohlc_n = len(self.ohlc_df)
        adx_n  = len(self.adx_df)
        adx_pct_diff = abs(ohlc_n - adx_n) / ohlc_n * 100
        if adx_pct_diff > 70:  # only warn if very large difference
            print(f"  ⚠️  ADX/OHLC mismatch: OHLC={ohlc_n:,} ADX={adx_n:,} ({adx_pct_diff:.1f}% diff)")
        else:
            print(f"  ADX    : {adx_n:,} rows ✅")

        print("  Building H4 tables...")
        self.h4_df    = build_h4_range_table(self.ohlc_df)
        self.h1_ob    = build_ob_table(self.ohlc_df, "1h")
        self.h4_ob_df = build_ob_table(self.ohlc_df, "4h")
        print(f"  H4 range   : {len(self.h4_df):,} candles ✅")
        print(f"  H1 OB table: {self.h1_ob['bull_ob'].sum()} bull | {self.h1_ob['bear_ob'].sum()} bear ✅")
        print(f"  H4 OB table: {self.h4_ob_df['bull_ob'].sum()} bull | {self.h4_ob_df['bear_ob'].sum()} bear ✅")

        # Daily Loss Tracker — Dynamic (based on day-open capital)
        self._today              = None
        self._daily_loss         = 0.0
        self._daily_sl_hit       = False
        # NOTE: -1.0 = sentinel (not set yet)
        # Bridge MUST call update_capital(equity) after MT5 connect
        # Trading is BLOCKED until update_capital() is called
        self._account_capital    = -1.0   # sentinel — NOT hardcoded!
        self._capital_set        = False  # guard flag
        # Blend tracking — initialized so first call never uses getattr fallback
        self._last_state_prob    = 0.0
        self._last_dir_prob      = 0.0
        self._last_vol_regime    = "normal"
        self._last_big_prob      = 0.0
        self._last_dur_prob      = 0.0
        self._last_dyn           = {}
        # ── Signal cache — avoids redundant computation same bar ──
        self._cache_timestamp    = None   # last computed timestamp
        self._cache_buy          = None   # cached BUY result
        self._cache_sell         = None   # cached SELL result
        self._day_open_capital   = -1.0   # set on first day reset

        # Live trade log
        self.live_log = Path(cfg.live_log)
        self.live_log.parent.mkdir(parents=True, exist_ok=True)

        # ── FAILSAFE: ensure at least one prediction model is loaded ──
        has_model = any([
            self.xgb is not None,
            bool(self.xgb_state),
            self.xgb_buy is not None,
            self.xgb_sell is not None,
            self.xgb_normal is not None,
            self.xgb_news is not None,
        ])
        if not has_model:
            raise RuntimeError(
                "❌ NO prediction model loaded — system cannot trade!\n"
                "   Run: python train.py\n"
                "   Then restart: startup.bat"
            )

        # Summary of loaded models
        loaded = []
        if self.xgb:          loaded.append("combined")
        if self.xgb_state:    loaded.append(f"state({','.join(self.xgb_state.keys())})")
        if self.xgb_buy:      loaded.append("buy")
        if self.xgb_sell:     loaded.append("sell")
        if self.xgb_normal:   loaded.append("normal")
        if self.xgb_news:     loaded.append("news")
        if self.online:        loaded.append("online")
        print(f"  Models active: {' | '.join(loaded)}")
        print("  ✅ Inference engine ready!\n")

    def get_signal(self,
                   timestamp:   pd.Timestamp,
                   trade_type:  str,
                   volume:      float = 0.1,
                   ohlc_update: pd.DataFrame = None,
                   adx_update:  pd.DataFrame = None,
                   news_update: pd.DataFrame = None,
                   ) -> dict:
        """
        Main entry point — call for each M15 candle.

        Parameters:
            timestamp   : current candle datetime (UTC+3)
            trade_type  : "BUY" or "SELL" (from your strategy)
            volume      : lot size
            *_update    : optional fresh data (if MT5 sends new rows)

        Returns dict with:
            signal      : "BUY" / "SELL" / "SKIP"
            win_prob    : calibrated probability (0-1)
            sl_mult     : SL multiplier
            hmm_state   : market state name
            reason      : why signal or skip
        """
        # Safety init — prevents UnboundLocalError on early returns
        feat_dict = {}
        # Update data if new rows provided
        if ohlc_update is not None:
            # FIX #22: live OHLC from the bridge has a "time" column but
            # this dataframe is keyed on "datetime". The old
            # drop_duplicates("datetime") collapsed ALL live rows (NaN
            # datetime) into one useless row — live bars were effectively
            # DISCARDED and signals ran on the startup CSV only.
            # Now: normalize to "datetime", merge base columns, and
            # re-engineer with the SAME pipeline as training data.
            try:
                from features import engineer_ohlc as _eng_ohlc
                _upd = ohlc_update.copy()
                if "datetime" not in _upd.columns and "time" in _upd.columns:
                    _upd["datetime"] = pd.to_datetime(_upd["time"])
                if "tick_volume" not in _upd.columns and "volume" in _upd.columns:
                    _upd["tick_volume"] = _upd["volume"]
                _base = ["datetime", "open", "high", "low", "close", "tick_volume"]
                _upd  = _upd[[c for c in _base if c in _upd.columns]]

                _prev_len  = len(self.ohlc_df)
                _last_dt   = self.ohlc_df["datetime"].max() if _prev_len else None
                _hist_base = self.ohlc_df[[c for c in _base if c in self.ohlc_df.columns]]
                # 2026-07-01: some callers (e.g. bridge_main._overnight_replay / _pre_pop_dashboard)
                # intentionally pass the SAME fetched ohlc_update object across many get_signal()
                # calls (looping only the `timestamp` arg over historical bars) — that is correct,
                # not staleness. Only run the staleness tracker below when the INCOMING update
                # itself is actually new vs the previous call, so replay/backfill loops don't spam
                # false alarms (caught live 2026-07-01: 100 false alarms in <1s during overnight replay).
                _upd_last_incoming = _upd["datetime"].max() if len(_upd) else None
                _is_new_incoming_update = (_upd_last_incoming != getattr(self, "_last_seen_upd_ts", None))
                self._last_seen_upd_ts = _upd_last_incoming
                _merged = (pd.concat([_hist_base, _upd])
                           .drop_duplicates("datetime", keep="last")
                           .sort_values("datetime")
                           .reset_index(drop=True)
                           .tail(50000))
                _new_last = _merged["datetime"].max()
                # Re-engineer only when content actually changed
                if len(_merged) != _prev_len or _new_last != _last_dt:
                    self.ohlc_df = _eng_ohlc(_merged)
                    # Rebuild OB + H4 range tables when new OHLC data arrives
                    # These tables must stay current — stale OBs give wrong distances
                    try:
                        self.h4_df    = build_h4_range_table(self.ohlc_df)
                        self.h1_ob    = build_ob_table(self.ohlc_df, "1h")
                        self.h4_ob_df = build_ob_table(self.ohlc_df, "4h")
                    except Exception as _e:
                        pass  # keep old tables if rebuild fails
                    self._ohlc_stale_bars = 0  # fresh candle landed — reset the staleness counter
                elif _is_new_incoming_update:
                    # 2026-07-01: STALENESS ALARM — the CALLER brought genuinely new data (a fresh
                    # MT5 pull, different from last call) but nothing new merged in. If this repeats
                    # across consecutive live bars, self.ohlc_df (and every feature/win_prob derived
                    # from it) is FROZEN even though price keeps moving — caught live 2026-07-01
                    # (win_prob stuck at 26.99% for 75+ min, 6 consecutive bars, before this fix).
                    self._ohlc_stale_bars = getattr(self, "_ohlc_stale_bars", 0) + 1
                    if self._ohlc_stale_bars >= 2:
                        try:
                            import logging as _lg
                            _lg.getLogger("QGAI").error(
                                f"⚠️ OHLC feed NOT advancing — {self._ohlc_stale_bars} consecutive "
                                f"bars with no new closed candle merged (last known: {_last_dt}). "
                                f"win_prob/features are STALE — restart the bridge if this persists.")
                        except Exception:
                            pass
                # else: caller replayed the same snapshot again (backfill/replay loop) — expected, no-op.
            except Exception as _me:
                # 2026-07-01 fix: this was a bare print() — invisible in bridge.log (only
                # [INFO]/[WARNING]/[ERROR] logger lines are captured there), so a merge
                # failure could silently freeze self.ohlc_df for as long as it kept happening
                # with no trace in the log. Now also routed through the "QGAI" logger.
                print(f"  ⚠️ Live OHLC merge failed: {_me} — using existing data")
                try:
                    import logging as _lg
                    _lg.getLogger("QGAI").error(f"⚠️ Live OHLC merge failed: {_me} — using existing (STALE) data")
                except Exception:
                    pass

        # ── LATENCY CACHE — same bar, same direction → return cached ──
        # Bridge calls get_signal(BUY) then get_signal(SELL) per bar
        # Features/HMM are identical for same bar — no need to recompute
        _direction = trade_type.upper()
        # FIX #2: NEW BAR → invalidate BOTH direction caches.
        # Without this, _cache_sell could still hold the PREVIOUS bar's
        # result: if BUY confirms first on the new bar it sets
        # _cache_timestamp, then the SELL call would return a STALE
        # result from the old bar — the bridge could trade on it.
        if timestamp != self._cache_timestamp:
            self._cache_buy  = None
            self._cache_sell = None
        if timestamp == self._cache_timestamp:
            _cached = self._cache_buy if _direction == "BUY" else self._cache_sell
            if _cached is not None:
                return _cached  # ← instant return, no pandas work
        if adx_update is not None:
            # FIX #22b: live ADX rows had NO "datetime" column at all —
            # they were collapsed/dropped by drop_duplicates("datetime")
            # and never reached the features. Bridge now sends datetime;
            # guard here in case it's missing.
            try:
                _au = adx_update.copy()
                if "datetime" not in _au.columns:
                    _au["datetime"] = pd.Timestamp(timestamp)
                self.adx_df = (pd.concat([self.adx_df, _au])
                               .drop_duplicates("datetime", keep="last")
                               .sort_values("datetime")
                               .reset_index(drop=True).tail(20000))
            except Exception as _ae:
                print(f"  ⚠️ Live ADX merge failed: {_ae}")
        if news_update is not None:
            self.news_df = pd.concat([self.news_df,  news_update]).drop_duplicates("datetime").sort_values("datetime").reset_index(drop=True).tail(10000)

        # ── Daily Loss Limit Check ───────────────────────────
        today = timestamp.date()
        if self._today != today:
            # New day — reset tracker. FIX 2026-06-14: do NOT freeze
            # day_open_capital from stale equity here. Clear it (-1) so the
            # next update_capital(equity) call sets it from TODAY's opening
            # equity. In backtest (no async update) we set it immediately
            # from current capital since that IS today's equity.
            self._today              = today
            self._daily_loss         = 0.0
            self._daily_sl_hit       = False
            self._day_open_capital   = -1.0
            if self._capital_set and self._account_capital > 0:
                # backtest path: capital is already today's equity
                self._day_open_capital = self._account_capital

        # ── CAPITAL GUARD — block trading if capital not set ──
        if not self._capital_set:
            return self._make_result(
                "SKIP", 0.0, 0, "N/A",
                "❌ Capital not set — bridge must call update_capital(equity) first",
                {}
            )

        # C9 fix: inference daily SL check kept as safety net only
        # Primary daily SL control is in mt5_bridge.py — this is secondary backup
        if CFG.filters.enable_daily_sl and self._daily_sl_hit:
            return self._make_result(
                "SKIP", 0.0, 0, "N/A",
                f"Daily SL hit (inference guard) — trading closed for today! "
                f"(Lost ${self._daily_loss:.2f} / limit "
                f"${self._day_open_capital * CFG.filters.daily_loss_limit_pct/100:.2f})",
                {}
            )

        # ── Time window filter REMOVED ───────────────────────
        # Slot+Day filter (145 profitable combos, 24hrs) handles
        # all time filtering. NY session hard filter was blocking
        # $11,415 of proven profitable trades outside 16:00-18:45.
        # Slot+Day filter is applied in mt5_bridge.py before calling
        # get_signal() — so no additional time check needed here.

        # ── Compute the model feature set (count = len(FEATURE_COLS)) ─────────
        feat_dict = compute_features(
            t          = timestamp,
            trade_type = trade_type,
            volume     = volume,
            ohlc_df    = self.ohlc_df,
            adx_df     = self.adx_df,
            news_df    = self.news_df,
            slot_table = self.slot_tbl,
            h4_df      = self.h4_df,
            h1_ob      = self.h1_ob,
            h4_ob_df   = self.h4_ob_df,
        )

        # ── HMM state ─────────────────────────────────────────
        # 2026-07-02 (Divyesh) HMM v3: build from the LOADED model's own feature
        # list (stored in the pkl) so the key list can never drift from the model
        # again (v2 bug: PlusDI/MinusDI defaulted to 0 at predict time).
        adx_row = {k: feat_dict.get(k, 0) for k in self.hmm.features}
        hmm_state      = self.hmm.predict(adx_row)
        hmm_state_name = self.hmm.state_name(hmm_state)

        # ── Inject hmm_state into feat_dict so models can find it ──
        feat_dict["hmm_state"] = hmm_state

        # ── REGIME-AWARE in_range_phase (2026-07-12, Imtiyaz) ──────────────
        # 1-month threshold sweep found the OPTIMAL |H4 move| cutoff differs
        # by regime: Trending peaks at 0.5% (+5.2R), Volatile peaks at 0.6%
        # (+8.5R), Ranging noisy/small-sample (kept at default). A single
        # global cutoff (0.5%) hides this trade-off. h4_move_pct (raw, always
        # computed in get_range_features) lets us recompute the binary AFTER
        # the regime is known — applied to BOTH live and backtest since both
        # go through this SAME LiveInferenceEngine.decide(). Master toggle:
        # env QGAI_REGIME_INRANGE=0 disables (falls back to the original
        # global-0.5% in_range_phase from compute_features). Default ON.
        # 🔒 2026-07-16 — a same-session "fix" briefly flipped this default to
        # OFF, reasoning that live serving a regime-aware value while
        # `train.py` trains on a flat 0.5% cutoff (train.py calls
        # compute_features() directly, never through decide()) was an
        # unintended train/serve skew. REVERTED same day (Imtiyaz): this
        # train/serve difference was already known and deliberately accepted
        # when this feature was built 2026-07-12 — not a bug. Do not flip
        # this default again without confirming first.
        if os.environ.get("QGAI_REGIME_INRANGE", "1") != "0":
            _REGIME_INRANGE_THRESH = {"Trending": 0.5, "Volatile": 0.6, "Ranging": 0.5}
            _rit = _REGIME_INRANGE_THRESH.get(hmm_state_name, 0.5)
            _h4mv = feat_dict.get("h4_move_pct", 0.0) or 0.0
            feat_dict["in_range_phase"] = int(abs(float(_h4mv)) < _rit)

        # Feature vectors built per-model using model.feature_names
        # (defined inside routing block below as _make_X_hybrid)

        # ── Volatility Regime — L7b 2026-06-29: was ATR-derived (informational only, no
        # filtering); ATR removed → constant "normal" (display-only, kept for log/dashboard).
        vol_regime = "normal"
        self._last_vol_regime = vol_regime

        # ── 6th: MODEL ROUTING — STRICT PRIORITY ORDER ───────
        # Priority: 1. News model  2. State model  3. Dir model  4. Combined
        direction  = trade_type.upper()
        state_key  = hmm_state_name.lower()

        # Use is_pre_news only for news routing (post-news = normal trading!)
        _is_in_news = feat_dict.get("is_pre_news", 0) > 0  # only PRE-news triggers news model

        def _to_scalar(x):
            """Force any model output to plain Python float."""
            import numpy as _np
            try:
                return float(_np.asarray(x).flat[0])
            except Exception:
                return float(x)

        def _make_X_hybrid(model):
            """Build feature vector using model's own feature_names."""
            cols = getattr(model, "feature_names", None) or FEATURE_COLS + ["hmm_state"]
            missing = [c for c in cols if c not in feat_dict]
            if missing:
                # FIX #21: also send to logging — print() never reached
                # bridge.log, so silent feature gaps went unnoticed.
                _msg = f"⚠️ Missing features ({len(missing)}): {missing[:5]}"
                print(f"  {_msg}")
                try:
                    import logging as _lg
                    _lg.getLogger("QGAI").warning(_msg)
                except Exception:
                    pass
            x = np.array([[feat_dict.get(c, 0) for c in cols]], dtype=np.float32)
            # Safety: replace any NaN/Inf with 0 before prediction
            x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
            return x

        def _prob(model):
            return _to_scalar(model.predict_win_prob(_make_X_hybrid(model)))

        # ── PRIORITY 1: News model (pre/post news bars) ───────
        if _is_in_news and self.xgb_news is not None:
            xgb_prob = _prob(self.xgb_news)
            self._last_state_prob = xgb_prob
            self._last_dir_prob   = xgb_prob
            _routing = "news_model"

        # ── PRIORITY 2: News normal model (clean bars) ────────
        elif not _is_in_news and self.xgb_normal is not None:
            xgb_prob = _prob(self.xgb_normal)
            self._last_state_prob = xgb_prob
            self._last_dir_prob   = xgb_prob
            _routing = "normal_model"

        # ── PRIORITY 3: State + Directional blend ─────────────
        elif self.xgb_state.get(state_key) is not None and (
             self.xgb_buy if direction == "BUY" else self.xgb_sell) is not None:
            state_model = self.xgb_state[state_key]
            dir_model   = self.xgb_buy if direction == "BUY" else self.xgb_sell
            dir_weight   = 0.35 if direction == "BUY" else 0.45
            state_weight = 1.0 - dir_weight
            state_prob = _prob(state_model)
            dir_prob   = _prob(dir_model)
            # Anchor blend: 70% combined (AUC=0.73) + 30% state/dir blend
            # Prevents weak state models (AUC ~0.60) from dominating the signal
            _raw_blend = state_weight * state_prob + dir_weight * dir_prob
            if self.xgb is not None:
                combined_prob = _prob(self.xgb)
                xgb_prob = 0.70 * combined_prob + 0.30 * _raw_blend
            else:
                xgb_prob = _raw_blend
            self._last_state_prob = round(state_prob, 4)
            self._last_dir_prob   = round(dir_prob, 4)
            _routing = f"combined(70%)+state({state_key})+dir({direction})(30%)"

        # ── PRIORITY 4: State only ────────────────────────────
        elif self.xgb_state.get(state_key) is not None:
            xgb_prob = _prob(self.xgb_state[state_key])
            self._last_state_prob = round(xgb_prob, 4)
            self._last_dir_prob   = xgb_prob
            _routing = f"state({state_key})"

        # ── PRIORITY 5: Directional only ─────────────────────
        elif (self.xgb_buy if direction == "BUY" else self.xgb_sell) is not None:
            dir_model = self.xgb_buy if direction == "BUY" else self.xgb_sell
            xgb_prob  = _prob(dir_model)
            self._last_state_prob = xgb_prob
            self._last_dir_prob   = round(xgb_prob, 4)
            _routing = f"dir({direction})"

        # ── PRIORITY 6: Combined model (fallback) ─────────────
        else:
            xgb_prob = _prob(self.xgb)
            self._last_state_prob = xgb_prob
            self._last_dir_prob   = xgb_prob
            _routing = "combined_fallback"

        # X_main for BigWin/Duration — use combined model's full feature set
        # feat_dict["hmm_state"] already set as integer above
        _fn = getattr(self.xgb, "feature_names", None) or FEATURE_COLS + ["hmm_state"]
        X_main = np.array([[feat_dict.get(c, 0) for c in _fn]], dtype=np.float32)

        # ── Prediction models (BigWin + Duration) ────────────
        # C10 fix: reset each bar so stale values don't show on dashboard
        self._last_big_prob = 0.0
        self._last_dur_prob = 0.0
        big_prob = 0.0; dur_prob = 0.0
        if hasattr(self, 'big_predictor') and self.big_predictor:
            try:
                big_prob = self.big_predictor.predict_prob(X_main)
            except Exception as _e:
                print(f"  ⚠ big_predictor failed: {_e}")
        if hasattr(self, 'dur_predictor') and self.dur_predictor:
            try:
                dur_prob = self.dur_predictor.predict_prob(X_main)
            except Exception as _e:
                print(f"  ⚠ dur_predictor failed: {_e}")
        dyn = get_dynamic_tp_sl(xgb_prob, big_prob, dur_prob)

        self._last_big_prob = big_prob
        self._last_dur_prob = dur_prob
        self._last_dyn      = dyn

        # ── Online learner blend ──────────────────────────────
        if self.online is not None:
            online_prob = self.online.predict(feat_dict)
            # Bug #4 fix: adaptive online weight based on recent accuracy
            _online_acc = self.online.recent_win_rate()
            if _online_acc > 0.55:
                _w_online = 0.20
            elif _online_acc > 0.50:
                _w_online = 0.15
            else:
                _w_online = 0.05   # near-random — barely trust it
            final_prob = (1.0 - _w_online) * xgb_prob + _w_online * online_prob
        else:
            final_prob = xgb_prob  # no online learner → use XGB directly

        # ── SL multiplier ─────────────────────────────────────
        sl_mult = self.xgb.get_sl_multiplier(feat_dict)
        # NOTE: removed vol-boost × 1.2 on SL — high ATR already produces a
        # wider SL naturally (SL = ATR × ATR_MULT × sl_mult). Double-widening
        # caused vSL $30-40 → lot=0.01-0.02 → tiny profit per trade.
        # High-vol filter now handled by skip logic at inference level if needed.

        # ── Skip conditions ───────────────────────────────────
        if sl_mult == -1.0:
            return self._make_result("SKIP", final_prob, 0, hmm_state_name,
                                     "EIA 0-15min after — spread too wide", feat_dict,
                                     state_prob=getattr(self, "_last_state_prob", None),
                                     dir_prob=getattr(self, "_last_dir_prob", None))

        # ── CONFIDENCE FILTER — data-proven thresholds ────────
        # Validated against 2,788 backtest trades:
        #   Ranging:  WR=37.9% (+0.7pp) → standard threshold ✅
        #   Trending: WR=35.7% (-1.4pp) → TRENDING is HARDER! Need higher bar
        #   Volatile: WR=37.7% (+0.5pp) → standard threshold ✅
        #
        # NEWS DATA (actual 3★ news file validated):
        #   0-15 min BEFORE news:  WR=37.9% — slightly uncertain, higher bar
        #   15-30 min BEFORE news: WR=37.3% — almost normal
        #   0-15 min AFTER news:   WR=37.1% — fine, normal threshold
        #   15-30 min AFTER news:  WR=41.9% (+4.8pp) ← GREAT! No penalty!
        #   30-60 min AFTER news:  WR=44.0% (+6.8pp) ← BEST! Post-news = good!
        #   CONCLUSION: Post-news is BETTER than average — do NOT penalize it!
        _base_thresh = CFG.filters.min_win_prob  # 0.45 from config
        # THRESHOLD A/B OFFSET (2026-07-12): env QGAI_THRESH_OFFSET subtracts a
        # uniform amount from every regime threshold (e.g. 0.05 → lower the bar,
        # take more trades, trust the model more — "model over hard filters").
        # Default 0.0 = current behaviour. Positive = lower bar; negative = raise.
        try:
            _toff = float(os.environ.get("QGAI_THRESH_OFFSET") or 0.0)
        except ValueError:
            _toff = 0.0
        _base_thresh = _base_thresh - _toff
        # Regime thresholds from signal replay analysis (644 trades):
        #   Volatile : 70.2% WR → lower bar slightly (more trades, best regime)
        #   Trending : 64.9% WR → standard
        #   Ranging  : 62.9% WR → raise bar slightly (weakest regime)
        _state_thresh = {
            "Ranging":  _base_thresh + 0.03,   # 0.48 — weakest (WR 62.9%)
            "Trending": _base_thresh,           # 0.45 — standard (WR 64.9%)
            "Volatile": max(0.42 - _toff, _base_thresh - 0.03),  # 0.42 — best (WR 70.2%)
        }

        # Only PRE-news (0-15min before) needs caution — NOT post-news!
        _is_pre_news_now  = feat_dict.get("is_pre_news", 0)   # 1 = within 15min of news
        _is_post_news_now = feat_dict.get("is_post_news", 0)  # 1 = within 15min after

        # Pre-news penalty REMOVED 2026-07-12 (Imtiyaz): pre-news now uses the plain
        # regime threshold (was +0.05 bar-raise). "model over hard filters".
        _threshold = _state_thresh.get(hmm_state_name, _base_thresh)
        _news_label = ("|pre-news" if _is_pre_news_now
                       else "|post-news" if _is_post_news_now else "")

        # EARLY-ENTRY THRESHOLD DISCOUNT -- REMOVED 2026-07-12 (Imtiyaz): nil impact
        # under max_open=1 (1-month A/B identical +8.9R, like ET1). _ed_disc stays 0.0
        # so the effective-threshold export below is unchanged. REVERT: git history.
        _ed_disc = 0.0
        # Expose the effective threshold used for THIS bar (regime + news adjusted +
        # early-entry discount), so downstream soft-gates (SMMA MTF, etc.) can layer
        # on top without re-deriving.
        self._last_effective_threshold = float(_threshold)
        self._last_early_discount = float(_ed_disc)
        if final_prob < _threshold:
            return self._make_result("SKIP", final_prob, sl_mult, hmm_state_name,
                                     f"prob {final_prob:.2%} < threshold {_threshold:.2%}"
                                     f" ({hmm_state_name}{_news_label})",
                                     feat_dict,
                                     state_prob=getattr(self, "_last_state_prob", None),
                                     dir_prob=getattr(self, "_last_dir_prob", None))

        # ── VOLATILE + LOW-CONFIDENCE + COUNTER-HTF GATE (2026-07-13, Imtiyaz) ──
        # Signal-audit finding: on the honest 53-week WFO baseline, Volatile-regime
        # trades in the 42-48% win_prob band that go AGAINST the dominant HTF
        # direction (H1/H4 DI, via ts_htf_agreement) are net-LOSING (n=38,
        # total -1.9R, PF 0.88) while the SAME band aligned WITH the HTF is
        # strongly profitable (n=48, +18.9R, PF 3.78). Confirmed NOT a time/slot
        # confound (slot_win_rate ~identical between both buckets, spread across
        # 18 hours/5 weekdays/24 different weeks — see FIXES_CHANGELOG4.md
        # 2026-07-13). This is a directional-agreement + confidence gate, not a
        # time-based filter (Imtiyaz's own principle: build the strategy first,
        # time-features stay soft/model-internal, no hard time filters).
        # Env-gated, default OFF — a candidate for WFO A/B testing, NOT yet
        # adopted live. REVERT: this whole block is a no-op when the env var
        # is unset (matches the QGAI_REGIME_INRANGE / QGAI_CTF_FADE pattern).
        if os.environ.get("QGAI_VOL_HTF_GATE", "0") == "1" and hmm_state_name == "Volatile":
            _dir_sign  = 1.0 if trade_type.upper() == "BUY" else -1.0
            _htf_agree = feat_dict.get("ts_htf_agreement", 0) or 0
            _htf_against = (_dir_sign * _htf_agree) < 0
            if _htf_against and 0.42 <= final_prob < 0.48:
                return self._make_result("SKIP", final_prob, sl_mult, hmm_state_name,
                                         f"prob={final_prob:.2%} in 42-48% band, Volatile, "
                                         f"AND counter-HTF (ts_htf_agreement={_htf_agree}) — "
                                         f"QGAI_VOL_HTF_GATE",
                                         feat_dict,
                                         state_prob=getattr(self, "_last_state_prob", None),
                                         dir_prob=getattr(self, "_last_dir_prob", None))

        # ── Signal confirmed ──────────────────────────────────
        signal = trade_type.upper()
        reason = (f"prob={final_prob:.2%} | "
                  f"model={_routing} | "
                  f"state={hmm_state_name} | vol={vol_regime} | "
                  f"slot_wr={feat_dict.get('slot_win_rate',0):.2%}")

        # Bug #7 fix: cache last features + timestamp for on_trade_closed reuse
        self._last_features   = feat_dict
        self._last_feat_ts    = timestamp
        self._last_trade_type = trade_type
        # 2026-07-03 (Divyesh) direction-swap log bug: backtest evaluates BUY then
        # SELL; _last_features always held the LAST call (SELL) — so when BUY won
        # the pick, the logged f_* columns described the SELL evaluation (131/308
        # OOS BUY rows had f_trade_direction=-1). Keep a PER-DIRECTION cache so
        # the caller can log the winning direction's own features.
        if trade_type.upper() == "BUY":
            self._last_features_buy = feat_dict
        else:
            self._last_features_sell = feat_dict

        # Store in latency cache for same-bar duplicate call
        _result = self._make_result(signal, final_prob, sl_mult, hmm_state_name, reason, feat_dict,
                                    state_prob=self._last_state_prob,
                                    dir_prob=self._last_dir_prob)
        self._cache_timestamp = timestamp
        if _direction == "BUY":
            self._cache_buy  = _result
        else:
            self._cache_sell = _result
        return _result

    def on_trade_closed(self,
                        timestamp:  pd.Timestamp,
                        trade_type: str,
                        volume:     float,
                        label:      int,
                        pnl:        float):
        """
        Call when a trade closes.
        label = 1 (Win) or 0 (Loss)
        """
        # Bug #7 fix: reuse cached features if timestamp matches — avoid double compute
        _cached_ts = getattr(self, '_last_feat_ts', None)
        _cached_tt = getattr(self, '_last_trade_type', None)
        # B9 fix: normalize both to pd.Timestamp for reliable comparison
        import pandas as _pd2
        _ts_norm = _pd2.Timestamp(timestamp) if timestamp is not None else None
        _cached_norm = _pd2.Timestamp(_cached_ts) if _cached_ts is not None else None
        if (_cached_norm is not None and _cached_norm == _ts_norm and _cached_tt == trade_type
                and hasattr(self, '_last_features')):
            feat_dict = self._last_features
        else:
            feat_dict = compute_features(
                t          = timestamp,
                trade_type = trade_type,
                volume     = volume,
                ohlc_df    = self.ohlc_df,
                adx_df     = self.adx_df,
                news_df    = self.news_df,
                slot_table = self.slot_tbl,
                h4_df      = self.h4_df,
                h1_ob      = self.h1_ob,
                h4_ob_df   = self.h4_ob_df,
            )

        # A. Online learning update
        if self.online is not None:
            self.online.update(feat_dict, label)

        # B. Drift detector update
        if self.drift is not None:
            self.drift.add(label)
            alert = self.drift.check_and_alert()
        else:
            alert = False

        # C. Log to CSV
        self._log_trade(timestamp, trade_type, volume, label, pnl, feat_dict)

        # D. Save updated online model + drift state
        cfg = CFG.paths
        if self.online is not None:
            self.online.save(f"{cfg.models_dir}/online_model.pkl")
        if self.drift is not None:
            self.drift.save(f"{cfg.models_dir}/drift_detector.pkl")

        # E. Trigger emergency retrain if drifting
        if alert:
            print("  Auto-retrain triggered by drift detector...")
            self._trigger_retrain()

        ol_acc = f"{self.online.accuracy():.3f}" if self.online else "N/A"
        dr_wr  = f"{self.drift.current_win_rate()*100:.1f}%" if self.drift else "N/A"
        print(f"  Trade closed → {'WIN' if label else 'LOSS'} | "
              f"P&L=${pnl:.2f} | "
              f"Online acc={ol_acc} | "
              f"Recent WR={dr_wr}")

    def _trigger_retrain(self):
        if self.retrainer is None:
            print("  ⚠️ Retrainer not available (river not installed) — skipping retrain")
            return
        cfg = CFG.paths
        self.retrainer.retrain(
            original_trades_path = cfg.trades_file,
            live_log_path        = cfg.live_log,
            ohlc_path            = cfg.ohlc_file,
            adx_path             = cfg.adx_file,
            news_path            = cfg.news_file,
            models_dir           = cfg.models_dir,
            registry_dir         = cfg.registry_dir,
        )
        # Reload models after retrain — safe (file may not exist yet)
        hmm_path = Path(cfg.models_dir) / "hmm_model.pkl"
        xgb_path = Path(cfg.models_dir) / "xgb_model.pkl"
        if hmm_path.exists(): self.hmm.load(str(hmm_path))
        if xgb_path.exists(): self.xgb.load(str(xgb_path))
        # Reload directional models
        buy_path  = Path(cfg.models_dir) / "buy_model.pkl"
        sell_path = Path(cfg.models_dir) / "sell_model.pkl"
        self.xgb_buy  = WinProbabilityModel().load(str(buy_path))  if buy_path.exists()  else None
        self.xgb_sell = WinProbabilityModel().load(str(sell_path)) if sell_path.exists() else None
        # Bug #5 fix: reload BigWin + Duration after retrain
        big_path = Path(cfg.models_dir) / "big_win_model.pkl"
        dur_path = Path(cfg.models_dir) / "duration_model.pkl"
        self.big_predictor = BigWinPredictor().load(str(big_path)) if big_path.exists() else None
        self.dur_predictor = DurationPredictor().load(str(dur_path)) if dur_path.exists() else None
        if self.drift is not None:
            self.drift.n_retrains += 1

    # 2026-06-27 L10: FIXED schema — do NOT dump the feature vector. The old code did
    # row.update(feat_dict) + fieldnames=row.keys(), so as the feature set changed over time
    # (ATR/volume removed, 67→44 prune) the column count drifted (82..99) and the one-time
    # header no longer matched → corrupted CSV. self_learning recomputes features from OHLC,
    # so the trade log only needs the core record. A few stable fields kept for the dashboard.
    LIVE_TRADE_COLS = ["datetime", "type", "volume", "label", "pnl",
                       "win_prob", "hmm_state", "in_range_phase"]

    def _log_trade(self, ts, trade_type, volume, label, pnl, feat_dict):
        fd = feat_dict or {}
        row = {"datetime": ts, "type": trade_type, "volume": volume,
               "label": label, "pnl": pnl,
               "win_prob":       fd.get("win_prob", ""),
               "hmm_state":      fd.get("hmm_state", ""),
               "in_range_phase": fd.get("in_range_phase", "")}
        write_header = not self.live_log.exists()
        with open(self.live_log, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.LIVE_TRADE_COLS,
                                    extrasaction="ignore", restval="")
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    def _predict_move(self, trade_type: str, feat_dict: dict) -> dict:
        """M1: predicted MFE (ATR units + %) for next 12 bars. Info-only."""
        out = {}
        try:
            d = trade_type.lower()
            if not self.move_models or (d, 50) not in self.move_models:
                return out
            import pandas as _pd3
            pack = self.move_models[(d, 50)]
            cols = pack["features"]
            row = _pd3.DataFrame([{c: feat_dict.get(c, 0) for c in cols}]).fillna(0)
            atr_pct = 0.2   # L7b: ATR removed — fixed 0.2% move-model normalization (must match train_move_model)
            for q in (25, 50, 75):
                pk = self.move_models.get((d, q))
                if pk is None:
                    continue
                v = float(pk["model"].predict(row[pk["features"]])[0])
                out[f"pred_move_p{q}_atr"] = round(v, 2)
                out[f"pred_move_p{q}_pct"] = round(v * atr_pct, 3)
            # M2: predicted adverse move (MAE) — for SL placement + trailing
            for q in (50, 75):
                pk = self.sl_models.get((d, q))
                if pk is None:
                    continue
                v = max(0.0, float(pk["model"].predict(row[pk["features"]])[0]))
                out[f"pred_mae_p{q}_atr"] = round(v, 2)
                out[f"pred_mae_p{q}_pct"] = round(v * atr_pct, 3)
        except Exception:
            return {}
        return out

    def _make_result(self, signal, prob, sl_mult, state_name, reason, feat_dict,
                     state_prob=None, dir_prob=None):
        try:
            _snap = {
                k: (float(v) if isinstance(v, (np.floating, np.integer)) else v)
                for k, v in sorted((feat_dict or {}).items())
                if not str(k).startswith("_")
            }
            _snap_json = json.dumps(_snap, sort_keys=True, separators=(",", ":"), default=str)
            _snap_hash = hashlib.sha256(_snap_json.encode("utf-8")).hexdigest()[:16]
        except Exception:
            _snap_json = "{}"
            _snap_hash = "snapshot_error"
        return {
            "signal":       signal,
            "model_version":getattr(self, "model_version", "unknown"),
            "model_hash":   getattr(self, "model_hash", "unknown"),
            "model_file_name": getattr(self, "model_file_name", "xgb_model.pkl"),
            "feature_snapshot_json": _snap_json,
            "feature_hash": _snap_hash,
            "win_prob":     round(prob, 4),
            "state_prob":   round(state_prob, 4) if state_prob is not None else round(prob, 4),
            "dir_prob":     round(dir_prob, 4)   if dir_prob   is not None else round(prob, 4),
            "big_win_prob": round(getattr(self,"_last_big_prob",0.0), 3),
            "long_dur_prob":round(getattr(self,"_last_dur_prob",0.0), 3),
            "dynamic_tp":   getattr(self,"_last_dyn",{}).get("tp_multiplier",1.5),
            "dynamic_advice":getattr(self,"_last_dyn",{}).get("advice","Standard"),
            "sl_multiplier":sl_mult,
            "tp_multiplier":getattr(self,"_last_dyn",{}).get("tp_multiplier",1.5),
            "hmm_state":    state_name,
            "reason":       reason,
            "slot":         feat_dict.get("15_min_slot", -1),
            "slot_wr":      round(feat_dict.get("slot_win_rate", 0), 3),
            "mins_to_3star":feat_dict.get("mins_to_next_3star", 999),
            "before_eia":      feat_dict.get("before_eia", 0),
            "is_post_big_move":feat_dict.get("is_post_big_move", 0),
            "big_move_dir":    feat_dict.get("big_move_direction", 0),
            "in_range_phase":  feat_dict.get("in_range_phase", 0),
            # dominant-TF momentum (for counter-trend-fade filter — config skip_counter_trend_fade)
            "H1_ADX":          feat_dict.get("H1_ADX", 0),
            "H4_ADX":          feat_dict.get("H4_ADX", 0),
            "H1_DI_diff":      feat_dict.get("H1_DI_diff", 0),
            "H4_DI_diff":      feat_dict.get("H4_DI_diff", 0),
            "h1_adx_slope":    feat_dict.get("h1_adx_slope", 0),
            "h4_adx_slope":    feat_dict.get("h4_adx_slope", 0),
            # ── ts_* trend-signal features (for the trend-pullback entry gate — ET1 — + market-intel box) ──
            "ts_line_dist_pct":   feat_dict.get("ts_line_dist_pct", 0),   # signed % dist price↔active ratchet line
            "ts_htf_agreement":   feat_dict.get("ts_htf_agreement", 0),   # trend_m15+h1+h4 (-3..+3)
            "ts_adx_switch_trend":feat_dict.get("ts_adx_switch_trend", 0),# EA rule: H4 trend if H4 ADX>=19 else H1
            "ts_flip_recent":     feat_dict.get("ts_flip_recent", 0),     # 1 = SMMA flip within last 3 M15 bars
            "ts_bars_since_flip": feat_dict.get("ts_bars_since_flip", 999),
            "ts_trend_m15":       feat_dict.get("ts_trend_m15", 0),       # +1 up / -1 down (M15 SMMA)
            "ts_trend_h1":        feat_dict.get("ts_trend_h1", 0),        # +1 / -1 (H1)
            "ts_trend_h4":        feat_dict.get("ts_trend_h4", 0),        # +1 / -1 (H4)
            "effective_threshold": round(getattr(self, "_last_effective_threshold", 0.45), 4),
            "h4_resist_dist":  feat_dict.get("h4_resist_dist", 999),
            "h4_support_dist": feat_dict.get("h4_support_dist", 999),
            "h4_in_ob_zone":   feat_dict.get("h4_in_ob_zone", 0),
            "h4_ob_strength":  feat_dict.get("h4_ob_strength", 0),
            "h1_resist_dist":  feat_dict.get("h1_resist_dist", 999),
            "h1_support_dist": feat_dict.get("h1_support_dist", 999),
            "h1_in_ob_zone":   feat_dict.get("h1_in_ob_zone", 0),
            "h1_ob_strength":  feat_dict.get("h1_ob_strength", 0),
            # M1: predicted move size (info-only, dashboard display)
            **self._predict_move("BUY" if feat_dict.get("is_buy", 1) else "SELL", feat_dict),
            "is_pre_news":     feat_dict.get("is_pre_news", 0),
            "is_post_news":    feat_dict.get("is_post_news", 0),
            # FIX #B5: the dashboard's "3★ Dev Sign" field read this key
            # but it was never copied from features → stuck at "--"
            "last_3star_dev_sign": feat_dict.get("last_3star_dev_sign", 0),
            "corr_imp_ratio":  feat_dict.get("corr_imp_ratio", 1.0),
            # FIX #B5: dashboard's "3★ Dev Sign" read this key but it was
            # never copied from features → permanent "--".
            "last_3star_dev_sign": feat_dict.get("last_3star_dev_sign", 0),
            "vol_regime":      getattr(self,"_last_vol_regime","normal"),
        }


    def update_capital(self, capital_usd: float):
        """
        MUST be called by bridge after MT5 connect with real account equity.
        Trading is blocked until this is called with a valid value.
        """
        if capital_usd <= 0:
            print(f"  ⚠️ update_capital: invalid value {capital_usd} — ignored")
            return
        was_set = self._account_capital > 0 and self._capital_set
        self._account_capital = float(capital_usd)
        self._capital_set     = True
        # FIX 2026-06-14: set day-open capital HERE using the freshly-updated
        # equity, so the daily-loss limit is based on TODAY's opening equity
        # (not yesterday's close). The get_signal() reset no longer sets it.
        if self._day_open_capital <= 0:
            self._day_open_capital = float(capital_usd)
        if not was_set:
            print(f"  ✅ Capital set: ${capital_usd:,.2f} — trading UNLOCKED")

    def record_trade_result(self, pnl: float):
        """
        Call when a trade closes to track daily loss.
        pnl: negative = loss, positive = profit (in account currency).
        """
        if pnl < 0:
            self._daily_loss += abs(pnl)
            limit = self._day_open_capital * CFG.filters.daily_loss_limit_pct / 100.0
            if CFG.filters.enable_daily_sl and self._daily_loss >= limit and not self._daily_sl_hit:
                self._daily_sl_hit = True
                print(f"  ⛔ DAILY SL HIT! Lost ${self._daily_loss:.2f} / limit ${limit:.2f}")

    def get_daily_status(self) -> dict:
        limit = self._day_open_capital * CFG.filters.daily_loss_limit_pct / 100.0
        return {
            "date":         str(self._today),
            "daily_loss_$": round(self._daily_loss, 2),
            "daily_sl_$":   round(limit, 2),
            "can_trade":    not self._daily_sl_hit,
        }


# ─────────────────────────────────────────────
# WEEKLY RETRAIN SCHEDULER
# ─────────────────────────────────────────────

def run_weekly_retrain():
    """
    Call this every Sunday.
    Can be scheduled via Windows Task Scheduler:
        python inference.py --retrain
    """
    if not ONLINE_LEARNING:
        print("  ⚠️ Online learning disabled (river not installed) — skipping manual retrain")
        return
    cfg = CFG.paths
    retrainer = PeriodicRetrainer()
    retrainer.retrain(
        original_trades_path = cfg.trades_file,
        live_log_path        = cfg.live_log,
        ohlc_path            = cfg.ohlc_file,
        adx_path             = cfg.adx_file,
        news_path            = cfg.news_file,
        models_dir           = cfg.models_dir,
        registry_dir         = cfg.registry_dir,
    )


# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if "--retrain" in sys.argv:
        print("Running weekly retrain...")
        run_weekly_retrain()
    else:
        engine = LiveInferenceEngine()

        test_time = pd.Timestamp("2026-04-15 17:15:00")
        result = engine.get_signal(
            timestamp  = test_time,
            trade_type = "BUY",
            volume     = 0.1,
        )

        print("\n" + "="*55)
        print("  SAMPLE SIGNAL OUTPUT")
        print("="*55)
        for k, v in result.items():
            print(f"  {k:<20}: {v}")
        print("="*55)
