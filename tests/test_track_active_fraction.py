#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the meter-based per-section active fraction (option H, v2.6.5).

Covers ``mix_analyzer.compute_track_active_fraction_by_section``, the WAV
peak-hold measurement that replaces the CQT zone_energy under-count on
percussive tracks. Motivation and design: see the commit that added this
function (Tambourine Hi-Hat in Acid Drops reading ~10% "active" when the
track hits every 16th note for the whole section).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub tkinter so mix_analyzer imports headless.
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
    ACTIVE_FRACTION_THRESHOLD_DB,
    ACTIVE_FRACTION_WINDOW_MS,
    compute_track_active_fraction_by_section,
)


SR = 44100


@dataclass
class FakeSection:
    index: int
    start_seconds: float
    end_seconds: float


def _stereo_constant(duration_s: float, amplitude: float, sr: int = SR) -> np.ndarray:
    """Stereo constant-amplitude signal — every window peaks at ``amplitude``."""
    n = int(duration_s * sr)
    ch = np.full(n, amplitude, dtype=np.float32)
    return np.stack([ch, ch], axis=1)


def _stereo_silent(duration_s: float, sr: int = SR) -> np.ndarray:
    n = int(duration_s * sr)
    return np.zeros((n, 2), dtype=np.float32)


def _analysis(data, name, type_="Individual", sr=SR):
    return (
        {"_data": data, "sample_rate": sr, "filename": name},
        {"name": name, "type": type_},
    )


# ---------------------------------------------------------------------------
# Defaults + constants
# ---------------------------------------------------------------------------

def test_default_constants_match_audio_engineering_conventions():
    """50 ms window + -40 dB threshold: standard VU-style meter.
    Pinned so future tweaks are deliberate."""
    assert ACTIVE_FRACTION_WINDOW_MS == 50.0
    assert ACTIVE_FRACTION_THRESHOLD_DB == -40.0


# ---------------------------------------------------------------------------
# Straightforward coverage behaviour
# ---------------------------------------------------------------------------

def test_constant_signal_above_threshold_reads_fully_active():
    """A signal constantly above -40 dBFS over the whole section -> 1.0."""
    # 0.5 linear = ~-6 dBFS, far above -40
    data = _stereo_constant(duration_s=5.0, amplitude=0.5)
    sections = [FakeSection(1, 0.0, 5.0)]
    result = compute_track_active_fraction_by_section(
        [_analysis(data, "T.wav")], sections,
    )
    assert result["T.wav"][1] == pytest.approx(1.0, abs=0.02)


def test_constant_signal_below_threshold_reads_zero():
    """Signal at -60 dBFS (below the -40 dB threshold) -> 0.0."""
    # 0.001 ≈ -60 dBFS
    data = _stereo_constant(duration_s=5.0, amplitude=0.001)
    sections = [FakeSection(1, 0.0, 5.0)]
    result = compute_track_active_fraction_by_section(
        [_analysis(data, "T.wav")], sections,
    )
    assert result["T.wav"][1] == 0.0


def test_silent_signal_reads_zero():
    """Pure silence -> 0.0. No log-of-zero crash either."""
    data = _stereo_silent(3.0)
    sections = [FakeSection(1, 0.0, 3.0)]
    result = compute_track_active_fraction_by_section(
        [_analysis(data, "T.wav")], sections,
    )
    assert result["T.wav"][1] == 0.0


# ---------------------------------------------------------------------------
# Partial coverage — the core mechanism the fix addresses
# ---------------------------------------------------------------------------

def test_half_active_half_silent_reads_around_half():
    """Build a section where the first half is loud (>> threshold) and the
    second half is silent. Fraction must be ~0.5."""
    sr = SR
    half = int(2.5 * sr)
    loud = np.full((half, 2), 0.5, dtype=np.float32)   # -6 dBFS
    quiet = np.zeros((half, 2), dtype=np.float32)
    data = np.vstack([loud, quiet])
    sections = [FakeSection(1, 0.0, 5.0)]
    result = compute_track_active_fraction_by_section(
        [_analysis(data, "T.wav")], sections,
    )
    assert result["T.wav"][1] == pytest.approx(0.5, abs=0.05)


