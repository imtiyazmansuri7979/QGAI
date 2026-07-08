"""
bridge_core.py — QUANT GOLD AI v2
MT5 connection, order execution, virtual SL monitor, partial close.
Orchestrates VirtualTrade objects and calls Session for state.
"""
import MetaTrader5 as mt5
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from bridge_constants import (
    log, CFG, SYMBOL, MAGIC, RISK_PCT,
    VIRTUAL_SL, PARTIAL_CLOSE_ENABLED, PARTIAL_CLOSE_PCT,
    MAX_SIMULTANEOUS, TEST_MODE, MAX_SPREAD_USD, SPREAD_WAIT_SEC,
    broker_now_ts, broker_day_start_ts, get_sym_info, sym_point,
    RATCHET_EXIT, RATCHET_BUF_PCT, RATCHET_TP_CAP_PCT, RATCHET_MAX_RISK_PCT,
    TP_EQUITY_PCT,
)
from bridge_risk import VirtualTrade, calc_lot
from bridge_session import Session, _close_position
import bridge_ratchet
from bridge_data import log_signal, get_shadow_summary, record_shadow_signal
import bridge_multi


class QGAICore:
    """
    Handles MT5 connection, trade execution, vSL monitoring.
    Used by bridge_main.run() — not called directly.
    """

    def __init__(self, session: Session):
        self.session        = session
        self.virtual_trades : dict[int, VirtualTrade] = {}
        self._last_signal   = {}
        self.engine         = None   # set by bridge_main after model load

    # FAB-S4 (2026-07-07): remove ticket from in-memory dict AND the persist
    # file, so a restart doesn't try to restore a vSL for an already-closed
    # ticket. Idempotent — safe to call even if ticket is unknown.
    def _forget_ticket(self, ticket: int) -> None:
        try:
            self.virtual_trades.pop(int(ticket), None)
        except Exception:
            pass
        try:
            import vsl_persist as _vp
            _vp.remove(int(ticket))
        except Exception as _e:
            log.warning(f"  vsl_persist remove fail #{ticket}: {_e}")

    # ── MT5 connection ────────────────────────────────────────
    def connect(self) -> bool:
        # Delegate to the shared primary-connect helper, which fails over across
        # MT5_PRIMARIES (≥1) and warms up the data feed on success. This is the
        # SAME path used by every reconnect, so a password change or dropped
        # connection on one primary auto-promotes the next configured primary
        # instead of halting trading.
        return bridge_multi.connect_primary(reason="startup")

    def disconnect(self):
        mt5.shutdown()
        log.info("MT5 disconnected")

    def count_open(self) -> int:
        pos = mt5.positions_get(symbol=SYMBOL) or []
        return sum(1 for p in pos if p.magic == MAGIC)

    # ── Execute (open position) ───────────────────────────────
    def execute(self, direction, sl_mult, tp_mult, win_prob):   # L7b: atr20_pct param removed (was unused)
        """
        Open a new position if all guards pass.
        """
        # Guards
        if self.session.daily_sl_hit:
            log.warning("⛔ execute() blocked — daily SL hit")
            return
        if self.session.daily_tp_hit:
            log.warning("🎯 execute() blocked — daily TARGET already achieved, done for today")
            return
        if self.count_open() >= MAX_SIMULTANEOUS:
            log.warning(f"⛔ execute() blocked — {MAX_SIMULTANEOUS} position(s) already open")
            return

        info = mt5.account_info()
        if not info:
            log.error("❌ execute() — account_info() returned None")
            return

        # L8 (2026-06-29): size off FLOW-ADJUSTED equity. Net out today's deposits/
        # withdrawals (so an intraday balance op can't suddenly grow/shrink the lot) AND
        # the manual leg's floating P&L (L13 — the bot sizes off ITS OWN equity, not a
        # manual trade's swing). Same adjustment the daily ratchet uses → consistent base.
        _eq_adj = info.equity - self.session._net_balance_flow_today()
        try:
            import bridge_manual; _eq_adj -= bridge_manual.manual_floating()
        except Exception:
            pass
        sizing_capital = _eq_adj if _eq_adj > 10 else self.session.day_open_bal

        tick = mt5.symbol_info_tick(SYMBOL)
        if not tick:
            log.error("❌ execute() — symbol_info_tick() returned None (market closed?)")
            return

        # Spread guard (deep-audit risk-gap #1): when bid/ask spread blows
        # out (news spikes, rollover), WAIT for it to normalize and then
        # fire — rather than skipping the whole 15-min bar. 0 = disabled.
        if MAX_SPREAD_USD > 0:
            _spread = tick.ask - tick.bid
            if _spread > MAX_SPREAD_USD:
                import time as _t
                _waited = 0.0
                log.warning(f"⏳ spread ${_spread:.2f} > ${MAX_SPREAD_USD:.2f} "
                            f"— waiting up to {SPREAD_WAIT_SEC:.0f}s to normalize...")
                while _spread > MAX_SPREAD_USD and _waited < SPREAD_WAIT_SEC:
                    _t.sleep(1.0)
                    _waited += 1.0
                    _t2 = mt5.symbol_info_tick(SYMBOL)
                    if not _t2:
                        continue
                    tick = _t2
                    _spread = tick.ask - tick.bid
                if _spread > MAX_SPREAD_USD:
                    log.warning(f"⛔ execute() blocked — spread still ${_spread:.2f} "
                                f"after {_waited:.0f}s (skipping this bar)")
                    return
                log.info(f"✅ spread normalized to ${_spread:.2f} "
                         f"after {_waited:.0f}s — firing")

        si = get_sym_info()
        if not si:
            log.error("❌ execute() — symbol_info() returned None")
            return
        pt = si.point

        price_ref = tick.ask if direction == "BUY" else tick.bid

        # ── SL sizing ─────────────────────────────────────────
        # ATR-based SL removed 2026-06-14. SL is set by ratchet line below.
        # These are placeholders until ratchet (or your custom rule) sets them.
        sl_dist       = 0.0
        sl_p          = 0
        tp_p          = 0
        lot           = 0.0

        # ── RATCHET SL sizing: line + buffer ──
        ratchet_trade = False
        ratchet_buf   = 0.0
        if RATCHET_EXIT:
            _st   = bridge_ratchet.get_state()
            _line = bridge_ratchet.line_for(direction, _st)
            _max_pct = RATCHET_MAX_RISK_PCT
            # HTF-SL (config-gated, default OFF): in a 4h/1h/30m-aligned trend the
            # 15-min line hugs price → stop too tight → whipsaw. If the HTF agrees
            # with the trade, use the HTF ratchet line (further away) for the stop
            # and allow a wider max. Falls back to the 15-min line if HTF disagrees
            # or is unavailable.
            if getattr(CFG.filters, "ratchet_htf_sl", False):
                _htf_tf = getattr(CFG.filters, "ratchet_htf_tf", "H1")
                _htf    = bridge_ratchet.get_htf_state(_htf_tf)
                _hline  = bridge_ratchet.line_for(direction, _htf)
                _hs     = 1 if direction == "BUY" else -1
                if _htf and _htf.get("trend") == _hs and _hline is not None:
                    _line    = _hline
                    _max_pct = getattr(CFG.filters, "ratchet_htf_max_risk_pct", 2.5)
                    log.info(f"  ⚡ HTF-SL: using {_htf_tf} line={_hline:.2f} (15-min line skipped)")
            if _line is not None:
                ratchet_buf = round(price_ref * RATCHET_BUF_PCT / 100.0, 3)
                _s    = 1 if direction == "BUY" else -1
                _vsl  = round(_line - _s * ratchet_buf, 3)
                _dist = round((price_ref - _vsl) * _s, 3)
                _max  = price_ref * _max_pct / 100.0
                _min_sl = price_ref * CFG.filters.ratchet_sl_min_pct / 100.0  # was fixed $8 → now % of price
                if _min_sl <= _dist <= _max:
                    sl_dist = _dist
                    sl_p    = max(100, int(sl_dist / pt))
                    # TP: equity-based to match WFO backtest. With constant
                    # risk_pct, "close at tp_equity_pct of equity" == a fixed
                    # R-multiple = tp_equity_pct / risk_pct. So TP distance =
                    # sl_dist × that multiple. (WFO: buf 0.09 / TP 4% / 3% risk
                    # = 1.333R → +199.6R out-of-sample.)
                    if TP_EQUITY_PCT > 0 and RISK_PCT > 0:
                        _r_mult = TP_EQUITY_PCT / RISK_PCT
                        tp_p    = max(1, int(sl_dist * _r_mult / pt))
                        _tp_lbl = f"equity-TP {TP_EQUITY_PCT}% = {_r_mult:.3f}R"
                    else:
                        # price-based TP cap. P3 (2026-06-27): regime-adaptive — switch
                        # the cap by HMM state at entry (matches backtest _TP_BY_REGIME,
                        # validated OOS: regime +266R/PF3.35 vs global +255R). Config-gated,
                        # reversible (ratchet_tp_regime=False → single RATCHET_TP_CAP_PCT).
                        _tpcap = RATCHET_TP_CAP_PCT
                        if getattr(CFG.filters, "ratchet_tp_regime", False):
                            _st = (self._last_signal.get("hmm_state") or "").strip().title()
                            _tpcap = {"Ranging": 2.0, "Trending": 1.0,
                                      "Volatile": 0.8}.get(_st, RATCHET_TP_CAP_PCT)
                            _tp_lbl = f"TP cap {_tpcap}% [{_st or 'regime?'}]"
                        else:
                            _tp_lbl = f"TP cap {_tpcap}%"
                        tp_p    = int(price_ref * _tpcap / 100.0 / pt)
                    lot     = calc_lot(sizing_capital, sl_p, si)
                    ratchet_trade = True
                    log.info(f"  ⚡ RATCHET SL: line={_line:.2f} buf=${ratchet_buf:.2f} "
                             f"vSL dist=${sl_dist:.2f} | {_tp_lbl}")
                else:
                    log.warning(f"  ⚡ RATCHET line risk ${_dist:.2f} outside "
                                f"[8.0, {_max:.2f}]")
            else:
                log.warning("  ⚡ RATCHET line unavailable for "
                            f"{direction} (trend against / no data)")

        # ── Skip if no valid SL set ──
        # Pure ratchet mode: no ATR fallback. If ratchet line unavailable → skip.
        if not ratchet_trade or sl_dist <= 0:
            log.warning(f"  ⛔ SKIP {direction} — no valid SL (no ratchet line)")
            return

        # FAB-S3: DD-brake halt band — calc_lot returns 0.0 when drawdown > halt
        # threshold. Treat as "no new entries until equity recovers".
        if 'lot' in dir() and lot is not None and lot <= 0:
            log.warning(f"  🛑 SKIP {direction} — DD brake HALT (drawdown > halt threshold)")
            return

        # Pre-trade daily SL check
        if self.session.daily_loss >= self.session.daily_limit:
            log.warning("⛔ execute() blocked — daily SL already at limit")
            return

        # Build order
        if direction == "BUY":
            otype      = mt5.ORDER_TYPE_BUY
            price      = tick.ask
            virtual_sl = round(price - sl_dist, 2)
            tp         = round(price + tp_p * pt, 2)
            broker_sl  = round(price - sl_dist * 1.5, 2) if VIRTUAL_SL else round(price - sl_p * pt, 2)
        else:
            otype      = mt5.ORDER_TYPE_SELL
            price      = tick.bid
            virtual_sl = round(price + sl_dist, 2)
            tp         = round(price - tp_p * pt, 2)
            broker_sl  = round(price + sl_dist * 1.5, 2) if VIRTUAL_SL else round(price + sl_p * pt, 2)

        # Market phase (Trending/Ranging/Volatile) — client-facing tag, NOT strategy data
        _phase = (self._last_signal.get("hmm_state") or "").strip().title()
        _cm    = f"QuantEdge AI | {_phase}" if _phase else "QuantEdge AI"
        req = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       SYMBOL,
            "volume":       lot,
            "type":         otype,
            "price":        price,
            "sl":           broker_sl,
            "tp":           tp,
            "deviation":    20,   # max 20 pts ($0.20) slippage — prevents silent rejects in fast markets
            "magic":        MAGIC,
            "comment":      _cm,
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # TEST MODE — log but don't send
        if TEST_MODE:
            log.info(f"🧪 TEST | {direction} {lot}lot @ {price:.2f} "
                     f"vSL:{virtual_sl:.2f} TP:{tp:.2f} [NOT SENT]")
            return

        r = mt5.order_send(req)
        if r is None or r.retcode == 10030:
            req["type_filling"] = mt5.ORDER_FILLING_FOK
            r = mt5.order_send(req)
        if r is None or r.retcode == 10030:
            req["type_filling"] = mt5.ORDER_FILLING_RETURN
            r = mt5.order_send(req)
        if r is None:
            log.error(f"❌ order_send returned None: {mt5.last_error()}")
            return

        if r.retcode == mt5.TRADE_RETCODE_DONE:
            self.session.trades_today += 1
            trade_num = self.session.trades_today
            # Trade-2 equity SL REMOVED 2026-06-19 — risk = per-trade 3% + daily 9%.

            log.info(f"✅ Trade#{trade_num} {direction} {lot} {SYMBOL} @ {price} "
                     f"virtualSL:{virtual_sl} TP:{tp} [VirtualSL+Trail] #{r.order}")

            # vSL immediate set confirmation via chart line
            self._draw_sl_line(r.order, virtual_sl, direction)

            # Register virtual trade tracker
            vt = VirtualTrade(
                ticket=r.order, direction=direction,
                entry=price, virtual_sl=virtual_sl,
                tp=tp, lot=lot, sl_dist=sl_dist,
                ratchet=ratchet_trade, ratchet_buf=ratchet_buf,
            )
            self.virtual_trades[r.order] = vt

            # FAB-S4 (2026-07-07): persist initial vSL immediately, so a restart
            # right after open sees the entry-level vSL (not 15.0 fallback).
            try:
                import vsl_persist as _vp
                _vp.save(r.order, virtual_sl, sl_dist, direction, price,
                         breakeven=False, trailing=False)
            except Exception as _e:
                log.warning(f"  vsl_persist open save fail #{r.order}: {_e}")

            # Immediately set last_trade_was_loss on vSL close (lag fix)
            # (will be properly set by check_closed, this is backup)
            vt._entry_price_ref = price

            # ── Multi-account: replicate to secondary MT5 accounts ──
            # sl_dist and tp_p are in scope from the sizing block above.
            # bridge_multi handles shutdown/reconnect of primary internally.
            try:
                bridge_multi.execute_secondary_accounts(direction, sl_dist, tp_p, comment=_cm)
            except Exception as _me:
                log.error(f"❌ [multi] Secondary execution error: {_me}", exc_info=True)

            return lot   # FIX #16: real lot back to caller for logging

        else:
            log.error(f"❌ Order rejected: retcode={r.retcode} ({r.comment})")
            return None

    # ── Partial close ─────────────────────────────────────────
    def partial_close(self, ticket: int, close_pct: float = 0.50) -> bool:
        """Close close_pct of position. Returns True on success."""
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False
        pos       = positions[0]
        tick      = mt5.symbol_info_tick(SYMBOL)
        if not tick:
            return False
        price     = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
        si        = get_sym_info()
        vol_min   = si.volume_min  if si else 0.01
        vol_step  = si.volume_step if si else 0.01

        # Snap to broker's volume step — round(x, 2) is wrong for brokers
        # where vol_step > 0.01 (e.g. 0.05 or 0.10); it produces volumes
        # that are not multiples of vol_step and get rejected.
        import math as _math
        raw_close = pos.volume * close_pct
        close_vol = _math.floor(raw_close / vol_step) * vol_step
        close_vol = round(max(vol_min, close_vol), 10)   # avoid float drift
        remaining = round(pos.volume - close_vol, 10)

        if remaining < vol_min:
            log.warning(f"  ⚠️ Partial close skipped #{ticket} — remaining {remaining} < {vol_min}")
            return False
        close_vol = max(vol_min, close_vol)

        req = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       SYMBOL,
            "volume":       close_vol,
            "type":         mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
            "position":     ticket,
            "price":        price,
            "magic":        MAGIC,
            "comment":      "QuantEdge_partial_close",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        r = mt5.order_send(req)
        if r is None or r.retcode == 10030:
            req["type_filling"] = mt5.ORDER_FILLING_FOK
            r = mt5.order_send(req)

        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            pnl_est = round(pos.profit * close_pct, 2)
            log.info(f"  ✂️ Partial {close_pct*100:.0f}% #{ticket} @ {price:.2f} | est P&L:${pnl_est:.2f}")
            vt = self.virtual_trades.get(ticket)
            if vt:
                vt.lot = round(remaining, 2)
                # Preserve trail gain — don't roll back to entry
                vt.virtual_sl = (
                    max(vt.virtual_sl, vt.entry) if vt.direction == "BUY"
                    else min(vt.virtual_sl, vt.entry)
                )
                vt.breakeven  = True
                self._update_sl_line(ticket, vt.virtual_sl)
                # FAB-S4: persist post-partial vSL + BE flag.
                try:
                    import vsl_persist as _vp
                    _vp.save(ticket, vt.virtual_sl, vt.sl_dist, vt.direction, vt.entry,
                             breakeven=True, trailing=vt.trailing)
                except Exception as _e:
                    log.warning(f"  vsl_persist partial save fail #{ticket}: {_e}")
            return True
        else:
            err = r.retcode if r else mt5.last_error()
            log.error(f"  ❌ Partial close failed #{ticket}: {err}")
            return False

    # ── Monitor virtual SL (every 2s) ─────────────────────────
    def monitor_virtual_sl(self, verbose=False):
        """
        Check vSL, trailing, daily SL, smart exit every 2 seconds.
        Modifies virtual_trades in place.
        """
        tick = mt5.symbol_info_tick(SYMBOL)
        si   = get_sym_info()
        if not tick or not si:
            return
        pt = si.point

        # Daily SL intra-bar check
        # BUGFIX: these checks return the STICKY flag True on every poll once
        # halted, so close_secondary_accounts() must fire ONLY on the fresh
        # transition (flag was False before the call) — otherwise it would
        # shutdown/reconnect + re-close secondaries every single second.
        _was_sl = self.session.daily_sl_hit
        if self.session.check_daily_sl_intrabar(self.virtual_trades):
            if not _was_sl:
                bridge_multi.close_secondary_accounts()   # BUGFIX: flatten secondaries too on daily-SL halt
            self.virtual_trades.clear()
            return

        # Daily Equity TARGET check (EA-style, virtual)
        _was_tp = self.session.daily_tp_hit
        if self.session.check_daily_tp_intrabar(self.virtual_trades):
            if not _was_tp:
                bridge_multi.close_secondary_accounts()   # BUGFIX: flatten secondaries too on daily-TP halt
            self.virtual_trades.clear()
            return

        # Trade-2 equity SL REMOVED 2026-06-19 — risk = per-trade 3% (vSL) + daily 9%.

        if not self.virtual_trades:
            return

        # ── RATCHET: per-closed-bar line trail + flip exit ────
        if RATCHET_EXIT and any(t.ratchet for t in self.virtual_trades.values()):
            st = bridge_ratchet.get_state()
            # HTF overlays (config-gated, default OFF). When enabled, the SL-trail
            # line and/or the flip-exit come from the HIGHER timeframe instead of
            # the tight 15-min line — so 15-min noise can't cut the stop and only a
            # real HTF flip exits the trade. Still re-evaluated every M15 close.
            _use_htf_sl   = getattr(CFG.filters, "ratchet_htf_sl", False)
            _use_htf_flip = getattr(CFG.filters, "ratchet_htf_flip", False)
            _htf_st = None
            if _use_htf_sl or _use_htf_flip:
                _htf_st = bridge_ratchet.get_htf_state(getattr(CFG.filters, "ratchet_htf_tf", "H1"))
            _line_st = _htf_st if (_use_htf_sl and _htf_st) else st
            _flip_st = _htf_st if (_use_htf_flip and _htf_st) else st
            if st and st["bar_time"] != getattr(self, "_ratchet_bar", None):
                self._ratchet_bar = st["bar_time"]
                for tk, tr in list(self.virtual_trades.items()):
                    if not tr.ratchet:
                        continue
                    ln  = bridge_ratchet.line_for(tr.direction, _line_st)
                    act = tr.ratchet_bar_update(ln, _flip_st["flip"])
                    if act == "FLIP_CLOSE":
                        log.warning(f"  🔄 #{tk} closing on opposite flip")
                        if _close_position(tk, vsl=tr.virtual_sl):
                            bridge_multi.close_secondary_accounts()
                            self._remove_sl_line(tk)
                            self._forget_ticket(tk)
                        # else: close failed (e.g. AutoTrading off) — keep tracking so the
                        # next tick retries automatically instead of silently abandoning it.
                        # L13 (approach A): no flip-hedge — the manual trade's own vSL ratchet
                        # (in bridge_manual.manage) trails the 2-SMMA line and CLOSES the manual
                        # leg when the trend turns against it. Simpler than hedging; same protection.
                # STRUCT-H1 EXIT (config-gated — fully reversible).
                #   enable_struct_h1_exit=True  → CLOSE the trade on 1h-structure break
                #   enable_struct_h1_exit=False → shadow LOG only (no close)
                try:
                    _en  = getattr(CFG.filters, "enable_struct_h1_exit", False)
                    _lkb = int(getattr(CFG.filters, "struct_h1_lookback", 6))
                    _h1 = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_H1, 1, _lkb)  # last N completed H1 bars
                    if _h1 is not None and len(_h1) >= 2:
                        _sup = float(min(b['low'] for b in _h1)); _res = float(max(b['high'] for b in _h1))
                        _cur = tick.bid
                        if not hasattr(self, "_shadow_done"): self._shadow_done = set()
                        for _tk, _tr in list(self.virtual_trades.items()):
                            _brk = (_tr.direction == 'BUY' and _cur < _sup) or (_tr.direction == 'SELL' and _cur > _res)
                            if not _brk:
                                continue
                            _r = ((_cur - _tr.entry) / _tr.sl_dist) * (1 if _tr.direction == 'BUY' else -1)
                            if _en:
                                log.warning(f"  📐 #{_tk} STRUCT-H1 exit @ {_cur:.2f} | R={_r:+.2f}")
                                if _close_position(_tk, vsl=_tr.virtual_sl):
                                    bridge_multi.close_secondary_accounts()
                                    self._remove_sl_line(_tk)
                                    self._forget_ticket(_tk)
                            elif _tk not in self._shadow_done:
                                log.info(f"  📍 [SHADOW Struct-H1] #{_tk} would EXIT @ {_cur:.2f} | R={_r:+.2f} (live exit unchanged)")
                                self._shadow_done.add(_tk)
                except Exception as _se:
                    log.debug(f"struct-h1 exit err: {_se}")
                if not self.virtual_trades:
                    return

        last_price = tick.bid
        for ticket, trade in list(self.virtual_trades.items()):
            current_price = tick.ask if trade.direction == "SELL" else tick.bid
            last_price    = current_price

            # Update HMM state for smart exit
            trade._hmm_state = self._last_signal.get("hmm_state", "")

            action = trade.update(current_price, pt)
            st     = trade.status(current_price)

            if verbose:
                _pnl  = st["pnl_$"]
                _icon = "🟢" if _pnl >= 0 else "🔴"
                log.info(
                    f"  ⏳ #{ticket} {trade.direction} {trade.lot}lot | "
                    f"Entry:{trade.entry:.2f} → Now:{current_price:.2f} | "
                    f"{_icon} PnL:${_pnl:+.2f} | "
                    f"vSL:{trade.virtual_sl:.2f} (${st['sl_dist_$']:.2f} away) | "
                    f"TP:{trade.tp:.2f} | R:{st['profit_R']:+.2f} | {st['mode_label']}"
                )

            if action == "CLOSE":
                log.warning(f"  🛑 #{ticket} Virtual SL hit @ {current_price:.2f} — closing!")
                if _close_position(ticket, vsl=trade.virtual_sl):
                    bridge_multi.close_secondary_accounts()
                    self._forget_ticket(ticket)
                # else: close failed — keep it in virtual_trades so this same "CLOSE" check
                # fires again next tick (2026-07-01 fix: used to abandon monitoring on the
                # first failed close, silently breaking the promised retry loop).
                continue

            if action == "PARTIAL_CLOSE":
                ok = self.partial_close(ticket, close_pct=PARTIAL_CLOSE_PCT)
                if ok:
                    vt = self.virtual_trades.get(ticket)
                    if vt:
                        # Extend broker TP to 3R
                        pos_list = mt5.positions_get(ticket=ticket)
                        if pos_list:
                            mr = mt5.order_send({
                                "action":   mt5.TRADE_ACTION_SLTP,
                                "symbol":   SYMBOL,
                                "position": ticket,
                                "sl":       pos_list[0].sl,
                                "tp":       vt.tp2,
                            })
                            if mr and mr.retcode == mt5.TRADE_RETCODE_DONE:
                                log.info(f"  🎯 #{ticket} TP extended → {vt.tp2:.2f} (3R)")
                        log.info(f"  ✅ #{ticket} Partial done | vSL:{vt.virtual_sl:.2f} | "
                                 f"lot:{vt.lot:.2f} riding to {vt.tp2:.2f}")
                continue

            if action == "SMART_CLOSE":
                reason  = trade.smart_exit_reason
                pnl_now = trade.status(current_price)["pnl_$"]
                log.warning(f"  🧠 #{ticket} Smart Exit: {reason} | locking ${pnl_now:+.2f}")
                if _close_position(ticket, vsl=trade.virtual_sl):
                    bridge_multi.close_secondary_accounts()
                    self._forget_ticket(ticket)
                continue

            # TP hit by broker (position disappeared)
            if not mt5.positions_get(ticket=ticket) and ticket in self.virtual_trades:
                log.info(f"  ✅ #{ticket} TP hit / closed by broker @ {current_price:.2f}")
                self._remove_sl_line(ticket)
                self._forget_ticket(ticket)

    # ── Chart indicator lines ─────────────────────────────────
    def _draw_sl_line(self, ticket, sl_price, direction):
        # FIX #7: removed a placeholder mt5.order_send() that fired a
        # malformed TRADE_ACTION_DEAL request at the broker after every
        # fill. MT5's Python API can't draw chart objects anyway — the
        # vSL is visible via the broker_sl field and this log line.
        log.info(f"  📏 vSL #{ticket} {direction} @ {sl_price:.2f}")

    def _update_sl_line(self, ticket, new_sl):
        pass  # Chart line updated via position modification

    def _remove_sl_line(self, ticket):
        pass  # Line removed when position closes

    # ── Opposite signal handler ───────────────────────────────
    def handle_opposite_signal(self, new_signal, new_prob, sl_mult, tp_mult,
                               win_prob) -> bool:   # L7b: atr20_pct param removed (was unused)
        """
        Called when signal direction is opposite to open position.
        Logic:
          - In LOSS  → exit immediately (cut loss)
          - In WIN   → exit only if new prob > 0.60 (strong reversal)
          - After close → optionally open new direction
        Returns True if handled (caller should not re-evaluate signal).
        """
        from bridge_constants import RISK_PCT
        LOSS_EXIT_THRESHOLD  = 0.45
        WIN_EXIT_THRESHOLD   = 0.60

        if not self.virtual_trades:
            return False

        for ticket, vt in list(self.virtual_trades.items()):
            if vt.direction == new_signal:
                continue   # same direction — not opposite

            pos_list = mt5.positions_get(ticket=ticket) or []
            if not pos_list:
                continue
            pos      = pos_list[0]
            tick     = mt5.symbol_info_tick(SYMBOL)
            if not tick:
                continue

            cur_price = tick.ask if vt.direction == "SELL" else tick.bid
            in_profit = (cur_price > vt.entry) if vt.direction == "BUY" \
                else (cur_price < vt.entry)
            pnl_pts   = (cur_price - vt.entry) if vt.direction == "BUY" \
                else (vt.entry - cur_price)
            profit_r  = pnl_pts / vt.sl_dist if vt.sl_dist else 0

            should_exit = False
            if not in_profit and new_prob >= LOSS_EXIT_THRESHOLD:
                log.info(f"  🔄 #{ticket} In LOSS — exiting on opposite signal (prob={new_prob:.2%})")
                should_exit = True
            elif in_profit and new_prob >= WIN_EXIT_THRESHOLD:
                log.info(f"  🔄 #{ticket} In WIN ({profit_r:.2f}R) — strong reversal signal ({new_prob:.2%})")
                should_exit = True

            if should_exit:
                if not _close_position(ticket, vsl=vt.virtual_sl):
                    continue   # close failed — leave it tracked, retry next tick, don't open the reversal yet
                bridge_multi.close_secondary_accounts()
                self.session.check_closed(self.virtual_trades)
                if ticket in self.virtual_trades:
                    self._forget_ticket(ticket)

                # FAB-S1 (2026-07-07): the reversal RE-ENTRY historically called
                # self.execute() DIRECTLY here — bypassing range/CTF/pullback/SMMA/
                # ADX entry filters (execute() only checks daily-SL). Backtest models
                # no reversal at all → parity gap (June overlap 12%).
                #   gate_reversal_entries=False (default): keep old behavior (open now).
                #   gate_reversal_entries=True: close only, return False → the main
                #     loop re-evaluates THIS bar's signal through the full filter stack
                #     and opens the reversal only if it passes (live == filtered entry).
                _gate_rev = bool(getattr(CFG.filters, "gate_reversal_entries", False))
                if _gate_rev:
                    log.info(f"  🔄 closed on opposite signal; reversal re-entry will pass entry filters")
                    return False   # let caller's filter stack decide on the re-entry
                # Legacy path: open new direction immediately if daily SL not hit
                if not self.session.daily_sl_hit:
                    log.info(f"  → Opening {new_signal} (reversal, unfiltered — legacy)")
                    self.execute(new_signal, sl_mult, tp_mult, win_prob)
                return True

        return False

    # ── Recover open trades on restart ───────────────────────
    def recover_open_trades(self):
        """
        On bridge restart with open positions: reconstruct VirtualTrade objects
        from MT5 position data so vSL monitoring continues.
        """
        positions = mt5.positions_get(symbol=SYMBOL) or []
        qgai_pos  = [p for p in positions if p.magic == MAGIC]
        if not qgai_pos:
            log.info("  ↩️ No open trades to recover")
            return

        for pos in qgai_pos:
            ticket    = pos.ticket
            direction = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
            entry     = pos.price_open
            lot       = pos.volume
            tp        = pos.tp

            # FAB-S4 (2026-07-07): recover vSL in priority order —
            #   (1) persisted state file (logs/vsl_state.json) — has TRAILED vSL
            #   (2) VSL=/SL= tags in position comment — legacy (comment no longer has them)
            #   (3) broker-SL fallback — puts vSL back to ENTRY, forfeits trail gain
            _persisted = None
            try:
                import vsl_persist as _vp
                _persisted = _vp.get(ticket)
            except Exception as _e:
                log.warning(f"  vsl_persist read fail #{ticket}: {_e}")

            _restored_be = False
            _restored_trail = False
            if _persisted:
                virtual_sl = float(_persisted["virtual_sl"])
                sl_dist    = float(_persisted["sl_dist"])
                _restored_be    = bool(_persisted.get("breakeven", False))
                _restored_trail = bool(_persisted.get("trailing", False))
                log.info(f"  ✅ #{ticket} vSL restored from persist: {virtual_sl:.2f} "
                         f"(trail={_restored_trail}, be={_restored_be})")
            else:
                import re as _re
                m_vsl = _re.search(r"VSL=([\d.]+)", pos.comment or "")
                m_sl  = _re.search(r"SL=([\d.]+)",  pos.comment or "")
                if m_vsl and m_sl:
                    sl_dist   = float(m_sl.group(1))
                    virtual_sl = float(m_vsl.group(1))
                else:
                    # Last-resort: reconstruct from broker SL (broker_sl = vSL × 3
                    # historically, now × 1.5 per FAB-S4 tightening — divisor updated).
                    broker_sl_dist = abs(pos.sl - entry) if pos.sl else 0.0
                    sl_dist   = round(broker_sl_dist / 1.5, 2) if broker_sl_dist else 15.0
                    virtual_sl = (round(entry + sl_dist, 2) if direction == "SELL"
                                  else round(entry - sl_dist, 2))
                    log.warning(f"  ⚠️  #{ticket} no persist + no SL tag — "
                                f"reconstructed vSL=${virtual_sl:.2f} (trail gain LOST)")

            _rbuf = round(entry * RATCHET_BUF_PCT / 100.0, 3) if RATCHET_EXIT else 0.0
            vt = VirtualTrade(
                ticket=ticket, direction=direction,
                entry=entry, virtual_sl=virtual_sl,
                tp=tp, lot=lot, sl_dist=sl_dist,
                ratchet=RATCHET_EXIT, ratchet_buf=_rbuf,
            )
            # FAB-S4: restore breakeven / trailing flags from persist so the
            # ratchet logic doesn't mistakenly reset them on the next bar.
            if _persisted:
                vt.breakeven = _restored_be
                vt.trailing  = _restored_trail
            # Restore partial BE state based on current profit
            tick = mt5.symbol_info_tick(SYMBOL)
            if tick:
                cur = tick.ask if direction == "SELL" else tick.bid
                profit_r = ((cur - entry) if direction == "BUY" else (entry - cur)) / sl_dist
                if profit_r >= 0.5:
                    vt.partial_be = 2
                elif profit_r >= 0.3:
                    vt.partial_be = 1
                # Bug B fix: restore the REAL open duration so the smart-exit 1h
                # timer doesn't reset to "now" on every bridge restart. tick.time
                # and pos.time are both MT5 server epochs (same reference).
                _dur = int(getattr(tick, "time", 0)) - int(getattr(pos, "time", 0))
                if _dur > 0:
                    vt.open_time = vt.open_time - timedelta(seconds=_dur)

            self.virtual_trades[ticket] = vt
            log.info(f"  ↩️ Recovered #{ticket} {direction} @ {entry} vSL:{virtual_sl:.2f} lot:{lot}")

        # FAB-S4: prune stale persist entries for tickets the broker no longer
        # holds (closed while bridge was down). Runs after all live positions
        # are reconstructed so `self.virtual_trades.keys()` is authoritative.
        try:
            import vsl_persist as _vp
            _n_pruned = _vp.prune_stale(set(self.virtual_trades.keys()))
            if _n_pruned:
                log.info(f"  🧹 vsl_persist pruned {_n_pruned} stale ticket(s)")
        except Exception as _e:
            log.warning(f"  vsl_persist prune fail: {_e}")
