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

# Pluggin Mapping.als template — required by als_utils._load_eq8_template
# to clone a real Eq8 when a track has none. Some local checkouts may not
# have this file (gitignored history). Tests that exercise CREATE paths
# (vs reuse-existing) skip when absent.
_PLUGGIN_TEMPLATE = (
    Path(__file__).resolve().parent.parent
    / "ableton" / "projects" / "Pluggin Mapping.als"
)
_eq8_template_available = _PLUGGIN_TEMPLATE.exists()
_skip_if_no_template = pytest.mark.skipif(
    not _eq8_template_available,
    reason=f"Pluggin Mapping.als template not present at {_PLUGGIN_TEMPLATE} — "
            "test requires Eq8 clone source. Existing-Eq8 reuse paths still tested.",
)


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


# ============================================================================
# Phase 4.10 Step 2 — chain_position resolution (unit tests on helpers)
# ============================================================================

from als_utils import (  # noqa: E402
    ChainPositionUnresolvedError,
    _categorize_device,
    _find_existing_eq8_in_region,
    _resolve_insert_position,
)


class _MockElement:
    """Minimal ET.Element-like for category resolution unit tests."""
    def __init__(self, tag): self.tag = tag


def _categories(tags):
    return [_categorize_device(_MockElement(t)) for t in tags]


def test_resolve_chain_start_returns_zero():
    cats = _categories(["Eq8", "Compressor2", "Limiter"])
    assert _resolve_insert_position(cats, "chain_start") == 0


def test_resolve_chain_end_returns_len():
    cats = _categories(["Eq8", "Compressor2", "Limiter"])
    assert _resolve_insert_position(cats, "chain_end") == 3


def test_resolve_pre_compressor_finds_first_compressor():
    cats = _categories(["Eq8", "Saturator", "Compressor2", "Limiter"])
    assert _resolve_insert_position(cats, "pre_compressor") == 2


def test_resolve_post_compressor_finds_after_last():
    cats = _categories(["Eq8", "Compressor2", "Saturator", "Limiter"])
    # Limiter (index 3) is also a compressor → post = 4
    assert _resolve_insert_position(cats, "post_compressor") == 4


def test_resolve_pre_compressor_no_compressor_raises():
    cats = _categories(["Eq8", "Saturator"])
    with pytest.raises(ChainPositionUnresolvedError, match="no Compressor"):
        _resolve_insert_position(cats, "pre_compressor")


def test_resolve_post_compressor_no_compressor_raises():
    cats = _categories(["Eq8", "Saturator"])
    with pytest.raises(ChainPositionUnresolvedError, match="no Compressor"):
        _resolve_insert_position(cats, "post_compressor")


def test_resolve_post_gate_pre_compressor_typical():
    cats = _categories(["Gate", "Compressor2"])
    assert _resolve_insert_position(cats, "post_gate_pre_compressor") == 1


def test_resolve_post_gate_pre_compressor_no_gate_falls_back_pre_comp():
    cats = _categories(["Eq8", "Compressor2"])
    assert _resolve_insert_position(cats, "post_gate_pre_compressor") == 1


def test_resolve_post_gate_pre_compressor_no_comp_appends_after_gate():
    cats = _categories(["Eq8", "Gate"])
    assert _resolve_insert_position(cats, "post_gate_pre_compressor") == 2


def test_resolve_post_gate_pre_compressor_neither_raises():
    cats = _categories(["Eq8", "Saturator"])
    with pytest.raises(ChainPositionUnresolvedError,
                        match="neither Gate nor Compressor"):
        _resolve_insert_position(cats, "post_gate_pre_compressor")


def test_resolve_post_gate_pre_compressor_inverted_raises():
    """Gate AFTER Compressor → impossible target."""
    cats = _categories(["Compressor2", "Gate"])
    with pytest.raises(ChainPositionUnresolvedError, match="impossible"):
        _resolve_insert_position(cats, "post_gate_pre_compressor")


def test_resolve_pre_saturation():
    cats = _categories(["Eq8", "Compressor2", "Saturator"])
    assert _resolve_insert_position(cats, "pre_saturation") == 2


