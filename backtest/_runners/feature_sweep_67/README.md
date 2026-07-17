# 67-Feature Validation Sweep Registry

Use this folder for the organized 67-feature validation sweep.
Every runner has a permanent registry ID. The same ID appears in the BAT
filename, result folder name, summary CSV, and per-feature trade/signal CSVs.
Per-feature CSVs also include a sort number: `000` is baseline, then
`001`, `002`, ... follow the test order. This keeps the view clean if all
CSVs are copied into one folder and sorted by name.

Main operator guide:

`C:\QGAI\docs\RUNNER_REGISTRY_GUIDE.md`

Root result folder:

`C:\QGAI\backtest\results\feature_sweep_67`

Models are trained only in:

`C:\QGAI\data\models\test_workspace`

The live model folder `data\models\final` is not touched.

## Registry

| ID | Runner | Result folder | Summary |
|---|---|---|---|
| `FS67-09` | `..\Run_FeatureSweep_TEST.bat` | `FS67-09_sanity_active2` | `FS67-09_sanity_active2_SUMMARY.csv` |
| `FS67-01` | `FS67-01_RUN_PriorityBatch.bat` | `FS67-01_priority_batch` | `FS67-01_priority_batch_SUMMARY.csv` |
| `FS67-02` | `FS67-02_RUN_Tier1_Active.bat` | `FS67-02_tier1_active` | `FS67-02_tier1_active_SUMMARY.csv` |
| `FS67-03` | `FS67-03_RUN_Tier2_HighProbability.bat` | `FS67-03_tier2_high_probability` | `FS67-03_tier2_high_probability_SUMMARY.csv` |
| `FS67-04` | `FS67-04_RUN_Tier3_Remaining.bat` | `FS67-04_tier3_remaining` | `FS67-04_tier3_remaining_SUMMARY.csv` |
| `FS67-11` | `FS67-11_RUN_PriorityBatch_OOS1YConfirm.bat` | `FS67-11_priority_batch_oos1y_confirm` | `FS67-11_priority_batch_oos1y_confirm_SUMMARY.csv` |
| `FS67-12` | `FS67-12_RUN_h4_support_OOS1YConfirm.bat` | `FS67-12_h4_support_oos1y_confirm` | `FS67-12_h4_support_oos1y_confirm_SUMMARY.csv` |
| `FS67-13` | `FS67-13_RUN_Tier1DropCandidates_OOS1YConfirm.bat` (+ `_TEST.bat`) | `FS67-13_tier1_drop_candidates_oos1y_confirm` (+ `_TEST`) | `FS67-13_tier1_drop_candidates_oos1y_confirm_SUMMARY.csv` |
| `FS67-21` | `FS67-21_RUN_h4_support_WFO6M.bat` | `FS67-21_h4_support_wfo6m_20251229_20260629` | `_WFO_SUMMARY.csv` |
| `FS67-22` | `FS67-22_RUN_15minSlot_M15ADX_WFO6M.bat` | `..._baseline_with_features` + `..._candidate_live_dropped` | `_WFO_SUMMARY.csv` (both arms) |
| `FS67-23` | `FS67-23_RUN_15minSlot_M15ADX_SingleSplit_H2_Isolate.bat` | `FS67-23_15minslot_m15adx_singlesplit_h2_baseline_with_features` + `..._candidate_live_dropped` | `backtest_summary_st-htf.csv` (both arms) |
| `FS67-24` | `FS67-24_RUN_FamilyGroup_ADX_Timing_Priority.bat` (+ `_TEST.bat`) | `FS67-24_family_group\{A_baseline,D_unprune_timing,E_unprune_adx_di}` | `backtest_summary_st-htf.csv` (3 arms — revised 2026-07-17, whole-family ABLATE arms removed, see below) |
| `FS67-25` | `FS67-25_RUN_SHAP_Interaction_Screen.bat` (runs `engine/analyze_feature_interactions.py`) | `FS67-25_shap_interactions` | `interaction_matrix_full.csv` + `interaction_matrix_flagged.csv` (zero-retrain, no train/test arms) |
| `FS67-26` | `FS67-26_RUN_NoiseFloor_Calibration.bat` | `FS67-26_noise_floor\{seed_42,seed_43,seed_44}` | `backtest_summary_st-htf.csv` (3 seeds, same features) |
| `FS67-27` | `FS67-27_RUN_Cumulative_PrunedSet_Restore.bat` | `FS67-27_cumulative_restore\{A_baseline,F_full_restore}` | `backtest_summary_st-htf.csv` (2 arms) |

