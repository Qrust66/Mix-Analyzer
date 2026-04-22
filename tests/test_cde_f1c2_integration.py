#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests for Feature 1 phase F1c2b — peak-following mode.

Exhaustive end-to-end coverage of ``peak_follow=True`` through
``write_dynamic_eq8_from_cde_diagnostics``. Each test copies the
``reference_project.als`` fixture into ``tmp_path``, runs the
writer, re-parses the resulting ``.als``, and asserts the expected
envelope structure band-by-band.

F1c2a already covered the pure helpers. Here we wire them through
the full writer pipeline (clustering → trajectory matching → curve
building → ``_write_validated_env``) and verify the XML that lands
on disk.
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
from spectral_evolution import PeakTrajectory  # noqa: E402
from tfp_parser import Function, Importance  # noqa: E402

from cde_apply import write_dynamic_eq8_from_cde_diagnostics  # noqa: E402


FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "reference_project.als"
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def project_copy(tmp_path: Path) -> Path:
    """Fresh isolated copy of the reference fixture per test."""
    dst = tmp_path / "project.als"
    shutil.copy2(FIXTURE_PATH, dst)
    return dst


def _diag(
    target_track: str,
    frequency_hz: float,
    sections: List[str],
    *,
    diag_id: str = "D",
    gain_db: float = -4.0,
    q: float = 4.0,
) -> CorrectionDiagnostic:
    return CorrectionDiagnostic(
        diagnostic_id=diag_id,
        timestamp=datetime(2026, 4, 22, 0, 0, 0),
        cde_version=CDE_VERSION,
        track_a=target_track,
        track_b=None,
        section=sections[0],
        issue_type="masking_conflict",
        severity="critical",
        measurement=ProblemMeasurement(
            frequency_hz=float(frequency_hz),
            peak_db=-5.0,
            duration_in_section_s=30.0,
            duration_ratio_in_section=1.0,
            is_audible_fraction=1.0,
            severity_score=0.8,
            masking_score=0.8,
        ),
        tfp_context=TFPContext(
            track_a_role=(Importance.H, Function.R),
            track_b_role=(Importance.S, Function.H),
            role_compatibility="dominant_support",
        ),
        section_context=SectionContext(
            section_name=sections[0], section_duration_s=30.0,
            tracks_active_count=4, conflicts_in_section=1,
            coherence_score=None,
        ),
        diagnosis_text="",
        primary_correction=CorrectionRecipe(
            target_track=target_track,
            device="EQ8",
            approach="static_dip",
            parameters={
                "frequency_hz": float(frequency_hz),
                "gain_db": float(gain_db),
                "q": float(q),
                "active_in_sections": list(sections),
            },
            applies_to_sections=list(sections),
            rationale="test",
            confidence="medium",
        ),
        fallback_correction=None,
    )


def _find_cde_eq8(track, prefix: str = "CDE Correction"):
    for eq8 in track.findall(".//Eq8"):
        un = eq8.find("UserName")
        if un is not None and un.get("Value", "").startswith(prefix):
            return eq8
    return None


def _band_envelopes_for(track, eq8, band_index: int) -> dict:
    """Return ``{param_name: [FloatEvent, ...]}`` for every envelope
    targeting an AutomationTarget of the given band. Absent params
    are simply missing keys."""
    band = eq8.find(f"Bands.{band_index}/ParameterA")
    if band is None:
        return {}
    target_ids = {}
    for name in ("Freq", "Gain", "Q", "IsOn"):
        at = band.find(f"{name}/AutomationTarget")
        if at is not None:
            target_ids[at.get("Id")] = name

    envelopes = {}
    for env in track.iter("AutomationEnvelope"):
        pid = env.find("EnvelopeTarget/PointeeId")
        if pid is None:
            continue
        name = target_ids.get(pid.get("Value"))
        if name is None:
            continue
        events = list(env.find("Automation/Events") or [])
        envelopes[name] = events
    return envelopes


def _envelope_float_values(events) -> list:
    """Extract float ``Value`` attributes, skipping the pre-song
    default event (``Time=-63072000``)."""
    values = []
    for e in events:
        try:
            t = float(e.get("Time", "0"))
            v = float(e.get("Value", "0"))
        except (TypeError, ValueError):
            continue
        if t < -1e9:  # pre-song default
            continue
        values.append(v)
    return values


# ---------------------------------------------------------------------------
# Test 5 — peak-follow writes 3 envelopes (Freq + Gain + Q)
# ---------------------------------------------------------------------------

