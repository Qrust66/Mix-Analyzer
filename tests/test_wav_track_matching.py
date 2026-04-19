#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for WAV-filename <-> Ableton-track-name matching."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from als_utils import match_track_name  # noqa: E402


# ---------------------------------------------------------------------------
# The Acid Drops bug: WAVs exported with "Acid_Drops " prefix, Ableton
# tracks named plainly — the old matcher missed everything.
# ---------------------------------------------------------------------------

def test_strips_project_prefix_space_separator():
    track_names = ["Bass Rythm", "Sub Bass", "Kick 1", "Pluck Lead"]
    assert match_track_name("Acid_Drops Bass Rythm", track_names) == "Bass Rythm"
    assert match_track_name("Acid_Drops Sub Bass", track_names) == "Sub Bass"
    assert match_track_name("Acid_Drops Kick 1", track_names) == "Kick 1"


def test_als_stem_hint_picks_specific_prefix():
    # Ambiguous case: "Drops Bass Rythm" COULD strip "Drops" AND match, but
    # supplying als_stem="Acid_Drops_Code" pins the intended prefix.
    track_names = ["Bass Rythm", "Drops Bass Rythm"]
    got = match_track_name(
        "Acid_Drops Bass Rythm",
        track_names,
        als_stem="Acid_Drops_Code",
    )
    assert got == "Bass Rythm"


def test_exact_match_wins_over_stripping():
    track_names = ["Acid_Drops Bass Rythm", "Bass Rythm"]
    # Exact match on the prefixed form must win.
    assert match_track_name("Acid_Drops Bass Rythm", track_names) == "Acid_Drops Bass Rythm"


def test_strips_leading_digits_group_number_form():
    track_names = ["Toms Rack", "Kick 1"]
    assert match_track_name("01 Toms Rack", track_names) == "Toms Rack"
    assert match_track_name("5-Toms Rack", track_names) == "Toms Rack"


def test_handles_als_track_with_leading_digits():
    # Ableton side has "5-Toms Rack", wav is plain "Toms Rack"
    track_names = ["5-Toms Rack"]
    assert match_track_name("Toms Rack", track_names) == "5-Toms Rack"


def test_no_match_returns_none():
    track_names = ["Bass Rythm", "Sub Bass"]
    assert match_track_name("Totally Unrelated Name", track_names) is None


def test_longest_suffix_wins_when_multiple_candidates():
    """Prefer the most specific (longest) matching suffix."""
    track_names = ["Rythm", "Bass Rythm"]
    # "Acid_Drops Bass Rythm" can strip to either "Bass Rythm" (longer, keep)
    # or to "Rythm" — the matcher must prefer the longest suffix.
    assert match_track_name("Acid_Drops Bass Rythm", track_names) == "Bass Rythm"


def test_substring_fallback_case_insensitive():
    track_names = ["Toms Overhead"]
    # WAV has "OverHead" (different case, different spacing) — fallback kicks in.
    got = match_track_name("Kit OverHead", track_names)
    assert got == "Toms Overhead"


def test_underscore_separator_between_prefix_and_track():
    track_names = ["Bass Rythm"]
    # Separator between prefix and track is an underscore instead of a space.
    got = match_track_name(
        "Acid_Drops_Bass Rythm", track_names, als_stem="Acid_Drops_Code"
    )
    assert got == "Bass Rythm"


def test_empty_candidates():
    assert match_track_name("Anything", []) is None


# ---------------------------------------------------------------------------
# Realistic Acid Drops end-to-end: 38 tracks all prefixed with "Acid_Drops "
# ---------------------------------------------------------------------------

def test_acid_drops_fullset_all_match():
    track_names = [
        "ARP Glitter Box", "ARP Intense", "Acid Bass", "Ambience",
        "Arp Roaming", "Bass Rythm", "Kick 1", "Kick 2", "NINja Lead",
        "Pluck Lead", "Sub Bass", "Toms Rack", "Voice FX Dark Wihispers",
    ]
    wav_stems = [f"Acid_Drops {t}" for t in track_names]
    missed = [
        stem for stem in wav_stems
        if match_track_name(stem, track_names, als_stem="Acid_Drops_Code") is None
    ]
    assert missed == [], f"expected all WAVs to match, missed: {missed}"

    # And every WAV must map back to its exact track
    for stem, expected in zip(wav_stems, track_names):
        assert (
            match_track_name(stem, track_names, als_stem="Acid_Drops_Code")
            == expected
        )
