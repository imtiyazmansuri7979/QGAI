import pandas as pd, numpy as np
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent   # QGAI root (engine/..)
OHLC = BASE/"data"/"merged"/"ohlc_merged.csv"
TRADES = BASE/"engine"/"logs"/"backtest_trades.csv"
HORIZON=48; TIME_EXIT=12; RSI_LEN=14; VOL_LEN=20; STRUCT_N=6

def rsi(c,n=RSI_LEN):
    d=c.diff(); up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+up/(dn+1e-9))
def prep(df):
    df=df.copy(); df["rsi"]=rsi(df["close"])
    df["vol_ma"]=df["tick_volume"].rolling(VOL_LEN,min_periods=5).mean()
    df["body"]=(df["close"]-df["open"]).abs(); df["body_ma"]=df["body"].rolling(VOL_LEN,min_periods=5).mean()
    df["sup"]=df["low"].rolling(STRUCT_N,min_periods=2).min(); df["res"]=df["high"].rolling(STRUCT_N,min_periods=2).max()
    return df
ohlc=prep(pd.read_csv(OHLC,parse_dates=["time"]).sort_values("time").reset_index(drop=True))
tr=pd.read_csv(TRADES,parse_dates=["entry_time"])
for c in ["entry_price","sl_dist","r_achieved","peak_r"]: tr[c]=pd.to_numeric(tr[c],errors="coerce")
tr=tr.dropna(subset=["entry_price","sl_dist","r_achieved"]).reset_index(drop=True)
def fwd(et):
    idx=ohlc.index[ohlc["time"]>=et]
    return None if len(idx)==0 else ohlc.iloc[idx[0]:idx[0]+HORIZON+1].reset_index(drop=True)
def r_of(p,t): s=1 if t.direction=="BUY" else -1; return s*(p-t.entry_price)/t.sl_dist
def hit_sl(b,t,sl): return (t.direction=="BUY" and b.low<=sl) or (t.direction=="SELL" and b.high>=sl)
def sl0(t): return t.entry_price-(t.sl_dist if t.direction=="BUY" else -t.sl_dist)

def m_time(w,t):
    sl=sl0(t)
    for k in range(1,len(w)):
        b=w.iloc[k]
        if hit_sl(b,t,sl): return -1.0
        if k>=TIME_EXIT: return r_of(b.close,t)
    return r_of(w.iloc[-1].close,t)
def m_mom(w,t):
    sl=sl0(t)
    for k in range(1,len(w)):
        b=w.iloc[k]
        if hit_sl(b,t,sl): return -1.0
        rr=r_of(b.close,t)
        if rr>0:
            wr=(b.rsi<50) if t.direction=="BUY" else (b.rsi>50)
            vd=b.tick_volume<0.7*(b.vol_ma if b.vol_ma==b.vol_ma else b.tick_volume)
            oc=((b.close<b.open) if t.direction=="BUY" else (b.close>b.open)) and (b.body>(b.body_ma or 0))
            if wr or vd or oc: return rr
    return r_of(w.iloc[-1].close,t)
def m_struct(w,t):
    sl=sl0(t)
    for k in range(1,len(w)):
        b=w.iloc[k]
        if hit_sl(b,t,sl): return -1.0
        if t.direction=="BUY" and b.close<b.sup: return r_of(b.close,t)
        if t.direction=="SELL" and b.close>b.res: return r_of(b.close,t)
    return r_of(w.iloc[-1].close,t)
def m_full(w,t):
    sl=sl0(t); half=None
    for k in range(1,len(w)):
        b=w.iloc[k]
        if hit_sl(b,t,sl): return -1.0 if half is None else half+0.5*-1.0
        rr=r_of(b.close,t)
        if half is None and rr>=1.0: half=0.5; sl=t.entry_price
        wr=(b.rsi<50) if t.direction=="BUY" else (b.rsi>50)
        vd=b.tick_volume<0.7*(b.vol_ma if b.vol_ma==b.vol_ma else b.tick_volume)
        sb=(b.close<b.sup) if t.direction=="BUY" else (b.close>b.res)
        if (rr>0 and (wr or vd)) or sb or k>=TIME_EXIT:
            return rr if half is None else half+0.5*rr
    rr=r_of(w.iloc[-1].close,t); return rr if half is None else half+0.5*rr

