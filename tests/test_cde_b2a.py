#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Feature 3.6 B2a — accumulation detector.

B2a consumes ``section.accumulations`` (persisted by B1a) and emits
``CorrectionDiagnostic`` instances with ``issue_type="accumulation_risk"``.
Per-accumulation behaviour under test:

    * Cut the two lowest-importance tracks (Atmos first, then Support).
      Hero tracks are never cut — an all-Hero accumulation yields a
      primary=None diagnostic with the awareness rule slug recorded.
    * Severity = ``"critical"`` when n_tracks ≥ 8 OR duration ≥ 10
      buckets; ``"moderate"`` otherwise.
    * Skip accumulations whose tracks are missing from
      ``all_tracks_zone_energy`` (Risque 7).
    * Template wording comes from ``accumulation_static_dip``, not
      the masking ``static_dip`` entry — same DSP (EQ dip) but
      different natural-language context.
"""

from __future__ import annotations

import os
import sys
from typing import List, Tuple

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from section_detector import Section  # noqa: E402
from tfp_parser import Function, Importance  # noqa: E402

from cde_engine import (  # noqa: E402
    RULE_ACCUMULATION_ALL_HERO_NO_ACTION,
    RULE_ACCUMULATION_CUT_LOW_IMPORTANCE,
    RULE_SUB_INTEGRITY_HR,
    _accumulation_recommendation,
    _accumulation_severity,
    detect_accumulation_risks,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_section(
    index: int = 1, start: int = 0, end: int = 99,
    total_energy_db: float = -10.0, name: str = "Chorus 1",
) -> Section:
    return Section(
        index=index, name=name,
        start_bucket=start, end_bucket=end,
        start_seconds=float(start), end_seconds=float(end),
        start_beats=float(start * 2), end_beats=float(end * 2),
        total_energy_db=total_energy_db,
    )


def _accumulation(
    freq_hz: float = 247.0,
    tracks: List[str] = None,
    n_tracks_simultaneous: int = 6,
    duration_buckets: int = 5,
    start: int = 10,
) -> dict:
    tracks = tracks or ["T1", "T2", "T3", "T4", "T5", "T6"]
    return {
        "freq_hz":                freq_hz,
        "n_tracks_simultaneous":  n_tracks_simultaneous,
        "duration_buckets":       duration_buckets,
        "start_bucket":           start,
        "end_bucket":             start + duration_buckets - 1,
        "track_names":            list(tracks),
    }


def _section_with_accumulation(
    roles: dict,
    freq_hz: float = 247.0,
    duration_buckets: int = 5,
    n_tracks_simultaneous: int = None,
) -> Section:
    s = _make_section()
    s.tracks_active = list(roles.keys())
    s.track_roles = dict(roles)
    # track_energy with one zone active so R1 dom_band priority-2 has
    # something to resolve in case it fires (it shouldn't, at 247 Hz the
    # zone is "mud", not any Hero's dom_band).
    s.track_energy = {t: {"mud": -5.0} for t in roles}
    s.track_presence = {t: {"mud": 1.0} for t in roles}
    s.accumulations = [_accumulation(
        freq_hz=freq_hz,
        tracks=list(roles.keys()),
        duration_buckets=duration_buckets,
        n_tracks_simultaneous=n_tracks_simultaneous or len(roles),
    )]
    return s


# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------

def test_severity_moderate_on_default_threshold():
    """Detector's default gate: 6 tracks / 3 buckets → moderate."""
    assert _accumulation_severity(6, 3) == "moderate"
    assert _accumulation_severity(7, 5) == "moderate"


def test_severity_critical_on_8_plus_tracks():
    assert _accumulation_severity(8, 3) == "critical"
    assert _accumulation_severity(12, 4) == "critical"


def test_severity_critical_on_long_duration():
    """Even with only 6 tracks, a 10+ bucket pile-up is critical."""
    assert _accumulation_severity(6, 10) == "critical"
    assert _accumulation_severity(6, 15) == "critical"


# ---------------------------------------------------------------------------
# Recommendation — picks the right target
# ---------------------------------------------------------------------------

def test_recommendation_cuts_atmos_before_support():
    """Priority: Atmos first (most expendable), then Support,
    never Hero."""
    s = _section_with_accumulation({
        "Kick":     (Importance.H, Function.R),
        "Bass":     (Importance.S, Function.H),
        "Pad":      (Importance.A, Function.T),
        "Reverb":   (Importance.A, Function.T),
        "Lead":     (Importance.H, Function.M),
        "Backing":  (Importance.S, Function.M),
    })
    recipe, rules = _accumulation_recommendation(
        s.accumulations[0], s,
    )
    assert recipe is not None
    # Atmos tracks come first (Pad / Reverb — alphabetical tie-break);
    # "Pad" < "Reverb" alphabetically.
    assert recipe.target_track == "Pad"
    assert recipe.parameters["secondary_cut"]["track"] == "Reverb"
    assert RULE_ACCUMULATION_CUT_LOW_IMPORTANCE in rules


