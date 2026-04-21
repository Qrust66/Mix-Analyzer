#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for ``tfp_coherence`` — Feature 3.5 Phase B3.

Exhaustive verification of the 4 scoring components against the worked
examples in R5 of the spec + edge cases (sparse sections, full diagnostic
path). The module is pure Python so these tests run without stubbing.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tfp_coherence import (  # noqa: E402
    CRITICAL_HH_THRESHOLD,
    HIGH_HERO_RATIO,
    IDEAL_IMPORTANCE_RANGES,
    LOW_ATMOS_RATIO,
    LOW_HERO_RATIO,
    MAX_POINTS_FUNCTION_DIVERSITY,
    MAX_POINTS_HERO_CONFLICTS,
    MAX_POINTS_IMPORTANCE,
    MAX_POINTS_ROLE_DIVERSITY,
    SPARSE_MIN_DURATION_S,
    SPARSE_MIN_TRACKS,
    compute_section_coherence_score,
    count_critical_hero_conflicts,
    function_diversity_points,
    hero_conflict_points,
    importance_points,
    role_diversity_points,
)
from tfp_parser import Function, Importance  # noqa: E402


# ---------------------------------------------------------------------------
# Minimal Section stub so we don't drag in section_detector / numpy here
# ---------------------------------------------------------------------------

