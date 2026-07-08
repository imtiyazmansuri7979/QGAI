"""
ForexFactory News Fetcher
==========================
Fetches current week's economic events from ForexFactory and inserts
into events_raw table. Wide ingestion - ALL stars (0/1/2/3).

Module: fundamental_engine.core.news_fetcher

Usage:
  Manual run:
    python C:\\QGAI\\fundamental_engine\\core\\news_fetcher.py

  As library:
    from core.news_fetcher import fetch_and_store
    result = fetch_and_store()

Returns dict with insert/update counts and currency breakdown.

Design:
  - Inserts new events (deduplicated via UNIQUE constraint)
  - Updates existing rows when 'actual' value released
  - Logs operations
  - Safe to run multiple times (idempotent)
"""

import sys
import os
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests

# ============================================================
# PATH SETUP — allow config imports
# ============================================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc

# ============================================================
# LOGGING SETUP
# ============================================================
os.makedirs(os.path.dirname(fc.LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=getattr(logging, fc.LOG_LEVEL),
    format=fc.LOG_FORMAT,
    handlers=[
        logging.FileHandler(fc.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("news_fetcher")


# ============================================================
# IMPACT STRING TO STAR LEVEL MAPPING
# ============================================================
IMPACT_TO_STARS = {
    "High":          3,
    "Medium":        2,
    "Low":           1,
    "Non-Economic":  0,
    "Holiday":       0,
    "":              0,
}


def impact_to_stars(impact_str: str) -> int:
    """Convert ForexFactory impact string to star level (0-3)."""
    if impact_str is None:
        return 0
    return IMPACT_TO_STARS.get(impact_str.strip(), 0)


# ============================================================
# VALUE PARSING (forecast / actual / previous)
# ============================================================
def parse_value(value_str: Optional[str]) -> Optional[float]:
    """
    Parse FF value strings into float.
    Handles units: K (thousand), M (million), B (billion), %, etc.
    
    Examples:
        "180K"   -> 180000.0
        "2.5M"   -> 2500000.0
        "3.2%"   -> 3.2
        ""       -> None
        "N/A"    -> None
    """
    if value_str is None or value_str == "" or value_str == "N/A":
        return None
    
    try:
        # Strip whitespace
        s = str(value_str).strip()
        
        # Handle negative
        is_negative = s.startswith("-")
        if is_negative:
            s = s[1:]
        
        # Remove common units
        multiplier = 1.0
        if s.endswith("K") or s.endswith("k"):
            multiplier = 1_000
            s = s[:-1]
        elif s.endswith("M") or s.endswith("m"):
            multiplier = 1_000_000
            s = s[:-1]
        elif s.endswith("B") or s.endswith("b"):
            multiplier = 1_000_000_000
            s = s[:-1]
        elif s.endswith("T") or s.endswith("t"):
            multiplier = 1_000_000_000_000
            s = s[:-1]
        
        # Remove percentage sign
        s = s.replace("%", "").strip()
        
        # Remove commas (thousand separators)
        s = s.replace(",", "")
        
        # Parse
        result = float(s) * multiplier
        
        return -result if is_negative else result
        
    except (ValueError, AttributeError):
        return None


# ============================================================
# FOREXFACTORY FETCH
# ============================================================
def fetch_forex_factory() -> list:
    """
    Fetch ForexFactory current week JSON feed.
    
    Returns:
        list of event dicts, or empty list on error.
    """
    log.info(f"Fetching ForexFactory: {fc.FF_CALENDAR_URL}")
    
    headers = {"User-Agent": fc.HTTP_USER_AGENT}
    
    try:
        response = requests.get(
            fc.FF_CALENDAR_URL,
            headers=headers,
            timeout=fc.HTTP_TIMEOUT_SEC
        )
        response.raise_for_status()
        data = response.json()
        log.info(f"Fetched {len(data)} events")
        return data
    
    except requests.exceptions.Timeout:
        log.error("ForexFactory request timeout")
        return []
    except requests.exceptions.RequestException as e:
        log.error(f"ForexFactory request error: {e}")
        return []
    except json.JSONDecodeError as e:
        log.error(f"ForexFactory JSON parse error: {e}")
        return []


# ============================================================
# DATABASE OPERATIONS
# ============================================================
def insert_or_update_event(conn: sqlite3.Connection, event: dict) -> str:
    """
    Insert new event or update existing one (when actual value released).
    
    Returns:
        'inserted', 'updated', or 'skipped'
    """
    cursor = conn.cursor()
    
    event_title = event.get("title", "")
    currency = event.get("country", "")
    release_time = event.get("date", "")
    impact_str = event.get("impact", "")
    forecast = event.get("forecast", "")
    previous = event.get("previous", "")
    actual = event.get("actual", "")
    
    if not event_title or not release_time:
        return "skipped"
    
    stars = impact_to_stars(impact_str)
    fetch_date = datetime.utcnow().isoformat()
    raw_json = json.dumps(event, ensure_ascii=False)
    
    # Check if event exists
    cursor.execute("""
        SELECT raw_id, actual 
        FROM events_raw 
        WHERE event_title = ? AND currency = ? AND release_time = ?
    """, (event_title, currency, release_time))
    
    existing = cursor.fetchone()
    
    if existing is None:
        # INSERT new event
        cursor.execute("""
            INSERT INTO events_raw (
                fetch_date, event_title, currency, impact, impact_stars,
                release_time, forecast, previous, actual, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fetch_date, event_title, currency, impact_str, stars,
            release_time, forecast, previous, actual, raw_json
        ))
        return "inserted"
    else:
        existing_actual = existing[1] or ""
        # Update only if actual changed (typically empty -> released value)
        if actual and actual != existing_actual:
            cursor.execute("""
                UPDATE events_raw 
                SET actual = ?, raw_json = ?, fetch_date = ?
                WHERE raw_id = ?
            """, (actual, raw_json, fetch_date, existing[0]))
            return "updated"
        else:
            return "skipped"


# ============================================================
# MAIN PIPELINE
# ============================================================
def fetch_and_store() -> dict:
    """
    Main pipeline: fetch FF data → store in events_raw.
    
    Returns:
        Stats dict with counts and breakdown.
    """
    stats = {
        "fetched": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
        "by_currency": {},
        "by_impact_stars": {0: 0, 1: 0, 2: 0, 3: 0},
        "total_in_db": 0,
        "fetch_timestamp": datetime.utcnow().isoformat(),
    }
    
    # 1. Fetch FF data
    events = fetch_forex_factory()
    stats["fetched"] = len(events)
    
    if not events:
        log.warning("No events fetched, exiting")
        return stats
    
    # 2. Connect to DB
    try:
        conn = sqlite3.connect(fc.DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
    except sqlite3.Error as e:
        log.error(f"Database connection failed: {e}")
        return stats
    
    # 3. Process each event
    log.info("Processing events...")
    
    for idx, event in enumerate(events):
        try:
            result = insert_or_update_event(conn, event)
            stats[result] += 1
            
            # Track by currency (new inserts only)
            if result == "inserted":
                currency = event.get("country", "Unknown")
                stats["by_currency"][currency] = stats["by_currency"].get(currency, 0) + 1
                
                # Track by impact
                stars = impact_to_stars(event.get("impact", ""))
                stats["by_impact_stars"][stars] += 1
        
        except Exception as e:
            log.error(f"Error processing event {idx}: {e}")
            stats["errors"] += 1
    
    # 4. Commit
    conn.commit()
    
    # 5. Total count
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events_raw")
    stats["total_in_db"] = cursor.fetchone()[0]
    
    conn.close()
    
    return stats


# ============================================================
# CLI SUMMARY OUTPUT
# ============================================================
def print_summary(stats: dict):
    """Pretty-print stats to console."""
    print("=" * 60)
    print(f"NEWS FETCHER SUMMARY")
    print(f"Run timestamp (UTC): {stats['fetch_timestamp']}")
    print("=" * 60)
    print(f"\nForexFactory:")
    print(f"  Events fetched:           {stats['fetched']}")
    
    print(f"\nDatabase operations:")
    print(f"  New inserts:              {stats['inserted']}")
    print(f"  Updates (actual changed): {stats['updated']}")
    print(f"  Skipped (no change):      {stats['skipped']}")
    print(f"  Errors:                   {stats['errors']}")
    
    if stats["inserted"] > 0:
        print(f"\nNew events by impact:")
        for stars, count in sorted(stats["by_impact_stars"].items()):
            label = ["Holiday/Other", "1-star", "2-star", "3-star"][stars]
            print(f"  {label:18}        {count}")
        
        print(f"\nNew events by currency:")
        for curr, count in sorted(stats["by_currency"].items(), key=lambda x: -x[1]):
            print(f"  {curr:10}                {count}")
    
    print(f"\nTotal rows in events_raw:    {stats['total_in_db']}")
    print("\nDONE.\n")


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    try:
        stats = fetch_and_store()
        print_summary(stats)
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        print(f"\nFATAL ERROR: {e}")
        sys.exit(1)
