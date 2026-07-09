"""
build_prob_buckets.py  (ET-panel helper, 2026-07-03)
Precompute "signals like this historically" stats per win_prob bucket (+ per HMM
regime) from a backtest trades CSV → logs/prob_bucket_stats.json. The dashboard's
AI-summary box reads this (read-only, cached) to show WR/PF/avgR/maxDD for the
current signal's prob band. Re-run after a fresh full backtest.

Usage:  python build_prob_buckets.py [trades_csv]
Default trades_csv = backtest/results/fullbt_hmm_10k_lot001/backtest_trades_st-htf.csv
"""
import sys, json, glob
from pathlib import Path
import pandas as pd
from config import CFG

ENG = Path(__file__).resolve().parent
DEFAULT = ENG.parent / "backtest" / "results" / "fullbt_hmm_10k_lot001" / "backtest_trades_st-htf.csv"


def _stats(x):
    x = x.dropna(subset=["wp", "r"])
    n = len(x)
    if n == 0:
        return {"n": 0}
    wr = float((x.r > 0).mean() * 100)
    gp = float(x.r[x.r > 0].sum()); gl = float(-x.r[x.r < 0].sum())
    pf = (gp / gl) if gl > 0 else 99.9
    eq = x.r.cumsum(); dd = float((eq.cummax() - eq).max())
    return {"n": int(n), "wr": round(wr, 1), "pf": round(pf, 2),
            "avg_r": round(float(x.r.mean()), 3), "total_r": round(float(x.r.sum()), 1),
            "max_dd_r": round(dd, 1)}


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT)
    files = glob.glob(src)
    if not files:
        print(f"[ERR] trades CSV not found: {src}"); return 1
    d = pd.read_csv(files[0])
    d["wp"] = pd.to_numeric(d.get("win_prob"), errors="coerce")
    d["r"] = pd.to_numeric(d.get("r_achieved"), errors="coerce")
    reg = d.get("hmm_state", pd.Series(["?"] * len(d)))

    out = {"source": Path(files[0]).name, "trades": int(len(d)),
           "buckets": {
               "gt60": _stats(d[d.wp > 0.60]),
               "p45_60": _stats(d[(d.wp >= 0.45) & (d.wp <= 0.60)]),
               "all": _stats(d)},
           "by_regime_gt60": {}}
    for rg in ("Ranging", "Trending", "Volatile"):
        out["by_regime_gt60"][rg] = _stats(d[(d.wp > 0.60) & (reg == rg)])

    dest = Path(CFG.paths.logs_dir) / "prob_bucket_stats.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[OK] wrote {dest}")
    print(f"   gt60: {out['buckets']['gt60']}")
    print(f"   p45_60: {out['buckets']['p45_60']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
