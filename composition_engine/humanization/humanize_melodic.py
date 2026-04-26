"""Melodic humanization — Phase 4-2 of composition_engine.

Cross-cycle melodic variations: when a melodic motif loops N times, it must
not be IDENTICAL each cycle. Apply documented advisor variations:
    - octave-jump on note N every M cycles (robot_rock)
    - retrograde half the motif every K cycles
    - ornament insertion (grace notes, mordents) on specific notes
    - micro-detuning via pitch_substitute (very subtle pitch wobble)

Workhorse: apply_melodic_loop_humanization — render a melodic motif N times
with cross-cycle variations.
"""

import random
from typing import List, Dict, Any, Callable, Optional


def add_grace_note(notes: List[Dict[str, Any]],
                   target_index: int,
                   grace_pitch_offset: int = -1,
                   grace_duration_beats: float = 0.0625,
                   grace_velocity: int = 60) -> List[Dict[str, Any]]:
    """Insert a grace note BEFORE a target note (anticipation).

    Grace note: short note (typically 1/16 or 1/32) at a pitch offset from the
    target, played just before. Used per advisor for tension/release ornaments
    or "Cobain-style" pitch slides.

    Args:
        notes: list of note dicts.
        target_index: which note to ornament.
        grace_pitch_offset: semitone offset (negative = below, +1 = chromatic upper neighbor).
        grace_duration_beats: how long the grace note is.
        grace_velocity: how loud (typically softer than target).

    Returns:
        New list with grace note inserted before the target.
    """
    if target_index < 0 or target_index >= len(notes):
        return [{**n} for n in notes]

    out = []
    for i, n in enumerate(notes):
        if i == target_index:
            grace = {
                'time': max(0.0, n['time'] - grace_duration_beats),
                'duration': grace_duration_beats,
                'velocity': max(1, min(127, grace_velocity)),
                'pitch': n['pitch'] + grace_pitch_offset,
            }
            out.append(grace)
        out.append({**n})
    return out


def add_mordent(notes: List[Dict[str, Any]],
                target_index: int,
                neighbor_offset: int = 1,
                ornament_duration: float = 0.0625) -> List[Dict[str, Any]]:
    """Insert a mordent: target_pitch → neighbor → target_pitch quick trill.

    Splits the target note into 3 sub-notes:
        [target (very short)] → [neighbor (very short)] → [target (remainder)]
    Total duration preserved.

    Args:
        notes: list of note dicts.
        target_index: which note to mordent.
        neighbor_offset: semitone offset for the neighbor pitch (+1 = upper, -1 = lower).
        ornament_duration: duration of each ornament note (target + neighbor each).

    Returns:
        New list with mordent applied.
    """
    if target_index < 0 or target_index >= len(notes):
        return [{**n} for n in notes]

    target = notes[target_index]
    if target['duration'] <= 2 * ornament_duration:
        # Note too short for mordent
        return [{**n} for n in notes]

    out = []
    for i, n in enumerate(notes):
        if i == target_index:
            # target (short)
            out.append({**n, 'duration': ornament_duration})
            # neighbor (short)
            out.append({
                'time': n['time'] + ornament_duration,
                'duration': ornament_duration,
                'velocity': n['velocity'],
                'pitch': n['pitch'] + neighbor_offset,
            })
            # target (remainder)
            out.append({
                'time': n['time'] + 2 * ornament_duration,
                'duration': n['duration'] - 2 * ornament_duration,
                'velocity': n['velocity'],
                'pitch': n['pitch'],
            })
        else:
            out.append({**n})
    return out


