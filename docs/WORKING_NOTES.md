# QGAI — Working Notes (where we are right now)

**Updated:** 2026-07-08 · **Use:** live status / handoff. If the session breaks or
Imtiyaz picks up, start HERE, then RULEBOOK.md → SYSTEM_OVERVIEW.md → FIXES_CHANGELOG.

---

## ▶ CURRENT STATE (2026-07-07 — major session; full detail → FIXES_CHANGELOG4.md + TASKS.md)

**Live bridge restarted 17:38 with today's changes. Open bot trade #1550707233 BUY 11.34lot
@4149.25, big profit (~+$16k on $1.1M demo), vSL 4122.79 trailing — vSL persist restored it on
restart (the S-4 bug fix, verified live).** Accounts: primary #25334572 VantageDemo $1.1M,
secondaries VantageCentLive $2,022 + OneFunded $9,895 (funded).

**Banked today:**
- **CTF-OFF** live (`skip_counter_trend_fade=False`): +34.3R Path-A (+9.8%).
- **Feature PART 1**: dropped 6 dead EA-combo features -> static full BT **+393.4R**,
  then weekly-retrained WFO **+444.7R** (**+51.3R / +13.0% WFO lift**, 51/53 positive weeks,
  worst week -0.4R). New honest WFO baseline = **+444.7R**. Model now 35 core features
  (+ `hmm_state` in model metadata = 36).
- **Fable-5 system audit (16 findings)**: fixed 9 — vsl_persist.py, dd_brake.py (live DD brake,
  PER-ACCOUNT after a live bug), picker (M11), checkpoint-sig (H8), ADX-gate live-wire (H9),
  replay-ADX as-of (H6), config cleanup (M14), reversal-gate flag (S1), news staleness (S2/false-pos).

**⚠️ Open items:**
- **PART 2 in test**: ADX 10 raw → 5 tanh composites (`QGAI_ADX_MODE=composite`), retrain+WFO gate
  ≥ +444.7R. Fable P(beats)≈30% (likely wash; value = stability). Bats: `Run_Part2_ADXComposite_*`.
- **DD brake bug legacy**: pre-restart trade #1550707233's secondary replicas were rejected → Imtiyaz
  opened manual trades in slaves; bot won't auto-close those (magic 0). Next NEW trade verifies the
  per-account fix.
