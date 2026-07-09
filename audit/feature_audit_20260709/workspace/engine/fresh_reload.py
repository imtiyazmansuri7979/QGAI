"""
fresh_reload.py — QUANT GOLD AI v2
═══════════════════════════════════════════════════════════════════
ONE-TIME full history reload from MT5 (broker-native, 2-decimal).
Pulls the broker's COMPLETE XAUUSD history for every timeframe into
fresh LIVE files, so training/backtest use one clean source — no
historical+live merge mismatch.

SAFETY:
  * Backs up data/live/ and data/historical/ to data/_pre_reload_backup/
    before touching anything. Restore = copy back.
  * Does NOT delete the old historical/ files — it RENAMES them with a
    .disabled suffix so merge_data.py stops using them (your old 2022
    data stays on disk, just inactive).
  * Recomputes ADX from the fresh OHLC (same formula as updater).

Run:  python fresh_reload.py            (asks for confirmation)
      python fresh_reload.py --yes      (skip prompt)
═══════════════════════════════════════════════════════════════════
"""
import sys, shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import MetaTrader5 as mt5
except ImportError:
    print("❌ MetaTrader5 module not found"); sys.exit(1)
try:
    import config_mt5 as _c
except ImportError:
    print("❌ config_mt5.py not found"); sys.exit(1)

import numpy as np
import pandas as pd
from config import CFG

SYMBOL   = getattr(_c, "MT5_SYMBOL", "XAUUSD")   # read from config_mt5 (was hardcoded "XAUUSD.pc")
DATA     = Path(CFG.paths.hist_dir).parent
LIVE     = Path(CFG.paths.live_dir)
HIST     = Path(CFG.paths.hist_dir)
BACKUP   = DATA / "_pre_reload_backup"

# timeframe → (MT5 attr, live OHLC filename)
TFS = {
    "M15": ("TIMEFRAME_M15", "ohlc_live.csv"),       # primary — drives features/training
    "M5":  ("TIMEFRAME_M5",  "ohlc_m5_live.csv"),
    "M30": ("TIMEFRAME_M30", "ohlc_m30_live.csv"),
    "H1":  ("TIMEFRAME_H1",  "ohlc_h1_live.csv"),
    "H4":  ("TIMEFRAME_H4",  "ohlc_h4_live.csv"),
    "D1":  ("TIMEFRAME_D1",  "ohlc_d1_live.csv"),
}


def _wilder(series, period):
    out = np.full(len(series), np.nan)
    if len(series) < period: return out
    out[period-1] = series[:period].mean()
    for i in range(period, len(series)):
        out[i] = (out[i-1]*(period-1) + series[i]) / period
    return out


def compute_adx(df, period=14):
    """Multi-TF ADX from M15 OHLC — same approach as mt5_data_updater."""
    d = df.copy()
    d["time"] = pd.to_datetime(d["time"])
    d = d.set_index("time")
    def one_tf(rule):
        r = d.resample(rule).agg({"open":"first","high":"max","low":"min","close":"last"}).dropna() if rule else d
        h,l,c = r["high"].values, r["low"].values, r["close"].values
        if len(c) < period*2: 
            s = pd.Series(np.nan, index=r.index); return s, s, s
        up = h[1:]-h[:-1]; dn = l[:-1]-l[1:]
        pdm = np.where((up>dn)&(up>0), up, 0.0); ndm = np.where((dn>up)&(dn>0), dn, 0.0)
        tr  = np.maximum(h[1:]-l[1:], np.maximum(np.abs(h[1:]-c[:-1]), np.abs(l[1:]-c[:-1])))
        atr=_wilder(tr,period); spdm=_wilder(pdm,period); sndm=_wilder(ndm,period)
        with np.errstate(divide="ignore",invalid="ignore"):
            pdi=100*spdm/atr; ndi=100*sndm/atr
            dx=100*np.abs(pdi-ndi)/(pdi+ndi)
        adx=_wilder(dx,period)
        idx=r.index[1:]
        return (pd.Series(adx,index=idx), pd.Series(pdi,index=idx), pd.Series(ndi,index=idx))
    # 2026-07-02 (Divyesh) HMM v3: lag-free band volatility per TF (parity with
    # regen_adx_di.py / mt5_data_updater.py — same trend_signal._ma SMMA2 band).
    def one_band(rule):
        from trend_signal import _ma
        r = d.resample(rule).agg({"open":"first","high":"max","low":"min","close":"last"}).dropna() if rule else d
        bw = (_ma(r["high"].to_numpy(float), 2, "SMMA")
              - _ma(r["low"].to_numpy(float), 2, "SMMA")) / r["close"].to_numpy(float) * 100.0
        return pd.Series(bw, index=r.index)
    out = pd.DataFrame(index=d.index)
    for name,rule in [("M15",None),("M30","30min"),("H1","1h"),("H4","4h")]:
        a,p,n = one_tf(rule)
        out[f"{name}_ADX"]=a.reindex(d.index,method="ffill").round(2)
        out[f"{name}_PlusDI"]=p.reindex(d.index,method="ffill").round(2)
        out[f"{name}_MinusDI"]=n.reindex(d.index,method="ffill").round(2)
        out[f"{name}_DI_diff"]=(out[f"{name}_PlusDI"]-out[f"{name}_MinusDI"]).round(2)
        out[f"{name}_band_width_pct"]=one_band(rule).reindex(d.index,method="ffill").round(4)
        # HMM v3 'rel' features — parity with regen_adx_di.py / mt5_data_updater.py
        _p=out[f"{name}_PlusDI"]; _n=out[f"{name}_MinusDI"]
        out[f"{name}_di_eff"]=(100*(_p-_n).abs()/(_p+_n+1e-9)).round(2)
        _b=out[f"{name}_band_width_pct"]
        out[f"{name}_band_rel"]=(_b/_b.rolling("30D").mean()).round(4).fillna(1.0)
    out=out.reset_index()
    out["timestamp"]=out["time"]; out["Time (24h)"]=out["time"].dt.strftime("%H:%M")
    out=out.drop(columns=["time"]).fillna(0.0)
    return out