def test_peak_follow_writes_3_envelopes_freq_gain_q(project_copy: Path):
    """A cluster in peak-follow mode must produce three envelopes on
    its band — Freq, Gain AND Q. The section-locked mode only writes
    Gain."""
    target = "[H/R] Kick 1"
    diag = _diag(target, 165.0, ["Drop 1"], diag_id="T5")
    # Trajectory straddling the cluster's 165 Hz centroid during Drop 1.
    # Drop 1 spans beats 168-199 at 128 BPM → times ~78.75-93.28s, so
    # frames 158-186 (at 0.5 s each) fall in the window.
    traj = PeakTrajectory(points=[
        (160, 164.0, -5.0),
        (170, 166.0, -4.0),
        (180, 165.0, -6.0),
    ])
    peaks = {target: [traj]}

    report = write_dynamic_eq8_from_cde_diagnostics(
        project_copy, [diag],
        peak_follow=True,
        peak_trajectories_by_track=peaks,
        _skip_confirmation=True,
    )
    assert report.applied == ["T5"]
    assert report.envelopes_written == 3

    tree = parse_als(str(project_copy))
    track = find_track_by_name(tree, target)
    eq8 = _find_cde_eq8(track)
    assert eq8 is not None

    envelopes = _band_envelopes_for(track, eq8, band_index=1)
    assert set(envelopes.keys()) == {"Freq", "Gain", "Q"}, (
        f"expected all three envelopes, got {sorted(envelopes.keys())}"
    )
    # Every envelope carries a non-trivial FloatEvents series.
    for name in ("Freq", "Gain", "Q"):
        assert len(envelopes[name]) > 2, (
            f"{name} envelope has only {len(envelopes[name])} events"
        )


# ---------------------------------------------------------------------------
# Test 6 — Freq curve is forward-filled between peaks
# ---------------------------------------------------------------------------

def test_peak_follow_freq_curve_is_forward_filled(project_copy: Path):
    """Forward-fill invariant: once a peak fires at frame N with
    freq F, the Freq envelope should keep reporting F (or the next
    peak's freq) at every subsequent frame INSIDE the active
    window — never jump back to the cluster centroid.

    The test uses peaks at two distinct frequencies (150 Hz at frame
    160, 175 Hz at frame 180). Between frames 160 and 180 the
    envelope should show 150 Hz, after frame 180 it should show
    175 Hz. Neither should equal the fallback centroid (165 Hz)
    once the first peak has fired.
    """
    target = "[H/R] Kick 1"
    cluster_centroid = 165.0
    diag = _diag(target, cluster_centroid, ["Drop 1"], diag_id="T6")
    # Two peaks inside Drop 1, at two DIFFERENT frequencies, so the
    # forward-fill is detectable by value (not just existence).
    traj = PeakTrajectory(points=[
        (160, 150.0, -5.0),  # first peak
        (180, 175.0, -5.0),  # second peak, clearly different freq
    ])
    peaks = {target: [traj]}

    write_dynamic_eq8_from_cde_diagnostics(
        project_copy, [diag],
        peak_follow=True,
        peak_trajectories_by_track=peaks,
        _skip_confirmation=True,
    )

    tree = parse_als(str(project_copy))
    track = find_track_by_name(tree, target)
    eq8 = _find_cde_eq8(track)
    envelopes = _band_envelopes_for(track, eq8, band_index=1)
    freq_values = _envelope_float_values(envelopes["Freq"])
    assert freq_values, "Freq envelope should not be empty"

    # If forward-fill works, the envelope contains at least one value
    # matching each peak's freq (or very close — dense sampling may
    # have interpolated between two of our 0.5s frames).
    has_first_peak_region = any(
        abs(v - 150.0) < 1.0 for v in freq_values
    )
    has_second_peak_region = any(
        abs(v - 175.0) < 1.0 for v in freq_values
    )
    assert has_first_peak_region, (
        f"forward-fill lost the first peak (150 Hz); values: {freq_values[:20]}"
    )
    assert has_second_peak_region, (
        f"forward-fill lost the second peak (175 Hz); values: {freq_values[:20]}"
    )

    # Between the two peaks, the envelope must NOT return to the
    # fallback centroid (165 Hz) — that would break the forward-fill
    # contract. We therefore require no event equal to 165 Hz
    # (±0.5 Hz) among the values that fall AFTER the first peak kicked
    # in. Since the envelope is thinned and ordered by time, we can
    # simply assert no 165 Hz values appear once 150 Hz has been seen
    # at least once.
    seen_first_peak = False
    for v in freq_values:
        if abs(v - 150.0) < 1.0:
            seen_first_peak = True
            continue
        if seen_first_peak and abs(v - cluster_centroid) < 0.5:
            pytest.fail(
                f"Freq curve jumped back to fallback {cluster_centroid} Hz "
                f"after first peak — forward-fill broken. Values: "
                f"{freq_values[:30]}"
            )


