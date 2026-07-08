"""
Cleanup: Remove EDT duplicate entries from events_csv_import
=============================================================
Problem: Earlier scraper runs (before timezone fix) stored events
in EDT. After fix, UTC versions added. DB has duplicates.

This script:
  - Finds pairs of same event 4 hours apart
  - Keeps the later (UTC) entry
  - Deletes the earlier (EDT) entry
  - Then triggers reclassification

Usage:
  python cleanup_edt_dupes.py            # Dry run (just shows what would be deleted)
  python cleanup_edt_dupes.py --execute  # Actually delete
"""

import sys
import os
import sqlite3
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc


def find_edt_duplicates(conn):
    """Find events that have an EDT-UTC duplicate pair."""
    cursor = conn.cursor()
    
    # Find pairs where same event_title+currency exist with ~4hr time difference
    cursor.execute("""
        SELECT e1.raw_id as edt_id,
               e1.release_time as edt_time,
               e2.raw_id as utc_id,
               e2.release_time as utc_time,
               e1.event_title,
               e1.currency
        FROM events_csv_import e1
        JOIN events_csv_import e2
            ON e1.event_title = e2.event_title
            AND e1.currency = e2.currency
            AND e2.release_time > e1.release_time
            AND ABS(
                (CAST(strftime('%s', e2.release_time) AS INTEGER) -
                 CAST(strftime('%s', e1.release_time) AS INTEGER)) - 14400
            ) < 600
        ORDER BY e1.release_time
    """)
    
    return cursor.fetchall()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                        help="Actually delete duplicates (default is dry-run)")
    args = parser.parse_args()
    
    print("=" * 70)
    print("EDT DUPLICATE CLEANUP")
    print("=" * 70)
    
    conn = sqlite3.connect(fc.DB_PATH)
    
    # Total before
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events_csv_import")
    total_before = cursor.fetchone()[0]
    print(f"\nTotal events in events_csv_import: {total_before}")
    
    # Find duplicates
    print(f"\nSearching for EDT/UTC duplicates (events 4hr apart)...")
    dupes = find_edt_duplicates(conn)
    
    if not dupes:
        print("[OK] No duplicates found!")
        conn.close()
        return
    
    print(f"\nFound {len(dupes)} duplicate pairs:")
    print(f"  {'EDT Time':22} {'UTC Time':22} {'Currency':10} {'Event'}")
    print(f"  {'-'*22} {'-'*22} {'-'*10} {'-'*40}")
    
    edt_ids_to_delete = []
    for row in dupes[:50]:  # Show first 50
        edt_id, edt_time, utc_id, utc_time, title, currency = row
        title_short = (title or "")[:38]
        print(f"  {edt_time[:19]:22} {utc_time[:19]:22} {currency:10} {title_short}")
        edt_ids_to_delete.append(edt_id)
    
    if len(dupes) > 50:
        print(f"  ... and {len(dupes) - 50} more")
        for row in dupes[50:]:
            edt_ids_to_delete.append(row[0])
    
    print(f"\nTotal EDT entries to delete: {len(edt_ids_to_delete)}")
    
    if not args.execute:
        print("\n[DRY RUN] No changes made.")
        print("Run with --execute to actually delete:")
        print("  python cleanup_edt_dupes.py --execute")
        conn.close()
        return
    
    # Delete
    print(f"\nDeleting {len(edt_ids_to_delete)} EDT entries...")
    placeholders = ','.join('?' * len(edt_ids_to_delete))
    cursor.execute(f"DELETE FROM events_csv_import WHERE raw_id IN ({placeholders})",
                   edt_ids_to_delete)
    deleted = cursor.rowcount
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM events_csv_import")
    total_after = cursor.fetchone()[0]
    
    print(f"\n[OK] Deleted: {deleted}")
    print(f"     Before: {total_before}")
    print(f"     After:  {total_after}")
    
    conn.close()
    
    print(f"\nNEXT STEPS:")
    print(f"  1. Re-classify: python C:\\QGAI\\fundamental_engine\\core\\classifier_v3.py --force")
    print(f"  2. Re-reactions: python C:\\QGAI\\fundamental_engine\\core\\historical_reactions.py --force")
    print(f"  3. Refresh dashboard (auto-refreshes)")


if __name__ == "__main__":
    main()
