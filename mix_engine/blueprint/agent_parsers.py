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
import math
import re
from typing import Any, Mapping, Optional

from mix_engine.blueprint.schema import (
    Anomaly,
    BandConflict,
    CANONICAL_BAND_COUNT,
    CANONICAL_BAND_LABELS,
    CDECorrectionRecipe,
    CDEDiagnostic,
    CDEMeasurement,
    CDETFPContext,
    CENTROID_HZ_MAX,
    CENTROID_HZ_MIN,
    CREST_FACTOR_MAX,
    CREST_FACTOR_MIN,
    DiagnosticReport,
    GenreContext,
    LOUDNESS_DB_MAX,
    LOUDNESS_DB_MIN,
    LRA_MAX,
    LRA_MIN,
    LUFS_MAX,
    LUFS_MIN,
    ONSETS_PER_SECOND_MAX,
    ONSETS_PER_SECOND_MIN,
    PLR_PSR_MAX,
    PLR_PSR_MIN,
    SPECTRAL_FLATNESS_MAX,
    SPECTRAL_FLATNESS_MIN,
    SPECTRAL_PEAKS_MAX,
    SpectralPeak,
    TARGET_LUFS_MIX_MAX,
    TARGET_LUFS_MIX_MIN,
    TONAL_STRENGTH_MAX,
    TONAL_STRENGTH_MIN,
    TYPICAL_CREST_MIX_MAX,
    TYPICAL_CREST_MIX_MIN,
    TrackAudioMetrics,
    VALID_DENSITY_TOLERANCES,
    VALID_GENRE_FAMILIES,
    DynamicsAutomationPoint,
    DynamicsCorrection,
    DynamicsCorrectiveDecision,
    RoutingDecision,
    SidechainRepair,
    SpatialDecision,
    SpatialMove,
    ChainBuildDecision,
    ChainSlot,
    TrackChainPlan,
    CHAIN_MAX_POSITION,
    EQ8_MAX_BANDS_PER_INSTANCE,
    AUTOMATION_MAX_TIME_BEATS,
    AUTOMATION_MAX_POINTS,
    AUTOMATION_MIN_POINTS,
    AutomationDecision,
    AutomationEnvelope,
    AutomationPoint,
    MASTER_TRACK_NAME,
    STALE_SIDECHAIN_REGEX,
    PAN_MIN,
    PAN_MAX,
    STEREO_WIDTH_MIN,
    STEREO_WIDTH_NEUTRAL,
    STEREO_WIDTH_MAX,
    BALANCE_MIN,
    BALANCE_NEUTRAL,
    BALANCE_MAX,
    MS_BALANCE_MIN,
    MS_BALANCE_NEUTRAL,
    MS_BALANCE_MAX,
    BASS_MONO_FREQ_MIN_HZ,
    BASS_MONO_FREQ_MAX_HZ,
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
    VALID_AUTOMATION_PURPOSES,
    VALID_AUTOMATION_TARGET_DEVICES,
    VALID_CHAIN_DEVICES,
    VALID_CONSUMES_LANES,
    VALID_FILTER_SLOPES_DB_PER_OCT,
    VALID_PHASE_CHANNELS,
    VALID_PROCESSING_MODES,
    VALID_ROUTING_FIX_TYPES,
    VALID_SIDECHAIN_MODES,
    VALID_SPATIAL_CHAIN_POSITIONS,
    VALID_SPATIAL_MOVE_TYPES,
    # Phase 4.9 — Mastering lane
    MASTER_BASS_MONO_FREQ_MAX_HZ,
    MASTER_BASS_MONO_FREQ_MIN_HZ,
    MASTER_CEILING_MAX_DBTP,
    MASTER_CEILING_MIN_DBTP,
    MASTER_CHAIN_POSITION_BY_TYPE,
    MASTER_DEVICES_BY_TYPE,
    MASTER_EQ_GAIN_MAX_DB,
    MASTER_EQ_GAIN_MIN_DB,
    MASTER_GLUE_GR_TARGET_MAX_DB,
    MASTER_GLUE_GR_TARGET_MIN_DB,
    MASTER_GLUE_RATIO_MAX,
    MASTER_GLUE_RATIO_MIN,
    MASTER_LUFS_MAX,
    MASTER_LUFS_MIN,
    MASTER_SATURATION_DRIVE_MAX_PCT,
    MASTER_SATURATION_DRIVE_MIN_PCT,
    MASTER_STEREO_WIDTH_MAX,
    MASTER_STEREO_WIDTH_MIN,
    MasterMove,
    MasteringDecision,
    VALID_MASTER_CHAIN_POSITIONS,
    VALID_MASTER_MOVE_TYPES,
    VALID_SATURATION_TYPES,
)


SUPPORTED_DIAGNOSTIC_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTED_EQ_CORRECTIVE_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTED_DYNAMICS_CORRECTIVE_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTED_ROUTING_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTED_SPATIAL_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTED_CHAIN_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTED_AUTOMATION_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTED_MASTERING_SCHEMA_VERSIONS = frozenset({"1.0"})

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


# ============================================================================
# Phase 4.7 — Per-track audio metrics + genre context sub-parsers
# ============================================================================
#
# Cross-field checks (parser-enforced) :
# 1. NaN rejection — mix-diagnostician must normalize NaN → null upstream
# 2. is_stereo coherence — mono = stereo fields None ; stereo = correlation
#    + width_overall mandatory
# 3. band_energies len == CANONICAL_BAND_COUNT (7)
# 4. width_per_band len == CANONICAL_BAND_COUNT (7) when set
# 5. spectral_peaks len ≤ SPECTRAL_PEAKS_MAX (10) ; magnitude descending
# 6. dominant_band ∈ CANONICAL_BAND_LABELS (7 values)


def _check_not_nan(value: Any, *, where: str) -> None:
    """Phase 4.7 Cross-field #1 — NaN rejection.

    mix-diagnostician must normalize NaN → null upstream. NaN floats
    indicate a measurement edge case (silent track, mono-summed-stereo)
    that should be treated as "not measured" rather than "value 0".
    """
    # Cross-field #1 — NaN rejection (audit Pass 3 Finding 5 : tagged for
    # coherence with #2-#7 numbering visible in inline comments).
    if isinstance(value, float) and math.isnan(value):
        raise MixAgentOutputError(
            f"{where} is NaN — mix-diagnostician must normalize NaN values "
            f"to null before emit (NaN indicates a measurement edge case "
            f"like silent track or mono-summed-stereo)."
        )


def _coerce_float_nonan_in_range(
    value: Any, *, where: str, lo: float, hi: float, unit: str = ""
) -> float:
    """Strict float coercion with NaN rejection + range check."""
    f = _coerce_float(value, where=where)
    _check_not_nan(f, where=where)
    if not (lo <= f <= hi):
        raise MixAgentOutputError(
            f"{where}={f}{(' ' + unit) if unit else ''} not in [{lo}, {hi}]"
        )
    return f


def _parse_spectral_peak(item: Any, *, where: str) -> SpectralPeak:
    if not isinstance(item, Mapping):
        # Allow [freq, db] tuple form for lenient input
        if isinstance(item, (list, tuple)) and len(item) == 2:
            freq = _coerce_float_nonan_in_range(
                item[0], where=f"{where}[0]", lo=16.0, hi=22050.0, unit="Hz",
            )
            mag = _coerce_float_nonan_in_range(
                item[1], where=f"{where}[1]", lo=-150.0, hi=0.0, unit="dB",
            )
            return SpectralPeak(frequency_hz=freq, magnitude_db=mag)
        raise MixAgentOutputError(
            f"{where}: expected object or [freq_hz, magnitude_db] pair, "
            f"got {type(item).__name__}"
        )
    freq = _coerce_float_nonan_in_range(
        _require(item, "frequency_hz", where=where),
        where=f"{where}.frequency_hz", lo=16.0, hi=22050.0, unit="Hz",
    )
    mag = _coerce_float_nonan_in_range(
        _require(item, "magnitude_db", where=where),
        where=f"{where}.magnitude_db", lo=-150.0, hi=0.0, unit="dB",
    )
    return SpectralPeak(frequency_hz=freq, magnitude_db=mag)


