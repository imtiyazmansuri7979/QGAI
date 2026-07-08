"""
Investing.com Economic Calendar Scraper v2
============================================
PAGINATION-BASED scraper to bypass the 200-event per request cap.

Key improvements over v1:
  - 14-day chunks (smaller, more reliable)
  - Pagination within each chunk (limit_from parameter)
  - Captures ALL events, not truncated at 200
  - Per-page delay (polite)
  - Better progress reporting
  - Expected: 12,000-15,000 events for 2 years
  - Runtime: ~15-20 minutes

Usage:
  python C:\\QGAI\\fundamental_engine\\core\\investing_com_scraper_v2.py
  
  # Custom range
  python C:\\QGAI\\fundamental_engine\\core\\investing_com_scraper_v2.py --days 365
  
  # Faster (smaller delay - risky)
  python C:\\QGAI\\fundamental_engine\\core\\investing_com_scraper_v2.py --delay 2

Module: fundamental_engine.core.investing_com_scraper_v2
"""

import sys
import os
import json
import sqlite3
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

import cloudscraper
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
INVESTING_URL = "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData"

DEFAULT_DAYS_BACK = 730    # 2 years
CHUNK_DAYS = 14            # 14-day chunks (smaller for pagination efficiency)
DELAY_SEC = 3              # Between chunks
PAGE_DELAY_SEC = 1.5       # Between pages within a chunk
MAX_RETRIES = 3
MAX_PAGES_PER_CHUNK = 15   # Safety limit (would be 3000 events per chunk, way more than realistic)

IMPORTANCE = ["1", "2", "3"]
TIMEZONE_ID = "8"
PAGE_SIZE = 200            # Investing.com fixed at 200


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
log = logging.getLogger("investing_scraper_v2")


# ============================================================
# DATABASE
# ============================================================
def ensure_investing_table(conn: sqlite3.Connection):
    """Create events_investing_raw table if not exists."""
    schema = """
    CREATE TABLE IF NOT EXISTS events_investing_raw (
        raw_id              INTEGER PRIMARY KEY AUTOINCREMENT,
        fetch_date          TIMESTAMP NOT NULL,
        event_title         TEXT NOT NULL,
        currency            TEXT NOT NULL,
        release_time        TIMESTAMP NOT NULL,
        impact_stars        INTEGER,
        forecast            TEXT,
        previous            TEXT,
        actual              TEXT,
        investing_event_id  TEXT,
        event_attr_id       TEXT,
        event_timestamp     INTEGER,
        raw_html            TEXT,
        UNIQUE(event_title, currency, release_time)
    );
    """
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_inv_release ON events_investing_raw(release_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_inv_currency ON events_investing_raw(currency, impact_stars);",
        "CREATE INDEX IF NOT EXISTS idx_inv_title ON events_investing_raw(event_title);",
        "CREATE INDEX IF NOT EXISTS idx_inv_actual ON events_investing_raw(actual);",
    ]
    
    cursor = conn.cursor()
    cursor.execute(schema)
    for idx_sql in indexes:
        cursor.execute(idx_sql)
    conn.commit()


