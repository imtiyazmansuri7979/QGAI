@echo off
title QGAI - FIX-1 FULL : honest re-baseline A/B WFO (legacy vs rel, as-of data)
REM ---------------------------------------------------------------------------
REM FULL RUN (each ~1.5-2.5 hrs, parallel). Run Run_Fix1_AsOf_AB_TEST.bat FIRST.
REM Re-preps the as-of data + workdirs (idempotent), then runs BOTH full WFOs:
REM   legacy = ORIGINAL 8-feature HMM   -> results\wfo_asof_legacy\
REM   rel    = v3 winner HMM            -> results\wfo_asof_rel\
REM These two numbers are the HONEST comparison (leak-free). The +483.1R and
REM +481.7R old-world numbers are NOT comparable to these. Decision rule
REM (profit-first): adopt rel if wfo_asof_rel total R >= wfo_asof_legacy.
REM LIVE data/models untouched; bridge keeps running.
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"

echo ============================================================
echo   [1/3] Rebuilding leak-free as-of ADX (preview, live untouched)
echo ============================================================
"%PY%" regen_adx_asof.py
if errorlevel 1 (echo AS-OF REGEN FAILED - STOP. Tell Claude. & pause & exit /b 1)

echo ============================================================
echo   [2/3] Refreshing workdirs + inserting as-of file
echo ============================================================
if not exist "C:\QGAI_wfo_asof_leg\engine\logs" mkdir "C:\QGAI_wfo_asof_leg\engine\logs"
if not exist "C:\QGAI_wfo_asof_rel\engine\logs" mkdir "C:\QGAI_wfo_asof_rel\engine\logs"
robocopy "C:\QGAI\data" "C:\QGAI_wfo_asof_leg\data" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP >nul
robocopy "C:\QGAI\data" "C:\QGAI_wfo_asof_rel\data" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP >nul
robocopy "C:\QGAI\engine\logs" "C:\QGAI_wfo_asof_leg\engine\logs" /E /R:1 /W:1 /XF *.log /NFL /NDL /NJH /NJS /NC /NS /NP >nul
robocopy "C:\QGAI\engine\logs" "C:\QGAI_wfo_asof_rel\engine\logs" /E /R:1 /W:1 /XF *.log /NFL /NDL /NJH /NJS /NC /NS /NP >nul
copy /Y "C:\QGAI\data\merged\adx_merged_asof.csv" "C:\QGAI_wfo_asof_leg\data\merged\adx_merged.csv" >nul
copy /Y "C:\QGAI\data\merged\adx_merged_asof.csv" "C:\QGAI_wfo_asof_rel\data\merged\adx_merged.csv" >nul
echo   Workdirs ready (as-of data inside)

echo ============================================================
echo   [3/3] Launching BOTH FULL WFOs (53 weeks each, parallel)
echo ============================================================
start "FIX1 FULL legacy" cmd /c "C:\QGAI\backtest\Run_AsOf_WFO_legacy.bat"
start "FIX1 FULL rel"    cmd /c "C:\QGAI\backtest\Run_AsOf_WFO_rel.bat"

echo.
echo Two FULL windows opened (~1.5-2.5 hrs each, resume-safe).
echo When BOTH finish, tell Claude: "asof wfo done" to compare
echo   results\wfo_asof_legacy\_WFO_SUMMARY.txt  vs  results\wfo_asof_rel\_WFO_SUMMARY.txt
echo (honest baseline decision - old +483.1R numbers do NOT apply here)
pause
