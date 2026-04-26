"""Banger v3 FILTER HOUSE variant — Phase 9-3 design.

Demonstrates engine generalization: same engine, Daft-Punk-leaning recipes.

Variant profile (vs main v3 industrial-techno):
    - 122 BPM (filter-house tempo)
    - D minor, Aeolian
    - 4-on-the-floor kick (NOT syncopated)
    - 8th-note hat (house tradition, not 16th-microvar robot-rock)
    - Vocoded-phrase melody as LEAD (call/response with built-in 2-beat rest)
    - Filter-house chord-stab loop (i-♭VI-IV-V) on PAD
    - Bass: simple alternating root-fifth pattern (no robot_rock variations)
    - 64 bars / 2:06 — extended-form dance track
"""
import sys
sys.path.insert(0, '/home/user/Mix-Analyzer')

from composition_engine.motifs.melodic import MELODIC_MOTIFS, render as render_melodic
from composition_engine.motifs.rhythmic import RHYTHMIC_MOTIFS
from composition_engine.motifs.harmonic import HARMONIC_PROGRESSIONS, render as render_harmonic
from composition_engine.composer.motif_evolution import EvolutionParams
from composition_engine.composer.track_layerer import LayerSpec
from composition_engine.composer.composer import Composition

TONIC = 50              # D3
TEMPO_BPM = 122
TOTAL_BARS = 64


def render_sub_drone(cycle_idx):
    return render_melodic(MELODIC_MOTIFS['national_anthem_pedal_bass_walking'],
                          tonic_pitch=TONIC, octave_offset=-1)


def render_bass_pedal(cycle_idx):
    """House-style bass: just root-fifth alternation, no aggressive variations."""
    return render_melodic(MELODIC_MOTIFS['national_anthem_pedal_bass_walking'],
                          tonic_pitch=TONIC - 12)


def render_kick_4on4(cycle_idx):
    """Pure 4-on-the-floor kick — no syncopation."""
    m = RHYTHMIC_MOTIFS['four_on_floor_house_pure']
    return [{'time': t, 'duration': dur, 'velocity': v, 'pitch': m['drum_pitch']}
            for (t, dur), v in zip(m['rhythm_beats'], m['velocity_contour'])]


def render_kick_offbeat_ghost(cycle_idx):
    """4-on-floor + offbeat ghost — adds forward propulsion."""
    m = RHYTHMIC_MOTIFS['four_on_floor_with_offbeat_ghost']
    return [{'time': t, 'duration': dur, 'velocity': v, 'pitch': m['drum_pitch']}
            for (t, dur), v in zip(m['rhythm_beats'], m['velocity_contour'])]


def render_snare_backbeat(cycle_idx):
    m = RHYTHMIC_MOTIFS['snare_backbeat_pure']
    return [{'time': t, 'duration': dur, 'velocity': v, 'pitch': m['drum_pitch']}
            for (t, dur), v in zip(m['rhythm_beats'], m['velocity_contour'])]


def render_hat_8th(cycle_idx):
    """8th-note closed hat with downbeat accent — house tradition."""
    m = RHYTHMIC_MOTIFS['hat_8th_accent_house']
    return [{'time': t, 'duration': dur, 'velocity': v, 'pitch': m['drum_pitch']}
            for (t, dur), v in zip(m['rhythm_beats'], m['velocity_contour'])]


def render_pad_filter_house(cycle_idx):
    """Filter-house chord-stab progression i-♭VI-IV-V (Dm-Bb-G-A)."""
    return render_harmonic(HARMONIC_PROGRESSIONS['filter_house_i_vi_IV_V_loop'],
                           tonic_pitch=TONIC, velocity=85)


def render_lead_vocoded(cycle_idx):
    """Vocoded call-response melody with 2-beat built-in breath."""
    return render_melodic(MELODIC_MOTIFS['vocoded_phrase_call_response_2bar'],
                          tonic_pitch=TONIC + 12)


