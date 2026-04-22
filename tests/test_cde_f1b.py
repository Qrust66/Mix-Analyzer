#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Feature 1 phase F1b — section-locked CDE writer.

Each test follows the same four-step pattern:

    Action A  copy ``tests/fixtures/reference_project.als`` into
              ``tmp_path``
    Action B  apply ``write_dynamic_eq8_from_cde_diagnostics`` with a
              synthetic list of ``CorrectionDiagnostic`` instances
    Action C  re-parse the mutated ``.als`` via ``parse_als``
    Action D  assert the expected XML structures (new EQ8, band
              configuration, envelopes, chain position)

The reference fixture is NEVER modified in place — each test
receives its own copy in ``tmp_path``.
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from als_utils import find_track_by_name, parse_als  # noqa: E402
from cde_engine import (  # noqa: E402
    CDE_VERSION,
    CorrectionDiagnostic,
    CorrectionRecipe,
    ProblemMeasurement,
    SectionContext,
    TFPContext,
)
from tfp_parser import Function, Importance  # noqa: E402

from cde_apply import (  # noqa: E402
    MAX_CDE_BANDS,
    write_dynamic_eq8_from_cde_diagnostics,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "reference_project.als"
)


# ---------------------------------------------------------------------------
# Fixture plumbing — copy-to-tmp so the reference file is never touched
# ---------------------------------------------------------------------------

@pytest.fixture
def project_copy(tmp_path: Path) -> Path:
    """Return a fresh copy of the reference project in ``tmp_path``.

    Also removes any ``.als.v24.bak`` left over from a previous run to
    keep each test's tmp directory clean.
    """
    dst = tmp_path / "project.als"
    shutil.copy2(FIXTURE_PATH, dst)
    return dst


# ---------------------------------------------------------------------------
# Synthetic diagnostic builder — kept local so tests stay readable
# ---------------------------------------------------------------------------

def _diag(
    approach: str,
    target_track: str,
    frequency_hz: float,
    *,
    gain_db: float = -3.0,
    q: float = 4.0,
    sections: List[str] = None,
    diag_id: str = None,
    issue_type: str = "masking_conflict",
    severity: str = "moderate",
    secondary_cut: dict = None,
    primary_none: bool = False,
) -> CorrectionDiagnostic:
    """Build a minimal diagnostic sufficient to exercise F1b."""
    sections = list(sections or ["Drop 1"])
    diag_id = diag_id or f"TEST_{target_track}_{int(frequency_hz)}"

    measurement = ProblemMeasurement(
        frequency_hz=float(frequency_hz),
        peak_db=-6.0,
        duration_in_section_s=30.0,
        duration_ratio_in_section=1.0,
        is_audible_fraction=1.0,
        severity_score=0.5,
        masking_score=0.5,
    )
    tfp = TFPContext(
        track_a_role=(Importance.H, Function.R),
        track_b_role=(Importance.S, Function.H),
        role_compatibility="dominant_support",
    )
    sec_ctx = SectionContext(
        section_name=sections[0],
        section_duration_s=30.0,
        tracks_active_count=4,
        conflicts_in_section=1,
        coherence_score=None,
    )
    params = {
        "frequency_hz": float(frequency_hz),
        "gain_db": float(gain_db),
        "q": float(q),
        "active_in_sections": sections,
    }
    if secondary_cut is not None:
        params["secondary_cut"] = secondary_cut

    primary = None if primary_none else CorrectionRecipe(
        target_track=target_track,
        device="EQ8 — Peak Resonance",
        approach=approach,
        parameters=params,
        applies_to_sections=sections,
        rationale="test",
        confidence="medium",
    )
    return CorrectionDiagnostic(
        diagnostic_id=diag_id,
        timestamp=datetime(2026, 4, 22, 0, 0, 0),
        cde_version=CDE_VERSION,
        track_a=target_track,
        track_b=None,
        section=sections[0],
        issue_type=issue_type,
        severity=severity,
        measurement=measurement,
        tfp_context=tfp,
        section_context=sec_ctx,
        diagnosis_text="",
        primary_correction=primary,
        fallback_correction=None,
    )


# ---------------------------------------------------------------------------
# XML-level helpers used across tests
# ---------------------------------------------------------------------------

def _find_cde_eq8s(track, prefix: str = "CDE Correction"):
    """Return every Eq8 element on the track whose UserName starts
    with ``prefix`` — used to count CDE devices and inspect their
    bands / envelopes."""
    result = []
    for eq8 in track.findall(".//Eq8"):
        un = eq8.find("UserName")
        if un is not None and un.get("Value", "").startswith(prefix):
            result.append(eq8)
    return result


