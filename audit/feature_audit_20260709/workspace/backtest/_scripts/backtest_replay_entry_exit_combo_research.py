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

_ROOT = Path(__file__).resolve().parents[2]
_ENGINE_DIR = _ROOT / "engine"
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

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
RESEARCH_TRAIL_CONFIRM_BARS = 0

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
        self.research_trail_breach_count = 0
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
            if reason == "TRAIL" and RESEARCH_TRAIL_CONFIRM_BARS > 0:
                self.research_trail_breach_count += 1
                if self.research_trail_breach_count < RESEARCH_TRAIL_CONFIRM_BARS:
                    return None
                return self._close(time, c, f"TRAIL_CONFIRM_{RESEARCH_TRAIL_CONFIRM_BARS}BAR")
            return self._close(time, self.virtual_sl, reason)
        self.research_trail_breach_count = 0

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
    global NO_TRAIL, TRAIL_MODE, LOGS, RESEARCH_TRAIL_CONFIRM_BARS
    NO_TRAIL = getattr(args, "no_trail", False)
    RESEARCH_TRAIL_CONFIRM_BARS = max(0, int(getattr(args, "research_trail_confirm_bars", 0) or 0))
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
    _resume_sig = (
        args.date_from, args.date_to, args.equity, args.risk, args.spread,
        args.ratchet, args.ratchet_buf_mode, args.ratchet_buf_mult, args.ratchet_buf_pct,
        args.daily_sl, args.tp_cap, args.tp_regime, args.skip_counter_trend, args.ctf_fade,
        getattr(args, "no_ctf_fade", False),
        getattr(args, "adx_strength_soft", False),
        getattr(args, "adx_strength_margin", 10.0),
        getattr(args, "adx_strength_penalty", 0.05),
        getattr(args, "adx_weight_h1", 0.40),
        getattr(args, "adx_weight_h4", 0.60),
        getattr(args, "adx_penalty_mode", "fixed"),
        getattr(args, "adx_margin_scale", 30.0),
        getattr(args, "adx_max_penalty", 0.06),
        getattr(args, "smma_mtf_soft", False),
        getattr(args, "smma_low_score", 30.0),
        getattr(args, "smma_mid_score", 50.0),
        getattr(args, "smma_low_penalty", 0.05),
        getattr(args, "smma_mid_penalty", 0.03),
        getattr(args, "smma_weight_m15", 0.25),
        getattr(args, "smma_weight_h1", 0.35),
        getattr(args, "smma_weight_h4", 0.40),
        getattr(args, "smma_penalty_mode", "bucket"),
        getattr(args, "smma_linear_target", 70.0),
        getattr(args, "smma_max_penalty", 0.06),
        args.tp_equity_pct, args.max_open, args.tp_mode, args.sl_mode, args.trail_mode,
        args.runner, args.pred_dirs, args.dd_brake, args.fixed_lot, args.max_lot,
        args.no_trail, args.stop_trail, TRAIL_MODE,
        getattr(args, "sell_early_confirm2_tv", False),
        getattr(args, "sell_early_states", "Trending,Volatile"),
        getattr(args, "sell_early_min_win_prob", 0.0),
        getattr(args, "sell_early_replace_weak_r", None),
        getattr(args, "second_trade_policy", "any"),
        getattr(args, "min_bars_between_same_direction", 0),
        RESEARCH_TRAIL_CONFIRM_BARS,
    )
    print("=" * 64)
    print(f"⚡ QGAI AI REPLAY BACKTEST  [trail={TRAIL_MODE}]")
    print("=" * 64)

    # 1. Engine — the SAME brain as live ------------------------------------
    from inference import LiveInferenceEngine, trend_pullback_block, trend_pullback_generate
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
    _TP_BY_REGIME = {"Ranging": 2.0, "Trending": 1.0, "Volatile": 0.8}
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
    sell_early_clean_streak = 0
    sell_early_trigger_count = 0
    sell_early_replace_count = 0
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
                sell_early_clean_streak = _ckpt.get("sell_early_clean_streak", 0)
                sell_early_trigger_count = _ckpt.get("sell_early_trigger_count", 0)
                sell_early_replace_count = _ckpt.get("sell_early_replace_count", 0)
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
    if getattr(args, "sell_early_confirm2_tv", False):
        print("  RESEARCH ENTRY: SELL_EARLY_SIGNAL_CONFIRM_2_TV is ON")
        print(f"    states={getattr(args, 'sell_early_states', 'Trending,Volatile')} | min_win={float(getattr(args, 'sell_early_min_win_prob', 0.0) or 0.0):.2f}")
        if getattr(args, "sell_early_replace_weak_r", None) is not None:
            print(f"    replace weak open trade if current R <= {float(args.sell_early_replace_weak_r):.2f}")
    if args.max_open > 1:
        print(f"  RESEARCH ENTRY POLICY: second_trade_policy={getattr(args, 'second_trade_policy', 'any')} | "
              f"min_bars_between_same_direction={int(getattr(args, 'min_bars_between_same_direction', 0) or 0)}")
    if getattr(args, "no_ctf_fade", False):
        print("  RESEARCH ENTRY: current hard CTF fade filter is forced OFF")
    if getattr(args, "adx_strength_soft", False):
        print(f"  RESEARCH ENTRY: ADX6 strength soft gate ON | adverse margin <= -{float(args.adx_strength_margin):.2f} "
              f"=> threshold +{float(args.adx_strength_penalty):.2%} | weights H1/H4="
              f"{float(args.adx_weight_h1):.0%}/{float(args.adx_weight_h4):.0%} | mode={args.adx_penalty_mode}")
    if getattr(args, "smma_mtf_soft", False):
        print(f"  RESEARCH ENTRY: SMMA MTF soft score ON | score < {float(args.smma_low_score):.0f}/100 "
              f"=> +{float(args.smma_low_penalty):.2%}, score < {float(args.smma_mid_score):.0f}/100 "
              f"=> +{float(args.smma_mid_penalty):.2%} | weights M15/H1/H4="
              f"{float(args.smma_weight_m15):.0%}/{float(args.smma_weight_h1):.0%}/{float(args.smma_weight_h4):.0%} | mode={args.smma_penalty_mode}")
    if RESEARCH_TRAIL_CONFIRM_BARS > 0:
        print(f"  RESEARCH EXIT : TRAIL_CONFIRM_{RESEARCH_TRAIL_CONFIRM_BARS}BAR is ON")

    def _fnum(_v, _default=0.0):
        try:
            if _v is None:
                return _default
            return float(_v)
        except Exception:
            return _default

    def _base_threshold_for(_sig):
        _base = float(getattr(CFG.filters, "min_win_prob", 0.45))
        _state = str(_sig.get("hmm_state", "") or "")
        _state_thresh = {
            "Ranging":  _base + 0.03,
            "Trending": _base,
            "Volatile": max(0.42, _base - 0.03),
        }
        if _fnum(_sig.get("is_pre_news", 0)) >= 1.0:
            return _base + 0.05
        return _state_thresh.get(_state, _base)

    def _adx6_strength_meta(_sig):
        """H1/H4 ADX + DI_diff + ADX-slope strength score.

        BUY score uses positive DI_diff; SELL score uses negative DI_diff.
        Slope is added as positive trend-strengthening context only. This keeps
        the score directional but avoids turning a fading ADX into fake strength.
        """
        _signal = _sig.get("signal")
        if _signal not in ("BUY", "SELL"):
            return {
                "margin": 0.0, "trade_score": 0.0, "opp_score": 0.0,
                "trade_tf": "", "opp_tf": "", "base_threshold": _base_threshold_for(_sig),
                "required_threshold": _base_threshold_for(_sig),
            }
        _d = 1.0 if _signal == "BUY" else -1.0
        _weights = {
            "H1": max(float(getattr(args, "adx_weight_h1", 0.40)), 0.0),
            "H4": max(float(getattr(args, "adx_weight_h4", 0.60)), 0.0),
        }
        _total_w = sum(_weights.values()) or 1.0
        _rows = []
        _trade_score = 0.0
        _opp_score = 0.0
        for _tf, _pfx in (("H1", "h1"), ("H4", "h4")):
            _adx = _fnum(_sig.get(f"{_tf}_ADX", 0))
            _di = _fnum(_sig.get(f"{_tf}_DI_diff", 0))
            _slope = max(_fnum(_sig.get(f"{_pfx}_adx_slope", 0)), 0.0)
            _tf_trade_score = _adx + max(_d * _di, 0.0) + _slope
            _tf_opp_score = _adx + max(-_d * _di, 0.0) + _slope
            _weight = _weights[_tf] / _total_w
            _trade_score += _tf_trade_score * _weight
            _opp_score += _tf_opp_score * _weight
            _rows.append((_tf, _tf_trade_score, _tf_opp_score))
        _trade_tf = max(_rows, key=lambda _r: _r[1])[0]
        _opp_tf = max(_rows, key=lambda _r: _r[2])[0]
        _base = _base_threshold_for(_sig)
        _margin = _trade_score - _opp_score
        _penalty = 0.0
        _penalty_mode = str(getattr(args, "adx_penalty_mode", "fixed") or "fixed")
        if _penalty_mode == "linear":
            _scale = max(float(getattr(args, "adx_margin_scale", 30.0)), 0.0001)
            _max_penalty = max(float(getattr(args, "adx_max_penalty", 0.06)), 0.0)
            _penalty = min(_max_penalty, _max_penalty * max(-_margin, 0.0) / _scale)
        elif _margin <= -float(getattr(args, "adx_strength_margin", 10.0)):
            _penalty = float(getattr(args, "adx_strength_penalty", 0.05))
        _required = _base + _penalty
        return {
            "margin": round(_margin, 4),
            "trade_score": round(_trade_score, 4),
            "opp_score": round(_opp_score, 4),
            "trade_tf": _trade_tf,
            "opp_tf": _opp_tf,
            "weight_h1": round(_weights["H1"], 4),
            "weight_h4": round(_weights["H4"], 4),
            "penalty": round(_penalty, 4),
            "penalty_mode": _penalty_mode,
            "base_threshold": round(_base, 4),
            "required_threshold": round(_required, 4),
        }

    def _adx6_strength_block_for(_sig):
        if not getattr(args, "adx_strength_soft", False):
            return False, "", _adx6_strength_meta(_sig)
        if _sig.get("signal") not in ("BUY", "SELL"):
            return False, "", _adx6_strength_meta(_sig)
        _meta = _adx6_strength_meta(_sig)
        _prob = _fnum(_sig.get("win_prob", 0.0))
        if _meta["required_threshold"] > _meta["base_threshold"] and _prob < _meta["required_threshold"]:
            return (
                True,
                f"adx6 soft {args.adx_penalty_mode}: margin {_meta['margin']:.2f}; "
                f"prob {_prob:.2%} < raised threshold {_meta['required_threshold']:.2%}",
                _meta,
            )
        return False, "", _meta

    def _smma_mtf_meta(_sig):
        """Weighted M15/H1/H4 2-SMMA alignment score.

        M15 is timing, H1 is context, H4 is background. The score is kept as a
        soft confidence adjustment because profitable pullback/reversal trades
        can occur when one or more HTFs are not aligned.
        """
        _signal = _sig.get("signal")
        _base = _base_threshold_for(_sig)
        if _signal not in ("BUY", "SELL"):
            return {
                "score": 0.0, "aligned_count": 0, "base_threshold": round(_base, 4),
                "required_threshold": round(_base, 4),
                "m15_aligned": 0, "h1_aligned": 0, "h4_aligned": 0,
            }
        _d = 1.0 if _signal == "BUY" else -1.0
        _weights = {
            "m15": float(getattr(args, "smma_weight_m15", 0.25)),
            "h1": float(getattr(args, "smma_weight_h1", 0.35)),
            "h4": float(getattr(args, "smma_weight_h4", 0.40)),
        }
        _total_w = sum(max(_w, 0.0) for _w in _weights.values()) or 1.0
        _aligned = {}
        for _tf in ("m15", "h1", "h4"):
            _trend = _fnum(_sig.get(f"ts_trend_{_tf}", 0))
            _aligned[_tf] = 1 if _trend * _d > 0 else 0
        _score = 100.0 * sum(_weights[_tf] * _aligned[_tf] for _tf in _weights) / _total_w
        _penalty = 0.0
        _penalty_mode = str(getattr(args, "smma_penalty_mode", "bucket") or "bucket")
        if _penalty_mode == "linear":
            _target = max(float(getattr(args, "smma_linear_target", 70.0)), 0.0001)
            _max_penalty = max(float(getattr(args, "smma_max_penalty", 0.06)), 0.0)
            _penalty = min(_max_penalty, _max_penalty * max(_target - _score, 0.0) / _target)
        elif _score < float(getattr(args, "smma_low_score", 30.0)):
            _penalty = float(getattr(args, "smma_low_penalty", 0.05))
        elif _score < float(getattr(args, "smma_mid_score", 50.0)):
            _penalty = float(getattr(args, "smma_mid_penalty", 0.03))
        _required = _base + _penalty
        return {
            "score": round(_score, 4),
            "aligned_count": int(sum(_aligned.values())),
            "base_threshold": round(_base, 4),
            "required_threshold": round(_required, 4),
            "penalty": round(_penalty, 4),
            "penalty_mode": _penalty_mode,
            "m15_aligned": _aligned["m15"],
            "h1_aligned": _aligned["h1"],
            "h4_aligned": _aligned["h4"],
        }

    def _smma_mtf_block_for(_sig):
        if not getattr(args, "smma_mtf_soft", False):
            return False, "", _smma_mtf_meta(_sig)
        if _sig.get("signal") not in ("BUY", "SELL"):
            return False, "", _smma_mtf_meta(_sig)
        _meta = _smma_mtf_meta(_sig)
        _prob = _fnum(_sig.get("win_prob", 0.0))
        if _meta["required_threshold"] > _meta["base_threshold"] and _prob < _meta["required_threshold"]:
            return (
                True,
                f"smma mtf soft: score {_meta['score']:.0f}/100; "
                f"prob {_prob:.2%} < raised threshold {_meta['required_threshold']:.2%}",
                _meta,
            )
        return False, "", _meta

    def _entry_blocks_for(_sig):
        _range_on2 = getattr(CFG.filters, "skip_range_phase_entry", False)
        _env_sr2 = os.environ.get("QGAI_SKIP_RANGE")
        if _env_sr2 not in (None, ""):
            _range_on2 = (_env_sr2 == "1")
        if getattr(args, "no_range_skip", False):
            _range_on2 = False

        _range_block2 = False
        if _range_on2:
            try:
                _irp2 = int(float(_sig.get("in_range_phase", 0) or 0))
            except Exception:
                _irp2 = 0
            _rmp2 = float(getattr(CFG.filters, "range_phase_min_prob", 0.0) or 0.0)
            if _irp2 == 1 and (_rmp2 <= 0 or float(_sig.get("win_prob", 1) or 1) < _rmp2):
                _range_block2 = True

        _ctf_block2 = False
        _ctf_on2 = (getattr(CFG.filters, "skip_counter_trend_fade", False) or getattr(args, "ctf_fade", False))
        if getattr(args, "no_ctf_fade", False):
            _ctf_on2 = False
        if _ctf_on2 and _sig.get("signal") in ("BUY", "SELL"):
            try:
                _h1a2 = float(_sig.get("H1_ADX", 0) or 0)
                _h4a2 = float(_sig.get("H4_ADX", 0) or 0)
                _uh42 = _h4a2 >= _h1a2
                _ddi2 = float(_sig.get("H4_DI_diff", 0) or 0) if _uh42 else float(_sig.get("H1_DI_diff", 0) or 0)
                _dsl2 = float(_sig.get("h4_adx_slope", 0) or 0) if _uh42 else float(_sig.get("h1_adx_slope", 0) or 0)
                _md2 = 1 if _ddi2 > 0 else (-1 if _ddi2 < 0 else 0)
                _wd2 = 1 if _sig["signal"] == "BUY" else -1
                if _md2 != 0 and _md2 != _wd2 and _dsl2 <= 0:
                    _ctf_block2 = True
            except Exception:
                _ctf_block2 = False

        _pb_block2, _pb_reason2 = False, ""
        if not _range_block2 and not _ctf_block2:
            try:
                _pb_block2, _pb_reason2 = trend_pullback_block(_sig, CFG)
            except Exception:
                _pb_block2, _pb_reason2 = False, ""
        return _range_block2, _ctf_block2, _pb_block2, _pb_reason2

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
                    "sell_early_clean_streak": sell_early_clean_streak,
                    "sell_early_trigger_count": sell_early_trigger_count,
                    "sell_early_replace_count": sell_early_replace_count,
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
                    "entry_research": "SELL_EARLY_CONFIRM2_TV" if tr.sig.get("_sell_early_entry") else "",
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

        _sell_early_forced = False
        _sell_early_replaced = False
        _sell_rs = dict(rs)
        _se_range_block, _se_ctf_block, _se_pb_block, _se_pb_reason = _entry_blocks_for(_sell_rs)
        _se_adx_block, _se_adx_reason, _se_adx_meta = _adx6_strength_block_for(_sell_rs)
        _se_smma_block, _se_smma_reason, _se_smma_meta = _smma_mtf_block_for(_sell_rs)
        _sell_early_states = {
            x.strip() for x in str(getattr(args, "sell_early_states", "Trending,Volatile")).split(",")
            if x.strip()
        }
        _sell_early_min_win = float(getattr(args, "sell_early_min_win_prob", 0.0) or 0.0)
        _sell_rs_clean_tv = (
            getattr(args, "sell_early_confirm2_tv", False)
            and _sell_rs.get("signal") == "SELL"
            and _sell_rs.get("hmm_state") in _sell_early_states
            and float(_sell_rs.get("win_prob", 0.0) or 0.0) >= _sell_early_min_win
            and not _se_range_block
            and not _se_ctf_block
            and not _se_adx_block
            and not _se_smma_block
            and not _se_pb_block
        )
        if _sell_rs_clean_tv and sell_early_clean_streak >= 1:
            sig = _sell_rs
            sig["_sell_early_entry"] = True
            sig["reason"] = "RESEARCH: SELL_EARLY_SIGNAL_CONFIRM_2_TV"
            _sell_early_forced = True
            sell_early_trigger_count += 1

        if sig.get("signal") == "BUY":
            feats = dict(getattr(engine, "_last_features_buy", None)
                         or getattr(engine, "_last_features", {}) or {})
        else:
            feats = dict(getattr(engine, "_last_features_sell", None)
                         or getattr(engine, "_last_features", {}) or {})

        # ── open trade at NEXT bar open ──────────────────────
        # Range-phase entry filter: skip entries during an H4 range/chop phase.
        # A/B: --no-range-skip (or env QGAI_SKIP_RANGE=0) FORCES it off to measure
        # whether range trades are really net-negative (config claims -43R) — 2026-07-03.
        _range_on = getattr(CFG.filters, "skip_range_phase_entry", False)
        _env_sr = os.environ.get("QGAI_SKIP_RANGE")
        if _env_sr not in (None, ""):
            _range_on = (_env_sr == "1")
        if getattr(args, "no_range_skip", False):
            _range_on = False
        _range_block = False
        if _range_on:
            try: _irp = int(float(sig.get("in_range_phase", 0) or 0))
            except Exception: _irp = 0
            _rmp = float(getattr(CFG.filters, "range_phase_min_prob", 0.0) or 0.0)
            if _irp == 1 and (_rmp <= 0 or float(sig.get("win_prob", 1) or 1) < _rmp):
                _range_block = True
        # Counter-trend-FADE filter: block a trade AGAINST the dominant timeframe's
        # momentum (H1/H4 — whichever ADX is higher) when that dominant ADX slope is
        # falling (trend real but fading = whipsaw zone). Data: in-sample +15R, PF 1.74→1.89.
        _ctf_block = False
        _ctf_on = getattr(CFG.filters, "skip_counter_trend_fade", False) or getattr(args, "ctf_fade", False)
        if getattr(args, "no_ctf_fade", False):
            _ctf_on = False
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
        _adx_block, _adx_reason, _adx_meta = False, "", _adx6_strength_meta(sig)
        if not _range_block and not _ctf_block:
            _adx_block, _adx_reason, _adx_meta = _adx6_strength_block_for(sig)

        _smma_block, _smma_reason, _smma_meta = False, "", _smma_mtf_meta(sig)
        if not _range_block and not _ctf_block and not _adx_block:
            _smma_block, _smma_reason, _smma_meta = _smma_mtf_block_for(sig)

        _pb_block, _pb_reason = False, ""
        if not _range_block and not _ctf_block and not _adx_block and not _smma_block:
            try:
                _pb_block, _pb_reason = trend_pullback_block(sig, CFG)
            except Exception:
                _pb_block, _pb_reason = False, ""

        # record EVERY signal (incl. SKIP + which filter blocked it — for auditing the CSV)
        signals_out.append({
            "bar_time": ts, "signal": sig.get("signal", "SKIP"),
            "win_prob": sig.get("win_prob"), "state_prob": sig.get("state_prob"),
            "dir_prob": sig.get("dir_prob"), "hmm_state": sig.get("hmm_state"),
            "atr20_pct": sig.get("atr20_pct"),
            "blocked_by": ("range" if _range_block else "ctf_fade" if _ctf_block
                           else "adx6_strength" if _adx_block
                           else "smma_mtf" if _smma_block
                           else "pullback" if _pb_block else ""),
            "in_range_phase": sig.get("in_range_phase", 0),
            "H1_ADX": sig.get("H1_ADX", 0), "H4_ADX": sig.get("H4_ADX", 0),
            "H1_DI_diff": sig.get("H1_DI_diff", 0), "H4_DI_diff": sig.get("H4_DI_diff", 0),
            "h1_adx_slope": sig.get("h1_adx_slope", 0), "h4_adx_slope": sig.get("h4_adx_slope", 0),
            "adx6_margin": _adx_meta.get("margin", 0),
            "adx6_trade_score": _adx_meta.get("trade_score", 0),
            "adx6_opp_score": _adx_meta.get("opp_score", 0),
            "adx6_trade_tf": _adx_meta.get("trade_tf", ""),
            "adx6_opp_tf": _adx_meta.get("opp_tf", ""),
            "adx6_weight_h1": _adx_meta.get("weight_h1", 0),
            "adx6_weight_h4": _adx_meta.get("weight_h4", 0),
            "adx6_penalty": _adx_meta.get("penalty", 0),
            "adx6_penalty_mode": _adx_meta.get("penalty_mode", ""),
            "adx6_base_threshold": _adx_meta.get("base_threshold", 0),
            "adx6_required_threshold": _adx_meta.get("required_threshold", 0),
            "smma_mtf_score": _smma_meta.get("score", 0),
            "smma_aligned_count": _smma_meta.get("aligned_count", 0),
            "smma_m15_aligned": _smma_meta.get("m15_aligned", 0),
            "smma_h1_aligned": _smma_meta.get("h1_aligned", 0),
            "smma_h4_aligned": _smma_meta.get("h4_aligned", 0),
            "smma_penalty": _smma_meta.get("penalty", 0),
            "smma_penalty_mode": _smma_meta.get("penalty_mode", ""),
            "smma_base_threshold": _smma_meta.get("base_threshold", 0),
            "smma_required_threshold": _smma_meta.get("required_threshold", 0),
            "ts_line_dist_pct": sig.get("ts_line_dist_pct", 0),
            "ts_trend_m15": sig.get("ts_trend_m15", 0),
            "ts_trend_h1": sig.get("ts_trend_h1", 0),
            "ts_trend_h4": sig.get("ts_trend_h4", 0),
            "ts_htf_agreement": sig.get("ts_htf_agreement", 0),
            "ts_adx_switch_trend": sig.get("ts_adx_switch_trend", 0),
            "sell_early_forced": int(_sell_early_forced),
            "sell_early_clean_streak_before": sell_early_clean_streak,
            "sell_model_signal": _sell_rs.get("signal", "SKIP"),
            "sell_model_win_prob": _sell_rs.get("win_prob"),
            "sell_model_hmm_state": _sell_rs.get("hmm_state"),
            "sell_model_clean_tv": int(_sell_rs_clean_tv),
            "sell_early_replaced_open_trade": int(_sell_early_replaced),
            "reason": (_adx_reason or _smma_reason or _pb_reason or sig.get("reason", ""))[:140],
        })

        sell_early_clean_streak = sell_early_clean_streak + 1 if _sell_rs_clean_tv else 0

        _replace_weak_r = getattr(args, "sell_early_replace_weak_r", None)
        if (_sell_early_forced
                and _replace_weak_r is not None
                and len(open_trades) >= args.max_open
                and open_trades):
            _replace_weak_r = float(_replace_weak_r)
            _weak_tr = min(open_trades, key=lambda _tr: _tr._r(row["close"]))
            _weak_r = _weak_tr._r(row["close"])
            if _weak_r <= _replace_weak_r:
                res = _weak_tr._close(ts, row["close"], f"REPLACE_EARLY_SELL_R<={_replace_weak_r:.2f}")
                equity += res["pnl_usd"]
                rec = {
                    "entry_time":  _weak_tr.entry_time, "exit_time": res["exit_time"],
                    "direction":   _weak_tr.direction,
                    "entry_price": round(_weak_tr.entry, 2), "exit_price": res["exit_price"],
                    "price_move":  round((res["exit_price"] - _weak_tr.entry) * _weak_tr.s, 2),
                    "sl_price":    round(_weak_tr.entry - _weak_tr.s * _weak_tr.sl_dist, 2),
                    "tp1_price":   round(_weak_tr.tp1, 2) if _weak_tr.tp1 is not None else None,
                    "tp2_price":   round(_weak_tr.tp2, 2) if _weak_tr.tp2 is not None else None,
                    "sl_dist":     round(_weak_tr.sl_dist, 2),
                    "risk_usd":    round(_weak_tr.risk_usd, 2),
                    "exit_reason": res["exit_reason"],
                    "r_achieved":  res["r_achieved"], "peak_r": res["peak_r"],
                    "pnl_usd":     res["pnl_usd"],
                    "equity_after": round(equity, 2),
                    "win_prob":    _weak_tr.sig.get("win_prob"), "state_prob": _weak_tr.sig.get("state_prob"),
                    "dir_prob":    _weak_tr.sig.get("dir_prob"), "hmm_state": _weak_tr.sig.get("hmm_state"),
                    "sl_mult":     _weak_tr.sig.get("sl_multiplier"), "tp_mult": _weak_tr.sig.get("tp_multiplier"),
                    "entry_research": "SELL_EARLY_CONFIRM2_TV" if _weak_tr.sig.get("_sell_early_entry") else "",
                    "reason":      _weak_tr.sig.get("reason", ""),
                }
                for fk, fv in _weak_tr.features.items():
                    rec[f"f_{fk}"] = fv
                trades_out.append(rec)
                open_trades = [tr for tr in open_trades if tr is not _weak_tr]
                peak_eq = max(peak_eq, equity)
                max_dd = max(max_dd, (peak_eq - equity) / peak_eq if peak_eq > 0 else 0)
                _sell_early_replaced = True
                sell_early_replace_count += 1
                if signals_out:
                    signals_out[-1]["sell_early_replaced_open_trade"] = 1

        _entry_policy_block = False
        _entry_policy_reason = ""
        if sig.get("signal") in ("BUY", "SELL") and len(open_trades) < args.max_open:
            _new_dir = sig.get("signal")
            _policy = getattr(args, "second_trade_policy", "any")
            if open_trades and _policy == "same_direction_only":
                if any(tr.direction != _new_dir for tr in open_trades):
                    _entry_policy_block = True
                    _entry_policy_reason = "second_trade_policy_same_direction_only"
            elif open_trades and _policy == "opposite_direction_only":
                if any(tr.direction == _new_dir for tr in open_trades):
                    _entry_policy_block = True
                    _entry_policy_reason = "second_trade_policy_opposite_direction_only"

            _min_same_bars = int(getattr(args, "min_bars_between_same_direction", 0) or 0)
            if not _entry_policy_block and _min_same_bars > 0:
                _min_same_minutes = _min_same_bars * 15
                for tr in open_trades:
                    if tr.direction == _new_dir:
                        try:
                            _age_min = (pd.Timestamp(nxt["datetime"]) - pd.Timestamp(tr.entry_time)).total_seconds() / 60.0
                        except Exception:
                            _age_min = 0.0
                        if _age_min < _min_same_minutes:
                            _entry_policy_block = True
                            _entry_policy_reason = f"min_bars_between_same_direction_{_min_same_bars}"
                            break

        if (sig.get("signal") in ("BUY", "SELL")
                and len(open_trades) < args.max_open
                and not _entry_policy_block
                and not daily_stopped
                and not _range_block
                and not _ctf_block
                and not _adx_block
                and not _smma_block
                and not _pb_block):
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
    if getattr(args, "sell_early_confirm2_tv", False):
        rep.append(f"Entry research : SELL_EARLY_SIGNAL_CONFIRM_2_TV | forced bars {sell_early_trigger_count}")
        rep.append(f"Entry filters  : states={getattr(args, 'sell_early_states', 'Trending,Volatile')} | min_win={float(getattr(args, 'sell_early_min_win_prob', 0.0) or 0.0):.2f}")
        if getattr(args, "sell_early_replace_weak_r", None) is not None:
            rep.append(f"Entry replace  : weak open trade R <= {float(args.sell_early_replace_weak_r):.2f} | replacements {sell_early_replace_count}")
    if args.max_open > 1:
        rep.append(f"Entry policy   : max_open={args.max_open} | second_trade_policy={getattr(args, 'second_trade_policy', 'any')} | min_same_dir_bars={int(getattr(args, 'min_bars_between_same_direction', 0) or 0)}")
    if getattr(args, "no_ctf_fade", False):
        rep.append("Entry CTF      : hard counter-trend-fade OFF")
    if getattr(args, "adx_strength_soft", False):
        if str(getattr(args, "adx_penalty_mode", "fixed")) == "linear":
            rep.append(f"Entry ADX6     : linear soft strength | scale {float(args.adx_margin_scale):.1f}, max +{float(args.adx_max_penalty):.2%} | weights H1/H4={float(args.adx_weight_h1):.0%}/{float(args.adx_weight_h4):.0%}")
        else:
            rep.append(f"Entry ADX6     : soft strength gate | adverse margin <= -{float(args.adx_strength_margin):.2f} -> threshold +{float(args.adx_strength_penalty):.2%} | weights H1/H4={float(args.adx_weight_h1):.0%}/{float(args.adx_weight_h4):.0%}")
    if getattr(args, "smma_mtf_soft", False):
        if str(getattr(args, "smma_penalty_mode", "bucket")) == "linear":
            rep.append(f"Entry SMMA MTF : linear soft score 0-100 | target {float(args.smma_linear_target):.0f}, max +{float(args.smma_max_penalty):.2%} | weights M15/H1/H4={float(args.smma_weight_m15):.0%}/{float(args.smma_weight_h1):.0%}/{float(args.smma_weight_h4):.0%}")
        else:
            rep.append(f"Entry SMMA MTF : soft score 0-100 | score < {float(args.smma_low_score):.0f} -> +{float(args.smma_low_penalty):.2%}; score < {float(args.smma_mid_score):.0f} -> +{float(args.smma_mid_penalty):.2%} | weights M15/H1/H4={float(args.smma_weight_m15):.0%}/{float(args.smma_weight_h1):.0%}/{float(args.smma_weight_h4):.0%}")
    if RESEARCH_TRAIL_CONFIRM_BARS > 0:
        rep.append(f"Exit research  : TRAIL_CONFIRM_{RESEARCH_TRAIL_CONFIRM_BARS}BAR")
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
    ap.add_argument("--no-range-skip", action="store_true",
                    help="A/B: FORCE the H4 range-phase entry filter OFF (allow range trades) to measure "
                         "whether range trades are really net-negative. Overrides config skip_range_phase_entry.")
    ap.add_argument("--ctf-fade", action="store_true",
                    help="counter-trend-FADE filter: block a trade against the dominant TF (higher ADX) "
                         "momentum when that ADX slope is falling. Overrides config skip_counter_trend_fade=True.")
    ap.add_argument("--no-ctf-fade", action="store_true",
                    help="RESEARCH ONLY: force the current hard counter-trend-fade filter OFF.")
    ap.add_argument("--adx-strength-soft", action="store_true",
                    help="RESEARCH ONLY: use H1/H4 ADX+DI_diff+slope as a soft strength gate. "
                         "When adverse margin is too negative, require a higher win_prob.")
    ap.add_argument("--adx-strength-margin", type=float, default=10.0,
                    help="RESEARCH ONLY: adverse ADX6 margin threshold. Soft gate activates when margin <= -N.")
    ap.add_argument("--adx-strength-penalty", type=float, default=0.05,
                    help="RESEARCH ONLY: win_prob threshold raise when ADX6 adverse margin triggers.")
    ap.add_argument("--adx-weight-h1", type=float, default=0.40,
                    help="RESEARCH ONLY: H1 weight in ADX6 strength score.")
    ap.add_argument("--adx-weight-h4", type=float, default=0.60,
                    help="RESEARCH ONLY: H4 weight in ADX6 strength score.")
    ap.add_argument("--adx-penalty-mode", choices=["fixed", "linear"], default="fixed",
                    help="RESEARCH ONLY: fixed=bucket margin gate; linear=penalty grows with adverse ADX margin.")
    ap.add_argument("--adx-margin-scale", type=float, default=30.0,
                    help="RESEARCH ONLY: linear ADX scale. At this adverse margin, --adx-max-penalty is fully applied.")
    ap.add_argument("--adx-max-penalty", type=float, default=0.06,
                    help="RESEARCH ONLY: maximum win_prob threshold raise for linear ADX penalty.")
    ap.add_argument("--smma-mtf-soft", action="store_true",
                    help="RESEARCH ONLY: use M15/H1/H4 2-SMMA alignment as a soft score. "
                         "Low score raises the required win_prob instead of hard-blocking.")
    ap.add_argument("--smma-low-score", type=float, default=30.0,
                    help="RESEARCH ONLY: SMMA score below this gets the low-score threshold penalty.")
    ap.add_argument("--smma-mid-score", type=float, default=50.0,
                    help="RESEARCH ONLY: SMMA score below this gets the mid-score threshold penalty.")
    ap.add_argument("--smma-low-penalty", type=float, default=0.05,
                    help="RESEARCH ONLY: win_prob threshold raise when SMMA score is below --smma-low-score.")
    ap.add_argument("--smma-mid-penalty", type=float, default=0.03,
                    help="RESEARCH ONLY: win_prob threshold raise when SMMA score is below --smma-mid-score.")
    ap.add_argument("--smma-weight-m15", type=float, default=0.25,
                    help="RESEARCH ONLY: M15 weight in SMMA MTF score.")
    ap.add_argument("--smma-weight-h1", type=float, default=0.35,
                    help="RESEARCH ONLY: H1 weight in SMMA MTF score.")
    ap.add_argument("--smma-weight-h4", type=float, default=0.40,
                    help="RESEARCH ONLY: H4 weight in SMMA MTF score.")
    ap.add_argument("--smma-penalty-mode", choices=["bucket", "linear"], default="bucket",
                    help="RESEARCH ONLY: bucket=two threshold bands; linear=penalty grows as score falls below target.")
    ap.add_argument("--smma-linear-target", type=float, default=70.0,
                    help="RESEARCH ONLY: linear SMMA target score. Below this, penalty increases gradually.")
    ap.add_argument("--smma-max-penalty", type=float, default=0.06,
                    help="RESEARCH ONLY: maximum win_prob threshold raise for linear SMMA penalty.")
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
    ap.add_argument("--sell-early-confirm2-tv", action="store_true",
                    help="RESEARCH ONLY: force SELL entry after 2 consecutive clean SELL-model signals in Trending/Volatile.")
    ap.add_argument("--sell-early-states", default="Trending,Volatile",
                    help="RESEARCH ONLY: comma-separated HMM states allowed for SELL early entry.")
    ap.add_argument("--sell-early-min-win-prob", type=float, default=0.0,
                    help="RESEARCH ONLY: minimum SELL-model win_prob for SELL early entry.")
    ap.add_argument("--sell-early-replace-weak-r", type=float, default=None,
                    help="RESEARCH ONLY: if slot is full, close weakest open trade when current R <= this value, then allow early SELL.")
    ap.add_argument("--second-trade-policy", choices=["any", "same_direction_only", "opposite_direction_only"],
                    default="any",
                    help="RESEARCH ONLY: when max_open > 1, restrict the second open trade by direction relationship.")
    ap.add_argument("--min-bars-between-same-direction", type=int, default=0,
                    help="RESEARCH ONLY: block a same-direction add if an open same-direction trade is younger than this many M15 bars.")
    ap.add_argument("--research-trail-confirm-bars", type=int, default=0,
                    help="RESEARCH ONLY: require N consecutive trail-SL touches before closing at bar close.")
    ap.add_argument("--out-dir", default="",
                    help="where to write backtest CSVs/report. Default = ../backtest/results/replay_logs (keeps them OUT of engine/logs).")
    ap.add_argument("--no-resume", action="store_true",
                    help="ignore any existing checkpoint for this exact config and start fresh "
                         "(checkpoint auto-saves every 500 bars + on Ctrl+C, so a stopped run "
                         "resumes automatically by default — use this flag to force a clean restart).")
    run(ap.parse_args())
