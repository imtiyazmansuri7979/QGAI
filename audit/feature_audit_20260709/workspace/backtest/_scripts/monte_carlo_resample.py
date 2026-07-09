"""
Monte-Carlo RESAMPLE — H1-exit strategy (live config: buf 0.20, cost $0.30,
M30+H1+H4-aligned 15-min entries, min-SL 0.18%). Bootstraps the trade sequence
5000x to show the RANGE of outcomes (return + max drawdown percentiles + ruin
probability) at risk 1/2/3/5%. Far more honest about risk than one backtest path.
"""
import sys, pandas as pd, numpy as np
sys.path.insert(0,"C:/QGAI/engine")
from trend_signal import compute_trend
OHLC="C:/QGAI/data/merged/ohlc_merged.csv"
P,M,BUF,COST,MINSL=2,"SMMA",0.20,0.30,0.18
N_SIM=5000
np.random.seed(42)

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
R=np.array(R); nt=len(R)
print("="*84)
print(f"MONTE-CARLO RESAMPLE | {N_SIM} sims | H1 exit, buf {BUF}, cost ${COST}, aligned")
print(f"base trades={nt} | win={ (R>0).mean()*100:.1f}% | avgR={R.mean():+.3f} | totalR={R.sum():+.1f}")
print("="*84)
print(f"{'risk':>5}{'ret p5':>9}{'ret p50':>9}{'ret p95':>9}{'DD p50':>8}{'DD p95':>8}{'P(DD>50%)':>11}{'P(ruin)':>9}")
for risk in [1,2,3,5]:
    idx=np.random.randint(0,nt,size=(N_SIM,nt))           # bootstrap trade order (with replacement)
    Rs=R[idx]                                              # (N_SIM, nt)
    growth=1.0+Rs*risk/100.0
    growth=np.clip(growth,1e-6,None)                       # avoid <=0 blowups
    eq=np.cumprod(growth,axis=1)
    peak=np.maximum.accumulate(eq,axis=1)
    dd=((peak-eq)/peak).max(axis=1)*100                    # max DD % per sim
    ret=(eq[:,-1]-1)*100                                   # final return % per sim
    pruin=(eq.min(axis=1)<=0.10).mean()*100                # equity ever < 10% of start
    print(f"{risk:>4}%{np.percentile(ret,5):>+9.0f}{np.percentile(ret,50):>+9.0f}{np.percentile(ret,95):>+9.0f}"
          f"{np.percentile(dd,50):>7.0f}%{np.percentile(dd,95):>7.0f}%{(dd>50).mean()*100:>10.0f}%{pruin:>8.0f}%")
print("\nret p5/p50/p95 = 5th/median/95th percentile final return over the period.")
print("DD p50/p95 = median / worst-5% max drawdown.  P(ruin)=chance equity ever fell below 10% of start.")
print("Takeaway: lower risk = much tighter, safer distribution. Watch P(DD>50%) and the p5 (bad-luck) return.")
