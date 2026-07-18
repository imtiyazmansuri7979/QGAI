# -*- coding: utf-8 -*-
"""
feature_registry.py — SINGLE SOURCE OF TRUTH for ML feature naming + the
permanent guards that keep naming errors from ever recurring.

WHY THIS EXISTS (Fable-5 architecture, 2026-07-18)
--------------------------------------------------
Feature names are identifiers that flow through several *zones* of the system.
A blind rename breaks cross-zone consistency. So we split by zone and keep ONE
canonical name per feature only inside the ML pipeline, while the persisted
schema (SQLite DB, signal-CSV headers, dashboard keys) and the raw indicator
CSV columns keep their legacy names forever.

    Zone-A  ML pipeline .... feat_dict keys, FEATURE_COLS, train/inference
                             lists, model.feature_names   -> CANONICAL (new)
    Zone-B  Persistence ..... SQLite columns, signal-CSV, dashboard keys
                             -> LEGACY (kept; schema, not vocabulary)
    Zone-C  Raw data ........ adx_merged.csv / indicators_merged.csv headers,
                             build_indicators / regen_adx / parity scripts
                             -> LEGACY (never touched)

The durable "foundation" is NOT the rename itself — it is the three guards
below, which run every startup and make silent drift impossible:

    1. remap_model_feature_names()  — load-shim: a model pickled with legacy
       feature_names still works on the renamed pipeline (rename<->retrain
       decoupled; no live downtime).
    2. assert_canonical()           — startup: model feature set must be a
       subset of the known canonical names, else hard-fail with the bad name.
    3. guard_feat_dict()            — compute_features() output must contain
       NO legacy feature name (silent train/serve skew caught on day one).
    + validate_feature_names()      — reject unknown names in QGAI_ABLATE /
       QGAI_UNPRUNE env lists (fixes the silent-no-op class, BUG_LOG #G-like).

ZONES / dtype are declared here explicitly so classification never drifts.
This module has NO heavy imports and is safe to import anywhere.
"""

