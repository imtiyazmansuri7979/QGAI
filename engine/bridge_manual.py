"""
bridge_manual.py - L13 MANUAL-TRADE MANAGER (config-gated, default OFF).

CUT-BASED PROTECTION (2026-07-17, Imtiyaz v2):
Treats ALL your manual XAUUSD trades (magic 0; the bot uses 202600) as ONE combined
position. If total lot exceeds the risk-equivalent allowed_lot, the EXCESS is
partial-closed IMMEDIATELY (no opposite-side hedge). Remaining allowed lot is
managed with one ratcheting virtual SL + floor + TP.

  - allowed_lot = (equity * manual_risk_pct%) / (contract * price * manual_sl_pct%)
  - excess = max(0, total_lot - allowed_lot) -> partial-close from the manual positions
  - ratchet ONE VIRTUAL vSL up the 2-SMMA line (HTF/H1). vSL is NOT placed on the
    broker (don't expose the stop to stop-hunting). Bot CLOSES on virtual breach.
  - target TP (manual_target_tp_pct) on the combined avg -> close ALL.
  - any STALE hedge positions (magic 202699) from old logic are cleaned up automatically.

WARNING: places REAL close orders. Master switch defaults False. DEMO-TEST. Respects TEST_MODE.
"""
import json
import re
from pathlib import Path

import MetaTrader5 as mt5
from datetime import datetime
from bridge_constants import log, CFG, SYMBOL, TEST_MODE

_managed = {}   # account:symbol -> {"vsl": float|None}  (ONE combined state per account+symbol)
_STATE_FILE = Path(__file__).resolve().parent / "logs" / "manual_vsl_state.json"
_BRIDGE_LOG = Path(__file__).resolve().parent / "logs" / "bridge.log"


def _f(name, default):
    return getattr(CFG.filters, name, default)

def _enabled():
    return bool(_f("manual_manager_enabled", False))

def _hedge_magic():
    return int(_f("manual_hedge_magic", 202699))

def _contract_size(sym):
    si = mt5.symbol_info(sym)
    cs = float(getattr(si, "trade_contract_size", 0) or 0) if si else 0
    return cs if cs > 0 else 100.0

def _positions(magic, sym):
    return [p for p in (mt5.positions_get(symbol=sym) or []) if p.magic == magic]

def _managed_key(sym):
    try:
        info = mt5.account_info()
        login = getattr(info, "login", "unknown") if info else "unknown"
    except Exception:
        login = "unknown"
    return f"{login}:{sym}"

def _read_state():
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text(encoding="utf-8") or "{}")
    except Exception as e:
        log.warning(f"manual-vsl state read failed: {e}")
    return {}

def _write_state(data):
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STATE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(_STATE_FILE)
    except Exception as e:
        log.warning(f"manual-vsl state write failed: {e}")

def _save_state(key, sym, is_buy, avg_entry, volume, vsl):
    if vsl is None:
        return
    data = _read_state()
    data[key] = {
        "symbol": sym,
        "side": "BUY" if is_buy else "SELL",
        "avg_entry": round(float(avg_entry), 5),
        "volume": round(float(volume), 4),
        "vsl": round(float(vsl), 5),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    _write_state(data)

def _drop_state(key):
    data = _read_state()
    if key in data:
        data.pop(key, None)
        _write_state(data)

def _state_matches(row, sym, is_buy, avg_entry, volume):
    try:
        if str(row.get("symbol")) != str(sym):
            return False
        if str(row.get("side")) != ("BUY" if is_buy else "SELL"):
            return False
        if abs(float(row.get("avg_entry", 0)) - float(avg_entry)) > max(2.0, float(avg_entry) * 0.001):
            return False
        if abs(float(row.get("volume", 0)) - float(volume)) > 0.02:
            return False
        return float(row.get("vsl", 0)) > 0
    except Exception:
        return False

def _load_state_vsl(key, sym, is_buy, avg_entry, volume):
    row = _read_state().get(key)
    if row and _state_matches(row, sym, is_buy, avg_entry, volume):
        return float(row["vsl"])
    return None

def _recover_vsl_from_log(sym, is_buy, avg_entry, floor):
    try:
        if not _BRIDGE_LOG.exists():
            return None
        lines = _BRIDGE_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()[-8000:]
        pat = re.compile(r"COMBINED vSL ratchet ->\s*([0-9]+(?:\.[0-9]+)?)")
        for line in reversed(lines):
            if f"[{sym}]" not in line:
                continue
            m = pat.search(line)
            if not m:
                continue
            vsl = float(m.group(1))
            if is_buy and floor <= vsl <= avg_entry:
                return vsl
            if (not is_buy) and avg_entry <= vsl <= floor:
                return vsl
    except Exception as e:
        log.warning(f"manual-vsl log recovery failed: {e}")
    return None

def _set_sl(pos, sl_price, sym):
    if TEST_MODE:
        log.info(f"TEST manual-mgr [NOT SENT] set SL #{pos.ticket} @ {sl_price:.2f}")
        return None
    req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": sym,
           "position": pos.ticket, "sl": round(sl_price, 2), "tp": pos.tp}
    return mt5.order_send(req)

