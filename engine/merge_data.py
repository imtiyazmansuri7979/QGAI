"""
merge_data.py — QGAI Data Manager
Manages separation between historical and live data.

QGAI/data/
  historical/  <- OLD backtest data (NEVER modified)
  live/        <- NEW live data (daily updated)
  merged/      <- COMBINED for training (auto-generated)

Usage:
  python merge_data.py          -> merge + show summary
  python merge_data.py --setup  -> first-time setup
  python merge_data.py --status -> show status only
"""
import sys, io
# Windows encoding fix — prevents UnicodeEncodeError on cp1252 terminals
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


import sys, shutil
import pandas as pd
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CFG

# ── All paths from CFG — no hardcoding ───────────────────────
DATA_DIR    = Path(CFG.paths.hist_dir).parent   # data/
HIST_DIR    = Path(CFG.paths.hist_dir)
HIST_OHLC   = HIST_DIR / "ohlc_historical.csv"
HIST_ADX    = HIST_DIR / "adx_historical.csv"
LIVE_DIR    = Path(CFG.paths.live_dir)
LIVE_OHLC   = LIVE_DIR / "ohlc_live.csv"
LIVE_ADX    = LIVE_DIR / "adx_live.csv"
LIVE_TRADES = LIVE_DIR / "trades_live.csv"
MERGE_DIR   = Path(CFG.paths.merge_dir)
MERGE_OHLC  = Path(CFG.paths.ohlc_file)
MERGE_ADX   = Path(CFG.paths.adx_file)
ORIG_OHLC   = DATA_DIR / "ohlc and volum data.csv"
ORIG_ADX    = DATA_DIR / "Back_testing_with_ADX_Data_Final_cleaned.csv"

G="\033[92m"; Y="\033[93m"; R="\033[91m"; B="\033[94m"; W="\033[0m"

# ── Safe datetime parsers ─────────────────────────────────────
# OHLC 'time' column has two formats depending on source:
#   Historical CSV  : 'YYYY-MM-DD HH:MM'       (no seconds)
#   Live / Merged   : 'YYYY-MM-DD HH:MM:SS'    (with seconds)
# Both are unambiguous ISO 8601 — no dayfirst guessing needed.
# Try the most common format first (with seconds), fall back to
# the shorter form, then coerce anything left to NaT instead of crashing.
def _parse_ohlc_time(series: pd.Series) -> pd.Series:
    """Parse OHLC 'time' column. Never raises; bad rows become NaT."""
    result = pd.to_datetime(series, format='%Y-%m-%d %H:%M:%S', errors='coerce')
    retry = result.isna() & series.notna() & (series.astype(str).str.strip() != '')
    if retry.any():
        result.loc[retry] = pd.to_datetime(
            series.loc[retry], format='%Y-%m-%d %H:%M', errors='coerce'
        )
    return result

# ADX '_dt' is always constructed as 'YYYY-MM-DD' + ' ' + 'HH:MM' (no seconds).
def _parse_adx_time(series: pd.Series) -> pd.Series:
    """Parse ADX constructed datetime column. Never raises; bad rows become NaT."""
    return pd.to_datetime(series, format='%Y-%m-%d %H:%M', errors='coerce')

def _warn_nat(series: pd.Series, label: str):
    """Warn if any rows became NaT after parsing so problems are visible."""
    n = series.isna().sum()
    if n:
        print(f"  {Y}⚠ {label}: {n} rows had unparseable timestamps and were dropped{W}")


def setup_folders():
    for f in [HIST_DIR, LIVE_DIR, MERGE_DIR]:
        f.mkdir(parents=True, exist_ok=True)

def first_time_setup():
    print(f"\n{B}FIRST TIME SETUP{W}")
    setup_folders()
    if ORIG_OHLC.exists() and not HIST_OHLC.exists():
        shutil.copy2(ORIG_OHLC, HIST_OHLC)
        n = len(pd.read_csv(HIST_OHLC, low_memory=False))
        print(f"  {G}OHLC copied → historical/ ({n:,} rows){W}")
    else:
        print(f"  {Y}Historical OHLC: already exists or source not found{W}")
    if ORIG_ADX.exists() and not HIST_ADX.exists():
        shutil.copy2(ORIG_ADX, HIST_ADX)
        n = len(pd.read_csv(HIST_ADX))
        print(f"  {G}ADX  copied → historical/ ({n:,} rows){W}")
    else:
        print(f"  {Y}Historical ADX:  already exists or source not found{W}")
    print(f"\n  {G}Done! Run: python merge_data.py{W}")

