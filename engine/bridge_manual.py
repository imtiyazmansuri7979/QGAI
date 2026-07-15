"""
bridge_manual.py - L13 MANUAL-TRADE MANAGER (config-gated, default OFF).

Treats ALL your manual XAUUSD trades (magic 0; the bot uses 202600) as ONE combined
position: sums the net lots, takes the volume-weighted average entry, and runs ONE
ratcheting vSL for the whole group. Anisa's spec (2026-06-29):
  - cap combined risk at manual_risk_pct (SEPARATE pool from the bot's risk_pct; 3%+3%=6% total):
    if the combined lot is bigger than the risk-equivalent volume, HEDGE the excess.
  - ratchet ONE VIRTUAL vSL up the 2-SMMA line (HTF/H1). 2026-06-30 (Anisa): the vSL is NOT
    placed on the broker/terminal (don't expose the stop to the market / stop-hunting) — the
    bot CLOSES all legs on a virtual breach (vSL or the manual_risk_pct floor), tracked like the
    bot's own trades. ⚠️ if the bot is OFF, the manual has NO protection (explicit trade-off).
    Breach (trend turns / floor) -> close ALL manual legs + hedges.
  - target TP (manual_target_tp_pct) on the combined avg -> close ALL.

Also manages trades that were ALREADY open when the manager started.
WARNING: places REAL orders. Master switch defaults False. DEMO-TEST. Respects TEST_MODE.
"""
import MetaTrader5 as mt5
from datetime import datetime
from bridge_constants import log, CFG, SYMBOL, TEST_MODE

_managed = {}   # account:symbol -> {"vsl": float|None}  (ONE combined state per account+symbol)


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

def _send_market(otype, volume, comment, sym):
    volume = round(float(volume), 2)
    if volume <= 0:
        return None
    tick = mt5.symbol_info_tick(sym)
    if not tick:
        return None
    price = tick.ask if otype == mt5.ORDER_TYPE_BUY else tick.bid
    req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": volume,
           "type": otype, "price": price, "deviation": 20, "magic": _hedge_magic(),
           "comment": comment[:31], "type_time": mt5.ORDER_TIME_GTC,
           "type_filling": mt5.ORDER_FILLING_IOC}
    if TEST_MODE:
        log.info(f"TEST manual-mgr [NOT SENT] {comment} vol={volume} @ {price:.2f}")
        return None
    r = mt5.order_send(req)
    for fill in (mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN):
        if r is None or r.retcode == 10030:
            req["type_filling"] = fill; r = mt5.order_send(req)
    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
        log.warning(f"manual-mgr order failed ({comment}): {getattr(r,'retcode',None)} {mt5.last_error()}")
    return r

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


