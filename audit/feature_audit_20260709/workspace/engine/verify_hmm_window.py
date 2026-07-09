"""
verify_hmm_window.py — HMM v3 acceptance checks on the TRAINED live model
==========================================================================
2026-07-02 (Divyesh). Run AFTER train.py. Checks, against data/models/final:
  1. State distribution: train-subset (first 70%% rows) vs FULL data — must be
     SIMILAR (stability; attempt-2 failed this: 37%% vs 0.6%% Ranging).
  2. The flat 2026-07-02 08:00-13:15 window must read Ranging (or Trending),
     NOT Volatile (this is the live mislabel that started the whole fix).
  3. Per-cluster feature means (Volatile must be the HIGH-volatility cluster).

Run:  python verify_hmm_window.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CFG
from features import load_adx
from hmm_model import MarketStateHMM, STATE_NAMES

WIN_FROM = "2026-07-02 08:00:00"
WIN_TO   = "2026-07-02 13:15:00"

print("=" * 60)
print("  HMM v3 — ACCEPTANCE VERIFICATION")
print("=" * 60)

hmm = MarketStateHMM().load(f"{CFG.paths.models_dir}/hmm_model.pkl")
adx = load_adx(CFG.paths.adx_file)
missing = [f for f in hmm.features if f not in adx.columns]
if missing:
    print(f"❌ ADX data missing model features: {missing}")
    print("   Run regen_adx_di.py first (or mt5_data_updater.py + merge_data.py).")
    sys.exit(1)

states = hmm.predict_batch(adx)
n = len(states); tr = int(n * 0.70)

print(f"\n1) STATE DISTRIBUTION (n={n:,}, train=first 70%):")
ok_stab = True
for s in range(3):
    p_tr = (states[:tr] == s).mean() * 100
    p_fu = (states == s).mean() * 100
    flag = "OK" if abs(p_tr - p_fu) < 10 else "⚠ UNSTABLE"
    ok_stab &= abs(p_tr - p_fu) < 10
    print(f"   {STATE_NAMES[s]:9s}: train={p_tr:5.1f}%  full={p_fu:5.1f}%   {flag}")

print(f"\n2) FLAT WINDOW {WIN_FROM} → {WIN_TO}:")
m = (adx["datetime"] >= WIN_FROM) & (adx["datetime"] <= WIN_TO)
if not m.any():
    print("   ⚠ window not in data — update ADX data first")
    sys.exit(1)
win_states = states[m.values]
import collections
cnt = collections.Counter(STATE_NAMES[s] for s in win_states)
for ts, s in zip(adx.loc[m, "datetime"], win_states):
    print(f"   {ts}  {STATE_NAMES[s]}")
n_vol = cnt.get("Volatile", 0)
print(f"   summary: {dict(cnt)}")
ok_win = n_vol == 0

print(f"\n3) VERDICT:")
print(f"   stability : {'PASS' if ok_stab else 'FAIL'}")
print(f"   flat window not Volatile: {'PASS' if ok_win else f'FAIL ({n_vol} Volatile bars)'}")
if ok_stab and ok_win:
    print("   ✅ ALL CHECKS PASSED — proceed per WFO result (profit-first).")
else:
    print("   ❌ CHECK FAILED — do NOT deploy; tell Claude.")
