"""
Fundamental Engine — Historical Reactions Builder (Step 2)
===========================================================
Joins classified events with M15 XAUUSD price data to calculate
Gold's actual reaction. Builds the historical hit-rate database.

Pipeline:
  events_classified (979 events with fundamental_direction)
      ↓
  M15 XAUUSD prices (ohlc_live.csv, 96k+ bars)
      ↓
  For each event:
    - Price at T+0 (release)
    - Price at T+15min, T+60min, T+4hr
    - High/Low within 15min window
    - MAE (max adverse) / MFE (max favorable)
    - Direction (UP/DOWN/MUTED with ±$2 buffer)
    - Match check vs fundamental_direction
      ↓
  gold_reactions table
      ↓
  Hit-rate report (per event_type, per currency, per tier)

Usage:
  python C:\\QGAI\\fundamental_engine\\core\\historical_reactions.py
  python C:\\QGAI\\fundamental_engine\\core\\historical_reactions.py --force

Module: fundamental_engine.core.historical_reactions
"""

import sys
import os
import sqlite3
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

# ============================================================
# PATH SETUP
# ============================================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc
from config import thresholds as th


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
log = logging.getLogger("historical_reactions")


# ============================================================
# CONSTANTS
# ============================================================
DIRECTION_BUFFER_USD = getattr(fc, "DIRECTION_BUFFER_USD", 2.0)
PRIMARY_WINDOW_MIN = getattr(fc, "DIRECTION_OBSERVATION_WINDOW_MIN", 15)
M15_BAR_MINUTES = 15
SECONDARY_WINDOW_MIN = 60
EXTENDED_WINDOW_MIN = 240  # 4 hours


