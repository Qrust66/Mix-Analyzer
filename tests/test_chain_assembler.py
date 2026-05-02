"""Tests for mix_engine.writers.chain_assembler (Phase 4.16).

Phase 4.16 v1 scope :
- Reorder existing children of <DeviceChain/Devices> to match plan.slots
- REUSE-only : no device creation
- Idempotency : re-apply same plan → no-op
- Extras (children not in plan) preserved at end with warning
- Multi-instance disambiguation by ``instance`` field

Reference fixture has tracks like :
- BUS Kick : [PluginDevice, GlueCompressor, Limiter]
- [H/M] Acid Bass : 10-device chain mixing Eq8/Glue/Limiter/PluginDevice/StereoGain
- [H/R] Kick 1 : single Eq8 (degenerate chain, good for empty/no-op tests)
"""
from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import als_utils
from mix_engine.blueprint import (
    ChainBuildDecision,
    ChainSlot,
    MixCitation,
    MixDecision,
    TrackChainPlan,
)
from mix_engine.writers import (
    ChainAssemblerError,
    ChainAssemblerReport,
    apply_chain_decision,
)
from mix_engine.writers.chain_assembler import (
    _build_target_order,
    _find_devices_container,
    _run_safety_checks,
    _slot_id,
)


_REF_ALS = Path(__file__).parent / "fixtures" / "reference_project.als"


# ============================================================================
# Builders
# ============================================================================


def _slot(
    position: int,
    device: str,
    *,
    is_preexisting: bool = False,
    instance: int = 0,
    consumes_lane: str | None = "eq_corrective",
    consumes_indices: tuple[int, ...] = (0,),
    purpose: str = "test",
) -> ChainSlot:
    if is_preexisting:
        return ChainSlot(
            position=position,
            device=device,
            is_preexisting=True,
            instance=instance,
            consumes_lane=None,
            consumes_indices=(),
            purpose=purpose,
        )
    return ChainSlot(
        position=position,
        device=device,
        is_preexisting=False,
        instance=instance,
        consumes_lane=consumes_lane,
        consumes_indices=consumes_indices,
        purpose=purpose,
    )


def _plan(track: str, *slots: ChainSlot) -> TrackChainPlan:
    return TrackChainPlan(
        track=track,
        slots=tuple(slots),
        rationale=(
            "Causal: chain-assembler test fixture. Interactional: validates "
            "Phase 4.16 reorder logic on reference .als project structure."
        ),
        inspired_by=(
            MixCitation(
                kind="als_state",
                path=f"tracks[{track}].devices",
                excerpt="test",
            ),
        ),
    )


def _decision(*plans: TrackChainPlan) -> MixDecision[ChainBuildDecision]:
    return MixDecision(
        value=ChainBuildDecision(plans=tuple(plans)),
        lane="chain",
        rationale="Chain assembler test wrapper.",
        confidence=0.85,
    )


def _read_chain_tags(als_path: Path, track_name: str) -> list[str]:
    tree = als_utils.parse_als(str(als_path))
    track_el = als_utils.find_track_by_name(tree, track_name)
    container = _find_devices_container(track_el)
    return [c.tag for c in container] if container is not None else []


# ============================================================================
# Helper unit tests — _build_target_order
# ============================================================================


def _make_devices(*tags: str) -> list[ET.Element]:
    return [ET.SubElement(ET.Element("Devices"), t) for t in tags]


def test_build_target_order_simple_reorder():
    """Plan asks for Limiter, GlueCompressor, PluginDevice ; chain has them
    in original order PluginDevice, GlueCompressor, Limiter — full swap."""
    children = _make_devices("PluginDevice", "GlueCompressor", "Limiter")
    plan = _plan(
        "Bus",
        _slot(0, "Limiter", consumes_lane="dynamics_corrective"),
        _slot(1, "GlueCompressor", consumes_lane="dynamics_corrective"),
        _slot(2, "PluginDevice", is_preexisting=True),
    )
    new_order, unmatched, extras = _build_target_order(children, plan)
    assert [c.tag for c in new_order] == ["Limiter", "GlueCompressor", "PluginDevice"]
    assert unmatched == []
    assert extras == []


