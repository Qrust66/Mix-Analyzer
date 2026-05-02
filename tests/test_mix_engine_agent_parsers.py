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


def test_dyn_chain_position_chain_end_accepted():
    """Phase 4.3 audit fix : 'chain_end' (generic) added for parity with
    eq-corrective ; bus_glue on Group track typically lands here."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0] = _valid_dyn_correction(
        track="Drums Bus",
        dynamics_type="bus_glue", device="GlueCompressor",
        threshold_db=-10.0, ratio=2.0, attack_ms=10.0,
        release_ms=None, release_auto=True,
        makeup_db=2.0, knee_db=None,
        chain_position="chain_end",
        rationale="Drums Bus glue placed at chain_end : GlueComp est le dernier device sur ce Group, pas de Limiter aval.",
        inspired_by=[
            {"kind": "user_brief", "path": "brief:glue", "excerpt": "glue the drums bus"},
        ],
    )
    decision = parse_dynamics_corrective_decision(payload)
    assert decision.value.corrections[0].chain_position == "chain_end"


def test_dyn_makeup_envelope_happy_path():
    """makeup_envelope tracking verse/chorus dynamic compensation."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0].update({
        "makeup_envelope": [
            {"bar": 0, "value": 2.0},
            {"bar": 16, "value": 4.0},
            {"bar": 32, "value": 2.0},
        ],
        "sections": [0, 1, 2],
    })
    decision = parse_dynamics_corrective_decision(payload)
    env = decision.value.corrections[0].makeup_envelope
    assert len(env) == 3
    assert env[1].value == 4.0


def test_dyn_dry_wet_envelope_happy_path():
    """dry_wet_envelope for parallel-compress blend changes per section."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0] = _valid_dyn_correction(
        dynamics_type="parallel_compress", device="Compressor2",
        threshold_db=-25.0, ratio=6.0, attack_ms=2.0, release_ms=80.0,
        makeup_db=None, knee_db=None,
        dry_wet=0.4,
        dry_wet_envelope=[
            {"bar": 0, "value": 0.3},
            {"bar": 16, "value": 0.5},
            {"bar": 32, "value": 0.3},
        ],
        sections=[0, 1, 2],
        rationale="Parallel comp Bass A : dry_wet envelope 0.3→0.5→0.3 augmente density au chorus puis revient au verse.",
        inspired_by=[
            {"kind": "user_brief", "path": "brief:parallel",
             "excerpt": "parallel comp Bass with denser blend in chorus"},
        ],
    )
    decision = parse_dynamics_corrective_decision(payload)
    env = decision.value.corrections[0].dry_wet_envelope
    assert len(env) == 3
    assert env[1].value == 0.5


@pytest.mark.parametrize("mode", ["mid", "side"])
def test_dyn_processing_mode_ms_accepted(mode):
    """Phase 4.3 : M/S processing valid for bus master compression. Agent
    is responsible for verifying correlation < 0.95 (not parser)."""
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["processing_mode"] = mode
    decision = parse_dynamics_corrective_decision(payload)
    assert decision.value.corrections[0].processing_mode == mode


def test_dyn_invalid_processing_mode_raises():
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0]["processing_mode"] = "stereo_diff"
    with pytest.raises(MixAgentOutputError, match="processing_mode"):
        parse_dynamics_corrective_decision(payload)


@pytest.mark.parametrize("position", sorted(VALID_DYNAMICS_CHAIN_POSITIONS))
def test_dyn_all_valid_chain_positions_parse(position):
    """Smoke : every value in VALID_DYNAMICS_CHAIN_POSITIONS is accepted.
    Picks scenarios that legitimize each position (gate_first → Gate,
    chain_end_limiter → Limiter, etc.) rather than blindly testing the
    string."""
    # Build a correction whose dynamics_type/device pair is compatible
    # with the position. Keep it minimal but valid.
    base_overrides = {"chain_position": position}
    if position == "gate_first":
        base_overrides.update({
            "dynamics_type": "gate", "device": "Gate",
            "threshold_db": -40.0, "ratio": None,
        })
    elif position == "chain_end_limiter":
        base_overrides.update({
            "dynamics_type": "limit", "device": "Limiter",
            "threshold_db": None, "ratio": None, "attack_ms": None,
            "release_ms": 50.0, "makeup_db": None, "knee_db": None,
            "ceiling_db": -1.0,
        })
    payload = _valid_dyn_payload()
    payload["dynamics_corrective"]["corrections"][0] = _valid_dyn_correction(**base_overrides)
    decision = parse_dynamics_corrective_decision(payload)
    assert decision.value.corrections[0].chain_position == position


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


# ============================================================================
# Phase 4.4 — Routing & sidechain lane parser
# ============================================================================


from mix_engine.blueprint import (
    RoutingDecision,
    SidechainRepair,
    STALE_SIDECHAIN_REGEX,
    VALID_ROUTING_FIX_TYPES,
    parse_routing_decision,
    parse_routing_decision_from_response,
)


def _valid_routing_repair(**overrides) -> dict:
    """Default = sidechain_redirect repair (most common scenario)."""
    base = {
        "track": "Bass A",
        "fix_type": "sidechain_redirect",
        "current_trigger": "AudioIn/Track.4/PostFxOut",
        "new_trigger": "Kick A",
        "rationale": "Bass A sidechain ref stale (Track 4 renommé) ; redirect vers Kick A confirmé par CDE diagnostic primary.",
        "inspired_by": [
            {"kind": "diagnostic", "path": "routing_warnings[0]",
             "excerpt": "Sidechain on Bass A points to renamed track"},
        ],
    }
    base.update(overrides)
    return base


def _valid_routing_payload(**overrides) -> dict:
    base = {
        "schema_version": "1.0",
        "routing": {"repairs": [_valid_routing_repair()]},
        "cited_by": [
            {"kind": "diagnostic", "path": "routing_warnings",
             "excerpt": "1 stale sidechain ref detected"},
        ],
        "rationale": "1 stale sidechain ref repair on Bass A (CDE-driven).",
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------------------------
# Happy paths
# ----------------------------------------------------------------------------


def test_routing_parses_minimum_valid_payload():
    decision = parse_routing_decision(_valid_routing_payload())
    assert decision.lane == "routing"
    assert isinstance(decision.value, RoutingDecision)
    assert len(decision.value.repairs) == 1
    r = decision.value.repairs[0]
    assert r.fix_type == "sidechain_redirect"
    assert r.current_trigger == "AudioIn/Track.4/PostFxOut"
    assert r.new_trigger == "Kick A"


def test_routing_decision_assignable_to_blueprint():
    from mix_engine.blueprint import MixBlueprint
    decision = parse_routing_decision(_valid_routing_payload())
    bp = MixBlueprint(name="session").with_decision("routing", decision)
    assert bp.routing is decision
    assert bp.filled_lanes() == ("routing",)


def test_routing_unsupported_schema_version_raises():
    payload = _valid_routing_payload()
    payload["schema_version"] = "99.0"
    with pytest.raises(MixAgentOutputError, match="schema_version"):
        parse_routing_decision(payload)


def test_routing_error_payload_raises():
    with pytest.raises(MixAgentOutputError, match="agent refused"):
        parse_routing_decision({"error": "no signal", "details": "no broken refs"})


def test_routing_empty_repairs_accepted():
    """No broken refs in the project → repairs=[] is the right outcome
    (idempotence preserves this on re-runs after Tier B applies fixes)."""
    payload = _valid_routing_payload()
    payload["routing"]["repairs"] = []
    payload["rationale"] = "All sidechain refs intact ; no repair needed."
    decision = parse_routing_decision(payload)
    assert decision.value.repairs == ()


@pytest.mark.parametrize("invalid_type", ["sidechain_validate", "redirect", "Sidechain_Redirect", ""])
def test_routing_invalid_fix_type_raises(invalid_type):
    """sidechain_validate was dropped (Pass 1 D audit) ; strict casing."""
    payload = _valid_routing_payload()
    payload["routing"]["repairs"][0]["fix_type"] = invalid_type
    with pytest.raises(MixAgentOutputError, match="fix_type"):
        parse_routing_decision(payload)


# ----------------------------------------------------------------------------
# 8 cross-field checks
# ----------------------------------------------------------------------------


def test_routing_check1_redirect_same_source_target_raises():
    """#1 : redirect with current == new = no-op."""
    payload = _valid_routing_payload()
    payload["routing"]["repairs"][0].update({
        "current_trigger": "Kick A",
        "new_trigger": "Kick A",
    })
    with pytest.raises(MixAgentOutputError, match="no-op"):
        parse_routing_decision(payload)


def test_routing_check2_redirect_missing_current_raises():
    payload = _valid_routing_payload()
    payload["routing"]["repairs"][0]["current_trigger"] = None
    with pytest.raises(MixAgentOutputError, match="requires BOTH"):
        parse_routing_decision(payload)


def test_routing_check2_redirect_missing_new_raises():
    payload = _valid_routing_payload()
    payload["routing"]["repairs"][0]["new_trigger"] = None
    with pytest.raises(MixAgentOutputError, match="requires BOTH"):
        parse_routing_decision(payload)


def test_routing_check3_remove_with_new_trigger_raises():
    """#3 : sidechain_remove must NOT have new_trigger."""
    payload = _valid_routing_payload()
    payload["routing"]["repairs"][0] = _valid_routing_repair(
        fix_type="sidechain_remove",
        current_trigger="AudioIn/Track.4/PostFxOut",
        new_trigger="Kick A",  # contradiction
        rationale="Remove broken sidechain ref but somehow new_trigger is set — should reject.",
    )
    with pytest.raises(MixAgentOutputError, match="no target"):
        parse_routing_decision(payload)


def test_routing_check4_remove_without_current_trigger_raises():
    payload = _valid_routing_payload()
    payload["routing"]["repairs"][0] = _valid_routing_repair(
        fix_type="sidechain_remove",
        current_trigger=None,
        new_trigger=None,
        rationale="Remove sidechain but no current_trigger specified — nothing to remove.",
    )
    with pytest.raises(MixAgentOutputError, match="current_trigger"):
        parse_routing_decision(payload)


def test_routing_check5_create_with_current_trigger_raises():
    """#5 : sidechain_create must NOT have current_trigger (Pass 2 audit Finding 2)."""
    payload = _valid_routing_payload()
    payload["routing"]["repairs"][0] = _valid_routing_repair(
        fix_type="sidechain_create",
        current_trigger="AudioIn/Track.4/PostFxOut",  # contradiction
        new_trigger="Kick A",
        rationale="Create new sidechain wiring but current_trigger set — should reject.",
    )
    with pytest.raises(MixAgentOutputError, match="no existing ref"):
        parse_routing_decision(payload)


def test_routing_check6_create_without_new_trigger_raises():
    payload = _valid_routing_payload()
    payload["routing"]["repairs"][0] = _valid_routing_repair(
        fix_type="sidechain_create",
        current_trigger=None,
        new_trigger=None,
        rationale="Create new sidechain but no new_trigger specified — no target.",
    )
    with pytest.raises(MixAgentOutputError, match="new_trigger"):
        parse_routing_decision(payload)


def test_routing_check7_recreating_stale_ref_raises():
    """#7 : new_trigger matching STALE_SIDECHAIN_REGEX = recreating broken ref."""
    payload = _valid_routing_payload()
    payload["routing"]["repairs"][0]["new_trigger"] = "AudioIn/Track.5/PostFxOut"
    with pytest.raises(MixAgentOutputError, match="raw stale-ref"):
        parse_routing_decision(payload)


def test_routing_check8_short_rationale_raises():
    """#8 : depth-light requires rationale ≥ 50 chars."""
    payload = _valid_routing_payload()
    payload["routing"]["repairs"][0]["rationale"] = "too short"
    with pytest.raises(MixAgentOutputError, match="rationale"):
        parse_routing_decision(payload)


def test_routing_check8_no_inspired_by_raises():
    payload = _valid_routing_payload()
    payload["routing"]["repairs"][0]["inspired_by"] = []
    with pytest.raises(MixAgentOutputError, match="inspired_by"):
        parse_routing_decision(payload)


def test_routing_duplicate_repairs_raises():
    """Cross-correction check : duplicate (track, fix_type, current, new) tuple."""
    payload = _valid_routing_payload()
    repair_dup = _valid_routing_repair()
    payload["routing"]["repairs"] = [repair_dup, dict(repair_dup)]
    with pytest.raises(MixAgentOutputError, match="duplicate"):
        parse_routing_decision(payload)


# ----------------------------------------------------------------------------
# Scenario coverage
# ----------------------------------------------------------------------------


def test_routing_scenario_b_remove_happy_path():
    """B : sidechain_remove when no good target available."""
    payload = _valid_routing_payload()
    payload["routing"]["repairs"][0] = _valid_routing_repair(
        fix_type="sidechain_remove",
        current_trigger="AudioIn/Track.7/PostFxOut",
        new_trigger=None,
        rationale="Bass A stale sidechain ; brief silent + no CDE diagnostic ; remove rather than guess a trigger.",
    )
    decision = parse_routing_decision(payload)
    r = decision.value.repairs[0]
    assert r.fix_type == "sidechain_remove"
    assert r.current_trigger == "AudioIn/Track.7/PostFxOut"
    assert r.new_trigger is None


def test_routing_scenario_c_create_happy_path():
    """C : sidechain_create from brief explicit "duck X under Y"."""
    payload = _valid_routing_payload()
    payload["routing"]["repairs"][0] = _valid_routing_repair(
        track="Pad",
        fix_type="sidechain_create",
        current_trigger=None,
        new_trigger="Kick A",
        rationale="Brief explicit duck Pad under Kick A ; wire sidechain ref ; dynamics-corrective Scenario B configures depth.",
        inspired_by=[
            {"kind": "user_brief", "path": "brief:duck", "excerpt": "duck Pad under Kick A"},
        ],
    )
    decision = parse_routing_decision(payload)
    r = decision.value.repairs[0]
    assert r.fix_type == "sidechain_create"
    assert r.current_trigger is None
    assert r.new_trigger == "Kick A"


# ----------------------------------------------------------------------------
# STALE_SIDECHAIN_REGEX exposed correctly
# ----------------------------------------------------------------------------


def test_stale_sidechain_regex_matches_documented_format():
    import re
    pat = re.compile(STALE_SIDECHAIN_REGEX)
    # Should match
    assert pat.match("AudioIn/Track.4/PostFxOut")
    assert pat.match("AudioIn/Track.0/PostMixerOut")
    assert pat.match("AudioIn/Track.10")
    # Should NOT match (resolved track names + permanent destinations)
    assert not pat.match("Kick A")
    assert not pat.match("AudioIn/Bus.1/Out")  # bus refs are permanent
    assert not pat.match("AudioIn/Master/Out")  # master is permanent


# ----------------------------------------------------------------------------
# Idempotence — re-running on .als post-Tier-B-applied produces repairs=()
# ----------------------------------------------------------------------------


