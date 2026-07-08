# Bug Findings By Codex - 2026-06-30

Report-only audit. No fixes were applied during this report pass.

## Scope Checked

- Project folder: `C:\QGAI`
- Python syntax parse: `engine`, `backtest`, `fundamental_engine`
- Null-byte corruption scan for `.py` files
- Existing bug/task/result documentation
- WFO/backtest configuration risk areas

## Summary

- Python files checked: 93
- Syntax parse result: OK
- Current `.py` null bytes found: 0
- Git repository: not detected at `C:\QGAI`

## Findings

| Severity | Finding | File |
|---|---|---|
| High | WFO trail-mode pass-through risk: `--trail-mode line` is the default, but `--stop-trail line` is not passed to `backtest_replay.py`. If live config defaults to HTF, a run intended as line-mode can silently use HTF behavior. | `engine/run_wfo.py` |
| High | WFO cache can reuse stale weekly results. Cache is based on `week_*.json` existence and does not appear to invalidate automatically when model/config/flags change. | `engine/run_wfo.py` |
| High | Archived WFO/backtest results marked WRONG/STALE/DO_NOT_USE can be accidentally quoted if not clearly avoided. | `backtest/results/_archive/...` |
| Medium | Documentation is inconsistent: older guide sections still list issues as open while newer task notes mark several as resolved. This can cause confusion about current truth. | `docs/QGAI_GUIDE.md`, `docs/TASKS.md` |
| Medium | Windows console Unicode output crash risk is documented. Scripts printing emoji/arrows can fail in non-UTF-8 console contexts. | `docs/TASKS.md`, backtest scripts |
| Medium | Multi-account MT5 design remains fragile because one shared MT5 terminal/session is used for multiple accounts. | `docs/TASKS.md` |

## Most Important Risk

The highest practical risk is WFO/backtest mismatch.

In `engine/run_wfo.py`, the user-facing trail mode can say `line`, but the command may omit `--stop-trail line`. Since `backtest_replay.py` can default to live config, this may produce HTF-style results while the run looks like line-mode. That can make validation numbers misleading.

## Invalid Result Warning

Do not rely on archived results under:

- `backtest/results/_archive/WRONG_WFO_tpEq3_DO_NOT_USE/`
- `backtest/results/_archive/WRONG_preHTFfix_20260627/`

Those folders are explicitly marked as invalid/stale by existing project docs.

## Recommended Next Checks

1. Confirm desired WFO trail behavior: `line` vs `htf`.
2. Before future WFO reruns, clear or isolate result folders to avoid stale cache reuse.
3. Update docs so `QGAI_GUIDE.md`, `TASKS.md`, and `BUG_LOG.md` agree on which bugs are open/resolved.
4. For Windows scripts, prefer UTF-8 wrapper or ASCII-only console output.

## Note

This file is a report only. No code fixes are included here.
