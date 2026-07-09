# QGAI Feature Audit - Step 3, Current 36 Features

આ report actual current 36-feature model માટે final classification અને Step 4 માટે feature-set variants છે.  
No code change. No backtest. No new features. No trading rules.

Category key:

- `A` = Pure raw/live-safe input
- `B` = Engineered but live-safe input
- `C` = Threshold-based engineered ML input
- `D` = Possible leakage / needs fix
- `E` = Exclude from first clean ablation
- `F` = Conditional: safe only if train/WFO past-only

## Classification Table

| Feature | Category | Reason | Keep Current Baseline? | Keep Clean Set? | Ablation Group |
|---|---|---|---|---|---|
| `15_min_slot` | A | Pure time input. | Yes | Yes | Raw/basic |
| `slot_win_rate` | F | Uses `win_bin` history; safe only train/WFO past-only. | Yes | Yes, conditional | No-slot |
| `slot_cos` | A | Cyclical time encoding. | Yes | Yes | Raw/basic |
| `day_of_week` | A | Calendar input. | Yes | Yes | Raw/basic |
| `h4_resist_dist` | B | Confirmed H4 OB resistance distance. | Yes | Yes | OB/SR |
| `h4_support_dist` | B | Confirmed H4 OB support distance. | Yes | Yes | OB/SR |
| `h4_ob_strength` | C | Confirmed OB impulse strength, threshold-based. | Yes | Yes | OB/SR |
| `h1_resist_dist` | B | Confirmed H1 OB resistance distance. | Yes | Yes | OB/SR |
| `h1_support_dist` | B | Confirmed H1 OB support distance. | Yes | Yes | OB/SR |
| `h1_ob_strength` | C | Confirmed H1 OB impulse strength, threshold-based. | Yes | Yes | OB/SR |
| `price_pos` | A | Closed M15 range position. | Yes | Yes | Raw/basic |
| `body_pct` | A | Closed M15 body percent. | Yes | Yes | Raw/basic |
| `in_range_phase` | D/E | Possible unfinished H4 leakage. | Yes | No | Leakage-exclude |
| `corr_imp_ratio` | D/E | Future H4 swing candles. | Yes | No | Leakage-exclude |
| `M15_ADX` | A | Raw ADX. | Yes | Yes | Raw/basic |
| `M30_ADX` | A | Raw ADX. | Yes | Yes | Raw/basic |
| `H1_ADX` | A | Raw ADX. | Yes | Yes | Raw/basic |
| `H4_ADX` | A | Raw ADX. | Yes | Yes | Raw/basic |
| `M15_DI_diff` | A | Raw DI difference. | Yes | Yes | Raw/basic |
| `M30_DI_diff` | A | Raw DI difference. | Yes | Yes | Raw/basic |
| `H1_DI_diff` | A | Raw DI difference. | Yes | Yes | Raw/basic |
| `H4_DI_diff` | A | Raw DI difference. | Yes | Yes | Raw/basic |
| `h4_adx_slope` | B | Rolling closed-bar ADX slope. | Yes | Yes | Raw/basic |
| `h1_adx_slope` | B | Rolling closed-bar ADX slope. | Yes | Yes | Raw/basic |
| `range_pct` | A | Closed M15 range percent. | Yes | Yes | Raw/basic |
| `move_1hr` | B | Past 1h closed-bar momentum. | Yes | Yes | Raw/basic |
| `move_4hr` | B | Past 4h closed-bar momentum. | Yes | Yes | Raw/basic |
| `momentum_aligned_1hr` | C | Sign-threshold alignment with 1h momentum. | Yes | Yes | Raw/basic |
| `momentum_aligned_2hr` | C | Sign-threshold alignment with 2h momentum. | Yes | Yes | Raw/basic |
| `momentum_aligned_4hr` | C | Sign-threshold alignment with 4h momentum. | Yes | Yes | Raw/basic |
| `price_vs_ema200` | B | Closed close vs EMA200 percent. | Yes | Yes | Raw/basic |
| `mins_to_next_3star` | B | Scheduled calendar timing. | Yes | Yes | No-news |
| `mins_since_last_3star` | B | Past calendar timing. | Yes | Yes | No-news |
| `ts_bars_since_flip` | B | Last closed M15 trend flip age. | Yes | Yes | Raw/basic |
| `ts_htf_agreement` | B | Closed M15/H1/H4 trend sum. | Yes | Yes | Raw/basic |
| `hmm_state` | B | GMM/HMM regime state, train-only fit required. | Yes | Yes | No-HMM |

## Clean Live-Safe Feature List

Current 36 minus `corr_imp_ratio` and `in_range_phase` = 34 features.

