"""Tests for resolution_presets.py — Phase F10a.

Coverage targets per spec §9.1 : > 85% on resolution_presets module.
Tests verify : (1) 5 presets registered with documented spec §2.1
values; (2) properties compute correctly; (3) Q1 strict v2.7.0
equivalent for standard preset; (4) sample-rate-aware helpers handle
44.1k and 48k correctly; (5) validation raises on bad inputs;
(6) build-time validation rejects malformed configs.
"""
from __future__ import annotations

import math

import pytest

from resolution_presets import (
    DEFAULT_RESOLUTION_PRESET,
    InvalidPresetError,
    InvalidThresholdError,
    PEAK_THRESHOLD_MAX_DB,
    PEAK_THRESHOLD_MIN_DB,
    REFERENCE_SAMPLE_RATE,
    RESOLUTION_PRESETS,
    ResolutionPreset,
    _build_preset,
    get_effective_cqt_hop_samples,
    get_effective_stft_delta_freq_hz,
    get_effective_stft_hop_ms,
    get_effective_stft_hop_samples,
    get_preset_by_name,
    validate_peak_threshold_db,
)


# ============================================================================
# Registry — the 5 presets exist
# ============================================================================


def test_six_presets_registered():
    """Phase F11 added the 6th preset 'extreme' (100 fps CQT,
    hop_ratio=0.125 STFT)."""
    assert set(RESOLUTION_PRESETS) == {
        "economy", "standard", "fine", "ultra", "maximum", "extreme",
    }


def test_default_is_standard():
    assert DEFAULT_RESOLUTION_PRESET == "standard"
    assert DEFAULT_RESOLUTION_PRESET in RESOLUTION_PRESETS


# ============================================================================
# Q1 validated 2026-05-02 — standard preset = v2.7.0 strict equivalent
# ============================================================================


def test_standard_preset_is_v270_strict_equivalent():
    """Q1 contract : standard preset must preserve ALL v2.7.0 params.
    If any of these values changes, the F10b non-regression test will
    fail and existing scripts that don't pass --resolution will see
    different output."""
    std = RESOLUTION_PRESETS["standard"]
    # CQT params (from spectral_evolution.py:24-26)
    assert std.cqt_target_fps == 6  # = TARGET_FRAMES_PER_SEC
    assert std.cqt_bins_per_octave == 24  # = CQT_BINS_PER_OCTAVE
    assert std.cqt_n_bins == 256  # = CQT_N_BINS

    # STFT params (from mix_analyzer.py:512-515)
    assert std.stft_n_fft == 8192


# ============================================================================
# Spec §2.1 / §15 quick card values — fundamentals
# ============================================================================


@pytest.mark.parametrize("name,n_fft,fps,bpo", [
    ("economy",  8192,  4,   24),
    ("standard", 8192,  6,   24),
    ("fine",     16384, 10,  24),
    ("ultra",    16384, 12,  36),
    ("maximum",  16384, 24,  48),
    ("extreme",  16384, 100, 48),  # Phase F11 — user target 10 ms/frame CQT
])
def test_preset_fundamental_values_match_spec_table(name, n_fft, fps, bpo):
    p = RESOLUTION_PRESETS[name]
    assert p.stft_n_fft == n_fft
    assert p.cqt_target_fps == fps
    assert p.cqt_bins_per_octave == bpo


# ============================================================================
# Properties — derived values match spec table
# ============================================================================


@pytest.mark.parametrize("name,expected_hop_samples,expected_df_hz", [
    ("economy",  2048, 5.38),
    ("standard", 2048, 5.38),
    ("fine",     4096, 2.69),
    ("ultra",    4096, 2.69),
    ("maximum",  4096, 2.69),
    ("extreme",  2048, 2.69),  # Phase F11 — hop_ratio=0.125 -> hop_samples=16384*0.125=2048, df unchanged (n_fft same)
])
def test_stft_derived_properties(name, expected_hop_samples, expected_df_hz):
    p = RESOLUTION_PRESETS[name]
    assert p.stft_hop_samples_at_44k == expected_hop_samples
    assert math.isclose(
        p.stft_delta_freq_hz_at_44k, expected_df_hz, rel_tol=0, abs_tol=0.01,
    )


