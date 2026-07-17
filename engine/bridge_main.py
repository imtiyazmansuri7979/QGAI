"""
bridge_main.py â€” QUANT GOLD AI v2
Main run loop: bar detection, signal evaluation, trade dispatch.
Entry point: python bridge_main.py
"""
import sys
import os
import subprocess
import atexit
import MetaTrader5 as mt5
import time
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path

from bridge_constants import (
    log, CFG, SYMBOL, TIMEFRAME, MAGIC,
    broker_day_start_ts, broker_now_ts, broker_now_dt, get_sym_info,
    ensure_db, TEST_MODE, USE_CLOSED_BAR,
    RATCHET_EXIT, RATCHET_BUF_PCT, RATCHET_TP_CAP_PCT, RATCHET_FLIP_EXIT,
    MAX_SPREAD_USD, SPREAD_WAIT_SEC,
)
from bridge_session import Session
from bridge_core    import QGAICore
from bridge_dashboard import write_dashboard, read_mode, set_mode, is_allowed_slot
from bridge_data    import log_signal, record_shadow_signal
import bridge_multi   # Bug A fix: flatten secondaries on check_closed daily-SL halt
import bridge_manual  # L13: manual-trade manager (config-gated, default OFF) â€” PRIMARY account only

# â”€â”€ Inference engine â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from inference import LiveInferenceEngine, trend_pullback_block, trend_pullback_generate, smma_mtf_soft_block, adx_strength_soft_block


# â”€â”€ Singleton lock (2026-07-17, Imtiyaz rule 8): refuse to start a second â”€â”€
# bridge_main.py while one is already running. Two live processes independently
# managing order flow (manual-hedge top-up/trim, vSL ratchet, etc.) could race
# and double-hedge / place conflicting orders.
_LOCK_FILE = Path(CFG.paths.logs_dir) / "bridge.lock"


def _pid_alive(pid):
    if os.name == "nt":
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                stderr=subprocess.DEVNULL, text=True, timeout=5)
            return str(pid) in out
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _acquire_singleton_lock():
    my_pid = os.getpid()
    if _LOCK_FILE.exists():
        try:
            old_pid = int((_LOCK_FILE.read_text(encoding="utf-8") or "0").strip())
        except Exception:
            old_pid = None
        if old_pid and old_pid != my_pid and _pid_alive(old_pid):
            log.error(f"ðŸš« Another bridge_main.py is already running (PID {old_pid}). "
                      f"Refusing to start a duplicate â€” two live processes could race and "
                      f"double-hedge / place conflicting orders. If that process is actually "
                      f"dead, delete {_LOCK_FILE} and restart.")
            sys.exit(1)
    try:
        _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LOCK_FILE.write_text(str(my_pid), encoding="utf-8")
        atexit.register(lambda: _LOCK_FILE.unlink(missing_ok=True))
    except Exception as e:
        log.warning(f"bridge singleton-lock write failed (continuing anyway): {e}")


# â”€â”€ Live OHLC / ADX helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def get_live_ohlc(n_bars=250):
    """Fetch last N M15 bars from MT5 with computed features."""
    try:
        rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, n_bars)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={"tick_volume": "volume"})
        # L7b 2026-06-29: ATR20 (prev_close/tr/atr20/atr20_pct) + vol_zscore/vol_spike REMOVED
        # â€” none used by any model (ATR/volume pruned). Only range_pct/body_pct kept.
        df["range_pct"]  = ((df["high"] - df["low"]) / df["close"] * 100).round(4)
        df["body_pct"]   = (abs(df["close"] - df["open"]) / df["close"] * 100).round(4)
        # FIX #8: the last row is the CURRENT FORMING bar (seconds old,
        # near-zero range/volume) â€” not what the models were trained on.
        # Drop it so all features come from CLOSED bars only.
        if USE_CLOSED_BAR and len(df) > 1:
            df = df.iloc[:-1].reset_index(drop=True)
        return df
    except Exception as e:
        log.warning(f"get_live_ohlc failed: {e}")
        return None