def test_build_target_order_unmatched_slot():
    """Plan requests a Saturator that the chain doesn't have."""
    children = _make_devices("Eq8", "Compressor2")
    plan = _plan(
        "T",
        _slot(0, "Eq8"),
        _slot(1, "Saturator"),  # not in chain
    )
    new_order, unmatched, extras = _build_target_order(children, plan)
    assert [c.tag for c in new_order] == ["Eq8", "Compressor2"]
    assert len(unmatched) == 1
    assert "Saturator" in unmatched[0][1]
    assert ("T", "Compressor2") in extras  # Compressor2 not claimed → extra


def test_build_target_order_multi_instance_eq8():
    """Two Eq8 in chain ; plan claims them in reverse instance order."""
    children = _make_devices("Eq8", "GlueCompressor", "Eq8")
    eq8_first, glue, eq8_second = children
    plan = _plan(
        "T",
        _slot(0, "Eq8", instance=1),  # claims the second one first
        _slot(1, "GlueCompressor", consumes_lane="dynamics_corrective"),
        _slot(2, "Eq8", instance=0),  # claims the first one last
    )
    new_order, unmatched, extras = _build_target_order(children, plan)
    assert new_order[0] is eq8_second
    assert new_order[1] is glue
    assert new_order[2] is eq8_first
    assert unmatched == []
    assert extras == []


def test_build_target_order_extras_preserved_at_end():
    """Plan only references 1 of 3 children ; the other 2 land at the end
    in original relative order."""
    children = _make_devices("Reverb", "Eq8", "Tuner")
    reverb, eq8, tuner = children
    plan = _plan(
        "T",
        _slot(0, "Eq8"),
    )
    new_order, unmatched, extras = _build_target_order(children, plan)
    assert new_order[0] is eq8
    assert new_order[1] is reverb
    assert new_order[2] is tuner
    assert ("T", "Reverb") in extras
    assert ("T", "Tuner") in extras


def test_build_target_order_instance_too_high():
    """Plan asks for Eq8 instance=2 but chain only has 1."""
    children = _make_devices("Eq8")
    plan = _plan("T", _slot(0, "Eq8", instance=2))
    new_order, unmatched, extras = _build_target_order(children, plan)
    assert [c.tag for c in new_order] == ["Eq8"]
    assert len(unmatched) == 1
    assert "instance=2" in unmatched[0][1]


def test_slot_id_format():
    s = _slot(3, "Eq8", instance=1)
    assert _slot_id("BassA", s) == "BassA:Eq8#1@pos3"


# ============================================================================
# Empty + smoke
# ============================================================================


