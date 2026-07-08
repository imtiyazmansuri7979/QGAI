"""Analyze the REAL ML-model backtest trade log (logs/trades_tp_1.00.csv).
Win rate, avg R, PF, equity, max drawdown, and breakdown by exit_reason / direction /
hmm_state. Also verifies the realistic compounded return vs the headline number."""
import sys, io, pandas as pd, numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CSV = r"C:\QGAI\engine\logs\trades_tp_1.00.csv"   # change TP here if needed
d = pd.read_csv(CSV)
d["pnl_usd"]   = pd.to_numeric(d["pnl_usd"], errors="coerce")
d["r_achieved"]= pd.to_numeric(d["r_achieved"], errors="coerce")
d = d.dropna(subset=["pnl_usd","r_achieved"]).reset_index(drop=True)
n = len(d)

def block(title): print("\n"+"="*70+"\n  "+title+"\n"+"="*70)

block(f"OVERALL  ({CSV.split(chr(92))[-1]})")
wins = d["r_achieved"]>0
wr = wins.mean()*100
gp = d.loc[d.r_achieved>0,"r_achieved"].sum(); gl = -d.loc[d.r_achieved<0,"r_achieved"].sum()
pf = gp/gl if gl>0 else float('inf')
print(f"  trades        : {n}")
print(f"  date range    : {d['entry_time'].iloc[0]}  ->  {d['exit_time'].iloc[-1]}")
print(f"  win rate      : {wr:.1f}%")
print(f"  avg R         : {d['r_achieved'].mean():+.3f}   (median {d['r_achieved'].median():+.3f})")
print(f"  total R       : {d['r_achieved'].sum():+.1f}")
print(f"  profit factor : {pf:.2f}")
print(f"  avg win R     : {d.loc[wins,'r_achieved'].mean():+.2f}   avg loss R: {d.loc[~wins,'r_achieved'].mean():+.2f}")

# Equity / drawdown — from the recorded equity_after if present, else cumulative pnl
block("EQUITY / DRAWDOWN")
if "equity_after" in d.columns and pd.to_numeric(d["equity_after"],errors="coerce").notna().any():
    eq = pd.to_numeric(d["equity_after"],errors="coerce").ffill()
    start = eq.iloc[0]-d["pnl_usd"].iloc[0]
else:
    start = 10000.0; eq = start + d["pnl_usd"].cumsum()
peak = eq.cummax(); dd = ((peak-eq)/peak*100)
print(f"  start equity  : ${start:,.0f}")
print(f"  end equity    : ${eq.iloc[-1]:,.0f}")
print(f"  total return  : {(eq.iloc[-1]/start-1)*100:,.0f}%   (<- sanity-check this vs headline)")
print(f"  max drawdown  : {dd.max():.1f}%")
print(f"  total pnl $   : ${d['pnl_usd'].sum():,.0f}")

block("BY EXIT REASON")
g = d.groupby("exit_reason").agg(trades=("r_achieved","size"), winR=("r_achieved",lambda x:(x>0).mean()*100),
                                 avgR=("r_achieved","mean"), totalR=("r_achieved","sum"), pnl=("pnl_usd","sum"))
print(g.round(2).sort_values("totalR",ascending=False).to_string())

block("BY DIRECTION")
g = d.groupby("direction").agg(trades=("r_achieved","size"), winR=("r_achieved",lambda x:(x>0).mean()*100),
                               avgR=("r_achieved","mean"), totalR=("r_achieved","sum"), pnl=("pnl_usd","sum"))
print(g.round(2).to_string())

if "hmm_state" in d.columns:
    block("BY HMM STATE")
    g = d.groupby("hmm_state").agg(trades=("r_achieved","size"), winR=("r_achieved",lambda x:(x>0).mean()*100),
                                   avgR=("r_achieved","mean"), totalR=("r_achieved","sum")).round(2)
    print(g.to_string())

block("NOTES")
print("  - 'total return %' is the headline; if it is astronomically high (e.g. +200,000%)")
print("    it is a COMPOUNDING artifact at high % risk, NOT realistic. Judge by PF / avg R / max DD.")
print("  - Compare exit reasons: how much R comes from TRAIL vs FLIP vs TP vs SL.")