def test_routing_idempotence_after_redirect_applied():
    """Once Tier B applies a redirect, mix-diagnostician re-reads the .als
    and sees a resolved track name (not raw AudioIn/Track.N). Re-running
    the agent on the new state must produce repairs=() — gates require
    stale signals that no longer exist."""
    # State 1 : stale ref → agent emits redirect
    payload_before = _valid_routing_payload()
    decision_before = parse_routing_decision(payload_before)
    assert len(decision_before.value.repairs) == 1

    # State 2 (post-Tier-B) : agent receives same brief but routing_warnings
    # is now empty AND the report would no longer contain the stale ref.
    # Agent's correct emission : repairs=[] (no signal, no move).
    payload_after = _valid_routing_payload()
    payload_after["routing"]["repairs"] = []
    payload_after["rationale"] = "Re-run after Tier B applied redirect ; sidechain ref now resolved to Kick A ; no further action."
    decision_after = parse_routing_decision(payload_after)
    assert decision_after.value.repairs == ()


# ----------------------------------------------------------------------------
# from_response (markdown fences, prose around)
# ----------------------------------------------------------------------------


def test_routing_from_response_handles_fences():
    payload_str = json.dumps(_valid_routing_payload())
    fenced = f"```json\n{payload_str}\n```"
    decision = parse_routing_decision_from_response(fenced)
    assert len(decision.value.repairs) == 1


def test_routing_from_response_handles_prose():
    payload_str = json.dumps(_valid_routing_payload())
    prosed = f"Here are the routing decisions:\n{payload_str}\nDone."
    decision = parse_routing_decision_from_response(prosed)
    assert len(decision.value.repairs) == 1


@pytest.mark.parametrize("ft", sorted(VALID_ROUTING_FIX_TYPES))
def test_routing_all_valid_fix_types_can_be_parsed(ft):
    """Smoke : each valid fix_type can produce a coherent repair."""
    if ft == "sidechain_redirect":
        repair = _valid_routing_repair()
    elif ft == "sidechain_remove":
        repair = _valid_routing_repair(
            fix_type=ft, new_trigger=None,
            rationale="No trigger candidate available ; remove the broken sidechain ref entirely.",
        )
    elif ft == "sidechain_create":
        repair = _valid_routing_repair(
            fix_type=ft, current_trigger=None, new_trigger="Kick A",
            rationale="Brief explicit duck Bass A under Kick A ; create new sidechain wiring.",
        )
    payload = _valid_routing_payload()
    payload["routing"]["repairs"][0] = repair
    decision = parse_routing_decision(payload)
    assert decision.value.repairs[0].fix_type == ft


# ============================================================================
# Phase 4.5 — Stereo & spatial lane parser
# ============================================================================


from mix_engine.blueprint import (
    SpatialDecision,
    SpatialMove,
    VALID_SPATIAL_MOVE_TYPES,
    VALID_SPATIAL_CHAIN_POSITIONS,
    VALID_PHASE_CHANNELS,
    parse_spatial_decision,
    parse_spatial_decision_from_response,
)


def _valid_spatial_move(**overrides) -> dict:
    """Default = pan move (simplest scenario)."""
    base = {
        "track": "Vocal Lead",
        "move_type": "pan",
        "pan": 0.0,
        "rationale": "Vocal Lead centered per brief explicit + standard mix anchoring practice for lead vocals.",
        "inspired_by": [
            {"kind": "user_brief", "path": "brief:pan", "excerpt": "vocal center"},
        ],
    }
    base.update(overrides)
    return base


def _valid_spatial_payload(**overrides) -> dict:
    base = {
        "schema_version": "1.0",
        "stereo_spatial": {"moves": [_valid_spatial_move()]},
        "cited_by": [
            {"kind": "user_brief", "path": "brief", "excerpt": "vocal center"},
        ],
        "rationale": "1 spatial move : pan Vocal Lead center.",
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------------------------
# Happy paths
# ----------------------------------------------------------------------------


def test_spatial_parses_minimum_valid_payload():
    decision = parse_spatial_decision(_valid_spatial_payload())
    assert decision.lane == "stereo_spatial"
    assert isinstance(decision.value, SpatialDecision)
    assert len(decision.value.moves) == 1
    assert decision.value.moves[0].move_type == "pan"
    assert decision.value.moves[0].pan == 0.0


def test_spatial_decision_assignable_to_blueprint():
    from mix_engine.blueprint import MixBlueprint
    decision = parse_spatial_decision(_valid_spatial_payload())
    bp = MixBlueprint(name="session").with_decision("stereo_spatial", decision)
    assert bp.stereo_spatial is decision
    assert bp.filled_lanes() == ("stereo_spatial",)


def test_spatial_unsupported_schema_version_raises():
    payload = _valid_spatial_payload()
    payload["schema_version"] = "99.0"
    with pytest.raises(MixAgentOutputError, match="schema_version"):
        parse_spatial_decision(payload)


def test_spatial_error_payload_raises():
    with pytest.raises(MixAgentOutputError, match="agent refused"):
        parse_spatial_decision({"error": "no signal", "details": "no spatial issues"})


def test_spatial_empty_moves_accepted():
    """No spatial signal in inputs → moves=[] (NO SIGNAL, NO MOVE)."""
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"] = []
    payload["rationale"] = "Aucune intervention spatiale justifiée."
    decision = parse_spatial_decision(payload)
    assert decision.value.moves == ()


@pytest.mark.parametrize("invalid_type", ["panning", "PAN", "wide", "narrow", ""])
def test_spatial_invalid_move_type_raises(invalid_type):
    """'wide' / 'narrow' folded into 'width' move_type ; strict casing."""
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0]["move_type"] = invalid_type
    with pytest.raises(MixAgentOutputError, match="move_type"):
        parse_spatial_decision(payload)


# ----------------------------------------------------------------------------
# Range checks (audit Pass 1 v2 corrected ranges)
# ----------------------------------------------------------------------------


def test_spatial_pan_out_of_range_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0]["pan"] = 1.5
    with pytest.raises(MixAgentOutputError, match="pan"):
        parse_spatial_decision(payload)


def test_spatial_stereo_width_max_4_accepted():
    """Audit Finding A : range corrected to [0, 4] (was [0, 2])."""
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        track="Pad",
        move_type="width", pan=None,
        stereo_width=3.5,
        rationale="Pad strong stereo widening per brief 'open up the pads' ; ear-candy 3.5 width = ambient territory.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "open up the pads"}],
    )
    decision = parse_spatial_decision(payload)
    assert decision.value.moves[0].stereo_width == 3.5


def test_spatial_stereo_width_above_4_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        track="Pad",
        move_type="width", pan=None,
        stereo_width=5.0,  # > catalog max 4.0
        rationale="Out of range width test must reject this value above catalog max 4.0.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "extreme wide"}],
    )
    with pytest.raises(MixAgentOutputError, match="stereo_width"):
        parse_spatial_decision(payload)


def test_spatial_bass_mono_freq_min_50_accepted():
    """Audit Finding C : range corrected to [50, 500] (was [60, 250])."""
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        track="Bass",
        move_type="bass_mono", pan=None,
        bass_mono_freq_hz=50.0,
        rationale="Bass sub-mono at 50 Hz cutoff per brief 'mono the sub' ; very low fundamental territory (808-style).",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "mono the sub"}],
    )
    decision = parse_spatial_decision(payload)
    assert decision.value.moves[0].bass_mono_freq_hz == 50.0


def test_spatial_bass_mono_freq_max_500_accepted():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        track="Bass",
        move_type="bass_mono", pan=None,
        bass_mono_freq_hz=500.0,
        rationale="Bass aggressive low-mid mono summing at 500 Hz per brief 'tighten the low-mid mud zone' ; rare but legit.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "tighten low mid"}],
    )
    decision = parse_spatial_decision(payload)
    assert decision.value.moves[0].bass_mono_freq_hz == 500.0


def test_spatial_bass_mono_freq_below_50_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        track="Bass",
        move_type="bass_mono", pan=None,
        bass_mono_freq_hz=30.0,  # below catalog min 50
        rationale="Below range test for bass_mono_freq_hz catalog minimum bound 50 Hz reject path.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "x"}],
    )
    with pytest.raises(MixAgentOutputError, match="bass_mono_freq_hz"):
        parse_spatial_decision(payload)


def test_spatial_ms_balance_range_0_to_2():
    """Audit Finding B : range corrected to [0, 2] (was [-1, 1])."""
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        track="Master Bus",
        move_type="ms_balance", pan=None,
        mid_side_balance=1.5,  # in [0, 2]
        rationale="Master bus slight side emphasis at 1.5 per brief 'open up' + Mix Health Stereo Image 60 modulator.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "open up"}],
    )
    decision = parse_spatial_decision(payload)
    assert decision.value.moves[0].mid_side_balance == 1.5


def test_spatial_ms_balance_negative_raises():
    """Audit Finding B : negative values rejected (real range [0, 2], not [-1, 1])."""
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        track="Master Bus",
        move_type="ms_balance", pan=None,
        mid_side_balance=-0.5,  # invalid in real range
        rationale="Negative MS balance test for audit Finding B fix - the old fictive [-1,1] range is rejected.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "x"}],
    )
    with pytest.raises(MixAgentOutputError, match="mid_side_balance"):
        parse_spatial_decision(payload)


# ----------------------------------------------------------------------------
# 11 cross-field checks
# ----------------------------------------------------------------------------


def test_spatial_check1_pan_missing_value_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0]["pan"] = None
    with pytest.raises(MixAgentOutputError, match="pan"):
        parse_spatial_decision(payload)


def test_spatial_check2_width_missing_value_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        move_type="width", pan=None,  # no stereo_width set
        rationale="Width move missing stereo_width value should trigger check #2 required field.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "wider"}],
    )
    with pytest.raises(MixAgentOutputError, match="stereo_width"):
        parse_spatial_decision(payload)


def test_spatial_check3_width_neutral_no_op_raises():
    """#3 : stereo_width == 1.0 (neutre) is no-op identity."""
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        move_type="width", pan=None, stereo_width=1.0,
        rationale="Width move with stereo_width 1.0 = no-op test ; should reject as identity neutre value.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "x"}],
    )
    with pytest.raises(MixAgentOutputError, match="no-op"):
        parse_spatial_decision(payload)


def test_spatial_check4_mono_with_extra_numeric_field_raises():
    """#4 : mono move_type forbids other value fields (numeric extra)."""
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        move_type="mono", pan=None, stereo_width=0.5,
        rationale="Mono move with extra stereo_width value field should reject ; mono is the move_type signal.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "mono"}],
    )
    with pytest.raises(MixAgentOutputError, match="extra value"):
        parse_spatial_decision(payload)


def test_spatial_check4_mono_with_extra_phase_channel_raises():
    """#4 audit Finding 3 : mono with phase_channel set also rejected
    (covers the second branch of the extras detection)."""
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        move_type="mono", pan=None, phase_channel="L",
        rationale="Mono move with extra phase_channel field should reject ; phase_flip and mono are distinct move types.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "mono"}],
    )
    with pytest.raises(MixAgentOutputError, match="extra value"):
        parse_spatial_decision(payload)


# Phase 4.5.1 audit Finding 1 : check #4 strictified to ALL move_types
# (was previously only mono). Each move_type allows exactly ONE value field.


def test_spatial_check4_pan_with_extra_stereo_width_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        move_type="pan", pan=0.0, stereo_width=0.7,  # extra
        rationale="Pan move with extra stereo_width value should reject ; each move_type owns one field.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "pan"}],
    )
    with pytest.raises(MixAgentOutputError, match="extra value"):
        parse_spatial_decision(payload)


def test_spatial_check4_phase_flip_with_extra_pan_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        move_type="phase_flip", pan=0.3, phase_channel="L",  # pan extra
        chain_position="chain_start",
        rationale="Phase flip move with extra pan field should reject ; phase_flip owns phase_channel only.",
        inspired_by=[{"kind": "diagnostic", "path": "Anomalies!x",
                      "excerpt": "Phase correlation -0.4"}],
    )
    with pytest.raises(MixAgentOutputError, match="extra value"):
        parse_spatial_decision(payload)


def test_spatial_check4_width_with_extra_balance_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        move_type="width", pan=None, stereo_width=0.7, balance=0.2,  # balance extra
        rationale="Width move with extra balance field should reject ; width owns stereo_width only.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "narrow"}],
    )
    with pytest.raises(MixAgentOutputError, match="extra value"):
        parse_spatial_decision(payload)


def test_spatial_check5_bass_mono_missing_freq_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        move_type="bass_mono", pan=None,
        rationale="Bass mono move without bass_mono_freq_hz cutoff set should reject required field check.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "bass mono"}],
    )
    with pytest.raises(MixAgentOutputError, match="bass_mono_freq_hz"):
        parse_spatial_decision(payload)


def test_spatial_check6_phase_flip_missing_channel_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        move_type="phase_flip", pan=None,
        rationale="Phase flip move without phase_channel L or R selection should reject required field check.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "phase"}],
    )
    with pytest.raises(MixAgentOutputError, match="phase_channel"):
        parse_spatial_decision(payload)


def test_spatial_check6_phase_flip_invalid_channel_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        move_type="phase_flip", pan=None, phase_channel="both",
        rationale="Phase flip move with invalid phase_channel value 'both' should reject ; only L or R allowed.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "phase"}],
    )
    with pytest.raises(MixAgentOutputError, match="phase_channel"):
        parse_spatial_decision(payload)


def test_spatial_check7_balance_missing_value_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        move_type="balance", pan=None,
        rationale="Balance move without balance value field set should reject required field check parser.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "balance"}],
    )
    with pytest.raises(MixAgentOutputError, match="balance"):
        parse_spatial_decision(payload)


def test_spatial_check8_balance_zero_no_op_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        move_type="balance", pan=None, balance=0.0,
        rationale="Balance move with balance 0.0 = center identity no-op test should reject as no shift.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "balance"}],
    )
    with pytest.raises(MixAgentOutputError, match="no-op"):
        parse_spatial_decision(payload)


def test_spatial_check9_ms_balance_missing_value_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        move_type="ms_balance", pan=None,
        rationale="MS balance move without mid_side_balance value field set should reject required field parser.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "ms"}],
    )
    with pytest.raises(MixAgentOutputError, match="mid_side_balance"):
        parse_spatial_decision(payload)


def test_spatial_check10_ms_balance_neutral_1_no_op_raises():
    """#10 : ms_balance == 1.0 (neutral) — NOT 0.0 which is full mid (audit Finding B/H)."""
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        move_type="ms_balance", pan=None, mid_side_balance=1.0,
        rationale="MS balance at 1.0 neutre identity no-op test ; should reject as no shift in real catalog encoding.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "ms"}],
    )
    with pytest.raises(MixAgentOutputError, match="no-op"):
        parse_spatial_decision(payload)


def test_spatial_check10_ms_balance_zero_is_full_mid_NOT_no_op():
    """Audit Finding B/H : ms_balance == 0.0 is FULL MID (legitimate),
    NOT no-op (which is 1.0). Common confusion to test against."""
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        track="Master Bus",
        move_type="ms_balance", pan=None, mid_side_balance=0.0,
        rationale="Master bus full mid focus at 0.0 = strong mid emphasis per brief 'kill the side ambience' ; legitimate.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "kill side"}],
    )
    decision = parse_spatial_decision(payload)
    # Should ACCEPT — 0.0 is full mid (extreme but legal), not no-op
    assert decision.value.moves[0].mid_side_balance == 0.0


