# QGAI — MASTER GUIDE (START HERE) · માસ્ટર ગાઈડ (અહીંથી શરૂ કરો)

**Updated:** 2026-07-01 · The single entry point. Read this first, then jump to the living doc you need.
**આ એક જ entry point છે. પહેલા આ વાંચો, પછી જરૂરી living doc પર જાઓ.**

## 🎯 PROJECT VISION (the goal everything serves)
**An honest, fully-visible, downtime-proof signal system** where Imtiyaz can: see EVERY signal and its
0.01-lot performance (terminal on or off); keep the SYSTEM's own track record (signal provider) SEPARATE
from the REAL account (receiver); never miss a signal to downtime (gap-backfill + "trade the last signal?"
prompt + VPS); view confidence breakdowns (month/week/day/hour, BUY/SELL/SKIP separate); and trade at 3%
risk only on a VALIDATED edge — on a clean, reliable foundation (organised docs/code, fixed logs,
deposit/withdrawal-aware equity, no stale labels). Backtest = potential; Live signals = what was emitted;
Real account = what was executed — always kept distinct.
**ગુજરાતી:** એક પ્રામાણિક, fully-visible, downtime-proof signal system — દરેક signal અને એની 0.01-lot
performance દેખાય; system ની provider track record real account થી અલગ; downtime છતાં signal miss ન થાય;
month/week/day/hour confidence breakdown; validated edge પર જ 3% risk; clean reliable foundation.

---

> Rule for Claude & Imtiyaz: this GUIDE is the index. Volatile detail lives in the linked docs
> (TASKS / WORKING_NOTES / etc.) — don't duplicate it here, just point to it. Keeps everything in sync.
> **નિયમ:** આ GUIDE = index. બદલાતી વિગત linked docs માં જ રહે — અહીં duplicate ન કરો, ફક્ત link કરો.

---

## 0 · DOC MAP — what is where / કઈ વસ્તુ ક્યાં છે

**EN — Active docs (the live set, keep these current):**

| Doc | Purpose | Read when |
|-----|---------|-----------|
| `QGAI_GUIDE.md` | **THIS** — index + essentials + pointers | always first |
| `WORKING_NOTES.md` | Current status / "where we are right now" / handoff | start of every session |
| `TASKS.md` | Prioritised task list (P1→P3 + LATER) | to know what to do next |
| `STRATEGY.md` | Data-driven strategy (what to ADD / REMOVE, why) | strategy decisions |
| `RULEBOOK.md` | Traps & things to NOT miss | before changing anything |
| `SYSTEM_OVERVIEW.md` | Architecture & workflow (how the system runs) | understanding the system |
| `FEATURES.md` | Model feature reference (the 44 features) | model / feature work |
| `BUG_LOG.md` | Known bugs (fixed + open) | debugging / before live |
| `FIXES_CHANGELOG4.md` | Full change history (2026-06) | "what changed & when" |
| `VALIDATION_RESULTS.md` | The evidence record (OOS/out-of-distribution numbers) | proving the edge / client report |

> All active docs are in **`docs/`** (this folder). Old docs are in **`docs/archive/`**. Backtest bats →
> `../backtest/README.md`. `CLAUDE.md` stays at the repo root (auto-loaded memory) and points here.

**Archive (in `docs/archive/`, history only):** `SESSION_NOTES.md`, `BACKTEST_SUMMARY.md`,
`QGAI_REVIEW_2026-06-22.md`, `SESSION_REVIEW_2026-06-22.md`,
`FIXES_CHANGELOG.md` / `2` / `3`, `GPT_INTEGRATION_COMPLETE.md`, `GPT_SETUP_GUIDE.md` (ChatGPT add-on, not wired live).

**GU — Active docs (જીવંત set, આ હંમેશા current રાખો):**
- `QGAI_GUIDE.md` = **આ** — index + essentials. હંમેશા પહેલા.
- `WORKING_NOTES.md` = અત્યારે ક્યાં છીએ / handoff. દર session ની શરૂઆતમાં.
- `TASKS.md` = priority task list. આગળ શું કરવું એ માટે.
- `STRATEGY.md` = data-driven strategy (શું ADD/REMOVE, કેમ).
- `RULEBOOK.md` = traps — બદલતા પહેલા વાંચો.
- `SYSTEM_OVERVIEW.md` = architecture / system કેવી રીતે ચાલે.
- `FEATURES.md` = model na 44 features.
- `BUG_LOG.md` = bugs (fixed + open).
- `FIXES_CHANGELOG4.md` = પૂરો change history.
- **Archive** (`docs/archive/`, ફક્ત history): SESSION_NOTES, BACKTEST_SUMMARY, *2026-06-22 reviews, CHANGELOG 1-3, GPT guides.

