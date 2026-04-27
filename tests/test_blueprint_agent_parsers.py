"""Tests for composition_engine.blueprint.agent_parsers — schema validation
of sphere-agent JSON payloads, including LLM-output tolerance (Phase 2.2.1)."""
import json

import pytest

from composition_engine.blueprint.agent_parsers import (
    AgentOutputError,
    extract_json_payload,
    parse_harmony_decision,
    parse_harmony_decision_from_response,
    parse_structure_decision,
    parse_structure_decision_from_response,
)
from composition_engine.blueprint.schema import (
    Citation,
    Decision,
    HarmonyDecision,
    StructureDecision,
    SubSection,
)


# ============================================================================
# Helpers
# ============================================================================


def _valid_payload(**overrides):
    """Return a minimum-valid structure-decider payload, merging overrides."""
    base = {
        "schema_version": "1.0",
        "structure": {
            "total_bars": 16,
            "sub_sections": [
                {"name": "hush", "start_bar": 0, "end_bar": 8, "role": "breath"},
                {"name": "build", "start_bar": 8, "end_bar": 16, "role": "build"},
            ],
            "breath_points": [7, 15],
            "transition_in": "abrupt vocal entry",
            "transition_out": "lead subtraction",
        },
        "rationale": "binaire 8+8 inspiré de Heart_Shaped_Box pacing.",
        "inspired_by": [
            {
                "song": "Nirvana/Heart_Shaped_Box",
                "path": "composition.section_count_and_lengths",
                "excerpt": "Intro 4 bars of guitar alone...",
            },
        ],
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


# ============================================================================
# Happy path
# ============================================================================


def test_parses_minimal_valid_payload():
    decision = parse_structure_decision(_valid_payload())
    assert isinstance(decision, Decision)
    assert decision.sphere == "structure"
    assert decision.confidence == 0.85
    assert isinstance(decision.value, StructureDecision)
    assert decision.value.total_bars == 16
    assert len(decision.value.sub_sections) == 2
    assert decision.value.breath_points == (7, 15)
    assert len(decision.inspired_by) == 1
    assert decision.inspired_by[0].song == "Nirvana/Heart_Shaped_Box"


def test_sub_section_role_optional():
    """role is optional and defaults to ''."""
    payload = _valid_payload()
    payload["structure"]["sub_sections"] = [
        {"name": "loop", "start_bar": 0, "end_bar": 16}  # no role
    ]
    decision = parse_structure_decision(payload)
    assert decision.value.sub_sections[0].role == ""


def test_empty_sub_sections_is_valid():
    payload = _valid_payload()
    payload["structure"]["sub_sections"] = []
    decision = parse_structure_decision(payload)
    assert decision.value.sub_sections == ()


def test_empty_breath_points_is_valid():
    payload = _valid_payload()
    payload["structure"]["breath_points"] = []
    decision = parse_structure_decision(payload)
    assert decision.value.breath_points == ()


def test_default_confidence_when_absent():
    payload = _valid_payload()
    del payload["confidence"]
    decision = parse_structure_decision(payload)
    assert decision.confidence == 0.8  # documented default


# ============================================================================
# Error paths
# ============================================================================


def test_raises_on_agent_error_payload():
    """Agent returned an explicit error refusal."""
    with pytest.raises(AgentOutputError, match="Agent returned error"):
        parse_structure_decision({"error": "no usable references", "details": "..."})


def test_raises_on_missing_structure_key():
    with pytest.raises(AgentOutputError, match="missing required key 'structure'"):
        parse_structure_decision({"rationale": "x", "inspired_by": [], "confidence": 0.5})


def test_raises_on_non_positive_total_bars():
    payload = _valid_payload()
    payload["structure"]["total_bars"] = 0
    with pytest.raises(AgentOutputError, match="total_bars must be > 0"):
        parse_structure_decision(payload)


def test_raises_on_wrong_type_for_total_bars():
    payload = _valid_payload()
    payload["structure"]["total_bars"] = "16"
    with pytest.raises(AgentOutputError, match="total_bars"):
        parse_structure_decision(payload)


def test_raises_on_invalid_sub_section_shape():
    payload = _valid_payload()
    payload["structure"]["sub_sections"] = [{"name": "incomplete"}]
    with pytest.raises(AgentOutputError, match="start_bar"):
        parse_structure_decision(payload)


def test_raises_on_breath_points_not_list_of_ints():
    payload = _valid_payload()
    payload["structure"]["breath_points"] = ["seven", "fifteen"]
    with pytest.raises(AgentOutputError, match="breath_points"):
        parse_structure_decision(payload)


def test_raises_on_invalid_citation():
    payload = _valid_payload()
    payload["inspired_by"] = [{"song": "X"}]  # missing path, excerpt
    with pytest.raises(AgentOutputError, match="path"):
        parse_structure_decision(payload)


def test_raises_on_confidence_out_of_range():
    payload = _valid_payload(confidence=1.5)
    with pytest.raises(AgentOutputError, match=r"confidence.*\[0.0, 1.0\]"):
        parse_structure_decision(payload)

    payload2 = _valid_payload(confidence=-0.1)
    with pytest.raises(AgentOutputError, match=r"confidence.*\[0.0, 1.0\]"):
        parse_structure_decision(payload2)


def test_raises_on_non_numeric_confidence():
    payload = _valid_payload(confidence="high")
    with pytest.raises(AgentOutputError, match="confidence"):
        parse_structure_decision(payload)


# ============================================================================
# Phase 2.2.1 — LLM-output tolerance
# ============================================================================


# extract_json_payload (raw text → dict)


def test_extract_json_from_pure_json_string():
    payload = json.dumps(_valid_payload())
    result = extract_json_payload(payload)
    assert result["schema_version"] == "1.0"


def test_extract_json_from_fenced_block():
    payload_str = json.dumps(_valid_payload())
    fenced = f"```json\n{payload_str}\n```"
    result = extract_json_payload(fenced)
    assert result["structure"]["total_bars"] == 16


def test_extract_json_from_unlabeled_fence():
    """LLMs sometimes use ``` without `json` language tag."""
    payload_str = json.dumps(_valid_payload())
    fenced = f"```\n{payload_str}\n```"
    result = extract_json_payload(fenced)
    assert "structure" in result


def test_extract_json_from_prose_with_object():
    """LLM prepends prose. Parser should still find the JSON object."""
    payload_str = json.dumps(_valid_payload())
    text = f"Voici la structure de la section :\n{payload_str}\nFin de la sortie."
    result = extract_json_payload(text)
    assert result["structure"]["total_bars"] == 16


def test_extract_json_raises_on_empty_input():
    with pytest.raises(AgentOutputError, match="empty"):
        extract_json_payload("")


def test_extract_json_raises_on_no_object():
    with pytest.raises(AgentOutputError, match="JSON"):
        extract_json_payload("no json here at all")


def test_extract_json_raises_on_non_string_input():
    with pytest.raises(AgentOutputError, match="string"):
        extract_json_payload({"already": "dict"})  # type: ignore[arg-type]


# Coercion: lenient input handling


def test_null_sub_sections_coerced_to_empty_list():
    payload = _valid_payload()
    payload["structure"]["sub_sections"] = None
    decision = parse_structure_decision(payload)
    assert decision.value.sub_sections == ()


def test_null_breath_points_coerced_to_empty_tuple():
    payload = _valid_payload()
    payload["structure"]["breath_points"] = None
    decision = parse_structure_decision(payload)
    assert decision.value.breath_points == ()


def test_integral_floats_coerced_to_int_for_total_bars():
    """LLM returns 16.0 instead of 16 — should still work."""
    payload = _valid_payload()
    payload["structure"]["total_bars"] = 16.0
    decision = parse_structure_decision(payload)
    assert decision.value.total_bars == 16


def test_integer_string_coerced_to_int_for_total_bars():
    payload = _valid_payload()
    payload["structure"]["total_bars"] = "16"
    decision = parse_structure_decision(payload)
    assert decision.value.total_bars == 16


def test_float_breath_points_coerced_to_int():
    """[7.0, 15.0] should be accepted as [7, 15]."""
    payload = _valid_payload()
    payload["structure"]["breath_points"] = [7.0, 15.0]
    decision = parse_structure_decision(payload)
    assert decision.value.breath_points == (7, 15)


def test_string_confidence_coerced_to_float():
    payload = _valid_payload()
    payload["confidence"] = "0.85"
    decision = parse_structure_decision(payload)
    assert decision.confidence == 0.85


def test_non_integral_float_for_total_bars_raises():
    """16.5 is not a valid bar count — should still error."""
    payload = _valid_payload()
    payload["structure"]["total_bars"] = 16.5
    with pytest.raises(AgentOutputError, match="non-integer"):
        parse_structure_decision(payload)


def test_bool_rejected_as_int():
    """isinstance(True, int) is True in Python — guard explicitly."""
    payload = _valid_payload()
    payload["structure"]["total_bars"] = True
    with pytest.raises(AgentOutputError, match="bool"):
        parse_structure_decision(payload)


# Schema version


def test_missing_schema_version_logs_warning_but_parses(caplog):
    payload = _valid_payload()
    del payload["schema_version"]
    import logging
    with caplog.at_level(logging.WARNING):
        decision = parse_structure_decision(payload)
    assert decision.value.total_bars == 16
    assert any("schema_version" in r.message for r in caplog.records)


def test_unknown_schema_version_logs_warning_but_parses(caplog):
    payload = _valid_payload()
    payload["schema_version"] = "99.99"
    import logging
    with caplog.at_level(logging.WARNING):
        decision = parse_structure_decision(payload)
    assert decision.value.total_bars == 16
    assert any("99.99" in r.message for r in caplog.records)


# End-to-end: raw text → Decision


def test_parse_from_response_handles_fenced_payload():
    payload_str = json.dumps(_valid_payload())
    fenced = f"```json\n{payload_str}\n```"
    decision = parse_structure_decision_from_response(fenced)
    assert decision.value.total_bars == 16


def test_parse_from_response_handles_prose_wrap():
    payload_str = json.dumps(_valid_payload())
    response = f"Sure, here's the structure:\n{payload_str}"
    decision = parse_structure_decision_from_response(response)
    assert decision.sphere == "structure"


# ============================================================================
# Phase 2.3 — harmony parser
# ============================================================================


def _valid_harmony_payload(**overrides):
    """Return a minimum-valid harmony-decider payload."""
    base = {
        "schema_version": "1.0",
        "harmony": {
            "mode": "Aeolian",
            "key_root": "A",
            "progression": ["i", "bVI", "bVII", "i"],
            "harmonic_rhythm": 0.5,
            "voicing_strategy": "close-voiced piano",
            "cadence_at_end": "open",
        },
        "rationale": "A minor avec progression descendante.",
        "inspired_by": [
            {"song": "Nirvana/Heart_Shaped_Box", "path": "composition.modal_choice",
             "excerpt": "Aeolian throughout"},
        ],
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


def test_parses_minimal_valid_harmony_payload():
    decision = parse_harmony_decision(_valid_harmony_payload())
    assert decision.sphere == "harmony"
    assert isinstance(decision.value, HarmonyDecision)
    assert decision.value.mode == "Aeolian"
    assert decision.value.key_root == "A"
    assert decision.value.progression == ("i", "bVI", "bVII", "i")
    assert decision.value.harmonic_rhythm == 0.5


def test_harmony_empty_progression_is_valid():
    """Static-modal harmonies (Around_The_World style) have no progression."""
    payload = _valid_harmony_payload()
    payload["harmony"]["progression"] = []
    decision = parse_harmony_decision(payload)
    assert decision.value.progression == ()


def test_harmony_optional_fields_default_to_empty_string():
    payload = _valid_harmony_payload()
    del payload["harmony"]["voicing_strategy"]
    del payload["harmony"]["cadence_at_end"]
    decision = parse_harmony_decision(payload)
    assert decision.value.voicing_strategy == ""
    assert decision.value.cadence_at_end == ""


def test_harmony_default_harmonic_rhythm_when_absent():
    payload = _valid_harmony_payload()
    del payload["harmony"]["harmonic_rhythm"]
    decision = parse_harmony_decision(payload)
    assert decision.value.harmonic_rhythm == 1.0  # documented default


@pytest.mark.parametrize("invalid_root", [
    "Am",          # mode-tagged, not a note name
    "A minor",     # mode-name string
    "H",           # German notation, not in our alphabet
    "X",           # nonsense
    "C natural",   # extra qualifier
    "",            # empty
])
def test_harmony_invalid_key_root_raises(invalid_root):
    payload = _valid_harmony_payload()
    payload["harmony"]["key_root"] = invalid_root
    with pytest.raises(AgentOutputError, match="key_root"):
        parse_harmony_decision(payload)


from composition_engine.music_theory import KEY_ROOTS as _KEY_ROOTS


@pytest.mark.parametrize("valid_root", sorted(_KEY_ROOTS))
def test_harmony_all_valid_roots_accepted(valid_root):
    payload = _valid_harmony_payload()
    payload["harmony"]["key_root"] = valid_root
    decision = parse_harmony_decision(payload)
    assert decision.value.key_root == valid_root


def test_harmony_zero_or_negative_harmonic_rhythm_raises():
    payload = _valid_harmony_payload()
    payload["harmony"]["harmonic_rhythm"] = 0.0
    with pytest.raises(AgentOutputError, match="harmonic_rhythm"):
        parse_harmony_decision(payload)

    payload2 = _valid_harmony_payload()
    payload2["harmony"]["harmonic_rhythm"] = -1.0
    with pytest.raises(AgentOutputError, match="harmonic_rhythm"):
        parse_harmony_decision(payload2)


def test_harmony_empty_mode_raises():
    payload = _valid_harmony_payload()
    payload["harmony"]["mode"] = "   "
    with pytest.raises(AgentOutputError, match="mode"):
        parse_harmony_decision(payload)


def test_harmony_string_harmonic_rhythm_coerced():
    """Same lenience as structure parser — accept "0.5" string."""
    payload = _valid_harmony_payload()
    payload["harmony"]["harmonic_rhythm"] = "0.5"
    decision = parse_harmony_decision(payload)
    assert decision.value.harmonic_rhythm == 0.5


def test_harmony_error_payload_raises():
    with pytest.raises(AgentOutputError, match="Agent returned error"):
        parse_harmony_decision({"error": "no usable refs", "details": "..."})


def test_harmony_from_response_handles_fences():
    payload_str = json.dumps(_valid_harmony_payload())
    fenced = f"```json\n{payload_str}\n```"
    decision = parse_harmony_decision_from_response(fenced)
    assert decision.value.key_root == "A"


# ============================================================================
# Integration — parser output feeds the blueprint
# ============================================================================


def test_decision_can_be_assigned_to_blueprint():
    """Parsed decision is valid input for SectionBlueprint.with_decision()."""
    from composition_engine.blueprint import SectionBlueprint

    decision = parse_structure_decision(_valid_payload())
    bp = SectionBlueprint(name="intro").with_decision("structure", decision)
    assert bp.structure is decision
    assert "structure" in bp.filled_spheres()


def test_harmony_decision_can_be_assigned_to_blueprint():
    """Parsed harmony decision is valid input for blueprint."""
    from composition_engine.blueprint import SectionBlueprint

    decision = parse_harmony_decision(_valid_harmony_payload())
    bp = SectionBlueprint(name="intro").with_decision("harmony", decision)
    assert bp.harmony is decision
    assert "harmony" in bp.filled_spheres()
