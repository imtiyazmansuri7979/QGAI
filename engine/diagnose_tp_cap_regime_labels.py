"""
diagnose_tp_cap_regime_labels.py -- CHEAP diagnostic (no retrain), Fable-5
recommended step before fixing the flat-vs-regime-adaptive TP-cap label bug
(2026-07-13 night).

For every historical trade entry used to train the win-prob models, this
re-simulates the exit TWICE:
  (a) FLAT cap   -- same as the current relabel_trades.py (TPCAP=1.00% for all
                    regimes, the labels the models are ACTUALLY trained on today)
  (b) REGIME cap -- Ranging 2.0% / Trending 1.0% / Volatile 0.8% (matches the
                    live bridge + backtest_replay.py since 2026-06-27), using
                    each trade's entry-time regime from the EXISTING production
                    hmm_model.pkl (no refit -- reuses the same classifier live
                    already uses, per Fable-5's recommendation).

Reports label-flip % and delta-R per regime -- the number needed to decide
whether the full relabel + retrain + WFO cycle (expensive) is worth running.

Read-only. No training. No live/demo impact. Pure pandas + OHLC/ADX replay.
"""
import argparse
import numpy as np, pandas as pd
from pathlib import Path

from analyze_capture import load_ohlc, htf_lines, BUF, SLMIN
from trend_signal import compute_trend
from features import load_adx
from hmm_model import MarketStateHMM, STATE_NAMES
from config import CFG

TP_FLAT = 1.00
TP_BY_REGIME = {"Ranging": 2.0, "Trending": 1.0, "Volatile": 0.8}

XLSX = Path(CFG.paths.trades_file)
ENGINE = Path(__file__).resolve().parent


