#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tfp_coherence.py — section coherence scoring for Feature 3.5 Phase B3.

Computes a 0-100 coherence score per section from the resolved TFP roles
(see :mod:`tfp_parser`) and the spectral conflicts detected on the
section. The score is the weighted sum of four components, each capped:

    40 — importance ratios vs reference ranges (H/S/A)
    20 — function diversity (R/H/M/T coverage)
    30 — hero-vs-hero critical conflicts penalty
    10 — role diversity penalty (how many distinct functions)

Kept as a pure, import-light module so it can be unit-tested against
the exact worked examples in the Feature 3.5 spec (R5), and later
reused by Feature 3.6 (Correction Diagnostic Engine).

Sparse / short section convention
---------------------------------
Sections shorter than 3 seconds OR with fewer than 3 active tracks are
reported with ``score=None`` (rendered as "—") and a single diagnostic
message ``"Section trop courte ou sparse"`` — scoring a section with
too few data points would be misleading.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional, Tuple

from tfp_parser import Function, Importance


# ---------------------------------------------------------------------------
# Constants — exposed so callers / tests can reference them directly
# ---------------------------------------------------------------------------

MAX_POINTS_IMPORTANCE = 40.0
MAX_POINTS_FUNCTION_DIVERSITY = 20.0
MAX_POINTS_HERO_CONFLICTS = 30.0
MAX_POINTS_ROLE_DIVERSITY = 10.0

# Reference ratios per importance dimension (low, high), closed interval.
# A ratio inside the range scores the full per-dimension share; outside,
# the penalty is proportional to the distance from the nearest bound,
# capped at 100% (i.e. zero points for that dimension).
IDEAL_IMPORTANCE_RANGES: Dict[Importance, Tuple[float, float]] = {
    Importance.H: (0.15, 0.30),
    Importance.S: (0.30, 0.50),
    Importance.A: (0.20, 0.40),
}

# Sparse section thresholds — below these values the score is unavailable.
SPARSE_MIN_DURATION_S = 3.0
SPARSE_MIN_TRACKS = 3

# Diagnostic thresholds surfaced in the textual messages.
HIGH_HERO_RATIO = 0.35
LOW_HERO_RATIO = 0.10
LOW_ATMOS_RATIO = 0.10
CRITICAL_HH_THRESHOLD = 3  # N conflicts H×H above which the message fires


# ---------------------------------------------------------------------------
# Component 1 — Importance ratio
# ---------------------------------------------------------------------------

def importance_points(
    ratios: Dict[Importance, float],
    max_points: float = MAX_POINTS_IMPORTANCE,
) -> float:
    """Score the H/S/A distribution against :data:`IDEAL_IMPORTANCE_RANGES`.

    ``ratios`` are in [0, 1] and need not sum to 1 (some tracks may drop
    out if they fall below the listing threshold). Each of the 3
    importance dimensions contributes ``max_points / 3`` when its ratio
    sits within the ideal range; otherwise a penalty proportional to the
    distance from the nearest bound (capped at 100%) is applied.

    Returns the rounded score (1 decimal).
    """
    points_per_dim = max_points / 3.0
    total = 0.0
    for dim in (Importance.H, Importance.S, Importance.A):
        r = float(ratios.get(dim, 0.0))
        low, high = IDEAL_IMPORTANCE_RANGES[dim]
        if low <= r <= high:
            total += points_per_dim
            continue
        if r < low:
            distance = (low - r) / low if low > 0 else 1.0
        else:
            distance = (r - high) / (1 - high) if high < 1 else 0.0
        penalty = min(max(distance, 0.0), 1.0)
        total += points_per_dim * (1.0 - penalty)
    return round(total, 1)


# ---------------------------------------------------------------------------
# Component 2 — Function diversity (R/H/M/T presence)
# ---------------------------------------------------------------------------

_FUNCTION_DIVERSITY_BAREME = {
    4: 20.0,
    3: 15.0,
    2: 10.0,
    1: 5.0,
    0: 0.0,
}


def function_diversity_points(
    functions_present: set,
    max_points: float = MAX_POINTS_FUNCTION_DIVERSITY,
) -> float:
    """Reward coverage of the four musical functions (R/H/M/T).

    The spec gives a flat barème — the multiplier against ``max_points``
    lets callers scale if the 4 function categories ever become 5.
    """
    n = len(functions_present & set(Function))
    # Spec barème is pinned to max_points=20; scale proportionally if
    # the caller overrides max_points for some extension.
    base = _FUNCTION_DIVERSITY_BAREME.get(n, 0.0)
    scale = max_points / 20.0
    return round(base * scale, 1)


# ---------------------------------------------------------------------------
# Component 3 — Hero-vs-hero critical conflicts penalty
# ---------------------------------------------------------------------------

