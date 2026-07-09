"""
vsl_persist.py — persist per-ticket VirtualTrade state across bridge restarts.

Fix for FAB-S4 (Fable-5 audit 2026-07-07): the recovery regex in
bridge_core.recover_open_trades() looked for VSL=/SL= tags in the position
COMMENT but the comment format is now "QuantEdge AI | {phase}" — no tags.
Fallback reconstructed vSL from broker_sl (= vSL_dist × 3), which put vSL
back at ENTRY LEVEL, forfeiting any trailing gain on every restart.

This module writes vSL state to logs/vsl_state.json after every mutation
and reads it on recovery. Broker-SL fallback stays as last-resort only.

State schema (per ticket):
  {"virtual_sl": float, "sl_dist": float, "direction": "BUY"|"SELL",
   "entry": float, "breakeven": bool, "trailing": bool, "updated": iso8601}

Small file, atomic write (tmp + rename) to survive mid-write crashes.
"""
from __future__ import annotations
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

_STATE_FILE = Path(__file__).resolve().parent / "logs" / "vsl_state.json"


def _load() -> dict[str, dict[str, Any]]:
    if not _STATE_FILE.exists():
        return {}
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _atomic_write(payload: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="vsl_", suffix=".json.tmp",
                                dir=str(_STATE_FILE.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, _STATE_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save(ticket: int, virtual_sl: float, sl_dist: float, direction: str,
         entry: float, breakeven: bool = False, trailing: bool = False) -> None:
    """Write/update state for one ticket. Safe to call on every trail update."""
    st = _load()
    st[str(ticket)] = {
        "virtual_sl": round(float(virtual_sl), 4),
        "sl_dist":    round(float(sl_dist), 4),
        "direction":  str(direction).upper(),
        "entry":      round(float(entry), 4),
        "breakeven":  bool(breakeven),
        "trailing":   bool(trailing),
        "updated":    datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    _atomic_write(st)


def get(ticket: int) -> dict | None:
    """Return persisted state for one ticket, or None if not tracked."""
    st = _load()
    return st.get(str(ticket))


def remove(ticket: int) -> None:
    """Drop a closed ticket. Idempotent."""
    st = _load()
    if str(ticket) in st:
        del st[str(ticket)]
        _atomic_write(st)


def prune_stale(alive_tickets: set[int]) -> int:
    """Drop any tickets not in the alive set (broker no longer holds them).
    Returns count removed. Call this once at startup after position sync."""
    st = _load()
    alive_str = {str(t) for t in alive_tickets}
    stale = [t for t in list(st.keys()) if t not in alive_str]
    for t in stale:
        del st[t]
    if stale:
        _atomic_write(st)
    return len(stale)


def all_tickets() -> dict[str, dict]:
    """Full snapshot — for debugging / dashboard."""
    return _load()