# ─────────────────────────────────────────────────────────────
# THE REGISTRY  —  legacy_name : (canonical_name, zone, dtype)
# zone: "pure" | "cross" | "adx_raw" | "excluded"
#   pure     -> renamed in ML pipeline, no persistence entanglement
#   cross    -> renamed in ML pipeline; a legacy DB/signal key also exists
#               (translated explicitly at the few persistence write-sites)
#   adx_raw  -> renamed ONLY at the raw->feature boundary loop in features.py;
#               the raw CSV column keeps the legacy name
#   excluded -> not renamed at all (raw MT5 column + pruned feature)
# For hmm_state the canonical model-feature is an INT id; the *string* state
# name keeps the legacy key "hmm_state" in DB/logs (a different concept).
# ─────────────────────────────────────────────────────────────
REGISTRY = {
    # ---- TIMING (pure) ----
    "15_min_slot":            ("time_15min_slot",          "pure",  "num"),
    "slot_win_rate":          ("time_1hr_winrate",         "pure",  "num"),
    "slot_cos":               ("time_cyclical_encoding",   "pure",  "num"),
    "day_of_week":            ("time_weekday",             "pure",  "num"),
    "session_score":          ("time_session_quality_score","pure", "num"),
    "is_ny_session":          ("time_is_ny_session_flag",  "cross", "flag"),
    "is_dead_hour":           ("time_is_dead_hour_flag",   "cross", "flag"),
    # ---- ORDER BLOCK / S-R ----
    "h4_resist_dist":         ("ob_h4_resistance_pct",     "cross", "num"),
    "h4_support_dist":        ("ob_h4_support_pct",        "cross", "num"),
    "h4_ob_strength":         ("ob_h4_strength",           "pure",  "num"),
    "h4_in_ob_zone":          ("ob_h4_in_zone_flag",       "cross", "flag"),
    "h1_resist_dist":         ("ob_h1_resistance_pct",     "cross", "num"),
    "h1_support_dist":        ("ob_h1_support_pct",        "cross", "num"),
    "h1_ob_strength":         ("ob_h1_strength",           "pure",  "num"),
    "h1_in_ob_zone":          ("ob_h1_in_zone_flag",       "cross", "flag"),
    # ---- PRICE STRUCTURE / CANDLE ----
    "price_pos":              ("bb_price_position",        "pure",  "num"),
    "body_pct":               ("candle_body_ratio",        "cross", "num"),
    "range_pct":              ("candle_range_pct",         "cross", "num"),
    "in_range_phase":         ("h4move_is_ranging",        "cross", "flag"),
    "corr_imp_ratio":         ("swing_correction_impulse_ratio", "cross", "num"),
    "big_move_direction":     ("h4_bigmove_direction",     "pure",  "num"),
    "is_post_big_move":       ("h4_is_post_bigmove_flag",  "cross", "flag"),
    # ---- ADX / DI (raw indicator columns — boundary rename only) ----
    "M15_ADX":                ("adx_m15_strength",         "adx_raw", "num"),
    "M30_ADX":                ("adx_m30_strength",         "adx_raw", "num"),
    "H1_ADX":                 ("adx_h1_strength",          "adx_raw", "num"),
    "H4_ADX":                 ("adx_h4_strength",          "adx_raw", "num"),
    "M15_DI_diff":            ("di_m15_direction",         "adx_raw", "num"),
    "M30_DI_diff":            ("di_m30_direction",         "adx_raw", "num"),
    "H1_DI_diff":             ("di_h1_direction",          "adx_raw", "num"),
    "H4_DI_diff":             ("di_h4_direction",          "adx_raw", "num"),
    "h4_adx_slope":           ("adx_h4_momentum",          "cross", "num"),
    "h1_adx_slope":           ("adx_h1_momentum",          "cross", "num"),
    "adx_trend_count":        ("adx_multi_tf_trend_count", "pure",  "num"),
    "h4_h1_regime_score":     ("adx_regime_quality_score", "pure",  "num"),
    # ---- REGIME COMPOSITES ----
    "h4_ranging_h1_extended": ("regime_h4ranging_h1extended", "pure", "num"),
    "h4_ranging_h1_neutral":  ("regime_h4ranging_h1neutral",  "pure", "num"),
    "h4_trending_h1_aligned": ("regime_h4trending_h1aligned", "pure", "num"),
    # hmm_state: model-feature is an INT id (regime_hmm_id); the STRING state
    # name keeps the legacy key "hmm_state" everywhere in DB/logs/dashboard.
    "hmm_state":              ("regime_hmm_id",            "cross", "int"),
    # ---- PRICE MOMENTUM ----
    "move_1hr":               ("price_change_1hr_usd",     "pure",  "num"),
    "move_2hr":               ("price_change_2hr_usd",     "pure",  "num"),
    "move_4hr":               ("price_change_4hr_usd",     "pure",  "num"),
    "move_8hr":               ("price_change_8hr_usd",     "pure",  "num"),
    "momentum_aligned_1hr":   ("price_1hr_signal_agree",   "pure",  "num"),
    "momentum_aligned_2hr":   ("price_2hr_signal_agree",   "pure",  "num"),
    "momentum_aligned_4hr":   ("price_4hr_signal_agree",   "pure",  "num"),
    # ---- EMA200 ----
    "price_vs_ema200":        ("ema200_distance_usd",      "pure",  "num"),
    "above_ema200":           ("ema200_above_flag",        "pure",  "flag"),
    "ema200_dist_abs":        ("ema200_distance_abs_usd",  "pure",  "num"),
    "near_ema200":            ("ema200_near_flag",         "pure",  "flag"),
    # ---- NEWS ----
    "mins_to_next_3star":     ("news_mins_until_next",     "cross", "num"),
    "mins_since_last_3star":  ("news_mins_since_last",     "pure",  "num"),
    "upcoming_3star_count":   ("news_upcoming_count_2hr",  "pure",  "num"),
    "last_3star_dev_sign":    ("news_last_deviation_sign", "pure",  "num"),
    "before_eia":             ("news_before_eia_flag",     "pure",  "flag"),
    "is_post_news":           ("news_is_post_news_flag",   "cross", "flag"),
    # ---- TREND SIGNAL (SMMA) ----
    "ts_bars_since_flip":     ("smma_bars_since_flip",     "pure",  "num"),
    "ts_htf_agreement":       ("smma_htf_agreement",       "cross", "num"),
    "ts_trend_m15":           ("smma_trend_m15",           "cross", "num"),
    "ts_trend_h1":            ("smma_trend_h1",            "cross", "num"),
    "ts_trend_h4":            ("smma_trend_h4",            "cross", "num"),
    "ts_line_dist_pct":       ("smma_line_distance_pct",   "cross", "num"),
    "ts_flip_recent":         ("smma_recent_flip_flag",    "pure",  "flag"),
    "ts_aligned":             ("smma_all_tf_aligned_flag", "pure",  "flag"),
    "ts_aligned_htf":         ("smma_htf_aligned_flag",    "pure",  "flag"),
    "ts_adx_switch_trend":    ("smma_adx_switch_trend_flag","pure", "flag"),
    # ---- META ----
    "trade_direction":        ("trade_direction_flag",     "pure",  "num"),
    # ---- EXCLUDED (raw MT5 column + pruned feature; never renamed) ----
    "volume":                 ("volume",                   "excluded", "num"),
    "tick_volume":            ("tick_volume",              "excluded", "num"),
}

