"""Tests for mix_engine.writers.routing_configurator (Phase 4.14).

Phase 4.14 v1 scope :
- sidechain_redirect : update Target on existing SideChain (preserve tap)
- sidechain_remove : Target=AudioIn/None + OnOff=false
- sidechain_create : deferred Phase 4.14.X (no template)

Reference fixture has [S/T] Arp Roaming with sidechain pointing to
AudioIn/Track.169/PreFxOut (Bass Rythm Id=169). Used for redirect tests.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import als_utils
from mix_engine.blueprint import (
    MixCitation,
    MixDecision,
    RoutingDecision,
    SidechainRepair,
)
from mix_engine.writers import (
    RoutingConfiguratorError,
    RoutingConfiguratorReport,
    apply_routing_decision,
)
from mix_engine.writers.routing_configurator import (
    _build_target_value,
    _parse_target_value,
    _resolve_track_id,
    _run_safety_checks,
)


_REF_ALS = Path(__file__).parent / "fixtures" / "reference_project.als"


def _decision(*repairs) -> MixDecision[RoutingDecision]:
    return MixDecision(
        value=RoutingDecision(repairs=tuple(repairs)),
        lane="routing",
        rationale="Routing test wrapper.",
        confidence=0.85,
    )


def _make_repair(
    track: str = "[S/T] Arp Roaming",
    fix_type: str = "sidechain_redirect",
    current_trigger: str | None = "[H/R] Bass Rythm",
    new_trigger: str | None = "[H/R] Kick 1",
) -> SidechainRepair:
    return SidechainRepair(
        track=track,
        fix_type=fix_type,
        current_trigger=current_trigger,
        new_trigger=new_trigger,
        rationale=(
            "Causal: routing test baseline. Interactional: validates Phase "
            "4.14 routing-configurator REUSE-only path on fixture."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )


# ============================================================================
# Helper unit tests
# ============================================================================


def test_parse_target_value_track():
    assert _parse_target_value("AudioIn/Track.169/PreFxOut") == ("169", "PreFxOut")


def test_parse_target_value_track_postfx():
    assert _parse_target_value("AudioIn/Track.42/PostFxOut") == ("42", "PostFxOut")


def test_parse_target_value_no_tap_defaults_postfx():
    """AudioIn/Track.42 (no tap) → tap defaults to PostFxOut."""
    assert _parse_target_value("AudioIn/Track.42") == ("42", "PostFxOut")


def test_parse_target_value_none_returns_none():
    assert _parse_target_value("AudioIn/None") == (None, None)


def test_parse_target_value_bus_returns_none():
    """Bus refs are not Track.<Id> matchers → return None tuple."""
    assert _parse_target_value("AudioIn/Bus.5") == (None, None)


def test_build_target_value_default_postfx():
    assert _build_target_value("169") == "AudioIn/Track.169/PostFxOut"


def test_build_target_value_explicit_prefx():
    assert _build_target_value("169", "PreFxOut") == "AudioIn/Track.169/PreFxOut"


def test_resolve_track_id_known(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    tree = als_utils.parse_als(str(ref_copy))
    track_id = _resolve_track_id(tree, "[H/R] Bass Rythm")
    assert track_id == "169"


def test_resolve_track_id_not_found(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    tree = als_utils.parse_als(str(ref_copy))
    with pytest.raises(ValueError, match="No track named"):
        _resolve_track_id(tree, "NonexistentTrack")


# ============================================================================
# Empty + smoke
# ============================================================================


def test_empty_repairs_no_op(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    report = apply_routing_decision(ref_copy, _decision())
    assert isinstance(report, RoutingConfiguratorReport)
    assert report.repairs_applied == ()
    assert report.sidechain_blocks_modified == 0


# ============================================================================
# sidechain_redirect — Arp Roaming has sidechain → Bass Rythm (Id=169)
# ============================================================================


def test_apply_redirect_updates_target(tmp_path):
    """Redirect Arp Roaming sidechain from Bass Rythm → Kick 1.
    Verify Target value is updated to AudioIn/Track.<Kick1Id>/PreFxOut
    (tap PreFxOut preserved from original)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    repair = _make_repair(
        track="[S/T] Arp Roaming",
        fix_type="sidechain_redirect",
        current_trigger="[H/R] Bass Rythm",
        new_trigger="[H/R] Kick 1",
    )
    report = apply_routing_decision(ref_copy, _decision(repair), output_path=output)
    assert len(report.repairs_applied) == 1
    assert report.sidechain_blocks_modified == 1

    tree = als_utils.parse_als(str(output))
    arp_track = als_utils.find_track_by_name(tree, "[S/T] Arp Roaming")
    kick_id = _resolve_track_id(tree, "[H/R] Kick 1")

    # Find the SideChain that now points to Kick 1
    found = False
    for sc in arp_track.findall(".//SideChain"):
        target = sc.find("RoutedInput/Routable/Target")
        if target is None:
            continue
        val = target.get("Value", "")
        if val == f"AudioIn/Track.{kick_id}/PreFxOut":
            found = True
            break
    assert found, f"Expected Target=AudioIn/Track.{kick_id}/PreFxOut after redirect"


