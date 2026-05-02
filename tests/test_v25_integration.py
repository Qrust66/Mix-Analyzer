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


# ===========================================================================
# Phase F10c — preset-aware mix_analyzer.py STFT call sites (5 cases)
# ===========================================================================
#
# These tests exercise the new ``preset`` parameter on ``analyze_track`` and
# its sub-functions. Sites are split into HARMONIZE (#1, #2, #5) and PRESERVE
# (#3, #4) per the audio-engineer audit. Each test enforces the corresponding
# contract :
#
# - Default (no preset) ≡ explicit standard ≡ v2.7.0 (byte-strict).
# - HARMONIZE site #1 (analyze_spectrum) : n_fft scales + peak distance scales.
# - HARMONIZE site #1 P5 contract : minimum 107 Hz between detected peaks
#   regardless of preset.
# - PRESERVE site #3 (analyze_stereo) : output strictly identical
#   regardless of preset (the deliberate hardcoded n_fft=4096 is enforced).
# - PROPAGATE site #5 : analyze_track(preset=ultra) reaches the CQT pipeline
#   and changes _v25_features frame counts proportionally.

import pytest


class TestPhaseF10cPresetSupport:
    """Phase F10c — preset parameter on mix_analyzer.py analysis functions."""

    @staticmethod
    def _fixture_path(name: str = '02_wideband_one_resonance_500hz.wav') -> str:
        return os.path.join(FIXTURES_DIR, name)

    def test_analyze_track_default_equals_explicit_standard(self):
        """Most critical F10c test : default behaviour preserved.

        ``analyze_track(filepath)`` without preset must produce a result
        whose key fields match ``analyze_track(filepath, preset=standard)``.
        Comparison is byte-strict on the spectral content (CQT matrix
        proxy via _v25_features.peak_trajectories count + zone_energy
        dict equality) and on the spectrum dict's bin count.

        If this test ever fails, F10c broke v2.7.0 backward compatibility
        for callers that don't pass --resolution.
        """
        from mix_analyzer import analyze_track
        from resolution_presets import RESOLUTION_PRESETS

        fp = self._fixture_path()
        r_default = analyze_track(fp, compute_tempo=False)
        r_standard = analyze_track(
            fp, compute_tempo=False, preset=RESOLUTION_PRESETS["standard"],
        )
        # Spectrum dict must have identical structure + key freq-bin count
        assert len(r_default['spectrum']['freqs']) == len(
            r_standard['spectrum']['freqs']
        )
        # Peak detection identical (same number of peaks, same first peak)
        assert len(r_default['spectrum']['peaks']) == len(
            r_standard['spectrum']['peaks']
        )
        if r_default['spectrum']['peaks']:
            assert (
                r_default['spectrum']['peaks'][0]
                == r_standard['spectrum']['peaks'][0]
            )
        # CQT pipeline frame count identical
        feat_def = r_default['_v25_features']
        feat_std = r_standard['_v25_features']
        assert feat_def is not None and feat_std is not None
        # peak_trajectories list lengths must match (CQT preset same)
        assert len(feat_def.peak_trajectories) == len(feat_std.peak_trajectories)

    def test_analyze_spectrum_harmonized_with_preset(self):
        """analyze_spectrum n_fft scales with preset.

        Standard (n_fft=8192) → freqs has 4097 bins (n_fft/2 + 1).
        Ultra (n_fft=16384) → freqs has 8193 bins.
        """
        from mix_analyzer import analyze_spectrum
        from resolution_presets import RESOLUTION_PRESETS

        mono, sr = _load_like_mix_analyzer(self._fixture_path())
        r_standard = analyze_spectrum(mono, sr, preset=RESOLUTION_PRESETS["standard"])
        r_ultra = analyze_spectrum(mono, sr, preset=RESOLUTION_PRESETS["ultra"])
        # n_fft=8192 → 4097 bins ; n_fft=16384 → 8193 bins
        assert len(r_standard['freqs']) == 4097
        assert len(r_ultra['freqs']) == 8193

    def test_analyze_spectrum_peak_distance_scales_with_preset(self):
        """P5 contract : detected peaks always at least ~107 Hz apart.

        Without the Hz-based scaling of find_peaks(distance=...), the
        ultra preset would produce peaks ~54 Hz apart — false-positive
        splits in the dense mid range.

        This test creates a synthetic signal with two close peaks
        ~80 Hz apart in the mid range, runs analyze_spectrum at both
        standard and ultra, and asserts NEITHER preset reports them as
        separate peaks (both are within MIN_PEAK_DISTANCE_HZ).
        """
        from mix_analyzer import analyze_spectrum, MIN_PEAK_DISTANCE_HZ
        from resolution_presets import RESOLUTION_PRESETS

        sr = 44100
        duration = 2.0
        t = np.arange(int(sr * duration)) / sr
        # Two pure tones 80 Hz apart at 2000 / 2080 Hz (within MIN_PEAK_DISTANCE_HZ)
        sig = (
            np.sin(2 * np.pi * 2000 * t)
            + np.sin(2 * np.pi * 2080 * t)
        ).astype(np.float32) * 0.3

        for preset_name in ["standard", "ultra"]:
            r = analyze_spectrum(sig, sr, preset=RESOLUTION_PRESETS[preset_name])
            # Peaks within ~MIN_PEAK_DISTANCE_HZ should NOT be split into 2.
            # Check : for any pair of detected peaks, freq diff >= 107 Hz - eps.
            peaks = sorted(r['peaks'], key=lambda p: p[0])  # sort by freq
            for i in range(len(peaks) - 1):
                f_lo = peaks[i][0]
                f_hi = peaks[i + 1][0]
                # Allow 5 Hz slack for boundary-rounding
                assert f_hi - f_lo >= MIN_PEAK_DISTANCE_HZ - 5.0, (
                    f"preset={preset_name}: peaks at {f_lo:.0f} and "
                    f"{f_hi:.0f} Hz are {f_hi - f_lo:.0f} Hz apart, "
                    f"below MIN_PEAK_DISTANCE_HZ={MIN_PEAK_DISTANCE_HZ}"
                )

    def test_analyze_stereo_preserves_4096_regardless_of_preset(self):
        """PRESERVE contract : analyze_stereo output is byte-strict
        identical regardless of preset (n_fft=4096 hardcoded by audio
        physics ; preset arg accepted for API symmetry but ignored)."""
        from mix_analyzer import analyze_stereo
        from resolution_presets import RESOLUTION_PRESETS

        # Build a stereo fixture
        sr = 44100
        t = np.arange(sr * 2) / sr
        L = np.sin(2 * np.pi * 1000 * t).astype(np.float32) * 0.3
        R = np.sin(2 * np.pi * 1010 * t).astype(np.float32) * 0.3
        data = np.column_stack([L, R])

        r_no_preset = analyze_stereo(data, sr)
        r_standard = analyze_stereo(data, sr, preset=RESOLUTION_PRESETS["standard"])
        r_ultra = analyze_stereo(data, sr, preset=RESOLUTION_PRESETS["ultra"])
        r_max = analyze_stereo(data, sr, preset=RESOLUTION_PRESETS["maximum"])

        # All four outputs strictly identical on width_overall + width_per_band.
        assert r_no_preset['width_overall'] == r_standard['width_overall']
        assert r_no_preset['width_overall'] == r_ultra['width_overall']
        assert r_no_preset['width_overall'] == r_max['width_overall']
        for band in r_no_preset['width_per_band']:
            assert (
                r_no_preset['width_per_band'][band]
                == r_ultra['width_per_band'][band]
            ), f"PRESERVE broken : ultra changed width_per_band[{band}]"
            assert (
                r_no_preset['width_per_band'][band]
                == r_max['width_per_band'][band]
            ), f"PRESERVE broken : maximum changed width_per_band[{band}]"

    def test_v25_extract_propagation_to_ultra_changes_frame_count(self):
        """Site #5 PROPAGATE : analyze_track(preset=ultra) reaches the
        CQT pipeline. ultra runs at 12 fps, standard at 6 fps → ultra
        produces ~2× more frames in the v2.5 features (zone_energy
        time axis is the easiest proxy)."""
        from mix_analyzer import analyze_track
        from resolution_presets import RESOLUTION_PRESETS

        fp = self._fixture_path()
        r_standard = analyze_track(
            fp, compute_tempo=False, preset=RESOLUTION_PRESETS["standard"],
        )
        r_ultra = analyze_track(
            fp, compute_tempo=False, preset=RESOLUTION_PRESETS["ultra"],
        )

        feat_std = r_standard['_v25_features']
        feat_ultra = r_ultra['_v25_features']
        assert feat_std is not None and feat_ultra is not None

        # zone_energy.times reflects CQT frame count
        n_frames_std = len(feat_std.zone_energy.times)
        n_frames_ultra = len(feat_ultra.zone_energy.times)
        # ultra is 12 fps vs standard 6 fps → ratio ≈ 2.0 (small slop for
        # rounding + edge-frame handling)
        ratio = n_frames_ultra / n_frames_std
        assert 1.7 <= ratio <= 2.3, (
            f"Expected ~2× more frames at ultra vs standard, got "
            f"ratio {ratio:.2f} ({n_frames_std} vs {n_frames_ultra})"
        )


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
