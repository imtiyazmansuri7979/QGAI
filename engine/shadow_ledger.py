"""
shadow_ledger.py — Forward PAPER-TRADE ledger from the bridge's REAL signals.
────────────────────────────────────────────────────────────────────────────
Reads the signals the live bridge actually produced (logs/signals_all.csv) and,
for every BUY/SELL signal (a "would-trade"), simulates the trade forward on the
M15 OHLC using the SAME live exit rules (HTF-H1 stop + flip, ratchet buffer,
far TP). Writes logs/shadow_trades.csv — one row per signal, WFO-style:

  entry_time, entry_price, direction, win_prob, hmm_state,
  exit_time, exit_price, exit_reason, R, pnl_usd, pnl_pct, real_executed

  real_executed = 1 if the signal was in LIVE mode (a real order was placed),
                  0 if MONITOR/shadow (paper only).

Runs OUTSIDE the live bridge → ZERO risk to trading. Re-run any time (or on a
schedule); it rebuilds the full ledger from the current signal log.

Usage:  python shadow_ledger.py
"""
import sys, io, csv
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import pandas as pd
from pathlib import Path

from trend_signal import compute_trend
try:
    from config import CFG
    F = CFG.filters
    BUF      = float(getattr(F, "ratchet_buf_pct", 0.20))
    SLMIN    = float(getattr(F, "ratchet_sl_min_pct", 0.18))
    TPCAP    = float(getattr(F, "ratchet_tp_cap_pct", 10.0))
    HTF_SL   = bool(getattr(F, "ratchet_htf_sl", True))
    HTF_FLIP = bool(getattr(F, "ratchet_htf_flip", True))
    RISK     = float(getattr(F, "risk_pct", 3.0))
    LOGS     = Path(CFG.paths.logs_dir)
except Exception:
    BUF, SLMIN, TPCAP, HTF_SL, HTF_FLIP, RISK = 0.20, 0.18, 10.0, True, True, 3.0
    LOGS = Path(__file__).resolve().parent / "logs"

ENGINE  = Path(__file__).resolve().parent
EQUITY  = 10000.0          # paper account for $/% figures (each trade sized at RISK% of this)
RISK_USD = EQUITY * RISK / 100.0

# OHLC source (merged M15)
_cands = [ENGINE.parent / "data" / "merged" / "ohlc_merged.csv",
          LOGS.parent / "merged" / "ohlc_merged.csv",
          ENGINE / "ohlc_merged.csv"]
OHLC_CSV = next((p for p in _cands if p.exists()), _cands[0])


