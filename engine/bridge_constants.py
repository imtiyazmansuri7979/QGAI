"""
bridge_constants.py — QUANT GOLD AI v2
Shared constants, imports and MT5 utility helpers.
All other bridge modules import from here.
"""
import MetaTrader5 as mt5
import os, time, logging, sys, json, re, sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import CFG

# ── Logging ───────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

_ANSI_RESET = "\033[0m"
_ANSI_DIM = "\033[2m"
_ANSI_RED = "\033[91m"
_ANSI_GREEN = "\033[92m"
_ANSI_YELLOW = "\033[93m"
_ANSI_BLUE = "\033[94m"
_ANSI_MAGENTA = "\033[95m"
_ANSI_CYAN = "\033[96m"
_ANSI_WHITE = "\033[97m"
_ANSI_BOLD = "\033[1m"
_ANSI_ORANGE = "\033[38;2;255;152;0m"
_ANSI_BG_RED = "\033[48;2;92;49;43m"
_ANSI_BG_GREEN = "\033[48;2;42;83;49m"
_ANSI_BG_BLUE = "\033[48;2;18;52;74m"


def _apply_bridge_console_theme():
    """Set the bridge CMD window to a dark editor-like base theme."""
    if os.environ.get("QGAI_NO_COLOR") or os.environ.get("NO_COLOR"):
        return
    if os.name == "nt" and os.environ.get("QGAI_BRIDGE_CONSOLE_THEME", "1") != "0":
        try:
            os.system("color 0F")
        except Exception:
            pass


def _enable_console_color():
    """Enable ANSI colors in Windows console without adding dependencies."""
    if os.environ.get("NO_COLOR") or os.environ.get("QGAI_NO_COLOR"):
        return False
    if not sys.stderr.isatty():
        return False
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        enabled = False
        for handle_id in (-11, -12):  # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_uint()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                enabled = bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004)) or enabled
        return enabled
    except Exception:
        return False


_CONSOLE_COLOR = _enable_console_color()


