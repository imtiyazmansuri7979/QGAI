# Entry-Timing Redesign — Trend-Following Pullback Entry (ATR-free)

**Status:** PARKED (2026-07-03, Imtiyaz chose baseline). Code fully built + parity-verified but the flag
`trend_pullback_entry` stays **OFF** → live = baseline, no change, fully reversible. **Sweep-A TEST (2 wk):**
no combo beat baseline (baseline +12.8R/14tr vs best pullback +7.7R/5-7tr); the pure block cut winners in
that window. FULL-year sweep NOT run. To revisit: run `_FULL.bat`, or pivot to GENERATE pullback entries
(a block-only filter can only remove trades, never re-time them). See §Revisit below.
**Date:** 2026-07-03 · **Author:** Claude (with independent Fable-5 review) · **Owner:** Imtiyaz

---

## ગુજરાતી સારાંશ (short)
Entry અત્યારે 100% ML `win_prob` gate પર છે → `dir_prob` breakout candle પછી જ ફરે → **top પર entry**
(02–03 જુલાઈ gold rally માં પુરવાર). Permanent fix = **Direction અને Timing અલગ કરો**:
HTF SMMA/ADX trend alignment (leading) દિશા નક્કી કરે, અને entry **ratchet line પર shallow pullback +
reclaim** પર થાય (breakout પર નહીં). Anti-chase = **`ts_line_dist_pct`** (ATR-free, પહેલેથી છે). ML =
quality-veto (re-trained). બધું existing features પર — નવો indicator જોઈતો નથી. Live જતાં પહેલા WFO +
backtest==live parity + total-R માપો.

---

## 1. Problem & evidence
Overnight gold rally 2026-07-02 → 07-03 (`engine/logs/signals_all.csv`):

| Time | Price | dir_prob | win_prob | Signal |
|------|-------|----------|----------|--------|
| 20:00 → 03:45 | 4106 → 4147 (slow grind +40) | ~0.32–0.37 | ~0.32 | **all SKIP** (< 0.45) |
| **04:00** | **4176 (+29 in ONE bar)** | **0.625** | **0.5545** | **BUY** |
| 04:15 | 4187 (near top) | 0.625 | 0.63 | BUY |

HTF DI was already bullish hours earlier (H4 DI_diff +24, PlusDI 35 vs MinusDI 11). All-TF ADX slopes
rising. Yet the bot only signalled BUY on the breakout candle = **buying the top**.

> NOTE: those 04:00 rows are `BACKFILL` (bot offline ~18:15 Jul-2 → ~08:00 Jul-3, then replayed). No live
> trade was executed. **Owner confirmed (2026-07-03): observed in the signal-log/dashboard, NOT a live
> trade.** The timing flaw is real regardless — it is what the engine *would* have signalled.

## 2. Root cause
Entry is gated purely by ML win_prob (`engine/inference.py:733`):
`final_prob = 0.70·combined + 0.30·(state_prob + dir_prob)`, threshold 0.45 (regime-adjusted).
`dir_prob` is an XGB classifier whose strongest feature is a big printed candle → it is **coincident /
breakout-confirming**, not leading. The architecture collapses two different questions —
*"which way?"* (answerable hours early from HTF SMMA/DI) and *"is NOW a good price?"* — into one scalar,
so the gate can only open after the breakout. Threshold/filter tuning cannot fix a lagging trigger; the
fix is structural.

## 3. Ground-truth: everything needed ALREADY EXISTS (no new indicators)
Verified in `engine/features.py` (`get_trend_signal_features`, lines 1049-1087) and `engine/regen_adx_asof.py`:

| Need | Existing feature | Meaning |
|------|------------------|---------|
| Direction / alignment | `ts_htf_agreement` | trend_m15+h1+h4, −3..+3 (±3 = all TF aligned) |
| HTF trend (EA rule) | `ts_adx_switch_trend` | H4 trend if H4 ADX≥19 else H1 trend |
| Trend freshness | `ts_bars_since_flip`, `ts_flip_recent` | bars since SMMA flip / flip within 3 bars |
| **Anti-chase / pullback** | **`ts_line_dist_pct`** | **signed % dist of price from active ratchet line** `(price−line)/price·100` |
| ADX rising | `h1_adx_slope`, `h4_adx_slope` | ADX change over 4h (>0 = strengthening) |
| Trend persistence | `adx_trend_count` | consecutive trend bars |
| DI alignment | `H1_DI_diff`, `H4_DI_diff` | +ve = bullish |

