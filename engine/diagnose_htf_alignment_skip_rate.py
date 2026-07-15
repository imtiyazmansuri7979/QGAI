"""
diagnose_htf_alignment_skip_rate.py -- Imtiyaz's follow-up to the win_prob
calibration diagnostic (2026-07-14): "most of the aligned_strong bars are
probably SKIPPED, not traded -- that's the real question."

The prior diagnostic (diagnose_win_prob_calibration.py) only looked at the
207 EXECUTED trades from the 3-month WFO OOS run -- it cannot see skipped
bars at all. This script looks at EVERY bar (BUY/SELL/SKIP alike) from that
same run's per-bar signal log (ALL_OOS_signals.csv) and asks: of the bars
where the 4 HTF-direction signals (H1 ADX-DI, H4 ADX-DI, H1 SMMA-trend,
H4 SMMA-trend) agree on a direction, how many were actually traded vs
skipped?

ALL_OOS_signals.csv already has H1_DI_diff/H4_DI_diff for every bar, but
NOT ts_trend_h1/ts_trend_h4 individually (only the combined ts_htf_agreement
= trend_m15+trend_h1+trend_h4). Those two are recomputed here directly from
OHLC via the same frozen trend_signal.compute_trend() used everywhere else
in the codebase -- deterministic indicator math, NOT a model call, NOT a
retrain, NOT new inference. Read-only.

Run:  python diagnose_htf_alignment_skip_rate.py
      [--signals-csv path] [--out-dir path]
"""
import argparse
import numpy as np
import pandas as pd
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
DEFAULT_SIGNALS_CSV = (ENGINE.parent / "backtest" / "results"
                        / "volhtfgate_wfo_TEST_A_off" / "ALL_OOS_signals.csv")

