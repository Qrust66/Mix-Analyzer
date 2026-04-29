"""Tests for mix_engine.writers.master_bus_configurator (Phase 4.15).

Phase 4.15 v1 scope :
- 6 master move types (limiter_target, glue_compression, master_eq_band,
  stereo_enhance, saturation_color, bus_glue)
- REUSE-only on master (LiveSet/MainTrack) and sub-bus (Group tracks)

Reference fixture's MainTrack has [PluginDevice×3, StereoGain, PluginDevice,
SpectrumAnalyzer, StereoGain] — only stereo_enhance is testable
end-to-end on master ; other types test the skip-with-reason path.

For bus_glue tests, sub-bus tracks like [H/R] Bass Rythm have
GlueCompressor (testable).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import als_utils
from mix_engine.blueprint import (
    MASTER_TRACK_NAME,
    MasteringDecision,
    MasterMove,
    MixCitation,
    MixDecision,
)
from mix_engine.writers import (
    MasterBusConfiguratorError,
    MasterBusConfiguratorReport,
    MasterTrackNotFoundError,
    apply_mastering_decision,
)
from mix_engine.writers.master_bus_configurator import (
    _find_master_track,
    _resolve_target,
    _run_safety_checks,
)


_REF_ALS = Path(__file__).parent / "fixtures" / "reference_project.als"


def _decision(*moves) -> MixDecision[MasteringDecision]:
    return MixDecision(
        value=MasteringDecision(moves=tuple(moves)),
        lane="mastering",
        rationale="Mastering test wrapper.",
        confidence=0.85,
    )


def _make_move(
    type: str,
    device: str,
    target_track: str = MASTER_TRACK_NAME,
    chain_position: str = "default",
    **fields,
) -> MasterMove:
    base = dict(
        type=type, target_track=target_track, device=device,
        chain_position=chain_position,
        rationale=(
            "Causal: mastering test baseline. Interactional: validates Phase "
            "4.15 master-bus-configurator REUSE-only path."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    base.update(fields)
    return MasterMove(**base)


# ============================================================================
# Helper unit tests
# ============================================================================


def test_find_master_track_locates_main_track(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    tree = als_utils.parse_als(str(ref_copy))
    main = _find_master_track(tree)
    assert main is not None
    assert main.tag == "MainTrack"


def test_resolve_target_master_constant(tmp_path):
    """target_track='Master' resolves to MainTrack."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    tree = als_utils.parse_als(str(ref_copy))
    move = _make_move(type="stereo_enhance", device="StereoGain", width=1.1)
    target = _resolve_target(tree, move)
    assert target.tag == "MainTrack"


def test_resolve_target_subbus_via_track_name(tmp_path):
    """target_track='[H/R] Bass Rythm' resolves via find_track_by_name."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    tree = als_utils.parse_als(str(ref_copy))
    move = _make_move(
        type="bus_glue", device="GlueCompressor",
        target_track="[H/R] Bass Rythm",
        chain_position="bus_glue",
        ratio=2.0, threshold_db=-12.0,
    )
    target = _resolve_target(tree, move)
    assert target.tag == "AudioTrack"


def test_resolve_target_subbus_not_found_raises(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    tree = als_utils.parse_als(str(ref_copy))
    move = _make_move(
        type="bus_glue", device="GlueCompressor",
        target_track="NonexistentBus",
        chain_position="bus_glue",
        ratio=2.0, threshold_db=-12.0,
    )
    with pytest.raises(ValueError, match="No track named"):
        _resolve_target(tree, move)


# ============================================================================
# Empty + smoke
# ============================================================================


def test_empty_moves_no_op(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    report = apply_mastering_decision(ref_copy, _decision())
    assert isinstance(report, MasterBusConfiguratorReport)
    assert report.moves_applied == ()
    assert report.devices_reused == 0


# ============================================================================
# stereo_enhance — only type fully testable on fixture MainTrack
# ============================================================================


def test_apply_master_stereo_enhance_width(tmp_path):
    """MainTrack has StereoGain → stereo_enhance with width=1.2 reuses it."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(
        type="stereo_enhance", device="StereoGain",
        chain_position="master_stereo",
        width=1.2,
    )
    report = apply_mastering_decision(ref_copy, _decision(move), output_path=output)
    assert len(report.moves_applied) == 1
    assert report.devices_reused == 1

    tree = als_utils.parse_als(str(output))
    main = _find_master_track(tree)
    sg = main.find(".//StereoGain")
    assert sg is not None
    width = float(sg.find("StereoWidth/Manual").get("Value"))
    assert abs(width - 1.2) < 0.01


def test_apply_master_stereo_enhance_bass_mono(tmp_path):
    """stereo_enhance with bass_mono_freq_hz enables BassMono on master."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(
        type="stereo_enhance", device="StereoGain",
        chain_position="master_stereo",
        bass_mono_freq_hz=120.0,
    )
    apply_mastering_decision(ref_copy, _decision(move), output_path=output)

    tree = als_utils.parse_als(str(output))
    main = _find_master_track(tree)
    sg = main.find(".//StereoGain")
    bm = sg.find("BassMono/Manual")
    assert bm.get("Value") == "true"
    bmf = float(sg.find("BassMonoFrequency/Manual").get("Value"))
    assert abs(bmf - 120.0) < 0.5


def test_apply_master_stereo_enhance_ms_balance(tmp_path):
    """stereo_enhance ms_balance enables MidSideBalanceOn flag + sets value."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(
        type="stereo_enhance", device="StereoGain",
        chain_position="master_stereo",
        mid_side_balance=1.3,
    )
    apply_mastering_decision(ref_copy, _decision(move), output_path=output)

    tree = als_utils.parse_als(str(output))
    main = _find_master_track(tree)
    sg = main.find(".//StereoGain")
    on = sg.find("MidSideBalanceOn")
    assert on.get("Value") == "true"


