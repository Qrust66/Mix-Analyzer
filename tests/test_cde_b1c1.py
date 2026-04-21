#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Feature 3.6 B1c1 — recommendation matrix + fallback.

B1c1 ships the §6.1 decision matrix and the §6.2 fallback table. Each
matrix branch has a dedicated test including the H/R × H/H sidechain
exception. Fallback coverage exercises each approach the primary
matrix can produce. The qualitative impact fields and the protection
rules ship in B1c2 and are intentionally out of scope here.
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
    FALLBACK_APPROACH_MAP,
    RULE_AA_NO_ACTION,
    RULE_HA_ZONE_CUT,
    RULE_HH_RECIPROCAL,
    RULE_HR_HH_SIDECHAIN,
    RULE_HS_SIDECHAIN,
    RULE_SA_ZONE_CUT,
    RULE_SS_ZONE_CUT,
    CorrectionRecipe,
    compute_fallback_recommendation,
    compute_primary_recommendation,
    detect_masking_conflicts,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_section(
    index: int, start: int, end: int, total_energy_db: float, name: str = "Drop 1",
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
    track_a: str = "Kick 1",
    track_b: str = "Sub Bass",
    zone: str = "sub",
    severity: str = "critical",
    score: float = 0.87,
) -> Section:
    s = _make_section(1, 0, 29, total_energy_db=-10.0)
    s.tracks_active = [track_a, track_b]
    s.track_roles = {track_a: role_a, track_b: role_b}
    s.track_presence = {
        track_a: {zone: 1.0},
        track_b: {zone: 1.0},
    }
    s.track_energy = {
        track_a: {zone: -5.0},
        track_b: {zone: -6.0},
    }
    s.conflicts = [{
        "track_a": track_a,
        "track_b": track_b,
        "zone": zone,
        "energy_a": -5.0,
        "energy_b": -6.0,
        "score": score,
        "severity": severity,
    }]
    return s


def _only_diag(section: Section):
    diags = detect_masking_conflicts(section)
    assert len(diags) == 1
    return diags[0]


# ---------------------------------------------------------------------------
# Primary matrix — §6.1, one test per role pair (+ exception)
# ---------------------------------------------------------------------------

def test_primary_H_vs_H_default_is_reciprocal_cuts():
    """H×H (both Hero, not H/R+H/H) → reciprocal_cuts with a secondary
    cut on the other track in the same zone."""
    s = _section_with_pair(
        role_a=(Importance.H, Function.M), role_b=(Importance.H, Function.M),
        track_a="Lead A", track_b="Lead B",
    )
    d = _only_diag(s)
    assert d.primary_correction is not None
    assert d.primary_correction.approach == "reciprocal_cuts"
    # Both tracks are cut; secondary is encoded in parameters.
    assert d.primary_correction.target_track == "Lead A"
    assert d.primary_correction.parameters["secondary_cut"]["track"] == "Lead B"
    assert d.rules_applied == [RULE_HH_RECIPROCAL]


def test_primary_H_R_vs_H_H_exception_is_sidechain_on_bass():
    """Exception to H×H: kick (H/R) vs bass (H/H) → sidechain the bass
    from the kick (classical kick+bass configuration)."""
    s = _section_with_pair(
        role_a=(Importance.H, Function.R), role_b=(Importance.H, Function.H),
        track_a="Kick 1", track_b="Acid Bass",
    )
    d = _only_diag(s)
    assert d.primary_correction.approach == "sidechain"
    assert d.primary_correction.target_track == "Acid Bass"
    assert d.primary_correction.parameters["trigger_track"] == "Kick 1"
    assert d.rules_applied == [RULE_HR_HH_SIDECHAIN]

    # Symmetric: same pair with tracks swapped role-wise.
    s_rev = _section_with_pair(
        role_a=(Importance.H, Function.H), role_b=(Importance.H, Function.R),
        track_a="Acid Bass", track_b="Kick 1",
    )
    d_rev = _only_diag(s_rev)
    assert d_rev.primary_correction.approach == "sidechain"
    assert d_rev.primary_correction.target_track == "Acid Bass"
    assert d_rev.primary_correction.parameters["trigger_track"] == "Kick 1"


def test_primary_H_vs_S_is_sidechain_support_ducked_from_hero():
    """H × S → sidechain; the Support is ducked when the Hero plays."""
    s = _section_with_pair(
        role_a=(Importance.H, Function.R), role_b=(Importance.S, Function.H),
        track_a="Kick 1", track_b="Sub Bass",
    )
    d = _only_diag(s)
    assert d.primary_correction.approach == "sidechain"
    assert d.primary_correction.target_track == "Sub Bass"
    assert d.primary_correction.parameters["trigger_track"] == "Kick 1"
    assert d.primary_correction.parameters["depth_db"] == -8.0
    assert d.rules_applied == [RULE_HS_SIDECHAIN]


