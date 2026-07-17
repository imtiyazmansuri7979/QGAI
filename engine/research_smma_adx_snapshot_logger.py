"""
research_smma_adx_snapshot_logger.py
====================================
COMPLETE live (forming) snapshot logger for the 2-SMMA + ADX-DI research.
At EVERY M15 decision bar it captures the full evolving state of BOTH indicators
across M15/M30/H1/H4, using PARTIAL-candle reconstruction for M30/H1/H4 (the same
leakage-safe forming method as research_smma_adx_score_sweep.py). Reproduces the
live evolving values (H4 = 16 snapshots per period), never backward-fills the
final HTF candle.

SEPARATION OF CONCERNS (research mandate, section 22):
  This logs RAW DATA ONLY. It does NOT make trade decisions. Entry logic stays in
  research_smma_adx_score_sweep.py and uses only the baseline direction scores +
  timeframe combination + equal weighting. Every rich field here (slope, distance,
  persistence, band width, transition, extension) is for LATER analysis / AI
  feature creation, and is tagged used_for_entry=0 in the data dictionary.

ISOLATION: loads only OHLC (+tick_volume). No model, no win_prob, no HMM, no
threshold, no news/slot filter. Never imports inference/bridge/train. Writes only
into backtest/results/smma_adx_snapshot/.

Run:  python research_smma_adx_snapshot_logger.py [--start YYYY-MM-DD --end YYYY-MM-DD]
"""
import argparse, sys
import numpy as np
import pandas as pd
from pathlib import Path

from trend_signal import _ma, compute_trend
from research_smma_adx_score_sweep import (
    _ema_di_adx, _ema_state, _resample_ohlcv, load_ohlc_vol,
    TF_MIN, TF_RULE)

ENGINE = Path(__file__).resolve().parent
OUT_DIR = ENGINE.parent / "backtest" / "results" / "smma_adx_snapshot"
TFS = ["M15", "M30", "H1", "H4"]
TF_EXPECT = {"M15": 1, "M30": 2, "H1": 4, "H4": 16}
ADX_PERIOD = 14
CLIP_DIST = 5.0          # fixed bounded clip for distance/score (no dataset normalization)


# ─────────────────────────────────────────────────────────────────────────
# Causal helpers
# ─────────────────────────────────────────────────────────────────────────
def _bars_since_true(cond):
    n = len(cond); out = np.full(n, np.nan); last = -1
    for i in range(n):
        if cond[i]:
            last = i
        if last >= 0:
            out[i] = i - last
    return out


def _bars_since_flip(dir_arr):
    n = len(dir_arr); out = np.full(n, np.nan); last = -1; prev = 0
    for i in range(n):
        d = dir_arr[i]
        if d != 0 and prev != 0 and d != prev:
            last = i
        if d != 0:
            prev = d
        if last >= 0:
            out[i] = i - last
    return out


def _persistence(dir_arr):
    n = len(dir_arr); out = np.zeros(n); cnt = 0; prev = None
    for i in range(n):
        if prev is not None and dir_arr[i] == prev:
            cnt += 1
        else:
            cnt = 0
        out[i] = cnt; prev = dir_arr[i]
    return out


