"""
Isolated smart-exit diagnostic backtest.

This does not change live trading code. It reuses the baseline entries and
M15 candles to compare the current baseline exits with a rule-based
smart-exit v1 idea.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASELINE_DIR = ROOT / "backtest" / "results" / "fullbt_hmm_10k_lot001"
TRADES_CSV = BASELINE_DIR / "backtest_trades_st-htf.csv"
BASELINE_REPORT = BASELINE_DIR / "backtest_report.txt"
OHLC_CSV = ROOT / "data" / "merged" / "ohlc_merged.csv"
OUT_DIR = ROOT / "backtest" / "results" / "smart_exit_v1"

INITIAL_CAPITAL = 10_000.0
COMPOUND_RISK_PCT = 0.03
AVAILABLE_POINTS_FALLBACK = 111_157.0
HORIZON_BARS = 96
STRUCT_BARS = 6
TIME_NO_PROGRESS_BARS = 24
TIME_MAX_BARS = 72
PARTIAL_R = 1.0
RANGING_FAST_TAKE_R = 1.50
TREND_FAST_TAKE_R = 2.25
GIVEBACK_AFTER_R = 1.50
GIVEBACK_KEEP = 0.62


@dataclass(frozen=True)
class TradeInput:
    row_id: int
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: str
    side: int
    entry: float
    sl_dist: float
    sl_price: float
    regime: str


def read_baseline_available_points() -> float:
    if not BASELINE_REPORT.exists():
        return AVAILABLE_POINTS_FALLBACK
    text = BASELINE_REPORT.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"available\s+([\d,]+)\s+pts", text, flags=re.I)
    if not m:
        return AVAILABLE_POINTS_FALLBACK
    return float(m.group(1).replace(",", ""))


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    trades = pd.read_csv(TRADES_CSV, parse_dates=["entry_time", "exit_time"])
    need = [
        "entry_time",
        "exit_time",
        "direction",
        "entry_price",
        "exit_price",
        "sl_dist",
        "sl_price",
        "hmm_state",
        "exit_reason",
        "r_achieved",
        "peak_r",
        "pnl_usd",
    ]
    missing = [c for c in need if c not in trades.columns]
    if missing:
        raise RuntimeError(f"Missing baseline trade columns: {missing}")

    for c in ["entry_price", "exit_price", "sl_dist", "sl_price", "r_achieved", "peak_r", "pnl_usd"]:
        trades[c] = pd.to_numeric(trades[c], errors="coerce")
    trades = trades.dropna(subset=["entry_time", "direction", "entry_price", "sl_dist", "sl_price"]).copy()
    trades = trades.sort_values("entry_time").reset_index(drop=True)

    ohlc = pd.read_csv(OHLC_CSV, parse_dates=["time"])
    for c in ["open", "high", "low", "close", "tick_volume"]:
        ohlc[c] = pd.to_numeric(ohlc[c], errors="coerce")
    ohlc = ohlc.dropna(subset=["time", "open", "high", "low", "close"]).sort_values("time").reset_index(drop=True)
    ohlc = add_indicators(ohlc)
    return trades, ohlc


def add_indicators(ohlc: pd.DataFrame) -> pd.DataFrame:
    o = ohlc.copy()
    delta = o["close"].diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    o["rsi"] = 100 - (100 / (1 + up / (dn + 1e-9)))
    o["body"] = (o["close"] - o["open"]).abs()
    o["body_ma"] = o["body"].rolling(20, min_periods=5).mean()
    o["vol_ma"] = o["tick_volume"].rolling(20, min_periods=5).mean()
    o["sup_m15"] = o["low"].rolling(STRUCT_BARS, min_periods=2).min().shift(1)
    o["res_m15"] = o["high"].rolling(STRUCT_BARS, min_periods=2).max().shift(1)

    h1 = (
        o.set_index("time")
        .resample("1h")
        .agg({"high": "max", "low": "min", "close": "last"})
        .dropna()
    )
    h1["sup_h1"] = h1["low"].rolling(STRUCT_BARS, min_periods=2).min().shift(1)
    h1["res_h1"] = h1["high"].rolling(STRUCT_BARS, min_periods=2).max().shift(1)
    h1 = h1.reset_index()[["time", "sup_h1", "res_h1"]].dropna()
    merged = pd.merge_asof(o[["time"]], h1, on="time", direction="backward")
    o["sup_h1"] = merged["sup_h1"].values
    o["res_h1"] = merged["res_h1"].values
    return o


def r_of_price(price: float, trade: TradeInput) -> float:
    return trade.side * (price - trade.entry) / trade.sl_dist


def price_at_r(r_value: float, trade: TradeInput) -> float:
    return trade.entry + trade.side * r_value * trade.sl_dist


def favorable_r(row: pd.Series, trade: TradeInput) -> float:
    return r_of_price(row["high"] if trade.side == 1 else row["low"], trade)


def adverse_r(row: pd.Series, trade: TradeInput) -> float:
    return r_of_price(row["low"] if trade.side == 1 else row["high"], trade)


def hit_price(row: pd.Series, trade: TradeInput, price: float) -> bool:
    if trade.side == 1:
        return bool(row["low"] <= price <= row["high"])
    return bool(row["low"] <= price <= row["high"])


def is_weak_momentum(row: pd.Series, trade: TradeInput) -> bool:
    rsi = row.get("rsi", np.nan)
    body = row.get("body", np.nan)
    body_ma = row.get("body_ma", np.nan)
    vol = row.get("tick_volume", np.nan)
    vol_ma = row.get("vol_ma", np.nan)
    weak_rsi = (rsi < 48) if trade.side == 1 else (rsi > 52)
    opposite_body = (row["close"] < row["open"]) if trade.side == 1 else (row["close"] > row["open"])
    large_body = bool(pd.notna(body_ma) and body > 1.15 * body_ma)
    low_volume = bool(pd.notna(vol_ma) and vol < 0.70 * vol_ma)
    return bool(weak_rsi or (opposite_body and large_body) or low_volume)


def structure_break(row: pd.Series, trade: TradeInput) -> bool:
    sup_h1 = row.get("sup_h1", np.nan)
    res_h1 = row.get("res_h1", np.nan)
    sup_m15 = row.get("sup_m15", np.nan)
    res_m15 = row.get("res_m15", np.nan)
    if trade.side == 1:
        return bool(
            (pd.notna(sup_h1) and row["close"] < sup_h1)
            or (pd.notna(sup_m15) and row["close"] < sup_m15 and is_weak_momentum(row, trade))
        )
    return bool(
        (pd.notna(res_h1) and row["close"] > res_h1)
        or (pd.notna(res_m15) and row["close"] > res_m15 and is_weak_momentum(row, trade))
    )


def adjusted_result(
    trade: TradeInput,
    exit_time: pd.Timestamp,
    exit_price: float,
    exit_r: float,
    peak_r: float,
    exit_reason: str,
    partial_taken: bool,
) -> dict[str, object]:
    if partial_taken:
        total_r = 0.5 * PARTIAL_R + 0.5 * exit_r
        weighted_move = total_r * trade.sl_dist
    else:
        total_r = exit_r
        weighted_move = trade.side * (exit_price - trade.entry)
    return {
        "row_id": trade.row_id,
        "entry_time": trade.entry_time,
        "exit_time": exit_time,
        "direction": trade.direction,
        "hmm_state": trade.regime,
        "entry_price": round(trade.entry, 2),
        "exit_price": round(exit_price, 2),
        "sl_dist": round(trade.sl_dist, 2),
        "exit_reason": exit_reason,
        "partial_taken": int(partial_taken),
        "r_achieved": round(float(total_r), 4),
        "peak_r": round(float(max(peak_r, total_r)), 4),
        "price_move": round(float(weighted_move), 2),
        "pnl_usd": round(float(weighted_move), 2),
        "bars_held": int(max(0, (exit_time - trade.entry_time).total_seconds() // 900)),
    }


def simulate_smart_exit(trade: TradeInput, window: pd.DataFrame) -> dict[str, object]:
    if len(window) < 2:
        return adjusted_result(trade, trade.entry_time, trade.entry, 0.0, 0.0, "NO_DATA", False)

    sl_price = trade.sl_price
    partial_taken = False
    peak_r = 0.0

    for k in range(1, len(window)):
        bar = window.iloc[k]
        bar_peak = favorable_r(bar, trade)
        peak_r = max(peak_r, bar_peak)

        if hit_price(bar, trade, sl_price):
            exit_r = r_of_price(sl_price, trade)
            return adjusted_result(trade, bar["time"], sl_price, exit_r, peak_r, "SL_OR_BE", partial_taken)

        if trade.regime == "Ranging" and bar_peak >= RANGING_FAST_TAKE_R:
            target = price_at_r(RANGING_FAST_TAKE_R, trade)
            return adjusted_result(trade, bar["time"], target, RANGING_FAST_TAKE_R, peak_r, "RANGE_TAKE_1_5R", partial_taken)

        if trade.regime == "Trending" and bar_peak >= TREND_FAST_TAKE_R:
            target = price_at_r(TREND_FAST_TAKE_R, trade)
            return adjusted_result(trade, bar["time"], target, TREND_FAST_TAKE_R, peak_r, "TREND_TAKE_2_25R", partial_taken)

        if not partial_taken and bar_peak >= PARTIAL_R:
            partial_taken = True
            sl_price = trade.entry

        close_r = r_of_price(float(bar["close"]), trade)
        giveback_line = max(0.50, peak_r * GIVEBACK_KEEP)

        if peak_r >= GIVEBACK_AFTER_R and close_r <= giveback_line:
            return adjusted_result(trade, bar["time"], float(bar["close"]), close_r, peak_r, "GIVEBACK_EXIT", partial_taken)

        if structure_break(bar, trade) and close_r > 0.0:
            return adjusted_result(trade, bar["time"], float(bar["close"]), close_r, peak_r, "STRUCTURE_EXIT", partial_taken)

        if k >= TIME_NO_PROGRESS_BARS and peak_r < 0.50:
            return adjusted_result(trade, bar["time"], float(bar["close"]), close_r, peak_r, "TIME_NO_PROGRESS", partial_taken)

        if k >= TIME_MAX_BARS and close_r > 0.0:
            return adjusted_result(trade, bar["time"], float(bar["close"]), close_r, peak_r, "TIME_MAX_PROFIT", partial_taken)

    last = window.iloc[-1]
    close_r = r_of_price(float(last["close"]), trade)
    return adjusted_result(trade, last["time"], float(last["close"]), close_r, peak_r, "HORIZON_CLOSE", partial_taken)


def build_windows(trades: pd.DataFrame, ohlc: pd.DataFrame) -> pd.DataFrame:
    times = ohlc["time"].to_numpy()
    out = []
    for row_id, row in trades.iterrows():
        side = 1 if str(row["direction"]).upper() == "BUY" else -1
        trade = TradeInput(
            row_id=row_id,
            entry_time=row["entry_time"],
            exit_time=row["exit_time"],
            direction=str(row["direction"]).upper(),
            side=side,
            entry=float(row["entry_price"]),
            sl_dist=float(row["sl_dist"]),
            sl_price=float(row["sl_price"]),
            regime=str(row.get("hmm_state", "")),
        )
        start = int(np.searchsorted(times, np.datetime64(trade.entry_time), side="left"))
        window = ohlc.iloc[start : start + HORIZON_BARS + 1].reset_index(drop=True)
        out.append(simulate_smart_exit(trade, window))
    return pd.DataFrame(out)


def profit_factor(r: pd.Series) -> float:
    wins = r[r > 0].sum()
    losses = -r[r < 0].sum()
    if losses <= 0:
        return math.inf
    return float(wins / losses)


def equity_curve_compound(r_values: pd.Series) -> pd.Series:
    eq = INITIAL_CAPITAL
    vals = []
    for r in r_values.fillna(0.0):
        eq += eq * COMPOUND_RISK_PCT * float(r)
        vals.append(eq)
    return pd.Series(vals, index=r_values.index)


def max_drawdown_pct(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min() * 100) if len(dd) else 0.0


def summarize(name: str, df: pd.DataFrame, available_points: float) -> dict[str, object]:
    r = pd.to_numeric(df["r_achieved"], errors="coerce").fillna(0.0)
    pnl = pd.to_numeric(df["pnl_usd"], errors="coerce").fillna(0.0)
    eq = equity_curve_compound(r)
    captured = float(pd.to_numeric(df["price_move"], errors="coerce").fillna(0.0).sum())
    return {
        "name": name,
        "trades": int(len(df)),
        "wins": int((r > 0).sum()),
        "losses": int((r <= 0).sum()),
        "win_rate_pct": float((r > 0).mean() * 100) if len(r) else 0.0,
        "profit_factor": profit_factor(r),
        "avg_r": float(r.mean()) if len(r) else 0.0,
        "total_r": float(r.sum()),
        "fixed_lot_pnl_usd": float(pnl.sum()),
        "avg_pnl_usd": float(pnl.mean()) if len(pnl) else 0.0,
        "compound_final_equity": float(eq.iloc[-1]) if len(eq) else INITIAL_CAPITAL,
        "compound_net_usd": float(eq.iloc[-1] - INITIAL_CAPITAL) if len(eq) else 0.0,
        "compound_return_pct": float((eq.iloc[-1] / INITIAL_CAPITAL - 1) * 100) if len(eq) else 0.0,
        "compound_max_dd_pct": max_drawdown_pct(eq),
        "captured_points": captured,
        "available_points": available_points,
        "capture_pct": float(captured / available_points * 100) if available_points else 0.0,
    }


def make_baseline_frame(trades: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "row_id": trades.index,
            "entry_time": trades["entry_time"],
            "exit_time": trades["exit_time"],
            "direction": trades["direction"],
            "hmm_state": trades["hmm_state"],
            "entry_price": trades["entry_price"],
            "exit_price": trades["exit_price"],
            "sl_dist": trades["sl_dist"],
            "exit_reason": trades["exit_reason"],
            "partial_taken": 0,
            "r_achieved": trades["r_achieved"],
            "peak_r": trades["peak_r"],
            "price_move": trades["price_move"] if "price_move" in trades.columns else trades["pnl_usd"],
            "pnl_usd": trades["pnl_usd"],
            "bars_held": ((trades["exit_time"] - trades["entry_time"]).dt.total_seconds() // 900).astype(int),
        }
    )


def chunk_table(baseline: pd.DataFrame, smart: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for start in range(0, len(baseline), 100):
        end = min(start + 100, len(baseline))
        b = baseline.iloc[start:end]
        s = smart.iloc[start:end]
        b_eq = equity_curve_compound(pd.to_numeric(b["r_achieved"], errors="coerce").fillna(0.0))
        s_eq = equity_curve_compound(pd.to_numeric(s["r_achieved"], errors="coerce").fillna(0.0))
        rows.append(
            {
                "trades": f"{start + 1}-{end}",
                "baseline_R": round(float(b["r_achieved"].sum()), 2),
                "smart_R": round(float(s["r_achieved"].sum()), 2),
                "delta_R": round(float(s["r_achieved"].sum() - b["r_achieved"].sum()), 2),
                "baseline_fixed_$": round(float(b["pnl_usd"].sum()), 2),
                "smart_fixed_$": round(float(s["pnl_usd"].sum()), 2),
                "delta_fixed_$": round(float(s["pnl_usd"].sum() - b["pnl_usd"].sum()), 2),
                "baseline_compound_$": round(float(b_eq.iloc[-1] - INITIAL_CAPITAL), 2),
                "smart_compound_$": round(float(s_eq.iloc[-1] - INITIAL_CAPITAL), 2),
                "delta_compound_$": round(float((s_eq.iloc[-1] - INITIAL_CAPITAL) - (b_eq.iloc[-1] - INITIAL_CAPITAL)), 2),
            }
        )
    return pd.DataFrame(rows)


def by_regime_table(baseline: pd.DataFrame, smart: pd.DataFrame) -> pd.DataFrame:
    merged = baseline[["row_id", "hmm_state", "r_achieved", "pnl_usd"]].merge(
        smart[["row_id", "r_achieved", "pnl_usd"]],
        on="row_id",
        suffixes=("_baseline", "_smart"),
    )
    rows = []
    for regime, g in merged.groupby("hmm_state", dropna=False):
        rows.append(
            {
                "regime": regime,
                "trades": int(len(g)),
                "baseline_R": round(float(g["r_achieved_baseline"].sum()), 2),
                "smart_R": round(float(g["r_achieved_smart"].sum()), 2),
                "delta_R": round(float(g["r_achieved_smart"].sum() - g["r_achieved_baseline"].sum()), 2),
                "baseline_$": round(float(g["pnl_usd_baseline"].sum()), 2),
                "smart_$": round(float(g["pnl_usd_smart"].sum()), 2),
                "delta_$": round(float(g["pnl_usd_smart"].sum() - g["pnl_usd_baseline"].sum()), 2),
            }
        )
    return pd.DataFrame(rows).sort_values("regime")


def fmt_money(v: float) -> str:
    return f"${v:,.2f}"


def fmt_pf(v: float) -> str:
    return "inf" if math.isinf(v) else f"{v:.2f}"


def write_report(
    baseline: pd.DataFrame,
    smart: pd.DataFrame,
    base_sum: dict[str, object],
    smart_sum: dict[str, object],
    chunks: pd.DataFrame,
    regimes: pd.DataFrame,
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    smart.to_csv(OUT_DIR / "smart_exit_v1_trades.csv", index=False)
    chunks.to_csv(OUT_DIR / "baseline_vs_smart_exit_v1_every_100_trades.csv", index=False)
    regimes.to_csv(OUT_DIR / "baseline_vs_smart_exit_v1_by_regime.csv", index=False)

    comparison = pd.DataFrame([base_sum, smart_sum])
    comparison.to_csv(OUT_DIR / "baseline_vs_smart_exit_v1_summary.csv", index=False)

    delta_r = smart_sum["total_r"] - base_sum["total_r"]
    delta_fixed = smart_sum["fixed_lot_pnl_usd"] - base_sum["fixed_lot_pnl_usd"]
    delta_comp = smart_sum["compound_net_usd"] - base_sum["compound_net_usd"]
    delta_cap = smart_sum["capture_pct"] - base_sum["capture_pct"]

    lines = [
        "# SMART EXIT V1 - BASELINE COMPARISON",
        "",
        "## Scope",
        "- This is an isolated diagnostic backtest only.",
        "- Live bridge / dashboard / broker execution files were not changed.",
        "- Method: same baseline entries, then smart-exit v1 is simulated from M15 OHLC after entry.",
        "- Limitation: this post-process test does not enforce one-open-trade scheduling after delayed exits. Use it as design evidence, not final deployable proof.",
        "",
        "## Smart Exit V1 Rules",
        f"- Take full profit in Ranging at {RANGING_FAST_TAKE_R:.2f}R.",
        f"- Take full profit in Trending at {TREND_FAST_TAKE_R:.2f}R.",
        f"- After +{PARTIAL_R:.2f}R, close 50% and move runner stop to breakeven.",
        f"- If peak is >= {GIVEBACK_AFTER_R:.2f}R and close gives back below {GIVEBACK_KEEP:.0%} of peak, exit.",
        "- Exit on H1 structure break, or M15 structure break with weak momentum.",
        f"- Exit no-progress trades after {TIME_NO_PROGRESS_BARS} M15 bars if peak < 0.50R.",
        f"- Exit profitable long holds after {TIME_MAX_BARS} M15 bars.",
        "",
        "## Headline Result",
        f"- Baseline total: {base_sum['total_r']:+.1f}R | fixed lot PnL {fmt_money(base_sum['fixed_lot_pnl_usd'])} | compound net {fmt_money(base_sum['compound_net_usd'])}",
        f"- Smart Exit V1 total: {smart_sum['total_r']:+.1f}R | fixed lot PnL {fmt_money(smart_sum['fixed_lot_pnl_usd'])} | compound net {fmt_money(smart_sum['compound_net_usd'])}",
        f"- Delta: {delta_r:+.1f}R | fixed lot {fmt_money(delta_fixed)} | compound {fmt_money(delta_comp)} | capture {delta_cap:+.2f} pct-points",
        "",
        "## Summary Table",
        "| Metric | Baseline | Smart Exit V1 | Delta |",
        "|---|---:|---:|---:|",
        f"| Trades | {base_sum['trades']} | {smart_sum['trades']} | {smart_sum['trades'] - base_sum['trades']:+d} |",
        f"| Win rate | {base_sum['win_rate_pct']:.1f}% | {smart_sum['win_rate_pct']:.1f}% | {smart_sum['win_rate_pct'] - base_sum['win_rate_pct']:+.1f}% |",
        f"| Profit factor | {fmt_pf(base_sum['profit_factor'])} | {fmt_pf(smart_sum['profit_factor'])} | |",
        f"| Avg R | {base_sum['avg_r']:+.3f} | {smart_sum['avg_r']:+.3f} | {smart_sum['avg_r'] - base_sum['avg_r']:+.3f} |",
        f"| Total R | {base_sum['total_r']:+.1f}R | {smart_sum['total_r']:+.1f}R | {delta_r:+.1f}R |",
        f"| Fixed lot PnL | {fmt_money(base_sum['fixed_lot_pnl_usd'])} | {fmt_money(smart_sum['fixed_lot_pnl_usd'])} | {fmt_money(delta_fixed)} |",
        f"| Compound net at 3% risk | {fmt_money(base_sum['compound_net_usd'])} | {fmt_money(smart_sum['compound_net_usd'])} | {fmt_money(delta_comp)} |",
        f"| Compound final equity | {fmt_money(base_sum['compound_final_equity'])} | {fmt_money(smart_sum['compound_final_equity'])} | {fmt_money(smart_sum['compound_final_equity'] - base_sum['compound_final_equity'])} |",
        f"| Compound max DD | {base_sum['compound_max_dd_pct']:.1f}% | {smart_sum['compound_max_dd_pct']:.1f}% | {smart_sum['compound_max_dd_pct'] - base_sum['compound_max_dd_pct']:+.1f}% |",
        f"| Captured points | {base_sum['captured_points']:+,.0f} | {smart_sum['captured_points']:+,.0f} | {smart_sum['captured_points'] - base_sum['captured_points']:+,.0f} |",
        f"| Capture efficiency | {base_sum['capture_pct']:.2f}% | {smart_sum['capture_pct']:.2f}% | {delta_cap:+.2f}% |",
        "",
        "## Every 100 Trades",
        chunks.to_markdown(index=False),
        "",
        "## By Regime",
        regimes.to_markdown(index=False),
        "",
        "## Smart Exit Reason Mix",
        smart["exit_reason"].value_counts().to_frame("count").to_markdown(),
        "",
        "## Verdict",
    ]
    if delta_r > 0 and delta_fixed > 0:
        lines.extend(
            [
                "- Smart Exit V1 improves this diagnostic test.",
                "- Next step: move this logic into the real replay engine so one-open-trade scheduling and signal blocking are measured correctly.",
            ]
        )
    else:
        lines.extend(
            [
                "- Smart Exit V1 does not beat the baseline in this diagnostic test.",
                "- Best next step: tune the exit rules by regime before touching live code.",
            ]
        )
    lines.append("")

    (OUT_DIR / "SMART_EXIT_V1_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    available_points = read_baseline_available_points()
    trades, ohlc = load_inputs()
    baseline = make_baseline_frame(trades)
    smart = build_windows(trades, ohlc)
    base_sum = summarize("Baseline", baseline, available_points)
    smart_sum = summarize("Smart Exit V1", smart, available_points)
    chunks = chunk_table(baseline, smart)
    regimes = by_regime_table(baseline, smart)
    write_report(baseline, smart, base_sum, smart_sum, chunks, regimes)

    print("SMART EXIT V1 diagnostic complete")
    print(f"Output folder: {OUT_DIR}")
    print(f"Baseline: {base_sum['total_r']:+.1f}R | {fmt_money(base_sum['fixed_lot_pnl_usd'])}")
    print(f"Smart   : {smart_sum['total_r']:+.1f}R | {fmt_money(smart_sum['fixed_lot_pnl_usd'])}")
    print(f"Delta   : {smart_sum['total_r'] - base_sum['total_r']:+.1f}R | {fmt_money(smart_sum['fixed_lot_pnl_usd'] - base_sum['fixed_lot_pnl_usd'])}")


if __name__ == "__main__":
    main()
