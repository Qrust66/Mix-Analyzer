"""Tests for composition_engine.blueprint.agent_parsers — schema validation
of sphere-agent JSON payloads, including LLM-output tolerance (Phase 2.2.1)."""
import json

import pytest

from composition_engine.blueprint.agent_parsers import (
    AgentOutputError,
    DB_MAX,
    DB_MIN,
    TEMPO_MAX_BPM,
    TEMPO_MIN_BPM,
    VALID_ARC_SHAPES,
    VALID_DENSITY_CURVES,
    VALID_SUBDIVISIONS,
    VELOCITY_MAX,
    VELOCITY_MIN,
    extract_json_payload,
    parse_arrangement_decision,
    parse_arrangement_decision_from_response,
    parse_dynamics_decision,
    parse_dynamics_decision_from_response,
    parse_harmony_decision,
    parse_harmony_decision_from_response,
    parse_rhythm_decision,
    parse_rhythm_decision_from_response,
    parse_structure_decision,
    parse_structure_decision_from_response,
)
from composition_engine.blueprint.schema import (
    ArrangementDecision,
    Citation,
    Decision,
    DynamicsDecision,
    HarmonyDecision,
    InstChange,
    LayerSpec,
    RhythmDecision,
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


# ============================================================================
# Phase 2.4 — rhythm parser
# ============================================================================


def _valid_rhythm_payload(**overrides):
    """Return a minimum-valid rhythm-decider payload."""
    base = {
        "schema_version": "1.0",
        "rhythm": {
            "tempo_bpm": 100,
            "time_signature": "4/4",
            "drum_pattern": "kick on 1 and 3, snare on 2 and 4",
            "subdivisions": 16,
            "swing": 0.0,
            "polyrhythms": [],
        },
        "rationale": "100 BPM 4/4 standard rock.",
        "inspired_by": [
            {"song": "Nirvana/Heart_Shaped_Box", "path": "tempo_bpm_documented_range",
             "excerpt": "100-104 BPM"},
        ],
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


def test_parses_minimal_valid_rhythm_payload():
    decision = parse_rhythm_decision(_valid_rhythm_payload())
    assert decision.sphere == "rhythm"
    assert isinstance(decision.value, RhythmDecision)
    assert decision.value.tempo_bpm == 100
    assert decision.value.time_signature == "4/4"
    assert decision.value.subdivisions == 16
    assert decision.value.swing == 0.0


def test_rhythm_empty_drum_pattern_is_valid():
    payload = _valid_rhythm_payload()
    payload["rhythm"]["drum_pattern"] = ""
    decision = parse_rhythm_decision(payload)
    assert decision.value.drum_pattern == ""


def test_rhythm_polyrhythms_optional():
    payload = _valid_rhythm_payload()
    del payload["rhythm"]["polyrhythms"]
    decision = parse_rhythm_decision(payload)
    assert decision.value.polyrhythms == ()


def test_rhythm_polyrhythms_with_strings():
    payload = _valid_rhythm_payload()
    payload["rhythm"]["polyrhythms"] = ["3:4 hihat over 4/4 kick"]
    decision = parse_rhythm_decision(payload)
    assert decision.value.polyrhythms == ("3:4 hihat over 4/4 kick",)


def test_rhythm_default_subdivisions_is_16():
    payload = _valid_rhythm_payload()
    del payload["rhythm"]["subdivisions"]
    decision = parse_rhythm_decision(payload)
    assert decision.value.subdivisions == 16


def test_rhythm_empty_time_signature_defaults_to_4_4():
    payload = _valid_rhythm_payload()
    payload["rhythm"]["time_signature"] = "   "
    decision = parse_rhythm_decision(payload)
    assert decision.value.time_signature == "4/4"


def test_rhythm_asymmetric_time_signature_accepted():
    """16/8 with internal grouping (Pyramid_Song style) is accepted."""
    payload = _valid_rhythm_payload()
    payload["rhythm"]["time_signature"] = "16/8 with 3+3+4+3+3 internal grouping"
    decision = parse_rhythm_decision(payload)
    assert "3+3+4+3+3" in decision.value.time_signature


@pytest.mark.parametrize("invalid_tempo", [
    0, -1, -100,                           # zero / negative
    TEMPO_MIN_BPM - 1, TEMPO_MIN_BPM - 10,  # just below floor
    TEMPO_MAX_BPM + 1, TEMPO_MAX_BPM + 100, # just above ceiling
    9999,                                   # absurd
])
def test_rhythm_tempo_out_of_range_raises(invalid_tempo):
    payload = _valid_rhythm_payload()
    payload["rhythm"]["tempo_bpm"] = invalid_tempo
    with pytest.raises(AgentOutputError, match="tempo_bpm"):
        parse_rhythm_decision(payload)


@pytest.mark.parametrize("valid_tempo", [
    TEMPO_MIN_BPM,           # boundary low
    60, 100, 120, 150, 200,  # mid-range
    TEMPO_MAX_BPM,           # boundary high
])
def test_rhythm_valid_tempos_accepted(valid_tempo):
    payload = _valid_rhythm_payload()
    payload["rhythm"]["tempo_bpm"] = valid_tempo
    decision = parse_rhythm_decision(payload)
    assert decision.value.tempo_bpm == valid_tempo


def test_rhythm_string_tempo_coerced_to_int():
    payload = _valid_rhythm_payload()
    payload["rhythm"]["tempo_bpm"] = "120"
    decision = parse_rhythm_decision(payload)
    assert decision.value.tempo_bpm == 120


@pytest.mark.parametrize("invalid_sub", [
    -1, -16,           # negative
    0, 1, 2, 3,        # below smallest valid (4)
    6, 12, 24, 48,     # not a power of 2
    100, 128,          # above largest valid (64) or non-power
])
def test_rhythm_invalid_subdivisions_raises(invalid_sub):
    payload = _valid_rhythm_payload()
    payload["rhythm"]["subdivisions"] = invalid_sub
    with pytest.raises(AgentOutputError, match="subdivisions"):
        parse_rhythm_decision(payload)


@pytest.mark.parametrize("valid_sub", sorted(VALID_SUBDIVISIONS))
def test_rhythm_valid_subdivisions_accepted(valid_sub):
    """Parametrized over the actual VALID_SUBDIVISIONS frozenset — single
    source of truth shared with the parser."""
    payload = _valid_rhythm_payload()
    payload["rhythm"]["subdivisions"] = valid_sub
    decision = parse_rhythm_decision(payload)
    assert decision.value.subdivisions == valid_sub


@pytest.mark.parametrize("invalid_swing", [-0.1, 1.0, 1.5, 2.0])
def test_rhythm_swing_out_of_range_raises(invalid_swing):
    payload = _valid_rhythm_payload()
    payload["rhythm"]["swing"] = invalid_swing
    with pytest.raises(AgentOutputError, match="swing"):
        parse_rhythm_decision(payload)


@pytest.mark.parametrize("valid_swing", [0.0, 0.1, 0.3, 0.5, 0.55, 0.99])
def test_rhythm_valid_swing_accepted(valid_swing):
    payload = _valid_rhythm_payload()
    payload["rhythm"]["swing"] = valid_swing
    decision = parse_rhythm_decision(payload)
    assert decision.value.swing == valid_swing


def test_rhythm_string_swing_coerced():
    payload = _valid_rhythm_payload()
    payload["rhythm"]["swing"] = "0.55"
    decision = parse_rhythm_decision(payload)
    assert decision.value.swing == 0.55


def test_rhythm_error_payload_raises():
    with pytest.raises(AgentOutputError, match="Agent returned error"):
        parse_rhythm_decision({"error": "no usable refs"})


def test_rhythm_from_response_handles_fences():
    payload_str = json.dumps(_valid_rhythm_payload())
    fenced = f"```json\n{payload_str}\n```"
    decision = parse_rhythm_decision_from_response(fenced)
    assert decision.value.tempo_bpm == 100


def test_rhythm_decision_can_be_assigned_to_blueprint():
    from composition_engine.blueprint import SectionBlueprint

    decision = parse_rhythm_decision(_valid_rhythm_payload())
    bp = SectionBlueprint(name="intro").with_decision("rhythm", decision)
    assert bp.rhythm is decision
    assert "rhythm" in bp.filled_spheres()


# ============================================================================
# Phase 2.5 — arrangement parser
# ============================================================================


def _valid_arrangement_payload(**overrides):
    """Return a minimum-valid arrangement-decider payload."""
    base = {
        "schema_version": "1.0",
        "arrangement": {
            "layers": [
                {
                    "role": "drum_kit",
                    "instrument": "Roland TR-909",
                    "enters_at_bar": 0,
                    "exits_at_bar": 16,
                    "base_velocity": 100,
                },
                {
                    "role": "bass",
                    "instrument": "sub synth",
                    "enters_at_bar": 4,
                    "exits_at_bar": 16,
                    "base_velocity": 90,
                },
            ],
            "density_curve": "build",
            "instrumentation_changes": [
                {"bar": 8, "change": "lead enters with filter sweep"},
            ],
            "register_strategy": "low + mid only at start, add upper later",
        },
        "rationale": "Build progressif 2 layers + 1 change.",
        "inspired_by": [
            {"song": "Daft_Punk/Veridis_Quo", "path": "arrangement.section_instrumentation",
             "excerpt": "drum machine alone first, then bass arrival"},
        ],
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


def test_parses_minimal_valid_arrangement_payload():
    decision = parse_arrangement_decision(_valid_arrangement_payload())
    assert decision.sphere == "arrangement"
    assert isinstance(decision.value, ArrangementDecision)
    assert len(decision.value.layers) == 2
    assert decision.value.density_curve == "build"
    assert len(decision.value.instrumentation_changes) == 1


def test_arrangement_layers_must_be_non_empty():
    payload = _valid_arrangement_payload()
    payload["arrangement"]["layers"] = []
    with pytest.raises(AgentOutputError, match="at least one LayerSpec"):
        parse_arrangement_decision(payload)


def test_arrangement_empty_instrumentation_changes_is_valid():
    payload = _valid_arrangement_payload()
    payload["arrangement"]["instrumentation_changes"] = []
    decision = parse_arrangement_decision(payload)
    assert decision.value.instrumentation_changes == ()


def test_arrangement_default_density_curve_when_blank():
    payload = _valid_arrangement_payload()
    payload["arrangement"]["density_curve"] = "   "
    decision = parse_arrangement_decision(payload)
    assert decision.value.density_curve == "medium"


@pytest.mark.parametrize("valid_curve", sorted(VALID_DENSITY_CURVES))
def test_arrangement_all_valid_density_curves_accepted(valid_curve):
    """Parametrize over the actual VALID_DENSITY_CURVES — no drift between
    code and test."""
    payload = _valid_arrangement_payload()
    payload["arrangement"]["density_curve"] = valid_curve
    decision = parse_arrangement_decision(payload)
    assert decision.value.density_curve == valid_curve


@pytest.mark.parametrize("invalid_curve", [
    "exponential", "medium-build", "growing", "decay", "spiky", "",
    "BUILD", "Sparse",  # case-sensitive
])
def test_arrangement_invalid_density_curve_raises(invalid_curve):
    if invalid_curve == "":
        # Empty string defaults to "medium" — not an error path
        return
    payload = _valid_arrangement_payload()
    payload["arrangement"]["density_curve"] = invalid_curve
    with pytest.raises(AgentOutputError, match="density_curve"):
        parse_arrangement_decision(payload)


def test_arrangement_layer_with_invalid_enters_at_bar_raises():
    payload = _valid_arrangement_payload()
    payload["arrangement"]["layers"][0]["enters_at_bar"] = -1
    with pytest.raises(AgentOutputError, match="enters_at_bar"):
        parse_arrangement_decision(payload)


def test_arrangement_layer_with_exits_le_enters_raises():
    payload = _valid_arrangement_payload()
    payload["arrangement"]["layers"][0]["enters_at_bar"] = 8
    payload["arrangement"]["layers"][0]["exits_at_bar"] = 8  # equal = invalid
    with pytest.raises(AgentOutputError, match="exits_at_bar"):
        parse_arrangement_decision(payload)


def test_arrangement_layer_empty_role_raises():
    payload = _valid_arrangement_payload()
    payload["arrangement"]["layers"][0]["role"] = "   "
    with pytest.raises(AgentOutputError, match="role"):
        parse_arrangement_decision(payload)


@pytest.mark.parametrize("invalid_velocity", [
    -1, -100,                 # negative
    VELOCITY_MAX + 1, 200,    # above MIDI ceiling
])
def test_arrangement_velocity_out_of_range_raises(invalid_velocity):
    payload = _valid_arrangement_payload()
    payload["arrangement"]["layers"][0]["base_velocity"] = invalid_velocity
    with pytest.raises(AgentOutputError, match="base_velocity"):
        parse_arrangement_decision(payload)


@pytest.mark.parametrize("valid_velocity", [
    VELOCITY_MIN, 1, 60, 100, 120, VELOCITY_MAX,
])
def test_arrangement_valid_velocities_accepted(valid_velocity):
    payload = _valid_arrangement_payload()
    payload["arrangement"]["layers"][0]["base_velocity"] = valid_velocity
    decision = parse_arrangement_decision(payload)
    assert decision.value.layers[0].base_velocity == valid_velocity


def test_arrangement_default_velocity_when_absent():
    payload = _valid_arrangement_payload()
    del payload["arrangement"]["layers"][0]["base_velocity"]
    decision = parse_arrangement_decision(payload)
    assert decision.value.layers[0].base_velocity == 100


def test_arrangement_inst_change_negative_bar_raises():
    payload = _valid_arrangement_payload()
    payload["arrangement"]["instrumentation_changes"][0]["bar"] = -1
    with pytest.raises(AgentOutputError, match="bar"):
        parse_arrangement_decision(payload)


def test_arrangement_inst_change_missing_change_field_raises():
    payload = _valid_arrangement_payload()
    payload["arrangement"]["instrumentation_changes"][0] = {"bar": 4}
    with pytest.raises(AgentOutputError, match="change"):
        parse_arrangement_decision(payload)


def test_arrangement_string_velocity_coerced():
    payload = _valid_arrangement_payload()
    payload["arrangement"]["layers"][0]["base_velocity"] = "120"
    decision = parse_arrangement_decision(payload)
    assert decision.value.layers[0].base_velocity == 120


def test_arrangement_error_payload_raises():
    with pytest.raises(AgentOutputError, match="Agent returned error"):
        parse_arrangement_decision({"error": "no usable refs"})


def test_arrangement_from_response_handles_fences():
    payload_str = json.dumps(_valid_arrangement_payload())
    fenced = f"```json\n{payload_str}\n```"
    decision = parse_arrangement_decision_from_response(fenced)
    assert len(decision.value.layers) == 2


def test_arrangement_decision_can_be_assigned_to_blueprint():
    from composition_engine.blueprint import SectionBlueprint

    decision = parse_arrangement_decision(_valid_arrangement_payload())
    bp = SectionBlueprint(name="intro").with_decision("arrangement", decision)
    assert bp.arrangement is decision
    assert "arrangement" in bp.filled_spheres()


# ============================================================================
# Phase 2.6 — dynamics parser
# ============================================================================


def _valid_dynamics_payload(**overrides):
    """Return a minimum-valid dynamics-decider payload."""
    base = {
        "schema_version": "1.0",
        "dynamics": {
            "arc_shape": "rising",
            "start_db": -18.0,
            "end_db": -6.0,
            "peak_bar": 15,
            "inflection_points": [[7, -13.0], [11, -9.0]],
        },
        "rationale": "Build progressif inspiré de Pyramid_Song.",
        "inspired_by": [
            {"song": "Radiohead/Pyramid_Song", "path": "arrangement.dynamic_arc_overall",
             "excerpt": "monotonically-rising swell"},
        ],
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


def test_parses_minimal_valid_dynamics_payload():
    decision = parse_dynamics_decision(_valid_dynamics_payload())
    assert decision.sphere == "dynamics"
    assert isinstance(decision.value, DynamicsDecision)
    assert decision.value.arc_shape == "rising"
    assert decision.value.start_db == -18.0
    assert decision.value.end_db == -6.0
    assert decision.value.peak_bar == 15
    assert len(decision.value.inflection_points) == 2


@pytest.mark.parametrize("arc", sorted(VALID_ARC_SHAPES))
def test_dynamics_all_valid_arc_shapes_accepted(arc):
    """Parametrize over the actual VALID_ARC_SHAPES — single source of truth."""
    payload = _valid_dynamics_payload()
    payload["dynamics"]["arc_shape"] = arc
    # Adapt levels to satisfy direction constraints
    if arc == "rising":
        payload["dynamics"]["start_db"] = -18.0
        payload["dynamics"]["end_db"] = -6.0
    elif arc == "descending":
        payload["dynamics"]["start_db"] = -6.0
        payload["dynamics"]["end_db"] = -18.0
    elif arc == "flat":
        payload["dynamics"]["start_db"] = -12.0
        payload["dynamics"]["end_db"] = -12.0
    elif arc == "peak":
        payload["dynamics"]["peak_bar"] = 8  # required for peak
    decision = parse_dynamics_decision(payload)
    assert decision.value.arc_shape == arc


@pytest.mark.parametrize("invalid_arc", ["plateau", "ramp", "smooth-build", "RISING", ""])
def test_dynamics_invalid_arc_shape_raises(invalid_arc):
    payload = _valid_dynamics_payload()
    payload["dynamics"]["arc_shape"] = invalid_arc
    with pytest.raises(AgentOutputError, match="arc_shape"):
        parse_dynamics_decision(payload)


@pytest.mark.parametrize("invalid_db", [DB_MIN - 0.1, -100.0, 0.1, 5.0, 100.0])
def test_dynamics_db_out_of_range_raises(invalid_db):
    payload = _valid_dynamics_payload()
    payload["dynamics"]["start_db"] = invalid_db
    with pytest.raises(AgentOutputError, match="start_db"):
        parse_dynamics_decision(payload)


@pytest.mark.parametrize("valid_db", [DB_MIN, -30.0, -12.0, -6.0, -1.0, DB_MAX])
def test_dynamics_valid_db_levels_accepted(valid_db):
    payload = _valid_dynamics_payload()
    payload["dynamics"]["arc_shape"] = "flat"
    payload["dynamics"]["start_db"] = valid_db
    payload["dynamics"]["end_db"] = valid_db
    payload["dynamics"]["inflection_points"] = []
    decision = parse_dynamics_decision(payload)
    assert decision.value.start_db == valid_db


def test_dynamics_rising_with_end_le_start_raises():
    payload = _valid_dynamics_payload()
    payload["dynamics"]["arc_shape"] = "rising"
    payload["dynamics"]["start_db"] = -6.0
    payload["dynamics"]["end_db"] = -10.0  # going down, not rising
    with pytest.raises(AgentOutputError, match="rising"):
        parse_dynamics_decision(payload)


def test_dynamics_descending_with_end_ge_start_raises():
    payload = _valid_dynamics_payload()
    payload["dynamics"]["arc_shape"] = "descending"
    payload["dynamics"]["start_db"] = -18.0
    payload["dynamics"]["end_db"] = -6.0  # going up, not descending
    with pytest.raises(AgentOutputError, match="descending"):
        parse_dynamics_decision(payload)


def test_dynamics_flat_with_unequal_levels_raises():
    payload = _valid_dynamics_payload()
    payload["dynamics"]["arc_shape"] = "flat"
    payload["dynamics"]["start_db"] = -10.0
    payload["dynamics"]["end_db"] = -8.0
    with pytest.raises(AgentOutputError, match="flat"):
        parse_dynamics_decision(payload)


def test_dynamics_peak_shape_without_peak_bar_raises():
    payload = _valid_dynamics_payload()
    payload["dynamics"]["arc_shape"] = "peak"
    payload["dynamics"]["peak_bar"] = None
    with pytest.raises(AgentOutputError, match="peak"):
        parse_dynamics_decision(payload)


def test_dynamics_peak_bar_negative_raises():
    payload = _valid_dynamics_payload()
    payload["dynamics"]["peak_bar"] = -1
    with pytest.raises(AgentOutputError, match="peak_bar"):
        parse_dynamics_decision(payload)


def test_dynamics_peak_bar_null_accepted_for_non_peak_shapes():
    payload = _valid_dynamics_payload()
    payload["dynamics"]["arc_shape"] = "flat"
    payload["dynamics"]["start_db"] = -12.0
    payload["dynamics"]["end_db"] = -12.0
    payload["dynamics"]["peak_bar"] = None
    decision = parse_dynamics_decision(payload)
    assert decision.value.peak_bar is None


def test_dynamics_inflection_points_as_list_pairs():
    payload = _valid_dynamics_payload()
    payload["dynamics"]["inflection_points"] = [[3, -10.0], [9, -8.0]]
    decision = parse_dynamics_decision(payload)
    assert decision.value.inflection_points == ((3, -10.0), (9, -8.0))


def test_dynamics_inflection_points_as_dict_objects():
    """LLMs may emit {bar, db} objects instead of [bar, db] arrays. Both ok."""
    payload = _valid_dynamics_payload()
    payload["dynamics"]["inflection_points"] = [
        {"bar": 3, "db": -10.0},
        {"bar": 9, "db": -8.0},
    ]
    decision = parse_dynamics_decision(payload)
    assert decision.value.inflection_points == ((3, -10.0), (9, -8.0))


def test_dynamics_inflection_db_out_of_range_raises():
    payload = _valid_dynamics_payload()
    payload["dynamics"]["inflection_points"] = [[3, 10.0]]  # +10 dB invalid
    with pytest.raises(AgentOutputError, match="db"):
        parse_dynamics_decision(payload)


def test_dynamics_inflection_negative_bar_raises():
    payload = _valid_dynamics_payload()
    payload["dynamics"]["inflection_points"] = [[-1, -10.0]]
    with pytest.raises(AgentOutputError, match="bar"):
        parse_dynamics_decision(payload)


def test_dynamics_empty_inflection_points_valid():
    payload = _valid_dynamics_payload()
    payload["dynamics"]["inflection_points"] = []
    decision = parse_dynamics_decision(payload)
    assert decision.value.inflection_points == ()


def test_dynamics_string_db_coerced():
    payload = _valid_dynamics_payload()
    payload["dynamics"]["arc_shape"] = "flat"
    payload["dynamics"]["start_db"] = "-12.0"
    payload["dynamics"]["end_db"] = "-12.0"
    payload["dynamics"]["inflection_points"] = []
    decision = parse_dynamics_decision(payload)
    assert decision.value.start_db == -12.0


def test_dynamics_error_payload_raises():
    with pytest.raises(AgentOutputError, match="Agent returned error"):
        parse_dynamics_decision({"error": "no usable refs"})


def test_dynamics_from_response_handles_fences():
    payload_str = json.dumps(_valid_dynamics_payload())
    fenced = f"```json\n{payload_str}\n```"
    decision = parse_dynamics_decision_from_response(fenced)
    assert decision.value.arc_shape == "rising"


def test_dynamics_decision_can_be_assigned_to_blueprint():
    from composition_engine.blueprint import SectionBlueprint

    decision = parse_dynamics_decision(_valid_dynamics_payload())
    bp = SectionBlueprint(name="intro").with_decision("dynamics", decision)
    assert bp.dynamics is decision
    assert "dynamics" in bp.filled_spheres()


# ============================================================================
# Phase 2.6.1 — tightened parser constraints
# ============================================================================


def test_dynamics_baseline_db_is_canonical():
    """The DYNAMICS_BASELINE_DB constant is the single source of truth for
    the section baseline used as default for missing start/end_db."""
    from composition_engine.blueprint import DYNAMICS_BASELINE_DB
    from composition_engine.blueprint.schema import DynamicsDecision

    # The dataclass default must equal the published constant.
    default = DynamicsDecision()
    assert default.start_db == DYNAMICS_BASELINE_DB
    assert default.end_db == DYNAMICS_BASELINE_DB


def test_dynamics_missing_start_db_defaults_to_baseline():
    """start_db is documented as optional with default = baseline."""
    from composition_engine.blueprint import DYNAMICS_BASELINE_DB

    payload = _valid_dynamics_payload()
    payload["dynamics"]["arc_shape"] = "flat"
    del payload["dynamics"]["start_db"]
    del payload["dynamics"]["end_db"]
    payload["dynamics"]["peak_bar"] = None
    payload["dynamics"]["inflection_points"] = []
    decision = parse_dynamics_decision(payload)
    assert decision.value.start_db == DYNAMICS_BASELINE_DB
    assert decision.value.end_db == DYNAMICS_BASELINE_DB


def test_dynamics_valley_requires_inflection_point():
    """A valley with zero inflection points has no valley — rejected."""
    payload = _valid_dynamics_payload()
    payload["dynamics"]["arc_shape"] = "valley"
    payload["dynamics"]["start_db"] = -6.0
    payload["dynamics"]["end_db"] = -6.0
    payload["dynamics"]["peak_bar"] = None
    payload["dynamics"]["inflection_points"] = []
    with pytest.raises(AgentOutputError, match="valley"):
        parse_dynamics_decision(payload)


def test_dynamics_valley_with_one_inflection_accepted():
    payload = _valid_dynamics_payload()
    payload["dynamics"]["arc_shape"] = "valley"
    payload["dynamics"]["start_db"] = -6.0
    payload["dynamics"]["end_db"] = -6.0
    payload["dynamics"]["peak_bar"] = None
    payload["dynamics"]["inflection_points"] = [[8, -20.0]]
    decision = parse_dynamics_decision(payload)
    assert decision.value.arc_shape == "valley"
    assert len(decision.value.inflection_points) == 1


def test_dynamics_sawtooth_requires_two_inflection_points():
    """A sawtooth with fewer than two cycles is not a sawtooth."""
    payload = _valid_dynamics_payload()
    payload["dynamics"]["arc_shape"] = "sawtooth"
    payload["dynamics"]["start_db"] = -3.0
    payload["dynamics"]["end_db"] = -3.0
    payload["dynamics"]["peak_bar"] = None
    payload["dynamics"]["inflection_points"] = [[4, -15.0]]  # only 1
    with pytest.raises(AgentOutputError, match="sawtooth"):
        parse_dynamics_decision(payload)


def test_dynamics_sawtooth_with_two_inflections_accepted():
    payload = _valid_dynamics_payload()
    payload["dynamics"]["arc_shape"] = "sawtooth"
    payload["dynamics"]["start_db"] = -3.0
    payload["dynamics"]["end_db"] = -3.0
    payload["dynamics"]["peak_bar"] = None
    payload["dynamics"]["inflection_points"] = [[2, -15.0], [6, -3.0]]
    decision = parse_dynamics_decision(payload)
    assert decision.value.arc_shape == "sawtooth"


def test_dynamics_inflection_points_unsorted_rejected():
    """Bar order must be strictly ascending — out-of-order is a parser bug."""
    payload = _valid_dynamics_payload()
    payload["dynamics"]["inflection_points"] = [[15, -6.0], [3, -10.0]]  # bars 15, 3
    with pytest.raises(AgentOutputError, match="ascending"):
        parse_dynamics_decision(payload)


def test_dynamics_inflection_points_duplicate_bar_rejected():
    """Two dB values at the same bar are contradictory."""
    payload = _valid_dynamics_payload()
    payload["dynamics"]["inflection_points"] = [[7, -10.0], [7, -8.0]]
    with pytest.raises(AgentOutputError, match="ascending"):
        parse_dynamics_decision(payload)


def test_dynamics_inflection_points_already_sorted_accepted():
    """Sanity: the happy path still works after the ordering check."""
    payload = _valid_dynamics_payload()
    payload["dynamics"]["inflection_points"] = [[3, -15.0], [7, -10.0], [11, -8.0]]
    decision = parse_dynamics_decision(payload)
    assert [bar for bar, _ in decision.value.inflection_points] == [3, 7, 11]


def test_arrangement_layers_with_overlapping_roles_kept_separate():
    """Multiple layers with the same role (e.g. two bass voices) are
    preserved — the composer_adapter groups them per-track downstream."""
    payload = _valid_arrangement_payload()
    payload["arrangement"]["layers"] = [
        {"role": "bass", "instrument": "sub_low",
         "enters_at_bar": 0, "exits_at_bar": 8, "base_velocity": 90},
        {"role": "bass", "instrument": "sub_high",
         "enters_at_bar": 8, "exits_at_bar": 16, "base_velocity": 90},
    ]
    decision = parse_arrangement_decision(payload)
    assert len(decision.value.layers) == 2
    assert all(l.role == "bass" for l in decision.value.layers)