# ─────────────────────────────────────────────────────────────────────────
# Forming per-TF raw arrays (partial candle + SMMA buffers + ADX/DI)
# ─────────────────────────────────────────────────────────────────────────
def forming_tf_arrays(base, tf, adx_period):
    """Per-M15-bar forming state for one timeframe. M15 = the closed M15 bar
    itself; M30/H1/H4 = reconstructed partial candle from completed M15 bars."""
    n = len(base)
    mo = base["time"].values.astype("datetime64[ns]")
    O = base["open"].to_numpy(float); H = base["high"].to_numpy(float)
    L = base["low"].to_numpy(float);  C = base["close"].to_numpy(float)
    V = (base["tick_volume"].to_numpy(float) if "tick_volume" in base.columns else np.zeros(n))

    if tf == "M15":
        maH = _ma(H, 2, "SMMA"); maL = _ma(L, 2, "SMMA")
        pdi, ndi, adx = _ema_di_adx(H, L, C, adx_period)
        return {
            "pstart": mo.copy(), "ncomp": np.ones(n, int),
            "o": O.copy(), "h": H.copy(), "l": L.copy(), "c": C.copy(), "v": V.copy(),
            "smma_high": maH, "smma_low": maL, "pdi": pdi, "ndi": ndi, "adx": adx,
            "last_m15": mo.copy(),
        }

    htf = _resample_ohlcv(base, TF_RULE[tf])
    ho = htf["time"].values.astype("datetime64[ns]")
    hh = htf["high"].to_numpy(float); hl = htf["low"].to_numpy(float); hc = htf["close"].to_numpy(float)
    maH = _ma(hh, 2, "SMMA"); maL = _ma(hl, 2, "SMMA")
    sTR, sPDM, sNDM, cADX = _ema_state(hh, hl, hc, adx_period)
    p_arr = np.searchsorted(ho, mo, side="right") - 1

    out = {k: np.full(n, np.nan) for k in
           ("o", "h", "l", "c", "v", "smma_high", "smma_low", "pdi", "ndi", "adx")}
    out["pstart"] = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
    out["ncomp"] = np.zeros(n, int)
    out["last_m15"] = mo.copy()

    run_hi = run_lo = run_vol = np.nan; per_open = np.nan; ncomp = 0; cur_p = -1
    for i in range(n):
        p = int(p_arr[i])
        if p != cur_p:
            cur_p = p; per_open = O[i]; run_hi = H[i]; run_lo = L[i]; run_vol = V[i]; ncomp = 1
        else:
            run_hi = max(run_hi, H[i]); run_lo = min(run_lo, L[i]); run_vol += V[i]; ncomp += 1
        out["pstart"][i] = ho[p] if p >= 0 else np.datetime64("NaT")
        out["ncomp"][i] = ncomp
        out["o"][i] = per_open; out["h"][i] = run_hi; out["l"][i] = run_lo
        out["c"][i] = C[i]; out["v"][i] = run_vol
        k = p - 1
        if k < 0 or k >= len(maH) or np.isnan(maH[k]) or np.isnan(maL[k]):
            continue
        out["smma_high"][i] = (maH[k] + run_hi) / 2.0
        out["smma_low"][i] = (maL[k] + run_lo) / 2.0
        if k >= 1 and not np.isnan(sTR[k]) and not np.isnan(cADX[k]):
            up = run_hi - hh[k]; dnn = hl[k] - run_lo
            pdm = up if (up > dnn and up > 0) else 0.0
            ndm = dnn if (dnn > up and dnn > 0) else 0.0
            trv = max(run_hi - run_lo, abs(run_hi - hc[k]), abs(run_lo - hc[k]))
            sTR_f = sTR[k] - sTR[k] / adx_period + trv
            sPDM_f = sPDM[k] - sPDM[k] / adx_period + pdm
            sNDM_f = sNDM[k] - sNDM[k] / adx_period + ndm
            if sTR_f > 0:
                pdi_f = 100 * sPDM_f / sTR_f; ndi_f = 100 * sNDM_f / sTR_f
                den = pdi_f + ndi_f
                dx_f = 100 * abs(pdi_f - ndi_f) / den if den > 0 else 0.0
                out["pdi"][i] = pdi_f; out["ndi"][i] = ndi_f
                out["adx"][i] = (cADX[k] * (adx_period - 1) + dx_f) / adx_period
    return out


