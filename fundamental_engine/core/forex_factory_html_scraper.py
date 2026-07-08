"""
ForexFactory HTML Calendar Scraper
===================================
Scrapes weekly calendar from forexfactory.com/calendar HTML pages.
Captures ACTUAL values not available in JSON/XML feeds.

Stores in new table: events_forexfactory_raw (separate from existing tables)

Strategy:
  - URL pattern: https://www.forexfactory.com/calendar?week=MMM<DD>.YYYY
  - Iterate week-by-week going back N days
  - Parse calendar__table HTML structure
  - Polite delay (3s) between weeks
  - Resumable (UNIQUE constraint prevents duplicates)

Expected:
  - 2 years = 104 weeks
  - ~50-80 events per week (filtered to High/Medium/Low impact)
  - Total: ~5000-8000 events
  - Runtime: ~6-8 minutes

Usage:
  python C:\\QGAI\\fundamental_engine\\core\\forex_factory_html_scraper.py
  
  # Custom range
  python C:\\QGAI\\fundamental_engine\\core\\forex_factory_html_scraper.py --weeks 52
  
  # Faster (smaller delay)
  python C:\\QGAI\\fundamental_engine\\core\\forex_factory_html_scraper.py --delay 2

Module: fundamental_engine.core.forex_factory_html_scraper
"""

import sys
import os
import sqlite3
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

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
FF_BASE_URL = "https://www.forexfactory.com/calendar"
DEFAULT_WEEKS_BACK = 104    # 2 years
DEFAULT_DELAY = 3.0
MAX_RETRIES = 3

# Browser-like headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.forexfactory.com/",
}

# Impact class to star mapping
IMPACT_TO_STARS = {
    "high":     3,
    "red":      3,
    "medium":   2,
    "ora":      2,  # orange
    "low":      1,
    "yel":      1,  # yellow
    "holiday":  0,
    "gra":      0,  # gray
    "non":      0,  # non-economic
}


