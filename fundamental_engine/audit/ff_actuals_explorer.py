"""
ForexFactory Actuals Source Explorer
=====================================
Tests multiple ForexFactory JSON URL variants to find one that returns
events WITH 'actual' values (post-release data).

The standard ff_calendar_thisweek.json provides upcoming events only
(no actuals). We need a different source for historical/released data.

Usage:
  python C:\\QGAI\\fundamental_engine\\audit\\ff_actuals_explorer.py

Output:
  - Console: which URLs work, which return actuals
  - File: ff_url_test_results.json with detailed findings
"""

import sys
import os
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta

# ============================================================
# PATH SETUP
# ============================================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc

# ============================================================
# OUTPUT PATH
# ============================================================
OUTPUT_FILE = os.path.join(fc.AUDIT_OUTPUT_DIR, "ff_url_test_results.json")
os.makedirs(fc.AUDIT_OUTPUT_DIR, exist_ok=True)

# ============================================================
# URL VARIANTS TO TEST
# ============================================================
URL_CANDIDATES = [
    # Standard variants (probably most likely to work)
    {
        "name": "thisweek (current)",
        "url": "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        "note": "Current week — already used, no actuals"
    },
    {
        "name": "lastweek",
        "url": "https://nfs.faireconomy.media/ff_calendar_lastweek.json",
        "note": "Last week — may have actuals (past events)"
    },
    {
        "name": "nextweek",
        "url": "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
        "note": "Next week — upcoming events"
    },
    {
        "name": "general calendar",
        "url": "https://nfs.faireconomy.media/ff_calendar.json",
        "note": "General feed without week suffix"
    },
    {
        "name": "ff_calendar_today",
        "url": "https://nfs.faireconomy.media/ff_calendar_today.json",
        "note": "Today's events"
    },
    {
        "name": "ff_calendar_yesterday",
        "url": "https://nfs.faireconomy.media/ff_calendar_yesterday.json",
        "note": "Yesterday's events — should have actuals"
    },
    # Alternative formats
    {
        "name": "lastweek_xml",
        "url": "https://nfs.faireconomy.media/ff_calendar_lastweek.xml",
        "note": "XML version of last week"
    },
    # ForexFactory's main domain
    {
        "name": "ff main weekly",
        "url": "https://www.forexfactory.com/ffcal_week_this.xml",
        "note": "Main FF site weekly XML"
    },
    {
        "name": "ff main last week",
        "url": "https://www.forexfactory.com/ffcal_week_last.xml",
        "note": "Main FF site last week XML"
    },
]