# ============================================================
# FETCH (with pagination support)
# ============================================================
def fetch_page(scraper, date_from: str, date_to: str, limit_from: int) -> Optional[str]:
    """Fetch single page from investing.com (200 events max per page)."""
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.investing.com",
        "Referer": "https://www.investing.com/economic-calendar/",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    
    data = []
    for imp in IMPORTANCE:
        data.append(("importance[]", imp))
    
    data.extend([
        ("timeZone", TIMEZONE_ID),
        ("timeFilter", "timeOnly"),
        ("currentTab", "custom"),
        ("dateFrom", date_from),
        ("dateTo", date_to),
        ("limit_from", str(limit_from)),
        ("submitFilters", "1"),
    ])
    
    for attempt in range(MAX_RETRIES):
        try:
            response = scraper.post(
                INVESTING_URL,
                headers=headers,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.text
            
            if response.status_code == 429:
                # Rate limited - longer backoff
                wait = 10 * (attempt + 1)
                log.warning(f"Rate limited (429). Waiting {wait}s...")
                time.sleep(wait)
            else:
                log.warning(f"HTTP {response.status_code} (attempt {attempt+1})")
                time.sleep(2 * (attempt + 1))
        
        except Exception as e:
            log.error(f"Page fetch error: {e} (attempt {attempt+1})")
            time.sleep(2 * (attempt + 1))
    
    return None


def fetch_chunk_with_pagination(scraper, date_from: str, date_to: str) -> tuple:
    """
    Fetch ALL events for a chunk using pagination.
    Returns (events_list, pages_fetched).
    """
    all_events = []
    page = 0
    
    while page < MAX_PAGES_PER_CHUNK:
        limit_from = page * PAGE_SIZE
        response = fetch_page(scraper, date_from, date_to, limit_from)
        
        if not response:
            # Failed page, but might have data from earlier pages
            break
        
        events = parse_response(response)
        
        if not events:
            # Empty page = end of pagination
            break
        
        all_events.extend(events)
        page += 1
        
        # Stop if got fewer than full page (last page)
        if len(events) < PAGE_SIZE:
            break
        
        # Polite delay between pages
        time.sleep(PAGE_DELAY_SEC)
    
    return all_events, page


# ============================================================
# PARSING
# ============================================================
def parse_response(response_text: str) -> list:
    """Parse JSON-wrapped HTML response → event records."""
    events = []
    
    try:
        data = json.loads(response_text)
        html_data = data.get("data", "")
    except json.JSONDecodeError:
        html_data = response_text
    
    if not html_data:
        return events
    
    soup = BeautifulSoup(html_data, "html.parser")
    rows = soup.find_all("tr", class_="js-event-item")
    
    for row in rows:
        try:
            event = parse_event_row(row)
            if event:
                events.append(event)
        except Exception:
            continue
    
    return events


def parse_event_row(row) -> Optional[dict]:
    """Parse single event row HTML → dict."""
    event_attr_id = row.get("event_attr_id", "")
    event_timestamp = row.get("event_timestamp", "")
    data_event_datetime = row.get("data-event-datetime", "")
    
    # Time
    time_cell = row.find("td", class_="time")
    time_str = time_cell.get_text(strip=True) if time_cell else ""
    
    # Currency
    cur_cell = row.find("td", class_="flagCur")
    currency = ""
    if cur_cell:
        spans = cur_cell.find_all("span")
        for span in spans:
            text = span.get_text(strip=True)
            if text and len(text) == 3 and text.isalpha():
                currency = text
                break
        if not currency:
            text = cur_cell.get_text(strip=True)
            if len(text) <= 5 and text.isalpha():
                currency = text
    
    # Importance
    impact_cell = row.find("td", class_="sentiment")
    impact_stars = 0
    if impact_cell:
        bull_icons = impact_cell.find_all("i", class_=lambda x: x and "FullBullishIcon" in x)
        impact_stars = len(bull_icons)
    
    # Event name
    event_cell = row.find("td", class_="event")
    event_title = ""
    investing_event_id = ""
    if event_cell:
        link = event_cell.find("a")
        if link:
            event_title = link.get_text(strip=True)
            href = link.get("href", "")
            if "-" in href:
                investing_event_id = href.split("-")[-1]
        else:
            event_title = event_cell.get_text(strip=True)
    
    # Values
    act_cell = row.find("td", class_="act")
    actual = act_cell.get_text(strip=True) if act_cell else ""
    if actual in ["", "Â"]:
        actual = ""
    
    fore_cell = row.find("td", class_="fore")
    forecast = fore_cell.get_text(strip=True) if fore_cell else ""
    if forecast == "Â":
        forecast = ""
    
    prev_cell = row.find("td", class_="prev")
    previous = prev_cell.get_text(strip=True) if prev_cell else ""
    if previous == "Â":
        previous = ""
    
    # Release time
    release_time = ""
    if event_timestamp:
        try:
            ts = int(event_timestamp)
            release_time = datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None).isoformat()
        except:
            release_time = data_event_datetime or ""
    elif data_event_datetime:
        release_time = data_event_datetime
    
    if not event_title or not release_time or not currency:
        return None
    
    return {
        "event_title": event_title,
        "currency": currency,
        "release_time": release_time,
        "impact_stars": impact_stars,
        "actual": actual,
        "forecast": forecast,
        "previous": previous,
        "investing_event_id": investing_event_id,
        "event_attr_id": event_attr_id,
        "event_timestamp": event_timestamp,
        "raw_html": str(row)[:2000],
    }


