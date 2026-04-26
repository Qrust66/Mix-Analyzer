"""Banger v3 AMBIENT MEDITATIVE variant — Phase 9-1.

Demonstrates the composition_engine generalizes. Same engine, different recipes.

Variant profile (vs main v3 industrial-techno):
    - Yorke-leaning blend (no Cobain aggression, no Reznor industrial)
    - 90 BPM (slower than 108) — meditative tempo
    - 64 bars / 2:50 — extended ambient form
    - 3 tracks only (SUB drone + PAD modal + LEAD ondes-martenot-style)
    - NO drums (pure ambient)
    - Atmospheric pad voicings (sus2 / sus_4_with_9 / quartal)
    - Drone foundation continuous, no bass-line aggression
    - Phrygian inflection deep in the middle for emotional weight
"""
import sys
sys.path.insert(0, '/home/user/Mix-Analyzer')

from composition_engine.motifs.melodic import MELODIC_MOTIFS, render as render_melodic
from composition_engine.motifs.harmonic import HARMONIC_PROGRESSIONS, render as render_harmonic
from composition_engine.composer.motif_evolution import EvolutionParams
from composition_engine.composer.track_layerer import LayerSpec
from composition_engine.composer.composer import Composition

TONIC = 50              # D3
TEMPO_BPM = 90
TOTAL_BARS = 64


def render_sub_drone(cycle_idx):
    """Pedal-bass walking pattern in deep sub-octave."""
    return render_melodic(MELODIC_MOTIFS['national_anthem_pedal_bass_walking'],
                          tonic_pitch=TONIC, octave_offset=-2)


def render_pad_dub_static(cycle_idx):
    """Dub-techno static-modal-shift progression — slow voicing drift over 32 beats."""
    return render_harmonic(HARMONIC_PROGRESSIONS['dub_techno_static_modal_shift'],
                           tonic_pitch=TONIC, velocity=78)


def render_pad_dorian_floating(cycle_idx):
    """Dorian sus floating progression — light/bright modal moment."""
    return render_harmonic(HARMONIC_PROGRESSIONS['dorian_sus_floating'],
                           tonic_pitch=TONIC, velocity=72)


def render_lead_phrygian_inflection(cycle_idx):
    """Phrygian inflection — the emotional dark moment in the ambient texture."""
    return render_melodic(MELODIC_MOTIFS['phrygian_inflection_dark_color'],
                          tonic_pitch=TONIC + 12)


def render_lead_modal_voicing(cycle_idx):
    """Soprano-line modal motion above sustained pad — the EIRP-style top-line."""
    return render_melodic(MELODIC_MOTIFS['modal_voice_leading_smooth_pad'],
                          tonic_pitch=TONIC + 12)


