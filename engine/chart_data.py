"""
chart_data.py - build logs/chart_data.json for chart.html.

Includes the last N M15 candles, all bridge signals in that window, and
paper-trade entry/exit markers from shadow_trades.csv.
Usage:  python chart_data.py [num_bars]   (default 1200)
"""
import csv
import io
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from config import CFG
    LOGS = Path(CFG.paths.logs_dir)
except Exception:
    LOGS = Path(__file__).resolve().parent / "logs"

ENGINE = Path(__file__).resolve().parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1200

OHLC_SOURCES = [
    ENGINE.parent / "data" / "merged" / "ohlc_merged.csv",
    ENGINE.parent / "data" / "live" / "ohlc_live.csv",
    LOGS.parent / "merged" / "ohlc_merged.csv",
    ENGINE / "ohlc_merged.csv",
    LOGS / "chart_ohlc_live.csv",
]


def _sec(t):
    return int(pd.Timestamp(t).timestamp())


def _current_m15_open():
    dash = LOGS / "dashboard.json"
    if not dash.exists():
        return None
    try:
        d = json.loads(dash.read_text(encoding="utf-8"))
        raw = d.get("broker_time") or d.get("updated")
        ts = pd.Timestamp(raw) if raw else pd.NaT
        if pd.isna(ts):
            return None
        return pd.Timestamp(ts).floor("15min")
    except Exception:
        return None


def _dashboard_live():
    dash = LOGS / "dashboard.json"
    if not dash.exists():
        return None
    try:
        d = json.loads(dash.read_text(encoding="utf-8"))
        bid = float(d.get("bid") or 0)
        current_open = _current_m15_open()
        if not bid or current_open is None:
            return None
        direction = ""
        open_trades = d.get("open_trades") or []
        if open_trades:
            direction = str(open_trades[0].get("direction", "")).upper()
        return {"time": current_open, "bid": bid, "direction": direction}
    except Exception:
        return None


def _read_signal_csv(path):
    """Read signals_all.csv even if an older header is missing the move column."""
    if not path.exists():
        return pd.DataFrame()
    with open(path, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        return pd.DataFrame()

    header = rows[0]
    original_width = len(header)
    move_insert_at = None
    if "trading_equity" not in header:
        header.append("trading_equity")
    if "move" not in header:
        move_insert_at = header.index("trading_equity") if "trading_equity" in header else len(header)
        header.insert(move_insert_at, "move")

    expected = len(header)
    fixed = []
    for row in rows[1:]:
        if move_insert_at is not None and len(row) == original_width:
            row = row[:move_insert_at] + [""] + row[move_insert_at:]
        while len(row) < expected:
            row.append("")
        if len(row) > expected:
            row = row[:expected]
        fixed.append(row)
    return pd.DataFrame(fixed, columns=header)


def _read_signal_db():
    """Primary immutable signal source for chart markers."""
    db_path = Path(getattr(CFG.paths, "db_path", LOGS / "qgai.db"))
    if not db_path.exists():
        return pd.DataFrame()
    try:
        con = sqlite3.connect(str(db_path))
        df = pd.read_sql_query(
            """
            SELECT signal_id, signal_created_at, bar_time, mode, signal, win_prob,
                   hmm_state, reason, price, trade_action, model_version, feature_hash
            FROM signals
            WHERE mode != 'BACKTEST'
            ORDER BY COALESCE(signal_created_at, bar_time), id
            """,
            con,
        )
        con.close()
        return df
    except Exception as e:
        print(f"Skipped signal DB source {db_path}: {e}")
        return pd.DataFrame()


def _read_ohlc_source(path):
    df = pd.read_csv(path)
    tcol = "time" if "time" in df.columns else ("datetime" if "datetime" in df.columns else df.columns[0])
    df = df.rename(columns={tcol: "time"})
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["time"]).copy()
    return df[["time", "open", "high", "low", "close"]]


def _latest_snapshot_closed_time():
    snap = LOGS / "chart_ohlc_live.csv"
    if not snap.exists():
        return None
    try:
        df = _read_ohlc_source(snap)
        if df.empty:
            return None
        return pd.Timestamp(df["time"].max())
    except Exception:
        return None


def _load_ohlc():
    frames = []
    for src in OHLC_SOURCES:
        if src.exists():
            try:
                frames.append(_read_ohlc_source(src))
            except Exception as e:
                print(f"Skipped OHLC source {src}: {e}")
    if not frames:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close"])

    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["time"]).drop_duplicates("time", keep="last").sort_values("time")
    snapshot_closed = _latest_snapshot_closed_time()
    if snapshot_closed is not None:
        df = df[df["time"] <= snapshot_closed].copy()
    else:
        current_open = _current_m15_open()
        if current_open is not None:
            df = df[df["time"] < current_open].copy()
    df = df.sort_values("time").tail(N).reset_index(drop=True)
    return df[["time", "open", "high", "low", "close"]]


