#!/usr/bin/env python3
"""
run_feature_sweep.py
─────────────────────
Systematic feature-by-feature validation sweep (Imtiyaz spec, 2026-07-13,
refined with the detailed 3-stage priority plan): check each of the 67 known
features (27 active + 40 dropped, features.py FEATURE_COLS + _ZERO_IMP) one
at a time, priority-ordered, via a clean 3-month retrain + backtest.

LEAKAGE-GUARD-SAFE: QGAI_TRAIN_CUTOFF is set explicitly BEFORE the backtest
window below, unlike the 2026-07-12 mistake that started this whole audit.
leakage_guard.py will hard-block any run that isn't.

Each feature is auto-routed to the correct test mechanism based on whether
it's CURRENTLY ACTIVE or CURRENTLY DROPPED (checked against features.py at
run time, not hardcoded per tier — a tier list can freely mix active and
dropped names, e.g. the "priority_batch" tier below does):
  - ACTIVE feature  -> temporarily ABLATE it (QGAI_ABLATE) vs baseline.
    R gets WORSE without it -> pulling real weight, KEEP.
  - DROPPED feature -> temporarily RESTORE it (QGAI_UNPRUNE) vs baseline.
    R IMPROVES with it back -> candidate to re-add (still needs the same
    combo-interference check PART-1's B3-only decision hit).

Per feature, also computes (from the real trades CSV, not just the summary
report): regime breakdown (Ranging/Trending/Volatile), BUY vs SELL
breakdown, and week-by-week R (to catch "improvement from 2 lucky trades in
1 week" rather than a genuinely consistent effect).

Usage:
  python run_feature_sweep.py --tier priority_batch      (10 features, run first/tonight)
  python run_feature_sweep.py --tier active               (27 features, Stage 1)
  python run_feature_sweep.py --tier high_prob             (Stage 2)
  python run_feature_sweep.py --tier remaining             (Stage 3)
  python run_feature_sweep.py --tier active --limit 20     (Stage 1, day-1 subset)

Resume-safe: a feature whose result.json already exists is skipped and its
cached numbers are reused — safe to stop and restart across the "3-4
overnight runs" this was built for. Every run is a REAL retrain + REAL
backtest on your own PC (house rule: no heavy runs happen inline in chat).
"""
import argparse, csv, json, os, re, subprocess, sys, time
from datetime import datetime
from pathlib import Path

ENGINE = Path(__file__).parent
sys.path.insert(0, str(ENGINE))
from features import FEATURE_ALIASES, FEATURE_COLS, _ZERO_IMP  # noqa: E402


def alias_of(feat):
    a, ind = FEATURE_ALIASES.get(feat, (feat, "?"))
    return f"{feat} [{a} / {ind}]"


def is_currently_active(feat):
    """True if `feat` is in the CURRENT live FEATURE_COLS (test = ablate);
    False if it's currently dropped/pruned (test = unprune). Auto-detected
    at run time so a tier list can freely mix both kinds."""
    return feat in FEATURE_COLS and feat not in _ZERO_IMP


BT_RESULTS = ENGINE.parent / "backtest" / "results"
SWEEP_DIR = Path(os.environ.get("QGAI_FEATURE_SWEEP_DIR", str(BT_RESULTS / "feature_sweep")))
SWEEP_DIR.mkdir(parents=True, exist_ok=True)

# 2026-07-13 (Imtiyaz, root-cause fix after 3 same-day model-loss incidents):
# every retrain in this sweep goes to a DEDICATED, separate models folder via
# QGAI_MODELS_DIR (config.py) -- NEVER data/models/final. The live model is
# now structurally unreachable from this script, no backup/restore dance
# needed at all.
TEST_WORKSPACE = ENGINE.parent / "data" / "models" / "test_workspace"
TEST_WORKSPACE.mkdir(parents=True, exist_ok=True)

PY = sys.executable

# Default clean 3-month OOS window. Registry runners may override these via
# env vars when they need an apples-to-apples confirmation against a different
# master baseline, e.g. OOS1Y-01 uses 2025-06-28 / 2025-06-29 -> 2026-06-29.
TRAIN_CUTOFF = os.environ.get("QGAI_SWEEP_TRAIN_CUTOFF", "2026-03-31")
BT_FROM = os.environ.get("QGAI_SWEEP_FROM", "2026-04-01")
BT_TO   = os.environ.get("QGAI_SWEEP_TO", "2026-06-29")
BT_ARGS = ["--from", BT_FROM, "--to", BT_TO, "--equity", "10000",
           "--fixed-lot", "0.01", "--risk", "3", "--ratchet", "auto",
           "--ratchet-buf-pct", "0.15", "--tp-regime", "--tp-equity-pct", "0",
           "--max-open", "1"]

