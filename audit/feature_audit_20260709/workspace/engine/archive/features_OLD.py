"""
features.py
───────────
All price-based calculations in % with 4 decimal precision.

Formula: pct = round((value / close) * 100, 4)

Example:
  Gold close = $4000
  Range = $40 → 40/4000 * 100 = 1.0000%
  ATR   = $8  → 8/4000  * 100 = 0.2000%
"""

import numpy as np
import pandas as pd
from config import CFG
from pathlib import Path

SLOT_WIN_RATE = {}
PIP_SIZE      = 0.01    # 1 pip = $0.01 for XAUUSD
PCT_DECIMALS  = 4       # 4 decimal % precision


def to_pct(value, close):
    """Convert $ value to % of price. 4 decimal precision."""
    return round(float(value) / (float(close) + 1e-9) * 100, PCT_DECIMALS)


def build_slot_table(trades_df: pd.DataFrame) -> dict:
    df = trades_df.copy()
    df["slot"] = df["datetime"].dt.hour * 4 + df["datetime"].dt.minute // 15
    tbl = df.groupby("slot")["win_bin"].mean().to_dict()
    global SLOT_WIN_RATE
    SLOT_WIN_RATE = tbl
    return tbl


# ─────────────────────────────────────────────
# LOADERS
# ─────────────────────────────────────────────

def load_trades(path: str) -> pd.DataFrame:
    if path.endswith(".xlsx") or path.endswith(".xls"):
        try:
            df = pd.read_excel(path, sheet_name="Clean_Trades_Final")
        except Exception:
            df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    # Date + time columns combine to 'YYYY-MM-DD HH:MM:SS' — explicit, no guessing
    date_str = df["Open Date"].astype(str) + " " + df["Open Time (24h)"].astype(str)
    df["datetime"] = pd.to_datetime(date_str, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    bad = df["datetime"].isna().sum()
    if bad:
        print(f"  ⚠ load_trades: {bad} rows had unparseable datetimes and were dropped")
    df = df[df["datetime"].notna()].copy()

    # Win/Loss
    if "Win" in df.columns:
        df["win_bin"] = (df["Win"] == "✓").astype(int)
    else:
        df["win_bin"] = (
            ((df["Type"] == "BUY")  & (df["Exit Price"] > df["Entry Price"])) |
            ((df["Type"] == "SELL") & (df["Exit Price"] < df["Entry Price"]))
        ).astype(int)

    # Volume
    if "Volume" not in df.columns:
        df["Volume"] = df.get("tick_volume", 0.1)

    # % move (4 decimal)
    df["move_pct"] = df.apply(
        lambda r: round(abs(r["Exit Price"] - r["Entry Price"]) / r["Entry Price"] * 100, PCT_DECIMALS),
        axis=1
    )

    df = df.sort_values("datetime").reset_index(drop=True)

    # Time Window Filter — only for training if training_time_filter=True
    if False:  # train on ALL data
        h = df["datetime"].dt.hour
        m = df["datetime"].dt.minute
        w1 = (h == 7) | ((h == 8) & (m < 45))
        w2 = (h >= 16) & (h < 19)
        before = len(df)
        df = df[w1 | w2].reset_index(drop=True)
        print(f"  Time filter: {before} → {len(df)} trades (training only)")
    else:
        print(f"  Training on ALL {len(df):,} trades (Option 1 — no time filter)")
        print(f"  Time filter will apply at INFERENCE only!")

    print(f"  Trades : {len(df):,} | Win rate: {df['win_bin'].mean()*100:.1f}%")
    print(f"  Avg move: {df['move_pct'].mean():.4f}% | Win avg: {df[df['win_bin']==1]['move_pct'].mean():.4f}% | Loss avg: {df[df['win_bin']==0]['move_pct'].mean():.4f}%")
    return df


def engineer_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """
    FIX #22: shared feature-engineering pipeline for OHLC.
    Used by BOTH load_ohlc (training/startup CSV) and live MT5 updates,
    so live bars get IDENTICAL columns/definitions to training data.
    Expects: datetime, open, high, low, close (+ tick_volume or volume).
    """
    df = df.sort_values("datetime").reset_index(drop=True)

    # Normalize volume column — accept both 'tick_volume' and 'volume'
    if "tick_volume" not in df.columns and "volume" in df.columns:
        df["tick_volume"] = df["volume"]
    elif "tick_volume" not in df.columns:
        df["tick_volume"] = 1.0  # fallback

    # Volume spike: high volume bar (no z-score — uses rolling ratio instead)
    df["vol_ma20"]  = df["tick_volume"].rolling(20).mean()
    df["vol_spike"] = (df["tick_volume"] > df["vol_ma20"] * 1.5).astype(int)

    # % based price features (4 decimal)
    df["body_pct"]       = ((df["close"] - df["open"]).abs() / df["close"] * 100).round(PCT_DECIMALS)
    df["upper_wick_pct"] = ((df["high"] - df[["open","close"]].max(axis=1)) / df["close"] * 100).round(PCT_DECIMALS)
    df["lower_wick_pct"] = ((df[["open","close"]].min(axis=1) - df["low"]) / df["close"] * 100).round(PCT_DECIMALS)
    df["range_pct"]      = ((df["high"] - df["low"]) / df["close"] * 100).round(PCT_DECIMALS)
    df["body_ratio"]     = (df["body_pct"] / (df["range_pct"] + 1e-9)).round(PCT_DECIMALS)
    df["is_bullish"]     = (df["close"] > df["open"]).astype(int)

    # Price position (0=day low, 1=day high) — already relative
    df["high_20"]    = df["high"].rolling(20).max()
    df["low_20"]     = df["low"].rolling(20).min()
    df["price_pos"]  = ((df["close"] - df["low_20"]) / (df["high_20"] - df["low_20"] + 1e-9)).round(4)

    # ATR % (4 decimal)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"]  - df["close"].shift(1)).abs()
    ], axis=1).max(axis=1)
    df["atr14_pct"]  = (tr.rolling(14).mean() / df["close"] * 100).round(PCT_DECIMALS)
    df["atr20_pct"]  = (tr.rolling(20).mean() / df["close"] * 100).round(PCT_DECIMALS)

    # Range ratio — current range vs 10-candle avg (already relative)
    df["range_ma10"]  = df["range_pct"].rolling(10).mean()
    df["range_ratio"] = (df["range_pct"] / (df["range_ma10"] + 1e-9)).round(4)

    # ── 200 EMA (data-proven: +3.8pp WR, +$8,709 P&L improvement) ──
    # Near EMA200 (±$10): WR=31% (-6pp) ← WORST zone, skip
    # FAR below EMA200 (>$60): WR=52% (+15pp) ← BEST
    # BUY $0-30 below EMA: WR=29.7% ← 4 consecutive losses zone
    df["ema200"]          = df["close"].ewm(span=200, adjust=False).mean().round(2)
    df["price_vs_ema200"] = ((df["close"] - df["ema200"]) / df["close"] * 100).round(4)  # % signed
    df["above_ema200"]    = (df["close"] > df["ema200"]).astype(int)
    df["ema200_dist_abs"] = df["price_vs_ema200"].abs().round(4)                          # % absolute
    df["near_ema200"]     = (df["ema200_dist_abs"] < 0.35).astype(int)                   # <0.35% ≈ $10 at $2800

    # Only drop rows where critical price columns are NaN
    # (not volume rolling which has NaN in first 20 rows)
    df.dropna(subset=["open","high","low","close","range_pct","atr14_pct"], inplace=True)
    return df


