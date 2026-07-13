"""
leakage_guard.py
─────────────────
Single source of truth for detecting + BLOCKING train/backtest data-leakage
(train-test date overlap) across the QGAI training + replay-backtest pipeline.

Root problem this fixes (Imtiyaz, 2026-07-13): several 2026-07-12 "Stage-1
3-month retrain backtest" screens called train.py with no QGAI_TRAIN_CUTOFF,
then replayed a backtest window that started INSIDE the labeled-trades date
range train.py had just trained on (training data ends 2026-04-29; those
backtests started 2026-04-01) → the model had literally seen the labels for
the first ~29 days of its own "out-of-sample" test. A printed warning is not
enough — this module makes that scenario impossible to run silently.

Design: every model file train.py saves gets a "<name>_meta.json" sidecar
recording the LATEST date of data it was exposed to (train + validation +
test + calibration — anything that touched weight-fitting, early-stopping,
hyperparameter selection, or isotonic calibration counts as exposure, not
just the raw training split). Before backtest_replay.py runs, this module
scans every required sidecar, takes the MAX across all of them (the
single latest-exposed component is the real bottleneck — trusting only one
file's date is exactly the bug we're fixing), and hard-refuses to run
if that date is on-or-after the backtest's start date.

No implicit escape hatches: the only way to run a genuinely in-sample
"sanity" backtest (e.g. current live model over full 2022→2026 history,
understood by the team as a quick look, never a profit-decision) is the
explicit --allow-in-sample flag on backtest_replay.py, which prints a loud
non-missable banner and must never be silently defaulted on.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

# Every model file the LIVE inference engine (bridge + backtest_replay, via
# inference.LiveInferenceEngine) actually loads AND that drives entry/exit
# signals. Missing one of these sidecars = hard failure, not a warning, and
# its cutoff date is part of the blocking max().
REQUIRED_META = {
    "model_meta.json":          "main (combined) model",
    "buy_model_meta.json":      "BUY directional model",
    "sell_model_meta.json":     "SELL directional model",
    "model_ranging_meta.json":  "Ranging state model",
    "model_trending_meta.json": "Trending state model",
    "model_volatile_meta.json": "Volatile state model",
    "hmm_meta.json":            "HMM regime model",
    "slot_table_meta.json":     "slot/day win-rate table",
}

# Loaded by inference.py but NOT gating (train.py comment: "They don't gate
# entries — combined+buy+sell drive signals"). Also, by design, WFO retrains
# these SKIPPED per-fold (QGAI_CORE_ONLY=1, deliberately reused across folds
# — see train.py Step 8) — so their on-disk cutoff is routinely from an
# older, non-fold-matched full retrain. Requiring their cutoff to predate
# every WFO fold's backtest_start would false-block the entire WFO
# methodology. Sidecar must still exist (hygiene) but its cutoff is
# informational only, excluded from the blocking max().
NON_GATING_META = {
    "big_win_model_meta.json":  "BigWin predictor (non-gating)",
    "duration_model_meta.json": "Duration predictor (non-gating)",
}

# Loaded by inference.py but hold NO historical data at save time (freshly
# initialised containers, populated only by live/replay-time online
# updates that only ever see PAST bars of that same run — not a train-cutoff
# leak in the sense this guard checks). Their meta must still exist (so a
# genuinely missing file is still caught) but is exempt from the cutoff
# date requirement as long as it says so explicitly.
NO_EXPOSURE_META = {
    "online_model_meta.json":   "Online learner",
    "drift_detector_meta.json": "Drift detector",
}

CUTOFF_FIELDS = ["training_end", "validation_end", "calibration_end",
                  "test_end", "feature_data_end"]


def _date(s):
    if not s:
        return None
    return pd.Timestamp(s).normalize()


def load_all_meta(models_dir) -> dict:
    """Read every required *_meta.json in models_dir. Hard failure (raises)
    if any REQUIRED/NO_EXPOSURE file is missing — never just a warning.
    NON_GATING_META (big_win/duration) is best-effort: WFO deliberately never
    recreates these per-fold (train.py Step 8, QGAI_CORE_ONLY=1), and a fresh
    checkout may have none yet — loaded if present, silently skipped if not,
    since their cutoff is excluded from the blocking max anyway."""
    models_dir = Path(models_dir)
    out = {}
    missing = []
    for fname, label in NON_GATING_META.items():
        p = models_dir / fname
        if p.exists():
            out[fname] = json.loads(p.read_text(encoding="utf-8"))
    for group in (REQUIRED_META, NO_EXPOSURE_META):
        for fname, label in group.items():
            p = models_dir / fname
            if not p.exists():
                missing.append((fname, label))
                continue
            out[fname] = json.loads(p.read_text(encoding="utf-8"))
    if missing:
        names = "\n    ".join(f"{f}  ({l})" for f, l in missing)
        raise RuntimeError(
            "LEAKAGE GUARD: required model metadata missing:\n    " + names +
            "\n  Retrain with the current train.py (it writes a *_meta.json "
            "sidecar for every model) before running a backtest. Missing "
            "metadata is a hard failure, not a warning — a backtest cannot "
            "prove it's leak-free without it."
        )
    return out


def effective_cutoff_of(fname: str, meta: dict):
    """Latest exposure date for ONE model's metadata, across all cutoff
    fields. Returns None for NO_EXPOSURE_META entries that declare so."""
    if fname in NO_EXPOSURE_META:
        if not meta.get("no_data_exposure"):
            raise RuntimeError(
                f"LEAKAGE GUARD: {fname} is expected to be a fresh, "
                f"no-history container but is missing 'no_data_exposure: "
                f"true' — treat as unsafe, hard failure."
            )
        return None
    dates = [_date(meta.get(f)) for f in CUTOFF_FIELDS]
    dates = [d for d in dates if d is not None]
    if not dates:
        raise RuntimeError(
            f"LEAKAGE GUARD: {fname} has no usable cutoff date field "
            f"(expected one of {CUTOFF_FIELDS}) — treat as unsafe, hard "
            f"failure."
        )
    return max(dates)


def compute_effective_training_cutoff(models_dir):
    """Max exposure date across every GATING model component (NON_GATING_META
    is recorded for visibility but excluded from the blocking max — see the
    comment on NON_GATING_META for why).
    Returns (effective_cutoff: pd.Timestamp, per_model: {fname: cutoff-or-None})."""
    all_meta = load_all_meta(models_dir)
    per_model = {}
    for fname, meta in all_meta.items():
        per_model[fname] = effective_cutoff_of(fname, meta)
    gating_dated = {k: v for k, v in per_model.items()
                    if v is not None and k in REQUIRED_META}
    if not gating_dated:
        raise RuntimeError(
            "LEAKAGE GUARD: no gating model component reported a usable "
            "cutoff date — cannot verify leak-free status, hard failure."
        )
    effective = max(gating_dated.values())
    return effective, per_model


def print_leakage_report(per_model, effective, backtest_start, leaked,
                          allow_in_sample):
    start = pd.Timestamp(backtest_start).normalize()
    print("=" * 64)
    print("  LEAKAGE GUARD")
    print("=" * 64)
    for fname in sorted(per_model):
        c = per_model[fname]
        if c is not None:
            shown = c.date().isoformat()
        else:
            shown = "n/a (no data exposure)"
        tag = " [non-gating]" if fname in NON_GATING_META else ""
        print(f"  {fname:28s} cutoff = {shown}{tag}")
    print("-" * 64)
    print(f"  Training cutoff (effective)  : {effective.date()}")
    print(f"  Backtest start                : {start.date()}")
    print(f"  Leakage check                 : {'FAIL' if leaked else 'PASS'}")
    if leaked:
        clean_start = (effective + pd.Timedelta(days=1)).date()
        print(f"  Clean OOS period would start  : {clean_start}")
    else:
        print(f"  Clean OOS period              : {start.date()} onward")
    print("=" * 64)


def assert_no_leakage(models_dir, backtest_start, allow_in_sample=False):
    """The hard gate. Call this BEFORE running any backtest.

    Raises RuntimeError on ANY train/backtest date overlap unless
    allow_in_sample=True — which must be an explicit, operator-passed CLI
    flag, never a default. Even when allowed, prints a loud banner so an
    in-sample result can never be silently mistaken for OOS proof.
    """
    effective, per_model = compute_effective_training_cutoff(models_dir)
    start = pd.Timestamp(backtest_start).normalize()
    leaked = effective >= start   # equal counts as leakage — no free buffer day

    print_leakage_report(per_model, effective, start, leaked, allow_in_sample)

    if leaked and not allow_in_sample:
        clean_start = (effective + pd.Timedelta(days=1)).date()
        raise RuntimeError(
            f"DATA LEAKAGE BLOCKED: effective training cutoff "
            f"({effective.date()}) is not strictly before backtest start "
            f"({start.date()}). Fix by ONE of:\n"
            f"  (a) retrain with QGAI_TRAIN_CUTOFF set to a date before "
            f"{start.date()}, or\n"
            f"  (b) move --from to {clean_start} (first clean day after "
            f"every model's exposure), or\n"
            f"  (c) if this is a KNOWN in-sample sanity check (not a "
            f"profit-decision result), re-run with --allow-in-sample."
        )
    if leaked and allow_in_sample:
        print("  ⚠️  IN-SAMPLE MODE — explicitly allowed via --allow-in-sample.")
        print("  ⚠️  This result is NOT valid out-of-sample proof.")
        print("  ⚠️  Do not use it for any keep/reject/profit decision.")
    return effective, leaked