```text
[
  '15_min_slot',
  'slot_win_rate',
  'slot_cos',
  'day_of_week',
  'h4_resist_dist',
  'h4_support_dist',
  'h4_ob_strength',
  'h1_resist_dist',
  'h1_support_dist',
  'h1_ob_strength',
  'price_pos',
  'body_pct',
  'M15_ADX',
  'M30_ADX',
  'H1_ADX',
  'H4_ADX',
  'M15_DI_diff',
  'M30_DI_diff',
  'H1_DI_diff',
  'H4_DI_diff',
  'h4_adx_slope',
  'h1_adx_slope',
  'range_pct',
  'move_1hr',
  'move_4hr',
  'momentum_aligned_1hr',
  'momentum_aligned_2hr',
  'momentum_aligned_4hr',
  'price_vs_ema200',
  'mins_to_next_3star',
  'mins_since_last_3star',
  'ts_bars_since_flip',
  'ts_htf_agreement',
  'hmm_state'
]
```

## Excluded Feature List

```text
[
  'corr_imp_ratio',
  'in_range_phase'
]
```

## Conditional Feature List

```text
[
  'slot_win_rate',
  'hmm_state',
  'mins_to_next_3star',
  'h4_resist_dist',
  'h4_support_dist',
  'h4_ob_strength',
  'h1_resist_dist',
  'h1_support_dist',
  'h1_ob_strength'
]
```

## Ablation Groups For 36-Feature Model

```text
LEAKAGE_EXCLUDE = ['corr_imp_ratio', 'in_range_phase']
NO_SLOT = ['slot_win_rate']
NO_HMM = ['hmm_state']
NO_OB_SR = [
  'h4_resist_dist', 'h4_support_dist', 'h4_ob_strength',
  'h1_resist_dist', 'h1_support_dist', 'h1_ob_strength'
]
NO_NEWS = ['mins_to_next_3star', 'mins_since_last_3star']
```

Old ADX engineered group is not in current 36:

```text
adx_trend_count
h4_trending_h1_aligned
h4_ranging_h1_neutral
h4_h1_regime_score
```

## Exact Feature Sets For Step 4+

### Set 1: Current Baseline, 36 Features

```text
[
  '15_min_slot',
  'slot_win_rate',
  'slot_cos',
  'day_of_week',
  'h4_resist_dist',
  'h4_support_dist',
  'h4_ob_strength',
  'h1_resist_dist',
  'h1_support_dist',
  'h1_ob_strength',
  'price_pos',
  'body_pct',
  'in_range_phase',
  'corr_imp_ratio',
  'M15_ADX',
  'M30_ADX',
  'H1_ADX',
  'H4_ADX',
  'M15_DI_diff',
  'M30_DI_diff',
  'H1_DI_diff',
  'H4_DI_diff',
  'h4_adx_slope',
  'h1_adx_slope',
  'range_pct',
  'move_1hr',
  'move_4hr',
  'momentum_aligned_1hr',
  'momentum_aligned_2hr',
  'momentum_aligned_4hr',
  'price_vs_ema200',
  'mins_to_next_3star',
  'mins_since_last_3star',
  'ts_bars_since_flip',
  'ts_htf_agreement',
  'hmm_state'
]
```

### Set 2: First Clean Live-Safe, 34 Features

Current baseline minus `corr_imp_ratio` and `in_range_phase`.

```text
[
  '15_min_slot',
  'slot_win_rate',
  'slot_cos',
  'day_of_week',
  'h4_resist_dist',
  'h4_support_dist',
  'h4_ob_strength',
  'h1_resist_dist',
  'h1_support_dist',
  'h1_ob_strength',
  'price_pos',
  'body_pct',
  'M15_ADX',
  'M30_ADX',
  'H1_ADX',
  'H4_ADX',
  'M15_DI_diff',
  'M30_DI_diff',
  'H1_DI_diff',
  'H4_DI_diff',
  'h4_adx_slope',
  'h1_adx_slope',
  'range_pct',
  'move_1hr',
  'move_4hr',
  'momentum_aligned_1hr',
  'momentum_aligned_2hr',
  'momentum_aligned_4hr',
  'price_vs_ema200',
  'mins_to_next_3star',
  'mins_since_last_3star',
  'ts_bars_since_flip',
  'ts_htf_agreement',
  'hmm_state'
]
```

### Set 3: Raw/Basic, 25 Features

```text
[
  '15_min_slot',
  'slot_cos',
  'day_of_week',
  'price_pos',
  'body_pct',
  'range_pct',
  'M15_ADX',
  'M30_ADX',
  'H1_ADX',
  'H4_ADX',
  'M15_DI_diff',
  'M30_DI_diff',
  'H1_DI_diff',
  'H4_DI_diff',
  'h4_adx_slope',
  'h1_adx_slope',
  'move_1hr',
  'move_4hr',
  'momentum_aligned_1hr',
  'momentum_aligned_2hr',
  'momentum_aligned_4hr',
  'price_vs_ema200',
  'ts_bars_since_flip',
  'ts_htf_agreement',
  'hmm_state'
]
```

