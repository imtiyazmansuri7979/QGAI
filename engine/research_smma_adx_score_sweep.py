"""
research_smma_adx_score_sweep.py
================================
STANDALONE rule-based research bot. Finds the RAW edge of the 2-SMMA
(20SMA_TrendSignals_Hybrid.mq5) and ADX-DI logic, with NO AI model, NO
win_prob, NO 67-feature logic, NO HMM entry gate, NO probability threshold,
NO news/slot/hard-ADX filter. Two independent scores only, swept over all 15
non-empty timeframe sets (M15/M30/H1/H4) to find which timeframe combination
carries the edge. The winner logic later seeds compact AI features.

ISOLATION GUARANTEE
  - Loads ONLY OHLC (data/merged/ohlc_merged.csv). No model file is ever loaded
    or written. inference.py / bridge_main.py / train.py are never imported.
  - Reuses (read-only) two trusted, model-free helpers:
      trend_signal.compute_trend / resample_ohlc  (exact .mq5 SMMA port)
      analyze_capture.htf_lines / BUF / SLMIN / TPCAP  (the trusted exit engine)
  - Writes only into backtest/results/smma_adx_score_sweep/. Existing production
    code and the live bot are unaffected; safe to run while the bot trades.

LEAKAGE SAFETY (printed again at startup)
  - Every higher-timeframe value (SMMA trend, +DI/-DI/ADX) is taken from the last
    FULLY CLOSED HTF candle at the M15 decision bar's close -- never the forming
    candle. Mapping is searchsorted(tf_close_time, m15_close_time, 'right') - 1.
  - Entry fills at NEXT M15 bar open + spread (no same-bar lookahead).
  - No full-dataset / future normalization; ADX version B/C use a FIXED bounded
    clip only. No future swing / high / low / exit outcome enters any entry score.

Run:  python research_smma_adx_score_sweep.py [--config config_smma_adx_sweep.json]
                                              [--smoke] [--families ...]
                                              [--start YYYY-MM-DD --end YYYY-MM-DD]
                                              [--benchmark]   (time ONE config, extrapolate)
"""
import argparse, json, sys, io, traceback
import numpy as np
import pandas as pd
from pathlib import Path
from itertools import combinations

from trend_signal import compute_trend, resample_ohlc
from analyze_capture import load_ohlc, htf_lines, BUF, SLMIN, TPCAP, OHLC_CSV

ENGINE = Path(__file__).resolve().parent
OUT_DIR = ENGINE.parent / "backtest" / "results" / "smma_adx_score_sweep"
TF_MIN = {"M15": 15, "M30": 30, "H1": 60, "H4": 240}
TF_RULE = {"M30": "30min", "H1": "1h", "H4": "4h"}


# ─────────────────────────────────────────────────────────────────────────
# Leakage-safe per-timeframe indicators (SMMA trend + ADX-DI), on M15 grid
# ─────────────────────────────────────────────────────────────────────────
def _ema_di_adx(h, l, c, period=14):
    """EMA +DI, -DI, ADX on bar arrays — matches mt5_data_updater / regen_adx_asof.
    Returns (pdi, ndi, adx), nan-padded, aligned to input bars (index 0 = nan)."""
    n = len(c)
    nan = np.full(n, np.nan)
    if n < period * 2 + 2:
        return nan, nan.copy(), nan.copy()
    up = h[1:] - h[:-1]
    dn = l[:-1] - l[1:]
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    atr  = pd.Series(tr).ewm(span=period, adjust=False).mean().to_numpy()
    spdm = pd.Series(pdm).ewm(span=period, adjust=False).mean().to_numpy()
    sndm = pd.Series(ndm).ewm(span=period, adjust=False).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100 * spdm / (atr + 1e-9)
        ndi = 100 * sndm / (atr + 1e-9)
        dx = 100 * np.abs(pdi - ndi) / (pdi + ndi + 1e-9)
    adx = pd.Series(dx).ewm(span=period, adjust=False).mean().to_numpy()
    lead = np.array([np.nan])
    return (np.concatenate([lead, pdi]), np.concatenate([lead, ndi]),
            np.concatenate([lead, adx]))


def _map_to_m15(tf_close_times, tf_vals, m15_close_times):
    """Last fully-closed HTF value at each M15 bar close (leakage-safe)."""
    idx = np.searchsorted(tf_close_times, m15_close_times, side="right") - 1
    out = np.full(len(m15_close_times), np.nan)
    valid = idx >= 0
    out[valid] = tf_vals[idx[valid]]
    return out


