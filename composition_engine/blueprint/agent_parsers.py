"""Parsers for sphere-agent JSON outputs.

Each sphere agent (structure-decider, harmony-decider, …) emits a JSON
payload that the orchestrator parses into a typed `Decision[T]`. This
module hosts the parsers, keeping the schema-validation logic in one
place rather than scattered across agent integrations.

Phase 2.2: only structure parser is implemented. Other spheres land in
their respective Phase 2.X commits as their agents come online.

## LLM-output tolerance (Phase 2.2.1)

LLMs occasionally return JSON wrapped in markdown fences, prefixed by
prose, or with mild type drift (string `"0.85"` instead of float, floats
where ints are expected, `null` instead of `[]`). The parsers in this
module are **lenient on input, strict on output**: they extract and
coerce on the way in, but the resulting Decision is fully typed and
guaranteed to satisfy the dataclass contract.

## Schema versioning

Sphere-agent payloads SHOULD include `"schema_version": "<major.minor>"`
at the top level. Phase 2.2.1 ships only schema_version "1.0" for the
structure decider. The parser currently warns (does not error) when the
field is missing or unknown, to ease the transition.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Mapping

from composition_engine.blueprint.schema import (
    ArrangementDecision,
    Citation,
    Decision,
    HarmonyDecision,
    InstChange,
    LayerSpec,
    RhythmDecision,
    StructureDecision,
    SubSection,
)
from composition_engine.music_theory import KEY_ROOTS

_LOG = logging.getLogger(__name__)

# Schema versions this parser understands. Bump when the agent contract
# changes in a way that requires a parser update; keep the old version
# entries as long as we want to support backward compatibility.
SUPPORTED_STRUCTURE_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTED_HARMONY_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTED_RHYTHM_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTED_ARRANGEMENT_SCHEMA_VERSIONS = frozenset({"1.0"})

# Density curve canonical values. Public so the test parametrize and any
# downstream consumer (cohesion rules, composer extensions) share the
# same source of truth.
VALID_DENSITY_CURVES = frozenset({
    "sparse", "medium", "dense", "build", "valley", "sawtooth",
})

# MIDI velocity range — 0 = silent, 127 = max. Public per the
# Phase 2.4.1 pattern (no hardcoded duplicates between code and test).
VELOCITY_MIN = 0
VELOCITY_MAX = 127

# Subdivision values accepted: powers of 2 from 4 to 64.
# 4 = quarter-note grid (rare). 8 = eighth-note. 16 = standard. 32/64 = detailed.
# Public so test parametrize can import (single source of truth).
VALID_SUBDIVISIONS = frozenset({4, 8, 16, 32, 64})

# Hard cap on tempo_bpm. 40 is below most musical music; 300 is faster than
# drum'n'bass / hardcore. Out-of-band values are almost certainly LLM bugs.
TEMPO_MIN_BPM = 40
TEMPO_MAX_BPM = 300

# Key root validation imported from the central music_theory module —
# single source of truth shared with composer_adapter, the music_theory
# tests, and any future sphere parser that needs to validate notes.
# (See composition_engine.music_theory.KEY_ROOTS.)


class AgentOutputError(ValueError):
    """Raised when an agent's JSON payload doesn't match the expected schema."""


# ============================================================================
# Lenient input cleanup — extract JSON from raw LLM text
# ============================================================================


_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL | re.IGNORECASE)
_FIRST_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json_payload(text: str) -> dict:
    """Extract a JSON object from raw LLM output text.

    Handles:
    - Pure JSON: returned as-is after json.loads.
    - Markdown fences: ```json\\n{...}\\n``` or ```\\n{...}\\n```
    - Prose around: "Voici la structure : {...}\\nFin." → extract {...}

    Raises AgentOutputError if no parseable JSON object is found.

    Note: this is the entry point for orchestrator code. If you already
    have a Python dict (e.g. from json.loads), pass it directly to
    parse_structure_decision() and skip this step.
    """
    if not isinstance(text, str):
        raise AgentOutputError(
            f"extract_json_payload expects a string, got {type(text).__name__}"
        )
    if not text.strip():
        raise AgentOutputError("agent output is empty")

    # 1) Try fenced block first (most common LLM accident)
    fence_match = _FENCE_RE.search(text)
    if fence_match:
        candidate = fence_match.group(1).strip()
    else:
        # 2) Try the first {...} block we can find
        obj_match = _FIRST_OBJECT_RE.search(text)
        if obj_match:
            candidate = obj_match.group(0)
        else:
            # 3) Fall back to the raw text
            candidate = text.strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise AgentOutputError(
            f"could not parse JSON from agent output: {exc}. "
            f"First 200 chars: {candidate[:200]!r}"
        ) from exc

    if not isinstance(parsed, dict):
        raise AgentOutputError(
            f"expected JSON object at top level, got {type(parsed).__name__}"
        )
    return parsed


# ============================================================================
# Type coercion helpers — accept mild LLM drift
# ============================================================================


def _coerce_list(value: Any, *, where: str) -> list:
    """null → []. Already-list → unchanged. Other → raise."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    raise AgentOutputError(
        f"{where}: expected list (or null), got {type(value).__name__}"
    )


