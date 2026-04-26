"""Harmonic progression library — Phase 1c of composition_engine.

A progression is a SEQUENCE OF CHORDS, each with root + voicing + duration.
All pitches are RELATIVE to a tonal center (tonic), so the progression can be
transposed to any key with a single parameter.

Schema:
    {
        'id': str,
        'sources': List[(artist, song, what)],
        'advisor_recipes': List[str],
        'mode': str,                 # 'aeolian' / 'phrygian' / 'dorian' / 'major' / etc.
        'chords': List[{
            'root_interval': int,    # semitones from tonic (0 = tonic, 5 = IV, 7 = V, 8 = ♭VI, 10 = ♭VII)
            'voicing': str,           # one of VOICINGS dict below
            'duration_beats': float,
            'roman': str,             # 'i', 'VI', 'VII', 'iv', etc. (lower = minor, upper = major)
            'inversion': int,         # 0 = root position, 1 = 1st inversion (3rd in bass), 2 = 2nd inv
        }],
        'duration_total_beats': float,
        'time_sig': Tuple[int, int],
        'character_tags': List[str],
        'transformations_allowed': List[str],
        'notes_on_use': str,
    }

Voicing dict: maps voicing-name -> list of interval offsets (semitones from chord root).
"""

from typing import List, Dict, Any, Tuple


VOICINGS: Dict[str, List[int]] = {
    # Triads
    'maj_triad': [0, 4, 7],            # major: root + maj3 + 5
    'min_triad': [0, 3, 7],            # minor: root + min3 + 5
    'dim_triad': [0, 3, 6],            # diminished: root + min3 + ♭5
    'aug_triad': [0, 4, 8],            # augmented: root + maj3 + #5

    # Power chords (no 3rd)
    'power': [0, 7],                   # root + 5
    'power_oct': [0, 7, 12],           # root + 5 + octave

    # Sus / quartal / quintal voicings
    'sus2': [0, 2, 7],                 # root + 2 + 5
    'sus4': [0, 5, 7],                 # root + 4 + 5
    'quartal': [0, 5, 10],             # stacked 4ths (root, 4th, ♭7) — contemporary jazz
    'quintal': [0, 7, 14],             # stacked 5ths (root, 5, 9 — open + ambiguous)

    # 7th chords
    'maj7': [0, 4, 7, 11],
    'min7': [0, 3, 7, 10],
    'dom7': [0, 4, 7, 10],
    'min_maj7': [0, 3, 7, 11],         # minor with major 7 (Hitchcock/dark color)
    'm7b5': [0, 3, 6, 10],             # half-diminished
    'dim7': [0, 3, 6, 9],              # fully diminished

    # Modal/extended
    'sus_4_with_9': [0, 2, 5, 7],      # sus4 with added 9 (modal openness, Eno tradition)
    'min_add9': [0, 3, 7, 14],         # minor + 9 (lush)
    'maj_add9': [0, 4, 7, 14],         # major + 9
    'maj9': [0, 4, 7, 11, 14],         # full maj9 (Veridis Quo / classical-electronic)
}


HARMONIC_PROGRESSIONS: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# AEOLIAN PROGRESSIONS — minor-key foundational
# ============================================================================

HARMONIC_PROGRESSIONS['aeolian_i_VI_VII_i'] = {
    'id': 'aeolian_i_VI_VII_i',
    'sources': [
        ('Nirvana', 'Dumb', 'Aeolian-rooted verse-chorus pad foundation'),
        ('Soundgarden', 'Head Down', 'modal voicings above drone — i-VI-VII-i family'),
        ('NIN', 'The Day The World Went Away', 'sustained Aeolian pad foundation'),
        ('Radiohead', 'Everything In Its Right Place', 'modal-Aeolian color palette'),
    ],
    'advisor_recipes': [
        'modal_voicings_above_drone_replace_chord_progression',
        'drone_foundation_as_compositional_anchor',
        'atmospheric_sustain_as_compositional_foundation',
        'sus_voicings_verse_with_drop_tuning_pedal',
    ],
    'mode': 'aeolian',
    # Dm – Bb – C – Dm (i – ♭VI – ♭VII – i)
    # Root intervals from D tonic: 0, 8, 10, 0
    # Major triads on ♭VI and ♭VII (Bb major, C major), minor triad on i (Dm)
    'chords': [
        {'root_interval': 0,  'voicing': 'min_triad', 'duration_beats': 4.0, 'roman': 'i',  'inversion': 0},
        {'root_interval': 8,  'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': 'VI', 'inversion': 0},
        {'root_interval': 10, 'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': 'VII','inversion': 0},
        {'root_interval': 0,  'voicing': 'min_triad', 'duration_beats': 4.0, 'roman': 'i',  'inversion': 0},
    ],
    'duration_total_beats': 16.0,   # 4 bars in 4/4
    'time_sig': (4, 4),
    'character_tags': ['aeolian', 'minor_modal', 'foundational', 'dark', 'cinematic', 'rock_modal'],
    'transformations_allowed': [
        'transpose',
        'voicing_swap',          # swap min_triad → sus2/sus4/min7 for color variation
        'inversion_swap',        # change inversions for voice-leading variation
        'augment_diminish',      # ×0.5 = 8-beat version, ×2 = 32-beat version
        'fragment',              # take 2-chord sub-sequence
    ],
    'notes_on_use': (
        'THE foundational minor-modal progression. Voice on Diva pad with slow attack '
        '(200-500ms) and long release (3-5sec) so chords BLEND. Pair with sustained tonic '
        'drone in sub-bass underneath (D1 if rendered in Dm). Each chord 4 beats = 1 bar '
        'in 4/4 — slow enough that voice-leading is audible. For voice-leading variation: '
        'use sus2 voicing on i (D-E-A) instead of triad — adds modal openness. Retrograde '
        'the progression once mid-track for harmonic surprise.'
    ),
}


