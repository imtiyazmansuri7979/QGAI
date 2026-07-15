"""
QGAI-CORE_Diag_SignalRepaint

Audits whether saved historical signals can repaint, disappear, be overwritten,
or diverge between SQLite, CSV, and dashboard history.

This is a STEP-BASED diagnostic, not a single-shot check: signal repaint is a
question about TIME (does a saved record change between now and 15 minutes
from now / 1 hour from now / after a restart / after a model reload?), so a
single run cannot answer it. Each invocation persists a ledger
(`_ledger.json` in the output folder) keyed by `signal_id`; the FIRST run
(--step baseline) captures the current value of every field that must never
change; every LATER run (--step after15m / after1h / after_restart /
after_model_reload / refresh_compare) re-reads the SAME signal_ids from
SQLite/CSV/dashboard and compares against the baseline, filling in exactly
one column-set per step. Nothing here mutates the `signals` table — every
DB access is a SELECT.

Usage (run each step at the point in time it names, per the house test
procedure — see RUN_QGAI-CORE_Diag_SignalRepaint.bat):
    python diag_signal_repaint.py --step baseline
    python diag_signal_repaint.py --step after15m
    python diag_signal_repaint.py --step after1h
    python diag_signal_repaint.py --step after_restart
    python diag_signal_repaint.py --step after_model_reload
    python diag_signal_repaint.py --step refresh_compare
"""
import argparse
import csv
import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

from bridge_constants import CFG, ensure_db


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine"
OUT = ROOT / "results" / "QGAI-CORE_Diag_SignalRepaint"
SUMMARY = OUT / "QGAI-CORE_Diag_SignalRepaint_summary.csv"
DETAILS = OUT / "QGAI-CORE_Diag_SignalRepaint_details.csv"
REPORT = OUT / "QGAI-CORE_Diag_SignalRepaint_report.txt"
RUNLOG = OUT / "QGAI-CORE_Diag_SignalRepaint_run.log"
LEDGER = OUT / "_ledger.json"

# Baseline and every later step MUST read the same number of newest DB rows,
# else the extra rows a wider step-read reaches (older than the baseline window)
# look like signals that "appeared later" when they were simply never in the
# baseline snapshot. Keep this single value for both reads.
READ_WINDOW = 400

STEPS = ["baseline", "after15m", "after1h", "after_restart", "after_model_reload", "refresh_compare"]
STEP_COLS = {
    "after15m":            ("direction_after_15m", "probability_after_15m", "state_after_15m"),
    "after1h":             ("direction_after_1h", "probability_after_1h"),
    "after_restart":       ("direction_after_restart", "probability_after_restart"),
    "after_model_reload":  ("direction_after_model_reload", "probability_after_model_reload"),
}

DETAIL_COLUMNS = [
    "signal_id", "signal_time", "symbol",
    "original_direction", "original_probability", "original_threshold",
    "original_state", "original_model_version", "original_feature_hash",
    "direction_after_15m", "probability_after_15m", "state_after_15m",
    "direction_after_1h", "probability_after_1h",
    "direction_after_restart", "probability_after_restart",
    "direction_after_model_reload", "probability_after_model_reload",
    "db_row_exists", "db_row_changed", "csv_row_changed",
    "dashboard_row_changed", "signal_disappeared",
    "historical_signal_appeared_later", "duplicate_signal_count",
    "repaint_type", "repaint_reason",
]

REPAINT_LABELS = {
    0: "No repaint", 1: "Probability or score changed", 2: "Direction changed",
    3: "Signal disappeared", 4: "Historical signal appeared later",
    5: "Database row overwritten", 6: "Dashboard-only repaint",
    7: "CSV/database mismatch", 8: "Model-version mismatch", 9: "Duplicate signal",
}