def _parse_track_audio_metrics(item: Any, *, where: str) -> TrackAudioMetrics:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )

    # === Loudness scalars (9 fields) ===
    peak_db = _coerce_float_nonan_in_range(
        _require(item, "peak_db", where=where), where=f"{where}.peak_db",
        lo=LOUDNESS_DB_MIN, hi=LOUDNESS_DB_MAX, unit="dB",
    )
    true_peak_db = _coerce_float_nonan_in_range(
        _require(item, "true_peak_db", where=where), where=f"{where}.true_peak_db",
        lo=LOUDNESS_DB_MIN, hi=LOUDNESS_DB_MAX, unit="dB",
    )
    rms_db = _coerce_float_nonan_in_range(
        _require(item, "rms_db", where=where), where=f"{where}.rms_db",
        lo=LOUDNESS_DB_MIN, hi=LOUDNESS_DB_MAX, unit="dB",
    )
    lufs_integrated = _coerce_float_nonan_in_range(
        _require(item, "lufs_integrated", where=where), where=f"{where}.lufs_integrated",
        lo=LUFS_MIN, hi=LUFS_MAX, unit="LUFS",
    )
    lufs_short_term_max = _coerce_float_nonan_in_range(
        _require(item, "lufs_short_term_max", where=where), where=f"{where}.lufs_short_term_max",
        lo=LUFS_MIN, hi=LUFS_MAX, unit="LUFS",
    )
    lra = _coerce_float_nonan_in_range(
        _require(item, "lra", where=where), where=f"{where}.lra",
        lo=LRA_MIN, hi=LRA_MAX, unit="LU",
    )
    crest_factor = _coerce_float_nonan_in_range(
        _require(item, "crest_factor", where=where), where=f"{where}.crest_factor",
        lo=CREST_FACTOR_MIN, hi=CREST_FACTOR_MAX, unit="dB",
    )
    plr = _coerce_float_nonan_in_range(
        _require(item, "plr", where=where), where=f"{where}.plr",
        lo=PLR_PSR_MIN, hi=PLR_PSR_MAX, unit="dB",
    )
    psr = _coerce_float_nonan_in_range(
        _require(item, "psr", where=where), where=f"{where}.psr",
        lo=PLR_PSR_MIN, hi=PLR_PSR_MAX, unit="dB",
    )

    # === Spectrum scalars + tuples ===
    dominant_band = _coerce_str(
        _require(item, "dominant_band", where=where), where=f"{where}.dominant_band"
    ).strip()
    # Cross-field #6 — dominant_band ∈ CANONICAL_BAND_LABELS
    if dominant_band not in CANONICAL_BAND_LABELS:
        raise MixAgentOutputError(
            f"{where}.dominant_band={dominant_band!r} not in "
            f"{CANONICAL_BAND_LABELS}."
        )
    centroid_hz = _coerce_float_nonan_in_range(
        _require(item, "centroid_hz", where=where), where=f"{where}.centroid_hz",
        lo=CENTROID_HZ_MIN, hi=CENTROID_HZ_MAX, unit="Hz",
    )
    rolloff_hz = _coerce_float_nonan_in_range(
        _require(item, "rolloff_hz", where=where), where=f"{where}.rolloff_hz",
        lo=CENTROID_HZ_MIN, hi=CENTROID_HZ_MAX, unit="Hz",
    )
    spectral_flatness = _coerce_float_nonan_in_range(
        _require(item, "spectral_flatness", where=where), where=f"{where}.spectral_flatness",
        lo=SPECTRAL_FLATNESS_MIN, hi=SPECTRAL_FLATNESS_MAX,
    )
    band_energies_raw = _coerce_list(
        _require(item, "band_energies", where=where), where=f"{where}.band_energies"
    )
    # Cross-field #3 — band_energies len exact 7
    if len(band_energies_raw) != CANONICAL_BAND_COUNT:
        raise MixAgentOutputError(
            f"{where}.band_energies len={len(band_energies_raw)} != "
            f"{CANONICAL_BAND_COUNT} (canonical : {CANONICAL_BAND_LABELS}). "
            f"mix_analyzer.py:382-390 FREQ_BANDS uses fixed 7-band split ; "
            f"reorder/migrate if upstream changes."
        )
    band_energies = tuple(
        _coerce_float_nonan_in_range(
            v, where=f"{where}.band_energies[{i}]", lo=0.0, hi=100.0, unit="%",
        )
        for i, v in enumerate(band_energies_raw)
    )
    # spectral_peaks
    peaks_raw = _coerce_list(
        item.get("spectral_peaks", []), where=f"{where}.spectral_peaks"
    )
    # Cross-field #5 — len cap
    if len(peaks_raw) > SPECTRAL_PEAKS_MAX:
        raise MixAgentOutputError(
            f"{where}.spectral_peaks len={len(peaks_raw)} > "
            f"{SPECTRAL_PEAKS_MAX} (cap). Keep only top-N most prominent ; "
            f"full spectrum lives in Excel."
        )
    spectral_peaks = tuple(
        _parse_spectral_peak(p, where=f"{where}.spectral_peaks[{i}]")
        for i, p in enumerate(peaks_raw)
    )
    # Cross-field #5 — magnitude descending order
    for i in range(len(spectral_peaks) - 1):
        if spectral_peaks[i].magnitude_db < spectral_peaks[i + 1].magnitude_db:
            raise MixAgentOutputError(
                f"{where}.spectral_peaks must be ordered by magnitude_db "
                f"DESCENDING (most prominent first). Got "
                f"[{i}].magnitude_db={spectral_peaks[i].magnitude_db} < "
                f"[{i+1}].magnitude_db={spectral_peaks[i+1].magnitude_db}."
            )

    # === Temporal scalars ===
    num_onsets = _coerce_int_strict(
        _require(item, "num_onsets", where=where), where=f"{where}.num_onsets"
    )
    if num_onsets < 0:
        raise MixAgentOutputError(
            f"{where}.num_onsets={num_onsets} must be >= 0"
        )
    onsets_per_second = _coerce_float_nonan_in_range(
        _require(item, "onsets_per_second", where=where),
        where=f"{where}.onsets_per_second",
        lo=ONSETS_PER_SECOND_MIN, hi=ONSETS_PER_SECOND_MAX,
    )

    # === Stereo scalars (cross-field #2 is_stereo coherence) ===
    is_stereo = _coerce_bool(
        _require(item, "is_stereo", where=where), where=f"{where}.is_stereo"
    )
    correlation_raw = item.get("correlation", None)
    correlation = (
        None if correlation_raw is None
        else _coerce_float_nonan_in_range(
            correlation_raw, where=f"{where}.correlation",
            lo=-1.0, hi=1.0,
        )
    )
    width_overall_raw = item.get("width_overall", None)
    width_overall = (
        None if width_overall_raw is None
        else _coerce_float_nonan_in_range(
            width_overall_raw, where=f"{where}.width_overall",
            lo=0.0, hi=1.0,
        )
    )
    width_per_band_raw = item.get("width_per_band", None)
    if width_per_band_raw is None:
        width_per_band = None
    else:
        wpb_list = _coerce_list(
            width_per_band_raw, where=f"{where}.width_per_band"
        )
        # Cross-field #4 — width_per_band len exact 7 when set
        if len(wpb_list) != CANONICAL_BAND_COUNT:
            raise MixAgentOutputError(
                f"{where}.width_per_band len={len(wpb_list)} != "
                f"{CANONICAL_BAND_COUNT} (canonical 7-band)."
            )
        width_per_band = tuple(
            _coerce_float_nonan_in_range(
                v, where=f"{where}.width_per_band[{i}]", lo=0.0, hi=1.0,
            )
            for i, v in enumerate(wpb_list)
        )

    # Cross-field #2 — is_stereo coherence
    if not is_stereo:
        for fname, fval in [("correlation", correlation),
                             ("width_overall", width_overall),
                             ("width_per_band", width_per_band)]:
            if fval is not None:
                raise MixAgentOutputError(
                    f"{where}.is_stereo=False but {fname}={fval!r} is set. "
                    f"Mono tracks have no stereo metrics — set to null."
                )
    else:
        if correlation is None or width_overall is None:
            raise MixAgentOutputError(
                f"{where}.is_stereo=True requires correlation AND "
                f"width_overall (got correlation={correlation!r}, "
                f"width_overall={width_overall!r}). width_per_band optional."
            )

    # === Musical scalars ===
    is_tonal = _coerce_bool(
        item.get("is_tonal", False), where=f"{where}.is_tonal"
    )
    dominant_note_raw = item.get("dominant_note", None)
    dominant_note = (
        None if dominant_note_raw is None or dominant_note_raw == ""
        else _coerce_str(dominant_note_raw, where=f"{where}.dominant_note")
    )
    tonal_strength = _coerce_float_nonan_in_range(
        item.get("tonal_strength", 0.0), where=f"{where}.tonal_strength",
        lo=TONAL_STRENGTH_MIN, hi=TONAL_STRENGTH_MAX,
    )

    # Cross-field #7 — is_tonal coherence (audit Pass 3 Finding 3).
    # When is_tonal=False, dominant_note must be None (logical : a non-tonal
    # signal has no clear dominant note ; mix_analyzer derives is_tonal from
    # tonal_strength threshold).
    if not is_tonal and dominant_note is not None:
        raise MixAgentOutputError(
            f"{where}.is_tonal=False but dominant_note={dominant_note!r} is set. "
            f"Non-tonal signals have no clear dominant note — set dominant_note "
            f"to null (mix_analyzer derives is_tonal from tonal_strength threshold)."
        )

    return TrackAudioMetrics(
        peak_db=peak_db, true_peak_db=true_peak_db, rms_db=rms_db,
        lufs_integrated=lufs_integrated, lufs_short_term_max=lufs_short_term_max,
        lra=lra, crest_factor=crest_factor, plr=plr, psr=psr,
        dominant_band=dominant_band, centroid_hz=centroid_hz,
        rolloff_hz=rolloff_hz, spectral_flatness=spectral_flatness,
        band_energies=band_energies, spectral_peaks=spectral_peaks,
        num_onsets=num_onsets, onsets_per_second=onsets_per_second,
        is_stereo=is_stereo, correlation=correlation,
        width_overall=width_overall, width_per_band=width_per_band,
        is_tonal=is_tonal, dominant_note=dominant_note,
        tonal_strength=tonal_strength,
    )


