"""Rhythmic humanization — Phase 4-1 of composition_engine.

Tempo-aware humanization of note-lists. Converts ms-based jitter (advisor specs)
to beat-based jitter using BPM. Implements the documented robot_rock rules
(timing jitter, velocity jitter, occasional skip/double per cycle).

Functions:
    ms_to_beats(ms, bpm)              — convert ms to beats for given tempo
    humanize_timing(notes, jitter_ms, tempo_bpm, rng_seed)
    humanize_gate_length(notes, jitter_pct, rng_seed)
    apply_motif_loop_humanization     — workhorse: render rhythmic motif N times
                                         with per-cycle micro_variation_rules
"""

import random
from typing import List, Dict, Any, Callable


def ms_to_beats(ms: float, bpm: float) -> float:
    """Convert milliseconds to beats at the given BPM.

    1 beat = 60/BPM seconds = 60000/BPM ms
    → 1 ms = BPM/60000 beats

    Args:
        ms: time in milliseconds (can be negative).
        bpm: tempo in beats per minute.

    Returns:
        Equivalent duration in beats.

    Example:
        ms_to_beats(15, 120) = 0.030 (15ms at 120 BPM = 0.030 beat)
        ms_to_beats(15, 108) = 0.027 (15ms at 108 BPM = 0.027 beat)
    """
    return ms * bpm / 60000.0


def humanize_timing(notes: List[Dict[str, Any]],
                    jitter_ms: float = 10.0,
                    tempo_bpm: float = 108.0,
                    rng_seed: int = None,
                    preserve_first_downbeat: bool = True) -> List[Dict[str, Any]]:
    """Apply tempo-aware random timing jitter (±jitter_ms) to each note.

    The first downbeat hit (time=0.0 within tolerance) is OPTIONALLY preserved
    so the start of a phrase stays on-grid (typical convention).

    Args:
        notes: list of note dicts.
        jitter_ms: max absolute deviation in milliseconds.
        tempo_bpm: tempo for ms→beats conversion.
        rng_seed: optional seed for reproducibility.
        preserve_first_downbeat: if True, notes at time≈0.0 stay exact.

    Returns:
        New list with humanized timing.
    """
    if jitter_ms < 0:
        raise ValueError(f'jitter_ms must be non-negative, got {jitter_ms}')

    rng = random.Random(rng_seed) if rng_seed is not None else random.Random()
    jitter_beats_max = ms_to_beats(jitter_ms, tempo_bpm)

    out = []
    for n in notes:
        if preserve_first_downbeat and abs(n['time']) < 0.001:
            out.append({**n})
            continue
        delta_ms = rng.uniform(-jitter_ms, jitter_ms)
        delta_beats = ms_to_beats(delta_ms, tempo_bpm)
        out.append({**n, 'time': max(0.0, n['time'] + delta_beats)})
    return out


def humanize_gate_length(notes: List[Dict[str, Any]],
                         jitter_pct: float = 15.0,
                         rng_seed: int = None,
                         min_duration: float = 0.0625) -> List[Dict[str, Any]]:
    """Apply random ±jitter_pct% variation to each note's duration (gate length).

    Used to add "played" feel — staccato-tenuto micro-variation per note.
    Each note's duration is multiplied by a random factor in
    (1 - jitter_pct/100, 1 + jitter_pct/100).

    Args:
        notes: list of note dicts.
        jitter_pct: max % variation (default 15 → ±15%).
        rng_seed: optional seed.
        min_duration: floor on resulting duration (default 1/16 note = 0.0625 beat).

    Returns:
        New list with varied gate-lengths.
    """
    if jitter_pct < 0:
        raise ValueError(f'jitter_pct must be non-negative')

    rng = random.Random(rng_seed) if rng_seed is not None else random.Random()
    out = []
    for n in notes:
        factor = 1.0 + rng.uniform(-jitter_pct, jitter_pct) / 100.0
        new_dur = max(min_duration, n['duration'] * factor)
        out.append({**n, 'duration': new_dur})
    return out