def _ema_state(h, l, c, period=14):
    """Per-CLOSED-bar EMA accumulators, bar-aligned (index 0 = nan).
    Returns sTR, sPDM, sNDM, adx arrays so a FORMING bar can be updated in O(1)
    from the previous closed bar's state. Matches mt5_data_updater EMA formula."""
    n = len(c)
    nan = np.full(n, np.nan)
    if n < period * 2 + 2:
        return nan, nan.copy(), nan.copy(), nan.copy()
    up = h[1:] - h[:-1]; dn = l[:-1] - l[1:]
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    atr  = pd.Series(tr).ewm(span=period, adjust=False).mean().to_numpy()
    spdm = pd.Series(pdm).ewm(span=period, adjust=False).mean().to_numpy()
    sndm = pd.Series(ndm).ewm(span=period, adjust=False).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100 * spdm / (atr + 1e-9); ndi = 100 * sndm / (atr + 1e-9)
        dx = 100 * np.abs(pdi - ndi) / (pdi + ndi + 1e-9)
    adx = pd.Series(dx).ewm(span=period, adjust=False).mean().to_numpy()
    lead = np.array([np.nan])
    return (np.concatenate([lead, atr]), np.concatenate([lead, spdm]),
            np.concatenate([lead, sndm]), np.concatenate([lead, adx]))


def _resample_ohlcv(base, rule):
    """Clock-aligned HTF candles WITH cumulative volume (open time = period start)."""
    d = base.set_index(pd.to_datetime(base["time"]))
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "tick_volume" in base.columns:
        agg["tick_volume"] = "sum"
    r = d.resample(rule, label="left", closed="left").agg(agg).dropna(subset=["open"])
    return r.reset_index().rename(columns={"index": "time"})


def build_forming_indicators(base, smma_mode, adx_period):
    """FORMING mode: at every M15 bar, reconstruct the PARTIAL (still-forming)
    M30/H1/H4 candle from ONLY the M15 candles completed so far, and recompute
    the HTF SMMA trend + ADX/+DI/-DI on [prev CLOSED HTF candles] + [this partial
    candle]. Reproduces the live evolving indicator (16 distinct H4 snapshots per
    H4 period). No future data of the current HTF candle enters any snapshot.
    Returns (smma, di, audit) with the same array shapes as build_indicators()."""
    n = len(base)
    mo = base["time"].values.astype("datetime64[ns]")             # M15 open times
    O = base["open"].to_numpy(float); H = base["high"].to_numpy(float)
    L = base["low"].to_numpy(float);  C = base["close"].to_numpy(float)
    V = (base["tick_volume"].to_numpy(float) if "tick_volume" in base.columns
         else np.zeros(n))
    smma, di, audit = {}, {}, {}

    # ── M15 itself: standard closed-bar values (no sub-bars to reconstruct) ──
    m15_tr = compute_trend(base, period=2, method="SMMA", ratchet=True)["trend"].to_numpy(float)
    if smma_mode == "memoryless_3state":
        from trend_signal import _ma
        maH = _ma(H, 2, "SMMA"); maL = _ma(L, 2, "SMMA")
        m15_tr = np.zeros(n)
        m15_tr[1:] = np.where(C[1:] > maH[:-1], 1.0, np.where(C[1:] < maL[:-1], -1.0, 0.0))
    p15, n15, a15 = _ema_di_adx(H, L, C, adx_period)
    smma["M15"] = m15_tr
    di["M15"] = {"pdi": p15, "ndi": n15, "adx": a15}

    from trend_signal import _ma
    for tf in ["M30", "H1", "H4"]:
        htf = _resample_ohlcv(base, TF_RULE[tf])
        ho = htf["time"].values.astype("datetime64[ns]")          # HTF open times
        hh = htf["high"].to_numpy(float); hl = htf["low"].to_numpy(float)
        hc = htf["close"].to_numpy(float)
        # closed-HTF SMMA state
        maH = _ma(hh, 2, "SMMA"); maL = _ma(hl, 2, "SMMA")
        htrend = compute_trend(htf, period=2, method="SMMA", ratchet=True)["trend"].to_numpy(float)
        # closed-HTF EMA state
        sTR, sPDM, sNDM, cADX = _ema_state(hh, hl, hc, adx_period)

        # which forming HTF period each M15 bar is in (p), prev closed bar = p-1
        p_arr = np.searchsorted(ho, mo, side="right") - 1

        tr_out = np.full(n, np.nan)
        pdi_out = np.full(n, np.nan); ndi_out = np.full(n, np.nan); adx_out = np.full(n, np.nan)
        au_pstart = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]"); au_ncomp = np.zeros(n, int)
        au_o = np.full(n, np.nan); au_h = np.full(n, np.nan); au_l = np.full(n, np.nan)
        au_c = np.full(n, np.nan); au_v = np.full(n, np.nan)

        run_hi = run_lo = run_vol = np.nan; per_open = np.nan; ncomp = 0; cur_p = -1
        for i in range(n):
            p = int(p_arr[i])
            if p != cur_p:                       # entered a new forming HTF period
                cur_p = p; per_open = O[i]; run_hi = H[i]; run_lo = L[i]
                run_vol = V[i]; ncomp = 1
            else:
                run_hi = max(run_hi, H[i]); run_lo = min(run_lo, L[i])
                run_vol += V[i]; ncomp += 1
            au_pstart[i] = ho[p] if p >= 0 else np.datetime64("NaT")
            au_ncomp[i] = ncomp
            au_o[i] = per_open; au_h[i] = run_hi; au_l[i] = run_lo
            au_c[i] = C[i]; au_v[i] = run_vol
            k = p - 1                            # previous CLOSED HTF bar
            if k < 0 or k >= len(maH) or np.isnan(maH[k]) or np.isnan(maL[k]):
                continue
            # ── forming SMMA trend (exact .mq5: close vs PREV closed bar MA) ──
            if smma_mode == "memoryless_3state":
                t = 1.0 if C[i] > maH[k] else (-1.0 if C[i] < maL[k] else 0.0)
            else:
                t = htrend[k]
                if C[i] > maH[k]: t = 1.0
                elif C[i] < maL[k]: t = -1.0
                if t == 0: t = 1.0 if C[i] >= per_open else -1.0
            tr_out[i] = t
            # ── forming ADX/+DI/-DI (one EMA step from closed bar k) ──
            if (k >= 1 and not np.isnan(sTR[k]) and not np.isnan(cADX[k])):
                up = run_hi - hh[k]; dnn = hl[k] - run_lo
                pdm = up if (up > dnn and up > 0) else 0.0
                ndm = dnn if (dnn > up and dnn > 0) else 0.0
                trv = max(run_hi - run_lo, abs(run_hi - hc[k]), abs(run_lo - hc[k]))
                _a = 2.0 / (adx_period + 1)
                sTR_f = (1 - _a) * sTR[k] + _a * trv
                sPDM_f = (1 - _a) * sPDM[k] + _a * pdm
                sNDM_f = (1 - _a) * sNDM[k] + _a * ndm
                if sTR_f > 0:
                    pdi_f = 100 * sPDM_f / sTR_f; ndi_f = 100 * sNDM_f / sTR_f
                    denom = pdi_f + ndi_f
                    dx_f = 100 * abs(pdi_f - ndi_f) / denom if denom > 0 else 0.0
                    adx_f = (1 - _a) * cADX[k] + _a * dx_f
                    pdi_out[i] = pdi_f; ndi_out[i] = ndi_f; adx_out[i] = adx_f
        smma[tf] = tr_out
        di[tf] = {"pdi": pdi_out, "ndi": ndi_out, "adx": adx_out}
        audit[tf] = {"period_start": au_pstart, "n_completed": au_ncomp,
                     "o": au_o, "h": au_h, "l": au_l, "c": au_c, "v": au_v}
    return smma, di, audit


