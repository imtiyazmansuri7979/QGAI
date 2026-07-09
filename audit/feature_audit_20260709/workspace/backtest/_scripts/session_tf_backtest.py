"""Session x timeframe check: which exit-TF (M15/M30/H1) is best per session?
Sessions by BROKER hour: ASIAN 0-6 | LONDON 7-12 | NY 13-23. Same M15-flip entries."""
import sys, pandas as pd, numpy as np
sys.path.insert(0,"C:/QGAI/engine")
from trend_signal import compute_trend
OHLC="C:/QGAI/data/merged/ohlc_merged.csv"
P,M,BUF=2,"SMMA",0.09
m=pd.read_csv(OHLC); m["time"]=pd.to_datetime(m["time"])
m=m[["time","open","high","low","close"]].dropna().reset_index(drop=True)
m15=compute_trend(m.copy(),P,M)
def htf(freq,mins):
    h=(m.set_index("time").resample(freq).agg({"open":"first","high":"max","low":"min","close":"last"}).dropna().reset_index())
    t=compute_trend(h.copy(),P,M); t["valid_from"]=t["time"]+pd.Timedelta(minutes=mins)
    j=pd.merge_asof(m15[["time"]],t[["valid_from","trend","buy_line","sell_line"]],left_on="time",right_on="valid_from",direction="backward")
    return j["buy_line"].values,j["sell_line"].values,j["trend"].values
H=m["high"].values;L=m["low"].values;C=m["close"].values;n=len(m); hours=m["time"].dt.hour.values
LINES={"M15":(m15["buy_line"].values,m15["sell_line"].values,None,m15["flip"].values)}
b,s,t=htf("30min",30); LINES["M30"]=(b,s,t,None)
b,s,t=htf("1h",60);    LINES["H1"]=(b,s,t,None)
def sess(h): return "ASIAN" if h<=6 else ("LONDON" if h<=12 else "NY")
def run(mode):
    buy,sell,tr,flip=LINES[mode]; mflip=m15["flip"].values; out=[]; i=1
    while i<n-1:
        d=1 if mflip[i]>0 else(-1 if mflip[i]<0 else 0)
        if d==0: i+=1; continue
        entry=C[i]; buf=entry*BUF/100.0; line=buy[i] if d>0 else sell[i]
        if np.isnan(line): i+=1; continue
        stop=line-d*buf; sl=(entry-stop)*d
        if sl<=0: i+=1; continue
        eh=hours[i]; j=i+1; ex=None
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
        out.append((sess(eh),(ex-entry)*d/sl)); i=j+1
    return out
res={mode:run(mode) for mode in ["M15","M30","H1"]}
def agg(rows):
    R=np.array([r for _,r in rows])
    if len(R)==0: return (0,0,0,0,0)
    win=(R>0).mean()*100; tiny=int(((R<0)&(R>-0.5)).sum())
    return (len(R),win,R.mean(),R.sum(),tiny)
print("="*92); print("SESSION x EXIT-TF  (ASIAN 0-6 | LONDON 7-12 | NY 13-23, broker hour)"); print("="*92)
print(f"{'session':8}{'TF':5}{'trades':>8}{'win%':>7}{'avgR':>8}{'totalR':>9}{'whip':>6}")
best={}
for S in ["ASIAN","LONDON","NY"]:
    rowbest=None
    for mode in ["M15","M30","H1"]:
        sub=[(x,r) for (x,r) in res[mode] if x==S]; tr,win,av,tot,ti=agg(sub)
        print(f"{S:8}{mode:5}{tr:8d}{win:7.1f}{av:+8.3f}{tot:+9.1f}{ti:6d}")
        if rowbest is None or av>rowbest[1]: rowbest=(mode,av,tot)
    best[S]=rowbest; print("-"*46)
print("\nBEST exit-TF per session (by avgR):")
hyb=0
for S in ["ASIAN","LONDON","NY"]:
    mode,av,tot=best[S]; hyb+=tot; print(f"  {S:8} → {mode:3} (avgR {av:+.3f}, totalR {tot:+.1f})")
# compare hybrid total vs all-H1 / all-M30
allH1=sum(agg([(x,r) for x,r in res['H1'] if x==S])[3] for S in ['ASIAN','LONDON','NY'])
allM30=sum(agg([(x,r) for x,r in res['M30'] if x==S])[3] for S in ['ASIAN','LONDON','NY'])
allM15=sum(agg([(x,r) for x,r in res['M15'] if x==S])[3] for S in ['ASIAN','LONDON','NY'])
print(f"\nTOTAL R — all-M15:{allM15:+.1f} | all-M30:{allM30:+.1f} | all-H1:{allH1:+.1f} | SESSION-HYBRID:{hyb:+.1f}")
