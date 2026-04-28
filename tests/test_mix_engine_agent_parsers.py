"""Tests for mix_engine.blueprint.agent_parsers (Phase 4.1).

Mirror of the composition-side parser test layout: helper to build a
canonical valid payload, then negative tests that mutate one field at a
time.
"""
import json

import pytest

from mix_engine.blueprint import (
    DiagnosticReport,
    MixAgentOutputError,
    MixBlueprint,
    MixDecision,
    VALID_ANOMALY_SEVERITIES,
    VALID_CITATION_KINDS,
    VALID_TRACK_TYPES,
    parse_diagnostic_decision,
    parse_diagnostic_decision_from_response,
)


def _valid_payload(**overrides) -> dict:
    """Minimum-valid mix-diagnostician payload."""
    base = {
        "schema_version": "1.0",
        "diagnostic": {
            "project_name": "TestProject",
            "full_mix": {
                "integrated_lufs": -13.64,
                "true_peak_dbtp": -0.3,
                "crest_factor_db": 12.4,
                "plr_db": 13.3,
                "lra_db": 8.2,
                "dominant_band": "low-mid",
                "correlation": 0.78,
                "stereo_width": 0.14,
                "spectral_entropy": 4.1,
            },
            "tracks": [
                {"name": "Kick A", "track_type": "Audio",
                 "parent_bus": "Drums", "color": "#FF0000",
                 "devices": ["Eq8", "GlueCompressor"],
                 "volume_db": -3.2, "pan": 0.0,
                 "sidechain_targets": [], "activator": True},
                {"name": "Bass A", "track_type": "Audio",
                 "parent_bus": None, "color": "",
                 "devices": ["Eq8", "Compressor2"],
                 "volume_db": -6.0, "pan": 0.1,
                 "sidechain_targets": ["Kick A"], "activator": True},
            ],
            "anomalies": [
                {"severity": "critical", "category": "shared_resonance",
                 "description": "247 Hz Kick/Bass",
                 "affected_tracks": ["Kick A", "Bass A"],
                 "suggested_fix_lane": "eq_corrective"},
            ],
            "health_score": {
                "overall": 52.2,
                "breakdown": [
                    {"category": "loudness", "score": 60.0},
                    {"category": "stereo", "score": 35.0},
                ],
            },
            "routing_warnings": [],
        },
        "cited_by": [
            {"kind": "diagnostic", "path": "Full Mix Analysis!B7",
             "excerpt": "LUFS: -13.64"},
        ],
        "rationale": "État P11 ; marge dans le spectral balance.",
        "confidence": 0.88,
    }
    base.update(overrides)
    return base


def test_parses_minimum_valid_payload():
    decision = parse_diagnostic_decision(_valid_payload())
    assert decision.lane == "diagnostic"
    assert isinstance(decision.value, DiagnosticReport)
    assert decision.value.project_name == "TestProject"
    assert len(decision.value.tracks) == 2
    assert len(decision.value.anomalies) == 1
    assert decision.value.health_score.overall == 52.2
    assert decision.confidence == 0.88
    assert len(decision.cited_by) == 1


def test_decision_can_be_assigned_to_blueprint():
    decision = parse_diagnostic_decision(_valid_payload())
    bp = MixBlueprint(name="session").with_decision("diagnostic", decision)
    assert bp.diagnostic is decision
    assert bp.filled_lanes() == ("diagnostic",)


def test_unsupported_schema_version_raises():
    payload = _valid_payload()
    payload["schema_version"] = "99.0"
    with pytest.raises(MixAgentOutputError, match="schema_version"):
        parse_diagnostic_decision(payload)


def test_error_payload_raises_with_details():
    payload = {"error": "missing input", "details": "no .xlsx"}
    with pytest.raises(MixAgentOutputError, match="missing input"):
        parse_diagnostic_decision(payload)


def test_missing_project_name_raises():
    payload = _valid_payload()
    del payload["diagnostic"]["project_name"]
    with pytest.raises(MixAgentOutputError, match="project_name"):
        parse_diagnostic_decision(payload)


