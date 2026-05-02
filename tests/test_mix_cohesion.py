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
# Real-module sanity — Phase 4.19.1 registry invariant
# ============================================================================


_EXPECTED_RULES_AT_PHASE_4_19_1 = {
    "sidechain_target_exists_in_routing",
}


def test_real_registry_matches_documented_rule_set():
    """The set of rules registered at module import time must match the
    set documented in cohesion.py's module docstring + the
    `_EXPECTED_RULES_AT_PHASE_4_19_1` constant above. This catches both
    accidental rule deletion AND speculative rule addition without
    updating the docstring."""
    # No isolated_rules fixture — inspect the real registry.
    actual = {r.__name__ for r in cohesion_module._RULES}
    assert actual == _EXPECTED_RULES_AT_PHASE_4_19_1, (
        f"Registered rules drifted from documented set. "
        f"Actual: {actual}. Expected: {_EXPECTED_RULES_AT_PHASE_4_19_1}. "
        f"If you added/removed a rule, update both the docstring of "
        f"cohesion.py AND this test's expected set."
    )


# ============================================================================
# Phase 4.19.1 rule — sidechain_target_exists_in_routing
# ============================================================================


def _dynamics_with_external_sidechain(
    target_track: str = "Bass",
    trigger_track: str = "Kick",
):
    from mix_engine.blueprint import (
        DynamicsCorrection,
        DynamicsCorrectiveDecision,
        SidechainConfig,
    )
    correction = DynamicsCorrection(
        track=target_track,
        dynamics_type="sidechain_duck",
        device="Compressor2",
        threshold_db=-15.0,
        ratio=4.0,
        sidechain=SidechainConfig(
            mode="external",
            trigger_track=trigger_track,
            depth_db=-8.0,
        ),
        rationale=(
            "Causal: Phase 4.19.1 cohesion test fixture — needs an external "
            "sidechain so the rule can compare trigger_track to routing repairs."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    return MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Cohesion test wrapper.",
        confidence=0.85,
    )


def _routing_with_remove(current_trigger: str = "Kick", track: str = "Bass"):
    from mix_engine.blueprint import RoutingDecision, SidechainRepair
    repair = SidechainRepair(
        track=track,
        fix_type="sidechain_remove",
        current_trigger=current_trigger,
        rationale=(
            "Causal: Phase 4.19.1 cohesion test fixture — removes the "
            "sidechain that the dynamics correction depends on."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    return MixDecision(
        value=RoutingDecision(repairs=(repair,)),
        lane="routing",
        rationale="Cohesion test wrapper.",
        confidence=0.85,
    )


def _routing_with_redirect(
    current_trigger: str = "Kick",
    new_trigger: str = "Kick Reinforce",
    track: str = "Bass",
):
    from mix_engine.blueprint import RoutingDecision, SidechainRepair
    repair = SidechainRepair(
        track=track,
        fix_type="sidechain_redirect",
        current_trigger=current_trigger,
        new_trigger=new_trigger,
        rationale=(
            "Causal: redirect away from the stale trigger to a live one. "
            "This should NOT trigger the rule — only sidechain_remove does."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    return MixDecision(
        value=RoutingDecision(repairs=(repair,)),
        lane="routing",
        rationale="Cohesion test wrapper.",
        confidence=0.85,
    )


def test_rule_fires_on_real_contradiction():
    """dynamics says 'duck Bass via Kick' + routing says 'remove Kick
    sidechain on Bass' → block."""
    bp = (
        MixBlueprint(name="contradiction")
        .with_decision("dynamics_corrective",
                       _dynamics_with_external_sidechain("Bass", "Kick"))
        .with_decision("routing", _routing_with_remove("Kick", "Bass"))
    )
    report = check_mix_cohesion(bp)
    blockers = [v for v in report.violations
                if v.rule == "sidechain_target_exists_in_routing"]
    assert len(blockers) == 1
    assert blockers[0].severity == "block"
    assert "Kick" in blockers[0].message
    assert "Bass" in blockers[0].message
    assert blockers[0].lanes == ("dynamics_corrective", "routing")
    assert not report.is_clean


def test_rule_skipped_when_only_dynamics_filled():
    """Rule needs both lanes ; only dynamics → silently skipped."""
    bp = MixBlueprint(name="dyn-only").with_decision(
        "dynamics_corrective",
        _dynamics_with_external_sidechain("Bass", "Kick"),
    )
    report = check_mix_cohesion(bp)
    assert report.violations == ()
    assert report.is_clean


def test_rule_skipped_when_only_routing_filled():
    """Rule needs both lanes ; only routing → silently skipped."""
    bp = MixBlueprint(name="routing-only").with_decision(
        "routing", _routing_with_remove("Kick", "Bass"),
    )
    report = check_mix_cohesion(bp)
    assert report.violations == ()
    assert report.is_clean


def test_rule_does_not_fire_for_internal_sidechain():
    """internal-mode sidechain has no trigger_track to validate → ok."""
    from mix_engine.blueprint import (
        DynamicsCorrection,
        DynamicsCorrectiveDecision,
        SidechainConfig,
    )
    correction = DynamicsCorrection(
        track="Lead Vox",
        dynamics_type="deess",
        device="Compressor2",
        threshold_db=-22.0,
        ratio=3.0,
        sidechain=SidechainConfig(
            mode="internal_filtered",
            filter_freq_hz=6500.0,
            filter_q=1.5,
        ),
        rationale=(
            "Causal: internal-mode sidechain on Lead Vox for de-essing — "
            "no external trigger track, so the rule should not match."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    dynamics = MixDecision(
        value=DynamicsCorrectiveDecision(corrections=(correction,)),
        lane="dynamics_corrective",
        rationale="Cohesion test wrapper.",
        confidence=0.85,
    )
    bp = (
        MixBlueprint(name="internal-sc")
        .with_decision("dynamics_corrective", dynamics)
        .with_decision("routing", _routing_with_remove("Kick", "Bass"))
    )
    report = check_mix_cohesion(bp)
    assert report.violations == ()


def test_rule_does_not_fire_when_remove_targets_different_trigger():
    """dynamics references Kick, routing removes a Hi-Hat sidechain →
    independent, no contradiction."""
    bp = (
        MixBlueprint(name="diff-trigger")
        .with_decision("dynamics_corrective",
                       _dynamics_with_external_sidechain("Bass", "Kick"))
        .with_decision("routing", _routing_with_remove("Hi-Hat", "Pad"))
    )
    report = check_mix_cohesion(bp)
    assert report.violations == ()


def test_rule_does_not_fire_for_sidechain_redirect():
    """sidechain_redirect is the SAFER fix path (rewires to a live
    trigger). Out of scope for v1 of the rule — must not block."""
    bp = (
        MixBlueprint(name="redirect")
        .with_decision("dynamics_corrective",
                       _dynamics_with_external_sidechain("Bass", "Kick"))
        .with_decision("routing", _routing_with_redirect("Kick",
                                                          "Kick Reinforce",
                                                          "Bass"))
    )
    report = check_mix_cohesion(bp)
    assert report.violations == ()
