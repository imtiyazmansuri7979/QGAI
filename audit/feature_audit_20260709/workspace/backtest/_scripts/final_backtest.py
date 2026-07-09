"""
FINAL backtest — CURRENT (M15 line + ~1.5R TP) vs PROPOSED (H1 line/flip + far TP).
Entry: 15-min flip, H1-aligned. Includes spread/slippage cost + max drawdown.
No-lookahead. NOTE: entries = M15 flips (proxy for the ML signal), so absolute
numbers are illustrative; the CURRENT-vs-PROPOSED *comparison* is the takeaway.
"""
import sys, pandas as pd, numpy as np
sys.path.insert(0,"C:/QGAI/engine")
from trend_signal import compute_trend
OHLC="C:/QGAI/data/merged/ohlc_merged.csv"
P,M,BUF=2,"SMMA",0.09
RISK_PCT=3.0           # % equity risked per trade (live setting)
COST_USD=0.50          # round-trip spread+slippage in $ (gold), per trade

m=pd.read_csv(OHLC); m["time"]=pd.to_datetime(m["time"])
m=m[["time","open","high","low","close"]].dropna().reset_index(drop=True)
m15=compute_trend(m.copy(),P,M)
h=(m.set_index("time").resample("1h").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna().reset_index())
h1=compute_trend(h.copy(),P,M); h1["valid_from"]=h1["time"]+pd.Timedelta(hours=1)
j=pd.merge_asof(m15[["time"]],h1[["valid_from","trend","buy_line","sell_line"]],left_on="time",right_on="valid_from",direction="backward")
H=m["high"].values;L=m["low"].values;C=m["close"].values;n=len(m)
mb=m15["buy_line"].values; ms=m15["sell_line"].values; mflip=m15["flip"].values
hb=j["buy_line"].values; hs=j["sell_line"].values; htr=j["trend"].values

def run(mode, tp_R):
    buy,sell = (mb,ms) if mode=="CURRENT" else (hb,hs)
    R=[]; i=1
    while i<n-1:
        d=1 if mflip[i]>0 else(-1 if mflip[i]<0 else 0)
        if d==0: i+=1; continue
        if np.isnan(htr[i]) or int(htr[i])!=d: i+=1; continue   # H1-aligned entries
        entry=C[i]; buf=entry*BUF/100.0; line=buy[i] if d>0 else sell[i]
        if np.isnan(line): i+=1; continue
        stop=line-d*buf; sl=(entry-stop)*d
        if sl<=0: i+=1; continue
        tp=entry+d*sl*tp_R if tp_R else None
        k=i+1; ex=None
        while k<n:
            if d>0 and L[k]<=stop: ex=stop; break
            if d<0 and H[k]>=stop: ex=stop; break
            if tp is not None and ((d>0 and H[k]>=tp) or (d<0 and L[k]<=tp)): ex=tp; break
            if mode=="CURRENT":
                opp=(mflip[k]<0 if d>0 else mflip[k]>0)
            else:
                opp=(not np.isnan(htr[k]) and int(htr[k])==-d)
            if opp: ex=C[k]; break
            nl=buy[k] if d>0 else sell[k]
            if not np.isnan(nl):
                ns=nl-d*buf; stop=max(stop,ns) if d>0 else min(stop,ns)
            k+=1
        if ex is None: ex=C[n-1]; k=n-1
        r=(ex-entry)*d/sl - COST_USD/sl          # subtract cost in R
        R.append(r); i=k+1
    return np.array(R)

def report(name,R):
    if len(R)==0: print(f"{name}: no trades"); return
    win=(R>0).mean()*100; gp=R[R>0].sum(); gl=-R[R<0].sum(); pf=gp/gl if gl>0 else 99
    mc=c=0
    for r in R: c=c+1 if r<0 else 0; mc=max(mc,c)
    # $ equity (compounding, risk_pct per trade) + max drawdown %
    eq=10000.0; peak=eq; dd=0.0
    for r in R:
        eq*= (1+ r*RISK_PCT/100.0); peak=max(peak,eq); dd=max(dd,(peak-eq)/peak*100)
    ret=(eq/10000-1)*100
    print(f"{name:9}| trades={len(R):4d} win={win:4.1f}% avgR={R.mean():+.3f} totalR={R.sum():+7.1f} "
          f"PF={pf:4.2f} maxConsecLoss={mc:2d} | $10k→${eq:,.0f} ({ret:+.0f}%) maxDD={dd:.1f}%")

print("="*104)
print(f"FINAL BACKTEST | H1-aligned 15-min entries | cost ${COST_USD}/trade | risk {RISK_PCT}%/trade | 2022-2026")
print("="*104)
report("CURRENT",  run("CURRENT", 1.5))    # M15 line + ~1.5R TP (≈ live 1% cap)
report("PROPOSED", run("PROPOSED", None))   # H1 line/flip + no TP (flip exits)
report("PROP 5R",  run("PROPOSED", 5.0))    # H1 + far 5R TP (caps tail risk)
