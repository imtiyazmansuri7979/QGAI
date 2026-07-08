# QGAI Flip-Fix — Full Workflow Reference / પૂરો workflow સંદર્ભ

*XAUUSD M15 · Volatile BUY/SELL flip-flop · Generated 2026-07-02 · EN + ગુજરાતી · Location column = clickable path*

EN: Flip-flop on Volatile bars — each bar picks max(BUY,SELL) with no memory, low Volatile threshold (0.42), both dir models fire. Fix: opt1 hysteresis (flip only if new signal beats last by a margin). Backtest-only toggles (live untouched), 3 options compared, margin swept, confirming on WFO. Location column links open the file/folder on this PC.

ગુજરાતી: Volatile bars પર flip-flop — દર bar max(BUY,SELL) pick કરે, memory નહીં, threshold નીચો (0.42). Fix: opt1 hysteresis. backtest-only toggles (live untouched), 3 options સરખાવ્યા, margin sweep, WFO પર confirm. Location column ની link ફાઇલ/folder ખોલે.

## 1. Code changes

| File (link) | What | Why |
|---|---|---|
| [C:\QGAI\engine\backtest_replay.py](file:///C:/QGAI/engine/backtest_replay.py) | Env-gated toggles QGAI_FF_HYST/GAP/VOLTHR at signal-pick; default OFF = identical to live. | EN: Test anti-flip options without touching live. / GU: Live અડ્યા વગર options ટેસ્ટ. |
| [C:\QGAI\engine\flipfix_analyze.py](file:///C:/QGAI/engine/flipfix_analyze.py) | Backtest-sweep analyzer: flips/WR/PF/R + PARITY guard. | EN: One table per sweep + catch non-frozen. / GU: sweep નું table + contaminated પકડે. |
| [C:\QGAI\engine\flipfix_wfo_analyze.py](file:///C:/QGAI/engine/flipfix_wfo_analyze.py) | WFO analyzer: concat weekly OOS, compare + parity. | EN: baseline vs hysteresis on OOS. / GU: OOS પર સરખાવે. |

## 2. Flip-fix bats

| Bat (link) | Output folder (link) | What it runs | Why | Status |
|---|---|---|---|---|
| [C:\QGAI\backtest\Run_FlipFix_Compare.bat](file:///C:/QGAI/backtest/Run_FlipFix_Compare.bat) | [C:\QGAI\backtest\results\flipfix](file:///C:/QGAI/backtest/results/flipfix) | baseline + opt1 hyst0.05 + opt2 gap0.08 + opt3 volthr0.46 (frozen). | Compare 3 options / 3 options સરખાવવા. | DONE — opt1 won (flips 55->17, PF 5.30->6.95). |
| [C:\QGAI\backtest\Run_FlipFix_MarginSweep.bat](file:///C:/QGAI/backtest/Run_FlipFix_MarginSweep.bat) | [C:\QGAI\backtest\results\flipfix_sweep](file:///C:/QGAI/backtest/results/flipfix_sweep) | baseline + hysteresis 0.03/0.05/0.07 (frozen). | Fine-tune margin / margin tune. | DONE — 0.07 best. |
| [C:\QGAI\backtest\Run_FlipFix_MarginSweep2.bat](file:///C:/QGAI/backtest/Run_FlipFix_MarginSweep2.bat) | [C:\QGAI\backtest\results\flipfix_sweep2](file:///C:/QGAI/backtest/results/flipfix_sweep2) | baseline + hysteresis 0.05/0.07/0.09/0.10 (frozen). | Find peak / peak શોધવા. | DONE — 0.10 overshoot; locked 0.07. |
| [C:\QGAI\backtest\Run_FlipFix_WFO.bat](file:///C:/QGAI/backtest/Run_FlipFix_WFO.bat) | [C:\QGAI\backtest\results\wfo_ff_baseline](file:///C:/QGAI/backtest/results/wfo_ff_baseline) | 2-pass WFO buf0.20 41wk: Pass A baseline + Pass B hyst0.07; auto-compare. | True-OOS confirm / OOS confirm. | RUNNING — A done (+360.1R); B 11/41 wk. |
| [C:\QGAI\backtest\Run_FlipFix_WFO_hyst015.bat](file:///C:/QGAI/backtest/Run_FlipFix_WFO_hyst015.bat) | [C:\QGAI\backtest\results\wfo_ff_hyst015](file:///C:/QGAI/backtest/results/wfo_ff_hyst015) | WFO hyst0.07 matching buf0.15/tp-regime/53wk. | OOS counterpart to 0.15 / 0.15 નો OOS. | NOT RUN (optional). |
| [C:\QGAI\backtest\Run_FlipFix_WFO_hyst020.bat](file:///C:/QGAI/backtest/Run_FlipFix_WFO_hyst020.bat) | [C:\QGAI\backtest\results\wfo_ff_hyst020](file:///C:/QGAI/backtest/results/wfo_ff_hyst020) | WFO hyst0.07 matching wfo_results (buf0.20). | OOS counterpart to wfo_results. | NOT RUN — superseded. |

## 3. Baseline bats

| Bat (link) | Output folder (link) | What it runs | Why | Status |
|---|---|---|---|---|
| [C:\QGAI\backtest\Run_Live_Buffer_015_CSV.bat](file:///C:/QGAI/backtest/Run_Live_Buffer_015_CSV.bat) | [C:\QGAI\backtest\results\live_buffer_015](file:///C:/QGAI/backtest/results/live_buffer_015) | backtest_replay IN-SAMPLE buf0.15. | In-sample baseline. | DONE — 597 tr, WR65.7%, PF4.27, +428.5R, 237 FLIP. |
| [C:\QGAI\backtest\Run_WFO_LiveMatch_Buf015.bat](file:///C:/QGAI/backtest/Run_WFO_LiveMatch_Buf015.bat) | [C:\QGAI\backtest\results\wfo_live_match_015](file:///C:/QGAI/backtest/results/wfo_live_match_015) | WFO OOS buf0.15 tp-regime 53wk. | OOS baseline (0.15). | DONE — 651 tr, WR68.2%, PF4.43, +483.0R, 973 flips, 258 FLIP. |
| [C:\QGAI\backtest\Run_WFO_FULL.bat](file:///C:/QGAI/backtest/Run_WFO_FULL.bat) | [C:\QGAI\backtest\results\wfo_results](file:///C:/QGAI/backtest/results/wfo_results) | WFO OOS buf0.20 41wk. | OOS baseline (0.20). | DONE — +255.4R, 682 flips. |

## 4. Comparison files

| File (link) | Compares | Key result |
|---|---|---|
| [C:\QGAI\backtest\results\flipfix\flipfix_comparison.csv](file:///C:/QGAI/backtest/results/flipfix/flipfix_comparison.csv) | 3 options vs baseline (frozen) | opt1 WINS: flips 55->17, PF 5.30->6.95. PARITY OK. |
| [C:\QGAI\backtest\results\flipfix_sweep\flipfix_comparison.csv](file:///C:/QGAI/backtest/results/flipfix_sweep/flipfix_comparison.csv) | hysteresis 0.03/0.05/0.07 | 0.07 best: flips 53->17, WR76.1, PF6.57. PARITY OK. |
| [C:\QGAI\backtest\results\flipfix_sweep2\flipfix_comparison.csv](file:///C:/QGAI/backtest/results/flipfix_sweep2/flipfix_comparison.csv) | hysteresis 0.05/0.07/0.09/0.10 | peak 0.07-0.09; 0.10 overshoot. PARITY OK. |
| [C:\QGAI\backtest\results\flipfix_wfo_comparison.csv](file:///C:/QGAI/backtest/results/flipfix_wfo_comparison.csv) | WFO baseline vs hyst0.07 (OOS) | PENDING — Pass B પૂરો થાય એટલે. |
| [C:\QGAI\backtest\results\live_buffer_015\BUFFER_015_BacktestVsWFO_2026-07-02.xlsx](file:///C:/QGAI/backtest/results/live_buffer_015/BUFFER_015_BacktestVsWFO_2026-07-02.xlsx) | backtest vs WFO (buf0.15) | WFO +483R vs backtest +428R; both flip heavy. |

## 5. Status & next

- Locked margin: opt1 hysteresis = 0.07.
- Running: Run_FlipFix_WFO Pass B (11/41 wk) -> results\flipfix_wfo_comparison.csv (PARITY) આપોઆપ બનશે.
- Next: OOS confirm -> integrate 0.07 into bridge_main.py + inference.py (default OFF -> DEMO -> live).
- Safety: frozen C:\QGAI_frozen + workdir C:\QGAI_wfo -> live models never touched.