# ── PRIORITY BATCH (10) — Imtiyaz's exact "first test tonight" list.
# Mixed active+dropped on purpose; auto-routed to ablate/unprune per feature.
# NOTE: tick_volume tested RAW only, no normalization, no hard rule — model
# decides for itself, baseline vs volume-added compared like everything else.
PRIORITY_BATCH_TIER = [
    "h4_support_dist", "h1_resist_dist", "move_2hr", "ts_line_dist_pct",
    "tick_volume", "H4_DI_diff", "h4_adx_slope", "move_4hr",
    "momentum_aligned_2hr", "h1_support_dist",
]

# ── ACTIVE (27) — Stage 1, priority = current feature_importance.csv,
# descending. Imtiyaz's specifically-flagged active features (move_1hr,
# momentum_aligned_1hr/2hr/4hr, M15/H1/H4_DI_diff, h4_adx_slope, h1_adx_slope,
# move_4hr) already rank in the top ~24 here, so a day-1 "--limit 20" run
# naturally covers all of them without manual curation.
ACTIVE_TIER = [
    "move_1hr", "price_pos", "momentum_aligned_1hr", "momentum_aligned_4hr",
    "slot_win_rate", "ts_htf_agreement", "M15_ADX", "mins_to_next_3star",
    "M15_DI_diff", "M30_DI_diff", "slot_cos", "H4_ADX", "h1_adx_slope",
    "momentum_aligned_2hr", "body_pct", "day_of_week", "range_pct",
    "15_min_slot", "move_4hr", "h4_h1_regime_score", "h4_adx_slope",
    "H1_DI_diff", "price_vs_ema200", "H4_DI_diff", "mins_since_last_3star",
    "in_range_phase", "ts_bars_since_flip",
]

# ── DROPPED, HIGH PROBABILITY (Stage 2) — the SMMA-trend family (directly
# relevant to the 2026-07-13 architecture-rethink finding), raw ADX
# redundancy re-confirm, OB/SR family, regime composites. The 6 items from
# Imtiyaz's stage-2 list that are in PRIORITY_BATCH_TIER already are NOT
# repeated here (h4_support_dist, h1_resist_dist, move_2hr, ts_line_dist_pct,
# tick_volume, h1_support_dist) — tested first, no need to duplicate.
HIGH_PROB_TIER = [
    "ts_trend_h1", "ts_trend_h4", "ts_trend_m15",
    "ts_aligned_htf", "ts_adx_switch_trend", "ts_flip_recent",
    "H1_ADX", "M30_ADX",
    "move_8hr",
    # "corr_imp_ratio" removed 2026-07-16 — its computation was deleted from
    # features.py (dead leaky code cleanup); QGAI_UNPRUNE would now be a no-op
    # (nothing computes a real value to unprune). See features.py's
    # _MANUAL_PRUNE comment for the full history.
    "h4_resist_dist",
    "h4_ob_strength", "h1_ob_strength",
    "trade_direction", "h4_trending_h1_aligned", "h4_ranging_h1_neutral",
    "h4_ranging_h1_extended",
]

# ── DROPPED, REMAINING (Stage 3) — everything else (move_8hr and
# tick_volume relocated to high_prob/priority_batch above).
REMAINING_TIER = [
    "above_ema200", "ema200_dist_abs", "near_ema200",
    "adx_trend_count", "before_eia", "big_move_direction",
    "is_dead_hour", "is_ny_session", "is_post_big_move", "is_post_news",
    "last_3star_dev_sign", "session_score",
    "upcoming_3star_count", "volume",
    "h1_in_ob_zone", "h4_in_ob_zone", "ts_aligned",
]

TIERS = {
    "priority_batch": PRIORITY_BATCH_TIER,
    "active": ACTIVE_TIER,
    "high_prob": HIGH_PROB_TIER,
    "remaining": REMAINING_TIER,
}


