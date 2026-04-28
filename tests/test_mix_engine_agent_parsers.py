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


# ============================================================================
# Phase 4.3 — DiagnosticReport.get_health_category_score helper
# ============================================================================


def test_get_health_category_score_case_insensitive():
    """Method matches case-insensitively against breakdown entries (mix-
    diagnostician normalizes to lowercase, but agents may pass the
    canonical capitalized form 'Dynamics' / 'Spectral Balance')."""
    payload = _valid_payload()
    payload["diagnostic"]["health_score"]["breakdown"] = [
        {"category": "loudness", "score": 60.0},
        {"category": "dynamics", "score": 52.5},
        {"category": "Spectral Balance", "score": 70.0},
    ]
    report = parse_diagnostic_decision(payload).value
    assert report.get_health_category_score("Dynamics") == 52.5
    assert report.get_health_category_score("dynamics") == 52.5
    assert report.get_health_category_score("DYNAMICS") == 52.5
    assert report.get_health_category_score("Spectral Balance") == 70.0
    assert report.get_health_category_score("spectral balance") == 70.0
    assert report.get_health_category_score("missing_cat") is None


# ============================================================================
# Phase 4.3 — Dynamics corrective lane parser
# ============================================================================


from mix_engine.blueprint import (
    DynamicsCorrection,
    DynamicsCorrectiveDecision,
    SidechainConfig,
    VALID_DYNAMICS_CHAIN_POSITIONS,
    VALID_DYNAMICS_DEVICES,
    VALID_DYNAMICS_TYPES,
    VALID_SIDECHAIN_MODES,
    parse_dynamics_corrective_decision,
    parse_dynamics_corrective_decision_from_response,
)


def _valid_dyn_correction(**overrides) -> dict:
    base = {
        "track": "Bass A",
        "dynamics_type": "compress",
        "device": "Compressor2",
        "threshold_db": -18.0,
        "ratio": 3.0,
        "attack_ms": 10.0,
        "release_ms": 100.0,
        "makeup_db": 3.0,
        "knee_db": 6.0,
        "chain_position": "post_eq_corrective",
        "processing_mode": "stereo",
        "rationale": "Bass A crest 18 dB ; ratio 3:1 stabilise sans tuer la dynamique de groove.",
        "inspired_by": [
            {"kind": "user_brief", "path": "brief:tighten_bass",
             "excerpt": "tighten Bass A — needs to sit better in the mix"},
        ],
    }
    base.update(overrides)
    return base


def _valid_dyn_payload(**overrides) -> dict:
    base = {
        "schema_version": "1.0",
        "dynamics_corrective": {
            "corrections": [_valid_dyn_correction()],
        },
        "cited_by": [
            {"kind": "diagnostic", "path": "Mix Health Score!Dynamics",
             "excerpt": "Dynamics 52/100 — moderate intervention space"},
        ],
        "rationale": "1 compression corrective sur Bass A, deferred from brief.",
        "confidence": 0.78,
    }
    base.update(overrides)
    return base


def test_dyn_parses_minimum_valid_payload():
    decision = parse_dynamics_corrective_decision(_valid_dyn_payload())
    assert decision.lane == "dynamics_corrective"
    assert isinstance(decision.value, DynamicsCorrectiveDecision)
    assert len(decision.value.corrections) == 1
    c = decision.value.corrections[0]
    assert c.track == "Bass A"
    assert c.dynamics_type == "compress"
    assert c.device == "Compressor2"
    assert c.threshold_db == -18.0
    assert c.ratio == 3.0


def test_dyn_decision_assignable_to_blueprint():
    from mix_engine.blueprint import MixBlueprint
    decision = parse_dynamics_corrective_decision(_valid_dyn_payload())
    bp = MixBlueprint(name="session").with_decision("dynamics_corrective", decision)
    assert bp.dynamics_corrective is decision
    assert bp.filled_lanes() == ("dynamics_corrective",)


