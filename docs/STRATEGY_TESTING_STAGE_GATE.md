# Strategy Testing Stage-Gate

**Purpose:** Every new feature, feature removal, strategy rule, filter, entry/exit idea, or model change must pass this loop before it can be called a winner.

**Permanent rule:** A 3-month backtest is only an initial screen. A feature/strategy is not final until it passes 3-month test, 1-year test, WFO, Monte Carlo risk, and forward/demo validation.

---

## Stage 1: 3-Month Initial Backtest

First train the model once, then run the next 3 months as a backtest.

Goal: check whether the strategy has a basic edge.

### Checkpoints

- Total R is positive
- Profit Factor is acceptable
- Max Drawdown is controlled
- Average R per trade is positive
- Total trades are enough
- Result is not caused by only a few large winners
- BUY and SELL results are separately acceptable
- Ranging, Trending, and Volatile regimes do not show heavy damage
- Worst week and longest losing streak are acceptable
- Spread, commission, and slippage stress still leave result positive
- No leakage or future-data usage

### Stage 1 Decision

**PASS:** 3-month result is profitable, explainable, and has acceptable drawdown. Move to Stage 2.

**HOLD:** Result is promising but trade count is low or one regime/direction is weak. Fix and rerun 3-month test.

**REJECT:** Result is negative, unstable, leakage-based, or has large drawdown. Do not run 1-year test.

---

## Stage 2: 1-Year Single-Training Backtest

After Stage 1 passes, train the model once and run a full 1-year backtest.

Goal: check whether the strategy survives different market periods.

### Checkpoints

- 1-year Total R is positive
- Profit Factor does not collapse versus 3-month result
- Max Drawdown is practically acceptable
- Monthly and quarterly performance are stable
- Profit does not come from only one month or one market event
- Majority of months are profitable or manageable
- Losing-month count and severity are acceptable
- Worst month is acceptable
- Longest losing streak is acceptable
- BUY and SELL results are explainable
- Strategy does not fully collapse in any regime
- Trade count is statistically meaningful
- Cost stress still leaves strategy positive
- Small parameter changes do not break the result
- 3-month and 1-year directions are broadly consistent

### Stage 2 Decision

**PASS:** 1-year result is stable, profitable, and has acceptable drawdown. Start WFO.

**HOLD:** Overall result is positive but one period, direction, or regime is weak. Apply targeted correction and rerun 1-year test.

**REJECT:** 3-month result was good but 1-year result is weak, flat, or negative. Strategy is not robust.

---

## Stage 3: Walk-Forward Optimization

Run WFO only after Stage 1 and Stage 2 both pass.

Goal: check whether retraining produces repeatable results on unseen periods.

### WFO Checkpoints

- Total R for each fold
- Positive folds %
- Median fold R
- Worst fold
- Profit Factor across folds
- Max Drawdown
- Performance remains stable after retraining
- Feature importance does not jump randomly across folds
- Result does not come from only one or two folds
- Overall WFO direction matches the 1-year backtest direction
- Retraining frequency is practical

---

## Final Testing Flow

```text
Step 1
Single Training
-> 3-Month Backtest

PASS
↓

Step 2
Single Training
-> 1-Year Backtest

PASS
↓

Step 3
Walk-Forward Optimization

PASS
↓

Monte Carlo
↓

Forward Test / Demo
↓

Small Live Deployment
```

---

## Important Rule

Never call a feature or strategy a final winner until it:

1. Passes 3-month test
2. Passes 1-year test
3. Stays stable in WFO
4. Shows acceptable Monte Carlo risk
5. Survives forward/demo execution

## Reminder For Every Future Test

Before accepting any result, write the stage beside it:

```text
Stage 1 only
Stage 2 passed
WFO passed
Monte Carlo passed
Forward/demo passed
```

If the stage is not written, the result is not final.