def log(msg):
    print(msg)
    with RUNLOG.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def rows_from_db(limit=200):
    ensure_db()
    con = sqlite3.connect(str(CFG.paths.db_path))
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT * FROM signals
        WHERE mode != 'BACKTEST'
        ORDER BY COALESCE(signal_created_at, bar_time) DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def row_by_signal_id(sid):
    """One exact row lookup by signal_id -- read-only, no mutation."""
    con = sqlite3.connect(str(CFG.paths.db_path))
    con.row_factory = sqlite3.Row
    r = con.execute("SELECT * FROM signals WHERE signal_id=?", (sid,)).fetchone()
    con.close()
    return dict(r) if r else None


def rows_from_csv():
    p = Path(CFG.paths.signal_log)
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def dashboard_rows():
    p = Path(CFG.paths.logs_dir) / "dashboard.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("signal_history") or []
    except Exception:
        return []


def code_pattern_audit():
    """Static audit: patterns that would let a historical signal row be
    overwritten/replaced/deleted, PLUS the dashboard bar_time-collapse
    pattern found 2026-07-14 (client-side merge keyed by bar_time instead
    of signal_id can silently show only one of two legitimately-distinct
    same-candle rows)."""
    patterns = [
        "INSERT OR REPLACE", "REPLACE INTO", "UPDATE signals",
        "ON CONFLICT", "UPSERT", "DELETE FROM signals", "INSERT OR IGNORE",
    ]
    hits = []
    for path in ENGINE.glob("*.py"):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for n, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith('"') or stripped.startswith("'"):
                continue
            if "silently ignored by INSERT OR IGNORE" in stripped:
                continue
            for pat in patterns:
                if pat in line:
                    hits.append({"file": str(path.relative_to(ROOT)), "line": n, "pattern": pat, "text": stripped})

    # Dashboard-side check: a client merge keyed by bar_time (map[r.bt]=r) instead
    # of signal_id would silently collapse two distinct immutable rows for the
    # same candle into whichever one the merge processed last.
    dash_html = ENGINE / "dashboard.html"
    if dash_html.exists():
        text = dash_html.read_text(encoding="utf-8", errors="ignore")
        for n, line in enumerate(text.splitlines(), start=1):
            if "map[r.bt]=r" in line or "map[r.bt] = r" in line:
                hits.append({"file": "engine/dashboard.html", "line": n,
                             "pattern": "DASHBOARD_BARTIME_COLLAPSE",
                             "text": line.strip()})
    return hits


def comparable(row):
    return {
        "signal": str(row.get("signal", "")),
        "win_prob": str(row.get("win_prob", "")),
        "hmm_state": str(row.get("hmm_state", "")),
        "model_version": str(row.get("model_version", "")),
        "feature_hash": str(row.get("feature_hash", "")),
        "decision_threshold": str(row.get("decision_threshold", row.get("eff_prob", ""))),
    }


def load_ledger():
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_ledger(ledger):
    LEDGER.write_text(json.dumps(ledger, indent=2, default=str), encoding="utf-8")


