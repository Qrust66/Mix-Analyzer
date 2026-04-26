"""Recipe → strategy — Phase 5-2 of composition_engine.

Maps each advisor recipe to a COMPOSITION STRATEGY: not just which motifs to
use, but HOW to deploy them — which transforms to apply, which primitives to
chain, which humanization rules to enable.

A `Strategy` is a structured plan the Phase-6 composer can execute:
    {
        'motif_choice': str,                       # selected motif id
        'motif_type': str,                          # melodic / rhythmic / harmonic
        'transforms': List[(callable_name, kwargs)], # ordered transform pipeline
        'primitives': List[(callable_name, kwargs)], # phrase-shape primitives
        'humanization': {                            # humanization rules
            'timing_jitter_ms': float,
            'velocity_jitter': int,
            'gate_jitter_pct': float,
            'apply_motif_loop_humanization': bool,
        },
        'rationale': str,                           # why this strategy for this recipe
    }

API:
    strategy_for_recipe(recipe_id, ...) → Strategy
    list_strategies() → all hand-crafted strategy mappings
"""

from typing import Dict, Any, List, Optional


# ============================================================================
# Hand-crafted strategy mappings for documented recipes
# ============================================================================
# Each strategy maps a recipe → the canonical way to render it. When multiple
# motifs are available, the strategy says which to use FIRST (with reasoning).
#
# Recipe IDs match composition_advisor.json atom IDs.

STRATEGIES: Dict[str, Dict[str, Any]] = {}


# ----- Foundational rhythmic recipes -----

STRATEGIES['syncopated_kick_creates_implied_meter_within_4_4'] = {
    'motif_choice': 'syncopated_kick_3_against_4',
    'motif_type': 'rhythmic',
    'transforms': [
        # No additional transforms — the motif IS the recipe
    ],
    'primitives': [],
    'humanization': {
        'apply_motif_loop_humanization': True,
        # Motif's own micro_variation_rules will be used (timing ±15ms, velocity ±8, etc.)
    },
    'rationale': (
        'Direct mapping: the syncopated_kick_3_against_4 motif IS the canonical '
        'pattern documented in advisor (kick at {0, 0.75, 1.5, 2.25}). Loop with '
        'micro-variations (skip every 8 cycles, flam every 4) for breathing.'
    ),
}

STRATEGIES['four_on_the_floor_120_bpm_house_foundation'] = {
    'motif_choice': 'four_on_floor_house_pure',
    'motif_type': 'rhythmic',
    'transforms': [],
    'primitives': [],
    'humanization': {
        'apply_motif_loop_humanization': True,
    },
    'rationale': (
        'House foundation. Tighter timing (±3ms vs ±15ms for syncopated) — '
        '4-on-floor wants precision. Pair with hat_8th_accent_house at the same level.'
    ),
}

STRATEGIES['robot_rock_hypnotic_repetitive_riff_with_micro_variations'] = {
    'motif_choice': 'robot_rock_riff_with_micro_variations',
    'motif_type': 'melodic',
    'transforms': [],
    'primitives': [],
    'humanization': {
        'apply_motif_loop_humanization': True,
        'octave_jump_rule': {
            'every_n_cycles': 4,
            'cycle_index': 3,
            'note_indices': [3],
            'octaves': 1,
        },
        'retrograde_rule': {
            'every_n_cycles': 8,
            'apply_to_half': 'second',
        },
        'timing_jitter_ms': 8,
        'velocity_jitter': 8,
    },
    'rationale': (
        'Robot rock = repeat with documented micro-variations. octave-jump on note 3 '
        'every 4 cycles (advisor recipe), retrograde the second half every 8 cycles '
        'for surprise. Gate-length variation already baked into motif (0.4 vs 0.5).'
    ),
}


# ----- Foundational melodic recipes -----

