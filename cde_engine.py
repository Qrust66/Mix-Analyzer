#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Correction Diagnostic Engine — v2.7.0 — Feature 3.6 (B1 complete).

The CDE produces structured correction diagnostics for the problems
already measured by Mix Analyzer (conflicts, accumulations, …) and the
TFP roles resolved by Feature 3.5. It does NOT write anything to the
ALS — that is Feature 1's job — and it produces deterministic output
(same inputs → same outputs).

This module is shipped in three sub-commits:

    * B1b: core dataclasses + masking conflict detector, producing
      CorrectionDiagnostic instances with ``primary_correction = None``
      and ``fallback_correction = None``.
    * B1c1: recommendation matrix + fallback table.
    * B1c2a: §6.3 protection rules (signature frequency, sub integrity,
      role-appropriate max cut) + ``apply_protection_rules`` orchestrator
      + coherence-invariance test against tfp_coherence.
    * B1c2b (this commit): qualitative-impact templates
      (``expected_outcomes`` / ``potential_risks`` / ``verification_steps``)
      and ``dump_diagnostics_to_json``.
    * B2+: accumulation detector, Excel sheet, richer JSON with summary.

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

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
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
# Track-name display cleanup
# ---------------------------------------------------------------------------
#
# Track names arriving here come from the WAV filenames (e.g.
# ``"Acid_Drops [H_R] Kick 1.wav"``). They carry three layers of noise
# that hurt readability in diagnostic IDs, diagnosis text and outcome
# templates:
#
#   1. the ``.wav`` extension
#   2. the TFP role prefix  ``[H/R]`` / ``[H_R]`` / ``[H R]`` (Ableton
#      substitutes ``/`` with ``_`` when bouncing, ``[H R]`` is a rarer
#      hand-written form — we accept all three)
#   3. the project stem prepended by the bouncer (e.g. ``"Acid_Drops"``)
#
# :func:`_clean_track_display_name` strips all three. The original
# name is NEVER mutated on the diagnostic; cleanup is display-layer
# only (IDs, diagnosis text, outcome template substitutions).

# Match a TFP prefix anywhere in the string:
#   "[H/R]", "[H_R]", "[H R]", lowercase variants, with optional spaces.
_TFP_PREFIX_ANYWHERE_RE = re.compile(
    r"\[\s*[HSAhsa]\s*[/_ ]\s*[RHMTrhmt]\s*\]\s*"
)
_WHITESPACE_COLLAPSE_RE = re.compile(r"\s+")


def _clean_track_display_name(
    raw_name: Optional[str],
    project_stem: Optional[str] = None,
) -> str:
    """Return a human-friendly display name for ``raw_name``.

    Applies three cleanups:

        1. Strip ``.wav`` extension (case-insensitive).
        2. Strip ``project_stem`` if it prefixes the name — accepting
           the raw stem, the underscore variant and the space variant.
        3. Strip any TFP role prefix (``[H/R]``, ``[H_R]``, ``[H R]``).

    Whitespace is collapsed and trimmed at the end. Already-clean names
    like ``"Kick 1"`` or ``"Sub Bass"`` pass through unchanged.
    """
    if not isinstance(raw_name, str):
        return ""
    s = raw_name.strip()
    if not s:
        return ""

    # (1) Strip .wav extension, case-insensitive.
    if s.lower().endswith(".wav"):
        s = s[:-4]

    # (2) Strip the project stem when it prefixes the name. We try the
    # stem verbatim and the two common separator substitutions (Ableton
    # names can mix spaces and underscores freely).
    if project_stem:
        stem_raw = project_stem.strip()
        variants = {stem_raw,
                    stem_raw.replace("_", " "),
                    stem_raw.replace(" ", "_")}
        for variant in variants:
            if variant and s.startswith(variant):
                s = s[len(variant):].lstrip(" _-")
                break

    # (3) Strip any TFP prefix anywhere — one pass is enough.
    s = _TFP_PREFIX_ANYWHERE_RE.sub(" ", s)

    # Collapse multi-space + trim.
    s = _WHITESPACE_COLLAPSE_RE.sub(" ", s).strip()
    return s


def infer_project_stem(track_names) -> str:
    """Guess the bouncer's project-name prefix shared by every track.

    Uses :func:`os.path.commonprefix` on the provided names and keeps
    only the portion before the first ``[`` — i.e. the start of the
    TFP role prefix. We intentionally require the TFP bracket to be in
    the common prefix: without it, a shared word across track names
    (``"Kick 1"``, ``"Kick 2"``) would be mistaken for a project stem
    and wreck the display name. Names without TFP prefixes therefore
    get no stem stripped — they likely do not need any cleanup anyway.

    The extracted stem is accepted only when it ends on a clean
    boundary (``" "`` or ``"_"``).

    Callers pass the full set of WAV track names
    (``all_tracks_zone_energy.keys()``). Returns ``""`` when fewer
    than 2 names are given or no reliable stem can be detected.
    """
    names = list(track_names or [])
    if len(names) < 2:
        return ""

    common = os.path.commonprefix(names)
    bracket_idx = common.find("[")
    if bracket_idx <= 0:
        return ""
    candidate = common[:bracket_idx]

    if candidate and candidate[-1] in " _":
        return candidate.rstrip(" _-")
    return ""


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
    project_stem: Optional[str] = None,
) -> str:
    """Build the natural-language explanation for a masking conflict.

    Track names are passed through :func:`_clean_track_display_name`
    so the user-facing sentence shows ``"Kick 1"`` instead of
    ``"Acid_Drops [H_R] Kick 1.wav"``.
    """
    sev_label = {"critical": "critique", "moderate": "modéré"}.get(severity, severity)
    role_a_str = (
        f"{_IMPORTANCE_LABEL_FR[role_a[0]]} {_FUNCTION_LABEL_FR[role_a[1]]}"
    )
    role_b_str = (
        f"{_IMPORTANCE_LABEL_FR[role_b[0]]} {_FUNCTION_LABEL_FR[role_b[1]]}"
    )
    a_clean = _clean_track_display_name(track_a, project_stem) or track_a
    b_clean = _clean_track_display_name(track_b, project_stem) or track_b
    return (
        f"Conflit {sev_label} autour de {int(round(freq_hz))} Hz entre "
        f"{a_clean} ({role_a_str}) et {b_clean} ({role_b_str}) dans "
        f"{section_name}. Les deux tracks occupent la même bande "
        f"spectrale ({get_zone_label(zone)}), créant du masking."
    )