def manage(sym=None):
    """Combine all manual trades into ONE position and run ONE ratcheting vSL.
    No-op unless enabled. Call from the live loop (primary account)."""
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
        risk_usd = eq * float(_f("manual_risk_pct", 6.0)) / 100.0
        sl_pct  = float(_f("manual_sl_pct", 1.0)) / 100.0
        tp_pct  = float(_f("manual_target_tp_pct", 0.0) or 0.0)
        buf_pct = float(_f("ratchet_buf_pct", 0.20)) / 100.0
        max_pct = float(_f("manual_risk_pct", 6.0)) / 100.0

        manual = _positions(0, sym)
        if not manual:
            for h in _positions(_hedge_magic(), sym):
                _close(h, sym, "manual-cleanup-hedge")
            _managed.pop(key, None)
            return

        # ── COMBINE all manual legs into one net position ──
        buy_vol  = sum(p.volume for p in manual if p.type == 0)
        sell_vol = sum(p.volume for p in manual if p.type == 1)
        net = buy_vol - sell_vol
        if abs(net) < 1e-6:
            return                                  # fully self-hedged manually -> no net risk
        is_buy = net > 0
        side = [p for p in manual if (p.type == 0) == is_buy]
        tot  = sum(p.volume for p in side)
        avg_entry = (sum(p.volume * p.price_open for p in side) / tot) if tot else manual[0].price_open
        V = abs(net)

        tick = mt5.symbol_info_tick(sym)
        cur  = (tick.bid if is_buy else tick.ask) if tick else avg_entry
        max_dist = avg_entry * max_pct   # 3% floor distance (from avg entry — risk cap)

        # ratchet line state (HTF H1 if live config uses it, else M15)
        try:
            import bridge_ratchet
            _use_htf = bool(_f("ratchet_htf_sl", False))
            _rst = bridge_ratchet.get_htf_state(_f("ratchet_htf_tf", "H1")) if _use_htf else bridge_ratchet.get_state()
        except Exception:
            bridge_ratchet, _rst = None, None

        st = _managed.get(key)
        # ── first time for this combined position: 6% backstop + excess hedge ──
        if st is None:
            sl_dist   = avg_entry * sl_pct
            risk6_lot = (risk_usd / (cs * sl_dist)) if (cs * sl_dist) > 0 else V
            if V > risk6_lot + 1e-6:
                excess = round(V - risk6_lot, 2)
                otype  = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
                _send_market(otype, excess, "manual-excess-hedge combined", sym)
                log.info(f"🛡 [{sym}] COMBINED {V} lot > {max_pct*100:.0f}%-lot {risk6_lot:.2f} -> hedged excess {excess}")
            # 2026-06-30 (Anisa): SL is VIRTUAL — do NOT place a broker SL on the terminal
            # (don't expose the stop to the market / stop-hunting). The bot CLOSES the position
            # on a virtual breach (floor / vSL below). ⚠️ if the bot is OFF, the manual has no
            # protection — that is the explicit trade-off.
            st = {"vsl": None}
            _managed[key] = st
            log.info(f"🛡 [{sym}] COMBINED manual {V} lot @ avg {avg_entry:.2f} -> VIRTUAL vSL ON "
                     f"({max_pct*100:.0f}% floor @ {(avg_entry - max_dist) if is_buy else (avg_entry + max_dist):.2f}, NO broker SL — bot closes on breach)")

        # ── L13 fix (2026-06-29): line-INDEPENDENT floor breach — enforce the {max_pct} cap even
        # when the ratchet line is unavailable (trend against the position) or already broken. If
        # price is past the floor, close ALL now (else an underwater manual sits unmanaged because
        # the breach-check below only runs when `line` exists, and the broker SL gets rejected). ──
        floor0 = (avg_entry - max_dist) if is_buy else (avg_entry + max_dist)
        if (is_buy and cur <= floor0) or ((not is_buy) and cur >= floor0):
            log.warning(f"🔻 [{sym}] COMBINED past {max_pct*100:.0f}% floor @ {floor0:.2f} (price {cur:.2f}) -> closing ALL manual + hedges")
            for p in manual:
                _close(p, sym, "manual-floor-close")
            for h in _positions(_hedge_magic(), sym):
                _close(h, sym, "manual-floor-hedge-close")
            _managed.pop(key, None)
            return

        # ── ratchet ONE VIRTUAL vSL up the 2-SMMA line (NOT placed on the broker); breach -> close all ──
        line = None
        if bridge_ratchet is not None and _rst is not None:
            try:
                line = bridge_ratchet.line_for("BUY" if is_buy else "SELL", _rst)
            except Exception:
                line = None
        if line:
            _lbuf = line * buf_pct   # 2026-06-30 (Anisa): buffer = 0.20% of the LIVE line (like the indicator / bot), not fixed-from-entry
            vsl   = (line - _lbuf) if is_buy else (line + _lbuf)
            floor = (avg_entry - max_dist) if is_buy else (avg_entry + max_dist)
            vsl   = max(vsl, floor) if is_buy else min(vsl, floor)
            prev  = st.get("vsl")
            if prev is not None:
                vsl = max(prev, vsl) if is_buy else min(prev, vsl)
            if (is_buy and cur <= vsl) or ((not is_buy) and cur >= vsl):
                log.info(f"🔻 [{sym}] COMBINED vSL hit @ {vsl:.2f} (price {cur:.2f}) -> closing ALL manual + hedges")
                for p in manual:
                    _close(p, sym, "manual-vsl-close")
                for h in _positions(_hedge_magic(), sym):
                    _close(h, sym, "manual-vsl-hedge-close")
                _managed.pop(key, None)
                return
            if vsl != prev:
                log.info(f"🔼 [{sym}] COMBINED vSL ratchet -> {vsl:.2f} (line {line:.2f}) [VIRTUAL — not on broker]")
            st["vsl"] = vsl

        # ── target TP on the combined average ──
        if tp_pct > 0 and tick:
            move_pct = ((cur - avg_entry) / avg_entry * 100.0) * (1 if is_buy else -1)
            if move_pct >= tp_pct:
                log.info(f"🎯 [{sym}] COMBINED hit target TP {tp_pct}% (move {move_pct:.2f}%) -> closing ALL")
                for p in manual:
                    _close(p, sym, "manual-tp-close")
                for h in _positions(_hedge_magic(), sym):
                    _close(h, sym, "manual-tp-hedge-close")
                _managed.pop(key, None)
    except Exception as e:
        log.warning(f"manual manager (manage {sym}) error: {e}")


# ── L8 isolation: floating P&L of the manual legs + their hedges ──
def manual_floating(sym=None):
    if not _enabled():
        return 0.0
    sym = sym or SYMBOL
    try:
        hm = _hedge_magic()
        return float(sum(p.profit for p in (mt5.positions_get(symbol=sym) or [])
                         if p.magic in (0, hm)))
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
