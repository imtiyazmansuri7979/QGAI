"""
bridge_dashboard.py — QUANT GOLD AI v2
Dashboard JSON writer. Reads MT5 + SQLite, writes dashboard.json every bar.
Also contains news filter helpers and slot filter.
"""
import json
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
from pathlib import Path

from bridge_constants import (
    log, CFG, SYMBOL, MAGIC, RISK_PCT, DAILY_SL,
    PARTIAL_CLOSE_ENABLED, PARTIAL_CLOSE_TP2_R,
    TEST_MODE,
    broker_now_ts, broker_day_start_ts, broker_now_dt, get_sym_info, sym_point,
)
from bridge_data import get_shadow_summary, db_conn


# ── Slot day filter ───────────────────────────────────────────

try:
    import json as _json
    _sdf_path = Path(CFG.paths.models_dir) / "slot_day_filter.json"
    SLOT_DAY_FILTER = _json.loads(_sdf_path.read_text()) if _sdf_path.exists() else {}
except Exception:
    SLOT_DAY_FILTER = {}


def is_allowed_slot(bar_time) -> bool:
    if not CFG.filters.use_slot_day_filter or not SLOT_DAY_FILTER:
        return True
    slot_int = bar_time.hour * 100 + bar_time.minute
    day      = bar_time.strftime("%A")
    allowed  = SLOT_DAY_FILTER.get(str(slot_int), [])
    return day in allowed if allowed else True


def get_today_slots(tick_time=None) -> list:
    """Return allowed slot strings for current broker day."""
    # FIX #B4: slots were sent (and drawn as an active-looking schedule)
    # even when use_slot_day_filter = False, while trading ignored them.
    # Empty list → the dashboard shows the honest "AI prob filter active —
    # no fixed slots needed" message. Turn the flag on and the grid returns.
    if not CFG.filters.use_slot_day_filter:
        return []
    try:
        if tick_time:
            now_b = datetime.fromtimestamp(tick_time, tz=timezone.utc).replace(tzinfo=None)
        else:
            tick = mt5.symbol_info_tick(SYMBOL)
            now_b = (datetime.fromtimestamp(tick.time, tz=timezone.utc).replace(tzinfo=None)
                     if tick else datetime.utcnow())
        today_name = now_b.strftime("%A")
        slots = []
        for slot_int, days in sorted(SLOT_DAY_FILTER.items()):
            if today_name in days:
                h, m = int(slot_int) // 100, int(slot_int) % 100
                slots.append(f"{h:02d}:{m:02d}")
        return slots
    except Exception:
        return []


# ── System health (FIX #B3) ──────────────────────────────────
# The dashboard's SYSTEM HEALTH panel reads d.system_health, but this
# key was never sent → the panel showed a false "❌ ERROR" forever.
# This builder checks real file ages and ships the data every write.

def _health_file(path: Path, label: str, stale_h: float, old_h: float) -> dict:
    """Status row for one file: OK <stale_h, STALE <old_h, OLD beyond, MISSING."""
    try:
        if not path.exists():
            return {"label": label, "status": "MISSING", "age_h": None, "modified": "--"}
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        age_h = (datetime.now() - mtime).total_seconds() / 3600.0
        status = "OK" if age_h < stale_h else "STALE" if age_h < old_h else "OLD"
        return {"label": label, "status": status, "age_h": round(age_h, 2),
                "modified": mtime.strftime("%m-%d %H:%M")}
    except Exception:
        return {"label": label, "status": "UNKNOWN", "age_h": None, "modified": "--"}