@pytest.mark.parametrize("invalid_type", ["audio", "Bus", "Aux", "VocalTrack"])
def test_invalid_track_type_raises(invalid_type):
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["track_type"] = invalid_type
    with pytest.raises(MixAgentOutputError, match="track_type"):
        parse_diagnostic_decision(payload)


@pytest.mark.parametrize("track_type", sorted(VALID_TRACK_TYPES))
def test_all_valid_track_types_accepted(track_type):
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["track_type"] = track_type
    decision = parse_diagnostic_decision(payload)
    assert decision.value.tracks[0].track_type == track_type


@pytest.mark.parametrize("invalid_severity", ["fatal", "warn", "Info", ""])
def test_invalid_anomaly_severity_raises(invalid_severity):
    payload = _valid_payload()
    payload["diagnostic"]["anomalies"][0]["severity"] = invalid_severity
    with pytest.raises(MixAgentOutputError, match="severity"):
        parse_diagnostic_decision(payload)


@pytest.mark.parametrize("severity", sorted(VALID_ANOMALY_SEVERITIES))
def test_all_valid_severities_accepted(severity):
    payload = _valid_payload()
    payload["diagnostic"]["anomalies"][0]["severity"] = severity
    decision = parse_diagnostic_decision(payload)
    assert decision.value.anomalies[0].severity == severity


def test_pan_out_of_range_raises():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["pan"] = 1.5
    with pytest.raises(MixAgentOutputError, match="pan"):
        parse_diagnostic_decision(payload)


def test_correlation_out_of_range_raises():
    payload = _valid_payload()
    payload["diagnostic"]["full_mix"]["correlation"] = 1.5
    with pytest.raises(MixAgentOutputError, match="correlation"):
        parse_diagnostic_decision(payload)


def test_stereo_width_out_of_range_raises():
    payload = _valid_payload()
    payload["diagnostic"]["full_mix"]["stereo_width"] = -0.1
    with pytest.raises(MixAgentOutputError, match="stereo_width"):
        parse_diagnostic_decision(payload)


def test_health_score_out_of_range_raises():
    payload = _valid_payload()
    payload["diagnostic"]["health_score"]["overall"] = 150.0
    with pytest.raises(MixAgentOutputError, match="overall"):
        parse_diagnostic_decision(payload)


def test_confidence_out_of_range_raises():
    payload = _valid_payload()
    payload["confidence"] = 1.5
    with pytest.raises(MixAgentOutputError, match="confidence"):
        parse_diagnostic_decision(payload)


def test_invalid_citation_kind_raises():
    payload = _valid_payload()
    payload["cited_by"][0]["kind"] = "invented_source"
    with pytest.raises(MixAgentOutputError, match="kind"):
        parse_diagnostic_decision(payload)


@pytest.mark.parametrize("kind", sorted(VALID_CITATION_KINDS))
def test_all_valid_citation_kinds_accepted(kind):
    payload = _valid_payload()
    payload["cited_by"][0]["kind"] = kind
    decision = parse_diagnostic_decision(payload)
    assert decision.cited_by[0].kind == kind


def test_health_score_breakdown_as_pairs_accepted():
    """Lenient input: accept [['cat', 60.0], ...] tuple form too."""
    payload = _valid_payload()
    payload["diagnostic"]["health_score"]["breakdown"] = [
        ["loudness", 60.0],
        ["stereo", 35.0],
    ]
    decision = parse_diagnostic_decision(payload)
    assert decision.value.health_score.breakdown == (
        ("loudness", 60.0), ("stereo", 35.0),
    )


def test_routing_warnings_as_string_list_accepted():
    payload = _valid_payload()
    payload["diagnostic"]["routing_warnings"] = [
        "Sidechain on Bass A points to renamed track",
        "Send 2 has No Output",
    ]
    decision = parse_diagnostic_decision(payload)
    assert len(decision.value.routing_warnings) == 2


def test_empty_anomalies_accepted():
    payload = _valid_payload()
    payload["diagnostic"]["anomalies"] = []
    decision = parse_diagnostic_decision(payload)
    assert decision.value.anomalies == ()