def _coerce_int(value: Any, *, where: str) -> int:
    """int → unchanged. float → int (rounded if exactly integral, else raise).
    str of int → int. Other → raise."""
    if isinstance(value, bool):
        raise AgentOutputError(f"{where}: expected int, got bool")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        # Accept floats that are exactly integral (e.g. 7.0 → 7)
        if value.is_integer():
            return int(value)
        # Round near-integer floats (LLM-typical 7.0001) within a small epsilon
        if abs(value - round(value)) < 1e-6:
            return int(round(value))
        raise AgentOutputError(f"{where}: expected int, got non-integer float {value}")
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            try:
                f = float(value)
                if f.is_integer():
                    return int(f)
                raise AgentOutputError(f"{where}: expected int, got non-integer string {value!r}") from exc
            except ValueError:
                raise AgentOutputError(f"{where}: cannot parse {value!r} as int") from exc
    raise AgentOutputError(
        f"{where}: expected int, got {type(value).__name__}"
    )


def _coerce_float(value: Any, *, where: str) -> float:
    """int/float → float. str numeric → float. Other → raise."""
    if isinstance(value, bool):
        raise AgentOutputError(f"{where}: expected number, got bool")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise AgentOutputError(f"{where}: cannot parse {value!r} as float") from exc
    raise AgentOutputError(
        f"{where}: expected number, got {type(value).__name__}"
    )


def _coerce_str(value: Any) -> str:
    """Anything → str via str(). null → empty string."""
    if value is None:
        return ""
    return str(value)


# ============================================================================
# Sub-component parsers
# ============================================================================


def _require(
    payload: Mapping[str, Any], key: str, *, where: str
) -> Any:
    """Return payload[key], raising AgentOutputError if missing."""
    if key not in payload:
        raise AgentOutputError(f"{where}: missing required key {key!r}")
    return payload[key]


def _parse_citation(payload: Mapping[str, Any], *, where: str) -> Citation:
    """Build a Citation. song/path/excerpt all coerced to str."""
    if not isinstance(payload, Mapping):
        raise AgentOutputError(
            f"{where}: expected object, got {type(payload).__name__}"
        )
    return Citation(
        song=_coerce_str(_require(payload, "song", where=where)),
        path=_coerce_str(_require(payload, "path", where=where)),
        excerpt=_coerce_str(_require(payload, "excerpt", where=where)),
    )


def _parse_sub_section(payload: Mapping[str, Any], *, where: str) -> SubSection:
    """Build a SubSection. start_bar / end_bar coerced from float if needed."""
    if not isinstance(payload, Mapping):
        raise AgentOutputError(
            f"{where}: expected object, got {type(payload).__name__}"
        )
    return SubSection(
        name=_coerce_str(_require(payload, "name", where=where)),
        start_bar=_coerce_int(_require(payload, "start_bar", where=where), where=f"{where}.start_bar"),
        end_bar=_coerce_int(_require(payload, "end_bar", where=where), where=f"{where}.end_bar"),
        role=_coerce_str(payload.get("role", "")),
    )


# ============================================================================
# Schema version handling
# ============================================================================


def _check_schema_version(payload: Mapping[str, Any], supported: frozenset) -> None:
    """Warn (don't fail) on missing or unknown schema_version.

    Phase 2.2.1 is lenient to ease transition; future phases may upgrade
    to AgentOutputError if a strict version policy is desired.
    """
    version = payload.get("schema_version")
    if version is None:
        _LOG.warning(
            "agent payload has no schema_version; assuming '%s'",
            next(iter(supported), "1.0"),
        )
        return
    version_str = str(version)
    if version_str not in supported:
        _LOG.warning(
            "agent payload has unknown schema_version=%r (supported: %s); "
            "attempting to parse anyway",
            version_str, sorted(supported),
        )


