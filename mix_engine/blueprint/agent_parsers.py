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
from typing import Any, Mapping

from mix_engine.blueprint.schema import (
    Anomaly,
    DiagnosticReport,
    EQAutomationPoint,
    EQBandCorrection,
    EQCorrectiveDecision,
    EQ_FREQ_MAX_HZ,
    EQ_FREQ_MIN_HZ,
    EQ_GAIN_MAX_DB,
    EQ_GAIN_MIN_DB,
    EQ_Q_MAX,
    EQ_Q_MIN,
    FullMixMetrics,
    HealthScore,
    MixCitation,
    MixDecision,
    TrackInfo,
    VALID_EQ_BAND_TYPES,
    VALID_EQ_INTENTS,
    VALID_FILTER_SLOPES_DB_PER_OCT,
)


SUPPORTED_DIAGNOSTIC_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTED_EQ_CORRECTIVE_SCHEMA_VERSIONS = frozenset({"1.0"})

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

    report = DiagnosticReport(
        project_name=project_name,
        full_mix=full_mix,
        tracks=tracks,
        anomalies=anomalies,
        health_score=health_score,
        routing_warnings=routing_warnings,
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


__all__ = [
    "MixAgentOutputError",
    "SUPPORTED_DIAGNOSTIC_SCHEMA_VERSIONS",
    "SUPPORTED_EQ_CORRECTIVE_SCHEMA_VERSIONS",
    "VALID_ANOMALY_SEVERITIES",
    "VALID_TRACK_TYPES",
    "VALID_CITATION_KINDS",
    "extract_json_payload",
    "parse_diagnostic_decision",
    "parse_diagnostic_decision_from_response",
    "parse_eq_corrective_decision",
    "parse_eq_corrective_decision_from_response",
]
