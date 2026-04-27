"""Music theory primitives — single source of truth for note names,
pitch classes, and MIDI mapping used across the composition_engine.

Before Phase 2.3.1, this lived as duplicated tables in:
  - composition_engine/blueprint/composer_adapter.py (_NOTE_TO_PITCH_CLASS)
  - composition_engine/blueprint/agent_parsers.py    (_VALID_KEY_ROOTS)

Tests also hardcoded the 17-name list. Drift between these would silently
corrupt the composer (a key the parser rejects might still slip through
some other path). Centralizing them makes the contract explicit.
"""
from __future__ import annotations


# ============================================================================
# The 17 canonical note names accepted as `key_root` throughout the project
# ============================================================================
#
# Includes both flat and sharp spellings of black keys (C#/Db, D#/Eb, F#/Gb,
# G#/Ab, A#/Bb). Excludes double-flat/sharp (Cbb, Fx) and exotic enharmonics
# (Edb) — out of scope for the genres in the corpus (rock, electronic).

_NOTE_TO_PITCH_CLASS: dict[str, int] = {
    "C":  0,
    "C#": 1, "Db": 1,
    "D":  2,
    "D#": 3, "Eb": 3,
    "E":  4,
    "F":  5,
    "F#": 6, "Gb": 6,
    "G":  7,
    "G#": 8, "Ab": 8,
    "A":  9,
    "A#": 10, "Bb": 10,
    "B":  11,
}

KEY_ROOTS: frozenset[str] = frozenset(_NOTE_TO_PITCH_CLASS)


# ============================================================================
# Conversion functions
# ============================================================================


def note_to_pitch_class(note: str) -> int:
    """Return the pitch class (0..11) for a note name.

    Raises KeyError if the note is not in KEY_ROOTS.
    """
    if note not in _NOTE_TO_PITCH_CLASS:
        raise KeyError(
            f"Unknown note name {note!r}. Expected one of: {sorted(KEY_ROOTS)}"
        )
    return _NOTE_TO_PITCH_CLASS[note]


def key_root_to_midi(key_root: str, octave: int = 3) -> int:
    """Convert a key-root letter + octave to a MIDI pitch.

    'A' at octave 3 → 57 (A3, MIDI standard). 'C' at 4 → 60 (middle C).
    'F#' at 3 → 54.

    Defensive: falls back to C if `key_root` is unrecognized — prose data
    from the corpus may have formatting quirks ('F#m', 'A minor'). Strict
    validation happens in the agent_parsers layer; this function is the
    last-mile resolver and should not crash the rendering pipeline on
    upstream slop.
    """
    pitch_class = _NOTE_TO_PITCH_CLASS.get(key_root, 0)
    # MIDI: C-1 = 0, so C{octave} = 12 * (octave + 1) + 0
    return 12 * (octave + 1) + pitch_class


__all__ = [
    "KEY_ROOTS",
    "note_to_pitch_class",
    "key_root_to_midi",
]
