"""Tests for the eq_corrective lane (Phase 4.2).

Schema + parser. The agent .md (`.claude/agents/eq-corrective-decider.md`)
is the LLM contract ; these tests pin the typed shape its output must
satisfy before the Tier B configurator can consume it.
"""
import json

import pytest

from mix_engine.blueprint import (
    EQ_FREQ_MAX_HZ,
    EQ_FREQ_MIN_HZ,
    EQ_GAIN_MAX_DB,
    EQ_GAIN_MIN_DB,
    EQ_Q_MAX,
    EQ_Q_MIN,
    EQAutomationPoint,
    EQBandCorrection,
    EQCorrectiveDecision,
    MixAgentOutputError,
    MixBlueprint,
    SUPPORTED_EQ_CORRECTIVE_SCHEMA_VERSIONS,
    VALID_EQ_BAND_TYPES,
    VALID_EQ_INTENTS,
    parse_eq_corrective_decision,
    parse_eq_corrective_decision_from_response,
)


def _valid_band(**overrides) -> dict:
    base = {
        "track": "Bass A",
        "band_type": "bell",
        "intent": "cut",
        "center_hz": 247.0,
        "q": 4.5,
        "gain_db": -3.5,
        "rationale": (
            "Causal: 247Hz resonance on Bass A masks the kick fundamental. "
            "Interactionnel: bass dominates low-mid energy. "
            "Idiomatique: industrial cut pattern from PDF."
        ),
        "inspired_by": [
            {"kind": "diagnostic", "path": "Anomalies!A14",
             "excerpt": "247 Hz shared resonance Kick A + Bass A, severity critical"},
        ],
    }
    base.update(overrides)
    return base


