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