def _ohlc_lag_info(df):
    sig = _read_signal_csv(LOGS / "signals_all.csv")
    info = {
        "ohlc_lag_bars": 0,
        "latest_signal_time": "",
        "latest_ohlc_time": "",
        "expected_closed_ohlc_time": "",
    }
    if df.empty:
        return info
    last_time = pd.Timestamp(df["time"].max())
    info["latest_ohlc_time"] = str(last_time)

    current_open = _current_m15_open()
    if current_open is not None:
        expected_closed = current_open - pd.Timedelta(minutes=15)
        info["expected_closed_ohlc_time"] = str(expected_closed)
        if expected_closed > last_time:
            info["ohlc_lag_bars"] = int((expected_closed - last_time) / pd.Timedelta(minutes=15))

    if sig.empty or "bar_time" not in sig.columns:
        return info

    sig["bar_time"] = pd.to_datetime(sig["bar_time"], errors="coerce")
    sig = sig.dropna(subset=["bar_time"])
    if sig.empty:
        return info
    latest_sig = pd.Timestamp(sig["bar_time"].max())
    info["latest_signal_time"] = str(latest_sig)
    if current_open is None and not info["ohlc_lag_bars"] and latest_sig > last_time:
        info["ohlc_lag_bars"] = int((latest_sig - last_time) / pd.Timedelta(minutes=15))
    return info


def _signal_markers(start_t, end_t):
    sig = _read_signal_db()
    if sig.empty:
        sig = _read_signal_csv(LOGS / "signals_all.csv")
    if sig.empty or "bar_time" not in sig.columns:
        return [], [], {"BUY": 0, "SELL": 0, "SKIP": 0}

    sig["bar_time"] = pd.to_datetime(sig["bar_time"], errors="coerce")
    sig = sig.dropna(subset=["bar_time"])
    sig = sig[(sig["bar_time"] >= start_t) & (sig["bar_time"] <= end_t)].copy()
    # Repaint audit 2026-07-14: never collapse historical signal rows by
    # bar_time+mode. If the same candle was evaluated again later, the old
    # BUY/SELL marker must remain visible instead of being replaced by the
    # newest snapshot. New immutable rows carry signal_id/signal_created_at.
    if "signal_id" in sig.columns:
        keyed = sig[sig["signal_id"].astype(str).str.len() > 0]
        unkeyed = sig[sig["signal_id"].astype(str).str.len() == 0]
        keyed = keyed.drop_duplicates(subset=["signal_id"], keep="first")
        sig = pd.concat([keyed, unkeyed], ignore_index=True)
    sig = sig.sort_values(["bar_time"]).reset_index(drop=True)

    clean_markers = []
    all_markers = []
    counts = {"BUY": 0, "SELL": 0, "SKIP": 0}
    for r in sig.itertuples(index=False):
        signal = str(getattr(r, "signal", "SKIP")).upper()
        win_prob = getattr(r, "win_prob", "")
        if signal not in counts:
            signal = "SKIP"
        counts[signal] += 1

        if signal == "BUY":
            m = {
                "time": _sec(r.bar_time), "position": "belowBar", "shape": "arrowUp",
                "color": "#76ff03", "size": 1, "text": "",
            }
            all_markers.append(m)
            clean_markers.append({**m, "text": f"B{float(win_prob or 0):.2%}"})
        elif signal == "SELL":
            m = {
                "time": _sec(r.bar_time), "position": "aboveBar", "shape": "arrowDown",
                "color": "#ff1744", "size": 1, "text": "",
            }
            all_markers.append(m)
            clean_markers.append({**m, "text": f"S{float(win_prob or 0):.2%}"})
    return clean_markers, all_markers, counts


def _trade_markers(start_t, end_t):
    path = LOGS / "shadow_trades.csv"
    if not path.exists():
        return [], 0

    st = pd.read_csv(path)
    if st.empty:
        return [], 0
    st["entry_time"] = pd.to_datetime(st["entry_time"], errors="coerce")
    st["exit_time"] = pd.to_datetime(st.get("exit_time"), errors="coerce")
    st = st.dropna(subset=["entry_time"])
    st = st[(st["entry_time"] <= end_t) & (st["exit_time"].fillna(end_t) >= start_t)].copy()

    markers = []
    for r in st.itertuples(index=False):
        direction = str(getattr(r, "direction", "")).upper()
        entry_txt = "B" if direction == "BUY" else "S"
        if pd.notna(r.entry_time) and start_t <= r.entry_time <= end_t:
            markers.append({
                "time": _sec(r.entry_time),
                "position": "belowBar" if direction == "BUY" else "aboveBar",
                "shape": "arrowUp" if direction == "BUY" else "arrowDown",
                "color": "#76ff03" if direction == "BUY" else "#ff1744",
                "size": 2,
                "text": entry_txt,
            })
        if pd.notna(r.exit_time) and start_t <= r.exit_time <= end_t:
            pnl = getattr(r, "pnl_usd", "")
            rsn = getattr(r, "exit_reason", "")
            r_mult = getattr(r, "R", "")
            color = "#76ff03" if float(r_mult or 0) >= 0 else "#ff1744"
            markers.append({
                "time": _sec(r.exit_time), "position": "inBar", "shape": "circle",
                "color": color, "size": 1,
                "text": "X",
            })
    return markers, len(st)


