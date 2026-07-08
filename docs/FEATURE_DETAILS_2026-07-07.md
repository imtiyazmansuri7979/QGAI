# QGAI Feature Details + Importance — 2026-07-07

**Live main model:** 42 features (41 `FEATURE_COLS` + `hmm_state`), AUC 0.6772, retrained 20260706.
Source: `data/models/final/feature_importance.csv` + `features.py::FEATURE_COLS`.
State-specific hybrid models: Ranging=32 · Trending=28 · Volatile=18 features.

---

## TIER 1 — HIGH importance (>0.035) — the model's real levers
| Rank | Feature | Imp | What it is / why used |
|-----:|---------|----:|-----------------------|
| 1 | `in_range_phase` | 0.071 | H4 chop/range detector (0/1). Top driver — gates trend vs range behavior |
| 2 | `move_1hr` | 0.048 | Gold $ change last 1hr. Data #1 momentum edge (+27.7pp WR) |
| 3 | `price_pos` | 0.042 | Price position in 20-candle range (0-1) — over/under-extended |
| 4 | `15_min_slot` | 0.042 | Direct 15-min slot timing (entry granularity) |
| 5 | `M15_DI_diff` | 0.042 | M15 +DI−−DI — short-TF direction |
| 6 | `M15_ADX` | 0.041 | M15 trend strength |
| 7 | `h4_support_dist` | 0.039 | H4 support OB %distance (loss-dir) |
| 8 | `day_of_week` | 0.039 | Weekday pattern |
| 9 | `ts_htf_agreement` | 0.037 | M15+H1+H4 SMMA agreement (−3..+3) — multi-TF trend |
| 10 | `H4_DI_diff` | 0.035 | H4 direction |
| 11 | `slot_win_rate` | 0.035 | 1-hour slot historical WR (leak-fixed) |

## TIER 2 — MEDIUM (0.019–0.035) — contextual support
| Rank | Feature | Imp | What |
|-----:|---------|----:|------|
| 12 | `M30_DI_diff` | 0.032 | M30 direction |
| 13 | `h1_ob_strength` | 0.031 | H1 order-block strength |
| 14 | `range_pct` | 0.031 | Candle range % |
| 15 | `move_4hr` | 0.031 | 4hr momentum (KEY: BUY↓=31%WR, BUY↑=52%WR) |
| 16 | `mins_to_next_3star` | 0.030 | Minutes to next 3★ news |
| 17 | `h1_resist_dist` | 0.030 | H1 resistance OB %dist |
| 18 | `h4_resist_dist` | 0.030 | H4 resistance OB %dist |
| 19 | `h1_adx_slope` | 0.030 | H1 ADX slope — strengthening/dying |
| 20 | `H4_ADX` | 0.027 | H4 trend strength |
| 21 | `h1_support_dist` | 0.027 | H1 support OB %dist |
| 22 | `momentum_aligned_4hr` | 0.027 | Signal vs 4hr momentum (+1/−1) — KEY |
| 23 | `h4_ob_strength` | 0.026 | H4 OB strength |
| 24 | `body_pct` | 0.026 | Candle body conviction |
| 25 | `h4_adx_slope` | 0.025 | H4 ADX slope |
| 26 | `M30_ADX` | 0.025 | M30 trend strength |
| 27 | `H1_DI_diff` | 0.023 | H1 direction |
| 28 | `H1_ADX` | 0.021 | H1 trend strength |
| 29 | `corr_imp_ratio` | 0.020 | Corrective vs impulsive ratio |

## TIER 3 — LOW (>0, <0.019) — marginal
| Rank | Feature | Imp | What |
|-----:|---------|----:|------|
| 30 | `price_vs_ema200` | 0.013 | Distance from EMA200 ($ signed) |
| 31 | `hmm_state` | 0.013 | Market regime (0/1/2) — small direct, drives state-model routing |
| 32 | `slot_cos` | 0.006 | Cyclical slot encoding |
| 33 | `ts_bars_since_flip` | 0.003 | M15 bars since SMMA flip (freshness) |

## TIER 4 — 🔴 ZERO importance (0.0000) — DEAD WEIGHT (9 features)
| Rank | Feature | Note |
|-----:|---------|------|
| 34 | `mins_since_last_3star` | model never splits on it |
| 35 | `momentum_aligned_1hr` | **redundant** with move_1hr (#2) |
| 36 | `momentum_aligned_2hr` | redundant with move_2hr |
| 37 | `h4_trending_h1_aligned` | redundant with ts_htf_agreement / DI diffs |
| 38 | `adx_trend_count` | redundant with individual ADX features |
| 39 | `h4_ranging_h1_neutral` | redundant with in_range_phase (#1) |
| 40 | `h4_h1_regime_score` | redundant with in_range_phase + DI diffs |
| 41 | `trade_direction` | direction lives in DI_diffs + momentum_aligned |
| 42 | `h4_in_ob_zone` | redundant with h4_resist/support_dist |

---

## 🚩 SUSPECTED OVERRIDING / REDUNDANCY (for Fable review)

1. **`in_range_phase` (#1, 0.071) may DOMINATE** — 1.5× the #2 feature. It's ALSO a hard entry
   filter (`skip_range_phase_entry`). Feature + filter double-counting → the model may be
   over-relying on one regime signal.

2. **Momentum family collinear:** `move_1hr`(#2)/`move_4hr`(#15) carry the signal;
   `momentum_aligned_1hr/2hr` = 0.0 (dead). The model picked raw moves, aligned-flags redundant.

3. **ADX/DI stack (9 features):** M15/M30/H1/H4 × (ADX + DI_diff) + 2 slopes + adx_trend_count.
   Many are collinear across TFs. `adx_trend_count`=0.0. Possible multicollinearity diluting
   each ADX feature's attributed importance.

4. **OB distance stack (8 features):** h4/h1 × resist/support/strength/in_zone. `h4_in_ob_zone`=0.0.
   The dist features carry it; zone flags redundant.

5. **Regime-combo features all 0.0:** `h4_trending_h1_aligned`, `h4_ranging_h1_neutral`,
   `h4_h1_regime_score` — hand-crafted regime combos the model ignores in favor of raw
   in_range_phase + DI diffs.

6. **`trade_direction`=0.0** — direction encoded elsewhere; possibly safe to drop.

**Net:** 9 dead features (21% of the vector) + 4 redundant clusters. Pruning could reduce
overfitting/noise, but a prior prune list was WRONG on honest data (hmm_state went 0→#6 area),
so re-verify before cutting.
