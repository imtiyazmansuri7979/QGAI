# QGAI â€” Bug Log (Core Live-Trading Files)

**Reviewed by:** Claude (Cowork) Â· **Date:** 2026-06-19
**Scope:** Core live-trading files only â€” `bridge_*.py`, `scheduler.py`, `train.py`,
`mt5_data_updater.py`, `merge_data.py`, `inference.py`, `self_learning.py`,
`config.py`, `serve.py`, `dashboard.html`.
**Method:** Deep static review (multiple passes) + the live `bridge.log` capture.
**Note:** This environment could not run `python -m py_compile` against the live
files (a file-mount caching artifact returned stale/zero-filled copies). All
edits were verified through the ground-truth file reader instead. **Test on a
demo account before going live.**

Legend â€” Severity: ðŸ”´ High (money/safety) Â· ðŸŸ  Medium Â· ðŸŸ¡ Low/UX Â· Status: âœ… Fixed this session Â· ðŸ”¶ Open (recommended)

---

## Summary

| # | File(s) | Severity | Status | One-line |
|---|---------|----------|--------|----------|
| 1 | bridge_multi.py, bridge_core.py | ðŸ”´ | âœ… | Stale M15 feed after account-switch â†’ vSL never trailed, flip exit ~12 min late |
| 2 | bridge_multi.py, bridge_core.py, config | ðŸ”´ | âœ… | Single primary; password change / dropped link halts everything (no failover) |
| 3 | bridge_main.py | ðŸ”´ | âœ… | After 2nd-SL halt the window froze silent ("looks crashed") until manual restart |
| 4 | bridge_core.py, bridge_session.py | ðŸ”´ | âœ… | Session exits (daily SL / daily TP / 2nd-SL) closed PRIMARY only â€” secondaries left open |
| 5 | dashboard.html | ðŸŸ¡ | âœ… | vSL progress bar ran rightâ†’left; now leftâ†’right (vSL left, TP right) |
| 6 | bridge_main.py (feed cadence) | ðŸŸ  | âœ… | Feed now re-subscribed every second so copy_rates can't sit on a stale bar |
| A | bridge_session.py (check_closed) | ðŸ”´ | âœ… | Bar-loop DAILY-SL force-close also flattens primary only, not secondaries â€” fixed (see 2026-06-27 entry below) |
| B | bridge_core.py (recover_open_trades) | ðŸŸ  | âœ… | open_time reset to "now" on restart â†’ fixed: reconstructed from real open duration (`tick.time âˆ’ pos.time`), verified in code 2026-07-01, still used by dashboard elapsed-time display |
| C | bridge_constants.py | ðŸŸ  | ðŸ”¶ | SYMBOL taken from MT5_ACCOUNTS[0]; a failover primary on a different symbol won't match |
| D | bridge_multi.py (architecture) | ðŸŸ  | ðŸ”¶ | One shared MT5 terminal for all accounts â€” switching is inherently fragile |
| E | backtest_replay.py (non-core) | ðŸŸ¡ | âœ… | cp1252 emoji crash on redirect â€” fixed: UTF-8 stdout/stderr `TextIOWrapper` at lines 26-27, verified 2026-07-01 |
| L | bridge_main.py (RUNNING CONFIG print) | ðŸŸ¡ | âœ… | **Stale config display (4-round check, Anisa 2026-06-30):** startup printed `PARTIAL / TRAIL/BE / SMART-EXIT` + `TP cap 1.0%` / `maxrisk 1.2%` as ACTIVE â€” but partial/BE/trail/smart-exit were REMOVED in L7b (dead code) and the real config is regime-TP + HTF-forming SL. Misleading (a config-verify would trust dead features). FIXED: now prints `EXIT: pure ratchet (line+flip)` + `RATCHET: ... TP regime(Rng2/Trn1/Vol0.8%) | SL-line HTF H1 forming (max 2.5%) | buf 0.2%Â·line`. Display-only â€” no behavioral impact. (bridge_main.py:233-249) |
| N | bridge_core.py (recover_open_trades) | ðŸŸ  | ðŸ”¶ | vSL-recovery fallback uses a hardcoded $15 guess when a trade has no comment-embedded VSL/SL AND no broker SL â€” discards the REAL trailed vSL on every restart. Root problem now mostly moot after fix O (trade stays live-tracked, doesn't need restart-recovery); a real vSL-persistence fix is still open/lower-priority. |
| P | bridge_manual.py, bridge_main.py | HIGH | Fixed 2026-07-16 | Manual vSL shown on dashboard was not always enforced if ratchet-line read failed on that tick; last stored vSL now closes manual trade independently; manual-manager exceptions now log stack traces. See `docs/LIVE_SAFETY_NOTICE_2026-07-16_MANUAL_VSL.md`. |
| O | bridge_core.py (5 close-call sites) | ðŸŸ  | âœ… | `del virtual_trades[ticket]` ran unconditionally even when the close FAILED â€” a stuck trade silently dropped out of live monitoring after one failed attempt (contradicted its own "will keep retrying" alert). Fixed: `_close_position()` returns True/False; callers only delete on confirmed success. |

---

## Fixed this session

### 1. ðŸ”´ Stale M15 feed after account switching â†’ vSL frozen, flip exit late
**Files:** `bridge_multi.py`, `bridge_core.py`
**Evidence:** In `bridge.log`, trade #1450995243's `vSL` stayed at 4353.03 the whole
time and the opposite-flip exit fired at 19:57 for the **19:45** bar â€” a ~12-minute lag.
**Cause:** The system uses ONE MT5 terminal. On every entry/close, `execute_secondary_accounts()` /
`close_secondary_accounts()` call `mt5.shutdown()`, log into secondaries, then reconnect.
After reconnect `copy_rates_from_pos` kept returning **stale bars**, so the ratchet trail and
flip detection ran on old data.
**Fix:** Added `_warm_up_feed()` (symbol_select + a rates pull) and routed all (re)connects
through `connect_primary()`, which warms the feed on success. `bridge_core.connect()` now
delegates to it.

### 2. ðŸ”´ No primary failover (single point of failure)
**Files:** `bridge_multi.py`, `bridge_core.py`, `config_mt5_template.py`
**Cause:** `connect()` / `_reconnect_primary()` used one hard-coded primary. The live
`config_mt5.py` even carries a manual "TEMP: switched to VantageDemo because Neex connection
was lost" edit â€” exactly this failure.
**Fix:** New `connect_primary()` fails over across a `MT5_PRIMARIES` list (â‰¥1). Backward
compatible (falls back to the single primary if the list is absent). **Action for you:**
populate `MT5_PRIMARIES` with 3 accounts in `config_mt5.py` (template updated).

### 3. ðŸ”´ Bridge froze ("looks crashed") after the 2nd-SL halt
**File:** `bridge_main.py`
**Evidence:** After `21:00:14 Trade2 Equity SL`, no logs until a manual restart at 22:04 â€”
the 21:30/21:45/22:00 bars never appeared.
**Cause:** Same stale-feed issue; once halted there were no trades/SKIP logs and the bar
feed was frozen, so the window went silent.
**Fix:** Added a heartbeat (~60s) + per-second symbol re-subscribe in the quiet loop so the
bridge visibly stays ALIVE and the feed cannot stall.

### 4. ðŸ”´ Secondary accounts not flattened on session-level exits
**Files:** `bridge_core.py` (monitor), `bridge_session.py`
**Cause:** `check_daily_sl_intrabar`, `check_daily_tp_intrabar`, `check_trade2_equity_sl`
all close only primary positions via `_close_position()`. The normal vSL/flip/smart exits
DO call `close_secondary_accounts()`, but these session-level halts did not â€” leaving
secondary accounts (e.g. TradeQuo) with open, unmanaged positions after a halt.
**Fix:** `bridge_core.monitor_virtual_sl` now calls `close_secondary_accounts()` on each of
the three session exits â€” guarded to fire only on the **fresh transition** (the checks
return a sticky `True` every poll once halted, so an unguarded call would shutdown/reconnect
and re-close every second).

### 5. ðŸŸ¡ Dashboard vSL progress bar direction
**File:** `dashboard.html`
**Fix:** Flipped orientation â€” vSL on the left (0%), TP on the right (100%); profit now
moves the dot leftâ†’right. Updated gradient, markers, labels, dot-colour thresholds, and the
`posPct` formula.

### 6. ðŸŸ  Feed refresh cadence
**File:** `bridge_main.py`
**Fix:** `_resync_every = 1` â†’ the symbol is re-subscribed every second so `copy_rates`
never sits on a stale bar (per your "feed every second" request).

---

## Open / recommended (NOT changed â€” review & test first)

### A. ðŸ”´ check_closed() daily-SL force-close flattens primary only
**File:** `bridge_session.py` (~lines 207â€“217)
The bar-loop DAILY-SL path force-closes only `MAGIC` positions on the primary terminal; it
does not close secondaries. Same family as Bug #4 but on the `check_closed` path (runs in
`bridge_main`, not the monitor). **Recommend:** after `session.check_closed(...)` in
`bridge_main`, if `daily_sl_hit` flipped True this iteration, call
`bridge_multi.close_secondary_accounts()`.