---

## 1 · WHAT QGAI IS / QGAI શું છે

**EN:** QGAI v2 = a live algorithmic trading system for GOLD (XAUUSD) on the M15 timeframe, running on
MetaTrader5. A 2-SMMA(2) "ratchet" line gives trend direction + trailing stop; an ML ensemble
(XGBoost + LightGBM + CatBoost, with an HMM regime selector) gives a win-probability per signal.
Entry when win_prob ≥ threshold (0.45); exit by ratchet trail + HTF H1 flip + TP cap. Risk 3%/trade,
daily 9% ratchet halt. Code in `C:\QGAI\engine`. Owner: Imtiyaz; collaborator: Anisa (shared PC via Cowork).

**GU:** QGAI v2 = MetaTrader5 પર GOLD (XAUUSD) M15 નું live algorithmic trading system. **2-SMMA(2)
ratchet line** trend direction + trailing stop આપે; **ML ensemble** (XGBoost+LightGBM+CatBoost + HMM
regime) દરેક signal નો win-probability આપે. Entry: win_prob ≥ threshold (0.45); Exit: ratchet trail +
HTF H1 flip + TP cap. Risk 3%/trade, daily 9% ratchet halt. Code: `C:\QGAI\engine`. Owner: Imtiyaz;
collaborator: Anisa (shared PC, Cowork).

---

## 2 · CORE STRATEGY / મુખ્ય strategy

**EN (the foundation — do not change lightly):**
- 2-SMMA(2) ratchet line = trend + trailing stop (basis of entry & exit).
- ML brain: HMM regime (Ranging/Trending/Volatile) → XGB+LGB+CAT → win-probability.
- It is TREND-FOLLOWING → wins in trends, loses in chop/range.
- Proven levers (data-tested): **range-phase filter** (skip H4 chop), **CTF-fade** (block counter-trend
  in a fading dominant TF), **HTF H1 exit** (anti-whipsaw), **regime-adaptive TP** (in validation).
- Full detail & the ADD/REMOVE list → `STRATEGY.md`.

**GU (પાયો — સહેલાઈથી ન બદલો):**
- 2-SMMA(2) ratchet line = trend + trailing stop (entry/exit નો પાયો).
- ML brain: HMM regime → XGB+LGB+CAT → win-probability.
- આ **trend-following** છે → trend માં જીતે, chop/range માં હારે.
- Proven levers: **range-phase filter**, **CTF-fade**, **HTF H1 exit**, **regime-adaptive TP** (validation માં).
- પૂરી વિગત + ADD/REMOVE list → `STRATEGY.md`.

---

## 3 · TOP RULES & TRAPS / મુખ્ય નિયમો & traps

