"""
Fundamental Engine — Main Configuration
=========================================
Operational settings: paths, time windows, observation parameters,
weighting schemes.

Module: fundamental_engine.config.fundamental_config
"""

# ============================================================
# FILE PATHS
# ============================================================

# SQLite database location
DB_PATH = r"C:\QGAI\data\fundamental\gold_engine.db"

# Price data source (XAUUSD M15 from QGAI shared data)
M15_PRICE_FILE = r"C:\QGAI\data\live\ohlc_live.csv"

# Audit and log outputs
AUDIT_OUTPUT_DIR = r"C:\QGAI\fundamental_engine\audit\audit_outputs"
LOG_DIR = r"C:\QGAI\fundamental_engine\logs"


# ============================================================
# ENGINE METADATA
# ============================================================

ENGINE_NAME = "Gold News-Aware Fundamental Engine"
ENGINE_VERSION = "1.0.0"
INSTRUMENT = "XAUUSD"


# ============================================================
# MODE TIME WINDOWS (in minutes, relative to event T-0)
# ============================================================

# Pre-event sub-phases
MODE_WINDOWS = {
    "EARLY_WARNING":    (-60, -30),    # T-1hr  to T-30min
    "ACTIVE_CAUTION":   (-30, -15),    # T-30m  to T-15min
    "IMMEDIATE_RISK":   (-15,  0),     # T-15m  to T-0
    "POST_EVENT":       (  0, 15),     # T+0    to T+15min
    "COOLDOWN":         ( 15, 30),     # T+15m  to T+30min
}

# Steady mode if no event in this window (minutes before/after)
STEADY_LOOKBACK_MIN = 30      # No event in last 30 min
STEADY_LOOKAHEAD_MIN = 60     # No event in next 60 min


# ============================================================
# DIRECTION OBSERVATION (post-event)
# ============================================================

# Window after release to observe direction (minutes)
# Aligned with M15 candle (1 candle = 15 min)
DIRECTION_OBSERVATION_WINDOW_MIN = 15

# Price buffer ($USD) - move must exceed this to count as directional
# Filters out spike noise
DIRECTION_BUFFER_USD = 2.0


# ============================================================
# HISTORICAL LOOKUP WEIGHTING
# ============================================================

# Time-decay weights for historical reactions
# Recent data weighted higher (current regime relevance)
TIMEDECAY_WEIGHTS = {
    "0_6_months":    0.50,
    "6_18_months":   0.25,
    "18_30_months":  0.15,
    "30_48_months":  0.10,
}

# Hit rate timeframe weighting
# 60min more reliable than 15min (less spike noise)
HIT_RATE_WEIGHTS = {
    "15min": 0.40,
    "60min": 0.60,
}


# ============================================================
# DATA INGESTION
# ============================================================

# ForexFactory live calendar JSON endpoint
FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# HTTP request settings
HTTP_TIMEOUT_SEC = 30
HTTP_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


# ============================================================
# LOGGING
# ============================================================

LOG_LEVEL = "INFO"      # DEBUG, INFO, WARNING, ERROR
LOG_FILE = r"C:\QGAI\fundamental_engine\logs\engine.log"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(module)s | %(message)s"


# ============================================================
# SAFETY / VALIDATION
# ============================================================

# Maximum acceptable Z-score (quarantine outliers above this)
MAX_VALID_Z_SCORE = 5.0

# Minimum candles needed for direction observation
MIN_M15_CANDLES_POST_EVENT = 1

# ============================================================
# SIGNAL FILTERING
# ============================================================

# Minimum currency_weight for an event to contribute to the fundamental view.
# Events from currencies with lower relevance than this are skipped.
#
# Backtested 15-min hit rates (events_csv_import + events_investing_raw, 14k events):
#   USD = 54.7%  ← only reliable signal
#   EUR = 48.6%  ← below random (noise, excluded)
#   GBP = 48.2%  ← below random (noise, excluded)
#   JPY = 44.1%  ← actively harmful (excluded)
#   CNY = 50.0%  ← coin flip (excluded)
#   All others   ← noise or tiny samples (excluded)
#
# Conclusion: only USD data has predictive power in the 15-min gold window.
# Set to 0.8 so only USD (weight=1.0) passes. Raise to 0.7 to include EUR
# if future data shows EUR hit rate improving above 52%.
MIN_CURRENCY_WEIGHT = 0.8

# Event types excluded from fundamental view (hit rate below 50% in backtests).
# Trade events (48.3%) are complex, directionally unreliable in 15-min window.
# To re-enable: remove from this set.
EXCLUDED_EVENT_TYPES = {"trade"}
