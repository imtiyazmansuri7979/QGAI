"""
news_updater.py — refresh the economic-calendar CSV.

FAB-S2 fix (Fable-5 audit 2026-07-07): the file
`data/news_all_2024_to_now_pure_cleaned.csv` had its last event on 2026-05-15
and no auto-updater existed. `mins_to_next_3star` pegged at 240 and every
news feature silently zeroed → pre-news threshold bump dead, news-model
routing dead. Bot has been trading NFP/CPI at the Volatile 0.42 threshold
for ~7 weeks with zero warning.

This module does TWO things:

1. `refresh(force=False)` — attempt to pull new events from investpy (or
   Trading Economics if configured) and merge into the existing CSV. Safe
   to run weekly. Never truncates history — only APPENDS newer rows.

2. `check_staleness(max_days=None)` — returns a dict with `stale`, `last_event`,
   `days_old`, `next_event`. Called at bridge startup so a stale calendar
   yells at the operator instead of failing silently.

Fallback: if no library is available, `refresh()` prints exact manual
instructions and returns without touching the file. The system stays
functional (calendar just gets older) — only the staleness alarm fires.
"""
from __future__ import annotations
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from config import CFG

NEWS_FILE = Path(CFG.paths.news_file)
DEFAULT_MAX_STALE_DAYS = 7


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def check_staleness(max_days: Optional[int] = None) -> dict:
    """Return staleness snapshot. Never raises — caller decides what to do."""
    max_days = max_days if max_days is not None else DEFAULT_MAX_STALE_DAYS
    result = {
        "file": str(NEWS_FILE),
        "exists": NEWS_FILE.exists(),
        "last_event": None,
        "next_event": None,
        "rows": 0,
        "days_old": None,
        "stale": True,   # default TRUE (safe assumption)
        "max_days": max_days,
        "reason": "",
    }
    if not NEWS_FILE.exists():
        result["reason"] = f"file missing: {NEWS_FILE}"
        return result
    try:
        df = pd.read_csv(NEWS_FILE, usecols=["timestamp"])
    except Exception as e:
        result["reason"] = f"read fail: {e}"
        return result
    if df.empty:
        result["reason"] = "empty CSV"
        return result
    df["ts"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["ts"]).sort_values("ts")
    if df.empty:
        result["reason"] = "no valid timestamps"
        return result
    now = _now_utc()
    last = df["ts"].iloc[-1].to_pydatetime()
    future = df[df["ts"] > now]
    next_ev = future["ts"].iloc[0].to_pydatetime() if len(future) else None
    days_old = max(0.0, (now - last).total_seconds() / 86400.0)
    result.update({
        "last_event": last.isoformat(sep=" ", timespec="minutes"),
        "next_event": next_ev.isoformat(sep=" ", timespec="minutes") if next_ev else None,
        "rows": int(len(df)),
        "days_old": round(days_old, 1),
        "stale": days_old > max_days or next_ev is None,
        "reason": ("no future events" if next_ev is None
                   else f"last event {days_old:.1f} days old (>{max_days})"
                   if days_old > max_days else "OK"),
    })
    return result


def _try_investpy_fetch(from_dt: datetime, to_dt: datetime) -> Optional[pd.DataFrame]:
    """Try investpy; return DataFrame in our schema or None if unavailable/failed.
    Schema: timestamp, impact (1/2/3), event, actual, forecast, previous."""
    try:
        import investpy  # type: ignore
    except ImportError:
        return None
    try:
        raw = investpy.economic_calendar(
            from_date=from_dt.strftime("%d/%m/%Y"),
            to_date=to_dt.strftime("%d/%m/%Y"),
        )
    except Exception as e:
        print(f"  ⚠️  investpy fetch failed: {e}")
        return None
    if raw is None or raw.empty:
        return None
    # Normalize columns to the CSV schema
    imp_map = {"high": 3, "medium": 2, "low": 1, "none": 0, "": 0}
    out = pd.DataFrame({
        "timestamp": pd.to_datetime(
            raw["date"] + " " + raw["time"].replace("All Day", "00:00"),
            errors="coerce", dayfirst=True),
        "impact":  raw["importance"].str.lower().map(imp_map).fillna(0).astype(int),
        "event":   raw.get("event", "").astype(str),
        "actual":  pd.to_numeric(raw.get("actual"),   errors="coerce"),
        "forecast":pd.to_numeric(raw.get("forecast"), errors="coerce"),
        "previous":pd.to_numeric(raw.get("previous"), errors="coerce"),
    }).dropna(subset=["timestamp"])
    return out.sort_values("timestamp").reset_index(drop=True)


def refresh(force: bool = False, lookahead_days: int = 14,
            backfill_days: int = 3) -> dict:
    """Pull recent + upcoming events and merge into the CSV. Returns summary.
    force=True re-fetches even if the file is not stale."""
    status = check_staleness()
    if not force and not status["stale"]:
        print(f"  ✅ news CSV up to date (last={status['last_event']}, "
              f"next={status['next_event']})")
        return {"updated": False, "reason": "not stale", **status}

    now = _now_utc()
    from_dt = now - timedelta(days=backfill_days)
    to_dt   = now + timedelta(days=lookahead_days)
    fresh = _try_investpy_fetch(from_dt, to_dt)
    if fresh is None:
        msg = (
            "  ⚠️  news_updater: no puller available (investpy not installed / "
            "failed). Manual instructions:\n"
            "   1) Export a fresh economic calendar CSV from investing.com or "
            "forexfactory covering the last week + next 2 weeks.\n"
            f"   2) Normalize columns to: timestamp,impact,event,actual,forecast,previous "
            f"(impact 1=low,2=med,3=high).\n"
            f"   3) Append rows to {NEWS_FILE} (do NOT truncate history).\n"
            "   4) pip install investpy to automate this next time."
        )
        print(msg)
        return {"updated": False, "reason": "no puller", **status}

    # Merge: keep existing history, append only rows newer than the current max.
    try:
        existing = pd.read_csv(NEWS_FILE)
        existing["ts"] = pd.to_datetime(existing["timestamp"], errors="coerce")
        cur_max = existing["ts"].max()
        new_rows = fresh[fresh["timestamp"] > cur_max] if pd.notna(cur_max) else fresh
        if new_rows.empty:
            print("  ℹ️  news_updater: puller returned no rows newer than existing history")
            return {"updated": False, "reason": "no new rows", **status}
        combined = pd.concat(
            [existing.drop(columns=["ts"], errors="ignore"),
             new_rows.rename(columns={"timestamp": "timestamp"})],
            ignore_index=True,
        )
        combined = combined.sort_values("timestamp").drop_duplicates(
            subset=["timestamp", "event"], keep="last").reset_index(drop=True)
        # Atomic write
        tmp = NEWS_FILE.with_suffix(NEWS_FILE.suffix + ".tmp")
        combined.to_csv(tmp, index=False)
        tmp.replace(NEWS_FILE)
        after = check_staleness()
        print(f"  ✅ news_updater: appended {len(new_rows)} rows, "
              f"last event now {after['last_event']}")
        return {"updated": True, "new_rows": int(len(new_rows)), **after}
    except Exception as e:
        print(f"  ❌ news_updater merge failed: {e}")
        return {"updated": False, "reason": f"merge fail: {e}", **status}


if __name__ == "__main__":
    force = "--force" in sys.argv
    st = refresh(force=force)
    if st.get("stale") and not st.get("updated"):
        print(f"\n  🚨 CALENDAR STILL STALE — {st.get('reason', '')}")
        sys.exit(1)
    sys.exit(0)