**EN:**
1. **Always test on DEMO before live.** Nothing goes live unvalidated.
2. **Risk is 3%** (Imtiyaz's choice; Monte-Carlo says 1-2% safer).
3. **config_mt5.py holds live credentials — gitignored, never commit/expose.**
4. Every config flag is reversible — old value is in the inline comment.
5. In-sample backtest ≠ live. Judge by **PF / drawdown / OOS**, not the headline % return.
6. The account also has Anisa's manual trades → the bot reads WHOLE-account equity.
7. Don't validate an equity-overlay rule (daily ratchet) with fixed-lot WFO — it won't bind.
8. Full trap list → `RULEBOOK.md`.

**GU:**
1. **Live પહેલા હંમેશા DEMO પર test.** Validate વગર કંઈ live નહીં.
2. **Risk 3%** (Imtiyaz ની પસંદ; 1-2% safer).
3. **config_mt5.py = live credentials — gitignored, ક્યારેય commit/expose નહીં.**
4. દરેક config flag reversible — જૂનું value inline comment માં.
5. In-sample backtest ≠ live. **PF / drawdown / OOS** થી judge કરો, headline % return થી નહીં.
6. Account માં Anisa ના manual trades પણ છે → bot WHOLE-account equity વાંચે.
7. Equity-overlay rule (daily ratchet) ને fixed-lot WFO થી validate ન કરો.
8. પૂરી trap list → `RULEBOOK.md`.

---

## 4 · CURRENT LIVE CONFIG / અત્યારની live config  (`engine/config.py`)

| Setting | Value | Note |
|---------|-------|------|
| `ratchet_tp_cap_pct` | 1.00 | global TP 1% (regime-adaptive in validation, not live yet) |
| `ratchet_htf_sl` / `ratchet_htf_flip` | True | H1-line SL + flip (anti-whipsaw) |
| `skip_range_phase_entry` | True | skip H4 chop entries |
| `skip_counter_trend_fade` | **False** | **2026-07-07 DISABLED** — Path-A live-parity BT: CTF-OFF = +384.5R vs +350.2R = **+34.3R (+9.8%)**. CTF was blocking the 0/3-aligned 77%-WR edge. Env `QGAI_CTF_FADE=1` to force ON. |
| `ratchet_buf_pct` | 0.15 | SL buffer % — 2026-07-01: set from `Run_Buffer_Sweep.bat` result (PF 3.87, +430.70%, DD 2.9%, best balance). Old value 0.20 (comment in config.py). |
| `risk_pct` / `use_fixed_lot` | 3.0 / False | 3% dynamic compounding |
| `enable_live_dd_brake` | **True** | **2026-07-07 NEW** — live multi-day DD brake (dd>10%→½ 20%→¼ 30%→halt), PER-ACCOUNT peak (`dd_brake.py`). Protective. |
| vSL persistence | ON | **2026-07-07 NEW** (`vsl_persist.py`) — trailed vSL survives restart (was reset to entry). |
| `manual_risk_pct` | 3.0 (6% when manual trade open) | Imtiyaz's design — separate manual pool; 6% fallback path is INTENTIONAL. |
| daily | 9% ratchet | loss-floor + profit-lock |
| `trades_file` | …_RELABELED.xlsx | closed-loop relabel (Task P1) |
| features | **35** (main) +hmm_state | **2026-07-07 PART 1** — dropped 6 dead EA-combo features (was 41). WFO +444.7R vs +393.7R = **+13%**. no ATR, no volume. PART 2 (ADX composite) in test. |
| `stuck_trade_hedge_enabled` | True | 2026-07-01: full-lot protective hedge if a close keeps failing (e.g. AutoTrading off). Escalating `🚨 STUCK` alert past `stuck_close_fail_threshold` (3). Dedicated `stuck_hedge_magic` (202698), isolated from L13's manual pool. |
| `leftover_excess_hedge_enabled` | **False** | 2026-07-01 (Imtiyaz's idea, built, not yet enabled): GRADUATED version of the above — stretch risk `risk_pct`→`leftover_risk_cap_pct` (3%→6%) and hedge only the excess lot once real slippage exceeds that, instead of freezing the full lot immediately. Takes priority over the flag above when True. |

**GU:** ઉપરનું table = અત્યારની live settings. બધું reversible (config.py comment માં જૂનું value).
`trades_file` હમણાં RELABELED પર (P1). Regime-adaptive TP હજુ validation માં — live નથી.

---

## 5 · WHERE WE ARE & WHAT'S NEXT / અત્યારે ક્યાં + આગળ શું

**EN (2026-07-07 — major session):** Live bridge restarted with today's changes. Banked wins:
(1) **CTF-OFF** live: +34.3R Path-A. (2) **Feature PART 1**: dropped 6 dead EA-combo features →
retrain → WFO **+444.7R vs +393.7R baseline (+13%, 51/53 positive weeks)** — new honest baseline
is +444.7R. (3) **Fable-5 full system audit**: 16 findings; fixed 9 (vSL persist, live DD brake,
picker, checkpoint-sig, ADX-gate live-wire, replay-ADX as-of, config cleanup, reversal-gate flag,
news staleness check). vSL persist + DD brake verified live (restart restored vSL 4122.79, not
entry-reset). (4) **DD brake bug caught live + fixed**: was one global peak → poisoned mirror
secondary accounts ($2k/$10k vs $1.1M primary) → per-account fix. Deferred: S-5 forming-bar, H7
backtest daily-SL, M10 HMM hysteresis, L15/L16. **NEXT:** PART 2 (ADX 10→5 composite scores,
`QGAI_ADX_MODE=composite`, gate ≥ +444.7R, Fable P≈30%); then Fable's #1 = **FIX-3 parity**
(live-vs-backtest overlap ~12% → the real blocker before max_open=2 for the +20-50% goal).
Lesson logged: confirm before changing any risk/trading setting.

**EN (prior, 2026-07-01):** For live status read `WORKING_NOTES.md`; for the task list read `TASKS.md`. Right now (2026-07-01):
live bridge running with one LEFTOVER trade (#1519547791) under active stuck-trade monitoring; today was a
big fix/cleanup day (vSL-recovery bug + a real close-retry-loop bug, both traced from Imtiyaz's live-log
flag; graduated stuck-trade hedge built but not enabled; backtest_replay.py got checkpoint/resume + a
console-buffering fix; bridge_main.py mojibake cleaned per-glyph). Full 1-year live-param backtest
(`Run_Live_Buffer_015_CSV.bat`, parity-verified against live config first) is running — awaiting result.

**GU:** Live status → `WORKING_NOTES.md`; tasks → `TASKS.md`. અત્યારે (2026-07-01): live bridge એક
LEFTOVER trade (#1519547791) સાથે ચાલે છે (stuck-trade monitoring active). આજે મોટો fix/cleanup દિવસ —
vSL-recovery bug + close-retry-loop bug (Imtiyaz ના live-log flag પરથી મળ્યા), graduated stuck-hedge બન્યું
(હજુ enable નથી), backtest_replay.py માં resume + buffering fix, bridge_main.py mojibake per-glyph clean.
Full 1-year live-param backtest ચાલે છે — result ની રાહ.

---

## 5b · KNOWN BUGS / OPEN ISSUES — open items from `BUG_LOG.md`

**EN (corrected 2026-07-01 — this table was stale, code check confirmed actual status):**

| # | Sev | File | Status |
|---|-----|------|--------|
| A | 🔴 | bridge_session.py | ✅ Fixed — secondaries flatten on every daily-SL/TP halt path (verified 06-29) |
| B | 🟠 | bridge_core.py `recover_open_trades()` | ✅ Fixed — `open_time` now reconstructed from real open duration (code comment "Bug B fix", verified in file) |
| C | 🟠 | bridge_constants.py | 🔶 OPEN (dormant) — `SYMBOL` set once from `MT5_ACCOUNTS[0]` at import, never updated after `connect_primary()` failover. Currently harmless because `MT5_PRIMARIES` is unconfigured (no failover happens); becomes live risk the day failover is set up. |
| D | 🟠 | bridge_multi.py | 🔶 OPEN — one shared MT5 terminal for all accounts, inherently fragile (root of old #1/#3). Big refactor, parked. |
| E | 🟡 | backtest_replay.py | ✅ Fixed — UTF-8 stdout/stderr wrapper present (lines 26-27) |
| F | 🟡 | backtest_replay vs bridge | ✅ Fixed 2026-06-27 — backtest now config-aware (defaults to HTF when `ratchet_htf_sl=True`), full HTF parity (entry SL + trail + flip) |
| M | 🟠 | `engine/run_wfo.py` | ✅ **Fixed 2026-07-01:** `--trail-mode` default changed `"line"`→`None`, forward guard changed to `if args.trail_mode is not None:`. No flag = follows `backtest_replay.py`'s own config-aware default (htf today, correct-by-design now, not accidental); explicit `--trail-mode line` now genuinely forces literal line mode. `py_compile` clean. |
| N | 🟠 | `bridge_core.py recover_open_trades()` | 🔶 **OPEN (found 2026-07-01, Imtiyaz flagged):** vSL-recovery fallback uses a hardcoded $15-from-entry guess when a trade has no comment-embedded VSL/SL (now the norm) AND no broker-side SL (pure-virtual design) — discards the REAL trailed vSL on every restart. Mostly moot now that fix O below keeps stuck trades live-tracked (no restart needed) — a real vSL-persistence fix is still open, lower priority. |
| O | 🟠 | `bridge_core.py` (5 close-call sites) | ✅ **Fixed 2026-07-01:** `del virtual_trades[ticket]` ran unconditionally even on a FAILED close — a stuck trade silently dropped out of live monitoring after one failure, contradicting its own "will keep retrying" alert. `_close_position()` now returns True/False; callers only delete on confirmed success. |

**GU:** table 2026-07-01 ના ફ્રેશ code-check પ્રમાણે સાચી કરી. A✅ B✅ E✅ F✅ fixed (code verified) · C🔶 open પણ
dormant (failover configured નથી) · D🔶 open (moટો refactor) · **M🔶 નવો bug:** `run_wfo.py` માં `--trail-mode
line` (default) ખરેખર `--stop-trail` forward નથી કરતું → `backtest_replay.py` config-aware default પર જાય
(અત્યારે = htf, કારણ live HTF ON છે) → "line" mode માંગો તો પણ ચૂપચાપ **htf** મળે. અત્યારે live safety પર અસર
નથી (htf જ જોઈએ છે), પણ ભવિષ્યમાં કોઈ forced line-only comparison run માંગે તો ખોટું પરિણામ મળશે, ખબર પણ નહીં
પડે. Fix: `!= "line"` guard કાઢી હંમેશા `--stop-trail` pass કરો.

---

## 6 · HOW TO RUN / કેવી રીતે ચલાવવું  (`.bat` launchers, full Python path inside)

> **Full bat index → `../backtest/README.md`** (categorised, bilingual). Old/superseded bats are in
> `backtest/_archive_bats/`; old results in `backtest/results/_archive/`. Nothing deleted, just organised.
> **પૂરી bat list → `../backtest/README.md`.** જૂના bats `_archive_bats/` માં, જૂના results `results/_archive/` માં.

**Start\ (daily ops):** `1_Start_Trading` · `2_Update_Data` · `3_Train_Models` · `4_Auto_Scheduler` · `5_Dashboard`

**backtest\ (research/validation):**
- `Run_Backtest_Report.bat` — full replay report (WR/PF/Avg R + BY REGIME/HOUR/MONTH)
- `Run_TP_Sweep.bat` — 13-TP cap sweep · `Run_TP_Regime(_TEST).bat` — regime-adaptive TP
- `Run_WFO_FULL.bat` — global-TP WFO OOS · `Run_WFO_TPREGIME.bat` — regime-TP WFO OOS · `Run_WFO_Analyze.bat` — $10k analysis
- `Run_Backtest_FullHistory.bat` — 2022→2026 total dataset (parked)
- `Run_Relabel_Trades.bat` — relabel outcomes (Option B) · `Run_Rebuild_Trainset.bat` — rebuild entries (Option A, parked)

**GU:** `Start\` = રોજનું operation (trading/data/train/scheduler/dashboard). `backtest\` = research/validation
(ઉપરના bats). દરેક bat માં full Python path છે (PATH set નથી એટલે).

---

## 7 · KEY NUMBERS / મુખ્ય આંકડા (reference)

- OOS baseline: **PF 1.55**, +144R / 41 weeks, 82% green weeks, 9/10 green months.
- Regime-adaptive TP (in-sample backtest): Total R 257.7 → **310.2 (+20%)**, PF 2.52 → 2.56 — needs OOS.
- Relabel: 27% of training labels changed under live exit (Task P1).
- Data: OHLC+ADX 2022-05 → 2026-06 (97,235 M15 bars). Training trades: relabeled, Dec24→Apr26.
- Risk 3% → real DD ~28-39% (backtest fixed-lot ~2%). Watch equity.

---

## 8 · FAQ / વારંવાર પૂછાતા પ્રશ્નો

**Q1. How do I start trading? / Trading કેવી રીતે શરૂ કરું?**
EN: Run `Start\1_Start_Trading.bat` and `Start\5_Dashboard.bat`. Test on DEMO first.
GU: `Start\1_Start_Trading.bat` + `Start\5_Dashboard.bat` ચલાવો. પહેલા DEMO પર.

**Q2. I changed config — does it take effect immediately? / config બદલ્યું — તરત લાગુ થાય?**
EN: No. Restart `1_Start_Trading.bat` (and `5_Dashboard.bat`) to load new settings. Model changes need `3_Train_Models.bat`.
GU: ના. `1_Start_Trading.bat` (+ `5_Dashboard.bat`) restart કરો. Model changes માટે `3_Train_Models.bat`.

**Q3. How do I undo a change? / Change કેવી રીતે undo કરું?**
EN: Every flag is reversible — the old value is in the inline comment in `config.py`. Set it back, restart.
GU: દરેક flag reversible — જૂનું value `config.py` ના comment માં. પાછું set કરી restart કરો.

**Q4. Is regime-adaptive TP live? / Regime-adaptive TP live છે?**
EN: No. It won the in-sample backtest but is still in WFO OOS validation. Goes live (P3) only after it confirms.
GU: ના. In-sample backtest જીત્યું પણ હજુ WFO OOS validation માં. Confirm થાય પછી જ (P3) live.

**Q5. Why did the model labels change 27%? / Model na labels 27% કેમ બદલાયા?**
EN: The old training data was labeled by an OLD exit. We relabeled under the live exit (Task P1) so 27% of
win/loss flipped — the model was learning some wrong outcomes. Retrain (P1) applies the fix.
GU: જૂના data ના labels જૂના exit પ્રમાણે હતા. Live exit પર relabel કર્યું (P1) → 27% win/loss flip થયા —
model થોડા ખોટા outcomes શીખતું હતું. Retrain (P1) એ fix લાગુ કરે.

**Q6. Why risk 3% if 1-2% is safer? / 1-2% safer છે તો 3% કેમ?**
EN: Imtiyaz's choice for higher growth. Trade-off: 3% → real drawdown ~28-39%. Watch equity closely.
GU: Imtiyaz ની પસંદ (વધારે growth). Trade-off: 3% → real DD ~28-39%. Equity ધ્યાનથી જુઓ.

**Q7. Backtest looks amazing (+thousands %). Real? / Backtest જબરદસ્ત લાગે — સાચું?**
EN: The headline % is compounding fantasy. Judge by PF (~1.55 OOS) and drawdown. OOS/DEMO is the real proof.
GU: Headline % એ compounding fantasy. PF (~1.55 OOS) અને drawdown થી judge કરો. OOS/DEMO જ સાચો પુરાવો.

**Q8. The dashboard shows "Failed to fetch". / Dashboard "Failed to fetch" બતાવે.**
EN: The dashboard server isn't running — start `Start\5_Dashboard.bat` (runs serve.py).
GU: Dashboard server ચાલુ નથી — `Start\5_Dashboard.bat` ચલાવો (serve.py).

**Q9. Where do I see what changed and when? / શું ક્યારે બદલાયું ક્યાં જોઉં?**
EN: `FIXES_CHANGELOG4.md` (full history) + `BUG_LOG.md` (bugs).
GU: `FIXES_CHANGELOG4.md` (પૂરો history) + `BUG_LOG.md` (bugs).

**Q10. A backtest crashed with an emoji/encoding error. / Backtest emoji/encoding error થી crash.**
EN: The bats set `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8`. If you run a script manually, set those first.
GU: bats માં `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` છે. જાતે script ચલાવો તો પહેલા એ set કરો.

**Q11. What runs on my PC vs what can Claude do? / મારા PC પર શું vs Claude શું કરી શકે?**
EN: Training/WFO/live trading run on your PC (need the ML stack + MT5). Claude edits code, builds backtests,
analyses results, and runs model-independent tools (relabel/rebuild) in its sandbox.
GU: Training/WFO/live trading તમારા PC પર (ML stack + MT5 જોઈએ). Claude code edit, backtest build, result
analysis, અને model-independent tools (relabel/rebuild) sandbox માં ચલાવે.

**Q12. Add a new idea/task — where? / નવી idea/task ક્યાં ઉમેરું?**
EN: Tell Claude; it logs it in `TASKS.md` (priority-ordered) and updates `WORKING_NOTES.md`.
GU: Claude ને કહો; એ `TASKS.md` (priority order) માં લખે + `WORKING_NOTES.md` update કરે.

---
*This guide is the front door. Update §4 (config) and §5 (status pointer) whenever they change; keep the
rest stable. Detailed/volatile content stays in the linked living docs to avoid drift.*
*આ guide = મુખ્ય દરવાજો. §4 (config) અને §5 (status) બદલાય ત્યારે update કરો; બાકી stable રાખો.*
