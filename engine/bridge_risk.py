"""
bridge_risk.py — QUANT GOLD AI v2
Risk management: VirtualTrade tracker, lot sizing, SL/TP math.
No MT5 direct calls — pure calculation layer.
"""
import math
from config import CFG
from datetime import datetime, timezone

try:
    import vsl_persist  # FAB-S4 (2026-07-07): persist vSL across bridge restarts
except ImportError:
    vsl_persist = None

from bridge_constants import (
    log, CFG,
    PARTIAL_CLOSE_ENABLED, PARTIAL_CLOSE_TP2_R,   # used in __init__ (tp2 calc)
    RATCHET_FLIP_EXIT,                            # used in ratchet_bar_update
    RATCHET_BUF_PCT,                              # 2026-06-30: %-based trail buffer
    RISK_PCT,                                     # used in calc_lot
    # L7b 2026-06-29: TRAIL_AFTER_R, BREAKEVEN_BUFFER, TRAILING_SL, PARTIAL_CLOSE_R,
    # PARTIAL_BE_*, SMART_EXIT_* imports removed — only the deleted _update_buy/_sell/
    # _smart_exit_check used them (dead in pure-ratchet mode).
)


class VirtualTrade:
    """
    Tracks a single open position's virtual SL, trailing, and partial close.
    Called every 2 seconds from monitor loop.
    Returns action string: None | 'CLOSE' | 'SMART_CLOSE' | 'PARTIAL_CLOSE'
    """

    def __init__(self, ticket, direction, entry, virtual_sl, tp, lot, sl_dist,
                 ratchet=False, ratchet_buf=0.0):
        self.ticket      = ticket
        self.direction   = direction   # 'BUY' or 'SELL'
        self.entry       = entry
        self.virtual_sl  = virtual_sl
        self.original_sl = virtual_sl
        self.tp          = tp
        self.lot         = lot
        self.sl_dist     = sl_dist     # $ distance of 1R

        self.breakeven          = False
        self.trailing           = False
        self.partial_be         = 0          # 0=none, 1=first step, 2=second step
        self.partial_close_done = False

        # RATCHET mode (EA-style): vSL follows the trend line one-way;
        # NO PBE / partial / BE / R-trail / smart-exit — line + flip decide.
        self.ratchet     = ratchet
        self.ratchet_buf = ratchet_buf      # $ buffer at entry (pct → $ fixed)
        self._flip_close = False

        self.open_time      = datetime.now(timezone.utc).replace(tzinfo=None)
        self.max_profit     = 0.0       # peak R
        self.max_profit_usd = 0.0       # peak $
        self.smart_exit_reason = ""

        # Extended TP for the 50% leg after partial close
        if PARTIAL_CLOSE_ENABLED and sl_dist > 0:
            tp2_dist = sl_dist * PARTIAL_CLOSE_TP2_R
            self.tp2 = round(entry + tp2_dist, 2) if direction == "BUY" \
                else round(entry - tp2_dist, 2)
        else:
            self.tp2 = tp

    # ─────────────────────────────────────────────────────────
    def update(self, current_price, pt=0.0) -> str | None:
        """Update vSL every 2s. The system is pure RATCHET (line + flip decide) — every
        live trade is created ratchet=True (a non-ratchet trade is skipped at execute()),
        so this always routes to _update_ratchet. The old non-ratchet path (PBE / partial
        close / full-breakeven / R-trail / smart-exit in _update_buy/_update_sell) was
        unreachable dead code and was removed 2026-06-29 (L7b). `pt` kept for call-site
        compatibility (unused)."""
        return self._update_ratchet(current_price)

    # ── RATCHET (EA-style) — 2s tick check ───────────────────
    def _update_ratchet(self, price) -> str | None:
        """Only the line decides: vSL cross → CLOSE. Trail/flip are
        applied per closed bar via ratchet_bar_update()."""
        s = 1 if self.direction == "BUY" else -1
        profit_r   = s * (price - self.entry) / self.sl_dist if self.sl_dist else 0.0
        profit_usd = s * (price - self.entry) * self.lot * 100
        self.max_profit     = max(self.max_profit, profit_r)
        self.max_profit_usd = max(self.max_profit_usd, profit_usd)
        if self._flip_close:
            return "CLOSE"
        if (price <= self.virtual_sl) if s == 1 else (price >= self.virtual_sl):
            return "CLOSE"
        return None

    # ── RATCHET — closed-bar update (line trail + flip exit) ──
    def ratchet_bar_update(self, line: float | None, flip: int) -> str | None:
        """Called once per NEW closed M15 bar.
        line: current ratchet line on the trade's side (None = trend against).
        flip: +1 BUY flip / -1 SELL flip / 0 none, on that closed bar.
        Returns 'FLIP_CLOSE' if the opposite flip ends the trade."""
        if not self.ratchet:
            return None
        s = 1 if self.direction == "BUY" else -1
        if RATCHET_FLIP_EXIT and flip == -s:
            self._flip_close = True
            log.warning(f"  🔄 #{self.ticket} opposite flip — RATCHET exit")
            return "FLIP_CLOSE"
        if line is not None:
            # 2026-06-30 (Anisa): buffer = 0.20% of the CURRENT line (recomputed each bar),
            # not a fixed $ from entry → vSL = line ∓ 0.20%·line, tracks the live line exactly.
            _buf = line * RATCHET_BUF_PCT / 100.0
            new_sl = round(line - s * _buf, 2)
            if (s == 1 and new_sl > self.virtual_sl) or (s == -1 and new_sl < self.virtual_sl):
                self.virtual_sl = new_sl
                self.trailing   = True
                log.info(f"  ⚡ #{self.ticket} RATCHET trail: vSL→{self.virtual_sl:.2f}")
                # FAB-S4: persist trailed vSL so a restart mid-trail keeps the gain.
                if vsl_persist is not None:
                    try:
                        vsl_persist.save(self.ticket, self.virtual_sl, self.sl_dist,
                                         self.direction, self.entry,
                                         breakeven=self.breakeven, trailing=self.trailing)
                    except Exception as _e:
                        log.warning(f"  vsl_persist trail save fail #{self.ticket}: {_e}")
        return None

    # ── L7b (2026-06-29): _update_buy / _update_sell / _smart_exit_check REMOVED —
    # dead code, unreachable in pure-ratchet mode (every live trade is ratchet=True;
    # update() always routes to _update_ratchet). PBE / partial-close / full-breakeven /
    # R-trail / smart-exit are NOT part of the live strategy.

    # ── Status dict (for dashboard / monitor log) ─────────────
    def status(self, current_price) -> dict:
        if self.direction == "BUY":
            pnl_pts  = current_price - self.entry
            sl_dist  = abs(current_price - self.virtual_sl)
            profit_r = pnl_pts / self.sl_dist if self.sl_dist else 0
        else:
            pnl_pts  = self.entry - current_price
            sl_dist  = abs(self.virtual_sl - current_price)
            profit_r = pnl_pts / self.sl_dist if self.sl_dist else 0

        if self.ratchet:
            mode_lbl = "⚡Ratchet"
        elif self.partial_close_done:
            mode_lbl = "✂️PC→3R"
        elif self.trailing:
            mode_lbl = "📈Trail"
        elif self.breakeven:
            mode_lbl = "🔒BE"
        elif self.partial_be > 0:
            mode_lbl = f"📐PBE{self.partial_be}"
        else:
            mode_lbl = "Open"

        return {
            "ticket":             self.ticket,
            "direction":          self.direction,
            "entry":              self.entry,
            "current":            current_price,
            "virtual_sl":         self.virtual_sl,
            "tp":                 self.tp,
            "tp2":                self.tp2,
            "pnl_$":              round(pnl_pts * self.lot * 100, 2),
            "profit_R":           round(profit_r, 2),
            "sl_dist_$":          round(sl_dist, 2),
            "breakeven":          self.breakeven,
            "trailing":           self.trailing,
            "partial_be":         self.partial_be,
            "partial_close_done": self.partial_close_done,
            "max_profit_R":       round(self.max_profit, 2),
            "mode_label":         mode_lbl,
        }


