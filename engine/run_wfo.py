#!/usr/bin/env python3
"""
Walk-Forward Backtest Orchestrator (QGAI v2)
─────────────────────────────────────────────
Simulates EXACTLY how the live system behaves: every week, retrain the
model on all past data (expanding window), then trade the next week
out-of-sample. Slides forward week by week.

This is TRUE out-of-sample validation — the model never sees future data.

Usage:
  python run_wfo.py --start 2025-06-01 --end 2026-06-12 \
      --buf 0.06 --tp-equity 3 --weeks 4   (test: first 4 weeks only)
  python run_wfo.py --start 2025-06-01 --end 2026-06-12 \
      --buf 0.06 --tp-equity 3              (full run)

Each week:
  1. set QGAI_TRAIN_CUTOFF = week_start, QGAI_CORE_ONLY=1
  2. python train.py            (model on data < week_start)
  3. python backtest_replay.py --from week_start --to week_end ...
  4. collect the week's trades / R

Resume-safe: completed weeks are cached in wfo_results/week_*.txt and skipped.
"""
import argparse, os, subprocess, sys, re, json
from datetime import datetime, timedelta
from pathlib import Path

ENGINE = Path(__file__).parent
BT_RESULTS = ENGINE.parent / "backtest" / "results"   # all backtest output lives here, NOT in engine/
RESULTS = BT_RESULTS / "wfo_results"
RESULTS.mkdir(parents=True, exist_ok=True)


def _train_cutoff_before(week_start: str) -> str:
    """Fix 2026-07-13 (leakage guard): QGAI_TRAIN_CUTOFF is INCLUSIVE through
    the end of its calendar day (train.py:_get_training_cutoff). Passing
    week_start itself made the cutoff equal week_start 23:59:59 while the
    backtest for that same week ALSO starts at week_start 00:00 — a 1-day
    train/test overlap on every fold. This docstring always said 'model on
    data < week_start'; the code just didn't do it. Train cutoff = the day
    BEFORE week_start closes the gap to zero, matching leakage_guard.py's
    strict 'cutoff must predate backtest_start' check."""
    d = datetime.strptime(week_start, "%Y-%m-%d") - timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def week_ranges(start: str, end: str):
    """Yield (week_start, week_end) Mondays from start to end."""
    d0 = datetime.strptime(start, "%Y-%m-%d")
    d1 = datetime.strptime(end, "%Y-%m-%d")
    # align to Monday
    d0 -= timedelta(days=d0.weekday())
    cur = d0
    while cur < d1:
        wk_end = cur + timedelta(days=7)
        yield cur.strftime("%Y-%m-%d"), min(wk_end, d1).strftime("%Y-%m-%d")
        cur = wk_end


def month_ranges(start: str, end: str):
    """Yield (month_start, month_end) calendar months from start to end.
    Each period = retrain on data before month_start, test the month."""
    d0 = datetime.strptime(start, "%Y-%m-%d")
    d1 = datetime.strptime(end, "%Y-%m-%d")
    # align to 1st of the month
    cur = d0.replace(day=1)
    while cur < d1:
        # first day of next month
        if cur.month == 12:
            nxt = cur.replace(year=cur.year + 1, month=1)
        else:
            nxt = cur.replace(month=cur.month + 1)
        yield cur.strftime("%Y-%m-%d"), min(nxt, d1).strftime("%Y-%m-%d")
        cur = nxt


def period_ranges(start: str, end: str, mode: str):
    """Dispatch to week or month ranges."""
    return month_ranges(start, end) if mode == "month" else week_ranges(start, end)


def parse_report(txt: str) -> dict:
    """Extract key metrics from a backtest report text."""
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


