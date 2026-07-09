# QGAI Feature Audit - Step 2, Current 36 Features

આ report actual current 36-feature model પર આધારિત suspicious feature deep audit છે.  
No code change. No feature removal. No backtest. No trading-rule change.

## Step 2 Summary Table

| Feature | Leakage Risk | Threshold Rule? | Live Safe? | Risk Level | Recommendation | Reason |
|---|---|---|---|---|---|---|
| `slot_win_rate` | Target/future leakage if built from full trade dataset | No | Yes if train/WFO past-only | Medium | Ablation-test | Uses `win_bin` outcome history; current main train uses first 70% train slice. |
| `hmm_state` | Low if HMM/GMM fit only on train data | No | Yes | Low | Keep + ablation-test | Current train fits HMM on ADX rows up to train cutoff; no win/loss target. |
| `in_range_phase` | Possible future H4 candle leakage | Yes: `abs(H4 move) < 0.5` | Questionable | High | Fix calculation or exclude | Current H4 table can include active H4 final close. |
| `corr_imp_ratio` | Future H4 candle leakage | Swing rules | No | Critical | Remove or fix | Centered swing detection uses future H4 candles `i+1..i+3`. |
| `h4_ob_strength` | Low/Medium if `confirm_datetime < t` holds | Yes: `range > MA10*1.5` | Yes after confirmation | Medium | Ablation-test | Uses next impulse for OB strength, but only after confirmation. |
| `h1_ob_strength` | Low/Medium if `confirm_datetime < t` holds | Yes | Yes after confirmation | Medium | Ablation-test | Same as H4 OB strength on H1. |
| `h4_resist_dist` | Low if confirmed-only | Direction side filter | Yes after confirmation | Low/Medium | Ablation-test | Nearest confirmed H4 profit-side OB distance. |
| `h4_support_dist` | Low if confirmed-only | Direction side filter | Yes after confirmation | Low/Medium | Ablation-test | Nearest confirmed H4 loss-side OB distance. |
| `h1_resist_dist` | Low if confirmed-only | Direction side filter | Yes after confirmation | Low/Medium | Ablation-test | Nearest confirmed H1 profit-side OB distance. |
| `h1_support_dist` | Low if confirmed-only | Direction side filter | Yes after confirmation | Low/Medium | Ablation-test | Nearest confirmed H1 loss-side OB distance. |
| `mins_to_next_3star` | Calendar governance risk only | Cap 240 | Yes if schedule known | Low/Medium | Keep + ablation-test | Uses scheduled event time, not market reaction. |
| `mins_since_last_3star` | Low | Cap 240 | Yes | Low | Keep + ablation-test | Uses previous scheduled event time. |

## Removed From Old 42, Not In Current 36

These are not current model features, so Step 2 does not audit them as active risk:

```text
trade_direction
h4_in_ob_zone
adx_trend_count
h4_trending_h1_aligned
h4_ranging_h1_neutral
h4_h1_regime_score
```

## Detailed Notes

### `slot_win_rate`

- Code: `engine/features.py:29` `build_slot_table`, `engine/features.py:546`, `engine/features.py:582`, `engine/train.py:130-131`.
- Calculation: hourly mean of `win_bin`, looked up by `t.hour`.
- Uses future candles: No.
- Uses target label: Yes, `win_bin`.
- Full-dataset risk: Yes if built on full trade history before validation/OOS. Current main train builds from first 70% train slice.
- Fixed threshold: No.
- Manual rule: No; historical prior input.
- Live availability: Yes after table is trained.
- OOS/WFO safe: Only if table is trained inside cutoff/past-only.
- Risk: Medium.
- Recommendation: Ablation-test.

### `hmm_state`

- Code: `engine/hmm_model.py` `MarketStateHMM.fit/predict`, `engine/train.py:164-167`, `engine/inference.py:713-717`.
- Calculation: GaussianMixture regime state from ADX/band feature list, appended as `hmm_state`.
- Uses future candles: No if source ADX/band rows are as-of.
- Uses target label: No.
- Full-dataset risk: Low in current train path because HMM fits only up to train cutoff.
- Fixed threshold: No trading threshold.
- Manual rule: No.
- Live availability: Yes.
- OOS/WFO safe: Yes if fit only on training data.
- Risk: Low.
- Recommendation: Keep + ablation-test.

### `in_range_phase`

