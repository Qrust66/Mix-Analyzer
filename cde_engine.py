#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cde_engine.py — Correction Diagnostic Engine (Feature 3.6).

The CDE produces structured correction diagnostics for the problems
already measured by Mix Analyzer (conflicts, accumulations, …) and the
TFP roles resolved by Feature 3.5. It does NOT write anything to the
ALS — that is Feature 1's job — and it produces deterministic output
(same inputs → same outputs).

This module is shipped in three sub-commits:

    * B1b (this commit): core dataclasses + masking conflict detector,
      producing CorrectionDiagnostic instances with
      ``primary_correction = None`` and ``fallback_correction = None``.
      The recommendation matrix + protection rules that fill those
      fields come in B1c.
    * B1c: recommendation matrix, fallback table, protection rules,
      JSON dump.
    * B2+: accumulation detector, Excel sheet, richer JSON.

Design invariants:

    1. Enums ``Importance`` / ``Function`` come from :mod:`tfp_parser` —
       never redefined here, to avoid divergence (same rule as the
       ``active_tracks_with_roles`` shared helper, Risque 6).
    2. Zone → representative frequency mapping is centralised in
       ``ZONE_CENTER_HZ``; any consumer generating a freq label goes
       through it. Arithmetic midpoint of the zone edges in Hz — this
       is a display/ID token, not a measurement.
    3. Tracks missing from ``all_tracks_zone_energy`` (MIDI without WAV)
       are skipped silently with a warning log — Risque 7 of the recon.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

from tfp_parser import Function, Importance
from section_detector import get_zone_label

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Version + issue-type vocabulary
# ---------------------------------------------------------------------------

CDE_VERSION = "1.0"

# Issue-type slugs. Short uppercase abbreviations used in diagnostic IDs
# are keyed here too, keeping the slug ↔ abbreviation mapping in a single
# table that downstream consumers (the Excel sheet + JSON dump) can read.
ISSUE_TYPES: Tuple[str, ...] = (
    "masking_conflict",
    "accumulation_risk",
    "resonance_buildup",
    "phase_issue",
    "dynamic_imbalance",
)

_ISSUE_TYPE_ABBR: dict = {
    "masking_conflict":    "CONF",
    "accumulation_risk":   "ACC",
    "resonance_buildup":   "RES",
    "phase_issue":         "PHASE",
    "dynamic_imbalance":   "DYN",
}


# ---------------------------------------------------------------------------
# Zone → representative frequency (arithmetic midpoint, Hz)
# ---------------------------------------------------------------------------
#
# Zones are bands (e.g. Sub = 20-80 Hz) — picking the arithmetic midpoint
# gives a representative integer Hz value that the user recognises when
# reading a diagnostic ID. Any future change to ``section_detector._ZONE_ORDER``
# must be mirrored here, which is why we pin the values explicitly.

ZONE_CENTER_HZ: dict = {
    "sub":        50,     # 20 + 80  / 2
    "low":        165,    # 80 + 250
    "mud":        350,    # 200 + 500
    "body":       525,    # 250 + 800
    "low_mid":    1250,   # 500 + 2000
    "mid":        2500,   # 1000 + 4000
    "presence":   3500,   # 2000 + 5000
    "sibilance":  7500,   # 5000 + 10000
    "air":        15000,  # 10000 + 20000
}


# ---------------------------------------------------------------------------
# Enum-side helpers — human labels used in diagnosis text
# ---------------------------------------------------------------------------

_IMPORTANCE_LABEL_FR: dict = {
    Importance.H: "Hero",
    Importance.S: "Support",
    Importance.A: "Atmos",
}
_FUNCTION_LABEL_FR: dict = {
    Function.R: "Rhythm",
    Function.H: "Harmonic",
    Function.M: "Melodic",
    Function.T: "Textural",
}


# ---------------------------------------------------------------------------
# Dataclasses — see Feature 3.6 spec, section 4
# ---------------------------------------------------------------------------

@dataclass
class ProblemMeasurement:
    """Numeric facts about the problem, extracted from the detectors.

    For a masking conflict, ``frequency_hz`` is the representative midpoint
    of the zone (not an FFT peak); ``peak_db`` is the louder track's energy
    in that zone; ``duration_ratio_in_section`` / ``is_audible_fraction``
    use the minimum presence ratio of the two tracks as a conservative
    "how long does the collision last" proxy.
    """
    frequency_hz: Optional[float]
    peak_db: Optional[float]
    duration_in_section_s: float
    duration_ratio_in_section: float
    is_audible_fraction: float
    severity_score: float
    masking_score: Optional[float] = None


