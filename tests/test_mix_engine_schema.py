"""Tests for mix_engine.blueprint.schema (Phase 4.1)."""
import pytest

from mix_engine.blueprint import (
    MIX_LANES,
    Anomaly,
    DiagnosticReport,
    FullMixMetrics,
    HealthScore,
    MixBlueprint,
    MixCitation,
    MixDecision,
    TrackInfo,
)


def _sample_metrics() -> FullMixMetrics:
    return FullMixMetrics(
        integrated_lufs=-13.6, true_peak_dbtp=-0.3, crest_factor_db=12.4,
        plr_db=13.3, lra_db=8.2, dominant_band="low-mid",
        correlation=0.78, stereo_width=0.14, spectral_entropy=4.1,
    )


def _sample_health() -> HealthScore:
    return HealthScore(overall=52.2, breakdown=(("loudness", 60.0), ("stereo", 35.0)))


def _sample_report() -> DiagnosticReport:
    return DiagnosticReport(
        project_name="x", full_mix=_sample_metrics(),
        tracks=(), anomalies=(), health_score=_sample_health(),
    )


def test_mix_lanes_lists_all_planned_lanes():
    """If you add a lane, update this set so the test trip-wires."""
    assert set(MIX_LANES) == {
        "diagnostic", "routing", "eq_corrective", "eq_creative",
        "dynamics_corrective", "saturation_color", "stereo_spatial",
        "automation", "chain", "mastering",
    }


def test_mixblueprint_starts_empty():
    bp = MixBlueprint(name="test")
    assert bp.diagnostic is None
    assert bp.filled_lanes() == ()


def test_with_decision_attaches_to_correct_lane():
    bp = MixBlueprint(name="test")
    decision = MixDecision(value=_sample_report(), lane="diagnostic")
    bp2 = bp.with_decision("diagnostic", decision)
    assert bp.diagnostic is None  # immutability — original unchanged
    assert bp2.diagnostic is decision
    assert bp2.filled_lanes() == ("diagnostic",)


def test_with_decision_rejects_unknown_lane():
    bp = MixBlueprint(name="test")
    decision = MixDecision(value=_sample_report(), lane="diagnostic")
    with pytest.raises(ValueError, match="Unknown mix lane"):
        bp.with_decision("not_a_real_lane", decision)


def test_with_decision_rejects_lane_mismatch():
    """Catching the typo where decision.lane != target slot."""
    bp = MixBlueprint(name="test")
    decision = MixDecision(value=_sample_report(), lane="routing")
    with pytest.raises(ValueError, match="lane mismatch"):
        bp.with_decision("diagnostic", decision)


def test_track_info_is_immutable():
    t = TrackInfo(
        name="Kick", track_type="Audio", parent_bus=None, color="",
        devices=(), volume_db=0.0, pan=0.0, sidechain_targets=(), activator=True,
    )
    with pytest.raises(Exception):  # frozen dataclass
        t.name = "Snare"  # type: ignore[misc]


def test_anomaly_severity_is_just_a_string_at_dataclass_level():
    """Schema doesn't enforce — that's the parser's job (single source of truth)."""
    a = Anomaly(severity="anything", category="x", description="y", affected_tracks=())
    assert a.severity == "anything"


def test_mix_citation_kind_is_just_a_string_at_dataclass_level():
    c = MixCitation(kind="invented", path="x", excerpt="y")
    assert c.kind == "invented"
