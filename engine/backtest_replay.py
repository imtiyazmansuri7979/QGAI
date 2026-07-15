"""
backtest_replay.py — QUANT GOLD AI · Event-Based AI Replay Backtest Engine
===========================================================================
Replays historical M15 bars through the SAME LiveInferenceEngine the live
bridge uses, simulates trades with the live SL/TP/trailing/partial rules,
and logs every trade with the full feature snapshot.

Usage:
    python backtest_replay.py --from 2026-01-01 --to 2026-04-29
    python backtest_replay.py --from 2025-06-01 --to 2025-12-31 --equity 2500 --risk 3
    python backtest_replay.py --from 2026-01-01 --to 2026-03-01 --spread 0.13 --max-open 1

Outputs (in logs/):
    backtest_trades.csv   — every simulated trade + all f_* feature values
    backtest_signals.csv  — every bar decision (BUY/SELL/SKIP, probs, reason)
    backtest_report.txt   — performance summary

Honesty rules:
    * Decision on bar close → execution at NEXT bar open (+ spread). No lookahead.
    * Worst-case intrabar: if a candle touches both SL and TP, SL counts FIRST.
    * Use --from AFTER your model's training cutoff for a true out-of-sample test.
      In-sample results (model tested on data it trained on) are NOT meaningful.
"""

import os
import sys, io
# line_buffering=True: 2026-07-01 (Imtiyaz) — progress prints (every 100 bars) were sitting
# in Python's stdout buffer and not reaching the console until the buffer filled or the
# process exited, making a long backtest LOOK frozen/blank for minutes at a time even
# though it was working. Line-buffered = each print() flushes immediately.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

import argparse
import json
import pickle
import signal
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from config import CFG

# Live trade-management constants — single source of truth when available.
# bridge_constants imports the MetaTrader5 module (Windows only); on machines
# without it we fall back to the SAME values (keep in sync with bridge_constants.py).
try:
    from bridge_constants import (
        TP_MULT, TRAIL_AFTER_R, TRAILING_SL,
        PARTIAL_CLOSE_ENABLED, PARTIAL_CLOSE_PCT, PARTIAL_CLOSE_TP2_R,
    )
except Exception:
    TP_MULT                    = 1.5
    TRAIL_AFTER_R, TRAILING_SL = 1.0, True
    PARTIAL_CLOSE_ENABLED      = True
    PARTIAL_CLOSE_PCT          = 0.50
    PARTIAL_CLOSE_TP2_R        = 3.0
    print("⚠️  MetaTrader5 module not found — using mirrored constants "
          "(same values as bridge_constants.py)")

try:
    from bridge_constants import (RATCHET_EXIT, RATCHET_BUF_PCT,
                                  RATCHET_TP_CAP_PCT, RATCHET_MAX_RISK_PCT,
                                  RATCHET_FLIP_EXIT)
except Exception:
    RATCHET_EXIT, RATCHET_BUF_PCT = False, 0.21
    RATCHET_TP_CAP_PCT, RATCHET_MAX_RISK_PCT, RATCHET_FLIP_EXIT = 1.5, 1.2, True
from trend_signal import compute_trend as _ts_compute

NO_TRAIL = False   # set by --no-trail: disables the upward stop-trail (flip-only exits)
# Trail mode (set by --trail-mode): how the stop trails in ratchet mode.
#   line    = trail the (M15) ratchet line from bar-1 (current behaviour)
#   off     = no trail (flip-only) — same as --no-trail
#   after1r = trail the line only AFTER the trade is +1R in profit
#   be      = at +1R move stop to breakeven and stop (no further trail)
#   htf     = trail the H1 ratchet line (slower) instead of M15
TRAIL_MODE   = "line"
TRAIL_AFTER  = 1.0     # R threshold for after1r / be modes

LOGS = Path(CFG.paths.logs_dir)


# ════════════════════════════════════════════════════════════════
# Simulated trade — mirrors bridge_risk.VirtualTrade bar-by-bar
# ════════════════════════════════════════════════════════════════
class SimTrade:
    def __init__(self, direction, entry_time, entry_price, sl_dist, risk_usd, sig, features,
                 ratchet=False, ratchet_buf=0.0, ratchet_buf_pct=0.0):
        self.direction   = direction              # "BUY" / "SELL"
        self.entry_time  = entry_time
        self.entry       = entry_price
        self.sl_dist     = sl_dist                # $ distance of 1R
        self.risk_usd    = risk_usd               # $ risked on full position
        self.sig         = sig                    # signal dict at entry
        self.features    = features or {}

        s = 1 if direction == "BUY" else -1
        self.s           = s
        self.virtual_sl  = entry_price - s * sl_dist
        # M1: TP distances can be overridden by the move model (predicted mode)
        _tp1d = sig.get("_tp1_dist") or sl_dist * TP_MULT                  # default 1.5R
        _tp2d = sig.get("_tp2_dist") or sl_dist * PARTIAL_CLOSE_TP2_R      # default 3R
        self.tp1         = entry_price + s * _tp1d
        # M5: runner=trail → no TP2 target; runner rides until trail/BE/SL
        self.tp2         = None if sig.get("_runner_trail") else entry_price + s * _tp2d
        # M2: trailing distance can be overridden by the MAE model
        self.trail_dist  = sig.get("_trail_dist") or sl_dist * 0.75
        self.breakeven   = False
        self.trailing    = False
        self.partial_done = False
        self.realized_r  = 0.0    # R locked in by partial close
        self.open_frac   = 1.0    # fraction of position still open
        self.peak_r      = 0.0

    # ── helpers ──────────────────────────────────────────────
        # RATCHET mode (EA-style)
        self.ratchet     = ratchet
        self.ratchet_buf = ratchet_buf
        self.ratchet_buf_pct = ratchet_buf_pct   # 2026-06-30: %-of-line trail buffer (live parity)
        if ratchet:
            # no partial / BE / R-trail — line + flip decide; TP = far cap
            self.tp2 = None
        self.tp_equity_usd = None   # equity-based TP $ target (set externally)

    def ratchet_bar(self, time, line, flip, close_px):
        """Per-bar (close) ratchet step: one-way line trail + flip exit.
        Returns close-result dict on flip exit, else None."""
        s = self.s
        if RATCHET_FLIP_EXIT and flip == -s:
            return self._close(time, close_px, "FLIP")
        # ── trail modes ──────────────────────────────────────────────
        if NO_TRAIL or TRAIL_MODE == "off":
            return None                              # flip-only: never trail
        # regime: data-backed — TRAIL is net-negative in Ranging/Trending (let
        # FLIP exit) but positive in Volatile (keep the line-trail).
        if TRAIL_MODE == "regime" and self.sig.get("hmm_state", "") in ("Ranging", "Trending"):
            return None
        pr = (close_px - self.entry) * s / self.sl_dist if self.sl_dist else 0.0
        if TRAIL_MODE in ("after1r", "be") and pr < TRAIL_AFTER:
            return None                              # wait for +1R before trailing
        if TRAIL_MODE == "be":
            be = self.entry + s * self.ratchet_buf   # move to breakeven once, then stop
            if (s == 1 and be > self.virtual_sl) or (s == -1 and be < self.virtual_sl):
                self.virtual_sl = round(be, 2)
                self.trailing   = True
            return None                              # no further trail beyond BE
        # 'line', 'after1r', 'htf' all trail the supplied line (htf line is fed in
        # by the caller); after1r reaches here only once pr >= TRAIL_AFTER.
        if line is not None and not np.isnan(line):
            # 2026-06-30 (Anisa): %-of-line buffer (live parity with bridge_risk); fall back to fixed-$ if unset
            _b = (line * self.ratchet_buf_pct / 100.0) if self.ratchet_buf_pct else self.ratchet_buf
            new_sl = line - s * _b
            if (s == 1 and new_sl > self.virtual_sl) or (s == -1 and new_sl < self.virtual_sl):
                self.virtual_sl = round(new_sl, 2)
                self.trailing   = True
        return None

    def _r(self, price):
        return self.s * (price - self.entry) / self.sl_dist if self.sl_dist else 0.0

    def _close(self, time, price, reason):
        """Close remaining fraction at price → final result dict."""
        r_final = self.realized_r + self._r(price) * self.open_frac
        return {
            "exit_time":   time,
            "exit_price":  round(price, 2),
            "exit_reason": reason,
            "r_achieved":  round(r_final, 3),
            "pnl_usd":     round(r_final * self.risk_usd, 2),
            "peak_r":      round(self.peak_r, 3),
        }

    # ── one M15 bar of management ────────────────────────────
    def update(self, time, o, h, l, c):
        """
        Process one bar. Returns close-result dict if trade ended, else None.
        Worst-case ordering inside the bar:
          1. SL touch checked FIRST (pessimistic)
          2. then TP1 partial / TP2 target
          3. breakeven + trailing updated from bar CLOSE (live updates every
             2s; bar close is the conservative bar-level equivalent)
        """
        s = self.s
        bar_lo_r = self._r(l if s == 1 else h)   # worst price of bar in R
        bar_hi_r = self._r(h if s == 1 else l)   # best price of bar in R
        self.peak_r = max(self.peak_r, self.realized_r / max(PARTIAL_CLOSE_PCT, 1e-9)
                          if False else bar_hi_r)  # peak of full-position R

        # 1) Virtual SL first (worst case)
        sl_touched = (l <= self.virtual_sl) if s == 1 else (h >= self.virtual_sl)
        if sl_touched:
            reason = ("TRAIL" if self.trailing else
                      "BE"    if self.breakeven else "SL")
            return self._close(time, self.virtual_sl, reason)

        if self.ratchet:
            # equity-based TP: close when best-of-bar profit $ >= equity% target
            if self.tp_equity_usd is not None:
                best_profit_usd = bar_hi_r * self.risk_usd
                if best_profit_usd >= self.tp_equity_usd:
                    # price at which profit target is hit
                    tp_price = self.entry + s * (self.tp_equity_usd / self.risk_usd) * self.sl_dist
                    return self._close(time, round(tp_price, 2), "TPEQ")
                return None
            # RATCHET: only far TP cap; trail/flip handled in ratchet_bar()
            tp_touched = (h >= self.tp1) if s == 1 else (l <= self.tp1)
            if tp_touched:
                return self._close(time, self.tp1, "TPCAP")
            return None

        # 2) TP1 partial close (once)
        tp1_touched = (h >= self.tp1) if s == 1 else (l <= self.tp1)
        if PARTIAL_CLOSE_ENABLED and not self.partial_done and tp1_touched:
            self.realized_r  += self._r(self.tp1) * PARTIAL_CLOSE_PCT
            self.open_frac   -= PARTIAL_CLOSE_PCT
            self.partial_done = True
            # move SL to breakeven on the runner (live behavior at >=1R)
            self.virtual_sl   = self.entry
            self.breakeven    = True

        # 3) TP2 runner target (None = no target, runner exits via trail/BE/SL)
        tp2_touched = False if self.tp2 is None else \
            ((h >= self.tp2) if s == 1 else (l <= self.tp2))
        if tp2_touched:
            return self._close(time, self.tp2, "TP2" if self.partial_done else "TP")
        if not PARTIAL_CLOSE_ENABLED and tp1_touched:
            return self._close(time, self.tp1, "TP")

        # 4) Breakeven + trailing — from bar close (conservative)
        close_r = self._r(c)
        if not self.breakeven and close_r >= TRAIL_AFTER_R:
            self.virtual_sl = self.entry
            self.breakeven  = True
        if self.breakeven and TRAILING_SL:
            trail = c - s * self.trail_dist
            if (s == 1 and trail > self.virtual_sl) or (s == -1 and trail < self.virtual_sl):
                self.virtual_sl = round(trail, 2)
                self.trailing   = True
        return None


