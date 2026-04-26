"""Timing transforms — Phase 2-2 of composition_engine.

All transforms operate on note-lists. Pure functions, no input mutation.

Transforms:
    augment_diminish    — scale all timings (and durations) by a factor
    rhythmic_displace   — shift entire pattern by N beats
    swing_apply         — apply swing feel to 8th/16th note positions
    gate_length_vary    — modify note durations (legato/staccato spectrum)
"""

from typing import List, Dict, Any, Set


def augment_diminish(notes: List[Dict[str, Any]], factor: float) -> List[Dict[str, Any]]:
    """Scale all note timings AND durations by a factor.

    factor=2.0: stretches the pattern to twice its length (augmentation).
    factor=0.5: compresses to half the length (diminution).

    Args:
        notes: list of note dicts.
        factor: positive number to multiply timings + durations by.

    Returns:
        New list with scaled timing.
    """
    if factor <= 0:
        raise ValueError(f'factor must be positive, got {factor}')
    return [{**n, 'time': n['time'] * factor, 'duration': n['duration'] * factor}
            for n in notes]


def rhythmic_displace(notes: List[Dict[str, Any]], beats: float) -> List[Dict[str, Any]]:
    """Shift the entire pattern in time by N beats (positive = later, negative = earlier).

    Args:
        notes: list of note dicts.
        beats: shift amount in beats.

    Returns:
        New list with shifted timing. Durations unchanged.
    """
    return [{**n, 'time': n['time'] + beats} for n in notes]


def swing_apply(notes: List[Dict[str, Any]], swing_amount: float = 0.5,
                subdivision: float = 0.5) -> List[Dict[str, Any]]:
    """Apply swing feel to notes on the OFFBEATS of the chosen subdivision.

    For subdivision=0.5 (8th-note swing): notes at positions 0.5, 1.5, 2.5, 3.5
    (the "&" of each beat) get pushed LATER by `swing_amount * subdivision/2`.

    For subdivision=0.25 (16th-note swing): notes at positions 0.25, 0.75, 1.25, ...
    (every odd 16th-note) get pushed later.

    swing_amount=0.0 → no swing (straight)
    swing_amount=0.5 → moderate swing (offbeat sits ~25% later, classic shuffle)
    swing_amount=1.0 → full swing (offbeat at triplet position, ~33% delayed)

    Detection: a note is on an offbeat if its time-in-subdivision-units is ODD.
        unit_idx = round(time / subdivision)
        is_offbeat = (unit_idx % 2 == 1)

    Args:
        notes: list of note dicts.
        swing_amount: 0.0 to 1.0.
        subdivision: 0.5 (8ths), 0.25 (16ths), etc.

    Returns:
        New list with swung timing.
    """
    if not 0 <= swing_amount <= 1:
        raise ValueError(f'swing_amount must be in [0,1], got {swing_amount}')

    out = []
    shift = swing_amount * subdivision / 2
    for n in notes:
        unit_idx = round(n['time'] / subdivision)
        # Verify this note actually sits on a subdivision boundary (within tolerance)
        is_on_grid = abs(n['time'] - unit_idx * subdivision) < subdivision * 0.05
        if is_on_grid and unit_idx % 2 == 1:
            out.append({**n, 'time': n['time'] + shift})
        else:
            out.append({**n})
    return out


def gate_length_vary(notes: List[Dict[str, Any]],
                     gate_factor: float = None,
                     gate_per_index: Dict[int, float] = None) -> List[Dict[str, Any]]:
    """Modify note durations to control legato/staccato character.

    gate_factor=1.0 → no change (notes stay as-is)
    gate_factor=0.5 → staccato (half-length notes)
    gate_factor=0.8 → tenuto (slightly clipped)
    gate_factor=1.2 → legato (overlapping into next beat)

    Optional gate_per_index for per-note control (overrides gate_factor for those indices).

    Args:
        notes: list of note dicts.
        gate_factor: global gate-length multiplier (None = no global change).
        gate_per_index: dict {index: gate_factor} for per-note override.

    Returns:
        New list with adjusted durations.
    """
    out = []
    for i, n in enumerate(notes):
        f = gate_factor if gate_factor is not None else 1.0
        if gate_per_index and i in gate_per_index:
            f = gate_per_index[i]
        out.append({**n, 'duration': max(0.001, n['duration'] * f)})
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
    print('=== Base: aeolian_descending_4_steps in Dm ===')
    for n in base:
        print(f'  pitch={n["pitch"]}  time={n["time"]}  dur={n["duration"]}  vel={n["velocity"]}')

    # augment_diminish ×2 (slower)
    print('\n=== augment_diminish ×2 (twice as long) ===')
    for n in augment_diminish(base, 2.0):
        print(f'  pitch={n["pitch"]}  time={n["time"]}  dur={n["duration"]}')

    # augment_diminish ×0.5 (faster)
    print('\n=== augment_diminish ×0.5 (compressed) ===')
    for n in augment_diminish(base, 0.5):
        print(f'  pitch={n["pitch"]}  time={n["time"]}  dur={n["duration"]}')

    # rhythmic_displace +0.5 (push half a beat later)
    print('\n=== rhythmic_displace +0.5 (offset by half-beat) ===')
    for n in rhythmic_displace(base, 0.5):
        print(f'  pitch={n["pitch"]}  time={n["time"]}  dur={n["duration"]}')

    # Swing on 8ths — apply to vocoded motif which has 8ths at offbeats
    voc = render(MELODIC_MOTIFS['vocoded_phrase_call_response_2bar'], tonic_pitch=50)
    print('\n=== vocoded_phrase before swing ===')
    for n in voc[:4]:
        print(f'  time={n["time"]}  pitch={n["pitch"]}')
    print('\n=== vocoded_phrase swing 0.5 (moderate shuffle) ===')
    for n in swing_apply(voc, swing_amount=0.5)[:4]:
        print(f'  time={n["time"]}  pitch={n["pitch"]}')

    # gate_length_vary global 0.5 (staccato)
    print('\n=== gate_length_vary global 0.5 (staccato) ===')
    for n in gate_length_vary(base, gate_factor=0.5):
        print(f'  pitch={n["pitch"]}  time={n["time"]}  dur={n["duration"]}')

    # gate_length_vary per-index (note 0 staccato, note 3 legato)
    print('\n=== gate_length_vary per-index {0: 0.4, 3: 1.5} ===')
    for n in gate_length_vary(base, gate_per_index={0: 0.4, 3: 1.5}):
        print(f'  pitch={n["pitch"]}  time={n["time"]}  dur={n["duration"]}')