# ─────────────────────────────────────────────────────────────────────────
# Full per-TF field frame (all sections 1-19 at TF level)
# ─────────────────────────────────────────────────────────────────────────
def build_tf_frame(base, tf, a):
    n = len(base)
    mo = base["time"]
    close_t = pd.to_datetime(mo) + pd.Timedelta(minutes=15)
    d = {}
    # 1) identification
    d["decision_time"] = close_t
    d["signal_bar_open_time"] = pd.to_datetime(mo)
    d["signal_bar_close_time"] = close_t
    d["timeframe"] = tf
    d["htf_period_start"] = a["pstart"]
    d["htf_period_expected_close"] = pd.to_datetime(a["pstart"]) + pd.Timedelta(minutes=TF_MIN[tf])
    d["partial_bar_number"] = a["ncomp"]
    d["partial_bar_count_expected"] = TF_EXPECT[tf]
    d["is_partial_candle"] = (a["ncomp"] < TF_EXPECT[tf]).astype(int)
    d["is_fully_closed_candle"] = (a["ncomp"] >= TF_EXPECT[tf]).astype(int)
    d["bars_used_in_partial_candle"] = a["ncomp"]
    d["source_last_m15_time"] = a["last_m15"]
    # 2) OHLCV + derived
    o, h, l, c, v = a["o"], a["h"], a["l"], a["c"], a["v"]
    d["tf_open"] = o; d["tf_high"] = h; d["tf_low"] = l; d["tf_close"] = c
    d["tf_tick_volume"] = v
    d["tf_real_volume"] = np.nan          # source has tick_volume only (documented)
    d["tf_spread"] = np.nan               # per-bar spread not in source (documented)
    rng = h - l; body = np.abs(c - o)
    d["tf_range"] = rng; d["tf_body"] = body
    d["tf_upper_wick"] = h - np.maximum(o, c)
    d["tf_lower_wick"] = np.minimum(o, c) - l
    with np.errstate(divide="ignore", invalid="ignore"):
        d["tf_body_pct_of_range"] = np.where(rng > 0, body / rng * 100.0, 0.0)
        d["tf_close_location_value"] = np.where(rng > 0, (c - l) / rng, 0.5)
    # 3) ADX raw
    pdi, ndi, adx = a["pdi"], a["ndi"], a["adx"]
    di_diff = pdi - ndi
    d["adx_value"] = adx; d["plus_di"] = pdi; d["minus_di"] = ndi
    d["di_diff"] = di_diff; d["abs_di_diff"] = np.abs(di_diff)
    with np.errstate(divide="ignore", invalid="ignore"):
        den = pdi + ndi
        d["dx_value"] = np.where(den > 0, 100 * np.abs(di_diff) / den, 0.0)
    adx_dir = np.where(pdi > ndi, 1, np.where(ndi > pdi, -1, 0))
    d["adx_di_direction"] = adx_dir
    d["adx_di_buy_flag"] = (adx_dir == 1).astype(int)
    d["adx_di_sell_flag"] = (adx_dir == -1).astype(int)
    d["adx_di_neutral_flag"] = (adx_dir == 0).astype(int)

    def sh(x, k):
        s = pd.Series(x).shift(k)
        return s.to_numpy()
    # 4) ADX historical (causal shifts)
    for k in (1, 2, 3, 4):
        d[f"adx_prev_{k}"] = sh(adx, k)
    d["plus_di_prev_1"] = sh(pdi, 1); d["minus_di_prev_1"] = sh(ndi, 1)
    d["di_diff_prev_1"] = sh(di_diff, 1); d["dx_prev_1"] = sh(d["dx_value"], 1)
    # 5) ADX slopes
    for k in (1, 2, 3, 4):
        d[f"adx_slope_{k}"] = adx - d[f"adx_prev_{k}"]
    d["plus_di_slope_1"] = pdi - d["plus_di_prev_1"]; d["plus_di_slope_3"] = pdi - sh(pdi, 3)
    d["minus_di_slope_1"] = ndi - d["minus_di_prev_1"]; d["minus_di_slope_3"] = ndi - sh(ndi, 3)
    d["di_diff_slope_1"] = di_diff - d["di_diff_prev_1"]; d["di_diff_slope_3"] = di_diff - sh(di_diff, 3)
    d["dx_slope_1"] = d["dx_value"] - d["dx_prev_1"]; d["dx_slope_3"] = d["dx_value"] - sh(d["dx_value"], 3)
    d["adx_rising"] = (d["adx_slope_1"] > 0).astype(int)
    d["adx_falling"] = (d["adx_slope_1"] < 0).astype(int)
    d["adx_flat"] = (d["adx_slope_1"] == 0).astype(int)
    d["plus_di_rising"] = (d["plus_di_slope_1"] > 0).astype(int)
    d["minus_di_rising"] = (d["minus_di_slope_1"] > 0).astype(int)
    prev_abs = sh(d["abs_di_diff"], 1)
    d["di_spread_expanding"] = (d["abs_di_diff"] > prev_abs).astype(int)
    d["di_spread_contracting"] = (d["abs_di_diff"] < prev_abs).astype(int)
    # 6) DI crossover
    prev_diff = d["di_diff_prev_1"]
    d["di_cross_up"] = ((di_diff > 0) & (prev_diff <= 0)).astype(int)
    d["di_cross_down"] = ((di_diff < 0) & (prev_diff >= 0)).astype(int)
    d["bars_since_di_cross"] = _bars_since_true((d["di_cross_up"] | d["di_cross_down"]).astype(bool))
    d["bars_since_plus_di_became_dominant"] = _bars_since_true(d["di_cross_up"].astype(bool))
    d["bars_since_minus_di_became_dominant"] = _bars_since_true(d["di_cross_down"].astype(bool))
    d["di_direction_persistence"] = _persistence(adx_dir)
    # 7) ADX bands (analysis only)
    band = np.where(adx < 20, "LOW", np.where(adx < 25, "EMERGING",
            np.where(adx < 35, "GOOD", np.where(adx < 50, "STRONG", "EXTREME"))))
    d["adx_band"] = band
    d["adx_below_20"] = (adx < 20).astype(int); d["adx_20_25"] = ((adx >= 20) & (adx < 25)).astype(int)
    d["adx_25_35"] = ((adx >= 25) & (adx < 35)).astype(int); d["adx_35_50"] = ((adx >= 35) & (adx < 50)).astype(int)
    d["adx_above_50"] = (adx >= 50).astype(int)
    # 8) ADX scores
    d["adx_score_direction_only"] = np.sign(di_diff)
    d["adx_score_di_diff"] = di_diff / 100.0
    strength = np.clip(adx / 25.0, 0.0, 2.0)
    d["adx_score_strength_weighted"] = np.clip((di_diff / 100.0) * strength, -CLIP_DIST, CLIP_DIST)
    slope_factor = 1 + np.clip(d["adx_slope_1"] / 10.0, -0.5, 0.5)
    d["adx_score_slope_adjusted"] = d["adx_score_strength_weighted"] * slope_factor
    # 9) SMMA raw
    sH, sL = a["smma_high"], a["smma_low"]
    sM = (sH + sL) / 2.0; bw = sH - sL
    d["smma_high"] = sH; d["smma_low"] = sL; d["smma_mid"] = sM
    d["smma_band_width"] = bw
    with np.errstate(divide="ignore", invalid="ignore"):
        d["smma_band_width_pct"] = np.where(c != 0, bw / c * 100.0, 0.0)
    d["smma_period"] = 2; d["smma_method"] = "SMMA"
    d["smma_price_source_high"] = "PRICE_HIGH"; d["smma_price_source_low"] = "PRICE_LOW"
    # 10) price distance from SMMA
    d["price_minus_smma_high"] = c - sH; d["price_minus_smma_low"] = c - sL
    d["price_minus_smma_mid"] = c - sM
    with np.errstate(divide="ignore", invalid="ignore"):
        d["price_to_smma_high_pct"] = np.where(c != 0, (c - sH) / c * 100.0, 0.0)
        d["price_to_smma_low_pct"] = np.where(c != 0, (c - sL) / c * 100.0, 0.0)
        d["price_to_smma_mid_pct"] = np.where(c != 0, (c - sM) / c * 100.0, 0.0)
    d["distance_above_band"] = np.maximum(c - sH, 0.0)
    d["distance_below_band"] = np.maximum(sL - c, 0.0)
    d["distance_inside_band"] = np.where((c <= sH) & (c >= sL), 1, 0)
    smma_dir = np.where(c > sH, 1, np.where(c < sL, -1, 0))
    d["smma_direction"] = smma_dir
    d["smma_buy_flag"] = (smma_dir == 1).astype(int)
    d["smma_sell_flag"] = (smma_dir == -1).astype(int)
    d["smma_neutral_flag"] = (smma_dir == 0).astype(int)
    # 11) SMMA slopes
    for k in (1, 2, 3, 4):
        d[f"smma_high_prev_{k}"] = sh(sH, k); d[f"smma_low_prev_{k}"] = sh(sL, k)
    d["smma_mid_prev_1"] = sh(sM, 1); d["smma_mid_prev_3"] = sh(sM, 3)
    for k in (1, 2, 3, 4):
        d[f"smma_high_slope_{k}"] = sH - d[f"smma_high_prev_{k}"]
        d[f"smma_low_slope_{k}"] = sL - d[f"smma_low_prev_{k}"]
    d["smma_mid_slope_1"] = sM - d["smma_mid_prev_1"]; d["smma_mid_slope_3"] = sM - d["smma_mid_prev_3"]
    d["smma_band_width_slope_1"] = bw - sh(bw, 1); d["smma_band_width_slope_3"] = bw - sh(bw, 3)
    with np.errstate(divide="ignore", invalid="ignore"):
        d["smma_high_slope_pct_1"] = np.where(sH != 0, d["smma_high_slope_1"] / np.abs(sH) * 100.0, 0.0)
        d["smma_low_slope_pct_1"] = np.where(sL != 0, d["smma_low_slope_1"] / np.abs(sL) * 100.0, 0.0)
        d["smma_mid_slope_pct_1"] = np.where(sM != 0, d["smma_mid_slope_1"] / np.abs(sM) * 100.0, 0.0)
    # 12) SMMA structure
    d["smma_both_rising"] = ((d["smma_high_slope_1"] > 0) & (d["smma_low_slope_1"] > 0)).astype(int)
    d["smma_both_falling"] = ((d["smma_high_slope_1"] < 0) & (d["smma_low_slope_1"] < 0)).astype(int)
    d["smma_band_expanding"] = (d["smma_band_width_slope_1"] > 0).astype(int)
    d["smma_band_contracting"] = (d["smma_band_width_slope_1"] < 0).astype(int)
    d["smma_lines_diverging"] = d["smma_band_expanding"]
    d["smma_lines_converging"] = d["smma_band_contracting"]
    d["smma_slope_agreement"] = (np.sign(d["smma_high_slope_1"]) == np.sign(d["smma_low_slope_1"])).astype(int)
    # 13) SMMA cross / transition
    prev_c = sh(c, 1); prev_sH = sh(sH, 1); prev_sL = sh(sL, 1)
    d["price_cross_above_smma_high"] = ((c > sH) & (prev_c <= prev_sH)).astype(int)
    d["price_cross_below_smma_low"] = ((c < sL) & (prev_c >= prev_sL)).astype(int)
    inside = ((c <= sH) & (c >= sL))
    prev_inside = ((prev_c <= prev_sH) & (prev_c >= prev_sL))
    d["price_entered_smma_band"] = (inside & ~prev_inside).astype(int)
    d["price_exited_smma_band_up"] = ((c > sH) & prev_inside).astype(int)
    d["price_exited_smma_band_down"] = ((c < sL) & prev_inside).astype(int)
    d["bars_since_price_above_band"] = _bars_since_true((c > sH))
    d["bars_since_price_below_band"] = _bars_since_true((c < sL))
    d["bars_since_price_inside_band"] = _bars_since_true(inside)
    d["bars_since_smma_direction_flip"] = _bars_since_flip(smma_dir)
    d["smma_direction_persistence"] = _persistence(smma_dir)
    # 14) SMMA scores
    d["smma_score_direction_only"] = smma_dir
    dist = np.where(c > sH, (c - sH) / np.where(c != 0, c, 1) * 100.0,
             np.where(c < sL, -((sL - c) / np.where(c != 0, c, 1) * 100.0), 0.0))
    d["smma_score_distance"] = np.clip(dist, -CLIP_DIST, CLIP_DIST)
    d["smma_score_slope_adjusted"] = smma_dir * (1 + np.clip(d["smma_mid_slope_1"] / 10.0, -0.5, 0.5))
    d["smma_score_band_adjusted"] = smma_dir * (1 + np.clip(d["smma_band_width_pct"] / 2.0, 0.0, 1.0))
    # 15) ADX-SMMA relationship (this TF)
    agree = (adx_dir == smma_dir) & (adx_dir != 0)
    disagree = (adx_dir != 0) & (smma_dir != 0) & (adx_dir != smma_dir)
    d["adx_smma_agree"] = agree.astype(int); d["adx_smma_disagree"] = disagree.astype(int)
    d["adx_smma_both_buy"] = ((adx_dir == 1) & (smma_dir == 1)).astype(int)
    d["adx_smma_both_sell"] = ((adx_dir == -1) & (smma_dir == -1)).astype(int)
    d["adx_buy_smma_neutral"] = ((adx_dir == 1) & (smma_dir == 0)).astype(int)
    d["adx_sell_smma_neutral"] = ((adx_dir == -1) & (smma_dir == 0)).astype(int)
    d["smma_buy_adx_sell"] = ((smma_dir == 1) & (adx_dir == -1)).astype(int)
    d["smma_sell_adx_buy"] = ((smma_dir == -1) & (adx_dir == 1)).astype(int)
    tf_comb = 0.5 * smma_dir + 0.5 * adx_dir
    d["tf_combined_score"] = tf_comb
    d["tf_combined_direction"] = np.sign(tf_comb)
    d["tf_agreement_count"] = ((smma_dir == np.sign(tf_comb)).astype(int)
                               + (adx_dir == np.sign(tf_comb)).astype(int)) * (np.sign(tf_comb) != 0)
    d["tf_disagreement_flag"] = disagree.astype(int)
    # 17) trend age (this TF)
    d["bars_since_adx_direction_flip"] = _bars_since_flip(adx_dir)
    d["bars_since_adx_smma_first_agreement"] = _bars_since_true(agree.to_numpy() if hasattr(agree, "to_numpy") else np.asarray(agree))
    # 18) score change (this TF)
    fs_tf = tf_comb
    d["adx_score_change_1"] = d["adx_score_strength_weighted"] - sh(d["adx_score_strength_weighted"], 1)
    d["adx_score_change_3"] = d["adx_score_strength_weighted"] - sh(d["adx_score_strength_weighted"], 3)
    d["adx_score_slope_3"] = d["adx_score_change_3"] / 3.0
    d["smma_score_change_1"] = d["smma_score_direction_only"] - sh(d["smma_score_direction_only"], 1)
    d["smma_score_change_3"] = d["smma_score_direction_only"] - sh(d["smma_score_direction_only"], 3)
    d["smma_score_slope_3"] = d["smma_score_change_3"] / 3.0
    d["final_score_change_1"] = fs_tf - sh(fs_tf, 1)
    d["final_score_change_3"] = fs_tf - sh(fs_tf, 3)
    d["final_score_slope_3"] = d["final_score_change_3"] / 3.0
    d["final_score_acceleration"] = d["final_score_change_1"] - sh(d["final_score_change_1"], 1)
    # 19) partial HTF update (inside current candle) -- only meaningful for HTF
    d["partial_high_change"] = h - sh(h, 1)
    d["partial_low_change"] = l - sh(l, 1)
    d["partial_close_change"] = c - sh(c, 1)
    d["partial_volume_change"] = v - sh(v, 1)
    same_candle = (a["ncomp"] > 1)
    d["adx_change_inside_current_htf_candle"] = np.where(same_candle, adx - sh(adx, 1), 0.0)
    d["plus_di_change_inside_current_htf_candle"] = np.where(same_candle, pdi - sh(pdi, 1), 0.0)
    d["minus_di_change_inside_current_htf_candle"] = np.where(same_candle, ndi - sh(ndi, 1), 0.0)
    d["smma_high_change_inside_current_htf_candle"] = np.where(same_candle, sH - sh(sH, 1), 0.0)
    d["smma_low_change_inside_current_htf_candle"] = np.where(same_candle, sL - sh(sL, 1), 0.0)
    d["smma_mid_change_inside_current_htf_candle"] = np.where(same_candle, sM - sh(sM, 1), 0.0)
    if tf == "H4":
        d["h4_snapshot_number"] = a["ncomp"]
        d["h4_snapshot_progress_pct"] = a["ncomp"] / 16.0
    return pd.DataFrame(d)


