"""mix_engine.blueprint — typed contract between mix agents and the .als writer.

Mirrors composition_engine.blueprint but for mix-side decisions: routing,
EQ corrections, dynamics, automation envelopes, mastering moves.

Phase 4.1 ships the foundation types + the diagnostic lane. Other lanes
materialize one-by-one as their producing agent gets built.
"""
from __future__ import annotations

from mix_engine.blueprint.schema import (
    MIX_LANES,
    Anomaly,
    DiagnosticReport,
    FullMixMetrics,
    HealthScore,
    MixBlueprint,
    MixCitation,
    MixDecision,
    TrackInfo,
)
from mix_engine.blueprint.agent_parsers import (
    MixAgentOutputError,
    SUPPORTED_DIAGNOSTIC_SCHEMA_VERSIONS,
    VALID_ANOMALY_SEVERITIES,
    VALID_CITATION_KINDS,
    VALID_TRACK_TYPES,
    extract_json_payload,
    parse_diagnostic_decision,
    parse_diagnostic_decision_from_response,
)

__all__ = [
    "MIX_LANES",
    "Anomaly",
    "DiagnosticReport",
    "FullMixMetrics",
    "HealthScore",
    "MixAgentOutputError",
    "MixBlueprint",
    "MixCitation",
    "MixDecision",
    "TrackInfo",
    "SUPPORTED_DIAGNOSTIC_SCHEMA_VERSIONS",
    "VALID_ANOMALY_SEVERITIES",
    "VALID_CITATION_KINDS",
    "VALID_TRACK_TYPES",
    "extract_json_payload",
    "parse_diagnostic_decision",
    "parse_diagnostic_decision_from_response",
]