def run_baseline():
    """Step A: capture the current value of every immutable field for the
    most recent signal_ids -- this is the 'original_*' record everything
    else gets compared against."""
    db_rows = rows_from_db(READ_WINDOW)
    csv_rows = rows_from_csv()
    dash = dashboard_rows()
    csv_by_id = {r.get("signal_id", ""): r for r in csv_rows if r.get("signal_id")}
    dash_by_id = {r.get("signal_id", ""): r for r in dash if r.get("signal_id")}
    id_counts = Counter(r.get("signal_id", "") for r in db_rows if r.get("signal_id"))
    # Frontier = newest bar_time we can see at baseline. A signal that appears
    # LATER with a bar_time AT OR BEFORE this frontier is a genuine back-dated
    # insertion into history (repaint type 4). A signal with a bar_time AFTER
    # the frontier is just the live bridge advancing to a new candle -- normal,
    # NOT a repaint. baseline_ids lets us tell brand-new rows from ones we
    # already had.
    _bts = [str(r.get("bar_time", "")) for r in db_rows if r.get("bar_time")]
    baseline_frontier = max(_bts, default="")
    # Floor = oldest bar_time in the baseline window. Rows older than this were
    # simply outside our snapshot, not "back-dated inserts" -- only flag new
    # rows whose bar_time falls INSIDE [floor, frontier], the range we fully saw.
    baseline_floor = min(_bts, default="")
    baseline_ids = [r.get("signal_id", "") for r in db_rows if r.get("signal_id")]

    ledger = {}
    n = max(3, min(40, len(db_rows)))
    for row in db_rows[:n]:
        sid = row.get("signal_id") or ""
        if not sid:
            continue
        b = comparable(row)
        ledger[sid] = {
            "signal_time": row.get("bar_time", ""),
            "symbol": row.get("symbol", ""),
            "bar_time": row.get("bar_time", ""),
            "mode": row.get("mode", ""),
            "original_direction": b["signal"],
            "original_probability": b["win_prob"],
            "original_threshold": b["decision_threshold"],
            "original_state": b["hmm_state"],
            "original_model_version": b["model_version"],
            "original_feature_hash": b["feature_hash"],
            "duplicate_signal_count": id_counts.get(sid, 0),
            "csv_seen": bool(csv_by_id.get(sid)),
            "csv_original": comparable(csv_by_id[sid]) if csv_by_id.get(sid) else None,
            "dash_seen": bool(dash_by_id.get(sid)),
            "dash_original": {
                "signal": str(dash_by_id[sid].get("signal", "")),
                "win_prob": str(dash_by_id[sid].get("win_prob", "")),
                "hmm_state": str(dash_by_id[sid].get("hmm_state", "")),
            } if dash_by_id.get(sid) else None,
            "after15m": {}, "after1h": {}, "after_restart": {}, "after_model_reload": {},
            "steps_done": [],
        }
    ledger["_meta"] = {
        "baseline_frontier": baseline_frontier,
        "baseline_floor": baseline_floor,
        "baseline_ids": baseline_ids,
        "baseline_run_at": datetime.now().isoformat(timespec="seconds"),
    }
    ledger["_new_past_rows"] = []
    save_ledger(ledger)
    log(f"Baseline captured: {len(ledger) - 1} signal_ids")
    return ledger