def test_apply_redirect_no_match_skipped(tmp_path):
    """Track with no SideChain pointing to current_trigger → skip with reason."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    # Bass Rythm has SideChain blocks but Target=AudioIn/None → no match for
    # any track-Id-based current_trigger
    repair = _make_repair(
        track="[H/R] Bass Rythm",
        fix_type="sidechain_redirect",
        current_trigger="[H/R] Kick 1",  # not currently wired on Bass Rythm
        new_trigger="[H/R] Kick 2",
    )
    report = apply_routing_decision(ref_copy, _decision(repair), dry_run=True)
    assert len(report.repairs_skipped) == 1
    assert "no SideChain currently pointing to" in report.repairs_skipped[0][1]


def test_apply_redirect_track_not_found_in_tracks_list(tmp_path):
    """Track owning the sidechain not in the project → ValueError propagates."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    repair = _make_repair(
        track="NonexistentTrack",
        fix_type="sidechain_redirect",
        current_trigger="[H/R] Bass Rythm",
        new_trigger="[H/R] Kick 1",
    )
    with pytest.raises(ValueError, match="No track named"):
        apply_routing_decision(ref_copy, _decision(repair), dry_run=True)


def test_apply_redirect_new_trigger_not_found_skipped(tmp_path):
    """new_trigger doesn't exist → skip with reason (no crash)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    repair = _make_repair(
        track="[S/T] Arp Roaming",
        fix_type="sidechain_redirect",
        current_trigger="[H/R] Bass Rythm",
        new_trigger="NonexistentNewTrigger",
    )
    report = apply_routing_decision(ref_copy, _decision(repair), dry_run=True)
    assert len(report.repairs_skipped) == 1
    assert "track resolution failed" in report.repairs_skipped[0][1]


# ============================================================================
# sidechain_remove
# ============================================================================


def test_apply_remove_sets_target_to_none_and_disables(tmp_path):
    """Remove Arp Roaming's sidechain (currently pointing Bass Rythm) :
    Target → AudioIn/None, OnOff/Manual → false."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    repair = SidechainRepair(
        track="[S/T] Arp Roaming",
        fix_type="sidechain_remove",
        current_trigger="[H/R] Bass Rythm",
        new_trigger=None,
        rationale="Test remove sidechain on Arp Roaming.",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    report = apply_routing_decision(ref_copy, _decision(repair), output_path=output)
    assert len(report.repairs_applied) == 1
    assert report.sidechain_blocks_modified == 1

    tree = als_utils.parse_als(str(output))
    arp_track = als_utils.find_track_by_name(tree, "[S/T] Arp Roaming")

    # Find at least one SideChain with Target=AudioIn/None AND OnOff=false
    found = False
    for sc in arp_track.findall(".//SideChain"):
        target = sc.find("RoutedInput/Routable/Target")
        onoff = sc.find("OnOff/Manual")
        if (target is not None and target.get("Value") == "AudioIn/None"
                and onoff is not None and onoff.get("Value") == "false"):
            found = True
            break
    assert found, "Expected at least one SideChain with Target=AudioIn/None + OnOff=false"


def test_apply_remove_no_match_skipped(tmp_path):
    """Remove on track without matching SideChain → skip with reason."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    repair = SidechainRepair(
        track="[H/R] Bass Rythm",
        fix_type="sidechain_remove",
        current_trigger="[H/R] Kick 1",  # not wired
        new_trigger=None,
        rationale="Test remove fail path.",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    report = apply_routing_decision(ref_copy, _decision(repair), dry_run=True)
    assert len(report.repairs_skipped) == 1
    assert "no SideChain currently pointing to" in report.repairs_skipped[0][1]


# ============================================================================
# sidechain_create — deferred
# ============================================================================


def test_apply_create_deferred_skipped(tmp_path):
    """sidechain_create deferred to Phase 4.14.X → skip with explicit reason."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    repair = SidechainRepair(
        track="[H/R] Kick 1",
        fix_type="sidechain_create",
        current_trigger=None,
        new_trigger="[H/R] Bass Rythm",
        rationale="Test sidechain_create deferral message.",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    report = apply_routing_decision(ref_copy, _decision(repair), dry_run=True)
    assert len(report.repairs_skipped) == 1
    assert "Phase 4.14.X" in report.repairs_skipped[0][1]


# ============================================================================
# Safety guardian
# ============================================================================


def test_safety_check_pass_on_fresh_apply(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    repair = _make_repair(
        track="[S/T] Arp Roaming",
        fix_type="sidechain_redirect",
        current_trigger="[H/R] Bass Rythm",
        new_trigger="[H/R] Kick 1",
    )
    report = apply_routing_decision(ref_copy, _decision(repair), output_path=output)
    assert report.safety_guardian_status == "PASS"


def test_safety_check_skipped_when_disabled(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    repair = _make_repair()
    report = apply_routing_decision(
        ref_copy, _decision(repair), output_path=output,
        invoke_safety_guardian=False,
    )
    assert report.safety_guardian_status == "SKIPPED"


def test_safety_check_unmodified_als_passes():
    status, issues = _run_safety_checks(_REF_ALS)
    assert status == "PASS", f"Reference fixture issues: {issues}"


def test_safety_check_detects_corrupted_file(tmp_path):
    bad = tmp_path / "bad.als"
    bad.write_bytes(b"not an als")
    status, issues = _run_safety_checks(bad)
    assert status == "FAIL"
    assert any("Cannot parse" in i for i in issues)


def test_safety_check_idempotent_re_apply(tmp_path):
    """Re-applying same redirect : Target value already updated → no match for
    current_trigger Id (which is now the OLD Id) → repair skipped (idempotent)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    repair = _make_repair(
        track="[S/T] Arp Roaming",
        fix_type="sidechain_redirect",
        current_trigger="[H/R] Bass Rythm",
        new_trigger="[H/R] Kick 1",
    )
    apply_routing_decision(ref_copy, _decision(repair), output_path=output)

    # Re-apply on output — current_trigger=Bass Rythm but Target now points
    # to Kick 1 → no match → skipped (idempotent)
    output2 = tmp_path / "out2.als"
    report2 = apply_routing_decision(output, _decision(repair), output_path=output2)
    assert len(report2.repairs_skipped) == 1
    assert report2.safety_guardian_status == "PASS"
