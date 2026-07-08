"""
Fundamental Engine — Core Public API (Step 3) — FIXED
======================================================
Main entry point: evaluate(technical_state, current_time)

Bug fix: handle None value for position_direction properly.

Module: fundamental_engine.core.engine
Version: 1.0.0
"""

import sys
import os
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

# PATH SETUP
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc
from config import thresholds as th
from config import event_classification as ec

# LOGGING
os.makedirs(os.path.dirname(fc.LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format=fc.LOG_FORMAT,
    handlers=[
        logging.FileHandler(fc.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("engine")

ENGINE_VERSION = "1.0.0"

MODE_WINDOWS = getattr(fc, "MODE_WINDOWS", {
    "EARLY_WARNING":   {"from": 60,  "to": 30},
    "ACTIVE_CAUTION":  {"from": 30,  "to": 15},
    "IMMEDIATE_RISK":  {"from": 15,  "to": 0},
    "POST_EVENT":      {"from": 0,   "to": 15},
    "COOLDOWN":        {"from": 15,  "to": 30},
})


def detect_mode(current_time: datetime, events: list) -> tuple:
    if not events:
        return "STEADY", None, None
    
    closest_event = None
    smallest_abs_diff = float('inf')
    
    for ev in events:
        try:
            ev_time = ev["release_time"]
            if isinstance(ev_time, str):
                ev_time = datetime.fromisoformat(ev_time.replace('Z', '+00:00'))
            if hasattr(ev_time, 'tzinfo') and ev_time.tzinfo is not None:
                ev_time = ev_time.replace(tzinfo=None)
            
            diff_minutes = (ev_time - current_time).total_seconds() / 60.0
            if abs(diff_minutes) < abs(smallest_abs_diff):
                smallest_abs_diff = diff_minutes
                closest_event = (ev_time, diff_minutes)
        except Exception:
            continue
    
    if closest_event is None:
        return "STEADY", None, None
    
    ev_time, diff_min = closest_event
    
    if diff_min > 0:
        if diff_min <= 15:
            return "IMMEDIATE_RISK", ev_time, diff_min
        elif diff_min <= 30:
            return "ACTIVE_CAUTION", ev_time, diff_min
        elif diff_min <= 60:
            return "EARLY_WARNING", ev_time, diff_min
        else:
            return "STEADY", ev_time, diff_min
    else:
        abs_diff = abs(diff_min)
        if abs_diff <= 15:
            return "POST_EVENT", ev_time, diff_min
        elif abs_diff <= 30:
            return "COOLDOWN", ev_time, diff_min
        else:
            return "STEADY", ev_time, diff_min


def get_events_in_window(conn, current_time, lookback_min=30, lookahead_min=60):
    window_start = current_time - timedelta(minutes=lookback_min)
    window_end = current_time + timedelta(minutes=lookahead_min)
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT classified_id, event_type, event_title, normalized_title, currency,
               release_time, impact_stars, tier,
               surprise_value, surprise_normalized, z_score,
               fundamental_direction, direction_confidence,
               currency_weight, event_weight, is_inverse
        FROM events_classified
        WHERE release_time >= ? AND release_time <= ?
        ORDER BY release_time ASC
    """, (window_start.isoformat(), window_end.isoformat()))
    
    events = []
    for row in cursor.fetchall():
        events.append({
            "classified_id": row[0], "event_type": row[1], "event_title": row[2],
            "normalized_title": row[3], "currency": row[4], "release_time": row[5],
            "impact_stars": row[6], "tier": row[7],
            "surprise_value": row[8], "surprise_normalized": row[9], "z_score": row[10],
            "fundamental_direction": row[11], "direction_confidence": row[12] or 0.0,
            "currency_weight": row[13] or 0.1, "event_weight": row[14] or 0.5,
            "is_inverse": row[15] or 0,
        })
    return events


def get_hit_rate(conn, event_type, currency, normalized_title=None):
    cursor = conn.cursor()
    
    if normalized_title:
        cursor.execute("""
            SELECT
                SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END),
                SUM(CASE WHEN direction_matched = 0 THEN 1 ELSE 0 END),
                SUM(CASE WHEN observed_direction = 'MUTED' THEN 1 ELSE 0 END),
                COUNT(*),
                AVG(ABS(move_15min_usd))
            FROM gold_reactions
            WHERE normalized_title = ? AND currency = ?
              AND data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
        """, (normalized_title, currency))
        row = cursor.fetchone()
        if row and row[3] and row[3] >= 5:
            return _format_hit_rate(row, "title_specific")
    
    cursor.execute("""
        SELECT
            SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN direction_matched = 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN observed_direction = 'MUTED' THEN 1 ELSE 0 END),
            COUNT(*),
            AVG(ABS(move_15min_usd))
        FROM gold_reactions
        WHERE event_type = ? AND currency = ?
          AND data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
    """, (event_type, currency))
    row = cursor.fetchone()
    if row and row[3] and row[3] >= 3:
        return _format_hit_rate(row, "type_currency")
    
    cursor.execute("""
        SELECT
            SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN direction_matched = 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN observed_direction = 'MUTED' THEN 1 ELSE 0 END),
            COUNT(*),
            AVG(ABS(move_15min_usd))
        FROM gold_reactions
        WHERE event_type = ?
          AND data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
    """, (event_type,))
    row = cursor.fetchone()
    if row and row[3] and row[3] >= 5:
        return _format_hit_rate(row, "type_only")
    
    return {
        "samples": 0, "matched": 0, "mismatched": 0, "muted": 0,
        "hit_rate_15min": None, "avg_move_usd": None, "data_quality": "insufficient",
    }


def _format_hit_rate(row, source):
    matched, mismatched, muted, total, avg_move = row
    matched = matched or 0
    mismatched = mismatched or 0
    muted = muted or 0
    determined = matched + mismatched
    return {
        "samples": total, "matched": matched, "mismatched": mismatched, "muted": muted,
        "hit_rate_15min": (matched / determined) if determined > 0 else None,
        "avg_move_usd": avg_move, "data_quality": source,
    }


def compose_fundamental_view(events, conn):
    if not events:
        return {"direction": "NEUTRAL", "strength": 0.0, "confidence": 0.0,
                "contributing_events": 0, "contributions": []}

    # --- DEDUPLICATION: one release = one signal ---
    # Investing.com/CSV exports many variants of the same release at the same
    # timestamp (e.g., CPI m/m, CPI y/y, Core CPI — all at 13:00).
    # Counting each as an independent event inflates the signal by 5-14x.
    # Fix: per (currency, release_time) group, keep only the HIGHEST-weighted
    # event (best tier × event_weight) so one release = one contribution.
    from collections import defaultdict as _defaultdict

    def _event_sort_key(ev):
        tier_val = {1: 3, 2: 2, 3: 1, 0: 0}.get(ev.get("tier") or 0, 0)
        return (tier_val, ev.get("event_weight", 0.5), ev.get("direction_confidence", 0.0))

    # Group non-NEUTRAL events by (currency, release_time)
    release_groups = _defaultdict(list)
    neutral_events = []
    for ev in events:
        if ev["fundamental_direction"] not in ("BULLISH_GOLD", "BEARISH_GOLD"):
            neutral_events.append(ev)
            continue
        key = (ev["currency"], ev["release_time"])
        release_groups[key].append(ev)

    # From each group, keep the single best representative event
    deduped_events = []
    for key, group in release_groups.items():
        best = max(group, key=_event_sort_key)
        deduped_events.append(best)
    # -----------------------------------------------

    bullish_weight = bearish_weight = total_weight = 0.0
    contributing = 0
    contributions = []

    # Minimum currency_weight to include in the view.
    # Currencies with weight < 0.2 (NZD, SEK, CHF, CAD, AUD) have an unreliable
    # and indirect relationship with gold. At 50% hit rate they are pure noise.
    # USD (1.0) and EUR (0.7) always pass. Raise this if hit rates stay near 50%.
    MIN_CURRENCY_WEIGHT = getattr(fc, "MIN_CURRENCY_WEIGHT", 0.3)

    # Event types that are statistically noise or harmful for gold prediction.
    # USD Trade Balance: 48.3% hit rate — worse than random in 15-min window.
    # Trade data is complex (exports vs imports, seasonality) and market reaction
    # is often already priced in or dominated by other simultaneous releases.
    EXCLUDED_EVENT_TYPES = getattr(fc, "EXCLUDED_EVENT_TYPES", {"trade"})

    for ev in deduped_events:
        if ev.get("currency_weight", 0) < MIN_CURRENCY_WEIGHT:
            continue  # skip noise currencies
        if ev.get("event_type") in EXCLUDED_EVENT_TYPES:
            continue  # skip event types with negative predictive value

        hit_rate_data = get_hit_rate(conn, ev["event_type"], ev["currency"], ev["normalized_title"])
        hit_rate = hit_rate_data.get("hit_rate_15min")

        # Tier multiplier — data-driven from 14k event backtest (USD only):
        #   Tier 3 (|Z|>=1.0): 57.1% hit rate  → highest weight
        #   Tier 2 (|Z|>=1.8): 54.9% hit rate  → medium weight
        #   Tier 0 (no Z):     54.3% hit rate  → base weight
        #   Tier 1 (|Z|>=2.5): 51.5% hit rate  → LOWEST (extreme surprises reverse)
        # "Buy the rumor, sell the news" effect: the strongest surprises are
        # already partially priced in, causing direction reversals.
        tier_mult = {0: 1.0, 3: 1.4, 2: 1.2, 1: 0.8}.get(ev["tier"], 1.0)

        if hit_rate is None:
            hr_mult = 0.7
        elif hit_rate >= 0.70:
            hr_mult = 1.5
        elif hit_rate >= 0.55:
            hr_mult = 1.0
        else:
            hr_mult = 0.5

        event_total_weight = (
            ev["currency_weight"] * ev["event_weight"] *
            tier_mult * hr_mult * ev["direction_confidence"]
        )

        if ev["fundamental_direction"] == "BULLISH_GOLD":
            bullish_weight += event_total_weight
        else:
            bearish_weight += event_total_weight

        total_weight += event_total_weight
        contributing += 1
        contributions.append({
            "event_title": ev["event_title"], "currency": ev["currency"],
            "direction": ev["fundamental_direction"], "weight": event_total_weight,
            "hit_rate": hit_rate,
            "hit_rate_samples": hit_rate_data.get("samples", 0),
        })
    
    if total_weight == 0:
        return {"direction": "NEUTRAL", "strength": 0.0, "confidence": 0.0,
                "contributing_events": 0, "contributions": contributions}
    
    net = (bullish_weight - bearish_weight) / total_weight
    
    if net > 0.3:
        direction, strength = "BULLISH_GOLD", net
    elif net < -0.3:
        direction, strength = "BEARISH_GOLD", abs(net)
    elif abs(net) > 0.1:
        direction = "BULLISH_GOLD" if net > 0 else "BEARISH_GOLD"
        strength = abs(net)
    else:
        direction = "CONFLICTED" if (bullish_weight > 0 and bearish_weight > 0) else "NEUTRAL"
        strength = 0.0
    
    if bullish_weight + bearish_weight > 0:
        agreement = max(bullish_weight, bearish_weight) / (bullish_weight + bearish_weight)
    else:
        agreement = 0.0
    
    confidence = min(0.95, agreement * min(1.0, total_weight / 2.0))
    
    return {
        "direction": direction, "strength": round(strength, 3),
        "confidence": round(confidence, 3), "contributing_events": contributing,
        "bullish_weight": round(bullish_weight, 3), "bearish_weight": round(bearish_weight, 3),
        "contributions": contributions,
    }


def observe_gold_direction(price_t0, price_now, buffer=None):
    if buffer is None:
        buffer = getattr(fc, "DIRECTION_BUFFER_USD", 2.0)
    if price_t0 is None or price_now is None:
        return "UNKNOWN"
    diff = price_now - price_t0
    if diff > buffer:
        return "UP"
    elif diff < -buffer:
        return "DOWN"
    else:
        return "MUTED"


def check_observation_match(fundamental_dir, observed_dir):
    if observed_dir in ("MUTED", "UNKNOWN") or fundamental_dir in ("NEUTRAL", "CONFLICTED"):
        return None
    if fundamental_dir == "BULLISH_GOLD" and observed_dir == "UP":
        return True
    elif fundamental_dir == "BEARISH_GOLD" and observed_dir == "DOWN":
        return True
    else:
        return False


def determine_grade(view, observation_match, events):
    if view["direction"] in ("NEUTRAL", "CONFLICTED"):
        return None
    if view["confidence"] < 0.3:
        return None

    # Build a lookup: event_title -> (hit_rate, samples) from contributions
    # (contributions are the events that actually influenced the view)
    hit_rate_by_title = {}
    for c in view.get("contributions", []):
        if c.get("hit_rate") is not None:
            hit_rate_by_title[c["event_title"]] = {
                "hit_rate": c["hit_rate"],
                "samples": c.get("hit_rate_samples", 0),
            }

    # Grade each contributing event on its OWN metrics (no cross-event mixing).
    # Best grade across all events wins.
    best_grade = None
    grade_order = {"A": 0, "B": 1, "C": 2, None: 3}

    for ev in events:
        tier = ev.get("tier") or 0
        z = ev.get("z_score")
        abs_z = abs(z) if z is not None else 0.0
        hr_data = hit_rate_by_title.get(ev["event_title"])
        hit_rate = hr_data["hit_rate"] if hr_data else None
        samples = hr_data["samples"] if hr_data else 0

        if tier <= 0:
            continue  # no Z-score significance — can only contribute to C

        ev_grade = None

        if (abs_z >= 1.5
                and hit_rate is not None and hit_rate >= 0.70
                and samples >= 5                          # min_sample_size for Grade A
                and observation_match is True):
            ev_grade = "A"
        elif (abs_z >= 1.0
                and hit_rate is not None and hit_rate >= 0.55
                and samples >= 3):                        # min_sample_size for Grade B
            ev_grade = "B"

        if grade_order.get(ev_grade, 3) < grade_order.get(best_grade, 3):
            best_grade = ev_grade

    # Grade C: view has some confidence even without a strong single event
    if best_grade is None and view["confidence"] >= 0.4:
        best_grade = "C"

    return best_grade


def select_action(mode, technical_state, view, observation_match, grade):
    in_position = technical_state.get("in_position", False)
    # FIX: handle None properly
    pos_dir = (technical_state.get("position_direction") or "").upper()
    
    reasoning = []
    
    if mode == "STEADY":
        reasoning.append("No events in next 1hr - normal operations")
        return ("HOLD_CONFIDENT" if in_position else "NO_FUNDAMENTAL_VIEW", reasoning)
    
    if mode == "EARLY_WARNING":
        ew = MODE_WINDOWS.get("EARLY_WARNING", {})
        reasoning.append(f"Event approaching in {ew.get('from', 60)}-{ew.get('to', 30)} min")
        if in_position:
            reasoning.append("Maintain position with awareness")
            return ("HOLD_AWARE", reasoning)
        else:
            reasoning.append("Delay new entries until event window passes")
            return ("DELAY_ENTRY", reasoning)
    
    if mode == "ACTIVE_CAUTION":
        reasoning.append("Event imminent (T-30 to T-15 min)")
        if in_position:
            if view["direction"] != "NEUTRAL" and view["confidence"] > 0.5:
                fund_align = (
                    (view["direction"] == "BULLISH_GOLD" and pos_dir == "LONG") or
                    (view["direction"] == "BEARISH_GOLD" and pos_dir == "SHORT")
                )
                if fund_align:
                    reasoning.append(f"Fundamental view aligns with {pos_dir} position")
                    return ("HOLD_AWARE", reasoning)
                else:
                    reasoning.append(f"Fundamental view opposes {pos_dir} position")
                    return ("PARTIAL_EXIT_RECOMMENDED", reasoning)
            return ("HOLD_AWARE", reasoning)
        else:
            return ("PAUSE_ENTRIES", reasoning)
    
    if mode == "IMMEDIATE_RISK":
        reasoning.append("Event within 15 minutes")
        if in_position:
            if view["direction"] != "NEUTRAL" and view["confidence"] > 0.6:
                fund_align = (
                    (view["direction"] == "BULLISH_GOLD" and pos_dir == "LONG") or
                    (view["direction"] == "BEARISH_GOLD" and pos_dir == "SHORT")
                )
                if not fund_align:
                    reasoning.append("Strong opposing fundamental view")
                    return ("EXIT_RECOMMENDED_URGENT", reasoning)
            reasoning.append("Reduce exposure ahead of event")
            return ("EXIT_RECOMMENDED", reasoning)
        else:
            return ("PAUSE_ENTRIES", reasoning)
    
    if mode == "POST_EVENT":
        reasoning.append("Post-event observation window")
        
        if view["direction"] == "CONFLICTED":
            reasoning.append("Multiple events with conflicting signals")
            return ("HOLD_AWARE" if in_position else "NO_FUNDAMENTAL_VIEW", reasoning)
        
        if view["direction"] == "NEUTRAL":
            reasoning.append("No clear fundamental view")
            return ("HOLD_CONFIDENT" if in_position else "NO_FUNDAMENTAL_VIEW", reasoning)
        
        if observation_match is True and grade in ("A", "B"):
            reasoning.append(f"Grade {grade}: fundamental + observation aligned")
            if in_position:
                fund_align = (
                    (view["direction"] == "BULLISH_GOLD" and pos_dir == "LONG") or
                    (view["direction"] == "BEARISH_GOLD" and pos_dir == "SHORT")
                )
                if fund_align:
                    reasoning.append("Position aligned with view")
                    return ("HOLD_CONFIDENT", reasoning)
                else:
                    reasoning.append("Position opposes confirmed view")
                    return ("EXIT_NOW", reasoning)
            else:
                reasoning.append("Strong setup for new entry")
                return ("CONFIRM_ENTRY", reasoning)
        
        if observation_match is False and grade in ("A", "B"):
            reasoning.append("Observation conflicts with fundamental view - likely SL hunt or news fake")
            return ("REJECT_ENTRY" if not in_position else "HOLD_AWARE", reasoning)
        
        if grade == "C":
            reasoning.append("Grade C signal - limited confidence")
            return ("HOLD_AWARE" if in_position else "NO_FUNDAMENTAL_VIEW", reasoning)
        
        return ("HOLD_AWARE" if in_position else "NO_FUNDAMENTAL_VIEW", reasoning)
    
    if mode == "COOLDOWN":
        reasoning.append("Post-event cooldown")
        return ("HOLD_AWARE" if in_position else "NO_FUNDAMENTAL_VIEW", reasoning)
    
    return ("NO_FUNDAMENTAL_VIEW", ["Unknown mode"])


def evaluate(technical_state, current_time=None, price_at_event=None, current_price=None, db_path=None):
    if current_time is None:
        current_time = datetime.now(timezone.utc).replace(tzinfo=None)
    elif hasattr(current_time, 'tzinfo') and current_time.tzinfo is not None:
        current_time = current_time.replace(tzinfo=None)
    
    if db_path is None:
        db_path = fc.DB_PATH
    
    conn = sqlite3.connect(db_path)
    
    try:
        events = get_events_in_window(conn, current_time, lookback_min=30, lookahead_min=60)
        mode, nearest_event_time, time_diff_min = detect_mode(current_time, events)
        view = compose_fundamental_view(events, conn)
        
        observed_dir = None
        observation_match = None
        if price_at_event is not None and current_price is not None:
            observed_dir = observe_gold_direction(price_at_event, current_price)
            observation_match = check_observation_match(view["direction"], observed_dir)
        
        grade = determine_grade(view, observation_match, events)
        action, reasoning = select_action(mode, technical_state, view, observation_match, grade)
        
        historical_context = []
        for ev in events[:3]:
            hr = get_hit_rate(conn, ev["event_type"], ev["currency"], ev["normalized_title"])
            historical_context.append({
                "event_title": ev["event_title"], "currency": ev["currency"],
                "event_type": ev["event_type"],
                "fundamental_direction": ev["fundamental_direction"],
                "tier": ev["tier"], "z_score": ev["z_score"],
                "historical_samples": hr["samples"], "historical_hit_rate": hr["hit_rate_15min"],
                "data_quality": hr["data_quality"],
            })
        
        result = {
            "engine_version": ENGINE_VERSION,
            "evaluation_time": current_time.isoformat(),
            "mode": mode,
            "nearest_event_time": nearest_event_time.isoformat() if nearest_event_time else None,
            "time_to_event_min": round(time_diff_min, 1) if time_diff_min is not None else None,
            "technical_context": {
                "in_position": technical_state.get("in_position", False),
                "position_direction": technical_state.get("position_direction"),
                "entry_price": technical_state.get("entry_price"),
                "regime": technical_state.get("regime"),
            },
            "active_events": [
                {
                    "event_title": e["event_title"], "currency": e["currency"],
                    "release_time": e["release_time"], "event_type": e["event_type"],
                    "tier": e["tier"], "z_score": e["z_score"],
                    "fundamental_direction": e["fundamental_direction"],
                    "direction_confidence": e["direction_confidence"],
                }
                for e in events
            ],
            "fundamental_view": view["direction"],
            "view_strength": view["strength"],
            "view_confidence": view["confidence"],
            "contributing_events": view["contributing_events"],
            "observed_direction": observed_dir,
            "view_observation_match": observation_match,
            "grade": grade,
            "action": action,
            "reasoning": reasoning,
            "historical_context": historical_context,
        }
        
        return result
    
    finally:
        conn.close()


def demo():
    print("=" * 70)
    print("FUNDAMENTAL ENGINE - DEMO EVALUATIONS")
    print("=" * 70)
    
    test_cases = [
        {
            "name": "Test 1: Idle, no position",
            "state": {"in_position": False, "position_direction": None, "regime": "trending"},
            "time": None,
        },
        {
            "name": "Test 2: LONG position, near recent event",
            "state": {"in_position": True, "position_direction": "LONG", "entry_price": 2400.0, "regime": "trending"},
            "time": datetime(2025, 2, 7, 11, 10),
        },
        {
            "name": "Test 3: SHORT position, before event",
            "state": {"in_position": True, "position_direction": "SHORT", "entry_price": 2450.0, "regime": "ranging"},
            "time": datetime(2025, 2, 7, 10, 45),
        },
        {
            "name": "Test 4: At historical event time with prices",
            "state": {"in_position": True, "position_direction": "LONG", "entry_price": 2380.0, "regime": "trending"},
            "time": datetime(2025, 2, 7, 11, 15),
            "price_at_event": 2389.0,
            "current_price": 2392.0,
        },
    ]
    
    for tc in test_cases:
        print(f"\n\n{'=' * 70}")
        print(f">>> {tc['name']}")
        print(f"{'=' * 70}")
        
        try:
            result = evaluate(
                tc["state"],
                current_time=tc.get("time"),
                price_at_event=tc.get("price_at_event"),
                current_price=tc.get("current_price"),
            )
            
            print(f"\n  Mode:                {result['mode']}")
            if result['nearest_event_time']:
                print(f"  Nearest event:       {result['nearest_event_time']}")
                print(f"  Time to event:       {result['time_to_event_min']} min")
            print(f"\n  Fundamental view:    {result['fundamental_view']}")
            print(f"  View strength:       {result['view_strength']}")
            print(f"  View confidence:     {result['view_confidence']}")
            print(f"  Contributing events: {result['contributing_events']}")
            
            if result['observed_direction']:
                print(f"\n  Observed direction:  {result['observed_direction']}")
                print(f"  Observation match:   {result['view_observation_match']}")
            
            print(f"\n  Grade:               {result['grade']}")
            print(f"  Action:              {result['action']}")
            print(f"\n  Reasoning:")
            for r in result['reasoning']:
                print(f"    - {r}")
            
            if result['active_events']:
                print(f"\n  Active events ({len(result['active_events'])}):")
                for e in result['active_events'][:3]:
                    print(f"    - [{e['currency']}] {e['event_title']} ({e['release_time']}) -> {e['fundamental_direction']}")
            
            if result['historical_context']:
                print(f"\n  Historical context:")
                for h in result['historical_context']:
                    hr = h['historical_hit_rate']
                    hr_str = f"{hr*100:.1f}%" if hr is not None else "N/A"
                    print(f"    - {h['event_title']}: {h['historical_samples']} samples, hit rate {hr_str}")
        
        except Exception as e:
            print(f"\n  ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n\n{'=' * 70}")
    print("DEMO COMPLETE")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    demo()
