"""
Events Raw Inspector
=====================
Utility to review raw events stored in events_raw table.
Outputs:
  - Console: grouped breakdown
  - CSV: all events for offline review
  - JSON: events grouped by impact + currency

Usage:
  python C:\\QGAI\\fundamental_engine\\core\\events_inspector.py

Or with filters:
  python C:\\QGAI\\fundamental_engine\\core\\events_inspector.py --stars 3
  python C:\\QGAI\\fundamental_engine\\core\\events_inspector.py --currency USD
"""

import sys
import os
import sqlite3
import json
import argparse
from pathlib import Path
from datetime import datetime

# ============================================================
# PATH SETUP
# ============================================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc

# ============================================================
# OUTPUT PATHS
# ============================================================
CSV_OUTPUT = os.path.join(fc.AUDIT_OUTPUT_DIR, "events_raw_review.csv")
JSON_OUTPUT = os.path.join(fc.AUDIT_OUTPUT_DIR, "events_raw_review.json")

os.makedirs(fc.AUDIT_OUTPUT_DIR, exist_ok=True)


# ============================================================
# QUERY FUNCTIONS
# ============================================================
def query_events(conn, min_stars=0, currency_filter=None):
    """Query events with optional filters."""
    sql = """
        SELECT 
            raw_id, event_title, currency, impact, impact_stars,
            release_time, forecast, previous, actual
        FROM events_raw
        WHERE impact_stars >= ?
    """
    params = [min_stars]
    
    if currency_filter:
        sql += " AND currency = ?"
        params.append(currency_filter)
    
    sql += " ORDER BY impact_stars DESC, currency, release_time"
    
    cursor = conn.cursor()
    cursor.execute(sql, params)
    
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    
    return columns, rows


def get_summary_stats(conn):
    """Get summary statistics from events_raw."""
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM events_raw")
    total = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT impact_stars, COUNT(*) 
        FROM events_raw 
        GROUP BY impact_stars 
        ORDER BY impact_stars DESC
    """)
    by_stars = dict(cursor.fetchall())
    
    cursor.execute("""
        SELECT currency, COUNT(*) 
        FROM events_raw 
        GROUP BY currency 
        ORDER BY COUNT(*) DESC
    """)
    by_currency = dict(cursor.fetchall())
    
    cursor.execute("""
        SELECT MIN(release_time), MAX(release_time) 
        FROM events_raw
    """)
    date_range = cursor.fetchone()
    
    # Events with actual values released
    cursor.execute("""
        SELECT COUNT(*) FROM events_raw 
        WHERE actual IS NOT NULL AND actual != ''
    """)
    with_actual = cursor.fetchone()[0]
    
    # Events with forecasts
    cursor.execute("""
        SELECT COUNT(*) FROM events_raw 
        WHERE forecast IS NOT NULL AND forecast != ''
    """)
    with_forecast = cursor.fetchone()[0]
    
    return {
        "total": total,
        "by_stars": by_stars,
        "by_currency": by_currency,
        "date_range": date_range,
        "with_actual": with_actual,
        "with_forecast": with_forecast,
    }


def get_unique_event_names(conn, min_stars=0):
    """Get unique event titles grouped by currency + impact."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT event_title, currency, impact_stars
        FROM events_raw
        WHERE impact_stars >= ?
        ORDER BY impact_stars DESC, currency, event_title
    """, (min_stars,))
    return cursor.fetchall()


# ============================================================
# OUTPUT FUNCTIONS
# ============================================================
def write_csv(columns, rows, filepath):
    """Write events to CSV file."""
    import csv
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)


def write_json_grouped(conn, filepath):
    """Write events grouped by impact + currency to JSON."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT event_title, currency, impact, impact_stars, 
               release_time, forecast, previous, actual
        FROM events_raw
        ORDER BY impact_stars DESC, currency, release_time
    """)
    
    grouped = {}
    for row in cursor.fetchall():
        title, curr, impact, stars, time, forecast, prev, actual = row
        
        key = f"{stars}-star"
        if key not in grouped:
            grouped[key] = {}
        if curr not in grouped[key]:
            grouped[key][curr] = []
        
        grouped[key][curr].append({
            "event": title,
            "release_time": time,
            "forecast": forecast,
            "previous": prev,
            "actual": actual,
        })
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({
            "review_date": datetime.now().isoformat(),
            "events_by_impact_and_currency": grouped
        }, f, indent=2, ensure_ascii=False)


def print_summary(stats):
    """Print summary to console."""
    print("=" * 70)
    print("EVENTS_RAW REVIEW SUMMARY")
    print("=" * 70)
    
    print(f"\nTotal events in DB:        {stats['total']}")
    print(f"With forecast value:        {stats['with_forecast']}")
    print(f"With actual value released: {stats['with_actual']}")
    
    if stats['date_range'][0]:
        print(f"\nDate range:")
        print(f"  From: {stats['date_range'][0]}")
        print(f"  To:   {stats['date_range'][1]}")
    
    print(f"\nBy impact level:")
    for stars in [3, 2, 1, 0]:
        count = stats['by_stars'].get(stars, 0)
        label = ["Holiday/Other", "1-star", "2-star", "3-star"][stars]
        print(f"  {label:18}        {count}")
    
    print(f"\nBy currency:")
    for curr, count in stats['by_currency'].items():
        print(f"  {curr:10}                {count}")


def print_events_by_impact(conn):
    """Print events grouped by impact level (most useful view)."""
    
    for stars in [3, 2, 1, 0]:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT event_title, currency, release_time, forecast, previous, actual
            FROM events_raw 
            WHERE impact_stars = ?
            ORDER BY currency, release_time
        """, (stars,))
        rows = cursor.fetchall()
        
        if not rows:
            continue
        
        label = ["HOLIDAY / NON-ECONOMIC", "1-STAR (LOW)", "2-STAR (MEDIUM)", "3-STAR (HIGH)"][stars]
        print(f"\n{'=' * 70}")
        print(f"  {label}  ({len(rows)} events)")
        print(f"{'=' * 70}")
        
        current_currency = None
        for row in rows:
            title, curr, rtime, forecast, prev, actual = row
            
            if curr != current_currency:
                print(f"\n  [{curr}]")
                current_currency = curr
            
            # Format release time
            try:
                dt = datetime.fromisoformat(rtime.replace("Z", "+00:00"))
                time_str = dt.strftime("%m-%d %H:%M")
            except:
                time_str = rtime[:16] if rtime else "?"
            
            # Format values
            fcst = f"F:{forecast}" if forecast else ""
            prv = f"P:{prev}" if prev else ""
            act = f"A:{actual}" if actual else ""
            details = " ".join([x for x in [fcst, prv, act] if x])
            
            print(f"    {time_str}  {title:<45} {details}")


