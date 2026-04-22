#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Feature 1 phase F1e1 — CLI wrapper minimal.

Covers:

    * ``cde_engine.load_diagnostics_from_json`` round-trip — the read
      half of the JSON contract shipped alongside the existing
      ``dump_diagnostics_to_json``.
    * ``scripts/apply_cde_corrections.py`` smoke-tested end-to-end
      (dry-run + apply) by invoking its ``main(argv)`` function
      in-process with synthetic inputs.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# The CLI script lives under scripts/ — add it to sys.path so we can
# import the module-level main() directly.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from als_utils import find_track_by_name, parse_als  # noqa: E402
from cde_engine import (  # noqa: E402
    CDE_VERSION,
    CorrectionDiagnostic,
    CorrectionRecipe,
    ProblemMeasurement,
    SectionContext,
    TFPContext,
    dump_diagnostics_to_json,
    load_diagnostics_from_json,
)
from tfp_parser import Function, Importance  # noqa: E402

from apply_cde_corrections import main as cli_main  # noqa: E402


FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "reference_project.als"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project_copy(tmp_path: Path) -> Path:
    """Fresh copy of the reference ``.als`` in ``tmp_path``."""
    dst = tmp_path / "project.als"
    shutil.copy2(FIXTURE_PATH, dst)
    return dst


def _make_diag(
    diag_id: str,
    target_track: str,
    frequency_hz: float,
    severity: str = "critical",
    gain_db: float = -4.0,
) -> CorrectionDiagnostic:
    return CorrectionDiagnostic(
        diagnostic_id=diag_id,
        timestamp=datetime(2026, 4, 22, 0, 0, 0),
        cde_version=CDE_VERSION,
        track_a=target_track,
        track_b=None,
        section="Drop 1",
        issue_type="masking_conflict",
        severity=severity,
        measurement=ProblemMeasurement(
            frequency_hz=frequency_hz, peak_db=-5.0,
            duration_in_section_s=30.0,
            duration_ratio_in_section=1.0,
            is_audible_fraction=1.0,
            severity_score=0.8, masking_score=0.8,
        ),
        tfp_context=TFPContext(
            track_a_role=(Importance.H, Function.R),
            track_b_role=(Importance.S, Function.H),
            role_compatibility="dominant_support",
        ),
        section_context=SectionContext(
            section_name="Drop 1", section_duration_s=30.0,
            tracks_active_count=4, conflicts_in_section=1,
            coherence_score=None,
        ),
        diagnosis_text="test",
        primary_correction=CorrectionRecipe(
            target_track=target_track, device="EQ8",
            approach="static_dip",
            parameters={
                "frequency_hz": frequency_hz,
                "gain_db": gain_db,
                "q": 4.0,
                "active_in_sections": ["Drop 1"],
            },
            applies_to_sections=["Drop 1"],
            rationale="", confidence="medium",
        ),
        fallback_correction=None,
    )


def _prepared_json(tmp_path: Path, diagnostics):
    """Write the given diagnostics to ``tmp_path/diagnostics.json``
    and return the path."""
    p = tmp_path / "diagnostics.json"
    dump_diagnostics_to_json(diagnostics, p)
    return p


def _als_has_cde_eq8(als_path: Path, track_name: str) -> bool:
    tree = parse_als(str(als_path))
    track = find_track_by_name(tree, track_name)
    for eq8 in track.findall(".//Eq8"):
        un = eq8.find("UserName")
        if un is not None and un.get("Value", "").startswith("CDE Correction"):
            return True
    return False


# ---------------------------------------------------------------------------
# Test 1 — load_diagnostics_from_json round-trip
# ---------------------------------------------------------------------------

def test_load_diagnostics_from_json_round_trip(tmp_path: Path):
    """``dump`` then ``load`` must preserve every field we rely on
    downstream: timestamp, role enums, recipe parameters + approach,
    application_status, applied_backup_path."""
    src = _make_diag(
        "RT_1", "[H/R] Kick 1", 62.0,
        severity="critical", gain_db=-3.0,
    )
    src.application_status = "applied"
    src.applied_backup_path = "/tmp/foo.als.v24.bak"

    json_path = tmp_path / "rt.json"
    dump_diagnostics_to_json([src], json_path)

    loaded = load_diagnostics_from_json(json_path)
    assert len(loaded) == 1
    d = loaded[0]

    assert d.diagnostic_id == "RT_1"
    assert d.timestamp == src.timestamp
    assert d.tfp_context.track_a_role == (Importance.H, Function.R)
    assert d.tfp_context.track_b_role == (Importance.S, Function.H)
    assert d.primary_correction is not None
    assert d.primary_correction.approach == "static_dip"
    assert d.primary_correction.parameters["frequency_hz"] == 62.0
    assert d.primary_correction.parameters["gain_db"] == -3.0
    assert d.application_status == "applied"
    assert d.applied_backup_path == "/tmp/foo.als.v24.bak"