# ─────────────────────────────────────────────────────────────────────────
# Aggregate (M15-decision level) across the 4 timeframes
# ─────────────────────────────────────────────────────────────────────────
def build_aggregate(frames):
    n = len(frames["M15"])
    agg = {"decision_time": frames["M15"]["decision_time"].to_numpy()}
    smma_d = {tf: frames[tf]["smma_direction"].to_numpy() for tf in TFS}
    adx_d = {tf: frames[tf]["adx_di_direction"].to_numpy() for tf in TFS}
    comb_d = {tf: frames[tf]["tf_combined_direction"].to_numpy() for tf in TFS}
    S = np.column_stack([smma_d[tf] for tf in TFS])
    A = np.column_stack([adx_d[tf] for tf in TFS])
    agg["smma_buy_count"] = (S == 1).sum(1); agg["smma_sell_count"] = (S == -1).sum(1)
    agg["smma_neutral_count"] = (S == 0).sum(1)
    agg["adx_buy_count"] = (A == 1).sum(1); agg["adx_sell_count"] = (A == -1).sum(1)
    agg["adx_neutral_count"] = (A == 0).sum(1)
    agg["smma_total_score"] = np.nanmean(S, axis=1)
    agg["adx_total_score"] = np.nanmean(A, axis=1)
    agg["final_combined_score"] = 0.5 * agg["smma_total_score"] + 0.5 * agg["adx_total_score"]
    # agreement between the two indicators per TF, counted across TFs
    per_tf_agree = np.column_stack([(S[:, j] == A[:, j]) & (S[:, j] != 0) for j in range(4)])
    agg["full_agreement_count"] = per_tf_agree.sum(1)
    agg["direction_agreement_count"] = per_tf_agree.sum(1)
    agg["direction_disagreement_count"] = np.column_stack(
        [(S[:, j] != 0) & (A[:, j] != 0) & (S[:, j] != A[:, j]) for j in range(4)]).sum(1)
    Cd = np.column_stack([comb_d[tf] for tf in TFS])
    agg["all_4_buy"] = (Cd == 1).all(1).astype(int); agg["all_4_sell"] = (Cd == -1).all(1).astype(int)
    agg["three_of_4_buy"] = ((Cd == 1).sum(1) == 3).astype(int)
    agg["three_of_4_sell"] = ((Cd == -1).sum(1) == 3).astype(int)
    agg["two_of_4_buy"] = ((Cd == 1).sum(1) == 2).astype(int)
    agg["two_of_4_sell"] = ((Cd == -1).sum(1) == 2).astype(int)
    idx = {tf: j for j, tf in enumerate(TFS)}

    def pair(x, y):
        return ((Cd[:, idx[x]] == Cd[:, idx[y]]) & (Cd[:, idx[x]] != 0)).astype(int)
    agg["m15_h1_agreement"] = pair("M15", "H1"); agg["m15_h4_agreement"] = pair("M15", "H4")
    agg["h1_h4_agreement"] = pair("H1", "H4"); agg["m30_h1_agreement"] = pair("M30", "H1")
    agg["smma_aligned_tf_count"] = np.maximum((S == 1).sum(1), (S == -1).sum(1))
    agg["adx_aligned_tf_count"] = np.maximum((A == 1).sum(1), (A == -1).sum(1))
    agg["combined_aligned_tf_count"] = np.maximum((Cd == 1).sum(1), (Cd == -1).sum(1))
    # trend age (aggregate)
    full_align = ((Cd == 1).all(1) | (Cd == -1).all(1))
    three_align = (((Cd == 1).sum(1) >= 3) | ((Cd == -1).sum(1) >= 3))
    agg["bars_since_full_alignment"] = _bars_since_true(full_align)
    agg["bars_since_3_of_4_alignment"] = _bars_since_true(three_align)
    agg["alignment_age"] = _persistence(np.where(full_align, 1, 0))
    agg["alignment_persistence"] = _persistence(agg["combined_aligned_tf_count"])
    # aggregate score change
    fcs = agg["final_combined_score"]
    agg["final_score_change_1"] = fcs - pd.Series(fcs).shift(1).to_numpy()
    agg["final_score_change_3"] = fcs - pd.Series(fcs).shift(3).to_numpy()
    agg["final_score_slope_3"] = agg["final_score_change_3"] / 3.0
    agg["final_score_acceleration"] = agg["final_score_change_1"] - pd.Series(agg["final_score_change_1"]).shift(1).to_numpy()
    return pd.DataFrame(agg)


