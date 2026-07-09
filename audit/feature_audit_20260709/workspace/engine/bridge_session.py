"""
bridge_session.py — QUANT GOLD AI v2
Daily session management: reset, deal tracking, trade counters,
check_closed outcome detection.
"""
import MetaTrader5 as mt5
from datetime import datetime, timezone

from bridge_constants import (
    log, CFG, SYMBOL, MAGIC, DAILY_SL, DAILY_TP, ENABLE_DAILY_TP,
    broker_day_start_ts, broker_now_ts,
)
from bridge_data import write_outcome, update_daily_summary, update_shadow_outcome


class Session:
    """
    Tracks daily state: balance, loss, trades, last outcome.
    One instance lives for the lifetime of the bridge process.
    """

    def __init__(self):
        self.day_open_bal        = 0.0
        self.day_peak_equity     = 0.0     # highest equity reached today (ratchet daily floor)
        self.daily_loss          = 0.0
        self.daily_sl_hit        = False
        self.daily_tp_hit        = False   # daily equity TARGET reached (EA-style)
        self.trades_today        = 0
        self.last_trade_was_loss = False
        self._last_closed_count  = 0
        # FIX #19: ticket-based dedupe — count-based dedupe could skip
        # deals (e.g. equal counts across a day rollover).
        self._processed_deals    = set()
        self._today_str          = None   # 'YYYY-MM-DD' of current broker day
        # L8 (2026-06-29): balance-op (deposit/withdrawal) audit. Pre-load all existing
        # ops silently on first scan, then announce + log only NEW ones as they occur.
        self._seen_balance_ops   = set()
        self._balance_ops_loaded = False

    # ── Daily reset ───────────────────────────────────────────
    def reset_daily(self, equity: float, broker_date_str: str):
        """Called when broker day changes (midnight UTC = broker midnight)."""
        self.day_open_bal        = equity
        self.day_peak_equity     = equity   # ratchet: peak starts at day-open
        self.daily_loss          = 0.0
        self.daily_sl_hit        = False
        self.daily_tp_hit        = False
        self.trades_today        = 0
        self.last_trade_was_loss = False
        self._today_str          = broker_date_str
        # L8 (2026-06-27): mark day start so deposits/withdrawals AFTER this point are
        # netted out of the daily-ratchet equity (day_open_bal already includes anything
        # before now). _flow_* is a short cache so we don't query deal history every 2s.
        from datetime import datetime as _dt
        self._day_start_ts       = _dt.now()
        self._flow_ts            = 0.0
        self._flow_val           = 0.0
        log.info(f"📅 New day! Equity:${equity:,.2f} DailySL:${equity*DAILY_SL/100:.2f}"
                 f" DailyTarget:${equity*(1+DAILY_TP/100):,.2f} (+{DAILY_TP}%)")

    def _net_balance_flow_today(self) -> float:
        """L8: net deposits(+)/withdrawals(-) since day start (MT5 DEAL_TYPE_BALANCE).
        Subtract from live equity so a deposit/withdrawal can't distort the daily ratchet
        floor or falsely trip the halt. Cached ~30s (balance ops are rare). 0.0 on any
        error → falls back to raw equity (safe)."""
        import time as _t
        from datetime import datetime as _dt
        now = _t.time()
        if (now - getattr(self, "_flow_ts", 0.0)) < 30.0 and hasattr(self, "_flow_val"):
            return self._flow_val
        flow = 0.0
        try:
            # 2026-06-29 FIX: count ONLY today's balance ops, filtered by the deal's
            # SERVER timestamp (d.time) vs the BROKER day start — NOT a local-time
            # from-date. The old code passed local _dt.now() as the from-date; the PC
            # was ~2.5h ahead of the UTC+3 server, so the from-date sat in the server's
            # future and history_deals_get returned the account's ENTIRE balance history
            # (lifetime demo deposits ~$906k) as "today's flow" → equity looked ~$906k
            # smaller → FALSE daily-SL halt on startup.
            day_start = broker_day_start_ts()
            deals = mt5.history_deals_get(_dt(2000, 1, 1), _dt.now())
            if deals:
                for d in deals:
                    if d.type == mt5.DEAL_TYPE_BALANCE and getattr(d, "time", 0) >= day_start:
                        flow += d.profit          # + deposit / - withdrawal (today only)
            # Safety guard: a flow > 50% of day-open is almost certainly a mis-read;
            # ignore it so a bad balance query can NEVER falsely trip the daily halt.
            if self.day_open_bal and abs(flow) > 0.5 * self.day_open_bal:
                if not getattr(self, "_flow_warned", False):
                    log.warning(f"⚠️ balance-flow ${flow:,.0f} > 50% of day-open — ignoring "
                                f"(same-day deposit/withdrawal or mis-read). Suppressing further warnings.")
                    self._flow_warned = True
                flow = 0.0
        except Exception:
            flow = 0.0
        self._flow_ts = now
        self._flow_val = flow
        return flow

    # L8: fixed UTC anchor for the trading-equity curve. Deposits/withdrawals AFTER this
    # instant are netted out of the logged equity so the curve reflects TRADING P&L only
    # (immune to future flows). Flows BEFORE it are a constant baseline offset (don't change
    # the curve's shape). 2026-06-29 = when this logging began.
    _TRADING_EQ_ANCHOR_TS = datetime(2026, 6, 29, tzinfo=timezone.utc).timestamp()

    def trading_equity(self, raw_equity: float) -> float:
        """L8: raw equity minus net external flow (deposits +/withdrawals -) since the
        fixed anchor → a clean TRADING-only equity for the signal log. Cached ~30s
        (balance ops are rare). Falls back to raw equity on any error (safe)."""
        import time as _t
        from datetime import datetime as _dt
        now = _t.time()
        if (now - getattr(self, "_teq_ts", 0.0)) < 30.0 and hasattr(self, "_teq_val"):
            flow = self._teq_val
        else:
            flow = 0.0
            try:
                # wide window + server-timestamp filter (same safe pattern as
                # _net_balance_flow_today — avoids the local-vs-server from-date bug).
                deals = mt5.history_deals_get(_dt(2000, 1, 1), _dt.now())
                if deals:
                    for d in deals:
                        if d.type == mt5.DEAL_TYPE_BALANCE and \
                           getattr(d, "time", 0) >= self._TRADING_EQ_ANCHOR_TS:
                            flow += d.profit
            except Exception:
                flow = 0.0
            self._teq_ts = now
            self._teq_val = flow
        return round(raw_equity - flow, 2)

    def log_new_balance_ops(self):
        """L8: detect deposits/withdrawals (DEAL_TYPE_BALANCE) and log each NEW one once
        (bridge log + balance_flows.csv) for audit. First scan pre-loads existing ops
        silently; only ops appearing AFTER startup are announced. Safe/no-op on error."""
        try:
            from datetime import datetime as _dt
            deals = mt5.history_deals_get(_dt(2000, 1, 1), _dt.now()) or []
            for d in deals:
                if d.type != mt5.DEAL_TYPE_BALANCE:
                    continue
                if d.ticket in self._seen_balance_ops:
                    continue
                self._seen_balance_ops.add(d.ticket)
                if self._balance_ops_loaded:   # announce only ops that appear after startup
                    kind = "DEPOSIT" if d.profit >= 0 else "WITHDRAWAL"
                    log.warning(f"💰 {kind} ${d.profit:+,.2f} (ticket {d.ticket}) — netted out "
                                f"of lot-sizing, daily ratchet & trading-equity (L8).")
                    try:
                        from bridge_data import log_flow_event
                        log_flow_event(d.ticket, getattr(d, "time", 0), d.profit, kind)
                    except Exception:
                        pass
            self._balance_ops_loaded = True
        except Exception as e:
            log.debug(f"log_new_balance_ops failed: {e}")

    @property
    def daily_limit(self) -> float:
        return self.day_open_bal * DAILY_SL / 100

    @property
    def daily_left(self) -> float:
        return max(0.0, self.daily_limit - self.daily_loss)

    # ── Startup preload ───────────────────────────────────────
    def preload(self):
        """
        On bridge restart mid-day: load today's deal history so
        trades_today, daily_loss, last_trade_was_loss are correct.
        """
        info = mt5.account_info()
        if not info:
            return
        self.day_open_bal = info.equity
        # ratchet: on a mid-day restart we did not observe the earlier peak —
        # start the peak at max(day-open, current equity) (conservative).
        self.day_peak_equity = max(self.day_open_bal, info.equity)

        _today_ts  = broker_day_start_ts()
        _now_ts    = broker_now_ts()
        _2day_ts   = _today_ts - 48 * 3600

        # Retry up to 3× — MT5 may not be fully synced
        deals_pre = []
        for attempt in range(3):
            import time as _t
            deals_pre = mt5.history_deals_get(_today_ts, _now_ts) or []
            if deals_pre:
                break
            log.info(f"  ⏳ Deal history empty (attempt {attempt+1}/3) — retrying...")
            _t.sleep(2)

        # Extra 48h window to find entry deals (for position_id matching)
        deals_48h = mt5.history_deals_get(_2day_ts, _now_ts) or []
        _qgai_pos = {
            d.position_id for d in deals_48h
            if d.magic == MAGIC and d.entry == mt5.DEAL_ENTRY_IN
        }

        # All exits today (including manual/third-party close via position_id)
        closed_pre = [
            d for d in deals_pre
            if (d.magic == MAGIC or d.position_id in _qgai_pos)
            and d.entry == mt5.DEAL_ENTRY_OUT
            and d.time >= _today_ts
        ]

        # trades_today = opened AND closed today only (exclude carryover)
        entry_today = {
            d.position_id for d in deals_48h
            if d.magic == MAGIC and d.entry == mt5.DEAL_ENTRY_IN
            and d.time >= _today_ts
        }
        closed_today_only = [
            d for d in closed_pre if d.position_id in entry_today
        ]
        self._last_closed_count = len(closed_pre)
        # FIX #19: mark already-closed deals as processed so a mid-day
        # restart doesn't re-feed them to the learner / outcome writer.
        self._processed_deals.update(d.ticket for d in closed_pre)
        self.trades_today       = len(closed_today_only)

        # Adjust day_open_bal for P&L already made today
        if closed_pre:
            today_net_pnl = sum(d.profit + d.commission + d.swap for d in closed_pre)
            true_day_open = self.day_open_bal - today_net_pnl
            if abs(today_net_pnl) > 0.01:
                log.info(f"  📅 Mid-day restart: day_open_bal ${self.day_open_bal:.2f}"
                         f" - ${today_net_pnl:.2f} = ${true_day_open:.2f}")
                self.day_open_bal = max(true_day_open, 100.0)

        # Daily loss = sum of negative deals
        if closed_pre:
            losses = [d.profit + d.commission + d.swap for d in closed_pre
                      if d.profit + d.commission + d.swap < 0]
            self.daily_loss = abs(sum(losses)) if losses else 0.0

            last_pre = sorted(closed_pre, key=lambda d: d.time)[-1]
            last_net = last_pre.profit + last_pre.commission + last_pre.swap
            self.last_trade_was_loss = last_net < 0
            log.info(f"  ↩️ Preloaded {len(closed_pre)} deal(s) | "
                     f"daily_loss=${self.daily_loss:.2f} | "
                     f"last_was_loss={self.last_trade_was_loss}")

            # 2026-06-29: backfill the signal-log outcome (WIN/LOSS + net $) for trades
            # that closed while the bridge was OFF. write_outcome otherwise only runs in
            # the live loop's check_closed, so offline/cross-restart-closed trades showed
            # NO result in the signal log. (Anisa flagged: 06-29 02:45 SELL closed, blank.)
            try:
                _entry_orders = {d.position_id: d for d in deals_48h
                                 if d.magic == MAGIC and d.entry == mt5.DEAL_ENTRY_IN}
                _n = write_outcome(_entry_orders, closed_pre)
                log.info(f"  ↩️ Backfilled signal-log outcome for {len(closed_pre)} offline-closed deal(s)")
            except Exception as _woe:
                log.debug(f"preload write_outcome backfill failed: {_woe}")

            if self.daily_loss >= self.daily_limit:
                self.daily_sl_hit = True
                log.warning(f"  ⛔ Daily SL already breached on restart: "
                            f"${self.daily_loss:.2f} >= ${self.daily_limit:.2f}")
        else:
            log.info("  ↩️ No today's closed deals — daily_loss=$0")

    # ── check_closed (called every bar) ──────────────────────
    def check_closed(self, virtual_trades: dict):
        """
        Detect newly closed deals since last bar.
        Updates daily_loss, trades_today, last_trade_was_loss.
        Writes outcome back to SQLite + CSV.
        Force-closes all if daily SL hit.
        Returns list of newly closed deals (for caller to clean up virtual_trades).
        """
        _now_ts    = broker_now_ts()
        _today_ts  = broker_day_start_ts()
        _2day_ts   = _today_ts - 48 * 3600

        deals = mt5.history_deals_get(_today_ts, _now_ts)
        if not deals:
            return []

        deals_48h = mt5.history_deals_get(_2day_ts, _now_ts) or []
        entry_orders_today = {
            d.position_id: d for d in deals_48h
            if d.magic == MAGIC and d.entry == mt5.DEAL_ENTRY_IN
        }

        # All exits today (our positions, including manual close)
        closed = [
            d for d in deals
            if (d.magic == MAGIC or d.position_id in entry_orders_today)
            and d.entry == mt5.DEAL_ENTRY_OUT
        ]
        if not closed:
            return []

        # FIX #19: ticket-based "what's new" detection (was count-based,
        # which could miss deals when counts coincide, e.g. day rollover).
        new_deals = [d for d in closed if d.ticket not in self._processed_deals]
        if not new_deals:
            return []
        self._processed_deals.update(d.ticket for d in new_deals)
        self._last_closed_count = len(closed)

        # trades_today: opened AND closed today
        closed_today_only = [
            d for d in closed
            if d.position_id in entry_orders_today
            and entry_orders_today[d.position_id].time >= _today_ts
        ]
        self.trades_today = max(self.trades_today, len(closed_today_only))

        # last_trade_was_loss
        if closed_today_only:
            last_deal = sorted(closed_today_only, key=lambda d: d.time)[-1]
            last_net  = last_deal.profit + last_deal.commission + last_deal.swap
            self.last_trade_was_loss = last_net < 0
        elif closed:
            last_deal = sorted(closed, key=lambda d: d.time)[-1]
            last_net  = last_deal.profit + last_deal.commission + last_deal.swap
            self.last_trade_was_loss = last_net < 0

        # Daily loss = sum of negative deal nets
        loss_deals = [d.profit + d.commission + d.swap for d in closed
                      if d.profit + d.commission + d.swap < 0]
        net_loss = abs(sum(loss_deals)) if loss_deals else 0.0
        if round(net_loss, 2) != round(self.daily_loss, 2):
            self.daily_loss = net_loss
            limit = self.daily_limit
            if self.daily_loss >= limit and not self.daily_sl_hit:
                self.daily_sl_hit = True
                log.warning(f"⛔ DAILY SL HIT! ${self.daily_loss:.2f} >= ${limit:.2f}")
                for t_id in list(virtual_trades.keys()):
                    log.warning(f"  🛑 Force-closing #{t_id}")
                    _close_position(t_id)
                # Also catch any untracked positions
                remaining = mt5.positions_get(symbol=SYMBOL) or []
                for pos in remaining:
                    if pos.magic == MAGIC:
                        _close_position(pos.ticket)

        outcome_word = "LOSS" if self.last_trade_was_loss else "WIN"
        log.info(f"📊 NEW deal: {outcome_word} ${last_net:+.2f}")

        # Write outcomes to DB
        write_outcome(entry_orders_today, closed)

        # Shadow slot outcome
        for d in closed_today_only:
            entry_d = entry_orders_today.get(d.position_id)
            if entry_d:
                bar_dt = datetime.fromtimestamp(entry_d.time, tz=timezone.utc).replace(tzinfo=None)
                bar_dt = bar_dt.replace(minute=(bar_dt.minute // 15) * 15, second=0, microsecond=0)
                net = d.profit + d.commission + d.swap
                update_shadow_outcome(bar_dt, net, "BUY" if d.type == 0 else "SELL")

        # Update daily summary in DB
        wins   = sum(1 for d in closed if (d.profit + d.commission + d.swap) > 0)
        losses = sum(1 for d in closed if (d.profit + d.commission + d.swap) < 0)
        gross  = sum(d.profit + d.commission + d.swap for d in closed)
        if self._today_str:
            update_daily_summary(self._today_str, self.trades_today, wins, losses,
                                 round(gross, 2), self.day_open_bal)

        # FIX #5: return structured info about NEWLY closed deals so
        # bridge_main can feed them to engine.on_trade_closed()
        # (online learning / drift detection were never updated before).
        new_closed_info = []
        for d in new_deals:
            entry_d = entry_orders_today.get(d.position_id)
            net = round(d.profit + d.commission + d.swap, 2)
            if entry_d:
                open_dt = datetime.fromtimestamp(entry_d.time, tz=timezone.utc).replace(tzinfo=None)
                bar_dt  = open_dt.replace(minute=(open_dt.minute // 15) * 15,
                                          second=0, microsecond=0)
                direction = "BUY" if entry_d.type == mt5.ORDER_TYPE_BUY else "SELL"
            else:
                bar_dt    = None
                direction = "SELL" if d.type == mt5.ORDER_TYPE_BUY else "BUY"
            new_closed_info.append({
                "ticket":    d.position_id,
                "direction": direction,
                "net":       net,
                "label":     1 if net > 0 else 0,
                "volume":    d.volume,
                "bar_time":  bar_dt,
            })
        return new_closed_info

    # ── Intra-tick daily SL check ─────────────────────────────
    def check_daily_sl_intrabar(self, virtual_trades: dict) -> bool:
        """
        Called every 2s by monitor loop.
        Returns True if daily SL was just hit (caller should close all).
        """
        if self.daily_sl_hit or self.day_open_bal <= 0:
            return self.daily_sl_hit

        info = mt5.account_info()
        if not info:
            return False

        # ── RATCHET daily stop (2026-06-20) ──────────────────────────────
        # A trailing daily floor that is DAILY_SL% (of day-open) below the day's
        # PEAK equity, so it is BOTH a loss-floor AND a profit-lock:
        #   day open  : peak = open      -> floor = open - 9%  (= -9% hard floor)
        #   peak +5%  : floor = -4%
        #   peak +9%  : floor = break-even
        #   peak +12% : floor = +3%      (locks 3% profit for the day)
        # Uses live account equity (= day_open + realized + floating); the primary
        # account is QGAI-only so its equity is QGAI's equity.
        eq = info.equity - self._net_balance_flow_today()   # L8: flow-adjusted (deposits/withdrawals netted out)
        try:
            import bridge_manual; eq -= bridge_manual.manual_floating()   # L13: ignore manual leg + its hedges
        except Exception:
            pass
        if eq > self.day_peak_equity:
            self.day_peak_equity = eq
        floor = self.day_peak_equity - self.daily_limit   # daily_limit = day_open * DAILY_SL%
        if eq <= floor:
            self.daily_sl_hit = True
            _peak_pct = (self.day_peak_equity / self.day_open_bal - 1) * 100 if self.day_open_bal else 0
            _floor_pct = (floor / self.day_open_bal - 1) * 100 if self.day_open_bal else 0
            log.warning(f"⛔ DAILY RATCHET HIT! equity=${eq:,.2f} <= floor=${floor:,.2f} "
                        f"(day peak +{_peak_pct:.1f}% -> locked floor {_floor_pct:+.1f}%, {DAILY_SL:.0f}% trail)")
            for t_id in list(virtual_trades.keys()):
                log.warning(f"  🛑 Force-closing #{t_id}")
                _close_position(t_id)
            return True
        return False

    @property
    def daily_target_equity(self) -> float:
        """Equity level at which the daily profit target is reached."""
        return self.day_open_bal * (1.0 + DAILY_TP / 100.0)

    # ── Daily Equity TARGET check (EA-style, virtual) ─────────
    def check_daily_tp_intrabar(self, virtual_trades: dict) -> bool:
        """
        Called every 2s by monitor loop. EA-style equity target:
        equity >= day_open × (1 + DAILY_TP%)  →  close ALL + stop for the day.
        Pure virtual — broker never sees a TP order (just like vTP).
        Equity-based, so it is self-healing across restarts.
        """
        if not ENABLE_DAILY_TP:
            return False
        if self.daily_tp_hit or self.day_open_bal <= 0:
            return self.daily_tp_hit

        info = mt5.account_info()
        if not info:
            return False

        _eq_tp = info.equity - self._net_balance_flow_today()   # L8: flow-adjusted
        try:
            import bridge_manual; _eq_tp -= bridge_manual.manual_floating()   # L13: ignore manual leg + its hedges
        except Exception:
            pass
        if _eq_tp >= self.daily_target_equity:
            self.daily_tp_hit = True
            log.warning(f"🎯 DAILY TARGET HIT (+{DAILY_TP}%)! "
                        f"equity=${_eq_tp:,.2f} (flow-adj) >= "
                        f"target=${self.daily_target_equity:,.2f} "
                        f"(day open ${self.day_open_bal:,.2f}) — "
                        f"closing all, done for today ✅")
            for t_id in list(virtual_trades.keys()):
                log.warning(f"  🏁 Booking profit — closing #{t_id}")
                _close_position(t_id)
            return True
        return False

    # Trade-2 equity SL REMOVED 2026-06-19 (user request) — risk model is now
    # simply: per-trade SL = 3% of equity (risk_pct) + daily SL = 9% of equity.


# ── Position close helper (used by session, not by execute) ──

# 2026-07-01 (Imtiyaz): STUCK-TRADE MANUAL-PROTECT. If the broker keeps rejecting the
# close (e.g. retcode 10027 = AutoTrading disabled at the terminal — caught live on
# #1519547791), don't just log one [ERROR] and silently keep retrying forever. Track
# consecutive failures per ticket; past a threshold, escalate the alert every attempt AND
# (if enabled) place a protective hedge so the position's net P&L stops moving even though
# it can't be closed. MAGIC stays the bot's own (202600) — MT5 doesn't allow changing an
# existing position's magic — this is bookkeeping only, not a real "manual trade" re-tag.
_CLOSE_FAIL_COUNTS = {}   # ticket -> consecutive failed close attempts
_STUCK_HEDGED       = set()  # tickets we've already placed a FULL-lot protective hedge for
_STUCK_HEDGE_LOT    = {}   # ticket -> currently-hedged lot under the GRADUATED scheme (0 if none)


def _stuck_hedge_comment(ticket: int) -> str:
    return f"stuck_hedge_{ticket}"[:31]


def _place_stuck_hedge(pos):
    """Open an opposite-direction position — on its OWN DEDICATED magic (stuck_hedge_magic,
    202698 by default), deliberately NOT the L13 manual_hedge_magic (202699) pool. L13's
    manual-manager closes/sweeps every position matching manual_hedge_magic whenever ITS OWN
    floor/vSL/TP fires (magic-only filter — see bridge_manual.py _positions()), so sharing that
    magic would let it silently close this protective hedge out from under a stuck BOT trade
    that has nothing to do with a manual position. A separate magic keeps the two fully isolated.
    Best-effort — if the broker is rejecting ALL orders (e.g. AutoTrading truly off), this will
    fail too; that's still surfaced via the same escalated log line."""
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return False
    otype = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if otype == mt5.ORDER_TYPE_SELL else tick.ask
    req = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       SYMBOL,
        "volume":       pos.volume,
        "type":         otype,
        "price":        price,
        "deviation":    20,
        "magic":        int(getattr(CFG.filters, "stuck_hedge_magic", 202698)),
        "comment":      _stuck_hedge_comment(pos.ticket),
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    r = mt5.order_send(req)
    for fill in (mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN):
        if r is None or r.retcode == 10030:
            req["type_filling"] = fill
            r = mt5.order_send(req)
    if r and r.retcode == mt5.TRADE_RETCODE_DONE:
        log.warning(f"  🛡 #{pos.ticket} STUCK-PROTECT: opened hedge @ {price:.2f} "
                    f"({pos.volume} lot, opposite dir) — net P&L now ~frozen while close keeps retrying.")
        return True
    log.error(f"  ❌ #{pos.ticket} STUCK-PROTECT hedge ALSO failed: "
              f"{r.retcode if r else mt5.last_error()} — broker may be rejecting ALL orders "
              f"(check AutoTrading in the MT5 terminal).")
    return False


def _stuck_risk_hedge(pos, vsl: float | None):
    """GRADUATED protective hedge for a STUCK trade (Imtiyaz's spec, 2026-07-01).
    Instead of freezing the WHOLE lot the instant close fails (see _place_stuck_hedge),
    let risk stretch from the normal risk_pct (3%) up to leftover_risk_cap_pct (6%) and
    hedge ONLY the excess lot once the UNPROTECTED slippage — price having moved past the
    real vSL while close keeps failing — pushes risk beyond that stretched cap. Tops up the
    hedge incrementally as slippage grows further; never hedges more than pos.volume.
    `vsl` is the trade's REAL virtual SL (passed by the caller in bridge_core.py, which still
    holds the VirtualTrade object) — NOT reconstructed/guessed, so this stays accurate even
    across the mid-session retries a restart-recovery fallback can't see.
    No-op (no hedge) while slippage is still inside the stretched band — lets the position
    ride in case price comes back. Returns True if an order was sent (new or top-up)."""
    info = mt5.account_info()
    tick = mt5.symbol_info_tick(SYMBOL)
    if not info or not tick or vsl is None:
        return False
    equity = float(info.equity)
    si = mt5.symbol_info(SYMBOL)
    cs = float(getattr(si, "trade_contract_size", 0) or 0) if si else 0.0
    if cs <= 0:
        cs = 100.0
    cur = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

    # slippage = how far PAST the real vSL price already moved while close kept failing.
    slip_dist = (vsl - cur) if pos.type == mt5.ORDER_TYPE_BUY else (cur - vsl)
    if slip_dist <= 0:
        return False   # hasn't actually breached vSL (or has come back) — no excess risk yet

    base_pct  = float(getattr(CFG.filters, "risk_pct", 3.0))
    cap_pct   = float(getattr(CFG.filters, "leftover_risk_cap_pct", 6.0))
    extra_pct = max(0.0, cap_pct - base_pct)          # stretched headroom beyond the original 1R
    extra_usd = equity * extra_pct / 100.0

    slip_usd = pos.volume * cs * slip_dist
    if slip_usd <= extra_usd:
        return False   # still inside the stretched risk_pct→cap_pct band — let it ride

    allowed_lot = (extra_usd / (cs * slip_dist)) if (cs * slip_dist) > 0 else 0.0
    need_hedge  = round(max(0.0, min(pos.volume, pos.volume - allowed_lot)), 2)
    have_hedge  = _STUCK_HEDGE_LOT.get(pos.ticket, 0.0)
    delta       = round(need_hedge - have_hedge, 2)
    if delta <= 0:
        return False   # already hedged enough for the current slippage

    otype = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if otype == mt5.ORDER_TYPE_SELL else tick.ask
    req = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       SYMBOL,
        "volume":       delta,
        "type":         otype,
        "price":        price,
        "deviation":    20,
        "magic":        int(getattr(CFG.filters, "stuck_hedge_magic", 202698)),
        "comment":      _stuck_hedge_comment(pos.ticket),
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    r = mt5.order_send(req)
    for fill in (mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN):
        if r is None or r.retcode == 10030:
            req["type_filling"] = fill
            r = mt5.order_send(req)
    if r and r.retcode == mt5.TRADE_RETCODE_DONE:
        _STUCK_HEDGE_LOT[pos.ticket] = need_hedge
        log.warning(f"  🛡 #{pos.ticket} STUCK-PROTECT (graduated): slip ${slip_usd:,.0f} > "
                    f"stretched budget ${extra_usd:,.0f} ({base_pct:.0f}%→{cap_pct:.0f}% cap) — "
                    f"hedged {delta} more lot (total {need_hedge}/{pos.volume})")
        return True
    log.error(f"  ❌ #{pos.ticket} STUCK-PROTECT graduated hedge failed: "
              f"{r.retcode if r else mt5.last_error()}")
    return False


def _unwind_stuck_hedge(ticket: int):
    """Called once the original ticket's close finally succeeds — close the matching
    protective hedge (if one was placed) so nothing is left dangling. Filters by BOTH
    the dedicated stuck_hedge_magic AND the ticket-specific comment tag — belt and
    suspenders so this only ever touches a hedge WE placed for THIS ticket, never an
    L13 manual-manager hedge or a hedge for a different stuck trade."""
    if ticket not in _STUCK_HEDGED and ticket not in _STUCK_HEDGE_LOT:
        return
    tag = _stuck_hedge_comment(ticket)
    _magic = int(getattr(CFG.filters, "stuck_hedge_magic", 202698))
    for h in (mt5.positions_get(symbol=SYMBOL) or []):
        if h.magic == _magic and h.comment == tag:
            _close_position(h.ticket)
    _STUCK_HEDGED.discard(ticket)
    _STUCK_HEDGE_LOT.pop(ticket, None)


def _close_position(ticket: int, vsl: float | None = None) -> bool:
    """Close a position — tries IOC → FOK → RETURN filling modes.
    Returns True if the position is confirmed gone (already-gone counts as success),
    False if the close attempt failed and the position is still open. Callers (bridge_core.py)
    use this to decide whether to keep retrying — see the 2026-07-01 fix: they used to drop
    the ticket from virtual_trades unconditionally, which silently abandoned monitoring the
    moment a close failed once (broke the "bot will keep retrying" promise below). Now they
    only drop it once this returns True.
    `vsl` (optional): the trade's REAL virtual SL, passed by the caller from its live
    VirtualTrade object — used for the graduated stuck-risk hedge below (NOT reconstructed/
    guessed, so it's accurate even mid-session across many retries)."""
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        _CLOSE_FAIL_COUNTS.pop(ticket, None)
        _STUCK_HEDGED.discard(ticket)
        _STUCK_HEDGE_LOT.pop(ticket, None)
        return True
    pos  = positions[0]
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return False
    price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
    req = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       SYMBOL,
        "volume":       pos.volume,
        "type":         mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
        "position":     ticket,
        "price":        price,
        "magic":        MAGIC,
        "comment":      "QuantEdge_vSL_close",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    r = mt5.order_send(req)
    if r is None or r.retcode == 10030:
        req["type_filling"] = mt5.ORDER_FILLING_FOK
        r = mt5.order_send(req)
    if r is None or r.retcode == 10030:
        req["type_filling"] = mt5.ORDER_FILLING_RETURN
        r = mt5.order_send(req)
    if r and r.retcode == mt5.TRADE_RETCODE_DONE:
        log.info(f"  ✅ #{ticket} Closed @ {price:.2f}")
        _CLOSE_FAIL_COUNTS.pop(ticket, None)
        _unwind_stuck_hedge(ticket)
        return True
    else:
        err = r.retcode if r else mt5.last_error()
        log.error(f"  ❌ Close failed #{ticket}: {err}")
        _CLOSE_FAIL_COUNTS[ticket] = _CLOSE_FAIL_COUNTS.get(ticket, 0) + 1
        _fails = _CLOSE_FAIL_COUNTS[ticket]
        _thresh = int(getattr(CFG.filters, "stuck_close_fail_threshold", 3))
        if _fails >= _thresh:
            log.error(f"  🚨 #{ticket} STUCK — {_fails} consecutive close failures (last: {err}). "
                      f"The bot's exit decision is CORRECT but the broker keeps rejecting the order — "
                      f"likely AutoTrading is OFF in the MT5 terminal. Check it NOW; the position is "
                      f"still open and unprotected. Bot will keep retrying every check.")
            if getattr(CFG.filters, "leftover_excess_hedge_enabled", False):
                _stuck_risk_hedge(pos, vsl)
            elif getattr(CFG.filters, "stuck_trade_hedge_enabled", False) and ticket not in _STUCK_HEDGED:
                if _place_stuck_hedge(pos):
                    _STUCK_HEDGED.add(ticket)
        return False