def test_from_response_handles_fences():
    payload_str = json.dumps(_valid_payload())
    fenced = f"```json\n{payload_str}\n```"
    decision = parse_diagnostic_decision_from_response(fenced)
    assert decision.value.project_name == "TestProject"


def test_from_response_handles_prose_around():
    payload_str = json.dumps(_valid_payload())
    prosed = f"Here is the diagnostic:\n{payload_str}\nEnd."
    decision = parse_diagnostic_decision_from_response(prosed)
    assert decision.value.project_name == "TestProject"


# ============================================================================
# Phase 4.2.8 — CDE diagnostics + Freq Conflicts absorption
# ============================================================================


def _valid_cde_diagnostic() -> dict:
    """Minimum-valid CDE diagnostic, mimicking cde_engine.py output."""
    return {
        "diagnostic_id": "cde-007",
        "issue_type": "masking_conflict",
        "severity": "critical",
        "section": "drop_1",
        "track_a": "Kick A",
        "track_b": "Bass A",
        "measurement": {"frequency_hz": 247.0},
        "tfp_context": {
            "track_a_role": ["H", "R"],
            "track_b_role": ["S", "L"],
            "role_compatibility": "high",
        },
        "primary_correction": {
            "target_track": "Bass A",
            "device": "EQ8 — Peak Resonance",
            "approach": "static_dip",
            "parameters": {
                "frequency_hz": 247.0, "gain_db": -3.0, "q": 4.0,
                "active_in_sections": [2, 3, 4],
            },
            "applies_to_sections": [2, 3, 4],
            "rationale": "Static dip libère espace pour Kick A (Hero).",
            "confidence": "high",
        },
        "fallback_correction": {
            "target_track": "Bass A",
            "device": "Kickstart 2",
            "approach": "sidechain",
            "parameters": {"trigger_track": "Kick A", "depth_db": -6.0, "release_ms": 120},
            "applies_to_sections": [2, 3, 4],
            "rationale": "Sidechain alternatif si EQ8 budget plein.",
            "confidence": "medium",
        },
        "expected_outcomes": [
            "Bass A clears 247Hz region by 3dB",
            "Mono compatibility +0.05",
        ],
        "potential_risks": [
            "Bass A may lose body if applied across all sections",
        ],
        "application_status": "pending",
    }


def test_diagnostic_report_with_cde_diagnostics():
    payload = _valid_payload()
    payload["diagnostic"]["cde_diagnostics"] = [_valid_cde_diagnostic()]
    decision = parse_diagnostic_decision(payload)
    cde_diags = decision.value.cde_diagnostics
    assert len(cde_diags) == 1
    d = cde_diags[0]
    assert d.diagnostic_id == "cde-007"
    assert d.issue_type == "masking_conflict"
    assert d.severity == "critical"
    assert d.track_a == "Kick A"
    assert d.track_b == "Bass A"
    assert d.measurement.frequency_hz == 247.0
    assert d.tfp_context.track_a_role == ("H", "R")
    assert d.primary_correction.device == "EQ8 — Peak Resonance"
    assert d.primary_correction.confidence == "high"
    assert d.primary_correction.parameters["gain_db"] == -3.0
    assert d.fallback_correction.device == "Kickstart 2"
    assert len(d.expected_outcomes) == 2
    assert len(d.potential_risks) == 1
    assert d.application_status == "pending"


def test_cde_diagnostic_with_null_optional_fields():
    """measurement, tfp_context, primary_correction, fallback_correction
    all may be null. application_status may be null (never processed)."""
    payload = _valid_payload()
    payload["diagnostic"]["cde_diagnostics"] = [{
        "diagnostic_id": "cde-min",
        "issue_type": "accumulation_risk",
        "severity": "moderate",
        "track_a": "Pad",
        "track_b": None,
        "measurement": None,
        "tfp_context": None,
        "primary_correction": None,
        "fallback_correction": None,
        "expected_outcomes": [],
        "potential_risks": [],
        "application_status": None,
    }]
    decision = parse_diagnostic_decision(payload)
    d = decision.value.cde_diagnostics[0]
    assert d.measurement is None
    assert d.tfp_context is None
    assert d.primary_correction is None
    assert d.application_status is None


