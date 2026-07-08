"""
QGAI Fundamental Engine — Complete Dashboard
==============================================
Comprehensive web dashboard showing all system data.

Features:
  - System overview & status
  - Database counts & breakdown
  - Hit rates by event type, currency, tier
  - Upcoming events (next 24 hours)
  - Recent captures from live scraper
  - Engine signal log
  - Top performing events
  - Configuration display
  - Engine test console (live evaluate)

Usage:
  python dashboard.py
  Then open: http://localhost:5000

Module: fundamental_engine.dashboard
Version: 1.0.0
"""

import sys
import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict

try:
    from flask import Flask, render_template_string, jsonify, request
except ImportError:
    print("ERROR: pip install flask")
    sys.exit(1)

# ============================================================
# PATH SETUP
# ============================================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR if (SCRIPT_DIR / "config").exists() else SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc

try:
    from core.engine import evaluate as engine_evaluate
    ENGINE_AVAILABLE = True
except ImportError:
    ENGINE_AVAILABLE = False

# ============================================================
# FLASK APP
# ============================================================
app = Flask(__name__)

# ============================================================
# DATA QUERIES
# ============================================================
def get_db():
    return sqlite3.connect(fc.DB_PATH)

def query_one(sql, params=()):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        result = cursor.fetchone()
        return result
    finally:
        conn.close()

def query_all(sql, params=()):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        cols = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def get_system_status():
    """Overall system metrics."""
    status = {}
    
    # Table counts
    tables = [
        ("events_raw", "FF JSON forecasts"),
        ("events_investing_raw", "Investing.com historical"),
        ("events_forexfactory_raw", "ForexFactory"),
        ("events_csv_import", "MT5 + live captures"),
        ("events_classified", "Classified events"),
        ("gold_reactions", "Gold reactions"),
        ("signal_log", "Engine signals"),
    ]
    
    table_stats = []
    for table, label in tables:
        try:
            count = query_one(f"SELECT COUNT(*) FROM {table}")[0]
            table_stats.append({"table": table, "label": label, "count": count})
        except:
            table_stats.append({"table": table, "label": label, "count": "N/A"})
    
    status["tables"] = table_stats
    
    # Date ranges
    try:
        ranges = query_one("""
            SELECT MIN(release_time), MAX(release_time)
            FROM events_csv_import
        """)
        status["data_range"] = {"from": ranges[0], "to": ranges[1]}
    except:
        status["data_range"] = {"from": "N/A", "to": "N/A"}
    
    # Overall hit rate
    try:
        result = query_one("""
            SELECT
                SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END),
                SUM(CASE WHEN direction_matched = 0 THEN 1 ELSE 0 END),
                SUM(CASE WHEN observed_direction = 'MUTED' THEN 1 ELSE 0 END)
            FROM gold_reactions
            WHERE data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
        """)
        matched, mismatched, muted = result
        matched = matched or 0
        mismatched = mismatched or 0
        muted = muted or 0
        det = matched + mismatched
        status["overall"] = {
            "matched": matched,
            "mismatched": mismatched,
            "muted": muted,
            "hit_rate": (matched / det * 100) if det > 0 else 0,
        }
    except:
        status["overall"] = {"matched": 0, "mismatched": 0, "muted": 0, "hit_rate": 0}
    
    return status


def get_hit_rates_by_type():
    return query_all("""
        SELECT 
            event_type,
            SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END) as matched,
            SUM(CASE WHEN direction_matched = 0 THEN 1 ELSE 0 END) as mismatched,
            SUM(CASE WHEN observed_direction = 'MUTED' THEN 1 ELSE 0 END) as muted,
            COUNT(*) as total,
            ROUND(100.0 * SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END) /
                NULLIF(SUM(CASE WHEN direction_matched IN (0,1) THEN 1 ELSE 0 END), 0), 1) as hit_rate
        FROM gold_reactions
        WHERE data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
        GROUP BY event_type
        ORDER BY total DESC
    """)


def get_hit_rates_by_currency():
    return query_all("""
        SELECT 
            currency,
            SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END) as matched,
            SUM(CASE WHEN direction_matched = 0 THEN 1 ELSE 0 END) as mismatched,
            COUNT(*) as total,
            ROUND(100.0 * SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END) /
                NULLIF(SUM(CASE WHEN direction_matched IN (0,1) THEN 1 ELSE 0 END), 0), 1) as hit_rate
        FROM gold_reactions
        WHERE data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
        GROUP BY currency
        ORDER BY total DESC
    """)