@dataclass
class TFPContext:
    """TFP roles for the tracks involved + their qualitative compatibility.

    ``role_compatibility`` takes one of three values, chosen to match the
    downstream recommendation matrix:

        * ``"conflict"``          — both tracks are Hero (H×H)
        * ``"dominant_support"``  — one Hero vs one non-Hero (H×S, H×A)
        * ``"compatible"``        — no Hero involved (S×S, S×A, A×A)
    """
    track_a_role: Tuple[Importance, Function]
    track_b_role: Optional[Tuple[Importance, Function]]
    role_compatibility: str


@dataclass
class SectionContext:
    """Summary of the section the diagnostic belongs to."""
    section_name: str
    section_duration_s: float
    tracks_active_count: int
    conflicts_in_section: int
    coherence_score: Optional[float]


@dataclass
class CorrectionRecipe:
    """A concrete correction proposal — target track, device, parameters.

    In B1b, detectors produce diagnostics with primary/fallback set to
    ``None``. B1c introduces ``compute_primary_recommendation`` and
    ``compute_fallback_recommendation`` that fill them.
    """
    target_track: str
    device: str
    approach: str
    parameters: dict
    applies_to_sections: List[str]
    rationale: str
    confidence: str


@dataclass
class CorrectionDiagnostic:
    """One diagnostic entry — identification + problem + context +
    (eventually) recommendations.

    ``primary_correction`` / ``fallback_correction`` are ``None`` in
    B1b and populated in B1c. Consumers that read diagnostics generated
    by B1b must tolerate ``None`` there.
    """
    # Identification
    diagnostic_id: str
    timestamp: datetime
    cde_version: str

    # Problem
    track_a: str
    track_b: Optional[str]
    section: Optional[str]
    issue_type: str
    severity: str
    measurement: ProblemMeasurement

    # Context
    tfp_context: TFPContext
    section_context: SectionContext

    # Diagnosis in natural language
    diagnosis_text: str

    # Recommendations — filled in B1c
    primary_correction: Optional[CorrectionRecipe] = None
    fallback_correction: Optional[CorrectionRecipe] = None

    # Qualitative impact — also filled in B1c (stay empty here)
    expected_outcomes: List[str] = field(default_factory=list)
    potential_risks: List[str] = field(default_factory=list)
    verification_steps: List[str] = field(default_factory=list)

    # Application state — defaults proposed
    application_status: str = "proposed"
    rejection_reason: Optional[str] = None
    applied_backup_path: Optional[str] = None

    # Audit
    data_sources: List[str] = field(default_factory=list)
    rules_applied: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Diagnostic ID — human-readable, deterministic
# ---------------------------------------------------------------------------

def _slug(value: str) -> str:
    """Normalize a free-form label to an ID-safe token.

    Uppercase, drop whitespace and a handful of separator characters so
    tokens like ``"Kick 1"`` become ``"KICK1"`` and ``"Sub-Bass"`` becomes
    ``"SUBBASS"``. Non-ASCII is passed through as-is — section names in
    Acid Drops use ASCII in practice, and the goal is a stable ID that
    the user can pronounce, not a strict ASCII-only token.
    """
    if value is None:
        return ""
    cleaned = (
        str(value)
        .strip()
        .upper()
        .replace(" ", "")
        .replace("-", "")
        .replace("/", "")
        .replace("_", "")
    )
    return cleaned


def generate_diagnostic_id(
    issue_type: str,
    section: Optional[str],
    track_a: str,
    track_b: Optional[str],
    frequency_hz: Optional[float],
) -> str:
    """Produce a human-readable, deterministic diagnostic ID.

    Format: ``<TYPE>_[<SECTION>_]<TRACK_A>[_<TRACK_B>][_<FREQ>HZ]``

    Examples:
        * ``generate_diagnostic_id("masking_conflict", "Drop 1",
          "Kick 1", "Sub Bass", 62)`` → ``"CONF_DROP1_KICK1_SUBBASS_62HZ"``
        * ``generate_diagnostic_id("masking_conflict", None,
          "Kick 1", "Sub Bass", 62)`` → ``"CONF_KICK1_SUBBASS_62HZ"``
        * ``generate_diagnostic_id("accumulation_risk", "Chorus 1",
          "T1", None, 247)`` → ``"ACC_CHORUS1_T1_247HZ"``

    Args:
        issue_type: One of :data:`ISSUE_TYPES`. Unknown types fall back
            to the uppercased type string with underscores removed.
        section: Section name. ``None`` → component is omitted (diagnostics
            that span the whole track).
        track_a: Primary track name.
        track_b: Secondary track name or ``None`` (single-track issues
            like resonance or dynamics).
        frequency_hz: Representative frequency (Hz). ``None`` or ``<= 0``
            → the ``<FREQ>HZ`` component is omitted.
    """
    type_abbr = _ISSUE_TYPE_ABBR.get(
        issue_type, _slug(issue_type.replace("_", ""))
    )
    parts: List[str] = [type_abbr]
    if section:
        parts.append(_slug(section))
    parts.append(_slug(track_a))
    if track_b:
        parts.append(_slug(track_b))
    if frequency_hz is not None and frequency_hz > 0:
        parts.append(f"{int(round(frequency_hz))}HZ")
    return "_".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# TFP context builder