def build_system_health() -> dict:
    """File-age health: data CSVs (legend: OK <25h, STALE 25-72h),
    model PKLs (weekly retrain: OK <8d, STALE 8-14d), last retrain."""
    try:
        data_dir   = Path(CFG.paths.live_dir).parent          # .../data
        models_dir = Path(CFG.paths.models_dir)
        logs_dir   = Path(CFG.paths.logs_dir)

        h = {
            # Data files — thresholds match the panel legend (<25h OK, 25-72h STALE)
            "ohlc_live":   _health_file(Path(CFG.paths.live_dir)  / "ohlc_live.csv",   "OHLC live",   25, 72),
            "adx_live":    _health_file(Path(CFG.paths.live_dir)  / "adx_live.csv",    "ADX live",    25, 72),
            "ohlc_merged": _health_file(Path(CFG.paths.ohlc_file), "OHLC merged", 25, 72),
            "adx_merged":  _health_file(Path(CFG.paths.adx_file),  "ADX merged",  25, 72),
            # Models — weekly retrain cycle: OK <8d (192h), STALE <14d (336h)
            "xgb_model":  _health_file(models_dir / "xgb_model.pkl",  "XGB model",  192, 336),
            "hmm_model":  _health_file(models_dir / "hmm_model.pkl",  "HMM model",  192, 336),
            "buy_model":  _health_file(models_dir / "buy_model.pkl",  "BUY model",  192, 336),
            "sell_model": _health_file(models_dir / "sell_model.pkl", "SELL model", 192, 336),
        }

        # Last retrain from logs/.last_retrain (ISO timestamp)
        retrain = {"status": "UNKNOWN", "age_d": None, "date": "--"}
        try:
            lr_path = logs_dir / ".last_retrain"
            if lr_path.exists():
                lr_dt  = datetime.fromisoformat(lr_path.read_text().strip())
                age_d  = (datetime.now() - lr_dt).days
                retrain = {"status": "OK" if age_d < 8 else "OVERDUE",
                           "age_d": age_d, "date": lr_dt.strftime("%Y-%m-%d %H:%M")}
        except Exception:
            pass
        h["last_retrain"] = retrain

        # Overall: ERROR only if something is really missing/dead,
        # WARNING if stale/overdue, otherwise OK.
        statuses = [v.get("status") for v in h.values()]
        if any(s in ("MISSING", "OLD") for s in statuses):
            overall = "ERROR"
        elif any(s in ("STALE", "OVERDUE") for s in statuses):
            overall = "WARNING"
        else:
            overall = "OK"

        h["overall"]    = overall
        h["checked_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return h
    except Exception as e:
        log.warning(f"system_health build failed: {e}")
        return {"overall": "UNKNOWN", "checked_at": "--"}


# ── News helpers ──────────────────────────────────────────────

def get_news_filter_status(bar_time, news_df, signal_direction="BUY") -> dict:
    """Return minimal news status dict for dashboard."""
    if news_df is None:
        return {"near": False, "label": "No data"}
    try:
        import pandas as _pd
        window = _pd.Timedelta(minutes=30)
        nearby = news_df[
            (news_df["datetime"] >= bar_time - window) &
            (news_df["datetime"] <= bar_time + window) &
            (news_df["impact"] >= 2)
        ]
        if nearby.empty:
            return {"near": False, "label": "Clear"}
        top = nearby.iloc[0]
        stars = "★" * int(top.get("impact", 2))
        return {"near": True, "label": f"{stars} {top.get('event','News')}"}
    except Exception:
        return {"near": False, "label": "Error"}



# ── Signal history (FIX #B5) ──────────────────────────────────
# The dashboard's SIGNAL LOG / SIGNAL HISTORY panels read
# d.signal_history — a key that was never sent, so they showed
# "No signals yet" forever while SQLite already had thousands of rows.

def get_signal_history(limit: int = 40) -> list:
    """Last N live/monitor signals from SQLite, ascending (frontend reverses).
    eff_prob = the regime threshold the engine applied (mirror of inference.py)."""
    try:
        conn = db_conn()
        rows = conn.execute(
            "SELECT bar_time, mode, signal, win_prob, hmm_state, reason "
            "FROM signals WHERE mode != 'BACKTEST' "
            "ORDER BY bar_time DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        _b = CFG.filters.min_win_prob
        _thr = {"Ranging": round(_b + 0.03, 2), "Trending": round(_b, 2),
                "Volatile": round(max(0.42, _b - 0.03), 2)}
        out = [{"bar_time": r[0], "mode": r[1], "signal": r[2],
                "win_prob": r[3], "eff_prob": _thr.get(r[4], round(_b, 2)),
                "hmm_state": r[4], "reason": r[5] or ""}
               for r in rows]
        out.reverse()
        return out
    except Exception as e:
        log.warning(f"signal_history read failed: {e}")
        return []


# ── AI DECISION SUMMARY (one-box, refreshed every bar) ────────
_PB_CACHE = {"mtime": None, "data": None}

def _prob_buckets():
    """Read logs/prob_bucket_stats.json (from build_prob_buckets.py), cached by mtime."""
    try:
        p = Path(CFG.paths.logs_dir) / "prob_bucket_stats.json"
        mt = p.stat().st_mtime
        if _PB_CACHE["mtime"] != mt:
            _PB_CACHE["data"] = json.loads(p.read_text(encoding="utf-8"))
            _PB_CACHE["mtime"] = mt
        return _PB_CACHE["data"] or {}
    except Exception:
        return {}


def build_ai_summary(sig, eff_prob, price):
    """One-box AI transparency digest — model-wise probs, agreement/confidence,
    regime, expected $ move, suggested SL/TP, and 'signals like this' history.
    Pure read of the signal dict + cached prob-bucket stats. Never touches the
    live decision path. Returns {} on any error (caller also try/excepts)."""
    try:
      return _build_ai_summary(sig, eff_prob, price)
    except Exception as _e:
      return {"error": str(_e)[:120]}


def _build_ai_summary(sig, eff_prob, price):
    d      = str(sig.get("signal", "SKIP"))
    prob   = float(sig.get("win_prob", 0) or 0)
    sp     = float(sig.get("state_prob", 0) or 0)
    dp     = float(sig.get("dir_prob", 0) or 0)
    bw     = float(sig.get("big_win_prob", 0) or 0)
    regime = str(sig.get("hmm_state", "?"))
    thr    = float(eff_prob or 0.45)
    px     = float(price or 0)

    # 5-model agreement (matches the user's mental model)
    votes = {
        "Main (combined)": prob >= thr,
        "Regime (state)":  sp   >= thr,
        "Direction":       dp   >= thr,
        "HMM actionable":  regime in ("Trending", "Volatile"),
        "BigWin":          bw   >= 0.5,
    }
    agree = sum(1 for v in votes.values() if v)
    conf  = ("VERY HIGH" if agree >= 5 else "HIGH" if agree == 4
             else "MEDIUM" if agree == 3 else "LOW")

    # expected $ move (median predicted MFE) + suggested SL/TP from MAE/MFE
    def _pct(k):
        try: return float(sig.get(k, 0) or 0)
        except Exception: return 0.0
    mfe50 = _pct("pred_move_p50_pct"); mfe75 = _pct("pred_move_p75_pct")
    mae50 = _pct("pred_mae_p50_pct")
    exp_move_usd = round(px * mfe50 / 100.0, 2) if px else 0.0
    sug_tp_usd   = round(px * mfe75 / 100.0, 2) if px else 0.0
    sug_sl_usd   = round(px * max(mae50, 0.18) / 100.0, 2) if px else 0.0   # min 0.18% floor

    # 'signals like this' history (prob bucket, regime-specific if available)
    pb = _prob_buckets()
    band = "gt60" if prob > 0.60 else "p45_60"
    hist = (pb.get("buckets", {}) or {}).get(band, {})
    hist_reg = (pb.get("by_regime_gt60", {}) or {}).get(regime, {}) if prob > 0.60 else {}

    return {
        "signal": d, "final_prob": round(prob, 4), "threshold": round(thr, 4),
        "regime": regime,
        "models": {"main": round(prob, 3), "state": round(sp, 3), "direction": round(dp, 3),
                   "bigwin": round(bw, 3)},
        "votes": votes, "agreement": agree, "agreement_max": 5, "confidence": conf,
        "expected_move_usd": exp_move_usd, "suggested_tp_usd": sug_tp_usd, "suggested_sl_usd": sug_sl_usd,
        "history_band": ">60%" if prob > 0.60 else "45-60%",
        "history": hist, "history_regime": hist_reg,
        "why": str(sig.get("reason", ""))[:160],
        "invalidation": f"Opposite H1 flip, or price hits SL (~${sug_sl_usd}). Regime→Ranging weakens it.",
        "bucket_source": pb.get("source", "—"),
    }


def build_market_intel(sig, ms, news_txt=""):
    """MARKET INTELLIGENCE box — the CONTEXT behind the decision (NOT duplicating the
    AI summary). Trend structure (SMMA per TF), ADX strength, S/R structure, order-flow
    phase, and session/news context. Pure read; returns {} on error."""
    try:
        ms = ms or {}
        def _f(k, dv=0):
            try: return float(sig.get(k, dv) or dv)
            except Exception: return dv
        di = _f("H4_DI_diff")
        return {
            "trend": {
                "m15": int(_f("ts_trend_m15")), "h1": int(_f("ts_trend_h1")), "h4": int(_f("ts_trend_h4")),
                "agree": int(_f("ts_htf_agreement")), "line_dist": round(_f("ts_line_dist_pct"), 3)},
            "strength": {
                "h1_adx": round(_f("H1_ADX"), 1), "h4_adx": round(_f("H4_ADX"), 1),
                "di_dir": "BULL" if di > 0 else "BEAR" if di < 0 else "FLAT"},
            "structure": {
                "h4_resist": ms.get("h4_resist"), "h4_support": ms.get("h4_support"),
                "h1_resist": ms.get("h1_resist"), "h1_support": ms.get("h1_support"),
                "in_ob": int(ms.get("ob_in_zone", 0) or 0)},
            "flow": {
                "phase": ms.get("phase", "—"), "imbalance": ms.get("imbalance", "—"),
                "corr_ratio": ms.get("corr_ratio")},
            "context": {
                "volatility": ms.get("volatility", "—"),
                "session": "NY" if int(_f("is_ny_session")) else ("dead" if int(_f("is_dead_hour")) else "—"),
                "news": (news_txt or "").replace("⚠️", "").replace("✅", "").strip()[:40]},
        }
    except Exception as _e:
        return {"error": str(_e)[:120]}


# ── Fable-5 dashboard helpers (2026-07-07): risk-state + account health ──

def _account_health_rows():
    """Per-account health for the mirror-fill panel. Empty list if multi off."""
    try:
        import bridge_multi
        rows = bridge_multi.get_account_health()
        # flag any secondary whose last order differs from the primary's
        prim = next((r for r in rows if r.get("is_primary")), None)
        prim_status = (prim or {}).get("last_order")
        for r in rows:
            r["mismatch"] = bool(
                (not r.get("is_primary"))
                and r.get("last_order") == "REJECTED"
                and prim_status == "FILLED"
            )
        return rows
    except Exception:
        return []


def _dd_state_rows():
    """DD-brake state per account (peak, dd%, scale). Empty if brake off."""
    try:
        import dd_brake
        if not bool(getattr(CFG.filters, "enable_live_dd_brake", False)):
            return []
        import bridge_multi
        out = []
        for r in bridge_multi.get_account_health():
            eq = r.get("equity")
            st = dd_brake.status(eq, account_id=str(r.get("login", "")))
            out.append({
                "name":  r.get("name"),
                "peak":  st.get("peak_equity"),
                "dd_pct": st.get("drawdown_pct", 0.0),
                "scale": dd_brake.risk_scale(eq, account_id=str(r.get("login", ""))) if eq else 1.0,
            })
        return out
    except Exception:
        return []


def _daily_sl_headroom(session):
    """How much of today's loss budget is used / remaining."""
    try:
        limit = float(getattr(session, "daily_limit", 0.0) or 0.0)
        loss  = float(getattr(session, "daily_loss", 0.0) or 0.0)
        if limit <= 0:
            return None
        used_pct = round(100.0 * min(1.0, max(0.0, loss / limit)), 1)
        return {"used": round(loss, 2), "limit": round(limit, 2),
                "remaining": round(max(0.0, limit - loss), 2), "used_pct": used_pct}
    except Exception:
        return None


def _open_trade_risk(virtual_trades, current_price):
    """Live $ at risk on the open trade (distance to vSL × lot)."""
    try:
        if not virtual_trades:
            return None
        rows = []
        for vt in virtual_trades.values():
            entry = float(getattr(vt, "entry", 0) or 0)
            vsl   = float(getattr(vt, "virtual_sl", 0) or 0)
            lot   = float(getattr(vt, "lot", 0) or 0)
            direction = getattr(vt, "direction", "")
            cur = float(current_price or 0)
            dist = abs(cur - vsl) if cur else abs(entry - vsl)
            # approx $ risk = distance × lot × 100 (XAUUSD contract 100 oz)
            risk_usd = round(dist * lot * 100.0, 2)
            rows.append({"ticket": getattr(vt, "ticket", 0), "dir": direction,
                         "vsl": round(vsl, 2), "vsl_dist": round(dist, 2),
                         "risk_usd": risk_usd,
                         "in_profit": (cur > entry) if direction == "BUY" else (cur < entry)})
        return rows
    except Exception:
        return None


# ── Dashboard writer ──────────────────────────────────────────

def write_dashboard(session, virtual_trades, current_price, last_signal=None,
                    engine_meta=None):
    """
    Build and write dashboard.json.
    Called every bar and immediately after deal close.
    """
    try:
        info = mt5.account_info()
        tick = mt5.symbol_info_tick(SYMBOL)
        if not tick or not info:
            return

        current_price = tick.bid
        _now_ts  = broker_now_ts(tick.time)
        _bts_ts  = broker_day_start_ts(tick.time)
        _7day_ts = _bts_ts - 7 * 24 * 3600

        si = get_sym_info()
        spread_pts = round((tick.ask - tick.bid) / (si.point if si else 0.01), 1)

        # ── Closed deal stats ─────────────────────────────────
        deals = mt5.history_deals_get(_7day_ts, _now_ts) or []
        entry_orders_dash = {
            d.position_id: d for d in deals
            if d.magic == MAGIC and d.entry == mt5.DEAL_ENTRY_IN
        }
        # Exits today (our positions, including manual close)
        closed_today_exit = [
            d for d in deals
            if (d.magic == MAGIC or d.position_id in entry_orders_dash)
            and d.entry == mt5.DEAL_ENTRY_OUT
            and d.time >= _bts_ts
        ]
        # Today only (opened AND closed today)
        closed_today_only = [
            d for d in closed_today_exit
            if d.position_id in entry_orders_dash
            and entry_orders_dash[d.position_id].time >= _bts_ts
        ]

        wins       = sum(1 for d in closed_today_exit if d.profit > 0)
        losses     = sum(1 for d in closed_today_exit if d.profit < 0)
        gross_pnl  = round(sum(d.profit + d.commission + d.swap for d in closed_today_exit), 2)
        win_rate   = round(wins / len(closed_today_exit) * 100, 1) if closed_today_exit else 0.0
        total_trades_today = max(session.trades_today, len(closed_today_exit))

        # ── Session stats ─────────────────────────────────────
        profits_all = [round(d.profit + d.commission + d.swap, 2) for d in closed_today_exit]
        best_trade  = max(profits_all) if profits_all else None
        worst_trade = min(profits_all) if profits_all else None
        risk_dollar = round(session.day_open_bal * RISK_PCT / 100, 2)
        avg_r_today = round(gross_pnl / risk_dollar, 3) if risk_dollar and profits_all else None

        # Streak
        streak = 0; streak_type = "--"
        if profits_all:
            streak_type = "W" if profits_all[-1] > 0 else "L"
            for p in reversed(profits_all):
                if (p > 0 and streak_type == "W") or (p < 0 and streak_type == "L"):
                    streak += 1
                else:
                    break

        # ── Open trades ───────────────────────────────────────
        open_trades = [t.status(current_price) for t in virtual_trades.values()]
        for t in open_trades:
            obj = virtual_trades.get(t["ticket"])
            if obj:
                elapsed = (datetime.now(timezone.utc).replace(tzinfo=None) - obj.open_time)
                t["open_duration"] = str(elapsed).split(".")[0]
        try:
            import bridge_manual
            _manual = bridge_manual.dashboard_status(SYMBOL)
            if _manual:
                open_trades.append(_manual)
        except Exception as e:
            log.warning(f"manual dashboard append failed: {e}")

        # ── Closed trade history (last 20) ────────────────────
        closed_history = []
        for d in sorted(closed_today_exit, key=lambda x: x.time, reverse=True)[:20]:
            entry_deal = entry_orders_dash.get(d.position_id)
            net_pnl    = round(d.profit + d.commission + d.swap, 2)
            direction  = ("BUY" if (entry_deal and entry_deal.type == mt5.ORDER_TYPE_BUY)
                          else "SELL")
            entry_price = entry_deal.price if entry_deal else d.price
            exit_price  = d.price

            # R value from SL comment
            import re as _re
            r_val = None
            if entry_deal:
                m = _re.search(r"SL=([\d.]+)", entry_deal.comment or "")
                if m:
                    sl_d    = float(m.group(1))
                    pnl_pts = abs(exit_price - entry_price)
                    r_val   = round(pnl_pts / sl_d * (1 if net_pnl >= 0 else -1), 2)

            # Duration
            open_time  = entry_deal.time if entry_deal else d.time
            dur_mins   = int((d.time - open_time) / 60)
            dur_str    = f"{dur_mins//60}h{dur_mins%60:02d}m" if dur_mins >= 60 else f"{dur_mins}m"

            closed_history.append({
                "ticket":    d.order,
                "time":      datetime.fromtimestamp(d.time, tz=timezone.utc).strftime("%H:%M:%S"),
                "direction": direction,
                "entry":     round(entry_price, 2) if entry_deal else "--",
                "exit":      round(exit_price, 2),
                "profit":    round(d.profit, 2),
                "net_pnl":   net_pnl,
                "volume":    d.volume,
                "result":    "WIN" if net_pnl > 0 else "LOSS",
                "r_val":     r_val,
                "duration":  dur_str,
                "label":     "" if (entry_deal and entry_deal.time >= _bts_ts) else "[yday]",
            })

        # ── Broker / local time ───────────────────────────────
        broker_dt   = broker_now_dt(tick.time)
        broker_time = broker_dt.strftime("%Y-%m-%d %H:%M:%S")

        # ── Signal info ───────────────────────────────────────
        sig  = last_signal or {}
        hmm_state    = sig.get("hmm_state",    "Unknown")
        state_prob   = round(sig.get("state_prob",  0.0), 4)
        dir_prob     = round(sig.get("dir_prob",     0.0), 4)
        active_auc   = engine_meta.get("auc", 0) if engine_meta else 0
        features_count = engine_meta.get("n_features", 0) if engine_meta else 0

        # T2 equity SL REMOVED 2026-06-19 — risk = per-trade 3% + daily 9%.

        # ── News filter status (FIX #B5) ──────────────────────
        # The dashboard's NEWS FILTER panel read news_status /
        # news_min_prob / effective_min_prob — keys never sent, so it
        # displayed a hardcoded fake 52%. Real numbers now, computed
        # with the SAME rules as inference.py (keep both in sync!):
        # base 0.45; Ranging +0.03, Volatile -0.03 (floor 0.42);
        # pre-news +0.05; post-news = no penalty.
        _base_prob = CFG.filters.min_win_prob
        _state_thresh = {
            "Ranging":  _base_prob + 0.03,
            "Trending": _base_prob,
            "Volatile": max(0.42, _base_prob - 0.03),
        }
        if sig.get("is_pre_news", 0):
            _eff_prob   = _base_prob + 0.05
            _news_state = f"⚠️ Pre-news window — threshold raised to {_eff_prob:.2%}"
        elif sig.get("is_post_news", 0):
            _eff_prob   = _state_thresh.get(hmm_state, _base_prob)
            _news_state = f"✅ Post-news — no penalty ({hmm_state} {_eff_prob:.2%})"
        else:
            _eff_prob   = _state_thresh.get(hmm_state, _base_prob)
            _news_state = f"Clear — {hmm_state} threshold {_eff_prob:.2%}"

        # ── Market structure from signal ──────────────────────
        atr_pct = sig.get("atr20_pct", 0.15)
        vol_label = ("Very High" if atr_pct > 0.35 else "High" if atr_pct > 0.20
                     else "Normal" if atr_pct > 0.098 else "Low")

        market_structure = {
            "phase": ("Expansion" if atr_pct > 0.22 and hmm_state != "Ranging"
                      else "Accumulation" if atr_pct < 0.10
                      else "Trending" if hmm_state == "Trending"
                      else "Ranging" if hmm_state == "Ranging"
                      else "Volatile"),
            "phase_score": round((85 if hmm_state == "Trending" else
                                  70 if hmm_state == "Ranging" else 50) *
                                 (1.2 if sig.get("corr_imp_ratio", 1) < 0.5 else 1.0), 0),
            "h4_resist":  round(sig.get("h4_resist_dist", 999), 2),
            "h4_support": round(sig.get("h4_support_dist", 999), 2),
            "h1_resist":  round(sig.get("h1_resist_dist", 999), 2),
            "h1_support": round(sig.get("h1_support_dist", 999), 2),
            "ob_in_zone": int(sig.get("h4_in_ob_zone", 0)) or int(sig.get("h1_in_ob_zone", 0)),
            "volatility":   vol_label,
            "imbalance": ("Bullish" if sig.get("big_move_dir", 0) > 0
                          else "Bearish" if sig.get("big_move_dir", 0) < 0
                          else "Balanced"),
            "impulse_dir":  sig.get("big_move_dir", 0),
            "corr_ratio":   round(sig.get("corr_imp_ratio", 1.0), 2),
            "post_big_move": bool(sig.get("is_post_big_move", 0)),
            "conf_model":   round(sig.get("win_prob", 0) * 100, 1),
            "conf_market":  round(min(100, (
                (40 if sig.get("h4_resist_dist", 999) < 10 or
                    sig.get("h4_support_dist", 999) < 10 else 20) +
                (30 if int(sig.get("h4_in_ob_zone", 0)) else 10) +
                30   # L7b: vol_spike removed — this term was (30 if no spike else 10), now constant
            )), 1),
            "conf_volatility": round(min(100, max(0,
                100 - (atr_pct / 0.35 * 50)
            )), 1),
            "trend":     "Bearish" if sig.get("big_move_dir", 0) < 0 else "Bullish",
            "volume":    "Normal",   # L7b: vol_spike removed (no longer detected)
            "session":   "London" if 7 <= broker_dt.hour < 12 else
                         "NY"     if 13 <= broker_dt.hour < 21 else "Asian",
            "ob_near":   sig.get("h4_resist_dist", 999) < 5 or sig.get("h4_support_dist", 999) < 5,
            "in_range":  bool(sig.get("in_range_phase", 0)),
            "post_big":  bool(sig.get("is_post_big_move", 0)),
            # FIX #15: was hardcoded False — news panel always showed
            # green. Now derived from the signal's own news features.
            "news_near": bool(sig.get("is_pre_news", 0)) or
                         (sig.get("mins_to_3star", 999) <= 30),
            "hmm":       hmm_state,
            # Bar countdown — seconds until next M15 close
            "bar_seconds_left": (900 - (int(broker_dt.timestamp()) % 900)),
        }

        # ── Risk Grade + Expected Value ───────────────────────
        wp = sig.get("win_prob", 0.0)
        sl_m = sig.get("sl_multiplier", 1.5)
        tp_m = sig.get("tp_multiplier", 1.5)
        # EV = win_prob × tp_mult - (1-win_prob) × 1.0
        ev_r = round(wp * tp_m - (1 - wp) * 1.0, 3) if wp > 0 else None
        # Risk Grade
        # FIX #1: 'signal' was undefined (NameError) — must read from sig dict.
        # The NameError was silently swallowed by the outer try/except,
        # so dashboard.json stopped updating whenever win_prob > 0.
        if ev_r is None or sig.get("signal", "SKIP") == "SKIP":
            risk_grade = "--"; risk_grade_label = "--"
        elif ev_r >= 0.5:
            risk_grade = "A"; risk_grade_label = "Excellent"
        elif ev_r >= 0.3:
            risk_grade = "B"; risk_grade_label = "Strong Signal"
        elif ev_r >= 0.1:
            risk_grade = "C"; risk_grade_label = "Moderate"
        elif ev_r >= 0.0:
            risk_grade = "D"; risk_grade_label = "Weak"
        else:
            risk_grade = "F"; risk_grade_label = "Avoid"
        daily_limit = round(session.day_open_bal * DAILY_SL / 100, 2)
        daily_left  = round(max(0, daily_limit - session.daily_loss), 2)

        dash = {
            # Header
            "broker_time":        broker_time,
            "symbol":             SYMBOL,
            "bid":                round(tick.bid, 2),
            "ask":                round(tick.ask, 2),
            "spread":             spread_pts,
            # Account
            "account":            info.login,
            "balance":            round(info.balance, 2),
            "equity":             round(info.equity, 2),
            "day_open_bal":       round(session.day_open_bal, 2),
            "margin":             round(info.margin, 2),
            "free_margin":        round(info.margin_free, 2),
            "leverage":           info.leverage,
            # Daily performance
            "daily_loss":         round(session.daily_loss, 2),
            "daily_sl_$":         daily_limit,
            "daily_sl_left":      daily_left,
            "can_trade":          not session.daily_sl_hit,
            "trading_mode":       _read_mode(),
            # Today's stats
            "wins_today":         wins,
            "losses_today":       losses,
            "win_rate_today":     win_rate,
            "gross_pnl_today":    gross_pnl,
            "total_trades_today": total_trades_today,
            "best_trade_today":   round(best_trade, 2) if best_trade is not None else None,
            "worst_trade_today":  round(worst_trade, 2) if worst_trade is not None else None,
            "avg_r_today":        avg_r_today,
            "streak":             streak,
            "streak_type":        streak_type,
            # Risk
            "risk_pct":           RISK_PCT,
            "risk_dollar":        risk_dollar,
            "min_win_prob":       round(CFG.filters.min_win_prob, 2),
            "trades_today":       session.trades_today,
            # System config states (2026-07-07 — surface today's changes on dashboard)
            "cfg_ctf_fade":       bool(getattr(CFG.filters, "skip_counter_trend_fade", False)),
            "cfg_range_skip":     bool(getattr(CFG.filters, "skip_range_phase_entry", False)),
            "cfg_dd_brake":       bool(getattr(CFG.filters, "enable_live_dd_brake", False)),
            "cfg_reversal_gated": bool(getattr(CFG.filters, "gate_reversal_entries", False)),
            "cfg_adx_mode":       __import__("os").environ.get("QGAI_ADX_MODE", "raw"),
            # ── Fable-5 dashboard adds (2026-07-07): risk-state + per-account health ──
            "account_health":     _account_health_rows(),
            "dd_state":           _dd_state_rows(),
            "daily_sl_headroom":  _daily_sl_headroom(session),
            "open_trade_risk":    _open_trade_risk(virtual_trades, current_price),
            # Signal quality
            "risk_grade":         risk_grade,
            "risk_grade_label":   risk_grade_label,
            # FIX D5: on SKIP the Risk Grade shows "--" but EV still
            # showed a value (e.g. +0.25R) — mixed half-state. Blank both.
            "ev_r":               (None if sig.get("signal", "SKIP") == "SKIP" else ev_r),
            # Signal
            "last_signal":        sig,
            "last_signal_direction": sig.get("signal", "SKIP"),
            "state_prob":         state_prob,
            "dir_prob":           dir_prob,
            "active_hmm_state":   hmm_state,
            "active_model_auc":   active_auc,
            "features_count":     features_count,
            "buy_model_auc":      engine_meta.get("buy_model_auc", 0) if engine_meta else 0,
            "sell_model_auc":     engine_meta.get("sell_model_auc", 0) if engine_meta else 0,
            "combined_auc":       engine_meta.get("combined_auc", 0) if engine_meta else 0,
            "training_trades":    engine_meta.get("training_trades", 0) if engine_meta else 0,
            "last_retrain_date":  engine_meta.get("last_retrain_date", "--") if engine_meta else "--",
            # L7b 2026-06-29: atr_mult removed (ATR not used by the ratchet+regime-TP strategy; dashboard ATR labels deleted)
            "vol_regime":         sig.get("vol_regime", "normal"),
            # Market structure
            "market_structure":   market_structure,
            # FIX D3: the dashboard's "Why This Signal?" panel reads
            # d.why_signal — that key was never sent, so MODEL/MARKET/VOL
            # CONF stayed "--" forever. market_structure already contains
            # every field the panel needs (trend, session, conf_*, ...).
            "why_signal":          market_structure,
            # Positions
            "open_trades":        open_trades,
            "open_count":         len(open_trades),
            "closed_history":     closed_history,
            "total_closed_today": len(closed_today_exit),
            # Shadow slots
            "shadow_slots":       get_shadow_summary(),
            # Today slots
            "today_slots":        get_today_slots(tick.time),
            "last_trade_loss":    session.last_trade_was_loss,
            # FIX #B3: SYSTEM HEALTH panel data — was never sent before
            "system_health":      build_system_health(),
            # FIX #B5: SIGNAL LOG / HISTORY + real NEWS FILTER numbers
            "signal_history":     get_signal_history(40),
            "news_status":        _news_state,
            "news_min_prob":      round(_base_prob, 2),
            "effective_min_prob": round(_eff_prob, 2),
            # AI DECISION SUMMARY (one-box, every-bar) — never breaks the dash on error
            "ai_summary":         (build_ai_summary(sig, _eff_prob, current_price)
                                   if sig else {}),
            # MARKET INTELLIGENCE (context box below AI summary — non-duplicative)
            "market_intel":       (build_market_intel(sig, market_structure, _news_state)
                                   if sig else {}),
            "updated":            broker_time,
        }

        # Write atomically
        dash_path = Path(CFG.paths.logs_dir) / "dashboard.json"
        tmp_path  = str(dash_path) + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(dash, f, default=str)
        import os
        os.replace(tmp_path, str(dash_path))

    except Exception as e:
        log.debug(f"Dashboard write failed: {e}")


# ── Mode helpers ──────────────────────────────────────────────

def _read_mode() -> str:
    try:
        mode_path = Path(CFG.paths.logs_dir) / "mode.json"
        if mode_path.exists():
            data = json.loads(mode_path.read_text(encoding="utf-8"))
            return data.get("mode", "live")
    except Exception:
        pass
    return "live"

def read_mode() -> str:
    return _read_mode()

def set_mode(mode: str):
    try:
        mode_path = Path(CFG.paths.logs_dir) / "mode.json"
        mode_path.write_text(json.dumps({"mode": mode}), encoding="utf-8")
        log.info(f"Mode set to: {mode}")
    except Exception as e:
        log.warning(f"set_mode failed: {e}")
