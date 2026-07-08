# HMM v3 — "Flat market reads Volatile" fix: A/B workflow (2026-07-02)

**Status:** code DONE + sandbox-verified · **A/B WFO pending on user PC** · bridge NOT restarted (old model still live in memory)

## 1. Problem
2026-07-02 08:00→13:15: price flat (net +0.047%, range 0.66%) yet every bar read **Volatile** → lowest entry threshold (0.42) → over-trading in chop. v1 (+DI/−DI raw) clustered by direction; v2 (di_sum/clarity) had non-discriminating di_sum (65% Volatile, unstable) **plus a predict-path bug: PlusDI/MinusDI keys were never passed at inference → silently 0**.

## 2. Sandbox findings (numpy GMM replica, 97,610 M15 rows)
| Finding | Evidence |
|---|---|
| Raw band % is non-stationary | Gold vol drifted 2022→2026. The "flat" window = p88–92 vs ALL data, but only p21–53 vs last 30 days |
| Smoothed ADX/\|DI_diff\| stay high in post-trend chop | Volatile vs Trending cluster ADX 38.3 vs 38.2 — no separation |
| Literal spec [ADX, \|DI_diff\|, band] FAILS its own acceptance | Volatile cluster band 0.217 ≈ Ranging 0.203 (NOT high); chop→78% Trending; 48% of quiet bars→Volatile; train/full drifts |
| Fix: di_eff + band_rel | di_eff = 100·\|+DI−−DI\|/(+DI+−DI) (instantaneous DX, lag-free clarity); band_rel = band_width_pct / trailing-30d-mean (drift-free; numerator stays lag-free, NOT ATR) |

## 3. A/B variants (env `QGAI_HMM_VARIANT`, per-TF blocks × M15/M30/H1/H4)
| | A = `spec` | B = `rel` (recommended) |
|---|---|---|
| Features | [ADX, \|DI_diff\|, band_width_pct] | [ADX, di_eff, band_rel] |
| Volatile cluster vol | 0.217% (≈ Ranging — FAIL) | 1.65× (Ranging 0.79× — PASS) |
| Flat 07-02 window | 16 Trending / 6 Ranging / 0 Volatile | 18 Ranging / 4 Trending / 0 Volatile |
| Proxy chop → Volatile | 1% (78% Trending) | 80% |
| Proxy quiet → Volatile | 48% | 0% |
| Train vs full distribution | 34.8/21.7/43.5 → 30.4/33.0/36.6 (drift) | 42.8/36.1/21.1 → 42.4/36.6/21.0 (stable) |

Labeling rule (both): Trending = max clarity (4-TF avg); of the rest Volatile = max vol, Ranging = min vol.

## 4. Code changes (all host-verified via ground-truth reader)
- `engine/regen_adx_di.py` — adds `{TF}_band_width_pct` (SMMA2 band, `trend_signal._ma` port), `{TF}_di_eff`, `{TF}_band_rel` (30D rolling, warmup→1.0); non-clobbering backup; DI_diff parity check kept.
- `engine/mt5_data_updater.py`, `engine/fresh_reload.py` — same columns, identical formulas (train==live parity).
- `engine/hmm_model.py` — v3: variant switch; `_engineer` = [ADX, |clarity|, vol]; 4-TF-avg labeling; **pkl stores its own feature list** (predict is env-var-proof); missing-key warning.
- `engine/features.py` — forwards the 3 new columns per TF into feat_dict (state-model-only, NOT in FEATURE_COLS).
- `engine/inference.py`, `train.py`, `self_learning.py` — adx_row now built from the model's own feature list (**fixes the v2 silent-zero key bug**; self_learning positional-column bug also fixed).
- `engine/verify_hmm_window.py` — NEW acceptance script (stability + flat-window checks).
- Bats: `backtest/Run_HMM_AB_WFO.bat` (regen + freeze + launch both), `Run_HMM_WFO_A_spec.bat`, `Run_HMM_WFO_B_rel.bat`, `Run_HMM_v3_Deploy.bat`.

## 5. RUN ON PC (in order)
1. **`C:\QGAI\backtest\Run_HMM_AB_WFO.bat`** — regen + freezes `C:\QGAI_wfo_spec` + `C:\QGAI_wfo_rel` + opens 2 parallel WFO windows (~1.5–2.5 h each; resume-safe; live untouched). Slow PC? Run the two child bats one after the other instead.
2. Check regen output: DI_diff parity Δ small; band/di_eff/band_rel stats printed.
3. When both finish → tell Claude **"AB WFO done"** → compare `results\wfo_hmm_spec` & `wfo_hmm_rel` `_WFO_SUMMARY.txt` vs baseline **+483.1R** (`wfo_live_match_015`).
4. **Adopt winner ONLY if total R ≥ +483.1R** (profit-first). If both worse → NO deploy, revert plan below.
5. `Run_HMM_v3_Deploy.bat` (default variant `rel`; **edit the `QGAI_HMM_VARIANT` line to `spec` if A won**) — backs up live models → `_backup_pre_hmm_v3`, regen, train.py, verify_hmm_window.py.
6. Verify prints **ALL CHECKS PASSED** → restart bridge — **DEMO first**, watch dashboard states.

## 6. Revert
Copy `data\models\_backup_pre_hmm_v3` (or `final_backup_pre_hmm_di_manual`) back into `data\models\final` + git-revert engine code + restart bridge. `adx_merged.csv` backups: `.bak_prediregen` (original) + timestamped `.bak_*`.

## 7. Open risks / notes
- Sandbox GMM = numpy EM replica, not sklearn — cluster structure was clean/stable, but the sklearn run on PC is definitive (train.py prints cluster stats; verify script gates deploy).
- WFO weekly retrains fit the HMM per week — per-week distributions will vary; the gate is TOTAL R.
- `merge_data.py` needs no change (concat carries new columns; historical files are `.disabled`, live-only mode).
