"""
Investing.com Smart Daily Scraper v2 — FAST FIRE
==================================================
Pre-warm + Sub-second capture strategy.

Strategy:
  T-30s: Pre-warm connection (keep-alive ping, no real data fetch)
  T+0.5s: Fire request #1 (likely catches if data ready)
  T+1.5s: Fire request #2 (retry if empty)
  ... up to T+10s in 1s intervals
  
  After T+10s: Slow retry (60s intervals × 3)

Result:
  Data captured within 0.5-2 seconds of release
  Pro-grade speed, automated

Usage:
  python investing_smart_daily.py
  python investing_smart_daily.py --morning-only
  python investing_smart_daily.py --resume
"""

import sys
import os
import time
import random
import argparse
import sqlite3
import logging
import signal
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    import cloudscraper
    from bs4 import BeautifulSoup
    from zoneinfo import ZoneInfo
except ImportError:
    print("ERROR: pip install cloudscraper beautifulsoup4 lxml")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc

LOG_FILE = os.path.join(os.path.dirname(fc.LOG_FILE), "investing_smart.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("investing_smart")

# Timezone objects (DST-aware)
NY_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")

# ============================================================
# CONFIG — FAST FIRE TIMING
# ============================================================
ENDPOINT = "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData"
INITIAL_PAGE = "https://www.investing.com/economic-calendar/"

# Note: investing.com API returns times in US Eastern (NY) timezone.
# Conversion to UTC is done via zoneinfo (DST-aware) in parse_events().

PRE_WARM_OFFSET_SEC = 30        # Warm-up connection this many seconds before event
INITIAL_FIRE_OFFSET_SEC = 0.5   # First fire this many seconds AFTER event time
FAST_RETRY_INTERVAL_SEC = 1.0   # Between fast retries
FAST_RETRY_MAX_SEC = 10.0       # Stop fast retries after this duration
SLOW_RETRY_INTERVAL_SEC = 60    # Slow retry interval
SLOW_RETRY_MAX = 3              # Up to 3 slow retries

CURRENCY_IDS = {
    "USD": 5, "EUR": 72, "GBP": 4, "JPY": 35, "AUD": 25,
    "CAD": 6, "CHF": 12, "NZD": 43, "CNY": 37,
}
COUNTRY_IDS = list(CURRENCY_IDS.values())
IMPORTANCE = ["2", "3"]


class Shutdown:
    requested = False

def signal_handler(signum, frame):
    log.info("Shutdown requested")
    Shutdown.requested = True

signal.signal(signal.SIGINT, signal_handler)
try:
    signal.signal(signal.SIGTERM, signal_handler)
except (AttributeError, ValueError):
    pass


# ============================================================
# SCRAPER SESSION
# ============================================================
class ScraperSession:
    def __init__(self):
        self.scraper = None
        self.last_warmup = None
    
    def get_scraper(self):
        if self.scraper is None:
            self.scraper = cloudscraper.create_scraper(
                browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
            )
        return self.scraper
    
    def warm_up(self, force=False):
        """Pre-establish TCP/SSL session. Reduces first-request latency."""
        now = datetime.now()
        if not force and self.last_warmup and (now - self.last_warmup).total_seconds() < 300:
            log.debug("Recent warm-up, skipping")
            return
        
        log.info("[PRE-WARM] Establishing session...")
        try:
            t0 = time.time()
            self.get_scraper().get(INITIAL_PAGE, timeout=15)
            elapsed = time.time() - t0
            log.info(f"[PRE-WARM] Done in {elapsed:.2f}s")
            self.last_warmup = now
        except Exception as e:
            log.warning(f"Warm-up failed (non-critical): {e}")
    
    def fetch(self, date_from: str, date_to: str, log_timing: bool = False) -> Optional[str]:
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': '*/*',
            'Origin': 'https://www.investing.com',
            'Referer': INITIAL_PAGE,
        }
        
        data = {
            'country[]': COUNTRY_IDS,
            'importance[]': IMPORTANCE,
            'timeZone': '0',
            'timeFilter': 'timeRemain',
            'currentTab': 'custom',
            'dateFrom': date_from,
            'dateTo': date_to,
            'submitFilters': '1',
            'limit_from': '0',
        }
        
        try:
            t0 = time.time()
            r = self.get_scraper().post(ENDPOINT, headers=headers, data=data, timeout=15)
            elapsed = time.time() - t0
            
            if log_timing:
                log.info(f"  [FETCH] {elapsed*1000:.0f}ms status={r.status_code}")
            
            if r.status_code == 200:
                return r.json().get('data', '')
            elif r.status_code == 429:
                log.error("RATE LIMITED (429)")
                return None
            else:
                log.error(f"HTTP {r.status_code}")
                return None
        except Exception as e:
            log.error(f"Fetch error: {e}")
            return None


# ============================================================
# PARSING (same as v1)
# ============================================================
def parse_events(html: str) -> list:
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'lxml')
    events = []
    rows = soup.find_all('tr', {'data-event-datetime': True})
    
    for row in rows:
        try:
            event_id = row.get('id', '').replace('eventRowId_', '')
            event_dt = row.get('data-event-datetime', '')
            if not event_dt:
                continue
            
            try:
                release_time = datetime.strptime(event_dt, "%Y/%m/%d %H:%M:%S")
            except ValueError:
                try:
                    release_time = datetime.strptime(event_dt, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
            
            # Convert US Eastern Time → UTC (DST-aware via zoneinfo)
            # investing.com API returns times in NY timezone regardless of timeZone param
            release_time_ny = release_time.replace(tzinfo=NY_TZ)
            release_time = release_time_ny.astimezone(UTC_TZ).replace(tzinfo=None)
            
            curr_cell = row.find('td', class_='flagCur')
            currency = curr_cell.get_text(strip=True) if curr_cell else ""
            
            imp_cell = row.find('td', class_='sentiment')
            impact_stars = 0
            if imp_cell:
                impact_stars = len(imp_cell.find_all('i', class_='grayFullBullishIcon'))
            
            event_cell = row.find('td', class_='event')
            event_title = event_cell.get_text(strip=True) if event_cell else ""
            
            actual_cell = row.find('td', class_='act')
            actual = actual_cell.get_text(strip=True) if actual_cell else ""
            if actual in ('\u00a0', '', ' '):
                actual = ""
            
            forecast_cell = row.find('td', class_='fore')
            forecast = forecast_cell.get_text(strip=True) if forecast_cell else ""
            
            previous_cell = row.find('td', class_='prev')
            previous = previous_cell.get_text(strip=True) if previous_cell else ""
            
            events.append({
                "event_id": event_id,
                "release_time": release_time,
                "release_time_iso": release_time.isoformat(),
                "currency": currency,
                "country": "",
                "impact_stars": impact_stars,
                "event_title": event_title,
                "actual": actual,
                "forecast": forecast,
                "previous": previous,
                "has_actual": bool(actual),
            })
        except Exception:
            continue
    
    return events


# ============================================================
# DATABASE
# ============================================================
def ensure_table(conn: sqlite3.Connection):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS events_csv_import (
        raw_id              INTEGER PRIMARY KEY AUTOINCREMENT,
        import_date         TIMESTAMP NOT NULL,
        source_file         TEXT NOT NULL,
        event_title         TEXT NOT NULL,
        currency            TEXT NOT NULL,
        release_time        TIMESTAMP NOT NULL,
        impact_stars        INTEGER,
        country             TEXT,
        actual_str          TEXT,
        forecast_str        TEXT,
        previous_str        TEXT,
        actual              TEXT,
        forecast            TEXT,
        previous            TEXT,
        UNIQUE(event_title, currency, release_time)
    );
    """)
    conn.commit()


def upsert_event(conn: sqlite3.Connection, ev: dict, source_tag: str = "investing_smart"):
    cursor = conn.cursor()
    import_date = datetime.now().isoformat()
    
    cursor.execute("""
        SELECT raw_id, actual FROM events_csv_import
        WHERE event_title = ? AND currency = ? AND release_time = ?
    """, (ev["event_title"], ev["currency"], ev["release_time_iso"]))
    
    existing = cursor.fetchone()
    
    if existing is None:
        cursor.execute("""
            INSERT INTO events_csv_import (
                import_date, source_file,
                event_title, currency, release_time,
                impact_stars, country,
                actual_str, forecast_str, previous_str,
                actual, forecast, previous
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (import_date, source_tag,
              ev["event_title"], ev["currency"], ev["release_time_iso"],
              ev["impact_stars"], ev["country"],
              ev["actual"], ev["forecast"], ev["previous"],
              ev["actual"], ev["forecast"], ev["previous"]))
        conn.commit()
        return "inserted"
    elif ev["actual"] and ev["actual"] != (existing[1] or ""):
        cursor.execute("""
            UPDATE events_csv_import
            SET actual = ?, actual_str = ?, import_date = ?
            WHERE raw_id = ?
        """, (ev["actual"], ev["actual"], import_date, existing[0]))
        conn.commit()
        return "updated"
    return "skipped"


# ============================================================
# MORNING SNAPSHOT
# ============================================================
def morning_snapshot(session: ScraperSession, conn: sqlite3.Connection, target_date: datetime) -> list:
    # Query today + tomorrow to capture timezone-edge events
    date_from_str = target_date.strftime("%Y-%m-%d")
    date_to_str = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")
    log.info(f"=== MORNING SNAPSHOT: {date_from_str} to {date_to_str} ===")
    
    session.warm_up(force=True)
    
    html = session.fetch(date_from_str, date_to_str)
    if html is None:
        log.error("Morning fetch failed")
        return []
    
    all_events = parse_events(html)
    
    # Filter to events within target UTC day (00:00 to 23:59 of target_date in UTC)
    target_day_start = datetime.combine(target_date.date(), datetime.min.time())
    target_day_end = target_day_start + timedelta(days=1)
    
    events = [ev for ev in all_events 
              if target_day_start <= ev["release_time"] < target_day_end]
    
    log.info(f"Found {len(all_events)} total events in {date_from_str}-{date_to_str} range, {len(events)} within target UTC day")
    
    for ev in events:
        upsert_event(conn, ev, source_tag="investing_smart_morning")
    
    log.info("Today's schedule (UTC times):")
    for ev in events:
        time_str = ev["release_time"].strftime("%H:%M")
        actual_str = f"A={ev['actual']}" if ev["has_actual"] else "[pending]"
        log.info(f"  {time_str} [{ev['currency']}] {ev['event_title']:<40} {actual_str}")
    
    return events


# ============================================================
# FAST-FIRE EVENT CAPTURE
# ============================================================
def capture_event_fast(session: ScraperSession, conn: sqlite3.Connection, ev: dict) -> bool:
    """
    Fast-fire strategy:
      - Pre-warm at T-30s
      - Fire at T+0.5s, T+1.5s, T+2.5s... up to T+10s
      - Then slow retry (60s × 3)
    
    Returns True if actual captured.
    """
    
    event_time = ev["release_time"]
    now = datetime.now()
    
    # Phase 1: Wait until T-30s (pre-warm window)
    pre_warm_time = event_time - timedelta(seconds=PRE_WARM_OFFSET_SEC)
    if now < pre_warm_time:
        wait_sec = (pre_warm_time - now).total_seconds()
        log.info(f"  Sleeping {wait_sec:.0f}s until pre-warm time ({pre_warm_time.strftime('%H:%M:%S')})")
        
        sleep_remaining = wait_sec
        while sleep_remaining > 0 and not Shutdown.requested:
            chunk = min(sleep_remaining, 5)
            time.sleep(chunk)
            sleep_remaining -= chunk
        
        if Shutdown.requested:
            return False
    
    # Phase 2: Pre-warm
    log.info(f"  [T-{PRE_WARM_OFFSET_SEC}s] Pre-warming connection...")
    session.warm_up(force=True)
    
    # Phase 3: Wait until T+initial_fire_offset
    first_fire_time = event_time + timedelta(seconds=INITIAL_FIRE_OFFSET_SEC)
    now = datetime.now()
    if now < first_fire_time:
        wait_sec = (first_fire_time - now).total_seconds()
        log.info(f"  Waiting {wait_sec:.1f}s for release (first fire at {first_fire_time.strftime('%H:%M:%S.%f')[:-3]})")
        time.sleep(wait_sec)
    
    # Phase 4: Fast-fire loop
    log.info(f"  === FAST-FIRE MODE === ({ev['event_title']})")
    
    fast_fire_start = time.time()
    fire_count = 0
    
    while not Shutdown.requested:
        elapsed_since_fast_fire = time.time() - fast_fire_start
        
        if elapsed_since_fast_fire > FAST_RETRY_MAX_SEC:
            log.info(f"  Fast-fire exhausted after {elapsed_since_fast_fire:.1f}s ({fire_count} attempts)")
            break
        
        fire_count += 1
        elapsed_since_event = (datetime.now() - event_time).total_seconds()
        
        log.info(f"  [Fire #{fire_count}] T+{elapsed_since_event:.1f}s")
        
        date_str = event_time.strftime("%Y-%m-%d")
        html = session.fetch(date_str, date_str, log_timing=True)
        
        if html:
            new_events = parse_events(html)
            for ne in new_events:
                if (ne["event_title"] == ev["event_title"] and
                    ne["currency"] == ev["currency"] and
                    ne["release_time"] == ev["release_time"]):
                    if ne["has_actual"]:
                        result = upsert_event(conn, ne, source_tag="investing_smart_fastfire")
                        elapsed_since_event = (datetime.now() - event_time).total_seconds()
                        log.info(f"  ✓✓✓ CAPTURED at T+{elapsed_since_event:.1f}s: A={ne['actual']}, F={ne['forecast']} ({result})")
                        return True
                    break
        
        time.sleep(FAST_RETRY_INTERVAL_SEC)
    
    # Phase 5: Slow retry
    log.warning(f"  Falling back to slow retry...")
    
    for slow_attempt in range(SLOW_RETRY_MAX):
        if Shutdown.requested:
            return False
        
        log.info(f"  Slow retry {slow_attempt+1}/{SLOW_RETRY_MAX} (sleeping {SLOW_RETRY_INTERVAL_SEC}s)")
        
        sleep_remaining = SLOW_RETRY_INTERVAL_SEC
        while sleep_remaining > 0 and not Shutdown.requested:
            chunk = min(sleep_remaining, 5)
            time.sleep(chunk)
            sleep_remaining -= chunk
        
        date_str = event_time.strftime("%Y-%m-%d")
        html = session.fetch(date_str, date_str)
        
        if html:
            new_events = parse_events(html)
            for ne in new_events:
                if (ne["event_title"] == ev["event_title"] and
                    ne["currency"] == ev["currency"] and
                    ne["release_time"] == ev["release_time"]):
                    if ne["has_actual"]:
                        result = upsert_event(conn, ne, source_tag="investing_smart_slow")
                        elapsed = (datetime.now() - event_time).total_seconds()
                        log.info(f"  ✓ Captured (slow) at T+{elapsed:.0f}s: A={ne['actual']}")
                        return True
                    break
    
    log.error(f"  ✗ Failed to capture {ev['event_title']}")
    return False


# ============================================================
# WATCH LOOP
# ============================================================
def event_watch_loop(session: ScraperSession, conn: sqlite3.Connection, events: list):
    now = datetime.now()
    pending = [ev for ev in events if not ev["has_actual"] and ev["release_time"] > now]
    pending.sort(key=lambda e: e["release_time"])
    
    if not pending:
        log.info("No pending events")
        return
    
    log.info(f"=== EVENT WATCH: {len(pending)} pending events ===")
    
    for i, ev in enumerate(pending, 1):
        if Shutdown.requested:
            break
        
        log.info(f"\n--- Event {i}/{len(pending)} ---")
        log.info(f"  Time:     {ev['release_time'].strftime('%H:%M:%S')}")
        log.info(f"  Currency: {ev['currency']}")
        log.info(f"  Title:    {ev['event_title']}")
        log.info(f"  Forecast: {ev['forecast']}, Previous: {ev['previous']}")
        
        capture_event_fast(session, conn, ev)
    
    log.info("\nEvent watch complete")


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--morning-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--date", type=str, default=None)
    args = parser.parse_args()
    
    print("=" * 70)
    print("INVESTING.COM SMART DAILY v2 — FAST FIRE")
    print("=" * 70)
    
    target_date = datetime.strptime(args.date, "%Y-%m-%d") if args.date else datetime.now()
    
    print(f"\nDate:                 {target_date.strftime('%Y-%m-%d')}")
    print(f"Pre-warm:             T-{PRE_WARM_OFFSET_SEC}s")
    print(f"Initial fire:         T+{INITIAL_FIRE_OFFSET_SEC}s")
    print(f"Fast-retry interval:  {FAST_RETRY_INTERVAL_SEC}s")
    print(f"Fast-retry duration:  {FAST_RETRY_MAX_SEC}s")
    print(f"Currencies:           {list(CURRENCY_IDS.keys())}")
    
    if args.dry_run:
        print("\n[DRY RUN]")
        return
    
    session = ScraperSession()
    conn = sqlite3.connect(fc.DB_PATH)
    ensure_table(conn)
    
    try:
        events = []
        if not args.resume:
            events = morning_snapshot(session, conn, target_date)
            if not events:
                print("\nNo events. Exit.")
                return
            print(f"\n✓ Morning: {len(events)} events captured")
        
        if not args.morning_only:
            if args.resume:
                events = morning_snapshot(session, conn, target_date)
            
            print(f"\nStarting fast-fire watch (Ctrl+C to stop)...")
            event_watch_loop(session, conn, events)
    
    finally:
        conn.close()
    
    print("\nDONE.\n")


if __name__ == "__main__":
    main()