def apply_motif_loop_humanization(motif: Dict[str, Any],
                                  num_cycles: int,
                                  cycle_duration_beats: float,
                                  tempo_bpm: float = 108.0,
                                  start_beat: float = 0.0,
                                  pitch_override: int = None,
                                  velocity_scale: float = 1.0,
                                  apply_micro_variations: bool = True,
                                  rng_seed_base: int = None,
                                  pitch_variation_callback: Callable = None) -> List[Dict[str, Any]]:
    """Render a rhythmic motif N times applying its micro_variation_rules per cycle.

    Each cycle gets:
        - Different timing jitter seed (cycle_index used)
        - Different velocity jitter
        - occasional_skip rule applied per cycle (when cycle_index matches)
        - occasional_double rule applied per cycle
        - Optional pitch_variation_callback(notes, cycle_idx) for advisor's
          melodic-side rules (octave-jump every 4 cycles, etc.)

    This is the workhorse for Phase 6 composer to render rhythmic tracks that
    BREATHE — different per cycle, never identical.

    Args:
        motif: dict from RHYTHMIC_MOTIFS (must have micro_variation_rules).
        num_cycles: how many times to repeat.
        cycle_duration_beats: bar length per cycle (e.g. 4.0 for 4/4).
        tempo_bpm: tempo for ms→beats conversion.
        start_beat: where the first cycle starts.
        pitch_override: if given, replace the motif's drum_pitch.
        velocity_scale: global velocity multiplier.
        apply_micro_variations: enable robot_rock-style breathing.
        rng_seed_base: base seed (each cycle uses base+cycle_index).
        pitch_variation_callback: optional fn(notes, cycle_idx) → notes for
                                  pitch-side mutations (octave-jump etc.).

    Returns:
        Combined note list across all cycles, humanized per advisor rules.
    """
    pitch = pitch_override if pitch_override is not None else motif['drum_pitch']
    rules = motif.get('micro_variation_rules', {}) if apply_micro_variations else {}

    out = []
    for cycle_idx in range(num_cycles):
        seed = (rng_seed_base or 0) + cycle_idx if rng_seed_base is not None else None
        rng = random.Random(seed) if seed is not None else random.Random(cycle_idx * 7919 + 17)

        # Determine skip/double indices for this cycle
        skip_indices = set()
        double_indices = set()
        if 'occasional_skip' in rules:
            os_rule = rules['occasional_skip']
            if cycle_idx % os_rule['every_n_cycles'] == os_rule['every_n_cycles'] - 1:
                skip_indices = set(os_rule['skip_indices'])
        if 'occasional_double' in rules:
            od_rule = rules['occasional_double']
            if cycle_idx % od_rule['every_n_cycles'] == od_rule['every_n_cycles'] - 1:
                double_indices = set(od_rule['double_indices'])

        cycle_notes = []
        for i, (rel_t, dur) in enumerate(motif['rhythm_beats']):
            if i in skip_indices:
                continue

            base_vel = motif['velocity_contour'][i]

            t = start_beat + cycle_idx * cycle_duration_beats + rel_t

            # Apply timing jitter
            if 'timing_jitter_ms' in rules:
                lo_ms, hi_ms = rules['timing_jitter_ms']
                delta_ms = rng.uniform(lo_ms, hi_ms)
                t += ms_to_beats(delta_ms, tempo_bpm)

            # Apply velocity jitter
            vel = base_vel
            if 'velocity_jitter' in rules:
                lo_v, hi_v = rules['velocity_jitter']
                vel += rng.randint(lo_v, hi_v)

            cycle_notes.append({
                'time': float(max(0, t)),
                'duration': float(dur),
                'velocity': max(1, min(127, int(vel * velocity_scale))),
                'pitch': int(pitch),
            })

            # Apply double (flam) rule
            if i in double_indices:
                flam_offset = rules.get('occasional_double', {}).get('flam_offset_beats', 0.0625)
                cycle_notes.append({
                    'time': float(t + flam_offset),
                    'duration': float(dur),
                    'velocity': max(1, min(127, int(vel * velocity_scale * 0.6))),
                    'pitch': int(pitch),
                })

        # Apply pitch_variation_callback (e.g. octave-jump on certain cycles)
        if pitch_variation_callback is not None:
            cycle_notes = pitch_variation_callback(cycle_notes, cycle_idx)

        out.extend(cycle_notes)

    return out


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    import sys
    sys.path.insert(0, '/home/user/Mix-Analyzer')
    from composition_engine.motifs.rhythmic import RHYTHMIC_MOTIFS

    print('=== ms_to_beats sanity ===')
    print(f'  15ms @ 120 BPM = {ms_to_beats(15, 120):.4f} beats (expect 0.030)')
    print(f'  15ms @ 108 BPM = {ms_to_beats(15, 108):.4f} beats')
    print(f'  15ms @  95 BPM = {ms_to_beats(15, 95):.4f} beats')

    # Test humanize_timing
    print('\n=== humanize_timing on flat 4-on-floor (jitter ±10ms @ 108 BPM, seed=42) ===')
    flat = [{'time': float(i), 'duration': 0.25, 'velocity': 110, 'pitch': 36} for i in range(4)]
    h = humanize_timing(flat, jitter_ms=10, tempo_bpm=108, rng_seed=42)
    for n in h:
        print(f'  time={n["time"]:.4f}')

    # Test humanize_gate_length
    print('\n=== humanize_gate_length ±15% (seed=42) ===')
    flat = [{'time': float(i), 'duration': 0.25, 'velocity': 110, 'pitch': 36} for i in range(4)]
    g = humanize_gate_length(flat, jitter_pct=15, rng_seed=42)
    for n in g:
        print(f'  duration={n["duration"]:.4f} (base 0.25)')

    # Test apply_motif_loop_humanization on syncopated_kick × 3 cycles
    print('\n=== apply_motif_loop_humanization syncopated_kick × 4 cycles @ 108 BPM ===')
    motif = RHYTHMIC_MOTIFS['syncopated_kick_3_against_4']
    notes = apply_motif_loop_humanization(
        motif, num_cycles=4, cycle_duration_beats=4.0,
        tempo_bpm=108, rng_seed_base=100, apply_micro_variations=True,
    )
    print(f'Total notes: {len(notes)}')
    for n in notes:
        cycle = int(n['time'] // 4)
        beat_in = n['time'] % 4
        print(f'  cycle={cycle}  beat_in_bar={beat_in:.4f}  vel={n["velocity"]}')

    # Demonstrate cycle 7 (skip rule kicks in)
    print('\n=== syncopated_kick × 8 cycles → cycle 7 should drop the beat-1.5 hit ===')
    notes = apply_motif_loop_humanization(
        motif, num_cycles=8, cycle_duration_beats=4.0,
        tempo_bpm=108, rng_seed_base=100, apply_micro_variations=True,
    )
    cycle_7_notes = [n for n in notes if 7*4 <= n['time'] < 8*4]
    print(f'Cycle 7 hits: {len(cycle_7_notes)} (expect 4 = 4 - 1 skip + 1 flam)')
    for n in cycle_7_notes:
        print(f'  beat_in_bar={n["time"]%4:.4f}  vel={n["velocity"]}')
