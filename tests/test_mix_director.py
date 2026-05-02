"""Tests for mix_engine.director.Director (Phase 4.19).

Phase 4.19 v1 scope :
- topological_order(lanes) helper based on MIX_DEPENDENCIES
- Director.apply_mix(MixBlueprint, ...) composes :
    1. check_mix_cohesion(bp) — cross-lane validation
    2. If blockers and not force → COHESION_BLOCKED, no write
    3. Else apply_blueprint() → writes .als via Tier B writers
- MixResult aggregates cohesion + apply reports

Sibling files :
- ``tests/test_director.py`` covers composition_engine.director (unrelated)
- ``tests/test_mix_cohesion.py`` covers the cohesion infrastructure
- ``tests/test_als_writer.py`` covers apply_blueprint
"""
from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path

import pytest

import als_utils
from mix_engine.blueprint import (
    MASTER_TRACK_NAME,
    MasteringDecision,
    MasterMove,
    MixBlueprint,
    MixCitation,
    MixCohesionViolation,
    MixDecision,
    mix_cohesion_rule,
)
from mix_engine.blueprint import cohesion as cohesion_module
from mix_engine.director import (
    Director,
    MIX_DEPENDENCIES,
    MixResult,
    topological_order,
)


_REF_ALS = Path(__file__).parent / "fixtures" / "reference_project.als"


# ============================================================================
# Test isolation — same registry-swap helper as test_mix_cohesion.py
# ============================================================================


@contextmanager
def _isolated_registry():
    saved = cohesion_module._RULES
    cohesion_module._RULES = []
    try:
        yield cohesion_module._RULES
    finally:
        cohesion_module._RULES = saved


@pytest.fixture
def isolated_rules():
    with _isolated_registry() as registry:
        yield registry


# ============================================================================
# Builders
# ============================================================================


