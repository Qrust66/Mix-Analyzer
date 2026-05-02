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


_EXPECTED_RULES = {
    "sidechain_target_exists_in_routing",        # Phase 4.19.1
    "automation_envelope_targets_active_param",  # Phase 4.19.2
}


def test_real_registry_matches_documented_rule_set():
    """The set of rules registered at module import time must match the
    set documented in cohesion.py's module docstring + the
    `_EXPECTED_RULES` constant above. This catches both accidental rule
    deletion AND speculative rule addition without updating the docstring."""
    # No isolated_rules fixture — inspect the real registry.
    actual = {r.__name__ for r in cohesion_module._RULES}
    assert actual == _EXPECTED_RULES, (
        f"Registered rules drifted from documented set. "
        f"Actual: {actual}. Expected: {_EXPECTED_RULES}. "
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


# ============================================================================
# Phase 4.19.2 rule — automation_envelope_targets_active_param
# ============================================================================


def _envelope(target_track="Kick", target_device="Eq8",
              target_device_instance=0, target_band_index=0,
              target_param="Gain"):
    from mix_engine.blueprint import (
        AutomationEnvelope, AutomationPoint, MixCitation,
    )
    return AutomationEnvelope(
        purpose="corrective_per_section",
        target_track=target_track,
        target_device=target_device,
        target_device_instance=target_device_instance,
        target_band_index=target_band_index,
        target_param=target_param,
        points=(
            AutomationPoint(time_beats=0.0, value=0.0),
            AutomationPoint(time_beats=4.0, value=-2.0),
            AutomationPoint(time_beats=8.0, value=0.0),
        ),
        sections=(0, 1, 2),
        rationale=(
            "Causal: Phase 4.19.2 cohesion test fixture — envelope used to "
            "check the chain plan reachability rule on the matching track."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )


def _band_track(target_track="Kick", target_eq8_instance=0,
                target_band_index=0):
    from mix_engine.blueprint import BandTrack, MixCitation
    return BandTrack(
        target_track=target_track,
        target_eq8_instance=target_eq8_instance,
        target_band_index=target_band_index,
        band_mode="bell",
        purpose="follow_peak",
        frame_times_sec=(0.0, 0.5, 1.0),
        freqs_hz=(3000.0, 3050.0, 3080.0),
        gains_db=(-3.0, -4.0, -3.5),
        q_values=(8.0, 8.5, 9.0),
        rationale=(
            "Causal: Phase 4.19.2 cohesion test fixture — BandTrack used to "
            "check the chain plan reachability rule for Eq8 instances."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )


def _automation(envelopes=(), band_tracks=()):
    from mix_engine.blueprint import AutomationDecision
    return MixDecision(
        value=AutomationDecision(envelopes=envelopes, band_tracks=band_tracks),
        lane="automation",
        rationale="Cohesion test wrapper.",
        confidence=0.85,
    )


def _chain_plan(track="Kick", devices_with_instances=(("Eq8", 0),)):
    """Build a TrackChainPlan for `track` with the listed (device, instance)
    pairs. Each pair becomes one slot at strictly ascending positions."""
    from mix_engine.blueprint import (
        ChainBuildDecision, ChainSlot, MixCitation, TrackChainPlan,
    )
    slots = tuple(
        ChainSlot(
            position=i,
            device=dev,
            instance=inst,
            is_preexisting=True,
        )
        for i, (dev, inst) in enumerate(devices_with_instances)
    )
    plan = TrackChainPlan(
        track=track,
        slots=slots,
        rationale=(
            "Causal: Phase 4.19.2 cohesion test fixture — chain plan used to "
            "validate automation envelope reachability against present devices."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    return MixDecision(
        value=ChainBuildDecision(plans=(plan,)),
        lane="chain",
        rationale="Cohesion test wrapper.",
        confidence=0.85,
    )


def test_automation_rule_fires_when_target_device_absent_from_plan():
    """Envelope targets Compressor2 on Kick, but chain plan only has Eq8."""
    bp = (
        MixBlueprint(name="bad-device")
        .with_decision(
            "automation",
            _automation(envelopes=(_envelope(
                target_device="Compressor2", target_band_index=None,
                target_param="Threshold",
            ),)),
        )
        .with_decision("chain", _chain_plan("Kick", (("Eq8", 0),)))
    )
    report = check_mix_cohesion(bp)
    blockers = [v for v in report.violations
                if v.rule == "automation_envelope_targets_active_param"]
    assert len(blockers) == 1
    assert "Compressor2" in blockers[0].message
    assert "no Compressor2 slot" in blockers[0].message
    assert not report.is_clean


def test_automation_rule_fires_when_instance_overflow():
    """Envelope targets Eq8 instance 2, chain plan has only instance 0."""
    bp = (
        MixBlueprint(name="instance-overflow")
        .with_decision(
            "automation",
            _automation(envelopes=(_envelope(target_device_instance=2),)),
        )
        .with_decision("chain", _chain_plan("Kick", (("Eq8", 0),)))
    )
    report = check_mix_cohesion(bp)
    blockers = [v for v in report.violations
                if v.rule == "automation_envelope_targets_active_param"]
    assert len(blockers) == 1
    assert "Eq8#2" in blockers[0].message
    assert "instance(s) [0]" in blockers[0].message


def test_automation_rule_fires_for_band_track_missing_eq8_instance():
    """BandTrack targets Eq8 instance 1, chain plan has only instance 0."""
    bp = (
        MixBlueprint(name="bt-overflow")
        .with_decision(
            "automation",
            _automation(band_tracks=(_band_track(target_eq8_instance=1),)),
        )
        .with_decision("chain", _chain_plan("Kick", (("Eq8", 0),)))
    )
    report = check_mix_cohesion(bp)
    blockers = [v for v in report.violations
                if v.rule == "automation_envelope_targets_active_param"]
    assert len(blockers) == 1
    assert "BandTrack" in blockers[0].message
    assert "Eq8#1" in blockers[0].message


def test_automation_rule_skipped_when_only_automation_filled():
    """Rule needs both lanes ; only automation → silently skipped."""
    bp = MixBlueprint(name="auto-only").with_decision(
        "automation",
        _automation(envelopes=(_envelope(target_device_instance=2),)),
    )
    report = check_mix_cohesion(bp)
    auto_blockers = [v for v in report.violations
                     if v.rule == "automation_envelope_targets_active_param"]
    assert auto_blockers == []


def test_automation_rule_does_not_fire_when_envelope_matches_plan():
    """Envelope targets Eq8 instance 0, chain plan has Eq8 instance 0 → ok."""
    bp = (
        MixBlueprint(name="happy")
        .with_decision("automation",
                       _automation(envelopes=(_envelope(),)))
        .with_decision("chain", _chain_plan("Kick", (("Eq8", 0),)))
    )
    report = check_mix_cohesion(bp)
    auto_blockers = [v for v in report.violations
                     if v.rule == "automation_envelope_targets_active_param"]
    assert auto_blockers == []


def test_automation_rule_skips_master_target_track():
    """target_track=='Master' is not in chain.plans (handled by mastering
    writer) — rule must skip without raising even if no Master plan exists."""
    bp = (
        MixBlueprint(name="master-env")
        .with_decision("automation", _automation(envelopes=(_envelope(
            target_track="Master", target_device="Limiter",
            target_band_index=None, target_param="Ceiling",
        ),)))
        .with_decision("chain", _chain_plan("Kick", (("Eq8", 0),)))
    )
    report = check_mix_cohesion(bp)
    auto_blockers = [v for v in report.violations
                     if v.rule == "automation_envelope_targets_active_param"]
    assert auto_blockers == []


def test_automation_rule_skips_track_without_chain_plan():
    """When target_track has no entry in chain.plans, the rule defers to
    runtime (envelope may target a pre-existing device the .als has but
    chain-builder didn't decide on)."""
    bp = (
        MixBlueprint(name="no-plan-for-track")
        .with_decision("automation", _automation(envelopes=(_envelope(
            target_track="Vox",  # Vox has no chain plan below
        ),)))
        .with_decision("chain", _chain_plan("Kick", (("Eq8", 0),)))
    )
    report = check_mix_cohesion(bp)
    auto_blockers = [v for v in report.violations
                     if v.rule == "automation_envelope_targets_active_param"]
    assert auto_blockers == []