def _parse_genre_context(item: Any, *, where: str) -> GenreContext:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )
    family = _coerce_str(
        _require(item, "family", where=where), where=f"{where}.family"
    ).strip()
    if family not in VALID_GENRE_FAMILIES:
        raise MixAgentOutputError(
            f"{where}.family={family!r} not in {sorted(VALID_GENRE_FAMILIES)} "
            f"(8 families per mix_analyzer.py:267 FAMILY_PROFILES)."
        )
    target_lufs_mix = _coerce_float_nonan_in_range(
        _require(item, "target_lufs_mix", where=where), where=f"{where}.target_lufs_mix",
        lo=TARGET_LUFS_MIX_MIN, hi=TARGET_LUFS_MIX_MAX, unit="LUFS",
    )
    typical_crest_mix = _coerce_float_nonan_in_range(
        _require(item, "typical_crest_mix", where=where), where=f"{where}.typical_crest_mix",
        lo=TYPICAL_CREST_MIX_MIN, hi=TYPICAL_CREST_MIX_MAX, unit="dB",
    )
    density_tolerance = _coerce_str(
        _require(item, "density_tolerance", where=where),
        where=f"{where}.density_tolerance",
    ).strip()
    if density_tolerance not in VALID_DENSITY_TOLERANCES:
        raise MixAgentOutputError(
            f"{where}.density_tolerance={density_tolerance!r} not in "
            f"{sorted(VALID_DENSITY_TOLERANCES)}."
        )
    return GenreContext(
        family=family,
        target_lufs_mix=target_lufs_mix,
        typical_crest_mix=typical_crest_mix,
        density_tolerance=density_tolerance,
    )


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
    # Phase 4.7 — optional per-track audio metrics absorption
    audio_metrics_raw = item.get("audio_metrics", None)
    audio_metrics = (
        None if audio_metrics_raw is None
        else _parse_track_audio_metrics(audio_metrics_raw, where=f"{where}.audio_metrics")
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
        audio_metrics=audio_metrics,
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

    # Phase 4.7 — optional project-level genre context
    genre_context_raw = diag_dict.get("genre_context", None)
    genre_context = (
        None if genre_context_raw is None
        else _parse_genre_context(genre_context_raw, where="diagnostic.genre_context")
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
        genre_context=genre_context,
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
    # Cross-field semantic-contradiction checks (11 numbered — pure-payload).
    # The original Pass-2 list had 13 ; check #2 (gate threshold > 0) was
    # dropped because the threshold_db range [-60, 0] already enforces it.
    # Plus envelope rules enforced in `_parse_dynamics_envelope_strict`
    # (≥ 3 points if non-empty, bar-ascending strict, value range checks
    # per envelope type — total enforcement = 11 here + 3 in helper).
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


# ============================================================================
# Public parser — routing & sidechain lane (Phase 4.4)
# ============================================================================
#
# Topological domain (track→track refs), no parametric values. The
# parser enforces 8 cross-field semantic-contradiction checks (pure
# payload — checks requiring DiagnosticReport context like
# "new_trigger ∈ tracks" live in the agent prompt as anti-patterns).


# Compile the regex once at module load — used by check #7 (recreating
# stale ref) and exposed via the schema constant for agent-side detection.
_STALE_SIDECHAIN_PATTERN = re.compile(STALE_SIDECHAIN_REGEX)


def _parse_sidechain_repair(item: Any, *, where: str) -> SidechainRepair:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )

    track = _coerce_str(_require(item, "track", where=where), where=f"{where}.track").strip()
    if not track:
        raise MixAgentOutputError(f"{where}.track must be non-empty")

    fix_type = _coerce_str(
        _require(item, "fix_type", where=where), where=f"{where}.fix_type"
    ).strip()
    if fix_type not in VALID_ROUTING_FIX_TYPES:
        raise MixAgentOutputError(
            f"{where}.fix_type={fix_type!r} not in {sorted(VALID_ROUTING_FIX_TYPES)}"
        )

    current_raw = item.get("current_trigger", None)
    current_trigger = (
        None if current_raw is None or current_raw == ""
        else _coerce_str(current_raw, where=f"{where}.current_trigger")
    )

    new_raw = item.get("new_trigger", None)
    new_trigger = (
        None if new_raw is None or new_raw == ""
        else _coerce_str(new_raw, where=f"{where}.new_trigger")
    )

    rationale = _coerce_str(item.get("rationale", ""))
    inspired_by_raw = _coerce_list(
        item.get("inspired_by", []), where=f"{where}.inspired_by"
    )
    inspired_by = _parse_citations(inspired_by_raw, where=f"{where}.inspired_by")

    # ------------------------------------------------------------------
    # Cross-field semantic-contradiction checks (8 numbered — pure-payload).
    # Required-field-per-fix_type matrix :
    #   redirect : current_trigger AND new_trigger BOTH required, must differ
    #   remove   : current_trigger required ; new_trigger must be None
    #   create   : new_trigger required ; current_trigger must be None
    # ------------------------------------------------------------------

    # #1 — redirect with same source and target (no-op)
    if (fix_type == "sidechain_redirect"
            and current_trigger is not None and new_trigger is not None
            and current_trigger == new_trigger):
        raise MixAgentOutputError(
            f"{where}.fix_type='sidechain_redirect' but new_trigger == current_trigger "
            f"({current_trigger!r}) — no-op, not a repair."
        )

    # #2 — redirect missing required fields
    if fix_type == "sidechain_redirect" and (current_trigger is None or new_trigger is None):
        raise MixAgentOutputError(
            f"{where}.fix_type='sidechain_redirect' requires BOTH current_trigger "
            f"and new_trigger (non-empty). Got current={current_trigger!r}, "
            f"new={new_trigger!r}."
        )

    # #3 — remove with new_trigger set (semantic contradiction)
    if fix_type == "sidechain_remove" and new_trigger is not None:
        raise MixAgentOutputError(
            f"{where}.fix_type='sidechain_remove' but new_trigger={new_trigger!r} "
            f"is set. A remove has no target — set new_trigger to null."
        )

    # #4 — remove without current_trigger (no ref to remove)
    if fix_type == "sidechain_remove" and current_trigger is None:
        raise MixAgentOutputError(
            f"{where}.fix_type='sidechain_remove' requires current_trigger "
            f"(the stale ref being removed). Got null."
        )

    # #5 — create with current_trigger set (semantic contradiction)
    if fix_type == "sidechain_create" and current_trigger is not None:
        raise MixAgentOutputError(
            f"{where}.fix_type='sidechain_create' but current_trigger={current_trigger!r} "
            f"is set. A create has no existing ref to replace — set current_trigger to null."
        )

    # #6 — create without new_trigger (no target)
    if fix_type == "sidechain_create" and new_trigger is None:
        raise MixAgentOutputError(
            f"{where}.fix_type='sidechain_create' requires new_trigger "
            f"(the trigger track being wired). Got null."
        )

    # #7 — recreating a stale ref : new_trigger must NOT match the
    # raw AudioIn/Track.N format (it should be a resolved track name)
    if (fix_type in {"sidechain_redirect", "sidechain_create"}
            and new_trigger is not None
            and _STALE_SIDECHAIN_PATTERN.match(new_trigger)):
        raise MixAgentOutputError(
            f"{where}.new_trigger={new_trigger!r} matches the raw stale-ref format "
            f"(AudioIn/Track.N/...). Use a resolved track name (e.g. 'Kick A'), "
            f"not the XML routing string — Tier B resolves the index from the name."
        )

    # #8 — depth-light : rationale ≥ 50 chars, ≥ 1 citation
    if len(rationale) < 50:
        raise MixAgentOutputError(
            f"{where}.rationale too short ({len(rationale)} chars, need ≥ 50). "
            f"Untraced routing repair = stub : Tier B routing-configurator can't "
            f"justify the wiring change to safety-guardian."
        )
    if not inspired_by:
        raise MixAgentOutputError(
            f"{where}.inspired_by must contain at least one citation. "
            f"Cite the routing_warning, CDE diagnostic, or user brief that "
            f"justifies this repair."
        )

    return SidechainRepair(
        track=track,
        fix_type=fix_type,
        current_trigger=current_trigger,
        new_trigger=new_trigger,
        rationale=rationale,
        inspired_by=inspired_by,
    )


def parse_routing_decision(
    payload: Mapping[str, Any],
) -> MixDecision[RoutingDecision]:
    """Parse a routing-and-sidechain-architect payload into a MixDecision.

    Expected shape (schema 1.0) :
        {
          "schema_version": "1.0",
          "routing": {
            "repairs": [
              {
                "track": str,
                "fix_type": str ∈ VALID_ROUTING_FIX_TYPES,
                "current_trigger": Optional[str],
                "new_trigger": Optional[str],
                "rationale": str (≥ 50 chars),
                "inspired_by": [{kind, path, excerpt}, …]   # ≥ 1 cite
              },
              ...
            ]
          },
          "cited_by": [...],
          "rationale": str,
          "confidence": float (0..1)
        }

    Or a refusal: {"error": "...", "details": "..."}

    Strict on output : 8 cross-field semantic-contradiction checks (per
    fix_type field requirements + recreating-stale-ref + depth-light)
    plus duplicate-key check across the repairs list.
    """
    envelope = _parse_envelope(
        payload, supported_versions=SUPPORTED_ROUTING_SCHEMA_VERSIONS
    )

    routing_dict = _require(payload, "routing", where="root")
    if not isinstance(routing_dict, Mapping):
        raise MixAgentOutputError(
            f"routing: expected object, got {type(routing_dict).__name__}"
        )

    repairs_raw = _coerce_list(
        routing_dict.get("repairs", []), where="routing.repairs"
    )
    repairs = tuple(
        _parse_sidechain_repair(item, where=f"routing.repairs[{i}]")
        for i, item in enumerate(repairs_raw)
    )

    # Cross-correction check : duplicate (track, fix_type, current_trigger,
    # new_trigger) tuples across repairs (Tier B would have collisions).
    seen_keys: set[tuple[str, str, Optional[str], Optional[str]]] = set()
    for i, r in enumerate(repairs):
        key = (r.track, r.fix_type, r.current_trigger, r.new_trigger)
        if key in seen_keys:
            raise MixAgentOutputError(
                f"routing.repairs[{i}]: duplicate repair "
                f"(track={r.track!r}, fix_type={r.fix_type!r}, "
                f"current_trigger={r.current_trigger!r}, new_trigger={r.new_trigger!r}). "
                f"Tier B would collide ; remove the duplicate."
            )
        seen_keys.add(key)

    decision_value = RoutingDecision(repairs=repairs)
    return MixDecision(value=decision_value, lane="routing", **envelope)


def parse_routing_decision_from_response(
    text: str,
) -> MixDecision[RoutingDecision]:
    """End-to-end: raw LLM response → MixDecision[RoutingDecision]."""
    return parse_routing_decision(extract_json_payload(text))


# ============================================================================
# Public parser — stereo & spatial lane (Phase 4.5)
# ============================================================================
#
# Parametric domain (per-track values for pan / width / phase / mono /
# balance / mid-side). 11 cross-field semantic-contradiction checks
# pure-payload + duplicate-key cross-corrections check.
#
# All ranges verified against StereoGain catalog (audit Pass 1 v2).


# Map move_type → (required value-field-name, range_min, range_max,
# neutral-value-or-None-if-no-no-op-check, error-format-spec).
# Used to centralize the "required field per move_type" cross-field
# checks #1-#10.
_SPATIAL_VALUE_FIELD_SPEC = {
    "pan":         ("pan",                PAN_MIN,                 PAN_MAX,                 None,                  "[-1, 1]"),
    "width":       ("stereo_width",       STEREO_WIDTH_MIN,        STEREO_WIDTH_MAX,        STEREO_WIDTH_NEUTRAL,  "[0, 4] excluding 1.0 (neutre)"),
    "bass_mono":   ("bass_mono_freq_hz",  BASS_MONO_FREQ_MIN_HZ,   BASS_MONO_FREQ_MAX_HZ,   None,                  "[50, 500] Hz"),
    "balance":     ("balance",            BALANCE_MIN,             BALANCE_MAX,             BALANCE_NEUTRAL,       "[-1, 1] excluding 0.0 (center)"),
    "ms_balance":  ("mid_side_balance",   MS_BALANCE_MIN,          MS_BALANCE_MAX,          MS_BALANCE_NEUTRAL,    "[0, 2] excluding 1.0 (neutre — NOT 0 which is full mid)"),
}

# Move types that don't take a numeric value field but use a different
# encoding : "phase_flip" uses phase_channel ; "mono" uses no value
# field at all (move_type itself signals Mono=True).
_SPATIAL_NUMERIC_VALUE_FIELDS = ("pan", "stereo_width", "bass_mono_freq_hz",
                                 "balance", "mid_side_balance")


def _parse_spatial_move(item: Any, *, where: str) -> SpatialMove:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )

    track = _coerce_str(_require(item, "track", where=where), where=f"{where}.track").strip()
    if not track:
        raise MixAgentOutputError(f"{where}.track must be non-empty")

    move_type = _coerce_str(
        _require(item, "move_type", where=where), where=f"{where}.move_type"
    ).strip()
    if move_type not in VALID_SPATIAL_MOVE_TYPES:
        raise MixAgentOutputError(
            f"{where}.move_type={move_type!r} not in {sorted(VALID_SPATIAL_MOVE_TYPES)}"
        )

    # Read all value fields ; cross-field checks below validate combos.
    pan = _coerce_optional_float_in_range(
        item.get("pan"), where=f"{where}.pan",
        lo=PAN_MIN, hi=PAN_MAX, unit="(pan)",
    )
    stereo_width = _coerce_optional_float_in_range(
        item.get("stereo_width"), where=f"{where}.stereo_width",
        lo=STEREO_WIDTH_MIN, hi=STEREO_WIDTH_MAX, unit="(width)",
    )
    bass_mono_freq_hz = _coerce_optional_float_in_range(
        item.get("bass_mono_freq_hz"), where=f"{where}.bass_mono_freq_hz",
        lo=BASS_MONO_FREQ_MIN_HZ, hi=BASS_MONO_FREQ_MAX_HZ, unit="Hz",
    )
    balance = _coerce_optional_float_in_range(
        item.get("balance"), where=f"{where}.balance",
        lo=BALANCE_MIN, hi=BALANCE_MAX, unit="(balance)",
    )
    mid_side_balance = _coerce_optional_float_in_range(
        item.get("mid_side_balance"), where=f"{where}.mid_side_balance",
        lo=MS_BALANCE_MIN, hi=MS_BALANCE_MAX, unit="(MS balance)",
    )

    # phase_channel : optional string, validated below for phase_flip
    phase_channel_raw = item.get("phase_channel", None)
    phase_channel = (
        None if phase_channel_raw is None or phase_channel_raw == ""
        else _coerce_str(phase_channel_raw, where=f"{where}.phase_channel").strip()
    )

    chain_position = _coerce_str(
        item.get("chain_position", "default"),
        where=f"{where}.chain_position",
    ).strip()
    if not chain_position:
        chain_position = "default"
    if chain_position not in VALID_SPATIAL_CHAIN_POSITIONS:
        raise MixAgentOutputError(
            f"{where}.chain_position={chain_position!r} not in "
            f"{sorted(VALID_SPATIAL_CHAIN_POSITIONS)}. Use 'default' if no preference."
        )

    rationale = _coerce_str(item.get("rationale", ""))
    inspired_by_raw = _coerce_list(
        item.get("inspired_by", []), where=f"{where}.inspired_by"
    )
    inspired_by = _parse_citations(inspired_by_raw, where=f"{where}.inspired_by")

    # ------------------------------------------------------------------
    # Cross-field semantic-contradiction checks (11 numbered — pure-payload).
    # Audit Pass 2 corrections applied :
    # - check #2 range [0, 4] (not [0, 2])
    # - check #5 range [50, 500] (not [60, 250])
    # - check #9 range [0, 2] (not [-1, 1])
    # - check #10 no-op == 1.0 (not 0.0)
    # ------------------------------------------------------------------

    # Pre-compute : is the agent setting numeric value fields not relevant
    # to this move_type? Used by checks #4 (mono) and #6 (phase_flip)
    # which forbid extraneous fields.
    relevant_field_name = (
        _SPATIAL_VALUE_FIELD_SPEC[move_type][0]
        if move_type in _SPATIAL_VALUE_FIELD_SPEC
        else None
    )
    other_numeric_set = []
    for fname in _SPATIAL_NUMERIC_VALUE_FIELDS:
        if fname == relevant_field_name:
            continue
        val = locals().get(fname)
        if val is not None:
            other_numeric_set.append(fname)

    # #1 — pan : pan in [-1, 1] required ; verifies presence (range already enforced above)
    if move_type == "pan" and pan is None:
        raise MixAgentOutputError(
            f"{where}.move_type='pan' requires pan field (in [-1, 1])."
        )

    # #2 — width : stereo_width required ; range [0, 4] verified above
    if move_type == "width" and stereo_width is None:
        raise MixAgentOutputError(
            f"{where}.move_type='width' requires stereo_width field (in [0, 4] \\ {{1.0}})."
        )

    # #3 — width with no-op identity value (1.0 = neutre)
    if move_type == "width" and stereo_width is not None and stereo_width == STEREO_WIDTH_NEUTRAL:
        raise MixAgentOutputError(
            f"{where}.move_type='width' but stereo_width={stereo_width} == 1.0 (neutre, no-op identity). "
            f"Pick a value ≠ 1.0 to actually change the stereo width."
        )

    # #4 — every move_type forbids extra value fields beyond its own
    # (Phase 4.5.1 audit Finding 1 : was previously only enforced for
    # 'mono' ; extended to all 7 move_types so schema docstring's
    # "others None" promise actually holds in the parser).
    extras = list(other_numeric_set)
    # phase_channel is the move_type-specific field for phase_flip ; for
    # any OTHER move_type its presence is an extra.
    if move_type != "phase_flip" and phase_channel is not None:
        extras.append("phase_channel")
    if extras:
        raise MixAgentOutputError(
            f"{where}.move_type={move_type!r} but extra value fields set : "
            f"{extras}. Each move_type allows ONE specific value field "
            f"(pan→pan, width→stereo_width, bass_mono→bass_mono_freq_hz, "
            f"phase_flip→phase_channel, balance→balance, ms_balance→"
            f"mid_side_balance ; mono allows none). Leave others null."
        )

    # #5 — bass_mono : bass_mono_freq_hz required, in [50, 500]
    if move_type == "bass_mono" and bass_mono_freq_hz is None:
        raise MixAgentOutputError(
            f"{where}.move_type='bass_mono' requires bass_mono_freq_hz field (in [50, 500] Hz)."
        )

    # #6 — phase_flip : phase_channel in {"L", "R"} required
    if move_type == "phase_flip":
        if phase_channel not in VALID_PHASE_CHANNELS:
            raise MixAgentOutputError(
                f"{where}.move_type='phase_flip' requires phase_channel in "
                f"{sorted(VALID_PHASE_CHANNELS)}, got {phase_channel!r}. "
                f"Flipping both channels = no-op (canceling phase invert)."
            )

    # #7 — balance : balance in [-1, 1] required
    if move_type == "balance" and balance is None:
        raise MixAgentOutputError(
            f"{where}.move_type='balance' requires balance field (in [-1, 1] \\ {{0.0}})."
        )

    # #8 — balance with no-op identity (0.0 = center)
    if move_type == "balance" and balance is not None and balance == BALANCE_NEUTRAL:
        raise MixAgentOutputError(
            f"{where}.move_type='balance' but balance={balance} == 0.0 (center, no-op identity). "
            f"Pick a value ≠ 0.0 to actually shift L/R balance."
        )

    # #9 — ms_balance : mid_side_balance in [0, 2] required
    # (audit Pass 1 v2 Finding B : range was incorrectly [-1, 1] before fix)
    if move_type == "ms_balance" and mid_side_balance is None:
        raise MixAgentOutputError(
            f"{where}.move_type='ms_balance' requires mid_side_balance field "
            f"(in [0, 2] \\ {{1.0}} — 0.0=full mid, 1.0=neutral, 2.0=full side)."
        )

    # #10 — ms_balance with no-op identity (1.0 = neutre — NOT 0 which is full mid)
    # (audit Pass 1 v2 Finding B/H : was incorrectly == 0 before fix)
    if (move_type == "ms_balance" and mid_side_balance is not None
            and mid_side_balance == MS_BALANCE_NEUTRAL):
        raise MixAgentOutputError(
            f"{where}.move_type='ms_balance' but mid_side_balance={mid_side_balance} == 1.0 "
            f"(neutral, no-op identity — note: 0.0 = full mid, 2.0 = full side, "
            f"1.0 = balanced). Pick a value ≠ 1.0 to actually shift M/S balance."
        )

    # #11 — depth-light : rationale ≥ 50 chars + ≥ 1 citation
    if len(rationale) < 50:
        raise MixAgentOutputError(
            f"{where}.rationale too short ({len(rationale)} chars, need ≥ 50). "
            f"Untraced spatial move = stub : Tier B spatial-configurator can't "
            f"justify the wiring change to safety-guardian."
        )
    if not inspired_by:
        raise MixAgentOutputError(
            f"{where}.inspired_by must contain at least one citation. "
            f"Cite the Anomaly cell, Mix Health Score, or user brief that "
            f"justifies this spatial move."
        )

    return SpatialMove(
        track=track,
        move_type=move_type,
        pan=pan,
        stereo_width=stereo_width,
        bass_mono_freq_hz=bass_mono_freq_hz,
        phase_channel=phase_channel,
        balance=balance,
        mid_side_balance=mid_side_balance,
        chain_position=chain_position,
        rationale=rationale,
        inspired_by=inspired_by,
    )