def _write_chart_ohlc_snapshot(live_ohlc):
    """Save the bridge's real closed M15 OHLC snapshot for chart.html."""
    try:
        if live_ohlc is None or live_ohlc.empty:
            return
        out = live_ohlc[["time", "open", "high", "low", "close"]].copy()
        out["time"] = pd.to_datetime(out["time"], errors="coerce")
        out = out.dropna(subset=["time"]).sort_values("time").tail(500)
        out["time"] = out["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
        p = Path(CFG.paths.logs_dir) / "chart_ohlc_live.csv"
        tmp = p.with_suffix(".csv.tmp")
        out.to_csv(tmp, index=False)
        tmp.replace(p)
    except Exception as e:
        log.debug(f"chart OHLC snapshot write failed: {e}")


def get_live_adx(n_bars=50, bar_dt=None):
    """Live ADX/DI/band features for the LAST CLOSED M15 bar — SAME as-of
    pipeline as the training data (regen_adx_asof.asof_tf).

    FIX 2026-07-03 (Divyesh, HMM v3 deploy crash): the old inline calc produced
    ONLY {TF}_ADX + {TF}_DI_diff → the new HMM columns (di_eff / band_rel /
    band_width_pct / PlusDI / MinusDI) were NaN on live-appended rows →
    GaussianMixture "Input X contains NaN" crash on every bar. Worse, the old
    calc used UNSMOOTHED DX as "ADX" and last-CLOSED HTF bars — neither matched
    training. Now: pull ~5000 M15 bars (enough for Wilder warmup + 30D band_rel
    baseline), drop the forming M15 bar, and compute every column per TF with
    the exact training pipeline. Train == live by construction."""
    try:
        from regen_adx_asof import asof_tf
        rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M15, 0, 5000)
        if rates is None or len(rates) < 500:
            log.warning("get_live_adx: not enough M15 history from MT5")
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        # FIX #8: last row = forming M15 bar — exclude (closed bars only)
        if USE_CLOSED_BAR and len(df) > 1:
            df = df.iloc[:-1]
        df = df.set_index("time")[["open", "high", "low", "close"]].sort_index()
        # FAB-H6 (2026-07-07): when a PAST bar_dt is requested (overnight replay /
        # backfill), truncate history to bars AT-OR-BEFORE bar_dt so the computed
        # ADX/DI/band reflect what was known THEN — not today's latest values
        # stamped onto an old timestamp (lookahead contamination of the shadow
        # ledger / BACKFILL rows). For the live loop bar_dt≈now so this is a no-op.
        if bar_dt is not None:
            try:
                _cut = pd.Timestamp(bar_dt)
                _sliced = df[df.index <= _cut]
                if len(_sliced) >= 500:   # keep only if enough warmup remains
                    df = _sliced
                else:
                    log.debug(f"get_live_adx: as-of slice for {bar_dt} left <500 bars — using full history")
            except Exception as _se:
                log.debug(f"get_live_adx as-of slice failed ({bar_dt}): {_se}")
        merged = {}
        for tf, rule in [("M15", "15min"), ("M30", "30min"),
                         ("H1", "1h"), ("H4", "4h")]:
            adx_t, pdi_t, ndi_t, band_t = asof_tf(df, rule)
            band = band_t.round(4)
            band_rel = (band / band.rolling("30D").mean()).fillna(1.0)
            _p = float(pdi_t.iloc[-1]); _n = float(ndi_t.iloc[-1])
            merged[f"{tf}_ADX"]            = round(float(adx_t.iloc[-1]), 2)
            merged[f"{tf}_DI_diff"]        = round(_p - _n, 2)
            merged[f"{tf}_PlusDI"]         = round(_p, 2)
            merged[f"{tf}_MinusDI"]        = round(_n, 2)
            merged[f"{tf}_band_width_pct"] = float(band.iloc[-1])
            merged[f"{tf}_di_eff"]         = round(100 * abs(_p - _n) / (_p + _n + 1e-9), 2)
            merged[f"{tf}_band_rel"]       = round(float(band_rel.iloc[-1]), 4)
        if any(pd.isna(v) for v in merged.values()):
            log.warning(f"get_live_adx: NaN in computed features — skipping row: "
                        f"{ {k: v for k, v in merged.items() if pd.isna(v)} }")
            return None
        _adx_df = pd.DataFrame([merged])
        # FIX #22b: live ADX must carry a datetime key or the engine's
        # drop_duplicates("datetime") discards it entirely.
        if bar_dt is not None:
            _adx_df["datetime"] = pd.Timestamp(bar_dt)
        return _adx_df
    except Exception as e:
        log.warning(f"get_live_adx failed: {e}")
        return None


# â”€â”€ L11: startup resume prompt â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _ask_resume(signal, price, win_prob, timeout):
    """On startup, ask whether to enter on the FIRST (possibly stale, off-period) signal.
    Returns True only if the user types y/yes within `timeout` seconds; otherwise NO (safe
    default â†’ skip the stale signal and wait for the next live one). Cross-platform (thread)."""
    import threading
    ans = {"v": None}
    def _read():
        try: ans["v"] = input().strip().lower()
        except Exception: ans["v"] = ""
    try:
        print(f"\n  â“ RESUME — take a trade on the LAST signal: {signal} @ {price:.2f} "
              f"(win {win_prob:.2%})?  [y / N]  ({int(timeout)}s, else NO): ", end="", flush=True)
    except Exception:
        pass
    t = threading.Thread(target=_read, daemon=True); t.start(); t.join(timeout)
    yes = (ans["v"] in ("y", "yes"))
    log.warning(f"  ðŸ”š Resume decision: {'YES — entering at risk_pct' if yes else 'NO / timeout — skipping the last signal, waiting for the next'}")
    return yes