Optional all-in-one:

`FS67-00_RUN_ALL.bat`

This runs all stages in order and stops if any stage fails.

## Stage Gate

`FS67-01` to `FS67-04` are 3-month clean OOS screening tests only.
They use a local 3-month baseline.

Baseline reuse rule:

- `FS67-01` creates the 3-month baseline.
- `FS67-02`, `FS67-03`, and `FS67-04` reuse:
  `C:\QGAI\backtest\results\feature_sweep_67\FS67-01_priority_batch\baseline\result.json`
- If that baseline file is missing, run `FS67-01` first.

`FS67-11` is the OOS1Y confirmation runner for the priority batch. It uses
the same train cutoff and backtest window as `OOS1Y-01`:

- train cutoff: `2025-06-28`
- backtest: `2025-06-29 -> 2026-06-29`

`FS67-13` is the OOS1Y confirmation runner for the 6 `DROP_CANDIDATE`
features found by `FS67-02`'s 3-month screen (`ts_bars_since_flip`,
`15_min_slot`, `M15_DI_diff`, `slot_cos`, `mins_to_next_3star`, `M15_ADX`).
Same `OOS1Y-01` window/cutoff as `FS67-11`/`FS67-12`. `in_range_phase` was
also a `DROP_CANDIDATE` on FS67-02 but is deliberately excluded — already
decided (2026-07-16) to keep it as-is.

Run `FS67-13_RUN_Tier1DropCandidates_OOS1YConfirm_TEST.bat` first (house
rule: test-run before any long run) — it tests only 1 feature (`M15_ADX`)
in an isolated `_TEST` result folder to confirm no crash / leakage-guard
PASS / correct output location before committing to the full 6-feature
run in `FS67-13_RUN_Tier1DropCandidates_OOS1YConfirm.bat`.

`FS67-22` is a PARALLEL WFO due-diligence run for `15_min_slot` and
`M15_ADX` — both were confirmed `DROP_CANDIDATE` on BOTH the FS67-02
3-month screen and the FS67-13 OOS1Y window (unlike the other 4 FS67-13
candidates, which flipped to `CORE_KEEP` on OOS1Y and were correctly not
dropped). Imtiyaz approved dropping both from live (`features.py`
`_MANUAL_PRUNE`, 2026-07-16) before this WFO ran — so this is
confirmatory due-diligence, not a live-adoption gate. Two arms, same
6-month window as FS67-21: arm A puts both features back
(`QGAI_UNPRUNE`) to simulate the old live config; arm B is today's actual
live default (no unprune). **Needs a retrain** (`Start/3_Train_Models.bat`)
for the live `.pkl` to actually stop expecting these 2 columns.

