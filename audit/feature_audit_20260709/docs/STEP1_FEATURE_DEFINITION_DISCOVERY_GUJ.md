# QGAI Feature Audit - Step 1, Current 36 Features

આ report actual saved current model પર આધારિત છે: 35 base `FEATURE_COLS` + appended `hmm_state` = 36 features.

No code change. No feature removal. No backtest. Step 1 only: feature definition discovery.

Current 36 features:

```text
[
  '15_min_slot', 'slot_win_rate', 'slot_cos', 'day_of_week',
  'h4_resist_dist', 'h4_support_dist', 'h4_ob_strength',
  'h1_resist_dist', 'h1_support_dist', 'h1_ob_strength',
  'price_pos', 'body_pct', 'in_range_phase', 'corr_imp_ratio',
  'M15_ADX', 'M30_ADX', 'H1_ADX', 'H4_ADX',
  'M15_DI_diff', 'M30_DI_diff', 'H1_DI_diff', 'H4_DI_diff',
  'h4_adx_slope', 'h1_adx_slope',
  'range_pct', 'move_1hr', 'move_4hr',
  'momentum_aligned_1hr', 'momentum_aligned_2hr', 'momentum_aligned_4hr',
  'price_vs_ema200',
  'mins_to_next_3star', 'mins_since_last_3star',
  'ts_bars_since_flip', 'ts_htf_agreement',
  'hmm_state'
]
```

These old 42-list features are not in current 36:

```text
trade_direction, h4_in_ob_zone, adx_trend_count,
h4_trending_h1_aligned, h4_ranging_h1_neutral, h4_h1_regime_score
```

## Feature Definition Table

