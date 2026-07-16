"""
build_feature_snapshot.py — QUANT GOLD AI v2
═══════════════════════════════════════════════════════════════════
Saves the FULL feature vector (all model features) for EVERY closed
M15 bar into one auditable file:

    data/merged/features_merged.csv

Layout:
  * time
  * 58+ shared features (same for BUY and SELL) — saved once
  * direction-dependent features — saved twice with _buy / _sell suffix:
      trade_direction, momentum_aligned_1hr/2hr/4hr,
      ts_aligned, ts_aligned_htf, h4_h1_regime_score, h4_trending_h1_aligned

INCREMENTAL by design: first run computes the full range (slow, one
time); every run after that appends ONLY new bars (seconds). Runs
automatically from merge_data.py, or standalone:

    python build_feature_snapshot.py                 # incremental
    python build_feature_snapshot.py --rebuild       # full rebuild
    python build_feature_snapshot.py --from 2025-01-01
    python build_feature_snapshot.py --verify 10
═══════════════════════════════════════════════════════════════════
"""
import sys
import time as _time
import numpy as np
import pandas as pd
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))

DATA      = ENGINE.parent / "data"
OHLC_FILE = DATA / "merged" / "ohlc_merged.csv"
ADX_FILE  = DATA / "merged" / "adx_merged.csv"
NEWS_FILE = DATA / "news_all_2024_to_now_pure_cleaned.csv"
TRADES_FILE = DATA / "Back_testing_data_final_cleaned.xlsx"
OUT_FILE  = DATA / "merged" / "features_merged.csv"

DEFAULT_FROM = "2024-12-01"     # backtest trades start — keeps first run sane

# Direction-dependent features (verified by BUY-vs-SELL diff + code review)
DIR_FEATS = [
    "trade_direction",
    "momentum_aligned_1hr", "momentum_aligned_2hr", "momentum_aligned_4hr",
    "ts_aligned", "ts_aligned_htf",
    "h4_h1_regime_score", "h4_trending_h1_aligned",
]


def _load_all():
    import features as F
    ohlc = F.load_ohlc(str(OHLC_FILE))
    adx  = F.load_adx(str(ADX_FILE))
    news = F.load_news(str(NEWS_FILE)) if NEWS_FILE.exists() else pd.DataFrame()
    trades = F.load_trades(str(TRADES_FILE))
    aux = dict(
        slot_table=F.build_slot_table(trades),
        h4_df=F.build_h4_range_table(ohlc),
        h1_ob=F.build_ob_table(ohlc, "1h"),
        h4_ob_df=F.build_ob_table(ohlc, "4h"),
    )
    return F, ohlc, adx, news, aux


def build(date_from=None, rebuild=False, verbose=True):
    F, ohlc, adx, news, aux = _load_all()
    shared = [c for c in F.FEATURE_COLS if c not in DIR_FEATS]

    bars = ohlc[["datetime"]].copy()
    bars = bars[bars["datetime"] >= pd.Timestamp(date_from or DEFAULT_FROM)]

    # incremental: skip bars already in the file
    existing = None
    if OUT_FILE.exists() and not rebuild:
        existing = pd.read_csv(OUT_FILE)
        if len(existing):
            last = pd.Timestamp(existing["time"].iloc[-1])
            bars = bars[bars["datetime"] > last]
            if verbose:
                print(f"  Incremental: existing rows {len(existing):,} "
                      f"(last {last}) → new bars to compute: {len(bars):,}")
    if len(bars) == 0:
        if verbose:
            print("  [OK] Already up to date — nothing to compute.")
        return existing

    rows, t0 = [], _time.time()
    for k, t in enumerate(bars["datetime"]):
        fb = F.compute_features(t, "BUY", 0.10, ohlc, adx, news, **aux)
        fs = F.compute_features(t, "SELL", 0.10, ohlc, adx, news, **aux)
        r = {"time": t.strftime("%Y-%m-%d %H:%M:%S")}
        for c in shared:
            r[c] = fb.get(c)
        for c in DIR_FEATS:
            r[f"{c}_buy"]  = fb.get(c)
            r[f"{c}_sell"] = fs.get(c)
        rows.append(r)
        if verbose and (k + 1) % 500 == 0:
            rate = (k + 1) / (_time.time() - t0)
            eta  = (len(bars) - k - 1) / max(rate, 1e-9)
            print(f"    {k+1:,}/{len(bars):,} bars | {rate:.0f} bars/s | ETA {eta/60:.1f} min", end="\r")

    new_df = pd.DataFrame(rows)
    out = pd.concat([existing, new_df], ignore_index=True) if existing is not None else new_df
    out.to_csv(OUT_FILE, index=False)
    if verbose:
        sz = OUT_FILE.stat().st_size / 1e6
        print(f"\n  [OK] {len(out):,} rows × {len(out.columns)} cols → {OUT_FILE} ({sz:.1f}MB) "
              f"| computed {len(new_df):,} new in {(_time.time()-t0)/60:.1f} min")
    return out


def verify(n_samples=10):
    """Recompute N random saved bars fresh and assert exact match."""
    F, ohlc, adx, news, aux = _load_all()
    snap = pd.read_csv(OUT_FILE)
    rng = np.random.default_rng(11)
    idxs = rng.integers(0, len(snap), n_samples)
    shared = [c for c in F.FEATURE_COLS if c not in DIR_FEATS]
    bad = 0
    for i in idxs:
        row = snap.iloc[i]
        t = pd.Timestamp(row["time"])
        fb = F.compute_features(t, "BUY", 0.10, ohlc, adx, news, **aux)
        fs = F.compute_features(t, "SELL", 0.10, ohlc, adx, news, **aux)
        for c in shared:
            if pd.notna(row[c]) and abs(float(fb.get(c, 0)) - float(row[c])) > 1e-6:
                print(f"  [MISMATCH] {row['time']} {c}: saved={row[c]} fresh={fb.get(c)}")
                bad += 1
        for c in DIR_FEATS:
            for suf, f_ in (("_buy", fb), ("_sell", fs)):
                v = row.get(f"{c}{suf}")
                if pd.notna(v) and abs(float(f_.get(c, 0)) - float(v)) > 1e-6:
                    print(f"  [MISMATCH] {row['time']} {c}{suf}: saved={v} fresh={f_.get(c)}")
                    bad += 1
    if bad == 0:
        print(f"  [OK] VERIFY PASSED — {n_samples} random bars, all features match ✅")
    else:
        print(f"  [ERR] {bad} mismatches!")
    return bad == 0


if __name__ == "__main__":
    print("=" * 55)
    print("  FEATURE SNAPSHOT — full vector, every 15min, saved")
    print("=" * 55)
    args = sys.argv[1:]
    dfrom = None
    if "--from" in args:
        dfrom = args[args.index("--from") + 1]
    build(date_from=dfrom, rebuild="--rebuild" in args)
    if "--verify" in args:
        try:
            nv = int(args[args.index("--verify") + 1])
        except Exception:
            nv = 10
        verify(nv)
