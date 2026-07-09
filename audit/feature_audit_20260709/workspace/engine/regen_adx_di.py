"""
regen_adx_di.py — rebuild data/merged/adx_merged.csv with +DI / -DI LEVELS
==========================================================================
2026-07-02 (Divyesh). The HMM "Volatile" mislabel fix needs {TF}_PlusDI /
{TF}_MinusDI columns (the current merged ADX only has ADX + DI_diff). This
recomputes ADX + DI_diff + PlusDI + MinusDI for M15/M30/H1/H4 straight from
data/merged/ohlc_merged.csv using the SAME formula as the live updater
(mt5_data_updater.compute_adx_tf) — so training data == live feed (parity).

Safe: backs up the old file first, and prints a DI_diff PARITY report vs the
old file (recompute should reproduce the old DI_diff; only +DI/-DI is new).

Run:  python regen_adx_di.py
(v3: adds {TF}_band_width_pct — lag-free SMMA2 band volatility per TF.)
Then: retrain (train.py) and validate with WFO before restarting live.
"""
import sys
import shutil
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trend_signal import _ma          # SMMA — SAME implementation as live band buffer

ENG   = Path(__file__).resolve().parent
OHLC  = ENG.parent / "data" / "merged" / "ohlc_merged.csv"
ADX   = ENG.parent / "data" / "merged" / "adx_merged.csv"
TFS   = {"M15": None, "M30": "30min", "H1": "1h", "H4": "4h"}

def compute_adx_tf(df, period=14):
    """EXACT copy of mt5_data_updater.compute_adx_tf (now returns +DI/-DI too)."""
    h, l, c = df["high"], df["low"], df["close"]
    tr  = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    up  = h - h.shift(1); dn = l.shift(1) - l
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0), index=df.index)
    ndm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0), index=df.index)
    atr = tr.ewm(span=period, adjust=False).mean()
    pdi = 100 * pdm.ewm(span=period, adjust=False).mean() / (atr + 1e-9)
    ndi = 100 * ndm.ewm(span=period, adjust=False).mean() / (atr + 1e-9)
    dx  = 100 * (pdi - ndi).abs() / (pdi + ndi + 1e-9)
    adx = dx.ewm(span=period, adjust=False).mean()
    return adx.round(2), (pdi - ndi).round(2), pdi.round(2), ndi.round(2)

def compute_band_width_pct(df, period=2, method="SMMA"):
    """2026-07-02 (Divyesh) HMM v3: lag-free volatility feature per TF.
    band_width_pct = (SMMA2(High) - SMMA2(Low)) / close * 100
    EXACT port of trend_signal.compute_trend band (Period=2 SMMA, line 115) —
    the live band-buffer indicator. NOT ATR (removed 2026-06-19, lagging)."""
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    maH = _ma(h, period, method)
    maL = _ma(l, period, method)
    bw  = (maH - maL) / c * 100.0
    return pd.Series(bw, index=df.index).round(4)

print(f"Reading OHLC: {OHLC}")
df = pd.read_csv(OHLC)
df["datetime"] = pd.to_datetime(df["time"])
df = df.set_index("datetime")

def resample(rule):
    return df.resample(rule).agg(open=("open", "first"), high=("high", "max"),
                                 low=("low", "min"), close=("close", "last")).dropna()

sources = {"M15": df, "M30": resample("30min"), "H1": resample("1h"), "H4": resample("4h")}
res = pd.DataFrame(index=df.index)
for tf, tdf in sources.items():
    adx, dd, pdi, ndi = compute_adx_tf(tdf)
    bw = compute_band_width_pct(tdf)              # HMM v3 volatility feature
    res[f"{tf}_ADX"]            = adx.reindex(df.index, method="ffill")
    res[f"{tf}_DI_diff"]        = dd.reindex(df.index, method="ffill")
    res[f"{tf}_PlusDI"]         = pdi.reindex(df.index, method="ffill")
    res[f"{tf}_MinusDI"]        = ndi.reindex(df.index, method="ffill")
    res[f"{tf}_band_width_pct"] = bw.reindex(df.index, method="ffill")
    print(f"  {tf}: {len(tdf):,} bars | band_width_pct mean={bw.mean():.4f}% "
          f"p10={bw.quantile(0.10):.4f}% p90={bw.quantile(0.90):.4f}%")

# ── HMM v3 'rel' variant features (derived at the M15 grid; index=datetime) ──
#   di_eff   = 100*|+DI - -DI| / (+DI + -DI)  — instantaneous DX (lag-free clarity;
#              unlike smoothed ADX/DI_diff it drops immediately in post-trend chop)
#   band_rel = band_width_pct / trailing 30-DAY mean — gold's absolute volatility
#              drifted 2022→2026, raw band % is non-stationary; numerator stays
#              lag-free, the trailing mean is slow CONTEXT (not an ATR-style signal).
#              Warmup (first ~30d) filled with neutral 1.0.
for tf in TFS:
    pdi = res[f"{tf}_PlusDI"]; ndi = res[f"{tf}_MinusDI"]
    res[f"{tf}_di_eff"] = (100 * (pdi - ndi).abs() / (pdi + ndi + 1e-9)).round(2)
    b = res[f"{tf}_band_width_pct"]
    res[f"{tf}_band_rel"] = (b / b.rolling("30D").mean()).round(4).fillna(1.0)
    print(f"  {tf}: di_eff mean={res[f'{tf}_di_eff'].mean():.2f} | "
          f"band_rel mean={res[f'{tf}_band_rel'].mean():.4f}")

res = res.reset_index()
res["timestamp"]   = res["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
res["Time (24h)"]  = res["datetime"].dt.strftime("%H:%M")
res = res.drop(columns=["datetime"])
res["data_source"] = "regen_di"

# ── PARITY vs old (DI_diff should reproduce; only +DI/-DI is new) ──
if ADX.exists():
    old = pd.read_csv(ADX)
    # Non-clobbering backup: .bak_prediregen holds the ORIGINAL pre-v1 file
    # (a revert asset) — never overwrite an existing backup.
    bak = str(ADX) + ".bak_prediregen"
    if Path(bak).exists():
        from datetime import datetime as _dt
        bak = str(ADX) + ".bak_" + _dt.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(ADX, bak)
    print(f"\nBacked up old -> {bak}")
    if "timestamp" in old.columns:
        cols = [f"{tf}_DI_diff" for tf in TFS]
        m = old[["timestamp"] + cols].merge(res[["timestamp"] + cols], on="timestamp",
                                             suffixes=("_old", "_new"))
        print("DI_diff PARITY (recompute vs old):")
        for tf in TFS:
            d = (m[f"{tf}_DI_diff_new"] - m[f"{tf}_DI_diff_old"]).abs()
            print(f"  {tf}: rows={len(m)} max|Δ|={d.max():.3f} mean|Δ|={d.mean():.4f} rows(>0.5)={int((d>0.5).sum())}")
        print("  (small Δ = method consistent, only +DI/-DI added. Large Δ = tell Claude before retraining.)")

res.to_csv(ADX, index=False)
print(f"\nWROTE {ADX}  ({len(res):,} rows)")
print("cols:", list(res.columns))
print("\nNEXT: retrain (train.py) — check the HMM cluster printout: Volatile should have HIGH")
print("      band_width_pct, Ranging LOW, Trending highest clarity. Then WFO to compare")
print("      total R vs +483.0R baseline (profit-first).")
