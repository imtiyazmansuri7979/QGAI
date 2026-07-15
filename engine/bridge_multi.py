"""
bridge_multi.py — QUANT GOLD AI v2
Multi-account trade execution.

When the primary MT5 (Vantage) fires a trade, this module sequentially
re-connects to each secondary account (Neex, OneFunded) and places the
same directional trade with independent lot sizing based on that account's
own equity.

Usage (called from bridge_core.py after primary execution):
    from bridge_multi import execute_secondary_accounts
    execute_secondary_accounts(direction, sl_dist, tp_p, primary_ticket)
"""

import MetaTrader5 as mt5
import math
import time
from bridge_constants import log, CFG, SYMBOL, MAGIC, RISK_PCT, VIRTUAL_SL, MAX_SPREAD_USD, SPREAD_WAIT_SEC
from bridge_risk import calc_lot

# ── Per-account health state (2026-07-07, Fable-5 dashboard fix) ──────────
# The mirror-account DD-brake bug silently rejected secondary orders while the
# dashboard showed a healthy primary trade. This module-level dict records the
# last known state of every account so the dashboard can surface a per-account
# health row + reject alert. Updated on connect + order attempt. Read via
# get_account_health().
ACCOUNT_HEALTH: dict = {}   # name -> {name, login, balance, equity, last_order, last_order_time, last_retcode, is_primary}
_LAST_SLAVE_MANUAL_MANAGE_TS = 0.0


def _record_health(name, login=None, balance=None, equity=None,
                   last_order=None, retcode=None, is_primary=False):
    import datetime as _dt
    rec = ACCOUNT_HEALTH.get(name, {})
    rec["name"] = name
    if login   is not None: rec["login"] = login
    if balance is not None: rec["balance"] = round(float(balance), 2)
    if equity  is not None: rec["equity"] = round(float(equity), 2)
    if last_order is not None:
        rec["last_order"] = last_order            # "FILLED" | "REJECTED" | "SKIPPED"
        rec["last_retcode"] = retcode
        try:
            rec["last_order_time"] = _dt.datetime.now().strftime("%H:%M:%S")
        except Exception:
            rec["last_order_time"] = ""
    rec["is_primary"] = bool(is_primary)
    ACCOUNT_HEALTH[name] = rec


def get_account_health() -> list:
    """Return per-account health rows for the dashboard (primary first)."""
    rows = list(ACCOUNT_HEALTH.values())
    rows.sort(key=lambda r: (not r.get("is_primary", False), r.get("name", "")))
    return rows


def _primary_candidates(_c):
    """Build the ordered list of PRIMARY-eligible accounts (failover list).

    Resolution order (first that exists wins):
      1. _c.MT5_PRIMARIES  — explicit list of >=1 primary dicts (preferred).
      2. accounts in _c.MT5_ACCOUNTS flagged {"primary": True}.
      3. the legacy single primary (MT5_PATH / MT5_LOGIN / MT5_PASS / MT5_SERVER).

    Each candidate is a dict: {name, path, login, pass, server, symbol}.
    Fully backward-compatible: with no new config the old single primary is used.
    """
    prims = getattr(_c, "MT5_PRIMARIES", None)
    if prims:
        return [p for p in prims if p.get("login")]

    flagged = [a for a in getattr(_c, "MT5_ACCOUNTS", []) if a.get("primary") and a.get("login")]
    if flagged:
        return flagged

    # Legacy fallback: the single primary defined by the top-level constants.
    return [{
        "name":   getattr(_c, "MT5_NAME", "Primary"),
        "path":   _c.MT5_PATH,
        "login":  _c.MT5_LOGIN,
        "pass":   _c.MT5_PASS,
        "server": _c.MT5_SERVER,
        "symbol": getattr(_c, "MT5_SYMBOL", SYMBOL),
    }]


