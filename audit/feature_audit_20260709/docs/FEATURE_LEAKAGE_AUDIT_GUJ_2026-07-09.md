# QGAI Feature Leakage Audit, 2026-07-09

આ audit માત્ર isolated copyમાં છે:

`C:\QGAI\audit\feature_audit_20260709\workspace`

Live trading folder `C:\QGAI\engine` માટે કોઈ feature logic change આ auditમાં કરેલ નથી.

## 1. Current Model Reality Check

User requestમાં 42 featuresની list હતી, પણ હાલનું saved live model `data\models\final\model_meta.json` મુજબ 36 features વાપરે છે:

- Base `FEATURE_COLS`: 35
- Extra appended model input: `hmm_state`
- Model AUC: `0.7047`
- Timestamp: `20260708_1515`

Requested 42માંથી આ features હાલ current live modelમાં નથી:

- `trade_direction`
- `h4_in_ob_zone`
- `adx_trend_count`
- `h4_trending_h1_aligned`
- `h4_ranging_h1_neutral`
- `h4_h1_regime_score`

આ બધું `engine\features.py`ની `_MANUAL_PRUNE` / `_ZERO_IMP` pruning બાદ remove થયેલું છે.

## 2. Classification Key

1. Pure raw/live-safe input
2. Engineered but live-safe input
3. Hard-rule / threshold-based feature
4. Possible future leakage or target leakage feature
5. Must remove or test separately

## 3. All 42 Feature Classification

| # | Feature | In current 36? | Class | Audit decision |
|---:|---|---|---|---|
| 1 | `15_min_slot` | Yes | 1 | Keep. Pure time input. |
| 2 | `slot_win_rate` | Yes | 2 | Keep only if train/WFO past-only. Current code builds train-split only. Test separately. |
| 3 | `slot_cos` | Yes | 1 | Keep. Pure cyclical time. |
| 4 | `day_of_week` | Yes | 1 | Keep. Pure calendar input. |
| 5 | `trade_direction` | No | 2 | Already removed. Keep removed unless ablation proves stable. |
| 6 | `h4_resist_dist` | Yes | 2 | Keep/test. Based on confirmed OB levels. |
| 7 | `h4_support_dist` | Yes | 2 | Keep/test. Based on confirmed OB levels. |
| 8 | `h4_in_ob_zone` | No | 3 | Already removed. Threshold/zone flag. |
| 9 | `h4_ob_strength` | Yes | 3 | Test separately. Uses strong impulse threshold but confirmed before use. |
| 10 | `h1_resist_dist` | Yes | 2 | Keep/test. Based on confirmed OB levels. |
| 11 | `h1_support_dist` | Yes | 2 | Keep/test. Based on confirmed OB levels. |
| 12 | `h1_ob_strength` | Yes | 3 | Test separately. Uses strong impulse threshold but confirmed before use. |
| 13 | `price_pos` | Yes | 1 | Keep. Closed candle range position. |
| 14 | `body_pct` | Yes | 1 | Keep. Closed candle body percent. |
| 15 | `in_range_phase` | Yes | 4/5 | High risk. Current H4 aggregation can expose unfinished H4 candle. Remove or rebuild last-closed-only, then test. |
| 16 | `corr_imp_ratio` | Yes | 4/5 | High risk. Swing detection uses future H4 candles. Remove or rebuild online-only, then test. |
| 17 | `M15_ADX` | Yes | 1 | Keep as ML input only. No manual ADX rule. |
| 18 | `M30_ADX` | Yes | 1 | Keep as ML input only. |
| 19 | `H1_ADX` | Yes | 1 | Keep as ML input only. |
| 20 | `H4_ADX` | Yes | 1 | Keep as ML input only. |
| 21 | `M15_DI_diff` | Yes | 1 | Keep. Raw directional indicator input. |
| 22 | `M30_DI_diff` | Yes | 1 | Keep. |
| 23 | `H1_DI_diff` | Yes | 1 | Keep. |
| 24 | `H4_DI_diff` | Yes | 1 | Keep. |
| 25 | `adx_trend_count` | No | 3 | Already removed. Count of ADX > 20. Keep removed. |
| 26 | `h4_adx_slope` | Yes | 2 | Keep/test. Rolling ADX slope, no direct target. |
| 27 | `h1_adx_slope` | Yes | 2 | Keep/test. |
| 28 | `h4_trending_h1_aligned` | No | 3 | Already removed. Uses H4 ADX > 30 and H1 DI threshold. |
| 29 | `h4_ranging_h1_neutral` | No | 3 | Already removed. Uses H4 ADX < 20 and H1 DI threshold. |
| 30 | `h4_h1_regime_score` | No | 3 | Already removed. Hard-coded threshold score. |
| 31 | `range_pct` | Yes | 1 | Keep. Closed candle range percent. |
| 32 | `move_1hr` | Yes | 2 | Keep. Past closed bars with gap guard. |
| 33 | `move_4hr` | Yes | 2 | Keep. Past closed bars with gap guard. |
| 34 | `momentum_aligned_1hr` | Yes | 2 | Test. Engineered from trade direction plus past momentum. Current importance 0. |
| 35 | `momentum_aligned_2hr` | Yes | 2 | Test/remove candidate. Current importance 0. |
| 36 | `momentum_aligned_4hr` | Yes | 2 | Test/remove candidate. Current importance 0. |
| 37 | `price_vs_ema200` | Yes | 2 | Keep/test. Past EMA context. |
| 38 | `mins_to_next_3star` | Yes | 2 | Keep only if calendar is known before trade time. Test separately. |
| 39 | `mins_since_last_3star` | Yes | 2 | Remove/test candidate. Current importance 0. |
| 40 | `ts_bars_since_flip` | Yes | 2 | Remove/test candidate. Current importance 0. |
| 41 | `ts_htf_agreement` | Yes | 2 | Keep/test. Uses last-closed TF trend signal table. |
| 42 | `hmm_state` | Yes | 2 | Keep/test. Current HMM fit is train-only, not target-based. |

