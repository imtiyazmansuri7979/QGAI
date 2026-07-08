"""
Investing.com Accessibility Test
=================================
Tests if investing.com economic calendar can be accessed via various methods.
Helps decide which scraping approach to use.

Tests:
  1. Plain requests (likely blocked by Cloudflare)
  2. requests with browser headers
  3. cloudscraper (Cloudflare bypass library)
  4. Reports what worked

Run this BEFORE building full scraper to know what's possible.

Usage:
  python C:\\QGAI\\fundamental_engine\\audit\\investing_com_test.py
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================
# CONFIG
# ============================================================
TARGET_URLS = [
    "https://www.investing.com/economic-calendar/",
    "https://br.investing.com/economic-calendar/",
    "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData",
]

# Browser-like headers
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}


# ============================================================
# TEST 1: Plain requests
# ============================================================
def test_plain_requests(url):
    """Try with basic requests library."""
    try:
        import requests
        response = requests.get(url, timeout=15)
        return {
            "method": "plain_requests",
            "status": response.status_code,
            "size_kb": len(response.content) / 1024,
            "has_events": "js-event-item" in response.text or "economic-calendar" in response.text.lower(),
            "blocked_indicators": detect_blocked(response.text),
            "success": response.status_code == 200,
        }
    except Exception as e:
        return {"method": "plain_requests", "success": False, "error": str(e)}


# ============================================================
# TEST 2: requests with browser headers
# ============================================================
def test_browser_headers(url):
    """Try with browser-like headers."""
    try:
        import requests
        response = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
        return {
            "method": "browser_headers",
            "status": response.status_code,
            "size_kb": len(response.content) / 1024,
            "has_events": "js-event-item" in response.text or "economic-calendar" in response.text.lower(),
            "blocked_indicators": detect_blocked(response.text),
            "success": response.status_code == 200,
        }
    except Exception as e:
        return {"method": "browser_headers", "success": False, "error": str(e)}


# ============================================================
# TEST 3: cloudscraper (specialized Cloudflare bypass)
# ============================================================
def test_cloudscraper(url):
    """Try with cloudscraper library."""
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, timeout=20)
        return {
            "method": "cloudscraper",
            "status": response.status_code,
            "size_kb": len(response.content) / 1024,
            "has_events": "js-event-item" in response.text or "economic-calendar" in response.text.lower(),
            "blocked_indicators": detect_blocked(response.text),
            "success": response.status_code == 200,
        }
    except ImportError:
        return {
            "method": "cloudscraper",
            "success": False,
            "error": "cloudscraper not installed (pip install cloudscraper)",
            "install_cmd": "pip install cloudscraper",
        }
    except Exception as e:
        return {"method": "cloudscraper", "success": False, "error": str(e)}


# ============================================================
# UTILITY: Detect if response is blocked/challenge page
# ============================================================
def detect_blocked(html: str) -> list:
    """Look for indicators that the response is a block/challenge page."""
    indicators = []
    text = html.lower()[:5000]  # Check first 5KB
    
    block_signs = [
        ("Cloudflare challenge", "cf-challenge"),
        ("Cloudflare ray", "cf-ray"),
        ("CAPTCHA challenge", "captcha"),
        ("Just a moment", "just a moment"),
        ("Access denied", "access denied"),
        ("Bot detection", "bot detection"),
        ("403 Forbidden", "403 forbidden"),
        ("Checking your browser", "checking your browser"),
    ]
    
    for label, marker in block_signs:
        if marker in text:
            indicators.append(label)
    
    return indicators


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 70)
    print("INVESTING.COM ACCESSIBILITY TEST")
    print("=" * 70)
    
    print(f"\nTesting {len(TARGET_URLS)} URLs with 3 methods each...\n")
    
    all_results = {}
    
    for url in TARGET_URLS:
        print(f"\n>>> URL: {url}")
        print("-" * 70)
        
        url_results = []
        
        for test_func in [test_plain_requests, test_browser_headers, test_cloudscraper]:
            result = test_func(url)
            url_results.append(result)
            
            method = result.get("method", "unknown")
            
            if result.get("success"):
                status = result.get("status")
                size = result.get("size_kb", 0)
                has_events = result.get("has_events", False)
                blocked = result.get("blocked_indicators", [])
                
                if blocked:
                    print(f"   [BLOCKED] {method:25} HTTP {status}, {size:.1f}KB, blocks: {blocked}")
                elif has_events:
                    print(f"   [OK]      {method:25} HTTP {status}, {size:.1f}KB, content looks valid")
                else:
                    print(f"   [PARTIAL] {method:25} HTTP {status}, {size:.1f}KB, no event markers found")
            else:
                error = result.get("error", "unknown")
                print(f"   [FAIL]    {method:25} {error}")
        
        all_results[url] = url_results
    
    # ============================================================
    # ANALYSIS
    # ============================================================
    print("\n" + "=" * 70)
    print("ANALYSIS & RECOMMENDATIONS")
    print("=" * 70)
    
    # Find best working method
    best_method = None
    best_url = None
    
    for url, results in all_results.items():
        for r in results:
            if r.get("success") and r.get("has_events") and not r.get("blocked_indicators"):
                best_method = r["method"]
                best_url = url
                break
        if best_method:
            break
    
    if best_method:
        print(f"\n[SUCCESS] Working configuration found:")
        print(f"   URL:    {best_url}")
        print(f"   Method: {best_method}")
        print(f"\nNext step: Build scraper using {best_method} for {best_url}")
    else:
        print(f"\n[BLOCKED] None of the simple methods worked.")
        print(f"\nFallback options:")
        print(f"   1. Install cloudscraper:  pip install cloudscraper")
        print(f"      Then re-run this test.")
        print(f"   2. Use Selenium with Chromium:")
        print(f"      pip install selenium")
        print(f"      Need ChromeDriver setup")
        print(f"   3. Use Playwright (modern alternative):")
        print(f"      pip install playwright")
        print(f"      playwright install chromium")
        print(f"   4. Fall back to ForexFactory HTML (verified working earlier)")
    
    print("\nDONE.\n")


if __name__ == "__main__":
    main()