- Code: `engine/features.py:357`, `engine/features.py:387`, `engine/features.py:392`.
- Calculation: H4 grouped candle move; `1` if `abs((close-open)/open*100) < 0.5`.
- Uses future candles: Possible yes. Precomputed H4 grouped table can include final close/high/low of an unfinished H4 block.
- Uses target label: No.
- Full-dataset risk: Uses future OHLC rows inside same H4 group if table built from full OHLC.
- Fixed threshold: Yes, `0.5%`.
- Manual rule: Regime condition, not direct entry rule.
- Live availability: Questionable until fixed to last fully closed H4 only.
- OOS/WFO safe: No, not clean as-is.
- Risk: High.
- Recommendation: Exclude from first clean ablation or fix calculation later.

### `corr_imp_ratio`

- Code: `engine/features.py:433`, `engine/features.py:453-454`, `engine/features.py:508-516`.
- Calculation: H4 swing highs/lows using centered `n=3` future bars, then correction/impulse ratio.
- Uses future candles: Yes, explicitly uses H4 `i+1..i+3`.
- Uses target label: No.
- Full-dataset risk: Yes through future swing confirmation.
- Fixed threshold: `n=3`, `move >= 0.3`, `candles >= 2`.
- Manual rule: Swing-structure logic, not direct trade rule.
- Live availability: No.
- OOS/WFO safe: No.
- Risk: Critical.
- Recommendation: Exclude from first clean ablation; remove or redesign later.

### OB/SR features

Features:

```text
h4_resist_dist, h4_support_dist, h4_ob_strength,
h1_resist_dist, h1_support_dist, h1_ob_strength
```

- Code: `engine/features.py:229` `build_ob_table`, `engine/features.py:273` `get_ob_features`.
- Calculation:
  - OB is candle before strong next impulse.
  - `is_strong = range_pct > range_ma10*1.5`.
  - `confirm_datetime = next bar datetime`.
  - `get_ob_features` filters `confirm_datetime < t`.
  - Distances use nearest confirmed OB midpoint.
  - Strength uses confirmed next impulse `range_pct`.
- Uses future candles: It uses next candle for OB confirmation, but should not expose it before `confirm_datetime < t`.
- Uses target label: No.
- Full-dataset risk: Precomputed table includes future confirmations, but availability filter blocks early use.
- Fixed threshold: Yes for OB strength/strong impulse; side filter for distances.
- Manual rule: Handcrafted market-structure inputs, not entry/exit rules.
- Live availability: Yes after confirmation.
- OOS/WFO safe: Mostly yes if `confirm_datetime < t` remains enforced.
- Risk: Low/Medium for distances, Medium for strengths.
- Recommendation: Ablation-test.

### News timing features

Features:

```text
mins_to_next_3star, mins_since_last_3star
```

- Code: `engine/features.py:806`, `engine/features.py:808`.
- Calculation:
  - `mins_to_next_3star`: minutes to next impact-3 calendar event, capped 240.
  - `mins_since_last_3star`: minutes since previous impact-3 event, capped 240.
- Uses future candles: No market candles.
- Uses future trade result: No.
- Uses target label: No.
- Full-dataset risk: `mins_to_next_3star` uses future scheduled event rows; acceptable only if schedule was known before trade.
- Fixed threshold: Numeric cap 240.
- Manual rule: No.
- Live availability: Yes with known calendar.
- OOS/WFO safe: Yes if historical calendar reflects known scheduled times.
- Risk: Low/Medium for next event, Low for since event.
- Recommendation: Keep + ablation-test.

## Step 2 Lists

Definitely safe or low risk:

```text
hmm_state
mins_since_last_3star
mins_to_next_3star, conditional on known calendar
h4_resist_dist, h4_support_dist, h1_resist_dist, h1_support_dist, conditional on confirm_datetime
```

Possible leakage:

```text
slot_win_rate
in_range_phase
corr_imp_ratio
```

Remove/exclude immediately from first clean test:

```text
corr_imp_ratio
in_range_phase
```

Need ablation testing:

```text
slot_win_rate
hmm_state
h4_resist_dist
h4_support_dist
h4_ob_strength
h1_resist_dist
h1_support_dist
h1_ob_strength
mins_to_next_3star
mins_since_last_3star
```

Step 2 status: current 36 suspicious-feature audit complete.
