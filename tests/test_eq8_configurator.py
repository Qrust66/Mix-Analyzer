"""Tests for mix_engine.writers.eq8_configurator (Phase 4.10).

Tier B writer = deterministic Python module. Tests verify :
- Translation table : band_type + slope → Eq8 Mode 0-7
- apply_eq_corrective_decision basic flow (Step 1)
- Typed exceptions (EqConfiguratorError, ChainPositionUnresolvedError)
- Report dataclass content

Phase 4.10 Step 1 scope. Steps 2-5 land additional tests as features
materialize (chain_position, envelopes, M/S, safety-guardian).
"""
from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import als_utils
from mix_engine.blueprint import (
    EQBandCorrection,
    EQCorrectiveDecision,
    MixCitation,
    MixDecision,
)
from mix_engine.writers import (
    EqConfiguratorError,
    EqConfiguratorReport,
    apply_eq_corrective_decision,
)
from mix_engine.writers.eq8_configurator import _resolve_eq8_mode


# Shared fixture path. reference_project.als has 34 AudioTracks ; the
# first is "[H/R] Kick 1" which already has an Eq8.
_REF_ALS = Path(__file__).parent / "fixtures" / "reference_project.als"


# ============================================================================
# Translation table tests
# ============================================================================


def _make_band(
    track: str = "[H/R] Kick 1",
    band_type: str = "bell",
    intent: str = "cut",
    center_hz: float = 247.0,
    q: float = 4.5,
    gain_db: float = -3.5,
    slope: float | None = None,
) -> EQBandCorrection:
    return EQBandCorrection(
        track=track,
        band_type=band_type,
        intent=intent,
        center_hz=center_hz,
        q=q,
        gain_db=gain_db,
        slope_db_per_oct=slope,
        chain_position="default",
        processing_mode="stereo",
        rationale="Causal: 247 Hz resonance. Interactional: masking conflict. Idiomatic: standard cleanup.",
        inspired_by=(MixCitation(kind="diagnostic", path="Anomalies!A3", excerpt="247 Hz"),),
    )


def test_translation_bell_to_mode_3():
    band = _make_band(band_type="bell")
    assert _resolve_eq8_mode(band) == 3


def test_translation_notch_to_mode_4():
    band = _make_band(band_type="notch", q=12.0, gain_db=-12.0)
    assert _resolve_eq8_mode(band) == 4


def test_translation_low_shelf_to_mode_2():
    band = _make_band(band_type="low_shelf")
    assert _resolve_eq8_mode(band) == 2


def test_translation_high_shelf_to_mode_5():
    band = _make_band(band_type="high_shelf")
    assert _resolve_eq8_mode(band) == 5


def test_translation_highpass_48_to_mode_0():
    band = _make_band(band_type="highpass", intent="filter",
                       gain_db=0.0, q=0.71, slope=48.0)
    assert _resolve_eq8_mode(band) == 0


def test_translation_highpass_12_to_mode_1():
    band = _make_band(band_type="highpass", intent="filter",
                       gain_db=0.0, q=0.71, slope=12.0)
    assert _resolve_eq8_mode(band) == 1


def test_translation_lowpass_12_to_mode_6():
    band = _make_band(band_type="lowpass", intent="filter",
                       gain_db=0.0, q=0.71, slope=12.0)
    assert _resolve_eq8_mode(band) == 6


def test_translation_lowpass_48_to_mode_7():
    band = _make_band(band_type="lowpass", intent="filter",
                       gain_db=0.0, q=0.71, slope=48.0)
    assert _resolve_eq8_mode(band) == 7


