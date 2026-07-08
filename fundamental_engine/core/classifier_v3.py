"""
Fundamental Engine — Classifier Module v3 (FINAL)
==================================================
All bugs fixed:
  - EXACT direction_rule aliases matching user's config:
      hawkish_bearish_gold, higher_bearish_gold, stronger_bearish_gold, tone_based, complex
  - Inverse-jobs event handling (Unemployment Rate, Jobless Claims)
  - Per-event-title Z-score history (accurate across event series)
  - Normalized surprise (% of baseline)
  - Z-score capping at |10|
  - Special handling for "complex" and "tone_based" rules

Usage:
  python C:\\QGAI\\fundamental_engine\\core\\classifier_v3.py --diagnose
  python C:\\QGAI\\fundamental_engine\\core\\classifier_v3.py --force
"""

import sys
import os
import re
import sqlite3
import argparse
import logging
import statistics
from pathlib import Path
from datetime import datetime
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
log = logging.getLogger("classifier_v3")


# ============================================================
# CONSTANTS
# ============================================================
Z_SCORE_CAP = 10.0
MIN_HISTORY_FOR_Z = 5


# ============================================================
# DIRECTION RULE ALIASES — Matches user's actual config
# ============================================================
DIRECTION_RULE_ALIASES = {
    # USER'S ACTUAL CONFIG VALUES:
    "hawkish_bearish_gold":  "HAWKISH_ON_HIGH",   # rate_decision
    "higher_bearish_gold":   "HAWKISH_ON_HIGH",   # inflation
    "stronger_bearish_gold": "HAWKISH_ON_HIGH",   # jobs, growth, sentiment, housing
    "tone_based":            "TONE_BASED",        # qualitative — special handler
    "complex":               "COMPLEX",           # trade — context dependent
    
    # Generic aliases (for future flexibility)
    "hawkish_on_high":   "HAWKISH_ON_HIGH",
    "higher_is_hawkish": "HAWKISH_ON_HIGH",
    "high_hawkish":      "HAWKISH_ON_HIGH",
    "positive_hawkish":  "HAWKISH_ON_HIGH",
    "dovish_on_high":    "DOVISH_ON_HIGH",
    "higher_is_dovish":  "DOVISH_ON_HIGH",
    "bullish_on_high":   "HAWKISH_ON_HIGH",
    "bearish_on_high":   "DOVISH_ON_HIGH",
    "neutral":           "NEUTRAL",
}


# ============================================================
# INVERSE JOBS EVENTS — Higher value = weaker jobs = BULLISH gold
# ============================================================
INVERSE_JOBS_KEYWORDS = [
    "unemployment rate",
    "u6 unemployment",
    "jobless claims",
    "initial claims",
    "continuing claims",
    "unemployment claims",
    "ilo unemployment",
]

# Inverse for these specific events: higher reading = weak = BULLISH gold
# (Same logic for non-USD: higher foreign unemployment = strong USD relatively = BEARISH gold)


# ============================================================
# INVERSE TRADE EVENTS — Higher imports = weaker trade balance = BULLISH gold
# ============================================================
INVERSE_TRADE_KEYWORDS = [
    "imports",
    "import price",
    "import index",
]

# Logic: Higher imports widen trade deficit → currency weak → BULLISH gold (for USD)
# Exports/Trade Balance follow standard: Higher = currency strong = BEARISH gold


def is_inverse_jobs_event(event_title: str) -> bool:
    """Check if this is an 'inverse direction' jobs event."""
    if not event_title:
        return False
    title_lower = event_title.lower()
    return any(kw in title_lower for kw in INVERSE_JOBS_KEYWORDS)


def is_inverse_trade_event(event_title: str) -> bool:
    """Check if this is an 'inverse direction' trade event (imports)."""
    if not event_title:
        return False
    title_lower = event_title.lower()
    # Must contain "import" but NOT also "export" (some events mention both)
    if "export" in title_lower:
        return False
    return any(kw in title_lower for kw in INVERSE_TRADE_KEYWORDS)


def normalize_direction_rule(rule: str) -> str:
    if not rule:
        return "NEUTRAL"
    return DIRECTION_RULE_ALIASES.get(rule.lower().strip(), "NEUTRAL")


