# QGAI v2 — Changelog #4 (2026-06-19 → 06-23)

Continues FIXES_CHANGELOG / 2 / 3. Same convention: changes tagged in code with
dated comments (search files for `2026-06-19` / `2026-06-22`). All config flags
are reversible (old values noted inline). **Test on DEMO before live.**

Worked on by Anisa via Cowork. Shared PC / shared folder — this file is the history record.

---

## 2026-07-15 — NEW: mirror PRIMARY manual trades to SLAVE accounts, each at its own 3% risk (Imtiyaz) — BUILT, default OFF
**Request (Imtiyaz):** "if I open a manual trade in primary, it should copy to slaves, sized on 3%
risk of that slave."
**Reused (not rebuilt):** `bridge_multi._execute_on_account()` already sizes each secondary from its
OWN equity via `calc_lot(equity, sl_p, si)` = that account's equity × `RISK_PCT` (3%) — exactly the
requested sizing, already proven live by the bot's own replication.
**Built:**
- `config.py`: `manual_copy_to_slaves_enabled` (**default False** — master switch),
  `manual_copy_magic = 202697`, `manual_copy_sl_basis = "floor"`.
- `bridge_multi.py`: `_execute_on_account()` gained optional `magic` + `skip_if_open_magic` params
  (both default None → the bot's own path is byte-for-byte unchanged);
  `close_secondary_accounts(magic=None, label=...)` is now magic-scopeable (default = MAGIC =
  unchanged); NEW `execute_manual_copy_to_secondaries()` + `close_manual_copies_on_secondaries()`.
- `bridge_manual.py`: `manage(sym=None, mirror_to_slaves=False)` — mirrors on the `st is None`
  (new combined manual position) branch, and closes the copies on ALL FOUR exit paths (floor
  breach / vSL breach / target TP / user closed it by hand).
- `bridge_main.py`: the primary call site passes `mirror_to_slaves=True`. The slave-side manager
  never mirrors (it would copy a slave's own trade back out to the other slaves).
**Two real hazards, both explicitly handled + tested:**
1. **Magic collision** — `close_secondary_accounts()` closes ALL `magic == MAGIC` (202600) positions
   on secondaries and runs every time the BOT closes its own trade. Had the copies shared that magic,
   **the bot closing its own trade would have wrongly closed Imtiyaz's manual copies too.** Copies use
   a separate magic (202697) and a magic-scoped close.
2. **Restart duplicate** — `bridge_manual._managed` is in-memory, so after a bridge restart the
   `st is None` branch re-fires for an ALREADY-mirrored manual trade → would open a DUPLICATE real
   position. Guard: before placing, `_execute_on_account` asks the BROKER (real source of truth, not
   in-memory state) whether that slave already holds a `manual_copy_magic` position, and skips if so.
**Sizing basis (`manual_copy_sl_basis`, default `"floor"`):** slave lot is sized off the manual
trade's real max-loss distance (`manual_risk_pct`, 3% of entry) — so a slave risks its own 3% if
price reaches that floor, a faithful mirror of the primary's risk. `"sl"` instead uses the tighter
`manual_sl_pct` (1%) → ~3× bigger slave lot.
**Verified:** offline test (`scratchpad/test_manual_copy.py`, mocked MT5 — no live terminal, no real
order) **11/11 PASS**: default-OFF places zero orders; enabled mirrors to both slaves; every copy
carries 202697 and none carries 202600; a slave already holding a copy is skipped (1 order, not 2);
both-already-mirrored → zero duplicates on restart re-fire; the manual close touches only 222/444
(copies) and never 111/333 (bot trades); and the bot's own close still closes only 111/333 and never
the copies. Python syntax clean on all 5 edited files.
**⚠️ NOT YET LIVE — `manual_copy_to_slaves_enabled = False`.** Places REAL orders on funded accounts.
DEMO-test first, then set True + restart. Takes effect on bridge restart (config read at start).
**Not covered (deliberate, documented):** adding a 2nd manual leg later changes the primary's net
volume/avg entry but does NOT re-mirror or resize the existing slave copies (`st` stays non-None) —
the copies keep their original size. Decide a policy if that becomes a real workflow.

## 2026-07-15 — Manual-trade manager DISABLED on secondary/slave accounts (Imtiyaz)
**What:** `config.py` `slave_manual_manager_enabled` **True → False**. The PRIMARY manual-trade
manager (`manual_manager_enabled`) is UNCHANGED (still True) — this only stops the bridge from
auto-managing magic=0 (manual) trades on secondary/slave accounts.
**Effect:** `bridge_multi.manage_secondary_manual_accounts()` already returns early on this flag
(`bridge_multi.py:338`), so with it False the bridge no longer connects to each slave every ~5s to
combine/floor/ratchet/TP-manage manual positions there. A manual trade opened on a slave from now on
gets **NO bot-side protection** (no virtual SL, no 3%-floor auto-close, no ratchet) — it must be
managed by the operator or the flag re-enabled.
**Safe to flip now:** verified no slave manual position was open at the time — TradeQuo-001 showed
`0 open` in the 21:00 account summary (the manual trade opened earlier today was already closed), so
nothing in-flight got stranded.
**Takes effect on next bridge restart** (config.py is read once at process start).
**Reversible:** set `slave_manual_manager_enabled = True`. `config.py` syntax re-checked clean.
Also logged in `FILTERS_MASTER.md` (status table + §CHANGE LOG).

## 2026-07-15 — DD-brake fix regressed itself: cross-account contamination corrupted TradeQuo's peak, blocked a real SELL replication (Imtiyaz reported)
**Symptom:** Imtiyaz noticed the primary fired a SELL (`Trade#3 SELL 17.41 XAUUSD #1598684643`,
20:45:29) and it replicated to VantageCentLive, but **TradeQuo-001 did not get the SELL at all.**
**Trace:** `bridge.log` right after the primary fill: `🛡️ DD brake active: risk scaled ×0.0 (balance
$5056)` immediately followed by `❌ [multi] TradeQuo-001 order rejected: 10014` (invalid volume —
×0.0 scale means lot rounds to 0, which MT5 rejects outright). `logs/dd_peak.json` showed TradeQuo's
peak had jumped from the correct ~$5053 (set earlier the same day, see the entry below) to
**$9519.88** — but `bridge.log`'s own `TradeQuo-001 connected | balance=...` lines show its balance
sat at **$5046-5064 the entire day**, never near $9.5k. No real deposit ever happened.
**Root cause: a regression in THIS SAME DAY's own deposit/withdrawal-aware `dd_brake.py` fix.** That
fix's `_balance_ops()` reads `mt5.history_deals_get()` from "whichever account MT5 is currently
connected to" with no verification. This bridge switches its single MT5 connection between the
primary and each secondary every few seconds (multi-account replication + the secondary manual-trade
manager) — right after a fresh `mt5.login()`, the terminal's internal history cache does not always
settle instantly, so `history_deals_get()` can momentarily still reflect a DIFFERENT (likely the much
larger primary) account's balance deals. One of those got misread as a ~$4466 "deposit" and added to
TradeQuo's peak, inflating it to $9519.88 against a real ~$5055 equity → computed drawdown ~47% →
past the 30% halt band → scale ×0.0 → lot 0 → broker rejected the SELL replication outright.
**Fix (`dd_brake.py`, `bridge_risk.py`, `bridge_multi.py`):** added `_connection_matches(expected_key)`
— verifies `mt5.account_info().login` actually equals the account being sized for RIGHT NOW before
trusting any balance-history read; on any mismatch (or error), treats balance ops as empty for that
cycle instead of risking corruption (fail closed: a missed same-tick adjustment is safe, a wrong one
is not). `calc_lot()` gained an optional `account_id` param so `bridge_multi._execute_on_account()`
can pass the login it JUST explicitly logged into, rather than dd_brake guessing from "whatever's
connected now". Primary's own sizing call (`bridge_core.py`) is unaffected (no `account_id` passed,
same fallback-to-current-login behavior as before).
**Immediate mitigation:** reset TradeQuo's peak in `logs/dd_peak.json` back to its real ~$5055.68
after the bridge restart (had to wait for restart — the OLD buggy code was actively rewriting the
file every ~20-50s, any reset attempted while it was still running would likely have been
immediately re-corrupted).
**Verified:** offline test extended with 3 new assertions (mismatched connection → scale stays 1.0,
no false brake; peak NOT contaminated by a stray deal; matched connection → a genuine deposit still
applies correctly) — all 8/8 scenarios PASS. Live, post-restart: `dd_peak.json`'s TradeQuo entry got
touched again by the running bridge (`updated` timestamp advanced) but `peak_equity` stayed exactly
5055.68 — no re-corruption. Zero errors in `bridge.log` since restart. No `DD brake active` warning
since (correctly no longer false-triggering).
**Lesson:** a same-day live-trading fix needs to be evaluated against this bridge's specific
rapid-multi-account-switching architecture, not just against isolated unit-test logic — the original
5-scenario test suite was logically correct but didn't model connection-timing races, which is
exactly where this one lived. Added scenario 6 to the permanent test file to prevent a silent
regression.

## 2026-07-15 — Slave manual-trade vSL never ratcheted (wrong symbol on secondary accounts) (Imtiyaz reported)
**Symptom:** Imtiyaz added a manual trade on a SECONDARY (slave) account (TradeQuo, symbol
`XAUUSDs`). `bridge.log` showed the manual manager picking it up every ~5s
(`[multi-manual] TradeQuo-001: managing 1 manual position(s) on XAUUSDs`) but ALSO logged
`⚡ ratchet HTF(H1): copy_rates failed — no state` on every cycle.
**Root cause:** `bridge_ratchet.get_htf_state()` / `get_state()` hard-coded the PRIMARY `SYMBOL`
(`XAUUSD`) in `mt5.copy_rates_from_pos(...)`. When `bridge_manual.manage()` runs on a slave whose
symbol differs (`XAUUSDs`), it was connected to the slave but asked for the PRIMARY symbol's bars —
the slave broker has no `XAUUSD`, so `copy_rates` returned None → ratchet line = None → the slave
manual trade's **vSL never trailed**. Its hard 3%-floor still protected it (confirmed:
`🛡 [XAUUSDs] COMBINED manual 0.04 lot @ avg 4048.37 → VIRTUAL vSL ON, 3% floor @ 3926.92`), but it
could give back all profit down to that wide floor because the profit-locking ratchet was dead.
Impact was limited to secondary accounts whose symbol ≠ the primary's; the primary itself was fine.
**Fix:** made `get_state()` / `get_htf_state()` symbol-aware — added an optional `symbol=None` param
(defaults to primary `SYMBOL`, so all existing primary callers in `bridge_core.py` are byte-for-byte
unchanged), and converted the module's single `_cache` / `_htf_cache` to PER-SYMBOL dicts so a slave
line can't collide with the primary's cached line. `bridge_manual.manage()` now passes its own `sym`
through to both calls.
**Verified:** offline test (mocked MT5, 6 assertions) all PASS — symbol-less call still defaults to
primary; `symbol="XAUUSDs"` routes to XAUUSDs; HTF variant likewise; an unknown symbol returns None
(no cross-symbol leak); primary and slave states are cached as separate objects. Python syntax OK on
both edited files.
**Takes effect on next bridge restart** (Python modules load once). Until then the slave manual
trade stays floor-protected but non-ratcheting.

