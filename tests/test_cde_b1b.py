#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Feature 3.6 B1b — CDE core engine + masking conflict detector.

B1b adds :mod:`cde_engine`:
    * Dataclasses (``CorrectionDiagnostic``, ``ProblemMeasurement``, …)
    * ``generate_diagnostic_id`` — human-readable, deterministic IDs
    * ``compute_tfp_context`` — maps conflict + section to TFPContext
    * ``detect_masking_conflicts`` — consumes ``section.conflicts``

Scope-wise this tests only B1b pieces. The recommendation matrix,
fallback, protection rules and JSON dump ship in B1c — the diagnostics
produced here intentionally carry ``primary_correction = None`` and
``fallback_correction = None``. A test pins that contract so a future
change that forgets to null them is caught.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from section_detector import (  # noqa: E402
    Section,
    build_sections_timeline_sheet,
    enrich_sections_with_track_stats,
)
from tfp_parser import DEFAULT_ROLE, Function, Importance  # noqa: E402

from cde_engine import (  # noqa: E402
    CDE_VERSION,
    ZONE_CENTER_HZ,
    CorrectionDiagnostic,
    ProblemMeasurement,
    TFPContext,
    SectionContext,
    _measurement_from_conflict,
    _role_compatibility,
    compute_tfp_context,
    detect_masking_conflicts,
    generate_diagnostic_id,
)
from openpyxl import Workbook  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_section(
    index: int, start: int, end: int, total_energy_db: float, name: str = None,
) -> Section:
    return Section(
        index=index,
        name=name or f"Section {index}",
        start_bucket=start,
        end_bucket=end,
        start_seconds=float(start),
        end_seconds=float(end),
        start_beats=float(start * 2),
        end_beats=float(end * 2),
        total_energy_db=total_energy_db,
    )


def _zone_arrays_for(level_db: float, n_frames: int, zones_with_energy: List[str]) -> dict:
    from section_detector import get_zone_order
    zones = {
        z: np.full(n_frames, -120.0, dtype=float)
        for z in get_zone_order()
    }
    for z in zones_with_energy:
        zones[z] = np.full(n_frames, float(level_db), dtype=float)
    return zones


def _section_with_one_conflict(
    role_a: Tuple[Importance, Function] = (Importance.H, Function.R),
    role_b: Tuple[Importance, Function] = (Importance.S, Function.H),
    section_name: str = "Drop 1",
    zone: str = "sub",
    severity: str = "critical",
) -> Section:
    """Build a Section already populated with one conflict — the easiest
    way to exercise the CDE without running build_sections_timeline_sheet
    end-to-end in every test."""
    n = 30
    s = _make_section(1, 0, n - 1, total_energy_db=-10.0, name=section_name)
    s.tracks_active = ["Kick 1", "Sub Bass"]
    s.track_roles = {"Kick 1": role_a, "Sub Bass": role_b}
    s.track_presence = {
        "Kick 1":   {zone: 1.0},
        "Sub Bass": {zone: 1.0},
    }
    s.track_energy = {
        "Kick 1":   {zone: -5.0},
        "Sub Bass": {zone: -6.0},
    }
    s.conflicts = [{
        "track_a": "Kick 1",
        "track_b": "Sub Bass",
        "zone": zone,
        "energy_a": -5.0,
        "energy_b": -6.0,
        "score": 0.87,
        "severity": severity,
    }]
    return s


# ---------------------------------------------------------------------------
# generate_diagnostic_id — format, section/track_b/freq optional
# ---------------------------------------------------------------------------

def test_generate_diagnostic_id_full_masking_conflict():
    """Spec example: CONF_DROP1_KICK1_SUBBASS_62HZ."""
    got = generate_diagnostic_id(
        "masking_conflict", "Drop 1", "Kick 1", "Sub Bass", 62,
    )
    assert got == "CONF_DROP1_KICK1_SUBBASS_62HZ"


def test_generate_diagnostic_id_omits_section_when_none():
    """No section → component is absent, no double underscore."""
    got = generate_diagnostic_id(
        "masking_conflict", None, "Kick 1", "Sub Bass", 62,
    )
    assert got == "CONF_KICK1_SUBBASS_62HZ"
    assert "__" not in got


def test_generate_diagnostic_id_single_track_issue():
    """Accumulation / resonance / phase issues: no track_b."""
    got = generate_diagnostic_id(
        "accumulation_risk", "Chorus 1", "Pad", None, 247,
    )
    assert got == "ACC_CHORUS1_PAD_247HZ"