def print_unique_events_summary(conn):
    """Print summary of unique event names that engine will encounter."""
    print(f"\n{'=' * 70}")
    print("UNIQUE EVENTS (for classifier reference)")
    print(f"{'=' * 70}")
    
    for stars in [3, 2]:
        rows = get_unique_event_names(conn, stars)
        rows = [r for r in rows if r[2] == stars]
        
        if not rows:
            continue
        
        label = ["", "1-star", "2-star", "3-star"][stars]
        print(f"\n--- {label} unique events ---")
        
        current_currency = None
        for title, curr, _ in rows:
            if curr != current_currency:
                print(f"\n  [{curr}]")
                current_currency = curr
            print(f"    - {title}")


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Review events_raw table")
    parser.add_argument("--stars", type=int, default=0, 
                        help="Minimum impact stars (0-3)")
    parser.add_argument("--currency", type=str, default=None,
                        help="Filter by currency (e.g., USD)")
    parser.add_argument("--csv", action="store_true",
                        help="Generate CSV output")
    parser.add_argument("--json", action="store_true",
                        help="Generate JSON output")
    parser.add_argument("--full", action="store_true",
                        help="Print all events (default: summary only)")
    args = parser.parse_args()
    
    print("Opening database:", fc.DB_PATH)
    
    conn = sqlite3.connect(fc.DB_PATH)
    
    # Always print summary
    stats = get_summary_stats(conn)
    print_summary(stats)
    
    # Print all events grouped by impact (default behavior)
    print_events_by_impact(conn)
    
    # Print unique events for classifier reference
    print_unique_events_summary(conn)
    
    # CSV output
    if args.csv or args.full:
        columns, rows = query_events(conn, args.stars, args.currency)
        write_csv(columns, rows, CSV_OUTPUT)
        print(f"\nCSV output: {CSV_OUTPUT}")
    
    # JSON output
    if args.json or args.full:
        write_json_grouped(conn, JSON_OUTPUT)
        print(f"JSON output: {JSON_OUTPUT}")
    
    conn.close()
    print("\nDONE.\n")


if __name__ == "__main__":
    main()
