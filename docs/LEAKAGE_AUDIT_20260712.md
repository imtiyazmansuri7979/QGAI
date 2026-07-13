# QGAI — Full Leakage (Lookahead) Audit — 2026-07-12

**Scope:** every feature-building path in `engine/features.py` across ALL timeframes (M15 / M30 / H1 / H4) + swing/OB/news. Report only — no code changed.

**Method:** hunt future-peek patterns — `.shift(-n)`, `iloc[i+j]`, `searchsorted` by start-time (current forming candle), `resample/groupby` full-bar formation, global-sample stats. Then read each in context to decide leak vs safe.

**Convention the codebase uses (correct):** "last fully CLOSED higher-TF bar" — pick the HTF bar whose `end <= t` (via `cutoff = t − tf_min` or `datetime + tf <= t`). This matches live.

---

## 🔴 CONFIRMED LEAK (in model now)

### 1. `corr_imp_ratio` — DOUBLE leak — HIGH priority
**Where:** `build_trend_ratio_table` (features.py:466–530) + `get_trend_ratio_features` (features.py:533).
- **(a) Swing detection reads the future:** line 470–471 — a swing high at candle `i` requires `h4.high[i] > h4.high[i+j]` for j=1..3 → needs **3 future H4 candles** to confirm (≈12h ahead).
- **(b) Availability gate too early:** line 536 `searchsorted(ratio_df.datetime, t, side='right')` stamps the ratio at the swing candle's **start**. But that value was only computable after candle `i+3` closed → the ratio becomes "visible" ~**16h before it could really be known** live.
- Plus the H4 candle itself is a full `floor("4h")` bar.

**Status:** currently **IN the model** (35 feat) — restored 2026-07-11.
**Profit impact:** LOW. Even with it in (leaky), honest WFO ≈ +80R; the 07-09 AUC test showed removing it = −0.014 (noise). So it leaks but barely moves R.
**Fix options:** (i) drop it (honest, ~neutral R), or (ii) gate availability at `swing_datetime + 4×4h ≤ t` and keep it. Either needs a retrain + WFO gate.

---

## 🟠 MINOR LEAK (partial-candle)

### 2. `h4_ob_strength` / `h1_ob_strength` — LOW–MEDIUM (both are model features)
**Where:** `build_ob_table` (features.py:258–260) — `ob_strength = range_pct.shift(-1)` = the impulse candle's **full** range. `confirm_datetime = datetime.shift(-1)` = impulse candle's **start** (features.py:267). `get_ob_features` makes the OB visible when `confirm_datetime < t` (features.py:313).
**Leak:** the OB is exposed at the impulse candle's START, but `ob_strength` already holds that candle's FULL (not-yet-closed) range → up to ~1 H1/H4 of lookahead **on the strength value only**.
**Safe part:** the OB **zone** itself (`h4/h1_resist_dist`, `support_dist`, `in_ob_zone`) uses the PRIOR candle's high/low (fully closed) → no leak.
**Fix:** set `confirm_datetime` to the impulse candle's END (`+tf`), or compute `ob_strength` from the prior candle. Retrain + gate.

### 3. news `dev_norm` — LOW
**Where:** `load_news` (features.py:203) — `groupby("event")["deviation"].transform(z-score)` uses the **full-sample** mean/std (includes future releases) to normalize each event.
**Leak:** mild global-stats leak; affects only news-deviation features. Small magnitude, rarely the deciding feature.
**Fix:** expanding/rolling per-event stats instead of whole-sample. Low priority.

---

## ✅ VERIFIED SAFE (leak-free)

| Feature group | Why safe | Evidence |
|---|---|---|
| **M15/M30/H1/H4 `ADX`, `DI_diff`, `band_width_pct`, `di_eff`, `band_rel`** | as-of rebuild (EWM over completed bars + one Wilder step on partial bar = live-match) | **drift vs as-of = 0.0000** across 97,632 rows ✓ (07-03 fix still in the 07-11 file) |
| `h4_adx_slope`, `h1_adx_slope`, `h4_adx_rising` | rolling ADX, window **ending at last closed M15 bar** (cutoff = t−15m) | features.py:1005–1018 |
| `ts_trend_m15/h1/h4`, `ts_bars_since_flip`, `ts_htf_agreement`, `ts_line_dist_pct`, `ts_aligned*`, `ts_adx_switch_trend` | "last fully CLOSED bar" cutoff = t−tf_min | features.py:1091–1104 |
| `in_range_phase`, `is_post_big_move`, `big_move_direction/size` | honest fix — only H4 candles with `end ≤ t` | features.py:397–418 ⚠️ *leaky again if `QGAI_INRANGE_LEGACY=1`* |
| `h4/h1_resist_dist`, `support_dist`, `in_ob_zone` | `confirm_datetime` gate; zone from prior closed candle | features.py:306–313 |
| M15 OHLC: `range_pct`, `body_pct`, wicks, `price_pos`, `tick_volume` | current M15 bar, evaluated at bar-close (live parity) | features.py:631–642 |
| time/slot features | pure function of `t` | features.py:597–628 |

---

## Bottom line

1. **The honest ~+80R WFO baseline is trustworthy** — no big hidden leak is propping it up. The two dominant HTF inputs (ADX family, trend-signal family) are both verified leak-free. That's why restoring `corr_imp_ratio` didn't bring +444R back: the +444/+384 numbers were inflated by the **in_range_phase** leak (pre-07-09) + the **ADX** leak (pre-07-03), both now fixed.
2. **Only real leak left = `corr_imp_ratio`** (low profit impact) + minor `ob_strength` + tiny `dev_norm`. None will meaningfully change R.
3. **So raising R must come from genuine signal, not from un-fixing leaks.** Legit levels: better honest features, threshold/model tuning on honest data, entry/exit/risk logic.

## Recommended actions (report only — no change made)
| # | Action | Effort | Expected R effect |
|---|--------|--------|-------------------|
| A | Decide `corr_imp_ratio`: drop (honest) OR fix its availability gate + retrain + WFO | small | ~neutral (cleans a leak) |
| B | Fix `ob_strength` confirm timing + retrain + WFO | small | tiny |
| C | `dev_norm` → expanding stats | small | tiny |
| D | **Real R work:** honest feature R&D, tuning on the +80R baseline | large | the actual upside |

*Audit by Claude, 2026-07-12. No code modified. All line numbers vs features.py at audit time.*
