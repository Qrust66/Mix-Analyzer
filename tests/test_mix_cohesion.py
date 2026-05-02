"""Tests for mix_engine.blueprint.cohesion infrastructure (Phase 4.19).

Phase 4.19 ships the decorator + registry + check_mix_cohesion runner.
NO concrete rules yet (rule-with-consumer principle). These tests use a
context-managed registry swap to isolate test-defined rules from the
module-level _RULES list.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Optional

import pytest

from mix_engine.blueprint import (
    MASTER_TRACK_NAME,
    MasteringDecision,
    MasterMove,
    MixBlueprint,
    MixCitation,
    MixCohesionReport,
    MixCohesionViolation,
    MixDecision,
    check_mix_cohesion,
    mix_cohesion_rule,
)
from mix_engine.blueprint import cohesion as cohesion_module


# ============================================================================
# Test isolation — swap _RULES around each test
# ============================================================================


@contextmanager
def _isolated_registry():
    """Temporarily swap the module-level _RULES list with an empty one,
    so a test can register rules via @mix_cohesion_rule without polluting
    the global registry seen by sibling tests."""
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
# Helpers
# ============================================================================


def _mastering_bp() -> MixBlueprint:
    """Minimal MixBlueprint with the mastering lane filled."""
    move = MasterMove(
        type="stereo_enhance",
        target_track=MASTER_TRACK_NAME,
        device="StereoGain",
        chain_position="master_stereo",
        width=1.1,
        rationale=(
            "Causal: cohesion test baseline. Interactional: validates the "
            "@mix_cohesion_rule infrastructure on a real lane."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    decision = MixDecision(
        value=MasteringDecision(moves=(move,)),
        lane="mastering",
        rationale="Cohesion test wrapper.",
        confidence=0.85,
    )
    return MixBlueprint(name="cohesion-test").with_decision("mastering", decision)


# ============================================================================
# Empty registry — baseline
# ============================================================================


def test_empty_registry_returns_clean(isolated_rules):
    bp = MixBlueprint(name="empty")
    report = check_mix_cohesion(bp)
    assert isinstance(report, MixCohesionReport)
    assert report.violations == ()
    assert report.is_clean
    assert report.blockers == ()
    assert report.warnings == ()


# ============================================================================
# Decorator — registration + lane skipping
# ============================================================================


def test_rule_runs_when_required_lanes_filled(isolated_rules):
    @mix_cohesion_rule(lanes=("mastering",))
    def my_rule(bp: MixBlueprint) -> Optional[MixCohesionViolation]:
        return MixCohesionViolation(
            rule="my_rule", severity="warn",
            message="fires whenever mastering is filled", lanes=("mastering",),
        )

    bp = _mastering_bp()
    report = check_mix_cohesion(bp)
    assert len(report.violations) == 1
    assert report.violations[0].rule == "my_rule"
    assert report.is_clean  # warn-only, no block


def test_rule_skipped_when_required_lane_missing(isolated_rules):
    @mix_cohesion_rule(lanes=("mastering",))
    def my_rule(bp: MixBlueprint) -> Optional[MixCohesionViolation]:
        return MixCohesionViolation(
            rule="my_rule", severity="block",
            message="should not fire", lanes=("mastering",),
        )

    bp = MixBlueprint(name="empty")
    report = check_mix_cohesion(bp)
    assert report.violations == ()


def test_rule_skipped_when_any_required_lane_missing(isolated_rules):
    """Rule needs both ``mastering`` AND ``routing`` ; only mastering is filled
    → rule must be silently skipped."""
    @mix_cohesion_rule(lanes=("mastering", "routing"))
    def my_rule(bp: MixBlueprint) -> Optional[MixCohesionViolation]:
        return MixCohesionViolation(
            rule="my_rule", severity="block",
            message="should not fire", lanes=("mastering", "routing"),
        )

    bp = _mastering_bp()
    assert "routing" not in bp.filled_lanes()
    report = check_mix_cohesion(bp)
    assert report.violations == ()


def test_rule_returning_none_emits_no_violation(isolated_rules):
    @mix_cohesion_rule(lanes=("mastering",))
    def cohesive_rule(bp: MixBlueprint) -> Optional[MixCohesionViolation]:
        return None

    bp = _mastering_bp()
    report = check_mix_cohesion(bp)
    assert report.violations == ()


# ============================================================================
# Multiple rules — block + warn semantics
# ============================================================================


def test_multiple_rules_all_run(isolated_rules):
    @mix_cohesion_rule(lanes=("mastering",))
    def rule_a(bp):
        return MixCohesionViolation(
            rule="rule_a", severity="warn",
            message="a", lanes=("mastering",),
        )

    @mix_cohesion_rule(lanes=("mastering",))
    def rule_b(bp):
        return MixCohesionViolation(
            rule="rule_b", severity="block",
            message="b", lanes=("mastering",),
        )

    bp = _mastering_bp()
    report = check_mix_cohesion(bp)
    assert len(report.violations) == 2
    rules_fired = {v.rule for v in report.violations}
    assert rules_fired == {"rule_a", "rule_b"}


def test_block_severity_makes_report_unclean(isolated_rules):
    @mix_cohesion_rule(lanes=("mastering",))
    def block_rule(bp):
        return MixCohesionViolation(
            rule="block_rule", severity="block",
            message="critical", lanes=("mastering",),
        )

    bp = _mastering_bp()
    report = check_mix_cohesion(bp)
    assert not report.is_clean
    assert len(report.blockers) == 1
    assert report.warnings == ()


def test_warn_severity_keeps_report_clean(isolated_rules):
    @mix_cohesion_rule(lanes=("mastering",))
    def warn_rule(bp):
        return MixCohesionViolation(
            rule="warn_rule", severity="warn",
            message="advisory", lanes=("mastering",),
        )

    bp = _mastering_bp()
    report = check_mix_cohesion(bp)
    assert report.is_clean
    assert report.blockers == ()
    assert len(report.warnings) == 1


def test_info_severity_keeps_report_clean(isolated_rules):
    @mix_cohesion_rule(lanes=("mastering",))
    def info_rule(bp):
        return MixCohesionViolation(
            rule="info_rule", severity="info",
            message="fyi", lanes=("mastering",),
        )

    bp = _mastering_bp()
    report = check_mix_cohesion(bp)
    assert report.is_clean
    assert report.blockers == ()
    assert report.warnings == ()


# ============================================================================
# Real-module sanity — Phase 4.19 ships ZERO concrete rules
# ============================================================================


def test_phase_4_19_ships_zero_concrete_rules():
    """Per rule-with-consumer principle, no rule should be registered yet.
    This test will need an update when the first concrete rule lands."""
    # No isolated_rules fixture — we want to inspect the real registry.
    assert cohesion_module._RULES == [], (
        "Phase 4.19 should ship 0 cohesion rules (rule-with-consumer). "
        "If a rule was added, update this test AND the docstring of "
        "cohesion.py to note the first concrete rule's phase."
    )