def test_empty_plans_no_op(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    report = apply_chain_decision(ref_copy, _decision())
    assert isinstance(report, ChainAssemblerReport)
    assert report.plans_applied == ()
    assert report.devices_reordered == 0


def test_track_not_found_raises(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    plan = _plan("NonexistentTrack", _slot(0, "Eq8"))
    with pytest.raises(ValueError, match="No track named"):
        apply_chain_decision(ref_copy, _decision(plan), dry_run=True)


# ============================================================================
# Reorder happy path on real fixture
# ============================================================================


def test_reorder_bus_kick_swaps_glue_and_limiter(tmp_path):
    """BUS Kick chain : [PluginDevice, GlueCompressor, Limiter].
    Plan asks for [PluginDevice, Limiter, GlueCompressor] — Limiter to slot 1,
    GlueCompressor terminal."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    pre = _read_chain_tags(ref_copy, "BUS Kick")
    assert pre == ["PluginDevice", "GlueCompressor", "Limiter"]

    plan = _plan(
        "BUS Kick",
        _slot(0, "PluginDevice", is_preexisting=True),
        _slot(1, "Limiter", consumes_lane="dynamics_corrective"),
        _slot(2, "GlueCompressor", consumes_lane="dynamics_corrective"),
    )
    report = apply_chain_decision(
        ref_copy, _decision(plan), output_path=output,
        invoke_safety_guardian=False,  # safety expects Limiter terminal — see dedicated test
    )
    assert "BUS Kick" in report.plans_applied
    assert report.devices_reordered >= 2

    post = _read_chain_tags(output, "BUS Kick")
    assert post == ["PluginDevice", "Limiter", "GlueCompressor"]


def test_idempotency_second_apply_no_op(tmp_path):
    """Apply same plan twice : second run yields no_op (chain already ordered)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    plan = _plan(
        "BUS Kick",
        _slot(0, "PluginDevice", is_preexisting=True),
        _slot(1, "GlueCompressor", consumes_lane="dynamics_corrective"),
        _slot(2, "Limiter", consumes_lane="dynamics_corrective"),
    )

    # First apply : already in target order → no_op
    r1 = apply_chain_decision(
        ref_copy, _decision(plan), invoke_safety_guardian=False,
    )
    assert "BUS Kick" in r1.plans_no_op
    assert r1.devices_reordered == 0

    # Second apply : still no_op
    r2 = apply_chain_decision(
        ref_copy, _decision(plan), invoke_safety_guardian=False,
    )
    assert "BUS Kick" in r2.plans_no_op
    assert r2.devices_reordered == 0


def test_extras_preserved_warning(tmp_path):
    """Plan references only the Eq8 of [H/R] Kick 1 ; chain has only Eq8.
    Plan with subset of devices → still no_op when chain matches first slot
    and there are no extras. Use BUS Kick subset case instead :
    plan only [GlueCompressor] → PluginDevice + Limiter become extras."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    plan = _plan(
        "BUS Kick",
        _slot(0, "GlueCompressor", consumes_lane="dynamics_corrective"),
    )
    report = apply_chain_decision(
        ref_copy, _decision(plan), output_path=output,
        invoke_safety_guardian=False,
    )

    extras_tags = {tag for _, tag in report.extras_preserved}
    assert "PluginDevice" in extras_tags
    assert "Limiter" in extras_tags

    post = _read_chain_tags(output, "BUS Kick")
    # GlueCompressor first (claimed by slot 0), then extras in original order
    assert post[0] == "GlueCompressor"
    assert post[1:] == ["PluginDevice", "Limiter"]

    # Warning emitted for each extra
    extra_warnings = [w for w in report.warnings if "preserved at end" in w]
    assert len(extra_warnings) >= 2


def test_unmatched_slot_skipped(tmp_path):
    """Plan asks for Saturator on BUS Kick which has none → unmatched, no crash."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    plan = _plan(
        "BUS Kick",
        _slot(0, "PluginDevice", is_preexisting=True),
        _slot(1, "Saturator", consumes_lane="dynamics_corrective"),
        _slot(2, "GlueCompressor", consumes_lane="dynamics_corrective"),
        _slot(3, "Limiter", consumes_lane="dynamics_corrective"),
    )
    report = apply_chain_decision(
        ref_copy, _decision(plan), dry_run=True, invoke_safety_guardian=False,
    )
    assert len(report.slots_unmatched) == 1
    slot_id, reason = report.slots_unmatched[0]
    assert "Saturator" in slot_id
    assert "0 'Saturator' device(s)" in reason


def test_duplicate_plan_for_same_track_skipped(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    plan_a = _plan("BUS Kick", _slot(0, "PluginDevice", is_preexisting=True))
    plan_b = _plan("BUS Kick", _slot(0, "Limiter", consumes_lane="dynamics_corrective"))
    report = apply_chain_decision(
        ref_copy, _decision(plan_a, plan_b),
        dry_run=True, invoke_safety_guardian=False,
    )
    skipped_reasons = {tr: r for tr, r in report.plans_skipped}
    assert "BUS Kick" in skipped_reasons
    assert "duplicate plan" in skipped_reasons["BUS Kick"]


# ============================================================================
# Multi-instance Eq8 on real fixture
# ============================================================================


def test_multi_instance_eq8_synthetic(tmp_path):
    """Acid Bass has 1 Eq8 in fixture. We add a second Eq8 child manually
    to validate the multi-instance path on real .als XML structure."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    # Inject a second Eq8 element directly (simulating eq8-configurator
    # cascade output) before chain-assembler runs.
    tree = als_utils.parse_als(str(ref_copy))
    track_el = als_utils.find_track_by_name(tree, "[H/M] Acid Bass")
    container = _find_devices_container(track_el)
    assert container is not None
    new_eq8 = ET.SubElement(container, "Eq8")
    new_eq8.set("Id", "999999")
    als_utils.save_als_from_tree(tree, str(ref_copy))

    pre = _read_chain_tags(ref_copy, "[H/M] Acid Bass")
    assert pre.count("Eq8") == 2

    # Plan : keep both Eq8 but swap their order. Don't try to enumerate
    # all 10 devices ; just claim the 2 Eq8 + Limiter and let extras land at end.
    plan = _plan(
        "[H/M] Acid Bass",
        _slot(0, "Eq8", instance=1),  # the appended one comes first
        _slot(1, "Eq8", instance=0),  # the original one second
        _slot(2, "Limiter", consumes_lane="dynamics_corrective"),
    )
    output = tmp_path / "out.als"
    report = apply_chain_decision(
        ref_copy, _decision(plan), output_path=output,
        invoke_safety_guardian=False,
    )
    assert "[H/M] Acid Bass" in report.plans_applied

    post = _read_chain_tags(output, "[H/M] Acid Bass")
    assert post[0] == "Eq8"
    assert post[1] == "Eq8"
    assert post[2] == "Limiter"
    # Verify Id-level identity : appended Eq8 (Id=999999) is now first
    tree_post = als_utils.parse_als(str(output))
    track_post = als_utils.find_track_by_name(tree_post, "[H/M] Acid Bass")
    eq8s = list(_find_devices_container(track_post))[:2]
    assert eq8s[0].get("Id") == "999999"


# ============================================================================
# Dry-run does not mutate
# ============================================================================


def test_dry_run_does_not_mutate(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    pre = _read_chain_tags(ref_copy, "BUS Kick")

    plan = _plan(
        "BUS Kick",
        _slot(0, "Limiter", consumes_lane="dynamics_corrective"),
        _slot(1, "GlueCompressor", consumes_lane="dynamics_corrective"),
        _slot(2, "PluginDevice", is_preexisting=True),
    )
    report = apply_chain_decision(ref_copy, _decision(plan), dry_run=True)
    assert "BUS Kick" in report.plans_applied  # would-be-applied
    # File unchanged
    post = _read_chain_tags(ref_copy, "BUS Kick")
    assert post == pre


# ============================================================================
# Safety guardian
# ============================================================================


def test_safety_guardian_pass_after_correct_reorder(tmp_path):
    """Reorder BUS Kick legitimately ; safety guardian PASS expected."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    plan = _plan(
        "BUS Kick",
        _slot(0, "PluginDevice", is_preexisting=True),
        _slot(1, "GlueCompressor", consumes_lane="dynamics_corrective"),
        _slot(2, "Limiter", consumes_lane="dynamics_corrective"),
    )
    report = apply_chain_decision(
        ref_copy, _decision(plan), output_path=output,
        invoke_safety_guardian=True,
    )
    assert report.safety_guardian_status == "PASS"


def test_safety_guardian_directly():
    """Run _run_safety_checks on the raw fixture (no mutation) — should PASS
    given the fixture is a valid Ableton project and no plans means no
    expected-sequence checks fire."""
    decision = _decision()  # empty
    status, issues = _run_safety_checks(_REF_ALS, decision)
    assert status == "PASS"
    assert issues == []
