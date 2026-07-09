@echo off
cd /d C:\QGAI\engine

echo ====== RUN 1/4: P1 BUY-only predicted ======
python backtest_replay.py --from 2025-04-01 --to 2025-09-30 --equity 10000 --risk 0.22 --tp-mode predicted --sl-mode predicted --pred-dirs BUY
copy /Y logs\backtest_report.txt logs\report_p1_buyonly.txt

echo ====== RUN 2/4: P1 hybrid ======
python backtest_replay.py --from 2025-04-01 --to 2025-09-30 --equity 10000 --risk 0.22 --tp-mode hybrid --sl-mode predicted
copy /Y logs\backtest_report.txt logs\report_p1_hybrid.txt

echo ====== RUN 3/4: P2 BUY-only predicted ======
python backtest_replay.py --from 2025-10-01 --to 2025-12-31 --equity 10000 --risk 0.22 --tp-mode predicted --sl-mode predicted --pred-dirs BUY
copy /Y logs\backtest_report.txt logs\report_p2_buyonly.txt

echo ====== RUN 4/4: P2 hybrid ======
python backtest_replay.py --from 2025-10-01 --to 2025-12-31 --equity 10000 --risk 0.22 --tp-mode hybrid --sl-mode predicted
copy /Y logs\backtest_report.txt logs\report_p2_hybrid.txt

echo.
echo ALL 4 RUNS DONE — reports in logs\report_p*_buyonly.txt and report_p*_hybrid.txt
pause
