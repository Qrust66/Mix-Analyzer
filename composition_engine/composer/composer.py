"""Composer — Phase 6-3 of composition_engine.

Top-level orchestrator. Takes:
    - A Composition spec (advisor recipe set + tonic + total_bars + per-track LayerSpecs)
And produces:
    - A dict {track_name: notes_list} ready for ALS rendering.

The composer applies the full pipeline:
    1. resolve_recipe_set (Phase 5-3) → unified plan
    2. for each track, gather LayerSpecs and call layer_track (Phase 6-2)
    3. cross-track finalization_pass (Phase 4-3)
    4. return per-track note-lists

This is the single entry-point for "give me a song".
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
import copy

from composition_engine.composer.motif_evolution import EvolutionParams
from composition_engine.composer.track_layerer import LayerSpec, layer_track
from composition_engine.advisor_bridge.synergy_resolver import resolve_recipe_set
from composition_engine.humanization.humanize_global import finalization_pass


@dataclass
class Composition:
    """Full description of a composition to render.

    The author specifies:
        - recipe_ids: which advisor recipes to deploy
        - tonic_pitch: MIDI pitch of the tonal center (e.g. 50 = D3)
        - total_bars: song length
        - tempo_bpm: tempo (overrides any tempo from resolved plan if specified)
        - layers_per_track: dict track_name → list of LayerSpec
        - apply_finalization: cross-track collision-fix pass
        - rng_seed: deterministic randomness for the whole composition
    """
    recipe_ids: List[str] = field(default_factory=list)
    tonic_pitch: int = 50           # default D3
    total_bars: int = 64
    tempo_bpm: float = 108.0
    layers_per_track: Dict[str, List[LayerSpec]] = field(default_factory=dict)
    apply_finalization: bool = True
    anchor_tracks: List[str] = field(default_factory=lambda: ['DRUMS', 'KICK', 'SUB', 'BASS'])
    rng_seed: int = 0


def compose(composition: Composition) -> Dict[str, Any]:
    """Render a Composition into per-track note-lists.

    Returns:
        {
          'tracks': {track_name: notes_list},
          'plan': resolved plan from synergy_resolver,
          'tempo_bpm': tempo,
          'total_bars': total_bars,
          'tonic_pitch': tonic_pitch,
          'diagnostics': {
              'layer_count_per_track': dict,
              'note_count_per_track': dict,
              'duration_beats': float,
          }
        }
    """
    # 1. Resolve advisor recipes into unified plan
    plan = resolve_recipe_set(composition.recipe_ids,
                              block_on_mutual_conflicts=False)

    # If tempo_bpm not given by composition AND plan has one, use plan's
    tempo_bpm = composition.tempo_bpm
    if tempo_bpm is None and plan.get('tempo_bpm'):
        tempo_bpm = plan['tempo_bpm']

    # 2. Render each track's layers
    tracks: Dict[str, List[Dict[str, Any]]] = {}
    layer_count_per_track: Dict[str, int] = {}
    note_count_per_track: Dict[str, int] = {}

    for track_name, layer_specs in composition.layers_per_track.items():
        notes = layer_track(layer_specs, tempo_bpm=tempo_bpm)
        tracks[track_name] = notes
        layer_count_per_track[track_name] = len(layer_specs)
        note_count_per_track[track_name] = len(notes)

    # 3. Cross-track finalization (collision nudge + downbeat snap)
    if composition.apply_finalization:
        tracks = finalization_pass(tracks,
                                   tempo_bpm=tempo_bpm,
                                   anchor_tracks=composition.anchor_tracks,
                                   rng_seed=composition.rng_seed)
        # Re-count notes after finalization (should be same count, just nudged times)
        note_count_per_track = {k: len(v) for k, v in tracks.items()}

    duration_beats = composition.total_bars * 4.0

    return {
        'tracks': tracks,
        'plan': plan,
        'tempo_bpm': tempo_bpm,
        'total_bars': composition.total_bars,
        'tonic_pitch': composition.tonic_pitch,
        'diagnostics': {
            'layer_count_per_track': layer_count_per_track,
            'note_count_per_track': note_count_per_track,
            'duration_beats': duration_beats,
            'total_notes': sum(note_count_per_track.values()),
        },
    }


# ============================================================================
# Self-test — full composition demo
# ============================================================================

if __name__ == '__main__':
    from composition_engine.motifs.melodic import MELODIC_MOTIFS, render as render_melodic
    from composition_engine.motifs.rhythmic import RHYTHMIC_MOTIFS
    from composition_engine.motifs.harmonic import HARMONIC_PROGRESSIONS, render as render_harmonic
    from composition_engine.humanization.humanize_rhythmic import apply_motif_loop_humanization

    # Define a minimal Banger-v3-style composition:
    #
    # 64 bars at 108 BPM, D minor.
    #
    # Tracks:
    #   SUB    — pedal-bass walking (D1) bars 5-60 with fade-in 4 / fade-out 4
    #   BASS   — robot_rock_riff (D2 area) bars 9-58 with fade-in 4 / fade-out 4
    #            evolution: octave-jump on note 3 every 4 cycles
    #   DRUMS  — syncopated_kick (D drum-rack) bars 13-60 (fades 4/4)
    #   PAD    — Aeolian Dm-Bb-C-Dm progression bars 5-64 (long fade-in 8)
    #   LEAD   — ascending counter motif bars 30-58 (peak in middle)

    TONIC = 50    # D3

    # Pre-build render funcs for each motif

    def render_sub(cycle_idx):
        # walking pedal in low register
        notes = render_melodic(MELODIC_MOTIFS['national_anthem_pedal_bass_walking'],
                               tonic_pitch=TONIC - 12,    # one octave below tonic
                               octave_offset=-1)          # and another octave below
        return notes

    def render_bass(cycle_idx):
        return render_melodic(MELODIC_MOTIFS['robot_rock_riff_with_micro_variations'],
                              tonic_pitch=TONIC - 12)    # bass octave

    def render_drums(cycle_idx):
        # rhythmic motif's apply_motif_loop_humanization handles its own micro-variations,
        # but here we use the simpler render which evolve_motif will then humanize.
        # Build a one-cycle rendering manually.
        m = RHYTHMIC_MOTIFS['syncopated_kick_3_against_4']
        return [{'time': t, 'duration': dur, 'velocity': v, 'pitch': m['drum_pitch']}
                for (t, dur), v in zip(m['rhythm_beats'], m['velocity_contour'])]

    def render_pad(cycle_idx):
        # Render the Aeolian progression
        return render_harmonic(HARMONIC_PROGRESSIONS['aeolian_i_VI_VII_i'],
                               tonic_pitch=TONIC,
                               velocity=85)

    def render_lead(cycle_idx):
        return render_melodic(MELODIC_MOTIFS['ascending_counter_to_descending_bass'],
                              tonic_pitch=TONIC + 12)

    # Build LayerSpecs
    sub_layer = LayerSpec(
        motif_render_func=render_sub,
        motif_id='national_anthem_pedal_bass',
        entry_at_bar=5, exit_at_bar=61,
        cycle_duration_beats=8.0,    # this motif is 2 bars (8 beats)
        base_volume=1.0,
        entry_fade_bars=4, exit_fade_bars=4,
        evolution_params=EvolutionParams(
            timing_jitter_ms=4, velocity_jitter=4, gate_jitter_pct=5,
        ),
        rng_seed_base=10, target_track='SUB',
    )

    bass_layer = LayerSpec(
        motif_render_func=render_bass,
        motif_id='robot_rock_riff',
        entry_at_bar=9, exit_at_bar=59,
        cycle_duration_beats=4.0,
        base_volume=1.0,
        entry_fade_bars=4, exit_fade_bars=4,
        evolution_params=EvolutionParams(
            octave_jump_every_n_cycles=4,
            octave_jump_indices=[3],
            timing_jitter_ms=8, velocity_jitter=8,
        ),
        rng_seed_base=20, target_track='BASS',
    )

    drums_layer = LayerSpec(
        motif_render_func=render_drums,
        motif_id='syncopated_kick',
        entry_at_bar=13, exit_at_bar=61,
        cycle_duration_beats=4.0,
        base_volume=1.0,
        entry_fade_bars=4, exit_fade_bars=4,
        rng_seed_base=30, target_track='DRUMS',
    )

    pad_layer = LayerSpec(
        motif_render_func=render_pad,
        motif_id='aeolian_progression',
        entry_at_bar=5, exit_at_bar=65,
        cycle_duration_beats=16.0,    # 4-bar progression = 16 beats per cycle
        base_volume=0.8,
        entry_fade_bars=8, exit_fade_bars=8,
        rng_seed_base=40, target_track='PAD',
    )

    lead_layer = LayerSpec(
        motif_render_func=render_lead,
        motif_id='ascending_counter',
        entry_at_bar=30, exit_at_bar=59,
        cycle_duration_beats=8.0,
        base_volume=0.85,
        entry_fade_bars=2, exit_fade_bars=4,
        evolution_params=EvolutionParams(
            timing_jitter_ms=6, velocity_jitter=6, gate_jitter_pct=8,
        ),
        rng_seed_base=50, target_track='LEAD',
    )

    composition = Composition(
        recipe_ids=[
            'mid_tempo_aggression_not_hardcore_speed',
            'descending_riff_as_song_identity',
            'syncopated_kick_creates_implied_meter_within_4_4',
            'robot_rock_hypnotic_repetitive_riff_with_micro_variations',
            'drone_foundation_as_compositional_anchor',
            'compressed_economy_under_three_minutes_in_long_album',
            'abrupt_song_end_no_fade',
        ],
        tonic_pitch=TONIC,
        total_bars=64,
        tempo_bpm=108,
        layers_per_track={
            'SUB':   [sub_layer],
            'BASS':  [bass_layer],
            'DRUMS': [drums_layer],
            'PAD':   [pad_layer],
            'LEAD':  [lead_layer],
        },
        rng_seed=42,
    )

    print('=== Compose Banger v3 demo ===')
    result = compose(composition)

    print(f'Tempo: {result["tempo_bpm"]} BPM')
    print(f'Total bars: {result["total_bars"]}')
    print(f'Tonic: {result["tonic_pitch"]}')
    print()
    print('Plan summary:')
    p = result['plan']
    print(f'  Resolved tempo: {p["tempo_bpm"]}')
    print(f'  Total bars (form): {p["total_bars"]}')
    print(f'  Ending: {p["ending_type"]}')
    print(f'  Conflicts: {len(p["conflicts"])}')
    print()
    print('Diagnostics:')
    d = result['diagnostics']
    for tname, c in d['note_count_per_track'].items():
        print(f'  {tname:6s}: {d["layer_count_per_track"][tname]} layer(s), {c} notes')
    print(f'  TOTAL: {d["total_notes"]} notes')

    # Sample some velocity values per track per "section"
    print('\n=== Sample velocity per track at key bar markers ===')
    sample_bars = [4, 8, 16, 32, 48, 56, 60, 64]
    print(f'{"track":6s}', *(f'{b:>8}' for b in sample_bars))
    for tname in ['SUB', 'BASS', 'DRUMS', 'PAD', 'LEAD']:
        notes = result['tracks'].get(tname, [])
        row = []
        for b in sample_bars:
            bar_notes = sorted([n for n in notes if (b-1)*4 <= n['time'] < b*4],
                              key=lambda n: n['time'])
            if bar_notes:
                row.append(f'{bar_notes[0]["velocity"]:>4}')
            else:
                row.append('   -')
        print(f'{tname:6s}', *(f'{v:>8s}' for v in row))
