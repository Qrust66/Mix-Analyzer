"""Velocity transforms — Phase 2-3 of composition_engine.

All transforms operate on note-lists. Pure functions, no input mutation.

Transforms:
    velocity_scale          — multiply all velocities by a factor (clamp 1-127)
    velocity_contour_apply  — apply a shape (cresc/decresc/arc/plateau) across the pattern
    humanize_velocity       — add random ±N to each velocity (deterministic with seed)
    accent_pattern          — boost specific indices (advisor robot_rock accent every Nth)
"""

import random
from typing import List, Dict, Any, Set


def velocity_scale(notes: List[Dict[str, Any]], factor: float) -> List[Dict[str, Any]]:
    """Multiply all velocities by a factor, clamp to MIDI range 1-127.

    factor=0.5 → quieter (half volume)
    factor=1.5 → louder (50% boost)

    Args:
        notes: list of note dicts.
        factor: positive multiplier.

    Returns:
        New list with scaled velocities.
    """
    if factor <= 0:
        raise ValueError(f'factor must be positive, got {factor}')
    return [{**n, 'velocity': max(1, min(127, int(round(n['velocity'] * factor))))}
            for n in notes]


def velocity_contour_apply(notes: List[Dict[str, Any]],
                           shape: str = 'flat',
                           low: int = 60, high: int = 120) -> List[Dict[str, Any]]:
    """Apply a velocity shape across the note-sequence.

    Shapes:
        'flat'         — all velocities = (low+high)/2
        'cresc'        — linear ramp low → high (crescendo)
        'decresc'      — linear ramp high → low (decrescendo)
        'arc'          — low → high → low (peak in middle, like a phrase shape)
        'arc_inverted' — high → low → high (valley)
        'climax'       — exponential ramp toward end (advisor pre_chorus_arc style)
        'release'      — sudden drop on the last note (cathartic release end-of-phrase)

    Args:
        notes: list of note dicts (sorted by time recommended).
        shape: one of the names above.
        low: minimum velocity (1-127).
        high: maximum velocity (1-127).

    Returns:
        New list with contoured velocities.
    """
    n = len(notes)
    if n == 0:
        return []

    if shape == 'flat':
        v = (low + high) // 2
        return [{**note, 'velocity': v} for note in notes]

    new_velocities = []
    for i in range(n):
        if n == 1:
            t = 0.5
        else:
            t = i / (n - 1)   # 0.0 at start, 1.0 at end

        if shape == 'cresc':
            v = low + (high - low) * t
        elif shape == 'decresc':
            v = high - (high - low) * t
        elif shape == 'arc':
            # Triangular: peak at t=0.5
            v = low + (high - low) * (1 - 2 * abs(t - 0.5))
        elif shape == 'arc_inverted':
            # Valley: bottom at t=0.5
            v = high - (high - low) * (1 - 2 * abs(t - 0.5))
        elif shape == 'climax':
            # Exponential climb: stays low until late, then accelerates
            v = low + (high - low) * (t ** 2)
        elif shape == 'release':
            # Stay high, drop on last note
            v = high if i < n - 1 else low
        else:
            raise ValueError(f'unknown shape {shape!r}')

        new_velocities.append(max(1, min(127, int(round(v)))))

    return [{**notes[i], 'velocity': new_velocities[i]} for i in range(n)]


def humanize_velocity(notes: List[Dict[str, Any]],
                      jitter: int = 8,
                      rng_seed: int = None) -> List[Dict[str, Any]]:
    """Add random ±jitter to each note's velocity for human-feel.

    Different jitter every call (random) unless rng_seed is given (reproducible).
    Clamps to MIDI range 1-127.

    Args:
        notes: list of note dicts.
        jitter: max absolute deviation (e.g. 8 → ±8).
        rng_seed: optional seed for reproducibility.

    Returns:
        New list with humanized velocities.
    """
    rng = random.Random(rng_seed) if rng_seed is not None else random.Random()
    out = []
    for n in notes:
        delta = rng.randint(-jitter, jitter)
        out.append({**n, 'velocity': max(1, min(127, n['velocity'] + delta))})
    return out


