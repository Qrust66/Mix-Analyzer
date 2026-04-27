"""Tests for composition_engine.blueprint.agent_parsers — schema validation
of sphere-agent JSON payloads."""
import pytest

from composition_engine.blueprint.agent_parsers import (
    AgentOutputError,
    parse_structure_decision,
)
from composition_engine.blueprint.schema import (
    Citation,
    Decision,
    StructureDecision,
    SubSection,
)


# ============================================================================
# Helpers
# ============================================================================


def _valid_payload(**overrides):
    """Return a minimum-valid structure-decider payload, merging overrides."""
    base = {
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
# Integration — parser output feeds the blueprint
# ============================================================================


def test_decision_can_be_assigned_to_blueprint():
    """Parsed decision is valid input for SectionBlueprint.with_decision()."""
    from composition_engine.blueprint import SectionBlueprint

    decision = parse_structure_decision(_valid_payload())
    bp = SectionBlueprint(name="intro").with_decision("structure", decision)
    assert bp.structure is decision
    assert "structure" in bp.filled_spheres()