def apply_melodic_loop_humanization(render_func: Callable[[int], List[Dict[str, Any]]],
                                    num_cycles: int,
                                    cycle_duration_beats: float,
                                    tempo_bpm: float = 108.0,
                                    start_beat: float = 0.0,
                                    rng_seed_base: int = None,
                                    octave_jump_rule: Optional[Dict[str, Any]] = None,
                                    retrograde_rule: Optional[Dict[str, Any]] = None,
                                    ornament_rule: Optional[Dict[str, Any]] = None,
                                    timing_jitter_ms: float = 5.0,
                                    velocity_jitter: int = 5) -> List[Dict[str, Any]]:
    """Render a melodic motif N times applying cross-cycle variations.

    Variation rules (each optional):
        octave_jump_rule: {
            'every_n_cycles': int,
            'cycle_index': int,           # 0 means first cycle, every_n_cycles - 1 means last in period
            'note_indices': List[int],    # which notes to lift
            'octaves': int,               # +1 / -1
        }
        retrograde_rule: {
            'every_n_cycles': int,
            'apply_to_half': str,         # 'first' / 'second' / 'all'
        }
        ornament_rule: {
            'every_n_cycles': int,
            'type': str,                  # 'grace' / 'mordent'
            'target_index': int,
            'pitch_offset': int,
        }

    Plus baseline humanization (timing + velocity jitter per cycle).

    Args:
        render_func: callable cycle_idx → notes list (rendered at time 0).
        num_cycles: how many times to repeat.
        cycle_duration_beats: bar length per cycle.
        tempo_bpm: tempo for ms→beats conversion.
        start_beat: where the first cycle starts.
        rng_seed_base: base seed for reproducibility.
        octave_jump_rule, retrograde_rule, ornament_rule: optional variation rules.
        timing_jitter_ms: per-note ±N ms (default 5 = subtle).
        velocity_jitter: per-note ±N velocity (default 5 = subtle).

    Returns:
        Combined note list across all cycles, with documented variations.
    """
    from composition_engine.transforms.pitch import octave_jump, retrograde
    from composition_engine.humanization.humanize_rhythmic import ms_to_beats

    out = []
    for cycle_idx in range(num_cycles):
        seed = (rng_seed_base or 0) + cycle_idx if rng_seed_base is not None else None
        rng = random.Random(seed) if seed is not None else random.Random(cycle_idx * 6571 + 23)

        cycle_notes = render_func(cycle_idx)

        # Apply octave-jump if rule fires this cycle
        if octave_jump_rule:
            n_cyc = octave_jump_rule['every_n_cycles']
            target_cyc = octave_jump_rule.get('cycle_index', n_cyc - 1)
            if cycle_idx % n_cyc == target_cyc:
                cycle_notes = octave_jump(cycle_notes,
                                          indices=octave_jump_rule['note_indices'],
                                          octaves=octave_jump_rule.get('octaves', 1))

        # Apply retrograde if rule fires this cycle
        if retrograde_rule:
            n_cyc = retrograde_rule['every_n_cycles']
            if cycle_idx % n_cyc == n_cyc - 1:
                half = retrograde_rule.get('apply_to_half', 'all')
                if half == 'all':
                    cycle_notes = retrograde(cycle_notes)
                elif half == 'first':
                    mid = len(cycle_notes) // 2
                    first_half = retrograde(cycle_notes[:mid])
                    cycle_notes = first_half + cycle_notes[mid:]
                elif half == 'second':
                    mid = len(cycle_notes) // 2
                    second_half = retrograde(cycle_notes[mid:])
                    # Re-zero second_half timing then offset to align with after first half
                    if cycle_notes[:mid]:
                        offset = cycle_notes[mid - 1]['time'] + cycle_notes[mid - 1]['duration']
                        second_half = [{**n, 'time': n['time'] + offset} for n in second_half]
                    cycle_notes = cycle_notes[:mid] + second_half

        # Apply ornament if rule fires this cycle
        if ornament_rule:
            n_cyc = ornament_rule['every_n_cycles']
            if cycle_idx % n_cyc == n_cyc - 1:
                t_idx = ornament_rule['target_index']
                p_off = ornament_rule.get('pitch_offset', -1)
                if ornament_rule['type'] == 'grace':
                    cycle_notes = add_grace_note(cycle_notes, t_idx,
                                                 grace_pitch_offset=p_off)
                elif ornament_rule['type'] == 'mordent':
                    cycle_notes = add_mordent(cycle_notes, t_idx,
                                              neighbor_offset=p_off)

        # Baseline humanization (timing + velocity per cycle)
        offset = start_beat + cycle_idx * cycle_duration_beats
        for n in cycle_notes:
            t = n['time'] + offset
            if timing_jitter_ms > 0 and abs(n['time']) > 0.001:
                # Don't jitter the first downbeat of the motif
                delta_ms = rng.uniform(-timing_jitter_ms, timing_jitter_ms)
                t += ms_to_beats(delta_ms, tempo_bpm)

            v = n['velocity']
            if velocity_jitter > 0:
                v = max(1, min(127, v + rng.randint(-velocity_jitter, velocity_jitter)))

            out.append({**n, 'time': max(0.0, t), 'velocity': v})

    return out


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    import sys
    sys.path.insert(0, '/home/user/Mix-Analyzer')
    from composition_engine.motifs.melodic import MELODIC_MOTIFS, render

    motif = MELODIC_MOTIFS['robot_rock_riff_with_micro_variations']
    base = render(motif, tonic_pitch=38)   # voice in low D2
    print('=== Base robot_rock_riff in D2 ===')
    print('  pitches:    ', [n['pitch'] for n in base])
    print('  velocities: ', [n['velocity'] for n in base])

    # Test grace note
    print('\n=== add_grace_note before index 3 (chromatic lower neighbor) ===')
    g = add_grace_note(base, target_index=3, grace_pitch_offset=-1)
    for n in g:
        print(f'  time={n["time"]:.4f}  pitch={n["pitch"]}  dur={n["duration"]}  vel={n["velocity"]}')

    # Test mordent on a longer note
    print('\n=== add_mordent on index 7 (last note, upper neighbor) ===')
    m = add_mordent(base, target_index=7, neighbor_offset=1)
    for n in m:
        print(f'  time={n["time"]:.4f}  pitch={n["pitch"]}  dur={n["duration"]}')

    # Test apply_melodic_loop_humanization with all 3 rules
    print('\n=== apply_melodic_loop_humanization on robot_rock × 8 cycles ===')
    print('  Rules: octave-jump note 3 every 4 cycles, retrograde all every 8, grace before note 3 every 4')

    def render_robot(cycle_idx):
        return render(motif, tonic_pitch=38)

    notes = apply_melodic_loop_humanization(
        render_robot, num_cycles=8, cycle_duration_beats=4.0, tempo_bpm=108,
        start_beat=0.0, rng_seed_base=42,
        octave_jump_rule={
            'every_n_cycles': 4,
            'cycle_index': 3,
            'note_indices': [3],
            'octaves': 1,
        },
        retrograde_rule={
            'every_n_cycles': 8,
            'apply_to_half': 'all',
        },
        ornament_rule={
            'every_n_cycles': 4,
            'type': 'grace',
            'target_index': 0,
            'pitch_offset': -1,
        },
        timing_jitter_ms=5,
        velocity_jitter=5,
    )

    # Show summary by cycle
    for cyc in range(8):
        cyc_notes = [n for n in notes if cyc * 4 <= n['time'] < (cyc + 1) * 4]
        pitches = [n['pitch'] for n in sorted(cyc_notes, key=lambda x: x['time'])]
        print(f'  cycle {cyc}: {len(cyc_notes)} notes, pitches={pitches}')
