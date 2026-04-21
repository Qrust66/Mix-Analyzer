#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Feature 3.6 B1c2a — protection rules + coherence invariance.

B1c2a wires three §6.3 protection rules after the B1c1 primary matrix:

    R2 Sub integrity (Hero Rhythm)   — can skip the whole recipe
    R1 Signature frequency protection — caps gain at -2 dB in dom_band
    R3 Role-appropriate max cut       — caps gain by Importance

Rules apply in the order R2 → R1 → R3. Each rule targets only cut
approaches (``static_dip``, ``musical_dip``, ``reciprocal_cuts``);
sidechain depth is a different dynamic-reduction concept and is left
untouched by these EQ-oriented rules.

The file also pins the invariance between :mod:`tfp_coherence` and
the CDE's ``active_tracks_with_roles`` path — Risque 6 of the F3.6
recon: no silent drift between the two consumers of that filter.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from typing import Tuple

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from section_detector import Section, active_tracks_with_roles  # noqa: E402
from tfp_coherence import compute_section_coherence_score  # noqa: E402
from tfp_parser import Function, Importance  # noqa: E402

from cde_engine import (  # noqa: E402
    RULE_ROLE_APPROPRIATE_MAX_CUT,
    RULE_SIGNATURE_FREQ_PROTECTION,
    RULE_SUB_INTEGRITY_HR,
    ZONE_CENTER_HZ,
    CorrectionRecipe,
    apply_protection_rules,
    detect_masking_conflicts,
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
    zone: str = "sub",
) -> Section:
    """One-conflict section set up so the detector will process it."""
    s = _make_section(1, 0, 29, total_energy_db=-10.0)
    s.tracks_active = [track_a, track_b]
    s.track_roles = {track_a: role_a, track_b: role_b}
    s.track_presence = {
        track_a: {zone: 1.0},
        track_b: {zone: 1.0},
    }
    # Populate track_energy so Rule 1's priority-2 dom_band lookup has
    # something to return.
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
        "score": 0.87,
        "severity": "critical",
    }]
    return s


def _only_diag(section: Section, **kwargs):
    diags = detect_masking_conflicts(section, **kwargs)
    assert len(diags) == 1
    return diags[0]


# Helper to make a diagnostic with a crafted recipe, used by the Rule 3
# tests (the primary matrix never produces gains deep enough to trigger
# Rule 3 on real inputs — we exercise it via a hand-built recipe).

def _diag_with_role(role_target: Tuple[Importance, Function], track: str = "Target"):
    """Build a minimal diagnostic whose track_a has the given role."""
    from datetime import datetime
    from cde_engine import (
        CDE_VERSION, CorrectionDiagnostic, ProblemMeasurement,
        SectionContext, TFPContext,
    )
    return CorrectionDiagnostic(
        diagnostic_id="CRAFTED",
        timestamp=datetime.now(),
        cde_version=CDE_VERSION,
        track_a=track,
        track_b=None,
        section="Drop 1",
        issue_type="masking_conflict",
        severity="critical",
        measurement=ProblemMeasurement(
            frequency_hz=50.0, peak_db=-5.0, duration_in_section_s=29.0,
            duration_ratio_in_section=1.0, is_audible_fraction=1.0,
            severity_score=0.87, masking_score=0.87,
        ),
        tfp_context=TFPContext(
            track_a_role=role_target, track_b_role=None,
            role_compatibility="compatible",
        ),
        section_context=SectionContext(
            section_name="Drop 1", section_duration_s=29.0,
            tracks_active_count=1, conflicts_in_section=1,
            coherence_score=None,
        ),
        diagnosis_text="",
    )


def _crafted_static_dip(target: str, gain_db: float, zone: str = "low") -> CorrectionRecipe:
    return CorrectionRecipe(
        target_track=target,
        device="EQ8 — Peak Resonance",
        approach="static_dip",
        parameters={
            "frequency_hz": float(ZONE_CENTER_HZ[zone]),
            "gain_db": gain_db,
            "q": 4.0,
            "active_in_sections": ["Drop 1"],
        },
        applies_to_sections=["Drop 1"],
        rationale="test recipe",
        confidence="medium",
    )


# ---------------------------------------------------------------------------
# Rule 1 — Signature frequency protection
# ---------------------------------------------------------------------------

def test_rule1_caps_gain_to_minus_2db_on_hero_melodic_in_dom_band():
    """H/M target + dom_band via AI Context = cut zone → gain capped at -2."""
    diag = _diag_with_role((Importance.H, Function.M), track="Acid Bass")
    recipe = _crafted_static_dip("Acid Bass", gain_db=-5.0, zone="sub")
    ai_context = {"Acid Bass": {"dom_band": "sub"}}

    out = apply_protection_rules(diag, recipe, ai_context=ai_context)
    assert out is not None
    assert out.parameters["gain_db"] == -2.0
    assert RULE_SIGNATURE_FREQ_PROTECTION in diag.rules_applied
    assert "signature frequency" in out.rationale


