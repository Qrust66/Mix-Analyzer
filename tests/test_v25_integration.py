#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration test for the v2.5 spectral evolution pipeline.

Verifies the full path: load WAV → extract_all_features → build_all_v25_sheets,
matching the exact code path used by mix_analyzer.py.
"""

import os
import sys
import traceback

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


FIXTURES_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_like_mix_analyzer(filepath):
    """Replicate mix_analyzer.load_audio + to_mono exactly."""
    data, sr = sf.read(filepath, always_2d=True)
    data = data.astype(np.float32)
    if data.shape[1] > 2:
        data = data[:, :2]
    if data.ndim == 2 and data.shape[1] > 1:
        mono = np.mean(data, axis=1)
    else:
        mono = data.flatten()
    return mono, sr


def test_extraction_with_test_fixtures():
    """Extract features from every WAV fixture — same path as mix_analyzer."""
    from spectral_evolution import extract_all_features

    wav_files = sorted(f for f in os.listdir(FIXTURES_DIR) if f.endswith('.wav'))
    assert len(wav_files) > 0, "No WAV fixtures found"

    for fname in wav_files:
        filepath = os.path.join(FIXTURES_DIR, fname)
        mono, sr = _load_like_mix_analyzer(filepath)
        print(f"  {fname}: mono.shape={mono.shape}, dtype={mono.dtype}, sr={sr}")

        feat = extract_all_features(mono, sr)
        assert feat is not None, f"extract_all_features returned None for {fname}"
        assert feat.zone_energy is not None
        assert feat.descriptors is not None
        assert len(feat.zone_energy.zones) == 9
        print(f"    OK: {feat.zone_energy.zones['mid'].shape[0]} frames")


def test_sheet_building_from_features():
    """Build all v2.5 sheets into a workbook — same path as generate_excel_report."""
    from openpyxl import Workbook
    from spectral_evolution import extract_all_features
    from feature_storage import build_all_v25_sheets

    filepath = os.path.join(FIXTURES_DIR, '01_flat_wideband.wav')
    mono, sr = _load_like_mix_analyzer(filepath)
    feat = extract_all_features(mono, sr)

    ti = {'name': '01_flat_wideband.wav', 'type': 'Individual', 'category': 'Test'}
    features_with_info = [(feat, ti)]

    wb = Workbook()
    errors = []
    build_all_v25_sheets(wb, features_with_info, log_fn=lambda m: errors.append(m) if 'ERROR' in m.upper() else None)

    expected_sheets = [
        '_track_zone_energy',
        '_track_spectral_descriptors',
        '_track_peak_trajectories',
        '_track_valley_trajectories',
        '_track_crest_by_zone',
        '_track_transients',
    ]
    for sn in expected_sheets:
        assert sn in wb.sheetnames, f"Missing sheet: {sn}"
        assert wb[sn].sheet_state == 'hidden', f"Sheet {sn} should be hidden"

    assert len(errors) == 0, f"Sheet build errors: {errors}"
    print(f"  All {len(expected_sheets)} sheets present and hidden")


def test_too_short_signal_raises():
    """Signals shorter than 0.1s should raise ValueError, not crash."""
    from spectral_evolution import extract_all_features

    mono = np.random.randn(100).astype(np.float32) * 0.1
    try:
        extract_all_features(mono, 44100)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "too short" in str(e).lower()
        print(f"  Correctly raised: {e}")


def test_float64_input_works():
    """mix_analyzer may pass float64 mono in some numpy configs."""
    from spectral_evolution import extract_all_features

    mono = np.random.randn(44100 * 2).astype(np.float64) * 0.1
    feat = extract_all_features(mono, 44100)
    assert feat is not None
    assert feat.zone_energy is not None
    print(f"  float64 input: OK, {feat.zone_energy.zones['mid'].shape[0]} frames")


if __name__ == '__main__':
    print("=" * 60)
    print("v2.5 Integration Tests")
    print("=" * 60)

    tests = [
        ("Extraction from WAV fixtures", test_extraction_with_test_fixtures),
        ("Sheet building from features", test_sheet_building_from_features),
        ("Short signal raises ValueError", test_too_short_signal_raises),
        ("float64 input accepted", test_float64_input_works),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        print(f"\n--- {name} ---")
        try:
            fn()
            passed += 1
            print(f"  PASSED")
        except Exception as e:
            failed += 1
            print(f"  FAILED: {type(e).__name__}: {e}")
            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
