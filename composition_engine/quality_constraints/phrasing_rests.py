"""Phrasing rest check — Phase 7-3 of composition_engine.

Detects tracks that NEVER BREATHE — no rests between notes. The Banger v2
critique was: notes ran continuously back-to-back, no phrasing pauses, like
a never-stopping wall of noise.

A phrase that BREATHES has gaps between sub-phrases — moments where the
listener can hear the surrounding pad/silence. Quality check measures:
    - rest density (% of time with no notes active)
    - longest_continuous_block (max bars without a rest)
    - phrasing_quality (qualitative score)

API:
    rest_segments(notes, min_rest_beats) → list of (start, end) gaps
    rest_density(notes, total_duration) → 0.0-1.0 fraction of silent time
    flag_no_breath(notes, ...) → diagnostic
"""

from typing import List, Dict, Any, Tuple


def rest_segments(notes: List[Dict[str, Any]],
                  total_duration: float = None,
                  min_rest_beats: float = 0.25) -> List[Tuple[float, float]]:
    """Find continuous silence segments in a note-list.

    A rest is a span of time during which NO notes are active (sustaining or
    starting). Sustained notes from earlier still "occupy" their range.

    Args:
        notes: list of note dicts.
        total_duration: track duration (default = max note end).
        min_rest_beats: minimum gap to count as a rest (filters out micro-gaps).

    Returns:
        List of (rest_start_beat, rest_end_beat) tuples.
    """
    if not notes:
        return [(0, total_duration)] if total_duration else []

    sorted_notes = sorted(notes, key=lambda n: n['time'])
    if total_duration is None:
        total_duration = max(n['time'] + n['duration'] for n in sorted_notes)

    # Build occupancy events: for each note, mark start and end
    events = [(n['time'], 'on') for n in sorted_notes]
    events += [(n['time'] + n['duration'], 'off') for n in sorted_notes]
    events.sort()

    out = []
    active = 0
    last_silent_start = 0.0 if events[0][0] > 0 else None

    cursor = 0.0
    if events[0][0] > 0:
        # Track starts with silence
        last_silent_start = 0.0

    for time, kind in events:
        if kind == 'on':
            if active == 0 and last_silent_start is not None:
                # End of a silence span
                if time - last_silent_start >= min_rest_beats:
                    out.append((last_silent_start, time))
                last_silent_start = None
            active += 1
        else:
            active -= 1
            if active == 0:
                last_silent_start = time

    # Trailing silence
    if last_silent_start is not None and total_duration - last_silent_start >= min_rest_beats:
        out.append((last_silent_start, total_duration))

    return out


def rest_density(notes: List[Dict[str, Any]],
                 total_duration: float = None,
                 min_rest_beats: float = 0.25) -> float:
    """Fraction of total time spent in rests (0.0=never silent, 1.0=always silent).

    Args:
        notes: list of note dicts.
        total_duration: track length (default = max note end).
        min_rest_beats: minimum gap to count.

    Returns:
        Float in [0.0, 1.0].
    """
    if not notes:
        return 1.0
    if total_duration is None:
        total_duration = max(n['time'] + n['duration'] for n in notes)
    if total_duration <= 0:
        return 0.0
    rests = rest_segments(notes, total_duration, min_rest_beats)
    rest_total = sum(end - start for start, end in rests)
    return rest_total / total_duration


def longest_continuous_block(notes: List[Dict[str, Any]],
                             min_rest_beats: float = 0.25) -> float:
    """Length (in beats) of the longest period with NO rest >= min_rest_beats.

    Args:
        notes: list of note dicts.
        min_rest_beats: gap threshold.

    Returns:
        Length in beats of the longest no-rest stretch.
    """
    if not notes:
        return 0.0
    sorted_notes = sorted(notes, key=lambda n: n['time'])
    total_dur = max(n['time'] + n['duration'] for n in sorted_notes)
    rests = rest_segments(sorted_notes, total_dur, min_rest_beats)

    if not rests:
        return total_dur

    boundaries = [0.0]
    for start, end in rests:
        boundaries.append(start)
        boundaries.append(end)
    boundaries.append(total_dur)

    # Pair up: between rests, blocks are (boundary[i], boundary[i+1]) where i is even
    longest = 0.0
    for i in range(0, len(boundaries) - 1, 2):
        block_len = boundaries[i + 1] - boundaries[i]
        if block_len > longest:
            longest = block_len
    return longest


