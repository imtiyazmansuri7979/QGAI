@echo off
title QGAI - HMM v3 A/B WFO : regen + freeze + launch BOTH variants (live SAFE)
REM ---------------------------------------------------------------------------
REM HMM "flat market reads Volatile" fix - A/B validation (2026-07-02, Divyesh).
REM   A (spec): ADX + abs(DI_diff) + band_width_pct   - literal spec
REM   B (rel) : ADX + di_eff + band_rel               - recommended (sandbox winner)
REM Steps: 1) regen adx_merged.csv with ALL new columns
REM        2) freeze TWO workdir copies (C:\QGAI_wfo_spec, C:\QGAI_wfo_rel)
REM        3) launch both WFO windows in PARALLEL (each ~1.5-2.5 hrs)
REM Live models / live data are NOT touched. Bridge keeps running old model.
REM ADOPT the winner ONLY if its total R is at least +483.1R (wfo_live_match_015).
REM If your PC is slow, close one window and run the two child bats one by one.
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"

echo ============================================================
echo   [1/3] Regenerating adx_merged.csv (band, di_eff, band_rel)
echo ============================================================
"%PY%" regen_adx_di.py
if errorlevel 1 (echo REGEN FAILED - STOP. Tell Claude. & pause & exit /b 1)

echo ============================================================
echo   [2/3] Freezing workdir copies (live untouched)
echo ============================================================
if not exist "C:\QGAI_wfo_spec\engine\logs" mkdir "C:\QGAI_wfo_spec\engine\logs"
if not exist "C:\QGAI_wfo_rel\engine\logs"  mkdir "C:\QGAI_wfo_rel\engine\logs"
robocopy "C:\QGAI\data" "C:\QGAI_wfo_spec\data" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP >nul
robocopy "C:\QGAI\data" "C:\QGAI_wfo_rel\data"  /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP >nul
robocopy "C:\QGAI\engine\logs" "C:\QGAI_wfo_spec\engine\logs" /E /R:1 /W:1 /XF *.log /NFL /NDL /NJH /NJS /NC /NS /NP >nul
robocopy "C:\QGAI\engine\logs" "C:\QGAI_wfo_rel\engine\logs"  /E /R:1 /W:1 /XF *.log /NFL /NDL /NJH /NJS /NC /NS /NP >nul
echo   Frozen: C:\QGAI_wfo_spec + C:\QGAI_wfo_rel

echo ============================================================
echo   [3/3] Launching BOTH WFO runs in parallel windows
echo ============================================================
start "WFO A - spec" "C:\QGAI\backtest\Run_HMM_WFO_A_spec.bat"
start "WFO B - rel"  "C:\QGAI\backtest\Run_HMM_WFO_B_rel.bat"

echo.
echo Two windows opened. Each takes about 1.5-2.5 hrs (resume-safe).
echo When BOTH finish, tell Claude: "AB WFO done" to analyze
echo   results\wfo_hmm_spec\_WFO_SUMMARY.txt (+ .csv)
echo   results\wfo_hmm_rel\_WFO_SUMMARY.txt (+ .csv)
echo vs baseline +483.1R. Then deploy the winner (Run_HMM_v3_Deploy.bat).
pause
