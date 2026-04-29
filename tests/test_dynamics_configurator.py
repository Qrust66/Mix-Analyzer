"""Tests for mix_engine.writers.dynamics_configurator (Phase 4.11).

Phase 4.11 v1 scope : GlueCompressor + Limiter REUSE-only (no create paths).
Tests follow the Phase 4.10 pattern : translation/contract → static params
→ envelopes → idempotency/safety.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import als_utils
from mix_engine.blueprint import (
    DynamicsCorrection,
    DynamicsCorrectiveDecision,
    MixCitation,
    MixDecision,
)
from mix_engine.writers import (
    DynamicsConfiguratorError,
    DynamicsConfiguratorReport,
    apply_dynamics_corrective_decision,
)


_REF_ALS = Path(__file__).parent / "fixtures" / "reference_project.als"


def _make_correction(
    track: str = "[H/R] Bass Rythm",
    dynamics_type: str = "bus_glue",
    device: str = "GlueCompressor",
    threshold_db: float | None = -10.0,
    ratio: float | None = 2.0,
    attack_ms: float | None = 10.0,
    release_ms: float | None = 100.0,
    makeup_db: float | None = None,
    dry_wet: float | None = None,
    ceiling_db: float | None = None,
    chain_position: str = "default",
) -> DynamicsCorrection:
    """Build a minimal valid DynamicsCorrection."""
    return DynamicsCorrection(
        track=track,
        dynamics_type=dynamics_type,
        device=device,
        threshold_db=threshold_db,
        ratio=ratio,
        attack_ms=attack_ms,
        release_ms=release_ms,
        makeup_db=makeup_db,
        dry_wet=dry_wet,
        ceiling_db=ceiling_db,
        chain_position=chain_position,
        rationale=(
            "Causal: dynamics correction baseline test. Interactional: "
            "validates GlueCompressor/Limiter reuse-only path Phase 4.11 v1."
        ),
        inspired_by=(
            MixCitation(kind="diagnostic", path="HealthScore!B5",
                         excerpt="Dynamics 60/100"),
        ),
    )


# ============================================================================
# Empty + smoke
# ============================================================================


def test_empty_corrections_no_op(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=()),
        lane="dynamics_corrective",
        rationale="No dynamics conflict measured.",
        confidence=0.9,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision)
    assert isinstance(report, DynamicsConfiguratorReport)
    assert report.corrections_applied == ()
    assert report.corrections_skipped == ()
    assert report.devices_reused == 0


# ============================================================================
# REUSE GlueCompressor (Bass Rythm has one)
# ============================================================================


def test_apply_glue_comp_reuses_existing(tmp_path):
    """[H/R] Bass Rythm has GlueCompressor. bus_glue should write Threshold/
    Ratio/Attack/Release/Makeup verbatim onto it (REUSE)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    correction = _make_correction(
        threshold_db=-12.5, ratio=2.0, attack_ms=15.0, release_ms=200.0,
        makeup_db=3.5,
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Glue 2:1 on Bass Rythm bus.",
        confidence=0.85,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, output_path=output)
    assert len(report.corrections_applied) == 1
    assert report.devices_reused == 1
    assert report.devices_created == 0

    # Verify XML : GlueCompressor on Bass Rythm has new Threshold = -12.5
    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    glue = track.find(".//GlueCompressor")
    assert glue is not None
    threshold = float(glue.find("Threshold/Manual").get("Value"))
    assert abs(threshold - (-12.5)) < 0.01
    ratio = float(glue.find("Ratio/Manual").get("Value"))
    assert abs(ratio - 2.0) < 0.01
    attack = float(glue.find("Attack/Manual").get("Value"))
    assert abs(attack - 15.0) < 0.01


