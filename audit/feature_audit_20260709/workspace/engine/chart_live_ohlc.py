"""
chart_live_ohlc.py - write the latest real closed M15 candles for chart.html.

This is intentionally separate from the training/merge pipeline so the chart never
waits for merged CSV refreshes. It pulls directly from MT5 and writes:
  logs/chart_ohlc_live.csv
"""
import io
import sys
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import CFG

try:
    import config_mt5 as MT5CFG
except Exception as e:
    print(f"config_mt5.py load failed: {e}")
    sys.exit(1)


SYMBOL = getattr(MT5CFG, "MT5_SYMBOL", "XAUUSD")
TIMEFRAME = mt5.TIMEFRAME_M15
N_BARS = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
OUT = Path(CFG.paths.logs_dir) / "chart_ohlc_live.csv"


def connect():
    ok = mt5.initialize(
        path=getattr(MT5CFG, "MT5_PATH", None),
        login=getattr(MT5CFG, "MT5_LOGIN", None),
        password=getattr(MT5CFG, "MT5_PASS", None),
        server=getattr(MT5CFG, "MT5_SERVER", None),
        timeout=10000,
    )
    if not ok:
        print(f"MT5 initialize failed: {mt5.last_error()}")
        return False
    return True


def main():
    if not connect():
        sys.exit(2)
    try:
        rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, max(N_BARS + 5, 100))
        if rates is None or len(rates) == 0:
            print(f"No MT5 rates returned for {SYMBOL} M15: {mt5.last_error()}")
            sys.exit(3)

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.sort_values("time").reset_index(drop=True)

        # MT5 includes the current forming candle as the newest row. Keep only
        # closed candles; chart.html builds the forming candle from live bid.
        if len(df) > 1:
            df = df.iloc[:-1].copy()

        df = df.tail(N_BARS)
        df["time"] = df["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
        out = df[["time", "open", "high", "low", "close", "tick_volume"]].copy()

        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".csv.tmp")
        out.to_csv(tmp, index=False)
        tmp.replace(OUT)
        print(f"chart_ohlc_live.csv: {len(out)} closed M15 candles -> {out['time'].iloc[-1]}")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
