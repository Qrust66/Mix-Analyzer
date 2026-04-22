#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for Feature 1 phase F1c2a — pure peak-following helpers.

Targets the four pure functions shipped in F1c1a:

    _scale_gain_by_amplitude
    _scale_q_by_peak_width
    _collect_active_peak_frames
    _build_peak_following_curves

These tests are unit-level (no ``.als`` I/O, no XML) and exercise
the logic in isolation so a future regression in the helpers is
caught quickly without having to reparse a full project. Integration
tests that exercise the helpers end-to-end through the writer ship
in F1c2b.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from spectral_evolution import PeakTrajectory  # noqa: E402

from cde_apply import (  # noqa: E402
    _collect_active_peak_frames,
    _scale_gain_by_amplitude,
)


# ---------------------------------------------------------------------------
# _scale_gain_by_amplitude
# ---------------------------------------------------------------------------
#
# Formula under test:
#     scale = (peak_amp_db - threshold_db) / abs(threshold_db)
#     scale = clip(scale, 0, 1)
#     return target_gain_db * scale
#
# With target=-6, threshold=-30:
#     peak=-5   → scale = 25/30 ≈ 0.833 → -5.0 dB
#     peak=-25  → scale =  5/30 ≈ 0.167 → -1.0 dB
#     peak=-35  → below threshold       →  0.0 dB

def test_scale_gain_by_amplitude_strong_peak():
    """A hot peak at -5 dB gets close to the full target cut."""
    got = _scale_gain_by_amplitude(
        target_gain_db=-6.0, peak_amp_db=-5.0, threshold_db=-30.0,
    )
    # scale = 25/30, target * scale = -6 * 0.833... = -5.0
    assert got == pytest.approx(-5.0, abs=0.1)


def test_scale_gain_by_amplitude_weak_peak():
    """A marginal peak at -25 dB only gets a light cut."""
    got = _scale_gain_by_amplitude(
        target_gain_db=-6.0, peak_amp_db=-25.0, threshold_db=-30.0,
    )
    # scale = 5/30, target * scale = -6 * 0.166... = -1.0
    assert got == pytest.approx(-1.0, abs=0.1)


def test_scale_gain_by_amplitude_below_threshold_returns_zero():
    """Peaks quieter than ``threshold_db`` must not be cut — the band
    stays neutral at 0 dB for that frame."""
    got = _scale_gain_by_amplitude(
        target_gain_db=-6.0, peak_amp_db=-35.0, threshold_db=-30.0,
    )
    assert got == 0.0


# ---------------------------------------------------------------------------
# _collect_active_peak_frames
# ---------------------------------------------------------------------------

def test_collect_active_peak_frames_filters_by_section_and_threshold():
    """Double filtering: a point is kept only if
    (a) its frame time falls inside at least one section range
    (b) its amp_db rises above ``threshold_db``.

    The test builds four points engineered to cover every combination:

        ┌───────────────────┬───────────────────────┬────────────┐
        │ frame (beats)     │ in section [0, 16]?   │ above -30? │
        ├───────────────────┼───────────────────────┼────────────┤
        │ frame 5  (5.3 b)  │ YES                   │ YES        │  ← KEEP
        │ frame 10 (10.7 b) │ YES                   │ NO         │  drop
        │ frame 20 (21.3 b) │ NO                    │ YES        │  drop
        │ frame 30 (32.0 b) │ NO                    │ NO         │  drop
        └───────────────────┴───────────────────────┴────────────┘

    Expected output: one tuple for frame 5.
    """
    traj = PeakTrajectory(points=[
        (5,  247.0,  -5.0),   # in section, above threshold → KEEP
        (10, 247.0, -40.0),   # in section, below threshold → drop
        (20, 247.0,  -5.0),   # out of section              → drop
        (30, 247.0, -40.0),   # out of section + below       → drop
    ])
    times = np.arange(40) * 0.5   # 40 frames, 0.5 s spacing → 20 s total
    tempo_bpm = 128.0
    section_ranges_beats = [(0.0, 16.0)]

    active = _collect_active_peak_frames(
        [traj],
        section_ranges_beats=section_ranges_beats,
        times=times,
        tempo=tempo_bpm,
        threshold_db=-30.0,
    )

    assert len(active) == 1
    frame_idx, freq_hz, amp_db = active[0]
    assert frame_idx == 5
    assert freq_hz == pytest.approx(247.0)
    assert amp_db == pytest.approx(-5.0)