@pytest.mark.parametrize("name,expected_n_bins,expected_fpb", [
    ("economy",  256, 1.875),    # 4 * 60/128
    ("standard", 256, 2.8125),   # 6 * 60/128
    ("fine",     256, 4.6875),   # 10 * 60/128
    ("ultra",    384, 5.625),    # 12 * 60/128
    ("maximum",  512, 11.25),    # 24 * 60/128
    ("extreme",  512, 46.875),   # 100 * 60/128 (Phase F11)
])
def test_cqt_derived_properties(name, expected_n_bins, expected_fpb):
    p = RESOLUTION_PRESETS[name]
    assert p.cqt_n_bins == expected_n_bins
    assert math.isclose(
        p.cqt_frames_per_beat_at_128bpm, expected_fpb,
        rel_tol=0, abs_tol=0.001,
    )


def test_n_bins_scaling_preserves_octave_coverage():
    """The n_bins formula scales linearly with bins_per_octave to
    preserve ~10.67 octaves of coverage. Verify across all presets."""
    for name, p in RESOLUTION_PRESETS.items():
        octaves = p.cqt_n_bins / p.cqt_bins_per_octave
        assert math.isclose(octaves, 256 / 24, rel_tol=0.01), (
            f"{name}: octave coverage drifted ({octaves:.3f} vs 10.67 ref)"
        )


# ============================================================================
# Sample-rate-aware helpers
# ============================================================================


@pytest.mark.parametrize("sample_rate,expected_ultra_hop_ms", [
    (44100, 92.88),
    (48000, 85.33),
    (88200, 46.44),
    (96000, 42.67),
])
def test_get_effective_stft_hop_ms_at_various_sr(
    sample_rate, expected_ultra_hop_ms,
):
    """STFT hop in samples is invariant; hop in ms scales with 1/sr."""
    ultra = RESOLUTION_PRESETS["ultra"]
    actual = get_effective_stft_hop_ms(ultra, sample_rate)
    assert math.isclose(actual, expected_ultra_hop_ms, abs_tol=0.05)


def test_stft_hop_samples_invariant_with_sr():
    """STFT hop in SAMPLES doesn't depend on sample rate (librosa
    convention : hop = n_fft / 4)."""
    ultra = RESOLUTION_PRESETS["ultra"]
    hop_at_44k = get_effective_stft_hop_samples(ultra, 44100)
    hop_at_48k = get_effective_stft_hop_samples(ultra, 48000)
    hop_at_96k = get_effective_stft_hop_samples(ultra, 96000)
    assert hop_at_44k == hop_at_48k == hop_at_96k == 4096


@pytest.mark.parametrize("sample_rate,expected_df_hz", [
    (44100, 2.69),
    (48000, 2.93),
    (88200, 5.38),
    (96000, 5.86),
])
def test_get_effective_stft_delta_freq_hz(sample_rate, expected_df_hz):
    """STFT Δf = sr / n_fft. Increases linearly with sr."""
    ultra = RESOLUTION_PRESETS["ultra"]
    actual = get_effective_stft_delta_freq_hz(ultra, sample_rate)
    assert math.isclose(actual, expected_df_hz, abs_tol=0.01)


