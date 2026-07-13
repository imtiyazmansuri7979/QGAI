"""
diagnose_win_prob_calibration.py -- win_prob calibration by HTF-direction
agreement state (Fable-5 recommended, 2026-07-13 night, Step 1 of the
"why does win_prob stay conservative during a clearly ADX+SMMA-aligned move"
investigation).

Uses an EXISTING backtest trades CSV (default: the 3-month WFO OOS run,
207 real executed trades, `ALL_OOS_trades.csv`) -- no new model inference,
no retrain, no shadow-simulation. Every row already has: the model's own
predicted win_prob at entry, the REALIZED outcome (r_achieved), and the raw
H1/H4 ADX-DI direction + SMMA ts_trend features.

For each trade, counts how many of the 4 HTF-direction signals
(H1 ADX-DI, H4 ADX-DI, H1 SMMA-trend, H4 SMMA-trend) agree with the
direction actually traded, and buckets:
  aligned_strong : all 4 agree      (score == 4)
  aligned_weak   : 3 of 4 agree     (score == 3)
  mixed_disagree : <=2 of 4 agree   (score <= 2)

Reports, per bucket: avg PREDICTED win_prob vs REALIZED win-rate. A large
gap in aligned_strong (predicted well below realized) is the calibration
signature of "the model stays conservative even when ADX+SMMA clearly
agree" -- confirming or ruling out the concern BEFORE any bigger
feature-architecture fix is attempted.

Read-only. No training. No live/demo impact. Pure pandas on an existing CSV.
"""
import argparse
import numpy as np, pandas as pd
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
DEFAULT_CSV = (ENGINE.parent / "backtest" / "results" / "volhtfgate_wfo_TEST_A_off"
               / "ALL_OOS_trades.csv")


def bucket_agreement(df):
    trade_dir = np.where(df["direction"].str.upper() == "BUY", 1.0, -1.0)
    sigs = np.column_stack([
        np.sign(df["f_H1_DI_diff"].fillna(0)),
        np.sign(df["f_H4_DI_diff"].fillna(0)),
        df["f_ts_trend_h1"].fillna(0),
        df["f_ts_trend_h4"].fillna(0),
    ])
    score = (sigs == trade_dir[:, None]).sum(axis=1)
    bucket = np.select(
        [score == 4, score == 3],
        ["aligned_strong", "aligned_weak"],
        default="mixed_disagree",
    )
    return bucket, score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades-csv", default=str(DEFAULT_CSV))
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    trades_path = Path(args.trades_csv)
    print("=" * 64)
    print("WIN_PROB CALIBRATION BY HTF-AGREEMENT STATE (cheap, existing data)")
    print(f"Source: {trades_path}")
    print("=" * 64)
    df = pd.read_csv(trades_path)
    need = ["direction", "f_H1_DI_diff", "f_H4_DI_diff", "f_ts_trend_h1",
            "f_ts_trend_h4", "win_prob", "r_achieved"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        print(f"ERROR: trades CSV is missing required columns: {missing}")
        return
    df = df.dropna(subset=need).copy()
    print(f"Trades usable: {len(df):,}")

    df["agree_bucket"], df["agree_score"] = bucket_agreement(df)
    df["win"] = (df["r_achieved"] > 0).astype(int)

    out_dir = Path(args.out_dir) if args.out_dir else (
        ENGINE.parent / "backtest" / "results" / "win_prob_calibration_diagnostic")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "calibration_detail.csv", index=False)

    lines = []
    lines.append("=" * 64)
    lines.append("WIN_PROB CALIBRATION BY HTF-AGREEMENT STATE")
    lines.append(f"Source: {trades_path}")
    lines.append(f"Trades: {len(df):,}")
    lines.append("-" * 64)
    lines.append(f"{'bucket':<16}{'n':>6}{'avg_predicted':>16}{'realized_WR':>14}{'gap':>10}{'avg_R':>10}")
    summary_rows = []
    for b in ["aligned_strong", "aligned_weak", "mixed_disagree"]:
        g = df[df["agree_bucket"] == b]
        if g.empty:
            lines.append(f"{b:<16}{'(no trades)':>6}")
            continue
        n = len(g)
        avg_pred = g["win_prob"].mean()
        realized_wr = g["win"].mean()
        gap = realized_wr - avg_pred
        avg_r = g["r_achieved"].mean()
        lines.append(f"{b:<16}{n:>6}{avg_pred*100:>15.1f}%{realized_wr*100:>13.1f}%"
                      f"{gap*100:>+9.1f}%{avg_r:>+10.3f}")
        summary_rows.append({"bucket": b, "n": n, "avg_predicted_win_prob": avg_pred,
                              "realized_win_rate": realized_wr, "gap": gap, "avg_R": avg_r})
    lines.append("-" * 64)
    lines.append("READ THIS AS: 'gap' = realized win-rate MINUS predicted win_prob, per bucket.")
    lines.append("A clearly POSITIVE gap in aligned_strong (realized > predicted) means the model")
    lines.append("is systematically UNDERCONFIDENT exactly when ADX+SMMA both agree with the trade")
    lines.append("direction -- confirms the live conservatism concern. A gap near zero means the")
    lines.append("model IS well-calibrated there and the 'too conservative' read was a perception")
    lines.append("issue (or explained by something else), not a model defect -- stop here.")
    lines.append("")
    lines.append("CAVEAT: this dataset is EXECUTED trades only (already passed the entry threshold).")
    lines.append("It cannot directly prove trades were WRONGLY skipped -- only whether the model is")
    lines.append("honest about trades it already takes. If a real underconfidence gap shows up here,")
    lines.append("the next (more expensive) step is a full shadow-simulation across SKIPPED bars too")
    lines.append("(Fable-5's Step 3: missed-profit quantification), not a feature-architecture change yet.")
    lines.append("=" * 64)
    report = "\n".join(lines)
    print("\n" + report)
    (out_dir / "calibration_report.txt").write_text(report, encoding="utf-8")

    pd.DataFrame(summary_rows).to_csv(out_dir / "calibration_summary.csv", index=False)
    print(f"\nSaved: {out_dir / 'calibration_detail.csv'}")
    print(f"Saved: {out_dir / 'calibration_summary.csv'}")
    print(f"Saved: {out_dir / 'calibration_report.txt'}")


if __name__ == "__main__":
    main()
