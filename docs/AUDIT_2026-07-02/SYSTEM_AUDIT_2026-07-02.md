# QGAI v2 — INDEPENDENT SYSTEM AUDIT (2026-07-02)

**Mandate:** find weaknesses, overfitting, leakage, hidden risk. Not to prove the system works.
**Data used:** `data/models/final` (meta + feature importance), 651 WFO OOS trades (`wfo_live_match_015`, 53 weeks 2025-06-29→2026-06-29), in-sample full-year replay (`live_buffer_015`), 754 shadow trades (Dec 2024→Jul 2026, deduped), 18 real live trades (2026-06-12→06-30), live `signals_all.csv`, engine source code, docs/BUG_LOG.
**Not available in this audit:** pkl internals beyond meta (sandbox lacks xgb/lgb/cat), per-model per-trade probabilities beyond the 3 logged streams, demo-account fill logs.

---

## 1. MODEL HEALTH CHECK

| Model | Purpose | Features | Val AUC / metric | Status |
|---|---|---|---|---|
| `hmm_model.pkl` (GMM 3-state) | Regime → threshold, model routing, TP/buffer regime | 12 | n/a (unsupervised) | **BROKEN on disk** (attempt-2; known Volatile mislabel; v3 A/B WFO in progress) |
| `xgb_model.pkl` (XGB+LGB+Cat + isotonic) | Combined win-probability (70% weight in routing) | 42+hmm_state | AUC 0.687 | Primary gate |
| `buy_model.pkl` | BUY-specific win-prob (30% blend member) | 42 | AUC 0.667 | Active |
| `sell_model.pkl` | SELL-specific win-prob | 42 | AUC 0.729 | Active |
| `model_ranging/trending/volatile.pkl` | Per-state win-prob (30% blend member) | state-subset of 42 | not logged | Active |
| `big_win_model.pkl`, `duration_model.pkl` | Auxiliary predictions (non-gating) | 42 | AUC ~ not re-logged | Informational |
| `move_model_*` (6, quantile) + `sl_model_*` (4) | Move/SL quantile predictions | — | BUY PASS (ρ=0.34); **SELL FAIL (ρ=0.25)** | Stale (2026-06-12); SELL failed own validation gate |
| `online_model.pkl` + `drift_detector.pkl` | Online adaptation / drift alarm | — | — | Present |
| `slot_table.pkl`, `slot_day_filter.json` | Time-of-day win-rate lookups | — | — | Lookup, not a model |

**Routing reality (from 651 OOS trade logs):** every single trade used `combined(70%)+state(30%)+dir(30%)` — one blend, no voting. The "many models" are one ensemble family plus decorations.

**Redundancy findings.** (a) buy/sell/state/combined models are all trained on the SAME 2,743 trades with the SAME 42 features — five views of one dataset; blend inputs correlate (win↔state 0.38, win↔dir 0.27) and the blend's weights are fixed, not learned. (b) **10 of 42 features have exactly ZERO importance** in the current combined model: `hmm_state, ts_bars_since_flip, momentum_aligned_1hr, momentum_aligned_4hr, mins_since_last_3star, adx_trend_count, h4_trending_h1_aligned, h4_ranging_h1_neutral, trade_direction, h4_in_ob_zone` — dead weight. Note the irony: `hmm_state` as a FEATURE adds nothing; its entire effect is threshold/routing/TP-regime. (c) SELL move-model failed its own validation and is still deployed on disk.

---

## 2. DATA LEAKAGE AUDIT

**CONFIRMED — intra-bar HTF lookahead (systematic).** The M15-grid ADX file is built by resampling FULL H4/H1/M30 bars (left-labeled) and forward-filling into the M15 rows *inside* those bars. So at decision time 09:00, the stored `H4_ADX/H4_DI_diff` already contain highs/lows/closes up to 11:59. Empirical measurement (June 2026, 20 days): backtest value vs honest partial-bar value differs by mean 0.60 / max 2.02 ADX points on H4, mean 0.34 / max 1.91 on H1 — non-zero on essentially every mid-bar decision. In LIVE the updater recomputes from the *partial* forming bar, so **the backtest sees information live never has**: simultaneous look-ahead bias in backtest/WFO AND train/serve skew, on the single most important feature family (ADX/DI block = ~30% of total importance) plus `h4_adx_slope/h1_adx_slope`, the regime-alignment features, and ALL HMM state inputs (the new band/di_eff/band_rel columns inherit the same convention).

