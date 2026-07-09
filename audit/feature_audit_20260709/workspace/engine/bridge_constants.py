"""
bridge_constants.py — QUANT GOLD AI v2
Shared constants, imports and MT5 utility helpers.
All other bridge modules import from here.
"""
import MetaTrader5 as mt5
import time, logging, sys, json, re, sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import CFG

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(CFG.paths.logs_dir) / "bridge.log", encoding="utf-8")
    ]
)
log = logging.getLogger("QGAI")

# ── MT5 credentials ───────────────────────────────────────────
try:
    import config_mt5 as _c
    MT5_PATH   = _c.MT5_PATH
    MT5_LOGIN  = _c.MT5_LOGIN
    MT5_PASS   = _c.MT5_PASS
    MT5_SERVER = _c.MT5_SERVER
except ImportError:
    print("❌ config_mt5.py not found! Copy config_mt5_template.py → config_mt5.py")
    sys.exit(1)

# ── Trading constants ─────────────────────────────────────────
# Read symbol from primary account config (falls back to XAUUSD.pc)
try:
    import config_mt5 as _cm
    _primary_accts = getattr(_cm, "MT5_ACCOUNTS", [])
    SYMBOL = _primary_accts[0].get("symbol", "XAUUSD.pc") if _primary_accts else "XAUUSD.pc"
except Exception:
    SYMBOL = "XAUUSD.pc"
TIMEFRAME  = mt5.TIMEFRAME_M15
MAGIC      = 202600
RISK_PCT   = CFG.filters.risk_pct
DAILY_SL   = CFG.filters.daily_loss_limit_pct
DAILY_TP        = CFG.filters.daily_profit_target_pct  # daily equity profit target %
ENABLE_DAILY_TP = CFG.filters.enable_daily_tp

# ── RATCHET exit (EA-style package) ───────────────────────────
RATCHET_EXIT         = CFG.filters.enable_ratchet_exit
RATCHET_BUF_PCT      = CFG.filters.ratchet_buf_pct
RATCHET_TP_CAP_PCT   = CFG.filters.ratchet_tp_cap_pct
TP_EQUITY_PCT        = CFG.filters.tp_equity_pct
RATCHET_MAX_RISK_PCT = CFG.filters.ratchet_max_risk_pct
RATCHET_FLIP_EXIT    = CFG.filters.ratchet_flip_exit
MAX_SPREAD_USD       = getattr(CFG.filters, "max_spread_usd", 0.0)
SPREAD_WAIT_SEC      = getattr(CFG.filters, "spread_wait_sec", 0.0)
# ── SL / TP constants ─────────────────────────────────────────
TP_MULT    = 1.5          # default TP = SL × TP_MULT

# ── Virtual SL / Trailing ─────────────────────────────────────
VIRTUAL_SL       = True
TRAILING_SL      = True
TRAIL_AFTER_R    = 1.0    # start trailing after 1R profit
BREAKEVEN_BUFFER = 2.0    # vSL moves to entry + $2 at breakeven

# ── Partial Close (data-validated: 36% of trades go >2R after 1.5R) ──
PARTIAL_CLOSE_ENABLED = True
PARTIAL_CLOSE_R       = 1.5    # close 50% at 1.5R
PARTIAL_CLOSE_PCT     = 0.50
PARTIAL_CLOSE_TP2_R   = 3.0    # remaining 50% targets 3R

# ── Partial Breakeven steps ───────────────────────────────────
PARTIAL_BE_1_R      = 0.3
PARTIAL_BE_1_BUFFER = 15.0
PARTIAL_BE_2_R      = 0.5
PARTIAL_BE_2_BUFFER = 5.0

# ── Smart Exit ────────────────────────────────────────────────
SMART_EXIT_ENABLED       = True
SMART_EXIT_PEAK_DROP     = 0.55   # close if profit drops to 55% of peak
SMART_EXIT_MIN_PEAK_R    = 0.5    # only activate if peak > 0.5R
SMART_EXIT_PEAK_R_MULT   = 1.0    # peak threshold = risk_dollar × 1.0
SMART_EXIT_PROFIT_R_MULT = 0.7    # HMM exit threshold = risk_dollar × 0.7
SMART_EXIT_HMM_RANGING   = True
SMART_EXIT_MIN_OPEN_H    = 1.0

# Trade-2 equity SL REMOVED 2026-06-19 — risk = per-trade 3% (risk_pct) + daily 9% (DAILY_SL).

# ── Maximum simultaneous open positions ───────────────────────
MAX_SIMULTANEOUS = 1

# ── Test mode ─────────────────────────────────────────────────
TEST_MODE = False

# ── Signal evaluation bar (FIX #8) ────────────────────────────
# True  = evaluate features on the LAST CLOSED M15 bar (matches training)
# False = old behavior: forming bar (seconds old, near-empty candle)
USE_CLOSED_BAR = True

