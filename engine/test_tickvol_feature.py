"""
test_tickvol_feature.py - smoke test that volume is NOT a model feature.

2026-07-10:
RAW tick_volume was tested as a model input and rejected after weak 3-week WFO
(+2.8R vs +21.7R same baseline weeks). This test now protects that decision:
tick_volume may remain in OHLC data and computed feature dictionaries for
compatibility/debugging, but it must NOT be in FEATURE_COLS/model inputs.

Writes nothing to disk.
"""
import sys
from datetime import datetime as _dt

from config import CFG
from features import (
    FEATURE_COLS, load_trades, load_ohlc, load_adx, load_news,
    build_slot_table, build_feature_matrix, build_h4_range_table,
    build_trend_ratio_table, build_ob_table,
)

N_TRADES = 120


def fail(msg):
    print(f"\n  TEST FAILED: {msg}")
    sys.exit(1)


def main():
    print("\n" + "=" * 64)
    print("  SMOKE TEST - volume/tick_volume are NOT model features")
    print("=" * 64)

    print(f"\n[1/4] FEATURE_COLS = {len(FEATURE_COLS)} features")
    if "tick_volume" in FEATURE_COLS:
        fail("'tick_volume' is still in FEATURE_COLS. Remove it before retrain/WFO.")
    if "volume" in FEATURE_COLS:
        fail("normalized 'volume' is still in FEATURE_COLS. It should stay pruned.")
    print("      OK: 'tick_volume' absent")
    print("      OK: 'volume' absent")

    print("\n[2/4] Loading data (read-only)...")
    cfg = CFG.paths
    trades = load_trades(cfg.trades_file)
    ohlc_df = load_ohlc(cfg.ohlc_file)
    adx_df = load_adx(cfg.adx_file)
    news_df = load_news(cfg.news_file)
    ohlc_df = ohlc_df[ohlc_df["datetime"] <= _dt.now()].copy()
    adx_df = adx_df[adx_df["datetime"] <= _dt.now()].copy()
    print(f"      trades={len(trades):,}  ohlc={len(ohlc_df):,}  adx={len(adx_df):,}  news={len(news_df):,}")

    print(f"\n[3/4] Building feature matrix on last {N_TRADES} trades...")
    h4_df = build_h4_range_table(ohlc_df)
    ratio_df = build_trend_ratio_table(ohlc_df)
    h1_ob = build_ob_table(ohlc_df, "1h")
    h4_ob_df = build_ob_table(ohlc_df, "4h")
    slot_tbl = build_slot_table(trades.iloc[:int(len(trades) * 0.70)])
    trades_slice = trades.tail(N_TRADES).reset_index(drop=True)

    try:
        X, y, feat_names = build_feature_matrix(
            trades_slice, ohlc_df, adx_df, news_df, slot_tbl,
            h4_df=h4_df, ratio_df=ratio_df, h1_ob=h1_ob, h4_ob_df=h4_ob_df,
        )
    except Exception as e:
        fail(f"build_feature_matrix crashed: {type(e).__name__}: {e}")

    print(f"      OK: matrix built: {X.shape[0]} trades x {X.shape[1]} features")

    print("\n[4/4] Matrix column checks...")
    if X.shape[1] != len(FEATURE_COLS):
        fail(f"matrix width {X.shape[1]} != len(FEATURE_COLS) {len(FEATURE_COLS)}")
    if "tick_volume" in feat_names:
        fail("'tick_volume' returned in feat_names. It must not be model input.")
    if "volume" in feat_names:
        fail("'volume' returned in feat_names. It must not be model input.")
    print(f"      OK: width matches FEATURE_COLS ({X.shape[1]})")
    print("      OK: no volume columns in model matrix")

    print("\n" + "=" * 64)
    print("  SMOKE TEST PASSED - volume removed from model inputs.")
    print("  Next: retrain, then WFO-gate before adopting.")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
