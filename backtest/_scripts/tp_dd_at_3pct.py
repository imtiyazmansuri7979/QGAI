"""Does adding a TP reduce drawdown at FIXED 3% risk? H1 exit, buf 0.20, cost $0.30,
H1+H4 aligned. For each TP level: return + maxDD + Monte-Carlo P(DD>50%) at 3% risk."""
import sys, io, pandas as pd, numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0,"C:/QGAI/engine")
from trend_signal import compute_trend
OHLC="C:/QGAI/data/merged/ohlc_merged.csv"
P,M,BUF,COST,MINSL,RISK=2,"SMMA",0.20,0.30,0.18,3.0
N_SIM=3000; np.random.seed(42)
m=pd.read_csv(OHLC); m["time"]=pd.to_datetime(m["time"])
m=m[["time","open","high","low","close"]].dropna().reset_index(drop=True)
m15=compute_trend(m.copy(),P,M)
def htf(freq,mins):
    h=(m.set_index("time").resample(freq).agg({"open":"first","high":"max","low":"min","close":"last"}).dropna().reset_index())
    t=compute_trend(h.copy(),P,M); t["valid_from"]=t["time"]+pd.Timedelta(minutes=mins)
    j=pd.merge_asof(m15[["time"]],t[["valid_from","trend","buy_line","sell_line"]],left_on="time",right_on="valid_from",direction="backward")
    return j["buy_line"].values,j["sell_line"].values,j["trend"].values
H=m["high"].values;L=m["low"].values;C=m["close"].values;n=len(m); mflip=m15["flip"].values
b1,s1,t1=htf("1h",60); _,_,t4=htf("4h",240)
def run(tp_R):
    R=[]; i=1
    while i<n-1:
        d=1 if mflip[i]>0 else(-1 if mflip[i]<0 else 0)
        if d==0: i+=1; continue
        if any(np.isnan(x[i]) or int(x[i])!=d for x in (t1,t4)): i+=1; continue
        entry=C[i]; buf=entry*BUF/100.0; line=b1[i] if d>0 else s1[i]
        if np.isnan(line): i+=1; continue
        stop=line-d*buf; sl=(entry-stop)*d
        if sl < entry*MINSL/100.0: i+=1; continue
        tp=entry+d*sl*tp_R if tp_R else None
        k=i+1; ex=None
        while k<n:
            if d>0 and L[k]<=stop: ex=stop; break
            if d<0 and H[k]>=stop: ex=stop; break
            if tp is not None and ((d>0 and H[k]>=tp) or (d<0 and L[k]<=tp)): ex=tp; break
            if not np.isnan(t1[k]) and int(t1[k])==-d: ex=C[k]; break
            nl=b1[k] if d>0 else s1[k]
            if not np.isnan(nl):
                ns=nl-d*buf; stop=max(stop,ns) if d>0 else min(stop,ns)
            k+=1
        if ex is None: ex=C[n-1]; k=n-1
        R.append((ex-entry)*d/sl - COST/sl); i=k+1
    return np.array(R)
def metrics(R):
    win=(R>0).mean()*100; gp=R[R>0].sum(); gl=-R[R<0].sum(); pf=gp/gl if gl>0 else 99
    eq=10000.0;peak=eq;dd=0
    for r in R: eq*=(1+r*RISK/100); peak=max(peak,eq); dd=max(dd,(peak-eq)/peak*100)
    # Monte-Carlo P(DD>50%) at 3% risk
    nt=len(R); idx=np.random.randint(0,nt,size=(N_SIM,nt)); Rs=R[idx]
    g=np.clip(1+Rs*RISK/100,1e-6,None); e=np.cumprod(g,axis=1)
    pk=np.maximum.accumulate(e,axis=1); mdd=((pk-e)/pk).max(axis=1)*100
    return len(R),win,R.mean(),R.sum(),pf,eq,dd,(mdd>50).mean()*100
print("="*96)
print(f"ADD-TP @ FIXED {RISK}% RISK | H1 exit, buf {BUF}, cost ${COST}, H1+H4 aligned | 2022-2026")
print("="*96)
print(f"{'TP':>6}{'trades':>8}{'win%':>7}{'avgR':>8}{'totalR':>8}{'PF':>6}{'$10k->':>11}{'maxDD':>8}{'MC P(DD>50%)':>14}")
for tp in [None,5.0,3.0,2.0,1.5]:
    nt,win,av,tot,pf,eq,dd,pdd=metrics(run(tp))
    lbl="none" if tp is None else f"{tp:.1f}R"
    print(f"{lbl:>6}{nt:8d}{win:7.1f}{av:+8.3f}{tot:+8.1f}{pf:6.2f}{eq:>11,.0f}{dd:>7.0f}%{pdd:>13.0f}%")
print("\nQuestion answered: does a TP cut drawdown at 3% risk? Compare maxDD & MC P(DD>50%) vs 'none'.")
print("If DD barely drops but return falls a lot -> TP is not worth it (lower risk is the real DD fix).")
