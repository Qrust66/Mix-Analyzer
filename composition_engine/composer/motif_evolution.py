"""Motif evolution — Phase 6-1 of composition_engine.

Generate a CONTINUOUSLY EVOLVING sequence of a motif across N cycles. Each cycle
is slightly different from the previous — small transforms accumulate gradually
so the music DEVELOPS without sectional boundaries.

This is the alternative to fixed-section composition: a single timeline where
the motif you started with at bar 1 is recognizably the same one at bar 64
but has accumulated subtle transformations along the way.

API:
    EvolutionParams: dataclass describing how a motif should drift over time
    evolve_motif: render a motif N cycles with progressive transformation
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional
import random

from composition_engine.transforms.pitch import (
    transpose, octave_jump, retrograde, fragment, pitch_substitute_in_scale,
)
from composition_engine.transforms.timing import (
    augment_diminish, rhythmic_displace, gate_length_vary,
)
from composition_engine.transforms.velocity import (
    velocity_scale, velocity_contour_apply, humanize_velocity, accent_pattern,
)
from composition_engine.humanization.humanize_rhythmic import (
    ms_to_beats, humanize_timing, humanize_gate_length,
)


@dataclass
class EvolutionParams:
    """Parameters for how a motif should evolve over N cycles.

    All "drift" parameters describe HOW MUCH the motif changes per cycle.
    Subtle drift values (e.g. 0.01 register_drift_per_cycle) accumulate over many
    cycles into noticeable evolution.

    Velocity envelope (entry_volume, peak_volume, exit_volume + when peak hits)
    shapes the motif's PRESENCE across the song timeline — fade-in / sustain /
    fade-out. This is the alternative to "active in section X, silent in section Y".
    """
    # Velocity envelope across cycles (0.0 = silent, 1.0 = full volume).
    # Trapezoidal: entry → fade_in → SUSTAIN at peak → fade_out → exit.
    entry_volume: float = 0.0          # cycle 0 volume
    peak_volume: float = 1.0           # sustain volume (between fade_in_pct and fade_out_pct)
    exit_volume: float = 0.0           # last cycle volume
    fade_in_pct: float = 0.1           # cycle fraction by which peak is reached
    fade_out_pct: float = 0.9          # cycle fraction at which fade-out begins
    peak_at_cycle_pct: float = None    # DEPRECATED: if set, used as triangular peak (overrides fade_in/fade_out)
    fade_curve: str = 'linear'         # 'linear' / 'exp' / 'sigmoid'

    # Pitch drift (semitones drift per cycle, accumulating)
    transpose_drift_per_cycle: float = 0.0   # e.g. 0.0625 → +1 semitone every 16 cycles

    # Register drift (every N cycles, octave-jump on chosen note indices)
    octave_jump_every_n_cycles: int = 0      # 0 = disabled
    octave_jump_indices: List[int] = field(default_factory=list)

    # Timing drift (gradually compress or expand)
    timing_compress_per_cycle: float = 0.0   # e.g. 0.005 → motif gets 0.5% faster per cycle

    # Gate length drift (gradually staccato or legato)
    gate_drift_per_cycle: float = 0.0        # e.g. -0.01 → gate shrinks 1% per cycle

    # Humanization (constant per cycle)
    timing_jitter_ms: float = 6.0
    velocity_jitter: int = 6
    gate_jitter_pct: float = 10.0

    # Tonal substitution (every N cycles, swap one scale degree)
    tonal_substitution_every_n_cycles: int = 0
    tonal_substitution_map: Dict[int, int] = field(default_factory=dict)


def _envelope_volume(cycle_idx: int, num_cycles: int, params: EvolutionParams) -> float:
    """Compute the velocity-envelope multiplier for this cycle.

    Returns a value based on TRAPEZOIDAL envelope:
        - cycle 0..fade_in_pct: ramp entry_volume → peak_volume
        - cycle fade_in_pct..fade_out_pct: SUSTAIN at peak_volume
        - cycle fade_out_pct..1.0: ramp peak_volume → exit_volume

    Legacy: if params.peak_at_cycle_pct is not None, falls back to triangular.
    """
    if num_cycles <= 1:
        return params.peak_volume

    t = cycle_idx / (num_cycles - 1)

    # Legacy triangular envelope
    if params.peak_at_cycle_pct is not None:
        peak_t = params.peak_at_cycle_pct
        if t <= peak_t:
            ratio = t / peak_t if peak_t > 0 else 1.0
            v = params.entry_volume + (params.peak_volume - params.entry_volume) * ratio
        else:
            ratio = (t - peak_t) / (1.0 - peak_t) if peak_t < 1 else 0.0
            v = params.peak_volume - (params.peak_volume - params.exit_volume) * ratio
    else:
        # Trapezoidal envelope (default)
        fi = params.fade_in_pct
        fo = params.fade_out_pct
        if t <= fi:
            ratio = t / fi if fi > 0 else 1.0
            v = params.entry_volume + (params.peak_volume - params.entry_volume) * ratio
        elif t >= fo:
            ratio = (t - fo) / (1.0 - fo) if fo < 1 else 0.0
            v = params.peak_volume - (params.peak_volume - params.exit_volume) * ratio
        else:
            v = params.peak_volume

    # Apply curve
    if params.fade_curve == 'exp':
        v = v ** 2 if v > 0 else 0
    elif params.fade_curve == 'sigmoid':
        if 0 < v < 1:
            v = 1 / (1 + 2.71828 ** (-12 * (v - 0.5)))

    return max(0.0, min(1.0, v))


def evolve_motif(render_func: Callable[[int], List[Dict[str, Any]]],
                 num_cycles: int,
                 cycle_duration_beats: float,
                 params: EvolutionParams,
                 tempo_bpm: float = 108.0,
                 start_beat: float = 0.0,
                 rng_seed_base: int = None,
                 tonic_for_substitution: Optional[int] = None,
                 scale_for_substitution: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    """Render a motif N cycles with continuously accumulating evolution.

    Args:
        render_func: callable cycle_idx → notes list (rendered at time 0).
        num_cycles: how many times to repeat.
        cycle_duration_beats: bar length per cycle.
        params: EvolutionParams describing the drift parameters.
        tempo_bpm: tempo for ms→beats conversion.
        start_beat: where the first cycle begins.
        rng_seed_base: base seed for reproducibility.
        tonic_for_substitution: required if params.tonal_substitution_every_n_cycles > 0.
        scale_for_substitution: required if substitution enabled.

    Returns:
        Combined note list spanning all cycles, with evolution applied.
    """
    out = []
    accumulated_transpose = 0.0
    accumulated_compress = 0.0
    accumulated_gate_factor = 1.0
    accumulated_substitutions = {}

    for cycle_idx in range(num_cycles):
        seed = (rng_seed_base or 0) + cycle_idx if rng_seed_base is not None else None

        # 1. Render base motif
        cycle_notes = render_func(cycle_idx)
        if not cycle_notes:
            continue

        # 2. Compute envelope volume for this cycle
        env_vol = _envelope_volume(cycle_idx, num_cycles, params)
        if env_vol <= 0.001:
            continue   # silent cycle — skip entirely

        # 3. Apply accumulated transpose drift
        accumulated_transpose += params.transpose_drift_per_cycle
        rounded_transpose = round(accumulated_transpose)
        if rounded_transpose != 0:
            cycle_notes = transpose(cycle_notes, rounded_transpose)

        # 4. Apply octave-jump rule if cycle matches
        if params.octave_jump_every_n_cycles > 0 and params.octave_jump_indices:
            if cycle_idx % params.octave_jump_every_n_cycles == params.octave_jump_every_n_cycles - 1:
                cycle_notes = octave_jump(cycle_notes,
                                          indices=params.octave_jump_indices,
                                          octaves=1)

        # 5. Apply accumulated timing-compress drift
        accumulated_compress += params.timing_compress_per_cycle
        compress_factor = 1.0 - accumulated_compress
        if compress_factor > 0 and abs(accumulated_compress) > 0.01:
            cycle_notes = augment_diminish(cycle_notes, compress_factor)

        # 6. Apply gate-length drift
        accumulated_gate_factor *= (1.0 + params.gate_drift_per_cycle)
        if abs(accumulated_gate_factor - 1.0) > 0.01:
            cycle_notes = gate_length_vary(cycle_notes, gate_factor=accumulated_gate_factor)

        # 7. Apply tonal substitution if cycle matches
        if (params.tonal_substitution_every_n_cycles > 0
                and tonic_for_substitution is not None
                and scale_for_substitution is not None):
            if cycle_idx % params.tonal_substitution_every_n_cycles == params.tonal_substitution_every_n_cycles - 1:
                accumulated_substitutions.update(params.tonal_substitution_map)
            if accumulated_substitutions:
                cycle_notes = pitch_substitute_in_scale(
                    cycle_notes,
                    tonic_pitch=tonic_for_substitution,
                    scale_intervals=scale_for_substitution,
                    substitutions=accumulated_substitutions,
                )

        # 8. Apply envelope volume
        cycle_notes = velocity_scale(cycle_notes, env_vol)

        # 9. Apply humanization
        if params.timing_jitter_ms > 0:
            cycle_notes = humanize_timing(cycle_notes,
                                          jitter_ms=params.timing_jitter_ms,
                                          tempo_bpm=tempo_bpm,
                                          rng_seed=seed)
        if params.velocity_jitter > 0:
            cycle_notes = humanize_velocity(cycle_notes,
                                            jitter=params.velocity_jitter,
                                            rng_seed=seed)
        if params.gate_jitter_pct > 0:
            cycle_notes = humanize_gate_length(cycle_notes,
                                               jitter_pct=params.gate_jitter_pct,
                                               rng_seed=seed)

        # 10. Offset to cycle position
        offset = start_beat + cycle_idx * cycle_duration_beats
        for n in cycle_notes:
            out.append({**n, 'time': max(0.0, n['time'] + offset)})

    return out


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    from composition_engine.motifs.melodic import MELODIC_MOTIFS, render

    motif = MELODIC_MOTIFS['robot_rock_riff_with_micro_variations']

    def render_robot(cycle_idx):
        return render(motif, tonic_pitch=38)

    # Test 1: a motif that fades IN, peaks at cycle 8 (of 16), then fades OUT
    print('=== Test 1: fade-in/peak/fade-out envelope across 16 cycles ===')
    params = EvolutionParams(
        entry_volume=0.0,
        peak_volume=1.0,
        exit_volume=0.0,
        peak_at_cycle_pct=0.5,
        fade_curve='linear',
    )
    notes = evolve_motif(render_robot, num_cycles=16, cycle_duration_beats=4.0,
                          params=params, tempo_bpm=108, rng_seed_base=42)

    # Sample one note per cycle to show the velocity envelope
    print('Cycle | First-note velocity (envelope check)')
    for cyc in range(16):
        cyc_notes = sorted([n for n in notes if cyc * 4 <= n['time'] < (cyc+1) * 4],
                           key=lambda n: n['time'])
        if cyc_notes:
            print(f'  {cyc:2d}  | {cyc_notes[0]["velocity"]:3d}')

    # Test 2: pitch-drift evolution — gradually rises 1 semitone over 16 cycles
    print('\n=== Test 2: gradual transpose drift (+1 semitone over 16 cycles) ===')
    params2 = EvolutionParams(
        entry_volume=0.5, peak_volume=0.5, exit_volume=0.5,    # constant volume
        transpose_drift_per_cycle=1.0/16,    # rise 1 semitone over 16 cycles
        timing_jitter_ms=0, velocity_jitter=0, gate_jitter_pct=0,    # disable jitter for clean test
    )
    notes2 = evolve_motif(render_robot, num_cycles=16, cycle_duration_beats=4.0,
                           params=params2, tempo_bpm=108)
    base_pitch = 38
    print('Cycle | First-note pitch (drift check)')
    for cyc in range(16):
        cyc_notes = sorted([n for n in notes2 if cyc * 4 <= n['time'] < (cyc+1) * 4],
                           key=lambda n: n['time'])
        if cyc_notes:
            shift = cyc_notes[0]['pitch'] - base_pitch
            print(f'  {cyc:2d}  | pitch={cyc_notes[0]["pitch"]:3d}  drift={shift:+d} semitones')

    # Test 3: octave-jump every 4 cycles + envelope
    print('\n=== Test 3: octave-jump every 4 cycles on note 3 ===')
    params3 = EvolutionParams(
        entry_volume=1.0, peak_volume=1.0, exit_volume=1.0,
        octave_jump_every_n_cycles=4,
        octave_jump_indices=[3],
        timing_jitter_ms=0, velocity_jitter=0, gate_jitter_pct=0,
    )
    notes3 = evolve_motif(render_robot, num_cycles=8, cycle_duration_beats=4.0,
                           params=params3, tempo_bpm=108)
    print('Cycle | All pitches in cycle (octave-jump shows on cycle 3, 7)')
    for cyc in range(8):
        cyc_notes = sorted([n for n in notes3 if cyc * 4 <= n['time'] < (cyc+1) * 4],
                           key=lambda n: n['time'])
        pitches = [n['pitch'] for n in cyc_notes]
        marker = '  ← octave-jumped' if 31 + 12 in pitches else ''
        print(f'  {cyc}     | pitches={pitches}{marker}')
