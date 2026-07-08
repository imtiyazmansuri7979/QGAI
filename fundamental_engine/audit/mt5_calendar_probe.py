"""
MT5 Calendar Comprehensive Probe
================================
Thorough test of MetaTrader5 Python API economic calendar capabilities.

Tests:
  1. Library version and capabilities
  2. All known calendar function names
  3. Live function calls with sample params
  4. Broker support for calendar data
  5. Suggests workaround based on findings

Usage:
  python C:\\QGAI\\fundamental_engine\\audit\\mt5_calendar_probe.py
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc

OUTPUT_FILE = os.path.join(fc.AUDIT_OUTPUT_DIR, "mt5_calendar_probe.json")
os.makedirs(fc.AUDIT_OUTPUT_DIR, exist_ok=True)


def main():
    print("=" * 70)
    print("MT5 CALENDAR COMPREHENSIVE PROBE")
    print("=" * 70)
    
    results = {
        "test_date": datetime.now().isoformat(),
        "tests": {},
    }
    
    # ============================================================
    # TEST 1: Library version
    # ============================================================
    print("\n[1] Library version check")
    print("-" * 70)
    
    try:
        import MetaTrader5 as mt5
        version = getattr(mt5, "__version__", "unknown")
        author = getattr(mt5, "__author__", "unknown")
        print(f"   MetaTrader5 module: imported OK")
        print(f"   Version:            {version}")
        print(f"   Author:             {author}")
        results["tests"]["import"] = {"success": True, "version": str(version)}
    except ImportError as e:
        print(f"   X MetaTrader5 not installed: {e}")
        results["tests"]["import"] = {"success": False, "error": str(e)}
        save_results(results)
        return
    
    # ============================================================
    # TEST 2: Initialize MT5 connection
    # ============================================================
    print("\n[2] MT5 connection")
    print("-" * 70)
    
    if not mt5.initialize():
        err = mt5.last_error()
        print(f"   X MT5 initialization failed: {err}")
        print(f"   Make sure MT5 terminal is running and logged in")
        results["tests"]["initialize"] = {"success": False, "error": str(err)}
        save_results(results)
        return
    
    print(f"   OK MT5 initialized")
    
    # Account info
    account = mt5.account_info()
    if account:
        print(f"   Broker:             {account.company}")
        print(f"   Account:            {account.login}")
        print(f"   Server:             {account.server}")
        print(f"   Currency:           {account.currency}")
        results["tests"]["initialize"] = {
            "success": True,
            "broker": account.company,
            "server": account.server,
            "account": account.login,
        }
    
    # Terminal info
    terminal = mt5.terminal_info()
    if terminal:
        print(f"   Terminal version:   {terminal.build}")
        print(f"   Terminal path:      {terminal.path}")
        results["tests"]["terminal"] = {
            "build": terminal.build,
            "path": terminal.path,
        }
    
    # ============================================================
    # TEST 3: Calendar functions discovery
    # ============================================================
    print("\n[3] Calendar functions discovery")
    print("-" * 70)
    
    all_attrs = dir(mt5)
    calendar_attrs = [a for a in all_attrs if 'calendar' in a.lower()]
    
    print(f"   Total mt5 attributes: {len(all_attrs)}")
    print(f"   Calendar-related:     {len(calendar_attrs)}")
    
    if calendar_attrs:
        for attr in calendar_attrs:
            print(f"      - {attr}")
    else:
        print(f"   X No calendar attributes in dir(mt5)")
    
    # Try known calendar function names (even if not in dir())
    KNOWN_CALENDAR_FUNCS = [
        "calendar_value_history",
        "calendar_value_history_by_event",
        "calendar_value_by_id",
        "calendar_value_last",
        "calendar_value_search",
        "calendar_event_by_id",
        "calendar_event_by_currency",
        "calendar_event_by_country",
        "calendar_news",
        "economic_calendar",
    ]
    
    print(f"\n   Checking known function names (via getattr):")
    available_funcs = []
    
    for func_name in KNOWN_CALENDAR_FUNCS:
        func = getattr(mt5, func_name, None)
        if func is not None and callable(func):
            print(f"      [OK] {func_name}: callable")
            available_funcs.append(func_name)
        else:
            print(f"      [--] {func_name}: not available")
    
    results["tests"]["calendar_functions"] = {
        "in_dir": calendar_attrs,
        "available_via_getattr": available_funcs,
    }
    
    # ============================================================
    # TEST 4: Try calling calendar functions
    # ============================================================
    if available_funcs:
        print("\n[4] Live calendar function calls")
        print("-" * 70)
        
        # Date range: last 7 days
        date_from = datetime.now() - timedelta(days=7)
        date_to = datetime.now()
        
        # Try calendar_value_history (most common)
        if "calendar_value_history" in available_funcs:
            print(f"\n   Testing: calendar_value_history({date_from.date()}, {date_to.date()})")
            try:
                events = mt5.calendar_value_history(date_from, date_to)
                if events is None:
                    err = mt5.last_error()
                    print(f"      X Returned None — error: {err}")
                    results["tests"]["calendar_value_history"] = {
                        "success": False,
                        "error": str(err),
                    }
                elif len(events) == 0:
                    print(f"      X Returned empty (broker doesn't provide calendar data)")
                    results["tests"]["calendar_value_history"] = {
                        "success": False,
                        "result": "empty",
                    }
                else:
                    print(f"      [OK] Got {len(events)} events!")
                    print(f"      Sample event:")
                    sample = events[0]
                    for attr in dir(sample):
                        if not attr.startswith("_"):
                            try:
                                val = getattr(sample, attr)
                                if not callable(val):
                                    print(f"         {attr}: {val}")
                            except:
                                pass
                    results["tests"]["calendar_value_history"] = {
                        "success": True,
                        "count": len(events),
                        "sample_attrs": [a for a in dir(sample) if not a.startswith("_")],
                    }
            except Exception as e:
                print(f"      X Exception: {e}")
                results["tests"]["calendar_value_history"] = {
                    "success": False,
                    "error": str(e),
                }
        
        # Try calendar_value_search
        if "calendar_value_search" in available_funcs:
            print(f"\n   Testing: calendar_value_search()")
            try:
                events = mt5.calendar_value_search()
                if events:
                    print(f"      [OK] Got {len(events)} events")
                    results["tests"]["calendar_value_search"] = {"success": True, "count": len(events)}
                else:
                    print(f"      X Returned empty/None")
                    results["tests"]["calendar_value_search"] = {"success": False}
            except Exception as e:
                print(f"      X Exception: {e}")
                results["tests"]["calendar_value_search"] = {"success": False, "error": str(e)}
    
    else:
        print("\n[4] SKIPPED — no calendar functions available to call")
    
    # ============================================================
    # TEST 5: Symbol info as alternative path
    # ============================================================
    print("\n[5] Alternative MT5 data sources")
    print("-" * 70)
    
    symbols = mt5.symbols_total()
    print(f"   Available symbols:    {symbols}")
    
    # Check if there's a news endpoint via terminal
    terminal_info = mt5.terminal_info()
    if terminal_info:
        attrs = [a for a in dir(terminal_info) if 'news' in a.lower() or 'calendar' in a.lower()]
        if attrs:
            print(f"   Terminal news/cal attrs: {attrs}")
        else:
            print(f"   No news/calendar attrs in terminal_info")
    
    # Shutdown
    mt5.shutdown()
    
    # ============================================================
    # ANALYSIS & RECOMMENDATION
    # ============================================================
    print("\n" + "=" * 70)
    print("ANALYSIS & RECOMMENDATION")
    print("=" * 70)
    
    cal_test = results["tests"].get("calendar_value_history", {})
    
    if cal_test.get("success") and cal_test.get("count", 0) > 0:
        print(f"\n[SUCCESS] MT5 broker provides calendar data!")
        print(f"   Got {cal_test['count']} events for last 7 days")
        print(f"   Available fields: {cal_test.get('sample_attrs', [])}")
        print(f"\n   NEXT STEP: Build MT5 calendar scraper")
    
    elif available_funcs:
        print(f"\n[PARTIAL] MT5 library has calendar functions but broker returns empty")
        print(f"   Broker:  {results['tests']['initialize'].get('broker', 'unknown')}")
        print(f"   This means Vantage Markets doesn't share calendar data feed")
        print(f"\n   WORKAROUND OPTIONS:")
        print(f"   1. Create free MetaQuotes demo account (provides full calendar)")
        print(f"      - Go to: https://www.metaquotes.net/")
        print(f"      - Download MT5 from MetaQuotes (not from broker)")
        print(f"      - Sign up for free demo with MetaQuotes-Demo server")
        print(f"      - Use ONLY for calendar data (keep Vantage for trading)")
        print(f"   2. Try brokers known to provide calendar:")
        print(f"      - IC Markets, Pepperstone, FXCM, OANDA demo")
    
    else:
        print(f"\n[BLOCKED] MT5 library doesn't have calendar functions in this version")
        print(f"   Version: {results['tests']['import'].get('version', '?')}")
        print(f"\n   ACTIONS:")
        print(f"   1. Upgrade MetaTrader5 library:")
        print(f"      pip install --upgrade MetaTrader5")
        print(f"   2. If still missing, library doesn't support calendar")
    
    save_results(results)
    print(f"\nResults saved: {OUTPUT_FILE}")
    print("\nDONE.\n")


def save_results(results):
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)


if __name__ == "__main__":
    main()