def parse_spatial_decision(
    payload: Mapping[str, Any],
) -> MixDecision[SpatialDecision]:
    """Parse a stereo-and-spatial-engineer payload into a MixDecision.

    Expected shape (schema 1.0) :
        {
          "schema_version": "1.0",
          "stereo_spatial": {
            "moves": [
              {
                "track": str,
                "move_type": str ∈ VALID_SPATIAL_MOVE_TYPES,
                "pan": Optional[float],                  # for "pan"
                "stereo_width": Optional[float],          # for "width"
                "bass_mono_freq_hz": Optional[float],     # for "bass_mono"
                "phase_channel": Optional[str],           # for "phase_flip"
                "balance": Optional[float],               # for "balance"
                "mid_side_balance": Optional[float],      # for "ms_balance"
                "chain_position": str ∈ VALID_SPATIAL_CHAIN_POSITIONS,
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

    Strict on output : 11 cross-field semantic-contradiction checks
    (pure-payload) plus duplicate (track, move_type) cross-correction
    check. Range bounds verified against ableton_devices_mapping.json
    StereoGain.params (audit Pass 1 v2 corrections applied).
    """
    envelope = _parse_envelope(
        payload, supported_versions=SUPPORTED_SPATIAL_SCHEMA_VERSIONS
    )

    spatial_dict = _require(payload, "stereo_spatial", where="root")
    if not isinstance(spatial_dict, Mapping):
        raise MixAgentOutputError(
            f"stereo_spatial: expected object, got {type(spatial_dict).__name__}"
        )

    moves_raw = _coerce_list(
        spatial_dict.get("moves", []), where="stereo_spatial.moves"
    )
    moves = tuple(
        _parse_spatial_move(item, where=f"stereo_spatial.moves[{i}]")
        for i, item in enumerate(moves_raw)
    )

    # Cross-correction check : duplicate (track, move_type) tuples in moves
    # (Tier B would have collisions / ambiguous dual-state).
    seen_keys: set[tuple[str, str]] = set()
    for i, m in enumerate(moves):
        key = (m.track, m.move_type)
        if key in seen_keys:
            raise MixAgentOutputError(
                f"stereo_spatial.moves[{i}]: duplicate move "
                f"(track={m.track!r}, move_type={m.move_type!r}). "
                f"Multiple SpatialMove on same track must have distinct "
                f"move_type ; remove or merge the duplicate."
            )
        seen_keys.add(key)

    decision_value = SpatialDecision(moves=moves)
    return MixDecision(value=decision_value, lane="stereo_spatial", **envelope)


def parse_spatial_decision_from_response(
    text: str,
) -> MixDecision[SpatialDecision]:
    """End-to-end: raw LLM response → MixDecision[SpatialDecision]."""
    return parse_spatial_decision(extract_json_payload(text))


# ============================================================================
# Public parser — chain build lane (Phase 4.6)
# ============================================================================
#
# Second-order reconciliation parser. 10 cross-field semantic-contradiction
# checks pure-payload + duplicate-key cross-correction check.
#
# Audit findings applied (Pass 1 + Pass 2) :
# - is_preexisting flag with conditional validation (Pass 1 Findings B/C)
# - Limiter at max position within plan, NOT hardcoded slot 10 (Pass 2 #3)
# - Hard semantic rules priority hierarchy (Pass 2 #2)
# - move_type="pan" handled (no chain slot — Mixer.Pan, Pass 2 #6)