# ─────────────────────────────────────────────────────────────
# Derived lookup tables (built once at import).
# ─────────────────────────────────────────────────────────────
LEGACY_TO_NEW = {old: new for old, (new, _z, _d) in REGISTRY.items()}
NEW_TO_LEGACY = {new: old for old, new in LEGACY_TO_NEW.items()}
ZONE          = {old: z   for old, (_n, z, _d) in REGISTRY.items()}
DTYPE         = {new: d   for old, (new, _z, d) in REGISTRY.items()}

# Names that actually change (exclude identity pairs like volume/tick_volume)
_RENAMED = {old: new for old, new in LEGACY_TO_NEW.items() if old != new}

# The set of every valid CANONICAL feature name (what the ML pipeline uses).
ALL_CANONICAL = set(LEGACY_TO_NEW.values())

# ─────────────────────────────────────────────────────────────
# PHASED MIGRATION CONTROL — the single knob that advances the rollout.
# A feature is "migrated" once compute_features() emits its CANONICAL name in
# feat_dict. Until then it stays legacy in feat_dict, so the load-shim must NOT
# remap it (or a still-legacy model name would miss it, and vice-versa).
# Advance by adding the next zone:  {"pure"} -> +"cross" -> +"adx_raw".
# "excluded" is never migrated (raw MT5 columns).
# ─────────────────────────────────────────────────────────────
ACTIVE_ZONES = {"pure", "cross", "adx_raw"}  # Phase 3 (all rename zones live).

MIGRATED = {old for old, (new, z, d) in REGISTRY.items()
            if z in ACTIVE_ZONES and old != new}
# active legacy->canonical map (only migrated features)
ACTIVE_MAP = {old: LEGACY_TO_NEW[old] for old in MIGRATED}


def remap_model_feature_names(names):
    """GUARD 1 — load-shim (phase-aware). Remap ONLY already-migrated legacy
    names to canonical, so a model pickled with legacy names lines up with the
    partially-renamed feat_dict. Un-migrated legacy names are left as-is on
    purpose (feat_dict still emits them legacy this phase)."""
    if not names:
        return names
    return [ACTIVE_MAP.get(n, n) for n in names]


def to_legacy(name):
    """Zone-B helper: canonical -> legacy DB/signal key (identity if none)."""
    return NEW_TO_LEGACY.get(name, name)


def to_canonical(name):
    """legacy -> canonical (identity if already canonical / unknown)."""
    return LEGACY_TO_NEW.get(name, name)


def assert_canonical(feature_names, where="model"):
    """GUARD 2 — startup assertion (phase-aware). After remap, no MIGRATED
    legacy name may survive — that would mean the shim failed to line the model
    up with the renamed feat_dict, i.e. train/serve skew. Caught here instead
    of surfacing as silent zeros at predict time. Names outside the registry
    (e.g. band_width_pct, hmm_state) and un-migrated legacy names are allowed."""
    remapped = remap_model_feature_names(feature_names)
    survived = [n for n in remapped if n in MIGRATED]
    if survived:
        raise ValueError(
            f"[feature_registry] {where}: migrated-legacy name(s) survived "
            f"remap: {survived}. Model/pipeline out of sync — expected "
            f"canonical {[LEGACY_TO_NEW[n] for n in survived]}.")
    return remapped


