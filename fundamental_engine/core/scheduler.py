"""
Fundamental Engine — Live Auto-Update Scheduler
================================================
Runs periodic tasks to keep engine data fresh.

Tasks:
  1. News fetch — every 30 min (market hours)
  2. Classify new events — after each fetch
  3. Update reactions — every 5 min (for events released 15+ min ago)
  4. Heartbeat — every hour (log state)

Features:
  - State persistence (last-run times saved to JSON)
  - Market-hours aware (less frequent on weekends)
  - Graceful shutdown (Ctrl+C)
  - Failure recovery (logs and continues)

Usage:
  # Run forever (foreground)
  python C:\\QGAI\\fundamental_engine\\core\\scheduler.py
  
  # Run with custom interval
  python C:\\QGAI\\fundamental_engine\\core\\scheduler.py --news-interval 15
  
  # Run single cycle (for testing)
  python C:\\QGAI\\fundamental_engine\\core\\scheduler.py --once
  
  # Status check (read state file)
  python C:\\QGAI\\fundamental_engine\\core\\scheduler.py --status

To run as background process:
  Windows Task Scheduler:
    Action: Start a program
    Program: python.exe
    Arguments: C:\\QGAI\\fundamental_engine\\core\\scheduler.py
    Start in: C:\\QGAI\\fundamental_engine\\
    Trigger: At startup OR daily at 6am
"""

import sys
import os
import json
import time
import signal
import logging
import argparse
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ============================================================
# PATH SETUP
# ============================================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc

# ============================================================
# CONFIG
# ============================================================
SCHEDULER_VERSION = "1.0.0"

# Default intervals (minutes)
DEFAULT_NEWS_INTERVAL = 30
DEFAULT_REACTIONS_INTERVAL = 5
DEFAULT_HEARTBEAT_INTERVAL = 60
MAIN_LOOP_SLEEP_SEC = 60  # Check tasks every 60 seconds

# State file
STATE_FILE = os.path.join(os.path.dirname(fc.LOG_FILE), "scheduler_state.json")

# Quiet hours (UTC) — reduced activity
QUIET_HOURS_START = 0   # midnight UTC
QUIET_HOURS_END = 5     # 5am UTC

# Scripts to run
NEWS_FETCHER_SCRIPT = SCRIPT_DIR / "news_fetcher.py"
CLASSIFIER_SCRIPT = SCRIPT_DIR / "classifier_v3.py"
REACTIONS_SCRIPT = SCRIPT_DIR / "historical_reactions.py"