def verify_no_lookahead(base, audit, sample_idx):
    """Rule 8: brute-force recompute the partial candle for sample M15 bars and
    assert it matches the incremental reconstruction AND uses no future M15 data."""
    mo = base["time"].values.astype("datetime64[ns]")
    O = base["open"].to_numpy(float); H = base["high"].to_numpy(float)
    L = base["low"].to_numpy(float);  C = base["close"].to_numpy(float)
    bad = 0
    for tf in ["M30", "H1", "H4"]:
        a = audit[tf]
        for i in sample_idx:
            ps = a["period_start"][i]
            if np.isnat(ps):
                continue
            m = (mo >= ps) & (np.arange(len(mo)) <= i)      # M15 bars in period, up to i (no future)
            if not m.any():
                continue
            exp_o = O[m][0]; exp_h = H[m].max(); exp_l = L[m].min(); exp_c = C[i]
            if (abs(a["o"][i]-exp_o) > 1e-6 or abs(a["h"][i]-exp_h) > 1e-6
                    or abs(a["l"][i]-exp_l) > 1e-6 or abs(a["c"][i]-exp_c) > 1e-6
                    or a["n_completed"][i] != int(m.sum())):
                bad += 1
            # hard no-lookahead check: last M15 bar used is bar i itself
            if np.where(m)[0].max() != i:
                bad += 1
    return bad


def build_indicators(base, smma_mode, adx_period):
    """Per-TF SMMA trend (+1/-1) and +DI/-DI/ADX, all mapped onto the M15 grid,
    leakage-safe. base: DataFrame time/open/high/low/close (M15, ascending)."""
    n = len(base)
    m15_close = base["time"].values.astype("datetime64[ns]") + np.timedelta64(15, "m")
    smma = {}   # tf -> trend array (+1/-1) on M15 grid
    di = {}     # tf -> dict(pdi, ndi, adx) on M15 grid
    for tf in ["M15", "M30", "H1", "H4"]:
        tfdf = base if tf == "M15" else resample_ohlc(base, TF_RULE[tf])
        tf_close = tfdf["time"].values.astype("datetime64[ns]") + np.timedelta64(TF_MIN[tf], "m")

        # ── SMMA trend (exact .mq5 port via compute_trend) ──
        tr = compute_trend(tfdf, period=2, method="SMMA", ratchet=True)
        trend = tr["trend"].to_numpy(float)
        if smma_mode == "memoryless_3state":
            # simple price-vs-band with a neutral zone (section-3 pseudocode variant)
            from trend_signal import _ma
            h = tfdf["high"].to_numpy(float); l = tfdf["low"].to_numpy(float)
            c = tfdf["close"].to_numpy(float)
            maH = _ma(h, 2, "SMMA"); maL = _ma(l, 2, "SMMA")
            mm = np.zeros(len(c))
            mm[1:] = np.where(c[1:] > maH[:-1], 1.0, np.where(c[1:] < maL[:-1], -1.0, 0.0))
            trend = mm
        smma[tf] = _map_to_m15(tf_close, trend, m15_close)

        # ── ADX-DI (EMA) on this TF's candles ──
        pdi, ndi, adx = _ema_di_adx(
            tfdf["high"].to_numpy(float), tfdf["low"].to_numpy(float),
            tfdf["close"].to_numpy(float), adx_period)
        di[tf] = {
            "pdi": _map_to_m15(tf_close, pdi, m15_close),
            "ndi": _map_to_m15(tf_close, ndi, m15_close),
            "adx": _map_to_m15(tf_close, adx, m15_close),
        }
    return smma, di


