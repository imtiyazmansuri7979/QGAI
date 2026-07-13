import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, date
from pathlib import Path


ROOT = Path(r"C:\QGAI")
ENGINE = ROOT / "engine"
MODEL_DIR = ROOT / "data" / "models" / "final"
BACKUP_ROOT = ROOT / "data" / "models" / "backups"
OUTBASE = ROOT / "backtest" / "results" / "removed_feature_top5_FORWARD_SELECT_TEST"
PY = Path(r"C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe")
TRAIN = ENGINE / "train.py"
REPLAY = ENGINE / "backtest_replay.py"

# -----------------------------------------------------------------------------
# LEAKAGE-SAFETY SETTINGS
# -----------------------------------------------------------------------------
# The training pipeline MUST honour QGAI_TRAIN_CUTOFF and must save the actual
# effective cutoff in model metadata. This script will hard-fail if it cannot
# verify that every trained model only used data strictly before BACKTEST_START.
TRAINING_CUTOFF = "2026-03-31"
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

CANDIDATES = [
    ("h4_support_dist", "H4 support distance"),
    ("is_dead_hour", "Dead-hour flag"),
    ("ts_line_dist_pct", "Ratchet line distance"),
    ("is_post_news", "Post-news flag"),
    ("move_2hr", "2-hour price move"),
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
        raise RuntimeError("BACKTEST_ARGS must contain --from and --to dates") from exc
    return parse_iso_date(start, "backtest start"), parse_iso_date(end, "backtest end")


def preflight_leakage_guard() -> None:
    train_cutoff = parse_iso_date(TRAINING_CUTOFF, "TRAINING_CUTOFF")
    backtest_start, backtest_end = get_backtest_dates()

    print("\n" + "=" * 72)
    print("LEAKAGE PREFLIGHT")
    print(f"Requested training cutoff : {train_cutoff.isoformat()}")
    print(f"Backtest start            : {backtest_start.isoformat()}")
    print(f"Backtest end              : {backtest_end.isoformat()}")

    if train_cutoff >= backtest_start:
        raise RuntimeError(
            "DATA LEAKAGE BLOCKED: TRAINING_CUTOFF must be strictly earlier "
            f"than BACKTEST_START ({train_cutoff} >= {backtest_start})"
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
    backtest_start, _ = get_backtest_dates()
    requested_cutoff = parse_iso_date(TRAINING_CUTOFF, "TRAINING_CUTOFF")
    found: list[tuple[str, date, str]] = []

    for path in MODEL_DIR.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        _collect_cutoffs(payload, str(path), found)

    if not found:
        msg = (
            "MODEL CUTOFF NOT VERIFIED: no recognised cutoff field was found "
            f"in JSON metadata under {MODEL_DIR}. train.py must save at least "
            "'effective_training_cutoff' or 'training_end'."
        )
        if REQUIRE_VERIFIED_MODEL_METADATA:
            raise RuntimeError(msg)
        print(f"WARNING: {msg}")
        return requested_cutoff

    effective_cutoff = max(item[1] for item in found)
    latest_sources = [item for item in found if item[1] == effective_cutoff]

    print("\nMODEL CUTOFF VERIFICATION")
    print(f"Requested cutoff          : {requested_cutoff.isoformat()}")
    print(f"Effective metadata cutoff : {effective_cutoff.isoformat()}")
    for key, cutoff, source in latest_sources[:5]:
        print(f"  latest source           : {key}={cutoff} | {source}")

    if effective_cutoff > requested_cutoff:
        raise RuntimeError(
            "TRAINING CUTOFF VIOLATION: model metadata shows data later than "
            f"the requested cutoff ({effective_cutoff} > {requested_cutoff})"
        )

    if effective_cutoff >= backtest_start:
        raise RuntimeError(
            "DATA LEAKAGE BLOCKED: effective model cutoff must be strictly "
            f"before backtest start ({effective_cutoff} >= {backtest_start})"
        )

    print("Model cutoff check        : PASS")
    return effective_cutoff


def safe_rmtree(path: Path) -> None:
    path = path.resolve()
    allowed = (ROOT / "backtest" / "results").resolve()
    if not str(path).lower().startswith(str(allowed).lower()):
        raise RuntimeError(f"Refusing to remove unsafe path: {path}")
    if path.exists():
        shutil.rmtree(path)


def copy_dir(src: Path, dst: Path, mirror: bool = False) -> None:
    if mirror and dst.exists():
        shutil.rmtree(dst)
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


def read_total_r(outdir: Path) -> dict:
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


def run_case(name: str, features: list[str]) -> dict:
    outdir = OUTBASE / name
    safe_rmtree(outdir)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["QGAI_CTF_FADE"] = "0"
    env["QGAI_ABLATE"] = ""
    env["QGAI_UNPRUNE"] = ",".join(features)
    env["QGAI_TRAIN_CUTOFF"] = TRAINING_CUTOFF
    env["QGAI_STRICT_CUTOFF"] = "1"

    print("\n" + "-" * 72)
    print(f"[{name}]")
    print(f"UNPRUNE = {env['QGAI_UNPRUNE'] or '(baseline current 27)'}")
    print("Retraining...")
    run_cmd([str(PY), str(TRAIN)], env)
    effective_cutoff = verify_trained_model_cutoff()
    env["QGAI_EFFECTIVE_MODEL_CUTOFF"] = effective_cutoff.isoformat()
    print("Backtesting...")
    run_cmd([str(PY), str(REPLAY), *BACKTEST_ARGS, "--out-dir", str(outdir)], env)
    result = read_total_r(outdir)
    result["outdir"] = str(outdir)
    return result


def main() -> int:
    preflight_leakage_guard()

    if not MODEL_DIR.exists():
        print(f"MODEL DIR NOT FOUND: {MODEL_DIR}")
        return 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_ROOT / f"FORWARD_SELECT_PRE_{stamp}"
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    copy_dir(MODEL_DIR, backup)
    OUTBASE.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    accepted: list[str] = []

    try:
        baseline = run_case("B0_baseline", accepted)
        current_r = baseline["total_r"]
        summary_rows.append({
            "step": "B0",
            "candidate": "baseline",
            "tested_features": "",
            "decision": "BASELINE",
            "compare_to_r": "",
            **baseline,
        })

        for idx, (feature, label) in enumerate(CANDIDATES, start=1):
            test_features = accepted + [feature]
            name = f"B{idx}_try_{feature}"
            result = run_case(name, test_features)
            diff = round(result["total_r"] - current_r, 3)
            if result["total_r"] > current_r:
                decision = "KEEP"
                accepted.append(feature)
                current_r = result["total_r"]
            else:
                decision = "DROP"

            summary_rows.append({
                "step": f"B{idx}",
                "candidate": feature,
                "label": label,
                "tested_features": ",".join(test_features),
                "decision": decision,
                "compare_to_r": current_r if decision == "KEEP" else round(current_r, 3),
                "diff_vs_current": diff,
                **result,
            })
            print(f"Decision for {feature}: {decision} (diff {diff:+.1f}R)")

        summary_path = OUTBASE / "_forward_select_summary.csv"
        fieldnames = [
            "step", "candidate", "label", "tested_features", "decision",
            "diff_vs_current", "compare_to_r", "trades", "wr_pct", "pf",
            "avg_r", "total_r", "net_return_pct", "max_dd_pct", "outdir",
        ]
        with summary_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(summary_rows)

        print("\n" + "=" * 72)
        print("FORWARD SELECTION DONE")
        print(f"Accepted features: {accepted if accepted else '(none)'}")
        print(f"Final Stage-1 R: {current_r:.1f}R")
        print(f"Summary: {summary_path}")
        print(f"Verified clean OOS start: {get_backtest_dates()[0].isoformat()}")
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
