"""
rebuild_trainset.py — Task: rebuild the training ENTRY SET (Option A).

The old training xlsx holds an OLD strategy's selective trades (Dec-24→Apr-26). After the last
2-3 weeks of changes the live system takes/misses different trades, so those entries are stale.

This regenerates the training set from the CURRENT structural entry trigger — every 2-SMMA(2)
ratchet FLIP (trend change) — over the FULL OHLC history (2022→2026), and labels each candidate
under the CURRENT LIVE exit engine (ratchet + HTF H1 SL/flip + TP cap + buffer).

WHY flips: model-independent (no chicken-egg with the win-prob model), leakage-safe, and matches
this codebase's design = "train on ALL candidate signals, apply the win-prob threshold + range/CTF
filters at INFERENCE only" (train.py). The model learns to rank ALL flip candidates; live then
selects the good ones. Gives ~5x more data incl. the 2022-2024 unseen regime.

Output: data/Back_testing_trainset_REBUILT.xlsx  (same schema as the old xlsx + R/exit_reason)
Then: point config.trades_file at it -> 3_Train_Models.bat -> WFO-validate vs current. Reversible.

Run:  python rebuild_trainset.py
"""
import numpy as np, pandas as pd
from pathlib import Path
from trend_signal import compute_trend
from analyze_capture import load_ohlc, htf_lines, BUF, SLMIN, TPCAP
from features import load_adx
from hmm_model import MarketStateHMM, STATE_NAMES
from config import CFG

OUT = Path(CFG.paths.trades_file).with_name("Back_testing_trainset_REBUILT.xlsx")

# 2026-07-13 (night): regime-adaptive TP cap fix (see relabel_trades.py for the
# full writeup) -- single source of truth in config.py, was a duplicated literal.
TP_BY_REGIME = dict(CFG.filters.tp_by_regime)


def regime_lookup_table(ohlc):
    """Per-bar regime array (aligned to ohlc rows) via the EXISTING production
    hmm_model.pkl (no refit) -- as-of the last closed ADX bar, no lookahead."""
    adx_df = load_adx(CFG.paths.adx_file)
    hmm = MarketStateHMM()
    hmm.load(str(Path(CFG.paths.models_dir) / "hmm_model.pkl"))
    states = hmm.predict_batch(adx_df)
    adx_times = adx_df["datetime"].values.astype("datetime64[ns]")
    ohlc_times = ohlc["time"].values.astype("datetime64[ns]")
    idx = np.searchsorted(adx_times, ohlc_times, side="right") - 1
    idx = np.clip(idx, 0, len(states) - 1)
    return np.array([STATE_NAMES.get(int(states[i]), "Ranging") for i in idx])


