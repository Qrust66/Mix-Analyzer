"""Pitch transforms — Phase 2-1 of composition_engine.

All transforms operate on note-lists (output of motifs.*.render()):
    notes = [{'time': float, 'duration': float, 'velocity': int, 'pitch': int}, ...]

Returning a new transformed list (does not mutate input).

Transforms:
    transpose          — shift all pitches by N semitones
    invert             — mirror pitches around an axis pitch
    retrograde         — reverse time order (last note plays first)
    octave_jump        — shift specific notes by ±12 semitones
    fragment           — extract sub-sequence (re-zero timing)
    pitch_substitute_in_scale — swap pitches by scale-degree mapping

All transforms preserve the SCHEMA of input notes.
"""

from typing import List, Dict, Any, Callable, Set


def transpose(notes: List[Dict[str, Any]], semitones: int) -> List[Dict[str, Any]]:
    """Shift all pitches by N semitones (positive = up, negative = down).

    Args:
        notes: list of note dicts.
        semitones: integer shift amount.

    Returns:
        New list with shifted pitches.
    """
    return [{**n, 'pitch': n['pitch'] + semitones} for n in notes]


def invert(notes: List[Dict[str, Any]], axis_pitch: int) -> List[Dict[str, Any]]:
    """Mirror pitches around an axis pitch.

    For each note: new_pitch = 2 * axis_pitch - old_pitch
    (i.e., reflection across axis_pitch on the chromatic line)

    Args:
        notes: list of note dicts.
        axis_pitch: MIDI pitch around which to mirror.

    Returns:
        New list with inverted pitches. Time/duration/velocity unchanged.

    Example:
        invert([{pitch=64}], axis=60) → [{pitch=56}]   (E above middle C → G# below)
    """
    return [{**n, 'pitch': 2 * axis_pitch - n['pitch']} for n in notes]


