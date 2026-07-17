"""compare_ohlc_parity.py — root-cause check: does the Python source
(data/merged/ohlc_merged.csv) actually match the live MT5 terminal's
own price history for the same bars? If OHLC itself differs, the ADX
parity mismatch is a DATA problem, not a FORMULA problem.

Usage:
    python compare_ohlc_parity.py --mt5 ohlc_mt5_export.csv --tol 0.10
"""
import argparse
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ohlc", default=r"C:\QGAI\data\merged\ohlc_merged.csv")
    ap.add_argument("--mt5", default="ohlc_mt5_export.csv")
    ap.add_argument("--tol", type=float, default=0.10, help="max allowed price difference ($)")
    args = ap.parse_args()

    py = pd.read_csv(args.ohlc)
    time_col = "datetime" if "datetime" in py.columns else "time"
    py[time_col] = pd.to_datetime(py[time_col])
    # ohlc_merged.csv "time" is bar OPEN time (see export_python_adx_for_mt5_parity.py) —
    # convert to bar CLOSE time (M15 = +15min) to match the MT5 export's close-time convention.
    py["bar_close_time"] = py[time_col] + pd.Timedelta(minutes=15)
    py = py[["bar_close_time", "open", "high", "low", "close"]].copy()
    py.columns = ["bar_close_time", "py_open", "py_high", "py_low", "py_close"]

    mt = pd.read_csv(args.mt5, sep=None, engine="python")
    mt["bar_close_time"] = pd.to_datetime(mt["bar_close_time"], format="%Y.%m.%d %H:%M:%S")
    mt.columns = ["bar_close_time", "mt5_open", "mt5_high", "mt5_low", "mt5_close"]

    merged = py.merge(mt, on="bar_close_time", how="outer", indicator=True)
    only_py = merged[merged["_merge"] == "left_only"]
    only_mt = merged[merged["_merge"] == "right_only"]
    both = merged[merged["_merge"] == "both"].copy()

    for col in ["open", "high", "low", "close"]:
        both[f"{col}_diff"] = (both[f"py_{col}"] - both[f"mt5_{col}"]).abs()

    both["max_diff"] = both[["open_diff", "high_diff", "low_diff", "close_diff"]].max(axis=1)
    bad = both[both["max_diff"] > args.tol]

    print(f"Matched bars: {len(both)}")
    print(f"Python-only (no MT5 match): {len(only_py)}")
    print(f"MT5-only (no Python match): {len(only_mt)}")
    print(f"Mean close diff: {both['close_diff'].mean():.4f}")
    print(f"Max close diff:  {both['close_diff'].max():.4f}")
    print(f"Bars exceeding tolerance (${args.tol}): {len(bad)} / {len(both)}")
    print()
    print("First 10 matched bars (raw comparison):")
    print(both[["bar_close_time", "py_close", "mt5_close", "close_diff"]].head(10).to_string(index=False))
    print()
    print("Last 10 matched bars (raw comparison):")
    print(both[["bar_close_time", "py_close", "mt5_close", "close_diff"]].tail(10).to_string(index=False))
    print()
    if len(bad) > len(both) * 0.05:
        print("VERDICT: DATA MISMATCH — Python's ohlc_merged.csv does NOT match this MT5")
        print("terminal's own price history. The ADX parity test cannot validate the")
        print("formula against a different underlying dataset. Root cause is a data-source")
        print("mismatch (different broker/feed/symbol), not the ADX smoothing formula.")
    else:
        print("VERDICT: DATA MATCHES — OHLC is consistent. If ADX still doesn't match,")
        print("the discrepancy is genuinely in the smoothing formula, not the input data.")


if __name__ == "__main__":
    main()