`FS67-22` came back **DONE 2026-07-17** with a result that CONTRADICTS
FS67-02/FS67-13: keeping the 2 features scored +90.8R vs +75.6R without
them over the same 26-week window (-15.2R for the drop). Fable-5
root-cause trace confirmed this is a real conflict, not a stale/period
effect (FS67-13's own H2-only sub-slice still says DROP), but found 3
confounded config differences between the static single-split sweep and
the WFO harness: `--skip-counter-trend` (WFO only), spread ($0.20 WFO vs
$0.13 sweep default), and joint-drop (WFO drops both features together;
FS67-13 ablated one at a time). `FS67-23` isolates retrain frequency as
the last remaining variable — same H2 window, same WFO flags
(`--skip-counter-trend --spread 0.20`, joint drop), but a SINGLE
train+backtest split (cutoff `2025-12-28`) instead of WFO's 26 weekly
retrains. If FS67-23 agrees with FS67-22 (live/dropped worse), retrain
frequency is the real cause; if it agrees with FS67-13 (live/dropped
better), one of the 3 confounds was. **Live drop has NOT been reverted
pending this result** — do not change `features.py` `_MANUAL_PRUNE`
based on FS67-22 alone.

`FS67-23` came back **DONE 2026-07-17**: -20.7R for the drop, same
direction as FS67-22. Retrain frequency is NOT the cause — one/more of
the 3 confounds was. **Imtiyaz's decision (2026-07-17): do NOT revert
the drop yet.** Test first to reduce noise in the decision. He also
raised a sharper, correct objection: FS67-22/23 proved `15_min_slot` +
`M15_ADX` interact SPECIFICALLY — that does not imply their whole
information FAMILIES (Timing, ADX_DI) interact. `FS67-24` originally
tried to test this via whole-family ablation, which Imtiyaz correctly
flagged as a trivial test (removing 7-11 correlated features will
always show a big loss — that's family signal mass, not evidence of a
specific pairwise interaction). Fable-5 confirmed the objection and
proposed a 3-runner replacement (all 2026-07-17):

- **`FS67-24`** (revised) — whole-family ABLATE arms removed. Keeps
  only the restore-value arms (D: unprune dropped Timing members, E:
  unprune dropped ADX_DI members) — a real "should these come back?"
  question, not a trivial one.
- **`FS67-25`** — zero-retrain SHAP interaction screen. Uses XGBoost's
  native `pred_interactions` on the already-trained live model (one
  forward pass, no training) to rank ALL feature pairs by interaction
  strength. This is how to find OTHER hidden pairs like
  `15_min_slot`+`M15_ADX` without brute-forcing all C(N,2) combinations.
  Output is a triage ranking, not proof — top pairs still need a real
  ablation-backtest confirmation.
- **`FS67-26`** — noise floor calibration. Retrains the SAME feature
  set 3 times with different seeds (`QGAI_SEED` env var added to
  `xgb_model.py` 2026-07-17) to measure how much `total_R` varies from
  randomness alone, holding features constant. No prior KEEP/DROP
  decision in this registry has ever been checked against this number.
- **`FS67-27`** — cumulative restore test. Every one of the 32
  restorable `_MANUAL_PRUNE` features (`corr_imp_ratio` excluded — its
  computation was deleted, restore is a no-op) was validated
  individually, never jointly. This tests the actual shipped decision:
  does restoring all 32 together beat the current live model? If yes
  by more than FS67-26's noise floor, bisect (split in half, recurse
  on the responsible half) to isolate which subset was mispruned.

`FS67-26` came back **DONE 2026-07-17**: same 25-feature live model,
same H2 window, 3 seeds (42/43/44) — `total_R` = 82.9R / 70.1R / 87.3R
(mean 80.1R). **NOISE FLOOR = range (max−min) = 17.2R.** This is how
much `total_R` moves from random seed ALONE, features held constant.

**⚠️ This directly undermines the FS67-22/23 "keep 15_min_slot+M15_ADX"
conclusion.** FS67-22 measured -15.2R for the drop (WFO), FS67-23
measured -20.7R (single-split H2) — both deltas are close to or only
modestly larger than the 17.2R noise floor measured on the SAME H2
window. This does not prove the FS67-22/23 result is noise (both runs
used a fixed default seed, not compared across seeds directly), but it
means the delta can no longer be treated as clearly-signal without
a same-seeds-vs-different-features comparison. **Do not treat the
15_min_slot+M15_ADX drop-cost as settled until this is resolved.**

Any feature that looks useful still needs:

1. Clean 1-year confirmation
2. WFO confirmation
3. Final live/demo check

---

## Backtest Timing Reference (measured 2026-07-17)

Per-unit benchmarks from completed runs on this PC:

| Operation | Approx Time |
|-----------|-------------|
| Train only (XGB+LGB+CAT ensemble) | ~10-15 min |
| 2-week backtest (TEST run, train + BT) | ~2.5 min/arm |
| 3-month backtest (train + BT) | ~16-23 min/arm |
| H2 6-month backtest (train + BT) | ~27 min/arm |
| 1-year backtest (train + BT) | ~57-62 min/arm |
| WFO 26-week (26 retrains + BTs) | ~3h/arm |

