# Backtest Result Audit — Standing Post-Backtest Rule

**Permanent rule (Imtiyaz, 2026-07-16):** run this full audit on EVERY backtest
result before quoting it, trusting it, or writing a KEEP/DROP/adopt decision
anywhere (`TASKS.md`, `FILTERS_MASTER.md`, `FIXES_CHANGELOG4.md`). A raw
Total R / Profit Factor number is not a verdict by itself — this checklist is.

Companion to [`docs/PRE_BACKTEST_AUDIT.md`](PRE_BACKTEST_AUDIT.md)
(pre-backtest checklist, run before the backtest starts). §1 below
carries forward that audit's Leakage/Repaint Verdict rather than
re-deriving it.

Applies to every stage: 3-month screen, 1-year OOS, WFO, feature-sweep
ablation/unprune tests, filter A/B tests. Do not skip sections because a
result "looks obviously good or bad" — every conclusion below must cite an
exact metric/number, never a general impression.

**The full validation ladder (3-Month -> 1-Year -> WFO -> Monte Carlo ->
Forward/Demo) lives in ONE place:
[`docs/STRATEGY_TESTING_STAGE_GATE.md`](STRATEGY_TESTING_STAGE_GATE.md) —
that doc is the single source of truth for stage order and stage-pass
criteria. This checklist does not repeat or re-derive that ladder; it only
tells you HOW to audit a result once you have one.** Current validation
stage across the whole engine is 3-Month OOS only — do not recommend
jumping to 1-year or WFO until the current stage explicitly PASSes per
the stage-gate doc.

## Tiering (Fable-5 review, 2026-07-16)

**Tier A — every result, no exceptions:** §1 (leakage — carry forward
from the matching pre-backtest audit's Leakage/Repaint Verdict; only
re-check what could have changed mid-run: retrain, repaint, data gap),
§2 (main performance), §9 (sample size), §15 (stage acceptance gate).

**Tier B — full 15 sections — before any KEEP/DROP/adopt decision or
stage promotion:** §3-8, §10-14. A quick A/B glance during screening can
use Tier A only; nothing gets written into `TASKS.md`/`FILTERS_MASTER.md`
as a decision without Tier B.

---

## 1. Data Integrity / Leakage Audit
**Carry forward, don't re-derive (Fable-5 review, 2026-07-16):** the
matching `docs/PRE_BACKTEST_AUDIT.md` run for this same backtest already
produced a Leakage Verdict and a Repainting Verdict — pull those forward
instead of re-running the full pre-audit here. Only re-check what could
have changed DURING the run itself: a mid-run retrain, a repaint
detected after the fact, or a data gap. If no matching pre-audit exists
for this run, that itself is a finding — note it and fall back to the
checks below.

Check first, before anything else:
- Training cutoff date is before the backtest start date.
- Training and testing periods do not overlap.
- No future candle / future high-low / future swing / future regime / future
  result value entered any feature.
- No incomplete candle or next-candle value used in feature calculation.
- Every signal was decided only from data available at that signal's own
  timestamp (no lookahead).
- slot_win_rate, day filters, probability thresholds, or other statistics
  were NOT built from the test-period data itself.
- No mid-backtest retrain or threshold tuning happened.
- No historical signal repaint / disappearance / direction flip after the
  fact.

**Verdict (pick one):** Leakage-Free / Leakage Risk / Confirmed Leakage.
If not Leakage-Free, do not trust the performance numbers below.

## 2. Main Performance Summary
Report in a table: Total Trades, Winning Trades, Losing Trades, Win Rate,
Total R, Average R/trade, Median R/trade, Profit Factor, Gross Profit,
Gross Loss, Max Drawdown, Max Drawdown in R, Max Consecutive Losses, Max
Consecutive Wins, Best Trade, Worst Trade, Avg Winning Trade, Avg Losing
Trade, Expectancy per Trade, **Avg Holding Duration, Max Holding
Duration, % Time in Market, Simultaneous-Open Overlap Count** (added
2026-07-16 — a trade can sit open for days per the SIGNAL≠REAL-TRADE
distinction; two results with equal Total R can carry very different
real exposure).

Specifically check: Total R truly positive; average R/trade positive;
whether PF is inflated by a few large trades; win-rate vs reward-to-risk
balance; return vs drawdown reasonableness.

