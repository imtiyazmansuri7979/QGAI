#!/usr/bin/env python3
"""
run_feature_sweep.py
─────────────────────
Systematic feature-by-feature validation sweep (Imtiyaz spec, 2026-07-13):
check each of the 67 known features (27 active + 40 dropped, features.py
FEATURE_COLS + _ZERO_IMP) one at a time, priority-ordered, via a clean
3-month retrain + backtest.

LEAKAGE-GUARD-SAFE this time: QGAI_TRAIN_CUTOFF is set explicitly BEFORE the
backtest window below, unlike the 2026-07-12 mistake that started this whole
audit (train.py with no cutoff, backtest starting inside the training data's
own date range). leakage_guard.py will hard-block any run that isn't.

For an ACTIVE feature (tier=active): temporarily ABLATE it (QGAI_ABLATE) and
  compare vs baseline. R gets WORSE without it -> the feature is pulling real
  weight, keep it. R doesn't change / improves -> candidate to drop.
For a DROPPED feature (tier=high_prob / remaining): temporarily RESTORE it
  (QGAI_UNPRUNE) and compare vs baseline. R improves -> candidate to re-add
  (needs the same combo-interference check PART-1's B3-only decision hit).
  R doesn't improve -> stays correctly dropped.

Usage:
  python run_feature_sweep.py --tier active                (27 features)
  python run_feature_sweep.py --tier high_prob              (~20 features)
  python run_feature_sweep.py --tier remaining               (~20 features)
  python run_feature_sweep.py --tier active --limit 2        (quick TEST run)
  python run_feature_sweep.py --tier active --resume-only    (just re-print the
      summary from whatever's cached so far, no new runs)

Resume-safe: a feature whose result.json already exists is skipped and its
cached numbers are reused (same principle as run_wfo.py's per-week cache) —
safe to stop and restart across the "3-4 overnight runs" this was built for.
Every run is a REAL retrain + REAL backtest on your own PC (house rule: no
heavy runs happen inline in chat).
"""
import argparse, csv, json, os, re, subprocess, sys, time
from datetime import datetime
from pathlib import Path

ENGINE = Path(__file__).parent
sys.path.insert(0, str(ENGINE))
from features import FEATURE_ALIASES  # {feature_name: (alias, indicator)} -- readable labels for the report


def alias_of(feat):
    a, ind = FEATURE_ALIASES.get(feat, (feat, "?"))
    return f"{feat} [{a} / {ind}]"


BT_RESULTS = ENGINE.parent / "backtest" / "results"
SWEEP_DIR = BT_RESULTS / "feature_sweep"
SWEEP_DIR.mkdir(parents=True, exist_ok=True)

# 2026-07-13 (Imtiyaz, root-cause fix after 3 same-day model-loss incidents):
# every retrain in this sweep goes to a DEDICATED, separate models folder via
# QGAI_MODELS_DIR (config.py) -- NEVER data/models/final. The live model is
# now structurally unreachable from this script, no backup/restore dance
# needed at all.
TEST_WORKSPACE = ENGINE.parent / "data" / "models" / "test_workspace"
TEST_WORKSPACE.mkdir(parents=True, exist_ok=True)

PY = sys.executable

# Clean 3-month OOS window, leakage-guard-safe: training data (labeled trades)
# naturally ends 2026-04-29, so a cutoff of 2026-03-31 with backtest starting
# 2026-04-01 leaves a full clean 3-month replay with a real margin, not just
# the bare-minimum 1-day gap the guard requires.
TRAIN_CUTOFF = "2026-03-31"
BT_FROM = "2026-04-01"
BT_TO   = "2026-06-29"
BT_ARGS = ["--from", BT_FROM, "--to", BT_TO, "--equity", "10000",
           "--fixed-lot", "0.01", "--risk", "3", "--ratchet", "auto",
           "--ratchet-buf-pct", "0.15", "--tp-regime", "--tp-equity-pct", "0",
           "--max-open", "1"]

# ── ACTIVE (27) — priority = current feature_importance.csv, descending ──
ACTIVE_TIER = [
    "move_1hr", "price_pos", "momentum_aligned_1hr", "momentum_aligned_4hr",
    "slot_win_rate", "ts_htf_agreement", "M15_ADX", "mins_to_next_3star",
    "M15_DI_diff", "M30_DI_diff", "slot_cos", "H4_ADX", "h1_adx_slope",
    "momentum_aligned_2hr", "body_pct", "day_of_week", "range_pct",
    "15_min_slot", "move_4hr", "h4_h1_regime_score", "h4_adx_slope",
    "H1_DI_diff", "price_vs_ema200", "H4_DI_diff", "mins_since_last_3star",
    "in_range_phase", "ts_bars_since_flip",
]

