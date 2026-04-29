"""Tests for mix_engine.writers.spatial_configurator (Phase 4.12).

Phase 4.12 v1 scope :
- 7 spatial move types : pan / width / mono / bass_mono / balance /
  ms_balance / phase_flip
- pan : Mixer.Pan write (no device required)
- 6 others : StereoGain device REUSE-only (no template create)
- Safety guardian post-write
- 2-step methodology (compressed from 4-5 as patterns mature)
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import als_utils
from mix_engine.blueprint import (
    MixCitation,
    MixDecision,
    SpatialDecision,
    SpatialMove,
)
from mix_engine.writers import (
    SpatialConfiguratorError,
    SpatialConfiguratorReport,
    apply_spatial_decision,
)


_REF_ALS = Path(__file__).parent / "fixtures" / "reference_project.als"


def _make_move(
    track: str = "[H/R] Bass Rythm",
    move_type: str = "width",
    **fields,
) -> SpatialMove:
    """Build a minimal valid SpatialMove."""
    base = dict(
        track=track, move_type=move_type,
        chain_position="default",
        rationale=(
            "Causal: spatial test baseline. Interactional: validates "
            "Phase 4.12 spatial-configurator REUSE-only path on fixture."
        ),
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    base.update(fields)
    return SpatialMove(**base)


def _decision(*moves) -> MixDecision[SpatialDecision]:
    return MixDecision(
        value=SpatialDecision(moves=tuple(moves)),
        lane="stereo_spatial",
        rationale="Spatial test decision wrapper.",
        confidence=0.85,
    )


# ============================================================================
# Empty + smoke
# ============================================================================


def test_empty_moves_no_op(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    report = apply_spatial_decision(ref_copy, _decision())
    assert isinstance(report, SpatialConfiguratorReport)
    assert report.moves_applied == ()
    assert report.stereo_gains_reused == 0
    assert report.pans_written == 0


# ============================================================================
# Pan move (Mixer.Pan, no device)
# ============================================================================


def test_apply_pan_writes_mixer_pan(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(move_type="pan", pan=0.3)
    report = apply_spatial_decision(_decision(move) and ref_copy or None,
                                      _decision(move), output_path=output)
    assert len(report.moves_applied) == 1
    assert report.pans_written == 1
    assert report.stereo_gains_reused == 0  # pan doesn't use StereoGain

    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    pan_manual = track.find(".//DeviceChain/Mixer/Pan/Manual")
    assert pan_manual is not None
    assert abs(float(pan_manual.get("Value")) - 0.3) < 0.01


def test_apply_pan_negative_value(tmp_path):
    """pan = -0.5 (left)"""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(move_type="pan", pan=-0.5)
    apply_spatial_decision(ref_copy, _decision(move), output_path=output)
    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    pan_manual = track.find(".//DeviceChain/Mixer/Pan/Manual")
    assert abs(float(pan_manual.get("Value")) - (-0.5)) < 0.01


# ============================================================================
# StereoGain moves — fixture has StereoGain on Bass Rythm
# ============================================================================


def test_apply_width(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(move_type="width", stereo_width=1.5)
    report = apply_spatial_decision(ref_copy, _decision(move), output_path=output)
    assert report.stereo_gains_reused == 1

    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    sg = track.find(".//StereoGain")
    width = float(sg.find("StereoWidth/Manual").get("Value"))
    assert abs(width - 1.5) < 0.01


def test_apply_mono(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(move_type="mono")
    apply_spatial_decision(ref_copy, _decision(move), output_path=output)
    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    sg = track.find(".//StereoGain")
    mono = sg.find("Mono/Manual")
    assert mono.get("Value") == "true"


def test_apply_bass_mono(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(move_type="bass_mono", bass_mono_freq_hz=120.0)
    apply_spatial_decision(ref_copy, _decision(move), output_path=output)
    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    sg = track.find(".//StereoGain")
    bm = sg.find("BassMono/Manual")
    assert bm.get("Value") == "true"
    freq = float(sg.find("BassMonoFrequency/Manual").get("Value"))
    assert abs(freq - 120.0) < 0.01


def test_apply_balance(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(move_type="balance", balance=0.2)
    apply_spatial_decision(ref_copy, _decision(move), output_path=output)
    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    sg = track.find(".//StereoGain")
    bal = float(sg.find("Balance/Manual").get("Value"))
    assert abs(bal - 0.2) < 0.01


def test_apply_ms_balance_enables_on_flag(tmp_path):
    """ms_balance must enable MidSideBalanceOn AND set MidSideBalance value."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(move_type="ms_balance", mid_side_balance=1.3)
    apply_spatial_decision(ref_copy, _decision(move), output_path=output)
    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    sg = track.find(".//StereoGain")
    on = sg.find("MidSideBalanceOn")
    assert on.get("Value") == "true"
    val = float(sg.find("MidSideBalance/Manual").get("Value"))
    assert abs(val - 1.3) < 0.01