Count note: listed items are 25 including `hmm_state`. It is called raw/basic for audit comparison, not pure raw only.

### Set 4: No `slot_win_rate`, 33 Features

Set 2 minus `slot_win_rate`.

```text
[
  '15_min_slot',
  'slot_cos',
  'day_of_week',
  'h4_resist_dist',
  'h4_support_dist',
  'h4_ob_strength',
  'h1_resist_dist',
  'h1_support_dist',
  'h1_ob_strength',
  'price_pos',
  'body_pct',
  'M15_ADX',
  'M30_ADX',
  'H1_ADX',
  'H4_ADX',
  'M15_DI_diff',
  'M30_DI_diff',
  'H1_DI_diff',
  'H4_DI_diff',
  'h4_adx_slope',
  'h1_adx_slope',
  'range_pct',
  'move_1hr',
  'move_4hr',
  'momentum_aligned_1hr',
  'momentum_aligned_2hr',
  'momentum_aligned_4hr',
  'price_vs_ema200',
  'mins_to_next_3star',
  'mins_since_last_3star',
  'ts_bars_since_flip',
  'ts_htf_agreement',
  'hmm_state'
]
```

### Set 5: No HMM, 33 Features

Set 2 minus `hmm_state`.

```text
[
  '15_min_slot',
  'slot_win_rate',
  'slot_cos',
  'day_of_week',
  'h4_resist_dist',
  'h4_support_dist',
  'h4_ob_strength',
  'h1_resist_dist',
  'h1_support_dist',
  'h1_ob_strength',
  'price_pos',
  'body_pct',
  'M15_ADX',
  'M30_ADX',
  'H1_ADX',
  'H4_ADX',
  'M15_DI_diff',
  'M30_DI_diff',
  'H1_DI_diff',
  'H4_DI_diff',
  'h4_adx_slope',
  'h1_adx_slope',
  'range_pct',
  'move_1hr',
  'move_4hr',
  'momentum_aligned_1hr',
  'momentum_aligned_2hr',
  'momentum_aligned_4hr',
  'price_vs_ema200',
  'mins_to_next_3star',
  'mins_since_last_3star',
  'ts_bars_since_flip',
  'ts_htf_agreement'
]
```

### Set 6: No ADX-Engineered

Same as Set 2 for current 36, because old ADX engineered features are already not in current model.

```text
Same as Set 2
```

### Set 7: No OB/SR, 28 Features

Set 2 minus OB/SR group.

```text
[
  '15_min_slot',
  'slot_win_rate',
  'slot_cos',
  'day_of_week',
  'price_pos',
  'body_pct',
  'M15_ADX',
  'M30_ADX',
  'H1_ADX',
  'H4_ADX',
  'M15_DI_diff',
  'M30_DI_diff',
  'H1_DI_diff',
  'H4_DI_diff',
  'h4_adx_slope',
  'h1_adx_slope',
  'range_pct',
  'move_1hr',
  'move_4hr',
  'momentum_aligned_1hr',
  'momentum_aligned_2hr',
  'momentum_aligned_4hr',
  'price_vs_ema200',
  'mins_to_next_3star',
  'mins_since_last_3star',
  'ts_bars_since_flip',
  'ts_htf_agreement',
  'hmm_state'
]
```

### Set 8: No News Timing, 32 Features

Set 2 minus news timing.

```text
[
  '15_min_slot',
  'slot_win_rate',
  'slot_cos',
  'day_of_week',
  'h4_resist_dist',
  'h4_support_dist',
  'h4_ob_strength',
  'h1_resist_dist',
  'h1_support_dist',
  'h1_ob_strength',
  'price_pos',
  'body_pct',
  'M15_ADX',
  'M30_ADX',
  'H1_ADX',
  'H4_ADX',
  'M15_DI_diff',
  'M30_DI_diff',
  'H1_DI_diff',
  'H4_DI_diff',
  'h4_adx_slope',
  'h1_adx_slope',
  'range_pct',
  'move_1hr',
  'move_4hr',
  'momentum_aligned_1hr',
  'momentum_aligned_2hr',
  'momentum_aligned_4hr',
  'price_vs_ema200',
  'ts_bars_since_flip',
  'ts_htf_agreement',
  'hmm_state'
]
```

## Step 4 Recommendation

Backtest first:

```text
Set 2: First Clean Live-Safe, 34 features
```

Reason: it removes the two active leakage-risk features while keeping the rest of the actual current model surface.

Step 3 status: current 36 classification and feature-set variants prepared only.
