@echo off
title QGAI - FIX-1 TEST : as-of data prep + 2-week WFO test (legacy vs rel)
REM ---------------------------------------------------------------------------
REM QUICK TEST (~10-20 min): builds the leak-free as-of ADX data, freezes TWO
REM workdirs, runs BOTH WFOs for only the FIRST 2 WEEKS to prove the pipeline
REM works (variant lines, no crashes, sane cluster stats). LIVE data untouched -
REM the as-of file goes ONLY into the frozen workdir copies.
REM If both test windows finish clean -> run Run_Fix1_AsOf_AB_FULL.bat
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"

echo ============================================================
echo   [1/3] Building leak-free as-of ADX (preview file, live untouched)
echo ============================================================
"%PY%" regen_adx_asof.py
if errorlevel 1 (echo AS-OF REGEN FAILED - STOP. Tell Claude. & pause & exit /b 1)
if not exist "C:\QGAI\data\merged\adx_merged_asof.csv" (echo asof file missing - STOP & pause & exit /b 1)

echo ============================================================
echo   [2/3] Freezing workdirs + inserting as-of file
echo ============================================================
if not exist "C:\QGAI_wfo_asof_leg\engine\logs" mkdir "C:\QGAI_wfo_asof_leg\engine\logs"
if not exist "C:\QGAI_wfo_asof_rel\engine\logs" mkdir "C:\QGAI_wfo_asof_rel\engine\logs"
robocopy "C:\QGAI\data" "C:\QGAI_wfo_asof_leg\data" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP >nul
robocopy "C:\QGAI\data" "C:\QGAI_wfo_asof_rel\data" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP >nul
robocopy "C:\QGAI\engine\logs" "C:\QGAI_wfo_asof_leg\engine\logs" /E /R:1 /W:1 /XF *.log /NFL /NDL /NJH /NJS /NC /NS /NP >nul
robocopy "C:\QGAI\engine\logs" "C:\QGAI_wfo_asof_rel\engine\logs" /E /R:1 /W:1 /XF *.log /NFL /NDL /NJH /NJS /NC /NS /NP >nul
copy /Y "C:\QGAI\data\merged\adx_merged_asof.csv" "C:\QGAI_wfo_asof_leg\data\merged\adx_merged.csv" >nul
copy /Y "C:\QGAI\data\merged\adx_merged_asof.csv" "C:\QGAI_wfo_asof_rel\data\merged\adx_merged.csv" >nul
echo   Workdirs ready: C:\QGAI_wfo_asof_leg + C:\QGAI_wfo_asof_rel (as-of data inside)

echo ============================================================
echo   [3/3] Launching BOTH 2-week TEST WFOs
echo ============================================================
start "FIX1 TEST legacy" cmd /c "C:\QGAI\backtest\Run_AsOf_WFO_legacy.bat" 2
start "FIX1 TEST rel"    cmd /c "C:\QGAI\backtest\Run_AsOf_WFO_rel.bat" 2

echo.
echo Two TEST windows opened (2 weeks each, ~10-20 min).
echo CHECK in each window: no crashes, weekly R lines appear, and results in
echo   results\wfo_asof_legacy_TEST\  and  results\wfo_asof_rel_TEST\
echo If both finish clean, run: Run_Fix1_AsOf_AB_FULL.bat
pause
