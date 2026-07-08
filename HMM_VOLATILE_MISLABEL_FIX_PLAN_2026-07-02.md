# QGAI — HMM "Volatile" Mislabel: Diagnosis & Fix Plan (+DI / −DI)

*XAUUSD M15 · HMM market-state detector · Generated 2026-07-02 · profit-first, ATR-free*

## Problem

Imtiyaz/Divyesh flagged: during VERY SLOW price movement the HMM reports state = "Volatile". That is wrong on its face (slow != volatile) and it matters because the Volatile state carries the LOWEST entry threshold (0.42), so the bot trades MORE in these mislabeled bars — the same zone where the BUY/SELL flip-flop was worst.

## Live evidence (2026-07-02, last ~5h)

Live confirmation (2026-07-02, last ~5 hours, 08:00->13:15, 22 M15 bars). Pulled from data/live/ohlc_live.csv + engine/logs/signals_all.csv. The market barely moved yet HMM said Volatile every bar.

| Metric | Value |
|---|---|
| Net move (5h) | +1.90 pts = +0.047%  -> essentially FLAT, market went nowhere |
| Total range (5h) | 26.73 pts = 0.658%  (tight band) |
| Avg bar range | 8.62 pts = 0.212%  (gold M15 avg ~0.145%) |
| HMM state, every bar | "Volatile"  (10:30-13:15 all Volatile, win_prob 0.32-0.39) |
| Verdict | QUIET / rangebound chop mislabeled VOLATILE. Oscillation -> +DI ~ -DI -> small DI_diff -> Volatile cluster. Root cause confirmed on live data. |

## Root cause

| Aspect | Detail |
|---|---|
| What the HMM sees | hmm_model.py HMM_FEATURES = M15_ADX, M15_DI_diff, M30_ADX, M30_DI_diff, H1_ADX, H1_DI_diff, H4_ADX, H4_DI_diff (8 values). NO volatility, NO ATR, NO band, NO volume. |
| How states are named | hmm_model.py fit(): lowest mean ADX -> Ranging(0); of the two higher-ADX clusters: high \|DI_diff\| -> Trending(1), low \|DI_diff\| -> Volatile(2). STATE_NAMES={0:Ranging,1:Trending,2:Volatile}. |
| The flaw | "Volatile" = high-ADX + SMALL \|DI_diff\| (DI+ ~ DI-). DI_diff is only the DIFFERENCE, so it cannot separate: (a) QUIET/slow = +DI low & -DI low -> small diff; (b) VOLATILE/chop = +DI high & -DI high (both strong, fighting) -> also small diff. Both land in the low-diff 'Volatile' cluster. |
| +DI / -DI are discarded | mt5_data_updater.py lines 58-59 compute pdi (+DI) and ndi (-DI), but line 62 returns only adx and (pdi-ndi); lines 158-159 write only {TF}_ADX and {TF}_DI_diff. The raw +DI/-DI LEVELS are thrown away — never saved to data/merged/adx_merged.csv, never seen by the HMM. features.py:185 also only derives DI_diff = PlusDI - MinusDI. |
| ATR ruled out | features.py:134 — ATR was REMOVED 2026-06-19 (lagging; volatility captured by the 2-SMMA). So ATR is NOT the fix. The system's lag-free volatility gauge is band_width_pct (trend_signal.py:115, = (MA(High)-MA(Low))/close*100). |

## Fix plan (+DI / −DI, ATR-free)

| Step | File / where | What to do |
|---|---|---|
| 1 | mt5_data_updater.py | Expose the levels the generator already computes. Change the ADX function to also return pdi & ndi (not just adx and pdi-ndi), and write result[f"{tf}_PlusDI"]=pdi, result[f"{tf}_MinusDI"]=ndi (~lines 58-62 and 158-159). Keep {tf}_ADX. DI_diff can stay for backward-compat. |
| 2 | merge_data.py | Make sure the new {TF}_PlusDI / {TF}_MinusDI columns are carried through the historical+live merge into data/merged/adx_merged.csv (currently only {TF}_ADX + {TF}_DI_diff exist). |
| 3 | (regenerate data) | Re-run the data update / merge so adx_merged.csv (and the live adx feed) now contain PlusDI/MinusDI per TF. Verify columns present. |
| 4 | hmm_model.py | HMM_FEATURES: use +DI and -DI SEPARATELY instead of (or in addition to) DI_diff — e.g. per TF: {tf}_ADX, {tf}_PlusDI, {tf}_MinusDI. Update the fit() cluster-labeling so 'Volatile' = high ADX with BOTH DI elevated (real churn) vs 'Ranging' = low ADX / both DI low. Optional cross-check against band_width_pct. |
| 5 | train.py / retrain | Retrain the HMM (and re-fit dependent per-state models: model_ranging/trending/volatile). random_state=42 keeps it deterministic. |
| 6 | VALIDATE (mandatory) | backtest_replay + WFO OOS. PROFIT-FIRST rule: the change is only acceptable if TOTAL R does NOT drop vs current. Also confirm new 'Volatile' bars actually have high band_width_pct (real volatility), and slow bars now read Ranging. |

## Alternatives considered

| Option | Note |
|---|---|
| Use +DI / -DI levels (CHOSEN) | Uses data the ADX math already computes; distinguishes quiet vs volatile without ATR. Matches Divyesh's request. |
| 2-SMMA band_width_pct feature | Also ATR-free & lag-free (trend_signal.py:115). Valid alternative / can be added alongside +DI/-DI. |
| Rename Volatile -> Choppy | Cosmetic only; honest label, zero behaviour change, zero risk. Can ship immediately regardless. |
| ATR feature | REJECTED — lagging, already removed 2026-06-19. |

## Files involved (reference)

| File | Role |
|---|---|
| engine/hmm_model.py | MarketStateHMM (GaussianMixture), HMM_FEATURES, STATE_NAMES, state_map labeling |
| engine/mt5_data_updater.py | ADX/+DI/-DI generator (lines 58-62 compute, 158-159 write) — DISCARDS +DI/-DI |
| engine/features.py | load_adx (172), DI_diff=PlusDI-MinusDI (185), _wilder_adx pdi/ndi (885), band via trend_signal |
| engine/trend_signal.py | band_width_pct = (MA(High)-MA(Low))/close*100 (line 115) — lag-free 2-SMMA volatility |
| engine/merge_data.py | merges historical+live ADX -> data/merged/adx_merged.csv |
| data/merged/adx_merged.csv | columns TODAY: {TF}_ADX, {TF}_DI_diff ONLY (no +DI/-DI) |
| engine/config.py | CFG.hmm.n_states=3, random_state=42 |

## Current HMM_FEATURES (for reference)

`M15_ADX, M15_DI_diff, M30_ADX, M30_DI_diff, H1_ADX, H1_DI_diff, H4_ADX, H4_DI_diff`

Proposed: replace each `{TF}_DI_diff` with `{TF}_PlusDI` + `{TF}_MinusDI`.