def _parse_chain_slot(item: Any, *, where: str) -> ChainSlot:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )

    position = _coerce_int_strict(
        _require(item, "position", where=where), where=f"{where}.position"
    )
    if not (0 <= position <= CHAIN_MAX_POSITION):
        raise MixAgentOutputError(
            f"{where}.position={position} not in [0, {CHAIN_MAX_POSITION}]"
        )

    device = _coerce_str(
        _require(item, "device", where=where), where=f"{where}.device"
    ).strip()
    if not device:
        raise MixAgentOutputError(f"{where}.device must be non-empty")

    is_preexisting = _coerce_bool(
        item.get("is_preexisting", False), where=f"{where}.is_preexisting"
    )

    instance = _coerce_int_strict(
        item.get("instance", 0), where=f"{where}.instance"
    )
    if instance < 0:
        raise MixAgentOutputError(
            f"{where}.instance={instance} must be ≥ 0"
        )

    consumes_lane_raw = item.get("consumes_lane", None)
    consumes_lane = (
        None if consumes_lane_raw is None or consumes_lane_raw == ""
        else _coerce_str(consumes_lane_raw, where=f"{where}.consumes_lane").strip()
    )

    indices_raw = _coerce_list(
        item.get("consumes_indices", []), where=f"{where}.consumes_indices"
    )
    consumes_indices_list = []
    for i, idx in enumerate(indices_raw):
        idx_int = _coerce_int_strict(idx, where=f"{where}.consumes_indices[{i}]")
        # Phase 4.6.1 audit Finding 2 : reject negative indices.
        # Python negative indexing (bands[-1] = last band) would confuse
        # Tier B which expects original-position references.
        if idx_int < 0:
            raise MixAgentOutputError(
                f"{where}.consumes_indices[{i}]={idx_int} must be >= 0 "
                f"(references position in lane's collection ; negative "
                f"indexing not allowed — would silently re-target via "
                f"Python's bands[-1]=last semantics)."
            )
        consumes_indices_list.append(idx_int)
    consumes_indices = tuple(consumes_indices_list)

    purpose = _coerce_str(item.get("purpose", ""), where=f"{where}.purpose")

    # ------------------------------------------------------------------
    # Cross-field semantic-contradiction checks (slot-level).
    # is_preexisting conditional validation (Pass 1 Findings B/C).
    # ------------------------------------------------------------------

    if is_preexisting:
        # #1 — preexisting must have consumes_lane=None
        if consumes_lane is not None:
            raise MixAgentOutputError(
                f"{where}.is_preexisting=True but consumes_lane={consumes_lane!r} "
                f"is set. A preserved device has no lane source — set consumes_lane to null."
            )
        # #2 — preexisting must have empty consumes_indices
        if consumes_indices:
            raise MixAgentOutputError(
                f"{where}.is_preexisting=True but consumes_indices={consumes_indices} "
                f"is non-empty. A preserved device has no source decisions — leave empty."
            )
    else:
        # #3 — non-preexisting device must be in VALID_CHAIN_DEVICES
        if device not in VALID_CHAIN_DEVICES:
            raise MixAgentOutputError(
                f"{where}.device={device!r} not in {sorted(VALID_CHAIN_DEVICES)} "
                f"(set is_preexisting=True if preserving a non-mapped device "
                f"already in track.devices, e.g., Reverb / Tuner / 3rd-party VST)."
            )
        # #4 — non-preexisting must have consumes_lane in VALID_CONSUMES_LANES
        if consumes_lane is None or consumes_lane not in VALID_CONSUMES_LANES:
            raise MixAgentOutputError(
                f"{where}.consumes_lane={consumes_lane!r} required and must be in "
                f"{sorted(VALID_CONSUMES_LANES)} when is_preexisting=False "
                f"(every inserted device must source from a Tier A lane)."
            )
        # #5 — non-preexisting must have non-empty consumes_indices
        if not consumes_indices:
            raise MixAgentOutputError(
                f"{where}.consumes_indices is empty but is_preexisting=False — "
                f"orphan device. Every inserted device must materialize ≥ 1 "
                f"Tier A decision (cite indices in lane's collection)."
            )
        # #6 — Eq8 8-band budget limit
        if device == "Eq8" and len(consumes_indices) > EQ8_MAX_BANDS_PER_INSTANCE:
            raise MixAgentOutputError(
                f"{where}.device='Eq8' but consumes_indices length="
                f"{len(consumes_indices)} > {EQ8_MAX_BANDS_PER_INSTANCE} "
                f"(Eq8 8-band hard limit). Split into multiple Eq8 instances "
                f"with distinct ``instance`` values."
            )

    return ChainSlot(
        position=position,
        device=device,
        is_preexisting=is_preexisting,
        instance=instance,
        consumes_lane=consumes_lane,
        consumes_indices=consumes_indices,
        purpose=purpose,
    )


def _parse_track_chain_plan(item: Any, *, where: str) -> TrackChainPlan:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )

    track = _coerce_str(_require(item, "track", where=where), where=f"{where}.track").strip()
    if not track:
        raise MixAgentOutputError(f"{where}.track must be non-empty")

    slots_raw = _coerce_list(
        _require(item, "slots", where=where), where=f"{where}.slots"
    )
    slots = tuple(
        _parse_chain_slot(s, where=f"{where}.slots[{i}]")
        for i, s in enumerate(slots_raw)
    )

    rationale = _coerce_str(item.get("rationale", ""))
    inspired_by_raw = _coerce_list(
        item.get("inspired_by", []), where=f"{where}.inspired_by"
    )
    inspired_by = _parse_citations(inspired_by_raw, where=f"{where}.inspired_by")

    cross_lane_notes = _coerce_str_tuple(
        item.get("cross_lane_notes", []), where=f"{where}.cross_lane_notes"
    )

    # ------------------------------------------------------------------
    # Plan-level cross-field checks.
    # ------------------------------------------------------------------

    # #7 — slots must have strictly monotone-increasing position
    positions = [s.position for s in slots]
    if positions != sorted(set(positions)) or len(set(positions)) != len(positions):
        raise MixAgentOutputError(
            f"{where}.slots positions must be strictly increasing (no duplicates, "
            f"no out-of-order). Got positions: {positions}"
        )

    # #8 — Limiter device (when present) MUST be at the maximum position
    # within this plan (terminal placement enforced ; absolute slot number
    # varies per plan length — Pass 2 audit Finding 3 fix).
    if slots:
        max_pos = max(s.position for s in slots)
        for s in slots:
            if s.device == "Limiter" and s.position != max_pos:
                raise MixAgentOutputError(
                    f"{where}.slots contains Limiter at position {s.position} "
                    f"but max position in this plan is {max_pos}. Limiter is "
                    f"terminal — it must be the last slot of the chain. "
                    f"Move Limiter to position {max_pos} or remove subsequent "
                    f"slots."
                )

    # #9 — depth-light : rationale ≥ 50 chars + ≥ 1 citation
    if len(rationale) < 50:
        raise MixAgentOutputError(
            f"{where}.rationale too short ({len(rationale)} chars, need ≥ 50). "
            f"Untraced chain plan = stub : Tier B configurators can't verify "
            f"the ordering rationale to safety-guardian."
        )
    if not inspired_by:
        raise MixAgentOutputError(
            f"{where}.inspired_by must contain at least one citation. "
            f"Cite the Tier A blueprint slots that justify the slot ordering, "
            f"OR the user brief override."
        )

    return TrackChainPlan(
        track=track,
        slots=slots,
        rationale=rationale,
        inspired_by=inspired_by,
        cross_lane_notes=cross_lane_notes,
    )


def parse_chain_decision(
    payload: Mapping[str, Any],
) -> MixDecision[ChainBuildDecision]:
    """Parse a chain-builder payload into a MixDecision.

    Expected shape (schema 1.0) :
        {
          "schema_version": "1.0",
          "chain": {
            "plans": [
              {
                "track": str,
                "slots": [
                  {
                    "position": int (∈ [0, 31]),
                    "device": str,
                    "is_preexisting": bool (default false),
                    "instance": int (default 0),
                    "consumes_lane": Optional[str ∈ VALID_CONSUMES_LANES],
                    "consumes_indices": Optional[list[int]],
                    "purpose": Optional[str]
                  },
                  ...
                ],
                "rationale": str (≥ 50 chars),
                "inspired_by": [{kind, path, excerpt}, …]   # ≥ 1 cite
                "cross_lane_notes": Optional[list[str]]
              },
              ...
            ]
          },
          "cited_by": [...],
          "rationale": str,
          "confidence": float (0..1)
        }

    Or a refusal: {"error": "...", "details": "..."}

    Strict on output : 9 cross-field semantic-contradiction checks
    (slot-level + plan-level + duplicate-key) including conditional
    is_preexisting validation, position monotonicity, Eq8 8-band budget,
    Limiter terminal placement, and depth-light per plan.
    """
    envelope = _parse_envelope(
        payload, supported_versions=SUPPORTED_CHAIN_SCHEMA_VERSIONS
    )

    chain_dict = _require(payload, "chain", where="root")
    if not isinstance(chain_dict, Mapping):
        raise MixAgentOutputError(
            f"chain: expected object, got {type(chain_dict).__name__}"
        )

    plans_raw = _coerce_list(
        chain_dict.get("plans", []), where="chain.plans"
    )
    plans = tuple(
        _parse_track_chain_plan(p, where=f"chain.plans[{i}]")
        for i, p in enumerate(plans_raw)
    )

    # Cross-correction check : duplicate (track,) tuples in plans
    # (each track gets exactly one plan).
    seen_tracks: set[str] = set()
    for i, p in enumerate(plans):
        if p.track in seen_tracks:
            raise MixAgentOutputError(
                f"chain.plans[{i}]: duplicate plan for track={p.track!r}. "
                f"Each track gets exactly one TrackChainPlan ; merge the duplicate."
            )
        seen_tracks.add(p.track)

    decision_value = ChainBuildDecision(plans=plans)
    return MixDecision(value=decision_value, lane="chain", **envelope)


def parse_chain_decision_from_response(
    text: str,
) -> MixDecision[ChainBuildDecision]:
    """End-to-end: raw LLM response → MixDecision[ChainBuildDecision]."""
    return parse_chain_decision(extract_json_payload(text))


# ============================================================================
# Public parser — automation lane (Phase 4.8 corrective + mastering scope)
# ============================================================================
#
# 8 cross-field semantic-contradiction checks (pure-payload).
# Out-of-scope (creative envelopes) flagged as agent-prompt anti-pattern.