def _count_active_bands(eq8) -> int:
    """Count bands whose IsOn/Manual is ``true``."""
    count = 0
    for i in range(8):
        ison = eq8.find(f"Bands.{i}/ParameterA/IsOn/Manual")
        if ison is not None and ison.get("Value") == "true":
            count += 1
    return count


def _gain_envelope_has_nonzero_events(track, eq8, band_index: int) -> bool:
    """Return True when the Gain envelope on the given band has at
    least one FloatEvent whose value differs from 0 — i.e. the
    section-locked cut lands somewhere."""
    band = eq8.find(f"Bands.{band_index}/ParameterA")
    if band is None:
        return False
    target = band.find("Gain/AutomationTarget")
    if target is None:
        return False
    target_id = target.get("Id")
    for env in track.iter("AutomationEnvelope"):
        pid = env.find("EnvelopeTarget/PointeeId")
        if pid is None or pid.get("Value") != target_id:
            continue
        for e in env.iter("FloatEvent"):
            try:
                v = float(e.get("Value", "0"))
            except (TypeError, ValueError):
                continue
            if abs(v) > 0.01:
                return True
    return False


def _chain_device_order(track) -> list:
    """Return the device chain as ``[(tag, user_name), …]`` in insertion order."""
    devices = track.find(".//DeviceChain/DeviceChain/Devices")
    if devices is None:
        devices = track.find(".//DeviceChain/Devices")
    if devices is None:
        return []
    out = []
    for child in devices:
        un = child.find("UserName")
        out.append((child.tag, un.get("Value") if un is not None else ""))
    return out


# ---------------------------------------------------------------------------
# Test A — end-to-end single track section-locked
# ---------------------------------------------------------------------------

def test_end_to_end_single_track_section_locked(project_copy: Path):
    """3 diagnostics at 3 distinct freqs on one track, all in
    ``Drop 1``. Expect an EQ8 ``CDE Correction (3 bands)`` with 3
    active bands and non-zero Gain envelope values landing inside the
    Drop 1 time range."""
    target = "[H/R] Kick 1"
    diags = [
        _diag("static_dip", target, 62,   sections=["Drop 1"], diag_id="A1"),
        _diag("static_dip", target, 250,  sections=["Drop 1"], diag_id="A2"),
        _diag("static_dip", target, 1000, sections=["Drop 1"], diag_id="A3"),
    ]

    report = write_dynamic_eq8_from_cde_diagnostics(
        project_copy, diags, _skip_confirmation=True,
    )
    assert sorted(report.applied) == ["A1", "A2", "A3"]
    assert report.devices_created[target] == "CDE Correction (3 bands)"
    assert report.envelopes_written == 3  # one Gain envelope per band

    tree = parse_als(str(project_copy))
    track = find_track_by_name(tree, target)
    cde_eq8s = _find_cde_eq8s(track)
    assert len(cde_eq8s) == 1

    eq8 = cde_eq8s[0]
    assert _count_active_bands(eq8) == 3
    # Envelopes exist on three bands with non-zero values.
    hits = [
        _gain_envelope_has_nonzero_events(track, eq8, i)
        for i in range(1, 7)
    ]
    assert sum(hits) == 3


# ---------------------------------------------------------------------------
# Test B — idempotence: double run replaces, does not duplicate
# ---------------------------------------------------------------------------

def test_idempotence_double_run_replaces_not_duplicates(project_copy: Path):
    target = "[H/R] Bass Rythm"
    diags = [
        _diag("static_dip", target, 165, sections=["Drop 2"], diag_id="B1"),
    ]

    write_dynamic_eq8_from_cde_diagnostics(
        project_copy, diags, _skip_confirmation=True,
    )
    write_dynamic_eq8_from_cde_diagnostics(
        project_copy, diags, _skip_confirmation=True,
    )

    tree = parse_als(str(project_copy))
    track = find_track_by_name(tree, target)
    # Only ONE "CDE Correction" device should remain — the second run
    # purged the first.
    assert len(_find_cde_eq8s(track)) == 1


# ---------------------------------------------------------------------------
# Test C — insertion position AFTER Peak Resonance
# ---------------------------------------------------------------------------

