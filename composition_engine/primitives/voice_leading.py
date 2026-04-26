"""Voice-leading primitives — Phase 3-2 of composition_engine.

Voice-leading = the smooth motion of individual voices (lines) between chord changes.
Good voice-leading = each voice moves by SMALL INTERVALS (step-wise or by 3rd)
between consecutive chords; AVOIDS large leaps; AVOIDS parallel 5ths/octaves.

Primitives:
    smooth_voice_to_nearest      — given a chord, transpose voicing to minimize movement from prior chord
    extract_voice_line           — pull a single voice (e.g. soprano) out of a chord-progression render
    apply_voice_leading_to_progression — automatic voice-leading on a chord-progression
    inverse_chord_for_smoothness — find the chord inversion that minimizes voice movement
"""

from typing import List, Dict, Any, Tuple


def _chord_distance(chord_a: List[int], chord_b: List[int]) -> int:
    """Sum of absolute pitch differences between two chord-pitch sets, matched greedily.

    Lower distance = smoother voice-leading.
    """
    if len(chord_a) != len(chord_b):
        # If sizes differ, pad the smaller with the highest pitch from the larger
        # (a voice "rests" — not perfect but pragmatic)
        return abs(len(chord_a) - len(chord_b)) * 12 + sum(abs(a - b) for a, b in zip(sorted(chord_a), sorted(chord_b)))
    return sum(abs(a - b) for a, b in zip(sorted(chord_a), sorted(chord_b)))


def smooth_voice_to_nearest(chord_pitches: List[int],
                            prior_chord_pitches: List[int]) -> List[int]:
    """Transpose chord_pitches by octaves so that the voicing is as close as possible
    to prior_chord_pitches (minimizes total voice-movement).

    Tries octave displacements (-2, -1, 0, +1, +2) on EACH note independently
    and returns the configuration with smallest total motion.

    Args:
        chord_pitches: list of MIDI pitches in a chord (any order).
        prior_chord_pitches: list of MIDI pitches of the PREVIOUS chord.

    Returns:
        List of pitches re-octaved to minimize movement from prior chord.

    Example:
        # Prior chord: C major in root position [60, 64, 67]
        # New chord: F major root position [65, 69, 72] — large jump
        # Smoothed: [65, 69, 72] → maybe re-octave F to 53, A to 57: result [53, 57, 60]
        # Now common tone (C=60) preserved, F+A move down by 5+7 = 12 (smaller than 27)
    """
    if not prior_chord_pitches or not chord_pitches:
        return list(chord_pitches)

    # For each note in chord_pitches, try octave shifts (-2, -1, 0, +1, +2) and pick the one closest to ANY prior pitch
    best = []
    for p in chord_pitches:
        candidates = [p + 12 * o for o in (-2, -1, 0, 1, 2)]
        # Pick the candidate closest to the closest prior_pitch
        best_cand = min(candidates, key=lambda c: min(abs(c - q) for q in prior_chord_pitches))
        best.append(best_cand)

    return best


def extract_voice_line(notes: List[Dict[str, Any]],
                       which_voice: str = 'soprano') -> List[Dict[str, Any]]:
    """Extract a single voice line from a chord-progression render.

    For each chord (notes sharing the same start time), picks a single pitch:
        'soprano' = highest pitch
        'alto'    = second-highest
        'tenor'   = second-lowest
        'bass'    = lowest pitch

    Args:
        notes: list of note dicts (chord-progression render).
        which_voice: 'soprano' / 'alto' / 'tenor' / 'bass'.

    Returns:
        List of single notes representing the chosen voice line.
    """
    # Group notes by start time
    chords = {}
    for n in notes:
        chords.setdefault(n['time'], []).append(n)

    out = []
    for t, chord in sorted(chords.items()):
        chord_sorted = sorted(chord, key=lambda n: n['pitch'])
        if which_voice == 'bass':
            picked = chord_sorted[0]
        elif which_voice == 'tenor':
            picked = chord_sorted[1] if len(chord_sorted) > 1 else chord_sorted[0]
        elif which_voice == 'alto':
            picked = chord_sorted[-2] if len(chord_sorted) > 1 else chord_sorted[-1]
        elif which_voice == 'soprano':
            picked = chord_sorted[-1]
        else:
            raise ValueError(f'unknown voice {which_voice!r}')
        out.append({**picked})
    return out