def test_apply_phase_flip_l(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(move_type="phase_flip", phase_channel="L")
    apply_spatial_decision(ref_copy, _decision(move), output_path=output)
    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    sg = track.find(".//StereoGain")
    inv = sg.find("PhaseInvertL/Manual")
    assert inv.get("Value") == "true"


def test_apply_phase_flip_r(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(move_type="phase_flip", phase_channel="R")
    apply_spatial_decision(ref_copy, _decision(move), output_path=output)
    tree = als_utils.parse_als(str(output))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    sg = track.find(".//StereoGain")
    inv = sg.find("PhaseInvertR/Manual")
    assert inv.get("Value") == "true"


# ============================================================================
# REUSE-only failure paths
# ============================================================================


def test_track_without_stereo_gain_skipped(tmp_path):
    """Kick 1 has only Eq8, no StereoGain → width move skipped with reason."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    move = _make_move(track="[H/R] Kick 1", move_type="width", stereo_width=1.2)
    report = apply_spatial_decision(ref_copy, _decision(move), dry_run=True)
    assert len(report.moves_applied) == 0
    assert len(report.moves_skipped) == 1
    assert "no StereoGain device" in report.moves_skipped[0][1]
    assert "REUSE-only" in report.moves_skipped[0][1]


def test_pan_works_even_without_stereo_gain(tmp_path):
    """Pan goes on Mixer (not device) → works on Kick 1 even though no StereoGain."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(track="[H/R] Kick 1", move_type="pan", pan=0.0)
    report = apply_spatial_decision(ref_copy, _decision(move), output_path=output)
    assert report.pans_written == 1
    assert report.stereo_gains_reused == 0


# ============================================================================
# Track not found
# ============================================================================


def test_track_not_found_raises(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    move = _make_move(track="NonexistentTrack", move_type="width", stereo_width=1.2)
    with pytest.raises(ValueError, match="No track named"):
        apply_spatial_decision(ref_copy, _decision(move), dry_run=True)


# ============================================================================
# Mixed multi-move
# ============================================================================


def test_apply_multi_move_mixed(tmp_path):
    """1 pan + 1 width on same track + 1 width on track without StereoGain."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    m1 = _make_move(track="[H/R] Bass Rythm", move_type="pan", pan=0.1)
    m2 = _make_move(track="[H/R] Bass Rythm", move_type="width", stereo_width=1.3)
    m3 = _make_move(track="[H/R] Kick 1", move_type="width", stereo_width=1.2)
    report = apply_spatial_decision(
        ref_copy, _decision(m1, m2, m3), output_path=output,
    )
    assert len(report.moves_applied) == 2  # pan + width on Bass Rythm
    assert len(report.moves_skipped) == 1  # width on Kick 1 (no StereoGain)
    assert report.pans_written == 1
    assert report.stereo_gains_reused == 1  # only Bass Rythm SG counted


# ============================================================================
# Phase 4.12 Step 2 — Safety guardian
# ============================================================================

from mix_engine.writers.spatial_configurator import _run_safety_checks  # noqa: E402


def test_safety_check_pass_on_fresh_apply(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(move_type="width", stereo_width=1.2)
    report = apply_spatial_decision(ref_copy, _decision(move), output_path=output)
    assert report.safety_guardian_status == "PASS"


def test_safety_check_skipped_when_disabled(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(move_type="width", stereo_width=1.2)
    report = apply_spatial_decision(
        ref_copy, _decision(move), output_path=output,
        invoke_safety_guardian=False,
    )
    assert report.safety_guardian_status == "SKIPPED"


def test_safety_check_skipped_for_dry_run(tmp_path):
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    move = _make_move(move_type="width", stereo_width=1.2)
    report = apply_spatial_decision(ref_copy, _decision(move), dry_run=True)
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


# ============================================================================
# Phase 4.12.1 audit fix — chain_position support tests
# ============================================================================

from mix_engine.writers.spatial_configurator import _find_existing_stereo_gain  # noqa: E402


def test_chain_position_default_finds_stereo_gain(tmp_path):
    """default → first StereoGain found (legacy behavior preserved)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    tree = als_utils.parse_als(str(ref_copy))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    found = _find_existing_stereo_gain(track, "default")
    assert found is not None and found.tag == "StereoGain"


def test_chain_position_post_eq_corrective_matches(tmp_path):
    """Bass Rythm chain : [Eq8, StereoGain, ...] → StereoGain IS after Eq8 → match."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    tree = als_utils.parse_als(str(ref_copy))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    found = _find_existing_stereo_gain(track, "post_eq_corrective")
    assert found is not None


def test_chain_position_post_dynamics_corrective_no_match(tmp_path):
    """Bass Rythm StereoGain at index 1, but GlueComp at 3 + Limiter at 4.
    StereoGain is NOT after dynamics → no match."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    tree = als_utils.parse_als(str(ref_copy))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    found = _find_existing_stereo_gain(track, "post_dynamics_corrective")
    assert found is None


def test_chain_position_chain_start_no_match_when_eq8_first(tmp_path):
    """Bass Rythm has Eq8 at index 0, not StereoGain → chain_start no match."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    tree = als_utils.parse_als(str(ref_copy))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    found = _find_existing_stereo_gain(track, "chain_start")
    assert found is None


def test_chain_position_chain_end_no_match_when_limiter_last(tmp_path):
    """Bass Rythm has Limiter at last index, not StereoGain → chain_end no match."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    tree = als_utils.parse_als(str(ref_copy))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    found = _find_existing_stereo_gain(track, "chain_end")
    assert found is None


def test_chain_position_unknown_raises(tmp_path):
    """Unknown chain_position → ValueError (defensive double-check)."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    tree = als_utils.parse_als(str(ref_copy))
    track = als_utils.find_track_by_name(tree, "[H/R] Bass Rythm")
    with pytest.raises(ValueError, match="Unknown spatial chain_position"):
        _find_existing_stereo_gain(track, "bogus")


def test_apply_post_eq_corrective_writes_to_existing_sg(tmp_path):
    """End-to-end : Tier A specifies chain_position='post_eq_corrective' →
    configurator finds StereoGain (after Eq8 on Bass Rythm) and writes width."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(
        track="[H/R] Bass Rythm",
        move_type="width",
        stereo_width=1.6,
        chain_position="post_eq_corrective",
    )
    report = apply_spatial_decision(ref_copy, _decision(move), output_path=output)
    assert len(report.moves_applied) == 1
    assert report.stereo_gains_reused == 1


def test_apply_chain_end_skipped_when_no_sg_terminal(tmp_path):
    """Bass Rythm : Limiter is last, not StereoGain → chain_end position
    skipped with reason."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    move = _make_move(
        track="[H/R] Bass Rythm",
        move_type="width",
        stereo_width=1.5,
        chain_position="chain_end",
    )
    report = apply_spatial_decision(ref_copy, _decision(move), dry_run=True)
    assert len(report.moves_skipped) == 1
    assert "chain_position='chain_end'" in report.moves_skipped[0][1]


# ============================================================================
# Phase 4.12.1 audit — invalid move_type defensive check
# ============================================================================


def test_apply_unknown_move_type_skipped(tmp_path):
    """Tier B double-checks move_type even if Tier A schema enforces.
    Defensive : if a malformed SpatialMove (constructed by hand bypassing
    Tier A parser) reaches Tier B, it must be skipped, not crash."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)

    # SpatialMove dataclass doesn't enforce move_type at construction time —
    # only the Tier A parser does. Tier B is the last line of defense.
    bogus_move = SpatialMove(
        track="[H/R] Bass Rythm",
        move_type="bogus_type",
        chain_position="default",
        rationale="Testing Tier B defensive check on unknown move_type.",
        inspired_by=(MixCitation(kind="diagnostic", path="x", excerpt="x"),),
    )
    decision = MixDecision(
        value=SpatialDecision(moves=(bogus_move,)),
        lane="stereo_spatial",
        rationale="Defensive check test for invalid move_type.",
        confidence=0.5,
    )
    report = apply_spatial_decision(ref_copy, decision, dry_run=True)
    assert len(report.moves_skipped) == 1
    assert "Unknown move_type" in report.moves_skipped[0][1]


def test_safety_check_idempotent_re_apply(tmp_path):
    """Re-apply same width value → no change, safety still PASS."""
    ref_copy = tmp_path / "ref.als"
    shutil.copy(_REF_ALS, ref_copy)
    output = tmp_path / "out.als"

    move = _make_move(move_type="width", stereo_width=1.4)
    apply_spatial_decision(ref_copy, _decision(move), output_path=output)
    tree1 = als_utils.parse_als(str(output))
    track1 = als_utils.find_track_by_name(tree1, "[H/R] Bass Rythm")
    width1 = float(track1.find(".//StereoGain/StereoWidth/Manual").get("Value"))

    output2 = tmp_path / "out2.als"
    report2 = apply_spatial_decision(output, _decision(move), output_path=output2)
    tree2 = als_utils.parse_als(str(output2))
    track2 = als_utils.find_track_by_name(tree2, "[H/R] Bass Rythm")
    width2 = float(track2.find(".//StereoGain/StereoWidth/Manual").get("Value"))

    assert abs(width1 - width2) < 0.001
    assert report2.safety_guardian_status == "PASS"
