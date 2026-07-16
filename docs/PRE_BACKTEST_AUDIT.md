# Pre-Backtest Audit — Standing Rule (run BEFORE starting any backtest)

**Permanent rule (Imtiyaz, 2026-07-16):** run this full technical audit
before starting ANY new backtest, WFO, or feature-sweep run — not to find
performance, but to confirm the run WILL be trustworthy before it burns
hours of compute. If any CRITICAL finding turns up, do not start the run.

Companion to [`docs/BACKTEST_RESULT_AUDIT.md`](BACKTEST_RESULT_AUDIT.md)
(post-backtest checklist). Use this one first; use that one after the run
completes.

**Goal:** confirm the backtest will run without data leakage, will use the
same logic as live trading, will build every signal only from information
truly available at that timestamp, will not repaint, will keep training
and testing periods separate, will use realistic execution/cost, and will
save results to the correct folder/file structure.

## Tiering (Fable-5 review, 2026-07-16 — do this or the checklist won't survive contact with real use)

Running all 30 sections before every single run is not sustainable and
will get silently skipped in practice. Split into two tiers instead:

**Tier A — every run, no exceptions (~10 minutes):**
§2 (data window still clean for this date range), §3 (leakage_guard
status — see wiring below), §20-22 merged "Freeze & Manifest", §25 (dry
run — only if a new code path is touched), §26 (determinism — only if a
new script), §29 (red-flag scan).

**Tier B — full 30 sections — only when:**
(a) a new feature/label/indicator was added, (b) inference/backtest loop
code changed, (c) a new data source was introduced, or (d) this is the
first full audit since the last one.

**Audit stamp (mandatory for Tier B):** end every full audit with
`Full audit PASSED @ git hash <X>, date <Y>`. The next run only needs to
re-audit files that changed since that hash (`git diff <X> -- engine/`) —
an audit result is not free to re-derive from scratch every time.

§29's red-flag list doubles as the Tier-A quick-scan — treat it that way,
not as a 31st separate section.

---

## 1. Audit Scope
Maintain ONE standing component inventory (training script, backtest/
replay script, live inference script, feature calculation files, data
loaders, label creation logic, model loading, threshold config, regime/
HMM logic, BUY/SELL directional model logic, entry logic, exit logic,
risk management, trading-cost calc, result-saving logic, BAT/runner
files, config JSON, model metadata, CSV inputs, DB/logging functions) —
don't rebuild this list from scratch every run. Per component: what it
does, what it depends on, what risk it carries. On each new audit, diff
against `git log` since the last audit stamp (see Tiering) and update
only the components that actually changed.

## 2. Data Source Audit
Per input dataset: file name, symbol, timeframe, start/end date, row
count, timezone, timestamp format, missing candles, duplicate rows,
unsorted timestamps, invalid OHLC, zero/negative prices, abnormal spread,
missing volume, weekend rows, market-closed rows. Specifically verify:
chronological sort; no duplicate-timestamp candles; High/Low always valid
relative to Open/Close; multi-timeframe (M15/M30/H1/H4) timestamps align
in the same timezone; no MT5-vs-external timezone mismatch; no DST/broker
server-time alignment error; no data gaps in the backtest window.
**Per-dataset verdict:** CLEAN / USABLE WITH WARNING / INVALID.

## 3. Training / Backtest Period Separation
Record exact dates: training start, training cutoff, validation period,
test period, backtest start/end. **Mandatory rule: training cutoff <
backtest start date.** Check: no backtest-period trade/candle leaked into
training; validation/test data not used for future tuning; threshold not
re-picked after seeing backtest result; same backtest period not repeatedly
retuned; feature selection didn't use future OOS results; slot/day filters
not built from test-period data; HMM/regime model not fit on test-period
data; scaling/normalization/imputation not fit on the whole dataset.
**Verdict:** PERIOD SEPARATION VALID / POSSIBLE CONTAMINATION / CONFIRMED
CONTAMINATION.

### 3a. Automated Tool Wiring (Fable-5 review, 2026-07-16)
Do not re-derive these checks by hand — QGAI already has working
automated tools for most of them:
- **This section (period separation):** `engine/leakage_guard.py` is
  already hard-wired into `backtest_replay.py`
  (`leakage_guard.assert_no_leakage(...)`, ~line 312-316) — it reads
  each model's `_meta.json` sidecar, takes the max exposure date, and
  raises unless `--allow-in-sample` is explicitly passed. Manual
  re-derivation of this check is only needed when `--allow-in-sample`
  is used, or a new script doesn't call `leakage_guard` at all.
