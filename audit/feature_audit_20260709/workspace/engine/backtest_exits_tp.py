"""
backtest_exits_tp.py — Exit-method & TP comparison on 1 year of signals
=======================================================================
On the LAST 12 MONTHS of your real BUY/SELL signals, compares:
  • EXIT methods:  current Ratchet  vs  Struct-H1  vs  Refined
  • TP sweep:      equity-TP 1.33R  vs  price-TP 0.50% .. 4.00%

Same 1R unit (ratchet line distance) everywhere → numbers comparable.
Entries are your real signals, unchanged. This is a BACKTEST ONLY —
it does NOT touch live trading.

Run from the engine folder:
    python backtest_exits_tp.py

Needs: pandas, numpy, trend_signal.py (in engine/).
Reads: ../data/merged/ohlc_merged.csv  and  logs/signals_all.csv
"""
import sys
from pathlib import Path
import pandas as pd, numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from trend_signal import compute_trend

OHLC    = ROOT / "data" / "merged" / "ohlc_merged.csv"
SIGNALS = HERE / "logs" / "signals_all.csv"

BUF        = 0.0009    # ratchet buffer = 0.09% of price
STRUCT_N   = 6         # H1 structure lookback
HOR        = 48        # max bars held (12h on M15)
DAYS       = 365
CURRENT_TP = 0.50      # your live ratchet_tp_cap_pct (marked in the table)
TP_SWEEP   = [0.50, 0.60, 0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 2.00, 4.00]

# ── price data + ratchet trend line + H1 structure ────────────────────
o = pd.read_csv(OHLC, parse_dates=["time"]).sort_values("time").reset_index(drop=True)
t = compute_trend(o[["time", "open", "high", "low", "close"]], 2, "SMMA", ratchet=True)
for c in ["buy_line", "sell_line", "flip"]:
    o[c] = t[c].values
g = o.set_index("time").resample("60min").agg({"high": "max", "low": "min"}).dropna()
lv = pd.DataFrame({"time": g.index,
                   "sup": g["low"].rolling(STRUCT_N, min_periods=2).min().shift(1).values,
                   "res": g["high"].rolling(STRUCT_N, min_periods=2).max().shift(1).values}).dropna()
mm = pd.merge_asof(o[["time"]], lv.sort_values("time"), on="time", direction="backward")
o["sup_h1"] = mm["sup"].values; o["res_h1"] = mm["res"].values

TM = o["time"].values; LOW = o.low.values; HIGH = o.high.values; CLO = o.close.values
BL = o.buy_line.values; SLN = o.sell_line.values; FLIP = o.flip.values
SUP = o.sup_h1.values; RES = o.res_h1.values
IDX = {pd.Timestamp(x): k for k, x in enumerate(TM)}

sig = pd.read_csv(SIGNALS, parse_dates=["bar_time"])
sig = sig[sig.signal.isin(["BUY", "SELL"])]
sig = sig[sig.bar_time >= sig.bar_time.max() - pd.Timedelta(days=DAYS)]


def setup(i, d, entry):
    line0 = BL[i] if d == "BUY" else SLN[i]
    if line0 != line0:
        return None
    buf = entry * BUF
    sl  = (line0 - buf) if d == "BUY" else (line0 + buf)
    sld = (entry - sl) if d == "BUY" else (sl - entry)
    return (sl, sld) if sld > 0 else None


