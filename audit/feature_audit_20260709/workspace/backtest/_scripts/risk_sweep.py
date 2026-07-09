"""Risk-per-trade sweep (1-5%) on the LIVE config: H1 exit, buffer 0.20, cost $0.30,
M30+H1+H4-aligned entries, min-SL 0.18% (live filter). Shows $ return + max drawdown.
Run on Windows:  cd C:\\QGAI\\backtest  &&  python risk_sweep.py"""
import sys, pandas as pd, numpy as np
sys.path.insert(0,"C:/QGAI/engine")
from trend_signal import compute_trend
OHLC="C:/QGAI/data/merged/ohlc_merged.csv"
P,M,BUF,COST,MINSL=2,"SMMA",0.20,0.30,0.18
m=pd.read_csv(OHLC); m["time"]=pd.to_datetime(m["time"])
m=m[["time","open","high","low","close"]].dropna().reset_index(drop=True)
m15=compute_trend(m.copy(),P,M)
def htf(freq,mins):
    h=(m.set_index("time").resample(freq).agg({"open":"first","high":"max","low":"min","close":"last"}).dropna().reset_index())
    t=compute_trend(h.copy(),P,M); t["valid_from"]=t["time"]+pd.Timedelta(minutes=mins)
    j=pd.merge_asof(m15[["time"]],t[["valid_from","trend","buy_line","sell_line"]],left_on="time",right_on="valid_from",direction="backward")
    return j["buy_line"].values,j["sell_line"].values,j["trend"].values
H=m["high"].values;L=m["low"].values;C=m["close"].values;n=len(m); mflip=m15["flip"].values
b1,s1,t1=htf("1h",60); _,_,t30=htf("30min",30); _,_,t4=htf("4h",240)
R=[]; i=1
while i<n-1:
    d=1 if mflip[i]>0 else(-1 if mflip[i]<0 else 0)
    if d==0: i+=1; continue
    if any(np.isnan(x[i]) or int(x[i])!=d for x in (t1,t4)): i+=1; continue   # H1+H4 aligned (M30 dropped)
    entry=C[i]; buf=entry*BUF/100.0; line=b1[i] if d>0 else s1[i]
    if np.isnan(line): i+=1; continue
    stop=line-d*buf; sl=(entry-stop)*d
    if sl < entry*MINSL/100.0: i+=1; continue
    k=i+1; ex=None
    while k<n:
        if d>0 and L[k]<=stop: ex=stop; break
        if d<0 and H[k]>=stop: ex=stop; break
        if not np.isnan(t1[k]) and int(t1[k])==-d: ex=C[k]; break
        nl=b1[k] if d>0 else s1[k]
        if not np.isnan(nl):
            ns=nl-d*buf; stop=max(stop,ns) if d>0 else min(stop,ns)
        k+=1
    if ex is None: ex=C[n-1]; k=n-1
    R.append((ex-entry)*d/sl - COST/sl); i=k+1
R=np.array(R)
win=(R>0).mean()*100; gp=R[R>0].sum(); gl=-R[R<0].sum(); pf=gp/gl if gl>0 else 99
mc=c=0
for r in R: c=c+1 if r<0 else 0; mc=max(mc,c)
print("="*78)
print(f"RISK SWEEP | H1 exit, buf {BUF}, cost ${COST}, aligned, min-SL {MINSL}% | 2022-2026")
print(f"trades={len(R)} | win={win:.1f}% | avgR={R.mean():+.3f} | totalR={R.sum():+.1f} | PF={pf:.2f} | maxConsecLoss={mc}")
print("="*78)
print(f"{'risk/trade':>11}{'$10k -> ':>14}{'return%':>10}{'maxDD%':>9}")
for risk in [1,2,3,4,5]:
    eq=10000.0; peak=eq; dd=0
    for r in R:
        eq*=(1+r*risk/100.0)
        if eq<=0: eq=0; break
        peak=max(peak,eq); dd=max(dd,(peak-eq)/peak*100)
    print(f"{risk:>9}%  {eq:>13,.0f}{(eq/10000-1)*100:>+10.0f}{dd:>8.0f}%")
print("\nNote: avgR/PF/win% identical at every risk - only $ growth & drawdown change.")