# ---------------------------------------------------------------------------
# Recommendation matrix — primary correction per TFP role pair
# ---------------------------------------------------------------------------
#
# Encodes §6.1 of the Feature 3.6 spec:
#
#   Role A | Role B | Primary recommendation
#   -------|--------|------------------------
#   H×H    | reciprocal_cuts (light cut on each in the shared zone)
#   H×S    | sidechain (H trigger, S ducked)
#   H×A    | zone cut on A
#   S×S    | zone cut on the alphabetically later track (the "secondary")
#   S×A    | zone cut on A
#   A×A    | no action
#
# Exception: H/R × H/H → sidechain the H/H (typically a bass) on the H/R
# (typically a kick), not reciprocal_cuts.
#
# Devices used:
#   * ``"EQ8 — Peak Resonance"`` for every zone-cut approach
#   * ``"Kickstart 2"`` for sidechain (matches the codebase's default
#     sidechain device — see eq8_automation / als_utils conventions).
#
# Rule names returned in CorrectionDiagnostic.rules_applied — short
# underscore-cased slugs, easy to grep for in the Excel sheet and JSON.

RULE_HH_RECIPROCAL = "hero_vs_hero_reciprocal_cuts_rule"
RULE_HR_HH_SIDECHAIN = "hero_rhythm_vs_hero_harmonic_sidechain_rule"
RULE_HS_SIDECHAIN = "hero_vs_support_sidechain_rule"
RULE_HA_ZONE_CUT = "hero_vs_atmos_zone_cut_rule"
RULE_SS_ZONE_CUT = "support_vs_support_secondary_cut_rule"
RULE_SA_ZONE_CUT = "support_vs_atmos_zone_cut_rule"
RULE_AA_NO_ACTION = "atmos_pair_no_action_rule"


def _sections_list(diagnostic: "CorrectionDiagnostic") -> List[str]:
    """Return a single-element list with the diagnostic's section, or []."""
    return [diagnostic.section] if diagnostic.section else []


def _make_reciprocal_cuts(diagnostic: "CorrectionDiagnostic") -> CorrectionRecipe:
    """H×H primary — a small cut on each track in the shared zone."""
    freq = diagnostic.measurement.frequency_hz
    sections = _sections_list(diagnostic)
    return CorrectionRecipe(
        target_track=diagnostic.track_a,
        device="EQ8 — Peak Resonance",
        approach="reciprocal_cuts",
        parameters={
            "frequency_hz": freq,
            "gain_db": -2.0,
            "q": 3.0,
            "secondary_cut": {
                "track": diagnostic.track_b,
                "frequency_hz": freq,
                "gain_db": -2.0,
                "q": 3.0,
            },
            "active_in_sections": sections,
        },
        applies_to_sections=sections,
        rationale=(
            "Deux tracks Hero se disputent la bande — léger cut "
            "réciproque pour partager l'espace sans qu'aucune des "
            "deux ne domine complètement."
        ),
        confidence="medium",
    )


def _make_sidechain(
    trigger: str,
    target: str,
    diagnostic: "CorrectionDiagnostic",
) -> CorrectionRecipe:
    """H-vs-* primary — sidechain-duck the target from the trigger."""
    sections = _sections_list(diagnostic)
    return CorrectionRecipe(
        target_track=target,
        device="Kickstart 2",
        approach="sidechain",
        parameters={
            "trigger_track": trigger,
            "depth_db": -8.0,
            "release_ms": 150,
            "active_in_sections": sections,
        },
        applies_to_sections=sections,
        rationale=(
            f"{trigger} conserve sa prééminence ; {target} est ducké "
            "à chaque frappe pour lui laisser l'espace rythmique."
        ),
        confidence="high",
    )


def _make_zone_cut(
    target: str,
    diagnostic: "CorrectionDiagnostic",
    gain_db: float = -3.0,
    q: float = 4.0,
    approach: str = "static_dip",
) -> CorrectionRecipe:
    """H/S-vs-* primary — a single EQ8 peak cut on the lower-priority track."""
    sections = _sections_list(diagnostic)
    return CorrectionRecipe(
        target_track=target,
        device="EQ8 — Peak Resonance",
        approach=approach,
        parameters={
            "frequency_hz": diagnostic.measurement.frequency_hz,
            "gain_db": gain_db,
            "q": q,
            "active_in_sections": sections,
        },
        applies_to_sections=sections,
        rationale=(
            f"{target} occupe la zone partagée avec une track de rôle "
            "supérieur — un léger dip statique libère l'espace sans "
            "altérer le reste du spectre."
        ),
        confidence="medium",
    )


