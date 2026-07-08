"""
dd_brake.py — live multi-day drawdown brake (FAB-S3, Fable-5 audit 2026-07-07).

The backtest has an M3 %-drawdown brake (`--dd-brake`: dd>10% of peak → ½ size,
>20% → ¼, >30% → halt) but the LIVE bridge had NO equivalent — only the daily
9% SL halt + the daily peak-floor ratchet. A multi-day losing streak therefore
compounded at full 3%/trade indefinitely.

PER-ACCOUNT (2026-07-07 fix): the bridge trades a PRIMARY account plus mirror
SECONDARY accounts with wildly different balances (e.g. primary $1.1M demo,
secondaries $2k / $10k). A single global peak would treat a $2k account as being
in 99% drawdown from the $1.1M peak → halt → order rejects. So peak equity is
tracked PER account login (`mt5.account_info().login`), keyed in the state file.

Protective only — can only REDUCE size in drawdown, never increase → never blocks
a profitable trade (prime-directive safe). Config-gated by
`CFG.filters.enable_live_dd_brake` (default False).

State file: logs/dd_peak.json  ->  {"<login>": {"peak_equity": float, "updated": iso}}
"""
from __future__ import annotations
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from config import CFG

_STATE = Path(__file__).resolve().parent / "logs" / "dd_peak.json"


def _current_login() -> str:
    """Login of the currently-connected MT5 account (peak key). 'default' if
    MT5 unavailable — keeps the module import-safe off-terminal."""
    try:
        import MetaTrader5 as mt5
        info = mt5.account_info()
        if info is not None:
            return str(info.login)
    except Exception:
        pass
    return "default"


def _load() -> dict:
    if not _STATE.exists():
        return {}
    try:
        d = json.loads(_STATE.read_text(encoding="utf-8"))
        # migrate old flat schema {"peak_equity": x} → {"default": {...}}
        if "peak_equity" in d:
            d = {"default": {"peak_equity": d.get("peak_equity", 0.0),
                             "updated": d.get("updated", "")}}
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        return {}


def _save(d: dict) -> None:
    try:
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="ddpeak_", suffix=".json.tmp", dir=str(_STATE.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
        os.replace(tmp, _STATE)
    except Exception:
        pass  # sizing must never crash on a persist failure


def risk_scale(current_equity: float, account_id: str | None = None) -> float:
    """Lot-size multiplier ∈ {1.0, 0.5, 0.25, 0.0} from drawdown vs THIS
    account's persisted peak. Updates that account's peak on a new high.
    Returns 1.0 when brake disabled or peak not yet established."""
    if not bool(getattr(CFG.filters, "enable_live_dd_brake", False)):
        return 1.0
    try:
        eq = float(current_equity)
    except (TypeError, ValueError):
        return 1.0
    if eq <= 0:
        return 1.0
    key = str(account_id) if account_id is not None else _current_login()
    d = _load()
    rec = d.get(key, {})
    peak = float(rec.get("peak_equity", 0.0) or 0.0)
    if eq > peak:
        d[key] = {"peak_equity": round(eq, 2),
                  "updated": datetime.utcnow().isoformat(timespec="seconds") + "Z"}
        _save(d)
        return 1.0
    if peak <= 0:
        d[key] = {"peak_equity": round(eq, 2),
                  "updated": datetime.utcnow().isoformat(timespec="seconds") + "Z"}
        _save(d)
        return 1.0
    dd = (peak - eq) / peak
    t_half = float(getattr(CFG.filters, "dd_brake_half_pct", 10.0)) / 100.0
    t_qtr  = float(getattr(CFG.filters, "dd_brake_quarter_pct", 20.0)) / 100.0
    t_halt = float(getattr(CFG.filters, "dd_brake_halt_pct", 30.0)) / 100.0
    if dd > t_halt:
        return 0.0
    if dd > t_qtr:
        return 0.25
    if dd > t_half:
        return 0.50
    return 1.0


def status(current_equity: float | None = None, account_id: str | None = None) -> dict:
    key = str(account_id) if account_id is not None else _current_login()
    d = _load()
    peak = float(d.get(key, {}).get("peak_equity", 0.0) or 0.0)
    out = {"enabled": bool(getattr(CFG.filters, "enable_live_dd_brake", False)),
           "account": key, "peak_equity": peak, "current": current_equity}
    if current_equity and peak > 0:
        out["drawdown_pct"] = round(100.0 * max(0.0, (peak - current_equity) / peak), 2)
    return out