def _trade_intervals(start_t, end_t):
    path = LOGS / "shadow_trades.csv"
    if not path.exists():
        return []

    st = pd.read_csv(path)
    if st.empty:
        return []
    st["entry_time"] = pd.to_datetime(st["entry_time"], errors="coerce")
    st["exit_time"] = pd.to_datetime(st.get("exit_time"), errors="coerce")
    st = st.dropna(subset=["entry_time"])
    st = st[(st["entry_time"] <= end_t) & (st["exit_time"].fillna(end_t) >= start_t)].copy()

    intervals = []
    for r in st.itertuples(index=False):
        direction = str(getattr(r, "direction", "")).upper()
        if direction not in ("BUY", "SELL"):
            continue
        entry = _sec(r.entry_time)
        exit_time = r.exit_time if pd.notna(r.exit_time) else end_t
        intervals.append((entry, _sec(exit_time), direction))
    return sorted(intervals)


def _candle_state(ts, intervals):
    state = "FLAT"
    best_entry = -1
    for entry, exit_time, direction in intervals:
        if entry <= ts <= exit_time and entry > best_entry:
            best_entry = entry
            state = direction
    return state


def _append_live_candle(candles, intervals, colors):
    live = _dashboard_live()
    if not live or not candles:
        return ""
    ts = _sec(live["time"])
    if ts <= candles[-1]["time"]:
        return ""
    op = float(candles[-1]["close"])
    px = float(live["bid"])
    state = live["direction"] if live["direction"] in ("BUY", "SELL") else _candle_state(ts, intervals)
    color = colors.get(state, colors["FLAT"])
    candles.append({
        "time": ts,
        "open": op,
        "high": max(op, px),
        "low": min(op, px),
        "close": px,
        "color": color,
        "borderColor": color,
        "wickColor": color,
    })
    return str(live["time"])


def main():
    df = _load_ohlc()
    if df.empty:
        print("No OHLC rows found in merged/live CSV sources.")
        return

    start_t = df["time"].iloc[0]
    end_t = df["time"].iloc[-1]
    lag_info = _ohlc_lag_info(df)
    intervals = _trade_intervals(start_t, end_t)
    colors = {
        "BUY": "#76ff03",
        "SELL": "#ff1744",
        "FLAT": "#ffff00",
    }

    candles = []
    for r in df.itertuples(index=False):
        ts = _sec(r.time)
        state = _candle_state(ts, intervals)
        color = colors[state]
        candles.append({
            "time": ts,
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "color": color,
            "borderColor": color,
            "wickColor": color,
        })

    live_candle_time = _append_live_candle(candles, intervals, colors)
    marker_end_t = pd.Timestamp(live_candle_time) if live_candle_time else end_t

    signal_markers, all_signal_markers, signal_counts = _signal_markers(start_t, marker_end_t)
    n_signals = len(all_signal_markers)
    trade_markers, n_trades = _trade_markers(start_t, marker_end_t)
    trade_markers = sorted(trade_markers, key=lambda x: (x["time"], x["text"]))
    signal_markers = sorted(signal_markers + trade_markers, key=lambda x: (x["time"], x["text"]))
    all_markers = sorted(all_signal_markers + trade_markers, key=lambda x: (x["time"], x["text"]))

    out = {
        "symbol": "XAUUSD M15",
        "timeframe": "M15",
        "candles": candles,
        "markers": trade_markers,
        "marker_groups": {
            "trades": trade_markers,
            "signals": signal_markers,
            "all": all_markers,
        },
        "n_candles": len(candles),
        "n_signals": n_signals,
        "n_trades": n_trades,
        "signal_counts": signal_counts,
        "from": str(start_t),
        "to": str(marker_end_t),
        "closed_to": str(end_t),
        "live_candle_time": live_candle_time,
        "updated_at": str(pd.Timestamp.now().floor("s")),
        **lag_info,
    }
    (LOGS / "chart_data.json").write_text(json.dumps(out), encoding="utf-8")
    print(
        f"chart_data.json: {len(candles)} candles, {n_signals} signals, "
        f"{n_trades} trades ({out['from']} -> {out['to']})"
    )


if __name__ == "__main__":
    main()
