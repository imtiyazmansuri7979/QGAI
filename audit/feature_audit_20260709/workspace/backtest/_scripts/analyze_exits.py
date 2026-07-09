"""Exit-reason breakdown of the OOS trades — especially TRAIL.
Usage: python analyze_exits.py [folder]   (default wfo_results)"""
import sys, io, os, pandas as pd, numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
_dir = sys.argv[1] if len(sys.argv) > 1 else "wfo_results"
CSV = os.path.join(_dir if os.path.isabs(_dir) else rf"C:\QGAI\engine\{_dir}", "ALL_OOS_trades.csv")
d = pd.read_csv(CSV)
d["r"] = pd.to_numeric(d["r_achieved"], errors="coerce"); d = d.dropna(subset=["r"])
print("="*78)
print(f"EXIT-REASON BREAKDOWN  ({len(d)} OOS trades)  |  {CSV}")
print("="*78)
g = d.groupby("exit_reason").agg(
        trades=("r","size"),
        win_pct=("r", lambda x: round((x>0).mean()*100,1)),
        avgR=("r","mean"), totalR=("r","sum"),
        minR=("r","min"), maxR=("r","max")).round(3)
g["share_pct"] = (g["trades"]/len(d)*100).round(0)
print(g.sort_values("totalR", ascending=False).to_string())

t = d[d.exit_reason == "TRAIL"]
if len(t):
    print("\n" + "-"*60)
    print(f"TRAIL deep-dive  ({len(t)} trades, {len(t)/len(d)*100:.0f}% of all)")
    print("-"*60)
    print(f"  win rate   : {(t.r>0).mean()*100:.1f}%")
    print(f"  avg R      : {t.r.mean():+.3f}   total {t.r.sum():+.1f}R")
    print(f"  best/worst : {t.r.max():+.2f}R / {t.r.min():+.2f}R")
    print(f"  R buckets:")
    print(f"     win > +0.5R     : {int((t.r>0.5).sum()):4d}")
    print(f"     small win 0..0.5: {int(((t.r>0)&(t.r<=0.5)).sum()):4d}")
    print(f"     small loss -0.5..0: {int(((t.r<0)&(t.r>=-0.5)).sum()):4d}")
    print(f"     loss < -0.5R    : {int((t.r<-0.5).sum()):4d}")
    print("\n  -> TRAIL should mostly be small wins / break-even (stop trailed up).")
    print("     If TRAIL avg R is negative, the trail may be too tight (exiting too early).")