def do_trail_sweep(args):
    """One retrain per week, then backtest ALL 6 stop-trail modes on that SAME model.
    5x faster than running 6 separate WFOs. Per-mode folders: backtest/results/sweep_<mode>/."""
    import shutil as _sh
    modes = ["line", "off", "after1r", "be", "htf", "regime"]
    # 2026-07-03 (Divyesh FIX-2): honor --results-dir as the folder PREFIX so a
    # new sweep (e.g. on as-of data) never reuses stale cached weeks from an old
    # sweep. Default prefix stays "sweep" (backward compatible).
    _prefix = args.results_dir if args.results_dir != "wfo_results" else "sweep"
    mode_dir = {m: BT_RESULTS / f"{_prefix}_{m}" for m in modes}
    for d in mode_dir.values():
        d.mkdir(parents=True, exist_ok=True)

    weeks = list(period_ranges(args.start, args.end, args.period))
    if args.weeks > 0:
        weeks = weeks[:args.weeks]

    # ⏱ ETA countdown (house rule 2026-07-02)
    import time as _time
    _durs = []
    def _eta_print(i_done, t_start):
        _durs.append(_time.time() - t_start)
        _avg = sum(_durs[-10:]) / len(_durs[-10:])
        _left_s = (len(weeks) - i_done) * _avg
        _eta = datetime.now() + timedelta(seconds=_left_s)
        print(f"    ⏱ week {_durs[-1]/60:.1f} min | avg {_avg/60:.1f} min | "
              f"~{_left_s/60:.0f} min remaining | ETA {_eta.strftime('%H:%M')} "
              f"({len(weeks)-i_done} weeks left)")

    print("=" * 64)
    print("  WALK-FORWARD TRAIL SWEEP (all 6 modes, shared weekly retrain)")
    print(f"  {args.start} -> {args.end}  ({len(weeks)} {args.period}s) x {len(modes)} modes")
    print(f"  buffer {args.buf}% | equity-TP {args.tp_equity}% | risk {args.risk}%")
    print("=" * 64)

    for i, (w_start, w_end) in enumerate(weeks, 1):
        tag = f"week_{w_start}"
        todo = [m for m in modes if not (mode_dir[m] / f"{tag}.json").exists()]
        if not todo:
            print(f"[{i}/{len(weeks)}] {w_start}  CACHED (all modes)")
            continue

        print(f"\n[{i}/{len(weeks)}] {w_start} -> {w_end}  (modes: {','.join(todo)})")
        _wk_t0 = _time.time()
        env = os.environ.copy()
        env["QGAI_TRAIN_CUTOFF"] = _train_cutoff_before(w_start)
        if args.core_only:
            env["QGAI_CORE_ONLY"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        # retrain ONCE for this week (shared by all modes)
        print(f"    retraining (cutoff {env['QGAI_TRAIN_CUTOFF']}, strictly before {w_start})...")
        r = subprocess.run([sys.executable, "train.py"], cwd=ENGINE, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(f"    train failed — see sweep_train_{w_start}.log")
            (BT_RESULTS / f"sweep_train_{w_start}.log").write_text(
                (r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
            continue

        # backtest each pending mode on the SAME freshly-trained model
        for m in todo:
            out = mode_dir[m]
            bt_cmd = [sys.executable, "backtest_replay.py",
                      "--from", w_start, "--to", w_end,
                      "--equity", str(args.equity), "--risk", str(args.risk),
                      "--spread", str(args.spread), "--ratchet", "on",
                      "--ratchet-buf-pct", str(args.buf),
                      "--tp-equity-pct", str(args.tp_equity),
                      "--skip-counter-trend", "--out-dir", str(out)]
            if getattr(args, "max_open", 1) != 1:
                bt_cmd += ["--max-open", str(args.max_open)]
            if m != "line":
                bt_cmd += ["--stop-trail", m]
            if args.tp_regime:
                bt_cmd += ["--tp-regime"]   # regime-adaptive TP cap (Task 5)
            if args.fixed_lot > 0:
                bt_cmd += ["--fixed-lot", str(args.fixed_lot)]
            bt = subprocess.run(bt_cmd, cwd=ENGINE, env=env,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
            report = (bt.stdout or "") + "\n" + (bt.stderr or "")
            (out / f"{tag}.txt").write_text(report, encoding="utf-8")
            metrics = parse_report(report)
            if metrics.get("total_r") is None:
                print(f"      {m:8} FAILED (see {tag}.txt) — will retry next run")
                continue
            # preserve this week's trades (unique suffix per mode → one file)
            for _f in out.glob("backtest_trades*.csv"):
                _sh.copy(_f, out / f"trades_{w_start}.csv")
                break
            (out / f"{tag}.json").write_text(json.dumps(
                {"week_start": w_start, "week_end": w_end, **metrics}), encoding="utf-8")
            print(f"      {m:8} R={metrics.get('total_r')} PF={metrics.get('pf')}")
        _eta_print(i, _wk_t0)

    # ── aggregate + comparison ──
    print("\n" + "=" * 64)
    print("  TRAIL SWEEP SUMMARY")
    print("=" * 64)
    print(f"  {'mode':10}{'totalR':>10}{'weeks+':>9}{'trades':>9}")
    out_lines = [f"{'mode':10}{'totalR':>10}{'weeks+':>9}{'trades':>9}"]
    import glob as _g
    try:
        import pandas as _pd
    except Exception:
        _pd = None
    for m in modes:
        rows = []
        for f in sorted(mode_dir[m].glob("week_*.json")):
            try: rows.append(json.loads(f.read_text()))
            except Exception: pass
        tot = sum((x.get("total_r") or 0) for x in rows)
        tr  = sum((x.get("trades") or 0) for x in rows)
        pos = sum(1 for x in rows if (x.get("total_r") or 0) > 0)
        line = f"  {m:10}{tot:>+10.1f}{str(pos)+'/'+str(len(rows)):>9}{tr:>9.0f}"
        print(line); out_lines.append(line.strip())
        tfiles = sorted(_g.glob(str(mode_dir[m] / "trades_*.csv")))
        if tfiles and _pd is not None:
            try:
                _df = _pd.concat([_pd.read_csv(x) for x in tfiles], ignore_index=True)
                _df.to_csv(mode_dir[m] / "ALL_OOS_trades.csv", index=False)
            except Exception as _e:
                print(f"    (combine {m}: {_e})")
    (BT_RESULTS / f"{_prefix.upper()}_SUMMARY.txt").write_text(
        "TRAIL SWEEP\n" + "\n".join(out_lines), encoding="utf-8")
    # House rule 2026-07-02: every backtest/WFO also saves its result as CSV.
    try:
        import csv as _csv
        with open(BT_RESULTS / f"{_prefix.upper()}_SUMMARY.csv", "w", newline="",
                  encoding="utf-8-sig") as _fc:
            _w = _csv.writer(_fc)
            _w.writerow(["mode", "total_r", "pos_weeks", "weeks", "trades"])
            for m in modes:
                rows = []
                for f in sorted(mode_dir[m].glob("week_*.json")):
                    try: rows.append(json.loads(f.read_text()))
                    except Exception: pass
                _w.writerow([m, round(sum((x.get("total_r") or 0) for x in rows), 1),
                             sum(1 for x in rows if (x.get("total_r") or 0) > 0),
                             len(rows),
                             int(sum((x.get("trades") or 0) for x in rows))])
    except Exception as _e:
        print(f"  (could not write sweep CSV: {_e})")
    print(f"\n  Per-mode folders: backtest/results/{_prefix}_<mode>/")
    print(f"  Summary: backtest/results/{_prefix.upper()}_SUMMARY.txt (+ .csv)")


def _pb_combos(on_key="QGAI_PB_ENTRY"):
    """Sweep grid (ET1): baseline (both modes OFF) + 6 param combos.
    on_key = "QGAI_PB_ENTRY" (v1 BLOCK sweep) or "QGAI_PB_GEN" (v2 GENERATE sweep).
    label is folder-safe; env carries per-combo params to backtest_replay via the
    shared _pullback_ok() conditions (QGAI_PB_* → parity with live).

    Trimmed 2026-07-03 (19→7): the meaningful axes are htf_agreement_min ∈ {1,3}
    (1=dominant/net trend only → trades even when TFs disagree; 3=all-3 aligned; 2 is
    degenerate) and pb_near_pct (how close to the line). chase_max barely bites — in
    GEN, established-trend entries already need sdist≤pb_near<chase, so chase only
    affects fresh-flip bars — so it's FIXED at 0.30 (loosest, doesn't cut fresh trends).
    Fewer combos also = less multiple-comparison luck risk in picking a winner."""
    CHASE = 0.30
    combos = [("baseline", {"QGAI_PB_ENTRY": "0", "QGAI_PB_GEN": "0"})]
    for a in (1, 3):                        # htf_agreement_min
        for n in (0.05, 0.075, 0.10):       # pb_near_pct
            label = f"a{a}_n{int(round(n*1000)):03d}_c{int(round(CHASE*100)):03d}"
            combos.append((label, {
                on_key: "1", "QGAI_PB_AGREE": str(a),
                "QGAI_PB_NEAR": str(n), "QGAI_PB_CHASE": str(CHASE)}))
    return combos


def do_pb_entry_sweep(args, mode="block"):
    """ET1 sweep: one retrain per week, then backtest EVERY param combo (baseline + 18)
    on that SAME model. mode="block" (v1: filter ML entries) or "gen" (v2: GENERATE early
    pullback entries). Exit held FIXED at the live-faithful config. Judged on total R.
    Per-combo folders: backtest/results/<prefix>_<label>/. Mirrors do_trail_sweep."""
    import shutil as _sh
    on_key = "QGAI_PB_GEN" if mode == "gen" else "QGAI_PB_ENTRY"
    combos = _pb_combos(on_key)
    labels = [c[0] for c in combos]
    _default_prefix = "pbgensweep" if mode == "gen" else "pbsweep"
    _prefix = args.results_dir if args.results_dir != "wfo_results" else _default_prefix
    combo_dir = {lab: BT_RESULTS / f"{_prefix}_{lab}" for lab in labels}
    for d in combo_dir.values():
        d.mkdir(parents=True, exist_ok=True)

    weeks = list(period_ranges(args.start, args.end, args.period))
    if args.weeks > 0:
        weeks = weeks[:args.weeks]

    import time as _time
    _durs = []
    def _eta_print(i_done, t_start):
        _durs.append(_time.time() - t_start)
        _avg = sum(_durs[-10:]) / len(_durs[-10:])
        _left_s = (len(weeks) - i_done) * _avg
        _eta = datetime.now() + timedelta(seconds=_left_s)
        print(f"    ⏱ week {_durs[-1]/60:.1f} min | avg {_avg/60:.1f} min | "
              f"~{_left_s/60:.0f} min remaining | ETA {_eta.strftime('%H:%M')} "
              f"({len(weeks)-i_done} weeks left)")

    _mname = "GENERATE (v2, create early entries)" if mode == "gen" else "BLOCK (v1, filter ML entries)"
    print("=" * 64)
    print(f"  WALK-FORWARD PULLBACK SWEEP — mode={_mname} (shared weekly retrain)")
    print(f"  {args.start} -> {args.end}  ({len(weeks)} {args.period}s) x {len(combos)} combos")
    print(f"  buffer {args.buf}% | equity-TP {args.tp_equity}% | risk {args.risk}% | exit=live-faithful (htf+regime)")
    print("=" * 64)

    for i, (w_start, w_end) in enumerate(weeks, 1):
        tag = f"week_{w_start}"
        todo = [lab for lab in labels if not (combo_dir[lab] / f"{tag}.json").exists()]
        if not todo:
            print(f"[{i}/{len(weeks)}] {w_start}  CACHED (all combos)")
            continue

        print(f"\n[{i}/{len(weeks)}] {w_start} -> {w_end}  ({len(todo)} combos)")
        _wk_t0 = _time.time()
        base_env = os.environ.copy()
        base_env["QGAI_TRAIN_CUTOFF"] = _train_cutoff_before(w_start)
        if args.core_only:
            base_env["QGAI_CORE_ONLY"] = "1"
        base_env["PYTHONIOENCODING"] = "utf-8"

        # retrain ONCE for this week (shared by all combos — entry params don't affect training)
        print(f"    retraining (cutoff {w_start})...")
        r = subprocess.run([sys.executable, "train.py"], cwd=ENGINE, env=base_env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(f"    train failed — see {_prefix}_train_{w_start}.log")
            (BT_RESULTS / f"{_prefix}_train_{w_start}.log").write_text(
                (r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
            continue

        for lab in todo:
            _, cenv = next(c for c in combos if c[0] == lab)
            env = dict(base_env); env.update(cenv)
            out = combo_dir[lab]
            # exit held FIXED at live-faithful config (isolate ENTRY): htf trail + regime TP
            bt_cmd = [sys.executable, "backtest_replay.py",
                      "--from", w_start, "--to", w_end,
                      "--equity", str(args.equity), "--risk", str(args.risk),
                      "--spread", str(args.spread), "--ratchet", "on",
                      "--ratchet-buf-pct", str(args.buf),
                      "--tp-equity-pct", str(args.tp_equity),
                      "--skip-counter-trend", "--stop-trail", "htf",
                      "--out-dir", str(out)]
            if args.tp_regime:
                bt_cmd += ["--tp-regime"]
            if args.fixed_lot > 0:
                bt_cmd += ["--fixed-lot", str(args.fixed_lot)]
            bt = subprocess.run(bt_cmd, cwd=ENGINE, env=env,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
            report = (bt.stdout or "") + "\n" + (bt.stderr or "")
            (out / f"{tag}.txt").write_text(report, encoding="utf-8")
            metrics = parse_report(report)
            if metrics.get("total_r") is None:
                print(f"      {lab:16} FAILED (see {tag}.txt) — will retry next run")
                continue
            for _f in out.glob("backtest_trades*.csv"):
                _sh.copy(_f, out / f"trades_{w_start}.csv")
                break
            (out / f"{tag}.json").write_text(json.dumps(
                {"week_start": w_start, "week_end": w_end, "combo": lab, **metrics}),
                encoding="utf-8")
            print(f"      {lab:16} R={metrics.get('total_r')} PF={metrics.get('pf')} trades={metrics.get('trades')}")
        _eta_print(i, _wk_t0)

    # ── aggregate + comparison (ranked by total R; baseline first) ──
    print("\n" + "=" * 64)
    print("  PULLBACK-ENTRY SWEEP SUMMARY  (accept: highest totalR that BEATS baseline)")
    print("=" * 64)
    rows_all = []
    for lab in labels:
        rows = []
        for f in sorted(combo_dir[lab].glob("week_*.json")):
            try: rows.append(json.loads(f.read_text()))
            except Exception: pass
        wk_rs = [(x.get("total_r") or 0) for x in rows]
        tot = round(sum(wk_rs), 1)
        tr  = int(sum((x.get("trades") or 0) for x in rows))
        pos = sum(1 for x in rows if (x.get("total_r") or 0) > 0)
        # Fable-5 luck-vs-edge metrics: worst weekly fold (a combo carried by a few bull
        # weeks looks great on total R but fails here) + avg R/trade (edge per trade, not
        # just more exposure). Prefer high worst_wk_r & avg_r_trade, not just total_r.
        worst = round(min(wk_rs), 1) if wk_rs else 0.0
        avgR  = round(tot / tr, 3) if tr else 0.0
        rows_all.append({"combo": lab, "total_r": tot, "pos_weeks": pos,
                         "weeks": len(rows), "trades": tr, "worst_wk_r": worst, "avg_r_trade": avgR})
    base_r = next((r["total_r"] for r in rows_all if r["combo"] == "baseline"), 0.0)
    base_w = next((r["worst_wk_r"] for r in rows_all if r["combo"] == "baseline"), 0.0)
    ranked = sorted(rows_all, key=lambda r: (r["combo"] != "baseline", -r["total_r"]))
    hdr = f"  {'combo':16}{'totalR':>9}{'vsBase':>8}{'wk+':>7}{'worstWk':>9}{'R/trade':>8}{'trades':>8}"
    print(hdr); out_lines = [hdr.strip()]
    for r in ranked:
        vb = "" if r["combo"] == "baseline" else f"{r['total_r']-base_r:+.1f}"
        line = (f"  {r['combo']:16}{r['total_r']:>+9.1f}{vb:>8}"
                f"{str(r['pos_weeks'])+'/'+str(r['weeks']):>7}{r['worst_wk_r']:>+9.1f}"
                f"{r['avg_r_trade']:>+8.2f}{r['trades']:>8}")
        print(line); out_lines.append(line.strip())
    winners = [r for r in ranked if r["combo"] != "baseline" and r["total_r"] > base_r]
    verdict = (f"WINNER (total R): {winners[0]['combo']} (+{winners[0]['total_r']-base_r:.1f}R vs baseline)"
               if winners else "NO combo beats baseline → REJECT (per house acceptance rule)")
    print(f"\n  {verdict}")
    out_lines.append(verdict)
    # robustness cross-check (Fable-5): best combo by WORST weekly fold — luck filter
    robust = max((r for r in rows_all if r["combo"] != "baseline"),
                 key=lambda r: r["worst_wk_r"], default=None)
    if robust:
        rob = (f"MOST ROBUST (best worst-week): {robust['combo']} worstWk {robust['worst_wk_r']:+.1f}R "
               f"(baseline {base_w:+.1f}R) | R/trade {robust['avg_r_trade']:+.2f}")
        print(f"  {rob}"); out_lines.append(rob)
        print("  ⚠️ Prefer a combo that beats baseline on total R AND holds up on worst-week + R/trade "
              "(not one carried by a few bull weeks).")
    (BT_RESULTS / f"{_prefix.upper()}_SUMMARY.txt").write_text(
        "PULLBACK SWEEP (ET1)\n" + "\n".join(out_lines), encoding="utf-8")
    try:
        import csv as _csv
        with open(BT_RESULTS / f"{_prefix.upper()}_SUMMARY.csv", "w", newline="",
                  encoding="utf-8-sig") as _fc:
            _w = _csv.writer(_fc)
            _w.writerow(["combo", "total_r", "vs_baseline", "pos_weeks", "weeks",
                         "worst_wk_r", "avg_r_trade", "trades"])
            for r in ranked:
                vb = 0.0 if r["combo"] == "baseline" else round(r["total_r"] - base_r, 1)
                _w.writerow([r["combo"], r["total_r"], vb, r["pos_weeks"], r["weeks"],
                             r["worst_wk_r"], r["avg_r_trade"], r["trades"]])
    except Exception as _e:
        print(f"  (could not write pbsweep CSV: {_e})")
    print(f"\n  Per-combo folders: backtest/results/{_prefix}_<label>/")
    print(f"  Summary: backtest/results/{_prefix.upper()}_SUMMARY.txt (+ .csv)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (e.g. 2025-06-01)")
    ap.add_argument("--end",   required=True, help="YYYY-MM-DD")
    ap.add_argument("--buf",       type=float, default=0.06)
    ap.add_argument("--tp-equity", type=float, default=3.0)
    ap.add_argument("--equity",    type=float, default=10000)
    ap.add_argument("--risk",      type=float, default=3.0)
    ap.add_argument("--max-open",  type=int,   default=1,
                    help="max concurrent positions (2026-07-08: test max_open=2 @ half-risk)")
    ap.add_argument("--spread",    type=float, default=0.20)
    ap.add_argument("--fixed-lot", type=float, default=0.01,
                    help="fixed lot for clean R (no compounding). 0 = compounding.")
    ap.add_argument("--weeks",     type=int,   default=0,
                    help="limit to first N periods (0 = all). Use for a quick test.")
    ap.add_argument("--period",    choices=["week", "month"], default="week",
                    help="retrain cadence: week (52x, ~13h) or month (12x, ~3-4h)")
    ap.add_argument("--core-only", action="store_true", default=True,
                    help="skip BigWin/Duration retrain for speed (default on)")
    ap.add_argument("--results-dir", default="wfo_results",
                    help="output folder under engine/ — use a NEW name to keep old runs "
                         "(e.g. wfo_results_ratchet). Each folder resumes independently.")
    ap.add_argument("--no-trail", action="store_true",
                    help="flip-only: disable the stop-trail in the backtest (removes TRAIL exits)")
    ap.add_argument("--tp-regime", action="store_true",
                    help="regime-adaptive TP cap (Rng 2.0 / Trn 1.0 / Vol 0.8 by HMM state at entry); "
                         "passed through to backtest_replay each week for OOS validation (Task 5)")
    ap.add_argument("--trail-mode", choices=["line", "off", "after1r", "be", "htf", "regime"],
                    default=None, help="stop-trail behaviour passed to backtest_replay. "
                    "Default = None -> follows live config (htf if ratchet_htf_sl else line), "
                    "same resolution backtest_replay.py itself uses. Pass explicitly (e.g. 'line') "
                    "to FORCE that mode instead. (BUG_LOG #M fix, 2026-07-01: the old default='line' "
                    "was silently NOT forwarded, so 'line' actually ran whatever backtest_replay's "
                    "config-aware default was — currently htf. Now default=None makes that explicit "
                    "instead of accidental, and an explicit --trail-mode line genuinely forces line.)")
    ap.add_argument("--sweep-trails", action="store_true",
                    help="compare ALL 6 stop-trail modes in ONE pass: retrain each week ONCE, "
                         "then backtest every mode on that same model (5x faster than 6 separate runs).")
    ap.add_argument("--sweep-pb-entry", action="store_true",
                    help="ET1 v1 BLOCK sweep: baseline + 18 pullback param combos that FILTER ML entries. "
                         "One weekly retrain, exit fixed live-faithful (htf+regime). Judged on total R vs baseline.")
    ap.add_argument("--sweep-pb-gen", action="store_true",
                    help="ET1 v2 GENERATE sweep: baseline + 18 combos that CREATE early pullback entries "
                         "(enter when ML SKIPs but ADX-aligned trend pulls back to the line). Same harness.")
    args = ap.parse_args()

    if args.sweep_trails:
        do_trail_sweep(args)
        return
    if args.sweep_pb_entry:
        do_pb_entry_sweep(args, mode="block")
        return
    if args.sweep_pb_gen:
        do_pb_entry_sweep(args, mode="gen")
        return

    global RESULTS
    RESULTS = BT_RESULTS / args.results_dir
    RESULTS.mkdir(parents=True, exist_ok=True)
    print(f"  results dir: {RESULTS.name}")

    weeks = list(period_ranges(args.start, args.end, args.period))
    if args.weeks > 0:
        weeks = weeks[:args.weeks]

    print("=" * 64)
    print("  QGAI WALK-FORWARD BACKTEST")
    print(f"  {args.start} → {args.end}  ({len(weeks)} {args.period}s)")
    print(f"  buffer {args.buf}% | equity-TP {args.tp_equity}% | risk {args.risk}%")
    print(f"  expanding window, {args.period}ly retrain, core-only={args.core_only}")
    print("=" * 64)

    all_rows = []

    # ⏱ ETA countdown (Divyesh, 2026-07-02): after each computed week, print how
    # long it took, the rolling average, minutes remaining and expected finish
    # time — based on the time the first (recent) weeks actually took.
    import time as _time
    _durs = []
    def _eta_print(i_done, t_start):
        _durs.append(_time.time() - t_start)
        _avg = sum(_durs[-10:]) / len(_durs[-10:])
        _left_s = (len(weeks) - i_done) * _avg
        _eta = datetime.now() + timedelta(seconds=_left_s)
        print(f"    ⏱ week {_durs[-1]/60:.1f} min | avg {_avg/60:.1f} min | "
              f"~{_left_s/60:.0f} min remaining | ETA {_eta.strftime('%H:%M')} "
              f"({len(weeks)-i_done} weeks left)")

    for i, (w_start, w_end) in enumerate(weeks, 1):
        tag = f"week_{w_start}"
        cache = RESULTS / f"{tag}.json"

        # resume: skip completed weeks
        if cache.exists():
            row = json.loads(cache.read_text())
            print(f"[{i}/{len(weeks)}] {w_start} → {w_end}  CACHED  "
                  f"R={row.get('total_r')}")
            all_rows.append(row)
            continue

        print(f"\n[{i}/{len(weeks)}] {w_start} → {w_end}")
        _wk_t0 = _time.time()
        env = os.environ.copy()
        env["QGAI_TRAIN_CUTOFF"] = _train_cutoff_before(w_start)
        if args.core_only:
            env["QGAI_CORE_ONLY"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        # 1. retrain on data < week_start
        print(f"    retraining (cutoff {w_start})...")
        r = subprocess.run([sys.executable, "train.py"],
                           cwd=ENGINE, env=env,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(f"    ⚠️ train failed — see {tag}_train.log")
            (RESULTS / f"{tag}_train.log").write_text(
                (r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
            _eta_print(i, _wk_t0)
            continue

        # 2. backtest the week (out-of-sample)
        print(f"    backtesting {w_start} → {w_end}...")
        bt_cmd = [
            sys.executable, "backtest_replay.py",
            "--from", w_start, "--to", w_end,
            "--equity", str(args.equity), "--risk", str(args.risk),
            "--spread", str(args.spread), "--ratchet", "on",
            "--ratchet-buf-pct", str(args.buf),
            "--tp-equity-pct", str(args.tp_equity),
            "--skip-counter-trend",
            "--out-dir", str(RESULTS),
        ]
        if args.no_trail:
            bt_cmd += ["--no-trail"]
        if args.trail_mode is not None:
            bt_cmd += ["--stop-trail", args.trail_mode]
        if args.tp_regime:
            bt_cmd += ["--tp-regime"]   # regime-adaptive TP cap by HMM state (Task 5)
        # Fixed-lot mode → clean R (no compounding inflation across the year).
        # This makes weekly R comparable and the total an honest R sum.
        if args.fixed_lot > 0:
            bt_cmd += ["--fixed-lot", str(args.fixed_lot)]
        bt = subprocess.run(bt_cmd, cwd=ENGINE, env=env,
                            capture_output=True, text=True,
                            encoding="utf-8", errors="replace")

        report = (bt.stdout or "") + "\n" + (bt.stderr or "")
        (RESULTS / f"{tag}.txt").write_text(report, encoding="utf-8")
        # Preserve THIS week's OOS trades + signals — backtest_replay overwrites
        # logs/backtest_*.csv every week, so copy them out before the next week.
        import shutil as _sh
        # 2026-06-27 Bug K: glob the output (matches the trail-mode suffix, e.g.
        # backtest_trades_st-htf.csv after the HTF default). The old exact name
        # "backtest_trades.csv" stopped matching once Bug F made the file suffixed,
        # so per-week trades were never copied → no ALL_OOS combine → no PF.
        for _pat, _dst in [("backtest_trades*.csv",  f"trades_{w_start}.csv"),
                           ("backtest_signals*.csv", f"signals_{w_start}.csv")]:
            _matches = sorted(RESULTS.glob(_pat))
            if _matches:
                _sh.copy(_matches[0], RESULTS / _dst)
        metrics = parse_report(report)
        row = {"week_start": w_start, "week_end": w_end, **metrics}
        cache.write_text(json.dumps(row), encoding="utf-8")
        all_rows.append(row)
        print(f"    R={metrics.get('total_r')} | trades={metrics.get('trades')} "
              f"| PF={metrics.get('pf')}")
        _eta_print(i, _wk_t0)

    # ── Aggregate ──
    print("\n" + "=" * 64)
    print("  WALK-FORWARD SUMMARY")
    print("=" * 64)
    total_r = sum(r["total_r"] for r in all_rows if r.get("total_r") is not None)
    total_trades = sum(r["trades"] for r in all_rows if r.get("trades") is not None)
    weeks_pos = sum(1 for r in all_rows if (r.get("total_r") or 0) > 0)
    weeks_neg = sum(1 for r in all_rows if (r.get("total_r") or 0) < 0)

    summary = []
    summary.append(f"Weeks tested : {len(all_rows)}")
    summary.append(f"Total R      : {total_r:+.1f}R")
    summary.append(f"Total trades : {total_trades}")
    summary.append(f"Positive weeks: {weeks_pos} | Negative: {weeks_neg}")
    if all_rows:
        summary.append(f"Avg R/week   : {total_r/len(all_rows):+.2f}R")
    summary.append("")
    summary.append("Week-by-week:")
    cum = 0.0
    for r in all_rows:
        tr = r.get("total_r") or 0
        cum += tr
        summary.append(f"  {r['week_start']}  R={tr:+6.1f}  cum={cum:+7.1f}  "
                       f"trades={r.get('trades')}")

    out_txt = "\n".join(summary)
    print(out_txt)
    (RESULTS / "_WFO_SUMMARY.txt").write_text(out_txt, encoding="utf-8")
    print(f"\n  Saved: wfo_results/_WFO_SUMMARY.txt")

    # 2026-07-02 (Divyesh): also save the backtest result as CSV — week-by-week
    # rows (R, cum R, trades, PF, WR, DD) + a TOTAL row. Opens directly in Excel.
    try:
        import csv as _csv
        with open(RESULTS / "_WFO_SUMMARY.csv", "w", newline="",
                  encoding="utf-8-sig") as _fcsv:
            _w = _csv.writer(_fcsv)
            _w.writerow(["week_start", "week_end", "total_r", "cum_r",
                         "trades", "pf", "wr_pct", "max_dd_pct"])
            _cum = 0.0
            for r in all_rows:
                _tr = r.get("total_r") or 0
                _cum += _tr
                _w.writerow([r.get("week_start"), r.get("week_end"), _tr,
                             round(_cum, 2), r.get("trades"), r.get("pf"),
                             r.get("wr"), r.get("dd")])
            _w.writerow([])
            _w.writerow(["TOTAL", f"{len(all_rows)} weeks", round(total_r, 1), "",
                         total_trades, f"pos={weeks_pos}", f"neg={weeks_neg}",
                         (f"avg/week={total_r/len(all_rows):+.2f}R" if all_rows else "")])
        print(f"  Saved: {RESULTS.name}/_WFO_SUMMARY.csv")
    except Exception as _e:
        print(f"  (could not write _WFO_SUMMARY.csv: {_e})")

    # Combine every week's OOS trades + signals into single full-history files.
    import pandas as _pd, glob as _glob
    for _kind in ("trades", "signals"):
        _files = sorted(_glob.glob(str(RESULTS / f"{_kind}_*.csv")))
        if _files:
            try:
                _df = _pd.concat([_pd.read_csv(_f) for _f in _files], ignore_index=True)
                _df.to_csv(RESULTS / f"ALL_OOS_{_kind}.csv", index=False)
                print(f"  Combined {len(_files)} weeks -> wfo_results/ALL_OOS_{_kind}.csv ({len(_df)} rows)")
            except Exception as _e:
                print(f"  (could not combine {_kind}: {_e})")


if __name__ == "__main__":
    main()