def test_primary_H_vs_A_is_zone_cut_on_atmos():
    """H × A → zone cut on the Atmos track (protect the Hero)."""
    s = _section_with_pair(
        role_a=(Importance.H, Function.M), role_b=(Importance.A, Function.T),
        track_a="Lead", track_b="Pad",
    )
    d = _only_diag(s)
    assert d.primary_correction.approach == "static_dip"
    assert d.primary_correction.target_track == "Pad"
    assert d.rules_applied == [RULE_HA_ZONE_CUT]

    # Reversed role order must still target the Atmos.
    s_rev = _section_with_pair(
        role_a=(Importance.A, Function.T), role_b=(Importance.H, Function.M),
        track_a="Pad", track_b="Lead",
    )
    d_rev = _only_diag(s_rev)
    assert d_rev.primary_correction.target_track == "Pad"


def test_primary_S_vs_S_cuts_the_alphabetically_later_track():
    """S × S → cut on the alphabetically later track (the "secondary"
    by convention when both importances are equal)."""
    # "Alpha" < "Bravo" → target is Bravo.
    s = _section_with_pair(
        role_a=(Importance.S, Function.H), role_b=(Importance.S, Function.M),
        track_a="Alpha", track_b="Bravo",
    )
    d = _only_diag(s)
    assert d.primary_correction.approach == "static_dip"
    assert d.primary_correction.target_track == "Bravo"
    assert d.rules_applied == [RULE_SS_ZONE_CUT]

    # Reverse alphabetical order in the conflict dict (Z then A) must
    # still pick the alphabetically later track (Z).
    s_rev = _section_with_pair(
        role_a=(Importance.S, Function.H), role_b=(Importance.S, Function.M),
        track_a="Zulu", track_b="Alpha",
    )
    d_rev = _only_diag(s_rev)
    assert d_rev.primary_correction.target_track == "Zulu"


def test_primary_S_vs_A_is_zone_cut_on_atmos():
    """S × A → zone cut on the Atmos (even though both are non-Hero,
    Support is more critical to the mix than Atmos)."""
    s = _section_with_pair(
        role_a=(Importance.S, Function.H), role_b=(Importance.A, Function.T),
        track_a="Bass Support", track_b="Pad",
    )
    d = _only_diag(s)
    assert d.primary_correction.target_track == "Pad"
    assert d.rules_applied == [RULE_SA_ZONE_CUT]


def test_primary_A_vs_A_is_no_action():
    """A × A → no correction (atmos pair rarely a real issue). The
    rules_applied list still records the 'no action' rule for audit."""
    s = _section_with_pair(
        role_a=(Importance.A, Function.T), role_b=(Importance.A, Function.T),
        track_a="Reverb", track_b="Pad",
    )
    d = _only_diag(s)
    assert d.primary_correction is None
    assert d.fallback_correction is None
    assert d.rules_applied == [RULE_AA_NO_ACTION]


# ---------------------------------------------------------------------------
# Fallback table — §6.2, one test per mapping
# ---------------------------------------------------------------------------

def test_fallback_for_none_primary_is_none():
    """No primary → no fallback. Applies to A×A and single-track
    diagnostics (resonance/phase/dynamics, later features)."""
    s = _section_with_pair(
        role_a=(Importance.A, Function.T), role_b=(Importance.A, Function.T),
    )
    d = _only_diag(s)
    assert d.primary_correction is None
    assert d.fallback_correction is None


def test_fallback_for_reciprocal_cuts_collapses_to_single_static_dip():
    """reciprocal_cuts fallback = a single shallower static_dip
    (-1.5 dB, Q = 3) on the primary target, dropping the secondary."""
    s = _section_with_pair(
        role_a=(Importance.H, Function.M), role_b=(Importance.H, Function.M),
        track_a="Lead A", track_b="Lead B",
    )
    d = _only_diag(s)
    assert d.primary_correction.approach == "reciprocal_cuts"
    fb = d.fallback_correction
    assert isinstance(fb, CorrectionRecipe)
    assert fb.approach == "static_dip"
    assert fb.target_track == "Lead A"
    assert fb.parameters["gain_db"] == -1.5
    assert fb.parameters["q"] == 3.0
    assert "secondary_cut" not in fb.parameters


def test_fallback_for_sidechain_halves_depth():
    """Sidechain primary depth = -8 dB → fallback depth = -4 dB, same
    device, same approach, trigger preserved."""
    s = _section_with_pair(
        role_a=(Importance.H, Function.R), role_b=(Importance.S, Function.H),
    )
    d = _only_diag(s)
    assert d.primary_correction.approach == "sidechain"
    assert d.primary_correction.parameters["depth_db"] == -8.0
    fb = d.fallback_correction
    assert fb.approach == "sidechain"
    assert fb.parameters["depth_db"] == -4.0
    assert fb.parameters["trigger_track"] == d.primary_correction.parameters["trigger_track"]