- **§17 (repainting):** the 4-step snapshot-compare procedure is already
  implemented — run `engine/diag_signal_repaint.py` and
  `engine/build_feature_snapshot.py --verify N`. Cite these tools by
  name; don't hand-build the snapshot-diff loop again.
- **§4 / §18 (feature leakage):** for a suspicious feature, run
  `engine/test_leakage_auc.py` to get its AUC-removal impact instead of
  reasoning about it from code alone.
- **§8 metadata:** align with the `_meta.json` sidecar schema
  `leakage_guard.py` already defines (exposure-date fields) — don't
  invent a second, different metadata standard.
- **Live-vs-backtest reconciliation (new, not in the original 30):** for
  an overlapping period, diff backtest-generated signals against actual
  live signals using `engine/weekly_reconcile.py` — code-level parity
  (§9) is necessary but not sufficient; an output-level diff catches
  what code review misses.

## 4. Feature Leakage Audit
List every feature, classify: Safe at signal time / Potentially leaky /
Confirmed leaky / Needs manual verification. Per feature check: value
truly available at signal time; no future-close use on an incomplete
candle; no negative-index shift reaching a future candle; no centered
rolling window; no `shift(-1)`/`shift(-N)`/future-row access; no future
high/low/close/return; swing high/low not written to a historical row only
after future confirmation; support/resistance not built from future
candles; order block not written to a historical entry row via future
confirmation; range-phase not labeled by looking at the whole future range;
regime assignment not using future observations; corr/impact ratio not
built from a future result; trade outcome/R/TP-SL result/duration not
smuggled in as a feature; slot win-rate not including the current test
trade; probability calibration not fit on the test period. **Cite the
exact code line/function for every suspicious feature.**

## 5. Multi-Timeframe Candle Audit
For M15/M30/H1/H4 features: which higher-TF candle was actually available
the moment the M15 signal was built? Is an incomplete H1/H4 candle's close
used, or only the last COMPLETED candle? Same candle-selection rule in
both live and backtest? No forward-fill placing a future final HTF value
into earlier M15 rows? No H1/H4 final ADX/SMMA/DI value shown before that
candle actually closed? Per timeframe record: source timestamp,
availability timestamp, signal timestamp, applied shift, safe/unsafe
verdict. **Mandatory rule: a feature may only be built from the value
that was truly available at that moment.**

## 6. Indicator Calculation Audit
SMMA, ADX, +DI, -DI, EMA, ATR, Stochastic, etc: correct period; Wilder
smoothing not mixed with plain EMA/SMA; enough warm-up candles; NaN-row
handling; backtest and live use the identical library/formula; no
MT5-vs-Python indicator mismatch; current-bar vs closed-bar indexing
consistent; recalculation doesn't rewrite historical values; buffer
indexing correct. **SMMA specifically:** fast/slow line price source
correct; slope not built from a future value; distance/buffer available
at signal time. **ADX specifically:** ADX measures strength, not a
disguised DI-difference score; +DI/-DI used correctly for direction; ADX
slope calc causal; strength and direction measured separately (not
cancelling each other inside one composite score).

## 7. Label Creation Audit
Explain how training labels are built. Check: future candles used ONLY
to build the target, never leaked back into a feature; entry price
candle is correct; when TP/SL become active; same-candle TP+SL-hit rule
(conservative, not optimistic, when intrabar order is unknown); spread
and slippage included in the label; max holding period defined;
unresolved trades' label handling; no overlap between big-win and
normal-win labels; duration label built only after future exit AND never
fed back as a feature; BUY/SELL label logic symmetric; TP-cap and R
calc correct. **Recommend a conservative rule for ambiguous same-candle
outcomes.**

## 8. Model Training Audit
Training rows all before cutoff; features/labels timestamp-aligned; no
X/y row mismatch; missing values not filled from future data; scaling fit
only on training data; feature selection only from training/validation;
no hyperparameter tuning against the OOS backtest; time-based (not
random) split; class imbalance handled properly; sample weights don't
create future-outcome bias; fixed random seed; model version saved;
feature list saved; training cutoff in metadata; threshold in metadata;
model hash/checksum saved; preprocessing objects saved alongside the
model. **Minimum saved metadata per model:** name, version, creation
timestamp, training start, training cutoff, feature names+order,
threshold, code version/git hash, data file/hash, regime model version,
directional model version.

