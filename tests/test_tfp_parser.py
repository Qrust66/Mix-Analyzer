#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exhaustive tests for ``tfp_parser`` — Feature 3.5 Phase B1.

Covers every case listed in R1 (prefix parsing), R3 (Locator annotation
override parsing), and R4 (role resolution) of the Feature 3.5 spec. The
parser is a pure module with no audio dependency, so these tests run fast
and without stubbing.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tfp_parser import (  # noqa: E402
    DEFAULT_ROLE,
    Function,
    Importance,
    parse_tfp_overrides,
    parse_tfp_prefix,
    resolve_track_role,
)


# ===========================================================================
# R1 — parse_tfp_prefix : 12 cases from the spec table
# ===========================================================================

def test_R1_01_standard_format_parses_and_preserves_name():
    """[H/R] Kick 1 -> (H, R, "Kick 1") — canonical case."""
    result = parse_tfp_prefix("[H/R] Kick 1")
    assert result == (Importance.H, Function.R, "Kick 1")


def test_R1_02_lowercase_prefix_is_accepted_name_case_preserved():
    """[h/r] kick 1 -> (H, R, "kick 1") — codes case-insensitive, body preserved."""
    result = parse_tfp_prefix("[h/r] kick 1")
    assert result == (Importance.H, Function.R, "kick 1")


def test_R1_03_missing_space_after_bracket_rejected():
    """[H/R]Kick 1 -> None — R1 requires at least one whitespace after ']'."""
    assert parse_tfp_prefix("[H/R]Kick 1") is None


def test_R1_04_invalid_importance_or_function_code_rejected():
    """[X/Y] Kick 1 -> None — codes outside the taxonomy."""
    assert parse_tfp_prefix("[X/Y] Kick 1") is None


def test_R1_05_incomplete_format_rejected():
    """[H] Kick 1 -> None — missing slash-separated function dimension."""
    assert parse_tfp_prefix("[H] Kick 1") is None


def test_R1_06_no_prefix_returns_none_so_caller_applies_default():
    """Plain name -> None (caller falls back to DEFAULT_ROLE with a warning)."""
    assert parse_tfp_prefix("Kick 1") is None


def test_R1_07_second_bracket_is_part_of_the_clean_name():
    """[H/R] [draft] Kick 1 -> (H, R, "[draft] Kick 1") — only the FIRST
    bracket group is consumed, the rest is body."""
    result = parse_tfp_prefix("[H/R] [draft] Kick 1")
    assert result == (Importance.H, Function.R, "[draft] Kick 1")


def test_R1_08_leading_whitespace_is_trimmed_before_match():
    """  [H/R] Kick 1 -> (H, R, "Kick 1") — leading whitespace tolerated."""
    result = parse_tfp_prefix("  [H/R] Kick 1")
    assert result == (Importance.H, Function.R, "Kick 1")


def test_R1_09_all_function_codes_are_accepted_individually():
    """Smoke-check each of the 4 function codes in the full matrix."""
    for code, fn in [("R", Function.R), ("H", Function.H),
                      ("M", Function.M), ("T", Function.T)]:
        assert parse_tfp_prefix(f"[S/{code}] Track")[1] == fn


def test_R1_10_all_importance_codes_are_accepted_individually():
    """Smoke-check each of the 3 importance codes."""
    for code, imp in [("H", Importance.H), ("S", Importance.S),
                       ("A", Importance.A)]:
        assert parse_tfp_prefix(f"[{code}/R] Track")[0] == imp


def test_R1_11_empty_or_none_or_non_string_input_returns_none():
    """Defensive: None / empty / non-str must not crash."""
    assert parse_tfp_prefix("") is None
    assert parse_tfp_prefix("   ") is None
    assert parse_tfp_prefix(None) is None  # type: ignore[arg-type]
    assert parse_tfp_prefix(42) is None    # type: ignore[arg-type]


def test_R1_12_multiple_trailing_spaces_in_body_are_kept_verbatim():
    """Internal whitespace of the name is not normalised — caller may care."""
    result = parse_tfp_prefix("[H/R]  Kick 1  ")
    assert result is not None
    # The outer strip() on input removes trailing spaces, but the
    # mandatory single space between "]" and "Kick" plus any extras are
    # swallowed by \s+; the body starts at "Kick 1".
    assert result[2] == "Kick 1"


# ===========================================================================
# R3 — parse_tfp_overrides : 11 cases from the spec table
# ===========================================================================

def test_R3_01_importance_only_short_form_accepted():
    """override: Kick 1=S -> Kick 1 becomes Support, function unchanged (None)."""
    result = parse_tfp_overrides("override: Kick 1=S")
    assert result == {"Kick 1": (Importance.S, None)}


def test_R3_02_wildcard_function_only_override_accepted():
    """override: Kick 1=*-T -> Kick 1 becomes textural, importance unchanged."""
    result = parse_tfp_overrides("override: Kick 1=*-T")
    assert result == {"Kick 1": (None, Function.T)}


def test_R3_03_long_form_hero_rhythm_accepted_case_insensitive():
    """override: kick 1=hero-rhythm -> case-insensitive match on the words."""
    result = parse_tfp_overrides("override: kick 1=hero-rhythm")
    assert result == {"kick 1": (Importance.H, Function.R)}