# ============================================================
# LOGGING
# ============================================================
os.makedirs(os.path.dirname(fc.LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format=fc.LOG_FORMAT,
    handlers=[
        logging.FileHandler(fc.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("ff_html_scraper")


# ============================================================
# DATABASE
# ============================================================
def ensure_ff_table(conn: sqlite3.Connection):
    """Create events_forexfactory_raw table if not exists."""
    schema = """
    CREATE TABLE IF NOT EXISTS events_forexfactory_raw (
        raw_id              INTEGER PRIMARY KEY AUTOINCREMENT,
        fetch_date          TIMESTAMP NOT NULL,
        
        event_title         TEXT NOT NULL,
        currency            TEXT NOT NULL,
        release_time        TIMESTAMP NOT NULL,
        
        impact_stars        INTEGER,
        impact_class        TEXT,
        
        forecast            TEXT,
        previous            TEXT,
        actual              TEXT,
        
        week_url            TEXT,
        raw_html            TEXT,
        
        UNIQUE(event_title, currency, release_time)
    );
    """
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_ff_release ON events_forexfactory_raw(release_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_ff_currency ON events_forexfactory_raw(currency, impact_stars);",
        "CREATE INDEX IF NOT EXISTS idx_ff_title ON events_forexfactory_raw(event_title);",
        "CREATE INDEX IF NOT EXISTS idx_ff_actual ON events_forexfactory_raw(actual);",
    ]
    
    cursor = conn.cursor()
    cursor.execute(schema)
    for idx_sql in indexes:
        cursor.execute(idx_sql)
    conn.commit()


# ============================================================
# URL GENERATION
# ============================================================
def format_week_url(week_date) -> str:
    """
    Generate FF week URL.
    Format: https://www.forexfactory.com/calendar?week=MMM<DD>.YYYY
    Example: ...?week=jun15.2025
    """
    month_str = week_date.strftime("%b").lower()
    return f"{FF_BASE_URL}?week={month_str}{week_date.day}.{week_date.year}"


def iterate_weeks(weeks_back: int):
    """
    Generate week start dates going back from today.
    Returns Sunday of each week (FF week starts Sunday).
    """
    today = datetime.now(timezone.utc).date()
    
    # Find Sunday of current week
    days_to_sunday = (today.weekday() + 1) % 7
    current_sunday = today - timedelta(days=days_to_sunday)
    
    for i in range(weeks_back):
        yield current_sunday - timedelta(days=i * 7)


# ============================================================
# FETCH
# ============================================================
def fetch_week_html(url: str) -> Optional[str]:
    """Fetch HTML for one week from ForexFactory."""
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            
            if response.status_code == 200:
                return response.text
            
            if response.status_code == 429:
                wait = 10 * (attempt + 1)
                log.warning(f"FF rate limited (429). Waiting {wait}s...")
                time.sleep(wait)
            elif response.status_code == 403:
                log.warning(f"FF blocked (403): {url}")
                time.sleep(5)
            else:
                log.warning(f"HTTP {response.status_code}: {url}")
                time.sleep(2 * (attempt + 1))
        
        except requests.exceptions.RequestException as e:
            log.error(f"Fetch error: {e}")
            time.sleep(2 * (attempt + 1))
    
    return None


# ============================================================
# PARSING
# ============================================================
def detect_impact_stars(impact_cell) -> tuple:
    """Detect impact level from cell. Returns (stars, class_name)."""
    if not impact_cell:
        return 0, ""
    
    # Look for span with impact class
    icons = impact_cell.find_all("span")
    for icon in icons:
        classes = icon.get("class", [])
        for cls in classes:
            cls_lower = cls.lower()
            # Common FF class patterns
            for keyword, stars in IMPACT_TO_STARS.items():
                if keyword in cls_lower:
                    return stars, cls
    
    # Check title attribute as fallback
    title_attr = impact_cell.get("title", "").lower()
    if "high" in title_attr:
        return 3, "title:high"
    elif "medium" in title_attr:
        return 2, "title:medium"
    elif "low" in title_attr:
        return 1, "title:low"
    elif "holiday" in title_attr or "non-economic" in title_attr:
        return 0, "title:holiday"
    
    # Check icon's title
    icon_title = ""
    icons_with_title = impact_cell.find_all(attrs={"title": True})
    for ic in icons_with_title:
        title_lower = ic.get("title", "").lower()
        if "high" in title_lower:
            return 3, "icon_title:high"
        elif "medium" in title_lower:
            return 2, "icon_title:medium"
        elif "low" in title_lower:
            return 1, "icon_title:low"
        elif "holiday" in title_lower or "non-economic" in title_lower:
            return 0, "icon_title:holiday"
    
    return 0, ""


def parse_calendar_html(html: str, week_start_date, week_url: str) -> list:
    """
    Parse FF calendar HTML.
    Returns list of event dicts.
    """
    events = []
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Find calendar table
    calendar_table = soup.find("table", class_="calendar__table")
    if not calendar_table:
        log.warning(f"calendar__table not found in HTML")
        # Try alternative selector
        calendar_table = soup.find("table", attrs={"class": lambda x: x and "calendar" in str(x)})
        if not calendar_table:
            return events
    
    # Iterate through rows
    rows = calendar_table.find_all("tr")
    
    current_date = week_start_date
    current_time_str = ""
    
    for row in rows:
        try:
            row_class = " ".join(row.get("class", []))
            
            # Day breaker row → update current_date
            if "day-breaker" in row_class or "day-row" in row_class:
                date_cell = row.find("td") or row.find("th")
                if date_cell:
                    date_text = date_cell.get_text(strip=True)
                    parsed_date = try_parse_date(date_text, week_start_date)
                    if parsed_date:
                        current_date = parsed_date
                # Don't parse this row as event (but may have event below)
            
            # Parse as event row
            time_cell = row.find("td", class_=lambda c: c and "time" in str(c).lower())
            event_cell = row.find("td", class_=lambda c: c and "event" in str(c).lower())
            
            if not event_cell:
                continue
            
            # Time
            if time_cell:
                time_text = time_cell.get_text(strip=True)
                if time_text and time_text != "All Day":
                    current_time_str = time_text
            
            # Currency
            cur_cell = row.find("td", class_=lambda c: c and "currency" in str(c).lower())
            currency = cur_cell.get_text(strip=True) if cur_cell else ""
            
            # Impact
            impact_cell = row.find("td", class_=lambda c: c and "impact" in str(c).lower())
            impact_stars, impact_class = detect_impact_stars(impact_cell)
            
            # Event title
            event_title_span = event_cell.find("span", class_=lambda c: c and "title" in str(c).lower())
            if event_title_span:
                event_title = event_title_span.get_text(strip=True)
            else:
                event_title = event_cell.get_text(strip=True)
            
            # Actual
            act_cell = row.find("td", class_=lambda c: c and "actual" in str(c).lower())
            actual = act_cell.get_text(strip=True) if act_cell else ""
            
            # Forecast
            fore_cell = row.find("td", class_=lambda c: c and "forecast" in str(c).lower())
            forecast = fore_cell.get_text(strip=True) if fore_cell else ""
            
            # Previous
            prev_cell = row.find("td", class_=lambda c: c and "previous" in str(c).lower())
            previous = prev_cell.get_text(strip=True) if prev_cell else ""
            
            # Skip empty rows
            if not event_title or not currency:
                continue
            
            # Construct release_time
            release_time = combine_date_time(current_date, current_time_str)
            
            events.append({
                "event_title": event_title,
                "currency": currency,
                "release_time": release_time,
                "impact_stars": impact_stars,
                "impact_class": impact_class,
                "actual": actual,
                "forecast": forecast,
                "previous": previous,
                "week_url": week_url,
                "raw_html": str(row)[:2000],
            })
        
        except Exception as e:
            log.debug(f"Row parse error: {e}")
            continue
    
    return events


def try_parse_date(date_text: str, fallback_week_date) -> Optional[object]:
    """Try to parse date from FF day-breaker text."""
    # Examples: "Mon Jun 9", "Sun Jun 8 2025", etc.
    try:
        # Strip day-of-week
        parts = date_text.replace(",", " ").split()
        if len(parts) >= 2:
            # Try parsing "Mon Jun 9"
            for fmt in ["%a %b %d", "%a %b %d %Y", "%b %d", "%b %d %Y"]:
                try:
                    parsed = datetime.strptime(" ".join(parts[:3]) if len(parts) >= 3 else " ".join(parts), fmt)
                    # Year may be missing — use week year
                    if parsed.year == 1900:
                        parsed = parsed.replace(year=fallback_week_date.year)
                    return parsed.date()
                except:
                    continue
    except:
        pass
    return None


def combine_date_time(date_obj, time_str: str) -> str:
    """Combine date + time into ISO timestamp string."""
    try:
        if not time_str or time_str in ["", "All Day"]:
            return f"{date_obj}T00:00:00"
        
        # Try various time formats: "8:30am", "14:00", "8:30 am"
        time_str_clean = time_str.replace(" ", "").lower()
        
        for fmt in ["%I:%M%p", "%H:%M", "%I%p"]:
            try:
                t = datetime.strptime(time_str_clean, fmt).time()
                combined = datetime.combine(date_obj, t)
                return combined.isoformat()
            except:
                continue
        
        # If parsing fails, return midnight
        return f"{date_obj}T00:00:00"
    except:
        return f"{date_obj}T00:00:00"


# ============================================================
# DB INSERT
# ============================================================
def insert_events(conn: sqlite3.Connection, events: list) -> dict:
    """Insert events into events_forexfactory_raw."""
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    
    fetch_date = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    cursor = conn.cursor()
    
    for ev in events:
        try:
            cursor.execute("""
                SELECT raw_id, actual FROM events_forexfactory_raw
                WHERE event_title = ? AND currency = ? AND release_time = ?
            """, (ev["event_title"], ev["currency"], ev["release_time"]))
            
            existing = cursor.fetchone()
            
            if existing is None:
                cursor.execute("""
                    INSERT INTO events_forexfactory_raw (
                        fetch_date, event_title, currency, release_time,
                        impact_stars, impact_class,
                        forecast, previous, actual,
                        week_url, raw_html
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fetch_date, ev["event_title"], ev["currency"], ev["release_time"],
                    ev["impact_stars"], ev["impact_class"],
                    ev["forecast"], ev["previous"], ev["actual"],
                    ev["week_url"], ev["raw_html"]
                ))
                stats["inserted"] += 1
            else:
                if ev["actual"] and ev["actual"] != (existing[1] or ""):
                    cursor.execute("""
                        UPDATE events_forexfactory_raw
                        SET actual = ?, fetch_date = ?
                        WHERE raw_id = ?
                    """, (ev["actual"], fetch_date, existing[0]))
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
        except Exception:
            pass
    
    conn.commit()
    return stats


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="FF HTML calendar scraper")
    parser.add_argument("--weeks", type=int, default=DEFAULT_WEEKS_BACK,
                        help=f"Weeks back to fetch (default: {DEFAULT_WEEKS_BACK} = 2 years)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help=f"Delay between weeks in seconds (default: {DEFAULT_DELAY})")
    args = parser.parse_args()
    
    print("=" * 70)
    print("FOREXFACTORY HTML CALENDAR SCRAPER")
    print("=" * 70)
    
    print(f"\nWeeks back:    {args.weeks}")
    print(f"Delay:         {args.delay}s between weeks")
    print(f"Est. runtime:  ~{(args.weeks * args.delay) // 60:.0f}-{(args.weeks * (args.delay + 2)) // 60:.0f} min")
    print(f"DB:            {fc.DB_PATH}")
    
    log.info(f"FF HTML scraper starting: {args.weeks} weeks back")
    
    conn = sqlite3.connect(fc.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    ensure_ff_table(conn)
    
    total_stats = {
        "weeks_done": 0,
        "weeks_failed": 0,
        "events_parsed": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
    }
    
    weeks = list(iterate_weeks(args.weeks))
    
    print(f"\nFetching {len(weeks)} weeks (most recent first)...\n")
    
    for idx, week_date in enumerate(weeks):
        week_num = idx + 1
        url = format_week_url(week_date)
        week_str = week_date.strftime("%b %d %Y")
        
        print(f"[{week_num:3}/{len(weeks)}] Week of {week_str:14}  ", end="", flush=True)
        
        html = fetch_week_html(url)
        
        if not html:
            print("FAILED")
            total_stats["weeks_failed"] += 1
            time.sleep(args.delay)
            continue
        
        events = parse_calendar_html(html, week_date, url)
        
        if not events:
            print(f"0 events parsed (HTML size: {len(html)/1024:.1f}KB)")
            total_stats["weeks_failed"] += 1
            time.sleep(args.delay)
            continue
        
        stats = insert_events(conn, events)
        
        total_stats["weeks_done"] += 1
        total_stats["events_parsed"] += len(events)
        total_stats["inserted"] += stats["inserted"]
        total_stats["updated"] += stats["updated"]
        total_stats["skipped"] += stats["skipped"]
        
        print(f"{len(events):3} events | INS:{stats['inserted']:3} UPD:{stats['updated']:2} SKIP:{stats['skipped']:3}")
        
        if idx < len(weeks) - 1:
            time.sleep(args.delay)
    
    # Final stats
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events_forexfactory_raw")
    total_in_db = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT impact_stars, COUNT(*) 
        FROM events_forexfactory_raw 
        GROUP BY impact_stars ORDER BY impact_stars DESC
    """)
    by_stars = dict(cursor.fetchall())
    
    cursor.execute("""
        SELECT currency, COUNT(*) 
        FROM events_forexfactory_raw 
        GROUP BY currency ORDER BY COUNT(*) DESC
        LIMIT 15
    """)
    by_currency = cursor.fetchall()
    
    cursor.execute("""
        SELECT COUNT(*) FROM events_forexfactory_raw 
        WHERE actual IS NOT NULL AND actual != ''
    """)
    with_actual = cursor.fetchone()[0]
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("FF HTML SCRAPER SUMMARY")
    print("=" * 70)
    print(f"Weeks done:        {total_stats['weeks_done']}/{len(weeks)}")
    print(f"Weeks failed:      {total_stats['weeks_failed']}")
    print(f"\nEvents parsed:     {total_stats['events_parsed']}")
    print(f"  Inserted:        {total_stats['inserted']}")
    print(f"  Updated:         {total_stats['updated']}")
    print(f"  Skipped:         {total_stats['skipped']}")
    
    print(f"\nDatabase totals:")
    print(f"  Total events:    {total_in_db}")
    print(f"  With actual:     {with_actual} ({(with_actual/max(total_in_db,1)*100):.1f}%)")
    
    print(f"\nBy impact:")
    for stars in [3, 2, 1, 0]:
        count = by_stars.get(stars, 0)
        label = ["Holiday/Other", "1-star", "2-star", "3-star"][stars]
        print(f"  {label:18}        {count}")
    
    print(f"\nTop currencies:")
    for curr, count in by_currency:
        print(f"  {curr:10}                {count}")
    
    print("\nDONE.\n")


if __name__ == "__main__":
    main()
