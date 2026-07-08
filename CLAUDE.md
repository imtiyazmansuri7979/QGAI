# Memory

## 📖 DOCS — read first (Claude: every session)
**ALL docs now live in `docs/`.** `docs/QGAI_GUIDE.md` = the master hub / single entry point (doc-map,
strategy, rules, current config, FAQ, status pointers — bilingual EN+GU). Claude must open
`docs/QGAI_GUIDE.md` at the start of QGAI work, then the living docs it points to: `docs/WORKING_NOTES.md`
(current status) · `docs/TASKS.md` (priority tasks) · `docs/STRATEGY.md` · `docs/RULEBOOK.md` ·
`docs/SYSTEM_OVERVIEW.md` · `docs/FIXES_CHANGELOG4.md` · `docs/BUG_LOG.md` · `docs/FILTERS_MASTER.md` (master copy of ALL filters — keep current + change-log on every filter change). Old docs → `docs/archive/`.
Backtest bat index → `backtest/README.md`. Keep `docs/QGAI_GUIDE.md` §4 (config) + §5 (status) current.

## ⚠️ WORKING RULES (Claude — always)
- **🗣️ ALWAYS reply in Gujarati (ગુજરાતી) — every single response, no exceptions, from the very first
  message of every session.** Technical terms / config keys / code / file names / numbers stay in English
  (Latin script) inside the Gujarati sentence. (Imtiyaz, 2026-07-01 — this was already in Preferences below
  but wasn't being followed consistently; moved up here so it's never missed.)
- **If Imtiyaz raises a flag / concern / "something looks off", treat it as a SERIOUS issue.** Do NOT
  explain it away or dismiss it. Investigate properly: read ALL relevant files (code + bats + config +
  results) and trace the actual cause before concluding. (Precedent: the WFO "results all the same" — flagged
  by Imtiyaz, initially dismissed as "trail tied", real cause was the `--tp-equity 3` TP-bypass. BUG_LOG #G.)
- **When two configs that SHOULD differ produce identical results, that's a bug to trace, not an expected tie.**
- **TEST-RUN FIRST (Divyesh, 2026-07-02): before ANY long run (full WFO/backtest/training sweep), ALWAYS do a SHORT test run first for error checking** — e.g. WFO with `--weeks 2`, backtest on a few days — verify: no crashes, expected variant/config lines print, output files (.txt + .csv) appear in the right folder. Only then launch the full run. Build every new long-run .bat with a matching `*_TEST.bat` (or weeks-arg) from the start.
- **ETA/COUNTDOWN in every long run (Divyesh, 2026-07-02): every long-running script (WFO/backtest/sweep/training loop) must print, after each unit of work, the time that unit took + rolling average + estimated minutes remaining + expected finish time (ETA HH:MM)** — based on the time the first/recent units actually took. Implemented in `run_wfo.py` (per-week ⏱ line); every NEW long-run script must include the same from the start.
- **BEFORE running or trusting ANY test/backtest/WFO: do a DEEP bug-check, minimum 4 rounds.** Verify the
  backtest EXACTLY matches the LIVE config (entry SL, trailing line, flip, TP, buffer, filters, lot/risk,
  HTF/M15 parity, no-lookahead). Most "results" so far were invalidated by backtest≠live mismatches
  (tp-equity #G, WFO-cache #H, HTF trail/flip/entry-SL #F/#J). Don't quote a number until parity is checked.
- Own mistakes plainly; verify against the ground-truth file reader (bash mount can serve stale/truncated copies).
- **ALWAYS update `docs/TASKS.md` the moment a task/sub-task is DONE — and MOVE the row from the REMAINING table INTO the DONE table** (mark done + date + result; don't just strike-through in REMAINING). REMAINING = only genuinely-pending work, at all times. Do this every time, automatically. (Anisa, 2026-06-29)
- **`docs/FILTERS_MASTER.md` = the MASTER COPY of every entry/exit/risk filter. Whenever ANY filter is added, removed, toggled (ON/OFF), or retuned — in code OR config — you MUST, in the SAME change: (1) update that filter's current value/status in the FILTERS_MASTER.md table, and (2) append a dated row to its §CHANGE LOG (filter · old→new · WHY · by whom). Never change a filter without updating both. This keeps one source of truth so nothing is forgotten.** (Imtiyaz, 2026-07-03)

## Me
Imtiyaz Mansuri. QGAI v2 — live algorithmic gold (XAUUSD) M15 auto-trading system on MetaTrader5. Folder: C:\QGAI.

## People
| Who | Role |
|-----|------|
| **Imtiyaz** | Imtiyaz Mansuri — owner/operator (imtiyazmansuri@gmail.com) |
| **Anisa** | Anisa — collaborator on QGAI, shared PC via Cowork (anisaimtiyazmansuri@gmail.com) |

## Projects
| Name | What |
|------|------|
| **QGAI / QGAI v2** | Live XAUUSD M15 ML trading bridge (MT5). Engine in C:\QGAI\engine. |

## Preferences
- **Language: reply in Gujarati (ગુજરાતી) for ALL answers.** Technical terms / config keys / code / file names stay in English (Latin script).
- Be concise and direct; minimal verbosity.
- Always test on DEMO before live. Risk kept at 3% (per user choice).
- config_mt5.py holds live credentials — gitignored, never commit/expose.
- **Deliverables: reports/comparisons/analyses in ONE format only — Markdown (.md).** (Divyesh, 2026-07-02, evening — REPLACES the earlier same-day "all three formats" rule; making .md+.xlsx+.docx every time didn't make sense.) Only produce .xlsx/.docx if explicitly asked for that specific document.
- **Documentation: NO new document per change. ALL changes/updates go into the 3 living reference docs only** (Divyesh, 2026-07-02): (1) `docs/QGAI_GUIDE.md` = what the system IS now (keep §4 config + §5 status current), (2) `docs/FIXES_CHANGELOG4.md` = WHAT CHANGED (append a dated entry for every change), (3) `docs/TASKS.md` = pending/done. A standalone analysis file only when explicitly asked — and then summarize + link it from the CHANGELOG.
- **Backtest/WFO outputs — ONE FOLDER PER RUN (Divyesh, 2026-07-02): EVERY backtest/WFO — whether run via a .bat OR directly with python — must ALSO save its results as CSV** (summary + per-week where applicable) **in the SAME results folder** as the run's other outputs (report .txt, trades/signals CSVs). **Analysis/report DOCUMENTS for that run (.md/.xlsx/.docx/.csv) also go in that SAME folder** — everything for one run lives together in one folder. Implemented: `run_wfo.py` → `_WFO_SUMMARY.csv`; `backtest_replay.py` → `backtest_summary*.csv` (both 2026-07-02). New backtest scripts must follow this rule.
- **PRIMARY OBJECTIVE = PROFIT. Do NOT block/skip profitable trades.** Any filter/change (e.g. flip-fix hysteresis) must be judged on TOTAL R / $ (profit), not just flip-count or PF/WR. If a change reduces total profit, it is NOT acceptable even if it looks "cleaner". Prefer changes that CUT losers without cutting winners. (Divyesh, 2026-07-02)
