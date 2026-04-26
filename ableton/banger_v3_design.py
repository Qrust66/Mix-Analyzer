"""Banger v3 design — Phase 8-1.

Uses the composition_engine to design a deterministic banger composition.
Validated via quality_constraints checks BEFORE rendering.

Composition profile:
    - 64 bars at 108 BPM (mid-tempo aggression — advisor)
    - D minor, Aeolian with Phrygian inflection in mid-track
    - 5 tracks with organic non-sectional entries:
        SUB (drone)        bars 1-60
        BASS (riff)         bars 5-60
        DRUMS (syncopated)  bars 9-60
        PAD (modal)         bars 5-64
        LEAD (counter)      bars 30-58
    - All trapezoidal envelopes (entry → sustain → exit fades)
    - Cross-cycle drift via EvolutionParams (octave-jumps, transpose drift,
      gate-length drift, tonal_substitution to phrygian mid-track)
    - Cross-track collision finalization

Output: a Composition object ready to feed into composer.compose()
"""
import sys
sys.path.insert(0, '/home/user/Mix-Analyzer')

from composition_engine.motifs.melodic import MELODIC_MOTIFS, render as render_melodic
from composition_engine.motifs.rhythmic import RHYTHMIC_MOTIFS
from composition_engine.motifs.harmonic import HARMONIC_PROGRESSIONS, render as render_harmonic, VOICINGS
from composition_engine.composer.motif_evolution import EvolutionParams
from composition_engine.composer.track_layerer import LayerSpec
from composition_engine.composer.composer import Composition


# ============================================================================
# Composition design parameters
# ============================================================================

TONIC = 50              # D3
TEMPO_BPM = 108
TOTAL_BARS = 64

# Aeolian scale intervals from D
AEOLIAN_INTERVALS = [0, 2, 3, 5, 7, 8, 10]


# ============================================================================
# Per-track render functions (each returns a fresh note-list at time 0)
# ============================================================================

def render_sub_drone(cycle_idx):
    """Walking pedal-bass in low register (octave below tonic)."""
    notes = render_melodic(MELODIC_MOTIFS['national_anthem_pedal_bass_walking'],
                           tonic_pitch=TONIC, octave_offset=-1)
    return notes


def render_bass_riff(cycle_idx):
    """Robot-rock riff (D2-area), micro-variations applied via evolve_motif."""
    return render_melodic(MELODIC_MOTIFS['robot_rock_riff_with_micro_variations'],
                          tonic_pitch=TONIC - 12)


def render_drums_kick(cycle_idx):
    """Single-cycle render of syncopated_kick at GM kick pitch (36)."""
    m = RHYTHMIC_MOTIFS['syncopated_kick_3_against_4']
    return [{'time': t, 'duration': dur, 'velocity': v, 'pitch': m['drum_pitch']}
            for (t, dur), v in zip(m['rhythm_beats'], m['velocity_contour'])]


def render_drums_snare(cycle_idx):
    """Snare with ghost notes — pocket-rich live-drummer feel."""
    m = RHYTHMIC_MOTIFS['snare_with_ghost_notes_groove']
    return [{'time': t, 'duration': dur, 'velocity': v, 'pitch': m['drum_pitch']}
            for (t, dur), v in zip(m['rhythm_beats'], m['velocity_contour'])]


def render_drums_hat(cycle_idx):
    """16th-note hat with robot_rock micro-variations."""
    m = RHYTHMIC_MOTIFS['hat_16th_micro_variation_robot_rock']
    return [{'time': t, 'duration': dur, 'velocity': v, 'pitch': m['drum_pitch']}
            for (t, dur), v in zip(m['rhythm_beats'], m['velocity_contour'])]


def render_pad_aeolian(cycle_idx):
    """Aeolian Dm-Bb-C-Dm progression."""
    return render_harmonic(HARMONIC_PROGRESSIONS['aeolian_i_VI_VII_i'],
                           tonic_pitch=TONIC, velocity=80)


def render_pad_phrygian(cycle_idx):
    """Phrygian dark-color progression for mid-track tension."""
    return render_harmonic(HARMONIC_PROGRESSIONS['phrygian_dark_descending'],
                           tonic_pitch=TONIC, velocity=85)


def render_lead_counter(cycle_idx):
    """Ascending counter-melody against bass descent."""
    return render_melodic(MELODIC_MOTIFS['ascending_counter_to_descending_bass'],
                          tonic_pitch=TONIC + 12)


def render_lead_phrygian(cycle_idx):
    """Phrygian inflection lead — appears mid-track for the dark moment."""
    return render_melodic(MELODIC_MOTIFS['phrygian_inflection_dark_color'],
                          tonic_pitch=TONIC + 12)


# ============================================================================
# Layers per track (trapezoidal envelopes, drift parameters per advisor)
# ============================================================================