def run_step(ledger, step):
    """Steps B-F: re-read the SAME baseline signal_ids now and confirm none of
    their immutable fields changed. SEPARATELY, detect genuine repaint type 4
    (a signal back-dated INTO history) by finding new signal_ids whose bar_time
    is at or before the baseline frontier -- new forward candles are expected
    and are NOT flagged."""
    meta = ledger.get("_meta", {})
    baseline_frontier = str(meta.get("baseline_frontier", ""))
    baseline_floor = str(meta.get("baseline_floor", ""))
    baseline_ids = set(meta.get("baseline_ids", []))

    db_rows_now = rows_from_db(READ_WINDOW)
    db_by_id = {r.get("signal_id", ""): r for r in db_rows_now if r.get("signal_id")}
    id_counts_now = Counter(r.get("signal_id", "") for r in db_rows_now if r.get("signal_id"))
    csv_rows = rows_from_csv()
    csv_by_id = {r.get("signal_id", ""): r for r in csv_rows if r.get("signal_id")}
    dash = dashboard_rows()
    dash_by_id = {r.get("signal_id", ""): r for r in dash if r.get("signal_id")}

    # Genuine "historical signal appeared later" (type 4): a signal_id NOT seen
    # at baseline, whose bar_time is at or before the baseline frontier -- i.e.
    # inserted into a PAST slot, not the live bridge moving to a new candle.
    new_past = []
    for r in db_rows_now:
        sid = r.get("signal_id", "")
        if not sid or sid in baseline_ids:
            continue
        bt = str(r.get("bar_time", ""))
        # Must fall INSIDE the observed baseline window [floor, frontier]:
        # newer than frontier = normal forward candle; older than floor = was
        # never in the baseline snapshot (outside the read window), not a repaint.
        if baseline_frontier and baseline_floor and baseline_floor <= bt <= baseline_frontier:
            new_past.append({
                "signal_id": sid, "bar_time": r.get("bar_time", ""),
                "mode": r.get("mode", ""), "signal": r.get("signal", ""),
                "win_prob": r.get("win_prob", ""), "detected_at_step": step,
            })
    ledger["_new_past_rows"] = (ledger.get("_new_past_rows") or []) + new_past

    for sid, entry in ledger.items():
        if sid in ("_meta", "_new_past_rows"):
            continue
        row = db_by_id.get(sid) or row_by_signal_id(sid)
        entry["duplicate_signal_count"] = max(entry.get("duplicate_signal_count", 0),
                                               id_counts_now.get(sid, 1 if row else 0))
        if not row:
            entry["signal_disappeared"] = 1
            entry.setdefault("steps_done", []).append(step)
            continue

        b_now = comparable(row)
        b_orig = {
            "signal": entry["original_direction"], "win_prob": entry["original_probability"],
            "hmm_state": entry["original_state"], "model_version": entry["original_model_version"],
            "feature_hash": entry["original_feature_hash"], "decision_threshold": entry["original_threshold"],
        }
        db_changed = any(b_now.get(k, "") != b_orig.get(k, "") for k in
                         ("signal", "win_prob", "hmm_state", "model_version", "feature_hash"))
        entry["db_row_changed"] = int(entry.get("db_row_changed", 0)) or int(db_changed)

        if step in STEP_COLS:
            dir_col, prob_col = STEP_COLS[step][0], STEP_COLS[step][1]
            entry[dir_col] = b_now["signal"]
            entry[prob_col] = b_now["win_prob"]
            if len(STEP_COLS[step]) > 2:
                entry[STEP_COLS[step][2]] = b_now["hmm_state"]

        # CSV cross-check (this step's read)
        csv_row = csv_by_id.get(sid)
        if csv_row:
            c_now = comparable(csv_row)
            csv_mismatch = any(c_now.get(k, "") and b_now.get(k, "") and c_now.get(k, "") != b_now.get(k, "")
                                for k in ("signal", "win_prob", "hmm_state", "model_version", "feature_hash"))
            entry["csv_row_changed"] = int(entry.get("csv_row_changed", 0)) or int(csv_mismatch)

        # Dashboard cross-check (this step's read)
        dash_row = dash_by_id.get(sid)
        if dash_row:
            d_now = {"signal": str(dash_row.get("signal", "")), "win_prob": str(dash_row.get("win_prob", "")),
                     "hmm_state": str(dash_row.get("hmm_state", ""))}
            dash_mismatch = any(d_now.get(k, "") and b_now.get(k, "") and d_now.get(k, "") != b_now.get(k, "")
                                 for k in ("signal", "win_prob", "hmm_state"))
            entry["dashboard_row_changed"] = int(entry.get("dashboard_row_changed", 0)) or int(dash_mismatch)

        entry.setdefault("steps_done", []).append(step)

    # Baseline frontier/ids are the fixed reference for EVERY later step --
    # never overwritten, so after_restart / after_model_reload still compare
    # against the original baseline, not the prior step.
    meta[f"{step}_run_at"] = datetime.now().isoformat(timespec="seconds")
    ledger["_meta"] = meta
    save_ledger(ledger)
    return ledger


def classify(entry):
    if entry.get("signal_disappeared"):
        return 3, "Signal disappeared from database"
    if entry.get("duplicate_signal_count", 0) > 1:
        return 9, "Duplicate signal_id exists"
    if entry.get("db_row_changed"):
        # distinguish direction vs probability-only drift for a clearer reason
        return 2, "Historical DB row's direction/model/feature identity changed since baseline"
    if entry.get("csv_row_changed"):
        return 7, "CSV/database mismatch"
    if entry.get("dashboard_row_changed"):
        return 6, "Dashboard-only mismatch (DB row intact, dashboard view diverged)"
    if entry.get("historical_signal_appeared_later"):
        return 4, "A new signal appeared for a bar_time/mode window already observed at baseline"
    return 0, "No repaint detected across all steps run so far"


