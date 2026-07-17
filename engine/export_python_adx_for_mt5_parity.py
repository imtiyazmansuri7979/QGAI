"""export_python_adx_for_mt5_parity.py — Test 1 (MT5 parity) helper.

Exports the Python-computed EMA ADX(14) for M15/M30/H1/H4 at the last
N closed bars, WITH exact timestamps, so it can be diffed against MT5's
own iADX() buffer values (dumped via the companion .mq5 script) for the
SAME symbol/timeframes/bars.

Usage:
    python export_python_adx_for_mt5_parity.py --bars 200 --out adx_python_export.csv
"""
import argparse
import numpy as np
import pandas as pd


def compute_adx_tf(df, period=14):
    """EXACT copy of mt5_data_updater.compute_adx_tf's math — inlined here
    (not imported) so this diagnostic script has zero dependency on
    config_mt5.py / a live MT5 connection. Same formula, verified against
    the live module at the time this script was written (2026-07-17)."""
    h = df["high"]; l = df["low"]; c = df["close"]
    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    up = h - h.shift(1); dn = l.shift(1) - l
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0), index=df.index)
    ndm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0), index=df.index)
    atr = tr.ewm(span=period, adjust=False).mean()
    pdi = 100 * pdm.ewm(span=period, adjust=False).mean() / (atr + 1e-9)
    ndi = 100 * ndm.ewm(span=period, adjust=False).mean() / (atr + 1e-9)
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi + 1e-9)
    adx = dx.ewm(span=period, adjust=False).mean()
    return adx.round(2), (pdi - ndi).round(2), pdi.round(2), ndi.round(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ohlc", default=r"C:\QGAI\data\merged\ohlc_merged.csv")
    ap.add_argument("--bars", type=int, default=200, help="last N M15 bars to export")
    ap.add_argument("--out", default="adx_python_export.csv")
    args = ap.parse_args()

    df = pd.read_csv(args.ohlc)
    time_col = "datetime" if "datetime" in df.columns else "time"
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.set_index(time_col).sort_index()

    rows = []
    for tf_name, rule in [("M15", None), ("M30", "30min"), ("H1", "1h"), ("H4", "4h")]:
        tdf = df.resample(rule).agg({"open": "first", "high": "max",
                                      "low": "min", "close": "last"}).dropna() if rule else df
        adx, dd, pdi, ndi = compute_adx_tf(tdf)
        tail = tdf.tail(args.bars).copy()
        tail["adx"] = adx.reindex(tail.index)
        tail["plus_di"] = pdi.reindex(tail.index)
        tail["minus_di"] = ndi.reindex(tail.index)
        for ts, r in tail.iterrows():
            rows.append({
                "timeframe": tf_name,
                "bar_close_time": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "python_adx": round(r["adx"], 4) if pd.notna(r["adx"]) else "",
                "python_plus_di": round(r["plus_di"], 4) if pd.notna(r["plus_di"]) else "",
                "python_minus_di": round(r["minus_di"], 4) if pd.notna(r["minus_di"]) else "",
            })

    out = pd.DataFrame(rows)
    out.to_csv(args.out, index=False)
    print(f"Wrote {len(out)} rows -> {args.out}")
    print("Next: run the companion export_mt5_adx_for_parity.mq5 script in MT5 for the")
    print("SAME symbol/timeframes/bar range, then run compare_adx_parity.py to diff them.")


if __name__ == "__main__":
    main()