def apply_voice_leading_to_progression(progression_notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply automatic smooth voice-leading to a rendered chord-progression.

    For each chord (after the first), re-octave its pitches to minimize movement
    from the previous chord. The first chord stays as-is; each subsequent chord
    is "voice-led" toward smoothness.

    Args:
        progression_notes: list of note dicts from a rendered HARMONIC_PROGRESSIONS.

    Returns:
        New list with voice-leading applied. Chord identities preserved (same
        scale degrees), but specific octave placements optimized.
    """
    # Group notes by start time
    chord_groups: List[Tuple[float, List[Dict[str, Any]]]] = []
    by_time = {}
    for n in progression_notes:
        by_time.setdefault(n['time'], []).append(n)
    for t in sorted(by_time.keys()):
        chord_groups.append((t, by_time[t]))

    out = []
    prev_pitches = None
    for t, chord in chord_groups:
        cur_pitches = [n['pitch'] for n in chord]
        if prev_pitches is None:
            # First chord stays as-is
            new_pitches = cur_pitches
        else:
            new_pitches = smooth_voice_to_nearest(cur_pitches, prev_pitches)
        # Reconstruct notes (preserve duration + velocity)
        for i, n in enumerate(chord):
            out.append({**n, 'pitch': new_pitches[i]})
        prev_pitches = new_pitches

    return out


def inverse_chord_for_smoothness(chord_pitches: List[int],
                                  prior_chord_pitches: List[int]) -> List[int]:
    """Find the inversion (rotation) of chord_pitches that minimizes voice-movement.

    Different from smooth_voice_to_nearest: this tries the standard inversions
    (root position, 1st inv, 2nd inv, etc.) by rotating which pitch is in the bass.

    Args:
        chord_pitches: chord pitches in any order.
        prior_chord_pitches: previous chord's pitches.

    Returns:
        Re-arranged pitches (same notes, different octave-spread) that minimize
        movement from prior chord.
    """
    sorted_p = sorted(chord_pitches)
    n = len(sorted_p)
    best = sorted_p
    best_dist = _chord_distance(sorted_p, prior_chord_pitches)

    for inv in range(1, n):
        # Inversion: lift the lowest `inv` pitches by 12
        candidate = sorted([p + 12 if i < inv else p for i, p in enumerate(sorted_p)])
        dist = _chord_distance(candidate, prior_chord_pitches)
        if dist < best_dist:
            best = candidate
            best_dist = dist

    return best


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    import sys
    sys.path.insert(0, '/home/user/Mix-Analyzer')
    from composition_engine.motifs.harmonic import HARMONIC_PROGRESSIONS, render

    # Render Aeolian progression in D minor
    progression = HARMONIC_PROGRESSIONS['aeolian_i_VI_VII_i']
    notes = render(progression, tonic_pitch=50)

    print('=== Chord-progression aeolian_i_VI_VII_i in Dm (no voice-leading) ===')
    chord_times = sorted(set(n['time'] for n in notes))
    for t in chord_times:
        pitches = sorted(n['pitch'] for n in notes if n['time'] == t)
        print(f'  beat {t:5.1f}: {pitches}')

    # Apply voice-leading
    print('\n=== After apply_voice_leading_to_progression ===')
    smoothed = apply_voice_leading_to_progression(notes)
    for t in chord_times:
        pitches = sorted(n['pitch'] for n in smoothed if n['time'] == t)
        print(f'  beat {t:5.1f}: {pitches}')

    # Compute total voice-movement before vs. after
    def total_movement(progression_notes):
        chords = {}
        for n in progression_notes:
            chords.setdefault(n['time'], []).append(n['pitch'])
        chords_sorted = [sorted(chords[t]) for t in sorted(chords.keys())]
        total = 0
        for i in range(len(chords_sorted) - 1):
            total += _chord_distance(chords_sorted[i], chords_sorted[i + 1])
        return total

    print(f'\nTotal voice-movement BEFORE voice-leading: {total_movement(notes)} semitones')
    print(f'Total voice-movement AFTER voice-leading:  {total_movement(smoothed)} semitones')

    # Test extract_voice_line
    print('\n=== Soprano line extracted from smoothed progression ===')
    soprano = extract_voice_line(smoothed, which_voice='soprano')
    print(f'Soprano pitches: {[n["pitch"] for n in soprano]}')
    print(f'Soprano times:   {[n["time"] for n in soprano]}')

    print('\n=== Bass line ===')
    bass = extract_voice_line(smoothed, which_voice='bass')
    print(f'Bass pitches: {[n["pitch"] for n in bass]}')

    # Test inverse_chord_for_smoothness
    print('\n=== inverse_chord_for_smoothness ===')
    dm = [50, 53, 57]    # Dm root position
    bb = [58, 62, 65]    # Bb root position
    print(f'Dm → Bb without inversion: distance = {_chord_distance(dm, bb)}')
    bb_smooth = inverse_chord_for_smoothness(bb, dm)
    print(f'Bb after smoothing: {bb_smooth}, distance = {_chord_distance(dm, bb_smooth)}')