# ============================================================
# DATABASE
# ============================================================
def ensure_reactions_table(conn: sqlite3.Connection):
    schema = """
    CREATE TABLE IF NOT EXISTS gold_reactions (
        reaction_id         INTEGER PRIMARY KEY AUTOINCREMENT,
        classified_id       INTEGER NOT NULL UNIQUE,
        
        -- Event reference (denormalized for query speed)
        event_type          TEXT NOT NULL,
        event_title         TEXT NOT NULL,
        normalized_title    TEXT NOT NULL,
        currency            TEXT NOT NULL,
        release_time        TIMESTAMP NOT NULL,
        impact_stars        INTEGER,
        tier                INTEGER,
        fundamental_direction TEXT,
        direction_confidence  REAL,
        z_score             REAL,
        
        -- Prices
        price_t0            REAL,
        price_t15min        REAL,
        price_t60min        REAL,
        price_t4hr          REAL,
        
        -- Moves USD
        move_15min_usd      REAL,
        move_60min_usd      REAL,
        move_4hr_usd        REAL,
        
        -- Moves %
        move_15min_pct      REAL,
        move_60min_pct      REAL,
        move_4hr_pct        REAL,
        
        -- Window highs/lows (for MAE/MFE)
        high_15min          REAL,
        low_15min           REAL,
        mae_15min           REAL,
        mfe_15min           REAL,
        
        -- Direction analysis
        observed_direction  TEXT,    -- UP, DOWN, MUTED
        direction_matched   INTEGER, -- 1=match, 0=mismatch, NULL=neutral/muted
        
        -- Quality
        data_quality        TEXT,    -- good, partial, no_data
        notes               TEXT,
        
        analysis_date       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_gr_release ON gold_reactions(release_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_gr_event_type ON gold_reactions(event_type);",
        "CREATE INDEX IF NOT EXISTS idx_gr_tier ON gold_reactions(tier DESC);",
        "CREATE INDEX IF NOT EXISTS idx_gr_match ON gold_reactions(direction_matched);",
        "CREATE INDEX IF NOT EXISTS idx_gr_norm_title ON gold_reactions(normalized_title);",
    ]
    
    cursor = conn.cursor()
    cursor.execute(schema)
    for idx in indexes:
        cursor.execute(idx)
    conn.commit()
    log.info("gold_reactions table verified/created")


# ============================================================
# LOAD M15 PRICES
# ============================================================
def load_m15_prices() -> Optional[pd.DataFrame]:
    """Load M15 OHLC into DataFrame indexed by timestamp."""
    csv_path = fc.M15_PRICE_FILE
    
    if not os.path.exists(csv_path):
        log.error(f"M15 file not found: {csv_path}")
        return None
    
    log.info(f"Loading M15 prices from {csv_path}")
    
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        log.error(f"Failed to read CSV: {e}")
        return None
    
    # Detect time column
    time_col = None
    for col in df.columns:
        if col.lower() in ("time", "datetime", "timestamp", "date"):
            time_col = col
            break
    
    if time_col is None:
        # Try first column
        time_col = df.columns[0]
        log.warning(f"No explicit time column, using first: {time_col}")
    
    # Parse times
    df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
    df = df.dropna(subset=[time_col])
    df = df.set_index(time_col).sort_index()
    
    # Normalize OHLC column names (handle different conventions)
    col_map = {}
    for col in df.columns:
        col_lower = col.lower()
        if col_lower in ("open", "o"):
            col_map[col] = "open"
        elif col_lower in ("high", "h"):
            col_map[col] = "high"
        elif col_lower in ("low", "l"):
            col_map[col] = "low"
        elif col_lower in ("close", "c"):
            col_map[col] = "close"
    
    df = df.rename(columns=col_map)
    
    required = ["open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        log.error(f"Missing OHLC columns: {missing}. Available: {list(df.columns)}")
        return None
    
    log.info(f"Loaded {len(df)} bars, range: {df.index.min()} to {df.index.max()}")
    return df


# ============================================================
# REACTION CALCULATION
# ============================================================
def find_bar_at_or_after(df: pd.DataFrame, target_time: datetime) -> Optional[pd.Series]:
    """Find the M15 bar that contains or is just after target_time."""
    try:
        # Get the next bar at or after target
        idx = df.index.searchsorted(target_time, side='left')
        if idx >= len(df):
            return None
        return df.iloc[idx]
    except Exception:
        return None


def find_bars_in_range(df: pd.DataFrame, start_time: datetime, end_time: datetime) -> Optional[pd.DataFrame]:
    """Get all bars in [start_time, end_time]."""
    try:
        mask = (df.index >= start_time) & (df.index < end_time)
        return df.loc[mask]
    except Exception:
        return None


def classify_observed_direction(price_t0: float, price_after: float, buffer: float) -> str:
    """Determine direction with $-buffer."""
    if price_t0 is None or price_after is None:
        return "MUTED"
    
    diff = price_after - price_t0
    if diff > buffer:
        return "UP"
    elif diff < -buffer:
        return "DOWN"
    else:
        return "MUTED"


def calculate_match(fundamental_direction: str, observed_direction: str) -> Optional[int]:
    """Compare fundamental view to observed reaction."""
    if observed_direction == "MUTED" or fundamental_direction == "NEUTRAL":
        return None
    
    if fundamental_direction == "BULLISH_GOLD" and observed_direction == "UP":
        return 1
    elif fundamental_direction == "BEARISH_GOLD" and observed_direction == "DOWN":
        return 1
    else:
        return 0


def build_reaction(event_row, df_m15) -> dict:
    """Build complete reaction record for a single event."""
    
    (classified_id, event_type, event_title, normalized_title, currency,
     release_time_str, impact_stars, tier, fundamental_direction,
     direction_confidence, z_score) = event_row
    
    reaction = {
        "classified_id": classified_id,
        "event_type": event_type,
        "event_title": event_title,
        "normalized_title": normalized_title,
        "currency": currency,
        "release_time": release_time_str,
        "impact_stars": impact_stars,
        "tier": tier,
        "fundamental_direction": fundamental_direction,
        "direction_confidence": direction_confidence,
        "z_score": z_score,
        "price_t0": None,
        "price_t15min": None,
        "price_t60min": None,
        "price_t4hr": None,
        "move_15min_usd": None,
        "move_60min_usd": None,
        "move_4hr_usd": None,
        "move_15min_pct": None,
        "move_60min_pct": None,
        "move_4hr_pct": None,
        "high_15min": None,
        "low_15min": None,
        "mae_15min": None,
        "mfe_15min": None,
        "observed_direction": None,
        "direction_matched": None,
        "data_quality": "no_data",
        "notes": "",
    }
    
    # Parse release time
    try:
        release_time = pd.to_datetime(release_time_str)
    except Exception:
        reaction["notes"] = "invalid release_time"
        return reaction
    
    # T+0 bar
    bar_t0 = find_bar_at_or_after(df_m15, release_time)
    if bar_t0 is None:
        reaction["notes"] = "no T+0 bar (outside price data range)"
        return reaction
    
    price_t0 = float(bar_t0["open"])
    reaction["price_t0"] = price_t0
    
    # T+15min bar
    t15_target = release_time + timedelta(minutes=PRIMARY_WINDOW_MIN)
    bar_t15 = find_bar_at_or_after(df_m15, t15_target)
    
    # T+60min bar
    t60_target = release_time + timedelta(minutes=SECONDARY_WINDOW_MIN)
    bar_t60 = find_bar_at_or_after(df_m15, t60_target)
    
    # T+4hr bar
    t4hr_target = release_time + timedelta(minutes=EXTENDED_WINDOW_MIN)
    bar_t4hr = find_bar_at_or_after(df_m15, t4hr_target)
    
    # Window bars for high/low
    window_bars = find_bars_in_range(df_m15, release_time, t15_target + timedelta(minutes=M15_BAR_MINUTES))
    
    if bar_t15 is not None:
        reaction["price_t15min"] = float(bar_t15["close"])
        reaction["move_15min_usd"] = reaction["price_t15min"] - price_t0
        if price_t0 != 0:
            reaction["move_15min_pct"] = reaction["move_15min_usd"] / price_t0 * 100
    
    if bar_t60 is not None:
        reaction["price_t60min"] = float(bar_t60["close"])
        reaction["move_60min_usd"] = reaction["price_t60min"] - price_t0
        if price_t0 != 0:
            reaction["move_60min_pct"] = reaction["move_60min_usd"] / price_t0 * 100
    
    if bar_t4hr is not None:
        reaction["price_t4hr"] = float(bar_t4hr["close"])
        reaction["move_4hr_usd"] = reaction["price_t4hr"] - price_t0
        if price_t0 != 0:
            reaction["move_4hr_pct"] = reaction["move_4hr_usd"] / price_t0 * 100
    
    # Window high/low + MAE/MFE
    if window_bars is not None and len(window_bars) > 0:
        reaction["high_15min"] = float(window_bars["high"].max())
        reaction["low_15min"] = float(window_bars["low"].min())
        # MAE = max adverse from price_t0
        # MFE = max favorable from price_t0
        reaction["mfe_15min"] = reaction["high_15min"] - price_t0
        reaction["mae_15min"] = reaction["low_15min"] - price_t0
    
    # Direction observation
    if reaction["price_t15min"] is not None:
        observed = classify_observed_direction(price_t0, reaction["price_t15min"], DIRECTION_BUFFER_USD)
        reaction["observed_direction"] = observed
        reaction["direction_matched"] = calculate_match(fundamental_direction, observed)
    
    # Data quality assessment
    if reaction["price_t15min"] and reaction["price_t60min"] and reaction["price_t4hr"]:
        reaction["data_quality"] = "good"
    elif reaction["price_t15min"]:
        reaction["data_quality"] = "partial"
        reaction["notes"] = "missing later windows"
    else:
        reaction["data_quality"] = "no_data"
        reaction["notes"] = "no T+15 bar"
    
    return reaction


# ============================================================
# MAIN PROCESSING
# ============================================================
def process_all_events(conn: sqlite3.Connection, df_m15: pd.DataFrame, force: bool = False) -> dict:
    cursor = conn.cursor()
    
    # If force, clear existing
    if force:
        cursor.execute("DELETE FROM gold_reactions")
        conn.commit()
        log.info("Force mode: cleared gold_reactions")
    
    # Fetch classified events
    cursor.execute("""
        SELECT classified_id, event_type, event_title, normalized_title, currency,
               release_time, impact_stars, tier, fundamental_direction,
               direction_confidence, z_score
        FROM events_classified
        ORDER BY release_time ASC
    """)
    
    events = cursor.fetchall()
    log.info(f"Processing {len(events)} classified events")
    
    stats = {
        "total": len(events),
        "processed": 0,
        "inserted": 0,
        "no_t0_bar": 0,
        "no_t15_bar": 0,
        "good_quality": 0,
        "partial_quality": 0,
        "no_data": 0,
        "matched": 0,
        "mismatched": 0,
        "muted": 0,
        "skipped_neutral": 0,
        "errors": 0,
    }
    
    for ev_row in events:
        try:
            reaction = build_reaction(ev_row, df_m15)
            
            # Update stats
            stats["processed"] += 1
            if reaction["data_quality"] == "good":
                stats["good_quality"] += 1
            elif reaction["data_quality"] == "partial":
                stats["partial_quality"] += 1
            else:
                stats["no_data"] += 1
            
            if reaction["data_quality"] != "no_data":
                if reaction["direction_matched"] == 1:
                    stats["matched"] += 1
                elif reaction["direction_matched"] == 0:
                    stats["mismatched"] += 1
                elif reaction["observed_direction"] == "MUTED":
                    stats["muted"] += 1
                elif reaction["fundamental_direction"] == "NEUTRAL":
                    stats["skipped_neutral"] += 1
            else:
                if "T+0" in reaction["notes"]:
                    stats["no_t0_bar"] += 1
                elif "T+15" in reaction["notes"]:
                    stats["no_t15_bar"] += 1
            
            # Insert
            cursor.execute("""
                INSERT OR REPLACE INTO gold_reactions (
                    classified_id, event_type, event_title, normalized_title, currency,
                    release_time, impact_stars, tier, fundamental_direction,
                    direction_confidence, z_score,
                    price_t0, price_t15min, price_t60min, price_t4hr,
                    move_15min_usd, move_60min_usd, move_4hr_usd,
                    move_15min_pct, move_60min_pct, move_4hr_pct,
                    high_15min, low_15min, mae_15min, mfe_15min,
                    observed_direction, direction_matched,
                    data_quality, notes
                ) VALUES (
                    :classified_id, :event_type, :event_title, :normalized_title, :currency,
                    :release_time, :impact_stars, :tier, :fundamental_direction,
                    :direction_confidence, :z_score,
                    :price_t0, :price_t15min, :price_t60min, :price_t4hr,
                    :move_15min_usd, :move_60min_usd, :move_4hr_usd,
                    :move_15min_pct, :move_60min_pct, :move_4hr_pct,
                    :high_15min, :low_15min, :mae_15min, :mfe_15min,
                    :observed_direction, :direction_matched,
                    :data_quality, :notes
                )
            """, reaction)
            
            stats["inserted"] += 1
        
        except Exception as e:
            stats["errors"] += 1
            log.debug(f"Error processing event: {e}")
    
    conn.commit()
    return stats


# ============================================================
# REPORTING
# ============================================================
def print_processing_summary(stats: dict):
    print("\n" + "=" * 70)
    print("PROCESSING SUMMARY")
    print("=" * 70)
    
    print(f"\nTotal classified events:   {stats['total']}")
    print(f"Processed:                 {stats['processed']}")
    print(f"Inserted into gold_reactions: {stats['inserted']}")
    print(f"Errors:                    {stats['errors']}")
    
    print(f"\nData quality:")
    print(f"  Good (all windows):      {stats['good_quality']}")
    print(f"  Partial (T+15 only):     {stats['partial_quality']}")
    print(f"  No data (outside range): {stats['no_data']}")
    
    print(f"\nDirection analysis:")
    print(f"  Matched:                 {stats['matched']}")
    print(f"  Mismatched:              {stats['mismatched']}")
    print(f"  Muted (within ${DIRECTION_BUFFER_USD} buffer): {stats['muted']}")
    print(f"  Skipped (NEUTRAL):       {stats['skipped_neutral']}")
    
    # Calculate hit rate
    determined = stats['matched'] + stats['mismatched']
    if determined > 0:
        hit_rate = stats['matched'] / determined * 100
        print(f"\nOverall hit rate: {hit_rate:.1f}% ({stats['matched']}/{determined})")


def show_hit_rates_by_event_type(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT event_type,
               SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END) as matched,
               SUM(CASE WHEN direction_matched = 0 THEN 1 ELSE 0 END) as mismatched,
               SUM(CASE WHEN observed_direction = 'MUTED' THEN 1 ELSE 0 END) as muted,
               COUNT(*) as total
        FROM gold_reactions
        WHERE data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
        GROUP BY event_type
        ORDER BY (matched + mismatched) DESC
    """)
    
    rows = cursor.fetchall()
    
    print("\n" + "=" * 70)
    print("HIT RATES BY EVENT TYPE (15min observation window)")
    print("=" * 70)
    print(f"\n  {'Event Type':14} {'Match':>6} {'Mismatch':>9} {'Muted':>6} {'Total':>6} {'Hit %':>7}")
    print(f"  {'-'*14} {'-'*6} {'-'*9} {'-'*6} {'-'*6} {'-'*7}")
    
    for row in rows:
        etype, matched, mismatched, muted, total = row
        det = matched + mismatched
        hit_rate = (matched / det * 100) if det > 0 else 0
        print(f"  {etype:14} {matched:>6} {mismatched:>9} {muted:>6} {total:>6} {hit_rate:>6.1f}%")