# â”€â”€ Main run loop â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def run():
    _acquire_singleton_lock()
    log.info("=" * 50)
    log.info("  QUANT GOLD AI v2 — Bridge Starting")
    log.info("=" * 50)

    # Ensure SQLite tables exist
    ensure_db()

    # Load model
    log.info("Loading AI models...")
    engine = LiveInferenceEngine()
    log.info("✅ Models loaded")

    # Session + Core
    session = Session()
    core    = QGAICore(session)
    core.engine = engine

    # Connect MT5
    if not core.connect():
        log.error("âŒ MT5 connection failed — exiting")
        return

    # Set capital so inference engine allows trading
    info = mt5.account_info()
    if info:
        engine.update_capital(info.equity)
        log.info(f"💰 Capital set: ${info.equity:,.2f}")

    # Show all account balances at startup
    from bridge_multi import log_all_accounts
    log_all_accounts()

    # Load news
    news_df = None
    try:
        news_df = pd.read_csv(CFG.paths.news_file)
        try:
            news_df["datetime"] = pd.to_datetime(news_df["timestamp"], utc=True).dt.tz_convert(None)
        except Exception:
            news_df["datetime"] = pd.to_datetime(news_df["timestamp"], errors="coerce")
        log.info(f"✅ News loaded: {len(news_df):,} events")
    except Exception as e:
        log.warning(f"âš ï¸ News load failed: {e}")

    # FAB-S2 (2026-07-07): assert news calendar isn't stale — silent-zero
    # of pre-news / news-routing features caused ~7 weeks of blind NFP/CPI
    # trading before Fable-5 audit caught it.
    try:
        from news_updater import check_staleness
        _news_max = int(getattr(CFG.filters, "news_max_stale_days", 7) or 7)
        _news_status = check_staleness(max_days=_news_max)
        if _news_status.get("stale"):
            _reason = _news_status.get("reason", "unknown")
            _last   = _news_status.get("last_event", "?")
            _next   = _news_status.get("next_event", "None")
            _days   = _news_status.get("days_old", "?")
            log.error("=" * 68)
            log.error(f"NEWS CALENDAR STALE - {_reason}")
            log.error(f"   last event: {_last}  ({_days} days old)")
            log.error(f"   next event: {_next}")
            log.error(f"   Consequence: is_pre_news/is_post_news/mins_to_next_3star will be WRONG.")
            log.error(f"   Pre-news threshold bump and news-model routing effectively OFF.")
            log.error(f"   Fix: run  python engine/news_updater.py  OR manually append rows.")
            log.error("=" * 68)
            if bool(getattr(CFG.filters, "pause_if_news_stale", False)):
                log.error("pause_if_news_stale=True - refusing to start until calendar refreshed.")
                sys.exit(1)
        else:
            log.info(f"News calendar OK  last={_news_status.get('last_event')}  "
                     f"next={_news_status.get('next_event')}  age={_news_status.get('days_old')}d")
    except Exception as _ne:
        log.warning(f"news staleness check failed: {_ne}")

    # Preload today's session state
    session.preload()

    # Recover any open positions
    core.recover_open_trades()

    # Overnight replay (shadow tracking)
    _overnight_replay(engine, core, session, news_df)

    # Initial dashboard write
    _pre_pop_dashboard(engine, core, session, news_df)

    # â”€â”€ Bar loop â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    last_bar_time = None
    _resume_pending = getattr(CFG.filters, "resume_prompt_on_start", False)  # L11: ask once, on the first actionable signal
    # 2026-06-30 (Anisa): resume prompt is STRICTLY startup-only. If a trade is already open
    # at startup (recovered above), skip it entirely â€” do NOT defer to mid-session (can't take
    # a 2nd trade anyway). So the prompt fires ONLY when the bot starts FLAT, never later.
    if _resume_pending and core.virtual_trades:
        _resume_pending = False
        log.info("  â„¹ï¸ Resume prompt skipped — a trade is already open at startup (nothing to resume).")
    last_date     = None
    monitor_count = 0
    # Loop heartbeat: how often to poll tick / monitor vSL. 1s = more
    # responsive vSL/vTP exits (was 2s). Error-recovery sleeps stay longer.
    POLL_SEC      = 1.0
    # verbose-log cadence: log every 1s (every poll)
    _verbose_every = 1
    # Heartbeat + feed-resync cadence (in polls). During quiet stretches â€”
    # especially when trading is HALTED for the day after the daily/2nd-SL
    # stop â€” the window used to go totally silent and looked CRASHED. We now
    # emit a heartbeat (~every 60s) so the bridge visibly stays ALIVE.
    # _resync_every = 1 â†’ the data feed is re-subscribed EVERY second so
    # copy_rates can never sit on a stale bar (feed refreshed every second).
    _hb_every     = 60
    _resync_every = 1

    log.info(f"🚀 Live trading on {SYMBOL} M15 | Ctrl+C to stop")
    # â”€â”€ FULL CONFIG DUMP â€” print every critical live setting so the
    #    operator can verify the running config at a glance (no guessing).
    from bridge_constants import (
        RISK_PCT, DAILY_SL, DAILY_TP, ENABLE_DAILY_TP, RATCHET_MAX_RISK_PCT,
        MAX_SIMULTANEOUS, MAGIC,
    )
    _fl  = getattr(CFG.filters, "use_fixed_lot", False)
    _flv = getattr(CFG.filters, "fixed_lot", 0.01)
    log.info("=" * 60)
    log.info("  ⚙️  RUNNING CONFIG (verify before trading)")
    log.info("=" * 60)
    log.info(f"  Symbol/TF   : {SYMBOL} M15 | magic {MAGIC} | max open {MAX_SIMULTANEOUS}")
    if RATCHET_EXIT:
        _tpd = "regime (Rng2.0/Trn1.0/Vol0.8%)" if getattr(CFG.filters, "ratchet_tp_regime", False) else f"{RATCHET_TP_CAP_PCT}% cap"
        if getattr(CFG.filters, "ratchet_htf_sl", False):
            _sld = f"HTF {getattr(CFG.filters,'ratchet_htf_tf','H1')}" + (" forming" if getattr(CFG.filters,'ratchet_htf_forming',False) else " last-closed") + f" (max {getattr(CFG.filters,'ratchet_htf_max_risk_pct',2.5)}%)"
        else:
            _sld = f"M15 (max {RATCHET_MAX_RISK_PCT}%)"
        log.info(f"  RATCHET     : ON ✅ | buf {RATCHET_BUF_PCT}%·line | TP {_tpd} | flip {RATCHET_FLIP_EXIT} | SL-line {_sld}")
    else:
        log.info(f"  RATCHET     : OFF âš ï¸ — no valid SL when ratchet disabled")
    if _fl:
        log.info(f"  SIZING      : FIXED LOT {_flv} (forward-test) | risk% ignored")
    else:
        log.info(f"  SIZING      : {RISK_PCT}% risk + compounding")
    log.info(f"  DAILY SL    : {DAILY_SL}% | DAILY TP : {DAILY_TP}% (on={ENABLE_DAILY_TP})")
    # 2026-06-30 (4-round bug-check, Anisa): the old PARTIAL / TRAIL/BE / SMART-EXIT lines were
    # STALE â€” that code was REMOVED in L7b (pure-ratchet only). Show the real exit config instead.
    log.info(f"  EXIT        : pure ratchet (line + flip) — partial / BE / R-trail / smart-exit NOT used (removed L7b)")
    if MAX_SPREAD_USD > 0:
        log.info(f"  SPREAD GUARD: max ${MAX_SPREAD_USD:.2f} | wait {SPREAD_WAIT_SEC:.0f}s then fire")
    else:
        log.info("  SPREAD GUARD: OFF")
    log.info(f"  LOOP        : {POLL_SEC}s heartbeat")
    # 2026-07-07: surface entry-filter + protective states for restart verification.
    _ctf = getattr(CFG.filters, "skip_counter_trend_fade", False)
    _rng = getattr(CFG.filters, "skip_range_phase_entry", False)
    _ddb = getattr(CFG.filters, "enable_live_dd_brake", False)
    _grev = getattr(CFG.filters, "gate_reversal_entries", False)
    log.info(f"  ENTRY GATES : range-phase {'ON' if _rng else 'OFF'} | "
             f"counter-trend-fade {'ON' if _ctf else 'OFF ✅(Path-A +34R)'} | "
             f"reversal-gated {'ON' if _grev else 'OFF(legacy)'}")
    log.info(f"  DD BRAKE    : {'ON ✅ (dd>10%→½ 20%→¼ 30%→halt)' if _ddb else 'OFF'} | "
             f"vSL persist ON")
    log.info("=" * 60)

    while True:
        try:
            tick = mt5.symbol_info_tick(SYMBOL)
            if not tick:
                # AUTO-RECONNECT: the primary feeds data AND is the leader for the
                # secondary/slave accounts. If it drops, don't just wait â€” actively
                # re-login so the leader (and the slaves) recover without a manual
                # restart. Keeps retrying every loop until the primary is back.
                log.warning("âš ï¸ No tick — primary MT5 disconnected? Attempting reconnectâ€¦")
                _reconnected = False
                for _attempt in range(1, 4):
                    try:
                        core.disconnect()
                    except Exception:
                        pass
                    time.sleep(3)
                    if core.connect():
                        log.info(f"✅ Primary reconnected (attempt {_attempt}) — leader restored")
                        _reconnected = True
                        break
                    log.warning(f"âš ï¸ Reconnect attempt {_attempt} failed — retryingâ€¦")
                if not _reconnected:
                    log.error("âŒ Primary still down — will keep retrying next loop")
                    time.sleep(5)
                continue

            # â”€â”€ Intra-bar monitor â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            monitor_count += 1
            verbose = (monitor_count % _verbose_every == 0)   # ~every 30s
            core.monitor_virtual_sl(verbose=verbose)
            # mirror_to_slaves=True: ONLY this (primary) call site may mirror a new
            # manual trade out to the secondaries — the slave-side manager must never
            # (2026-07-15, Imtiyaz). Still gated by manual_copy_to_slaves_enabled.
            try: bridge_manual.manage(mirror_to_slaves=True)
            except Exception as _me: log.error(f"manual manager error: {_me}", exc_info=True)
            try: bridge_multi.manage_secondary_manual_accounts()
            except Exception as _se: log.error(f"secondary manual manager error: {_se}", exc_info=True)

            # Write dashboard EVERY poll (was gated on open trades â†’ froze the
            # price/dashboard after a trade closed until the next bar). Now the
            # live price updates every 1s whether or not a trade is open.
            # 2026-07-09 (Imtiyaz-reported mismatch): this heartbeat re-sends the SAME
            # core._last_signal dict from the last real bar-close (unchanged) every ~30s
            # between bar closes. Hardcoding signal_confirmed=False here made the SIGNAL
            # box + AI DECISION SUMMARY hide an already-decided BUY/SELL behind SKIP for
            # the whole ~15min until the next bar close (while EV/Grade/AI-summary %s kept
            # showing the real BUY — the tell-tale mismatch vs the SIGNAL LOG). confirmed
            # must reflect whether core._last_signal is an actual decided signal (any
            # bar-close call, or the startup pre-pop probe, sets its "signal" key), not
            # whether THIS particular write is a heartbeat vs a fresh bar.
            if verbose:
                write_dashboard(session, core.virtual_trades, tick.bid,
                                core._last_signal, _engine_meta(engine),
                                signal_confirmed=bool(core._last_signal.get("signal")))

            # â”€â”€ Bar detection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 1)
            if rates is None or len(rates) == 0:
                time.sleep(POLL_SEC)
                continue

            bar_time = datetime.fromtimestamp(rates[0]["time"], tz=timezone.utc).replace(tzinfo=None)
            if bar_time == last_bar_time:
                # Quiet stretch (no new bar yet). This is exactly where the
                # window went silent after the daily/2nd-SL halt and looked
                # crashed. Keep it visibly ALIVE and keep the feed fresh:
                #   • re-subscribe the symbol so copy_rates can't stay stale
                #     (the stale-bar freeze that mimicked a crash), and
                #   • emit a heartbeat showing HALTED-vs-live state.
                if monitor_count % _resync_every == 0:
                    try:
                        mt5.symbol_select(SYMBOL, True)
                    except Exception:
                        pass
                if monitor_count % _hb_every == 0:
                    _hb_state = "⏸ HALTED (daily SL hit) — paused for the day" if session.daily_sl_hit else "live"
                    log.info(f"💓 heartbeat — {_hb_state} | price {tick.bid:.2f} | last bar {bar_time:%H:%M} | ALIVE")
                time.sleep(POLL_SEC)
                continue

            last_bar_time = bar_time
            broker_dt = broker_now_dt(tick.time)
            log.info(f"── New bar: {bar_time} ── [Broker: {broker_dt.strftime('%H:%M')}]")

            # FIX #11: scheduler writes logs/.reload_requested after a
            # successful retrain, but nothing ever read it â€” the bridge
            # kept trading on OLD models until manually restarted.
            try:
                _reload_flag = Path(CFG.paths.logs_dir) / ".reload_requested"
                if _reload_flag.exists():
                    log.info("ðŸ”„ Reload flag found — reloading models after retrain...")
                    engine = LiveInferenceEngine()
                    core.engine = engine
                    _ri = mt5.account_info()
                    if _ri:
                        engine.update_capital(_ri.equity)
                    _reload_flag.unlink()
                    log.info("✅ Models reloaded — trading on fresh weights")
            except Exception as _re_e:
                log.error(f"âŒ Model reload failed (keeping old models): {_re_e}")

            # â”€â”€ Day rollover check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            today = datetime.fromtimestamp(rates[0]["time"], tz=timezone.utc).date()
            if last_date and today != last_date:
                info = mt5.account_info()
                eq   = info.equity if info else session.day_open_bal
                session.reset_daily(eq, str(today))
                log.info(f"ðŸ—“ Broker day: {last_date} â†’ {today}")
            last_date = today

            # â”€â”€ check_closed â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            _was_halted = session.daily_sl_hit
            new_closed = session.check_closed(core.virtual_trades)
            # Bug A fix: check_closed's DAILY-SL force-close flattens only the
            # PRIMARY terminal. Flatten secondaries too â€” but ONLY on the fresh
            # Falseâ†’True transition (daily_sl_hit is sticky True every poll once
            # halted, so an unguarded call would reconnect/close every second).
            if session.daily_sl_hit and not _was_halted:
                try:
                    bridge_multi.close_secondary_accounts()
                    log.warning("â›” Daily-SL halt — secondary accounts flattened")
                except Exception as _se:
                    log.error(f"âŒ Secondary flatten on daily-SL failed: {_se}")

            # FIX #5: feed every newly closed trade to the inference
            # engine. on_trade_closed() / record_trade_result() were
            # NEVER called before, so online learning, drift detection,
            # auto-retrain trigger and live_trades.csv were all dead.
            for _cd in (new_closed or []):
                try:
                    engine.record_trade_result(_cd["net"])
                    if _cd["bar_time"] is not None:
                        engine.on_trade_closed(
                            timestamp  = pd.Timestamp(_cd["bar_time"]),
                            trade_type = _cd["direction"],
                            volume     = _cd["volume"],
                            label      = _cd["label"],
                            pnl        = _cd["net"],
                        )
                except Exception as _le:
                    log.warning(f"âš ï¸ Learning update failed #{_cd.get('ticket')}: {_le}")

            # â”€â”€ Skip if daily SL hit â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if session.daily_sl_hit:
                write_dashboard(session, core.virtual_trades, tick.bid,
                                core._last_signal, _engine_meta(engine),
                                signal_confirmed=True)
                time.sleep(POLL_SEC)   # FIX #6: vSL must stay monitored (1s heartbeat)
                continue

            # â”€â”€ Get signal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # Sync engine capital with live equity every bar
            _acct = mt5.account_info()
            if _acct:
                engine.update_capital(_acct.equity)
            # equity at signal-generation time â€” logged for EVERY signal (executed or not)
            _cur_equity = float(_acct.equity) if _acct else 0.0
            # L8: flow-adjusted TRADING equity (deposits/withdrawals netted out) for a clean
            # equity curve; + detect/announce any new deposit/withdrawal this bar.
            _cur_trading_eq = session.trading_equity(_cur_equity)
            session.log_new_balance_ops()

            # FIX #8: evaluate the LAST CLOSED bar (bar_time is the open
            # of the just-formed, still-empty candle). All features now
            # match how the models were trained (completed candles).
            eval_ts = (pd.Timestamp(bar_time) - pd.Timedelta(minutes=15)
                       if USE_CLOSED_BAR else pd.Timestamp(bar_time))

            live_ohlc = get_live_ohlc(250)
            live_adx  = get_live_adx(50, bar_dt=eval_ts)
            if live_ohlc is None:
                log.warning("âš ï¸ No OHLC data — skipping bar")
                time.sleep(POLL_SEC)   # FIX #6: vSL must stay monitored (1s heartbeat)
                continue
            _write_chart_ohlc_snapshot(live_ohlc)

            # L7b 2026-06-29: Live ATR20 readout + threading REMOVED. ATR was display-only
            # (dropped from FEATURE_COLS 2026-06-19; never used in any live decision). The
            # SQLite atr20_pct column is left nullable (no live-DB migration) â†’ logs 0.
            ts = eval_ts   # FIX #8: last closed bar, not the forming one
            try:
                result_buy  = engine.get_signal(timestamp=ts, trade_type="BUY",  volume=0.10,
                                                ohlc_update=live_ohlc, adx_update=live_adx)
                result_sell = engine.get_signal(timestamp=ts, trade_type="SELL", volume=0.10,
                                                ohlc_update=live_ohlc, adx_update=live_adx)
            except Exception as e:
                log.error(f"âŒ get_signal failed: {e}")
                time.sleep(POLL_SEC)   # FIX #6: vSL must stay monitored (1s heartbeat)
                continue

            # Pick best signal.
            # FAB-M11 (2026-07-07): prefer any NON-SKIP over a higher-prob SKIP.
            # Old code took max(win_prob) blindly — if the higher-prob side was a
            # SKIP (below its own regime threshold) while the lower-prob side had
            # PASSED its threshold (=BUY/SELL), the tradable signal was silently
            # discarded (prime-directive violation). Now: a side that produced an
            # actionable BUY/SELL wins over a side that produced SKIP; only when
            # both are actionable (or both SKIP) do we fall back to higher win_prob.
            _rb_act = result_buy.get("signal")  in ("BUY", "SELL")
            _rs_act = result_sell.get("signal") in ("BUY", "SELL")
            if _rb_act and not _rs_act:
                result = result_buy
            elif _rs_act and not _rb_act:
                result = result_sell
            else:
                result = (result_buy if result_buy.get("win_prob", 0) >= result_sell.get("win_prob", 0)
                          else result_sell)
            result["bar_time"] = str(bar_time)
            core._last_signal = result

            signal   = result.get("signal", "SKIP")
            win_prob = result.get("win_prob", 0.0)
            sl_mult  = result.get("sl_multiplier", 1.5)
            tp_mult  = result.get("tp_multiplier", 1.5)

            # â”€â”€ GENERATE early trend-pullback entry (ET1 v2 â€” config/env-gated) â”€â”€
            # ML fires LATE (at the breakout top). When it SKIPs but the dominant HTF
            # trend is aligned AND price has pulled back to the ratchet line, CREATE the
            # entry now (early) instead of waiting for the late ML top-signal.
            if signal == "SKIP":
                try:
                    _gen = trend_pullback_generate(result_buy, CFG)  # ts_*/ADX are dir-independent
                    if _gen in ("BUY", "SELL"):
                        result = result_buy if _gen == "BUY" else result_sell
                        result["bar_time"] = str(bar_time)
                        result["reason"]   = "GEN: trend-pullback early entry"
                        core._last_signal  = result
                        signal   = _gen
                        win_prob = result.get("win_prob", 0.0)
                        sl_mult  = result.get("sl_multiplier", 1.5)
                        tp_mult  = result.get("tp_multiplier", 1.5)
                        log.info(f"âš¡ GEN entry {signal} (ADX-aligned pullback) | ml_prob={win_prob:.2%}")
                except Exception as _ge:
                    log.warning(f"generate-entry error (ignored): {_ge}")

            # Shadow record
            record_shadow_signal(bar_time, result)

            # â”€â”€ MONITOR mode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            mode = read_mode()
            if mode == "monitor":
                log.warning(f"👁 MONITOR | {signal} prob={win_prob:.2%} [no trade]")
                log_signal(bar_time, signal, result, float(live_ohlc["close"].iloc[-1]),
                           "MONITOR", trade_action="MONITOR", equity=_cur_equity, trading_equity=_cur_trading_eq)
                write_dashboard(session, core.virtual_trades, tick.bid,
                                result, _engine_meta(engine),
                                signal_confirmed=True, trade_action="MONITOR")
                time.sleep(POLL_SEC)   # FIX #6: vSL must stay monitored (1s heartbeat)
                continue

            # â”€â”€ Slot filter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if not TEST_MODE and not is_allowed_slot(bar_time):
                log.info(f"â­ Outside slot — {bar_time.strftime('%H:%M')} not in filter")
                log_signal(bar_time, signal, result, float(live_ohlc["close"].iloc[-1]),
                           "LIVE", trade_action="BLOCK_SLOT", equity=_cur_equity, trading_equity=_cur_trading_eq)
                write_dashboard(session, core.virtual_trades, tick.bid,
                                result, _engine_meta(engine),
                                signal_confirmed=True, trade_action="BLOCK_SLOT")
                time.sleep(POLL_SEC)   # FIX #6: vSL must stay monitored (1s heartbeat)
                continue

            # â”€â”€ Opposite signal check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if signal in ("BUY", "SELL") and core.virtual_trades:
                handled = core.handle_opposite_signal(
                    signal, win_prob, sl_mult, tp_mult, win_prob)
                if handled:
                    log_signal(bar_time, signal, result, float(live_ohlc["close"].iloc[-1]),
                               "LIVE", lot=0.0, trade_action="OPPOSITE_HANDLED", equity=_cur_equity, trading_equity=_cur_trading_eq)
                    write_dashboard(session, core.virtual_trades, tick.bid,
                                    result, _engine_meta(engine),
                                    signal_confirmed=True, trade_action="OPPOSITE_HANDLED")
                    time.sleep(POLL_SEC)   # FIX #6: vSL must stay monitored (1s heartbeat)
                    continue

            # â”€â”€ Range-phase entry filter (skip H4 chop entries â€” config-gated) â”€â”€
            _range_block = False
            # H4 RANGE-PHASE ENTRY FILTER -- REMOVED 2026-07-12 (Imtiyaz):
            # "model over hard filters". 1-month A/B OFF +8.9R vs ON +0.9R
            # (blocked winners). _range_block kept False so downstream
            # compound conditions are untouched. REVERT: git history.

            # â”€â”€ Counter-trend-FADE filter (block trade against a FADING dominant trend â€” config-gated) â”€â”€
            _ctf_block = False
            if signal in ("BUY", "SELL") and not _range_block and getattr(CFG.filters, "skip_counter_trend_fade", False):
                try:
                    _h1a = float(result.get("H1_ADX", 0) or 0); _h4a = float(result.get("H4_ADX", 0) or 0)
                    _uh4 = _h4a >= _h1a
                    _ddi = float(result.get("H4_DI_diff", 0) or 0) if _uh4 else float(result.get("H1_DI_diff", 0) or 0)
                    _dsl = float(result.get("h4_adx_slope", 0) or 0) if _uh4 else float(result.get("h1_adx_slope", 0) or 0)
                    _md  = 1 if _ddi > 0 else (-1 if _ddi < 0 else 0)
                    _wd  = 1 if signal == "BUY" else -1
                    if _md != 0 and _md != _wd and _dsl <= 0:
                        _ctf_block = True
                        log.info(f"â­ SKIP (counter-trend fade | dom {'H4' if _uh4 else 'H1'} slopeâ†“) | prob={win_prob:.2%}")
                        log_signal(bar_time, signal, result, float(live_ohlc["close"].iloc[-1]), "LIVE", trade_action="BLOCK_CTF", equity=_cur_equity, trading_equity=_cur_trading_eq)
                except Exception:
                    _ctf_block = False

            # â”€â”€ Trend-following PULLBACK entry gate (ET1 â€” config/env-gated, ATR-free) â”€â”€
            _pb_block = False
            if signal in ("BUY", "SELL") and not _range_block and not _ctf_block:
                try:
                    _pbb, _pbr = trend_pullback_block(result, CFG)
                    if _pbb:
                        _pb_block = True
                        log.info(f"â­ SKIP ({_pbr}) | prob={win_prob:.2%}")
                        log_signal(bar_time, signal, result, float(live_ohlc["close"].iloc[-1]), "LIVE", trade_action="BLOCK_PULLBACK", equity=_cur_equity, trading_equity=_cur_trading_eq)
                except Exception as _pbe:
                    log.warning(f"pullback gate error (ignored): {_pbe}")
                    _pb_block = False

            # â”€â”€ SMMA MTF soft gate (2026-07-06, research +51R, 4/4 quarters OOS win) â”€â”€
            _smma_block = False
            _sm = {"penalty": 0.0}
            if signal in ("BUY", "SELL") and not _range_block and not _ctf_block and not _pb_block:
                try:
                    _base_th = float(result.get("effective_threshold", CFG.filters.min_win_prob))
                    _sb, _sr, _sm = smma_mtf_soft_block(result, _base_th, CFG)
                    if _sb:
                        _smma_block = True
                        log.info(f"â­ SKIP ({_sr}) | prob={win_prob:.2%}")
                        log_signal(bar_time, signal, result, float(live_ohlc["close"].iloc[-1]), "LIVE", trade_action="BLOCK_SMMA", equity=_cur_equity, trading_equity=_cur_trading_eq)
                except Exception as _sme:
                    log.warning(f"smma mtf gate error (ignored): {_sme}")
                    _smma_block = False

            # â”€â”€ ADX STRENGTH soft gate (FAB-H9 2026-07-07: wired live for parity; default OFF) â”€â”€
            # Additive stack with SMMA (cap total_pen ≤ 0.08, required ≤ 0.60) — mirror
            # of backtest_replay so that IF adx_strength_soft is ever enabled, live == BT.
            _adx_block = False
            if signal in ("BUY", "SELL") and not _range_block and not _ctf_block and not _pb_block and not _smma_block:
                try:
                    _base_th = float(result.get("effective_threshold", CFG.filters.min_win_prob))
                    _ab, _ar, _am = adx_strength_soft_block(result, _base_th, CFG)
                    _smma_pen = float(_sm.get("penalty", 0) or 0)
                    _adx_pen  = float(_am.get("penalty", 0) or 0)
                    _total_pen = min(0.08, _smma_pen + _adx_pen)
                    _combined_req = min(0.60, _base_th + _total_pen)
                    if _combined_req > _base_th and win_prob < _combined_req:
                        _adx_block = True
                        log.info(f"â­ SKIP (combined SMMA+ADX gate: total_pen {_total_pen:.4f}) | prob={win_prob:.2%}")
                        log_signal(bar_time, signal, result, float(live_ohlc["close"].iloc[-1]), "LIVE", trade_action="BLOCK_ADX", equity=_cur_equity, trading_equity=_cur_trading_eq)
                except Exception as _ae:
                    log.warning(f"adx strength gate error (ignored): {_ae}")
                    _adx_block = False

            # â”€â”€ Execute signal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if signal in ("BUY", "SELL") and not core.virtual_trades and not _range_block and not _ctf_block and not _pb_block and not _smma_block and not _adx_block:
                # L11: on the FIRST actionable signal after startup, ASK before entering
                # (this may be a signal that fired while the system was off). Once answered,
                # all later signals trade normally. Default OFF (config resume_prompt_on_start).
                if _resume_pending:
                    _resume_pending = False
                    _px0 = float(live_ohlc["close"].iloc[-1])
                    if not _ask_resume(signal, _px0, win_prob,
                                       getattr(CFG.filters, "resume_prompt_timeout_s", 60.0)):
                        log.info("  â­ Resume: skipped the last signal — waiting for the next one")
                        log_signal(bar_time, signal, result, _px0, "LIVE", trade_action="RESUME_SKIP", equity=_cur_equity, trading_equity=_cur_trading_eq)
                        write_dashboard(session, core.virtual_trades, tick.bid, result, _engine_meta(engine), signal_confirmed=True, trade_action="RESUME_SKIP")
                        time.sleep(POLL_SEC)
                        continue
                # FIX #16: execute FIRST, then log the REAL lot size
                # (old code logged a hardcoded lot=0.02 before execution).
                used_lot = core.execute(signal, sl_mult, tp_mult, win_prob)
                log_signal(bar_time, signal, result, float(live_ohlc["close"].iloc[-1]),
                           "LIVE", lot=used_lot or 0.0, sl=0.0, tp=0.0,
                           trade_action=("EXECUTED" if used_lot else "EXEC_FAILED"),
                           equity=_cur_equity, trading_equity=_cur_trading_eq)
            elif not _range_block and not _ctf_block and not _pb_block and not _smma_block and not _adx_block:
                # (range/ctf/pullback block already logged its SKIP above â€” don't log twice)
                reason = result.get("reason", "SKIP")
                log.info(f"âŒ SKIP | prob={win_prob:.2%} | {reason}")
                _ta = "HOLD_IN_TRADE" if (signal in ("BUY", "SELL") and core.virtual_trades) else "NO_TRADE"
                log_signal(bar_time, signal, result, float(live_ohlc["close"].iloc[-1]),
                           "LIVE", trade_action=_ta, equity=_cur_equity, trading_equity=_cur_trading_eq)

            _dash_ta = ("BLOCK_RANGE" if _range_block else
                        "BLOCK_CTF" if _ctf_block else
                        "BLOCK_PULLBACK" if _pb_block else
                        "BLOCK_SMMA" if _smma_block else
                        "BLOCK_ADX" if _adx_block else "")
            write_dashboard(session, core.virtual_trades, tick.bid,
                            result, _engine_meta(engine),
                            signal_confirmed=True, trade_action=_dash_ta)
            time.sleep(POLL_SEC)   # FIX #6: vSL monitored right after entry (1s heartbeat)

        except KeyboardInterrupt:
            log.info("ðŸ›‘ Ctrl+C — shutting down")
            break
        except Exception as e:
            log.error(f"âŒ Run loop error: {e}", exc_info=True)
            time.sleep(10)

    core.disconnect()
    log.info("Bridge stopped.")


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _engine_meta(engine) -> dict:
    """Read model metadata â€” buy/sell AUC from JSON files, not waiting for first bar."""
    import json as _json
    from pathlib import Path as _Path
    meta = {
        "auc":          getattr(engine, "_last_auc", 0),
        "n_features":   getattr(engine, "_n_features", 0),
        "buy_model_auc":  0,
        "sell_model_auc": 0,
        "combined_auc":   0,
        "training_trades": 0,
        "last_retrain_date": "--",
    }
    try:
        models_dir = _Path(CFG.paths.models_dir)
        # Buy model AUC
        buy_meta = models_dir / "buy_model_meta.json"
        if buy_meta.exists():
            d = _json.loads(buy_meta.read_text())
            meta["buy_model_auc"]  = round(d.get("auc", 0), 4)
            meta["training_trades"] = d.get("n_trades", 0)
        # Sell model AUC
        sell_meta = models_dir / "sell_model_meta.json"
        if sell_meta.exists():
            d = _json.loads(sell_meta.read_text())
            meta["sell_model_auc"] = round(d.get("auc", 0), 4)
        # Combined model AUC + retrain date
        model_meta = models_dir / "model_meta.json"
        if model_meta.exists():
            d = _json.loads(model_meta.read_text())
            meta["combined_auc"]       = round(d.get("auc", 0), 4)
            meta["auc"]               = round(d.get("auc", 0), 4)
            meta["n_features"]        = len(d.get("features", []))
            ts = d.get("timestamp", "")
            if ts:
                meta["last_retrain_date"] = ts[:8]  # YYYYMMDD
    except Exception as e:
        log.debug(f"engine_meta read failed: {e}")
    return meta