def test_generate_diagnostic_id_no_frequency():
    """Phase issues may not have a frequency — ID must still be valid."""
    got = generate_diagnostic_id(
        "phase_issue", "Intro", "Lead", None, None,
    )
    assert got == "PHASE_INTRO_LEAD"
    # 0 or negative frequency is also dropped
    got_zero = generate_diagnostic_id(
        "phase_issue", "Intro", "Lead", None, 0,
    )
    assert got_zero == "PHASE_INTRO_LEAD"


def test_generate_diagnostic_id_slug_sanitizes_special_chars():
    """Spaces, dashes, slashes, underscores must be stripped from each
    token so the ID stays pronounceable."""
    got = generate_diagnostic_id(
        "masking_conflict",
        "Break-Down 2",
        "Sub/Bass",
        "Kick 1",
        100,
    )
    assert got == "CONF_BREAKDOWN2_SUBBASS_KICK1_100HZ"


# ---------------------------------------------------------------------------
# TFPContext — role compatibility mapping
# ---------------------------------------------------------------------------

def test_role_compatibility_hero_vs_hero_is_conflict():
    compat = _role_compatibility(
        (Importance.H, Function.R), (Importance.H, Function.H),
    )
    assert compat == "conflict"


def test_role_compatibility_hero_vs_support_is_dominant_support():
    compat = _role_compatibility(
        (Importance.H, Function.R), (Importance.S, Function.H),
    )
    assert compat == "dominant_support"
    # Symmetric: order of arguments must not flip the label.
    compat_rev = _role_compatibility(
        (Importance.S, Function.H), (Importance.H, Function.R),
    )
    assert compat_rev == "dominant_support"


def test_role_compatibility_non_hero_pair_is_compatible():
    assert _role_compatibility(
        (Importance.S, Function.H), (Importance.S, Function.M),
    ) == "compatible"
    assert _role_compatibility(
        (Importance.A, Function.T), (Importance.A, Function.T),
    ) == "compatible"
    assert _role_compatibility(
        (Importance.S, Function.R), (Importance.A, Function.T),
    ) == "compatible"


def test_role_compatibility_single_track_diagnostic():
    """Resonance / dynamic / phase diagnostics have a single track —
    role_b is None and the label defaults to 'compatible'."""
    compat = _role_compatibility((Importance.H, Function.M), None)
    assert compat == "compatible"


def test_compute_tfp_context_falls_back_to_default_role_for_unmapped_track():
    """Tracks missing from section.track_roles fall back to DEFAULT_ROLE
    (S/R), matching tfp_coherence behaviour (R2 of the F3.5 spec)."""
    s = _section_with_one_conflict()
    # Remove the role for Sub Bass so the fallback kicks in.
    s.track_roles = {"Kick 1": (Importance.H, Function.R)}
    conflict = s.conflicts[0]

    ctx = compute_tfp_context(conflict, s)
    assert ctx.track_a_role == (Importance.H, Function.R)
    assert ctx.track_b_role == DEFAULT_ROLE


# ---------------------------------------------------------------------------
# ProblemMeasurement builder
# ---------------------------------------------------------------------------

def test_measurement_from_conflict_populates_all_fields():
    """Measurement fields are computed deterministically from the conflict
    dict + section.track_presence."""
    s = _section_with_one_conflict(zone="sub")
    s.track_presence["Kick 1"]["sub"] = 0.9
    s.track_presence["Sub Bass"]["sub"] = 0.6
    conflict = s.conflicts[0]

    m = _measurement_from_conflict(conflict, s)
    assert isinstance(m, ProblemMeasurement)
    assert m.frequency_hz == float(ZONE_CENTER_HZ["sub"])  # 50 Hz
    assert m.peak_db == pytest.approx(-5.0)  # max(energy_a, energy_b)
    assert m.duration_in_section_s == pytest.approx(29.0)  # end - start
    # Minimum of the two presence ratios — the pessimistic proxy.
    assert m.duration_ratio_in_section == pytest.approx(0.6)
    assert m.is_audible_fraction == pytest.approx(0.6)
    assert m.severity_score == pytest.approx(0.87)
    assert m.masking_score == pytest.approx(0.87)


# ---------------------------------------------------------------------------
# detect_masking_conflicts — main public entry point
# ---------------------------------------------------------------------------