def parse_report(txt):
    out = {}
    for pat, key in [
        (r"Total:\s*([+-]?\d+\.?\d*)R", "total_r"),
        (r"Trades\s*:\s*(\d+)", "trades"),
        (r"Profit factor\s*:\s*(\d+\.?\d*)", "pf"),
        (r"Win rate\s*:\s*(\d+\.?\d*)%", "wr"),
        (r"Max drawdown\s*:\s*(\d+\.?\d*)%", "dd"),
    ]:
        m = re.search(pat, txt)
        out[key] = float(m.group(1)) if m else None
    # Captured/Avail line (2026-07-13, Fable-5 review): "captured +834 pts |
    # available 28,887 pts (all swings) / 653 net | efficiency 2.9% of path".
    # The sweep's whole point is to increase profit by capturing more of the
    # available move (goal: 10-20% of path) -- Total R alone can go up while
    # actual captured points stay flat or fall (e.g. fewer/tighter trades),
    # so this must be tracked alongside R, not inferred from it.
    m = re.search(
        r"captured\s*([+-]?[\d,]+)\s*pts\s*\|\s*available\s*([\d,]+)\s*pts\s*"
        r"\(all swings\)\s*/\s*([+-]?[\d,]+)\s*net\s*\|\s*efficiency\s*([+-]?\d+\.?\d*)%",
        txt)
    if m:
        out["captured_pts"] = float(m.group(1).replace(",", ""))
        out["available_pts"] = float(m.group(2).replace(",", ""))
        out["available_net_pts"] = float(m.group(3).replace(",", ""))
        out["efficiency_pct"] = float(m.group(4))
    else:
        out["captured_pts"] = out["available_pts"] = out["available_net_pts"] = out["efficiency_pct"] = None
    return out


def _run_streaming(cmd, env, log_path, tag):
    """Run a subprocess with LIVE console output (line-by-line, prefixed with
    `tag`) while also capturing everything to log_path. Fixes the earlier
    silent-for-minutes UX bug: subprocess.run(capture_output=True) buffers
    ALL output until the process exits, so a 2-5 minute train/backtest looked
    completely frozen with no sign of life (Imtiyaz flagged this same day)."""
    proc = subprocess.Popen(cmd, cwd=str(ENGINE), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)
    lines = []
    for line in proc.stdout:
        line = line.rstrip("\n")
        lines.append(line)
        print(f"    [{tag}] {line}")
    proc.wait()
    full_text = "\n".join(lines)
    Path(log_path).write_text(full_text, encoding="utf-8")
    return proc.returncode, full_text


def _analyze_trades_csv(out_dir):
    """Regime / direction / weekly breakdown from the real trades CSV (not
    just the printed report) — per Imtiyaz's detailed checklist: BUY/SELL
    effect, Ranging/Trending/Volatile effect, weekly consistency (so a
    result driven by 2 lucky trades in 1 week doesn't look like a stable
    edge). Returns {} on any failure (no pandas, missing file, etc.) rather
    than crashing the sweep — this is supplementary detail, not required."""
    try:
        import pandas as pd
    except Exception:
        return {}
    csvs = list(Path(out_dir).glob("*backtest_trades*.csv"))
    if not csvs:
        return {}
    try:
        df = pd.read_csv(csvs[0])
    except Exception:
        return {}
    if df.empty or "r_achieved" not in df.columns:
        return {}

    out = {}
    # Regime breakdown
    if "hmm_state" in df.columns:
        for regime in ("Ranging", "Trending", "Volatile"):
            d = df[df["hmm_state"] == regime]
            out[f"r_{regime.lower()}"] = round(d["r_achieved"].sum(), 2) if len(d) else 0.0
            out[f"n_{regime.lower()}"] = int(len(d))
    # BUY/SELL breakdown
    if "direction" in df.columns:
        for direction in ("BUY", "SELL"):
            d = df[df["direction"] == direction]
            out[f"r_{direction.lower()}"] = round(d["r_achieved"].sum(), 2) if len(d) else 0.0
            out[f"n_{direction.lower()}"] = int(len(d))
    # Weekly consistency: group by ISO week, count how many weeks are net-negative
    if "entry_time" in df.columns:
        try:
            wk = pd.to_datetime(df["entry_time"]).dt.to_period("W")
            weekly_r = df.groupby(wk)["r_achieved"].sum()
            out["weeks_total"] = int(len(weekly_r))
            out["weeks_negative"] = int((weekly_r < 0).sum())
            # biggest single trade's share of total R (0 or negative total -> skip ratio)
            total_r = df["r_achieved"].sum()
            if len(df) and abs(total_r) > 1e-9:
                out["top_trade_share_of_r"] = round(float(df["r_achieved"].abs().max() / abs(total_r)), 2)
        except Exception:
            pass
    return out


