"""
check_history_depth.py — QUANT GOLD AI v2
═══════════════════════════════════════════════════════════════════
READ-ONLY diagnostic. Asks the broker how far back XAUUSD history
goes for each timeframe, and how many decimals the prices have.
Saves nothing, changes nothing — safe to run anytime.

Run:  python check_history_depth.py
═══════════════════════════════════════════════════════════════════
"""
import sys
from datetime import datetime, timezone, timedelta

try:
    import MetaTrader5 as mt5
except ImportError:
    print("❌ MetaTrader5 module not found"); sys.exit(1)

try:
    import config_mt5 as _c
except ImportError:
    print("❌ config_mt5.py not found (need MT5 login)"); sys.exit(1)

import pandas as pd

SYMBOL = getattr(_c, "MT5_SYMBOL", "XAUUSD")   # read from config_mt5 (was hardcoded "XAUUSD.pc")

TFS = {
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
}


def main():
    if not mt5.initialize(path=_c.MT5_PATH, login=_c.MT5_LOGIN,
                          password=_c.MT5_PASS, server=_c.MT5_SERVER, timeout=10000):
        print(f"❌ MT5 connect failed: {mt5.last_error()}"); return
    info = mt5.account_info()
    print("=" * 64)
    print("  BROKER HISTORY DEPTH CHECK (read-only)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Account: {info.login if info else '?'} | Server: {_c.MT5_SERVER}")
    print("=" * 64)

    si = mt5.symbol_info(SYMBOL)
    if si is None:
        print(f"❌ Symbol {SYMBOL} not found"); mt5.shutdown(); return
    print(f"\n  Symbol: {SYMBOL}")
    print(f"  Broker quote DIGITS: {si.digits}   "
          f"({'3-decimal (e.g. 3300.555)' if si.digits == 3 else str(si.digits)+'-decimal'})")
    print(f"  Point: {si.point} | Tick size: {si.trade_tick_size}")

    # large overshoot end so MT5 returns up to its latest bar
    end = datetime.now(timezone.utc) + timedelta(days=2)

    print(f"\n  {'TF':<5}{'bars avail':>13}{'oldest bar':>22}{'newest bar':>22}{'~years':>9}")
    print("  " + "-" * 68)
    rows = []
    for name, tf in TFS.items():
        # request a huge count from position 0 (newest) backwards
        rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, 500_000)
        if rates is None or len(rates) == 0:
            print(f"  {name:<5}{'— none —':>13}")
            continue
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        oldest, newest = df["time"].iloc[0], df["time"].iloc[-1]
        yrs = (newest - oldest).days / 365.25
        # decimals actually present in close prices
        decs = df["close"].apply(lambda x: len(f"{x:.10f}".rstrip("0").split(".")[1])
                                 if "." in f"{x:.10f}".rstrip("0") else 0).max()
        rows.append((name, len(df), oldest, newest, yrs, decs))
        print(f"  {name:<5}{len(df):>13,}{str(oldest):>22}{str(newest):>22}{yrs:>9.1f}")

    print("\n  Price decimals actually returned per TF:")
    for name, n, o, ne, y, d in rows:
        print(f"    {name:<5} max decimals = {d}")

    # compare to current saved M15 history
    print("\n  " + "-" * 68)
    try:
        cur = pd.read_csv("../data/merged/ohlc_merged.csv", usecols=["time"])
        print(f"  CURRENT saved M15 history: {len(cur):,} bars "
              f"({cur['time'].iloc[0][:10]} → {cur['time'].iloc[-1][:10]})")
        m15 = next((r for r in rows if r[0] == "M15"), None)
        if m15:
            verdict = "✅ broker ≥ current — full reload SAFE" if m15[1] >= len(cur) * 0.9 \
                      else "⚠️ broker < current — reload would LOSE history, prefer HYBRID"
            print(f"  Broker M15 available  : {m15[1]:,} bars  →  {verdict}")
    except Exception as e:
        print(f"  (couldn't read current history: {e})")

    print("=" * 64)
    mt5.shutdown()


if __name__ == "__main__":
    main()
