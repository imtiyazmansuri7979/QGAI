"""
SQLite Database Initialization
==============================
Purpose: Create the fundamental engine's SQLite database with all tables and indexes.

Location: C:\\QGAI\\data\\fundamental\\gold_engine.db

Tables:
  1. events_raw          - Raw ForexFactory events (all stars, all currencies)
  2. events_classified   - Pattern-classified + enriched events (engine-ready)
  3. gold_reactions      - Historical XAUUSD reactions to events
  4. signal_log          - Engine output audit trail

Safe to re-run: Uses CREATE TABLE IF NOT EXISTS.

Requirements: (sqlite3 is built into Python, no install needed)

Usage:
  python C:\\QGAI\\fundamental_engine\\core\\db_init.py
"""

import sqlite3
import os
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
DB_PATH = r"C:\QGAI\data\fundamental\gold_engine.db"

# Ensure parent directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ============================================================
# SCHEMA DEFINITIONS
# ============================================================

SCHEMA_EVENTS_RAW = """
CREATE TABLE IF NOT EXISTS events_raw (
    raw_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fetch_date      TIMESTAMP NOT NULL,
    event_title     TEXT NOT NULL,
    currency        TEXT NOT NULL,
    impact          TEXT,
    impact_stars    INTEGER,
    release_time    TIMESTAMP NOT NULL,
    forecast        TEXT,
    previous        TEXT,
    actual          TEXT,
    raw_json        TEXT,
    UNIQUE(event_title, currency, release_time)
);
"""

SCHEMA_EVENTS_CLASSIFIED = """
CREATE TABLE IF NOT EXISTS events_classified (
    classified_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id              INTEGER NOT NULL,
    
    -- Identity
    event_title         TEXT NOT NULL,
    currency            TEXT NOT NULL,
    impact_stars        INTEGER NOT NULL,
    release_time        TIMESTAMP NOT NULL,
    
    -- Classification result
    event_type          TEXT,
    matched_pattern     TEXT,
    is_special_handler  INTEGER DEFAULT 0,
    handler_name        TEXT,
    
    -- Direction & weights
    direction_rule      TEXT,
    base_weight         REAL DEFAULT 1.0,
    currency_relevance  REAL DEFAULT 1.0,
    final_weight        REAL DEFAULT 1.0,
    
    -- Parsed values
    actual_value        REAL,
    forecast_value      REAL,
    previous_value      REAL,
    
    -- Computed
    surprise            REAL,
    z_score             REAL,
    z_score_method      TEXT,
    
    -- Metadata
    classified_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (raw_id) REFERENCES events_raw(raw_id)
);
"""

SCHEMA_GOLD_REACTIONS = """
CREATE TABLE IF NOT EXISTS gold_reactions (
    reaction_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    classified_id               INTEGER NOT NULL,
    
    -- Event reference
    event_title                 TEXT NOT NULL,
    currency                    TEXT NOT NULL,
    release_time                TIMESTAMP NOT NULL,
    z_score                     REAL,
    
    -- Gold price snapshots (M15 base)
    xauusd_at_release           REAL,
    xauusd_at_15min             REAL,
    xauusd_at_60min             REAL,
    xauusd_at_4hr               REAL,
    
    -- Computed reactions
    move_15min_pct              REAL,
    move_60min_pct              REAL,
    move_4hr_pct                REAL,
    
    -- Direction tracking
    expected_direction          TEXT,
    observed_direction_15min    TEXT,
    observed_direction_60min    TEXT,
    direction_matched_15min     INTEGER,
    direction_matched_60min     INTEGER,
    
    -- Max adverse excursion (for SL guidance)
    mae_60min_pct               REAL,
    mae_4hr_pct                 REAL,
    
    -- Metadata
    computed_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (classified_id) REFERENCES events_classified(classified_id)
);
"""

