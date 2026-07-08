"""
Fundamental Engine — CSV Importer
==================================
Imports CSV data from investing.com Pro AI exports.

Expected CSV format:
  Timestamp,Country,Currency,Importance,Event,Event (translated),Actual (US),Actual (EU),Forecast,Previous (US),Previous (EU)
  2026-06-05 12:30:00,United States,USD,3,Nonfarm Payrolls,Nonfarm Payrolls,172K,172K,85.000,179K,179K

Features:
  - Auto-detects format
  - Filters empty actuals (FOMC speakers etc)
  - Handles K/M/B/T/% units
  - Skips duplicates (UNIQUE constraint)
  - Stores source filename for traceability
  - After import: shows summary + suggests next steps

Usage:
  python C:\\QGAI\\fundamental_engine\\core\\csv_importer.py path/to/file.csv
  python C:\\QGAI\\fundamental_engine\\core\\csv_importer.py path/to/file.csv --keep-empty
  python C:\\QGAI\\fundamental_engine\\core\\csv_importer.py --analyze   (analyze existing data)
"""

import sys
import os
import csv
import sqlite3
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

# ============================================================
# PATH SETUP
# ============================================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc


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
log = logging.getLogger("csv_importer")


# ============================================================
# DATABASE TABLE
# ============================================================
def ensure_csv_import_table(conn: sqlite3.Connection):
    """Create events_csv_import table for storing CSV-sourced data."""
    schema = """
    CREATE TABLE IF NOT EXISTS events_csv_import (
        raw_id              INTEGER PRIMARY KEY AUTOINCREMENT,
        import_date         TIMESTAMP NOT NULL,
        source_file         TEXT NOT NULL,
        
        -- Event identity
        event_title         TEXT NOT NULL,
        currency            TEXT NOT NULL,
        release_time        TIMESTAMP NOT NULL,
        
        -- Impact
        impact_stars        INTEGER,
        country             TEXT,
        
        -- Values (raw strings as imported)
        actual_str          TEXT,
        forecast_str        TEXT,
        previous_str        TEXT,
        
        -- Parsed numeric values
        actual              TEXT,    -- normalized value as string for compatibility
        forecast            TEXT,
        previous            TEXT,
        
        UNIQUE(event_title, currency, release_time)
    );
    """
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_csv_release ON events_csv_import(release_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_csv_currency ON events_csv_import(currency, impact_stars);",
        "CREATE INDEX IF NOT EXISTS idx_csv_title ON events_csv_import(event_title);",
        "CREATE INDEX IF NOT EXISTS idx_csv_source ON events_csv_import(source_file);",
    ]
    
    cursor = conn.cursor()
    cursor.execute(schema)
    for idx in indexes:
        cursor.execute(idx)
    conn.commit()
    log.info("events_csv_import table verified/created")


# ============================================================
# VALUE NORMALIZATION
# ============================================================
def clean_value(value_str: str) -> str:
    """
    Clean and normalize value strings.
    Handles: "172K" → "172K", "1,795K" → "1795K", "172.5" → "172.5"
    Returns string (preserved format for compatibility with classifier).
    """
    if not value_str:
        return ""
    
    s = str(value_str).strip()
    if not s or s.lower() in ("", "n/a", "null"):
        return ""
    
    # European format: "1,795K" → "1795K" (comma as thousand separator before suffix)
    if "," in s and any(suffix in s.upper() for suffix in ("K", "M", "B", "T")):
        # Replace comma with nothing if it appears to be thousands separator
        # e.g., "1,795K" - the comma is thousands separator
        # vs "0,5%" (European decimal) - comma is decimal point
        parts = s.split(",")
        if len(parts) == 2 and parts[0].isdigit() and len(parts[1]) > 1:
            # Likely thousands separator
            s = parts[0] + parts[1]
    
    return s


