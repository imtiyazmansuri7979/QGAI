# Buffer 0.15 Comparison - 2026-07-01

Comparison between old buffer sweep `buf_0.15` and today's `live_buffer_015` backtest.

## Files Compared

- Old buffer sweep: `backtest/results/bufsweep/buf_0.15.txt`
- Today's run: `backtest/results/live_buffer_015/backtest_report.txt`

Both reports use period:

`2025-06-29 -> 2026-06-29`

## Summary Table

| Metric | Old `buf_0.15` | Today `live_buffer_015` | Difference |
|---|---:|---:|---:|
| Trades | 600 | 597 | -3 |
| Wins / Losses | 394 / 206 | 392 / 205 | nearly same |
| Win rate | 65.7% | 65.7% | same |
| Profit factor | 3.87 | 4.27 | today better |
| Avg R | +0.714 | +0.718 | today slightly better |
| Total R | +428.6R | +428.5R | almost same |
| Price move total | +10,767.4 | +10,750.2 | old +17.2 better |
| Avg move per trade | +17.95 | +18.01 | today slightly better |
| Captured efficiency | 9.7% | 9.7% | same |
| Net return | +430.70% | +19,890,222.77% | today inflated by compounding |
| Real $ profit on $10,000 start | +$43,070.00 | +$1,989,022,277.36 | today is compounded |
| Ending equity on $10,000 start | $53,070.00 | $1,989,032,277.36 | today is compounded |
| Max drawdown | 2.9% | 10.8% | old much safer |

## Exit Reason Comparison

| Exit Reason | Old `buf_0.15` | Today `live_buffer_015` |
|---|---:|---:|
| FLIP | 237 | 237 |
| TPCAP | 231 | 229 |
| TRAIL | 74 | 74 |
| SL | 58 | 57 |

## Move Comparison

Move capture is almost the same.

- Old `buf_0.15`: `+10,767.4` gold points
- Today `live_buffer_015`: `+10,750.2` gold points
- Difference: old is better by only `+17.2` points

This is very small over 597-600 trades, so move performance is practically equal.

## Main Finding

Strategy edge is almost unchanged:

- Same win rate: `65.7%`
- Same captured efficiency: `9.7%`
- Almost same Total R: `+428.6R` vs `+428.5R`
- Almost same move capture

The big difference is risk display / sizing:

- Old `buf_0.15` used `FIXED LOT 0.01`, no compounding.
- Today's report appears risk-based / compounding, so net return and drawdown are inflated.

## Compounding Reality - Every 100 Trades

Old `buf_0.15` exact per-trade CSV was not retained in `backtest/results/bufsweep`; only the text summary is available.

The table below uses today's full trade CSV:

`backtest/results/live_buffer_015/backtest_trades_st-htf.csv`

It shows how the same R edge looks under fixed 3% risk versus full compounding.

Dollar amounts below assume starting equity of `$10,000`.

| Trades | Block R | Cumulative R | Fixed 3% Profit | Compounded Profit | Ending Equity | Max DD |
|---|---:|---:|---:|---:|---:|---:|
| 1-100 | +116.2R | +116.2R | +$34,872.30 | +$259,426.96 | $269,426.96 | 5.9% |
| 101-200 | +65.8R | +182.1R | +$54,620.70 | +$1,757,176.48 | $1,767,176.48 | 7.5% |
| 201-300 | +48.1R | +230.1R | +$69,037.50 | +$6,898,844.86 | $6,908,844.86 | 10.8% |
| 301-400 | +74.5R | +304.6R | +$91,374.30 | +$58,211,425.54 | $58,221,425.54 | 10.8% |
| 401-500 | +52.8R | +357.4R | +$107,219.70 | +$260,045,257.43 | $260,055,257.43 | 10.8% |
| 501-597 | +71.1R | +428.5R | +$128,563.20 | +$1,989,022,277.36 | $1,989,032,277.36 | 10.8% |

Client-safe interpretation:

- Use `Cumulative R` for strategy quality.
- Use `Fixed 3% Profit` for a cleaner risk comparison.
- Treat `Compounded Profit` as a growth simulation only.
- The compounding numbers become extremely large because every gain increases the next trade's risk size.

## Conclusion

For clean strategy comparison, old `buf_0.15` is more reliable because fixed-lot sizing makes drawdown easier to compare.

Move-wise, both versions are almost equal.

Risk-wise, old `buf_0.15` is safer:

`2.9% DD` vs `10.8% DD`

Final read:

`buf_0.15` remains the cleaner benchmark. Today's run confirms the same edge, but with higher displayed drawdown due to sizing/compounding differences.
