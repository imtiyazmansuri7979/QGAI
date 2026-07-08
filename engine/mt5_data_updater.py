"""
mt5_data_updater.py — Auto Data Update from MT5
Pulls latest OHLCV + computes ADX for all TFs
Run: python mt5_data_updater.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys, os

sys.path.insert(0, str(Path(__file__).parent))
try:
    import config_mt5 as _c
except ImportError:
    print("❌ config_mt5.py not found!"); sys.exit(1)

from config import CFG

SYMBOL   = getattr(_c, "MT5_SYMBOL", "XAUUSD")   # read from config_mt5 (was hardcoded "XAUUSD.pc")
OUT_DIR = Path(CFG.paths.live_dir)   # live data folder — path from config.py
OUT_DIR.mkdir(parents=True, exist_ok=True)

OHLC_FILE = OUT_DIR / "ohlc_live.csv"
# Extra timeframes — SAVE-ONLY collection (used later for analysis/features).
# name: (MT5 timeframe attr, live filename, fresh-download start date)
EXTRA_TFS = {
    "M5":  ("TIMEFRAME_M5",  "ohlc_m5_live.csv",  "2024-01-01"),  # US-session volatility
    "M30": ("TIMEFRAME_M30", "ohlc_m30_live.csv", "2022-01-01"),
    "H1":  ("TIMEFRAME_H1",  "ohlc_h1_live.csv",  "2022-01-01"),
    "H4":  ("TIMEFRAME_H4",  "ohlc_h4_live.csv",  "2020-01-01"),
    "D1":  ("TIMEFRAME_D1",  "ohlc_d1_live.csv",  "2015-01-01"),
}
ADX_FILE  = OUT_DIR / "adx_live.csv"

def connect():
    if not mt5.initialize(path=_c.MT5_PATH, login=_c.MT5_LOGIN,
                          password=_c.MT5_PASS, server=_c.MT5_SERVER, timeout=10000):
        print(f"❌ MT5 failed: {mt5.last_error()}"); return False
    info = mt5.account_info()
    print(f"✅ Connected: {info.login} | Bal:${info.balance:,.2f}")
    return True

def compute_adx_tf(df, period=14):
    h=df["high"]; l=df["low"]; c=df["close"]
    tr = pd.concat([h-l,(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
    up = h-h.shift(1); dn = l.shift(1)-l
    pdm = np.where((up>dn)&(up>0), up, 0)
    ndm = np.where((dn>up)&(dn>0), dn, 0)
    pdm = pd.Series(pdm, index=df.index)
    ndm = pd.Series(ndm, index=df.index)
    atr = tr.ewm(span=period,adjust=False).mean()
    pdi = 100*pdm.ewm(span=period,adjust=False).mean()/(atr+1e-9)
    ndi = 100*ndm.ewm(span=period,adjust=False).mean()/(atr+1e-9)
    dx  = 100*(pdi-ndi).abs()/(pdi+ndi+1e-9)
    adx = dx.ewm(span=period,adjust=False).mean()
    # 2026-07-02 (Divyesh): also return raw +DI / -DI LEVELS (not just the diff) so the HMM
    # can tell QUIET (both DI low) from VOLATILE-chop (both DI high but close). DI_diff alone
    # conflates them -> slow markets mislabeled "Volatile". Backward-compat: diff still returned.
    return adx.round(2), (pdi-ndi).round(2), pdi.round(2), ndi.round(2)

def compute_band_width_pct_tf(df, period=2, method="SMMA"):
    """2026-07-02 (Divyesh) HMM v3: lag-free volatility feature per TF for the HMM.
    band_width_pct = (SMMA2(High) - SMMA2(Low)) / close * 100 — EXACT port of
    trend_signal.compute_trend band (Period=2 SMMA). NOT ATR (removed, lagging).
    MUST match regen_adx_di.compute_band_width_pct (training/live parity)."""
    from trend_signal import _ma
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    bw = (_ma(h, period, method) - _ma(l, period, method)) / c * 100.0
    return pd.Series(bw, index=df.index).round(4)

def update_ohlcv():
    print("\n📊 Updating OHLCV data...")

    # Load existing
    if OHLC_FILE.exists():
        existing = pd.read_csv(OHLC_FILE, low_memory=False)
        # Normalize: always work with 'time' col
        if "datetime" in existing.columns and "time" not in existing.columns:
            existing = existing.rename(columns={"datetime": "time"})
        existing["time"] = pd.to_datetime(existing["time"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        existing = existing[existing["time"].notna()].copy()
        last_dt = existing["time"].max()
        from_dt = last_dt - timedelta(hours=1)
        print(f"  Existing: {len(existing):,} rows | Last: {last_dt}")
    else:
        existing = None
        from_dt  = datetime(2024, 1, 1)
        print(f"  Fresh download from {from_dt.date()}")

    # Pull from MT5
    # Bug fix: naive datetimes passed to copy_rates_range are interpreted by
    # the MT5 lib as PC-LOCAL time and converted to a UTC epoch, while bar
    # epochs encode BROKER wall-clock. Net effect: the 'to' bound landed
    # ~3 hours behind broker-now and every update missed the newest 3h of
    # bars (file always ended 3h in the past). Fix: build both bounds as
    # tz-aware UTC values that ENCODE broker wall-clock, matching bar epochs.
    from datetime import timezone as _tz
    _tick_u = mt5.symbol_info_tick(SYMBOL)
    if _tick_u:
        _to_dt = datetime.fromtimestamp(_tick_u.time, tz=_tz.utc) + timedelta(hours=1)
    else:
        _to_dt = datetime.now(_tz.utc) + timedelta(hours=6)  # overshoot — MT5 caps at last bar
    # from_dt holds broker wall-clock values (CSV base) — localize as UTC so
    # the lib uses it verbatim instead of shifting by the PC timezone.
    _from_dt = pd.Timestamp(from_dt).tz_localize(_tz.utc).to_pydatetime()
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M15, _from_dt, _to_dt)
    if rates is None or len(rates) == 0:
        print(f"  ❌ No new data"); return None

    new_df = pd.DataFrame(rates)
    new_df["time"] = pd.to_datetime(new_df["time"], unit="s")

    # ── Date sanity guard ─────────────────────────────────
    # Compare in BROKER wall-clock base (CSV base), not PC-local time
    if _tick_u:
        _today = datetime.fromtimestamp(_tick_u.time, tz=_tz.utc).replace(tzinfo=None) + timedelta(minutes=5)
    else:
        _today = datetime.now(_tz.utc).replace(tzinfo=None) + timedelta(hours=3, minutes=5)
    _before = len(new_df)
    new_df = new_df[new_df["time"] <= _today].copy()
    if len(new_df) < _before:
        print(f"  ⚠️ Removed {_before-len(new_df)} future-dated OHLC rows")
    # ──────────────────────────────────────────────────────

    # Standardize: save time as ISO string "YYYY-MM-DD HH:MM:SS"
    new_df["time"] = new_df["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    new_df = new_df[["time","open","high","low","close","tick_volume"]]

    # Merge — both must be same type (ISO string)
    if existing is not None:
        # Convert existing timestamps to ISO string for consistent comparison
        existing["time"] = pd.to_datetime(existing["time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        df = pd.concat([existing, new_df], ignore_index=True)
        df = df.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)  # keep='last': fresh re-fetched bar wins over stale existing
    else:
        df = new_df.sort_values("time").reset_index(drop=True)

    df.to_csv(OHLC_FILE, index=False)
    print(f"  ✅ OHLCV: {len(df):,} rows | Updated to {df['time'].max()}")
    return df

def update_adx(df_m15):
    print("\n📈 Computing multi-TF ADX...")
    df = df_m15.copy()
    # Normalize: df_m15 now saves with 'time' col
    time_col = "time" if "time" in df.columns else "datetime"
    df["datetime"] = pd.to_datetime(df[time_col])
    df = df.set_index("datetime")

    def resample(rule):
        return df.resample(rule).agg(
            open=("open","first"),high=("high","max"),
            low=("low","min"),close=("close","last")
        ).dropna()

    tfs = {"M15":df,"M30":resample("30min"),"H1":resample("1h"),"H4":resample("4h")}

    # Build merged ADX dataframe at M15 timestamps
    result = pd.DataFrame(index=df.index)

    # 2026-07-02 (Divyesh, AUDIT FIX-1): AS-OF convention for ALL rows.
    # Old code ffilled FULL-bar HTF values into the M15 rows INSIDE the bar →
    # historical rows embedded intra-bar FUTURE data (backtest lookahead +
    # train/serve skew; audit: H4 drift mean 0.60 / max 2.02 ADX pts). Now every
    # row = EWM state over COMPLETED bars + one Wilder step with the PARTIAL
    # forming bar — exactly what this updater used to produce for the LATEST row
    # only, so LIVE decision behavior is UNCHANGED; only historical rows become
    # honest. Single source of truth: regen_adx_asof.asof_tf (validated err=0.0).
    from regen_adx_asof import asof_tf
    tf_rules = {"M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h"}
    for tf, rule in tf_rules.items():
        adx_t, pdi_t, ndi_t, band_t = asof_tf(df[["open", "high", "low", "close"]], rule)
        result[f"{tf}_ADX"]            = adx_t.round(2)
        result[f"{tf}_DI_diff"]        = (pdi_t - ndi_t).round(2)
        result[f"{tf}_PlusDI"]         = pdi_t.round(2)
        result[f"{tf}_MinusDI"]        = ndi_t.round(2)
        result[f"{tf}_band_width_pct"] = band_t.round(4)
        result[f"{tf}_di_eff"] = (100 * (pdi_t - ndi_t).abs() / (pdi_t + ndi_t + 1e-9)).round(2)
        _b = result[f"{tf}_band_width_pct"]
        result[f"{tf}_band_rel"] = (_b / _b.rolling("30D").mean()).round(4).fillna(1.0)
        print(f"  ✅ {tf}: as-of (leak-free)")

    result = result.reset_index()
    # Save with 'timestamp' + 'Time (24h)' cols to match load_adx() expectations
    result["timestamp"]    = result["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    result["Time (24h)"]   = result["datetime"].dt.strftime("%H:%M")
    result = result.drop(columns=["datetime"])
    result["data_source"] = "live"
    result.to_csv(ADX_FILE, index=False)
    print(f"  ✅ ADX saved: {len(result):,} rows → {ADX_FILE}")
    return result


# ── NEWS SURPRISE CALENDAR UPDATE ────────────────────────────────
# Pulls actual + forecast + previous from MT5 built-in economic calendar
# Covers all USD 2★ and 3★ events
# Saves to: CFG.paths.surprise_csv  (data/news_surprises.csv relative to QGAI root)
# ─────────────────────────────────────────────────────────────────

SURPRISE_FILE = Path(CFG.paths.surprise_csv)
SURPRISE_FILE.parent.mkdir(parents=True, exist_ok=True)

# USD 2★ + 3★ event keywords to track
USD_EVENTS_2_3STAR = [
    # 3★ VERY HIGH IMPACT
    "Nonfarm Payrolls", "Unemployment Rate", "Average Hourly Earnings",
    "Fed Interest Rate", "FOMC", "Federal Funds Rate",
    "Consumer Price Index", "CPI", "Core CPI",
    "Gross Domestic Product", "GDP",
    "Retail Sales", "Core Retail Sales",
    "ISM Manufacturing", "ISM Non-Manufacturing", "ISM Services",
    "JOLTS", "Job Openings",
    "Initial Jobless Claims", "Continuing Jobless Claims",
    "PCE Price Index", "Core PCE", "Personal Consumption",
    "Producer Price Index", "PPI", "Core PPI",
    "ADP Nonfarm", "ADP Employment",
    "Consumer Confidence", "Michigan",
    "Durable Goods",
    "Trade Balance",
    # 2★ MEDIUM IMPACT
    "Building Permits", "Housing Starts",
    "Existing Home Sales", "New Home Sales",
    "Factory Orders",
    "Philadelphia Fed", "Philly Fed",
    "Empire State",
    "Chicago PMI",
    "Pending Home Sales",
    "Wholesale Inventories",
    "Current Account",
    "EIA Crude", "Crude Oil Inventories",
    "Natural Gas Storage",
    "S&P Global Manufacturing PMI", "S&P Global Services PMI",
    "Flash Manufacturing PMI", "Flash Services PMI",
    "Baker Hughes",
]

def _parse_calendar_value(val):
    """Convert MT5 calendar value (integer multiplied by 10^digits) to float."""
    if val is None:
        return None
    try:
        v = float(val)
        # MT5 stores as integer * multiplier — already converted by Python API
        if v == -2147483648 or v == 0:  # MT5 sentinel for "no value"
            return None
        return v
    except (ValueError, TypeError):
        return None

def _format_value(val, multiplier_code, digits):
    """Format MT5 calendar value with correct unit."""
    if val is None:
        return ""
    try:
        v = float(val) / (10 ** digits) if digits > 0 else float(val)
        # MT5 multiplier codes: 0=none, 1=K, 2=M, 3=B, 4=T, 5=%
        units = {0: "", 1: "K", 2: "M", 3: "B", 4: "T", 5: "%"}
        unit = units.get(multiplier_code, "")
        if v == -2147483648 / (10 ** digits if digits > 0 else 1):
            return ""
        return f"{v:.4f}{unit}".rstrip('0').rstrip('.')
    except Exception:
        return str(val)

def update_news_surprises():
    """
    Pull USD 2★ + 3★ economic calendar events from MT5 built-in calendar.
    Saves: timestamp, event, currency, impact, actual, forecast, previous
    Updates incrementally — only fetches last 30 days + next 7 days.
    """
    print("\n📰 Updating news surprises from MT5 calendar...")

    from datetime import timezone
    import math

    # Date range: last 90 days + next 14 days
    now      = datetime.now()
    dt_from  = now - timedelta(days=90)
    dt_to    = now + timedelta(days=14)

    # Load existing surprises
    if SURPRISE_FILE.exists():
        existing = pd.read_csv(SURPRISE_FILE)
        existing['timestamp'] = pd.to_datetime(existing['timestamp'])
        print(f"  Existing: {len(existing):,} events")
    else:
        existing = pd.DataFrame()
        print("  Fresh download...")

    # ── Pull from MT5 calendar API ──────────────────────────
    try:
        # mt5.calendar_event_by_country returns all events for a country
        # mt5.calendar_value_history_by_event returns historical values with actual/forecast
        # First get all USD events
        events = mt5.calendar_event_by_country("US")
        if events is None:
            print("  ⚠️ MT5 calendar_event_by_country returned None — trying alternative...")
            events = mt5.calendar_event_by_country("USD")
        if events is None or len(events) == 0:
            print("  ❌ MT5 calendar API not available on this broker")
            print("  ℹ️ Using Option B (price momentum) automatically")
            return False
    except AttributeError:
        print("  ❌ MT5 calendar functions not available — broker may not support it")
        print("  ℹ️ Using Option B (price momentum) automatically")
        return False

    print(f"  Found {len(events):,} USD calendar events total")

    rows = []
    matched = 0

    for ev in events:
        # Filter by importance: 2★ (MEDIUM) or 3★ (HIGH)
        # MT5 importance: 1=LOW, 2=MEDIUM, 3=HIGH
        importance = getattr(ev, 'importance', 0)
        if importance < 2:
            continue

        event_name = getattr(ev, 'name', '') or ''

        # Filter to our tracked USD events only
        is_tracked = any(kw.lower() in event_name.lower() for kw in USD_EVENTS_2_3STAR)
        if not is_tracked:
            continue

        # Get historical values for this event
        try:
            values = mt5.calendar_value_history_by_event(
                ev.id,
                dt_from,
                dt_to
            )
        except Exception:
            continue

        if values is None or len(values) == 0:
            continue

        matched += 1
        digits     = getattr(ev, 'digits', 0) or 0
        multiplier = getattr(ev, 'multiplier', 0) or 0

        for val in values:
            try:
                # MT5 calendar val.time is a TRUE UTC epoch (unlike bar/tick
                # epochs which encode broker wall-clock). bar_time and the main
                # news file are in broker base (UTC+3) — verified: NFP rows in
                # news_all CSV sit at 16:30 (winter) = 8:30 ET. Convert calendar
                # UTC → broker base so _get_surprise_direction's [t-2h, t]
                # window can actually match (it never matched with UTC values).
                ts = (datetime.fromtimestamp(val.time, tz=timezone.utc).replace(tzinfo=None)
                      + timedelta(hours=3)) if hasattr(val, 'time') else None
                if ts is None:
                    continue

                # actual_value, forecast_value, prev_value stored as int * 10^digits
                raw_actual   = getattr(val, 'actual_value',   None)
                raw_forecast = getattr(val, 'forecast_value', None)
                raw_prev     = getattr(val, 'prev_value',     None)

                actual   = _format_value(raw_actual,   multiplier, digits)
                forecast = _format_value(raw_forecast, multiplier, digits)
                previous = _format_value(raw_prev,     multiplier, digits)

                rows.append({
                    'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S'),
                    'event':     event_name,
                    'currency':  'USD',
                    'impact':    importance,
                    'actual':    actual,
                    'forecast':  forecast,
                    'previous':  previous,
                })
            except Exception:
                continue

    print(f"  Matched {matched} tracked event types → {len(rows):,} data points")

    if len(rows) == 0:
        print("  ⚠️ No data rows fetched — check broker calendar support")
        return False

    new_df = pd.DataFrame(rows)
    new_df['timestamp'] = pd.to_datetime(new_df['timestamp'])

    # Merge with existing — deduplicate by timestamp+event
    if len(existing) > 0:
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=['timestamp', 'event'], keep='last')
        combined = combined.sort_values('timestamp').reset_index(drop=True)
    else:
        combined = new_df.sort_values('timestamp').reset_index(drop=True)

    combined.to_csv(SURPRISE_FILE, index=False)
    print(f"  ✅ Surprises saved: {len(combined):,} events → {SURPRISE_FILE}")

    # Show last 5 released events
    released = combined[combined['actual'].notna() & (combined['actual'] != '')]
    if len(released) > 0:
        print("  📊 Last 5 released events:")
        for _, r in released.tail(5).iterrows():
            stars = "3★" if r['impact'] == 3 else "2★"
            print(f"     {stars} {r['timestamp'].strftime('%m-%d %H:%M')} | {r['event'][:30]:30s} | actual={r['actual']:>8} | forecast={r['forecast']:>8}")

    return True

def update_ohlcv_tf(tf_name: str):
    """Generic extra-timeframe OHLCV — SAVE-ONLY (no features use it yet).
    Same incremental + broker-timezone-safe logic as the M15 updater.
    Pure data collection so history accumulates for future use."""
    from datetime import timezone as _tz
    tf_attr, fname, fresh_from = EXTRA_TFS[tf_name]
    out_file = OUT_DIR / fname
    print(f"\n📊 Updating {tf_name} OHLCV data (save-only)...")

    if out_file.exists():
        existing = pd.read_csv(out_file, low_memory=False)
        existing["time"] = pd.to_datetime(existing["time"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        existing = existing[existing["time"].notna()].copy()
        from_dt = existing["time"].max() - timedelta(days=2)
        print(f"  Existing: {len(existing):,} rows | Last: {existing['time'].max()}")
    else:
        existing = None
        from_dt  = datetime.strptime(fresh_from, "%Y-%m-%d")
        print(f"  Fresh {tf_name} download from {fresh_from} (broker history permitting)")

    _tick_u = mt5.symbol_info_tick(SYMBOL)
    if _tick_u:
        _to_dt = datetime.fromtimestamp(_tick_u.time, tz=_tz.utc) + timedelta(hours=1)
    else:
        _to_dt = datetime.now(_tz.utc) + timedelta(hours=6)
    _from_dt = pd.Timestamp(from_dt).tz_localize(_tz.utc).to_pydatetime()
    rates = mt5.copy_rates_range(SYMBOL, getattr(mt5, tf_attr), _from_dt, _to_dt)
    if rates is None or len(rates) == 0:
        print(f"  ❌ No {tf_name} data returned"); return None

    new_df = pd.DataFrame(rates)
    new_df["time"] = pd.to_datetime(new_df["time"], unit="s")
    if _tick_u:
        _today = datetime.fromtimestamp(_tick_u.time, tz=_tz.utc).replace(tzinfo=None) + timedelta(days=1)
    else:
        _today = datetime.now(_tz.utc).replace(tzinfo=None) + timedelta(hours=27)
    _before = len(new_df)
    new_df = new_df[new_df["time"] <= _today].copy()
    if len(new_df) < _before:
        print(f"  ⚠️ Removed {_before-len(new_df)} future-dated {tf_name} rows")

    new_df["time"] = new_df["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    new_df = new_df[["time","open","high","low","close","tick_volume"]]

    if existing is not None:
        existing["time"] = pd.to_datetime(existing["time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        df = pd.concat([existing, new_df], ignore_index=True)
        df = df.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)  # keep='last': fresh re-fetched bar wins over stale existing
    else:
        df = new_df.sort_values("time").reset_index(drop=True)

    df.to_csv(out_file, index=False)
    print(f"  ✅ {tf_name} OHLCV: {len(df):,} rows | Updated to {df['time'].max()}")
    return df


def main():
    print("="*55)
    print("  QUANT GOLD AI — MT5 Data Updater")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*55)

    if not connect(): return
    df_ohlc = update_ohlcv()
    if df_ohlc is not None:
        update_adx(df_ohlc)
    for _tf in EXTRA_TFS:                 # M5, M30, H1, H4, D1 — save-only
        try:
            update_ohlcv_tf(_tf)
        except Exception as _e:
            print(f"  ⚠️ {_tf} update failed: {_e}")
    update_news_surprises()
    mt5.shutdown()
    print("\n✅ Data update complete!")
    print(f"   OHLCV : {OHLC_FILE}")
    print(f"   ADX   : {ADX_FILE}")
    for _tf, (_a, _fn, _d) in EXTRA_TFS.items():
        print(f"   {_tf:<5} : {OUT_DIR / _fn}")
    # Auto-merge historical + live for training
    try:
        import subprocess, sys as _sys
        _merge = Path(__file__).resolve().parent / "merge_data.py"
        if _merge.exists():
            result = subprocess.run(
                [_sys.executable, str(_merge)], check=False, timeout=60,
                capture_output=True, text=True
            )
            if result.returncode != 0:
                print(f"  ⚠ Auto-merge exited with code {result.returncode}")
                if result.stderr:
                    print(f"  ⚠ merge stderr: {result.stderr[-300:]}")
    except Exception as e:
        print(f"  ⚠ Auto-merge failed: {e}")
    print(f"   Surprises: {SURPRISE_FILE}")

if __name__ == "__main__":
    main()
