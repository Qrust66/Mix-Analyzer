"""Rhythmic motif library — Phase 1b of composition_engine.

Each motif is a SINGLE-PITCH rhythmic pattern (kick / snare / hat / etc.)
designed to be COMBINED with other rhythmic motifs in Phase 3 (primitives).

Schema differs from melodic: no pitch_intervals (drum pitches are FIXED to
GM-909 mapping), but adds drum_pitch and micro_variation_rules for
robot_rock-style humanization.

Drum pitch reference (GM Drum Map / Live's default 909 Drum Rack):
    36 = KICK / Bass Drum 1
    38 = SNARE / Snare 1
    39 = CLAP / Hand Clap
    41 = TOM_LO / Low Floor Tom
    42 = HAT_CL / Closed Hi-Hat
    46 = HAT_OP / Open Hi-Hat
    49 = CRASH / Crash Cymbal 1
    50 = TOM_HI / High Tom
    51 = RIDE / Ride Cymbal 1
"""

from typing import List, Tuple, Dict, Any


# Drum pitch constants
KICK = 36
SNARE = 38
CLAP = 39
TOM_LO = 41
HAT_CL = 42
HAT_OP = 46
CRASH = 49
TOM_HI = 50
RIDE = 51


RHYTHMIC_MOTIFS: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# SYNCOPATED KICK — canonical pattern from advisor recipe
# ============================================================================

RHYTHMIC_MOTIFS['syncopated_kick_3_against_4'] = {
    'id': 'syncopated_kick_3_against_4',
    'sources': [
        ('NIN', 'March of the Pigs', 'Reznor-programmed drums avoiding 4-on-floor'),
        ('Aphex Twin', 'Amber-era kick programming', 'IDM rhythmic complexity within club tempo'),
        ('Theo Parrish', 'shuffled kick tradition', 'techno-with-shuffle deliberately not on the beat'),
    ],
    'advisor_recipes': [
        'syncopated_kick_creates_implied_meter_within_4_4',
        'programmed_drums_as_compositional_engine',
    ],
    # Documented pattern from advisor: kick at 1, 1.75, 2.5, 3.25 (1-indexed)
    # = 0-indexed beats {0.0, 0.75, 1.5, 2.25}
    # 4 hits per bar with gaps of 0.75 / 0.75 / 0.75 / 1.75 (loop wrap)
    # NONE on standard 4-on-floor positions or backbeat — implies 3-against-4 polyrhythm
    'drum_pitch': KICK,
    'rhythm_beats': [
        (0.0, 0.25),     # downbeat (the only "expected" hit)
        (0.75, 0.25),    # the "+a" of beat 1 (4th 16th)
        (1.5, 0.25),     # the "+" of beat 2 (6th 16th)
        (2.25, 0.25),    # the "e" of beat 3 (9th 16th)
    ],
    'velocity_contour': [120, 100, 105, 100],   # downbeat strongest, others equal-but-syncopated
    'character_tags': ['syncopated', 'polyrhythmic', '3_against_4', 'aggressive', 'industrial'],
    'duration_total_beats': 4.0,   # 1 bar
    'time_sig': (4, 4),
    'target_genres': ['industrial_techno', 'IDM', 'dark_electronic', 'EBM'],
    'micro_variation_rules': {
        # robot_rock principles applied to drums
        'timing_jitter_ms': (-15, 15),       # ±15ms timing nudge per hit per cycle
        'velocity_jitter': (-8, 8),          # ±8 velocity per hit per cycle
        'occasional_skip': {                 # every Nth cycle, skip a specific hit
            'every_n_cycles': 8,
            'skip_indices': [2],             # skip note 3 (beat 1.5) every 8 cycles
        },
        'occasional_double': {               # every Nth cycle, double a hit (16th-flam)
            'every_n_cycles': 4,
            'double_indices': [0],           # double the downbeat every 4 cycles
            'flam_offset_beats': 0.0625,     # 1/64th note flam
        },
    },
    'transformations_allowed': [
        'rhythmic_displace',   # shift entire pattern by N beats
        'augment_diminish',    # ×0.5 for 32nd-density, ×2 for half-tempo feel
        'fragment',
    ],
    'notes_on_use': (
        'AVOID combining with backbeat-snare on beats 2+4 (ruins the 3-against-4 illusion). '
        'Pair with snare on the OFFBEATS that don\'t collide: snare on 0.5 + 2.0 (the "and" of '
        '1 + downbeat of 3) or just on beat 3.0. For drum pattern: kick uses THIS motif, snare '
        'uses snare_offbeat_complement (Phase 1b-3), hats use 16th_micro_variation_pattern '
        '(Phase 1b-4). Apply micro_variation_rules every cycle for the breathing-not-mechanical '
        'feel that distinguishes Banger v3 from v2.'
    ),
}