def test_translation_bell_with_slope_rejected():
    """Bell + slope is forbidden (parser should catch but writer double-checks)."""
    # Bypass parser by constructing directly — tests writer's defensive check
    band = EQBandCorrection(
        track="t", band_type="bell", intent="cut",
        center_hz=1000.0, q=2.0, gain_db=-3.0,
        slope_db_per_oct=12.0,  # Invalid for bell
        chain_position="default", processing_mode="stereo",
        rationale="x" * 50, inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    with pytest.raises(EqConfiguratorError, match="must NOT have slope"):
        _resolve_eq8_mode(band)


def test_translation_highpass_invalid_slope_rejected():
    band = EQBandCorrection(
        track="t", band_type="highpass", intent="filter",
        center_hz=80.0, q=0.71, gain_db=0.0,
        slope_db_per_oct=24.0,  # Invalid (only 12 or 48 supported)
        chain_position="default", processing_mode="stereo",
        rationale="x" * 50, inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    with pytest.raises(EqConfiguratorError, match="requires slope_db_per_oct"):
        _resolve_eq8_mode(band)


# ============================================================================
# apply_eq_corrective_decision — empty decision (no-op)
# ============================================================================


def test_apply_empty_decision_no_op(tmp_path):
    """Empty decision (bands=()) returns valid report without modifying .als."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    decision = MixDecision(
        value=EQCorrectiveDecision(bands=()),
        lane="eq_corrective",
        rationale="No conflict measured ; no intervention.",
        confidence=0.9,
    )
    report = apply_eq_corrective_decision(ref_copy, decision, dry_run=False)
    assert report.bands_applied == ()
    assert report.eq8_created == 0
    assert report.eq8_reused == 0
    # File unchanged size (bytes equal)
    assert ref_copy.stat().st_size == _REF_ALS.stat().st_size


# ============================================================================
# apply_eq_corrective_decision — single bell cut (dry_run + real apply)
# ============================================================================


def test_apply_single_bell_cut_dry_run(tmp_path):
    """dry_run=True : no file write, but report describes the operation."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    initial_size = ref_copy.stat().st_size

    band = _make_band()  # default : Kick 1, bell cut at 247 Hz
    decision = MixDecision(
        value=EQCorrectiveDecision(bands=(band,)),
        lane="eq_corrective",
        rationale="247 Hz resonance on Kick 1.",
        confidence=0.85,
    )
    report = apply_eq_corrective_decision(ref_copy, decision, dry_run=True)
    assert len(report.bands_applied) == 1
    assert "[H/R] Kick 1" in report.bands_applied[0]
    assert "bell@247.0Hz" in report.bands_applied[0]
    # File NOT modified (dry run)
    assert ref_copy.stat().st_size == initial_size


def test_apply_single_bell_cut_real_write(tmp_path):
    """Full apply : decompress + patch + recompress. Verify Eq8 band has new params."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    band = _make_band(center_hz=300.0, gain_db=-2.5, q=3.0)
    decision = MixDecision(
        value=EQCorrectiveDecision(bands=(band,)),
        lane="eq_corrective",
        rationale="300 Hz mud cleanup on Kick 1.",
        confidence=0.85,
    )
    report = apply_eq_corrective_decision(ref_copy, decision, output_path=output)

    assert output.exists()
    assert len(report.bands_applied) == 1
    # Kick 1 already had Eq8 → reused
    assert report.eq8_reused == 1
    assert report.eq8_created == 0
    assert report.output_path == str(output)

    # Verify Eq8 band actually configured
    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Kick 1")
    eq8 = track.find(".//Eq8")
    assert eq8 is not None

    # Find a band with Mode=3 (Bell) AND Freq close to 300 — it's our write
    found = False
    for i in range(8):
        try:
            band_el = als_utils.get_eq8_band(eq8, i)
        except (ValueError, IndexError):
            continue
        mode_el = band_el.find("Mode/Manual")
        freq_el = band_el.find("Freq/Manual")
        is_on = band_el.find("IsOn/Manual")
        if mode_el is None or freq_el is None:
            continue
        if (mode_el.get("Value") == "3"
                and abs(float(freq_el.get("Value", 0)) - 300.0) < 0.1
                and is_on is not None
                and is_on.get("Value") == "true"):
            found = True
            # Also verify gain and Q
            gain_el = band_el.find("Gain/Manual")
            q_el = band_el.find("Q/Manual")
            assert abs(float(gain_el.get("Value")) - (-2.5)) < 0.01
            assert abs(float(q_el.get("Value")) - 3.0) < 0.01
            break
    assert found, "Bell band at 300 Hz not found in patched Eq8"


# ============================================================================
# apply_eq_corrective_decision — track not found
# ============================================================================


def test_apply_track_not_found_raises(tmp_path):
    """als_utils.find_track_by_name raises ValueError when track absent.
    Configurator propagates verbatim (Tier A should have caught it earlier)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    band = _make_band(track="NonexistentTrack")
    decision = MixDecision(
        value=EQCorrectiveDecision(bands=(band,)),
        lane="eq_corrective",
        rationale="Test : track not in .als.",
        confidence=0.5,
    )
    with pytest.raises(ValueError, match="No track named 'NonexistentTrack'"):
        apply_eq_corrective_decision(ref_copy, decision, dry_run=True)


# ============================================================================
# apply_eq_corrective_decision — multiple bands on one track
# ============================================================================


def test_apply_multiple_bands_one_track(tmp_path):
    """Two bands on Kick 1 → both land on the existing Eq8 (eq8_reused = 1)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    band1 = _make_band(center_hz=247.0, gain_db=-3.5, q=4.5)
    band2 = _make_band(band_type="highpass", intent="filter",
                        center_hz=30.0, q=0.71, gain_db=0.0, slope=12.0)
    decision = MixDecision(
        value=EQCorrectiveDecision(bands=(band1, band2)),
        lane="eq_corrective",
        rationale="2 corrections sur Kick 1 : sub cleanup + résonance 247.",
        confidence=0.85,
    )
    report = apply_eq_corrective_decision(ref_copy, decision, output_path=output)
    assert len(report.bands_applied) == 2
    # Existing Eq8 reused for first band ; second band reuses same Eq8
    # (no new Eq8 created)
    assert report.eq8_created == 0
    assert report.eq8_reused == 1
