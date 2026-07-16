# FEATURES MASTER LIST - QGAI v2

**Last updated:** 2026-07-12  
**Current code model inputs:** 27 base `FEATURE_COLS`  
**Regime label:** `hmm_state` is appended/used by trained models and regime feature maps.  
**Status:** OB/SR model inputs removed by user decision after 3-month retrain A/B.

## Previous Snapshot - Before OB/SR Full Prune

Keep this for history. Before the 2026-07-12 full OB/SR prune, the documented active master list was 33 features:

```text
H4_ADX
move_1hr
h4_adx_slope
h4_support_dist
price_pos
slot_win_rate
day_of_week
ts_htf_agreement
price_vs_ema200
M30_DI_diff
h1_resist_dist
body_pct
H4_DI_diff
h1_adx_slope
M15_DI_diff
h4_h1_regime_score
move_4hr
range_pct
M15_ADX
momentum_aligned_1hr
h1_support_dist
h1_ob_strength
H1_DI_diff
mins_since_last_3star
momentum_aligned_2hr
mins_to_next_3star
h4_ob_strength
momentum_aligned_4hr
h4_resist_dist
ts_bars_since_flip
15_min_slot
slot_cos
hmm_state
```

The old snapshot kept OB/SR as active. The current code list below shows the latest prune state.

## Active Base Features (27)

| # | Feature Name | Alias | Indicator |
|---|---|---|---|
| 1 | `15_min_slot` | time_15min_slot | Clock |
| 2 | `slot_win_rate` | time_1hr_winrate | Historical WR |
| 3 | `slot_cos` | time_cyclical_encoding | Clock |
| 4 | `day_of_week` | time_weekday | Calendar |
| 5 | `price_pos` | bb_price_position | Bollinger Band |
| 6 | `body_pct` | candle_body_ratio | Candlestick |
| 7 | `in_range_phase` | h4move_is_ranging | H4 Price Move % |
| 8 | `M15_ADX` | adx_m15_strength | ADX |
| 9 | `H4_ADX` | adx_h4_strength | ADX |
| 10 | `M15_DI_diff` | di_m15_direction | DI+ / DI- |
| 11 | `M30_DI_diff` | di_m30_direction | DI+ / DI- |
| 12 | `H1_DI_diff` | di_h1_direction | DI+ / DI- |
| 13 | `H4_DI_diff` | di_h4_direction | DI+ / DI- |
| 14 | `h4_adx_slope` | adx_h4_momentum | ADX Slope |
| 15 | `h1_adx_slope` | adx_h1_momentum | ADX Slope |
| 16 | `h4_h1_regime_score` | adx_regime_quality_score | ADX + DI Combo |
| 17 | `range_pct` | candle_range_pct | Candlestick |
| 18 | `move_1hr` | price_change_1hr_usd | Raw Price Move |
| 19 | `move_4hr` | price_change_4hr_usd | Raw Price Move |
| 20 | `momentum_aligned_1hr` | price_1hr_signal_agree | Price Move + Signal |
| 21 | `momentum_aligned_2hr` | price_2hr_signal_agree | Price Move + Signal |
| 22 | `momentum_aligned_4hr` | price_4hr_signal_agree | Price Move + Signal |
| 23 | `price_vs_ema200` | ema200_distance_usd | EMA200 |
| 24 | `mins_to_next_3star` | news_mins_until_next | Economic Calendar |
| 25 | `mins_since_last_3star` | news_mins_since_last | Economic Calendar |
| 26 | `ts_bars_since_flip` | smma_bars_since_flip | 20-SMA Hybrid |
| 27 | `ts_htf_agreement` | smma_htf_agreement | 20-SMA Hybrid |

## Regime Feature Lists

These are the current state-specific lists after pruning. `hmm_state` is included inside the regime lists.

### Ranging (22)

```text
slot_win_rate
day_of_week
mins_to_next_3star
mins_since_last_3star
price_pos
body_pct
range_pct
M30_DI_diff
H1_DI_diff
hmm_state
h4_h1_regime_score
move_4hr
momentum_aligned_4hr
momentum_aligned_2hr
price_vs_ema200
ts_bars_since_flip
ts_htf_agreement
h4_adx_slope
h1_adx_slope
in_range_phase
move_1hr
momentum_aligned_1hr
```

### Trending (23)

```text
slot_win_rate
day_of_week
mins_to_next_3star
mins_since_last_3star
price_pos
body_pct
range_pct
M15_ADX
M30_DI_diff
H1_DI_diff
hmm_state
h4_h1_regime_score
move_4hr
momentum_aligned_4hr
momentum_aligned_2hr
price_vs_ema200
ts_bars_since_flip
ts_htf_agreement
h4_adx_slope
h1_adx_slope
H4_ADX
M15_DI_diff
H4_DI_diff
```

### Volatile (17)