**Other checks.** Future candles: trend-signal features use the closed-bar convention (`trend_at` with `when − tf` cutoff) — clean. Repainting: the 2-SMMA ratchet lines don't repaint; ADX ffill is the repaint-equivalent (above). Label leakage: labels are recomputed under the live HTF exit (relabel project) — mechanically consistent; but the label generator and the backtest are the same engine, so any engine optimism enters labels too. Train/test contamination: WFO cutoff filters trades+ohlc+adx (< week start) and slot table is train-split-only — protocol is sound; contamination via the intra-bar columns remains. HMM v2 predict-path fed PlusDI/MinusDI = 0 silently (train≠predict) — found and fixed this session, pending deploy. Duplicates: shadow log contained 11 duplicate rows (765→754) — logging hygiene issue; training-set dedupe not directly verifiable in this audit. WFO cache (#H) and tp-equity bypass (#G) were real historical leakage/invalidation bugs — culture catches them, but they keep appearing.

**Leakage risk score: 38/100** (0 = clean). Protocol-level design is decent; one confirmed systematic intra-bar leak of modest per-bar magnitude but on the dominant feature family and the regime detector, plus a history of engine≠live bugs.

---

## 3. OVERFITTING ANALYSIS

| Layer | WR | PF | Avg R | Total | Source |
|---|---|---|---|---|---|
| In-sample full-year (same period) | 65.7% | 4.27 | +0.718 | +428.5R | live_buffer_015 |
| **WFO "OOS"** (53 wk, weekly retrain) | 68.2% | 4.43 | +0.742 | +483.1R | wfo_live_match_015 |
| Shadow / paper (19 mo, live-computed) | 50.1% | — | **+0.377** | +284.6R / 754 | shadow_trades.csv |
| Shadow, June 2026 only | **29.4%** | <1 | −0.02 | **−1.9R / 109** | shadow_trades.csv |
| Real live (18 trades, 2.5 wk) | 27.8% | — | — | +$137k, **but top-3 wins = +$158.7k; other 15 trades = −$21.5k** | live_trades.csv |

The alarming pattern is not train>val — it is that **"OOS" ≥ in-sample** (WFO PF 4.43 > in-sample 4.27). True out-of-sample degradation is ~30–50% for honest systems; here the WFO shows none, while the live-computed shadow shows a ~50% avgR haircut and the most recent month (June 2026) shows the WFO at +48.1R / 66.7% WR **while the shadow log for the same month is −1.9R / 29.4% WR on 109 trades**. Also: **51 positive weeks, 0 negative in 53** — for a retail M15 system this distribution is statistically implausible as genuine OOS and is the signature of shared engine optimism (intra-bar HTF features + modeled exit fills) rather than random luck.

Model-level AUCs (0.667–0.729 val) are modest and honest. The overfitting is not primarily in the classifiers — **it is in the backtest engine's world-model**. Classification: models = slightly overfit; **backtest/WFO pipeline = moderately-to-severely optimistic**; live evidence insufficient (n=18) but pointing the wrong way.

---

## 4. REGIME ANALYSIS (651 WFO OOS trades)

| Regime | Trades | WR | PF | Avg R | Total R | Avg win / loss |
|---|---|---|---|---|---|---|
| Ranging | 188 | 68.6% | **6.58** | **+1.149** | +216.0 | +1.97R / −0.64R |
| Trending | 211 | 69.2% | 4.44 | +0.668 | +141.0 | +1.19R / −0.49R |
| Volatile | 252 | 67.1% | 3.33 | +0.500 | +126.0 | +0.97R / −0.46R |

Best = Ranging, worst = Volatile (still positive). Max DD in R terms 4.0R (suspiciously smooth); max 6 consecutive losses. **BUT:** shadow trades order the regimes differently (Trending +0.649 avgR best; Ranging +0.208; Volatile +0.226), i.e. **the regime labels themselves do not transfer** from backtest to live — expected, given the regime detector is the component currently known to be broken (2026-07-02 live: the flat 08:00–13:15 window = 23/23 bars "Volatile"; last 30 live days = 42% Trending / 34.5% Volatile / 23.5% Ranging). The avgWin ladder (1.97/1.19/0.97) mostly reflects the regime-TP caps (2.0/1.0/0.8), i.e. the exit config, not model skill.

---

## 5. PROBABILITY QUALITY TEST (651 OOS trades)