# ============================================================================
# Common envelope parser — shared by all sphere parsers
# ============================================================================


def _parse_envelope(
    payload: Mapping[str, Any],
    *,
    supported_versions: frozenset,
) -> dict:
    """Parse the cross-sphere fields: error, schema_version, inspired_by,
    rationale, confidence.

    Returns a dict ready to splat into Decision(...): keys are
    `inspired_by`, `rationale`, `confidence`.

    Raises AgentOutputError on the agent-error refusal path or on
    out-of-range confidence.
    """
    if not isinstance(payload, Mapping):
        raise AgentOutputError(
            f"payload must be a JSON object, got {type(payload).__name__}"
        )
    if "error" in payload:
        raise AgentOutputError(
            f"Agent returned error: {payload['error']} "
            f"(details: {payload.get('details', 'none')})"
        )

    _check_schema_version(payload, supported_versions)

    raw_inspired = _coerce_list(payload.get("inspired_by", []), where="inspired_by")
    inspired_by = tuple(
        _parse_citation(c, where=f"inspired_by[{i}]")
        for i, c in enumerate(raw_inspired)
    )

    confidence = _coerce_float(payload.get("confidence", 0.8), where="confidence")
    if not (0.0 <= confidence <= 1.0):
        raise AgentOutputError(
            f"confidence must be in [0.0, 1.0], got {confidence}"
        )
    if confidence < 0.5:
        _LOG.warning(
            "agent returned low confidence=%.2f — "
            "consider rerunning with clearer brief or refs",
            confidence,
        )

    return {
        "inspired_by": inspired_by,
        "rationale": _coerce_str(payload.get("rationale", "")),
        "confidence": confidence,
    }


# ============================================================================
# Public parser — structure
# ============================================================================


def parse_structure_decision(payload: Mapping[str, Any]) -> Decision[StructureDecision]:
    """Parse a structure-decider agent payload into a Decision.

    Expected shape (schema 1.0):
        {
          "schema_version": "1.0",
          "structure": {
            "total_bars": int,
            "sub_sections": [{"name", "start_bar", "end_bar", "role?"}, …],
            "breath_points": [int, …],
            "transition_in": str,
            "transition_out": str
          },
          "rationale": str,
          "inspired_by": [{"song", "path", "excerpt"}, …],
          "confidence": float (0..1)
        }

    Or a refusal payload:
        {"error": "...", "details": "..."}

    Lenient on input: accepts null for lists (→ []), floats where ints
    are expected (if integral or near-integral), strings for numbers,
    missing schema_version (logs warning).

    Raises AgentOutputError on truly broken payloads (missing required
    keys, semantically invalid values).
    """
    envelope = _parse_envelope(payload, supported_versions=SUPPORTED_STRUCTURE_SCHEMA_VERSIONS)

    structure_dict = _require(payload, "structure", where="root")
    if not isinstance(structure_dict, Mapping):
        raise AgentOutputError(
            f"structure: expected object, got {type(structure_dict).__name__}"
        )

    total_bars = _coerce_int(
        _require(structure_dict, "total_bars", where="structure"),
        where="structure.total_bars",
    )
    if total_bars <= 0:
        raise AgentOutputError(
            f"structure.total_bars must be > 0, got {total_bars}"
        )

    raw_subs = _coerce_list(structure_dict.get("sub_sections", []), where="structure.sub_sections")
    sub_sections = tuple(
        _parse_sub_section(s, where=f"structure.sub_sections[{i}]")
        for i, s in enumerate(raw_subs)
    )

    raw_breath = _coerce_list(structure_dict.get("breath_points", []), where="structure.breath_points")
    breath_points = tuple(
        _coerce_int(b, where=f"structure.breath_points[{i}]")
        for i, b in enumerate(raw_breath)
    )

    structure_value = StructureDecision(
        total_bars=total_bars,
        sub_sections=sub_sections,
        breath_points=breath_points,
        transition_in=_coerce_str(structure_dict.get("transition_in", "")),
        transition_out=_coerce_str(structure_dict.get("transition_out", "")),
    )

    return Decision(value=structure_value, sphere="structure", **envelope)


