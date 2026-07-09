# -*- coding: utf-8 -*-
"""
Offline TEST — signal/trade DECOUPLE (2026-07-09).
Verifies bridge_data.log_signal now:
  (1) records the PURE engine signal (BUY/SELL/SKIP) in the `signal` column, and
  (2) records what MT5 did in a SEPARATE new `trade_action` column,
  (3) auto-migrates an OLD CSV / SQLite table (adds trade_action, blank for old rows).
Runs on a TEMP db+csv — the LIVE signals_all.csv / qgai.db are NOT touched.
"""
import os, sys, csv, sqlite3, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bridge_constants
from bridge_constants import CFG

tmp = tempfile.mkdtemp(prefix="qgai_decouple_")
tmp_csv = os.path.join(tmp, "signals_all.csv")
tmp_db  = os.path.join(tmp, "qgai.db")

# redirect live paths to TEMP (this process only — live bridge unaffected)
CFG.paths.signal_log = tmp_csv
CFG.paths.db_path     = tmp_db

# --- pre-migration signals table (NO trade_action column) ---
c = sqlite3.connect(tmp_db)
c.executescript("""
CREATE TABLE signals(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 bar_time TEXT NOT NULL, mode TEXT NOT NULL, signal TEXT,
 win_prob REAL, state_prob REAL, dir_prob REAL, big_win_prob REAL,
 hmm_state TEXT, price REAL, lot REAL, sl REAL, tp REAL,
 atr20_pct REAL, vol_spike INTEGER, in_range_phase INTEGER,
 slot_wr REAL, h4_bull_ob_dist REAL, h4_bear_ob_dist REAL,
 reason TEXT, outcome TEXT, pnl_net REAL,
 UNIQUE(bar_time,mode));
""")
c.commit(); c.close()

# --- OLD-format CSV (pre trade_action) : header + 1 old row ---
OLD_HDR = ["bar_time","mode","signal","win_prob","state_prob","dir_prob",
           "big_win_prob","hmm_state","price","lot","sl","tp","atr20_pct",
           "vol_spike","in_range_phase","slot_wr","h4_bull_ob_dist",
           "h4_bear_ob_dist","reason","outcome","equity","move","trading_equity"]
old_row = ["2026-07-09 10:00:00","LIVE","SKIP","0.5"] + ["0"]*(len(OLD_HDR)-4)
with open(tmp_csv, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(OLD_HDR); w.writerow(old_row)

import bridge_data

RESULT = {"win_prob":0.7859,"state_prob":0.61,"dir_prob":0.55,"big_win_prob":0.30,
          "hmm_state":"trending","atr20_pct":0.42,"vol_spike":0,"in_range_phase":0,
          "slot_wr":0.55,"h4_resist_dist":1.2,"h4_support_dist":1.1,
          "reason":"prob=78.59% | model=xgb | state=trending"}

# high-prob BUY that MT5 could NOT take (slot blocked) — signal must stay BUY
bridge_data.log_signal("2026-07-09 11:00:00","BUY",RESULT,2650.50,"LIVE",
                       trade_action="BLOCK_SLOT",equity=1000.0,trading_equity=1000.0)
bridge_data._last_sig_key = None  # reset dedupe guard for next bar
# genuine engine SKIP
bridge_data.log_signal("2026-07-09 11:15:00","SKIP",RESULT,2651.00,"LIVE",
                       trade_action="NO_TRADE",equity=1000.0,trading_equity=1000.0)
bridge_data._last_sig_key = None
# high-prob BUY, trade already open (HOLD) — the exact 78.59%-shows-SKIP bug
bridge_data.log_signal("2026-07-09 11:30:00","BUY",RESULT,2652.00,"LIVE",
                       trade_action="HOLD_IN_TRADE",equity=1000.0,trading_equity=1000.0)

# ---------------- ASSERTIONS ----------------
fails = []
def chk(name, cond):
    print(("  PASS  " if cond else "  FAIL  ") + name)
    if not cond: fails.append(name)

with open(tmp_csv, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
by_bt = {r["bar_time"]: r for r in rows}

chk("CSV header has trade_action column", "trade_action" in rows[0].keys())
chk("OLD row migrated: trade_action blank",
    by_bt["2026-07-09 10:00:00"]["trade_action"] == "")
chk("Blocked BUY: signal=BUY (NOT overwritten to SKIP)",
    by_bt["2026-07-09 11:00:00"]["signal"] == "BUY")
chk("Blocked BUY: trade_action=BLOCK_SLOT",
    by_bt["2026-07-09 11:00:00"]["trade_action"] == "BLOCK_SLOT")
chk("Engine SKIP: signal=SKIP, trade_action=NO_TRADE",
    by_bt["2026-07-09 11:15:00"]["signal"] == "SKIP" and
    by_bt["2026-07-09 11:15:00"]["trade_action"] == "NO_TRADE")
chk("HOLD bar: signal=BUY, trade_action=HOLD_IN_TRADE (78.59% bug fixed)",
    by_bt["2026-07-09 11:30:00"]["signal"] == "BUY" and
    by_bt["2026-07-09 11:30:00"]["trade_action"] == "HOLD_IN_TRADE")

# SQLite
cc = sqlite3.connect(tmp_db)
cols = [r[1] for r in cc.execute("PRAGMA table_info(signals)").fetchall()]
chk("SQLite: trade_action column added by migration", "trade_action" in cols)
row = cc.execute("SELECT signal,trade_action FROM signals WHERE bar_time='2026-07-09 11:00:00'").fetchone()
chk("SQLite: blocked BUY stored as (BUY, BLOCK_SLOT)", row == ("BUY","BLOCK_SLOT"))
cc.close()

# static scan of bridge_main.py — no SKIP-overwrite remains
main_src = open(os.path.join(HERE,"bridge_main.py"), encoding="utf-8-sig").read()
chk('bridge_main.py: zero  log_signal(bar_time, "SKIP"  overwrites',
    'log_signal(bar_time, "SKIP"' not in main_src)
chk("bridge_main.py: >=10 trade_action= tags present",
    main_src.count("trade_action=") >= 10)

print("\n" + ("="*46))
if fails:
    print(f"RESULT: FAIL ({len(fails)} check(s) failed)")
    for x in fails: print("   - " + x)
    sys.exit(1)
print("RESULT: ALL CHECKS PASSED  (temp dir: %s)" % tmp)
sys.exit(0)
