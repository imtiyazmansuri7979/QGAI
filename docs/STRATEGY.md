# QGAI — STRATEGY (data-driven) · 2026-06-23

XAUUSD M15 auto-trading. આ doc = આપણી ચર્ચા + data-test નો નિચોડ: **શું ADD, શું REMOVE, કેમ.**
(બીજા docs: RULEBOOK = traps · SYSTEM_OVERVIEW = architecture · WORKING_NOTES = current status.)

---

## 1. CORE STRATEGY (પાયો — બદલવાનો નથી)
- **2-SMMA(2) ratchet line** = trend direction + trailing stop (entry/exit નો પાયો).
- **ML brain:** HMM regime (Ranging/Trending/Volatile) → XGB+LGB+CAT ensemble → win-probability.
- **Entry:** model નો win_prob ≥ threshold (0.45) → BUY/SELL.
- **Exit:** ratchet line trail + flip + TP. **Risk 3%/trade, daily 9% ratchet halt.**
- ⚠️ આ trend-following છે → **trend માં જીતે, chop/range માં હારે.**

---

## 2. ✅ ADD કરવાનું (data-proven, આ session માં શોધ્યું)

### A. 🔥 RANGE-PHASE FILTER (સૌથી મોટો lever — IMPLEMENTED)
- **શોધ:** range-phase (H4 chop) trades **NET LOSE** — PF 0.76, −43R. Trend trades PF 2.62.
- **અસર:** range-phase skip → PF **1.74 → 2.62**, totR +287→**+331**, $move +$4,837→**+$6,120**.
- **કેમ:** trend-following ratchet range/chop માં whipsaw કરે (line ઉપર-નીચે = SL/TRAIL losses).
- **Config:** `skip_range_phase_entry = True`. Lookahead-free (last completed H4 bar). ✅
- **🔬 0.5% THRESHOLD — data-proven (sweep 2026-06-23, 1303 trades):** last-H4 move % પ્રમાણે avgR:
  0–0.25% = **−0.201R / PF 0.49** (deep chop, મોટો loser) · 0.25–0.5% = +0.027 / PF 1.10 (breakeven) ·
  0.5–0.75% = +0.228 / PF 1.81 · **0.75–1.0% = +0.610 / PF 3.66** · 1.0–2.0% = +0.66 / PF ~4.
  ➜ 0.5% ની નીચે બધું net-negative/breakeven → skip સાચું. 0.5% **well-placed, arbitrary નથી**.
  strong H4 move (0.75%+) = best entries. (Optional: 0.4% સહેજ tighter — benefit નહિવત્.)

### B. M15-ADX FILTER (બીજો lever — optional, higher quality)
- **શોધ:** low ADX (<25) = PF 2.52; high ADX (≥45) = PF 1.21. (range_phase=0 માં ADX<25 = PF **5.54**!)
- **અસર:** range + skip ADX≥45 → PF **3.27**, WR 58% (totR +305, સહેજ ઓછું પણ quality ઘણું ઊંચું).
- **કેમ:** high M15 ADX = M15 પહેલેથી extended = **late/chasing entry** = reversal risk.
- **Status:** flag ઉમેરવાનો બાકી (`max_m15_adx`). Optional refinement.

### C. TP = 1.00 (revert — best result config)
- **શોધ:** TP=1.00 config = **+287R / PF 1.74** vs far-TP WFO +144R / PF 1.55.
- **કેમ:** **TPCAP (TP hit) જ profit engine** — 165 trades, +352R, 100% win. far-TP કરો તો એ profit FLIP/TRAIL (~શૂન્ય) પર જાય → ગુમાવો.
- **Config:** `ratchet_tp_cap_pct = 1.00` (was 10 far). ✅ set (demo).

---

## 3. ❌ REMOVE / ન કરવાનું (data-proven)

### A. far-TP (HTF H1 exit) — REVERTED
- આ session માં far-TP + HTF exit ઉમેર્યું → **નફો કાપતું હતું** (profit FLIP પર જાય, TPCAP ગુમાવાય).
- **Config:** `ratchet_htf_sl=False, ratchet_htf_flip=False, tp_cap=1.00` — જૂનો best config પાછો. ✅

