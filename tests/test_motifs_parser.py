"""Tests for parse_motifs_decision (Phase 2.7).

Pattern : minimum-valid payload, then mutations exercising each
validation rule. Same shape as test_blueprint_agent_parsers.py.
"""
import json

import pytest

from composition_engine.blueprint import (
    LayerMotif,
    MotifsDecision,
    Note,
    SectionBlueprint,
    MOTIF_PITCH_MIN,
    MOTIF_PITCH_MAX,
    MOTIF_VELOCITY_MIN,
    MOTIF_VELOCITY_MAX,
)
from composition_engine.blueprint.agent_parsers import (
    AgentOutputError,
    SUPPORTED_MOTIFS_SCHEMA_VERSIONS,
    parse_motifs_decision,
    parse_motifs_decision_from_response,
)


def _valid_payload(**overrides) -> dict:
    base = {
        "schema_version": "1.0",
        "motifs": {
            "by_layer": [
                {
                    "layer_role": "drum_kit",
                    "layer_instrument": "kit",
                    "notes": [
                        {"bar": 0, "beat": 0.0, "pitch": 36,
                         "duration_beats": 0.25, "velocity": 110},
                        {"bar": 0, "beat": 1.0, "pitch": 36,
                         "duration_beats": 0.25, "velocity": 105},
                    ],
                    "rationale": "Causal: 4x4 kick. Interactionnel: kick anchor for hats. Idiomatique: banque/02_Rhythm_Patterns Dark techno.Kick X...X...",
                    "inspired_by": [
                        {"song": "banque/02_Rhythm_Patterns",
                         "path": "Dark techno.Kick",
                         "excerpt": "X...X...X...X... — Four-on-floor solide"},
                    ],
                },
            ],
        },
        "rationale": "4-bar Acid Drops kick groove",
        "inspired_by": [
            {"song": "banque/05_Qrust_Profiles",
             "path": "Acid Drops (cible)", "excerpt": "128 BPM Phrygien"},
        ],
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


# ============================================================================
# Happy paths
# ============================================================================


def test_parses_minimum_valid_payload():
    decision = parse_motifs_decision(_valid_payload())
    assert decision.sphere == "motifs"
    assert isinstance(decision.value, MotifsDecision)
    assert len(decision.value.by_layer) == 1
    assert decision.value.by_layer[0].layer_role == "drum_kit"
    assert len(decision.value.by_layer[0].notes) == 2
    assert decision.confidence == 0.85


def test_supports_schema_version_1_0():
    assert "1.0" in SUPPORTED_MOTIFS_SCHEMA_VERSIONS


def test_decision_can_be_assigned_to_blueprint():
    decision = parse_motifs_decision(_valid_payload())
    bp = SectionBlueprint(name="test").with_decision("motifs", decision)
    assert bp.motifs is decision
    assert "motifs" in bp.filled_spheres()


# ============================================================================
# Range / type validation
# ============================================================================


@pytest.mark.parametrize("invalid_pitch", [-1, 128, 200, MOTIF_PITCH_MIN - 1, MOTIF_PITCH_MAX + 1])
def test_pitch_out_of_range_raises(invalid_pitch):
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["notes"][0]["pitch"] = invalid_pitch
    with pytest.raises(AgentOutputError, match="pitch"):
        parse_motifs_decision(payload)


@pytest.mark.parametrize("valid_pitch", [MOTIF_PITCH_MIN, 36, 60, 127, MOTIF_PITCH_MAX])
def test_pitch_in_range_accepted(valid_pitch):
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["notes"][0]["pitch"] = valid_pitch
    decision = parse_motifs_decision(payload)
    assert decision.value.by_layer[0].notes[0].pitch == valid_pitch


@pytest.mark.parametrize("invalid_vel", [0, -1, 128, 200])
def test_velocity_out_of_range_raises(invalid_vel):
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["notes"][0]["velocity"] = invalid_vel
    with pytest.raises(AgentOutputError, match="velocity"):
        parse_motifs_decision(payload)


def test_velocity_min_accepted():
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["notes"][0]["velocity"] = MOTIF_VELOCITY_MIN
    decision = parse_motifs_decision(payload)
    assert decision.value.by_layer[0].notes[0].velocity == MOTIF_VELOCITY_MIN


def test_velocity_max_accepted():
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["notes"][0]["velocity"] = MOTIF_VELOCITY_MAX
    decision = parse_motifs_decision(payload)
    assert decision.value.by_layer[0].notes[0].velocity == MOTIF_VELOCITY_MAX


def test_negative_bar_raises():
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["notes"][0]["bar"] = -1
    with pytest.raises(AgentOutputError, match="bar"):
        parse_motifs_decision(payload)


def test_negative_beat_raises():
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["notes"][0]["beat"] = -0.5
    with pytest.raises(AgentOutputError, match="beat"):
        parse_motifs_decision(payload)


def test_zero_duration_raises():
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["notes"][0]["duration_beats"] = 0.0
    with pytest.raises(AgentOutputError, match="duration"):
        parse_motifs_decision(payload)


def test_negative_duration_raises():
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["notes"][0]["duration_beats"] = -0.25
    with pytest.raises(AgentOutputError, match="duration"):
        parse_motifs_decision(payload)


# ============================================================================
# Structural validation
# ============================================================================


def test_empty_by_layer_raises():
    payload = _valid_payload()
    payload["motifs"]["by_layer"] = []
    with pytest.raises(AgentOutputError, match="by_layer"):
        parse_motifs_decision(payload)


def test_layer_with_empty_notes_raises():
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["notes"] = []
    with pytest.raises(AgentOutputError, match="notes"):
        parse_motifs_decision(payload)


def test_empty_layer_role_raises():
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["layer_role"] = ""
    with pytest.raises(AgentOutputError, match="layer_role"):
        parse_motifs_decision(payload)


def test_missing_pitch_raises():
    payload = _valid_payload()
    del payload["motifs"]["by_layer"][0]["notes"][0]["pitch"]
    with pytest.raises(AgentOutputError, match="pitch"):
        parse_motifs_decision(payload)


def test_missing_motifs_key_raises():
    payload = _valid_payload()
    del payload["motifs"]
    with pytest.raises(AgentOutputError, match="motifs"):
        parse_motifs_decision(payload)


# ============================================================================
# Schema version + envelope
# ============================================================================


def test_unsupported_schema_version_warns_but_parses(caplog):
    """Composition-side policy is lenient on input: unknown schema version
    logs a WARNING but still parses (so a future agent-side bump doesn't
    hard-block the orchestrator)."""
    payload = _valid_payload()
    payload["schema_version"] = "99.0"
    with caplog.at_level("WARNING"):
        decision = parse_motifs_decision(payload)
    assert any("schema_version" in rec.message for rec in caplog.records)
    assert decision.sphere == "motifs"


def test_error_payload_raises():
    with pytest.raises(AgentOutputError, match="insufficient"):
        parse_motifs_decision({
            "schema_version": "1.0",
            "error": "insufficient input",
            "details": "no refs",
        })


def test_confidence_out_of_range_raises():
    payload = _valid_payload()
    payload["confidence"] = 1.5
    with pytest.raises(AgentOutputError):
        parse_motifs_decision(payload)


# ============================================================================
# Lenient input — fences, prose around
# ============================================================================


def test_from_response_handles_fences():
    payload_str = json.dumps(_valid_payload())
    fenced = f"```json\n{payload_str}\n```"
    decision = parse_motifs_decision_from_response(fenced)
    assert decision.value.by_layer[0].layer_role == "drum_kit"


def test_from_response_handles_prose_around():
    payload_str = json.dumps(_valid_payload())
    prosed = f"Voici la décision motifs:\n{payload_str}\nEnd."
    decision = parse_motifs_decision_from_response(prosed)
    assert len(decision.value.by_layer) == 1


def test_string_pitch_coerced():
    """Lenient on input: string '36' → int 36."""
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["notes"][0]["pitch"] = "36"
    decision = parse_motifs_decision(payload)
    assert decision.value.by_layer[0].notes[0].pitch == 36


# ============================================================================
# Multi-layer payload
# ============================================================================


def test_multi_layer_payload_preserves_order():
    payload = _valid_payload()
    payload["motifs"]["by_layer"].append({
        "layer_role": "perc",
        "layer_instrument": "hat",
        "notes": [
            {"bar": 0, "beat": 0.5, "pitch": 42,
             "duration_beats": 0.25, "velocity": 95},
        ],
        "rationale": "Off-beat hat at 0.5: tombe entre les kicks pour creer le shuffle Acid Drops profile.",
        "inspired_by": [{"song": "banque/05_Qrust_Profiles",
                         "path": "Acid Drops (cible)",
                         "excerpt": "Hat pattern 0.5, 1.5, 2.5, 3.5 (off-beat)"}],
    })
    decision = parse_motifs_decision(payload)
    assert len(decision.value.by_layer) == 2
    assert decision.value.by_layer[0].layer_role == "drum_kit"
    assert decision.value.by_layer[1].layer_role == "perc"


# ============================================================================
# Phase 2.7.1 audit-driven hardening
# ============================================================================


def test_unordered_notes_within_layer_raises():
    """Notes must be (bar, beat) ascending strict — same discipline as
    Phase 2.6.1 inflection_points ordering."""
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["notes"] = [
        {"bar": 5, "beat": 0.0, "pitch": 36, "duration_beats": 0.25, "velocity": 100},
        {"bar": 0, "beat": 0.0, "pitch": 36, "duration_beats": 0.25, "velocity": 100},
    ]
    with pytest.raises(AgentOutputError, match="ordered"):
        parse_motifs_decision(payload)


def test_thin_rationale_rejected():
    """rationale < 50 chars indicates placeholder agent output."""
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["rationale"] = "drum"
    with pytest.raises(AgentOutputError, match="rationale"):
        parse_motifs_decision(payload)


def test_empty_inspired_by_per_layer_rejected():
    """A LayerMotif without provenance is indistinguishable from placeholder."""
    payload = _valid_payload()
    payload["motifs"]["by_layer"][0]["inspired_by"] = []
    with pytest.raises(AgentOutputError, match="inspired_by"):
        parse_motifs_decision(payload)


def test_duplicate_role_instrument_rejected():
    """Composer's _find_layer_motif first-match would silently ignore
    the duplicate — better to raise so the agent sees the bug."""
    payload = _valid_payload()
    payload["motifs"]["by_layer"].append({
        "layer_role": "drum_kit",
        "layer_instrument": "kit",  # same as the existing entry
        "notes": [
            {"bar": 0, "beat": 2.0, "pitch": 36,
             "duration_beats": 0.25, "velocity": 100},
        ],
        "rationale": "Different bar/beat but same role+instrument — dupe to test.",
        "inspired_by": [{"song": "X/Y", "path": "p", "excerpt": "non-empty"}],
    })
    with pytest.raises(AgentOutputError, match="duplicate"):
        parse_motifs_decision(payload)