from config import CFG
from features import load_ohlc, build_trend_signal_tables, get_trend_signal_features


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals-csv", default=str(DEFAULT_SIGNALS_CSV))
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    print("=" * 70)
    print("HTF-ALIGNMENT SKIP-RATE DIAGNOSTIC (every bar, not just executed trades)")
    print(f"Source: {args.signals_csv}")
    print("=" * 70)

    sig = pd.read_csv(args.signals_csv)
    sig["bar_time"] = pd.to_datetime(sig["bar_time"])
    print(f"Bars: {len(sig):,} | signal counts: {sig['signal'].value_counts().to_dict()}")

    print("\nLoading OHLC + recomputing H1/H4 SMMA trend (frozen indicator, no model)...")
    ohlc_df = load_ohlc(CFG.paths.ohlc_file)
    ts_tables = build_trend_signal_tables(ohlc_df)

    ts_h1, ts_h4 = [], []
    for t in sig["bar_time"]:
        f = get_trend_signal_features(t, "BUY", None, None, ts_tables)
        ts_h1.append(f.get("ts_trend_h1", 0.0))
        ts_h4.append(f.get("ts_trend_h4", 0.0))
    sig["ts_trend_h1"] = ts_h1
    sig["ts_trend_h4"] = ts_h4

    # 4 HTF-direction signals, each +1 (bullish) / -1 (bearish)
    votes = np.column_stack([
        np.sign(sig["H1_DI_diff"].fillna(0)),
        np.sign(sig["H4_DI_diff"].fillna(0)),
        sig["ts_trend_h1"].fillna(0),
        sig["ts_trend_h4"].fillna(0),
    ])
    score_buy = (votes > 0).sum(axis=1)     # 0..4 signals pointing BUY
    score_sell = (votes < 0).sum(axis=1)    # 0..4 signals pointing SELL

    consensus = np.where(score_buy > score_sell, "BUY",
                 np.where(score_sell > score_buy, "SELL", "NONE"))  # NONE = 2-2 tie
    agree_strength = np.maximum(score_buy, score_sell)

    bucket = np.select(
        [(agree_strength == 4) & (consensus != "NONE"),
         (agree_strength == 3) & (consensus != "NONE")],
        ["aligned_strong", "aligned_weak"],
        default="mixed_disagree",
    )
    sig["htf_consensus_dir"] = consensus
    sig["agree_strength"] = agree_strength
    sig["bucket"] = bucket

    # outcome relative to the HTF consensus direction (only meaningful when
    # a consensus direction exists, i.e. NOT mixed_disagree)
    def _outcome(row):
        if row["bucket"] == "mixed_disagree":
            return "n/a (no consensus)"
        if row["signal"] == "SKIP":
            return "SKIPPED"
        if row["signal"] == row["htf_consensus_dir"]:
            return "TRADED_WITH_CONSENSUS"
        return "TRADED_AGAINST_CONSENSUS"  # model traded the opposite side
    sig["outcome"] = sig.apply(_outcome, axis=1)

    out_dir = Path(args.out_dir) if args.out_dir else (
        ENGINE.parent / "backtest" / "results" / "htf_alignment_skip_rate_diagnostic")
    out_dir.mkdir(parents=True, exist_ok=True)
    sig.to_csv(out_dir / "htf_alignment_skip_rate_detail.csv", index=False)

    lines = []
    lines.append("=" * 70)
    lines.append("HTF-ALIGNMENT SKIP-RATE DIAGNOSTIC")
    lines.append(f"Source: {args.signals_csv}")
    lines.append(f"Total bars: {len(sig):,}")
    lines.append("-" * 70)
    lines.append(f"{'bucket':<16}{'n':>7}{'SKIPPED':>10}{'TRADED_w':>10}{'TRADED_x':>10}"
                 f"{'skip%':>8}{'avg_wp_skip':>13}{'avg_wp_traded':>15}")
    summary_rows = []
    for b in ["aligned_strong", "aligned_weak", "mixed_disagree"]:
        g = sig[sig["bucket"] == b]
        n = len(g)
        if n == 0:
            continue
        n_skip = int((g["outcome"] == "SKIPPED").sum())
        n_with = int((g["outcome"] == "TRADED_WITH_CONSENSUS").sum())
        n_against = int((g["outcome"] == "TRADED_AGAINST_CONSENSUS").sum())
        skip_pct = 100 * n_skip / n if n else 0.0
        wp_skip = g.loc[g["outcome"] == "SKIPPED", "win_prob"].mean()
        wp_traded = g.loc[g["outcome"].isin(["TRADED_WITH_CONSENSUS", "TRADED_AGAINST_CONSENSUS"]),
                          "win_prob"].mean()
        lines.append(f"{b:<16}{n:>7}{n_skip:>10}{n_with:>10}{n_against:>10}"
                     f"{skip_pct:>7.1f}%{wp_skip:>13.3f}{wp_traded:>15.3f}")
        summary_rows.append({
            "bucket": b, "n_bars": n, "n_skipped": n_skip,
            "n_traded_with_consensus": n_with, "n_traded_against_consensus": n_against,
            "skip_pct": round(skip_pct, 1),
            "avg_win_prob_when_skipped": round(wp_skip, 4) if pd.notna(wp_skip) else None,
            "avg_win_prob_when_traded": round(wp_traded, 4) if pd.notna(wp_traded) else None,
        })
    lines.append("-" * 70)
    lines.append("READ THIS AS: for bars where the 4 HTF signals (H1/H4 ADX-DI + H1/H4 SMMA")
    lines.append("trend) agree on a direction, how many did the model actually TRADE vs SKIP?")
    lines.append("A high skip_pct in aligned_strong directly answers Imtiyaz's question: the")
    lines.append("model IS mostly skipping the bars where HTF signals fully agree -- the prior")
    lines.append("calibration diagnostic (win_prob vs realized WR) only ever saw the minority")
    lines.append("that got traded, which is why its aligned_strong sample (n=74) was small and")
    lines.append("its avg_R (+0.008) looked weak -- most of the bucket never got a chance to prove")
    lines.append("itself either way.")
    lines.append("")
    lines.append("CAVEAT: SKIPPED here means this run's ACTUAL win_prob (from the real model,")
    lines.append("real threshold) came out below threshold for the executed side. It does NOT by")
    lines.append("itself prove those skips were WRONG (missed profit) -- that needs the next step:")
    lines.append("shadow-simulating what WOULD have happened if every aligned_strong SKIP had been")
    lines.append("traded anyway (a proper missed-profit quantification, Fable-5's Step 3).")
    lines.append("=" * 70)
    report = "\n".join(lines)
    print("\n" + report)
    (out_dir / "htf_alignment_skip_rate_report.txt").write_text(report, encoding="utf-8")
    pd.DataFrame(summary_rows).to_csv(out_dir / "htf_alignment_skip_rate_summary.csv", index=False)

    print(f"\nSaved: {out_dir / 'htf_alignment_skip_rate_detail.csv'}")
    print(f"Saved: {out_dir / 'htf_alignment_skip_rate_summary.csv'}")
    print(f"Saved: {out_dir / 'htf_alignment_skip_rate_report.txt'}")


if __name__ == "__main__":
    main()
