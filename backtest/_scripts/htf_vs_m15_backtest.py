"""Data check: M15 vs M30 vs H1 line as stop/flip. Same M15-flip entries. No-lookahead."""
import sys, pandas as pd, numpy as np
sys.path.insert(0, "C:/QGAI/engine")
from trend_signal import compute_trend

OHLC="C:/QGAI/data/merged/ohlc_merged.csv"
PERIOD, METHOD, BUF_PCT = 2, "SMMA", 0.09

m=pd.read_csv(OHLC); m["time"]=pd.to_datetime(m["time"])
m=m[["time","open","high","low","close"]].dropna().reset_index(drop=True)
m15=compute_trend(m.copy(),PERIOD,METHOD)

def htf(freq, mins):
    h=(m.set_index("time").resample(freq).agg({"open":"first","high":"max","low":"min","close":"last"}).dropna().reset_index())
    t=compute_trend(h.copy(),PERIOD,METHOD); t["valid_from"]=t["time"]+pd.Timedelta(minutes=mins)
    j=pd.merge_asof(m15[["time"]],t[["valid_from","trend","buy_line","sell_line"]],left_on="time",right_on="valid_from",direction="backward")
    return j["buy_line"].values, j["sell_line"].values, j["trend"].values

H=m["high"].values; L=m["low"].values; C=m["close"].values; T=m["time"].values; n=len(m)
LINES={"M15":(m15["buy_line"].values, m15["sell_line"].values, None, m15["flip"].values)}
b30,s30,t30=htf("30min",30); LINES["M30"]=(b30,s30,t30,None)
b1,s1,t1=htf("1h",60);       LINES["H1"]=(b1,s1,t1,None)
htr=t1  # HTF-aligned reference = H1 trend

def run(mode, aligned):
    buy,sell,tr,flip=LINES[mode]; mflip=m15["flip"].values; R=[]; i=1
    while i<n-1:
        d=1 if mflip[i]>0 else(-1 if mflip[i]<0 else 0)
        if d==0: i+=1; continue
        if aligned and (np.isnan(htr[i]) or int(htr[i])!=d): i+=1; continue
        entry=C[i]; buf=entry*BUF_PCT/100.0
        line=buy[i] if d>0 else sell[i]
        if np.isnan(line): i+=1; continue
        stop=line-d*buf; sl=(entry-stop)*d
        if sl<=0: i+=1; continue
        j=i+1; ex=None
        while j<n:
            if d>0 and L[j]<=stop: ex=stop; break
            if d<0 and H[j]>=stop: ex=stop; break
            nl=buy[j] if d>0 else sell[j]
            opp=(flip[j]<0 if d>0 else flip[j]>0) if tr is None else (not np.isnan(tr[j]) and int(tr[j])==-d)
            if opp: ex=C[j]; break
            if not np.isnan(nl):
                ns=nl-d*buf; stop=max(stop,ns) if d>0 else min(stop,ns)
            j+=1
        if ex is None: ex=C[n-1]; j=n-1
        R.append((ex-entry)*d/sl); i=j+1
    return np.array(R)

def stats(R):
    if len(R)==0: return "no trades"
    win=(R>0).mean()*100; gp=R[R>0].sum(); gl=-R[R<0].sum(); pf=gp/gl if gl>0 else 99.0
    mc=c=0
    for r in R: c=c+1 if r<0 else 0; mc=max(mc,c)
    tiny=int(((R<0)&(R>-0.5)).sum())
    return f"trades={len(R):4d} | win={win:5.1f}% | avgR={R.mean():+.3f} | totalR={R.sum():+7.1f} | PF={pf:4.2f} | maxConsecLoss={mc:2d} | tinyWhipsaws={tiny}"

print("="*96)
print(f"DATA CHECK — M15 vs M30 vs H1 stop/flip | same M15-flip entries | {str(T[0])[:10]}→{str(T[-1])[:10]} | {n:,} bars")
print("="*96)
for lbl,al in [("ALL M15-flip entries",False),("HTF-ALIGNED only (H1 agrees) = problem case",True)]:
    print(f"\n--- {lbl} ---")
    for mode in ["M15","M30","H1"]:
        print(f"  {mode:3} line stop/flip : {stats(run(mode,al))}")