def test_apply_glue_comp_track_no_device_skips(tmp_path):
    """Track without GlueCompressor → REUSE fails → skip with reason."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    # [H/R] Kick 1 only has Eq8, no GlueCompressor
    correction = _make_correction(track="[H/R] Kick 1")
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Test REUSE-only failure path.",
        confidence=0.8,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, dry_run=True)
    assert len(report.corrections_applied) == 0
    assert len(report.corrections_skipped) == 1
    assert "no GlueCompressor" in report.corrections_skipped[0][1]


def test_apply_glue_comp_knee_db_warning(tmp_path):
    """knee_db on GlueCompressor → warning (no Knee param exists)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    correction = DynamicsCorrection(
        track="[H/R] Bass Rythm",
        dynamics_type="bus_glue",
        device="GlueCompressor",
        threshold_db=-10.0,
        ratio=2.0,
        attack_ms=10.0,
        release_ms=100.0,
        makeup_db=2.0,
        knee_db=3.0,  # not supported on GlueComp
        chain_position="default",
        rationale="Test knee_db warning on GlueCompressor (no Knee param).",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Knee warning test.",
        confidence=0.7,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, output_path=output)
    assert len(report.corrections_applied) == 1
    assert any("knee_db" in w and "GlueCompressor has no Knee" in w
                for w in report.warnings)


# ============================================================================
# REUSE Limiter
# ============================================================================


def test_apply_limiter_reuses_existing(tmp_path):
    """Bass Rythm has Limiter. limit dynamics_type sets Ceiling."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    correction = DynamicsCorrection(
        track="[H/R] Bass Rythm",
        dynamics_type="limit",
        device="Limiter",
        ceiling_db=-0.5,
        release_ms=50.0,
        chain_position="default",
        rationale="Test Limiter REUSE — write Ceiling and Release.",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Per-track limiter.",
        confidence=0.85,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, output_path=output)
    assert len(report.corrections_applied) == 1
    assert report.devices_reused == 1

    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    limiter = track.find(".//Limiter")
    assert limiter is not None
    ceiling = float(limiter.find("Ceiling/Manual").get("Value"))
    assert abs(ceiling - (-0.5)) < 0.01


def test_apply_limiter_release_auto_sets_flag(tmp_path):
    """release_auto=True → AutoRelease/@Value=true."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    correction = DynamicsCorrection(
        track="[H/R] Bass Rythm",
        dynamics_type="limit",
        device="Limiter",
        ceiling_db=-0.3,
        release_ms=50.0,
        release_auto=True,
        chain_position="default",
        rationale="Test AutoRelease flag write on Limiter.",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="AutoRelease test.",
        confidence=0.8,
    )
    apply_dynamics_corrective_decision(ref_copy, decision, output_path=output)

    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    limiter = track.find(".//Limiter")
    auto = limiter.find("AutoRelease")
    assert auto is not None
    assert auto.get("Value") == "true"


def test_apply_limiter_threshold_warning(tmp_path):
    """threshold_db on Limiter → warning (Limiter has no Threshold separate from Ceiling)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    correction = DynamicsCorrection(
        track="[H/R] Bass Rythm",
        dynamics_type="limit",
        device="Limiter",
        threshold_db=-3.0,  # warned
        ceiling_db=-0.5,
        release_ms=50.0,
        chain_position="default",
        rationale="Test threshold_db warning on Limiter (uses Ceiling instead).",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Limiter ignored params test.",
        confidence=0.7,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, output_path=output)
    assert any("threshold_db" in w and "ignored" in w for w in report.warnings)


# ============================================================================
# Phase 4.11 v1 scope check (unsupported devices/types skipped with reason)
# ============================================================================


def test_unsupported_compressor2_skipped(tmp_path):
    """Compressor2 not yet supported by Phase 4.11 v1 → skipped with reason."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    correction = DynamicsCorrection(
        track="[H/R] Bass Rythm",
        dynamics_type="compress",
        device="Compressor2",
        threshold_db=-12.0,
        ratio=4.0,
        attack_ms=5.0,
        release_ms=50.0,
        chain_position="default",
        rationale="Compressor2 not supported in Phase 4.11 v1 (Phase 4.12 will add).",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Test scope skip.",
        confidence=0.5,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, dry_run=True)
    assert len(report.corrections_applied) == 0
    assert len(report.corrections_skipped) == 1
    assert "Compressor2" in report.corrections_skipped[0][1]
    assert "Phase 4.12" in report.corrections_skipped[0][1]


