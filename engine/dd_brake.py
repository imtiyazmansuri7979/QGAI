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

DEPOSIT/WITHDRAWAL-AWARE (2026-07-15 fix, Imtiyaz-reported): the brake compares
current equity to a persisted peak, but a DEPOSIT or WITHDRAWAL moves equity
without any trading gain/loss. A real case: TradeQuo peaked at ~$5917 equity,
the owner WITHDREW $814 of trading profit → equity fell to $5046, and the brake
wrongly read that as a 14.7% drawdown and halved the account's risk even though
there was ZERO trading loss (the account's lifetime trading result was +$814).
Fix: each sizing call reads the account's balance-operation deals
(`DEAL_TYPE_BALANCE` etc. — deposits/withdrawals) from MT5 history and shifts the
stored peak by the SAME amount (withdrawal ↓ peak, deposit ↑ peak), so only
genuine trading losses can ever move equity below the peak. Idempotent: each
balance deal is applied at most once, tracked by its ticket in the state file.

State file: logs/dd_peak.json  ->
  {"<login>": {"peak_equity": float, "updated": iso, "applied_balance_deals": [ticket,...]}}
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


def _connection_matches(expected_key: str) -> bool:
    """True only if MT5 is VERIFIABLY connected to the account `expected_key`
    right now. 2026-07-15 fix (Imtiyaz-reported): this bridge switches MT5's
    single connection between the primary and each secondary account every
    few seconds (multi-account replication + manual-trade management). Right
    after a fresh mt5.login() the terminal's internal history cache does not
    always settle instantly -- `history_deals_get()` can momentarily still
    reflect the PREVIOUS account. Blindly trusting that once corrupted
    TradeQuo's peak with what looks like the primary's own large balance
    deals (peak jumped ~$5053->$9519 with no real deposit -> false 47%
    "drawdown" -> risk scaled to x0.0 -> a real SELL replication was rejected
    by the broker, retcode 10014, invalid volume). Fail CLOSED: on any doubt,
    return False (skip applying balance ops this cycle) rather than risk
    attributing another account's deals to this one's peak -- a missed
    same-tick adjustment is safe (caught next genuinely-connected cycle); a
    wrong one corrupts the peak until manually reset."""
    try:
        import MetaTrader5 as mt5
        info = mt5.account_info()
        return info is not None and str(info.login) == str(expected_key)
    except Exception:
        return False


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


def _balance_ops() -> list[tuple[int, float]]:
    """[(ticket, profit)] for the CURRENTLY-CONNECTED account's non-trading
    balance operations (deposits +, withdrawals −, credits/corrections) from MT5
    deal history. Empty on any error — sizing must never crash. A 120-day rolling
    window bounds the query cost; a genuinely new deposit/withdrawal is always
    recent, and anything older is already baked into the historical peak."""
    try:
        import MetaTrader5 as mt5
        from datetime import timedelta
        date_from = datetime.utcnow() - timedelta(days=120)
        date_to   = datetime.utcnow() + timedelta(days=1)
        deals = mt5.history_deals_get(date_from, date_to)
        if not deals:
            return []
        bal_types = {getattr(mt5, "DEAL_TYPE_BALANCE", 2)}
        for extra in ("DEAL_TYPE_CREDIT", "DEAL_TYPE_CORRECTION", "DEAL_TYPE_BONUS", "DEAL_TYPE_CHARGE"):
            v = getattr(mt5, extra, None)
            if v is not None:
                bal_types.add(v)
        return [(int(dl.ticket), float(dl.profit)) for dl in deals if dl.type in bal_types]
    except Exception:
        return []


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def risk_scale(current_equity: float, account_id: str | None = None) -> float:
    """Lot-size multiplier ∈ {1.0, 0.5, 0.25, 0.0} from drawdown vs THIS
    account's persisted peak. Deposits/withdrawals shift the peak by the same
    amount (so they are NOT mistaken for trading drawdown); a new equity high
    advances the peak. Returns 1.0 when brake disabled or peak not established."""
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
    has_field = "applied_balance_deals" in rec
    applied = set(rec.get("applied_balance_deals", []))

    # Only trust balance-history if MT5 is verifiably connected to THIS
    # account right now (see _connection_matches docstring for why).
    ops = _balance_ops() if _connection_matches(key) else []

    if peak <= 0 or not has_field:
        # First establishment OR one-time migration of a pre-existing peak:
        # baseline ALL existing balance ops as "already accounted" so we never
        # retroactively subtract historical deposits/withdrawals. Peak starts at
        # the higher of any existing peak and current equity.
        peak = max(peak, eq)
        applied = {t for t, _ in ops}
    else:
        # Neutralise NEW balance operations since last check (idempotent by
        # ticket): a withdrawal (profit<0) lowers the peak by exactly the amount
        # withdrawn so it is NOT read as trading drawdown; a deposit (profit>0)
        # raises it. Only genuine trading losses now move equity below the peak.
        for t, p in ops:
            if t not in applied:
                peak = max(0.0, peak + p)
                applied.add(t)

    # New trading high → advance the peak.
    if eq > peak:
        peak = eq

    d[key] = {
        "peak_equity": round(peak, 2),
        "updated": _now_iso(),
        "applied_balance_deals": sorted(applied)[-500:],   # cap growth
    }
    _save(d)

    if peak <= 0:
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