# ---------------------------------------------------------------------------
# Test 2 — CLI dry-run shows preview, does not write the .als
# ---------------------------------------------------------------------------

def test_cli_dry_run_shows_preview_and_does_not_write(
    project_copy: Path, tmp_path: Path, capsys,
):
    """``--dry-run --yes`` must print a preview, return exit code 0,
    and leave the ``.als`` + JSON untouched."""
    diag = _make_diag("CLI_DRY", "[H/R] Kick 1", 62.0)
    json_path = _prepared_json(tmp_path, [diag])
    als_before_mtime = project_copy.stat().st_mtime_ns
    json_before_mtime = json_path.stat().st_mtime_ns

    rc = cli_main([
        "--als", str(project_copy),
        "--diagnostics-json", str(json_path),
        "--dry-run", "--yes",
    ])
    assert rc == 0

    # Preview header is in the captured stdout.
    captured = capsys.readouterr().out
    assert "DRY-RUN REPORT" in captured
    assert "Loaded 1 diagnostics" in captured

    # File mtimes unchanged — nothing was written.
    assert project_copy.stat().st_mtime_ns == als_before_mtime
    assert json_path.stat().st_mtime_ns == json_before_mtime
    # And of course no CDE EQ8 was inserted.
    assert _als_has_cde_eq8(project_copy, "[H/R] Kick 1") is False
    # JSON's diagnostic is still "proposed".
    reread = load_diagnostics_from_json(json_path)
    assert reread[0].application_status == "proposed"


# ---------------------------------------------------------------------------
# Test 3 — CLI apply writes the .als and updates the JSON
# ---------------------------------------------------------------------------

def test_cli_apply_writes_als_and_updates_json(
    project_copy: Path, tmp_path: Path,
):
    """``--yes`` (no dry-run) performs the real write AND re-dumps the
    diagnostics JSON with the applied diagnostic's status flipped."""
    target = "[H/R] Kick 1"
    diag = _make_diag("CLI_APPLY", target, 62.0)
    json_path = _prepared_json(tmp_path, [diag])

    rc = cli_main([
        "--als", str(project_copy),
        "--diagnostics-json", str(json_path),
        "--yes",
    ])
    assert rc == 0

    # .als now carries the CDE Correction EQ8 on the target track.
    assert _als_has_cde_eq8(project_copy, target) is True

    # JSON was re-dumped with the updated status.
    reread = load_diagnostics_from_json(json_path)
    assert len(reread) == 1
    assert reread[0].diagnostic_id == "CLI_APPLY"
    assert reread[0].application_status == "applied"
    assert reread[0].applied_backup_path is not None
    assert Path(reread[0].applied_backup_path).exists()


# ---------------------------------------------------------------------------
# Test 4 — CLI filter: severity=critical drops moderate diagnostics
# ---------------------------------------------------------------------------

def test_cli_filter_severity_restricts_applied_set(
    project_copy: Path, tmp_path: Path,
):
    """``--filter severity=critical`` on a batch containing both
    ``critical`` and ``moderate`` entries must apply ONLY the critical
    one. The ``moderate`` diagnostic stays at ``"proposed"`` in the
    re-dumped JSON."""
    crit = _make_diag("CRIT_1", "[H/R] Kick 1", 62.0, severity="critical")
    mod = _make_diag("MOD_1", "[H/R] Kick 1", 250.0, severity="moderate")
    json_path = _prepared_json(tmp_path, [crit, mod])

    rc = cli_main([
        "--als", str(project_copy),
        "--diagnostics-json", str(json_path),
        "--filter", "severity=critical",
        "--yes",
    ])
    assert rc == 0

    reread = load_diagnostics_from_json(json_path)
    by_id = {d.diagnostic_id: d for d in reread}
    assert by_id["CRIT_1"].application_status == "applied"
    assert by_id["MOD_1"].application_status == "proposed"