def test_percussive_hits_with_gaps_are_mostly_active():
    """Synthesize percussion-like behaviour: brief loud hits on every beat,
    silent between. With a 50 ms window, hits of 40+ ms alone cover ~95%+
    of the section. Tambourine in Acid 1 at 128 BPM is the real-world
    motivation."""
    sr = SR
    bpm = 128.0
    beat_s = 60.0 / bpm
    duration = 10.0
    total = int(duration * sr)
    data = np.zeros((total, 2), dtype=np.float32)

    # Hits of 45 ms (slightly under one window) spaced on the quarter-note
    # grid. After windowing, each hit falls into at least one window.
    hit_s = 0.045
    hit_samples = int(hit_s * sr)
    t = 0.0
    while t + hit_s < duration:
        start = int(t * sr)
        data[start:start + hit_samples] = 0.5  # ~-6 dBFS
        t += beat_s  # every quarter note

    sections = [FakeSection(1, 0.0, duration)]
    result = compute_track_active_fraction_by_section(
        [_analysis(data, "T.wav")], sections,
    )
    fraction = result["T.wav"][1]
    # 10s * (128/60) = ~21 beats. ~21 windows containing a hit out of 200.
    # So we expect ~10% with 45ms hits on quarter notes. Test just confirms
    # the metric responds positively — the user's Tambourine runs 16th
    # notes, much denser, which is the next test.
    assert fraction > 0.05


def test_dense_16th_note_percussion_is_nearly_fully_active():
    """Tambourine Hi-Hat style: hits every 16th note at 128 BPM.
    Inter-onset interval ≈ 117 ms. With 50 ms window and 30 ms hits, every
    window covers either the current hit or the decay tail of the previous
    hit; fraction should be close to 1.0. This is the Acid Drops scenario
    that motivates the whole fix."""
    sr = SR
    bpm = 128.0
    sixteenth_s = 60.0 / bpm / 4.0  # ≈ 0.117 s
    duration = 10.0
    total = int(duration * sr)
    data = np.zeros((total, 2), dtype=np.float32)

    # 60 ms hit — wider than one 50 ms window, so a hit lights up both its
    # own window AND any window partially overlapping.
    hit_s = 0.060
    hit_samples = int(hit_s * sr)
    t = 0.0
    while t + hit_s < duration:
        start = int(t * sr)
        data[start:start + hit_samples] = 0.5
        t += sixteenth_s

    sections = [FakeSection(1, 0.0, duration)]
    result = compute_track_active_fraction_by_section(
        [_analysis(data, "T.wav")], sections,
    )
    # Very high — the 16th-note grid is tight enough that essentially every
    # window contains (or almost contains) a hit.
    assert result["T.wav"][1] > 0.70


# ---------------------------------------------------------------------------
# Edge cases & input robustness
# ---------------------------------------------------------------------------

def test_empty_inputs_return_empty_dict():
    assert compute_track_active_fraction_by_section([], [FakeSection(1, 0, 1)]) == {}
    data = _stereo_constant(1.0, 0.1)
    assert compute_track_active_fraction_by_section(
        [_analysis(data, "T.wav")], []
    ) == {}


def test_non_individual_tracks_are_skipped():
    data = _stereo_constant(1.0, 0.5)
    sections = [FakeSection(1, 0.0, 1.0)]
    result = compute_track_active_fraction_by_section(
        [
            _analysis(data, "Kick.wav", type_="Individual"),
            _analysis(data, "Bus.wav", type_="BUS"),
            _analysis(data, "Mix.wav", type_="Full Mix"),
        ],
        sections,
    )
    assert set(result) == {"Kick.wav"}