## 9. Inference Pipeline Audit
Backtest uses the SAME function as live inference; feature names/order
match training exactly; missing feature is not silently zeroed; extra
feature is not silently ignored; probability taken for the correct class;
BUY/SELL models not mixed up; regime model returns the correct state;
combined/state/directional weights correct and sum to the intended
formula; documented fallback when the state model is unavailable;
threshold correctly sourced per regime; no hardcoded-vs-config threshold
mismatch; no live-vs-backtest probability rounding difference; no
duplicate signal generation; no repaint/disappear of historical signals.
**Trace one full sample timestamp:** raw candle -> features -> regime ->
model probabilities -> blend -> threshold -> final decision.

## 10. Entry Logic Audit
Signal built on candle close or intrabar? Entry on that same close or the
next candle's open? No same-close decision-then-fill at that same close
price; spread applied as ask for BUY / bid for SELL; delay/latency
accounted for; duplicate entries prevented; rule for an existing open
position; rule for an opposite signal; cooldown period; max simultaneous
trades; pending-order expiry; missed-entry handling. **Default realistic
entry when the signal is built on a candle's close: next available
candle's open + spread/slippage.**

## 11. Exit Logic Audit
SL/TP fixed or dynamic from entry; trailing stop updates without knowing
future high/low; exit-AI signal applies only after a historical candle
close; same-candle trail-update-then-exit sequence is realistic;
time-based exit correct; opposite-signal exit rule consistent; equity
TP/daily-stop enabled/disabled as intended; backtest and live exit logic
identical; partial-close R calc correct; breakeven move execution
realistic; gap/slippage applied to stop-loss; exit price correct per
bid/ask side. **Mandatory: a clear priority rule for same-bar TP/SL
conflicts.**

## 12. Position Sizing / Risk Audit
Fixed lot or percentage risk; where the risk % comes from; lot calc from
stop distance correct; gold contract size correct; point/pip/price-unit
conversion correct; broker 2/3-decimal digits handled correctly; min
lot/lot step respected; margin limitation; compounding enabled;
equity-vs-balance used for sizing; consecutive positions don't silently
raise total risk; daily risk cap actually enforced in code; max open risk
defined; zero/invalid SL rejects the trade. **Manually verify lot size on
one example trade.**

## 13. Spread / Commission / Slippage Audit
Spread historical-fixed, variable, or ignored; BUY entry at ask / exit at
bid, SELL entry at bid / exit at ask; commission round-turn or per-side;
swap/overnight charge included; slippage modeled both favorable AND
adverse (not favorable-only); spread widens during news/high volatility;
stop-loss fills at a worse gap price; cost deducted from R calc.
**Prepare at least 3 cost profiles before the backtest: Normal,
Conservative, Stress.** A cost-free backtest is diagnostic only, never
final validation.

**XAUUSD-specific (Fable-5 review, 2026-07-16) — make the Stress profile
session-aware, not a flat +50%:** gold spreads widen sharply in the Asian
session and spike hard in the minute around NFP/FOMC/CPI releases;
Wednesday carries triple swap; Friday-late/weekend-gap liquidity is thin.
A realistic Stress profile widens spread 2-3x specifically inside those
windows rather than applying a uniform markup across the whole day.

## 14. Session / Time Filter Audit
Trading-session timezone; broker-time-to-local/UTC conversion; DST
effect; session start/end inclusive or exclusive; midnight-crossing
session handled correctly; day-of-week filter not built from future
statistics; Friday-close/weekend-gap handling; market-holiday handling;
news filter causal on historical timestamps; slot/day filter is
inference-only, not a training feature; any time filter currently meant
to be disabled is actually disabled in code (verify config AND code both
agree).

## 15. Regime / HMM Audit
HMM fit before the training cutoff; not refit on the test period; state
labels not smoothed into historical rows using a future sequence;
`predict_proba`/Viterbi not exploiting the full future sequence; live
inference uses the same state-availability rule as backtest; state
numbering/mapping stable; Ranging/Trending/Volatile labels don't shift
after a model reload; regime scaler fit only on training data; fallback
exists for an unknown regime; state-specific feature sets correct;
correct combined-model weighting when a state model is missing. **If
full-sequence decoding is used without causal filtering, the backtest is
invalid.**

## 16. Directional Model Audit
BUY/SELL training samples built separately and correctly labeled; no
BUY-trade leak into the SELL model; feature order correct per direction;
differing BUY/SELL thresholds recorded in metadata; combined+directional
blend formula correct; documented fallback if one side's model is
unavailable; BUY/SELL probability calibration comparable; no hardcoded
directional-weight asymmetry without evidence. **Give one inference
trace per direction.**