### B. ðŸŸ  open_time reset on restart delays smart exit
**File:** `bridge_core.py` `recover_open_trades()` â†’ `bridge_risk.VirtualTrade.open_time`
`open_time` is set to "now" when a trade is reconstructed after a restart, so the
`SMART_EXIT_MIN_OPEN_H` (1h) timer restarts and a long-open trade looks fresh.
**Recommend:** reconstruct `open_time` from the entry deal's time.

### C. ðŸŸ  SYMBOL vs connected-primary mismatch
**File:** `bridge_constants.py` (line ~43)
`SYMBOL` is read from `MT5_ACCOUNTS[0]["symbol"]`, but with the new `MT5_PRIMARIES`
failover a backup primary may use a different broker symbol (e.g. `XAUUSDs`). If failover
switches to it, `SYMBOL` won't match and tick/rates calls will fail.
**Recommend:** after `connect_primary()` succeeds, set the live `SYMBOL` from the
account that actually connected.

### D. ðŸŸ  Single shared MT5 terminal (architecture) â€” reviewed 2026-07-01, KEPT FOR REFERENCE, not being fixed
**File:** `bridge_multi.py`
The MetaTrader5 Python library is process-wide singleton â€” only one account at a time. All
multi-account logic shutdown/reconnect-switches one terminal, which is inherently fragile
and is the root of Bugs #1/#3 (both already patched with `_warm_up_feed()` + `connect_primary()`
failover â€” the SYMPTOM is mitigated even though the underlying one-terminal design remains).
**Deep fix (not being done):** run one subprocess per terminal (one MT5 install + Python
process per account) and coordinate via files/DB. Larger refactor, real-money account
involved (VantageCentLive), high risk to touch live execution code for an architectural
concern with no active symptom.
**2026-07-01 â€” Imtiyaz confirmed intentional, no change wanted:** the design IS one primary
(decides) + secondary/slave accounts (mirror the primary's trades) â€” that's the intended
architecture, not an accident. Asked whether to (a) explain only, (b) do a small switching-
robustness mitigation, or (c) the full subprocess refactor â€” Imtiyaz confirmed "current is
fine as-is," no code change. First asked to remove this entry entirely, then asked to keep it
for future reference instead â€” **kept, staying parked/dormant, not an active fix target.**
Revisit only if a NEW live symptom traces back to this (e.g. another stale-feed incident the
warm-up fix doesn't cover).

### E. ðŸŸ¡ backtest_replay.py cp1252 crash (non-core)
Per `SESSION_NOTES.md`: the `âš¡` emoji on line ~208 crashes under cp1252 when stdout is
redirected. Outside the core live-trading scope, but worth the same UTF-8 stdout wrapper
already used in `scheduler.py`.

---

## 2026-06-23 review (recent changes â€” range-filter, TP=1.00, ablation)
**No critical bug found in the recent changes.** Verified:
- âœ… Range-phase filter integration correct â€” `in_range_phase` is in the inference result (inference.py:906)
  and the signal log, so the filter fires in BOTH bridge_main (`result.get`) and backtest_replay (`sig.get`).
- âœ… Config consistent for the M15 + TP=1.00 setup: `enable_ratchet_exit=True`, `ratchet_flip_exit=True`,
  `ratchet_htf_sl/flip=False`, `tp_equity_pct=0` â†’ price cap 1.00 used.
- âœ… No accidental `QGAI_ABLATE` env in any non-ablation bat. No leftover volume/ATR feature refs that break.

| # | File | Sev | Status | One-line |
|---|------|-----|--------|----------|
| F | backtest_replay.py vs bridge_core.py | ðŸŸ¡ | ðŸ”¶ | backtest_replay's HTF-SL is driven by `--stop-trail htf`, NOT the config `ratchet_htf_sl` the live bridge reads. Harmless now (both HTF-off), but if `ratchet_htf_sl=True` is set for live, a default backtest won't match unless `--stop-trail htf` is also passed. Make backtest config-aware if HTF is ever re-enabled. |

Known older OPEN bugs (Aâ€“E above) remain pre-existing.

---

## 2026-06-27 â€” ðŸ”´ WFO TP-bypass (validation bug â€” Imtiyaz flagged it earlier, Claude initially missed it)
| # | File | Sev | Status | One-line |
|---|------|-----|--------|----------|
| G | Run_WFO_*.bat â†’ backtest_replay.py | ðŸ”´ | âœ… | WFO passed `--tp-equity 3`; in backtest_replay `tp_equity_pct>0` runs the equity-TP path and **skips the price TP cap entirely**, and under fixed-lot 0.01 the equity-TP ($300/$10k) never fires â†’ **no TP cap acted** (global 1.0% AND regime both inert) â†’ global==regime WFO, and didn't match live (`tp_equity_pct=0` + price cap). **Fixed:** WFO bats now use `--tp-equity 0`. |

**How it surfaced:** Imtiyaz earlier noted WFO results were "all the same"; that was attributed to trail
modes being tied. The real/added cause was this TP-bypass â€” caught later by the regime-TP smoke test
(global == regime, +20.3R identical). Lesson: when two configs that SHOULD differ produce identical
results, treat it as a bug to trace, not an expected tie.
**Impact:** the historical "OOS PF 1.55" was a no-TP-cap flip/trail strategy, not today's live price-TP.
Re-run WFO with `--tp-equity 0` for a live-faithful number.

## 2026-06-27 â€” ðŸŸ  WFO stale-cache trap
| # | File | Sev | Status | One-line |
|---|------|-----|--------|----------|
| H | run_wfo.py | ðŸŸ  | âœ… (workaround) | WFO resume-cache keys ONLY on `week_*.json` existing (line ~248-252) â€” it ignores model version / `--tp-equity` / `--tp-regime` / relabel. So after retraining or changing flags, a re-run shows every week `CACHED` and silently REUSES old results. First full WFO after the relabel returned +143.9R â€” but `week_2025-09-01.json` mtime was 2026-06-20 (the OLD pre-relabel, `--tp-equity 3` run). |
**Fix/workaround:** before a fresh WFO, clear/rename the results-dir (or use a new `--results-dir`). Stale
`wfo_results/` moved to `_archive/wfo_results_STALE_preRelabel_tpEq3`. **Proper fix (TODO):** make run_wfo
write a `run_meta.json` (model timestamp + key flags) and auto-invalidate the cache when they change.
**Lesson (again):** all weeks `CACHED` + a number equal to an OLD baseline = stale, not a result. Check mtimes.

## 2026-06-27 â€” ðŸ”´ live_trades.csv schema drift â†’ corrupted CSV (FIXED)
| # | File | Sev | Status | One-line |
|---|------|-----|--------|----------|
| I | inference.py `_log_trade` | ðŸ”´ | âœ… | It did `row.update(feat_dict)` + `fieldnames=row.keys()`, dumping the whole feature vector and writing the header only once. As features changed (ATR/volume removed, 67â†’44 prune) the column count drifted (82/83/96/97/98/99) â†’ CSV unreadable by pandas â†’ live trade history lost. |
## 2026-06-27 â€” ðŸŸ  Entry SL: live uses H1 line, backtest uses M15 line (mismatch)
| # | File | Sev | Status | One-line |
|---|------|-----|--------|----------|
| J | bridge_core.py `execute()` vs backtest_replay.py | ðŸŸ  | ðŸ”¶ | With `ratchet_htf_sl=True`, live `execute()` sizes the ENTRY SL off the **H1 line** (wide â†’ small lot), but `backtest_replay` sizes the entry SL off the **M15 line** (`_buyL[i]`, tight â†’ big lot) and uses H1 only for the trailing stop. The design intent (changelog) says *"Entry stays 15-min; lot auto-shrinks"* â†’ entry should be M15. So the LIVE code contradicts both the intent AND the validated backtest. The +321R / PF 3.28 OOS was the M15-entry strategy; live runs a different (H1-entry) geometry â†’ live â‰  validated, different risk/lot per trade. |
**RESOLVED (2026-06-27) â€” Imtiyaz chose to make the BACKTEST match live (keep H1 entry).** Fixed in
`backtest_replay.py`: when HTF is active the ENTRY SL is now sized off the H1 line (M15 fallback) with the
wider `ratchet_htf_max_risk_pct` cap â€” matching live `execute()`.

## 2026-06-27 â€” ðŸ”´ Bug F RESOLVED + completed HTF parity (backtest now matches live HTF exactly)
**Root finding (Imtiyaz: "do all backtests use H1 HTF SL?"):** NO. The HTF in `backtest_replay` was driven by
`--stop-trail htf` (not the config), AND it was incomplete:
- The **WFO** (the +321R / PF 3.28 "validation") passed NO `--trail-mode` â†’ ran `stop-trail=line` (M15 trail +
  M15 flip) â€” it did NOT use HTF at all, while LIVE has `ratchet_htf_sl/flip=True`. So +321R was a DIFFERENT
  (M15) strategy than live. âŒ
- Even the explicit `--stop-trail htf` runs used H1 trail but **M15 flip** (`_flip[i]`) and **M15 entry SL** â€”
  only partial HTF.
**Fixes (all in `backtest_replay.py`):**
1. **Config-aware default** â€” if `--stop-trail` not given, TRAIL_MODE follows `CFG.filters.ratchet_htf_sl`
   (htf if on, else line). So the WFO + every backtest now uses HTF automatically = live.
2. **H1 flip** â€” compute `_flip_h1` and use it in htf mode (was M15 flip). Matches live `ratchet_htf_flip`.
3. **H1 entry SL** (Bug J) â€” entry SL off the H1 line + wider max-risk cap. Matches live `execute()`.
Now backtest HTF = live HTF (entry SL + trail + flip all H1).
**âš ï¸ CONSEQUENCE â€” ALL prior backtest numbers are STALE/invalid** (incl. the +321R WFO = M15). **Must
re-run** the WFO + any backtest, and **clear the results-dir first** (Bug H cache trap won't auto-invalidate).

## 2026-06-27 â€” Bug A FIXED + L8 (deposit/withdrawal-aware equity) DONE
- **Bug A ðŸ”´ â†’ âœ…** (was ðŸ”¶ open): `bridge_main` already calls `bridge_multi.close_secondary_accounts()` on the
  fresh daily-SL transition after `check_closed` (lines 328-339, guarded by `daily_sl_hit and not _was_halted`).
  Secondaries now flatten on the bar-loop daily-SL halt too. Verified present.
- **L8 âœ…:** `bridge_session._net_balance_flow_today()` sums MT5 `DEAL_TYPE_BALANCE` deals since day start
  (cached 30s); `check_daily_sl_intrabar` + `check_daily_tp_intrabar` now use **flow-adjusted equity**
  (`info.equity âˆ’ net_flow`) so a deposit can't distort the ratchet floor and a withdrawal can't FALSELY
  trip the daily halt. preload's day_open is already MAGIC-filtered (balance-safe). Lot sizing intentionally
  left on raw equity (deposit â†’ bigger lot is desired). Errors fall back to raw equity (safe). DEMO-verify.

## 2026-06-29 â€” ðŸ”´ L8 balance-flow used LOCAL time â†’ FALSE daily-SL halt on startup (Anisa flagged via live log, FIXED)
| # | File | Sev | Status | One-line |
|---|------|-----|--------|----------|
| L8-bug | bridge_session.py `_net_balance_flow_today` | ðŸ”´ | âœ… | Local-time from-date â†’ MT5 history returned the account's LIFETIME balance deposits as "today's flow" â†’ equity looked ~$906k smaller â†’ bridge halted for the whole day, ZERO trading. |
**Evidence (live log 2026-06-29 09:56):** `â›” DAILY RATCHET HIT! equity=$68,642.31 <= floor=$887,568.40`
while the account summary the same second showed VantageDemo **Eq=$974,907.14**. The check used
`info.equity âˆ’ _net_balance_flow_today()` = 974,907 âˆ’ **906,265** = 68,642. The $906,265 â‰ˆ the demo's
lifetime deposits, NOT today's flow.
**Cause:** the L8 method built the from-date from local `_dt.now()` (`_day_start_ts`), then
`mt5.history_deals_get(start, _dt.now())`. The PC clock was ~2.5h AHEAD of the UTC+3 broker (log shows
local 09:56 vs **Broker 07:26**), so the from-date sat in the server's FUTURE â†’ the query returned the
ENTIRE balance history. (The preload/check_closed paths were fine â€” they already used `broker_day_start_ts`;
the L8 method was the only one on local time.)
**Fix:** filter by the deal's SERVER timestamp `d.time >= broker_day_start_ts()` (query a wide
2000â†’now window, then keep only today's broker-day deals) + a **safety guard**: if `abs(flow) > 50% of
day_open_bal`, ignore it (â†’ 0) so a bad balance read can NEVER falsely trip the daily halt. Verified the
preload/floor math was otherwise correct (floor $887,568 from real day-open; raw equity $974,907 > floor â†’
no halt once flow is correct). `_day_start_ts` (line 51) is now vestigial. **Restart bridge to clear the halt.**

## 2026-06-27 â€” ðŸŸ  Bug K: WFO combine broke after the HTF fix (no ALL_OOS / no PF)
| # | File | Sev | Status | One-line |
|---|------|-----|--------|----------|
| K | run_wfo.py (single path ~308) | ðŸŸ  | âœ… | Copied the exact name `backtest_trades.csv` each week. After Bug F made the backtest output suffixed (`backtest_trades_st-htf.csv`), the copy matched nothing â†’ per-week `trades_*.csv` never written â†’ `ALL_OOS_trades.csv` combine produced nothing â†’ no PF / no $10k analysis (Run_WFO_Analyze fails). Found via the 4-round rule (my own fix's side-effect). |
**Fix:** copy via glob `backtest_trades*.csv` / `backtest_signals*.csv` (like the sweep path already did).
**âš ï¸ Consequence:** the global WFO that already ran lost its per-week trades (backtest overwrites each week,
only the last survives) â†’ its **summary R (+254.9R) is valid, but PF/exit-mix/$10k need a re-run**. The regime
WFO running now is on the OLD code â†’ it'll also miss the combine (summary still fine). Re-run the chosen config
ONCE after this fix to get ALL_OOS â†’ then Run_WFO_Analyze.

## 2026-06-27 (cont.) â€” live_trades.csv schema fix detail
**Fix:** `_log_trade` now writes a FIXED 8-col schema (`datetime,type,volume,label,pnl,win_prob,hmm_state,
in_range_phase`) via DictWriter `extrasaction='ignore', restval=''` â€” no feature dump, no drift. self_learning
recomputes features from OHLC, so nothing is lost. Existing corrupt file migrated (first-5 fields are positional
& consistent) â†’ 15 clean rows recovered; backup `live_trades.csv.bak_corrupt_20260627`. **Bridge restart needed**
for the writer change to take effect (existing file already clean).

## Files changed this session
- `engine/bridge_multi.py` â€” `connect_primary()`, `_primary_candidates()`, `_warm_up_feed()`, `_reconnect_primary()` delegate
- `engine/bridge_core.py` â€” `connect()` delegates; secondary-close on session exits (guarded)
- `engine/bridge_main.py` â€” heartbeat + per-second feed resync
- `engine/dashboard.html` â€” vSL bar orientation
- `engine/config_mt5_template.py` â€” `MT5_PRIMARIES` failover example
- `Start/` â€” launcher .bat files (1_Start_Trading, 2_Update_Data, 3_Train_Models, 4_Auto_Scheduler, 5_Dashboard)

---

## 2026-07-01 â€” Fresh bug-audit (Claude/Cowork, requested by Imtiyaz) â€” doc drift found + 1 new bug

**Method:** 4-round static check â€” Python syntax/null-byte scan (94 files, `engine`+`backtest`+`fundamental_engine`,
all clean, matches the independent Codex 2026-06-30 report), targeted re-read of `run_wfo.py`,
`backtest_replay.py`, `bridge_core.py`, `bridge_constants.py`, `bridge_manual.py`, `config.py`.

**Finding 1 â€” docs were stale, not the code.** This GUIDE/BUG_LOG/TASKS table said Bugs B and E were still
open (ðŸ”¶). Code check shows both are actually fixed already (B: `bridge_core.py:649-654`, explicit "Bug B fix"
comment; E: `backtest_replay.py:26-27`, UTF-8 `TextIOWrapper`). Corrected the tables above. Bug C confirmed
**still genuinely open** (not "N/A" as one TASKS.md summary row claimed) â€” `SYMBOL` in `bridge_constants.py:43`
is set once at import from `MT5_ACCOUNTS[0]` and never refreshed after `connect_primary()` fails over; dormant
only because `MT5_PRIMARIES` isn't populated yet.

**Finding 2 â€” new bug M (ðŸŸ , `engine/run_wfo.py`).** `--trail-mode` argparse default is `"line"`; the command
builder only forwards `--stop-trail` to `backtest_replay.py` `if args.trail_mode != "line"`. Since Bug F's fix
made `backtest_replay.py` fall back to a **config-aware** default when `--stop-trail` is omitted (`"htf"` if
live `ratchet_htf_sl=True`, else `"line"`), NOT forwarding the flag no longer means "run literal M15 line
mode" â€” it means "run whatever the live config says," which today is HTF. So `run_wfo.py --trail-mode line`
(the default, or typed explicitly) silently produces an HTF backtest while claiming/labelling it "line."
**Impact today: none** â€” no production `.bat` (`Run_WFO_FULL`, `Run_WFO_TPREGIME`, `Run_WFO_TEST`,
`Run_Buffer_Sweep`, etc.) ever passes `--trail-mode`, so they all got the config-aware HTF default anyway,
which is what you want (matches live). The risk was latent: the day someone deliberately wanted a genuine
forced-line-mode comparison run, they'd have silently gotten HTF results mislabeled as line, no warning.
**âœ… FIXED 2026-07-01 (later, same day):** changed the argparse default from `"line"` to `None` and the
forward guard from `if args.trail_mode != "line":` to `if args.trail_mode is not None:` â€” no flag now
correctly means "follow `backtest_replay.py`'s own config-aware default" (same htf result as before, now
by design not accident), and an explicit `--trail-mode line` genuinely forces literal M15-line mode.
`py_compile` clean; confirmed no other reference to `args.trail_mode` in the file.

**Finding 3 â€” live config changed today, docs hadn't caught up.** `config.py` `ratchet_buf_pct` was moved
`0.20â†’0.15` today (comment dated 2026-07-01, backed by `backtest/results/bufsweep/buf_0.*.txt` from the
2026-06-30 sweep: 0.15 gave PF 3.87 / +430.70% / DD 2.9%, best balance of the 5 tested). `QGAI_GUIDE.md` Â§4
still showed 0.20 and `TASKS.md` still listed the buffer sweep (L5) as not-started. **Fixed:** GUIDE Â§4 updated,
L5 moved to DONE in TASKS.md. Note the sweep was GLOBAL only â€” a regime-wise (Ranging/Trending/Volatile)
buffer breakdown is still not done if that's wanted later.

**No other issues found.** No syntax errors, no null-byte corruption (incl. `bridge_manual.py`, which had
mount-write corruption twice before â€” currently clean), config.py values otherwise consistent with what the
docs describe.

---

## 2026-07-01 (later) â€” ðŸ”´ LIVE INCIDENT: AutoTrading disabled â†’ vSL close failed (retcode 10027) + N â€” win_prob frozen ~75 min

**Trigger:** Imtiyaz pasted the live `bridge_main.py` console log after start; asked why WinProb had been
stuck at 27% for the last hour.

### ðŸ”´ URGENT â€” close failed, retcode 10027 (both primary + secondary)
```
ðŸ›‘ #1519547791 Virtual SL hit @ 3983.22 â€” closing!
âŒ Close failed #1519547791: 10027
âŒ [multi] VantageCentLive #370630636 close failed: 10027
```
Primary = VantageDemo #25334572 (demo, 15.58 lot synthetic size â€” fine, demo). Secondary =
**VantageCentLive #29453256, which is REAL money** (per TASKS.md L13/config) â€” its mirrored leg ALSO failed
to close with the same code. **MT5 retcode 10027 = `TRADE_RETCODE_CLIENT_DISABLES_AT` â€” "AutoTrading disabled
by the client terminal."** The Python bridge can read prices/positions but the MT5 terminal app itself has
AutoTrading toggled OFF (or algo-trading isn't permitted for that connection), so every close/open order the
bridge sends is rejected. **Action for Imtiyaz: open the MT5 terminal window and enable AutoTrading (toolbar
button / Ctrl+E) immediately** â€” until then, any vSL/flip/TP exit the bot decides on will fail silently at the
broker, i.e. **stops are not actually protective** even though the bridge logic is correct. Recommend also
adding a bridge-side ALERT (not just a log line) when a close fails with 10027/10018/etc., since right now a
failed close only prints `[ERROR]` and moves on â€” easy to miss in a scrolling console.

### ðŸŸ  New: win_prob frozen 12:15â†’13:30 (75+ min) â€” stale feature cache in inference.py
**Evidence (`logs/signals_all.csv`):** `win_prob`, `state_prob`, `dir_prob`, `big_win_prob`, and `hmm_state`
were **bit-identical** (0.2699 / 0.3103 / 0.303 / 0.611 / Trending) across 6 consecutive M15 bars
(12:15â†’13:30) while `price` and the OB-distance columns kept moving normally (those are computed from LIVE
price directly, not from the cached `self.ohlc_df`/features).
**Root cause (inference.py `get_signal()`, lines ~360-399):** the live-OHLC merge only re-engineers
`self.ohlc_df` `if len(_merged) != _prev_len or _new_last != _last_dt`. If that guard evaluates falsely-equal,
or the merge/re-engineer throws, `self.ohlc_df` silently stays on the OLD data â€” and any exception is caught
by a bare `except Exception as _me: print(...)` (a plain `print`, NOT `log.error`), so it does **not** appear
in `bridge.log`'s `[INFO]/[WARNING]/[ERROR]` lines â€” only in raw console stdout, easy to miss (and this
console already shows mojibake/encoding issues on emoji output). Since `compute_features()` reads off
`self.ohlc_df`/`self.adx_df` (frozen) rather than the fresh `ohlc_update` directly, every model-facing feature
â€” and therefore `win_prob` â€” froze at whatever it was computed from at ~12:00-12:15, while log-only columns
computed straight from the fresh tick/bar (price, OB distance = fresh_price âˆ’ frozen_OB_level) kept moving,
creating the illusion that "data looks live" while the model was actually blind to the last ~5 candles.
**Immediate fix:** restart `1_Start_Trading.bat` â€” that resets `self.ohlc_df` from a fresh pull and clears the
freeze. **Root-cause fix (not yet applied):** in `inference.py`'s merge block, change the silent
`except Exception as _me: print(...)` to `log.error(...)` so a merge failure is visible in `bridge.log` going
forward; consider also logging a warning if `self.ohlc_df`'s last timestamp hasn't advanced for 2+ consecutive
bars, so a frozen feed is caught within 30 minutes instead of discovered by a human noticing an unchanged %.
**Status:** âœ… **FIXED 2026-07-01** (bridge stopped, edited safely). `inference.py` `get_signal()`'s OHLC-merge
block now: (1) routes the merge-failure `except` through `logging.getLogger("QGAI").error(...)` as well as
`print()`, so a failure is captured in `bridge.log` going forward; (2) tracks `self._ohlc_stale_bars` and
alarms after 2 consecutive bars with no new candle merged.

**Follow-up bug in the fix itself (caught immediately on restart, same session):** the first version fired
**100 false alarms in under 1 second** right after restart, during `_overnight_replay()` â€” that function
(and `_pre_pop_dashboard()`) intentionally passes the SAME fetched `live_ohlc`/`live_adx` snapshot across many
`get_signal()` calls (looping only the `timestamp` arg over up to 50 historical bars Ã— BUY+SELL = 100 calls) â€”
correct, intentional replay behavior, not staleness. The naive counter couldn't tell that apart from a real
live freeze. **Fixed:** added `self._last_seen_upd_ts` â€” tracks the incoming `ohlc_update`'s own last
timestamp across calls; the staleness tracker now only evaluates when the CALLER brought genuinely new data
(different from last call), so replay/backfill loops (same object reused) are silently skipped, while the
live per-bar loop (fresh MT5 pull every bar) is still checked correctly. Bonus: this also fixes the original
version double-counting BUY+SELL as 2 bars instead of 1 within the same live bar. Verified via direct file
read (ground-truth) â€” **the bash sandbox mount was serving a stale cached copy of `inference.py` (old
size/mtime, pre-dating this session's edits) and could not be used to `py_compile`-check this round**, a
known project quirk (see CLAUDE.md: "bash mount can serve stale/truncated copies"). Manually verified the
edit's structure/indentation via Read instead. **Needs another bridge restart to load** â€” not yet
live-verified end to end.

### ðŸŸ¡ Mojibake emoji in console (`Ã°Å¸â€™â€œ` instead of `ðŸ’“` etc.) â€” FIXED (bat-level)
**Cause:** `Start\1_Start_Trading.bat` (and `2_Update_Data`, `3_Train_Models`, `4_Auto_Scheduler`,
`5_Dashboard`) never set `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1`, unlike every backtest `.bat` and
`Start\6_Shadow_Ledger.bat` / `7_Refresh_Chart.bat` (which already had them). Without it, Python's stdout on
Windows falls back to the console's legacy codepage (cp1252/850), so any emoji `logging`/`print` output gets
mangled. This is the SAME class of issue as Bug E, just never extended to the live-trading Start bats â€” a
long-standing gap, not something introduced today. **Display-only** â€” never affected trading logic, prices,
or decisions. **Fixed 2026-07-01:** added `set "PYTHONIOENCODING=utf-8"` + `set "PYTHONUTF8=1"` to all 5
Start bats. Takes effect on the NEXT restart of each (the currently-running bridge process is unaffected
until restarted).

### Codex-mistake check (Imtiyaz asked, 2026-07-01)
Files with a today's-date mtime (`bridge_main.py`, `bridge_data.py`, `chart_data.py`, `chart_live_ohlc.py`,
`config.py`, `backtest_replay.py`, `shadow_ledger.py`, `backtest/README.md`) were checked: all still
py_compile clean, no null bytes, and no unexplained/undated code changes found in them beyond the ALREADY
documented + verified `ratchet_buf_pct` buffer change (see the 2026-07-01 audit entry above). The win_prob
freeze traces to `inference.py` (not touched today) and the 10027 close failure is an MT5 **terminal**
AutoTrading toggle, not a code change â€” neither looks Codex-caused. No other suspicious edits found.

---

## 2026-07-01 (even later) â€” vSL-recovery fallback bug + a real "retry loop" bug found alongside it

### N. ðŸŸ  `recover_open_trades()` fallback reconstructs vSL as a hardcoded $15 guess, discarding the REAL value
**File:** `bridge_core.py` (`recover_open_trades()`, ~line 620)
**Trigger:** Imtiyaz flagged leftover trade #1519547791's vSL showing 4016.42 while the live H1 ratchet
line was ~3975 â€” "this issue I raise."
**Evidence (`bridge.log`):** trade opened 2026-06-30 22:15 with REAL vSL 4012.35, trailed favorably once
to **4015.11** at 22:30 (price briefly ran up), then never trailed again (price stayed under entry all
day). Every restart since (08:30, 09:25, 15:21 on 07-01) logged
`no SL comment â€” reconstructed vSL=$4016.42` and recovered with that WRONG value.
**Cause:** trade comments are now a clean brand-tag by design (no embedded `VSL=`/`SL=`), so the recovery
regex always misses â†’ falls to the fallback branch. This trade also has no broker-side SL (pure-virtual
design) â†’ `broker_sl_dist=0` â†’ hardcoded literal `sl_dist = 15.0` is used â†’ `entry(4031.42) âˆ’ 15.0 =
4016.42`, an exact match confirming the bug (not a coincidence).
**Impact:** every restart threw away the real, trailed vSL (4015.11) and replaced it with a disconnected
$15-from-entry placeholder. In this case the fake value happened to be slightly MORE protective ($1.31
tighter) than the real one, so no loss resulted â€” but the mechanism is fundamentally wrong and could go
either way on a different trade.
**Not yet fixed directly** â€” superseded by fix O below, which makes the underlying problem (repeated
restarts losing state) mostly moot: a stuck/failing-close trade now stays tracked live instead of needing
a restart to "recover" it at all. A real persistence-based fix (save the true vSL to a small state file on
every trail update) is still a good idea but lower priority now.

### O. ðŸŸ  `_close_position()` callers dropped a trade from `virtual_trades` on ANY close attempt, even failure
**File:** `bridge_core.py` (5 call sites: flip-close, struct-H1-exit, vSL-hit CLOSE, SMART_CLOSE, reversal-exit)
**Cause:** all 5 sites did `_close_position(ticket)` then unconditionally `del self.virtual_trades[ticket]`
â€” regardless of whether the close actually succeeded. The very own alert text next to this code
(`"Bot will keep retrying every check"`, from the earlier stuck-trade-protect feature) was FALSE: once a
close failed once, the ticket silently vanished from live monitoring for the rest of that session. It only
ever got "recovered" again â€” with bug N's lossy fallback vSL â€” on the NEXT bridge restart.
**Found while investigating bug N** â€” the connection: this is *why* #1519547791 needed `recover_open_trades()`
to run 3 times today in the first place (it wasn't being actively monitored between restarts).
**FIXED:** `_close_position()` now returns `True` (confirmed closed / already gone) or `False` (still open).
All 5 call sites only delete the `VirtualTrade` on `True`; on `False` they leave it tracked so the SAME
close/vSL check fires again next tick (2s), matching what the alert text always claimed. Also threaded the
trade's REAL `virtual_sl` into `_close_position(ticket, vsl=...)` so the (new, still-disabled) graduated
stuck-hedge can compute real slippage without needing bug N's fallback guess at all.

### P. Graduated stuck-trade excess-hedge (feature, not a bug) â€” `leftover_excess_hedge_enabled`, OFF by default
Imtiyaz's idea, built in `bridge_session._stuck_risk_hedge()`: instead of `_place_stuck_hedge()`'s
immediate FULL-lot freeze the moment a close fails 3x, let risk stretch from `risk_pct` (3%) to
`leftover_risk_cap_pct` (6%) and hedge only the excess lot once real slippage (price past the trade's
actual `virtual_sl`, via the bug-O fix above) exceeds that stretched budget â€” tops up incrementally.
Takes priority over the old full-lot hedge when enabled. Not yet enabled or fire-tested.

### Q. bridge_main.py had ~680 pre-existing mojibake log-message glyphs â€” fixed on request, glyph-by-glyph
Not a NEW bug from today â€” while fixing the one heart-emoji (ðŸ’“) Imtiyaz pointed at (his working theory:
"only [the one] Codex set"), a full-file scan found the SAME double UTF-8â†’CP1252â†’UTF-8 corruption pattern
in ~680 more places (every emoji/dash/bullet in the file's `log.info`/`print` strings). First pass fixed
ALL of them file-wide; **Imtiyaz explicitly said this went too far ("other don't want to remove") and asked
for a revert** â€” reverted the blanket sweep, then re-applied fixes ONE GLYPH AT A TIME as he pointed each
one out in subsequent messages (ðŸ’“âš™ï¸â”€â”€ðŸ‘ðŸ“‹ðŸ“ŠðŸš€ðŸ’°âœ…â€”Â·). Process note for next time: don't blanket-fix a whole
file's cosmetic issues without confirming scope first, even when the root cause is identical everywhere â€”
ask per-glyph or get explicit "fix everything" confirmation first.

### R. backtest_replay.py: dead checkpoint code + unbuffered console (both fixed)
`_checkpoint_pkl` was defined but never read/written anywhere â€” a stopped/interrupted backtest lost ALL
progress, no resume was actually possible despite the variable's name suggesting otherwise. Built real
save (every 500 bars + on Ctrl+C, config-signature-gated so it can never resume a mismatched run) + load +
auto-delete-on-success. Separately, `stdout`/`stderr` weren't line-buffered so progress prints sat
unflushed, making a long run look frozen â€” fixed with `line_buffering=True` + `flush=True` + tighter
100-bar progress interval + `PYTHONUNBUFFERED=1` in the two `Run_Live_Buffer_015_CSV*.bat` files.
âš ï¸ Could not run `py_compile` against the edited file this session â€” bash sandbox mount was stuck serving
a 3+ hour stale cached copy (confirmed via `stat` mtime, independent of the file's actual saved content
per the `Read`/`Edit` tools). Verified via full manual line-by-line review instead. Spot-check on next run.

### P. HIGH - Manual dashboard vSL visible but not enforced on every tick
**Files:** `engine/bridge_manual.py`, `engine/bridge_main.py`  
**Reported:** 2026-07-16 by Imtiyaz.  
**Evidence:** manual BUY entry `4041.43`, dashboard vSL `4022.08`; bridge heartbeat showed price `4016.61` but no `COMBINED vSL hit` close log appeared.  
**Root cause:** manual vSL enforcement was inside the fresh ratchet-line branch. If ratchet line was unavailable on that tick, old displayed vSL remained visible but was not checked.  
**Fix:** enforce previous stored vSL before recalculating fresh line; once a vSL exists it remains active every tick. Also log manual-manager exceptions instead of silently swallowing them.  
**Verification:** `python -m py_compile engine/bridge_manual.py engine/bridge_main.py` passed.  
**Operator action:** restart bridge to load new code. Full note: `docs/LIVE_SAFETY_NOTICE_2026-07-16_MANUAL_VSL.md`.

