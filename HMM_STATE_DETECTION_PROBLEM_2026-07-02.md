# QGAI — HMM Market-State Detection Problem (handoff / full detail)

*XAUUSD M15 · GaussianMixture 3-state (Ranging/Trending/Volatile) · 2026-07-02 · profit-first, ATR ruled out*

## Problem

SYMPTOM: during very slow / flat price the HMM reports state = 'Volatile'. Live proof (2026-07-02 08:00->13:15, 22 M15 bars): net move +1.90 pts = +0.047% (flat), total range 0.658%, avg bar 0.212% — yet the HMM said 'Volatile' on EVERY bar. WHY IT MATTERS: state drives everything downstream — the per-state entry threshold (Volatile=0.42 lowest -> more trades), which model is used (model_ranging/trending/volatile), and buffer/TP-regime. A wrong state => wrong thresholds, over-trading in chop, and it fed the earlier BUY/SELL flip-flop. GOAL: state must reflect ACTUAL volatility, not be a misnomer. Constraint: ATR is ruled out (lagging; already removed 2026-06-19). Judge any change PROFIT-FIRST (WFO total R must not drop).

## Diagnosis journey

| Stage | What was done | Result |
|---|---|---|
| Original (live before today) | HMM_FEATURES = {TF}_ADX + {TF}_DI_diff (8 feats). Label: lowest ADX=Ranging; of rest high\|DI_diff\|=Trending, low\|DI_diff\|=Volatile. | MISLABEL. DI_diff (the difference) can't separate QUIET (both DI low) from CHOP (both DI high, close) — both small diff -> both 'Volatile'. Also ADX lags (flat price but elevated ADX). Slow -> Volatile. |
| Attempt 1 — raw +DI/-DI | Exposed {TF}_PlusDI/{TF}_MinusDI (mt5_data_updater), HMM_FEATURES = ADX,+DI,-DI x4 (12). Label by clarity=\|+DI - -DI\| and di_sum. | BAD. Feeding RAW +DI/-DI made GMM cluster by DIRECTION (up/down/flat). Cluster stats: Trending +DI27.3/-DI14.2 (uptrend), 'Ranging' +DI14.2/-DI27.0 (DOWNTREND mislabeled!), Volatile clarity0.2 (flat). Full dist 95.4% Ranging / 4.2% Trending / 0.4% Volatile — degenerate. |
| Attempt 2 — direction-agnostic | Added _engineer(): raw [ADX,+DI,-DI] -> [ADX, di_sum=+DI+-DI, di_clarity=\|+DI - -DI\|] per TF (direction-agnostic). Cluster+label on those. | BETTER LABELS but STILL NOT SOLVED. Cluster stats: Trending ADX43.3/sum42.4/clarity23.0; Volatile ADX33.3/sum42.8/clarity12.2; Ranging ADX25.3/sum40.2/clarity8.9 (lowest = quiet, sane). BUT full dist = Ranging 0.6% / Trending 34.4% / Volatile 65.0% (Ranging almost never fires; slow likely STILL Volatile). Unstable: train-subset Ranging 37.2% vs full 0.6%. |

## Root cause

| Aspect | Detail |
|---|---|
| Core | ADX, +DI, -DI all measure DIRECTIONAL STRENGTH, not PRICE VOLATILITY. di_sum (+DI + -DI) is nearly CONSTANT across clusters (40.2 / 42.4 / 42.8) -> it does not discriminate how much price actually moved. |
| Consequence | With no true volatility feature, the GMM splits on ADX + clarity (both direction-strength). A slow but not-clearly-directional bar lands in the mid-ADX 'Volatile' cluster. So 'Volatile' still ~ 'directionally-unclear', not 'high volatility'. |
| ATR | Ruled out — lagging; removed 2026-06-19 (features.py:134). Not an option. |

## Recommended fix

