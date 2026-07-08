@echo off
title QGAI - Capture / Available Move Analysis
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - CAPTURE / AVAILABLE MOVE ANALYSIS
echo ------------------------------------------------------------
echo   Re-simulates the real BUY/SELL signals (signals_all.csv)
echo   under 4 exit rules and reports how much of the AVAILABLE
echo   market move each one CAPTURES:
echo      A baseline    - M15 line + M15 flip  (current live)
echo      B htf         - H1 line  + H1 flip   (anti-whipsaw)
echo      C flipconfirm - flip only on prob^>=45%% opposite signal
echo      D trendhold   - widen trail once +0.5R in profit
echo   Pure paper math. Read-only. Does NOT touch trading.
echo ============================================================
echo.
"%PY%" analyze_capture.py
echo.
echo ============================================================
echo   Done. Higher capturedPts + totalR = better trend capture.
echo   To CONFIRM the winner on the real engine backtest, run:
echo      python backtest_replay.py --stop-trail htf   (vs default)
echo ============================================================
pause