# ════════════════════════════════════════════════════════════════
# Replay loop
# ════════════════════════════════════════════════════════════════
def run(args):
    global NO_TRAIL, TRAIL_MODE, LOGS
    NO_TRAIL = getattr(args, "no_trail", False)
    # 2026-06-27 Bug F: default the stop-trail to the LIVE config. If --stop-trail isn't
    # given explicitly, follow ratchet_htf_sl: HTF → "htf", else "line". This keeps every
    # backtest (incl. the WFO, which never passed --trail-mode) matched to live's HTF exit.
    _stp = getattr(args, "stop_trail", None)
    if NO_TRAIL:
        TRAIL_MODE = "off"
    elif _stp:
        TRAIL_MODE = _stp
    else:
        TRAIL_MODE = "htf" if getattr(CFG.filters, "ratchet_htf_sl", False) else "line"
    # Route backtest output OUT of engine/logs → backtest/results/ (live logs stay in engine).
    _od = getattr(args, "out_dir", "") or ""
    LOGS = Path(_od) if _od else (Path(__file__).resolve().parent.parent / "backtest" / "results" / "replay_logs")
    LOGS.mkdir(parents=True, exist_ok=True)
    _suffix = "" if (args.tp_mode, args.sl_mode, args.trail_mode) == ("fixed",)*3 else \
        f"_{args.tp_mode[0]}tp_{args.sl_mode[0]}sl_{args.trail_mode[0]}tr"
    _st = TRAIL_MODE
    if _st != "line":
        _suffix += f"_st-{_st}"
    _trades_csv = LOGS / f"backtest_trades{_suffix}.csv"
    _signals_csv = LOGS / f"backtest_signals{_suffix}.csv"
    _checkpoint_pkl = LOGS / f"backtest_checkpoint{_suffix}.pkl"
    # 2026-07-01 (Imtiyaz): resume support. Signature = every arg that changes the
    # simulation, so a checkpoint is ONLY ever reused for the EXACT same config —
    # never silently resumed into a mismatched run (same paranoia as the WFO-cache
    # Bug H precedent: a stale/mismatched cache producing wrong-but-plausible results).
    # FAB-H8 (2026-07-07): fold ALL QGAI_* env toggles + model-file mtimes into
    # the resume signature. Without this, changing an env flag (CTF/SMMA/ADX/
    # early-entry) or retraining models and re-running the same CLI would resume
    # a half-old/half-new checkpoint → plausible-but-wrong results (WFO-cache
    # class bug, BUG_LOG #H). Signature mismatch now forces a fresh run.
    _env_sig = tuple(sorted(
        (k, v) for k, v in os.environ.items() if k.startswith("QGAI_")
    ))
    _model_sig = ()
    try:
        from pathlib import Path as _P
        _mdir = _P(CFG.paths.models_dir)
        if _mdir.exists():
            _model_sig = tuple(sorted(
                (p.name, int(p.stat().st_mtime))
                for p in _mdir.glob("*.pkl")
            ))
    except Exception:
        _model_sig = ()
    _resume_sig = (
        args.date_from, args.date_to, args.equity, args.risk, args.spread,
        args.ratchet, args.ratchet_buf_mode, args.ratchet_buf_mult, args.ratchet_buf_pct,
        args.daily_sl, args.tp_cap, args.tp_regime, args.skip_counter_trend, args.ctf_fade,
        args.tp_equity_pct, args.max_open, args.tp_mode, args.sl_mode, args.trail_mode,
        args.runner, args.pred_dirs, args.dd_brake, args.fixed_lot, args.max_lot,
        args.no_trail, args.stop_trail, TRAIL_MODE,
        _env_sig, _model_sig,
    )
    print("=" * 64)
    print(f"⚡ QGAI AI REPLAY BACKTEST  [trail={TRAIL_MODE}]")
    print("=" * 64)

    # ── DATA-LEAKAGE GUARD (Imtiyaz, 2026-07-13) ────────────────────────────
    # Hard-stop BEFORE any real work if the currently-trained models' data
    # exposure (train+val+test+calibration, across EVERY gating model file)
    # reaches args.date_from or later. A printed warning is not enough — see
    # leakage_guard.py for why. --allow-in-sample is the only override, and
    # it must be passed explicitly on the command line every time.
    import leakage_guard
    try:
        leakage_guard.assert_no_leakage(
            CFG.paths.models_dir, args.date_from,
            allow_in_sample=getattr(args, "allow_in_sample", False),
        )
    except RuntimeError as _leak_err:
        print(f"\n{_leak_err}\n")
        raise SystemExit(1)

    # 1. Engine — the SAME brain as live ------------------------------------
    from inference import LiveInferenceEngine, trend_pullback_block, trend_pullback_generate, smma_mtf_soft_block, adx_strength_soft_block
    engine = LiveInferenceEngine()
    engine.update_capital(args.equity)

    ohlc = engine.ohlc_df.copy()
    ohlc["datetime"] = pd.to_datetime(ohlc["datetime"])
    ohlc = ohlc.sort_values("datetime").reset_index(drop=True)

    t_from = pd.Timestamp(args.date_from)
    t_to   = pd.Timestamp(args.date_to) + pd.Timedelta(days=1)
    idx_all = ohlc.index[(ohlc["datetime"] >= t_from) & (ohlc["datetime"] < t_to)]
    if len(idx_all) < 10:
        print(f"❌ Only {len(idx_all)} bars in range {args.date_from} → {args.date_to}. "
              f"Data covers {ohlc['datetime'].min()} → {ohlc['datetime'].max()}")
        sys.exit(1)
    # RATCHET: precompute trend lines on the full OHLC (same engine as live)
    _ratchet_on = RATCHET_EXIT if args.ratchet == "auto" else (args.ratchet == "on")
    _BUFPCT = args.ratchet_buf_pct if args.ratchet_buf_pct is not None else RATCHET_BUF_PCT
    _TPCAP = args.tp_cap if args.tp_cap is not None else RATCHET_TP_CAP_PCT
    # REGIME-ADAPTIVE TP (2026-06-26): per-HMM-state TP cap from the 13-TP sweep.
    # Ranging wants wide TP, Volatile wants tight, Trending in the middle.
    # 2026-07-13 (night): now reads the single source of truth in config.py
    # (was a duplicated literal here + relabel_trades.py + rebuild_trainset.py +
    # shadow_ledger.py — a drift-bug risk). Values unchanged, source centralized.
    _TP_BY_REGIME = dict(CFG.filters.tp_by_regime)
    # FIX (2026-07-08): per-regime TP override for the TP-cap sweep. Env
    # QGAI_TP_REGIME_VALS="R,T,V" (e.g. "2.4,1.2,0.6") overrides the defaults
    # so a sweep can vary one regime while holding the others. Empty/unset = defaults.
    _tpv = os.environ.get("QGAI_TP_REGIME_VALS", "").strip()
    if _tpv:
        try:
            _r, _t, _v = (float(x) for x in _tpv.split(","))
            _TP_BY_REGIME = {"Ranging": _r, "Trending": _t, "Volatile": _v}
        except Exception:
            print(f"   ⚠ bad QGAI_TP_REGIME_VALS='{_tpv}' — using defaults")
    if args.tp_regime:
        print(f"   ⚙ REGIME-ADAPTIVE TP ON: {_TP_BY_REGIME} (fallback {_TPCAP}%)")
    if _ratchet_on:
        _tdf = _ts_compute(ohlc.rename(columns={"datetime": "time"})
                           [["time", "open", "high", "low", "close"]], 2, "SMMA")
        _buyL  = _tdf["buy_line"].to_numpy()
        _sellL = _tdf["sell_line"].to_numpy()
        _flip  = _tdf["flip"].to_numpy()
        _bandpct = _tdf["band_width_pct"].to_numpy()   # SMMA band width % (Step 1: band buffer)
        # H1 ratchet line for --stop-trail htf (slower trail). Only computed when the
        # htf mode is actually selected. Map each M15 bar to the last CLOSED H1 line
        # (no lookahead). Requires a real DatetimeIndex for resample/merge_asof.
        _buyL_h1 = _sellL_h1 = _flip_h1 = None
        if TRAIL_MODE == "htf":
            # pick the single datetime column by name (ohlc may have BOTH "datetime"
            # and "time" → a rename would create duplicate "time" cols and crash
            # to_datetime with "duplicate keys"). Select positionally to stay clean.
            _tc = "datetime" if "datetime" in ohlc.columns else "time"
            _h1src = ohlc[[_tc, "open", "high", "low", "close"]].copy()
            _h1src.columns = ["time", "open", "high", "low", "close"]
            _h1src["time"] = pd.to_datetime(_h1src["time"])
            _h1d = (_h1src.set_index("time")
                    .resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"})
                    .dropna().reset_index())
            _h1t = _ts_compute(_h1d, 2, "SMMA")
            # 2026-06-30 (Anisa): forming-bar parity. When ratchet_htf_forming, the H1 line is
            # valid from the bar's OPEN (live includes the forming bar; line[i]=MA[i-1]+offset so
            # NO lookahead). Else last-closed = valid at CLOSE (+1h). Matches bridge_ratchet.
            if bool(getattr(CFG.filters, "ratchet_htf_forming", False)):
                _h1t["vf"] = _h1t["time"]
            else:
                _h1t["vf"] = _h1t["time"] + pd.Timedelta(hours=1)
            _left = ohlc[[_tc]].copy()
            _left.columns = ["time"]
            _left["time"] = pd.to_datetime(_left["time"])
            _h1m = pd.merge_asof(_left.sort_values("time"),
                                 _h1t[["vf", "buy_line", "sell_line", "flip"]].sort_values("vf"),
                                 left_on="time", right_on="vf", direction="backward")
            _buyL_h1  = _h1m["buy_line"].to_numpy()
            _sellL_h1 = _h1m["sell_line"].to_numpy()
            # 2026-06-27 Bug F: H1 flip too (live ratchet_htf_flip exits on the H1 flip,
            # not the M15 flip). Use it for the flip signal in htf mode below.
            _flip_h1  = _h1m["flip"].fillna(0).to_numpy()
        if args.ratchet_buf_mode == "band":
            print(f"⚡ RATCHET exit ON | buf=BAND×{args.ratchet_buf_mult} "
                  f"(SMMA2 band-adaptive) | TP cap {_TPCAP}% | flip {RATCHET_FLIP_EXIT}")
        else:
            print(f"⚡ RATCHET exit ON | buf {_BUFPCT}% (fixed) | "
                  f"TP cap {_TPCAP}% | flip-exit {RATCHET_FLIP_EXIT}")

    # ── ADX-DEATH exit precomputation ────────────────────────────────────
    _adx_death_env = os.environ.get("QGAI_ADX_DEATH")
    _adx_death_on = ((_adx_death_env is not None and _adx_death_env not in ("", "0"))
                     or getattr(CFG.filters, "adx_death_enabled", False))
    _adx_death_k = int(os.environ.get("QGAI_ADX_DEATH_K", 0) or getattr(CFG.filters, "adx_death_k", 3))
    _adx_death_n = int(os.environ.get("QGAI_ADX_DEATH_N", 0) or getattr(CFG.filters, "adx_death_n", 3))
    _adx_death_min_r = float(os.environ.get("QGAI_ADX_DEATH_MIN_R", 0) or getattr(CFG.filters, "adx_death_min_r", 0.5))
    _adx_falling_count = None
    if _adx_death_on:
        _adx_src = engine.adx_df.copy()
        _adx_src["datetime"] = pd.to_datetime(_adx_src["datetime"])
        _adx_merged = pd.merge_asof(
            ohlc[["datetime"]].reset_index(),
            _adx_src[["datetime", "M15_ADX", "M30_ADX", "H1_ADX", "H4_ADX"]].sort_values("datetime"),
            on="datetime", direction="backward"
        ).set_index("index").reindex(ohlc.index)
        _m15a = _adx_merged["M15_ADX"].to_numpy(dtype=float, na_value=np.nan)
        _m30a = _adx_merged["M30_ADX"].to_numpy(dtype=float, na_value=np.nan)
        _h1a  = _adx_merged["H1_ADX"].to_numpy(dtype=float, na_value=np.nan)
        _h4a  = _adx_merged["H4_ADX"].to_numpy(dtype=float, na_value=np.nan)
        _m15s = np.empty_like(_m15a); _m15s[0] = np.nan; _m15s[1:] = _m15a[1:] - _m15a[:-1]
        _m30s = np.full_like(_m30a, np.nan); _m30s[2:] = _m30a[2:] - _m30a[:-2]
        _h1s  = np.full_like(_h1a, np.nan);  _h1s[4:]  = _h1a[4:]  - _h1a[:-4]
        _h4s  = np.full_like(_h4a, np.nan);  _h4s[16:] = _h4a[16:] - _h4a[:-16]
        _valid = ~(np.isnan(_m15s) | np.isnan(_m30s) | np.isnan(_h1s) | np.isnan(_h4s))
        _adx_falling_count = np.full(len(ohlc), -1, dtype=int)
        _adx_falling_count[_valid] = ((_m15s[_valid] <= 0).astype(int)
                                      + (_m30s[_valid] <= 0).astype(int)
                                      + (_h1s[_valid] <= 0).astype(int)
                                      + (_h4s[_valid] <= 0).astype(int))
        print(f"⚡ ADX-DEATH exit ON | K={_adx_death_k} N={_adx_death_n} min_r={_adx_death_min_r}")

    print(f"Bars to replay : {len(idx_all):,}  ({args.date_from} → {args.date_to})")
    print(f"Start equity   : ${args.equity:,.2f} | risk/trade {args.risk}% | "
          f"spread ${args.spread:.2f} | max open {args.max_open}")
    print(f"⚠️  Remember: only bars AFTER the model's training cutoff are out-of-sample.")

    # 2. State ----------------------------------------------------------------
    equity        = args.equity
    day_open_eq   = equity
    day_peak_eq   = equity
    cur_day       = None
    daily_stopped = False
    open_trades   = []
    trades_out    = []
    signals_out   = []
    peak_eq       = equity
    max_dd        = 0.0
    k_start       = 0

    # ── Resume from checkpoint if one exists for this EXACT config ──────────
    if not getattr(args, "no_resume", False) and _checkpoint_pkl.exists():
        try:
            with open(_checkpoint_pkl, "rb") as _f:
                _ckpt = pickle.load(_f)
            if _ckpt.get("sig") == _resume_sig:
                k_start       = _ckpt["k"] + 1
                equity        = _ckpt["equity"]
                day_open_eq   = _ckpt["day_open_eq"]
                day_peak_eq   = _ckpt["day_peak_eq"]
                cur_day       = _ckpt["cur_day"]
                daily_stopped = _ckpt["daily_stopped"]
                open_trades   = _ckpt["open_trades"]
                trades_out    = _ckpt["trades_out"]
                signals_out   = _ckpt["signals_out"]
                peak_eq       = _ckpt["peak_eq"]
                max_dd        = _ckpt["max_dd"]
                print(f"↩️  RESUMING from checkpoint: bar {k_start:,}/{len(idx_all):,} "
                      f"| equity ${equity:,.2f} | {len(trades_out)} trades so far")
            else:
                print("⚠️  Checkpoint found but config differs (different args) — ignoring, starting fresh.")
        except Exception as _ce:
            print(f"⚠️  Checkpoint load failed ({_ce}) — starting fresh.")

    daily_sl_pct = args.daily_sl if args.daily_sl is not None else getattr(CFG.filters, "daily_loss_limit_pct", 8.0)
    daily_sl_pct = daily_sl_pct / 100.0 if daily_sl_pct > 1 else daily_sl_pct
    print(f"  Daily SL: {daily_sl_pct*100:.0f}%")

    def _save_checkpoint(k):
        try:
            tmp = _checkpoint_pkl.with_suffix(".pkl.tmp")
            with open(tmp, "wb") as _f:
                pickle.dump({
                    "sig": _resume_sig, "k": k, "equity": equity,
                    "day_open_eq": day_open_eq, "day_peak_eq": day_peak_eq,
                    "cur_day": cur_day, "daily_stopped": daily_stopped,
                    "open_trades": open_trades, "trades_out": trades_out,
                    "signals_out": signals_out, "peak_eq": peak_eq, "max_dd": max_dd,
                }, _f)
            tmp.replace(_checkpoint_pkl)   # atomic — never leaves a half-written checkpoint
        except Exception as _se:
            print(f"⚠️  Checkpoint save failed: {_se}")

    # Ctrl+C → save checkpoint + stop cleanly instead of losing all progress.
    # Flag-based (checked once per bar) rather than exception-based, so it can't land
    # mid-write of a trade/signal record and corrupt partial state.
    _stop_requested = {"v": False}
    def _on_sigint(signum, frame):
        _stop_requested["v"] = True
        print("\n⏸  Ctrl+C received — saving checkpoint at the next bar boundary, then stopping...")
    _prev_handler = signal.signal(signal.SIGINT, _on_sigint)

    n = len(idx_all)
    _idx_list = list(idx_all)
    import time as _time
    from datetime import timedelta as _td
    _bt_t0 = _time.time()          # ETA/timing (house rule 2026-07-02)
    _bt_k0 = k_start
    for k, i in zip(range(k_start, n), _idx_list[k_start:]):
        if _stop_requested["v"]:
            _save_checkpoint(k - 1)   # everything through bar k-1 is fully processed; bar k not yet started
            print(f"⏸  Stopped at bar {k:,}/{n:,} (checkpoint saved) — "
                  f"re-run the SAME command to resume from here.")
            signal.signal(signal.SIGINT, _prev_handler)
            sys.exit(130)
        if k > k_start and k % 500 == 0:
            _save_checkpoint(k - 1)   # state as of the end of the PREVIOUS bar (k-1 fully done)
        row = ohlc.iloc[i]
        ts  = row["datetime"]

        # next bar (execution bar) — must exist
        if i + 1 >= len(ohlc):
            break
        nxt = ohlc.iloc[i + 1]

        # ── daily reset / daily SL ───────────────────────────
        if cur_day != ts.date():
            cur_day       = ts.date()
            day_open_eq   = equity
            day_peak_eq   = equity          # ratchet: daily peak resets at day open
            daily_stopped = False
        day_peak_eq = max(day_peak_eq, equity)
        # RATCHET daily stop (2026-06-20): floor trails daily_sl_pct (of day-open)
        # below the day's PEAK equity. Loss-floor (-9% at open) + profit-lock
        # (peak +12% -> floor +3%). Matches bridge_session live logic.
        if equity <= day_peak_eq - day_open_eq * daily_sl_pct:
            daily_stopped = True

        # ── M3: %-based drawdown brake (no hard $ numbers) ───
        # dd>10% of peak → half size | >20% → quarter | >30% → halt
        dd_now = (peak_eq - equity) / peak_eq if peak_eq > 0 else 0.0
        risk_scale = 1.0
        if args.dd_brake:
            if   dd_now > 0.30: risk_scale = 0.0
            elif dd_now > 0.20: risk_scale = 0.25
            elif dd_now > 0.10: risk_scale = 0.50

        # ── manage open trades on THIS bar ───────────────────
        still_open = []
        for tr in open_trades:
            res = tr.update(ts, row["open"], row["high"], row["low"], row["close"])
            if res is None and _ratchet_on and tr.ratchet:
                if TRAIL_MODE == "htf":
                    _ln = _buyL_h1[i] if tr.s == 1 else _sellL_h1[i]
                    # H1 flip (matches live ratchet_htf_flip); fall back to M15 if missing
                    _flip_i = int(_flip_h1[i]) if _flip_h1 is not None else int(_flip[i])
                else:
                    _ln = _buyL[i] if tr.s == 1 else _sellL[i]
                    _flip_i = int(_flip[i])
                res = tr.ratchet_bar(ts, _ln, _flip_i, row["close"])
            if res is None and _adx_death_on and _adx_falling_count is not None:
                _fc = int(_adx_falling_count[i])
                if _fc < 0:
                    pass  # NaN bar — leave streak unchanged
                elif _fc >= _adx_death_k:
                    tr._adx_death_streak = getattr(tr, "_adx_death_streak", 0) + 1
                else:
                    tr._adx_death_streak = 0
                if tr._adx_death_streak >= _adx_death_n and tr._r(row["close"]) >= _adx_death_min_r:
                    res = tr._close(ts, row["close"], "ADX_DEATH")
            if res is None:
                still_open.append(tr)
            else:
                equity += res["pnl_usd"]
                rec = {
                    "entry_time":  tr.entry_time, "exit_time": res["exit_time"],
                    "direction":   tr.direction,
                    "entry_price": round(tr.entry, 2), "exit_price": res["exit_price"],
                    "price_move":  round((res["exit_price"] - tr.entry) * tr.s, 2),  # actual $ gold move captured (BUY: exit-entry, SELL: entry-exit)
                    "sl_price":    round(tr.entry - tr.s * tr.sl_dist, 2),
                    "tp1_price":   round(tr.tp1, 2) if tr.tp1 is not None else None,
                    "tp2_price":   round(tr.tp2, 2) if tr.tp2 is not None else None,
                    "sl_dist":     round(tr.sl_dist, 2),
                    "risk_usd":    round(tr.risk_usd, 2),
                    "exit_reason": res["exit_reason"],
                    "r_achieved":  res["r_achieved"], "peak_r": res["peak_r"],
                    "pnl_usd":     res["pnl_usd"],
                    "equity_after": round(equity, 2),
                    "win_prob":    tr.sig.get("win_prob"), "state_prob": tr.sig.get("state_prob"),
                    "dir_prob":    tr.sig.get("dir_prob"), "hmm_state": tr.sig.get("hmm_state"),
                    "sl_mult":     tr.sig.get("sl_multiplier"), "tp_mult": tr.sig.get("tp_multiplier"),
                    "reason":      tr.sig.get("reason", ""),
                }
                for fk, fv in tr.features.items():           # full 55-feature snapshot
                    rec[f"f_{fk}"] = fv
                trades_out.append(rec)
        open_trades = still_open
        peak_eq = max(peak_eq, equity)
        max_dd  = max(max_dd, (peak_eq - equity) / peak_eq if peak_eq > 0 else 0)

        # ── AI decision at bar close (mirror of bridge_main) ─
        try:
            engine.update_capital(equity)
            rb = engine.get_signal(timestamp=ts, trade_type="BUY",  volume=0.10)
            rs = engine.get_signal(timestamp=ts, trade_type="SELL", volume=0.10)
        except Exception as e:
            signals_out.append({"bar_time": ts, "signal": "ERROR", "reason": str(e)[:120]})
            continue
        # FAB-M11 (2026-07-07): prefer any actionable BUY/SELL over a higher-prob
        # SKIP — mirror of bridge_main picker for live==backtest parity.
        _rb_act = rb.get("signal") in ("BUY", "SELL")
        _rs_act = rs.get("signal") in ("BUY", "SELL")
        if _rb_act and not _rs_act:
            sig = rb
        elif _rs_act and not _rb_act:
            sig = rs
        else:
            sig = rb if rb.get("win_prob", 0) >= rs.get("win_prob", 0) else rs
        # 2026-07-03 (Divyesh) direction-swap log FIX: take the WINNING direction's
        # own feature dict (old code took engine._last_features = always the last
        # evaluated = SELL → BUY trades logged SELL features in the f_* columns).
        # Decisions/probabilities were always correct — this corrupted ONLY the
        # logged analysis columns.
        # GENERATE early trend-pullback entry (ET1 v2) — SAME shared function as live.
        # If ML SKIPs but the dominant HTF trend is aligned and price pulled back to
        # the line, create the entry now (early) instead of waiting for the late signal.
        if sig.get("signal") == "SKIP":
            try:
                _gen = trend_pullback_generate(rb, CFG)
                if _gen in ("BUY", "SELL"):
                    sig = rb if _gen == "BUY" else rs
                    sig["signal"] = _gen
                    sig["reason"] = "GEN: trend-pullback early entry"
            except Exception:
                pass

        # ── SHADOW-SKIP TRADE SIMULATION (missed-profit quantification) ─────
        # Imtiyaz's follow-up (2026-07-14) to the HTF-alignment skip-rate diagnostic:
        # "of the trades we did NOT take, how many would have been profitable?"
        # Env-gated (QGAI_SHADOW_SKIPS unset/empty = zero change to normal behavior,
        # exact original code path below runs untouched).
        # When set to "strong" (4/4 HTF agreement), "weak" (3/4), or "both" (>=3/4),
        # EVERY bar's decision this run is REPLACED by a pure counterfactual:
        #   - if the bar's 4 HTF-direction signals (H1/H4 ADX-DI + H1/H4 SMMA-trend,
        #     same 4 signals as diagnose_htf_alignment_skip_rate.py) agree strongly
        #     enough to match the requested bucket -> FORCE a trade in that direction,
        #     bypassing the model's win_prob gate AND all soft filters (range/ctf/
        #     pullback/smma/adx) -- this measures "if we traded HTF-alignment
        #     regardless of the model's confidence", not a filter A/B.
        #   - otherwise -> SUPPRESS to SKIP (including the model's OWN real BUY/SELL
        #     signals) so this run's total R is 100% attributable to bars the REAL
        #     model actually skipped -- comparable directly against 0 (no missed
        #     profit) rather than mixed with real-trade P&L.
        # Same SL/TP/trailing/ratchet simulation as every other trade below --
        # only the entry gate is bypassed. READ-ONLY diagnostic, no live impact.
        _shadow_mode = os.environ.get("QGAI_SHADOW_SKIPS", "").strip().lower()
        if _shadow_mode:
            _was_real_trade = sig.get("signal") in ("BUY", "SELL")
            _h1v = float(rb.get("H1_DI_diff", 0) or 0)
            _h4v = float(rb.get("H4_DI_diff", 0) or 0)
            _t1v = float(rb.get("ts_trend_h1", 0) or 0)
            _t4v = float(rb.get("ts_trend_h4", 0) or 0)
            _votes = [1 if _h1v > 0 else (-1 if _h1v < 0 else 0),
                      1 if _h4v > 0 else (-1 if _h4v < 0 else 0),
                      1 if _t1v > 0 else (-1 if _t1v < 0 else 0),
                      1 if _t4v > 0 else (-1 if _t4v < 0 else 0)]
            _buy_n  = sum(1 for v in _votes if v > 0)
            _sell_n = sum(1 for v in _votes if v < 0)
            _cdir   = "BUY" if _buy_n > _sell_n else ("SELL" if _sell_n > _buy_n else None)
            _strength = max(_buy_n, _sell_n)
            _bucket_ok = ((_shadow_mode == "both" and _strength >= 3)
                          or (_shadow_mode == "strong" and _strength == 4)
                          or (_shadow_mode == "weak" and _strength == 3))
            if (not _was_real_trade) and _cdir is not None and _bucket_ok:
                sig = dict(rb if _cdir == "BUY" else rs)
                sig["signal"] = _cdir
                sig["reason"] = f"SHADOW forced-skip (HTF {_strength}/4 {_cdir})"
            else:
                sig = dict(sig)
                sig["signal"] = "SKIP"
                sig["reason"] = ("SHADOW: real trade suppressed" if _was_real_trade
                                  else "SHADOW: not a qualifying skip")

        # ── FIX-3 (2026-07-07): model LIVE opposite-signal reversal-close ──────
        # Live bridge_core.handle_opposite_signal closes an open trade EARLY when
        # the new signal is opposite: in LOSS → exit if new_prob≥0.45; in PROFIT →
        # exit if new_prob≥0.60. The backtest never did this → a major source of the
        # 12% live-overlap gap (live cuts trades the backtest holds to SL/TP/flip).
        # Flag-gated: QGAI_BT_REVERSAL=1 (default OFF → baseline +444.7R unchanged).
        _bt_rev_env = os.environ.get("QGAI_BT_REVERSAL")
        _bt_reversal = (_bt_rev_env is not None and _bt_rev_env not in ("", "0"))
        if _bt_reversal and sig.get("signal") in ("BUY", "SELL") and open_trades:
            _new_dir = sig["signal"]
            _new_prob = float(sig.get("win_prob", 0) or 0)
            _LOSS_TH, _WIN_TH = 0.45, 0.60
            _kept = []
            for _tr in open_trades:
                if _tr.direction == _new_dir:
                    _kept.append(_tr); continue          # same dir — not opposite
                _cur = float(row["close"])
                _in_profit = (_cur > _tr.entry) if _tr.direction == "BUY" else (_cur < _tr.entry)
                _do_exit = ((not _in_profit and _new_prob >= _LOSS_TH)
                            or (_in_profit and _new_prob >= _WIN_TH))
                if not _do_exit:
                    _kept.append(_tr); continue
                _res = _tr._close(ts, _cur, "REVERSAL")
                equity += _res["pnl_usd"]
                trades_out.append({
                    "entry_time":  _tr.entry_time, "exit_time": _res["exit_time"],
                    "direction":   _tr.direction,
                    "entry_price": round(_tr.entry, 2), "exit_price": _res["exit_price"],
                    "price_move":  round((_res["exit_price"] - _tr.entry) * _tr.s, 2),
                    "sl_price":    round(_tr.entry - _tr.s * _tr.sl_dist, 2),
                    "tp1_price":   round(_tr.tp1, 2) if _tr.tp1 is not None else None,
                    "tp2_price":   round(_tr.tp2, 2) if _tr.tp2 is not None else None,
                    "sl_dist":     round(_tr.sl_dist, 2),
                    "risk_usd":    round(_tr.risk_usd, 2),
                    "exit_reason": "REVERSAL",
                    "r_achieved":  _res["r_achieved"], "peak_r": _res["peak_r"],
                    "pnl_usd":     _res["pnl_usd"],
                    "equity_after": round(equity, 2),
                    "win_prob":    _tr.sig.get("win_prob"),
                    "hmm_state":   _tr.sig.get("hmm_state", ""),
                })
            open_trades = _kept
            peak_eq = max(peak_eq, equity)
            max_dd  = max(max_dd, (peak_eq - equity) / peak_eq if peak_eq > 0 else 0)

        if sig.get("signal") == "BUY":
            feats = dict(getattr(engine, "_last_features_buy", None)
                         or getattr(engine, "_last_features", {}) or {})
        else:
            feats = dict(getattr(engine, "_last_features_sell", None)
                         or getattr(engine, "_last_features", {}) or {})

        # ── open trade at NEXT bar open ──────────────────────
        # H4 RANGE-PHASE ENTRY FILTER — REMOVED 2026-07-12 (Imtiyaz): "model over
        # hard filters". 1-month honest A/B: OFF +8.9R/63tr vs ON +0.9R/29tr — the
        # filter was blocking WINNERS (WR 60.3% > 55.2%). The old -43R was in-sample
        # on the leaky model. Kept as a False constant so downstream compound
        # conditions (not _range_block ...) and the blocked_by taxonomy are untouched.
        # REVERT: restore the _range_on / in_range_phase gate here (git history).
        _range_block = False
        # Counter-trend-FADE filter: block a trade AGAINST the dominant timeframe's
        # momentum (H1/H4 — whichever ADX is higher) when that dominant ADX slope is
        # falling (trend real but fading = whipsaw zone). Data: in-sample +15R, PF 1.74→1.89.
        _ctf_block = False
        # Env override precedence: QGAI_CTF_FADE=1/0 wins over config+CLI (A/B testing).
        _ctf_env = os.environ.get("QGAI_CTF_FADE")
        if _ctf_env is not None and _ctf_env != "":
            try:
                _ctf_on = float(_ctf_env) >= 0.5
            except ValueError:
                _ctf_on = getattr(CFG.filters, "skip_counter_trend_fade", False) or getattr(args, "ctf_fade", False)
        else:
            _ctf_on = getattr(CFG.filters, "skip_counter_trend_fade", False) or getattr(args, "ctf_fade", False)
        if _ctf_on and sig.get("signal") in ("BUY", "SELL"):
            try:
                _h1a = float(sig.get("H1_ADX", 0) or 0); _h4a = float(sig.get("H4_ADX", 0) or 0)
                _uh4 = _h4a >= _h1a
                _ddi = float(sig.get("H4_DI_diff", 0) or 0) if _uh4 else float(sig.get("H1_DI_diff", 0) or 0)
                _dsl = float(sig.get("h4_adx_slope", 0) or 0) if _uh4 else float(sig.get("h1_adx_slope", 0) or 0)
                _md  = 1 if _ddi > 0 else (-1 if _ddi < 0 else 0)
                _wd  = 1 if sig["signal"] == "BUY" else -1
                if _md != 0 and _md != _wd and _dsl <= 0:
                    _ctf_block = True
            except Exception:
                _ctf_block = False

        # Trend-following PULLBACK entry gate (ET1) — SAME shared function as live
        # bridge_main → parity by construction. Env/config-gated (default OFF).
        _pb_block, _pb_reason = False, ""
        if not _range_block and not _ctf_block:
            try:
                _pb_block, _pb_reason = trend_pullback_block(sig, CFG)
            except Exception:
                _pb_block, _pb_reason = False, ""

        # SMMA MTF soft gate — SAME shared function as live bridge_main → parity.
        _smma_block, _smma_reason, _smma_meta = False, "", {"score":0.0,"required_threshold":0.0,"penalty":0.0}
        if not _range_block and not _ctf_block and not _pb_block:
            try:
                _base_th = float(sig.get("effective_threshold", CFG.filters.min_win_prob))
                _smma_block, _smma_reason, _smma_meta = smma_mtf_soft_block(sig, _base_th, CFG)
            except Exception:
                _smma_block, _smma_reason = False, ""

        # ADX STRENGTH soft gate (Fable-5 redesign, direction-agnostic).
        # ADDITIVE penalty on top of SMMA — combined_required = base + smma_pen + adx_pen,
        # capped at total_penalty ≤ 0.08 and absolute required ≤ 0.60 (Fable safeguards).
        _adx_block, _adx_reason, _adx_meta = False, "", {"score":0.0,"required_threshold":0.0,"penalty":0.0}
        if not _range_block and not _ctf_block and not _pb_block and not _smma_block:
            try:
                _base_th = float(sig.get("effective_threshold", CFG.filters.min_win_prob))
                _adx_block, _adx_reason, _adx_meta = adx_strength_soft_block(sig, _base_th, CFG)
                # additive stack: recompute required with SMMA + ADX combined, capped
                _smma_pen = float(_smma_meta.get("penalty", 0) or 0)
                _adx_pen  = float(_adx_meta.get("penalty", 0) or 0)
                _total_pen = min(0.08, _smma_pen + _adx_pen)
                _combined_req = min(0.60, _base_th + _total_pen)
                if _combined_req > _base_th and float(sig.get("win_prob", 0) or 0) < _combined_req:
                    _adx_block, _adx_reason = True, f"combined SMMA+ADX gate: total_pen {_total_pen:.4f}; prob {float(sig.get('win_prob',0)):.2%} < {_combined_req:.2%}"
            except Exception:
                _adx_block, _adx_reason = False, ""

        # record EVERY signal (incl. SKIP + which filter blocked it — for auditing the CSV)
        signals_out.append({
            "bar_time": ts, "signal": sig.get("signal", "SKIP"),
            "win_prob": sig.get("win_prob"), "state_prob": sig.get("state_prob"),
            "dir_prob": sig.get("dir_prob"), "hmm_state": sig.get("hmm_state"),
            "atr20_pct": sig.get("atr20_pct"),
            "blocked_by": ("range" if _range_block else "ctf_fade" if _ctf_block
                           else "pullback" if _pb_block
                           else "smma_mtf" if _smma_block
                           else "adx_strength" if _adx_block else ""),
            "smma_score": _smma_meta.get("score", 0),
            "smma_required_threshold": _smma_meta.get("required_threshold", 0),
            "adx_strength_score": _adx_meta.get("score", 0),
            "adx_strength_penalty": _adx_meta.get("penalty", 0),
            "effective_threshold": sig.get("effective_threshold", 0),
            "in_range_phase": sig.get("in_range_phase", 0),
            "H1_ADX": sig.get("H1_ADX", 0), "H4_ADX": sig.get("H4_ADX", 0),
            "H1_DI_diff": sig.get("H1_DI_diff", 0), "H4_DI_diff": sig.get("H4_DI_diff", 0),
            "h1_adx_slope": sig.get("h1_adx_slope", 0), "h4_adx_slope": sig.get("h4_adx_slope", 0),
            "ts_line_dist_pct": sig.get("ts_line_dist_pct", 0),
            "ts_htf_agreement": sig.get("ts_htf_agreement", 0),
            "ts_adx_switch_trend": sig.get("ts_adx_switch_trend", 0),
            "reason": (_adx_reason or _smma_reason or _pb_reason or sig.get("reason", ""))[:140],
        })

        if (sig.get("signal") in ("BUY", "SELL")
                and len(open_trades) < args.max_open
                and not daily_stopped
                and not _range_block
                and not _ctf_block
                and not _pb_block
                and not _smma_block
                and not _adx_block):
            direction = sig["signal"]
            s = 1 if direction == "BUY" else -1
            _pred_ok = direction in args.pred_dirs.upper().split(",")
            if args.runner == "trail" and _pred_ok:
                sig["_runner_trail"] = True
            # ── RATCHET SL sizing (pure ratchet — no ATR fallback) ──
            _r_trade, _r_buf, _buf_pct = False, 0.0, 0.0
            if _ratchet_on:
                # 2026-06-27 Bug J fix: match LIVE entry SL. When HTF SL is on, live
                # execute() sizes the ENTRY SL off the H1 line (ratchet_htf_sl=True),
                # so the backtest must too — else lot/risk differ from live. M15 fallback
                # if the H1 line is missing; use the wider HTF max-risk cap (2.5%).
                if TRAIL_MODE == "htf" and _buyL_h1 is not None:
                    _ln0 = _buyL_h1[i] if s == 1 else _sellL_h1[i]
                    if _ln0 is None or np.isnan(_ln0):
                        _ln0 = _buyL[i] if s == 1 else _sellL[i]
                    _entry_max_pct = getattr(CFG.filters, "ratchet_htf_max_risk_pct", 2.5)
                else:
                    _ln0 = _buyL[i] if s == 1 else _sellL[i]
                    _entry_max_pct = RATCHET_MAX_RISK_PCT
                if _ln0 is not None and not np.isnan(_ln0):
                    if args.ratchet_buf_mode == "band":
                        _bp = _bandpct[i]
                        if np.isnan(_bp) or _bp <= 0:
                            _bp = _BUFPCT / args.ratchet_buf_mult  # fallback → ~fixed
                        _buf_pct = _bp * args.ratchet_buf_mult
                    else:
                        _buf_pct = _BUFPCT
                    _r_buf = round(nxt["open"] * _buf_pct / 100.0, 2)
                    _vsl0  = _ln0 - s * _r_buf
                    _d0    = round((nxt["open"] - _vsl0) * s, 2)
                    _max0  = nxt["open"] * _entry_max_pct / 100.0
                    _min0  = nxt["open"] * CFG.filters.ratchet_sl_min_pct / 100.0  # matches live bridge (was hardcoded $8)
                    if _min0 <= _d0 <= _max0:
                        sl_dist = _d0
                        # regime-adaptive TP: switch cap on the trade's HMM state at entry
                        _tpcap_use = _TP_BY_REGIME.get(sig.get("hmm_state", ""), _TPCAP) \
                                     if args.tp_regime else _TPCAP
                        sig["_tp1_dist"] = nxt["open"] * _tpcap_use / 100.0
                        sig["_tp2_dist"] = sig["_tp1_dist"]
                        _r_trade = True
            # Pure ratchet: skip if no valid ratchet line (no ATR fallback)
            if _ratchet_on and not _r_trade:
                continue
            if not _ratchet_on:
                sl_dist = nxt["open"] * (getattr(CFG.filters, "ratchet_sl_min_pct", 0.3) / 100.0)
            entry = round(nxt["open"] + s * args.spread, 2)    # spread charged at entry
            # M3: fixed-lot mode — 0.01 lot gold = 1 oz = $1 per $1 move,
            # so $ risked = lot × 100 × sl_dist. Matches live use_fixed_lot.
            if args.fixed_lot > 0:
                risk_usd = args.fixed_lot * 100.0 * sl_dist
            else:
                risk_usd = equity * args.risk / 100.0 * risk_scale
            # broker max-lot cap: lot = risk_usd / (100 * sl_dist); cap it
            if args.max_lot > 0 and sl_dist > 0:
                _lot = risk_usd / (100.0 * sl_dist)
                if _lot > args.max_lot:
                    risk_usd = args.max_lot * 100.0 * sl_dist  # capped lot
            if risk_usd <= 0:
                continue
            # M1: predicted-TP mode — TP1 = P50 move, TP2 = P75 move (in $),
            # with sanity floors so TPs never sit inside the spread/noise.
            if args.tp_mode in ("predicted", "hybrid") and _pred_ok and sig.get("pred_move_p50_atr"):
                atr_usd = (sig.get("atr20_pct") or 0.2) / 100.0 * nxt["open"]
                tp1d = max(0.6 * sl_dist, sig["pred_move_p50_atr"] * atr_usd)
                if args.tp_mode == "predicted":
                    tp2d = max(tp1d * 1.2, sig.get("pred_move_p75_atr", 0) * atr_usd)
                else:           # hybrid: partial at P50, runner UNCAPPED — trail decides
                    tp2d = 1e9
                sig["_tp1_dist"], sig["_tp2_dist"] = round(tp1d, 2), round(tp2d, 2)
            _st_obj = SimTrade(direction, nxt["datetime"], entry,
                                        sl_dist, risk_usd, sig, feats,
                ratchet=_r_trade, ratchet_buf=_r_buf, ratchet_buf_pct=_buf_pct)
            # equity-based TP: store $ profit target = equity% at entry
            if args.tp_equity_pct is not None and args.tp_equity_pct > 0:
                _st_obj.tp_equity_usd = equity * args.tp_equity_pct / 100.0
            open_trades.append(_st_obj)

        if (k + 1) % 100 == 0 or k == n - 1:
            _pct = (k + 1) / n * 100
            # ETA/timing (house rule): elapsed + rate + est. remaining + finish HH:MM
            _el = _time.time() - _bt_t0
            _done = (k + 1) - _bt_k0
            _rate = _done / _el if _el > 0 else 0            # bars/sec
            _left = (n - (k + 1)) / _rate if _rate > 0 else 0
            _eta = (datetime.now() + _td(seconds=_left)).strftime("%H:%M")
            print(f"  {k+1:>6}/{n} bars ({_pct:5.1f}%) | {ts} | equity ${equity:,.2f} | "
                  f"trades {len(trades_out)} | open {len(open_trades)} | "
                  f"⏱ {_el/60:.1f}m elapsed | ~{_left/60:.0f}m left | ETA {_eta}", flush=True)

    # Loop completed normally (not interrupted) — restore the default Ctrl+C behavior
    # and delete the checkpoint so a future run of this SAME config starts fresh
    # instead of "resuming" past a run that already finished.
    signal.signal(signal.SIGINT, _prev_handler)
    try:
        if _checkpoint_pkl.exists():
            _checkpoint_pkl.unlink()
    except Exception:
        pass

    # force-close anything still open at last price
    if open_trades:
        last = ohlc.iloc[min(idx_all[-1] + 1, len(ohlc) - 1)]
        for tr in open_trades:
            res = tr._close(last["datetime"], last["close"], "EOD")
            equity += res["pnl_usd"]
            rec = {
                "entry_time":  tr.entry_time, "exit_time": res["exit_time"],
                "direction":   tr.direction,
                "entry_price": round(tr.entry, 2), "exit_price": res["exit_price"],
                "price_move":  round((res["exit_price"] - tr.entry) * tr.s, 2),
                "sl_price":    round(tr.entry - tr.s * tr.sl_dist, 2),
                "tp1_price":   round(tr.tp1, 2) if tr.tp1 is not None else None,
                "tp2_price":   round(tr.tp2, 2) if tr.tp2 is not None else None,
                "sl_dist":     round(tr.sl_dist, 2),
                "risk_usd":    round(tr.risk_usd, 2),
                "exit_reason": "EOD",
                "r_achieved":  res["r_achieved"], "peak_r": res["peak_r"],
                "pnl_usd":     res["pnl_usd"],
                "equity_after": round(equity, 2),
                "win_prob":    tr.sig.get("win_prob"), "state_prob": tr.sig.get("state_prob"),
                "dir_prob":    tr.sig.get("dir_prob"), "hmm_state": tr.sig.get("hmm_state"),
                "sl_mult":     tr.sig.get("sl_multiplier"), "tp_mult": tr.sig.get("tp_multiplier"),
                "reason":      tr.sig.get("reason", ""),
            }
            for fk, fv in tr.features.items():
                rec[f"f_{fk}"] = fv
            trades_out.append(rec)

    # 3. Save -----------------------------------------------------------------
    LOGS.mkdir(exist_ok=True)
    tdf = pd.DataFrame(trades_out)
    sdf = pd.DataFrame(signals_out)
    _suffix = "" if (args.tp_mode, args.sl_mode, args.trail_mode) == ("fixed",)*3 else \
        f"_{args.tp_mode[0]}tp_{args.sl_mode[0]}sl_{args.trail_mode[0]}tr"
    # Unique CSV per stop-trail mode → safe to run all modes in PARALLEL (no file clobber).
    _st = TRAIL_MODE   # the RESOLVED mode (config-aware default), not the raw arg
    if _st != "line":
        _suffix += f"_st-{_st}"
    tdf.to_csv(LOGS / f"backtest_trades{_suffix}.csv", index=False)
    sdf.to_csv(LOGS / f"backtest_signals{_suffix}.csv", index=False)

    # 4. Report ----------------------------------------------------------------
    rep = []
    rep.append("=" * 64)
    rep.append("⚡ QGAI AI REPLAY BACKTEST — REPORT")
    rep.append(f"Period         : {args.date_from} → {args.date_to}")
    rep.append(f"Modes          : TP={args.tp_mode} | SL={args.sl_mode} | trail={args.trail_mode} | runner={args.runner} | pred dirs={args.pred_dirs}")
    _shadow_env = os.environ.get("QGAI_SHADOW_SKIPS", "").strip().lower()
    if _shadow_env:
        rep.append(f"⚠ SHADOW-SKIPS MODE = '{_shadow_env}' — R below is COUNTERFACTUAL missed-profit")
        rep.append(f"  from bars the REAL model skipped, NOT a real/tradeable result. Real trades suppressed.")
    if args.fixed_lot > 0:
        rep.append(f"Sizing         : FIXED LOT {args.fixed_lot} (no compounding)")
    elif args.max_lot > 0:
        rep.append(f"Sizing         : {args.risk}% compounding, CAPPED at {args.max_lot} lots (realistic)")
    rep.append(f"Bars replayed  : {len(sdf):,} | Signals BUY/SELL: "
               f"{(sdf['signal'].isin(['BUY','SELL'])).sum() if len(sdf) else 0}")
    rep.append("=" * 64)
    if len(tdf):
        wins   = tdf[tdf.pnl_usd > 0]
        losses = tdf[tdf.pnl_usd <= 0]
        pf     = wins.pnl_usd.sum() / abs(losses.pnl_usd.sum()) if len(losses) and losses.pnl_usd.sum() != 0 else float("inf")
        rep.append(f"Trades         : {len(tdf)}  (W {len(wins)} / L {len(losses)})")
        rep.append(f"Win rate       : {len(wins)/len(tdf)*100:.1f}%")
        rep.append(f"Profit factor  : {pf:.2f}")
        rep.append(f"Avg R          : {tdf.r_achieved.mean():+.3f}  |  Total: {tdf.r_achieved.sum():+.1f}R")
        rep.append(f"Price move ($) : Total {tdf.price_move.sum():+,.1f} | avg {tdf.price_move.mean():+.2f}/trade  (gold points entry->exit, lot-independent)")
        try:
            _win = ohlc.loc[list(idx_all)]
            _avail_path = float(_win["close"].diff().abs().sum())
            _avail_net  = abs(float(_win["close"].iloc[-1] - _win["close"].iloc[0]))
            _cap = float(tdf.price_move.sum())
            _eff = 100 * _cap / _avail_path if _avail_path > 0 else 0.0
            rep.append(f"Captured/Avail : captured {_cap:+,.0f} pts | available {_avail_path:,.0f} pts (all swings) / {_avail_net:,.0f} net | efficiency {_eff:.1f}% of path")
        except Exception as _ce:
            rep.append(f"Captured/Avail : (n/a: {_ce})")
        rep.append(f"Net return     : {(equity/args.equity-1)*100:+.2f}%  (risk {args.risk}%/trade)")
        rep.append(f"Max drawdown   : {max_dd*100:.1f}%")
        rep.append(f"Avg win        : {wins.r_achieved.mean():+.2f}R | Avg loss: {losses.r_achieved.mean():+.2f}R")
        rep.append(f"Exit reasons   : {tdf.exit_reason.value_counts().to_dict()}")
        rep.append("-" * 64)
        rep.append("BY REGIME (R = movement relative to risk):")
        for st, g in tdf.groupby("hmm_state"):
            wr = (g.r_achieved > 0).mean() * 100
            rep.append(f"  {st:<10} {len(g):>4} trades | WR {wr:5.1f}% | {g.r_achieved.sum():>+8.1f}R | avg {g.r_achieved.mean():+.3f}R")
        rep.append("BY HOUR (entry):")
        hh = pd.to_datetime(tdf.entry_time).dt.hour
        for h, g in tdf.groupby(hh):
            wr = (g.r_achieved > 0).mean() * 100
            rep.append(f"  {h:02d}:00      {len(g):>4} trades | WR {wr:5.1f}% | {g.r_achieved.sum():>+8.1f}R")
        rep.append("BY MONTH:")
        mm = pd.to_datetime(tdf.entry_time).dt.to_period("M")
        for m, g in tdf.groupby(mm):
            rep.append(f"  {m}    {len(g):>4} trades | {g.r_achieved.sum():>+8.1f}R | avg {g.r_achieved.mean():+.3f}R")
    else:
        rep.append("No trades opened in this period (all signals SKIP).")
        if len(sdf):
            rep.append(f"Avg win_prob of bars: {pd.to_numeric(sdf.win_prob, errors='coerce').mean():.2%}")
    rep.append("=" * 64)
    try:
        _bt_total = _time.time() - _bt_t0
        rep.append(f"⏱ DONE — run time {_bt_total/60:.1f} min ({n:,} bars) | "
                   f"finished {datetime.now().strftime('%H:%M:%S')}")
    except Exception:
        pass
    rep.append("Files: logs/backtest_trades.csv (with f_* feature columns), "
               "logs/backtest_signals.csv")
    report = "\n".join(rep)
    (LOGS / "backtest_report.txt").write_text(report, encoding="utf-8")
    print("\n" + report)

    # 2026-07-02 (Divyesh) RULE: EVERY backtest — via bat OR direct CLI — also
    # saves its result as CSV in the SAME output folder as the rest of the run
    # (trades/signals/report), so one folder holds everything. Excel-ready.
    try:
        import csv as _csv
        with open(LOGS / f"backtest_summary{_suffix}.csv", "w", newline="",
                  encoding="utf-8-sig") as _fs:
            _w = _csv.writer(_fs)
            _w.writerow(["from", "to", "trades", "wins", "losses", "wr_pct", "pf",
                         "avg_r", "total_r", "net_return_pct", "max_dd_pct",
                         "tp_mode", "sl_mode", "trail_mode", "fixed_lot", "risk_pct"])
            if len(tdf):
                _wins   = tdf[tdf.pnl_usd > 0]
                _losses = tdf[tdf.pnl_usd <= 0]
                _pf = (_wins.pnl_usd.sum() / abs(_losses.pnl_usd.sum())
                       if len(_losses) and _losses.pnl_usd.sum() != 0 else float("inf"))
                _w.writerow([args.date_from, args.date_to, len(tdf), len(_wins), len(_losses),
                             round(len(_wins) / len(tdf) * 100, 1),
                             (round(_pf, 2) if _pf != float("inf") else "inf"),
                             round(tdf.r_achieved.mean(), 3), round(tdf.r_achieved.sum(), 1),
                             round((equity / args.equity - 1) * 100, 2), round(max_dd * 100, 1),
                             args.tp_mode, args.sl_mode, TRAIL_MODE, args.fixed_lot, args.risk])
                _w.writerow([])
                _w.writerow(["BY_REGIME", "trades", "wr_pct", "total_r", "avg_r"])
                for _st_name, _g in tdf.groupby("hmm_state"):
                    _w.writerow([_st_name, len(_g), round((_g.r_achieved > 0).mean() * 100, 1),
                                 round(_g.r_achieved.sum(), 1), round(_g.r_achieved.mean(), 3)])
            else:
                _w.writerow([args.date_from, args.date_to, 0, 0, 0, "", "", "", 0, "", "",
                             args.tp_mode, args.sl_mode, TRAIL_MODE, args.fixed_lot, args.risk])
        print(f"Saved: {LOGS / ('backtest_summary' + _suffix + '.csv')}")
    except Exception as _se:
        print(f"  (could not write backtest_summary CSV: {_se})")


# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="QGAI AI replay backtest")
    ap.add_argument("--from",    dest="date_from", required=True, help="start date YYYY-MM-DD")
    ap.add_argument("--to",      dest="date_to",   required=True, help="end date YYYY-MM-DD")
    ap.add_argument("--equity",  type=float, default=2500.0, help="starting equity $")
    ap.add_argument("--risk",    type=float, default=CFG.filters.risk_pct * 100
                    if CFG.filters.risk_pct < 1 else CFG.filters.risk_pct,
                    help="risk %% per trade (default from config)")
    ap.add_argument("--spread",  type=float, default=0.13, help="spread in $ (13 pts = 0.13)")
    ap.add_argument("--ratchet", choices=["auto", "on", "off"], default="auto",
                    help="RATCHET exit mode: auto=config flag, on/off=force")
    ap.add_argument("--ratchet-buf-mode", choices=["pct", "band"], default="pct",
                    help="pct=fixed RATCHET_BUF_PCT; band=SMMA2 band-width adaptive")
    ap.add_argument("--ratchet-buf-mult", type=float, default=0.50,
                    help="multiplier for band mode: buffer = band_width%% * mult")
    ap.add_argument("--ratchet-buf-pct", type=float, default=None,
                    help="override fixed buffer %% (e.g. 0.06, 0.21); default uses config value")
    ap.add_argument("--daily-sl", type=float, default=None,
                    help="override daily SL %% (e.g. 6, 7, 8); default uses config value")
    ap.add_argument("--tp-cap", type=float, default=None,
                    help="override ratchet TP cap %% (e.g. 1.0, 1.5, 2.0); default uses config value")
    ap.add_argument("--tp-regime", action="store_true",
                    help="REGIME-ADAPTIVE TP cap: pick TP%% by HMM state at entry "
                         "(Ranging 2.0 / Trending 1.0 / Volatile 0.8 — from 13-TP sweep). "
                         "Overrides --tp-cap per trade. Unknown state falls back to --tp-cap/config.")
    ap.add_argument("--skip-counter-trend", action="store_true",
                    help="skip trades where ratchet line unavailable (no ATR fallback). Pure ratchet only.")
    # --no-range-skip REMOVED 2026-07-12 (range filter deleted; arg no longer used).
    ap.add_argument("--ctf-fade", action="store_true",
                    help="counter-trend-FADE filter: block a trade against the dominant TF (higher ADX) "
                         "momentum when that ADX slope is falling. Overrides config skip_counter_trend_fade=True.")
    ap.add_argument("--tp-equity-pct", type=float, default=None,
                    help="equity-based TP: close when trade profit reaches this %% of current equity (e.g. 2,3,4). Replaces price-based TP cap.")
    ap.add_argument("--max-open", type=int, default=1, help="max concurrent trades")
    ap.add_argument("--tp-mode", choices=["fixed", "predicted", "hybrid"], default="fixed",
                    help="fixed = live 1.5R/3R | predicted = P50/P75 TPs | "
                         "hybrid = P50 partial + uncapped trailing runner")
    ap.add_argument("--sl-mode", choices=["fixed", "predicted"], default="fixed",
                    help="fixed = ATR SL | predicted = MAE-model SL (P75 + 10%% buffer)")
    ap.add_argument("--trail-mode", choices=["fixed", "predicted"], default="fixed",
                    help="fixed = 0.75xSL trail | predicted = MAE-P50 trail")
    ap.add_argument("--runner", choices=["target", "trail"], default="target",
                    help="runner exit: target = TP2 price (P75/3R) | trail = no TP2, ride with trailing")
    ap.add_argument("--pred-dirs", default="BUY,SELL",
                    help="directions allowed to use predicted geometry, e.g. BUY (SELL keeps fixed rules)")
    ap.add_argument("--dd-brake", action="store_true",
                    help="%%-based drawdown brake: dd>10%%=half size, >20%%=quarter, >30%%=halt")
    ap.add_argument("--fixed-lot", type=float, default=0.0,
                    help="fixed lot mode, e.g. 0.01 (0 = use --risk %% sizing)")
    ap.add_argument("--max-lot", type=float, default=0.0,
                    help="cap lot size (broker max), e.g. 50. 0 = no cap. Realistic compounding.")
    ap.add_argument("--no-trail", action="store_true",
                    help="flip-only: disable the upward stop-trail (removes TRAIL exits)")
    ap.add_argument("--stop-trail", choices=["line", "off", "after1r", "be", "htf", "regime"],
                    default=None, help="stop-trail mode. Default = follow live config (htf if ratchet_htf_sl else line). Pass explicitly to override.")
    ap.add_argument("--out-dir", default="",
                    help="where to write backtest CSVs/report. Default = ../backtest/results/replay_logs (keeps them OUT of engine/logs).")
    ap.add_argument("--no-resume", action="store_true",
                    help="ignore any existing checkpoint for this exact config and start fresh "
                         "(checkpoint auto-saves every 500 bars + on Ctrl+C, so a stopped run "
                         "resumes automatically by default — use this flag to force a clean restart).")
    ap.add_argument("--allow-in-sample", action="store_true",
                    help="EXPLICIT override for the data-leakage guard (2026-07-13). By default, "
                         "backtest_replay.py refuses to run if any model's training/validation/"
                         "test/calibration exposure reaches --from or later (train-test overlap). "
                         "Pass this ONLY for a known in-sample sanity check (e.g. current live model "
                         "over full history, just to look) — the result is NOT valid OOS proof and "
                         "must never be used for a keep/reject/profit decision.")
    run(ap.parse_args())
