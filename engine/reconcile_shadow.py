"""
reconcile_shadow.py — AUDIT FIX 3: shadow (live-computed) vs backtest reconciliation
=====================================================================================
2026-07-02 (Divyesh audit). Quantifies WHY live ≠ backtest for a period:
entry-set overlap, exit-reason mix, R differences on matched trades.
June 2026 audit finding: only 8/66 backtest entries matched shadow;
shadow TRAIL 49%% of exits vs backtest 11%%; shadow -1.9R vs backtest +48.1R.

Usage:
  python reconcile_shadow.py --from 2026-06-01 --to 2026-07-01 ^
      --backtest-glob "..\\backtest\\results\\wfo_live_match_015\\trades_*.csv" ^
      --out-dir "..\\backtest\\results\\reconcile_2026-06"

All outputs (summary CSV + matched/only CSVs) go to ONE folder (house rule).
"""
import argparse, glob, csv
from pathlib import Path
import pandas as pd

ENG = Path(__file__).resolve().parent
SHADOW = ENG / "logs" / "shadow_trades.csv"

ap = argparse.ArgumentParser()
ap.add_argument("--from", dest="date_from", required=True)
ap.add_argument("--to", dest="date_to", required=True)
ap.add_argument("--backtest-glob", required=True, help="glob of backtest/WFO trades_*.csv")
ap.add_argument("--out-dir", required=True)
args = ap.parse_args()

out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)

sh = pd.read_csv(SHADOW).drop_duplicates(subset=["entry_time", "direction", "entry_price"])
sh["et"] = pd.to_datetime(sh["entry_time"])
sh = sh[(sh.et >= args.date_from) & (sh.et < args.date_to)].copy()

frames = []
for f in sorted(glob.glob(args.backtest_glob)):
    try:
        d = pd.read_csv(f)
        if len(d):
            frames.append(d)
    except Exception:
        pass
bt = pd.concat(frames, ignore_index=True)
bt["et"] = pd.to_datetime(bt["entry_time"])
bt = bt[(bt.et >= args.date_from) & (bt.et < args.date_to)].copy()

bt["key"] = bt.et.astype(str) + "|" + bt.direction
sh["key"] = sh.et.astype(str) + "|" + sh.direction
common = set(bt.key) & set(sh.key)

m = bt.merge(sh, on="key", suffixes=("_bt", "_sh"))
bt_only = bt[~bt.key.isin(common)]
sh_only = sh[~sh.key.isin(common)]

def exit_mix(df, col):
    return df[col].value_counts(normalize=True).round(3).to_dict()

summary = [
    ["period", f"{args.date_from} -> {args.date_to}"],
    ["backtest trades", len(bt)],
    ["shadow trades", len(sh)],
    ["matched (same bar+direction)", len(common)],
    ["overlap % of backtest", round(100 * len(common) / max(len(bt), 1), 1)],
    ["backtest-only entries", len(bt_only)],
    ["shadow-only entries", len(sh_only)],
    ["backtest total R", round(bt.r_achieved.sum(), 1) if "r_achieved" in bt else ""],
    ["shadow total R", round(sh.R.sum(), 1)],
    ["backtest exit mix", str(exit_mix(bt, "exit_reason"))],
    ["shadow exit mix", str(exit_mix(sh, "exit_reason"))],
]
if len(m):
    same_exit = (m.exit_reason_bt == m.exit_reason_sh.replace({"TP": "TPCAP"})).mean()
    summary += [
        ["matched: same exit reason %", round(100 * same_exit, 1)],
        ["matched: avg R backtest", round(m.r_achieved.mean(), 3)],
        ["matched: avg R shadow", round(m.R.mean(), 3)],
        ["matched: mean R diff (bt-sh)", round((m.r_achieved - m.R).mean(), 3)],
    ]

with open(out / "reconcile_summary.csv", "w", newline="", encoding="utf-8-sig") as f:
    csv.writer(f).writerows([["metric", "value"]] + summary)
m.to_csv(out / "matched_pairs.csv", index=False)
bt_only.to_csv(out / "backtest_only.csv", index=False)
sh_only.to_csv(out / "shadow_only.csv", index=False)

print("RECONCILIATION SUMMARY")
for k, v in summary:
    print(f"  {k:32s}: {v}")
print(f"\nSaved -> {out}\\reconcile_summary.csv (+ matched_pairs / backtest_only / shadow_only)")
print("Gate for scaling capital: overlap should be HIGH and exit mix similar;")
print("weekly R difference within +/-20% (audit recommendation).")