## 4. Detailed Audit Of 12 Suspicious Features

| Feature | Calculation | Fixed threshold? | Future/full-data/target leakage? | Live availability | Decision |
|---|---|---:|---|---|---|
| `slot_win_rate` | `build_slot_table()` groups training trades by hour and mean `win_bin`; inference reads hour prior. | No trading threshold in model input, but outcome-derived prior. | Current `train.py` builds on first 70 percent train slice only. Old comments say full-set leak was fixed. WFO cutoff also filters training data before week. | Yes, if table is trained from past only. | Keep but ablate C. Never build from full dataset for OOS. |
| `hmm_state` | GaussianMixture HMM-like state model fitted on ADX/band features, then state appended to XGB. | No manual entry threshold. | Current `train.py` fits HMM only on training ADX rows up to train cutoff. No win/loss target used. | Yes after model is trained. | Keep but ablate D. Audit copy now supports true `QGAI_ABLATE=hmm_state`. |
| `h4_trending_h1_aligned` | `H4_ADX > 30` plus H1 DI direction confirms signal. | Yes. | No target leakage, but hard-coded ADX/DI rule-like feature. | Yes from ADX row. | Already removed. Keep removed. |
| `h4_ranging_h1_neutral` | `H4_ADX < 20` and `abs(H1_DI_diff) < 10`. | Yes. | No target leakage, but threshold rule. | Yes from ADX row. | Already removed. Keep removed. |
| `h4_h1_regime_score` | Score from ADX > 30, > 25, < 20, DI abs < 10/>15. | Yes. | No target leakage, but hard-coded regime score. | Yes from ADX row. | Already removed. Keep removed. |
| `adx_trend_count` | Count of TFs where ADX > 20. | Yes. | No target leakage, but threshold count. | Yes from ADX row. | Already removed. Keep removed. |
| `in_range_phase` | H4 grouped candle move: `abs(h4 close-open) < 0.5`. | Yes. | Possible future leak: H4 table is built from complete H4 OHLC, and lookup can include the active H4 group before close. | Not safely available inside current H4 candle. | Must remove or rebuild last-closed-only, then test I. |
| `h4_in_ob_zone` | Price inside recent H4 OB zone. | Yes zone flag. | Current OB uses `confirm_datetime < t`, so confirmation is after impulse close. This part is live-safe. | Yes after confirmation. | Already removed, okay to keep removed. |
| `h4_ob_strength` | Strength equals next impulse candle range pct after OB candle. Available only at confirm time. | Yes `is_strong = range > MA10*1.5`. | Uses next candle to confirm OB, but `confirm_datetime < t` prevents early use. No target outcome. | Yes after impulse close only. | Test separately F. |
| `h1_ob_strength` | Same as H4 but H1 timeframe. | Yes. | Same as above. | Yes after impulse close only. | Test separately F. |
| `corr_imp_ratio` | H4 swing highs/lows with `n=3` centered future bars, then ratio forward filled. | No direct entry threshold in current feature, but swing confirmation uses future bars. | High risk future leakage because swing high/low at bar i requires bars i+1 to i+3. | Not safely available at live time as currently built. | Must remove or rebuild online-only, then test J. |
| `mins_to_next_3star` | Minutes until next 3-star calendar event. | Cap at 240, but no trade threshold in model input. | Acceptable only if calendar data is known before trade time. If file includes future revised events unavailable then data governance risk. Does not use market reaction. | Yes if using known calendar feed. | Keep/test H. |

