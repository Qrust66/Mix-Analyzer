"""Duration variety check — Phase 7-1 of composition_engine.

Detects monotonous note-duration patterns. The Banger v2 critique was: every
note had the same duration → mechanical feel. Quality check should flag tracks
where note durations are TOO UNIFORM and recommend transforms.

A "varied" track has multiple distinct durations (8th, 16th, dotted-quarter,
half-note, etc.) and entropy/variance above a threshold.

API:
    duration_distribution(notes) → dict {duration: count}
    duration_entropy(notes) → bits (Shannon entropy of duration distribution)
    flag_monotonous(notes, threshold_bits) → bool + diagnostic
    recommend_variations(notes) → suggestions (apply gate_jitter / split notes / etc.)
"""

import math
from collections import Counter
from typing import List, Dict, Any


def duration_distribution(notes: List[Dict[str, Any]],
                          quantize: float = 0.0625) -> Dict[float, int]:
    """Histogram of note durations (rounded to nearest `quantize` beat).

    Args:
        notes: list of note dicts.
        quantize: round durations to this resolution (default 1/16 note).

    Returns:
        Dict {duration_beats: count}.
    """
    rounded = [round(n['duration'] / quantize) * quantize for n in notes]
    return dict(Counter(rounded))


def duration_entropy(notes: List[Dict[str, Any]],
                     quantize: float = 0.0625) -> float:
    """Shannon entropy of note-duration distribution (bits).

    entropy=0 → all notes same duration (monotonous)
    entropy=1 → 2 equally-frequent durations
    entropy=2 → 4 equally-frequent durations
    entropy=3 → 8 equally-frequent durations
    Higher = more variety.

    Args:
        notes: list of note dicts.
        quantize: round durations for histogram.

    Returns:
        Entropy in bits.
    """
    dist = duration_distribution(notes, quantize)
    total = sum(dist.values())
    if total == 0:
        return 0.0
    h = 0.0
    for count in dist.values():
        p = count / total
        if p > 0:
            h -= p * math.log2(p)
    return h


def flag_monotonous(notes: List[Dict[str, Any]],
                    threshold_bits: float = 1.0,
                    min_distinct_durations: int = 2,
                    quantize: float = 0.0625) -> Dict[str, Any]:
    """Flag tracks with monotonous note durations.

    A track is "monotonous" if either:
        - duration_entropy < threshold_bits, OR
        - distinct_durations < min_distinct_durations

    Args:
        notes: list of note dicts.
        threshold_bits: minimum acceptable entropy.
        min_distinct_durations: minimum distinct durations.
        quantize: histogram resolution.

    Returns:
        {
          'is_monotonous': bool,
          'entropy_bits': float,
          'distinct_durations': int,
          'distribution': dict,
          'reason': str (if monotonous),
        }
    """
    dist = duration_distribution(notes, quantize)
    entropy = duration_entropy(notes, quantize)
    distinct = len(dist)

    is_monotonous = entropy < threshold_bits or distinct < min_distinct_durations
    reason = ''
    if is_monotonous:
        if distinct < min_distinct_durations:
            reason = f'Only {distinct} distinct duration(s) (need {min_distinct_durations}+)'
        else:
            reason = f'Entropy {entropy:.2f} bits below threshold {threshold_bits}'

    return {
        'is_monotonous': is_monotonous,
        'entropy_bits': round(entropy, 3),
        'distinct_durations': distinct,
        'distribution': {k: v for k, v in sorted(dist.items())},
        'reason': reason,
    }


def recommend_variations(notes: List[Dict[str, Any]]) -> List[str]:
    """Suggest transforms to add duration variety.

    Returns: list of human-readable recommendations.
    """
    diag = flag_monotonous(notes)
    if not diag['is_monotonous']:
        return ['Already varied — no recommendation needed.']

    suggestions = []
    if diag['distinct_durations'] == 1:
        only_dur = list(diag['distribution'].keys())[0]
        suggestions.append(
            f'All notes are {only_dur} beats. Apply gate_length_vary(notes, '
            f'gate_per_index={{0: 0.5, 2: 1.5, ...}}) to introduce 2-3 distinct durations.'
        )
        suggestions.append(
            f'Apply humanize_gate_length(notes, jitter_pct=20) for ±20% variation '
            f'across all notes.'
        )
        # Identify ornaments
        if only_dur >= 0.5:
            suggestions.append(
                f'Notes are long (≥{only_dur}b). Consider add_grace_note or add_mordent '
                f'on a few accent notes to inject 16th/32nd-note details.'
            )
    elif diag['entropy_bits'] < 1.0:
        suggestions.append(
            f'Entropy {diag["entropy_bits"]} below 1.0 bit. Apply '
            f'humanize_gate_length to increase variation, OR layer with another '
            f'motif at different rhythmic density.'
        )

    return suggestions


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    from composition_engine.motifs.melodic import MELODIC_MOTIFS, render

    print('=== Test duration variety per motif ===\n')
    for mid, m in MELODIC_MOTIFS.items():
        notes = render(m, tonic_pitch=50)
        diag = flag_monotonous(notes, threshold_bits=1.0, min_distinct_durations=2)
        flag = '🚩 MONOTONOUS' if diag['is_monotonous'] else '✓ varied'
        print(f'{flag:18s} {mid:50s} entropy={diag["entropy_bits"]:.2f}b  distinct={diag["distinct_durations"]}')

    # Recommend variations for the canonical motif
    print('\n=== Recommendations for aeolian_descending_4_steps (all 1-beat notes) ===')
    notes = render(MELODIC_MOTIFS['aeolian_descending_4_steps'], tonic_pitch=50)
    print(f'Distribution: {duration_distribution(notes)}')
    for s in recommend_variations(notes):
        print(f'  - {s}')

    # Test a manually-monotonous track
    print('\n=== Synthetic flat 16th-note track ===')
    flat = [{'time': i*0.25, 'duration': 0.25, 'velocity': 100, 'pitch': 60} for i in range(16)]
    diag = flag_monotonous(flat)
    print(f'  is_monotonous: {diag["is_monotonous"]}')
    print(f'  reason: {diag["reason"]}')
    print(f'  distribution: {diag["distribution"]}')

    # Test a varied track
    print('\n=== Synthetic varied track (8 notes mixed durations) ===')
    varied = [
        {'time': 0, 'duration': 0.25, 'velocity': 100, 'pitch': 60},
        {'time': 0.25, 'duration': 0.5, 'velocity': 100, 'pitch': 62},
        {'time': 0.75, 'duration': 0.125, 'velocity': 100, 'pitch': 64},
        {'time': 0.875, 'duration': 1.0, 'velocity': 100, 'pitch': 65},
        {'time': 1.875, 'duration': 0.5, 'velocity': 100, 'pitch': 67},
        {'time': 2.375, 'duration': 0.0625, 'velocity': 100, 'pitch': 65},
        {'time': 2.4375, 'duration': 1.5, 'velocity': 100, 'pitch': 64},
        {'time': 3.9375, 'duration': 0.0625, 'velocity': 100, 'pitch': 60},
    ]
    diag = flag_monotonous(varied)
    print(f'  is_monotonous: {diag["is_monotonous"]}')
    print(f'  entropy: {diag["entropy_bits"]} bits')
    print(f'  distinct: {diag["distinct_durations"]} ({diag["distribution"]})')