def parse_structure_decision_from_response(text: str) -> Decision[StructureDecision]:
    """End-to-end: raw LLM response text → Decision[StructureDecision]."""
    return parse_structure_decision(extract_json_payload(text))


# ============================================================================
# Public parser — harmony
# ============================================================================


def parse_harmony_decision(payload: Mapping[str, Any]) -> Decision[HarmonyDecision]:
    """Parse a harmony-decider agent payload into a Decision.

    Expected shape (schema 1.0):
        {
          "schema_version": "1.0",
          "harmony": {
            "mode": str,
            "key_root": str,           // C, C#, Db, D, ..., G#, Ab, A, ...
            "progression": [str, …],    // e.g. ["i", "bVI", "bVII", "i"]
            "harmonic_rhythm": float,   // chords per bar, > 0
            "voicing_strategy": str,
            "cadence_at_end": str
          },
          "rationale": str,
          "inspired_by": [{"song", "path", "excerpt"}, …],
          "confidence": float (0..1)
        }

    Or a refusal payload: {"error": "...", "details": "..."}

    Lenient input + strict output, same conventions as
    parse_structure_decision.
    """
    envelope = _parse_envelope(payload, supported_versions=SUPPORTED_HARMONY_SCHEMA_VERSIONS)

    harmony_dict = _require(payload, "harmony", where="root")
    if not isinstance(harmony_dict, Mapping):
        raise AgentOutputError(
            f"harmony: expected object, got {type(harmony_dict).__name__}"
        )

    mode = _coerce_str(_require(harmony_dict, "mode", where="harmony"))
    if not mode.strip():
        raise AgentOutputError("harmony.mode must be non-empty")

    key_root = _coerce_str(_require(harmony_dict, "key_root", where="harmony")).strip()
    if key_root not in KEY_ROOTS:
        raise AgentOutputError(
            f"harmony.key_root {key_root!r} is not a recognized note name. "
            f"Expected one of: {sorted(KEY_ROOTS)}"
        )

    raw_progression = _coerce_list(harmony_dict.get("progression", []), where="harmony.progression")
    progression = tuple(
        _coerce_str(p) for p in raw_progression
    )

    harmonic_rhythm = _coerce_float(
        harmony_dict.get("harmonic_rhythm", 1.0),
        where="harmony.harmonic_rhythm",
    )
    if harmonic_rhythm <= 0:
        raise AgentOutputError(
            f"harmony.harmonic_rhythm must be > 0, got {harmonic_rhythm}"
        )

    harmony_value = HarmonyDecision(
        mode=mode,
        key_root=key_root,
        progression=progression,
        harmonic_rhythm=harmonic_rhythm,
        voicing_strategy=_coerce_str(harmony_dict.get("voicing_strategy", "")),
        cadence_at_end=_coerce_str(harmony_dict.get("cadence_at_end", "")),
    )

    return Decision(value=harmony_value, sphere="harmony", **envelope)


def parse_harmony_decision_from_response(text: str) -> Decision[HarmonyDecision]:
    """End-to-end: raw LLM response text → Decision[HarmonyDecision]."""
    return parse_harmony_decision(extract_json_payload(text))


# ============================================================================
# Public parser — rhythm
# ============================================================================