class _BridgeConsoleFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: _ANSI_DIM,
        logging.INFO: _ANSI_WHITE,
        logging.WARNING: _ANSI_YELLOW + _ANSI_BOLD,
        logging.ERROR: _ANSI_RED + _ANSI_BOLD,
        logging.CRITICAL: _ANSI_RED + _ANSI_BOLD,
    }

    KEYWORD_COLORS = [
        (r"\b(ERROR|FAILED|failed|fail|halt|DAILY RATCHET HIT|NO broker SL|Access is denied|WinError)\b", _ANSI_BG_RED + _ANSI_WHITE + _ANSI_BOLD),
        (r"\b(BUY|LONG|ENTRY BUY)\b", _ANSI_BG_GREEN + _ANSI_GREEN + _ANSI_BOLD),
        (r"\b(SELL|SHORT|ENTRY SELL)\b", _ANSI_BG_RED + _ANSI_RED + _ANSI_BOLD),
        (r"\b(SKIP|BLOCK|BLOCKED|Outside slot|SPREAD GUARD|DD BRAKE|Force-closing)\b", _ANSI_YELLOW + _ANSI_BOLD),
        (r"\b(WARNING|watch|stale|timeout)\b", _ANSI_YELLOW + _ANSI_BOLD),
        (r"\b(connected|reconnected|ready|loaded|complete|UNLOCKED|OK|ALIVE|DONE|saved|live)\b", _ANSI_GREEN + _ANSI_BOLD),
        (r"\b(vSL|RATCHET|ratchet|TP|SL|ENTRY GATES|win_prob|prob|threshold)\b", _ANSI_CYAN + _ANSI_BOLD),
        (r"\b(manual|Secondary|Primary|multi)\b", _ANSI_MAGENTA + _ANSI_BOLD),
        (r"\b(XAUUSD(?:s|\.pc)?|M15|M30|H1|H4|D1)\b", _ANSI_BLUE + _ANSI_BOLD),
        # regime names — mirrors the dashboard's Trending=green/Volatile=orange/Ranging=red convention
        (r"\bTrending\b", _ANSI_GREEN + _ANSI_BOLD),
        (r"\bVolatile\b", _ANSI_ORANGE + _ANSI_BOLD),
        (r"\bRanging\b", _ANSI_RED + _ANSI_BOLD),
        # structural/event markers
        (r"\bNew bar\b", _ANSI_MAGENTA + _ANSI_BOLD),
        (r"\bBroker\b", _ANSI_BLUE + _ANSI_BOLD),
        (r"\bheartbeat\b", _ANSI_CYAN + _ANSI_BOLD),
        # de-emphasize plain labels so the values next to them pop by contrast
        (r"\b(price|last bar)\b", _ANSI_DIM),
        # HH:MM / HH:MM:SS timestamps not already at line-start
        (r"(?<!^)\b\d{1,2}:\d{2}(?::\d{2})?\b", _ANSI_CYAN),
        (r"[$][0-9,]+(?:\.[0-9]+)?", _ANSI_GREEN + _ANSI_BOLD),
        (r"\b\d+(?:\.\d+)?%", _ANSI_YELLOW + _ANSI_BOLD),
        (r"\b[+-]?[0-9]+(?:\.[0-9]+)?R\b", _ANSI_YELLOW + _ANSI_BOLD),
        # bare price-looking decimals (e.g. 3988.33) not already tagged as $/R/% above
        (r"(?<![\d.$,])\b\d{3,5}\.\d{1,2}\b(?!\s*R\b)(?!%)", _ANSI_CYAN + _ANSI_BOLD),
    ]

    def format(self, record):
        if not _CONSOLE_COLOR:
            return super().format(record)

        record_copy = logging.makeLogRecord(record.__dict__.copy())
        record_copy.levelname = self._paint(record.levelname, self.LEVEL_COLORS.get(record.levelno, ""))
        record_copy.msg = self._color_message(record.getMessage())
        record_copy.args = ()

        line = super().format(record_copy)
        line = re.sub(
            r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})",
            lambda m: self._paint(m.group(1), _ANSI_DIM),
            line,
        )
        return line

    @staticmethod
    def _paint(text, color):
        return f"{color}{text}{_ANSI_RESET}" if color else text

    @classmethod
    def _color_message(cls, message):
        colored = message
        for pattern, color in cls.KEYWORD_COLORS:
            colored = re.sub(pattern, lambda m: cls._paint(m.group(0), color), colored, flags=re.IGNORECASE)
        return colored


