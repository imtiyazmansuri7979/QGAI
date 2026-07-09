@echo off
REM ============================================================
REM  Test_Decouple_Signal.bat  (2026-07-09)
REM  Offline test for the signal/trade DECOUPLE change.
REM  Uses a TEMP db+csv — the LIVE signals_all.csv / qgai.db are NOT touched.
REM ============================================================
cd /d C:\QGAI\engine
echo ---- Signal/Trade DECOUPLE test ----
py test_decouple_signal.py
echo.
echo Exit code: %ERRORLEVEL%
pause