# ============================================================
# LOGGING
# ============================================================
LOG_FILE = os.path.join(os.path.dirname(fc.LOG_FILE), "scheduler.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("scheduler")


# ============================================================
# SHUTDOWN HANDLER
# ============================================================
class GracefulShutdown:
    shutdown_requested = False
    
    def __init__(self):
        signal.signal(signal.SIGINT, self.request_shutdown)
        try:
            signal.signal(signal.SIGTERM, self.request_shutdown)
        except (AttributeError, ValueError):
            pass  # Some platforms don't support SIGTERM
    
    def request_shutdown(self, signum, frame):
        log.info("Shutdown requested (signal received)")
        GracefulShutdown.shutdown_requested = True


# ============================================================
# STATE MANAGEMENT
# ============================================================
def load_state() -> dict:
    """Load last-run times from state file."""
    default_state = {
        "scheduler_version": SCHEDULER_VERSION,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "last_news_fetch": None,
        "last_classifier": None,
        "last_reactions": None,
        "last_heartbeat": None,
        "cycles_completed": 0,
        "tasks_executed": {
            "news_fetch": 0,
            "classifier": 0,
            "reactions": 0,
            "heartbeat": 0,
        },
        "errors": [],
    }
    
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                loaded = json.load(f)
            # Merge with defaults (preserve loaded values, add missing keys)
            for k, v in default_state.items():
                if k not in loaded:
                    loaded[k] = v
            return loaded
        except Exception as e:
            log.warning(f"Could not load state file: {e}. Using defaults.")
    
    return default_state


def save_state(state: dict):
    """Save state to JSON file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Could not save state: {e}")


# ============================================================
# UTILITY: Should task run?
# ============================================================
def minutes_since(timestamp_str: str) -> float:
    """Returns minutes since given ISO timestamp. Returns inf if None."""
    if not timestamp_str:
        return float('inf')
    try:
        ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - ts).total_seconds() / 60.0
    except Exception:
        return float('inf')


def should_run_news_fetch(state: dict, interval_min: int) -> bool:
    """Check if news fetch should run."""
    return minutes_since(state.get("last_news_fetch")) >= interval_min


def should_run_classifier(state: dict) -> bool:
    """Run classifier shortly after news fetch."""
    news_min = minutes_since(state.get("last_news_fetch"))
    classifier_min = minutes_since(state.get("last_classifier"))
    # Run if news was just fetched (within 5 min) and classifier hasn't run since
    if news_min < 5 and classifier_min > news_min:
        return True
    # Also run every 2 hours as safety
    return classifier_min >= 120


def should_run_reactions(state: dict, interval_min: int) -> bool:
    return minutes_since(state.get("last_reactions")) >= interval_min


def should_run_heartbeat(state: dict, interval_min: int) -> bool:
    return minutes_since(state.get("last_heartbeat")) >= interval_min


def is_quiet_hours() -> bool:
    """Check if we're in low-activity hours (UTC)."""
    hour = datetime.now(timezone.utc).hour
    return QUIET_HOURS_START <= hour < QUIET_HOURS_END


def is_weekend() -> bool:
    """Check if weekend (Sat/Sun UTC)."""
    return datetime.now(timezone.utc).weekday() >= 5


# ============================================================
# TASK: Run subprocess safely
# ============================================================
def run_script(script_path: Path, extra_args: list = None, timeout_sec: int = 600) -> dict:
    """Run a Python script as subprocess. Returns dict with status."""
    args = [sys.executable, str(script_path)]
    if extra_args:
        args.extend(extra_args)
    
    started = datetime.now(timezone.utc)
    
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            encoding='utf-8',
            errors='replace',
        )
        
        ended = datetime.now(timezone.utc)
        duration = (ended - started).total_seconds()
        
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "duration_sec": round(duration, 1),
            "stdout_tail": result.stdout[-500:] if result.stdout else "",
            "stderr_tail": result.stderr[-500:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "TIMEOUT", "duration_sec": timeout_sec}
    except Exception as e:
        return {"success": False, "error": str(e), "duration_sec": 0}


# ============================================================
# TASKS
# ============================================================
def task_news_fetch(state: dict) -> bool:
    """Fetch latest news from FF JSON."""
    log.info(">>> Task: News Fetch")
    
    if not NEWS_FETCHER_SCRIPT.exists():
        log.error(f"News fetcher script not found: {NEWS_FETCHER_SCRIPT}")
        return False
    
    result = run_script(NEWS_FETCHER_SCRIPT, timeout_sec=120)
    
    if result["success"]:
        log.info(f"   [OK] News fetch complete in {result['duration_sec']}s")
        state["last_news_fetch"] = datetime.now(timezone.utc).isoformat()
        state["tasks_executed"]["news_fetch"] += 1
        return True
    else:
        err = result.get("error") or result.get("stderr_tail", "unknown")
        log.error(f"   [FAIL] News fetch failed: {err}")
        state["errors"].append({
            "task": "news_fetch",
            "time": datetime.now(timezone.utc).isoformat(),
            "error": err,
        })
        return False


def task_classifier(state: dict) -> bool:
    """Re-classify events (incremental, no force)."""
    log.info(">>> Task: Classify Events")
    
    if not CLASSIFIER_SCRIPT.exists():
        log.error(f"Classifier script not found: {CLASSIFIER_SCRIPT}")
        return False
    
    # No --force flag — only adds new classifications
    result = run_script(CLASSIFIER_SCRIPT, timeout_sec=180)
    
    if result["success"]:
        log.info(f"   [OK] Classifier complete in {result['duration_sec']}s")
        state["last_classifier"] = datetime.now(timezone.utc).isoformat()
        state["tasks_executed"]["classifier"] += 1
        return True
    else:
        err = result.get("error") or result.get("stderr_tail", "unknown")
        log.error(f"   [FAIL] Classifier failed: {err}")
        state["errors"].append({
            "task": "classifier",
            "time": datetime.now(timezone.utc).isoformat(),
            "error": err,
        })
        return False