def _close(pos, sym, tag="manual-close"):
    otype = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(sym)
    if not tick:
        return None
    price = tick.bid if pos.type == 0 else tick.ask
    if TEST_MODE:
        log.info(f"TEST manual-mgr [NOT SENT] close #{pos.ticket} ({pos.volume})")
        return None
    req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": pos.volume,
           "type": otype, "position": pos.ticket, "price": price, "deviation": 20,
           "magic": _hedge_magic(), "comment": tag[:31],
           "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC}
    r = mt5.order_send(req)
    for fill in (mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN):
        if r is None or r.retcode == 10030:
            req["type_filling"] = fill; r = mt5.order_send(req)
    return r


def _partial_close(pos, sym, volume, tag="manual-risk-cut"):
    """Partial-close ONE position by `volume` lots, leaving the rest open."""
    volume = round(float(volume), 2)
    if volume <= 0:
        return None
    otype = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(sym)
    if not tick:
        return None
    price = tick.bid if pos.type == 0 else tick.ask
    if TEST_MODE:
        log.info(f"TEST manual-mgr [NOT SENT] partial-close #{pos.ticket} {volume}/{pos.volume}")
        return None
    req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": volume,
           "type": otype, "position": pos.ticket, "price": price, "deviation": 20,
           "magic": _hedge_magic(), "comment": tag[:31],
           "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC}
    r = mt5.order_send(req)
    for fill in (mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN):
        if r is None or r.retcode == 10030:
            req["type_filling"] = fill; r = mt5.order_send(req)
    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
        log.warning(f"manual-mgr partial-close failed ({tag}): {getattr(r,'retcode',None)} {mt5.last_error()}")
    return r


def _cleanup_stale_hedges(sym):
    """Close any leftover hedge positions (magic 202699) from the old hedge-based logic."""
    for h in _positions(_hedge_magic(), sym):
        _close(h, sym, "stale-hedge-cleanup")
        log.warning(f"[{sym}] stale hedge #{h.ticket} from old logic -> closed")


def _enforce_risk_cap(sym, is_buy, positions, avg_entry, eq, cs):
    """CUT-BASED (2026-07-17, Imtiyaz v2): if total manual lot exceeds the
    risk-equivalent allowed_lot, partial-close the excess from the manual
    positions themselves (largest first). No opposite-side hedge.

      allowed_lot = (equity * manual_risk_pct%) / (contract_size * price * manual_sl_pct%)
      excess      = max(0, total_lot - allowed_lot) -> partial-close immediately
    """
    _cleanup_stale_hedges(sym)

    risk_pct = float(_f("manual_risk_pct", 3.0))
    sl_pct   = float(_f("manual_sl_pct", 1.0)) / 100.0
    sl_dist  = avg_entry * sl_pct
    risk_usd = eq * risk_pct / 100.0
    total_lot = round(sum(p.volume for p in positions), 2)
    allowed_lot = round((risk_usd / (cs * sl_dist)), 2) if (cs * sl_dist) > 0 else total_lot
    excess = round(total_lot - allowed_lot, 2)

    if excess <= 0.01:
        return

    remaining = excess
    for p in sorted(positions, key=lambda x: x.volume, reverse=True):
        if remaining <= 0.005:
            break
        take = min(p.volume, remaining)
        if take >= p.volume - 0.005:
            _close(p, sym, "manual-risk-cut")
        else:
            _partial_close(p, sym, take, "manual-risk-cut")
        remaining = round(remaining - take, 2)

    log.info(f"[{sym}] CUT excess {excess:.2f} lot | was {total_lot:.2f} -> allowed {allowed_lot:.2f} "
             f"@ {risk_pct:.1f}% risk ({sl_pct*100:.1f}% SL dist)")