def fetch(tf_attr):
    end = datetime.now(timezone.utc) + timedelta(days=2)
    rates = mt5.copy_rates_from_pos(SYMBOL, getattr(mt5, tf_attr), 0, 500_000)
    if rates is None or len(rates) == 0: return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    df = df[df["time"] <= now]
    df["time"] = df["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df[["time","open","high","low","close","tick_volume"]]


def main():
    yes = "--yes" in sys.argv
    print("="*64)
    print("  FRESH RELOAD — full broker history, 2-decimal, all TFs")
    print("="*64)
    print(f"  Symbol: {SYMBOL} | will reload: {', '.join(TFS)}")
    print(f"  Old historical/ files will be RENAMED .disabled (not deleted)")
    print(f"  Backup → {BACKUP}")
    if not yes:
        if input("\n  Proceed? type YES: ").strip() != "YES":
            print("  Cancelled."); return

    # 1. backup
    BACKUP.mkdir(parents=True, exist_ok=True)
    for src in (LIVE, HIST):
        if src.exists():
            dst = BACKUP / src.name
            if dst.exists(): shutil.rmtree(dst)
            shutil.copytree(src, dst)
    print(f"  ✅ Backed up live/ + historical/ → {BACKUP}")

    # 2. connect
    if not mt5.initialize(path=_c.MT5_PATH, login=_c.MT5_LOGIN,
                          password=_c.MT5_PASS, server=_c.MT5_SERVER, timeout=10000):
        print(f"  ❌ MT5 connect failed: {mt5.last_error()}"); return
    LIVE.mkdir(parents=True, exist_ok=True)

    # 3. fetch each TF fresh
    m15_df = None
    for name,(attr,fname) in TFS.items():
        df = fetch(attr)
        if df is None:
            print(f"  ⚠️ {name}: no data"); continue
        df.to_csv(LIVE / fname, index=False)
        print(f"  ✅ {name}: {len(df):,} bars → live/{fname} "
              f"({df['time'].iloc[0][:10]} → {df['time'].iloc[-1][:10]})")
        if name == "M15": m15_df = df

    # 4. fresh ADX from M15
    if m15_df is not None:
        adx = compute_adx(m15_df)
        adx.to_csv(LIVE / "adx_live.csv", index=False)
        print(f"  ✅ ADX recomputed: {len(adx):,} rows → live/adx_live.csv")

    mt5.shutdown()

    # 5. disable old historical + ORIG sources so merge uses ONLY fresh live
    disabled = 0
    for f in HIST.glob("*.csv"):
        f.rename(f.with_suffix(".csv.disabled")); disabled += 1
    for orig in [DATA / "ohlc and volum data.csv",
                 DATA / "Back_testing_with_ADX_Data_Final_cleaned.csv"]:
        if orig.exists():
            orig.rename(orig.with_suffix(orig.suffix + ".disabled")); disabled += 1
    print(f"  ✅ {disabled} old source file(s) → .disabled (inactive, recoverable)")

    print("="*64)
    print("  DONE. Next:")
    print("    1. python merge_data.py        (build merged from fresh live)")
    print("    2. QGAI_RETRAIN.bat            (or just train.py)")
    print("    3. python build_feature_snapshot.py --rebuild --verify 10")
    print("  Restore if needed: copy _pre_reload_backup/* back, un-rename .disabled")
    print("="*64)


if __name__ == "__main__":
    main()
