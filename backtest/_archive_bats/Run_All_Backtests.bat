@echo off
title QGAI - Run All Backtests (resumable)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "SCRIPTS=htf_vs_m15_backtest session_tf_backtest h1_tp_sweep h1_buffer_sweep aligned_htf_exit_backtest final_backtest risk_sweep monte_carlo_resample"
cd /d "C:\QGAI\backtest"
if not exist results mkdir results
echo ============================================================
echo   QGAI - RUNNING ALL BACKTESTS  (RESUMABLE)
echo   Already-finished ones are SKIPPED. If a run stops midway,
echo   just double-click this file again - it continues.
echo   To force re-run everything: delete the  results  folder
echo   (or run  Reset_Backtests.bat).
echo ============================================================
echo.
for %%F in (%SCRIPTS%) do (
    if exist "results\%%F.txt" (
        echo   [SKIP - already done]  %%F
    ) else (
        echo   Running %%F  ...
        "%PY%" "%%F.py" > "results\%%F.tmp" 2>&1
        move /y "results\%%F.tmp" "results\%%F.txt" >nul
        echo   [done]  %%F
    )
)
echo.
echo   Combining results into ALL_RESULTS.txt ...
type nul > ALL_RESULTS.txt
for %%F in (%SCRIPTS%) do (
    echo ================================================================ >> ALL_RESULTS.txt
    echo  ^>^>^>  %%F >> ALL_RESULTS.txt
    echo ================================================================ >> ALL_RESULTS.txt
    if exist "results\%%F.txt" ( type "results\%%F.txt" >> ALL_RESULTS.txt ) else ( echo [NOT RUN YET] >> ALL_RESULTS.txt )
    echo. >> ALL_RESULTS.txt
)
echo.
echo ============================================================
echo   ALL DONE. Full results: C:\QGAI\backtest\ALL_RESULTS.txt
echo ============================================================
notepad ALL_RESULTS.txt
pause >nul
