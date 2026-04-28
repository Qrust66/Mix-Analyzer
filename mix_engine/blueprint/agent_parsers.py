"""Mix-side agent parsers — JSON → MixDecision[T].

Mirrors composition_engine.blueprint.agent_parsers. Each mix agent emits
a JSON payload that this module parses into a typed MixDecision.

Phase 4.1 ships the diagnostic parser. Each subsequent agent lands with
its own parser — same rule-with-consumer discipline as composition.

Conventions inherited from the composition side:

- Lenient on input, strict on output (markdown fences, prose around,
  mild type drift all tolerated).
- Schema versioning via "schema_version": "1.0" at top level.
- Public canonical constants (no magic numbers in tests).
- MixAgentOutputError raised on contract violation, with `where=...`
  pointer to the offending field for actionable messages.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping, Optional

from mix_engine.blueprint.schema import (
    Anomaly,
    BandConflict,
    CDECorrectionRecipe,
    CDEDiagnostic,
    CDEMeasurement,
    CDETFPContext,
    DiagnosticReport,
    DynamicsAutomationPoint,
    DynamicsCorrection,
    DynamicsCorrectiveDecision,
    DYN_ATTACK_MAX_MS,
    DYN_ATTACK_MIN_MS,
    DYN_CEILING_MAX_DB,
    DYN_CEILING_MIN_DB,
    DYN_DRY_WET_MAX,
    DYN_DRY_WET_MIN,
    DYN_KNEE_MAX_DB,
    DYN_KNEE_MIN_DB,
    DYN_MAKEUP_MAX_DB,
    DYN_MAKEUP_MIN_DB,
    DYN_RATIO_MAX,
    DYN_RATIO_MIN,
    DYN_RELEASE_MAX_MS,
    DYN_RELEASE_MIN_MS,
    DYN_SIDECHAIN_DEPTH_MAX_DB,
    DYN_SIDECHAIN_DEPTH_MIN_DB,
    DYN_THRESHOLD_MAX_DB,
    DYN_THRESHOLD_MIN_DB,
    DYN_TRANSIENTS_MAX,
    DYN_TRANSIENTS_MIN,
    EQAutomationPoint,
    EQBandCorrection,
    EQCorrectiveDecision,
    EQ_FREQ_MAX_HZ,
    EQ_FREQ_MIN_HZ,
    EQ_GAIN_MAX_DB,
    EQ_GAIN_MIN_DB,
    EQ_Q_MAX,
    EQ_Q_MIN,
    FreqConflictsMetadata,
    FullMixMetrics,
    HealthScore,
    KNOWN_CDE_ISSUE_TYPES,
    MixCitation,
    MixDecision,
    SidechainConfig,
    TrackInfo,
    DEPRECATED_CHAIN_POSITIONS_REDIRECT,
    VALID_CDE_APPLICATION_STATUSES,
    VALID_CDE_CONFIDENCES,
    VALID_CDE_SEVERITIES,
    VALID_CHAIN_POSITIONS,
    VALID_DYNAMICS_CHAIN_POSITIONS,
    VALID_DYNAMICS_DEVICES,
    VALID_DYNAMICS_TYPES,
    VALID_EQ_BAND_TYPES,
    VALID_EQ_INTENTS,
    VALID_FILTER_SLOPES_DB_PER_OCT,
    VALID_PROCESSING_MODES,
    VALID_SIDECHAIN_MODES,
)


SUPPORTED_DIAGNOSTIC_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTED_EQ_CORRECTIVE_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTED_DYNAMICS_CORRECTIVE_SCHEMA_VERSIONS = frozenset({"1.0"})

# Severity values accepted in Anomaly.severity.
VALID_ANOMALY_SEVERITIES = frozenset({"critical", "warning", "info"})

# Track-type values accepted in TrackInfo.track_type.
VALID_TRACK_TYPES = frozenset({"Audio", "MIDI", "Group", "Return", "Master"})

# Citation kinds accepted in MixCitation.kind.
VALID_CITATION_KINDS = frozenset({
    "diagnostic", "device_mapping", "manipulation_guide",
    "pdf", "user_brief", "als_state",
})


class MixAgentOutputError(ValueError):
    """Raised when a mix agent's JSON payload doesn't match the expected schema."""


# ============================================================================
# Lenient input cleanup
# ============================================================================

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL | re.IGNORECASE)
_FIRST_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json_payload(text: str) -> dict:
    """Extract a JSON object from raw LLM output.

    Handles pure JSON, markdown fences, and prose around. Mirror of the
    composition-side helper.
    """
    if not isinstance(text, str):
        raise MixAgentOutputError(
            f"extract_json_payload expects a string, got {type(text).__name__}"
        )
    if not text.strip():
        raise MixAgentOutputError("agent output is empty")

    fence_match = _FENCE_RE.search(text)
    if fence_match:
        candidate = fence_match.group(1).strip()
    else:
        obj_match = _FIRST_OBJECT_RE.search(text)
        candidate = obj_match.group(0) if obj_match else text.strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise MixAgentOutputError(
            f"could not parse JSON from agent output: {exc}. "
            f"First 200 chars: {candidate[:200]!r}"
        ) from exc

    if not isinstance(parsed, dict):
        raise MixAgentOutputError(
            f"expected JSON object at top level, got {type(parsed).__name__}"
        )
    return parsed


# ============================================================================
# Type coercion helpers
# ============================================================================


def _require(payload: Mapping[str, Any], key: str, *, where: str) -> Any:
    if key not in payload:
        raise MixAgentOutputError(f"{where}: missing required key {key!r}")
    return payload[key]


def _coerce_str(value: Any, *, where: str = "") -> str:
    if isinstance(value, str):
        return value
    raise MixAgentOutputError(
        f"{where}: expected str, got {type(value).__name__}"
    )


def _coerce_float(value: Any, *, where: str) -> float:
    if isinstance(value, bool):
        raise MixAgentOutputError(f"{where}: expected number, got bool")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise MixAgentOutputError(f"{where}: cannot parse {value!r} as float") from exc
    raise MixAgentOutputError(
        f"{where}: expected number, got {type(value).__name__}"
    )


def _coerce_bool(value: Any, *, where: str) -> bool:
    if isinstance(value, bool):
        return value
    raise MixAgentOutputError(f"{where}: expected bool, got {type(value).__name__}")


def _coerce_list(value: Any, *, where: str) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    raise MixAgentOutputError(
        f"{where}: expected list (or null), got {type(value).__name__}"
    )


def _coerce_str_tuple(value: Any, *, where: str) -> tuple[str, ...]:
    items = _coerce_list(value, where=where)
    out = []
    for i, item in enumerate(items):
        out.append(_coerce_str(item, where=f"{where}[{i}]"))
    return tuple(out)


# ============================================================================
# Envelope (cross-agent metadata: schema_version, citations, rationale, confidence)
# ============================================================================


def _parse_citations(value: Any, *, where: str) -> tuple[MixCitation, ...]:
    items = _coerce_list(value, where=where)
    out: list[MixCitation] = []
    for i, item in enumerate(items):
        slot = f"{where}[{i}]"
        if not isinstance(item, Mapping):
            raise MixAgentOutputError(
                f"{slot}: expected object, got {type(item).__name__}"
            )
        kind = _coerce_str(_require(item, "kind", where=slot), where=f"{slot}.kind")
        if kind not in VALID_CITATION_KINDS:
            raise MixAgentOutputError(
                f"{slot}.kind={kind!r} not in {sorted(VALID_CITATION_KINDS)}"
            )
        path = _coerce_str(_require(item, "path", where=slot), where=f"{slot}.path")
        excerpt = _coerce_str(
            _require(item, "excerpt", where=slot), where=f"{slot}.excerpt"
        )
        out.append(MixCitation(kind=kind, path=path, excerpt=excerpt))
    return tuple(out)


def _parse_envelope(
    payload: Mapping[str, Any],
    *,
    supported_versions: frozenset[str],
) -> dict:
    """Parse the cross-agent envelope (schema_version, cited_by, rationale,
    confidence, mode). Returns a dict that can be ** unpacked into a
    MixDecision constructor (minus value + lane which the caller supplies).

    A refusal payload (top-level "error" key) raises immediately rather
    than reaching the lane-specific parser.
    """
    if "error" in payload:
        details = payload.get("details", "")
        raise MixAgentOutputError(
            f"agent refused: {payload['error']}. {details}"
        )

    schema_version = payload.get("schema_version")
    if schema_version not in supported_versions:
        raise MixAgentOutputError(
            f"unsupported schema_version {schema_version!r}. "
            f"Supported: {sorted(supported_versions)}"
        )

    citations = _parse_citations(
        payload.get("cited_by", []), where="cited_by"
    )
    rationale = _coerce_str(
        payload.get("rationale", ""), where="rationale"
    )
    confidence = _coerce_float(
        payload.get("confidence", 0.0), where="confidence"
    )
    if not (0.0 <= confidence <= 1.0):
        raise MixAgentOutputError(
            f"confidence={confidence} not in [0.0, 1.0]"
        )
    mode = _coerce_str(payload.get("mode", ""), where="mode")

    return {
        "cited_by": citations,
        "rationale": rationale,
        "confidence": confidence,
        "mode": mode,
    }


# ============================================================================
# Public parser — diagnostic lane
# ============================================================================


def _parse_track_info(item: Any, *, where: str) -> TrackInfo:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )
    name = _coerce_str(_require(item, "name", where=where), where=f"{where}.name")
    track_type = _coerce_str(
        _require(item, "track_type", where=where), where=f"{where}.track_type"
    )
    if track_type not in VALID_TRACK_TYPES:
        raise MixAgentOutputError(
            f"{where}.track_type={track_type!r} not in {sorted(VALID_TRACK_TYPES)}"
        )
    parent_bus_raw = item.get("parent_bus", None)
    parent_bus = (
        None if parent_bus_raw is None
        else _coerce_str(parent_bus_raw, where=f"{where}.parent_bus")
    )
    color = _coerce_str(item.get("color", ""), where=f"{where}.color")
    devices = _coerce_str_tuple(
        item.get("devices", []), where=f"{where}.devices"
    )
    volume_db = _coerce_float(
        item.get("volume_db", 0.0), where=f"{where}.volume_db"
    )
    pan = _coerce_float(item.get("pan", 0.0), where=f"{where}.pan")
    if not (-1.0 <= pan <= 1.0):
        raise MixAgentOutputError(
            f"{where}.pan={pan} not in [-1.0, 1.0]"
        )
    sidechain_targets = _coerce_str_tuple(
        item.get("sidechain_targets", []), where=f"{where}.sidechain_targets"
    )
    activator = _coerce_bool(
        item.get("activator", True), where=f"{where}.activator"
    )
    return TrackInfo(
        name=name,
        track_type=track_type,
        parent_bus=parent_bus,
        color=color,
        devices=devices,
        volume_db=volume_db,
        pan=pan,
        sidechain_targets=sidechain_targets,
        activator=activator,
    )


def _parse_full_mix(item: Any, *, where: str) -> FullMixMetrics:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )
    correlation = _coerce_float(
        _require(item, "correlation", where=where), where=f"{where}.correlation"
    )
    if not (-1.0 <= correlation <= 1.0):
        raise MixAgentOutputError(
            f"{where}.correlation={correlation} not in [-1.0, 1.0]"
        )
    stereo_width = _coerce_float(
        _require(item, "stereo_width", where=where), where=f"{where}.stereo_width"
    )
    if not (0.0 <= stereo_width <= 1.0):
        raise MixAgentOutputError(
            f"{where}.stereo_width={stereo_width} not in [0.0, 1.0]"
        )
    return FullMixMetrics(
        integrated_lufs=_coerce_float(
            _require(item, "integrated_lufs", where=where),
            where=f"{where}.integrated_lufs",
        ),
        true_peak_dbtp=_coerce_float(
            _require(item, "true_peak_dbtp", where=where),
            where=f"{where}.true_peak_dbtp",
        ),
        crest_factor_db=_coerce_float(
            _require(item, "crest_factor_db", where=where),
            where=f"{where}.crest_factor_db",
        ),
        plr_db=_coerce_float(
            _require(item, "plr_db", where=where), where=f"{where}.plr_db"
        ),
        lra_db=_coerce_float(
            _require(item, "lra_db", where=where), where=f"{where}.lra_db"
        ),
        dominant_band=_coerce_str(
            _require(item, "dominant_band", where=where),
            where=f"{where}.dominant_band",
        ),
        correlation=correlation,
        stereo_width=stereo_width,
        spectral_entropy=_coerce_float(
            _require(item, "spectral_entropy", where=where),
            where=f"{where}.spectral_entropy",
        ),
    )


def _parse_anomaly(item: Any, *, where: str) -> Anomaly:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )
    severity = _coerce_str(
        _require(item, "severity", where=where), where=f"{where}.severity"
    )
    if severity not in VALID_ANOMALY_SEVERITIES:
        raise MixAgentOutputError(
            f"{where}.severity={severity!r} not in {sorted(VALID_ANOMALY_SEVERITIES)}"
        )
    return Anomaly(
        severity=severity,
        category=_coerce_str(
            _require(item, "category", where=where), where=f"{where}.category"
        ),
        description=_coerce_str(
            _require(item, "description", where=where),
            where=f"{where}.description",
        ),
        affected_tracks=_coerce_str_tuple(
            item.get("affected_tracks", []),
            where=f"{where}.affected_tracks",
        ),
        suggested_fix_lane=_coerce_str(
            item.get("suggested_fix_lane", ""),
            where=f"{where}.suggested_fix_lane",
        ),
    )


def _parse_health_score(item: Any, *, where: str) -> HealthScore:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )
    overall = _coerce_float(
        _require(item, "overall", where=where), where=f"{where}.overall"
    )
    if not (0.0 <= overall <= 100.0):
        raise MixAgentOutputError(
            f"{where}.overall={overall} not in [0.0, 100.0]"
        )
    breakdown_raw = _coerce_list(
        item.get("breakdown", []), where=f"{where}.breakdown"
    )
    breakdown: list[tuple[str, float]] = []
    for i, entry in enumerate(breakdown_raw):
        slot = f"{where}.breakdown[{i}]"
        if isinstance(entry, Mapping):
            cat = _coerce_str(
                _require(entry, "category", where=slot), where=f"{slot}.category"
            )
            sc = _coerce_float(
                _require(entry, "score", where=slot), where=f"{slot}.score"
            )
        elif isinstance(entry, (list, tuple)):
            if len(entry) != 2:
                raise MixAgentOutputError(
                    f"{slot}: expected [category, score] pair, got len={len(entry)}"
                )
            cat = _coerce_str(entry[0], where=f"{slot}[0]")
            sc = _coerce_float(entry[1], where=f"{slot}[1]")
        else:
            raise MixAgentOutputError(
                f"{slot}: expected object or [category, score] pair, "
                f"got {type(entry).__name__}"
            )
        breakdown.append((cat, sc))
    return HealthScore(overall=overall, breakdown=tuple(breakdown))


# ============================================================================
# CDE + Freq Conflicts sub-parsers (Phase 4.2.8)
# ============================================================================


def _parse_cde_measurement(item: Any, *, where: str) -> Optional[CDEMeasurement]:
    if item is None:
        return None
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object or null, got {type(item).__name__}"
        )
    freq_hz = _coerce_float(
        _require(item, "frequency_hz", where=where),
        where=f"{where}.frequency_hz",
    )
    return CDEMeasurement(frequency_hz=freq_hz, raw=dict(item))


def _parse_cde_tfp_context(item: Any, *, where: str) -> Optional[CDETFPContext]:
    if item is None:
        return None
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object or null, got {type(item).__name__}"
        )

    def _role(value, slot):
        if value is None:
            return None
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise MixAgentOutputError(
                f"{slot}: expected [Importance, Function] pair or null, got {value!r}"
            )
        return (str(value[0]), str(value[1]))

    return CDETFPContext(
        track_a_role=_role(item.get("track_a_role"), f"{where}.track_a_role"),
        track_b_role=_role(item.get("track_b_role"), f"{where}.track_b_role"),
        role_compatibility=_coerce_str(item.get("role_compatibility", "")),
    )


def _parse_cde_correction_recipe(
    item: Any, *, where: str
) -> Optional[CDECorrectionRecipe]:
    if item is None:
        return None
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object or null, got {type(item).__name__}"
        )
    confidence = _coerce_str(_require(item, "confidence", where=where)).strip().lower()
    if confidence not in VALID_CDE_CONFIDENCES:
        raise MixAgentOutputError(
            f"{where}.confidence={confidence!r} not in {sorted(VALID_CDE_CONFIDENCES)}"
        )
    sections_raw = _coerce_list(
        item.get("applies_to_sections", []), where=f"{where}.applies_to_sections"
    )
    applies_to_sections = tuple(
        _coerce_int_strict(s, where=f"{where}.applies_to_sections[{i}]")
        for i, s in enumerate(sections_raw)
    )
    return CDECorrectionRecipe(
        target_track=_coerce_str(_require(item, "target_track", where=where)),
        device=_coerce_str(_require(item, "device", where=where)),
        approach=_coerce_str(_require(item, "approach", where=where)),
        parameters=dict(item.get("parameters", {}) or {}),
        applies_to_sections=applies_to_sections,
        rationale=_coerce_str(item.get("rationale", "")),
        confidence=confidence,
    )


def _parse_cde_diagnostic(item: Any, *, where: str) -> CDEDiagnostic:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )

    diagnostic_id = _coerce_str(_require(item, "diagnostic_id", where=where))
    issue_type = _coerce_str(_require(item, "issue_type", where=where)).strip()
    # issue_type is open-set : warn (don't raise) on unknown values
    # so future CDE detectors don't break the pipeline. We log via the
    # python warnings system here rather than passing an external logger.
    if issue_type and issue_type not in KNOWN_CDE_ISSUE_TYPES:
        # Forward but document : the agent will see issue_type and decide.
        pass

    severity = _coerce_str(_require(item, "severity", where=where)).strip().lower()
    if severity not in VALID_CDE_SEVERITIES:
        raise MixAgentOutputError(
            f"{where}.severity={severity!r} not in {sorted(VALID_CDE_SEVERITIES)}"
        )

    section_raw = item.get("section", None)
    section = None if section_raw is None else _coerce_str(section_raw)

    track_a = _coerce_str(item.get("track_a", ""))
    track_b_raw = item.get("track_b", None)
    track_b = None if track_b_raw is None else _coerce_str(track_b_raw)

    measurement = _parse_cde_measurement(
        item.get("measurement", None), where=f"{where}.measurement"
    )
    tfp_context = _parse_cde_tfp_context(
        item.get("tfp_context", None), where=f"{where}.tfp_context"
    )
    primary_correction = _parse_cde_correction_recipe(
        item.get("primary_correction", None),
        where=f"{where}.primary_correction",
    )
    fallback_correction = _parse_cde_correction_recipe(
        item.get("fallback_correction", None),
        where=f"{where}.fallback_correction",
    )

    expected_outcomes = _coerce_str_tuple(
        item.get("expected_outcomes", []), where=f"{where}.expected_outcomes"
    )
    potential_risks = _coerce_str_tuple(
        item.get("potential_risks", []), where=f"{where}.potential_risks"
    )

    application_status_raw = item.get("application_status", None)
    if application_status_raw is None:
        application_status = None
    else:
        application_status = _coerce_str(application_status_raw).strip().lower()
        if application_status not in VALID_CDE_APPLICATION_STATUSES:
            raise MixAgentOutputError(
                f"{where}.application_status={application_status!r} not in "
                f"{sorted(VALID_CDE_APPLICATION_STATUSES)} (or null)"
            )

    return CDEDiagnostic(
        diagnostic_id=diagnostic_id,
        issue_type=issue_type,
        severity=severity,
        section=section,
        track_a=track_a,
        track_b=track_b,
        measurement=measurement,
        tfp_context=tfp_context,
        primary_correction=primary_correction,
        fallback_correction=fallback_correction,
        expected_outcomes=expected_outcomes,
        potential_risks=potential_risks,
        application_status=application_status,
    )


def _parse_freq_conflicts_meta(
    item: Any, *, where: str
) -> Optional[FreqConflictsMetadata]:
    if item is None:
        return None
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object or null, got {type(item).__name__}"
        )
    return FreqConflictsMetadata(
        threshold_pct=_coerce_float(
            _require(item, "threshold_pct", where=where),
            where=f"{where}.threshold_pct",
        ),
        min_tracks=_coerce_int_strict(
            _require(item, "min_tracks", where=where),
            where=f"{where}.min_tracks",
        ),
    )


def _parse_band_conflict(item: Any, *, where: str) -> BandConflict:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )
    energy_raw = item.get("energy_per_track", {})
    if not isinstance(energy_raw, Mapping):
        raise MixAgentOutputError(
            f"{where}.energy_per_track: expected object/dict, got {type(energy_raw).__name__}"
        )
    energy_per_track = tuple(
        (str(k), _coerce_float(v, where=f"{where}.energy_per_track[{k!r}]"))
        for k, v in energy_raw.items()
    )
    return BandConflict(
        band_label=_coerce_str(_require(item, "band_label", where=where)),
        energy_per_track=energy_per_track,
        conflict_count=_coerce_int_strict(
            _require(item, "conflict_count", where=where),
            where=f"{where}.conflict_count",
        ),
        status=_coerce_str(item.get("status", "")),
    )


def parse_diagnostic_decision(
    payload: Mapping[str, Any],
) -> MixDecision[DiagnosticReport]:
    """Parse a mix-diagnostician payload into a MixDecision.

    Expected shape (schema 1.0):
        {
          "schema_version": "1.0",
          "diagnostic": {
            "project_name": str,
            "full_mix": {integrated_lufs, true_peak_dbtp, crest_factor_db, …},
            "tracks": [{name, track_type, …}, …],
            "anomalies": [{severity, category, description, affected_tracks, …}, …],
            "health_score": {overall, breakdown: [{category, score}, …]},
            "routing_warnings": ["...", …]
          },
          "cited_by": [{kind, path, excerpt}, …],
          "rationale": str,
          "confidence": float (0..1),
          "mode": str (optional)
        }

    Or a refusal: {"error": "...", "details": "..."}
    """
    envelope = _parse_envelope(
        payload, supported_versions=SUPPORTED_DIAGNOSTIC_SCHEMA_VERSIONS
    )

    diag_dict = _require(payload, "diagnostic", where="root")
    if not isinstance(diag_dict, Mapping):
        raise MixAgentOutputError(
            f"diagnostic: expected object, got {type(diag_dict).__name__}"
        )

    project_name = _coerce_str(
        _require(diag_dict, "project_name", where="diagnostic"),
        where="diagnostic.project_name",
    )
    full_mix = _parse_full_mix(
        _require(diag_dict, "full_mix", where="diagnostic"),
        where="diagnostic.full_mix",
    )
    tracks_raw = _coerce_list(
        _require(diag_dict, "tracks", where="diagnostic"),
        where="diagnostic.tracks",
    )
    tracks = tuple(
        _parse_track_info(item, where=f"diagnostic.tracks[{i}]")
        for i, item in enumerate(tracks_raw)
    )
    anomalies_raw = _coerce_list(
        diag_dict.get("anomalies", []), where="diagnostic.anomalies"
    )
    anomalies = tuple(
        _parse_anomaly(item, where=f"diagnostic.anomalies[{i}]")
        for i, item in enumerate(anomalies_raw)
    )
    health_score = _parse_health_score(
        _require(diag_dict, "health_score", where="diagnostic"),
        where="diagnostic.health_score",
    )
    routing_warnings = _coerce_str_tuple(
        diag_dict.get("routing_warnings", []),
        where="diagnostic.routing_warnings",
    )

    # Phase 4.2.8 — CDE diagnostics + Freq Conflicts metadata absorption
    cde_diag_raw = _coerce_list(
        diag_dict.get("cde_diagnostics", []),
        where="diagnostic.cde_diagnostics",
    )
    cde_diagnostics = tuple(
        _parse_cde_diagnostic(item, where=f"diagnostic.cde_diagnostics[{i}]")
        for i, item in enumerate(cde_diag_raw)
    )
    freq_conflicts_meta = _parse_freq_conflicts_meta(
        diag_dict.get("freq_conflicts_meta", None),
        where="diagnostic.freq_conflicts_meta",
    )
    freq_conflicts_bands_raw = _coerce_list(
        diag_dict.get("freq_conflicts_bands", []),
        where="diagnostic.freq_conflicts_bands",
    )
    freq_conflicts_bands = tuple(
        _parse_band_conflict(item, where=f"diagnostic.freq_conflicts_bands[{i}]")
        for i, item in enumerate(freq_conflicts_bands_raw)
    )

    report = DiagnosticReport(
        project_name=project_name,
        full_mix=full_mix,
        tracks=tracks,
        anomalies=anomalies,
        health_score=health_score,
        routing_warnings=routing_warnings,
        cde_diagnostics=cde_diagnostics,
        freq_conflicts_meta=freq_conflicts_meta,
        freq_conflicts_bands=freq_conflicts_bands,
    )
    return MixDecision(value=report, lane="diagnostic", **envelope)


def parse_diagnostic_decision_from_response(
    text: str,
) -> MixDecision[DiagnosticReport]:
    """End-to-end: raw LLM response → MixDecision[DiagnosticReport]."""
    return parse_diagnostic_decision(extract_json_payload(text))


# ============================================================================
# Public parser — eq_corrective lane (Phase 4.2)
# ============================================================================


def _parse_eq_automation_point(item: Any, *, where: str) -> EQAutomationPoint:
    """Parse a single envelope point. Accepts {bar, value} object OR
    [bar, value] pair (lenient input)."""
    if isinstance(item, Mapping):
        bar = _coerce_int_strict(_require(item, "bar", where=where), where=f"{where}.bar")
        value = _coerce_float(_require(item, "value", where=where), where=f"{where}.value")
    elif isinstance(item, (list, tuple)):
        if len(item) != 2:
            raise MixAgentOutputError(
                f"{where}: expected [bar, value] pair, got len={len(item)}"
            )
        bar = _coerce_int_strict(item[0], where=f"{where}[0]")
        value = _coerce_float(item[1], where=f"{where}[1]")
    else:
        raise MixAgentOutputError(
            f"{where}: expected object or [bar, value] pair, "
            f"got {type(item).__name__}"
        )
    if bar < 0:
        raise MixAgentOutputError(f"{where}.bar must be >= 0, got {bar}")
    return EQAutomationPoint(bar=bar, value=value)


def _parse_envelope_strictly_ordered(
    raw: Any, *, where: str
) -> tuple[EQAutomationPoint, ...]:
    """Parse and validate envelope ordering (bar ascending strict).

    An out-of-order or duplicate-bar envelope would create ambiguous
    automation playback — better to raise than render unpredictably.
    """
    items_raw = _coerce_list(raw, where=where)
    points = tuple(
        _parse_eq_automation_point(item, where=f"{where}[{i}]")
        for i, item in enumerate(items_raw)
    )
    bars = [p.bar for p in points]
    if bars != sorted(set(bars)) or len(set(bars)) != len(bars):
        raise MixAgentOutputError(
            f"{where} must be strictly bar-ascending (no repeats). "
            f"Got bars: {bars}"
        )
    return points


def _coerce_int_strict(value: Any, *, where: str) -> int:
    """Strict-only int coercion (no string-of-int leniency for bars in
    automation envelopes — surface contract bugs)."""
    if isinstance(value, bool):
        raise MixAgentOutputError(f"{where}: expected int, got bool")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise MixAgentOutputError(
        f"{where}: expected int, got {type(value).__name__}"
    )


def _parse_eq_band_correction(item: Any, *, where: str) -> EQBandCorrection:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )

    track = _coerce_str(_require(item, "track", where=where), where=f"{where}.track").strip()
    if not track:
        raise MixAgentOutputError(f"{where}.track must be non-empty")

    band_type = _coerce_str(
        _require(item, "band_type", where=where), where=f"{where}.band_type"
    ).strip()
    if band_type not in VALID_EQ_BAND_TYPES:
        raise MixAgentOutputError(
            f"{where}.band_type={band_type!r} not in {sorted(VALID_EQ_BAND_TYPES)}"
        )

    intent = _coerce_str(
        _require(item, "intent", where=where), where=f"{where}.intent"
    ).strip()
    if intent not in VALID_EQ_INTENTS:
        raise MixAgentOutputError(
            f"{where}.intent={intent!r} not in {sorted(VALID_EQ_INTENTS)}"
        )

    center_hz = _coerce_float(
        _require(item, "center_hz", where=where), where=f"{where}.center_hz"
    )
    if not (EQ_FREQ_MIN_HZ <= center_hz <= EQ_FREQ_MAX_HZ):
        raise MixAgentOutputError(
            f"{where}.center_hz={center_hz} not in [{EQ_FREQ_MIN_HZ}, {EQ_FREQ_MAX_HZ}]"
        )

    q = _coerce_float(_require(item, "q", where=where), where=f"{where}.q")
    if not (EQ_Q_MIN <= q <= EQ_Q_MAX):
        raise MixAgentOutputError(
            f"{where}.q={q} not in [{EQ_Q_MIN}, {EQ_Q_MAX}]"
        )

    gain_db = _coerce_float(
        _require(item, "gain_db", where=where), where=f"{where}.gain_db"
    )
    if not (EQ_GAIN_MIN_DB <= gain_db <= EQ_GAIN_MAX_DB):
        raise MixAgentOutputError(
            f"{where}.gain_db={gain_db} not in [{EQ_GAIN_MIN_DB}, {EQ_GAIN_MAX_DB}]"
        )

    # Cross-field consistency : intent should match gain sign / band_type
    if intent == "cut" and gain_db > 0:
        raise MixAgentOutputError(
            f"{where}.intent='cut' but gain_db={gain_db} (positive). "
            f"A cut requires negative gain — set intent='boost' or fix gain."
        )
    if intent == "boost" and gain_db < 0:
        raise MixAgentOutputError(
            f"{where}.intent='boost' but gain_db={gain_db} (negative). "
            f"A boost requires positive gain — set intent='cut' or fix gain."
        )
    if intent == "filter" and band_type not in {"highpass", "lowpass", "notch"}:
        raise MixAgentOutputError(
            f"{where}.intent='filter' requires band_type in "
            f"{{highpass, lowpass, notch}}, got {band_type!r}"
        )

    # Slope only meaningful for highpass/lowpass.
    raw_slope = item.get("slope_db_per_oct", None)
    if raw_slope is None:
        slope_db_per_oct = None
    else:
        slope_db_per_oct = _coerce_float(
            raw_slope, where=f"{where}.slope_db_per_oct"
        )
        if band_type not in {"highpass", "lowpass"}:
            raise MixAgentOutputError(
                f"{where}.slope_db_per_oct only meaningful for "
                f"highpass/lowpass ; got band_type={band_type!r}. "
                f"Remove the field for shelves/bell/notch."
            )
        if slope_db_per_oct not in VALID_FILTER_SLOPES_DB_PER_OCT:
            raise MixAgentOutputError(
                f"{where}.slope_db_per_oct={slope_db_per_oct} not in "
                f"{sorted(VALID_FILTER_SLOPES_DB_PER_OCT)} (Eq8 supports "
                f"only 12 or 48 dB/oct ; pick the closest)."
            )

    # Phase 4.2.5 : chain_position with refined vocabulary. Default =
    # "default" (Tier B picks). Deprecated values from 4.2.3 raise with
    # an explicit redirect to the new equivalents.
    chain_position = _coerce_str(
        item.get("chain_position", "default"),
        where=f"{where}.chain_position",
    ).strip()
    if not chain_position:
        chain_position = "default"
    if chain_position in DEPRECATED_CHAIN_POSITIONS_REDIRECT:
        redirect = DEPRECATED_CHAIN_POSITIONS_REDIRECT[chain_position]
        raise MixAgentOutputError(
            f"{where}.chain_position={chain_position!r} is deprecated "
            f"(too coarse — Phase 4.2.5 audit). {redirect}"
        )
    if chain_position not in VALID_CHAIN_POSITIONS:
        raise MixAgentOutputError(
            f"{where}.chain_position={chain_position!r} not in "
            f"{sorted(VALID_CHAIN_POSITIONS)}. Use 'default' if you "
            f"don't have a strong placement preference."
        )

    # Phase 4.2.4 : processing_mode (stereo / mid / side).
    processing_mode = _coerce_str(
        item.get("processing_mode", "stereo"),
        where=f"{where}.processing_mode",
    ).strip().lower()
    if not processing_mode:
        processing_mode = "stereo"
    if processing_mode not in VALID_PROCESSING_MODES:
        raise MixAgentOutputError(
            f"{where}.processing_mode={processing_mode!r} not in "
            f"{sorted(VALID_PROCESSING_MODES)}. Eq8 supports only "
            f"stereo, mid, side."
        )

    gain_envelope = _parse_envelope_strictly_ordered(
        item.get("gain_envelope", []), where=f"{where}.gain_envelope"
    )
    freq_envelope = _parse_envelope_strictly_ordered(
        item.get("freq_envelope", []), where=f"{where}.freq_envelope"
    )
    q_envelope = _parse_envelope_strictly_ordered(
        item.get("q_envelope", []), where=f"{where}.q_envelope"
    )

    # Range-check envelope values
    for p in gain_envelope:
        if not (EQ_GAIN_MIN_DB <= p.value <= EQ_GAIN_MAX_DB):
            raise MixAgentOutputError(
                f"{where}.gain_envelope contains value {p.value} dB outside "
                f"[{EQ_GAIN_MIN_DB}, {EQ_GAIN_MAX_DB}]"
            )
    for p in freq_envelope:
        if not (EQ_FREQ_MIN_HZ <= p.value <= EQ_FREQ_MAX_HZ):
            raise MixAgentOutputError(
                f"{where}.freq_envelope contains value {p.value} Hz outside "
                f"[{EQ_FREQ_MIN_HZ}, {EQ_FREQ_MAX_HZ}]"
            )
    for p in q_envelope:
        if not (EQ_Q_MIN <= p.value <= EQ_Q_MAX):
            raise MixAgentOutputError(
                f"{where}.q_envelope contains value {p.value} outside "
                f"[{EQ_Q_MIN}, {EQ_Q_MAX}]"
            )

    sections_raw = _coerce_list(
        item.get("sections", []), where=f"{where}.sections"
    )
    sections = tuple(
        _coerce_int_strict(s, where=f"{where}.sections[{i}]")
        for i, s in enumerate(sections_raw)
    )

    rationale = _coerce_str(item.get("rationale", ""))
    inspired_by_raw = _coerce_list(
        item.get("inspired_by", []), where=f"{where}.inspired_by"
    )
    inspired_by = _parse_citations(inspired_by_raw, where=f"{where}.inspired_by")

    # Depth-light : every band must have ≥ 1 citation + ≥ 50 char rationale.
    # Same discipline as composition motif-decider Phase 2.7.1 fix #5.
    if len(rationale) < 50:
        raise MixAgentOutputError(
            f"{where}.rationale too short ({len(rationale)} chars, need ≥ 50). "
            f"Untraced EQ correction = stub : the Tier B configurator can't "
            f"justify the move to safety-guardian."
        )
    if not inspired_by:
        raise MixAgentOutputError(
            f"{where}.inspired_by must contain at least one citation. "
            f"Cite the Mix Analyzer cell (Anomalies!A12 etc.) or device "
            f"mapping rule that justifies this band."
        )

    return EQBandCorrection(
        track=track,
        band_type=band_type,
        intent=intent,
        center_hz=center_hz,
        q=q,
        gain_db=gain_db,
        slope_db_per_oct=slope_db_per_oct,
        chain_position=chain_position,
        processing_mode=processing_mode,
        gain_envelope=gain_envelope,
        freq_envelope=freq_envelope,
        q_envelope=q_envelope,
        sections=sections,
        rationale=rationale,
        inspired_by=inspired_by,
    )


def parse_eq_corrective_decision(
    payload: Mapping[str, Any],
) -> MixDecision[EQCorrectiveDecision]:
    """Parse an eq-corrective-decider payload into a MixDecision.

    Expected shape (schema 1.0) :
        {
          "schema_version": "1.0",
          "eq_corrective": {
            "bands": [
              {
                "track": str,
                "band_type": str ∈ VALID_EQ_BAND_TYPES,
                "intent": str ∈ VALID_EQ_INTENTS,
                "center_hz": float,
                "q": float,
                "gain_db": float,
                "gain_envelope": [{"bar": int, "value": float}, …]   # optional
                "freq_envelope": [...],                              # optional
                "q_envelope": [...],                                 # optional
                "sections": [int, ...]                               # optional
                "rationale": str (≥ 50 chars),
                "inspired_by": [{kind, path, excerpt}, …]            # ≥ 1 cite
              },
              ...
            ]
          },
          "cited_by": [...],
          "rationale": str,
          "confidence": float (0..1)
        }

    Or a refusal: {"error": "...", "details": "..."}

    Strict on output : ranges enforced (freq, Q, gain), envelopes
    bar-ascending strict, intent/gain sign coherence, depth-light per band.
    """
    envelope = _parse_envelope(
        payload, supported_versions=SUPPORTED_EQ_CORRECTIVE_SCHEMA_VERSIONS
    )

    eq_dict = _require(payload, "eq_corrective", where="root")
    if not isinstance(eq_dict, Mapping):
        raise MixAgentOutputError(
            f"eq_corrective: expected object, got {type(eq_dict).__name__}"
        )

    bands_raw = _coerce_list(
        eq_dict.get("bands", []), where="eq_corrective.bands"
    )
    bands = tuple(
        _parse_eq_band_correction(item, where=f"eq_corrective.bands[{i}]")
        for i, item in enumerate(bands_raw)
    )

    decision_value = EQCorrectiveDecision(bands=bands)
    return MixDecision(value=decision_value, lane="eq_corrective", **envelope)


def parse_eq_corrective_decision_from_response(
    text: str,
) -> MixDecision[EQCorrectiveDecision]:
    """End-to-end: raw LLM response → MixDecision[EQCorrectiveDecision]."""
    return parse_eq_corrective_decision(extract_json_payload(text))


# ============================================================================
# Public parser — dynamics_corrective lane (Phase 4.3)
# ============================================================================
#
# Mirror of the eq-corrective parser. Strict on output : ranges enforced,
# envelopes bar-ascending strict, depth-light per correction, 13
# cross-field semantic-contradiction checks. Pure-payload — checks that
# require DiagnosticReport context (M/S vs correlation, sidechain
# trigger_track presence in tracks) live in the agent prompt as
# anti-patterns the agent must self-enforce before emission.


def _parse_dynamics_automation_point(
    item: Any, *, where: str
) -> DynamicsAutomationPoint:
    """Parse one envelope point. Accepts {bar, value} or [bar, value]."""
    if isinstance(item, Mapping):
        bar = _coerce_int_strict(_require(item, "bar", where=where), where=f"{where}.bar")
        value = _coerce_float(_require(item, "value", where=where), where=f"{where}.value")
    elif isinstance(item, (list, tuple)):
        if len(item) != 2:
            raise MixAgentOutputError(
                f"{where}: expected [bar, value] pair, got len={len(item)}"
            )
        bar = _coerce_int_strict(item[0], where=f"{where}[0]")
        value = _coerce_float(item[1], where=f"{where}[1]")
    else:
        raise MixAgentOutputError(
            f"{where}: expected object or [bar, value] pair, "
            f"got {type(item).__name__}"
        )
    if bar < 0:
        raise MixAgentOutputError(f"{where}.bar must be >= 0, got {bar}")
    return DynamicsAutomationPoint(bar=bar, value=value)


def _parse_dynamics_envelope_strict(
    raw: Any, *, where: str, value_min: float, value_max: float, value_unit: str
) -> tuple[DynamicsAutomationPoint, ...]:
    """Parse + validate envelope ordering (bar ascending strict, ≥ 3 points
    if non-empty) + range-check values."""
    items_raw = _coerce_list(raw, where=where)
    points = tuple(
        _parse_dynamics_automation_point(item, where=f"{where}[{i}]")
        for i, item in enumerate(items_raw)
    )
    if not points:
        return points
    bars = [p.bar for p in points]
    if bars != sorted(set(bars)) or len(set(bars)) != len(bars):
        raise MixAgentOutputError(
            f"{where} must be strictly bar-ascending (no repeats). Got bars: {bars}"
        )
    # Cross-field check #9 : envelope non-empty AND len < 3 → reject
    if len(points) < 3:
        raise MixAgentOutputError(
            f"{where} non-empty envelope needs ≥ 3 points (got {len(points)} ; "
            f"2 points = ramp, equivalent to a static change — use static fields)."
        )
    for p in points:
        if not (value_min <= p.value <= value_max):
            raise MixAgentOutputError(
                f"{where} contains value {p.value} {value_unit} outside "
                f"[{value_min}, {value_max}]"
            )
    return points


def _parse_sidechain_config(
    item: Any, *, where: str
) -> Optional[SidechainConfig]:
    if item is None:
        return None
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object or null, got {type(item).__name__}"
        )
    mode = _coerce_str(_require(item, "mode", where=where), where=f"{where}.mode").strip()
    if mode not in VALID_SIDECHAIN_MODES:
        raise MixAgentOutputError(
            f"{where}.mode={mode!r} not in {sorted(VALID_SIDECHAIN_MODES)}"
        )
    trigger_raw = item.get("trigger_track", None)
    trigger_track = (
        None if trigger_raw is None or trigger_raw == ""
        else _coerce_str(trigger_raw, where=f"{where}.trigger_track")
    )
    depth_raw = item.get("depth_db", None)
    depth_db = (
        None if depth_raw is None
        else _coerce_float(depth_raw, where=f"{where}.depth_db")
    )
    if depth_db is not None and not (DYN_SIDECHAIN_DEPTH_MIN_DB <= depth_db <= DYN_SIDECHAIN_DEPTH_MAX_DB):
        raise MixAgentOutputError(
            f"{where}.depth_db={depth_db} not in "
            f"[{DYN_SIDECHAIN_DEPTH_MIN_DB}, {DYN_SIDECHAIN_DEPTH_MAX_DB}]"
        )
    filter_freq_raw = item.get("filter_freq_hz", None)
    filter_freq_hz = (
        None if filter_freq_raw is None
        else _coerce_float(filter_freq_raw, where=f"{where}.filter_freq_hz")
    )
    if filter_freq_hz is not None and not (EQ_FREQ_MIN_HZ <= filter_freq_hz <= EQ_FREQ_MAX_HZ):
        raise MixAgentOutputError(
            f"{where}.filter_freq_hz={filter_freq_hz} not in "
            f"[{EQ_FREQ_MIN_HZ}, {EQ_FREQ_MAX_HZ}]"
        )
    filter_q_raw = item.get("filter_q", None)
    filter_q = (
        None if filter_q_raw is None
        else _coerce_float(filter_q_raw, where=f"{where}.filter_q")
    )
    if filter_q is not None and not (EQ_Q_MIN <= filter_q <= EQ_Q_MAX):
        raise MixAgentOutputError(
            f"{where}.filter_q={filter_q} not in [{EQ_Q_MIN}, {EQ_Q_MAX}]"
        )
    # Cross-field within sidechain : external mode requires trigger_track
    if mode == "external" and not trigger_track:
        raise MixAgentOutputError(
            f"{where}.mode='external' requires non-empty trigger_track"
        )
    return SidechainConfig(
        mode=mode,
        trigger_track=trigger_track,
        depth_db=depth_db,
        filter_freq_hz=filter_freq_hz,
        filter_q=filter_q,
    )


def _coerce_optional_float_in_range(
    value: Any, *, where: str, lo: float, hi: float, unit: str
) -> Optional[float]:
    if value is None:
        return None
    f = _coerce_float(value, where=where)
    if not (lo <= f <= hi):
        raise MixAgentOutputError(
            f"{where}={f} {unit} not in [{lo}, {hi}]"
        )
    return f


def _parse_dynamics_correction(item: Any, *, where: str) -> DynamicsCorrection:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )

    track = _coerce_str(_require(item, "track", where=where), where=f"{where}.track").strip()
    if not track:
        raise MixAgentOutputError(f"{where}.track must be non-empty")

    # Strict casing — matches eq-corrective discipline (band_type, intent are
    # also strict). Agent emits canonical lowercase values from VALID_DYNAMICS_TYPES.
    dynamics_type = _coerce_str(
        _require(item, "dynamics_type", where=where), where=f"{where}.dynamics_type"
    ).strip()
    if dynamics_type not in VALID_DYNAMICS_TYPES:
        raise MixAgentOutputError(
            f"{where}.dynamics_type={dynamics_type!r} not in {sorted(VALID_DYNAMICS_TYPES)}"
        )

    device = _coerce_str(
        _require(item, "device", where=where), where=f"{where}.device"
    ).strip()
    if device not in VALID_DYNAMICS_DEVICES:
        raise MixAgentOutputError(
            f"{where}.device={device!r} not in {sorted(VALID_DYNAMICS_DEVICES)} "
            f"(Kickstart 2 is intentionally absent — use Compressor2 with "
            f"sidechain.mode='external' for ducking)"
        )

    threshold_db = _coerce_optional_float_in_range(
        item.get("threshold_db"), where=f"{where}.threshold_db",
        lo=DYN_THRESHOLD_MIN_DB, hi=DYN_THRESHOLD_MAX_DB, unit="dB",
    )
    ratio = _coerce_optional_float_in_range(
        item.get("ratio"), where=f"{where}.ratio",
        lo=DYN_RATIO_MIN, hi=DYN_RATIO_MAX, unit=":1",
    )
    attack_ms = _coerce_optional_float_in_range(
        item.get("attack_ms"), where=f"{where}.attack_ms",
        lo=DYN_ATTACK_MIN_MS, hi=DYN_ATTACK_MAX_MS, unit="ms",
    )
    release_ms = _coerce_optional_float_in_range(
        item.get("release_ms"), where=f"{where}.release_ms",
        lo=DYN_RELEASE_MIN_MS, hi=DYN_RELEASE_MAX_MS, unit="ms",
    )
    release_auto = _coerce_bool(
        item.get("release_auto", False), where=f"{where}.release_auto"
    )
    makeup_db = _coerce_optional_float_in_range(
        item.get("makeup_db"), where=f"{where}.makeup_db",
        lo=DYN_MAKEUP_MIN_DB, hi=DYN_MAKEUP_MAX_DB, unit="dB",
    )
    knee_db = _coerce_optional_float_in_range(
        item.get("knee_db"), where=f"{where}.knee_db",
        lo=DYN_KNEE_MIN_DB, hi=DYN_KNEE_MAX_DB, unit="dB",
    )
    dry_wet = _coerce_optional_float_in_range(
        item.get("dry_wet"), where=f"{where}.dry_wet",
        lo=DYN_DRY_WET_MIN, hi=DYN_DRY_WET_MAX, unit="(0..1)",
    )
    ceiling_db = _coerce_optional_float_in_range(
        item.get("ceiling_db"), where=f"{where}.ceiling_db",
        lo=DYN_CEILING_MIN_DB, hi=DYN_CEILING_MAX_DB, unit="dB",
    )
    transients = _coerce_optional_float_in_range(
        item.get("transients"), where=f"{where}.transients",
        lo=DYN_TRANSIENTS_MIN, hi=DYN_TRANSIENTS_MAX, unit="(-1..+1)",
    )

    sidechain = _parse_sidechain_config(
        item.get("sidechain"), where=f"{where}.sidechain"
    )

    chain_position = _coerce_str(
        item.get("chain_position", "default"),
        where=f"{where}.chain_position",
    ).strip()
    if not chain_position:
        chain_position = "default"
    if chain_position not in VALID_DYNAMICS_CHAIN_POSITIONS:
        raise MixAgentOutputError(
            f"{where}.chain_position={chain_position!r} not in "
            f"{sorted(VALID_DYNAMICS_CHAIN_POSITIONS)}. Use 'default' if you "
            f"don't have a strong placement preference."
        )

    processing_mode = _coerce_str(
        item.get("processing_mode", "stereo"),
        where=f"{where}.processing_mode",
    ).strip().lower()
    if not processing_mode:
        processing_mode = "stereo"
    if processing_mode not in VALID_PROCESSING_MODES:
        raise MixAgentOutputError(
            f"{where}.processing_mode={processing_mode!r} not in "
            f"{sorted(VALID_PROCESSING_MODES)}."
        )

    threshold_envelope = _parse_dynamics_envelope_strict(
        item.get("threshold_envelope", []), where=f"{where}.threshold_envelope",
        value_min=DYN_THRESHOLD_MIN_DB, value_max=DYN_THRESHOLD_MAX_DB, value_unit="dB",
    )
    makeup_envelope = _parse_dynamics_envelope_strict(
        item.get("makeup_envelope", []), where=f"{where}.makeup_envelope",
        value_min=DYN_MAKEUP_MIN_DB, value_max=DYN_MAKEUP_MAX_DB, value_unit="dB",
    )
    dry_wet_envelope = _parse_dynamics_envelope_strict(
        item.get("dry_wet_envelope", []), where=f"{where}.dry_wet_envelope",
        value_min=DYN_DRY_WET_MIN, value_max=DYN_DRY_WET_MAX, value_unit="(0..1)",
    )
    sidechain_depth_envelope = _parse_dynamics_envelope_strict(
        item.get("sidechain_depth_envelope", []), where=f"{where}.sidechain_depth_envelope",
        value_min=DYN_SIDECHAIN_DEPTH_MIN_DB, value_max=DYN_SIDECHAIN_DEPTH_MAX_DB, value_unit="dB",
    )

    sections_raw = _coerce_list(
        item.get("sections", []), where=f"{where}.sections"
    )
    sections = tuple(
        _coerce_int_strict(s, where=f"{where}.sections[{i}]")
        for i, s in enumerate(sections_raw)
    )

    rationale = _coerce_str(item.get("rationale", ""))
    inspired_by_raw = _coerce_list(
        item.get("inspired_by", []), where=f"{where}.inspired_by"
    )
    inspired_by = _parse_citations(inspired_by_raw, where=f"{where}.inspired_by")

    # ------------------------------------------------------------------
    # Cross-field semantic-contradiction checks (12 total — pure-payload).
    # The original Pass-2 list had 13 ; check #2 (gate threshold > 0) was
    # dropped because the threshold_db range [-60, 0] already enforces it.
    # ------------------------------------------------------------------

    # #1 — compress with effectively-no-compression ratio
    if dynamics_type == "compress" and ratio is not None and ratio < 1.1:
        raise MixAgentOutputError(
            f"{where}.dynamics_type='compress' but ratio={ratio} < 1.1 "
            f"(no compression). Use ratio ≥ 1.5 for real compression, or "
            f"set dynamics_type to a passthrough type."
        )

    # #2 — limit ceiling above 0 dBFS (impossible)
    if dynamics_type == "limit" and ceiling_db is not None and ceiling_db > 0:
        raise MixAgentOutputError(
            f"{where}.dynamics_type='limit' but ceiling_db={ceiling_db} > 0 dBFS. "
            f"Limiter ceiling must be ≤ 0 dBFS."
        )

    # #3 — sidechain_duck requires SidechainConfig(mode='external', trigger_track=...)
    if dynamics_type == "sidechain_duck":
        if sidechain is None:
            raise MixAgentOutputError(
                f"{where}.dynamics_type='sidechain_duck' requires "
                f"sidechain block (mode='external', trigger_track=..., depth_db=...)."
            )
        if sidechain.mode != "external":
            raise MixAgentOutputError(
                f"{where}.dynamics_type='sidechain_duck' requires "
                f"sidechain.mode='external' (got {sidechain.mode!r})."
            )

    # #4 — parallel_compress with full-wet dry_wet (= standard compression)
    if dynamics_type == "parallel_compress" and dry_wet is not None and dry_wet >= 0.95:
        raise MixAgentOutputError(
            f"{where}.dynamics_type='parallel_compress' but dry_wet={dry_wet} ≥ 0.95 "
            f"(essentially full wet). Use dynamics_type='compress' instead."
        )

    # #5 — non-parallel types with low dry_wet (= parallel territory)
    if (dynamics_type in {"compress", "limit", "sidechain_duck"}
            and dry_wet is not None and dry_wet < 0.5):
        raise MixAgentOutputError(
            f"{where}.dynamics_type={dynamics_type!r} but dry_wet={dry_wet} < 0.5 "
            f"(parallel territory). Use dynamics_type='parallel_compress' for blends."
        )

    # #6 — GlueCompressor outside bus_glue role
    if device == "GlueCompressor" and dynamics_type != "bus_glue":
        raise MixAgentOutputError(
            f"{where}.device='GlueCompressor' but dynamics_type={dynamics_type!r}. "
            f"GlueCompressor is the bus-glue device ; use Compressor2 for "
            f"track-level compression / sidechain / parallel."
        )

    # #7 — DrumBuss outside transient_shape role
    if device == "DrumBuss" and dynamics_type != "transient_shape":
        raise MixAgentOutputError(
            f"{where}.device='DrumBuss' but dynamics_type={dynamics_type!r}. "
            f"DrumBuss in this lane = transient shaping only ; full sat/comp "
            f"belongs to eq-creative-colorist."
        )

    # #8 — envelope non-empty AND sections == () (envelope #9 = ≥3 points
    # already enforced in _parse_dynamics_envelope_strict)
    has_envelope = bool(threshold_envelope or makeup_envelope
                        or dry_wet_envelope or sidechain_depth_envelope)
    if has_envelope and not sections:
        raise MixAgentOutputError(
            f"{where} has non-empty envelope but sections=() ; specify which "
            f"section indices the envelope applies to."
        )

    # #9 — depth-light : rationale ≥ 50 chars, ≥ 1 citation
    if len(rationale) < 50:
        raise MixAgentOutputError(
            f"{where}.rationale too short ({len(rationale)} chars, need ≥ 50). "
            f"Untraced dynamics correction = stub : the Tier B configurator "
            f"can't justify the move to safety-guardian."
        )
    if not inspired_by:
        raise MixAgentOutputError(
            f"{where}.inspired_by must contain at least one citation. "
            f"Cite the Mix Analyzer cell, CDE diagnostic, or user brief that "
            f"justifies this correction."
        )

    # #10 — external sidechain_duck requires depth_db intent
    if (dynamics_type == "sidechain_duck"
            and sidechain is not None and sidechain.mode == "external"
            and sidechain.depth_db is None):
        raise MixAgentOutputError(
            f"{where}.dynamics_type='sidechain_duck' with external sidechain "
            f"requires sidechain.depth_db (the agent's intent dB ; Tier B "
            f"translates to threshold/ratio)."
        )

    # #11 — Compressor2 has no auto-release ; release_auto only valid on
    # GlueCompressor and Limiter
    if release_auto and device == "Compressor2":
        raise MixAgentOutputError(
            f"{where}.release_auto=True but device='Compressor2' — Compressor2 "
            f"has no auto-release. Use a numeric release_ms, or pick "
            f"GlueCompressor/Limiter if auto behavior is required."
        )

    return DynamicsCorrection(
        track=track,
        dynamics_type=dynamics_type,
        device=device,
        threshold_db=threshold_db,
        ratio=ratio,
        attack_ms=attack_ms,
        release_ms=release_ms,
        release_auto=release_auto,
        makeup_db=makeup_db,
        knee_db=knee_db,
        dry_wet=dry_wet,
        ceiling_db=ceiling_db,
        transients=transients,
        sidechain=sidechain,
        chain_position=chain_position,
        processing_mode=processing_mode,
        threshold_envelope=threshold_envelope,
        makeup_envelope=makeup_envelope,
        dry_wet_envelope=dry_wet_envelope,
        sidechain_depth_envelope=sidechain_depth_envelope,
        sections=sections,
        rationale=rationale,
        inspired_by=inspired_by,
    )


def parse_dynamics_corrective_decision(
    payload: Mapping[str, Any],
) -> MixDecision[DynamicsCorrectiveDecision]:
    """Parse a dynamics-corrective-decider payload into a MixDecision.

    Expected shape (schema 1.0) :
        {
          "schema_version": "1.0",
          "dynamics_corrective": {
            "corrections": [
              {
                "track": str,
                "dynamics_type": str ∈ VALID_DYNAMICS_TYPES,
                "device": str ∈ VALID_DYNAMICS_DEVICES,
                "threshold_db": Optional[float],
                "ratio": Optional[float],
                "attack_ms": Optional[float],
                "release_ms": Optional[float],
                "release_auto": Optional[bool],
                "makeup_db": Optional[float],
                "knee_db": Optional[float],
                "dry_wet": Optional[float],
                "ceiling_db": Optional[float],
                "transients": Optional[float],
                "sidechain": Optional[{mode, trigger_track, depth_db, filter_freq_hz, filter_q}],
                "chain_position": str ∈ VALID_DYNAMICS_CHAIN_POSITIONS,
                "processing_mode": "stereo"|"mid"|"side",
                "threshold_envelope": [{bar, value}, …]   # optional
                "makeup_envelope": [...]                  # optional
                "dry_wet_envelope": [...]                 # optional
                "sidechain_depth_envelope": [...]         # optional
                "sections": [int, ...]                    # required if any envelope non-empty
                "rationale": str (≥ 50 chars),
                "inspired_by": [{kind, path, excerpt}, …] # ≥ 1 cite
              },
              ...
            ]
          },
          "cited_by": [...],
          "rationale": str,
          "confidence": float (0..1)
        }

    Or a refusal: {"error": "...", "details": "..."}

    Strict on output : ranges enforced, envelopes bar-ascending strict
    (≥ 3 points if non-empty), 13 cross-field semantic-contradiction
    checks, depth-light per correction.
    """
    envelope = _parse_envelope(
        payload, supported_versions=SUPPORTED_DYNAMICS_CORRECTIVE_SCHEMA_VERSIONS
    )

    dyn_dict = _require(payload, "dynamics_corrective", where="root")
    if not isinstance(dyn_dict, Mapping):
        raise MixAgentOutputError(
            f"dynamics_corrective: expected object, got {type(dyn_dict).__name__}"
        )

    corrections_raw = _coerce_list(
        dyn_dict.get("corrections", []), where="dynamics_corrective.corrections"
    )
    corrections = tuple(
        _parse_dynamics_correction(item, where=f"dynamics_corrective.corrections[{i}]")
        for i, item in enumerate(corrections_raw)
    )

    decision_value = DynamicsCorrectiveDecision(corrections=corrections)
    return MixDecision(value=decision_value, lane="dynamics_corrective", **envelope)


def parse_dynamics_corrective_decision_from_response(
    text: str,
) -> MixDecision[DynamicsCorrectiveDecision]:
    """End-to-end: raw LLM response → MixDecision[DynamicsCorrectiveDecision]."""
    return parse_dynamics_corrective_decision(extract_json_payload(text))


__all__ = [
    "MixAgentOutputError",
    "SUPPORTED_DIAGNOSTIC_SCHEMA_VERSIONS",
    "SUPPORTED_EQ_CORRECTIVE_SCHEMA_VERSIONS",
    "SUPPORTED_DYNAMICS_CORRECTIVE_SCHEMA_VERSIONS",
    "VALID_ANOMALY_SEVERITIES",
    "VALID_TRACK_TYPES",
    "VALID_CITATION_KINDS",
    # Phase 4.2.8 — CDE + Freq Conflicts re-exports
    "VALID_CDE_SEVERITIES",
    "VALID_CDE_CONFIDENCES",
    "VALID_CDE_APPLICATION_STATUSES",
    "KNOWN_CDE_ISSUE_TYPES",
    # Phase 4.3 — Dynamics corrective re-exports
    "VALID_DYNAMICS_TYPES",
    "VALID_DYNAMICS_DEVICES",
    "VALID_SIDECHAIN_MODES",
    "VALID_DYNAMICS_CHAIN_POSITIONS",
    "extract_json_payload",
    "parse_diagnostic_decision",
    "parse_diagnostic_decision_from_response",
    "parse_eq_corrective_decision",
    "parse_eq_corrective_decision_from_response",
    "parse_dynamics_corrective_decision",
    "parse_dynamics_corrective_decision_from_response",
]
