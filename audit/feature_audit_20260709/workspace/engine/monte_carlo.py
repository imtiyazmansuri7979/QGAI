"""
monte_carlo.py — QUANT GOLD AI v2
═══════════════════════════════════════════════════════════════════
Monte Carlo robustness test on backtest trade results.

Reads logs/backtest_trades.csv (the r_achieved column) and runs
thousands of simulations to answer:
  * Was the backtest result luck, or a robust edge?
  * What's the realistic RANGE of outcomes (not one lucky path)?
  * Risk of ruin / large drawdown at a given risk %?
  * 5th–95th percentile final equity?

Two resampling methods:
  1. SHUFFLE  — same trades, random ORDER (tests path/sequence luck)
  2. BOOTSTRAP — resample trades WITH replacement (tests sample luck)

Compounding equity model: each trade risks `risk%` of CURRENT equity,
result = r_achieved × risk_amount  (matches backtest_replay sizing).

Run:
  python monte_carlo.py
  python monte_carlo.py --equity 10000 --risk 3 --runs 10000
  python monte_carlo.py --risk 2 --method bootstrap
  python monte_carlo.py --ruin 0.5          # define "ruin" as -50% equity
═══════════════════════════════════════════════════════════════════
"""
import sys, argparse
from pathlib import Path
import numpy as np
import pandas as pd

ENGINE = Path(__file__).resolve().parent
TRADES = ENGINE / "logs" / "backtest_trades.csv"


def load_r():
    if not TRADES.exists():
        print(f"❌ {TRADES} not found — run a backtest first."); sys.exit(1)
    df = pd.read_csv(TRADES)
    if "r_achieved" not in df.columns:
        print("❌ no r_achieved column in backtest_trades.csv"); sys.exit(1)
    r = df["r_achieved"].dropna().to_numpy(float)
    return r, df


def simulate(r, n_runs, n_trades, start_eq, risk_pct, method, ruin_frac, seed=7):
    rng = np.random.default_rng(seed)
    risk = risk_pct / 100.0
    finals = np.empty(n_runs)
    max_dds = np.empty(n_runs)
    ruined = 0
    ruin_level = start_eq * ruin_frac

    for i in range(n_runs):
        if method == "bootstrap":
            seq = rng.choice(r, size=n_trades, replace=True)
        else:  # shuffle
            seq = r.copy(); rng.shuffle(seq)
        eq = start_eq
        peak = start_eq
        max_dd = 0.0
        hit_ruin = False
        for rr in seq:
            eq += eq * risk * rr          # compounding: risk % of current equity
            if eq <= 0:
                eq = 1e-9; hit_ruin = True; break
            peak = max(peak, eq)
            dd = (peak - eq) / peak
            max_dd = max(max_dd, dd)
            if eq <= ruin_level:
                hit_ruin = True
        finals[i] = eq
        max_dds[i] = max_dd
        if hit_ruin:
            ruined += 1
    return finals, max_dds, ruined


def pct(a, p):
    return float(np.percentile(a, p))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity", type=float, default=10000)
    ap.add_argument("--risk", type=float, default=3.0)
    ap.add_argument("--runs", type=int, default=10000)
    ap.add_argument("--trades", type=int, default=0, help="trades per run (0 = same as backtest)")
    ap.add_argument("--method", choices=["shuffle", "bootstrap"], default="bootstrap")
    ap.add_argument("--ruin", type=float, default=0.5, help="ruin = equity falls to this fraction of start")
    args = ap.parse_args()

    r, df = load_r()
    n_trades = args.trades if args.trades > 0 else len(r)

    print("=" * 64)
    print("  MONTE CARLO SIMULATION — QGAI backtest robustness")
    print("=" * 64)
    print(f"  Source trades : {len(r)} (from backtest_trades.csv)")
    print(f"  Actual: WR {(r>0).mean()*100:.1f}% | avg R {r.mean():+.3f} | "
          f"total {r.sum():+.1f}R | best {r.max():+.2f} | worst {r.min():+.2f}")
    print(f"  Sim config    : {args.runs:,} runs × {n_trades} trades | "
          f"method={args.method} | risk {args.risk}%/trade | start ${args.equity:,.0f}")
    print(f"  Ruin defined  : equity ≤ {args.ruin*100:.0f}% of start (${args.equity*args.ruin:,.0f})")
    print("-" * 64)

    finals, max_dds, ruined = simulate(
        r, args.runs, n_trades, args.equity, args.risk, args.method, args.ruin)

    ret = (finals / args.equity - 1) * 100
    print("\n  FINAL EQUITY DISTRIBUTION:")
    for p in [5, 25, 50, 75, 95]:
        e = pct(finals, p)
        print(f"    {p:>2}th percentile : ${e:>16,.0f}   ({(e/args.equity-1)*100:+,.0f}%)")
    print(f"    mean            : ${finals.mean():>16,.0f}   ({(finals.mean()/args.equity-1)*100:+,.0f}%)")

    print("\n  MAX DRAWDOWN DISTRIBUTION:")
    for p in [50, 75, 90, 95, 99]:
        print(f"    {p:>2}th percentile : {pct(max_dds, p)*100:5.1f}%")
    print(f"    worst observed  : {max_dds.max()*100:5.1f}%")

    p_loss = (finals < args.equity).mean() * 100
    p_2x   = (finals >= args.equity*2).mean() * 100
    p_10x  = (finals >= args.equity*10).mean() * 100
    print("\n  PROBABILITIES:")
    print(f"    End below start (net loss) : {p_loss:5.1f}%")
    print(f"    End ≥ 2×  start            : {p_2x:5.1f}%")
    print(f"    End ≥ 10× start            : {p_10x:5.1f}%")
    print(f"    RISK OF RUIN (≤{args.ruin*100:.0f}%)        : {ruined/args.runs*100:5.1f}%")

    print("\n  VERDICT:")
    if p_loss < 5 and ruined/args.runs < 0.05:
        print("    ✅ ROBUST edge — net loss & ruin both rare across thousands of paths.")
    elif p_loss < 20:
        print("    🟡 POSITIVE but risky — most paths profit, but DD/ruin tail is real.")
    else:
        print("    ⚠️ FRAGILE — too many paths lose; result may be sequence-luck.")
    if pct(max_dds, 95) > 0.40:
        print(f"    ⚠️ 95th-pct drawdown {pct(max_dds,95)*100:.0f}% is steep — consider lower risk%.")
    print("=" * 64)


if __name__ == "__main__":
    main()