def test_rule1_does_not_trigger_when_freq_outside_dom_band():
    """Recipe freq in sub, but the track's dom_band is mid → R1 no-op.

    Uses a gain (-2.5 dB) within the Hero cap (-3) so R3 does not mask
    R1's behaviour — the test pins R1's decision alone.
    """
    diag = _diag_with_role((Importance.H, Function.M), track="Lead")
    recipe = _crafted_static_dip("Lead", gain_db=-2.5, zone="sub")
    ai_context = {"Lead": {"dom_band": "mid"}}

    out = apply_protection_rules(diag, recipe, ai_context=ai_context)
    assert out.parameters["gain_db"] == -2.5  # untouched by R1 or R3
    assert RULE_SIGNATURE_FREQ_PROTECTION not in diag.rules_applied
    assert RULE_ROLE_APPROPRIATE_MAX_CUT not in diag.rules_applied


def test_rule1_does_not_trigger_on_non_signature_protected_roles():
    """Support and Hero Rhythm are NOT signature-protected by Rule 1."""
    for role in [
        (Importance.S, Function.M),   # Support Melodic
        (Importance.H, Function.R),   # Hero Rhythm (protected by R2, not R1)
        (Importance.A, Function.T),   # Atmos Textural
    ]:
        diag = _diag_with_role(role, track="T")
        # Use a non-sub zone for the H/R case so Rule 2 does not fire.
        recipe = _crafted_static_dip("T", gain_db=-5.0, zone="mid")
        ai_context = {"T": {"dom_band": "mid"}}
        out = apply_protection_rules(diag, recipe, ai_context=ai_context)
        assert out is not None
        assert out.parameters["gain_db"] == -5.0 or \
               out.parameters["gain_db"] == _ROLE_MAX_CUT_CAPS[role[0]], (
                f"Rule 1 must not touch {role}"
            )
        assert RULE_SIGNATURE_FREQ_PROTECTION not in diag.rules_applied


def test_rule1_accepts_zone_label_form_in_ai_context():
    """The dom_band value can be a label (``"Sub (20-80 Hz)"``) or the
    short key (``"sub"``) — both forms must resolve to the zone."""
    diag = _diag_with_role((Importance.H, Function.H), track="Pluck")
    recipe = _crafted_static_dip("Pluck", gain_db=-4.0, zone="sub")
    ai_context = {"Pluck": {"dom_band": "Sub (20-80 Hz)"}}

    out = apply_protection_rules(diag, recipe, ai_context=ai_context)
    assert out.parameters["gain_db"] == -2.0
    assert RULE_SIGNATURE_FREQ_PROTECTION in diag.rules_applied


# Rule 3 expected caps used by the Rule 1 cross-test above.
_ROLE_MAX_CUT_CAPS = {
    Importance.H: -3.0,
    Importance.S: -5.0,  # unreachable — -5 dB is within -6 cap so no cap
    Importance.A: -5.0,  # unreachable — -5 dB is within -12 cap so no cap
}


# ---------------------------------------------------------------------------
# Rule 2 — Sub integrity for Hero Rhythm
# ---------------------------------------------------------------------------

def test_rule2_skips_static_dip_on_hero_rhythm_in_sub_zone():
    """Cut at 50 Hz on a Hero Rhythm track → recipe dropped entirely."""
    diag = _diag_with_role((Importance.H, Function.R), track="Kick 1")
    recipe = _crafted_static_dip("Kick 1", gain_db=-5.0, zone="sub")

    out = apply_protection_rules(diag, recipe)
    assert out is None
    assert RULE_SUB_INTEGRITY_HR in diag.rules_applied


def test_rule2_passes_through_when_cut_outside_sub_zone():
    """Kick cut at 350 Hz (mud) — outside the Sub zone → left alone."""
    diag = _diag_with_role((Importance.H, Function.R), track="Kick 1")
    recipe = _crafted_static_dip("Kick 1", gain_db=-3.0, zone="mud")

    out = apply_protection_rules(diag, recipe)
    assert out is not None
    assert out.parameters["gain_db"] == -3.0
    assert RULE_SUB_INTEGRITY_HR not in diag.rules_applied