METH={"Ratchet(live)":None,"Time-only":m_time,"Momentum":m_mom,"Structure":m_struct,"FULL engine":m_full}
rows={m:[] for m in METH}; reg=[]
for _,t in tr.iterrows():
    w=fwd(t.entry_time)
    if w is None or len(w)<3: continue
    reg.append(t.get("hmm_state",""))
    for m,fn in METH.items(): rows[m].append(t.r_achieved if fn is None else fn(w,t))
res=pd.DataFrame(rows); res["regime"]=reg
print("Trades simulated:",len(res),"\n")
print(f"{'Method':<16}{'TotalR':>9}{'AvgR':>8}{'WinRate':>9}"); print("-"*42)
for m in METH:
    s=res[m]; print(f"{m:<16}{s.sum():>8.1f}R{s.mean():>8.3f}{(s>0).mean()*100:>8.0f}%")
print("\nBy regime (Total R):")
print(f"{'regime':<11}"+"".join(f"{m[:11]:>13}" for m in METH))
for r,g in res.groupby("regime"):
    print(f"{r:<11}"+"".join(f"{g[m].sum():>12.1f}R" for m in METH))

# ===== Higher-timeframe STRUCTURE / FLIP exit (M30, H1) =====
def tf_levels(o, rule):
    g=o.set_index("time").resample(rule).agg({"high":"max","low":"min"}).dropna()
    sup=g["low"].rolling(STRUCT_N,min_periods=2).min().shift(1)
    res=g["high"].rolling(STRUCT_N,min_periods=2).max().shift(1)
    return pd.DataFrame({"time":g.index,"sup":sup.values,"res":res.values}).dropna()
for rule,tag in [("30min","m30"),("1h","h1")]:
    lv=tf_levels(ohlc,rule)
    m=pd.merge_asof(ohlc[["time"]].sort_values("time"),lv.sort_values("time"),on="time",direction="backward")
    ohlc[f"sup_{tag}"]=m["sup"].values; ohlc[f"res_{tag}"]=m["res"].values

def make_tf_struct(tag):
    def f(w,t):
        sl=sl0(t)
        for k in range(1,len(w)):
            b=w.iloc[k]
            if hit_sl(b,t,sl): return -1.0
            sup=getattr(b,f"sup_{tag}"); res=getattr(b,f"res_{tag}")
            if t.direction=="BUY" and sup==sup and b.close<sup: return r_of(b.close,t)
            if t.direction=="SELL" and res==res and b.close>res: return r_of(b.close,t)
        return r_of(w.iloc[-1].close,t)
    return f

TF={"Struct M15":m_struct,"Struct M30":make_tf_struct("m30"),"Struct H1":make_tf_struct("h1")}
out={k:[] for k in TF}; rg=[]
for _,t in tr.iterrows():
    w=fwd(t.entry_time)
    if w is None or len(w)<3: continue
    rg.append(t.get("hmm_state",""))
    for k,fn in TF.items(): out[k].append(fn(w,t))
r2=pd.DataFrame(out); r2["regime"]=rg; r2["Ratchet"]=res["Ratchet(live)"].values
print("\n\n===== FLIP/STRUCTURE EXIT by TIMEFRAME =====")
print(f"{'Method':<13}{'TotalR':>9}{'AvgR':>8}{'WinRate':>9}"); print("-"*39)
for k in ["Ratchet","Struct M15","Struct M30","Struct H1"]:
    s=r2[k]; print(f"{k:<13}{s.sum():>8.1f}R{s.mean():>8.3f}{(s>0).mean()*100:>8.0f}%")
print("\nBy regime (Total R):")
cols=["Ratchet","Struct M15","Struct M30","Struct H1"]
print(f"{'regime':<11}"+"".join(f"{c:>12}" for c in cols))
for r,g in r2.groupby("regime"):
    print(f"{r:<11}"+"".join(f"{g[c].sum():>11.1f}R" for c in cols))

# Regime hybrid: H1-structure in Ranging, Ratchet otherwise
hyb=[]
for i,r in r2.iterrows():
    hyb.append(r["Struct H1"] if r["regime"]=="Ranging" else r["Ratchet"])
hyb=np.array(hyb)
print("\n===== REGIME HYBRID (H1-structure in Ranging, Ratchet in Trending/Volatile) =====")
print(f"  Total: {hyb.sum():+.1f}R | Avg {hyb.mean():+.3f}R | WinRate {(hyb>0).mean()*100:.0f}%")
print(f"  (vs Ratchet +16.0R, vs H1-struct +20.4R)")