# ─────────────────────────────────────────────────────────────────────────
# Score builders (all normalized to [-1, 1], comparable across families)
# ─────────────────────────────────────────────────────────────────────────
def smma_score(smma, tf_set):
    """Equal-weight mean of per-TF stateful trend (+1/-1) -> [-1, 1]."""
    arrs = [smma[tf] for tf in tf_set]
    return np.nanmean(np.column_stack(arrs), axis=1)


def adx_score(di, tf_set, version, cfg):
    """Per-TF ADX-DI score (version A/B/C), equal-weight mean -> ~[-1, 1]."""
    per_tf = []
    for tf in tf_set:
        pdi, ndi, adx = di[tf]["pdi"], di[tf]["ndi"], di[tf]["adx"]
        diff = pdi - ndi
        if version == "A":                       # DI direction only
            s = np.sign(diff)
        elif version == "B":                     # raw DI diff, fixed bounded clip
            s = np.clip(diff, -cfg["adx_clip_B"], cfg["adx_clip_B"]) / cfg["adx_clip_B"]
        else:                                    # C: DI diff * ADX strength
            strength = np.clip(adx / cfg["adx_strength_div_C"], 0.0, cfg["adx_strength_cap_C"])
            s = np.clip((diff / 100.0) * strength, -1.0, 1.0)
        per_tf.append(s)
    return np.nanmean(np.column_stack(per_tf), axis=1)


# ─────────────────────────────────────────────────────────────────────────
# Trade simulation: entry policy + the trusted fixed exit engine
# ─────────────────────────────────────────────────────────────────────────
def simulate(final_score, base, buyH1, sellH1, flipH1, buyL, sellL,
             entry_mode, spread, warmup):
    """Walk M15 bars; entry from score direction, exit via the trusted engine
    (H1 line SL + one-way trail + flat TP cap + H1 flip). Non-overlapping,
    max_open=1. Returns list of trade dicts."""
    n = len(base)
    op = base["open"].to_numpy(float); hi = base["high"].to_numpy(float)
    lo = base["low"].to_numpy(float);  cl = base["close"].to_numpy(float)
    tm = base["time"]
    sdir = np.sign(np.nan_to_num(final_score, nan=0.0)).astype(int)

    trades = []
    last_dir = 0
    i = max(warmup, 1)
    while i < n - 1:
        d = sdir[i]
        take = (d != 0) and (d != last_dir if entry_mode == "A" else True)
        if not take:
            i += 1
            continue
        # ── entry: fill NEXT bar open + spread ──
        i0 = i + 1
        if i0 >= n - 1:
            break
        sgn = d
        entry = op[i0] + sgn * spread
        buf_abs = entry * BUF / 100.0
        line = buyH1[i0] if sgn > 0 else sellH1[i0]
        if line is None or np.isnan(line):
            line = buyL[i0] if sgn > 0 else sellL[i0]
        if line is None or np.isnan(line):
            i += 1
            continue
        vsl = line - sgn * buf_abs
        min_dist = entry * SLMIN / 100.0
        if abs(entry - vsl) < min_dist:
            vsl = entry - sgn * min_dist
        sl_dist = abs(entry - vsl)
        if sl_dist <= 0:
            i += 1
            continue
        tp = entry + sgn * entry * TPCAP / 100.0

        exit_px = exit_rsn = exit_bar = None
        trailing = False
        mfe = mae = 0.0
        for j in range(i0 + 1, n):
            fav = (cl[j] - entry) * sgn
            mfe = max(mfe, (hi[j] - entry) * sgn if sgn > 0 else (entry - lo[j]) * sgn)
            mae = min(mae, (lo[j] - entry) * sgn if sgn > 0 else (entry - hi[j]) * sgn)
            if (sgn > 0 and lo[j] <= vsl) or (sgn < 0 and hi[j] >= vsl):
                exit_px = vsl; exit_rsn = "TRAIL" if trailing else "SL"; exit_bar = j; break
            if (sgn > 0 and hi[j] >= tp) or (sgn < 0 and lo[j] <= tp):
                exit_px = tp; exit_rsn = "TP"; exit_bar = j; break
            ln = buyH1[j] if sgn > 0 else sellH1[j]
            if ln is not None and not np.isnan(ln):
                new_sl = ln - sgn * buf_abs
                if (sgn > 0 and new_sl > vsl) or (sgn < 0 and new_sl < vsl):
                    vsl = new_sl; trailing = True
            if flipH1[j] == -sgn:
                exit_px = cl[j]; exit_rsn = "FLIP"; exit_bar = j; break
        if exit_px is None:                 # still open at data end -> drop
            break
        R = ((exit_px - entry) / sl_dist) * sgn
        trades.append({
            "entry_time": tm.iloc[i0], "exit_time": tm.iloc[exit_bar],
            "direction": "BUY" if sgn > 0 else "SELL",
            "entry_price": round(entry, 2), "exit_price": round(float(exit_px), 2),
            "exit_reason": exit_rsn, "R": round(float(R), 4),
            "score_at_entry": round(float(final_score[i]), 4),
            "bars_held": exit_bar - i0,
            "mae_pts": round(float(mae), 2), "mfe_pts": round(float(mfe), 2),
        })
        last_dir = sgn
        i = exit_bar + 1                    # non-overlapping (max_open=1)
    return trades


