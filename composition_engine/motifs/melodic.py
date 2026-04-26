"""Melodic motif library — Phase 1a of composition_engine.

Each motif is a CONTOUR + RHYTHM + CHARACTER, encoded with INTERVAL-RELATIVE pitches
(semitones from tonal center) so transposition is trivial. Cut & assemble friendly:
each motif is a SHORT fragment (1-4 bars) drawn from MULTIPLE source songs
documented in the advisor (anti-copyright by construction — no motif is a literal
copy of a single source phrase).

Schema:
    {
        'id': str,                              # snake_case unique identifier
        'sources': List[(artist, song, what)],   # multi-source provenance
        'advisor_recipes': List[str],            # which composition_advisor recipes
        'pitch_intervals_from_tonic': List[int], # semitones (negative = below tonic)
        'rhythm_beats': List[(start, duration)], # in beats; (4,4) default time-sig
        'velocity_contour': List[int],           # 1-127, parallel to pitch list
        'character_tags': List[str],             # 'descending', 'aeolian', 'lament', ...
        'duration_total_beats': float,
        'time_sig': Tuple[int, int],
        'transformations_allowed': List[str],
        'notes_on_use': str,
    }

Three lists (pitch_intervals, rhythm_beats, velocity_contour) MUST be same length.
"""

from typing import List, Tuple, Dict, Any


MELODIC_MOTIFS: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# DESCENDING MOTIFS — Aeolian / Phrygian / chromatic
# ============================================================================

MELODIC_MOTIFS['aeolian_descending_4_steps'] = {
    'id': 'aeolian_descending_4_steps',
    'sources': [
        ('Nirvana', 'All Apologies', 'verse vocal: D-C-Bb-A descending Aeolian phrase'),
        ('Soundgarden', 'Head Down', 'modal motion descending above drone'),
        ('Daft Punk', 'Veridis Quo', 'classical-influenced descending bass anchor'),
        ('Smashing Pumpkins', 'Soma', 'verse melodic descent before explosion'),
    ],
    'advisor_recipes': [
        'descending_riff_as_song_identity',
        'modal_voicings_above_drone_replace_chord_progression',
        'classical_influenced_chord_progression_in_electronic_context',
    ],
    # D minor relative: 1-♭7-♭6-5 = 0, -2, -4, -5 semitones (D, C, Bb, A)
    'pitch_intervals_from_tonic': [0, -2, -4, -5],
    # 1 beat each, total 4 beats = 1 bar in 4/4
    'rhythm_beats': [(0.0, 1.0), (1.0, 1.0), (2.0, 1.0), (3.0, 1.0)],
    'velocity_contour': [110, 100, 95, 92],   # softening descent — natural decay
    'character_tags': ['descending', 'aeolian', 'lament', 'foundational'],
    'duration_total_beats': 4.0,
    'time_sig': (4, 4),
    'transformations_allowed': [
        'transpose',           # change tonic
        'invert',              # mirror around tonic
        'retrograde',          # reverse direction
        'fragment',            # take any sub-sequence
        'octave_jump',         # shift any single note ±12
        'rhythmic_displace',   # shift all timing by N beats
        'augment_diminish',    # scale duration ×0.5 / ×2
    ],
    'notes_on_use': (
        'Foundational lament gesture. Strongest as bass-line at slow tempo (60-100 BPM) '
        'or as vocal/lead phrase at mid-tempo (100-130 BPM). Pairs with sustained drone '
        'on tonic. Becomes "robot_rock" engine when looped with micro-variations every '
        '4-8 bars (octave-jump on last note, retrograde once per 16-bar cycle).'
    ),
}


# ============================================================================
# Render API — turn a motif into concrete MIDI notes
# ============================================================================

def render(motif: Dict[str, Any], tonic_pitch: int, start_beat: float = 0.0,
           octave_offset: int = 0, velocity_scale: float = 1.0) -> List[Dict[str, Any]]:
    """Render a motif into a list of concrete MIDI notes.

    Args:
        motif: a dict from MELODIC_MOTIFS
        tonic_pitch: MIDI pitch of the tonal center (e.g. 50 = D3)
        start_beat: where in the song this motif starts (0.0 = bar 1 beat 1)
        octave_offset: shift all pitches by N octaves (±12 semitones each)
        velocity_scale: multiply velocities by this (clamped 1-127)

    Returns:
        List of {'time', 'duration', 'velocity', 'pitch'} dicts ready for MIDI.
    """
    notes = []
    for i, interval in enumerate(motif['pitch_intervals_from_tonic']):
        rel_start, dur = motif['rhythm_beats'][i]
        vel = motif['velocity_contour'][i]
        notes.append({
            'time': float(start_beat + rel_start),
            'duration': float(dur),
            'velocity': max(1, min(127, int(vel * velocity_scale))),
            'pitch': int(tonic_pitch + interval + 12 * octave_offset),
        })
    return notes


def list_motifs(filter_tags: List[str] = None,
                filter_recipes: List[str] = None) -> List[str]:
    """List motif IDs matching given character tags or advisor recipes."""
    out = []
    for mid, m in MELODIC_MOTIFS.items():
        if filter_tags and not any(t in m['character_tags'] for t in filter_tags):
            continue
        if filter_recipes and not any(r in m['advisor_recipes'] for r in filter_recipes):
            continue
        out.append(mid)
    return out


# Self-test
if __name__ == '__main__':
    print(f'Melodic motifs: {len(MELODIC_MOTIFS)}')
    for mid, m in MELODIC_MOTIFS.items():
        print(f'\n=== {mid} ===')
        print(f'  Sources: {len(m["sources"])} ({", ".join(s[0] for s in m["sources"])})')
        print(f'  Advisor recipes: {m["advisor_recipes"]}')
        print(f'  Tags: {m["character_tags"]}')
        # Render in D minor at quarter note
        rendered = render(m, tonic_pitch=50, start_beat=0)
        print(f'  Rendered in D minor:')
        for n in rendered:
            print(f'    pitch={n["pitch"]} time={n["time"]} dur={n["duration"]} vel={n["velocity"]}')