# ============================================================
# TEST FUNCTION
# ============================================================
def test_url(url_info: dict) -> dict:
    """Test a URL and analyze response."""
    result = {
        "name": url_info["name"],
        "url": url_info["url"],
        "note": url_info["note"],
        "accessible": False,
        "status_code": None,
        "content_type": None,
        "is_json": False,
        "is_xml": False,
        "event_count": 0,
        "has_actual_field": False,
        "events_with_actual": 0,
        "fields_found": [],
        "sample_event": None,
        "error": None,
    }
    
    headers = {
        "User-Agent": fc.HTTP_USER_AGENT,
        "Accept": "application/json, application/xml, */*"
    }
    
    try:
        response = requests.get(url_info["url"], headers=headers, timeout=15)
        result["status_code"] = response.status_code
        result["content_type"] = response.headers.get("Content-Type", "unknown")
        
        if response.status_code != 200:
            result["error"] = f"HTTP {response.status_code}"
            return result
        
        result["accessible"] = True
        
        # Try JSON first
        try:
            data = response.json()
            result["is_json"] = True
            
            if isinstance(data, list) and len(data) > 0:
                result["event_count"] = len(data)
                
                # Inspect first event for fields
                first = data[0]
                if isinstance(first, dict):
                    result["fields_found"] = list(first.keys())
                    result["sample_event"] = first
                    
                    # Check for 'actual' field anywhere
                    actual_field_names = ["actual", "actualValue", "actual_value", "result"]
                    for field in actual_field_names:
                        if field in first:
                            result["has_actual_field"] = True
                            # Count events with non-empty actual
                            count = sum(
                                1 for ev in data
                                if isinstance(ev, dict) and 
                                ev.get(field) and 
                                str(ev[field]).strip() not in ["", "N/A", "null"]
                            )
                            result["events_with_actual"] = count
                            break
            
            return result
        
        except json.JSONDecodeError:
            pass
        
        # Try XML detection
        if "xml" in result["content_type"].lower() or response.text.strip().startswith("<?xml"):
            result["is_xml"] = True
            # Quick XML field check
            text = response.text[:5000]  # First 5KB
            
            # Common FF XML field names
            xml_actual_indicators = ["<actual>", "<actualValue>", 'actual="', '"actual"']
            for indicator in xml_actual_indicators:
                if indicator in text:
                    result["has_actual_field"] = True
                    break
            
            # Count event tags
            event_tag_candidates = ["<event>", "<item>", "<calendar>"]
            for tag in event_tag_candidates:
                count = text.count(tag)
                if count > 0:
                    result["event_count"] = count
                    break
            
            result["sample_event"] = response.text[:500] + "..." if len(response.text) > 500 else response.text
            
            return result
        
        # Neither JSON nor XML
        result["error"] = "Unknown content format"
        result["sample_event"] = response.text[:500]
        return result
    
    except requests.exceptions.Timeout:
        result["error"] = "Timeout"
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)
    
    return result


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 70)
    print("FOREXFACTORY ACTUALS SOURCE EXPLORER")
    print("=" * 70)
    print(f"\nTesting {len(URL_CANDIDATES)} URL variants...\n")
    
    results = []
    
    for url_info in URL_CANDIDATES:
        print(f"Testing: {url_info['name']:25}", end=" ", flush=True)
        result = test_url(url_info)
        results.append(result)
        
        # Quick status line
        if not result["accessible"]:
            print(f"[X] {result['error']}")
        elif result["has_actual_field"]:
            print(f"[OK]  events={result['event_count']}, with_actuals={result['events_with_actual']}")
        elif result["is_json"]:
            print(f"[OK]  events={result['event_count']}, NO actual field")
        elif result["is_xml"]:
            actual_in_xml = "WITH actual" if result["has_actual_field"] else "NO actual"
            print(f"[OK]  XML format, {actual_in_xml}")
        else:
            print(f"[?]  Unknown format")
    
    # Save full results
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            "test_date": datetime.now().isoformat(),
            "url_count": len(URL_CANDIDATES),
            "results": results,
        }, f, indent=2, default=str)
    
    # ============================================================
    # SUMMARY & RECOMMENDATIONS
    # ============================================================
    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)
    
    # Find best sources
    sources_with_actuals = [
        r for r in results 
        if r["accessible"] and r["has_actual_field"] and r["events_with_actual"] > 0
    ]
    sources_accessible = [r for r in results if r["accessible"]]
    
    print(f"\nAccessible URLs:              {len(sources_accessible)}/{len(results)}")
    print(f"With 'actual' field:          {sum(1 for r in results if r['has_actual_field'])}")
    print(f"With released actual values:  {len(sources_with_actuals)}")
    
    if sources_with_actuals:
        print("\n>>> RECOMMENDED SOURCES (have actuals):")
        for src in sources_with_actuals:
            print(f"\n  Name:        {src['name']}")
            print(f"  URL:         {src['url']}")
            print(f"  Format:      {'JSON' if src['is_json'] else 'XML'}")
            print(f"  Events:      {src['event_count']}")
            print(f"  With actual: {src['events_with_actual']}")
            print(f"  Fields:      {src['fields_found']}")
    else:
        print("\n>>> NO URL provides actuals directly.")
        print("    Need fallback strategy:")
        print("    1. Web scrape ForexFactory's HTML calendar pages")
        print("    2. Use alternative source (Investing.com, TradingEconomics)")
        print("    3. Manually capture actuals from ff_calendar_thisweek.json")
        print("       after events are released (re-fetch later in week)")
    
    print(f"\nFull results saved: {OUTPUT_FILE}")
    print("\nDONE.\n")


if __name__ == "__main__":
    main()