SCHEMA_SIGNAL_LOG = """
CREATE TABLE IF NOT EXISTS signal_log (
    signal_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp           TIMESTAMP NOT NULL,
    engine_mode         TEXT,
    
    -- Technical context input
    has_position        INTEGER,
    position_direction  TEXT,
    pending_entry       INTEGER,
    pending_direction   TEXT,
    
    -- Event context
    event_title         TEXT,
    currency            TEXT,
    event_tier          INTEGER,
    
    -- Engine output
    action              TEXT NOT NULL,
    urgency             TEXT,
    confidence          REAL,
    grade               TEXT,
    fundamental_view    TEXT,
    observed_direction  TEXT,
    alignment           TEXT,
    
    -- Metadata
    z_score             REAL,
    hit_rate            REAL,
    sample_size         INTEGER,
    reasoning           TEXT,
    
    logged_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ============================================================
# INDEX DEFINITIONS
# ============================================================

INDEXES = [
    # events_raw indexes
    "CREATE INDEX IF NOT EXISTS idx_raw_release_time ON events_raw(release_time);",
    "CREATE INDEX IF NOT EXISTS idx_raw_curr_impact ON events_raw(currency, impact_stars);",
    "CREATE INDEX IF NOT EXISTS idx_raw_title ON events_raw(event_title);",
    
    # events_classified indexes
    "CREATE INDEX IF NOT EXISTS idx_class_release ON events_classified(release_time DESC);",
    "CREATE INDEX IF NOT EXISTS idx_class_title_z ON events_classified(event_title, z_score);",
    "CREATE INDEX IF NOT EXISTS idx_class_currency ON events_classified(currency, impact_stars);",
    "CREATE INDEX IF NOT EXISTS idx_class_type ON events_classified(event_type);",
    "CREATE INDEX IF NOT EXISTS idx_class_raw ON events_classified(raw_id);",
    
    # gold_reactions indexes (CRITICAL for hit rate lookup)
    "CREATE INDEX IF NOT EXISTS idx_reaction_title_z ON gold_reactions(event_title, z_score);",
    "CREATE INDEX IF NOT EXISTS idx_reaction_time ON gold_reactions(release_time DESC);",
    "CREATE INDEX IF NOT EXISTS idx_reaction_classified ON gold_reactions(classified_id);",
    
    # signal_log indexes
    "CREATE INDEX IF NOT EXISTS idx_signal_time ON signal_log(timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS idx_signal_action ON signal_log(action);",
    "CREATE INDEX IF NOT EXISTS idx_signal_event ON signal_log(event_title);",
]

# ============================================================
# INITIALIZATION
# ============================================================

def init_database():
    print("=" * 60)
    print("SQLITE DATABASE INITIALIZATION")
    print("=" * 60)
    print(f"\nTarget: {DB_PATH}")
    
    # Check if database already exists
    db_exists = os.path.exists(DB_PATH)
    if db_exists:
        size_mb = os.path.getsize(DB_PATH) / 1024 / 1024
        print(f"OK Database exists (size: {size_mb:.2f} MB)")
    else:
        print("New database will be created")
    
    # Connect (creates file if not exists)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")     # Enable FK constraints
    conn.execute("PRAGMA journal_mode = WAL;")    # Better concurrency
    cursor = conn.cursor()
    
    # Create tables
    print("\nCreating tables...")
    tables = {
        'events_raw': SCHEMA_EVENTS_RAW,
        'events_classified': SCHEMA_EVENTS_CLASSIFIED,
        'gold_reactions': SCHEMA_GOLD_REACTIONS,
        'signal_log': SCHEMA_SIGNAL_LOG
    }
    
    for table_name, schema in tables.items():
        cursor.execute(schema)
        print(f"   OK {table_name}")
    
    # Create indexes
    print("\nCreating indexes...")
    for idx_sql in INDEXES:
        cursor.execute(idx_sql)
    print(f"   OK {len(INDEXES)} indexes created")
    
    # Commit
    conn.commit()
    
    # Verify
    print("\nVerifying schema...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables_found = [row[0] for row in cursor.fetchall()]
    
    print(f"   Tables in database: {tables_found}")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    indexes_found = [row[0] for row in cursor.fetchall()]
    
    print(f"   Indexes count: {len(indexes_found)}")
    
    # Stats
    print("\nTable row counts:")
    for table in tables_found:
        if not table.startswith('sqlite_'):
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            count = cursor.fetchone()[0]
            print(f"   {table:30} {count:>10} rows")
    
    # Database file info
    final_size_mb = os.path.getsize(DB_PATH) / 1024 / 1024
    
    print("\n" + "=" * 60)
    print("INITIALIZATION SUMMARY")
    print("=" * 60)
    print(f"Database path:   {DB_PATH}")
    print(f"Database size:   {final_size_mb:.2f} MB")
    print(f"Tables created:  {len([t for t in tables_found if not t.startswith('sqlite_')])}")
    print(f"Indexes created: {len(indexes_found)}")
    print(f"Status:          {'EXISTING (verified)' if db_exists else 'NEW (initialized)'}")
    
    conn.close()
    print("\nDONE. Database ready for fundamental engine.\n")


if __name__ == "__main__":
    init_database()
