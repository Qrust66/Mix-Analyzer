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
    Citation,
    Decision,
    StructureDecision,
    SubSection,
)

_LOG = logging.getLogger(__name__)

# Schema versions this parser understands. Bump when the agent contract
# changes in a way that requires a parser update; keep the old version
# entries as long as we want to support backward compatibility.
SUPPORTED_STRUCTURE_SCHEMA_VERSIONS = frozenset({"1.0"})


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
# Public parser
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
    if not isinstance(payload, Mapping):
        raise AgentOutputError(
            f"payload must be a JSON object, got {type(payload).__name__}"
        )

    if "error" in payload:
        raise AgentOutputError(
            f"Agent returned error: {payload['error']} "
            f"(details: {payload.get('details', 'none')})"
        )

    _check_schema_version(payload, SUPPORTED_STRUCTURE_SCHEMA_VERSIONS)

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
            "structure-decider returned low confidence=%.2f — "
            "consider rerunning with clearer brief or refs",
            confidence,
        )

    return Decision(
        value=structure_value,
        sphere="structure",
        inspired_by=inspired_by,
        rationale=_coerce_str(payload.get("rationale", "")),
        confidence=confidence,
    )


def parse_structure_decision_from_response(text: str) -> Decision[StructureDecision]:
    """End-to-end: raw LLM response text → Decision[StructureDecision].

    Combines extract_json_payload (strip fences, extract from prose) with
    parse_structure_decision (schema validation + coercion). Use this from
    orchestrator code that gets the raw agent output as a string.
    """
    payload = extract_json_payload(text)
    return parse_structure_decision(payload)


__all__ = [
    "AgentOutputError",
    "SUPPORTED_STRUCTURE_SCHEMA_VERSIONS",
    "extract_json_payload",
    "parse_structure_decision",
    "parse_structure_decision_from_response",
]