# ============================================================================
# 4-ON-THE-FLOOR FAMILY — house/techno foundation
# ============================================================================

RHYTHMIC_MOTIFS['four_on_floor_house_pure'] = {
    'id': 'four_on_floor_house_pure',
    'sources': [
        ('Daft Punk', 'Around the World', 'TR-909 4-on-floor at 121 BPM as house foundation'),
        ('Daft Punk', 'Harder Better Faster Stronger', '4-on-floor anchor under vocoded lead'),
    ],
    'advisor_recipes': [
        'four_on_the_floor_120_bpm_house_foundation',
        'tr_909_drum_machine_as_compositional_instrument',
        'programmed_drums_as_compositional_engine',
    ],
    'drum_pitch': KICK,
    # Kick on every beat (1, 2, 3, 4) = beats {0, 1, 2, 3} 0-indexed
    'rhythm_beats': [(0.0, 0.25), (1.0, 0.25), (2.0, 0.25), (3.0, 0.25)],
    'velocity_contour': [120, 110, 115, 110],   # downbeat slightly stronger
    'character_tags': ['four_on_floor', 'house', 'techno', 'foundation', 'predictable'],
    'duration_total_beats': 4.0,
    'time_sig': (4, 4),
    'target_genres': ['filter_house', 'deep_house', 'techno', 'electronic_pop'],
    'micro_variation_rules': {
        'timing_jitter_ms': (-3, 3),         # tighter than syncopated — 4-on-floor wants precision
        'velocity_jitter': (-5, 5),
    },
    'transformations_allowed': ['rhythmic_displace', 'augment_diminish', 'fragment'],
    'notes_on_use': (
        'THE foundational house kick. Pair with offbeat hi-hat (beats 0.5/1.5/2.5/3.5) for '
        'classic house feel, OR with 16th-note hat micro-variations for tech-house. AVOID '
        'overlaying with syncopated_kick_3_against_4 (genre conflict). Strict 120-128 BPM '
        'for house/filter-house; can extend to 130-140 for techno.'
    ),
}


RHYTHMIC_MOTIFS['four_on_floor_with_offbeat_ghost'] = {
    'id': 'four_on_floor_with_offbeat_ghost',
    'sources': [
        ('Daft Punk', 'Around the World', 'four-on-floor + ghost kicks on the and-of-2 + and-of-4'),
        ('NIN', 'The Hand That Feeds', 'commercial-single 4-on-floor with extra dynamics'),
    ],
    'advisor_recipes': [
        'four_on_the_floor_120_bpm_house_foundation',
        'commercial_single_economy_three_minutes_thirty_one',
    ],
    'drum_pitch': KICK,
    # Main 4-on-floor + ghost kicks at 1.5 + 3.5 (the "and" of 2 + 4)
    'rhythm_beats': [
        (0.0, 0.25), (1.0, 0.25), (1.5, 0.25),    # downbeat + beat 2 + ghost
        (2.0, 0.25), (3.0, 0.25), (3.5, 0.25),    # beat 3 + beat 4 + ghost
    ],
    'velocity_contour': [120, 110, 65, 115, 110, 65],   # main 110-120, ghosts at 65 (much softer)
    'character_tags': ['four_on_floor', 'ghost_kick', 'house_advanced', 'syncopated_overlay'],
    'duration_total_beats': 4.0,
    'time_sig': (4, 4),
    'target_genres': ['filter_house', 'deep_house', 'electronic_pop'],
    'micro_variation_rules': {
        'timing_jitter_ms': (-3, 3),
        'velocity_jitter': (-5, 5),
        'occasional_skip': {
            'every_n_cycles': 4,
            'skip_indices': [2],     # skip the first ghost every 4th cycle for variation
        },
    },
    'transformations_allowed': ['rhythmic_displace', 'fragment'],
    'notes_on_use': (
        'House-music advanced kick. The ghosts at 65 velocity are FELT not heard — they add '
        'forward-propulsion without disrupting the 4-on-floor primary pulse. Strongest at '
        '120-128 BPM. The skip-rule on ghost #1 every 4 cycles introduces breathing variation.'
    ),
}