# ---------------------------------------------------------------------------

def _role_compatibility(
    role_a: Tuple[Importance, Function],
    role_b: Optional[Tuple[Importance, Function]],
) -> str:
    """Qualitative label describing the two roles' compatibility.

    Single-track diagnostics (``role_b is None``) are tagged
    ``"compatible"`` by default — the field is kept for uniformity with
    conflict diagnostics.
    """
    if role_b is None:
        return "compatible"
    a_imp = role_a[0]
    b_imp = role_b[0]
    if a_imp is Importance.H and b_imp is Importance.H:
        return "conflict"
    if a_imp is Importance.H or b_imp is Importance.H:
        return "dominant_support"
    return "compatible"


def compute_tfp_context(
    conflict: dict,
    section,
) -> TFPContext:
    """Build a :class:`TFPContext` for a conflict using ``section.track_roles``.

    Tracks missing from ``section.track_roles`` fall back to the
    tfp_parser default (S/R) — matches the convention used by
    :mod:`tfp_coherence` (R2 of the Feature 3.5 spec).

    Args:
        conflict: One entry of ``section.conflicts``; must carry
            ``track_a`` and ``track_b``.
        section: The :class:`section_detector.Section` the conflict
            belongs to.
    """
    from tfp_parser import DEFAULT_ROLE

    track_roles = getattr(section, "track_roles", {}) or {}
    role_a = track_roles.get(conflict["track_a"], DEFAULT_ROLE)
    role_b = track_roles.get(conflict["track_b"], DEFAULT_ROLE)
    return TFPContext(
        track_a_role=role_a,
        track_b_role=role_b,
        role_compatibility=_role_compatibility(role_a, role_b),
    )


# ---------------------------------------------------------------------------
# Section context builder
# ---------------------------------------------------------------------------

def _section_context(section) -> SectionContext:
    """Build a :class:`SectionContext` from the Section instance.

    ``coherence_score`` pulls from ``section.tfp_summary`` when present
    (populated by Feature 3.5); otherwise ``None`` — the CDE does not
    recompute coherence on its own.
    """
    tfp_summary = getattr(section, "tfp_summary", None) or {}
    coherence = tfp_summary.get("score") if isinstance(tfp_summary, dict) else None
    conflicts = getattr(section, "conflicts", []) or []
    tracks_active = getattr(section, "tracks_active", []) or []
    return SectionContext(
        section_name=getattr(section, "name", ""),
        section_duration_s=float(
            getattr(section, "end_seconds", 0.0)
            - getattr(section, "start_seconds", 0.0)
        ),
        tracks_active_count=len(tracks_active),
        conflicts_in_section=len(conflicts),
        coherence_score=coherence,
    )


# ---------------------------------------------------------------------------
# Masking-conflict → ProblemMeasurement
# ---------------------------------------------------------------------------

def _measurement_from_conflict(conflict: dict, section) -> ProblemMeasurement:
    """Translate a conflict dict into a :class:`ProblemMeasurement`.

    The conflict dict is zone-level (no single FFT frequency), so
    ``frequency_hz`` is the zone midpoint — a stable display token, not
    a measurement. ``duration_ratio_in_section`` uses the minimum
    presence ratio of the two tracks in the zone, which is the most
    pessimistic realistic estimate of how long the collision lasts.
    """
    zone = conflict["zone"]
    track_presence = getattr(section, "track_presence", {}) or {}
    pa = track_presence.get(conflict["track_a"], {}).get(zone, 0.0)
    pb = track_presence.get(conflict["track_b"], {}).get(zone, 0.0)
    min_presence = min(float(pa), float(pb))

    duration_s = float(
        getattr(section, "end_seconds", 0.0)
        - getattr(section, "start_seconds", 0.0)
    )

    return ProblemMeasurement(
        frequency_hz=float(ZONE_CENTER_HZ.get(zone, 0)) or None,
        peak_db=float(max(conflict["energy_a"], conflict["energy_b"])),
        duration_in_section_s=duration_s,
        duration_ratio_in_section=min_presence,
        is_audible_fraction=min_presence,
        severity_score=float(conflict["score"]),
        masking_score=float(conflict["score"]),
    )


# ---------------------------------------------------------------------------
# Diagnosis text — French, single paragraph
# ---------------------------------------------------------------------------