def _valid_payload(**overrides) -> dict:
    base = {
        "schema_version": "1.0",
        "eq_corrective": {
            "bands": [_valid_band()],
        },
        "cited_by": [{"kind": "diagnostic", "path": "x", "excerpt": "y"}],
        "rationale": "test",
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


# ============================================================================
# Schema invariants
# ============================================================================


def test_canonical_band_types_pin():
    """If the user adds a band_type, update this set so consumers know."""
    assert VALID_EQ_BAND_TYPES == {
        "bell", "low_shelf", "high_shelf", "highpass", "lowpass", "notch",
    }


def test_canonical_intents_pin():
    assert VALID_EQ_INTENTS == {"cut", "boost", "shape", "filter"}


def test_supported_schema_version_includes_1_0():
    assert "1.0" in SUPPORTED_EQ_CORRECTIVE_SCHEMA_VERSIONS


def test_eq_band_correction_is_immutable():
    band = EQBandCorrection(
        track="t", band_type="bell", intent="cut",
        center_hz=247.0, q=4.5, gain_db=-3.5,
    )
    with pytest.raises(Exception):
        band.gain_db = -5.0  # type: ignore[misc]


# ============================================================================
# Happy paths
# ============================================================================


def test_parses_minimum_valid_payload():
    decision = parse_eq_corrective_decision(_valid_payload())
    assert decision.lane == "eq_corrective"
    assert isinstance(decision.value, EQCorrectiveDecision)
    assert len(decision.value.bands) == 1
    band = decision.value.bands[0]
    assert band.track == "Bass A"
    assert band.center_hz == 247.0
    assert band.gain_db == -3.5
    assert band.gain_envelope == ()
    assert decision.confidence == 0.85


def test_decision_can_be_assigned_to_blueprint():
    decision = parse_eq_corrective_decision(_valid_payload())
    bp = MixBlueprint(name="session").with_decision("eq_corrective", decision)
    assert bp.eq_corrective is decision
    assert "eq_corrective" in bp.filled_lanes()


def test_empty_bands_accepted():
    """Scenario E: no anomalies → empty bands, valid output."""
    payload = _valid_payload()
    payload["eq_corrective"]["bands"] = []
    decision = parse_eq_corrective_decision(payload)
    assert decision.value.bands == ()


# ============================================================================
# Range validation — center_hz, q, gain_db
# ============================================================================


@pytest.mark.parametrize("invalid_freq", [-1.0, 0, 15.99, 22001.0, 50000.0])
def test_center_hz_out_of_range_raises(invalid_freq):
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["center_hz"] = invalid_freq
    with pytest.raises(MixAgentOutputError, match="center_hz"):
        parse_eq_corrective_decision(payload)


@pytest.mark.parametrize("valid_freq", [EQ_FREQ_MIN_HZ, 60.0, 247.0, 5000.0, EQ_FREQ_MAX_HZ])
def test_center_hz_in_range_accepted(valid_freq):
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["center_hz"] = valid_freq
    decision = parse_eq_corrective_decision(payload)
    assert decision.value.bands[0].center_hz == valid_freq


@pytest.mark.parametrize("invalid_q", [-1.0, 0.0, 0.05, 18.5, 100.0])
def test_q_out_of_range_raises(invalid_q):
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["q"] = invalid_q
    with pytest.raises(MixAgentOutputError, match=r"\bq="):
        parse_eq_corrective_decision(payload)


@pytest.mark.parametrize("invalid_gain", [-20.0, -15.5, 15.5, 20.0])
def test_gain_db_out_of_range_raises(invalid_gain):
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["gain_db"] = invalid_gain
    # Need to also update intent to match (avoid intent/sign coherence
    # check tripping first)
    payload["eq_corrective"]["bands"][0]["intent"] = (
        "cut" if invalid_gain < 0 else "boost"
    )
    with pytest.raises(MixAgentOutputError, match="gain_db"):
        parse_eq_corrective_decision(payload)


# ============================================================================
# Cross-field coherence — intent ↔ gain sign
# ============================================================================


def test_cut_with_positive_gain_raises():
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["intent"] = "cut"
    payload["eq_corrective"]["bands"][0]["gain_db"] = 3.0
    with pytest.raises(MixAgentOutputError, match="cut"):
        parse_eq_corrective_decision(payload)


def test_boost_with_negative_gain_raises():
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["intent"] = "boost"
    payload["eq_corrective"]["bands"][0]["gain_db"] = -3.0
    with pytest.raises(MixAgentOutputError, match="boost"):
        parse_eq_corrective_decision(payload)


def test_filter_with_bell_band_type_raises():
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["intent"] = "filter"
    payload["eq_corrective"]["bands"][0]["band_type"] = "bell"
    payload["eq_corrective"]["bands"][0]["gain_db"] = 0.0  # filters often have gain=0
    # intent/gain check passes, but filter/band_type check should raise
    with pytest.raises(MixAgentOutputError, match="filter"):
        parse_eq_corrective_decision(payload)


def test_filter_with_highpass_accepted():
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["intent"] = "filter"
    payload["eq_corrective"]["bands"][0]["band_type"] = "highpass"
    payload["eq_corrective"]["bands"][0]["gain_db"] = 0.0
    decision = parse_eq_corrective_decision(payload)
    assert decision.value.bands[0].intent == "filter"


# ============================================================================
# Invalid enums
# ============================================================================


@pytest.mark.parametrize("invalid_type", ["parametric", "BELL", "shelving", ""])
def test_invalid_band_type_raises(invalid_type):
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["band_type"] = invalid_type
    with pytest.raises(MixAgentOutputError, match="band_type"):
        parse_eq_corrective_decision(payload)


@pytest.mark.parametrize("invalid_intent", ["reduce", "kill", "tilt", ""])
def test_invalid_intent_raises(invalid_intent):
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["intent"] = invalid_intent
    with pytest.raises(MixAgentOutputError, match="intent"):
        parse_eq_corrective_decision(payload)


# ============================================================================
# Envelopes — ordering, range validation, lenient input shapes
# ============================================================================


def test_static_band_with_empty_envelopes_accepted():
    """Static-only correction = all envelopes empty — most common case."""
    payload = _valid_payload()
    band = payload["eq_corrective"]["bands"][0]
    band["gain_envelope"] = []
    band["freq_envelope"] = []
    band["q_envelope"] = []
    decision = parse_eq_corrective_decision(payload)
    assert decision.value.bands[0].gain_envelope == ()


def test_dynamic_band_with_gain_envelope_accepted():
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["gain_envelope"] = [
        {"bar": 0, "value": 0.0},
        {"bar": 16, "value": -3.5},
        {"bar": 32, "value": -5.0},
        {"bar": 48, "value": 0.0},
    ]
    decision = parse_eq_corrective_decision(payload)
    env = decision.value.bands[0].gain_envelope
    assert len(env) == 4
    assert env[2].bar == 32
    assert env[2].value == -5.0


def test_envelope_accepts_pair_format():
    """Lenient input: [bar, value] tuple instead of {bar, value} object."""
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["gain_envelope"] = [
        [0, 0.0], [16, -3.5], [32, -5.0],
    ]
    decision = parse_eq_corrective_decision(payload)
    assert len(decision.value.bands[0].gain_envelope) == 3
    assert decision.value.bands[0].gain_envelope[1].bar == 16


def test_envelope_unsorted_raises():
    """Envelopes must be bar-ascending strict — automation ambiguity guard."""
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["gain_envelope"] = [
        {"bar": 32, "value": -5.0},
        {"bar": 16, "value": -3.5},
    ]
    with pytest.raises(MixAgentOutputError, match="ascending"):
        parse_eq_corrective_decision(payload)


def test_envelope_duplicate_bar_raises():
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["gain_envelope"] = [
        {"bar": 16, "value": -3.0},
        {"bar": 16, "value": -5.0},
    ]
    with pytest.raises(MixAgentOutputError, match="ascending"):
        parse_eq_corrective_decision(payload)


def test_envelope_negative_bar_raises():
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["gain_envelope"] = [
        {"bar": -1, "value": -3.0},
    ]
    with pytest.raises(MixAgentOutputError, match="bar"):
        parse_eq_corrective_decision(payload)


def test_envelope_value_out_of_gain_range_raises():
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["gain_envelope"] = [
        {"bar": 0, "value": 0.0},
        {"bar": 16, "value": -25.0},  # below EQ_GAIN_MIN_DB
    ]
    with pytest.raises(MixAgentOutputError, match="gain_envelope"):
        parse_eq_corrective_decision(payload)


def test_envelope_freq_out_of_range_raises():
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["freq_envelope"] = [
        {"bar": 0, "value": 247.0},
        {"bar": 16, "value": 30000.0},  # above EQ_FREQ_MAX_HZ
    ]
    with pytest.raises(MixAgentOutputError, match="freq_envelope"):
        parse_eq_corrective_decision(payload)


def test_envelope_q_out_of_range_raises():
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["q_envelope"] = [
        {"bar": 0, "value": 4.5},
        {"bar": 16, "value": 25.0},  # above EQ_Q_MAX
    ]
    with pytest.raises(MixAgentOutputError, match="q_envelope"):
        parse_eq_corrective_decision(payload)


# ============================================================================
# Depth-light enforcement (matches motif-decider Phase 2.7.1 fix #5)
# ============================================================================


def test_thin_rationale_per_band_rejected():
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["rationale"] = "cut 247"
    with pytest.raises(MixAgentOutputError, match="rationale"):
        parse_eq_corrective_decision(payload)


def test_empty_inspired_by_per_band_rejected():
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["inspired_by"] = []
    with pytest.raises(MixAgentOutputError, match="inspired_by"):
        parse_eq_corrective_decision(payload)


# ============================================================================
# Schema version + envelope (cross-agent metadata)
# ============================================================================


def test_error_payload_raises():
    with pytest.raises(MixAgentOutputError, match="out-of-scope"):
        parse_eq_corrective_decision({
            "schema_version": "1.0",
            "error": "out-of-scope",
            "details": "Tonal imbalance global — escalating to mastering-decider",
        })


def test_unsupported_schema_version_raises():
    payload = _valid_payload()
    payload["schema_version"] = "99.0"
    with pytest.raises(MixAgentOutputError):
        parse_eq_corrective_decision(payload)


# ============================================================================
# Multi-band + sections + lenient input (fences, prose around)
# ============================================================================


def test_multi_band_payload():
    payload = _valid_payload()
    payload["eq_corrective"]["bands"].append(_valid_band(
        track="Vocal Lead",
        band_type="bell",
        intent="cut",
        center_hz=2400.0,
        q=6.0,
        gain_db=-2.0,
    ))
    decision = parse_eq_corrective_decision(payload)
    assert len(decision.value.bands) == 2
    assert decision.value.bands[1].track == "Vocal Lead"


def test_sections_field_preserves_indices():
    payload = _valid_payload()
    payload["eq_corrective"]["bands"][0]["sections"] = [1, 2, 3]
    decision = parse_eq_corrective_decision(payload)
    assert decision.value.bands[0].sections == (1, 2, 3)


def test_from_response_handles_fences():
    payload_str = json.dumps(_valid_payload())
    fenced = f"```json\n{payload_str}\n```"
    decision = parse_eq_corrective_decision_from_response(fenced)
    assert decision.value.bands[0].track == "Bass A"


def test_from_response_handles_prose_around():
    payload_str = json.dumps(_valid_payload())
    prosed = f"Voici la décision EQ:\n{payload_str}\nFin."
    decision = parse_eq_corrective_decision_from_response(prosed)
    assert len(decision.value.bands) == 1