def test_rule2_skips_reciprocal_cuts_when_both_tracks_are_hr_in_sub():
    """H/R × H/R at 50 Hz — the matrix produces reciprocal_cuts but
    Rule 2 skips it (either cut lands on a Kick in Sub)."""
    s = _section_with_pair(
        role_a=(Importance.H, Function.R), role_b=(Importance.H, Function.R),
        track_a="Kick 1", track_b="Kick 2", zone="sub",
    )
    d = _only_diag(s)
    assert d.primary_correction is None
    # Fallback of reciprocal_cuts is static_dip on track_a, still H/R in Sub
    # → Rule 2 also skips it.
    assert d.fallback_correction is None
    assert RULE_SUB_INTEGRITY_HR in d.rules_applied


def test_rule2_does_not_affect_sidechain_approach():
    """Sidechain isn't a static cut — R2 must not touch it even on H/R."""
    diag = _diag_with_role((Importance.H, Function.R), track="Kick 1")
    sidechain = CorrectionRecipe(
        target_track="Kick 1",
        device="Kickstart 2",
        approach="sidechain",
        parameters={"trigger_track": "Bass", "depth_db": -8.0, "release_ms": 150},
        applies_to_sections=["Drop 1"],
        rationale="test",
        confidence="high",
    )
    out = apply_protection_rules(diag, sidechain)
    assert out is sidechain or out.parameters["depth_db"] == -8.0
    assert RULE_SUB_INTEGRITY_HR not in diag.rules_applied


# ---------------------------------------------------------------------------
# Rule 3 — Role-appropriate max cut
# ---------------------------------------------------------------------------

def test_rule3_caps_hero_gain_to_minus_3db():
    """Hero target with an engineered -6 dB cut → capped to -3."""
    diag = _diag_with_role((Importance.H, Function.M), track="Lead")
    recipe = _crafted_static_dip("Lead", gain_db=-6.0, zone="mid")

    out = apply_protection_rules(diag, recipe)
    assert out is not None
    assert out.parameters["gain_db"] == -3.0
    assert RULE_ROLE_APPROPRIATE_MAX_CUT in diag.rules_applied
    assert "role-appropriate" in out.rationale.lower()


def test_rule3_caps_support_gain_to_minus_6db():
    diag = _diag_with_role((Importance.S, Function.H), track="Sub Bass")
    recipe = _crafted_static_dip("Sub Bass", gain_db=-10.0, zone="mid")

    out = apply_protection_rules(diag, recipe)
    assert out.parameters["gain_db"] == -6.0
    assert RULE_ROLE_APPROPRIATE_MAX_CUT in diag.rules_applied


def test_rule3_caps_atmos_gain_to_minus_12db():
    diag = _diag_with_role((Importance.A, Function.T), track="Pad")
    recipe = _crafted_static_dip("Pad", gain_db=-20.0, zone="mid")

    out = apply_protection_rules(diag, recipe)
    assert out.parameters["gain_db"] == -12.0
    assert RULE_ROLE_APPROPRIATE_MAX_CUT in diag.rules_applied


def test_rule3_does_not_touch_values_within_cap():
    """Primary-matrix defaults (-3 dB on Atmos, -2 dB reciprocal Hero)
    must never trigger Rule 3 — confirm on a typical static_dip."""
    diag = _diag_with_role((Importance.A, Function.T), track="Pad")
    recipe = _crafted_static_dip("Pad", gain_db=-3.0, zone="mud")

    out = apply_protection_rules(diag, recipe)
    assert out.parameters["gain_db"] == -3.0
    assert RULE_ROLE_APPROPRIATE_MAX_CUT not in diag.rules_applied


def test_rule3_caps_secondary_cut_on_reciprocal_cuts():
    """For reciprocal_cuts, Rule 3 must cap both primary and secondary."""
    diag = _diag_with_role((Importance.S, Function.M), track="Track A")
    # Second track role = Atmos, secondary_cut gain deep enough to cap.
    diag.track_b = "Track B"
    diag.tfp_context.track_b_role = (Importance.A, Function.T)

    recipe = CorrectionRecipe(
        target_track="Track A",
        device="EQ8 — Peak Resonance",
        approach="reciprocal_cuts",
        parameters={
            "frequency_hz": 350.0,
            "gain_db": -10.0,   # Support cap -6
            "q": 3.0,
            "secondary_cut": {
                "track": "Track B",
                "frequency_hz": 350.0,
                "gain_db": -18.0,  # Atmos cap -12
                "q": 3.0,
            },
        },
        applies_to_sections=["Drop 1"],
        rationale="test",
        confidence="medium",
    )
    out = apply_protection_rules(diag, recipe)
    assert out.parameters["gain_db"] == -6.0
    assert out.parameters["secondary_cut"]["gain_db"] == -12.0
    assert RULE_ROLE_APPROPRIATE_MAX_CUT in diag.rules_applied


# ---------------------------------------------------------------------------
# Rule ordering — R2 short-circuits R1 and R3
# ---------------------------------------------------------------------------

