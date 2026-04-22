#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Feature 1 phase F1d — status round-trip + revert utility.

Covers the two F1d1 behaviours:

    - ``write_dynamic_eq8_from_cde_diagnostics`` flips each applied
      diagnostic's ``application_status`` to ``"applied"`` and stamps
      ``applied_backup_path`` with the backup file it just created.
    - ``revert_cde_application(als_path, *, diagnostics=…,
      diagnostic_ids=…, backup_path=…)`` restores the ``.als`` from
      the backup, flips the applicable diagnostics to
      ``application_status="reverted"`` (with
      ``rejection_reason="reverted by user"`` and
      ``applied_backup_path=None``), and exposes the reverted ids on
      ``CdeApplicationReport.reverted``.

Each test copies ``tests/fixtures/reference_project.als`` into
``tmp_path`` so the reference file stays pristine.
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
    revert_cde_application,
    write_dynamic_eq8_from_cde_diagnostics,
)


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
    approach: str,
    target_track: str,
    frequency_hz: float,
    *,
    diag_id: str,
    gain_db: float = -4.0,
    q: float = 4.0,
    sections: List[str] = None,
) -> CorrectionDiagnostic:
    """Minimal CorrectionDiagnostic for F1d testing."""
    sections = list(sections or ["Drop 1"])
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
            section_name=sections[0],
            section_duration_s=30.0,
            tracks_active_count=4,
            conflicts_in_section=1,
            coherence_score=None,
        ),
        diagnosis_text="",
        primary_correction=CorrectionRecipe(
            target_track=target_track,
            device="EQ8",
            approach=approach,
            parameters={
                "frequency_hz": float(frequency_hz),
                "gain_db": float(gain_db),
                "q": float(q),
                "active_in_sections": sections,
            },
            applies_to_sections=sections,
            rationale="test",
            confidence="medium",
        ),
        fallback_correction=None,
    )


def _als_has_cde_eq8(als_path: Path, track_name: str) -> bool:
    """True when the track carries an EQ8 whose UserName starts with
    ``"CDE Correction"``."""
    tree = parse_als(str(als_path))
    track = find_track_by_name(tree, track_name)
    for eq8 in track.findall(".//Eq8"):
        un = eq8.find("UserName")
        if un is not None and un.get("Value", "").startswith("CDE Correction"):
            return True
    return False


# ---------------------------------------------------------------------------
# Test 1 — apply flips status + stamps backup path
# ---------------------------------------------------------------------------

def test_apply_flips_status_and_stamps_backup_path(project_copy: Path):
    """Every diagnostic that lands in ``report.applied`` must have its
    ``application_status`` flipped to ``"applied"`` AND its
    ``applied_backup_path`` stamped with the backup file. Diagnostics
    that were skipped (sidechain here) keep their initial
    ``"proposed"`` status so a future Feature 1.5 writer can still
    pick them up."""
    d_cut = _diag("static_dip", "[H/R] Kick 1", 62,
                  diag_id="APPLY_OK")
    d_sidechain = _diag("sidechain", "[S/H] Sub Bass", 62,
                         diag_id="APPLY_SKIPPED")

    # Both start as fresh diagnostics — default status = "proposed".
    assert d_cut.application_status == "proposed"
    assert d_cut.applied_backup_path is None
    assert d_sidechain.application_status == "proposed"

    report = write_dynamic_eq8_from_cde_diagnostics(
        project_copy, [d_cut, d_sidechain], _skip_confirmation=True,
    )

    # Applied diagnostic is flipped + stamped.
    assert report.applied == ["APPLY_OK"]
    assert d_cut.application_status == "applied"
    assert d_cut.applied_backup_path is not None
    # The stamped path matches the backup the writer actually created.
    assert d_cut.applied_backup_path == str(report.backup_path)
    assert Path(d_cut.applied_backup_path).exists()

    # Skipped diagnostic stays at the default proposed status.
    assert d_sidechain.application_status == "proposed"
    assert d_sidechain.applied_backup_path is None


# ---------------------------------------------------------------------------
# Test 2 — revert (full) restores file + flips every applied status
# ---------------------------------------------------------------------------