def get_hit_rates_by_tier():
    return query_all("""
        SELECT 
            tier,
            SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END) as matched,
            SUM(CASE WHEN direction_matched = 0 THEN 1 ELSE 0 END) as mismatched,
            COUNT(*) as total,
            ROUND(100.0 * SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END) /
                NULLIF(SUM(CASE WHEN direction_matched IN (0,1) THEN 1 ELSE 0 END), 0), 1) as hit_rate
        FROM gold_reactions
        WHERE data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
        GROUP BY tier
        ORDER BY tier ASC
    """)


def get_upcoming_events(hours_ahead=48):
    now = datetime.now()
    cutoff = now + timedelta(hours=hours_ahead)
    return query_all("""
        SELECT release_time, currency, event_title, impact_stars, 
               actual, forecast, previous, source_file
        FROM events_csv_import
        WHERE datetime(release_time) >= datetime(?)
          AND datetime(release_time) <= datetime(?)
        ORDER BY release_time ASC
        LIMIT 50
    """, (now.isoformat(), cutoff.isoformat()))


def get_recent_classified(limit=20):
    return query_all("""
        SELECT release_time, currency, event_title, event_type, tier,
               z_score, fundamental_direction, direction_confidence,
               surprise_normalized
        FROM events_classified
        WHERE datetime(release_time) <= datetime('now')
        ORDER BY release_time DESC
        LIMIT ?
    """, (limit,))


def get_top_performers(limit=20):
    return query_all("""
        SELECT 
            event_title,
            currency,
            event_type,
            COUNT(*) as samples,
            SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END) as matched,
            SUM(CASE WHEN direction_matched = 0 THEN 1 ELSE 0 END) as mismatched,
            ROUND(100.0 * SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END) /
                NULLIF(SUM(CASE WHEN direction_matched IN (0,1) THEN 1 ELSE 0 END), 0), 1) as hit_rate
        FROM gold_reactions
        WHERE data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
        GROUP BY event_title, currency
        HAVING COUNT(*) >= 5 AND SUM(CASE WHEN direction_matched IN (0,1) THEN 1 ELSE 0 END) >= 3
        ORDER BY hit_rate DESC
        LIMIT ?
    """, (limit,))


def get_strongest_reactions(limit=15):
    return query_all("""
        SELECT 
            release_time, event_title, currency, event_type, tier,
            fundamental_direction, observed_direction, direction_matched,
            move_15min_usd, mae_15min, mfe_15min
        FROM gold_reactions
        WHERE tier > 0 
          AND data_quality != 'no_data'
          AND ABS(move_15min_usd) > 5
        ORDER BY ABS(move_15min_usd) DESC
        LIMIT ?
    """, (limit,))


def get_recent_captures(limit=20):
    """From events_csv_import where source is live."""
    return query_all("""
        SELECT release_time, currency, event_title, impact_stars,
               actual, forecast, previous, source_file, import_date
        FROM events_csv_import
        WHERE source_file LIKE '%investing_smart%'
        ORDER BY import_date DESC
        LIMIT ?
    """, (limit,))