| Item | Detail |
|---|---|
| Recommended | Add a REAL volatility / range feature to the HMM, per TF. Two lag-free options ALREADY computed in the codebase: |
| Option A — band_width_pct | 2-SMMA band width = (MA(High)-MA(Low))/close*100, lag-free at Period=2. Computed in trend_signal.py:115 (out['band_width_pct']). Used by the RATCHET band-buffer. This is the user's own preferred gauge. |
| Option B — range_pct | Per-bar (high-low)/close*100. Computed in features.py:125. Simplest direct 'how much did price move this bar'. Also range_ma10 / range_ratio available (features.py:141-142). |
| Then | HMM_FEATURES per TF = [ADX, di_clarity(=\|+DI - -DI\|), band_width_pct OR range_pct]. Now: wide band/range + low clarity = REAL Volatile; narrow band/range = Ranging (quiet); high clarity = Trending. Direction-agnostic + volatility-aware. |
| Implementation | (1) add the chosen vol column(s) per TF into data/merged/adx_merged.csv (extend regen_adx_di.py — for band, port trend_signal.compute_trend per TF; for range, compute (H-L)/C on each resampled TF). (2) update hmm_model.HMM_FEATURES + _engineer/labeling to include it. (3) retrain (train.py). (4) verify cluster stats: Volatile=high band/range, Ranging=low; and train-vs-full distribution SIMILAR (stability). (5) verify the flat 2026-07-02 08:00-13:15 window now reads Ranging. (6) WFO vs old baseline +483R (profit-first). |

## Files involved (with lines)

| File | Role / lines |
|---|---|
| engine/hmm_model.py | MarketStateHMM (sklearn GaussianMixture, 3 comp, full cov, random_state=42). HMM_FEATURES, _engineer() transform, fit() cluster-labeling, predict/predict_batch/predict_proba. CURRENTLY = attempt-2 (12 feats +DI/-DI, direction-agnostic transform). |
| engine/mt5_data_updater.py | ADX/+DI/-DI generator. compute_adx_tf (lines ~49-62) now returns adx, di_diff, pdi, ndi. Result writes {TF}_ADX/{TF}_DI_diff/{TF}_PlusDI/{TF}_MinusDI (~lines 154-159). |
| engine/features.py | load_adx (172); DI_diff=PlusDI-MinusDI (185); _wilder_adx pdi/ndi (885); range_pct (125); range_ma10/range_ratio (141-142). ATR removed note (134). |
| engine/trend_signal.py | compute_trend(); band_width_pct = (MA(High)-MA(Low))/close*100 (line 115) — lag-free 2-SMMA volatility. |
| engine/regen_adx_di.py | Rebuilds data/merged/adx_merged.csv from ohlc_merged.csv with ADX/DI_diff/PlusDI/MinusDI x4 (same method as live updater; DI_diff parity vs old = 0.000). EXTEND THIS to also add band_width_pct / range_pct per TF. |
| engine/config.py | CFG.hmm.n_states=3, CFG.hmm.random_state=42. |
| engine/inference.py | Uses hmm_state for the per-state threshold: Ranging=base+0.03 (0.48), Trending=base (0.45), Volatile=max(0.42,base-0.03) (0.42). Also selects model_ranging/trending/volatile by state. |
| data/merged/adx_merged.csv | NOW has {TF}_ADX/{TF}_DI_diff/{TF}_PlusDI/{TF}_MinusDI x4 (regen done). band_width_pct / range_pct NOT yet in it. |

## Current state (code / data / models / backups)

| Area | State |
|---|---|
| Code | hmm_model.py = attempt-2 (12-feat +DI/-DI, direction-agnostic). mt5_data_updater outputs +DI/-DI. regen_adx_di.py exists. |
| Data | adx_merged.csv regenerated WITH +DI/-DI (parity 0.000 vs old DI_diff). Backup: adx_merged.csv.bak_prediregen. |
| Live models | data/models/final = RETRAINED to attempt-2 (12-feat HMM). NOT deployed — bridge still running OLD 8-feat model in memory. DO NOT restart the bridge until a good HMM is chosen (else 12-feat pkl works but is the not-good attempt-2). |
| Backups (revert) | data/models/final_backup_pre_hmm_di_manual = ORIGINAL good 8-feature models. data/models/final_backup_relabeled_20260628 = Jun-28 full set. Revert = copy a backup into final + REVERT hmm_model.py/mt5_data_updater.py code + restart. |
| Bats | backtest/Run_Regen_ADX.bat, Run_HMM_DI_Deploy.bat, Run_HMM_DI_WFO.bat. |

## READY-TO-PASTE PROMPT for the solver

