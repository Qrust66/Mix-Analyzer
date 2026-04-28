"""mix_engine.blueprint — typed contract between mix agents and the .als writer.

Mirrors composition_engine.blueprint but for mix-side decisions: routing,
EQ corrections, dynamics, automation envelopes, mastering moves.

Phase 4.1 ships the foundation types + the diagnostic lane.
Phase 4.2 adds the eq_corrective lane (Tier A schema).
Other lanes materialize one-by-one as their producing agent gets built.
"""
from __future__ import annotations

from mix_engine.blueprint.schema import (
    EQ_FREQ_MAX_HZ,
    EQ_FREQ_MIN_HZ,
    EQ_GAIN_MAX_DB,
    EQ_GAIN_MIN_DB,
    EQ_Q_MAX,
    EQ_Q_MIN,
    MIX_LANES,
    Anomaly,
    DiagnosticReport,
    EQAutomationPoint,
    EQBandCorrection,
    EQCorrectiveDecision,
    FullMixMetrics,
    HealthScore,
    MixBlueprint,
    MixCitation,
    MixDecision,
    TrackInfo,
    VALID_CHAIN_POSITIONS,
    VALID_EQ_BAND_TYPES,
    VALID_EQ_INTENTS,
    VALID_FILTER_SLOPES_DB_PER_OCT,
)
from mix_engine.blueprint.agent_parsers import (
    MixAgentOutputError,
    SUPPORTED_DIAGNOSTIC_SCHEMA_VERSIONS,
    SUPPORTED_EQ_CORRECTIVE_SCHEMA_VERSIONS,
    VALID_ANOMALY_SEVERITIES,
    VALID_CITATION_KINDS,
    VALID_TRACK_TYPES,
    extract_json_payload,
    parse_diagnostic_decision,
    parse_diagnostic_decision_from_response,
    parse_eq_corrective_decision,
    parse_eq_corrective_decision_from_response,
)

__all__ = [
    "MIX_LANES",
    # Foundation types
    "Anomaly",
    "DiagnosticReport",
    "FullMixMetrics",
    "HealthScore",
    "MixAgentOutputError",
    "MixBlueprint",
    "MixCitation",
    "MixDecision",
    "TrackInfo",
    # EQ corrective lane (Phase 4.2)
    "EQ_FREQ_MAX_HZ",
    "EQ_FREQ_MIN_HZ",
    "EQ_GAIN_MAX_DB",
    "EQ_GAIN_MIN_DB",
    "EQ_Q_MAX",
    "EQ_Q_MIN",
    "EQAutomationPoint",
    "EQBandCorrection",
    "EQCorrectiveDecision",
    "VALID_CHAIN_POSITIONS",
    "VALID_EQ_BAND_TYPES",
    "VALID_EQ_INTENTS",
    "VALID_FILTER_SLOPES_DB_PER_OCT",
    # Schema versions + canonical enums
    "SUPPORTED_DIAGNOSTIC_SCHEMA_VERSIONS",
    "SUPPORTED_EQ_CORRECTIVE_SCHEMA_VERSIONS",
    "VALID_ANOMALY_SEVERITIES",
    "VALID_CITATION_KINDS",
    "VALID_TRACK_TYPES",
    # Parsers
    "extract_json_payload",
    "parse_diagnostic_decision",
    "parse_diagnostic_decision_from_response",
    "parse_eq_corrective_decision",
    "parse_eq_corrective_decision_from_response",
]