## 2026-07-15 — DD brake counted a WITHDRAWAL as drawdown → wrongly halved TradeQuo risk (Imtiyaz reported)
**Symptom:** Imtiyaz noticed the smaller secondary account VantageCentLive ($3,640) was trading a
LARGER lot (0.05) than the bigger TradeQuo-001 ($5,046, lot 0.04) — inverted from risk-proportional
sizing.
**Trace:** the live DD brake (`dd_brake.py`, FAB-S3) was scaling TradeQuo's risk ×0.5 — confirmed in
`bridge.log` (`🛡️ DD brake active: risk scaled ×0.5 (balance $5046)`) and `logs/dd_peak.json`
(TradeQuo login 125961163 peak $5917.37 vs current $5046 = 14.7% "drawdown" → ½-size band). Lot math
verified exact: Vantage `(3640.78×3%)/1866pts×1.0 = 0.05`; TradeQuo `(5046.04×3%)/1866pts×0.5 = 0.04`.
**Root cause (Imtiyaz clarified, MT5 history screenshot confirmed):** the $5917→$5046 drop was NOT a
trading loss — it was a **$814 WITHDRAWAL** of trading profit (account history: Deposit $5,046,
lifetime trading Profit **+$814.04**, Withdrawal −$814.00, Balance $5,046.04 — i.e. zero net trading
drawdown, the account only ever made money). `risk_scale()` compared current equity to a persisted
equity peak and had NO awareness of deposits/withdrawals, so a withdrawal looked identical to a loss.
**Immediate fix (live, no restart needed):** reset TradeQuo's stale peak in `logs/dd_peak.json`
($5917.37 → current equity); the running bridge re-anchored it to $5053.12 on the next connect →
drawdown ~0% → ×1.0 full risk, matching Vantage. VantageCentLive left untouched (Imtiyaz: "keep as
is vantage").
**Permanent fix (`dd_brake.py`, takes effect on next bridge restart):** made `risk_scale()`
deposit/withdrawal-aware. Added `_balance_ops()` — reads the connected account's `DEAL_TYPE_BALANCE`
(+ CREDIT/CORRECTION/BONUS/CHARGE) deals from MT5 history (120-day rolling window) — and each sizing
call now shifts the stored peak by any NEW balance operation (withdrawal ↓ peak by the exact amount
withdrawn, deposit ↑ peak), so only genuine trading losses can move equity below the peak. Idempotent:
each balance deal is applied at most once, tracked by ticket in a new `applied_balance_deals` list in
the state file. Existing state migrates safely one-time (baselines current ops as already-accounted,
never retroactively double-subtracts). Protective-only contract preserved (can only reduce size).
**Verified:** offline logic test (mocked MT5 history, 5 scenarios) all PASS — withdrawal → no brake
(×1.0, peak lowered by exactly the withdrawal); real 15% trading loss → still brakes (×0.5); deposit
→ no brake (peak raised); withdrawal-then-real-12%-loss → brakes only on the real loss; same
withdrawal seen twice → peak adjusted once (idempotent). Python syntax check passed.

## 2026-07-15 — Proactive AutoTrading-off detection + dashboard banner (Anisa)
**Context:** Anisa intentionally disabled AutoTrading in the MT5 terminal to test system behavior
under that condition (not a bug report). Investigating `bridge.log` surfaced the full mechanics of
a prior real incident from this same cause: ticket #1550707233 (BUY 11.34 lot, opened 2026-07-07
17:15) had its virtual SL breach correctly detected by the bot starting 2026-07-08 14:02, but
EVERY close attempt was rejected by the broker with retcode 10027 ("AutoTrading disabled by
client") — including the existing STUCK-TRADE MANUAL-PROTECT hedge fallback (`bridge_session.py`,
2026-07-01 spec), since a hedge is also a new order and hits the same restriction. The position sat
open and unprotected for ~31 hours (15,923+ consecutive close failures logged) until AutoTrading
was re-enabled around 2026-07-09 21:15, when it finally closed for **-$25,424.96**, triggering a
daily-SL halt for the rest of that day.
**Root gap identified:** the bridge only discovers "AutoTrading is off" REACTIVELY -- after an
order already failed -- inferring it from retcode 10027 in a log message ("likely AutoTrading is
OFF"). A direct, definitive check (`mt5.terminal_info().trade_allowed`) already existed in the
standalone `diag_mt5.py` diagnostic script but was never wired into the live loop or the dashboard.
**Fix (monitoring/alerting addition, not a change to trading/risk logic):**
- `bridge_dashboard.py`: added `_check_autotrading()` -- a cheap, read-only `mt5.terminal_info()`
  call (no order sent) -- as a new `"autotrading"` row inside `build_system_health()`, and folded
  its `"ERROR"` status into the panel's existing overall-status rollup.
- Added a top-level `"autotrading_enabled"` boolean to the main `dash` dict in `write_dashboard()`
  (computed once via a new `_sys_health` local, reused for both the health panel and this flag --
  avoids calling `build_system_health()` twice).
- `dashboard.html`: added a new `#autotrading_banner` bar (same visual language/CSS as the existing
  `#danger_banner` -- red, flashing) that shows immediately when `d.autotrading_enabled === false`,
  independent of the daily-loss-driven banner. Added to the same conditional-bars list as
  `danger_banner`/`sl_progress_wrap` so it renders as a plain sibling above the GridStack grid.
**Verified:** Python syntax check passed; live browser test confirmed the banner element exists
(hidden by default, `display:none`), and manually toggling its class to `show` renders it correctly
(red text/border, flashing animation, correct message) with no console errors.
**Net effect:** a future AutoTrading-off event (accidental or intentional) now surfaces on the
dashboard within one poll cycle, instead of only being discoverable via `bridge.log` after a
position already needed (and failed) an emergency close.

## 2026-07-15 — SIGNAL + SIGNAL LOG equal-height fix: root-caused GridStack transition bug (Imtiyaz reported)
**What:** Imtiyaz wanted SIGNAL and SIGNAL LOG panels to be EXACTLY the same height with no dead
space and no scrollbar, resize handle ("↘") removed, and the fix done WITHIN GridStack (not by
moving panels out of GridStack).
**Root cause found (after extensive debugging):** GridStack's `grid-stack-animate` class adds
`transition: left 0.3s, right 0.3s, top 0.3s, height 0.3s, width 0.3s` to all `.grid-stack-item`
elements. When programmatically setting an item's inline `style.height` (or via `_gsGrid.update()`),
the `height 0.3s` transition PREVENTS the new value from taking effect — the browser cannot
properly interpolate from the original `calc(N * var(--gs-cell-height))` value to a pixel value,
so the element stays locked at its original computed height. Confirmed: inline `height: 168px
!important` shows in `cssText` but `getComputedStyle().height` returns `280px`; with the class
removed, the same inline change takes effect instantly.
**Fix — 3 parts:**
1. **CSS transition override:** added a rule that excludes `height` from the transition for
   signal/signal_log items specifically: `.grid-stack-animate .grid-stack-item[gs-id="signal"],
   .grid-stack-animate .grid-stack-item[gs-id="signal_log"]{transition:left .3s,right .3s,top .3s,
   width .3s!important}` — other panels keep their height animation.
2. **`_syncSignalLogToSignalHeight()` rewritten:** measures `panel_signal`'s exact content height
   via `getBoundingClientRect()`, updates GridStack's `gs-h` attribute via `_gsGrid.update()` for
   positioning of items below, then sets EXACT pixel height on both grid-stack-items + sets
   `panel_signal_log`'s panel height to match. No row-quantization gap.
3. **Resize handle removed:** CSS `display:none!important` on `.grid-stack-item>.ui-resizable-handle`.
**Also reverted:** signal/signal_log entries restored to PANEL_CONFIG (had been incorrectly removed
in the previous session); `#signal_pair_row` CSS Grid wrapper removed (it was a workaround for
the same transition bug, now properly fixed).
**Verified (JS measurements, page reload):** both items 276px height, top-aligned at y=238,
side-by-side (6+6 cols), heights match within <1px, resize handle display=none, no console errors.

**Follow-up same day (Imtiyaz reported, screenshot: native scrollbar with up/down arrow buttons
overlapping the SIGNAL box's WIN PROB/RATCHET area):** Root cause: `.grid-stack-item-content`
(line ~230) has `overflow:auto` with no `scrollbar-width:thin` styling, unlike other scrollable
areas in this file (`.sl-body`, `#liveSigRows`, `.tcard` all set `scrollbar-width:thin`) -- so it
renders the browser's bulky default scrollbar. A 1px sub-pixel rounding gap between
`panel_signal`'s exact content height and `.grid-stack-item-content`'s computed height (both set
independently, one via JS pixel height, one via GridStack's `inset:1px`) was just enough to
trigger it. Fix: `.grid-stack-item[gs-id="signal"]>.grid-stack-item-content,
.grid-stack-item[gs-id="signal_log"]>.grid-stack-item-content{overflow:hidden}` -- safe because
both panels already manage their own internal overflow (`panel_signal` has
`overflow:hidden!important`; `panel_signal_log` scrolls internally via its own `.sl-body`).
**Verified live:** both wrappers' computed `overflow-y` = `hidden`, `offsetWidth-clientWidth` = 0
(no scrollbar reserved width) on both, heights still match.

**Correction same day (Imtiyaz: "you remove resize option from all box panal it is wrong... put it
in ↘ all panal box as it is"):** the `.grid-stack-item>.ui-resizable-handle{display:none!important}`
rule added earlier (misreading of a request that was actually about a scrollbar, not the resize
handle) had hidden the ↘ resize-corner icon on EVERY panel, not just signal/signal_log. Removed
that rule entirely -- restores GridStack's original per-panel resize-handle behavior everywhere
(handle only renders in Edit Mode, per `enableResize(true)`/`disableResize:true` toggle, unchanged).
**Verified live:** confirmed via `document.styleSheets` that the override rule is gone and only
GridStack's own built-in `.ui-resizable-handle` rules remain; SIGNAL/SIGNAL LOG height-match and
no-scrollbar fixes above are unaffected (unrelated CSS).

## 2026-07-15 — Hours Heatmap always overlaps the panel above it after Save (Imtiyaz reported, screenshot)
**Root cause:** `_tightenLowerOuterGaps()` (added 2026-07-11 to visually close row-quantization gaps
around Signal History/Hours Heatmap/Closed Trades) worked by writing a hardcoded pixel offset
directly onto each panel's `.grid-stack-item` `style.top` (e.g. `calc(11 * cellHeight - 13px)`),
bypassing GridStack's own `top = y * cellHeight` positioning entirely. Two problems compounded:
(1) the function explicitly no-ops during Edit Mode (`if(_gsEditMode) return`) so it never
recalculates while the user drags/resizes panels, and (2) it was never re-triggered right after
`gsSaveLayout()`/`gsExitEdit()` either -- so the moment editing shifted any panel's real `gs-y` row,
the STALE pre-edit pixel offset stayed applied on top of the NEW row position, visually pulling
Hours Heatmap up into whatever panel now sat above it. The offset only got recalculated (and the
overlap silently disappeared) on the next per-poll cycle, which is why it looked like it happened
"every time right after Save."
**Also found:** the gap this hack was compensating for no longer exists -- `_fitPanelToGrid()`
(genuine GridStack row-height shrink, fixed 2026-07-14) already closes it to 0px on its own; the
pixel-pull was redundant on top of being unsafe.
**Fix:** removed `_tightenLowerOuterGaps()`'s body entirely (kept as a no-op stub since 3 call
sites still reference it) -- panels now rely solely on `_fitPanelToGrid()`'s real row updates.
**Verified live:** measured gaps between Signal History/Hours Heatmap/Closed Trades = 0px with
clean `top: calc(N * var(--gs-cell-height))` (no pixel subtraction) in the normal state, AND after
simulating a full enter-edit → move → `gsSaveLayout()` → exit-edit cycle -- no overlap in either
case, no console errors.

## 2026-07-15 — Panel width alignment check + missing viewport meta tag (Imtiyaz reported, screenshot)
**What:** Imtiyaz flagged panel widths looking uneven/not fitting the browser. Investigated at
1366px and 1920px width (his real laptop, maximized, 100% zoom): all `.grid-stack-item` left
edges align within 0-2px, no horizontal scroll, dashboard content fills the full viewport width
with no gap. The SIGNAL (half-width, paired with SIGNAL LOG) vs HOURS/Signal History/Closed
Trades (full-width) size difference Imtiyaz initially flagged is confirmed intentional design
(explicitly approved earlier this session), not a bug.
**Found + fixed regardless (real, separate issue):** the file had **no `<meta name="viewport">`
tag** at all -- added `<meta name="viewport" content="width=device-width, initial-scale=1">`.
Without it, mobile browsers fall back to a virtual ~980px canvas and zoom the whole page down to
fit the real screen, which is a genuine cause of cramped/uneven-looking panels on a phone (though
not what today's laptop screenshot showed).

## 2026-07-15 — Inner stat-box border color didn't match main panel border (Imtiyaz reported, screenshot)
**What:** Imtiyaz pointed out the outer panel border and the border on small inner stat-boxes
looked different.
**Root cause:** the outer panel border (`.tcard`, all main panels) uses `var(--border)`
(`#0d2535`), but a dashboard-wide shared style block ("Shared highlighted metric boxes", ~line 680:
`.r-cell,.sig-hero-mini,.trade-item,.mauc,.rc,.slot-big-box,.ftc-item`) plus two more standalone
rules (`.sig-hero-mini` ~line 164; `.why-factor-cell,.why-matrix .r-cell,.market-tools-col .trow`
~line 203) all hardcoded a different, slightly lighter blue `#123247` instead of reusing the
`--border` variable -- a deliberate-looking but inconsistent design choice affecting stat-boxes
across the ENTIRE dashboard (not just SIGNAL panel).
**Confirmed scope with Imtiyaz before changing** (broad, dashboard-wide change): fix all inner
boxes to match the main panel color, not just the one panel in the screenshot.
**Fix:** replaced all 3 occurrences of hardcoded `#123247` with `var(--border)`.
**Verified live:** `getComputedStyle` on outer panel vs `.sig-hero-mini` now both return
`rgb(13, 37, 53)` (`#0d2535`) -- exact match. No `#123247` left in the file (grep confirmed 0
matches).

## 2026-07-15 — Panel border different in Edit Mode vs View Mode (Imtiyaz reported)
**What:** Imtiyaz noticed panel borders looked different while editing the layout vs normal
viewing.
**Root cause:** `body.gs-edit-mode .grid-stack-item-content{outline:1px dashed rgba(0,212,255,.3)}`
(~line 236) added an extra dashed cyan outline around every panel only during Edit Mode (plus a
brighter cyan on hover), layered on top of the normal solid `var(--border)` border -- an
intentional "which panels are editable" indicator, but it meant the two modes never looked the
same. Confirmed with Imtiyaz before removing (broad, dashboard-wide visual change): wanted View
and Edit mode borders to match exactly, not keep the indicator.
**Fix:** removed both outline rules (base + hover state); kept the unrelated `.gs-drag-handle`
grab-cursor/background rules, which aren't part of the border complaint.
**Verified live:** `getComputedStyle` on `panel_signal`'s border AND its `.grid-stack-item-content`
wrapper's outline are now byte-identical between View Mode and a live `gsEnterEdit()` call --
`1px solid rgb(13,37,53)` border, `none` outline, in both modes.

## 2026-07-15 — HOURS heatmap cells had no border at all, unlike other stat-boxes (Imtiyaz reported, screenshot)
**What:** Imtiyaz's screenshot (EV box + SIGNAL HISTORY + HOURS heatmap) showed the HOURS
heatmap's hour-cells (01:00, 02:00, etc.) still looking inconsistent with the "EV" box even after
the earlier `#123247`->`var(--border)` fix.
**Root cause:** `.heat-cell` (~line 492) never had a border on top/left/right AT ALL --
`border-bottom:3px solid transparent` (colored per win-rate tier via `.tier-best/.tier-good/
.tier-ok/.tier-weak`) was its ONLY border property, unlike `.sig-hero-mini`/other stat-boxes which
have a full 1px border on all 4 sides. Confirmed with Imtiyaz before changing (would affect every
hour-cell across the Hours Heatmap panel): add a full border while preserving the win-rate
tier-color accent.
**Fix:** added `border:1px solid var(--border)` before the existing `border-bottom:...` override
(CSS cascade lets the more specific bottom-only declaration win for that one side), so each cell
now has a full border like other stat-boxes, PLUS its distinct colored bottom accent.
**Verified live:** all sampled heat-cells show `border-top: 1px solid rgb(13,37,53)` (exact match
to the EV box's border color) while `border-bottom` correctly still varies by tier (green #00ff88
for tier-best, orange #ffaa00 for tier-ok, cyan #00c8ff for tier-good) -- both properties coexist
as intended, no console errors.

## 2026-07-15 — Ticker-pill borders unified + a real pre-existing bug found along the way (Imtiyaz reported)
**What:** Imtiyaz asked for ALL borders across the dashboard to align, not just the ones already
fixed today. A broader grep found a third border family: `.bb-item`/`.bb-label` (ticker pills used
in Risk & Session, AI Summary, Market Intelligence, Open Trades bars), `.slot-panel`, and `.lsf-btn`
(Signal Log's ALL/BUY-SELL/RELOAD filter buttons) all used a cyan-tinted `rgba(0,212,255,...)`
border instead of `var(--border)`. Confirmed scope with Imtiyaz before changing (visually
noticeable across multiple ticker strips) -- fix base/default states only; left the `.gold`/`.warn`
semantic variants (`.bb-item.gold`, `.bb-item.warn`) and interactive hover/active states
(`.lsf-btn:hover`, `.lsf-btn.lsf-on`) untouched, since those intentionally convey a different
state, not just a stray color choice.
**Fix:** `.bb-item`, `.bb-label`, `.slot-panel`, `.lsf-btn` base border -> `var(--border)`.
**Real bug found investigating `.lsf-btn` (unrelated to the color question, found by accident):**
its entire `<style>` block (defining `.lsf-btn`/`:hover`/`.lsf-on`) was sitting inside
`<div class="tab-pane" id="tab-live">` in the raw HTML. `gsInitDashboard()` moves every actual
panel (`[id^="panel_"]`/`.tcard`) OUT of each tab-pane into GridStack on page load, then deletes
any tab-pane left with no matching children ("Remove empty tab panes (content moved to grid)").
Since this stray `<style>` tag was the ONLY thing left behind in `#tab-live` afterward, it matched
the "empty" cleanup condition and got deleted from the DOM on EVERY page load -- meaning these
filter button styles have **never actually applied**, ever, confirmed via `document.styleSheets`
showing only the 2 real stylesheets, neither containing `.lsf-btn`. The buttons had silently been
rendering as native unstyled browser buttons (2px black outset border) the entire time.
**Fix:** moved the 3 `.lsf-btn` rules into the main `<head>` stylesheet (next to `.gs-toolbar
button`, another toolbar-button style) and deleted the orphaned in-body `<style>` tag.
**Verified live:** `document.styleSheets` now contains a real `.lsf-btn` rule; the RELOAD/BUY-SELL
buttons render `1px solid rgb(13,37,53)` (exact match to main panel border, `solid` style, `1px`
width -- was `2px outset rgb(0,0,0)` before); the active filter button still correctly shows cyan
(`rgb(0,255,238)`, the intentional "on" state); `_liveSigFilt('trade')` toggle still works
(`lsf-on` class moves correctly between buttons); no console errors.

## 2026-07-14 — Open Trades panel: dead space when empty + GridStack resize bug (Imtiyaz reported)
**What:** Imtiyaz reported the Open Trades panel always reserved dashboard space even with zero
trades open, and asked for it to collapse to about ticker-row height when empty (like the vSL/TP
bar, `sl_progress_wrap`, already does) instead of sitting at the bottom with dead space.
**Fix 1 — CSS:** `#panel_open_trades{height:auto!important;overflow:hidden!important}` (same proven
pattern already used for `#panel_signal`/`#signal_history_panel`). The global rule
`.grid-stack-item-content>.tcard{height:100%}` was stretching the panel to fill its allocated
GridStack cell even when its real content (header-only, no open trades) was tiny. This alone
shrank the panel's own content box from ~112px to ~36-38px (close to ticker-row height).
**Fix 2 — real bug found while verifying Fix 1:** the GridStack row allocation (`gs-h`) never
actually followed the smaller content down, staying stuck at 2 rows (112px) regardless. Root
caused to TWO separate pre-existing bugs in the shared `_fitPanelToGrid()` helper (used by Open
Trades, Closed Trades, Hours Heatmap, Signal History -- all of them affected, not just Open
Trades):
  1. A premature memo (`_panelFitLastH[panelId]`) marked a resize as "already handled" once it
     computed a target height ONE time, without ever confirming the resize actually took effect —
     so if the very first attempt silently failed, every later call skipped the fix forever.
     Fixed: now checks the REAL grid attribute (`curH`) directly instead of trusting the memo alone.
  2. The resize itself (`_gsGrid.removeWidget(wrap,false); _gsGrid.addWidget(wrap,{...})`) was
     silently no-op'ing — confirmed via console spam already present on every page load: `"V11:
     GridStack.addWidget() does not support HTMLElement anymore. use makeWidget()"`. This project's
     GridStack build is v11, which dropped that call signature. Fixed: switched to `_gsGrid.update(wrap,
     {x,y,w,h,minW,minH})` — the SAME method this file already uses successfully elsewhere for
     resizing an existing widget (layout-restore code, ~line 4515).
**Verified live** (browser preview): Open Trades panel wrapper height 112px -> 56px (GridStack's
minimum 1-row quantization -- rows can't be smaller than the configured `cellH`, so 56px is the
floor achievable while it stays a draggable/resizable grid panel; true ticker-row height (~36px)
would require taking it out of the grid system entirely, a bigger structural change not done here).
**Also benefits (same shared function, same bug):** Closed Trades, Hours Heatmap, and Signal
History panels should now also correctly shrink-to-fit instead of getting stuck at a stale height.
**Takes effect on browser refresh** (static HTML/JS, no server restart). If a saved GridStack
layout still shows the old size, click the 🔁 Reset button once.

**Follow-up same day (Imtiyaz: "I want hide also"):** 56px (1 GridStack row) still wasn't enough —
wanted the panel FULLY gone (0px) when no trades are open, popping back in the instant one opens,
matching `sl_progress_wrap`'s show/hide exactly. Extended the "OPEN TRADES" render block: on zero
open trades, `_gsGrid.removeWidget(wrap, false)` (detaches from grid tracking, keeps the DOM node)
+ `wrap.style.display='none'`; the moment `open_trades.length` is truthy again, `wrap.style.display=''`
+ `_gsGrid.makeWidget(wrap)` (the v11-correct re-attach call, per the same console warning) +
`_gsGrid.compact()` to close the gap / let later panels shift up. A `data-gs-attached` flag on the
wrapper avoids calling removeWidget/makeWidget redundantly every poll tick.
**Verified live:** hidden state = `display:none`, height 0px, `data-gs-attached="0"`. Manually invoked
the show-path (`makeWidget`+`compact`) — no exceptions, panel reappeared at its normal size. Then
let the next real poll tick (still 0 open trades) hide it again — no errors, no duplicate widget
registration. Full hide-show-hide cycle confirmed clean.

**Second follow-up same day (Imtiyaz: "sl_progress_wrap જેવો fixed bar yes"):** the makeWidget/
removeWidget dance above still left the panel bound to GridStack's 56px row grid whenever it WAS
shown. Took it out of GridStack entirely instead, mirroring exactly how `sl_progress_wrap` and
`danger_banner` already work:
- `gsInitDashboard()`'s "conditional bars" list (`['danger_banner','sl_progress_wrap']`, moved to sit
  as plain siblings just above the `.grid-stack` div, not wrapped as grid items) now also includes
  `'panel_open_trades'`.
- Removed the `open_trades` entry from `PANEL_CONFIG` entirely (it's no longer grid-managed, so the
  panel-creation loop that wraps each config entry into a `.grid-stack-item` never touches it).
- `#panel_open_trades` CSS: added `display:none` as the default (matching `.sl-progress-wrap`'s own
  default-hidden pattern) instead of relying on JS to hide it before first render.
- Simplified the "OPEN TRADES" render block back down to a single direct toggle —
  `panel.style.display = hasTrades ? 'block' : 'none'` — since there's no GridStack widget to
  attach/detach anymore; removed the now-unnecessary `removeWidget`/`makeWidget`/`compact` calls
  from the previous fix.
- Removed the 3 now-stale `_fitPanelToGrid('panel_open_trades')` calls (harmless no-ops now since
  `.closest('.grid-stack-item')` returns null off-grid, but cleaned up for clarity).
**Trade-off (accepted, matches sl_progress_wrap):** Open Trades can no longer be dragged/resized in
edit mode — it's a fixed bar now, by design, same as the vSL/TP bar it's paired next to.
**Verification status:** code-reviewed line-by-line (confirmed the conditional-bars move runs BEFORE
`PANEL_CONFIG` is read into the grid-creation loop, so removing the config entry is safe; confirmed
no other code references `PANEL_CONFIG.open_trades`/`'open_trades'` anywhere). **Live browser
re-verification was NOT completed this round** — the browser tool became temporarily unavailable
mid-session (model-availability outage, not an app issue) right after this change. Please Ctrl+F5
and confirm: (1) panel fully hidden with 0 open trades, (2) sits directly under the vSL/TP bar when
a trade opens, (3) no console errors on load.

**Third follow-up same day (Imtiyaz, with a real open trade now visible: "use only as ticker hight
even trade is open"):** even correctly positioned/hideable, the panel was still ~150px tall
WHILE a trade was open — the per-trade card rendered a 3x3 stat grid (Entry/Current/Virtual SL/TP/
SL Dist/TP Dist/R Profit/Max R/Breakeven) plus a "To TP" progress bar, most of which duplicates what
`sl_progress_wrap` already shows prominently right above it (vSL, TP, R, entry marker, progress
track). Collapsed the per-trade template (`otc.innerHTML` map in the OPEN TRADES render block) from
that tall grid down to a single ticker-style row reusing the SAME `.bb-item`/`.bb-val` classes as
the Risk & Session strip: direction+ticket+status, Entry, Now, SL, TP, P&L/R — one line. Dropped the
redundant progress bar entirely.
**Verified live** (browser preview, real open trade): trade-card height 32px at 1400px width (was
~150px) — right in ticker-row range; at a narrower 900px width it wraps cleanly to ~50px (2 lines)
via `flex-wrap`, no text clipping (`scrollWidth === clientWidth` confirmed) and no visual overlap in
either width. Whole panel (header + 1 trade row) now ~71px total vs. the original ~180px+.
**Takes effect on browser refresh**, no server restart.

**Fourth follow-up same day (Imtiyaz: remove the header line too, +20% font, bubbles justified
across the full row):**
- `#panel_open_trades .tcard-hdr{display:none}` — the "⚡ Open Trades" header bar is gone; the
  ticker row itself already says direction/ticket/status, nothing lost.
- Font bumped 20% over the base `.bb-item` ticker size, scoped to `#panel_open_trades` only (Risk &
  Session / AI Summary / Market Intelligence tickers elsewhere untouched): label 0.5rem->0.6rem,
  value 0.62rem->0.74rem, sub 0.56rem->0.67rem; the direction badge specifically 0.72rem->0.86rem.
- Trade-card row: added `justify-content:space-between;width:100%` so the 6 bubbles (direction,
  entry, now, SL, TP, P&L) spread across the FULL row width with even gaps instead of clustering
  left.
**Verified live:** header `display:none` confirmed; panel height 71px -> 49px (no header) with font
20% bigger; bubble positions measured via `getBoundingClientRect()` -- first bubble starts at 13px,
last ends at 1336px on a 1347px-wide card, evenly spaced between -- confirms the full-width justified
spread. Computed font-size 11.84px (0.74rem) and 13.76px (0.86rem) on a 16px root, both exact 20%
bumps.

**Fifth follow-up same day (Imtiyaz: "vSL/TP bar make it 30% smaller"):** scaled `sl_progress_wrap`
(the vSL/TP bar itself, not Open Trades) down ~30% across the board: track height 54px->38px (exact
0.7x), header font 0.68rem->0.48rem, price-label fonts 0.8rem->0.56rem, price-sub fonts
0.69rem->0.48rem, pct-detail 0.72rem->0.5rem, R/pct badges 0.88/0.9rem->0.62/0.63rem, labels-row
height 14px->10px + font 0.6rem->0.42rem, wrap padding 3px 10px 4px->2px 7px 3px, eq-grid inset
8px 10px->6px 7px.
**Verified live:** track height measured 38px (matches the 0.7x target exactly), header 14.4px,
labels row 10px, neither header nor labels row overflowing (`scrollWidth`==`clientWidth`), no
console errors. Whole bar visibly more compact, same information, nothing clipped.

## 2026-07-14 — Real bug: SIGNAL vs SIGNAL LOG height drifts out of sync during live use (Imtiyaz reported)
**What:** Imtiyaz reported the SIGNAL panel (left) and SIGNAL LOG panel (right) heights not matching
during real live use — a growing dead-space gap under SIGNAL while SIGNAL LOG kept a scrollbar,
worse than a fresh page load. Explicitly did not want a manual drag-to-resize workaround.
**Root cause found:** `_syncSignalLogToSignalHeight()` (measures `panel_signal`'s real content
height and forces `panel_signal_log` to match) was ONLY wired to three trigger points: initial
`gsInitDashboard()`, window `resize`, and `switchTab()`. It was **never called on the regular
data-poll refresh cycle** — so whenever `panel_signal`'s own content height drifted with live data
(a longer/shorter signal-reason string, a lifecycle step appearing/disappearing, the manual-trade
banner toggling) with no resize or tab-switch happening in between, `panel_signal_log`'s height
silently went stale and the two panels drifted apart — exactly what a fresh page load could never
show (which is why my earlier post-Reset test looked fine — that was right after the init-time
sync ran, before any live drift had a chance to accumulate).
**Fix:** added a call to `_syncSignalLogToSignalHeight()` inside the main per-poll render block,
right next to the other per-poll `_fitPanelToGrid(...)` calls (hours heatmap / signal history /
closed trades), so SIGNAL and SIGNAL LOG re-sync on every single data refresh, not just on resize/
tab-switch.
**Verified live (real wiring test, not just the function in isolation):** artificially shrank
`panel_signal`'s content height 278px -> 161px via a temporary `max-height` override, WITHOUT
calling any resize/tab-switch/sync function manually. Waited 6 seconds (one natural poll interval).
`panel_signal_log` automatically followed to 162px (`log.style.height` updated to `"162px"`) purely
from the regular poll cycle picking up the new fix — confirms the sync now runs continuously during
live use, not just at specific trigger moments.

## 2026-07-14 — Dashboard SIGNAL HISTORY ticker: font legibility fix (Imtiyaz reported)
**What:** Imtiyaz reported the price/time text drawn on the SIGNAL HISTORY canvas ticker
(`drawSigChart()` in `engine/dashboard.html`) was not clearly visible.
**Round 1 (partial fix):** the canvas CSS height was only 34px while the code drew 2 lines of
13px/11px bold text into it — genuinely cramped. Bumped `#sig_history_chart` height 34px→46px
(and the flex container's min-height to match) and bumped fonts to 15px/12px.
**Round 2 (the actual main problem, per Imtiyaz's follow-up):** the "improvement" in round 1 also
thickened the black text-outline (`ctx.lineWidth` 3→3.5, opacity 0.9→0.95) meant to keep text
readable against any bar color — at these small font sizes a stroke that thick reads as a muddy
black shadow/blob smearing the glyph edges, on BOTH the price and time lines. Replaced the hard
`strokeText` outline with a soft `ctx.shadowBlur` halo (blur 2.5, no stroke) — same contrast against
varying backgrounds, without thickening the letterforms. Verified visually (scaled 3x in-browser)
before/after — round 2 reads noticeably cleaner.
**Takes effect on browser refresh** (static HTML/JS, no server restart needed) — hard-refresh
(Ctrl+F5) if the dashboard tab was already open.

## 2026-07-14 — OneFunded secondary account disabled (Imtiyaz)
**What:** Commented out the OneFunded entry in `engine/config_mt5.py` `MT5_ACCOUNTS` (same
disable-by-comment convention already used for TradeQuo/Neex — credentials preserved for later
re-enable, not deleted).
**Why:** Every single mirrored order on this account was rejected with retcode 10027
("AutoTrading disabled by client") — confirmed via `bridge.log` on 2026-07-13 19:45, 2026-07-14
07:45, and 2026-07-14 16:45 (100% failure rate, 2+ days). This is a terminal-side setting (the
AutoTrading toggle inside that specific MT5 terminal), not a code bug — no code changed to "fix"
the rejection itself.
**To re-enable:** turn AutoTrading back on in the OneFunded MT5 terminal, then uncomment the block
in `config_mt5.py`.
**Takes effect on next bridge restart** (bridge_main.py reads `config_mt5.py` at process start).

## 2026-07-14 — Broker-side SL self-heal + wide-trail (Imtiyaz reported, Claude fixed)
**Context:** while auditing today's primary trade (#1589591435, BUY 34.8 lot @ 4021.94), Imtiyaz
manually deleted the position's broker-side SL (which had been correctly set at open to 4005.15 —
verified byte-for-byte against the MT5 terminal's own trade log) mid-trade. Investigation found:
`bridge_core.py`'s broker SL is set ONCE at `execute()` time (`entry ∓ sl_dist×1.5`) and NEVER
touched again by any code path (`grep TRADE_ACTION_SLTP` = only 2 hits, neither is a periodic
resync) — the software's own virtual SL (vSL) ratchets every tick, but that protection is 100%
in-app; if the bridge process had crashed or lost connection before the position closed, it would
have had ZERO broker-level stop. (No loss occurred this time — Imtiyaz closed the position manually
minutes later for +$245,479.20 profit — but the gap was real.)
**Fix (`engine/bridge_core.py`, new `_sync_broker_sl()` method, called from the existing per-tick
`monitor_virtual_sl()` loop for every non-closing tick):**
- Restores the broker SL if MT5 reports it missing (`pos.sl == 0`).
- Otherwise trails it forward at `vSL − broker_sl_trail_buffer_mult × sl_dist` — verified this
  reproduces the EXACT original 4005.15 backstop at trade-open (since `vSL = entry − sl_dist`, so
  `vSL − 0.5×sl_dist = entry − 1.5×sl_dist`, the same formula `execute()` already uses).
- One-way only (never loosens) — mirrors the vSL's own ratchet philosophy.
- Deliberately offset BEHIND the tight vSL (not equal to it) — per Imtiyaz's own point that a SL
  sitting exactly on the visible ratchet line is an easier "SL hunt" target than one held back with
  a buffer; the buffer itself still narrows over time as profit locks in.
- Throttled (`broker_sl_sync_interval_sec=10`, default) — does not spam `order_send` every tick.
**New config (`engine/config.py` `FilterConfig`):** `broker_sl_sync_enabled=True`,
`broker_sl_trail_buffer_mult=0.5`, `broker_sl_sync_interval_sec=10.0`. `FILTERS_MASTER.md` §B +
change log updated in the same change.
**Scope (deliberately NOT changed):** secondary/mirror accounts' static 3x-wide broker SL is
untouched — that design relies on `close_secondary_accounts()` syncing to the primary's real exit
event, not on the secondary's own broker SL trailing tightly; widening the scope here would have
mixed two different safety mechanisms without being asked to.
**Verified:** `python -m py_compile config.py bridge_core.py` clean. Formula hand-checked against
today's real trade numbers (entry 4021.94, sl_dist 11.19 → target 4005.155 ≈ MT5's own logged
4005.15). **Not yet exercised on a live running bridge** — next restart of the bridge picks it up;
watch for the new `🛡️ #<ticket> broker SL RESTORED/synced -> ...` log line.

**Follow-up same day — widened to 3x (Imtiyaz):** primary's trade-open backstop was 1.5x sl_dist
(hardcoded), narrower/easier to "SL hunt" than secondary's 3x. Made `broker_sl_open_mult` a config
value (`config.py`, default **3.0**, was hardcoded 1.5) and used it in `bridge_core.py execute()`'s
broker_sl formula (both BUY/SELL branches) instead of the literal `1.5`. Updated
`broker_sl_trail_buffer_mult` 0.5 → **2.0** to match (`open_mult − 1`, so the trail formula still
reproduces the exact trade-open value at t=0). Secondary (`bridge_multi.py`) was already 3x —
unchanged, now symmetric with primary. Verified: `entry − sl_dist×3.0` == `vSL − sl_dist×2.0` on
today's real numbers (3988.37 both ways). `py_compile` clean.

## 2026-07-14 — Signal-repaint audit: dashboard bar_time-collapse bug found + fixed
**What:** Imtiyaz asked for a full audit + diagnostic proving saved historical signals never
repaint (direction/probability/score/state/threshold/model-version/feature-snapshot must stay
immutable once logged). Full read-only audit of the flow: LiveInferenceEngine -> log_signal() ->
SQLite `signals` table -> CSV backup -> dashboard.json -> dashboard history panels.
**Confirmed already correct (built in an earlier session, verified this session):**
`log_signal()` does a plain `INSERT INTO signals` (no REPLACE/IGNORE/UPSERT); the only later
`UPDATE signals` (`write_outcome()`) touches only `outcome`/`pnl_net`, and only while blank;
`_signal_audit_fields()` generates a genuinely unique `signal_id` (SHA1 of symbol+bar+signal+
mode+model_version+microsecond timestamp+feature_hash) plus all required audit columns
(model_version/hash, feature_snapshot_json/hash, decision_threshold, combined/state/directional
scores); `_make_result()` in `inference.py` hashes the EXACT `feat_dict` used for that inference
call (a true point-in-time snapshot, never recomputed later); `get_signal_history()` (dashboard.json's
`signal_history` key) is a pure DB `SELECT`, never re-inference; the dashboard's "Current Signal"
(`last_signal`) and "Signal History" (`signal_history`) keys are already properly separate sources;
model reload (`bridge_main.py`) only swaps the live `LiveInferenceEngine` instance for FUTURE
inference, never touches past rows; `_overnight_replay()` backfill only fills genuine gaps
(`_logged_bar_times()` gate) rather than re-logging already-logged bars. The old `UNIQUE(bar_time,
mode)` schema constraint that WOULD have silently dropped/blocked a re-evaluated candle was already
migrated away in a prior session (`_ensure_signal_immutable_schema()` in `bridge_constants.py`).
**Found + fixed (real bug, dashboard-side only):** `engine/dashboard.html`'s "SIGNAL LOG" panel
(`window._liveSigLoad`, feeding `#liveSigRows`) parsed `signals_all.csv` + `signals_complete.csv`
and merged them keyed by **`bar_time`** alone (`map[r.bt]=r`, "live overrides same bar"). Since the
backend explicitly tolerates two distinct immutable rows sharing a bar_time (a candle re-evaluated —
e.g. BACKFILL then LIVE — each with its own snapshot/probability, per the comment in
`bridge_data.py`'s `log_signal()`), this client-side merge could silently show only ONE of them for
a given time slot, and WHICH one could change between 15-second dashboard refreshes depending on
file-read order — a genuine dashboard-only repaint even though the underlying DB/CSV rows were
correctly immutable throughout. **Fix:** `_parseSig()` now also extracts the `signal_id` column
(already present in the CSV since the 2026-07-13 schema migration but never parsed by the JS); the
merge key is now `r.sid||r.bt` (falls back to bar_time only for legacy pre-migration rows with no
signal_id) — every distinct immutable signal_id now renders as its own row, never collapsed.
**Diagnostic tool rewritten:** `engine/diag_signal_repaint.py` was a single-shot placeholder (it
copied the SAME current value into every `_after_15m`/`_after_1h`/`_after_restart`/
`_after_model_reload` column, proving nothing about time). Rewritten as a step-based tool with a
persisted `_ledger.json` (keyed by `signal_id`): `--step baseline` snapshots the current signal_ids'
immutable fields; each later step (`after15m`/`after1h`/`after_restart`/`after_model_reload`/
`refresh_compare`) re-reads the SAME signal_ids from SQLite/CSV/dashboard.json NOW and fills in
that step's columns, classifying repaint_type 0-9 per the spec. Also added a static check for the
dashboard bar_time-collapse anti-pattern (regression guard). `RUN_QGAI-CORE_Diag_SignalRepaint.bat`
now takes an optional `[step]` argument.
**Not yet done (requires real elapsed time / a real restart / a real retrain — cannot be done by
Claude in one turn, must be run by Imtiyaz per the house "never run tests inline" rule):** the
actual baseline + 15-min + 1-hour + restart + model-reload + dashboard-refresh sequence has not
been executed end-to-end. The prior single-shot run (08:08, before this rewrite) showed PASS
(0 repaint rows) on a one-time read, which is evidence but not proof across time.
**Files touched:** `engine/dashboard.html` (merge key fix only, no model/entry/trading logic
touched), `engine/diag_signal_repaint.py` (rewrite), `backtest/_runners/RUN_QGAI-CORE_Diag_SignalRepaint.bat`.
Both scripts py_compile / ASCII clean.
**Follow-up same day (diagnostic false-positive fix):** Imtiyaz ran baseline (15:32, PASS/0) then
after15m (15:51) — after15m reported 38 "repaint" rows, ALL repaint_type 4. Investigated: this was
a BUG IN THE DIAGNOSTIC, not a real repaint. The 38 tracked baseline signals were all intact
(db_row_changed=0, csv=0, dash=0, not disappeared, not duplicate — only the type-4 flag fired). The
flaw: the type-4 ("historical signal appeared later") check flagged EVERY tracked entry whenever ANY
new bar appeared since baseline — but the live bridge advancing to new candles (15:45 etc.) between
baseline and after15m is normal forward progress, not a back-dated insertion. Fixed the logic:
type-4 now fires only for a NEW signal_id whose bar_time is AT OR BEFORE the baseline frontier (a
genuine insertion into a past slot); forward-progress candles are excluded by construction. Also
fixed two related flaws found alongside: (1) `run_step` was overwriting the baseline reference
(`bar_mode_at_baseline`) on every step, so after_restart/after_model_reload would have compared
against the prior step instead of the true baseline — now the baseline frontier + id-set are fixed
and never overwritten; (2) baseline now stores the frontier bar_time + full id-set instead of a
deduplicated (bar_time,mode) set. **Real-signal conclusion from the run: the 38 saved signals did
NOT repaint across the 15-minute window — direction/probability/state/model/feature all unchanged.**
Stale ledger deleted; re-run baseline fresh with the fixed tool.
**Second diagnostic false-positive (window-size mismatch), found on the after15m re-run:** the fixed
tool still reported 189 type-4 rows at after15m — again NOT real. All 189 had bar_times 07-08..07-10,
i.e. BELOW the baseline window (the tracked baseline signals only spanned 07-14 04:45..14:00). Cause:
`run_baseline` read the newest 200 rows but `run_step` read the newest 400 — the extra 200 older rows
a step reaches were never in the baseline id-set, so they looked "back-dated". Fixed: (1) a single
`READ_WINDOW=400` constant used by BOTH baseline and every step; (2) baseline now also stores a
`baseline_floor` (oldest bar_time it saw) and the type-4 check only fires for a new signal_id whose
bar_time is INSIDE `[floor, frontier]` — rows older than the observed window (never snapshotted) and
newer than the frontier (normal forward candles) are both excluded. py_compile clean, stale ledger
deleted again. Net: two diagnostic-only bugs fixed; still zero evidence of any real signal repaint.

---

## 2026-07-14 — Leakage-fix results comparison + RESULTS_INDEX.md correction (Imtiyaz asked, Claude fixed)
**What:** Imtiyaz asked to keep the honest (post-leak-fix) WFO/backtest results separate from the
old pre-leak-fix (leak-inflated) ones in one place, and for an opinion on where things stand.
**Found while doing this:** `backtest/results/RESULTS_INDEX.md` (dated 2026-07-11) still labeled
W1 (`wfo_part1_prune35`, +444.7R) as **"ADOPTED / BEST"** — stale and actively misleading, since
the 2026-07-12 leakage audit (`docs/LEAKAGE_AUDIT_20260712.md`) already established that number is
lookahead-inflated (`in_range_phase` future-candle leak + `corr_imp_ratio` double-leak). Fixed:
W1's verdict corrected to "RETIRED (leak-inflated)", "Key Observations" #1 corrected to point at
the real honest baseline, and a correction banner added near the top of the doc.
**New:** `backtest/results/_LEAKAGE_FIX_COMPARISON/SUMMARY.md` (NEW folder, documentation-only —
no result CSVs copied/moved) — side-by-side OLD (leak-inflated: W1/W9/W10/W11, B1) vs NEW (honest:
W12, W13, `volhtfgate_wfo_TEST_A_off`, `leakfix_p1p2p3_backtest_TEST`) with an opinion section.
**Opinion (full detail in that file):** the honest ~+80-86R/53wk baseline (W13) is real and
trustworthy, but every honest number currently on disk is missing something (W12/W13 predate the
P2/P3 fixes; the 12-week `volhtfgate` run is honest+current-feature-set but too short a period;
the P1P2P3 1-month backtest is too small a sample). The actual next step — `Run_LeakFix_P1P2P3_
Retrain_WFO_FULL.bat` (53-week, current model) — is already built (2026-07-12) but has not been
run; that is what would give one clean, fully-current honest 1-year number instead of comparing
partial/stale ones against each other.

---

## 2026-07-13 (night) — Training-label TP-cap bug found (Imtiyaz's hypothesis), Fable-5 corrects the causal direction
**Trigger:** Imtiyaz watched a live ~29pt bearish move (2026-07-13, bar 16:00-17:00, price 4067→4038,
ADX H1/H4 slope rising = strengthening trend, a separate SMMA trend signal also showing SELL) where
win_prob stayed 30-42% the whole time — below the 45-48% regime entry threshold — despite what looked
like a clear directional setup. He hypothesized: (1) maybe a hard-coded ADX number is blocking entries
inside the buy/sell models, and (2) maybe the profit target (TP) itself is shaping what the model
considers a "win," so setups that don't reach the TP fast enough get trained as losses regardless of
direction correctness.
**Investigation (code-read, no test run):** (1) confirmed no literal hard-coded ADX gate exists in
`inference.py`'s entry-decision path (only the regime win_prob threshold + the env-gated, currently-OFF
`QGAI_VOL_HTF_GATE`) — checked line-by-line. (2) Confirmed hypothesis 2 directly: `relabel_trades.py`
(which generates the Win/Loss + R label for EVERY historical trade used to train all win-prob models)
computes each trade's TP price via a single **flat** `TPCAP` (currently 1.00%, imported from
`analyze_capture.py`). But the live system + `backtest_replay.py` have used a **regime-adaptive** TP cap
since 2026-06-27 (`config.py:218`, `ratchet_tp_regime=True` → Ranging 2.0% / Trending 1.0% / Volatile
0.8%, `backtest_replay.py:346`). This is a genuine, previously-undiscovered train-label-vs-live-exit
parity gap.
**Fable-5 opinion requested — and it corrected my causal-direction claim.** My first-pass read was that
flat-1.0%-cap labels make Ranging training pessimistic and Volatile optimistic relative to the real
regime caps. Fable-5 traced the actual exit-loop order in `relabel_trades.py` (checks SL/trail hit
BEFORE checking TP hit, every bar) and showed the true direction is the OPPOSITE of what I claimed:
- **Ranging** (label 1.0% vs live 2.0%, wider): a trade labeled "Loss" under the tight 1.0% cap
  necessarily exited via SL/trail/flip BEFORE ever reaching 1.0% — a wider 2.0% cap changes nothing
  about that same earlier exit, so **Loss→Win is mathematically impossible**. But a trade labeled "Win"
  (hit 1.0%) would, under a 2.0% cap, keep running and could retrace into an SL/flip exit before
  reaching 2.0% — **Win→Loss is possible**. Net effect: **current flat-cap Ranging labels are too
  OPTIMISTIC** (overstate win-rate) — fixing this bug would make the Ranging model MORE conservative,
  not less.
- **Volatile** (label 1.0% vs live 0.8%, tighter): a trade labeled "Win" (hit 1.0%) must have already
  crossed the nearer 0.8% level first (0.8% < 1.0%, same direction) — **Win→Loss is impossible** under
  the tighter cap. But a trade labeled "Loss" that got close (reached ≥0.8% before its SL/trail/flip)
  would have been a Win under the tighter live cap — **Loss→Win is possible**. Net effect: **current
  flat-cap Volatile labels are too PESSIMISTIC** (understate win-rate) — the reverse of my original claim.
- **Trending** has no gap at all (both are 1.00%).
**Consequence — this bug does NOT explain the triggering observation.** The live bars in question were
Ranging/Trending, not Volatile; Trending has no TP-cap gap, and the Ranging fix would push win_prob
DOWN, not up. The live conservatism Imtiyaz observed is more likely explained by the existing
[[project_htf_direction_architecture_rethink]] ADX-DI-vs-SMMA-trend divergence issue, not this TP-cap
bug. The bug is real and worth fixing on truth-in-labels grounds, but it is a separate issue from what
triggered the investigation.
**Scope wider than first found:** the same flat-TP simulation pattern also exists in
`rebuild_trainset.py:64` and `shadow_ledger.py:157` (fallback `TPCAP=10.0` if the config import fails)
— fixing only `relabel_trades.py` would create a NEW mismatch against these other two tools (shadow
ledger / trainset rebuild parity checks would then run on a different TP assumption than the actual
training labels).
**Fable-5's recommended sequence (nothing implemented yet):**
1. **Cheap diagnostic first, no retrain:** re-run the relabel simulation with the regime-adaptive TP
   cap and measure ONLY the label-flip % and ΔR per regime (a diff, not a training run — minutes, not
   hours). Gate: only proceed to full retrain+WFO if flips exceed ~3% of rows overall or 5-7% in any
   single regime.
2. If the gate passes: reuse the EXISTING production `hmm_model.pkl` (do not fit a fresh HMM) to
   retro-assign each historical trade's regime, persist it as a stored column so `train.py` doesn't
   independently re-predict a possibly-inconsistent regime for the same trades, and validate the
   retro-assigned regimes against already-logged live/backtest `hmm_state` values (need ≥85-90%
   agreement before trusting the retro-classification).
3. Centralize `_TP_BY_REGIME` into `config.py` as a single source of truth (currently a duplicated
   literal across 3+ files — a standing drift-bug risk on its own, independent of this fix). This is a
   config change — confirm with Imtiyaz first per house rule.
4. Fix all 3 files (`relabel_trades.py`, `rebuild_trainset.py`, `shadow_ledger.py`) together, not
   piecemeal.
5. House process: TEST-run on a small slice first → full relabel → full retrain → WFO with
   `--tp-regime` ON (live-faithful) → judge strictly on TOTAL R vs the current champion model → demo
   before any live swap. Update `FILTERS_MASTER.md` + this changelog when done.
**Priority placement:** after the in-progress 67-feature sweep and the built-but-not-yet-run post-cap
continuation audit (both cheap, both already investigating "TP policy vs reality" from a different
angle) — full retrain only if the cheap diagnostic clears the gate above. Not urgent: likely a small
effect, and wrong-signed relative to the live-conservatism complaint that triggered the investigation.
**Status:** bug confirmed real via code read, verified the additional 2 files independently
(`grep -n "TPCAP" rebuild_trainset.py shadow_ledger.py` both hit). No code changed this entry — pure
investigation + Fable-5 consultation.
**Follow-up (same night): step 1 of Fable-5's sequence built.** `engine/diagnose_tp_cap_regime_labels.py`
(NEW) — re-simulates every historical trade (`Back_testing_data_final_cleaned_RELABELED.xlsx` entries,
2024-12-02 to 2026-04-29, 2,743 rows) TWICE on real M15 OHLC: once with the current flat 1.00% TP cap
(matches what the models are actually trained on today) and once with the regime-adaptive cap
(Ranging 2.0% / Trending 1.0% / Volatile 0.8%, matching live since 2026-06-27). Each trade's entry-time
regime is classified using the EXISTING production `hmm_model.pkl` (loaded via `MarketStateHMM.load()` +
`predict_batch()` on `adx_merged.csv` — no HMM refit, exactly Fable-5's recommendation to reuse the
live classifier rather than introduce a second, possibly-inconsistent one), looked up as-of the last
closed ADX bar before each entry (no lookahead). Reports, overall and per regime: label-flip count/%
(Win↔Loss), total ΔR, and an exit-reason migration table (flat→regime) — everything needed to check
Fable-5's decision gate (full retrain+WFO only justified if flips exceed ~3% of rows overall or ~5-7% in
any single regime) before committing to the expensive fix. Pure pandas + OHLC/ADX replay, read-only, no
training, no model-file writes. Delivered as `.bat` (house rule):
`backtest/_runners/Run_TPCapRegimeLabelDiagnostic_TEST.bat`. Verified:
`python -m py_compile diagnose_tp_cap_regime_labels.py` clean; bat checked for non-ASCII characters
(none found). Not run — per house rule, Imtiyaz runs it on his own PC.
**Bug found on first real run (Imtiyaz, same night):** crashed with
`ValueError: I/O operation on closed file` inside `features.py`'s own import-time print. Root cause:
my script did its own `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, ...)` UTF-8 wrap AND then
imported `analyze_capture`, which does the exact same wrap — the second wrap creates a new
`TextIOWrapper` around the same underlying buffer; the first wrapper object then has zero references
and gets garbage-collected, and `TextIOWrapper.__del__` closes the underlying buffer it was wrapping
(shared with the second wrapper) — so the next `print()` call fails on a "closed file". Fixed by
removing the redundant wrap from my script (importing `analyze_capture` already performs it once).
Found the exact same latent double-wrap bug in `analyze_post_cap_continuation.py` (built earlier the
same night, not yet run) — fixed identically before it could hit the same crash. Verified no other
double-wrap risk exists in either script's import chain (`grep -l "sys.stdout = io.TextIOWrapper" *.py`
— only `analyze_capture.py` itself wraps, among everything both scripts import). Both re-compiled clean.

## 2026-07-13 (night) — TP-cap/regime label bug: diagnostic result + code fix (no retrain)
**Diagnostic result (`Run_TPCapRegimeLabelDiagnostic_TEST.bat`, run by Imtiyaz):** 2,743/2,743 historical
trades simulated OK. **Total label flips: 17 (0.62%)** — well under Fable-5's 3% gate.
```
Ranging  : 5/1340 (0.37%) flips — ALL Win->Loss, 0 Loss->Win  | delta-R +62.8
Trending : 0/747  (0.00%) flips — no gap (both caps 1.00%)     | delta-R  +0.0
Volatile : 12/656 (1.83%) flips — ALL Loss->Win, 0 Win->Loss   | delta-R -16.4
```
The 100%-directional flip pattern (Ranging only ever Win→Loss, Volatile only ever Loss→Win) exactly
confirms Fable-5's earlier corrected mechanism — mathematically, a wider cap can only ever cost Ranging
wins, and a tighter cap can only ever gift Volatile losses, never the reverse. This also validates the
diagnostic script's own bar-by-bar trail simulation is behaving as designed (not a shortcut/approximation).
Interesting nuance: Ranging's aggregate ΔR is net-POSITIVE (+62.8) despite its flips being all Win→Loss,
because the ~1335 non-flipped Ranging "Win" trades rode the wider 2.0% cap further via the trail before
exiting, gaining more R each. Volatile's aggregate ΔR is net-NEGATIVE (-16.4) despite its flips being all
Loss→Win, because many non-flipped Volatile "Win" trades got cut short earlier at the tighter 0.8% cap.
**2nd Fable-5 consult — decision: skip the full retrain, fix the code anyway.** Asked whether the
measured result (well under the gate, but with a real +46.4R aggregate ΔR and a clean directional
pattern) changed anything. Fable-5's answer: no — and gave a decisive extra reason found by re-reading
`train.py`: **the win-prob models train on binary Win/Loss labels only; R never enters training as a
target or sample weight** (`y_big = (trades["% Move"].abs() > 0.30)`, `y_dur = (...)` — both binary;
main buy/sell/regime models are binary classifiers). So the +46.4R aggregate is informationally
irrelevant to what the model actually learns — only the 17 flipped binary labels matter, and 17/2,743
cannot move an XGBoost decision boundary in any measurable way. Also confirmed the `big_win` label
(0.30% threshold) is structurally immune to this bug, since both TP caps (0.8-2.0%) sit above it — a
cap-hit exit is always ≥0.8% move, so its label can never flip either way from this bug.
**Fable-5's recommendation: fix the 3 files anyway (correctness/parity), skip retrain.** Especially
`shadow_ledger.py`, since it's used for live-vs-shadow parity checks — a stale flat-cap assumption there
would silently produce false "why did live and shadow disagree?" investigations (this project's
BUG_LOG #F/#G/#H/#J class of incident). Root cause reframed: not really "flat vs regime," but "the same
per-regime TP dict duplicated as a literal in 4 different files" — a structural drift-bug waiting to
recur on the next TP-cap tuning.
**Code fix implemented (no retrain triggered):**
- **`engine/config.py`** — new `FilterConfig.tp_by_regime` field (`{"Ranging": 2.0, "Trending": 1.0,
  "Volatile": 0.8}`) — the single source of truth. Change values here only, going forward.
- **`engine/backtest_replay.py`** — `_TP_BY_REGIME` now reads `CFG.filters.tp_by_regime` instead of a
  local literal dict. Values unchanged — pure refactor, no behavior change (still overridable via
  `QGAI_TP_REGIME_VALS` for sweeps, unchanged).
- **`engine/relabel_trades.py`** — new `assign_regimes()` retro-classifies each historical trade's
  regime using the EXISTING production `hmm_model.pkl` (`MarketStateHMM.load()` + `predict_batch()` on
  `adx_merged.csv`, no refit — exactly Fable-5's recommendation to reuse the live classifier), looked up
  as-of the last closed ADX bar before entry (no lookahead). `relabel()` now takes a per-trade TP%
  array instead of the flat module constant. Gated by `CFG.filters.ratchet_tp_regime` — set it False to
  fully revert to old flat-cap behavior. The `regime` working column is dropped before writing the
  output xlsx (schema unchanged, as the script's own docstring promises); added to the `_RELABEL_DIFF.csv`
  diagnostic output for transparency.
- **`engine/rebuild_trainset.py`** — same fix pattern (`regime_lookup_table()` precomputes a per-bar
  regime array via the same production HMM, `simulate()` picks the per-candidate TP% from it). This
  script is currently DORMANT (not wired to `config.trades_file` — an alternative/experimental
  trainset generator per its own docstring), so this fix has zero live effect today, only correctness
  for if/when it's adopted.
- **`engine/shadow_ledger.py`** — simplest fix: this script already has `hmm_state` logged per signal
  in `signals_all.csv` (the bridge wrote it live), so no HMM retro-classification is needed — just reads
  `s["hmm_state"]` and looks up the matching regime TP% from the same `tp_by_regime` dict. Gated by
  `CFG.filters.ratchet_tp_regime` (new `TP_REGIME` flag), same revert path.
**Verified:** all 5 touched files (`config.py`, `backtest_replay.py`, `relabel_trades.py`,
`rebuild_trainset.py`, `shadow_ledger.py`) re-compile clean (`python -m py_compile`). No retrain
triggered — the fixed scripts will only affect model training the next time someone actually re-runs
`relabel_trades.py` → `train.py`, which per this decision is not being scheduled now.
**`docs/FILTERS_MASTER.md`** updated: current-value table note + dated §CHANGE LOG row (per house rule
— any filter-adjacent code change gets both).

## 2026-07-13 (night) — win_prob calibration diagnostic built (Fable-5 Step 1, original concern)
**Purpose:** the TP-cap investigation above turned out to be a separate tangent (fixed, but doesn't
explain the triggering observation). Fable-5's Step 1 for the ACTUAL concern — win_prob staying 30-42%
during a clear ~29pt bearish move where ADX H1/H4 + a separate SMMA trend signal both agreed SELL —
is a cheap calibration check, built as `engine/diagnose_win_prob_calibration.py`.
**Design:** uses an ALREADY-EXISTING dataset — the 3-month VolHTFGate WFO OOS run's
`ALL_OOS_trades.csv` (207 real executed trades, `volhtfgate_wfo_TEST_A_off/`). No new model inference
needed: every row already carries the model's own predicted `win_prob` at entry, the REALIZED outcome
(`r_achieved`), and the raw HTF-direction features (`f_H1_DI_diff`, `f_H4_DI_diff`, `f_ts_trend_h1`,
`f_ts_trend_h4`). For each trade, counts how many of these 4 signals agree with the direction actually
traded and buckets: `aligned_strong` (4/4 agree), `aligned_weak` (3/4), `mixed_disagree` (≤2/4). Reports
avg predicted win_prob vs realized win-rate per bucket, plus the gap (realized − predicted).
**Interpretation built into the report:** a clear positive gap in `aligned_strong` (realized notably
above predicted) confirms systematic underconfidence exactly when ADX+SMMA agree — the concern that
started this whole investigation. A gap near zero means the model IS well-calibrated there, and the
"too conservative" read was a perception issue (or explained by something else already found, e.g. a
specific bar's regime routing) — stop, don't build the bigger fix.
**Explicit caveat (documented in the script's own output):** this dataset is EXECUTED trades only
(already cleared the entry threshold) — it can prove/disprove whether the model is honest about trades
it already takes, but cannot by itself prove that good trades were wrongly SKIPPED (no realized outcome
exists for a bar that was never traded). If a real gap shows up, the next, more expensive step per
Fable-5 is a full shadow-simulation across SKIPPED bars too (extending `analyze_capture.py`-style
replay to bars below threshold) to quantify actual missed profit — not jumping straight to the bigger
ADX-DI/SMMA-trend feature-consolidation fix.
**Delivered as `.bat`** (house rule): `backtest/_runners/Run_WinProbCalibration_TEST.bat`. Verified:
`python -m py_compile diagnose_win_prob_calibration.py` clean; bat checked for non-ASCII characters
(none found). Not run — per house rule, Imtiyaz runs it on his own PC.

## 2026-07-13 (night) — Volatile counter-HTF gate: 3-month WFO A/B REJECTED the filter
**Result:** `Run_VolHTFGate_AB_WFO_TEST.bat` (12-week/3-month WFO) completed both configs (12/12 weeks
each, run by Imtiyaz on his own PC):
- **Config A (gate OFF, baseline):** +32.5R, 207 trades, 9/12 positive weeks, avg +2.71R/week.
- **Config B (gate ON, `QGAI_VOL_HTF_GATE` active):** +17.1R, 183 trades, 8/12 positive weeks, avg
  +1.43R/week.
B is **-15.4R (-47%) worse than A**, and worse in every week from 2026-05-04 through the end of the
window — not a one-week fluke.
**Decision (per the bat's own pre-committed gate: B>=A required before running the 53-week FULL WFO):**
**B < A → REJECTED.** `Run_VolHTFGate_AB_WFO_FULL.bat` does not need to run. `QGAI_VOL_HTF_GATE` stays
OFF by default in `inference.py` (it was always env-gated — no code revert needed, zero live impact
either way). This confirms the same-day caveat found during the original signal-audit: re-measuring the
"against-HTF" bucket with raw ADX-DI instead of the SMMA-based `ts_htf_agreement` the gate actually
uses flipped it from losing to profitable — the original 53-week-baseline finding (Volatile 42-48%
win_prob band against dominant HTF direction is net-losing) was fragile/noise tied to the specific
SMMA-based direction signal, not a real tradeable edge. Results:
`backtest/results/volhtfgate_wfo_TEST_A_off/_WFO_SUMMARY.txt`,
`backtest/results/volhtfgate_wfo_TEST_B_on/_WFO_SUMMARY.txt` (both `_WFO_SUMMARY.csv` also present, per
the one-folder-per-run convention).
**Closes:** the "Volatile counter-HTF gate" TASKS.md row, the 5-step Volatile-state-model architecture
plan queued behind it (add H1/H4 DI + SMMA features to `model_volatile.pkl`) can now proceed without
waiting further, though it remains a separate, larger, not-yet-started piece of work.

## 2026-07-13 (night) — 4th Fable-5 opinion: smart Exit-AI model vs current rule-based exits
**Question asked (Imtiyaz):** could a dedicated "exit-AI" ML model (separate from the entry classifier)
be both smart (doesn't give back profit on reversals) and capture more of the available move than the
current rule-based exit (HTF trailing-stop + HTF-flip exit + regime TP-cap)?
**Fable-5's independent opinion (full text kept in session transcript; summary below):**
1. **Pushback on the capture% metric itself** — "% of total bar-to-bar path length" is an ill-posed
   denominator: it shrinks/grows purely with bar granularity (M15 vs M5) and isn't a real ceiling.
   Recommends replacing it with **per-trade MFE-capture ratio** (realized profit ÷ Maximum Favorable
   Excursion during the trade), and retiring the "10-20% of total path" framing entirely — capture% is
   a diagnostic, not the actual objective (total $/R is, per the project's own PRIMARY OBJECTIVE rule).
2. **Exit-AI is NOT the right next step — 3 cheaper things come first:**
   - **Post-cap continuation audit** (pure measurement, no code/model change): for the 44 trades that
     hit the TP-cap in the `active_baseline` report, measure how far price continued in the trade's
     favor between the cap-touch and the eventual HTF-flip. This single number tells us whether there's
     real money being left on the table or not — decides whether anything below is even worth doing.
   - **Main recommendation: don't hard-close at the TP cap.** Either (a) partial-exit 50-70% of the
     position at the cap and let the remainder ride on the existing HTF trail, or (b) keep the full
     position but switch the trail to a much tighter line (e.g. M15-line + 0.05-0.08% buffer, vs the
     current H1-line + 0.20%) at the cap-touch moment. Fable's reasoning: the TP-cap's real function is
     "giveback insurance" (lock in some profit before a reversal), not "profit ceiling" — trail-tightening
     provides the same insurance without capping the upside. This reframes the R/PF-vs-capture% conflict
     found earlier today as an artifact of the current *binary* hard-close design, not a fundamental
     trade-off — a third option (tighten, don't close) may recover both at once.
   - **Re-check whether the TP-cap %s themselves are overfit** — the `config.py:198` comment says the
     1.00% global cap was chosen on in-sample evidence; 34% of trades hitting a cap this tight, on a
     131-trade sample, is a thin base for a parameter this sensitive.
3. **If exit-AI is still pursued after the above:** keep it narrow. A binary gating classifier
   (predicts p(continuation)) invoked ONLY at 2 fixed decision points — cap-touch and HTF-flip-moment —
   never a free-running per-bar policy and never an RL agent (both flagged as over-engineered and
   leakage-prone for this data size).
4. **Biggest risk: sample size, called a "deal-breaker level" concern.** The entry model trains on
   ~98k bars; an exit model's effective sample size ≈ trade count (131), since in-trade bars within one
   trade are heavily autocorrelated. Fable's recommendation: do not start exit-AI training below
   ~500-1000 trades (a longer replay window or expanded shadow-entry set, not more bars of the same
   trades).
5. **Label construction (if/when attempted):** triple-barrier method (López de Prado) — ATR-scaled
   favorable/adverse barriers over a forward window (e.g. H=16 bars ≈ 4h), features strictly ≤ t using
   the SAME feature pipeline + leakage guards as the entry model. Explicitly warned against
   "distance-to-eventual-peak"-style labels (leak by construction, depend on the full future path).
   CV must be trade-episode-level (never split one trade's own bars across train/test) with
   purge+embargo at fold boundaries. Evaluate via OOS total $ replay, not classifier AUC (AUC can look
   good while total $ is worse).
**Status:** opinion only — nothing implemented yet. Queued in `docs/TASKS.md` with this exact priority
order: (a) post-cap continuation audit → (b) TP-cap-as-trail-tighten redesign + WFO A/B → (c) switch
the north-star metric to MFE-capture → (d) grow the trade sample → (e) only then consider exit-AI
phase 1. No code changed this entry — pure investigation/consultation.
**Follow-up (same night): step (a) tool built.** `engine/analyze_post_cap_continuation.py` (NEW) — for
every TPCAP-exited trade in a given `backtest_trades_*.csv`, replays forward from the cap-touch bar
using the SAME H1-line trail + HTF-flip exit logic already live for non-capped trades (reuses
`analyze_capture.py`'s `load_ohlc()`/`htf_lines()`/`BUF`/`SLMIN`), until the trail is hit or the HTF
flips (max 384 M15 bars / 4 days look-ahead). Reports, per capped trade and in aggregate: extra pts/R
gained or given back after the cap, % of trades that would have continued favorably vs reversed, and
average giveback (peak-vs-eventual-exit) — the exact numbers needed to decide whether the TP-cap is
leaving real money on the table (worth the trail-tighten redesign) or already doing its job (giveback
insurance, retire the capture% target instead). Pure pandas + OHLC replay, read-only, no model/retrain.
Delivered as `.bat` (house rule): `backtest/_runners/Run_PostCapContinuationAudit_TEST.bat`, pointed at
the existing `active_baseline` trades CSV (already on disk from the feature-sweep run) — runs in
seconds. **Sequencing (Imtiyaz):** run this AFTER the 67-feature validation sweep's nightly runs finish
— it kicks off a separate exit-side work stream, not blocking the feature-sweep. Verified:
`python -m py_compile analyze_post_cap_continuation.py` clean; bat file checked for non-ASCII characters
(the em-dash bug class from earlier this session) — none found. Not run — per house rule, Imtiyaz runs
it on his own PC.

## 2026-07-13 (night) — Feature-sweep: capture-efficiency tracking added (Fable-5 profit-focus opinion)
**Context:** Imtiyaz asked Fable-5 (independent 3rd opinion) how to find genuinely profitable features
from the 67-feature list without overfitting, given the real goal is not just a positive R number but
capturing more of the AVAILABLE market move (target: 10-20% of available move captured). Fable-5's
top recommendation: track a capture/efficiency metric per feature test, not just Total R — a feature
that raises R while capturing LESS of the available move (e.g. via fewer, larger cherry-picked trades)
is a red flag, not a win. Fable-5's second point — that HTF H1-flip exit logic is the bigger lever than
any single feature — was checked against `config.py` and found **already live**: `ratchet_htf_sl=True`
(06-23), `ratchet_htf_flip=True` (06-26), `ratchet_htf_forming=True` (06-30). No new implementation
needed there; it's a status clarification, not a pending action.
**Implemented in `engine/run_feature_sweep.py`:**
- `parse_report()` now also parses the backtest report's `captured X pts | available Y pts (all swings)
  / Z net | efficiency W% of path` line into `captured_pts`/`available_pts`/`available_net_pts`/
  `efficiency_pct` (None-safe if the line format doesn't match).
- `_auto_verdict()` takes a new `baseline_captured_pts` param; the shared `_stability_flags()` guard-rail
  set now also flags **captured points DOWN >10% vs baseline even when Total R improved** — catches the
  "R went up but we're capturing less of the move" false-positive Fable-5 warned about.
- `main()` prints captured-pts + efficiency-% for baseline and every feature test, and the per-tier
  `*_SUMMARY.csv` gained 3 columns: `captured_pts`, `delta_captured_pts`, `efficiency_pct`.
**Verified:** `python -m py_compile run_feature_sweep.py` clean. No retrain/backtest run (per house rule —
Imtiyaz runs all real tests on his own PC).

### ✅ RESOLVED same day — capture-audit refresh: 2.9% vs 5.7% explained (NOT a bug, a known trade-off)
**Question:** why does the current feature-sweep baseline (3-month, `active_baseline`) show only ~2.9%
capture efficiency when STRATEGY.md §7b's 06-23 shadow-sim (`analyze_capture.py`, 18-month/738-signal
window) measured ~5.7% for the same HTF-flip exit?
**Root cause found (code-read, no test run needed):** the `available path` denominator calculation is
IDENTICAL in both places (`close.diff().abs().sum()` over the window — `backtest_replay.py:964` and
`analyze_capture.py:117`), so it is not a methodology inconsistency in the metric itself. The real
cause is a **TP-cap config change made AFTER the 06-23 shadow-sim**:
- 06-23 shadow-sim ran with `ratchet_tp_cap_pct` still at its old default **10.0%** (effectively
  unconstrained — HTF-flip was the dominant exit).
- **06-26**: `ratchet_tp_cap_pct` tightened to **1.00%** (config.py:198) — chosen because it gave the
  best in-sample R/PF (+287R/PF1.74), a deliberate profit-optimization choice, not an oversight.
- **06-27**: `ratchet_tp_regime=True` adopted (config.py:218) — TP now regime-adaptive and even tighter
  in Volatile: Ranging 2.0% / Trending 1.0% / **Volatile 0.8%**.
**Proof:** `active_baseline/backtest_report.txt` (2026-04-01→06-29, 131 trades) exit-reason mix =
`{'FLIP': 59, 'TPCAP': 44, 'TRAIL': 22, 'SL': 5, 'EOD': 1}` — **44/131 (34%) of trades exit via the TP
cap**, locking profit at 0.8-2.0% of entry price regardless of how far the market keeps moving after.
The other 59 (45%) exit via HTF-flip and capture the move fine — the TPCAP-exited third of trades is
what drags the aggregate efficiency % down from the old 5.7% to the current 2.9%.
**Conclusion — real trade-off, not a bug:** higher path-capture-% and higher R/PF pulled in opposite
directions in the 06-26/06-27 data (wide/no TP cap → more path captured but worse R/PF; tight
regime-TP → less path captured but better R/PF), and the team knowingly chose R/PF. Recovering
10-20% capture would require re-widening `ratchet_tp_cap_pct` and/or disabling `ratchet_tp_regime`,
which the existing 06-26/06-27 evidence says would cost total R/PF — a new dedicated wide-TP-vs-tight-TP
A/B (not yet run) would be needed before touching this, since "maximize capture %" and "maximize R/PF"
are not the same objective on this data. No code changed — this was a read-only investigation.

## 2026-07-13 — Data-leakage guard: hard-blocks train/backtest overlap (Imtiyaz flagged, Claude fixed)
**What happened:** Imtiyaz found that several 2026-07-12 "Stage-1 3-month retrain backtest" screens
(OB redundancy, RemovedFeature top-10, RawMove, RegimeScore individual/combo A/B, InRange sweep,
LeakFix P1P2P3, Legacy CTFOFF) called `train.py` with no `QGAI_TRAIN_CUTOFF`, then replayed a backtest
starting `--from 2026-04-01` — but the labeled-trades training data (`Back_testing_data_final_cleaned_RELABELED.xlsx`)
ends **2026-04-29 20:00**. So Apr 1→29 (164 trades) overlapped train and "test" — genuine in-sample
leakage, not a clean 3-month OOS result. Worst-hit: the **B3-only feature prune (commit `10fad5f`,
"keep only h4_h1_regime_score") was already committed to live models based on this in-sample evidence,
with no WFO gate.** Separately found (independent of this fix): `run_wfo.py` had a 1-day-per-fold
train/test boundary overlap too (`QGAI_TRAIN_CUTOFF=w_start` == the backtest's own `--from w_start`).
**Fix (permanent, code-level, not a one-off rerun):**
- **`engine/leakage_guard.py`** (NEW) — every model file gets a `<name>_meta.json` sidecar recording
  its real data exposure (training/validation/calibration/test end dates). Before any backtest,
  `assert_no_leakage()` takes the MAX exposure across every GATING model (main/buy/sell/state models/
  HMM/slot-table) and hard-**raises** (not warns) if that date is on-or-after `--from`. BigWin/Duration
  predictors are tracked but excluded from the blocking max (non-gating, deliberately not
  retrained per WFO fold — would otherwise false-block all of WFO). Online/drift learners are
  exempt (fresh, no historical fit at train time).
- **`engine/train.py`** — writes the new sidecars for every model (hmm/slot_table/state models/
  big_win/duration/online/drift — previously only main+buy+sell had any meta at all); `_cutoff_metadata()`
  extended with `training_start`, `validation_end`, `model_created_at`, `data_hash`. Whole training run
  now goes through `_run_training_atomically()` — writes to a temp `final_building_tmp` dir, only
  swaps into `data/models/final` on full success (old version kept at `final_prev`); a crash/kill
  mid-training leaves the live models untouched.
- **`engine/backtest_replay.py`** — new `--allow-in-sample` flag (explicit opt-out only, prints a loud
  "NOT valid OOS proof" banner, never a default) is the *only* way to run a knowingly in-sample sanity
  backtest (e.g. current live model over full 2022→2026 history). Without it, an overlapping run now
  hard-exits (`SystemExit(1)`) before touching any data.
- **`engine/run_wfo.py`** — fixed the 1-day fold-boundary overlap: `QGAI_TRAIN_CUTOFF` is now
  `week_start − 1 day` (strictly before the test week) instead of `week_start` itself, at all 3
  subprocess call sites (trail sweep, PB-entry sweep, main WFO loop). Matches the file's own docstring
  ("model on data < week_start") which the code hadn't actually implemented.
- **`engine/tests/test_leakage_guard.py`** (NEW) — 9 automated tests: cutoff==start/after-start → FAIL,
  cutoff-before-start → PASS, missing metadata → FAIL, one directional model newer → latest wins,
  non-gating model's stale cutoff doesn't block, `--allow-in-sample` overrides but still reports FAIL,
  no-exposure meta without the explicit flag is unsafe, plus a regression test for the
  `in_range_phase`/big-move lookahead leak family this audit started from. All 9 pass.
**Verified:** real (non-synthetic) smoke test — retrained with `QGAI_TRAIN_CUTOFF=2026-04-01`, confirmed
`model_meta.json`/`hmm_meta.json` correctly recorded `training_end=2026-04-01` (HMM's own train-split
cutoff even earlier, 2025-11-19) — then confirmed `leakage_guard.assert_no_leakage()` correctly BLOCKS
`--from 2026-04-01` (same day) and correctly PASSES `--from 2026-04-02`.
**Independently re-verified by Imtiyaz on his own PC (2026-07-13, `Run_LeakageGuard_Smoke_TEST.bat`):**
9/9 unit tests pass; real retrain (cutoff 2026-04-01) → `--from 2026-03-25` (window starting BEFORE
cutoff, genuine overlap) correctly **BLOCKED** with the full leakage report + `DATA LEAKAGE BLOCKED`
error; `--from 2026-05-05` (clean, after cutoff) correctly **PASSED** and produced a real backtest
report (+2.9R, 9 trades, PF 3.63); Step 5 correctly restored the original live models from
`final_prev` afterward. Two bat-authoring bugs found and fixed along the way (both in the .bat only,
not in the guard logic): (1) em-dash characters inside REM/echo lines broke cmd.exe's parser entirely
(same mojibake class as the earlier heartbeat-emoji bug) — replaced with plain ASCII; (2) parentheses
and `!` inside echo text nested INSIDE an `if (...) else (...)` block get misread by cmd.exe as
block-structure characters, silently truncating output or aborting the whole script — rewritten to
avoid parens/`!` inside any such block. Also caught and fixed a flawed first draft of the test
scenario itself: it used `--from 2026-04-15` (14 days AFTER the 2026-04-01 cutoff — not actually
overlapping) and expected a BLOCK, which the guard correctly refused to do; corrected to
`--from 2026-03-25 --to 2026-04-10` (a window that genuinely starts before the cutoff).
**Delivered as .bat (per house rule — long/real runs execute on the user's PC, not inline):**
`backtest/_runners/Run_LeakageGuard_UnitTests.bat` (fast, synthetic, ~1s) and
`Run_LeakageGuard_Smoke_TEST.bat` (real retrain + real backtest_replay.py block/pass check, auto-restores
the original live models from `final_prev` afterward).
**Known residual risk:** the ~30 already-existing 2026-07-12 result folders (`ob_redundancy_*`,
`removed_feature_*`, `regimescore_*`, `rawmove_ab_*`, `individual_ab_*`, `combo_b3b4_*`, `inrange_sweep_*`)
were produced BEFORE this guard existed and are still in-sample-contaminated — re-run them (now
correctly blocked/fixed) before trusting any KEEP/REJECT decision drawn from them, especially the
already-committed B3-only prune.
**First-run note:** `big_win_model_meta.json`/`duration_model_meta.json` don't exist until one full
(non-`QGAI_CORE_ONLY`) `python train.py` has run at least once — do that before the very first WFO run
on a fresh checkout, or the guard's metadata scan will (correctly) fail on their absence.

## 2026-07-13 — Root-cause fix: dedicated test_workspace, live model structurally unreachable
**Imtiyaz's call after 3 same-day model-loss incidents (crash mid-swap, concurrent processes, sweep
chain) — instead of another backup/restore variant, separate test model-building from the live model
entirely.** `engine/config.py`'s `PathConfig.models_dir` now respects an env override
`QGAI_MODELS_DIR` (unset = unchanged default, `data/models/final` — the live bridge is unaffected
either way). `engine/run_feature_sweep.py` sets this to a dedicated `data/models/test_workspace/` for
every retrain — the one-time "true-original backup" dance added earlier today is now unnecessary and
removed entirely (nothing to back up when `final` is never touched). All 4 FeatureSweep `.bat` files
(`_TEST`, `_Tier1_Active`, `_Tier2_HighProbability`, `_Tier3_Remaining`) updated: no more
backup/restore step, no more "close the live bridge first" warning — the live bridge can now run
*at the same time* as any of these with zero conflict. `Run_VolHTFGate_AB_WFO_FULL.bat` (not running
at the time) updated the same way (`QGAI_MODELS_DIR=test_workspace` before both `run_wfo.py` calls).
`Run_VolHTFGate_AB_WFO_TEST.bat` was mid-run at the time (actively read by a live cmd.exe process) —
editing a running `.bat` file risks the interpreter's line-position tracking jumping to the wrong
line, so that file's fix is deferred until its current run finishes.
**This supersedes the two earlier fixes today** (the lock file and the `PRE_FEATURE_SWEEP_ORIGINAL`
dedicated backup) for anything using `QGAI_MODELS_DIR` — those remain in place as defense-in-depth for
any script that still points at `data/models/final` directly (e.g. the leakage-guard smoke-test bats,
which intentionally exercise the real atomic-swap+backup mechanism as their whole point).

## 2026-07-13 — 🔴 Feature-sweep restore bug (3rd model-loss incident, found + fixed)
**What happened:** after `Run_FeatureSweep_TEST.bat` completed (2 features: `move_1hr`, `price_pos`),
its "restore original live model" step used `final_prev` — but `final_prev` only ever holds the model
from the IMMEDIATELY PRIOR retrain in `train.py`'s atomic swap. A sweep runs baseline -> feature1 ->
feature2 -> ... in sequence; by feature #2, `final_prev` already held feature1's ablated model, not the
true pre-sweep original. `data/models/final` was left holding `price_pos`-ablated model, and its
"restore" silently put back `move_1hr`-ablated model instead of the real production model — the true
original was gone from both locations (same failure shape as the two earlier incidents, different
mechanism: a sequential-chain problem this time, not concurrent writes).
**Recovery:** restored again from `data/models/backups/ACTIVE27_DROP_PRE_20260713_083334` (third use of
this same known-good snapshot today) via `robocopy /MIR`; confirmed no `python.exe` running first.
**Fix:** `engine/run_feature_sweep.py` now takes a ONE-TIME, dedicated backup of the real
`data/models/final` to `data/models/backups/PRE_FEATURE_SWEEP_ORIGINAL/` at the very start of `main()`
— created once (checked via `.exists()`), never overwritten by later retrains, shared across all
tiers/nights so the true starting point is always recoverable regardless of how many features get
swept in between. All 4 `.bat` files (`Run_FeatureSweep_TEST`, `_Tier1_Active`, `_Tier2_HighProbability`,
`_Tier3_Remaining`) updated to restore from this dedicated backup instead of `final_prev` at the end.
**Pattern across all 3 incidents today:** every one was a variant of "assume exclusive/simple ownership
of `data/models/final`'s backup slot, get surprised by a longer chain of events than assumed" (crash
mid-swap; two processes; one process but many sequential swaps). The lock file (2nd incident's fix)
guards against concurrent runs; this fix guards against a single run's own multi-step chain. Recommend
treating `final_prev` as purely "undo the very last retrain," never "get back to where I started."

## 2026-07-13 — Fable-5 review of the feature-sweep design + 4 fixes applied
Imtiyaz asked for a Fable-5 second opinion on `run_feature_sweep.py`'s redesigned methodology (3-stage
priority plan, auto-verdict heuristic). Findings and fixes:
1. **Duplicate retrains (biggest concrete bug):** `priority_batch`'s 4 features that also appear in the
   full `active` tier (`H4_DI_diff`, `h4_adx_slope`, `move_4hr`, `momentum_aligned_2hr`) were cached under
   TIER-PREFIXED labels (`priority_batch_06_H4_DI_diff` vs `active_23_H4_DI_diff`) — each would retrain
   TWICE for identical information, and worse, every tier's own `{tier}_baseline` (which changes nothing)
   was ALSO being recomputed from scratch per tier (4x waste). **Fixed:** cache keys are now
   tier-independent (`baseline`, `ablate_<feat>`, `unprune_<feat>`) — any tier reusing the same
   feature+mechanism gets an instant cache hit.
2. **Verdict asymmetry:** the stability guard-rails (week-consistency, single-trade-share, BUY/SELL and
   regime concentration) only applied to "looks good" verdicts (`CORE_KEEP`, `NEEDS_1YEAR_CONFIRMATION`)
   — a `DROP_CANDIDATE` verdict (recommending removal of an active feature) got NO red-flag check, despite
   being at least as risky a decision. **Fixed:** same guard-rails now apply to `DROP_CANDIDATE` too,
   downgrading to `REVIEW` when triggered.
3. **Unused parameter:** `_auto_verdict()` accepted `baseline_trades` but never used it. **Fixed:** added
   a stability-flag check — if a feature's trade count moved more than 30% vs baseline, the comparison
   isn't apples-to-apples and gets flagged.
4. **Noise-floor not calibrated (flagged, not fully solved):** the ±0.5R "flat" threshold is a fixed
   constant, not measured against this system's actual retrain-to-retrain variance. Documented as an open
   caveat — a future improvement would be comparing repeated baseline reruns (different seeds) to measure
   the real noise floor before trusting any verdict near the ±0.5R boundary.
Also flagged (open, not yet acted on): LOCO (leave-one-out) ablation can't see feature *combinations* or
correlated-feature masking (dropping one of two correlated features can look "redundant" only because its
correlated twin absorbed the signal); the whole 3-month screen is a SINGLE market-regime sample, so a
`DROP_CANDIDATE` verdict should also pass the 1-year gate before actually being dropped, not just
`NEEDS_1YEAR_CONFIRMATION` re-adds — consistent with the project's own "don't block profitable trades"
philosophy.

## 2026-07-13 — Feature aliases extended to all 67 (for the feature-sweep report)
`engine/features.py`'s existing `FEATURE_ALIASES` table only covered 34 features (the 27 active +
`hmm_state` + 6 already-aliased dropped OB features). Added alias + indicator-category entries for
the remaining 34 (`H1_ADX`, `M30_ADX`, the whole `ts_*` SMMA-trend family, `corr_imp_ratio`,
`trade_direction`, EMA200/news/session/volume variants, etc.) — all 67 known features now have a
readable `(alias, indicator)` pair. `engine/run_feature_sweep.py` updated to print
`feature [alias / indicator]` per candidate and include `feature`/`alias`/`indicator` columns in each
tier's `_SUMMARY.csv`.

## 2026-07-13 — 🔴 Concurrent-write corruption of data/models/final (2nd incident, found + recovered)
**What happened:** while the new `run_feature_sweep.py` sanity test was retraining, Imtiyaz was
independently running his own test bat (`Run_Active27_DropScan_TEST.bat` or similar) — BOTH processes
were writing to `data/models/final` (and its atomic-swap partner `final_prev`) at the same time. Every
`train.py` run assumes it has exclusive ownership of that directory during its atomic swap
(`_run_training_atomically()`); with two independent runs interleaving, files ended up mixed from both:
`buy_model_meta.json`/`sell_model_meta.json` showed `requested_training_cutoff=2026-03-31` (this
session's feature-sweep test) while `model_meta.json`/`hmm_meta.json`/state-model metas in the SAME
directory showed `requested_training_cutoff=2026-05-31` (Imtiyaz's concurrent run) — an internally
inconsistent model set. `final_prev` was equally contaminated (same mixed-cutoff pattern), and
`final_building_tmp` was left behind orphaned (an interrupted build, missing several files).
**Recovery:** confirmed no `python.exe` process was still running (Imtiyaz closed his window), then
restored AGAIN from the same known-good backup used in the first incident,
`data/models/backups/ACTIVE27_DROP_PRE_20260713_083334/` (verified consistent, 28 files, all
2026-07-13 05:07-05:09 timestamps) — via `robocopy /MIR`. Deleted the contaminated `final_prev` and the
orphaned `final_building_tmp`. `hmm_meta.json` is absent from this backup (it predates today's
leakage-guard metadata work) — this is fine and actually SAFE: `leakage_guard.py` will correctly
hard-block any backtest against this model until a fresh retrain (with the current `train.py`)
regenerates the missing sidecar, rather than silently running against an unverifiable model.
**Rule going forward (no code enforces this yet — operational discipline only):** run only ONE
train/backtest job against `data/models/final` at a time, whether it's Claude's or Imtiyaz's own —
same discipline as "close the live bridge before retraining," now extended to "check nothing else is
mid-retrain before starting a new one." **Open TODO:** consider a simple lock file
(`data/models/.training_lock`, written at the start of `_run_training_atomically()` and removed at the
end/on exception) that makes a second concurrent `train.py` invocation refuse to start instead of
silently colliding — not yet implemented.

## 2026-07-13 — Systematic 67-feature validation sweep (tool + bug fix)
**Context:** Imtiyaz's own worry — since ANY past backtest could theoretically have a leakage or
validation issue not yet caught, he wants every one of the 67 known features (27 currently active +
40 historically dropped, `features.py` `FEATURE_COLS` + `_ZERO_IMP`) individually re-checked via a
clean 3-month retrain+backtest, priority-ordered, over 3-4 overnight runs.
**Built:** `engine/run_feature_sweep.py` (NEW) — orchestrates one retrain+backtest per feature
(ablate an active feature via `QGAI_ABLATE`, or restore a dropped one via `QGAI_UNPRUNE`), all
against a shared baseline, leakage-guard-safe (`QGAI_TRAIN_CUTOFF=2026-03-31`, backtest
`2026-04-01→2026-06-29` — a full 3-month margin, not just the bare 1-day minimum). Resume-safe
(cached `result.json` per feature, safe to stop/restart across nights) with ETA countdown (house
rule). Produces a `_SUMMARY.csv` per tier with `total_r`/`pf`/`wr`/`delta_vs_baseline` per feature.
**Priority tiers** (delivered as 4 `.bat`, one per night, per house rule — no heavy runs execute
inline): `Run_FeatureSweep_TEST.bat` (2 features, sanity check first) → `Run_FeatureSweep_Tier1_Active.bat`
(27 active, priority = current `feature_importance.csv` ranking) → `Run_FeatureSweep_Tier2_HighProbability.bat`
(~20 dropped features most likely to matter — the SMMA-trend family + raw ADX + OB/SR + previously-
flagged partial signals) → `Run_FeatureSweep_Tier3_Remaining.bat` (~19 remaining dropped features).
**Bug found + fixed while sanity-testing the new tool (before handing it off):** `train.py`'s
`_validation_end`/`_test_end` variables (added earlier today for the leakage-guard metadata work)
were computed in Step 9, but Step 8 (BigWin/Duration meta) already referenced them — `UnboundLocalError`
on every non-core-only retrain. Moved the computation up to right after the train/val/test split
(Step 4), before Step 5 onward, removed the now-duplicate later definition. Caught by
`Run_FeatureSweep_TEST.bat`'s own sanity run (a REAL retrain, not a synthetic test) before either
tier bat was handed off — exactly the "test small first" pattern this project already follows for a
reason. Verified fixed with a second real sanity run.

## 2026-07-13 — Feature-sweep redesigned around a permanent registry system (Imtiyaz's detailed spec)
**Retroactive changelog entry (added 2026-07-15):** this change was recorded in `docs/TASKS.md` at
the time but never got its own `FIXES_CHANGELOG4.md` entry, against this project's own rule that
every change goes into both. Backfilled after the gap was noticed while investigating today's
feature-sweep runs.
**What changed:** `engine/run_feature_sweep.py` (built same day, entry above) was redesigned around
Imtiyaz's exact priority plan. It now supports **permanent registry folders** — every runner gets a
stable `FS67-NN` ID that appears in the `.bat` filename, the result folder name, the summary CSV,
and every per-feature trade/signal CSV — plus cutoff/window overrides and baseline reuse via a new
`QGAI_SWEEP_BASELINE_JSON` env var (so tiers 2-4 don't re-train the same 3-month baseline tier 1
already built).
**New layout:** organized runners moved to `backtest/_runners/feature_sweep_67/`; organized results
to `backtest/results/feature_sweep_67/` (registry table + baseline-reuse rule documented in that
folder's own `README.md`). Screening runners: `FS67-01_RUN_PriorityBatch.bat` → `FS67-01_priority_batch`
(creates the 3-month baseline); `FS67-02_RUN_Tier1_Active.bat`, `FS67-03_RUN_Tier2_HighProbability.bat`,
`FS67-04_RUN_Tier3_Remaining.bat` (all reuse `FS67-01_priority_batch/baseline/result.json`, never
re-run baseline). OOS1Y confirmation runner: `FS67-11_RUN_PriorityBatch_OOS1YConfirm.bat` →
`FS67-11_priority_batch_oos1y_confirm`, matched to `OOS1Y-01`'s exact cutoff/window
(`2025-06-28` train cutoff, `2025-06-29 → 2026-06-29` backtest). Priority-batch feature list:
`h4_support_dist, h1_resist_dist, move_2hr, ts_line_dist_pct, tick_volume, H4_DI_diff,
h4_adx_slope, move_4hr, momentum_aligned_2hr, h1_support_dist`. Optional all-in-one:
`FS67-00_RUN_ALL.bat`. Each feature auto-routes to ablate (active feature) or unprune (dropped
feature) mode and computes BUY/SELL split, regime split, week-consistency, capture-efficiency, and
a verdict string.
**Decision flow this enables:** FS67-0N quick 3-month screen → FS67-1N OOS1Y confirm for any
promising candidate → WFO before live adoption. (First real use of this flow, 2026-07-15:
`h4_support_dist` passed the 3-month screen at +8.1R but was `CONFIRMED_DROPPED` at -15.3R on the
1-year OOS1Y confirm — exactly the failure mode this staged design exists to catch.)

## 2026-07-13 — BUY-signal audit fixes: model-version logging + Volatile counter-HTF gate (candidate, WFO pending)
**Context:** root-cause audit of the 2026-07-13 04:30 BUY signal (see earlier entry / artifact) plus a
Fable-5 second opinion produced two concrete, testable findings. Both implemented as reversible,
default-safe changes — NOT yet adopted into live decision behavior.
**#1 Model-version logging (DONE, live-safe, additive only):**
- `engine/inference.py` — `LiveInferenceEngine.__init__` now reads `model_meta.json` once and builds
  `self.model_version = f"{model_created_at}_{data_hash}"`; `_make_result()` includes it in every
  returned signal dict.
- `engine/bridge_data.py` — `log_signal()` writes a trailing `model_version` CSV column (same
  migration pattern as the 2026-07-09 `trade_action` column) + a matching SQLite `ALTER TABLE`.
- Verified via an isolated smoke test (scratch files only, real signals_all.csv/qgai.db untouched).
- Closes exactly the gap the 04:30 audit hit: the exact live model snapshot that produced a past
  signal can now always be traced.
**#2 Volatile counter-HTF gate (CODE DONE, env-gated OFF by default, WFO test PENDING before any
live adoption):**
- Finding: on the honest 53-week WFO baseline (`wfo_adxdeath_novol_baseline_20260710`, +80.5R,
  leak-free), Volatile-regime trades in the 42-48% win_prob band that go AGAINST the dominant H1/H4
  DI direction (via `ts_htf_agreement`) are net-losing: n=38, total -1.9R, PF 0.88 — while the SAME
  band aligned WITH the HTF direction is strongly profitable: n=48, +18.9R, PF 3.78.
- Ruled out time/slot confound: `f_slot_win_rate` nearly identical between the losing (0.413) and
  winning (0.420) buckets; losing bucket spread across 18 different hours, all 5 weekdays, 24
  different weeks (not concentrated in a few bad episodes or a known-dead time slot). Controlling
  for slot-quality tercile, the counter-HTF penalty holds at every tercile.
- This is NOT a time-based filter (Imtiyaz's own stated principle: build the strategy first, keep
  time-features soft/model-internal, no hard time-of-day blocks) — it's a directional-agreement +
  confidence gate on already-existing features (`ts_htf_agreement`, `hmm_state`, `win_prob`).
- Implemented in `engine/inference.py`, gated behind `QGAI_VOL_HTF_GATE` (default `"0"` = OFF, exact
  no-op — matches the `QGAI_REGIME_INRANGE`/`QGAI_CTF_FADE` toggle convention). SKIPs a signal only
  when: `hmm_state == "Volatile"` AND `0.42 <= final_prob < 0.48` AND the trade direction disagrees
  with `ts_htf_agreement`'s sign.
- Delivered as `.bat` per house rule: `Run_VolHTFGate_AB_WFO_TEST.bat` (5-week quick check) and
  `Run_VolHTFGate_AB_WFO_FULL.bat` (full 53-week confirm) — both A (gate OFF) vs B (gate ON).
  **Decision rule: adopt live ONLY if B total R >= A, DD not worse, and the improvement isn't
  concentrated in 1-2 folds.** Not yet run as of this entry.
- **⚠️ CAVEAT found same day (Imtiyaz asked "does this model not pay attention to ADX?"):** the gate's
  "counter-HTF" check uses `ts_htf_agreement` (the SMMA/20-period-trend system), NOT the raw ADX-DI
  system (`H1_DI_diff`/`H4_DI_diff`) that the original 04:30 signal audit actually flagged. Re-measured
  the same Volatile 42-48% band using ADX-DI-based direction instead: **the "against" bucket flips to
  PROFITABLE (+1.57R, n=38) instead of the SMMA-based -1.86R.** The two direction measures agree 89.5%
  of the time overall, but within this band they diverge enough to matter — the entire SMMA-based
  negative result traces to a tiny 6-trade subgroup ("SMMA says against, ADX-DI does NOT": -2.01R)
  while the ADX-DI-against/SMMA-not-against subgroup (also n=6) is +1.42R. **This substantially weakens
  confidence in the original finding — it looks fragile/possibly noise, not a robust pattern, once
  measured a different (equally valid) way.** The `QGAI_VOL_HTF_GATE` code stays (default OFF, zero
  live risk), but go into the WFO A/B test expecting it may well show B < A given this caveat — the
  WFO run is now the real arbiter, not the bucket read.
- **Bigger-picture note (Imtiyaz, same day): "need to rethink architecture of the model."** The
  underlying issue this caveat surfaces: the system carries (at least) two parallel, independently-
  computed HTF-trend-direction representations — the ADX/DI family (`H1_ADX/H4_ADX/H1_DI_diff/
  H4_DI_diff`, used by the combined + directional models) and the SMMA/20-trend family (`ts_trend_h1/
  h4`, `ts_htf_agreement`, used by `ts_*` features and now this gate) — and no part of the pipeline
  reconciles them or flags when they disagree. Different sub-models (combined vs Volatile-state vs
  directional) each see different SUBSETS of these two families (see the Volatile-state model's
  17-feature list, which has neither raw ADX/DI). Worth a dedicated architecture review: which HTF-
  direction signal is actually more predictive, whether they should be unified into one canonical
  feature, and whether every regime/directional sub-model should have consistent access to it. Not
  scoped or started — flagged for a future session.

## 2026-07-13 — 🔴 Atomic-swap bug lost the true live model (found + recovered same session)
**What happened:** During repeated `Run_LeakageGuard_Smoke_TEST.bat` runs (see the entry above), the
NEW `_run_training_atomically()` backup mechanism ended up with **both** `data/models/final` and
`data/models/final_prev` holding the SAME test model (`QGAI_TRAIN_CUTOFF=2026-04-01`, created
`2026-07-13T12:46:32`) — the true pre-session live model (trained 2026-07-13 05:07, 28 features, no
cutoff) was gone from both slots. Root cause of WHY `final_prev` also ended up wrong is not fully
diagnosed (suspect: two back-to-back atomic swaps across two separate `train.py` process runs, the
second one's own backup-then-swap overwriting `final_prev` with a copy of `final` at a moment `final`
already held the first run's test model) — flagged as an open risk below, not fully root-caused.
**Recovery:** found `data/models/backups/ACTIVE27_DROP_PRE_20260713_083334/` — a backup Imtiyaz's own
`Run_Active27_DropScan_TEST.bat` made at 08:33:34 that morning (before any of today's leakage-guard
testing), holding the exact model that generated the 04:30 BUY signal backfilled at 08:49:03 (verified:
no retrain happened between 08:33 and 08:49). Confirmed no `python.exe` process was running (bridge was
down), then `robocopy /MIR` restored this backup into BOTH `final` and `final_prev`. Verified:
`model_meta.json` now shows `timestamp: 20260713_0507`, 28 features, `n_trades: 2743` (matches the
pre-session state).
**Open risk / TODO:** `_run_training_atomically()` (`train.py`) needs a safety improvement — it should
refuse to silently overwrite `final_prev` if `final_prev` already exists and looks like it might still
be needed (e.g. compare a hash/timestamp, or keep more than one generation of backup) rather than
always doing a single blind `rmtree` + replace. Until that's added: **do not run back-to-back
retrain/atomic-swap tests without an independent backup (git commit, or manual copy) of
`data/models/final` first.**

## 2026-07-12 — ADX redundancy prune: 3 features dropped (Imtiyaz)
**What:** Dropped `h4_ranging_h1_extended`, `M30_ADX`, `H1_ADX` from model via `_MANUAL_PRUNE` (36→33 features).
**Why:** Individual ablation A/B (1-month, retrain each):
- D1 `h4_ranging_h1_extended`: +14.8R = exactly baseline (model uses it ZERO — `h4_h1_regime_score=-1` covers the same condition)
- D2 `M30_ADX`: +15.3R (+0.5R better without — middle TF redundant when H4_ADX+M15_ADX present)
- D3 `H1_ADX`: **+18.0R (+3.2R, +22% gain)** — WR 59.5%, PF 2.55, DD 0.5% (best). `h1_adx_slope` + `H1_DI_diff` already carry the H1 information; raw H1_ADX was overfeed/noise.
**Reversible:** Remove lines from `_MANUAL_PRUNE` + retrain.
**⚠️ NEEDS WFO GATE** (full-year confirm before live adoption).

## 2026-07-12 — PART-1 feature restore: only B3 kept (Imtiyaz)
**What:** Of the 4 PART-1-pruned features tested for restore, only `h4_h1_regime_score` (B3) kept in model. `h4_trending_h1_aligned` (B1), `h4_ranging_h1_neutral` (B2), `trade_direction` (B4) re-added to `_MANUAL_PRUNE`.
**Why:** Individual 1-month A/B: B3 +14.8R, B4 +12.3R, B1 +10.6R, B2 +10.2R vs baseline +8.9R. BUT combo B3+B4 = +8.8R (flat — interference). B3 already encodes B1+B2 info as a gradient score (-1 to +2); B4 overlaps/interferes. Keeping only B3 = cleanest signal, no overfeed.
**Net:** 35 → +B3 → −B1/B2/B4 = 36 feat (before ADX prune above → 33 feat final).
**Reversible:** Remove B1/B2/B4 from `_MANUAL_PRUNE` + retrain.

## 2026-07-12 — in_range_phase REGIME-AWARE cutoff applied (Imtiyaz)
**What:** `in_range_phase` (rank #1 model feature) now uses a per-regime |H4 move| cutoff instead of one global 0.5%: **Trending 0.5%, Volatile 0.6%, Ranging 0.5%** (unchanged — noisy/small sample). Implemented in `inference.py` right after `hmm_state_name` is known, before model routing — overrides `feat_dict["in_range_phase"]` using the already-computed raw `h4_move_pct`. Applies identically to live and backtest (both use `LiveInferenceEngine.decide()`). No retrain needed — `in_range_phase` stays a binary model input, only WHERE the line sits changed per regime.
**Why:** A 1-month sweep of the global threshold (0.3–0.7%) showed the per-regime optimum differs: Trending peaks at 0.5% (+5.2R), Volatile peaks at 0.6% (+8.5R) — a single global cutoff was averaging away real per-regime signal. Combined (Trending 0.5 + Volatile 0.6 + Ranging 0.5): **+13.8R (1-month) vs +8.9R global** — but small samples (13-46 trades/regime).
**Reversible:** env `QGAI_REGIME_INRANGE=0` reverts to old global-0.5% behavior instantly (no retrain either way).
**⚠️ NEEDS FULL-YEAR + WFO CONFIRM** before trusting live (1-month is directional only). Bat: `Run_InRange_RegimeSwap_AB_FullYear.bat` (A=off vs B=on).

## 2026-07-12 — RAW H4-move features added (hidden-hard-filter fix) (Imtiyaz)
**What:** Added raw continuous `h4_move_pct` + `cum3_move_pct` to the model (`features.py` get_range_features + FEATURE_COLS).
**Why:** Audit of hardcoded thresholds inside features (user: "like ADX≥19") found most binary-cutoff features were already pruned WITH their raw continuous counterparts in the model — EXCEPT `in_range_phase` (rank #1): it exposes only a hardcoded `H4 move < 0.5%` binary and the raw `h4_move_pct` was NOT in the model. So the model was forced onto a human 0.5% cutoff. Same for `is_big_move` (2.0%). Now the raw H4 move % / cum-3-H4 move % are features → the model learns its OWN range/big-move threshold. "model over hard filters".
**Verified:** compute_features returns h4_move_pct=0.0917 / cum3_move_pct=-0.2593 on real data; both in FEATURE_COLS, not pruned; syntax OK. Model +2 features.
**⚠️ NEEDS RETRAIN + A/B GATE.** Bat: `Run_RawMove_AB_Retrain_Backtest_TEST.bat` (A=ablate raw vs B=with raw, 1-month). Keep raw only if B > A on R with healthy WR. REVERT: remove the 2 lines from FEATURE_COLS + get_range_features (backup `_backup_pre_rawmove_20260712`).

**RESULT ❌ REJECTED (same day):** single-backtest B +6.8R/55tr/WR54.5% vs A +8.9R/63tr/WR60.3%; WFO ~5wk B +8.9R vs A +11.7R. The model did NOT learn/improve from the raw values even with weekly WFO retraining — they added noise, not signal. Binary `in_range_phase` is cleaner for this model. Removed h4_move_pct/cum3_move_pct from FEATURE_COLS (get_range_features still computes them, just unused); restored the 35-feat +8.9R baseline model to data/models/final. Good hypothesis, negative result — recorded so it isn't re-tried blindly.

## 2026-07-12 — Filter CODE removed: range + #2 pre-news + #4 early-discount (Imtiyaz)
**What:** Deleted the filter code (not just flags) for the 3 removed entry filters — per Imtiyaz, without waiting for the range full-year confirm. Net −87 lines across 4 files, all git-reversible:
- **RANGE** — `backtest_replay.py`: range-detection block → `_range_block = False` constant; `--no-range-skip` arg deleted. `bridge_main.py`: BLOCK_RANGE compute block → constant. Config keys `skip_range_phase_entry`/`range_phase_min_prob` KEPT (read by `bridge_main` startup banner + `bridge_dashboard` display).
- **#2 PRE-NEWS** — `inference.py`: pre-news penalty branch collapsed to the plain regime threshold; `QGAI_PRENEWS_PENALTY` env removed.
- **#4 EARLY-DISCOUNT** — `inference.py`: whole early_entry_discount block deleted (`_ed_disc = 0.0` kept for the downstream export); config keys `early_entry_discount`/`ed_*` removed; `QGAI_EARLY_DISCOUNT`/`QGAI_ED_*` env gone.
**Design:** kept `_range_block`/`_ed_disc` as harmless constants so the shared downstream compound conditions (`not _range_block and ...`) and the `blocked_by`/CSV/dashboard schema are untouched — minimal-risk removal.
**Bug-check (code-level PASS):** all 4 files syntax OK, imports OK, no dangling refs (only REVERT comments), range cfg-key still present (dashboard safe), early_entry_discount key gone.
**Parity smoke (pending):** `Run_FilterRemoval_Parity_TEST.bat` must reproduce +8.9R/63tr (identical to range_ab_TEST_OFF) — since the filters were already functionally off, removing the code must not change results. Any diff = a removal bug.
**⚠️ Live effect on next bridge restart.** Demo first.

## 2026-07-12 — H4 Range-phase entry filter REMOVED (Imtiyaz)
**What:** `config.py` `skip_range_phase_entry` **True → False**. The range filter (skip BUY/SELL when `in_range_phase==1`) is now OFF in live.
**Why:** It was added post-hoc for a small profit bump WITHOUT a proper WFO/OOS test ("Demo/WFO confirm" TODO never closed). On the honest 34-feat model it blocks ~63% of actionable BUY/SELL (30d smoke: 121 BUY + 41 SELL blocked, only 96 through) — the dominant entry-stopper by far. Prior A/B (2026-07-03) showed keeping = +10R, but that was IN-SAMPLE on the leaky pre-fix model. Removing now; re-add only if an honest A/B/WFO proves it raises TOTAL R.
**Measurement (rule: judge by profit):** `Run_Range_AB_Backtest_TEST.bat` (30d ON vs OFF) + `Run_Range_AB_Backtest.bat` (1yr). Uses env `QGAI_SKIP_RANGE=1/0` to A/B regardless of config. If OFF R ≥ ON R → removal confirmed; if OFF much lower → reconsider revert.
**Reversible:** `skip_range_phase_entry=True` or env `QGAI_SKIP_RANGE=1`. FILTERS_MASTER #3 updated (status + change log).
**⚠️ Live effect on next bridge restart.** Test on demo first.

## 2026-07-12 — Leakage-audit fixes P1+P2+P3 applied (Imtiyaz)
**What (all HONEST, no lookahead — reversible):**
- **P1 — DROP `corr_imp_ratio`** (`features.py` `_MANUAL_PRUNE`, 35→34 feat): confirmed double leak (swing detection reads 3 future H4 candles via `iloc[i+j]` + availability gate stamps ~16h early). Low importance (rank #28, AUC −0.014), redundant with honest `ts_trend_h4`/`h4_ADX`/`in_range_phase`. Gating honestly would only yield a 16h-stale near-useless value → drop, not fix.
- **P2 — `ob_strength` confirm timing** (`build_ob_table:267`): `confirm_datetime = datetime.shift(-1)` → `shift(-2)`. Old exposed the OB at the impulse candle's START while `ob_strength` = that candle's FULL (not-yet-closed) range → strength leaked ~1 HTF bar. Now visible only after the impulse fully closes. Zone features (dist/in_zone) were already safe.
- **P3 — news `dev_norm` expanding stats** (`load_news:203`): whole-sample per-event mean/std (included FUTURE releases) → EXPANDING past-only z-score (`shift(1)` excludes current; <2 history → 0). Verified in isolation (row0-1 = 0, then real, no future).
**Status:** code done, syntax OK, past-only z-score unit-checked. **⚠️ NEEDS RETRAIN + WFO GATE.**
**Gate:** honest baseline ~+80R (W13 corr_imp-out = +80.5R). PASS if Total R ≥ ~+78R (within noise). Big drop ⇒ a fix cut real signal → investigate.
**Bats:** `Run_LeakFix_P1P2P3_Retrain_WFO_TEST.bat` (2-wk smoke) + `_FULL.bat` (53-wk, backup→retrain→WFO).
**REVERT:** each fix has an inline REVERT note; restore model from `_backup_pre_leakfix_p1p2p3_20260712`.

## 2026-07-12 — Full leakage audit (all timeframes) — report only (Imtiyaz)
**What:** Audited every feature path in `features.py` across M15/M30/H1/H4 + swing/OB/news for lookahead. Report: `docs/LEAKAGE_AUDIT_20260712.md`.
**Findings:** Only real leak left = `corr_imp_ratio` (double leak: swing reads 3 future H4 candles + availability gate ~16h early; but LOW profit impact — currently restored/in-model). Minor: `h4/h1_ob_strength` (partial-candle), news `dev_norm` (global-stats). **Verified SAFE:** all M15/M30/H1/H4 ADX/DI/band (drift vs as-of = 0.0000 over 97,632 rows), rolling adx_slope, all ts_* trend-signal features, in_range_phase (honest), OB zones, M15 OHLC.
**Bottom line:** honest ~+80R baseline is trustworthy (no big hidden leak). The old +444R/+384R were inflated by the in_range_phase (pre-07-09) + ADX (pre-07-03) leaks, both now fixed. Raising R must come from genuine signal, not un-fixing leaks.

## 2026-07-11 — in_range_phase LEGACY toggle added (Imtiyaz decision)
**What:** Added env toggle `QGAI_INRANGE_LEGACY=1` in `features.py:get_range_features()`. Default (unset) = honest leak-free behaviour (07-09 fix, only COMPLETED H4 candles). `=1` = old pre-07-09 behaviour (indexes by start-time → includes the current forming H4 candle with its fully-formed future OHLC = lookahead).
**Why:** Investigation of the +444.7R→+80.5R WFO gap proved the dominant cause was NOT the corr_imp_ratio removal but the **07-09 in_range_phase leak-fix**. Partial WFO evidence (same 30 weeks): W1 leaky = +237.8R/316tr vs restore honest = +46.3R/208tr. Imtiyaz wants the +384.5R CTF-OFF Path-A backtest result reproduced, so the old leaky behaviour is now reachable via toggle.
**⚠️ Honesty note:** The +384.5R / +444.7R numbers come partly from lookahead (training/backtest sees the fully-formed future H4 candle). **Live trading cannot reproduce this** — at time t the current H4 candle is only partially formed. Live default stays honest (toggle unset). The toggle is for reproducing old backtest numbers only.
**⚠️ Train/infer parity correction (same day):** inference-only legacy (backtest toggle without a matching retrain) does NOT reproduce +384.5R — the current model was retrained 07-11 23:22 on HONEST in_range_phase, so a leaky-inference backtest feeds it feature values it never trained on (mismatch). Correct reproduction needs leaky TRAINING too. Superseded the inference-only bats with:
- `Run_Legacy_Retrain_CTFOFF_TEST.bat` (backup → legacy retrain → 30d backtest → restore honest)
- `Run_Legacy_Retrain_CTFOFF_FULL.bat` (same, full year, expect ~+384.5R)
Both BACKUP the honest model → retrain with `QGAI_INRANGE_LEGACY=1` → backtest leaky → **RESTORE the honest model** so the LIVE model never keeps the leaky one.
**REVERT:** delete the `QGAI_INRANGE_LEGACY` branch; the honest path is the `else`.

## 2026-07-11 — Master Results Index created (Imtiyaz)
**What:** Created `backtest/results/RESULTS_INDEX.md` — a single reference document listing ALL WFO, backtest, and training results with date, config, total R, trades, feature count, purpose, and verdict (ADOPTED/REJECTED/RETIRED/BASELINE). Also documents the feature-count timeline and pending runs.
**Why:** Too many result folders were causing confusion about which run was which, what config each used, and whether a result is current or retired.

## 2026-07-11 — corr_imp_ratio RESTORED in features.py (Imtiyaz)
**What:** Uncommented `corr_imp_ratio` from `_MANUAL_PRUNE` set — feature is back in model (35 features).
**Why:** Removal on 07-09 was done WITHOUT WFO profit gate (rule violation). WFO dropped from +444.7R → +80.5R (768→391 trades). The feature wasn't truly leaking in a way that hurt OOS — it was genuinely useful for model confidence. Restoring and will re-verify with full WFO.
**Pending:** `Run_Restore_CorrImp_Retrain_WFO.bat` — expect ~+444R recovery.

---

## 2026-07-10 — Dashboard layout overhaul: GridStack.js integration (Anisa)
**What:** Replaced the fragile custom drag/resize/zoom layout system with GridStack.js v12.6.0 — a professional 12-column grid with drag, resize, snap, collision detection, and layout persistence.

**Changes in `engine/dashboard.html`:**
- **GridStack integration:** All 20 panels wrapped in GridStack grid items with proper IDs, min sizes, and tab assignments (LIVE=13, STATS=6, ANALYSIS=1)
- **Edit mode:** ✏️ EDIT button toggles drag/resize; toolbar with Compact, Auto Arrange, Save, Cancel, Reset; ESC key to cancel
- **Tab filtering:** All tabs in one grid, `switchTab()` shows/hides panels via `gs-item-hidden` class
- **Layout persistence:** Save/restore per-tab layouts to localStorage (`quantGoldDashboardLayout_v1`); survives page refresh; debounced auto-save on change
- **Container queries:** `container-type: inline-size` on all panels; semantic font variables with `clamp()` (--font-panel-title, --font-main-value, --font-metric, --font-label, --font-small); `@container` queries for small panels
- **Responsive breakpoints:** 1 column (<768px), 6 columns (768-1199px), 12 columns (>=1200px) via `_gsGrid.column()` on resize
- **Canvas ResizeObserver:** Redraws sparkline/signal charts when panel resizes
- **Performance:** Responsive resize throttled via `requestAnimationFrame`; layout save debounced 300ms
- **Old code neutralized:** Old `fitDashboardText`, `setupPanelResizers`, `setupStitchedColumns` overridden via function hoisting (no-ops); old drag/resize/zoom JS is dead code

**New files:**
- `engine/gridstack-all.js` — GridStack v12.6.0 library (local, ~85KB)
- `engine/gridstack.min.css` — GridStack CSS (~4KB)
- `engine/dashboard_backup_pre_gridstack_20260710_081601.html` — pre-change backup

**No trading logic modified.** All signal/trade/polling/bridge code untouched.

## 2026-07-10 — Dashboard: blocked signal display (Imtiyaz/Anisa)
**What:** When a BUY/SELL signal is blocked by a filter (BLOCK_RANGE, BLOCK_CTF, BLOCK_PULLBACK, BLOCK_SMMA, BLOCK_ADX, BLOCK_SLOT), the dashboard now clearly shows it as blocked instead of showing a bright active signal that could be misread as a live trade.

**Changes:**
- `bridge_main.py`: Pass `trade_action` to every `write_dashboard()` call (MONITOR, BLOCK_SLOT, OPPOSITE_HANDLED, RESUME_SKIP, and computed BLOCK_* from filter chain)
- `bridge_dashboard.py`: Accept `trade_action=""` param in `write_dashboard()`, include in JSON output; `get_signal_history()` now includes `trade_action` from SQLite
- `dashboard.html` — 4 display locations updated:
  1. **SIGNAL hero box**: "SELL BLOCKED" in gray (#555) + dimmed (opacity 0.6) + "⛔ range-phase H4 chop" tag
  2. **AI Decision Summary**: red "⛔ BLOCKED — SELL signal blocked by [filter]" banner above the pill groups
  3. **Signal History chart**: blocked bars drawn with hatched pattern + very low opacity
  4. **Overnight replay / Signal History table**: blocked rows dimmed + strikethrough signal text + BLK RANGE badge

**No trading logic modified.** Only display layer; all block decisions remain in `bridge_main.py`.

## 2026-07-10 — Dashboard: Signal+Lifecycle merge + empty-space fix (Anisa)
**What:** (1) Merged SIGNAL card and TRADE LIFECYCLE into one combined panel ("Signal + Lifecycle"). (2) Fixed 180px empty space above OPEN TRADES caused by hidden conditional panels (danger_banner, sl_progress_wrap) occupying GridStack grid positions even when display:none.

**Changes in `dashboard.html`:**
- Lifecycle HTML moved inside `#panel_signal` after sig-hero-reason; separate `#panel_lifecycle` wrapper removed
- GridStack config: merged into one entry `signal: {title:'Signal + Lifecycle', w:5, h:6}`
- **Empty-space fix:** Removed `danger_banner` and `sl_progress_wrap` from `PANEL_CONFIG` entirely — they're conditional bars, not persistent panels. During GridStack init, they're moved just above the grid as plain DOM elements (shown/hidden via existing CSS `.show` class and `display:none`). This eliminates the 180px gap (3 GridStack rows × 60px) that appeared between Market Intelligence and Open Trades when no trade was open and daily loss was below 70%.

**No trading logic modified.**

---

## 2026-07-09 — Feature leakage fix: prune `corr_imp_ratio` + fix `in_range_phase` H4 lookahead (Imtiyaz)
**Issue:** Imtiyaz flagged `in_range_phase` and `corr_imp_ratio` for leakage risk. Code trace confirmed:
- **`corr_imp_ratio`** (rank #28, importance 0.022): swing detection uses `h4["high"].iloc[i+j]` — explicitly
  reads **3 future H4 bars** (12h+ lookahead). Training sees future-confirmed swings; live sees stale/missing
  swings. AUC test: removing it = −0.014 test AUC (negligible, within noise).
- **`in_range_phase`** (rank #1, importance 0.071): `get_range_features()` used `searchsorted(h4_df['datetime'],
  t, side='right')` which includes the **current incomplete H4 candle** — its close/OHLC includes up to ~3.75h
  of future M15 bars in training. AUC test: removing it = −0.074 test AUC (severe drop — feature is valuable
  but implementation was leaky).
**Fable-5 architectural review** confirmed both leakage paths.
**AUC impact test** (`Start/6_Test_Leakage_AUC.bat`): 4 variants on 2,743 trades:
  A) Baseline (36 feat): val 0.6771, test 0.6752
  B) −corr_imp_ratio:    val 0.6861, test 0.6616 (−0.014)
  C) −both:              val 0.6275, test 0.6085 (−0.067)
  D) −in_range_phase:    val 0.6229, test 0.6014 (−0.074)
**Fix 1 (`features.py` _MANUAL_PRUNE):** `corr_imp_ratio` added to `_MANUAL_PRUNE` → removed from model.
  Also removed from `RANGING_FEATURES` list. Computation functions untouched (harmless).
**Fix 2 (`features.py` get_range_features):** changed `searchsorted(h4_df['datetime'], t)` to
  `searchsorted(h4_df['datetime'] + 4h, t)` — only COMPLETED H4 candles included. The current (incomplete)
  H4 candle is excluded. No more future M15 bars leaking into `in_range_phase` or `is_post_big_move`.
**⚠️ NEEDS RETRAIN + WFO-GATE.** Model now has 35 features (was 36). Expected: AUC may shift slightly due to
honest `in_range_phase` values (no more future peek). `corr_imp_ratio` removal is AUC-neutral.

## 2026-07-09 — SIGNAL box / AI DECISION SUMMARY showing SKIP while SIGNAL LOG shows the real BUY/SELL (Imtiyaz-flagged mismatch)
**Symptom:** SIGNAL box + 🧠 AI DECISION SUMMARY both showed `SKIP`, while the SIGNAL LOG's latest row (same
bar) showed a real `BUY` — yet EV (+1.05R), Risk Grade (A/Excellent), and the AI summary's own model votes
(51.24% win, Trending, 63.16% dir, 74.7% bigwin) all matched the BUY exactly, not the null/`--` a genuine
SKIP requires. Confirmed live (not just the screenshot): `signals_all.csv` last row = `signal=BUY,
trade_action=HOLD_IN_TRADE`; `dashboard.json` at the same moment = `signal_confirmed:false, ev_r:1.05`
(`ev_r` is only ever non-null when the backend's own `sig["signal"]` is BUY/SELL — proof the backend really
decided BUY, the display just hid it).
**Root cause:** `bridge_main.py`'s intra-bar heartbeat write (~every 30s between bar closes, `if verbose:`)
re-sends the SAME already-decided `core._last_signal` dict but hardcoded `signal_confirmed=False` on every
call. Two frontend spots (`dashboard.html` SIGNAL box `_isForming`/`_lastConfirmedSig` logic, and
`renderAISummary()` line ~1556) both treat `signal_confirmed!==true` as "not yet decided, hide the real
BUY/SELL behind SKIP" — a concept meant for a genuinely gate-blocked decision, but actually driven here by
an unrelated "is this write a heartbeat vs a fresh bar" flag. Net effect: any real BUY/SELL was hidden behind
SKIP for the ~15 minutes until the next bar close, any time the page was loaded/refreshed during that window
— even though the SIGNAL LOG (reads `signals_all.csv` directly) always showed the truth.
**Fix (`bridge_main.py:361-364`, one line):** the heartbeat call now passes
`signal_confirmed=bool(core._last_signal.get("signal"))` instead of a hardcoded `False` — true once ANY real
decision (bar-close or the startup pre-pop probe) has populated `core._last_signal`, so the box/AI-summary
stop hiding an already-decided signal. The two genuinely-intentional `signal_confirmed=False` calls (the
`_pre_pop_dashboard` startup probe, before any real bar exists yet) are untouched. `py_compile` clean.
**Scope:** dashboard display only — live trading decisions/execution (`trade_action`, real gates) are
completely unaffected; this never touched what the bot actually trades. **Activation: bridge restart**
(backend Python change, not a browser-only fix this time).

## 2026-07-09 — Add RAW tick volume as a model feature (Imtiyaz)
Request: give the model **raw tick volume** — no formula, ratio, z-score or normalization — and let the
model itself decide if it's useful. **State before:** `f["tick_volume"]` (the closed bar's raw MT5 tick
count) was already COMPUTED in `features.py` (~line 625, else-fallback ~694) but was **not** in
`FEATURE_COLS`, so no model ever saw it. The only volume-derived feature, `"volume"` (a 20-bar normalized
ratio, capped 5.0), has been **pruned** since 2026-06-23 via `_MANUAL_PRUNE` → the live model currently has
**zero** volume input.
**Change (`features.py`, one line + comment):** added **`"tick_volume"`** to `FEATURE_COLS` (FACTOR 4 block,
~line 1183). It is NOT in `_ZERO_IMP`/`_MANUAL_PRUNE`, so it survives the prune. The normalized `"volume"`
stays pruned on purpose — we want ONLY the raw count. `inference.py` imports `FEATURE_COLS` from `features.py`
(line 209) → **train==serve** automatically once retrained. `py_compile` OK; `tick_volume` present in both
the populated branch (625) and the zero-fallback (694) so `df_feat[FEATURE_COLS]` can't KeyError.
**⚠️ NOT LIVE YET — NEEDS A RETRAIN.** The current live `.pkl` has no `tick_volume` column, so the bot would
feature-mismatch until `Start/3_Train_Models.bat` is rerun. Per rules: test-run first, deep bug-check, and
**WFO-gate (≥ current baseline R) before adopting live** — raw volume may add noise; the model deciding it's
useless (importance ≈ 0) is a valid outcome. REVERT: delete the `"tick_volume"` line.

## 2026-07-09 — Option A: SIGNAL box ALWAYS = current bar (backend freeze OFF) (Imtiyaz)
The struck-through/mirror-removal fixes below stopped the box from *inventing* a SELL, but the box could
still lag: `_remember_last_trade_signal()` **froze** the last BUY/SELL and the WHOLE decision block
(ai_summary, votes, prob, `signal_confirmed`) is derived from that frozen `sig` (see `bridge_dashboard.py`
line ~595 comment) → box showed the old 08:15 SELL while the log's newest 08:30 bar was SKIP. Two contexts
disagreed again.
**Fix (`bridge_dashboard.py`, backend — needs a bridge RESTART, no filter/trading logic touched):** added a
reversible module constant **`_FREEZE_LAST_SIGNAL = False`** (line ~35). `_remember_last_trade_signal()` now
returns the **raw current-bar signal** (freeze-mode gated behind the flag). The last-signal cache is still
kept on disk (used elsewhere); only the DISPLAY return switched. Because the entire block derives from `sig`,
ai_summary/votes/prob/`signal_confirmed` all become current-bar → **box === SIGNAL LOG newest row, SKIP shows
SKIP.** `_sig_cached` self-resolves to False (sig == raw). Set the flag `True` to restore the old freeze.
No frontend change needed (the mirror-fallback was already removed). **Action: restart the bridge to apply.**

## 2026-07-09 — PERMANENT fix: SIGNAL box vs SIGNAL LOG never contradict (Imtiyaz, recurring flag)
**Root cause (traced in live log):** the SIGNAL LOG shows the RAW model signal (`signal` column), the SIGNAL
box shows the ACTIONABLE decision after gates. On 08:15 the model call was SELL (win_prob 51.73% > thr 48%)
but `trade_action=BLOCK_RANGE` (Ranging range-filter) → no trade → box correctly = SKIP. Log showed a bare
"SELL" with no block marker → looked like a contradiction. **Not a bug — a display gap.** (See new working
rule "SIGNAL ≠ REAL TRADE" in CLAUDE.md + memory.)
**Two frontend fixes (`dashboard.html` only — no trading/filter logic, no bridge restart, Ctrl+F5):**
1. **Removed the SIGNAL-box "mirror the log's last BUY/SELL" fallback** (added earlier same day). It wrongly
   copied a range-BLOCKED SELL into the box, making a SKIP look like a live SELL — the exact confusion. Box
   now always shows the true gated decision from `d.last_signal`. `_feCached` pinned false.
2. **SIGNAL LOG: blocked directional signals now render struck-through + 🚫** when `trade_action != EXECUTED`
   (BLOCK_*/HOLD_IN_TRADE/MONITOR/EXEC_FAILED/OPPOSITE_HANDLED). The `trade_action` badge already existed;
   this makes the raw-but-not-traded signal unmistakable (a blocked SELL can't be misread as a live SELL).
Result: box = actionable decision, LOG = raw signal (struck-through + tag when not traded), OPEN TRADES = the
only real positions — three distinct layers, clearly labelled. JS syntax verified (vm.Script, 2 blocks OK).

## 2026-07-09 — Dashboard Audit (Ideal vs Current vs Fix) → `docs/DASHBOARD_AUDIT_2026-07-09.md`
Requested standalone audit (Fable-style prompt). Rating **RISKY**. Top risks: (1) leaky feature
`corr_imp_ratio` (Step-2 = Critical, future H4 candles) shown on board as `corr_ratio`; (2) backtest
sizing ≠ live — **confirmed** fixed_lot 0.01 in `step4_monthly_set1_36/backtest_summary_st-htf.csv`
(66 trades, max_dd 0.9%), so $/DD not live-equivalent; (3) WFO "too good" — full run = **53 weeks /
768 trades / +444.7R, pos=51 neg=1** (part2 52/0, hmm 52/0) = leakage signature, while leaky features
still in the set; (4) "STRENGTH" panel implies the ADX6 gate that is OFF + old formula cancelled ADX/slope;
(5) no provenance (git-commit/config-hash/data-range) on any output. **F-10 (new):** the clean-set control
(Set-2, 34-feat = current minus the 2 leaky feats) — the one test that would prove edge-vs-leakage — was
started but left unfinished (`step4_set2_clean_34/` has only 1 train log) → finish it first. Also:
`BY_REGIME` per-regime R exists in the backtest CSV but is not surfaced on any board.
*(Self-correction: an earlier draft cited "~4 trades/wk / max_dd 0.3%" — that was a truncated early-weeks
slice; the numbers above are the full-run reality.)* Full findings + KPI/mismatch/integrity tables +
roadmap in the linked doc. No code changed.

---

## 2026-07-09 — SIGNAL box mirrors the LOG + entry price atop BUY/SELL bars (Imtiyaz req)
Imtiyaz flag: SIGNAL LOG's newest row = SELL, but the big SIGNAL box showed SKIP (box's
State/Direction matched the current SKIP bar → backend freeze/bootstrap not active in the running
bridge). Verified `_bootstrap_last_trade_signal()` DOES find the last BUY/SELL in signals_all.csv
(864 actionable rows; last = 05:30 BUY 4080.41) → backend fix is correct, just needs the bridge
restarted with the new code. Added a **restart-independent frontend safety net** so the box can
never disagree with the log:
- **Frontend** `dashboard.html`:
  - `_parseSig()` now also captures `state_prob` + `dir_prob`; `window._liveSigData` exposed.
  - `update()`: when `d.last_signal` isn't an actionable BUY/SELL, the box falls back to the most
    recent BUY/SELL from `window._liveSigData` — the SAME signals_all.csv the SIGNAL LOG is drawn
    from → box mirrors the log's latest signal. EV/GRADE recomputed from win_prob when backend sends
    null. Shows the dim "🕒 last @ HH:MM" hint. **Ctrl+F5 only, no restart needed.**
  - `drawSigChart()`: entry price now printed **atop each BUY/SELL bar** — horizontal, bold 9px,
    black-outlined for contrast (earlier 7px rotated label was unreadable). Chart height `44→60px`,
    canvas internal height matches CSS for crisp text. SKIP bars unchanged.
- **Backend** `bridge_dashboard.py` → `get_signal_history()`: added `price` to the SELECT + output
  dict (feeds the chart's price labels). **Needs bridge restart.** Display-only, no filter/logic change.

---

## 2026-07-09 — `_gDate is not defined` crash + ADX vs MT5 explained (Imtiyaz flags)

**(1) `_gDate is not defined (line 1947)` — render crash.** The signal box showed no date, missing
WIN PROB/EV/GRADE/State/Direction, AND the Signal History chart was blank — ALL from ONE JS error.
`_gDate()` was defined INSIDE the live-signal-log IIFE (`<script>` at ~652), but the main `update()`
loop in a SEPARATE `<script>` block called it at line ~1947 → ReferenceError → every render step after
that line aborted (date, signal-box fields, `drawSigChart` at ~2438 all downstream). **Fix:** exposed it
globally — `window._gDate=_gDate;` right after the definition (dashboard.html ~673). Frontend-only →
needs a browser hard-refresh (Ctrl+F5), no bridge restart.

**(2) Dashboard ADX ≠ MT5 chart ADX — investigated (flag), NOT a bug.** STRENGTH showed H1 16.5 / H4 34.2
while MT5 read H1 12.92 / H4 28.19. Confirmed the box value = engine's live per-bar ADX (dashboard.json
04:00 bar: H1_ADX 16.49, H4_ADX 34.18 → rounds to 16.5/34.2), not frozen. Root cause = **smoothing method**:
the engine computes ADX with `ewm(span=14)` (alpha≈0.133; `regen_adx_di.compute_adx_tf`,
`mt5_data_updater.compute_adx_tf`, `regen_adx_asof.asof_tf` all identical) — MT5 uses **Wilder** smoothing
(alpha=1/14≈0.071), ~2× slower → engine reads higher in a rising-ADX phase. Secondary: (a) as-of convention
= last-CLOSED H1/H4 bars' EWM state + one step folding the **forming** (partial) bar, updated every M15 bar
(not tick like MT5's right edge); (b) pandas-resample bar boundaries vs MT5 broker-server-time bars; (c) MT5
ships two indicators (ADX vs ADX Wilder). **Live == training** (same `compute_adx_tf`), so the model is
self-consistent; its thresholds (H4>30 trending, <20 ranging) were learned on THIS EWM-ADX. **Decision: keep
as-is (option A)** — switching to Wilder would need a full retrain + backtest≠live re-verify. Added a
clarifying tooltip on the STRENGTH H1/H4 ADX pills (dashboard.html `pill()` gained an optional `tip` arg).
To compare on MT5, use **ADX Wilder, period 14**.

## 2026-07-09 — Decision box: BOOTSTRAP last BUY/SELL on fresh restart (was stuck on SKIP)

**Symptom (Imtiyaz):** after the "freeze box to last BUY/SELL" change + bridge restart, the signal box
still showed **SKIP** with WIN PROB / EV / GRADE / State / Direction all `--` and no date.

**Cause:** `_remember_last_trade_signal()` only cached a BUY/SELL when one arrived *after* restart, and
persisted it to `logs/last_trade_signal.json`. On the FIRST restart that file didn't exist yet, and only
SKIP bars had occurred since → `_LAST_TRADE_SIG` stayed `None` → box kept showing the live SKIP
(`signal_is_cached=False`). It would have self-healed only on the next live BUY/SELL (possibly hours).

**Fix (`bridge_dashboard.py`):** added `_bootstrap_last_trade_signal()` — when no persisted cache exists
on first load, it reads the most recent BUY/SELL row from `signals_all.csv` and seeds `_LAST_TRADE_SIG`.
Numeric columns (`_LTS_NUM_COLS`) are coerced to `float` so the decision block's arithmetic
(`ev_r = wp*tp_m …`, `round(state_prob,4)`) never hits a `str × float` TypeError. The block *computes*
eff_prob / ev_r / risk_grade / market-structure from raw fields (win_prob, state_prob, dir_prob, hmm_state,
atr20_pct …), all present in the CSV, so a CSV row is enough for a coherent box. Verified on the live file:
last BUY `2026-07-09 03:15` 54.44% → ev_r 0.361, GRADE B. Display-only; no filter/trade logic touched.
**Needs a bridge restart to load.**

## 2026-07-09 — Signal ↔ Trade DECOUPLE (Imtiyaz architecture) + new `trade_action` column

**Imtiyaz spec:** System = signal PROVIDER, MT5 = signal RECEIVER. A pure/virtual engine signal
(BUY/SELL/SKIP by threshold — exactly like backtest) must be logged on EVERY bar, regardless of
whether a trade is placed (system or manual) or whether an account is even connected. Signal must
NEVER stop, and trade-execution filters must NOT overwrite it.

**Root problem (verified):** in `bridge_main.py`, 11 trade-execution paths each called
`log_signal(bar_time, "SKIP", …)` — overwriting the engine's real BUY/SELL to "SKIP". This is
exactly why a high-prob (e.g. 78.59%) BUY showed **SKIP** in the log when a position was already
open (single-position HOLD) — backtest≠live in the signal column.

**Fix — two decoupled columns (logging only; NO trade-logic change):**

| Column | Meaning | Values |
|--------|---------|--------|
| `signal` | PURE engine decision — every bar, backtest-identical | BUY / SELL / SKIP |
| `trade_action` (**NEW**) | what the RECEIVER (MT5) did | EXECUTED · EXEC_FAILED · HOLD_IN_TRADE · OPPOSITE_HANDLED · MONITOR · BLOCK_SLOT · BLOCK_RANGE · BLOCK_CTF · BLOCK_PULLBACK · BLOCK_SMMA · BLOCK_ADX · RESUME_SKIP · NO_TRADE |

- `bridge_main.py`: all 11 `log_signal()` sites now pass the **real `signal`** + a `trade_action=`.
  Execute path logs `EXECUTED` if a lot came back else `EXEC_FAILED` (so a no-account / AutoTrading-OFF
  / retcode-10027 failure no longer hides the signal). Control flow / filter blocking logic **unchanged**.
- `bridge_data.py`: `log_signal(..., trade_action="")` new param; new trailing `trade_action` column in
  CSV, `signals_complete.csv`, and SQLite (`ALTER TABLE signals ADD COLUMN trade_action`, one-time).
  `_ensure_signal_columns()` migrates old CSVs (blank for old rows).
- **Test:** `Test_Decouple_Signal.bat` → `engine/test_decouple_signal.py` (offline, TEMP db+csv, live
  files untouched). 10/10 checks PASS incl. the 78.59%→HOLD_IN_TRADE case + old-file migration.

**Dashboard (done same day):** `dashboard.html` SIGNAL LOG (`_parseSig` + `_liveSigRender`) now parses
the new `trade_action` column and shows a colored badge per row (EXECUTED=green · EXEC_FAILED=red ·
HOLD_IN_TRADE=cyan · BLOCK_*=orange · MONITOR=blue · OPPOSITE_HANDLED=purple; NO_TRADE hidden as
redundant on SKIP rows). So a high-prob BUY that MT5 held now reads `BUY … HOLD_IN_TRADE`, not SKIP.

**Remaining:** restart bridge + dashboard server to activate (new column populates on next bar).

---

## 2026-07-09 — SIGNAL LOG: virtual entry→exit→move on EVERY BUY/SELL (Imtiyaz)

**Imtiyaz spec:** in the SIGNAL LOG, every BUY/SELL must show its price move — e.g. `buy 4076 → exit
4100 = +$24` — **whether or not a real trade was placed** (system = signal provider, like backtest).
Exit-price calc "seemed to be missing" → make it visible + complete.

**Root cause (verified — nothing was actually broken in the engine):** the exit-price calc already
exists — `shadow_ledger.py` paper-trades EVERY BUY/SELL signal from `signals_all.csv` with the live
exit rules (HTF-H1 stop + flip, ratchet buffer, far TP) and writes `logs/shadow_trades.csv`
(entry_price, exit_price, exit_reason, R, pnl). Scheduler refreshes it every 15 min (`scheduler.py`
`shadow_ledger.py`, 821 signals: 42 real + 779 paper). What was missing was **display**: the old
badge (a) only showed for non-real signals (real rows used the `move` col, which is blank on older
rows → "WIN" with no price → looked like "no exit calc"), and (b) never showed the entry→exit prices
inline, only the move number.

**Fix (dashboard-only — NO engine / data-path / trade-logic change):** `dashboard.html`
`_liveSigRender()` rewritten so that:
- **Every BUY/SELL row** now renders the SIGNAL's virtual result inline from the shadow ledger:
  `4076.00→4100.00  +$24.00  +2.5R  TPᵛ` (green profit / red loss, dashed border, ᵛ = virtual).
  Shown whether or not a real trade was placed (matches the provider/backtest spec).
- If a **real trade also closed** on that bar, an extra solid `WIN/LOSS +$move REAL` chip is appended
  (real account result kept SEPARATE from the virtual signal result — no contradiction).
- Tooltip gives full detail (entry, exit, move, R, exit reason, real-vs-paper, account outcome).

No new CSV columns, no bridge change. **Activation: just hard-refresh the dashboard browser**
(shadow_trades.csv is already produced by the scheduler). Very recent BUY/SELL show the badge once the
trade exits + next shadow refresh (≤15 min) — same as backtest (exit unknown until it happens).

---

## 2026-07-09 — Decision area shows the LAST BUY/SELL signal (not a SKIP bar) + SKIP win% dim

**Imtiyaz spec:** the signal box must show the **last placed signal** (last BUY/SELL) with ALL its
params, and the **AI DECISION SUMMARY** + **MARKET INTELLIGENCE** boxes above must show data for that
SAME signal — a plain SKIP bar should not overwrite/blank the decision area.

**Fix (backend `bridge_dashboard.py` — display only, NO trade-logic change):** the whole decision
block (hmm/state/dir prob, `market_structure`, `eff_prob`, `ev_r`, `risk_grade`, `ai_summary`,
`market_intel`, win/big-win/duration inside `sig`) is all derived from one `sig` dict. Added a
last-actionable-signal cache — `_remember_last_trade_signal()` — that returns the most recent BUY/SELL
signal (persisted to `logs/last_trade_signal.json`, survives restart). `write_dashboard()` now freezes
`sig` to that at line ~508, so the entire block stays coherent on the last real signal. **Live price /
spread / session / open-trades / countdown come from `tick` (not `sig`) → they stay live.** When a
cached (past) signal is shown, `signal_confirmed` is forced True (renders directly, not "forming") and
a new `signal_is_cached` flag is sent.
- `dashboard.html`: the `sig_confirmed_tag` span now shows a dim **🕒 last @ HH:MM** hint (the signal's
  own bar time) whenever `signal_is_cached` — so a frozen past signal isn't mistaken for the live bar.

**Also (same day) — SIGNAL LOG win% colour:** on a **SKIP** row the win_prob no longer shows gold; it
stays dim like the SKIP text. Gold only for an actual BUY/SELL ≥45%. (`dashboard.html` `_liveSigRender`.)

**Also (same day) — date format + signal-box date/time:** new `_gDate()` helper →
`2026-07-09 23:15` renders as **`9 Jul 26 23:15`** (day + 3-char English month + 2-digit year). Applied to
(a) the SIGNAL LOG time column (was `MM-DD HH:MM`), and (b) the SIGNAL BOX — which previously showed
NO date/time (the old `signal_bar_time` element didn't exist); added a `signal_datetime` span in the
card header showing the signal's full date+time. (`dashboard.html`, frontend — browser refresh only.)

**Activation:** signal-box/AI/intel change is BACKEND → needs a **bridge restart**. The SKIP-colour +
virtual-move badges are frontend → just a browser hard-refresh.

---

## 2026-07-08 — Deep bug check + FORMING/CONFIRMED signal fix

**7 bugs found and fixed across 3 files:**

| # | File | Severity | Bug | Fix |
|---|------|----------|-----|-----|
| 1 | dashboard.html | CRITICAL | `_isConf` TDZ error — AI Decision Summary never rendered (silently swallowed by try/catch) | Moved `const _isConf` declaration before first use |
| 2 | bridge_main.py | CRITICAL | `import sys` missing — `sys.exit(1)` in news-stale guard throws NameError, bridge continues with stale calendar | Added `import sys` |
| 3 | bridge_main.py | MODERATE | SMMA/ADX block SKIP double-logged — guard at line 681 didn't check `_smma_block`/`_adx_block` | Added both to the elif guard |
| 4 | backtest_replay.py | CRITICAL | EOD-closed trades missing from `trades_out` — equity changed but trade invisible in CSV | Added full record dict + append for EOD trades |
| 5 | backtest_replay.py | CRITICAL (latent) | `sl_dist` undefined when `--ratchet off` → NameError on first trade | Added fallback `sl_dist` for non-ratchet mode |
| 6 | backtest_replay.py | MODERATE | REVERSAL trade records always had None for win_prob/hmm_state — accessed `_tr.win_prob` instead of `_tr.sig.get("win_prob")` | Fixed to `_tr.sig.get(...)` |
| 7 | backtest_replay.py | MODERATE | NaN ADX bars reset death streak to 0 instead of leaving unchanged | Changed init to -1, skip streak update on -1 |

**FORMING/CONFIRMED signal fix (Imtiyaz request):**
- Dashboard now suppresses forming-bar BUY/SELL — shows SKIP until bar-close confirmed
- AI Decision Summary also suppressed — ✅/⏳ icon on SIGNAL pill
- Both main signal card and summary card stay consistent

---

## 2026-07-08 — ADX-death exit rule (Imtiyaz idea + Fable-5 design)

**Insight (Imtiyaz):** ADX slope falling across TFs during hold = trend dying = give-back coming.
Data: 0 TFs falling = +1.34R avg, 4 falling = −0.23R avg. Strongest exit signal found this session.

**Rule (Fable-5 design):** At each M15 bar close: if K≥3 of 4 TF ADX slopes ≤0 for N≥3 consecutive
bars AND unrealized profit ≥0.5R → exit at bar close, reason `ADX_DEATH`.
Slopes: M15=diff(1), M30=diff(2), H1=diff(4), H4=diff(16).

**Changes:**
- `engine/config.py`: FilterConfig + `adx_death_enabled=False, _k=3, _n=3, _min_r=0.5`
- `engine/backtest_replay.py`: precompute 4-TF ADX slope arrays from ohlc before bar loop;
  in trade mgmt loop after ratchet_bar, track per-trade death-streak + exit check
- Env overrides: `QGAI_ADX_DEATH=1`, `QGAI_ADX_DEATH_K`, `_N`, `_MIN_R`
- Default **OFF** → live unchanged until sweep + WFO validation

**Test bats:**
- `backtest/_runners/Run_ADXDeath_TEST.bat` — 2-week smoke test
- `backtest/_runners/Run_ADXDeath_Sweep.bat` — 18-cell K{2,3}×N{2,3,4}×X{0.3,0.5,1.0} + baseline

**Gate:** WFO ≥+444.7R AND Trending R not down AND avg-winner-R down <5% AND median R-saved >0

---

## 2026-07-07 — FIX-3 parity (Fable-5 #1): reversal-close modeled in backtest
Worked on by Claude via Cowork (Imtiyaz). Fable-5 ranked this #1 ("stop adding gains you can't collect").

**Gap:** live `bridge_core.handle_opposite_signal` closes an open trade EARLY on an opposite
signal (in LOSS → exit if new_prob≥0.45; in PROFIT → exit if new_prob≥0.60) and re-enters.
The backtest NEVER modeled this → a major source of the ~12% live-vs-backtest entry overlap
(live cuts trades the backtest holds to SL/TP/flip). (The forming-H1-bar gap turned out already
handled — `backtest_replay.py:356-362` added forming parity 2026-06-30.)

**Fix:** `backtest_replay.py` — after the signal is picked, if an open trade is OPPOSITE and the
live exit thresholds are met, close it (`exit_reason="REVERSAL"`) and let the new entry proceed.
Flag-gated `QGAI_BT_REVERSAL=1` (default OFF → +444.7R baseline unchanged). Smoke (30-day):
18→79 trades, 11 REVERSAL exits fired, no crash.

**RESULT (2026-07-08, Fable-5 re-read):** Reversal-close is NOT the main gap. Reconcile over the
live period (2026-06-09→07-07) vs shadow: overlap 13.6%→15.2% (+1.6pp only). Full-year reversal ON
= 903 tr / WR 62%→50% / +406.6R = low-quality re-entry churn → keep OFF. **The "12% overlap" is
dominantly a SHADOW-ENGINE ARTIFACT, not live≠backtest:** `shadow_ledger.py` enforces NO max_open
(sims all 143 signals in parallel) while backtest+live hold 1 position. Verified: shadow's 154
entries collapse to 44 under a 1-position lock (vs backtest 66) — the entry gap is blocked-signal
artifact + exit-hold-time, not missed trades. On matched trades backtest books 0.6R LESS than
shadow → **if +444.7R is biased it's PESSIMISTIC, not optimistic.** **FIX-3 REDEFINED:** drop the
shadow-overlap metric (confounded); the real task = `backtest_replay` ↔ `bridge_core` (live truth)
**exit/trail/flip/TP parity via code diff**. Entry-count + exit-mix + matched-R gaps are all
downstream of the trail logic. Keep demo running as the final entry-side arbiter. `adx_fs_div` etc.
Reversal flag stays wired (OFF) for reference.

**⚠️ Caught during this work:** the PART-2 `Run_Part2_ADXComposite_FULL.bat` retrains composite
models INTO `data/models/final` — after the (rejected) PART-2 WFO it left composite-31 models on
disk (ts 20260708_0000). Restored validated raw-36 from `_backup_part1_raw35`. Live bot memory was
still raw-36 (safe); the restore makes the next restart safe too. **RESOLUTION: both PART-2 bats
DELETED (`Run_Part2_ADXComposite_TEST/FULL.bat`) so the composite model can never be accidentally
retrained into the live folder again.** The composite feature code + `QGAI_ADX_MODE` toggle stay
dormant in `features.py` (default raw, harmless — like the other parked gates). To restore raw-36
if ever needed: `xcopy /E /I /Y "C:\QGAI\data\models\_backup_part1_raw35" "C:\QGAI\data\models\final"`.

---

## 2026-07-07 — Dashboard upgrade + tooling (Fable-5 dashboard review)
Worked on by Claude via Cowork (Imtiyaz).

**Dashboard (`engine/dashboard.html` + `engine/bridge_dashboard.py`):**
- **Config badges** (System Settings card): CTF Fade / Range Skip / DD Brake / Reversal Gate /
  ADX Mode — color-coded ON/OFF, live from config.
- **🛡️ Account Health & Risk State card** (Fable-5 #1/#2): per-account rows (PRIMARY/MIRROR ·
  balance · DD% · brake-scale · last-order FILLED/REJECTED) with red-highlight on a mirror reject
  while primary filled (would have caught the DD-brake silent-reject bug in one trade); full-width
  **DD-BRAKE HALT banner**; open-trade **$ at risk** (vSL distance × lot); **daily-SL headroom**
  ($used/$limit, color-escalating). Data via new `bridge_multi.ACCOUNT_HEALTH` tracker
  (`get_account_health()`) recorded at connect/order/skip. All render wrapped in try/catch +
  null-guards (JS-crash history); node-validated.
- **Deferred (Fable-5 #3, investor-prereq):** sim/live visual split + DEMO watermark + `n=` labels.

**Signal log:** `signals_complete.csv` was stale at 2026-07-03 (dashboard SIGNAL LOG stuck at
~25k). Rebuilt via `build_signal_log.py` → 97,908 bars through 2026-07-07. New one-click
`backtest/_runners/Rebuild_SignalLog.bat` (uses the correct Python312, not the uv python).

**Master launcher:** `Start/0_START_ALL.bat` — one-click cold-start: data update → chart refresh →
shadow ledger → signal-log rebuild → bridge (own minimized window) → dashboard server :8000 (own
minimized window) → open browser. So every dashboard tab has fresh data on launch. **Training is
deliberately EXCLUDED** (stays manual `3_Train_Models.bat`) — auto-retrain on startup is exactly
what caused today's model mismatch; training must stay a conscious, WFO-gated decision.

**Config-print (`bridge_main.py`):** RUNNING CONFIG now prints ENTRY GATES (range/CTF/reversal) +
DD BRAKE + vSL-persist state on every restart for verification.

---

## 2026-07-07 — Feature PART 1: drop 6 dead EA-threshold-combo features (needs retrain)
Worked on by Claude via Cowork (Imtiyaz). Fable-5 feature audit.

**Context:** `data/models/final/feature_importance.csv` shows 6 features at EXACTLY 0.0000
importance — all hand-crafted EA-threshold combos of raw ADX/DI features the tree already
has (XGB rebuilds the interactions). Fable-5: "DROP NOW, high confidence." Prior turn's data
also confirmed every EA-threshold ADX feature (19/20/25/30 cutoffs) is dead — the model uses
raw continuous ADX/DI (M15_DI_diff #5, M15_ADX #6, H4_DI_diff #10 are top levers) not the EA
cutoffs.

**Dropped (added to `features.py::_MANUAL_PRUNE`):** `adx_trend_count`, `h4_trending_h1_aligned`,
`h4_ranging_h1_neutral`, `h4_h1_regime_score`, `h4_in_ob_zone`, `trade_direction`.
Main model 41 → **35 features** (+ hmm_state = 36). Hybrid: Ranging 28, Trending 24, Volatile 16.

**Validation: ✅ ADOPTED 2026-07-07.** Retrained on 35-feat, WFO over live period (53 weeks):
**Total R = +444.7R vs +393.7R honest baseline = +51.0R (+13%)**, 51/53 positive weeks
(1 negative), avg +8.39R/week, 768 trades. The dead features were adding overfit noise, not
just neutral weight — dropping them IMPROVED OOS R materially. Result: `wfo_part1_prune35`.
Backup at `data/models/_backup_pre_part1_prune`. Live now 35-feat (bridge restart to load).

**Feature reference:** full per-feature importance + redundancy analysis (what each feature does,
tier ranking, which are dead) → `docs/FEATURE_DETAILS_2026-07-07.md`.

**PART 2 (❌ REJECTED 2026-07-07):** ONE-shot ADX consolidation — 10 raw ADX/DI → 5 tanh composites
(`adx_dir_fast/slow`, `adx_str_fast/slow`, `adx_fs_div`), env `QGAI_ADX_MODE=composite`, model 35→30.
TEST passed (AUC 0.677→0.705, all 5 composites alive). **FULL WFO = +405.6R vs +444.7R baseline =
−39R (−8.8%), 52/53 positive weeks.** Higher AUC but LOWER total R — accuracy ≠ profit; the raw
per-TF ADX/DI features carry information the 5 composites lose. Fable P(beats)≈30% was correct.
**DECISION: keep PART-1 raw-36 (validated, live). Never set `QGAI_ADX_MODE=composite`.** Composite
model discarded; live already on raw-36. Bats kept for the record. Lesson: a cleaner/simpler
feature set with higher AUC can still lose R — always WFO-gate on total R, not AUC.

---

## 2026-07-07 — FAB audit batch 2: S-1, S-3, H6, H8, H9, M11, M12, M14 fixed
Worked on by Claude via Cowork (Imtiyaz). Fable-5 system audit follow-through.
Each finding re-verified against code before change (S-2 was a false positive → all verified first).

- **FAB-M11 (picker, prime-directive):** `bridge_main.py` + `backtest_replay.py` picker now
  prefers any actionable BUY/SELL over a higher-`win_prob` SKIP (was: blind max(win_prob) →
  a tradable signal could be silently dropped when the other side's SKIP had higher prob).
  Mirrored in backtest for parity. Behavior-neutral on smoke week (rare edge case).

- **FAB-H8 (checkpoint resume):** `_resume_sig` now folds `sorted(QGAI_* env)` + model `.pkl`
  mtimes. Changing an env toggle or retraining → signature mismatch → fresh run (kills the
  WFO-cache class bug, BUG_LOG #H ghost).

- **FAB-H9 (ADX gate live wire):** `adx_strength_soft_block` + combined SMMA+ADX penalty cap
  (≤0.08, required ≤0.60) wired into `bridge_main` dormant (default OFF) so live==backtest if
  `adx_strength_soft`/`QGAI_ADX_STRENGTH` is ever enabled. Init `_sm={'penalty':0.0}` guards
  the SMMA-off path.

- **FAB-H6 (replay ADX lookahead):** `get_live_adx()` now truncates history to bars
  at-or-before `bar_dt` (true as-of) instead of always computing today's latest and merely
  labeling the row. Overnight replay passes `bar_dt` per bar → BACKFILL/shadow rows no longer
  lookahead-tainted. Live loop bar_dt≈now → no-op.

- **FAB-S3 (live DD brake):** NEW `engine/dd_brake.py` — persists peak equity
  (`logs/dd_peak.json`), `risk_scale(equity)` returns {1.0,0.5,0.25,0.0} by drawdown band
  (dd>10%→½, >20%→¼, >30%→halt). Wired into `bridge_risk.calc_lot` (scales raw lot); 0-lot
  halt band → `bridge_core.execute` skips new entry. Protective only → prime-directive safe.
  **2026-07-07: `enable_live_dd_brake` set True (Imtiyaz) — ON for real capital.**
  **⚠️ BUGFIX same day (live-caught):** first version used ONE global peak → the bridge's
  mirror SECONDARY accounts ($2k/$10k) were compared against the PRIMARY's $1.1M peak →
  99% false-drawdown → risk ×0.0 → secondary orders rejected (10014). Fixed to PER-ACCOUNT:
  peak keyed by `mt5.account_info().login`, so each account tracks its own peak (old flat
  schema auto-migrates). Verified: primary/cent/onefunded all ×1.0 at their own equity;
  primary −15% → ×0.5. **Needs bridge restart to load (running bot has old global-peak code).**

- **FAB-S1 (reversal filter bypass):** `handle_opposite_signal` reversal RE-ENTRY historically
  called `execute()` directly, bypassing every entry filter. New config `gate_reversal_entries`
  (default **OFF** = legacy behavior). When True: closes the losing side, returns False → the
  main loop re-evaluates the same bar's signal through the full filter stack and opens only if
  it passes. Enable after a backtest that also models close-on-opposite (parity TODO, tracked
  in FILTERS_MASTER §PARITY GAPS #2).

- **FAB-M14 (config re-enable trap):** SMMA gate comment rewritten to "🔴 PROVEN HARMFUL, DO
  NOT FLIP" (was "flip to True after DEMO"). Dead session keys (`use_time_filter`,
  `enable_ny_session`, `enable_morning_session`, `window1/2_*`) verified 0 readers → marked
  ⚰️ DEAD and flipped to False (no behavior change).

- **FAB-M12 (parity-gap doc):** 7-gap table written to `docs/FILTERS_MASTER.md §PARITY GAPS`
  with per-gap status. NOTE: `manual_risk_pct=6.0` (lines 106/110) vs 3.0 (255) is **INTENTIONAL
  design** (Imtiyaz) — a manual trade open by the user caps at 6%. Claude briefly "fixed" it to
  3.0 then REVERTED on owner correction. Do NOT unify. Lesson: confirm before changing any
  risk/trading setting.

**Deferred (with reason, tracked in TASKS.md):** S-5 (forming-bar — profit tradeoff, needs
forming-replay backtest, don't silently flip Anisa's setting), H-7 (backtest daily-SL
mark-to-market — would shift the +350.2R baseline, flag-gate first), M-10 (HMM hysteresis —
stateful behavior change, needs backtest before live), L-15 (is_dead_hour — retrain cycle),
L-16 (backtest exit spread — would shift baseline).

**Verification:** AST syntax OK on all 9 touched files; `dd_brake`/`vsl_persist`/`news_updater`
round-trip tested; full backtest smoke (1 week) = +11.1R, no crash. Live changes effective on
next bridge restart.

---

## 2026-07-07 — FAB-S2: News calendar false-positive + defensive staleness check installed
Worked on by Claude via Cowork (Imtiyaz). Fable-5 audit claim reviewed on real file.

**Fable-5 claim:** `news_all_2024_to_now_pure_cleaned.csv` last event 2026-05-15;
`is_pre_news`/`is_post_news` always 0; bot silently trading NFP/CPI at Volatile 0.42.

**Reality check (2026-07-07):** file has **33,134 events, earliest 2024-01-01, latest
2026-12-05**. Last 30 days: 628 low + 306 med + **65 high-impact** events (including
CPI 2026-12-05, Core CPI, 10-Year Note Auction). Calendar is NOT stale.

**Root of the false positive:** Claude previously showed Fable `tail -3` of the file
which happened to land on 2026-05-15 CFTC rows (alphabetically-sorted within same date
chunk). Fable took this as "last event" — actually the file continues 5 months into
future.

**Defensive check installed anyway** (real risk if file *does* age out):
1. **NEW `engine/news_updater.py`** — `check_staleness(max_days=N)` returns snapshot
   `{last_event, next_event, days_old, stale, reason}`. `refresh(force)` tries
   `investpy`; falls back to manual instructions if lib missing.
2. **`bridge_main.py` startup assertion** — after news load, runs staleness check.
   If stale: ERROR banner with last/next/days_old + fix instructions. If
   `pause_if_news_stale=True` (default False): `sys.exit(1)` to refuse startup.
3. **Config keys added** (`config.py::FilterConfig`): `news_max_stale_days=7`,
   `pause_if_news_stale=False`.

**Test:** `check_staleness()` returns `stale=False, last=2026-12-05 21:00, next=
2026-08-01 00:10, age=0.0d`. Startup log will print `News calendar OK ...` on
next restart. AST syntax check on all touched files: OK.

**Files:** `engine/news_updater.py` (NEW), `engine/bridge_main.py` (startup check),
`engine/config.py` (2 new keys). Live change effective on next bridge restart.

**Meta lesson:** shared summaries with Fable — quote a `head` + `tail` + full-file
`wc -l` at minimum. `tail -3` alone can mislead when the CSV is sorted by day+
event-name (multiple events share a timestamp).

---

## 2026-07-07 — FAB-S4: vSL persistence + broker-SL tighten (Fable-5 audit fix)
Worked on by Claude via Cowork (Imtiyaz). Fable-5 audit finding.

**Bug:** On bridge restart, `bridge_core.recover_open_trades()` (formerly line 626-637) tried
to read `VSL=`/`SL=` regex tags from the position comment. Comment format is now
`QuantEdge AI | {phase}` (line 225) — has no tags. **Every restart fell to the broker-SL
fallback** which reconstructed vSL from `broker_sl / 3.0` = entry-level vSL. Any trailed
gain was silently forfeited. If `pos.sl==0`, an invented `sl_dist=15.0` was used, giving
random risk. Also, disaster broker SL was 3× vSL_dist = ~9% account risk if the bridge
died mid-trade — larger than the 9% daily-SL halt.

**Fix:**
1. **New module `engine/vsl_persist.py`** — JSON round-trip of per-ticket vSL state at
   `logs/vsl_state.json` (atomic tmp+rename write). Schema: `virtual_sl`, `sl_dist`,
   `direction`, `entry`, `breakeven`, `trailing`, `updated` (ISO8601 UTC).
2. **`bridge_risk.py::VirtualTrade.check_ratchet()`** — persist after every trail update
   (line ~110). Import guarded with `try/except ImportError`.
3. **`bridge_core.py::execute()`** — persist immediately on trade open (line ~276) so
   a crash-right-after-open keeps entry-level vSL, not the fallback.
4. **`bridge_core.py::_partial_close()`** — persist after partial + BE flag update.
5. **`bridge_core.py::recover_open_trades()`** — priority: (1) persist file (has TRAILED
   vSL) → (2) legacy VSL=/SL= regex → (3) broker-SL fallback (WARNING now). Also
   restores `breakeven`/`trailing` flags so ratchet doesn't reset them.
6. **`bridge_core.py::__init__` + `_forget_ticket(ticket)`** — new helper that dels from
   in-memory dict AND removes from persist file. All 6 `del self.virtual_trades[...]`
   sites converted to `self._forget_ticket(...)`. Idempotent.
7. **Stale prune** at end of `recover_open_trades()`: drop persist entries for tickets
   the broker no longer holds (closed while bridge was down).
8. **Broker SL tightened `3.0 → 1.5×`** (`bridge_core.py:215/221` + last-resort
   reconstruction divisor). Fable-5 recommendation. Halves disaster-crash risk.

**Test:** `vsl_persist` round-trip save/get/remove verified. AST-syntax check on all
touched files passes. **Live change effective on next bridge restart** — existing open
positions will follow the legacy fallback until they close; new opens are persisted.

**Files:** `engine/vsl_persist.py` (NEW), `engine/bridge_risk.py`, `engine/bridge_core.py`
(6 del-sites converted, execute/partial/recover updated, broker-SL divisor changed 2x).

**Rollback:** Delete `engine/vsl_persist.py` + revert bridge_core / bridge_risk. The
`try/except ImportError` guards mean the system still works if `vsl_persist.py` is missing
(falls back to legacy regex + broker-SL reconstruction — the pre-fix behavior).

---

## 2026-07-07 — LIVE CONFIG CHANGE: Counter-trend-fade DISABLED (Path-A +34.3R proven)
Worked on by Claude via Cowork (Imtiyaz). Independent Fable-5 audit.

**Change:** `config.py:74` `skip_counter_trend_fade: True → False`.

**Why:** Path-A live-parity full-year backtest (2025-06-29 → 2026-06-29, `backtest_replay.py`):
- Baseline (CTF ON): 644 tr / +350.2R / WR 62.3% / PF 3.23 / DD 0.9%
- CTF OFF: **673 tr / +384.5R / WR 62.7% / PF 3.43 / DD 1.1%** = **+34.3R (+9.8%)**

**Root cause (Fable-5):** CTF was a pure EA rule with zero ML input — blocking trades against
the dominant TF (H1/H4 higher-ADX) when that ADX slope was falling. Prior blocked-trade audit
established that alignment ANTI-correlates with profit: 0/3 SMMA-aligned = WR 77% (best),
3/3 aligned = WR 60% (worst). CTF was cutting exactly the 77%-WR counter-aligned cohort that
IS this pullback/mean-reversion-flavored system's edge. 29 extra trades taken, mostly winners
(WR +0.4pp on more trades). DD +0.2% is acceptable.

**Reversible:** set `skip_counter_trend_fade=True` OR env `QGAI_CTF_FADE=1`. Backtest can
force via `--ctf-fade` or the env flag. Bridge restart required to load new config.

**Files:** `engine/config.py:74`, `docs/FILTERS_MASTER.md` (#4 status + change-log row).

**Fable-5 predicted range:** +5 to +25R. Actual +34.3R exceeded upper bound — CTF was cutting
more edge than estimated.

---

## 2026-07-03 — ET1: trend-following PULLBACK entry (fix late "buy-the-top") — flag-gated, sweep-ready
Worked on by Claude via Cowork (Imtiyaz). Design → `docs/ENTRY_TIMING_REDESIGN.md`. Independent Fable-5 review.

**Problem (Imtiyaz flagged):** entry is 100% ML `win_prob`-gated (`inference.py:733`). On the 02-03 Jul gold
rally (`signals_all.csv`) HTF ADX/DI aligned bullish for hours (H4 DI_diff +24) while `dir_prob` stayed
~0.32 → all SKIP; only the 04:00 breakout candle (+29 pts, 4147→4176) flipped `dir_prob` to 0.625 → BUY
fired at 4176, top at 04:15 = 4187. `dir_prob` is a **coincident/breakout-confirming** signal → buys the top.
(Confirmed owner saw it in the signal-log/dashboard, NOT a live trade — those rows were BACKFILL, bot offline
overnight.) Threshold/filter tuning can't fix a lagging trigger → structural fix.

**Fix (structural, ATR-free) — split DIRECTION from TIMING.** New shared gate `trend_pullback_block(sig,cfg)`
in `inference.py` (used by BOTH live `bridge_main.py` AND `backtest_replay.py` → parity by construction):
DIRECTION = HTF `ts_adx_switch_trend` matches trade + `ts_htf_agreement` ≥ min + ADX rising (`h1/h4_adx_slope`);
TIMING/anti-chase = `ts_line_dist_pct` (signed % of price from the active ratchet line — ALL already-computed
features, no new indicators; ATR stays removed since 2026-06-19). Block if not reclaimed (sdist<0), if chased
(sdist>chase_max), or established-trend-not-pulled-back (sdist>pb_near unless `ts_flip_recent`). ML kept as a
future quality-veto (Sweep B); Sweep A is deterministic, ML-veto OFF, runaway OFF. Ground-truth correction:
`band_rel` is a band-WIDTH/vol ratio (`regen_adx_asof.py:107`), NOT price-to-line distance — so `ts_line_dist_pct`
is used, not band_rel.

**Files:** `config.py` (FilterConfig: `trend_pullback_entry`=False master flag + `pb_near_pct`/`chase_max_pct`/
`htf_agreement_min`; env overrides `QGAI_PB_ENTRY/NEAR/CHASE/AGREE`), `inference.py` (gate fn + `ts_*` exposed in
result dict), `bridge_main.py` (live `_pb_block` wired after ctf), `backtest_replay.py` (same gate + `blocked_by=pullback`
+ `ts_*` in signals CSV), `run_wfo.py` (`--sweep-pb-entry` → `do_pb_entry_sweep`: baseline + 18 combos, one weekly
retrain shared, exit fixed live-faithful htf+regime, ranked `PBSWEEP_SUMMARY.csv` with vs_baseline + WINNER/REJECT
verdict). Bats: `backtest/Run_PBEntrySweep_AsOf_TEST.bat` (--weeks 2) + `_FULL.bat` (full year), as-of leak-free workdir.

**DEFAULT OFF → live behaviour unchanged.** Smoke test (1 wk direct backtest): flag-OFF baseline = unchanged path
(13 tr/+41.55%); flag-ON default = gate active (89 signals blocked, 4 tr/+9.31% — default params too tight in that
window, expected; the sweep decides). Compile-clean, `_pb_combos()` = baseline+18 verified. **ACCEPTANCE:** adopt the
combo with highest total R that BEATS baseline; if none, REJECT. PENDING: run TEST bat → FULL sweep → (Sweep B: ML
re-train veto + runaway) → DEMO → live. Reversible: `trend_pullback_entry=False`.

**OUTCOME (same day) — PARKED, baseline kept.** Sweep-A TEST (2 wk, as-of) ran clean (plumbing verified: 19 combos
ranked, verdict + `PBSWEEPT_SUMMARY.csv`). Result: **NO combo beat baseline** — baseline +12.8R/14tr vs best pullback
+7.7R (a1_n*_c030) /5-7tr; total R fell monotonically as the gate tightened (c030>c025>c020, a1≥a3), i.e. the block
cut *winners* in that window. Structural takeaway: a block-only filter can only REMOVE trades, never re-time them —
it can help only when the blocked trades are net-negative (that window they weren't). Imtiyaz chose to **keep baseline**;
FULL-year sweep NOT run. Live unchanged (`trend_pullback_entry` stays False, gate dormant). Code kept for a future
revisit (run `_FULL.bat`, or redesign to GENERATE pullback entries rather than block).

**v2 GENERATE mode (same day) — the real fix, built + promising.** Per the block-only limitation above (a filter can
only REMOVE trades, never re-time them), Imtiyaz chose to build the GENERATE version: **create an early entry** in the
dominant HTF trend direction when the ML SKIPs but price pulls back to the ratchet line — so we enter EARLY on the dip
instead of at the late ML top-signal. Refactored the pullback logic into a shared `_pullback_ok(sig,d,cfg)` (single
source of truth) used by BOTH `trend_pullback_block()` (v1) and new `trend_pullback_generate(sig,cfg)` (v2, returns
BUY/SELL to enter from `ts_adx_switch_trend` dominant direction). Wired into `bridge_main.py` + `backtest_replay.py`
right after the ML signal is picked: if signal==SKIP and generate fires → override to that entry (parity). Config
`trend_pullback_generate`=False / env `QGAI_PB_GEN`; `run_wfo.py --sweep-pb-gen` (mode="gen", reuses the harness);
bats `Run_PBGenSweep_AsOf_TEST/_FULL.bat`. Compile-clean; unit test of the gate correct (pullback→BUY, extended/top→None,
no-trend→None, off→None). **Smoke test (1 wk, window where baseline=+41.55%/13tr): GENERATE = +48.48%/11tr → BEATS
baseline** (opposite of v1 block which lost). Not a verdict (1 wk) — run the `--sweep-pb-gen` TEST then FULL to confirm
on total R over the year. DEFAULT OFF → live still baseline. Reversible: `trend_pullback_generate=False`.

**Fable-5 review of v2 (endorsed GENERATE as the correct pivot) + actions:** (1) Flaw to close — if a GEN entry
stops out mid-leg the late ML entry can still fire at the top (whipsaw + top-chase); fix = per-LEG lock (suppress ML
entry in that direction until the HTF trend flips), TODO after the first sweep shows promise. (2) Leakage watch — the
GEN trigger depends on `win_prob<threshold` i.e. the weekly retrain; the as-of leak-free WFO (per-week cutoff,
next-bar-open fill, last-closed ts_*) already handles this — spot-verify. (3) "Loosest combo won" is a luck flag
(likely just more exposure) → ADDED `worst_wk_r` (worst weekly fold) + `avg_r_trade` + a "MOST ROBUST" line to the
sweep summary/CSV; accept only a combo that beats baseline on total R AND holds worst-week + R/trade. (4) Choppy-regime
guard — the existing range-veto (`in_range_phase`) already gates GEN; an ADX floor is an easy add if the sweep shows
chop losses. Summary enhancement compiled clean.

**backtest_replay.py — ETA/timing added (house rule) + $10k/0.01-lot full-BT bats (2026-07-03).** Per the "every
long run prints timing" rule, the per-100-bar progress line now also shows elapsed min, est. min remaining, and finish
ETA HH:MM; and the report ends with `⏱ DONE — run time X min (N bars) | finished HH:MM:SS`. New bats
`backtest/Run_FullBT_HMM_10k_lot001_TEST.bat` (1 wk) + `_FULL` variant (`Run_FullBT_HMM_10k_lot001.bat`, 1 yr): current
corrected rel HMM, $10k equity, fixed 0.01 lot, live-faithful (htf trail + regime-TP + buf 0.15), one-folder-per-run
output = backtest_report.txt + backtest_signals_*.csv (every bar) + backtest_trades_*.csv (each trade + f_* features) +
backtest_summary_*.csv. NOTE: single-model IN-SAMPLE (OOS honest baseline stays the WFO wfo_asof_rel +393.7R). Verified:
1-wk TEST clean ($10k→$10,042, MaxDD 0.0%, timing lines + DONE mark print).

**AI DECISION SUMMARY box — dashboard, every bar (2026-07-03, Imtiyaz).** One always-visible box on the dashboard
(above the tab bar) that refreshes every 15-min bar with the model-transparency digest Imtiyaz asked for ("don't
just ask BUY/SELL — ask why/confidence/regime/risk/invalidation/past-similar"). Shows: signal + final win_prob vs
threshold, regime (HMM), the 4 model probs (Main/State/Direction/BigWin), a **5-model AGREEMENT score** (Main≥thr,
State≥thr, Dir≥thr, HMM-actionable, BigWin≥0.5 → X/5 → LOW/MEDIUM/HIGH/VERY-HIGH), expected $ move + suggested SL/TP
(from the move/MAE models), **"signals like this" history** (WR/PF/avgR/maxDD for the current prob-band, regime-specific
when >60%), why, and invalidation. Build: `engine/build_prob_buckets.py` → `logs/prob_bucket_stats.json` (WR/PF per
prob-band + regime from the full backtest — re-run after each fresh backtest); `bridge_dashboard.build_ai_summary()`
(read-only, fully try/except-guarded, never touches the live decision path) → adds `ai_summary` to `dashboard.json`;
`dashboard.html` `renderAISummary()` + `#ai_summary_box`. Fable-5 architecture (read-only, decoupled, snapshot pattern)
+ its metric guidance (per-regime buckets, grey-out on small n) followed. Compile/JS-syntax clean; sample injected from
the real last_signal renders correctly (SKIP/Ranging/1-of-5/LOW). Activates on next bridge write (restart to load).
UI iterated per Imtiyaz: grouped rounded bubbles (label-up/value-down), centered, big headings, per-model VOTES merged
into MODELS (prob + ✓/✗), full green/red color-coding (signal/prob/regime/WR/PF/avgR/votes), SKIP=yellow, title+invalidation
on one row. **MARKET INTELLIGENCE box added below it** (`bridge_dashboard.build_market_intel()` → `market_intel` in
dashboard.json; `dashboard.html` `renderMarketIntel()` + `#market_intel_box`, cyan theme) — CONTEXT groups TREND (M15/H1/H4
SMMA + HTF agree + line-dist), STRENGTH (H1/H4 ADX + DI), STRUCTURE (H4/H1 S/R + in-OB), FLOW (phase/imbalance/corr), CONTEXT
(vol/session/news). Deliberately NON-duplicative of the AI box (no signal/prob/HMM-regime/models/history). Needs `ts_trend_m15/h1/h4`
now also exposed in inference.py result dict. Both boxes refresh every 15-min bar (per new signal).

## 2026-07-02 — HMM v3 (flat≠Volatile fix, A/B), CSV output rules, system audit + fix tools
Worked on by Claude via Cowork (Divyesh). Full audit detail → `docs/AUDIT_2026-07-02/`.

**HMM v3 — "flat market reads Volatile" fix (A/B, WFO running):** v1 (+DI/−DI raw) and v2
(di_sum/clarity) both failed; v2 ALSO had a predict-path bug — PlusDI/MinusDI keys were never
passed at inference → silently 0 (train≠predict). v3: two variants behind env `QGAI_HMM_VARIANT`:
`spec` = [ADX, |DI_diff|, band_width_pct] (literal plan — fails own acceptance in sandbox) vs
`rel` = [ADX, di_eff(=inst. DX), band_rel(=band/trailing-30d mean)] (passes all: flat 07-02 window
18 Ranging/4 Trending/0 Volatile; train≈full distribution; Volatile=1.65× band_rel). Root causes
found: gold vol drift 2022→26 makes raw band % non-stationary (flat window = p88-92 globally but
p21-53 vs last 30d), and smoothed ADX/|DI_diff| stay high in post-trend chop. Code: `regen_adx_di.py`
+ `mt5_data_updater.py` + `fresh_reload.py` write band_width_pct/di_eff/band_rel per TF;
`hmm_model.py` v3 (pkl stores its own feature list → env-proof predict; missing-key warning);
`features.py`/`inference.py`/`train.py`/`self_learning.py` key-lists now driven from model.features
(kills the silent-zero class of bug; self_learning positional-column bug also fixed);
`verify_hmm_window.py` NEW acceptance script. Bats: `Run_HMM_AB_WFO.bat` (regen+freeze+launch both),
`Run_HMM_WFO_A_spec/B_rel.bat`, `Run_HMM_v3_Deploy.bat`. Regen ran clean (DI_diff parity Δ=0.000).
Gate: adopt winner ONLY if ≥ +483.1R. Bridge NOT restarted. (Bat gotcha fixed: `|`/`>=` inside
title/REM lines are parsed by cmd — pipes/redirects fired; all bats sanitized.)

**Output rules (Divyesh):** every backtest/WFO (bat OR direct python) also saves CSV results in the
SAME run folder — `run_wfo.py` → `_WFO_SUMMARY.csv`, `backtest_replay.py` → `backtest_summary*.csv`;
run documents live in that same folder too (one folder per run). Report format rule CHANGED same
evening: reports/analyses in **.md only** (replaces the morning's "all three formats" rule).
Documentation rule: all changes go into the 3 living docs (GUIDE / this CHANGELOG / TASKS) — no new
per-change documents unless explicitly asked.

**Independent system audit (docs/AUDIT_2026-07-02/):** verdict **D — Experimental (borderline C−)**,
readiness 41/100, leakage risk 38/100. Three key findings: (1) CONFIRMED intra-bar HTF lookahead —
M30/H1/H4 ADX-DI columns on the M15 grid embed full-bar (future) data; H4 drift vs honest partial-bar
mean 0.60 / max 2.02 ADX pts → all backtest/WFO numbers incl. +483.1R are upper bounds; (2) entry-ML
is not the edge — 89% of OOS profit is TPCAP exits; win_prob NOT calibrated (<50% bucket won 67.1%,
+113.7R); 10/42 features zero importance; TRAIL bucket value-destroying (peak +0.94R → exit −0.15R);
(3) live≠backtest — June 2026: WFO +48.1R/66.7% WR vs shadow −1.9R/29.4% WR (109 trades); entry
overlap only 8/66 (12%); live TRAIL 49% of exits vs 11% backtest; real live n=18: top-3 wins +$158.7k,
other 15 = −$21.5k, lots 0.89→15.58. **Fix tools shipped:** `engine/regen_adx_asof.py` (leak-free
as-of rebuild, validated err=0.0 vs brute force) + `backtest/Run_Fix1_AsOf_Regen.bat` (run AFTER A/B
WFO; new WFO after apply = new HONEST baseline, +483.1R retired); `engine/reconcile_shadow.py`
(weekly shadow-vs-backtest reconciliation, ±20% scaling gate); plan: prune dead features, retire
failed SELL move-model, rolling-OOS recalibration + threshold sweep, `--sweep-trails` on as-of data.
Master sequence → `docs/AUDIT_2026-07-02/SOLUTIONS_1_2_3_2026-07-02.md`.

**2026-07-03 — FIX-1 APPLIED + HMM v3 `rel` DEPLOYED.** A/B WFO (leak-world): spec +470.4R
degenerate REJECT; rel +481.7R ≈ baseline. Honest (as-of) A/B: legacy +407.6R vs rel +393.7R —
paired t=−0.69 = tie; rel maxDD 5.2R vs 7.0R (−26%), 0 negative weeks vs 2 → **Divyesh chose rel.**
Leak-inflation confirmed ~15-18% (483→408). `Run_HMM_v3_Deploy.bat`: models backup
(`_backup_pre_hmm_v3`) + as-of adx_merged applied (`.bak_preasof_20260703_104235`) + full retrain
(combined AUC 0.677 val / 0.669 test; SELL test 0.743) + **verify ALL CHECKS PASSED** (flat 07-02
window 18 Ranging/4 Trending/0 Volatile; stability 45/35/20 train≈full). `mt5_data_updater.py`
now writes as-of rows (updates stay leak-free). `run_wfo.py`: `_WFO_SUMMARY.csv` + per-week ⏱
ETA/countdown; `backtest_replay.py`: `backtest_summary*.csv`. Legacy variant (original 8-feat)
preserved in hmm_model.py behind `QGAI_HMM_VARIANT=legacy` (restored from engine_backup_0612).
**Bridge-start crash FIXED (2026-07-03 ~11:00):** first demo start crashed every bar —
`get_signal failed: Input X contains NaN` (GaussianMixture). Root cause: `bridge_main.get_live_adx()`
built live-appended ADX rows with ONLY {TF}_ADX+{TF}_DI_diff → the new HMM columns
(di_eff/band_rel/band_width_pct/PlusDI/MinusDI) were NaN on merged live rows. WORSE (pre-existing
live≠train drift): the old inline calc used UNSMOOTHED DX as "ADX" and last-CLOSED HTF bars —
neither matched training. Fix: get_live_adx now pulls ~5000 M15 bars and computes EVERY column via
`regen_adx_asof.asof_tf` (train==live by construction) + NaN row guard; `hmm_model.predict/
predict_batch` got a NaN neutral-fill guard (band_rel→1.0, else 0) so a feature gap can never kill
the trading loop again. Requires bridge restart to load.
**Direction-swap LOG bug FIXED (2026-07-03, flagged by Divyesh):** backtest evaluates BUY then
SELL per bar; `backtest_replay` logged `engine._last_features` = always the LAST call (SELL) — so
when BUY won the pick, the trade's f_* columns described the SELL evaluation (131/308 OOS BUY rows
had f_trade_direction=−1). **Decisions/probabilities were always correct** (each get_signal computes
its own features; online-learner path protected by the trade_type guard in on_trade_closed) — only
the LOGGED analysis columns were corrupted. Fix: per-direction feature cache in inference
(`_last_features_buy/_sell`) + backtest takes the winning direction's dict. ⚠ Any PAST analysis
built from backtest f_* columns of BUY trades is suspect. Re trade_direction importance 0.0:
training data was CORRECT (features recomputed per trade Type at train time); the 0 is redundancy —
direction-awareness lives in ts_htf_agreement (#2) + momentum_aligned_1hr (#4), which are
direction-SIGNED features. trade_direction stays a FIX-2 prune candidate.
**NEW HONEST BASELINE = wfo_asof_rel +393.7R.** Honest-data feature importances shifted
(hmm_state 0→0.0305 #6; only h4_trending_h1_aligned/trade_direction + direction-specific zeros
remain dead) → FIX-2 prune-list must be rebuilt from the new feature_importance.csv. Next: bridge
start on DEMO config → watch flat-hour states → FIX-2/FIX-3 per audit plan.

---

## 2026-07-01 — stuck-trade protect + graduated hedge, vSL-recovery/retry-loop bugs, backtest resume, mojibake, formatting
Worked on by Claude via Cowork. Full detail → `TASKS.md` DONE table (2026-07-01 rows) + `BUG_LOG.md`
(bugs N/O/Q/R + the earlier same-day entries). This is a summary index.

**Live-incident fixes (early in the day):** win_prob frozen 75+ min (`inference.py` OHLC-merge staleness
guard silently failing — now `log.error`s + a `_ohlc_stale_bars` counter); 10027 close-fail (AutoTrading
off) surfaced as a one-line `[ERROR]` only — led to the stuck-trade-protect feature below; mojibake console
output (`Start\*.bat` missing `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8` — added to all 5); dashboard.html
fixes (Imtiyaz's own edits: duplicate `sig_history_chart` canvas ID, missing MODEL confidence box);
win-prob/all-% displays standardized to 2 decimals (~35 spots across 8 files).

**Stuck-trade manual-protect (`bridge_session.py`, NEW):** `_close_position()` tracks consecutive
close-failures per ticket; past `stuck_close_fail_threshold` (3) escalates a repeating `🚨 STUCK` alert +
(if `stuck_trade_hedge_enabled=True`, enabled today) opens a FULL-lot protective hedge on a dedicated
`stuck_hedge_magic` (202698) — deliberately NOT L13's `manual_hedge_magic` (202699), whose cleanup sweep
would otherwise silently close it. Auto-unwinds once the original close succeeds.

**Bug N (open) — vSL-recovery fallback = hardcoded $15 guess:** Imtiyaz flagged leftover trade
#1519547791's vSL not matching the live H1 line. Traced to `recover_open_trades()`'s fallback (no comment
VSL/SL + no broker SL → hardcoded `sl_dist=15.0`) discarding the real trailed vSL on every restart. See
BUG_LOG.md #N for the full trace.

**Bug O (fixed) — close-retry-loop was broken:** found while investigating bug N. All 5 `_close_position()`
call sites in `bridge_core.py` did `del virtual_trades[ticket]` **unconditionally**, even on a FAILED
close — silently abandoning live monitoring after one failure (its own alert claimed "will keep retrying",
which was false). `_close_position()` now returns True/False; callers only delete on confirmed success —
threaded the trade's real `virtual_sl` through too (`_close_position(ticket, vsl=...)`).

**Graduated stuck-trade excess-hedge (Imtiyaz's idea, NEW, `leftover_excess_hedge_enabled=False` by
default):** `bridge_session._stuck_risk_hedge()` — stretch risk from `risk_pct` (3%) to
`leftover_risk_cap_pct` (6%) and hedge only the excess lot once real slippage (price past the trade's
actual vSL, via bug O's fix) exceeds the stretched budget, instead of an immediate full-lot freeze.
Not yet enabled or fire-tested.

**bridge_main.py mojibake — per-glyph, not blanket:** ~680 pre-existing corrupted log-message
glyphs found file-wide; a first blanket-fix pass was explicitly reverted per Imtiyaz ("only remove
[the one he flagged]"), then re-applied one glyph at a time as he pointed each one out: 💓⚙️──👁📋📊🚀💰✅—·.

**backtest_replay.py: checkpoint/resume + unbuffered-console fix, NEW:** `_checkpoint_pkl` existed in code
but was never read/written (dead) — a stopped run lost all progress. Now saves every 500 bars + on
Ctrl+C (config-signature-gated, `--no-resume` to force fresh), auto-deletes on success. Also fixed
`stdout`/`stderr` not being line-buffered (progress prints sat unflushed, long runs looked frozen) —
`line_buffering=True` + `flush=True` + 100-bar progress interval + `PYTHONUNBUFFERED=1` in
`Run_Live_Buffer_015_CSV*.bat`. ⚠️ Bash sandbox mount was stuck serving a 3+ hr stale cached copy this
session — could not `py_compile`-verify automatically, did a full manual line-by-line review instead.

**`Run_Live_Buffer_015_CSV.bat` (full 1-year, $10k/3% dynamic compounding) deep-parity-checked** against
live config (buffer 0.15%, TP-regime values, TP-equity-bypass avoidance, HTF SL/flip/forming auto-sync via
CFG import, entry-SL sizing, risk%, no-lookahead) before trusting it — all ✅. 1-week smoke test passed
first (`_TEST.bat`). Full run kicked off by Imtiyaz, in progress.

---

## 2026-06-29 — L13 MANUAL-TRADE MANAGER + L11 BACKFILL + signal-log + L8 fix + cent account
All reversible. Most live-config flags unchanged; new work is config-gated.

**L13 Manual-trade Manager (`engine/bridge_manual.py`, NEW) — final design (approach A, COMBINED vSL):**
- Treats ALL manual XAUUSD trades (magic 0; bot=202600) as ONE combined net position: sums net lots,
  takes the volume-weighted average entry, runs ONE ratcheting vSL for the whole group.
- **Risk = SEPARATE 3% pool** (`manual_risk_pct=3`, independent of the bot's `risk_pct=3` → 3%+3%=6%
  total, two budgets on the same equity). On first detect, sets a 3% broker SL on every leg; if combined
  lot > 3%-equivalent volume, HEDGES the excess (magic 202699).
- **ONE ratcheting vSL** up the 2-SMMA line (HTF/H1 per `ratchet_htf_sl`), one-way, capped at the 3%
  floor — trailed as a **VISIBLE broker SL on every leg** (logs 🔼). Breach (trend turns) → close ALL
  manual legs + hedges (🔻). **No flip-hedge** — the vSL handles reversal (FLIP_CLOSE hook in
  `bridge_core.py` left as comment only).
- **Target TP** (`manual_target_tp_pct=2%`) on combined avg → close ALL (🎯).
- Mixed-direction nets out; fully self-hedged (net 0) → no vSL. Also manages trades already open at start.
- **L8 isolation:** `manual_floating()` subtracts manual+hedge P&L from the bot's daily ratchet/TP.
- **DEMO (primary) only** — cent extension rejected (would clash with mirror-trading replication).
  Config: `manual_manager_enabled=True` (demo test), `manual_risk_pct=3` (separate pool), `manual_sl_pct=1`,
  `manual_target_tp_pct=2`, `manual_hedge_magic=202699`. Master switch reversible (set False to disable).
- ⚠️ `bridge_manual.py` hit mount-write null-byte corruption twice — stripped + re-verified both times
  (would crash import). If import errors / "null bytes" ever appear, re-strip the file.

**L11 startup gap-backfill (`bridge_main._overnight_replay`):** on start, logs any missing signal bars
(`mode=BACKFILL`) using a `_logged_bar_times()` set so the signal log is continuous after downtime.

**Signal-log overhaul:** `build_signal_log.py` merges full-history regime backtest (every bar + `$move`)
+ live `signals_all.csv` → `engine/logs/signals_complete.csv` (bat: `backtest/Run_BuildSignalLog.bat`).
`bridge_data.log_signal` got a dedupe guard (one row/bar+mode) + `equity` + `move` columns;
`write_outcome` now writes the real `$move = (exit−entry)·dir` and backfills offline-closed outcomes.
`dashboard.html` rebuilt to ONE date+time-sorted log (history cached + live 15s) with WIN/LOSS + $move.

**L8 false daily-SL halt FIXED (`bridge_session._net_balance_flow_today`):** was using local time → MT5
returned lifetime deposits as "today's flow" → bridge halted all day. Now broker-time filtered + 50%-of-
day-open safety guard + warn-once. Live-confirmed fixed.

**L8 COMPLETED (remaining 3 pieces, 2026-06-29):** (1) **lot-sizing flow-adjusted** — `bridge_core.execute`
now sizes off `equity − today's flow − manual_floating` (an intraday deposit/withdrawal or the manual leg
can no longer grow/shrink the bot's 3% lot). (2) **signal-log `trading_equity` column** —
`bridge_session.trading_equity()` = equity minus net external flow since a fixed anchor (2026-06-29);
written on every live/monitor signal (`log_signal(..., trading_equity=)`); pre-L8 CSVs auto-migrate via
`_ensure_teq_column` (trailing column, old rows blank). (3) **flow-event logging** —
`session.log_new_balance_ops()` (called each bar) announces each NEW deposit/withdrawal once → bridge log +
`logs/balance_flows.csv`. All three fall back safely (raw equity / no-op) on any MT5 error. Files touched:
`bridge_core.py`, `bridge_session.py`, `bridge_data.py`, `bridge_main.py` (0 null bytes; bash py_compile
shows false last-line errors = mount truncation, Read-tool verified complete). DEMO-verify next.

**Accounts (`config_mt5.py`):** added cent-live `29453256` (VantageMarkets-Live 21, `XAUUSD.pc`,
secondary), disabled TradeQuo `125926628`. VantageDemo `25334572` stays PRIMARY. Backup
`config_mt5.py.bak_20260629`. ⚠️ holds real passwords — never commit/expose.

**Bug A + Bug F — verified ALREADY DONE (docs were stale):** (A) secondaries are flattened on every daily-SL/
TP halt path (`bridge_main:360-365`, `bridge_core:369-372/377-380`), transition-guarded. (F) `backtest_replay`
defaults `TRAIL_MODE` to the live config (`htf` if `ratchet_htf_sl` else `line`, line 243-249) + Bug J entry-SL
+ H1 flip. No code change — just ticked off in TASKS L4.

**L7b (partial) — dead `bridge_risk` code REMOVED:** dep-traced that every live `VirtualTrade` is `ratchet=True`
(a non-ratchet trade is skipped at `execute()`), so the non-ratchet path was unreachable. Removed `_update_buy`,
`_update_sell`, `_smart_exit_check`; `update()` now always routes to `_update_ratchet`; trimmed the now-unused
PBE/BE/SMART_EXIT imports. `__init__` + `status()` fields kept (dashboard uses them). Compile-OK; mount-write
null-byte corruption hit the file (5661 nulls) → stripped + re-verified (0 nulls, would otherwise crash import).
**Feature removal — `ts_line_dist_pct` dropped from the model (Anisa, explicit request):** investigation of
`BASELINE_trades_tp_1.00.csv` (1303 trades) showed entry distance-from-line is the strongest outcome signal
(near-line +0.392R/50% win vs far/chasing +0.034R/43%) — this is the mechanism behind the "system enters at
the bottom" observation (late/chasing entries barely break even). A distance-from-line ENTRY FILTER tested
in-sample lifted PF 1.74→2.25 (≤0.40% cutoff), but Anisa declined the filter AND the feature. `ts_line_dist_pct`
(rank #2, imp 0.0484) was added to `_MANUAL_PRUNE` (features.py) → excluded from all model feature sets
(main + ranging/trending/volatile). ⚠️ **Requires `3_Train_Models.bat` retrain before next bridge restart**
(live .pkl=44 feat vs code=43 → mismatch). Flagged that it's a top feature (removal likely lowers PF/AUC);
recommend a post-retrain WFO. REVERT: delete the `_MANUAL_PRUNE` line.

**L7b ATR — REMAINING cleanup done (2026-06-29, bot stopped):** with the bot stopped, removed the last
ATR vestiges: `bridge_main` atr20_pct/atr20/tr compute deleted; `inference.py` vol_regime → constant
"normal" (was ATR-derived, display-only) + atr14/atr20_pct result-dict keys removed + move-model
normalization → fixed 0.2; `train_move_model.py` atr_usd → fixed 0.2 (matches inference; atr20_pct was
always the 0.2 default, so net-identical — no retrain needed). ADX-internal `atr14` (Wilder TR for ADX/DI)
KEPT (real indicator math). SQLite/CSV `atr20_pct` column LEFT nullable (logs 0) — dropping = DB migration
+ dashboard-parity risk, not worth it. inference+bridge_main hit mount null-corruption (82+327 nulls) →
stripped + COMPILE_OK. Bot safe to restart (behavior-neutral).

**L7b ATR — SAFE SUBSET removed (live-neutral):** ATR confirmed fully vestigial (out of FEATURE_COLS since
06-19; reads use default constants; `execute()`'s `atr20_pct` param unused; `vol_regime` informational-only).
Removed the `📐 Live ATR20` per-bar log + `result["atr20_pct"]` threading (`bridge_main`) and the unused
`atr20_pct` param from `execute()`/`handle_opposite_signal()` (`bridge_core`). 0 nulls, Read-verified.
Deferred (need bot stopped): SQLite `atr20_pct` column (kept nullable → logs 0, no live migration), the
`inference.py vol_regime` constant, the `df["atr20_pct"]` compute, and `train_move_model.py atr_usd`.

---

## 2026-06-27 — REPO REORGANISATION (docs + backtest tidy-up; nothing deleted)
Big housekeeping pass — files were scattered across root / `engine/` / `bug_review/` / `engine/docs/`.
All MOVES, nothing deleted; everything is reversible.

**Docs → one folder `docs/`:**
- Active docs now in `docs/`: `QGAI_GUIDE.md` (master hub), `WORKING_NOTES.md`, `TASKS.md`, `STRATEGY.md`,
  `RULEBOOK.md`, `SYSTEM_OVERVIEW.md`, `FEATURES.md`, `BUG_LOG.md`, `FIXES_CHANGELOG4.md` (this file).
- Old docs → `docs/archive/`: SESSION_NOTES, BACKTEST_SUMMARY, the two *2026-06-22 reviews, CHANGELOG 1-3,
  GPT guides, and 5 old engine/docs txt (README_INSTALL, THIRD_PARTY_REVIEW, bug_audit ×2, buf0.06_current).
- `CLAUDE.md` STAYS at repo root (auto-loaded memory) and now points to `docs/`. Cross-references in
  `CLAUDE.md` + `QGAI_GUIDE.md` updated to the new paths. No code/bat references docs → nothing broke.
- Empty `bug_review/` dir + `engine/docs/` (2 live logs left) couldn't be rmdir'd via the mount — delete the
  empty `bug_review/` in Explorer if desired.

**Backtest tidy-up (`backtest/`):**
- New `backtest/README.md` = bilingual INDEX of all bats + results map.
- 31 bats → 14 ACTIVE (kept) + 17 superseded → `backtest/_archive_bats/` (trail variants, ablation,
  fixes A/B, all-backtests, reset — those ideas are done).
- `engine/` cleaned of 21 stray backtest outputs (`results_tp_*.txt` ×11, `trades_tp_*.csv` ×10,
  TP_SWEEP_SUMMARY) → `backtest/results/_archive/engine_tp_outputs/`.
- 15 old result folders (sweep_*, wfo_results_*, ablate, trail_compare, _OLD_GARBAGE…) → `results/_archive/old_runs/`;
  loose result txt → `results/_archive/loose_txt/`. Active result folders untouched (backtests, wfo_results,
  report, replay_logs, baseline).
- 6 one-off research .py LEFT in `engine/` (they import engine modules; would break if moved) — documented in README.

**New layout:** `CLAUDE.md` (root) · `docs/` (all docs) · `backtest/` (bats + README + results) · `engine/` (live code).

---

## 2026-06-26 — Regime-adaptive TP + CLOSED-LOOP RELABEL (train=backtest=live)

### A. REGIME-ADAPTIVE TP cap (backtest, config-gated, default OFF)
- 13-TP sweep (`backtest/results/backtests/tp_*`) showed each HMM regime wants a different TP cap.
  `backtest_replay.py`: new `--tp-regime` flag + `_TP_BY_REGIME` map (Ranging 2.0 / Trending 1.0 /
  Volatile 0.8), switched on the trade's HMM state at entry. Reversible (omit the flag = old behaviour).
- Bats: `Run_TP_Regime_TEST.bat` (smoke) + `Run_TP_Regime.bat` (full) + `Run_Backtest_FullHistory.bat`
  (2022→2026 total dataset, global vs adaptive). Full 9-mo A/B: **regime-adaptive WON** — Total R
  257.7→**310.2 (+20%)**, PF 2.52→2.56, avg R 0.384→0.436, DD 1.7→2.0% (Ranging the driver +34R).
- ⚠️ IN-SAMPLE. NOT in the live bridge yet — gated on WFO OOS + full-history checks first.

### B. 🔥 CLOSED-LOOP RELABEL — model now trains on LIVE-EXIT labels (Imtiyaz's concern, fixed)
- **Problem:** the win-prob model trained on `Back_testing_data_final_cleaned.xlsx`, whose Win/Loss
  came from an OLD external backtest's exit — NOT the live exit (ratchet + HTF H1 SL/flip + TP cap).
  So the model predicted "win" for the WRONG exit definition.
- **Fix:** `engine/relabel_trades.py` (+ `backtest/Run_Relabel_Trades.bat`) replays every entry through
  the live HTF exit engine (reuses `analyze_capture.py` line/flip construction), leakage-safe (each trade
  forward-simulated on its own future bars only). Recomputes Win/R/$Move/exit + adds R + exit_reason cols.
- **Result:** 2,743/2,788 relabeled (45 unmatched at data edges). **744 labels CHANGED (27.1%)** even
  though aggregate WR is coincidentally identical (37.7%→37.7%) → the model HAD ~27% labels disagreeing
  with live. Exit mix FLIP 1050 / TRAIL 679 / TP 543 / SL 471. Output:
  `data/Back_testing_data_final_cleaned_RELABELED.xlsx`.
- **`config.py trades_file` switched to the RELABELED file** (reversible — comment holds old name).
  NEXT: `3_Train_Models.bat` retrain → WFO-validate vs PF 1.55 → keep only if equal/better.

---

## 2026-06-23 (evening) — Signal Log, Virtual Ledger, CAPTURE leak + two fixes
Big session. Dashboard signal-log overhaul, a virtual paper-trade ledger surfaced, and a
data-driven hunt for WHY the system misses clean trend moves → two reversible fixes.

### A. DASHBOARD — Signal Log (live, on the dashboard, works even when bridge is OFF)
- **`signals.html`** (new) — standalone Signal Log viewer; reads `logs/signals_all.csv` directly,
  so it shows even when the trading bridge is stopped. Filters (All / BUY-SELL), 15s refresh.
- **`dashboard.html`** — inline **📋 SIGNAL LOG** panel placed **below ▸ RISK & SESSION** (COL 3),
  styled like the old 🌙 panel (Trending/Ranging/Volatile HMM badge + replay-row look) + filter
  buttons (All / BUY-SELL / ↻). CSV-based. Columns shown: Time · Signal · **Price** · Win% ·
  Regime · **H4 RANGE** · **BW%** (big-win prob) · **lot** · **WIN/LOSS** (real outcome) ·
  **virtual WIN/LOSS+R** (from shadow ledger, dashed badge = paper) · **equity** (at signal time).
- Old duplicate 🌙 Signal Log widget removed; 📈 CHART + 📒 LEDGER tabs added.
- Label clarity: orange **"H4 RANGE"** (H4 in_range_phase flag) vs HMM **"Ranging"** regime —
  were confusing; now distinct + tooltips. (H4 RANGE = 4-h move <0.5%; HMM = 15-min state.)

### B. DEDUPE + EQUITY in the signal log
- **Bug: same M15 bar logged 2-3×** in signals_all.csv. Cause: no dedupe + a range-block
  double-log. Fix: `bridge_data.log_signal` now writes **one row per (bar_time, mode)**
  (module guard `_last_sig_key`); `bridge_main` range-block path `else`→`elif not _range_block`.
  Cleaned 44 existing dup rows (backup `.bak_20260623`).
- **`equity` column added** to log_signal (CSV) — account equity **at signal-generation time**,
  logged for EVERY signal (executed or not). All 6 call sites pass `equity=_cur_equity`
  (`_acct.equity` captured each bar). Existing CSV migrated (`.bak_eq_20260623`).
- `serve.py` chart_data.json write wrapped in try/except (silences harmless WinError 10053).

### C. VIRTUAL TRADE LEDGER (shadow) — see all trades, real OR monitor, even when off
- System already had `shadow_ledger.py` (simulates every BUY/SELL signal forward with the live
  exit rules → R, $, exit-reason, real_executed). It had not run since 06-19 → regenerated
  (712 paper trades). **`shadow.html`** (new) — the Virtual Trade Ledger viewer the
  `6_Shadow_Ledger.bat` referenced but which never existed: entry/exit, why-exit, R, $, %,
  WIN/LOSS, **REAL/VIRT** tag, summary stats + filters. **📒 LEDGER** tab added to dashboard.
- Signal-log panel **merges** the shadow outcome → BUY/SELL show virtual WIN/LOSS even in MONITOR.
- **`scheduler.py`**: auto-refresh shadow ledger **every 15 min** (`_shadow_sec`) so the virtual
  log stays current without manual runs.

### D. 🔥 CAPTURE LEAK found — "Captured Move / Available Move" (Anisa's framing)
- New metric: `engine/analyze_capture.py` + `backtest/Run_Capture_Analysis.bat`. Re-simulates
  real signals under 4 exit rules. Also added a **Captured/Available** line to the
  backtest_replay **report**.
- **Finding:** 18-23 Jun = 318-pt downtrend available, system **captured −61 pts (−19%)** —
  14/18 trades exited via **FLIP at ~−8 pts each = M15-line whipsaw**.
- Variant test (738 signals): **HTF H1-flip = 2× captured move, +33% total R** (+223→+297R).
  The M15 flip whipsaw is the leak; HTF (H1 line, farther) rides the trend. (This is the HTF
  exit we built then reverted on 06-23 afternoon — data says re-enable.) flip-confirm = runner-up.

### E. 🔥 ENTRY fix — COUNTER-TREND-FADE block (Anisa's "dominant-TF" insight)
- Tested entry filters 5 ways; only this works: block a trade **against the DOMINANT timeframe
  momentum** (H1 or H4 — **whichever ADX is higher**) **when that dominant ADX slope is FALLING**
  (trend real but fading = whipsaw zone). In-sample (1303 trades): **+15R, PF 1.74→1.89**;
  blocked group = net-loser (PF 0.67). Counter-trend in a RISING trend is fine (kept).
- Implemented config-gated (default OFF): `config.skip_counter_trend_fade`;
  `inference.py` now exposes H1/H4 ADX/DI/slope in the result dict; filter in
  `backtest_replay.py` (`--ctf-fade` CLI) and `bridge_main.py`. Lookahead-free.

### F. BACKTEST INFRASTRUCTURE
- `backtest_replay.py`: `backtest_signals*.csv` now has **`blocked_by`** (range/ctf_fade) +
  H1/H4 ADX/DI/slope → audit which signals were blocked and why. Trades CSV already carries
  entry/exit/why (reason+exit_reason)/price_move + full 55 `f_*` features for research.
- `backtest/Run_Backtest_Fixes.bat` (+ `_TEST`): A/B **baseline / +CTF / +HTF / +BOTH**,
  **0.01 fixed lot**, **resumable** (skips runs with an existing report). New backtests save
  **separately** under `backtest\results\backtests\` (WFO stays in `backtest\results\wfo_*`).
- TEST (26 May–12 Jun) PASSED, no errors: BOTH best (PF 4.58 vs 3.84). Full 9-mo run pending.

### ✅ ENABLED (2026-06-23 evening) after full backtest confirmed BOTH best:
Full 9-mo backtest (0.01 lot, real engine): BOTH = PF **2.29→2.52**, WR 53→**55.5%**, Total R
+252→**+258**, MaxDD 4.2→**3.6%**. CTF is the main driver; HTF adds lower DD on top. (TP=1.00 caps
the HTF "trend-ride" gain, so Total R rise is modest +2.4% — but quality/DD clearly better.)
Set in `config.py`: `ratchet_htf_sl=True`, `ratchet_htf_flip=True`, `skip_counter_trend_fade=True`.
All reversible (set False). ⚠️ In-sample → watch the live/demo equity curve closely; revert if it
behaves worse than backtest. Restart `1_Start_Trading.bat` (+ `5_Dashboard.bat`) to load.

---

## 2026-06-23 (afternoon) — TP=1.00 revert + RANGE-PHASE filter (data-driven)
Data showed the OLD **TP=1.00 + partial/BE** config was the best result (backtest_replay real
model: +287R / PF 1.74; TPCAP is the profit engine = +352R, 100% win). Far-TP we switched to
earlier actually CUT profit (winners went to FLIP/TRAIL ≈ $0 instead of the 1% TP). So reverted:
- **config.py:** `ratchet_tp_cap_pct` 10.0 → **1.00** (TP at 1%); `ratchet_htf_sl` True → **False**;
  `ratchet_htf_flip` True → **False** (M15 ratchet, matches trades_tp_1.00). Reversible (comments hold old values).
- **🔥 RANGE-PHASE ENTRY FILTER (new, strongest lever):** `skip_range_phase_entry = True` +
  `range_phase_min_prob`. Skips entries when H4 in_range_phase==1 (chop). Data: range trades net
  −43R / PF 0.76 vs trend PF 2.62; skipping → PF **1.74→2.62**, +43R, +$1,283 move. Trend-following
  whipsaws in ranges. in_range_phase is lookahead-free (last completed H4 bar). Implemented in
  config.py + backtest_replay.py (entry gate) + bridge_main.py (skip + "⏭ SKIP (range-phase)" log).
- **`price_move` column** added to backtest trade CSV = (exit−entry)×dir = actual $ gold move captured;
  report shows "Price move ($): Total | avg". Baseline file: backtest/results/baseline/BASELINE_trades_tp_1.00.csv.
- **serve.py:** wrapped chart_data.json write in try/except (ConnectionAborted/Reset/BrokenPipe) —
  silences harmless WinError 10053 when the browser refreshes mid-response.
- Retrained → 44 features (volume removed), AUC Main 0.7594/0.7470, BUY 0.80, SELL 0.75 — healthy.
- **Data-driven "chasing" pattern found:** losers concentrate in range-phase (in_range 0.52 vs 0.30),
  high M15_ADX (≥45 PF 1.21 vs <25 PF 2.52), and FAR from the 2-SMMA line (PF 1.14 vs CLOSE 2.96).
  Same lesson: late/extended entry = bad; early/clean trend entry = good (PF up to 5.5). M15_ADX and
  ts_line_dist_pct are TOP features — USE them as filters, do NOT remove. (See STRATEGY.md.)

## EXIT LOGIC (config.py + bridge_core/ratchet/risk)
- **HTF H1 exit (NEW, LIVE ON)** — `ratchet_htf_sl=True`, `ratchet_htf_flip=True`, `ratchet_htf_tf="H1"`.
  Problem: 15-min SMMA(2) line sat near entry → SL cut by 15-min noise → 3× re-entry whipsaw
  even when 4h/1h/30m all agreed. Fix: SL + flip now ride the **H1 line** (farther). Entry
  stays 15-min; lot auto-shrinks so 1R still = `risk_pct`% equity. `get_htf_state()` added in
  bridge_ratchet (reuses compute_trend on H1/M30/H4 bars). `ratchet_htf_max_risk_pct=2.5`
  (if H1 line is farther than this, fall back to the 15-min line).
  Backtest (H1, no-TP, $0.30 cost, aligned): +61.7R, PF 1.17, $10k→$33k vs M15 ~breakeven.
- **Buffer 0.09% → 0.20%** (`ratchet_buf_pct`) — buffer-sweep: same profit ($33k) but max DD
  61%→55%, PF 1.18. SL = H1 line ∓ (price × 0.20%).
- **TP set far** (`ratchet_tp_cap_pct=10`, ~no TP) — flip is the exit. h1_tp_sweep: tight 1R TP = PF 1.00
  (kills edge); far/none = PF 1.21. `tp_equity_pct=0` (price-based TP path).
- **Min SL** fixed $8 → `ratchet_sl_min_pct=0.18%`; **breakeven buf** $2 → `breakeven_buf_pct=0.05%` (%-of-price).

## RISK / DAILY (bridge_session.py + backtest_replay.py)
- **Daily RATCHET rule (NEW)** — replaced fixed −9% daily SL with a trailing floor:
  floor = day-peak-equity − 9%. Loss-cap −9% at open; as profit grows the floor trails up
  (peak +9% → break-even, peak +12% → +3% locked). State: `day_peak_equity` (init/reset/preload).
  $10k-sim: at 2% risk RATCHET beat fixed (+1,589% vs +1,461%, DD 22%).
- **Trade-2 Equity SL — REMOVED COMPLETELY** (not disabled) from bridge_core, bridge_session,
  bridge_dashboard, bridge_constants. It halted the whole day at −3%, conflicting with the
  9% daily SL. Now clean: per-trade 3% (vSL=1R) + daily 9% only. (grep-verified, no leftovers.)

## ML / FEATURES (features.py + train.py + xgb_model.py)
- **ATR removed** — `atr14_pct` / `atr20_pct` no longer computed or in any feature list.
  2-SMMA already captures volatility (redundant + lagging). ADX's internal True-Range untouched
  (ADX uses the standard Wilder formula, computes its own TR).
- **slot_win_rate fixed** — (1) was 15-min slots (96, ~29 trades each, noisy) → now **1-hour**
  (24 slots, ~116 each); (2) **look-ahead leakage FIXED** — slot table now built on the
  train-split only (was full data → past trades saw future outcomes).
- **Volume removed entirely (2026-06-23, like ATR).** vol_spike was already pruned; `volume` (imp 0.02)
  added to _MANUAL_PRUNE. Data showed volume is not a useful lever (entry + exit filters both failed,
  every rolling version hurt) — SL-hunting noise the model barely used. Model now has ZERO volume
  dependency. Retrain to apply; AUC expected unchanged. Reversible (remove "volume" from _MANUAL_PRUNE).
- **Ablation toggle added** (features.py): env `QGAI_ABLATE="f1,f2"` drops extra features for one test
  WFO without touching committed lists. Bats: Run_Ablate_TEST/FULL.bat (default removes H1-alignment).
- **23 features pruned** (67→45) — 13 zero-importance + 10 manual, data-backed via
  `feature_importance.csv` (now dumped each retrain by xgb_model.evaluate). Kept: hmm_state
  (regime selector), trade_direction, M30 ADX/DI (cross-model useful). AUC unchanged → safe.
- Prune sets `_ZERO_IMP` / `_MANUAL_PRUNE` in features.py (delete a name to restore).

## VALIDATION (backtest/ + run_wfo.py)
- **Walk-forward OOS (true): PF 1.55, avgR +0.139, 33/40 green weeks (82%), 9/10 green months.**
  Weekly retrain on past only, trade next week unseen. Edge is REAL (survives OOS) — the
  +279,000% backtest headline is compounding fantasy; judge by PF.
- In-sample vs OOS on real ML trades: PF 1.74 vs 1.68 — small drop = not overfit.
- **TRAIL finding** — exit-mix: FLIP carries profit (+148R); TRAIL net-negative (−7R, win 32%).
  By regime: Ranging −0.10 / Trending −0.05 (trail hurts) ; Volatile +0.05 (trail helps).
- **`--trail-mode` flag added** to backtest_replay + run_wfo: `line` (current) / `off` /
  `after1r` / `be` / `htf` / `regime`. Each has a `Run_WFO_*.bat` → separate results folder,
  resumable, comparable. Trail-variant WFOs ran 06-21 (wfo_results_after1r/be/fliponly/regime).

## ENVIRONMENT
- Python 3.12.10 + MetaTrader5, pandas, scipy, scikit-learn, xgboost, lightgbm, catboost,
  hmmlearn, river, joblib, openpyxl. (Dropped Python 3.14 — hmmlearn needed C++ build tools.)
- `.bat` launchers (Start/ + backtest/) use the full Python path since PATH isn't set.

## ⚠️ MUST REMEMBER — Stage 2 TP
When running the WINNER's realistic WFO (Stage 2, real 3%-equity volume sizing):
use **FAR TP** (`--tp-equity 0`, price-cap far) — NOT `--tp-equity 3`. Reason:
equity-TP% ÷ risk% = R-multiple, so equity-TP 3% with 3% risk = exactly **1R**
(tight TP) which kills the edge AND mismatches live (live has tp_equity_pct=0,
ratchet_tp_cap_pct=10 = far). Stage 1 sweep uses fixed-lot 0.01 so equity-TP 3%
rarely fires (≈ far, fine for the trail comparison) — the trap is only Stage 2.

## PENDING (next steps)
1. Run trail-variant WFOs (Stage 1, fixed-lot, clean R) → pick best trail mode → Stage 2 (winner, real 3% volume, FAR TP) → implement live.
2. Populate `MT5_PRIMARIES` (3 accounts) in config_mt5.py → activate failover (code wired, list empty).
3. Bug C — set live SYMBOL from the connected primary (matters once failover is on).
4. Restart bridge on DEMO, forward-test 3–7 days, then live.

## NOTE
- config_mt5.py (real passwords) is gitignored / untracked — keep it that way.
- The bash file-mount in Cowork serves stale copies intermittently; all edits were verified via
  the ground-truth file reader (a known artifact, not a code bug).
