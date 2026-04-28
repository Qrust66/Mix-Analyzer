"""Tests for composition_engine.banque_bridge.banque_loader (Bloc 0.2).

The banque_midi_qrust.xlsx is hand-curated by the user. These tests pin
its structure (sheet names, expected counts, expected presence of known
profiles/scales/drums) so any future edit by the user that breaks the
loader's assumptions is caught immediately.
"""
import pytest

from composition_engine.banque_bridge.banque_loader import (
    get_drum_mapping,
    get_drum_note_for_role,
    get_meta,
    get_qrust_profile,
    get_rhythm_pattern,
    get_scale,
    get_tempo_for_genre,
    get_velocity_range,
    list_basslines,
    list_chord_progressions,
    list_qrust_profiles,
    list_qrust_starred_scales,
    list_rhythm_genres,
    list_scales,
    list_tempo_genres,
    load_banque,
    parse_intervals,
    parse_pattern_16,
)


# ============================================================================
# Top-level structure invariants (trip-wires for accidental sheet edits)
# ============================================================================


# Core sheets the loader's accessor functions depend on. Other sheets
# may be present (the user enriches the banque over time — v2 added
# 14 reference / theory sheets) — only the 8 below are load-bearing
# for the existing accessors.
REQUIRED_SHEETS = {
    "01_Drum_Mapping", "02_Rhythm_Patterns",
    "03_Scales_Modes", "04_Chord_Progressions", "05_Qrust_Profiles",
    "06_Velocity_Dynamics", "07_Tempo_Reference",
    "08_Bassline_Patterns",
}


def test_load_banque_includes_required_sheets():
    banque = load_banque()
    missing = REQUIRED_SHEETS - set(banque.keys())
    assert not missing, f"required sheets missing from banque: {missing}"


def test_meta_lists_all_sheets():
    meta = get_meta()
    # User's banque grows; only verify the loader sees ≥ 8 sheets and
    # that each required sheet is in the meta list.
    assert meta["sheet_count"] >= len(REQUIRED_SHEETS)
    assert REQUIRED_SHEETS <= set(meta["sheets"])


# ============================================================================
# 01 Drum mapping
# ============================================================================


def test_drum_mapping_covers_full_general_midi_drum_range():
    """Banque covers MIDI 35-64 (the standard GM drum range used by Ableton)."""
    drums = get_drum_mapping()
    midis = [d["midi"] for d in drums]
    assert min(midis) == 35
    assert max(midis) == 64
    assert len(set(midis)) == len(midis), "duplicate MIDI numbers"


def test_drum_canonical_kicks_resolve():
    """Kick principal must be MIDI 36 (Ableton convention)."""
    assert get_drum_note_for_role("kick") == 36
    assert get_drum_note_for_role("sub_kick") == 35


def test_drum_role_resolution_for_common_roles():
    assert get_drum_note_for_role("snare") == 38
    assert get_drum_note_for_role("hat") == 42
    assert get_drum_note_for_role("open_hat") == 46
    assert get_drum_note_for_role("clap") == 39


def test_drum_unknown_role_returns_none():
    assert get_drum_note_for_role("xylophone") is None


# ============================================================================
# 02 Rhythm patterns
# ============================================================================


def test_rhythm_genres_includes_known_genres():
    genres = list_rhythm_genres()
    # Sample known genres from the user's curation
    for expected in ("Techno (4x4)", "Dark techno",
                     "Industrial classic", "EBM (DAF/Front 242)",
                     "NIN (Reznor) heavy", "DnB (rolling)"):
        assert expected in genres, f"missing genre {expected!r}"


def test_rhythm_pattern_format_is_16_chars():
    """Each pattern_16 string must be exactly 16 characters of {X, g, a, .}."""
    rows = get_rhythm_pattern("Techno (4x4)")
    assert len(rows) > 0
    for r in rows:
        p = r["pattern_16"]
        assert len(p) == 16, f"pattern length {len(p)} for {r['element']!r}: {p!r}"
        assert all(c in "Xga." for c in p), f"unexpected chars in {p!r}"


def test_rhythm_pattern_filter_by_element():
    kicks = get_rhythm_pattern("Techno (4x4)", element="Kick")
    assert len(kicks) == 1
    assert "X" in kicks[0]["pattern_16"]


def test_parse_pattern_16_decodes_canonical_4x4():
    """Standard four-on-floor: hits on steps 0, 4, 8, 12."""
    events = parse_pattern_16("X...X...X...X...")
    assert len(events) == 4
    assert [e["step"] for e in events] == [0, 4, 8, 12]
    assert all(e["kind"] == "hit" for e in events)


def test_parse_pattern_16_distinguishes_ghost_and_accent():
    events = parse_pattern_16("Xg.aX...X...X...")
    kinds = [(e["step"], e["kind"]) for e in events]
    assert (0, "hit") in kinds
    assert (1, "ghost") in kinds
    assert (3, "accent") in kinds