def test_rule_ordering_r2_invalidation_short_circuits_r1_and_r3():
    """When R2 skips the recipe, R1 and R3 must not record their slugs —
    they never ran. Only RULE_SUB_INTEGRITY_HR ends up in rules_applied."""
    diag = _diag_with_role((Importance.H, Function.R), track="Kick 1")
    # Deep cut that would trigger both R1 (if H/M) and R3 — but R2 stops.
    recipe = _crafted_static_dip("Kick 1", gain_db=-15.0, zone="sub")
    ai_context = {"Kick 1": {"dom_band": "sub"}}

    out = apply_protection_rules(diag, recipe, ai_context=ai_context)
    assert out is None
    assert diag.rules_applied == [RULE_SUB_INTEGRITY_HR]
    assert RULE_SIGNATURE_FREQ_PROTECTION not in diag.rules_applied
    assert RULE_ROLE_APPROPRIATE_MAX_CUT not in diag.rules_applied


def test_rule_ordering_r1_runs_then_r3_caps_further_if_needed():
    """R1 caps an H/M track at -2 dB (within Hero cap of -3), so R3 does
    not need to fire on the same gain. This pins that R1 runs before R3
    and R3 no-ops when R1's output already satisfies it."""
    diag = _diag_with_role((Importance.H, Function.M), track="Lead")
    recipe = _crafted_static_dip("Lead", gain_db=-10.0, zone="mid")
    ai_context = {"Lead": {"dom_band": "mid"}}

    out = apply_protection_rules(diag, recipe, ai_context=ai_context)
    assert out.parameters["gain_db"] == -2.0  # R1 cap
    assert RULE_SIGNATURE_FREQ_PROTECTION in diag.rules_applied
    # R3 didn't need to cap further since -2 is within -3.
    assert RULE_ROLE_APPROPRIATE_MAX_CUT not in diag.rules_applied


# ---------------------------------------------------------------------------
# Coherence invariance — §6.3 Risque 6
# ---------------------------------------------------------------------------

def test_coherence_and_cde_agree_on_active_role_counts():
    """tfp_coherence's role Counter and the CDE's active_tracks_with_roles
    must agree on the same Section — they both flow through the single
    shared helper (section_detector.active_tracks_with_roles).

    Any future refactor that reintroduces a divergent inline filter on
    either side is caught here.
    """
    s = _make_section(1, 0, 40, total_energy_db=-12.0)
    s.tracks_active = [
        "Kick 1", "Acid Bass", "Sub Bass", "Pad", "Reverb",
    ]
    s.track_roles = {
        "Kick 1":       (Importance.H, Function.R),
        "Acid Bass":    (Importance.H, Function.M),
        "Sub Bass":     (Importance.S, Function.H),
        "Pad":          (Importance.A, Function.T),
        "Reverb":       (Importance.A, Function.T),
        # Extra role not referenced in tracks_active — must be excluded.
        "Bleed":        (Importance.S, Function.R),
    }

    coherence = compute_section_coherence_score(s, conflicts=[])
    counts = coherence["counts"]

    active = active_tracks_with_roles(s)
    imp_counts = Counter(role[0] for role in active.values())
    fn_counts = Counter(role[1] for role in active.values())

    # Importance counts must match.
    assert counts["H"] == imp_counts[Importance.H] == 2
    assert counts["S"] == imp_counts[Importance.S] == 1
    assert counts["A"] == imp_counts[Importance.A] == 2

    # Function counts must match.
    assert counts["fn_R"] == fn_counts[Function.R] == 1
    assert counts["fn_H"] == fn_counts[Function.H] == 1
    assert counts["fn_M"] == fn_counts[Function.M] == 1
    assert counts["fn_T"] == fn_counts[Function.T] == 2

    # "Bleed" is not in tracks_active — must be filtered out from both.
    assert "Bleed" not in active


# ---------------------------------------------------------------------------
# End-to-end integration — the detector calls apply_protection_rules
# ---------------------------------------------------------------------------

def test_detect_masking_conflicts_applies_protection_rules_end_to_end():
    """Running detect_masking_conflicts on an H/R × H/R Sub conflict
    must produce a diagnostic with both primary and fallback set to
    None, and RULE_SUB_INTEGRITY_HR in rules_applied. Pins the wiring
    between the detector and the orchestrator."""
    s = _section_with_pair(
        role_a=(Importance.H, Function.R), role_b=(Importance.H, Function.R),
        track_a="Kick 1", track_b="Kick 2", zone="sub",
    )
    d = _only_diag(s)
    assert d.primary_correction is None
    assert d.fallback_correction is None
    assert RULE_SUB_INTEGRITY_HR in d.rules_applied