## 17. Repainting Audit
Historical signals don't change later; old feature values aren't
rewritten after the current candle finalizes; swing/pivot/order-block/
regime confirmations aren't added to a past timestamp after the fact;
dashboard/history DB updates don't overwrite an old signal; backtest
doesn't use final historical values where live only had provisional ones
at that time; a forming higher-TF candle doesn't show its final value in
historical data; a duplicate signal doesn't delete/replace the first one.
**Repainting test:** (1) candle-by-candle replay, (2) save each
timestamp's feature snapshot, (3) compare old snapshots after adding more
candles, (4) identify the exact feature if an old row changed.
**Verdict:** NO REPAINTING FOUND / POSSIBLE REPAINTING / CONFIRMED
REPAINTING.

## 18. Lookahead Code Search
Search the whole codebase for: `shift(-`, `iloc[i+`, `index + 1`,
`future`, `next_`, `center=True`, `bfill`, backward fill, full-sample
normalization, future max/min, expanding calc without a cutoff,
full-sequence HMM prediction, test-period aggregation, global win-rate
mapping, post-trade result merge, trade-outcome merge, label columns
inside features. Classify every match: Safe / Suspicious / Confirmed
leakage. **A keyword match alone is not proof — inspect context before
declaring an issue.**

## 19. Backtest Loop Audit
Confirm the candle-by-candle sequence is: (1) load available historical
candles, (2) compute features only from completed candles, (3) process
existing trade's SL/TP/exit, (4) evaluate signal for current timestamp,
(5) enter at next executable price, (6) apply costs, (7) save
state/log, (8) advance to next candle. Check: no whole-dataframe
precomputed feature leaking future values; trade exit processed before
new entry (or documented order); same-timestamp conflicting orders
handled; multi-timeframe updates happen in correct order; no row
skip/duplicate; correct first valid warm-up index; last incomplete
candle excluded; open trade at test-end closed correctly.

## 20-21. Freeze & Manifest (merged, Fable-5 review, 2026-07-16 — was two ~60% overlapping sections)
Freeze and save a manifest before the run starts: Run ID, Test ID, model
version, code version, data version, feature list, threshold, weights,
date range, risk, costs (spread/commission/slippage), session settings,
filters, regime settings, direction settings, entry rule, exit rule,
random seed, expected output folder. Config must not silently change
once the run starts; every result is saved alongside a copy of its
config. During feature testing, change exactly ONE thing at a time:
`Candidate = Baseline + One Explicit Change`. Never A/B-test feature +
threshold + exit + risk all at once.

## 22. Runner / Folder Audit
Strict one-to-one mapping: **One Runner = One Test ID = One Output
Folder.** QGAI's actual registry naming convention (see
`docs/RUNNER_REGISTRY_GUIDE.md` and `backtest/_runners/feature_sweep_67/`,
`backtest/_runners/exit_workstream/` for real examples) is
**`<ID>_RUN_<Name>.bat`** (ID comes first, e.g.
`FS67-13_RUN_Tier1DropCandidates_OOS1YConfirm.bat`,
`EXIT01_RUN_PostCapContinuationAudit.bat`) ->
`results/<registry_folder>/<ID>_<name>/` ->
`<ID>_<name>_SUMMARY.csv` / `_report.txt` / `_trades.csv` /
`_config.json`. Check: runner calls the correct Python file; passes
correct config; passes correct dates; doesn't silently overwrite an
existing result; captures exit code; never prints success after a
failure; log file is complete; Test ID consistent across all output
files; a multi-ID runner doesn't mix results between IDs.

## 23. Output File Audit
Confirm these will be saved. **Trade-level CSV:** Trade ID, signal
timestamp, entry timestamp, exit timestamp, direction, entry price, exit
price, SL, TP, spread, commission, slippage, gross R, net R, probability,
threshold, regime, combined/state/directional probability, model
version, feature-set version, exit reason, holding duration. **Summary
file:** total trades, Total R, win rate, PF, max DD, avg R, consecutive
losses, BUY/SELL split, regime split, month/week split.
**Reproducibility files:** config, model metadata, feature list,
code/version hash, data hashes, run log, errors/warnings.