def _logged_bar_times(n=2000):
    """L11: SET of bar_time strings already in signals_all.csv (last n rows). Backfill
    logs ONLY genuinely-missing bars â†’ fills internal gaps/holes too (not just newer
    ones), dedupe-safe across restarts."""
    try:
        p = Path(CFG.paths.signal_log)
        if not p.exists():
            return set()
        lines = p.read_text(encoding="utf-8").strip().split("\n")
        return {ln.split(",", 1)[0] for ln in lines[-n:] if ln.startswith("20")}
    except Exception:
        return set()


def _overnight_replay(engine, core, session, news_df):
    """Backfill the off-time gap: replay recent bars, shadow-track, AND log every NEW
    signal to signals_all.csv (mode=BACKFILL) so the dashboard shows the overnight
    history even though no trade was placed. No trades. (L11 / L9)"""
    try:
        rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 52)
        if rates is None or len(rates) < 2:
            return
        _logged_set = _logged_bar_times()    # bars already in the log â†’ skip them (fill only holes)
        log.info("📋 Replaying overnight bars (shadow + signal-log backfill)...")
        live_ohlc = get_live_ohlc(250)
        _write_chart_ohlc_snapshot(live_ohlc)
        _logged = 0
        for i, r in enumerate(rates[:-2]):
            bt = datetime.fromtimestamp(r["time"], tz=timezone.utc).replace(tzinfo=None)
            try:
                # FAB-H6: compute ADX AS-OF this replayed bar (not today's latest)
                # so BACKFILL / shadow rows aren't lookahead-tainted.
                live_adx = get_live_adx(50, bar_dt=pd.Timestamp(bt))
                rb = engine.get_signal(pd.Timestamp(bt), "BUY",  0.10, live_ohlc, live_adx)
                rs = engine.get_signal(pd.Timestamp(bt), "SELL", 0.10, live_ohlc, live_adx)
                res = rb if rb.get("win_prob", 0) >= rs.get("win_prob", 0) else rs
                res["bar_time"] = str(bt)
                record_shadow_signal(bt, res)
                core._last_signal = res
                # L11: log any bar NOT already in the signal log â†’ fills overnight gaps/holes
                _bts = str(bt)
                if _bts not in _logged_set:
                    log_signal(bt, res.get("signal", "SKIP"), res,
                               float(r["close"]), "BACKFILL", equity=0.0)
                    _logged_set.add(_bts)
                    _logged += 1
            except Exception:
                pass
        log.info(f"📋 Overnight replay done ✅ ({_logged} new bars backfilled to signal log)")
    except Exception as e:
        log.warning(f"Overnight replay failed: {e}")