def test_revert_full_restores_als_and_flips_all_applied(project_copy: Path):
    """Full-rollback revert (``diagnostic_ids=None``) restores the
    ``.als`` from ``.als.v24.bak`` AND flips every diagnostic whose
    status is currently ``"applied"`` to ``"reverted"``."""
    target = "[H/R] Kick 1"
    diags = [
        _diag("static_dip", target, 62,  diag_id="R1"),
        _diag("static_dip", target, 250, diag_id="R2"),
    ]

    # Apply the batch.
    apply_report = write_dynamic_eq8_from_cde_diagnostics(
        project_copy, diags, _skip_confirmation=True,
    )
    assert sorted(apply_report.applied) == ["R1", "R2"]
    assert _als_has_cde_eq8(project_copy, target) is True
    for d in diags:
        assert d.application_status == "applied"

    # Revert — no diagnostic_ids filter = full rollback.
    revert_report = revert_cde_application(
        project_copy, diagnostics=diags,
    )
    assert sorted(revert_report.reverted) == ["R1", "R2"]

    # .als is restored — the CDE EQ8 is gone.
    assert _als_has_cde_eq8(project_copy, target) is False

    # Every diagnostic is now "reverted" with the expected side fields.
    for d in diags:
        assert d.application_status == "reverted"
        assert d.rejection_reason == "reverted by user"
        assert d.applied_backup_path is None

    # At least one warning message documents the restore.
    assert any("Restored" in w for w in revert_report.warnings)


# ---------------------------------------------------------------------------
# Test 3 — selective revert leaves untouched ids at "applied"
# ---------------------------------------------------------------------------

def test_revert_selective_only_flips_matching_ids(project_copy: Path):
    """When ``diagnostic_ids=["R1"]`` is passed, only that diagnostic
    is flipped — the rest keep their ``"applied"`` status. The
    ``.als`` is always restored (the backup is consumed at file
    level, not per-diagnostic)."""
    target = "[H/R] Kick 1"
    diags = [
        _diag("static_dip", target, 62,   diag_id="R1"),
        _diag("static_dip", target, 1000, diag_id="R2"),
    ]
    write_dynamic_eq8_from_cde_diagnostics(
        project_copy, diags, _skip_confirmation=True,
    )
    for d in diags:
        assert d.application_status == "applied"

    revert_report = revert_cde_application(
        project_copy, diagnostics=diags, diagnostic_ids=["R1"],
    )

    assert revert_report.reverted == ["R1"]

    # Per-diagnostic assertions — R1 was flipped, R2 was NOT.
    by_id = {d.diagnostic_id: d for d in diags}
    assert by_id["R1"].application_status == "reverted"
    assert by_id["R1"].rejection_reason == "reverted by user"
    assert by_id["R1"].applied_backup_path is None

    assert by_id["R2"].application_status == "applied"
    assert by_id["R2"].rejection_reason is None
    assert by_id["R2"].applied_backup_path is not None


# ---------------------------------------------------------------------------
# Test 4 — missing backup returns a warning (not an exception)
# ---------------------------------------------------------------------------

def test_revert_missing_backup_returns_warning_not_crash(tmp_path: Path):
    """Calling ``revert_cde_application`` on an ``.als`` whose backup
    does not exist must NOT raise. The returned report exposes a
    warning so the CLI can surface the problem to the user, and
    ``reverted`` stays empty because no work happened."""
    bogus_als = tmp_path / "never_applied.als"
    bogus_als.write_bytes(b"not-a-real-als")
    # Deliberately no .als.v24.bak file alongside.

    diag = _diag("static_dip", "[H/R] Kick 1", 62, diag_id="R_ABSENT")
    diag.application_status = "applied"
    diag.applied_backup_path = str(bogus_als) + ".v24.bak"

    report = revert_cde_application(bogus_als, diagnostics=[diag])

    # No exception — the function returned gracefully.
    # Warning mentions the missing backup explicitly.
    assert any("Backup not found" in w for w in report.warnings)
    # Nothing was flipped; no backup was consumed.
    assert report.reverted == []
    assert report.backup_path is None
    # Caller's diagnostic is untouched (still "applied").
    assert diag.application_status == "applied"