# ── DROPPED, HIGH PROBABILITY (~20) — directly relevant to the 2026-07-13
# architecture-rethink finding (SMMA trend family) + raw ADX (D2/D3 redundancy
# re-confirm) + previously-flagged partial signals ──
HIGH_PROB_TIER = [
    "ts_trend_h1", "ts_trend_h4", "ts_trend_m15", "ts_line_dist_pct",
    "ts_aligned_htf", "ts_adx_switch_trend", "ts_flip_recent",
    "H1_ADX", "M30_ADX",
    "move_2hr", "corr_imp_ratio",
    "h4_resist_dist", "h1_resist_dist", "h4_support_dist", "h1_support_dist",
    "h4_ob_strength", "h1_ob_strength",
    "trade_direction", "h4_trending_h1_aligned", "h4_ranging_h1_neutral",
    "h4_ranging_h1_extended",
]

# ── DROPPED, REMAINING (~19) — everything else ──
REMAINING_TIER = [
    "above_ema200", "ema200_dist_abs", "near_ema200",
    "adx_trend_count", "before_eia", "big_move_direction",
    "is_dead_hour", "is_ny_session", "is_post_big_move", "is_post_news",
    "last_3star_dev_sign", "move_8hr", "session_score",
    "tick_volume", "upcoming_3star_count", "volume",
    "h1_in_ob_zone", "h4_in_ob_zone", "ts_aligned",
]

TIERS = {"active": ACTIVE_TIER, "high_prob": HIGH_PROB_TIER, "remaining": REMAINING_TIER}


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


def run_one(label, ablate="", unprune=""):
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
    result_json.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def main():
    ap = argparse.ArgumentParser(description="QGAI feature-by-feature validation sweep")
    ap.add_argument("--tier", choices=list(TIERS.keys()), required=True)
    ap.add_argument("--limit", type=int, default=0,
                     help="only test the first N features this tier (0 = all)")
    args = ap.parse_args()

    features = TIERS[args.tier]
    if args.limit > 0:
        features = features[:args.limit]
    is_active = args.tier == "active"

    print(f"[setup] All retrains in this sweep go to a SEPARATE folder: {TEST_WORKSPACE}")
    print(f"[setup] data/models/final (live) is never touched by this script.")

    print("=" * 64)
    print(f"  FEATURE SWEEP -- tier={args.tier} ({len(features)} features)")
    print(f"  mode: {'ABLATE (drop each active feature)' if is_active else 'UNPRUNE (restore each dropped feature)'}")
    print(f"  train cutoff={TRAIN_CUTOFF} | backtest {BT_FROM} -> {BT_TO}")
    print("=" * 64)

    print("\n[baseline] current committed feature set, unchanged...")
    baseline = run_one(f"{args.tier}_baseline")
    if baseline is None:
        print("baseline FAILED -- aborting sweep (fix train.py/backtest_replay.py first)")
        return
    base_r = baseline.get("total_r") or 0.0
    print(f"  baseline: R={base_r} PF={baseline.get('pf')} WR={baseline.get('wr')}%")

    durs = []
    results = [baseline]
    for i, feat in enumerate(features, 1):
        t0 = time.time()
        label = f"{args.tier}_{i:02d}_{feat}"
        print(f"\n[{i}/{len(features)}] {alias_of(feat)} ({'ablate' if is_active else 'unprune'})...")
        m = run_one(label, ablate=feat if is_active else "", unprune=feat if not is_active else "")
        if m is None:
            continue
        results.append(m)
        delta = (m.get("total_r") or 0.0) - base_r
        if is_active:
            tag = "MATTERS -- R drops without it, KEEP" if delta < -0.5 else \
                  "little/no effect -- candidate to drop" if abs(delta) <= 0.5 else \
                  "R IMPROVES without it -- candidate to drop"
        else:
            tag = "HELPS -- candidate to re-add" if delta > 0.5 else \
                  "little/no effect -- stays dropped" if abs(delta) <= 0.5 else \
                  "HURTS -- confirms correctly dropped"
        print(f"  R={m.get('total_r')} (delta {delta:+.1f} vs baseline) | {tag}")
        durs.append(time.time() - t0)
        avg = sum(durs) / len(durs)
        left = (len(features) - i) * avg
        eta = datetime.fromtimestamp(time.time() + left).strftime("%H:%M")
        print(f"  time {durs[-1]/60:.1f}m | avg {avg/60:.1f}m | ~{left/60:.0f}m remaining | ETA {eta}")

    summary_path = SWEEP_DIR / f"{args.tier}_SUMMARY.csv"
    with open(summary_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["label", "feature", "alias", "indicator", "ablate", "unprune",
                    "total_r", "trades", "pf", "wr", "dd", "delta_vs_baseline"])
        for r in results:
            _feat = r.get("ablate") or r.get("unprune") or ""
            _alias, _ind = FEATURE_ALIASES.get(_feat, ("", ""))
            delta = 0.0 if r is baseline else (r.get("total_r") or 0.0) - base_r
            w.writerow([r.get("label"), _feat, _alias, _ind, r.get("ablate"), r.get("unprune"),
                       r.get("total_r"), r.get("trades"), r.get("pf"), r.get("wr"), r.get("dd"),
                       round(delta, 2)])
    print(f"\nSummary saved: {summary_path}")
    print("Every row's --out-dir also has the full backtest_report.txt + trades/signals CSVs.")


if __name__ == "__main__":
    main()
