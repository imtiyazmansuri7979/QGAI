"""
config.py — QUANT GOLD AI v2
All settings in one place.

Folder structure (relative to this file's location):
  QGAI/
  +-- data/          <- datasets, models, news CSVs
  |   +-- historical/
  |   +-- live/
  |   +-- merged/
  |   +-- models/final/
  |   +-- news_*.csv
  +-- engine/        <- all Python files, logs, dashboard  ← this file lives here
      +-- logs/
      +-- *.bat

Paths are derived automatically from __file__ — no hardcoding needed.
To move the project: just move the QGAI/ folder. Nothing else changes.
To override any path: set env var QGAI_ROOT before launching, e.g.
    set QGAI_ROOT=D:/trading/QGAI   (use forward slashes or double backslashes)
"""
import os
from pathlib import Path
from dataclasses import dataclass, field

# ── Root resolution ───────────────────────────────────────────
# engine/config.py  →  engine/  →  QGAI_ROOT/
# QGAI_ROOT can be overridden via environment variable for VPS / cloud deployments.
_ENGINE_DIR = Path(__file__).resolve().parent
_DEFAULT_ROOT = _ENGINE_DIR.parent           # one level up from engine/
QGAI_ROOT = Path(os.environ.get("QGAI_ROOT", str(_DEFAULT_ROOT)))

# Convenience sub-roots — used below and importable by other modules
_DATA_DIR   = QGAI_ROOT / "data"
_ENGINE_DIR_FINAL = QGAI_ROOT / "engine"    # same as _ENGINE_DIR unless QGAI_ROOT overridden


@dataclass
class PathConfig:
    # ── Data folder ───────────────────────────────────────────
    trades_file : str = str(_DATA_DIR / "Back_testing_data_final_cleaned_RELABELED.xlsx")  # 2026-06-26 Task 1: closed-loop relabel (labels recomputed under live HTF exit; 27% of labels differed from the old static backtest). REVERT: change back to Back_testing_data_final_cleaned.xlsx
    ohlc_file   : str = str(_DATA_DIR / "merged"  / "ohlc_merged.csv")
    adx_file    : str = str(_DATA_DIR / "merged"  / "adx_merged.csv")
    news_file   : str = str(_DATA_DIR / "news_all_2024_to_now_pure_cleaned.csv")
    surprise_csv: str = str(_DATA_DIR / "news_surprises.csv")
    # 2026-07-13 (Imtiyaz): env override QGAI_MODELS_DIR lets tests/WFO/sweeps
    # point at a completely SEPARATE folder so they never touch the live
    # model at all — root-cause fix for 3 same-day incidents where a test's
    # backup/restore dance around data/models/final went wrong (crash mid-
    # swap, two concurrent processes, a multi-step sweep chain). Unset =
    # unchanged default behavior (live bridge always uses this branch).
    models_dir  : str = os.environ.get("QGAI_MODELS_DIR", str(_DATA_DIR / "models" / "final"))
    registry_dir: str = str(_DATA_DIR / "models"  / "registry")
    # ── Sub-directories used by merge_data / mt5_data_updater ─
    hist_dir    : str = str(_DATA_DIR / "historical")
    live_dir    : str = str(_DATA_DIR / "live")
    merge_dir   : str = str(_DATA_DIR / "merged")
    # ── Engine folder ─────────────────────────────────────────
    logs_dir    : str = str(_ENGINE_DIR_FINAL / "logs")
    live_log    : str = str(_ENGINE_DIR_FINAL / "logs" / "live_trades.csv")
    signal_log  : str = str(_ENGINE_DIR_FINAL / "logs" / "signals_all.csv")
    db_path     : str = str(_ENGINE_DIR_FINAL / "logs" / "qgai.db")

