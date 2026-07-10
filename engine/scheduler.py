"""
scheduler.py — QUANT GOLD AI v2 Auto Scheduler
Full auto: Data → Retrain → Trade → Report
Run: python scheduler.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import time
import subprocess
import os
from datetime import datetime, timezone, timedelta

_BROKER_TZ = timezone(timedelta(hours=3))  # UTC+3 — all scheduler times in broker time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import CFG
from console_colors import configure_color_logger

# ── Logging ───────────────────────────────────────────
Path(CFG.paths.logs_dir).mkdir(parents=True, exist_ok=True)
log = configure_color_logger("Scheduler", Path(CFG.paths.logs_dir) / "scheduler.log")

# ── Global State ──────────────────────────────────────
bridge_process  = None
last_retrain    = None

RETRAIN_FLAG = Path(__file__).parent / "logs" / ".last_retrain"

def _load_last_retrain():
    """Read last retrain date from file — survives restarts."""
    global last_retrain
    try:
        if RETRAIN_FLAG.exists():
            txt = RETRAIN_FLAG.read_text().strip()
            last_retrain = datetime.fromisoformat(txt)
            log.info(f"  Last retrain loaded: {last_retrain.date()}")
    except Exception:
        last_retrain = None

def _save_last_retrain(dt):
    """Save retrain date to file."""
    global last_retrain
    last_retrain = dt
    try:
        RETRAIN_FLAG.parent.mkdir(parents=True, exist_ok=True)
        RETRAIN_FLAG.write_text(dt.isoformat())
    except Exception as e:
        log.warning(f"  Could not save retrain flag: {e}")

def run(cmd, label=""):
    """Run a python script — no timeout, runs until complete."""
    log.info(f"Running: {label or cmd}")
    try:
        result = subprocess.run(
            [sys.executable, cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3600,   # 1 hour max — enough for full retrain
            cwd=str(Path(__file__).parent)
        )
        if result.returncode == 0:
            log.info(f"OK: {label} done")
            if result.stdout:
                for line in result.stdout.strip().split("\n")[-5:]:
                    log.info(f"  {line}")
        else:
            log.error(f"FAILED: {label}")
            log.error(result.stderr[-800:] if result.stderr else "no stderr")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log.error(f"TIMEOUT: {label} exceeded 1 hour")
        return False
    except Exception as e:
        log.error(f"ERROR in {label}: {e}")
        return False

# ─────────────────────────────────────────────────────
# TASKS
# ─────────────────────────────────────────────────────

def task_update_data():
    """
    Run on startup + daily — fills ALL data gaps automatically.
    Gap can be 1 hour, 1 day, 1 week, 1 month — updater handles all.
    Smart skip: if data is < 1 hour old, no update needed.
    """
    import pandas as pd
    from pathlib import Path as _Path

    log.info("=" * 50)
    log.info("  📊 TASK: Data gap check + update")

    # Check gap size before updating
    try:
        ohlc_path = _Path(CFG.paths.ohlc_file)
        if ohlc_path.exists():
            df = pd.read_csv(ohlc_path, usecols=[0])
            df.columns = ["time"]
            df["time"] = pd.to_datetime(df["time"], errors="coerce")
            last_dt  = df["time"].max()
            # FIX: data timestamps are BROKER time, but utcnow() was being
            # compared against them — a 3h offset meant data up to ~4h
            # stale still looked "fresh". Compare broker-now vs broker-data.
            now      = datetime.now(_BROKER_TZ).replace(tzinfo=None)
            gap_hrs  = (now - last_dt).total_seconds() / 3600 if pd.notna(last_dt) else 9999

            if gap_hrs < 1.0:
                log.info(f"  ✅ Data fresh (gap={gap_hrs:.1f}h < 1h) — no update needed")
                return
            elif gap_hrs < 24:
                log.info(f"  📥 Gap: {gap_hrs:.1f} hours — updating...")
            elif gap_hrs < 168:
                log.info(f"  📥 Gap: {gap_hrs/24:.1f} days — updating...")
            elif gap_hrs < 720:
                log.info(f"  📥 Gap: {gap_hrs/168:.1f} weeks — updating...")
            else:
                log.info(f"  📥 Gap: {gap_hrs/720:.1f} months — full download needed...")
        else:
            log.info("  📥 No data file — fresh download from 2024-01-01...")
    except Exception as e:
        log.warning(f"  Gap check failed: {e} — running update anyway")

    run("mt5_data_updater.py", "Data Update")

def task_check_retrain(startup=False):
    """07:30 — Retrain model on Mondays OR if gap > 7 days since last retrain.
    On startup: only retrain if models are missing (never trained before).
    """
    global last_retrain
    today     = datetime.now(_BROKER_TZ).replace(tzinfo=None)  # naive broker datetime — avoids tz mismatch
    is_monday = today.weekday() == 0  # Monday=0 (broker calendar)

    # Already trained today — skip
    if last_retrain and last_retrain.date() == today.date():
        log.info(f"  Model OK — already retrained today ({today.date()})")
        return

    days_since = (today - last_retrain).days if last_retrain else 999

    # On startup — NEVER retrain unless models are completely missing
    # Retrain only happens at scheduled 07:30 on Mondays
    # This prevents retrain every time scheduler restarts on Monday
    if startup:
        # FIX #10: old check used relative "models/final/" which does not
        # exist (real path is ../data/models/final via CFG) — so models
        # always looked "missing" and a FULL RETRAIN ran on every
        # scheduler start. Now uses the real configured path.
        models_dir = Path(CFG.paths.models_dir)
        has_models = (models_dir / "xgb_model.pkl").exists()
        if has_models:
            log.info(f"  Model OK — last retrain {days_since}d ago | Scheduled retrain: Monday 07:30")
            return
        else:
            reason = "No models found — first time training"

    # Scheduled run (07:30) — normal retrain logic
    elif last_retrain is None:
        reason = "First run ever — training model"
    elif days_since >= 7:
        reason = f"⚠️ {days_since}d since last retrain (threshold: 7d) — retraining now"
    elif is_monday:
        reason = f"Monday — weekly retrain (last: {days_since}d ago)"
    else:
        log.info(f"  Model OK — last retrain {days_since}d ago (next Monday)")
        return

    log.info(f"  {reason}")

    # Merge data before retraining
    log.info("="*50)
    log.info("  🔄 TASK: Merge historical + live data")
    run("merge_data.py", "Data Merge")
    log.info("="*50)
    log.info("  🤖 TASK: Retrain model")
    success = run("train.py", "Model Retrain")
    if success:
        _save_last_retrain(today)
        log.info(f"✅ Model retrained: {today.date()}")
        # Write reload flag — bridge picks this up and reloads OHLC + models
        try:
            from pathlib import Path as _Ph
            _flag = _Ph("logs/.reload_requested")
            _flag.parent.mkdir(parents=True, exist_ok=True)
            _flag.write_text(today.isoformat())
            log.info(f"📋 Reload flag written → bridge will reload OHLC + models")
        except Exception as _fe:
            log.debug(f"Reload flag write failed: {_fe}")

def task_start_bridge():
    """07:00 — Start MT5 bridge (24hr slot+day filter)."""
    global bridge_process
    if bridge_process and bridge_process.poll() is None:
        log.info("  Bridge already running!")
        return

    log.info("="*50)
    log.info("  🚀 TASK: Start MT5 bridge (NY session)")
    try:
        # FIX #3: entry point is bridge_main.py — mt5_bridge.py does not exist.
        # Old code made the scheduler unable to ever start the bridge, and
        # the watchdog kept "restarting" a dead process every 5 minutes.
        bridge_process = subprocess.Popen(
            [sys.executable, "bridge_main.py"],
            cwd=str(Path(__file__).parent)
        )
        log.info(f"✅ Bridge started (PID: {bridge_process.pid})")
    except Exception as e:
        log.error(f"❌ Bridge start failed: {e}")

def task_stop_bridge():
    """23:55 — Stop bridge at end of broker day."""
    global bridge_process
    log.info("="*50)
    log.info("  ⏹ TASK: Stop MT5 bridge")
    if bridge_process and bridge_process.poll() is None:
        bridge_process.terminate()
        bridge_process.wait(timeout=10)
        log.info("✅ Bridge stopped!")
    else:
        log.info("  Bridge not running")
    bridge_process = None

def task_daily_report():
    """19:30 — Generate daily report."""
    log.info("="*50)
    log.info("  📋 TASK: Daily report")

    log_file = Path(CFG.paths.logs_dir) / "bridge.log"
    if not log_file.exists():
        log.info("  No bridge log found")
        return

    # Parse today's trades from log
    today     = datetime.now(_BROKER_TZ).date()  # broker date
    trades    = 0
    signals   = 0

    with open(log_file, encoding="utf-8") as f:
        for line in f:
            if str(today) in line:
                if "TRADE OPEN" in line: trades += 1
                if "Signal:" in line:    signals += 1

    log.info(f"  Today: {signals} signals | {trades} trades")
    log.info(f"  Report saved to logs/")

# ─────────────────────────────────────────────────────
# SCHEDULE
# ─────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────
# BROKER TIME TASK SCHEDULE
# All times in Broker time (UTC+3) — no PC timezone dependency
# Works on any PC timezone (IST, UTC, UTC+3, etc.)
# ─────────────────────────────────────────────────────
BROKER_TASKS = [
    ("01:00", task_start_bridge,  "Start bridge — broker day open"),
    ("01:30", task_update_data,   "Data update — daily gap fill"),
    ("07:30", task_check_retrain, "Model retrain check (Mondays)"),
    ("23:55", task_stop_bridge,   "Stop bridge — before midnight reset"),
    ("23:58", task_daily_report,  "Daily report"),
]

def _broker_now():
    """Current broker wall-clock time (UTC+3) — from PC clock."""
    return datetime.now(_BROKER_TZ)  # Bug 41 fix: use module-level constant, no local import

def _check_broker_tasks(fired_today: set) -> set:
    """Fire any BROKER_TASKS whose broker time has arrived."""
    bt       = _broker_now()
    b_total  = bt.hour * 60 + bt.minute   # broker time in total minutes
    b_date   = str(bt.date())

    for broker_time_str, task_fn, label in BROKER_TASKS:
        bh, bm     = map(int, broker_time_str.split(":"))
        task_total = bh * 60 + bm
        task_key   = f"{b_date}_{broker_time_str}"

        # Bug fix: fire within a 0–2 min catch-up window instead of exact-minute
        # equality. A slow loop iteration (e.g. a 60s data-update subprocess) can
        # skip the exact scheduled minute, which previously meant the task NEVER
        # fired that day (a cause of missed daily updates). The fired_today guard
        # still prevents re-firing, and the small window avoids firing past-due
        # tasks on a mid-day startup.
        if 0 <= (b_total - task_total) <= 2 and task_key not in fired_today:
            fired_today.add(task_key)
            log.info(f"⏰ Broker {broker_time_str} → {label}")
            try:
                task_fn()
            except Exception as _te:
                log.error(f"Task failed [{label}]: {_te}")

    # Keep only today's keys — clean old ones
    fired_today = {k for k in fired_today if k.startswith(b_date)}
    return fired_today

def setup_schedule():
    log.info("Schedule set (ALL times = Broker UTC+3 — PC timezone does not matter):")
    for broker_time_str, _, label in BROKER_TASKS:
        log.info(f"  Broker {broker_time_str} → {label}")

def main():
    log.info("="*55)
    log.info("  QUANT GOLD AI v2 — Auto Scheduler")
    log.info(f"  Started: {datetime.now(_BROKER_TZ).strftime('%Y-%m-%d %H:%M:%S')} Broker")
    log.info("="*55)

    # Run data update immediately on start
    log.info("\nRunning startup tasks...")
    _load_last_retrain()   # ← check if already trained recently
    task_update_data()
    task_check_retrain(startup=True)  # startup=True → only retrain if models missing

    # 24hr system — start bridge after data update + retrain
    task_start_bridge()

    # Setup schedule — prints broker-time task list
    setup_schedule()

    # Watchdog + main loop state
    _fired_today  = set()     # tracks which broker-time tasks fired today
    _watchdog_sec = 0         # seconds since last watchdog check
    _shadow_sec   = 840       # 2026-06-23: refresh shadow paper-ledger every 15 min
                              #   (seeded high so it runs ~1 min after start too)

    log.info("\n✅ Scheduler running (Broker time based)! Press Ctrl+C to stop.\n")

    try:
        while True:
            bt = _broker_now()

            # ── Broker-time task scheduler ──────────────────
            _fired_today = _check_broker_tasks(_fired_today)

            # ── Watchdog: check every 5 min ─────────────────
            _watchdog_sec += 30
            if _watchdog_sec >= 300:
                _watchdog_sec = 0
                if bridge_process is not None and bridge_process.poll() is not None:
                    # Block restarts during broker 23:50–01:00 midnight window
                    b_hhmm = bt.hour * 100 + bt.minute
                    in_midnight_window = (b_hhmm >= 2350 or b_hhmm < 100)
                    if in_midnight_window:
                        log.info(f"Watchdog: Broker {bt.strftime('%H:%M')} — no restart (midnight window 23:50-01:00)")
                    else:
                        log.warning(f"Bridge crashed at Broker {bt.strftime('%H:%M')} — restarting in 10s...")
                        time.sleep(10)
                        task_start_bridge()

            # ── Shadow + chart + signal-log refresh: every 15 min ───
            # Rebuilds logs/shadow_trades.csv, chart JSON, and live OHLC so
            # dashboard stays current without manual refresh. Safe — never touches trading.
            _shadow_sec += 30
            if _shadow_sec >= 900:
                _shadow_sec = 0
                run("shadow_ledger.py", "shadow ledger refresh")
                run("chart_live_ohlc.py", "chart live OHLC refresh")
                run("chart_data.py", "chart data JSON refresh")

            time.sleep(30)

    except KeyboardInterrupt:
        log.info("Stopping scheduler...")
        if bridge_process and bridge_process.poll() is None:
            log.info("Stopping bridge...")
            bridge_process.terminate()
        task_stop_bridge()
        log.info("✅ Stopped!")

if __name__ == "__main__":
    main()