def _sweep_result_prefix():
    return os.environ.get("QGAI_FEATURE_SWEEP_RESULT_ID") or os.environ.get("RESULT_ID") or SWEEP_DIR.name


def _prefix_output_csvs(out_dir, label, sort_id=""):
    """Keep every generated CSV self-identifying even if it is copied out of
    its folder later. Example:
    FS67-01_priority_batch_001_ablate_move_4hr_backtest_trades.csv"""
    prefix = _sweep_result_prefix()
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", label)
    sort_part = f"{sort_id}_" if sort_id else ""
    for csv_path in Path(out_dir).glob("*.csv"):
        if csv_path.name.startswith(prefix + "_"):
            continue
        target = csv_path.with_name(f"{prefix}_{sort_part}{safe_label}_{csv_path.name}")
        if target.exists():
            continue
        csv_path.rename(target)


def _auto_verdict(is_active, delta, breakdown, baseline_trades, baseline_captured_pts=None):
    """Best-effort automated verdict per Imtiyaz's checklist. Hard-checkable
    rules only — the rest (e.g. "logical reason is strong") stays a human
    judgment call. A verdict here is NOT a final adoption decision — anything
    other than NEUTRAL_REDUNDANT / CONFIRMED_DROPPED still needs Stage 2
    (1-year) + Stage 3 (WFO) before being trusted, per your own stage-gate.

    Semantics differ by which mechanism was tested:
      ACTIVE feature (ablate test) — delta = R_without_it - R_with_it.
        delta << 0  -> removing it HURT performance -> feature MATTERS -> KEEP.
        delta >> 0  -> removing it IMPROVED performance -> DROP_CANDIDATE.
      DROPPED feature (unprune test) — delta = R_with_it - R_without_it.
        delta >> 0  -> adding it back HELPED -> NEEDS_1YEAR_CONFIRMATION.
        delta << 0  -> adding it back HURT -> CONFIRMED_DROPPED (stays out).
    """
    reasons = []
    if delta is None:
        return "REVIEW", ["no delta computed"]

    flat = abs(delta) <= 0.5
    active_matters   = is_active and delta < -0.5       # removing it hurt -> keep
    active_drop      = is_active and delta > 0.5        # removing it helped -> drop candidate
    dropped_helps    = (not is_active) and delta > 0.5  # adding it back helped
    dropped_confirmed_out = (not is_active) and delta < -0.5  # adding it back hurt

    def _stability_flags():
        """Shared guard-rails for any 'this looks good' outcome (checkable
        subset of Imtiyaz's pass criteria) -- returns a list of red-flag
        strings, empty if none found."""
        flags = []
        if breakdown.get("weeks_total", 0) >= 2:
            neg_ratio = breakdown.get("weeks_negative", 0) / breakdown["weeks_total"]
            if neg_ratio > 0.5:
                flags.append("more than half the weeks were net-negative despite total improving")
        if breakdown.get("top_trade_share_of_r", 0) >= 0.5:
            flags.append("a single trade drives >=50% of the total R -- not a stable edge")
        for d in ("buy", "sell"):
            n = breakdown.get(f"n_{d}")
            r = breakdown.get(f"r_{d}")
            if n and n >= 3 and r is not None and r < -1.0:
                flags.append(f"{d.upper()} side is net-negative ({r:+.1f}R over {n} trades)")
        for reg in ("ranging", "trending", "volatile"):
            n = breakdown.get(f"n_{reg}")
            r = breakdown.get(f"r_{reg}")
            if n and n >= 3 and r is not None and r < -2.0:
                flags.append(f"{reg} regime is heavily net-negative ({r:+.1f}R over {n} trades)")
        # Fable-5 strategy review (2026-07-13): the actual goal is capturing
        # MORE of the available price move (target 10-20% of path), not just
        # a higher Total R -- R can rise while captured points fall (fewer,
        # tighter-SL trades). A "helps"/"keep" verdict must not come at the
        # cost of capturing meaningfully fewer points.
        this_captured = breakdown.get("captured_pts")
        if baseline_captured_pts and this_captured is not None and baseline_captured_pts > 0:
            cap_delta_pct = (this_captured - baseline_captured_pts) / abs(baseline_captured_pts)
            if cap_delta_pct < -0.10:
                flags.append(f"captured points DOWN {abs(cap_delta_pct)*100:.0f}% vs baseline "
                             f"({baseline_captured_pts:+.0f} -> {this_captured:+.0f} pts) -- "
                             f"review capture quality; the strategy is capturing LESS of the available move")
        # Fable-5 review (2026-07-13): baseline_trades was accepted but never
        # used -- a "helps"/"drop" verdict driven by a big swing in TRADE
        # COUNT (not just R) isn't apples-to-apples vs the baseline.
        this_trades = breakdown.get("trades")
        if baseline_trades and this_trades is not None and baseline_trades > 0:
            trade_delta_pct = abs(this_trades - baseline_trades) / baseline_trades
            if trade_delta_pct > 0.30:
                flags.append(f"trade count moved {trade_delta_pct*100:.0f}% vs baseline "
                             f"({baseline_trades:.0f} -> {this_trades:.0f}) -- not apples-to-apples")
        return flags

    if flat:
        verdict = "NEUTRAL_REDUNDANT"
        reasons.append("Total R within +-0.5R of baseline")
    elif active_matters:
        verdict = "CORE_KEEP"
        reasons.append(f"Removing it changed Total R by {delta:+.1f}R -- it pulls real weight, keep it")
        flags = _stability_flags()
        if flags:
            verdict = "REGIME_OR_DIRECTIONAL_KEEP"
            reasons.append("keep confirmed, but concentrated in one side/regime -- review before treating as a general-purpose feature:")
            reasons.extend(flags)
    elif active_drop:
        verdict = "DROP_CANDIDATE"
        reasons.append(f"Removing it IMPROVED Total R by {-delta:+.1f}R -- candidate to drop (confirm before acting)")
        # Fable-5 review (2026-07-13): a DROP decision on an active feature is
        # at least as risky as a re-add decision -- give it the same guard-rails
        # (was previously asymmetric: only the "helps" verdicts got checked).
        flags = _stability_flags()
        if flags:
            verdict = "REVIEW"
            reasons.append("drop looks tempting, but the swing is concentrated / not apples-to-apples -- do NOT drop without checking:")
            reasons.extend(flags)
    elif dropped_confirmed_out:
        verdict = "CONFIRMED_DROPPED"
        reasons.append(f"Adding it back HURT Total R by {delta:+.1f}R -- correctly excluded")
    elif dropped_helps:
        verdict = "NEEDS_1YEAR_CONFIRMATION"
        reasons.append(f"Adding it back improved Total R by {delta:+.1f}R -- candidate to re-add")
        flags = _stability_flags()
        if flags:
            verdict = "REVIEW"
            reasons.extend(flags)
    return verdict, reasons


