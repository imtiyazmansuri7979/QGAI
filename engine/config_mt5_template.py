"""
config_mt5_template.py
======================
STEP 1: Copy this file:
  copy config_mt5_template.py config_mt5.py

STEP 2: Edit config_mt5.py with YOUR settings
"""

# ── Legacy single primary (still supported as a fallback) ──────────────
# MT5 Terminal Path — Right-click MT5 icon → Properties → Target
MT5_PATH = r"C:\Imtiyaz\Vantage MT5 009\terminal64.exe"

# Account details
MT5_LOGIN  = 25334572
MT5_PASS   = "YourNewPassword"   # ← your new password here
MT5_SERVER = "VantageInternational-Demo"
MT5_SYMBOL = "XAUUSD"            # primary broker's gold symbol


# ── PRIMARY FAILOVER LIST (recommended: 3+ primaries) ──────────────────
# The bridge uses ONE MT5 terminal for market data + leading the trades.
# If that single primary's password changes or its connection drops, the
# whole system stalls. To avoid that, list MULTIPLE primary-eligible accounts
# here. On startup AND on every reconnect, the bridge tries them in order and
# uses the FIRST one that connects — so a dead primary auto-fails-over to the
# next without any manual config edit or restart.
#
# If MT5_PRIMARIES is left empty/absent, the legacy single primary above is
# used (fully backward-compatible).
MT5_PRIMARIES = [
    {
        "name":   "Vantage-009",
        "path":   r"C:\Imtiyaz\Vantage MT5 009\terminal64.exe",
        "login":  25334572,
        "pass":   "YourNewPassword",
        "server": "VantageInternational-Demo",
        "symbol": "XAUUSD",
    },
    {
        "name":   "Vantage-005",
        "path":   r"C:\Imtiyaz\Vantage MT5 005\terminal64.exe",
        "login":  0,                       # ← fill in
        "pass":   "",
        "server": "VantageMarkets-Demo",
        "symbol": "XAUUSD",
    },
    {
        "name":   "Neex-001",
        "path":   r"C:\Imtiyaz\Neex 001\terminal64.exe",
        "login":  0,                       # ← fill in
        "pass":   "",
        "server": "Neex-Live 2",
        "symbol": "XAUUSD",
    },
]


# == MULTI-ACCOUNT: secondary accounts that mirror the signal ==
# Index 0 = primary/leader; the rest are secondaries traded with independent
# lot sizing. (Unchanged — kept for execute_secondary_accounts.)
MT5_ACCOUNTS = [
    {
        "name":   "Vantage-009",
        "path":   r"C:\Imtiyaz\Vantage MT5 009\terminal64.exe",
        "login":  25334572,
        "pass":   "YourNewPassword",
        "server": "VantageInternational-Demo",
        "symbol": "XAUUSD",
    },
    # {
    #     "name":   "TradeQuo",
    #     "path":   r"C:\Imtiyaz\Tradequo 001\terminal64.exe",
    #     "login":  125926628,
    #     "pass":   "YourPass",
    #     "server": "TradeQuo-Server",
    #     "symbol": "XAUUSDs",
    # },
]