def compute_primary_recommendation(
    diagnostic: CorrectionDiagnostic,
) -> Tuple[Optional[CorrectionRecipe], List[str]]:
    """Return the primary :class:`CorrectionRecipe` + rule slugs applied.

    Implements the §6.1 matrix for ``masking_conflict`` diagnostics.
    Returns ``(None, [RULE_AA_NO_ACTION])`` for atmos-vs-atmos pairs,
    matching the spec ("rarely a real problem — leave as is").

    Args:
        diagnostic: A :class:`CorrectionDiagnostic` with ``tfp_context``
            and ``measurement`` populated.

    Returns:
        ``(recipe_or_none, rules_applied)``. ``rules_applied`` always
        contains at least one entry so the audit trail is never empty.
    """
    if diagnostic.issue_type != "masking_conflict":
        return None, []

    role_a = diagnostic.tfp_context.track_a_role
    role_b = diagnostic.tfp_context.track_b_role
    if role_b is None:
        return None, []

    imp_a, fn_a = role_a
    imp_b, fn_b = role_b
    ta, tb = diagnostic.track_a, diagnostic.track_b

    # A × A — no action
    if imp_a is Importance.A and imp_b is Importance.A:
        return None, [RULE_AA_NO_ACTION]

    # H × H — exception first (H/R × H/H → sidechain), else reciprocal
    if imp_a is Importance.H and imp_b is Importance.H:
        if fn_a is Function.R and fn_b is Function.H:
            return (
                _make_sidechain(trigger=ta, target=tb, diagnostic=diagnostic),
                [RULE_HR_HH_SIDECHAIN],
            )
        if fn_a is Function.H and fn_b is Function.R:
            return (
                _make_sidechain(trigger=tb, target=ta, diagnostic=diagnostic),
                [RULE_HR_HH_SIDECHAIN],
            )
        return _make_reciprocal_cuts(diagnostic), [RULE_HH_RECIPROCAL]

    # H vs S — sidechain the Support from the Hero
    if imp_a is Importance.H and imp_b is Importance.S:
        return (
            _make_sidechain(trigger=ta, target=tb, diagnostic=diagnostic),
            [RULE_HS_SIDECHAIN],
        )
    if imp_b is Importance.H and imp_a is Importance.S:
        return (
            _make_sidechain(trigger=tb, target=ta, diagnostic=diagnostic),
            [RULE_HS_SIDECHAIN],
        )

    # H vs A — zone cut on the Atmos track
    if imp_a is Importance.H and imp_b is Importance.A:
        return _make_zone_cut(target=tb, diagnostic=diagnostic), [RULE_HA_ZONE_CUT]
    if imp_b is Importance.H and imp_a is Importance.A:
        return _make_zone_cut(target=ta, diagnostic=diagnostic), [RULE_HA_ZONE_CUT]

    # S × S — cut on the alphabetically later track (the "secondary")
    if imp_a is Importance.S and imp_b is Importance.S:
        target = tb if ta <= tb else ta
        return _make_zone_cut(target=target, diagnostic=diagnostic), [RULE_SS_ZONE_CUT]

    # S × A — zone cut on the Atmos track
    if imp_a is Importance.S and imp_b is Importance.A:
        return _make_zone_cut(target=tb, diagnostic=diagnostic), [RULE_SA_ZONE_CUT]
    if imp_b is Importance.S and imp_a is Importance.A:
        return _make_zone_cut(target=ta, diagnostic=diagnostic), [RULE_SA_ZONE_CUT]

    return None, []


# ---------------------------------------------------------------------------
# Fallback — a conservative alternative to the primary (§6.2)
# ---------------------------------------------------------------------------
#
#   Primary                | Fallback
#   -----------------------|----------------------------------------
#   reciprocal_cuts        | static_dip (cut on a single track)
#   sidechain depth -8 dB  | sidechain depth -4 dB
#   static_dip / musical_dip | musical_dip (wider Q, shallower depth)
#
# ``ms_side_cut → stereo_cut`` from the spec is defined as a plain-dict
# mapping so B4 can reuse it when it introduces phase diagnostics — it
# is not currently produced by the B1c1 primary matrix.

FALLBACK_APPROACH_MAP: dict = {
    "reciprocal_cuts": "static_dip",
    "sidechain":       "sidechain",
    "static_dip":      "musical_dip",
    "musical_dip":     "musical_dip",
    "ms_side_cut":     "stereo_cut",
}


def compute_fallback_recommendation(
    diagnostic: CorrectionDiagnostic,
    primary: Optional[CorrectionRecipe],
) -> Optional[CorrectionRecipe]:
    """Compute a conservative alternative to ``primary`` per §6.2.

    ``primary = None`` (A×A or single-track) → no fallback either.
    Unknown approaches return ``None`` rather than guess — the test
    suite pins every mapping this function produces.
    """
    if primary is None:
        return None

    approach = primary.approach
    sections = primary.applies_to_sections

    if approach == "reciprocal_cuts":
        # Drop the secondary cut, keep a single dip on track_a.
        return CorrectionRecipe(
            target_track=primary.target_track,
            device="EQ8 — Peak Resonance",
            approach="static_dip",
            parameters={
                "frequency_hz": primary.parameters.get("frequency_hz"),
                "gain_db": -1.5,
                "q": 3.0,
                "active_in_sections": sections,
            },
            applies_to_sections=sections,
            rationale=(
                "Cut unique (pas réciproque) — option moins agressive "
                "si le reciprocal_cuts laisse entendre des artefacts."
            ),
            confidence="medium",
        )

    if approach == "sidechain":
        return CorrectionRecipe(
            target_track=primary.target_track,
            device=primary.device,
            approach="sidechain",
            parameters={
                **primary.parameters,
                "depth_db": -4.0,
            },
            applies_to_sections=sections,
            rationale=(
                "Sidechain moitié moins profond (-4 dB) — plus "
                "transparent si le pumping à -8 dB est audible."
            ),
            confidence="medium",
        )

    if approach in ("static_dip", "musical_dip"):
        new_params = dict(primary.parameters)
        # Shallower and wider: gain -1.5 dB min, Q = 2.
        new_params["gain_db"] = min(
            float(primary.parameters.get("gain_db", -3.0)) + 1.5, -1.5
        )
        new_params["q"] = 2.0
        return CorrectionRecipe(
            target_track=primary.target_track,
            device=primary.device,
            approach="musical_dip",
            parameters=new_params,
            applies_to_sections=sections,
            rationale=(
                "Dip plus large et moins profond — alternative plus "
                "musicale si le cut primaire sonne artificiel."
            ),
            confidence="medium",
        )

    # Unknown approach — no fallback rather than guess.
    return None


