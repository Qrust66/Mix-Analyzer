"""Polyrhythm primitives — Phase 3-3 of composition_engine.

Polyrhythms = patterns that imply a different pulse than the underlying meter.
ALL operate WITHIN 4/4 (mono-meter per user constraint) — the polyrhythm is in
the NOTE PLACEMENT, not the time-signature.

Examples:
    3-against-4: 3 evenly-spaced hits across 4 beats (the canonical advisor
                 syncopated_kick {0, 1.333, 2.666} — but advisor's docs say
                 {0, 0.75, 1.5, 2.25} which is actually 4-evenly-in-3 inverted)
    5-against-4: 5 evenly-spaced hits across 4 beats
    Hemiola: 3 dotted-quarters ≈ 4.5 quarters → wraps differently each bar

Primitives:
    polyrhythm_n_against_4   — generate N evenly-spaced hits across 4 beats
    hemiola                  — generate dotted-quarter pulse over 4/4 (3 dotted-q in 6 beats)
    layer_polyrhythms        — superpose 2+ polyrhythmic streams (with cohesion check)
    cohesion_check           — verify all streams agree on a SHARED downbeat anchor
"""

from typing import List, Dict, Any


def polyrhythm_n_against_4(n_hits: int,
                           pitch: int,
                           num_bars: int = 1,
                           velocity: int = 100,
                           hit_duration: float = 0.25,
                           start_beat: float = 0.0) -> List[Dict[str, Any]]:
    """Generate N evenly-spaced hits across `num_bars * 4` beats.

    n_hits=3 → 3-against-4 polyrhythm (each hit at intervals of 4/3 beats)
    n_hits=5 → 5-against-4 polyrhythm (each hit at intervals of 4/5 beats)
    n_hits=7 → 7-against-4 polyrhythm

    Args:
        n_hits: number of hits to fit in `num_bars * 4` beats.
        pitch: MIDI pitch for all hits (single-pitch polyrhythm).
        num_bars: how many bars (default 1 = 4 beats).
        velocity: base velocity, downbeat-anchored hit gets +10 boost.
        hit_duration: each hit's duration.
        start_beat: where the polyrhythm begins.

    Returns:
        List of N notes evenly spaced.

    Note: Only hits at positions 0, 4, 8, ... (start of each bar) get the +10
    velocity accent — this anchors the polyrhythm to the underlying 4/4.
    """
    if n_hits < 1:
        raise ValueError(f'n_hits must be >= 1, got {n_hits}')

    total_beats = num_bars * 4
    interval = total_beats / n_hits

    out = []
    for i in range(n_hits):
        t = start_beat + i * interval
        # Anchor accent: if this hit lands ON a beat boundary (within 0.05 tolerance), boost
        beat_in_bar = (t - start_beat) % 4
        is_anchored = abs(beat_in_bar - round(beat_in_bar)) < 0.05
        v = velocity + 12 if is_anchored else velocity
        out.append({
            'time': float(t),
            'duration': float(hit_duration),
            'velocity': max(1, min(127, int(v))),
            'pitch': int(pitch),
        })
    return out


def hemiola(pitch: int,
            num_bars: int = 2,
            velocity: int = 100,
            hit_duration: float = 0.25,
            start_beat: float = 0.0) -> List[Dict[str, Any]]:
    """Generate a hemiola: dotted-quarter pulse (1.5 beats apart) running through 4/4.

    Standard hemiola: 4 dotted-quarter hits = 6 beats = 1.5 bars in 4/4.
    With num_bars=2 (8 beats), you get 5 hits across the 8 beats with the cycle
    wrapping in the 5th — natural polyrhythmic tension.

    The hemiola creates a "3-feel inside 4-feel" because each hit is a dotted
    quarter (3 eighth-notes), but the bar is 8 eighths.

    Args:
        pitch: MIDI pitch for all hits.
        num_bars: how many bars (default 2 = 8 beats).
        velocity: base velocity.
        hit_duration: hit duration in beats.
        start_beat: where to start.

    Returns:
        Hemiola hits at intervals of 1.5 beats.
    """
    total_beats = num_bars * 4
    interval = 1.5
    out = []
    t = start_beat
    while t < start_beat + total_beats:
        # Anchor accent on ON-beat-boundary hits
        beat_in_bar = (t - start_beat) % 4
        is_anchored = abs(beat_in_bar - round(beat_in_bar)) < 0.05
        v = velocity + 12 if is_anchored else velocity
        out.append({
            'time': float(t),
            'duration': float(hit_duration),
            'velocity': max(1, min(127, int(v))),
            'pitch': int(pitch),
        })
        t += interval
    return out


