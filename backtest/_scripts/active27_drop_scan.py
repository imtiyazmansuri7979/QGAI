import csv
import json
import os
import shutil
import subprocess
from datetime import datetime, date
from pathlib import Path


ROOT = Path(r"C:\QGAI")
ENGINE = ROOT / "engine"
MODEL_DIR = ROOT / "data" / "models" / "final"
BACKUP_ROOT = ROOT / "data" / "models" / "backups"
OUTBASE = ROOT / "backtest" / "results" / "active27_drop_SCAN_TEST"
PY = Path(r"C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe")
TRAIN = ENGINE / "train.py"
REPLAY = ENGINE / "backtest_replay.py"

# Strict OOS boundary. BAT may also set these, but this script enforces them itself.
TRAINING_CUTOFF = os.environ.get("QGAI_TRAIN_CUTOFF", "2026-03-31").strip()
REQUIRE_VERIFIED_MODEL_METADATA = True

CUTOFF_KEYS = {
    "effective_training_cutoff",
    "training_cutoff",
    "training_end",
    "train_end",
    "calibration_end",
    "validation_end",
    "test_end",
    "feature_data_end",
    "slot_day_table_cutoff",
    "hmm_cutoff",
}

BACKTEST_ARGS = [
    "--from", "2026-04-01",
    "--to", "2026-06-29",
    "--equity", "10000",
    "--fixed-lot", "0.01",
    "--risk", "3",
    "--ratchet", "auto",
    "--ratchet-buf-pct", "0.15",
    "--tp-regime",
    "--tp-equity-pct", "0",
    "--max-open", "1",
]

ACTIVE_27 = [
    "15_min_slot",
    "slot_win_rate",
    "slot_cos",
    "day_of_week",
    "price_pos",
    "body_pct",
    "in_range_phase",
    "M15_ADX",
    "H4_ADX",
    "M15_DI_diff",
    "M30_DI_diff",
    "H1_DI_diff",
    "H4_DI_diff",
    "h4_adx_slope",
    "h1_adx_slope",
    "h4_h1_regime_score",
    "range_pct",
    "move_1hr",
    "move_4hr",
    "momentum_aligned_1hr",
    "momentum_aligned_2hr",
    "momentum_aligned_4hr",
    "price_vs_ema200",
    "mins_to_next_3star",
    "mins_since_last_3star",
    "ts_bars_since_flip",
    "ts_htf_agreement",
]


def parse_iso_date(value: str, label: str) -> date:
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")).date()
    except Exception as exc:
        raise RuntimeError(f"Invalid {label}: {value!r}") from exc


def get_backtest_dates() -> tuple[date, date]:
    try:
        start = BACKTEST_ARGS[BACKTEST_ARGS.index("--from") + 1]
        end = BACKTEST_ARGS[BACKTEST_ARGS.index("--to") + 1]
    except (ValueError, IndexError) as exc:
        raise RuntimeError("BACKTEST_ARGS must contain --from and --to") from exc
    return parse_iso_date(start, "backtest start"), parse_iso_date(end, "backtest end")


def preflight_leakage_guard() -> None:
    cutoff = parse_iso_date(TRAINING_CUTOFF, "TRAINING_CUTOFF")
    backtest_start, backtest_end = get_backtest_dates()

    print("\n" + "=" * 72)
    print("LEAKAGE PREFLIGHT")
    print(f"Requested training cutoff : {cutoff.isoformat()}")
    print(f"Backtest start            : {backtest_start.isoformat()}")
    print(f"Backtest end              : {backtest_end.isoformat()}")

    if cutoff >= backtest_start:
        raise RuntimeError(
            "DATA LEAKAGE BLOCKED: training cutoff must be strictly earlier "
            f"than backtest start ({cutoff} >= {backtest_start})"
        )
    print("Date overlap check        : PASS")
    print("=" * 72)


def _collect_cutoffs(obj, source: str, found: list[tuple[str, date, str]]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).strip().lower()
            if key_l in CUTOFF_KEYS and value not in (None, "", []):
                try:
                    found.append((key_l, parse_iso_date(str(value), key_l), source))
                except RuntimeError:
                    pass
            _collect_cutoffs(value, source, found)
    elif isinstance(obj, list):
        for value in obj:
            _collect_cutoffs(value, source, found)


def verify_trained_model_cutoff() -> date:
    requested = parse_iso_date(TRAINING_CUTOFF, "TRAINING_CUTOFF")
    backtest_start, _ = get_backtest_dates()
    found: list[tuple[str, date, str]] = []

    for path in MODEL_DIR.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        _collect_cutoffs(payload, str(path), found)

    if not found:
        raise RuntimeError(
            "MODEL CUTOFF NOT VERIFIED: no recognised cutoff metadata found "
            f"under {MODEL_DIR}"
        )

    effective = max(item[1] for item in found)
    latest = [item for item in found if item[1] == effective]

    print("\nMODEL CUTOFF VERIFICATION")
    print(f"Requested cutoff          : {requested.isoformat()}")
    print(f"Effective metadata cutoff : {effective.isoformat()}")
    for key, cutoff, source in latest[:5]:
        print(f"  latest source           : {key}={cutoff} | {source}")

    if effective > requested:
        raise RuntimeError(
            "TRAINING CUTOFF VIOLATION: metadata is later than requested "
            f"({effective} > {requested})"
        )
    if effective >= backtest_start:
        raise RuntimeError(
            "DATA LEAKAGE BLOCKED: effective model cutoff must be before "
            f"backtest start ({effective} >= {backtest_start})"
        )

    print("Model cutoff check        : PASS")
    return effective


