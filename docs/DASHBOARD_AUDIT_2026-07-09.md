# QGAI Dashboard Audit — 2026-07-09

**Auditor role:** independent senior AI-trading-system auditor / dashboard architect / quant-QA / product-risk reviewer.
**Scope:** live dashboard (`engine/dashboard.html` + `engine/bridge_dashboard.py`), research/backtest outputs
(`backtest_replay.py`, `run_wfo.py`), feature/leakage audit (`audit/feature_audit_20260709/`), config (`engine/config.py`),
docs (`SYSTEM_OVERVIEW.md`, `FILTERS_MASTER.md`).
**Stance:** strict, evidence-first. Praise only where evidence supports it. Painful truth preferred.

> ⚠️ **Evidence limits (read this first).** This audit is grounded in the files above, actually read on 2026-07-09.
> I did **not** re-run any backtest/WFO, did not diff every model-training log, and did not trace every one of the
> 36 features to source. Where a claim rests on something I did not fully verify, it is marked **[needs-confirm]**.
> Missing evidence is listed in each section rather than guessed.

---

## 1. Executive Summary

**Overall dashboard rating: RISKY** (not Broken — it runs and most live numbers are real; but it mixes purposes,
shows at least one known-leaky feature as a valid signal, and has **no** research/backtest-integrity surface at all).

The live dashboard is genuinely good at *operational* monitoring (price, open trade, vSL ticker, daily risk, news).
It is **not** trustworthy as a *decision-quality* or *research* surface, because the things most likely to be wrong
(feature leakage, OOS sample size, backtest-vs-live config parity, probability calibration) are **not shown anywhere**.

### Top 5 biggest risks
1. **Leaky feature shown as signal.** `corr_imp_ratio` (Step-2 audit = **Critical**, uses future H4 candles `i+1..i+3`)
   is an *active* model feature AND surfaced on the dashboard as `corr_ratio` in market-structure. The board presents
   a look-ahead-contaminated number as a valid live signal. `in_range_phase` (audit = **High**) is the same story.
   Evidence: `audit/.../STEP2_SUSPICIOUS_FEATURE_DEEP_AUDIT_GUJ.md`; payload keys `corr_ratio`, `in_range`.
2. **Backtest risk ≠ live risk — CONFIRMED.** `step4_monthly_set1_36/backtest_summary_st-htf.csv` shows
   `fixed_lot=0.01` with `risk_pct=3.0` and `max_dd_pct=0.9` (66 trades). The run used a **0.01 fixed lot**, not the
   live **3%-of-equity** sizing → every $-P&L / net-return-% / max-DD number is **not** live-equivalent. R-based metrics
   are fine; $-metrics compared to the live account are apples-to-oranges.
3. **"Too good" WFO with leaky features still in the set.** Full WFO (`wfo_part1_prune35`) = **53 weeks, 768 trades,
   +444.7R, pos=51 / neg=1 weeks, avg +8.39R/week**; the other two variants are **pos=52/neg=0**. Near-perfect weekly
   win rates on gold M15 are a **classic leakage/overfit signature** — and `corr_imp_ratio` (Critical) + `in_range_phase`
   (High) are *in* the Set-1 feature list that produced these. The clean-set control that would rule leakage in/out is
   **unfinished** (see F-10). *(Note: an earlier read of a partial summary showed "4 trades/week, PF blank"; that was
   a truncated early-weeks slice — the full run is ~14.5 trades/week. Corrected here.)*
4. **"STRENGTH" panel implies a gate that is OFF and was mathematically broken.** The ADX6 strength gate
   (`adx6_strength_soft=False`) is disabled, and the code itself documents the old formula cancelled ADX+slope
   (`margin=d*DI_diff`) — config.py:115, inference.py:167. The dashboard's "STRENGTH / H1 ADX / H4 ADX / DI" panel can
   read as an active strength score driving decisions. It is not.