### B. VOLUME — REMOVED (model માંથી)
- volume entry filter ❌, volume exit ❌ — દરેક rolling version **hurt** (tested).
- `volume` feature (imp 0.02) + vol_spike model માંથી કાઢ્યા (ATR ની જેમ). Model volume ભાગ્યે જ વાપરતું.

### C. ATR — REMOVED
- ATR decisions માં વપરાતું નથી (2-SMMA volatility પકડે). ફક્ત display. Model feature કાઢ્યું.

### D. H1-ALIGNMENT ablation — WASH (ન કાઢ્યું)
- H1-align features કાઢી WFO → +149.8 vs +144 (wash). Descriptive (PF 2.46) oversold. **રાખ્યું.**

---

## 4. 🧪 PATTERN — એક જ underlying lesson
**"Late/extended/chasing entry = ખરાબ":**
- Range/chop entry (range-phase) ❌
- High M15 ADX (extended) ❌
- (big body/range/volume spike — same chasing, model પહેલેથી handle કરે)

**"Early/clean trend entry = સારું":** range_phase=0 + low ADX = PF 5.54.
👉 Focus = **clean trend entries પકડવા, chasing ટાળવા.**

### 🔎 BIG-MOVE → RANGE timing (data-verified, 2026-06-23)
Anisa ની intuition ("big move પછી 8-10 H4 candle sideways") H4 data (101 big-move events, 2022→હવે) પર check કરી:
- **Baseline:** gold H4 candle **83%** વખત range (<0.5%) જ હોય — range = default state.
- **Big move (3 H4 ≥2%) પછી:** તરત range-rate **ઘટે** — candle +4 પર ફક્ત **53%** (volatility/follow-through ટોચ પર), પછી ધીમે ચઢે (+7 પર 72%) પણ 15 candle સુધી **83% baseline ને નથી અડતું**.
- **સાચું reading:** big move પછી market **સીધું flat નથી** થતું — પહેલા ~4 candle follow-through/volatility, પછી ધીમે consolidate. "Post big move" નો ~10-12 H4 window (`is_post_big_move`) આ બરાબર પકડે.
- **Implication:** `is_post_big_move` (big થયો કે નહીં) અને `in_range_phase` (અત્યારે flat કે નહીં) **અલગ રાખવા સાચું** — model બંને જુએ, એક ધારણા પર નહીં. big-move પછી તરત entry = volatility risk; settle થયા પછી = safer.

---

## 5. 📋 FINAL CONFIG (current, demo)
| setting | value | કેમ |
|---|---|---|
| `ratchet_tp_cap_pct` | **1.00** | TPCAP profit engine |
| `ratchet_htf_sl/flip` | **False** | far-TP નફો કાપતું |
| `skip_range_phase_entry` | **True** | range chop = loss |
| `ratchet_buf_pct` | 0.20 | validated |
| `risk_pct` | 3.0 | (1-2% safer — Monte Carlo) |
| daily | 9% ratchet | loss-floor + profit-lock |
| features | 44 (no volume/ATR) | leaner |

---

## 6. ✅ VALIDATION — FINAL backtest (clean 44-feat model, 2025-09→2026-06)
**Confirmed on backtest_replay (real model, range-filter ON):**
| metric | before (no filter) | **FINAL (range-filter)** |
|---|---|---|
| Win rate | 44.7% | **52.8%** |
| Profit Factor | 1.74 | **2.26** |
| SL hits | 140 | **19** (chop trades gone) |
| $/trade | $3.71 | **$8.27** |
| Total | +287R | +247.6R / +$6,122 |
- Filter VERIFIED: 740/740 trades have in_range_phase=0 (zero chop). ✅
- ⚠️ STILL in-sample (whole-period single model) — **DEMO forward-test = the real proof** before live money.
- Mechanism structural (chop=loss) → credible. Max DD 1.8% is fixed-lot; real 3% sizing DD is higher.

## 6b. ✅ THIS IS THE FINAL STRATEGY → now on DEMO
Config locked (section 5). Clean model retrained. Applying on DEMO forward-test next.