def accent_pattern(notes: List[Dict[str, Any]],
                   accent_every: int = 4,
                   accent_offset: int = 0,
                   accent_boost: int = 20) -> List[Dict[str, Any]]:
    """Boost the velocity of every Nth note (period accent).

    Used per advisor recipes for hi-hat accents on every 4th 16th-note (downbeat
    accent), or for snare ghost-vs-primary contrast.

    accent_every=4, accent_offset=0 → boost notes at indices 0, 4, 8, ... (on downbeats)
    accent_every=4, accent_offset=2 → boost notes at indices 2, 6, 10, ... (on offbeats)
    accent_every=2, accent_offset=0 → alternating (every other note)

    Args:
        notes: list of note dicts.
        accent_every: period of accents.
        accent_offset: starting index for accents.
        accent_boost: amount to add to accented velocities.

    Returns:
        New list with accented velocities.
    """
    out = []
    for i, n in enumerate(notes):
        if (i - accent_offset) % accent_every == 0 and i >= accent_offset:
            new_vel = max(1, min(127, n['velocity'] + accent_boost))
        else:
            new_vel = n['velocity']
        out.append({**n, 'velocity': new_vel})
    return out


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    import sys
    sys.path.insert(0, '/home/user/Mix-Analyzer')
    from composition_engine.motifs.melodic import MELODIC_MOTIFS, render

    motif = MELODIC_MOTIFS['aeolian_descending_4_steps']
    base = render(motif, tonic_pitch=50)
    print('=== Base velocities ===', [n['velocity'] for n in base])

    print('\nvelocity_scale 0.7:    ', [n['velocity'] for n in velocity_scale(base, 0.7)])
    print('velocity_scale 1.5:    ', [n['velocity'] for n in velocity_scale(base, 1.5)])

    print('\nvelocity_contour cresc 60→120:    ', [n['velocity'] for n in velocity_contour_apply(base, 'cresc', 60, 120)])
    print('velocity_contour decresc 120→60:  ', [n['velocity'] for n in velocity_contour_apply(base, 'decresc', 60, 120)])
    print('velocity_contour arc 50→125:      ', [n['velocity'] for n in velocity_contour_apply(base, 'arc', 50, 125)])
    print('velocity_contour climax 60→125:   ', [n['velocity'] for n in velocity_contour_apply(base, 'climax', 60, 125)])
    print('velocity_contour release 100→40:  ', [n['velocity'] for n in velocity_contour_apply(base, 'release', 40, 100)])

    print('\nhumanize ±8 (seed=42):  ', [n['velocity'] for n in humanize_velocity(base, jitter=8, rng_seed=42)])
    print('humanize ±8 (seed=42):  ', [n['velocity'] for n in humanize_velocity(base, jitter=8, rng_seed=42)], '(reproducible)')

    # Accent test on a longer pattern
    pre_chorus = render(MELODIC_MOTIFS['pre_chorus_ascending_arc'], tonic_pitch=50)
    print(f'\npre_chorus_ascending_arc velocities: {[n["velocity"] for n in pre_chorus]}')
    accented = accent_pattern(pre_chorus, accent_every=2, accent_offset=0, accent_boost=15)
    print(f'accent_pattern every 2 (+15):       {[n["velocity"] for n in accented]}')

    # Complete pipeline: cresc + humanize
    print('\n=== Pipeline: velocity_contour_apply(cresc) → humanize_velocity ===')
    step1 = velocity_contour_apply(base, 'cresc', 60, 120)
    step2 = humanize_velocity(step1, jitter=5, rng_seed=99)
    print('Final:', [n['velocity'] for n in step2])