# ============================================================================
# Render API — turn a harmonic progression into concrete MIDI notes
# ============================================================================

def render(progression: Dict[str, Any], tonic_pitch: int, start_beat: float = 0.0,
           octave_offset: int = 0, velocity: int = 90,
           voicing_override: Dict[int, str] = None) -> List[Dict[str, Any]]:
    """Render a harmonic progression into concrete MIDI notes.

    Each chord becomes a SET of simultaneous sustained notes (one per voicing-tone).

    Args:
        progression: a dict from HARMONIC_PROGRESSIONS
        tonic_pitch: MIDI pitch of the tonal center (e.g. 50 = D3)
        start_beat: where in the song this progression starts
        octave_offset: shift all chord-tones by N octaves
        velocity: base velocity (1-127) — clamped
        voicing_override: dict of chord_index -> voicing_name to override

    Returns:
        List of {'time', 'duration', 'velocity', 'pitch'} dicts.
    """
    notes = []
    cursor = start_beat
    for i, chord in enumerate(progression['chords']):
        root_pitch = tonic_pitch + chord['root_interval'] + 12 * octave_offset
        voicing_name = chord['voicing']
        if voicing_override and i in voicing_override:
            voicing_name = voicing_override[i]
        intervals = VOICINGS[voicing_name]
        # Apply inversion: rotate intervals so the Nth interval becomes the bass
        inv = chord.get('inversion', 0)
        if inv > 0 and inv < len(intervals):
            # Each rotation: lowest interval gets +12
            intervals = list(intervals)
            for _ in range(inv):
                lowest_idx = intervals.index(min(intervals))
                intervals[lowest_idx] += 12
        for iv in intervals:
            notes.append({
                'time': float(cursor),
                'duration': float(chord['duration_beats']),
                'velocity': max(1, min(127, int(velocity))),
                'pitch': int(root_pitch + iv),
            })
        cursor += chord['duration_beats']
    return notes


def list_progressions(filter_tags: List[str] = None,
                      filter_recipes: List[str] = None,
                      filter_mode: str = None) -> List[str]:
    """List progression IDs matching given filters."""
    out = []
    for pid, p in HARMONIC_PROGRESSIONS.items():
        if filter_tags and not any(t in p['character_tags'] for t in filter_tags):
            continue
        if filter_recipes and not any(r in p['advisor_recipes'] for r in filter_recipes):
            continue
        if filter_mode and p.get('mode') != filter_mode:
            continue
        out.append(pid)
    return out


# Self-test
if __name__ == '__main__':
    print(f'Harmonic progressions: {len(HARMONIC_PROGRESSIONS)}')
    print(f'Voicings available: {len(VOICINGS)}')
    for pid, p in HARMONIC_PROGRESSIONS.items():
        print(f'\n=== {pid} ===')
        print(f'  Mode: {p["mode"]}, total = {p["duration_total_beats"]} beats ({p["time_sig"]})')
        print(f'  Chord progression:')
        for c in p['chords']:
            print(f'    {c["roman"]:<5} root_offset={c["root_interval"]:+3d}  voicing={c["voicing"]:<12} dur={c["duration_beats"]}b inv={c["inversion"]}')

    # Render canonical progression in D minor (tonic_pitch=50 = D3)
    print('\n=== aeolian_i_VI_VII_i rendered in D minor at tonic D3 (50) ===')
    notes = render(HARMONIC_PROGRESSIONS['aeolian_i_VI_VII_i'], tonic_pitch=50, velocity=85)
    chord_times = sorted(set(n['time'] for n in notes))
    for t in chord_times:
        chord_notes = sorted([n['pitch'] for n in notes if n['time'] == t])
        print(f'  beat {t:5.1f}: pitches={chord_notes}')

    # Demo voicing_override: swap chord 0 to sus2
    print('\n=== Same progression with chord 0 voiced as sus2 ===')
    notes2 = render(HARMONIC_PROGRESSIONS['aeolian_i_VI_VII_i'], tonic_pitch=50, velocity=85,
                    voicing_override={0: 'sus2', 3: 'sus2'})
    chord_times = sorted(set(n['time'] for n in notes2))
    for t in chord_times:
        chord_notes = sorted([n['pitch'] for n in notes2 if n['time'] == t])
        print(f'  beat {t:5.1f}: pitches={chord_notes}')