STRATEGIES['descending_riff_as_song_identity'] = {
    'motif_choice': 'aeolian_descending_4_steps',
    'motif_type': 'melodic',
    'transforms': [
        # Could optionally add transpose for genre fit
    ],
    'primitives': [
        # apply velocity arc to make the descent feel intentional
        ('apply_arc_to_phrase', {
            'peak_position': 0.0,        # peak at start, descending intensity
            'velocity_low': 80, 'velocity_high': 115,
        }),
    ],
    'humanization': {
        'timing_jitter_ms': 6,
        'velocity_jitter': 6,
    },
    'rationale': (
        'Descending Aeolian D-C-Bb-A is the canonical descending-riff. Apply '
        'arc with peak at start (descent feels intentional, not just running '
        'down). Multi-source-tagged (Nirvana AA + SG Head Down + DP Veridis Quo + SP Soma).'
    ),
}

STRATEGIES['drone_foundation_as_compositional_anchor'] = {
    'motif_choice': 'national_anthem_pedal_bass_walking',
    'motif_type': 'melodic',
    'transforms': [
        # Render LOW (sub octave): octave_offset=-1 at render-time
    ],
    'primitives': [],
    'humanization': {
        'timing_jitter_ms': 4,
        'velocity_jitter': 4,
        'gate_jitter_pct': 5,
    },
    'rationale': (
        'D pedal-bass walking pattern (Yorke wrote at 16) provides the drone-anchor '
        'in low register. Voice on Sub37/Massive bass synth in octave -1. Combined '
        'with sustained tonic in deeper sub-bass for full drone-foundation.'
    ),
}


STRATEGIES['modal_voicings_above_drone_replace_chord_progression'] = {
    'motif_choice': 'modal_voice_leading_smooth_pad',
    'motif_type': 'melodic',     # this motif is the soprano line
    'transforms': [
        # Could augment_diminish ×2 for slower modal motion
    ],
    'primitives': [],
    'humanization': {
        'timing_jitter_ms': 3,
        'velocity_jitter': 3,
    },
    'rationale': (
        'Modal voice-leading = the soprano-line motion above sustained pad chords. '
        'Pair with dub_techno_static_modal_shift (harmonic) underneath for full '
        'modal-voicings-above-drone effect.'
    ),
}


# ----- Harmonic recipes -----

STRATEGIES['classical_influenced_chord_progression_in_electronic_context'] = {
    'motif_choice': 'pachelbel_descending_bass_8',
    'motif_type': 'harmonic',
    'transforms': [],
    'primitives': [
        # Apply voice-leading for smooth chord transitions
        ('apply_voice_leading_to_progression', {}),
    ],
    'humanization': {
        'timing_jitter_ms': 2,    # very tight (classical-tradition precision)
        'velocity_jitter': 4,
    },
    'rationale': (
        'Pachelbel-descending-bass + automatic voice-leading. Apply on Diva pad '
        'with slow attack (200-500ms) and long release (3-5s). At 80-100 BPM '
        'feels classical/cinematic; at 120-128 feels filter-house-classical.'
    ),
}


# ----- Phrase-shape recipes -----

STRATEGIES['hard_soft_hard_contrast_within_song'] = {
    'motif_choice': None,    # this is a SECTION-level recipe, no single motif
    'motif_type': None,
    'transforms': [],
    'primitives': [
        # The composer applies this at SECTION level: drop drums in breakdown,
        # return at full density in verse-B. This strategy describes the
        # section-level tag for the composer.
    ],
    'humanization': {},
    'section_directives': {
        'breakdown': {'drums_density_factor': 0.0, 'pad_voicing': 'phrygian'},
        'verse_a': {'drums_density_factor': 1.0},
        'verse_b': {'drums_density_factor': 1.0},
    },
    'rationale': (
        'Not a per-motif strategy — this is a SECTION-LEVEL directive: drum density '
        '→ 0 in breakdown, full in verses. Composer Phase-6 will read section_directives '
        'and apply at the arrangement layer.'
    ),
}