LAYERS_PER_TRACK = {
    'SUB': [
        # Long sustained drone with slow gate-drift across full song
        LayerSpec(
            motif_render_func=render_sub_drone,
            motif_id='ambient_pedal_drone',
            entry_at_bar=1, exit_at_bar=64,
            cycle_duration_beats=8.0,
            base_volume=0.85,
            entry_fade_bars=8, exit_fade_bars=12,    # slow ambient fades
            evolution_params=EvolutionParams(
                gate_drift_per_cycle=-0.003,    # gentle gate decrease
                timing_jitter_ms=3, velocity_jitter=3, gate_jitter_pct=5,
            ),
            rng_seed_base=10, target_track='SUB',
        ),
    ],

    'PAD': [
        # Dub-techno static-modal-shift bars 1-30 (Aeolian darkness + voicing drift)
        LayerSpec(
            motif_render_func=render_pad_dub_static,
            motif_id='pad_dub_static',
            entry_at_bar=1, exit_at_bar=33,
            cycle_duration_beats=32.0,
            base_volume=0.7,
            entry_fade_bars=8, exit_fade_bars=4,
            rng_seed_base=20, target_track='PAD',
        ),
        # Dorian sus floating bars 33-50 (lift toward bright modal-color)
        LayerSpec(
            motif_render_func=render_pad_dorian_floating,
            motif_id='pad_dorian_lift',
            entry_at_bar=33, exit_at_bar=50,
            cycle_duration_beats=16.0,
            base_volume=0.75,
            entry_fade_bars=4, exit_fade_bars=4,
            rng_seed_base=21, target_track='PAD',
        ),
        # Return to Dub-techno static for resolution bars 50-64
        LayerSpec(
            motif_render_func=render_pad_dub_static,
            motif_id='pad_dub_return',
            entry_at_bar=50, exit_at_bar=65,
            cycle_duration_beats=32.0,
            base_volume=0.7,
            entry_fade_bars=2, exit_fade_bars=12,    # long fade-out
            rng_seed_base=22, target_track='PAD',
        ),
    ],

    'LEAD': [
        # Modal voice-leading soprano line bars 9-30 (the floating top voice)
        LayerSpec(
            motif_render_func=render_lead_modal_voicing,
            motif_id='lead_modal_top',
            entry_at_bar=9, exit_at_bar=33,
            cycle_duration_beats=16.0,
            base_volume=0.65,
            entry_fade_bars=6, exit_fade_bars=4,
            evolution_params=EvolutionParams(
                timing_jitter_ms=8, velocity_jitter=5, gate_jitter_pct=10,
            ),
            rng_seed_base=30, target_track='LEAD',
        ),
        # Phrygian inflection bars 30-42 — the dark emotional centerpiece
        LayerSpec(
            motif_render_func=render_lead_phrygian_inflection,
            motif_id='lead_phrygian_dark_moment',
            entry_at_bar=30, exit_at_bar=43,
            cycle_duration_beats=8.0,
            base_volume=0.85,    # featured during emotional moment
            entry_fade_bars=2, exit_fade_bars=4,
            evolution_params=EvolutionParams(
                timing_jitter_ms=6, velocity_jitter=4, gate_jitter_pct=8,
            ),
            rng_seed_base=31, target_track='LEAD',
        ),
        # Modal voicing return bars 42-58 (resolution)
        LayerSpec(
            motif_render_func=render_lead_modal_voicing,
            motif_id='lead_modal_return',
            entry_at_bar=42, exit_at_bar=58,
            cycle_duration_beats=16.0,
            base_volume=0.55,    # softer than initial entry
            entry_fade_bars=4, exit_fade_bars=8,
            rng_seed_base=32, target_track='LEAD',
        ),
    ],
}


BANGER_AMBIENT_COMPOSITION = Composition(
    recipe_ids=[
        'drone_foundation_as_compositional_anchor',
        'modal_voicings_above_drone_replace_chord_progression',
        'classical_influenced_chord_progression_in_electronic_context',
        'mingus_freedom_chromatic_harmony_inspiration',
    ],
    tonic_pitch=TONIC,
    total_bars=TOTAL_BARS,
    tempo_bpm=TEMPO_BPM,
    layers_per_track=LAYERS_PER_TRACK,
    apply_finalization=True,
    anchor_tracks=['SUB'],   # ambient: only SUB needs grid-anchor
    rng_seed=99,
)


if __name__ == '__main__':
    from composition_engine.composer.composer import compose

    print('=== Banger Ambient design ===')
    print(f'Tonic={TONIC} (D3), Tempo={TEMPO_BPM} BPM, Bars={TOTAL_BARS}')
    print(f'Recipes: {BANGER_AMBIENT_COMPOSITION.recipe_ids}')
    print(f'Tracks: {list(LAYERS_PER_TRACK.keys())}')

    result = compose(BANGER_AMBIENT_COMPOSITION)
    d = result['diagnostics']
    print(f'\nTotal notes: {d["total_notes"]}')
    for t, c in d['note_count_per_track'].items():
        print(f'  {t}: {c} notes ({d["layer_count_per_track"][t]} layer(s))')