def _mastering_decision(width: float = 1.2) -> MixDecision[MasteringDecision]:
    move = MasterMove(
        type="stereo_enhance",
        target_track=MASTER_TRACK_NAME,
        device="StereoGain",
        chain_position="master_stereo",
        width=width,
        rationale=(
            "Causal: Director test baseline. Interactional: validates Phase "
            "4.19 Director.apply_mix() end-to-end on a single lane."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    return MixDecision(
        value=MasteringDecision(moves=(move,)),
        lane="mastering",
        rationale="Director test wrapper.",
        confidence=0.85,
    )


def _mastering_bp(width: float = 1.2) -> MixBlueprint:
    return MixBlueprint(name="dir-test").with_decision(
        "mastering", _mastering_decision(width),
    )


# ============================================================================
# topological_order
# ============================================================================


def test_topological_order_full_set_respects_dependencies():
    full = set(MIX_DEPENDENCIES)
    order = topological_order(full)
    assert len(order) == len(full)
    seen: set[str] = set()
    for lane in order:
        for dep in MIX_DEPENDENCIES[lane]:
            assert dep in seen, f"{lane} ran before its dep {dep}"
        seen.add(lane)


def test_topological_order_writer_only_subset():
    from mix_engine.blueprint import lanes_with_writer
    order = topological_order(lanes_with_writer())
    assert set(order) == set(lanes_with_writer())
    assert order.index("routing") < order.index("eq_corrective")
    assert order.index("eq_corrective") < order.index("chain")
    assert order.index("chain") < order.index("automation")
    assert order.index("automation") < order.index("mastering")


def test_topological_order_single_lane():
    assert topological_order({"mastering"}) == ("mastering",)


def test_topological_order_empty_set():
    assert topological_order(set()) == ()


def test_topological_order_partial_subset_skips_external_deps():
    """When a lane's dep is outside the subset, it shouldn't block it."""
    assert topological_order({"mastering"}) == ("mastering",)
    order = topological_order({"automation", "mastering", "chain"})
    assert order == ("chain", "automation", "mastering")


def test_topological_order_unknown_lane_raises():
    with pytest.raises(ValueError, match="Unknown lane"):
        topological_order({"frobnicate"})


# ============================================================================
# Director — happy paths
# ============================================================================


def test_apply_mix_empty_blueprint_returns_pass(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    bp = MixBlueprint(name="empty")
    result = Director().apply_mix(bp, ref_copy)
    assert isinstance(result, MixResult)
    assert result.overall_status == "PASS"
    assert result.cohesion.is_clean
    assert result.apply_report is not None
    assert result.apply_report.execution_order == ()
    assert result.ok


def test_apply_mix_single_mastering_lane_writes_als(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    result = Director().apply_mix(
        bp=_mastering_bp(width=1.25),
        als_path=ref_copy,
        output_path=output,
    )
    assert result.ok
    assert result.overall_status == "PASS"
    assert result.apply_report.execution_order == ("mastering",)
    assert result.output_path == str(output)
    rep = result.apply_report.lane_reports["mastering"]
    assert rep.safety_guardian_status == "PASS"

    tree = als_utils.parse_als(str(output))
    main = tree.getroot().find(".//MainTrack")
    sg = main.find(".//StereoGain")
    width = float(sg.find("StereoWidth/Manual").get("Value"))
    assert abs(width - 1.25) < 0.01


def test_apply_mix_dry_run_does_not_mutate(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    pre_size = ref_copy.stat().st_size

    result = Director().apply_mix(_mastering_bp(), ref_copy, dry_run=True)
    assert result.ok
    assert ref_copy.stat().st_size == pre_size


# ============================================================================
# Cohesion gate — block-severity halts the apply unless force=True
# ============================================================================


def test_apply_mix_cohesion_block_halts_apply(tmp_path, isolated_rules):
    """A registered block-severity rule firing must stop the apply
    pipeline ; the .als is left untouched."""
    @mix_cohesion_rule(lanes=("mastering",))
    def fail_rule(bp):
        return MixCohesionViolation(
            rule="fail_rule", severity="block",
            message="testing the gate", lanes=("mastering",),
        )

    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    pre_size = ref_copy.stat().st_size

    result = Director().apply_mix(_mastering_bp(width=1.5), ref_copy)
    assert result.overall_status == "COHESION_BLOCKED"
    assert not result.cohesion.is_clean
    assert len(result.cohesion.blockers) == 1
    assert result.apply_report is None  # no apply attempted
    assert result.output_path is None
    assert ref_copy.stat().st_size == pre_size  # .als untouched


def test_apply_mix_cohesion_warn_does_not_halt(tmp_path, isolated_rules):
    """A warn-severity rule must NOT stop the apply ; the violation is
    surfaced in the report but the .als is still written."""
    @mix_cohesion_rule(lanes=("mastering",))
    def warn_rule(bp):
        return MixCohesionViolation(
            rule="warn_rule", severity="warn",
            message="advisory only", lanes=("mastering",),
        )

    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    result = Director().apply_mix(
        _mastering_bp(width=1.18), ref_copy, output_path=output,
    )
    assert result.ok
    assert result.cohesion.is_clean  # warns don't make it unclean
    assert len(result.cohesion.warnings) == 1
    assert result.apply_report is not None
    assert result.apply_report.execution_order == ("mastering",)


def test_apply_mix_force_overrides_cohesion_block(tmp_path, isolated_rules):
    """force=True applies the .als even when cohesion has block-severity
    violations. Cohesion report stays surfaced."""
    @mix_cohesion_rule(lanes=("mastering",))
    def block_rule(bp):
        return MixCohesionViolation(
            rule="block_rule", severity="block",
            message="serious problem", lanes=("mastering",),
        )

    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    result = Director().apply_mix(
        _mastering_bp(width=1.40), ref_copy, output_path=output, force=True,
    )
    assert result.overall_status == "PASS"  # apply succeeded despite block
    assert not result.cohesion.is_clean  # cohesion report still surfaces it
    assert result.apply_report is not None
    assert result.apply_report.execution_order == ("mastering",)
    # .als was actually written
    tree = als_utils.parse_als(str(output))
    main = tree.getroot().find(".//MainTrack")
    sg = main.find(".//StereoGain")
    width = float(sg.find("StereoWidth/Manual").get("Value"))
    assert abs(width - 1.40) < 0.01


# ============================================================================
# Schema-typed mismatches still rejected at MixBlueprint.with_decision()
# ============================================================================


def test_blueprint_rejects_lane_mismatch(tmp_path):
    """MixBlueprint.with_decision() validates that decision.lane matches
    the slot. The Director consumes that validated invariant — no need
    for redundant checks at apply_mix time."""
    bp = MixBlueprint(name="x")
    decision = _mastering_decision()  # decision.lane == "mastering"
    with pytest.raises(ValueError, match="lane mismatch"):
        bp.with_decision("eq_corrective", decision)
