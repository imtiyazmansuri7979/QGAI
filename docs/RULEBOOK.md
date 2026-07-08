# QGAI — RULEBOOK (things to NOT miss)

A living checklist of rules, traps, and principles learned the hard way.
Read this before changing parameters, backtesting, or going live.
**Live-trading system. Demo-test every change before live.**

---

## 0. PROCESS rules (how we work) ⚠️
- **🔒 "CK / check work" = CHECK ONLY. (Anisa, 2026-06-29)** When Anisa/Imtiyaz says "ck work" / "check it"
  / "ck this", it means **review and report findings ONLY**. Do NOT edit, fix, refactor, or change ANY file
  (code, config, docs, bats) **without explicit permission first**. Report what's wrong + suggested fix, then
  WAIT for a clear yes before changing anything. Do not change Imtiyaz's docs/work without permission.
- **🗂 ALWAYS update the task list the moment a task is DONE — and MOVE it into the DONE table. (Anisa,
  2026-06-29)** When any task/sub-task finishes: (1) mark it done + date + result, and (2) **physically MOVE
  the row OUT of the "🟡 બાકી (REMAINING)" table INTO the "✅ DONE" table** — do NOT just strike it through and
  leave it in REMAINING. The REMAINING table must contain ONLY genuinely-pending work at all times. Keep this
  up every single time, automatically.
- **When Imtiyaz raises a flag / "something looks off", it's SERIOUS — investigate, don't dismiss.**
  Read ALL relevant files (code + bats + config + results) and trace the real cause. (Precedent: the WFO
  "results all the same" flag was real — it was the `--tp-equity 3` TP-bypass, BUG_LOG #G — initially
  explained away as "trail tied". Don't repeat that.)
- **Two configs that SHOULD differ but produce IDENTICAL results = a bug to trace, not an expected tie.**
- **WFO/backtest must match LIVE config.** Live uses price TP cap (`tp_equity_pct=0`); so WFO must pass
  `--tp-equity 0`, NOT 3 (3 silently bypasses the TP cap). Check the bat flags match `config.py` before trusting a run.
- **⭐ BEFORE ANY test/backtest/WFO → DEEP bug-check, MINIMUM 4 ROUNDS.** Verify backtest == live on EVERY
  axis: entry SL (M15 vs H1), trailing line, flip signal (M15 vs H1), TP (price cap vs equity), buffer,
  lot/risk sizing, filters (range/CTF), HTF parity, no-lookahead (drop forming bar). History: nearly every
  "validated" number was later voided by a backtest≠live mismatch (#G tp-equity, #H WFO-cache, #F/#J HTF
  trail/flip/entry-SL). NEVER quote a result before parity is verified across these.
- **When fixing ONE cosmetic issue Imtiyaz points at (e.g. one broken emoji), don't blanket-fix every similar
  instance in the file without asking first — even if the root cause is identical everywhere.** (2026-07-01:
  Imtiyaz pointed at one mojibake glyph in `bridge_main.py`; a full-file sweep found ~680 more and fixed all
  of them — he explicitly said that went too far and asked for a revert, then wanted them fixed one-by-one
  as he pointed each out.) Fix exactly what was asked; offer the wider fix as a question, don't just do it.
- **The bash sandbox's file-mount cache can stay stale for HOURS, not just seconds** (confirmed 2026-07-01:
  `stat` mtime showed a 3+ hour lag on `backtest_replay.py` after edits that the `Read`/`Edit` tools showed
  correctly). Waiting/retrying doesn't reliably fix it. Ground truth is always the `Read`/`Edit`/`Grep`
  tools, never bash `cat`/`wc`/`py_compile` — if bash disagrees with `Read`, trust `Read`.

---

## 1. TP / EXIT traps  ⚠️
- **equity-TP% ÷ risk% = R-multiple.** So equity-TP 3% with risk 3% = **1R** (tight!).
  Tight TP (≈1R) → PF collapses to ~1.0 (kills the edge). Wide / no TP → PF ~1.2.
- **Live uses FAR TP** (`tp_equity_pct = 0`, `ratchet_tp_cap_pct = 10`) so the **flip is the exit**.
- In backtests with **real % sizing**, DO NOT pass `--tp-equity 3` (= 1R tight). Use `--tp-equity 0` (far).
- In backtests with **fixed-lot 0.01**, `--tp-equity 3` rarely fires (≈ far) — fine for clean-R comparison.

## 2. SIZING / LOT
- Live lot = **equity × risk% / SL_dist** (`risk_pct = 3`, `use_fixed_lot = False`). Wider SL → smaller lot, same $ risk.
- vSL hit = exactly **1R = risk% of equity** (≈3%), regardless of how wide the stop is.
- A wider HTF stop does NOT increase $ risk — it shrinks the lot.

## 3. RISK level (Monte-Carlo evidence)
- 3% risk → ~**87% chance of >50% drawdown**, big swings. 1–2% is much safer (DD ~22–40%).
- Higher risk does NOT keep helping — past ~Kelly it lowers return AND raises ruin.
- Drawdown is fixed by **lowering risk**, NOT by adding a TP (TP only cuts profit, not DD).

