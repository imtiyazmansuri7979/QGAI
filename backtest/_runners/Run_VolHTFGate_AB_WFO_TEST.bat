@echo off
setlocal
chcp 65001 >nul
title QGAI - Volatile counter-HTF gate A/B - WFO ~3 months (TEST)

REM =====================================================================
REM  Signal-audit finding (2026-07-13, Imtiyaz + Fable-5 second opinion):
REM  on the honest 53-week WFO baseline (wfo_adxdeath_novol_baseline_20260710),
REM  Volatile-regime trades in the 42-48% win_prob band that go AGAINST the
REM  dominant HTF direction (H1/H4 DI, via ts_htf_agreement) are net-LOSING
REM  (n=38, total -1.9R, PF 0.88) while the SAME band aligned WITH HTF is
REM  strongly profitable (n=48, +18.9R, PF 3.78). Confirmed NOT a time/slot
REM  confound (checked slot_win_rate, hour, day-of-week, week spread).
REM
REM  This is NOT a time-based filter (Imtiyaz's own principle: build the
REM  strategy first, keep time-features soft/model-internal) - it's a
REM  directional-agreement + confidence gate, implemented in inference.py
REM  behind QGAI_VOL_HTF_GATE (default OFF, no-op unless set to 1).
REM
REM  A = baseline (gate OFF, current live behavior)
REM  B = candidate (gate ON, skips the losing combo)
REM
REM  DECISION RULE: B total R >= A total R (and DD not worse) -> run the
REM  full 53-week WFO (Run_VolHTFGate_AB_WFO_FULL.bat) before considering
REM  live adoption. B < A -> reject, delete the QGAI_VOL_HTF_GATE block in
REM  inference.py (or just leave it env-gated OFF forever - zero live risk
REM  either way since it defaults OFF).
REM
REM  SAFE BY DESIGN (2026-07-13, added after this exact bat's first run left
REM  data\models\final holding a WFO-fold model instead of the live one):
REM  every weekly retrain now goes to data\models\test_workspace (separate
REM  from data\models\final) via QGAI_MODELS_DIR. Live model is NEVER
REM  touched - the live bridge can even run at the same time. Resume-safe:
REM  weeks already cached under the OLD (final-touching) run are reused as-
REM  is (the cached R/trades numbers don't depend on which folder held the
REM  model) - only week 5 onward will use the new safe folder.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_MODELS_DIR=C:\QGAI\data\models\test_workspace"

cd /d "%ROOT%\engine"

echo ============================================================
echo   VOLATILE COUNTER-HTF GATE A/B - WFO TEST (~3 months / 12 weeks)
echo   %DATE% %TIME%
echo ============================================================

echo.
echo [A] WFO baseline (gate OFF)...
set "QGAI_VOL_HTF_GATE=0"
"%PY%" run_wfo.py --start 2026-04-06 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir volhtfgate_wfo_TEST_A_off
if errorlevel 1 goto fail

echo.
echo [B] WFO candidate (gate ON)...
set "QGAI_VOL_HTF_GATE=1"
"%PY%" run_wfo.py --start 2026-04-06 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir volhtfgate_wfo_TEST_B_on
if errorlevel 1 goto fail
set "QGAI_VOL_HTF_GATE="

echo.
echo ============================================================
echo   DONE. Compare cum R (_WFO_SUMMARY.csv in each results-dir):
echo     A (gate OFF): backtest\results\volhtfgate_wfo_TEST_A_off\
echo     B (gate ON) : backtest\results\volhtfgate_wfo_TEST_B_on\
echo   B total R ^>= A total R -^> run Run_VolHTFGate_AB_WFO_FULL.bat (53 weeks)
echo   B ^< A -^> reject; gate stays OFF by default, no live risk either way.
echo ============================================================
pause
exit /b 0

:fail
set "QGAI_VOL_HTF_GATE="
echo *** FAILED %DATE% %TIME% ***
pause
exit /b 1
