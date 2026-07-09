"""
monte_carlo_segmented.py — QUANT GOLD AI v2
═══════════════════════════════════════════════════════════════════
Monte Carlo robustness, SEGMENTED by market regime and time session.

Answers the question: is the edge robust IN EACH regime
(Volatile / Trending / Ranging) and in EACH time session — or does
the overall +R hide a weak/lucky segment?

For every segment it runs N bootstrap simulations and reports:
  * actual stats (n, WR, avg R, total R)
  * 5th / 50th / 95th percentile final equity (segment-only compounding)
  * probability of net loss
  * verdict (ROBUST / POSITIVE / FRAGILE / TOO-FEW)

Segments:
  REGIME   : Ranging, Trending, Volatile (from hmm_state)
  SESSION  : Asian 23-07, London 07-13, NY 13-21, Late 21-23 (entry hour)
  + COMBINED (regime × session) optional grid

Run:
  python monte_carlo_segmented.py
  python monte_carlo_segmented.py --risk 3 --runs 5000
  python monte_carlo_segmented.py --grid          # regime×session matrix
═══════════════════════════════════════════════════════════════════
"""
import sys, argparse
from pathlib import Path
import numpy as np
import pandas as pd

ENGINE = Path(__file__).resolve().parent
TRADES = ENGINE / "logs" / "backtest_trades.csv"

SESSIONS = [  # name, start_hour, end_hour (entry hour, broker time)
    ("Asian  (23-07)", lambda h: (h >= 23) or (h < 7)),
    ("London (07-13)", lambda h: 7 <= h < 13),
    ("NY     (13-21)", lambda h: 13 <= h < 21),
    ("Late   (21-23)", lambda h: 21 <= h < 23),
]

MIN_TRADES = 30   # below this, a segment is "TOO-FEW" to judge


def load():
    if not TRADES.exists():
        print(f"❌ {TRADES} not found — run a backtest first."); sys.exit(1)
    df = pd.read_csv(TRADES)
    df = df[df["r_achieved"].notna()].copy()
    df["hour"] = pd.to_datetime(df["entry_time"]).dt.hour
    return df


def mc_segment(r, n_runs, start_eq, risk_pct, seed=7):
    """Bootstrap MC on one segment's R array. Returns (p5,p50,p95,p_loss,avgR,total)."""
    if len(r) == 0:
        return None
    rng = np.random.default_rng(seed)
    risk = risk_pct / 100.0
    n = len(r)
    finals = np.empty(n_runs)
    for i in range(n_runs):
        seq = rng.choice(r, size=n, replace=True)
        eq = start_eq
        for rr in seq:
            eq += eq * risk * rr
            if eq <= 0:
                eq = 1e-9; break
        finals[i] = eq
    p_loss = (finals < start_eq).mean() * 100
    return (np.percentile(finals, 5), np.percentile(finals, 50),
            np.percentile(finals, 95), p_loss, r.mean(), r.sum())


def verdict(n, p_loss, avg_r):
    if n < MIN_TRADES:
        return "⚪ TOO-FEW (need ≥30)"
    if avg_r <= 0:
        return "🔴 NEGATIVE edge — avoid"
    if p_loss < 10:
        return "✅ ROBUST"
    if p_loss < 30:
        return "🟡 POSITIVE (some risk)"
    return "⚠️ FRAGILE (luck-prone)"


def report_segments(df, title, segments, n_runs, start_eq, risk):
    print(f"\n{'='*78}\n  {title}\n{'='*78}")
    print(f"  {'segment':<18}{'n':>5}{'WR':>6}{'avgR':>8}{'totR':>8}"
          f"{'5th%':>11}{'50th%':>11}{'P(loss)':>9}  verdict")
    print("  " + "-" * 88)
    for name, r in segments:
        if len(r) == 0:
            print(f"  {name:<18}{'0':>5}  — no trades —"); continue
        res = mc_segment(r, n_runs, start_eq, risk)
        p5, p50, p95, p_loss, avg_r, total = res
        wr = (r > 0).mean() * 100
        v = verdict(len(r), p_loss, avg_r)
        print(f"  {name:<18}{len(r):>5}{wr:>5.0f}%{avg_r:>+8.3f}{total:>+8.1f}"
              f"{p5:>11,.0f}{p50:>11,.0f}{p_loss:>8.1f}%  {v}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity", type=float, default=10000)
    ap.add_argument("--risk", type=float, default=3.0)
    ap.add_argument("--runs", type=int, default=5000)
    ap.add_argument("--grid", action="store_true", help="also show regime×session matrix")
    args = ap.parse_args()

    df = load()
    print("=" * 78)
    print("  MONTE CARLO — SEGMENTED by REGIME & TIME")
    print("=" * 78)
    print(f"  Total trades : {len(df)} | overall WR {(df['r_achieved']>0).mean()*100:.1f}% "
          f"| avg R {df['r_achieved'].mean():+.3f} | total {df['r_achieved'].sum():+.1f}R")
    print(f"  Sim: {args.runs:,} bootstrap runs/segment | risk {args.risk}% | start ${args.equity:,.0f}")
    print(f"  Note: each segment compounds ALONE (isolates that segment's edge)")

    # ALL
    report_segments(df, "OVERALL (baseline)",
                    [("ALL", df["r_achieved"].to_numpy())],
                    args.runs, args.equity, args.risk)

    # BY REGIME
    regs = [(s, df[df["hmm_state"] == s]["r_achieved"].to_numpy())
            for s in ["Ranging", "Trending", "Volatile"]]
    report_segments(df, "BY REGIME (hmm_state)", regs, args.runs, args.equity, args.risk)

    # BY SESSION
    sess = [(name, df[df["hour"].apply(fn)]["r_achieved"].to_numpy())
            for name, fn in SESSIONS]
    report_segments(df, "BY TIME SESSION (entry hour)", sess, args.runs, args.equity, args.risk)

    # GRID regime × session
    if args.grid:
        print(f"\n{'='*78}\n  REGIME × SESSION GRID (avg R | n)\n{'='*78}")
        print(f"  {'regime':<12}" + "".join(f"{nm.split()[0]:>14}" for nm, _ in SESSIONS))
        for s in ["Ranging", "Trending", "Volatile"]:
            row = f"  {s:<12}"
            for nm, fn in SESSIONS:
                seg = df[(df["hmm_state"] == s) & (df["hour"].apply(fn))]["r_achieved"]
                if len(seg) == 0:
                    row += f"{'·':>14}"
                else:
                    row += f"{seg.mean():>+8.2f}|{len(seg):>3}"
            print(row)
        print("\n  (negative or thin cells = avoid that regime+session combo)")

    print("\n" + "=" * 78)
    print("  HOW TO READ:")
    print("    ✅ ROBUST   = even the unlucky 5th-percentile path profits → trust it")
    print("    🟡 POSITIVE = profits on average but has a real losing tail")
    print("    ⚠️ FRAGILE  = >30% of paths lose → edge may be luck, tighten filter")
    print("    🔴 NEGATIVE = avg R ≤ 0 → this segment LOSES money, consider blocking")
    print("=" * 78)


if __name__ == "__main__":
    main()