def test_spatial_check11_short_rationale_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0]["rationale"] = "too short"
    with pytest.raises(MixAgentOutputError, match="rationale"):
        parse_spatial_decision(payload)


def test_spatial_check11_no_inspired_by_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0]["inspired_by"] = []
    with pytest.raises(MixAgentOutputError, match="inspired_by"):
        parse_spatial_decision(payload)


# ----------------------------------------------------------------------------
# Cross-correction duplicate check
# ----------------------------------------------------------------------------


def test_spatial_duplicate_track_move_type_raises():
    """Multiple SpatialMove on same (track, move_type) = ambiguous."""
    payload = _valid_spatial_payload()
    move_a = _valid_spatial_move(pan=0.0)
    move_b = _valid_spatial_move(pan=0.5)  # same track + same move_type "pan"
    payload["stereo_spatial"]["moves"] = [move_a, move_b]
    with pytest.raises(MixAgentOutputError, match="duplicate"):
        parse_spatial_decision(payload)


def test_spatial_same_track_distinct_move_types_accepted():
    """Same track + DIFFERENT move_type = legitimate (e.g. pan + width)."""
    payload = _valid_spatial_payload()
    pan_move = _valid_spatial_move(track="Pad", pan=0.3)
    width_move = _valid_spatial_move(
        track="Pad", move_type="width", pan=None, stereo_width=1.5,
        rationale="Pad slight widening at 1.5 per brief 'open up the pads' for ambient depth.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "open up"}],
    )
    payload["stereo_spatial"]["moves"] = [pan_move, width_move]
    decision = parse_spatial_decision(payload)
    assert len(decision.value.moves) == 2
    assert decision.value.moves[0].move_type == "pan"
    assert decision.value.moves[1].move_type == "width"


# ----------------------------------------------------------------------------
# Scenario coverage (happy paths for each move_type)
# ----------------------------------------------------------------------------


def test_spatial_scenario_c_phase_flip_happy_path():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        track="Overheads",
        move_type="phase_flip", pan=None,
        phase_channel="L",
        chain_position="chain_start",
        rationale="Overheads stereo correlation -0.42 critical anomaly ; flip L channel to restore mono compat per Anomaly trigger.",
        inspired_by=[
            {"kind": "diagnostic", "path": "Anomalies!Overheads",
             "excerpt": "Phase correlation -0.42 - serious mono compatibility issue"},
        ],
    )
    decision = parse_spatial_decision(payload)
    assert decision.value.moves[0].phase_channel == "L"
    assert decision.value.moves[0].chain_position == "chain_start"


def test_spatial_scenario_e_mono_happy_path():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        track="Kick DI",
        move_type="mono", pan=None,
        rationale="Kick DI must be mono per brief 'force kick mono' ; standard practice for sub-content tracks.",
        inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "force kick mono"}],
    )
    decision = parse_spatial_decision(payload)
    assert decision.value.moves[0].move_type == "mono"
    # All other value fields should be None (parser enforces)
    m = decision.value.moves[0]
    assert m.pan is None
    assert m.stereo_width is None
    assert m.bass_mono_freq_hz is None


def test_spatial_scenario_g_ms_balance_more_side_happy_path():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0] = _valid_spatial_move(
        track="Master Bus",
        move_type="ms_balance", pan=None,
        mid_side_balance=1.4,  # > 1.0 = more side
        rationale="Master bus slight more side emphasis at 1.4 per brief 'more space' + Mix Health Stereo Image 58.",
        inspired_by=[
            {"kind": "user_brief", "path": "b", "excerpt": "more space"},
            {"kind": "diagnostic", "path": "Mix Health Score!Stereo Image",
             "excerpt": "Stereo Image 58/100"},
        ],
    )
    decision = parse_spatial_decision(payload)
    assert decision.value.moves[0].mid_side_balance == 1.4


# ----------------------------------------------------------------------------
# Chain position
# ----------------------------------------------------------------------------


@pytest.mark.parametrize("position", sorted(VALID_SPATIAL_CHAIN_POSITIONS))
def test_spatial_all_valid_chain_positions_parse(position):
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0]["chain_position"] = position
    decision = parse_spatial_decision(payload)
    assert decision.value.moves[0].chain_position == position


def test_spatial_invalid_chain_position_raises():
    payload = _valid_spatial_payload()
    payload["stereo_spatial"]["moves"][0]["chain_position"] = "post_saturation"
    with pytest.raises(MixAgentOutputError, match="chain_position"):
        parse_spatial_decision(payload)


# ----------------------------------------------------------------------------
# from_response (markdown fences, prose around)
# ----------------------------------------------------------------------------


def test_spatial_from_response_handles_fences():
    payload_str = json.dumps(_valid_spatial_payload())
    fenced = f"```json\n{payload_str}\n```"
    decision = parse_spatial_decision_from_response(fenced)
    assert len(decision.value.moves) == 1


def test_spatial_from_response_handles_prose():
    payload_str = json.dumps(_valid_spatial_payload())
    prosed = f"Here are spatial decisions:\n{payload_str}\nDone."
    decision = parse_spatial_decision_from_response(prosed)
    assert len(decision.value.moves) == 1


@pytest.mark.parametrize("mt", sorted(VALID_SPATIAL_MOVE_TYPES))
def test_spatial_all_valid_move_types_can_be_parsed(mt):
    """Smoke : each valid move_type can produce a coherent move."""
    payload = _valid_spatial_payload()
    if mt == "pan":
        m = _valid_spatial_move()
    elif mt == "width":
        m = _valid_spatial_move(
            move_type=mt, pan=None, stereo_width=0.7,
            rationale="Width narrow at 0.7 per Anomaly 'Very wide stereo image' for mono compat protection.",
            inspired_by=[{"kind": "diagnostic", "path": "Anomalies!x", "excerpt": "Very wide stereo image"}],
        )
    elif mt == "mono":
        m = _valid_spatial_move(
            track="Kick DI", move_type=mt, pan=None,
            rationale="Kick DI mono summing per brief 'kick mono' ; sub content best mono for clarity.",
            inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "kick mono"}],
        )
    elif mt == "bass_mono":
        m = _valid_spatial_move(
            move_type=mt, pan=None, bass_mono_freq_hz=120.0,
            rationale="Bass mono at 120 Hz per brief 'tighten low end stereo' standard sub-mono cutoff.",
            inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "tighten low end"}],
        )
    elif mt == "phase_flip":
        m = _valid_spatial_move(
            move_type=mt, pan=None, phase_channel="R",
            chain_position="chain_start",
            rationale="Phase flip R per Anomaly Phase correlation critical on overheads stereo content.",
            inspired_by=[{"kind": "diagnostic", "path": "Anomalies!x", "excerpt": "Phase correlation -0.4"}],
        )
    elif mt == "balance":
        m = _valid_spatial_move(
            move_type=mt, pan=None, balance=0.2,
            rationale="Balance R+0.2 per brief 'right side too quiet' on stereo recording asymmetry repair.",
            inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "right side too quiet"}],
        )
    elif mt == "ms_balance":
        m = _valid_spatial_move(
            move_type=mt, pan=None, mid_side_balance=0.7,
            rationale="MS balance more mid at 0.7 per brief 'vocal forward focus' + Mix Health Stereo Image 60.",
            inspired_by=[{"kind": "user_brief", "path": "b", "excerpt": "vocal forward"}],
        )
    payload["stereo_spatial"]["moves"][0] = m
    decision = parse_spatial_decision(payload)
    assert decision.value.moves[0].move_type == mt


# ============================================================================
# Phase 4.6 — Chain build lane parser
# ============================================================================


from mix_engine.blueprint import (
    ChainBuildDecision,
    ChainSlot,
    TrackChainPlan,
    CHAIN_MAX_POSITION,
    EQ8_MAX_BANDS_PER_INSTANCE,
    VALID_CHAIN_DEVICES,
    VALID_CONSUMES_LANES,
    parse_chain_decision,
    parse_chain_decision_from_response,
)


def _valid_chain_slot(**overrides) -> dict:
    base = {
        "position": 2,
        "device": "Eq8",
        "is_preexisting": False,
        "instance": 0,
        "consumes_lane": "eq_corrective",
        "consumes_indices": [0, 1, 2],
        "purpose": "corrective_eq",
    }
    base.update(overrides)
    return base


def _valid_chain_plan(**overrides) -> dict:
    base = {
        "track": "Bass A",
        "slots": [
            _valid_chain_slot(position=0, device="Gate",
                              consumes_lane="dynamics_corrective",
                              consumes_indices=[0], purpose="gate"),
            _valid_chain_slot(position=2),
            _valid_chain_slot(position=3, device="Compressor2",
                              consumes_lane="dynamics_corrective",
                              consumes_indices=[1], purpose="comp"),
        ],
        "rationale": "Bass A multi-family chain : Gate first cleans noise, Eq8 corrective post-Gate, Compressor2 post-EQ controls dynamics.",
        "inspired_by": [
            {"kind": "diagnostic", "path": "blueprint.eq_corrective.bands[0..2]",
             "excerpt": "3 corrective EQ bands targeting Bass A"},
        ],
    }
    base.update(overrides)
    return base


def _valid_chain_payload(**overrides) -> dict:
    base = {
        "schema_version": "1.0",
        "chain": {"plans": [_valid_chain_plan()]},
        "cited_by": [
            {"kind": "als_state", "path": "tracks", "excerpt": "1 plan emitted"},
        ],
        "rationale": "1 chain plan : Bass A multi-family.",
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------------------------
# Happy paths
# ----------------------------------------------------------------------------


def test_chain_parses_minimum_valid_payload():
    decision = parse_chain_decision(_valid_chain_payload())
    assert decision.lane == "chain"
    assert isinstance(decision.value, ChainBuildDecision)
    assert len(decision.value.plans) == 1
    plan = decision.value.plans[0]
    assert plan.track == "Bass A"
    assert len(plan.slots) == 3
    assert plan.slots[0].device == "Gate"
    assert plan.slots[2].device == "Compressor2"


def test_chain_decision_assignable_to_blueprint():
    from mix_engine.blueprint import MixBlueprint
    decision = parse_chain_decision(_valid_chain_payload())
    bp = MixBlueprint(name="session").with_decision("chain", decision)
    assert bp.chain is decision
    assert bp.filled_lanes() == ("chain",)


def test_chain_unsupported_schema_version_raises():
    payload = _valid_chain_payload()
    payload["schema_version"] = "99.0"
    with pytest.raises(MixAgentOutputError, match="schema_version"):
        parse_chain_decision(payload)


def test_chain_error_payload_raises():
    with pytest.raises(MixAgentOutputError, match="agent refused"):
        parse_chain_decision({"error": "no Tier A decisions", "details": "blueprint empty"})


def test_chain_empty_plans_accepted():
    """Blueprint with no Tier A decisions targeting any track → plans=[]."""
    payload = _valid_chain_payload()
    payload["chain"]["plans"] = []
    payload["rationale"] = "Aucune Tier A decision à réconcilier."
    decision = parse_chain_decision(payload)
    assert decision.value.plans == ()


# ----------------------------------------------------------------------------
# Slot-level cross-field checks (#1-#6)
# ----------------------------------------------------------------------------


def test_chain_check1_preexisting_with_consumes_lane_raises():
    """#1 : is_preexisting=True with consumes_lane set is contradiction."""
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"][1] = _valid_chain_slot(
        position=2, device="Reverb",
        is_preexisting=True,
        consumes_lane="eq_corrective",  # contradiction
        consumes_indices=[],
    )
    with pytest.raises(MixAgentOutputError, match="preserved device has no lane"):
        parse_chain_decision(payload)


def test_chain_check2_preexisting_with_consumes_indices_raises():
    """#2 : is_preexisting=True with consumes_indices non-empty is contradiction."""
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"][1] = _valid_chain_slot(
        position=2, device="Reverb",
        is_preexisting=True,
        consumes_lane=None,
        consumes_indices=[0, 1],  # contradiction
    )
    with pytest.raises(MixAgentOutputError, match="no source decisions"):
        parse_chain_decision(payload)


def test_chain_check3_non_preexisting_unknown_device_raises():
    """#3 : non-preexisting device must be in VALID_CHAIN_DEVICES."""
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"][1]["device"] = "ProQ3"  # not mapped
    with pytest.raises(MixAgentOutputError, match="set is_preexisting=True"):
        parse_chain_decision(payload)


def test_chain_check3_preexisting_allows_unmapped_device():
    """Mirror : preexisting bypasses VALID_CHAIN_DEVICES check (Reverb,
    Tuner, 3rd-party VSTs preserved from track.devices)."""
    payload = _valid_chain_payload()
    # Replace 3 slots with one preexisting Reverb (sole slot)
    payload["chain"]["plans"][0]["slots"] = [
        _valid_chain_slot(
            position=5, device="Reverb",  # not in VALID_CHAIN_DEVICES
            is_preexisting=True, consumes_lane=None, consumes_indices=[],
            purpose="preserved_reverb",
        ),
    ]
    decision = parse_chain_decision(payload)
    assert decision.value.plans[0].slots[0].device == "Reverb"
    assert decision.value.plans[0].slots[0].is_preexisting is True


def test_chain_check4_non_preexisting_missing_consumes_lane_raises():
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"][1]["consumes_lane"] = None
    with pytest.raises(MixAgentOutputError, match="consumes_lane"):
        parse_chain_decision(payload)


def test_chain_check4_invalid_consumes_lane_raises():
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"][1]["consumes_lane"] = "fx_decider"
    with pytest.raises(MixAgentOutputError, match="must be in"):
        parse_chain_decision(payload)


def test_chain_check5_non_preexisting_empty_consumes_indices_raises():
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"][1]["consumes_indices"] = []
    with pytest.raises(MixAgentOutputError, match="orphan"):
        parse_chain_decision(payload)


def test_chain_check6_eq8_8_band_budget_overflow_raises():
    """#6 : Eq8 instance with > 8 bands consumed = budget overflow."""
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"][1]["consumes_indices"] = list(range(9))  # 9 bands
    with pytest.raises(MixAgentOutputError, match="8-band"):
        parse_chain_decision(payload)


def test_chain_eq8_exactly_8_bands_accepted():
    """Edge case : exactly EQ8_MAX_BANDS_PER_INSTANCE (8) bands accepted."""
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"][1]["consumes_indices"] = list(range(8))
    decision = parse_chain_decision(payload)
    assert len(decision.value.plans[0].slots[1].consumes_indices) == 8


# ----------------------------------------------------------------------------
# Plan-level cross-field checks (#7-#9)
# ----------------------------------------------------------------------------


def test_chain_check7_position_not_monotone_raises():
    """#7 : slots positions must be strictly increasing."""
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"] = [
        _valid_chain_slot(position=2),
        _valid_chain_slot(position=0, device="Gate",
                          consumes_lane="dynamics_corrective",
                          consumes_indices=[0]),  # out of order
    ]
    payload["chain"]["plans"][0]["rationale"] = "Test position not monotone — should reject as out-of-order positions in plan."
    with pytest.raises(MixAgentOutputError, match="strictly increasing"):
        parse_chain_decision(payload)