def safe_rmtree(path: Path) -> None:
    path = path.resolve()
    allowed = (ROOT / "backtest" / "results").resolve()
    if not str(path).lower().startswith(str(allowed).lower()):
        raise RuntimeError(f"Refusing to remove unsafe path: {path}")
    if path.exists():
        shutil.rmtree(path)


def copy_dir(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def restore_models(backup: Path) -> None:
    if MODEL_DIR.exists():
        shutil.rmtree(MODEL_DIR)
    shutil.copytree(backup, MODEL_DIR)


def run_cmd(cmd, env) -> None:
    proc = subprocess.run(cmd, cwd=str(ENGINE), env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(map(str, cmd))}")


def read_summary(outdir: Path) -> dict:
    path = outdir / "backtest_summary_st-htf.csv"
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))
    return {
        "trades": int(float(row["trades"])),
        "wr_pct": float(row["wr_pct"]),
        "pf": float(row["pf"]),
        "avg_r": float(row["avg_r"]),
        "total_r": float(row["total_r"]),
        "net_return_pct": float(row["net_return_pct"]),
        "max_dd_pct": float(row["max_dd_pct"]),
    }


def run_case(name: str, drop_feature: str) -> dict:
    outdir = OUTBASE / name
    safe_rmtree(outdir)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["QGAI_CTF_FADE"] = "0"
    env["QGAI_UNPRUNE"] = ""
    env["QGAI_ABLATE"] = drop_feature
    env["QGAI_TRAIN_CUTOFF"] = TRAINING_CUTOFF
    env["QGAI_STRICT_CUTOFF"] = "1"

    print("\n" + "-" * 72)
    print(f"[{name}]")
    print(f"ABLATE = {drop_feature or '(baseline current 27)'}")
    print("Retraining...")
    run_cmd([str(PY), "-u", str(TRAIN)], env)
    effective_cutoff = verify_trained_model_cutoff()
    env["QGAI_EFFECTIVE_MODEL_CUTOFF"] = effective_cutoff.isoformat()
    print("Backtesting...")
    run_cmd([str(PY), "-u", str(REPLAY), *BACKTEST_ARGS, "--out-dir", str(outdir)], env)
    result = read_summary(outdir)
    result["outdir"] = str(outdir)
    return result


def main() -> int:
    preflight_leakage_guard()

    if not MODEL_DIR.exists():
        print(f"MODEL DIR NOT FOUND: {MODEL_DIR}")
        return 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_ROOT / f"ACTIVE27_DROP_PRE_{stamp}"
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    copy_dir(MODEL_DIR, backup)
    OUTBASE.mkdir(parents=True, exist_ok=True)

    rows = []
    try:
        baseline = run_case("B00_baseline", "")
        baseline_r = baseline["total_r"]
        rows.append({
            "rank": "",
            "test": "B00_baseline",
            "feature": "",
            "action": "baseline",
            "diff_vs_baseline": 0.0,
            "decision": "BASELINE",
            **baseline,
        })

        for idx, feature in enumerate(ACTIVE_27, start=1):
            name = f"D{idx:02d}_drop_{feature}"
            result = run_case(name, feature)
            diff = round(result["total_r"] - baseline_r, 3)
            if diff > 0:
                decision = "PRUNE_CANDIDATE"
            elif diff < 0:
                decision = "KEEP_IMPORTANT"
            else:
                decision = "NEUTRAL"
            rows.append({
                "rank": "",
                "test": name,
                "feature": feature,
                "action": "drop_active_feature",
                "diff_vs_baseline": diff,
                "decision": decision,
                **result,
            })
            print(f"{feature}: {decision} ({diff:+.1f}R vs baseline)")

        ranked = sorted(rows[1:], key=lambda r: r["diff_vs_baseline"], reverse=True)
        for i, row in enumerate(ranked, start=1):
            row["rank"] = i
        ordered = [rows[0], *ranked]

        summary_path = OUTBASE / "_active27_drop_summary.csv"
        fieldnames = [
            "rank", "test", "feature", "action", "decision", "diff_vs_baseline",
            "trades", "wr_pct", "pf", "avg_r", "total_r", "net_return_pct",
            "max_dd_pct", "outdir",
        ]
        with summary_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(ordered)

        print("\n" + "=" * 72)
        print("ACTIVE-27 DROP SCAN DONE")
        print(f"Baseline R: {baseline_r:.1f}R")
        print(f"Summary: {summary_path}")
        print("=" * 72)
        return 0
    except Exception as exc:
        print(f"\nFAILED: {exc}")
        return 1
    finally:
        print("\nRestoring original live model...")
        restore_models(backup)
        print("Original live model restored.")


if __name__ == "__main__":
    raise SystemExit(main())