# ---------------------------------------------------------------------------
# Test 7 — peak-follow fallback per-cluster (coexistence of modes)
# ---------------------------------------------------------------------------

def test_peak_follow_fallback_when_no_trajectories_matches(
    project_copy: Path,
):
    """Two clusters on the same track; only one has a matching
    trajectory. The matched cluster goes peak-follow (3 envelopes),
    the other falls back to section-locked (1 envelope Gain). The
    report carries exactly one "fell back to section-locked"
    warning, mentioning the unmatched cluster's track."""
    target = "[H/R] Kick 1"
    # Cluster A at 150 Hz — will have a matching trajectory.
    # Cluster B at 2500 Hz — far from any supplied trajectory.
    diag_a = _diag(target, 150.0, ["Drop 1"], diag_id="T7_A")
    diag_b = _diag(target, 2500.0, ["Drop 1"], diag_id="T7_B")
    traj_a = PeakTrajectory(points=[
        (160, 150.0, -5.0), (170, 151.0, -4.0), (180, 149.0, -6.0),
    ])
    peaks = {target: [traj_a]}  # only Cluster A's trajectory

    report = write_dynamic_eq8_from_cde_diagnostics(
        project_copy, [diag_a, diag_b],
        peak_follow=True,
        peak_trajectories_by_track=peaks,
        _skip_confirmation=True,
    )
    assert set(report.applied) == {"T7_A", "T7_B"}
    # Cluster A = 3 envelopes, Cluster B = 1 envelope → total 4.
    assert report.envelopes_written == 4

    # Exactly one fallback warning, mentioning the track.
    fallback_warnings = [
        w for w in report.warnings if "section-locked" in w
    ]
    assert len(fallback_warnings) == 1
    assert target in fallback_warnings[0]

    # XML-level verification — band 1 (Cluster A, sorted by centroid)
    # has the full 3-envelope set; band 2 (Cluster B) has only Gain.
    tree = parse_als(str(project_copy))
    track = find_track_by_name(tree, target)
    eq8 = _find_cde_eq8(track)

    # Clusters are sorted by centroid ascending inside the writer —
    # so band 1 = 150 Hz (Cluster A), band 2 = 2500 Hz (Cluster B).
    band1_envs = _band_envelopes_for(track, eq8, band_index=1)
    band2_envs = _band_envelopes_for(track, eq8, band_index=2)

    assert set(band1_envs.keys()) == {"Freq", "Gain", "Q"}
    assert set(band2_envs.keys()) == {"Gain"}


# ---------------------------------------------------------------------------
# Test 8 — peak_follow=False stays byte-compatible with F1b
# ---------------------------------------------------------------------------

def test_peak_follow_false_unchanged_from_f1b(project_copy: Path):
    """Compat guard: with ``peak_follow=False`` (the F1b path), the
    writer must emit exactly ONE envelope per cluster — the Gain
    envelope. No Freq, no Q envelope should land on the band.

    This protects against a future F1c refactor that would accidentally
    start writing Freq/Q envelopes even in section-locked mode.
    """
    target = "[H/R] Kick 1"
    diag1 = _diag(target, 62,   ["Drop 1"], diag_id="T8_A")
    diag2 = _diag(target, 250,  ["Drop 1"], diag_id="T8_B")
    diag3 = _diag(target, 1000, ["Drop 1"], diag_id="T8_C")
    report = write_dynamic_eq8_from_cde_diagnostics(
        project_copy, [diag1, diag2, diag3],
        peak_follow=False,
        _skip_confirmation=True,
    )
    assert sorted(report.applied) == ["T8_A", "T8_B", "T8_C"]
    # 3 clusters × 1 envelope each = 3.
    assert report.envelopes_written == 3

    tree = parse_als(str(project_copy))
    track = find_track_by_name(tree, target)
    eq8 = _find_cde_eq8(track)
    for bi in (1, 2, 3):
        envs = _band_envelopes_for(track, eq8, band_index=bi)
        assert set(envs.keys()) == {"Gain"}, (
            f"Band {bi}: expected Gain-only envelopes, got "
            f"{sorted(envs.keys())}"
        )
