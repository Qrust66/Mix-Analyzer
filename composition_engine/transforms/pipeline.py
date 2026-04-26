"""Pipeline / combinator helpers — Phase 2-4 of composition_engine.

Compose multiple transforms in a readable chain. Two styles:

1. Functional pipe:
       notes = pipe(motif_render, transpose(+5), augment_diminish(0.5), humanize_velocity(8))

2. Pipeline class (mutable accumulator):
       p = Pipeline(motif_render).then(transpose, +5).then(augment_diminish, 0.5)
       notes = p.run()

Also provides:
    apply_chain    — run a list of (callable, args, kwargs) tuples
    repeat_with    — render a motif N times back-to-back, optionally varying per cycle
"""

from typing import List, Dict, Any, Callable, Tuple, Iterable, Optional
import copy


# ============================================================================
# Pipe-style composition
# ============================================================================

def pipe(*funcs):
    """Chain a sequence of single-argument functions.

    Each function receives the OUTPUT of the previous as input. The first arg
    is treated as the seed (notes list).

    Usage:
        chain = pipe(
            lambda: render(motif, tonic_pitch=50),
            lambda notes: transpose(notes, 5),
            lambda notes: augment_diminish(notes, 0.5),
        )
        notes = chain()

    Or with `lift` helper for simple transforms:
        chain = pipe(
            lambda: render(motif, tonic_pitch=50),
            lift(transpose, 5),
            lift(augment_diminish, 0.5),
        )
        notes = chain()
    """
    def composed():
        # First func is the seed (no args)
        result = funcs[0]()
        for f in funcs[1:]:
            result = f(result)
        return result
    return composed


def lift(transform_func: Callable, *args, **kwargs) -> Callable:
    """Lift a transform-with-args into a single-arg lambda for use in pipe().

    Example:
        lift(transpose, 5)   # returns a function: notes → transpose(notes, 5)
    """
    return lambda notes: transform_func(notes, *args, **kwargs)


# ============================================================================
# Pipeline class (mutable / fluent style)
# ============================================================================

class Pipeline:
    """Fluent pipeline for chaining transforms.

    Usage:
        p = Pipeline(initial_notes)
        p.then(transpose, 5).then(augment_diminish, 0.5)
        notes = p.run()
    """

    def __init__(self, seed):
        """seed: either notes list, or a callable that produces notes."""
        self._seed = seed
        self._steps: List[Tuple[Callable, tuple, dict]] = []

    def then(self, func: Callable, *args, **kwargs) -> 'Pipeline':
        """Append a transform to the chain. Returns self for fluent chaining."""
        self._steps.append((func, args, kwargs))
        return self

    def run(self) -> List[Dict[str, Any]]:
        """Execute the chain and return final notes list."""
        if callable(self._seed):
            notes = self._seed()
        else:
            notes = copy.deepcopy(self._seed)
        for func, args, kwargs in self._steps:
            notes = func(notes, *args, **kwargs)
        return notes

    def __len__(self):
        return len(self._steps)


# ============================================================================
# Multi-render helpers — render a motif N times with optional per-cycle variation
# ============================================================================

def repeat_with(render_func: Callable[[int], List[Dict[str, Any]]],
                num_cycles: int,
                cycle_duration_beats: float,
                start_beat: float = 0.0) -> List[Dict[str, Any]]:
    """Render a motif N times back-to-back, accumulating into a single note list.

    render_func is called with cycle_index (0..N-1) and should return a fresh
    note list whose timing starts at beat 0 (it will be shifted to the right
    cycle position by this helper).

    Args:
        render_func: callable cycle_idx -> notes (rendered at time 0).
        num_cycles: number of repetitions.
        cycle_duration_beats: how many beats each cycle occupies.
        start_beat: where the first cycle starts.

    Returns:
        Combined note list with proper timing across all cycles.

    Example:
        # Render robot_rock_riff 16 times with octave-jump on cycle %4 == 3
        from composition_engine.motifs.melodic import MELODIC_MOTIFS, render
        from composition_engine.transforms.pitch import octave_jump

        def render_with_variation(cycle_idx):
            base = render(MELODIC_MOTIFS['robot_rock_riff_with_micro_variations'], tonic_pitch=38)
            if cycle_idx % 4 == 3:
                base = octave_jump(base, indices=[3], octaves=1)
            return base

        notes = repeat_with(render_with_variation, num_cycles=16, cycle_duration_beats=4.0)
    """
    out = []
    for cycle_idx in range(num_cycles):
        cycle_notes = render_func(cycle_idx)
        offset = start_beat + cycle_idx * cycle_duration_beats
        for n in cycle_notes:
            out.append({**n, 'time': n['time'] + offset})
    return out