# ============================================================
# CSV PARSING
# ============================================================
def parse_csv_file(csv_path: Path, keep_empty: bool = False) -> list:
    """Parse CSV file and return list of event dicts."""
    events = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            # Detect column names (handle variations)
            fieldnames = reader.fieldnames or []
            log.info(f"CSV columns: {fieldnames}")
            
            # Map expected columns
            col_map = {
                "timestamp": next((c for c in fieldnames if c.lower() == "timestamp"), None),
                "country": next((c for c in fieldnames if c.lower() == "country"), None),
                "currency": next((c for c in fieldnames if c.lower() == "currency"), None),
                "importance": next((c for c in fieldnames if c.lower() == "importance"), None),
                "event": next((c for c in fieldnames if c.lower() == "event"), None),
                "actual": next((c for c in fieldnames if "actual" in c.lower() and "us" in c.lower()), None),
                "forecast": next((c for c in fieldnames if c.lower() == "forecast"), None),
                "previous": next((c for c in fieldnames if "previous" in c.lower() and "us" in c.lower()), None),
            }
            
            # Fallback if (US) suffix not present
            if col_map["actual"] is None:
                col_map["actual"] = next((c for c in fieldnames if "actual" in c.lower()), None)
            if col_map["previous"] is None:
                col_map["previous"] = next((c for c in fieldnames if "previous" in c.lower()), None)
            
            log.info(f"Column mapping: {col_map}")
            
            # Check required columns
            required = ["timestamp", "event", "currency"]
            missing = [k for k in required if col_map[k] is None]
            if missing:
                log.error(f"Missing required columns: {missing}")
                return []
            
            # Parse rows
            for row_num, row in enumerate(reader, start=2):
                try:
                    timestamp = row.get(col_map["timestamp"], "").strip()
                    event_title = row.get(col_map["event"], "").strip()
                    currency = row.get(col_map["currency"], "").strip()
                    
                    if not timestamp or not event_title or not currency:
                        continue
                    
                    actual = clean_value(row.get(col_map["actual"], ""))
                    forecast = clean_value(row.get(col_map["forecast"], ""))
                    previous = clean_value(row.get(col_map["previous"], ""))
                    
                    # Skip rows without actuals (FOMC speakers, etc.) unless keep_empty
                    if not actual and not keep_empty:
                        continue
                    
                    # Parse timestamp to ISO format
                    try:
                        if "T" not in timestamp:
                            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                            iso_time = dt.isoformat()
                        else:
                            iso_time = timestamp
                    except ValueError:
                        log.debug(f"Row {row_num}: invalid timestamp: {timestamp}")
                        continue
                    
                    # Importance
                    try:
                        impact_stars = int(row.get(col_map["importance"], "0") or 0)
                    except (ValueError, TypeError):
                        impact_stars = 0
                    
                    country = row.get(col_map["country"], "").strip() if col_map["country"] else ""
                    
                    events.append({
                        "release_time": iso_time,
                        "event_title": event_title,
                        "currency": currency,
                        "country": country,
                        "impact_stars": impact_stars,
                        "actual_str": actual,
                        "forecast_str": forecast,
                        "previous_str": previous,
                        "actual": actual,
                        "forecast": forecast,
                        "previous": previous,
                    })
                
                except Exception as e:
                    log.debug(f"Row {row_num} error: {e}")
                    continue
    
    except Exception as e:
        log.error(f"Failed to read CSV: {e}")
        return []
    
    return events


