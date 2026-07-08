"""
QGAI Fundamental Engine — Compact Trader Dashboard
====================================================
Single-screen layout. Most important info at top.

Layout:
  [TOP BAR]    Engine state | Mode | Action | Grade
  [ROW 1]      Active Event (live) | Next Event countdown
  [ROW 2]      Hit Rates | DB Stats | Live Scraper status
  [ROW 3]      Today's Events (compact list)
  [ROW 4]      Recent classified | Top performers

Run:
  python dashboard.py
  Open: http://localhost:5000
"""

import sys
import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

try:
    from flask import Flask, render_template_string, jsonify
except ImportError:
    print("ERROR: pip install flask")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR if (SCRIPT_DIR / "config").exists() else SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import fundamental_config as fc

try:
    from core.engine import evaluate as engine_evaluate
    ENGINE_AVAILABLE = True
except ImportError:
    ENGINE_AVAILABLE = False

app = Flask(__name__)


def get_db():
    return sqlite3.connect(fc.DB_PATH)


def query_one(sql, params=()):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchone()
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


def get_engine_state():
    """Call engine.evaluate to get current state."""
    if not ENGINE_AVAILABLE:
        return {"error": "engine not importable"}
    try:
        result = engine_evaluate({
            "in_position": False,
            "position_direction": None,
        })
        return result
    except Exception as e:
        return {"error": str(e)}