def test_resolve_post_saturation_with_drumbuss():
    cats = _categories(["Eq8", "DrumBuss", "Limiter"])
    # DrumBuss is "saturation" category → post = 2
    assert _resolve_insert_position(cats, "post_saturation") == 2


def test_resolve_pre_eq_creative_raises_not_supported():
    cats = _categories(["Eq8", "Compressor2"])
    with pytest.raises(ChainPositionUnresolvedError,
                        match="distinguishing creative vs corrective"):
        _resolve_insert_position(cats, "pre_eq_creative")


def test_resolve_unknown_chain_position_raises():
    cats = _categories(["Eq8"])
    with pytest.raises(ChainPositionUnresolvedError, match="Unknown"):
        _resolve_insert_position(cats, "bogus_position")


# ============================================================================
# Phase 4.10 Step 2 — _find_existing_eq8_in_region idempotency tests
# ============================================================================


def test_existing_eq8_at_chain_start_reused():
    """Eq8 at index 0 → reused for chain_start."""
    children = [_MockElement("Eq8"), _MockElement("Compressor2")]
    cats = ["eq8", "compressor"]
    found = _find_existing_eq8_in_region(children, cats, "chain_start")
    assert found is children[0]


def test_existing_eq8_pre_compressor_reused():
    """Eq8 before first Compressor → reused for pre_compressor."""
    children = [_MockElement("Eq8"), _MockElement("Saturator"),
                _MockElement("Compressor2")]
    cats = ["eq8", "saturation", "compressor"]
    found = _find_existing_eq8_in_region(children, cats, "pre_compressor")
    assert found is children[0]


def test_existing_eq8_post_compressor_reused():
    """Eq8 after last Compressor → reused for post_compressor."""
    children = [_MockElement("Compressor2"), _MockElement("Eq8")]
    cats = ["compressor", "eq8"]
    found = _find_existing_eq8_in_region(children, cats, "post_compressor")
    assert found is children[1]


def test_no_existing_eq8_in_region_returns_none():
    """No Eq8 in target region → None (caller will create)."""
    children = [_MockElement("Compressor2"), _MockElement("Limiter")]
    cats = ["compressor", "compressor"]
    found = _find_existing_eq8_in_region(children, cats, "pre_compressor")
    assert found is None


def test_no_compressor_at_all_returns_none():
    """post_compressor target but no comp → None (caller raises)."""
    children = [_MockElement("Eq8")]
    cats = ["eq8"]
    found = _find_existing_eq8_in_region(children, cats, "post_compressor")
    assert found is None


# ============================================================================
# Phase 4.10 Step 2 — Integration tests on real .als with multiple devices
# ============================================================================


