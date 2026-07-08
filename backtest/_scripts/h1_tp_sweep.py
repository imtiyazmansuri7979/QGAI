"""H1 stop/flip exit + TP-cap sweep. Does a far TP (or none) beat a tight TP?"""
import sys, pandas as pd, numpy as np
sys.path.insert(0,"C:/QGAI/engine")
from trend_signal import compute_trend
OHLC="C:/QGAI/data/merged/ohlc_merged.csv"
P,M,BUF=2,"SMMA",0.09
m=pd.read_csv(OHLC); m["time"]=pd.to_datetime(m["time"])
m=m[["time","open","high","low","close"]].dropna().reset_index(drop=True)
m15=compute_trend(m.copy(),P,M)
h=(m.set_index("time").resample("1h").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna().reset_index())
h1=compute_trend(h.copy(),P,M); h1["valid_from"]=h1["time"]+pd.Timedelta(hours=1)
j=pd.merge_asof(m15[["time"]],h1[["valid_from","trend","buy_line","sell_line"]],left_on="time",right_on="valid_from",direction="backward")
H=m["high"].values;L=m["low"].values;C=m["close"].values;n=len(m)
buy=j["buy_line"].values; sell=j["sell_line"].values; tr=j["trend"].values; mflip=m15["flip"].values

def run(tp_R):   # tp_R = TP distance in R (None = no TP)
    R=[]; i=1
    while i<n-1:
        d=1 if mflip[i]>0 else(-1 if mflip[i]<0 else 0)
        if d==0: i+=1; continue
        entry=C[i]; buf=entry*BUF/100.0; line=buy[i] if d>0 else sell[i]
        if np.isnan(line): i+=1; continue
        stop=line-d*buf; sl=(entry-stop)*d
        if sl<=0: i+=1; continue
        tp=entry+d*sl*tp_R if tp_R else None
        j2=i+1; ex=None
        while j2<n:
            if d>0 and L[j2]<=stop: ex=stop; break          # stop first (conservative)
            if d<0 and H[j2]>=stop: ex=stop; break
            if tp is not None:
                if d>0 and H[j2]>=tp: ex=tp; break
                if d<0 and L[j2]<=tp: ex=tp; break
            opp=(not np.isnan(tr[j2]) and int(tr[j2])==-d)
            if opp: ex=C[j2]; break
            nl=buy[j2] if d>0 else sell[j2]
            if not np.isnan(nl):
                ns=nl-d*buf; stop=max(stop,ns) if d>0 else min(stop,ns)
            j2+=1
        if ex is None: ex=C[n-1]; j2=n-1
        R.append((ex-entry)*d/sl); i=j2+1
    return np.array(R)

print("="*80); print("H1 stop/flip — TP-cap sweep (TP in R = multiples of initial risk)"); print("="*80)
print(f"{'TP':>6}{'trades':>8}{'win%':>7}{'avgR':>8}{'totalR':>9}{'PF':>6}{'avgWin':>8}{'avgLoss':>8}")
for tp in [1.0,1.5,2.0,3.0,5.0,None]:
    R=run(tp); win=(R>0).mean()*100; gp=R[R>0].sum(); gl=-R[R<0].sum(); pf=gp/gl if gl>0 else 99
    aw=R[R>0].mean() if (R>0).any() else 0; al=R[R<0].mean() if (R<0).any() else 0
    lbl=f"{tp:.1f}R" if tp else "none"
    print(f"{lbl:>6}{len(R):8d}{win:7.1f}{R.mean():+8.3f}{R.sum():+9.1f}{pf:6.2f}{aw:+8.2f}{al:+8.2f}")