def test_parse_pattern_16_silences_excluded():
    events = parse_pattern_16("................")
    assert events == []


# ============================================================================
# 03 Scales / modes
# ============================================================================


def test_scales_includes_all_diatonic_modes():
    names = {s["name"] for s in list_scales()}
    for mode in ("Ionien (Majeur)", "Dorien", "Phrygien", "Lydien",
                 "Mixolydien", "Aéolien (Mineur nat.)", "Locrien"):
        assert mode in names, f"missing diatonic mode {mode!r}"


def test_get_scale_phrygien_intervals():
    """Phrygien: 0,1,3,5,7,8,10 (root, b2, b3, 4, 5, b6, b7)."""
    s = get_scale("Phrygien")
    assert s is not None
    assert s["intervals"] == "0,1,3,5,7,8,10"
    assert "★★★" in s["qrust_rating"]  # 3-star Qrust scale


def test_qrust_3star_scales_include_dark_phrygian_family():
    starred = list_qrust_starred_scales(min_stars=3)
    names = {s["name"] for s in starred}
    # The user's dark/industrial backbone
    assert "Phrygien" in names
    assert "Locrien" in names
    assert "Phrygien dominant" in names


def test_parse_intervals_decodes_phrygian():
    assert parse_intervals("0,1,3,5,7,8,10") == (0, 1, 3, 5, 7, 8, 10)


def test_parse_intervals_chromatic_shorthand():
    assert parse_intervals("0..11") == tuple(range(12))


def test_parse_intervals_unparseable_returns_empty():
    assert parse_intervals("not numbers") == ()


# ============================================================================
# 04 Chord progressions
# ============================================================================


def test_chord_progressions_unfiltered_returns_many():
    progs = list_chord_progressions()
    assert len(progs) >= 15  # the user has documented 20+ progressions


def test_chord_progressions_filter_by_mood():
    dark_phr = list_chord_progressions(mood="Dark Phrygien")
    assert len(dark_phr) >= 1
    assert all(p["mood"] == "Dark Phrygien" for p in dark_phr)


# ============================================================================
# 05 Qrust profiles (full presets)
# ============================================================================


def test_qrust_profiles_includes_acid_drops():
    """Acid Drops is the canonical target profile per CLAUDE.md context."""
    p = get_qrust_profile("Acid Drops (cible)")
    assert p is not None
    assert p["tempo_sweet"] == 128
    assert "Phrygien" in p["scale"]


def test_qrust_profiles_all_have_required_fields():
    for p in list_qrust_profiles():
        assert p["name"]
        assert p["tempo_sweet"] is not None
        assert p["scale"]
        assert p["velocity_range"]


def test_qrust_profiles_includes_canonical_archetypes():
    names = {p["name"] for p in list_qrust_profiles()}
    expected_archetypes = {
        "Acid Drops (cible)",
        "Industrial groovy",
        "NIN heavy (Reznor)",
        "EBM driving",
        "Dark techno minimal",
    }
    assert expected_archetypes <= names


# ============================================================================
# 06 Velocity dynamics
# ============================================================================


def test_velocity_ranges_for_known_style():
    rows = get_velocity_range("NIN heavy")
    assert len(rows) >= 3  # kick, snare, hat
    for r in rows:
        assert 0 <= r["vel_min"] <= r["vel_max"] <= 127


def test_velocity_filter_by_element():
    rows = get_velocity_range("Acid Drops style", element="Kick")
    assert len(rows) == 1
    assert rows[0]["vel_min"] == 100
    assert rows[0]["vel_max"] == 118


# ============================================================================
# 07 Tempo reference
# ============================================================================


def test_tempo_for_acid_drops_genre():
    t = get_tempo_for_genre("ACID DROPS")
    assert t is not None
    assert t["tempo_min"] == 125
    assert t["tempo_max"] == 132
    assert t["sweet_spot"] == 128


def test_tempo_genres_list_is_non_empty():
    genres = list_tempo_genres()
    assert "Techno (4x4)" in genres
    assert "DnB" in genres
    assert "Ambient / Drone" in genres


def test_tempo_unknown_genre_returns_none():
    assert get_tempo_for_genre("ChiptuneFromMars") is None


# ============================================================================
# 08 Bassline patterns
# ============================================================================


def test_basslines_unfiltered_returns_styles():
    bb = list_basslines()
    styles = {b["style"] for b in bb}
    assert "Acid (303-style)" in styles
    assert "NIN-style heavy" in styles


def test_basslines_filter_by_style():
    acid = list_basslines("Acid Drops style")
    assert len(acid) == 1
    assert "1, 1, b2, 1" in acid[0]["degrees"]