## 4. DAILY rule
- Daily = **9% ratchet** (loss-floor −9% + profit-lock; floor trails 9% below day-peak).
- Per-trade = 3% (vSL). The old "Trade-2 equity SL" was REMOVED (don't re-add).
- ⚠️ Daily/equity rules read the **WHOLE account equity** — if the account has **manual trades**,
  their P&L triggers the bot's halt/sizing. Use a dedicated account OR know this.

## 5. BACKTEST methodology
- **Stage 1 (rank exits):** fixed-lot 0.01 → clean comparable R, equity-effects muted. Use to PICK.
- **Stage 2 (realism):** real $10k + 3% volume → true $/DD/equity curve. Use to VALIDATE the winner. (FAR TP — see §1.)
- **Trade set VARIES by exit** (exit → equity → daily-halt/equity-TP → which trades happen).
  So you CANNOT re-derive other exit modes from a saved trade CSV — each needs a FULL sim.
- **Trail mode = exit only**, doesn't change training → one weekly retrain can feed all trail modes (the sweep).
- WFO resets each week to $10k → weekly R is comparable; total R is an honest sum.

## 6. TRUST / validation
- **Ignore headline backtest % (e.g. +279,000%)** — that's compounding fantasy. Judge by **PF, OOS, max DD**.
- **Walk-forward OOS is the truth** (weekly retrain on past, trade next week unseen). In-sample ≈ optimistic.
  Our validated baseline: PF 1.55 OOS, 82% green weeks, 9/10 green months.
- Always run a **--weeks 2 quick test** before a multi-hour full run.
- **A filter tested by dropping rows from an existing trade CSV can MISLEAD.** A static/hindsight cut
  (e.g. "top 10% volume across all trades") may look great but isn't implementable live. ALWAYS re-test
  with the **live-realistic rolling definition** (rolling percentile/threshold) before implementing.
  Example: the high-volume entry filter looked +3.6R better statically but every rolling version HURT
  (−25 to −50R). The model already uses volume as a feature — crude bolt-on filters usually hurt.

## 7. MODEL / FEATURES
- **Look-ahead leakage:** any slot/aggregate table (e.g. slot_win_rate) must be built on the **train split only**.
- **Prune only data-backed** (0 importance via feature_importance.csv). Beware **cross-model redistribution**:
  a feature with 0 importance in SELL may be top-5 in BUY/main — check all models before removing.
- After ANY feature change → **retrain** (3_Train_Models.bat) before live/backtest.
- **WFO/sweep overwrites `data/models/final/` each week** → after a WFO run the model there is the
  LAST week's, **cutoff-limited + core-only**. NEVER ship that to live. WFO = validation only;
  for live, run a **fresh full retrain** (3_Train_Models.bat, no cutoff, BigWin/Duration included).
- ATR removed (2-SMMA already gives volatility). ADX keeps its OWN internal TR — don't touch ADX.
- **NEVER train on the model's own backtest/WFO output** (e.g. ALL_OOS_trades.csv) as "trade history".
  It's circular — the model's own predictions, no NEW ground truth (same OHLC re-labelled) → leakage +
  false confidence (backtest glows, live doesn't follow). Training labels must come from PRICE outcomes.
  WFO's good result already reaches live via the weekly retrain — no need to inject WFO trades.

## 8. LIVE / SAFETY
- **Trade comments must NOT expose SL or strategy** (only branded text + phase).
- `config_mt5.py` holds REAL passwords → gitignored, **never push/commit**.
- TradeQuo (#125926628) is a LIVE real-money account — demo first.
- Restart the bridge after config/code changes for them to take effect.

## 9. FILE / PROJECT hygiene
- All backtest output lives in **`backtest/results/`** — never in `engine/` (engine = code + LIVE logs only).
- Don't delete files (even junk) unless asked. Move with care.
- History/changelogs in `engine/docs/FIXES_CHANGELOG*.md`. Update them after changes.
- Bats use the **full Python path** (PATH not set): `C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe`.

## 10. ENVIRONMENT quirks
- Python **3.12** (not 3.14 — hmmlearn needs C++ build tools on 3.14).
- Bats need `set PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8` (emoji crash under cp1252 when output is redirected).
- **Mount-cache artifact:** the helper's `bash` sometimes reads a truncated copy → false "syntax error" near EOF.
  The file is fine — verify with the file reader, not bash py_compile.
- Argparse: don't reuse an existing flag name (the `--trail-mode` vs `--stop-trail` clash crashed every run).

## 11. WORKFLOW order (current plan)
1. Stage 1 trail-sweep (fixed-lot, clean R) → pick best trail mode.
2. Stage 2 winner WFO (real $10k, 3% volume, FAR TP) → realistic $/DD.
3. Finalize exit → set in config.py → demo-test.
4. THEN apply shadow ledger + dashboard on the FINAL strategy.
5. Go live small, monitor.

---
*Add a line here whenever we hit a new "wish we'd remembered that" moment.*