def test_chain_check7_duplicate_position_raises():
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"] = [
        _valid_chain_slot(position=2, device="Eq8", consumes_indices=[0]),
        _valid_chain_slot(position=2, device="Compressor2",
                          consumes_lane="dynamics_corrective",
                          consumes_indices=[0]),  # duplicate position
    ]
    payload["chain"]["plans"][0]["rationale"] = "Test duplicate position in plan should reject as collision in monotone increasing requirement."
    with pytest.raises(MixAgentOutputError, match="strictly increasing"):
        parse_chain_decision(payload)


def test_chain_check8_limiter_at_max_position_accepted():
    """#8 : Limiter at max position in plan = OK (terminal placement
    enforced but absolute slot varies per plan length, audit Pass 2 #3)."""
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"] = [
        _valid_chain_slot(position=0, device="Gate",
                          consumes_lane="dynamics_corrective",
                          consumes_indices=[0], purpose="gate"),
        _valid_chain_slot(position=2),
        _valid_chain_slot(position=3, device="Limiter",
                          consumes_lane="dynamics_corrective",
                          consumes_indices=[1], purpose="limiter"),
    ]
    decision = parse_chain_decision(payload)
    # Limiter at position 3 = max in this plan (only 3 slots) — accepted
    limiter_slots = [s for s in decision.value.plans[0].slots if s.device == "Limiter"]
    assert len(limiter_slots) == 1
    assert limiter_slots[0].position == 3


def test_chain_check8_limiter_not_at_max_raises():
    """#8 : Limiter at non-max position in plan = invalid (terminal violation)."""
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"] = [
        _valid_chain_slot(position=0, device="Limiter",
                          consumes_lane="dynamics_corrective",
                          consumes_indices=[0], purpose="limiter"),
        _valid_chain_slot(position=2),  # AFTER Limiter — invalid
    ]
    payload["chain"]["plans"][0]["rationale"] = "Test Limiter not at max position — should reject as Limiter must be terminal in chain."
    with pytest.raises(MixAgentOutputError, match="terminal"):
        parse_chain_decision(payload)


def test_chain_check9_short_rationale_raises():
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["rationale"] = "too short"
    with pytest.raises(MixAgentOutputError, match="rationale"):
        parse_chain_decision(payload)


def test_chain_check9_no_inspired_by_raises():
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["inspired_by"] = []
    with pytest.raises(MixAgentOutputError, match="inspired_by"):
        parse_chain_decision(payload)


# ----------------------------------------------------------------------------
# Cross-correction duplicate-key check
# ----------------------------------------------------------------------------


def test_chain_duplicate_track_plans_raises():
    payload = _valid_chain_payload()
    plan_a = _valid_chain_plan()
    plan_b = _valid_chain_plan()  # same track "Bass A"
    payload["chain"]["plans"] = [plan_a, plan_b]
    with pytest.raises(MixAgentOutputError, match="duplicate"):
        parse_chain_decision(payload)


# ----------------------------------------------------------------------------
# Position range
# ----------------------------------------------------------------------------


def test_chain_position_above_max_raises():
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"][2]["position"] = CHAIN_MAX_POSITION + 1
    with pytest.raises(MixAgentOutputError, match="position"):
        parse_chain_decision(payload)


def test_chain_position_negative_raises():
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"][0]["position"] = -1
    with pytest.raises(MixAgentOutputError, match="position"):
        parse_chain_decision(payload)


def test_chain_consumes_indices_negative_raises():
    """Phase 4.6.1 audit Finding 2 : negative indices rejected (Python
    -1 = last semantics would silently re-target Tier B reads)."""
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"][1]["consumes_indices"] = [0, 1, -1]
    with pytest.raises(MixAgentOutputError, match="negative indexing"):
        parse_chain_decision(payload)


# ----------------------------------------------------------------------------
# Scenario coverage
# ----------------------------------------------------------------------------


def test_chain_scenario_c_eq8_overflow_split_accepted():
    """Scenario C : > 8 bands split into multiple Eq8 instances cascaded."""
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"] = [
        _valid_chain_slot(
            position=2, device="Eq8", instance=0,
            consumes_lane="eq_corrective",
            consumes_indices=list(range(8)),  # bands 0-7 in instance 0
            purpose="corrective_eq_part1",
        ),
        _valid_chain_slot(
            position=3, device="Eq8", instance=1,
            consumes_lane="eq_corrective",
            consumes_indices=[8, 9, 10],  # bands 8-10 in instance 1
            purpose="corrective_eq_part2",
        ),
    ]
    decision = parse_chain_decision(payload)
    eq8_slots = [s for s in decision.value.plans[0].slots if s.device == "Eq8"]
    assert len(eq8_slots) == 2
    assert eq8_slots[0].instance == 0
    assert eq8_slots[1].instance == 1


def test_chain_scenario_d_ms_split_accepted():
    """Scenario D : different processing_modes → multiple Eq8 instances
    one per mode (Eq8.Mode_global is device-level)."""
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0]["slots"] = [
        _valid_chain_slot(
            position=2, device="Eq8", instance=0,
            consumes_indices=[0, 1],  # stereo bands
            purpose="corrective_eq_stereo",
        ),
        _valid_chain_slot(
            position=3, device="Eq8", instance=1,
            consumes_indices=[2, 3],  # mid bands
            purpose="corrective_eq_mid",
        ),
    ]
    decision = parse_chain_decision(payload)
    assert len(decision.value.plans[0].slots) == 2


def test_chain_scenario_f_pure_preservation_accepted():
    """Scenario F : track with only existing devices, no Tier A decisions."""
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0] = _valid_chain_plan(
        track="Tuner Track",
        slots=[
            _valid_chain_slot(
                position=0, device="Tuner",
                is_preexisting=True, consumes_lane=None, consumes_indices=[],
                purpose="preserved_tuner",
            ),
            _valid_chain_slot(
                position=1, device="Eq8",
                is_preexisting=True, consumes_lane=None, consumes_indices=[],
                purpose="preserved_eq",
            ),
        ],
        rationale="Pure preservation : Tuner Track has Tuner + Eq8 already, no Tier A decisions targeting it. Preserve order.",
    )
    decision = parse_chain_decision(payload)
    assert all(s.is_preexisting for s in decision.value.plans[0].slots)


def test_chain_scenario_e_cross_lane_notes_accepted():
    """Scenario E : cross-lane composition awareness via cross_lane_notes."""
    payload = _valid_chain_payload()
    payload["chain"]["plans"][0] = _valid_chain_plan(
        cross_lane_notes=[
            "EQ band processing_mode='mid' on slot 2 + StereoGain ms_balance=0.7 on slot 6 : composition cumulative effect ; M-filtered then global M/S amplitude shift. Document for safety-guardian.",
        ],
    )
    decision = parse_chain_decision(payload)
    assert len(decision.value.plans[0].cross_lane_notes) == 1


# ----------------------------------------------------------------------------
# from_response (markdown fences, prose around)
# ----------------------------------------------------------------------------


def test_chain_from_response_handles_fences():
    payload_str = json.dumps(_valid_chain_payload())
    fenced = f"```json\n{payload_str}\n```"
    decision = parse_chain_decision_from_response(fenced)
    assert len(decision.value.plans) == 1


def test_chain_from_response_handles_prose():
    payload_str = json.dumps(_valid_chain_payload())
    prosed = f"Chain plans:\n{payload_str}\nDone."
    decision = parse_chain_decision_from_response(prosed)
    assert len(decision.value.plans) == 1


# ----------------------------------------------------------------------------
# DAG cohérence
# ----------------------------------------------------------------------------


def test_chain_dag_dependencies_include_corrective_trio_plus_routing():
    """Verify Phase 4.6 audit fix : chain depends on stereo_spatial AND
    routing in addition to eq_corrective + dynamics_corrective + future
    eq_creative + saturation_color."""
    from mix_engine.director.director import MIX_DEPENDENCIES
    chain_deps = MIX_DEPENDENCIES["chain"]
    assert "eq_corrective" in chain_deps
    assert "dynamics_corrective" in chain_deps
    assert "stereo_spatial" in chain_deps  # audit pre-empt fix
    assert "routing" in chain_deps          # audit pre-empt fix


# ============================================================================
# Phase 4.7 — Per-track audio metrics + genre context absorption
# ============================================================================


from mix_engine.blueprint import (
    CANONICAL_BAND_COUNT,
    CANONICAL_BAND_LABELS,
    SPECTRAL_PEAKS_MAX,
    GenreContext,
    SpectralPeak,
    TrackAudioMetrics,
    VALID_DENSITY_TOLERANCES,
    VALID_GENRE_FAMILIES,
)


def _valid_audio_metrics(**overrides) -> dict:
    """Minimum-valid TrackAudioMetrics dict (mono case)."""
    base = {
        "peak_db": -3.2,
        "true_peak_db": -2.8,
        "rms_db": -18.5,
        "lufs_integrated": -14.2,
        "lufs_short_term_max": -10.5,
        "lra": 8.5,
        "crest_factor": 14.7,
        "plr": 10.5,
        "psr": 11.2,
        "dominant_band": "bass",
        "centroid_hz": 2150.0,
        "rolloff_hz": 8500.0,
        "spectral_flatness": 0.15,
        "band_energies": [15.2, 35.8, 18.5, 12.3, 9.5, 5.2, 3.5],  # 7 bands
        "spectral_peaks": [
            {"frequency_hz": 247.0, "magnitude_db": -3.5},
            {"frequency_hz": 120.0, "magnitude_db": -8.2},
        ],
        "num_onsets": 180,
        "onsets_per_second": 2.5,
        "is_stereo": False,
        # mono → stereo fields all None
        "is_tonal": True,
        "dominant_note": "C",
        "tonal_strength": 0.78,
    }
    base.update(overrides)
    return base


def _valid_genre_context(**overrides) -> dict:
    base = {
        "family": "electronic_aggressive",
        "target_lufs_mix": -8.0,
        "typical_crest_mix": 8.0,
        "density_tolerance": "very_high",
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------------------------
# Backward-compat (CRITICAL — existing fixtures must still parse)
# ----------------------------------------------------------------------------


def test_phase47_diagnostic_report_backward_compat_no_audio_metrics():
    """Existing fixture without audio_metrics still parses, audio_metrics=None."""
    decision = parse_diagnostic_decision(_valid_payload())
    for t in decision.value.tracks:
        assert t.audio_metrics is None


def test_phase47_diagnostic_report_backward_compat_no_genre_context():
    decision = parse_diagnostic_decision(_valid_payload())
    assert decision.value.genre_context is None


# ----------------------------------------------------------------------------
# TrackAudioMetrics happy paths (mono + stereo)
# ----------------------------------------------------------------------------


def test_phase47_audio_metrics_mono_happy_path():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics()
    decision = parse_diagnostic_decision(payload)
    am = decision.value.tracks[0].audio_metrics
    assert am is not None
    assert am.peak_db == -3.2
    assert am.lra == 8.5
    assert am.dominant_band == "bass"
    assert len(am.band_energies) == 7
    assert am.is_stereo is False
    assert am.correlation is None
    assert am.is_tonal is True


def test_phase47_audio_metrics_stereo_happy_path():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        is_stereo=True,
        correlation=0.85,
        width_overall=0.45,
        width_per_band=[0.1, 0.2, 0.3, 0.5, 0.6, 0.4, 0.3],
    )
    decision = parse_diagnostic_decision(payload)
    am = decision.value.tracks[0].audio_metrics
    assert am.is_stereo is True
    assert am.correlation == 0.85
    assert am.width_overall == 0.45
    assert len(am.width_per_band) == 7


def test_phase47_audio_metrics_partial_population_per_track():
    """Lazy absorption : some tracks have audio_metrics, others don't."""
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics()
    # tracks[1] has no audio_metrics (still parses)
    decision = parse_diagnostic_decision(payload)
    assert decision.value.tracks[0].audio_metrics is not None
    assert decision.value.tracks[1].audio_metrics is None


# ----------------------------------------------------------------------------
# Range checks
# ----------------------------------------------------------------------------


def test_phase47_audio_metrics_peak_db_out_of_range():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(peak_db=50.0)
    with pytest.raises(MixAgentOutputError, match="peak_db"):
        parse_diagnostic_decision(payload)


def test_phase47_audio_metrics_lra_negative():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(lra=-1.0)
    with pytest.raises(MixAgentOutputError, match="lra"):
        parse_diagnostic_decision(payload)


def test_phase47_audio_metrics_crest_factor_extreme():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(crest_factor=100.0)
    with pytest.raises(MixAgentOutputError, match="crest_factor"):
        parse_diagnostic_decision(payload)


def test_phase47_audio_metrics_centroid_above_nyquist_max():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(centroid_hz=30000.0)
    with pytest.raises(MixAgentOutputError, match="centroid_hz"):
        parse_diagnostic_decision(payload)


def test_phase47_audio_metrics_negative_onsets():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(num_onsets=-5)
    with pytest.raises(MixAgentOutputError, match="num_onsets"):
        parse_diagnostic_decision(payload)


# ----------------------------------------------------------------------------
# Cross-field check #1 — NaN rejection
# ----------------------------------------------------------------------------


def test_phase47_audio_metrics_nan_rejected():
    """NaN floats are rejected explicitly — mix-diagnostician must normalize."""
    import math
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        peak_db=float("nan")
    )
    with pytest.raises(MixAgentOutputError, match="NaN"):
        parse_diagnostic_decision(payload)


# ----------------------------------------------------------------------------
# Cross-field check #2 — is_stereo coherence
# ----------------------------------------------------------------------------


def test_phase47_audio_metrics_mono_with_correlation_set_raises():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        is_stereo=False, correlation=0.5,
    )
    with pytest.raises(MixAgentOutputError, match="is_stereo=False"):
        parse_diagnostic_decision(payload)


def test_phase47_audio_metrics_mono_with_width_overall_set_raises():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        is_stereo=False, width_overall=0.3,
    )
    with pytest.raises(MixAgentOutputError, match="is_stereo=False"):
        parse_diagnostic_decision(payload)


def test_phase47_audio_metrics_stereo_without_correlation_raises():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        is_stereo=True, width_overall=0.4,
        # correlation omis → required
    )
    with pytest.raises(MixAgentOutputError, match="correlation"):
        parse_diagnostic_decision(payload)


def test_phase47_audio_metrics_stereo_without_width_overall_raises():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        is_stereo=True, correlation=0.7,
        # width_overall omis → required
    )
    with pytest.raises(MixAgentOutputError, match="width_overall"):
        parse_diagnostic_decision(payload)


def test_phase47_audio_metrics_stereo_width_per_band_optional():
    """Stereo : width_per_band is optional (correlation + width_overall mandatory)."""
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        is_stereo=True, correlation=0.7, width_overall=0.4,
        # width_per_band omitted → OK
    )
    decision = parse_diagnostic_decision(payload)
    assert decision.value.tracks[0].audio_metrics.width_per_band is None