def _warm_up_feed(symbol):
    """Force the freshly-connected terminal to (re)sync the symbol's data feed.

    After an account switch / reconnect, MT5 can keep serving STALE bars from
    copy_rates_from_pos until the symbol is re-selected and history is pulled.
    That stale window is what froze the vSL trail and delayed the flip exit.
    Selecting the symbol + a throwaway rates pull forces an immediate resync.
    """
    try:
        mt5.symbol_select(symbol, True)
        # Pull a tick and a few M15 bars to kick the terminal into syncing.
        mt5.symbol_info_tick(symbol)
        mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 2)
    except Exception as e:
        log.warning(f"⚠️ [multi] feed warm-up for {symbol} failed: {e}")


def connect_primary(reason: str = "") -> bool:
    """Connect to the PRIMARY account, failing over across MT5_PRIMARIES.

    Tries each candidate in order until one initializes + logs in + returns a
    valid account_info(). On success the symbol feed is warmed up so bar data
    is fresh immediately. Returns True on success, False if ALL primaries fail.

    This is the single entry point used by both the initial connect and every
    reconnect (after secondary executions / closes, and on lost-tick recovery),
    so a password change or dropped connection on one primary no longer halts
    trading — the next configured primary takes over automatically.
    """
    try:
        import config_mt5 as _c
    except ImportError:
        log.error("❌ [multi] config_mt5.py not found")
        return False

    candidates = _primary_candidates(_c)
    if not candidates:
        log.error("❌ [multi] No primary accounts configured")
        return False

    suffix = f" ({reason})" if reason else ""
    for i, acct in enumerate(candidates):
        name = acct.get("name", f"Primary{i+1}")
        try:
            mt5.shutdown()  # ensure a clean slate before re-init
            if not mt5.initialize(path=acct["path"]):
                log.warning(f"⚠️ [multi] primary '{name}' init failed: {mt5.last_error()} — trying next")
                continue
            if not mt5.login(acct["login"], password=acct["pass"], server=acct["server"]):
                log.warning(f"⚠️ [multi] primary '{name}' login failed: {mt5.last_error()} — trying next")
                mt5.shutdown()
                continue
            info = mt5.account_info()
            if not info:
                log.warning(f"⚠️ [multi] primary '{name}' account_info() None — trying next")
                mt5.shutdown()
                continue

            _warm_up_feed(acct.get("symbol", SYMBOL))
            tag = "" if i == 0 else f" [FAILOVER #{i+1}]"
            log.info(f"✅ [multi] Primary connected{suffix}{tag} | {name} #{info.login} | bal=${info.balance:,.2f}")
            return True
        except Exception as e:
            log.warning(f"⚠️ [multi] primary '{name}' exception: {e} — trying next")
            try:
                mt5.shutdown()
            except Exception:
                pass

    log.error(f"❌ [multi] ALL {len(candidates)} primary account(s) failed to connect{suffix}")
    return False


def _reconnect_primary():
    """Re-initialize the primary MT5 connection after secondary executions.
    Delegates to connect_primary() so reconnects also fail over AND resync the
    data feed (prevents the stale-bar window that froze the vSL trail)."""
    return connect_primary(reason="reconnect")


