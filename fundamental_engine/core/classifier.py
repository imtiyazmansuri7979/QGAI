"""
Fundamental Engine — Classifier Module
=======================================
Categorizes raw events into 8 event types, calculates surprise + Z-score,
determines fundamental direction (BULLISH_GOLD / BEARISH_GOLD / NEUTRAL).

This is the FOUNDATION module — everything else depends on classified events.

Pipeline:
  events_investing_raw (raw events w/ actuals)
      ↓
  Pattern matching (event_classification.EVENT_TYPE_PATTERNS)
      ↓
  Numeric value extraction (handle %, K, M, B suffixes)
      ↓
  Surprise = actual - forecast
      ↓
  Z-score (rolling 20-event history per event_type+currency)
      ↓
  Tier classification (1/2/3 based on |Z|)
      ↓
  Fundamental direction (with currency direction flip)
      ↓
  events_classified table

Usage:
  python C:\\QGAI\\fundamental_engine\\core\\classifier.py
  
  # Process only specific source
  python C:\\QGAI\\fundamental_engine\\core\\classifier.py --source investing
  
  # Re-classify (overwrites existing)
  python C:\\QGAI\\fundamental_engine\\core\\classifier.py --force

Module: fundamental_engine.core.classifier
"""

import sys
import os
import re
import sqlite3
import argparse
import logging
import statistics
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict

# ============================================================
# PATH SETUP
# ============================================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc
from config import thresholds as th
from config import event_classification as ec


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
log = logging.getLogger("classifier")


# ============================================================
# DATABASE SCHEMA
# ============================================================
def ensure_classified_table(conn: sqlite3.Connection):
    """Create events_classified table if not exists."""
    schema = """
    CREATE TABLE IF NOT EXISTS events_classified (
        classified_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        
        -- Source reference
        raw_id_source       INTEGER NOT NULL,
        source_table        TEXT NOT NULL,
        
        -- Event identity
        event_type          TEXT NOT NULL,
        event_title         TEXT NOT NULL,
        currency            TEXT NOT NULL,
        release_time        TIMESTAMP NOT NULL,
        impact_stars        INTEGER,
        
        -- Parsed values
        forecast_value      REAL,
        previous_value      REAL,
        actual_value        REAL,
        
        -- Calculated signals
        surprise_value      REAL,
        z_score             REAL,
        tier                INTEGER,   -- 1, 2, 3 (3=highest impact)
        
        -- Direction
        fundamental_direction TEXT,    -- BULLISH_GOLD, BEARISH_GOLD, NEUTRAL
        direction_confidence  REAL,    -- 0.0 to 1.0
        
        -- Meta
        currency_weight     REAL,
        event_weight        REAL,
        classification_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        UNIQUE(raw_id_source, source_table)
    );
    """
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_cl_release ON events_classified(release_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_cl_type_curr ON events_classified(event_type, currency);",
        "CREATE INDEX IF NOT EXISTS idx_cl_tier ON events_classified(tier DESC);",
        "CREATE INDEX IF NOT EXISTS idx_cl_direction ON events_classified(fundamental_direction);",
        "CREATE INDEX IF NOT EXISTS idx_cl_zscore ON events_classified(z_score);",
    ]
    
    cursor = conn.cursor()
    cursor.execute(schema)
    for idx in indexes:
        cursor.execute(idx)
    conn.commit()
    log.info("events_classified table verified/created")