LAYERS_PER_TRACK = {
    'SUB': [
        # Constant SUB drone in deep octave
        LayerSpec(
            motif_render_func=render_sub_drone,
            motif_id='sub_drone',
            entry_at_bar=1, exit_at_bar=64,
            cycle_duration_beats=8.0,
            base_volume=0.85,
            entry_fade_bars=4, exit_fade_bars=4,
            evolution_params=EvolutionParams(
                timing_jitter_ms=3, velocity_jitter=3, gate_jitter_pct=4,
            ),
            rng_seed_base=10, target_track='SUB',
        ),
    ],

    'BASS': [
        # House bass enters at bar 9 (after intro)
        LayerSpec(
            motif_render_func=render_bass_pedal,
            motif_id='house_bass',
            entry_at_bar=9, exit_at_bar=61,
            cycle_duration_beats=8.0,
            base_volume=1.0,
            entry_fade_bars=4, exit_fade_bars=4,
            evolution_params=EvolutionParams(
                timing_jitter_ms=4, velocity_jitter=6, gate_jitter_pct=10,
            ),
            rng_seed_base=20, target_track='BASS',
        ),
    ],

    'DRUMS': [
        # KICK: 4-on-floor pure for first half (bars 5-32)
        LayerSpec(
            motif_render_func=render_kick_4on4,
            motif_id='kick_4on4_pure',
            entry_at_bar=5, exit_at_bar=33,
            cycle_duration_beats=4.0,
            base_volume=1.0,
            entry_fade_bars=2, exit_fade_bars=0,
            evolution_params=EvolutionParams(
                timing_jitter_ms=3, velocity_jitter=5,
            ),
            rng_seed_base=30, target_track='DRUMS',
        ),
        # KICK upgrade: offbeat-ghost for second half (bars 33-60) — intensification
        LayerSpec(
            motif_render_func=render_kick_offbeat_ghost,
            motif_id='kick_with_ghost',
            entry_at_bar=33, exit_at_bar=61,
            cycle_duration_beats=4.0,
            base_volume=1.0,
            entry_fade_bars=0, exit_fade_bars=4,
            evolution_params=EvolutionParams(
                timing_jitter_ms=3, velocity_jitter=5,
            ),
            rng_seed_base=31, target_track='DRUMS',
        ),
        # SNARE: classic backbeat throughout drum section
        LayerSpec(
            motif_render_func=render_snare_backbeat,
            motif_id='snare_backbeat',
            entry_at_bar=13, exit_at_bar=60,
            cycle_duration_beats=4.0,
            base_volume=0.9,
            entry_fade_bars=4, exit_fade_bars=4,
            evolution_params=EvolutionParams(
                timing_jitter_ms=4, velocity_jitter=7,
            ),
            rng_seed_base=32, target_track='DRUMS',
        ),
        # HAT: 8th-note accent throughout
        LayerSpec(
            motif_render_func=render_hat_8th,
            motif_id='hat_8th',
            entry_at_bar=17, exit_at_bar=60,
            cycle_duration_beats=4.0,
            base_volume=0.7,
            entry_fade_bars=4, exit_fade_bars=4,
            evolution_params=EvolutionParams(
                timing_jitter_ms=3, velocity_jitter=6,
            ),
            rng_seed_base=33, target_track='DRUMS',
        ),
    ],

    'PAD': [
        # Filter-house chord-stab progression — sustained throughout
        LayerSpec(
            motif_render_func=render_pad_filter_house,
            motif_id='pad_filter_house',
            entry_at_bar=5, exit_at_bar=64,
            cycle_duration_beats=16.0,    # 4-bar progression
            base_volume=0.75,
            entry_fade_bars=4, exit_fade_bars=8,
            rng_seed_base=40, target_track='PAD',
        ),
    ],

    'LEAD': [
        # Vocoded call-response intro — bars 25-40 (between intro-build and peak)
        LayerSpec(
            motif_render_func=render_lead_vocoded,
            motif_id='lead_vocoded_call',
            entry_at_bar=25, exit_at_bar=41,
            cycle_duration_beats=8.0,    # 2-bar phrase
            base_volume=0.85,
            entry_fade_bars=2, exit_fade_bars=2,
            evolution_params=EvolutionParams(
                octave_jump_every_n_cycles=4,
                octave_jump_indices=[6],    # last note octave-jumped every 4 cycles
                timing_jitter_ms=5, velocity_jitter=6, gate_jitter_pct=8,
            ),
            rng_seed_base=50, target_track='LEAD',
        ),
        # Vocoded extended — bars 49-58 (peak section)
        LayerSpec(
            motif_render_func=render_lead_vocoded,
            motif_id='lead_vocoded_peak',
            entry_at_bar=49, exit_at_bar=59,
            cycle_duration_beats=8.0,
            base_volume=1.0,    # peak intensity
            entry_fade_bars=2, exit_fade_bars=4,
            evolution_params=EvolutionParams(
                octave_jump_every_n_cycles=2,    # MORE octave-jumps in peak
                octave_jump_indices=[6],
                timing_jitter_ms=4, velocity_jitter=8, gate_jitter_pct=10,
            ),
            rng_seed_base=51, target_track='LEAD',
        ),
    ],
}


BANGER_FILTER_HOUSE_COMPOSITION = Composition(
    recipe_ids=[
        'four_on_the_floor_120_bpm_house_foundation',
        'tr_909_drum_machine_as_compositional_instrument',
        'compositional_movement_via_filter_not_via_chord_change',
        'drone_foundation_as_compositional_anchor',
        'pop_song_structure_within_electronic_vocabulary',
        'compressed_economy_under_three_minutes_in_long_album',
    ],
    tonic_pitch=TONIC,
    total_bars=TOTAL_BARS,
    tempo_bpm=TEMPO_BPM,
    layers_per_track=LAYERS_PER_TRACK,
    apply_finalization=True,
    anchor_tracks=['DRUMS', 'SUB', 'BASS'],
    rng_seed=77,
)


if __name__ == '__main__':
    from composition_engine.composer.composer import compose

    print('=== Banger Filter House design ===')
    print(f'Tonic={TONIC} (D3), Tempo={TEMPO_BPM} BPM, Bars={TOTAL_BARS}')
    print(f'Recipes: {BANGER_FILTER_HOUSE_COMPOSITION.recipe_ids}')

    result = compose(BANGER_FILTER_HOUSE_COMPOSITION)
    d = result['diagnostics']
    print(f'\nTotal notes: {d["total_notes"]}')
    for t, c in d['note_count_per_track'].items():
        print(f'  {t}: {c} notes ({d["layer_count_per_track"][t]} layer(s))')
