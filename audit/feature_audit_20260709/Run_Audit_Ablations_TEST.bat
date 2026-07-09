@echo off
setlocal EnableExtensions
title QGAI Feature Audit Ablations TEST

set ROOT=%~dp0workspace
set PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe
set START=2026-06-01
set END=2026-06-15
set WEEKS=2

echo ============================================================
echo   QGAI FEATURE AUDIT ABLATIONS - TEST ONLY
echo ------------------------------------------------------------
echo   Isolated workspace:
echo   %ROOT%
echo.
echo   No live files are changed.
echo ============================================================

pushd "%ROOT%\engine"

call :RUN A_current ""
call :RUN B_basic_safe "slot_win_rate,hmm_state,h4_trending_h1_aligned,h4_ranging_h1_neutral,h4_h1_regime_score,adx_trend_count,in_range_phase,h4_in_ob_zone,h4_ob_strength,h1_ob_strength,corr_imp_ratio,mins_to_next_3star,mins_since_last_3star"
call :RUN C_no_slot "slot_win_rate"
call :RUN D_no_hmm "hmm_state"
call :RUN E_no_adx_engineered "adx_trend_count,h4_trending_h1_aligned,h4_ranging_h1_neutral,h4_h1_regime_score"
call :RUN F_no_ob_strength_zone "h4_in_ob_zone,h4_ob_strength,h1_ob_strength"
call :RUN G_no_sr_dist "h4_resist_dist,h4_support_dist,h1_resist_dist,h1_support_dist"
call :RUN H_no_news_timing "mins_to_next_3star,mins_since_last_3star"
call :RUN I_no_in_range "in_range_phase"
call :RUN J_no_corr_imp "corr_imp_ratio"

popd
echo.
echo Done. Results are under:
echo %ROOT%\backtest\results\audit_test_*
pause
exit /b 0

:RUN
set NAME=%~1
set ABL=%~2
echo.
echo ------------------------------------------------------------
echo Running %NAME%
echo QGAI_ABLATE=%ABL%
echo ------------------------------------------------------------
set QGAI_ABLATE=%ABL%
"%PY%" run_wfo.py --start %START% --end %END% --weeks %WEEKS% --buf 0.15 --tp-equity 0 --equity 10000 --risk 3 --tp-regime --results-dir audit_test_%NAME%
exit /b 0