def test_cde_invalid_severity_raises():
    payload = _valid_payload()
    bad_diag = _valid_cde_diagnostic()
    bad_diag["severity"] = "INFO"  # not in CDE vocabulary
    payload["diagnostic"]["cde_diagnostics"] = [bad_diag]
    with pytest.raises(MixAgentOutputError, match="severity"):
        parse_diagnostic_decision(payload)


def test_cde_invalid_application_status_raises():
    payload = _valid_payload()
    bad_diag = _valid_cde_diagnostic()
    bad_diag["application_status"] = "queued"  # not in valid set
    payload["diagnostic"]["cde_diagnostics"] = [bad_diag]
    with pytest.raises(MixAgentOutputError, match="application_status"):
        parse_diagnostic_decision(payload)


def test_cde_invalid_confidence_raises():
    payload = _valid_payload()
    bad_diag = _valid_cde_diagnostic()
    bad_diag["primary_correction"]["confidence"] = "very_high"
    payload["diagnostic"]["cde_diagnostics"] = [bad_diag]
    with pytest.raises(MixAgentOutputError, match="confidence"):
        parse_diagnostic_decision(payload)


def test_cde_unknown_issue_type_does_not_raise():
    """Open-set : unknown issue_type forwarded so future CDE detectors don't break."""
    payload = _valid_payload()
    novel_diag = _valid_cde_diagnostic()
    novel_diag["issue_type"] = "novel_detector_xyz"
    payload["diagnostic"]["cde_diagnostics"] = [novel_diag]
    decision = parse_diagnostic_decision(payload)
    assert decision.value.cde_diagnostics[0].issue_type == "novel_detector_xyz"


def test_diagnostic_report_with_freq_conflicts_meta():
    payload = _valid_payload()
    payload["diagnostic"]["freq_conflicts_meta"] = {
        "threshold_pct": 30.0,
        "min_tracks": 2,
    }
    payload["diagnostic"]["freq_conflicts_bands"] = [
        {
            "band_label": "low-mid (200-500Hz)",
            "energy_per_track": {"Kick A": 22.0, "Bass A": 38.0, "Synth Pad": 28.0},
            "conflict_count": 2,
            "status": "Conflict",
        },
        {
            "band_label": "mid (500-1k)",
            "energy_per_track": {"Kick A": 8.0, "Bass A": 12.0, "Synth Pad": 35.0},
            "conflict_count": 1,
            "status": "OK",
        },
    ]
    decision = parse_diagnostic_decision(payload)
    meta = decision.value.freq_conflicts_meta
    assert meta is not None
    assert meta.threshold_pct == 30.0
    assert meta.min_tracks == 2
    bands = decision.value.freq_conflicts_bands
    assert len(bands) == 2
    low_mid = bands[0]
    assert low_mid.band_label == "low-mid (200-500Hz)"
    assert low_mid.conflict_count == 2
    assert low_mid.status == "Conflict"
    energy_dict = dict(low_mid.energy_per_track)
    assert energy_dict["Bass A"] == 38.0


def test_diagnostic_report_without_cde_or_freq_conflicts_optional():
    """Backward-compat: payloads without cde_diagnostics/freq_conflicts_*
    still parse cleanly with empty defaults."""
    decision = parse_diagnostic_decision(_valid_payload())
    assert decision.value.cde_diagnostics == ()
    assert decision.value.freq_conflicts_meta is None
    assert decision.value.freq_conflicts_bands == ()


def test_sidechain_target_text_preserved():
    """Routing references to renamed tracks survive verbatim — a downstream
    routing-and-sidechain-architect agent will check them against current
    track names."""
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][1]["sidechain_targets"] = [
        "AudioIn/Track.4/PostFxOut",
    ]
    decision = parse_diagnostic_decision(payload)
    assert decision.value.tracks[1].sidechain_targets == (
        "AudioIn/Track.4/PostFxOut",
    )
