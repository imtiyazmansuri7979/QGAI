"""
ForexFactory Calendar Audit Utility
====================================
Purpose: Extract list of available economic events from ForexFactory
         (Used because MT5 library doesn't expose calendar API)

Output: 
  - C:\\QGAI\\fundamental_engine\\audit\\audit_outputs\\ff_calendar_audit.csv
  - C:\\QGAI\\fundamental_engine\\audit\\audit_outputs\\ff_calendar_audit.json

Requirements:
  pip install requests pandas

Source: https://nfs.faireconomy.media/ff_calendar_thisweek.json
        (Public JSON feed, free, no API key needed)

NOTE: This fetches THIS WEEK's events. For historical, separate process needed.
      This audit purpose: discover event names + structure used by ForexFactory.
"""

import requests
import pandas as pd
import json
import os
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
OUTPUT_DIR = r"C:\QGAI\fundamental_engine\audit\audit_outputs"
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Impact levels in ForexFactory:
# "High" = 3-star (red folder)
# "Medium" = 2-star (orange folder)
# "Low" = 1-star (yellow folder)
# "Non-Economic" = 0-star (gray)
TARGET_IMPACTS = ["High", "Medium"]   # 2-star and 3-star only

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# STEP 1: Fetch ForexFactory JSON
# ============================================================
print("=" * 60)
print("FOREXFACTORY CALENDAR AUDIT")
print("=" * 60)

print(f"\nFetching: {FF_URL}")

try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(FF_URL, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    print(f"OK Fetched {len(data)} events for current week")
except requests.exceptions.RequestException as e:
    print(f"X Network error: {e}")
    print("  Check internet connection and firewall settings.")
    quit()
except json.JSONDecodeError as e:
    print(f"X JSON parse error: {e}")
    print("  ForexFactory may have changed format. Visit URL manually to verify.")
    quit()
except Exception as e:
    print(f"X Unexpected error: {e}")
    quit()

# ============================================================
# STEP 2: Convert to DataFrame
# ============================================================
df = pd.DataFrame(data)

# Expected fields in FF JSON:
# title, country, date, impact, forecast, previous, actual (when released)
print(f"\nFields in response: {df.columns.tolist()}")
print(f"\nSample event:")
if len(df) > 0:
    print(df.iloc[0].to_dict())

# ============================================================
# STEP 3: Filter by impact (2-star + 3-star)
# ============================================================
if 'impact' in df.columns:
    df_filtered = df[df['impact'].isin(TARGET_IMPACTS)].copy()
else:
    print("X 'impact' field not found in response. Schema changed?")
    df_filtered = df.copy()

print(f"\nFiltered to {TARGET_IMPACTS}: {len(df_filtered)} events this week")

# ============================================================
# STEP 4: Extract unique events
# ============================================================
print("\nExtracting unique events...")

# Build unique event inventory
unique_events = []

if 'title' in df_filtered.columns and 'country' in df_filtered.columns:
    grouped = df_filtered.groupby(['title', 'country', 'impact'])
    
    for (title, country, impact), group in grouped:
        unique_events.append({
            'event_name': title,
            'currency': country,           # FF uses 'country' for currency
            'impact': impact,
            'impact_stars': 3 if impact == 'High' else 2,
            'occurrences_this_week': len(group),
            'has_forecast': bool(group['forecast'].notna().any()) if 'forecast' in group.columns else False,
            'has_previous': bool(group['previous'].notna().any()) if 'previous' in group.columns else False,
            'has_actual': bool(group['actual'].notna().any()) if 'actual' in group.columns else False,
        })

inventory_df = pd.DataFrame(unique_events)

if len(inventory_df) > 0:
    inventory_df = inventory_df.sort_values(
        ['currency', 'impact_stars', 'event_name'],
        ascending=[True, False, True]
    )

# ============================================================
# STEP 5: Save outputs
# ============================================================
csv_path = os.path.join(OUTPUT_DIR, 'ff_calendar_audit.csv')
json_path = os.path.join(OUTPUT_DIR, 'ff_calendar_audit.json')

inventory_df.to_csv(csv_path, index=False)

with open(json_path, 'w', encoding='utf-8') as f:
    json.dump({
        'audit_date': datetime.now().isoformat(),
        'source': 'forexfactory.com',
        'source_url': FF_URL,
        'week_events_fetched': len(df),
        'filtered_events_2star_plus': len(df_filtered),
        'unique_events': len(inventory_df),
        'currencies_found': sorted(inventory_df['currency'].unique().tolist()) if len(inventory_df) > 0 else [],
        'all_events_raw': data,           # Keep raw data for reference
        'unique_event_inventory': unique_events
    }, f, indent=2, default=str, ensure_ascii=False)

# ============================================================
# STEP 6: Summary
# ============================================================
print("\n" + "=" * 60)
print("AUDIT SUMMARY")
print("=" * 60)
print(f"Source:                     ForexFactory")
print(f"Total events this week:     {len(df)}")
print(f"2-star + 3-star events:     {len(df_filtered)}")
print(f"Unique event types:         {len(inventory_df)}")

if len(inventory_df) > 0:
    print(f"Currencies found:           {', '.join(sorted(inventory_df['currency'].unique()))}")
    
    print("\nUnique events per currency:")
    print(inventory_df.groupby('currency').size().to_string())
    
    print("\nEvents per impact tier:")
    print(inventory_df.groupby('impact_stars').size().to_string())
    
    print("\nSample of 3-star events:")
    three_star = inventory_df[inventory_df['impact_stars'] == 3].head(10)
    if len(three_star) > 0:
        print(three_star[['event_name', 'currency']].to_string(index=False))

print(f"\nOutput files:")
print(f"   CSV:  {csv_path}")
print(f"   JSON: {json_path}")
print("\nDONE. Share output files for next step (gold_events.json build).\n")