def show_hit_rates_by_tier(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tier,
               SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END) as matched,
               SUM(CASE WHEN direction_matched = 0 THEN 1 ELSE 0 END) as mismatched,
               SUM(CASE WHEN observed_direction = 'MUTED' THEN 1 ELSE 0 END) as muted,
               COUNT(*) as total
        FROM gold_reactions
        WHERE data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
        GROUP BY tier
        ORDER BY tier ASC
    """)
    
    rows = cursor.fetchall()
    
    print("\n" + "=" * 70)
    print("HIT RATES BY TIER (Z-score impact)")
    print("=" * 70)
    print(f"\n  {'Tier':4} {'Match':>6} {'Mismatch':>9} {'Muted':>6} {'Total':>6} {'Hit %':>7}")
    print(f"  {'-'*4} {'-'*6} {'-'*9} {'-'*6} {'-'*6} {'-'*7}")
    
    tier_labels = {0: "0 (no Z)", 1: "1 (>=2.5)", 2: "2 (>=1.8)", 3: "3 (>=1.0)"}
    for row in rows:
        tier, matched, mismatched, muted, total = row
        det = matched + mismatched
        hit_rate = (matched / det * 100) if det > 0 else 0
        label = tier_labels.get(tier, f"T{tier}")
        print(f"  {label:4} {matched:>6} {mismatched:>9} {muted:>6} {total:>6} {hit_rate:>6.1f}%")


def show_top_reactions(conn: sqlite3.Connection, limit: int = 15):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT release_time, event_type, currency, event_title,
               fundamental_direction, observed_direction, direction_matched,
               move_15min_usd, mae_15min, mfe_15min
        FROM gold_reactions
        WHERE data_quality != 'no_data'
          AND fundamental_direction != 'NEUTRAL'
          AND tier > 0
          AND ABS(move_15min_usd) > 2
        ORDER BY ABS(move_15min_usd) DESC
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    
    print("\n" + "=" * 70)
    print(f"TOP {limit} STRONGEST GOLD REACTIONS (15min, Tier>0, non-NEUTRAL)")
    print("=" * 70)
    
    if not rows:
        print("\nNo reactions matching criteria")
        return
    
    print(f"\n  {'Time':16} {'Type':10} {'Curr':4} {'Title':<30} {'Fund':12} {'Obs':6} {'M?':2} {'15min$':>7} {'MAE':>6} {'MFE':>6}")
    print(f"  {'-'*16} {'-'*10} {'-'*4} {'-'*30} {'-'*12} {'-'*6} {'-'*2} {'-'*7} {'-'*6} {'-'*6}")
    
    for row in rows:
        time_s, etype, curr, title, fund, obs, matched, move, mae, mfe = row
        ts = time_s[:16] if time_s else "?"
        title_s = (title or "")[:30]
        match_s = "Y" if matched == 1 else ("N" if matched == 0 else "-")
        move_s = f"{move:.2f}" if move else "N/A"
        mae_s = f"{mae:.1f}" if mae else "N/A"
        mfe_s = f"{mfe:.1f}" if mfe else "N/A"
        print(f"  {ts:16} {etype[:10]:10} {curr:4} {title_s:<30} {fund[:12]:12} {obs[:6]:6} {match_s:2} {move_s:>7} {mae_s:>6} {mfe_s:>6}")


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Clear and rebuild all reactions")
    parser.add_argument("--show-top", type=int, default=15)
    args = parser.parse_args()
    
    print("=" * 70)
    print("FUNDAMENTAL ENGINE — HISTORICAL REACTIONS BUILDER")
    print("=" * 70)
    
    print(f"\nDB:                {fc.DB_PATH}")
    print(f"M15 prices:        {fc.M15_PRICE_FILE}")
    print(f"Direction buffer:  ${DIRECTION_BUFFER_USD}")
    print(f"Primary window:    {PRIMARY_WINDOW_MIN} minutes")
    print(f"Force rebuild:     {args.force}")
    
    # Load M15 prices
    df_m15 = load_m15_prices()
    if df_m15 is None:
        print("\nFATAL: Could not load M15 prices. Aborting.")
        return
    
    # Open DB
    conn = sqlite3.connect(fc.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    ensure_reactions_table(conn)
    
    # Process all events
    print(f"\nProcessing reactions...")
    stats = process_all_events(conn, df_m15, force=args.force)
    
    # Reports
    print_processing_summary(stats)
    show_hit_rates_by_event_type(conn)
    show_hit_rates_by_tier(conn)
    if args.show_top > 0:
        show_top_reactions(conn, args.show_top)
    
    conn.close()
    
    print("\nDONE.\n")
    print("Next step: build engine core (mode detection + signal generation)")
    print()


if __name__ == "__main__":
    main()