# ============================================================
# NUMERIC VALUE EXTRACTION
# ============================================================
def extract_numeric_value(value_str: str) -> Optional[float]:
    """
    Parse numeric value from strings like:
      "0.3%"     → 0.3
      "172K"     → 172000
      "1.2M"     → 1200000
      "$50B"     → 50000000000
      "-2.5"     → -2.5
      "2.25%"    → 2.25
      "4.21T"    → 4210000000000
    Returns None if unparseable.
    """
    if not value_str:
        return None
    
    s = str(value_str).strip()
    if not s:
        return None
    
    # Remove currency symbols and formatting
    s = s.replace("$", "").replace("€", "").replace("£", "").replace("¥", "")
    s = s.replace(",", "").replace(" ", "")
    
    # Detect multiplier suffix
    multiplier = 1.0
    suffix_map = {
        "K": 1_000,
        "M": 1_000_000,
        "B": 1_000_000_000,
        "T": 1_000_000_000_000,
    }
    
    # Handle percentage
    if s.endswith("%"):
        s = s[:-1]
    
    # Handle multiplier suffix
    if s and s[-1].upper() in suffix_map:
        multiplier = suffix_map[s[-1].upper()]
        s = s[:-1]
    
    # Try parse
    try:
        return float(s) * multiplier
    except (ValueError, TypeError):
        return None


# ============================================================
# EVENT TYPE CLASSIFICATION
# ============================================================
def classify_event_type(event_title: str) -> Optional[tuple]:
    """
    Pattern-match event title against EVENT_TYPE_PATTERNS.
    Returns (event_type, type_config) or None if no match.
    """
    if not event_title:
        return None
    
    title_lower = event_title.lower()
    
    best_match = None
    best_priority = -1
    
    for event_type, config in ec.EVENT_TYPE_PATTERNS.items():
        patterns = config.get("patterns", [])
        priority = config.get("priority", 0)
        
        for pattern in patterns:
            if pattern.lower() in title_lower:
                if priority > best_priority:
                    best_match = (event_type, config)
                    best_priority = priority
                break
    
    return best_match


def check_event_override(event_title: str, currency: str) -> Optional[dict]:
    """Check if event matches override rules (OPEC, Holidays, etc.)"""
    title_lower = event_title.lower()
    
    overrides = getattr(ec, "EVENT_OVERRIDES", {})
    for override_name, override_config in overrides.items():
        patterns = override_config.get("patterns", [])
        for pattern in patterns:
            if pattern.lower() in title_lower:
                return override_config
    
    return None


# ============================================================
# Z-SCORE & TIER
# ============================================================
def calculate_z_score(current_surprise: float, history: list) -> Optional[float]:
    """
    Calculate Z-score using rolling history.
    Returns None if insufficient history (<3 samples).
    """
    if not history or len(history) < 3:
        return None
    
    try:
        mean = statistics.mean(history)
        std = statistics.stdev(history)
        if std == 0:
            return 0.0  # All historical surprises were identical
        return (current_surprise - mean) / std
    except statistics.StatisticsError:
        return None


def classify_tier(z_score: Optional[float]) -> int:
    """
    Tier classification based on |Z-score|.
    Tier 3 = highest impact (|Z| >= 1.0)
    Tier 2 = medium (|Z| >= 1.8)  -- corrected from spec
    Tier 1 = highest threshold (|Z| >= 2.5)
    
    Note: From spec, lower thresholds = higher tier (more events qualify)
    """
    if z_score is None:
        return 0  # Unranked
    
    abs_z = abs(z_score)
    thresholds = getattr(th, "Z_THRESHOLDS", {3: 1.0, 2: 1.8, 1: 2.5})
    
    if abs_z >= thresholds.get(1, 2.5):
        return 1   # Outlier - highest tier
    elif abs_z >= thresholds.get(2, 1.8):
        return 2
    elif abs_z >= thresholds.get(3, 1.0):
        return 3
    else:
        return 0  # Below threshold


