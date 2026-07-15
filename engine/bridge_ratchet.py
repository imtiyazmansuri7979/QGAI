"""
bridge_ratchet.py — QUANT GOLD AI v2
RATCHET exit engine (EA-style): live trend-line provider.

Wraps trend_signal.py (20SMA TrendSignals Hybrid port, Period=2 SMMA)
for the live bridge: fetches closed M15 bars from MT5, computes the
trend state + ratchet lines, and caches per closed bar.

Used by bridge_core when RATCHET_EXIT is enabled:
  * entry SL  = line ∓ buffer            (instead of ATR)
  * trailing  = line follows one-way     (every closed bar)
  * exit      = price crosses line, or opposite flip
"""
import MetaTrader5 as mt5
import pandas as pd

from bridge_constants import log, SYMBOL
from trend_signal import compute_trend
try:
    from config import CFG
except Exception:
    CFG = None

TS_PERIOD = 2        # indicator settings (validated)
TS_METHOD = "SMMA"
_BARS     = 600      # history depth for stable SMMA + ratchet state

# 2026-07-15 (Imtiyaz): caches are now PER-SYMBOL. The slave manual-trade manager
# (bridge_manual) calls these while connected to a SECONDARY account whose symbol
# (e.g. "XAUUSDs") differs from the primary's SYMBOL ("XAUUSD"). A single shared
# cache would return the wrong symbol's line; and the old code hard-coded SYMBOL in
# copy_rates so a slave whose symbol ≠ primary got "copy_rates failed — no state"
# every cycle → its vSL never ratcheted (only the wide floor protected it).
_cache     = {}   # symbol -> {"bar_time", "state"}
_htf_cache = {}   # symbol -> {"bar_time", "state", "tf"}


def get_state(symbol: str | None = None) -> dict | None:
    """
    Trend state of the LAST CLOSED M15 bar:
      {bar_time, trend(+1/-1), buy_line, sell_line, flip(+1/-1/0)}
    Cached per (symbol, bar) — recomputes only when a new bar closes.
    `symbol` defaults to the primary SYMBOL; pass a secondary account's symbol
    when managing that account (must be connected to it). Returns None if MT5
    data unavailable (caller falls back to ATR).
    """
    sym = symbol or SYMBOL
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, _BARS)
    if rates is None or len(rates) < 50:
        log.warning(f"⚡ ratchet[{sym}]: copy_rates failed — no state")
        return None

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    # index 0..n-2 are closed bars; the LAST row is the forming bar → drop it
    closed = df.iloc[:-1][["time", "open", "high", "low", "close"]].reset_index(drop=True)
    last_t = closed["time"].iloc[-1]

    c = _cache.get(sym)
    if c and c["bar_time"] == last_t and c["state"] is not None:
        return c["state"]

    t = compute_trend(closed, TS_PERIOD, TS_METHOD)
    r = t.iloc[-1]
    state = {
        "bar_time":  last_t,
        "trend":     int(r["trend"]),
        "buy_line":  None if pd.isna(r["buy_line"])  else float(r["buy_line"]),
        "sell_line": None if pd.isna(r["sell_line"]) else float(r["sell_line"]),
        "flip":      int(r["flip"]),
    }
    _cache[sym] = {"bar_time": last_t, "state": state}
    return state


def line_for(direction: str, state: dict | None) -> float | None:
    """Active ratchet line for a trade direction, or None if not available
    (e.g. trend currently against the trade — no line on that side)."""
    if not state:
        return None
    return state.get("buy_line") if direction == "BUY" else state.get("sell_line")


# ── HTF (higher-timeframe) ratchet state ──────────────────────────────────
_TF_MAP    = {"M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}


def get_htf_state(tf_str: str = "H1", symbol: str | None = None) -> dict | None:
    """Trend state of the LAST CLOSED bar on a HIGHER timeframe (M30/H1/H4).
    Same shape as get_state(): {bar_time, trend, buy_line, sell_line, flip}.
    Cached per (symbol, HTF bar). `symbol` defaults to the primary SYMBOL; pass a
    secondary account's symbol when managing that account (must be connected to
    it). Returns None if the timeframe is unknown or MT5 data is unavailable
    (caller falls back to the M15 line)."""
    tf = _TF_MAP.get(str(tf_str).upper())
    if tf is None:
        return None
    sym = symbol or SYMBOL
    rates = mt5.copy_rates_from_pos(sym, tf, 0, _BARS)
    if rates is None or len(rates) < 50:
        log.warning(f"⚡ ratchet HTF({tf_str})[{sym}]: copy_rates failed — no state")
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    # 2026-06-30 (Anisa): forming-bar mode → INCLUDE the current (not-yet-closed) HTF bar so
    # the line matches the chart indicator's live "SELL Line" value and the vSL trails the LIVE
    # line WITHOUT the hourly lag (less profit give-back). Default OFF = last-closed bar only.
    _forming = bool(getattr(getattr(CFG, "filters", None), "ratchet_htf_forming", False)) if CFG else False
    if _forming:
        closed = df[["time", "open", "high", "low", "close"]].reset_index(drop=True)          # incl. forming (live close)
    else:
        closed = df.iloc[:-1][["time", "open", "high", "low", "close"]].reset_index(drop=True) # last closed only
    last_t = closed["time"].iloc[-1]
    # in forming mode the last bar's close moves live → skip the per-bar cache (recompute).
    c = _htf_cache.get(sym)
    if (not _forming and c and c["bar_time"] == last_t and c["tf"] == tf_str
            and c["state"] is not None):
        return c["state"]
    t = compute_trend(closed, TS_PERIOD, TS_METHOD)
    r = t.iloc[-1]
    state = {
        "bar_time":  last_t,
        "trend":     int(r["trend"]),
        "buy_line":  None if pd.isna(r["buy_line"])  else float(r["buy_line"]),
        "sell_line": None if pd.isna(r["sell_line"]) else float(r["sell_line"]),
        "flip":      int(r["flip"]),
    }
    _htf_cache[sym] = {"bar_time": last_t, "state": state, "tf": tf_str}
    return state
