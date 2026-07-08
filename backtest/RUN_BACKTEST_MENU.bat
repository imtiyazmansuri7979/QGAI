@echo off
setlocal
chcp 65001 >nul

set "ROOT=C:\QGAI"
set "BACKTEST=C:\QGAI\backtest"
set "RUNNERS=C:\QGAI\backtest\_runners"
set "ENTRY=C:\QGAI\backtest\results\buy_sell_entry_timing_research"
set "EXIT=C:\QGAI\backtest\results\available_move_vs_captured_move_research"

:menu
cls
echo ============================================================
echo QGAI BACKTEST MENU
echo ============================================================
echo.
echo  1. SELL early-entry real backtest
echo  2. Baseline full backtest + BUY/SELL entry research
echo  3. Baseline full HMM 10k lot001 backtest
echo  4. Exit research Phase 3 menu
echo  5. Combined entry + exit real backtest
echo  6. Entry variant 3-way full backtest
echo  7. WFO live-match buffer 0.15
echo  8. Open runners folder
echo  9. Open organized backtest index
echo 10. Exit TP-cap sweep 0.50 to 3.00
echo 11. Entry max_open=2 policy tests
echo 12. ADX6 strength soft entry tests
echo 13. SMMA MTF score entry tests
echo  0. Exit
echo.
set /p CHOICE=Select option: 

if "%CHOICE%"=="1" call "%ENTRY%\RUN_SELL_EARLY_CONFIRM2_TV_FULL_BACKTEST.bat" & goto menu
if "%CHOICE%"=="2" call "%ENTRY%\RUN_FULL_BACKTEST_THEN_BUY_SELL_ENTRY_RESEARCH.bat" & goto menu
if "%CHOICE%"=="3" call "%RUNNERS%\Run_FullBT_HMM_10k_lot001.bat" & goto menu
if "%CHOICE%"=="4" call "%EXIT%\RUN_PHASE3_RESEARCH_MENU.bat" & goto menu
if "%CHOICE%"=="5" call "%ENTRY%\RUN_COMBO_SELL_EARLY_PLUS_TRAIL_CONFIRM2_FULL_BACKTEST.bat" & goto menu
if "%CHOICE%"=="6" call "%ENTRY%\RUN_ENTRY_VARIANT_3WAY_FULL_BACKTEST.bat" & goto menu
if "%CHOICE%"=="7" call "%RUNNERS%\Run_WFO_LiveMatch_Buf015.bat" & goto menu
if "%CHOICE%"=="8" explorer "%RUNNERS%" & goto menu
if "%CHOICE%"=="9" notepad "%BACKTEST%\BACKTEST_FOLDER_INDEX.md" & goto menu
if "%CHOICE%"=="10" call "%EXIT%\RUN_EXIT_TP_CAP_SWEEP_050_TO_300.bat" & goto menu
if "%CHOICE%"=="11" call "%ENTRY%\RUN_ENTRY_MAXOPEN2_POLICY_TESTS.bat" & goto menu
if "%CHOICE%"=="12" call "%ENTRY%\RUN_ADX6_STRENGTH_SOFT_TESTS.bat" & goto menu
if "%CHOICE%"=="13" call "%ENTRY%\RUN_SMMA_MTF_SCORE_TESTS.bat" & goto menu
if "%CHOICE%"=="0" exit /b 0

echo.
echo Invalid choice.
pause
goto menu
