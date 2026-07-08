"""
trend_signal.py — Python port of 20SMA TrendSignals Hybrid / Trend Signal Pro EA engine
========================================================================================
Logic (exact match to MQ5 ComputeTrendSignals / indicator OnCalculate):

    trend = +1  when close[i] > MA(High)[i-1]
    trend = -1  when close[i] < MA(Low)[i-1]
    else        trend carries over (seed: close>=open ? +1 : -1)

    BUY line  (trend>0)  = MA(Low)[i-1]  - buy_offset   (ratcheted UP only)
    SELL line (trend<0)  = MA(High)[i-1] + sell_offset  (ratcheted DOWN only)

    Flip bar: prevTrend<0 -> +1 = BUY signal ; prevTrend>0 -> -1 = SELL signal

Supports SMA and SMMA (Wilder) methods, any period.
EA default:        period=1, SMA
Indicator default: period=2, SMMA
"""

import numpy as np
import pandas as pd


def _ma(series: np.ndarray, period: int, method: str) -> np.ndarray:
    """MA of an array. method: 'SMA' or 'SMMA' (Wilder)."""
    n = len(series)
    out = np.full(n, np.nan)
    if period <= 1:
        return series.astype(float).copy()
    if method.upper() == "SMA":
        s = pd.Series(series)
        return s.rolling(period, min_periods=period).mean().to_numpy()
    # SMMA (MT5 MODE_SMMA): first value = SMA(period), then (prev*(p-1)+x)/p
    if n < period:
        return out
    out[period - 1] = series[:period].mean()
    for i in range(period, n):
        out[i] = (out[i - 1] * (period - 1) + series[i]) / period
    return out


def compute_trend(df: pd.DataFrame, period: int = 1, method: str = "SMA",
                  buy_offset: float = 0.0, sell_offset: float = 0.0,
                  ratchet: bool = True) -> pd.DataFrame:
    """
    df: columns time/open/high/low/close (bar OPEN time, ascending).
    Returns df with: trend (+1/-1), buy_line, sell_line, flip (+1 buy / -1 sell / 0).
    Values are as of bar CLOSE — usable only after the bar has closed (no lookahead
    if you reference the previous closed bar at decision time).
    """
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    n = len(df)

    maH = _ma(h, period, method)
    maL = _ma(l, period, method)

    trend = np.zeros(n)
    buy_line = np.full(n, np.nan)
    sell_line = np.full(n, np.nan)
    flip = np.zeros(n, dtype=int)

    for i in range(1, n):
        prev = trend[i - 1]
        t = prev
        if not np.isnan(maH[i - 1]) and c[i] > maH[i - 1]:
            t = 1
        elif not np.isnan(maL[i - 1]) and c[i] < maL[i - 1]:
            t = -1
        if t == 0:
            t = 1 if c[i] >= o[i] else -1
        trend[i] = t

        if t > 0:
            lvl = maL[i - 1] - buy_offset
            if ratchet and prev > 0 and not np.isnan(buy_line[i - 1]) and lvl < buy_line[i - 1]:
                lvl = buy_line[i - 1]
            buy_line[i] = lvl
            if prev < 0:
                flip[i] = 1
        else:
            lvl = maH[i - 1] + sell_offset
            if ratchet and prev < 0 and not np.isnan(sell_line[i - 1]) and lvl > sell_line[i - 1]:
                lvl = sell_line[i - 1]
            sell_line[i] = lvl
            if prev > 0:
                flip[i] = -1

    out = df[["time"]].copy()
    out["trend"] = trend.astype(int)
    out["buy_line"] = buy_line
    out["sell_line"] = sell_line
    out["flip"] = flip
    # bars since last flip
    flip_idx = np.where(flip != 0)[0]
    bars_since = np.full(n, np.nan)
    last = -1
    fi = 0
    for i in range(n):
        if fi < len(flip_idx) and flip_idx[fi] == i:
            last = i
            fi += 1
        if last >= 0:
            bars_since[i] = i - last
    out["bars_since_flip"] = bars_since
    # distance of close to active line, in % of close
    line = np.where(trend > 0, buy_line, sell_line)
    out["line_dist_pct"] = (c - line) / c * 100.0
    # SMMA band width = MA(High) - MA(Low) — volatility proxy (lag-free at P=2).
    # Used by RATCHET band-buffer mode (buffer = band_width * mult).
    band_w = maH - maL
    out["band_width"] = band_w
    out["band_width_pct"] = band_w / c * 100.0
    return out


def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample M15 OHLC to higher TF. rule: '1h', '4h'. time = bar OPEN time."""
    d = df.set_index(pd.to_datetime(df["time"]))
    r = d.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()
    r = r.reset_index().rename(columns={"index": "time"})
    return r


def trend_at(trend_df: pd.DataFrame, when: pd.Timestamp, tf_minutes: int):
    """Trend/lines from the last FULLY CLOSED bar at decision time `when`.
    Bar with open time T is closed when T + tf <= when."""
    cutoff = when - pd.Timedelta(minutes=tf_minutes)
    idx = trend_df["time"].searchsorted(cutoff, side="right") - 1
    if idx < 0:
        return None
    return trend_df.iloc[idx]