**Key resolutions:**
- **ATR-free by construction.** ATR was already removed from QGAI (`features.py:134`, 2026-06-19 —
  "volatility captured by the 2-SMMA band"). The anti-chase gate uses `ts_line_dist_pct` (price-to-SMMA-line
  distance), so no ATR anywhere. Consistent with the codebase.
- **`band_rel` is NOT the anti-chase measure.** Verified `regen_adx_asof.py:86,107`:
  `band_rel = band_width / 30D-mean(band_width)` = a *volatility-regime* ratio, not price-to-line distance.
  (Fable-5's first pass assumed otherwise — corrected.) Use `ts_line_dist_pct` instead.

## 4. New architecture — split DIRECTION from TIMING
```
[Direction/bias]  deterministic, LEADING
   long-bias  if  ts_adx_switch_trend == +1  AND  ts_htf_agreement >= +2
                  AND (h4_adx_slope > 0 OR h1_adx_slope > 0)      # trend real & strengthening
                  AND HMM state != Ranging                        # existing range-veto
   (short-bias = mirror)                                          # counter-trend already skipped
        │
        ▼
[Timing/entry]  PULLBACK-to-line, NOT breakout  (trend-following = shallow dips only)
   arm when bias set; ENTER on the RECLAIM bar:
     |ts_line_dist_pct| <= PB_NEAR%           # price pulled back near the ratchet line
     AND close back on trend side of the line # "reclaim", 1-bar confirmation (kills whipsaw)
     OR  2-3 tight/inside bars near line       # lateral pause counts as a pullback
        │
        ▼
[Anti-chase guard]  ATR-free
   BLOCK entry if  ts_line_dist_pct > CHASE_MAX%   (price already stretched above line = top)
        │
        ▼
[Runaway safety]  don't miss never-pullback trends (structural, NOT a timer)
   if bias persists and no qualifying pullback, allow ONE continuation entry at HALF risk
   only on a micro-pause (1-2 bar stall / new Donchian(N) high after a small shelf), still
   CHASE_MAX-gated.  Drop entirely if WFO shows net-negative R.
        │
        ▼
[ML win_prob]  QUALITY-VETO only (re-trained on the new pullback-entry population)
   block if final_prob < veto_thresh; it no longer decides TIMING.
        │
        ▼
[Exit]  unchanged — existing SMMA ratchet/trail + ratchet_tp_regime.
   Entry & trail share the SAME line ⇒ minimal entry MAE, trail "in position" from bar 1.
```

### Fable-5 review refinements (folded in)
- Enter on **reclaim (close back on trend side)**, not the raw touch → kills choppy-trend whip stop-outs.
- Accept **shallow pullback OR tight consolidation** (some trends pause sideways, don't dip).
- Runaway continuation must be **structural (micro-pause), not an N-bar timer** (a timer buys the most
  extended point). Keep at half risk; it's insurance, drop if WFO says net-negative.
- **One-position-per-direction lock**; **suppress fresh pullback entries once the ratchet has advanced
  past entry** (trend mature → adding at worse R than the position already held).

## 5. Starting parameters (to be WFO-tuned, not final)
| Param | Start | Meaning |
|-------|-------|---------|
| `PB_NEAR%` | 0.05–0.10 | max |dist| from line to count as "at the line" (pullback) |
| `CHASE_MAX%` | 0.20–0.30 | block entry if price > this far above line (anti-chase) |
| `htf_agreement_min` | {1, 3} | 1 = dominant/net trend only (trades when TFs disagree); 3 = all M15+H1+H4 aligned. (2 is degenerate — agreement ∈ {-3,-1,1,3}.) |
| `adx_switch_level` | 19 (existing) | H4-vs-H1 confirmation switch |
| `runaway_bars` | 8–12 | bias-persist window before allowing half-risk continuation |
| `runaway_risk_mult` | 0.5 | half risk on continuation entries |
| `veto_thresh` | tune | ML quality-veto cutoff on new entry population |
| `donchian_N` | 20 | lookback for runaway breakout + validation percentile |

All behind a single reversible config flag, e.g. `filters.trend_pullback_entry: bool = False`
(default False = current behaviour; flip to True to test). Mirror of the existing reversible-flag pattern.

## 6. Backtest == live parity checklist (do BEFORE trusting any number — min 4 rounds)
- [ ] Entry uses last **CLOSED** bar per TF (no lookahead) — reuse `get_trend_signal_features` cutoff logic.
- [ ] `ts_line_dist_pct` computed identically in backtest and live (same ratchet line, same `price_now`).
- [ ] Reclaim = close of the CLOSED bar, not the forming bar.
- [ ] Entry SL / trailing line / flip / TP / buffer identical to LIVE config.
- [ ] HMM range-veto + `skip_counter_trend_fade` still applied, same order as live.
- [ ] Lot/risk (3%), half-risk multiplier applied same in both.
- [ ] ML model used in backtest == the RE-TRAINED model (not the old one).
- [ ] No WFO cache staleness (precedent BUG_LOG #H), no tp-equity bypass (#G).

## 7. WFO / validation plan
1. **TEST-RUN FIRST** (house rule): `run_wfo.py --weeks 2` — verify no crash, variant lines print, `.txt`+`.csv`
   land in the run folder (one-folder-per-run). Build a `*_TEST.bat`. Only then the full run.
2. Full **WFO** old→new, backtest==live parity, ETA/countdown line per week (existing in `run_wfo.py`).
3. **Metrics (judge on total R / $ — PRIMARY):**
   - Total R / $ vs current  ← accept only if **higher**
   - **Entry-location percentile** within the following 8h range (current ≈ 100% = top; should drop hard)
   - MAE-at-entry distribution (should shrink)
   - % of HTF-trend windows captured (should not collapse)
   - flip-count / stop-out rate as diagnostics (NOT the acceptance criterion)
4. **Targeted replay of 2026-07-02/03** — confirm entry now lands in the 4106–4147 grind, not 4176–4187 top.
5. **Reject** any variant that lowers total R, however much cleaner the entries look.

## 7b. Parameter SWEEP — decide the winner (owner: total-R wins, we accept)
Owner approved the starting ranges (2026-07-03) and wants the **final combo decided by a sweep**, accepted
purely on **total R / $**.

**Isolate variables first (house rule: don't add variables mid-validation).**
- **Sweep A — core entry-timing only** (ML-veto OFF, runaway OFF). Proves the timing change alone.
  Grid (within approved ranges):

  | Param | Values | n |
  |-------|--------|---|
  | `PB_NEAR%` | 0.05, 0.075, 0.10 | 3 |
  | `CHASE_MAX%` | 0.20, 0.25, 0.30 | 3 |
  | `htf_agreement_min` | 1, 3 | 2 |  ← 1=dominant-only (handles "TFs not all aligned"), 3=all-aligned

  = **18 combos + baseline (current live)** = 19 WFO runs, all backtest==live parity, one-folder-per-run,
  `_SWEEP_SUMMARY.csv` (total R, PF, WR, MaxDD, entry-location percentile, MAE-at-entry) per combo.
- **Sweep B — refine the Sweep-A winner** by adding: ML re-trained quality-veto (on/off + `veto_thresh`),
  and runaway continuation (on/off). Only around the winning region.

**Acceptance:** the combo with the **highest total R** that also **beats baseline** wins and is adopted.
Tie-break by lower MaxDD, then better entry-location percentile. Reject the whole change if NO combo beats
baseline total R.

**TEST-RUN FIRST:** `Run_EntrySweep_TEST.bat` = 1 combo × `--weeks 2` (crash/columns/output check) before the
full 19-run sweep. ETA/countdown line per run (reuse `run_wfo.py` per-week ⏱).

## 8. Rollout
- Config flag OFF by default → merge safely.
- DEMO first (house rule), then live at 3% only after WFO + demo both beat current on total R.
- Reversible: set flag False to revert instantly.
- On adoption: append dated entry to `docs/FIXES_CHANGELOG4.md`, update `docs/QGAI_GUIDE.md` §4 config + §5
  status, move the TASKS.md row to DONE.

## 9. Risks / open questions
- **Re-train dependency:** the ML veto must be re-trained on the new entry population before WFO is
  trustworthy — otherwise old-model bias contaminates results.
- **Confirm live vs backfill:** was the top-entry seen in a real live trade or only in the backfilled log?
- **Sideways-pause detection** ("tight/inside bars") needs a precise, lookahead-free definition.
- **Runaway path** may be net-negative on gold; treat as optional, gated by WFO.