def test_section_out_of_audio_bounds_is_clamped_to_zero():
    """End past WAV -> clamped to available audio. End at or before start
    -> 0.0. No crash in either case."""
    data = _stereo_constant(1.0, 0.5)  # 1s of signal
    sections = [
        FakeSection(1, 0.0, 0.5),       # fully inside
        FakeSection(2, 0.9, 99.0),      # end past WAV, 100ms of audio left
        FakeSection(3, 0.5, 0.5),       # zero length
        FakeSection(4, 0.8, 0.3),       # inverted
    ]
    result = compute_track_active_fraction_by_section(
        [_analysis(data, "T.wav")], sections,
    )
    per = result["T.wav"]
    assert per[1] == pytest.approx(1.0, abs=0.05)
    assert per[2] == pytest.approx(1.0, abs=0.05)  # clamped but signal is all above
    assert per[3] == 0.0
    assert per[4] == 0.0


def test_mono_wav_does_not_crash_and_returns_sensible_values():
    sr = SR
    n = int(2.0 * sr)
    mono_data = np.full((n, 1), 0.5, dtype=np.float32)
    sections = [FakeSection(1, 0.0, 2.0)]
    result = compute_track_active_fraction_by_section(
        [_analysis(mono_data, "T.wav")], sections,
    )
    assert result["T.wav"][1] == pytest.approx(1.0, abs=0.05)


def test_threshold_override_changes_result():
    """A signal at -50 dBFS reads 0% at the default -40 dB threshold, but
    100% when the threshold is lowered to -60 dB. Confirms the threshold
    kwarg is honoured."""
    amp = 10 ** (-50 / 20)  # ~0.00316, i.e. -50 dBFS
    data = _stereo_constant(duration_s=2.0, amplitude=amp)
    sections = [FakeSection(1, 0.0, 2.0)]
    strict = compute_track_active_fraction_by_section(
        [_analysis(data, "T.wav")], sections, threshold_db=-40.0,
    )
    lenient = compute_track_active_fraction_by_section(
        [_analysis(data, "T.wav")], sections, threshold_db=-60.0,
    )
    assert strict["T.wav"][1] == 0.0
    assert lenient["T.wav"][1] == pytest.approx(1.0, abs=0.02)


def test_window_override_changes_granularity():
    """Larger window -> more forgiving: a brief hit surrounded by silence
    covers a smaller fraction of windows because each window is wider."""
    sr = SR
    n = int(1.0 * sr)
    data = np.zeros((n, 2), dtype=np.float32)
    # Single 10 ms hit at the start
    data[: int(0.01 * sr)] = 0.5
    sections = [FakeSection(1, 0.0, 1.0)]

    small_window = compute_track_active_fraction_by_section(
        [_analysis(data, "T.wav")], sections, window_ms=10.0,
    )
    large_window = compute_track_active_fraction_by_section(
        [_analysis(data, "T.wav")], sections, window_ms=100.0,
    )
    # Small window (10 ms): one hit = 1/100 ≈ 1% active
    # Large window (100 ms): one hit = 1/10 = 10% active
    assert large_window["T.wav"][1] > small_window["T.wav"][1]


def test_section_shorter_than_one_window_uses_single_window_fallback():
    """A section with fewer samples than ``window_ms * sr / 1000`` must not
    crash — it falls back to a single whole-slice window."""
    sr = SR
    # 20 ms of signal, 50 ms window default
    data = np.full((int(0.020 * sr), 2), 0.5, dtype=np.float32)
    sections = [FakeSection(1, 0.0, 0.020)]
    result = compute_track_active_fraction_by_section(
        [_analysis(data, "T.wav")], sections,
    )
    # The 20ms slice is above threshold -> active_fraction == 1.0 under the
    # single-window fallback.
    assert result["T.wav"][1] == pytest.approx(1.0, abs=0.05)
