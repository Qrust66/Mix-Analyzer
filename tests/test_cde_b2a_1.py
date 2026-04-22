#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Feature 3.6 B2a.1 — two fixes surfaced by the first
accumulation field run on Acid Drops:

    1. ``_resolve_zone_label_for_freq`` now range-matches instead of
       looking up an exact midpoint. Accumulations ship with the
       cluster's actual median (e.g. ``311 Hz``), which is not a zone
       midpoint, so the old exact lookup fell back to the generic
       "la bande concernée" in every single accumulation's
       diagnosis text and outcome templates.
    2. Accumulation diagnostic IDs now carry a ``_B<start_bucket>``
       suffix. A section can legitimately contain multiple
       accumulations at the same freq cluster (a pile-up that dies
       down and resumes); the old ID format produced collisions that
       broke the "stable pointer for Claude conversations" contract.

Existing non-B2a.1 behaviours that these fixes must NOT disturb:

    * Masking diagnostic IDs (unchanged — masking conflicts already
      have unique (track_a, track_b, zone) per section).
    * Zone label for masking midpoints (50, 165, 350, …) still resolves
      to the same label string.
"""

from __future__ import annotations

import os
import sys
from typing import List

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from section_detector import Section  # noqa: E402
from tfp_parser import Function, Importance  # noqa: E402

from cde_engine import (  # noqa: E402
    ZONE_BOUNDS_HZ,
    ZONE_CENTER_HZ,
    _resolve_zone_label_for_freq,
    detect_accumulation_risks,
)


# ---------------------------------------------------------------------------
# Fix 1 — zone label range match
# ---------------------------------------------------------------------------

def test_zone_label_resolves_off_midpoint_accumulation_frequencies():
    """The real Acid Drops accumulation output used 311 Hz (cluster
    median) and 247 Hz. Both must resolve to a human-readable zone."""
    assert _resolve_zone_label_for_freq(311.0) == "Mud (200-500 Hz)"
    # 246.8 sits just below the low/mud boundary (250) — low midpoint
    # (165) is closer than mud midpoint (350), so low wins.
    assert _resolve_zone_label_for_freq(246.8) == "Low (80-250 Hz)"


def test_zone_label_preserved_for_midpoints_no_regression():
    """All nine zone midpoints (the masking detector's freq values)
    must still resolve to the same label as before — no regression in
    masking diagnostics."""
    expected = {
        50:     "Sub (20-80 Hz)",
        165:    "Low (80-250 Hz)",
        350:    "Mud (200-500 Hz)",
        525:    "Body (250-800 Hz)",
        1250:   "Low-Mid (500-2 kHz)",
        2500:   "Mid (1-4 kHz)",
        3500:   "Presence (2-5 kHz)",
        7500:   "Sibilance (5-10 kHz)",
        15000:  "Air (10-20 kHz)",
    }
    for freq, label in expected.items():
        assert _resolve_zone_label_for_freq(freq) == label, (
            f"{freq} Hz drifted to {_resolve_zone_label_for_freq(freq)!r}"
        )


def test_zone_label_falls_back_when_freq_is_out_of_range():
    """Frequencies outside the instrument-relevant band
    (20-20000 Hz) or ``None`` must yield the generic fallback."""
    assert _resolve_zone_label_for_freq(None) == "la bande concernée"
    assert _resolve_zone_label_for_freq(10.0) == "la bande concernée"
    assert _resolve_zone_label_for_freq(25000.0) == "la bande concernée"


def test_zone_label_overlap_resolved_by_closest_midpoint():
    """Zone ranges overlap (Low 80-250, Mud 200-500, Body 250-800).
    The resolver picks the zone whose midpoint is closest — avoids
    surprising users with an arbitrary first-match."""
    # 220 Hz sits inside both Low and Mud; Low midpoint (165) is
    # closer than Mud midpoint (350) → Low wins.
    assert _resolve_zone_label_for_freq(220.0) == "Low (80-250 Hz)"
    # 400 Hz sits inside Mud and Body; Mud midpoint (350) is closer
    # than Body midpoint (525) → Mud wins.
    assert _resolve_zone_label_for_freq(400.0) == "Mud (200-500 Hz)"


def test_zone_bounds_cover_every_zone_center():
    """Guard against a future edit of ZONE_CENTER_HZ or ZONE_BOUNDS_HZ
    leaving them out of sync — every midpoint must fall within its
    own declared bounds."""
    for zone, center in ZONE_CENTER_HZ.items():
        lo, hi = ZONE_BOUNDS_HZ[zone]
        assert lo <= center <= hi, (
            f"zone {zone}: center {center} outside bounds ({lo}, {hi})"
        )


# ---------------------------------------------------------------------------
# Fix 2 — accumulation diagnostic_id uniqueness
# ---------------------------------------------------------------------------

def _make_section(name: str = "Build 2") -> Section:
    return Section(
        index=1, name=name,
        start_bucket=0, end_bucket=99,
        start_seconds=0.0, end_seconds=99.0,
        start_beats=0.0, end_beats=198.0,
        total_energy_db=-10.0,
    )


def _acc(freq_hz: float, start_bucket: int, tracks: List[str]) -> dict:
    return {
        "freq_hz":                freq_hz,
        "n_tracks_simultaneous":  len(tracks),
        "duration_buckets":       5,
        "start_bucket":           start_bucket,
        "end_bucket":             start_bucket + 4,
        "track_names":            list(tracks),
    }


def test_accumulation_diagnostic_id_includes_bucket_suffix():
    """IDs now end in ``_B<start_bucket>`` — field report observed
    collisions without it."""
    s = _make_section()
    s.tracks_active = ["Kick", "Pad", "Reverb"]
    s.track_roles = {
        "Kick":   (Importance.H, Function.R),
        "Pad":    (Importance.A, Function.T),
        "Reverb": (Importance.A, Function.T),
    }
    s.track_energy = {t: {"mud": -5.0} for t in s.tracks_active}
    s.track_presence = {t: {"mud": 1.0} for t in s.tracks_active}
    s.accumulations = [_acc(247.0, start_bucket=12,
                            tracks=s.tracks_active)]

    d = detect_accumulation_risks(s)[0]
    assert d.diagnostic_id.endswith("_B12")
    assert d.diagnostic_id.startswith("ACC_BUILD2_PAD_")


def test_two_accumulations_same_freq_same_section_get_distinct_ids():
    """Field scenario: two separate pile-ups at 247 Hz in the same
    section (a gap, then a resume). Pre-B2a.1 they collided on ID;
    post-fix the ``_B<start>`` suffix disambiguates deterministically."""
    s = _make_section(name="Build 2")
    s.tracks_active = ["Kick", "Pad", "Reverb"]
    s.track_roles = {
        "Kick":   (Importance.H, Function.R),
        "Pad":    (Importance.A, Function.T),
        "Reverb": (Importance.A, Function.T),
    }
    s.track_energy = {t: {"mud": -5.0} for t in s.tracks_active}
    s.track_presence = {t: {"mud": 1.0} for t in s.tracks_active}
    # Two pile-ups at the same cluster freq, different buckets.
    s.accumulations = [
        _acc(247.0, start_bucket=10, tracks=s.tracks_active),
        _acc(247.0, start_bucket=40, tracks=s.tracks_active),
    ]

    diags = detect_accumulation_risks(s)
    assert len(diags) == 2
    ids = [d.diagnostic_id for d in diags]
    assert len(set(ids)) == 2, (
        f"accumulations collided on ID: {ids!r}"
    )
    assert diags[0].diagnostic_id.endswith("_B10")
    assert diags[1].diagnostic_id.endswith("_B40")


def test_accumulation_diagnosis_text_resolves_zone_off_midpoint():
    """The diagnosis text used to say ``(la bande concernée)`` for
    every accumulation. Post-fix it shows the actual zone label."""
    s = _make_section()
    s.tracks_active = ["Kick", "Pad", "Reverb"]
    s.track_roles = {
        "Kick":   (Importance.H, Function.R),
        "Pad":    (Importance.A, Function.T),
        "Reverb": (Importance.A, Function.T),
    }
    s.track_energy = {t: {"mud": -5.0} for t in s.tracks_active}
    s.track_presence = {t: {"mud": 1.0} for t in s.tracks_active}
    s.accumulations = [_acc(311.0, start_bucket=5,
                            tracks=s.tracks_active)]

    d = detect_accumulation_risks(s)[0]
    assert "Mud (200-500 Hz)" in d.diagnosis_text
    assert "la bande concernée" not in d.diagnosis_text


def test_accumulation_outcome_template_uses_resolved_zone_label():
    """The outcome template ``"libère de l'espace autour de [zone]"``
    must show a real zone, not the fallback label."""
    s = _make_section()
    s.tracks_active = ["Kick", "Pad", "Reverb"]
    s.track_roles = {
        "Kick":   (Importance.H, Function.R),
        "Pad":    (Importance.A, Function.T),
        "Reverb": (Importance.A, Function.T),
    }
    s.track_energy = {t: {"mud": -5.0} for t in s.tracks_active}
    s.track_presence = {t: {"mud": 1.0} for t in s.tracks_active}
    s.accumulations = [_acc(311.0, start_bucket=5,
                            tracks=s.tracks_active)]

    d = detect_accumulation_risks(s)[0]
    all_text = " | ".join(
        d.expected_outcomes + d.potential_risks + d.verification_steps
    )
    assert "Mud (200-500 Hz)" in all_text
    assert "la bande concernée" not in all_text
