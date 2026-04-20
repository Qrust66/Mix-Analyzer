#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the per-section track-peak computation.

Covers ``mix_analyzer.compute_track_peak_by_section`` (v2.6.x).

**Assumption under test: WAV files are post-FX, post-fader** — the default
Ableton "All Individual Tracks" export. The function returns the raw
sample-peak of the section slice; it does NOT re-apply effective_gain.
Tests here check slicing, silence floor, stereo handling, and clipping
behaviour. They deliberately do NOT exercise gain application, since the
v2.6.4 fix removed that path.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import List

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub tkinter so mix_analyzer imports headless (same pattern as
# test_section_metrics.py — keep in sync).
if "tkinter" not in sys.modules:
    import types

    _tk = types.ModuleType("tkinter")
    for _name in ("Tk", "StringVar", "BooleanVar", "IntVar", "Toplevel",
                  "Frame", "Label", "Button", "Entry", "Canvas",
                  "PhotoImage", "Widget", "Misc"):
        setattr(_tk, _name, type(_name, (), {}))
    _tk.TclError = Exception
    sys.modules["tkinter"] = _tk
    for _sub in ("ttk", "filedialog", "messagebox", "scrolledtext", "font"):
        _mod = types.ModuleType(f"tkinter.{_sub}")
        sys.modules[f"tkinter.{_sub}"] = _mod
        setattr(_tk, _sub, _mod)

from mix_analyzer import (  # noqa: E402
    TRACK_PEAK_SILENCE_FLOOR_DB,
    compute_track_peak_by_section,
)
from automation_map import TrackAutomationMap  # noqa: E402


SR = 44100


@dataclass
class FakeSection:
    index: int
    start_seconds: float
    end_seconds: float


def _stereo_sine(duration_s: float, freq_hz: float = 1000.0,
                 amplitude: float = 0.5, sr: int = SR) -> np.ndarray:
    """Mono sine replicated on both channels — peak == amplitude exactly."""
    n = int(duration_s * sr)
    t = np.arange(n, dtype=np.float64) / sr
    wave = (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)
    return np.stack([wave, wave], axis=1)


def _auto_map_constant(gain: float, duration_s: float = 60.0,
                       name: str = "Track") -> TrackAutomationMap:
    """Build a TrackAutomationMap whose effective_gain is a single flat value."""
    return TrackAutomationMap(
        track_name=name,
        curves=[],
        effective_gain=np.array([gain], dtype=np.float64),
        effective_gain_times=np.array([0.0], dtype=np.float64),
        is_audible=np.array([gain >= 1e-3], dtype=bool),
    )


def _auto_map_ramp(g_start: float, g_end: float, duration_s: float = 20.0,
                   n_points: int = 201, name: str = "Track") -> TrackAutomationMap:
    """Linear gain ramp from g_start to g_end over [0, duration_s]."""
    times = np.linspace(0.0, duration_s, n_points)
    values = np.linspace(g_start, g_end, n_points)
    return TrackAutomationMap(
        track_name=name,
        curves=[],
        effective_gain=values,
        effective_gain_times=times,
        is_audible=values >= 1e-3,
    )


def _analysis(data: np.ndarray, name: str, sr: int = SR, type_: str = "Individual"):
    """Build an (analysis_dict, track_info) pair mimicking mix_analyzer.analyze_track."""
    return (
        {"_data": data, "sample_rate": sr, "filename": name},
        {"name": name, "type": type_},
    )


# ---------------------------------------------------------------------------
# Baseline: sinus at known amplitude, gain = 1.0 -> peak = 20*log10(amp)
# ---------------------------------------------------------------------------

def test_sine_without_gain_map_returns_raw_peak_dbfs():
    """Amplitude 0.5 (≈ -6 dBFS) on a track with no auto_map must yield ~-6 dB."""
    data = _stereo_sine(duration_s=5.0, amplitude=0.5)
    sections = [FakeSection(1, 0.0, 5.0)]

    result = compute_track_peak_by_section(
        [_analysis(data, "Kick.wav")], sections, auto_maps=None,
    )
    assert set(result) == {"Kick.wav"}
    peak = result["Kick.wav"][1]
    expected = 20 * np.log10(0.5)  # -6.0206...
    assert peak == pytest.approx(expected, abs=0.2)


def test_auto_maps_does_not_affect_peak_v264_post_fader_assumption():
    """v2.6.4 regression guard: even if auto_maps is passed, the function
    must NOT apply effective_gain. Ableton's "All Individual Tracks" export
    already bakes the fader into the WAV — applying gain on top would
    double-attenuate (the pre-v2.6.4 bug that surfaced in Acid Drops
    testing: Spoon Percussion read -29.5 dB instead of her ~-19 dB meter)."""
    data = _stereo_sine(duration_s=5.0, amplitude=0.5)  # WAV peak = -6 dBFS
    sections = [FakeSection(1, 0.0, 5.0)]
    # auto_map with gain 0.5 (-6 dB) — if re-applied, result would be -12 dB
    auto_maps_with_gain = {"Kick": _auto_map_constant(0.5)}

    result_with = compute_track_peak_by_section(
        [_analysis(data, "Kick.wav")], sections,
        auto_maps=auto_maps_with_gain,
    )
    result_without = compute_track_peak_by_section(
        [_analysis(data, "Kick.wav")], sections, auto_maps=None,
    )
    # Both paths must produce the same peak — the raw WAV peak (-6 dB)
    assert result_with["Kick.wav"][1] == pytest.approx(-6.0, abs=0.2)
    assert result_without["Kick.wav"][1] == pytest.approx(-6.0, abs=0.2)


def test_silent_slice_returns_none():
    """Amplitude below the silence floor => None. Uses a very quiet WAV
    (1e-5 ≈ -100 dBFS) so the silence floor triggers regardless of gain."""
    sr = SR
    n = int(1.0 * sr)
    quiet = (np.full((n, 2), 1e-5, dtype=np.float32))
    sections = [FakeSection(1, 0.0, 1.0)]
    result = compute_track_peak_by_section(
        [_analysis(quiet, "T.wav")], sections, auto_maps=None,
    )
    assert result["T.wav"][1] is None


def test_zero_audio_returns_none():
    """All-zero WAV with gain 1.0 -> peak_lin == 0 -> None (not -inf)."""
    data = np.zeros((SR, 2), dtype=np.float32)
    sections = [FakeSection(1, 0.0, 1.0)]
    result = compute_track_peak_by_section(
        [_analysis(data, "T.wav")], sections, auto_maps=None,
    )
    assert result["T.wav"][1] is None


def test_clipping_yields_positive_db():
    """Amplitude 1.2 -> 20*log10(1.2) ≈ +1.58 dBFS.

    The function must return the raw (positive) value — the sheet-layer
    renders it with a '+' prefix so the user sees clipping without us
    silently muting the signal.
    """
    data = _stereo_sine(duration_s=1.0, amplitude=1.2)
    sections = [FakeSection(1, 0.0, 1.0)]

    result = compute_track_peak_by_section(
        [_analysis(data, "T.wav")], sections, auto_maps=None,
    )
    peak = result["T.wav"][1]
    assert peak is not None
    assert peak > 0.0
    assert peak == pytest.approx(20 * np.log10(1.2), abs=0.1)


def test_non_individual_tracks_are_skipped():
    """Full Mix / BUS tracks must not appear in the output dict."""
    data = _stereo_sine(1.0)
    sections = [FakeSection(1, 0.0, 1.0)]
    result = compute_track_peak_by_section(
        [
            _analysis(data, "Kick.wav", type_="Individual"),
            _analysis(data, "MixBus.wav", type_="BUS"),
            _analysis(data, "FullMix.wav", type_="Full Mix"),
        ],
        sections, auto_maps=None,
    )
    assert set(result) == {"Kick.wav"}


def test_missing_auto_map_falls_back_to_raw_peak():
    """Track whose name doesn't match any auto_map entry must fall back to
    gain=1.0 (raw WAV peak) rather than crashing or returning None."""
    data = _stereo_sine(1.0, amplitude=0.25)  # -12 dBFS
    sections = [FakeSection(1, 0.0, 1.0)]
    # auto_maps has a different track name -> no match for "Orphan"
    auto_maps = {"SomethingElse": _auto_map_constant(0.1)}

    result = compute_track_peak_by_section(
        [_analysis(data, "Orphan.wav")], sections, auto_maps=auto_maps,
    )
    peak = result["Orphan.wav"][1]
    # Should NOT have the 0.1 gain applied (that would give ~-32 dB);
    # should be the raw -12 dBFS.
    assert peak == pytest.approx(20 * np.log10(0.25), abs=0.3)


def test_section_out_of_range_is_clamped_not_crashing():
    """end_seconds past the audio length -> clamped slice, still computable."""
    data = _stereo_sine(duration_s=2.0, amplitude=0.5)
    sections = [
        FakeSection(1, 0.0, 1.0),
        FakeSection(2, 1.5, 999.0),  # end past audio
    ]
    result = compute_track_peak_by_section(
        [_analysis(data, "T.wav")], sections, auto_maps=None,
    )
    assert result["T.wav"][1] == pytest.approx(20 * np.log10(0.5), abs=0.2)
    assert result["T.wav"][2] == pytest.approx(20 * np.log10(0.5), abs=0.2)


def test_zero_length_section_returns_none():
    data = _stereo_sine(1.0)
    sections = [FakeSection(1, 0.5, 0.5)]
    result = compute_track_peak_by_section(
        [_analysis(data, "T.wav")], sections, auto_maps=None,
    )
    assert result["T.wav"][1] is None


def test_empty_inputs_return_empty_dict():
    assert compute_track_peak_by_section([], [FakeSection(1, 0, 1)], None) == {}
    data = _stereo_sine(1.0)
    assert compute_track_peak_by_section(
        [_analysis(data, "T.wav")], [], None
    ) == {}


def test_silence_floor_constant_is_negative_ninety():
    """The user validated -90 dB in Phase A. Document it as a test so a
    future tweak of the constant surfaces a deliberate discussion."""
    assert TRACK_PEAK_SILENCE_FLOOR_DB == -90.0
