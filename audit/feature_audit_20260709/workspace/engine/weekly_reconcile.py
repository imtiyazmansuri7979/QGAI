"""
weekly_reconcile.py — FIX-3: weekly live(shadow)-vs-backtest parity check
==========================================================================
2026-07-03 (Divyesh audit FIX-3). One command does the whole weekly check:
  1. backtest_replay over the last N days (default 7) with the CURRENT live
     models + live config flags (buf 0.15, tp-regime, tp-equity 0, risk 3,
     fixed-lot 0.01 for clean R) -> one run folder
  2. reconcile_shadow vs engine/logs/shadow_trades.csv for the same window
All outputs land in ONE folder: backtest/results/reconcile_<end-date>/
(reconcile_summary.csv, matched_pairs.csv, backtest_only.csv, shadow_only.csv,
 backtest_report.txt, backtest_summary*.csv, trades/signals CSVs)

SCALING GATE (audit): 4-8 consecutive weeks with high entry overlap, similar
exit mix, and weekly R gap within +/-20% — before increasing capital.

Run:  python weekly_reconcile.py            (last 7 days)
      python weekly_reconcile.py --days 14
"""
import argparse, subprocess, sys
from datetime import datetime, timedelta
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
BT_RESULTS = ENGINE.parent / "backtest" / "results"

ap = argparse.ArgumentParser()
ap.add_argument("--days", type=int, default=7)
args = ap.parse_args()

d_to   = datetime.now().strftime("%Y-%m-%d")
d_from = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
out    = BT_RESULTS / f"reconcile_{d_to}"
out.mkdir(parents=True, exist_ok=True)

print(f"WEEKLY RECONCILE  {d_from} -> {d_to}  (folder: {out.name})")

print("\n[1/2] Backtest replay with CURRENT live models (live-match flags)...")
r = subprocess.run([sys.executable, "backtest_replay.py",
                    "--from", d_from, "--to", d_to,
                    "--risk", "3", "--ratchet", "on",
                    "--ratchet-buf-pct", "0.15",
                    "--tp-equity-pct", "0", "--tp-regime",
                    "--skip-counter-trend", "--fixed-lot", "0.01",
                    "--out-dir", str(out)],
                   cwd=ENGINE)
if r.returncode != 0:
    print("backtest_replay FAILED — stop. Tell Claude.")
    sys.exit(1)

print("\n[2/2] Reconciling vs shadow_trades.csv ...")
r2 = subprocess.run([sys.executable, "reconcile_shadow.py",
                     "--from", d_from, "--to", d_to,
                     "--backtest-glob", str(out / "backtest_trades*.csv"),
                     "--out-dir", str(out)],
                    cwd=ENGINE)
sys.exit(r2.returncode)