def guard_feat_dict(feat_dict, where="compute_features"):
    """GUARD 3 — no MIGRATED legacy feature name may leak out of the feature
    builder. Un-migrated legacy keys (cross/adx in earlier phases) are allowed
    until their phase lands; internal '_'-keys ignored."""
    leaked = [k for k in feat_dict.keys() if k in MIGRATED]
    if leaked:
        raise ValueError(
            f"[feature_registry] {where}: migrated-legacy feature key(s) "
            f"leaked: {leaked}. Use canonical "
            f"{[LEGACY_TO_NEW[k] for k in leaked]} instead.")
    return feat_dict


def validate_feature_names(names, where="QGAI_ABLATE"):
    """GUARD 4 — reject unknown names in ablation/prune env lists so a
    stale legacy name does not silently no-op (BUG_LOG #G-class)."""
    bad = [n for n in names
           if n and n not in ALL_CANONICAL and n not in LEGACY_TO_NEW]
    if bad:
        raise ValueError(
            f"[feature_registry] {where}: unknown feature name(s) {bad}. "
            f"Check spelling against feature_registry.REGISTRY.")
    return [to_canonical(n) for n in names if n]


if __name__ == "__main__":
    # ── Self-test: registry integrity + agreement with features.FEATURE_ALIASES
    assert len(REGISTRY) == 68, f"expected 68 entries, got {len(REGISTRY)}"
    # canonical names unique
    canon = list(LEGACY_TO_NEW.values())
    dupes = {c for c in canon if canon.count(c) > 1 and c not in ("volume", "tick_volume")}
    assert not dupes, f"duplicate canonical names: {dupes}"
    # zone counts
    from collections import Counter
    zc = Counter(ZONE.values())
    print("Zone counts:", dict(zc))
    assert zc["excluded"] == 2
    assert zc["adx_raw"] == 8
    print(f"pure={zc['pure']}  cross={zc['cross']}  "
          f"(pure+cross={zc['pure']+zc['cross']})")

    # Agreement with the alias table still in features.py (catch drift).
    import re, io, os
    fp = os.path.join(os.path.dirname(__file__), "features.py")
    txt = io.open(fp, encoding="utf-8").read()
    m = re.search(r"FEATURE_ALIASES = \{(.*?)\n\}\n", txt, re.S)
    pairs = dict(re.findall(r'"([A-Za-z0-9_]+)":\s*\("([A-Za-z0-9_]+)"', m.group(1)))
    # excluded pair is intentionally identity here but has a display-only
    # alias in FEATURE_ALIASES — allow that one difference.
    mismatch = {k: (LEGACY_TO_NEW[k], pairs.get(k))
                for k in LEGACY_TO_NEW
                if pairs.get(k) != LEGACY_TO_NEW[k]
                and ZONE[k] != "excluded"}
    assert not mismatch, f"registry<->FEATURE_ALIASES drift: {mismatch}"

    # Guard smoke tests (phase-agnostic — derive expectations from MIGRATED)
    print("ACTIVE_ZONES:", ACTIVE_ZONES, "| MIGRATED count:", len(MIGRATED))
    _mig_ex  = next(iter(MIGRATED))                       # a migrated legacy name
    _unmig   = next((l for l in LEGACY_TO_NEW              # an un-migrated legacy name
                     if l not in MIGRATED and l != LEGACY_TO_NEW[l]), None)
    # migrated legacy name always remaps to its canonical
    assert remap_model_feature_names([_mig_ex])[0] == LEGACY_TO_NEW[_mig_ex], "remap wrong"
    # guard fires on a MIGRATED legacy key
    try:
        guard_feat_dict({_mig_ex: 1}); raise SystemExit("guard failed to fire")
    except ValueError:
        pass
    if _unmig is not None:                                 # only before the final phase
        assert remap_model_feature_names([_unmig]) == [_unmig], "un-migrated must pass through"
        guard_feat_dict({_unmig: 1})                       # un-migrated -> allowed
    assert_canonical([_mig_ex, "band_width_pct"])          # remap lines it up
    try:
        validate_feature_names(["nonexistent_feat"]); raise SystemExit("validate failed")
    except ValueError:
        pass
    print("feature_registry self-test: ALL PASS")