def test_unsupported_gate_skipped(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    correction = DynamicsCorrection(
        track="[H/R] Bass Rythm",
        dynamics_type="gate",
        device="Gate",
        threshold_db=-50.0,
        chain_position="default",
        rationale="Gate not supported in Phase 4.11 v1 — should skip cleanly.",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Gate skip test.",
        confidence=0.5,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, dry_run=True)
    assert len(report.corrections_skipped) == 1
    assert "Gate" in report.corrections_skipped[0][1]


def test_dynamics_type_bus_glue_wrong_device_skipped(tmp_path):
    """bus_glue + Limiter combo → cross-field skip (bus_glue requires GlueComp)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    correction = DynamicsCorrection(
        track="[H/R] Bass Rythm",
        dynamics_type="bus_glue",
        device="Limiter",  # wrong : bus_glue requires GlueCompressor
        threshold_db=-10.0,
        chain_position="default",
        rationale="Cross-field check : bus_glue must use GlueCompressor.",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Wrong-device test.",
        confidence=0.4,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, dry_run=True)
    assert len(report.corrections_skipped) == 1
    assert "bus_glue" in report.corrections_skipped[0][1]
    assert "GlueCompressor" in report.corrections_skipped[0][1]


# ============================================================================
# Track not found (propagates)
# ============================================================================


def test_track_not_found_raises(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    correction = _make_correction(track="NonexistentTrack")
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Test track-not-found path.",
        confidence=0.5,
    )
    with pytest.raises(ValueError, match="No track named 'NonexistentTrack'"):
        apply_dynamics_corrective_decision(ref_copy, decision, dry_run=True)


# ============================================================================
# Multi-correction (mix of supported + skipped)
# ============================================================================


# ============================================================================
# Phase 4.11 Step 2 — chain_position support tests
# ============================================================================

from als_utils import find_existing_device_at_dynamics_position  # noqa: E402


def test_position_pre_limiter_finds_glue_before_limiter(tmp_path):
    """Bass Rythm chain : [Eq8, StereoGain, PluginDevice, GlueComp, Limiter].
    GlueCompressor at index 3 IS before Limiter at index 4 → match."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    tree = als_utils.parse_als(str(ref_copy))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    found = find_existing_device_at_dynamics_position(
        track, "GlueCompressor", "pre_limiter",
    )
    assert found is not None
    assert found.tag == "GlueCompressor"


def test_position_chain_end_limiter_finds_terminal_limiter(tmp_path):
    """Limiter at last index → chain_end_limiter matches."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    tree = als_utils.parse_als(str(ref_copy))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    found = find_existing_device_at_dynamics_position(
        track, "Limiter", "chain_end_limiter",
    )
    assert found is not None
    assert found.tag == "Limiter"


def test_position_post_eq_corrective_finds_glue_after_eq8(tmp_path):
    """GlueCompressor at index 3 is after Eq8 at index 0 → post_eq_corrective match."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    tree = als_utils.parse_als(str(ref_copy))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    found = find_existing_device_at_dynamics_position(
        track, "GlueCompressor", "post_eq_corrective",
    )
    assert found is not None


def test_position_pre_eq_corrective_no_match_when_eq8_after(tmp_path):
    """GlueCompressor at index 3 is AFTER Eq8 at 0 → pre_eq_corrective NO match."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    tree = als_utils.parse_als(str(ref_copy))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    found = find_existing_device_at_dynamics_position(
        track, "GlueCompressor", "pre_eq_corrective",
    )
    assert found is None


def test_position_no_anchor_returns_none(tmp_path):
    """Track with no Saturator → pre_saturation/post_saturation return None."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    tree = als_utils.parse_als(str(ref_copy))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    # Bass Rythm has no Saturator/DrumBuss
    found = find_existing_device_at_dynamics_position(
        track, "GlueCompressor", "pre_saturation",
    )
    assert found is None


def test_position_unknown_raises(tmp_path):
    """Unknown chain_position → ValueError. Requires a track WITH the
    target device for the validation to fire (None returned early if no match)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    tree = als_utils.parse_als(str(ref_copy))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    with pytest.raises(ValueError, match="Unknown dynamics chain_position"):
        find_existing_device_at_dynamics_position(
            track, "GlueCompressor", "bogus_position",
        )


def test_apply_glue_pre_limiter_position(tmp_path):
    """End-to-end : Tier A specifies chain_position='pre_limiter' →
    configurator finds GlueComp (which IS before Limiter on Bass Rythm)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    correction = _make_correction(
        track="[H/R] Bass Rythm",
        chain_position="pre_limiter",
        threshold_db=-15.0,
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Glue at pre_limiter — bus glue before final limiter.",
        confidence=0.85,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, output_path=output)
    assert len(report.corrections_applied) == 1
    assert report.devices_reused == 1