def _execute_on_account(acct: dict, direction: str, sl_dist: float, tp_p: int, comment: str = "QuantEdge AI") -> bool:
    """
    Connect to a single secondary MT5 account and place a trade.
    sl_dist: SL distance in price units (e.g. $7.50)
    tp_p:    TP distance in points
    Returns True if trade was sent successfully.
    """
    name = acct.get("name", "Unknown")
    try:
        # Skip placeholder accounts (login == 0 means not configured)
        if not acct.get("login"):
            log.warning(f"  ⚠️ [multi] {name}: login=0 — skipping (not configured)")
            _record_health(name, login=0, last_order="SKIPPED", retcode=None)
            return False

        log.info(f"  🔗 [multi] Connecting to {name}...")
        if not mt5.initialize(path=acct["path"]):
            log.error(f"  ❌ [multi] {name} initialize failed: {mt5.last_error()}")
            return False

        if not mt5.login(acct["login"], password=acct["pass"], server=acct["server"]):
            log.error(f"  ❌ [multi] {name} login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False

        info = mt5.account_info()
        if not info:
            log.error(f"  ❌ [multi] {name} account_info() returned None")
            mt5.shutdown()
            return False

        equity = info.equity if info.equity > 10 else 100.0
        log.info(f"  💰 [multi] {name} connected | balance=${info.balance:,.2f} | equity=${equity:,.2f}")
        _record_health(name, login=acct.get("login"), balance=info.balance, equity=info.equity)

        acct_symbol = acct.get("symbol", SYMBOL)
        tick = mt5.symbol_info_tick(acct_symbol)
        if not tick:
            log.error(f"  ❌ [multi] {name} no tick for {acct_symbol} — wrong symbol or market closed?")
            mt5.shutdown()
            return False

        # Optional spread guard
        if MAX_SPREAD_USD > 0:
            _spread = tick.ask - tick.bid
            if _spread > MAX_SPREAD_USD:
                waited = 0.0
                log.warning(f"  ⏳ [multi] {name} spread ${_spread:.2f} > ${MAX_SPREAD_USD:.2f} — waiting...")
                while _spread > MAX_SPREAD_USD and waited < SPREAD_WAIT_SEC:
                    time.sleep(1.0)
                    waited += 1.0
                    t2 = mt5.symbol_info_tick(acct_symbol)
                    if t2:
                        tick = t2
                        _spread = tick.ask - tick.bid
                if _spread > MAX_SPREAD_USD:
                    log.warning(f"  ⛔ [multi] {name} spread still ${_spread:.2f} — skipping")
                    mt5.shutdown()
                    return False

        si = mt5.symbol_info(acct_symbol)
        if not si:
            log.error(f"  ❌ [multi] {name} symbol_info({acct_symbol}) returned None")
            mt5.shutdown()
            return False

        pt = si.point

        # Independent lot sizing from this account's equity
        sl_p = max(100, int(sl_dist / pt))
        lot  = calc_lot(equity, sl_p, si)

        if direction == "BUY":
            otype      = mt5.ORDER_TYPE_BUY
            price      = tick.ask
            virtual_sl = round(price - sl_dist, 2)
            tp         = round(price + tp_p * pt, 2)
            broker_sl  = round(price - sl_dist * 3.0, 2) if VIRTUAL_SL else round(price - sl_p * pt, 2)
        else:
            otype      = mt5.ORDER_TYPE_SELL
            price      = tick.bid
            virtual_sl = round(price + sl_dist, 2)
            tp         = round(price - tp_p * pt, 2)
            broker_sl  = round(price + sl_dist * 3.0, 2) if VIRTUAL_SL else round(price + sl_p * pt, 2)

        req = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       acct_symbol,
            "volume":       lot,
            "type":         otype,
            "price":        price,
            "sl":           broker_sl,
            "tp":           tp,
            "deviation":    20,
            "magic":        MAGIC,
            "comment":      comment,
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
            log.info(f"  ✅ [multi] {name} {direction} {lot}lot @ {price:.2f} "
                     f"vSL:{virtual_sl:.2f} TP:{tp:.2f} ticket:#{r.order}")
            _record_health(name, last_order="FILLED", retcode=int(r.retcode))
            mt5.shutdown()
            return True
        else:
            err = r.retcode if r else mt5.last_error()
            log.error(f"  ❌ [multi] {name} order rejected: {err}")
            _record_health(name, last_order="REJECTED", retcode=(int(r.retcode) if r else None))
            mt5.shutdown()
            return False

    except Exception as e:
        log.error(f"  ❌ [multi] {name} exception: {e}", exc_info=True)
        try:
            mt5.shutdown()
        except Exception:
            pass
        return False


def execute_secondary_accounts(direction: str, sl_dist: float, tp_p: int, comment: str = "QuantEdge AI"):
    """
    Called by bridge_core after the primary trade is placed.
    Iterates MT5_ACCOUNTS[1:] (skips the primary) and places the
    same signal on each secondary account with independent lot sizing.
    Re-connects primary MT5 when done.
    """
    try:
        import config_mt5 as _c
        accounts = getattr(_c, "MT5_ACCOUNTS", [])
    except ImportError:
        log.warning("[multi] config_mt5.py not found — skipping secondary accounts")
        return

    # Secondary accounts = all except index 0 (primary)
    secondary = accounts[1:]
    if not secondary:
        return

    log.info(f"🔀 [multi] Replicating {direction} to {len(secondary)} secondary account(s)...")

    # Must disconnect primary before re-initializing for another account
    mt5.shutdown()

    for acct in secondary:
        _execute_on_account(acct, direction, sl_dist, tp_p, comment)

    # Restore primary connection
    _reconnect_primary()
    log.info("🔀 [multi] Secondary execution complete")


def manage_secondary_manual_accounts():
    """Run manual-trade manager on secondary/slave accounts.

    Only slave positions with magic=0 are treated as manual. Bot positions use
    MAGIC and remain handled by the normal mirror open/close code.
    """
    global _LAST_SLAVE_MANUAL_MANAGE_TS
    if not bool(getattr(CFG.filters, "manual_manager_enabled", False)):
        return
    if not bool(getattr(CFG.filters, "slave_manual_manager_enabled", False)):
        return
    interval = float(getattr(CFG.filters, "slave_manual_manage_interval_sec", 5.0) or 5.0)
    now = time.monotonic()
    if now - _LAST_SLAVE_MANUAL_MANAGE_TS < max(1.0, interval):
        return
    _LAST_SLAVE_MANUAL_MANAGE_TS = now

    try:
        import config_mt5 as _c
        import bridge_manual
        accounts = getattr(_c, "MT5_ACCOUNTS", [])
    except ImportError:
        return

    secondary = accounts[1:]
    if not secondary:
        return

    touched = False
    mt5.shutdown()
    for acct in secondary:
        name = acct.get("name", "Unknown")
        if not acct.get("login"):
            continue
        try:
            if not mt5.initialize(path=acct["path"]):
                log.error(f"  [multi-manual] {name} initialize failed: {mt5.last_error()}")
                continue
            if not mt5.login(acct["login"], password=acct["pass"], server=acct["server"]):
                log.error(f"  [multi-manual] {name} login failed: {mt5.last_error()}")
                continue
            info = mt5.account_info()
            acct_symbol = acct.get("symbol", SYMBOL)
            if info:
                _record_health(name, login=acct.get("login"), balance=info.balance, equity=info.equity)
            mt5.symbol_select(acct_symbol, True)
            manual_count = len([p for p in (mt5.positions_get(symbol=acct_symbol) or []) if p.magic == 0])
            if manual_count:
                log.info(f"  [multi-manual] {name}: managing {manual_count} manual position(s) on {acct_symbol}")
            bridge_manual.manage(acct_symbol)
            touched = True
        except Exception as e:
            log.error(f"  [multi-manual] {name} exception: {e}", exc_info=True)
        finally:
            mt5.shutdown()

    if touched:
        _reconnect_primary()


def close_secondary_accounts():
    """
    Close all open QGAI positions on every secondary account.
    Called whenever the primary closes a trade (vSL, TP, flip, smart exit).
    Primary must already be connected — this disconnects and reconnects it.
    """
    try:
        import config_mt5 as _c
        accounts = getattr(_c, "MT5_ACCOUNTS", [])
    except ImportError:
        return

    secondary = accounts[1:]
    if not secondary:
        return

    log.info("🔀 [multi] Closing secondary accounts...")
    mt5.shutdown()

    for acct in secondary:
        name = acct.get("name", "Unknown")
        if not acct.get("login"):
            continue
        try:
            if not mt5.initialize(path=acct["path"]):
                log.error(f"  ❌ [multi] {name} initialize failed: {mt5.last_error()}")
                continue
            if not mt5.login(acct["login"], password=acct["pass"], server=acct["server"]):
                log.error(f"  ❌ [multi] {name} login failed: {mt5.last_error()}")
                mt5.shutdown()
                continue

            acct_symbol = acct.get("symbol", SYMBOL)
            positions = mt5.positions_get(symbol=acct_symbol) or []
            qgai_pos  = [p for p in positions if p.magic == MAGIC]

            if not qgai_pos:
                log.info(f"  ℹ️ [multi] {name}: no open QGAI positions")
                mt5.shutdown()
                continue

            for pos in qgai_pos:
                tick = mt5.symbol_info_tick(acct_symbol)
                if not tick:
                    log.error(f"  ❌ [multi] {name} no tick for {acct_symbol}")
                    continue
                close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
                price      = tick.bid if pos.type == 0 else tick.ask
                req = {
                    "action":       mt5.TRADE_ACTION_DEAL,
                    "symbol":       acct_symbol,
                    "volume":       pos.volume,
                    "type":         close_type,
                    "position":     pos.ticket,
                    "price":        price,
                    "magic":        MAGIC,
                    "comment":      "QuantEdge_close_secondary",
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
                    log.info(f"  ✅ [multi] {name} #{pos.ticket} closed @ {price:.2f}")
                else:
                    err = r.retcode if r else mt5.last_error()
                    log.error(f"  ❌ [multi] {name} #{pos.ticket} close failed: {err}")

        except Exception as e:
            log.error(f"  ❌ [multi] {name} close exception: {e}", exc_info=True)
        finally:
            mt5.shutdown()

    _reconnect_primary()
    log.info("🔀 [multi] Secondary close complete")


def log_all_accounts():
    """
    Print a summary table of all configured accounts (balance, equity, open P&L).
    Called at bridge startup and can be called any time.
    Primary must already be connected — this disconnects and reconnects it.
    """
    try:
        import config_mt5 as _c
        accounts = getattr(_c, "MT5_ACCOUNTS", [])
    except ImportError:
        return

    if not accounts:
        return

    log.info("=" * 60)
    log.info("  ACCOUNT SUMMARY")
    log.info("=" * 60)

    # Snapshot primary (already connected) before cycling
    primary_info = mt5.account_info()
    primary_name = accounts[0].get("name", "Primary") if accounts else "Primary"
    rows = []

    if primary_info:
        open_pos  = mt5.positions_get(symbol=None) or []
        open_pnl  = sum(p.profit for p in open_pos)
        rows.append((primary_name, primary_info.login,
                     primary_info.balance, primary_info.equity, open_pnl,
                     len(open_pos), "OK"))
    else:
        rows.append((primary_name, 0, 0, 0, 0, 0, "ERROR"))

    # Cycle secondary accounts
    mt5.shutdown()
    for acct in accounts[1:]:
        name = acct.get("name", "?")
        if not acct.get("login"):
            rows.append((name, 0, 0, 0, 0, 0, "NOT CONFIGURED"))
            continue
        try:
            ok = mt5.initialize(path=acct["path"])
            if ok:
                ok = mt5.login(acct["login"], password=acct["pass"], server=acct["server"])
            if ok:
                info = mt5.account_info()
                if info:
                    open_pos = mt5.positions_get(symbol=None) or []
                    open_pnl = sum(p.profit for p in open_pos)
                    rows.append((name, info.login, info.balance, info.equity,
                                 open_pnl, len(open_pos), "OK"))
                else:
                    rows.append((name, acct["login"], 0, 0, 0, 0, "NO INFO"))
            else:
                rows.append((name, acct["login"], 0, 0, 0, 0, "LOGIN FAIL"))
        except Exception as e:
            rows.append((name, acct.get("login", 0), 0, 0, 0, 0, f"ERR:{e}"))
        finally:
            mt5.shutdown()

    # Print table
    total_bal = total_eq = total_pnl = 0
    for name, login, bal, eq, pnl, n_pos, status in rows:
        icon = "OK" if status == "OK" else "!!"
        pnl_str = f"${pnl:+.2f}" if status == "OK" else "  --  "
        pos_str = f"{n_pos} open" if status == "OK" else ""
        log.info(f"  [{icon}] {name:<12} #{login:<10} "
                 f"Bal=${bal:>10,.2f}  Eq=${eq:>10,.2f}  "
                 f"PnL={pnl_str:<10} {pos_str}  [{status}]")
        if status == "OK":
            total_bal += bal
            total_eq  += eq
            total_pnl += pnl

    log.info("-" * 60)
    log.info(f"  {'TOTAL':<12} {'':10}  "
             f"Bal=${total_bal:>10,.2f}  Eq=${total_eq:>10,.2f}  "
             f"PnL=${total_pnl:+.2f}")
    log.info("=" * 60)

    # Restore primary
    _reconnect_primary()
