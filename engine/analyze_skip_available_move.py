"""
analyze_skip_available_move.py — Split available move into IN-TRADE vs SKIP bars.

Shows how much price movement happens while the system is in a trade vs sitting
out (SKIP). Reads the OOS trades CSV + M15 OHLC data, marks each bar as
in-trade or skip, and sums high-low for each group.

Usage:
  python analyze_skip_available_move.py \
    --trades-csv <path> --from 2025-06-29 --to 2026-06-29 \
    --out-dir <path>
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades-csv", required=True)
    ap.add_argument("--from", dest="dt_from", required=True)
    ap.add_argument("--to", dest="dt_to", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    ohlc_path = Path(__file__).resolve().parent.parent / "data" / "merged" / "ohlc_merged.csv"
    if not ohlc_path.exists():
        print(f"ERROR: OHLC file not found: {ohlc_path}")
        sys.exit(1)

    trades = pd.read_csv(args.trades_csv)
    print(f"Loaded {len(trades)} trades from {Path(args.trades_csv).name}")

    ohlc = pd.read_csv(ohlc_path)
    time_col = "datetime" if "datetime" in ohlc.columns else "time"
    ohlc[time_col] = pd.to_datetime(ohlc[time_col])
    ohlc = ohlc.rename(columns={time_col: "datetime"})
    t_from = pd.Timestamp(args.dt_from)
    t_to = pd.Timestamp(args.dt_to)
    ohlc = ohlc[(ohlc["datetime"] >= t_from) & (ohlc["datetime"] < t_to)].copy()
    ohlc = ohlc.sort_values("datetime").reset_index(drop=True)
    print(f"OHLC bars in range: {len(ohlc)}")

    trades["entry_time"] = pd.to_datetime(trades["entry_time"])
    trades["exit_time"] = pd.to_datetime(trades["exit_time"])

    in_trade = np.zeros(len(ohlc), dtype=bool)
    bar_times = ohlc["datetime"].values
    for _, t in trades.iterrows():
        mask = (bar_times >= t["entry_time"].to_numpy()) & (bar_times < t["exit_time"].to_numpy())
        in_trade |= mask

    ohlc["bar_range"] = ohlc["high"] - ohlc["low"]
    ohlc["in_trade"] = in_trade

    total_move = ohlc["bar_range"].sum()
    in_trade_move = ohlc.loc[ohlc["in_trade"], "bar_range"].sum()
    skip_move = ohlc.loc[~ohlc["in_trade"], "bar_range"].sum()
    in_trade_bars = ohlc["in_trade"].sum()
    skip_bars = (~ohlc["in_trade"]).sum()
    total_bars = len(ohlc)

    in_trade_pct = in_trade_bars / total_bars * 100
    skip_pct = skip_bars / total_bars * 100
    in_trade_move_pct = in_trade_move / total_move * 100
    skip_move_pct = skip_move / total_move * 100

    captured = trades["price_move"].sum()
    captured_pct = captured / in_trade_move * 100 if in_trade_move > 0 else 0

    # Per-regime breakdown
    regime_stats = []
    if "hmm_state" in trades.columns:
        for regime in ["Ranging", "Trending", "Volatile"]:
            rt = trades[trades["hmm_state"] == regime]
            r_in_trade = np.zeros(len(ohlc), dtype=bool)
            for _, t in rt.iterrows():
                mask = (bar_times >= t["entry_time"].to_numpy()) & (bar_times < t["exit_time"].to_numpy())
                r_in_trade |= mask
            r_move = ohlc.loc[r_in_trade, "bar_range"].sum()
            r_captured = rt["price_move"].sum()
            regime_stats.append({
                "regime": regime, "trades": len(rt),
                "in_trade_bars": int(r_in_trade.sum()),
                "in_trade_move_pts": round(r_move, 1),
                "captured_pts": round(r_captured, 1),
                "capture_of_intrade": round(r_captured / r_move * 100, 1) if r_move > 0 else 0,
            })

    # Per-hour skip move
    ohlc["hour"] = ohlc["datetime"].dt.hour
    hour_skip = ohlc[~ohlc["in_trade"]].groupby("hour")["bar_range"].sum()
    hour_total = ohlc.groupby("hour")["bar_range"].sum()

    print()
    print("=" * 70)
    print("AVAILABLE MOVE SPLIT: IN-TRADE vs SKIP")
    print(f"Period         : {args.dt_from} -> {args.dt_to}")
    print(f"Total M15 bars : {total_bars:,}")
    print(f"Total trades   : {len(trades)}")
    print("=" * 70)
    print()
    print(f"{'Category':<20} {'Bars':>8} {'%bars':>8} {'Move(pts)':>12} {'%move':>8}")
    print("-" * 60)
    print(f"{'IN-TRADE':<20} {in_trade_bars:>8,} {in_trade_pct:>7.1f}% {in_trade_move:>11,.1f} {in_trade_move_pct:>7.1f}%")
    print(f"{'SKIP (no trade)':<20} {skip_bars:>8,} {skip_pct:>7.1f}% {skip_move:>11,.1f} {skip_move_pct:>7.1f}%")
    print(f"{'TOTAL':<20} {total_bars:>8,} {'100.0':>7}% {total_move:>11,.1f} {'100.0':>7}%")
    print()
    print(f"Captured from in-trade move : {captured:>+,.1f} pts  ({captured_pct:.1f}% of in-trade available)")
    print(f"Left on table (skip move)   : {skip_move:>,.1f} pts  (move during no-trade)")
    print()

    if regime_stats:
        print("BY REGIME (in-trade only):")
        print(f"  {'Regime':<12} {'Trades':>7} {'InTradeBars':>12} {'InTradeMove':>12} {'Captured':>10} {'Capture%':>9}")
        for rs in regime_stats:
            print(f"  {rs['regime']:<12} {rs['trades']:>7} {rs['in_trade_bars']:>12,} {rs['in_trade_move_pts']:>11,.1f} {rs['captured_pts']:>+9,.1f} {rs['capture_of_intrade']:>8.1f}%")
        print()

    print("BY HOUR — skip move (move happening while NO trade is open):")
    print(f"  {'Hour':>4}  {'SkipMove':>10} {'TotalMove':>10} {'Skip%':>7}")
    for h in range(24):
        sm = hour_skip.get(h, 0)
        tm = hour_total.get(h, 0)
        sp = sm / tm * 100 if tm > 0 else 0
        print(f"  {h:>4}  {sm:>10,.1f} {tm:>10,.1f} {sp:>6.1f}%")
    print()

    # Save
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    report_path = out / "skip_available_move_report.txt"
    import io
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    print("=" * 70)
    print("AVAILABLE MOVE SPLIT: IN-TRADE vs SKIP")
    print(f"Period         : {args.dt_from} -> {args.dt_to}")
    print(f"Total M15 bars : {total_bars:,}")
    print(f"Total trades   : {len(trades)}")
    print("=" * 70)
    print()
    print(f"{'Category':<20} {'Bars':>8} {'%bars':>8} {'Move(pts)':>12} {'%move':>8}")
    print("-" * 60)
    print(f"{'IN-TRADE':<20} {in_trade_bars:>8,} {in_trade_pct:>7.1f}% {in_trade_move:>11,.1f} {in_trade_move_pct:>7.1f}%")
    print(f"{'SKIP (no trade)':<20} {skip_bars:>8,} {skip_pct:>7.1f}% {skip_move:>11,.1f} {skip_move_pct:>7.1f}%")
    print(f"{'TOTAL':<20} {total_bars:>8,} {'100.0':>7}% {total_move:>11,.1f} {'100.0':>7}%")
    print()
    print(f"Captured from in-trade move : {captured:>+,.1f} pts  ({captured_pct:.1f}% of in-trade available)")
    print(f"Left on table (skip move)   : {skip_move:>,.1f} pts  (move during no-trade)")
    sys.stdout = old_stdout
    report_path.write_text(buf.getvalue(), encoding="utf-8")

    summary = pd.DataFrame([{
        "period": f"{args.dt_from} -> {args.dt_to}",
        "total_bars": total_bars,
        "in_trade_bars": int(in_trade_bars),
        "skip_bars": int(skip_bars),
        "total_move_pts": round(total_move, 1),
        "in_trade_move_pts": round(in_trade_move, 1),
        "skip_move_pts": round(skip_move, 1),
        "captured_pts": round(captured, 1),
        "in_trade_pct": round(in_trade_pct, 1),
        "skip_pct": round(skip_pct, 1),
        "capture_of_intrade_pct": round(captured_pct, 1),
    }])
    summary.to_csv(out / "skip_available_move_summary.csv", index=False)

    hour_df = pd.DataFrame({
        "hour": range(24),
        "skip_move": [round(hour_skip.get(h, 0), 1) for h in range(24)],
        "total_move": [round(hour_total.get(h, 0), 1) for h in range(24)],
        "skip_pct": [round(hour_skip.get(h, 0) / hour_total.get(h, 1) * 100, 1) if hour_total.get(h, 0) > 0 else 0 for h in range(24)],
    })
    hour_df.to_csv(out / "skip_available_move_by_hour.csv", index=False)

    print(f"Saved: {report_path}")
    print(f"Saved: {out / 'skip_available_move_summary.csv'}")
    print(f"Saved: {out / 'skip_available_move_by_hour.csv'}")


if __name__ == "__main__":
    main()