# ============================================================
# DB INSERT
# ============================================================
def insert_events(conn: sqlite3.Connection, events: list) -> dict:
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    
    fetch_date = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    cursor = conn.cursor()
    
    for ev in events:
        try:
            cursor.execute("""
                SELECT raw_id, actual FROM events_investing_raw
                WHERE event_title = ? AND currency = ? AND release_time = ?
            """, (ev["event_title"], ev["currency"], ev["release_time"]))
            
            existing = cursor.fetchone()
            
            if existing is None:
                cursor.execute("""
                    INSERT INTO events_investing_raw (
                        fetch_date, event_title, currency, release_time,
                        impact_stars, forecast, previous, actual,
                        investing_event_id, event_attr_id, event_timestamp,
                        raw_html
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fetch_date, ev["event_title"], ev["currency"], ev["release_time"],
                    ev["impact_stars"], ev["forecast"], ev["previous"], ev["actual"],
                    ev["investing_event_id"], ev["event_attr_id"], ev["event_timestamp"],
                    ev["raw_html"]
                ))
                stats["inserted"] += 1
            else:
                if ev["actual"] and ev["actual"] != (existing[1] or ""):
                    cursor.execute("""
                        UPDATE events_investing_raw
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
    parser = argparse.ArgumentParser(description="Investing.com calendar scraper v2 (paginated)")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS_BACK,
                        help=f"Days back to fetch (default: {DEFAULT_DAYS_BACK})")
    parser.add_argument("--chunk", type=int, default=CHUNK_DAYS,
                        help=f"Days per chunk (default: {CHUNK_DAYS})")
    parser.add_argument("--delay", type=float, default=DELAY_SEC,
                        help=f"Delay between chunks (default: {DELAY_SEC})")
    args = parser.parse_args()
    
    print("=" * 70)
    print("INVESTING.COM HISTORICAL SCRAPER v2 (paginated)")
    print("=" * 70)
    
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=args.days)
    total_chunks = (args.days + args.chunk - 1) // args.chunk
    
    print(f"\nDate range:      {start_date} to {today} ({args.days} days)")
    print(f"Chunk size:      {args.chunk} days")
    print(f"Total chunks:    {total_chunks}")
    print(f"Pagination:      YES (limit_from parameter)")
    print(f"Page delay:      {PAGE_DELAY_SEC}s")
    print(f"Chunk delay:     {args.delay}s")
    print(f"Estimated time:  ~{(total_chunks * 5) // 60}-{(total_chunks * 10) // 60} min")
    
    log.info(f"v2 scraper starting: {args.days}d back, {args.chunk}d chunks, paginated")
    
    conn = sqlite3.connect(fc.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    ensure_investing_table(conn)
    
    scraper = cloudscraper.create_scraper()
    
    total_stats = {
        "chunks_done": 0,
        "chunks_failed": 0,
        "pages_total": 0,
        "events_parsed": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
    }
    
    chunk_start = start_date
    chunk_num = 0
    
    print("\nFetching chunks with pagination...\n")
    
    while chunk_start < today:
        chunk_end = min(chunk_start + timedelta(days=args.chunk - 1), today)
        chunk_num += 1
        
        date_from_str = chunk_start.strftime("%Y-%m-%d")
        date_to_str = chunk_end.strftime("%Y-%m-%d")
        
        print(f"[{chunk_num:3}/{total_chunks}] {date_from_str} -> {date_to_str}  ", end="", flush=True)
        
        events, pages = fetch_chunk_with_pagination(scraper, date_from_str, date_to_str)
        
        if not events:
            print("0 events / failed")
            total_stats["chunks_failed"] += 1
            chunk_start = chunk_end + timedelta(days=1)
            time.sleep(args.delay)
            continue
        
        stats = insert_events(conn, events)
        
        total_stats["chunks_done"] += 1
        total_stats["pages_total"] += pages
        total_stats["events_parsed"] += len(events)
        total_stats["inserted"] += stats["inserted"]
        total_stats["updated"] += stats["updated"]
        total_stats["skipped"] += stats["skipped"]
        
        print(f"{len(events):4} events ({pages}p) | INS:{stats['inserted']:4} UPD:{stats['updated']:3} SKIP:{stats['skipped']:3}")
        
        chunk_start = chunk_end + timedelta(days=1)
        
        if chunk_start < today:
            time.sleep(args.delay)
    
    # Final stats
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events_investing_raw")
    total_in_db = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT impact_stars, COUNT(*) 
        FROM events_investing_raw 
        GROUP BY impact_stars ORDER BY impact_stars DESC
    """)
    by_stars = dict(cursor.fetchall())
    
    cursor.execute("""
        SELECT currency, COUNT(*) 
        FROM events_investing_raw 
        WHERE currency IN ('USD','EUR','GBP','JPY','CNY','CAD','AUD','NZD','CHF')
        GROUP BY currency ORDER BY COUNT(*) DESC
    """)
    by_currency = cursor.fetchall()
    
    cursor.execute("""
        SELECT COUNT(*) FROM events_investing_raw 
        WHERE actual IS NOT NULL AND actual != ''
    """)
    with_actual = cursor.fetchone()[0]
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("v2 SCRAPER SUMMARY")
    print("=" * 70)
    print(f"Chunks done:        {total_stats['chunks_done']}/{total_chunks}")
    print(f"Chunks failed:      {total_stats['chunks_failed']}")
    print(f"Total pages:        {total_stats['pages_total']}")
    print(f"Avg pages/chunk:    {total_stats['pages_total'] / max(total_stats['chunks_done'], 1):.1f}")
    print(f"\nEvents parsed:      {total_stats['events_parsed']}")
    print(f"  Inserted:         {total_stats['inserted']}")
    print(f"  Updated:          {total_stats['updated']}")
    print(f"  Skipped:          {total_stats['skipped']}")
    
    print(f"\nDatabase totals:")
    print(f"  Total events:     {total_in_db}")
    print(f"  With actual:      {with_actual} ({(with_actual/max(total_in_db,1)*100):.1f}%)")
    
    print(f"\nBy impact:")
    for stars in [3, 2, 1, 0]:
        count = by_stars.get(stars, 0)
        label = ["Holiday/Other", "1-star", "2-star", "3-star"][stars]
        print(f"  {label:18}        {count}")
    
    print(f"\nGold-relevant currencies:")
    for curr, count in by_currency:
        print(f"  {curr:10}                {count}")
    
    print("\nDONE.\n")


if __name__ == "__main__":
    main()
