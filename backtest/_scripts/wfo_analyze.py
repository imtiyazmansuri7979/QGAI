"""WFO OOS analysis — $10,000 account, weekly + monthly + summary.
Reads wfo_results/ALL_OOS_trades.csv (real entry/exit prices + R per OOS trade)
and builds a continuous $10k account (3% risk compounding), then breaks the
P&L down by WEEK and by MONTH. Saves WFO_WEEKLY.csv + WFO_MONTHLY.csv."""
import sys, io, pandas as pd, numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os as _os
# Optional arg: python wfo_analyze.py [folder-name]  (default wfo_results).
# e.g.  python wfo_analyze.py wfo_results_ratchet
_dir = sys.argv[1] if len(sys.argv) > 1 else "wfo_results"
_base = _dir if _os.path.isabs(_dir) else rf"C:\QGAI\backtest\results\{_dir}"
TRADES = _os.path.join(_base, "ALL_OOS_trades.csv")
OUTDIR = _base
START  = 10000.0
RISK   = 3.0      # % of equity risked per trade (change to 1 or 2 for safer)

d = pd.read_csv(TRADES)
d["r"]  = pd.to_numeric(d["r_achieved"], errors="coerce")
d = d.dropna(subset=["r"]).reset_index(drop=True)
# use exit_time as the realisation time; fall back to entry_time
d["t"] = pd.to_datetime(d.get("exit_time", d["entry_time"]), errors="coerce")
d = d.dropna(subset=["t"]).sort_values("t").reset_index(drop=True)

# ── build the continuous $10k account (3% risk compounding) ──
eq = START; eqs = []
for r in d["r"]:
    eq *= (1 + r * RISK / 100.0)
    eqs.append(eq)
d["equity"] = eqs
d["pnl"]    = d["equity"].diff().fillna(d["equity"].iloc[0] - START)
d["week"]   = d["t"].dt.to_period("W").apply(lambda p: p.start_time.date())
d["month"]  = d["t"].dt.to_period("M").astype(str)

def grp(by):
    g = d.groupby(by).agg(
        trades=("r","size"),
        win_pct=("r", lambda x: round((x>0).mean()*100,1)),
        totalR=("r", lambda x: round(x.sum(),1)),
        pnl_usd=("pnl", lambda x: round(x.sum(),0)),
        equity_end=("equity", lambda x: round(x.iloc[-1],0)),
    )
    return g

wk = grp("week"); mo = grp("month")

def summary():
    n=len(d); win=(d.r>0).mean()*100
    gp=d.r[d.r>0].sum(); gl=-d.r[d.r<0].sum(); pf=gp/gl if gl>0 else 99
    peak=d["equity"].cummax(); dd=((peak-d["equity"])/peak*100).max()
    print("="*72)
    print(f"  WFO OUT-OF-SAMPLE — $ {START:,.0f} account | {RISK}% risk/trade")
    print("="*72)
    print(f"  period      : {d['t'].min().date()}  ->  {d['t'].max().date()}")
    print(f"  trades      : {n}")
    print(f"  win rate    : {win:.1f}%")
    print(f"  total R     : {d.r.sum():+.1f}   avg R {d.r.mean():+.3f}")
    print(f"  profit factor: {pf:.2f}")
    print(f"  end equity  : ${d['equity'].iloc[-1]:,.0f}   (return {(d['equity'].iloc[-1]/START-1)*100:+,.0f}%)")
    print(f"  max drawdown: {dd:.1f}%")
    pw=(wk.totalR>0).sum(); nw=(wk.totalR<0).sum()
    pm=(mo.totalR>0).sum(); nm=(mo.totalR<0).sum()
    print(f"  weeks +/-   : {pw} positive / {nw} negative   ({pw/max(1,pw+nw)*100:.0f}% green)")
    print(f"  months +/-  : {pm} positive / {nm} negative")

summary()
print("\n"+"="*72+"\n  MONTHLY\n"+"="*72)
print(mo.to_string())
print("\n"+"="*72+"\n  WEEKLY\n"+"="*72)
print(wk.to_string())

wk.to_csv(_os.path.join(OUTDIR,"WFO_WEEKLY.csv")); mo.to_csv(_os.path.join(OUTDIR,"WFO_MONTHLY.csv"))
d[["t","direction","entry_price","exit_price","r","pnl","equity","exit_reason"]].to_csv(_os.path.join(OUTDIR,"WFO_ACCOUNT_10k.csv"), index=False)
print(f"\nSaved: WFO_WEEKLY.csv | WFO_MONTHLY.csv | WFO_ACCOUNT_10k.csv  (in {OUTDIR})")
print(f"Tip: change RISK at the top of this script to 1 or 2 to see a safer account curve.")