def test_apply_pre_compressor_reuses_existing_eq8(tmp_path):
    """[H/R] Bass Rythm has Eq8 at index 0, GlueCompressor at index 3.
    Requesting chain_position=pre_compressor must REUSE the existing Eq8
    (idempotency) — not create a duplicate."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    band = _make_band(track="[H/R] Bass Rythm", center_hz=120.0,
                       gain_db=-2.0, q=2.0)
    band = EQBandCorrection(
        track=band.track, band_type=band.band_type, intent=band.intent,
        center_hz=band.center_hz, q=band.q, gain_db=band.gain_db,
        slope_db_per_oct=band.slope_db_per_oct,
        chain_position="pre_compressor",  # explicit
        processing_mode=band.processing_mode,
        rationale=band.rationale, inspired_by=band.inspired_by,
    )
    decision = MixDecision(
        value=EQCorrectiveDecision(bands=(band,)),
        lane="eq_corrective",
        rationale="120 Hz boom on Bass Rythm pre_compressor.",
        confidence=0.85,
    )
    report = apply_eq_corrective_decision(ref_copy, decision, output_path=output)
    assert report.eq8_reused == 1
    assert report.eq8_created == 0

    # Verify chain still has only 1 Eq8 (no duplicate created)
    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    devices = track.find(".//DeviceChain/DeviceChain/Devices")
    eq8_count = sum(1 for c in devices if c.tag == "Eq8")
    assert eq8_count == 1, "pre_compressor must reuse existing Eq8, not duplicate"


@_skip_if_no_template
def test_apply_post_compressor_creates_new_eq8(tmp_path):
    """[H/R] Bass Rythm has NO Eq8 after Limiter. post_compressor must
    CREATE a new Eq8 inserted at chain_end position (after Limiter)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    band = _make_band(track="[H/R] Bass Rythm", center_hz=2500.0,
                       gain_db=-1.5, q=3.0)
    band = EQBandCorrection(
        track=band.track, band_type=band.band_type, intent=band.intent,
        center_hz=band.center_hz, q=band.q, gain_db=band.gain_db,
        slope_db_per_oct=band.slope_db_per_oct,
        chain_position="post_compressor",
        processing_mode=band.processing_mode,
        rationale=band.rationale, inspired_by=band.inspired_by,
    )
    decision = MixDecision(
        value=EQCorrectiveDecision(bands=(band,)),
        lane="eq_corrective",
        rationale="Post-comp tame harshness on Bass Rythm.",
        confidence=0.8,
    )
    report = apply_eq_corrective_decision(ref_copy, decision, output_path=output)
    # Bass Rythm already had an Eq8 → tracks_with_eq8_before_run includes it
    # → counts as reused. (eq8_created/reused track per-track presence, not
    # per-position.)
    assert report.eq8_reused == 1
    assert report.eq8_created == 0

    # Verify chain now has 2 Eq8 (1 original + 1 newly inserted post_compressor)
    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    devices = list(track.find(".//DeviceChain/DeviceChain/Devices"))
    eq8_indices = [i for i, c in enumerate(devices) if c.tag == "Eq8"]
    assert len(eq8_indices) == 2, "post_compressor must create a new Eq8"
    # New Eq8 must be at the end (after Limiter)
    assert eq8_indices[-1] == len(devices) - 1


def test_apply_pre_compressor_no_compressor_raises(tmp_path):
    """[H/R] Kick 1 only has [Eq8] — no compressor. Requesting pre_compressor
    must raise ChainPositionUnresolvedError."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    band = _make_band(track="[H/R] Kick 1")
    band = EQBandCorrection(
        track=band.track, band_type=band.band_type, intent=band.intent,
        center_hz=band.center_hz, q=band.q, gain_db=band.gain_db,
        slope_db_per_oct=band.slope_db_per_oct,
        chain_position="post_compressor",  # no comp on Kick 1
        processing_mode=band.processing_mode,
        rationale=band.rationale, inspired_by=band.inspired_by,
    )
    decision = MixDecision(
        value=EQCorrectiveDecision(bands=(band,)),
        lane="eq_corrective",
        rationale="Test : post_compressor requested but no comp.",
        confidence=0.5,
    )
    with pytest.raises(ChainPositionUnresolvedError, match="no Compressor"):
        apply_eq_corrective_decision(ref_copy, decision, dry_run=True)


def test_apply_chain_start_existing_eq8_reused(tmp_path):
    """Kick 1 has Eq8 at index 0 → chain_start reuses it (not duplicates)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    band = _make_band(track="[H/R] Kick 1")
    band = EQBandCorrection(
        track=band.track, band_type=band.band_type, intent=band.intent,
        center_hz=band.center_hz, q=band.q, gain_db=band.gain_db,
        slope_db_per_oct=band.slope_db_per_oct,
        chain_position="chain_start",
        processing_mode=band.processing_mode,
        rationale=band.rationale, inspired_by=band.inspired_by,
    )
    decision = MixDecision(
        value=EQCorrectiveDecision(bands=(band,)),
        lane="eq_corrective",
        rationale="Test chain_start with existing Eq8 at index 0.",
        confidence=0.8,
    )
    report = apply_eq_corrective_decision(ref_copy, decision, output_path=output)
    assert report.eq8_reused == 1

    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Kick 1")
    devices = list(track.find(".//DeviceChain/DeviceChain/Devices"))
    assert sum(1 for c in devices if c.tag == "Eq8") == 1
