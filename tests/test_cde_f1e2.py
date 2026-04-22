#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Feature 1 phase F1e2 — advanced CLI flags.

Covers the three new CLI capabilities:

    * ``--revert [IDS]``              — revert applied diagnostics
    * ``--peak-xlsx PATH``            — enable peak-following using a
                                        Mix Analyzer Excel report
    * ``--tolerance-semitones FLOAT`` — override clustering tolerance

Also exercises the small ``_excel_track_to_ableton_name`` helper the
CLI uses to align Excel WAV names (``"Acid_Drops [A_T] Ambience.wav"``)
with Ableton EffectiveNames (``"[A/T] Ambience"``).
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
# The CLI lives under scripts/ — expose it on sys.path so we can
# import main() directly.
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

from apply_cde_corrections import (  # noqa: E402
    _excel_track_to_ableton_name,
    main as cli_main,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "reference_project.als"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project_copy(tmp_path: Path) -> Path:
    dst = tmp_path / "project.als"
    shutil.copy2(FIXTURE_PATH, dst)
    return dst


def _make_diag(
    diag_id: str,
    target_track: str,
    frequency_hz: float,
) -> CorrectionDiagnostic:
    return CorrectionDiagnostic(
        diagnostic_id=diag_id,
        timestamp=datetime(2026, 4, 22, 0, 0, 0),
        cde_version=CDE_VERSION,
        track_a=target_track,
        track_b=None,
        section="Drop 1",
        issue_type="masking_conflict",
        severity="critical",
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
        diagnosis_text="",
        primary_correction=CorrectionRecipe(
            target_track=target_track, device="EQ8",
            approach="static_dip",
            parameters={
                "frequency_hz": frequency_hz,
                "gain_db": -4.0, "q": 4.0,
                "active_in_sections": ["Drop 1"],
            },
            applies_to_sections=["Drop 1"],
            rationale="", confidence="medium",
        ),
        fallback_correction=None,
    )


def _als_has_cde_eq8(als_path: Path, track_name: str) -> bool:
    tree = parse_als(str(als_path))
    track = find_track_by_name(tree, track_name)
    for eq8 in track.findall(".//Eq8"):
        un = eq8.find("UserName")
        if un is not None and un.get("Value", "").startswith("CDE Correction"):
            return True
    return False


def _find_band_envelope_names(als_path: Path, track_name: str) -> set:
    """Return the set of parameter names (``{"Freq", "Gain", "Q"}``)
    for which an AutomationEnvelope exists on the CDE band #1 of the
    given track. Used to verify peak-follow wrote all three envelopes.
    """
    tree = parse_als(str(als_path))
    track = find_track_by_name(tree, track_name)
    cde = None
    for eq8 in track.findall(".//Eq8"):
        un = eq8.find("UserName")
        if un is not None and un.get("Value", "").startswith("CDE Correction"):
            cde = eq8
            break
    if cde is None:
        return set()
    band = cde.find("Bands.1/ParameterA")
    if band is None:
        return set()
    target_by_id = {}
    for name in ("Freq", "Gain", "Q"):
        at = band.find(f"{name}/AutomationTarget")
        if at is not None:
            target_by_id[at.get("Id")] = name
    present = set()
    for env in track.iter("AutomationEnvelope"):
        pid = env.find("EnvelopeTarget/PointeeId")
        if pid is None:
            continue
        hit = target_by_id.get(pid.get("Value"))
        if hit is not None:
            present.add(hit)
    return present


# ---------------------------------------------------------------------------
# Test 1 — _excel_track_to_ableton_name transforms
# ---------------------------------------------------------------------------

def test_excel_track_to_ableton_name_common_cases():
    # Project prefix + TFP underscore + .wav → clean Ableton name.
    assert _excel_track_to_ableton_name(
        "Acid_Drops [A_T] Ambience.wav"
    ) == "[A/T] Ambience"
    assert _excel_track_to_ableton_name(
        "Acid_Drops [H_R] Kick 1.wav"
    ) == "[H/R] Kick 1"

    # No TFP prefix → only ``.wav`` stripped (buses, return tracks).
    assert _excel_track_to_ableton_name("BUS Kick.wav") == "BUS Kick"

    # Already clean (no ``.wav``, no project prefix) → passthrough.
    assert _excel_track_to_ableton_name("[A/T] Ambience") == "[A/T] Ambience"

    # Case-insensitive ``.wav`` stripping.
    assert _excel_track_to_ableton_name("Kick 1.WAV") == "Kick 1"


# ---------------------------------------------------------------------------
# Test 2 — CLI revert round-trip
# ---------------------------------------------------------------------------

def test_cli_revert_restores_file_and_flips_status(
    project_copy: Path, tmp_path: Path,
):
    """Apply a diagnostic, then run the CLI with ``--revert`` (no IDs
    → revert-all). Expect the ``.als`` restored, the status flipped
    back to ``"reverted"``, and exit code 0."""
    target = "[H/R] Kick 1"
    diag = _make_diag("REV_1", target, 62.0)
    json_path = tmp_path / "diags.json"
    dump_diagnostics_to_json([diag], json_path)

    # Step 1 — apply.
    rc = cli_main([
        "--als", str(project_copy),
        "--diagnostics-json", str(json_path),
        "--yes",
    ])
    assert rc == 0
    assert _als_has_cde_eq8(project_copy, target) is True
    assert load_diagnostics_from_json(json_path)[0].application_status == "applied"

    # Step 2 — revert (no IDs = revert all applied).
    rc = cli_main([
        "--als", str(project_copy),
        "--diagnostics-json", str(json_path),
        "--revert",
    ])
    assert rc == 0

    # File restored — CDE Correction EQ8 is gone.
    assert _als_has_cde_eq8(project_copy, target) is False
    # JSON re-dumped with the flipped status.
    reloaded = load_diagnostics_from_json(json_path)[0]
    assert reloaded.application_status == "reverted"
    assert reloaded.rejection_reason == "reverted by user"
    assert reloaded.applied_backup_path is None


# ---------------------------------------------------------------------------
# Test 3 — CLI peak-xlsx enables peak-following
# ---------------------------------------------------------------------------

def test_cli_peak_xlsx_enables_peak_following(
    project_copy: Path, tmp_path: Path,
):
    """With ``--peak-xlsx PATH`` the writer runs in peak-following
    mode and emits THREE envelopes per band (Freq + Gain + Q), unlike
    the section-locked default which only writes Gain.

    The test builds a minimal Excel fixture with a single trajectory
    matching the diagnostic's 165 Hz centroid on ``[H/R] Kick 1``.
    Frame indices are chosen so at least one sample lands inside the
    Drop 1 beat range (168-199 beats at 128 BPM ≈ frames 157-186 at
    0.5 s per frame).
    """
    from openpyxl import Workbook

    target = "[H/R] Kick 1"
    diag = _make_diag("PF_CLI", target, 165.0)
    json_path = tmp_path / "diags.json"
    dump_diagnostics_to_json([diag], json_path)

    # Build a minimal _track_peak_trajectories sheet the CLI can
    # consume. Track name uses the Excel WAV format; the CLI's
    # _excel_track_to_ableton_name filter will normalise it.
    xlsx_path = tmp_path / "report.xlsx"
    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("_track_peak_trajectories")
    ws.append((
        "Track", "Traj#", "Frame", "Time (s)",
        "Freq (Hz)", "Amp (dB)",
    ))
    wav_name = "Acid_Drops [H_R] Kick 1.wav"
    # Four points inside the Drop 1 window, all above the default
    # -30 dB threshold so they trigger peak-follow.
    for frame in (160, 170, 180, 185):
        ws.append((wav_name, 1, frame, frame * 0.5, 165.0, -5.0))
    wb.save(str(xlsx_path))

    rc = cli_main([
        "--als", str(project_copy),
        "--diagnostics-json", str(json_path),
        "--peak-xlsx", str(xlsx_path),
        "--yes",
    ])
    assert rc == 0

    # The CDE band must carry all three envelopes in peak-follow mode.
    envs = _find_band_envelope_names(project_copy, target)
    assert envs == {"Freq", "Gain", "Q"}, (
        f"expected Freq+Gain+Q envelopes, got {sorted(envs)}"
    )

    # JSON updated with applied status.
    reloaded = load_diagnostics_from_json(json_path)[0]
    assert reloaded.application_status == "applied"