## 24. Model-Version Logging Audit
Ideal: every signal and trade logs model version, model file name, model
hash, training cutoff, feature-set version, threshold version, regime
model version, directional model version, code version, config run ID.
**Practical minimum (Fable-5 review, 2026-07-16):** if `signals_all.csv`
doesn't carry per-signal model hashes today, that alone doesn't fail this
section — a run-level manifest (§20-21) that links the whole run to its
model hashes is acceptable. What fails this section is a run with NO
traceable link at all between its signals and the exact model snapshot
that produced them.

## 25. Dry-Run Test
Before the full 3-month backtest, run a short dry run: 1-3 trading days,
at least 5-10 signals, candle-by-candle debug logging, feature-snapshot
logging, entry/exit price verification, spread/commission verification,
model-probability verification, output-file verification. **Manually
verify at least 3 trades** — for each, show: candles available at
signal time, feature values, model output, threshold decision, entry
price, exit path, gross R, costs, net R. Manual and code results must
match.

## 26. Determinism / Reproducibility Test
Run the same config twice. Compare: trade count, entry timestamps, exit
timestamps, probabilities, Total R, PF, drawdown, output hashes. Both
runs must be identical unless randomness is intentional. **On a
mismatch, do not start full validation until the cause is found.**

## 27. Failure Handling Audit
Missing model stops the run; missing column raises a clear error; NaN
probability rejects the trade; divide-by-zero is safe; invalid lot size
is rejected; data gaps are logged; an empty result is never saved as a
success; a partial run is clearly marked; a crash never leaves an old
result looking like the final result; an existing folder is never
silently overwritten without a warning or unique ID. **Treat any silent
fallback as high risk.**

## 28. Performance Optimization Safety
Vectorized calculation produces the same result as candle-by-candle;
cached features aren't contaminated by future data; multiprocessing
doesn't mix state/order across workers; parallel runs don't write to the
same output folder; shared model/config objects aren't mutated; chunk
processing doesn't break a rolling indicator at chunk boundaries;
database writes aren't missing or out-of-order. **Prioritize a correct
backtest over a fast one.**

## 29. Pre-Backtest Red Flags — DO NOT START if any is present
Training/backtest overlap; confirmed future-feature leakage; an
incomplete HTF candle's final value used early; HMM full-future-sequence
leakage; repainting; live-vs-backtest inference mismatch; unrealistic
same-close entry; spread/commission entirely missing; feature-order
mismatch; wrong model version loaded; threshold/filter built from the
test period; optimistic same-bar TP/SL handling; results overwritten or
Test IDs mixed; model/version logging absent; dry-run vs manual trade
mismatch; two runs of the same config differing; serious
missing/duplicate candle data; silent error fallback.

## 30. Severity Classification
**CRITICAL** — can make the result entirely invalid; stop the backtest.
**HIGH** — can seriously bias performance; fix mandatory before the full
run. **MEDIUM** — affects interpretation or reproducibility; fix before
the run if feasible. **LOW** — documentation, naming, or minor robustness
issue. For every finding give: severity, file, function/line, problem,
why it matters, exact fix, verification method.

---

## Final Audit Report Format (always end with this exact structure)

**A. Audit Verdict** — one of: APPROVED FOR DRY RUN / APPROVED FOR FULL
RUN (state which stage per `docs/STRATEGY_TESTING_STAGE_GATE.md` — e.g.
"3-Month Screen", "1-Year OOS", "WFO") / CONDITIONAL APPROVAL / NOT
APPROVED / INVALID DUE TO LEAKAGE

**B. Critical Findings** — all CRITICAL and HIGH findings.

**C. Leakage Verdict** — Leakage-Free / Potential Leakage / Confirmed
Leakage

**D. Repainting Verdict** — No Repainting Found / Possible Repainting /
Confirmed Repainting

**E. Live-vs-Backtest Match** — Exact Match / Minor Differences /
Material Mismatch / Not Verified

**F. Data Quality Verdict** — Clean / Usable with Warnings / Invalid

**G. Reproducibility Verdict** — Reproducible / Partially Reproducible /
Not Reproducible / Not Tested

**H. Mandatory Fixes Before Backtest** — numbered list, only genuinely
necessary fixes.

**I. Recommended Dry-Run Command** — the correct runner, config, dates,
and output folder.

**J. Final Permission** — state exactly one of: "Full backtest can be
started." or "Do not start the full backtest yet."

Approval only when code compiling/running is NOT the bar — approve only
when data, timing, features, model, execution, costs, logging, and
reproducibility are all sufficiently verified.