# ----------------------------------------------------------------------------
# Cross-field check #3/#4 — band_energies + width_per_band len exact 7
# ----------------------------------------------------------------------------


def test_phase47_audio_metrics_band_energies_wrong_length_6():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        band_energies=[10.0, 20.0, 30.0, 25.0, 10.0, 5.0],  # only 6
    )
    with pytest.raises(MixAgentOutputError, match="band_energies"):
        parse_diagnostic_decision(payload)


def test_phase47_audio_metrics_width_per_band_wrong_length():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        is_stereo=True, correlation=0.7, width_overall=0.4,
        width_per_band=[0.1, 0.2, 0.3],  # only 3
    )
    with pytest.raises(MixAgentOutputError, match="width_per_band"):
        parse_diagnostic_decision(payload)


# ----------------------------------------------------------------------------
# Cross-field check #5 — spectral_peaks cap + descending order
# ----------------------------------------------------------------------------


def test_phase47_audio_metrics_spectral_peaks_above_max_raises():
    """SPECTRAL_PEAKS_MAX = 10 cap."""
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        spectral_peaks=[
            {"frequency_hz": 100.0 + i * 50, "magnitude_db": -5.0 - i * 0.5}
            for i in range(11)  # 11 > 10 cap
        ],
    )
    with pytest.raises(MixAgentOutputError, match="spectral_peaks"):
        parse_diagnostic_decision(payload)


def test_phase47_audio_metrics_spectral_peaks_not_descending_raises():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        spectral_peaks=[
            {"frequency_hz": 100.0, "magnitude_db": -10.0},
            {"frequency_hz": 247.0, "magnitude_db": -3.5},  # higher = should be first
        ],
    )
    with pytest.raises(MixAgentOutputError, match="DESCENDING"):
        parse_diagnostic_decision(payload)


def test_phase47_audio_metrics_spectral_peaks_empty_accepted():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        spectral_peaks=[],
    )
    decision = parse_diagnostic_decision(payload)
    assert decision.value.tracks[0].audio_metrics.spectral_peaks == ()


# ----------------------------------------------------------------------------
# Cross-field check #6 — dominant_band ∈ CANONICAL_BAND_LABELS
# ----------------------------------------------------------------------------


def test_phase47_audio_metrics_invalid_dominant_band_raises():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        dominant_band="treble"  # not in canonical 7
    )
    with pytest.raises(MixAgentOutputError, match="dominant_band"):
        parse_diagnostic_decision(payload)


@pytest.mark.parametrize("band", sorted(CANONICAL_BAND_LABELS))
def test_phase47_audio_metrics_all_canonical_bands_accepted(band):
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        dominant_band=band
    )
    decision = parse_diagnostic_decision(payload)
    assert decision.value.tracks[0].audio_metrics.dominant_band == band


# ----------------------------------------------------------------------------
# GenreContext
# ----------------------------------------------------------------------------


def test_phase47_genre_context_minimum_valid():
    payload = _valid_payload()
    payload["diagnostic"]["genre_context"] = _valid_genre_context()
    decision = parse_diagnostic_decision(payload)
    gc = decision.value.genre_context
    assert gc is not None
    assert gc.family == "electronic_aggressive"
    assert gc.target_lufs_mix == -8.0
    assert gc.density_tolerance == "very_high"


def test_phase47_genre_context_invalid_family_raises():
    payload = _valid_payload()
    payload["diagnostic"]["genre_context"] = _valid_genre_context(family="metal")
    with pytest.raises(MixAgentOutputError, match="family"):
        parse_diagnostic_decision(payload)


def test_phase47_genre_context_invalid_density_tolerance_raises():
    payload = _valid_payload()
    payload["diagnostic"]["genre_context"] = _valid_genre_context(
        density_tolerance="extreme"
    )
    with pytest.raises(MixAgentOutputError, match="density_tolerance"):
        parse_diagnostic_decision(payload)


def test_phase47_genre_context_target_lufs_out_of_range():
    payload = _valid_payload()
    payload["diagnostic"]["genre_context"] = _valid_genre_context(
        target_lufs_mix=-50.0  # below TARGET_LUFS_MIX_MIN=-30
    )
    with pytest.raises(MixAgentOutputError, match="target_lufs_mix"):
        parse_diagnostic_decision(payload)


@pytest.mark.parametrize("family", sorted(VALID_GENRE_FAMILIES))
def test_phase47_all_valid_genre_families_parse(family):
    payload = _valid_payload()
    payload["diagnostic"]["genre_context"] = _valid_genre_context(family=family)
    decision = parse_diagnostic_decision(payload)
    assert decision.value.genre_context.family == family


@pytest.mark.parametrize("dt", sorted(VALID_DENSITY_TOLERANCES))
def test_phase47_all_valid_density_tolerances_parse(dt):
    payload = _valid_payload()
    payload["diagnostic"]["genre_context"] = _valid_genre_context(density_tolerance=dt)
    decision = parse_diagnostic_decision(payload)
    assert decision.value.genre_context.density_tolerance == dt


# ----------------------------------------------------------------------------
# Full integration smoke test
# ----------------------------------------------------------------------------


def test_phase47_audio_metrics_is_tonal_false_with_dominant_note_raises():
    """Phase 4.7.0.1 audit Finding 3 : cross-field #7 is_tonal coherence.
    is_tonal=False signals non-tonal content ; dominant_note must be None."""
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        is_tonal=False,
        dominant_note="C",  # contradiction
    )
    with pytest.raises(MixAgentOutputError, match="is_tonal=False"):
        parse_diagnostic_decision(payload)


def test_phase47_audio_metrics_is_tonal_false_with_dominant_note_none_accepted():
    """Mirror of #7 : non-tonal with dominant_note None is correct."""
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        is_tonal=False,
        dominant_note=None,
        tonal_strength=0.05,
    )
    decision = parse_diagnostic_decision(payload)
    assert decision.value.tracks[0].audio_metrics.is_tonal is False
    assert decision.value.tracks[0].audio_metrics.dominant_note is None


def test_phase47_audio_metrics_centroid_24000_accepted():
    """Phase 4.7.0.1 audit Finding 2 : centroid_hz max bumped 22050→24000
    to cover 48 kHz Nyquist. Test that 24000 (Nyquist for 48 kHz) accepted."""
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        centroid_hz=24000.0,
    )
    decision = parse_diagnostic_decision(payload)
    assert decision.value.tracks[0].audio_metrics.centroid_hz == 24000.0


def test_phase47_audio_metrics_rolloff_above_24000_raises():
    """Above Nyquist for 48 kHz still rejected."""
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        rolloff_hz=25000.0,
    )
    with pytest.raises(MixAgentOutputError, match="rolloff_hz"):
        parse_diagnostic_decision(payload)


# ============================================================================
# Phase 4.8 — Automation lane parser
# ============================================================================


from mix_engine.blueprint import (
    AUTOMATION_MAX_TIME_BEATS,
    AUTOMATION_MAX_POINTS,
    AUTOMATION_MIN_POINTS,
    AutomationDecision,
    AutomationEnvelope,
    AutomationPoint,
    MASTER_TRACK_NAME,
    VALID_AUTOMATION_PURPOSES,
    VALID_AUTOMATION_TARGET_DEVICES,
    parse_automation_decision,
    parse_automation_decision_from_response,
)


def _valid_automation_envelope(**overrides) -> dict:
    """Default = mastering Limiter ceiling envelope (master bus scope)."""
    base = {
        "purpose": "mastering_master_bus",
        "target_track": "Master",
        "target_device": "Limiter",
        "target_param": "Ceiling",
        "target_device_instance": 0,
        "points": [
            {"time_beats": 0, "value": -1.0},
            {"time_beats": 16, "value": -0.5},
            {"time_beats": 32, "value": -1.0},
        ],
        "sections": [0, 1, 2],
        "rationale": "Master Limiter ceiling envelope per section : tighter -0.5 dB ceiling in chorus for loudness, -1 dB safety in verses + outro.",
        "inspired_by": [
            {"kind": "diagnostic", "path": "genre_context.target_lufs_mix",
             "excerpt": "electronic_aggressive target -8 LUFS"},
        ],
    }
    base.update(overrides)
    return base


def _valid_automation_payload(**overrides) -> dict:
    base = {
        "schema_version": "1.0",
        "automation": {"envelopes": [_valid_automation_envelope()]},
        "cited_by": [
            {"kind": "diagnostic", "path": "genre_context", "excerpt": "1 master automation"},
        ],
        "rationale": "1 master Limiter ceiling envelope automation per-section.",
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------------------------
# Happy paths
# ----------------------------------------------------------------------------


def test_automation_parses_minimum_valid():
    decision = parse_automation_decision(_valid_automation_payload())
    assert decision.lane == "automation"
    assert isinstance(decision.value, AutomationDecision)
    assert len(decision.value.envelopes) == 1
    env = decision.value.envelopes[0]
    assert env.purpose == "mastering_master_bus"
    assert env.target_track == "Master"
    assert len(env.points) == 3


def test_automation_decision_assignable_to_blueprint():
    from mix_engine.blueprint import MixBlueprint
    decision = parse_automation_decision(_valid_automation_payload())
    bp = MixBlueprint(name="session").with_decision("automation", decision)
    assert bp.automation is decision
    assert bp.filled_lanes() == ("automation",)


def test_automation_unsupported_schema_version_raises():
    payload = _valid_automation_payload()
    payload["schema_version"] = "99.0"
    with pytest.raises(MixAgentOutputError, match="schema_version"):
        parse_automation_decision(payload)


def test_automation_error_payload_raises():
    with pytest.raises(MixAgentOutputError, match="agent refused"):
        parse_automation_decision({"error": "no signal", "details": "..."})


def test_automation_empty_envelopes_accepted():
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"] = []
    payload["rationale"] = "Aucune envelope automation justifiée."
    decision = parse_automation_decision(payload)
    assert decision.value.envelopes == ()


# ----------------------------------------------------------------------------
# Purpose enum + creative OOS
# ----------------------------------------------------------------------------


@pytest.mark.parametrize("invalid_purpose",
                         ["creative_riser", "creative_drop_buildup",
                          "fx_swell", "Mastering", ""])
def test_automation_invalid_purpose_raises(invalid_purpose):
    """Creative purposes are out-of-scope Phase 4.8."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["purpose"] = invalid_purpose
    with pytest.raises(MixAgentOutputError, match="purpose"):
        parse_automation_decision(payload)


@pytest.mark.parametrize("purpose", sorted(VALID_AUTOMATION_PURPOSES))
def test_automation_all_valid_purposes_accepted(purpose):
    payload = _valid_automation_payload()
    if purpose == "corrective_per_section":
        payload["automation"]["envelopes"][0] = _valid_automation_envelope(
            purpose=purpose,
            target_track="Vocal Lead",
            target_device="Eq8",
            target_param="Gain",
            target_band_index=4,  # Eq8 band-specific
            points=[
                {"time_beats": 0, "value": 0.0},
                {"time_beats": 16, "value": -3.5},
                {"time_beats": 32, "value": 0.0},
            ],
            sections=[0, 1, 2],
            rationale="Vocal Lead sibilance only in chorus sections : Eq8 band 4 gain envelope cuts -3.5 dB at 7 kHz only when sibilance present.",
        )
    decision = parse_automation_decision(payload)
    assert decision.value.envelopes[0].purpose == purpose


# ----------------------------------------------------------------------------
# Target device + param checks
# ----------------------------------------------------------------------------


def test_automation_invalid_target_device_raises():
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["target_device"] = "Reverb"  # not in VALID set
    with pytest.raises(MixAgentOutputError, match="target_device"):
        parse_automation_decision(payload)


def test_automation_empty_target_param_raises():
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["target_param"] = ""
    with pytest.raises(MixAgentOutputError, match="target_param"):
        parse_automation_decision(payload)


# ----------------------------------------------------------------------------
# 8 cross-field checks
# ----------------------------------------------------------------------------


def test_automation_check1_points_too_few_raises():
    """#1 : envelope < 3 points."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["points"] = [
        {"time_beats": 0, "value": -1.0},
        {"time_beats": 16, "value": -0.5},
    ]
    with pytest.raises(MixAgentOutputError, match="≥ 3 points"):
        parse_automation_decision(payload)


def test_automation_check1_points_above_cap_raises():
    """#1 : envelope > AUTOMATION_MAX_POINTS sanity cap."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["points"] = [
        {"time_beats": i, "value": -1.0} for i in range(AUTOMATION_MAX_POINTS + 1)
    ]
    with pytest.raises(MixAgentOutputError, match="cap"):
        parse_automation_decision(payload)


def test_automation_check2_bars_not_ascending_raises():
    """#2 : bars must be strictly ascending no duplicates."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["points"] = [
        {"time_beats": 0, "value": -1.0},
        {"time_beats": 32, "value": -0.5},
        {"time_beats": 16, "value": -1.0},  # out of order
    ]
    with pytest.raises(MixAgentOutputError, match="ascending"):
        parse_automation_decision(payload)


def test_automation_check2_duplicate_bars_raises():
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["points"] = [
        {"time_beats": 0, "value": -1.0},
        {"time_beats": 16, "value": -0.5},
        {"time_beats": 16, "value": -0.7},  # duplicate
    ]
    with pytest.raises(MixAgentOutputError, match="ascending"):
        parse_automation_decision(payload)


def test_automation_check3_eq8_band_specific_param_requires_band_index():
    """#3 : Eq8 + Gain/Frequency/Q requires target_band_index."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0] = _valid_automation_envelope(
        purpose="corrective_per_section",
        target_track="Vocal Lead",
        target_device="Eq8",
        target_param="Gain",
        # target_band_index NOT set — should reject
        sections=[0, 1, 2],
        rationale="Eq8 Gain envelope without band_index — should reject : Eq8 has 8 bands, must specify which.",
    )
    with pytest.raises(MixAgentOutputError, match="target_band_index"):
        parse_automation_decision(payload)


def test_automation_check4_non_eq8_with_band_index_raises():
    """#4 : Non-Eq8 device must NOT have target_band_index set."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["target_band_index"] = 3  # Limiter doesn't have bands
    with pytest.raises(MixAgentOutputError, match="band_index"):
        parse_automation_decision(payload)


def test_automation_check4_band_index_out_of_range_raises():
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0] = _valid_automation_envelope(
        purpose="corrective_per_section",
        target_track="Vocal Lead",
        target_device="Eq8",
        target_param="Gain",
        target_band_index=8,  # invalid (max 7)
        sections=[0, 1, 2],
        rationale="Eq8 band_index=8 out of range test ; valid range is 0-7 (8 bands 0-indexed).",
    )
    with pytest.raises(MixAgentOutputError, match="target_band_index"):
        parse_automation_decision(payload)