## 3. Big-Winner Dependency
Report Total R: all trades / minus best 1 / minus best 3 / minus best 5 /
minus top 10% winners. Answer: is the edge spread across many trades, or
resting on a few lucky ones? **If removing the top 3-5 trades flips Total R
negative, classify the result as unstable.** (This same removal test is
reused by §12 Robustness and §13 Overfitting below — run it once here,
those sections cite this result rather than re-running it.)

## 4. Time-Based Consistency
Month-wise and week-wise: Total R, Trades, Win Rate, PF, Max DD. Best/worst
week, consecutive losing weeks, % of profitable weeks. Check: does one
month/week carry the whole result while the rest are flat/negative; is the
equity curve smooth or one jump then flat; are start/middle/end periods
comparable.

## 5. BUY / SELL Separate Analysis
Both directions: Trades, Win Rate, Total R, PF, Avg R, Max DD, Consecutive
Losses. Check both directions are profitable, whether the whole edge is
really only BUY or only SELL, and whether one direction is a persistent
loser. A weak direction does not require dropping the whole
feature/system — consider "Directional Use Only" instead.

## 6. Market Regime Analysis
Ranging / Trending / Volatile, each with: Trades, Win Rate, Total R, PF,
Avg R, Max DD, Consecutive Losses. Check whether it works in every regime
or only one, whether any regime is badly damaged, and whether overall
profit is really just a few trades in one regime.
**Classification:** Core Feature/System / Regime-Specific / Directional /
Neutral-Redundant / Drop Candidate.

**Causality check (Fable-5 review, 2026-07-16):** confirm the regime
column used for this split is the AT-SIGNAL-TIME regime actually logged
in the trades CSV at signal time, not a regime re-computed/re-decoded
after the fact with hindsight (see [[project_htf_direction_architecture_rethink]]
memory — this project has a known history of HTF-direction features
disagreeing with each other; regime labels are exactly the kind of thing
that can quietly become non-causal if re-derived).

## 7. Probability / Threshold Analysis
Bucket by model probability (e.g. 0.40-0.45, 0.45-0.50, 0.50-0.55,
0.55-0.60, 0.60+): Trades, Predicted Win Rate, Actual Win Rate, Total R,
PF, Avg R per bucket. Check: does actual performance rise with predicted
probability (calibration); is the current threshold evidence-based or
arbitrary; does any lower bucket outperform a higher one; was any threshold
change made without checking sample size.

## 8. Feature / Filter Contribution (when this run is an A/B or ablation test)
Compare Baseline vs Candidate: Total R, PF, Max DD, Trades, Avg R.
**Total R improving alone does not make a feature useful.** Check: DD
improved; Avg R improved; result more consistent; trade count didn't
collapse; the gain isn't just from dropping a handful of trades to look
cleaner; both BUY/SELL benefited; multiple regimes benefited; the feature
isn't duplicate information of an existing one — **check this with a
concrete method (Fable-5 review, 2026-07-16), not just a description: a
correlation matrix against existing active features, or permutation-
importance overlap.** This project has a documented case of exactly this
kind of hidden redundancy (ADX/DI vs SMMA-trend features disagreeing
~10% of the time while both claim to measure HTF direction) — don't
accept "seems different" without running the number.
**Final status:** KEEP / DROP / REGIME-SPECIFIC KEEP / DIRECTIONAL KEEP /
REDUNDANT / NEEDS MORE DATA.

## 9. Sample Size Check
Check total trades, BUY/SELL counts, per-regime counts, and per-bucket
counts are all statistically meaningful. **Never write "Pass" off 10-20
trades** — write "Promising, but insufficient sample size" instead.

**Concrete floors (Fable-5 review, 2026-07-16 — this doc says "cite an
exact number, never an impression," so the floors need numbers too):**
minimum **100 trades** for any overall PASS; minimum **30 trades** in any
cell (a BUY/SELL split, a regime split, a probability bucket) before
that cell's own conclusion is trusted — below 30, report the cell's raw
numbers but label it "insufficient sample, directional signal only, not
a verdict." Where feasible, put a rough confidence interval (e.g.
bootstrap) around Avg R rather than a bare point estimate.