# ---------------------------------------------------------------------------
# Protection rules (§6.3) — applied after the primary matrix
# ---------------------------------------------------------------------------
#
# Three rules cap or invalidate a recommendation produced by the §6.1
# matrix. They are applied in this strict order:
#
#   R2  Sub integrity (Hero Rhythm): can skip the whole recipe
#   R1  Signature frequency protection: caps gain at -2 dB in dom_band
#   R3  Role-appropriate max cut: caps gain by Importance
#
# R2 skips → the orchestrator stops, caller can try the fallback.
# R1 caps → R3 still runs afterwards. R3 is a final safety net.
#
# All rules target the ``gain_db`` parameter of cut approaches
# (``static_dip``, ``musical_dip``, ``reciprocal_cuts``) — not
# sidechain's ``depth_db``, which is a dynamic reduction with a
# different risk profile. The §6.1 matrix's sidechain defaults (-8 dB
# primary, -4 dB fallback) are intentional starting points that should
# not be capped by a static-EQ rule.

RULE_SIGNATURE_FREQ_PROTECTION = "signature_freq_protection_rule"
RULE_SUB_INTEGRITY_HR = "sub_integrity_hero_rhythm_rule"
RULE_ROLE_APPROPRIATE_MAX_CUT = "role_appropriate_max_cut_rule"

# Importance → max cut depth (dB). Values are the magnitudes; gains
# must stay >= the stored negative number.
_ROLE_MAX_CUT_DB: dict = {
    Importance.H: -3.0,
    Importance.S: -6.0,
    Importance.A: -12.0,
}

# Sub zone range (inclusive). Matches ``section_detector._ZONE_LABELS["sub"]``.
SUB_ZONE_RANGE_HZ: Tuple[float, float] = (20.0, 80.0)

# Approaches that operate via a static gain cut; all protection rules
# apply only to these (sidechain is ducking, not cutting).
_CUT_APPROACHES: Tuple[str, ...] = ("static_dip", "musical_dip", "reciprocal_cuts")

# Reverse mapping from zone center frequency to zone key. Used to
# resolve "the recipe targets freq X Hz — which zone is that?" without
# re-importing section_detector's private tables.
_HZ_TO_ZONE: dict = {v: k for k, v in ZONE_CENTER_HZ.items()}

# Zone label → key inverse, built from section_detector's public
# ``get_zone_label`` so the two tables cannot drift.
def _build_zone_label_to_key() -> dict:
    from section_detector import get_zone_order
    return {get_zone_label(k): k for k in get_zone_order()}


_ZONE_LABEL_TO_KEY: dict = _build_zone_label_to_key()


# ---------------------------------------------------------------------------
# Protection-rule helpers
# ---------------------------------------------------------------------------

def _target_role(
    diagnostic: CorrectionDiagnostic,
    track_name: Optional[str],
) -> Optional[Tuple[Importance, Function]]:
    """Return the (Importance, Function) tuple for ``track_name`` if it
    is one of the diagnostic's two tracks; ``None`` otherwise."""
    if track_name is None:
        return None
    if track_name == diagnostic.track_a:
        return diagnostic.tfp_context.track_a_role
    if track_name == diagnostic.track_b:
        return diagnostic.tfp_context.track_b_role
    return None


def _freq_in_sub_zone(freq_hz: Optional[float]) -> bool:
    """True when ``freq_hz`` sits inside the Sub zone (20-80 Hz, inclusive)."""
    if freq_hz is None:
        return False
    lo, hi = SUB_ZONE_RANGE_HZ
    return lo <= float(freq_hz) <= hi


def _dom_band_zone(
    track_name: str,
    ai_context: Optional[dict],
    zone_energy: Optional[dict],
) -> Optional[str]:
    """Resolve the dominant-band zone key for ``track_name``.

    Priority 1: ``ai_context[track][dom_band]`` — either a zone key
    (``"mid"``) or a label (``"Mid (1-4 kHz)"``). Accept both.
    Priority 2: the zone with the highest energy in
    ``zone_energy[track]`` (``{zone: db_level}``).
    Otherwise: ``None`` — caller skips the rule with a warning.
    """
    if ai_context:
        entry = ai_context.get(track_name)
        if isinstance(entry, dict):
            dom_band = entry.get("dom_band")
            if isinstance(dom_band, str):
                if dom_band in ZONE_CENTER_HZ:
                    return dom_band
                key = _ZONE_LABEL_TO_KEY.get(dom_band)
                if key is not None:
                    return key

    if zone_energy:
        entry = zone_energy.get(track_name)
        if isinstance(entry, dict):
            scalars = {
                z: float(v) for z, v in entry.items()
                if isinstance(v, (int, float))
            }
            if scalars:
                return max(scalars, key=scalars.get)

    return None


def _ensure_rule(diagnostic: CorrectionDiagnostic, slug: str) -> None:
    """Append ``slug`` to ``diagnostic.rules_applied`` if not already present."""
    if slug not in diagnostic.rules_applied:
        diagnostic.rules_applied.append(slug)