## 5. Leakage Findings

High-confidence issues:

- `in_range_phase`: possible unfinished H4 candle leakage. It is current model importance rank #1 (`0.073539`), so this is the biggest audit risk.
- `corr_imp_ratio`: centered swing logic uses future H4 bars. Current model importance rank #28 (`0.022626`).

Currently fixed or acceptable:

- `slot_win_rate`: old full-dataset risk is already fixed in normal training by train-split build.
- `hmm_state`: fitted on training ADX only, no target outcome.
- OB features: confirmation timestamp filter prevents using OB before the impulse close.
- News timing: no target/result leakage if calendar was available before trade.

## 6. Hard-Rule / Threshold Findings

These were hard-threshold engineered features and are already removed from current model:

- `adx_trend_count`
- `h4_trending_h1_aligned`
- `h4_ranging_h1_neutral`
- `h4_h1_regime_score`
- `h4_in_ob_zone`

Still in current model but threshold-engineered and should be tested:

- `h4_ob_strength`
- `h1_ob_strength`
- `in_range_phase` (also leakage risk)

## 7. Recommended Keep / Remove / Test

Keep now:

- Pure time: `15_min_slot`, `slot_cos`, `day_of_week`
- Raw OHLC/indicator: `price_pos`, `body_pct`, `range_pct`, raw ADX and DI diffs
- Past momentum/EMA: `move_1hr`, `move_4hr`, `price_vs_ema200`
- `hmm_state`, but only because train-only fit is verified
- `slot_win_rate`, but only with past-only training/WFO

Remove or rebuild before trusting:

- `in_range_phase`
- `corr_imp_ratio`

Test separately:

- `slot_win_rate`
- `hmm_state`
- OB strength/features
- Support/resistance distance features
- News timing features
- Zero-importance current features: `ts_bars_since_flip`, `mins_since_last_3star`, `momentum_aligned_1hr`, `momentum_aligned_2hr`, `momentum_aligned_4hr`

## 8. Existing Backtest Evidence Found

These are existing result folders, not newly completed A-H ablations:

| Result folder | Total R | Trades | Positive weeks | Negative weeks | Avg R/week | Note |
|---|---:|---:|---:|---:|---:|---|
| `wfo_part1_prune35` | +444.7R | 768 | 51 | 1 | +8.39R | Current 35-base prune family. |
| `wfo_live_match_015` | +483.1R | 651 | 51 | 0 | +9.12R | Live-match 0.15 buffer WFO result. |
| `wfo_hmm_spec` | +470.4R | 670 | 52 | 0 | +8.88R | HMM spec variant. |
| `wfo_part2_composite` | +405.6R | 731 | 52 | 0 | +7.65R | ADX composite variant underperformed current prune baseline. |

## 9. Audit Ablation Runners Created

Smoke test:

`C:\QGAI\audit\feature_audit_20260709\Run_Audit_Ablations_TEST.bat`

Full WFO:

`C:\QGAI\audit\feature_audit_20260709\Run_Audit_Ablations_FULL.bat`

Both runners operate only inside:

`C:\QGAI\audit\feature_audit_20260709\workspace`

Variants:

- A current
- B basic safe, removes suspicious set
- C remove `slot_win_rate`
- D remove `hmm_state`
- E remove ADX engineered threshold features
- F remove OB strength/zone
- G remove support/resistance distances
- H remove news timing
- I remove `in_range_phase`
- J remove `corr_imp_ratio`

Note: audit copy of `train.py` was patched so `QGAI_ABLATE=hmm_state` truly removes `hmm_state` from training matrices. Live `engine\train.py` was not changed.

Lightweight verification passed:

- `py_compile` passed for audit-copy `features.py`, `train.py`, `inference.py`, `hmm_model.py`, and `backtest_replay.py`.
- All A-J ablation variants imported successfully from the audit workspace.
- `E_no_adx_engineered` does not change base feature count because those ADX threshold features are already pruned from the current model.

## 10. Final Recommended Feature Set Before Full Ablation

Conservative candidate for next WFO test:

- Current 36 features minus `in_range_phase`
- Current 36 features minus `corr_imp_ratio`
- Then combined test minus both `in_range_phase,corr_imp_ratio`

Do not deploy this directly. Gate it by full WFO and month/regime stability first.