def _pre_pop_dashboard(engine, core, session, news_df):
    """Write dashboard once before first bar to populate the UI."""
    try:
        tick = mt5.symbol_info_tick(SYMBOL)
        if not tick:
            return
        live_ohlc = get_live_ohlc(250)
        _write_chart_ohlc_snapshot(live_ohlc)
        live_adx  = get_live_adx(50)
        if live_ohlc is None:
            return
        rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 1)
        if rates is None or len(rates) == 0:   # FIX #9b: numpy-safe check
            return
        bt = datetime.fromtimestamp(rates[0]["time"], tz=timezone.utc).replace(tzinfo=None)
        # FIX #8: pre-populate using last CLOSED bar too
        _ts0 = (pd.Timestamp(bt) - pd.Timedelta(minutes=15)
                if USE_CLOSED_BAR else pd.Timestamp(bt))
        rb = engine.get_signal(_ts0, "BUY",  0.10, live_ohlc, live_adx)
        rs = engine.get_signal(_ts0, "SELL", 0.10, live_ohlc, live_adx)
        res = rb if rb.get("win_prob", 0) >= rs.get("win_prob", 0) else rs
        res["bar_time"] = str(bt)
        core._last_signal = res
        write_dashboard(session, core.virtual_trades, tick.bid, res, _engine_meta(engine), signal_confirmed=False)
        log.info(f"📊 Dashboard pre-populated | HMM:{res.get('hmm_state','?')} "
                 f"| WinProb:{res.get('win_prob',0):.2%}")
    except Exception as e:
        log.warning(f"Dashboard pre-populate failed: {e}")


if __name__ == "__main__":
    run()