def test_R3_04_spaces_around_equals_reject_only_the_bad_pair():
    """override: Kick 1 = S -> pair rejected (logged), dict empty."""
    result = parse_tfp_overrides("override: Kick 1 = S")
    assert result == {}


def test_R3_05_invalid_codes_are_rejected_per_pair():
    """override: Kick 1=X-Y -> pair rejected, empty dict."""
    result = parse_tfp_overrides("override: Kick 1=X-Y")
    assert result == {}


def test_R3_06_unknown_track_names_are_preserved_not_validated_here():
    """override: Inexistant=H -> parser cannot know about track names; it
    records the override verbatim. The consumer (resolve_track_role) sees
    that no real track matches and effectively drops the entry — the spec
    says this is a warning at consume time, not at parse time."""
    result = parse_tfp_overrides("override: Inexistant=H")
    assert result == {"Inexistant": (Importance.H, None)}


def test_R3_07_missing_space_after_colon_rejects_whole_clause():
    """override:Kick 1=S -> whole 'override:' clause ignored (R3 strict)."""
    result = parse_tfp_overrides("override:Kick 1=S")
    assert result == {}


def test_R3_08_two_overrides_both_applied():
    """override: Kick 1=S, Sub Bass=H -> both pairs parsed."""
    result = parse_tfp_overrides("override: Kick 1=S, Sub Bass=H")
    assert result == {
        "Kick 1": (Importance.S, None),
        "Sub Bass": (Importance.H, None),
    }


def test_R3_09_duplicate_track_last_value_wins():
    """override: Kick 1=S, Kick 1=A -> Kick 1 becomes A (last wins)."""
    result = parse_tfp_overrides("override: Kick 1=S, Kick 1=A")
    assert result == {"Kick 1": (Importance.A, None)}


def test_R3_10_empty_annotation_returns_empty_dict_no_warning():
    """Empty string / whitespace / None -> {} (no error, no warning)."""
    assert parse_tfp_overrides("") == {}
    assert parse_tfp_overrides("   ") == {}
    assert parse_tfp_overrides(None) == {}  # type: ignore[arg-type]


def test_R3_11_non_override_annotation_returns_empty_dict():
    """Annotation without 'override:' prefix -> ignored silently."""
    assert parse_tfp_overrides("Intro bass drop") == {}
    assert parse_tfp_overrides("note: check kick") == {}


# Bonus coverage: long-form full override + wildcard long-form
def test_R3_12_long_form_full_override_and_wildcard_long_form():
    result = parse_tfp_overrides(
        "override: Kick=support-textural, Snare=*-melodic"
    )
    assert result == {
        "Kick": (Importance.S, Function.T),
        "Snare": (None, Function.M),
    }


# ===========================================================================
# R4 — resolve_track_role : 5+ resolution cases
# ===========================================================================

def test_R4_01_prefix_only_no_override_keeps_base_role():
    """[H/R] Kick 1 with no overrides -> (H, R)."""
    result = resolve_track_role("[H/R] Kick 1", section_overrides={})
    assert result == (Importance.H, Function.R)


def test_R4_02_no_prefix_no_override_falls_to_default_SR():
    """Bare name with no override -> DEFAULT_ROLE (Support / Rhythm)."""
    result = resolve_track_role("New Track", section_overrides={})
    assert result == DEFAULT_ROLE == (Importance.S, Function.R)


def test_R4_03_full_override_replaces_both_dimensions():
    """Base [H/R], override A-T in this section -> (A, T)."""
    overrides = {"Kick 1": (Importance.A, Function.T)}
    result = resolve_track_role("[H/R] Kick 1", section_overrides=overrides)
    assert result == (Importance.A, Function.T)


def test_R4_04_importance_only_override_preserves_base_function():
    """Base [H/R], override importance=S -> (S, R) — function kept from prefix."""
    overrides = {"Kick 1": (Importance.S, None)}
    result = resolve_track_role("[H/R] Kick 1", section_overrides=overrides)
    assert result == (Importance.S, Function.R)


def test_R4_05_function_only_wildcard_override_preserves_base_importance():
    """Base [H/R], override *-T -> (H, T) — importance kept from prefix."""
    overrides = {"Kick 1": (None, Function.T)}
    result = resolve_track_role("[H/R] Kick 1", section_overrides=overrides)
    assert result == (Importance.H, Function.T)


def test_R4_06_override_takes_precedence_over_default_for_unprefixed_tracks():
    """R3 case: override applied to a track that has no global prefix —
    the override wins, default is bypassed for that section."""
    overrides = {"Kick 1": (Importance.H, Function.R)}
    result = resolve_track_role("Kick 1", section_overrides=overrides)
    assert result == (Importance.H, Function.R)


def test_R4_07_override_matching_is_case_insensitive():
    """Track 'Kick 1' (with Pascal case) resolves against override keyed 'kick 1'."""
    overrides = {"kick 1": (Importance.A, None)}
    result = resolve_track_role("[H/R] Kick 1", section_overrides=overrides)
    assert result == (Importance.A, Function.R)