def merge_ohlc():
    frames = []
    _now = pd.Timestamp.now()
    src = HIST_OHLC if HIST_OHLC.exists() else (ORIG_OHLC if ORIG_OHLC.exists() else None)
    if src is not None:
        df = pd.read_csv(src, low_memory=False)
        df['time'] = _parse_ohlc_time(df['time'])
        _warn_nat(df['time'], 'hist OHLC')
        df = df[df['time'].notna() & (df['time'] <= _now)].copy()
        df['time'] = df['time'].dt.strftime('%Y-%m-%d %H:%M:%S')  # normalize to ISO
        frames.append(df)
        t_min = pd.to_datetime(df['time']).min().date()
        t_max = pd.to_datetime(df['time']).max().date()
        print(f"  Historical: {len(df):>7,} rows | {t_min} → {t_max}")
    else:
        print(f"  {Y}Historical OHLC disabled/absent — LIVE-ONLY mode (fresh reload){W}")
    if LIVE_OHLC.exists():
        df = pd.read_csv(LIVE_OHLC, low_memory=False)
        df['time'] = _parse_ohlc_time(df['time'])
        _warn_nat(df['time'], 'live OHLC')
        df = df[df['time'].notna() & (df['time'] <= _now)].copy()
        df['time'] = df['time'].dt.strftime('%Y-%m-%d %H:%M:%S')  # normalize
        frames.append(df)
        t_min = pd.to_datetime(df['time']).min().date()
        t_max = pd.to_datetime(df['time']).max().date()
        print(f"  {G}Live:      {len(df):>7,} rows | {t_min} → {t_max}{W}")
    else:
        print(f"  {Y}Live OHLC: none yet{W}")
    if not frames:
        print(f"  {R}No OHLC source at all (historical absent + live missing)!{W}"); return False
    merged = pd.concat(frames, ignore_index=True)
    merged['time'] = pd.to_datetime(merged['time'])
    merged = merged.drop_duplicates('time', keep='last').sort_values('time').reset_index(drop=True)  # fresh live wins over historical on overlap
    merged['time'] = merged['time'].dt.strftime('%Y-%m-%d %H:%M:%S')
    merged.to_csv(MERGE_OHLC, index=False)
    print(f"  {G}Merged:    {len(merged):>7,} rows → merged/ohlc_merged.csv [OK]{W}")
    return True

def merge_adx():
    frames = []
    _now = pd.Timestamp.now()
    src = HIST_ADX if HIST_ADX.exists() else (ORIG_ADX if ORIG_ADX.exists() else None)
    if src is not None:
        df = pd.read_csv(src)
        # Build datetime from the date part of timestamp + the HH:MM time column.
        # This is always 'YYYY-MM-DD HH:MM' — a single, explicit format.
        df['_dt'] = _parse_adx_time(
            df['timestamp'].astype(str).str[:10] + ' ' + df['Time (24h)'].astype(str)
        )
        _warn_nat(df['_dt'], 'hist ADX')
        df = df[df['_dt'].notna() & (df['_dt'] <= _now)].copy()
        # Normalize timestamp to full ISO
        df['timestamp'] = df['_dt'].dt.strftime('%Y-%m-%d %H:%M:%S')
        df = df.drop(columns=['_dt'])
        frames.append(df)
        t_max = pd.to_datetime(df['timestamp']).max()
        print(f"  Historical: {len(df):>7,} rows | → {t_max.date()}")
    else:
        print(f"  {Y}Historical ADX disabled/absent — LIVE-ONLY mode (fresh reload){W}")
    if LIVE_ADX.exists():
        df = pd.read_csv(LIVE_ADX)
        df['_dt'] = _parse_adx_time(
            df['timestamp'].astype(str).str[:10] + ' ' + df['Time (24h)'].astype(str)
        )
        _warn_nat(df['_dt'], 'live ADX')
        df = df[df['_dt'].notna() & (df['_dt'] <= _now)].copy()
        df['timestamp'] = df['_dt'].dt.strftime('%Y-%m-%d %H:%M:%S')
        df = df.drop(columns=['_dt'])
        frames.append(df)
        t_max = pd.to_datetime(df['timestamp']).max()
        print(f"  {G}Live:       {len(df):>7,} rows | → {t_max.date()}{W}")
    else:
        print(f"  {Y}Live ADX: none yet{W}")
    if not frames:
        print(f"  {R}No ADX source at all!{W}"); return False
    merged = pd.concat(frames, ignore_index=True)
    merged['_dt'] = pd.to_datetime(merged['timestamp'])
    merged = merged.drop_duplicates('_dt', keep='last').sort_values('_dt').reset_index(drop=True)  # fresh live wins over historical on overlap
    merged['timestamp'] = merged['_dt'].dt.strftime('%Y-%m-%d %H:%M:%S')
    merged = merged.drop(columns=['_dt'])
    merged.to_csv(MERGE_ADX, index=False)
    print(f"  {G}Merged:     {len(merged):>7,} rows → merged/adx_merged.csv [OK]{W}")
    return True

