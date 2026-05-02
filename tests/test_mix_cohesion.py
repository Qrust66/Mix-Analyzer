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
    "chain_order_respects_signal_flow",          # Phase 4.19.3
    "master_ceiling_below_minus_03_dbtp",        # Phase 4.19.4
    "eq_cuts_redundant_across_tracks",           # Phase 4.19.5 (renamed
                                                  # from the audio-incorrect
                                                  # "phase_holes" name)
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


# ============================================================================
# Phase 4.19.3 rule — chain_order_respects_signal_flow
# ============================================================================


def _chain_with_slots(track: str, slots_spec):
    """Build a chain MixDecision from a list of (device, instance,
    is_preexisting, consumes_lane) tuples. consumes_indices defaults
    to (0,) when consumes_lane is set, () when None."""
    from mix_engine.blueprint import (
        ChainBuildDecision, ChainSlot, MixCitation, TrackChainPlan,
    )
    slots = tuple(
        ChainSlot(
            position=i,
            device=dev,
            instance=inst,
            is_preexisting=preex,
            consumes_lane=lane,
            consumes_indices=(0,) if lane is not None else (),
        )
        for i, (dev, inst, preex, lane) in enumerate(slots_spec)
    )
    plan = TrackChainPlan(
        track=track,
        slots=slots,
        rationale=(
            "Causal: Phase 4.19.3 cohesion test fixture — chain plan used to "
            "validate signal-flow conventions on corrective EQ vs compressor."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    return MixDecision(
        value=ChainBuildDecision(plans=(plan,)),
        lane="chain",
        rationale="Cohesion test wrapper.",
        confidence=0.85,
    )


def test_chain_order_warns_when_corrective_eq_after_compressor():
    """Compressor2 at slot 0 + corrective Eq8 at slot 1 → warn."""
    bp = MixBlueprint(name="bad-flow").with_decision(
        "chain",
        _chain_with_slots("Bass", [
            ("Compressor2", 0, False, "dynamics_corrective"),
            ("Eq8",         0, False, "eq_corrective"),
        ]),
    )
    report = check_mix_cohesion(bp)
    warns = [v for v in report.violations
             if v.rule == "chain_order_respects_signal_flow"]
    assert len(warns) == 1
    assert warns[0].severity == "warn"
    assert "position(s) [1]" in warns[0].message
    assert "position 0" in warns[0].message
    # Warn-only does not unclean the report
    assert report.is_clean


def test_chain_order_silent_when_eq_before_compressor():
    """Eq8 at slot 0 + Compressor2 at slot 1 → canonical, no warn."""
    bp = MixBlueprint(name="canonical-flow").with_decision(
        "chain",
        _chain_with_slots("Bass", [
            ("Eq8",         0, False, "eq_corrective"),
            ("Compressor2", 0, False, "dynamics_corrective"),
        ]),
    )
    report = check_mix_cohesion(bp)
    warns = [v for v in report.violations
             if v.rule == "chain_order_respects_signal_flow"]
    assert warns == []


def test_chain_order_skips_preexisting_eq():
    """A pre-existing Eq8 at slot 1 (after a comp at slot 0) should NOT
    trigger the rule — we don't know its semantic role."""
    bp = MixBlueprint(name="preexisting-eq").with_decision(
        "chain",
        _chain_with_slots("Bass", [
            ("Compressor2", 0, False, "dynamics_corrective"),
            ("Eq8",         0, True,  None),  # pre-existing, lane unknown
        ]),
    )
    report = check_mix_cohesion(bp)
    warns = [v for v in report.violations
             if v.rule == "chain_order_respects_signal_flow"]
    assert warns == []


def test_chain_order_skips_creative_eq_after_compressor():
    """An Eq8 with consumes_lane=='eq_creative' AFTER a comp is a
    legitimate flavour move — don't warn."""
    bp = MixBlueprint(name="creative-eq").with_decision(
        "chain",
        _chain_with_slots("Bass", [
            ("Compressor2", 0, False, "dynamics_corrective"),
            ("Eq8",         0, False, "eq_creative"),
        ]),
    )
    report = check_mix_cohesion(bp)
    warns = [v for v in report.violations
             if v.rule == "chain_order_respects_signal_flow"]
    assert warns == []


def test_chain_order_skipped_when_chain_lane_absent():
    """Single-lane rule still respects the lane-skipping contract : if
    chain isn't filled, rule must not run."""
    bp = MixBlueprint(name="no-chain")
    report = check_mix_cohesion(bp)
    warns = [v for v in report.violations
             if v.rule == "chain_order_respects_signal_flow"]
    assert warns == []


def test_chain_order_handles_glue_compressor_too():
    """GlueCompressor counts as a compressor for this rule, same as
    Compressor2."""
    bp = MixBlueprint(name="glue-flow").with_decision(
        "chain",
        _chain_with_slots("Drum Bus", [
            ("GlueCompressor", 0, False, "dynamics_corrective"),
            ("Eq8",            0, False, "eq_corrective"),
        ]),
    )
    report = check_mix_cohesion(bp)
    warns = [v for v in report.violations
             if v.rule == "chain_order_respects_signal_flow"]
    assert len(warns) == 1
    assert "Drum Bus" in warns[0].message


# ============================================================================
# Phase 4.19.4 rule — master_ceiling_below_minus_03_dbtp
# ============================================================================


def _mastering_with_limiter(ceiling_dbtp: float = -0.4):
    move = MasterMove(
        type="limiter_target",
        target_track=MASTER_TRACK_NAME,
        device="Limiter",
        chain_position="master_dynamics",
        target_lufs_i=-14.0,
        ceiling_dbtp=ceiling_dbtp,
        rationale=(
            "Causal: Phase 4.19.4 cohesion test fixture — sets a streaming "
            "limiter target at the configured ceiling for ceiling-rule check."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    return MixDecision(
        value=MasteringDecision(moves=(move,)),
        lane="mastering",
        rationale="Cohesion test wrapper.",
        confidence=0.85,
    )


def test_master_ceiling_blocks_at_minus_02():
    """ceiling_dbtp=-0.2 > -0.3 → block."""
    bp = MixBlueprint(name="too-loud").with_decision(
        "mastering", _mastering_with_limiter(ceiling_dbtp=-0.2),
    )
    report = check_mix_cohesion(bp)
    blockers = [v for v in report.violations
                if v.rule == "master_ceiling_below_minus_03_dbtp"]
    assert len(blockers) == 1
    assert blockers[0].severity == "block"
    assert "-0.2" in blockers[0].message
    assert "streaming-safe" in blockers[0].message
    assert "--force" in blockers[0].message
    assert not report.is_clean


def test_master_ceiling_silent_at_minus_05():
    """ceiling_dbtp=-0.5 <= -0.3 → no block."""
    bp = MixBlueprint(name="safe").with_decision(
        "mastering", _mastering_with_limiter(ceiling_dbtp=-0.5),
    )
    report = check_mix_cohesion(bp)
    blockers = [v for v in report.violations
                if v.rule == "master_ceiling_below_minus_03_dbtp"]
    assert blockers == []


def test_master_ceiling_silent_exactly_at_minus_03_boundary():
    """ceiling_dbtp=-0.3 (boundary) → no block ; rule uses strict >."""
    bp = MixBlueprint(name="boundary").with_decision(
        "mastering", _mastering_with_limiter(ceiling_dbtp=-0.3),
    )
    report = check_mix_cohesion(bp)
    blockers = [v for v in report.violations
                if v.rule == "master_ceiling_below_minus_03_dbtp"]
    assert blockers == []


def test_master_ceiling_skipped_when_no_limiter_target_move():
    """A mastering decision with only stereo_enhance moves (no
    limiter_target) is not in scope of this rule."""
    bp = _mastering_bp()  # uses stereo_enhance, NO limiter_target
    report = check_mix_cohesion(bp)
    blockers = [v for v in report.violations
                if v.rule == "master_ceiling_below_minus_03_dbtp"]
    assert blockers == []


def test_master_ceiling_skipped_when_ceiling_dbtp_is_none():
    """limiter_target with ceiling_dbtp=None (Tier B picks default) is
    not flagged — there's no ceiling to validate."""
    move = MasterMove(
        type="limiter_target",
        target_track=MASTER_TRACK_NAME,
        device="Limiter",
        chain_position="master_dynamics",
        target_lufs_i=-14.0,
        ceiling_dbtp=None,  # explicit None
        rationale=(
            "Causal: Phase 4.19.4 cohesion test fixture — limiter without "
            "explicit ceiling_dbtp ; Tier B picks the default."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    decision = MixDecision(
        value=MasteringDecision(moves=(move,)),
        lane="mastering",
        rationale="Cohesion test wrapper.",
        confidence=0.85,
    )
    bp = MixBlueprint(name="ceiling-none").with_decision("mastering", decision)
    report = check_mix_cohesion(bp)
    blockers = [v for v in report.violations
                if v.rule == "master_ceiling_below_minus_03_dbtp"]
    assert blockers == []


def test_master_ceiling_skipped_when_mastering_lane_absent():
    """Single-lane rule still respects the lane-skipping contract."""
    bp = MixBlueprint(name="no-mastering")
    report = check_mix_cohesion(bp)
    blockers = [v for v in report.violations
                if v.rule == "master_ceiling_below_minus_03_dbtp"]
    assert blockers == []


# ============================================================================
# Phase 4.19.5 rule — eq_cuts_redundant_across_tracks
# (renamed from the audio-incorrect "phase_holes_with_neighbours")
# ============================================================================


def _eq_band(track: str, center_hz: float, gain_db: float,
             intent: str = "cut", band_type: str = "bell", q: float = 1.5):
    from mix_engine.blueprint import EQBandCorrection
    return EQBandCorrection(
        track=track,
        band_type=band_type,
        intent=intent,
        center_hz=center_hz,
        q=q,
        gain_db=gain_db,
        chain_position="default",
        rationale=(
            "Causal: Phase 4.19.5 cohesion test fixture — band crafted to land "
            "in or out of the redundant-cluster detection window."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )


def _eq_corrective(*bands):
    from mix_engine.blueprint import EQCorrectiveDecision
    return MixDecision(
        value=EQCorrectiveDecision(bands=tuple(bands)),
        lane="eq_corrective",
        rationale="Cohesion test wrapper.",
        confidence=0.85,
    )


def test_redundant_cuts_warns_on_two_tracks_same_freq_band():
    """Track A cuts -6 dB at 250 Hz, Track B cuts -6 dB at 245 Hz : both
    bands fall in the same 1/3-octave window → warn."""
    bp = MixBlueprint(name="redundant").with_decision(
        "eq_corrective",
        _eq_corrective(
            _eq_band("Bass",     center_hz=250.0, gain_db=-6.0),
            _eq_band("Synth Pad", center_hz=245.0, gain_db=-6.0),
        ),
    )
    report = check_mix_cohesion(bp)
    warns = [v for v in report.violations
             if v.rule == "eq_cuts_redundant_across_tracks"]
    assert len(warns) == 1
    assert warns[0].severity == "warn"
    assert "Bass" in warns[0].message and "Synth Pad" in warns[0].message
    assert "single bus EQ cut" in warns[0].message
    # The message must NOT use the audio-incorrect "phase hole" terminology
    assert "phase hole" not in warns[0].message.lower()
    assert report.is_clean  # warns don't unclean


def test_redundant_cuts_warns_on_three_tracks():
    """3 tracks all cut around 250 Hz → cluster of 3 → warn."""
    bp = MixBlueprint(name="three-tracks").with_decision(
        "eq_corrective",
        _eq_corrective(
            _eq_band("Bass",      center_hz=250.0, gain_db=-5.0),
            _eq_band("Synth Pad",  center_hz=240.0, gain_db=-4.0),
            _eq_band("Lead Vox",   center_hz=260.0, gain_db=-6.0),
        ),
    )
    report = check_mix_cohesion(bp)
    warns = [v for v in report.violations
             if v.rule == "eq_cuts_redundant_across_tracks"]
    assert len(warns) == 1
    assert "3 tracks" in warns[0].message


def test_redundant_cuts_silent_when_freqs_more_than_third_octave_apart():
    """Track A at 250 Hz, Track B at 400 Hz → ratio 1.6 > 1.26 → no warn."""
    bp = MixBlueprint(name="far-apart").with_decision(
        "eq_corrective",
        _eq_corrective(
            _eq_band("Bass",     center_hz=250.0, gain_db=-6.0),
            _eq_band("Synth Pad", center_hz=400.0, gain_db=-6.0),
        ),
    )
    report = check_mix_cohesion(bp)
    warns = [v for v in report.violations
             if v.rule == "eq_cuts_redundant_across_tracks"]
    assert warns == []


def test_redundant_cuts_silent_when_cuts_too_shallow():
    """Two -2 dB cuts → below -3 dB perceptual threshold → no warn."""
    bp = MixBlueprint(name="shallow").with_decision(
        "eq_corrective",
        _eq_corrective(
            _eq_band("Bass",     center_hz=250.0, gain_db=-2.0),
            _eq_band("Synth Pad", center_hz=245.0, gain_db=-2.0),
        ),
    )
    report = check_mix_cohesion(bp)
    warns = [v for v in report.violations
             if v.rule == "eq_cuts_redundant_across_tracks"]
    assert warns == []


def test_redundant_cuts_silent_for_same_track_pair():
    """Two cuts on the SAME track → not a cross-track cluster, no warn."""
    bp = MixBlueprint(name="same-track").with_decision(
        "eq_corrective",
        _eq_corrective(
            _eq_band("Bass", center_hz=250.0, gain_db=-6.0),
            _eq_band("Bass", center_hz=245.0, gain_db=-6.0, q=2.5),
        ),
    )
    report = check_mix_cohesion(bp)
    warns = [v for v in report.violations
             if v.rule == "eq_cuts_redundant_across_tracks"]
    assert warns == []


def test_redundant_cuts_silent_when_one_band_is_boost():
    """Track A boosts (+4 dB) at 250 Hz, Track B cuts (-6 dB) at 245 Hz.
    Boost has intent='boost' → filtered out → cluster has 1 cut from 1
    track → no warn."""
    bp = MixBlueprint(name="boost-vs-cut").with_decision(
        "eq_corrective",
        _eq_corrective(
            _eq_band("Bass",     center_hz=250.0, gain_db=4.0,  intent="boost"),
            _eq_band("Synth Pad", center_hz=245.0, gain_db=-6.0, intent="cut"),
        ),
    )
    report = check_mix_cohesion(bp)
    warns = [v for v in report.violations
             if v.rule == "eq_cuts_redundant_across_tracks"]
    assert warns == []


def test_redundant_cuts_silent_for_shelf_band_types():
    """Two high_shelf cuts → out of v1 scope (only bell). No warn."""
    bp = MixBlueprint(name="shelves").with_decision(
        "eq_corrective",
        _eq_corrective(
            _eq_band("Bass",     center_hz=250.0, gain_db=-6.0,
                     band_type="high_shelf"),
            _eq_band("Synth Pad", center_hz=245.0, gain_db=-6.0,
                     band_type="high_shelf"),
        ),
    )
    report = check_mix_cohesion(bp)
    warns = [v for v in report.violations
             if v.rule == "eq_cuts_redundant_across_tracks"]
    assert warns == []


def test_redundant_cuts_skipped_when_eq_corrective_lane_absent():
    bp = MixBlueprint(name="no-eq")
    report = check_mix_cohesion(bp)
    warns = [v for v in report.violations
             if v.rule == "eq_cuts_redundant_across_tracks"]
    assert warns == []
