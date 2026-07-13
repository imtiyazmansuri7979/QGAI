"""
relabel_trades.py — Task 1 (Option B): closed-loop relabel.

Takes the historical ENTRIES from the training xlsx (Back_testing_data_final_cleaned.xlsx)
and recomputes each trade's Win / R / exit under the CURRENT LIVE exit engine
(2-SMMA ratchet line + HTF H1 line SL/flip + TP cap + buffer), so the win-probability
model trains on labels that MATCH what the live bridge actually does.

Faithful to analyze_capture.py 'htf' variant (which mirrors backtest_replay / the live
bridge). Leakage-safe: each trade is simulated forward only on its OWN future bars until
it exits — no future info leaks into the entry.

Keeps the same ENTRY set (same entry times + direction + price); only the OUTCOME columns
(Win, Exit Price, $ Move, % Move, Close Date/Time, Duration) are recomputed, plus two new
columns R and exit_reason. Schema otherwise unchanged so train.py reads it as-is.

OUTPUT: data/Back_testing_data_final_cleaned_RELABELED.xlsx  (+ _RELABEL_DIFF.csv)
Then: point config.trades_file at it -> 3_Train_Models.bat -> WFO-validate vs current.

Run:  python relabel_trades.py
"""
import numpy as np, pandas as pd
from pathlib import Path
from trend_signal import compute_trend
# reuse the EXACT line construction + config the live-faithful capture tool uses
from analyze_capture import load_ohlc, htf_lines, BUF, SLMIN, TPCAP
from features import load_adx
from hmm_model import MarketStateHMM, STATE_NAMES
from config import CFG

XLSX = Path(CFG.paths.trades_file)
OUT  = XLSX.with_name(XLSX.stem + "_RELABELED.xlsx")
DIFF = XLSX.with_name(XLSX.stem + "_RELABEL_DIFF.csv")

# 2026-07-13 (night): regime-adaptive TP cap fix (Fable-5-reviewed, diagnostic
# measured 0.62% total label flips / +46.4R on the current trades file --
# real but small; fixed here anyway for label-vs-live-exit truth, not because
# a retrain was judged necessary). Reads config.py's single source of truth
# (was a duplicated literal here + backtest_replay.py + rebuild_trainset.py +
# shadow_ledger.py). Toggle CFG.filters.ratchet_tp_regime=False to revert to
# the old flat TPCAP behaviour for all regimes.
TP_BY_REGIME = dict(CFG.filters.tp_by_regime)