@dataclass
class FilterConfig:
    min_win_prob             : float = 0.45
    # 2026-06-23: skip entries during an H4 RANGE/CHOP phase (in_range_phase==1).
    # Trend-following ratchet whipsaws in ranges. Old baseline (IN-SAMPLE only): range
    # trades net −43R / PF 0.76 vs trend PF 2.62 — but that was never WFO/honest-model
    # confirmed (the "Demo/WFO confirm" TODO stayed open). 2026-07-12 (Imtiyaz): this
    # filter was added post-hoc for a small profit bump WITHOUT a proper test, and on
    # the honest 34-feat model it blocks ~63% of actionable BUY/SELL. REMOVED (set to
    # False) — re-add later only if a WFO/honest A/B proves it raises TOTAL R.
    # in_range_phase is lookahead-free (last completed H4 bar). Set True to re-enable.
    skip_range_phase_entry   : bool  = False
    range_phase_min_prob     : float = 0.0    # if >0: only skip range entries when win_prob < this (soft). 0 = always skip range.
    resume_prompt_on_start   : bool  = False  # 2026-06-30 (Anisa) REMOVED: bot now manages manual trades, so the user opens trades manually when wanted (bot handles them). No startup prompt — bot auto-trades its OWN signals. (Set True to re-enable the "trade the last signal? [y/N]" prompt.)
    resume_prompt_timeout_s  : float = 60.0   # how long the startup resume prompt waits for y/N before defaulting to NO (skip)
    # 2026-06-23: counter-trend-FADE block (data-found, in-sample +15R / PF 1.74→1.89).
    # Block a trade that is AGAINST the DOMINANT timeframe's momentum (H1 or H4 — whichever
    # has the higher ADX) WHEN that dominant ADX slope is FALLING (trend real but fading =
    # whipsaw no-man's-land). Counter-trend in a RISING/strong trend is still fine (kept).
    # Lookahead-free (uses last-closed H1/H4). Default OFF until backtest_replay confirms.
    skip_counter_trend_fade  : bool  = False  # 2026-07-07 DISABLED: Path-A live-parity BT proved CTF was blocking 77%-WR counter-aligned edge. Baseline +350.2R vs CTF-OFF +384.5R = +34.3R (+9.8%) with WR 62.7% (+0.4pp) and PF 3.43 (+0.20). DD 0.9%→1.1% (acceptable). Reversible: set True. Env A/B: QGAI_CTF_FADE=1 to force ON.
    # ── TREND-FOLLOWING PULLBACK ENTRY (2026-07-03, ET1) — fixes late "buy-the-top" entry ──
    # Problem: entry is 100% ML win_prob-gated; dir_prob only turns after the breakout candle,
    # so BUY fires near the top (02-03 Jul gold rally, signals_all.csv). Fix = split DIRECTION
    # (HTF SMMA/ADX alignment, leading) from TIMING (enter on a shallow pullback/reclaim to the
    # ratchet line, NOT the breakout). Anti-chase uses ts_line_dist_pct (price-to-SMMA-line %,
    # ATR-free — ATR already removed 2026-06-19). Sweep A: deterministic gate, ML-veto OFF.
    # ALL lookahead-free (last-closed ts_* features). DEFAULT OFF → live unchanged until WFO-won.
    # Reversible: set trend_pullback_entry=False. Env overrides (for the sweep, per combo):
    #   QGAI_PB_ENTRY(0/1), QGAI_PB_NEAR, QGAI_PB_CHASE, QGAI_PB_AGREE.
    trend_pullback_entry     : bool  = False  # v1 BLOCK mode: veto ML entries that aren't a valid pullback (default OFF)
    trend_pullback_generate  : bool  = False  # v2 GENERATE mode: CREATE early pullback entries when ML SKIPs but ADX-aligned trend pulls back to the line (the real "enter early, not at top" fix). Env: QGAI_PB_GEN. Default OFF. Don't enable together with trend_pullback_entry.
    pb_near_pct              : float = 0.075   # entry only if price within this % of the ratchet line (pullback zone); established-trend bars
    chase_max_pct            : float = 0.25    # hard anti-chase: never enter if price > this % beyond the line (buys-the-top guard); also the fresh-flip entry window
    htf_agreement_min        : int   = 3       # required |ts_htf_agreement| (M15+H1+H4 trend sum, ∈{1,3}) in trade dir. 1=dominant/net trend only (trades when TFs disagree); 3=all-3 aligned (strict). Sweep {1,3}.
    # ── SMMA MTF SOFT GATE — 🔴 PARKED, PROVEN HARMFUL (2026-07-07). DO NOT FLIP TO TRUE. ──
    # The earlier "+51R research win" was a Combo-flag artifact + slot-substitution. LIVE-PARITY
    # full-year backtest (2026-07-07): SMMA ON = +346.5R vs baseline +350.2R = **−3.7R**. It
    # blocked 33 PROFITABLE trades (+15.3R, avg +0.46R). Fable-5 data check: alignment ANTI-
    # correlates with profit (0/3 aligned WR 77% > 3/3 aligned WR 60%) — this pullback/mean-
    # reversion system's edge IS the counter-aligned cohort. Keep code path for reference only.
    smma_mtf_soft            : bool  = False   # ⚠️ PROVEN HARMFUL — keep False (env QGAI_SMMA_MTF=1 for A/B only)
    smma_weight_m15          : float = 0.25    # weight for M15 SMMA-2 alignment
    smma_weight_h1           : float = 0.35    # weight for H1  SMMA-2 alignment
    smma_weight_h4           : float = 0.40    # weight for H4  SMMA-2 alignment
    smma_linear_target       : float = 70.0    # alignment-score target (score ≥ target → 0 penalty)
    smma_max_penalty         : float = 0.06    # max additive threshold penalty (score=0 → +6%)
    # ── ADX6 STRENGTH SOFT GATE (2026-07-06) — complementary safety layer to SMMA MTF.
    # Different signal: SMMA measures SMMA-2 slope alignment (trend direction agreement);
    # ADX6 measures ADX+DI_diff+slope on H1/H4 (trend STRENGTH bias). Weighted margin =
    # (trade_score - opp_score). If margin < -scale → penalty scales linearly to max.
    # Research (Jul 4-5): linear W H1=40 / H4=60 scale=30 max +0.06 = +400.6R (near SMMA).
    # 96.7% overlap with SMMA on which trades to block — kept as ADDITIVE penalty (not OR):
    # required_threshold = base + smma_penalty + adx6_penalty. Where both agree it's weak,
    # threshold rises MORE → over-block-safe. Default OFF. Env override: QGAI_ADX6_SOFT=1.
    adx6_strength_soft       : bool  = False   # master switch — ADX6 strength soft gate
    adx6_weight_h1           : float = 0.40    # weight for H1 ADX6 score
    adx6_weight_h4           : float = 0.60    # weight for H4 ADX6 score
    adx6_margin_scale        : float = 30.0    # linear scale — penalty=max*(-margin/scale)
    adx6_max_penalty         : float = 0.06    # max additive threshold penalty
    # ── ADX STRENGTH SOFT GATE — Fable-5 REDESIGN (2026-07-07, direction-agnostic) ──
    # Old ADX6 formula = trade_score - opp_score = d*DI_diff (ADX + slope cancel out) →
    # was mislabeled "strength", actually direction bias. 96.7% overlap with SMMA.
    # NEW: direction-agnostic magnitude score using H1/H4 ADX level + positive slope.
    # BUY/SELL score the same for the same market — strong trend against us still HIGH.
    # Direction is Gate A's (SMMA) job. Bounded 0-100. Penalty target=55, max +0.04
    # (smaller than SMMA — strength is a weaker prior). Env: QGAI_ADX_STRENGTH=1.
    adx_strength_soft         : bool  = False   # master switch
    adx_strength_lo           : float = 15.0    # ADX 15 → level score 0
    adx_strength_hi           : float = 35.0    # ADX 35+ → level score 1
    adx_strength_slope_div    : float = 1.5     # slope divisor (positive-only contribution)
    adx_strength_linear_target: float = 55.0    # target score → 0 penalty
    adx_strength_max_penalty  : float = 0.04    # max additive threshold penalty
    # ── EARLY-ENTRY THRESHOLD DISCOUNT (2026-07-07, Fable #1 pick for late-entry) ──
    # EARLY-ENTRY THRESHOLD DISCOUNT config keys REMOVED 2026-07-12 (Imtiyaz):
    # feature deleted from inference.py (nil impact under max_open=1). REVERT: git.
    # ── FAB-S2 news staleness assertion (2026-07-07, Fable-5 audit fix) ──
    # bridge_main startup runs check_staleness() and logs ERROR banner if the
    # calendar's last event is > N days old. `pause_if_news_stale=True` will
    # additionally refuse to start the bot until the CSV is refreshed —
    # default False so a stale calendar shouts but doesn't ground the bot.
    news_max_stale_days       : int   = 7       # max days since last event before ERROR banner
    pause_if_news_stale       : bool  = False   # True: sys.exit(1) at startup when stale
    # ── FAB-S3 live multi-day drawdown brake (2026-07-07, Fable-5 audit fix) ──
    # Backtest has an M3 %-DD brake; live had NONE (only daily 9% halt). Protective:
    # scales lot size down as equity draws down from the persisted all-time peak
    # (dd>half%→×0.5, >quarter%→×0.25, >halt%→halt). Never increases size → never
    # blocks a profitable trade (prime-directive safe). Default OFF — enabling is an
    # explicit operator choice (changes live sizing). RECOMMENDED ON for real capital.
    enable_live_dd_brake      : bool  = True    # 2026-07-07 ENABLED (Imtiyaz): protective multi-day DD brake ON for real capital. Reversible: set False.
    dd_brake_half_pct         : float = 10.0    # dd > this% of peak → ½ size
    dd_brake_quarter_pct      : float = 20.0    # dd > this% → ¼ size
    dd_brake_halt_pct         : float = 30.0    # dd > this% → halt new entries
    # ── FAB-S1 reversal-entry gating (2026-07-07, Fable-5 audit fix) ──
    # False (default): opposite-signal reversal opens immediately, UNFILTERED (legacy).
    # True: reversal closes the losing side, then the main loop re-evaluates the same
    # bar's signal through the FULL entry-filter stack (range/CTF/pullback/SMMA/ADX)
    # before opening — so a reversal entry is filtered identically to a fresh entry.
    # Enable only after a backtest that ALSO models close-on-opposite (parity).
    gate_reversal_entries     : bool  = True
    # ── ADX-DEATH EXIT (2026-07-08, Imtiyaz idea + Fable-5 design) ──
    # During hold: if K of 4 TF ADX slopes ≤0 for N consecutive bars AND
    # unrealized profit ≥ min_r × R → exit at bar close (reason ADX_DEATH).
    # Slopes: M15=diff(1), M30=diff(2), H1=diff(4), H4=diff(16).
    # Default OFF. Env: QGAI_ADX_DEATH=1, QGAI_ADX_DEATH_K, _N, _MIN_R.
    adx_death_enabled         : bool  = False
    adx_death_k               : int   = 3       # min TFs with slope ≤ 0
    adx_death_n               : int   = 3       # consecutive bars needed
    adx_death_min_r           : float = 0.5     # min unrealized profit in R
    # ── ⚰️ DEAD KEYS (FAB-M14 2026-07-07): verified 0 non-config readers in engine/.
    # Session timing is ONLY a model FEATURE (is_ny_session, session_score), NOT a
    # hard filter. The actual slot gate is `use_slot_day_filter` (=False). These are
    # kept (not deleted) to avoid breaking any dynamic getattr, but flipped to False
    # so config.py doesn't LOOK like session filtering is active. Do not wire logic
    # to these — add a real filter with its own key instead. ──
    use_time_filter          : bool  = False  # DEAD (was True — misleading; 0 readers)
    enable_morning_session   : bool  = False  # DEAD
    enable_ny_session        : bool  = False  # DEAD (was True — misleading; 0 readers)
    window1_start            : int   = 7      # DEAD
    window1_end              : int   = 9      # DEAD
    window2_start            : int   = 16     # DEAD
    window2_end              : int   = 19     # DEAD
    training_time_filter     : bool  = False  # (1 reader in train pipeline — kept)
    enable_daily_sl          : bool  = True
    daily_loss_limit_pct     : float = 9.0
    # Daily Equity TARGET (EA-style, virtual — hidden from broker):
    # when equity >= day_open × (1 + target%), close all + stop for the day
    enable_daily_tp          : bool  = False  # disabled 2026-06-14 (let trades run all day)
    daily_profit_target_pct  : float = 8.0
    # RATCHET exit (EA-style, full package): line+buffer SL sizing,
    # one-way line trailing, opposite-flip exit. All values in % of price.
    # OFF by default — switch ON after backtest_replay comparison.
    enable_ratchet_exit      : bool  = True   # validated 2026-06-14: ratchet ON is the tested strategy
    ratchet_buf_pct          : float = 0.15   # 2026-07-01: live buffer from latest bufsweep; 0.15 best balance (PF 3.87, +430.70%, DD 2.9%). Reversible: set 0.20 for prior value.
    ratchet_tp_cap_pct       : float = 1.00   # 2026-06-26 user choice: keep TP=1.00 (NOT 1.20). The trades_tp_1.00 "best result" config: +287R/PF1.74 in-sample. Restore far TP = set 10.0.
    # EQUITY-BASED TP (matches WFO backtest --tp-equity-pct). Trade closes
    # when profit reaches tp_equity_pct of equity. With risk_pct=3% this is
    # a constant R-multiple = tp_equity_pct / risk_pct. Set >0 to ENABLE
    # equity-TP (overrides the price-based tp_cap above). 0 = use price cap.
    # Added 2026-06-14: live MUST match WFO (was price-based 4% = ~40R bug).
    tp_equity_pct            : float = 0.0    # 2026: switched to PRICE-based TP (set 0 → use ratchet_tp_cap_pct). Backtest: price-TP 4% +165R vs equity-1.33R +87R. Toggle: set back to 4.0 for old equity-TP.
    ratchet_max_risk_pct     : float = 1.2    # line farther than this % → ATR fallback
    ratchet_flip_exit        : bool  = True   # close on opposite flip (15-min)
    # ── HTF (higher-timeframe) ratchet — fixes the 15-min whipsaw ──────────
    # Problem: in a 4h/1h/30m uptrend the 15-min SMMA line hugs price, so the
    # SL sits ~$8 from entry (< one M15 candle range) → normal 15-min noise
    # cuts it → repeated small losses. When the HTF agrees with the trade,
    # base the STOP and the FLIP-exit on the HTF line (further away) instead.
    # ALL DEFAULT OFF → live behaviour unchanged until you enable + demo-test.
    ratchet_htf_sl           : bool  = True   # 2026-06-23 ENABLED (evening): H1-line SL = anti-whipsaw. Full backtest BOTH best (DD 4.2→3.6%). Reversible: set False.
    ratchet_htf_flip         : bool  = True   # 2026-06-26: H1 flip-exit ON (user choice). Shadow-sim showed +33% R, lower whipsaw. TP-1.2 backtest used M15 flip, but user prefers the H1-flip edge. Reversible: set False for M15 flip.
    ratchet_htf_tf           : str   = "H1"   # HTF timeframe: "M30" or "H1"
    ratchet_htf_max_risk_pct : float = 2.5    # max SL distance (% of price) when using the HTF line
    ratchet_htf_forming      : bool  = True   # 2026-06-30 (Anisa) ENABLED: use the FORMING (current, not-yet-closed) HTF bar's line — MATCHES the chart indicator's live "SELL Line" value (e.g. 3979.55) instead of the last-closed bar (3988.03). vSL then trails the LIVE line (no hourly lag → less profit give-back). Recomputes per M15 bar. ⚠️ tighter = some premature-tighten on intra-hour noise; needs backtest_replay parity + WFO before live. Default OFF (= last-closed).
    ratchet_tp_regime        : bool  = True   # 2026-06-27 P3 ADOPTED: regime-adaptive TP cap — TP% switches by HMM state at entry (Ranging 2.0 / Trending 1.0 / Volatile 0.8). Won OOS on the live-faithful HTF WFO (+266R/PF3.35 vs global +255R). Reversible: set False = single ratchet_tp_cap_pct. DEMO-test first.
    tp_by_regime : dict = field(default_factory=lambda: {"Ranging": 2.0, "Trending": 1.0, "Volatile": 0.8})
    # 2026-07-13 (night): single source of truth for the regime-adaptive TP cap above —
    # was duplicated as a literal dict in backtest_replay.py + relabel_trades.py +
    # rebuild_trainset.py + shadow_ledger.py (a standing drift-bug risk: change one,
    # forget the others). Everything now imports THIS. Change values here only.
    # STRUCT-H1 EXIT (2026 backtest: +258R vs ratchet +139R over 1yr). Exits a
    # trade when price closes beyond the 1h support/resistance structure.
    # Reversible: set enable_struct_h1_exit=False to fully restore old behaviour.
    enable_struct_h1_exit    : bool  = False  # OFF: additive-on-ratchet gave no edge (≈ratchet). Shadow-logs only. True+pure-replacement needs forward-test for the +258R edge.
    struct_h1_lookback       : int   = 6      # number of completed H1 bars for the structure level
    # Price-based (golden rule): scale with price instead of fixed $.
    ratchet_sl_min_pct       : float = 0.18   # min 1R SL distance = 0.18% of price (~$8 @ 4339). Was fixed $8.
    breakeven_buf_pct        : float = 0.05   # breakeven SL offset = 0.05% of price (~$2 @ 4339). Was fixed $2.
    risk_pct                 : float = 3.0
    # ── Broker-side backstop SL self-heal + wide-trail (2026-07-14, Imtiyaz) ──
    # Context: the broker-side SL sent at trade open (entry ± sl_dist*1.5) was
    # manually deleted mid-trade with no code path to restore or re-trail it —
    # if the app/bridge had crashed afterward, the position would have had ZERO
    # broker-level protection. Fix: the primary vSL monitor loop now periodically
    # (a) restores the broker SL if missing, and (b) trails it forward as the
    # software vSL ratchets, but OFFSET further back than the tight vSL by
    # broker_sl_trail_buffer_mult × sl_dist — wide enough to not be an easy
    # "SL hunt" target (Imtiyaz's own concern), narrow enough to actually
    # tighten as profit locks in. Never loosens (one-way, same as vSL itself).
    broker_sl_sync_enabled       : bool  = True
    # 2026-07-14 (Imtiyaz): widened primary's backstop to match secondary's 3x
    # (was 1.5x) — same hunt-safety reasoning, now symmetric across accounts.
    # broker_sl_open_mult sets the trade-open backstop AND the trail keeps it
    # equal to that same distance thereafter: vSL - trail_buffer_mult*sl_dist
    # must equal entry - open_mult*sl_dist at t=0 (vSL=entry-sl_dist for BUY),
    # so trail_buffer_mult = open_mult - 1.
    broker_sl_open_mult          : float = 3.0    # trade-open broker SL = entry -+ sl_dist * this (primary; secondary's own 3x is separate, in bridge_multi.py)
    broker_sl_trail_buffer_mult  : float = 2.0    # gap behind vSL, in units of sl_dist == broker_sl_open_mult - 1
    broker_sl_sync_interval_sec  : float = 10.0   # throttle — don't resend order_send every monitor tick
    # ── L13 MANUAL-TRADE MANAGER (2026-06-29, Anisa) — auto-manage YOUR manual trades ──
    # A manual trade = an XAUUSD position with magic 0 (the bot uses magic 202600).
    # ⚠️ Places REAL hedge orders → DEMO-TEST HEAVILY. Master switch default OFF.
    manual_manager_enabled   : bool  = True   # 2026-06-29 ENABLED for DEMO-primary test (manage manual trades on demo). Set False to stop.
    manual_risk_pct          : float = 3.0    # cap manual-trade risk at this % of equity — excess lot is CUT (partial-closed) immediately (see bridge_manual.py _enforce_risk_cap).
    manual_sl_pct            : float = 1.0    # SL distance for the manual leg = this % of price
    manual_target_tp_pct     : float = 2.0    # 2026-06-29 TEST: close/hedge both legs at 2% profit. 0 = off.
    manual_hedge_magic       : int   = 202699  # magic stamped on the bot's hedge orders (to track them)
    slave_manual_manager_enabled : bool = False  # 2026-07-15 (Imtiyaz): DISABLED — do NOT manage magic=0 manual trades on secondary/slave accounts (primary manual manager above stays ON). Set True to re-enable.
    slave_manual_manage_interval_sec : float = 5.0  # Throttle slave MT5 reconnect cycles.
    # ── MANUAL-COPY TO SLAVES (2026-07-15, Imtiyaz) — mirror a PRIMARY manual trade to every
    # secondary account, each sized independently at its OWN equity × risk_pct (3%).
    # ⚠️ Places REAL orders on funded accounts → DEMO-TEST before enabling. Default OFF.
    manual_copy_to_slaves_enabled : bool = True   # 2026-07-15 (Imtiyaz): ENABLED LIVE. True = a new manual (magic 0) trade on PRIMARY is mirrored to all secondaries. Set False to stop.
    manual_copy_magic  : int = 202697  # magic stamped on the slave copies. MUST differ from MAGIC (202600) — close_secondary_accounts() closes ALL MAGIC positions whenever the BOT closes its own trade, so sharing the magic would wrongly close these manual copies too.
    # 2026-07-15 (Imtiyaz caught this): "fixed_risk" sizes each slave at the CONFIG risk_pct (3%)
    # regardless of what you actually risked on the primary — so opening 10 lot on a $1.5M primary
    # (= 1% risk) would still open 3% on the slave = 3x MORE risk than you took. "proportional"
    # (default) mirrors YOUR actual risk instead: slave_lot = primary_lot × (slave_eq / primary_eq).
    # sl_dist and contract size cancel out, so it faithfully copies whatever % you chose (1%, 3%, 0.5%).
    manual_copy_mode : str = "proportional"  # "proportional" (mirror your real risk) | "fixed_risk" (always risk_pct)
    # 2026-07-15 (Imtiyaz): what to do when the proportional lot lands BELOW the broker's volume_min
    # (0.01) — e.g. a small primary lot on a huge primary vs a small slave. "round_up" = place the
    # broker minimum anyway (the copy exists, but that slave carries MORE relative risk than the
    # primary — absolute risk is still small at 0.01 lot). "skip" = don't copy at all on that account.
    manual_copy_min_lot_action : str = "round_up"  # "round_up" (Imtiyaz's choice) | "skip"
    # 2026-07-15 (Imtiyaz): HARD CEILING — a slave copy must never risk more than this % of that
    # account, whatever the maths says. Two ways it could otherwise blow past 3%: (a) round_up above
    # (on a small enough account even the broker's 0.01 minimum can exceed 3%), (b) the PRIMARY itself
    # risking >3% — proportional would faithfully mirror that over-risk. If even the broker minimum
    # would breach this ceiling the copy is SKIPPED (can't be placed safely); otherwise the lot is
    # capped down to the ceiling. Set 0 to disable the cap.
    manual_copy_max_risk_pct : float = 3.0
    manual_copy_sl_basis : str = "floor"  # only used by "fixed_risk" mode: "floor" = manual_risk_pct (3% of entry) | "sl" = manual_sl_pct (1%). Ignored in proportional mode (still sets the copy's broker SL/TP levels).
    # ── STUCK-TRADE MANUAL-PROTECT (2026-07-01, Imtiyaz) — if the bot's own close keeps
    # failing at the broker (e.g. retcode 10027 AutoTrading-off, caught live 2026-07-01 on
    # #1519547791), switch that ONE trade to manual-style protection instead of silently
    # retrying forever with just one [ERROR] log line. Bot keeps ownership (magic unchanged —
    # MT5 doesn't allow changing an existing position's magic); this is a code-level flag only.
    stuck_close_fail_threshold : int  = 3      # consecutive failed close attempts before escalating
    stuck_trade_hedge_enabled  : bool = True   # 2026-07-01 Imtiyaz: ENABLED. Places a REAL opposite-
                                                # direction hedge order to neutralise further P&L
                                                # movement when the direct close won't go through.
    stuck_hedge_magic          : int  = 202698  # 2026-07-01: DEDICATED magic, deliberately DIFFERENT
                                                # from manual_hedge_magic (202699) above. L13's
                                                # manual-manager sweeps/closes ALL positions matching
                                                # manual_hedge_magic whenever ITS OWN floor/vSL/TP fires
                                                # (magic-only filter, no comment check) — sharing the
                                                # same magic would let it silently close/interfere with
                                                # a stuck-trade protective hedge that has nothing to do
                                                # with a manual trade. Separate magic = fully isolated.
    # ── GRADUATED stuck-risk hedge (2026-07-01, Imtiyaz's idea). Instead of freezing the
    # WHOLE lot the instant close fails (stuck_trade_hedge_enabled above), let risk stretch
    # from risk_pct (3%) up to leftover_risk_cap_pct (6%) and hedge ONLY the excess lot once
    # unprotected slippage (price past the real vSL while close keeps failing) exceeds that
    # stretched band — tops up incrementally if slippage keeps growing. When this flag is ON
    # it takes priority over stuck_trade_hedge_enabled's full-lot hedge for stuck trades.
    # OFF by default until confirmed live — reversible: set False to fall back to full-lot.
    leftover_excess_hedge_enabled : bool  = False
    leftover_risk_cap_pct         : float = 6.0   # stretched ceiling (risk_pct=3% -> this %)
    # SIZING: dynamic compounding mode (use_fixed_lot=False) — every trade
    # risks risk_pct of CURRENT equity, so lot auto-grows as equity grows.
    # Set 2026-06-14 per user: live with dynamic compounding at 3% risk.
    # ⚠️ WFO showed ~28% max drawdown at 3% risk — aggressive. Feb 2026
    #    was a -4R month. Equity will swing; size the account accordingly.
    use_fixed_lot            : bool  = False
    fixed_lot                : float = 0.01
    # Spread guard: skip entry if (ask-bid) exceeds this $ value.
    # Gold normal spread ~$0.10-0.30; blows out to $0.50-2.00 on news/rollover.
    # 0 = disabled. Added 2026-06-14 (deep audit risk-gap #1).
    max_spread_usd           : float = 0.50
    # When spread is wide, WAIT (re-poll) up to this many seconds for it to
    # normalize, then fire — instead of skipping the whole bar. 0 = no wait
    # (skip immediately). Added 2026-06-14.
    spread_wait_sec          : float = 30.0
    drift_threshold          : float = 0.30
    drift_window             : int   = 50
    use_slot_day_filter      : bool  = False