def test_dyn_unsupported_schema_version_raises():
    payload = _valid_dyn_payload()
    payload["schema_version"] = "99.0"
    with pytest.raises(MixAgentOutputError, match="schema_version"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_error_payload_raises():
    with pytest.raises(MixAgentOutputError, match="agent refused"):
        parse_dynamics_corrective_decision({"error": "no signal", "details": "..."})


@pytest.mark.parametrize("invalid_type", ["smash", "duck_it", "Compress", "COMPRESS", ""])
def test_dyn_invalid_dynamics_type_raises(invalid_type):
    """Strict casing : 'Compress' / 'COMPRESS' must raise ; agent emits canonical 'compress'."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["dynamics_type"] = invalid_type
    with pytest.raises(MixAgentOutputError, match="dynamics_type"):
        parse_dynamics_corrective_decision(payload)


@pytest.mark.parametrize("invalid_device", ["Kickstart 2", "Kickstart2", "ProQ3", ""])
def test_dyn_invalid_device_raises_kickstart_explicitly(invalid_device):
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["device"] = invalid_device
    with pytest.raises(MixAgentOutputError, match="device"):
        parse_dynamics_corrective_decision(payload)


# ----------------------------------------------------------------------------
# Range checks
# ----------------------------------------------------------------------------


def test_dyn_threshold_out_of_range_raises():
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["threshold_db"] = 5.0
    with pytest.raises(MixAgentOutputError, match="threshold_db"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_ratio_out_of_range_raises():
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["ratio"] = 200.0
    with pytest.raises(MixAgentOutputError, match="ratio"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_attack_out_of_range_raises():
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["attack_ms"] = 500.0
    with pytest.raises(MixAgentOutputError, match="attack_ms"):
        parse_dynamics_corrective_decision(payload)


# ----------------------------------------------------------------------------
# 13 cross-field checks
# ----------------------------------------------------------------------------


def test_dyn_check1_compress_with_low_ratio_raises():
    """Cross-field #1 : compress requires ratio ≥ 1.1."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["ratio"] = 1.05
    with pytest.raises(MixAgentOutputError, match="no compression"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_gate_threshold_range_enforced_by_range_check():
    """Range check on threshold_db [-60, 0] subsumes the original Pass-2
    cross-field #2 (gate threshold > 0 impossible). Both paths same outcome :
    gate threshold > 0 dBFS rejected."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0].update({
        "dynamics_type": "gate", "device": "Gate",
        "threshold_db": 3.0,
    })
    with pytest.raises(MixAgentOutputError, match="threshold_db"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_check2_limit_ceiling_above_zero_raises():
    """Cross-field #2 : limiter ceiling > 0 dBFS impossible."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0] = _valid_dyn_correction(
        dynamics_type="limit", device="Limiter",
        threshold_db=None, ratio=None, attack_ms=None, release_ms=None,
        makeup_db=None, knee_db=None,
        ceiling_db=2.0,
    )
    with pytest.raises(MixAgentOutputError, match="ceiling"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_check3_sidechain_duck_requires_external_sidechain():
    """Cross-field #3 : sidechain_duck requires SidechainConfig."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["dynamics_type"] = "sidechain_duck"
    # No sidechain block
    with pytest.raises(MixAgentOutputError, match="sidechain"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_check3_sidechain_duck_internal_mode_raises():
    """Cross-field #3 : sidechain_duck mode must be 'external'."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0].update({
        "dynamics_type": "sidechain_duck",
        "sidechain": {
            "mode": "internal_filtered",
            "filter_freq_hz": 100.0, "filter_q": 0.7,
        },
    })
    with pytest.raises(MixAgentOutputError, match="external"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_check4_parallel_with_full_wet_raises():
    """Cross-field #4 : parallel_compress with dry_wet ≥ 0.95 = standard comp."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0].update({
        "dynamics_type": "parallel_compress",
        "dry_wet": 0.98,
    })
    with pytest.raises(MixAgentOutputError, match="parallel_compress"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_check5_compress_with_low_dry_wet_raises():
    """Cross-field #5 : compress with dry_wet < 0.5 = parallel territory."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["dry_wet"] = 0.3
    with pytest.raises(MixAgentOutputError, match="parallel"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_check6_gluecompressor_outside_bus_glue_raises():
    """Cross-field #6 : GlueCompressor restricted to bus_glue."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["device"] = "GlueCompressor"
    with pytest.raises(MixAgentOutputError, match="GlueCompressor"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_check7_drumbuss_outside_transient_shape_raises():
    """Cross-field #7 : DrumBuss restricted to transient_shape."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["device"] = "DrumBuss"
    with pytest.raises(MixAgentOutputError, match="DrumBuss"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_envelope_min_3_points_enforced():
    """Envelope < 3 points = ramp = static change (enforced in
    _parse_dynamics_envelope_strict, parallel to eq-corrective)."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0].update({
        "threshold_envelope": [{"bar": 0, "value": -18.0}, {"bar": 16, "value": -22.0}],
        "sections": [0, 1],
    })
    with pytest.raises(MixAgentOutputError, match="≥ 3 points"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_check8_envelope_without_sections_raises():
    """Cross-field #8 : envelope non-empty AND sections=() ambiguous."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0].update({
        "threshold_envelope": [
            {"bar": 0, "value": -18.0},
            {"bar": 16, "value": -22.0},
            {"bar": 32, "value": -18.0},
        ],
        # sections deliberately absent
    })
    with pytest.raises(MixAgentOutputError, match="sections"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_check9_short_rationale_raises():
    """Cross-field #9 : depth-light requires rationale ≥ 50 chars."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["rationale"] = "too short"
    with pytest.raises(MixAgentOutputError, match="rationale"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_check9_no_inspired_by_raises():
    """Cross-field #9 : depth-light requires ≥ 1 citation."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["inspired_by"] = []
    with pytest.raises(MixAgentOutputError, match="inspired_by"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_check10_external_sidechain_requires_depth_db():
    """Cross-field #10 : external sidechain_duck requires depth_db intent."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0].update({
        "dynamics_type": "sidechain_duck",
        "sidechain": {
            "mode": "external", "trigger_track": "Kick A",
            # depth_db deliberately absent
        },
    })
    with pytest.raises(MixAgentOutputError, match="depth_db"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_check11_release_auto_on_compressor2_raises():
    """Cross-field #11 : Compressor2 has no auto-release."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["release_auto"] = True
    with pytest.raises(MixAgentOutputError, match="Compressor2"):
        parse_dynamics_corrective_decision(payload)


# ----------------------------------------------------------------------------
# Sidechain config
# ----------------------------------------------------------------------------


def test_dyn_sidechain_external_happy_path():
    """CDE Kickstart 2 → Compressor2 sidechain external defer mapping."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0] = _valid_dyn_correction(
        dynamics_type="sidechain_duck", device="Compressor2",
        threshold_db=None, ratio=None, attack_ms=None, release_ms=120.0,
        makeup_db=None, knee_db=None,
        sidechain={
            "mode": "external",
            "trigger_track": "Kick A",
            "depth_db": -8.0,
        },
        chain_position="post_eq_corrective",
        rationale="CDE deferred: Bass A ducked under Kick A by -8 dB ; Compressor2 sidechain external translation of CDE Kickstart 2 intent.",
        inspired_by=[
            {"kind": "diagnostic", "path": "cde:cde-007.primary",
             "excerpt": "Kickstart 2 sidechain depth=-8 dB target=Bass A trigger=Kick A"},
            {"kind": "diagnostic", "path": "cde:cde-007.tfp_context",
             "excerpt": "track_a_role=(H,R) track_b_role=(S,L)"},
        ],
    )
    decision = parse_dynamics_corrective_decision(payload)
    c = decision.value.corrections[0]
    assert c.sidechain.mode == "external"
    assert c.sidechain.trigger_track == "Kick A"
    assert c.sidechain.depth_db == -8.0


def test_dyn_sidechain_external_without_trigger_raises():
    """SidechainConfig.mode=external requires trigger_track."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0].update({
        "dynamics_type": "sidechain_duck",
        "sidechain": {
            "mode": "external", "depth_db": -8.0,
            # trigger_track deliberately absent
        },
    })
    with pytest.raises(MixAgentOutputError, match="trigger_track"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_internal_filtered_deess_happy_path():
    """deess via Compressor2 internal_filtered sidechain (no trigger needed)."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0] = _valid_dyn_correction(
        dynamics_type="deess", device="Compressor2",
        threshold_db=-22.0, ratio=4.0, attack_ms=2.0, release_ms=80.0,
        makeup_db=None, knee_db=3.0,
        sidechain={
            "mode": "internal_filtered",
            "filter_freq_hz": 7000.0, "filter_q": 4.0,
        },
        rationale="Vocal Lead sibilance during drops ; internal_filtered sidechain at 7 kHz only triggers comp on esses, transparent elsewhere.",
        inspired_by=[
            {"kind": "user_brief", "path": "brief:de_ess",
             "excerpt": "tame the esses on Vocal Lead"},
        ],
    )
    decision = parse_dynamics_corrective_decision(payload)
    c = decision.value.corrections[0]
    assert c.dynamics_type == "deess"
    assert c.sidechain.mode == "internal_filtered"
    assert c.sidechain.filter_freq_hz == 7000.0


# ----------------------------------------------------------------------------
# Envelope ordering
# ----------------------------------------------------------------------------


def test_dyn_envelope_out_of_order_raises():
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0].update({
        "threshold_envelope": [
            {"bar": 0, "value": -18.0},
            {"bar": 32, "value": -22.0},
            {"bar": 16, "value": -20.0},
        ],
        "sections": [0, 1, 2],
    })
    with pytest.raises(MixAgentOutputError, match="bar-ascending"):
        parse_dynamics_corrective_decision(payload)


def test_dyn_envelope_value_out_of_range_raises():
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0].update({
        "sidechain": {"mode": "external", "trigger_track": "Kick A", "depth_db": -8.0},
        "dynamics_type": "sidechain_duck",
        "device": "Compressor2",
        "threshold_db": None, "ratio": None, "attack_ms": None, "release_ms": None,
        "makeup_db": None, "knee_db": None,
        "sidechain_depth_envelope": [
            {"bar": 0, "value": -4.0},
            {"bar": 16, "value": -50.0},  # out of range (-24..0)
            {"bar": 32, "value": -4.0},
        ],
        "sections": [0, 1, 2],
    })
    with pytest.raises(MixAgentOutputError, match="sidechain_depth_envelope"):
        parse_dynamics_corrective_decision(payload)


# ----------------------------------------------------------------------------
# DrumBuss transient_shape
# ----------------------------------------------------------------------------


def test_dyn_transient_shape_drumbuss_happy_path():
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0] = _valid_dyn_correction(
        dynamics_type="transient_shape", device="DrumBuss",
        threshold_db=None, ratio=None, attack_ms=None, release_ms=None,
        makeup_db=None, knee_db=None,
        transients=0.4,
        chain_position="post_eq_corrective",
        rationale="Brief explicit punchier kick ; DrumBuss Transients +0.4 enhances attack without compressor coloration.",
        inspired_by=[
            {"kind": "user_brief", "path": "brief:punchier_kick",
             "excerpt": "punchier kick"},
        ],
    )
    decision = parse_dynamics_corrective_decision(payload)
    assert decision.value.corrections[0].transients == 0.4


def test_dyn_transients_out_of_range_raises():
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0].update({
        "dynamics_type": "transient_shape", "device": "DrumBuss",
        "threshold_db": None, "ratio": None, "attack_ms": None,
        "release_ms": None, "makeup_db": None, "knee_db": None,
        "transients": 1.5,
    })
    with pytest.raises(MixAgentOutputError, match="transients"):
        parse_dynamics_corrective_decision(payload)


# ----------------------------------------------------------------------------
# Bus glue
# ----------------------------------------------------------------------------


def test_dyn_bus_glue_gluecomp_with_release_auto():
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0] = _valid_dyn_correction(
        track="Drums Bus",
        dynamics_type="bus_glue", device="GlueCompressor",
        threshold_db=-12.0, ratio=2.0, attack_ms=10.0,
        release_ms=None, release_auto=True,   # GlueComp Auto-Release legal
        makeup_db=2.0, knee_db=None,
        chain_position="post_eq_corrective",
        rationale="Drums bus glue : ratio 2:1 et release auto cohère le groupe sans pumper.",
        inspired_by=[
            {"kind": "user_brief", "path": "brief:glue_drums",
             "excerpt": "glue the drums bus"},
        ],
    )
    decision = parse_dynamics_corrective_decision(payload)
    c = decision.value.corrections[0]
    assert c.device == "GlueCompressor"
    assert c.release_auto is True


# ----------------------------------------------------------------------------
# from_response (markdown fences, prose)
# ----------------------------------------------------------------------------


def test_dyn_from_response_handles_fences():
    payload_str = json.dumps(_valid_dyn_payload())
    fenced = f"```json\n{payload_str}\n```"
    decision = parse_dynamics_corrective_decision_from_response(fenced)
    assert len(decision.value.corrections) == 1


def test_dyn_from_response_handles_prose():
    payload_str = json.dumps(_valid_dyn_payload())
    prosed = f"Here are the dynamics decisions:\n{payload_str}\nDone."
    decision = parse_dynamics_corrective_decision_from_response(prosed)
    assert len(decision.value.corrections) == 1


# ----------------------------------------------------------------------------
# Empty corrections (no signal → bands=[])
# ----------------------------------------------------------------------------


def test_dyn_empty_corrections_accepted():
    """No signal in inputs → corrections=[] is the right outcome (NO SIGNAL, NO MOVE)."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"] = []
    payload["rationale"] = "Aucune intervention dynamics-corrective justifiée par les sources."
    decision = parse_dynamics_corrective_decision(payload)
    assert decision.value.corrections == ()


# ----------------------------------------------------------------------------
# All valid dynamics_types accepted
# ----------------------------------------------------------------------------


def test_dyn_all_valid_dynamics_types_can_be_parsed():
    """Smoke : each valid dynamics_type can produce a coherent correction."""
    valid_combos = [
        # (dynamics_type, device, extra_overrides)
        ("compress", "Compressor2", {}),
        ("sidechain_duck", "Compressor2", {
            "sidechain": {"mode": "external", "trigger_track": "Kick A", "depth_db": -6.0},
        }),
        ("bus_glue", "GlueCompressor", {"track": "Drums Bus"}),
        ("gate", "Gate", {"threshold_db": -40.0, "ratio": None}),
        ("limit", "Limiter", {
            "threshold_db": None, "ratio": None, "ceiling_db": -1.0,
            "attack_ms": None, "release_ms": 50.0,
            "makeup_db": None, "knee_db": None,
        }),
        ("transient_shape", "DrumBuss", {
            "threshold_db": None, "ratio": None, "attack_ms": None, "release_ms": None,
            "makeup_db": None, "knee_db": None, "transients": 0.3,
        }),
        ("parallel_compress", "Compressor2", {
            "ratio": 6.0, "dry_wet": 0.4,
        }),
        ("deess", "Compressor2", {
            "ratio": 4.0, "attack_ms": 2.0,
            "sidechain": {"mode": "internal_filtered", "filter_freq_hz": 7000.0, "filter_q": 4.0},
        }),
    ]
    for dt, dev, extras in valid_combos:
        payload = _valid_dyn_payload()
        payload["dynamics_corrective"]["corrections"][0] = _valid_dyn_correction(
            dynamics_type=dt, device=dev, **extras
        )
        decision = parse_dynamics_corrective_decision(payload)
        assert decision.value.corrections[0].dynamics_type == dt, f"dynamics_type {dt} failed"