- **NEXT (Fable's #1)**: FIX-3 parity — live↔backtest entry-overlap ~12%; the real blocker before
  chasing the +20-50% goal via max_open=2.

**⛔ LESSON (Imtiyaz 2026-07-07):** confirm before changing ANY risk/trading/config setting. Claude
"fixed" `manual_risk_pct` 6→3 (a Fable-flagged "footgun") — it was Imtiyaz's INTENTIONAL 6% for
open-manual-trade; reverted. Audit findings = hypotheses to raise, not licence to change.

---

## ▶ PRIOR STEP (2026-07-01 — big cleanup/fix day, full detail in TASKS.md DONE table)
**Live bridge is running with one LEFTOVER trade (#1519547791, opened 2026-06-30 22:15, BUY, still open).**
Today's work, newest first (full write-ups → `TASKS.md` DONE table, `BUG_LOG.md` for bug detail):
- **backtest_replay.py: checkpoint/resume + console-buffering fix (built, untested end-to-end).** A stopped/
  interrupted backtest used to lose ALL progress (checkpoint file existed in code but was dead/unused).
  Now auto-saves every 500 bars + on Ctrl+C, keyed to an exact config signature (never resumes a mismatched
  run — same paranoia as Bug H). `--no-resume` forces fresh. Also fixed: console looked frozen for long
  stretches — `stdout`/`stderr` weren't line-buffered, so `print()` sat unflushed. Progress now every 100
  bars with `flush=True` + `line_buffering=True`; `PYTHONUNBUFFERED=1` added to the two `Run_Live_Buffer_015`
  bats. ⚠️ Could NOT get an automated `py_compile` this session (bash sandbox mount stuck serving a 3+ hr
  stale cached copy — confirmed via `stat` mtime) — verified by full manual line-by-line Read-tool review
  instead. **Spot-check this on the next backtest run.**
- **`Run_Live_Buffer_015_CSV.bat` (full 1-year, $10k/3% dynamic compounding, both trade+signal CSV) —
  deep parity-checked against live config (buffer/TP-regime/HTF-sync/entry-SL/risk%/no-lookahead, all ✅)
  before trusting it, per the CLAUDE.md 4-round rule.** 1-week smoke test passed first (`_TEST.bat`,
  13 trades/WR69%/PF9.36 — too small a sample to mean anything, just confirmed no crash). Full-year run
  was kicked off by Imtiyaz, in progress as of this note.
- **vSL-recovery bug found + FIXED:** Imtiyaz flagged leftover trade #1519547791's vSL (4016.42) not
  matching the live H1 line (~3975). Root cause: `bridge_core.recover_open_trades()`'s fallback path used
  a hardcoded `sl_dist=15.0` guess whenever a trade's comment has no embedded VSL/SL (now the norm — clean
  brand-tag comments) AND it has no broker-side SL (pure-virtual design) — discarding the REAL vSL on every
  restart. Deeper bug found alongside it: `bridge_core.py`'s close-call-sites did `del virtual_trades[ticket]`
  **unconditionally**, even when the close FAILED — so a stuck trade silently dropped out of live monitoring
  after ONE failed attempt (contradicting the "bot will keep retrying" alert text). **FIXED:** `_close_position()`
  now returns True/False; callers only drop the ticket on confirmed success — a failed close now correctly
  keeps retrying every tick with the REAL vSL intact, no restart-and-lose-progress needed.
- **NEW: graduated stuck-trade excess-hedge (Imtiyaz's idea) — built, OFF by default (`leftover_excess_hedge_enabled`).**
  Instead of freezing the FULL lot the instant a stuck trade's close fails (existing `stuck_trade_hedge_enabled`,
  full-lot, still there as fallback), stretch risk from `risk_pct` (3%) up to `leftover_risk_cap_pct` (6%) and
  hedge ONLY the excess lot once unprotected slippage (price past the real vSL while close keeps failing)
  exceeds that stretched band. Tops up incrementally. Needs Imtiyaz's go-ahead + a real test before enabling.
- **bridge_main.py mojibake cleanup** (targeted, glyph-by-glyph per Imtiyaz's explicit picks — NOT a blanket
  sweep, he asked to revert a first over-broad attempt): 💓⚙️──👁📋📊🚀💰✅—· now clean in their log.info() lines;
  everything else (⚠️❌🔄🗓⛔❓⏭🔚🛑) deliberately left as-is per his instruction.
- **Stuck-trade manual-protect feature (from end of prior session) — ENABLED, still not live-fire-tested.**
- Win_prob-freeze fix, 10027-close-fail alert, dashboard.html fixes (dup canvas ID, missing MODEL box),
  2-decimal % formatting everywhere — all from earlier in the same 2026-07-01 session, see TASKS.md.
**TO-DO (Imtiyaz):** watch the full-year `Run_Live_Buffer_015_CSV.bat` finish → report back. Decide on the
graduated excess-hedge (enable + test?). Restart the bridge to pick up the vSL/retry-loop fix.

---

## ▶ PRIOR (2026-06-29 — RESTART + VERIFY all of today's changes)
**Lots of live-code changed 2026-06-29 (Anisa). RESTART `1_Start_Trading.bat` + `5_Dashboard.bat`, watch
startup for errors; if any error → tell Claude (revert).** Today's work (all in TASKS.md DONE 06-29):
🔴 **L8 false-halt bug FIXED** (balance-flow used local time → counted lifetime deposits → halted all day);
offline-closed-trade outcome backfill; signal-log dedupe + equity + $-move columns; **L9 complete signal log**
(`signals_complete.csv` = full-history regime + live, dashboard reads it; bat `Run_BuildSignalLog.bat`);
**L11 gap-backfill** (overnight signals → dashboard); **dashboard signal-log overhaul** (one log: date+time
sorted, price/win%/regime/H4-RANGE/BW%/lot/WIN-LOSS-REAL/$move/equity/reason; removed dup table + SLOT
DISCOVERY; kept chart); **L13 Manual-trade Manager BUILT + ENABLED on DEMO** (`bridge_manual.py`): final design = combine ALL
manual trades (magic 0) into ONE net position → ONE **ratcheting vSL** (2-SMMA H1 line), trailed as a
VISIBLE broker SL on every leg, breach→close all; SEPARATE 3% risk pool (`manual_risk_pct=3`, independent
of bot's `risk_pct=3` → 3%+3%=6% total) broker-SL backstop + excess-hedge; target-TP 2%→
close all; NO flip-hedge (approach A); DEMO-primary only (cent rejected — mirror-trade conflict);
L8-isolates manual P&L. `manual_manager_enabled=True` for the demo test (verified live: detects existing
trades, sets 3% SL + vSL). Bot entry-guard (`count_open()`) only counts magic 202600, so a manual BUY does
NOT block a system BUY — they run as two independent pools (room to trade). ⚠️ `bridge_manual.py` got
mount-write null-byte corruption twice — caught +
stripped both times (would crash import); if you ever see "null bytes"/import error, re-strip it.
Config: added cent-live 29453256 (pass filled, connected), disabled TradeQuo 125926628.
**TO-DO (you):** fill 29453256 pass · rotate 25334572 pass (leak) · DEMO-test L13 before enabling.
**Then validation (parked):** P2b real-3%-DD sim · demo forward-test 1-2 wks · (optional) global WFO re-run.

---
## ▶ (2026-06-27) — WFO test caught a TP-bypass bug → bats FIXED, re-test next
**🔎 WFO smoke-test (3 wk) found a real bug:** global TP and regime-TP came out IDENTICAL (+20.3R).
Cause: the WFO bats passed `--tp-equity 3`. In `backtest_replay`, when `tp_equity_pct>0` the equity-TP path
runs and **completely skips the price-based TP cap** (`tp1`/TPCAP) — and under fixed-lot 0.01 the equity-TP
($300 on $10k) NEVER fires → so NO TP cap acted at all (global 1.0% AND regime both inert) → exits were
flip/trail/SL only, and it didn't match LIVE (live = `tp_equity_pct=0` + price cap 1.0%).
**FIXED:** `Run_WFO_FULL.bat`, `Run_WFO_TPREGIME.bat`, `Run_WFO_TEST.bat` now use `--tp-equity 0` → the
config price TP cap (1.0% global / regime-switched) is used → matches live AND regime-TP actually acts.
(`Run_TP_Regime.bat` was already correct — no `--tp-equity` → price cap active → that's why its backtest won.)
**✅ RE-TEST PASSED (3wk, `--tp-equity 0`):** global +22.0R/20tr vs regime +20.3R/18tr — they now DIFFER
and TPCAP exits appear → TP cap live-faithful again. (3-wk/18-20 trade sample too small to judge regime vs
global; global slightly ahead here is meaningless — the FULL WFO decides.)
**⚠️ FIRST full WFO run was STALE** — every week showed `CACHED` and returned +143.9R = the OLD pre-relabel
/ `--tp-equity 3` baseline (week_*.json mtime 2026-06-20). run_wfo's cache keys only on the week file
existing, ignoring model/flags (BUG_LOG #H). Stale `wfo_results/` archived → `_archive/wfo_results_STALE_preRelabel_tpEq3`.
**NEXT (re-run FRESH):** `Run_WFO_FULL.bat` (now computes all 41 weeks fresh on the relabeled model + tp-equity 0)
+ `Run_WFO_TPREGIME.bat` (wfo_tpregime is new = fresh). ~1.5-2 hr each. Then "WFO done" → compare regime vs global.
**Before any future WFO re-run after retrain/flag-change: clear the results-dir first (cache won't auto-invalidate).**

### ✅ FRESH global WFO done (2026-06-27, relabeled model, --tp-equity 0, live-faithful)
**+321.4R / 725 trades / PF 3.28 / WR 55.9% / 41-of-41 green weeks / avg +7.84R/wk.** avg win +1.14,
avg loss −0.44 (losses bounded −1R; only 18 full SL). Exit mix FLIP 404 · TPCAP 194 · TRAIL 109 · SL 18.
This is MUCH stronger than the old broken +143.9R (which had NO TP cap) — the relabel + working price TP cap
(1%) is the gain. 41/41 green is real but a fixed-lot smoothness artifact (TP locks wins, ratchet cuts losers
tight, low variance); **3% dynamic sizing will have red weeks + real DD** → quantify in P2b ($10k sim).
Mild in-distribution optimism (model trained on relabel-under-this-exit) → full-history (L1) + DEMO are harder.
### ✅ 2026-06-27 (late) — REGIME-ADAPTIVE TP ADOPTED + WIRED LIVE (P3 done)
On the CORRECT (HTF, live-matched) WFO, regime-adaptive TP WON: **regime +266.1R / PF 3.35 / WR 60% /
39-41 green / $10k-3% Max DD ~18.7%** vs global +254.9R. (The earlier "regime rejected" was on the invalid
M15 run — REVERSED.) Ranging is the driver (avg +0.884R via wide TP 2.0). **Wired into live:**
`config.py ratchet_tp_regime=True` (reversible) + `bridge_core.execute()` switches the TP cap by HMM state
(Rng 2.0 / Trn 1.0 / Vol 0.8) — matches the validated backtest. **Restart `1_Start_Trading.bat` (DEMO) to load.**
Caveat: 10/10 green months = in-distribution optimism; real DEMO/future will have red months + higher DD.
**NEXT:** DEMO forward-test the full validated config (relabel + HTF + regime-TP, 3%). Watch equity.

### ⚠️ 2026-06-27 — ALL prior WFO INVALID (M15, not HTF). RE-RAN after Bug F/J fix.
The earlier "+321R global / +307R regime" used `stop-trail=line` (M15 trail+flip) — NOT live HTF. Voided.
Backtest now config-aware HTF (BUG_LOG #F/#J). Stale runs → `_archive/WRONG_preHTFfix_20260627`.
**✅ NEW global WFO (HTF, live-faithful, verified fresh + st-htf suffix): +254.9R / 556 trades / 39-of-41
green / avg +6.22R/wk.** Lower than the inflated M15 +321R (HTF entry SL is wider → fewer trades, 2 red
weeks = realistic) — but now it actually matches what LIVE runs. PF pending (run Run_WFO_Analyze — ALL_OOS
combine not auto-done). **Regime WFO (wfo_tpregime, HTF) RUNNING — compare when done.**

### ~~Regime WFO done — REGIME-ADAPTIVE TP REJECTED~~ (THIS WAS THE INVALID M15 RUN — see above; redoing)
Global +321.4R / PF 3.28 / 41-green  vs  Regime +307.3R / PF 3.10 / 39-green. Regime WON in-sample (+20%)
but LOSES OOS → that in-sample edge was overfit/cherry-pick (exactly the flagged risk). **Decision: keep
global TP 1.0% (config already there), do NOT wire regime-TP live → P3 CANCELLED.** Relabel KEPT (sound +
strong OOS). Validated win = relabel + global price TP cap (PF 3.28 OOS), far above the old broken +143.9.
### ✅ P2b done — $10k 3% dynamic sim (on wfo_results OOS log) — but OPTIMISTIC, treat as a CEILING
Max DD: 1%→4.6% · 2%→9.1% · **3%→13.4%** (no daily-ratchet halt modeled → real a bit lower). Returns are
compounding fantasy (3% = +1,046,793%) — IGNORE; judge by DD + smoothness only. 10/10 green months, worst
month +60%, 41/41 green weeks = **"too smooth" = in-distribution optimism**: the model's labels were generated
under THIS exact exit (relabel) and the WFO replays the same exit, so it predicts exactly the game it's scored
on. Live has slippage/spread/execution gaps + a different future → **expect real losing weeks/months and higher
DD.** Earlier "28-39% DD" was the OLD no-TP-cap strategy; the new one is genuinely smoother but these figures
are an upper bound.
**NEXT (P3' = the REAL test):** DEMO forward-test the relabeled + global-TP model on UNSEEN future data; also
run full-history L1 (2022-24 unseen) for an honest out-of-distribution read. Consider starting live at 1-2%
risk (DD 4.6-9.1%) given the optimism. Live config is already correct (global TP 1.0, relabeled trades_file).
**⚠️ Note:** the old "OOS PF 1.55" baseline used `--tp-equity 3` → it was a no-TP-cap flip/trail strategy,
NOT today's live (price TP 1.0%). New WFO (`--tp-equity 0`) is the live-faithful number — expect different.

## ▶ PRIOR (2026-06-27 — P1 RETRAIN done)
**✅ P1 done: model retrained on the RELABELED data** (n_trades 2,743, win_rate 37.7%, ts 20260627_0517).
**⚠️ AUC DROPPED on the new (live-exit) labels:** Main 0.759→**0.679**, BUY 0.80→**0.672 (−0.13!)**,
SELL 0.747→0.751 (~same). Likely HONEST not bad — the live exit (ratchet+HTF flip+TP cap) outcome is
path-dependent and harder to predict than the old static-exit label; the old 0.80 was partly illusory
(predicting a target that didn't match live). BUT could also be added noise → **AUC does NOT decide**.
**The decider = P2 OOS PF.** If OOS PF ≥1.55 holds/improves → keep relabel; if it drops → revert
`config.py trades_file` to the old `Back_testing_data_final_cleaned.xlsx` (1 line). Watch BUY especially.
**NEXT:** run P2 — `Run_WFO_FULL.bat` (global TP, relabel baseline) + `Run_WFO_TPREGIME.bat` (regime-adaptive),
both on the current model/data → tell Claude "WFO done" for the OOS verdict.
**📏 WFO SIZING NOTE:** all WFO runs use **fixed 0.01 lot** (run_wfo default) → CLEAN R, honest weekly edge
measurement. 3% dynamic compounding is the LIVE sizing, NOT used in WFO (compounding/ordering would distort
PF & total-R). Two-step: WFO (fixed 0.01) proves the edge → then the **$10k 3%-dynamic sim (Stage 2)** shows
real return + DD (~28-39%). ⚠️ The daily 9% ratchet rule can't be validated by fixed-lot WFO (never binds) —
only by the $10k sim. → see TASKS P2b.

## ▶ PRIOR (2026-06-26 — CLOSED-LOOP RELABEL done + config switched → RETRAIN next)
**✅ Task 1 (closed-loop relabel) DONE + LIVE-SWITCHED.** Built `engine/relabel_trades.py`
(+ `backtest/Run_Relabel_Trades.bat`): recomputes every training-trade's Win/R/exit under the
live HTF exit engine (ratchet + H1 line SL/flip + TP cap), leakage-safe. RAN: 2,743/2,788 relabeled;
**744 labels CHANGED (27.1%)** vs the old static backtest (aggregate WR coincidentally same 37.7%).
→ confirms the model WAS training on ~27% labels that disagree with live. Output:
`data/Back_testing_data_final_cleaned_RELABELED.xlsx`. **`config.py trades_file` now points at it**
(reversible — comment holds old name).
**NEXT (do in order):** 1) `Start\3_Train_Models.bat` → retrain on relabeled file.
2) WFO-validate OOS vs current PF 1.55 — keep ONLY if equal/better, else revert `trades_file`.
3) (parallel, still pending) regime-adaptive TP WFO + full-history backtest (below).

## ▶ PRIOR (2026-06-26 — REGIME-ADAPTIVE TP backtest WON, next = WFO OOS)
**✅ Full 9-mo backtest_replay A/B done — REGIME-ADAPTIVE TP WON:** global TP=1.0 vs regime-adaptive
(Rng 2.0 / Trn 1.0 / Vol 0.8): Total R **257.7 → 310.2 (+20%)**, PF 2.52→2.56, avg R 0.384→0.436,
WR ~55%, Max DD 1.7→2.0%. Drivers: Ranging +34R (wide TP=2.0), Trending +16R, Volatile +2.5R.
Code = `backtest_replay.py --tp-regime` (config-gated, reversible, NOT yet in live bridge).
Reports: `results\backtests\tp_regime\` vs `tp_1\`.
**⚠️ Still IN-SAMPLE.** Gate before live = 2 OOS checks:
  1. **WFO OOS** (TASKS.md #5) — needs `run_wfo.py --tp-regime` passthrough first, then `Run_WFO_TPREGIME.bat`.
  2. **Full-history backtest** (TASKS.md #4) — `Run_Backtest_FullHistory.bat`, tests on 2022-24 unseen data.
Both must hold → wire regime map into live bridge (`config.py`+`bridge_core.py`) → DEMO → live. NOT done yet.

## ▶ EARLIER (2026-06-26 — REGIME-ADAPTIVE TP, mid-test snapshot)
**Where we stopped:** built REGIME-ADAPTIVE TP cap (TP switches by HMM state at entry:
Ranging 2.0 / Trending 1.0 / Volatile 0.8 — from the 13-TP sweep). Code added in
`backtest_replay.py` (new `--tp-regime` flag + `_TP_BY_REGIME` map, config-gated, reversible,
default OFF so nothing else changed). Bats: `backtest\Run_TP_Regime_TEST.bat` + `Run_TP_Regime.bat`
(same settings as the sweep: $10k, 0.01 lot, HTF flip + CTF-fade — apples-to-apples vs `tp_*`).
**TEST done (short 05-26→06-12, 44 trades): adaptive BEAT global TP=1.0** —
Total R +19.6→**+26.8**, PF 4.58→**5.32**, WR 57.8→**63.6%**, avg R 0.435→**0.610**, DD 0.5→0.4%.
Ranging was the driver (+8.2R→+15.6R via wide TP=2.0), as predicted. Small sample though.
**NEXT (resume here):** Imtiyaz runs **`Run_TP_Regime.bat`** (FULL 9-mo) → tells Claude
**"regime TP done"** → Claude compares `results\backtests\tp_regime\` vs `tp_1` (global 1.0).
If adaptive wins → WFO-validate OOS (TASKS.md item 2) → then DEMO. Live config NOT changed yet.

## ▶ PRIOR STEP (2026-06-26)
**TP sweep analyzed. USER CHOSE TP=1.00 (2026-06-26), NOT 1.20.** (TP-1.2 backtest winner was
PF 2.62 / +257.9R / DD 2.0%, but user kept the proven TP=1.00 config: +287R/PF1.74 in-sample.)
Sizing = **3% risk dynamic compounding** (NOT fixed lot). H1 flip exit ON (shadow-sim +33% R edge).
**Live config (config.py) now:**
  `ratchet_tp_cap_pct=1.00`, `ratchet_htf_sl=True`, `ratchet_htf_flip=True`,
  `skip_counter_trend_fade=True`, `risk_pct=3.0`, `use_fixed_lot=False`.
**NEXT:** restart `Start\1_Start_Trading.bat` + `Start\5_Dashboard.bat`.
⚠️ 3% compounding → real DD ~28-39% (backtest was fixed 0.01 lot = ~2% DD). Watch equity closely.

## ▶ PREVIOUS STEP (2026-06-23 EVENING)
**✅ DONE: full backtest ran, BOTH won, config ENABLED.** Full 9-mo (0.01 lot): BOTH = PF 2.29→**2.52**,
WR 53→**55.5%**, Total R +252→**+258**, MaxDD 4.2→**3.6%**. Enabled in config.py:
`ratchet_htf_sl=True`, `ratchet_htf_flip=True`, `skip_counter_trend_fade=True` (all reversible).
**NEXT: restart `1_Start_Trading.bat` + `5_Dashboard.bat`** to load. ⚠️ In-sample → **watch the equity
curve closely; revert any flag to False if live behaves worse than backtest.** TP=1.00 caps the HTF
gain so Total-R rise is modest (+2.4%) — the real win is higher PF + WR + **lower drawdown**.

### 📋 STEPS FOR IMTIYAZ (continue here — do in order, no confusion)
**STEP 1 — load new settings (once):** close + re-run `Start\1_Start_Trading.bat` and
`Start\5_Dashboard.bat`. ✅ done = dashboard shows 📋 SIGNAL LOG + 📒 LEDGER tabs; bridge logs
"SKIP (counter-trend fade)" / "SKIP (range-phase)" when it filters.
**STEP 2 — fine-tune TP% (current job):**
  (a) TEST: run `backtest\Run_TP_Sweep_TEST.bat` (short, 10 TPs, $10k, 0.01 lot, HTF+CTF on).
      All 10 finish, no errors → continue.
  (b) FULL: run `backtest\Run_TP_Sweep.bat` (full 9-mo, **resumable** — re-run if it stops).
  (c) Tell Claude **"TP sweep done"** → it reads `backtest\results\backtests\tp_*` reports and
      gives the best TP **per regime** (Trending/Ranging/Volatile).
**STEP 3 — apply best TP:** change `ratchet_tp_cap_pct` (one line in `config.py`) to Claude's
  recommended value → restart `1_Start_Trading.bat`.
**TO UNDO any fix** (if live worse than backtest): in `config.py` set back to False →
  `ratchet_htf_sl`, `ratchet_htf_flip` (HTF exit) · `skip_counter_trend_fade` (entry block) ·
  `skip_range_phase_entry` (H4-chop). Restart bridge. Nothing is permanent.
**Files:** config=`engine\config.py` · backtests=`backtest\results\backtests\` ·
  WFO=`backtest\results\wfo_*` · full change log=`engine\docs\FIXES_CHANGELOG4.md` (06-23 evening).
**⚠️ TradeQuo #125926628 = REAL money — watch first days, revert if worse.**

**Why (today's big finding):** the system MISSES clean trend moves — measured via **Captured/Available
Move**: an 18-23 Jun 318-pt downtrend captured −19% (lost), 14/18 trades whipsawed out via M15 FLIP.
Two reversible fixes found (both default OFF, need full-backtest confirm):
 1. **HTF H1-flip** (exit) — flip/SL on H1 line = 2× capture, +33% R (in shadow-sim). The anti-whipsaw
    exit we built then reverted; data says re-enable.
 2. **Counter-trend-FADE** (entry, Anisa's "dominant-TF" idea) — block a trade against the dominant
    timeframe (higher ADX of H1/H4) when that ADX slope is FALLING. In-sample +15R, PF 1.74→1.89.

**Also shipped today:** dashboard 📋 Signal Log (below RISK & SESSION; price/win%/regime/H4-RANGE/BW%/
lot/WIN-LOSS/equity/virtual-outcome; works bridge-off), 📒 LEDGER tab (`shadow.html` virtual trade
ledger), signal-log dedupe + equity column, shadow ledger auto-refresh (15 min). See FIXES_CHANGELOG4
(06-23 evening) for the full list. New backtests now save under `backtest\results\backtests\` (separate
from WFO in `backtest\results\wfo_*`).

## ▶ NEXT STEP (2026-06-23 afternoon)
**Config reverted to TP=1.00 + M15 ratchet + RANGE-PHASE FILTER (data-driven best).** Clean 44-feat
model retrained ✅. NEXT: run `Run_Backtest_Report.bat` → confirm range-filter (expect ~756 trades,
PF ~2.6, price_move column). Then demo restart → forward-test. See STRATEGY.md for full add/remove list.
Key wins today: range-phase filter (PF 1.74→2.62, strongest lever), TP=1.00 revert (far-TP was cutting
profit), "chasing" pattern (range/high-ADX/far-from-line = bad). M15_ADX + ts_line_dist_pct = top
features, USE as filters not remove. (Changes in FIXES_CHANGELOG4, bug review in BUG_LOG 06-23.)

## (earlier) ▶ NEXT STEP (morning 2026-06-23)
**Running now:** `Run_Ablate_FULL.bat` (H1-alignment ablation, 41-wk WFO, ~12hr, overnight, demo paused).
When it finishes → tell Claude **"ablation done"** → compare wfo_ablate_h1 vs baseline (+144R, PF 1.55):
 - IMPROVES → make H1-align removal permanent (add the 3 feats to _MANUAL_PRUNE).
 - WORSE → revert (do nothing; the ablation was env-only, committed lists untouched).
**THEN, before live:** run `3_Train_Models.bat` for a FRESH production model — the ablation WFO left a
41-feature cutoff model in data/models/final (NOT production-ready). Then `1_Start_Trading.bat` on DEMO.

## 🧪 BACKTEST TEST QUEUE — test ALL via backtest_replay (priority order)
**Approach (Anisa's preference):** use **backtest_replay.py** ("this type" — real ML model, single
replay, ~minutes, rich report with BY HOUR / BY REGIME / BY MONTH) for FAST screening. NOT WFO for
search (WFO = validation only, slow + overfit-prone). Validate the final winner ONCE (WFO or demo).
**First rebuild a clean 44-feature model** (3_Train_Models.bat — ablation left a 41-feat model).
Tools ready: `Run_Backtest_Report.bat` (full report), `Run_TrailCompare.bat` (trail modes).

| Pri | Idea | Status | How |
|----|------|--------|-----|
| **1 ⭐** | **Time-of-day / HOUR filter** (chosen schedule below) | descriptive only — NOT validated | time-filter config + replay/WFO |
| **2** | **Trail modes** confirm via replay (line/off/after1r/be/htf/regime) | WFO: all tied — re-confirm fast | Run_TrailCompare.bat |
| **3** | **Buffer sweep** (0.05–0.50%) | not via replay yet | replay sweep |
| **4** | **TP sweep** (0.5 → far/no-TP) | partial (trades_tp_*.csv) | run_tp_backtest |
| **5** | **Oversized-bar entry** filter (body/range top quantile) | descriptive hint only | replay filter |
| done | Risk 1/2/3/5% (Monte-Carlo: 1-2% safer) | done | post-process trade log |
| ✅ WFO-done | Baseline (PF 1.55), Trail (tied), Ratchet (same), H1-ablation (wash) | done | — |
| ❌ rejected | Volume ENTRY filter, Volume EXIT | tested — both hurt | do NOT re-test |

**Chosen HOUR schedule to test (broker time):** core every day 1,2,8,9,15,16,17 ·
Mon 1,2,7,8,9,15,16 · Tue +18 · Wed drop 15 · Thu +20 · Fri base. Avoid 14,19,12 always.
(Descriptive: PF 1.55→2.00. Validate before live; fallback = base-7, PF 1.94.)

## ✅ DONE TODAY (2026-06-23)
- **Volume removed from the model** (like ATR): vol_spike was already out; added `volume` (imp 0.02) to
  _MANUAL_PRUNE. Retrained → 44 features, AUC unchanged (Main 0.7594/0.7470, BUY 0.80, SELL 0.75) → safe.
- **Confirmed ATR is fully vestigial** — used in ZERO decisions (only logs/dashboard display; ADX keeps its own TR).
- **H1-alignment finding (per regime):** among 15m+4h-aligned trades, H1-DISAGREE beats H1-AGREE in ALL 3
  regimes (Ranging PF 1.51 vs 1.15 · Trending 4.36 vs 1.48 · Volatile 2.44 vs 1.51). Universal, not regime-specific.
  → motivated the H1-alignment ablation test (now running).
- **Ablation tool built + verified** (env `QGAI_ABLATE`; Run_Ablate_TEST/FULL.bat). QUICK TEST passed,
  feature count 44→41 confirmed (H1-align feats removed).
- **Reminder logged:** never delete features from one model's 0-importance list — cross-model trap
  (e.g. momentum_aligned_1hr = 0 in SELL but #1 in BUY). Importance is per-model.

## ✅ EXIT FINALIZED (Stage 1 + 2 done, 2026-06-22)
- **Trail sweep (41-wk WFO, all 6 modes): essentially TIED** (+140 to +144R, avgR ~0.138, PF 1.65-1.69).
  Trail mode barely matters — the HTF H1 flip is the dominant exit. Keep **current "line"** (highest PF 1.69).
- **Stage 2 ($10k, 3% real volume, far TP):** 9/10 green months, PF 1.55 OOS.
  Risk: 1%→+300%/15%DD · 2%→+1342%/28%DD · 3%(live)→+4624%/39%DD. (3% aggressive; daily-halt not modeled
  here → real DD likely lower.) Only red month = Feb-2026 (−$30k).
- **Final exit config (live, in config.py):** ratchet_htf_sl/flip=True, tf=H1, buffer 0.20, far TP
  (tp_equity_pct=0, ratchet_tp_cap_pct=10), line trail, risk 3%, daily 9% ratchet.

## ✅ EXIT FINALIZED (Stage 1 + 2 done, 2026-06-22)
- **Trail sweep (41-wk WFO, all 6 modes): essentially TIED** (+140 to +144R, avgR ~0.138, PF 1.65-1.69).
  Trail mode barely matters — the HTF H1 flip is the dominant exit. Keep **current "line"** (highest PF 1.69).
- **Stage 2 ($10k, 3% real volume, far TP):** 9/10 green months, PF 1.55 OOS.
  Risk: 1%→+300%/15%DD · 2%→+1342%/28%DD · 3%(live)→+4624%/39%DD. (3% aggressive; daily-halt not modeled
  here → real DD likely lower.) Only red month = Feb-2026 (−$30k).
- **Final exit config (live, in config.py):** ratchet_htf_sl/flip=True, tf=H1, buffer 0.20, far TP
  (tp_equity_pct=0, ratchet_tp_cap_pct=10), line trail, risk 3%, daily 9% ratchet.

## ✅ DONE (this session, all in code + verified)
- Exit: HTF **H1** stop + flip ON, buffer **0.20**, TP **far** (flip is the exit).
- Daily: **9% ratchet** (loss-floor + profit-lock). Old "Trade-2 equity SL" **removed**.
- ML: ATR removed; slot_win_rate → 1-hour + **leakage fixed**; **23 features pruned** (→45); retrained.
- Validated: walk-forward OOS **PF 1.55, 82% green weeks, 9/10 green months** (edge is real).
- Env: Python 3.12 + all packages; bats use full python path.
- Backtest output moved to `backtest\results\`; engine = code + live logs only.
- Built (tested): **trail-sweep** (`--sweep-trails`, one retrain → all 6 modes) and
  **shadow_ledger.py** (real signals → paper-trade ledger, 708 trades OK).
- Docs: RULEBOOK.md, SYSTEM_OVERVIEW.md, FIXES_CHANGELOG4.md.

## ⏳ IN PROGRESS
- **Stage 1 trail-sweep** — QUICK TEST passed (6 modes, resume works, htf bug fixed).
  Full 41-week run = the immediate next step above.

## 🔜 AFTER STAGE 1
1. Pick winning trail mode from the sweep (totalR / PF / DD / green-weeks).
2. **Stage 2:** winner only, real **$10k + 3% volume + FAR TP** (`--tp-equity 0`, NOT 3 — see RULEBOOK §1).
3. Set winner in `config.py` → retrain → **demo forward-test** a few days → live small.
4. THEN apply the **shadow ledger + dashboard** on the FINAL exit strategy (parked until then).

## 🧪 IDEAS TO TEST (later, after the trail-sweep)
- **⭐⭐ TIME-OF-DAY FILTER (Anisa's chosen schedule) — implement + WFO-validate next.**
  Descriptive (baseline WFO trades): trading only good hours lifts PF 1.55→2.00, avgR 0.139→0.254,
  green 30→31/41 (totR +117 vs +144; fewer-but-better trades). Sessions are structural → more
  trustworthy than volume, BUT in-sample-selected + small per-day samples → MUST WFO-validate.
  **Chosen schedule (broker time):**
   - Core every day: 1, 2, 8, 9, 15, 16, 17  (Asia 1,2 · Europe 8,9 · NY 15,16,17)
   - Mon: 1,2,7,8,9,15,16   (drop 17, add 7)
   - Tue: 1,2,8,9,15,16,17,18   (add 18)
   - Wed: 1,2,8,9,16,17   (drop 15)
   - Thu: 1,2,8,9,15,16,17,20   (add 20)
   - Fri: 1,2,8,9,15,16,17   (base)
  **Plan:** (1) add day-specific hour filter to config; (2) WFO-validate OOS; (3) holds → live, drops → use
  the robust BASE-7 (1,2,8,9,15,16,17 every day, PF 1.94) as fallback; (4) then demo.
  Avoid-everywhere hours confirmed bad: 14, 19, 12.

- **🔄 Drop H1 alignment? — ABLATION RUNNING NOW (Run_Ablate_FULL.bat).** Per-regime descriptive
  CONFIRMED universal: among 15m+4h-aligned trades, H1-DISAGREE > H1-AGREE in all 3 regimes
  (Ranging PF 1.51 vs 1.15 · Trending 4.36 vs 1.48 · Volatile 2.44 vs 1.51). Removing the 3 H1-align
  composites (h4_trending_h1_aligned [#2 feat], h4_h1_regime_score, ts_htf_agreement) via env ablation,
  full WFO. Awaiting result → compare vs +144R/PF1.55 → keep removal ONLY if it improves. (h4_trending_h1_aligned
  is the #2 feature, so blind removal was refused — testing first per RULEBOOK.)
- **Avoid oversized-bar entries?** Descriptive hint: high `body_pct` / `range_pct` at entry → lower avgR
  (−0.19 / −0.17), i.e. entering after a big/wide bar = "chasing". Test as an ENTRY FILTER (skip if the
  entry bar's body/range is in the top quantile). NOT a feature to delete — test as a filter via WFO.
- ~~Avoid HIGH-VOLUME / spike entries~~ **❌ TESTED — DOES NOT WORK, do not implement.**
  Static top-10%-volume filter looked great (+147.6R) BUT that was an artifact of absolute volume levels.
  Every LIVE-REALISTIC rolling threshold (roll96/500 P80–P99) HURT: totR fell to +93–118, avgR/PF dropped
  below baseline — even removing only the top 1% spikes. The model already handles volume (it's a feature);
  a crude bolt-on filter removes its nuance and cuts good trades too. Instinct is real but already captured.
- ~~Use HIGH VOLUME for EXIT~~ **❌ TESTED — DOES NOT WORK.** All variants hurt vs actual (+144R):
  ungated +85, against-position +89, favor/climax +122. High-vol bars are mostly CONTINUATION not
  reversal → exiting cuts winners. OB-gated not tested directly (needs OB reconstruction) but the
  consistent negative makes it a long shot. PATTERN: volume is not a standalone lever (entry OR exit) —
  the model/ratchet already capture it. Original idea kept below for reference:
- **Use HIGH VOLUME for EXIT (not entry) — gated by supportive features (Anisa's idea).** Same spike that
  traps an entry can signal a good EXIT (climax/exhaustion or reversal). Design: exit (or tighten) when a
  high-vol / vol_spike bar prints AND a supportive condition holds — e.g. price at/inside an **Order Block
  zone** (h4/h1 resist/support dist, in_ob_zone, ob_strength — already strong features), or the spike is
  AGAINST the position, or after an extended move (momentum exhaustion). OB zones = the S/R confluence.
  New config-gated EXIT variant;
  WFO-test vs current (does totalR/DD improve). Note: intra-trade volume path isn't saved yet, so this is
  design + WFO, not a quick descriptive check.
- **Proper feature ablation (the real "which feature kills profit" test):** after the sweep, remove the
  top profit-drag candidates ONE AT A TIME, re-run WFO, keep a removal only if OOS totalR/PF IMPROVES.
  Correlation/importance are only hints — ablation is the proof. Beware cross-model redistribution.

## ⚠️ OPEN DECISIONS / THINGS KNOWN
- **Risk kept at 3%** (Anisa's choice). Monte-Carlo: 3% ≈ 87% chance of >50% DD; 1-2% safer if ever wanted.
- **Account has manual trades** (Anisa) → bot's daily-halt/sizing read WHOLE-account equity. Kept as-is (known).
- **Stage 2 TP trap:** equity-TP 3% with 3% risk = 1R (tight, kills edge). Stage 2 must use FAR TP.
- Dashboard server (serve.py) crash + dashboard.json read fixed → restart `5_Dashboard.bat` to load it.
- Failover (`MT5_PRIMARIES`) still not configured (code ready, list empty) — optional.

## 🧠 KEY NUMBERS (current, for reference)
- risk_pct 3% · ratchet_buf_pct 0.20 · ratchet_tp_cap_pct 10 (far) · tp_equity_pct 0 (off)
- ratchet_htf_sl/flip = True, tf = H1 · daily 9% ratchet · features = 45 (no ATR, 1h slot)
- OOS baseline: PF 1.55, +144R / 41 weeks, 82% green weeks.

---
*Update this note whenever the "current step" changes — it's the session bookmark.*