# ─────────────────────────────────────────────────────────────────────────
def leakage_audit(base, arrays, sample_idx):
    """Brute-force recheck: partial HTF candle uses only M15 bars <= decision bar."""
    mo = base["time"].values.astype("datetime64[ns]")
    O = base["open"].to_numpy(float); H = base["high"].to_numpy(float)
    L = base["low"].to_numpy(float);  C = base["close"].to_numpy(float)
    rows = []; bad = 0
    for tf in ["M30", "H1", "H4"]:
        a = arrays[tf]
        for i in sample_idx:
            ps = a["pstart"][i]
            if np.isnat(ps):
                continue
            m = (mo >= ps) & (np.arange(len(mo)) <= i)
            if not m.any():
                continue
            exp_o = O[m][0]; exp_h = H[m].max(); exp_l = L[m].min(); exp_c = C[i]
            last_used = int(np.where(m)[0].max())
            ok = (abs(a["o"][i]-exp_o) < 1e-6 and abs(a["h"][i]-exp_h) < 1e-6
                  and abs(a["l"][i]-exp_l) < 1e-6 and abs(a["c"][i]-exp_c) < 1e-6
                  and a["ncomp"][i] == int(m.sum()) and last_used == i)
            if not ok:
                bad += 1
            rows.append({"timeframe": tf, "decision_bar": i,
                         "decision_time": str(pd.Timestamp(mo[i]) + pd.Timedelta(minutes=15)),
                         "period_start": str(pd.Timestamp(ps)),
                         "n_completed": int(a["ncomp"][i]),
                         "last_m15_index_used": last_used, "is_last_bar_i": last_used == i,
                         "partial_high_ok": abs(a["h"][i]-exp_h) < 1e-6,
                         "partial_low_ok": abs(a["l"][i]-exp_l) < 1e-6,
                         "no_future_used": last_used == i, "PASS": ok})
    return pd.DataFrame(rows), bad