def load_entries():
    df = pd.read_excel(XLSX)
    ds = df["Open Date"].astype(str) + " " + df["Open Time (24h)"].astype(str)
    df["datetime"] = pd.to_datetime(ds, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    return df[df["datetime"].notna()].reset_index(drop=True)


def assign_regimes(entries, adx_df):
    hmm = MarketStateHMM()
    hmm_path = str(Path(CFG.paths.models_dir) / "hmm_model.pkl")
    hmm.load(hmm_path)
    states = hmm.predict_batch(adx_df)   # aligned to adx_df rows
    times = adx_df["datetime"].values.astype("datetime64[ns]")
    regimes = []
    for t in entries["datetime"]:
        t64 = np.datetime64(t)
        i = int(np.searchsorted(times, t64, side="right")) - 1   # last CLOSED bar, no lookahead
        regimes.append(STATE_NAMES.get(int(states[i]), "Ranging") if i >= 0 else "Ranging")
    return regimes


def simulate(entries, ohlc, tp_pcts):
    """tp_pcts: one TP% per trade, aligned to entries (by position)."""
    n = len(ohlc)
    idx_of = {t: i for i, t in enumerate(ohlc["time"])}
    hi = ohlc["high"].to_numpy(); lo = ohlc["low"].to_numpy(); cl = ohlc["close"].to_numpy()
    buyH1, sellH1, flipH1 = htf_lines(ohlc)
    m15 = compute_trend(ohlc, 2, "SMMA", ratchet=True)
    buyL = m15["buy_line"].to_numpy(); sellL = m15["sell_line"].to_numpy()

    out = []
    for (_, r), tp_pct in zip(entries.iterrows(), tp_pcts):
        bt = r["datetime"].floor("15min")
        i0 = idx_of.get(bt)
        if i0 is None or i0 + 1 >= n:
            out.append((np.nan, "", np.nan)); continue
        sgn = 1 if str(r["Type"]).upper().startswith("B") else -1
        entry = float(r["Entry Price"])
        buf_abs = entry * BUF / 100.0
        line = buyH1[i0] if sgn > 0 else sellH1[i0]
        if line is None or np.isnan(line):
            line = buyL[i0] if sgn > 0 else sellL[i0]
        if line is None or np.isnan(line):
            out.append((np.nan, "", np.nan)); continue
        vsl = line - sgn * buf_abs
        min_dist = entry * SLMIN / 100.0
        if abs(entry - vsl) < min_dist:
            vsl = entry - sgn * min_dist
        sl_dist = abs(entry - vsl)
        if sl_dist <= 0:
            out.append((np.nan, "", np.nan)); continue
        tp = entry + sgn * entry * float(tp_pct) / 100.0

        exit_px = exit_rsn = None; trailing = False
        for j in range(i0 + 1, n):
            if (sgn > 0 and lo[j] <= vsl) or (sgn < 0 and hi[j] >= vsl):
                exit_px = vsl; exit_rsn = "TRAIL" if trailing else "SL"; break
            if (sgn > 0 and hi[j] >= tp) or (sgn < 0 and lo[j] <= tp):
                exit_px = tp; exit_rsn = "TP"; break
            ln = buyH1[j] if sgn > 0 else sellH1[j]
            if ln is not None and not np.isnan(ln):
                new_sl = ln - sgn * buf_abs
                if (sgn > 0 and new_sl > vsl) or (sgn < 0 and new_sl < vsl):
                    vsl = new_sl; trailing = True
            if flipH1[j] == -sgn:
                exit_px = cl[j]; exit_rsn = "FLIP"; break
        if exit_px is None:
            out.append((np.nan, "", np.nan)); continue
        R = ((exit_px - entry) / sl_dist) * sgn
        out.append((round(float(R), 4), exit_rsn, 1 if R > 0 else 0))
    return pd.DataFrame(out, columns=["R", "exit_reason", "win"], index=entries.index)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    print("=" * 64)
    print("TP-CAP REGIME LABEL DIAGNOSTIC (cheap, no retrain)")
    print("=" * 64)
    entries = load_entries()
    ohlc = load_ohlc()
    adx_df = load_adx(CFG.paths.adx_file)
    print(f"Entries: {len(entries):,} | {entries['datetime'].min().date()} -> {entries['datetime'].max().date()}")

    print("\nAssigning entry-time regime via EXISTING production hmm_model.pkl (no refit)...")
    entries = entries.assign(regime=assign_regimes(entries, adx_df))
    print(entries["regime"].value_counts().to_string())

    print("\nSimulating FLAT cap (1.00% for all -- current relabel_trades.py behaviour)...")
    flat = simulate(entries, ohlc, np.full(len(entries), TP_FLAT))

    print("Simulating REGIME cap (Ranging 2.0 / Trending 1.0 / Volatile 0.8 -- matches live)...")
    regime_tp = entries["regime"].map(TP_BY_REGIME).fillna(TP_FLAT).to_numpy()
    regime = simulate(entries, ohlc, regime_tp)

    det = entries[["datetime", "Type", "regime"]].copy()
    det["flat_win"] = flat["win"]; det["flat_R"] = flat["R"]; det["flat_exit"] = flat["exit_reason"]
    det["regime_win"] = regime["win"]; det["regime_R"] = regime["R"]; det["regime_exit"] = regime["exit_reason"]
    ok = det["flat_win"].notna() & det["regime_win"].notna()
    det = det[ok].copy()
    det["flipped"] = det["flat_win"] != det["regime_win"]
    det["delta_R"] = det["regime_R"] - det["flat_R"]

    out_dir = Path(args.out_dir) if args.out_dir else (
        ENGINE.parent / "backtest" / "results" / "tp_cap_regime_diagnostic")
    out_dir.mkdir(parents=True, exist_ok=True)
    det.to_csv(out_dir / "tp_cap_diagnostic_detail.csv", index=False)

    lines = []
    lines.append("=" * 64)
    lines.append("TP-CAP REGIME LABEL DIAGNOSTIC")
    lines.append(f"Entries simulated OK: {len(det):,} / {len(entries):,}")
    lines.append("-" * 64)
    total_flip = int(det["flipped"].sum())
    lines.append(f"TOTAL label flips (Win<->Loss): {total_flip:,} / {len(det):,} "
                  f"({100 * total_flip / len(det):.2f}%)")
    lines.append(f"TOTAL delta-R (regime - flat)  : {det['delta_R'].sum():+.1f}R")
    lines.append("-" * 64)
    lines.append("BY REGIME:")
    for reg, g in det.groupby("regime"):
        n = len(g); flips = int(g["flipped"].sum())
        w2l = int(((g["flat_win"] == 1) & (g["regime_win"] == 0)).sum())
        l2w = int(((g["flat_win"] == 0) & (g["regime_win"] == 1)).sum())
        lines.append(f"  {reg:<10} n={n:5d} | flips={flips:4d} ({100 * flips / n:5.2f}%) | "
                      f"Win->Loss={w2l:4d} Loss->Win={l2w:4d} | delta-R={g['delta_R'].sum():+8.1f}")
    lines.append("-" * 64)
    lines.append("EXIT-REASON MIGRATION (flat -> regime), top moves by regime:")
    for reg, g in det.groupby("regime"):
        mig = g.groupby(["flat_exit", "regime_exit"]).size().sort_values(ascending=False)
        lines.append(f"  {reg}:")
        for (fe, re_), c in mig.head(6).items():
            lines.append(f"    {fe:>6} -> {re_:<6} : {c}")
    lines.append("=" * 64)
    lines.append("GATE (Fable-5): full relabel+retrain+WFO only justified if TOTAL flips")
    lines.append("> ~3% of rows, OR any single regime's flips > ~5-7%. Otherwise the flat-")
    lines.append("cap label bug is real but too small to change model behaviour materially.")
    lines.append("=" * 64)
    report = "\n".join(lines)
    print("\n" + report)
    (out_dir / "tp_cap_diagnostic_report.txt").write_text(report, encoding="utf-8")

    summary = det.groupby("regime").agg(
        n=("flipped", "size"), flips=("flipped", "sum"), delta_R=("delta_R", "sum")
    ).reset_index()
    summary["flip_pct"] = 100 * summary["flips"] / summary["n"]
    summary.to_csv(out_dir / "tp_cap_diagnostic_summary.csv", index=False)
    print(f"\nSaved: {out_dir / 'tp_cap_diagnostic_detail.csv'}")
    print(f"Saved: {out_dir / 'tp_cap_diagnostic_summary.csv'}")
    print(f"Saved: {out_dir / 'tp_cap_diagnostic_report.txt'}")


if __name__ == "__main__":
    main()