def _with_rationale_warning(
    recipe: CorrectionRecipe,
    params: dict,
    warning: str,
) -> CorrectionRecipe:
    """Return a copy of ``recipe`` with ``params`` and an appended warning."""
    existing = recipe.rationale or ""
    sep = " " if existing and not existing.endswith(" ") else ""
    return CorrectionRecipe(
        target_track=recipe.target_track,
        device=recipe.device,
        approach=recipe.approach,
        parameters=params,
        applies_to_sections=recipe.applies_to_sections,
        rationale=f"{existing}{sep}{warning}",
        confidence=recipe.confidence,
    )


# ---------------------------------------------------------------------------
# Rule 2 — Sub integrity for Hero Rhythm (applied first)
# ---------------------------------------------------------------------------

def _apply_rule_sub_integrity(
    diagnostic: CorrectionDiagnostic,
    recipe: CorrectionRecipe,
) -> Tuple[Optional[CorrectionRecipe], bool]:
    """Skip the recipe when it would cut an H/R track in the Sub zone.

    Returns ``(recipe_or_None, triggered)``. For ``reciprocal_cuts``,
    either the primary target OR the secondary cut being on an H/R
    track in Sub skips the whole recipe — caller can try the fallback.
    """
    if recipe.approach not in _CUT_APPROACHES:
        return recipe, False

    primary_role = _target_role(diagnostic, recipe.target_track)
    primary_freq = recipe.parameters.get("frequency_hz")
    if (primary_role == (Importance.H, Function.R)
            and _freq_in_sub_zone(primary_freq)):
        return None, True

    secondary = recipe.parameters.get("secondary_cut")
    if isinstance(secondary, dict):
        secondary_target = secondary.get("track")
        secondary_role = _target_role(diagnostic, secondary_target)
        secondary_freq = secondary.get("frequency_hz")
        if (secondary_role == (Importance.H, Function.R)
                and _freq_in_sub_zone(secondary_freq)):
            return None, True

    return recipe, False


# ---------------------------------------------------------------------------
# Rule 1 — Signature frequency protection (applied second)
# ---------------------------------------------------------------------------

_SIGNATURE_PROTECTED_FUNCTIONS: Tuple[Function, ...] = (Function.M, Function.H)


def _is_signature_protected(role: Optional[Tuple[Importance, Function]]) -> bool:
    """Hero Melodic or Hero Harmonic tracks are signature-protected."""
    return (
        role is not None
        and role[0] is Importance.H
        and role[1] in _SIGNATURE_PROTECTED_FUNCTIONS
    )


def _freq_in_zone(freq_hz: Optional[float], zone_key: Optional[str]) -> bool:
    """True when the recipe's freq falls into the given zone key.

    Because ``frequency_hz`` is always a zone midpoint produced by
    :data:`ZONE_CENTER_HZ`, the test reduces to a dict lookup — no
    arithmetic comparison needed.
    """
    if freq_hz is None or zone_key is None:
        return False
    return _HZ_TO_ZONE.get(float(freq_hz)) == zone_key


def _apply_rule_signature_freq(
    diagnostic: CorrectionDiagnostic,
    recipe: CorrectionRecipe,
    ai_context: Optional[dict],
    zone_energy: Optional[dict],
) -> Tuple[CorrectionRecipe, bool]:
    """Cap gain to -2 dB when cutting H/M or H/H in its dom_band.

    No-op when the target is not signature-protected, when dom_band
    cannot be resolved, or when the recipe's freq falls outside the
    dom_band zone. Also checks the secondary cut for reciprocal_cuts.
    """
    if recipe.approach not in _CUT_APPROACHES:
        return recipe, False

    new_params = dict(recipe.parameters)
    changed = False

    primary_role = _target_role(diagnostic, recipe.target_track)
    if _is_signature_protected(primary_role):
        dom_zone = _dom_band_zone(recipe.target_track, ai_context, zone_energy)
        if dom_zone is None:
            logger.warning(
                "CDE: signature freq protection skipped for %s — dom_band unresolved",
                recipe.target_track,
            )
        elif _freq_in_zone(new_params.get("frequency_hz"), dom_zone):
            gain = float(new_params.get("gain_db", 0.0))
            if gain < -2.0:
                new_params["gain_db"] = -2.0
                changed = True

    secondary = new_params.get("secondary_cut")
    if isinstance(secondary, dict):
        secondary_target = secondary.get("track")
        secondary_role = _target_role(diagnostic, secondary_target)
        if _is_signature_protected(secondary_role):
            dom_zone = _dom_band_zone(secondary_target, ai_context, zone_energy)
            if dom_zone is None:
                logger.warning(
                    "CDE: signature freq protection skipped for %s — dom_band unresolved",
                    secondary_target,
                )
            elif _freq_in_zone(secondary.get("frequency_hz"), dom_zone):
                gain = float(secondary.get("gain_db", 0.0))
                if gain < -2.0:
                    new_secondary = dict(secondary)
                    new_secondary["gain_db"] = -2.0
                    new_params["secondary_cut"] = new_secondary
                    changed = True

    if not changed:
        return recipe, False

    return _with_rationale_warning(
        recipe, new_params,
        "Correction limitée à -2 dB par protection signature frequency.",
    ), True


# ---------------------------------------------------------------------------
# Rule 3 — Role-appropriate max cut (applied last)
# ---------------------------------------------------------------------------