def _setup_bridge_logging():
    Path(CFG.paths.logs_dir).mkdir(parents=True, exist_ok=True)
    _apply_bridge_console_theme()

    logger = logging.getLogger("QGAI")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(_BridgeConsoleFormatter(LOG_FORMAT))

    file_handler = logging.FileHandler(Path(CFG.paths.logs_dir) / "bridge.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


log = _setup_bridge_logging()

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
    _ensure_signal_immutable_schema(conn)
    conn.close()


def _ensure_signal_immutable_schema(conn):
    """Migrate signals to immutable per-inference rows.

    Older DBs used UNIQUE(bar_time, mode), so a later evaluation of the same
    candle could be silently ignored by INSERT OR IGNORE. This migration keeps
    all historical rows but removes that uniqueness constraint and adds audit
    fields needed to prove old signals do not repaint after refresh/restart.
    """
    cols = [r[1] for r in conn.execute("PRAGMA table_info(signals)").fetchall()]
    if not cols:
        return

    required = {
        "signal_id": "TEXT",
        "signal_created_at": "TEXT",
        "market_timestamp": "TEXT",
        "symbol": "TEXT",
        "timeframe": "TEXT",
        "decision_threshold": "REAL",
        "combined_model_score": "REAL",
        "state_model_score": "REAL",
        "directional_model_score": "REAL",
        "model_version": "TEXT",
        "model_hash": "TEXT",
        "model_file_name": "TEXT",
        "feature_snapshot_json": "TEXT",
        "feature_hash": "TEXT",
        "decision": "TEXT",
        "signal_status": "TEXT",
        "trade_action": "TEXT DEFAULT ''",
    }
    for name, ddl in required.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE signals ADD COLUMN {name} {ddl}")
    conn.commit()

    idx_rows = conn.execute("PRAGMA index_list(signals)").fetchall()
    has_bar_mode_unique = False
    for idx in idx_rows:
        idx_name = idx[1]
        is_unique = bool(idx[2])
        if not is_unique:
            continue
        idx_cols = [r[2] for r in conn.execute(f"PRAGMA index_info({idx_name})").fetchall()]
        if idx_cols == ["bar_time", "mode"]:
            has_bar_mode_unique = True
            break

    if has_bar_mode_unique:
        conn.execute("ALTER TABLE signals RENAME TO signals_legacy_unique")
        conn.executescript("""
            CREATE TABLE signals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id    TEXT UNIQUE,
                signal_created_at TEXT,
                market_timestamp TEXT,
                symbol       TEXT,
                timeframe    TEXT,
                bar_time     TEXT NOT NULL,
                mode         TEXT NOT NULL,
                signal       TEXT,
                win_prob     REAL, state_prob REAL, dir_prob REAL, big_win_prob REAL,
                hmm_state    TEXT,
                price        REAL, lot REAL, sl REAL, tp REAL,
                atr20_pct    REAL, vol_spike INTEGER, in_range_phase INTEGER,
                slot_wr      REAL, h4_bull_ob_dist REAL, h4_bear_ob_dist REAL,
                reason       TEXT, outcome TEXT, pnl_net REAL,
                trade_action TEXT DEFAULT '',
                model_version TEXT,
                model_hash TEXT,
                model_file_name TEXT,
                decision_threshold REAL,
                combined_model_score REAL,
                state_model_score REAL,
                directional_model_score REAL,
                feature_snapshot_json TEXT,
                feature_hash TEXT,
                decision TEXT,
                signal_status TEXT
            );
        """)
        old_cols = [r[1] for r in conn.execute("PRAGMA table_info(signals_legacy_unique)").fetchall()]
        copy_cols = [c for c in old_cols if c in [r[1] for r in conn.execute("PRAGMA table_info(signals)").fetchall()]]
        col_sql = ",".join(copy_cols)
        conn.execute(f"INSERT INTO signals ({col_sql}) SELECT {col_sql} FROM signals_legacy_unique")
        conn.execute("""
            UPDATE signals
            SET signal_id = COALESCE(signal_id, 'LEGACY_' || id || '_' || REPLACE(REPLACE(bar_time, ' ', '_'), ':', '') || '_' || mode),
                signal_created_at = COALESCE(signal_created_at, bar_time),
                market_timestamp = COALESCE(market_timestamp, bar_time),
                symbol = COALESCE(symbol, ?),
                timeframe = COALESCE(timeframe, 'M15'),
                decision_threshold = COALESCE(decision_threshold, 0.45),
                combined_model_score = COALESCE(combined_model_score, win_prob),
                state_model_score = COALESCE(state_model_score, state_prob),
                directional_model_score = COALESCE(directional_model_score, dir_prob),
                decision = COALESCE(decision, signal),
                signal_status = COALESCE(signal_status, 'HISTORICAL_IMPORTED')
        """, (SYMBOL,))
        conn.execute("DROP TABLE signals_legacy_unique")

    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sig_signal_id ON signals(signal_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sig_created ON signals(signal_created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sig_market ON signals(market_timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sig_bar    ON signals(bar_time)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sig_mode   ON signals(mode)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sig_outcome ON signals(outcome)")
    conn.commit()