def test_fallback_for_static_dip_widens_and_shallows():
    """static_dip primary → musical_dip fallback: Q = 2, gain made
    shallower (capped at -1.5 dB)."""
    s = _section_with_pair(
        role_a=(Importance.H, Function.M), role_b=(Importance.A, Function.T),
        track_a="Lead", track_b="Pad",
    )
    d = _only_diag(s)
    assert d.primary_correction.approach == "static_dip"
    assert d.primary_correction.parameters["gain_db"] == -3.0
    fb = d.fallback_correction
    assert fb.approach == "musical_dip"
    assert fb.parameters["q"] == 2.0
    # -3 + 1.5 = -1.5, which is the cap — must not go positive or
    # shallower than -1.5 dB.
    assert fb.parameters["gain_db"] == pytest.approx(-1.5)


def test_fallback_approach_map_preserves_spec_mapping():
    """The FALLBACK_APPROACH_MAP table must contain every mapping the
    spec §6.2 lists so B4 (phase/ms_side_cut) and any future approach
    can read it."""
    assert FALLBACK_APPROACH_MAP["reciprocal_cuts"] == "static_dip"
    assert FALLBACK_APPROACH_MAP["sidechain"] == "sidechain"
    assert FALLBACK_APPROACH_MAP["static_dip"] == "musical_dip"
    assert FALLBACK_APPROACH_MAP["ms_side_cut"] == "stereo_cut"


def test_fallback_unknown_approach_returns_none():
    """Defensive: an approach outside the fallback table returns None,
    so the CDE never guesses a recipe it cannot justify."""
    fake_primary = CorrectionRecipe(
        target_track="X",
        device="Ghost",
        approach="phantom_approach_not_in_map",
        parameters={},
        applies_to_sections=[],
        rationale="",
        confidence="low",
    )
    # Pass any diagnostic — the function only reads ``primary`` when the
    # approach is recognised.
    s = _section_with_pair(
        role_a=(Importance.S, Function.H), role_b=(Importance.S, Function.H),
    )
    d = _only_diag(s)
    assert compute_fallback_recommendation(d, fake_primary) is None


# ---------------------------------------------------------------------------
# Cross-cutting invariants
# ---------------------------------------------------------------------------

def test_primary_and_fallback_carry_same_applies_to_sections():
    """The fallback must be scoped to the same section(s) as the primary
    — correcting in a different scope would be a behavioural change the
    user did not ask for."""
    s = _section_with_pair(
        role_a=(Importance.H, Function.R), role_b=(Importance.S, Function.H),
    )
    d = _only_diag(s)
    assert d.primary_correction.applies_to_sections == ["Drop 1"]
    assert d.fallback_correction.applies_to_sections == ["Drop 1"]


def test_rules_applied_is_never_empty_when_primary_is_populated():
    """Every non-None primary must come with at least one rule slug in
    ``rules_applied`` — the audit trail is mandatory per §6.3 spec."""
    s = _section_with_pair(
        role_a=(Importance.H, Function.R), role_b=(Importance.S, Function.H),
    )
    d = _only_diag(s)
    assert d.primary_correction is not None
    assert len(d.rules_applied) >= 1


def test_compute_primary_recommendation_ignores_non_masking_issues():
    """Future issue types (accumulation_risk, resonance_buildup, …) must
    not trigger the masking matrix — they'll each have their own
    recommendation function."""
    from cde_engine import (
        CDE_VERSION, CorrectionDiagnostic, ProblemMeasurement,
        SectionContext, TFPContext,
    )
    from datetime import datetime

    bogus = CorrectionDiagnostic(
        diagnostic_id="ACC_DROP1_PAD_247HZ",
        timestamp=datetime.now(),
        cde_version=CDE_VERSION,
        track_a="Pad",
        track_b=None,
        section="Drop 1",
        issue_type="accumulation_risk",
        severity="moderate",
        measurement=ProblemMeasurement(
            frequency_hz=247.0, peak_db=-6.0, duration_in_section_s=8.0,
            duration_ratio_in_section=0.6, is_audible_fraction=0.6,
            severity_score=0.5, masking_score=None,
        ),
        tfp_context=TFPContext(
            track_a_role=(Importance.H, Function.M),
            track_b_role=None, role_compatibility="compatible",
        ),
        section_context=SectionContext(
            section_name="Drop 1", section_duration_s=8.0,
            tracks_active_count=12, conflicts_in_section=0,
            coherence_score=None,
        ),
        diagnosis_text="",
    )
    primary, rules = compute_primary_recommendation(bogus)
    assert primary is None
    assert rules == []
