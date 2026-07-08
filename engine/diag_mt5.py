"""
diag_mt5.py — quick MT5 diagnostic (read-only, safe)
Run: python diag_mt5.py
Tells us: connection, symbol status, and the most-recent bars MT5 actually has.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import MetaTrader5 as mt5
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import config_mt5 as _c

SYMBOL = "XAUUSD.pc"

print("=" * 55)
print("  MT5 DIAGNOSTIC")
print("=" * 55)

if not mt5.initialize(path=_c.MT5_PATH, login=_c.MT5_LOGIN,
                      password=_c.MT5_PASS, server=_c.MT5_SERVER, timeout=10000):
    print(f"❌ MT5 initialize failed: {mt5.last_error()}")
    sys.exit(1)

ti = mt5.terminal_info()
ai = mt5.account_info()
print(f"✅ Connected account: {ai.login} | Bal: ${ai.balance:,.2f}")
print(f"   Terminal connected to server: {getattr(ti,'connected',None)}")
print(f"   Trade allowed: {getattr(ti,'trade_allowed',None)}")
print(f"   Terminal time (server): {datetime.utcfromtimestamp(mt5.symbol_info_tick(SYMBOL).time) if mt5.symbol_info_tick(SYMBOL) else 'no tick'}")

print("-" * 55)
si = mt5.symbol_info(SYMBOL)
if si is None:
    print(f"❌ Symbol {SYMBOL} NOT found at broker. Listing close matches:")
    for s in mt5.symbols_get():
        if "XAU" in s.name.upper():
            print("   candidate:", s.name, "| visible:", s.visible)
else:
    print(f"Symbol {SYMBOL}: visible(in Market Watch)={si.visible} | last tick price={si.last} | bid={si.bid}")
    if not si.visible:
        print("   ⚠️ Symbol is NOT in Market Watch — selecting it now...")
        mt5.symbol_select(SYMBOL, True)

print("-" * 55)
print("Most-recent bars MT5 actually has (copy_rates_from_pos, newest first):")
for tf_name, tf in [("M15", mt5.TIMEFRAME_M15), ("M5", mt5.TIMEFRAME_M5), ("H1", mt5.TIMEFRAME_H1)]:
    rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, 3)
    if rates is None or len(rates) == 0:
        print(f"  {tf_name}: ❌ none returned  (last_error={mt5.last_error()})")
    else:
        times = [str(datetime.utcfromtimestamp(r['time'])) for r in rates]
        print(f"  {tf_name}: newest bar = {times[-1]}   (got {len(rates)} bars)")

print("=" * 55)
mt5.shutdown()