LAYERS_PER_TRACK = {
    # === SUB: drone foundation ===
    # Long sustain bars 1-60 with subtle gate-length drift (humanization across cycles)
    'SUB': [
        LayerSpec(
            motif_render_func=render_sub_drone,
            motif_id='national_anthem_pedal_bass',
            entry_at_bar=1, exit_at_bar=61,
            cycle_duration_beats=8.0,    # 2-bar motif
            base_volume=1.0,
            entry_fade_bars=2, exit_fade_bars=4,
            evolution_params=EvolutionParams(
                gate_drift_per_cycle=-0.005,   # gradually shorter gate (0.5% per cycle)
                timing_jitter_ms=4, velocity_jitter=4, gate_jitter_pct=8,
            ),
            rng_seed_base=10, target_track='SUB',
        ),
    ],

    # === BASS: robot-rock riff with octave-jump cycles ===
    'BASS': [
        LayerSpec(
            motif_render_func=render_bass_riff,
            motif_id='robot_rock_riff',
            entry_at_bar=5, exit_at_bar=61,
            cycle_duration_beats=4.0,
            base_volume=1.0,
            entry_fade_bars=4, exit_fade_bars=4,
            evolution_params=EvolutionParams(
                octave_jump_every_n_cycles=4,
                octave_jump_indices=[3],     # last note octave-jumped every 4 cycles
                timing_jitter_ms=8, velocity_jitter=8, gate_jitter_pct=15,
            ),
            rng_seed_base=20, target_track='BASS',
        ),
    ],

    # === DRUMS: kick + snare + hat all on one track (Drum Rack) ===
    'DRUMS': [
        # KICK enters at bar 9 with full syncopated pattern + skip-rule cycles
        LayerSpec(
            motif_render_func=render_drums_kick,
            motif_id='syncopated_kick',
            entry_at_bar=9, exit_at_bar=61,
            cycle_duration_beats=4.0,
            base_volume=1.0,
            entry_fade_bars=4, exit_fade_bars=4,
            evolution_params=EvolutionParams(
                timing_jitter_ms=6, velocity_jitter=8, gate_jitter_pct=10,
            ),
            rng_seed_base=30, target_track='DRUMS',
        ),
        # SNARE enters at bar 13 with ghost-notes
        LayerSpec(
            motif_render_func=render_drums_snare,
            motif_id='snare_with_ghosts',
            entry_at_bar=13, exit_at_bar=60,
            cycle_duration_beats=4.0,
            base_volume=0.95,
            entry_fade_bars=4, exit_fade_bars=4,
            evolution_params=EvolutionParams(
                timing_jitter_ms=10, velocity_jitter=10, gate_jitter_pct=12,
            ),
            rng_seed_base=31, target_track='DRUMS',
        ),
        # HAT enters at bar 17 (the third drum-element layer)
        LayerSpec(
            motif_render_func=render_drums_hat,
            motif_id='hat_16th_microvar',
            entry_at_bar=17, exit_at_bar=60,
            cycle_duration_beats=4.0,
            base_volume=0.85,
            entry_fade_bars=2, exit_fade_bars=4,
            evolution_params=EvolutionParams(
                timing_jitter_ms=4, velocity_jitter=12, gate_jitter_pct=8,
            ),
            rng_seed_base=32, target_track='DRUMS',
        ),
    ],

    # === PAD: 2 progressions stitched — Aeolian most of song, Phrygian in middle ===
    'PAD': [
        # Aeolian foundation bars 5-28 (first half) and 37-64 (second half)
        LayerSpec(
            motif_render_func=render_pad_aeolian,
            motif_id='pad_aeolian',
            entry_at_bar=5, exit_at_bar=29,
            cycle_duration_beats=16.0,    # 4-bar progression
            base_volume=0.75,
            entry_fade_bars=8, exit_fade_bars=2,
            rng_seed_base=40, target_track='PAD',
        ),
        # Phrygian darkness bars 29-37 (the mid-track tension moment)
        LayerSpec(
            motif_render_func=render_pad_phrygian,
            motif_id='pad_phrygian',
            entry_at_bar=29, exit_at_bar=37,
            cycle_duration_beats=16.0,    # 4-bar progression  -- 8 bars = 2 cycles
            base_volume=0.85,
            entry_fade_bars=2, exit_fade_bars=2,
            rng_seed_base=41, target_track='PAD',
        ),
        # Aeolian return bars 37-65
        LayerSpec(
            motif_render_func=render_pad_aeolian,
            motif_id='pad_aeolian_return',
            entry_at_bar=37, exit_at_bar=65,
            cycle_duration_beats=16.0,
            base_volume=0.85,
            entry_fade_bars=2, exit_fade_bars=8,
            rng_seed_base=42, target_track='PAD',
        ),
    ],

    # === LEAD: 2 motifs — Phrygian inflection mid-track + ascending counter late ===
    'LEAD': [
        # Phrygian inflection during PAD-Phrygian moment (bars 29-36)
        LayerSpec(
            motif_render_func=render_lead_phrygian,
            motif_id='lead_phrygian_inflection',
            entry_at_bar=29, exit_at_bar=37,
            cycle_duration_beats=8.0,    # this motif is 8 beats
            base_volume=0.85,
            entry_fade_bars=2, exit_fade_bars=2,
            rng_seed_base=50, target_track='LEAD',
        ),
        # Ascending counter-melody during the bass-descent intensity bars 41-58
        LayerSpec(
            motif_render_func=render_lead_counter,
            motif_id='lead_ascending_counter',
            entry_at_bar=41, exit_at_bar=59,
            cycle_duration_beats=8.0,
            base_volume=0.9,
            entry_fade_bars=2, exit_fade_bars=4,
            evolution_params=EvolutionParams(
                timing_jitter_ms=8, velocity_jitter=8, gate_jitter_pct=12,
            ),
            rng_seed_base=51, target_track='LEAD',
        ),
    ],
}


