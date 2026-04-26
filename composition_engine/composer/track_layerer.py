"""Track layerer — Phase 6-2 of composition_engine.

For each track in the composition, layer multiple motif-evolutions over the
song timeline with natural overlap and fade. This produces a continuous
per-track note-list — no hard section boundaries, but layers introduced and
retired organically based on their entry_at_bar / exit_at_bar.

API:
    LayerSpec: dataclass — describes one motif-evolution layer on a track
    layer_track: combine multiple LayerSpecs on a track into a single note-list
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

from composition_engine.composer.motif_evolution import (
    EvolutionParams, evolve_motif,
)


@dataclass
class LayerSpec:
    """Describes one motif-evolution layered on a track over a bar-range.

    The motif is rendered for `num_cycles_active` cycles starting at
    `entry_at_bar`, fading in via `entry_fade_bars` and fading out via
    `exit_fade_bars`. Outside the active range the layer is silent.

    Multiple LayerSpecs on the same track can OVERLAP — they're combined into
    a single note-list with each layer's notes sharing the timeline.
    """
    motif_render_func: Callable[[int], List[Dict[str, Any]]]   # cycle_idx → notes at time 0
    motif_id: str = ''                  # for diagnostics
    entry_at_bar: int = 1               # bar index (1-indexed) where layer becomes audible
    exit_at_bar: int = 64               # bar index where layer goes silent (exclusive)
    cycle_duration_beats: float = 4.0   # bar length per cycle
    base_volume: float = 1.0            # peak volume for this layer
    entry_fade_bars: int = 0            # bars to ramp up from silence to base_volume
    exit_fade_bars: int = 0             # bars to ramp down from base_volume to silence
    evolution_params: Optional[EvolutionParams] = None    # use motif's natural drift
    rng_seed_base: int = None
    target_track: str = ''              # diagnostic: which track this layer lives on


def _bars_to_cycles(bars: int, cycle_duration_beats: float = 4.0) -> int:
    """How many cycles fit in N bars at 4 beats/bar."""
    return max(1, int(bars * 4.0 / cycle_duration_beats))


def render_layer(spec: LayerSpec, tempo_bpm: float = 108.0) -> List[Dict[str, Any]]:
    """Render a single LayerSpec into a note-list with entry/exit fades.

    Strategy:
        - Total active duration = exit_at_bar - entry_at_bar bars
        - That maps to N cycles
        - The fade-in / fade-out bars get encoded into the EvolutionParams envelope
          (entry_volume = 0 if entry_fade_bars > 0, peak_at_cycle_pct positioned
          to put the peak after fade-in)
    """
    active_bars = spec.exit_at_bar - spec.entry_at_bar
    if active_bars <= 0:
        return []
    num_cycles = _bars_to_cycles(active_bars, spec.cycle_duration_beats)

    # Compute envelope based on entry/exit fades
    fade_in_cycles = max(0, _bars_to_cycles(spec.entry_fade_bars, spec.cycle_duration_beats))
    fade_out_cycles = max(0, _bars_to_cycles(spec.exit_fade_bars, spec.cycle_duration_beats))

    if num_cycles == 0:
        return []
    if fade_in_cycles + fade_out_cycles >= num_cycles:
        # Truncate fades if they're longer than the layer
        fade_in_cycles = min(fade_in_cycles, num_cycles // 2)
        fade_out_cycles = min(fade_out_cycles, num_cycles - fade_in_cycles - 1)

    # Compute trapezoidal envelope: entry → fade_in → SUSTAIN at peak → fade_out → exit
    fade_in_pct = (fade_in_cycles / num_cycles) if num_cycles > 0 else 0.1
    fade_out_pct = 1.0 - (fade_out_cycles / num_cycles) if num_cycles > 0 else 0.9
    # Guard: ensure fade_in_pct < fade_out_pct
    if fade_in_pct >= fade_out_pct:
        fade_in_pct = max(0.0, fade_out_pct - 0.01)

    if spec.evolution_params is not None:
        params = EvolutionParams(
            entry_volume=0.0 if fade_in_cycles > 0 else spec.base_volume,
            peak_volume=spec.base_volume,
            exit_volume=0.0 if fade_out_cycles > 0 else spec.base_volume,
            fade_in_pct=fade_in_pct,
            fade_out_pct=fade_out_pct,
            fade_curve=spec.evolution_params.fade_curve,
            transpose_drift_per_cycle=spec.evolution_params.transpose_drift_per_cycle,
            octave_jump_every_n_cycles=spec.evolution_params.octave_jump_every_n_cycles,
            octave_jump_indices=spec.evolution_params.octave_jump_indices,
            timing_compress_per_cycle=spec.evolution_params.timing_compress_per_cycle,
            gate_drift_per_cycle=spec.evolution_params.gate_drift_per_cycle,
            timing_jitter_ms=spec.evolution_params.timing_jitter_ms,
            velocity_jitter=spec.evolution_params.velocity_jitter,
            gate_jitter_pct=spec.evolution_params.gate_jitter_pct,
            tonal_substitution_every_n_cycles=spec.evolution_params.tonal_substitution_every_n_cycles,
            tonal_substitution_map=spec.evolution_params.tonal_substitution_map,
        )
    else:
        # Default: trapezoidal envelope with fades, no drift
        params = EvolutionParams(
            entry_volume=0.0 if fade_in_cycles > 0 else spec.base_volume,
            peak_volume=spec.base_volume,
            exit_volume=0.0 if fade_out_cycles > 0 else spec.base_volume,
            fade_in_pct=fade_in_pct,
            fade_out_pct=fade_out_pct,
            timing_jitter_ms=6, velocity_jitter=6, gate_jitter_pct=10,
        )

    # Compute start_beat from entry_at_bar (1-indexed bars → 0-indexed beats)
    start_beat = (spec.entry_at_bar - 1) * 4.0

    return evolve_motif(
        spec.motif_render_func,
        num_cycles=num_cycles,
        cycle_duration_beats=spec.cycle_duration_beats,
        params=params,
        tempo_bpm=tempo_bpm,
        start_beat=start_beat,
        rng_seed_base=spec.rng_seed_base,
    )


def layer_track(layers: List[LayerSpec], tempo_bpm: float = 108.0) -> List[Dict[str, Any]]:
    """Combine multiple LayerSpecs on the SAME track into a single note-list.

    Layers can overlap in time — their notes are simply summed into one list.
    The result is sorted by time.

    Args:
        layers: list of LayerSpec for this track.
        tempo_bpm: tempo for ms→beats conversion.

    Returns:
        Combined sorted note-list for the track.
    """
    out = []
    for spec in layers:
        layer_notes = render_layer(spec, tempo_bpm=tempo_bpm)
        out.extend(layer_notes)
    out.sort(key=lambda n: n['time'])
    return out


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    from composition_engine.motifs.melodic import MELODIC_MOTIFS, render

    motif_riff = MELODIC_MOTIFS['robot_rock_riff_with_micro_variations']
    motif_lead = MELODIC_MOTIFS['ascending_counter_to_descending_bass']

    def render_riff(cycle_idx):
        return render(motif_riff, tonic_pitch=38)

    def render_lead(cycle_idx):
        return render(motif_lead, tonic_pitch=50)

    # Layer 1: bass-riff active bars 5-60, fade-in over 4 bars, fade-out over 4 bars
    bass_layer = LayerSpec(
        motif_render_func=render_riff,
        motif_id='robot_rock_riff',
        entry_at_bar=5,
        exit_at_bar=61,
        cycle_duration_beats=4.0,
        base_volume=1.0,
        entry_fade_bars=4,
        exit_fade_bars=4,
        rng_seed_base=42,
        target_track='BASS',
    )

    # Layer 2: lead enters at bar 30 (mid-song), continues to end
    lead_layer = LayerSpec(
        motif_render_func=render_lead,
        motif_id='ascending_counter',
        entry_at_bar=30,
        exit_at_bar=64,
        cycle_duration_beats=8.0,    # this motif is 8 beats long (2 bars per cycle)
        base_volume=0.7,
        entry_fade_bars=2,
        exit_fade_bars=4,
        rng_seed_base=99,
        target_track='LEAD',
    )

    print('=== Layer 1: BASS robot_rock_riff bars 5-60 with fade-in 4 / fade-out 4 ===')
    bass_notes = render_layer(bass_layer, tempo_bpm=108)
    print(f'Total notes: {len(bass_notes)}')
    # Sample velocity at bars 5, 8, 30, 56, 60
    sample_bars = [5, 7, 9, 30, 55, 58, 60]
    print('Velocity samples (first note in each bar):')
    for b in sample_bars:
        bar_notes = sorted([n for n in bass_notes if (b-1)*4 <= n['time'] < b*4],
                          key=lambda n: n['time'])
        if bar_notes:
            print(f'  bar {b:2d}: vel={bar_notes[0]["velocity"]:3d}')
        else:
            print(f'  bar {b:2d}: SILENT')

    print('\n=== Layer 2: LEAD ascending_counter bars 30-64 ===')
    lead_notes = render_layer(lead_layer, tempo_bpm=108)
    print(f'Total notes: {len(lead_notes)}')
    print('Lead first/last notes:')
    if lead_notes:
        first = sorted(lead_notes, key=lambda n: n['time'])[0]
        last = sorted(lead_notes, key=lambda n: n['time'])[-1]
        print(f'  first: time={first["time"]:.2f}  pitch={first["pitch"]}')
        print(f'  last:  time={last["time"]:.2f}  pitch={last["pitch"]}')

    print('\n=== Combined (BASS + LEAD layers on same track for sanity) ===')
    combined = layer_track([bass_layer, lead_layer], tempo_bpm=108)
    print(f'Combined notes: {len(combined)}')