def count_critical_hero_conflicts(
    conflicts: List[dict],
    track_roles: Dict[str, Tuple[Importance, Function]],
) -> int:
    """Return the number of ``severity == "critical"`` conflicts whose
    both tracks are flagged as Hero importance.

    Conflicts whose tracks are not in ``track_roles`` are treated as
    Support / Rhythm (the :data:`tfp_parser.DEFAULT_ROLE`) and thus
    never count as H×H — this matches the R2 "default when unclassified"
    convention used everywhere else in Feature 3.5.
    """
    count = 0
    for c in conflicts:
        if c.get("severity") != "critical":
            continue
        role_a = track_roles.get(c.get("track_a"))
        role_b = track_roles.get(c.get("track_b"))
        if role_a is None or role_b is None:
            continue
        if role_a[0] is Importance.H and role_b[0] is Importance.H:
            count += 1
    return count


def hero_conflict_points(
    n_critical_hh: int,
    max_points: float = MAX_POINTS_HERO_CONFLICTS,
) -> float:
    """Penalty scoring — starts at ``max_points`` and drops 5 per H×H."""
    penalty_per_conflict = 5.0
    remaining = max_points - (n_critical_hh * penalty_per_conflict)
    return round(max(remaining, 0.0), 1)


# ---------------------------------------------------------------------------
# Component 4 — Minimum role diversity
# ---------------------------------------------------------------------------

def role_diversity_points(
    functions_present: set,
    max_points: float = MAX_POINTS_ROLE_DIVERSITY,
) -> float:
    """Extra penalty when the section has too few distinct functions.

    Spec barème: ≥3 → full points, 2 → half, <2 → 0. Complements
    :func:`function_diversity_points` (which rewards the other end of
    the scale, the 4-of-4 case).
    """
    n = len(functions_present & set(Function))
    if n >= 3:
        return round(max_points, 1)
    if n == 2:
        return round(max_points / 2.0, 1)
    return 0.0


# ---------------------------------------------------------------------------
# Public entry point — compute the full score for a section
# ---------------------------------------------------------------------------

def compute_section_coherence_score(
    section,
    conflicts: Optional[List[dict]] = None,
) -> dict:
    """Compute the complete 0-100 coherence score for a section.

    Returns a dict with keys:
        score              : float or ``None`` (None when sparse)
        components         : dict of the 4 sub-scores (keys: importance,
                             function_diversity, hero_conflicts,
                             role_diversity) — all ``None`` when sparse.
        counts             : dict of {"H", "S", "A", "R", "H" (fn),
                             "M", "T"} integer counts — included even
                             when sparse so the sheet can still render
                             them usefully.
        n_critical_hh      : int count of critical H×H conflicts.
        diagnostic         : str — generic verdict string.
        messages           : list[str] — up to 3 specific messages
                             (see R5).
        sparse             : bool — True when the sparse guard triggered.

    The ``conflicts`` arg is the list returned by
    :func:`section_detector.detect_conflicts_in_section` for this
    section. When ``None``, hero conflicts are treated as 0 — callers
    can compute the conflicts themselves and pass them in to exercise
    the full penalty.

    Args:
        section: A :class:`section_detector.Section` with ``track_roles``
            populated (i.e. after
            :func:`section_detector.enrich_sections_with_track_roles`
            has run).
        conflicts: Optional list of conflict dicts; ``None`` to skip
            the H×H penalty.
    """
    # --- Sparse guard -------------------------------------------------
    duration = float(
        getattr(section, "end_seconds", 0.0) - getattr(section, "start_seconds", 0.0)
    )
    tracks_active = list(getattr(section, "tracks_active", []) or [])

    track_roles = getattr(section, "track_roles", {}) or {}
    # Restrict role counts to tracks actually "active" in the section so
    # the score reflects what the user sees in the PEAK MAX block.
    active_roles = [
        track_roles[t] for t in tracks_active if t in track_roles
    ]

    imp_counts = Counter(r[0] for r in active_roles)
    fn_counts = Counter(r[1] for r in active_roles)

    counts = {
        "H": int(imp_counts.get(Importance.H, 0)),
        "S": int(imp_counts.get(Importance.S, 0)),
        "A": int(imp_counts.get(Importance.A, 0)),
        "fn_R": int(fn_counts.get(Function.R, 0)),
        "fn_H": int(fn_counts.get(Function.H, 0)),
        "fn_M": int(fn_counts.get(Function.M, 0)),
        "fn_T": int(fn_counts.get(Function.T, 0)),
    }
    total_active = len(active_roles)

    if duration < SPARSE_MIN_DURATION_S or total_active < SPARSE_MIN_TRACKS:
        return {
            "score": None,
            "components": {
                "importance": None,
                "function_diversity": None,
                "hero_conflicts": None,
                "role_diversity": None,
            },
            "counts": counts,
            "n_critical_hh": 0,
            "diagnostic": "Section trop courte ou sparse",
            "messages": [],
            "sparse": True,
        }

    # --- Component 1: importance ratios -------------------------------
    ratios = {
        Importance.H: counts["H"] / total_active,
        Importance.S: counts["S"] / total_active,
        Importance.A: counts["A"] / total_active,
    }
    pts_imp = importance_points(ratios)

    # --- Component 2: function diversity ------------------------------
    functions_present = set(fn_counts.keys())
    pts_fn_div = function_diversity_points(functions_present)

    # --- Component 3: hero conflicts penalty -------------------------
    n_hh = count_critical_hero_conflicts(conflicts or [], track_roles)
    pts_hh = hero_conflict_points(n_hh)

    # --- Component 4: role diversity ---------------------------------
    pts_role_div = role_diversity_points(functions_present)

    score = round(pts_imp + pts_fn_div + pts_hh + pts_role_div, 1)

    diagnostic, messages = _build_diagnostic(
        score=score,
        ratios=ratios,
        functions_present=functions_present,
        n_critical_hh=n_hh,
    )

    return {
        "score": score,
        "components": {
            "importance": pts_imp,
            "function_diversity": pts_fn_div,
            "hero_conflicts": pts_hh,
            "role_diversity": pts_role_div,
        },
        "counts": counts,
        "n_critical_hh": n_hh,
        "diagnostic": diagnostic,
        "messages": messages,
        "sparse": False,
    }