def show_status():
    print(f"\n{'='*55}\n  DATA STATUS\n{'='*55}")
    for section, files in [
        (f"{B}HISTORICAL (read-only){W}", [(HIST_OHLC,'OHLC'),(HIST_ADX,'ADX')]),
        (f"{G}LIVE (daily updated){W}",   [(LIVE_OHLC,'OHLC'),(LIVE_ADX,'ADX'),(LIVE_TRADES,'Trades')]),
        (f"{Y}MERGED (for training){W}",  [(MERGE_OHLC,'OHLC'),(MERGE_ADX,'ADX')]),
    ]:
        print(f"\n  {section}")
        for path, name in files:
            if path.exists():
                sz = path.stat().st_size
                mt = datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                sz_s = f"{sz/1024:.0f}KB" if sz<1024*1024 else f"{sz/1024/1024:.1f}MB"
                try: rows = f"{sum(1 for _ in open(path, encoding='utf-8', errors='ignore'))-1:,} rows"
                except OSError: rows = "? rows"
                print(f"    {G}[OK]{W} {name:<8} {rows:>12} {sz_s:>8}  {mt}")
            else:
                print(f"    {Y}--{W} {name:<8} {'not created yet':>20}")
    if LIVE_TRADES.exists():
        try:
            t = pd.read_csv(LIVE_TRADES)
            w = (t['profit']>0).sum(); l = (t['profit']<=0).sum()
            print(f"\n  {B}LIVE TRADES:{W} {w+l} trades | WR:{w/(w+l)*100:.0f}% | P&L:${t['profit'].sum():+,.2f}")
        except (pd.errors.ParserError, KeyError, ValueError) as e:
            print(f"\n  {Y}⚠ Could not read live trades summary: {e}{W}")

def save_live_trade(ticket, direction, entry, close_price, profit, lot, open_time, close_time, sl_dist=0, win_prob=0):
    """Save closed QGAI trade to live/trades_live.csv"""
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    row = {'ticket':ticket,'direction':direction,'lot':lot,'entry':entry,'close':close_price,
           'profit':round(profit,2),'sl_dist':round(sl_dist,2),'win_prob':round(win_prob,4),
           'open_time':str(open_time),'close_time':str(close_time),'win':int(profit>0),
           'source':'qgai_live','date':str(close_time)[:10]}
    df = pd.DataFrame([row])
    df.to_csv(LIVE_TRADES, mode='a', header=not LIVE_TRADES.exists(), index=False)

if __name__ == "__main__":
    print(f"\n{'='*55}\n  QGAI DATA MANAGER — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{'='*55}")
    if "--setup" in sys.argv:
        first_time_setup(); sys.exit(0)
    if "--status" in sys.argv:
        show_status(); sys.exit(0)
    setup_folders()
    show_status()
    print(f"\n{'='*55}\n  MERGING OHLC\n{'='*55}")
    ok1 = merge_ohlc()
    print(f"\n{'='*55}\n  MERGING ADX\n{'='*55}")
    ok2 = merge_adx()
    # ── Extra timeframes (M5/M30/H1/H4/D1) → merged copies ──────────
    print(f"\n{'='*55}\n  MERGING EXTRA TIMEFRAMES (save-only)\n{'='*55}")
    _extra = {"M5":"ohlc_m5", "M30":"ohlc_m30", "H1":"ohlc_h1", "H4":"ohlc_h4", "D1":"ohlc_d1"}
    for _tf, _base in _extra.items():
        try:
            _lv = LIVE_DIR / f"{_base}_live.csv"
            _hist = HIST_DIR / f"{_base}_historical.csv"   # optional — merged if present
            if not _lv.exists():
                print(f"  -- {_tf:<4} no live file yet (first MT5 update will create it)")
                continue
            _d = pd.read_csv(_lv, low_memory=False)
            _d["time"] = pd.to_datetime(_d["time"], errors="coerce")
            _d = _d[_d["time"].notna()]
            if _hist.exists():
                _h = pd.read_csv(_hist, low_memory=False)
                _h["time"] = pd.to_datetime(_h["time"], errors="coerce")
                _d = pd.concat([_h[_h["time"].notna()], _d], ignore_index=True)
            _d["time"] = _d["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
            _d = _d.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)  # fresh live wins over historical on overlap
            _out = MERGE_DIR / f"{_base}_merged.csv"
            _d.to_csv(_out, index=False)
            print(f"  [OK] {_tf:<4} {len(_d):>8,} rows | {_d['time'].iloc[0][:10]} → "
                  f"{_d['time'].iloc[-1][:16]} → {_out.name}")
        except Exception as _e:
            print(f"  [WARN] {_tf} merge failed: {_e}")

    # ── Indicator snapshot: ALL values per 15-min bar (no loopholes) ──
    if ok1 and ok2:
        print(f"\n{'='*55}\n  BUILDING INDICATOR SNAPSHOT\n{'='*55}")
        try:
            from build_indicators import build as _bi_build, verify as _bi_verify
            _snap = _bi_build()
            _bi_verify(_snap, 15)
        except Exception as _e:
            print(f"  [WARN] indicator snapshot failed: {_e}")
        print(f"\n{'='*55}\n  BUILDING FEATURE SNAPSHOT (incremental)\n{'='*55}")
        try:
            from build_feature_snapshot import build as _fs_build
            _fs_build()
        except Exception as _e:
            print(f"  [WARN] feature snapshot failed: {_e}")
    print(f"\n{'='*55}")
    print(f"  {G+'[OK] Ready for training!'+W if ok1 and ok2 else R+'[ERR] Check errors above'+W}")
    print(f"{'='*55}\n")