| Predicted bucket | n | Predicted WR | Actual WR | Avg R |
|---|---|---|---|---|
| <50% | 164 | 46.3% | **67.1%** | +0.693 |
| 50–55% | 107 | 52.3% | 61.7% | +0.568 |
| 55–60% | 101 | 57.3% | 66.3% | +0.610 |
| 60–65% | 102 | 62.5% | 68.6% | +0.908 |
| 65–70% | 52 | 67.4% | 71.2% | +0.819 |
| 70%+ | 125 | 81.6% | 75.2% | +0.895 |

**Verdict: probabilities are NOT trustworthy.** A 35-point predicted range (46→82%) maps to a 13-point actual range (62→75%), the lowest bucket outperforms the mid buckets, and isotonic calibration is failing out-of-sample. Practical implication: the 0.42–0.50 state thresholds barely bind — 164 sub-50% trades were taken and earned +113.7R (24% of all profit). Raising the threshold to a "sensible" 0.55 would have *destroyed* profit. The classifier is a weak ranker, not a probability engine; the money comes from elsewhere (see §8).

---

## 6. MODEL AGREEMENT ANALYSIS

The system has no 5-model vote; it logs three probability streams (combined / state / dir). Agreement = number of streams > 0.5:

| Agreement | n | WR | PF | Avg R | Total R |
|---|---|---|---|---|---|
| 0/3 | 55 | 54.5% | 2.67 | +0.553 | +30.4 |
| 1/3 | 179 | 62.6% | 3.60 | +0.630 | +112.8 |
| 2/3 | 236 | 72.9% | **5.60** | **+0.877** | +207.0 |
| 3/3 | 181 | 71.8% | 4.67 | +0.734 | +132.8 |

Minimum agreement for profitability: **zero** — even 0/3 trades were profitable OOS, which again says the entry filter is not the edge. 2/3 is the sweet spot; 3/3 adds nothing (correlated ensembles saturate). A 2-of-3 gate would have cut 234 trades (+143.2R foregone) — under the house profit-first rule, do NOT add such a gate without WFO proof.

---

## 7. FEATURE IMPORTANCE REVIEW (combined model, 2026-07-02 retrain)

Top of the table: `in_range_phase` (0.070) is #1 by a wide margin, then `move_1hr` (0.046), `h4_ob_strength` (0.045), `price_pos` (0.041), `H1_DI_diff` (0.041), `M30_DI_diff` (0.039), `h4_h1_regime_score` (0.038), `15_min_slot` (0.038), `h4_support_dist` (0.035), `h1_ob_strength` (0.034), `M15_ADX` (0.034), `day_of_week` (0.034), `ts_htf_agreement` (0.034), `H4_DI_diff` (0.033), `M15_DI_diff` (0.032), `h1_adx_slope` (0.032), `H4_ADX` (0.031), `M30_ADX` (0.030), `slot_win_rate` (0.029), `range_pct` (0.029).

Useless (exactly 0.0): the 10 features listed in §1 — prune them. Redundant: 8 ADX/DI features + 2 slopes + 3 regime-alignment features all derive from one Wilder pipeline (~11 features, ~30% of importance, all sharing the intra-bar leak of §2); `slot_win_rate`/`15_min_slot`/`slot_cos`/`day_of_week` overlap. Overfit-prone: `slot_win_rate` and `15_min_slot`+`day_of_week` (a learned time-of-day lookup + raw slot keys = memorising the calendar of 2,743 trades); `in_range_phase` at 2× the next feature deserves a leave-one-out sanity test. Honest positives: OB/support-resist distances and `price_pos`/`move_1hr` are structurally sensible and independently computed.

---

## 8. EXIT ANALYSIS (651 OOS trades)

| Exit | n | WR | PF | Avg R | Total R | Share of profit |
|---|---|---|---|---|---|---|
| TPCAP (regime TP cap) | 272 (42%) | 100%* | inf | +1.587 | **+431.6** | **89%** |
| FLIP (signal reversal) | 258 (40%) | 58.9% | 1.97 | +0.421 | +108.7 | 23% |
| TRAIL | 75 (12%) | 26.7% | **0.29** | −0.150 | **−11.3** | −2% |
| SL | 46 (7%) | 0%* | 0 | −1.000 | −46.0 | −10% |

*by construction. **The exit engine IS the system.** 89% of all profit is the regime-adaptive TP cap; the ML entry gate barely binds (§5). Two red flags: (1) the TRAIL bucket is value-destroying as logged (PF 0.29) — investigate whether trailing exits are rescuing disasters or amputating winners; (2) the SHADOW exit mix is radically different (TRAIL 32.5% of shadow exits vs 11.5% in backtest; FLIP 22% vs 40%) — live exits do not behave like backtested exits, which is exactly where the June divergence would come from. Best exit method on this data: TPCAP + FLIP; TRAIL as configured is suspect. All TP fills assume touch-fill at modeled price with 0.20 spread and zero slippage — unvalidated against broker fills.