5. **No provenance on any output.** No config-hash, git-commit, data-date-range, or train/test-cutoff stamp on the
   dashboard or on backtest CSVs (beyond a few config columns). You cannot prove *which* code+config produced *which*
   number — the exact condition that let past bugs (tp-equity #G, WFO-cache #H) hide.

### Top 5 highest-value improvements
1. **Feature-health strip** on the live board: for every feature feeding the current signal, show group + live-safe
   flag + leak-risk badge (Critical/High from the audit) + staleness. Kills risk #1 by making it visible.
2. **One backtest-integrity block** auto-written next to every run: data range, train/test cutoff, sizing mode
   (lot vs %), spread/commission/slippage, trade count, config-hash, git-commit. Kills #2, #5.
3. **Trade-count / confidence guardrail**: any weekly or variant result with <N trades or blank PF renders yellow/red
   with "low sample — not significant". Kills #3.
4. **Rename the panel** "STRENGTH" → "ADX/DI (raw, EWM-14, display-only — no gate active)". Kills #4.
5. **Split the board** into Live-Decision / Model-Health / Risk / Research(WFO). One page trying to be all six is why
   old vs new logic hides.

---

## 2. Ideal Dashboard Blueprint

AI-trading systems need **six** distinct surfaces. Do not merge them.

| Dashboard | Audience | Refresh | Purpose |
|---|---|---|---|
| **Live Decision** | operator (you) | 1s | take/skip *this* bar safely |
| **Model Health** | you / quant | per bar + daily | AUC, calibration, drift, feature staleness |
| **Risk** | you | 1s | exposure (bot+manual), daily floor, DD state, ruin |
| **Research / WFO** | you / quant | per run | baseline vs variant, OOS honesty |
| **Backtest Integrity** | you / quant | per run | provenance + leakage checks (pass/fail) |
| **Investor Summary** | client | weekly | clean, non-misleading equity + KPIs |

### Compulsory KPIs (every research/live-stats surface)
Total R · Net profit · Max DD (% and $) · Profit Factor · Win rate · Trade count · **Avg R & Median R** ·
Expectancy · Avg win / Avg loss · Risk per trade (bot **+** manual combined) · Max consecutive losses ·
Weekly/monthly consistency · Regime-wise R · BUY vs SELL R · Session/hour R · Exit-reason breakdown
(SL/TP/BE/TRAIL/manual/timeout) · Probability-bucket win rate · **Calibration curve** · OOS (WFO) R with **trade count** ·
Baseline-vs-variant delta.

### Charts / tables
Equity curve (with DD shading) · R-distribution histogram · calibration reliability plot · regime×direction heatmap ·
hour×weekday R heatmap · exit-reason pie · per-week WFO bar (colored by trade count) · feature-importance bar ·
open-trades table · signal log.

### Warning / validation panels
Trade-count guardrail · leakage badges · calibration-error banner · same-result-after-change detector ·
regime-drift banner · backtest-vs-live config-parity check · "let the trade complete" override lock.

### Filters
Date range · regime · direction · session/hour · mode (live/backfill/backtest) · probability bucket · win/loss.

---

## 3. Current Dashboard Findings

> Live panels present (from `dashboard.html`): ⚡ Open Trades · Signal History · 🧠 AI Learning · Closed Trades ·
> News Filter · System Settings · Model Stats · 🛡️ Account Health & Risk State · Protection · plus the big SIGNAL
> box, STRENGTH pills, market-structure, EV/GRADE, live price bar. Payload confirmed via `bridge_dashboard.py`.

### F-1 — Leaky feature surfaced as a valid signal — **Critical**
- **Evidence:** `corr_imp_ratio` classified **Critical / "Remove or fix" — centered swing detection uses future H4
  candles i+1..i+3** (Step-2 audit). It is in the current 36-feature model (Step-1 list) and appears on the board as
  `corr_ratio` inside `market_structure`. `in_range_phase` = **High** (possible future-H4 leakage) shows as `in_range`.
- **Why it matters:** the dashboard tells you "structure/corr looks like X" using numbers that partly know the future.
  In live that value is computed from *incomplete* H4 → its live meaning differs from its training meaning. Decisions
  and confidence built on it are contaminated.
- **Fix:** (a) fix the feature (confirmed-past-only swing) or drop it and retrain; (b) until then, badge these fields
  on the board as `⚠️ leak-risk` so they are never read as clean signal.

### F-2 — Backtest sizing/DD not equal to live — **High** (confirmed)
- **Evidence:** `step4_monthly_set1_36/backtest_summary_st-htf.csv`: `fixed_lot=0.01`, `risk_pct=3.0`, `max_dd_pct=0.9`,
  66 trades. Same `fixed_lot=0.01` in the WFO summary CSVs.
- **Why it matters:** the run sized at 0.01 fixed lot, **not** live 3%-of-equity → $-P&L, net-return-% and max-DD are
  not what live produces; comparing them to the live account misleads. R-metrics are unaffected.
- **Fix:** print the *single* active sizing mode explicitly; R-based metrics as the headline; show $-metrics only under
  the exact sizing used, labeled. Optionally re-run with 3%-risk sizing for a live-equivalent DD.

### F-3 — WFO looks "too good" while leaky features are still in the set — **High**
- **Evidence:** `wfo_part1_prune35/_WFO_SUMMARY.csv` TOTAL = 53 weeks, 768 trades, **+444.7R, pos=51 / neg=1**,
  avg **+8.39R/week**; `wfo_part2_composite` pos=52/neg=0 (+405.6R); `wfo_hmm_spec` pos=52/neg=0 (+470.4R). The Set-1
  feature list feeding these includes `corr_imp_ratio` (Critical) + `in_range_phase` (High).
- **Why it matters:** ~51–52 positive weeks out of 53 on gold M15 is not a realistic edge profile — it's the shape you
  get when a feature peeks at the future. With confirmed leaky features present, these OOS numbers cannot be trusted
  until the clean-set control (F-10) is run. *No surface warns about this; the cumulative-R headline invites trust.*
- **Fix:** never headline cumulative-R without the clean-set delta; add "positive-week ratio" as a leakage sniff
  (>90% → red); complete F-10 before quoting any WFO number as an edge.

### F-10 — The leakage control test is unfinished — **High**
- **Evidence:** ablation Set 2 (34 features = current minus `corr_imp_ratio` + `in_range_phase`) is *defined*
  (`STEP3_..._GUJ.md`) and recommended as the first backtest, but `step4_set2_clean_34/` contains **only**
  `week_2025-06-23_train.log` — one week's train log, no `_WFO_SUMMARY.csv`, no summary. The run was started and not
  completed.
- **Why it matters:** this is the single test that tells you whether the "too good" WFO (F-3) is real edge or leakage.
  Until it finishes, you are trading/reporting on numbers of unknown validity.
- **Fix:** finish the Set-2 clean WFO; compare pos-week ratio, total-R and PF vs Set-1. A large drop = leakage confirmed
  → fix/drop features and re-baseline before trusting any result.

### F-4 — "STRENGTH" panel implies an active, once-broken gate — **Medium**
- **Evidence:** `adx6_strength_soft=False` (gate OFF); config.py:115 + inference.py:167 document the old formula
  cancelled ADX+slope (`margin=d*DI_diff` → direction bias, not strength). Board shows STRENGTH/H1 ADX/H4 ADX/DI pills.
- **Why it matters:** reads as a strength score gating trades. It is only a raw display; the gate that *would* use it is
  off, and its historical formula was invalid. Users infer a control that isn't there.
- **Fix:** relabel "ADX/DI — raw EWM(14), display-only, gate OFF". (ADX-vs-MT5 methodology tooltip already added 07-09.)

### F-5 — Single board mixes six purposes — **Medium**
- **Evidence:** one page = live signal + model stats + risk + news + AI-learning; no research/WFO/integrity/feature panels.
- **Why it matters:** operational and research truth get read with the same trust level; old-vs-new logic drift hides in
  the mixing. Research currently lives in loose `.txt`/`.csv` with no dashboard — invisible to routine review.
- **Fix:** split per §2; at minimum add a read-only Research/WFO surface.

### F-6 — No provenance stamp on outputs — **High**
- **Evidence:** dashboard payload has `last_retrain_date`, `mode`; backtest CSV has config columns — but **no**
  config-hash, git-commit, data-range, or train/test-cutoff anywhere.
- **Why it matters:** you cannot prove which code+config made a number → the exact gap that hid tp-equity (#G) and
  WFO-cache (#H). Reproducibility is unverifiable.
- **Fix:** stamp every run + the live board footer with git-commit + config-hash + data-range.

### F-7 — Combined risk (bot 3% + manual 3% = 6%) may under-read — **Medium** **[needs-confirm]**
- **Evidence:** `risk_pct=3.0` and separate `manual_risk_pct=3.0` (config.py:224/229; two independent pools = 6% total).
- **Why it matters:** if the Risk panel shows only bot risk, true peak exposure is understated 2×.
- **Fix:** show combined open risk = bot + manual, and % of equity, prominently.

### F-8 — `win_prob` display vs calibrated `final_prob` — **Medium** **[needs-confirm]**
- **Evidence:** payload has both `win_prob` and `final_prob`; models are isotonic-calibrated (SYSTEM_OVERVIEW §B).
- **Why it matters:** if the board labels a *raw* score as "probability", the 52% threshold line is not what it seems.
- **Fix:** confirm the displayed number is the calibrated one; label it "calibrated win prob"; add a calibration panel.

### F-9 — Dead/misleading config still readable — **Low**
- **Evidence:** `use_time_filter` = "DEAD (0 readers)", `use_slot_day_filter=False` (config.py:176/276).
- **Fix:** ensure the board never shows a slot schedule / time filter as active when flags are off (FIX #B4 already did
  this for slots — re-verify after each change).

**Missing evidence for §3:** exact live→dashboard mapping of `final_prob` vs `win_prob`; whether the Risk panel already
sums manual+bot; the actual sizing used in the shipped backtest CSVs.

---

## 4. Mismatch Table

| Dashboard item | Current (implied) meaning | Actual backend meaning | Mismatch risk | Fix required |
|---|---|---|---|---|
| STRENGTH / H1·H4 ADX | trend-strength score gating trades | raw EWM(14) ADX display; ADX6 gate `= OFF`; old formula cancelled ADX/slope | Medium — false sense of an active control | Relabel "raw, display-only, gate OFF" |
| H1/H4 ADX value | matches MT5 chart ADX | EWM(span14) ≠ MT5 Wilder | Low (tooltip added) | Keep tooltip; note "engine method" |
| `corr_ratio`, `in_range` | clean live structure signal | leak-risk features (future H4 candles) | **Critical/High** | Badge leak-risk; fix or drop feature |
| Signal box vs Signal Log | same source | box=`d.last_signal` (backend freeze), log=`signals_all.csv` | Medium (07-09 frontend mirror added) | Verify parity after restart |
| Backtest $/DD | live-equivalent 3% risk result | likely 0.01 fixed-lot run | **High** | Print active sizing; R-first headline |
| WFO cumulative R | reliable OOS edge | ~4 trades/wk, PF blank | **High** | Trade-count coloring + significance line |
| EV / GRADE on SKIP | live trade quality | recomputed/ frozen from last signal | Low | Label "last signal" (hint added 07-09) |
| Risk panel | total account risk | may show bot 3% only (not +manual 3%) | Medium | Show combined 6% pool |
| `win_prob` | calibrated probability | possibly raw score | Medium | Confirm + label calibrated |
| Any output | reproducible | no hash/commit/data-range | High | Stamp provenance |

---

## 5. KPI Formula Table

| KPI | Correct formula | Current (found) | Status | Fix |
|---|---|---|---|---|
| Total R | Σ trade_R | present (backtest CSV `total_r`) | OK | keep; also show trade-weighted |
| Net profit | Σ $P&L after costs | present; sizing ambiguous | Unclear | tie to declared sizing |
| Max DD % | max peak-to-trough / peak ×100 | `max_dd_pct` (0.3 implausible) | Wrong/Unclear | recompute on live-equivalent equity |
| Profit Factor | Σwins$ / Σlosses$ | blank when losses=0 | OK-but-misleading | grey "n/a (no losses, N trades)" |
| Win rate | wins / trades | present | OK | always pair with trade count |
| Trade count | n | present | OK | promote to headline everywhere |
| Avg R | mean(R) | present (`avg_r`) | OK | keep |
| Median R | median(R) | not found | Missing | add (robust to outliers) |
| Expectancy | WR·avgWin − (1−WR)·avgLoss | not found | Missing | add |
| Avg win / loss | mean R\|win, mean R\|loss | not found | Missing | add |
| Max consec losses | longest losing streak | not found on research | Missing | add |
| Expectancy per regime | expectancy split by HMM state | `BY_REGIME` in backtest CSV | Computed, not surfaced | add regime table to board |
| Calibration | predicted vs realized win% per bucket | not found | Missing | add reliability curve + Brier |
| OOS R (WFO) | Σ next-week R, past-only train | present but no n-context | Unclear | add n + significance |
| EV (live box) | `wp·tp_m − (1−wp)·1`, tp_m=1.5 | matches backend | OK | show tp_m used |

---

## 6. Feature Transparency Audit

**Current model = 36 features** (35 `FEATURE_COLS` + `hmm_state`), model AUC 0.7047 (`model_meta.json`, 20260708_1515).
Six of the old "42" list (`trade_direction`, `h4_in_ob_zone`, `adx_trend_count`, `h4_trending_h1_aligned`,
`h4_ranging_h1_neutral`, `h4_h1_regime_score`) are **pruned** — dashboards/docs must stop referencing them as active.

- **Clearly explained (Step-1 table):** time features (`15_min_slot`, `slot_cos`, `day_of_week`), momentum
  (`move_1hr/4hr`, `momentum_aligned_*`), `price_vs_ema200`, news timers (`mins_to/since_next/last_3star`), ADX/DI set.
- **Unclear / need dashboard grouping:** `ts_bars_since_flip`, `ts_htf_agreement`, `h*_ob_strength`, `price_pos`,
  `body_pct` — meaning not visible to the operator.
- **Stale / leaky (must badge):** `corr_imp_ratio` (**Critical**, future H4), `in_range_phase` (**High**),
  `slot_win_rate` (**Medium**, outcome-derived prior — leaks if built on full dataset), OB-strength/S-R distances
  (**Low/Medium**, safe only if `confirm_datetime < t`). Source: Step-2 audit.
- **Grouping to add on the board:** price · trend · volatility · session/time · regime(HTF) · news · target-derived.
  For each feature show: group · timeframe source · closed-bar-only? · live-safe? · leak-risk badge · null/fresh.

**Missing evidence:** SHAP/contribution per live decision (not produced); with-volume vs without-volume and
with-ADX vs without-ADX ablation deltas (audit lists them as "ablation-test" TODO, results not yet in a dashboard);
per-decision top-feature list.

---

## 7. Backtest Integrity Checklist

| Check | Status |
|---|---|
| Data date range shown | **Missing** on board; partial in CSV (`from`/`to`) |
| Train / validation / test dates | **Missing** (WFO implies it; not surfaced) |
| Walk-forward windows | Present in `_WFO_SUMMARY.csv` (week_start/end) |
| Retraining cutoff date | **Not enough evidence** (in logs, not surfaced) |
| Bars used | **Missing** |
| Trades count | Present |
| Spread / commission / slippage | **Missing** from summary — must confirm applied |
| Max open trades | **Missing** |
| Lot / risk mode | Present but **ambiguous** (lot AND %) — F-2 |
| TP/SL/trail/BE config | Present (`tp_mode/sl_mode/trail_mode`) |
| Feature shift / leakage check | **Fail** — known leaky features active (F-1) |
| Leakage control run (clean-set) | **Started, unfinished** — `step4_set2_clean_34/` has 1 train log only (F-10) |
| Per-regime R breakdown | **Computed, not surfaced** — `BY_REGIME` block exists in `backtest_summary*` but no board panel |
| Duplicate-trades check | **Not enough evidence** (bridge_data guards dupes live; backtest?) |
| Missing-bars check | **Missing** |
| Timezone consistency | **Not enough evidence** (broker vs UTC handled live; backtest?) |
| News/calendar exclusion | Partial (news timers are features; explicit exclusion not shown) |
| Baseline fingerprint | **Missing** |
| Variant fingerprint | **Missing** |
| Config hash | **Missing** |
| Code version / git commit | **Missing** |

**Verdict:** integrity surface is largely **Missing**. Highest priority = sizing clarity (F-2), leakage badge (F-1),
provenance stamp (F-6).

---

## 8. Live Dashboard Design (ideal)

**Top bar:** symbol · broker time · spread · session · daily-risk state (bot+manual combined) · can-trade flag.

**Per-signal card (before you act):** time · direction · entry · SL/TP (price + $ + R) · risk $ · lot · **calibrated
win prob** · BUY-model prob · SELL-model prob · regime + regime confidence · top-3 features (with leak badges) ·
HTF alignment · ADX/DI raw (display-only) · SMMA/ratchet state · raw MT5 tick-volume (labeled raw) · spread ·
**take/skip reason** · conflict warnings.

**Conflict banners (must):** regime=Ranging but entry logic=Trending · BUY-model vs combined disagree ·
leak-risk feature drove confidence · spread too wide · pre-news window.

**Recent-performance strip:** last-20-trade WR/R, current daily headroom, open-trade status, **"🔒 let the trade
complete — do not override"** lock when a system rule owns the exit.

**Do NOT show clients:** raw model scores, feature internals, per-feature leak badges, AUC, WFO week noise, EV/GRADE
internals, dead config flags. Clients get §2 Investor Summary only.

---

## 9. Research Dashboard Design (ideal)

**Per experiment row:** name · datetime · **git-commit + config-hash** · baseline result · variant result ·
ΔR · ΔProfit · ΔMaxDD · ΔPF · ΔWR · ΔTradeCount · **common vs unique trades** · entry-quality change ·
exit-reason shift · regime-wise Δ · BUY/SELL Δ · session Δ · calibration Δ · WFO-week stability ·
bootstrap CI / p-value (if available) · **Pass/Fail**.

### Detecting fake improvement (SMMA case specifically)
When SMMA shows +R, force the board to decompose it — do not accept the headline:
1. **Common-trade management gain** — trades taken by *both* baseline and variant; compare only their exits/R.
2. **True new-entry-quality gain** — trades *only* the variant takes; their standalone expectancy.
3. **Avoided-bad-trades gain** — trades baseline takes that variant skips; were they net losers?
4. **Composition effect** — did regime/session mix simply shift? Normalize by regime/session before crediting SMMA.
Only #2 and #3 (net-loser avoidance) are "real edge". If +R is mostly #1 or #4, label it **management/composition, not
entry quality**. Show all four bars side-by-side.

---

## 10. Fix Priority Roadmap

### Immediate (1–2 days)
- **Finish the clean-set (34-feature) WFO control** — the one test that proves whether the "too good" WFO is real
  edge or leakage; currently started but unfinished (F-10). Do this *first* — most other trust decisions depend on it.
- Badge `corr_imp_ratio`/`in_range_phase` (and any leak-risk field) on the board as `⚠️ leak-risk` (F-1).
- Print the single active sizing mode on every backtest summary; make R the headline (F-2).
- Relabel "STRENGTH" → "ADX/DI raw, display-only, gate OFF" (F-4).
- Add trade-count to every WR/PF headline; grey PF when losses=0 (F-3).
- Show combined bot+manual open risk on the Risk panel (F-7).

### Short-term (1 week)
- Provenance stamp (git-commit + config-hash + data-range) on live footer + all run outputs (F-6).
- Trade-count / low-sample guardrail with color rules (§11 warnings).
- Confirm and label calibrated `win_prob`; add calibration reliability panel (F-8).
- Add Median R, Expectancy, Avg win/loss, Max-consec-loss, regime/direction/session tables (§5 Missing rows).

### Medium-term (2–4 weeks)
- Fix or drop the leaky features and retrain; re-run WFO past-only; verify no same-result bug.
- Build the separate Research/WFO + Backtest-Integrity surfaces (§2, §7).
- Add per-decision top-feature (SHAP) + ablation results (volume on/off, ADX on/off) to Model-Health.
- Investor Summary surface with the "do-not-show" list enforced.

---

## 11. Warning System (red/yellow/green)

| Rule | Yellow | Red |
|---|---|---|
| Trade count (window) | < 30 | < 10 |
| PF with no losses | losses=0 & trades<20 → "n/a" | — |
| OOS >> train | OOS_R/train_R > 1.3 | > 1.8 (leakage) |
| Same result after param change | Δ fingerprint but ΔR≈0 | identical hash+result (bug) |
| Regime distribution shift | >20% vs baseline | >40% (drift) |
| Calibration error (Brier / ECE) | ECE > 0.05 | ECE > 0.10 |
| Variant +R but +DD | ΔR>0 & ΔDD>0 | ΔR>0 & ΔDD>+50% |
| Metric formula unknown | — | always red until documented |
| ADX score cancels ADX | — | red (the ADX6 old-formula case) |
| Live feature unavailable at entry | — | red (leakage) — block or flag |
| Leak-risk feature in active model | High-rated | Critical-rated (corr_imp_ratio) |
| Backtest sizing ≠ live | mode mismatch | $/DD compared cross-sizing |
| Spread/cost not modeled | costs=0 in backtest | red until confirmed |

---

## 12. Final Recommendation

- **Should you trust the current dashboard?** For *operations* (is a trade open, where's my stop, am I within daily
  risk) — **yes, mostly**. For *decision quality and research* — **no**, until leakage is badged/fixed, sizing parity
  is proven, and OOS shows sample size.
- **Before trading decisions:** F-1 (leak badge), F-2 (sizing clarity), F-4 (STRENGTH relabel), F-7 (combined risk),
  F-8 (calibrated-prob confirm).
- **Before showing an investor/client:** everything above **plus** F-3 (sample-size honesty), F-6 (provenance), and the
  §8 "do-not-show" enforcement. Do not show a client a 100%-WR-on-4-trades week.
- **Next Step-1 task (single, concrete):** add the **feature-health strip** to the live board — for each of the 36
  active features show `group · timeframe · live-safe? · leak-risk badge · fresh/null`, seeded from the Step-1/Step-2
  audit tables (`corr_imp_ratio`=Critical, `in_range_phase`=High, `slot_win_rate`=Medium). It is the highest
  risk-reduction per hour and needs no retraining — pure transparency.

---

*Evidence base: `engine/dashboard.html`, `engine/bridge_dashboard.py`, `engine/config.py`, `engine/inference.py`,
`docs/SYSTEM_OVERVIEW.md`, `audit/feature_audit_20260709/docs/STEP1_/STEP2_/FEATURE_LEAKAGE_AUDIT_GUJ`,
`.../backtest/results/*/_WFO_SUMMARY.csv`, `.../backtest_summary_st-htf.csv`. Read 2026-07-09. Items marked
**[needs-confirm]** were not independently re-run.*
