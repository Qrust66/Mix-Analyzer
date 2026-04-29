"""Tests for scripts/apply_mix_decisions.py — end-to-end test drive CLI.

Phase 4.13 — verifies the CLI orchestrator applies EQ + Dynamics + Spatial
decisions to a real .als and produces a valid output that all 3 writers'
safety guardians pass.

This is the test drive smoke test : the user runs this script on
reference_project.als with sample decision JSONs, gets a modified .als,
opens in Ableton to verify.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import als_utils


_REPO = Path(__file__).resolve().parent.parent
_REF_ALS = _REPO / "tests" / "fixtures" / "reference_project.als"
_SAMPLES = _REPO / "tests" / "fixtures" / "sample_decisions"
_CLI = _REPO / "scripts" / "apply_mix_decisions.py"


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    """Run the CLI as a subprocess. Returns CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(_CLI)] + args,
        capture_output=True, text=True, encoding="utf-8",
    )


def test_cli_help_works():
    """--help prints usage and exits 0."""
    result = _run_cli(["--help"])
    assert result.returncode == 0
    assert "apply_mix_decisions" in result.stdout.lower() or "usage" in result.stdout.lower()


def test_cli_missing_als_argument_exits_2():
    """No --als → argparse error, exit code 2."""
    result = _run_cli([])
    assert result.returncode == 2


def test_cli_no_decisions_exits_2(tmp_path):
    """At least one decision JSON required."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    result = _run_cli(["--als", str(ref_copy)])
    assert result.returncode == 2
    assert "at least one" in result.stderr.lower()


def test_cli_eq_only_smoke(tmp_path):
    """EQ-only test drive : applies sample EQ decision, output passes safety."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    eq_json = _SAMPLES / "eq_corrective_sample.json"
    result = _run_cli([
        "--als", str(ref_copy),
        "--eq-json", str(eq_json),
        "--output", str(output),
    ])
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert output.exists()
    assert "EQ corrective" in result.stdout
    assert "RESULT : OK" in result.stdout


def test_cli_dynamics_only_smoke(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    dyn_json = _SAMPLES / "dynamics_corrective_sample.json"
    result = _run_cli([
        "--als", str(ref_copy),
        "--dynamics-json", str(dyn_json),
        "--output", str(output),
    ])
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert output.exists()
    assert "Dynamics corrective" in result.stdout


def test_cli_spatial_only_smoke(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    sp_json = _SAMPLES / "spatial_sample.json"
    result = _run_cli([
        "--als", str(ref_copy),
        "--spatial-json", str(sp_json),
        "--output", str(output),
    ])
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert output.exists()
    assert "Spatial" in result.stdout


def test_cli_full_pipeline_eq_dyn_spatial(tmp_path):
    """**THE test drive** : apply ALL three lanes in one CLI run.
    Output .als must have :
    - Bass Rythm Eq8 with bell band at 250 Hz (EQ corrective)
    - Bass Rythm GlueCompressor with new threshold (Dynamics)
    - Bass Rythm StereoGain with BassMono enabled at 120 Hz (Spatial)
    - Kick 1 Eq8 with HPF + Mixer.Pan = 0 (centered)
    """
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    result = _run_cli([
        "--als", str(ref_copy),
        "--eq-json", str(_SAMPLES / "eq_corrective_sample.json"),
        "--dynamics-json", str(_SAMPLES / "dynamics_corrective_sample.json"),
        "--spatial-json", str(_SAMPLES / "spatial_sample.json"),
        "--output", str(output),
    ])
    assert result.returncode == 0, (
        f"FULL PIPELINE FAILED\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert output.exists()

    # All 3 lanes ran
    assert "EQ corrective" in result.stdout
    assert "Dynamics corrective" in result.stdout
    assert "Spatial" in result.stdout
    assert "RESULT : OK" in result.stdout

    # Verify output .als is valid + has expected XML changes
    tree = als_utils.parse_als(str(output))

    # 1. Bass Rythm Eq8 : new bell band at 250 Hz Mode=3 active
    bass = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    bass_eq8 = bass.find(".//Eq8")
    assert bass_eq8 is not None
    found_bell_250 = False
    for i in range(8):
        try:
            band = als_utils.get_eq8_band(bass_eq8, i)
        except (ValueError, IndexError):
            continue
        mode = band.find("Mode/Manual")
        freq = band.find("Freq/Manual")
        is_on = band.find("IsOn/Manual")
        if (mode is not None and mode.get("Value") == "3"
                and freq is not None and abs(float(freq.get("Value")) - 250.0) < 0.5
                and is_on is not None and is_on.get("Value") == "true"):
            found_bell_250 = True
            break
    assert found_bell_250, "Expected bell at 250 Hz on Bass Rythm Eq8"

    # 2. Bass Rythm GlueCompressor : threshold = -12.0
    glue = bass.find(".//GlueCompressor")
    threshold = float(glue.find("Threshold/Manual").get("Value"))
    assert abs(threshold - (-12.0)) < 0.1, f"Expected -12 dB, got {threshold}"

    # 3. Bass Rythm StereoGain : BassMono enabled at 120 Hz
    sg = bass.find(".//StereoGain")
    bm = sg.find("BassMono/Manual")
    assert bm.get("Value") == "true"
    bmf = float(sg.find("BassMonoFrequency/Manual").get("Value"))
    assert abs(bmf - 120.0) < 0.5

    # 4. Bass Rythm Mixer.Pan = 0
    pan = float(bass.find(".//Mixer/Pan/Manual").get("Value"))
    assert abs(pan - 0.0) < 0.01

    # 5. Kick 1 Eq8 : HPF (Mode 1, 12 dB/oct) at 30 Hz
    kick = als_utils.find_track_by_name(tree, "[H/R] Kick 1")
    kick_eq8 = kick.find(".//Eq8")
    found_hpf = False
    for i in range(8):
        try:
            band = als_utils.get_eq8_band(kick_eq8, i)
        except (ValueError, IndexError):
            continue
        mode = band.find("Mode/Manual")
        freq = band.find("Freq/Manual")
        is_on = band.find("IsOn/Manual")
        if (mode is not None and mode.get("Value") == "1"  # 12dB HPF
                and freq is not None and abs(float(freq.get("Value")) - 30.0) < 0.5
                and is_on is not None and is_on.get("Value") == "true"):
            found_hpf = True
            break
    assert found_hpf, "Expected HPF 12dB/oct at 30 Hz on Kick 1 Eq8"


def test_cli_dry_run_does_not_write(tmp_path):
    """--dry-run leaves source .als untouched."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    initial_size = ref_copy.stat().st_size

    result = _run_cli([
        "--als", str(ref_copy),
        "--eq-json", str(_SAMPLES / "eq_corrective_sample.json"),
        "--dry-run",
    ])
    assert result.returncode == 0
    assert ref_copy.stat().st_size == initial_size  # unchanged


def test_cli_no_safety_flag_disables_guardian(tmp_path):
    """--no-safety produces SKIPPED status (not PASS)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    result = _run_cli([
        "--als", str(ref_copy),
        "--eq-json", str(_SAMPLES / "eq_corrective_sample.json"),
        "--output", str(output),
        "--no-safety",
    ])
    assert result.returncode == 0
    assert "safety: SKIPPED" in result.stdout
