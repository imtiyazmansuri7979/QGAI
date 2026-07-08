"""
Fundamental Engine — Config Package
=====================================
Configuration package for the Gold News-Aware Fundamental Engine.

Modules:
  fundamental_config    — Operational settings (paths, time windows, weights)
  thresholds            — Z-score thresholds, confidence, grade rules
  event_classification  — Pattern rules, special handlers, overrides

Usage:
  from fundamental_engine.config import fundamental_config as fc
  from fundamental_engine.config import thresholds as th
  from fundamental_engine.config import event_classification as ec

  print(fc.DB_PATH)
  print(th.Z_THRESHOLDS[3])
  print(ec.EVENT_TYPE_PATTERNS["inflation"])
"""

# Re-export commonly used names for convenience
from .fundamental_config import (
    DB_PATH,
    M15_PRICE_FILE,
    AUDIT_OUTPUT_DIR,
    ENGINE_NAME,
    ENGINE_VERSION,
    INSTRUMENT,
    MODE_WINDOWS,
    DIRECTION_OBSERVATION_WINDOW_MIN,
    DIRECTION_BUFFER_USD,
    TIMEDECAY_WEIGHTS,
    HIT_RATE_WEIGHTS,
    FF_CALENDAR_URL,
)

from .thresholds import (
    SURPRISE_HISTORY_DEPTH,
    Z_THRESHOLDS,
    Z_MATCH_TOLERANCE,
    MIN_HISTORICAL_SAMPLES,
    CONFIDENCE_MAPPING,
    ALIGNMENT_BOOST,
    ALIGNMENT_PENALTY,
    MUTED_PENALTY,
    GRADE_A_REQUIREMENTS,
    GRADE_B_REQUIREMENTS,
)

from .event_classification import (
    EVENT_TYPE_PATTERNS,
    CURRENCY_RELEVANCE,
    SPECIAL_HANDLERS,
    EVENT_OVERRIDES,
    CURRENCY_DIRECTION_FLIP,
)

__version__ = "1.0.0"