def test_detect_masking_conflicts_returns_empty_when_no_conflicts():
    """Section with empty conflicts list → no diagnostics, no crash."""
    s = _make_section(1, 0, 29, total_energy_db=-15.0)
    assert detect_masking_conflicts(s) == []


def test_detect_masking_conflicts_produces_one_diagnostic_per_conflict():
    """One conflict in section.conflicts → one CorrectionDiagnostic with
    the expected fields wired up."""
    s = _section_with_one_conflict(
        role_a=(Importance.H, Function.R),
        role_b=(Importance.S, Function.H),
        section_name="Drop 1",
        zone="sub",
        severity="critical",
    )
    diags = detect_masking_conflicts(s)
    assert len(diags) == 1

    d = diags[0]
    assert isinstance(d, CorrectionDiagnostic)
    assert d.issue_type == "masking_conflict"
    assert d.severity == "critical"
    assert d.track_a == "Kick 1"
    assert d.track_b == "Sub Bass"
    assert d.section == "Drop 1"
    assert d.cde_version == CDE_VERSION

    # Id matches the spec example format (zone midpoint = 50 Hz for sub).
    assert d.diagnostic_id == "CONF_DROP1_KICK1_SUBBASS_50HZ"

    # TFP context is wired up correctly.
    assert d.tfp_context.track_a_role == (Importance.H, Function.R)
    assert d.tfp_context.track_b_role == (Importance.S, Function.H)
    assert d.tfp_context.role_compatibility == "dominant_support"

    # Section context summary.
    assert isinstance(d.section_context, SectionContext)
    assert d.section_context.section_name == "Drop 1"
    assert d.section_context.conflicts_in_section == 1
    assert d.section_context.tracks_active_count == 2

    # Diagnosis text is human-readable French.
    assert "Kick 1" in d.diagnosis_text
    assert "Sub Bass" in d.diagnosis_text
    assert "masking" in d.diagnosis_text.lower()

    # Audit trail — no rules yet, but data sources pinned.
    assert any("CONFLITS" in src for src in d.data_sources)
    assert any("track_roles" in src for src in d.data_sources)

    # Default application status + empty reason.
    assert d.application_status == "proposed"
    assert d.rejection_reason is None


def test_detect_masking_conflicts_leaves_primary_and_fallback_none_in_b1b():
    """B1b contract: recommendations are intentionally None — they're
    computed in B1c by the recommendation matrix. This test pins that
    contract so a premature implementation is caught."""
    s = _section_with_one_conflict()
    diags = detect_masking_conflicts(s)
    assert len(diags) == 1
    assert diags[0].primary_correction is None
    assert diags[0].fallback_correction is None
    assert diags[0].rules_applied == []
    assert diags[0].expected_outcomes == []
    assert diags[0].potential_risks == []
    assert diags[0].verification_steps == []


def test_detect_masking_conflicts_skips_midi_tracks_without_wav():
    """Risque 7 of the F3.6 recon — tracks present in section.conflicts
    but absent from all_tracks_zone_energy (MIDI without WAV) must be
    skipped silently."""
    s = _section_with_one_conflict()
    # Kick 1 is in the WAV map; Sub Bass is not — skip this conflict.
    all_tracks_zone_energy = {"Kick 1": {"sub": np.full(30, -5.0)}}
    diags = detect_masking_conflicts(s, all_tracks_zone_energy)
    assert diags == []


def test_detect_masking_conflicts_integrated_with_build_sheet():
    """End-to-end: run build_sections_timeline_sheet, then feed the
    resulting Section directly into detect_masking_conflicts. The
    persisted section.conflicts must be the only input the CDE needs
    (no re-running of detect_conflicts_in_section)."""
    n = 30
    s = _make_section(1, 0, n - 1, total_energy_db=-10.0, name="Drop 1")
    all_tracks = {
        "TrackA": _zone_arrays_for(-5.0, n, ["low"]),
        "TrackB": _zone_arrays_for(-6.0, n, ["low"]),
    }

    wb = Workbook()
    build_sections_timeline_sheet(
        workbook=wb, sections=[s], all_tracks_zone_energy=all_tracks,
    )
    assert s.conflicts, "build_sheet must persist at least one conflict"

    diags = detect_masking_conflicts(s, all_tracks)
    assert len(diags) == len(s.conflicts)
    for d, conf in zip(diags, s.conflicts):
        assert d.track_a == conf["track_a"]
        assert d.track_b == conf["track_b"]
        assert d.severity == conf["severity"]
