# Feature Rename Architecture — Permanent Naming Foundation

**Created:** 2026-07-18 · **Owner:** Imtiyaz · **Architect opinion:** Fable-5
**Status:** Phase 0 ✅ · Phase 1 ✅ (35 pure) · Phase 2 ✅ (23 cross incl. hmm_state split, backtest bit-identical + live-path verified) · Phases 3–4 pending
**Code:** [`engine/feature_registry.py`](../engine/feature_registry.py)

> ગુજરાતી સાર: ~67 cryptic feature નામ (દા.ત. `M15_ADX`, `hmm_state`, `body_pct`)
> ને readable નામ (`adx_m15_strength`, `regime_hmm_id`, `candle_body_ratio`)
> આપવાનાં છે. પણ આ નામ ML pipeline + live SQLite DB + dashboard + raw CSV — બધે
> વપરાય છે, એટલે blind rename તૂટે. **પાયાનો ઉકેલ = એક registry + 4 guards** જે
> દર startup પર ભૂલ પકડે. Rename ફક્ત ML-pipeline (Zone-A) માં; DB/CSV schema
> legacy રહે. આથી ઘર મજબૂત — rename એક વાર, guards કાયમ.

---

## 1. The problem

Feature names are identifiers that flow through several **zones**. The same
string can be an ML feature key, a trained-model `feature_names` entry, a CSV
column header, a **live SQLite DB column**, a dashboard key, and (for ADX/DI) a
**raw indicator column**. A blind find-replace breaks cross-zone consistency,
and two names carry two meanings at once (`hmm_state`).

Discovered collisions:

| Kind | Names | Why dangerous |
|------|-------|---------------|
| Dual-meaning | `hmm_state` | model-feature = **int** 0/1/2; DB/log field = **string** "Ranging"/… — same key, two types, ~36 refs / ~30 files |
| DB-column entangled | `in_range_phase` (+22 more) | also a SQLite column / signal-CSV / dashboard key |
| Raw indicator column | `M15_ADX,M30_ADX,H1_ADX,H4_ADX` + 4×`*_DI_diff` | raw column in `adx_merged.csv`; feeds `build_indicators` / `regen_adx_*` / `compare_adx_parity` (parity stabilized 2026-07-18) |
| Raw MT5 + pruned | `volume`, `tick_volume` | raw OHLC column AND pruned feature — not renamed at all |

## 2. The zone model (the decision)

Keep **one canonical name per feature only inside the ML pipeline**. The
persisted schema and raw CSVs keep their **legacy** names forever — schema
stability is the foundation, not the label.

| Zone | Contents | Naming |
|------|----------|--------|
| **A — ML pipeline** | `feat_dict` keys, `FEATURE_COLS`, train/inference lists, `model.feature_names`, sweep/prune/ablate lists | **CANONICAL (new)** |
| **B — Persistence** | SQLite columns (`bridge_constants.py`), signal-CSV headers, dashboard JSON keys, `bridge.log` | **LEGACY (kept)** |
| **C — Raw data** | `adx_merged.csv` / `indicators_merged.csv` headers, `build_indicators.py`, `regen_adx_*.py`, `compare_adx_parity.py` | **LEGACY (never touched)** |

Zone-A↔Zone-B translation happens at a **few explicit write-sites only**
(auditable), never by renaming across all 30 files.

## 3. The foundation = 1 registry + 4 guards

`engine/feature_registry.py` is the single source of truth:
`REGISTRY = { legacy : (canonical, zone, dtype) }` (68 entries) → derived
`LEGACY_TO_NEW`, `NEW_TO_LEGACY`, `ZONE`, `DTYPE`, `ALL_CANONICAL`.