# ---------------------------------------------------------------------------
# Diagnostic construction
# ---------------------------------------------------------------------------

_FUNCTION_LABELS_FR = {
    Function.R: "Rhythm",
    Function.H: "Harmonic",
    Function.M: "Melodic",
    Function.T: "Textural",
}


def _generic_diagnostic(score: float) -> str:
    if score >= 80:
        return "Équilibre OK"
    if score >= 60:
        return "Quelques déséquilibres à surveiller"
    if score >= 40:
        return "Problèmes de composition des rôles"
    return "Problèmes structurels importants"


def _build_diagnostic(
    score: float,
    ratios: Dict[Importance, float],
    functions_present: set,
    n_critical_hh: int,
) -> Tuple[str, List[str]]:
    """Return (generic_diagnostic, specific_messages) per R5 of the spec.

    Specific messages are sorted by impact (H×H > importance > diversity)
    and capped at 3. When the score is high (>=85) and nothing triggers,
    only the generic "Équilibre OK" is returned with an empty message
    list.
    """
    messages: List[Tuple[int, str]] = []  # (priority, text)

    # 1. Hero-vs-hero conflicts — highest priority
    if n_critical_hh >= CRITICAL_HH_THRESHOLD:
        messages.append((
            0,
            f"{n_critical_hh} conflits critiques entre tracks hero — "
            "priorité de correction",
        ))

    # 2. Importance imbalance — medium priority
    h_ratio = ratios.get(Importance.H, 0.0)
    a_ratio = ratios.get(Importance.A, 0.0)
    if h_ratio > HIGH_HERO_RATIO:
        # Count derived from ratio * total; the caller has the raw count
        # but here we only have ratios. Format the ratio as a fraction
        # to keep the message human-readable.
        messages.append((
            1,
            f"{h_ratio * 100:.0f}% de tracks hero — "
            "risque de masking et surcharge",
        ))
    elif h_ratio < LOW_HERO_RATIO:
        messages.append((
            1,
            "Très peu de tracks hero — section sans leader clair",
        ))
    if a_ratio < LOW_ATMOS_RATIO:
        messages.append((
            1,
            "Peu d'éléments atmosphériques — manque d'espace et respiration",
        ))

    # 3. Function diversity — lowest priority
    all_functions = set(Function)
    missing = all_functions - functions_present
    if len(functions_present & all_functions) == 1:
        messages.append((
            2,
            "Section sur une seule dimension fonctionnelle — manque de variété",
        ))
    elif missing and len(missing) <= 2:
        # Surface up to two missing functions in the same message.
        names = ", ".join(
            _FUNCTION_LABELS_FR[f] for f in missing if f in _FUNCTION_LABELS_FR
        )
        messages.append((
            2,
            f"Aucun élément {names} — section incomplète",
        ))

    # Sort by priority, truncate to 3
    messages.sort(key=lambda m: m[0])
    specific = [text for _, text in messages[:3]]

    generic = _generic_diagnostic(score)
    if score >= 85 and not specific:
        return generic, []
    return generic, specific