def parse_rhythm_decision(payload: Mapping[str, Any]) -> Decision[RhythmDecision]:
    """Parse a rhythm-decider agent payload into a Decision.

    Expected shape (schema 1.0):
        {
          "schema_version": "1.0",
          "rhythm": {
            "tempo_bpm": int (40..300),
            "time_signature": str ("4/4", "10/4", "16/8 with 3+3+4+3+3", etc.),
            "drum_pattern": str (prose),
            "subdivisions": int ∈ {4, 8, 16, 32, 64},
            "swing": float ∈ [0.0, 1.0),
            "polyrhythms": [str, …]
          },
          "rationale": str,
          "inspired_by": [{"song", "path", "excerpt"}, …],
          "confidence": float (0..1)
        }

    Or a refusal payload: {"error": "...", "details": "..."}

    Lenient input + strict output, same conventions as parse_harmony_decision
    and parse_structure_decision.
    """
    envelope = _parse_envelope(payload, supported_versions=SUPPORTED_RHYTHM_SCHEMA_VERSIONS)

    rhythm_dict = _require(payload, "rhythm", where="root")
    if not isinstance(rhythm_dict, Mapping):
        raise AgentOutputError(
            f"rhythm: expected object, got {type(rhythm_dict).__name__}"
        )

    tempo_bpm = _coerce_int(
        _require(rhythm_dict, "tempo_bpm", where="rhythm"),
        where="rhythm.tempo_bpm",
    )
    if not (TEMPO_MIN_BPM <= tempo_bpm <= TEMPO_MAX_BPM):
        raise AgentOutputError(
            f"rhythm.tempo_bpm must be in [{TEMPO_MIN_BPM}, {TEMPO_MAX_BPM}], "
            f"got {tempo_bpm}"
        )

    time_signature = _coerce_str(rhythm_dict.get("time_signature", "4/4")).strip()
    if not time_signature:
        time_signature = "4/4"

    drum_pattern = _coerce_str(rhythm_dict.get("drum_pattern", ""))

    subdivisions = _coerce_int(
        rhythm_dict.get("subdivisions", 16),
        where="rhythm.subdivisions",
    )
    if subdivisions not in VALID_SUBDIVISIONS:
        raise AgentOutputError(
            f"rhythm.subdivisions must be one of {sorted(VALID_SUBDIVISIONS)}, "
            f"got {subdivisions}"
        )

    swing = _coerce_float(rhythm_dict.get("swing", 0.0), where="rhythm.swing")
    if not (0.0 <= swing < 1.0):
        raise AgentOutputError(
            f"rhythm.swing must be in [0.0, 1.0), got {swing}"
        )

    raw_poly = _coerce_list(rhythm_dict.get("polyrhythms", []), where="rhythm.polyrhythms")
    polyrhythms = tuple(_coerce_str(p) for p in raw_poly)

    rhythm_value = RhythmDecision(
        tempo_bpm=tempo_bpm,
        time_signature=time_signature,
        drum_pattern=drum_pattern,
        subdivisions=subdivisions,
        swing=swing,
        polyrhythms=polyrhythms,
    )

    return Decision(value=rhythm_value, sphere="rhythm", **envelope)


def parse_rhythm_decision_from_response(text: str) -> Decision[RhythmDecision]:
    """End-to-end: raw LLM response text → Decision[RhythmDecision]."""
    return parse_rhythm_decision(extract_json_payload(text))


# ============================================================================
# Public parser — arrangement
# ============================================================================


def _parse_layer_spec(payload: Mapping[str, Any], *, where: str) -> LayerSpec:
    """Build a LayerSpec from a {role, instrument, enters_at_bar,
    exits_at_bar, base_velocity?} dict."""
    if not isinstance(payload, Mapping):
        raise AgentOutputError(
            f"{where}: expected object, got {type(payload).__name__}"
        )
    role = _coerce_str(_require(payload, "role", where=where)).strip()
    if not role:
        raise AgentOutputError(f"{where}.role must be non-empty")
    instrument = _coerce_str(_require(payload, "instrument", where=where))
    enters = _coerce_int(
        _require(payload, "enters_at_bar", where=where),
        where=f"{where}.enters_at_bar",
    )
    exits = _coerce_int(
        _require(payload, "exits_at_bar", where=where),
        where=f"{where}.exits_at_bar",
    )
    if enters < 0:
        raise AgentOutputError(
            f"{where}.enters_at_bar must be >= 0, got {enters}"
        )
    if exits <= enters:
        raise AgentOutputError(
            f"{where}: exits_at_bar ({exits}) must be > enters_at_bar ({enters})"
        )
    base_velocity = _coerce_int(
        payload.get("base_velocity", 100),
        where=f"{where}.base_velocity",
    )
    if not (VELOCITY_MIN <= base_velocity <= VELOCITY_MAX):
        raise AgentOutputError(
            f"{where}.base_velocity must be in [{VELOCITY_MIN}, {VELOCITY_MAX}], "
            f"got {base_velocity}"
        )
    return LayerSpec(
        role=role,
        instrument=instrument,
        enters_at_bar=enters,
        exits_at_bar=exits,
        base_velocity=base_velocity,
    )