def simulate(ohlc):
    """Every 2-SMMA flip = a candidate entry (next-bar open); exit via the live HTF engine."""
    n = len(ohlc)
    op = ohlc["open"].to_numpy(); hi = ohlc["high"].to_numpy()
    lo = ohlc["low"].to_numpy();  cl = ohlc["close"].to_numpy()
    tm = ohlc["time"]
    m15 = compute_trend(ohlc, 2, "SMMA", ratchet=True)
    buyL = m15["buy_line"].to_numpy(); sellL = m15["sell_line"].to_numpy()
    flip = m15["flip"].fillna(0).to_numpy()
    buyH1, sellH1, flipH1 = htf_lines(ohlc)
    regimes = regime_lookup_table(ohlc) if CFG.filters.ratchet_tp_regime else None

    rows = []
    for i in range(n - 2):
        f = flip[i]
        if f == 0:
            continue
        sgn = 1 if f > 0 else -1            # +1 flip = BUY, -1 = SELL
        i0 = i + 1                          # enter on the bar AFTER the flip (next-bar open)
        entry = float(op[i0])
        if not np.isfinite(entry) or entry <= 0:
            continue
        buf_abs = entry * BUF / 100.0
        line = buyH1[i0] if sgn > 0 else sellH1[i0]
        if line is None or np.isnan(line):
            line = buyL[i0] if sgn > 0 else sellL[i0]
        if line is None or np.isnan(line):
            continue
        vsl = line - sgn * buf_abs
        min_dist = entry * SLMIN / 100.0
        if abs(entry - vsl) < min_dist:
            vsl = entry - sgn * min_dist
        sl_dist = abs(entry - vsl)
        if sl_dist <= 0:
            continue
        tp_pct = TP_BY_REGIME.get(regimes[i0], TPCAP) if regimes is not None else TPCAP
        tp = entry + sgn * entry * tp_pct / 100.0

        exit_px = exit_rsn = None; exit_t = None; trailing = False
        for j in range(i0 + 1, n):
            if (sgn > 0 and lo[j] <= vsl) or (sgn < 0 and hi[j] >= vsl):
                exit_px = vsl; exit_rsn = "TRAIL" if trailing else "SL"; exit_t = tm.iloc[j]; break
            if (sgn > 0 and hi[j] >= tp) or (sgn < 0 and lo[j] <= tp):
                exit_px = tp; exit_rsn = "TP"; exit_t = tm.iloc[j]; break
            ln = buyH1[j] if sgn > 0 else sellH1[j]
            if ln is not None and not np.isnan(ln):
                new_sl = ln - sgn * buf_abs
                if (sgn > 0 and new_sl > vsl) or (sgn < 0 and new_sl < vsl):
                    vsl = new_sl; trailing = True
            if flipH1[j] == -sgn:
                exit_px = cl[j]; exit_rsn = "FLIP"; exit_t = tm.iloc[j]; break
        if exit_px is None:
            continue
        R = ((exit_px - entry) / sl_dist) * sgn
        et = tm.iloc[i0]
        dur = (exit_t - et).total_seconds() / 60.0
        rows.append({
            "Type": "BUY" if sgn > 0 else "SELL",
            "Day": et.strftime("%a"),
            "Open Date": et.strftime("%Y-%m-%d"),
            "Open Time (24h)": et.strftime("%H:%M:%S"),
            "Entry Price": round(entry, 2),
            "Close Date": exit_t.strftime("%Y-%m-%d"),
            "Close Time (24h)": exit_t.strftime("%H:%M:%S"),
            "Exit Price": round(float(exit_px), 2),
            "Volume": 0.10,
            "Duration (min)": round(dur, 0),
            "P&L ($)": round((exit_px - entry) * sgn * 10.0, 2),   # ~0.10 lot gold
            "Win": "✓" if R > 0 else "✗",
            "$ Move": round((exit_px - entry) * sgn, 2),
            "% Move": round((exit_px - entry) * sgn / entry * 100, 4),
            "R": round(float(R), 4),
            "exit_reason": exit_rsn,
        })
    df = pd.DataFrame(rows)
    df.insert(0, "#", range(1, len(df) + 1))
    return df


def main():
    print("=" * 60)
    print("  REBUILD TRAINSET — 2-SMMA flips + live HTF exit (full history)")
    if CFG.filters.ratchet_tp_regime:
        print(f"  buffer {BUF}% | min-SL {SLMIN}% | TP cap: REGIME-ADAPTIVE {TP_BY_REGIME} "
              f"(fallback {TPCAP}%)")
    else:
        print(f"  buffer {BUF}% | min-SL {SLMIN}% | TP cap {TPCAP}% (flat -- ratchet_tp_regime=False)")
    print("=" * 60)
    ohlc = load_ohlc()
    print(f"  OHLC: {len(ohlc):,} bars | {ohlc['time'].min().date()} -> {ohlc['time'].max().date()}")
    df = simulate(ohlc)
    wr = (df["Win"] == "✓").mean() * 100
    print(f"\n  Candidate trades (flips): {len(df):,}")
    print(f"  Win rate (live exit): {wr:.1f}%")
    print(f"  Exit mix: {df['exit_reason'].value_counts().to_dict()}")
    print(f"  R: total {df['R'].sum():+.1f} | avg {df['R'].mean():+.4f}")
    tmp = df.assign(yr=df['Open Date'].str[:4], w=(df['Win'] == "✓").astype(int))
    by = tmp.groupby('yr')['w'].agg(['count', 'mean'])
    print("  By year (count | win%):")
    for yr, r in by.iterrows():
        print(f"    {yr}: {int(r['count']):5d} | {r['mean']*100:4.1f}%")
    df.to_excel(OUT, index=False)
    print("  SAVED:", OUT)


if __name__ == "__main__":
    main()