def load_ohlc(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    # Merged OHLC 'time' is always 'YYYY-MM-DD HH:MM:SS' after merge_data normalisation
    df["datetime"] = pd.to_datetime(df["time"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    bad = df["datetime"].isna().sum()
    if bad:
        print(f"  ⚠ load_ohlc: {bad} rows had unparseable timestamps and were dropped")
    df = df[df["datetime"].notna()].copy()
    df = engineer_ohlc(df)
    print(f"  OHLC   : {len(df):,} rows | avg range: {df['range_pct'].mean():.4f}% | avg ATR: {df['atr14_pct'].mean():.4f}%")
    return df


def load_adx(path: str) -> pd.DataFrame:
    if not __import__('pathlib').Path(path).exists():
        print(f"  ⚠️  ADX file not found: {path} — returning empty DataFrame")
        return pd.DataFrame()
    df = pd.read_csv(path, low_memory=False)
    if df.empty:
        print(f"  ⚠️  ADX file is empty: {path}")
        return df
    # Merged ADX 'timestamp' is always 'YYYY-MM-DD HH:MM:SS' after merge_data normalisation
    df["datetime"] = pd.to_datetime(df["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    # ADX values already in % (0-100) — no conversion needed
    for tf in ["M15","M30","H1","H4"]:
        if f"{tf}_PlusDI" in df.columns and f"{tf}_MinusDI" in df.columns:
            df[f"{tf}_DI_diff"] = (df[f"{tf}_PlusDI"] - df[f"{tf}_MinusDI"]).round(4)
    # NaN guard: fill NaN with 0 to prevent GaussianMixture crash
    adx_cols = [c for c in df.columns if any(tf in c for tf in ["M15","M30","H1","H4"])]
    df[adx_cols] = df[adx_cols].fillna(0)
    return df.sort_values("datetime").reset_index(drop=True)


def load_news(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["datetime"]  = pd.to_datetime(df["timestamp"])
    df["actual"]    = pd.to_numeric(df["actual"],   errors="coerce")
    df["forecast"]  = pd.to_numeric(df["forecast"], errors="coerce")
    df["previous"]  = pd.to_numeric(df["previous"], errors="coerce")
    df["deviation"] = df["actual"] - df["forecast"]
    df["abs_dev"]   = df["deviation"].abs()
    df["dev_sign"]  = df["deviation"].apply(
        lambda x: 1.0 if x>0 else -1.0 if x<0 else 0.0 if pd.notna(x) else 0.0)
    df["dev_norm"]  = df.groupby("event")["deviation"].transform(
        lambda x: (x - x.mean()) / (x.std() + 1e-9)).clip(-3, 3).fillna(0)
    df = df.sort_values("datetime").reset_index(drop=True)
    # Pre-compute impact subsets — stored as module-level cache, not df attributes
    # (Pandas 2.0+ does not allow custom attributes on DataFrame)
    _news_cache = {
        "news3":    df[df["impact"] == 3].reset_index(drop=True),
        "news2":    df[df["impact"] == 2].reset_index(drop=True),
        "news_eia": df[df["event"].str.contains("EIA Crude Oil Stocks Change", case=False, na=False)].reset_index(drop=True),
    }
    # Attach as a single dict attribute (one assignment = one warning suppressed)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df._news_cache = _news_cache
    return df






# ─────────────────────────────────────────────
# ORDER BLOCK FEATURES (H1 + H4)
# H4 bull_dist + H1 align = +6.3% win rate!
# ─────────────────────────────────────────────

def build_ob_table(ohlc_df: pd.DataFrame, timeframe: str = "1h") -> pd.DataFrame:
    """
    Build Order Block table from OHLC data.
    Bullish OB = bearish candle before strong up impulse
    Bearish OB = bullish candle before strong down impulse
    """
    tf = ohlc_df.groupby(ohlc_df["datetime"].dt.floor(timeframe)).agg(
        open=("open","first"), high=("high","max"),
        low=("low","min"), close=("close","last"),
        volume=("tick_volume","sum")
    ).reset_index()
    tf.columns = ["datetime","open","high","low","close","volume"]

    tf["move_pct"]   = ((tf["close"]-tf["open"])/tf["open"]*100).round(4)
    tf["range_pct"]  = ((tf["high"]-tf["low"])/tf["close"]*100).round(4)
    tf["range_ma10"] = tf["range_pct"].rolling(10).mean()
    tf["is_strong"]  = (tf["range_pct"] > tf["range_ma10"]*1.5).astype(int)

    tf["next_up"]   = ((tf["move_pct"].shift(-1) > 0) & (tf["is_strong"].shift(-1)==1)).astype(int)
    tf["next_down"] = ((tf["move_pct"].shift(-1) < 0) & (tf["is_strong"].shift(-1)==1)).astype(int)

    tf["bull_ob"] = ((tf["close"] < tf["open"]) & (tf["next_up"]==1)).astype(int)
    tf["bear_ob"] = ((tf["close"] > tf["open"]) & (tf["next_down"]==1)).astype(int)

    tf["bull_ob_high"] = tf["high"].where(tf["bull_ob"]==1)
    tf["bull_ob_low"]  = tf["low"].where(tf["bull_ob"]==1)
    tf["bear_ob_high"] = tf["high"].where(tf["bear_ob"]==1)
    tf["bear_ob_low"]  = tf["low"].where(tf["bear_ob"]==1)
    tf["ob_strength"]  = 0.0
    tf.loc[tf["bull_ob"]==1, "ob_strength"] = tf["range_pct"].shift(-1)[tf["bull_ob"]==1]
    tf.loc[tf["bear_ob"]==1, "ob_strength"] = tf["range_pct"].shift(-1)[tf["bear_ob"]==1]

    return tf.sort_values("datetime").reset_index(drop=True)


def get_ob_features(t: pd.Timestamp, price: float,
                    h1_ob: pd.DataFrame, h4_ob: pd.DataFrame,
                    trade_type: str = "BUY",
                    n_recent: int = 5, max_dist: float = 1.0) -> dict:
    """
    Direction-aware S/R Order-Block features (8 total: 4 per timeframe).

    For a trade direction, RESISTANCE = nearest OB ahead (profit direction),
    SUPPORT = nearest OB behind (loss direction).
      BUY  → resistance = bear OB above, support = bull OB below
      SELL → resistance = bull OB below, support = bear OB above

    Per timeframe (H4, H1):
      *_resist_dist : % distance to nearest resistance OB ahead (signed +)
      *_support_dist: % distance to nearest support OB behind
      *_in_zone     : 1 if price currently inside ANY recent OB zone, else 0
      *_strength    : ob_strength (range_pct) of the nearest resistance OB

    All OBs are strictly PAST (datetime < t) — no lookahead.
    Returns % distances (price-independent / stationary).
    """
    is_buy = str(trade_type).upper() == "BUY"

    def scan(ob_df, ob_col, high_col, low_col, ahead_is_above):
        """Return (nearest_dist_pct, in_zone_flag, strength) for OB type.
        ahead_is_above: True → only OBs ABOVE price count (resistance for BUY);
                        False → only OBs BELOW price count."""
        past = ob_df[(ob_df["datetime"] < t) & (ob_df[ob_col]==1)].tail(n_recent)
        best_dist = 999.0
        in_zone = 0
        strength = 0.0
        for _, ob in past.iterrows():
            hi, lo = ob[high_col], ob[low_col]
            if pd.isna(hi) or pd.isna(lo):
                continue
            # in-zone: price between this OB's low and high
            if lo <= price <= hi:
                in_zone = 1
            mid = (hi + lo) / 2
            # directional filter: count only OBs on the correct side
            if ahead_is_above and mid < price:
                continue
            if (not ahead_is_above) and mid > price:
                continue
            dist = abs(price - mid) / price * 100
            if dist < best_dist:
                best_dist = dist
                strength = float(ob.get("ob_strength", 0.0) or 0.0)
        return min(best_dist, 999.0), in_zone, round(strength, 4)

    out = {}
    for tf_name, ob_df in (("h4", h4_ob), ("h1", h1_ob)):
        # RESISTANCE = profit-direction OB
        #   BUY  → bear OB above ; SELL → bull OB below
        if is_buy:
            r_dist, r_zone, r_str = scan(ob_df, "bear_ob", "bear_ob_high", "bear_ob_low", ahead_is_above=True)
            s_dist, s_zone, _     = scan(ob_df, "bull_ob", "bull_ob_high", "bull_ob_low", ahead_is_above=False)
        else:
            r_dist, r_zone, r_str = scan(ob_df, "bull_ob", "bull_ob_high", "bull_ob_low", ahead_is_above=False)
            s_dist, s_zone, _     = scan(ob_df, "bear_ob", "bear_ob_high", "bear_ob_low", ahead_is_above=True)
        out[f"{tf_name}_resist_dist"]  = round(r_dist, 4)
        out[f"{tf_name}_support_dist"] = round(s_dist, 4)
        out[f"{tf_name}_in_ob_zone"]   = int(r_zone or s_zone)
        out[f"{tf_name}_ob_strength"]  = r_str
    return out

# ─────────────────────────────────────────────
# H4 RANGE BOUND PATTERN
# After 2-4% cumulative move → 32-40hr range
# ─────────────────────────────────────────────

def build_h4_range_table(ohlc_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build H4 candles from M15 OHLC.
    Compute cumulative 3-H4 move to detect big moves.
    Returns H4 dataframe with range-bound flags.
    """
    ohlc_df = ohlc_df.copy()
    ohlc_df["h4_group"] = ohlc_df["datetime"].dt.floor("4h")

    h4 = ohlc_df.groupby("h4_group").agg(
        open  = ("open",  "first"),
        high  = ("high",  "max"),
        low   = ("low",   "min"),
        close = ("close", "last"),
    ).reset_index()
    h4.rename(columns={"h4_group": "datetime"}, inplace=True)

    # H4 move % (4 decimal)
    h4["h4_move_pct"] = ((h4["close"] - h4["open"]) / h4["open"] * 100).round(4)

    # Cumulative 3-H4 move
    h4["cum3_move_pct"] = ((h4["close"] - h4["close"].shift(3)) /
                           (h4["close"].shift(3) + 1e-9) * 100).round(4)

    # Big move flag: cumulative 3-H4 >= 2%
    h4["is_big_move"]      = (h4["cum3_move_pct"].abs() >= 2.0).astype(int)
    h4["big_move_size"]    = h4["cum3_move_pct"].abs().round(4)
    h4["big_move_dir"]     = h4["cum3_move_pct"].apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)

    # Range phase: current H4 move < 0.5% = consolidating
    h4["in_range_phase"]   = (h4["h4_move_pct"].abs() < 0.5).astype(int)

    return h4.reset_index(drop=True)


def get_range_features(t: pd.Timestamp, h4_df: pd.DataFrame) -> dict:
    """
    For a given M15 candle time t, compute 5 range-bound features.
    Looks back at last 10 H4 candles to find big move.
    """
    # Get H4 candles up to current time — searchsorted 150× faster
    _t64    = t.to_datetime64() if hasattr(t, 'to_datetime64') else np.datetime64(t)
    _h4_idx = int(np.searchsorted(h4_df['datetime'].values, _t64, side='right')) if h4_df is not None else 0
    past_h4 = h4_df.iloc[:_h4_idx].tail(12) if h4_df is not None else pd.DataFrame()

    if len(past_h4) < 4:
        return {
            "is_post_big_move":   0,
            "big_move_direction": 0,
            "big_move_size_pct":  0.0,
            "in_range_phase":     0,
        }

    # Find most recent big move in last 10 H4 candles
    big_move_rows = past_h4[past_h4["is_big_move"] == 1]

    if len(big_move_rows) == 0:
        return {
            "is_post_big_move":   0,
            "big_move_direction": 0,
            "big_move_size_pct":  0.0,
            "in_range_phase":     int(past_h4.iloc[-1]["in_range_phase"]),
        }

    # Most recent big move
    last_big     = big_move_rows.iloc[-1]

    return {
        "is_post_big_move":   1,
        "big_move_direction": int(last_big["big_move_dir"]),
        "big_move_size_pct":  float(last_big["big_move_size"]),
        "in_range_phase":     int(past_h4.iloc[-1]["in_range_phase"]),
    }



def build_trend_ratio_table(ohlc_df: pd.DataFrame) -> pd.DataFrame:
    """
    Builds H4 swing table with correction/impulse ratio.
    correction_impulse_ratio > 2.0 = Strong trend
    correction_impulse_ratio < 1.5 = Weak/choppy
    """
    ohlc_df = ohlc_df.copy()
    ohlc_df["h4_group"] = ohlc_df["datetime"].dt.floor("4h")
    h4 = ohlc_df.groupby("h4_group").agg(
        open  = ("open",  "first"),
        high  = ("high",  "max"),
        low   = ("low",   "min"),
        close = ("close", "last"),
    ).reset_index()
    h4.rename(columns={"h4_group": "datetime"}, inplace=True)

    # Find swing highs and lows (n=3)
    n = 3
    swing_list = []
    for i in range(n, len(h4) - n):
        is_high = all(h4["high"].iloc[i] > h4["high"].iloc[i-j] for j in range(1,n+1)) and                   all(h4["high"].iloc[i] > h4["high"].iloc[i+j] for j in range(1,n+1))
        is_low  = all(h4["low"].iloc[i]  < h4["low"].iloc[i-j]  for j in range(1,n+1)) and                   all(h4["low"].iloc[i]  < h4["low"].iloc[i+j]  for j in range(1,n+1))
        if is_high:
            swing_list.append({"idx": i, "datetime": h4["datetime"].iloc[i],
                               "price": h4["high"].iloc[i], "type": "HIGH"})
        elif is_low:
            swing_list.append({"idx": i, "datetime": h4["datetime"].iloc[i],
                               "price": h4["low"].iloc[i], "type": "LOW"})

    if not swing_list:
        h4["corr_imp_ratio"] = 1.0
        return h4[["datetime","corr_imp_ratio"]].reset_index(drop=True)
    swings = pd.DataFrame(swing_list).sort_values("idx").reset_index(drop=True)

    # Compute recent ratio for each H4 candle
    h4["corr_imp_ratio"] = 1.0

    # For each swing pair compute ratio
    ratios = []
    for i in range(1, len(swings)):
        prev = swings.iloc[i-1]
        curr = swings.iloc[i]
        candles = curr["idx"] - prev["idx"]
        move    = abs(curr["price"] - prev["price"]) / prev["price"] * 100
        if move < 0.3 or candles < 2:
            continue
        ratios.append({
            "start_idx": prev["idx"],
            "end_idx":   curr["idx"],
            "candles":   candles,
            "direction": "UP" if curr["type"]=="HIGH" else "DOWN",
        })

    # Compute rolling ratio: last UP candles / last DOWN candles
    ratio_records = []
    for i in range(len(ratios) - 1):
        curr_leg = ratios[i]
        next_leg = ratios[i+1]
        if curr_leg["direction"] == "DOWN" and next_leg["direction"] == "UP":
            ratio = next_leg["candles"] / (curr_leg["candles"] + 1e-9)
            ratio_records.append({
                "h4_idx": next_leg["end_idx"],
                "ratio":  round(ratio, 2),
            })
        elif curr_leg["direction"] == "UP" and next_leg["direction"] == "DOWN":
            ratio = curr_leg["candles"] / (next_leg["candles"] + 1e-9)
            ratio_records.append({
                "h4_idx": next_leg["end_idx"],
                "ratio":  round(ratio, 2),
            })

    # Assign ratio to h4 rows
    for rec in ratio_records:
        idx = rec["h4_idx"]
        if idx < len(h4):
            h4.at[idx, "corr_imp_ratio"] = rec["ratio"]

    # Forward fill ratio
    h4["corr_imp_ratio"]  = h4["corr_imp_ratio"].replace(1.0, np.nan).ffill().fillna(1.0)

    return h4[["datetime","corr_imp_ratio"]].reset_index(drop=True)


def get_trend_ratio_features(t: pd.Timestamp, ratio_df: pd.DataFrame) -> dict:
    """Get trend ratio features for timestamp t."""
    _t64  = t.to_datetime64() if hasattr(t, 'to_datetime64') else np.datetime64(t)
    _idx  = int(np.searchsorted(ratio_df['datetime'].values, _t64, side='right'))
    past  = ratio_df.iloc[:_idx]
    if len(past) == 0:
        return {"corr_imp_ratio": 1.0}
    row = past.iloc[-1]
    return {
        "corr_imp_ratio":  round(float(row["corr_imp_ratio"]), 2),
    }

# ─────────────────────────────────────────────
# COMPUTE 54 FEATURES (46 + 5 range-bound + 3 trend-ratio)
# All price features in % (4 decimal)
# ─────────────────────────────────────────────

def _safe_int(val, default=0):
    """Safe int conversion — returns default if NaN/None."""
    try:
        v = float(val)
        return default if v != v else int(v)  # v!=v is NaN check
    except (TypeError, ValueError):
        return default

def compute_features(t, trade_type, volume, ohlc_df, adx_df, news_df, slot_table=None, h4_df=None, ratio_df=None, h1_ob=None, h4_ob_df=None):
    f = {}
    slot_tbl = slot_table or SLOT_WIN_RATE
    hour     = t.hour
    slot     = hour * 4 + t.minute // 15
    slot_wr  = slot_tbl.get(slot, 0.372)

    # ── Fast lookup helpers (searchsorted = 150× faster than boolean filter) ──
    _t64 = t.to_datetime64() if hasattr(t, 'to_datetime64') else np.datetime64(t)

    def _ohlc_upto(df=ohlc_df):
        idx = int(np.searchsorted(df['datetime'].values, _t64, side='right'))
        return df.iloc[:idx]

    def _adx_upto(df=adx_df):
        idx = int(np.searchsorted(df['datetime'].values, _t64, side='right'))
        return df.iloc[:idx]

    def _h4_upto(df=h4_df):
        if df is None: return None
        idx = int(np.searchsorted(df['datetime'].values, _t64, side='right'))
        return df.iloc[:idx]

    def _news_after(df, impact=None):
        _cache = getattr(df, '_news_cache', {})
        if impact == 3:   src = _cache.get("news3", df[df["impact"]==3])
        elif impact == 2: src = _cache.get("news2", df[df["impact"]==2])
        else:             src = df
        idx = int(np.searchsorted(src['datetime'].values, _t64, side='right'))
        return src.iloc[idx:]

    def _news_before(df, impact=None):
        _cache = getattr(df, '_news_cache', {})
        if impact == 3:   src = _cache.get("news3", df[df["impact"]==3])
        elif impact == 2: src = _cache.get("news2", df[df["impact"]==2])
        else:             src = df
        idx = int(np.searchsorted(src['datetime'].values, _t64, side='right'))
        return src.iloc[:idx]

    # ── GROUP 1: TIME + SLOT (11) ──
    f["15_min_slot"]   = slot
    f["slot_win_rate"] = round(slot_wr, 4)
    f["is_hot_slot"]   = int(slot_wr > 0.50)
    f["is_dead_slot"]  = int(slot_wr < 0.25)
    f["slot_sin"]      = round(np.sin(2 * np.pi * slot / 96), 4)
    f["slot_cos"]      = round(np.cos(2 * np.pi * slot / 96), 4)
    f["hour"]          = hour
    f["hour_sin"]      = round(np.sin(2 * np.pi * hour / 24), 4)
    f["hour_cos"]      = round(np.cos(2 * np.pi * hour / 24), 4)
    f["session_NY"]    = int(13 <= hour < 20)
    f["session_Asia"]  = int(1  <= hour < 8)
    f["day_of_week"]   = pd.Timestamp(t).dayofweek  # 0=Mon...4=Fri

    # ── SESSION SCORE — Data-proven (2,788 trades backtest) ──
    # +2: 16-18 UTC (NY Open)   → WR=49-52% (+12-15pp) BEST
    # +1: 04,05,20,21 UTC       → WR=40-47% (+3-10pp)
    #  0: neutral
    # -1: 10,11,13,22,23 UTC    → WR=29-36% (-1 to -8pp)
    # -2: 06,12 UTC             → WR=22-28% (-9 to -15pp) WORST
    if hour in [16, 17, 18]:
        f["session_score"] = 2
    elif hour in [4, 5, 20, 21]:
        f["session_score"] = 1
    elif hour in [6, 12]:
        f["session_score"] = -2
    elif hour in [10, 11, 13, 22, 23]:
        f["session_score"] = -1
    else:
        f["session_score"] = 0
    f["is_ny_session"] = int(hour in [15, 16, 17, 18])  # WR=40-52%
    f["is_dead_hour"]  = int(hour in [9, 20])  # actual low WR hours: 09 UTC=57.1%, 20 UTC=58.8%

    # ── GROUP 2: OHLC + VOLUME (12) — all % based ──
    ohlc_row = _ohlc_upto()
    if len(ohlc_row) > 0:
        r = ohlc_row.iloc[-1]
        f["vol_spike"]       = _safe_int(r.get("vol_spike", 0)) if str(r.get("vol_spike","nan")) not in ("nan","NaN","") else 0
        f["atr14_pct"]       = float(r["atr14_pct"])      # e.g. 0.2125%
        f["atr20_pct"]       = float(r["atr20_pct"])      # 5hr lookback (better!)
        f["range_pct"]       = float(r["range_pct"])      # e.g. 0.3075%
        f["body_pct"]        = float(r["body_pct"])       # e.g. 0.1050%
        f["lower_wick_pct"]  = float(r["lower_wick_pct"]) # e.g. 0.0250%
        f["upper_wick_pct"]  = float(r["upper_wick_pct"]) # e.g. 0.0300%
        f["price_pos"]       = float(r["price_pos"])      # 0-1 relative
        f["body_ratio"]      = float(r["body_ratio"])     # relative
        f["range_ratio"]     = float(r["range_ratio"])    # relative
        f["tick_volume"]     = float(r["tick_volume"])    # raw count
        f["is_bullish_candle"] = _safe_int(r.get("is_bullish", 0)) if str(r.get("is_bullish","nan")) not in ("nan","NaN","") else 0

        # ── EMA200 FEATURES (data-proven: +3.8pp WR) ─────────────────
        for _ema_col in ["ema200","price_vs_ema200","above_ema200","ema200_dist_abs","near_ema200"]:
            f[_ema_col] = float(r[_ema_col]) if _ema_col in r.index else 0.0

        # ── PRICE MOMENTUM FEATURES (data-proven, backtest analysis) ──
        # Key finding: BUY when 4hr price dropped → WR=31% (AVOID)
        #              BUY when 4hr price rose    → WR=52% (TRADE)
        #              SELL when 4hr price dropped >$40 → WR=67-74% (BEST)
        # These 4 features explain your 4 consecutive BUY losses
        price_now = float(r["close"]) if "close" in r.index else 0.0

        # ── GAP DETECTION ─────────────────────────────────────────────
        # If last bar time differs by more than expected (M15 = 15min per bar),
        # we may be crossing a data gap → momentum features would be artificial
        def _bar_time(row_idx):
            if row_idx >= 0 and row_idx < len(ohlc_df):
                return ohlc_df.iloc[row_idx]["datetime"]
            return None

        last_idx = len(ohlc_row) - 1
        last_bar_dt = ohlc_row.iloc[-1]["datetime"]

        def _has_gap(bars_back):
            """True if there is a gap ≥ 45min across the lookback window."""
            if len(ohlc_row) < bars_back + 1:
                return True
            t_now  = ohlc_row.iloc[-1]["datetime"]
            t_back = ohlc_row.iloc[-(bars_back+1)]["datetime"]
            expected_mins = bars_back * 15
            actual_mins   = (t_now - t_back).total_seconds() / 60
            return actual_mins > expected_mins + 45  # 45min tolerance for weekend/holiday

        # 1hr move = price now vs 4 bars ago — zero if gap detected
        if len(ohlc_row) >= 5 and price_now > 0 and not _has_gap(4):
            price_1hr_ago = float(ohlc_row.iloc[-5]["close"])
            f["move_1hr"] = round((price_now - price_1hr_ago) / price_1hr_ago * 100, 4) if price_1hr_ago > 0 else 0.0
        else:
            f["move_1hr"] = 0.0

        # 2hr move = price now vs 8 bars ago
        if len(ohlc_row) >= 9 and price_now > 0 and not _has_gap(8):
            price_2hr_ago = float(ohlc_row.iloc[-9]["close"])
            f["move_2hr"] = round((price_now - price_2hr_ago) / price_2hr_ago * 100, 4) if price_2hr_ago > 0 else 0.0
        else:
            f["move_2hr"] = 0.0

        # 4hr move = price now vs 16 bars ago
        if len(ohlc_row) >= 17 and price_now > 0 and not _has_gap(16):
            price_4hr_ago = float(ohlc_row.iloc[-17]["close"])
            f["move_4hr"] = round((price_now - price_4hr_ago) / price_4hr_ago * 100, 4) if price_4hr_ago > 0 else 0.0
        else:
            f["move_4hr"] = 0.0

        # 8hr move = price now vs 32 bars ago
        if len(ohlc_row) >= 33 and price_now > 0 and not _has_gap(32):
            price_8hr_ago = float(ohlc_row.iloc[-33]["close"])
            f["move_8hr"] = round((price_now - price_8hr_ago) / price_8hr_ago * 100, 4) if price_8hr_ago > 0 else 0.0
        else:
            f["move_8hr"] = 0.0
        # Signal-aligned momentum: +1 if momentum agrees with signal, -1 if against
        _is_buy_m = int(str(trade_type).upper() == "BUY")
        f["momentum_aligned_1hr"] = 1 if (_is_buy_m and f["move_1hr"] > 0) or (not _is_buy_m and f["move_1hr"] < 0) else -1 if f["move_1hr"] != 0 else 0
        f["momentum_aligned_2hr"] = 1 if (_is_buy_m and f["move_2hr"] > 0) or (not _is_buy_m and f["move_2hr"] < 0) else -1 if f["move_2hr"] != 0 else 0
        f["momentum_aligned_4hr"] = 1 if (_is_buy_m and f["move_4hr"] > 0) or (not _is_buy_m and f["move_4hr"] < 0) else -1 if f["move_4hr"] != 0 else 0
    else:
        for k in ["vol_spike","atr14_pct","atr20_pct","range_pct","body_pct",
                  "lower_wick_pct","upper_wick_pct","price_pos","body_ratio",
                  "range_ratio","tick_volume","is_bullish_candle",
                  "move_1hr","move_2hr","move_4hr","move_8hr",
                  "momentum_aligned_1hr","momentum_aligned_2hr","momentum_aligned_4hr",
                  "ema200","price_vs_ema200","above_ema200","ema200_dist_abs","near_ema200"]:
            f[k] = 0.0

    # ── GROUP 3: ADX (10) — already % scale ──
    adx_row = _adx_upto()
    if len(adx_row) > 0:
        a = adx_row.iloc[-1]
        for tf in ["M15","M30","H1","H4"]:
            f[f"{tf}_ADX"]     = round(float(a[f"{tf}_ADX"]), 4)
            f[f"{tf}_DI_diff"] = round(float(a[f"{tf}_DI_diff"]), 4)
        f["adx_trend_count"]     = sum([int(a[f"{tf}_ADX"] > 20) for tf in ["M15","M30","H1","H4"]])
        f["london_adx_filtered"] = int((1 <= hour < 13) and float(a["M15_ADX"]) > 25)

        # ── ADX SLOPE — ROLLING (updates every M15 bar, no lookahead) ──
        # Standard H4_ADX freezes for 16 bars; rolling version recomputes
        # the 4hr window at every closed M15 bar (phase-grid trick).
        # Data: H4<19+falling = 30.3% WR (dead) | H4<19+rising = 42.2%
        try:
            _radx = get_rolling_adx(t, ohlc_df)
            f["h4_adx_slope"] = round(_radx["h4_now"] - _radx["h4_prev"], 6) \
                if (_radx["h4_now"] is not None and _radx["h4_prev"] is not None) else 0.0
            f["h1_adx_slope"] = round(_radx["h1_now"] - _radx["h1_prev"], 6) \
                if (_radx["h1_now"] is not None and _radx["h1_prev"] is not None) else 0.0
            f["_h4_adx_rolling"] = _radx["h4_now"]   # for ts_adx_switch (not a model feature)
        except Exception:
            f["h4_adx_slope"] = 0.0
            f["h1_adx_slope"] = 0.0
            f["_h4_adx_rolling"] = None
        f["h4_adx_rising"] = int(f["h4_adx_slope"] > 0)

        # ── H4/H1 Regime Alignment Features (data-proven) ────
        # Backtest analysis of 2,788 trades:
        # H4 Trending(>30) + H1 aligned → +3.7pp WR, +$11 avg P&L ⭐⭐
        # H4 Ranging(<20)  + H1 neutral → +1.8pp WR ⭐
        # H4 Ranging(<20)  + H1 strong  → -8.2pp WR ❌ (trap!)
        _h4_adx   = float(a["H4_ADX"])
        _h1_di    = float(a["H1_DI_diff"])
        _h1_di_abs= abs(_h1_di)
        _is_buy_f = int(str(trade_type).upper() == "BUY")
        _h1_aln   = (_h1_di > 10 and _is_buy_f == 1) or (_h1_di < -10 and _is_buy_f == 0)
        # Feature 1: H4 strongly trending + H1 confirms signal direction
        f["h4_trending_h1_aligned"] = int(_h4_adx > 30 and _h1_aln)
        # Feature 2: H4 ranging + H1 not overextended (early entry - good)
        f["h4_ranging_h1_neutral"]  = int(_h4_adx < 20 and _h1_di_abs < 10)
        # Feature 3: H4 ranging + H1 already strongly extended (AVOID)
        f["h4_ranging_h1_extended"] = int(_h4_adx < 20 and _h1_di_abs > 15)
        # Feature 4: Combined regime score (-1 to +2)
        if   _h4_adx > 30 and _h1_aln:      f["h4_h1_regime_score"] = 2
        elif _h4_adx > 25 and _h1_aln:      f["h4_h1_regime_score"] = 1
        elif _h4_adx < 20 and _h1_di_abs < 10: f["h4_h1_regime_score"] = 1
        elif _h4_adx < 20 and _h1_di_abs > 15: f["h4_h1_regime_score"] = -1
        else:                                f["h4_h1_regime_score"] = 0
    else:
        for tf in ["M15","M30","H1","H4"]:
            f[f"{tf}_ADX"]     = 0.0
            f[f"{tf}_DI_diff"] = 0.0
        f["adx_trend_count"]     = 0
        f["london_adx_filtered"] = 0
        f["h4_adx_slope"]        = 0.0
        f["h1_adx_slope"]        = 0.0
        f["h4_adx_rising"]       = 0
        f["h4_trending_h1_aligned"] = 0
        f["h4_ranging_h1_neutral"]  = 0
        f["h4_ranging_h1_extended"] = 0
        f["h4_h1_regime_score"]     = 0

    # ── GROUP 4: NEWS STAR RATING (8) ──
    _news_after_t = _news_after(news_df)
    upcoming = _news_after_t[_news_after_t['datetime'] <= t + pd.Timedelta(hours=2)]
    last3    = _news_before(news_df, impact=3)
    last2    = _news_before(news_df, impact=2)
    next3    = _news_after(news_df, impact=3)
    next2    = _news_after(news_df, impact=2)

    f["mins_to_next_3star"]    = min((next3["datetime"].min() - t).total_seconds()/60 if len(next3)>0 else 240, 240)
    f["mins_to_next_2star"]    = min((next2["datetime"].min() - t).total_seconds()/60 if len(next2)>0 else 240, 240)
    f["mins_since_last_3star"] = min((t - last3["datetime"].max()).total_seconds()/60 if len(last3)>0 else 240, 240)

    last3_dev = last3[last3["deviation"].notna()]
    f["last_deviation_sign"] = float(np.sign(last3_dev.iloc[-1]["deviation"])) if len(last3_dev)>0 else 0.0
    f["last_abs_deviation"]  = round(float(last3_dev.iloc[-1]["abs_dev"]), 4)  if len(last3_dev)>0 else 0.0
    f["upcoming_3star_count"]= int((upcoming["impact"] == 3).sum())

    # ── NEWS MODE — data-proven separate behavior ──────────────
    # Pre-news:  WR=35.7% (-1.4pp) ← avoid or use special model
    # Post-news: WR=34.4% (-2.8pp) ← reversal opportunity
    # Normal:    WR=37.4% (+0.3pp) ← clean trading
    _is_pre_news  = int(f["mins_to_next_3star"]  < 15)   # 15min before 3★ ← data: only close window is bad
    _is_post_news = int(f["mins_since_last_3star"] < 15)  # 15min after 3★ ← data: post-news GOOD after 15min!
    f["is_pre_news"]  = _is_pre_news
    f["is_post_news"] = _is_post_news
    # news_mode: 0=normal, 1=pre-news, 2=post-news
    # Surprise magnitude — how big was the last news shock?

    # ── News Deviation Features (NEW) ──────────────────────
    last3_all = _news_before(news_df, impact=3)
    last2_all = news_df[(news_df["datetime"] <= t) & (news_df["impact"]==2) & news_df["deviation"].notna()]

    # Last 3-star deviation sign (+1/-1/0)
    f["last_3star_dev_sign"] = float(last3_all.iloc[-1]["dev_sign"]) if len(last3_all)>0 else 0.0

    # ── GROUP 5: EIA (2) ──
    _cache    = getattr(news_df, '_news_cache', {})
    _eia_src  = _cache.get("news_eia", news_df[news_df["event"].str.contains("EIA Crude Oil Stocks Change", case=False, na=False)])
    _eia_idx  = int(np.searchsorted(_eia_src['datetime'].values, _t64, side='right'))
    next_eia  = _eia_src.iloc[_eia_idx:]
    last_eia  = _eia_src.iloc[:_eia_idx]
    mins_to_eia = min((next_eia["datetime"].min() - t).total_seconds()/60 if len(next_eia)>0 else 999, 999)
    f["before_eia"]          = int(mins_to_eia <= 120)
    f["mins_since_last_eia"] = min((t - last_eia["datetime"].max()).total_seconds()/60 if len(last_eia)>0 else 240, 240)

    # ── GROUP 6: TRADE (2) ──
    # trade_direction replaces is_buy + is_sell (no contradiction possible)
    t_upper = str(trade_type).upper()
    f["trade_direction"] = 1 if t_upper == "BUY" else -1 if t_upper == "SELL" else 0
    # volume = tick_volume ratio to 20-bar mean (normalized: ~1.0 normal, >1.5 spike)
    # Capped at 5.0 to prevent extreme outlier domination
    _ohlc_last = _ohlc_upto()
    if len(_ohlc_last) > 0:
        _tv = _ohlc_last.iloc[-1].get("tick_volume", None)
        if _tv is not None and str(_tv) not in ("nan","NaN","") and float(_tv) > 0:
            _raw_tv = float(_tv)
            # compute 20-bar rolling mean for normalization
            _vol_ma = _ohlc_last["tick_volume"].dropna().tail(20).mean()
            if _vol_ma and _vol_ma > 0:
                f["volume"] = round(min(_raw_tv / _vol_ma, 5.0), 4)
            else:
                f["volume"] = 1.0
        else:
            f["volume"] = 1.0
    else:
        f["volume"] = 1.0
    # Keep is_buy/is_sell for backward compat but not in FEATURE_COLS
    f["is_buy"]  = int(t_upper == "BUY")
    f["is_sell"] = int(t_upper == "SELL")

    # ── GROUP 7: RANGE BOUND (5) ──
    if h4_df is not None:
        rb = get_range_features(t, h4_df)
    else:
        rb = {"is_post_big_move":0,
              "big_move_direction":0,"big_move_size_pct":0.0,"in_range_phase":0}
    f.update(rb)

    # ── GROUP 8: TREND RATIO (3) ──
    if ratio_df is not None:
        tr = get_trend_ratio_features(t, ratio_df)
    else:
        tr = {"corr_imp_ratio": 1.0}
    f.update(tr)

    # ── GROUP 9: ORDER BLOCK (3) ──
    if h1_ob is not None and h4_ob_df is not None:
        _ohlc_last_row = _ohlc_upto()
        _last_close    = float(_ohlc_last_row.iloc[-1]["close"]) if len(_ohlc_last_row) > 0 else 0
        ob = get_ob_features(t, _last_close, h1_ob, h4_ob_df, trade_type=trade_type)
    else:
        ob = {"h4_resist_dist":999.0,"h4_support_dist":999.0,"h4_in_ob_zone":0,"h4_ob_strength":0.0,
              "h1_resist_dist":999.0,"h1_support_dist":999.0,"h1_in_ob_zone":0,"h1_ob_strength":0.0}
    f.update(ob)

    # ── TREND SIGNALS — all indicator conditions (P=2, SMMA) ──────
    try:
        _ts = _ts_tables_cached(ohlc_df)
        _o  = _ohlc_upto()
        _px = float(_o.iloc[-1]["close"]) if len(_o) > 0 else 0.0
        _h4a = f.get("_h4_adx_rolling")
        if _h4a is None:
            _h4a = f.get("H4_ADX", 0.0)
        f.update(get_trend_signal_features(t, trade_type, _px, _h4a, _ts))
        f.pop("_h4_adx_rolling", None)   # internal only — not a model feature
    except Exception as _ts_err:
        f.update({k: 0.0 for k in TS_FEATURES})
        f["ts_bars_since_flip"] = 999.0

    return f


# ═══════════════════════════════════════════════════════════════
# ROLLING ADX (no-step, no-lookahead)
# Standard H4_ADX in the data updates only when an H4 bar closes
# (frozen for 16 M15 bars) AND carries the bar's FINAL value to rows
# inside the bar (lookahead). Rolling ADX fixes both: at every closed
# M15 bar we take the H4/H1 grid PHASE whose bar closes exactly there,
# so the value updates every 15 min using only closed data.
# Used by: h4_adx_slope, h1_adx_slope, ts_adx_switch_trend.
# ═══════════════════════════════════════════════════════════════

def _wilder_adx(h, l, c, period=14):
    """Wilder ADX on bar arrays. Returns ADX array (np.nan until warm)."""
    n = len(c)
    if n < period * 2 + 1:
        return np.full(n, np.nan)
    up  = h[1:] - h[:-1]
    dn  = l[:-1] - l[1:]
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr  = np.maximum(h[1:] - l[1:],
          np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    def smooth(x):
        out = np.full(len(x), np.nan)
        out[period - 1] = x[:period].sum()
        for i in range(period, len(x)):
            out[i] = out[i - 1] - out[i - 1] / period + x[i]
        return out
    atr, spdm, sndm = smooth(tr), smooth(pdm), smooth(ndm)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100 * spdm / atr
        ndi = 100 * sndm / atr
        dx  = 100 * np.abs(pdi - ndi) / (pdi + ndi)
    adx = np.full(len(dx), np.nan)
    s = 2 * period - 2
    if s < len(dx):
        adx[s] = np.nanmean(dx[period - 1:s + 1])
        for i in range(s + 1, len(dx)):
            adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period
    return np.concatenate([[np.nan], adx])


def build_rolling_adx_table(ohlc_df: pd.DataFrame) -> dict:
    """Rolling H4/H1 ADX(14), one value per closed M15 bar (phase trick)."""
    d = ohlc_df[["datetime", "high", "low", "close"]].reset_index(drop=True)
    H = d["high"].to_numpy(float); L = d["low"].to_numpy(float); C = d["close"].to_numpy(float)
    n = len(d)
    out = {"times": d["datetime"].values.astype("datetime64[ns]")}
    for key, step in (("h4", 16), ("h1", 4)):
        vals = np.full(n, np.nan)
        for ph in range(step):              # phase grids: bars close at i where (i-ph) % step == step-1
            idx_end = np.arange(ph + step - 1, n, step)   # last M15 index of each pseudo-bar
            if len(idx_end) < 30:
                continue
            bh = np.array([H[j - step + 1:j + 1].max() for j in idx_end])
            bl = np.array([L[j - step + 1:j + 1].min() for j in idx_end])
            bc = C[idx_end]
            adx = _wilder_adx(bh, bl, bc, 14)
            vals[idx_end] = adx
        # every closed M15 bar i now has the ADX of the H4/H1 window ENDING at i
        out[key] = vals
    return out


_RADX_CACHE = {"key": None, "tables": None}


def _rolling_adx_cached(ohlc_df: pd.DataFrame) -> dict:
    try:
        key = (len(ohlc_df), str(ohlc_df["datetime"].iloc[-1]))
    except Exception:
        key = (len(ohlc_df), None)
    if _RADX_CACHE["key"] != key:
        _RADX_CACHE["tables"] = build_rolling_adx_table(ohlc_df)
        _RADX_CACHE["key"] = key
    return _RADX_CACHE["tables"]


def get_rolling_adx(t, ohlc_df: pd.DataFrame) -> dict:
    """{h4_now, h4_prev16, h1_now, h1_prev16} at last closed M15 bar before t."""
    rt = _rolling_adx_cached(ohlc_df)
    _t64 = t.to_datetime64() if hasattr(t, "to_datetime64") else np.datetime64(t)
    cutoff = _t64 - np.timedelta64(15, "m")
    i = int(np.searchsorted(rt["times"], cutoff, side="right")) - 1
    def gv(arr, j):
        if j < 0 or j >= len(arr) or np.isnan(arr[j]):
            return None
        return float(arr[j])
    return {
        "h4_now":  gv(rt["h4"], i), "h4_prev": gv(rt["h4"], i - 16),
        "h1_now":  gv(rt["h1"], i), "h1_prev": gv(rt["h1"], i - 16),
    }


# ═══════════════════════════════════════════════════════════════
# TREND SIGNALS (20SMA TrendSignals Hybrid — INDICATOR settings)
# Period=2, SMMA — exact Python port of the MQ5 engine
# ALL indicator conditions exposed as features:
#   trend state (M15/H1/H4), ratchet line distance, flip freshness,
#   higher-TF agreement, EA's ADX-switch confirmation, alignment
# ═══════════════════════════════════════════════════════════════
from trend_signal import compute_trend, resample_ohlc

TS_PERIOD = 2        # Indicator default
TS_METHOD = "SMMA"   # Indicator default (MT5 MODE_SMMA / Wilder)
TS_ADX_SWITCH_LEVEL = 19.0   # Imtiyaz's EA setting: H4 ADX >= 19 → confirm on H4, else H1
                             # (was code-default H1 ADX >= 50, which fired only 4.3% of time)

TS_FEATURES = [
    "ts_trend_m15",        # +1 up / -1 down (M15, last CLOSED bar)
    "ts_trend_h1",         # +1 / -1 (H1)
    "ts_trend_h4",         # +1 / -1 (H4)
    "ts_bars_since_flip",  # M15 bars since last flip (fresh vs old trend)
    "ts_flip_recent",      # 1 = flip within last 3 closed M15 bars
    "ts_line_dist_pct",    # signed distance of price from active ratchet line (%)
    "ts_htf_agreement",    # trend_m15+trend_h1+trend_h4 (-3..+3)
    "ts_adx_switch_trend", # EA rule: H4 ADX>=19 → H4 trend, else H1 trend
    "ts_aligned",          # +1 trade dir matches M15 trend, -1 against
    "ts_aligned_htf",      # +1 trade dir matches ADX-switch trend, -1 against
]

_TS_CACHE = {"key": None, "tables": None}


def build_trend_signal_tables(ohlc_df: pd.DataFrame) -> dict:
    """Precompute trend state/lines/flips for M15 + resampled H1/H4.
    Stored as numpy arrays for fast searchsorted lookup (no lookahead)."""
    base = (ohlc_df[["datetime", "open", "high", "low", "close"]]
            .rename(columns={"datetime": "time"})
            .sort_values("time").reset_index(drop=True))
    tfs = {
        "m15": (compute_trend(base, TS_PERIOD, TS_METHOD), 15),
        "h1":  (compute_trend(resample_ohlc(base, "1h"), TS_PERIOD, TS_METHOD), 60),
        "h4":  (compute_trend(resample_ohlc(base, "4h"), TS_PERIOD, TS_METHOD), 240),
    }
    out = {}
    for k, (df, tf_min) in tfs.items():
        out[k] = {
            "times":     df["time"].values.astype("datetime64[ns]"),
            "trend":     df["trend"].to_numpy(),
            "flip":      df["flip"].to_numpy(),
            "bsf":       df["bars_since_flip"].to_numpy(),
            "buy_line":  df["buy_line"].to_numpy(),
            "sell_line": df["sell_line"].to_numpy(),
            "tf_min":    tf_min,
        }
    return out


def _ts_tables_cached(ohlc_df: pd.DataFrame) -> dict:
    """Auto-build with cache — rebuilds only when OHLC content changes
    (daily data update). Keeps every existing call site working untouched."""
    try:
        key = (len(ohlc_df), str(ohlc_df["datetime"].iloc[-1]))
    except Exception:
        key = (len(ohlc_df), None)
    if _TS_CACHE["key"] != key:
        _TS_CACHE["tables"] = build_trend_signal_tables(ohlc_df)
        _TS_CACHE["key"] = key
    return _TS_CACHE["tables"]


def get_trend_signal_features(t, trade_type, price_now, h4_adx, ts: dict) -> dict:
    """All indicator conditions at decision time t — uses last fully CLOSED
    bar per timeframe (bar_open + tf <= t) so training == live, no lookahead."""
    f = {k: 0.0 for k in TS_FEATURES}
    f["ts_bars_since_flip"] = 999.0
    if not ts:
        return f
    _t64 = t.to_datetime64() if hasattr(t, "to_datetime64") else np.datetime64(t)
    vals = {}
    for k in ("m15", "h1", "h4"):
        tb = ts[k]
        cutoff = _t64 - np.timedelta64(tb["tf_min"], "m")
        idx = int(np.searchsorted(tb["times"], cutoff, side="right")) - 1
        vals[k] = idx if idx >= 0 else None

    if vals["m15"] is not None:
        tb, i = ts["m15"], vals["m15"]
        tr = float(tb["trend"][i])
        f["ts_trend_m15"] = tr
        bsf = tb["bsf"][i]
        f["ts_bars_since_flip"] = float(bsf) if not np.isnan(bsf) else 999.0
        f["ts_flip_recent"] = float(f["ts_bars_since_flip"] <= 3)
        line = tb["buy_line"][i] if tr > 0 else tb["sell_line"][i]
        if price_now and not np.isnan(line):
            f["ts_line_dist_pct"] = round((price_now - line) / price_now * 100.0, 6)
    if vals["h1"] is not None:
        f["ts_trend_h1"] = float(ts["h1"]["trend"][vals["h1"]])
    if vals["h4"] is not None:
        f["ts_trend_h4"] = float(ts["h4"]["trend"][vals["h4"]])

    f["ts_htf_agreement"] = f["ts_trend_m15"] + f["ts_trend_h1"] + f["ts_trend_h4"]
    # EA confirmation rule: strong H1 trend → confirm on H4, else on H1
    # Imtiyaz's EA rule: H4 trending (ADX>=19) → confirm on H4; flat → drop to H1
    f["ts_adx_switch_trend"] = f["ts_trend_h4"] if (h4_adx or 0) >= TS_ADX_SWITCH_LEVEL else f["ts_trend_h1"]

    d = 1.0 if str(trade_type).upper().startswith("B") else -1.0
    f["ts_aligned"]     = d * f["ts_trend_m15"]
    f["ts_aligned_htf"] = d * f["ts_adx_switch_trend"]
    return f


# ─────────────────────────────────────────────
# FEATURE COLUMNS (46)
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# FINAL 20 CLEAN FEATURES (Top 20 by importance)
# 43 → 20 features → TEST win 66.1% → 74.4%!
# Removed: low importance features (rank 21-43)
# ─────────────────────────────────────────────

FEATURE_COLS = [
    # ── FACTOR 1: Institutional Order Flow Timing (7) ──
    "15_min_slot",           # direct slot timing
    "slot_win_rate",         # historical WR per slot
    "slot_cos",              # cyclical slot encoding
    "day_of_week",           # day pattern
    "session_score",         # data-proven session quality (-2=worst to +2=best NY)
    "is_ny_session",         # 1=NY open 15-18 UTC (WR=40-52%) ← KEY
    "is_dead_hour",          # 1=low WR hours: 09 UTC=57.1%, 20 UTC=58.8% (data-proven)
    "trade_direction",       # BUY/SELL alignment

    # ── FACTOR 2: Bigger Wins Smaller Losses (9) ──
    "h4_resist_dist",        # H4 resistance OB %dist (profit-dir) ← NEW S/R
    "h4_support_dist",       # H4 support OB %dist (loss-dir) ← NEW S/R
    "h4_in_ob_zone",         # price inside H4 OB zone 0/1 ← NEW
    "h4_ob_strength",        # H4 nearest resist OB strength ← NEW
    "h1_resist_dist",        # H1 resistance OB %dist ← NEW S/R
    "h1_support_dist",       # H1 support OB %dist ← NEW S/R
    "h1_in_ob_zone",         # price inside H1 OB zone 0/1 ← NEW
    "h1_ob_strength",        # H1 nearest resist OB strength ← NEW
    "price_pos",             # price position in range
    "body_pct",              # candle body conviction
    "in_range_phase",        # range detection
    "corr_imp_ratio",        # correction/impulse ratio ← NEW
    "is_post_big_move",      # post big move flag ← NEW
    "big_move_direction",    # big move direction ← NEW

    # ── FACTOR 3: Stronger Trending Moves (13) ──
    "M15_ADX",               # M15 trend strength
    "M30_ADX",               # M30 trend strength ← NEW
    "H1_ADX",                # H1 trend strength ← NEW
    "H4_ADX",                # H4 trend strength ← NEW
    "M15_DI_diff",           # M15 directional diff
    "M30_DI_diff",           # M30 directional diff
    "H1_DI_diff",            # H1 directional diff ← NEW
    "H4_DI_diff",            # H4 directional diff
    "adx_trend_count",       # consecutive trend bars
    "h4_adx_slope",          # H4 ADX change over 4hr — trend strengthening/dying
    "h1_adx_slope",          # H1 ADX change over 4hr
    # h4_adx_rising removed — redundant with slope, WF test: all-3 combo hurt OOS
    "h4_trending_h1_aligned",# H4 trend + H1 confirms ← DATA-PROVEN +3.7pp
    "h4_ranging_h1_neutral", # H4 range + H1 not extended ← +1.8pp
    "h4_ranging_h1_extended",# H4 range + H1 extended ← AVOID -8.2pp
    "h4_h1_regime_score",    # combined regime score (-1 to +2)

    # ── FACTOR 4: Real Price Momentum (7) ──
    "range_pct",             # candle range %
    "atr20_pct",             # ATR20 sustained volatility
    "atr14_pct",             # ATR14 short-term momentum
    "volume",                # raw tick volume
    "vol_spike",             # volume spike flag ← NEW
    # ── PRICE MOMENTUM (data-proven) ─────────────────────────
    # Backtest: BUY when 4hr dropped → WR=31%, BUY when 4hr rose → WR=52%
    "move_1hr",              # Gold price change last 1hr ($) ← data #1 edge +27.7pp
    "move_2hr",              # Gold price change last 2hr ($) ← NEW data #2 edge +15.7pp
    "move_4hr",              # Gold price change last 4hr ($) ← KEY feature
    "move_8hr",              # Gold price change last 8hr ($)
    "momentum_aligned_1hr",  # +1 signal matches 1hr momentum, -1 against
    "momentum_aligned_2hr",  # +1 signal matches 2hr momentum ← NEW
    "momentum_aligned_4hr",  # +1 signal matches 4hr momentum, -1 against ← KEY
    # ── EMA200 (data-proven: +3.8pp WR, +$8,709 P&L) ────────────
    "price_vs_ema200",       # distance from EMA200 in $ (signed)
    "above_ema200",          # 1=above EMA, 0=below
    "ema200_dist_abs",       # absolute distance (far=good, near=bad)
    "near_ema200",           # 1=within ±$10 danger zone (WR=31%)

    # ── NEWS EVENTS: 2★ & 3★ Calendar (8) ──────────────────
    "mins_to_next_3star",    # mins to next 3★ event ← NEW
    "mins_since_last_3star", # mins since last 3★ event ← NEW
    "upcoming_3star_count",  # upcoming 3★ count in 2hrs ← NEW
    "last_3star_dev_sign",   # last 3★ beat/miss sign ← NEW
    "before_eia",            # EIA crude oil event flag ← NEW
    "is_post_news",          # 1=within 15min after 3★ news ← data: post-news WR=41-44% GREAT!
    # is_pre_news removed — mins_to_next_3star < 15 already covers it

    # ── TREND SIGNALS: 20SMA Hybrid indicator, ALL conditions (10) ──
    "ts_trend_m15",          # M15 trend state +1/-1
    "ts_trend_h1",           # H1 trend state
    "ts_trend_h4",           # H4 trend state
    "ts_bars_since_flip",    # M15 bars since flip (freshness)
    "ts_flip_recent",        # flip within last 3 bars
    "ts_line_dist_pct",      # distance from ratchet line %
    "ts_htf_agreement",      # M15+H1+H4 agreement (-3..+3)
    "ts_adx_switch_trend",   # EA rule: H4 ADX>=19→H4 else H1
    "ts_aligned",            # trade dir vs M15 trend
    "ts_aligned_htf",        # trade dir vs ADX-switch trend
]


def build_feature_matrix(trades_df, ohlc_df, adx_df, news_df, slot_table, h4_df=None, ratio_df=None, h1_ob=None, h4_ob_df=None):
    rows  = []
    total = len(trades_df)
    for i, (_, trade) in enumerate(trades_df.iterrows()):
        if i % 200 == 0:
            print(f"    Processing {i}/{total}...", end="\r")
        f = compute_features(
            t          = trade["datetime"],
            trade_type = trade["Type"],
            volume     = trade["Volume"],
            ohlc_df    = ohlc_df,
            adx_df     = adx_df,
            news_df    = news_df,
            slot_table = slot_table,
            h4_df      = h4_df,
            ratio_df   = ratio_df,
            h1_ob      = h1_ob,
            h4_ob_df   = h4_ob_df,
        )
        rows.append(f)
    print(f"    Processing {total}/{total}... done!    ")

    df_feat = pd.DataFrame(rows)
    X = df_feat[FEATURE_COLS].values.astype(np.float32)
    y = trades_df["win_bin"].values.astype(int)
    return X, y, FEATURE_COLS


# ═══════════════════════════════════════════════════════════════
# HYBRID FEATURE SETS — Layer 1 (Core) + Layer 2 (State-based)
# ═══════════════════════════════════════════════════════════════

# ── LAYER 1: Core — always ON in every market state (17) ──────
CORE_FEATURES = [
    "slot_win_rate",           # slot historical win rate
    "day_of_week",             # weekday effect
    "session_score",           # session quality score ← data-proven
    "is_ny_session",           # NY session flag
    "is_dead_hour",            # dead hour flag
    "mins_to_next_3star",      # upcoming high-impact news
    "mins_since_last_3star",   # last high-impact news
    "trade_direction",         # BUY=1 / SELL=0
    "price_pos",               # price in 20-candle range (0-1)
    "body_pct",                # candle body %
    "range_pct",               # candle range %
    "atr20_pct",               # sustained volatility
    "atr14_pct",               # short-term momentum
    "M15_ADX",                 # M15 trend strength
    "H1_ADX",                  # H1 trend strength
    "M30_DI_diff",             # M30 direction
    "H1_DI_diff",              # H1 direction
    "hmm_state",               # market state (0/1/2)
    "h4_h1_regime_score",      # H4/H1 regime alignment score (data-proven)
    "move_4hr",                # 4hr price momentum — KEY: BUY↓=31%WR, BUY↑=52%WR
    "move_2hr",                # 2hr momentum ← NEW data-proven +15.7pp edge
    "momentum_aligned_4hr",    # signal matches 4hr momentum (+1) or against (-1)
    "momentum_aligned_2hr",    # signal matches 2hr momentum ← NEW
    "price_vs_ema200",         # EMA200 distance — key context feature
    "near_ema200",             # danger zone flag (WR=31% when near)
    # ── TREND SIGNALS (indicator P=2 SMMA, all conditions) ──
    "ts_trend_m15",            # M15 trend state
    "ts_trend_h1",             # H1 trend state
    "ts_trend_h4",             # H4 trend state
    "ts_bars_since_flip",      # flip freshness
    "ts_flip_recent",          # fresh flip flag
    "ts_line_dist_pct",        # ratchet line distance %
    "ts_htf_agreement",        # multi-TF agreement
    "ts_adx_switch_trend",     # EA ADX-switch confirmation
    "ts_aligned",              # dir vs M15 trend
    "ts_aligned_htf",          # dir vs ADX-switch trend
    "h4_adx_slope",            # ADX direction — trend strengthening/dying
    "h1_adx_slope",
]

# ── LAYER 2: State-specific — dynamic ON/OFF ──────────────────

# RANGING (hmm=0): price structure + OB, remove ADX (useless in range)
RANGING_FEATURES = (
    [f for f in CORE_FEATURES if f not in ("M15_ADX", "H1_ADX")]
    + [
        "in_range_phase",      # confirmed range phase
        "h4_resist_dist",      # H4 resistance OB %dist ← NEW S/R
        "h4_support_dist",     # H4 support OB %dist ← NEW S/R
        "h4_in_ob_zone",       # price inside H4 OB zone ← NEW
        "h4_ob_strength",      # H4 resist OB strength ← NEW
        "h1_resist_dist",      # H1 resistance OB %dist ← NEW S/R
        "h1_support_dist",     # H1 support OB %dist ← NEW S/R
        "h1_in_ob_zone",       # price inside H1 OB zone ← NEW
        "h1_ob_strength",      # H1 resist OB strength ← NEW
        "corr_imp_ratio",      # corrective vs impulsive ratio
        "h4_ranging_h1_neutral",   # H4 range + H1 not extended (good entry)
        "h4_ranging_h1_extended",  # H4 range + H1 extended (avoid)
        "move_1hr",                # 1hr momentum — important in ranging
        "momentum_aligned_1hr",    # 1hr momentum alignment
        "ema200_dist_abs",         # ✅ data-proven: +5pp AUC — EMA bounce zone
        # note: near_ema200 + price_vs_ema200 already in CORE_FEATURES — not repeated
    ]
)

# TRENDING (hmm=1): full ADX suite, all DI diffs, trend context
TRENDING_FEATURES = (
    CORE_FEATURES
    + [
        "M30_ADX",             # M30 trend strength
        "H4_ADX",              # H4 trend strength
        "M15_DI_diff",         # M15 direction
        "H4_DI_diff",          # H4 direction
        "adx_trend_count",     # timeframes with ADX > 20
        "h4_trending_h1_aligned",  # H4 trend + H1 confirms ← +3.7pp WR
        "move_8hr",                # 8hr momentum — trend persistence
        "above_ema200",            # trend direction vs EMA
        "ema200_dist_abs",         # keep — data: removing = -5.3pp AUC
        # note: move_4hr + momentum_aligned_4hr already in CORE_FEATURES — not repeated
    ]
)

# VOLATILE (hmm=2): news + volume, remove lagging trend features
# Removed: h4_ranging_h1_extended (ranging concept, not volatile)
#          is_pre_news (mins_to_next_3star already covers it)
# Added  : ema200_dist_abs (data-proven: +4.2pp AUC)
VOLATILE_FEATURES = (
    [f for f in CORE_FEATURES if f not in ("M15_ADX", "H1_ADX", "M30_DI_diff", "H1_DI_diff")]
    + [
        "last_3star_dev_sign",   # news surprise direction ← 0.856 importance!
        "before_eia",            # before EIA release
        "vol_spike",             # volume spike flag
        "is_post_news",          # post-news reversal setup
        "ema200_dist_abs",       # ✅ data-proven: +4.2pp AUC in volatile
    ]
)

STATE_FEATURE_MAP = {
    "ranging":  RANGING_FEATURES,
    "trending": TRENDING_FEATURES,
    "volatile": VOLATILE_FEATURES,
}

print(f"  Hybrid feature sets: Ranging={len(RANGING_FEATURES)} | Trending={len(TRENDING_FEATURES)} | Volatile={len(VOLATILE_FEATURES)}")
