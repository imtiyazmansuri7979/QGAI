"""
build_indicators.py — QUANT GOLD AI v2
═══════════════════════════════════════════════════════════════════
Saves EVERY indicator value for EVERY closed M15 bar into one file:

    data/merged/indicators_merged.csv

So that training, backtest_replay, and live all reference the SAME
exact, no-lookahead values — no loopholes, fully auditable in Excel.

Columns (per closed M15 bar, value AS OF that bar's close):
    time
    h4_adx_roll, h1_adx_roll      — rolling ADX (updates every bar)
    h4_adx_slope, h1_adx_slope    — change vs 16 bars ago
    trend_m15, trend_h1, trend_h4 — TrendSignals state (+1/-1)
    buy_line, sell_line           — ratchet lines (M15)
    flip                          — +1/-1 on flip bar, else 0
    bars_since_flip
    line_dist_pct                 — close distance from active line (%)
    htf_agreement                 — trend_m15+h1+h4 (-3..+3)
    adx_switch_trend              — H4 ADX(roll)>=19 → trend_h4 else trend_h1

Runs automatically at the end of merge_data.py (QGAI_RETRAIN step 2),
or standalone:  python build_indicators.py [--verify N]
═══════════════════════════════════════════════════════════════════
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))

from trend_signal import compute_trend, resample_ohlc

DATA       = ENGINE.parent / "data"
OHLC_FILE  = DATA / "merged" / "ohlc_merged.csv"
MERGE_DIR  = DATA / "merged"
OUT_FILE   = DATA / "merged" / "indicators_merged.csv"

TS_PERIOD, TS_METHOD = 2, "SMMA"      # indicator settings (validated)
ADX_SWITCH_LEVEL     = 19.0           # EA rule: H4 ADX >= 19 → H4 confirm


def build(verbose: bool = True) -> pd.DataFrame:
    import features as F   # reuse the EXACT same engines as live/training

    ohlc = pd.read_csv(OHLC_FILE)
    ohlc["datetime"] = pd.to_datetime(ohlc["time"])
    ohlc = ohlc.sort_values("datetime").reset_index(drop=True)
    n = len(ohlc)
    if verbose:
        print(f"  OHLC(M15) bars: {n:,} | {ohlc['datetime'].iloc[0]} → {ohlc['datetime'].iloc[-1]}")

    m15_times = ohlc["datetime"].values.astype("datetime64[ns]")
    out = pd.DataFrame({"time": ohlc["time"]})

    # ── Rolling ADX (H4 + H1 — H1 needed for switch) ───────────
    radx = F.build_rolling_adx_table(ohlc)
    h4 = radx["h4"]; h1 = radx["h1"]
    h4_slope = np.full(n, np.nan); h1_slope = np.full(n, np.nan)
    h4_slope[16:] = h4[16:] - h4[:-16]
    h1_slope[16:] = h1[16:] - h1[:-16]

    base = ohlc[["datetime", "open", "high", "low", "close"]].rename(columns={"datetime": "time"})
    close = ohlc["close"].to_numpy(float)

    # ── Per-TF trend signals (TrendSignals indicator, P=2 SMMA) ──
    # TFs requested: M5, M15, M30, H4, Daily.  (H1 kept internally for switch.)
    # M5 comes from a finer file if present; others resample from M15 base.
    def compute_tf(tf_key):
        """Return (trend, buy_line, sell_line, flip, bsf) arrays mapped onto M15 bars."""
        if tf_key == "m5":
            m5f = MERGE_DIR / "ohlc_m5_merged.csv"
            if not m5f.exists():
                return None
            d5 = pd.read_csv(m5f)
            d5["time"] = pd.to_datetime(d5["time"], errors="coerce")
            d5 = d5[d5["time"].notna()][["time", "open", "high", "low", "close"]].reset_index(drop=True)
            if len(d5) < 50:
                return None
            t5 = compute_trend(d5, TS_PERIOD, TS_METHOD)
            # map last CLOSED M5 bar (close = open+5min) to each M15 bar
            bar_close = t5["time"].values.astype("datetime64[ns]") + np.timedelta64(5, "m")
            idx = np.searchsorted(bar_close, m15_times + np.timedelta64(15, "m"), side="right") - 1
            return _gather(t5, idx, n)
        tf_map = {"m15": ("15min", 15), "m30": ("30min", 30), "h4": ("4h", 240), "d1": ("1D", 1440)}
        rule, tf_min = tf_map[tf_key]
        tdf = compute_trend(resample_ohlc(base, rule) if tf_key != "m15" else base, TS_PERIOD, TS_METHOD)
        bar_close = tdf["time"].values.astype("datetime64[ns]") + np.timedelta64(tf_min, "m")
        idx = np.searchsorted(bar_close, m15_times + np.timedelta64(15, "m"), side="right") - 1
        return _gather(tdf, idx, n)

    def _gather(tdf, idx, n):
        tr = tdf["trend"].to_numpy(); bl = tdf["buy_line"].to_numpy()
        sl_ = tdf["sell_line"].to_numpy(); fl = tdf["flip"].to_numpy()
        bsf = tdf["bars_since_flip"].to_numpy()
        valid = idx >= 0
        ci = np.clip(idx, 0, len(tr) - 1)
        return {
            "trend": np.where(valid, tr[ci], 0).astype(int),
            "buy_line": np.where(valid, bl[ci], np.nan),
            "sell_line": np.where(valid, sl_[ci], np.nan),
            "flip": np.where(valid, fl[ci], 0).astype(int),
            "bsf": np.where(valid, bsf[ci], np.nan),
        }

    TF_LIST = ["m5", "m15", "m30", "h4", "d1"]
    tf_data = {}
    for tf in TF_LIST:
        r = compute_tf(tf)
        if r is None:
            if verbose:
                print(f"  -- {tf.upper()} skipped (no data yet — will populate after MT5 M5 download)")
            continue
        tf_data[tf] = r
        out[f"trend_{tf}"]     = r["trend"]
        out[f"buy_line_{tf}"]  = np.round(r["buy_line"], 3)
        out[f"sell_line_{tf}"] = np.round(r["sell_line"], 3)
        out[f"flip_{tf}"]      = r["flip"]
        out[f"bars_since_flip_{tf}"] = r["bsf"]
        # distance of M15 close from this TF's active line (%)
        active = np.where(r["trend"] > 0, r["buy_line"], r["sell_line"])
        with np.errstate(invalid="ignore"):
            out[f"line_dist_pct_{tf}"] = np.round((close - active) / close * 100.0, 6)

    # ── ADX block (rolling H4/H1) ──────────────────────────────
    out["h4_adx_roll"]  = np.round(h4, 6)
    out["h1_adx_roll"]  = np.round(h1, 6)
    out["h4_adx_slope"] = np.round(h4_slope, 6)
    out["h1_adx_slope"] = np.round(h1_slope, 6)

    # ── Cross-TF summaries ─────────────────────────────────────
    trends_for_agree = [tf_data[t]["trend"] for t in ["m15", "h4"] if t in tf_data]
    if "m30" in tf_data: trends_for_agree.append(tf_data["m30"]["trend"])
    if trends_for_agree:
        out["htf_agreement"] = np.sum(trends_for_agree, axis=0).astype(int)
    # ADX switch (live logic): H4 ADX(roll) >= 19 → H4 trend else H1 trend
    tr_h4 = tf_data["h4"]["trend"] if "h4" in tf_data else np.zeros(n, int)
    # H1 trend (internal, not a saved column) for switch:
    th1 = compute_trend(resample_ohlc(base, "1h"), TS_PERIOD, TS_METHOD)
    bc = th1["time"].values.astype("datetime64[ns]") + np.timedelta64(60, "m")
    i1 = np.searchsorted(bc, m15_times + np.timedelta64(15, "m"), side="right") - 1
    tr_h1 = np.where(i1 >= 0, th1["trend"].to_numpy()[np.clip(i1, 0, len(th1) - 1)], 0).astype(int)
    out["adx_switch_trend"] = np.where(np.nan_to_num(h4, nan=0.0) >= ADX_SWITCH_LEVEL, tr_h4, tr_h1).astype(int)

    out.to_csv(OUT_FILE, index=False, float_format="%.6g")
    if verbose:
        sz = OUT_FILE.stat().st_size / 1e6
        saved_tfs = [t.upper() for t in TF_LIST if t in tf_data]
        print(f"  [OK] {len(out):,} rows × {len(out.columns)} cols → {OUT_FILE} ({sz:.1f}MB)")
        print(f"       TFs saved: {', '.join(saved_tfs)}")
    return out


def verify(snapshot: pd.DataFrame, n_samples: int = 25) -> bool:
    """Paranoid check: recompute N random bars via the LIVE feature path
    (features.compute_features) and assert the saved values match."""
    import features as F
    ohlc = F.load_ohlc(str(OHLC_FILE))
    adx_file = DATA / "merged" / "adx_merged.csv"
    adx  = F.load_adx(str(adx_file))
    news_file = DATA / "news_all_2024_to_now_pure_cleaned.csv"
    news = F.load_news(str(news_file)) if news_file.exists() else pd.DataFrame()

    rng = np.random.default_rng(7)
    snap = snapshot.copy()
    snap["dt"] = pd.to_datetime(snap["time"])
    idxs = rng.integers(2000, len(snap) - 2, n_samples)
    bad = 0
    for i in idxs:
        row = snap.iloc[i]
        # decision time = NEXT bar open (so saved bar i is the last closed bar)
        t = snap["dt"].iloc[i + 1]
        f = F.compute_features(t, "BUY", 0.10, ohlc, adx, news)
        checks = [
            ("ts_trend_m15",        row.get("trend_m15")),
            ("ts_trend_h4",         row.get("trend_h4")),
            ("h4_adx_slope",        row.get("h4_adx_slope")),
            ("h1_adx_slope",        row.get("h1_adx_slope")),
            ("ts_adx_switch_trend", row.get("adx_switch_trend")),
        ]
        for k, want in checks:
            got = f.get(k)
            if want is None or (isinstance(want, float) and np.isnan(want)):
                continue
            if abs(float(got) - float(want)) > 0.02:
                print(f"  [MISMATCH] {snap['time'].iloc[i]} {k}: saved={want} live={got}")
                bad += 1
    if bad == 0:
        print(f"  [OK] VERIFY PASSED — {n_samples} random bars, saved == live-computed ✅")
    else:
        print(f"  [ERR] {bad} mismatches — investigate before trusting backtests!")
    return bad == 0


if __name__ == "__main__":
    print("=" * 55)
    print("  INDICATOR SNAPSHOT — all values, every 15min, saved")
    print("=" * 55)
    snap = build()
    nv = 25
    if "--verify" in sys.argv:
        try:
            nv = int(sys.argv[sys.argv.index("--verify") + 1])
        except Exception:
            pass
    verify(snap, nv)
