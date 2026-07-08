"""
tp_complete_analysis.py
========================
તમામ TP Results નું સંપૂર્ણ વિશ્લેષણ (tp_0.5 થી tp_3.0)

કોણ ચલાવવું:
    python tp_complete_analysis.py

NOTE (2026-06-26): Rewritten to be self-contained.
  - Reads the REAL report layout: backtest/results/backtests/tp_*/backtest_report.txt
  - Parses the AI-replay report format directly with regex (no OpenAI key needed).
  - Ranks by Profit Factor / Total-R, finds best TP per regime, exports a CSV.
The old version globbed `backtest/results_tp_*.txt` (never existed) and depended on
GPT for every report, so it always exited with "No TP files found".
"""

from pathlib import Path
import csv
import re
import sys

# Windows consoles default to cp1252 and can't print the emoji below.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

print("\n" + "=" * 80)
print("COMPLETE TP ANALYSIS (tp_0.5 to tp_3.0)")
print("=" * 80)

# ── locate reports ────────────────────────────────────────────────
# script lives in engine/, results live in ../backtest/results/backtests/tp_*/
HERE = Path(__file__).resolve().parent
BT_ROOT = (HERE / ".." / "backtest").resolve()
REPORT_DIR = BT_ROOT / "results" / "backtests"

report_files = sorted(
    REPORT_DIR.glob("tp_*/backtest_report.txt"),
    key=lambda p: float(p.parent.name.replace("tp_", "")),
)

print(f"\n✅ Found {len(report_files)} TP reports in {REPORT_DIR}\n")

if not report_files:
    print("❌ No TP reports found! Run backtest\\Run_TP_Sweep.bat first.")
    raise SystemExit(1)


# ── parser for the AI-replay report text ──────────────────────────
def _f(pattern, text, default=0.0):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else default


def parse_report(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8", errors="ignore")
    tp = float(path.parent.name.replace("tp_", ""))

    data = {
        "tp": tp,
        "file": str(path.relative_to(BT_ROOT)),
        "total_trades": int(_f(r"Trades\s*:\s*(\d+)", txt)),
        "win_rate": _f(r"Win rate\s*:\s*([\d.]+)%", txt),          # percent
        "profit_factor": _f(r"Profit factor\s*:\s*([\d.]+)", txt),
        "avg_r": _f(r"Avg R\s*:\s*\+?(-?[\d.]+)", txt),
        "total_r": _f(r"Total:\s*\+?(-?[\d.]+)R", txt),
        "max_drawdown": _f(r"Max drawdown\s*:\s*([\d.]+)%", txt),  # percent
        "regime": {},
    }
    for regime in ("Ranging", "Trending", "Volatile"):
        m = re.search(
            rf"{regime}\s+(\d+) trades \| WR\s+([\d.]+)% \|\s*\+?(-?[\d.]+)R \| avg \+?(-?[\d.]+)R",
            txt,
        )
        if m:
            data["regime"][regime] = {
                "trades": int(m.group(1)),
                "wr": float(m.group(2)),
                "total_r": float(m.group(3)),
                "avg_r": float(m.group(4)),
            }
    return data


results = [parse_report(p) for p in report_files]

# ── 1. ranking by profit factor ───────────────────────────────────
print("=" * 80)
print("RANKING BY PROFIT FACTOR")
print("=" * 80 + "\n")

by_pf = sorted(results, key=lambda x: x["profit_factor"], reverse=True)
for rank, d in enumerate(by_pf, 1):
    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"{rank:2d}.")
    print(
        f"{medal} TP {d['tp']:>4.2f} | PF {d['profit_factor']:>5.2f} | "
        f"WR {d['win_rate']:>5.1f}% | TotR {d['total_r']:>6.1f} | "
        f"AvgR {d['avg_r']:>+5.3f} | Trades {d['total_trades']:>3} | DD {d['max_drawdown']:.1f}%"
    )

# ── 2. best by each metric ────────────────────────────────────────
print("\n" + "=" * 80)
print("BEST TP BY METRIC")
print("=" * 80 + "\n")
best_pf = max(results, key=lambda x: x["profit_factor"])
best_tot = max(results, key=lambda x: x["total_r"])
best_dd = min(results, key=lambda x: x["max_drawdown"])
print(f"🏆 Best Profit Factor : TP {best_pf['tp']}  (PF {best_pf['profit_factor']:.2f})")
print(f"💰 Best Total-R       : TP {best_tot['tp']}  ({best_tot['total_r']:+.1f}R)")
print(f"🛡️  Lowest Drawdown    : TP {best_dd['tp']}  ({best_dd['max_drawdown']:.1f}%)")

# ── 3. best TP PER REGIME (the key question for live) ──────────────
print("\n" + "=" * 80)
print("BEST TP PER REGIME  (by Total-R, then avg-R)")
print("=" * 80 + "\n")
for regime in ("Ranging", "Trending", "Volatile"):
    rows = [r for r in results if regime in r["regime"]]
    if not rows:
        continue
    best = max(rows, key=lambda r: r["regime"][regime]["total_r"])
    rg = best["regime"][regime]
    print(
        f"  {regime:<9} → TP {best['tp']:>4.2f}  "
        f"({rg['total_r']:+.1f}R | avg {rg['avg_r']:+.3f} | WR {rg['wr']:.1f}% | {rg['trades']} trades)"
    )

# ── 4. CSV export ─────────────────────────────────────────────────
csv_file = BT_ROOT / "tp_comparison_summary.csv"
with open(csv_file, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(
        ["TP", "Trades", "Win_Rate_%", "Profit_Factor", "Avg_R", "Total_R", "Max_DD_%",
         "Rng_TotR", "Trn_TotR", "Vol_TotR", "File"]
    )
    for d in by_pf:
        rg = d["regime"]
        w.writerow([
            f"{d['tp']:.2f}", d["total_trades"], f"{d['win_rate']:.1f}",
            f"{d['profit_factor']:.2f}", f"{d['avg_r']:.3f}",
            f"{d['total_r']:.1f}", f"{d['max_drawdown']:.1f}",
            f"{rg.get('Ranging', {}).get('total_r', '')}",
            f"{rg.get('Trending', {}).get('total_r', '')}",
            f"{rg.get('Volatile', {}).get('total_r', '')}",
            d["file"],
        ])

print(f"\n✅ CSV saved: {csv_file}\n")
print("=" * 80 + "\n")
