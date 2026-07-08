"""
Investing.com Data Analyzer
============================
Deep analysis of events_investing_raw table.
Helps decide if existing data is good enough OR need to refetch.

Checks:
  - 3-star events: which captured, which missing?
  - Major events coverage (FOMC, NFP, CPI, ECB, etc.)
  - Date range coverage / gaps
  - Currency-specific event lists
  - Sample events with values
  - Data quality (actuals presence)

Usage:
  python C:\\QGAI\\fundamental_engine\\core\\investing_data_analyzer.py
"""

import sys
import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter

# ============================================================
# PATH SETUP
# ============================================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc

# Output file
OUTPUT_FILE = os.path.join(fc.AUDIT_OUTPUT_DIR, "investing_data_analysis.json")
os.makedirs(fc.AUDIT_OUTPUT_DIR, exist_ok=True)

# Gold-relevant currencies
GOLD_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CNY", "CAD", "AUD", "NZD", "CHF"]

# Key events to check (by currency)
EXPECTED_EVENTS = {
    "USD": {
        "FOMC": ["Fed Interest Rate Decision", "Federal Funds Rate", "FOMC Statement", "FOMC Press Conference", "Interest Rate Decision"],
        "NFP": ["Nonfarm Payrolls", "Non-Farm Employment Change", "Change in Nonfarm Payrolls"],
        "CPI": ["Core CPI (YoY)", "CPI (YoY)", "Core CPI (MoM)", "CPI (MoM)", "Consumer Price Index"],
        "PPI": ["Core PPI (YoY)", "PPI (YoY)", "Core PPI (MoM)", "PPI (MoM)"],
        "GDP": ["GDP (QoQ)", "Gross Domestic Product"],
        "Unemployment": ["Unemployment Rate", "Initial Jobless Claims"],
    },
    "EUR": {
        "ECB Rate": ["Deposit Facility Rate", "Main Refinancing Rate", "Interest Rate Decision", "ECB Marginal Lending Facility"],
        "ECB Press": ["ECB Press Conference", "ECB Monetary Policy Statement"],
        "Eurozone CPI": ["Core CPI (YoY)", "CPI (YoY)", "Eurozone CPI"],
        "Eurozone GDP": ["GDP (QoQ)", "Eurozone GDP"],
        "German CPI": ["German CPI", "German Harmonized CPI"],
    },
    "GBP": {
        "BoE Rate": ["BoE Interest Rate Decision", "Bank of England Rate Decision", "Interest Rate Decision"],
        "UK CPI": ["CPI (YoY)", "Core CPI (YoY)", "UK CPI"],
        "UK GDP": ["GDP (QoQ)", "GDP (MoM)"],
    },
    "JPY": {
        "BoJ Rate": ["BoJ Interest Rate Decision", "Bank of Japan Rate Decision", "Interest Rate Decision"],
        "Japan CPI": ["National CPI (YoY)", "Tokyo CPI", "Japan CPI"],
    },
    "CNY": {
        "China CPI": ["Chinese CPI (YoY)", "CPI (YoY)"],
        "China GDP": ["Chinese GDP (YoY)", "GDP (YoY)"],
        "China PMI": ["Manufacturing PMI", "Caixin Manufacturing PMI"],
    },
}