# ── Lot sizing ────────────────────────────────────────────────

def calc_lot(balance, sl_pts, sym_info=None) -> float:
    """
    Risk-based lot size.
    lot = (balance × RISK_PCT%) / sl_pts
    Respects broker min/max/step.
    """
    import MetaTrader5 as mt5
    from bridge_constants import SYMBOL   # FIX #18: was hardcoded "XAUUSD.pc"
    si = sym_info or mt5.symbol_info(SYMBOL)
    vol_min  = si.volume_min  if si else 0.01
    vol_max  = si.volume_max  if si else 50.0
    vol_step = si.volume_step if si else 0.01

    # M3: fixed-lot forward-test mode — bypasses %-risk sizing entirely
    if getattr(CFG.filters, "use_fixed_lot", False):
        fl = getattr(CFG.filters, "fixed_lot", 0.01)
        if vol_step > 0:
            fl = max(vol_min, min(round(fl / vol_step) * vol_step, vol_max))
        return round(fl, 2)
    raw = (balance * RISK_PCT / 100) / (sl_pts if sl_pts > 0 else 200)
    # FAB-S3 (2026-07-07): live multi-day drawdown brake — mirrors backtest M3.
    # Protective only (scale ∈ {1.0, 0.5, 0.25, 0.0}); config-gated default OFF.
    try:
        import dd_brake as _ddb
        _scale = _ddb.risk_scale(balance)
        if _scale < 1.0:
            log.warning(f"  🛡️ DD brake active: risk scaled ×{_scale} (balance ${balance:.0f})")
        raw *= _scale
    except Exception as _de:
        log.warning(f"  dd_brake sizing skipped: {_de}")
    if raw <= 0:
        return 0.0   # halt band — caller treats 0 lot as "skip sizing"
    if vol_step > 0:
        raw = math.floor(raw / vol_step) * vol_step
    return round(max(vol_min, min(raw, vol_max)), 2)


# calc_sl_points (ATR-based SL) removed 2026-06-19 — system is pure ratchet only.
