"""
MT5 Calendar Audit Utility
==========================
Purpose: Extract list of available economic events from MT5 calendar
Output: 
  - C:\\QGAI\\fundamental_engine\\audit\\audit_outputs\\mt5_calendar_audit.csv
  - C:\\QGAI\\fundamental_engine\\audit\\audit_outputs\\mt5_calendar_audit.json

One-time run utility. NOT part of engine.

Requirements:
  pip install MetaTrader5 pandas
  pip install --upgrade MetaTrader5

Usage:
  1. Open MT5 platform, login to broker
  2. Run: python C:\\QGAI\\fundamental_engine\\audit\\mt5_audit.py
  3. Share output files for analysis
"""

import MetaTrader5 as mt5
import pandas as pd
import json
import os
from datetime import datetime, timedelta

# ============================================================
# CONFIG
# ============================================================
OUTPUT_DIR = r"C:\QGAI\fundamental_engine\audit\audit_outputs"
LOOKBACK_DAYS = 365      # 12 months audit
MIN_IMPORTANCE = 2       # 2-star and above (filters out 0-star and 1-star)

# Ensure output dir exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# STEP 1: Initialize MT5
# ============================================================
print("=" * 60)
print("MT5 CALENDAR AUDIT")
print("=" * 60)

if not mt5.initialize():
    print(f"X MT5 init failed: {mt5.last_error()}")
    print("  Fix: Open MT5 platform and login first.")
    quit()

acc = mt5.account_info()
print(f"OK MT5 connected")
if acc:
    print(f"   Account: {acc.login}")
    print(f"   Server:  {acc.server}")
    print(f"   Company: {acc.company}")

# ============================================================
# STEP 2: Fetch calendar history
# ============================================================
end_date = datetime.now()
start_date = end_date - timedelta(days=LOOKBACK_DAYS)

print(f"\nFetching calendar: {start_date.date()} -> {end_date.date()}")

try:
    events = mt5.calendar_value_history(start_date, end_date)
except AttributeError:
    print("X Your MetaTrader5 library doesn't support calendar API.")
    print("  Fix: pip install --upgrade MetaTrader5")
    mt5.shutdown()
    quit()
except Exception as e:
    print(f"X Calendar fetch error: {e}")
    mt5.shutdown()
    quit()

if events is None or len(events) == 0:
    print("X No calendar events returned.")
    print("  Possible cause: Broker doesn't expose calendar API.")
    print(f"  MT5 error: {mt5.last_error()}")
    mt5.shutdown()
    quit()

print(f"OK Fetched {len(events)} event records (all importances)")

# ============================================================
# STEP 3: Convert to DataFrame
# ============================================================
df = pd.DataFrame(events)

# Common MT5 calendar fields:
# event_id, time, currency, importance, actual_value, forecast_value, prev_value
if 'time' in df.columns:
    df['time'] = pd.to_datetime(df['time'], unit='s')

# ============================================================
# STEP 4: Filter 2-star + 3-star
# ============================================================
df_filtered = df[df['importance'] >= MIN_IMPORTANCE].copy()
print(f"Filtered to 2-star + 3-star events: {len(df_filtered)} records")

# ============================================================
# STEP 5: Fetch event metadata
# ============================================================
print("\nFetching event names + metadata...")

event_meta = {}
unique_event_ids = df_filtered['event_id'].unique() if 'event_id' in df_filtered.columns else []

for idx, event_id in enumerate(unique_event_ids):
    try:
        info = mt5.calendar_event_by_id(int(event_id))
        if info:
            event_meta[event_id] = {
                'name': getattr(info, 'name', 'Unknown'),
                'currency': getattr(info, 'currency', 'Unknown'),
                'importance': getattr(info, 'importance', 0),
                'frequency': getattr(info, 'frequency', 0),
                'unit': getattr(info, 'unit', '')
            }
    except Exception:
        # Silent fail for individual events
        pass
    
    if (idx + 1) % 50 == 0:
        print(f"   Processed {idx+1}/{len(unique_event_ids)} unique events...")

print(f"OK Resolved metadata for {len(event_meta)} unique events")

# ============================================================
# STEP 6: Build inventory
# ============================================================
inventory = []

for event_id, meta in event_meta.items():
    records = df_filtered[df_filtered['event_id'] == event_id]
    
    actual_col = 'actual_value' if 'actual_value' in records.columns else None
    forecast_col = 'forecast_value' if 'forecast_value' in records.columns else None
    prev_col = 'prev_value' if 'prev_value' in records.columns else None
    
    inventory.append({
        'event_id': int(event_id),
        'event_name': meta['name'],
        'currency': meta['currency'],
        'importance': meta['importance'],
        'frequency': meta['frequency'],
        'unit': meta['unit'],
        'records_count_12mo': len(records),
        'first_occurrence': str(records['time'].min()) if 'time' in records.columns and len(records) > 0 else None,
        'last_occurrence': str(records['time'].max()) if 'time' in records.columns and len(records) > 0 else None,
        'has_actual_data': bool(records[actual_col].notna().any()) if actual_col else False,
        'has_forecast_data': bool(records[forecast_col].notna().any()) if forecast_col else False,
        'has_previous_data': bool(records[prev_col].notna().any()) if prev_col else False,
    })

inventory_df = pd.DataFrame(inventory)

if len(inventory_df) > 0:
    inventory_df = inventory_df.sort_values(
        ['currency', 'importance', 'event_name'],
        ascending=[True, False, True]
    )

# ============================================================
# STEP 7: Save outputs
# ============================================================
csv_path = os.path.join(OUTPUT_DIR, 'mt5_calendar_audit.csv')
json_path = os.path.join(OUTPUT_DIR, 'mt5_calendar_audit.json')

inventory_df.to_csv(csv_path, index=False)

with open(json_path, 'w', encoding='utf-8') as f:
    json.dump({
        'audit_date': datetime.now().isoformat(),
        'broker_company': acc.company if acc else 'N/A',
        'broker_server': acc.server if acc else 'N/A',
        'lookback_days': LOOKBACK_DAYS,
        'total_records_fetched': len(df),
        'total_records_2star_plus': len(df_filtered),
        'total_unique_events': len(inventory),
        'currencies_found': sorted(inventory_df['currency'].unique().tolist()) if len(inventory_df) > 0 else [],
        'events': inventory
    }, f, indent=2, default=str, ensure_ascii=False)

# ============================================================
# STEP 8: Summary
# ============================================================
print("\n" + "=" * 60)
print("AUDIT SUMMARY")
print("=" * 60)
print(f"Broker:                {acc.company if acc else 'N/A'}")
print(f"Total records fetched: {len(df)}")
print(f"2-star+ records:       {len(df_filtered)}")
print(f"Unique events:         {len(inventory)}")

if len(inventory_df) > 0:
    print(f"Currencies found:      {', '.join(sorted(inventory_df['currency'].unique()))}")
    
    print("\nEvents per currency:")
    print(inventory_df.groupby('currency').size().to_string())
    
    print("\nEvents per impact tier:")
    print(inventory_df.groupby('importance').size().to_string())

print(f"\nOutput files:")
print(f"   CSV:  {csv_path}")
print(f"   JSON: {json_path}")

mt5.shutdown()
print("\nDONE. Share output files for next step.\n")