def data_dictionary(frames, agg):
    """One row per column: source / formula-ish / causal / used_for_entry / analysis."""
    rows = []
    ENTRY = {"smma_score_direction_only", "adx_score_direction_only", "smma_direction",
             "adx_di_direction", "smma_total_score", "adx_total_score", "final_combined_score"}
    for tf in TFS:
        for col in frames[tf].columns:
            causal = "post_trade" if col in ("decision_time",) else "causal"
            rows.append({"column_name": col, "timeframe": tf,
                         "source": "M15 base (forming partial candle)" if tf != "M15" else "M15 closed",
                         "formula": "see spec section", "unit": _unit(col),
                         "causal_or_post_trade": causal,
                         "used_for_entry": int(col in ENTRY),
                         "used_for_analysis_only": int(col not in ENTRY)})
    for col in agg.columns:
        rows.append({"column_name": col, "timeframe": "AGGREGATE",
                     "source": "4-TF aggregate", "formula": "see spec section 16-18",
                     "unit": _unit(col), "causal_or_post_trade": "causal",
                     "used_for_entry": int(col in ("smma_total_score", "adx_total_score", "final_combined_score")),
                     "used_for_analysis_only": int(col not in ("smma_total_score", "adx_total_score", "final_combined_score"))})
    return pd.DataFrame(rows)