def test_apply_glue_chain_end_no_match_skipped(tmp_path):
    """Bass Rythm has Limiter at chain_end (not GlueComp). Requesting
    chain_position='chain_end' for GlueCompressor → no match → skipped."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    correction = _make_correction(
        track="[H/R] Bass Rythm",
        chain_position="chain_end",
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="GlueComp at chain_end — but Bass Rythm has Limiter there.",
        confidence=0.6,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, dry_run=True)
    assert len(report.corrections_skipped) == 1
    assert "chain_position='chain_end'" in report.corrections_skipped[0][1]


def test_apply_limiter_chain_end_limiter_position(tmp_path):
    """chain_end_limiter is the canonical Limiter terminal placement.
    Bass Rythm Limiter IS at chain end → match."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    correction = DynamicsCorrection(
        track="[H/R] Bass Rythm",
        dynamics_type="limit",
        device="Limiter",
        ceiling_db=-0.3,
        release_ms=50.0,
        chain_position="chain_end_limiter",
        rationale="Final Limiter at chain_end_limiter — terminal placement.",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Final limiter on Bass Rythm.",
        confidence=0.85,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, output_path=output)
    assert len(report.corrections_applied) == 1
    assert report.devices_reused == 1


# ============================================================================
# Phase 4.11 Step 3 — Envelope writing (threshold/makeup/dry_wet on GlueComp)
# ============================================================================

from mix_engine.blueprint import DynamicsAutomationPoint  # noqa: E402


def _glue_with_envelope(envelope_field: str, points: list, **overrides):
    """Build a GlueCompressor correction with one envelope on threshold/makeup/dry_wet."""
    base = dict(
        track="[H/R] Bass Rythm",
        dynamics_type="bus_glue",
        device="GlueCompressor",
        threshold_db=-10.0,
        ratio=2.0,
        attack_ms=10.0,
        release_ms=100.0,
        makeup_db=2.0,
        dry_wet=1.0,
        chain_position="default",
        rationale="Dynamic envelope baseline test for envelope writing path Step 3.",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
        threshold_envelope=(),
        makeup_envelope=(),
        dry_wet_envelope=(),
        sidechain_depth_envelope=(),
        sections=(),
    )
    base.update(overrides)
    base[envelope_field] = tuple(
        DynamicsAutomationPoint(bar=b, value=v) for b, v in points
    )
    return DynamicsCorrection(**base)


def test_apply_threshold_envelope_writes_automation(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    correction = _glue_with_envelope(
        "threshold_envelope",
        [(0, -10.0), (16, -14.0), (32, -10.0)],
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Test threshold envelope on GlueCompressor.",
        confidence=0.85,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, output_path=output)
    assert report.automations_written == 1

    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    envelopes = track.findall(".//AutomationEnvelopes/Envelopes/AutomationEnvelope")
    assert len(envelopes) >= 1
    counts = [len(e.findall(".//FloatEvent")) for e in envelopes]
    # 3 points + 1 default pre-song = 4 events on the new envelope
    assert 4 in counts


def test_apply_multi_envelope_one_correction(tmp_path):
    """Threshold + Makeup + DryWet envelopes on same GlueComp → 3 envelopes."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    base = dict(
        track="[H/R] Bass Rythm",
        dynamics_type="bus_glue",
        device="GlueCompressor",
        threshold_db=-10.0,
        ratio=2.0,
        attack_ms=10.0,
        release_ms=100.0,
        makeup_db=2.0,
        dry_wet=1.0,
        chain_position="default",
        rationale="Triple envelope (threshold+makeup+drywet) on GlueCompressor.",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
        sections=(),
    )
    correction = DynamicsCorrection(
        threshold_envelope=(DynamicsAutomationPoint(0, -10),
                             DynamicsAutomationPoint(16, -12),
                             DynamicsAutomationPoint(32, -10)),
        makeup_envelope=(DynamicsAutomationPoint(0, 2),
                          DynamicsAutomationPoint(16, 3),
                          DynamicsAutomationPoint(32, 2)),
        dry_wet_envelope=(DynamicsAutomationPoint(0, 1.0),
                           DynamicsAutomationPoint(16, 0.7),
                           DynamicsAutomationPoint(32, 1.0)),
        sidechain_depth_envelope=(),
        **base,
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Triple envelope test.",
        confidence=0.8,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, output_path=output)
    assert report.automations_written == 3


def test_apply_envelope_with_sections_skipped_with_warning(tmp_path):
    """sections non-empty + envelope → SKIPPED with warning, static still applied."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    correction = _glue_with_envelope(
        "threshold_envelope",
        [(0, -10), (16, -14), (32, -10)],
        sections=(2,),
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Envelope with sections — Phase 4.11 v1 limitation expected.",
        confidence=0.7,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, output_path=output)
    assert len(report.corrections_applied) == 1  # static still applied
    assert report.automations_written == 0  # envelope skipped
    assert any("sections" in w.lower() and "skipped" in w.lower()
                for w in report.warnings)