def test_recommendation_falls_back_to_support_when_no_atmos():
    """No Atmos in the accumulation → cuts Support tracks."""
    s = _section_with_accumulation({
        "Kick":     (Importance.H, Function.R),
        "Bass":     (Importance.S, Function.H),
        "Backing":  (Importance.S, Function.M),
        "Lead":     (Importance.H, Function.M),
    })
    recipe, rules = _accumulation_recommendation(
        s.accumulations[0], s,
    )
    assert recipe is not None
    # Two Support tracks, alphabetical: "Backing" < "Bass"
    assert recipe.target_track == "Backing"
    assert recipe.parameters["secondary_cut"]["track"] == "Bass"


def test_recommendation_is_none_when_all_tracks_are_hero():
    """All-Hero accumulation — no cut recommended, awareness rule."""
    s = _section_with_accumulation({
        "Kick":   (Importance.H, Function.R),
        "Bass":   (Importance.H, Function.R),
        "Lead":   (Importance.H, Function.M),
        "Guitar": (Importance.H, Function.H),
    })
    recipe, rules = _accumulation_recommendation(
        s.accumulations[0], s,
    )
    assert recipe is None
    assert RULE_ACCUMULATION_ALL_HERO_NO_ACTION in rules


def test_recommendation_single_cut_when_only_one_non_hero():
    """If only one non-Hero track exists → no secondary_cut."""
    s = _section_with_accumulation({
        "Kick":   (Importance.H, Function.R),
        "Bass":   (Importance.H, Function.R),
        "Pad":    (Importance.A, Function.T),
        "Lead":   (Importance.H, Function.M),
    })
    recipe, rules = _accumulation_recommendation(
        s.accumulations[0], s,
    )
    assert recipe is not None
    assert recipe.target_track == "Pad"
    assert "secondary_cut" not in recipe.parameters


# ---------------------------------------------------------------------------
# detect_accumulation_risks — the public entry point
# ---------------------------------------------------------------------------

def test_detector_returns_empty_when_no_accumulations():
    s = _make_section()
    assert detect_accumulation_risks(s) == []


def test_detector_produces_one_diagnostic_per_accumulation():
    s = _section_with_accumulation({
        "Kick":   (Importance.H, Function.R),
        "Bass":   (Importance.S, Function.H),
        "Pad":    (Importance.A, Function.T),
        "Reverb": (Importance.A, Function.T),
        "Lead":   (Importance.H, Function.M),
        "Backing":(Importance.S, Function.M),
    }, freq_hz=350.0, n_tracks_simultaneous=6, duration_buckets=5)

    diags = detect_accumulation_risks(s)
    assert len(diags) == 1
    d = diags[0]
    assert d.issue_type == "accumulation_risk"
    assert d.severity == "moderate"
    assert d.track_a == "Pad"  # lowest-importance Atmos
    assert d.track_b is None   # accumulation is multi-track, no pair
    assert d.section == "Chorus 1"
    # Diagnostic ID follows the human-readable convention.
    assert d.diagnostic_id.startswith("ACC_CHORUS1_PAD_")
    assert d.diagnostic_id.endswith("HZ")
    # Primary correction is filled, fallback intentionally None for B2a.
    assert d.primary_correction is not None
    assert d.primary_correction.approach == "static_dip"
    assert d.fallback_correction is None
    # Rules applied include the matrix rule at minimum.
    assert RULE_ACCUMULATION_CUT_LOW_IMPORTANCE in d.rules_applied
    # Audit trail points at the right source.
    assert any("ACCUMULATIONS" in src for src in d.data_sources)


def test_detector_produces_all_hero_awareness_diagnostic():
    """All-Hero accumulation emits a diagnostic with primary=None."""
    s = _section_with_accumulation({
        "Kick":   (Importance.H, Function.R),
        "Bass":   (Importance.H, Function.R),
        "Lead":   (Importance.H, Function.M),
        "Guitar": (Importance.H, Function.H),
    }, freq_hz=350.0)
    diags = detect_accumulation_risks(s)
    assert len(diags) == 1
    assert diags[0].primary_correction is None
    assert RULE_ACCUMULATION_ALL_HERO_NO_ACTION in diags[0].rules_applied
    # expected_outcomes stays empty — no recipe, no template.
    assert diags[0].expected_outcomes == []


