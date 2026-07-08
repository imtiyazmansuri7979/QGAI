# QGAI — Folder Review & Fix Report

**Reviewed by:** Claude (Cowork) · **Date:** 2026-06-22
**Scope:** Full `C:\QGAI` folder — structure, code state, bug status.
**Note:** Live-trading code. Test on a demo account before going live.
The bash/file-mount in this environment returns stale copies for some files;
all edits were verified through the authoritative file reader.

---

## 1. Folder structure
| Folder | Purpose |
|---|---|
| `engine/` | Core trading system — 39 Python files, ~11,500 lines |
| `fundamental_engine/` | Separate news / fundamental engine (own dashboard) |
| `backtest/` | WFO backtest runners (`Run_WFO_*.bat`) + ALL_RESULTS.txt |
| `bug_review/` | BUG_LOG.md + this report |
| `Start/` | Launcher .bat files (Start Trading, Update Data, Train, Scheduler, Dashboard) |
| `data/` | OHLC/ADX CSVs + trained models (`data/models/final/`) |
| `Economi calandar data/` | ForexFactory + broker economic calendars (3yr) |
| `engine_backup_0612/` | Old backup (12 Jun) |

## 2. Engine — main components
- **Live trading:** bridge_main, bridge_core, bridge_risk, bridge_session, bridge_multi (multi-account), bridge_ratchet (exit), bridge_dashboard
- **ML / AI:** inference, train, features, xgb_model, hmm_model, prediction_model, self_learning
- **Data:** mt5_data_updater, merge_data, build_indicators, trend_signal
- **Backtest:** backtest_replay, run_wfo, monte_carlo, backtest_exits_tp, exit_backtest_1year

## 3. Documentation present
BUG_LOG.md · FIXES_CHANGELOG (×3) · SESSION_NOTES.md · BACKTEST_SUMMARY.md · FEATURES.md · bug_audit_2026-06-14.txt · THIRD_PARTY_REVIEW_REFERENCE.txt
→ Many contributors / sessions have worked on this project.

## 4. Bug status

### Fixed in a prior Cowork review (2026-06-19, per BUG_LOG.md)
Stale feed after account-switch · no failover · bridge freeze after halt ·
secondaries not closed on session exits · vSL bar direction · feed cadence.

### Fixed THIS session (2026-06-22)
| Bug | Fix |
|---|---|
| Data symbol hardcoded `XAUUSD.pc` → data went 30h stale | read `MT5_SYMBOL` from config |
| STATS tab missing `</div>` → tab blank | added `</div>` |
| vSL ticker dot wrong (TP=0) | R-based dot position |
| Focus-card force-shown on any open trade (duplicate) | guarded + merged |
| Data-merge `keep='first'` → stale bars survived re-fetch | `keep='last'` (5 places) |
| Scheduler exact-minute match → tasks missed if loop delayed | 0–2 min catch-up window |
| **Bug E**: backtest_replay cp1252 emoji crash on file redirect | `PYTHONUTF8=1` in .bat |
| **Bug A** 🔴: daily-SL `check_closed` halt closed PRIMARY only | flatten secondaries on fresh halt (guarded) |
| **Bug B** 🟠: restart reset trade open_time → smart-exit 1h timer restarts | restore real open duration from MT5 epochs |
| Dashboard froze after trade close until next candle | write dashboard every 1s (not gated on open trades) |
| Dashboard refresh 2s → 1s (gold price every second) | refresh interval = 1000ms |
| TP equity-1.33R (too tight) → price-based 0.50% | config (validated +116R, best drawdown) |
| Fixed-$ params ($8 SL min, $2 breakeven) → % of price | config |

### Still OPEN / recommended
| # | Bug | Severity | Why open |
|---|---|---|---|
| C | failover backup on a different symbol → `SYMBOL` mismatch | 🟠 | Moot until `MT5_PRIMARIES` failover is configured |
| D | one shared MT5 terminal for all accounts (fragile) | 🟠 | Large refactor (subprocess per terminal) |

## 5. Key observations
1. **Failover code exists but is NOT configured.** `connect_primary()` + `MT5_PRIMARIES`
   failover is wired (bridge_core.connect → bridge_multi.connect_primary), but
   `config_mt5.py` has no `MT5_PRIMARIES` list → it falls back to the single primary
   (currently VantageDemo). **Action: populate `MT5_PRIMARIES` with 3 accounts.**
2. This session's changes build ON TOP of the prior session's (auto-reconnect,
   per-second feed resync) — complementary, no conflict.
3. Many uncommitted changes; git author = Anisa.

## 6. Recommendations (priority order)
1. Populate `MT5_PRIMARIES` (3 accounts) in `config_mt5.py` → activate real failover.
2. After configuring failover, fix Bug C (set live SYMBOL from the connected account).
3. Re-build data so the merge fix refreshes recent bars:
   `python mt5_data_updater.py` then `python merge_data.py`.
4. Restart bridge/scheduler, then `python sync_done.py` to save to GitHub.
5. **Test on demo before live** — TradeQuo secondary is a live account.