## 10. Drawdown / Risk Analysis
Max DD, DD duration, recovery time, max consecutive losses, worst
day/week/month, average loss cluster, return-to-drawdown ratio. Answer:
is this drawdown survivable psychologically and financially in live
trading? State the backtest's risk setting explicitly — never assume how
result would change if risk were raised.

## 11. Trading Cost / Execution Stress Test
Re-check the result under: normal cost, cost +25%, cost +50%, slight
adverse slippage (spread/commission/slippage/delayed entry/delayed
exit/missed trades). Confirm the edge survives a moderate cost increase,
not just the exact backtest assumptions.

## 12. Robustness Test
Best-trades-removal: cite §3's result rather than re-running it. Where
feasible, additionally run: trade-order shuffle, Monte Carlo, entry-delay
test, exit-delay test, slight threshold variation, slight parameter
variation, spread/slippage stress. Check whether small changes collapse
the result — if so, treat as overfitting risk.

## 13. Overfitting Audit
Look for: profit only at one exact threshold; dependence on a handful of
trades (cite §3); one profitable month; total dependence on one regime;
training performance rising while OOS falls when a feature is added;
trade count dropping abnormally; PF rising while Total R/avg R falls; a
small parameter change flipping the result negative; complexity exceeding
what the result can explain.

**Multiple-testing / data-snooping (Fable-5 review, 2026-07-16 — the
single biggest real gap found in this doc):** record how many candidate
variants (features, thresholds, filters) have already been tested against
this EXACT OOS window across all prior runs. Chance alone guarantees some
will show a spurious "PASS" out of a large enough pool — this is a
structural risk for the feature-sweep registry (`feature_sweep_67/`),
which tests dozens of candidates on the same 3-month window. If N is
large (rough guide: >10-15 candidates tried on the same window), raise
the bar for what counts as a real PASS, or require confirmation on a
fresh/held-out window before trusting it.

**Overfitting risk classification:** Low / Medium / High.

## 14. Equity Curve Quality
Describe: smooth upward / choppy upward / flat / one-time jump / long
stagnation / consistent decline / recovery after drawdown. Check: does
profit build gradually; does one big trade make the whole curve; does the
system spend long stretches in recovery; does the tail end deteriorate.

## 15. Stage Acceptance Gate
**(Renamed from "Final 3-Month Acceptance Gate", Fable-5 review,
2026-07-16 — this doc applies to every stage, not just the 3-month
screen, so the gate below applies to whichever stage's criteria are
defined in `docs/STRATEGY_TESTING_STAGE_GATE.md` for the CURRENT stage
being audited.)** PASS the current stage only when ALL of: no leakage;
Total R positive and meaningful; avg R/trade positive; PF acceptable; Max
DD controlled; enough trades (§9 floors met); result not resting on a few
big winners; most weeks/months stable; any BUY/SELL or regime weakness is
clear and manageable; edge survives cost/slippage stress; small
threshold/parameter changes don't collapse it; equity curve quality
acceptable; and, if this is a 1-year or WFO stage, all additional
checkpoints for that stage in `STRATEGY_TESTING_STAGE_GATE.md` are met.

---

## Final Verdict Format (always end with this exact structure)

**Overall Verdict:** PASS / CONDITIONAL PASS / FAIL / INSUFFICIENT DATA /
INVALID DUE TO LEAKAGE

**Strongest Evidence:** 3 strongest points in the system's favor (with exact
numbers).

**Biggest Risks:** 3 biggest risks (with exact numbers).

**Feature/System Classification:** Core Keep / Regime-Specific Keep /
Directional Keep / Neutral-Redundant / Drop Candidate / Needs More Data.

**Next Action** — state the current stage's PASS/HOLD/REJECT decision per
`docs/STRATEGY_TESTING_STAGE_GATE.md` (that doc owns the ladder and its
exact stage names/criteria — don't restate a separate copy of the ladder
here). Then pick exactly one of:
1. Current stage FAILED — stop and fix the issue.
2. Repeat the current stage because sample size is insufficient (§9).
3. Current stage PASSED — proceed to the next stage per the stage-gate
   doc.
4. Result invalid because of leakage — fix leakage and rerun from the
   beginning.

Every conclusion must cite an exact metric or number — no general or
estimate-based answers.