def _parse_automation_point(item: Any, *, where: str) -> AutomationPoint:
    """Parse one envelope point. Accepts {time_beats, value} object OR
    [time_beats, value] pair. Phase 4.8.2 : float resolution (was int
    bar) for sub-bar precision matching mix_analyzer's frame-level
    analysis."""
    if isinstance(item, Mapping):
        time_beats = _coerce_float(
            _require(item, "time_beats", where=where), where=f"{where}.time_beats"
        )
        value = _coerce_float(_require(item, "value", where=where), where=f"{where}.value")
    elif isinstance(item, (list, tuple)):
        if len(item) != 2:
            raise MixAgentOutputError(
                f"{where}: expected [time_beats, value] pair, got len={len(item)}"
            )
        time_beats = _coerce_float(item[0], where=f"{where}[0]")
        value = _coerce_float(item[1], where=f"{where}[1]")
    else:
        raise MixAgentOutputError(
            f"{where}: expected object or [time_beats, value] pair, "
            f"got {type(item).__name__}"
        )
    if time_beats < 0 or time_beats > AUTOMATION_MAX_TIME_BEATS:
        raise MixAgentOutputError(
            f"{where}.time_beats={time_beats} not in "
            f"[0, {AUTOMATION_MAX_TIME_BEATS}] (Ableton native beats unit ; "
            f"in 4/4 time signature, 1 bar = 4 beats so cap covers ~10h song "
            f"at 120 BPM)"
        )
    return AutomationPoint(time_beats=time_beats, value=value)