STRATEGIES['density_arc_arrangement_sparse_to_wall'] = {
    'motif_choice': None,
    'motif_type': None,
    'transforms': [],
    'primitives': [
        ('apply_dynamic_arc_section', {}),    # one of intro/build/verse/breakdown/drop/outro
    ],
    'humanization': {},
    'section_directives': {
        # Layer count per section (composer applies)
        'intro':     {'active_tracks': ['SUB']},
        'build':     {'active_tracks': ['SUB', 'BASS']},
        'verse_a':   {'active_tracks': ['SUB', 'BASS', 'DRUMS', 'PAD']},
        'breakdown': {'active_tracks': ['SUB', 'PAD', 'LEAD']},
        'verse_b':   {'active_tracks': ['SUB', 'BASS', 'DRUMS', 'PAD', 'LEAD']},
        'drop':      {'active_tracks': ['SUB', 'BASS', 'DRUMS', 'PAD', 'LEAD']},
        'outro':     {'active_tracks': ['SUB', 'PAD']},
    },
    'rationale': (
        'Section-level layer count directive. Density grows: intro=1 → build=2 → '
        'verse=4 → breakdown=3 → verse=5 → drop=5 → outro=2. Composer applies.'
    ),
}


# ----- Tempo / form recipes -----

STRATEGIES['mid_tempo_aggression_not_hardcore_speed'] = {
    'motif_choice': None,    # tempo-level directive
    'motif_type': None,
    'transforms': [],
    'primitives': [],
    'humanization': {},
    'tempo_directive': {'bpm': 108, 'range': (100, 115)},
    'rationale': (
        'Tempo directive: 108 BPM (range 100-115). Composer uses this when '
        'this recipe is selected for the song.'
    ),
}


STRATEGIES['compressed_economy_under_three_minutes_in_long_album'] = {
    'motif_choice': None,
    'motif_type': None,
    'transforms': [],
    'primitives': [],
    'humanization': {},
    'form_directive': {'total_bars': 64, 'max_runtime_seconds': 180},
    'rationale': (
        'Form directive: ≤3 min runtime, around 64 bars at typical mid-tempo BPM '
        '(108-120). Composer respects this as a global form constraint.'
    ),
}


STRATEGIES['abrupt_song_end_no_fade'] = {
    'motif_choice': None,
    'motif_type': None,
    'transforms': [],
    'primitives': [],
    'humanization': {},
    'ending_directive': {'type': 'abrupt_cut', 'cut_position': 'last_beat'},
    'rationale': (
        'Ending directive: abrupt cut on the last beat of the final bar. Composer '
        'truncates all sustained notes (pad, sub) at the cut position.'
    ),
}


# ============================================================================
# API
# ============================================================================

def strategy_for_recipe(recipe_id: str) -> Optional[Dict[str, Any]]:
    """Get the deployment strategy for an advisor recipe.

    Returns None if no hand-crafted strategy exists for this recipe.
    Caller can fall back to motif_for_recipe() for raw motif candidates.
    """
    return STRATEGIES.get(recipe_id)


def list_strategies() -> List[str]:
    """All recipe IDs with hand-crafted strategies."""
    return sorted(STRATEGIES.keys())


def strategies_by_category() -> Dict[str, List[str]]:
    """Group strategies by their primary directive type."""
    out = {
        'motif_based': [],         # has motif_choice
        'section_directive': [],   # has section_directives
        'tempo_directive': [],     # has tempo_directive
        'form_directive': [],      # has form_directive
        'ending_directive': [],    # has ending_directive
    }
    for r, s in STRATEGIES.items():
        if s.get('motif_choice'):
            out['motif_based'].append(r)
        if 'section_directives' in s:
            out['section_directive'].append(r)
        if 'tempo_directive' in s:
            out['tempo_directive'].append(r)
        if 'form_directive' in s:
            out['form_directive'].append(r)
        if 'ending_directive' in s:
            out['ending_directive'].append(r)
    for k in out:
        out[k].sort()
    return out


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    print(f'=== Recipe → strategy mappings: {len(STRATEGIES)} ===')

    cats = strategies_by_category()
    for cat, recipes in cats.items():
        print(f'\n  {cat}: {len(recipes)}')
        for r in recipes:
            print(f'    - {r}')

    print('\n=== Sample strategy: descending_riff_as_song_identity ===')
    s = strategy_for_recipe('descending_riff_as_song_identity')
    import json
    print(json.dumps(s, indent=2, default=str))

    print('\n=== Sample strategy: hard_soft_hard_contrast_within_song ===')
    s = strategy_for_recipe('hard_soft_hard_contrast_within_song')
    print(json.dumps(s, indent=2, default=str))