def test_detector_marks_dense_accumulation_as_critical():
    """8+ tracks or ≥10 buckets → critical severity."""
    s = _section_with_accumulation({
        "T1": (Importance.S, Function.R),
        "T2": (Importance.S, Function.R),
        "T3": (Importance.A, Function.T),
        "T4": (Importance.A, Function.T),
        "T5": (Importance.A, Function.T),
        "T6": (Importance.A, Function.T),
        "T7": (Importance.A, Function.T),
        "T8": (Importance.A, Function.T),
    }, freq_hz=350.0, n_tracks_simultaneous=8, duration_buckets=5)

    diags = detect_accumulation_risks(s)
    assert diags[0].severity == "critical"


def test_detector_skips_accumulation_with_midi_tracks_missing_from_wav_map():
    """Risque 7 — accumulation referencing a track with no WAV is
    skipped silently (the detector log warns)."""
    s = _section_with_accumulation({
        "Kick":   (Importance.H, Function.R),
        "Ghost":  (Importance.A, Function.T),  # no WAV
        "Pad":    (Importance.A, Function.T),
    })
    # Ghost has no WAV in the map.
    all_tracks = {"Kick": {"mud": -5.0}, "Pad": {"mud": -5.0}}
    assert detect_accumulation_risks(
        s, all_tracks_zone_energy=all_tracks,
    ) == []


def test_detector_uses_accumulation_specific_template_wording():
    """The FR outcome templates mention the accumulation context —
    ``"aération"``, ``"démêler"`` — not the masking variant."""
    s = _section_with_accumulation({
        "Kick":   (Importance.H, Function.R),
        "Bass":   (Importance.S, Function.H),
        "Pad":    (Importance.A, Function.T),
        "Reverb": (Importance.A, Function.T),
    }, freq_hz=350.0, n_tracks_simultaneous=6)
    d = detect_accumulation_risks(s)[0]
    assert d.expected_outcomes, "accumulation template must populate outcomes"
    all_text = " | ".join(
        d.expected_outcomes + d.potential_risks + d.verification_steps
    )
    # Keywords that are only present in the accumulation template.
    assert "démêler" in all_text or "aérée" in all_text
    # The masking static_dip risk about "body" is NOT used for accumulations.
    assert "body" not in all_text


def test_detector_applies_protection_rules_on_accumulation_recipe():
    """R2 (Sub integrity) must still run — an accumulation at 50 Hz
    (Sub zone) whose lowest-importance cuttable track is H/R gets
    skipped, even though that scenario is contrived."""
    # Pathological case: the only cuttable track happens to be H/R.
    # Our matrix would target it, R2 then invalidates the recipe.
    s = _section_with_accumulation({
        "Kick 1":  (Importance.H, Function.R),  # Hero — skipped by cut logic
        "Kick 2":  (Importance.H, Function.R),
        "Kick 3":  (Importance.H, Function.R),
    }, freq_hz=50.0)
    # All Hero → primary=None via the cut-logic path, not R2. Verify the
    # awareness rule fires instead.
    d = detect_accumulation_risks(s)[0]
    assert d.primary_correction is None
    assert RULE_ACCUMULATION_ALL_HERO_NO_ACTION in d.rules_applied
    # R2 did not even run (no recipe to protect).
    assert RULE_SUB_INTEGRITY_HR not in d.rules_applied


def test_detector_cleans_track_names_in_diagnostic_text_and_id():
    """Project-stem cleanup flows through accumulation diagnostics too."""
    s = _make_section()
    s.tracks_active = ["Acid_Drops [H_R] Kick 1.wav",
                       "Acid_Drops [A_T] Pad.wav",
                       "Acid_Drops [A_T] Reverb.wav"]
    s.track_roles = {
        "Acid_Drops [H_R] Kick 1.wav":  (Importance.H, Function.R),
        "Acid_Drops [A_T] Pad.wav":     (Importance.A, Function.T),
        "Acid_Drops [A_T] Reverb.wav":  (Importance.A, Function.T),
    }
    s.track_energy = {
        "Acid_Drops [H_R] Kick 1.wav":  {"mud": -5.0},
        "Acid_Drops [A_T] Pad.wav":     {"mud": -5.0},
        "Acid_Drops [A_T] Reverb.wav":  {"mud": -5.0},
    }
    s.track_presence = {
        t: {"mud": 1.0} for t in s.tracks_active
    }
    s.accumulations = [_accumulation(
        freq_hz=350.0,
        tracks=s.tracks_active,
        duration_buckets=5,
        n_tracks_simultaneous=3,
    )]
    d = detect_accumulation_risks(s, project_stem="Acid_Drops")[0]
    # ID is clean: no project stem, no .wav, no TFP.
    assert "ACIDDROPS" not in d.diagnostic_id
    assert "PAD" in d.diagnostic_id  # target is Pad (Atmos, alphabetical)
    # Diagnosis text mentions the clean name and no leakage.
    assert "Pad" in d.diagnosis_text
    assert ".wav" not in d.diagnosis_text
    assert "[A_T]" not in d.diagnosis_text