def test_automation_check5_mastering_purpose_requires_master_track():
    """#5 : mastering_master_bus purpose requires target_track == Master."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["target_track"] = "Vocal Lead"  # not Master
    with pytest.raises(MixAgentOutputError, match="Master"):
        parse_automation_decision(payload)


def test_automation_check6_corrective_requires_sections():
    """#6 : corrective_per_section requires non-empty sections."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0] = _valid_automation_envelope(
        purpose="corrective_per_section",
        target_track="Vocal Lead",
        target_device="Compressor2",
        target_param="Threshold",
        sections=[],  # empty — should reject
        rationale="Corrective envelope without sections anchoring — should reject : envelope ambiguous without section context.",
    )
    with pytest.raises(MixAgentOutputError, match="sections"):
        parse_automation_decision(payload)


def test_automation_check7_short_rationale_raises():
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["rationale"] = "too short"
    with pytest.raises(MixAgentOutputError, match="rationale"):
        parse_automation_decision(payload)


def test_automation_check7_no_inspired_by_raises():
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["inspired_by"] = []
    with pytest.raises(MixAgentOutputError, match="inspired_by"):
        parse_automation_decision(payload)


# ----------------------------------------------------------------------------
# Cross-correction duplicate check (#8)
# ----------------------------------------------------------------------------


def test_automation_check8_duplicate_envelope_raises():
    """#8 : duplicate (track, device, instance, param, band_index) tuple."""
    payload = _valid_automation_payload()
    env_a = _valid_automation_envelope()
    env_b = _valid_automation_envelope(
        points=[
            {"time_beats": 0, "value": -2.0},
            {"time_beats": 16, "value": -1.0},
            {"time_beats": 32, "value": -2.0},
        ],
    )  # different points but same (track, device, instance, param) tuple
    payload["automation"]["envelopes"] = [env_a, env_b]
    with pytest.raises(MixAgentOutputError, match="duplicate"):
        parse_automation_decision(payload)


def test_automation_distinct_band_indices_accepted():
    """Same (track, device, instance, param) but distinct band_index = OK."""
    payload = _valid_automation_payload()
    env_a = _valid_automation_envelope(
        purpose="corrective_per_section",
        target_track="Vocal Lead",
        target_device="Eq8",
        target_param="Gain",
        target_band_index=4,  # band 4
        sections=[0, 1, 2],
        rationale="Eq8 band 4 gain envelope on Vocal Lead per chorus sections (sibilance variation).",
    )
    env_b = _valid_automation_envelope(
        purpose="corrective_per_section",
        target_track="Vocal Lead",
        target_device="Eq8",
        target_param="Gain",
        target_band_index=6,  # band 6 — distinct
        sections=[0, 1, 2],
        rationale="Eq8 band 6 gain envelope on Vocal Lead per chorus sections (presence boost only in chorus).",
    )
    payload["automation"]["envelopes"] = [env_a, env_b]
    decision = parse_automation_decision(payload)
    assert len(decision.value.envelopes) == 2


# ----------------------------------------------------------------------------
# Range checks
# ----------------------------------------------------------------------------


def test_automation_bar_above_max_raises():
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["points"] = [
        {"time_beats": 0, "value": -1.0},
        {"time_beats": 16, "value": -0.5},
        {"time_beats": AUTOMATION_MAX_TIME_BEATS + 1, "value": -1.0},  # above cap
    ]
    with pytest.raises(MixAgentOutputError, match="bar"):
        parse_automation_decision(payload)


def test_automation_negative_bar_raises():
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["points"] = [
        {"time_beats": -1, "value": -1.0},
        {"time_beats": 16, "value": -0.5},
        {"time_beats": 32, "value": -1.0},
    ]
    with pytest.raises(MixAgentOutputError, match="bar"):
        parse_automation_decision(payload)


# ----------------------------------------------------------------------------
# Scenario coverage (corrective + mastering happy paths)
# ----------------------------------------------------------------------------


def test_automation_corrective_eq8_band_envelope_happy_path():
    """Per-section sibilance correction via Eq8 band 4 gain envelope."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0] = _valid_automation_envelope(
        purpose="corrective_per_section",
        target_track="Vocal Lead",
        target_device="Eq8",
        target_param="Gain",
        target_band_index=4,
        points=[
            {"time_beats": 0, "value": 0.0},     # verse : no cut
            {"time_beats": 16, "value": -3.5},    # chorus : sibilance cut
            {"time_beats": 32, "value": 0.0},     # outro : no cut
        ],
        sections=[0, 1, 2],
        rationale="Vocal Lead sibilance variable per section : audio_metrics.spectral_peaks confirms 7kHz peak only in chorus ; envelope makes static -3.5dB cut dynamic.",
    )
    decision = parse_automation_decision(payload)
    env = decision.value.envelopes[0]
    assert env.purpose == "corrective_per_section"
    assert env.target_band_index == 4


def test_automation_corrective_compressor_threshold_envelope():
    """Per-section dynamics variation via Compressor2 threshold envelope."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0] = _valid_automation_envelope(
        purpose="corrective_per_section",
        target_track="Bass A",
        target_device="Compressor2",
        target_param="Threshold",
        points=[
            {"time_beats": 0, "value": -18.0},   # verse : less compression
            {"time_beats": 16, "value": -22.0},   # chorus : more compression
            {"time_beats": 32, "value": -18.0},
        ],
        sections=[0, 1, 2],
        rationale="Bass A dynamics range varies per section ; threshold envelope -18 verse / -22 chorus prevents pumping in verses while controlling chorus peaks.",
    )
    decision = parse_automation_decision(payload)
    assert decision.value.envelopes[0].target_param == "Threshold"


def test_automation_mastering_eq_tilt_envelope():
    """Master EQ tilt envelope (mastering scope)."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0] = _valid_automation_envelope(
        purpose="mastering_master_bus",
        target_track="Master",
        target_device="Eq8",
        target_param="Gain",
        target_band_index=6,  # presence band
        points=[
            {"time_beats": 0, "value": 0.0},
            {"time_beats": 16, "value": +1.5},   # subtle brightness in chorus
            {"time_beats": 32, "value": 0.0},
        ],
        sections=[0, 1, 2],
        rationale="Master EQ tilt subtle brightness boost in chorus per family electronic_dance preference ; +1.5dB at 6kHz only in chorus sections.",
    )
    decision = parse_automation_decision(payload)
    assert decision.value.envelopes[0].purpose == "mastering_master_bus"


def test_automation_mastering_stereo_width_envelope():
    """Master StereoGain.StereoWidth envelope per section."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0] = _valid_automation_envelope(
        purpose="mastering_master_bus",
        target_track="Master",
        target_device="StereoGain",
        target_param="StereoWidth",
        points=[
            {"time_beats": 0, "value": 1.0},     # verse : neutral
            {"time_beats": 16, "value": 1.4},    # chorus : wider
            {"time_beats": 32, "value": 1.0},
        ],
        sections=[0, 1, 2],
        rationale="Master stereo width envelope : neutral in verses (1.0), wider in chorus (1.4) for impact ; transitions at section boundaries.",
    )
    decision = parse_automation_decision(payload)
    assert decision.value.envelopes[0].target_param == "StereoWidth"


# ----------------------------------------------------------------------------
# from_response (markdown fences, prose around)
# ----------------------------------------------------------------------------


def test_automation_from_response_handles_fences():
    payload_str = json.dumps(_valid_automation_payload())
    fenced = f"```json\n{payload_str}\n```"
    decision = parse_automation_decision_from_response(fenced)
    assert len(decision.value.envelopes) == 1


def test_automation_from_response_handles_prose():
    payload_str = json.dumps(_valid_automation_payload())
    prosed = f"Automation envelopes:\n{payload_str}\nDone."
    decision = parse_automation_decision_from_response(prosed)
    assert len(decision.value.envelopes) == 1


# ----------------------------------------------------------------------------
# Phase 4.8.1 audit polish : edge case tests
# ----------------------------------------------------------------------------


def test_automation_empty_target_track_raises():
    """Phase 4.8.1 audit Finding 5 : empty target_track explicit rejection."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["target_track"] = ""
    with pytest.raises(MixAgentOutputError, match="target_track"):
        parse_automation_decision(payload)


def test_automation_target_param_case_sensitive():
    """Phase 4.8.1 audit : target_param strict case (no normalization).
    Agent emits canonical case ; lowercase variant should not be normalized."""
    payload = _valid_automation_payload()
    # "ceiling" lowercase — accepted (parser doesn't validate against device-mapping-oracle)
    # but Tier B will catch via param name lookup. Parser permissive by design.
    payload["automation"]["envelopes"][0]["target_param"] = "ceiling"
    decision = parse_automation_decision(payload)
    # Parser accepts free-form param name ; design choice (delegation to Tier B)
    assert decision.value.envelopes[0].target_param == "ceiling"


def test_automation_purpose_case_sensitive_strict():
    """Phase 4.8.1 audit : purpose enum is strict-case (cohérent avec autres
    Tier A patterns dynamics_type etc.). Capitalized variant rejected."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["purpose"] = "Mastering_Master_Bus"
    with pytest.raises(MixAgentOutputError, match="purpose"):
        parse_automation_decision(payload)


def test_automation_negative_target_device_instance_raises():
    """Phase 4.8.1 audit : target_device_instance must be >= 0."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["target_device_instance"] = -1
    with pytest.raises(MixAgentOutputError, match="target_device_instance"):
        parse_automation_decision(payload)


def test_automation_phase482_sub_beat_precision_accepted():
    """Phase 4.8.2 : float time_beats supports sub-beat precision aligned
    with mix_analyzer.py:analyze_temporal frame-level resolution (~11.6 ms).
    Sub-beat values like 0.25 (sixteenth-note) accepted."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["points"] = [
        {"time_beats": 0.0, "value": -1.0},
        {"time_beats": 0.25, "value": -0.8},     # 1/16 beat
        {"time_beats": 0.5, "value": -0.6},      # 1/8 beat
        {"time_beats": 1.0, "value": -0.5},      # 1/4 beat
        {"time_beats": 1.75, "value": -0.7},     # 7/16 beat
        {"time_beats": 2.0, "value": -1.0},      # 1/2 bar
    ]
    decision = parse_automation_decision(payload)
    points = decision.value.envelopes[0].points
    assert len(points) == 6
    assert points[1].time_beats == 0.25
    assert points[4].time_beats == 1.75


def test_automation_phase482_strict_ascending_with_floats():
    """Phase 4.8.2 : ascending order check works with float time_beats."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["points"] = [
        {"time_beats": 0.0, "value": -1.0},
        {"time_beats": 0.5, "value": -0.5},
        {"time_beats": 0.25, "value": -0.7},   # out of order
    ]
    with pytest.raises(MixAgentOutputError, match="ascending"):
        parse_automation_decision(payload)


def test_automation_phase482_pair_form_lenient():
    """Phase 4.8.2 : [time_beats, value] pair form still works (lenient parsing)."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["points"] = [
        [0.0, -1.0],
        [0.5, -0.5],
        [1.0, -0.8],
    ]
    decision = parse_automation_decision(payload)
    assert decision.value.envelopes[0].points[1].time_beats == 0.5


def test_automation_phase483_autofilter2_corrective_envelope():
    """Phase 4.8.3 : AutoFilter2 added to VALID_AUTOMATION_TARGET_DEVICES.
    Corrective use case : LPF cutoff sweep to hunt wandering resonance."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0] = _valid_automation_envelope(
        purpose="corrective_per_section",
        target_track="Synth Pad",
        target_device="AutoFilter2",
        target_param="Filter_Frequency",
        points=[
            {"time_beats": 0.0, "value": 8000.0},     # verse : cutoff at 8kHz
            {"time_beats": 64.0, "value": 6500.0},    # chorus : roll off resonance
            {"time_beats": 128.0, "value": 8000.0},
        ],
        sections=[0, 1, 2],
        rationale="AutoFilter2 LPF cutoff envelope on Synth Pad : roll off harsh resonance only in chorus per spectral_peaks evidence ; verse + outro keep full top end.",
    )
    decision = parse_automation_decision(payload)
    assert decision.value.envelopes[0].target_device == "AutoFilter2"
    assert decision.value.envelopes[0].target_param == "Filter_Frequency"


def test_automation_phase483_saturator_drive_envelope():
    """Phase 4.8.3 : Saturator added. Corrective use case : Drive
    modulation per section (less drive in sparse verse, full in chorus)."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0] = _valid_automation_envelope(
        purpose="corrective_per_section",
        target_track="Bass A",
        target_device="Saturator",
        target_param="PreDrive",
        points=[
            {"time_beats": 0.0, "value": 0.0},      # verse : minimal drive
            {"time_beats": 64.0, "value": 4.0},     # chorus : full drive
            {"time_beats": 128.0, "value": 0.0},
        ],
        sections=[0, 1, 2],
        rationale="Saturator PreDrive envelope on Bass A : verse needs cleaner low-end (0 drive), chorus benefits from harmonic excitement (4 drive) per density_tolerance + brief 'aggressive chorus'.",
    )
    decision = parse_automation_decision(payload)
    assert decision.value.envelopes[0].target_device == "Saturator"


def test_automation_phase483_smartlimit_mastering_envelope():
    """Phase 4.8.3 : SmartLimit (VST3) added for mastering scope."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0] = _valid_automation_envelope(
        purpose="mastering_master_bus",
        target_track="Master",
        target_device="SmartLimit",
        target_param="General_limiterThreshold",
        points=[
            {"time_beats": 0.0, "value": -1.0},
            {"time_beats": 64.0, "value": -0.5},   # tighter ceiling in chorus
            {"time_beats": 128.0, "value": -1.0},
        ],
        sections=[0, 1, 2],
        rationale="SmartLimit threshold envelope on Master per genre electronic_aggressive target -8 LUFS : tighter -0.5dB chorus, -1dB safety verse + outro.",
    )
    decision = parse_automation_decision(payload)
    assert decision.value.envelopes[0].target_device == "SmartLimit"


@pytest.mark.parametrize("device", sorted(VALID_AUTOMATION_TARGET_DEVICES))
def test_automation_phase483_all_devices_accepted(device):
    """Smoke : every device in VALID_AUTOMATION_TARGET_DEVICES emittable."""
    payload = _valid_automation_payload()
    # For Eq8 require band_index ; for Limiter avoid band_index ; etc.
    overrides = {"target_device": device, "target_param": "Gain"}
    if device == "Eq8":
        overrides["target_param"] = "Gain"
        overrides["target_band_index"] = 4
    elif device == "Limiter":
        overrides["target_param"] = "Ceiling"
    elif device == "Compressor2":
        overrides["target_param"] = "Threshold"
    elif device == "GlueCompressor":
        overrides["target_param"] = "Threshold"
    elif device == "Gate":
        overrides["target_param"] = "Threshold"
    elif device == "DrumBuss":
        overrides["target_param"] = "Drive"
    elif device == "StereoGain":
        overrides["target_param"] = "StereoWidth"
    elif device == "AutoFilter2":
        overrides["target_param"] = "Filter_Frequency"
    elif device == "Saturator":
        overrides["target_param"] = "PreDrive"
    elif device == "SmartLimit":
        overrides["target_param"] = "General_limiterThreshold"
        overrides["purpose"] = "mastering_master_bus"
        overrides["target_track"] = "Master"
    payload["automation"]["envelopes"][0] = _valid_automation_envelope(**overrides)
    decision = parse_automation_decision(payload)
    assert decision.value.envelopes[0].target_device == device


def test_automation_phase484_q_on_hpf_lpf_corrective_use_case():
    """Phase 4.8.4 correction : Q on HPF/LPF Eq8 bands EST automatable
    et audio-meaningful (résonance au cutoff). Use case corrective :
    Q modulation inter-track correlation-driven (snare HPF Q higher
    when kick saturates, lower when kick quiet)."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0] = _valid_automation_envelope(
        purpose="corrective_per_section",
        target_track="Snare Top",
        target_device="Eq8",
        target_param="Q",
        target_band_index=0,  # HPF band typically band 0
        points=[
            {"time_beats": 0.0, "value": 0.7},      # verse : flat HPF (no resonance peak)
            {"time_beats": 64.0, "value": 2.5},     # chorus : Q peak adds snare snap
            {"time_beats": 128.0, "value": 0.7},
        ],
        sections=[0, 1, 2],
        rationale="Snare HPF Q correlation-driven : Q haute en chorus quand kick saturate libère space pour snare snap résonance au cutoff. Phase 4.8.4 corrective inter-track use case (audio_metrics.band_energies kick low-mid varies per section).",
    )
    decision = parse_automation_decision(payload)
    env = decision.value.envelopes[0]
    assert env.target_param == "Q"
    assert env.target_band_index == 0
    assert env.points[1].value == 2.5  # peak character in chorus


