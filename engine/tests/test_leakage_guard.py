"""
test_leakage_guard.py
──────────────────────
Automated tests for the train/backtest data-leakage guard (Imtiyaz spec,
2026-07-13, item 14). Pure stdlib unittest (pytest is not installed in this
environment) — run with:

    python -m unittest engine/tests/test_leakage_guard.py -v

Covers the guard logic itself (engine/leakage_guard.py) with synthetic meta
files in a temp dir, plus one feature-level regression test guarding the
in_range_phase lookahead leak this whole audit started from.

NOT covered here (documented, not silently skipped — see FIXES_CHANGELOG4.md
2026-07-13 entry "unresolved leakage risks"):
  - "slot table built using future trades -> FAIL": the train-split slice
    (trades.iloc[:_slot_tr_end], train.py Step 2) happens BEFORE
    build_slot_table() is called at all, so there is no future-trades code
    PATH to unit-test against — it's enforced by that call order, verified
    by code review, not a runtime check. If someone moves that call above
    the slice, no automated test here will catch it.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import leakage_guard as lg


def _write(d, fname, meta):
    (d / fname).write_text(json.dumps(meta), encoding="utf-8")


def _full_meta_set(d, cutoff_date, non_gating_cutoff=None):
    """Write a complete, valid meta set for every required/non-gating/
    no-exposure file, all sharing `cutoff_date` unless overridden."""
    base = {
        "training_end": cutoff_date, "validation_end": cutoff_date,
        "calibration_end": cutoff_date, "test_end": cutoff_date,
        "feature_data_end": cutoff_date,
    }
    for fname in lg.REQUIRED_META:
        _write(d, fname, dict(base))
    ng = non_gating_cutoff or cutoff_date
    ng_meta = {
        "training_end": ng, "validation_end": ng,
        "calibration_end": ng, "test_end": ng, "feature_data_end": ng,
    }
    for fname in lg.NON_GATING_META:
        _write(d, fname, dict(ng_meta))
    for fname in lg.NO_EXPOSURE_META:
        _write(d, fname, {"no_data_exposure": True})


class TestLeakageGuard(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_cutoff_equal_to_backtest_start_fails(self):
        """Spec case: cutoff == backtest_start -> FAIL (no free buffer day)."""
        _full_meta_set(self.d, "2026-06-29")
        with self.assertRaises(RuntimeError):
            lg.assert_no_leakage(self.d, "2026-06-29")

    def test_cutoff_after_backtest_start_fails(self):
        """Spec case: cutoff after backtest_start -> FAIL."""
        _full_meta_set(self.d, "2026-07-15")
        with self.assertRaises(RuntimeError):
            lg.assert_no_leakage(self.d, "2026-06-29")

    def test_cutoff_before_backtest_start_passes(self):
        """Spec case: cutoff strictly before backtest_start -> PASS."""
        _full_meta_set(self.d, "2026-04-29")
        effective, leaked = lg.assert_no_leakage(self.d, "2026-04-30")
        self.assertFalse(leaked)
        self.assertEqual(str(effective.date()), "2026-04-29")

    def test_missing_metadata_fails(self):
        """Spec case: missing metadata -> hard failure, not a warning."""
        _full_meta_set(self.d, "2026-04-29")
        (self.d / "hmm_meta.json").unlink()
        with self.assertRaises(RuntimeError):
            lg.assert_no_leakage(self.d, "2026-04-30")

    def test_one_directional_model_newer_uses_latest_cutoff(self):
        """Spec case: one directional model newer than the rest -> the
        LATEST cutoff across all components wins (never trust one file)."""
        _full_meta_set(self.d, "2026-04-29")
        _write(self.d, "buy_model_meta.json", {
            "training_end": "2026-06-15", "validation_end": "2026-06-15",
            "calibration_end": "2026-06-15", "test_end": "2026-06-15",
            "feature_data_end": "2026-06-15",
        })
        effective, _ = lg.compute_effective_training_cutoff(self.d)
        self.assertEqual(str(effective.date()), "2026-06-15")
        # a backtest starting right after the OTHER models' (older) cutoff
        # must still be BLOCKED because buy_model's true exposure is newer.
        with self.assertRaises(RuntimeError):
            lg.assert_no_leakage(self.d, "2026-04-30")

    def test_non_gating_model_stale_cutoff_does_not_block(self):
        """big_win/duration are deliberately NOT retrained per WFO fold
        (train.py Step 8, QGAI_CORE_ONLY=1) — their on-disk cutoff is
        routinely from an older full retrain and must NOT block a fold
        whose gating models are correctly cutoff-dated."""
        _full_meta_set(self.d, "2026-04-29", non_gating_cutoff="2026-07-10")
        effective, leaked = lg.assert_no_leakage(self.d, "2026-04-30")
        self.assertFalse(leaked)

    def test_allow_in_sample_overrides_but_still_reports_leak(self):
        """--allow-in-sample must not raise, but must not hide the true
        leaked status either (still returned/printed as FAIL)."""
        _full_meta_set(self.d, "2026-06-29")
        effective, leaked = lg.assert_no_leakage(
            self.d, "2026-06-29", allow_in_sample=True)
        self.assertTrue(leaked)

    def test_no_exposure_meta_without_flag_is_unsafe(self):
        """online/drift metas MUST declare no_data_exposure=True explicitly
        — a meta file that looks like it has real history but claims to be
        a no-exposure container is treated as unsafe."""
        _full_meta_set(self.d, "2026-04-29")
        _write(self.d, "online_model_meta.json", {"note": "oops, forgot the flag"})
        with self.assertRaises(RuntimeError):
            lg.assert_no_leakage(self.d, "2026-04-30")


class TestFeatureHonesty(unittest.TestCase):
    """Regression guard for the in_range_phase / big-move lookahead leak
    (features.py get_range_features) — the family of bugs this whole audit
    started from. A future-shifted feature here must be caught."""

    def test_in_range_phase_ignores_still_forming_h4_candle(self):
        import pandas as pd
        from features import get_range_features

        # 6 H4 candles: 4 boring, then a BIG-MOVE spike candle 16:00-20:00,
        # then one more. t sits INSIDE the spike candle (18:00), before its
        # 20:00 close.
        h4 = pd.DataFrame({
            "datetime": pd.to_datetime([
                "2026-01-01 00:00", "2026-01-01 04:00",
                "2026-01-01 08:00", "2026-01-01 12:00",
                "2026-01-01 16:00", "2026-01-01 20:00",
            ]),
            "h4_move_pct":   [0.1, 0.2, 0.1, 0.2, 5.0, 0.3],
            "cum3_move_pct": [0.1, 0.3, 0.4, 0.5, 5.3, 5.5],
            "is_big_move":   [0,   0,   0,   0,   1,   1],
            "big_move_size": [0.1, 0.3, 0.4, 0.5, 5.3, 5.5],
            "big_move_dir":  [1,   1,   1,   1,   1,   1],
            "in_range_phase":[1,   1,   1,   1,   0,   1],
        })
        t = pd.Timestamp("2026-01-01 18:00")   # inside the 16:00-20:00 candle
        feat = get_range_features(t, h4)
        self.assertEqual(
            feat["is_post_big_move"], 0,
            "LEAK: get_range_features saw the still-forming 16:00-20:00 "
            "candle's big-move flag before it closed at 20:00"
        )


if __name__ == "__main__":
    unittest.main()
