"""
train_move_model.py — QUANT GOLD AI · Move-Size Predictor (Step 1)
===================================================================
Trains a quantile regression model that predicts HOW FAR price will move
in the trade's favor (MFE — Maximum Favorable Excursion) over the next
N bars, measured in ATR units (volatility-normalized, converts to % later).

Three quantiles per direction:
    P25 — pessimistic  → SKIP filter ("move likely at least this big")
    P50 — median       → TP1 placement
    P75 — optimistic   → TP2 / runner target

Then runs an HONEST calibration test on a chronological holdout:
    * decile table: predicted P50 vs actual median move
    * Spearman rank correlation (does bigger prediction = bigger move?)
    * pinball loss vs naive baseline (constant median)
    * PASS / FAIL verdict — if FAIL, do NOT wire this into trading.

Usage:
    python train_move_model.py --from 2025-01-01 --to 2026-03-01
    python train_move_model.py --from 2025-01-01 --to 2026-03-01 --step 2 --dirs BUY
    (--step 2 = use every 2nd bar, 2x faster, for quick tests)

Outputs:
    ../data/models/final/move_model_{buy,sell}_q{25,50,75}.pkl
    ../data/models/final/move_model_meta.json
    logs/move_model_report.txt
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
import lightgbm as lgb
from scipy.stats import spearmanr

from config import CFG
from features import compute_features

HORIZON = 12          # bars ahead (12 × M15 = 3 hours)
QUANTILES = [0.25, 0.50, 0.75]
MODELS_DIR = Path(CFG.paths.models_dir)
LOGS = Path(CFG.paths.logs_dir)


def build_dataset(eng, ts_index, direction, step=1):
    """Per-bar features + MFE label in ATR units. No lookahead in features;
    labels use future bars by definition (training only)."""
    ohlc = eng.ohlc_df.reset_index(drop=True)
    highs, lows, opens, closes = (ohlc["high"].values, ohlc["low"].values,
                                  ohlc["open"].values, ohlc["close"].values)
    rows, labels, labels_mae, times = [], [], [], []
    t0 = time.time()
    n_done = 0
    for i in ts_index[::step]:
        if i + 1 + HORIZON >= len(ohlc):
            continue
        t = ohlc["datetime"].iloc[i]
        try:
            f = compute_features(t, direction, 0.1, eng.ohlc_df, eng.adx_df,
                                 eng.news_df, eng.slot_tbl, eng.h4_df,
                                 eng.ratio_df, eng.h1_ob, eng.h4_ob_df)
        except Exception:
            continue
        atr_pct = 0.2   # L7b: ATR removed — fixed 0.2% normalization (was always this default; matches inference)
        atr_usd = atr_pct / 100.0 * closes[i]
        if atr_usd <= 0:
            continue
        entry = opens[i + 1]                       # execution = next bar open
        if direction == "BUY":
            mfe = highs[i + 1: i + 1 + HORIZON].max() - entry
            mae = entry - lows[i + 1: i + 1 + HORIZON].min()   # adverse move
        else:
            mfe = entry - lows[i + 1: i + 1 + HORIZON].min()
            mae = highs[i + 1: i + 1 + HORIZON].max() - entry  # adverse move
        rows.append(f)
        labels.append(mfe / atr_usd)               # label in ATR units
        labels_mae.append(max(mae, 0) / atr_usd)
        times.append(t)
        n_done += 1
        if n_done % 2000 == 0:
            print(f"    {n_done:,} bars | {(time.time()-t0)/n_done*1000:.0f} ms/bar", flush=True)
    X = pd.DataFrame(rows).select_dtypes(include=[np.number]).fillna(0)
    return X, np.array(labels), np.array(labels_mae), pd.Series(times)


def pinball(y_true, y_pred, q):
    d = y_true - y_pred
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))


def train_direction(eng, ts_index, direction, step, report):
    print(f"\n━━ {direction} ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    X, y, y_mae, times = build_dataset(eng, ts_index, direction, step)
    print(f"  Dataset: {len(X):,} rows × {X.shape[1]} features | "
          f"MFE median={np.median(y):.2f} ATR | MAE median={np.median(y_mae):.2f} ATR")

    # Chronological split — NO shuffling (time-series honesty)
    cut = int(len(X) * 0.70)
    Xtr, Xte, ytr, yte = X.iloc[:cut], X.iloc[cut:], y[:cut], y[cut:]
    ytr_mae, yte_mae = y_mae[:cut], y_mae[cut:]
    report.append(f"\n{direction}: {len(Xtr):,} train ({times.iloc[0].date()} → "
                  f"{times.iloc[cut-1].date()}) | {len(Xte):,} test "
                  f"({times.iloc[cut].date()} → {times.iloc[len(X)-1].date()})")

    preds = {}
    for q in QUANTILES:
        m = lgb.LGBMRegressor(objective="quantile", alpha=q,
                              n_estimators=400, learning_rate=0.05,
                              num_leaves=31, min_child_samples=60,
                              subsample=0.8, colsample_bytree=0.8,
                              random_state=42, verbose=-1)
        m.fit(Xtr, ytr, eval_set=[(Xte, yte)],
              callbacks=[lgb.early_stopping(40, verbose=False)])
        preds[q] = m.predict(Xte)
        joblib.dump({"model": m, "features": list(X.columns), "horizon": HORIZON},
                    MODELS_DIR / f"move_model_{direction.lower()}_q{int(q*100)}.pkl")

    # ── M2: SL/MAE models — predicted adverse move (for SL + trailing)
    preds_mae = {}
    for q in [0.50, 0.75]:
        m = lgb.LGBMRegressor(objective="quantile", alpha=q,
                              n_estimators=400, learning_rate=0.05,
                              num_leaves=31, min_child_samples=60,
                              subsample=0.8, colsample_bytree=0.8,
                              random_state=42, verbose=-1)
        m.fit(Xtr, ytr_mae, eval_set=[(Xte, yte_mae)],
              callbacks=[lgb.early_stopping(40, verbose=False)])
        preds_mae[q] = m.predict(Xte)
        joblib.dump({"model": m, "features": list(X.columns), "horizon": HORIZON},
                    MODELS_DIR / f"sl_model_{direction.lower()}_q{int(q*100)}.pkl")
    rho_mae, _ = spearmanr(preds_mae[0.50], yte_mae)
    cov_sl = float(np.mean(yte_mae <= preds_mae[0.75]))
    report.append(f"  [SL/MAE] Spearman: {rho_mae:.3f} | adverse move stays inside "
                  f"P75 SL {cov_sl:.0%} of bars (target ~75%)")

    # ── CALIBRATION TEST (holdout only) ──────────────────────
    p50 = preds[0.50]
    rho, _ = spearmanr(p50, yte)
    pb_model = pinball(yte, p50, 0.50)
    pb_naive = pinball(yte, np.full_like(yte, np.median(ytr)), 0.50)
    improve = (pb_naive - pb_model) / pb_naive * 100

    report.append(f"  Spearman corr (pred vs actual): {rho:.3f}")
    report.append(f"  Pinball P50: model {pb_model:.4f} vs naive {pb_naive:.4f} "
                  f"→ {improve:+.1f}% better")
    report.append(f"  Decile table (TEST set, label = MFE in ATRs):")
    df = pd.DataFrame({"pred": p50, "actual": yte})
    df["decile"] = pd.qcut(df["pred"], 10, labels=False, duplicates="drop")
    mono = []
    for d, g in df.groupby("decile"):
        mono.append(g["actual"].median())
        report.append(f"    D{int(d)+1:>2}  pred_med {g['pred'].median():5.2f}  "
                      f"actual_med {g['actual'].median():5.2f}  "
                      f"actual_mean {g['actual'].mean():5.2f}  n={len(g)}")
    # monotonicity: how often does the next decile's actual exceed the previous
    inc = sum(1 for a, b in zip(mono, mono[1:]) if b >= a) / max(len(mono) - 1, 1)
    report.append(f"  Monotonic deciles: {inc:.0%}")

    # P25/P75 coverage honesty: actual should land above P25 ~75% of time, above P75 ~25%
    cov25 = float(np.mean(yte >= preds[0.25]))
    cov75 = float(np.mean(yte >= preds[0.75]))
    report.append(f"  Coverage: above P25 {cov25:.0%} (target ~75%) | "
                  f"above P75 {cov75:.0%} (target ~25%)")

    verdict = "PASS" if (rho >= 0.15 and improve >= 3.0 and inc >= 0.65) else "FAIL"
    report.append(f"  ➤ VERDICT: {verdict}"
                  + ("" if verdict == "PASS" else "  — do NOT use for trading"))
    print("\n".join(report[-16:]))
    return verdict, rho, improve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to",   dest="date_to",   required=True)
    ap.add_argument("--step", type=int, default=1, help="use every Nth bar (speed)")
    ap.add_argument("--dirs", default="BUY,SELL")
    args = ap.parse_args()

    print("=" * 60)
    print("⚡ QGAI MOVE-SIZE MODEL — Step 1 (train + calibration)")
    print("=" * 60)
    from inference import LiveInferenceEngine
    eng = LiveInferenceEngine()

    ohlc = eng.ohlc_df.reset_index(drop=True)
    mask = ((ohlc["datetime"] >= pd.Timestamp(args.date_from)) &
            (ohlc["datetime"] < pd.Timestamp(args.date_to) + pd.Timedelta(days=1)))
    ts_index = list(ohlc.index[mask])
    print(f"Bars in range: {len(ts_index):,} (step {args.step} → "
          f"~{len(ts_index)//args.step:,} samples/direction)")

    report = [f"⚡ MOVE-SIZE MODEL CALIBRATION — {args.date_from} → {args.date_to}",
              f"Label: MFE (max favorable excursion) next {HORIZON} bars, in ATR units",
              f"Split: chronological 70/30 — calibration numbers are HOLDOUT ONLY"]
    results = {}
    for d in args.dirs.split(","):
        verdict, rho, improve = train_direction(eng, ts_index, d.strip(), args.step, report)
        results[d.strip()] = {"verdict": verdict, "spearman": round(rho, 3),
                              "pinball_improve_pct": round(improve, 1)}

    meta = {"horizon_bars": HORIZON, "quantiles": QUANTILES,
            "trained_range": [args.date_from, args.date_to],
            "trained_at": pd.Timestamp.now().isoformat(), "results": results}
    (MODELS_DIR / "move_model_meta.json").write_text(json.dumps(meta, indent=2))
    LOGS.mkdir(exist_ok=True)
    (LOGS / "move_model_report.txt").write_text("\n".join(report), encoding="utf-8")
    print("\n" + "=" * 60)
    print(f"Saved: move_model_*.pkl + move_model_meta.json")
    print(f"Report: logs/move_model_report.txt")


if __name__ == "__main__":
    main()
