@echo off
title QGAI - Live Chart Refresher
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"

echo ============================================================
echo   QGAI - LIVE SIGNALS CHART REFRESHER
echo ------------------------------------------------------------
echo   Builds the real M15 candle chart with all bridge signals.
echo   Updates after every 15-minute candle close.
echo.
echo   Keep this window open.
echo   Open chart: http://localhost:8000/chart.html
echo   Stop: Ctrl+C
echo ============================================================
echo.

:loop
echo [%date% %time%] Pulling REAL closed M15 candles from MT5...
"%PY%" chart_live_ohlc.py 1500
echo.
echo [%date% %time%] Refreshing shadow ledger...
"%PY%" shadow_ledger.py
echo.
echo [%date% %time%] Building chart JSON...
"%PY%" chart_data.py 1200
echo.
echo [%date% %time%] Chart ready: http://localhost:8000/chart.html
echo Waiting for next M15 candle close...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$now=Get-Date; $next=$now.AddMinutes(15-($now.Minute %% 15)).AddSeconds(-$now.Second).AddMilliseconds(-$now.Millisecond).AddSeconds(8); if($next -le $now){$next=$next.AddMinutes(15)}; $wait=[int][Math]::Max(5,($next-$now).TotalSeconds); Write-Host ('Next refresh at ' + $next.ToString('HH:mm:ss') + '  (' + $wait + ' sec)'); Start-Sleep -Seconds $wait"
echo.
goto loop
