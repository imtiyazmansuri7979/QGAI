"""
build_signal_log.py — COMPLETE continuous signal log (full-history backtest + LIVE), with $ move.

Merges:
  1) a full-history backtest run  (backtest_signals*.csv = EVERY M15 candle BUY/SELL/SKIP +
     win_prob + regime + blocked_by ; backtest_trades*.csv = entry/exit + price_move + result)
  2) the LIVE log  (logs/signals_all.csv — real LIVE/MONITOR/BACKFILL signals with real
     outcome + real $ move from write_outcome)

Live rows OVERRIDE backtest rows for the same bar (live = the real record); the backtest fills
the rest of history + any gaps → one continuous record.

Output is written in the SAME column schema as signals_all.csv, to logs/signals_complete.csv,
so the dashboard Signal Log reads it directly (no parser change).

Usage:  python build_signal_log.py <backtest_results_folder>
   e.g. python build_signal_log.py ../backtest/results/fullhistory_regime   (regime-TP adopted)

Safety: if the backtest folder has no backtest_signals*.csv and
logs/signals_complete.csv already exists, this script preserves the existing
complete history instead of shrinking it to live-only rows.
"""
import sys, glob, os
import pandas as pd
from pathlib import Path

ENGINE   = Path(__file__).resolve().parent
LIVE_LOG = ENGINE / "logs" / "signals_all.csv"
OUT      = ENGINE / "logs" / "signals_complete.csv"

SCHEMA = ["bar_time","mode","signal","win_prob","state_prob","dir_prob","big_win_prob",
          "hmm_state","price","lot","sl","tp","atr20_pct","vol_spike","in_range_phase",
          "slot_wr","h4_bull_ob_dist","h4_bear_ob_dist","reason","outcome","equity","move"]


def _find(folder, pat):
    g = sorted(glob.glob(str(Path(folder) / pat)))
    return g[0] if g else None


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    frames = []

    # ── 1) full-history backtest (every bar) ────────────────────────────────
    sig_f = _find(folder, "backtest_signals*.csv")
    if not sig_f and OUT.exists() and not os.environ.get("QGAI_BUILD_SIGNAL_LOG_ALLOW_LIVE_ONLY"):
        live_rows = 0
        if LIVE_LOG.exists():
            try:
                live_rows = max(0, sum(1 for _ in LIVE_LOG.open("r", encoding="utf-8", errors="ignore")) - 1)
            except Exception:
                live_rows = 0
        try:
            existing_rows = max(0, sum(1 for _ in OUT.open("r", encoding="utf-8", errors="ignore")) - 1)
        except Exception:
            existing_rows = 0
        print("WARNING: no backtest_signals*.csv found in:")
        print(f"  {Path(folder).resolve()}")
        print(f"Preserving existing {OUT} ({existing_rows:,} rows).")
        print(f"Live-only rows available: {live_rows:,}. Set QGAI_BUILD_SIGNAL_LOG_ALLOW_LIVE_ONLY=1 to overwrite intentionally.")
        return
    if sig_f:
        sig = pd.read_csv(sig_f)
        sig["bar_time"] = pd.to_datetime(sig["bar_time"], errors="coerce")
        sig = sig.dropna(subset=["bar_time"]).sort_values("bar_time").reset_index(drop=True)
        bt = pd.DataFrame({c: "" for c in SCHEMA}, index=range(len(sig)))
        bt["bar_time"] = sig["bar_time"].astype(str).values
        bt["mode"]     = "BACKTEST"
        for c in ["signal", "win_prob", "state_prob", "dir_prob", "big_win_prob",
                  "hmm_state", "in_range_phase", "reason"]:
            if c in sig.columns:
                bt[c] = sig[c].astype(str).values

        trd_f = _find(folder, "backtest_trades*.csv")
        if trd_f:
            t = pd.read_csv(trd_f)
            t = t.dropna(subset=["entry_time"])
            t["bar_time"] = pd.to_datetime(t["entry_time"], errors="coerce").astype(str)
            t["outcome"]  = (pd.to_numeric(t["r_achieved"], errors="coerce") > 0).map({True: "WIN", False: "LOSS"})
            t["price"]    = pd.to_numeric(t["entry_price"], errors="coerce").round(2)
            t["move"]     = pd.to_numeric(t.get("price_move", 0), errors="coerce").round(2)
            tt = t[["bar_time", "outcome", "price", "move"]].drop_duplicates("bar_time").set_index("bar_time")
            for i in range(len(bt)):
                k = bt.at[i, "bar_time"]
                if k in tt.index:
                    # str() — bt columns are string-schema; newer pandas rejects
                    # assigning a float into a StringDtype column via .at
                    bt.at[i, "outcome"] = str(tt.at[k, "outcome"])
                    bt.at[i, "price"]   = str(tt.at[k, "price"])
                    bt.at[i, "move"]    = str(tt.at[k, "move"])
        frames.append(bt[SCHEMA])
        print(f"  backtest: {len(bt):,} bars  (from {sig_f})")

    # ── 2) LIVE log (real signals + real outcome/move) ──────────────────────
    if LIVE_LOG.exists():
        live = pd.read_csv(LIVE_LOG, dtype=str).fillna("")
        if "mode" in live.columns:
            live = live[live["mode"].isin(["LIVE", "MONITOR", "BACKFILL", "REPLAY"])]
        for c in SCHEMA:
            if c not in live.columns:
                live[c] = ""
        frames.append(live[SCHEMA])
        print(f"  live    : {len(live):,} rows  (from {LIVE_LOG})")

    if not frames:
        print("nothing to merge"); return

    allrows = pd.concat(frames, ignore_index=True)
    allrows = allrows[allrows["bar_time"].astype(str).str.startswith("20")]
    # live overrides backtest on the same bar: live last -> keep='last'
    allrows["_pri"] = (allrows["mode"] != "BACKTEST").astype(int)
    allrows = (allrows.sort_values(["bar_time", "_pri"])
                      .drop_duplicates("bar_time", keep="last")
                      .sort_values("bar_time")
                      .drop(columns=["_pri"]))
    allrows[SCHEMA].to_csv(OUT, index=False)
    _ex = (allrows["outcome"].isin(["WIN", "LOSS"])).sum()
    print(f"OK  {OUT}")
    print(f"    {len(allrows):,} bars | {allrows['bar_time'].min()} -> {allrows['bar_time'].max()} | {_ex:,} with outcome/move")


if __name__ == "__main__":
    main()