# ─────────────────────────────────────────────────────────────────────────
# Metrics + ranking
# ─────────────────────────────────────────────────────────────────────────
def _pf(r):
    g = r[r > 0].sum(); l = -r[r < 0].sum()
    return float(g / l) if l > 0 else (99.0 if g > 0 else 0.0)


def _max_dd_R(r):
    eq = np.cumsum(r); peak = np.maximum.accumulate(eq)
    return float(np.max(peak - eq)) if len(r) else 0.0


def _longest_loss_streak(r):
    best = cur = 0
    for x in r:
        cur = cur + 1 if x < 0 else 0
        best = max(best, cur)
    return best


def metrics(trades):
    if not trades:
        return {"trades": 0, "total_R": 0.0, "avg_R": 0.0, "median_R": 0.0,
                "win_rate": 0.0, "pf": 0.0, "max_dd_R": 0.0, "longest_loss": 0,
                "avg_bars": 0.0, "buy_trades": 0, "buy_R": 0.0, "buy_pf": 0.0,
                "sell_trades": 0, "sell_R": 0.0, "sell_pf": 0.0,
                "months": 0, "neg_months": 0, "pos_month_pct": 0.0,
                "worst_month_R": 0.0, "best_month_R": 0.0}
    df = pd.DataFrame(trades)
    r = df["R"].to_numpy()
    mo = pd.to_datetime(df["entry_time"]).dt.to_period("M")
    mR = df.groupby(mo)["R"].sum()
    buy = df[df.direction == "BUY"]["R"].to_numpy()
    sell = df[df.direction == "SELL"]["R"].to_numpy()
    return {
        "trades": len(df), "total_R": round(float(r.sum()), 2),
        "avg_R": round(float(r.mean()), 4), "median_R": round(float(np.median(r)), 4),
        "win_rate": round(float((r > 0).mean() * 100), 1), "pf": round(_pf(r), 3),
        "max_dd_R": round(_max_dd_R(r), 2), "longest_loss": _longest_loss_streak(r),
        "avg_bars": round(float(df["bars_held"].mean()), 1),
        "buy_trades": len(buy), "buy_R": round(float(buy.sum()), 2), "buy_pf": round(_pf(buy), 3),
        "sell_trades": len(sell), "sell_R": round(float(sell.sum()), 2), "sell_pf": round(_pf(sell), 3),
        "months": int(mR.size), "neg_months": int((mR < 0).sum()),
        "pos_month_pct": round(float((mR > 0).mean() * 100), 1),
        "worst_month_R": round(float(mR.min()), 2), "best_month_R": round(float(mR.max()), 2),
    }


def rank_score(m, min_trades):
    """Transparent multi-factor rank (higher=better). Not R alone."""
    if m["trades"] < min_trades or m["total_R"] <= 0:
        return -999.0
    return round(
        1.0 * m["total_R"]
        + 8.0 * min(m["pf"], 4.0)
        - 1.5 * m["max_dd_R"]
        + 0.3 * m["pos_month_pct"]
        + 20.0 * m["avg_R"]
        - 3.0 * m["neg_months"]
        + (5.0 if (m["buy_R"] > 0 and m["sell_R"] > 0) else 0.0), 2)


# ─────────────────────────────────────────────────────────────────────────
# Config enumeration
# ─────────────────────────────────────────────────────────────────────────
def tf_sets(timeframes):
    """All 15 non-empty subsets, ordered by size then base order."""
    out = []
    for k in range(1, len(timeframes) + 1):
        for c in combinations(timeframes, k):
            out.append(list(c))
    return out


def build_config_list(cfg):
    tfs = tf_sets(cfg["timeframes"])
    configs = []
    fams = cfg["families"]
    if "smma_only" in fams:
        for s in tfs:
            configs.append({"family": "smma_only", "smma_set": s, "adx_set": None, "adx_version": None})
    if "adx_only" in fams:
        for s in tfs:
            for v in cfg["adx_versions"]:
                configs.append({"family": "adx_only", "smma_set": None, "adx_set": s, "adx_version": v})
    if "combined" in fams:
        for ss in tfs:
            for a_s in tfs:
                for v in cfg["adx_versions"]:
                    configs.append({"family": "combined", "smma_set": ss, "adx_set": a_s, "adx_version": v})
    return configs


