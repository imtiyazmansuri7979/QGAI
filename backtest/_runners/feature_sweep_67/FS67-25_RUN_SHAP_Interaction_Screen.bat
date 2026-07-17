@echo off
setlocal
chcp 65001 >nul
call "%~dp0..\_console_theme.bat"
title QGAI - FS67-25 - SHAP Interaction Screen (zero-retrain triage)

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%ROOT%\engine"

echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  FS67-25 - SHAP Interaction Screen (zero-retrain)%QGAI_RESET%
echo %QGAI_DIM%------------------------------------------------------------%QGAI_RESET%
echo.
echo   Purpose (Fable-5, 2026-07-17): find which feature PAIRS have hidden
echo   interactions (like 15_min_slot + M15_ADX) WITHOUT retraining. Uses
echo   XGBoost's built-in pred_interactions on the ALREADY-TRAINED live
echo   model -- one scoring pass, no training, no backtest.
echo.
echo   This is a TRIAGE step, not a decision. Output ranks feature pairs
echo   by interaction strength. Only the top-ranked pairs (especially
echo   where one side is already dropped) need a real confirmation
echo   backtest afterward (QGAI_ABLATE="featA,featB").
echo.
echo   Analyzes: data\models\final\xgb_model.pkl (main live model)
echo   Does NOT touch or retrain any model. Read-only analysis.
echo.
echo   %QGAI_YELLOW%Estimated time: ~5-10 minutes (no training, analysis only)%QGAI_RESET%
echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%

echo.
"%PY%" analyze_feature_interactions.py --model xgb_model.pkl --top 40 --sample 3000
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  FS67-25 DONE%QGAI_RESET%
echo   Results: backtest\results\feature_sweep_67\FS67-25_shap_interactions\
echo     interaction_matrix_full.csv     - every pair, ranked
echo     interaction_matrix_flagged.csv  - pairs where >=1 side is dropped/low-importance
echo.
echo   Next: pick the top 3-5 flagged pairs and confirm with a real
echo   backtest (QGAI_ABLATE="featA,featB" on train.py + backtest_replay.py),
echo   same pattern as FS67-23's joint-drop isolation run.
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%

pause
exit /b 0

:fail
echo.
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_RED%%QGAI_BOLD%  FAILED FS67-25%QGAI_RESET%
echo   Check error output above.
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
pause
exit /b 1
