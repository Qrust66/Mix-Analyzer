"""Tests for composition_engine.music_theory — note name → pitch / MIDI."""
import pytest

from composition_engine.music_theory import (
    KEY_ROOTS,
    key_root_to_midi,
    note_to_pitch_class,
)


# ============================================================================
# KEY_ROOTS contract
# ============================================================================


def test_key_roots_has_17_entries():
    """7 naturals + 5 sharps + 5 flats = 17. Drop any here = drop a sphere
    parser test (parametrized by KEY_ROOTS)."""
    assert len(KEY_ROOTS) == 17


def test_key_roots_includes_all_naturals():
    for note in ("C", "D", "E", "F", "G", "A", "B"):
        assert note in KEY_ROOTS


def test_key_roots_includes_sharps_and_flats():
    for note in ("C#", "Db", "D#", "Eb", "F#", "Gb", "G#", "Ab", "A#", "Bb"):
        assert note in KEY_ROOTS


def test_key_roots_excludes_double_accidentals():
    """We don't model Cbb / Fx (out of scope for corpus genres)."""
    for note in ("Cbb", "Fx", "Bbb", "F##"):
        assert note not in KEY_ROOTS


# ============================================================================
# note_to_pitch_class
# ============================================================================


@pytest.mark.parametrize("note,expected", [
    ("C", 0),
    ("C#", 1), ("Db", 1),
    ("D", 2),
    ("D#", 3), ("Eb", 3),
    ("E", 4),
    ("F", 5),
    ("F#", 6), ("Gb", 6),
    ("G", 7),
    ("G#", 8), ("Ab", 8),
    ("A", 9),
    ("A#", 10), ("Bb", 10),
    ("B", 11),
])
def test_note_to_pitch_class(note, expected):
    assert note_to_pitch_class(note) == expected


def test_note_to_pitch_class_raises_on_unknown():
    with pytest.raises(KeyError, match="Unknown note name"):
        note_to_pitch_class("H")  # German notation, not supported


def test_note_to_pitch_class_raises_on_empty():
    with pytest.raises(KeyError):
        note_to_pitch_class("")


def test_enharmonic_pairs_collapse_to_same_pitch_class():
    """C#/Db, D#/Eb, etc. must map to the same integer."""
    pairs = [("C#", "Db"), ("D#", "Eb"), ("F#", "Gb"), ("G#", "Ab"), ("A#", "Bb")]
    for sharp, flat in pairs:
        assert note_to_pitch_class(sharp) == note_to_pitch_class(flat), \
            f"{sharp} and {flat} should be enharmonic (same pitch class)"


# ============================================================================
# key_root_to_midi
# ============================================================================


@pytest.mark.parametrize("key_root,octave,expected", [
    ("C", 3, 48),
    ("C", 4, 60),       # middle C
    ("D", 3, 50),
    ("A", 3, 57),       # A3 — common reference
    ("A", 4, 69),       # A4 — standard tuning A
    ("F#", 3, 54),
    ("Gb", 3, 54),      # enharmonic with F#
    ("Bb", 3, 58),
    ("A#", 3, 58),      # enharmonic with Bb
])
def test_key_root_to_midi(key_root, octave, expected):
    assert key_root_to_midi(key_root, octave=octave) == expected


def test_key_root_to_midi_falls_back_to_C_on_unknown():
    """Defensive: prose data may have quirks. Don't crash the pipeline."""
    assert key_root_to_midi("???", octave=3) == 48  # C3
    assert key_root_to_midi("Am", octave=3) == 48   # mode-tagged → C
    assert key_root_to_midi("", octave=3) == 48