def test_automation_phase484_q_on_lpf_inter_track_correlation():
    """Phase 4.8.4 : Q on LPF for bass<->kick low-mid correlation balance."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0] = _valid_automation_envelope(
        purpose="corrective_per_section",
        target_track="Bass A",
        target_device="Eq8",
        target_param="Q",
        target_band_index=7,  # LPF band typically last
        points=[
            {"time_beats": 0.0, "value": 0.7},      # kick dominant low-mid
            {"time_beats": 64.0, "value": 1.5},     # kick recule, bass Q peak fills space
            {"time_beats": 128.0, "value": 0.7},
        ],
        sections=[0, 1, 2],
        rationale="Bass LPF Q automation correlation-driven : Q haute quand kick low-mid recule (cross-track band_energies divergence per Sections Timeline). Q peak = warm character compensation pour kick absence.",
    )
    decision = parse_automation_decision(payload)
    assert decision.value.envelopes[0].target_param == "Q"


def test_automation_phase483_trackspacer_still_rejected():
    """Phase 4.8.3 : Trackspacer remains OOS (eq-creative scope)."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["target_device"] = "Trackspacer"
    with pytest.raises(MixAgentOutputError, match="target_device"):
        parse_automation_decision(payload)


def test_automation_phase482_max_time_beats_accepted():
    """Phase 4.8.2 : AUTOMATION_MAX_TIME_BEATS = 39996.0 accepted (boundary)."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0]["points"] = [
        {"time_beats": 0.0, "value": -1.0},
        {"time_beats": 100.0, "value": -0.5},
        {"time_beats": AUTOMATION_MAX_TIME_BEATS, "value": -1.0},  # boundary
    ]
    decision = parse_automation_decision(payload)
    assert decision.value.envelopes[0].points[2].time_beats == AUTOMATION_MAX_TIME_BEATS


def test_automation_corrective_with_master_track_raises_via_purpose_check():
    """Phase 4.8.1 audit : combo corrective_per_section + target_track=Master
    is contradiction. While parser doesn't directly check this combo,
    test verifies the typical scenario : agent should use mastering_master_bus
    for Master target. corrective_per_section + Master track has no parser
    check directly, but it's an agent-prompt anti-pattern. Test confirms
    parser ACCEPTS the combo (delegation to agent-prompt enforcement)."""
    payload = _valid_automation_payload()
    payload["automation"]["envelopes"][0] = _valid_automation_envelope(
        purpose="corrective_per_section",
        target_track="Master",
        target_device="Eq8",
        target_param="Gain",
        target_band_index=4,
        sections=[0, 1, 2],
        rationale="Test : corrective_per_section + Master track is logical contradiction (corrective is per-track Tier A scope) but parser permissive. Agent-prompt enforces.",
    )
    # Parser accepts (no parser check for this combo) — agent-prompt anti-pattern
    decision = parse_automation_decision(payload)
    assert decision.value.envelopes[0].target_track == "Master"


# ============================================================================
# Phase 4.17 — BandTrack parser tests
# ============================================================================


def _valid_band_track(**overrides) -> dict:
    """Default = bell-mode peak follower on a single track, 5 frames."""
    base = {
        "target_track": "Vocal",
        "target_eq8_instance": 0,
        "target_band_index": 3,
        "band_mode": "bell",
        "purpose": "follow_peak",
        "frame_times_sec": [0.0, 0.5, 1.0, 1.5, 2.0],
        "freqs_hz": [3000.0, 3050.0, 3100.0, 3120.0, 3080.0],
        "gains_db": [-3.0, -4.5, -6.0, -5.0, -3.5],
        "q_values": [8.0, 8.5, 9.0, 9.0, 8.5],
        "source_amps_db": [-25.0, -22.0, -18.0, -20.0, -24.0],
        "q_static": 8.0,
        "gain_max_db": 6.0,
        "threshold_db": -40.0,
        "interpolation": "parabolic",
        "sub_frame_factor": 1,
        "rationale": "Track a sibilant 3 kHz peak that drifts +120 Hz over 2 seconds during the chorus build. Proportional gain reduction tied to source amplitude.",
        "inspired_by": [
            {"kind": "diagnostic", "path": "tracks[Vocal].peak_trajectories[0]",
             "excerpt": "stable 3kHz peak, mean -20 dBFS, drifts within demi-octave"},
        ],
    }
    base.update(overrides)
    return base


def _payload_with_band_tracks(*band_tracks, envelopes=None) -> dict:
    return {
        "schema_version": "1.0",
        "automation": {
            "envelopes": envelopes if envelopes is not None else [],
            "band_tracks": list(band_tracks),
        },
        "cited_by": [
            {"kind": "diagnostic", "path": "x", "excerpt": "x"},
        ],
        "rationale": "BandTrack parser test wrapper.",
        "confidence": 0.85,
    }


def test_band_track_parses_minimum_valid():
    decision = parse_automation_decision(_payload_with_band_tracks(_valid_band_track()))
    assert len(decision.value.band_tracks) == 1
    bt = decision.value.band_tracks[0]
    assert bt.band_mode == "bell"
    assert bt.target_band_index == 3
    assert len(bt.freqs_hz) == 5
    assert bt.q_values == (8.0, 8.5, 9.0, 9.0, 8.5)


def test_band_track_optional_series_become_none():
    """Optional gains_db/q_values/source_amps_db default to None when absent."""
    bt_dict = _valid_band_track()
    del bt_dict["gains_db"]
    del bt_dict["q_values"]
    del bt_dict["source_amps_db"]
    decision = parse_automation_decision(_payload_with_band_tracks(bt_dict))
    bt = decision.value.band_tracks[0]
    assert bt.gains_db is None
    assert bt.q_values is None
    assert bt.source_amps_db is None


@pytest.mark.parametrize("mode", sorted(["lowcut_48", "lowcut_12", "lowshelf",
                                          "bell", "notch", "highshelf",
                                          "highcut_12", "highcut_48"]))
def test_band_track_all_8_modes_accepted(mode):
    decision = parse_automation_decision(
        _payload_with_band_tracks(_valid_band_track(band_mode=mode))
    )
    assert decision.value.band_tracks[0].band_mode == mode


def test_band_track_invalid_mode_rejected():
    with pytest.raises(MixAgentOutputError, match="band_mode"):
        parse_automation_decision(
            _payload_with_band_tracks(_valid_band_track(band_mode="parametric"))
        )


def test_band_track_invalid_purpose_rejected():
    with pytest.raises(MixAgentOutputError, match="purpose"):
        parse_automation_decision(
            _payload_with_band_tracks(_valid_band_track(purpose="random_thing"))
        )


def test_band_track_band_index_out_of_range_rejected():
    with pytest.raises(MixAgentOutputError, match="target_band_index"):
        parse_automation_decision(
            _payload_with_band_tracks(_valid_band_track(target_band_index=8))
        )


def test_band_track_freqs_out_of_range_rejected():
    bt = _valid_band_track()
    bt["freqs_hz"] = [3000.0, 3050.0, 30000.0, 3120.0, 3080.0]  # index 2 too high
    with pytest.raises(MixAgentOutputError, match="freqs_hz.*out of"):
        parse_automation_decision(_payload_with_band_tracks(bt))


def test_band_track_time_series_length_mismatch_rejected():
    bt = _valid_band_track()
    bt["gains_db"] = [-3.0, -4.5, -6.0]  # length 3 != n_frames 5
    with pytest.raises(MixAgentOutputError, match="length"):
        parse_automation_decision(_payload_with_band_tracks(bt))


def test_band_track_non_monotone_times_rejected():
    bt = _valid_band_track()
    bt["frame_times_sec"] = [0.0, 1.0, 0.5, 1.5, 2.0]  # decrease at index 2
    with pytest.raises(MixAgentOutputError, match="strictly increasing"):
        parse_automation_decision(_payload_with_band_tracks(bt))


def test_band_track_too_few_frames_rejected():
    bt = _valid_band_track(
        frame_times_sec=[0.0, 0.5],
        freqs_hz=[3000.0, 3050.0],
        gains_db=[-3.0, -4.5],
        q_values=[8.0, 8.5],
        source_amps_db=[-25.0, -22.0],
    )
    with pytest.raises(MixAgentOutputError, match="need >= 3"):
        parse_automation_decision(_payload_with_band_tracks(bt))


def test_band_track_invalid_interpolation_rejected():
    with pytest.raises(MixAgentOutputError, match="interpolation"):
        parse_automation_decision(
            _payload_with_band_tracks(_valid_band_track(interpolation="bezier"))
        )


def test_band_track_sub_frame_factor_out_of_range_rejected():
    with pytest.raises(MixAgentOutputError, match="sub_frame_factor"):
        parse_automation_decision(
            _payload_with_band_tracks(_valid_band_track(sub_frame_factor=99))
        )


def test_band_track_q_values_out_of_eq8_range_rejected():
    bt = _valid_band_track()
    bt["q_values"] = [8.0, 8.5, 25.0, 9.0, 8.5]  # 25.0 > 18.0 max
    with pytest.raises(MixAgentOutputError, match="out of \\[0.1, 18.0\\]"):
        parse_automation_decision(_payload_with_band_tracks(bt))


def test_band_track_duplicate_band_alloc_rejected():
    """Two BandTracks targeting the same Eq8 band → parser collision."""
    bt_a = _valid_band_track(target_band_index=3, target_track="Vocal")
    bt_b = _valid_band_track(target_band_index=3, target_track="Vocal",
                              band_mode="highshelf",
                              rationale="Different mode but same band — should still reject because two BandTracks cannot share an Eq8 band.")
    with pytest.raises(MixAgentOutputError, match="duplicate BandTrack"):
        parse_automation_decision(_payload_with_band_tracks(bt_a, bt_b))


def test_band_track_distinct_instances_or_bands_accepted():
    bt_a = _valid_band_track(target_band_index=3, target_eq8_instance=0)
    bt_b = _valid_band_track(target_band_index=4, target_eq8_instance=0)
    bt_c = _valid_band_track(target_band_index=3, target_eq8_instance=1)
    decision = parse_automation_decision(
        _payload_with_band_tracks(bt_a, bt_b, bt_c)
    )
    assert len(decision.value.band_tracks) == 3


def test_band_track_collides_with_envelope_on_same_eq8_band_rejected():
    """An AutomationEnvelope targeting (Vocal, Eq8, instance=0, band=3, Gain)
    + a BandTrack targeting the same band → cross-collection collision."""
    envelope = _valid_automation_envelope(
        purpose="corrective_per_section",
        target_track="Vocal",
        target_device="Eq8",
        target_param="Gain",
        target_band_index=3,
        sections=[0, 1, 2],
    )
    bt = _valid_band_track(
        target_track="Vocal", target_eq8_instance=0, target_band_index=3,
    )
    with pytest.raises(MixAgentOutputError, match="collides with"):
        parse_automation_decision(
            _payload_with_band_tracks(bt, envelopes=[envelope])
        )


def test_band_track_default_interpolation_is_parabolic():
    bt = _valid_band_track()
    del bt["interpolation"]
    decision = parse_automation_decision(_payload_with_band_tracks(bt))
    assert decision.value.band_tracks[0].interpolation == "parabolic"


def test_band_track_rationale_too_short_rejected():
    bt = _valid_band_track(rationale="too short")
    with pytest.raises(MixAgentOutputError, match="depth-light"):
        parse_automation_decision(_payload_with_band_tracks(bt))


def test_band_track_no_inspired_by_rejected():
    bt = _valid_band_track()
    bt["inspired_by"] = []
    with pytest.raises(MixAgentOutputError, match="at least 1 citation"):
        parse_automation_decision(_payload_with_band_tracks(bt))


def test_band_track_empty_band_tracks_accepted():
    """band_tracks=[] coexists with envelopes=[]."""
    decision = parse_automation_decision(_payload_with_band_tracks())
    assert decision.value.band_tracks == ()
    assert decision.value.envelopes == ()


def test_phase47_full_integration_audio_metrics_plus_genre_context():
    payload = _valid_payload()
    payload["diagnostic"]["tracks"][0]["audio_metrics"] = _valid_audio_metrics(
        is_stereo=True, correlation=0.78, width_overall=0.35,
        width_per_band=[0.05, 0.1, 0.2, 0.45, 0.55, 0.4, 0.3],
    )
    payload["diagnostic"]["tracks"][1]["audio_metrics"] = _valid_audio_metrics(
        is_stereo=False,  # mono kick
    )
    payload["diagnostic"]["genre_context"] = _valid_genre_context(
        family="electronic_dance", target_lufs_mix=-9.0,
        typical_crest_mix=8.0, density_tolerance="high",
    )
    decision = parse_diagnostic_decision(payload)
    assert decision.value.tracks[0].audio_metrics.is_stereo is True
    assert decision.value.tracks[1].audio_metrics.is_stereo is False
    assert decision.value.genre_context.family == "electronic_dance"


# ============================================================================
# Phase 4.9 — Mastering lane parser tests
# ============================================================================

from mix_engine.blueprint import (  # noqa: E402
    MASTER_TRACK_NAME,
    MasterMove,
    MasteringDecision,
    SUPPORTED_MASTERING_SCHEMA_VERSIONS,
    VALID_MASTER_CHAIN_POSITIONS,
    VALID_MASTER_MOVE_TYPES,
    VALID_SATURATION_TYPES,
    parse_mastering_decision,
    parse_mastering_decision_from_response,
)


_RATIONALE_50 = (
    "Master move justifié par signal full_mix.integrated_lufs vs target genre context."
)
_CITE_FULL_MIX = {
    "kind": "diagnostic", "path": "Full Mix Analysis!B7",
    "excerpt": "Integrated LUFS: -13.5",
}
_CITE_GENRE = {
    "kind": "diagnostic", "path": "GenreContext.target_lufs_mix",
    "excerpt": "electronic_aggressive: -8 LUFS",
}


def _master_payload(moves):
    return {
        "schema_version": "1.0",
        "mastering": {"moves": moves},
        "cited_by": [_CITE_FULL_MIX],
        "rationale": _RATIONALE_50,
        "confidence": 0.85,
    }


def _move_limiter(**over):
    base = {
        "type": "limiter_target",
        "target_track": "Master",
        "device": "Limiter",
        "target_lufs_i": -8.0,
        "ceiling_dbtp": -0.3,
        "lookahead_ms": 1.5,
        "chain_position": "master_limiter",
        "rationale": _RATIONALE_50,
        "inspired_by": [_CITE_FULL_MIX, _CITE_GENRE],
    }
    base.update(over)
    return base


def _move_glue(**over):
    base = {
        "type": "glue_compression",
        "target_track": "Master",
        "device": "GlueCompressor",
        "ratio": 1.7,
        "threshold_db": -12.0,
        "attack_ms": 30.0,
        "release_ms": 200.0,
        "gr_target_db": 2.0,
        "chain_position": "master_glue",
        "rationale": _RATIONALE_50,
        "inspired_by": [_CITE_FULL_MIX],
    }
    base.update(over)
    return base


def _move_eq_bell(**over):
    base = {
        "type": "master_eq_band",
        "target_track": "Master",
        "device": "Eq8",
        "band_type": "bell",
        "center_hz": 600.0,
        "q": 1.5,
        "gain_db": -1.5,
        "chain_position": "master_corrective",
        "processing_mode": "stereo",
        "rationale": _RATIONALE_50,
        "inspired_by": [_CITE_FULL_MIX],
    }
    base.update(over)
    return base


def _move_eq_hpf(**over):
    base = {
        "type": "master_eq_band",
        "target_track": "Master",
        "device": "Eq8",
        "band_type": "highpass",
        "center_hz": 30.0,
        "q": 0.71,
        "slope_db_per_oct": 12.0,
        "chain_position": "master_corrective",
        "processing_mode": "stereo",
        "rationale": _RATIONALE_50,
        "inspired_by": [_CITE_FULL_MIX],
    }
    base.update(over)
    return base


def _move_stereo(**over):
    base = {
        "type": "stereo_enhance",
        "target_track": "Master",
        "device": "StereoGain",
        "width": 1.15,
        "chain_position": "master_stereo",
        "rationale": _RATIONALE_50,
        "inspired_by": [_CITE_FULL_MIX],
    }
    base.update(over)
    return base


def _move_saturation(**over):
    base = {
        "type": "saturation_color",
        "target_track": "Master",
        "device": "Saturator",
        "drive_pct": 8.0,
        "saturation_type": "soft_sine",
        "dry_wet": 1.0,
        "chain_position": "master_color",
        "rationale": _RATIONALE_50,
        "inspired_by": [_CITE_FULL_MIX],
    }
    base.update(over)
    return base


def _move_bus_glue(**over):
    base = {
        "type": "bus_glue",
        "target_track": "Drum Bus",
        "device": "GlueCompressor",
        "ratio": 1.7,
        "threshold_db": -10.0,
        "attack_ms": 30.0,
        "release_ms": 250.0,
        "gr_target_db": 1.5,
        "chain_position": "bus_glue",
        "rationale": _RATIONALE_50,
        "inspired_by": [_CITE_FULL_MIX],
    }
    base.update(over)
    return base


# === Happy paths ===

def test_mastering_empty_moves_accepted():
    """No master signal → moves: [] is the do-no-harm exit."""
    decision = parse_mastering_decision(_master_payload([]))
    assert isinstance(decision.value, MasteringDecision)
    assert decision.value.moves == ()
    assert decision.lane == "mastering"


def test_mastering_limiter_target_native_valid():
    decision = parse_mastering_decision(_master_payload([_move_limiter()]))
    assert len(decision.value.moves) == 1
    move = decision.value.moves[0]
    assert move.type == "limiter_target"
    assert move.device == "Limiter"
    assert move.target_lufs_i == -8.0
    assert move.ceiling_dbtp == -0.3


def test_mastering_limiter_target_smartlimit_alternative():
    decision = parse_mastering_decision(_master_payload([
        _move_limiter(device="SmartLimit"),
    ]))
    assert decision.value.moves[0].device == "SmartLimit"


def test_mastering_glue_compression_valid():
    decision = parse_mastering_decision(_master_payload([_move_glue()]))
    move = decision.value.moves[0]
    assert move.type == "glue_compression"
    assert move.ratio == 1.7
    assert move.gr_target_db == 2.0


def test_mastering_glue_compression_compressor2_alternative():
    decision = parse_mastering_decision(_master_payload([
        _move_glue(device="Compressor2"),
    ]))
    assert decision.value.moves[0].device == "Compressor2"


def test_mastering_master_eq_bell_valid():
    decision = parse_mastering_decision(_master_payload([_move_eq_bell()]))
    move = decision.value.moves[0]
    assert move.band_type == "bell"
    assert move.gain_db == -1.5
    assert move.slope_db_per_oct is None


def test_mastering_master_eq_high_shelf_tonal():
    decision = parse_mastering_decision(_master_payload([
        _move_eq_bell(band_type="high_shelf", center_hz=10000.0,
                      q=0.7, gain_db=1.5,
                      chain_position="master_tonal"),
    ]))
    move = decision.value.moves[0]
    assert move.band_type == "high_shelf"
    assert move.chain_position == "master_tonal"


def test_mastering_master_eq_hpf_with_slope_valid():
    decision = parse_mastering_decision(_master_payload([_move_eq_hpf()]))
    move = decision.value.moves[0]
    assert move.band_type == "highpass"
    assert move.slope_db_per_oct == 12.0


def test_mastering_stereo_enhance_width_valid():
    decision = parse_mastering_decision(_master_payload([_move_stereo()]))
    move = decision.value.moves[0]
    assert move.width == 1.15


def test_mastering_stereo_enhance_bass_mono_valid():
    decision = parse_mastering_decision(_master_payload([
        _move_stereo(width=None, bass_mono_freq_hz=120.0),
    ]))
    move = decision.value.moves[0]
    assert move.bass_mono_freq_hz == 120.0
    assert move.width is None


def test_mastering_saturation_color_valid():
    decision = parse_mastering_decision(_master_payload([_move_saturation()]))
    move = decision.value.moves[0]
    assert move.drive_pct == 8.0
    assert move.saturation_type == "soft_sine"


def test_mastering_bus_glue_valid():
    decision = parse_mastering_decision(_master_payload([_move_bus_glue()]))
    move = decision.value.moves[0]
    assert move.type == "bus_glue"
    assert move.target_track == "Drum Bus"
    assert move.chain_position == "bus_glue"


def test_mastering_multi_move_decision():
    """Realistic mastering chain : limiter + glue + tonal EQ."""
    decision = parse_mastering_decision(_master_payload([
        _move_eq_bell(band_type="high_shelf", center_hz=10000.0,
                      q=0.7, gain_db=1.5, chain_position="master_tonal"),
        _move_glue(),
        _move_limiter(),
    ]))
    assert len(decision.value.moves) == 3
    types = [m.type for m in decision.value.moves]
    assert types == ["master_eq_band", "glue_compression", "limiter_target"]


# === Cross-field check rejections ===

def test_mastering_limiter_target_missing_lufs_raises():
    payload = _master_payload([_move_limiter(target_lufs_i=None)])
    with pytest.raises(MixAgentOutputError, match="requires target_lufs_i"):
        parse_mastering_decision(payload)


def test_mastering_limiter_target_missing_ceiling_raises():
    payload = _master_payload([_move_limiter(ceiling_dbtp=None)])
    with pytest.raises(MixAgentOutputError, match="requires ceiling_dbtp"):
        parse_mastering_decision(payload)


def test_mastering_ceiling_above_minus_0_1_rejected():
    """Streaming standard : ceiling NEVER above -0.1 dBTP."""
    payload = _master_payload([_move_limiter(ceiling_dbtp=0.0)])
    with pytest.raises(MixAgentOutputError, match="ceiling_dbtp"):
        parse_mastering_decision(payload)


def test_mastering_eq_gain_above_3db_rejected():
    """Master EQ gain capped at ±3 dB ; > 3 = mix problem signal."""
    payload = _master_payload([_move_eq_bell(gain_db=5.0)])
    with pytest.raises(MixAgentOutputError, match="gain_db"):
        parse_mastering_decision(payload)


def test_mastering_eq_bell_with_slope_rejected():
    """Bell/notch/shelf MUST NOT have slope_db_per_oct."""
    payload = _master_payload([_move_eq_bell(slope_db_per_oct=12.0)])
    with pytest.raises(MixAgentOutputError, match="slope only applies"):
        parse_mastering_decision(payload)


def test_mastering_eq_hpf_without_slope_rejected():
    """HPF/LPF MUST have slope_db_per_oct."""
    payload = _master_payload([_move_eq_hpf(slope_db_per_oct=None)])
    with pytest.raises(MixAgentOutputError, match="requires slope_db_per_oct"):
        parse_mastering_decision(payload)


def test_mastering_stereo_enhance_no_value_rejected():
    """At least one of (width, mid_side_balance, bass_mono_freq_hz)."""
    payload = _master_payload([_move_stereo(width=None)])
    with pytest.raises(MixAgentOutputError, match="at least one"):
        parse_mastering_decision(payload)


def test_mastering_stereo_enhance_width_neutral_rejected():
    """No-op identity (width=1.0) rejected."""
    payload = _master_payload([_move_stereo(width=1.0)])
    with pytest.raises(MixAgentOutputError, match="no-op"):
        parse_mastering_decision(payload)


def test_mastering_target_track_non_master_for_limiter_rejected():
    """Only bus_glue can target sub-bus."""
    payload = _master_payload([_move_limiter(target_track="Drum Bus")])
    with pytest.raises(MixAgentOutputError, match="requires target_track"):
        parse_mastering_decision(payload)


def test_mastering_bus_glue_targeting_master_rejected():
    """bus_glue must target sub-bus, not master itself."""
    payload = _master_payload([_move_bus_glue(target_track="Master")])
    with pytest.raises(MixAgentOutputError, match="bus_glue"):
        parse_mastering_decision(payload)


def test_mastering_two_limiter_targets_rejected():
    """Only ONE Limiter terminal per master."""
    payload = _master_payload([_move_limiter(), _move_limiter(device="SmartLimit")])
    with pytest.raises(MixAgentOutputError, match="max 1"):
        parse_mastering_decision(payload)


def test_mastering_duplicate_move_rejected():
    """Same (target_track, device, chain_position) twice rejected."""
    payload = _master_payload([_move_glue(), _move_glue()])
    with pytest.raises(MixAgentOutputError, match="duplicate move"):
        parse_mastering_decision(payload)


def test_mastering_chain_position_mismatch_for_type_rejected():
    """limiter_target with master_glue position rejected."""
    payload = _master_payload([_move_limiter(chain_position="master_glue")])
    with pytest.raises(MixAgentOutputError, match="not allowed for type"):
        parse_mastering_decision(payload)


def test_mastering_device_mismatch_for_type_rejected():
    """limiter_target with Eq8 rejected."""
    payload = _master_payload([_move_limiter(device="Eq8")])
    with pytest.raises(MixAgentOutputError, match="not allowed for type"):
        parse_mastering_decision(payload)


def test_mastering_extra_field_for_type_rejected():
    """saturation_color with target_lufs_i (limiter field) rejected."""
    move = _move_saturation()
    move["target_lufs_i"] = -8.0
    payload = _master_payload([move])
    with pytest.raises(MixAgentOutputError, match="extra value fields"):
        parse_mastering_decision(payload)


def test_mastering_glue_ratio_above_4_rejected():
    """Master glue ratio capped at 4:1 ; > 4 = creative scope."""
    payload = _master_payload([_move_glue(ratio=5.0)])
    with pytest.raises(MixAgentOutputError, match="ratio"):
        parse_mastering_decision(payload)


def test_mastering_saturation_drive_above_25_rejected():
    """Master saturation drive capped at 25% ; > 25 = creative scope."""
    payload = _master_payload([_move_saturation(drive_pct=50.0)])
    with pytest.raises(MixAgentOutputError, match="drive_pct"):
        parse_mastering_decision(payload)


def test_mastering_invalid_saturation_type_rejected():
    payload = _master_payload([_move_saturation(saturation_type="bogus")])
    with pytest.raises(MixAgentOutputError, match="saturation_type"):
        parse_mastering_decision(payload)


def test_mastering_invalid_move_type_rejected():
    payload = _master_payload([_move_limiter(type="bogus_move")])
    with pytest.raises(MixAgentOutputError, match="not in"):
        parse_mastering_decision(payload)


def test_mastering_invalid_band_type_rejected():
    payload = _master_payload([_move_eq_bell(band_type="bogus")])
    with pytest.raises(MixAgentOutputError, match="band_type"):
        parse_mastering_decision(payload)


def test_mastering_invalid_processing_mode_rejected():
    payload = _master_payload([_move_eq_bell(processing_mode="bogus")])
    with pytest.raises(MixAgentOutputError, match="processing_mode"):
        parse_mastering_decision(payload)


# === Depth-light + envelope checks ===

def test_mastering_rationale_too_short_rejected():
    payload = _master_payload([_move_limiter(rationale="short")])
    with pytest.raises(MixAgentOutputError, match="rationale too short"):
        parse_mastering_decision(payload)


def test_mastering_inspired_by_empty_rejected():
    payload = _master_payload([_move_limiter(inspired_by=[])])
    with pytest.raises(MixAgentOutputError, match="must contain at least one citation"):
        parse_mastering_decision(payload)


def test_mastering_unsupported_schema_version_rejected():
    payload = _master_payload([])
    payload["schema_version"] = "9.0"
    with pytest.raises(MixAgentOutputError):
        parse_mastering_decision(payload)


def test_mastering_refusal_payload_propagates():
    payload = {"error": "missing input", "details": "no .als path"}
    with pytest.raises(MixAgentOutputError, match="agent refused"):
        parse_mastering_decision(payload)


def test_mastering_from_response_handles_fences():
    payload = _master_payload([_move_limiter()])
    text = "```json\n" + json.dumps(payload) + "\n```"
    decision = parse_mastering_decision_from_response(text)
    assert decision.value.moves[0].type == "limiter_target"


def test_mastering_master_track_name_constant_used():
    """target_track must equal MASTER_TRACK_NAME for all non-bus_glue."""
    decision = parse_mastering_decision(_master_payload([_move_limiter()]))
    assert decision.value.moves[0].target_track == MASTER_TRACK_NAME


def test_mastering_blueprint_slot_filled():
    """Phase 4.9 : MixBlueprint.mastering slot exists."""
    bp = MixBlueprint(name="t")
    decision = parse_mastering_decision(_master_payload([_move_limiter()]))
    bp_filled = bp.with_decision("mastering", decision)
    assert bp_filled.mastering is not None
    assert "mastering" in bp_filled.filled_lanes()
