"""
bridge_data.py — QUANT GOLD AI v2
All data persistence: SQLite (primary) + CSV (backup).
No MT5 calls here — pure data layer.
"""
import csv, json, os, shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone

from bridge_constants import log, db_conn, CFG


# ── Signal logging ────────────────────────────────────────────

# Dedupe guard: the run-loop can call log_signal more than once for the SAME
# bar (e.g. range-block path + the else branch, or the same bar re-processed
# across poll iterations). We log exactly ONE row per (bar_time, mode).
_last_sig_key = None

# L8: ensure the signal CSV has a trailing trading_equity column exactly once per run.
_teq_col_checked = False


def _ensure_teq_column(log_path):
    """L8: one-time migration — append a trailing `trading_equity` column (blank for old
    rows) to a signal CSV that predates L8, so new appends stay column-aligned. No-op if
    the column already exists or the file is absent. Runs at most once per process."""
    global _teq_col_checked
    if _teq_col_checked:
        return
    _teq_col_checked = True
    try:
        if not os.path.exists(log_path):
            return
        with open(log_path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if not rows or "trading_equity" in rows[0]:
            return
        rows[0].append("trading_equity")
        for r in rows[1:]:
            r.append("")
        tmp = log_path + ".tmp"
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
        shutil.move(tmp, log_path)
        log.info("  🔧 signal log: added trading_equity column (L8 migration)")
    except Exception as e:
        log.debug(f"trading_equity column migration failed: {e}")


def _ensure_signal_columns(log_path):
    """Normalize the signal CSV backup schema before appending new rows."""
    global _teq_col_checked
    if _teq_col_checked:
        return
    _teq_col_checked = True
    try:
        if not os.path.exists(log_path):
            return
        with open(log_path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if not rows:
            return

        header = rows[0]
        original_width = len(header)
        changed = False
        move_insert_at = None
        if "trading_equity" not in header:
            header.append("trading_equity")
            changed = True
        if "move" not in header:
            move_insert_at = header.index("trading_equity") if "trading_equity" in header else len(header)
            header.insert(move_insert_at, "move")
            changed = True
        if not changed:
            return

        expected = len(header)
        for i, row in enumerate(rows[1:], start=1):
            if move_insert_at is not None and len(row) == original_width:
                row = row[:move_insert_at] + [""] + row[move_insert_at:]
                rows[i] = row
            while len(row) < expected:
                row.append("")
            if len(row) > expected:
                del row[expected:]

        tmp = log_path + ".tmp"
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
        shutil.move(tmp, log_path)
        log.info("  signal log: normalized CSV columns")
    except Exception as e:
        log.debug(f"signal CSV column migration failed: {e}")


def log_flow_event(ticket, server_time, amount, kind):
    """L8: append one deposit/withdrawal to logs/balance_flows.csv for audit."""
    try:
        path = os.path.join(os.path.dirname(str(CFG.paths.signal_log)), "balance_flows.csv")
        exists = os.path.exists(path)
        try:
            ts = datetime.fromtimestamp(int(server_time), tz=timezone.utc).replace(tzinfo=None)
            ts_str = str(ts)
        except Exception:
            ts_str = str(server_time)
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not exists:
                w.writerow(["server_time", "ticket", "kind", "amount"])
            w.writerow([ts_str, ticket, kind, round(float(amount), 2)])
    except Exception as e:
        log.debug(f"log_flow_event failed: {e}")

def log_signal(bar_time, signal, result, price, mode, lot=0.0, sl=0.0, tp=0.0,
               equity=0.0, trading_equity=None):
    """
    Write every signal to SQLite (primary) + CSV (backup).
    Called once per bar for both SKIP and executed signals.
    `equity` = raw account equity at the moment the signal was generated (logged for
    EVERY signal — executed or not — so the log shows balance-at-signal-time).
    `trading_equity` (L8) = equity with deposits/withdrawals netted out → a clean
    TRADING-only equity curve. None → blank (e.g. BACKFILL rows).
    """
    global _last_sig_key
    bt_str = str(bar_time)

    # 2026-06-23: skip duplicate writes for the same bar+mode (was logging the
    # same M15 bar 2-3x → duplicate rows in signals_all.csv / dashboard log).
    _key = (bt_str, mode)
    if _key == _last_sig_key:
        return
    _last_sig_key = _key

    vals = (
        bt_str, mode, signal,
        round(result.get("win_prob",        0), 4),
        round(result.get("state_prob",      0), 4),
        round(result.get("dir_prob",        0), 4),
        round(result.get("big_win_prob",    0), 4),
        result.get("hmm_state", ""),
        round(price, 2), round(lot, 2), round(sl, 2), round(tp, 2),
        round(result.get("atr20_pct",       0), 4),
        int(result.get("vol_spike",         0)),
        int(result.get("in_range_phase",    0)),
        round(result.get("slot_wr",         0), 4),
        round(result.get("h4_resist_dist", 0), 4),
        round(result.get("h4_support_dist", 0), 4),
        result.get("reason", "")[:120],
    )

    # Primary: SQLite
    try:
        conn = db_conn()
        conn.execute("""
            INSERT OR IGNORE INTO signals
            (bar_time,mode,signal,win_prob,state_prob,dir_prob,big_win_prob,
             hmm_state,price,lot,sl,tp,atr20_pct,vol_spike,in_range_phase,
             slot_wr,h4_bull_ob_dist,h4_bear_ob_dist,reason,outcome)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'')
        """, vals)
        conn.commit()
        conn.close()
    except Exception as e:
        log.debug(f"SQLite signal log failed: {e}")

    # Backup: CSV
    try:
        log_path = str(CFG.paths.signal_log)
        file_exists = os.path.exists(log_path)
        if file_exists:
            _ensure_signal_columns(log_path)   # one-time backup CSV schema migration
        _teq_out = round(trading_equity, 2) if trading_equity is not None else ""
        with open(log_path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not file_exists:
                w.writerow([
                    "bar_time","mode","signal","win_prob","state_prob",
                    "dir_prob","big_win_prob","hmm_state","price","lot","sl","tp",
                    "atr20_pct","vol_spike","in_range_phase","slot_wr",
                    "h4_bull_ob_dist","h4_bear_ob_dist","reason","outcome","equity","move",
                    "trading_equity"
                ])
            w.writerow(list(vals) + ["", round(equity, 2), "", _teq_out])
    except Exception as e:
        log.debug(f"CSV signal log failed: {e}")


def write_outcome(entry_orders_today, closed_deals):
    """
    Write WIN/LOSS outcome back to SQLite + CSV for all newly closed deals.
    Called from session.check_closed() after every new deal detected.
    """
    outcome_map = {}
    for d in closed_deals:
        entry_d = entry_orders_today.get(d.position_id)
        if entry_d is None:
            continue
        net = round(d.profit + d.commission + d.swap, 2)
        outcome_str = "WIN" if net > 0 else "LOSS"
        # real price MOVE ($ gold points, lot-independent) = exit - entry, signed by dir (0=BUY)
        try:
            _dir = 1 if getattr(entry_d, "type", 0) == 0 else -1
            move = round((float(d.price) - float(entry_d.price)) * _dir, 2)
        except Exception:
            move = ""
        open_dt = datetime.fromtimestamp(entry_d.time, tz=timezone.utc).replace(tzinfo=None)
        bar_dt  = open_dt.replace(minute=(open_dt.minute // 15) * 15, second=0, microsecond=0)
        for delta in [0, -15, 15]:
            key = str(bar_dt + timedelta(minutes=delta))
            outcome_map[key] = (outcome_str, net, move)

    if not outcome_map:
        return

    # SQLite (1ms, no file rewrite)
    try:
        conn = db_conn()
        updated = 0
        for bt_key, (out, net, mv) in outcome_map.items():
            cur = conn.execute("""
                UPDATE signals SET outcome=?, pnl_net=?
                WHERE bar_time=? AND mode IN ('LIVE','MONITOR')
                AND (outcome='' OR outcome IS NULL)
            """, (out, net, bt_key))
            updated += cur.rowcount
        conn.commit()
        conn.close()
        if updated:
            log.info(f"  ✅ SQLite: {updated} outcome(s) written")
    except Exception as e:
        log.debug(f"SQLite outcome write-back failed: {e}")

    # CSV backup
    try:
        log_path = str(CFG.paths.signal_log)
        if not os.path.exists(log_path):
            return
        rows = []
        updated_csv = 0
        with open(log_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fnames = list(reader.fieldnames or [])
            if "outcome" not in fnames:
                fnames.append("outcome")
            if "move" not in fnames:
                fnames.append("move")
            for row in reader:
                bt = row.get("bar_time", "")
                if (row.get("outcome", "") in ("", "PENDING") and
                        row.get("mode", "") in ("LIVE", "MONITOR") and
                        bt in outcome_map):
                    row["outcome"] = outcome_map[bt][0]
                    row["move"]    = outcome_map[bt][2]   # real price move ($, lot-independent)
                    updated_csv += 1
                rows.append(row)
        if updated_csv:
            tmp = log_path + ".tmp"
            with open(tmp, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fnames)
                writer.writeheader()
                writer.writerows(rows)
            shutil.move(tmp, log_path)
            log.info(f"  ✅ CSV: {updated_csv} outcome(s) written")
    except Exception as e:
        log.debug(f"CSV outcome write-back failed: {e}")


def save_trade(ticket, direction, entry_price, exit_price, entry_time, exit_time,
               lot, sl_dist, vsl_price, tp_price, pnl_gross, pnl_net,
               commission, swap, r_achieved, hmm_state, atr_pct, win_prob,
               bar_time, partial_closed=0, comment=""):
    """Insert or update a closed trade in SQLite trades table."""
    try:
        conn = db_conn()
        conn.execute("""
            INSERT OR REPLACE INTO trades
            (ticket,direction,entry_price,exit_price,entry_time,exit_time,
             lot,sl_dist,vsl_price,tp_price,pnl_gross,pnl_net,commission,swap,
             r_achieved,hmm_state,atr_pct,win_prob,bar_time,partial_closed,comment)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (ticket,direction,entry_price,exit_price,entry_time,exit_time,
              lot,sl_dist,vsl_price,tp_price,pnl_gross,pnl_net,commission,swap,
              r_achieved,hmm_state,atr_pct,win_prob,bar_time,partial_closed,comment))
        conn.commit()
        conn.close()
        log.info(f"  💾 Trade #{ticket} saved to DB | {direction} pnl=${pnl_net:+.2f}")
    except Exception as e:
        log.debug(f"Trade DB save failed: {e}")


def update_daily_summary(trade_date, trades, wins, losses, gross_pnl, day_open_bal):
    """Upsert daily summary row."""
    try:
        conn = db_conn()
        conn.execute("""
            INSERT OR REPLACE INTO daily_summary
            (trade_date, trades, wins, losses, gross_pnl, day_open_bal)
            VALUES (?,?,?,?,?,?)
        """, (trade_date, trades, wins, losses, gross_pnl, day_open_bal))
        conn.commit()
        conn.close()
    except Exception as e:
        log.debug(f"Daily summary save failed: {e}")


# ── Shadow slot tracking ──────────────────────────────────────

def shadow_file() -> Path:
    return Path(CFG.paths.logs_dir) / "shadow_slots.json"

def load_shadow() -> dict:
    try:
        f = shadow_file()
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def save_shadow(data: dict):
    try:
        shadow_file().write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning(f"Shadow save failed: {e}")

def record_shadow_signal(bar_time, result):
    """Track every bar signal in shadow_slots for future slot analysis."""
    try:
        slot_key = f"{bar_time.strftime('%H:%M')}|{bar_time.strftime('%A')}"
        shadow = load_shadow()
        if slot_key not in shadow:
            shadow[slot_key] = {
                "slot": bar_time.strftime("%H:%M"),
                "day":  bar_time.strftime("%A"),
                "observations": 0, "signals": 0,
                "total_win_prob": 0.0, "wins": 0, "losses": 0,
                "last_seen": str(bar_time), "pending_outcome": None,
            }
        entry = shadow[slot_key]
        entry["observations"] += 1
        entry["total_win_prob"] += result.get("win_prob", 0.0)
        entry["last_seen"] = str(bar_time)
        wp = result.get("win_prob", 0.0)
        if wp >= CFG.filters.min_win_prob:
            entry["signals"] += 1
            entry["pending_outcome"] = {
                "bar_time":  str(bar_time),
                "signal":    result.get("signal", "SKIP"),
                "win_prob":  round(wp, 4),
                "hmm_state": result.get("hmm_state", ""),
                "direction": result.get("signal", ""),
            }
        save_shadow(shadow)
    except Exception as e:
        log.warning(f"Shadow record failed: {e}")

def update_shadow_outcome(bar_time, pnl_usd, direction):
    """Mark pending shadow outcome as WIN/LOSS after trade closes."""
    try:
        shadow = load_shadow()
        slot_key = f"{bar_time.strftime('%H:%M')}|{bar_time.strftime('%A')}"
        if slot_key not in shadow:
            return
        entry = shadow[slot_key]
        outcome = "WIN" if pnl_usd > 0 else "LOSS"
        if outcome == "WIN":
            entry["wins"] = entry.get("wins", 0) + 1
        else:
            entry["losses"] = entry.get("losses", 0) + 1
        total = entry.get("wins", 0) + entry.get("losses", 0)
        entry["win_rate"] = entry["wins"] / total if total else 0.0
        entry["pending_outcome"] = None
        save_shadow(shadow)
    except Exception as e:
        log.warning(f"Shadow outcome update failed: {e}")

def get_shadow_summary() -> list:
    """Return top 20 shadow slots by win rate (for dashboard)."""
    try:
        shadow = load_shadow()
        rows = []
        for key, v in shadow.items():
            if not isinstance(v, dict):
                continue
            total = v.get("wins", 0) + v.get("losses", 0)
            rows.append({
                "slot":         v.get("slot", "--"),
                "day":          v.get("day", "--"),
                "observations": v.get("observations", 0),
                "signals":      v.get("signals", 0),
                "wins":         v.get("wins", 0),
                "losses":       v.get("losses", 0),
                "win_rate":     v.get("win_rate", 0.0),
                "avg_win_prob": round(v.get("total_win_prob", 0) / max(v.get("observations", 1), 1), 4),
                "last_seen":    v.get("last_seen", ""),
            })
        rows.sort(key=lambda x: (x["win_rate"], x["wins"]), reverse=True)
        return rows[:20]
    except Exception:
        return []