def layer_polyrhythms(*streams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Superpose multiple rhythmic streams into a single combined note-list.

    Used for layering kick (4-on-floor) + hi-hat (16ths) + perc (3-against-4)
    where each stream lives at its own pitch but they share the same time-grid.

    Args:
        *streams: multiple note-lists.

    Returns:
        Combined note list (sorted by time).
    """
    out = []
    for stream in streams:
        out.extend({**n} for n in stream)
    out.sort(key=lambda n: n['time'])
    return out


def cohesion_check(streams: List[List[Dict[str, Any]]],
                   bar_length_beats: float = 4.0,
                   tolerance: float = 0.05) -> Dict[str, Any]:
    """Verify all streams agree on the SHARED downbeat (cohesion of polyrhythmic layering).

    For each stream, finds the earliest hit AT a downbeat (time = N × bar_length).
    Returns whether all streams have at least one hit per downbeat — the anchor
    that lets listeners "find the 1" even with polyrhythmic complexity above.

    Args:
        streams: list of note-lists.
        bar_length_beats: bar length (default 4.0 = 4/4).
        tolerance: timing tolerance for "on-downbeat" check.

    Returns:
        Dict with diagnostic info:
            'streams_anchored': how many streams have at least one downbeat hit
            'downbeats_covered': list of downbeat times where ≥1 stream hits
            'fully_cohesive': bool — True if all bars in span have anchor coverage
    """
    if not streams:
        return {'streams_anchored': 0, 'downbeats_covered': [], 'fully_cohesive': True}

    # Find time span
    all_notes = [n for s in streams for n in s]
    if not all_notes:
        return {'streams_anchored': 0, 'downbeats_covered': [], 'fully_cohesive': True}

    max_time = max(n['time'] + n['duration'] for n in all_notes)
    num_bars = int(max_time / bar_length_beats) + 1
    downbeats = [b * bar_length_beats for b in range(num_bars)]

    streams_anchored = 0
    for stream in streams:
        for n in stream:
            on_downbeat = any(abs(n['time'] - d) < tolerance for d in downbeats)
            if on_downbeat:
                streams_anchored += 1
                break

    downbeats_covered = []
    for d in downbeats:
        covered = any(any(abs(n['time'] - d) < tolerance for n in s) for s in streams)
        if covered:
            downbeats_covered.append(d)

    fully_cohesive = len(downbeats_covered) == num_bars

    return {
        'streams_anchored': streams_anchored,
        'downbeats_covered': downbeats_covered,
        'fully_cohesive': fully_cohesive,
        'num_bars': num_bars,
    }


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    KICK = 36
    PERC = 41   # low tom for percussive layer
    HAT = 42

    # Test 1: 3-against-4
    print('=== 3-against-4 polyrhythm (kick) ===')
    p3 = polyrhythm_n_against_4(n_hits=3, pitch=KICK, num_bars=1, velocity=100)
    for n in p3:
        print(f'  time={n["time"]:.4f}  pitch={n["pitch"]}  vel={n["velocity"]}')

    # Test 2: 5-against-4
    print('\n=== 5-against-4 polyrhythm (perc) ===')
    p5 = polyrhythm_n_against_4(n_hits=5, pitch=PERC, num_bars=1, velocity=100)
    for n in p5:
        print(f'  time={n["time"]:.4f}  pitch={n["pitch"]}  vel={n["velocity"]}')

    # Test 3: Hemiola
    print('\n=== Hemiola (1.5-beat pulse over 2 bars) ===')
    h = hemiola(pitch=PERC, num_bars=2, velocity=95)
    for n in h:
        print(f'  time={n["time"]:.4f}  pitch={n["pitch"]}  vel={n["velocity"]}')

    # Test 4: Layered polyrhythms — 4-on-floor kick + 3-against-4 perc + 16th hats
    print('\n=== Layered: 4-on-floor kick (every beat) + 3-against-4 perc + 16ths hat ===')
    kick_4on4 = polyrhythm_n_against_4(n_hits=4, pitch=KICK, num_bars=1, velocity=110)
    perc_3on4 = polyrhythm_n_against_4(n_hits=3, pitch=PERC, num_bars=1, velocity=85)
    hat_16ths = polyrhythm_n_against_4(n_hits=16, pitch=HAT, num_bars=1, velocity=70, hit_duration=0.0625)

    combined = layer_polyrhythms(kick_4on4, perc_3on4, hat_16ths)
    print(f'Combined: {len(combined)} hits across {max(n["time"] for n in combined):.2f} beats')

    # Test 5: Cohesion check
    print('\n=== cohesion_check ===')
    coh = cohesion_check([kick_4on4, perc_3on4, hat_16ths])
    print(f'  Streams with downbeat anchor: {coh["streams_anchored"]} of 3')
    print(f'  Downbeats covered: {coh["downbeats_covered"]}')
    print(f'  Fully cohesive: {coh["fully_cohesive"]}')

    # Test 6: Polyrhythm WITHOUT proper anchor (3-against-4 starting at 0.5)
    print('\n=== 3-against-4 starting at 0.5 (NO downbeat anchor) ===')
    p3_offset = polyrhythm_n_against_4(n_hits=3, pitch=KICK, num_bars=1, velocity=100, start_beat=0.5)
    coh2 = cohesion_check([p3_offset])
    print(f'  Cohesive: {coh2["fully_cohesive"]} (single stream, NOT on downbeat 0)')