| Feature | File/Function | Calculation | Source Data | Timeframe | Closed Candle Only? | Uses Threshold? | Future Data Risk? | Live Safe? | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `15_min_slot` | `engine/features.py` `compute_features` | `hour*4 + minute//15` | signal time `t` | M15 | N/A | No | No | Yes | Time index only. |
| `slot_win_rate` | `build_slot_table`, `compute_features` | Hourly `win_bin.mean()`, lookup by `t.hour` | historical trades | 1-hour slot | N/A | No | Possible if built from future trades | Yes if train/WFO past-only | Outcome-derived prior. |
| `slot_cos` | `compute_features` | `cos(2*pi*slot/96)` | signal time | M15/day cycle | N/A | No | No | Yes | Cyclical time. |
| `day_of_week` | `compute_features` | `pd.Timestamp(t).dayofweek` | signal time | Daily | N/A | No | No | Yes | Calendar input. |
| `h4_resist_dist` | `get_ob_features` | Distance % from price to nearest profit-side confirmed H4 OB midpoint | OHLC OB table | H4 | After OB confirmation | Direction side filter | Low if confirmed | Yes after confirm | Direction-aware S/R. |
| `h4_support_dist` | `get_ob_features` | Distance % from price to nearest loss-side confirmed H4 OB midpoint | OHLC OB table | H4 | After OB confirmation | Direction side filter | Low if confirmed | Yes after confirm | Direction-aware S/R. |
| `h4_ob_strength` | `build_ob_table`, `get_ob_features` | Nearest H4 resistance OB `ob_strength = next impulse range_pct` | OHLC | H4 | Available after next H4 confirms | Yes, strong impulse | Medium | Yes after confirm | Requires `confirm_datetime < t`. |
| `h1_resist_dist` | `get_ob_features` | Distance % to nearest profit-side confirmed H1 OB midpoint | OHLC OB table | H1 | After OB confirmation | Direction side filter | Low if confirmed | Yes after confirm | Direction-aware S/R. |
| `h1_support_dist` | `get_ob_features` | Distance % to nearest loss-side confirmed H1 OB midpoint | OHLC OB table | H1 | After OB confirmation | Direction side filter | Low if confirmed | Yes after confirm | Direction-aware S/R. |
| `h1_ob_strength` | `build_ob_table`, `get_ob_features` | Nearest H1 resistance OB strength from next impulse range | OHLC | H1 | Available after next H1 confirms | Yes | Medium | Yes after confirm | Requires `confirm_datetime < t`. |
| `price_pos` | `engineer_ohlc`, `compute_features` | `(close-low_20)/(high_20-low_20)` | OHLC | M15 rolling 20 | Yes if closed row | No | No | Yes | Position in recent range. |
| `body_pct` | `engineer_ohlc`, `compute_features` | `abs(close-open)/close*100` | OHLC | M15 | Yes | No | No | Yes | Candle body percent. |
| `in_range_phase` | `build_h4_range_table`, `get_range_features` | `1` if `abs(H4 close-open %) < 0.5` | OHLC grouped H4 | H4 | Risk: current H4 can be included | Yes, `0.5%` | Yes possible | Questionable | May include unfinished H4 final close. |
| `corr_imp_ratio` | `build_trend_ratio_table`, `get_trend_ratio_features` | Centered H4 swing leg candle ratio, forward-filled | OHLC grouped H4 | H4 | No | Swing rules | Yes | No | Uses future H4 candles `i+1..i+3`. |
| `M15_ADX` | `load_adx`, `compute_features` | Latest `M15_ADX` row `<= t` | ADX CSV | M15 | Depends on as-of CSV | No | CSV-dependent | Yes if as-of | Raw ADX input. |
| `M30_ADX` | `load_adx`, `compute_features` | Latest `M30_ADX` row `<= t` | ADX CSV | M30 | Depends on as-of CSV | No | CSV-dependent | Yes if as-of | Raw ADX input. |
| `H1_ADX` | `load_adx`, `compute_features` | Latest `H1_ADX` row `<= t` | ADX CSV | H1 | Depends on as-of CSV | No | CSV-dependent | Yes if as-of | Raw ADX input. |
| `H4_ADX` | `load_adx`, `compute_features` | Latest `H4_ADX` row `<= t` | ADX CSV | H4 | Depends on as-of CSV | No | CSV-dependent | Yes if as-of | Raw ADX input. |
| `M15_DI_diff` | `load_adx` | `M15_PlusDI - M15_MinusDI` | ADX CSV | M15 | Depends on as-of CSV | No | CSV-dependent | Yes if as-of | Directional input. |
| `M30_DI_diff` | `load_adx` | `M30_PlusDI - M30_MinusDI` | ADX CSV | M30 | Depends on as-of CSV | No | CSV-dependent | Yes if as-of | Directional input. |
| `H1_DI_diff` | `load_adx` | `H1_PlusDI - H1_MinusDI` | ADX CSV | H1 | Depends on as-of CSV | No | CSV-dependent | Yes if as-of | Directional input. |
| `H4_DI_diff` | `load_adx` | `H4_PlusDI - H4_MinusDI` | ADX CSV | H4 | Depends on as-of CSV | No | CSV-dependent | Yes if as-of | Directional input. |
| `h4_adx_slope` | `get_rolling_adx`, `compute_features` | Rolling H4 ADX now minus previous 16 M15 bars | OHLC | Rolling H4 | Yes, cutoff `t-15m` | No | No | Yes | Closed M15 phase-grid ADX. |
| `h1_adx_slope` | `get_rolling_adx`, `compute_features` | Rolling H1 ADX now minus previous 16 M15 bars | OHLC | Rolling H1 | Yes, cutoff `t-15m` | No | No | Yes | Closed M15 phase-grid ADX. |
| `range_pct` | `engineer_ohlc`, `compute_features` | `(high-low)/close*100` | OHLC | M15 | Yes | No | No | Yes | Candle range. |
| `move_1hr` | `compute_features` | `(close_now-close_4bars_ago)/close_4bars_ago*100`, gap guarded | OHLC | 1h lookback | Yes | Gap guard | No | Yes | Past momentum. |
| `move_4hr` | `compute_features` | `(close_now-close_16bars_ago)/close_16bars_ago*100`, gap guarded | OHLC | 4h lookback | Yes | Gap guard | No | Yes | Past momentum. |
| `momentum_aligned_1hr` | `compute_features` | `+1` if signal direction agrees with `move_1hr`, `-1` if against, else `0` | OHLC + signal type | 1h | Yes | Sign threshold | No | Yes | Directional engineered input. |
| `momentum_aligned_2hr` | `compute_features` | Same using internal `move_2hr` | OHLC + signal type | 2h | Yes | Sign threshold | No | Yes | `move_2hr` is computed but not in current 36. |
| `momentum_aligned_4hr` | `compute_features` | Same using `move_4hr` | OHLC + signal type | 4h | Yes | Sign threshold | No | Yes | Directional engineered input. |
| `price_vs_ema200` | `engineer_ohlc`, `compute_features` | `(close-EMA200)/close*100`, EMA span 200 | OHLC | M15 EMA200 | Yes | No | No | Yes | EMA context. |
| `mins_to_next_3star` | `load_news`, `compute_features` | Minutes to next impact-3 event, capped 240 | news calendar | Event time | N/A | Cap 240 | Calendar-dependent | Yes if known schedule | Future scheduled event time only. |
| `mins_since_last_3star` | `compute_features` | Minutes since previous impact-3 event, capped 240 | news calendar | Event time | N/A | Cap 240 | No | Yes | Past event timing. |
| `ts_bars_since_flip` | `get_trend_signal_features` | M15 `bars_since_flip` from trend table | OHLC trend table | M15 | Yes, cutoff `t-15m` | No | No | Yes | Last closed M15 trend state. |
| `ts_htf_agreement` | `get_trend_signal_features` | `ts_trend_m15 + ts_trend_h1 + ts_trend_h4` | OHLC trend table | M15/H1/H4 | Yes, per TF cutoff | No | No | Yes | Multi-TF trend sum. |
| `hmm_state` | `train.py`, `inference.py`, `hmm_model.py` | GMM/HMM regime state appended to model features | ADX/band features | M15/M30/H1/H4 | Depends on as-of inputs | No trading threshold | Low if train-only fit | Yes | Unsupervised state. |

Step 1 status: current 36 feature definitions traced only.