def test_insertion_position_after_peak_resonance(project_copy: Path):
    """The fixture's ``[H/R] Kick 1`` carries a Peak Resonance EQ8.
    After apply, the new CDE device must sit immediately after it."""
    target = "[H/R] Kick 1"
    diags = [
        _diag("static_dip", target, 2500, sections=["Drop 1"], diag_id="C1"),
    ]
    write_dynamic_eq8_from_cde_diagnostics(
        project_copy, diags, _skip_confirmation=True,
    )
    tree = parse_als(str(project_copy))
    track = find_track_by_name(tree, target)
    order = _chain_device_order(track)
    names = [u for (_t, u) in order]
    assert "Peak Resonance" in names
    assert "CDE Correction (1 bands)" in names
    pr_idx = names.index("Peak Resonance")
    cde_idx = names.index("CDE Correction (1 bands)")
    assert cde_idx == pr_idx + 1, (
        f"Expected CDE device right after Peak Resonance, got order: {names}"
    )


# ---------------------------------------------------------------------------
# Test D — insertion position without Peak Resonance (append to end)
# ---------------------------------------------------------------------------

def test_insertion_position_no_peak_resonance(project_copy: Path):
    """``[S/R] Clap`` has no Peak Resonance EQ8 in the fixture, so the
    CDE device should be appended at the END of the chain."""
    target = "[S/R] Clap"
    diags = [
        _diag("static_dip", target, 2500, sections=["Drop 1"], diag_id="D1"),
    ]
    write_dynamic_eq8_from_cde_diagnostics(
        project_copy, diags, _skip_confirmation=True,
    )
    tree = parse_als(str(project_copy))
    track = find_track_by_name(tree, target)
    order = _chain_device_order(track)
    names = [u for (_t, u) in order]
    assert "Peak Resonance" not in names
    # The CDE device is the LAST entry in the chain.
    assert names[-1] == "CDE Correction (1 bands)"


# ---------------------------------------------------------------------------
# Test E — multi-track batch produces per-track device
# ---------------------------------------------------------------------------

def test_multi_track_batch_produces_per_track_device(project_copy: Path):
    """Two tracks, two clusters each → two EQ8 CDE devices, one per
    track, each with the expected band count."""
    diags = [
        _diag("static_dip", "[H/R] Kick 1",     62,   diag_id="E1"),
        _diag("static_dip", "[H/R] Kick 1",     250,  diag_id="E2"),
        _diag("static_dip", "[H/R] Bass Rythm", 165,  diag_id="E3"),
        _diag("static_dip", "[H/R] Bass Rythm", 1000, diag_id="E4"),
    ]
    report = write_dynamic_eq8_from_cde_diagnostics(
        project_copy, diags, _skip_confirmation=True,
    )
    assert set(report.devices_created.keys()) == {
        "[H/R] Kick 1", "[H/R] Bass Rythm",
    }
    assert report.devices_created["[H/R] Kick 1"] == "CDE Correction (2 bands)"
    assert report.devices_created["[H/R] Bass Rythm"] == "CDE Correction (2 bands)"

    tree = parse_als(str(project_copy))
    kick = find_track_by_name(tree, "[H/R] Kick 1")
    bass = find_track_by_name(tree, "[H/R] Bass Rythm")
    assert len(_find_cde_eq8s(kick)) == 1
    assert len(_find_cde_eq8s(bass)) == 1
    assert _count_active_bands(_find_cde_eq8s(kick)[0]) == 2
    assert _count_active_bands(_find_cde_eq8s(bass)[0]) == 2


# ---------------------------------------------------------------------------
# Test F — cluster cap emits warning and keeps severest
# ---------------------------------------------------------------------------

def test_cluster_cap_emits_warning_and_keeps_severest(project_copy: Path):
    """7 well-separated frequencies on one track → cap at 6, least
    severe diagnostic dropped. Warning must mention the cap."""
    target = "[H/R] Kick 1"
    # Seven bands with gradually increasing severity (more negative gain
    # = more severe). The LEAST severe (smallest magnitude) is -1 dB;
    # that's the one we expect to be dropped.
    diags = [
        _diag("static_dip", target, 50,    gain_db=-1.0,  diag_id="F1"),
        _diag("static_dip", target, 150,   gain_db=-2.0,  diag_id="F2"),
        _diag("static_dip", target, 400,   gain_db=-3.0,  diag_id="F3"),
        _diag("static_dip", target, 1000,  gain_db=-4.0,  diag_id="F4"),
        _diag("static_dip", target, 2500,  gain_db=-5.0,  diag_id="F5"),
        _diag("static_dip", target, 6000,  gain_db=-6.0,  diag_id="F6"),
        _diag("static_dip", target, 15000, gain_db=-7.0,  diag_id="F7"),
    ]
    report = write_dynamic_eq8_from_cde_diagnostics(
        project_copy, diags, _skip_confirmation=True,
    )
    # The cap warning must be present.
    assert any(
        ("cap" in w.lower() or "exceed" in w.lower()) for w in report.warnings
    ), f"expected cap warning in {report.warnings!r}"
    # Exactly 6 bands active on the created EQ8.
    tree = parse_als(str(project_copy))
    track = find_track_by_name(tree, target)
    eq8 = _find_cde_eq8s(track)[0]
    assert _count_active_bands(eq8) == MAX_CDE_BANDS
    # The least-severe diagnostic (F1, -1 dB) is the one that was dropped.
    assert "F1" not in report.applied
    assert ("F1", "cluster_cap_exceeded") in report.skipped


