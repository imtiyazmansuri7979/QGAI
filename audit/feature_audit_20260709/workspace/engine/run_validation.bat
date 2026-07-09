@echo off
cd /d C:\QGAI\engine

echo ====== RUN 1/6: P1 fixed ======
python backtest_replay.py --from 2025-04-01 --to 2025-09-30 --equity 10000 --risk 0.22
copy /Y logs\backtest_report.txt logs\report_p1_fixed.txt

echo ====== RUN 2/6: P1 predicted ======
python backtest_replay.py --from 2025-04-01 --to 2025-09-30 --equity 10000 --risk 0.22 --tp-mode predicted --sl-mode predicted
copy /Y logs\backtest_report.txt logs\report_p1_pred.txt

echo ====== RUN 3/6: P1 BUY-only ======
python backtest_replay.py --from 2025-04-01 --to 2025-09-30 --equity 10000 --risk 0.22 --tp-mode predicted --sl-mode predicted --pred-dirs BUY
copy /Y logs\backtest_report.txt logs\report_p1_buyonly.txt

echo ====== RUN 4/6: P2 fixed ======
python backtest_replay.py --from 2025-10-01 --to 2025-12-31 --equity 10000 --risk 0.22
copy /Y logs\backtest_report.txt logs\report_p2_fixed.txt

echo ====== RUN 5/6: P2 predicted ======
python backtest_replay.py --from 2025-10-01 --to 2025-12-31 --equity 10000 --risk 0.22 --tp-mode predicted --sl-mode predicted
copy /Y logs\backtest_report.txt logs\report_p2_pred.txt

echo ====== RUN 6/6: P2 BUY-only ======
python backtest_replay.py --from 2025-10-01 --to 2025-12-31 --equity 10000 --risk 0.22 --tp-mode predicted --sl-mode predicted --pred-dirs BUY
copy /Y logs\backtest_report.txt logs\report_p2_buyonly.txt

echo.
echo ALL 6 RUNS DONE — reports are in logs\report_p*.txt
pause