def load_entries():
    df = pd.read_excel(XLSX)
    ds = df["Open Date"].astype(str) + " " + df["Open Time (24h)"].astype(str)
    df["datetime"] = pd.to_datetime(ds, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    df = df[df["datetime"].notna()].reset_index(drop=True)
    return df


def assign_regimes(df):
    """Retro-classify each entry's regime using the EXISTING production
    hmm_model.pkl (no refit) -- same approach as diagnose_tp_cap_regime_labels.py."""
    adx_df = load_adx(CFG.paths.adx_file)
    hmm = MarketStateHMM()
    hmm.load(str(Path(CFG.paths.models_dir) / "hmm_model.pkl"))
    states = hmm.predict_batch(adx_df)
    times = adx_df["datetime"].values.astype("datetime64[ns]")
    out = []
    for t in df["datetime"]:
        t64 = np.datetime64(t)
        i = int(np.searchsorted(times, t64, side="right")) - 1   # last CLOSED bar, no lookahead
        out.append(STATE_NAMES.get(int(states[i]), "Ranging") if i >= 0 else "Ranging")
    return out


def relabel(df, ohlc, tp_pcts):
    """Simulate every entry under the live HTF exit engine; return outcome columns.
    tp_pcts: one TP% per row, aligned to df by position (regime-adaptive or flat)."""
    n = len(ohlc)
    idx_of = {t: i for i, t in enumerate(ohlc["time"])}
    hi = ohlc["high"].to_numpy(); lo = ohlc["low"].to_numpy(); cl = ohlc["close"].to_numpy()
    buyH1, sellH1, flipH1 = htf_lines(ohlc)              # H1 ratchet line + flip (live exit)
    m15 = compute_trend(ohlc, 2, "SMMA", ratchet=True)   # M15 fallback if H1 line missing
    buyL = m15["buy_line"].to_numpy(); sellL = m15["sell_line"].to_numpy()

    out, miss = [], 0
    BLANK = (np.nan, pd.NaT, np.nan, "", np.nan)
    for pos, (_, r) in enumerate(df.iterrows()):
        bt = r["datetime"].floor("15min")                # snap to the M15 grid
        i0 = idx_of.get(bt)
        if i0 is None or i0 + 1 >= n:
            miss += 1; out.append(BLANK); continue
        sgn = 1 if str(r["Type"]).upper().startswith("B") else -1
        entry = float(r["Entry Price"])
        buf_abs = entry * BUF / 100.0
        line = buyH1[i0] if sgn > 0 else sellH1[i0]
        if line is None or np.isnan(line):
            line = buyL[i0] if sgn > 0 else sellL[i0]
        if line is None or np.isnan(line):
            miss += 1; out.append(BLANK); continue
        vsl = line - sgn * buf_abs
        min_dist = entry * SLMIN / 100.0
        if abs(entry - vsl) < min_dist:
            vsl = entry - sgn * min_dist
        sl_dist = abs(entry - vsl)
        if sl_dist <= 0:
            miss += 1; out.append(BLANK); continue
        tp = entry + sgn * entry * float(tp_pcts[pos]) / 100.0

        exit_px = exit_rsn = exit_t = None; trailing = False
        for j in range(i0 + 1, n):
            # 1) stop / trail hit
            if (sgn > 0 and lo[j] <= vsl) or (sgn < 0 and hi[j] >= vsl):
                exit_px = vsl; exit_rsn = "TRAIL" if trailing else "SL"
                exit_t = ohlc["time"].iloc[j]; break
            # 2) TP cap hit
            if (sgn > 0 and hi[j] >= tp) or (sgn < 0 and lo[j] <= tp):
                exit_px = tp; exit_rsn = "TP"; exit_t = ohlc["time"].iloc[j]; break
            # 3) trail the H1 line up (one-way)
            ln = buyH1[j] if sgn > 0 else sellH1[j]
            if ln is not None and not np.isnan(ln):
                new_sl = ln - sgn * buf_abs
                if (sgn > 0 and new_sl > vsl) or (sgn < 0 and new_sl < vsl):
                    vsl = new_sl; trailing = True
            # 4) opposite H1 flip = exit
            if flipH1[j] == -sgn:
                exit_px = cl[j]; exit_rsn = "FLIP"; exit_t = ohlc["time"].iloc[j]; break
        if exit_px is None:
            miss += 1; out.append(BLANK); continue

        R = ((exit_px - entry) / sl_dist) * sgn
        out.append((round(float(exit_px), 2), exit_t, round(float(R), 4),
                    exit_rsn, 1 if R > 0 else 0))

    res = pd.DataFrame(out, columns=["_exit_px", "_exit_t", "R", "exit_reason", "_win"],
                       index=df.index)
    return res, miss


def main():
    print("=" * 60)
    print("  RELABEL TRADES — closed-loop (live HTF exit engine)")
    if CFG.filters.ratchet_tp_regime:
        print(f"  buffer {BUF}% | min-SL {SLMIN}% | TP cap: REGIME-ADAPTIVE {TP_BY_REGIME} "
              f"(fallback {TPCAP}%)")
    else:
        print(f"  buffer {BUF}% | min-SL {SLMIN}% | TP cap {TPCAP}% (flat -- ratchet_tp_regime=False)")
    print("=" * 60)
    df = load_entries()
    ohlc = load_ohlc()
    print(f"  Entries: {len(df):,} | {df['datetime'].min().date()} -> {df['datetime'].max().date()}")
    print(f"  OHLC   : {len(ohlc):,} bars | {ohlc['time'].min().date()} -> {ohlc['time'].max().date()}")

    if CFG.filters.ratchet_tp_regime:
        print("\n  Assigning entry-time regime via EXISTING production hmm_model.pkl (no refit)...")
        df = df.assign(regime=assign_regimes(df))
        print("  " + df["regime"].value_counts().to_string().replace("\n", "\n  "))
        tp_pcts = df["regime"].map(TP_BY_REGIME).fillna(TPCAP).to_numpy()
    else:
        tp_pcts = np.full(len(df), TPCAP)

    old_win = (df["Win"] == "✓").astype(int) if "Win" in df.columns else None
    res, miss = relabel(df, ohlc, tp_pcts)
    ok = res["_win"].notna()
    print(f"\n  Relabeled OK: {int(ok.sum()):,} | unmatched/skipped: {miss:,}")

    new_win = res["_win"]
    if old_win is not None:
        o = old_win[ok].mean() * 100
        n_ = new_win[ok].mean() * 100
        print(f"  Win rate  OLD label: {o:5.1f}%   NEW (live-exit): {n_:5.1f}%")
        changed = int((old_win[ok].values != new_win[ok].values).sum())
        print(f"  Labels changed: {changed:,} / {int(ok.sum()):,} "
              f"({100*changed/max(1,int(ok.sum())):.1f}%)")
    print(f"  Exit mix: {res.loc[ok, 'exit_reason'].value_counts().to_dict()}")
    print(f"  R: total {res['R'].sum():+.1f} | avg {res['R'].mean():+.4f}")

    # write back into the original schema (only outcome cols change)
    outdf = df.copy()
    m = ok.values
    outdf.loc[m, "Exit Price"] = res.loc[m, "_exit_px"].values
    outdf.loc[m, "Win"] = np.where(res.loc[m, "_win"].values == 1, "✓", "✗")
    mv = (outdf["Exit Price"] - outdf["Entry Price"]) * np.where(
        outdf["Type"].astype(str).str.upper().str.startswith("B"), 1, -1)
    if "$ Move" in outdf.columns:
        outdf.loc[m, "$ Move"] = mv[m].round(2)
    if "% Move" in outdf.columns:
        outdf.loc[m, "% Move"] = (mv[m] / outdf.loc[m, "Entry Price"] * 100).round(4)
    if "Close Date" in outdf.columns:
        outdf.loc[m, "Close Date"] = pd.to_datetime(res.loc[m, "_exit_t"]).dt.strftime("%Y-%m-%d").values
    if "Close Time (24h)" in outdf.columns:
        outdf.loc[m, "Close Time (24h)"] = pd.to_datetime(res.loc[m, "_exit_t"]).dt.strftime("%H:%M:%S").values
    if "Duration (min)" in outdf.columns:
        dur = (pd.to_datetime(res.loc[m, "_exit_t"]) - outdf.loc[m, "datetime"]).dt.total_seconds() / 60.0
        outdf.loc[m, "Duration (min)"] = dur.round(0).values
    outdf.loc[m, "R"] = res.loc[m, "R"].values
    outdf.loc[m, "exit_reason"] = res.loc[m, "exit_reason"].values
    # drop rows we could not relabel (keep the dataset clean / consistent -- "regime"
    # was only a working column for this script, not part of the original schema)
    outdf = outdf[m].drop(columns=["datetime", "regime"], errors="ignore").reset_index(drop=True)

    outdf.to_excel(OUT, index=False)
    res.assign(Type=df["Type"], entry=df["Entry Price"], dt=df["datetime"],
               regime=df["regime"] if "regime" in df.columns else "") \
       .to_csv(DIFF, index=False)
    print(f"\n  ✅ Saved: {OUT}")
    print(f"     diff : {DIFF}")
    print("  NEXT: set config.trades_file -> this file, run 3_Train_Models.bat, then WFO-validate.")


if __name__ == "__main__":
    main()