def concat_motifs(*note_lists: List[Dict[str, Any]],
                  spacing_beats: float = 0.0) -> List[Dict[str, Any]]:
    """Concatenate multiple note-lists end-to-end (each starts after the previous ends).

    Each input list is treated as starting at time=0; this function shifts each
    successive list by the cumulative duration of the previous lists.

    Args:
        *note_lists: variable number of note lists to concatenate.
        spacing_beats: optional silence between consecutive lists.

    Returns:
        Single combined note list.
    """
    out = []
    cursor = 0.0
    for nl in note_lists:
        if not nl:
            continue
        # Shift all notes by cursor
        for n in nl:
            out.append({**n, 'time': n['time'] + cursor})
        # Move cursor past this list's end
        max_end = max(n['time'] + n['duration'] for n in nl)
        cursor += max_end + spacing_beats
    return out


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    import sys
    sys.path.insert(0, '/home/user/Mix-Analyzer')
    from composition_engine.motifs.melodic import MELODIC_MOTIFS, render as melodic_render
    from composition_engine.transforms.pitch import transpose, octave_jump, retrograde
    from composition_engine.transforms.timing import augment_diminish, rhythmic_displace
    from composition_engine.transforms.velocity import velocity_contour_apply, humanize_velocity

    motif = MELODIC_MOTIFS['aeolian_descending_4_steps']

    # Test 1: pipe-style
    print('=== pipe-style ===')
    chain = pipe(
        lambda: melodic_render(motif, tonic_pitch=50),
        lift(transpose, 5),
        lift(velocity_contour_apply, 'climax', 50, 125),
    )
    out = chain()
    for n in out:
        print(f'  pitch={n["pitch"]}  time={n["time"]}  vel={n["velocity"]}')

    # Test 2: Pipeline class
    print('\n=== Pipeline class ===')
    p = Pipeline(lambda: melodic_render(motif, tonic_pitch=50))
    p.then(retrograde)
    p.then(augment_diminish, 0.5)
    p.then(humanize_velocity, 5, 42)   # jitter=5, seed=42
    out = p.run()
    print(f'Steps: {len(p)}')
    for n in out:
        print(f'  pitch={n["pitch"]}  time={n["time"]}  dur={n["duration"]}  vel={n["velocity"]}')

    # Test 3: repeat_with — 4 cycles with octave-jump every 2nd cycle on note index 3
    print('\n=== repeat_with: 4 cycles, octave_jump on cycle %2==1 ===')
    def render_var(cycle_idx):
        base = melodic_render(motif, tonic_pitch=50)
        if cycle_idx % 2 == 1:
            base = octave_jump(base, indices=[3], octaves=1)
        return base

    looped = repeat_with(render_var, num_cycles=4, cycle_duration_beats=4.0, start_beat=0.0)
    print(f'Total notes: {len(looped)} (4 cycles × 4 notes = 16)')
    for n in looped:
        marker = ' ← octave-jumped' if n['pitch'] == 57 and abs(n['time'] % 4 - 3) < 0.01 else ''
        print(f'  cycle@{int(n["time"]//4)}  beat{n["time"]%4:.1f}  pitch={n["pitch"]}{marker}')

    # Test 4: concat_motifs — three different motifs end-to-end
    print('\n=== concat_motifs: aeolian → ascending_arc → outro_chant ===')
    notes_a = melodic_render(MELODIC_MOTIFS['aeolian_descending_4_steps'], tonic_pitch=50)
    notes_b = melodic_render(MELODIC_MOTIFS['pre_chorus_ascending_arc'], tonic_pitch=50)
    notes_c = melodic_render(MELODIC_MOTIFS['outro_chant_fragment_repeating'], tonic_pitch=50)
    combined = concat_motifs(notes_a, notes_b, notes_c, spacing_beats=0.5)
    print(f'Total: {len(combined)} notes spanning {max(n["time"] + n["duration"] for n in combined)} beats')
    for n in combined:
        print(f'  time={n["time"]:.2f}  pitch={n["pitch"]}  dur={n["duration"]}')
