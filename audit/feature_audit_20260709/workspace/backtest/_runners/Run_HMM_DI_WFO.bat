@echo off
title QGAI - HMM +DI/-DI fix : rebuild ADX + WFO validate (live models SAFE)
REM ---------------------------------------------------------------------------
REM Validates the HMM "Volatile" mislabel fix (uses +DI / -DI levels instead of
REM DI_diff). Steps:
REM   1. regen_adx_di.py  -> rebuild data\merged\adx_merged.csv WITH +DI/-DI
REM      (additive; old ADX/DI_diff preserved + backed up; prints DI_diff parity)
REM   2. freeze a WORKDIR copy (C:\QGAI_wfo) and run WFO there with the NEW code
REM      -> weekly retrain builds the +DI/-DI HMM; LIVE models are NOT touched.
REM   3. Compare new HMM OOS total R vs the OLD baseline wfo_live_match_015 (+483.0R).
REM
REM *** SAFETY — READ ***
REM The engine code now expects the 12 +DI/-DI features, but the LIVE model pkl is
REM still the OLD 8-feature one. DO NOT restart the live bridge until you have
REM retrained live (train.py) AND this WFO shows total R is NOT worse (profit-first).
REM Until then the running bridge keeps working on the old model in memory.
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "SRC=C:\QGAI"
set "WORK=C:\QGAI_wfo"

cd /d "C:\QGAI\engine"

echo ============================================================
echo   PREREQUISITE: run Run_Regen_ADX.bat FIRST (rebuilds adx_merged
echo   with +DI/-DI). This bat does NOT regen — it just freezes the
echo   already-regen'd data and runs the WFO. Safe to run in PARALLEL
echo   with Run_HMM_DI_Deploy.bat (different output folders).
echo ============================================================

echo ============================================================
echo   freeze WORKDIR + run WFO with NEW +DI/-DI HMM (live safe)
echo ============================================================
if not exist "%WORK%\engine\logs" mkdir "%WORK%\engine\logs"
robocopy "%SRC%\data" "%WORK%\data" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP >nul
robocopy "%SRC%\engine\logs" "%WORK%\engine\logs" /E /R:1 /W:1 /XF *.log /NFL /NDL /NJH /NJS /NC /NS /NP >nul
set "QGAI_ROOT=%WORK%"
"%PY%" run_wfo.py --start 2025-06-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --results-dir wfo_hmm_di
set "QGAI_ROOT="

echo.
echo ============================================================
echo   DONE. Compare:
echo     OLD (ADX/DI_diff HMM) : wfo_live_match_015  = +483.0R
echo     NEW (+DI/-DI HMM)     : wfo_hmm_di\_WFO_SUMMARY.txt
echo   Profit-first: adopt ONLY if new total R is NOT worse.
echo   Also open a few wfo_hmm_di\signals_*.csv and check slow/flat
echo   bars now read Ranging (not Volatile).
echo ============================================================
pause