def retrograde(notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reverse the time order of notes.

    The note that played LAST now plays FIRST. Pitches stay attached to their
    original durations, but timing is mirrored:
        new_time(n) = total_duration - old_time(n) - duration(n)

    where total_duration = max(time + duration) across all notes.

    Args:
        notes: list of note dicts.

    Returns:
        New list with reversed timing. Pitches/velocities/durations unchanged.
    """
    if not notes:
        return []
    total_dur = max(n['time'] + n['duration'] for n in notes)
    out = []
    for n in notes:
        new_time = total_dur - n['time'] - n['duration']
        out.append({**n, 'time': new_time})
    out.sort(key=lambda n: n['time'])
    return out


def octave_jump(notes: List[Dict[str, Any]], indices: List[int],
                octaves: int = 1) -> List[Dict[str, Any]]:
    """Shift specific notes (by index) up or down by N octaves.

    Used per advisor robot_rock_hypnotic_repetitive_riff_with_micro_variations:
    "octave-jump on last note every 8 bars".

    Args:
        notes: list of note dicts.
        indices: which notes to jump (0-indexed).
        octaves: number of octaves to shift (positive = up, negative = down).

    Returns:
        New list with selected notes octave-shifted.
    """
    idx_set = set(indices)
    out = []
    for i, n in enumerate(notes):
        if i in idx_set:
            out.append({**n, 'pitch': n['pitch'] + 12 * octaves})
        else:
            out.append({**n})
    return out


def fragment(notes: List[Dict[str, Any]], start_idx: int = 0,
             length: int = None, rezero_time: bool = True) -> List[Dict[str, Any]]:
    """Extract a sub-sequence of notes.

    Args:
        notes: list of note dicts (sorted by time).
        start_idx: starting index (inclusive).
        length: number of notes to extract (None = all from start_idx onward).
        rezero_time: if True, shift first note's time to 0.

    Returns:
        New list with extracted notes.
    """
    notes_sorted = sorted(notes, key=lambda n: n['time'])
    if length is None:
        sub = notes_sorted[start_idx:]
    else:
        sub = notes_sorted[start_idx:start_idx + length]
    if not sub:
        return []
    if rezero_time:
        offset = sub[0]['time']
        return [{**n, 'time': n['time'] - offset} for n in sub]
    return [{**n} for n in sub]


def pitch_substitute_in_scale(notes: List[Dict[str, Any]],
                              tonic_pitch: int,
                              scale_intervals: List[int],
                              substitutions: Dict[int, int]) -> List[Dict[str, Any]]:
    """Replace pitches by scale-degree substitution.

    For each note, compute its scale degree (interval from tonic % 12), check if
    that degree is in `substitutions`, and if so, replace with the substituted degree.

    Args:
        notes: list of note dicts.
        tonic_pitch: MIDI pitch of the tonal center.
        scale_intervals: list of intervals defining the scale (e.g. Aeolian = [0, 2, 3, 5, 7, 8, 10]).
        substitutions: dict mapping {old_interval: new_interval}.

    Returns:
        New list with substituted pitches.

    Example:
        # Convert Aeolian to Phrygian by replacing major-2 (interval 2) with minor-2 (interval 1):
        pitch_substitute_in_scale(notes, tonic_pitch=50,
                                  scale_intervals=[0,2,3,5,7,8,10],
                                  substitutions={2: 1})
        # Now any "E" (interval 2 above D) becomes "Eb" (interval 1 above D).
    """
    out = []
    for n in notes:
        # Compute interval from tonic (mod 12)
        interval = (n['pitch'] - tonic_pitch) % 12
        # Compute octave displacement
        octave_offset = (n['pitch'] - tonic_pitch - interval) // 12
        if interval in substitutions:
            new_interval = substitutions[interval]
            new_pitch = tonic_pitch + 12 * octave_offset + new_interval
            out.append({**n, 'pitch': new_pitch})
        else:
            out.append({**n})
    return out


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    import sys
    sys.path.insert(0, '/home/user/Mix-Analyzer')
    from composition_engine.motifs.melodic import MELODIC_MOTIFS, render

    # Render the canonical descending Aeolian motif in D minor
    motif = MELODIC_MOTIFS['aeolian_descending_4_steps']
    base = render(motif, tonic_pitch=50)
    print('=== Base: aeolian_descending_4_steps in Dm ===')
    for n in base:
        print(f'  pitch={n["pitch"]:3d}  time={n["time"]}  vel={n["velocity"]}')

    # Test transpose +5 (D minor → G minor)
    print('\n=== transpose +5 (G minor) ===')
    for n in transpose(base, 5):
        print(f'  pitch={n["pitch"]:3d}  time={n["time"]}  vel={n["velocity"]}')

    # Test invert around D (50)
    print('\n=== invert around D (axis=50) → ascending ===')
    for n in invert(base, 50):
        print(f'  pitch={n["pitch"]:3d}  time={n["time"]}  vel={n["velocity"]}')

    # Test retrograde (reverse)
    print('\n=== retrograde (reverse: A1 → Bb1 → C2 → D2) ===')
    for n in retrograde(base):
        print(f'  pitch={n["pitch"]:3d}  time={n["time"]}  vel={n["velocity"]}')

    # Test octave_jump on note 3 (last note)
    print('\n=== octave_jump on last note (index 3, +1 octave) ===')
    for n in octave_jump(base, indices=[3], octaves=1):
        print(f'  pitch={n["pitch"]:3d}  time={n["time"]}  vel={n["velocity"]}')

    # Test fragment first 2 notes
    print('\n=== fragment notes [0:2] ===')
    for n in fragment(base, start_idx=0, length=2):
        print(f'  pitch={n["pitch"]:3d}  time={n["time"]}  vel={n["velocity"]}')

    # Test pitch_substitute: Aeolian → Phrygian (replace ♭6 with ♭2)
    # In D minor (Aeolian = D-E-F-G-A-Bb-C), the ♭6 is Bb (interval 8 from D)
    # In D Phrygian (D-Eb-F-G-A-Bb-C), the ♭2 is Eb (interval 1 from D)
    # Wait — better example: replace the major 2nd (E, interval 2) with minor 2nd (Eb, interval 1)
    # to convert from Dorian/Aeolian to Phrygian
    # The base motif uses pitches D(50), C(48), Bb(46), A(45) — intervals 0, -2 (=10 mod 12), -4 (=8), -5 (=7)
    # So we have: tonic, ♭7, ♭6, 5 — already Aeolian. To make it more Phrygian, swap ♭6 (8) for ♭2...
    # Actually let's do something cleaner: swap the C (♭7, interval 10) for B (♮7, interval 11) → harmonic minor
    print('\n=== pitch_substitute: Aeolian → harmonic minor (♭7 → ♮7, swap interval 10 for 11) ===')
    for n in pitch_substitute_in_scale(base, tonic_pitch=50,
                                       scale_intervals=[0,2,3,5,7,8,10],
                                       substitutions={10: 11}):
        print(f'  pitch={n["pitch"]:3d}  time={n["time"]}  vel={n["velocity"]}')
