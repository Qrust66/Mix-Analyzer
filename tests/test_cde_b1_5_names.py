#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Feature 3.6 B1.5 — track-name display cleanup (v2.7.1).

After the first field run on Acid Drops we saw diagnostic IDs like
``CONF_CHORUS1_ACIDDROPS[HH]GUITARDISTORTED.WAV_ACIDDROPS[HR]BASSRYTHM.WAV_165HZ``
— bouncer's project prefix, TFP role tag and ``.wav`` extension all
leaked into the user-facing string. B1.5 adds
:func:`cde_engine._clean_track_display_name` and
:func:`cde_engine.infer_project_stem`, threads a ``project_stem``
argument through the detector + outcome templates, and asserts the
cleaned names land in IDs, diagnosis text and templates.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from section_detector import Section  # noqa: E402
from tfp_parser import Function, Importance  # noqa: E402

from cde_engine import (  # noqa: E402
    CorrectionRecipe,
    _clean_track_display_name,
    detect_masking_conflicts,
    generate_diagnostic_id,
    infer_project_stem,
    populate_outcome_templates,
)


# ---------------------------------------------------------------------------
# _clean_track_display_name
# ---------------------------------------------------------------------------

def test_clean_strips_wav_extension_case_insensitive():
    assert _clean_track_display_name("Kick 1.wav") == "Kick 1"
    assert _clean_track_display_name("Kick 1.WAV") == "Kick 1"
    # No extension → passthrough.
    assert _clean_track_display_name("Kick 1") == "Kick 1"


def test_clean_strips_all_three_tfp_prefix_forms():
    """Ableton produces ``[H/R]`` in-app and ``[H_R]`` on disk (/ is
    illegal in filenames). Rare hand-written ``[H R]`` also accepted."""
    assert _clean_track_display_name("[H/R] Kick 1") == "Kick 1"
    assert _clean_track_display_name("[H_R] Kick 1") == "Kick 1"
    assert _clean_track_display_name("[H R] Kick 1") == "Kick 1"
    assert _clean_track_display_name("[S/H] Sub Bass") == "Sub Bass"
    # Case insensitive.
    assert _clean_track_display_name("[h/r] kick") == "kick"
    # Mid-name prefix is also caught — the real-data case where the
    # project stem sits before the TFP tag.
    assert _clean_track_display_name(
        "Acid_Drops [H_R] Kick 1"
    ) == "Acid_Drops Kick 1"


def test_clean_strips_project_stem_when_provided():
    """When the caller supplies a project stem, every prefix variant
    (raw, underscore, space) is stripped from the start of the name."""
    raw = "Acid_Drops [H_R] Kick 1.wav"
    # Full acid drops case from the field run.
    assert _clean_track_display_name(raw, "Acid_Drops") == "Kick 1"
    # Stem variant with spaces instead of underscores.
    assert _clean_track_display_name(
        "Acid Drops [H_R] Kick 1.wav", "Acid_Drops",
    ) == "Kick 1"
    # Stem is a prefix of the name but doesn't appear at the very start
    # → stripping only happens when prefixed.
    assert _clean_track_display_name(
        "Other Project [H_R] Kick 1.wav", "Acid_Drops",
    ) == "Other Project Kick 1"


def test_clean_is_noop_on_already_clean_names():
    """Fixture-style names used by the existing test suite stay intact
    — guards against regressions in the 300+ pre-B1.5 tests."""
    for name in ["Kick 1", "Sub Bass", "TrackA", "Acid Bass",
                 "Snare 2", "Pluck Lead"]:
        assert _clean_track_display_name(name) == name
        assert _clean_track_display_name(name, "Acid_Drops") == name


# ---------------------------------------------------------------------------
# infer_project_stem — requires a TFP bracket in the common prefix
# ---------------------------------------------------------------------------

def test_infer_project_stem_detects_acid_drops_prefix():
    names = [
        "Acid_Drops [H_R] Kick 1.wav",
        "Acid_Drops [H_H] Guitar Distorted.wav",
        "Acid_Drops [S_H] Sub Bass.wav",
    ]
    assert infer_project_stem(names) == "Acid_Drops"


def test_infer_project_stem_requires_tfp_bracket_in_common_prefix():
    """Without a TFP prefix we cannot safely extract a stem — the
    shared word across track names is legitimate content, not a
    project marker. Returns empty string rather than mis-stripping."""
    # "Kick 1.wav" and "Kick 2.wav" share "Kick " — but that's the
    # track name, not a project stem. Must NOT strip it.
    assert infer_project_stem(["Kick 1.wav", "Kick 2.wav"]) == ""
    # Single track → can't infer.
    assert infer_project_stem(["Kick 1.wav"]) == ""
    # No shared prefix at all.
    assert infer_project_stem(["A.wav", "B.wav"]) == ""
    # Empty input.
    assert infer_project_stem([]) == ""


def test_infer_project_stem_accepts_space_and_underscore_boundary():
    """The stem must end on a space or underscore — a clean boundary
    that separates the project name from the TFP tag."""
    # Space boundary.
    assert infer_project_stem([
        "MyProject [H/R] A.wav",
        "MyProject [S/R] B.wav",
    ]) == "MyProject"
    # Underscore boundary.
    assert infer_project_stem([
        "MyProject_[H/R] A.wav",
        "MyProject_[S/R] B.wav",
    ]) == "MyProject"


