"""
Quick date format migration.
Converts release_time from '2024/06/14 10:00:00' → '2024-06-14T10:00:00' (ISO)
in all relevant tables.
"""

import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc

def main():
    print("=" * 60)
    print("DATE FORMAT MIGRATION")
    print("=" * 60)
    print(f"\nDB: {fc.DB_PATH}\n")
    
    conn = sqlite3.connect(fc.DB_PATH)
    cursor = conn.cursor()
    
    # Check which tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_tables = [r[0] for r in cursor.fetchall()]
    
    target_tables = ['events_investing_raw', 'events_classified', 'gold_reactions',
                     'events_forexfactory_raw', 'events_raw']
    
    total_updated = 0
    
    for table in target_tables:
        if table not in all_tables:
            print(f"[SKIP] {table}: table doesn't exist")
            continue
        
        # Check column exists
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cursor.fetchall()]
        if 'release_time' not in cols:
            print(f"[SKIP] {table}: no release_time column")
            continue
        
        # Count rows needing update
        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE release_time LIKE '%/%'")
        needs_update = cursor.fetchone()[0]
        
        if needs_update == 0:
            print(f"[OK]   {table}: already ISO format ({0} updated)")
            continue
        
        # Update
        cursor.execute(f"""
            UPDATE {table}
            SET release_time = REPLACE(REPLACE(release_time, '/', '-'), ' ', 'T')
            WHERE release_time LIKE '%/%'
        """)
        updated = cursor.rowcount
        total_updated += updated
        
        print(f"[OK]   {table}: {updated} rows migrated")
    
    conn.commit()
    
    # Verify
    print(f"\nTotal rows migrated: {total_updated}")
    print("\nVerification — sample dates after migration:")
    
    cursor.execute("""
        SELECT release_time FROM events_classified
        WHERE event_title LIKE '%Michigan%' LIMIT 3
    """)
    samples = [r[0] for r in cursor.fetchall()]
    if samples:
        for s in samples:
            print(f"  {repr(s)}")
    
    conn.close()
    print("\nDONE.\n")


if __name__ == "__main__":
    main()