def _mirror_open(direction, sl_dist, tp_p, primary_lot=None, primary_equity=None):
    """Mirror a NEW primary manual trade to the secondaries (config-gated, default OFF)."""
    try:
        import bridge_multi
        bridge_multi.execute_manual_copy_to_secondaries(
            direction, sl_dist, tp_p,
            primary_lot=primary_lot, primary_equity=primary_equity)
    except Exception as e:
        log.warning(f"manual-copy mirror open failed: {e}")


def _mirror_close():
    """Close the secondaries' manual copies (config-gated, default OFF). Never raises."""
    try:
        import bridge_multi
        bridge_multi.close_manual_copies_on_secondaries()
    except Exception as e:
        log.warning(f"manual-copy mirror close failed: {e}")


def manage(sym=None, mirror_to_slaves=False):
    """Combine all manual trades into ONE position and run ONE ratcheting vSL.
    No-op unless enabled. Call from the live loop (primary account).

    CUT-BASED (2026-07-17 v2): excess lot is partial-closed from the manual
    positions themselves -- no opposite-side hedge orders.
    """
    if not _enabled():
        return
    sym = sym or SYMBOL
    try:
        key = _managed_key(sym)
        info = mt5.account_info()
        if not info:
            return
        eq = float(info.equity)
        cs = _contract_size(sym)
        sl_pct  = float(_f("manual_sl_pct", 1.0)) / 100.0
        tp_pct  = float(_f("manual_target_tp_pct", 0.0) or 0.0)
        buf_pct = float(_f("ratchet_buf_pct", 0.20)) / 100.0
        max_pct = float(_f("manual_risk_pct", 3.0)) / 100.0

        manual = _positions(0, sym)
        if not manual:
            _cleanup_stale_hedges(sym)
            _had = _managed.pop(key, None) is not None
            _drop_state(key)
            if _had and mirror_to_slaves:
                log.info(f"[{sym}] manual position gone (closed by hand / broker) -> closing slave copies")
                _mirror_close()
            return

        # -- COMBINE all manual legs into one net position --
        buy_vol  = sum(p.volume for p in manual if p.type == 0)
        sell_vol = sum(p.volume for p in manual if p.type == 1)
        net = buy_vol - sell_vol
        if abs(net) < 1e-6:
            _cleanup_stale_hedges(sym)
            return
        is_buy = net > 0
        side = [p for p in manual if (p.type == 0) == is_buy]
        tot  = sum(p.volume for p in side)
        avg_entry = (sum(p.volume * p.price_open for p in side) / tot) if tot else manual[0].price_open
        V = abs(net)

        # -- CUT excess lot immediately (2026-07-17 v2, Imtiyaz): partial-close
        # the manual positions themselves if total lot > allowed_lot. No hedge.
        _enforce_risk_cap(sym, is_buy, side, avg_entry, eq, cs)

        tick = mt5.symbol_info_tick(sym)
        cur  = (tick.bid if is_buy else tick.ask) if tick else avg_entry
        max_dist = avg_entry * max_pct
        floor0 = (avg_entry - max_dist) if is_buy else (avg_entry + max_dist)

        try:
            import bridge_ratchet
            _use_htf = bool(_f("ratchet_htf_sl", False))
            _rst = (bridge_ratchet.get_htf_state(_f("ratchet_htf_tf", "H1"), symbol=sym)
                    if _use_htf else bridge_ratchet.get_state(symbol=sym))
        except Exception:
            bridge_ratchet, _rst = None, None

        st = _managed.get(key)
        # -- first time for this combined position: vSL init/recovery + slave mirror --
        if st is None:
            recovered_vsl = _load_state_vsl(key, sym, is_buy, avg_entry, V)
            if recovered_vsl is None:
                recovered_vsl = _recover_vsl_from_log(sym, is_buy, avg_entry, floor0)
            st = {"vsl": recovered_vsl}
            _managed[key] = st
            log.info(f"[{sym}] COMBINED manual {V} lot @ avg {avg_entry:.2f} -> VIRTUAL vSL ON "
                     f"({max_pct*100:.0f}% floor @ {(avg_entry - max_dist) if is_buy else (avg_entry + max_dist):.2f}, NO broker SL)")
            if recovered_vsl is not None:
                log.warning(f"[{sym}] restored manual vSL {recovered_vsl:.2f} after restart/log recovery")
                _save_state(key, sym, is_buy, avg_entry, V, recovered_vsl)
            if mirror_to_slaves and recovered_vsl is None:
                _basis = str(_f("manual_copy_sl_basis", "floor")).lower()
                _copy_sl_dist = max_dist if _basis == "floor" else (avg_entry * sl_pct)
                _tp_points = int((avg_entry * tp_pct / 100.0) / (mt5.symbol_info(sym).point or 0.01)) if tp_pct > 0 else 0
                _risk_pct_taken = (V * cs * _copy_sl_dist / eq * 100.0) if eq > 0 else 0.0
                log.info(f"[{sym}] NEW manual detected -> mirroring {('BUY' if is_buy else 'SELL')} to slaves "
                         f"| primary {V} lot @ ${eq:,.0f} eq (~{_risk_pct_taken:.2f}% risk vs {_basis} SL ${_copy_sl_dist:.2f}) "
                         f"| tp={_tp_points}pts")
                _mirror_open("BUY" if is_buy else "SELL", _copy_sl_dist, _tp_points,
                             primary_lot=V, primary_equity=eq)
            elif mirror_to_slaves:
                log.info(f"[{sym}] restored existing manual vSL; not re-mirroring slave copies")

        # -- floor breach: enforce the risk cap even when ratchet line is unavailable --
        if (is_buy and cur <= floor0) or ((not is_buy) and cur >= floor0):
            log.warning(f"[{sym}] COMBINED past {max_pct*100:.0f}% floor @ {floor0:.2f} (price {cur:.2f}) -> closing ALL manual")
            for p in _positions(0, sym):
                _close(p, sym, "manual-floor-close")
            _cleanup_stale_hedges(sym)
            _managed.pop(key, None)
            _drop_state(key)
            if mirror_to_slaves:
                _mirror_close()
            return

        # -- ratchet ONE VIRTUAL vSL (NOT placed on the broker); breach -> close all --
        prev_vsl = st.get("vsl")
        if prev_vsl is not None:
            try:
                prev_vsl = float(prev_vsl)
            except Exception:
                prev_vsl = None
        if prev_vsl is not None and ((is_buy and cur <= prev_vsl) or ((not is_buy) and cur >= prev_vsl)):
            log.info(f"[{sym}] COMBINED previous vSL hit @ {prev_vsl:.2f} (price {cur:.2f}) -> closing ALL manual")
            for p in _positions(0, sym):
                _close(p, sym, "manual-vsl-close")
            _cleanup_stale_hedges(sym)
            _managed.pop(key, None)
            _drop_state(key)
            if mirror_to_slaves:
                _mirror_close()
            return

        line = None
        if bridge_ratchet is not None and _rst is not None:
            try:
                line = bridge_ratchet.line_for("BUY" if is_buy else "SELL", _rst)
            except Exception:
                line = None
        if line:
            _lbuf = line * buf_pct
            vsl   = (line - _lbuf) if is_buy else (line + _lbuf)
            floor = (avg_entry - max_dist) if is_buy else (avg_entry + max_dist)
            vsl   = max(vsl, floor) if is_buy else min(vsl, floor)
            prev  = st.get("vsl")
            if prev is not None:
                vsl = max(prev, vsl) if is_buy else min(prev, vsl)
            if (is_buy and cur <= vsl) or ((not is_buy) and cur >= vsl):
                log.info(f"[{sym}] COMBINED vSL hit @ {vsl:.2f} (price {cur:.2f}) -> closing ALL manual")
                for p in _positions(0, sym):
                    _close(p, sym, "manual-vsl-close")
                _cleanup_stale_hedges(sym)
                _managed.pop(key, None)
                _drop_state(key)
                if mirror_to_slaves:
                    _mirror_close()
                return
            if vsl != prev:
                log.info(f"[{sym}] COMBINED vSL ratchet -> {vsl:.2f} (line {line:.2f}) [VIRTUAL]")
            st["vsl"] = vsl
            _save_state(key, sym, is_buy, avg_entry, V, vsl)

        # -- target TP on the combined average --
        if tp_pct > 0 and tick:
            move_pct = ((cur - avg_entry) / avg_entry * 100.0) * (1 if is_buy else -1)
            if move_pct >= tp_pct:
                log.info(f"[{sym}] COMBINED hit target TP {tp_pct}% (move {move_pct:.2f}%) -> closing ALL")
                for p in _positions(0, sym):
                    _close(p, sym, "manual-tp-close")
                _cleanup_stale_hedges(sym)
                _managed.pop(key, None)
                _drop_state(key)
                if mirror_to_slaves:
                    _mirror_close()
    except Exception as e:
        log.warning(f"manual manager (manage {sym}) error: {e}")