RHYTHMIC_MOTIFS['boom_bap_kick_groove'] = {
    'id': 'boom_bap_kick_groove',
    'sources': [
        ('Queens Of The Stone Age', 'First It Giveth', 'robot-rock groove with kick on 1 + offbeat-of-3'),
        ('Soundgarden', 'My Wave', '5/4 groove kick anchored on beats 1 + 4'),
        ('Trip-hop tradition', 'Massive Attack-adjacent', 'slow boom-bap groove'),
    ],
    'advisor_recipes': [
        'groove_over_complexity_compositional_priority',
        'robot_rock_hypnotic_repetitive_riff_with_micro_variations',
        'rhythmic_emphasis_over_harmonic_movement_industrial_lesson',
    ],
    'drum_pitch': KICK,
    # Boom-bap classic: kick on 1, kick on 2.5 (the "and" of 3 in 1-indexed = 2.5 in 0-indexed)
    # PLUS sparse 16th anticipations
    'rhythm_beats': [
        (0.0, 0.25),     # downbeat (boom)
        (2.5, 0.25),     # boom-bap second hit (2 boom-bap-style)
        (3.75, 0.125),   # 16th-anticipation back to next downbeat
    ],
    'velocity_contour': [125, 115, 70],   # primary boom strongest, anticipation ghost-soft
    'character_tags': ['boom_bap', 'groove', 'sparse', 'pocket', 'hip_hop_adjacent'],
    'duration_total_beats': 4.0,
    'time_sig': (4, 4),
    'target_genres': ['trip_hop', 'downtempo', 'neo_classical_electronic'],
    'micro_variation_rules': {
        'timing_jitter_ms': (-8, 8),    # looser than house — boom-bap WANTS swing feel
        'velocity_jitter': (-10, 10),
        'occasional_skip': {
            'every_n_cycles': 8,
            'skip_indices': [2],         # drop the anticipation every 8 cycles
        },
    },
    'transformations_allowed': ['rhythmic_displace', 'fragment', 'augment_diminish'],
    'notes_on_use': (
        'Best at 80-100 BPM (trip-hop / downtempo / neo-classical-electronic). The pocket is '
        'in the SPACE between kicks — do not fill it with extra hits. Pair with snare on '
        'beat 2 + 4 (backbeat) or with snare_with_ghost_notes for groove variety. The 16th '
        'anticipation at beat 3.75 is the "Cameron-Castillo" detail (pulled from QOTSA / '
        'session-drummer tradition).'
    ),
}


# ============================================================================
# Render API — turn a rhythmic motif into concrete MIDI notes
# ============================================================================