---

## 9. LIVE DEPLOYMENT READINESS

| Dimension | Score | Basis |
|---|---|---|
| Predictive Power | 35 | AUC 0.67–0.73; calibration broken; threshold non-binding |
| Robustness | 40 | Good WFO protocol; but OOS ≥ in-sample and 51/0 week record = engine optimism |
| Risk Control | 50 | Small avg loss (−0.52R), daily-SL, equity guards; BUT live lots ranged 0.89→15.58 and one −$16.5k day |
| Adaptability | 60 | Weekly retrain, online learner, drift detector, active bug culture |
| Regime Detection | 25 | Known-broken on disk; live 23/23 Volatile on a flat morning; v3 fix unvalidated |
| Execution Quality | 30 | June 2026: shadow 29.4% WR vs backtest 66.7% same month; exit-mix mismatch |
| Capital Preservation | 45 | Live P&L = 3 trades; ex-top-3 the book is −$21.5k; DD estimates 10.8%→39% depending on assumptions |
| **OVERALL** | **41/100** | |

---

## 10. RED TEAM REVIEW (assume it fails)

**Biggest weakness:** the backtest's world-model, not the models. The WFO says +9.1R/week with zero losing weeks; the live-computed shadow says +0.377R/trade falling to **negative in the newest month**. Until that gap is explained bar-by-bar, every backtest number (including the pending A/B HMM WFO) is an upper bound, not an estimate.

**Most dangerous assumption:** that exits fill as modeled (TPCAP touch-fills, 0.20 fixed spread, no slippage, no requotes) and that decision-time features equal stored features (they don't — §2). 89% of profit flows through those two assumptions.

**Most likely failure condition:** exactly what June 2026 looked like — high absolute volatility, low directional efficiency (post-trend chop), regime stuck on "Volatile" (threshold 0.42 = most permissive), spreads widening around news. Shadow evidence: 109 trades, 29.4% WR, −1.9R. Second failure mode: a gapping news candle against a 15-lot position (live sizing already reached 15.58 lots).

**Expected drawdown during failure:** with 3% risk/trade, 6+ observed consecutive losses and June-style 30% WR sustained for 4–6 weeks: **25–40% equity drawdown** is the realistic planning number (the house's own P2b estimate: 18.7% "optimistic", possibly 28–39%).

**How to reduce risk:** (1) fix the HTF feature convention — use last CLOSED HTF bar (or recompute partial-bar in the file) so backtest = live, then re-run the WFO and accept the lower number as the real baseline; (2) reconcile shadow vs backtest for June 2026 trade-by-trade before trusting any further WFO; (3) risk 1–1.5% and a hard lot cap until 4–8 weeks of demo shows backtest-parity; (4) prune the 10 dead features and retire the failed SELL move-model; (5) investigate/disable the TRAIL exit as configured; (6) recalibrate or stop interpreting win_prob as probability; (7) keep the A/B HMM gate (this session) — regime is the highest-leverage broken part.

---

## 11. FINAL VERDICT: **D — Experimental** (borderline C−)

Reasoning. The engineering culture is genuinely above retail standard: true walk-forward with weekly retrain and cutoffs, fixed-lot R accounting, an adversarial BUG_LOG, demo-first discipline, profit-first evaluation. The exit architecture (regime TP caps + flip exits with small average losses) is a coherent, plausible edge. But the audit cannot certify the headline numbers: a confirmed intra-bar feature leak favors the backtest on its most important feature family; probability calibration is broken; the regime detector — which sets thresholds, models, and TP caps — is mid-surgery; and the only ground truth we have (754 shadow trades, 18 real trades) shows roughly half the backtested edge overall and a *negative* newest month while the backtest shows +48R for the same month. "51 profitable weeks, 0 losing" is not a track record — it is a warning label.

Path to C: (i) close the HTF-feature parity gap and re-run WFO; (ii) explain June 2026 shadow-vs-backtest divergence; (iii) deploy the validated HMM v3; (iv) 4–8 weeks demo with weekly backtest-vs-actual reconciliation within ±20%. Path to B requires live months, not backtests.

*Auditor: Claude (independent review requested by Divyesh). All figures computed from repository data on 2026-07-02; numbers are reproducible from the files cited in the header.*