def _unit(col):
    if col.endswith("_pct") or "pct" in col: return "percent"
    if "time" in col or col.endswith("_start") or col.endswith("_close"): return "datetime"
    if col.endswith(("_flag", "_rising", "_falling", "_flat", "_up", "_down", "_buy", "_sell",
                     "_agree", "_disagree", "_expanding", "_contracting", "_diverging", "_converging")):
        return "bool"
    if "count" in col or "bars_since" in col or "persistence" in col or "number" in col: return "count"
    if col in ("adx_band", "timeframe", "smma_method", "smma_price_source_high",
               "smma_price_source_low"): return "category"
    if "direction" in col or "score" in col: return "signed"
    return "price"


# ─────────────────────────────────────────────────────────────────────────
def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-04-01")
    ap.add_argument("--end", default="2026-06-29")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    out_dir = Path(args.out_dir) if args.out_dir else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("SMMA + ADX-DI LIVE SNAPSHOT LOGGER (forming candles, no AI, no entry)")
    print("=" * 70)
    print("  - FORMING partial M30/H1/H4 candle rebuilt from completed M15 bars only")
    print("  - no future HTF high/low/close/volume; no backward-fill; no shift(-1)")
    print("  - RAW DATA CAPTURE only: NOT used for entry decisions (section 22)")
    print("  - fully isolated: no model / win_prob / HMM / threshold / news / slot")
    print("-" * 70)

    ohlc = load_ohlc_vol()
    ds, de = pd.to_datetime(args.start), pd.to_datetime(args.end)
    base = ohlc[ohlc["time"] <= de].reset_index(drop=True)
    print(f"Data: {len(base):,} M15 bars (warmup incl.) | window {ds.date()} -> {de.date()}")

    arrays = {}
    print("Building forming per-TF arrays...")
    for tf in TFS:
        arrays[tf] = forming_tf_arrays(base, tf, ADX_PERIOD)
    print("Building per-TF field frames (sections 1-19)...")
    frames = {tf: build_tf_frame(base, tf, arrays[tf]) for tf in TFS}
    print("Building aggregate (sections 16-18)...")
    agg = build_aggregate(frames)

    # window mask (write only in-window rows; computed with full warmup history)
    dt = frames["M15"]["signal_bar_open_time"]
    mask = (dt >= ds) & (dt <= de)
    idx_full = np.where(mask.to_numpy())[0]

    # leakage audit (rule 8)
    rng = np.random.default_rng(7)
    lo_i = max(int(idx_full[0]), 40); hi_i = int(idx_full[-1])
    sample = rng.integers(lo_i, hi_i, size=min(300, max(1, hi_i - lo_i)))
    audit_df, bad = leakage_audit(base, arrays, sample)
    print(f"Leakage audit: {len(sample)} bars x 3 HTFs -> "
          f"{'PASS (0)' if bad == 0 else f'FAIL ({bad})'}")
    if bad:
        print("  ABORTING: forming reconstruction failed no-lookahead assertion.")
        return

    # write per-TF + combined + aggregate
    for tf in TFS:
        frames[tf].iloc[idx_full].to_csv(out_dir / f"smma_adx_snapshot_{tf}.csv", index=False)
    allf = pd.concat([frames[tf].iloc[idx_full] for tf in TFS], ignore_index=True)
    allf.to_csv(out_dir / "smma_adx_snapshot_all.csv", index=False)
    agg.iloc[idx_full].to_csv(out_dir / "smma_adx_aggregate_scores.csv", index=False)
    audit_df.to_csv(out_dir / "smma_adx_leakage_audit.csv", index=False)

    # transition events (any cross / flip on any TF)
    ev = []
    for tf in TFS:
        f = frames[tf].iloc[idx_full]
        e = f[(f["di_cross_up"] == 1) | (f["di_cross_down"] == 1)
              | (f["price_cross_above_smma_high"] == 1) | (f["price_cross_below_smma_low"] == 1)]
        for _, r in e.iterrows():
            ev.append({"decision_time": r["decision_time"], "timeframe": tf,
                       "di_cross_up": r["di_cross_up"], "di_cross_down": r["di_cross_down"],
                       "price_cross_above_smma_high": r["price_cross_above_smma_high"],
                       "price_cross_below_smma_low": r["price_cross_below_smma_low"],
                       "adx_value": r["adx_value"], "di_diff": r["di_diff"],
                       "smma_direction": r["smma_direction"], "adx_di_direction": r["adx_di_direction"]})
    pd.DataFrame(ev).to_csv(out_dir / "smma_adx_transition_events.csv", index=False)

    # data dictionary
    data_dictionary(frames, agg).to_csv(out_dir / "smma_adx_data_dictionary.csv", index=False)

    # report
    rep = []
    rep.append("=" * 70)
    rep.append("SMMA + ADX-DI SNAPSHOT LOGGER - REPORT")
    rep.append(f"Window {ds.date()} -> {de.date()} | rows/TF: {len(idx_full):,} | ADX P={ADX_PERIOD}")
    rep.append(f"Total per-TF columns: {frames['M15'].shape[1]} | aggregate columns: {agg.shape[1]}")
    rep.append(f"Leakage audit: PASS (0 mismatches over {len(sample)} sampled bars x 3 HTFs)")
    rep.append("-" * 70)
    a4 = agg.iloc[idx_full]
    rep.append("AGGREGATE ALIGNMENT SNAPSHOT (in-window):")
    rep.append(f"  all_4_buy rows : {int(a4['all_4_buy'].sum())} | all_4_sell rows: {int(a4['all_4_sell'].sum())}")
    rep.append(f"  3-of-4 buy     : {int(a4['three_of_4_buy'].sum())} | 3-of-4 sell   : {int(a4['three_of_4_sell'].sum())}")
    rep.append(f"  mean final_combined_score: {a4['final_combined_score'].mean():+.3f}")
    rep.append("-" * 70)
    rep.append("H4 forming evolution check (partial_bar_number distribution, H4 file):")
    h4 = frames["H4"].iloc[idx_full]
    rep.append("  " + h4["partial_bar_number"].value_counts().sort_index().to_string().replace("\n", "\n  "))
    rep.append("-" * 70)
    rep.append("NOTE: RAW DATA CAPTURE ONLY. Entry decisions use only baseline direction")
    rep.append("scores (see research_smma_adx_score_sweep.py). All slope/distance/")
    rep.append("persistence/band/transition fields are used_for_entry=0 (analysis / future")
    rep.append("AI features), per the data dictionary.")
    rep.append("=" * 70)
    report = "\n".join(rep)
    print("\n" + report)
    (out_dir / "smma_adx_snapshot_report.txt").write_text(report, encoding="utf-8")
    print(f"\nSaved 10 files to {out_dir}")


if __name__ == "__main__":
    main()
