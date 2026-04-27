"""Parsers for sphere-agent JSON outputs.

Each sphere agent (structure-decider, harmony-decider, …) emits a JSON
payload that the orchestrator parses into a typed `Decision[T]`. This
module hosts the parsers, keeping the schema-validation logic in one
place rather than scattered across agent integrations.

Phase 2.2: only structure parser is implemented. Other spheres land in
their respective Phase 2.X commits as their agents come online.
"""
from __future__ import annotations

from typing import Any, Mapping

from composition_engine.blueprint.schema import (
    Citation,
    Decision,
    StructureDecision,
    SubSection,
)


class AgentOutputError(ValueError):
    """Raised when an agent's JSON payload doesn't match the expected schema."""


def _require(payload: Mapping[str, Any], key: str, expected_type: type, *, where: str) -> Any:
    """Return payload[key], raising AgentOutputError if missing or wrong type."""
    if key not in payload:
        raise AgentOutputError(f"{where}: missing required key {key!r}")
    value = payload[key]
    if not isinstance(value, expected_type):
        raise AgentOutputError(
            f"{where}: key {key!r} expected {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )
    return value


def _parse_citation(payload: Mapping[str, Any], *, where: str) -> Citation:
    """Validate and build a Citation from a {song, path, excerpt} dict."""
    return Citation(
        song=_require(payload, "song", str, where=where),
        path=_require(payload, "path", str, where=where),
        excerpt=_require(payload, "excerpt", str, where=where),
    )


def _parse_sub_section(payload: Mapping[str, Any], *, where: str) -> SubSection:
    """Validate and build a SubSection. role is optional (defaults to '')."""
    return SubSection(
        name=_require(payload, "name", str, where=where),
        start_bar=_require(payload, "start_bar", int, where=where),
        end_bar=_require(payload, "end_bar", int, where=where),
        role=str(payload.get("role", "")),
    )


def parse_structure_decision(payload: Mapping[str, Any]) -> Decision[StructureDecision]:
    """Parse a structure-decider agent JSON payload into a Decision.

    Expected shape:
        {
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

    Raises AgentOutputError if the payload is malformed. Caller is
    responsible for handling the error path (retry the agent, fall back
    to manual fill, etc.).
    """
    if "error" in payload:
        raise AgentOutputError(
            f"Agent returned error: {payload['error']} "
            f"(details: {payload.get('details', 'none')})"
        )

    structure_dict = _require(payload, "structure", dict, where="root")

    total_bars = _require(structure_dict, "total_bars", int, where="structure")
    if total_bars <= 0:
        raise AgentOutputError(
            f"structure.total_bars must be > 0, got {total_bars}"
        )

    raw_subs = structure_dict.get("sub_sections", [])
    if not isinstance(raw_subs, list):
        raise AgentOutputError(
            f"structure.sub_sections must be a list, got {type(raw_subs).__name__}"
        )
    sub_sections = tuple(
        _parse_sub_section(s, where=f"structure.sub_sections[{i}]")
        for i, s in enumerate(raw_subs)
    )

    raw_breath = structure_dict.get("breath_points", [])
    if not isinstance(raw_breath, list) or not all(isinstance(b, int) for b in raw_breath):
        raise AgentOutputError(
            "structure.breath_points must be a list of ints"
        )
    breath_points = tuple(raw_breath)

    structure_value = StructureDecision(
        total_bars=total_bars,
        sub_sections=sub_sections,
        breath_points=breath_points,
        transition_in=str(structure_dict.get("transition_in", "")),
        transition_out=str(structure_dict.get("transition_out", "")),
    )

    raw_inspired = payload.get("inspired_by", [])
    if not isinstance(raw_inspired, list):
        raise AgentOutputError(
            f"inspired_by must be a list, got {type(raw_inspired).__name__}"
        )
    inspired_by = tuple(
        _parse_citation(c, where=f"inspired_by[{i}]")
        for i, c in enumerate(raw_inspired)
    )

    confidence_raw = payload.get("confidence", 0.8)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError) as exc:
        raise AgentOutputError(f"confidence must be a number: {exc}") from exc
    if not (0.0 <= confidence <= 1.0):
        raise AgentOutputError(
            f"confidence must be in [0.0, 1.0], got {confidence}"
        )

    return Decision(
        value=structure_value,
        sphere="structure",
        inspired_by=inspired_by,
        rationale=str(payload.get("rationale", "")),
        confidence=confidence,
    )


__all__ = [
    "AgentOutputError",
    "parse_structure_decision",
]
