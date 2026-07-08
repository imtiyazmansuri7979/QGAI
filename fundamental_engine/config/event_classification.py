"""
Fundamental Engine — Event Classification
===========================================
Hybrid classification: pattern-based event type detection
+ special handlers + selective overrides for specific events.

Module: fundamental_engine.config.event_classification
"""

# ============================================================
# EVENT TYPE PATTERNS
# ============================================================
# Pattern-based classification of event_name → event_type
# Patterns are case-insensitive substring matches
# First matching type wins (order matters for ambiguous events)

EVENT_TYPE_PATTERNS = {

    # ----- Monetary Policy -----
    "rate_decision": {
        "patterns": [
            "Federal Funds Rate",
            "Main Refinancing Rate",
            "Overnight Rate",
            "Official Bank Rate",
            "Cash Rate",
            "Policy Rate",
            "Bank Rate",
            "Interest Rate Decision",
        ],
        "direction_rule": "hawkish_bearish_gold",
        "base_weight": 1.0,
        "priority": 100,
    },

    # ----- Inflation -----
    "inflation": {
        "patterns": [
            "CPI",
            "Core CPI",
            "PCE",
            "Core PCE",
            "PPI",
            "Core PPI",
            "Inflation Rate",
            "Trimmed Mean",
        ],
        "direction_rule": "higher_bearish_gold",  # Post-2022 regime
        "base_weight": 0.9,
        "priority": 90,
    },

    # ----- Employment -----
    "jobs": {
        "patterns": [
            "Non-Farm Employment",
            "Non-Farm Payrolls",
            "NFP",
            "Unemployment Rate",
            "Initial Jobless Claims",
            "Continuing Jobless",
            "Average Hourly Earnings",
            "Employment Change",
            "ADP",
        ],
        "direction_rule": "stronger_bearish_gold",
        "base_weight": 0.9,
        "priority": 85,
    },

    # ----- Growth / Activity -----
    "growth": {
        "patterns": [
            "GDP",
            "ISM Manufacturing",
            "ISM Services",
            "PMI",
            "Retail Sales",
            "Core Retail Sales",
            "Industrial Production",
            "Durable Goods",
            "Factory Orders",
        ],
        "direction_rule": "stronger_bearish_gold",
        "base_weight": 0.7,
        "priority": 75,
    },

    # ----- Sentiment / Surveys -----
    "sentiment": {
        "patterns": [
            "Consumer Confidence",
            "Consumer Sentiment",
            "Michigan",
            "ZEW",
            "Ifo",
            "Tankan",
            "Business Confidence",
            "Manufacturing Confidence",
        ],
        "direction_rule": "stronger_bearish_gold",
        "base_weight": 0.5,
        "priority": 50,
    },

    # ----- Qualitative (Fed Speak, Statements) -----
    "qualitative": {
        "patterns": [
            "Statement",
            "Press Conference",
            "Minutes",
            "Speech",
            "Testimony",
            "Monetary Policy Statement",
            "Outlook Report",
            "Hearings",
        ],
        "direction_rule": "tone_based",       # Requires interpretation
        "base_weight": 0.6,
        "priority": 60,
    },

    # ----- Housing -----
    "housing": {
        "patterns": [
            "Housing Starts",
            "Building Permits",
            "Existing Home Sales",
            "New Home Sales",
            "Pending Home Sales",
            "Case-Shiller",
        ],
        "direction_rule": "stronger_bearish_gold",
        "base_weight": 0.4,
        "priority": 40,
    },

    # ----- Trade -----
    "trade": {
        "patterns": [
            "Trade Balance",
            "Current Account",
            "Exports",
            "Imports",
        ],
        "direction_rule": "higher_bearish_gold",  # Higher = currency strong = bearish gold
                                                   # NOTE: "Imports" is INVERSE — handled in classifier
        "base_weight": 0.4,
        "priority": 30,
    },
}


# ============================================================
# CURRENCY RELEVANCE TO GOLD
# ============================================================
# Multiplier applied to base_weight based on currency
# 1.0 = full impact, 0.0 = irrelevant