# ============================================================================
# REUSE-only failure paths : MainTrack lacks Limiter / Eq8 / etc.
# ============================================================================


def test_apply_master_limiter_no_device_skipped(tmp_path):
    """MainTrack has no Limiter → limiter_target skipped with reason."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    move = _make_move(
        type="limiter_target", device="Limiter",
        chain_position="master_limiter",
        target_lufs_i=-10.0, ceiling_dbtp=-0.3,
    )
    report = apply_mastering_decision(ref_copy, _decision(move), dry_run=True)
    assert len(report.moves_skipped) == 1
    assert "REUSE-only" in report.moves_skipped[0][1]


def test_apply_master_eq_band_no_device_skipped(tmp_path):
    """MainTrack has no Eq8 → master_eq_band skipped."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    move = _make_move(
        type="master_eq_band", device="Eq8",
        chain_position="master_corrective",
        band_type="bell", center_hz=600.0, q=1.5, gain_db=-1.5,
    )
    report = apply_mastering_decision(ref_copy, _decision(move), dry_run=True)
    assert len(report.moves_skipped) == 1
    assert "no" in report.moves_skipped[0][1].lower()


def test_apply_master_glue_no_device_skipped(tmp_path):
    """MainTrack has no GlueCompressor → glue_compression skipped."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    move = _make_move(
        type="glue_compression", device="GlueCompressor",
        chain_position="master_glue",
        ratio=1.7, threshold_db=-10.0,
    )
    report = apply_mastering_decision(ref_copy, _decision(move), dry_run=True)
    assert len(report.moves_skipped) == 1


def test_apply_master_saturation_no_device_skipped(tmp_path):
    """MainTrack has no Saturator → saturation_color skipped."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    move = _make_move(
        type="saturation_color", device="Saturator",
        chain_position="master_color",
        drive_pct=8.0, saturation_type="soft_sine", dry_wet=1.0,
    )
    report = apply_mastering_decision(ref_copy, _decision(move), dry_run=True)
    assert len(report.moves_skipped) == 1


# ============================================================================
# bus_glue on sub-bus track (testable — Bass Rythm has GlueCompressor)
# ============================================================================


def test_apply_bus_glue_on_subbus_writes_threshold(tmp_path):
    """bus_glue on Bass Rythm REUSE GlueCompressor → write Threshold."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(
        type="bus_glue", device="GlueCompressor",
        target_track="[H/R] Bass Rythm",
        chain_position="bus_glue",
        ratio=2.0, threshold_db=-15.0, attack_ms=10.0, release_ms=200.0,
    )
    report = apply_mastering_decision(ref_copy, _decision(move), output_path=output)
    assert len(report.moves_applied) == 1
    assert report.devices_reused == 1

    tree = als_utils.parse_als(str(output))
    bass = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    glue = bass.find(".//GlueCompressor")
    threshold = float(glue.find("Threshold/Manual").get("Value"))
    assert abs(threshold - (-15.0)) < 0.1


# ============================================================================
# Safety guardian
# ============================================================================


def test_safety_check_pass_on_fresh_apply(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(
        type="stereo_enhance", device="StereoGain",
        chain_position="master_stereo",
        width=1.1,
    )
    report = apply_mastering_decision(ref_copy, _decision(move), output_path=output)
    assert report.safety_guardian_status == "PASS"


def test_safety_check_skipped_when_disabled(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(
        type="stereo_enhance", device="StereoGain",
        chain_position="master_stereo", width=1.1,
    )
    report = apply_mastering_decision(
        ref_copy, _decision(move), output_path=output,
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
    """Re-apply same width → stable value, status PASS."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(
        type="stereo_enhance", device="StereoGain",
        chain_position="master_stereo", width=1.15,
    )
    apply_mastering_decision(ref_copy, _decision(move), output_path=output)
    tree1 = als_utils.parse_als(str(output))
    main1 = _find_master_track(tree1)
    width1 = float(main1.find(".//StereoGain/StereoWidth/Manual").get("Value"))

    output2 = tmp_path / "out2.als"
    report2 = apply_mastering_decision(output, _decision(move), output_path=output2)
    tree2 = als_utils.parse_als(str(output2))
    main2 = _find_master_track(tree2)
    width2 = float(main2.find(".//StereoGain/StereoWidth/Manual").get("Value"))

    assert abs(width1 - width2) < 0.001
    assert report2.safety_guardian_status == "PASS"


# ============================================================================
# Multi-move : mix of supported (stereo_enhance master) + skipped (limiter)
# ============================================================================


def test_apply_multi_move_mixed_master_subbus(tmp_path):
    """3 moves : stereo_enhance master + limiter_target master skipped +
    bus_glue Bass Rythm applied."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    m1 = _make_move(
        type="stereo_enhance", device="StereoGain",
        chain_position="master_stereo", width=1.1,
    )
    m2 = _make_move(
        type="limiter_target", device="Limiter",
        chain_position="master_limiter",
        target_lufs_i=-10.0, ceiling_dbtp=-0.3,
    )  # skipped (no Limiter on master)
    m3 = _make_move(
        type="bus_glue", device="GlueCompressor",
        target_track="[H/R] Bass Rythm",
        chain_position="bus_glue",
        ratio=2.0, threshold_db=-12.0,
    )
    report = apply_mastering_decision(
        ref_copy, _decision(m1, m2, m3), output_path=output,
    )
    assert len(report.moves_applied) == 2
    assert len(report.moves_skipped) == 1  # Limiter
    assert report.devices_reused == 2  # StereoGain master + GlueComp Bass Rythm