def _diagnosis_text_masking(
    track_a: str,
    track_b: str,
    role_a: Tuple[Importance, Function],
    role_b: Tuple[Importance, Function],
    zone: str,
    freq_hz: float,
    severity: str,
    section_name: str,
) -> str:
    """Build the natural-language explanation for a masking conflict."""
    sev_label = {"critical": "critique", "moderate": "modéré"}.get(severity, severity)
    role_a_str = (
        f"{_IMPORTANCE_LABEL_FR[role_a[0]]} {_FUNCTION_LABEL_FR[role_a[1]]}"
    )
    role_b_str = (
        f"{_IMPORTANCE_LABEL_FR[role_b[0]]} {_FUNCTION_LABEL_FR[role_b[1]]}"
    )
    return (
        f"Conflit {sev_label} autour de {int(round(freq_hz))} Hz entre "
        f"{track_a} ({role_a_str}) et {track_b} ({role_b_str}) dans "
        f"{section_name}. Les deux tracks occupent la même bande "
        f"spectrale ({get_zone_label(zone)}), créant du masking."
    )


# ---------------------------------------------------------------------------
# Public API — masking detector
# ---------------------------------------------------------------------------

def detect_masking_conflicts(
    section,
    all_tracks_zone_energy: Optional[dict] = None,
) -> List[CorrectionDiagnostic]:
    """Generate one :class:`CorrectionDiagnostic` per conflict in ``section``.

    Consumes ``section.conflicts`` (populated by B1a's persistence step
    in ``build_sections_timeline_sheet``). The CDE does not recompute
    conflicts — running ``detect_conflicts_in_section`` twice would be
    wasteful and risks drift.

    Tracks missing from ``all_tracks_zone_energy`` (MIDI instruments
    that were never bounced to WAV) are skipped with a warning log —
    Risque 7 of the F3.6 recon.

    In B1b the returned diagnostics carry ``primary_correction = None``
    and ``fallback_correction = None``; the recommendation matrix +
    protection rules that fill them ship in B1c.

    Args:
        section: A :class:`section_detector.Section` whose
            ``conflicts`` / ``track_roles`` / ``track_presence`` /
            ``tracks_active`` / ``tfp_summary`` fields were populated by
            :func:`section_detector.build_sections_timeline_sheet`.
        all_tracks_zone_energy: Optional ``{track_name: zone_arrays}``
            map — used only to skip diagnostics for MIDI-only tracks.
            When ``None``, all conflicts are processed regardless.

    Returns:
        Diagnostics in the same order as ``section.conflicts``.
    """
    conflicts = getattr(section, "conflicts", None) or []
    if not conflicts:
        return []

    section_ctx = _section_context(section)
    now = datetime.now()
    diagnostics: List[CorrectionDiagnostic] = []

    for conflict in conflicts:
        track_a = conflict["track_a"]
        track_b = conflict["track_b"]

        # Risque 7 — skip MIDI-without-WAV silently.
        if all_tracks_zone_energy is not None:
            if track_a not in all_tracks_zone_energy or track_b not in all_tracks_zone_energy:
                logger.warning(
                    "CDE: skipping conflict %s vs %s — track missing from WAV map",
                    track_a, track_b,
                )
                continue

        tfp_ctx = compute_tfp_context(conflict, section)
        measurement = _measurement_from_conflict(conflict, section)

        freq_hz = measurement.frequency_hz or 0.0
        diag_id = generate_diagnostic_id(
            issue_type="masking_conflict",
            section=section_ctx.section_name,
            track_a=track_a,
            track_b=track_b,
            frequency_hz=freq_hz,
        )
        diagnosis_text = _diagnosis_text_masking(
            track_a=track_a,
            track_b=track_b,
            role_a=tfp_ctx.track_a_role,
            role_b=tfp_ctx.track_b_role,
            zone=conflict["zone"],
            freq_hz=freq_hz,
            severity=conflict["severity"],
            section_name=section_ctx.section_name,
        )

        diagnostics.append(
            CorrectionDiagnostic(
                diagnostic_id=diag_id,
                timestamp=now,
                cde_version=CDE_VERSION,
                track_a=track_a,
                track_b=track_b,
                section=section_ctx.section_name,
                issue_type="masking_conflict",
                severity=conflict["severity"],
                measurement=measurement,
                tfp_context=tfp_ctx,
                section_context=section_ctx,
                diagnosis_text=diagnosis_text,
                primary_correction=None,   # filled in B1c
                fallback_correction=None,  # filled in B1c
                data_sources=[
                    "Sections Timeline:CONFLITS DE FREQUENCES",
                    "Section.track_roles (Feature 3.5)",
                ],
                rules_applied=[],  # filled in B1c
            )
        )

    return diagnostics
