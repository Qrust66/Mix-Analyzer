"""Tests for mix_engine.blueprint.als_writer.apply_blueprint (Phase 4.19).

Phase 4.19 v1 scope :
- apply_blueprint(MixBlueprint, ...) iterates filled lanes in
  MIX_DEPENDENCIES topological order and calls the matching Tier B writer
- Lanes filled in the blueprint but without a Tier B writer (currently
  ``diagnostic`` only — read-only) land in skipped_lanes
- AlsWriterReport aggregates per-lane writer reports + overall safety
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import als_utils
from mix_engine.blueprint import (
    AlsWriterReport,
    MASTER_TRACK_NAME,
    MasteringDecision,
    MasterMove,
    MixBlueprint,
    MixCitation,
    MixDecision,
    apply_blueprint,
    lanes_with_writer,
)


_REF_ALS = Path(__file__).parent / "fixtures" / "reference_project.als"


def _mastering_decision(width: float = 1.2) -> MixDecision[MasteringDecision]:
    move = MasterMove(
        type="stereo_enhance",
        target_track=MASTER_TRACK_NAME,
        device="StereoGain",
        chain_position="master_stereo",
        width=width,
        rationale=(
            "Causal: als_writer test baseline. Interactional: validates Phase "
            "4.19 apply_blueprint() end-to-end on the mastering lane."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    return MixDecision(
        value=MasteringDecision(moves=(move,)),
        lane="mastering",
        rationale="als_writer test wrapper.",
        confidence=0.85,
    )


# ============================================================================
# lanes_with_writer
# ============================================================================


def test_lanes_with_writer_matches_documented_seven():
    expected = {
        "routing", "eq_corrective", "dynamics_corrective", "stereo_spatial",
        "chain", "automation", "mastering",
    }
    assert lanes_with_writer() == frozenset(expected)


# ============================================================================
# apply_blueprint — happy paths
# ============================================================================


def test_empty_blueprint_no_op(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    bp = MixBlueprint(name="empty")
    report = apply_blueprint(bp, ref_copy)
    assert isinstance(report, AlsWriterReport)
    assert report.execution_order == ()
    assert report.lane_reports == {}
    assert report.skipped_lanes == ()
    assert report.overall_safety_status == "PASS"


def test_single_mastering_lane_writes_als(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    bp = MixBlueprint(name="masttest").with_decision(
        "mastering", _mastering_decision(width=1.30),
    )
    report = apply_blueprint(bp, ref_copy, output_path=output)
    assert report.execution_order == ("mastering",)
    assert report.overall_safety_status == "PASS"
    assert report.output_path == str(output)
    assert "mastering" in report.lane_reports

    tree = als_utils.parse_als(str(output))
    main = tree.getroot().find(".//MainTrack")
    sg = main.find(".//StereoGain")
    width = float(sg.find("StereoWidth/Manual").get("Value"))
    assert abs(width - 1.30) < 0.01


def test_dry_run_does_not_mutate(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    pre_size = ref_copy.stat().st_size

    bp = MixBlueprint(name="dryrun").with_decision(
        "mastering", _mastering_decision(),
    )
    report = apply_blueprint(bp, ref_copy, dry_run=True)
    assert report.execution_order == ("mastering",)
    assert ref_copy.stat().st_size == pre_size


def test_overwrite_source_when_no_output(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    bp = MixBlueprint(name="overwrite").with_decision(
        "mastering", _mastering_decision(width=1.05),
    )
    report = apply_blueprint(bp, ref_copy, output_path=None)
    assert report.output_path == str(ref_copy)
    tree = als_utils.parse_als(str(ref_copy))
    main = tree.getroot().find(".//MainTrack")
    sg = main.find(".//StereoGain")
    width = float(sg.find("StereoWidth/Manual").get("Value"))
    assert abs(width - 1.05) < 0.01


def test_missing_als_raises(tmp_path):
    bp = MixBlueprint(name="x").with_decision("mastering", _mastering_decision())
    with pytest.raises(FileNotFoundError):
        apply_blueprint(bp, tmp_path / "nonexistent.als")


# ============================================================================
# Writerless lane handling — diagnostic is read-only, lands in skipped
# ============================================================================


def test_diagnostic_lane_filled_lands_in_skipped(tmp_path):
    """The ``diagnostic`` lane carries a DiagnosticReport (read-only) ; it
    must NEVER be passed to a Tier B writer. apply_blueprint records it
    in skipped_lanes with a reason."""
    from mix_engine.blueprint import (
        DiagnosticReport, FullMixMetrics, HealthScore,
    )

    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    diag_decision = MixDecision(
        value=DiagnosticReport(
            project_name="test",
            full_mix=FullMixMetrics(
                integrated_lufs=-14.0, true_peak_dbtp=-1.0,
                crest_factor_db=10.0, plr_db=10.0, lra_db=6.0,
                dominant_band="mid", correlation=0.5, stereo_width=0.5,
                spectral_entropy=0.7,
            ),
            tracks=(),
            anomalies=(),
            health_score=HealthScore(overall=85.0, breakdown=()),
        ),
        lane="diagnostic",
        rationale="Diagnostic test wrapper.",
        confidence=0.9,
    )
    bp = MixBlueprint(name="diag").with_decision("diagnostic", diag_decision)
    report = apply_blueprint(bp, ref_copy)
    assert report.execution_order == ()
    assert len(report.skipped_lanes) == 1
    lane, reason = report.skipped_lanes[0]
    assert lane == "diagnostic"
    assert "no Tier B writer" in reason