@dataclass
class XGBConfig:
    n_estimators          : int   = 200
    max_depth             : int   = 4
    learning_rate         : float = 0.05
    subsample             : float = 0.7
    colsample_bytree      : float = 0.7
    min_child_weight      : int   = 8
    gamma                 : float = 0.0
    reg_alpha             : float = 0.0
    reg_lambda            : float = 1.0
    early_stopping_rounds : int   = 30
    random_state          : int   = 42

@dataclass
class SLConfig:
    normal         : float = 1.5
    london_adx     : float = 2.0
    dead_slot      : float = 2.0
    before_event   : float = 1.5
    after_eia_0_15 : bool  = True
    after_eia_15_60: float = 1.8

@dataclass
class HMMConfig:
    n_states     : int   = 3
    n_iter       : int   = 100
    random_state : int   = 42

@dataclass
class GPTConfig:
    """ChatGPT integration settings (gpt_integration.py)"""
    enabled                  : bool  = True   # Enable/disable all GPT features
    api_key                  : str   = ""     # Loaded from OPENAI_API_KEY env var if not set
    model                    : str   = "gpt-4o-mini"  # Model: gpt-4o-mini, gpt-4, gpt-3.5-turbo
    # Feature flags — enable only what you use to save tokens
    enable_news_analysis     : bool  = True   # Analyze economic news → trade filter
    enable_trade_commentary  : bool  = True   # Real-time analysis of active trades
    enable_signal_validation : bool  = False  # Skeptical review of model signals (costs tokens!)
    enable_dashboard_insight : bool  = True   # Dashboard market summary
    enable_backtest_analysis : bool  = True   # Analyze backtest results
    enable_trade_reporting   : bool  = True   # Generate daily/weekly reports
    # Usage limits (to prevent runaway costs)
    max_requests_per_day     : int   = 500    # Daily API request limit
    cache_responses          : bool  = True   # Cache GPT responses for the same input (TTL 1 hour)
    timeout_sec              : float = 10.0   # API timeout
    retry_on_failure         : bool  = True   # Retry failed requests once
    # Logging
    log_all_requests         : bool  = False  # Log every request/response to file (verbose)

@dataclass
class Config:
    paths   : PathConfig   = field(default_factory=PathConfig)
    filters : FilterConfig = field(default_factory=FilterConfig)
    xgb     : XGBConfig    = field(default_factory=XGBConfig)
    sl      : SLConfig     = field(default_factory=SLConfig)
    hmm     : HMMConfig    = field(default_factory=HMMConfig)
    gpt     : GPTConfig    = field(default_factory=GPTConfig)

CFG = Config()