# ============================================================
# ANALYSIS FUNCTIONS
# ============================================================
def get_overview(conn):
    """High-level statistics."""
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM events_investing_raw")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT MIN(release_time), MAX(release_time) FROM events_investing_raw")
    date_range = cursor.fetchone()
    
    cursor.execute("""
        SELECT COUNT(*) FROM events_investing_raw
        WHERE actual IS NOT NULL AND actual != ''
    """)
    with_actual = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT impact_stars, COUNT(*) 
        FROM events_investing_raw 
        GROUP BY impact_stars 
        ORDER BY impact_stars DESC
    """)
    by_stars = dict(cursor.fetchall())
    
    return {
        "total": total,
        "with_actual": with_actual,
        "actual_pct": (with_actual / total * 100) if total > 0 else 0,
        "date_range": date_range,
        "by_stars": by_stars,
    }


def get_currency_breakdown(conn, gold_only=False):
    """Events per currency, with star breakdown."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT currency, impact_stars, COUNT(*) 
        FROM events_investing_raw 
        GROUP BY currency, impact_stars
        ORDER BY currency, impact_stars DESC
    """)
    
    breakdown = defaultdict(lambda: {"3": 0, "2": 0, "1": 0, "0": 0, "total": 0})
    
    for currency, stars, count in cursor.fetchall():
        if gold_only and currency not in GOLD_CURRENCIES:
            continue
        breakdown[currency][str(stars)] = count
        breakdown[currency]["total"] += count
    
    return dict(breakdown)


def get_3star_events_by_currency(conn):
    """Detailed 3-star events grouped by currency."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT currency, event_title, COUNT(*), 
               MIN(release_time), MAX(release_time)
        FROM events_investing_raw 
        WHERE impact_stars = 3
        GROUP BY currency, event_title
        ORDER BY currency, COUNT(*) DESC
    """)
    
    result = defaultdict(list)
    for currency, title, count, min_t, max_t in cursor.fetchall():
        result[currency].append({
            "event": title,
            "count": count,
            "first_seen": min_t,
            "last_seen": max_t,
        })
    
    return dict(result)


def check_expected_events_coverage(conn):
    """Check if expected major events are in data."""
    cursor = conn.cursor()
    coverage = {}
    
    for currency, event_groups in EXPECTED_EVENTS.items():
        coverage[currency] = {}
        
        for group_name, possible_names in event_groups.items():
            found_events = []
            
            for name in possible_names:
                cursor.execute("""
                    SELECT event_title, COUNT(*) 
                    FROM events_investing_raw 
                    WHERE currency = ? AND event_title LIKE ?
                    GROUP BY event_title
                """, (currency, f"%{name}%"))
                
                for title, count in cursor.fetchall():
                    found_events.append({"name": title, "count": count})
            
            coverage[currency][group_name] = found_events
    
    return coverage


def monthly_distribution(conn, currency=None):
    """Events per month — find gaps."""
    cursor = conn.cursor()
    
    sql = """
        SELECT 
            substr(release_time, 1, 7) as month,
            COUNT(*) as cnt,
            SUM(CASE WHEN impact_stars = 3 THEN 1 ELSE 0 END) as three_star,
            SUM(CASE WHEN impact_stars = 2 THEN 1 ELSE 0 END) as two_star
        FROM events_investing_raw
    """
    params = []
    
    if currency:
        sql += " WHERE currency = ?"
        params.append(currency)
    
    sql += " GROUP BY month ORDER BY month"
    
    cursor.execute(sql, params)
    return cursor.fetchall()


def get_sample_events_with_actuals(conn, currency, impact_stars, limit=10):
    """Sample events with actual values for sanity check."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT event_title, release_time, actual, forecast, previous
        FROM events_investing_raw
        WHERE currency = ? AND impact_stars = ?
        AND actual IS NOT NULL AND actual != ''
        ORDER BY release_time DESC
        LIMIT ?
    """, (currency, impact_stars, limit))
    
    return cursor.fetchall()


# ============================================================
# OUTPUT
# ============================================================
def print_overview(stats):
    print("=" * 70)
    print("INVESTING.COM DATA ANALYSIS")
    print("=" * 70)
    
    print(f"\nDB: {fc.DB_PATH}")
    print(f"\nTotal events:        {stats['total']}")
    print(f"With actual value:   {stats['with_actual']} ({stats['actual_pct']:.1f}%)")
    
    if stats['date_range'][0]:
        print(f"\nDate range:")
        print(f"  From: {stats['date_range'][0]}")
        print(f"  To:   {stats['date_range'][1]}")
    
    print(f"\nBy impact level:")
    for stars in [3, 2, 1, 0]:
        count = stats['by_stars'].get(stars, 0)
        label = ["Holiday/Other", "1-star", "2-star", "3-star"][stars]
        print(f"  {label:18}        {count}")


def print_currency_breakdown(breakdown, title):
    print(f"\n{'-' * 70}")
    print(f"  {title}")
    print(f"{'-' * 70}")
    print(f"  {'Currency':10}  {'3-star':>8}  {'2-star':>8}  {'1-star':>8}  {'Total':>8}")
    
    total_3 = total_2 = total_1 = total_all = 0
    
    for curr in sorted(breakdown.keys(), key=lambda c: -breakdown[c]["total"]):
        data = breakdown[curr]
        s3 = data["3"]
        s2 = data["2"]
        s1 = data["1"]
        t = data["total"]
        total_3 += s3
        total_2 += s2
        total_1 += s1
        total_all += t
        print(f"  {curr:10}  {s3:>8}  {s2:>8}  {s1:>8}  {t:>8}")
    
    print(f"  {'TOTAL':10}  {total_3:>8}  {total_2:>8}  {total_1:>8}  {total_all:>8}")


def print_3star_events(events_by_currency):
    print(f"\n{'=' * 70}")
    print("  ALL 3-STAR EVENTS BY CURRENCY")
    print(f"{'=' * 70}")
    
    for currency in sorted(events_by_currency.keys()):
        events = events_by_currency[currency]
        print(f"\n  [{currency}]  ({sum(e['count'] for e in events)} total)")
        for ev in events[:30]:  # Limit to top 30 per currency
            print(f"    {ev['count']:>3}x  {ev['event']}")


def print_expected_coverage(coverage):
    print(f"\n{'=' * 70}")
    print("  EXPECTED MAJOR EVENTS COVERAGE CHECK")
    print(f"{'=' * 70}")
    print("  (Verifies if known important events are captured)\n")
    
    for currency, groups in coverage.items():
        print(f"  [{currency}]")
        for group_name, found in groups.items():
            if found:
                total = sum(e["count"] for e in found)
                print(f"    OK  {group_name}: {total} found across {len(found)} variants")
                for ev in found[:3]:  # Show top 3
                    print(f"        - {ev['name']} ({ev['count']}x)")
            else:
                print(f"    XX  {group_name}: NOT FOUND")
        print()


def print_monthly_dist(rows):
    print(f"\n{'=' * 70}")
    print("  MONTHLY DISTRIBUTION (all currencies)")
    print(f"{'=' * 70}")
    print(f"  {'Month':10}  {'Total':>6}  {'3-star':>7}  {'2-star':>7}")
    
    for month, total, three, two in rows:
        print(f"  {month:10}  {total:>6}  {three:>7}  {two:>7}")


def print_samples(conn):
    print(f"\n{'=' * 70}")
    print("  SAMPLE 3-STAR EVENTS WITH ACTUAL VALUES")
    print(f"{'=' * 70}")
    
    for currency in ["USD", "EUR", "GBP", "JPY"]:
        samples = get_sample_events_with_actuals(conn, currency, 3, 5)
        if samples:
            print(f"\n  [{currency}]")
            for title, time, actual, forecast, previous in samples:
                t = time[:16] if time else "?"
                print(f"    {t}  {title:<40}  A:{actual or '-':<10} F:{forecast or '-':<10} P:{previous or '-':<10}")


# ============================================================
# MAIN
# ============================================================
def main():
    print("Opening database:", fc.DB_PATH)
    conn = sqlite3.connect(fc.DB_PATH)
    
    # Check if table exists
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events_investing_raw'")
    if not cursor.fetchone():
        print("X events_investing_raw table not found!")
        return
    
    # 1. Overview
    stats = get_overview(conn)
    print_overview(stats)
    
    # 2. Currency breakdown - All
    all_breakdown = get_currency_breakdown(conn, gold_only=False)
    print_currency_breakdown(all_breakdown, "ALL CURRENCIES BREAKDOWN")
    
    # 3. Currency breakdown - Gold relevant only
    gold_breakdown = get_currency_breakdown(conn, gold_only=True)
    print_currency_breakdown(gold_breakdown, "GOLD-RELEVANT CURRENCIES ONLY")
    
    # 4. 3-star events detail
    three_star_events = get_3star_events_by_currency(conn)
    print_3star_events(three_star_events)
    
    # 5. Expected major events coverage
    coverage = check_expected_events_coverage(conn)
    print_expected_coverage(coverage)
    
    # 6. Monthly distribution
    monthly = monthly_distribution(conn)
    print_monthly_dist(monthly)
    
    # 7. Sample events
    print_samples(conn)
    
    # Save JSON output
    output = {
        "analysis_date": datetime.now().isoformat(),
        "overview": stats,
        "currency_breakdown_all": all_breakdown,
        "currency_breakdown_gold": gold_breakdown,
        "three_star_events": three_star_events,
        "expected_coverage": coverage,
        "monthly_distribution": [
            {"month": m, "total": t, "3-star": s3, "2-star": s2} 
            for m, t, s3, s2 in monthly
        ],
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\nFull analysis saved: {OUTPUT_FILE}")
    
    conn.close()
    print("\nDONE.\n")


if __name__ == "__main__":
    main()