# ============================================================
# IMPORT
# ============================================================
def import_events(conn: sqlite3.Connection, events: list, source_file: str) -> dict:
    """Insert events into events_csv_import table."""
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
    
    import_date = datetime.now().isoformat()
    cursor = conn.cursor()
    
    for ev in events:
        try:
            cursor.execute("""
                SELECT raw_id, actual FROM events_csv_import
                WHERE event_title = ? AND currency = ? AND release_time = ?
            """, (ev["event_title"], ev["currency"], ev["release_time"]))
            
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
                """, (
                    import_date, source_file,
                    ev["event_title"], ev["currency"], ev["release_time"],
                    ev["impact_stars"], ev["country"],
                    ev["actual_str"], ev["forecast_str"], ev["previous_str"],
                    ev["actual"], ev["forecast"], ev["previous"],
                ))
                stats["inserted"] += 1
            else:
                if ev["actual"] and ev["actual"] != (existing[1] or ""):
                    cursor.execute("""
                        UPDATE events_csv_import
                        SET actual = ?, actual_str = ?, import_date = ?, source_file = ?
                        WHERE raw_id = ?
                    """, (ev["actual"], ev["actual_str"], import_date, source_file, existing[0]))
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
        
        except Exception as e:
            stats["errors"] += 1
            log.debug(f"Insert error: {e}")
    
    conn.commit()
    return stats


# ============================================================
# ANALYSIS
# ============================================================
def analyze_imports(conn: sqlite3.Connection):
    """Analyze imported CSV data."""
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM events_csv_import")
    total = cursor.fetchone()[0]
    
    if total == 0:
        print("\nNo data in events_csv_import table.")
        return
    
    cursor.execute("SELECT MIN(release_time), MAX(release_time) FROM events_csv_import")
    date_range = cursor.fetchone()
    
    cursor.execute("""
        SELECT impact_stars, COUNT(*) 
        FROM events_csv_import 
        GROUP BY impact_stars 
        ORDER BY impact_stars DESC
    """)
    by_impact = dict(cursor.fetchall())
    
    cursor.execute("""
        SELECT currency, COUNT(*) 
        FROM events_csv_import 
        GROUP BY currency 
        ORDER BY COUNT(*) DESC
    """)
    by_currency = cursor.fetchall()
    
    cursor.execute("""
        SELECT source_file, COUNT(*), MIN(release_time), MAX(release_time)
        FROM events_csv_import 
        GROUP BY source_file 
        ORDER BY MIN(release_time)
    """)
    by_source = cursor.fetchall()
    
    cursor.execute("""
        SELECT event_title, COUNT(*) 
        FROM events_csv_import 
        WHERE impact_stars = 3
        GROUP BY event_title 
        ORDER BY COUNT(*) DESC
        LIMIT 15
    """)
    top_3star = cursor.fetchall()
    
    print(f"\n{'=' * 70}")
    print(f"CSV IMPORT ANALYSIS")
    print(f"{'=' * 70}")
    print(f"\nTotal events:        {total}")
    print(f"Date range:")
    print(f"  From: {date_range[0]}")
    print(f"  To:   {date_range[1]}")
    
    print(f"\nBy impact level:")
    for stars in [3, 2, 1, 0]:
        count = by_impact.get(stars, 0)
        print(f"  {stars}-star            {count}")
    
    print(f"\nBy currency:")
    for curr, count in by_currency:
        print(f"  {curr:10}        {count}")
    
    print(f"\nBy source file:")
    for src, count, min_t, max_t in by_source:
        src_short = src[-50:] if len(src) > 50 else src
        print(f"  {src_short}: {count} ({min_t[:10]} to {max_t[:10]})")
    
    print(f"\nTop 3-star events:")
    for title, count in top_3star:
        print(f"  {count:>3}x  {title}")


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_file", nargs='?', help="Path to CSV file to import")
    parser.add_argument("--keep-empty", action="store_true", 
                        help="Keep rows without actual values (FOMC speakers etc)")
    parser.add_argument("--analyze", action="store_true",
                        help="Analyze existing imports without importing new data")
    args = parser.parse_args()
    
    print("=" * 70)
    print("FUNDAMENTAL ENGINE — CSV IMPORTER")
    print("=" * 70)
    print(f"\nDB: {fc.DB_PATH}")
    
    conn = sqlite3.connect(fc.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    ensure_csv_import_table(conn)
    
    if args.analyze or not args.csv_file:
        analyze_imports(conn)
        conn.close()
        return
    
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        log.error(f"CSV file not found: {csv_path}")
        conn.close()
        return
    
    print(f"\nImporting: {csv_path}")
    print(f"Keep empty actuals: {args.keep_empty}")
    
    events = parse_csv_file(csv_path, keep_empty=args.keep_empty)
    print(f"\nParsed {len(events)} valid events")
    
    if not events:
        print("No events to import.")
        conn.close()
        return
    
    stats = import_events(conn, events, source_file=str(csv_path.name))
    
    print(f"\nImport results:")
    print(f"  Inserted:  {stats['inserted']}")
    print(f"  Updated:   {stats['updated']}")
    print(f"  Skipped:   {stats['skipped']}")
    print(f"  Errors:    {stats['errors']}")
    
    # Analysis after import
    analyze_imports(conn)
    
    conn.close()
    print("\nDONE.\n")
    print("NEXT STEPS:")
    print("  1. (Optional) Import more CSV blocks: same command, different files")
    print("  2. Re-run classifier to include new events:")
    print("       python C:\\QGAI\\fundamental_engine\\core\\classifier_v3.py --force")
    print("       (will need updating to read from events_csv_import too)")
    print()


if __name__ == "__main__":
    main()
