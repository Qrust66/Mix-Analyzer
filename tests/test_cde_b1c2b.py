#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Feature 3.6 B1c2b — outcome templates + JSON serialization.

B1c2b fills the qualitative-impact fields on each
:class:`CorrectionDiagnostic` (``expected_outcomes``,
``potential_risks``, ``verification_steps``) from per-approach
templates, and ships ``dump_diagnostics_to_json`` — the write-only
half of the §9 storage contract. The read/filter API lands in B3.

Scope covered here:

    * Template selection per approach (sidechain / reciprocal_cuts /
      static_dip / musical_dip); empty-list fallback for ``None`` or
      unknown approach.
    * Placeholder substitution: ``[track_a]`` / ``[track_b]`` /
      ``[track_cut]`` / ``[track_protected]`` / ``[section]`` /
      ``[zone]``, including the sidechain-specific trigger/target
      semantics.
    * JSON dump structure, enum / datetime / None handling, and a
      round-trip sanity check via ``json.loads``.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from section_detector import Section  # noqa: E402
from tfp_parser import Function, Importance  # noqa: E402

from cde_engine import (  # noqa: E402
    CDE_VERSION,
    ZONE_CENTER_HZ,
    CorrectionDiagnostic,
    CorrectionRecipe,
    ProblemMeasurement,
    SectionContext,
    TFPContext,
    _substitute_placeholders,
    detect_masking_conflicts,
    dump_diagnostics_to_json,
    populate_outcome_templates,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_section(
    index: int, start: int, end: int, total_energy_db: float,
    name: str = "Drop 1",
) -> Section:
    return Section(
        index=index,
        name=name,
        start_bucket=start,
        end_bucket=end,
        start_seconds=float(start),
        end_seconds=float(end),
        start_beats=float(start * 2),
        end_beats=float(end * 2),
        total_energy_db=total_energy_db,
    )


def _section_with_pair(
    role_a: Tuple[Importance, Function],
    role_b: Tuple[Importance, Function],
    track_a: str = "Track A",
    track_b: str = "Track B",
    zone: str = "low",
) -> Section:
    s = _make_section(1, 0, 29, total_energy_db=-10.0)
    s.tracks_active = [track_a, track_b]
    s.track_roles = {track_a: role_a, track_b: role_b}
    s.track_presence = {track_a: {zone: 1.0}, track_b: {zone: 1.0}}
    s.track_energy = {track_a: {zone: -5.0}, track_b: {zone: -6.0}}
    s.conflicts = [{
        "track_a": track_a, "track_b": track_b, "zone": zone,
        "energy_a": -5.0, "energy_b": -6.0,
        "score": 0.87, "severity": "critical",
    }]
    return s


def _only_diag(section: Section, **kwargs) -> CorrectionDiagnostic:
    diags = detect_masking_conflicts(section, **kwargs)
    assert len(diags) == 1
    return diags[0]


def _bare_diag(
    track_a: str = "Kick 1", track_b: str = "Sub Bass",
    role_a=(Importance.H, Function.R), role_b=(Importance.S, Function.H),
    section_name: str = "Drop 1", zone: str = "low",
) -> CorrectionDiagnostic:
    """Build a minimal CorrectionDiagnostic without running the detector."""
    return CorrectionDiagnostic(
        diagnostic_id="TEST",
        timestamp=datetime(2026, 4, 21, 17, 30, 0),
        cde_version=CDE_VERSION,
        track_a=track_a,
        track_b=track_b,
        section=section_name,
        issue_type="masking_conflict",
        severity="critical",
        measurement=ProblemMeasurement(
            frequency_hz=float(ZONE_CENTER_HZ[zone]),
            peak_db=-5.0, duration_in_section_s=29.0,
            duration_ratio_in_section=1.0, is_audible_fraction=1.0,
            severity_score=0.87, masking_score=0.87,
        ),
        tfp_context=TFPContext(
            track_a_role=role_a, track_b_role=role_b,
            role_compatibility="dominant_support",
        ),
        section_context=SectionContext(
            section_name=section_name, section_duration_s=29.0,
            tracks_active_count=2, conflicts_in_section=1,
            coherence_score=None,
        ),
        diagnosis_text="test diag",
    )


def _recipe(
    approach: str, target: str = "Sub Bass",
    zone: str = "low", **params,
) -> CorrectionRecipe:
    base_params = {"frequency_hz": float(ZONE_CENTER_HZ[zone])}
    base_params.update(params)
    return CorrectionRecipe(
        target_track=target,
        device="test device",
        approach=approach,
        parameters=base_params,
        applies_to_sections=["Drop 1"],
        rationale="test",
        confidence="medium",
    )


# ---------------------------------------------------------------------------
# Templates — per approach
# ---------------------------------------------------------------------------

def test_template_sidechain_populates_with_trigger_as_track_a():
    """For sidechain, ``[track_a]`` in the template resolves to the
    trigger (the one that gains punch), NOT to diagnostic.track_a."""
    d = _bare_diag(track_a="Kick 1", track_b="Sub Bass")
    d.primary_correction = _recipe(
        "sidechain", target="Sub Bass", trigger_track="Kick 1", depth_db=-8.0,
    )

    populate_outcome_templates(d)
    assert any("Kick 1" in line for line in d.expected_outcomes)
    assert any("plus de punch" in line for line in d.expected_outcomes)
    assert any("Sub Bass" in line for line in d.potential_risks)
    assert any("respire entre les frappes" in line
               for line in d.verification_steps)


def test_template_reciprocal_cuts_populates_generic_lines():
    """reciprocal_cuts templates have no placeholders — just generic
    symmetric text about "les deux tracks"."""
    d = _bare_diag(role_a=(Importance.H, Function.M),
                   role_b=(Importance.H, Function.H))
    d.primary_correction = _recipe(
        "reciprocal_cuts", target=d.track_a, gain_db=-2.0,
    )

    populate_outcome_templates(d)
    assert any("espace spectral" in line for line in d.expected_outcomes)
    assert any("presence" in line.lower() or "présence" in line
               for line in d.potential_risks)
    assert any("A/B" in line for line in d.verification_steps)
    # No placeholder substitution needed — no square brackets left.
    for line in (d.expected_outcomes + d.potential_risks
                 + d.verification_steps):
        assert "[" not in line and "]" not in line


def test_template_static_dip_substitutes_track_cut_and_zone():
    """static_dip templates substitute ``[track_cut]``,
    ``[track_protected]``, ``[section]`` and ``[zone]``."""
    d = _bare_diag(track_a="Kick 1", track_b="Sub Bass", zone="low")
    d.primary_correction = _recipe(
        "static_dip", target="Sub Bass", zone="low", gain_db=-3.0, q=3.0,
    )

    populate_outcome_templates(d)
    # Target ("Sub Bass") mentioned in outcomes + risks; protected
    # ("Kick 1") mentioned in verification; zone label injected.
    assert any("Sub Bass" in line and "espace" in line
               for line in d.expected_outcomes)
    assert any("Sub Bass" in line and "body" in line
               for line in d.potential_risks)
    assert any("Kick 1" in line for line in d.verification_steps)
    # Zone label comes from get_zone_label — "Low (80-250 Hz)".
    combined = " ".join(d.expected_outcomes + d.potential_risks)
    assert "Low (80-250 Hz)" in combined


def test_template_musical_dip_mentions_character_preserved():
    """musical_dip is the softer variant — templates emphasise
    preserving the track's character."""
    d = _bare_diag(track_b="Pad")
    d.primary_correction = _recipe("musical_dip", target="Pad", zone="mid")

    populate_outcome_templates(d)
    assert any("character de Pad" in line for line in d.expected_outcomes)
    assert any("subtil" in line for line in d.potential_risks)
    assert any("A/B" in line for line in d.verification_steps)


# ---------------------------------------------------------------------------
# Templates — empty paths
# ---------------------------------------------------------------------------

def test_no_templates_when_primary_correction_is_none():
    """R2-skipped diagnostics (primary=None) must NOT invent outcomes —
    there is no action to describe."""
    d = _bare_diag(role_a=(Importance.H, Function.R),
                   role_b=(Importance.H, Function.R), zone="sub")
    d.primary_correction = None

    populate_outcome_templates(d)
    assert d.expected_outcomes == []
    assert d.potential_risks == []
    assert d.verification_steps == []


def test_no_templates_for_unknown_approach():
    """An approach not in _OUTCOME_TEMPLATES yields empty lists — we
    prefer silence to guessing."""
    d = _bare_diag()
    d.primary_correction = _recipe("unknown_exotic_approach", target="Sub Bass")

    populate_outcome_templates(d)
    assert d.expected_outcomes == []
    assert d.potential_risks == []
    assert d.verification_steps == []


# ---------------------------------------------------------------------------
# Placeholder substitution edge cases
# ---------------------------------------------------------------------------

def test_substitute_placeholders_resolves_section_fallback_when_none():
    """``diagnostic.section == None`` → ``[section]`` renders as
    ``"la section"`` — a legible French fallback."""
    d = _bare_diag()
    d.section = None
    d.section_context.section_name = ""
    recipe = _recipe("static_dip", target="Sub Bass", zone="low")

    text = _substitute_placeholders(
        "corriger [track_cut] dans [section]", d, recipe,
    )
    assert text == "corriger Sub Bass dans la section"


def test_substitute_placeholders_protected_is_the_other_track():
    """When the recipe targets track_b, [track_protected] must resolve
    to track_a — the one receiving the benefit of the cut."""
    d = _bare_diag(track_a="Kick 1", track_b="Sub Bass")
    recipe = _recipe("static_dip", target="Sub Bass")
    text = _substitute_placeholders(
        "[track_cut] libère [track_protected]", d, recipe,
    )
    assert text == "Sub Bass libère Kick 1"

    # And the reverse — target = track_a.
    recipe_rev = _recipe("static_dip", target="Kick 1")
    text_rev = _substitute_placeholders(
        "[track_cut] libère [track_protected]", d, recipe_rev,
    )
    assert text_rev == "Kick 1 libère Sub Bass"


# ---------------------------------------------------------------------------
# End-to-end through the detector — B1c2b wiring
# ---------------------------------------------------------------------------

def test_detect_masking_conflicts_fills_impact_fields_via_pipeline():
    """The detector now calls populate_outcome_templates after
    apply_protection_rules — running it end-to-end on an H/S Sub
    conflict yields sidechain templates with the correct substitutions.
    """
    s = _section_with_pair(
        role_a=(Importance.H, Function.R), role_b=(Importance.S, Function.H),
        track_a="Kick 1", track_b="Sub Bass", zone="low",
    )
    d = _only_diag(s)
    assert d.primary_correction is not None
    assert d.primary_correction.approach == "sidechain"
    assert d.expected_outcomes
    assert d.potential_risks
    assert d.verification_steps


# ---------------------------------------------------------------------------
# JSON dump — structure + serialisation
# ---------------------------------------------------------------------------

def _dump_and_load(diagnostics, tmp_path: Path) -> dict:
    target = tmp_path / "diagnostics.json"
    dump_diagnostics_to_json(diagnostics, target)
    assert target.exists()
    return json.loads(target.read_text(encoding="utf-8"))


def test_json_dump_top_level_structure(tmp_path: Path):
    """Top-level envelope matches spec §9.1."""
    s = _section_with_pair(
        role_a=(Importance.H, Function.R), role_b=(Importance.S, Function.H),
        zone="low",
    )
    diags = detect_masking_conflicts(s)

    payload = _dump_and_load(diags, tmp_path)
    assert payload["cde_version"] == CDE_VERSION
    assert "generated_at" in payload
    # generated_at must be ISO format parseable.
    datetime.fromisoformat(payload["generated_at"])
    assert payload["diagnostic_count"] == len(diags)
    assert isinstance(payload["diagnostics"], list)
    assert len(payload["diagnostics"]) == len(diags)


def test_json_dump_serialises_enums_as_short_codes(tmp_path: Path):
    """Importance / Function enums must land in JSON as their single-
    character codes — the canonical cross-module representation."""
    s = _section_with_pair(
        role_a=(Importance.H, Function.M), role_b=(Importance.S, Function.H),
        zone="low",
    )
    diags = detect_masking_conflicts(s)

    payload = _dump_and_load(diags, tmp_path)
    first = payload["diagnostics"][0]
    assert first["tfp_context"]["track_a_role"] == ["H", "M"]
    assert first["tfp_context"]["track_b_role"] == ["S", "H"]


def test_json_dump_serialises_timestamp_as_iso_string(tmp_path: Path):
    """Per-diagnostic timestamp is written as an ISO 8601 string."""
    d = _bare_diag()
    payload = _dump_and_load([d], tmp_path)
    ts = payload["diagnostics"][0]["timestamp"]
    assert ts == "2026-04-21T17:30:00"
    # Must round-trip through fromisoformat.
    assert datetime.fromisoformat(ts) == datetime(2026, 4, 21, 17, 30, 0)


def test_json_dump_handles_none_primary_and_fallback(tmp_path: Path):
    """A R2-skipped diagnostic has both recommendations ``None`` — the
    dumper must serialise them as JSON ``null``, not crash."""
    s = _section_with_pair(
        role_a=(Importance.H, Function.R), role_b=(Importance.H, Function.R),
        zone="sub",
    )
    diags = detect_masking_conflicts(s)
    assert diags[0].primary_correction is None
    assert diags[0].fallback_correction is None

    payload = _dump_and_load(diags, tmp_path)
    first = payload["diagnostics"][0]
    assert first["primary_correction"] is None
    assert first["fallback_correction"] is None


def test_json_dump_round_trip_preserves_all_fields(tmp_path: Path):
    """Dump → ``json.loads`` → the important fields are recoverable.

    This does NOT exercise the load API (B3) — it just confirms the
    payload is self-describing and that no field silently evaporates.
    """
    s = _section_with_pair(
        role_a=(Importance.H, Function.R), role_b=(Importance.S, Function.H),
        track_a="Kick 1", track_b="Sub Bass", zone="low",
    )
    diags = detect_masking_conflicts(s)
    d = diags[0]

    payload = _dump_and_load(diags, tmp_path)
    restored = payload["diagnostics"][0]

    assert restored["diagnostic_id"] == d.diagnostic_id
    assert restored["issue_type"] == d.issue_type
    assert restored["severity"] == d.severity
    assert restored["section"] == d.section
    assert restored["track_a"] == d.track_a
    assert restored["track_b"] == d.track_b
    assert restored["measurement"]["frequency_hz"] == d.measurement.frequency_hz
    assert restored["tfp_context"]["role_compatibility"] == (
        d.tfp_context.role_compatibility
    )
    assert restored["primary_correction"]["approach"] == (
        d.primary_correction.approach
    )
    assert restored["expected_outcomes"] == d.expected_outcomes
    assert restored["potential_risks"] == d.potential_risks
    assert restored["verification_steps"] == d.verification_steps
    assert restored["rules_applied"] == d.rules_applied


def test_json_dump_preserves_diagnostic_order(tmp_path: Path):
    """The output list must match the input order — downstream
    consumers rely on severity-sorted order from
    ``detect_conflicts_in_section``."""
    # Build three distinct diagnostics by hand, each with a unique ID.
    d1 = _bare_diag(track_a="A", track_b="B")
    d1.diagnostic_id = "FIRST"
    d2 = _bare_diag(track_a="C", track_b="D")
    d2.diagnostic_id = "SECOND"
    d3 = _bare_diag(track_a="E", track_b="F")
    d3.diagnostic_id = "THIRD"

    payload = _dump_and_load([d1, d2, d3], tmp_path)
    ids = [entry["diagnostic_id"] for entry in payload["diagnostics"]]
    assert ids == ["FIRST", "SECOND", "THIRD"]


def test_json_dump_creates_parent_directories(tmp_path: Path):
    """The dumper auto-creates missing parent dirs for convenience."""
    nested = tmp_path / "nested" / "subdir" / "diagnostics.json"
    d = _bare_diag()
    dump_diagnostics_to_json([d], nested)
    assert nested.exists()
    parsed = json.loads(nested.read_text(encoding="utf-8"))
    assert parsed["diagnostic_count"] == 1


def test_json_dump_accepts_string_path(tmp_path: Path):
    """Both ``str`` and :class:`pathlib.Path` inputs are accepted —
    callers in the pipeline may pass either form."""
    target = tmp_path / "diagnostics.json"
    d = _bare_diag()
    dump_diagnostics_to_json([d], str(target))  # str path
    assert target.exists()