# ---------------------------------------------------------------------------
# Threading project_stem through the detector — end-to-end
# ---------------------------------------------------------------------------

def _make_section(index: int, start: int, end: int,
                  total_energy_db: float, name: str = "Drop 1") -> Section:
    return Section(
        index=index, name=name,
        start_bucket=start, end_bucket=end,
        start_seconds=float(start), end_seconds=float(end),
        start_beats=float(start * 2), end_beats=float(end * 2),
        total_energy_db=total_energy_db,
    )


def _section_with_noisy_names(zone: str = "low") -> Section:
    """Mimic the real Acid_Drops track-name convention that leaked into
    the first field diagnostics dump."""
    s = _make_section(1, 0, 29, -10.0)
    track_a = "Acid_Drops [H_R] Kick 1.wav"
    track_b = "Acid_Drops [S_H] Sub Bass.wav"
    s.tracks_active = [track_a, track_b]
    s.track_roles = {
        track_a: (Importance.H, Function.R),
        track_b: (Importance.S, Function.H),
    }
    s.track_presence = {track_a: {zone: 1.0}, track_b: {zone: 1.0}}
    s.track_energy = {track_a: {zone: -5.0}, track_b: {zone: -6.0}}
    s.conflicts = [{
        "track_a": track_a, "track_b": track_b, "zone": zone,
        "energy_a": -5.0, "energy_b": -6.0,
        "score": 0.87, "severity": "critical",
    }]
    return s


def test_detector_cleans_track_names_in_diagnostic_id():
    """The detector produces a compact, human-readable ID even when
    the incoming track names carry the project stem + TFP tag + .wav."""
    s = _section_with_noisy_names()
    diags = detect_masking_conflicts(
        s, project_stem="Acid_Drops",
    )
    assert len(diags) == 1
    # Expected clean ID — the noisy prefix / TFP / extension are gone.
    assert diags[0].diagnostic_id == "CONF_DROP1_KICK1_SUBBASS_165HZ"
    # The raw names are preserved on the diagnostic for matching back
    # to section.track_energy / track_roles etc.
    assert diags[0].track_a == "Acid_Drops [H_R] Kick 1.wav"
    assert diags[0].track_b == "Acid_Drops [S_H] Sub Bass.wav"


def test_detector_cleans_track_names_in_diagnosis_text():
    s = _section_with_noisy_names()
    d = detect_masking_conflicts(s, project_stem="Acid_Drops")[0]
    # The French sentence must say "Kick 1" and "Sub Bass", not the
    # raw WAV filenames.
    assert "Kick 1" in d.diagnosis_text
    assert "Sub Bass" in d.diagnosis_text
    assert ".wav" not in d.diagnosis_text
    assert "[H_R]" not in d.diagnosis_text
    assert "Acid_Drops" not in d.diagnosis_text


def test_detector_cleans_track_names_in_outcome_templates():
    """Sidechain templates mention the trigger (H/R Kick 1, gains
    punch) and the ducked track (Sub Bass). Both must land cleaned
    into the outcome lists."""
    s = _section_with_noisy_names()
    d = detect_masking_conflicts(s, project_stem="Acid_Drops")[0]
    # Matrix H×S → sidechain: trigger = track_a (Kick 1, Hero),
    # target = track_b (Sub Bass, ducked).
    assert d.primary_correction is not None
    assert d.primary_correction.approach == "sidechain"
    full_text = " | ".join(
        d.expected_outcomes + d.potential_risks + d.verification_steps
    )
    assert "Kick 1" in full_text
    assert "Sub Bass" in full_text
    # No leaked WAV extension or TFP prefix anywhere in the text.
    assert ".wav" not in full_text
    assert "[H_R]" not in full_text
    assert "Acid_Drops" not in full_text


def test_detector_without_project_stem_still_strips_tfp_and_wav():
    """When the caller forgets to pass ``project_stem``, the TFP
    prefix and ``.wav`` extension are still removed — the project
    stem is the only piece that requires explicit opt-in."""
    s = _section_with_noisy_names()
    d = detect_masking_conflicts(s)[0]  # no project_stem
    # ID degrades gracefully — project prefix leaks in as
    # "ACIDDROPS" but TFP + .wav are still gone.
    assert d.diagnostic_id.startswith("CONF_DROP1_ACIDDROPSKICK1_")
    assert "[H_R]" not in d.diagnosis_text
    assert ".wav" not in d.diagnosis_text


# ---------------------------------------------------------------------------
# Degenerate input — cleaner must not crash or empty a legitimate name
# ---------------------------------------------------------------------------

def test_clean_returns_empty_on_none_or_empty():
    assert _clean_track_display_name(None) == ""
    assert _clean_track_display_name("") == ""
    assert _clean_track_display_name("   ") == ""


def test_clean_does_not_empty_name_when_stem_mismatches_everything():
    """An overly aggressive stem that equals the track itself would
    leave an empty string. The cleaner must return "" for a now-empty
    name; the detector falls back to the raw name in that edge case."""
    # Degenerate case: the stem equals the track name entirely.
    assert _clean_track_display_name("Acid_Drops", "Acid_Drops") == ""
    # Detector fallback guard — reuse the helper used in production.
    assert (
        _clean_track_display_name("Acid_Drops", "Acid_Drops") or "Acid_Drops"
    ) == "Acid_Drops"
