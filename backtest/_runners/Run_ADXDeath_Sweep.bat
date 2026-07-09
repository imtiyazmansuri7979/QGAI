@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title QGAI - ADX-Death EXIT - 18-cell K x N x X sweep (in-sample)

REM =====================================================================
REM  ADX-Death exit param sweep: K{2,3} x N{2,3,4} x X{0.3,0.5,1.0}
REM  = 18 cells, fixed-lot 0.01, full in-sample year.
REM  Resume-safe: skips any cell whose report already exists.
REM
REM  ALSO runs baseline (ADX_DEATH OFF) for clean comparison.
REM  Total ~18-20 hr. Leave running overnight.
REM
REM  GATE: top-2 cells then WFO validation (separate bat).
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "OUTROOT=C:\QGAI\backtest\results\adx_death_sweep"
set "YEAR=--from 2025-06-29 --to 2026-06-29"
set "COMMON=%YEAR% --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"

if not exist "%OUTROOT%" mkdir "%OUTROOT%"
cd /d "%ROOT%\engine"

echo ============================================================
echo ADX-DEATH SWEEP  %DATE% %TIME%
echo   18 cells: K{2,3} x N{2,3,4} x X{0.3,0.5,1.0}
echo   + baseline (OFF)
echo ============================================================

REM -- Baseline (ADX_DEATH OFF) --
set QGAI_ADX_DEATH=
echo [BASELINE] ADX_DEATH OFF...
if not exist "%OUTROOT%\baseline\backtest_report.txt" ( "%PY%" "%SCRIPT%" %COMMON% --out-dir "%OUTROOT%\baseline" || goto fail )

REM -- Sweep --
set QGAI_ADX_DEATH=1

for %%K in (2 3) do (
    for %%N in (2 3 4) do (
        for %%X in (0.3 0.5 1.0) do (
            set "QGAI_ADX_DEATH_K=%%K"
            set "QGAI_ADX_DEATH_N=%%N"
            set "QGAI_ADX_DEATH_MIN_R=%%X"
            set "TAG=K%%K_N%%N_X%%X"
            echo [!TAG!] K=%%K N=%%N min_r=%%X ...
            if not exist "%OUTROOT%\!TAG!\backtest_report.txt" (
                "%PY%" "%SCRIPT%" %COMMON% --out-dir "%OUTROOT%\!TAG!" || goto fail
            ) else (
                echo   already done, skipping.
            )
        )
    )
)

set QGAI_ADX_DEATH=
echo.
echo ============================================================
echo ALL 18 CELLS + BASELINE DONE  %DATE% %TIME%
echo   Results: %OUTROOT%\
echo   Compare each cell's Total R vs baseline.
echo   GATE: pick top-2 by Total R, then WFO validate.
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED %DATE% %TIME% -- resume-safe: re-run to continue. ***
pause
exit /b 1