**Rule: every new bat must include an `Estimated time` line in its
banner, computed from this table.** Formula: `arms × per-arm-time`.

---

## Feature Importance Theory Reference (2026-07-17)

Reference for future feature KEEP/DROP decisions. Added after the
FS67-13 vs FS67-22/23 contradiction exposed that individual ablation
alone is not trustworthy for correlated features.

### 1. Strobl et al. (2008) — Conditional Permutation Importance

Standard permutation importance shuffles a feature across the entire
dataset. Strobl et al. showed this is **misleading for correlated
predictors** because:

- One feature can get inflated importance (the tree happened to split
  on it rather than its correlated twin);
- The truly useful correlated feature's importance appears low;
- After removing one, importance **transfers** to the remaining
  correlated feature — making individual ablation look "safe" when the
  pair is actually load-bearing.

**QGAI example:** `H4_ADX`, `H4_DI_diff`, `adx_trend_count` all share
the same underlying trend information. Remove one → the tree rebuilds
via the others → delta ≈ 0. Remove all → no substitute → large loss.

**Strobl's solution:** conditional permutation importance — shuffle
the feature *conditioned on* its correlated partners, answering:

> "With the related features' information already present, does this
> feature add its own unique information?"

**Key finding:** unconditional permutation gives correlated features
an undeserved advantage; conditional importance reflects independent
contribution more reliably.

### 2. Shapley Theory / SHAP (Lundberg & Lee)

Shapley value = cooperative game theory concept. Each feature = a
"player", model prediction = the "payout".

A feature's Shapley value = the weighted average marginal contribution
when that feature joins every possible subset of other features:

```
φᵢ = Σ_{S⊆N\{i}} [ |S|! (M-|S|-1)! / M! ] × [ f(S∪{i}) - f(S) ]
```

**Plain meaning:** average how much the prediction changes when this
feature is added, across every possible ordering.

Lundberg & Lee's SHAP framework applies this to ML: for each
prediction, SHAP shows every feature's positive/negative contribution.

### 3. Key Differences

| Method | Question it answers |
|--------|-------------------|
| Standard permutation importance | How much does performance drop if we scramble this feature? |
| Strobl conditional importance | With correlated features preserved, what is this feature's unique value? |
| SHAP | How is prediction credit allocated fairly across features? |

### 4. Critical Warnings for Correlated Features

SHAP gives "fair allocation" but **not causal importance**:

- Two near-duplicate features → SHAP splits credit between them;
- Remove one → the other's SHAP rises (credit transfers);
- Low SHAP ≠ useless (may be load-bearing via backup role);
- High SHAP ≠ stable or leakage-free.

**Therefore:** in QGAI's correlated technical-feature system, relying
on gain importance or mean |SHAP| alone for feature selection is
insufficient.

### 5. QGAI Evidence Stack (use this order)

1. **Correlation / feature-cluster analysis** — identify families
   (→ `FEATURE_FAMILIES` in `features.py`)
2. **Conditional permutation importance** — Strobl-style, within-family
3. **Grouped SHAP** — family-level SHAP, not individual
4. **Feature ablation backtest** — both individual AND group (family)
   (→ `--mode group` in `run_feature_sweep.py`)
5. **OOS / WFO stability** — delta must exceed noise floor
6. **Leakage + timestamp audit** — `PRE_BACKTEST_AUDIT.md`

### 6. Practical Rule

> SHAP = excellent for **explanation** (why did the model predict BUY
> here?). Strobl conditional importance = for understanding
> **redundancy** (is this feature unique?). But the **final KEEP/DROP
> decision** must come from an honest OOS ablation result — and for
> multi-feature drops, always a **joint group ablation**, never
> individual-only.

Standing rule (2026-07-17): multi-feature drop → combined confirmation
run mandatory. Individual "safe to drop" is necessary but not
sufficient. Use `FEATURE_FAMILIES` grouping for family-level tests.