def task_reactions(state: dict) -> bool:
    """Update gold reactions for recent events."""
    log.info(">>> Task: Update Reactions")
    
    if not REACTIONS_SCRIPT.exists():
        log.error(f"Reactions script not found: {REACTIONS_SCRIPT}")
        return False
    
    # Run incremental (without --force) — INSERT OR REPLACE in script handles dedup
    result = run_script(REACTIONS_SCRIPT, timeout_sec=300)
    
    if result["success"]:
        log.info(f"   [OK] Reactions update complete in {result['duration_sec']}s")
        state["last_reactions"] = datetime.now(timezone.utc).isoformat()
        state["tasks_executed"]["reactions"] += 1
        return True
    else:
        err = result.get("error") or result.get("stderr_tail", "unknown")
        log.error(f"   [FAIL] Reactions failed: {err}")
        state["errors"].append({
            "task": "reactions",
            "time": datetime.now(timezone.utc).isoformat(),
            "error": err,
        })
        return False


def task_heartbeat(state: dict) -> bool:
    """Log current engine state."""
    log.info(">>> Heartbeat")
    
    try:
        conn = sqlite3.connect(fc.DB_PATH)
        cursor = conn.cursor()
        
        stats = {}
        
        # Table counts
        for table in ["events_raw", "events_investing_raw", "events_classified", "gold_reactions"]:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            except:
                stats[table] = "N/A"
        
        # Recent activity (events in last 24 hours by release_time)
        cursor.execute("""
            SELECT COUNT(*) FROM events_classified
            WHERE datetime(release_time) >= datetime('now', '-24 hours')
        """)
        recent_24h = cursor.fetchone()[0]
        
        # Hit rate overall
        cursor.execute("""
            SELECT
                SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END),
                SUM(CASE WHEN direction_matched = 0 THEN 1 ELSE 0 END)
            FROM gold_reactions
            WHERE data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
        """)
        matched, mismatched = cursor.fetchone()
        matched = matched or 0
        mismatched = mismatched or 0
        det = matched + mismatched
        hit_rate = (matched / det * 100) if det > 0 else 0
        
        conn.close()
        
        log.info(f"   Tables: investing={stats['events_investing_raw']}, classified={stats['events_classified']}, reactions={stats['gold_reactions']}")
        log.info(f"   Last 24h events: {recent_24h}")
        log.info(f"   Overall hit rate: {hit_rate:.1f}% ({matched}/{det})")
        log.info(f"   Tasks run: fetch={state['tasks_executed']['news_fetch']}, classifier={state['tasks_executed']['classifier']}, reactions={state['tasks_executed']['reactions']}")
        log.info(f"   Errors logged: {len(state['errors'])}")
        
        state["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        state["tasks_executed"]["heartbeat"] += 1
        state["last_stats"] = stats
        state["last_hit_rate"] = round(hit_rate, 1)
        
        return True
    
    except Exception as e:
        log.error(f"   [FAIL] Heartbeat error: {e}")
        return False


# ============================================================
# MAIN LOOP
# ============================================================
def main_loop(news_interval: int, reactions_interval: int, heartbeat_interval: int, single_cycle: bool):
    """Main scheduler loop."""
    shutdown_handler = GracefulShutdown()
    state = load_state()
    
    log.info("=" * 70)
    log.info("FUNDAMENTAL ENGINE SCHEDULER STARTED")
    log.info("=" * 70)
    log.info(f"Version:            {SCHEDULER_VERSION}")
    log.info(f"News interval:      {news_interval} min")
    log.info(f"Reactions interval: {reactions_interval} min")
    log.info(f"Heartbeat interval: {heartbeat_interval} min")
    log.info(f"Quiet hours UTC:    {QUIET_HOURS_START}:00 - {QUIET_HOURS_END}:00")
    log.info(f"Log file:           {LOG_FILE}")
    log.info(f"State file:         {STATE_FILE}")
    log.info("Press Ctrl+C for graceful shutdown")
    log.info("")
    
    cycle = 0
    
    while not GracefulShutdown.shutdown_requested:
        cycle += 1
        state["cycles_completed"] = cycle
        
        try:
            # Skip heavy tasks during quiet hours unless first cycle
            in_quiet = is_quiet_hours()
            in_weekend = is_weekend()
            
            # Heartbeat
            if should_run_heartbeat(state, heartbeat_interval):
                task_heartbeat(state)
                save_state(state)
            
            # News fetch
            if should_run_news_fetch(state, news_interval):
                if in_quiet:
                    log.info("(quiet hours — skipping news fetch this cycle)")
                else:
                    task_news_fetch(state)
                    save_state(state)
            
            # Classifier (after news fetch)
            if should_run_classifier(state):
                task_classifier(state)
                save_state(state)
            
            # Reactions update
            if should_run_reactions(state, reactions_interval):
                if in_quiet:
                    pass  # Skip quietly
                else:
                    task_reactions(state)
                    save_state(state)
            
            if single_cycle:
                log.info("Single cycle complete (--once mode)")
                break
            
            # Sleep
            for _ in range(MAIN_LOOP_SLEEP_SEC):
                if GracefulShutdown.shutdown_requested:
                    break
                time.sleep(1)
        
        except Exception as e:
            log.error(f"Loop error (cycle {cycle}): {e}")
            time.sleep(10)
    
    # Final save
    save_state(state)
    log.info("Scheduler stopped gracefully")


# ============================================================
# STATUS DISPLAY
# ============================================================
def show_status():
    """Display scheduler status from state file."""
    print("=" * 70)
    print("FUNDAMENTAL ENGINE SCHEDULER — STATUS")
    print("=" * 70)
    
    state = load_state()
    
    print(f"\nState file:         {STATE_FILE}")
    print(f"State exists:       {os.path.exists(STATE_FILE)}")
    print(f"Scheduler version:  {state.get('scheduler_version', '?')}")
    print(f"Started at:         {state.get('started_at', '?')}")
    print(f"Cycles completed:   {state.get('cycles_completed', 0)}")
    
    print(f"\nLast runs:")
    for key, label in [
        ("last_news_fetch", "News fetch"),
        ("last_classifier", "Classifier"),
        ("last_reactions", "Reactions"),
        ("last_heartbeat", "Heartbeat"),
    ]:
        last = state.get(key)
        if last:
            mins = minutes_since(last)
            print(f"  {label:14}    {last}  ({mins:.1f} min ago)")
        else:
            print(f"  {label:14}    never")
    
    print(f"\nTasks executed:")
    for task, count in state.get("tasks_executed", {}).items():
        print(f"  {task:14}    {count}")
    
    print(f"\nErrors: {len(state.get('errors', []))}")
    for err in state.get("errors", [])[-3:]:  # Last 3 errors
        print(f"  - [{err.get('time', '?')}] {err.get('task', '?')}: {err.get('error', '?')[:100]}")
    
    if state.get("last_stats"):
        print(f"\nLast DB stats:")
        for k, v in state["last_stats"].items():
            print(f"  {k:25}  {v}")
        print(f"  Overall hit rate:      {state.get('last_hit_rate', '?')}%")
    
    print()


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Fundamental engine scheduler")
    parser.add_argument("--news-interval", type=int, default=DEFAULT_NEWS_INTERVAL)
    parser.add_argument("--reactions-interval", type=int, default=DEFAULT_REACTIONS_INTERVAL)
    parser.add_argument("--heartbeat-interval", type=int, default=DEFAULT_HEARTBEAT_INTERVAL)
    parser.add_argument("--once", action="store_true", help="Run single cycle and exit")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    args = parser.parse_args()
    
    if args.status:
        show_status()
        return
    
    main_loop(
        news_interval=args.news_interval,
        reactions_interval=args.reactions_interval,
        heartbeat_interval=args.heartbeat_interval,
        single_cycle=args.once,
    )


if __name__ == "__main__":
    main()