# ============================================================================
# Composition assembly
# ============================================================================

BANGER_V3_COMPOSITION = Composition(
    recipe_ids=[
        # Tempo & form directives
        'mid_tempo_aggression_not_hardcore_speed',
        'compressed_economy_under_three_minutes_in_long_album',
        'abrupt_song_end_no_fade',
        # Rhythmic recipes
        'syncopated_kick_creates_implied_meter_within_4_4',
        'robot_rock_hypnotic_repetitive_riff_with_micro_variations',
        # Melodic recipes
        'descending_riff_as_song_identity',
        'drone_foundation_as_compositional_anchor',
        # Harmonic recipes
        'modal_voicings_above_drone_replace_chord_progression',
        'classical_influenced_chord_progression_in_electronic_context',
        # Phrasing recipes
        'mingus_freedom_chromatic_harmony_inspiration',    # Phrygian inflection
    ],
    tonic_pitch=TONIC,
    total_bars=TOTAL_BARS,
    tempo_bpm=TEMPO_BPM,
    layers_per_track=LAYERS_PER_TRACK,
    apply_finalization=True,
    anchor_tracks=['DRUMS', 'SUB', 'BASS'],
    rng_seed=42,
)


# ============================================================================
# Self-test — render and run quality checks
# ============================================================================

if __name__ == '__main__':
    from composition_engine.composer.composer import compose
    from composition_engine.quality_constraints.duration_variety import flag_monotonous
    from composition_engine.quality_constraints.range_arc import flag_static_range
    from composition_engine.quality_constraints.phrasing_rests import flag_no_breath

    print('=== Banger v3 design summary ===')
    print(f'Tonic: {TONIC} (D3), Tempo: {TEMPO_BPM} BPM, Total: {TOTAL_BARS} bars')
    print(f'Recipes: {len(BANGER_V3_COMPOSITION.recipe_ids)}')
    for r in BANGER_V3_COMPOSITION.recipe_ids:
        print(f'  - {r}')
    print(f'\nLayers per track:')
    for tname, layers in LAYERS_PER_TRACK.items():
        print(f'  {tname}: {len(layers)} layer(s)')
        for l in layers:
            print(f'    [{l.motif_id}] bars {l.entry_at_bar}-{l.exit_at_bar} fade {l.entry_fade_bars}/{l.exit_fade_bars} vol={l.base_volume}')

    # Render
    print('\n=== Rendering composition ===')
    result = compose(BANGER_V3_COMPOSITION)
    d = result['diagnostics']
    print(f'Total notes: {d["total_notes"]}')
    for tname, c in d['note_count_per_track'].items():
        print(f'  {tname}: {c} notes')

    # Quality checks per track
    print('\n=== Quality checks per track ===')
    total_dur = TOTAL_BARS * 4.0
    for tname, notes in result['tracks'].items():
        dur_diag = flag_monotonous(notes, threshold_bits=1.5)
        rng_diag = flag_static_range(notes, min_span_semitones=5)
        brth_diag = flag_no_breath(notes, total_duration=total_dur,
                                   min_rest_density=0.05, max_continuous_beats=24)

        print(f'\n{tname}:')
        print(f'  duration variety: entropy={dur_diag["entropy_bits"]}b, distinct={dur_diag["distinct_durations"]} → {"🚩" if dur_diag["is_monotonous"] else "✓"}')
        print(f'  range/arc: span={rng_diag["span_semitones"]}st, shape={rng_diag["arc_shape"]} → {"🚩" if rng_diag["is_static"] else "✓"}')
        print(f'  phrasing: rest_density={brth_diag["rest_density"]}, longest_block={brth_diag["longest_continuous_beats"]}b → {"🚩" if brth_diag["is_no_breath"] else "✓"}')
