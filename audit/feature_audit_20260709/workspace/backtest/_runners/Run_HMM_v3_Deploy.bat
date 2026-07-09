@echo off
title QGAI - APPLY NEW SETTINGS : as-of data + HMM v3 + retrain + verify
REM ---------------------------------------------------------------------------
REM THE "apply new settings" bat (updated 2026-07-02 after FIX-1). Run ONLY
REM after the as-of A/B WFO ("asof wfo done" -> Claude confirms the winner).
REM Default variant below is "rel" - EDIT to "legacy" ONLY if legacy won.
REM
REM Applies, in one atomic pass:
REM   1. backup live models -> data\models\_backup_pre_hmm_v3
REM   2. leak-free AS-OF adx_merged.csv (regen_adx_asof --apply, auto-backup)
REM      (mt5_data_updater.py is already patched to keep future updates as-of)
REM   3. retrain ALL live models on the honest data with the winning HMM
REM   4. acceptance verification (cluster stats, stability, flat-window)
REM Then: restart bridge - DEMO FIRST.
REM Revert = copy _backup_pre_hmm_v3 back into data\models\final + restore the
REM adx_merged .bak_preasof_* backup + revert code + restart.
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_HMM_VARIANT=rel"
cd /d "C:\QGAI\engine"

echo ============================================================
echo   Variant: %QGAI_HMM_VARIANT%   (edit this bat to change)
echo   [1/4] Backing up current LIVE models...
echo ============================================================
robocopy "C:\QGAI\data\models\final" "C:\QGAI\data\models\_backup_pre_hmm_v3" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP >nul
echo   Backup done: C:\QGAI\data\models\_backup_pre_hmm_v3

echo ============================================================
echo   [2/4] Applying leak-free AS-OF ADX data (auto-backup of old file)
echo ============================================================
"%PY%" regen_adx_asof.py --apply
if errorlevel 1 (echo AS-OF APPLY FAILED - STOP. Tell Claude. & pause & exit /b 1)

echo ============================================================
echo   [3/4] Retraining LIVE models (train.py) on honest data...
echo   Watch: "HMM variant: %QGAI_HMM_VARIANT%" + Volatile cluster = HIGH vol.
echo ============================================================
"%PY%" train.py

echo ============================================================
echo   [4/4] Acceptance verification (flat window + stability)
echo ============================================================
"%PY%" verify_hmm_window.py

echo.
echo If verification shows ALL CHECKS PASSED:
echo   1. RESTART the bridge (DEMO account first - test before live!)
echo   2. Watch dashboard states: flat hours should read Ranging now.
echo If FAILED: revert (see REM header) + tell Claude.
pause
