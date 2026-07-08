"""
analyze_capture.py — Capture-efficiency comparison of exit-rule variants.
Re-simulates the REAL BUY/SELL signals (signals_all.csv) forward on M15 OHLC
under 4 exit rules and reports Captured/Available move + R + PF + exit-mix.
Pure pandas — no model, no trading. Read-only diagnostic.

Variants:
  A baseline    — M15 line SL/trail + M15 flip            (current live)
  B htf         — H1 line SL/trail + H1 flip              (farther = anti-whipsaw)
  C flipconfirm — M15 line SL/trail, flip ONLY on a confirmed opposite
                  model signal (prob >= 0.45) — ignore noise flips
  D trendhold   — M15 line SL/trail + M15 flip, but once trade is +0.5R in
                  profit widen the buffer 3x (let winners run through pullbacks)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from pathlib import Path
from trend_signal import compute_trend
try:
    from config import CFG
    F = CFG.filters
    BUF   = float(getattr(F, "ratchet_buf_pct", 0.20))
    SLMIN = float(getattr(F, "ratchet_sl_min_pct", 0.18))
    TPCAP = float(getattr(F, "ratchet_tp_cap_pct", 10.0))
    LOGS  = Path(CFG.paths.logs_dir)
except Exception:
    BUF, SLMIN, TPCAP = 0.20, 0.18, 10.0
    LOGS = Path(__file__).resolve().parent / "logs"
ENGINE = Path(__file__).resolve().parent
OHLC_CSV = next((p for p in [ENGINE.parent/"data"/"merged"/"ohlc_merged.csv",
                             ENGINE/"ohlc_merged.csv"] if p.exists()), None)
CONF_PROB = 0.45   # flip-confirm threshold

def load_ohlc():
    df = pd.read_csv(OHLC_CSV)
    tcol = "time" if "time" in df.columns else df.columns[0]
    df = df.rename(columns={tcol:"time"}); df["time"]=pd.to_datetime(df["time"])
    return df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)[["time","open","high","low","close"]]

def htf_lines(ohlc):
    h1=(ohlc.set_index("time").resample("1h").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna().reset_index())
    h1t=compute_trend(h1,2,"SMMA",ratchet=True); h1t["vf"]=h1t["time"]+pd.Timedelta(hours=1)
    m=pd.merge_asof(ohlc[["time"]],h1t[["vf","buy_line","sell_line","flip"]],left_on="time",right_on="vf",direction="backward")
    return m["buy_line"].to_numpy(),m["sell_line"].to_numpy(),m["flip"].to_numpy()

def simulate(would, ohlc, variant):
    n=len(ohlc); idx_of={t:i for i,t in enumerate(ohlc["time"])}
    hi=ohlc["high"].to_numpy(); lo=ohlc["low"].to_numpy(); cl=ohlc["close"].to_numpy()
    m15=compute_trend(ohlc,2,"SMMA",ratchet=True)
    buyL=m15["buy_line"].to_numpy(); sellL=m15["sell_line"].to_numpy(); flipM=m15["flip"].to_numpy()
    buyH1,sellH1,flipH1=htf_lines(ohlc)
    htf = (variant=="htf")
    # opposite-confirmed-flip bar set: bars where a model BUY/SELL with prob>=CONF_PROB fired
    confbuy=set(); confsell=set()
    for _,s in would.iterrows():
        if float(s.get("win_prob",0) or 0)>=CONF_PROB:
            (confbuy if s["signal"]=="BUY" else confsell).add(s["bar_time"])
    rows=[]
    for _,s in would.iterrows():
        bt=s["bar_time"]; i0=idx_of.get(bt)
        if i0 is None or i0+1>=n: continue
        sgn=1 if s["signal"]=="BUY" else -1
        entry=float(s.get("price") or cl[i0]) or cl[i0]
        buf_abs=entry*BUF/100.0
        line=(buyH1[i0] if sgn>0 else sellH1[i0]) if htf else (buyL[i0] if sgn>0 else sellL[i0])
        if line is None or np.isnan(line): line=(buyL[i0] if sgn>0 else sellL[i0])
        if line is None or np.isnan(line): continue
        vsl=line-sgn*buf_abs
        min_dist=entry*SLMIN/100.0
        if abs(entry-vsl)<min_dist: vsl=entry-sgn*min_dist
        sl_dist=abs(entry-vsl)
        if sl_dist<=0: continue
        tp=entry+sgn*entry*TPCAP/100.0
        exit_px=exit_rsn=exit_t=None; trailing=False
        for j in range(i0+1,n):
            cur_buf=buf_abs
            # trend-hold: once +0.5R, widen buffer 3x to let it run
            if variant=="trendhold":
                cur_R=((cl[j]-entry)/sl_dist)*sgn
                if cur_R>=0.5: cur_buf=buf_abs*3.0
            if (sgn>0 and lo[j]<=vsl) or (sgn<0 and hi[j]>=vsl):
                exit_px=vsl; exit_rsn="TRAIL" if trailing else "SL"; exit_t=ohlc["time"].iloc[j]; break
            if (sgn>0 and hi[j]>=tp) or (sgn<0 and lo[j]<=tp):
                exit_px=tp; exit_rsn="TP"; exit_t=ohlc["time"].iloc[j]; break
            ln=(buyH1[j] if sgn>0 else sellH1[j]) if htf else (buyL[j] if sgn>0 else sellL[j])
            if ln is not None and not np.isnan(ln):
                new_sl=ln-sgn*cur_buf
                if (sgn>0 and new_sl>vsl) or (sgn<0 and new_sl<vsl): vsl=new_sl; trailing=True
            fl=(flipH1[j] if htf else flipM[j])
            if fl==-sgn:
                if variant=="flipconfirm":
                    # only flip if a confirmed opposite model signal exists at this bar
                    tj=ohlc["time"].iloc[j]
                    opp = confsell if sgn>0 else confbuy
                    if tj not in opp:
                        continue  # ignore noise flip, keep holding
                exit_px=cl[j]; exit_rsn="FLIP"; exit_t=ohlc["time"].iloc[j]; break
        if exit_px is None: continue
        R=((exit_px-entry)/sl_dist)*sgn
        cap=(exit_px-entry)*sgn
        rows.append({"bt":bt,"dir":s["signal"],"R":R,"cap":cap,"exit":exit_rsn})
    return pd.DataFrame(rows)

def pf(x):
    g=x[x>0].sum(); l=-x[x<0].sum(); return g/l if l>0 else 99.0

def main():
    sig=pd.read_csv(LOGS/"signals_all.csv")
    sig["bar_time"]=pd.to_datetime(sig.get("bar_time"),errors="coerce")
    sig=sig.dropna(subset=["bar_time"])
    would=sig[sig["signal"].isin(["BUY","SELL"])].copy()
    ohlc=load_ohlc()
    # available move over the signal span
    lo_t,hi_t=would.bar_time.min(),would.bar_time.max()
    win=ohlc[(ohlc.time>=lo_t)&(ohlc.time<=hi_t)]
    avail_path=win.close.diff().abs().sum()
    avail_net=abs(win.close.iloc[-1]-win.close.iloc[0])
    print(f"Signals: {len(would)} | period {lo_t.date()} -> {hi_t.date()}")
    print(f"Available move: path(all swings)={avail_path:,.0f} pts | net-directional={avail_net:,.0f} pts\n")
    print(f"{'variant':12} {'trades':>6} {'capturedPts':>11} {'cap/path':>8} {'totalR':>8} {'PF':>5} {'win%':>5} | exit-mix")
    for v in ["baseline","htf","flipconfirm","trendhold"]:
        r=simulate(would,ohlc,v)
        if r.empty: print(f"{v:12} (no trades)"); continue
        mix=r.exit.value_counts().to_dict()
        print(f"{v:12} {len(r):6d} {r.cap.sum():11,.0f} {100*r.cap.sum()/avail_path:7.1f}% {r.R.sum():+8.1f} {pf(r.R):5.2f} {100*(r.R>0).mean():4.0f}% | {mix}")

if __name__=="__main__":
    main()
