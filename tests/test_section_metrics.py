#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for per-section metrics rendered in the Mix Health Score sheet.

Covers ``mix_analyzer.compute_section_metrics`` (v2.6.x) — slicing of the
full-mix audio, LUFS/PLR masking on short sections, and consistency of the
per-section totals against the global metrics.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import List

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# mix_analyzer imports tkinter at module top-level for the GUI. The metric
# functions under test don't use any Tk widget — they only need numpy / scipy
# / pyloudnorm / librosa. Stub tkinter before import so headless CI can run.
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
    SECTION_LUFS_MIN_SECONDS,
    analyze_loudness,
    analyze_stereo,
    compute_section_metrics,
)


@dataclass
class FakeSection:
    name: str
    start_seconds: float
    end_seconds: float
    tracks_active: List[str] = None


def _make_stereo_noise(duration_s: float, sr: int = 44100,
                      amplitude: float = 0.2, seed: int = 0) -> np.ndarray:
    """Stereo white noise — enough signal for all metrics to produce finite values."""
    rng = np.random.default_rng(seed)
    n = int(duration_s * sr)
    data = rng.standard_normal((n, 2)).astype(np.float32) * amplitude
    return data


def test_empty_sections_returns_empty_list():
    data = _make_stereo_noise(10.0)
    assert compute_section_metrics(data, 44100, []) == []


def test_none_inputs_return_empty_list():
    assert compute_section_metrics(None, 44100, [FakeSection("X", 0, 1)]) == []
    assert compute_section_metrics(_make_stereo_noise(2.0), None,
                                    [FakeSection("X", 0, 1)]) == []


def test_section_slicing_produces_one_row_per_section():
    data = _make_stereo_noise(20.0)
    sections = [
        FakeSection("Intro", 0.0, 5.0, tracks_active=["Kick"]),
        FakeSection("Drop", 5.0, 15.0, tracks_active=["Kick", "Bass"]),
        FakeSection("Outro", 15.0, 20.0),
    ]
    result = compute_section_metrics(data, 44100, sections)
    assert len(result) == 3
    assert [r['name'] for r in result] == ["Intro", "Drop", "Outro"]
    assert result[0]['tracks_active'] == ["Kick"]
    assert result[1]['tracks_active'] == ["Kick", "Bass"]
    assert result[2]['tracks_active'] == []  # None coerced to []


def test_short_section_lufs_and_plr_are_none_other_metrics_valid():
    """A section shorter than SECTION_LUFS_MIN_SECONDS must yield None for
    LUFS and PLR, but True Peak, Crest, Width, Correlation remain computable
    (pyloudnorm True Peak / Crest are NOT integrated-loudness-gated)."""
    assert SECTION_LUFS_MIN_SECONDS >= 1.0
    duration = SECTION_LUFS_MIN_SECONDS - 0.5  # comfortably short
    data = _make_stereo_noise(duration + 0.1)
    sections = [FakeSection("Tiny", 0.0, duration)]
    result = compute_section_metrics(data, 44100, sections)
    assert len(result) == 1
    row = result[0]
    assert row['lufs'] is None
    assert row['plr'] is None
    # These must still be finite numbers on a short slice
    assert np.isfinite(row['true_peak_db'])
    assert np.isfinite(row['crest'])
    assert np.isfinite(row['width'])
    assert np.isfinite(row['correlation'])


def test_long_section_produces_finite_lufs_and_plr():
    """Sections ≥ SECTION_LUFS_MIN_SECONDS should get real numeric LUFS/PLR."""
    duration = SECTION_LUFS_MIN_SECONDS + 1.0
    data = _make_stereo_noise(duration + 0.5)
    sections = [FakeSection("LongEnough", 0.0, duration)]
    result = compute_section_metrics(data, 44100, sections)
    assert len(result) == 1
    row = result[0]
    assert row['lufs'] is not None
    assert row['plr'] is not None
    assert np.isfinite(row['lufs'])
    assert np.isfinite(row['plr'])


def test_per_section_metrics_roughly_match_global():
    """Sanity: a weighted average of per-section metrics should land near the
    global metrics computed over the full audio. Not an exact equality (LUFS
    uses BS.1770 gating which is non-linear), but the order of magnitude has
    to match — catches accidental unit / slicing bugs."""
    duration = 20.0
    sr = 44100
    data = _make_stereo_noise(duration)
    # Three equal-length sections covering the whole file
    sections = [
        FakeSection("A", 0.0, duration / 3),
        FakeSection("B", duration / 3, 2 * duration / 3),
        FakeSection("C", 2 * duration / 3, duration),
    ]
    result = compute_section_metrics(data, sr, sections)
    assert len(result) == 3

    global_loud = analyze_loudness(data, sr)
    global_stereo = analyze_stereo(data, sr)

    # Weighted-average LUFS in dB space: this is NOT the correct way to pool
    # BS.1770 loudness (you'd need to pool in linear power space and regate),
    # but for uniform-amplitude white noise the difference is tiny.
    total = sum(r['duration_s'] for r in result)
    avg_lufs = sum(r['lufs'] * r['duration_s'] for r in result) / total
    assert abs(avg_lufs - global_loud['lufs_integrated']) < 2.0  # within 2 LU

    # True Peak of the full mix must be ≥ the max of per-section true peaks
    # (because per-section TP is computed on strict subsets)
    per_section_max_tp = max(r['true_peak_db'] for r in result)
    assert global_loud['true_peak_db'] >= per_section_max_tp - 0.5

    # Correlation: white noise is ~0, all sections should be close
    for r in result:
        assert abs(r['correlation'] - global_stereo['correlation']) < 0.2


def test_sections_out_of_range_are_clamped():
    """Section end_seconds past the audio length should clamp, not crash."""
    data = _make_stereo_noise(5.0)
    sections = [
        FakeSection("Inside", 0.0, 3.0),
        FakeSection("PastEnd", 4.0, 999.0),  # end > audio duration
    ]
    result = compute_section_metrics(data, 44100, sections)
    assert len(result) == 2
    # Both must have a positive duration and finite metrics
    for r in result:
        assert r['duration_s'] > 0
        assert np.isfinite(r['true_peak_db'])


def test_zero_length_section_is_skipped():
    """start == end -> no row emitted rather than a zero-duration artifact."""
    data = _make_stereo_noise(5.0)
    sections = [
        FakeSection("Real", 0.0, 2.0),
        FakeSection("Empty", 3.0, 3.0),   # zero length
        FakeSection("Inverted", 4.0, 3.5),  # inverted: end < start
    ]
    result = compute_section_metrics(data, 44100, sections)
    assert [r['name'] for r in result] == ["Real"]


def test_mono_input_returns_default_stereo_metrics():
    """Mono audio (shape (N,) or (N, 1)) should not crash and should yield
    conventional stereo defaults (width=0, correlation=1)."""
    sr = 44100
    data = (np.random.default_rng(1).standard_normal(int(5 * sr)).astype(np.float32)
            * 0.2).reshape(-1, 1)
    sections = [FakeSection("Mono", 0.0, 4.0)]
    result = compute_section_metrics(data, sr, sections)
    assert len(result) == 1
    assert result[0]['width'] == 0.0
    assert result[0]['correlation'] == 1.0