def get_signal_log(limit=20):
    """Recent engine signals."""
    try:
        return query_all("""
            SELECT * FROM signal_log
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
    except:
        return []


def get_config():
    """Get configuration values."""
    config = {}
    
    config_attrs = [
        "DB_PATH", "M15_PRICE_FILE", "LOG_FILE",
        "MODE_WINDOWS", "DIRECTION_BUFFER_USD",
        "DIRECTION_OBSERVATION_WINDOW_MIN",
    ]
    
    for attr in config_attrs:
        try:
            val = getattr(fc, attr, "N/A")
            if isinstance(val, dict):
                val = json.dumps(val, indent=2, default=str)
            config[attr] = str(val)
        except:
            config[attr] = "N/A"
    
    return config


# ============================================================
# HTML TEMPLATE
# ============================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>QGAI Fundamental Engine Dashboard</title>
    <meta http-equiv="refresh" content="30">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0f1419;
            color: #e6e6e6;
            line-height: 1.5;
        }
        .header {
            background: linear-gradient(135deg, #1a2332 0%, #2d3e54 100%);
            padding: 20px 30px;
            border-bottom: 2px solid #4a90e2;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        h1 { font-size: 24px; }
        .timestamp { color: #888; font-size: 13px; }
        .container { padding: 20px 30px; }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }
        
        .card {
            background: #1a2332;
            border: 1px solid #2d3e54;
            border-radius: 8px;
            padding: 20px;
        }
        .card h2 {
            font-size: 14px;
            text-transform: uppercase;
            color: #6ab7ff;
            margin-bottom: 12px;
            border-bottom: 1px solid #2d3e54;
            padding-bottom: 8px;
            letter-spacing: 0.5px;
        }
        .metric { display: flex; justify-content: space-between; padding: 6px 0; }
        .metric .label { color: #888; }
        .metric .value { color: #fff; font-weight: 600; font-family: 'Consolas', monospace; }
        
        .big-number { font-size: 28px; font-weight: 700; color: #6ab7ff; }
        .big-number .unit { font-size: 14px; color: #888; margin-left: 5px; }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            margin-top: 10px;
        }
        th, td {
            text-align: left;
            padding: 8px 10px;
            border-bottom: 1px solid #2d3e54;
        }
        th {
            background: #243246;
            color: #6ab7ff;
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        tr:hover { background: rgba(74,144,226,0.05); }
        td { font-family: 'Consolas', 'Courier New', monospace; }
        
        .bullish { color: #4caf50; }
        .bearish { color: #f44336; }
        .neutral { color: #888; }
        .conflicted { color: #ff9800; }
        .grade-a { background: #4caf50; color: white; padding: 2px 8px; border-radius: 4px; font-weight: 700; }
        .grade-b { background: #2196f3; color: white; padding: 2px 8px; border-radius: 4px; }
        .grade-c { background: #ff9800; color: white; padding: 2px 8px; border-radius: 4px; }
        
        .pill {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 600;
        }
        .pill-usd { background: #2e7d32; }
        .pill-eur { background: #1565c0; }
        .pill-gbp { background: #c62828; }
        .pill-jpy { background: #6a1b9a; }
        .pill-cad { background: #ef6c00; }
        .pill-aud { background: #00838f; }
        .pill-nzd { background: #455a64; }
        .pill-cny { background: #d32f2f; }
        .pill-chf { background: #4527a0; }
        
        .stars {
            color: #ffc107;
            letter-spacing: 1px;
        }
        
        .progress-bar {
            background: #2d3e54;
            border-radius: 4px;
            height: 8px;
            overflow: hidden;
            margin-top: 4px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #4caf50, #6ab7ff);
            transition: width 0.3s ease;
        }
        
        .section-title {
            font-size: 18px;
            color: #6ab7ff;
            margin: 20px 0 15px;
            padding-bottom: 8px;
            border-bottom: 2px solid #4a90e2;
        }
        
        .tabs {
            display: flex;
            gap: 5px;
            border-bottom: 1px solid #2d3e54;
            margin-bottom: 15px;
        }
        .tab {
            padding: 8px 16px;
            background: transparent;
            border: none;
            color: #888;
            cursor: pointer;
            font-size: 14px;
        }
        .tab.active {
            color: #6ab7ff;
            border-bottom: 2px solid #6ab7ff;
        }
        
        .badge {
            display: inline-block;
            background: #2196f3;
            color: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 11px;
            margin-left: 5px;
        }
        
        .text-truncate { 
            overflow: hidden; 
            text-overflow: ellipsis; 
            white-space: nowrap; 
            max-width: 250px;
        }
        
        .config-block {
            background: #0a1018;
            padding: 12px;
            border-radius: 4px;
            font-family: 'Consolas', monospace;
            font-size: 12px;
            white-space: pre-wrap;
            overflow-x: auto;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏛️ QGAI Fundamental Engine — Dashboard</h1>
        <div>
            <span class="timestamp">Last refresh: {{ now }}</span>
            <span class="badge">Auto-refresh 30s</span>
        </div>
    </div>
    
    <div class="container">
        
        <!-- OVERVIEW -->
        <h2 class="section-title">📊 System Overview</h2>
        <div class="grid">
            <div class="card">
                <h2>Database Tables</h2>
                {% for t in status.tables %}
                <div class="metric">
                    <span class="label">{{ t.label }}</span>
                    <span class="value">{{ "{:,}".format(t.count) if t.count != "N/A" else "N/A" }}</span>
                </div>
                {% endfor %}
            </div>
            
            <div class="card">
                <h2>Hit Rate (Overall)</h2>
                <div class="big-number">{{ "%.1f"|format(status.overall.hit_rate) }}<span class="unit">%</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: {{ status.overall.hit_rate }}%"></div></div>
                <div class="metric"><span class="label">Matched</span><span class="value bullish">{{ status.overall.matched }}</span></div>
                <div class="metric"><span class="label">Mismatched</span><span class="value bearish">{{ status.overall.mismatched }}</span></div>
                <div class="metric"><span class="label">Muted (≤$2)</span><span class="value neutral">{{ status.overall.muted }}</span></div>
            </div>
            
            <div class="card">
                <h2>Data Coverage</h2>
                <div class="metric">
                    <span class="label">From</span>
                    <span class="value">{{ status.data_range.from[:10] if status.data_range.from else 'N/A' }}</span>
                </div>
                <div class="metric">
                    <span class="label">To</span>
                    <span class="value">{{ status.data_range.to[:10] if status.data_range.to else 'N/A' }}</span>
                </div>
                <div class="metric">
                    <span class="label">Total events</span>
                    <span class="value">{{ "{:,}".format(total_events) }}</span>
                </div>
                <div class="metric">
                    <span class="label">Classified</span>
                    <span class="value">{{ "{:,}".format(classified_count) }}</span>
                </div>
            </div>
        </div>
        
        <!-- HIT RATES BREAKDOWN -->
        <h2 class="section-title">🎯 Hit Rates Breakdown</h2>
        <div class="grid">
            
            <div class="card">
                <h2>By Event Type</h2>
                <table>
                    <thead>
                        <tr><th>Type</th><th>Match</th><th>Mis</th><th>Mute</th><th>Hit %</th></tr>
                    </thead>
                    <tbody>
                    {% for r in hit_rates_type %}
                    <tr>
                        <td>{{ r.event_type }}</td>
                        <td class="bullish">{{ r.matched }}</td>
                        <td class="bearish">{{ r.mismatched }}</td>
                        <td class="neutral">{{ r.muted }}</td>
                        <td><strong>{{ r.hit_rate or '-' }}%</strong></td>
                    </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
            
            <div class="card">
                <h2>By Currency</h2>
                <table>
                    <thead>
                        <tr><th>Curr</th><th>Total</th><th>Match</th><th>Hit %</th></tr>
                    </thead>
                    <tbody>
                    {% for r in hit_rates_currency %}
                    <tr>
                        <td><span class="pill pill-{{ r.currency|lower }}">{{ r.currency }}</span></td>
                        <td>{{ r.total }}</td>
                        <td class="bullish">{{ r.matched }}</td>
                        <td><strong>{{ r.hit_rate or '-' }}%</strong></td>
                    </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
            
            <div class="card">
                <h2>By Tier (Z-Score)</h2>
                <table>
                    <thead>
                        <tr><th>Tier</th><th>Match</th><th>Mis</th><th>Total</th><th>Hit %</th></tr>
                    </thead>
                    <tbody>
                    {% for r in hit_rates_tier %}
                    <tr>
                        <td>
                            {% if r.tier == 0 %}T0 (no Z)
                            {% elif r.tier == 1 %}T1 ≥2.5
                            {% elif r.tier == 2 %}T2 ≥1.8
                            {% elif r.tier == 3 %}T3 ≥1.0
                            {% else %}T{{ r.tier }}{% endif %}
                        </td>
                        <td class="bullish">{{ r.matched }}</td>
                        <td class="bearish">{{ r.mismatched }}</td>
                        <td>{{ r.total }}</td>
                        <td><strong>{{ r.hit_rate or '-' }}%</strong></td>
                    </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- UPCOMING EVENTS -->
        <h2 class="section-title">📅 Upcoming Events (Next 48h)</h2>
        <div class="card">
            <table>
                <thead>
                    <tr>
                        <th>Time UTC</th>
                        <th>Cur</th>
                        <th>Event</th>
                        <th>Impact</th>
                        <th>Forecast</th>
                        <th>Previous</th>
                    </tr>
                </thead>
                <tbody>
                {% for e in upcoming %}
                <tr>
                    <td>{{ e.release_time[:16] }}</td>
                    <td><span class="pill pill-{{ e.currency|lower }}">{{ e.currency }}</span></td>
                    <td class="text-truncate">{{ e.event_title }}</td>
                    <td><span class="stars">{{ '★' * (e.impact_stars or 0) }}</span></td>
                    <td>{{ e.forecast or '-' }}</td>
                    <td>{{ e.previous or '-' }}</td>
                </tr>
                {% endfor %}
                {% if not upcoming %}
                <tr><td colspan="6" style="text-align:center;color:#888;">No upcoming events</td></tr>
                {% endif %}
                </tbody>
            </table>
        </div>
        
        <!-- RECENT CAPTURES (LIVE SCRAPER) -->
        <h2 class="section-title">📡 Recent Live Captures (Smart Scraper)</h2>
        <div class="card">
            <table>
                <thead>
                    <tr>
                        <th>Release Time</th>
                        <th>Cur</th>
                        <th>Event</th>
                        <th>Actual</th>
                        <th>Forecast</th>
                        <th>Previous</th>
                        <th>Captured At</th>
                    </tr>
                </thead>
                <tbody>
                {% for c in recent_captures %}
                <tr>
                    <td>{{ c.release_time[:16] }}</td>
                    <td><span class="pill pill-{{ c.currency|lower }}">{{ c.currency }}</span></td>
                    <td class="text-truncate">{{ c.event_title }}</td>
                    <td class="bullish"><strong>{{ c.actual or '-' }}</strong></td>
                    <td>{{ c.forecast or '-' }}</td>
                    <td>{{ c.previous or '-' }}</td>
                    <td style="color:#888;font-size:11px;">{{ c.import_date[:19] if c.import_date else '-' }}</td>
                </tr>
                {% endfor %}
                {% if not recent_captures %}
                <tr><td colspan="7" style="text-align:center;color:#888;">No live captures yet</td></tr>
                {% endif %}
                </tbody>
            </table>
        </div>
        
        <!-- TOP PERFORMERS -->
        <h2 class="section-title">🏆 Top Performing Events (Hit Rate ≥5 samples)</h2>
        <div class="card">
            <table>
                <thead>
                    <tr>
                        <th>Event</th>
                        <th>Currency</th>
                        <th>Type</th>
                        <th>Samples</th>
                        <th>Matched</th>
                        <th>Hit %</th>
                    </tr>
                </thead>
                <tbody>
                {% for p in top_performers %}
                <tr>
                    <td class="text-truncate">{{ p.event_title }}</td>
                    <td><span class="pill pill-{{ p.currency|lower }}">{{ p.currency }}</span></td>
                    <td>{{ p.event_type }}</td>
                    <td>{{ p.samples }}</td>
                    <td class="bullish">{{ p.matched }}</td>
                    <td><strong>{{ p.hit_rate }}%</strong></td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        
        <!-- STRONGEST REACTIONS -->
        <h2 class="section-title">⚡ Strongest Gold Reactions (Tier 1-3)</h2>
        <div class="card">
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Cur</th>
                        <th>Event</th>
                        <th>Fund</th>
                        <th>Obs</th>
                        <th>Match</th>
                        <th>15min $</th>
                        <th>MAE</th>
                        <th>MFE</th>
                    </tr>
                </thead>
                <tbody>
                {% for r in strongest %}
                <tr>
                    <td>{{ r.release_time[:16] }}</td>
                    <td><span class="pill pill-{{ r.currency|lower }}">{{ r.currency }}</span></td>
                    <td class="text-truncate">{{ r.event_title }}</td>
                    <td class="{{ 'bullish' if r.fundamental_direction == 'BULLISH_GOLD' else 'bearish' if r.fundamental_direction == 'BEARISH_GOLD' else 'neutral' }}">
                        {{ r.fundamental_direction[:4] if r.fundamental_direction else '-' }}
                    </td>
                    <td>{{ r.observed_direction or '-' }}</td>
                    <td>
                        {% if r.direction_matched == 1 %}<span class="bullish">✓</span>
                        {% elif r.direction_matched == 0 %}<span class="bearish">✗</span>
                        {% else %}-{% endif %}
                    </td>
                    <td class="{{ 'bullish' if r.move_15min_usd > 0 else 'bearish' }}">
                        ${{ "%.2f"|format(r.move_15min_usd) if r.move_15min_usd else '-' }}
                    </td>
                    <td>{{ "%.1f"|format(r.mae_15min) if r.mae_15min else '-' }}</td>
                    <td>{{ "%.1f"|format(r.mfe_15min) if r.mfe_15min else '-' }}</td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        
        <!-- RECENT CLASSIFIED -->
        <h2 class="section-title">🔬 Recent Classified Events</h2>
        <div class="card">
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Cur</th>
                        <th>Event</th>
                        <th>Type</th>
                        <th>Tier</th>
                        <th>Z</th>
                        <th>Surprise</th>
                        <th>Direction</th>
                        <th>Conf</th>
                    </tr>
                </thead>
                <tbody>
                {% for c in recent_classified %}
                <tr>
                    <td>{{ c.release_time[:16] }}</td>
                    <td><span class="pill pill-{{ c.currency|lower }}">{{ c.currency }}</span></td>
                    <td class="text-truncate">{{ c.event_title }}</td>
                    <td>{{ c.event_type }}</td>
                    <td>{{ c.tier or '-' }}</td>
                    <td>{{ "%.2f"|format(c.z_score) if c.z_score else '-' }}</td>
                    <td>{{ "%.2f"|format(c.surprise_normalized) if c.surprise_normalized else '-' }}</td>
                    <td class="{{ 'bullish' if c.fundamental_direction == 'BULLISH_GOLD' else 'bearish' if c.fundamental_direction == 'BEARISH_GOLD' else 'neutral' }}">
                        {{ c.fundamental_direction[:8] if c.fundamental_direction else '-' }}
                    </td>
                    <td>{{ "%.2f"|format(c.direction_confidence) if c.direction_confidence else '-' }}</td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        
        <!-- CONFIGURATION -->
        <h2 class="section-title">⚙️ Engine Configuration</h2>
        <div class="card">
            {% for key, val in config.items() %}
            <h2 style="margin-top:15px;">{{ key }}</h2>
            <div class="config-block">{{ val }}</div>
            {% endfor %}
        </div>
        
        <div style="text-align:center;padding:30px 0;color:#888;font-size:12px;">
            QGAI Fundamental Engine v1.0.0 | DB: {{ status.tables[0].count if status.tables else 0 }} events |
            <a href="/api/engine/test" style="color:#6ab7ff;">Engine Test</a> |
            <a href="/api/signal/recent" style="color:#6ab7ff;">Signal Log</a> |
            Auto-refresh every 30s
        </div>
    </div>
</body>
</html>
"""


# ============================================================
# ROUTES
# ============================================================
@app.route('/')
def index():
    status = get_system_status()
    
    # Total events from classified
    total_events = 0
    for t in status["tables"]:
        if t["table"] == "events_csv_import" and isinstance(t["count"], int):
            total_events = t["count"]
    
    classified_count = 0
    for t in status["tables"]:
        if t["table"] == "events_classified" and isinstance(t["count"], int):
            classified_count = t["count"]
    
    return render_template_string(
        HTML_TEMPLATE,
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        status=status,
        total_events=total_events,
        classified_count=classified_count,
        hit_rates_type=get_hit_rates_by_type(),
        hit_rates_currency=get_hit_rates_by_currency(),
        hit_rates_tier=get_hit_rates_by_tier(),
        upcoming=get_upcoming_events(48),
        recent_captures=get_recent_captures(20),
        recent_classified=get_recent_classified(15),
        top_performers=get_top_performers(15),
        strongest=get_strongest_reactions(15),
        config=get_config(),
    )


@app.route('/api/engine/test')
def engine_test():
    """Test engine.evaluate() with current state."""
    if not ENGINE_AVAILABLE:
        return jsonify({"error": "Engine not importable"}), 500
    
    try:
        result = engine_evaluate({
            "in_position": False,
            "position_direction": None,
            "regime": "trending",
        })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/signal/recent')
def signal_log():
    return jsonify(get_signal_log(50))


@app.route('/api/stats')
def stats_api():
    return jsonify({
        "system": get_system_status(),
        "hit_rates_type": get_hit_rates_by_type(),
        "hit_rates_currency": get_hit_rates_by_currency(),
        "hit_rates_tier": get_hit_rates_by_tier(),
    })


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("QGAI FUNDAMENTAL ENGINE DASHBOARD")
    print("=" * 70)
    print(f"\nDB:    {fc.DB_PATH}")
    print(f"Open:  http://localhost:5000")
    print(f"\nPress Ctrl+C to stop\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