def _apply_rule_role_max_cut(
    diagnostic: CorrectionDiagnostic,
    recipe: CorrectionRecipe,
) -> Tuple[CorrectionRecipe, bool]:
    """Cap gain_db to the Importance-based max (§6.3 Rule 3).

    Hero: -3 dB; Support: -6 dB; Atmos: -12 dB. Applies to both the
    primary target and the secondary_cut for reciprocal_cuts. Sidechain
    depth_db is not touched.
    """
    if recipe.approach not in _CUT_APPROACHES:
        return recipe, False

    new_params = dict(recipe.parameters)
    changed = False

    primary_role = _target_role(diagnostic, recipe.target_track)
    if primary_role is not None:
        cap = _ROLE_MAX_CUT_DB.get(primary_role[0])
        if cap is not None:
            gain = new_params.get("gain_db")
            if gain is not None and float(gain) < cap:
                new_params["gain_db"] = cap
                changed = True

    secondary = new_params.get("secondary_cut")
    if isinstance(secondary, dict):
        secondary_target = secondary.get("track")
        secondary_role = _target_role(diagnostic, secondary_target)
        if secondary_role is not None:
            cap = _ROLE_MAX_CUT_DB.get(secondary_role[0])
            if cap is not None:
                gain = secondary.get("gain_db")
                if gain is not None and float(gain) < cap:
                    new_secondary = dict(secondary)
                    new_secondary["gain_db"] = cap
                    new_params["secondary_cut"] = new_secondary
                    changed = True

    if not changed:
        return recipe, False

    return _with_rationale_warning(
        recipe, new_params,
        "Gain plafonné par la règle role-appropriate max cut.",
    ), True


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def apply_protection_rules(
    diagnostic: CorrectionDiagnostic,
    recommendation: Optional[CorrectionRecipe],
    ai_context: Optional[dict] = None,
    zone_energy: Optional[dict] = None,
) -> Optional[CorrectionRecipe]:
    """Run R2 → R1 → R3 in strict order on ``recommendation``.

    Returns the (possibly modified) recipe or ``None`` if R2 skipped
    the whole recipe. Appends every triggered rule's slug to
    ``diagnostic.rules_applied`` (deduped — a rule that fires on both
    primary AND fallback is recorded once).
    """
    if recommendation is None:
        return None

    current = recommendation

    current, r2 = _apply_rule_sub_integrity(diagnostic, current)
    if r2:
        _ensure_rule(diagnostic, RULE_SUB_INTEGRITY_HR)
    if current is None:
        return None

    current, r1 = _apply_rule_signature_freq(
        diagnostic, current, ai_context, zone_energy,
    )
    if r1:
        _ensure_rule(diagnostic, RULE_SIGNATURE_FREQ_PROTECTION)

    current, r3 = _apply_rule_role_max_cut(diagnostic, current)
    if r3:
        _ensure_rule(diagnostic, RULE_ROLE_APPROPRIATE_MAX_CUT)

    return current


# ---------------------------------------------------------------------------
# Qualitative-impact templates (§7)
# ---------------------------------------------------------------------------
#
# Each approach gets three parallel lists of French one-liners — what
# the engineer should expect, what could go wrong, and how to verify
# the correction audibly. Templates use bracketed placeholders that
# :func:`_substitute_placeholders` resolves against the diagnostic +
# recipe pair.
#
# Placeholder semantics:
#   [track_a]        — for sidechain: the trigger (gains punch).
#                      For other cut approaches: diagnostic.track_a.
#   [track_b]        — for sidechain: the ducked track (the recipe's
#                      target_track). For other approaches: diagnostic.track_b.
#   [track_cut]      — the track being cut (recipe.target_track).
#   [track_protected]— the other track in the conflict (the one that
#                      benefits from the correction).
#   [section]        — diagnostic.section, falling back to "la section".
#   [zone]           — human-readable zone label derived from the
#                      recipe's frequency_hz via ZONE_CENTER_HZ.
#
# Approaches not listed here (or a ``None`` recommendation) yield empty
# lists — no made-up text.

_OUTCOME_TEMPLATES: dict = {
    "sidechain": {
        "expected": [
            "Le [track_a] aura plus de punch dans [section]",
            "Le sub-mix sera plus propre pendant les frappes",
        ],
        "risks": [
            "Pumping audible si le release est trop long",
            "[track_b] pourrait paraître moins soutenu",
        ],
        "verification": [
            "Écouter [section], vérifier que [track_b] respire entre les frappes",
            "A/B comparaison avant/après",
        ],
    },
    "reciprocal_cuts": {
        "expected": [
            "Les deux tracks auront chacune leur espace spectral",
        ],
        "risks": [
            "Les deux pourraient perdre en présence si le cut est trop profond",
        ],
        "verification": [
            "A/B comparaison avant/après",
            "Vérifier que chaque track garde son character",
        ],
    },
    "static_dip": {
        "expected": [
            "[track_cut] laissera plus d'espace dans la zone [zone]",
        ],
        "risks": [
            "[track_cut] pourrait perdre du body dans [zone]",
        ],
        "verification": [
            "Écouter [section], vérifier que [track_protected] respire mieux",
        ],
    },
    "musical_dip": {
        "expected": [
            "Correction douce, le character de [track_cut] est préservé",
        ],
        "risks": [
            "Effet subtil, peut être insuffisant si le conflit est sévère",
        ],
        "verification": [
            "A/B comparaison, vérifier que l'effet est audible",
        ],
    },
}


def _resolve_zone_label_for_freq(freq_hz: Optional[float]) -> str:
    """Return a human-readable zone label for a recipe frequency.

    The recipe's ``frequency_hz`` is always a zone midpoint from
    :data:`ZONE_CENTER_HZ`, so the reverse lookup is exact — no range
    matching. Falls back to a generic label if the freq doesn't match.
    """
    if freq_hz is None:
        return "la bande concernée"
    zone_key = _HZ_TO_ZONE.get(float(freq_hz))
    if zone_key is None:
        return "la bande concernée"
    return get_zone_label(zone_key)