```text
slot_win_rate
day_of_week
mins_to_next_3star
mins_since_last_3star
price_pos
body_pct
range_pct
hmm_state
h4_h1_regime_score
move_4hr
momentum_aligned_4hr
momentum_aligned_2hr
price_vs_ema200
ts_bars_since_flip
ts_htf_agreement
h4_adx_slope
h1_adx_slope
```

## Pruned Features

| Feature | Group | Why Pruned | Date |
|---|---|---|---|
| `corr_imp_ratio` | Leakage | Confirmed future H4 swing leak; low impact after audit. | 2026-07-12 |
| `volume` | Volume | Volume lever failed; noise/slippage risk. | 2026-06-23 |
| `tick_volume` | Volume | Raw tick-volume AUC small, WFO weak; keep out. | 2026-07-10 |
| `ts_line_dist_pct` | SMMA distance | User removed line-distance as a feature. | 2026-06-29 |
| `ema200_dist_abs` | EMA200 | User kept only `price_vs_ema200`. | 2026-06-30 |
| `above_ema200` | EMA200 | User kept only `price_vs_ema200`. | 2026-06-30 |
| `near_ema200` | EMA200 | User kept only `price_vs_ema200`. | 2026-06-30 |
| `adx_trend_count` | ADX engineered | Zero/redundant with raw ADX. | 2026-07-07 |
| `h4_trending_h1_aligned` | ADX engineered | Redundant with `h4_h1_regime_score`. | 2026-07-12 |
| `h4_ranging_h1_neutral` | ADX engineered | Redundant with `h4_h1_regime_score`. | 2026-07-12 |
| `trade_direction` | Signal | Interfered with `h4_h1_regime_score` combo. | 2026-07-12 |
| `h4_in_ob_zone` | OB/SR | Redundant with H4 OB distance features; now OB group removed. | 2026-07-12 |
| `h4_ranging_h1_extended` | ADX engineered | Covered by `h4_h1_regime_score = -1`. | 2026-07-12 |
| `M30_ADX` | ADX | Middle timeframe redundant in latest test. | 2026-07-12 |
| `H1_ADX` | ADX | H1 slope + DI sufficient in latest test. | 2026-07-12 |
| `h1_support_dist` | OB/SR | D6 combo prune: +34.7R vs baseline +31.8R in 3-month retrain test. | 2026-07-12 |
| `h1_ob_strength` | OB/SR | D6 combo prune: +34.7R vs baseline +31.8R in 3-month retrain test. | 2026-07-12 |
| `h4_resist_dist` | OB/SR | D5 combo prune: +34.5R vs baseline +31.8R in 3-month retrain test. | 2026-07-12 |
| `h4_ob_strength` | OB/SR | D5 combo prune: +34.5R vs baseline +31.8R in 3-month retrain test. | 2026-07-12 |
| `h4_support_dist` | OB/SR | User decision: remove remaining OB/SR inputs before no-OB retrain test. | 2026-07-12 |
| `h1_resist_dist` | OB/SR | User decision: remove remaining OB/SR inputs before no-OB retrain test. | 2026-07-12 |

## Indicator Groups Summary

| Indicator | Active Count | Active Features |
|---|---:|---|
| Time/Clock | 4 | `15_min_slot`, `slot_win_rate`, `slot_cos`, `day_of_week` |
| Candlestick / Range | 4 | `price_pos`, `body_pct`, `range_pct`, `in_range_phase` |
| ADX + DI | 8 | `M15_ADX`, `H4_ADX`, `M15_DI_diff`, `M30_DI_diff`, `H1_DI_diff`, `H4_DI_diff`, `h4_adx_slope`, `h1_adx_slope` |
| ADX + DI Combo | 1 | `h4_h1_regime_score` |
| Raw Price Move | 2 | `move_1hr`, `move_4hr` |
| Price Move + Signal | 3 | `momentum_aligned_1hr`, `momentum_aligned_2hr`, `momentum_aligned_4hr` |
| EMA200 | 1 | `price_vs_ema200` |
| Economic Calendar | 2 | `mins_to_next_3star`, `mins_since_last_3star` |
| 20-SMA Hybrid | 2 | `ts_bars_since_flip`, `ts_htf_agreement` |
| Order Block / S-R | 0 | none |
| HMM Regime | appended | `hmm_state` |
| **TOTAL BASE FEATURES** | **27** | |

## Latest OB/SR Test Note

`Run_OB_Redundancy_AB_TEST.bat` was fixed to retrain each variant before replay. The valid 3-month retrain test showed:

| Test | Removed | Total R | Diff vs baseline |
|---|---|---:|---:|
| Baseline | none | +31.8R | 0 |
| D5 | `h4_resist_dist`, `h4_ob_strength` | +34.5R | +2.7R |
| D6 | `h1_support_dist`, `h1_ob_strength` | +34.7R | +2.9R |

User then requested full OB/SR removal. A dedicated test runner was created:

```text
backtest/_runners/Run_OB_AllRemoved_Retrain_TEST.bat
```

Final live adoption still requires retrain and validation.
