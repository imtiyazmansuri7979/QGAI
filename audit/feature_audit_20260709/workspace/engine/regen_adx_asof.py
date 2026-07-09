"""
regen_adx_asof.py — AUDIT FIX 1: leak-free (as-of / live-match) ADX rebuild
============================================================================
2026-07-02 (Divyesh audit). The old adx_merged.csv embeds intra-bar FUTURE
data: HTF (M30/H1/H4) columns are full-bar values forward-filled into the
M15 rows INSIDE the bar (audit: H4_ADX drift vs honest value mean 0.60 /
max 2.02 pts). This script rebuilds every column AS-OF each M15 row —
EWM state over COMPLETED bars + exactly one Wilder step with the PARTIAL
forming bar — which equals what mt5_data_updater computes at live decision
time (algorithm validated EXACT vs brute-force partial resample, err=0.0).

Columns produced (same schema as regen_adx_di.py):
  {TF}_ADX, {TF}_DI_diff, {TF}_PlusDI, {TF}_MinusDI,
  {TF}_band_width_pct, {TF}_di_eff, {TF}_band_rel   x M15/M30/H1/H4

Usage:
  python regen_adx_asof.py            -> writes data/merged/adx_merged_asof.csv (preview)
  python regen_adx_asof.py --apply    -> backup + REPLACE data/merged/adx_merged.csv

⚠ SEQUENCE: run ONLY after the A/B HMM WFO windows are finished. After
--apply: retrain (train.py) + rerun WFO -> that total R is the new HONEST
baseline (old +483.1R was leak-inflated; do not compare against it).
⚠ Also update mt5_data_updater.update_adx to the same as-of convention at
deploy time (one atomic switch with the retrain).
"""
import sys
import shutil
import numpy as np
import pandas as pd
from pathlib import Path

ENG   = Path(__file__).resolve().parent
OHLC  = ENG.parent / "data" / "merged" / "ohlc_merged.csv"
ADX   = ENG.parent / "data" / "merged" / "adx_merged.csv"
OUT   = ENG.parent / "data" / "merged" / "adx_merged_asof.csv"
TFS   = {"M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h"}
P     = 14
A     = 2.0 / (P + 1)          # ewm(span=14, adjust=False) alpha — same as live updater


def asof_tf(df, rule):
    """As-of ADX/DI/band per M15 row for one TF (vectorized, exact).
    = EWM state after last COMPLETED bar + one Wilder step with the partial
    forming bar (aggregated up to the row). Validated err=0 vs brute force."""
    barid = df.index.floor(rule)
    g  = df.groupby(barid)
    Hf = g["high"].cummax(); Lf = g["low"].cummin(); Cf = df["close"]

    bars = df.resample(rule).agg({"open": "first", "high": "max",
                                  "low": "min", "close": "last"}).dropna()
    h, l, c = bars["high"], bars["low"], bars["close"]
    tr  = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    up  = h - h.shift(1); dn = l.shift(1) - l
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0), index=bars.index)
    ndm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0), index=bars.index)
    atr  = tr.ewm(span=P, adjust=False).mean()
    spdm = pdm.ewm(span=P, adjust=False).mean()
    sndm = ndm.ewm(span=P, adjust=False).mean()
    pdi  = 100 * spdm / (atr + 1e-9); ndi = 100 * sndm / (atr + 1e-9)
    dx   = 100 * (pdi - ndi).abs() / (pdi + ndi + 1e-9)
    adx  = dx.ewm(span=P, adjust=False).mean()
    # SMMA period 2 == ewm(alpha=0.5, adjust=False) (identical recursion from idx 1)
    maH  = h.ewm(alpha=0.5, adjust=False).mean()
    maL  = l.ewm(alpha=0.5, adjust=False).mean()

    bid = pd.Series(barid, index=df.index)
    def prev(series):
        return bid.map(series.shift(1))          # state at LAST COMPLETED bar
    atr_k, spdm_k, sndm_k, adx_k = prev(atr), prev(spdm), prev(sndm), prev(adx)
    Hk, Lk, Ck   = prev(h), prev(l), prev(c)
    maHk, maLk   = prev(maH), prev(maL)

    tr_f  = pd.concat([Hf - Lf, (Hf - Ck).abs(), (Lf - Ck).abs()], axis=1).max(axis=1)
    upf   = Hf - Hk; dnf = Lk - Lf
    pdm_f = np.where((upf > dnf) & (upf > 0), upf, 0)
    ndm_f = np.where((dnf > upf) & (dnf > 0), dnf, 0)
    atr_t  = (1 - A) * atr_k  + A * tr_f
    spdm_t = (1 - A) * spdm_k + A * pdm_f
    sndm_t = (1 - A) * sndm_k + A * ndm_f
    pdi_t  = 100 * spdm_t / (atr_t + 1e-9)
    ndi_t  = 100 * sndm_t / (atr_t + 1e-9)
    dx_t   = 100 * (pdi_t - ndi_t).abs() / (pdi_t + ndi_t + 1e-9)
    adx_t  = (1 - A) * adx_k + A * dx_t
    maH_t  = (maHk + Hf) / 2.0                    # one SMMA2 step
    maL_t  = (maLk + Lf) / 2.0
    band_t = (maH_t - maL_t) / Cf * 100.0
    return adx_t, pdi_t, ndi_t, band_t


