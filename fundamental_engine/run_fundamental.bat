@echo off
chcp 65001 >nul
title Fundamental Engine - Full Run

echo ======================================================================
echo  FUNDAMENTAL ENGINE - FULL PIPELINE RUN
echo  %date% %time%
echo ======================================================================
echo.

set PYTHON=python
set ENGINE=C:\QGAI\fundamental_engine\core

:: -----------------------------------------------------------------------
:: MENU
:: -----------------------------------------------------------------------
echo  [1] Full rebuild  (fetch + classify --force + reactions --force)
echo  [2] Quick update  (fetch + classify incremental + reactions)
echo  [3] Fetch only    (news_fetcher only)
echo  [4] Classify only (--force)
echo  [5] Reactions only (--force)
echo  [6] Status check  (scheduler state)
echo  [7] Run scheduler (live, press Ctrl+C to stop)
echo  [8] Dashboard      (compact trader view - http://localhost:5000)
echo  [9] Dashboard Full (complete analysis - http://localhost:5001)
echo.
set /p CHOICE=Choose [1-9]:

echo.

if "%CHOICE%"=="1" goto FULL_REBUILD
if "%CHOICE%"=="2" goto QUICK_UPDATE
if "%CHOICE%"=="3" goto FETCH_ONLY
if "%CHOICE%"=="4" goto CLASSIFY_ONLY
if "%CHOICE%"=="5" goto REACTIONS_ONLY
if "%CHOICE%"=="6" goto STATUS
if "%CHOICE%"=="7" goto SCHEDULER
if "%CHOICE%"=="8" goto DASHBOARD
if "%CHOICE%"=="9" goto DASHBOARD_FULL
echo Invalid choice.
goto END

:: -----------------------------------------------------------------------
:: 1 - FULL REBUILD
:: -----------------------------------------------------------------------
:FULL_REBUILD
echo [STEP 1/3] Fetching latest news from ForexFactory...
echo -----------------------------------------------------------------------
%PYTHON% "%ENGINE%\news_fetcher.py"
if errorlevel 1 ( echo [WARN] News fetch had errors, continuing... )
echo.

echo [STEP 2/3] Classifying all events (--force rebuild)...
echo -----------------------------------------------------------------------
%PYTHON% "%ENGINE%\classifier_v3.py" --force
if errorlevel 1 ( echo [ERROR] Classifier failed! & goto END )
echo.

echo [STEP 3/3] Building historical reactions (--force rebuild)...
echo -----------------------------------------------------------------------
%PYTHON% "%ENGINE%\historical_reactions.py" --force
if errorlevel 1 ( echo [ERROR] Reactions failed! & goto END )
echo.
goto DONE

:: -----------------------------------------------------------------------
:: 2 - QUICK UPDATE
:: -----------------------------------------------------------------------
:QUICK_UPDATE
echo [STEP 1/3] Fetching latest news from ForexFactory...
echo -----------------------------------------------------------------------
%PYTHON% "%ENGINE%\news_fetcher.py"
if errorlevel 1 ( echo [WARN] News fetch had errors, continuing... )
echo.

echo [STEP 2/3] Classifying new events (incremental)...
echo -----------------------------------------------------------------------
%PYTHON% "%ENGINE%\classifier_v3.py"
if errorlevel 1 ( echo [ERROR] Classifier failed! & goto END )
echo.

echo [STEP 3/3] Updating historical reactions (incremental)...
echo -----------------------------------------------------------------------
%PYTHON% "%ENGINE%\historical_reactions.py"
if errorlevel 1 ( echo [ERROR] Reactions failed! & goto END )
echo.
goto DONE

:: -----------------------------------------------------------------------
:: 3 - FETCH ONLY
:: -----------------------------------------------------------------------
:FETCH_ONLY
echo Fetching latest news from ForexFactory...
echo -----------------------------------------------------------------------
%PYTHON% "%ENGINE%\news_fetcher.py"
goto DONE

:: -----------------------------------------------------------------------
:: 4 - CLASSIFY ONLY
:: -----------------------------------------------------------------------
:CLASSIFY_ONLY
echo Classifying all events (--force)...
echo -----------------------------------------------------------------------
%PYTHON% "%ENGINE%\classifier_v3.py" --force
goto DONE

:: -----------------------------------------------------------------------
:: 5 - REACTIONS ONLY
:: -----------------------------------------------------------------------
:REACTIONS_ONLY
echo Rebuilding historical reactions (--force)...
echo -----------------------------------------------------------------------
%PYTHON% "%ENGINE%\historical_reactions.py" --force
goto DONE

:: -----------------------------------------------------------------------
:: 6 - STATUS
:: -----------------------------------------------------------------------
:STATUS
echo Scheduler status...
echo -----------------------------------------------------------------------
%PYTHON% "%ENGINE%\scheduler.py" --status
goto DONE

:: -----------------------------------------------------------------------
:: 7 - SCHEDULER
:: -----------------------------------------------------------------------
:SCHEDULER
echo Starting live scheduler (Ctrl+C to stop)...
echo -----------------------------------------------------------------------
%PYTHON% "%ENGINE%\scheduler.py"
goto DONE

:: -----------------------------------------------------------------------
:: 8 - DASHBOARD (compact trader)
:: -----------------------------------------------------------------------
:DASHBOARD
echo Starting compact trader dashboard on http://localhost:5000
echo Press Ctrl+C to stop.
echo -----------------------------------------------------------------------
pip install flask --quiet --break-system-packages 2>nul
start "" "http://localhost:5000"
%PYTHON% "C:\QGAI\fundamental_engine\dashboard.py"
goto DONE

:: -----------------------------------------------------------------------
:: 9 - DASHBOARD FULL (comprehensive)
:: -----------------------------------------------------------------------
:DASHBOARD_FULL
echo Starting full analysis dashboard on http://localhost:5000
echo Press Ctrl+C to stop.
echo -----------------------------------------------------------------------
pip install flask --quiet --break-system-packages 2>nul
start "" "http://localhost:5000"
%PYTHON% "C:\QGAI\fundamental_engine\core\dashboard.py"
goto DONE

:: -----------------------------------------------------------------------
:DONE
echo.
echo ======================================================================
echo  DONE - %date% %time%
echo ======================================================================
echo.

:END
pause