def config_key(c):
    sm = "+".join(c["smma_set"]) if c["smma_set"] else "-"
    ad = "+".join(c["adx_set"]) if c["adx_set"] else "-"
    return f"{c['family']}|smma={sm}|adx={ad}|v={c['adx_version'] or '-'}"


def compute_final_score(c, smma, di, cfg):
    fam = c["family"]
    if fam == "smma_only":
        return smma_score(smma, c["smma_set"])
    if fam == "adx_only":
        return adx_score(di, c["adx_set"], c["adx_version"], cfg)
    s = smma_score(smma, c["smma_set"])
    a = adx_score(di, c["adx_set"], c["adx_version"], cfg)
    return cfg["combined_weight_smma"] * s + cfg["combined_weight_adx"] * a


# ─────────────────────────────────────────────────────────────────────────
def load_ohlc_vol():
    """OHLC + tick_volume (M15, ascending). load_ohlc() drops volume, which the
    forming-candle reconstruction needs for partial cumulative volume."""
    df = pd.read_csv(OHLC_CSV)
    tcol = "time" if "time" in df.columns else df.columns[0]
    df = df.rename(columns={tcol: "time"})
    df["time"] = pd.to_datetime(df["time"])
    keep = ["time", "open", "high", "low", "close"]
    if "tick_volume" in df.columns:
        keep.append("tick_volume")
    return df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)[keep]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ENGINE / "config_smma_adx_sweep.json"))
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--families", nargs="*", default=None)
    ap.add_argument("--smoke", action="store_true", help="tiny run: few configs, short window")
    ap.add_argument("--benchmark", action="store_true", help="time ONE config, extrapolate, exit")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.start: cfg["date_start"] = args.start
    if args.end:   cfg["date_end"] = args.end
    if args.families: cfg["families"] = args.families
    if args.smoke:
        cfg["families"] = ["smma_only", "adx_only", "combined"]
        cfg["timeframes"] = ["H1", "H4"]        # -> 3 tf-sets, tiny sweep
    out_dir = Path(args.out_dir) if args.out_dir else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    htf_mode = cfg.get("htf_mode", "forming")
    print("=" * 70)
    print("SMMA + ADX-DI RULE-BASED SCORE SWEEP (standalone research, no AI)")
    print("=" * 70)
    print("LEAKAGE-SAFETY ASSUMPTIONS:")
    if htf_mode == "forming":
        print("  - HTF mode = FORMING: at every M15 bar, the current M30/H1/H4 candle")
        print("    is reconstructed from ONLY M15 candles completed up to that bar;")
        print("    HTF SMMA trend + ADX/DI recomputed on [prev CLOSED HTF] + [this")
        print("    partial candle]. Reproduces the LIVE evolving indicator (16 H4")
        print("    snapshots per H4 period). No future H4 high/low/close/volume used.")
    else:
        print("  - HTF mode = CLOSED: last fully-closed HTF candle only (delayed signal)")
    print("  - entry fills at NEXT M15 bar open + spread (no same-bar lookahead)")
    print("  - no full-dataset/future normalization; ADX B/C use FIXED bounded clip")
    print("  - no model / win_prob / HMM gate / threshold / news / slot filter")
    print("  - exit = trusted engine (analyze_capture H1 line SL+trail+flat TP+flip)")
    print(f"  - TP: FLAT {TPCAP}% for all configs (isolation from HMM regime TP)")
    print("-" * 70)

    ohlc = load_ohlc_vol()   # time/open/high/low/close/tick_volume, M15, ascending
    base_all = ohlc.copy()
    ds, de = pd.to_datetime(cfg["date_start"]), pd.to_datetime(cfg["date_end"])
    # keep warmup history BEFORE date_start for indicator/HTF warmup, then trade only in-window
    base = base_all[base_all["time"] <= de].reset_index(drop=True)
    print(f"Data: {len(base):,} M15 bars (warmup incl.) | trade window {ds.date()} -> {de.date()}")
    print(f"Building indicators (htf_mode={htf_mode}, SMMA={cfg['smma_score_mode']}, ADX P={cfg['adx_period']})...")
    audit = None
    if htf_mode == "forming":
        smma, di, audit = build_forming_indicators(base, cfg["smma_score_mode"], cfg["adx_period"])
    else:
        smma, di = build_indicators(base, cfg["smma_score_mode"], cfg["adx_period"])
    buyH1, sellH1, flipH1 = htf_lines(base)
    m15t = compute_trend(base, period=2, method="SMMA", ratchet=True)
    buyL = m15t["buy_line"].to_numpy(); sellL = m15t["sell_line"].to_numpy()

    # warmup = first bar with all indicators valid AND inside the trade window
    warmup = int(np.searchsorted(base["time"].values.astype("datetime64[ns]"),
                                 np.datetime64(ds), side="left"))
    for tf in cfg["timeframes"]:
        v = np.where(~np.isnan(smma[tf]))[0]
        if len(v): warmup = max(warmup, int(v[0]))
        v2 = np.where(~np.isnan(di[tf]["adx"]))[0]
        if len(v2): warmup = max(warmup, int(v2[0]))
    print(f"Warmup index: {warmup} ({base['time'].iloc[warmup]})")

    # ── forming-mode: no-lookahead self-check + snapshot audit CSV (rules 7-8) ──
    if audit is not None:
        rng = np.random.default_rng(7)
        sample = rng.integers(warmup + 20, len(base) - 2, size=min(300, len(base) - warmup - 25))
        bad = verify_no_lookahead(base, audit, sample)
        print(f"No-lookahead self-check: {len(sample)} sampled bars x 3 HTFs -> "
              f"{'PASS (0 mismatches)' if bad == 0 else f'FAIL ({bad} mismatches!)'}")
        if bad:
            print("  ABORTING: forming reconstruction failed its own no-lookahead assertion.")
            return
        # audit CSV: one full H4 period (16 snapshots) after warmup, to show evolution
        h4a = audit["H4"]
        j0 = warmup + 5
        while j0 < len(base) and (np.isnat(h4a["period_start"][j0]) or h4a["n_completed"][j0] != 1):
            j0 += 1
        arows = []
        for tf in ["M30", "H1", "H4"]:
            a = audit[tf]
            span = 16 if tf == "H4" else (4 if tf == "H1" else 2)
            for i in range(j0, min(j0 + span, len(base))):
                arows.append({
                    "htf": tf, "decision_time": base["time"].iloc[i],
                    "current_htf_period_start": a["period_start"][i],
                    "n_completed_m15_bars_used": a["n_completed"][i],
                    "partial_open": round(a["o"][i], 2), "partial_high": round(a["h"][i], 2),
                    "partial_low": round(a["l"][i], 2), "partial_close": round(a["c"][i], 2),
                    "partial_volume": a["v"][i],
                    "forming_smma_trend": smma[tf][i],
                    "forming_plus_di": round(di[tf]["pdi"][i], 2) if not np.isnan(di[tf]["pdi"][i]) else None,
                    "forming_minus_di": round(di[tf]["ndi"][i], 2) if not np.isnan(di[tf]["ndi"][i]) else None,
                    "forming_adx": round(di[tf]["adx"][i], 2) if not np.isnan(di[tf]["adx"][i]) else None,
                })
        pd.DataFrame(arows).to_csv(out_dir / "forming_snapshot_audit.csv", index=False)
        print(f"Snapshot audit written: forming_snapshot_audit.csv "
              f"(1 H4 period = 16 evolving snapshots, + H1 x4, M30 x2)")

    configs = build_config_list(cfg)
    spread, mode = cfg["spread"], cfg["entry_mode"]

    def run_one(c):
        fs = compute_final_score(c, smma, di, cfg)
        trades = simulate(fs, base, buyH1, sellH1, flipH1, buyL, sellL, mode, spread, warmup)
        # trade window filter (entry inside [ds, de])
        trades = [t for t in trades if ds <= pd.Timestamp(t["entry_time"]) <= de]
        return trades

    if args.benchmark:
        import time as _t
        c0 = next((c for c in configs if c["family"] == "combined"), configs[0])
        t0 = _t.perf_counter()
        tr = run_one(c0)
        dt = _t.perf_counter() - t0
        print(f"\nBENCHMARK: 1 combined config = {dt:.2f}s, {len(tr)} trades")
        print(f"  Full sweep ({len(configs)} configs) ~= {dt*len(configs)/60:.1f} min (single-threaded)")
        return

    # ── resume / incremental output ──
    prog_path = out_dir / "_progress.json"
    done = set()
    if prog_path.exists():
        try: done = set(json.loads(prog_path.read_text(encoding="utf-8")))
        except Exception: done = set()
    err_log = out_dir / "_errors.log"
    summ_path = out_dir / "score_sweep_summary.csv"
    det_path = out_dir / "score_sweep_trade_detail.csv"
    mon_path = out_dir / "score_sweep_monthly.csv"
    summ_cols = ["config_key", "family", "smma_set", "adx_set", "adx_version",
                 "rank_score", "flag", "trades", "total_R", "avg_R", "median_R",
                 "win_rate", "pf", "max_dd_R", "longest_loss", "avg_bars",
                 "buy_trades", "buy_R", "buy_pf", "sell_trades", "sell_R", "sell_pf",
                 "months", "neg_months", "pos_month_pct", "worst_month_R", "best_month_R"]
    if not summ_path.exists():
        summ_path.write_text(",".join(summ_cols) + "\n", encoding="utf-8")

    total = len(configs)
    print(f"\nConfigs to run: {total} (already done: {len(done)})")
    import time as _t
    t_start = _t.perf_counter(); ran = 0
    for k, c in enumerate(configs, 1):
        key = config_key(c)
        if key in done:
            continue
        try:
            trades = run_one(c)
            m = metrics(trades)
            rs = rank_score(m, cfg["min_trades_for_winner"])
            flag = "OK" if m["trades"] >= cfg["min_trades_for_winner"] else (
                "ZERO_TRADES" if m["trades"] == 0 else "LOW_TRADES")
            row = [key, c["family"],
                   "+".join(c["smma_set"]) if c["smma_set"] else "",
                   "+".join(c["adx_set"]) if c["adx_set"] else "",
                   c["adx_version"] or "", rs, flag] + [m[col] for col in summ_cols[7:]]
            with open(summ_path, "a", encoding="utf-8") as f:
                f.write(",".join(str(x) for x in row) + "\n")
            if cfg.get("save_all_trade_detail", True) and trades:
                dd = pd.DataFrame(trades)
                dd.insert(0, "config_key", key)
                dd.to_csv(det_path, mode="a", header=not det_path.exists(), index=False)
            if trades:
                dfm = pd.DataFrame(trades)
                mo = pd.to_datetime(dfm["entry_time"]).dt.to_period("M").astype(str)
                mrow = dfm.groupby(mo)["R"].sum().reset_index()
                mrow.insert(0, "config_key", key)
                mrow.columns = ["config_key", "month", "R"]
                mrow.to_csv(mon_path, mode="a", header=not mon_path.exists(), index=False)
            done.add(key); ran += 1
        except Exception as e:
            with open(err_log, "a", encoding="utf-8") as f:
                f.write(f"{key}\n{traceback.format_exc()}\n{'-'*60}\n")
            print(f"  [ERR] {key}: {e}")
        if k % 25 == 0 or k == total:
            el = _t.perf_counter() - t_start
            rate = ran / el if el > 0 and ran else 0
            rem = (total - k) / rate / 60 if rate > 0 else 0
            print(f"  [{k}/{total}] done={len(done)} | {el:.0f}s | ~{rem:.1f} min left")
            prog_path.write_text(json.dumps(sorted(done)), encoding="utf-8")
    prog_path.write_text(json.dumps(sorted(done)), encoding="utf-8")

    # ── final report + top candidates ──
    if summ_path.exists():
        s = pd.read_csv(summ_path)
        s = s.sort_values("rank_score", ascending=False)
        top = s[(s["flag"] == "OK")].head(20)
        top.to_csv(out_dir / "score_sweep_top_candidates.csv", index=False)
        rep = []
        rep.append("=" * 70)
        rep.append("SMMA + ADX-DI SCORE SWEEP - REPORT")
        rep.append(f"Window {cfg['date_start']} -> {cfg['date_end']} | entry mode {mode} | "
                   f"SMMA {cfg['smma_score_mode']} | flat TP {TPCAP}%")
        rep.append(f"Configs: {len(s)} | OK (>= {cfg['min_trades_for_winner']} trades): "
                   f"{(s['flag']=='OK').sum()} | low: {(s['flag']=='LOW_TRADES').sum()} | "
                   f"zero: {(s['flag']=='ZERO_TRADES').sum()}")
        rep.append("-" * 70)
        rep.append("TOP 15 by rank_score (OK configs only):")
        rep.append(f"{'rank':>6}  {'key':<44}{'trades':>7}{'R':>8}{'PF':>6}{'DD':>7}{'pm%':>6}")
        for _, r in top.head(15).iterrows():
            rep.append(f"{r['rank_score']:>6}  {r['config_key']:<44}{int(r['trades']):>7}"
                       f"{r['total_R']:>8.1f}{r['pf']:>6.2f}{r['max_dd_R']:>7.1f}{r['pos_month_pct']:>6.0f}")
        rep.append("-" * 70)
        rep.append("PARETO LEADERS (each dimension, OK configs):")
        if (s["flag"] == "OK").any():
            ok = s[s["flag"] == "OK"]
            for label, col, asc in [("Highest R", "total_R", False), ("Best PF", "pf", False),
                                    ("Lowest DD", "max_dd_R", True), ("Best month-stability", "pos_month_pct", False)]:
                b = ok.sort_values(col, ascending=asc).iloc[0]
                rep.append(f"  {label:<22}: {b['config_key']}  (R={b['total_R']:.1f} PF={b['pf']:.2f} "
                           f"DD={b['max_dd_R']:.1f} pm%={b['pos_month_pct']:.0f})")
        rep.append("=" * 70)
        rep.append("NOTE: this is the Phase-1 3-month SCREEN only. A winner here still needs")
        rep.append("Phase-2 (1-year holdout), Phase-3 (WFO stability), Phase-4 (robustness)")
        rep.append("before its logic is trusted or turned into AI features. rank_score is a")
        rep.append("transparent heuristic; read raw metrics too (both are in the summary CSV).")
        rep.append("=" * 70)
        report = "\n".join(rep)
        print("\n" + report)
        (out_dir / "score_sweep_report.txt").write_text(report, encoding="utf-8")

    print(f"\nSaved to {out_dir}")
    print(f"  score_sweep_summary.csv | score_sweep_top_candidates.csv | "
          f"score_sweep_report.txt | score_sweep_monthly.csv | score_sweep_trade_detail.csv")


if __name__ == "__main__":
    main()
