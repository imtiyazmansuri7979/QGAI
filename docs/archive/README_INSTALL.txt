============================================================
  QGAI — COMPLETE UPDATE PACKAGE (2026-06-12)
  13 files — બધા updates એક સાથે
============================================================

📦 FILES (બધી C:\QGAI\engine\ માં copy કરો, overwrite YES):

  NEW FILES (4):
    trend_signal.py           - TrendSignals indicator નું Python port (P=2, SMMA)
    bridge_ratchet.py         - Live ratchet line provider (MT5 bars માંથી)
    build_indicators.py       - Indicator snapshot builder (verify સાથે)
    build_feature_snapshot.py - Full 66-feature snapshot builder (incremental)

  UPDATED FILES (9):
    features.py          - 66 features: 10 TS + ADX switch (H4>=19) + rolling ADX slopes
    config.py            - Daily TP 8% + RATCHET settings (% માં)
    bridge_constants.py  - નવા constants
    bridge_session.py    - Daily Equity Target (virtual, broker-hidden)
    bridge_core.py       - Daily TP guards + RATCHET execute/monitor
    bridge_risk.py       - VirtualTrade ⚡Ratchet mode
    backtest_replay.py   - --ratchet on/off/auto CLI flag
    merge_data.py        - Hooks: extra TFs + indicator + feature snapshots
    mt5_data_updater.py  - M5/M30/H1/H4/D1 collection (24hr, save-only)

============================================================
  INSTALL STEPS (ક્રમ મહત્વનો!)
============================================================

  1. QGAI bridge બંધ કરો (ચાલતું હોય તો)

  2. Backup (recommended):
     C:\QGAI\engine\ ની copy બનાવો -> C:\QGAI\engine_backup_0612\

  3. આ ZIP ની બધી 13 files copy -> C:\QGAI\engine\  (overwrite)

  4. MT5 terminal ખુલ્લું રાખીને:
     QGAI_RETRAIN.bat ચલાવો
     - Step [1/3]: પાંચ નવા TF download થશે (પહેલી વાર થોડી વધારે મિનિટ)
     - Step [2/3]: merged files + indicators_merged.csv + VERIFY PASSED દેખાવું જોઈએ
     - Step [3/3]: training console માં આ confirm કરો:
         "Hybrid feature sets: Ranging=47 | Trending=46 | Volatile=38"

  5. Feature snapshot - પહેલી વાર (એક જ વાર, ~45-60 min):
     cd C:\QGAI\engine
     python build_feature_snapshot.py --verify 10
     (પછી દરેક retrain માં આપમેળે incremental ચાલશે - seconds)

  6. QGAI_START.bat -> bridge restart (નવા models load)
     Logs માં confirm: "DailyTarget:$X,XXX (+8.0%)"

============================================================
  BACKTEST (decision આનાથી થશે)
============================================================

  python backtest_replay.py --date_from 2026-01-01 --date_to 2026-06-12 --ratchet off
  python backtest_replay.py --date_from 2026-01-01 --date_to 2026-06-12 --ratchet on

  (તમારા regular arguments - equity/risk/fixed_lot - સાથે રાખવા)
  બંને results સરખાવો: total P&L, WR, max DD, avg R
  -> Ratchet જીતે તો config.py માં enable_ratchet_exit = True

============================================================
  SAFETY NOTES
============================================================

  - RATCHET mode default OFF છે - live behaviour આજ જેવું જ રહેશે
  - Daily Equity Target 8% ON છે (virtual - broker ને દેખાય નહીં)
  - Retrain ફરજિયાત છે - વગર retrain bridge ચલાવશો તો
    feature dimension mismatch error આવશે
  - કંઈ ખોટું લાગે તો backup folder પાછું મૂકી દો

============================================================
