"""
Fundamental Engine — Thresholds & Grade Rules
==============================================
Z-score thresholds, confidence mappings, alignment adjustments,
grade A/B/C requirements.

Module: fundamental_engine.config.thresholds
"""

# ============================================================
# SURPRISE NORMALIZATION
# ============================================================

# Rolling window depth for surprise history
# Per-event last N surprises used to calculate Z-score
SURPRISE_HISTORY_DEPTH = 20

# Minimum samples for valid Z-score
# Below this, fall back to absolute threshold per event
MIN_SAMPLES_FOR_ZSCORE = 5


# ============================================================
# Z-SCORE THRESHOLDS PER IMPACT TIER
# ============================================================

# Minimum |Z| for engine to consider event significant
# Higher tier = lower bar (always-moving events)
# Lower tier = higher bar (need bigger surprise to overcome noise)
Z_THRESHOLDS = {
    3: 1.0,     # 3-star (High impact)
    2: 1.8,     # 2-star (Medium impact)
    1: 2.5,     # 1-star (Low - mostly ignored, very high bar)
}


# ============================================================
# HISTORICAL REACTION LOOKUP
# ============================================================

# Z-score tolerance for "similar event" matching
# Past events with Z within ±tolerance considered matches
Z_MATCH_TOLERANCE = 0.5

# Minimum historical samples to compute reliable hit rate
MIN_HISTORICAL_SAMPLES = 5

# Max lookback for relevance (months)
# Older data considered but heavily down-weighted (see TIMEDECAY_WEIGHTS)
MAX_HISTORICAL_LOOKBACK_MONTHS = 48


# ============================================================
# CONFIDENCE CALCULATION
# ============================================================

# Hit rate → confidence mapping
# Format: sorted list of (hit_rate_threshold, confidence_value)
# Find highest threshold where hit_rate >= threshold
CONFIDENCE_MAPPING = [
    (0.75, 0.90),     # ≥75% hit rate → 0.90 confidence
    (0.65, 0.70),     # ≥65% → 0.70
    (0.55, 0.50),     # ≥55% → 0.50
    (0.00, 0.20),     # below 55% → 0.20 (low confidence flag)
]

# Default confidence when historical samples insufficient
DEFAULT_LOW_CONFIDENCE = 0.30


# ============================================================
# ALIGNMENT ADJUSTMENTS
# ============================================================

# Fundamental view (predicted) vs observed direction
# Adjustments applied to base confidence

ALIGNMENT_BOOST = 0.10        # Fundamental + observed both same direction
ALIGNMENT_PENALTY = -0.30     # Fundamental opposite of observed (regime/interpretation issue)
MUTED_PENALTY = -0.10         # Observed direction flat (no market reaction)


# ============================================================
# GRADE REQUIREMENTS
# ============================================================

# Grade A: Highest conviction signal
GRADE_A_REQUIREMENTS = {
    "min_tier": 3,                  # 3-star event minimum
    "min_z_score": 1.5,             # Strong surprise
    "min_hit_rate": 0.70,           # 70%+ historical accuracy
    "alignment_required": "match",   # Fundamental matches observed
    "min_sample_size": 5,
}

# Grade B: Medium conviction
GRADE_B_REQUIREMENTS = {
    "min_tier": 2,
    "min_z_score": 1.0,
    "min_hit_rate": 0.55,
    "alignment_required": "any",     # Can be match, conflict, or muted
    "min_sample_size": 3,
}

# Grade C: Low conviction (signal generated but flagged)
# Anything not meeting A or B → C


# ============================================================
# OUTPUT THRESHOLDS
# ============================================================

# Minimum signal grade for engine to emit any action
# 'C' grade signals logged but may be filtered by integration layer
MIN_OUTPUT_GRADE = "C"

# Confidence floor — below this, output "NO_FUNDAMENTAL_VIEW"
MIN_OUTPUT_CONFIDENCE = 0.15