# ── Broker timezone (UTC+3) ───────────────────────────────────
try:
    from zoneinfo import ZoneInfo
    BROKER_TZ = ZoneInfo("Etc/GMT-3")
except Exception:
    BROKER_TZ = timezone(timedelta(hours=3))

# ── Symbol info cache ─────────────────────────────────────────
_sym_info_cache    = None
_sym_info_cache_ts = 0.0

def get_sym_info():
    """Cached mt5.symbol_info() — refreshed once per bar."""
    global _sym_info_cache, _sym_info_cache_ts
    now = time.monotonic()
    if _sym_info_cache is None or (now - _sym_info_cache_ts) > 30:
        _sym_info_cache    = mt5.symbol_info(SYMBOL)
        _sym_info_cache_ts = now
    return _sym_info_cache

def sym_point() -> float:
    si = get_sym_info()
    return si.point if si else 0.01

# ── Broker time helpers ───────────────────────────────────────
def broker_day_start_ts(tick_unix=None) -> int:
    """
    Broker-encoded unix timestamp of broker midnight.
    MT5 epochs ENCODE broker wall-clock as if UTC.
    Interpret with tz=utc to get broker wall-clock, take midnight.
    """
    if tick_unix:
        now_b = datetime.fromtimestamp(tick_unix, tz=timezone.utc)
    else:
        tick = mt5.symbol_info_tick(SYMBOL)
        if tick:
            now_b = datetime.fromtimestamp(tick.time, tz=timezone.utc)
        else:
            now_b = datetime.now(timezone.utc) + timedelta(hours=3)
    midnight_b = now_b.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight_b.timestamp())

def broker_now_ts(tick_unix=None) -> int:
    """Current broker wall-clock as unix timestamp."""
    if tick_unix:
        return tick_unix
    tick = mt5.symbol_info_tick(SYMBOL)
    return tick.time if tick else int(datetime.now(timezone.utc).timestamp())

def broker_now_dt(tick_unix=None) -> datetime:
    """Current broker wall-clock as datetime (tz=UTC, encodes broker time)."""
    return datetime.fromtimestamp(broker_now_ts(tick_unix), tz=timezone.utc)

# ── SQLite connection ─────────────────────────────────────────
def db_conn():
    """WAL-mode SQLite connection to qgai.db."""
    conn = sqlite3.connect(str(CFG.paths.db_path), timeout=5, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def ensure_db():
    """Create tables if they don't exist."""
    conn = db_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            bar_time     TEXT NOT NULL,
            mode         TEXT NOT NULL,
            signal       TEXT,
            win_prob     REAL, state_prob REAL, dir_prob REAL, big_win_prob REAL,
            hmm_state    TEXT,
            price        REAL, lot REAL, sl REAL, tp REAL,
            atr20_pct    REAL, vol_spike INTEGER, in_range_phase INTEGER,
            slot_wr      REAL, h4_bull_ob_dist REAL, h4_bear_ob_dist REAL,
            reason       TEXT, outcome TEXT, pnl_net REAL,
            UNIQUE(bar_time, mode)
        );
        CREATE INDEX IF NOT EXISTS idx_sig_bar    ON signals(bar_time);
        CREATE INDEX IF NOT EXISTS idx_sig_mode   ON signals(mode);
        CREATE INDEX IF NOT EXISTS idx_sig_outcome ON signals(outcome);

        CREATE TABLE IF NOT EXISTS trades (
            ticket       INTEGER PRIMARY KEY,
            direction    TEXT, entry_price REAL, exit_price REAL,
            entry_time   TEXT, exit_time TEXT,
            lot REAL, sl_dist REAL, vsl_price REAL, tp_price REAL,
            pnl_gross REAL, pnl_net REAL, commission REAL, swap REAL,
            r_achieved REAL, hmm_state TEXT, atr_pct REAL, win_prob REAL,
            bar_time TEXT, partial_closed INTEGER DEFAULT 0, comment TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_trades_entry ON trades(entry_time);

        CREATE TABLE IF NOT EXISTS shadow_slots (
            slot_key       TEXT PRIMARY KEY,
            slot TEXT, day TEXT,
            observations   INTEGER DEFAULT 0,
            signals_count  INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0,
            win_rate REAL DEFAULT 0.0,
            total_win_prob REAL DEFAULT 0.0,
            avg_win_prob   REAL DEFAULT 0.0,
            last_seen TEXT
        );

        CREATE TABLE IF NOT EXISTS daily_summary (
            trade_date   TEXT PRIMARY KEY,
            trades INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            gross_pnl REAL DEFAULT 0.0,
            day_open_bal REAL DEFAULT 0.0
        );
    """)
    conn.close()