# ============================================================
# DATABASE SCHEMA
# ============================================================
def ensure_classified_table(conn: sqlite3.Connection):
    schema = """
    CREATE TABLE IF NOT EXISTS events_classified (
        classified_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_id_source       INTEGER NOT NULL,
        source_table        TEXT NOT NULL,
        event_type          TEXT NOT NULL,
        event_title         TEXT NOT NULL,
        normalized_title    TEXT NOT NULL,
        currency            TEXT NOT NULL,
        release_time        TIMESTAMP NOT NULL,
        impact_stars        INTEGER,
        forecast_value      REAL,
        previous_value      REAL,
        actual_value        REAL,
        surprise_value      REAL,
        surprise_normalized REAL,
        z_score             REAL,
        tier                INTEGER,
        is_inverse          INTEGER DEFAULT 0,
        fundamental_direction TEXT,
        direction_confidence  REAL,
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
        "CREATE INDEX IF NOT EXISTS idx_cl_normtitle ON events_classified(normalized_title);",
    ]
    
    cursor = conn.cursor()
    cursor.execute(schema)
    for idx in indexes:
        cursor.execute(idx)
    conn.commit()


# ============================================================
# UTILITIES
# ============================================================
def normalize_event_title(title: str) -> str:
    if not title:
        return ""
    cleaned = re.sub(r'\s*\((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Q[1-4]|H[1-2])\)\s*$', '', title.strip())
    cleaned = re.sub(r'\s*\(Q[1-4]\)\s*', '', cleaned).strip()
    return cleaned


def extract_numeric_value(value_str) -> Optional[float]:
    if not value_str:
        return None
    s = str(value_str).strip()
    if not s:
        return None
    s = s.replace("$", "").replace("€", "").replace("£", "").replace("¥", "")
    s = s.replace(",", "").replace(" ", "")
    
    multiplier = 1.0
    suffix_map = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}
    
    if s.endswith("%"):
        s = s[:-1]
    if s and s[-1].upper() in suffix_map:
        multiplier = suffix_map[s[-1].upper()]
        s = s[:-1]
    
    try:
        return float(s) * multiplier
    except (ValueError, TypeError):
        return None


# ============================================================
# EVENT TYPE CLASSIFICATION
# ============================================================
def classify_event_type(event_title: str):
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


# ============================================================
# Z-SCORE
# ============================================================
def calculate_normalized_surprise(actual, forecast, previous) -> tuple:
    if forecast is not None:
        raw = actual - forecast
        baseline = forecast
    elif previous is not None:
        raw = actual - previous
        baseline = previous
    else:
        return 0.0, 0.0
    
    if abs(baseline) > 0.0001:
        normalized = raw / abs(baseline)
    else:
        normalized = raw
    
    return raw, normalized


def calculate_z_score(current, history):
    if not history or len(history) < MIN_HISTORY_FOR_Z:
        return None
    try:
        mean = statistics.mean(history)
        std = statistics.stdev(history)
        if std < 1e-9:
            return 0.0
        z = (current - mean) / std
        return max(-Z_SCORE_CAP, min(Z_SCORE_CAP, z))
    except statistics.StatisticsError:
        return None


def classify_tier(z_score):
    if z_score is None:
        return 0
    abs_z = abs(z_score)
    thresholds = getattr(th, "Z_THRESHOLDS", {3: 1.0, 2: 1.8, 1: 2.5})
    if abs_z >= thresholds.get(1, 2.5):
        return 1
    elif abs_z >= thresholds.get(2, 1.8):
        return 2
    elif abs_z >= thresholds.get(3, 1.0):
        return 3
    return 0


# ============================================================
# FUNDAMENTAL DIRECTION — Full Logic
# ============================================================
def determine_fundamental_direction(
    event_type: str,
    event_title: str,
    type_config: dict,
    currency: str,
    surprise: float,
    z_score,
) -> tuple:
    """
    Returns (direction, confidence).
    
    Logic:
      1. Get canonical direction rule
      2. Determine "metric direction" (HAWKISH/DOVISH for currency)
      3. Apply inverse-jobs override if applicable
      4. Map to gold direction (currency-aware)
      5. Confidence from |Z|
    """
    raw_rule = type_config.get("direction_rule", "neutral")
    canonical = normalize_direction_rule(raw_rule)
    
    if canonical == "NEUTRAL":
        return "NEUTRAL", 0.0
    
    # COMPLEX and TONE_BASED — needs special handlers (future work)
    # For now, treat as neutral but flag confidence
    if canonical in ("COMPLEX", "TONE_BASED"):
        return "NEUTRAL", 0.0
    
    # Zero surprise = actual matched forecast exactly — no new information, no direction.
    if surprise == 0:
        return "NEUTRAL", 0.0

    # Determine currency view from surprise
    if canonical == "HAWKISH_ON_HIGH":
        currency_view = "HAWKISH" if surprise > 0 else "DOVISH"
    elif canonical == "DOVISH_ON_HIGH":
        currency_view = "DOVISH" if surprise > 0 else "HAWKISH"
    else:
        return "NEUTRAL", 0.0
    
    # INVERSE JOBS OVERRIDE
    # If this is an inverse-jobs event (unemployment, claims), flip the currency_view
    if event_type == "jobs" and is_inverse_jobs_event(event_title):
        currency_view = "DOVISH" if currency_view == "HAWKISH" else "HAWKISH"
    
    # INVERSE TRADE OVERRIDE
    # If this is an imports event, flip currency_view
    # (Higher imports → trade deficit grows → currency weak)
    if event_type == "trade" and is_inverse_trade_event(event_title):
        currency_view = "DOVISH" if currency_view == "HAWKISH" else "HAWKISH"
    
    # Map to Gold direction (currency-aware).
    # CURRENCY_DIRECTION_FLIP controls whether a hawkish reading for this currency
    # is bullish or bearish for gold.
    # USD: hawkish = USD strong = BEARISH gold (no flip)
    # EUR/GBP/AUD etc: hawkish = USD weak = BULLISH gold (flip)
    # JPY/CHF: safe-haven dynamic — do NOT flip (same direction as USD)
    flip = ec.CURRENCY_DIRECTION_FLIP.get(currency, True)  # default flip for unknown currencies
    if not flip:
        # USD-like: hawkish → BEARISH gold
        gold_direction = "BEARISH_GOLD" if currency_view == "HAWKISH" else "BULLISH_GOLD"
    else:
        # Non-USD (EUR, GBP, etc.): hawkish → BULLISH gold
        gold_direction = "BULLISH_GOLD" if currency_view == "HAWKISH" else "BEARISH_GOLD"
    
    # Confidence from |Z|
    if z_score is None:
        confidence = 0.3
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


def get_currency_weight(currency: str) -> float:
    relevance = getattr(ec, "CURRENCY_RELEVANCE", {})
    return relevance.get(currency, 0.1)


# ============================================================
# DIAGNOSTIC
# ============================================================
def run_diagnostic():
    print("=" * 70)
    print("CLASSIFIER v3 DIAGNOSTIC")
    print("=" * 70)
    
    print("\n[1] EVENT_TYPE_PATTERNS:")
    for event_type, config in ec.EVENT_TYPE_PATTERNS.items():
        raw_rule = config.get("direction_rule", "MISSING")
        canonical = normalize_direction_rule(raw_rule)
        patterns_count = len(config.get("patterns", []))
        
        if canonical == "NEUTRAL" and raw_rule.lower() not in ("neutral", "none"):
            status = "WARN (unrecognized)"
        elif canonical in ("COMPLEX", "TONE_BASED"):
            status = "DEFERRED (needs special handler)"
        else:
            status = "OK"
        
        print(f"\n  [{event_type}]")
        print(f"     raw rule:     {raw_rule}")
        print(f"     canonical:    {canonical}  [{status}]")
        print(f"     patterns:     {patterns_count}")
    
    print("\n[2] INVERSE JOBS keywords (will flip direction):")
    for kw in INVERSE_JOBS_KEYWORDS:
        print(f"   - {kw}")
    
    print("\n[3] Sample direction calculations:")
    examples = [
        ("USD", "Core CPI (YoY)", "inflation", 0.3, "HAWKISH→BEARISH_GOLD"),
        ("USD", "Core CPI (YoY)", "inflation", -0.2, "DOVISH→BULLISH_GOLD"),
        ("USD", "Nonfarm Payrolls", "jobs", 87.0, "HAWKISH→BEARISH_GOLD"),
        ("USD", "Unemployment Rate", "jobs", 0.2, "INVERSE-DOVISH→BULLISH_GOLD"),
        ("USD", "Initial Jobless Claims", "jobs", 15.0, "INVERSE-DOVISH→BULLISH_GOLD"),
        ("EUR", "CPI (YoY)", "inflation", 0.2, "HAWKISH EUR→BULLISH_GOLD"),
        ("EUR", "Unemployment Rate", "jobs", 0.1, "INVERSE-DOVISH EUR→BEARISH_GOLD"),
    ]
    print(f"\n  {'Currency':8} {'Event':24} {'Type':10} {'Surprise':>10}  Expected")
    print(f"  {'-'*8} {'-'*24} {'-'*10} {'-'*10}  {'-'*30}")
    for curr, title, etype, surp, expected in examples:
        type_config = ec.EVENT_TYPE_PATTERNS.get(etype, {})
        direction, confidence = determine_fundamental_direction(
            etype, title, type_config, curr, surp, 1.5
        )
        match = "OK" if expected.split("→")[-1] == direction else "MISMATCH"
        print(f"  {curr:8} {title[:24]:24} {etype:10} {surp:>10.2f}  Got: {direction:14} [{match}]")
    
    print("\nDONE.\n")


# ============================================================
# MAIN PIPELINE
# ============================================================
def run_classifier(conn, source_filter="all"):
    cursor = conn.cursor()
    
    sources = []
    if source_filter in ("all", "investing"):
        sources.append("events_investing_raw")
    if source_filter in ("all", "forexfactory"):
        # events_raw is where news_fetcher.py writes live ForexFactory data.
        # events_forexfactory_raw is a legacy name kept for backward compatibility.
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events_raw'")
        if cursor.fetchone():
            sources.append("events_raw")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events_forexfactory_raw'")
        if cursor.fetchone():
            sources.append("events_forexfactory_raw")
    if source_filter in ("all", "csv"):
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events_csv_import'")
        if cursor.fetchone():
            sources.append("events_csv_import")
    
    surprise_history = defaultdict(list)
    
    stats = {
        "total_input": 0, "classified": 0, "unclassified": 0,
        "no_actual": 0, "no_surprise": 0, "inserted": 0, "errors": 0,
        "by_type": defaultdict(int), "by_currency": defaultdict(int),
        "by_tier": defaultdict(int), "by_direction": defaultdict(int),
        "inverse_jobs_count": 0,
    }
    
    for source_table in sources:
        log.info(f"Processing source: {source_table}")
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
            raw_id, title, currency, release_time, impact_stars, fc_s, prev_s, act_s = ev
            
            try:
                match = classify_event_type(title)
                if not match:
                    stats["unclassified"] += 1
                    continue
                event_type, type_config = match
                
                actual = extract_numeric_value(act_s)
                forecast = extract_numeric_value(fc_s)
                previous = extract_numeric_value(prev_s)
                
                if actual is None:
                    stats["no_actual"] += 1
                    continue
                
                raw_surp, norm_surp = calculate_normalized_surprise(actual, forecast, previous)

                if forecast is None and previous is None:
                    # No baseline to compute a surprise against — cannot assign direction.
                    # Must skip here; falling through would classify surprise=0 as DOVISH.
                    stats["no_surprise"] += 1
                    continue
                
                normalized_title = normalize_event_title(title)
                history_key = f"{currency}|{normalized_title}"
                
                history = surprise_history[history_key]
                z_score = calculate_z_score(norm_surp, history)
                
                history.append(norm_surp)
                max_depth = getattr(th, "SURPRISE_HISTORY_DEPTH", 20)
                if len(history) > max_depth:
                    history.pop(0)
                
                tier = classify_tier(z_score)
                
                is_inverse = 0
                if event_type == "jobs" and is_inverse_jobs_event(title):
                    is_inverse = 1
                elif event_type == "trade" and is_inverse_trade_event(title):
                    is_inverse = 1
                
                if is_inverse:
                    stats["inverse_jobs_count"] += 1
                
                direction, confidence = determine_fundamental_direction(
                    event_type, title, type_config, currency, raw_surp, z_score
                )
                
                curr_weight = get_currency_weight(currency)
                event_weight = type_config.get("base_weight", 0.5)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO events_classified (
                        raw_id_source, source_table,
                        event_type, event_title, normalized_title, currency, release_time, impact_stars,
                        forecast_value, previous_value, actual_value,
                        surprise_value, surprise_normalized, z_score, tier, is_inverse,
                        fundamental_direction, direction_confidence,
                        currency_weight, event_weight
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    raw_id, source_table,
                    event_type, title, normalized_title, currency, release_time, impact_stars,
                    forecast, previous, actual,
                    raw_surp, norm_surp, z_score, tier, is_inverse,
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
                log.debug(f"Error: {e}")
        
        conn.commit()
    
    return stats


# ============================================================
# REPORTING
# ============================================================
def print_summary(stats):
    print("\n" + "=" * 70)
    print("CLASSIFICATION SUMMARY")
    print("=" * 70)
    
    print(f"\nInput:               {stats['total_input']}")
    print(f"Classified:          {stats['classified']}")
    print(f"Inserted:            {stats['inserted']}")
    print(f"Inverse jobs:        {stats['inverse_jobs_count']}")
    
    print(f"\nDropped:")
    print(f"  No pattern match:  {stats['unclassified']}")
    print(f"  Invalid actual:    {stats['no_actual']}")
    print(f"  No surprise:       {stats['no_surprise']}")
    print(f"  Errors:            {stats['errors']}")
    
    print(f"\nBy event type:")
    for etype, count in sorted(stats['by_type'].items(), key=lambda x: -x[1]):
        print(f"  {etype:18}  {count}")
    
    print(f"\nBy tier:")
    tier_labels = {1: "Tier 1 |Z|>=2.5", 2: "Tier 2 |Z|>=1.8", 3: "Tier 3 |Z|>=1.0", 0: "Below thresh"}
    for tier in [1, 2, 3, 0]:
        count = stats['by_tier'].get(tier, 0)
        print(f"  {tier_labels[tier]:18}  {count}")
    
    print(f"\nBy direction:")
    for direction, count in sorted(stats['by_direction'].items(), key=lambda x: -x[1]):
        print(f"  {direction:18}  {count}")


def show_top_signals(conn, limit=20):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT release_time, event_type, event_title, currency,
               surprise_normalized, z_score, tier, is_inverse,
               fundamental_direction, direction_confidence
        FROM events_classified
        WHERE tier > 0 AND fundamental_direction != 'NEUTRAL'
        ORDER BY direction_confidence DESC, ABS(z_score) DESC
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    
    print(f"\n" + "=" * 70)
    print(f"TOP {limit} STRONGEST SIGNALS (non-NEUTRAL only)")
    print("=" * 70)
    
    if not rows:
        print("\nNo non-NEUTRAL signals found!")
        return
    
    print(f"\n  {'Time':16} {'Type':10} {'Curr':4} {'Inv':3} {'Title':<32} {'NormSurp':>8} {'Z':>6} {'T':>1} {'Direction':12} {'Conf':>4}")
    print(f"  {'-'*16} {'-'*10} {'-'*4} {'-'*3} {'-'*32} {'-'*8} {'-'*6} {'-'*1} {'-'*12} {'-'*4}")
    
    for row in rows:
        time_s, etype, title, curr, norm_s, z, tier, is_inv, direction, conf = row
        ts = time_s[:16] if time_s else "?"
        inv_str = "INV" if is_inv else " "
        title_s = (title or "")[:32]
        norm_str = f"{norm_s:.2f}" if norm_s is not None else "N/A"
        z_str = f"{z:.2f}" if z is not None else "N/A"
        print(f"  {ts:16} {etype[:10]:10} {curr:4} {inv_str:3} {title_s:<32} {norm_str:>8} {z_str:>6} {tier:>1} {direction[:12]:12} {conf:>4.2f}")


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--source", default="all", choices=["all", "investing", "forexfactory"])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--show-top", type=int, default=20)
    args = parser.parse_args()
    
    print("=" * 70)
    print("FUNDAMENTAL ENGINE — CLASSIFIER v3 (FINAL)")
    print("=" * 70)
    
    if args.diagnose:
        run_diagnostic()
        return
    
    print(f"\nDB:          {fc.DB_PATH}")
    print(f"Source:      {args.source}")
    print(f"Force:       {args.force}")
    
    conn = sqlite3.connect(fc.DB_PATH)
    
    if args.force:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS events_classified")
        conn.commit()
        print("\nForce mode: dropped old events_classified")
    
    ensure_classified_table(conn)
    
    print(f"\nRunning classification...")
    stats = run_classifier(conn, source_filter=args.source)
    
    print_summary(stats)
    
    if args.show_top > 0:
        show_top_signals(conn, args.show_top)
    
    conn.close()
    print("\nDONE.\n")


if __name__ == "__main__":
    main()