| # | Guard | When | What it prevents |
|---|-------|------|------------------|
| 1 | `remap_model_feature_names()` | model load (`inference.py` `safe_load`) | old pickle with legacy names still runs on renamed pipeline → **rename & retrain decoupled, no live downtime** |
| 2 | `assert_canonical()` | startup | model feature ∉ canonical set → **hard fail** (train/serve skew caught day-1, not as silent zeros) |
| 3 | `guard_feat_dict()` | end of `compute_features()` | a legacy key leaking out of the feature builder → **hard fail** (silent drift impossible) |
| 4 | `validate_feature_names()` | `QGAI_ABLATE` / `QGAI_UNPRUNE` parse | stale legacy name in an env list silently no-ops → **hard fail** (BUG_LOG #G-class) |

Helpers: `to_legacy()` / `to_canonical()` for the Zone-A↔B write-site
translations.

## 4. Hard-case decisions

- **`hmm_state` → split into two names.** Model-feature (int) = **`regime_hmm_id`**
  (`inference.py:736`, `train.py` feat_full, model-list fallbacks). The string
  state name **keeps the legacy key `hmm_state`** in DB / dashboard / signal
  CSV / `backtest_replay` sig-dict. Two names = two concepts = conflation ended
  permanently. *(The earlier alias `regime_hmm_label` was corrected to
  `regime_hmm_id` — "label" wrongly implied a string.)*
- **`in_range_phase` → `h4move_is_ranging`** on the feature side; DB column
  `in_range_phase` stays legacy, translated at the 2 write-sites
  (`bridge_data.py` insert dict, `inference.py` result dict) with an explicit
  `"in_range_phase": fd.get("h4move_is_ranging", 0)`.
- **ADX/DI 8 raw columns → boundary rename only.** Rename happens at the
  raw→feature boundary loop in `features.py:679-681` / `752-753`:
  `f[f"adx_{tf.lower()}_strength"] = round(float(a[f"{tf}_ADX"]), 4)`. Raw CSV
  headers and `build_indicators` / `regen_adx_*` / `compare_adx_parity` stay
  untouched — the just-stabilized parity layer is not reopened.
- **`volume` / `tick_volume` → not renamed.** Raw MT5 columns + pruned.

## 5. Migration & backward-compat

- **Trained models:** rename requires retrain, but the **load-shim** means old
  `.pkl`s run bit-identically on the renamed pipeline → rename and retrain are
  decoupled, **no live downtime**.
- **SQLite DB:** no migration; columns stay legacy. Optional cosmetic
  `CREATE VIEW` with new names (not required).
- **CSVs:** `adx_merged.csv` / `indicators_merged.csv` and
  `signals_*.csv` headers unchanged. Exception: `feature_snapshot_json` /
  `feature_hash` change when feat_dict keys change → on rename-day compare by
  **value, not hash**; normalize old snapshots via `LEGACY_TO_NEW`.
- **Shim + guards are permanent** (~30 lines): any old model/backup/branch runs
  without ambiguity, and drift is caught every startup.

## 6. Phased execution (each phase has a real gate)

Because a full backtest needs retrained models, the per-phase gate is
**"output bit-identical to the pre-rename baseline"** (shim active) — a
leakage-style parity test that runs without retraining.

| Phase | Scope | Gate |
|-------|-------|------|
| **0 ✅** | registry + 4 guards + shim (no name changed) | self-test PASS; captured baseline (2026-06-15→29, 41 trades +6.0R) |
| **1 ✅** | 35 pure names renamed (features.py Zone-A + inference.py feat_dict lookups); shim wired at `_make_X_hybrid`/`X_main`/`_predict_move`; guard-4 on ablate env; import-time FEATURE_COLS guard | **backtest bit-identical to baseline** (summary 5×16, trades 41×133, signals 982×24 — all 0 diffs). Registry `ACTIVE_ZONES={"pure"}`, MIGRATED=35 |
| **2 ✅** | 23 cross names renamed. features.py Zone-A (172 repl). inference.py: feat_dict lookups+injections→canonical (incl. `hmm_state`→`regime_hmm_id` inject at 737, `in_range_phase`→`h4move_is_ranging` at 761, two `["hmm_state"]` fallbacks); **result-dict/CSV KEYS kept legacy, values read canonical** (Zone-B untouched: bridge_data `log_signal` reads `result.get("hmm_state"/"in_range_phase"/"h4_resist_dist"…)`, `_log_trade` CSV cols legacy). Registry `ACTIVE_ZONES={"pure","cross"}`, MIGRATED=58 | **backtest bit-identical** (0 diffs, 41 trades) **+ live-path static-verified** (all bridge/DB reads hit preserved Zone-B legacy keys). ⚠️ `train.py` deferred to Phase 4 (retrain path: `feat_full + ["hmm_state"]`→`["regime_hmm_id"]`, `h4_df["in_range_phase"]`→`["h4move_is_ranging"]`) |
| **2** | cross-layer: `hmm_state`→`regime_hmm_id`, `in_range_phase`→`h4move_is_ranging`, write-site translations | identical output + bridge dry-run + DB insert/select sanity |
| **3** | ADX/DI boundary rename | identical output + **`compare_adx_parity.py` still passes** |
| **4** | retrain (separate): PRE_BACKTEST_AUDIT → retrain (canonical `feature_names` in meta) → POST_BACKTEST_AUDIT | live old models on shim meanwhile |

Local commit after each phase (no push until Imtiyaz says so — standing rule).

## 7. Fable-5's single strongest recommendation (verbatim intent)

> Make the new readable names canonical **only** in the ML pipeline (Zone-A);
> keep DB columns, signal-CSV schema and raw indicator CSVs legacy forever —
> persisted-schema stability is the foundation, not its name — and lock the
> whole thing with a registry + guards. The `hmm_state` int-feature →
> `regime_hmm_id` split is the single biggest permanent win; reopening the ADX
> raw layer the same day parity stabilized would be the biggest mistake. The
> house is made strong by the guards, not the rename: the rename happens once,
> the guards catch errors on every startup.
