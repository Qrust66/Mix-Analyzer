"""Pitch-range variety check — Phase 7-2 of composition_engine.

Detects monotonous pitch-range usage:
    - notes all clustered in <1 octave → static, no contour
    - no register shift across the timeline → no arc
    - peak/valley not aligned with phrase-shape

A "varied" track has:
    - >= 1 octave total range
    - identifiable arc (peak in middle, edges lower) OR clear directional motion (ascending/descending)

API:
    pitch_range(notes) → (min, max, span_semitones)
    pitch_arc_shape(notes, num_buckets) → list of mean-pitches per timeline bucket
    flag_static_range(notes) → diagnostic
"""

from typing import List, Dict, Any, Tuple


def pitch_range(notes: List[Dict[str, Any]]) -> Tuple[int, int, int]:
    """Return (min_pitch, max_pitch, span_semitones)."""
    if not notes:
        return (0, 0, 0)
    pitches = [n['pitch'] for n in notes]
    return (min(pitches), max(pitches), max(pitches) - min(pitches))


def pitch_arc_shape(notes: List[Dict[str, Any]],
                    num_buckets: int = 8) -> List[float]:
    """Compute mean pitch per timeline bucket (split track into N equal-time buckets).

    Args:
        notes: list of note dicts.
        num_buckets: how many timeline buckets to compute mean over.

    Returns:
        List of mean pitches (length=num_buckets). Empty buckets get None.
    """
    if not notes:
        return [None] * num_buckets
    sorted_notes = sorted(notes, key=lambda n: n['time'])
    total_dur = max(n['time'] + n['duration'] for n in sorted_notes)
    bucket_size = total_dur / num_buckets
    buckets = [[] for _ in range(num_buckets)]
    for n in sorted_notes:
        b = min(num_buckets - 1, int(n['time'] / bucket_size))
        buckets[b].append(n['pitch'])
    out = []
    for b in buckets:
        if b:
            out.append(round(sum(b) / len(b), 1))
        else:
            out.append(None)
    return out


def detect_arc_shape(arc: List[float]) -> str:
    """Classify the arc shape from a list of mean-pitches per bucket.

    Returns:
        'static'        — span < 3 semitones across buckets
        'ascending'     — monotonic rise
        'descending'    — monotonic fall
        'arc_up_down'   — peak somewhere in the middle, lower at edges
        'arc_down_up'   — valley somewhere in the middle, higher at edges
        'irregular'     — none of the above (mixed motion)
    """
    valid = [p for p in arc if p is not None]
    if len(valid) < 2:
        return 'static'
    span = max(valid) - min(valid)
    if span < 3:
        return 'static'

    # Check for monotonic motion
    is_asc = all(valid[i] <= valid[i+1] for i in range(len(valid) - 1))
    is_desc = all(valid[i] >= valid[i+1] for i in range(len(valid) - 1))
    if is_asc:
        return 'ascending'
    if is_desc:
        return 'descending'

    # Check for arc shape: peak in interior, lower at edges
    peak_idx = valid.index(max(valid))
    valley_idx = valid.index(min(valid))
    edges = [valid[0], valid[-1]]
    interior = valid[1:-1] if len(valid) > 2 else []

    if peak_idx not in (0, len(valid) - 1):
        # Peak in interior
        if max(edges) < max(valid):
            return 'arc_up_down'
    if valley_idx not in (0, len(valid) - 1):
        if min(edges) > min(valid):
            return 'arc_down_up'

    return 'irregular'


def flag_static_range(notes: List[Dict[str, Any]],
                      min_span_semitones: int = 7,
                      num_buckets: int = 8) -> Dict[str, Any]:
    """Flag tracks with static / narrow pitch range.

    A track is "static" if either:
        - total span < min_span_semitones (default 7 = perfect 5th)
        - arc_shape == 'static'

    Args:
        notes: list of note dicts.
        min_span_semitones: minimum acceptable total range.
        num_buckets: timeline buckets for arc analysis.

    Returns:
        {
          'is_static': bool,
          'span_semitones': int,
          'min_pitch': int,
          'max_pitch': int,
          'arc_shape': str,
          'arc': list,
          'reason': str (if static),
        }
    """
    lo, hi, span = pitch_range(notes)
    arc = pitch_arc_shape(notes, num_buckets)
    shape = detect_arc_shape(arc)
    is_static = span < min_span_semitones or shape == 'static'
    reason = ''
    if is_static:
        if span < min_span_semitones:
            reason = f'Span {span} semitones below {min_span_semitones}'
        else:
            reason = 'Arc shape is flat (static across timeline)'

    return {
        'is_static': is_static,
        'span_semitones': span,
        'min_pitch': lo,
        'max_pitch': hi,
        'arc_shape': shape,
        'arc': arc,
        'reason': reason,
    }


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    from composition_engine.motifs.melodic import MELODIC_MOTIFS, render

    print('=== Pitch-range/arc per melodic motif (single render) ===\n')
    for mid, m in MELODIC_MOTIFS.items():
        notes = render(m, tonic_pitch=50)
        diag = flag_static_range(notes, min_span_semitones=5, num_buckets=4)
        flag = '🚩 STATIC' if diag['is_static'] else f'✓ {diag["arc_shape"]:<14}'
        print(f'{flag:18s} {mid:50s} span={diag["span_semitones"]:2d}st  arc={diag["arc"]}')

    # Test on a longer composition (use composer demo)
    print('\n=== Range/arc on a longer composition (from composer demo, BASS track) ===')
    # Synthesize a longer ascending arc track
    asc = [{'time': i*1.0, 'duration': 0.5, 'velocity': 100, 'pitch': 50 + i*2}
           for i in range(8)]
    diag = flag_static_range(asc, min_span_semitones=5)
    print(f'  ascending track: {diag["arc_shape"]}, span={diag["span_semitones"]}')
    print(f'  arc: {diag["arc"]}')

    # Static track
    static = [{'time': i*0.5, 'duration': 0.25, 'velocity': 100, 'pitch': 60}
              for i in range(8)]
    diag = flag_static_range(static, min_span_semitones=5)
    print(f'\n  static track (all C4): {diag}')

    # Arc up-down
    arc_track = [
        {'time': 0, 'duration': 0.5, 'velocity': 100, 'pitch': 50},
        {'time': 0.5, 'duration': 0.5, 'velocity': 100, 'pitch': 53},
        {'time': 1.0, 'duration': 0.5, 'velocity': 100, 'pitch': 60},
        {'time': 1.5, 'duration': 0.5, 'velocity': 100, 'pitch': 65},
        {'time': 2.0, 'duration': 0.5, 'velocity': 100, 'pitch': 60},
        {'time': 2.5, 'duration': 0.5, 'velocity': 100, 'pitch': 53},
        {'time': 3.0, 'duration': 0.5, 'velocity': 100, 'pitch': 50},
    ]
    diag = flag_static_range(arc_track, min_span_semitones=5)
    print(f'\n  arc-up-down track: {diag["arc_shape"]}, span={diag["span_semitones"]}, arc={diag["arc"]}')