def write_outputs(ledger, code_hits):
    detail_rows = []
    for sid, entry in ledger.items():
        if sid in ("_meta", "_new_past_rows"):
            continue
        repaint_type, reason = classify(entry)
        detail_rows.append({
            "signal_id": sid,
            "signal_time": entry.get("signal_time", ""),
            "symbol": entry.get("symbol", ""),
            "original_direction": entry.get("original_direction", ""),
            "original_probability": entry.get("original_probability", ""),
            "original_threshold": entry.get("original_threshold", ""),
            "original_state": entry.get("original_state", ""),
            "original_model_version": entry.get("original_model_version", ""),
            "original_feature_hash": entry.get("original_feature_hash", ""),
            "direction_after_15m": entry.get("direction_after_15m", ""),
            "probability_after_15m": entry.get("probability_after_15m", ""),
            "state_after_15m": entry.get("state_after_15m", ""),
            "direction_after_1h": entry.get("direction_after_1h", ""),
            "probability_after_1h": entry.get("probability_after_1h", ""),
            "direction_after_restart": entry.get("direction_after_restart", ""),
            "probability_after_restart": entry.get("probability_after_restart", ""),
            "direction_after_model_reload": entry.get("direction_after_model_reload", ""),
            "probability_after_model_reload": entry.get("probability_after_model_reload", ""),
            "db_row_exists": 0 if entry.get("signal_disappeared") else 1,
            "db_row_changed": int(entry.get("db_row_changed", 0)),
            "csv_row_changed": int(entry.get("csv_row_changed", 0)),
            "dashboard_row_changed": int(entry.get("dashboard_row_changed", 0)),
            "signal_disappeared": int(entry.get("signal_disappeared", 0)),
            "historical_signal_appeared_later": int(entry.get("historical_signal_appeared_later", 0)),
            "duplicate_signal_count": entry.get("duplicate_signal_count", 1),
            "repaint_type": repaint_type,
            "repaint_reason": reason,
        })

    # Genuine type-4 rows: signals inserted into the PAST (bar_time <= baseline
    # frontier) after baseline. Forward-progress candles are NOT here by design.
    for npr in (ledger.get("_new_past_rows") or []):
        detail_rows.append({
            "signal_id": npr.get("signal_id", ""),
            "signal_time": npr.get("bar_time", ""),
            "symbol": "",
            "original_direction": "", "original_probability": "", "original_threshold": "",
            "original_state": "", "original_model_version": "", "original_feature_hash": "",
            "direction_after_15m": "", "probability_after_15m": "", "state_after_15m": "",
            "direction_after_1h": "", "probability_after_1h": "",
            "direction_after_restart": "", "probability_after_restart": "",
            "direction_after_model_reload": "", "probability_after_model_reload": "",
            "db_row_exists": 1, "db_row_changed": 0, "csv_row_changed": 0,
            "dashboard_row_changed": 0, "signal_disappeared": 0,
            "historical_signal_appeared_later": 1, "duplicate_signal_count": 1,
            "repaint_type": 4,
            "repaint_reason": f"Signal back-dated into history (bar_time {npr.get('bar_time','')} "
                              f"<= baseline frontier), detected at step {npr.get('detected_at_step','')}",
        })

    with DETAILS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DETAIL_COLUMNS)
        w.writeheader()
        w.writerows(detail_rows)

    repaint_rows = [r for r in detail_rows if int(r["repaint_type"]) != 0]
    risky_patterns = []
    for h in code_hits:
        if h["pattern"] == "DASHBOARD_BARTIME_COLLAPSE":
            risky_patterns.append(h)
        elif h["pattern"] == "INSERT OR IGNORE":
            risky_patterns.append(h)
        elif h["pattern"] == "UPDATE signals" and h["file"].endswith("bridge_constants.py"):
            continue
        elif h["pattern"] == "UPDATE signals" and "outcome" not in h["text"] and "pnl_net" not in h["text"]:
            risky_patterns.append(h)

    steps_done = sorted({s for e in ledger.values() if isinstance(e, dict) for s in e.get("steps_done", [])})
    summary = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "steps_completed": ",".join(steps_done) if steps_done else "baseline",
        "signal_ids_tracked": len(detail_rows),
        "repaint_rows": len(repaint_rows),
        "code_pattern_hits": len(code_hits),
        "risky_pattern_hits": len(risky_patterns),
        "pass": int(not repaint_rows and not risky_patterns),
    }
    with SUMMARY.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary.keys()))
        w.writeheader()
        w.writerow(summary)

    report = []
    report.append("QGAI-CORE_Diag_SignalRepaint Report")
    report.append("=" * 44)
    report.append(f"Run at: {summary['run_at']}")
    report.append(f"Steps completed so far: {summary['steps_completed']}")
    report.append("")
    report.append("Flow audited:")
    report.append("Market data -> Feature calculation -> Model inference -> Signal decision -> "
                   "SQLite logging -> CSV logging -> Dashboard display -> Signal history display")
    report.append("")
    report.append(f"Signal_ids tracked: {len(detail_rows)}")
    report.append(f"Repaint rows: {len(repaint_rows)}")
    for r in repaint_rows:
        report.append(f"  [{r['repaint_type']}={REPAINT_LABELS.get(int(r['repaint_type']), '?')}] "
                       f"{r['signal_id']}: {r['repaint_reason']}")
    report.append("")
    report.append("Static overwrite-pattern audit:")
    for h in code_hits:
        report.append(f"- {h['pattern']}: {h['file']}:{h['line']} | {h['text']}")
    if not code_hits:
        report.append("- No overwrite patterns found.")
    report.append("")
    report.append("Verdict:")
    report.append("PASS" if summary["pass"] else "CHECK_DETAILS")
    report.append("")
    report.append("Notes:")
    report.append("- Current Signal panel may change because it is live inference.")
    report.append("- Signal History must come from saved DB rows only.")
    report.append("- Outcome/pnl updates are allowed; direction/probability/model/feature snapshot must not change.")
    report.append("- Run --step baseline first, then the remaining steps at their real time offsets")
    report.append("  (15 min, 1 hour, after an actual restart, after an actual model reload, after a")
    report.append("  dashboard refresh) -- this tool cannot fast-forward real time or fake a restart.")
    REPORT.write_text("\n".join(report), encoding="utf-8")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", choices=STEPS, default=None,
                    help="Which point-in-time check to run. Omit to auto-pick: "
                         "'baseline' if no ledger exists yet, else the next unrun step.")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    RUNLOG.write_text("", encoding="utf-8")
    log("QGAI-CORE_Diag_SignalRepaint started")

    ledger = load_ledger()
    step = args.step
    if step is None:
        if not ledger:
            step = "baseline"
        else:
            done = set()
            for e in ledger.values():
                if isinstance(e, dict):
                    done |= set(e.get("steps_done", []))
            remaining = [s for s in STEPS[1:] if s not in done]
            step = remaining[0] if remaining else "refresh_compare"
    log(f"Step: {step}")

    if step == "baseline" or not ledger:
        ledger = run_baseline()
    else:
        ledger = run_step(ledger, step)

    code_hits = code_pattern_audit()
    summary = write_outputs(ledger, code_hits)

    log(f"summary: {SUMMARY}")
    log(f"details: {DETAILS}")
    log(f"report: {REPORT}")
    return 0 if summary["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
