"""
analyze_post_cap_continuation.py -- Post-cap continuation audit (Fable-5 recommended,
2026-07-13, 4th opinion on smart Exit-AI vs rule-based exits).

For every trade in a given backtest_trades_*.csv that exited via the TP-cap
(exit_reason == TPCAP), this measures how far price kept moving in the trade's
favor AFTER the cap -- following the SAME H1-line trail + HTF-flip exit already
live for non-capped trades -- until either that trail is hit or the HTF flips.
Quantifies "money left on the table" by the hard TP-cap vs a trail-only exit.

Pure pandas + OHLC replay. No model, no retrain, no live/demo impact. Read-only.
"""
import argparse
import numpy as np, pandas as pd
from pathlib import Path

from analyze_capture import load_ohlc, htf_lines, BUF, SLMIN


def continue_trade(direction, cap_exit_time, cap_exit_price, ohlc, buyH1, sellH1, flipH1,
                    idx_of, max_bars):
    sgn = 1 if direction == "BUY" else -1
    i0 = idx_of.get(cap_exit_time)
    if i0 is None:
        return None
    n = len(ohlc)
    hi = ohlc["high"].to_numpy(); lo = ohlc["low"].to_numpy(); cl = ohlc["close"].to_numpy()
    line0 = buyH1[i0] if sgn > 0 else sellH1[i0]
    if line0 is None or np.isnan(line0):
        return None
    buf_abs = cap_exit_price * BUF / 100.0
    vsl = line0 - sgn * buf_abs
    min_dist = cap_exit_price * SLMIN / 100.0
    if abs(cap_exit_price - vsl) < min_dist:
        vsl = cap_exit_price - sgn * min_dist
    peak_price = cap_exit_price
    j_end = min(i0 + max_bars, n - 1)
    exit_px, exit_rsn, exit_t = cap_exit_price, "HORIZON", ohlc["time"].iloc[j_end]
    for j in range(i0 + 1, j_end + 1):
        ln = buyH1[j] if sgn > 0 else sellH1[j]
        if ln is not None and not np.isnan(ln):
            new_sl = ln - sgn * buf_abs
            if (sgn > 0 and new_sl > vsl) or (sgn < 0 and new_sl < vsl):
                vsl = new_sl
        cur_px = cl[j]
        if (sgn > 0 and cur_px > peak_price) or (sgn < 0 and cur_px < peak_price):
            peak_price = cur_px
        if (sgn > 0 and lo[j] <= vsl) or (sgn < 0 and hi[j] >= vsl):
            exit_px, exit_rsn, exit_t = vsl, "TRAIL_SL", ohlc["time"].iloc[j]
            break
        fl = flipH1[j]
        if fl == -sgn:
            exit_px, exit_rsn, exit_t = cl[j], "HTF_FLIP", ohlc["time"].iloc[j]
            break
    continuation_pts = (exit_px - cap_exit_price) * sgn
    peak_pts = (peak_price - cap_exit_price) * sgn
    giveback_pts = peak_pts - continuation_pts
    return dict(continuation_exit_time=exit_t, continuation_exit_reason=exit_rsn,
                continuation_exit_price=exit_px, continuation_pts=continuation_pts,
                peak_pts_after_cap=peak_pts, giveback_pts=giveback_pts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades-csv", required=True)
    ap.add_argument("--max-bars", type=int, default=384,
                     help="max M15 bars to look ahead after cap-touch (default 384 = 4 days)")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    trades_path = Path(args.trades_csv)
    trades = pd.read_csv(trades_path, parse_dates=["entry_time", "exit_time"])
    capped = trades[trades["exit_reason"] == "TPCAP"].copy()
    print(f"Loaded {len(trades)} trades from {trades_path.name} | {len(capped)} exited via TPCAP")
    if capped.empty:
        print("No TPCAP-exited trades found -- nothing to audit.")
        return

    ohlc = load_ohlc()
    idx_of = {t: i for i, t in enumerate(ohlc["time"])}
    buyH1, sellH1, flipH1 = htf_lines(ohlc)

    rows = []
    for _, tr in capped.iterrows():
        res = continue_trade(tr["direction"], tr["exit_time"], tr["exit_price"],
                              ohlc, buyH1, sellH1, flipH1, idx_of, args.max_bars)
        if res is None:
            continue
        sl_dist = tr["sl_dist"] if pd.notna(tr["sl_dist"]) and tr["sl_dist"] else np.nan
        row = {
            "entry_time": tr["entry_time"], "exit_time": tr["exit_time"], "direction": tr["direction"],
            "entry_price": tr["entry_price"], "cap_exit_price": tr["exit_price"],
            "actual_r_achieved": tr["r_achieved"], "sl_dist": sl_dist,
        }
        row.update(res)
        row["continuation_R"] = row["continuation_pts"] / sl_dist if sl_dist and not np.isnan(sl_dist) else np.nan
        rows.append(row)

    det = pd.DataFrame(rows)
    out_dir = Path(args.out_dir) if args.out_dir else trades_path.parent / "post_cap_audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    det_path = out_dir / "post_cap_audit_detail.csv"
    det.to_csv(det_path, index=False)

    n = len(det)
    pos = int((det["continuation_pts"] > 0).sum())
    neg = int((det["continuation_pts"] < 0).sum())
    total_extra_pts = float(det["continuation_pts"].sum())
    total_extra_R = float(det["continuation_R"].sum(skipna=True))
    avg_extra_pts = float(det["continuation_pts"].mean())
    median_extra_pts = float(det["continuation_pts"].median())
    avg_giveback = float(det["giveback_pts"].mean())
    exit_mix = det["continuation_exit_reason"].value_counts().to_dict()

    lines = []
    lines.append("=" * 64)
    lines.append("POST-CAP CONTINUATION AUDIT (Fable-5 recommended, 2026-07-13)")
    lines.append(f"Source trades : {trades_path}")
    lines.append(f"TPCAP trades  : {n} (of {len(trades)} total)")
    lines.append(f"Look-ahead    : up to {args.max_bars} M15 bars after cap-touch, "
                 f"exit at HTF-flip or trail-SL hit (same rule already live for non-capped trades)")
    lines.append("-" * 64)
    lines.append(f"Continued FAVORABLY (more profit after cap) : {pos}/{n} ({100*pos/n:.1f}%)")
    lines.append(f"Continued UNFAVORABLY (reversed, lost back) : {neg}/{n} ({100*neg/n:.1f}%)")
    lines.append(f"Total extra pts if held to flip/trail-SL    : {total_extra_pts:+,.1f} pts  ({total_extra_R:+.2f}R)")
    lines.append(f"Avg extra pts per capped trade               : {avg_extra_pts:+.2f} pts")
    lines.append(f"Median extra pts per capped trade             : {median_extra_pts:+.2f} pts")
    lines.append(f"Avg giveback (peak vs eventual exit)          : {avg_giveback:+.2f} pts")
    lines.append(f"Continuation exit mix                         : {exit_mix}")
    lines.append("-" * 64)
    lines.append("READ THIS AS: if total extra R is clearly positive and giveback is small, the TP")
    lines.append("cap is leaving real money on the table -> worth trying partial-exit-at-cap or")
    lines.append("trail-tighten-at-cap (Fable-5 recommendation) and WFO A/B testing it. If giveback")
    lines.append("is large relative to extra pts, the cap is doing its job (giveback insurance) and")
    lines.append("capture% should just be retired as a target, not chased with a design change.")
    lines.append("=" * 64)
    report_txt = "\n".join(lines)
    print("\n" + report_txt)
    (out_dir / "post_cap_audit_report.txt").write_text(report_txt, encoding="utf-8")

    summary = pd.DataFrame([{
        "trades_csv": str(trades_path), "n_capped": n,
        "pct_continued_favorable": 100 * pos / n if n else np.nan,
        "pct_continued_unfavorable": 100 * neg / n if n else np.nan,
        "total_extra_pts": total_extra_pts, "total_extra_R": total_extra_R,
        "avg_extra_pts": avg_extra_pts, "median_extra_pts": median_extra_pts,
        "avg_giveback_pts": avg_giveback,
    }])
    summary.to_csv(out_dir / "post_cap_audit_summary.csv", index=False)
    print(f"\nSaved: {det_path}")
    print(f"Saved: {out_dir / 'post_cap_audit_summary.csv'}")
    print(f"Saved: {out_dir / 'post_cap_audit_report.txt'}")


if __name__ == "__main__":
    main()