def _substitute_placeholders(
    template: str,
    diagnostic: CorrectionDiagnostic,
    recipe: CorrectionRecipe,
    project_stem: Optional[str] = None,
) -> str:
    """Render ``template`` against ``(diagnostic, recipe)``.

    Sidechain needs special handling because the template's
    ``[track_a]`` / ``[track_b]`` refer to trigger / ducked semantics,
    not to the diagnostic's raw track_a / track_b ordering.

    Track-name placeholders pass through :func:`_clean_track_display_name`,
    so user-facing text reads ``"Kick 1"`` rather than
    ``"Acid_Drops [H_R] Kick 1.wav"``.
    """
    track_a = diagnostic.track_a
    track_b = diagnostic.track_b or ""
    section = diagnostic.section or "la section"
    freq = diagnostic.measurement.frequency_hz if diagnostic.measurement else None
    zone_label = _resolve_zone_label_for_freq(freq)

    def _clean(name: str) -> str:
        # Fall back to the raw name when the cleaner empties it — a
        # defensive guard against overly-aggressive stem stripping.
        return _clean_track_display_name(name, project_stem) or name

    target = recipe.target_track
    # "Protected" is the other track in the conflict — the one that
    # benefits from the correction.
    if target == track_a:
        protected = track_b
    elif target == track_b:
        protected = track_a
    else:
        protected = track_a  # fallback — shouldn't normally happen

    if recipe.approach == "sidechain":
        trigger = recipe.parameters.get("trigger_track", "") or ""
        sub_a = _clean(trigger)
        sub_b = _clean(target)
    else:
        sub_a = _clean(track_a)
        sub_b = _clean(track_b)

    replacements = {
        "[track_a]":         sub_a,
        "[track_b]":         sub_b,
        "[track_cut]":       _clean(target),
        "[track_protected]": _clean(protected),
        "[section]":         section,
        "[zone]":            zone_label,
    }
    out = template
    for placeholder, value in replacements.items():
        out = out.replace(placeholder, str(value))
    return out


def populate_outcome_templates(
    diagnostic: CorrectionDiagnostic,
    project_stem: Optional[str] = None,
) -> None:
    """Fill ``expected_outcomes`` / ``potential_risks`` / ``verification_steps``
    on the diagnostic using the primary_correction's approach.

    Uses the primary correction by default (the user's first-choice
    path). When primary is ``None`` — for example R2 skipped a Sub-zone
    cut on Hero Rhythm — the lists stay empty: there is no concrete
    action to describe outcomes for.

    Args:
        diagnostic: Will be mutated in place.
        project_stem: Optional project prefix stripped from every track
            name in the template substitutions (see
            :func:`_clean_track_display_name`).
    """
    recipe = diagnostic.primary_correction
    if recipe is None:
        return

    templates = _OUTCOME_TEMPLATES.get(recipe.approach)
    if templates is None:
        return

    diagnostic.expected_outcomes = [
        _substitute_placeholders(t, diagnostic, recipe, project_stem)
        for t in templates.get("expected", [])
    ]
    diagnostic.potential_risks = [
        _substitute_placeholders(t, diagnostic, recipe, project_stem)
        for t in templates.get("risks", [])
    ]
    diagnostic.verification_steps = [
        _substitute_placeholders(t, diagnostic, recipe, project_stem)
        for t in templates.get("verification", [])
    ]


# ---------------------------------------------------------------------------
# JSON serialisation — minimal B1c2b output
# ---------------------------------------------------------------------------
#
# ``dump_diagnostics_to_json`` writes the masking diagnostics to disk in
# a deterministic, human-readable format. B2 will extend the payload
# with a ``summary`` block (counts by severity) and accumulation
# diagnostics; the field-level shape of each diagnostic entry is stable.
#
# Deserialisation (load + filter + get_by_id) ships in B3 together with
# the consultation API. B1c2b is write-only.

def _role_to_list(
    role: Optional[Tuple[Importance, Function]],
) -> Optional[List[str]]:
    """Convert a role tuple to a JSON list of short codes (``["H", "R"]``).

    ``None`` stays ``None`` — a single-track diagnostic has no second role.
    """
    if role is None:
        return None
    return [role[0].value, role[1].value]