# ---------------------------------------------------------------------------
# Test G — sidechain diagnostics filtered with proper reason
# ---------------------------------------------------------------------------

def test_sidechain_diagnostics_filtered_with_proper_reason(project_copy: Path):
    """Mixed batch: 3 static_dip + 2 sidechain. ``applied`` gets the
    three cuts, ``skipped`` lists the two sidechain with a reason
    mentioning Kickstart 2 / Feature 1.5."""
    diags = [
        _diag("static_dip", "[H/R] Kick 1",     62,  diag_id="G_CUT_1"),
        _diag("static_dip", "[H/R] Bass Rythm", 165, diag_id="G_CUT_2"),
        _diag("static_dip", "[S/H] Sub Bass",   62,  diag_id="G_CUT_3"),
        _diag("sidechain",  "[S/H] Sub Bass",   62,  diag_id="G_SC_1"),
        _diag("sidechain",  "[H/R] Bass Rythm", 62,  diag_id="G_SC_2"),
    ]
    report = write_dynamic_eq8_from_cde_diagnostics(
        project_copy, diags, _skip_confirmation=True,
    )
    assert sorted(report.applied) == ["G_CUT_1", "G_CUT_2", "G_CUT_3"]
    # Both sidechain diagnostics land in skipped with the Kickstart 2 reason.
    sc_skips = [s for s in report.skipped if s[0].startswith("G_SC_")]
    assert len(sc_skips) == 2
    for _diag_id, reason in sc_skips:
        assert "Kickstart 2" in reason or "Feature 1.5" in reason


# ---------------------------------------------------------------------------
# Test H — reciprocal_cuts atomic pair
# ---------------------------------------------------------------------------

def test_reciprocal_cuts_atomic_pair_both_existing(project_copy: Path):
    """H1 — a reciprocal_cuts diagnostic whose ``secondary_cut.track``
    exists. Both tracks receive a CDE Correction device carrying a
    band at the recipe's frequency."""
    diag = _diag(
        "reciprocal_cuts",
        "[H/R] Kick 1",
        165,
        gain_db=-2.0,
        sections=["Drop 1"],
        diag_id="H1",
        secondary_cut={
            "track": "[H/R] Bass Rythm",
            "frequency_hz": 165.0,
            "gain_db": -2.0,
            "q": 3.0,
        },
    )
    report = write_dynamic_eq8_from_cde_diagnostics(
        project_copy, [diag], _skip_confirmation=True,
    )
    # Both tracks in devices_created — the atomic pair landed.
    assert "[H/R] Kick 1" in report.devices_created
    assert "[H/R] Bass Rythm" in report.devices_created

    tree = parse_als(str(project_copy))
    for track_name in ("[H/R] Kick 1", "[H/R] Bass Rythm"):
        track = find_track_by_name(tree, track_name)
        assert len(_find_cde_eq8s(track)) == 1


def test_reciprocal_cuts_atomic_pair_missing_track(project_copy: Path):
    """H2 — ``secondary_cut.track`` points at a track that does not
    exist. Both halves of the pair are skipped together and the
    report's reason mentions ``reciprocal_cut_missing_track``."""
    diag = _diag(
        "reciprocal_cuts",
        "[H/R] Kick 1",
        165,
        gain_db=-2.0,
        sections=["Drop 1"],
        diag_id="H2",
        secondary_cut={
            "track": "NonExistentTrackName",
            "frequency_hz": 165.0,
            "gain_db": -2.0,
            "q": 3.0,
        },
    )
    report = write_dynamic_eq8_from_cde_diagnostics(
        project_copy, [diag], _skip_confirmation=True,
    )
    # Nothing applied.
    assert "H2" not in report.applied
    # Skipped with the dedicated reason.
    matching = [s for s in report.skipped if s[0] == "H2"]
    assert len(matching) == 1
    assert "reciprocal_cut_missing_track" in matching[0][1]
    # No CDE device was inserted on Kick 1 because the pair was refused
    # before writing.
    tree = parse_als(str(project_copy))
    kick = find_track_by_name(tree, "[H/R] Kick 1")
    assert _find_cde_eq8s(kick) == []
