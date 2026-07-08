@echo off
setlocal
chcp 65001 >nul

REM =====================================================================
REM  SMMA-winner (linear W25/35/40 T70 max +0.06) — FULL QUARTERLY OOS
REM
REM  Runs the SAME winning config on 4 non-overlapping quarters.
REM  Goal: confirm in-sample edge (+51R vs baseline over full year)
REM  is not concentrated in one quarter (luck-vs-edge check).
REM
REM  Resume-safe: skips a quarter if backtest_report.txt already exists.
REM  Each quarter gets its own sub-folder with .txt + summary + trades CSVs.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "SCRIPT=C:\QGAI\backtest\_scripts\backtest_replay_entry_exit_combo_research.py"
set "OUT_ROOT=C:\QGAI\backtest\results\smma_winner_oos_quarterly"

set "BASE_ARGS=--equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --research-trail-confirm-bars 2 --sell-early-confirm2-tv --max-open 1 --no-ctf-fade"
set "SMMA_ARGS=--smma-mtf-soft --smma-penalty-mode linear --smma-weight-m15 0.25 --smma-weight-h1 0.35 --smma-weight-h4 0.40 --smma-linear-target 70 --smma-max-penalty 0.06"

set "BASE_BT_ARGS=--equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --research-trail-confirm-bars 2 --sell-early-confirm2-tv --max-open 1 --no-ctf-fade"

if not exist "%OUT_ROOT%" mkdir "%OUT_ROOT%"

cd /d "%ROOT%"

REM ─────────── Q1: 2025-06-29 → 2025-09-29 ───────────
set "Q=%OUT_ROOT%\Q1_2025Q3_smma"
set "QB=%OUT_ROOT%\Q1_2025Q3_baseline"
echo ============================================================
echo [Q1/4] 2025-06-29 -^> 2025-09-29  (SMMA + Baseline)
echo ============================================================
if exist "%Q%\backtest_report.txt" ( echo Q1 SMMA already done - skip. ) else (
  %PY% "%SCRIPT%" --from 2025-06-29 --to 2025-09-29 %BASE_ARGS% %SMMA_ARGS% --out-dir "%Q%"
  if errorlevel 1 goto fail
)
if exist "%QB%\backtest_report.txt" ( echo Q1 Baseline already done - skip. ) else (
  %PY% "%SCRIPT%" --from 2025-06-29 --to 2025-09-29 %BASE_BT_ARGS% --out-dir "%QB%"
  if errorlevel 1 goto fail
)

REM ─────────── Q2: 2025-09-29 → 2025-12-29 ───────────
set "Q=%OUT_ROOT%\Q2_2025Q4_smma"
set "QB=%OUT_ROOT%\Q2_2025Q4_baseline"
echo ============================================================
echo [Q2/4] 2025-09-29 -^> 2025-12-29  (SMMA + Baseline)
echo ============================================================
if exist "%Q%\backtest_report.txt" ( echo Q2 SMMA already done - skip. ) else (
  %PY% "%SCRIPT%" --from 2025-09-29 --to 2025-12-29 %BASE_ARGS% %SMMA_ARGS% --out-dir "%Q%"
  if errorlevel 1 goto fail
)
if exist "%QB%\backtest_report.txt" ( echo Q2 Baseline already done - skip. ) else (
  %PY% "%SCRIPT%" --from 2025-09-29 --to 2025-12-29 %BASE_BT_ARGS% --out-dir "%QB%"
  if errorlevel 1 goto fail
)

REM ─────────── Q3: 2025-12-29 → 2026-03-29 ───────────
set "Q=%OUT_ROOT%\Q3_2026Q1_smma"
set "QB=%OUT_ROOT%\Q3_2026Q1_baseline"
echo ============================================================
echo [Q3/4] 2025-12-29 -^> 2026-03-29  (SMMA + Baseline)
echo ============================================================
if exist "%Q%\backtest_report.txt" ( echo Q3 SMMA already done - skip. ) else (
  %PY% "%SCRIPT%" --from 2025-12-29 --to 2026-03-29 %BASE_ARGS% %SMMA_ARGS% --out-dir "%Q%"
  if errorlevel 1 goto fail
)
if exist "%QB%\backtest_report.txt" ( echo Q3 Baseline already done - skip. ) else (
  %PY% "%SCRIPT%" --from 2025-12-29 --to 2026-03-29 %BASE_BT_ARGS% --out-dir "%QB%"
  if errorlevel 1 goto fail
)

REM ─────────── Q4: 2026-03-29 → 2026-06-29 ───────────
set "Q=%OUT_ROOT%\Q4_2026Q2_smma"
set "QB=%OUT_ROOT%\Q4_2026Q2_baseline"
echo ============================================================
echo [Q4/4] 2026-03-29 -^> 2026-06-29  (SMMA + Baseline)
echo ============================================================
if exist "%Q%\backtest_report.txt" ( echo Q4 SMMA already done - skip. ) else (
  %PY% "%SCRIPT%" --from 2026-03-29 --to 2026-06-29 %BASE_ARGS% %SMMA_ARGS% --out-dir "%Q%"
  if errorlevel 1 goto fail
)
if exist "%QB%\backtest_report.txt" ( echo Q4 Baseline already done - skip. ) else (
  %PY% "%SCRIPT%" --from 2026-03-29 --to 2026-06-29 %BASE_BT_ARGS% --out-dir "%QB%"
  if errorlevel 1 goto fail
)

echo.
echo ============================================================
echo ALL 4 QUARTERS DONE (SMMA + Baseline pairs).
echo Root: %OUT_ROOT%
echo Next: compare per-Q  Total R / WR / PF / DD  SMMA vs Baseline.
echo (If SMMA wins in 3/4 quarters -^> real edge. If only 1/4 -^> luck.)
echo ============================================================
pause
exit /b 0

:fail
echo *** RUN FAILED — check the last folder's log. Bat is resume-safe: fix and re-run. ***
pause
exit /b 1