CURRENCY_RELEVANCE = {
    "USD":  1.0,      # Direct inverse driver
    "EUR":  0.7,      # DXY 57% weight, indirect
    "CNY":  0.5,      # China Gold demand
    "GBP":  0.4,      # DXY 12% weight
    "JPY":  0.4,      # Safe haven competition
    "CHF":  0.2,      # Safe haven competition (minor)
    "CAD":  0.2,      # DXY 9% weight, oil correlation
    "AUD":  0.2,      # Commodity currency
    "NZD":  0.1,      # Minor
    "SEK":  0.1,      # DXY 4% weight only
    "All":  0.3,      # Regional/global events (OPEC, etc.)
}


# ============================================================
# SPECIAL HANDLERS
# ============================================================
# Events requiring special composite logic beyond pattern matching
# Override pattern classification when present

SPECIAL_HANDLERS = {

    # NFP composite — headline + earnings + unemployment combined
    "Non-Farm Employment Change": {
        "handler": "nfp_composite",
        "components": [
            "Non-Farm Employment Change",
            "Unemployment Rate",
            "Average Hourly Earnings m/m",
        ],
        "weights": [0.50, -0.20, 0.30],   # Earnings positive, unemployment inverse
        "currency": "USD",
    },

    # CPI with Core priority
    "CPI y/y": {
        "handler": "cpi_with_core_priority",
        "priority_event": "Core CPI y/y",
        "currency": "USD",
        "comment": "If Core CPI same release, weight Core higher than headline",
    },

    # Rate decisions — basis points based surprise
    "Federal Funds Rate": {
        "handler": "rate_decision_bps",
        "min_surprise_bps": 5,            # Below 5 bps = priced in, ignore
        "currency": "USD",
    },

    "Main Refinancing Rate": {
        "handler": "rate_decision_bps",
        "min_surprise_bps": 5,
        "currency": "EUR",
    },

    "Official Bank Rate": {
        "handler": "rate_decision_bps",
        "min_surprise_bps": 5,
        "currency": "GBP",
    },

    "Overnight Rate": {
        "handler": "rate_decision_bps",
        "min_surprise_bps": 5,
        "currency": "CAD",
    },
}


# ============================================================
# SELECTIVE EVENT OVERRIDES
# ============================================================
# Override pattern classification for specific events
# Useful for events that don't fit standard patterns

EVENT_OVERRIDES = {

    # OPEC meetings — commodity event, not standard currency
    "OPEC-JMMC Meetings": {
        "event_type": "commodity_event",
        "direction_rule": "complex",
        "base_weight": 0.5,
        "skip_engine": False,
    },

    "OPEC Meetings": {
        "event_type": "commodity_event",
        "direction_rule": "complex",
        "base_weight": 0.5,
        "skip_engine": False,
    },

    # Bank holidays — no actual data event
    "Bank Holiday": {
        "skip_engine": True,
    },

    # Add more overrides as discovered through data flow
}


# ============================================================
# DIRECTION RULE INTERPRETATIONS
# ============================================================
# How each direction_rule translates to Gold direction
# Reference for engine logic

DIRECTION_RULE_LOGIC = {
    "higher_bearish_gold":
        "Higher actual vs forecast → Gold bearish (e.g., high CPI = hawkish Fed = Gold down)",
    "hawkish_bearish_gold":
        "Rate hike larger than expected → Gold bearish; dovish surprise → Gold bullish",
    "stronger_bearish_gold":
        "Strong economic data (jobs, growth, sentiment) → Gold bearish (risk-on, Fed hawkish)",
    "tone_based":
        "Qualitative event — requires NLP/sentiment interpretation, default neutral",
    "complex":
        "Multi-factor event — context-dependent, engine flags for manual review",
}


# ============================================================
# CURRENCY-SPECIFIC DIRECTION ADJUSTMENT
# ============================================================
# Non-USD events: stronger currency means weaker USD which means stronger Gold
# This flips the direction for non-USD events

CURRENCY_DIRECTION_FLIP = {
    "USD": False,    # USD strong = Gold weak (no flip)
    "EUR": True,     # EUR strong = USD weak = Gold strong (flip)
    "GBP": True,     # Same
    "CNY": False,    # Complex - China demand can override
    "JPY": False,    # Safe haven dynamic complex
    "CHF": False,    # Safe haven dynamic complex
    "CAD": True,     # CAD strong = USD weak = Gold strong (flip)
    "AUD": True,
    "NZD": True,
    "SEK": True,
    "All": False,    # No flip applied
}