def exit_ratchet(i, d, entry, sl, sld, tp_dist=None, struct=False):
    """Ratchet trail/flip. Optional price-TP (tp_dist $) and/or Struct-H1 break."""
    s = sl
    tp = None
    if tp_dist:
        tp = (entry + tp_dist) if d == "BUY" else (entry - tp_dist)
    for k in range(1, HOR + 1):
        j = i + k
        if j >= len(TM):
            break
        if tp is not None:
            if d == "BUY" and HIGH[j] >= tp:  return (tp - entry) / sld
            if d == "SELL" and LOW[j] <= tp:  return (entry - tp) / sld
        if struct:
            su, re = SUP[j], RES[j]
            if d == "BUY" and su == su and CLO[j] < su:  return (CLO[j] - entry) / sld
            if d == "SELL" and re == re and CLO[j] > re: return (entry - CLO[j]) / sld
        lk = BL[j] if d == "BUY" else SLN[j]
        if lk == lk:
            ns = (lk - entry * BUF) if d == "BUY" else (lk + entry * BUF)
            if d == "BUY" and ns > s:  s = ns
            if d == "SELL" and ns < s: s = ns
        if (d == "BUY" and LOW[j] <= s) or (d == "SELL" and HIGH[j] >= s):
            return ((s - entry) / sld) if d == "BUY" else ((entry - s) / sld)
        if (d == "BUY" and FLIP[j] == -1) or (d == "SELL" and FLIP[j] == 1):
            return ((CLO[j] - entry) / sld) if d == "BUY" else ((entry - CLO[j]) / sld)
    j = min(i + HOR, len(TM) - 1)
    return ((CLO[j] - entry) / sld) if d == "BUY" else ((entry - CLO[j]) / sld)


def stats(s):
    s = np.asarray(s)
    if len(s) == 0:
        return 0, 0, 0, 0, 0, 0
    eq = np.cumsum(s); dd = (np.maximum.accumulate(eq) - eq).max()
    w = s[s > 0]; l = s[s <= 0]
    pf = w.sum() / abs(l.sum()) if l.sum() != 0 else float("inf")
    mcl = cur = 0
    for x in s:
        cur = cur + 1 if x <= 0 else 0; mcl = max(mcl, cur)
    return s.sum(), s.mean(), (s > 0).mean() * 100, pf, dd, mcl


rat = []; h1 = []; rg = []
tp_eq = []; sweep = {p: [] for p in TP_SWEEP}
for _, r in sig.iterrows():
    i = IDX.get(pd.Timestamp(r.bar_time))
    if i is None:
        continue
    d = r.signal; entry = float(r.price)
    st = setup(i, d, entry)
    if st is None:
        continue
    sl, sld = st
    rg.append(str(r.hmm_state))
    rat.append(exit_ratchet(i, d, entry, sl, sld))
    h1.append(exit_ratchet(i, d, entry, sl, sld, struct=True))
    tp_eq.append(exit_ratchet(i, d, entry, sl, sld, tp_dist=1.3333 * sld))
    for p in TP_SWEEP:
        sweep[p].append(exit_ratchet(i, d, entry, sl, sld, tp_dist=entry * p / 100))

rg = np.array(rg)
refined = np.where(rg == "Volatile", np.array(rat), np.array(h1))

print(f"\n1-YEAR BACKTEST  ({sig.bar_time.min().date()} -> {sig.bar_time.max().date()})  |  {len(rat)} trades")
print("(exit/TP study only — entries unchanged; spread/slippage NOT deducted)\n")

def row(name, s, mark=""):
    tot, avg, wr, pf, dd, mcl = stats(s)
    print(f"  {name:<24}{tot:>8.1f}R  avg {avg:+.3f}  WR {wr:>3.0f}%  PF {pf:>4.2f}  maxDD {dd:>3.0f}R  streak {mcl}{mark}")

print("=== EXIT METHOD ===")
row("Ratchet (current)", rat)
row("Struct H1", h1)
row("Refined (H1 ex-Vol)", refined)

print("\n=== TP SWEEP (with ratchet trail/flip) ===")
row("equity-TP 1.33R (old)", tp_eq)
for p in TP_SWEEP:
    mark = "   <== LIVE" if abs(p - CURRENT_TP) < 1e-9 else ""
    row(f"price-TP {p:.2f}%", sweep[p], mark)

print("\nBy regime — Ratchet vs Struct H1 (Total R):")
for reg in ["Ranging", "Trending", "Volatile"]:
    mk = rg == reg
    if mk.sum():
        print(f"  {reg:<10} n={mk.sum():>3} | Ratchet {np.array(rat)[mk].sum():+6.1f}R"
              f" | StructH1 {np.array(h1)[mk].sum():+6.1f}R")