def _load_signals(sig_path):
    """Read signals_all.csv while tolerating the old missing-`move` header."""
    with open(sig_path, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        return pd.DataFrame()

    header = rows[0]
    original_width = len(header)
    move_insert_at = None
    if "trading_equity" not in header:
        header.append("trading_equity")
    if "move" not in header:
        move_insert_at = header.index("trading_equity") if "trading_equity" in header else len(header)
        header.insert(move_insert_at, "move")

    expected = len(header)
    fixed = []
    repaired = 0
    for row in rows[1:]:
        if move_insert_at is not None and len(row) == original_width:
            row = row[:move_insert_at] + [""] + row[move_insert_at:]
        if len(row) != expected:
            repaired += 1
        while len(row) < expected:
            row.append("")
        if len(row) > expected:
            row = row[:expected]
        fixed.append(row)

    if repaired:
        print(f"Repaired {repaired} signal-log row(s) with legacy column counts.")
    return pd.DataFrame(fixed, columns=header)


def _load_ohlc():
    df = pd.read_csv(OHLC_CSV)
    tcol = "time" if "time" in df.columns else ("datetime" if "datetime" in df.columns else df.columns[0])
    df = df.rename(columns={tcol: "time"})
    df["time"] = pd.to_datetime(df["time"])
    df = df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    return df[["time", "open", "high", "low", "close"]]


def _htf_lines(ohlc):
    """Map each M15 bar to the last CLOSED H1 ratchet line + flip (no lookahead)."""
    h1 = (ohlc.set_index("time")
          .resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"})
          .dropna().reset_index())
    h1t = compute_trend(h1, 2, "SMMA", ratchet=True)
    h1t["vf"] = h1t["time"] + pd.Timedelta(hours=1)
    m = pd.merge_asof(ohlc[["time"]], h1t[["vf", "buy_line", "sell_line", "flip"]],
                      left_on="time", right_on="vf", direction="backward")
    return m["buy_line"].to_numpy(), m["sell_line"].to_numpy(), m["flip"].to_numpy()


def main():
    sig_path = LOGS / "signals_all.csv"
    if not sig_path.exists():
        print(f"No signal log yet: {sig_path}")
        return
    sig = _load_signals(sig_path)
    sig["bar_time"] = pd.to_datetime(sig.get("bar_time"), errors="coerce")
    sig = sig.dropna(subset=["bar_time"])
    would = sig[sig["signal"].isin(["BUY", "SELL"])].copy()
    if would.empty:
        print("No BUY/SELL signals in the log yet — nothing to paper-trade.")
        return

    ohlc = _load_ohlc()
    n = len(ohlc)
    idx_of = {t: i for i, t in enumerate(ohlc["time"])}
    hi = ohlc["high"].to_numpy(); lo = ohlc["low"].to_numpy(); cl = ohlc["close"].to_numpy()

    m15 = compute_trend(ohlc, 2, "SMMA", ratchet=True)
    buyL = m15["buy_line"].to_numpy(); sellL = m15["sell_line"].to_numpy(); flipM = m15["flip"].to_numpy()
    if HTF_SL or HTF_FLIP:
        buyH1, sellH1, flipH1 = _htf_lines(ohlc)
    else:
        buyH1, sellH1, flipH1 = buyL, sellL, flipM

    rows = []
    for _, s in would.iterrows():
        bt = s["bar_time"]
        i0 = idx_of.get(bt)
        if i0 is None or i0 + 1 >= n:
            continue
        sgn = 1 if s["signal"] == "BUY" else -1
        entry = float(s.get("price") or cl[i0]) or cl[i0]
        buf_abs = entry * BUF / 100.0

        # initial stop on the HTF (H1) line if it agrees, else M15 line
        line = (buyH1[i0] if sgn > 0 else sellH1[i0]) if HTF_SL else (buyL[i0] if sgn > 0 else sellL[i0])
        if line is None or np.isnan(line):
            line = (buyL[i0] if sgn > 0 else sellL[i0])
        if line is None or np.isnan(line):
            continue
        vsl = line - sgn * buf_abs
        # enforce a minimum stop distance
        min_dist = entry * SLMIN / 100.0
        if abs(entry - vsl) < min_dist:
            vsl = entry - sgn * min_dist
        sl_dist = abs(entry - vsl)
        if sl_dist <= 0:
            continue
        tp = entry + sgn * entry * TPCAP / 100.0

        exit_px = exit_rsn = None
        exit_t = None
        trailing = False
        for j in range(i0 + 1, n):
            # intrabar stop
            if (sgn > 0 and lo[j] <= vsl) or (sgn < 0 and hi[j] >= vsl):
                exit_px = vsl; exit_rsn = "TRAIL" if trailing else "SL"; exit_t = ohlc["time"].iloc[j]; break
            # intrabar TP (far)
            if (sgn > 0 and hi[j] >= tp) or (sgn < 0 and lo[j] <= tp):
                exit_px = tp; exit_rsn = "TP"; exit_t = ohlc["time"].iloc[j]; break
            # on close: trail the stop toward the (H1) line, one-way
            ln = (buyH1[j] if sgn > 0 else sellH1[j]) if HTF_SL else (buyL[j] if sgn > 0 else sellL[j])
            if ln is not None and not np.isnan(ln):
                new_sl = ln - sgn * buf_abs
                if (sgn > 0 and new_sl > vsl) or (sgn < 0 and new_sl < vsl):
                    vsl = new_sl; trailing = True
            # flip exit on the (H1) flip
            fl = (flipH1[j] if HTF_FLIP else flipM[j])
            if fl == -sgn:
                exit_px = cl[j]; exit_rsn = "FLIP"; exit_t = ohlc["time"].iloc[j]; break
        if exit_px is None:   # still open at end of data
            continue

        R = ((exit_px - entry) / sl_dist) * sgn
        mode = str(s.get("mode", "")).lower()
        rows.append({
            "entry_time": bt, "entry_price": round(entry, 2), "direction": s["signal"],
            "win_prob": round(float(s.get("win_prob", 0) or 0), 4),
            "hmm_state": s.get("hmm_state", ""),
            "exit_time": exit_t, "exit_price": round(float(exit_px), 2),
            "exit_reason": exit_rsn, "R": round(R, 3),
            "pnl_usd": round(R * RISK_USD, 2), "pnl_pct": round(R * RISK, 3),
            "real_executed": 1 if mode == "live" else 0,
        })

    if not rows:
        print("No completed paper trades (signals too recent or no OHLC match).")
        return
    out = pd.DataFrame(rows)
    out_path = LOGS / "shadow_trades.csv"
    out.to_csv(out_path, index=False)

    # summary
    tot_r = out["R"].sum(); tot_usd = out["pnl_usd"].sum()
    wins = (out["R"] > 0).sum(); wr = wins / len(out) * 100
    real = int(out["real_executed"].sum())
    print("=" * 60)
    print("  SHADOW PAPER-TRADE LEDGER")
    print("=" * 60)
    print(f"  signals paper-traded : {len(out)}  (real={real}, shadow={len(out)-real})")
    print(f"  win rate             : {wr:.1f}%")
    print(f"  total R              : {tot_r:+.1f}R")
    print(f"  total P&L            : ${tot_usd:+,.0f}  ({tot_r*RISK:+.1f}% of ${EQUITY:,.0f}/trade base)")
    print(f"  exit mix             : {out['exit_reason'].value_counts().to_dict()}")
    print(f"  saved                : {out_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
