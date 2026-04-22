#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke tests for Feature 1 phase F1c1c — peak-following mode wiring.

These two tests check that ``write_dynamic_eq8_from_cde_diagnostics``
runs the peak-following branch end-to-end on the real
``tests/fixtures/reference_project.als`` without crashing, and that
the fallback-to-section-locked path activates cleanly when no peak
trajectory is supplied.

Exhaustive per-helper tests (gain scaling formulas, forward-fill
semantics, threshold edge cases, Q envelope contents, coexistence of
modes in one batch, etc.) ship in F1c2. Here we only assert that the
branches are reachable and the report reflects the expected mode.
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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


@pytest.fixture
def project_copy(tmp_path: Path) -> Path:
    """Fresh copy of the reference fixture in ``tmp_path`` so each
    test mutates its own workspace without touching the reference."""
    dst = tmp_path / "project.als"
    shutil.copy2(FIXTURE_PATH, dst)
    return dst


def _diag(
    target_track: str,
    frequency_hz: float,
    sections: list,
    *,
    diag_id: str = "SMOKE",
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
            rationale="smoke",
            confidence="medium",
        ),
        fallback_correction=None,
    )


# ---------------------------------------------------------------------------
# Smoke test A — peak_follow=True with a matching trajectory
# ---------------------------------------------------------------------------

def test_peak_follow_true_with_trajectories_runs_without_crash(
    project_copy: Path,
):
    """End-to-end peak-follow run on the fixture. A synthetic trajectory
    that straddles the 165 Hz cluster is supplied; expected outcome is
    three envelopes written (Freq + Gain + Q) and no fallback warning.
    """
    target = "[H/R] Kick 1"
    diag = _diag(target, 165.0, ["Drop 1"], diag_id="PF_A")
    # Trajectory matches the cluster's centroid within the default
    # 2-semitone tolerance (~147-185 Hz window). The frame indices
    # were chosen so at least one falls inside the Drop 1 range
    # (168-199 beats ≈ frames 157-186 at 0.5 s per frame / 128 BPM).
    traj = PeakTrajectory(points=[
        (160, 165.0, -5.0),
        (165, 163.0, -4.0),
        (170, 167.0, -6.0),
        (175, 165.0, -3.0),
        (180, 162.0, -7.0),
    ])
    peaks = {target: [traj]}

    report = write_dynamic_eq8_from_cde_diagnostics(
        project_copy, [diag],
        peak_follow=True,
        peak_trajectories_by_track=peaks,
        _skip_confirmation=True,
    )

    assert report.applied == ["PF_A"]
    # Peak-follow writes three envelopes per cluster.
    assert report.envelopes_written == 3
    # No "fell back to section-locked" warning — the trajectory matched.
    assert not any(
        "section-locked" in w for w in report.warnings
    ), f"unexpected fallback warning: {report.warnings!r}"


# ---------------------------------------------------------------------------
# Smoke test B — peak_follow=True with NO trajectories → graceful fallback
# ---------------------------------------------------------------------------

def test_peak_follow_true_without_trajectories_falls_back_gracefully(
    project_copy: Path,
):
    """When peak_follow is requested but no trajectory dict is passed,
    each cluster falls back to section-locked mode and the report
    records an explicit warning. The diagnostic still lands in
    ``applied`` — the fallback path is a success path."""
    target = "[H/R] Bass Rythm"
    diag = _diag(target, 165.0, ["Drop 2"], diag_id="PF_B")

    report = write_dynamic_eq8_from_cde_diagnostics(
        project_copy, [diag],
        peak_follow=True,
        peak_trajectories_by_track=None,  # deliberately absent
        _skip_confirmation=True,
    )

    assert report.applied == ["PF_B"]
    # Fallback mode writes one envelope per cluster (Gain only).
    assert report.envelopes_written == 1
    # The fallback warning must mention section-locked explicitly.
    fallback_warnings = [
        w for w in report.warnings if "section-locked" in w
    ]
    assert len(fallback_warnings) >= 1, (
        f"expected a 'fell back to section-locked' warning, got "
        f"{report.warnings!r}"
    )
    # And the warning mentions the track name so the user knows which
    # cluster degraded.
    assert any(target in w for w in fallback_warnings)
