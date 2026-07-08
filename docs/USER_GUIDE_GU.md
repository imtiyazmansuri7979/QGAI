# QGAI v2 — User Guide (ગુજરાતી, ટૂંકમાં)

XAUUSD (Gold) M15 પર ML auto-trading bot (MetaTrader5). Folder: `C:\QGAI`.

---

## 1. શું કરે છે (એક લાઈનમાં)
Gold ના M15 chart પર **2-SMMA trend-line** + **ML model** જોઈ, વિશ્વાસ હોય ત્યારે BUY/SELL trade ખોલે, **ratchet vSL** થી manage કરે, અને **3% risk** રાખે.

---

## 2. Entry — trade ક્યારે ખોલે?
ત્રણ વસ્તુ સાથे હોય ત્યારે જ:
1. **2-SMMA(2) flip** — trend BUY કે SELL માં વળે (direction નક્કી કરે).
2. **Model win-probability ≥ threshold** (~45%, regime પ્રમાણે) — model ને trade પર પૂરતો વિશ્વાસ.
3. **Filters pass** — slot/time, range-phase, counter-trend-fade.

> એક સમયે **max 1 bot trade** (magic 202600).
> ⚠️ Prob threshold ઓછો હોય તો trade SKIP થાય — એટلે ઘણીવાર મોડું entry થાય (model ની weakness).

---

## 3. Exit — trade ક્યારે બંધ કરે?
**Ratchet vSL** (virtual stop, broker પર નહીં):
- **vSL = HTF (H1) line ∓ 0.20% buffer**, **live (forming) line** ને follow કરે (chart indicator જેવું, hourly lag વગર).
- Line trend તરફ ખસે તેમ vSL **એક જ દિશામાં (ratchet)** tighten થાય — profit lock.
- **Price vSL ને cross કરે → CLOSE.**
- **2-SMMA flip ઊલટો થાય → CLOSE** (flip-exit, anti-whipsaw).
- **Regime-TP cap:** Ranging 2.0% / Trending 1.0% / Volatile 0.8% (HMM state પ્રમાણे).

---

## 4. Risk
- **દરેક trade: 3%** of equity (lot auto-size, compounding).
- **Daily 9% ratchet** — day-peak થી 9% નીચે આવે તો બધું બંધ + દિવસ માટे રોકાય (loss-floor + profit-lock).
- **L8 fix:** deposit/withdrawal ને equity માંથી net-out કરે (false halt ટાળે).

---

## 5. Manual trades (તમે જાતे ખોલેલ)
Bot તમારી manual trades (magic 0) ને પણ manage કરે:
- બધી manual trades **combine** → એક net position, એક vSL.
- **Virtual vSL** (broker પર SL નહીં — market ને stop ન દેખાય), bot breach પર close કરે.
- **અલગ 3% risk pool** (bot 3% + manual 3% = 6% total). વધારે lot હોય તો excess **hedge**.
- Target-TP 2% પર close. ⚠️ Bot OFF હોય તો manual ને protection નથी.

---

## 6. કેવી રીતे ચલાવવું (bats)
| કામ | File |
|---|---|
| Live trading શરૂ | `Start\1_Start_Trading.bat` |
| Data update | `Start\2_Update_Data.bat` |
| Model retrain | `Start\3_Train_Models.bat` |
| Dashboard | `Start\5_Dashboard.bat` |
| Backtest WFO | `backtest\Run_WFO_FULL.bat` |
| Buffer sweep | `backtest\Run_Buffer_Sweep.bat` |

> **નિયમ:** કોઈ પણ change LIVE કરતા પહેલા **DEMO + backtest/WFO** પર verify કરો.

---

## 7. હાલનું setup (2026-06-30)
- **Model:** 42 features (ts_line_dist_pct, vol_spike, EMA200-extra કાઢ્યા; price_vs_ema200 રાખ્યું). AUC ~0.68. WFO +255R / 93% green weeks.
- **vSL:** live forming H1 line + 0.20%-of-line buffer.
- **Manual:** virtual + combined + 3% pool.
- **Resume-prompt:** startup પર flat હોય તો "last signal trade કરવો? [y/N]" એક વાર પૂછે.

---

## 8. Startup log માં શું જોવું
- `✅ Inference engine ready` — models loaded.
- `🚀 Live trading` — ચાલુ.
- `RUNNING CONFIG` — settings verify.
- `🛡 COMBINED manual ... VIRTUAL vSL ON` — manual manage થાય છે.
- `❌ SKIP | prob X% < threshold` — signal હતું પણ confidence ઓછી.
- `✅ Trade SELL/BUY ... #ticket` — trade ખૂલી.
- ⚠️ કોઈ `error` / `null bytes` / crash દેખાય → તરત flag કરો.

---
*Files index: `docs\QGAI_GUIDE.md` (master) · `docs\TASKS.md` · `docs\RULEBOOK.md` · `docs\BUG_LOG.md`*