def _coerce_value(value):
    """Recursively coerce a parameters-dict value to a JSON-native form.

    Handles the usual suspects: enums → ``.value``, ``datetime`` →
    ISO string, ``Path`` → ``str(...)``, nested dicts / lists. Any
    unknown object falls through untouched and will raise at
    ``json.dumps`` time — better to fail loudly than silently drop data.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _coerce_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_coerce_value(v) for v in value]
    return value


def _recipe_to_dict(recipe: Optional[CorrectionRecipe]) -> Optional[dict]:
    """Serialise a :class:`CorrectionRecipe` to a JSON-ready dict."""
    if recipe is None:
        return None
    return {
        "target_track":        recipe.target_track,
        "device":              recipe.device,
        "approach":            recipe.approach,
        "parameters":          _coerce_value(recipe.parameters),
        "applies_to_sections": list(recipe.applies_to_sections),
        "rationale":           recipe.rationale,
        "confidence":          recipe.confidence,
    }


def _diagnostic_to_dict(d: CorrectionDiagnostic) -> dict:
    """Serialise one :class:`CorrectionDiagnostic` to a JSON-ready dict.

    Top-level field order matches the spec §9.1 example for readability —
    ID / identification first, then problem + contexts, then
    recommendations, then impact lists, then audit.
    """
    return {
        "diagnostic_id":    d.diagnostic_id,
        "timestamp":        d.timestamp.isoformat() if d.timestamp else None,
        "cde_version":      d.cde_version,
        "issue_type":       d.issue_type,
        "severity":         d.severity,
        "section":          d.section,
        "track_a":          d.track_a,
        "track_b":          d.track_b,
        "measurement":      asdict(d.measurement) if d.measurement else None,
        "tfp_context": {
            "track_a_role":         _role_to_list(d.tfp_context.track_a_role),
            "track_b_role":         _role_to_list(d.tfp_context.track_b_role),
            "role_compatibility":   d.tfp_context.role_compatibility,
        },
        "section_context":   asdict(d.section_context) if d.section_context else None,
        "diagnosis_text":    d.diagnosis_text,
        "primary_correction":   _recipe_to_dict(d.primary_correction),
        "fallback_correction":  _recipe_to_dict(d.fallback_correction),
        "expected_outcomes":    list(d.expected_outcomes),
        "potential_risks":      list(d.potential_risks),
        "verification_steps":   list(d.verification_steps),
        "application_status":   d.application_status,
        "rejection_reason":     d.rejection_reason,
        "applied_backup_path":  (
            str(d.applied_backup_path) if d.applied_backup_path else None
        ),
        "data_sources":         list(d.data_sources),
        "rules_applied":        list(d.rules_applied),
    }


def dump_diagnostics_to_json(
    diagnostics: List[CorrectionDiagnostic],
    path,
) -> None:
    """Write ``diagnostics`` to ``path`` as UTF-8 JSON (indent=2, human-readable).

    Payload shape::

        {
            "cde_version":        "1.0",
            "generated_at":       "<ISO timestamp>",
            "diagnostic_count":   <int>,
            "diagnostics":        [ { ... }, ... ]
        }

    A ``summary`` block with per-severity counts and accumulation
    diagnostics ships in B2. B1c2b is intentionally minimal.

    Args:
        diagnostics: Output of :func:`detect_masking_conflicts` (or any
            caller that produces ``CorrectionDiagnostic`` instances).
            Order is preserved in the output file.
        path: Destination file path (``str`` or :class:`pathlib.Path`).
            Parent directories are created if missing.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "cde_version":      CDE_VERSION,
        "generated_at":     datetime.now().isoformat(),
        "diagnostic_count": len(diagnostics),
        "diagnostics":      [_diagnostic_to_dict(d) for d in diagnostics],
    }

    with target.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Public API — masking detector
# ---------------------------------------------------------------------------

def detect_masking_conflicts(
    section,
    all_tracks_zone_energy: Optional[dict] = None,
    ai_context: Optional[dict] = None,
    project_stem: Optional[str] = None,
) -> List[CorrectionDiagnostic]:
    """Generate one :class:`CorrectionDiagnostic` per conflict in ``section``.

    Consumes ``section.conflicts`` (populated by B1a's persistence step
    in ``build_sections_timeline_sheet``). The CDE does not recompute
    conflicts — running ``detect_conflicts_in_section`` twice would be
    wasteful and risks drift.

    Tracks missing from ``all_tracks_zone_energy`` (MIDI instruments
    that were never bounced to WAV) are skipped with a warning log —
    Risque 7 of the F3.6 recon.

    Since B1c1 each diagnostic is decorated with a
    ``primary_correction`` (via :func:`compute_primary_recommendation`,
    §6.1 matrix) and a ``fallback_correction``
    (:func:`compute_fallback_recommendation`, §6.2). Since B1c2a both
    are run through :func:`apply_protection_rules` (§6.3) which can
    cap the gain or invalidate a recipe — ``None`` is therefore also
    returned when the protection rules skip the recipe entirely (e.g.
    a kick's Sub-zone cut).

    Args continued:
        ai_context: Optional ``{track_name: {"dom_band": <zone_or_label>}}``
            map from the AI Context sheet. Feeds Rule 1 (signature
            frequency protection). When absent the rule falls back to
            ``section.track_energy`` to find the track's dom_band.
        project_stem: Optional project prefix (e.g. ``"Acid_Drops"``)
            stripped from every user-facing track name — diagnostic
            IDs, diagnosis text, and outcome template substitutions.
            Use :func:`infer_project_stem` to detect it from the set of
            WAV track names. Internal fields (``track_a``,
            ``recipe.target_track``, etc.) keep the raw name so
            matching with ``section.*`` keys stays intact.

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
        # Clean the track names going into the ID so the user sees
        # CONF_CHORUS1_KICK1_SUBBASS_50HZ instead of the full WAV path.
        diag_id = generate_diagnostic_id(
            issue_type="masking_conflict",
            section=section_ctx.section_name,
            track_a=_clean_track_display_name(track_a, project_stem) or track_a,
            track_b=_clean_track_display_name(track_b, project_stem) or track_b,
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
            project_stem=project_stem,
        )

        diag = CorrectionDiagnostic(
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
            data_sources=[
                "Sections Timeline:CONFLITS DE FREQUENCES",
                "Section.track_roles (Feature 3.5)",
            ],
        )
        # B1c1 — fill recommendations from the §6.1 matrix + §6.2 fallback
        primary, rules = compute_primary_recommendation(diag)
        fallback = compute_fallback_recommendation(diag, primary)
        diag.rules_applied = list(rules)

        # B1c2a — protection rules (§6.3) may cap or invalidate each recipe.
        # ``section.track_energy`` feeds Rule 1's priority-2 dom_band lookup
        # when no ``ai_context`` is provided.
        zone_energy = getattr(section, "track_energy", {}) or {}
        diag.primary_correction = apply_protection_rules(
            diag, primary, ai_context=ai_context, zone_energy=zone_energy,
        )
        diag.fallback_correction = apply_protection_rules(
            diag, fallback, ai_context=ai_context, zone_energy=zone_energy,
        )

        # B1c2b — fill the qualitative-impact lists (outcomes / risks /
        # verification) from the primary_correction's approach. Track
        # names in the substitutions get the same cleanup as the ID.
        populate_outcome_templates(diag, project_stem=project_stem)

        diagnostics.append(diag)

    return diagnostics
