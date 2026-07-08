# QGAI Backtest Quick Start

Updated: 2026-07-04

## Run Menu

Use this first:

`C:\QGAI\backtest\RUN_BACKTEST_MENU.bat`

## Full Index

Detailed folder map:

`C:\QGAI\backtest\BACKTEST_FOLDER_INDEX.md`

## Folder Layout

| Folder | Purpose |
|---|---|
| `_runners` | Root `Run_*.bat` files moved here. |
| `_docs` | Workflow docs/reports moved here. |
| `_scripts` | Loose old Python utilities moved here. |
| `_archive_bats` | Old archived BAT files. |
| `results` | All active result and research folders. |

## Current Important Actions

| Need | Use |
|---|---|
| All backtest master log | `ALL_BACKTEST_MASTER_LOG_2026-07-04.md` |
| SELL early-entry real backtest | Menu option 1 |
| Baseline full backtest + BUY/SELL research | Menu option 2 |
| Baseline HMM backtest only | Menu option 3 |
| Exit Phase 3 research | Menu option 4 |
| Combined entry + exit real backtest | Menu option 5 |
| Entry variant 3-way full backtest | Menu option 6 |
| WFO live-match buffer 0.15 | Menu option 7 |
| Exit TP-cap sweep 0.50 to 3.00 | Menu option 10 |
| Entry max_open=2 policy tests | Menu option 11 |

## Resume Rule

Long backtests are resume-able:

- If a checkpoint exists, run the same BAT again.
- If a report already exists and no checkpoint exists, main BATs skip rerun.
- For a fresh rerun, delete that specific output folder/report first.

## Gujarati

- Normal કામ માટે `RUN_BACKTEST_MENU.bat` ચલાવો.
- Old root BATs હવે `_runners` માં છે.
- Active research outputs `results` folder માં છે.
- Long backtest અટકે તો same BAT ફરી run કરો, resume થશે.
