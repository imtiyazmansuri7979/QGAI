# Memory

## 📖 DOCS — read first (Claude: every session)
**ALL docs now live in `docs/`.** `docs/QGAI_GUIDE.md` = the master hub / single entry point (doc-map,
strategy, rules, current config, FAQ, status pointers — bilingual EN+GU). Claude must open
`docs/QGAI_GUIDE.md` at the start of QGAI work, then the living docs it points to: `docs/WORKING_NOTES.md`
(current status) · `docs/TASKS.md` (priority tasks) · `docs/STRATEGY.md` · `docs/RULEBOOK.md` ·
`docs/SYSTEM_OVERVIEW.md` · `docs/FIXES_CHANGELOG4.md` · `docs/BUG_LOG.md` · `docs/FILTERS_MASTER.md` (master copy of ALL filters — keep current + change-log on every filter change) · `docs/PRE_BACKTEST_AUDIT.md` (mandatory pre-backtest audit checklist, run BEFORE starting any backtest) · `docs/BACKTEST_RESULT_AUDIT.md` (mandatory post-backtest audit checklist, run AFTER any backtest finishes — see rules below). Old docs → `docs/archive/`.
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
- **An A/B-test "decision" written in the docs is NOT the same as that decision being shipped in code — always verify the env var / config value is actually wired in before trusting past results.** (Imtiyaz, 2026-07-16 — found via `QGAI_REGIME_INRANGE`: 2026-07-12's full-year A/B test picked OFF and the docs recorded "keep `QGAI_REGIME_INRANGE=0`," but a full-repo grep showed that env var was never set anywhere except inside the A/B test's own bat — the code's default stayed ON.) **So:** whenever a doc says a flag/filter was "decided" ON or OFF, grep the actual codebase (config default + every `Start\*.bat` / live launch script) to confirm that value is really what runs — don't assume the doc and the code agree. Do this spot-check before quoting any backtest number that depends on that flag, and whenever reviewing/closing out an old A/B-test task.
  **⚠️ Verifying the gap is NOT license to close it on your own judgment.** Same day, same flag:
  Claude found the gap above AND a separate train/serve mismatch in the same feature, "fixed" both by
  flipping the code default — Imtiyaz reverted both same-day: the A/B result was real (OFF is
  marginally better) but he'd already decided the ~1.7R margin wasn't worth acting on, and the
  train/serve difference was already known and deliberately accepted when the feature was built.
  **Verify the fact, then STILL confirm with Imtiyaz before changing anything** — this is the same
  rule as the standing "confirm before settings changes" rule below, and finding a real discrepancy
  doesn't create an exception to it.
- **🔀 SIGNAL ≠ REAL TRADE — never conflate them (Imtiyaz, 2026-07-09, said repeatedly).** The **SIGNAL** = the model's per-M15-bar output (BUY/SELL/SKIP), logged to `engine/logs/signals_all.csv` (~98k rows, mostly `SKIP`/`NO_TRADE`); it is a *prediction* that changes every 15 min. The **REAL TRADE** = an actual MT5 position with a ticket (e.g. `#1550707233`), entry, vSL, lot — opened **once** and living across **many** signal bars (sometimes days) until vSL/flip/TP/manual closes it, managed independently of the current signal. A live position can be open & losing while the current signal shows SKIP — that's normal, not a contradiction. **So:** for "why didn't it exit / why is my position losing / what's open" → read the **TRADE side** (`bridge.log` ticket events: `Trade# BUY/SELL … #ticket`, `vSL`, `RATCHET`, `SL hit — closing`, `FLIP_CLOSE`, `STUCK`), NOT signals_all.csv; for "what's the prediction / why SKIP" → read the **SIGNAL side**. Never infer trade state from the signal or vice-versa; always label which one you're showing. (Evidence: #1550707233 opened 07-07 17:15 @4149.5, still open, while all 07-09 signals were SKIP; ticket appears 0× in signals_all.csv.)
- **TEST-RUN FIRST (Divyesh, 2026-07-02): before ANY long run (full WFO/backtest/training sweep), ALWAYS do a SHORT test run first for error checking** — e.g. WFO with `--weeks 2`, backtest on a few days — verify: no crashes, expected variant/config lines print, output files (.txt + .csv) appear in the right folder. Only then launch the full run. Build every new long-run .bat with a matching `*_TEST.bat` (or weeks-arg) from the start.
- **ETA/COUNTDOWN in every long run (Divyesh, 2026-07-02): every long-running script (WFO/backtest/sweep/training loop) must print, after each unit of work, the time that unit took + rolling average + estimated minutes remaining + expected finish time (ETA HH:MM)** — based on the time the first/recent units actually took. Implemented in `run_wfo.py` (per-week ⏱ line); every NEW long-run script must include the same from the start.
- **BEFORE running or trusting ANY test/backtest/WFO: do a DEEP bug-check, minimum 4 rounds.** Verify the
  backtest EXACTLY matches the LIVE config (entry SL, trailing line, flip, TP, buffer, filters, lot/risk,
  HTF/M15 parity, no-lookahead). Most "results" so far were invalidated by backtest≠live mismatches
  (tp-equity #G, WFO-cache #H, HTF trail/flip/entry-SL #F/#J). Don't quote a number until parity is checked.
- **PRE-BACKTEST AUDIT (Imtiyaz, 2026-07-16): before starting ANY new backtest/WFO/feature-sweep run, run the full 30-section checklist in `docs/PRE_BACKTEST_AUDIT.md`.** Covers: full file/component audit scope, data-source cleanliness, training/backtest period separation, feature-by-feature leakage audit, multi-timeframe candle availability, indicator calc correctness (SMMA/ADX/DI causal), label-creation audit, model-training audit + required metadata, inference-pipeline live-vs-backtest parity trace, entry/exit logic realism, position-sizing/risk audit, spread-commission-slippage cost profiles, session/time-filter audit, regime/HMM causality, directional-model audit, repainting test, lookahead code search, backtest-loop sequence audit, baseline/config freeze, runner/folder one-to-one mapping, output-file completeness, model-version logging, dry-run + manual trade verification, determinism/reproducibility test, failure-handling audit, performance-optimization safety, then the 30 pre-backtest red flags (any one present = do not start). Ends in the doc's exact Final Audit Report format (Audit Verdict / Critical Findings / Leakage Verdict / Repainting Verdict / Live-vs-Backtest Match / Data Quality / Reproducibility / Mandatory Fixes / Dry-Run Command / Final Permission). **If any CRITICAL finding is present, do not start the backtest.**
- **POST-BACKTEST AUDIT (Imtiyaz, 2026-07-16): after ANY backtest/WFO/feature-sweep/A-B test finishes, run the full checklist in `docs/BACKTEST_RESULT_AUDIT.md` before quoting the result or writing any KEEP/DROP/adopt decision anywhere.** Covers: leakage verdict, full metrics table, big-winner-dependency (remove top 1/3/5/10% trades — does it flip negative?), month/week consistency, BUY/SELL split, regime split, probability-bucket calibration, feature/filter contribution (Total R alone ≠ useful), sample-size check (never "Pass" on 10-20 trades), drawdown/risk, cost/slippage stress, robustness, overfitting-risk classification, equity-curve quality, then a Final Verdict in the doc's exact format (Overall Verdict / Strongest Evidence / Biggest Risks / Classification / Next Action — one of: fix-and-stop, repeat-3-month, proceed-to-1-year, fix-leakage-and-rerun). **Current validation stage across the whole engine is 3-month OOS only — do not recommend jumping to 1-year or WFO until the current stage explicitly PASSes per this checklist.** Every conclusion must cite an exact number, never a general impression.
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