def test_cqt_hop_targets_fps_regardless_of_sr():
    """CQT hop is computed to hit cqt_target_fps; preserves frame rate
    across different sample rates."""
    ultra = RESOLUTION_PRESETS["ultra"]  # 12 fps target
    hop_at_44k = get_effective_cqt_hop_samples(ultra, 44100)
    hop_at_48k = get_effective_cqt_hop_samples(ultra, 48000)
    # Frame rate = sr / hop ; should be ≈ 12 fps for both
    fps_44k = 44100 / hop_at_44k
    fps_48k = 48000 / hop_at_48k
    assert math.isclose(fps_44k, 12.0, abs_tol=0.1)
    assert math.isclose(fps_48k, 12.0, abs_tol=0.1)


def test_cqt_hop_floors_at_512():
    """At very high target_fps × low sr combinations, hop floors at
    512 (librosa CQT lower bound)."""
    # Maximum preset (24 fps) at 8 kHz would compute hop = 333 ; floored to 512.
    p_max = RESOLUTION_PRESETS["maximum"]
    hop = get_effective_cqt_hop_samples(p_max, sample_rate=8000)
    assert hop == 512


# ============================================================================
# get_preset_by_name + validate_peak_threshold_db
# ============================================================================


def test_get_preset_by_name_returns_dataclass():
    p = get_preset_by_name("ultra")
    assert isinstance(p, ResolutionPreset)
    assert p.name == "ultra"


def test_get_preset_by_name_unknown_raises():
    with pytest.raises(InvalidPresetError, match="inconnu"):
        get_preset_by_name("frobnicate")


def test_validate_peak_threshold_accepts_range_endpoints():
    validate_peak_threshold_db(PEAK_THRESHOLD_MIN_DB)  # -80
    validate_peak_threshold_db(PEAK_THRESHOLD_MAX_DB)  # -40
    validate_peak_threshold_db(-70.0)  # default
    # No exception = pass


@pytest.mark.parametrize("bad_value", [-100.0, -85.0, -39.9, 0.0, -200.0])
def test_validate_peak_threshold_rejects_out_of_range(bad_value):
    with pytest.raises(InvalidThresholdError):
        validate_peak_threshold_db(bad_value)


# ============================================================================
# Frozen dataclass + build-time validation
# ============================================================================


def test_preset_dataclass_is_frozen():
    p = RESOLUTION_PRESETS["ultra"]
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        p.stft_n_fft = 4096  # type: ignore[misc]


def test_build_preset_rejects_non_power_of_2_n_fft():
    with pytest.raises(ValueError, match="puissance de 2"):
        _build_preset(
            name="invalid",
            description="x",
            stft_n_fft=10000,  # not power of 2
            cqt_target_fps=6,
            cqt_bins_per_octave=24,
        )


def test_build_preset_rejects_n_fft_below_min():
    with pytest.raises(ValueError, match="hors range"):
        _build_preset(
            name="invalid",
            description="x",
            stft_n_fft=1024,  # below _STFT_N_FFT_MIN=2048
            cqt_target_fps=6,
            cqt_bins_per_octave=24,
        )


def test_build_preset_rejects_cqt_fps_above_max():
    """Phase F11 bumped _CQT_FPS_MAX from 60 to 120 ; this test now uses
    121 to verify the new bound (the dedicated F11 test
    test_build_preset_rejects_cqt_fps_above_new_max also covers the
    boundary explicitly)."""
    with pytest.raises(ValueError, match="cqt_target_fps"):
        _build_preset(
            name="invalid",
            description="x",
            stft_n_fft=8192,
            cqt_target_fps=200,  # above new _CQT_FPS_MAX=120
            cqt_bins_per_octave=24,
        )


def test_build_preset_rejects_cqt_bpo_below_min():
    with pytest.raises(ValueError, match="cqt_bins_per_octave"):
        _build_preset(
            name="invalid",
            description="x",
            stft_n_fft=8192,
            cqt_target_fps=6,
            cqt_bins_per_octave=6,  # below min=12
        )


# ============================================================================
# Phase F11 — extreme preset + stft_hop_ratio paramétrable
# ============================================================================