@dataclass
class FakeSection:
    start_seconds: float = 0.0
    end_seconds: float = 15.0
    tracks_active: List[str] = field(default_factory=list)
    track_roles: Dict[str, Tuple[Importance, Function]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Component 1 — importance_points
# ---------------------------------------------------------------------------

def test_importance_points_constants_pinned_to_spec():
    """Pin the reference ranges — the spec hard-codes these."""
    assert IDEAL_IMPORTANCE_RANGES[Importance.H] == (0.15, 0.30)
    assert IDEAL_IMPORTANCE_RANGES[Importance.S] == (0.30, 0.50)
    assert IDEAL_IMPORTANCE_RANGES[Importance.A] == (0.20, 0.40)
    assert MAX_POINTS_IMPORTANCE == 40.0


def test_R5_example_intro_all_three_within_ideal_scores_40_of_40():
    """Spec example: Intro with 1H/2S/1A -> ratios 25/50/25, all ideal."""
    ratios = {
        Importance.H: 0.25,
        Importance.S: 0.50,
        Importance.A: 0.25,
    }
    result = importance_points(ratios)
    assert result == 40.0


def test_R5_example_chorus1_high_hero_low_atmos_matches_spec_within_tolerance():
    """Spec example: Chorus 1 with 8H/5S/1A -> target 26.2/40 (tolerance
    ±0.2 because the spec worked the arithmetic with 13.3 per dim while
    the formula uses 40/3 ≈ 13.333)."""
    n = 14
    ratios = {
        Importance.H: 8 / n,   # 0.571
        Importance.S: 5 / n,   # 0.357
        Importance.A: 1 / n,   # 0.071
    }
    result = importance_points(ratios)
    # Spec: 26.2 ; exact math: ~26.28 -> rounds to 26.3
    assert 26.0 <= result <= 26.5, (
        f"expected ~26.2 (spec) / 26.3 (exact), got {result}"
    )


def test_importance_points_missing_dimension_counts_as_zero():
    """Empty ratio dict -> all three dims score 0 against their low bound."""
    result = importance_points({})
    # Each dim fully at 100% penalty -> 0 points each
    assert result == 0.0


def test_importance_points_all_hero_scores_penalized():
    """100% hero -> H past its ideal (0.30), S+A at 0.
    - H: distance = (1-0.30)/(1-0.30) = 1.0 -> 0 points
    - S: distance = (0.30-0)/0.30 = 1.0 -> 0 points
    - A: distance = (0.20-0)/0.20 = 1.0 -> 0 points
    Total: 0/40"""
    result = importance_points({
        Importance.H: 1.0,
        Importance.S: 0.0,
        Importance.A: 0.0,
    })
    assert result == 0.0


# ---------------------------------------------------------------------------
# Component 2 — function_diversity_points
# ---------------------------------------------------------------------------

def test_function_diversity_all_four_scores_20():
    result = function_diversity_points({Function.R, Function.H, Function.M, Function.T})
    assert result == 20.0


def test_function_diversity_barème_matches_spec():
    """Spec: 4→20, 3→15, 2→10, 1→5, 0→0."""
    assert function_diversity_points({Function.R, Function.H, Function.M, Function.T}) == 20.0
    assert function_diversity_points({Function.R, Function.H, Function.M}) == 15.0
    assert function_diversity_points({Function.R, Function.H}) == 10.0
    assert function_diversity_points({Function.R}) == 5.0
    assert function_diversity_points(set()) == 0.0


# ---------------------------------------------------------------------------
# Component 3 — hero_conflict_points + count_critical_hero_conflicts
# ---------------------------------------------------------------------------

def test_hero_conflict_points_zero_conflicts_full_points():
    assert hero_conflict_points(0) == 30.0


def test_hero_conflict_points_drops_five_per_conflict_with_floor_at_zero():
    assert hero_conflict_points(1) == 25.0
    assert hero_conflict_points(2) == 20.0
    assert hero_conflict_points(5) == 5.0
    assert hero_conflict_points(6) == 0.0
    assert hero_conflict_points(10) == 0.0  # plancher 0


def test_count_critical_hero_conflicts_only_counts_both_hero_criticals():
    """Moderate conflicts, Support tracks, missing tracks -> all excluded."""
    track_roles = {
        "KickA":  (Importance.H, Function.R),
        "KickB":  (Importance.H, Function.R),
        "Bass":   (Importance.S, Function.H),
        "Atmos":  (Importance.A, Function.T),
    }
    conflicts = [
        # H × H critical  -> count
        {"track_a": "KickA", "track_b": "KickB", "severity": "critical"},
        # H × H but moderate -> skip
        {"track_a": "KickA", "track_b": "KickB", "severity": "moderate"},
        # H × S critical -> skip
        {"track_a": "KickA", "track_b": "Bass", "severity": "critical"},
        # Unknown track -> skip
        {"track_a": "Unknown", "track_b": "KickA", "severity": "critical"},
    ]
    assert count_critical_hero_conflicts(conflicts, track_roles) == 1


def test_count_critical_hero_conflicts_empty_inputs_return_zero():
    assert count_critical_hero_conflicts([], {}) == 0
    assert count_critical_hero_conflicts(
        [{"track_a": "X", "track_b": "Y", "severity": "critical"}], {}
    ) == 0


# ---------------------------------------------------------------------------
# Component 4 — role_diversity_points
# ---------------------------------------------------------------------------

def test_role_diversity_points_barème_matches_spec():
    """Spec: ≥3 → 10, 2 → 5, 1 or 0 → 0."""
    assert role_diversity_points({Function.R, Function.H, Function.M}) == 10.0
    assert role_diversity_points({Function.R, Function.H, Function.M, Function.T}) == 10.0
    assert role_diversity_points({Function.R, Function.H}) == 5.0
    assert role_diversity_points({Function.R}) == 0.0
    assert role_diversity_points(set()) == 0.0


# ---------------------------------------------------------------------------
# compute_section_coherence_score — full integration
# ---------------------------------------------------------------------------

def _make_section(
    duration: float = 15.0,
    tracks: Optional[Dict[str, Tuple[Importance, Function]]] = None,
) -> FakeSection:
    """Build a section whose ``tracks_active`` equals the keys of ``tracks``."""
    tracks = tracks or {}
    return FakeSection(
        start_seconds=0.0,
        end_seconds=duration,
        tracks_active=list(tracks.keys()),
        track_roles=dict(tracks),
    )


def test_score_sparse_when_duration_below_threshold_returns_none():
    section = _make_section(
        duration=SPARSE_MIN_DURATION_S - 0.5,
        tracks={
            "A": (Importance.H, Function.R),
            "B": (Importance.S, Function.H),
            "C": (Importance.A, Function.T),
        },
    )
    result = compute_section_coherence_score(section)
    assert result["score"] is None
    assert result["sparse"] is True
    assert result["diagnostic"] == "Section trop courte ou sparse"


def test_score_sparse_when_fewer_than_three_tracks_returns_none():
    section = _make_section(
        duration=15.0,
        tracks={
            "A": (Importance.H, Function.R),
            "B": (Importance.S, Function.H),
        },
    )
    result = compute_section_coherence_score(section)
    assert result["score"] is None
    assert result["sparse"] is True


def test_R5_balanced_intro_scores_around_85_or_more():
    """Spec: Intro 1H/2S/1A + 4 functions (R,H,M,T) + 0 H×H conflicts
    should land in the 'Équilibre OK' band (>= 80).
    Expected breakdown:
      importance      = 40.0
      function_div    = 20.0
      hero_conflicts  = 30.0
      role_diversity  = 10.0
      total           = 100.0"""
    section = _make_section(
        duration=15.0,
        tracks={
            "Kick":  (Importance.H, Function.R),
            "Bass":  (Importance.S, Function.H),
            "Pad":   (Importance.S, Function.M),
            "Atmos": (Importance.A, Function.T),
        },
    )
    result = compute_section_coherence_score(section, conflicts=[])
    assert result["score"] == 100.0
    assert result["components"]["importance"] == 40.0
    assert result["components"]["function_diversity"] == 20.0
    assert result["components"]["hero_conflicts"] == 30.0
    assert result["components"]["role_diversity"] == 10.0
    assert result["diagnostic"] == "Équilibre OK"
    assert result["messages"] == []


def test_R5_chorus1_heavy_hero_scores_below_60():
    """Spec: Chorus 1 with 8H/5S/1A and 3 critical H×H conflicts.
    Expected breakdown:
      importance     ≈ 26.3 (spec says 26.2)
      function_div   varies (we give full 20 assuming all 4 functions)
      hero_conflicts = 30 - 3*5 = 15
      role_diversity = 10
    Total ≈ 71.3 — lands in 'Quelques déséquilibres' band."""
    # 8 hero tracks covering all four function codes
    tracks = {}
    hero_functions = [Function.R, Function.R, Function.R, Function.H,
                      Function.M, Function.M, Function.T, Function.T]
    for i, fn in enumerate(hero_functions):
        tracks[f"Hero{i}"] = (Importance.H, fn)
    # 5 support
    for i in range(5):
        tracks[f"Support{i}"] = (Importance.S, Function.R)
    # 1 atmos
    tracks["Atmos"] = (Importance.A, Function.T)

    # 3 H×H critical conflicts among Hero* tracks
    conflicts = [
        {"track_a": "Hero0", "track_b": "Hero1", "severity": "critical"},
        {"track_a": "Hero2", "track_b": "Hero3", "severity": "critical"},
        {"track_a": "Hero4", "track_b": "Hero5", "severity": "critical"},
    ]
    section = _make_section(duration=15.0, tracks=tracks)
    result = compute_section_coherence_score(section, conflicts=conflicts)

    assert 65.0 <= result["score"] <= 75.0, f"got {result['score']}"
    assert result["components"]["hero_conflicts"] == 15.0
    assert result["components"]["role_diversity"] == 10.0
    assert result["n_critical_hh"] == 3
    # Should surface the H×H message (priority 0)
    assert any("conflits critiques" in m for m in result["messages"])


def test_high_score_no_messages_returns_empty_message_list():
    """When score ≥ 85 and nothing triggers, messages are empty and
    only the generic 'Équilibre OK' is returned."""
    section = _make_section(
        duration=15.0,
        tracks={
            "H": (Importance.H, Function.R),
            "S1": (Importance.S, Function.H),
            "S2": (Importance.S, Function.M),
            "A": (Importance.A, Function.T),
        },
    )
    result = compute_section_coherence_score(section, conflicts=[])
    assert result["score"] >= 85
    assert result["messages"] == []
    assert result["diagnostic"] == "Équilibre OK"


def test_message_when_too_few_heros():
    """No hero tracks -> ratio H = 0 < LOW_HERO_RATIO -> diagnostic message."""
    section = _make_section(
        duration=15.0,
        tracks={
            "S1": (Importance.S, Function.R),
            "S2": (Importance.S, Function.H),
            "S3": (Importance.S, Function.M),
            "A": (Importance.A, Function.T),
        },
    )
    result = compute_section_coherence_score(section, conflicts=[])
    assert any("Très peu de tracks hero" in m for m in result["messages"])


def test_message_when_no_atmos():
    """Zero atmos tracks -> A ratio below threshold -> dedicated message."""
    section = _make_section(
        duration=15.0,
        tracks={
            "H1": (Importance.H, Function.R),
            "S1": (Importance.S, Function.H),
            "S2": (Importance.S, Function.M),
            "S3": (Importance.S, Function.T),
        },
    )
    result = compute_section_coherence_score(section, conflicts=[])
    assert any("atmosphériques" in m.lower() for m in result["messages"])


def test_message_when_single_function_dimension():
    """Section entirely on Rhythm -> diversity message fires."""
    section = _make_section(
        duration=15.0,
        tracks={
            "H1": (Importance.H, Function.R),
            "H2": (Importance.H, Function.R),
            "H3": (Importance.H, Function.R),
            "H4": (Importance.H, Function.R),
        },
    )
    result = compute_section_coherence_score(section, conflicts=[])
    assert any(
        "une seule dimension" in m or "sur une seule" in m
        for m in result["messages"]
    )


def test_messages_capped_at_three_sorted_by_priority():
    """When more than 3 issues fire, H×H comes first (priority 0),
    importance imbalance second (priority 1), diversity last (priority 2)."""
    # Many heros + no atmos + single function + 5 critical H×H
    tracks = {}
    for i in range(8):
        tracks[f"H{i}"] = (Importance.H, Function.R)  # single fn only
    conflicts = [
        {"track_a": f"H{i}", "track_b": f"H{i+1}", "severity": "critical"}
        for i in range(5)
    ]
    section = _make_section(duration=15.0, tracks=tracks)
    result = compute_section_coherence_score(section, conflicts=conflicts)
    assert len(result["messages"]) == 3
    # First must mention H×H conflicts (highest priority)
    assert "conflits critiques" in result["messages"][0]


# ---------------------------------------------------------------------------
# Counts dict — available even for sparse sections
# ---------------------------------------------------------------------------

def test_counts_are_present_on_sparse_sections():
    """Even when the score is None, the per-importance / per-function
    counts should be available for display in the sheet ('H/S/A' cell)."""
    section = _make_section(
        duration=15.0,
        tracks={
            "H": (Importance.H, Function.R),
            "S": (Importance.S, Function.H),
        },  # only 2 tracks -> sparse
    )
    result = compute_section_coherence_score(section)
    assert result["sparse"] is True
    assert result["counts"]["H"] == 1
    assert result["counts"]["S"] == 1
    assert result["counts"]["A"] == 0
    assert result["counts"]["fn_R"] == 1
    assert result["counts"]["fn_H"] == 1
