@echo off
title QGAI - Relabel trades (closed-loop, live HTF exit)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   RELABEL TRADES (Task 1) - closed-loop
echo   Recomputes Win/R/exit of every training entry under the
echo   CURRENT LIVE exit engine (ratchet + HTF H1 SL/flip + TP cap).
echo   Output: data\Back_testing_data_final_cleaned_RELABELED.xlsx
echo ============================================================
echo.
"%PY%" relabel_trades.py
echo.
echo ============================================================
echo   DONE. To use it: in config.py set
echo     trades_file -^> Back_testing_data_final_cleaned_RELABELED.xlsx
echo   then run Start\3_Train_Models.bat, then WFO-validate vs current.
echo ============================================================
pause
