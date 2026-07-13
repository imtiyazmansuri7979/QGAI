# QGAI — Model Feature Reference

**Updated:** 2026-06-19 · **Total:** 67 features (+ `hmm_state` regime) feeding the win/buy/sell + state models.
**Importance:** ⭐⭐⭐ High · ⭐⭐ Medium · ⭐ Supporting.
Tiers are inferred from the in-code "data-proven" annotations + domain reasoning — **for the exact ranking, load the model and read `feature_importances_`** (run on your PC; the sandbox can't load xgboost). After a retrain you can dump real importances.

> **Recent changes:** `atr14_pct` / `atr20_pct` **removed** (lagging, redundant with the 2-SMMA). `slot_win_rate` rebuilt on **1-hour** slots + **train-split only** (leakage fixed).

---

## Current Update - 2026-07-12

Do not delete the historical feature notes below. Current code status after the latest prune:

- Current base `FEATURE_COLS`: 27
- `hmm_state`: still used/appended by regime models
- Regime lists: Ranging=22, Trending=23, Volatile=17
- OB/SR model inputs currently pruned: `h4_resist_dist`, `h4_support_dist`, `h4_ob_strength`, `h1_resist_dist`, `h1_support_dist`, `h1_ob_strength`
- Volume inputs remain pruned: `volume`, `tick_volume`
- `in_range_phase` remains active
- Live model files change only after retraining

Full current active/regime list: `docs/FEATURES_MASTER.md`.

---

## 1. Order-Flow / Timing (when to trade)

| Feature | What it does | Imp |
|---|---|---|
| `is_ny_session` | 1 = NY session (15–18 UTC), WR 40–52% — the prime window | ⭐⭐⭐ |
| `session_score` | Session quality −2 (worst) → +2 (best NY) | ⭐⭐⭐ |
| `slot_win_rate` | Historical win-rate of the **1-hour** time-slot (priority signal) | ⭐⭐ |
| `day_of_week` | Weekday pattern (some days trend better) | ⭐⭐ |
| `is_dead_hour` | 1 = low-WR hours (09, 20 UTC) — avoid | ⭐ |
| `15_min_slot` | Raw 15-min slot index (entry granularity) | ⭐ |
| `slot_cos` | Cyclical (cosine) encoding of time-of-day | ⭐ |
| `trade_direction` | BUY=1 / SELL=0 (lets the model learn dir-specific edges) | ⭐⭐ |

## 2. Momentum / Price Action (the strongest edge group)

| Feature | What it does | Imp |
|---|---|---|
| `move_1hr` | Gold price change last 1h ($) — **data #1 edge +27.7pp WR** | ⭐⭐⭐ |
| `move_4hr` | 4h price change — KEY (BUY after ↓=31% WR, after ↑=52% WR) | ⭐⭐⭐ |
| `move_2hr` | 2h price change — **+15.7pp edge** | ⭐⭐⭐ |
| `move_8hr` | 8h price change — trend persistence | ⭐⭐ |
| `momentum_aligned_4hr` | +1 if trade dir matches 4h momentum, −1 against | ⭐⭐⭐ |
| `momentum_aligned_2hr` | dir vs 2h momentum | ⭐⭐ |
| `momentum_aligned_1hr` | dir vs 1h momentum | ⭐⭐ |
| `range_pct` | Candle range % (volatility proxy — replaces ATR) | ⭐⭐ |
| `body_pct` | Candle body % (conviction of the bar) | ⭐ |
| `price_pos` | Price position within the 20-candle range (0–1) | ⭐ |
| `volume` / `vol_spike` | Raw tick volume / volume-spike flag | ⭐ / ⭐⭐ |

## 3. EMA200 (mean-reversion / context)

| Feature | What it does | Imp |
|---|---|---|
| `price_vs_ema200` | Signed % distance from EMA200 — **+3.8pp WR, +$8.7k P&L** | ⭐⭐⭐ |
| `near_ema200` | 1 = within ±0.35% danger zone (WR 31%) | ⭐⭐⭐ |
| `ema200_dist_abs` | Absolute distance (far = good, near = bad) — data-proven | ⭐⭐ |
| `above_ema200` | 1 = price above EMA200 (trend bias) | ⭐⭐ |

## 4. Trend Signals — the 2-SMMA / ratchet indicator (core strategy)

| Feature | What it does | Imp |
|---|---|---|
| `ts_trend_m15` / `ts_trend_h1` / `ts_trend_h4` | 2-SMMA trend state (+1/−1) per timeframe | ⭐⭐⭐ |
| `ts_htf_agreement` | M15+H1+H4 agreement (−3…+3) — multi-TF alignment | ⭐⭐⭐ |
| `ts_adx_switch_trend` | EA rule: use H4 trend if H4 ADX≥19 else H1 | ⭐⭐ |
| `ts_aligned` / `ts_aligned_htf` | Trade dir vs M15 trend / vs ADX-switch trend | ⭐⭐ |
| `ts_line_dist_pct` | Distance from the ratchet line (%) | ⭐⭐ |
| `ts_bars_since_flip` / `ts_flip_recent` | Bars since last flip / flip within last 3 bars (freshness) | ⭐ |

## 5. ADX / Trend Strength (regime)

| Feature | What it does | Imp |
|---|---|---|
| `H1_ADX` / `H4_ADX` | Higher-TF trend strength | ⭐⭐⭐ |
| `M15_ADX` / `M30_ADX` | Lower-TF trend strength | ⭐⭐ |
| `H1_DI_diff` / `H4_DI_diff` | Directional index diff (trend direction) HTF | ⭐⭐ |
| `M15_DI_diff` / `M30_DI_diff` | DI diff LTF | ⭐ |
| `h4_h1_regime_score` | Combined H4/H1 regime score (−1…+2) | ⭐⭐⭐ |
| `h4_trending_h1_aligned` | H4 trend + H1 confirms — **+3.7pp WR** | ⭐⭐⭐ |
| `h4_ranging_h1_extended` | H4 range + H1 extended — **AVOID −8.2pp** | ⭐⭐ |
| `h4_ranging_h1_neutral` | H4 range + H1 neutral — +1.8pp | ⭐ |
| `adx_trend_count` | # timeframes with ADX>20 | ⭐ |
| `h4_adx_slope` / `h1_adx_slope` | ADX rising/falling (trend strengthening/dying) | ⭐ |

## 6. Order-Block Structure (S/R — newer features)

| Feature | What it does | Imp |
|---|---|---|
| `h4_resist_dist` / `h4_support_dist` | % distance to H4 resistance / support OB | ⭐⭐ |
| `h1_resist_dist` / `h1_support_dist` | % distance to H1 resistance / support OB | ⭐⭐ |
| `h4_ob_strength` / `h1_ob_strength` | Strength of nearest resistance OB | ⭐ |
| `h4_in_ob_zone` / `h1_in_ob_zone` | 1 = price inside an OB zone | ⭐ |
| `in_range_phase` | Confirmed ranging phase | ⭐ |
| `corr_imp_ratio` | Corrective-vs-impulsive move ratio | ⭐ |
| `is_post_big_move` / `big_move_direction` | After a big move / its direction | ⭐ |

## 7. News / Fundamentals

| Feature | What it does | Imp |
|---|---|---|
| `last_3star_dev_sign` | Last 3★ event beat/miss sign — **0.856 importance!** | ⭐⭐⭐ |
| `is_post_news` | Within 15 min after 3★ news (post-news WR 41–44%) | ⭐⭐⭐ |
| `mins_to_next_3star` | Minutes to next high-impact event | ⭐⭐ |
| `mins_since_last_3star` | Minutes since last high-impact event | ⭐ |
| `upcoming_3star_count` | # of 3★ events in next 2h | ⭐ |
| `before_eia` | EIA crude-oil event flag | ⭐ |

## 8. Market State

| Feature | What it does | Imp |
|---|---|---|
| `hmm_state` | HMM regime: Ranging / Trending / Volatile (0/1/2). **Selects which state-model runs** (Ranging=47, Trending=43, Volatile=35 features) | ⭐⭐⭐ |

---

## Quick takeaways
- **Strongest edges:** momentum (`move_1hr/2hr/4hr` + alignment), EMA200 distance, the 2-SMMA trend-signal suite, HTF ADX/regime, and the news surprise (`last_3star_dev_sign`).
- **Removed:** ATR (lagging) — volatility now comes from `range_pct` + the 2-SMMA.
- **Fixed:** `slot_win_rate` (now 1-hour + leakage-free).
- **For exact importances:** after `3_Train_Models.bat`, dump `model.feature_importances_` — I can add a 2-line print to `train.py` if you want a real ranked list every retrain.
