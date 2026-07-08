@echo off
title QGAI - TP-cap sweep (with HTF + CTF enabled)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
set "OUT=..\backtest\results\backtests"
set "FROM=2025-09-01"
set "TO=2026-06-12"
REM --- $10,000 capital, 0.01 fixed lot, HTF flip + CTF-fade ON ; vary only TP cap % ---
set "BASE=--equity 10000 --fixed-lot 0.01 --stop-trail htf --ctf-fade"
echo ============================================================
echo   QGAI - TP-CAP SWEEP   (%FROM% .. %TO%)
echo   HTF flip + CTF-fade ON. Only ratchet_tp_cap_pct varies.
echo   Q: now that HTF lets trends ride, does a HIGHER TP beat 1%%?
echo   Variants: 0.5 0.6 0.7 0.8 0.9 1 1.1 1.2 1.3 1.4 1.5 2 3 %%
echo   Saves to backtest\results\backtests\tp_*  (resumable)
echo ============================================================
echo.
for %%T in (0.5 0.6 0.7 0.8 0.9 1 1.1 1.2 1.3 1.4 1.5 2 3) do (
  if exist "%OUT%\tp_%%T\backtest_report.txt" (
    echo   [SKIP] tp_%%T already done
  ) else (
    echo ----- TP cap = %%T %% --------------------------------------
    "%PY%" backtest_replay.py --from %FROM% --to %TO% %BASE% --tp-cap %%T --out-dir "%OUT%\tp_%%T"
  )
  echo.
)
echo ============================================================
echo   Done. Compare backtest\results\backtests\tp_*\backtest_report.txt
echo   Look at Total R + PF + Captured/Avail + Max DD per TP.
echo   Best TP -^> set config ratchet_tp_cap_pct to that value.
echo ============================================================
pause