```
You are fixing the market-state (regime) detector in a live XAUUSD M15 algo-trading system (QGAI, folder C:\QGAI, engine in C:\QGAI\engine). Work carefully — this is LIVE trading code.

PROBLEM
The HMM (sklearn GaussianMixture, 3 states: Ranging / Trending / Volatile) mislabels SLOW / FLAT markets as "Volatile". Live proof: 2026-07-02 08:00->13:15 the price was flat (net +0.047%, total range 0.66%) yet every bar read "Volatile". This matters because state sets the entry threshold (Volatile=0.42, lowest -> more trades), picks the per-state model, and drives buffer/TP-regime. So a wrong state = over-trading in chop.

ROOT CAUSE (already diagnosed)
The HMM only uses ADX + directional-index features, which measure DIRECTIONAL STRENGTH, not PRICE VOLATILITY:
 - Original: {TF}_ADX + {TF}_DI_diff -> DI_diff can't tell QUIET (both DI low) from CHOP (both DI high but close); both give a small diff -> both "Volatile".
 - Attempt 1 (raw +DI/-DI): GMM clustered by DIRECTION (up/down/flat); a downtrend got labeled "Ranging"; 95% one state. BAD.
 - Attempt 2 (direction-agnostic transform [ADX, di_sum=+DI+-DI, di_clarity=|+DI - -DI|]): labels sane, BUT di_sum is nearly constant across clusters (40.2/42.4/42.8) so it does NOT discriminate volatility -> full-data distribution 65% Volatile / 0.6% Ranging, and unstable (train 37% Ranging vs full 0.6%). Still not solved.

TASK
Make the HMM state reflect ACTUAL volatility. Add a real, lag-free VOLATILITY / RANGE feature per timeframe (M15/M30/H1/H4) to the state model. DO NOT use ATR (lagging; removed 2026-06-19). Use one of these already-computed measures:
 - band_width_pct = (MA(High)-MA(Low))/close*100, 2-SMMA Period=2, lag-free — trend_signal.py line 115 (out['band_width_pct']).  [PREFERRED]
 - range_pct = (high-low)/close*100 — features.py line 125 (+ range_ma10/range_ratio 141-142).
Target feature set per TF: [ADX, di_clarity(=|+DI - -DI|), band_width_pct OR range_pct]. Then wide band/range + low clarity = real Volatile; narrow = Ranging (quiet); high clarity = Trending.

STEPS
1. Add the chosen volatility column(s) per TF into data/merged/adx_merged.csv by EXTENDING engine/regen_adx_di.py (it already rebuilds ADX/DI_diff/PlusDI/MinusDI from data/merged/ohlc_merged.csv; for band, port trend_signal.compute_trend per resampled TF; for range, compute (H-L)/C per TF). Keep a DI_diff parity check.
2. Update engine/hmm_model.py: HMM_FEATURES + _engineer()/labeling to use [ADX, di_clarity, vol]. Keep GaussianMixture(3, full cov, random_state=42).
3. Retrain: python train.py (writes data/models/final).
4. VERIFY (print already added): cluster stats must show Volatile = HIGH band/range, Ranging = LOW; and the train-subset vs full-data state distribution must be SIMILAR (stability). Confirm the flat 2026-07-02 08:00-13:15 window now reads Ranging (or Trending), NOT Volatile.
5. VALIDATE profit-first: run WFO (backtest/Run_HMM_DI_WFO.bat pattern: run_wfo.py --start 2025-06-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime, in a workdir via QGAI_ROOT so live models are untouched). ADOPT ONLY IF total R is NOT worse than the old baseline +483.0R (wfo_live_match_015).

CONSTRAINTS / SAFETY
 - LIVE bridge is running the OLD 8-feature model in memory; the file is currently the not-good attempt-2. DO NOT restart the bridge until a GOOD HMM is trained and WFO-validated.
 - Backups for revert: data/models/final_backup_pre_hmm_di_manual (original 8-feature) and final_backup_relabeled_20260628. Reverting requires restoring models AND reverting hmm_model.py / mt5_data_updater.py code.
 - No ATR. Judge by PROFIT (total R), not by flip-count or PF alone. Test on demo before live.

ACCEPTANCE
Flat/slow bars read Ranging; genuinely churny/wide-range bars read Volatile; state distribution stable train-vs-full; WFO total R >= +483R. Then retrain live + restart bridge to deploy.
```