# ============================================================
# FUNDAMENTAL DIRECTION
# ============================================================
def determine_fundamental_direction(
    event_type: str,
    type_config: dict,
    currency: str,
    surprise: float,
    z_score: Optional[float],
) -> tuple:
    """
    Determine fundamental view direction.
    
    Returns (direction, confidence):
      direction: BULLISH_GOLD / BEARISH_GOLD / NEUTRAL
      confidence: 0.0 to 1.0
    
    Logic:
      direction_rule = "higher_is_hawkish" → high actual surprises currency hawkish
      direction_rule = "higher_is_dovish" → high actual surprises currency dovish (e.g., unemployment)
      
      For USD:    Hawkish → BEARISH_GOLD;  Dovish → BULLISH_GOLD
      For non-USD: Hawkish foreign → relatively dovish USD → BULLISH_GOLD
                   Dovish foreign → relatively hawkish USD → BEARISH_GOLD
    """
    direction_rule = type_config.get("direction_rule", "neutral")
    
    if direction_rule == "neutral":
        return "NEUTRAL", 0.0
    
    # Determine base currency view (hawkish vs dovish for THIS currency)
    if direction_rule == "higher_is_hawkish":
        currency_view = "HAWKISH" if surprise > 0 else "DOVISH"
    elif direction_rule == "higher_is_dovish":
        currency_view = "DOVISH" if surprise > 0 else "HAWKISH"
    else:
        return "NEUTRAL", 0.0
    
    # Map to Gold direction
    if currency == "USD":
        if currency_view == "HAWKISH":
            gold_direction = "BEARISH_GOLD"
        else:
            gold_direction = "BULLISH_GOLD"
    else:
        # Non-USD currency — relative effect on USD
        if currency_view == "HAWKISH":
            gold_direction = "BULLISH_GOLD"  # Foreign strong = USD weak relatively
        else:
            gold_direction = "BEARISH_GOLD"  # Foreign weak = USD strong relatively
    
    # Confidence based on Z-score magnitude
    if z_score is None:
        confidence = 0.3  # No history baseline
    else:
        abs_z = abs(z_score)
        if abs_z >= 2.5:
            confidence = 0.95
        elif abs_z >= 1.8:
            confidence = 0.80
        elif abs_z >= 1.0:
            confidence = 0.60
        elif abs_z >= 0.5:
            confidence = 0.40
        else:
            confidence = 0.20
    
    return gold_direction, confidence


# ============================================================
# CURRENCY WEIGHTING
# ============================================================
def get_currency_weight(currency: str) -> float:
    """Get currency relevance weight (0.0-1.0) from config."""
    relevance = getattr(ec, "CURRENCY_RELEVANCE", {})
    return relevance.get(currency, 0.1)  # Default low for unknown