def _parse_automation_envelope(item: Any, *, where: str) -> AutomationEnvelope:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )

    purpose = _coerce_str(
        _require(item, "purpose", where=where), where=f"{where}.purpose"
    ).strip()
    if purpose not in VALID_AUTOMATION_PURPOSES:
        raise MixAgentOutputError(
            f"{where}.purpose={purpose!r} not in {sorted(VALID_AUTOMATION_PURPOSES)} "
            f"(creative envelope purposes are out-of-scope Phase 4.8 ; future "
            f"creative-automation agent will handle riser/drop/fx swell/etc.)"
        )

    target_track = _coerce_str(
        _require(item, "target_track", where=where), where=f"{where}.target_track"
    ).strip()
    if not target_track:
        raise MixAgentOutputError(f"{where}.target_track must be non-empty")

    target_device = _coerce_str(
        _require(item, "target_device", where=where), where=f"{where}.target_device"
    ).strip()
    if target_device not in VALID_AUTOMATION_TARGET_DEVICES:
        raise MixAgentOutputError(
            f"{where}.target_device={target_device!r} not in "
            f"{sorted(VALID_AUTOMATION_TARGET_DEVICES)}."
        )

    target_param = _coerce_str(
        _require(item, "target_param", where=where), where=f"{where}.target_param"
    ).strip()
    if not target_param:
        raise MixAgentOutputError(f"{where}.target_param must be non-empty")

    target_device_instance = _coerce_int_strict(
        item.get("target_device_instance", 0),
        where=f"{where}.target_device_instance",
    )
    if target_device_instance < 0:
        raise MixAgentOutputError(
            f"{where}.target_device_instance={target_device_instance} must be >= 0"
        )

    band_index_raw = item.get("target_band_index", None)
    if band_index_raw is None:
        target_band_index = None
    else:
        target_band_index = _coerce_int_strict(
            band_index_raw, where=f"{where}.target_band_index"
        )
        if not (0 <= target_band_index <= 7):
            raise MixAgentOutputError(
                f"{where}.target_band_index={target_band_index} not in [0, 7] "
                f"(Eq8 has 8 bands, 0-indexed)."
            )

    points_raw = _coerce_list(
        _require(item, "points", where=where), where=f"{where}.points"
    )
    points = tuple(
        _parse_automation_point(p, where=f"{where}.points[{i}]")
        for i, p in enumerate(points_raw)
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
    # Cross-field semantic-contradiction checks (8 pure-payload).
    # ------------------------------------------------------------------

    # #1 — points len ≥ AUTOMATION_MIN_POINTS (3) ; ≤ AUTOMATION_MAX_POINTS
    if len(points) < AUTOMATION_MIN_POINTS:
        raise MixAgentOutputError(
            f"{where}.points len={len(points)} < {AUTOMATION_MIN_POINTS} "
            f"(envelope needs ≥ 3 points ; 2 = ramp = static change, use "
            f"static parameter on the Tier A decision instead)."
        )
    if len(points) > AUTOMATION_MAX_POINTS:
        raise MixAgentOutputError(
            f"{where}.points len={len(points)} > {AUTOMATION_MAX_POINTS} "
            f"(sanity cap to prevent runaway envelopes)."
        )

    # #2 — time_beats strictly ascending no duplicates
    times = [p.time_beats for p in points]
    if times != sorted(set(times)) or len(set(times)) != len(times):
        raise MixAgentOutputError(
            f"{where}.points time_beats must be strictly ascending (no duplicates, "
            f"no out-of-order). Got time_beats: {times}"
        )

    # #3 — Eq8 target_param requires target_band_index for band-specific params
    eq8_band_specific_params = {"Gain", "Frequency", "Q"}
    if target_device == "Eq8" and target_param in eq8_band_specific_params:
        if target_band_index is None:
            raise MixAgentOutputError(
                f"{where}.target_device='Eq8' AND target_param={target_param!r} "
                f"requires target_band_index (in [0, 7]) — band-specific param "
                f"on a per-band Eq8 architecture."
            )

    # #4 — Non-Eq8 device must NOT have target_band_index set
    if target_device != "Eq8" and target_band_index is not None:
        raise MixAgentOutputError(
            f"{where}.target_device={target_device!r} (not Eq8) but "
            f"target_band_index={target_band_index} is set. band_index only "
            f"applies to Eq8 devices."
        )

    # #5 — mastering_master_bus purpose requires target_track == MASTER_TRACK_NAME
    if purpose == "mastering_master_bus" and target_track != MASTER_TRACK_NAME:
        raise MixAgentOutputError(
            f"{where}.purpose='mastering_master_bus' requires target_track="
            f"{MASTER_TRACK_NAME!r} (got {target_track!r}). Master bus envelopes "
            f"address only the master track."
        )

    # #6 — corrective_per_section purpose requires non-empty sections
    if purpose == "corrective_per_section" and not sections:
        raise MixAgentOutputError(
            f"{where}.purpose='corrective_per_section' requires non-empty "
            f"sections tuple (which Sections Timeline indices the envelope "
            f"applies to). Without section anchoring, envelope is ambiguous."
        )

    # #7 — depth-light : rationale ≥ 50 chars + ≥ 1 cite
    if len(rationale) < 50:
        raise MixAgentOutputError(
            f"{where}.rationale too short ({len(rationale)} chars, need ≥ 50). "
            f"Untraced automation envelope = stub : Tier B automation-writer "
            f"can't justify the envelope to safety-guardian."
        )
    if not inspired_by:
        raise MixAgentOutputError(
            f"{where}.inspired_by must contain at least one citation. "
            f"Cite the Tier A decision being made dynamic OR the section-driven "
            f"signal that justifies the envelope (Sections Timeline + "
            f"audio_metrics evidence)."
        )

    return AutomationEnvelope(
        purpose=purpose,
        target_track=target_track,
        target_device=target_device,
        target_param=target_param,
        target_device_instance=target_device_instance,
        target_band_index=target_band_index,
        points=points,
        sections=sections,
        rationale=rationale,
        inspired_by=inspired_by,
    )


def parse_automation_decision(
    payload: Mapping[str, Any],
) -> MixDecision[AutomationDecision]:
    """Parse an automation-engineer payload into a MixDecision.

    Expected shape (schema 1.0) :
        {
          "schema_version": "1.0",
          "automation": {
            "envelopes": [
              {
                "purpose": str ∈ VALID_AUTOMATION_PURPOSES,
                "target_track": str (TrackInfo.name OR "Master"),
                "target_device": str ∈ VALID_AUTOMATION_TARGET_DEVICES,
                "target_param": str (device parameter name),
                "target_device_instance": int (default 0),
                "target_band_index": Optional[int ∈ [0, 7]] (Eq8 only),
                "points": [{bar, value}, ...] (≥ 3, bar-ascending strict),
                "sections": [int, ...] (required for corrective_per_section),
                "rationale": str (≥ 50 chars),
                "inspired_by": [{kind, path, excerpt}, ...] (≥ 1)
              },
              ...
            ]
          },
          "cited_by": [...],
          "rationale": str,
          "confidence": float (0..1)
        }

    Or a refusal: {"error": "...", "details": "..."}

    Strict on output : 8 cross-field checks (point count + ordering, Eq8
    band_index requirements, mastering target_track requirement, corrective
    sections requirement, depth-light) + duplicate-key check across envelopes.
    """
    envelope_meta = _parse_envelope(
        payload, supported_versions=SUPPORTED_AUTOMATION_SCHEMA_VERSIONS
    )

    auto_dict = _require(payload, "automation", where="root")
    if not isinstance(auto_dict, Mapping):
        raise MixAgentOutputError(
            f"automation: expected object, got {type(auto_dict).__name__}"
        )

    envelopes_raw = _coerce_list(
        auto_dict.get("envelopes", []), where="automation.envelopes"
    )
    envelopes = tuple(
        _parse_automation_envelope(e, where=f"automation.envelopes[{i}]")
        for i, e in enumerate(envelopes_raw)
    )

    # #8 — Cross-correction duplicate check : (track, device, instance, param,
    # band_index) must be unique across envelopes (Tier B would have collision).
    seen_keys: set[tuple] = set()
    for i, env in enumerate(envelopes):
        key = (
            env.target_track,
            env.target_device,
            env.target_device_instance,
            env.target_param,
            env.target_band_index,
        )
        if key in seen_keys:
            raise MixAgentOutputError(
                f"automation.envelopes[{i}]: duplicate envelope on "
                f"(track={env.target_track!r}, device={env.target_device!r}, "
                f"instance={env.target_device_instance}, "
                f"param={env.target_param!r}, "
                f"band_index={env.target_band_index}). "
                f"Tier B automation-writer would collide ; merge or remove."
            )
        seen_keys.add(key)

    decision_value = AutomationDecision(envelopes=envelopes)
    return MixDecision(value=decision_value, lane="automation", **envelope_meta)


def parse_automation_decision_from_response(
    text: str,
) -> MixDecision[AutomationDecision]:
    """End-to-end: raw LLM response → MixDecision[AutomationDecision]."""
    return parse_automation_decision(extract_json_payload(text))


# ============================================================================
# Mastering lane parser — Phase 4.9
# ============================================================================
#
# Discriminator-based : MasterMove.type selects which subset of fields
# applies. Cross-field checks enforce coherence between type / device /
# chain_position / value fields.


# Numeric value-bearing fields per type (used for "extra fields not allowed
# for this type" check, mirroring spatial _SPATIAL_VALUE_FIELD_SPEC).
_MASTER_VALUE_FIELDS_BY_TYPE: dict[str, frozenset[str]] = {
    "limiter_target": frozenset({"target_lufs_i", "ceiling_dbtp",
                                  "lookahead_ms", "gain_drive_db"}),
    "glue_compression": frozenset({"ratio", "threshold_db", "attack_ms",
                                    "release_ms", "gr_target_db", "makeup_db"}),
    "master_eq_band": frozenset({"band_type", "center_hz", "q", "gain_db",
                                  "slope_db_per_oct", "processing_mode"}),
    "stereo_enhance": frozenset({"width", "mid_side_balance",
                                  "bass_mono_freq_hz"}),
    "saturation_color": frozenset({"drive_pct", "saturation_type",
                                    "dry_wet", "output_db"}),
    "bus_glue": frozenset({"ratio", "threshold_db", "attack_ms",
                            "release_ms", "gr_target_db", "makeup_db"}),
}

_MASTER_ALL_VALUE_FIELDS: frozenset[str] = frozenset({
    "target_lufs_i", "ceiling_dbtp", "lookahead_ms", "gain_drive_db",
    "ratio", "threshold_db", "attack_ms", "release_ms",
    "gr_target_db", "makeup_db",
    "band_type", "center_hz", "q", "gain_db", "slope_db_per_oct",
    "processing_mode",
    "width", "mid_side_balance", "bass_mono_freq_hz",
    "drive_pct", "saturation_type", "dry_wet", "output_db",
})


def _parse_master_move(item: Any, *, where: str) -> MasterMove:
    if not isinstance(item, Mapping):
        raise MixAgentOutputError(
            f"{where}: expected object, got {type(item).__name__}"
        )

    # === Discriminator + targeting ===
    move_type = _coerce_str(
        _require(item, "type", where=where), where=f"{where}.type"
    ).strip()
    if move_type not in VALID_MASTER_MOVE_TYPES:
        raise MixAgentOutputError(
            f"{where}.type={move_type!r} not in {sorted(VALID_MASTER_MOVE_TYPES)}"
        )

    target_track = _coerce_str(
        _require(item, "target_track", where=where),
        where=f"{where}.target_track",
    ).strip()
    if not target_track:
        raise MixAgentOutputError(f"{where}.target_track must be non-empty")

    device = _coerce_str(
        _require(item, "device", where=where), where=f"{where}.device"
    ).strip()
    allowed_devices = MASTER_DEVICES_BY_TYPE[move_type]
    if device not in allowed_devices:
        raise MixAgentOutputError(
            f"{where}.device={device!r} not allowed for type={move_type!r}. "
            f"Allowed: {sorted(allowed_devices)}"
        )

    chain_position = _coerce_str(
        item.get("chain_position", "default"),
        where=f"{where}.chain_position",
    ).strip()
    if not chain_position:
        chain_position = "default"
    if chain_position not in VALID_MASTER_CHAIN_POSITIONS:
        raise MixAgentOutputError(
            f"{where}.chain_position={chain_position!r} not in "
            f"{sorted(VALID_MASTER_CHAIN_POSITIONS)}"
        )
    allowed_positions = MASTER_CHAIN_POSITION_BY_TYPE[move_type]
    if chain_position not in allowed_positions:
        raise MixAgentOutputError(
            f"{where}.chain_position={chain_position!r} not allowed for "
            f"type={move_type!r}. Allowed: {sorted(allowed_positions)}"
        )

    rationale = _coerce_str(item.get("rationale", ""))
    inspired_by_raw = _coerce_list(
        item.get("inspired_by", []), where=f"{where}.inspired_by"
    )
    inspired_by = _parse_citations(inspired_by_raw, where=f"{where}.inspired_by")

    # === Numeric / categorical fields (read all, validate presence below) ===
    target_lufs_i = _coerce_optional_float_in_range(
        item.get("target_lufs_i"), where=f"{where}.target_lufs_i",
        lo=MASTER_LUFS_MIN, hi=MASTER_LUFS_MAX, unit="LUFS",
    )
    ceiling_dbtp = _coerce_optional_float_in_range(
        item.get("ceiling_dbtp"), where=f"{where}.ceiling_dbtp",
        lo=MASTER_CEILING_MIN_DBTP, hi=MASTER_CEILING_MAX_DBTP, unit="dBTP",
    )
    lookahead_ms = _coerce_optional_float_in_range(
        item.get("lookahead_ms"), where=f"{where}.lookahead_ms",
        lo=0.0, hi=10.0, unit="ms",
    )
    gain_drive_db = _coerce_optional_float_in_range(
        item.get("gain_drive_db"), where=f"{where}.gain_drive_db",
        lo=-12.0, hi=24.0, unit="dB",
    )

    ratio = _coerce_optional_float_in_range(
        item.get("ratio"), where=f"{where}.ratio",
        lo=MASTER_GLUE_RATIO_MIN, hi=MASTER_GLUE_RATIO_MAX, unit=":1",
    )
    threshold_db = _coerce_optional_float_in_range(
        item.get("threshold_db"), where=f"{where}.threshold_db",
        lo=DYN_THRESHOLD_MIN_DB, hi=DYN_THRESHOLD_MAX_DB, unit="dB",
    )
    attack_ms = _coerce_optional_float_in_range(
        item.get("attack_ms"), where=f"{where}.attack_ms",
        lo=DYN_ATTACK_MIN_MS, hi=DYN_ATTACK_MAX_MS, unit="ms",
    )
    release_ms = _coerce_optional_float_in_range(
        item.get("release_ms"), where=f"{where}.release_ms",
        lo=DYN_RELEASE_MIN_MS, hi=DYN_RELEASE_MAX_MS, unit="ms",
    )
    gr_target_db = _coerce_optional_float_in_range(
        item.get("gr_target_db"), where=f"{where}.gr_target_db",
        lo=MASTER_GLUE_GR_TARGET_MIN_DB, hi=MASTER_GLUE_GR_TARGET_MAX_DB, unit="dB",
    )
    makeup_db = _coerce_optional_float_in_range(
        item.get("makeup_db"), where=f"{where}.makeup_db",
        lo=DYN_MAKEUP_MIN_DB, hi=DYN_MAKEUP_MAX_DB, unit="dB",
    )

    band_type_raw = item.get("band_type")
    band_type = (
        None if band_type_raw is None or band_type_raw == ""
        else _coerce_str(band_type_raw, where=f"{where}.band_type").strip()
    )
    if band_type is not None and band_type not in VALID_EQ_BAND_TYPES:
        raise MixAgentOutputError(
            f"{where}.band_type={band_type!r} not in {sorted(VALID_EQ_BAND_TYPES)}"
        )

    center_hz = _coerce_optional_float_in_range(
        item.get("center_hz"), where=f"{where}.center_hz",
        lo=EQ_FREQ_MIN_HZ, hi=EQ_FREQ_MAX_HZ, unit="Hz",
    )
    q = _coerce_optional_float_in_range(
        item.get("q"), where=f"{where}.q",
        lo=EQ_Q_MIN, hi=EQ_Q_MAX, unit="(Q)",
    )
    gain_db = _coerce_optional_float_in_range(
        item.get("gain_db"), where=f"{where}.gain_db",
        lo=MASTER_EQ_GAIN_MIN_DB, hi=MASTER_EQ_GAIN_MAX_DB, unit="dB",
    )

    slope_raw = item.get("slope_db_per_oct")
    slope_db_per_oct: Optional[float] = None
    if slope_raw is not None:
        slope_db_per_oct = _coerce_float(slope_raw, where=f"{where}.slope_db_per_oct")
        if slope_db_per_oct not in VALID_FILTER_SLOPES_DB_PER_OCT:
            raise MixAgentOutputError(
                f"{where}.slope_db_per_oct={slope_db_per_oct} not in "
                f"{sorted(VALID_FILTER_SLOPES_DB_PER_OCT)}"
            )

    processing_mode_raw = item.get("processing_mode")
    processing_mode = (
        None if processing_mode_raw is None or processing_mode_raw == ""
        else _coerce_str(processing_mode_raw, where=f"{where}.processing_mode").strip()
    )
    if processing_mode is not None and processing_mode not in VALID_PROCESSING_MODES:
        raise MixAgentOutputError(
            f"{where}.processing_mode={processing_mode!r} not in "
            f"{sorted(VALID_PROCESSING_MODES)}"
        )

    width = _coerce_optional_float_in_range(
        item.get("width"), where=f"{where}.width",
        lo=MASTER_STEREO_WIDTH_MIN, hi=MASTER_STEREO_WIDTH_MAX, unit="(width)",
    )
    mid_side_balance = _coerce_optional_float_in_range(
        item.get("mid_side_balance"), where=f"{where}.mid_side_balance",
        lo=MS_BALANCE_MIN, hi=MS_BALANCE_MAX, unit="(MS)",
    )
    bass_mono_freq_hz = _coerce_optional_float_in_range(
        item.get("bass_mono_freq_hz"), where=f"{where}.bass_mono_freq_hz",
        lo=MASTER_BASS_MONO_FREQ_MIN_HZ, hi=MASTER_BASS_MONO_FREQ_MAX_HZ, unit="Hz",
    )

    drive_pct = _coerce_optional_float_in_range(
        item.get("drive_pct"), where=f"{where}.drive_pct",
        lo=MASTER_SATURATION_DRIVE_MIN_PCT, hi=MASTER_SATURATION_DRIVE_MAX_PCT,
        unit="%",
    )
    saturation_type_raw = item.get("saturation_type")
    saturation_type = (
        None if saturation_type_raw is None or saturation_type_raw == ""
        else _coerce_str(saturation_type_raw, where=f"{where}.saturation_type").strip()
    )
    if saturation_type is not None and saturation_type not in VALID_SATURATION_TYPES:
        raise MixAgentOutputError(
            f"{where}.saturation_type={saturation_type!r} not in "
            f"{sorted(VALID_SATURATION_TYPES)}"
        )

    dry_wet = _coerce_optional_float_in_range(
        item.get("dry_wet"), where=f"{where}.dry_wet",
        lo=DYN_DRY_WET_MIN, hi=DYN_DRY_WET_MAX, unit="(0..1)",
    )
    output_db = _coerce_optional_float_in_range(
        item.get("output_db"), where=f"{where}.output_db",
        lo=DYN_MAKEUP_MIN_DB, hi=DYN_MAKEUP_MAX_DB, unit="dB",
    )

    # ------------------------------------------------------------------
    # Cross-field checks (12 numbered)
    # ------------------------------------------------------------------

    # #1 — target_track : Master constant for all types except bus_glue
    if move_type != "bus_glue" and target_track != MASTER_TRACK_NAME:
        raise MixAgentOutputError(
            f"{where}.target_track={target_track!r} but type={move_type!r} "
            f"requires target_track={MASTER_TRACK_NAME!r}. "
            f"Only type='bus_glue' targets sub-bus tracks."
        )
    if move_type == "bus_glue" and target_track == MASTER_TRACK_NAME:
        raise MixAgentOutputError(
            f"{where}.target_track={MASTER_TRACK_NAME!r} but type='bus_glue' "
            f"targets sub-bus (Group) tracks ; use type='glue_compression' "
            f"for master bus."
        )

    # #2 — limiter_target requires target_lufs_i AND ceiling_dbtp
    if move_type == "limiter_target":
        if target_lufs_i is None:
            raise MixAgentOutputError(
                f"{where}.type='limiter_target' requires target_lufs_i field "
                f"(in [{MASTER_LUFS_MIN}, {MASTER_LUFS_MAX}] LUFS)."
            )
        if ceiling_dbtp is None:
            raise MixAgentOutputError(
                f"{where}.type='limiter_target' requires ceiling_dbtp field "
                f"(in [{MASTER_CEILING_MIN_DBTP}, {MASTER_CEILING_MAX_DBTP}] dBTP)."
            )

    # #3 — glue_compression / bus_glue require ratio AND threshold_db
    if move_type in ("glue_compression", "bus_glue"):
        if ratio is None:
            raise MixAgentOutputError(
                f"{where}.type={move_type!r} requires ratio field "
                f"(in [{MASTER_GLUE_RATIO_MIN}, {MASTER_GLUE_RATIO_MAX}])."
            )
        if threshold_db is None:
            raise MixAgentOutputError(
                f"{where}.type={move_type!r} requires threshold_db field."
            )

    # #4 — master_eq_band requires band_type, center_hz, q
    if move_type == "master_eq_band":
        if band_type is None:
            raise MixAgentOutputError(
                f"{where}.type='master_eq_band' requires band_type field."
            )
        if center_hz is None:
            raise MixAgentOutputError(
                f"{where}.type='master_eq_band' requires center_hz field."
            )
        if q is None:
            raise MixAgentOutputError(
                f"{where}.type='master_eq_band' requires q field."
            )

    # #5 — band_type/slope coherence (mirror EQBandCorrection rules)
    if move_type == "master_eq_band" and band_type is not None:
        if band_type in {"highpass", "lowpass"} and slope_db_per_oct is None:
            raise MixAgentOutputError(
                f"{where}.band_type={band_type!r} requires slope_db_per_oct "
                f"(in {sorted(VALID_FILTER_SLOPES_DB_PER_OCT)})."
            )
        if (band_type in {"bell", "notch", "low_shelf", "high_shelf"}
                and slope_db_per_oct is not None):
            raise MixAgentOutputError(
                f"{where}.band_type={band_type!r} must NOT have slope_db_per_oct ; "
                f"slope only applies to highpass/lowpass."
            )
        # gain_db meaningful for bell + shelves ; 0.0 acceptable but warn-worthy
        if band_type == "notch" and gain_db is not None and gain_db > -1.0:
            raise MixAgentOutputError(
                f"{where}.band_type='notch' typically uses deep cuts ; "
                f"gain_db={gain_db} > -1.0 dB suggests bell instead."
            )

    # #6 — stereo_enhance requires at least ONE value field
    if move_type == "stereo_enhance":
        if width is None and mid_side_balance is None and bass_mono_freq_hz is None:
            raise MixAgentOutputError(
                f"{where}.type='stereo_enhance' requires at least one of "
                f"(width, mid_side_balance, bass_mono_freq_hz)."
            )
        # No-op identity checks
        if width is not None and width == 1.0:
            raise MixAgentOutputError(
                f"{where}.type='stereo_enhance' but width=1.0 (neutre, no-op). "
                f"Pick a value ≠ 1.0 in [{MASTER_STEREO_WIDTH_MIN}, "
                f"{MASTER_STEREO_WIDTH_MAX}]."
            )
        if mid_side_balance is not None and mid_side_balance == MS_BALANCE_NEUTRAL:
            raise MixAgentOutputError(
                f"{where}.type='stereo_enhance' but mid_side_balance=1.0 (neutre, no-op)."
            )

    # #7 — saturation_color requires drive_pct AND saturation_type
    if move_type == "saturation_color":
        if drive_pct is None:
            raise MixAgentOutputError(
                f"{where}.type='saturation_color' requires drive_pct field "
                f"(in [{MASTER_SATURATION_DRIVE_MIN_PCT}, "
                f"{MASTER_SATURATION_DRIVE_MAX_PCT}] %)."
            )
        if saturation_type is None:
            raise MixAgentOutputError(
                f"{where}.type='saturation_color' requires saturation_type field "
                f"(in {sorted(VALID_SATURATION_TYPES)})."
            )

    # #8 — extra value fields not relevant to this type forbidden
    relevant_fields = _MASTER_VALUE_FIELDS_BY_TYPE[move_type]
    extras: list[str] = []
    for fname in _MASTER_ALL_VALUE_FIELDS - relevant_fields:
        val = locals().get(fname)
        if val is not None:
            extras.append(fname)
    if extras:
        raise MixAgentOutputError(
            f"{where}.type={move_type!r} but extra value fields set : "
            f"{sorted(extras)}. Each type allows only its own fields ; "
            f"leave others null. Allowed for {move_type!r}: {sorted(relevant_fields)}."
        )

    # #9 — depth-light : rationale ≥ 50 chars + ≥ 1 citation
    if len(rationale) < 50:
        raise MixAgentOutputError(
            f"{where}.rationale too short ({len(rationale)} chars, need ≥ 50). "
            f"Untraced master move = stub : Tier B master-bus-configurator "
            f"can't justify the move to safety-guardian."
        )
    if not inspired_by:
        raise MixAgentOutputError(
            f"{where}.inspired_by must contain at least one citation. "
            f"Cite FullMixMetrics, HealthScore breakdown, Anomaly, or user brief."
        )

    return MasterMove(
        type=move_type,
        target_track=target_track,
        device=device,
        chain_position=chain_position,
        rationale=rationale,
        inspired_by=inspired_by,
        target_lufs_i=target_lufs_i,
        ceiling_dbtp=ceiling_dbtp,
        lookahead_ms=lookahead_ms,
        gain_drive_db=gain_drive_db,
        ratio=ratio,
        threshold_db=threshold_db,
        attack_ms=attack_ms,
        release_ms=release_ms,
        gr_target_db=gr_target_db,
        makeup_db=makeup_db,
        band_type=band_type,
        center_hz=center_hz,
        q=q,
        gain_db=gain_db,
        slope_db_per_oct=slope_db_per_oct,
        processing_mode=processing_mode,
        width=width,
        mid_side_balance=mid_side_balance,
        bass_mono_freq_hz=bass_mono_freq_hz,
        drive_pct=drive_pct,
        saturation_type=saturation_type,
        dry_wet=dry_wet,
        output_db=output_db,
    )


def parse_mastering_decision(
    payload: Mapping[str, Any],
) -> MixDecision[MasteringDecision]:
    """Parse a mastering-engineer payload into a MixDecision.

    Phase 4.9 contract :
    - Static-only moves (no envelopes here ; envelopes via automation-engineer)
    - ≤ 1 limiter_target move (cross-field check)
    - Each move : type discriminator + type-specific value fields +
      shared (target_track, device, chain_position, rationale, inspired_by)
    """
    envelope_meta = _parse_envelope(
        payload, supported_versions=SUPPORTED_MASTERING_SCHEMA_VERSIONS
    )

    mastering_dict = _require(payload, "mastering", where="root")
    if not isinstance(mastering_dict, Mapping):
        raise MixAgentOutputError(
            f"mastering: expected object, got {type(mastering_dict).__name__}"
        )

    moves_raw = _coerce_list(
        mastering_dict.get("moves", []), where="mastering.moves"
    )
    moves = tuple(
        _parse_master_move(m, where=f"mastering.moves[{i}]")
        for i, m in enumerate(moves_raw)
    )

    # #10 — at most 1 limiter_target per MasteringDecision
    limiter_count = sum(1 for m in moves if m.type == "limiter_target")
    if limiter_count > 1:
        raise MixAgentOutputError(
            f"mastering.moves: {limiter_count} limiter_target moves found, "
            f"max 1 allowed (single Limiter terminal on master bus)."
        )

    # #11 — duplicate (target_track, device, chain_position) check
    seen_keys: set[tuple] = set()
    for i, m in enumerate(moves):
        key = (m.target_track, m.device, m.chain_position)
        if key in seen_keys:
            raise MixAgentOutputError(
                f"mastering.moves[{i}]: duplicate move on "
                f"(track={m.target_track!r}, device={m.device!r}, "
                f"chain_position={m.chain_position!r}). "
                f"Tier B master-bus-configurator would collide."
            )
        seen_keys.add(key)

    decision_value = MasteringDecision(moves=moves)
    return MixDecision(value=decision_value, lane="mastering", **envelope_meta)


def parse_mastering_decision_from_response(
    text: str,
) -> MixDecision[MasteringDecision]:
    """End-to-end: raw LLM response → MixDecision[MasteringDecision]."""
    return parse_mastering_decision(extract_json_payload(text))


__all__ = [
    "MixAgentOutputError",
    "SUPPORTED_DIAGNOSTIC_SCHEMA_VERSIONS",
    "SUPPORTED_EQ_CORRECTIVE_SCHEMA_VERSIONS",
    "SUPPORTED_DYNAMICS_CORRECTIVE_SCHEMA_VERSIONS",
    "SUPPORTED_ROUTING_SCHEMA_VERSIONS",
    "SUPPORTED_SPATIAL_SCHEMA_VERSIONS",
    "SUPPORTED_CHAIN_SCHEMA_VERSIONS",
    "SUPPORTED_AUTOMATION_SCHEMA_VERSIONS",
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
    # Phase 4.4 — Routing & sidechain re-exports
    "VALID_ROUTING_FIX_TYPES",
    # Phase 4.5 — Stereo & spatial re-exports
    "VALID_SPATIAL_MOVE_TYPES",
    "VALID_SPATIAL_CHAIN_POSITIONS",
    "VALID_PHASE_CHANNELS",
    # Phase 4.6 — Chain build re-exports
    "VALID_CHAIN_DEVICES",
    "VALID_CONSUMES_LANES",
    # Phase 4.8 — Automation re-exports
    "VALID_AUTOMATION_PURPOSES",
    "VALID_AUTOMATION_TARGET_DEVICES",
    # Phase 4.9 — Mastering re-exports
    "SUPPORTED_MASTERING_SCHEMA_VERSIONS",
    "VALID_MASTER_MOVE_TYPES",
    "VALID_MASTER_CHAIN_POSITIONS",
    "VALID_SATURATION_TYPES",
    "extract_json_payload",
    "parse_diagnostic_decision",
    "parse_diagnostic_decision_from_response",
    "parse_eq_corrective_decision",
    "parse_eq_corrective_decision_from_response",
    "parse_dynamics_corrective_decision",
    "parse_dynamics_corrective_decision_from_response",
    "parse_routing_decision",
    "parse_routing_decision_from_response",
    "parse_spatial_decision",
    "parse_spatial_decision_from_response",
    "parse_chain_decision",
    "parse_chain_decision_from_response",
    "parse_automation_decision",
    "parse_automation_decision_from_response",
    "parse_mastering_decision",
    "parse_mastering_decision_from_response",
]