def test_extreme_preset_meets_user_targets():
    """User targets validated 2026-05-03 :
    - 10 ms/frame CQT (= 100 fps)
    - close to 50 ms/frame STFT (= hop_samples ~2200)
    - same freq resolution as ultra/maximum (= n_fft=16384)
    """
    p = RESOLUTION_PRESETS['extreme']
    # CQT 10 ms target
    assert p.cqt_target_fps == 100
    cqt_ms = 1000.0 / p.cqt_target_fps
    assert math.isclose(cqt_ms, 10.0, rel_tol=0, abs_tol=0.01)
    # STFT ~46-50 ms target via hop_ratio=0.125
    assert p.stft_hop_ratio == 0.125
    assert p.stft_hop_samples_at_44k == 2048
    # 2048 samples at 44.1k = 46.44 ms — close to 50 ms target
    assert math.isclose(p.stft_hop_ms_at_44k, 46.44, rel_tol=0, abs_tol=0.5)
    # Freq resolution preserved (same n_fft as maximum)
    assert p.stft_n_fft == 16384
    assert math.isclose(p.stft_delta_freq_hz_at_44k, 2.69, rel_tol=0, abs_tol=0.01)


@pytest.mark.parametrize("name", ["economy", "standard", "fine", "ultra", "maximum"])
def test_historic_5_presets_have_default_hop_ratio_025(name):
    """Backward compat strict : the 5 historic presets must keep the
    v2.7.0 hop ratio (0.25 = n_fft / 4 = overlap 75%). Phase F11 added
    stft_hop_ratio as a paramètre but defaults to 0.25 for all 5."""
    p = RESOLUTION_PRESETS[name]
    assert p.stft_hop_ratio == 0.25, (
        f"{name} must have hop_ratio=0.25 to preserve v2.7.0 byte-identical "
        f"output. Got {p.stft_hop_ratio}."
    )


def test_extreme_preset_overrides_hop_ratio():
    """extreme is the only preset overriding the 0.25 default."""
    p = RESOLUTION_PRESETS['extreme']
    assert p.stft_hop_ratio == 0.125


def test_build_preset_rejects_cqt_fps_above_new_max():
    """Phase F11 bumped _CQT_FPS_MAX from 60 to 120. Verify the new bound."""
    from resolution_presets import _build_preset
    # 121 should be rejected (just over the new max of 120)
    with pytest.raises(ValueError, match="cqt_target_fps"):
        _build_preset(
            name="too_fast",
            description="too fast",
            stft_n_fft=8192,
            cqt_target_fps=121,
            cqt_bins_per_octave=24,
        )
    # 120 should be accepted (= new max)
    p = _build_preset(
        name="at_max",
        description="at max",
        stft_n_fft=8192,
        cqt_target_fps=120,
        cqt_bins_per_octave=24,
    )
    assert p.cqt_target_fps == 120


def test_build_preset_rejects_invalid_hop_ratio():
    """Phase F11 added stft_hop_ratio validation in [0.0625, 0.5]."""
    from resolution_presets import _build_preset
    with pytest.raises(ValueError, match="stft_hop_ratio"):
        _build_preset(
            name="bad_hop",
            description="hop_ratio out of range",
            stft_n_fft=8192,
            cqt_target_fps=6,
            cqt_bins_per_octave=24,
            stft_hop_ratio=0.05,  # below min 0.0625
        )
    with pytest.raises(ValueError, match="stft_hop_ratio"):
        _build_preset(
            name="bad_hop2",
            description="hop_ratio out of range",
            stft_n_fft=8192,
            cqt_target_fps=6,
            cqt_bins_per_octave=24,
            stft_hop_ratio=0.6,  # above max 0.5
        )


# ============================================================================
# Reference sample rate constant
# ============================================================================


def test_reference_sample_rate_is_44100():
    """Presets are documented with values at 44.1 kHz reference. Helpers
    use this constant for the at_44k properties."""
    assert REFERENCE_SAMPLE_RATE == 44100