# ============================================================
# MAIN CLASSIFIER PIPELINE
# ============================================================
def run_classifier(conn: sqlite3.Connection, source_filter: str = "all", force: bool = False) -> dict:
    """
    Run classification on raw events.
    
    Args:
        conn: SQLite connection
        source_filter: 'all', 'investing', 'forexfactory'
        force: If True, reclassify even already-classified events
    
    Returns:
        Statistics dict
    """
    cursor = conn.cursor()
    
    # Tables to process
    sources = []
    if source_filter in ("all", "investing"):
        sources.append(("events_investing_raw", "events_investing_raw"))
    if source_filter in ("all", "forexfactory"):
        # Check if FF table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events_forexfactory_raw'")
        if cursor.fetchone():
            sources.append(("events_forexfactory_raw", "events_forexfactory_raw"))
    
    # Surprise history for Z-score (key = event_type + currency)
    surprise_history = defaultdict(list)
    
    stats = {
        "total_input": 0,
        "classified": 0,
        "unclassified": 0,
        "no_actual": 0,
        "no_surprise": 0,
        "inserted": 0,
        "errors": 0,
        "by_type": defaultdict(int),
        "by_currency": defaultdict(int),
        "by_tier": defaultdict(int),
        "by_direction": defaultdict(int),
    }
    
    for source_table, source_label in sources:
        log.info(f"Processing source: {source_table}")
        
        # Fetch events sorted by release_time (so Z-score history builds correctly)
        cursor.execute(f"""
            SELECT raw_id, event_title, currency, release_time, impact_stars,
                   forecast, previous, actual
            FROM {source_table}
            WHERE actual IS NOT NULL AND actual != ''
            ORDER BY release_time ASC
        """)
        
        events = cursor.fetchall()
        log.info(f"  Found {len(events)} events with actuals")
        stats["total_input"] += len(events)
        
        for ev in events:
            raw_id, title, currency, release_time, impact_stars, forecast_s, previous_s, actual_s = ev
            
            try:
                # Step 1: Classify event type
                match = classify_event_type(title)
                if not match:
                    stats["unclassified"] += 1
                    continue
                event_type, type_config = match
                
                # Step 2: Parse numeric values
                actual = extract_numeric_value(actual_s)
                forecast = extract_numeric_value(forecast_s)
                previous = extract_numeric_value(previous_s)
                
                if actual is None:
                    stats["no_actual"] += 1
                    continue
                
                # Step 3: Calculate surprise
                if forecast is not None:
                    surprise = actual - forecast
                elif previous is not None:
                    surprise = actual - previous
                else:
                    surprise = 0.0
                    stats["no_surprise"] += 1
                
                # Step 4: Z-score (rolling history)
                history_key = f"{event_type}|{currency}"
                history = surprise_history[history_key]
                z_score = calculate_z_score(surprise, history)
                
                # Update history
                history.append(surprise)
                max_depth = getattr(th, "SURPRISE_HISTORY_DEPTH", 20)
                if len(history) > max_depth:
                    history.pop(0)
                
                # Step 5: Tier
                tier = classify_tier(z_score)
                
                # Step 6: Fundamental direction
                direction, confidence = determine_fundamental_direction(
                    event_type, type_config, currency, surprise, z_score
                )
                
                # Step 7: Currency weight
                curr_weight = get_currency_weight(currency)
                event_weight = type_config.get("base_weight", 0.5)
                
                # Step 8: Insert into events_classified
                cursor.execute("""
                    INSERT OR REPLACE INTO events_classified (
                        raw_id_source, source_table,
                        event_type, event_title, currency, release_time, impact_stars,
                        forecast_value, previous_value, actual_value,
                        surprise_value, z_score, tier,
                        fundamental_direction, direction_confidence,
                        currency_weight, event_weight
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    raw_id, source_table,
                    event_type, title, currency, release_time, impact_stars,
                    forecast, previous, actual,
                    surprise, z_score, tier,
                    direction, confidence,
                    curr_weight, event_weight,
                ))
                
                stats["classified"] += 1
                stats["inserted"] += 1
                stats["by_type"][event_type] += 1
                stats["by_currency"][currency] += 1
                stats["by_tier"][tier] += 1
                stats["by_direction"][direction] += 1
            
            except Exception as e:
                stats["errors"] += 1
                log.debug(f"Error processing event {raw_id}: {e}")
        
        conn.commit()
    
    return stats


# ============================================================
# REPORTING
# ============================================================
def print_classification_report(stats: dict):
    print("\n" + "=" * 70)
    print("CLASSIFICATION SUMMARY")
    print("=" * 70)
    
    print(f"\nInput events:        {stats['total_input']}")
    print(f"Classified:          {stats['classified']}")
    print(f"Inserted/updated:    {stats['inserted']}")
    print(f"\nDropped:")
    print(f"  No pattern match:  {stats['unclassified']}")
    print(f"  Invalid actual:    {stats['no_actual']}")
    print(f"  No forecast/prev:  {stats['no_surprise']}")
    print(f"  Errors:            {stats['errors']}")
    
    print(f"\nBy event type:")
    for etype, count in sorted(stats['by_type'].items(), key=lambda x: -x[1]):
        print(f"  {etype:18}  {count}")
    
    print(f"\nBy currency:")
    for curr, count in sorted(stats['by_currency'].items(), key=lambda x: -x[1]):
        print(f"  {curr:10}          {count}")
    
    print(f"\nBy tier (Z-score impact):")
    tier_labels = {1: "Tier 1 (|Z|>=2.5, outlier)", 2: "Tier 2 (|Z|>=1.8)",
                   3: "Tier 3 (|Z|>=1.0)", 0: "Below threshold"}
    for tier in [1, 2, 3, 0]:
        count = stats['by_tier'].get(tier, 0)
        label = tier_labels.get(tier, f"Tier {tier}")
        print(f"  {label:30}  {count}")
    
    print(f"\nBy direction:")
    for direction, count in sorted(stats['by_direction'].items(), key=lambda x: -x[1]):
        print(f"  {direction:18}  {count}")


def show_top_signals(conn: sqlite3.Connection, limit: int = 15):
    """Show the strongest classified signals."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT release_time, event_type, event_title, currency,
               surprise_value, z_score, tier, fundamental_direction, direction_confidence
        FROM events_classified
        WHERE tier > 0
        ORDER BY ABS(z_score) DESC
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    
    print(f"\n" + "=" * 70)
    print(f"TOP {limit} STRONGEST SIGNALS (by |Z-score|)")
    print("=" * 70)
    
    if not rows:
        print("\nNo classified signals with tier > 0")
        return
    
    print(f"\n  {'Time':16}  {'Type':12}  {'Currency':4}  {'Title':<35}  {'Surprise':>10}  {'Z':>6}  {'Tier':>4}  {'Direction':12}  {'Conf':>5}")
    print(f"  {'-'*16}  {'-'*12}  {'-'*4}  {'-'*35}  {'-'*10}  {'-'*6}  {'-'*4}  {'-'*12}  {'-'*5}")
    
    for row in rows:
        time_s, etype, title, curr, surp, z, tier, direction, conf = row
        time_short = time_s[:16] if time_s else "?"
        title_short = (title or "")[:35]
        surp_s = f"{surp:.3f}" if surp is not None else "N/A"
        z_s = f"{z:.2f}" if z is not None else "N/A"
        direction_short = (direction or "")[:12]
        
        print(f"  {time_short:16}  {etype[:12]:12}  {curr:4}  {title_short:<35}  {surp_s:>10}  {z_s:>6}  {tier:>4}  {direction_short:12}  {conf:>5.2f}")


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Fundamental engine classifier")
    parser.add_argument("--source", default="all",
                        choices=["all", "investing", "forexfactory"],
                        help="Which source table to process")
    parser.add_argument("--force", action="store_true",
                        help="Reclassify all (overwrites existing)")
    parser.add_argument("--show-top", type=int, default=15,
                        help="Show top N strongest signals after classification")
    args = parser.parse_args()
    
    print("=" * 70)
    print("FUNDAMENTAL ENGINE — CLASSIFIER")
    print("=" * 70)
    
    print(f"\nDB:              {fc.DB_PATH}")
    print(f"Source filter:   {args.source}")
    print(f"Force reclass:   {args.force}")
    
    log.info(f"Classifier starting: source={args.source}, force={args.force}")
    
    conn = sqlite3.connect(fc.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # Setup table
    ensure_classified_table(conn)
    
    # If force, truncate first
    if args.force:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events_classified")
        deleted = cursor.rowcount
        conn.commit()
        log.info(f"Force mode: deleted {deleted} existing classifications")
        print(f"\nForce mode: cleared {deleted} existing rows")
    
    # Run classifier
    print(f"\nRunning classification...")
    stats = run_classifier(conn, source_filter=args.source, force=args.force)
    
    # Report
    print_classification_report(stats)
    
    # Show top signals
    if args.show_top > 0:
        show_top_signals(conn, args.show_top)
    
    conn.close()
    
    print("\nDONE.\n")
    print("Next step: build historical reactions module")
    print("           (joins classified events with M15 XAUUSD prices)")
    print()


if __name__ == "__main__":
    main()