def get_today_events():
    """Today's events ordered by time, with capture status."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    return query_all("""
        SELECT release_time, currency, event_title, impact_stars,
               actual, forecast, previous, source_file
        FROM events_csv_import
        WHERE datetime(release_time) >= datetime(?)
          AND datetime(release_time) < datetime(?)
        ORDER BY release_time ASC
    """, (today_start.isoformat(), today_end.isoformat()))


def get_overview():
    """Quick stats."""
    overview = {}
    
    # Table counts
    for table, label in [
        ("events_csv_import", "events"),
        ("events_classified", "classified"),
        ("gold_reactions", "reactions"),
    ]:
        try:
            cnt = query_one(f"SELECT COUNT(*) FROM {table}")[0]
            overview[label] = cnt
        except:
            overview[label] = 0
    
    # Overall hit rate
    try:
        r = query_one("""
            SELECT SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN direction_matched = 0 THEN 1 ELSE 0 END)
            FROM gold_reactions
            WHERE data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
        """)
        m, mm = r[0] or 0, r[1] or 0
        overview["hit_rate"] = round(m / (m + mm) * 100, 1) if (m + mm) > 0 else 0
        overview["matched_total"] = m
        overview["mismatched_total"] = mm
    except:
        overview["hit_rate"] = 0
        overview["matched_total"] = 0
        overview["mismatched_total"] = 0
    
    return overview


def get_hit_rates_quick():
    """Compact hit rates by type and currency."""
    by_type = query_all("""
        SELECT event_type,
               ROUND(100.0 * SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END) /
                   NULLIF(SUM(CASE WHEN direction_matched IN (0,1) THEN 1 ELSE 0 END), 0), 1) as hr,
               COUNT(*) as n
        FROM gold_reactions
        WHERE data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
        GROUP BY event_type
        ORDER BY hr DESC
    """)
    
    by_currency = query_all("""
        SELECT currency,
               ROUND(100.0 * SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END) /
                   NULLIF(SUM(CASE WHEN direction_matched IN (0,1) THEN 1 ELSE 0 END), 0), 1) as hr,
               COUNT(*) as n
        FROM gold_reactions
        WHERE data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
        GROUP BY currency
        ORDER BY n DESC
    """)
    
    return {"type": by_type, "currency": by_currency}


def get_top_performers():
    return query_all("""
        SELECT event_title, currency,
               COUNT(*) as n,
               ROUND(100.0 * SUM(CASE WHEN direction_matched = 1 THEN 1 ELSE 0 END) /
                   NULLIF(SUM(CASE WHEN direction_matched IN (0,1) THEN 1 ELSE 0 END), 0), 1) as hr
        FROM gold_reactions
        WHERE data_quality != 'no_data' AND fundamental_direction != 'NEUTRAL'
        GROUP BY event_title, currency
        HAVING COUNT(*) >= 8
        ORDER BY hr DESC
        LIMIT 8
    """)


def get_recent_classified():
    return query_all("""
        SELECT release_time, currency, event_title, event_type, tier,
               z_score, fundamental_direction
        FROM events_classified
        WHERE datetime(release_time) <= datetime('now')
        ORDER BY release_time DESC
        LIMIT 8
    """)


def get_scraper_status():
    """Check if scraper has been active."""
    try:
        # Latest capture from live scraper
        last = query_one("""
            SELECT MAX(import_date), COUNT(*)
            FROM events_csv_import
            WHERE source_file LIKE '%investing_smart%'
        """)
        return {"last_capture": last[0], "live_count": last[1] or 0}
    except:
        return {"last_capture": "Never", "live_count": 0}


# ============================================================
# COMPACT HTML TEMPLATE
# ============================================================
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>QGAI Live Dashboard</title>
    <meta http-equiv="refresh" content="15">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Consolas', 'Courier New', monospace;
            background: #0a0e1a;
            color: #e0e6ed;
            font-size: 12px;
            line-height: 1.4;
        }
        
        /* TOP STATUS BAR */
        .topbar {
            background: linear-gradient(90deg, #0f1419 0%, #1a2332 100%);
            padding: 8px 15px;
            display: grid;
            grid-template-columns: 200px 1fr 1fr 1fr 200px;
            gap: 10px;
            border-bottom: 2px solid #4a90e2;
            align-items: center;
        }
        .topbar-item { display: flex; flex-direction: column; }
        .topbar-label { font-size: 9px; color: #7a8694; text-transform: uppercase; letter-spacing: 1px; }
        .topbar-value { font-size: 16px; font-weight: 700; }
        
        .mode-STEADY { color: #4caf50; }
        .mode-EARLY_WARNING { color: #ffc107; }
        .mode-ACTIVE_CAUTION { color: #ff9800; }
        .mode-IMMEDIATE_RISK { color: #f44336; }
        .mode-POST_EVENT { color: #2196f3; }
        .mode-COOLDOWN { color: #9e9e9e; }
        
        .grade-A { background: #4caf50; color: white; padding: 2px 8px; border-radius: 3px; font-weight: 700; }
        .grade-B { background: #2196f3; color: white; padding: 2px 8px; border-radius: 3px; font-weight: 700; }
        .grade-C { background: #ff9800; color: white; padding: 2px 8px; border-radius: 3px; font-weight: 700; }
        .grade-None { color: #7a8694; }
        
        /* MAIN LAYOUT */
        .main {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            padding: 10px;
        }
        
        .panel {
            background: #131825;
            border: 1px solid #232b3d;
            border-radius: 4px;
            padding: 10px;
        }
        .panel h3 {
            color: #6ab7ff;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 8px;
            padding-bottom: 4px;
            border-bottom: 1px solid #232b3d;
        }
        
        /* ENGINE STATE */
        .engine-state {
            grid-column: 1 / -1;
            background: linear-gradient(135deg, #131825 0%, #1a2030 100%);
            border-left: 3px solid #4a90e2;
        }
        .engine-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 15px; }
        .engine-cell { text-align: center; }
        .engine-cell .v { font-size: 18px; font-weight: 700; }
        .engine-cell .l { font-size: 9px; color: #7a8694; text-transform: uppercase; }
        
        /* COMPACT TABLE */
        table { width: 100%; font-size: 11px; }
        td, th { padding: 3px 5px; border-bottom: 1px solid #1d2333; }
        th { color: #6ab7ff; font-size: 9px; text-transform: uppercase; text-align: left; }
        tr:hover { background: rgba(74,144,226,0.05); }
        
        .bullish { color: #66bb6a; }
        .bearish { color: #ef5350; }
        .neutral { color: #7a8694; }
        .conflicted { color: #ffa726; }
        
        .pill {
            display: inline-block;
            padding: 1px 5px;
            border-radius: 2px;
            font-size: 9px;
            font-weight: 700;
        }
        .pill-USD { background: #2e7d32; }
        .pill-EUR { background: #1565c0; }
        .pill-GBP { background: #c62828; }
        .pill-JPY { background: #6a1b9a; }
        .pill-CAD { background: #ef6c00; }
        .pill-AUD { background: #00838f; }
        .pill-NZD { background: #455a64; }
        .pill-CNY { background: #d32f2f; }
        .pill-CHF { background: #4527a0; }
        
        .stars { color: #ffc107; font-size: 10px; }
        
        .truncate { 
            overflow: hidden; 
            text-overflow: ellipsis; 
            white-space: nowrap; 
            max-width: 200px;
            display: inline-block;
            vertical-align: middle;
        }
        
        .captured { color: #66bb6a; }
        .pending { color: #ffa726; }
        .past { color: #7a8694; }
        
        .countdown {
            font-size: 24px;
            font-weight: 700;
            color: #6ab7ff;
            text-align: center;
        }
        
        .alert {
            background: linear-gradient(90deg, #b71c1c, #c62828);
            color: white;
            padding: 8px 15px;
            text-align: center;
            font-weight: 700;
            font-size: 13px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.8; }
        }
        
        .footer {
            text-align: center;
            color: #5a6473;
            font-size: 10px;
            padding: 8px;
            border-top: 1px solid #232b3d;
        }
        
        .hr-bar {
            height: 4px;
            background: #232b3d;
            border-radius: 2px;
            margin-top: 2px;
            position: relative;
        }
        .hr-fill {
            position: absolute;
            top: 0;
            left: 0;
            height: 100%;
            border-radius: 2px;
        }
        .hr-fill.good { background: #66bb6a; }
        .hr-fill.medium { background: #ffa726; }
        .hr-fill.poor { background: #ef5350; }
        
        .reasoning-list {
            color: #b0bec5;
            font-size: 11px;
            padding: 4px 0;
        }
        .reasoning-list li { margin: 2px 0; padding-left: 8px; }
    </style>
</head>
<body>
    
    <!-- TOP STATUS BAR -->
    <div class="topbar">
        <div class="topbar-item">
            <span class="topbar-label">Mode</span>
            <span class="topbar-value mode-{{ engine.mode if engine.mode else 'STEADY' }}">
                {{ engine.mode if engine.mode else 'NO ENGINE' }}
            </span>
        </div>
        <div class="topbar-item">
            <span class="topbar-label">View</span>
            <span class="topbar-value {{ 'bullish' if engine.fundamental_view == 'BULLISH_GOLD' else 'bearish' if engine.fundamental_view == 'BEARISH_GOLD' else 'conflicted' if engine.fundamental_view == 'CONFLICTED' else 'neutral' }}">
                {{ engine.fundamental_view if engine.fundamental_view else '-' }}
            </span>
        </div>
        <div class="topbar-item">
            <span class="topbar-label">Action</span>
            <span class="topbar-value">{{ engine.action if engine.action else '-' }}</span>
        </div>
        <div class="topbar-item">
            <span class="topbar-label">Grade</span>
            <span class="topbar-value">
                {% if engine.grade %}<span class="grade-{{ engine.grade }}">{{ engine.grade }}</span>{% else %}-{% endif %}
            </span>
        </div>
        <div class="topbar-item">
            <span class="topbar-label">UTC Now</span>
            <span class="topbar-value">{{ utc_now }}</span>
        </div>
    </div>
    
    {% if engine.mode in ['IMMEDIATE_RISK', 'ACTIVE_CAUTION'] %}
    <div class="alert">
        ⚠ HIGH-IMPACT EVENT IN {{ engine.time_to_event_min|abs|round|int }} MIN — REDUCE EXPOSURE
    </div>
    {% endif %}
    
    {% if engine.grade == 'A' %}
    <div class="alert" style="background:linear-gradient(90deg,#1b5e20,#2e7d32);">
        ⭐ GRADE A SIGNAL ACTIVE — {{ engine.fundamental_view }} | {{ engine.action }}
    </div>
    {% endif %}
    
    <!-- ENGINE STATE ROW -->
    <div style="padding: 10px;">
        <div class="panel engine-state">
            <h3>🤖 Engine Live State</h3>
            <div class="engine-row">
                <div class="engine-cell">
                    <div class="v {{ 'bullish' if engine.fundamental_view == 'BULLISH_GOLD' else 'bearish' if engine.fundamental_view == 'BEARISH_GOLD' else 'neutral' }}">
                        {{ engine.view_strength|round(2) if engine.view_strength else '0.0' }}
                    </div>
                    <div class="l">Strength</div>
                </div>
                <div class="engine-cell">
                    <div class="v">{{ engine.view_confidence|round(2) if engine.view_confidence else '0.0' }}</div>
                    <div class="l">Confidence</div>
                </div>
                <div class="engine-cell">
                    <div class="v">{{ engine.contributing_events if engine.contributing_events else 0 }}</div>
                    <div class="l">Contrib Events</div>
                </div>
                <div class="engine-cell">
                    <div class="v">{{ engine.active_events|length if engine.active_events else 0 }}</div>
                    <div class="l">Active Events</div>
                </div>
                <div class="engine-cell">
                    <div class="v">{{ engine.time_to_event_min|round|int if engine.time_to_event_min is not none else '-' }}</div>
                    <div class="l">Min to Event</div>
                </div>
                <div class="engine-cell">
                    <div class="v">{{ engine.observed_direction if engine.observed_direction else '-' }}</div>
                    <div class="l">Observed</div>
                </div>
            </div>
            {% if engine.reasoning %}
            <ul class="reasoning-list">
            {% for r in engine.reasoning %}
                <li>→ {{ r }}</li>
            {% endfor %}
            </ul>
            {% endif %}
        </div>
    </div>
    
    <!-- MAIN GRID -->
    <div class="main">
        
        <!-- TODAY'S EVENTS (LEFT - LARGER) -->
        <div class="panel" style="grid-row: span 2;">
            <h3>📅 Today's Events ({{ today|length }})</h3>
            <table>
                <thead>
                    <tr><th>UTC</th><th>Cur</th><th>Event</th><th>★</th><th>Act</th><th>Fcst</th><th>Prev</th></tr>
                </thead>
                <tbody>
                {% for e in today %}
                <tr>
                    <td style="font-weight:600;">{{ e.release_time[11:16] }}</td>
                    <td><span class="pill pill-{{ e.currency }}">{{ e.currency }}</span></td>
                    <td><span class="truncate" title="{{ e.event_title }}">{{ e.event_title }}</span></td>
                    <td><span class="stars">{{ '★' * (e.impact_stars or 0) }}</span></td>
                    <td class="{{ 'captured' if e.actual else 'pending' }}"><strong>{{ e.actual or '⏳' }}</strong></td>
                    <td class="neutral">{{ e.forecast or '-' }}</td>
                    <td class="neutral">{{ e.previous or '-' }}</td>
                </tr>
                {% endfor %}
                {% if not today %}
                <tr><td colspan="7" style="text-align:center;color:#7a8694;padding:10px;">No events today</td></tr>
                {% endif %}
                </tbody>
            </table>
        </div>
        
        <!-- RIGHT COLUMN -->
        <div style="display: grid; gap: 10px;">
            
            <!-- HIT RATES + OVERVIEW -->
            <div class="panel">
                <h3>📊 Hit Rates by Type</h3>
                <table>
                    <thead><tr><th>Type</th><th>Hit %</th><th>N</th><th></th></tr></thead>
                    <tbody>
                    {% for r in hit_rates.type %}
                    <tr>
                        <td>{{ r.event_type }}</td>
                        <td><strong>{{ r.hr or '-' }}%</strong></td>
                        <td class="neutral">{{ r.n }}</td>
                        <td style="width:80px;">
                            <div class="hr-bar">
                                <div class="hr-fill {{ 'good' if (r.hr or 0) > 55 else 'medium' if (r.hr or 0) > 50 else 'poor' }}" 
                                     style="width: {{ r.hr or 0 }}%;"></div>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
            
            <!-- HIT RATES BY CURRENCY -->
            <div class="panel">
                <h3>💱 Hit Rates by Currency</h3>
                <table>
                    <thead><tr><th>Cur</th><th>Hit %</th><th>N</th></tr></thead>
                    <tbody>
                    {% for r in hit_rates.currency %}
                    <tr>
                        <td><span class="pill pill-{{ r.currency }}">{{ r.currency }}</span></td>
                        <td><strong>{{ r.hr or '-' }}%</strong></td>
                        <td class="neutral">{{ r.n }}</td>
                    </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- BOTTOM ROW -->
        
        <!-- TOP PERFORMERS -->
        <div class="panel">
            <h3>🏆 Top Performers (≥8 samples)</h3>
            <table>
                <thead><tr><th>Cur</th><th>Event</th><th>N</th><th>Hit %</th></tr></thead>
                <tbody>
                {% for p in top_performers %}
                <tr>
                    <td><span class="pill pill-{{ p.currency }}">{{ p.currency }}</span></td>
                    <td><span class="truncate" title="{{ p.event_title }}">{{ p.event_title }}</span></td>
                    <td class="neutral">{{ p.n }}</td>
                    <td><strong>{{ p.hr }}%</strong></td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        
        <!-- RECENT CLASSIFIED -->
        <div class="panel">
            <h3>🔬 Recent Classified</h3>
            <table>
                <thead><tr><th>Time</th><th>Cur</th><th>Event</th><th>T</th><th>Z</th><th>Dir</th></tr></thead>
                <tbody>
                {% for c in recent %}
                <tr>
                    <td style="font-size:10px;">{{ c.release_time[5:16] }}</td>
                    <td><span class="pill pill-{{ c.currency }}">{{ c.currency }}</span></td>
                    <td><span class="truncate" title="{{ c.event_title }}">{{ c.event_title }}</span></td>
                    <td>{{ c.tier or '-' }}</td>
                    <td>{{ "%.1f"|format(c.z_score) if c.z_score else '-' }}</td>
                    <td class="{{ 'bullish' if c.fundamental_direction == 'BULLISH_GOLD' else 'bearish' if c.fundamental_direction == 'BEARISH_GOLD' else 'neutral' }}">
                        {{ c.fundamental_direction[:4] if c.fundamental_direction else '-' }}
                    </td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <!-- FOOTER STATS -->
    <div class="footer">
        Events: {{ overview.events|default(0) }} | 
        Classified: {{ overview.classified|default(0) }} | 
        Reactions: {{ overview.reactions|default(0) }} | 
        Overall Hit: {{ overview.hit_rate }}% ({{ overview.matched_total }}/{{ overview.matched_total + overview.mismatched_total }}) | 
        Live captures: {{ scraper.live_count }} | 
        Last live: {{ scraper.last_capture[:19] if scraper.last_capture and scraper.last_capture != 'Never' else 'Never' }} | 
        Refresh: 15s
    </div>
</body>
</html>
"""


@app.route('/')
def index():
    engine_state = get_engine_state()
    return render_template_string(
        HTML,
        utc_now=datetime.utcnow().strftime("%H:%M:%S"),
        engine=engine_state,
        today=get_today_events(),
        hit_rates=get_hit_rates_quick(),
        overview=get_overview(),
        scraper=get_scraper_status(),
        top_performers=get_top_performers(),
        recent=get_recent_classified(),
    )


@app.route('/api/engine')
def api_engine():
    return jsonify(get_engine_state())


@app.route('/api/today')
def api_today():
    return jsonify(get_today_events())


if __name__ == "__main__":
    print("=" * 70)
    print("QGAI FUNDAMENTAL ENGINE — COMPACT TRADER DASHBOARD")
    print("=" * 70)
    print(f"\nDB:    {fc.DB_PATH}")
    print(f"Open:  http://localhost:5000")
    print(f"\nLayout: Single-screen, auto-refresh 15s")
    print(f"Press Ctrl+C to stop\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