def main():
    apply = "--apply" in sys.argv
    print(f"Reading OHLC: {OHLC}")
    df = pd.read_csv(OHLC)
    df["datetime"] = pd.to_datetime(df["time"])
    df = df.set_index("datetime").sort_index()

    res = pd.DataFrame(index=df.index)
    for tf, rule in TFS.items():
        adx_t, pdi_t, ndi_t, band_t = asof_tf(df, rule)
        res[f"{tf}_ADX"]            = adx_t.round(2)
        res[f"{tf}_DI_diff"]        = (pdi_t - ndi_t).round(2)
        res[f"{tf}_PlusDI"]         = pdi_t.round(2)
        res[f"{tf}_MinusDI"]        = ndi_t.round(2)
        res[f"{tf}_band_width_pct"] = band_t.round(4)
        res[f"{tf}_di_eff"]         = (100 * (pdi_t - ndi_t).abs() / (pdi_t + ndi_t + 1e-9)).round(2)
        b = res[f"{tf}_band_width_pct"]
        res[f"{tf}_band_rel"]       = (b / b.rolling("30D").mean()).round(4).fillna(1.0)
        print(f"  {tf}: as-of done | ADX mean={res[f'{tf}_ADX'].mean():.2f}")

    # ── DRIFT REPORT vs the old (leaky) file ──
    if ADX.exists():
        try:
            old = pd.read_csv(ADX)
            old["datetime"] = pd.to_datetime(old["timestamp"])
            old = old.set_index("datetime")
            print("\nLEAK DRIFT (old full-bar file vs as-of; >0 = leak existed):")
            for tf in TFS:
                col = f"{tf}_ADX"
                if col in old.columns:
                    j = res[[col]].join(old[[col]], rsuffix="_old").dropna()
                    d = (j[col] - j[f"{col}_old"]).abs()
                    print(f"  {tf}_ADX: mean|Δ|={d.mean():.3f} p95={d.quantile(0.95):.3f} max={d.max():.3f}")
        except Exception as e:
            print(f"  (drift report skipped: {e})")

    res = res.reset_index()
    res["timestamp"]   = res["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    res["Time (24h)"]  = res["datetime"].dt.strftime("%H:%M")
    res = res.drop(columns=["datetime"])
    res["data_source"] = "regen_asof"

    if apply:
        if ADX.exists():
            from datetime import datetime as _dt
            bak = str(ADX) + ".bak_preasof_" + _dt.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(ADX, bak)
            print(f"\nBacked up old -> {bak}")
        res.to_csv(ADX, index=False)
        print(f"APPLIED -> {ADX}  ({len(res):,} rows)")
        print("NEXT: python train.py, then RERUN the WFO — that total R is the")
        print("      new HONEST baseline. Do NOT compare against +483.1R.")
    else:
        res.to_csv(OUT, index=False)
        print(f"\nPreview written -> {OUT}  ({len(res):,} rows)  (use --apply to replace live file)")


if __name__ == "__main__":
    main()
