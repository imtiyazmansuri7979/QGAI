"""
smma_winner_quarterly_split.py
Split existing full-year Combo (baseline) + SMMA-winner trades into 4 quarters
and compare per-Q Total R / WR / PF / avg R. Answers: does SMMA-gate win in
3/4 quarters (real edge) or 1-2/4 (luck)?

No re-run needed — reads existing trades CSVs.
"""
import pandas as pd
from pathlib import Path

RES = Path(r"C:\QGAI\backtest\results\buy_sell_entry_timing_research")
COMBO = RES / "combo_sell_early_trail_confirm2_fullbt" / "backtest_trades_st-htf.csv"
SMMA  = RES / "smma_linear_w25_35_40_t70_p06_fullbt"  / "backtest_trades_st-htf.csv"
OUT   = Path(r"C:\QGAI\backtest\results\smma_winner_oos_quarterly") / "QUARTERLY_COMPARE.md"
OUT.parent.mkdir(parents=True, exist_ok=True)

QUARTERS = [
    ("Q1_2025Q3", "2025-06-29", "2025-09-29"),
    ("Q2_2025Q4", "2025-09-29", "2025-12-29"),
    ("Q3_2026Q1", "2025-12-29", "2026-03-29"),
    ("Q4_2026Q2", "2026-03-29", "2026-06-29"),
]

def stats(df):
    n = len(df)
    if n == 0: return dict(n=0, wr=0.0, total_r=0.0, avg_r=0.0, pf=0.0, wins=0, losses=0)
    r = pd.to_numeric(df["r_achieved"], errors="coerce").fillna(0.0)
    wins = (r > 0).sum(); losses = (r <= 0).sum()
    gp = r[r > 0].sum(); gl = -r[r <= 0].sum()
    pf = (gp / gl) if gl > 0 else float("inf")
    return dict(n=n, wr=100*wins/n, total_r=r.sum(), avg_r=r.mean(), pf=pf, wins=int(wins), losses=int(losses))

def load(p):
    df = pd.read_csv(p)
    df["entry_time"] = pd.to_datetime(df["entry_time"], errors="coerce")
    return df.dropna(subset=["entry_time"])

cb = load(COMBO)
sm = load(SMMA)

lines = ["# SMMA-Winner Quarterly OOS Compare",
         f"Source: `{COMBO.name}` (Combo/baseline) vs `{SMMA.name}` (SMMA-gate)",
         f"Full-year totals: Combo {len(cb)}tr — SMMA {len(sm)}tr",
         "",
         "| Quarter | Period | Config | Trades | WR% | Total R | avg R | PF |",
         "|---------|--------|--------|-------:|----:|--------:|------:|---:|"]

wins_smma = 0
per_q = []
for name, a, b in QUARTERS:
    A = pd.Timestamp(a); B = pd.Timestamp(b)
    q_cb = cb[(cb["entry_time"] >= A) & (cb["entry_time"] < B)]
    q_sm = sm[(sm["entry_time"] >= A) & (sm["entry_time"] < B)]
    s_cb = stats(q_cb); s_sm = stats(q_sm)
    per_q.append((name, s_cb, s_sm))
    won = s_sm["total_r"] > s_cb["total_r"]
    if won: wins_smma += 1
    mark = " ✅" if won else " ❌"
    lines.append(f"| {name} | {a}→{b} | Combo | {s_cb['n']} | {s_cb['wr']:.1f} | {s_cb['total_r']:+.1f} | {s_cb['avg_r']:+.3f} | {s_cb['pf']:.2f} |")
    lines.append(f"| {name} | {a}→{b} | SMMA{mark} | {s_sm['n']} | {s_sm['wr']:.1f} | {s_sm['total_r']:+.1f} | {s_sm['avg_r']:+.3f} | {s_sm['pf']:.2f} |")

lines += ["",
          f"## Verdict",
          f"- SMMA-gate beats Combo in **{wins_smma}/4 quarters**",
          "- Rule: **3-4/4 → real edge (proceed to live wire + DEMO)**",
          "- Rule: **1-2/4 → luck (do NOT adopt)**",
          "",
          "## Full-year totals",
          f"- Combo : {len(cb)} tr / {pd.to_numeric(cb['r_achieved'], errors='coerce').sum():+.1f}R",
          f"- SMMA  : {len(sm)} tr / {pd.to_numeric(sm['r_achieved'], errors='coerce').sum():+.1f}R",
          f"- Delta : {pd.to_numeric(sm['r_achieved'], errors='coerce').sum() - pd.to_numeric(cb['r_achieved'], errors='coerce').sum():+.1f}R",
         ]

OUT.write_text("\n".join(lines), encoding="utf-8")
print(OUT)
print("\n".join(lines))