def _parse_inst_change(payload: Mapping[str, Any], *, where: str) -> InstChange:
    """Build an InstChange from a {bar, change} dict."""
    if not isinstance(payload, Mapping):
        raise AgentOutputError(
            f"{where}: expected object, got {type(payload).__name__}"
        )
    bar = _coerce_int(
        _require(payload, "bar", where=where), where=f"{where}.bar"
    )
    if bar < 0:
        raise AgentOutputError(
            f"{where}.bar must be >= 0, got {bar}"
        )
    change = _coerce_str(_require(payload, "change", where=where))
    return InstChange(bar=bar, change=change)


def parse_arrangement_decision(payload: Mapping[str, Any]) -> Decision[ArrangementDecision]:
    """Parse an arrangement-decider agent payload into a Decision.

    Expected shape (schema 1.0):
        {
          "schema_version": "1.0",
          "arrangement": {
            "layers": [
              {"role", "instrument", "enters_at_bar", "exits_at_bar",
               "base_velocity?"}, …
            ],
            "density_curve": str ∈ VALID_DENSITY_CURVES,
            "instrumentation_changes": [{"bar", "change"}, …],
            "register_strategy": str
          },
          "rationale": str,
          "inspired_by": [{"song", "path", "excerpt"}, …],
          "confidence": float (0..1)
        }

    Or a refusal payload: {"error": "...", "details": "..."}

    Lenient input + strict output, same conventions as the other sphere
    parsers. arrangement.layers MUST have at least one entry.
    """
    envelope = _parse_envelope(
        payload, supported_versions=SUPPORTED_ARRANGEMENT_SCHEMA_VERSIONS
    )

    arr_dict = _require(payload, "arrangement", where="root")
    if not isinstance(arr_dict, Mapping):
        raise AgentOutputError(
            f"arrangement: expected object, got {type(arr_dict).__name__}"
        )

    raw_layers = _coerce_list(
        _require(arr_dict, "layers", where="arrangement"),
        where="arrangement.layers",
    )
    if not raw_layers:
        raise AgentOutputError(
            "arrangement.layers must contain at least one LayerSpec; "
            "an arrangement with no layers cannot be rendered to MIDI"
        )
    layers = tuple(
        _parse_layer_spec(item, where=f"arrangement.layers[{i}]")
        for i, item in enumerate(raw_layers)
    )

    density_curve = _coerce_str(arr_dict.get("density_curve", "medium")).strip()
    if not density_curve:
        density_curve = "medium"
    if density_curve not in VALID_DENSITY_CURVES:
        raise AgentOutputError(
            f"arrangement.density_curve {density_curve!r} not recognized. "
            f"Expected one of: {sorted(VALID_DENSITY_CURVES)}"
        )

    raw_changes = _coerce_list(
        arr_dict.get("instrumentation_changes", []),
        where="arrangement.instrumentation_changes",
    )
    instrumentation_changes = tuple(
        _parse_inst_change(item, where=f"arrangement.instrumentation_changes[{i}]")
        for i, item in enumerate(raw_changes)
    )

    arrangement_value = ArrangementDecision(
        layers=layers,
        density_curve=density_curve,
        instrumentation_changes=instrumentation_changes,
        register_strategy=_coerce_str(arr_dict.get("register_strategy", "")),
    )

    return Decision(value=arrangement_value, sphere="arrangement", **envelope)


def parse_arrangement_decision_from_response(text: str) -> Decision[ArrangementDecision]:
    """End-to-end: raw LLM response text → Decision[ArrangementDecision]."""
    return parse_arrangement_decision(extract_json_payload(text))


__all__ = [
    "AgentOutputError",
    "SUPPORTED_STRUCTURE_SCHEMA_VERSIONS",
    "SUPPORTED_HARMONY_SCHEMA_VERSIONS",
    "SUPPORTED_RHYTHM_SCHEMA_VERSIONS",
    "SUPPORTED_ARRANGEMENT_SCHEMA_VERSIONS",
    "TEMPO_MIN_BPM",
    "TEMPO_MAX_BPM",
    "VALID_SUBDIVISIONS",
    "VALID_DENSITY_CURVES",
    "VELOCITY_MIN",
    "VELOCITY_MAX",
    "extract_json_payload",
    "parse_structure_decision",
    "parse_structure_decision_from_response",
    "parse_harmony_decision",
    "parse_harmony_decision_from_response",
    "parse_rhythm_decision",
    "parse_rhythm_decision_from_response",
    "parse_arrangement_decision",
    "parse_arrangement_decision_from_response",
]