def render(motif: Dict[str, Any], start_beat: float = 0.0,
           pitch_override: int = None, velocity_scale: float = 1.0,
           apply_micro_variations: bool = False, cycle_index: int = 0,
           rng_seed: int = None) -> List[Dict[str, Any]]:
    """Render a rhythmic motif into a list of concrete MIDI notes.

    Args:
        motif: a dict from RHYTHMIC_MOTIFS
        start_beat: where in the song this motif starts
        pitch_override: if given, use this pitch instead of motif['drum_pitch']
        velocity_scale: multiply velocities by this (clamped 1-127)
        apply_micro_variations: enable robot_rock-style humanization
        cycle_index: which loop cycle this is (for occasional_skip / occasional_double rules)
        rng_seed: random seed for reproducible humanization

    Returns:
        List of {'time', 'duration', 'velocity', 'pitch'} dicts.
    """
    import random
    rng = random.Random(rng_seed if rng_seed is not None else (cycle_index * 7919 + 17))

    pitch = pitch_override if pitch_override is not None else motif['drum_pitch']
    notes = []

    skip_indices = set()
    double_indices = set()
    if apply_micro_variations and 'micro_variation_rules' in motif:
        rules = motif['micro_variation_rules']
        if 'occasional_skip' in rules:
            os_rule = rules['occasional_skip']
            if cycle_index % os_rule['every_n_cycles'] == os_rule['every_n_cycles'] - 1:
                skip_indices = set(os_rule['skip_indices'])
        if 'occasional_double' in rules:
            od_rule = rules['occasional_double']
            if cycle_index % od_rule['every_n_cycles'] == od_rule['every_n_cycles'] - 1:
                double_indices = set(od_rule['double_indices'])

    for i, (rel_start, dur) in enumerate(motif['rhythm_beats']):
        if i in skip_indices:
            continue
        vel = motif['velocity_contour'][i]
        time = start_beat + rel_start

        if apply_micro_variations and 'micro_variation_rules' in motif:
            rules = motif['micro_variation_rules']
            if 'timing_jitter_ms' in rules:
                lo_ms, hi_ms = rules['timing_jitter_ms']
                # Convert ms to beats at assumed 120 BPM (caller can override; just an offset)
                # 120 BPM → 1 beat = 500ms → 1ms = 0.002 beats
                jitter_beats = rng.uniform(lo_ms, hi_ms) * 0.002
                time += jitter_beats
            if 'velocity_jitter' in rules:
                lo_v, hi_v = rules['velocity_jitter']
                vel += rng.randint(lo_v, hi_v)

        notes.append({
            'time': float(time),
            'duration': float(dur),
            'velocity': max(1, min(127, int(vel * velocity_scale))),
            'pitch': int(pitch),
        })

        if i in double_indices:
            flam_offset = motif['micro_variation_rules']['occasional_double']['flam_offset_beats']
            notes.append({
                'time': float(time + flam_offset),
                'duration': float(dur),
                'velocity': max(1, min(127, int(vel * velocity_scale * 0.6))),
                'pitch': int(pitch),
            })

    return notes


def list_motifs(filter_tags: List[str] = None,
                filter_recipes: List[str] = None,
                filter_drum_pitch: int = None) -> List[str]:
    """List rhythmic motif IDs matching given filters."""
    out = []
    for mid, m in RHYTHMIC_MOTIFS.items():
        if filter_tags and not any(t in m['character_tags'] for t in filter_tags):
            continue
        if filter_recipes and not any(r in m['advisor_recipes'] for r in filter_recipes):
            continue
        if filter_drum_pitch is not None and m.get('drum_pitch') != filter_drum_pitch:
            continue
        out.append(mid)
    return out


# Self-test
if __name__ == '__main__':
    print(f'Rhythmic motifs: {len(RHYTHMIC_MOTIFS)}')
    for mid, m in RHYTHMIC_MOTIFS.items():
        print(f'\n=== {mid} ===')
        print(f'  Drum pitch: {m["drum_pitch"]}')
        print(f'  Time sig: {m["time_sig"]}')
        print(f'  Tags: {m["character_tags"]}')

    # Demo: 3 cycles of syncopated_kick with micro-variations
    print('\n=== syncopated_kick_3_against_4 (3 cycles, micro-variations on) ===')
    for cyc in range(3):
        notes = render(RHYTHMIC_MOTIFS['syncopated_kick_3_against_4'],
                       start_beat=cyc * 4.0,
                       apply_micro_variations=True,
                       cycle_index=cyc, rng_seed=cyc)
        print(f'Cycle {cyc} ({len(notes)} hits):')
        for n in notes:
            print(f'  pitch={n["pitch"]}  time={n["time"]:.4f}  vel={n["velocity"]}')

    print('\n=== syncopated_kick_3_against_4 cycle 7 (skip-rule kicks in) ===')
    notes = render(RHYTHMIC_MOTIFS['syncopated_kick_3_against_4'],
                   start_beat=28.0, apply_micro_variations=True,
                   cycle_index=7, rng_seed=7)
    print(f'Cycle 7 ({len(notes)} hits, expecting skip of beat-1.5 kick):')
    for n in notes:
        print(f'  pitch={n["pitch"]}  time={n["time"]:.4f}  vel={n["velocity"]}')