def flag_no_breath(notes: List[Dict[str, Any]],
                   total_duration: float = None,
                   min_rest_density: float = 0.10,
                   max_continuous_beats: float = 16.0,
                   min_rest_beats: float = 0.25) -> Dict[str, Any]:
    """Flag tracks that never breathe.

    A track is "no breath" if either:
        - rest_density < min_rest_density (default 10% silence)
        - longest_continuous_block > max_continuous_beats (4 bars without rest)

    Args:
        notes: list of note dicts.
        total_duration: track length.
        min_rest_density: minimum % silence (default 0.10 = 10%).
        max_continuous_beats: max no-rest block (default 16 = 4 bars).
        min_rest_beats: gap threshold.

    Returns:
        Diagnostic dict.
    """
    if total_duration is None:
        total_duration = max((n['time'] + n['duration'] for n in notes), default=0)

    density = rest_density(notes, total_duration, min_rest_beats)
    longest = longest_continuous_block(notes, min_rest_beats)
    rests = rest_segments(notes, total_duration, min_rest_beats)

    is_no_breath = density < min_rest_density or longest > max_continuous_beats
    reason = ''
    if is_no_breath:
        if density < min_rest_density:
            reason = f'Rest density {density:.1%} below minimum {min_rest_density:.0%}'
        else:
            reason = f'Longest continuous block {longest:.1f} beats exceeds max {max_continuous_beats}'

    return {
        'is_no_breath': is_no_breath,
        'rest_density': round(density, 3),
        'longest_continuous_beats': round(longest, 2),
        'rest_count': len(rests),
        'rests_first_5': rests[:5],
        'reason': reason,
    }


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    # Test 1: dense track (no rests)
    print('=== Test 1: dense 16th-note 4-bar track (no rests) ===')
    dense = [{'time': i * 0.25, 'duration': 0.25, 'velocity': 100, 'pitch': 60}
             for i in range(64)]
    diag = flag_no_breath(dense, total_duration=16.0)
    print(f'  is_no_breath: {diag["is_no_breath"]}')
    print(f'  rest_density: {diag["rest_density"]}')
    print(f'  longest continuous: {diag["longest_continuous_beats"]}')
    print(f'  reason: {diag["reason"]}')

    # Test 2: phrased track (4 phrases of 1 bar each, with 1-beat rests between)
    print('\n=== Test 2: phrased track (4 × 3-beat phrase + 1-beat rest = 16 beats) ===')
    phrased = []
    for phrase in range(4):
        offset = phrase * 4
        for i in range(3):
            phrased.append({
                'time': offset + i * 1.0,
                'duration': 1.0,
                'velocity': 100, 'pitch': 60,
            })
    diag = flag_no_breath(phrased, total_duration=16.0)
    print(f'  is_no_breath: {diag["is_no_breath"]}')
    print(f'  rest_density: {diag["rest_density"]}')
    print(f'  rest_count: {diag["rest_count"]}')
    print(f'  rests: {diag["rests_first_5"]}')

    # Test 3: vocoded_phrase from motif library (has 2-beat rest built in)
    print('\n=== Test 3: vocoded_phrase_call_response_2bar (has 2-beat call/response gap) ===')
    from composition_engine.motifs.melodic import MELODIC_MOTIFS, render
    voc = render(MELODIC_MOTIFS['vocoded_phrase_call_response_2bar'], tonic_pitch=50)
    diag = flag_no_breath(voc)
    print(f'  is_no_breath: {diag["is_no_breath"]}')
    print(f'  rest_density: {diag["rest_density"]}')
    print(f'  rest_count: {diag["rest_count"]}')
    print(f'  rests: {diag["rests_first_5"]}')

    # Test 4: full motif library scan
    print('\n=== Phrasing per melodic motif (single render) ===\n')
    for mid, m in MELODIC_MOTIFS.items():
        notes = render(m, tonic_pitch=50)
        diag = flag_no_breath(notes, min_rest_density=0.10, max_continuous_beats=8)
        flag = '🚩 NO_BREATH' if diag['is_no_breath'] else '✓ breathes  '
        print(f'{flag} {mid:50s} rest_density={diag["rest_density"]:.2f}  longest_block={diag["longest_continuous_beats"]:.1f}b')