## 7. ▶ NEXT STEPS
1. `3_Train_Models.bat` → clean 44-feat model
2. `Run_Backtest_Report.bat` → range-filter ON નો report (expect PF ~2.6) confirm
3. (optional) ADX≥45 skip flag ઉમેરો → PF 3.27
4. **Demo restart** → 1-2 અઠવાડિયા forward-test → exits/range-skip logs જુઓ
5. Demo OK → live small (risk 1-2% વિચારો)

## 7b. 🔥 CAPTURE LEAK — FLIP whipsaw (data-found 2026-06-23, BIG)
**Problem:** 18-23 Jun downtrend = 318 pts down-distance available, system **captured −61 pts (−19%)** —
14/18 trades exited via **FLIP at ~−8 pts each** = M15 line flips on minor noise → whipsaw.
**Metric:** "Captured Move / Available Move" (Anisa's framing). Script: `engine/analyze_capture.py`,
bat: `backtest/Run_Capture_Analysis.bat`. Re-simulates real signals under 4 exit rules.
**Result (738 signals, 2024-12→2026-06):**
| variant | captured pts | cap/path | total R | PF | win% |
|---|---|---|---|---|---|
| baseline (M15 flip) | 3,852 | 2.8% | +223 | 2.66 | 54% |
| **🏆 HTF (H1 flip)** | **7,984** | **5.7%** | **+297** | 2.51 | 49% |
| flip-confirm (prob≥45%) | 4,692 | 3.4% | +276 | 2.48 | 50% |
| trend-hold (+0.5R widen) | 3,925 | 2.8% | +225 | 2.65 | 54% |
**WINNER = HTF H1-flip:** 2× captured move, +33% total R. The M15 flip whipsaw was the leak.
(This is the HTF exit we built then reverted — data says re-enable it.) flip-confirm = good runner-up.
**⚠️ CONFIRM before live:** shadow-sim is relative. Run real `backtest_replay.py --stop-trail htf`
vs default → check total R + capture don't regress with TP=1.00 position mgmt. Then demo.
**Config to re-enable HTF:** `ratchet_htf_sl=True, ratchet_htf_flip=True` (currently False).

### 🔥 ENTRY fix — COUNTER-TREND FADE block (Anisa's "whichever-stronger TF" idea, data-WIN)
The 18-23 loss had 2 halves: exit-whipsaw (HTF fixes) AND some bad counter-trend entries.
Tested entry filters 5 ways (DI dir, ADX level, H4 slope, H1+H4 slope) — all blocked PROFITABLE
trades (raised PF but cut total R). **Anisa's refinement = use the DOMINANT timeframe (H1 or H4,
whichever ADX higher), not both/fixed** → first filter that ADDS profit:
| | trades | total R | PF | win% |
|---|---|---|---|---|
| baseline | 1303 | +287.7 | 1.74 | 45% |
| **+ CTF-fade block** | 1180 | **+303.0** | **1.89** | 46% |
| (blocked group) | 123 | −15.4 | **0.67** ❌ net-loser |
**RULE:** block a trade AGAINST the dominant-TF momentum (sign of that TF's DI_diff) WHEN that
dominant ADX slope is **FALLING** (trend real but fading = whipsaw no-man's-land). Counter-trend
in a RISING/strong trend is fine (TP catches pullbacks) — kept. Surprising: the losers are in
FADING trends, not strengthening ones (opposite of first guess — that's why we tested).
**Implemented (config-gated, default OFF):** `config.skip_counter_trend_fade` + inference exposes
H1/H4 ADX/DI/slope + filter in backtest_replay (`--ctf-fade`) & bridge_main. Lookahead-free.
**CONFIRM:** `backtest/Run_Backtest_Fixes.bat` A/B's baseline vs +CTF vs +HTF vs +BOTH on the real
engine. If BOTH wins → enable `ratchet_htf_sl/flip=True` + `skip_counter_trend_fade=True` → demo.

## 8. 📌 બાકી test-ideas (priority)
- **HTF H1-flip re-enable (above) — TOP priority, +33% R / 2× capture.** Confirm on backtest_replay first.
- Hour filter (config-dependent — TP=1.00 માં બધા hours positive, filter ઓછી જરૂર)
- ADX filter (above)
- News features fresh રાખવા (day×hour = fundamental timing, model પહેલેથી જાણે)

---
*data-driven. દરેક ADD/REMOVE પાછળ test છે. In-sample → demo confirm પછી live.*
