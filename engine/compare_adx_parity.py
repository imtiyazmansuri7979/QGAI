"""compare_adx_parity.py — Test 1 (MT5 parity) final diff.

Compares adx_python_export.csv (from export_python_adx_for_mt5_parity.py)
against adx_mt5_export.csv (from export_mt5_adx_for_parity.mq5, copied
out of MQL5\\Files\\) and reports mismatches beyond tolerance.

Usage:
    python compare_adx_parity.py --python adx_python_export.csv --mt5 adx_mt5_export.csv --tol 0.5
"""
import argparse
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default="adx_python_export.csv")
    ap.add_argument("--mt5", default="adx_mt5_export.csv")
    ap.add_argument("--tol", type=float, default=0.5, help="max allowed ADX point difference")
    args = ap.parse_args()

    py = pd.read_csv(args.python)
    mt = pd.read_csv(args.mt5)

    # Normalize timestamp format — MT5's TimeToString uses dots (2026.07.17
    # 18:45:00), the Python export uses dashes (2026-07-17 18:45:00). Parse
    # both to a common string so the merge key actually matches.
    py["bar_close_time"] = pd.to_datetime(py["bar_close_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    mt["bar_close_time"] = pd.to_datetime(mt["bar_close_time"], format="%Y.%m.%d %H:%M:%S").dt.strftime("%Y-%m-%d %H:%M:%S")

    merged = py.merge(mt, on=["timeframe", "bar_close_time"], how="outer", indicator=True)
    only_py = merged[merged["_merge"] == "left_only"]
    only_mt = merged[merged["_merge"] == "right_only"]
    both = merged[merged["_merge"] == "both"].copy()

    both["adx_diff"] = (both["python_adx"] - both["mt5_adx"]).abs()
    bad = both[both["adx_diff"] > args.tol]

    print(f"Matched bars: {len(both)}")
    print(f"Python-only (no MT5 match): {len(only_py)}")
    print(f"MT5-only (no Python match): {len(only_mt)}")
    print(f"Mean |diff|: {both['adx_diff'].mean():.4f}")
    print(f"Max |diff|:  {both['adx_diff'].max():.4f}")
    print(f"Bars exceeding tolerance ({args.tol}): {len(bad)}")
    if len(bad):
        print(bad[["timeframe", "bar_close_time", "python_adx", "mt5_adx", "adx_diff"]].to_string(index=False))
        print("\nVERDICT: FAIL — investigate before trusting the EMA ADX as MT5-matched.")
    else:
        print("\nVERDICT: PASS — Python EMA ADX matches MT5 iADX() within tolerance.")


if __name__ == "__main__":
    main()