def test_apply_envelope_on_limiter_skipped_with_warning(tmp_path):
    """Limiter envelopes not yet supported (no compatible params) → skipped."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    correction = DynamicsCorrection(
        track="[H/R] Bass Rythm",
        dynamics_type="limit",
        device="Limiter",
        ceiling_db=-0.5,
        release_ms=50.0,
        threshold_envelope=(DynamicsAutomationPoint(0, -3),
                             DynamicsAutomationPoint(16, -1),
                             DynamicsAutomationPoint(32, -3)),
        chain_position="default",
        rationale="Limiter envelope test — Phase 4.11 v1 should skip with warning.",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Limiter envelope skip test.",
        confidence=0.7,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, output_path=output)
    # Static Ceiling still written
    assert len(report.corrections_applied) == 1
    # Envelope NOT written (Limiter envelopes not supported v1)
    assert report.automations_written == 0
    assert any("Limiter" in w and "not yet supported" in w
                for w in report.warnings)


def test_apply_sidechain_depth_envelope_deferred_warning(tmp_path):
    """sidechain_depth_envelope deferred to Phase 4.12 → warning, no write."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    correction = _glue_with_envelope(
        "sidechain_depth_envelope",
        [(0, -3), (16, -8), (32, -3)],
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Sidechain depth envelope test — Phase 4.12 deferred.",
        confidence=0.7,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, output_path=output)
    assert any("sidechain_depth_envelope" in w and "deferred" in w
                for w in report.warnings)
    # 0 envelopes written (sidechain only ; threshold/makeup/dry_wet are
    # empty in this correction)
    assert report.automations_written == 0


def test_apply_multi_correction_mixed(tmp_path):
    """3 corrections : 1 GlueComp valid + 1 Limiter valid + 1 Compressor2 skipped."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    c1 = _make_correction(track="[H/R] Bass Rythm", dynamics_type="bus_glue",
                           device="GlueCompressor", threshold_db=-12.0)
    c2 = DynamicsCorrection(
        track="[H/R] Bass Rythm", dynamics_type="limit", device="Limiter",
        ceiling_db=-0.3, release_ms=50.0, chain_position="default",
        rationale="Limiter on Bass Rythm — second correction in mixed batch.",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    c3 = DynamicsCorrection(
        track="[H/R] Bass Rythm", dynamics_type="compress", device="Compressor2",
        threshold_db=-15.0, ratio=4.0, chain_position="default",
        rationale="Compressor2 in batch — should skip (Phase 4.12 scope).",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    decision = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(c1, c2, c3)),
        lane="dynamics_corrective",
        rationale="Mixed Phase 4.11 v1 + 4.12 scope batch — partial apply expected.",
        confidence=0.8,
    )
    report = apply_dynamics_corrective_decision(ref_copy, decision, output_path=output)
    assert len(report.corrections_applied) == 2  # GlueComp + Limiter
    assert len(report.corrections_skipped) == 1  # Compressor2
    assert report.devices_reused == 2