def run_one(label, ablate="", unprune="", sort_id=""):
    out_dir = SWEEP_DIR / label
    result_json = out_dir / "result.json"
    if result_json.exists():
        print(f"  [{label}] CACHED, skipping")
        return json.loads(result_json.read_text(encoding="utf-8"))

    out_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["QGAI_MODELS_DIR"] = str(TEST_WORKSPACE)   # never touches data/models/final
    env["QGAI_TRAIN_CUTOFF"] = TRAIN_CUTOFF
    env["QGAI_ABLATE"]  = ablate
    env["QGAI_UNPRUNE"] = unprune
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"   # so train.py's own prints flush immediately, not just at exit

    t0 = time.time()
    print(f"  [{label}] training (live output below)...")
    rc, _ = _run_streaming([PY, "train.py"], env, out_dir / "train.log", "train")
    if rc != 0:
        print(f"  [{label}] TRAIN FAILED - see {out_dir / 'train.log'}")
        return None

    print(f"  [{label}] backtesting (live output below)...")
    rc, report = _run_streaming([PY, "backtest_replay.py"] + BT_ARGS + ["--out-dir", str(out_dir)],
                                 env, out_dir / "backtest.log", "backtest")
    if rc != 0:
        print(f"  [{label}] BACKTEST FAILED/BLOCKED (leakage guard?) - see {out_dir / 'backtest.log'}")
        return None

    metrics = parse_report(report)
    metrics.update({"label": label, "ablate": ablate, "unprune": unprune,
                     "elapsed_sec": round(time.time() - t0, 1)})
    metrics.update(_analyze_trades_csv(out_dir))
    _prefix_output_csvs(out_dir, label, sort_id)
    result_json.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def load_reused_baseline():
    baseline_json = os.environ.get("QGAI_SWEEP_BASELINE_JSON", "").strip()
    if not baseline_json:
        return None
    path = Path(baseline_json)
    if not path.exists():
        raise FileNotFoundError(f"QGAI_SWEEP_BASELINE_JSON not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("label", "baseline")
    data.setdefault("ablate", "")
    data.setdefault("unprune", "")
    data["reused_from"] = str(path)
    return data


def main():
    ap = argparse.ArgumentParser(description="QGAI feature-by-feature validation sweep")
    ap.add_argument("--tier", choices=list(TIERS.keys()), required=True)
    ap.add_argument("--limit", type=int, default=0,
                     help="only test the first N features this tier (0 = all)")
    ap.add_argument("--only", default="",
                    help="comma-separated feature names to run from this tier only")
    args = ap.parse_args()

    features = TIERS[args.tier]
    if args.only.strip():
        wanted = [f.strip() for f in args.only.split(",") if f.strip()]
        missing = [f for f in wanted if f not in features]
        if missing:
            print(f"--only contains feature(s) not in tier {args.tier}: {', '.join(missing)}")
            return 1
        features = wanted
    if args.limit > 0:
        features = features[:args.limit]

    print(f"[setup] All retrains in this sweep go to a SEPARATE folder: {TEST_WORKSPACE}")
    print(f"[setup] data/models/final (live) is never touched by this script.")

    print("=" * 64)
    print(f"  FEATURE SWEEP -- tier={args.tier} ({len(features)} features)")
    print(f"  each feature auto-routed to ablate (if currently active) or")
    print(f"  unprune (if currently dropped) based on features.py right now")
    print(f"  train cutoff={TRAIN_CUTOFF} | backtest {BT_FROM} -> {BT_TO}")
    print("=" * 64)

    # Cache keys are TIER-INDEPENDENT (Fable-5 review, 2026-07-13): "baseline"
    # (no feature changed) and "ablate_<feat>" / "unprune_<feat>" are IDENTICAL
    # regardless of which tier asked for them. Without this, priority_batch's
    # 4 features that are also in the full active tier (H4_DI_diff,
    # h4_adx_slope, move_4hr, momentum_aligned_2hr) would each get retrained
    # TWICE (once under priority_batch_04_H4_DI_diff, once under
    # active_23_H4_DI_diff) -- and every tier's own "baseline" run (which
    # changes nothing) would ALSO be recomputed from scratch 4 times, wasting
    # ~30-60 min total across a 3-4 night campaign for zero new information.
    try:
        baseline = load_reused_baseline()
    except Exception as e:
        print(f"baseline reuse FAILED: {e}")
        return 1
    if baseline is not None:
        print(f"\n[baseline] REUSED from {baseline.get('reused_from')}")
    else:
        print("\n[baseline] current committed feature set, unchanged...")
        baseline = run_one("baseline", sort_id="000")
        if baseline is None:
            print("baseline FAILED -- aborting sweep (fix train.py/backtest_replay.py first)")
            return 1
    base_r = baseline.get("total_r") or 0.0
    base_trades = baseline.get("trades") or 0
    base_captured = baseline.get("captured_pts")
    print(f"  baseline: R={base_r} PF={baseline.get('pf')} WR={baseline.get('wr')}% "
          f"captured={base_captured} pts efficiency={baseline.get('efficiency_pct')}% of path")

    durs = []
    results = [baseline]
    for i, feat in enumerate(features, 1):
        t0 = time.time()
        is_active = is_currently_active(feat)
        label = f"{'ablate' if is_active else 'unprune'}_{feat}"
        print(f"\n[{i}/{len(features)}] {alias_of(feat)} ({'ablate' if is_active else 'unprune'})...")
        m = run_one(label, ablate=feat if is_active else "", unprune=feat if not is_active else "", sort_id=f"{i:03d}")
        if m is None:
            print(f"\nABORTING sweep: {label} failed. Fix the error above, then rerun; cached completed features will be reused.")
            return 1
        m["is_active"] = is_active
        results.append(m)
        delta = (m.get("total_r") or 0.0) - base_r
        verdict, reasons = _auto_verdict(is_active, delta, m, base_trades, base_captured)
        m["verdict"] = verdict
        m["verdict_reasons"] = "; ".join(reasons)
        print(f"  R={m.get('total_r')} (delta {delta:+.1f} vs baseline) | {verdict}")
        for r in reasons:
            print(f"    - {r}")
        if "r_buy" in m:
            print(f"    BUY {m.get('r_buy'):+.1f}R/{m.get('n_buy')}tr | SELL {m.get('r_sell'):+.1f}R/{m.get('n_sell')}tr")
        if "r_ranging" in m:
            print(f"    Ranging {m.get('r_ranging'):+.1f}R | Trending {m.get('r_trending'):+.1f}R | Volatile {m.get('r_volatile'):+.1f}R")
        if m.get("captured_pts") is not None:
            cap_delta = m["captured_pts"] - (base_captured or 0)
            print(f"    Captured {m['captured_pts']:+.0f} pts (delta {cap_delta:+.0f}) | "
                  f"efficiency {m.get('efficiency_pct')}% of path (baseline {baseline.get('efficiency_pct')}%)")
        durs.append(time.time() - t0)
        avg = sum(durs) / len(durs)
        left = (len(features) - i) * avg
        eta = datetime.fromtimestamp(time.time() + left).strftime("%H:%M")
        print(f"  time {durs[-1]/60:.1f}m | avg {avg/60:.1f}m | ~{left/60:.0f}m remaining | ETA {eta}")

    summary_prefix = _sweep_result_prefix() if os.environ.get("QGAI_FEATURE_SWEEP_RESULT_ID") or os.environ.get("RESULT_ID") else args.tier
    summary_path = SWEEP_DIR / f"{summary_prefix}_SUMMARY.csv"
    with open(summary_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["label", "feature", "alias", "indicator", "mode", "total_r", "trades", "pf", "wr", "dd",
                    "delta_vs_baseline", "captured_pts", "delta_captured_pts", "efficiency_pct",
                    "verdict", "verdict_reasons",
                    "r_buy", "n_buy", "r_sell", "n_sell",
                    "r_ranging", "n_ranging", "r_trending", "n_trending", "r_volatile", "n_volatile",
                    "weeks_total", "weeks_negative", "top_trade_share_of_r"])
        for r in results:
            _feat = r.get("ablate") or r.get("unprune") or ""
            _alias, _ind = FEATURE_ALIASES.get(_feat, ("", ""))
            _mode = "ablate" if r.get("ablate") else ("unprune" if r.get("unprune") else "baseline")
            delta = 0.0 if r is baseline else (r.get("total_r") or 0.0) - base_r
            _cap = r.get("captured_pts")
            _cap_delta = None if (r is baseline or _cap is None or base_captured is None) else round(_cap - base_captured, 1)
            w.writerow([r.get("label"), _feat, _alias, _ind, _mode, r.get("total_r"),
                       r.get("trades"), r.get("pf"), r.get("wr"), r.get("dd"), round(delta, 2),
                       _cap, _cap_delta, r.get("efficiency_pct"),
                       r.get("verdict", ""), r.get("verdict_reasons", ""),
                       r.get("r_buy"), r.get("n_buy"), r.get("r_sell"), r.get("n_sell"),
                       r.get("r_ranging"), r.get("n_ranging"), r.get("r_trending"), r.get("n_trending"),
                       r.get("r_volatile"), r.get("n_volatile"),
                       r.get("weeks_total"), r.get("weeks_negative"), r.get("top_trade_share_of_r")])
    print(f"\nSummary saved: {summary_path}")
    print("Every row's --out-dir also has the full backtest_report.txt + trades/signals CSVs.")
    print("\nVerdict legend: CORE_KEEP-equivalent = 'MATTERS'-style active features that hurt when")
    print("removed become DROP_CANDIDATE if flipped; NEEDS_1YEAR_CONFIRMATION = passed the 3-month")
    print("screen with no red flags found -- still needs Stage 2 (1-year) + Stage 3 (WFO) before trusting.")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