def manual_floating(sym=None):
    if not _enabled():
        return 0.0
    sym = sym or SYMBOL
    try:
        return float(sum(p.profit for p in (mt5.positions_get(symbol=sym) or [])
                         if p.magic == 0))
    except Exception:
        return 0.0


def dashboard_status(sym=None):
    """Return one combined manual position in the same shape as bot open_trades."""
    if not _enabled():
        return None
    sym = sym or SYMBOL
    try:
        key = _managed_key(sym)
        manual = _positions(0, sym)
        if not manual:
            return None

        buy_vol = sum(p.volume for p in manual if p.type == 0)
        sell_vol = sum(p.volume for p in manual if p.type == 1)
        net = buy_vol - sell_vol
        if abs(net) < 1e-6:
            return None

        is_buy = net > 0
        direction = "BUY" if is_buy else "SELL"
        side = [p for p in manual if (p.type == 0) == is_buy]
        volume = abs(net)
        avg_entry = (sum(p.volume * p.price_open for p in side) / sum(p.volume for p in side)) if side else manual[0].price_open

        tick = mt5.symbol_info_tick(sym)
        cur = (tick.bid if is_buy else tick.ask) if tick else avg_entry
        st = _managed.get(key, {})
        max_pct = float(_f("manual_risk_pct", 3.0)) / 100.0
        floor = (avg_entry - avg_entry * max_pct) if is_buy else (avg_entry + avg_entry * max_pct)
        vsl = float(st.get("vsl") or floor)

        tp_pct = float(_f("manual_target_tp_pct", 0.0) or 0.0) / 100.0
        tp = ((avg_entry * (1 + tp_pct)) if is_buy else (avg_entry * (1 - tp_pct))) if tp_pct > 0 else 0.0

        cs = _contract_size(sym)
        pnl_pts = (cur - avg_entry) if is_buy else (avg_entry - cur)
        sl_base = abs(avg_entry - vsl) or (avg_entry * max_pct)
        profit_r = pnl_pts / sl_base if sl_base else 0.0
        opened = min(getattr(p, "time", 0) or 0 for p in manual)
        open_duration = "--"
        if opened:
            elapsed = datetime.now() - datetime.fromtimestamp(opened)
            open_duration = "0:00:00" if elapsed.total_seconds() < 0 else str(elapsed).split(".")[0]

        return {
            "ticket": "MANUAL",
            "kind": "manual",
            "direction": direction,
            "entry": round(avg_entry, 2),
            "current": round(cur, 2),
            "virtual_sl": round(vsl, 2),
            "tp": round(tp, 2) if tp else 0,
            "tp2": round(tp, 2) if tp else 0,
            "pnl_$": round(pnl_pts * volume * cs, 2),
            "profit_R": round(profit_r, 2),
            "sl_dist_$": round(abs(cur - vsl), 2),
            "breakeven": False,
            "trailing": True,
            "partial_be": 0,
            "partial_close_done": False,
            "max_profit_R": round(profit_r, 2),
            "mode_label": "Manual vSL",
            "open_duration": open_duration,
            "lot": round(volume, 2),
        }
    except Exception as e:
        log.warning(f"manual dashboard status error: {e}")
        return None
