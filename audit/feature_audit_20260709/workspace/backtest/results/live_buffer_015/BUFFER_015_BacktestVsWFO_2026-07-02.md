# QGAI · Buffer 0.15 — Backtest (in-sample) vs WFO (true OOS)

**Symbol/TF:** XAUUSD M15 · **Period:** 2025-06-29 → 2026-06-29 · **Sizing:** fixed 0.01 lot (clean R) · **Risk:** 3%/trade
**Config:** buf 0.15, tp-regime, live-faithful HTF ratchet · **Generated:** 2026-07-02

Both runs use the **exact same period and config**. The only difference is the validation method:
`live_buffer_015` = one model trained on the whole dataset then replayed (**in-sample**);
`wfo_live_match_015` = weekly retrain on past-only data, trade the next unseen week (**true out-of-sample** — this is what LIVE actually does).

---

## Side-by-side

| Metric | live_buffer_015 (backtest, in-sample) | wfo_live_match_015 (WFO, OOS) | Δ |
|--------|:---:|:---:|:---:|
| Model | single, trained on all data | weekly retrain (live-like) | — |
| Trades | 597 (W 392 / L 205) | 651 | +54 |
| Win rate | 65.7% | **68.2%** | +2.5 pp |
| Profit factor | 4.27 | **4.43** | +0.16 |
| Avg R / trade | 0.718 | **0.742** | +0.024 |
| **Total R** | +428.5R | **+483.0R** | **+54.5R** |
| Positive / negative weeks | — | 51 / 0 | — |
| Max drawdown | 10.8% | — | — |
| **FLIP exits (whipsaw)** | **237** | **258** | +21 |
| Direction flips (signals) | — | 973 | — |
| Exit mix | FLIP 237 · TPCAP 229 · TRAIL 74 · SL 57 | FLIP 258 · TPCAP 272 · TRAIL 75 · SL 46 | — |

---

## Read-out / તારણ

1. **WFO (OOS) beats the static backtest here** — +483R vs +428R, WR 68.2% vs 65.7%, PF 4.43 vs 4.27.
   Normally OOS is *worse*; here the **weekly retrain adapts to each regime**, so 53 fresh weekly models
   are sharper than one model averaged over a whole year. WFO also **mirrors LIVE** (which retrains often),
   so it is the number to trust — the plain backtest is, if anything, slightly *conservative* here, not optimistic.
   *(GU: WFO દર week ફરી train કરે એટલે regime ને adapt કરે — એટલે એક-જ static model કરતાં સારો, ને live ને સાચી રીતે રજૂ કરે.)*

2. **Flip-flop whipsaw is real in BOTH** — 237 FLIP exits in-sample, 258 OOS. This is the direction
   BUY↔SELL flip-flop problem; it is not a display artifact. Reducing it is the goal of the
   **opt1 hysteresis (margin 0.07)** fix, currently under OOS validation.
   *(GU: flip-flop backtest અને OOS બંનેમાં ભારે — 237/258 FLIP exits. opt1 hysteresis 0.07 એ ઘટાડવાનું છે.)*

3. **Ignore the backtest "Net return %"** (compounding-TP artifact). Use **R (risk-multiple)** as the metric.

---

## Method reference

| | backtest_replay | WFO (walk-forward) |
|---|---|---|
| Model | one, trained on all data | retrained each week, past-only |
| Test data | model has seen it (in-sample) | next week unseen (true OOS) |
| Numbers | can be optimistic | honest, trustworthy |
| Speed | minutes | ~1.5–2 hr / pass |
| Use for | quickly ranking options | confirming the final decision |
