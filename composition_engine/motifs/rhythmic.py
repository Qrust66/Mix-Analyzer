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
# SNARE FAMILY — backbeat, ghost-notes, fills
# ============================================================================

RHYTHMIC_MOTIFS['snare_backbeat_pure'] = {
    'id': 'snare_backbeat_pure',
    'sources': [
        ('Nirvana', 'All Apologies', 'classic backbeat snare'),
        ('Soundgarden', 'Jesus Christ Pose', 'aggressive backbeat anchor'),
        ('Daft Punk', 'Around the World', 'house tradition backbeat'),
        ('Smashing Pumpkins', 'Soma', 'rock anthem backbeat foundation'),
    ],
    'advisor_recipes': [
        'programmed_drums_as_compositional_engine',
        'tr_909_drum_machine_as_compositional_instrument',
    ],
    'drum_pitch': SNARE,
    'rhythm_beats': [(1.0, 0.25), (3.0, 0.25)],
    'velocity_contour': [115, 118],
    'character_tags': ['backbeat', 'rock', 'foundation', 'predictable', 'anchor'],
    'duration_total_beats': 4.0,
    'time_sig': (4, 4),
    'target_genres': ['techno', 'electronic_pop', 'trip_hop', 'neo_classical_electronic'],
    'micro_variation_rules': {
        'timing_jitter_ms': (-5, 5),
        'velocity_jitter': (-7, 7),
    },
    'transformations_allowed': ['rhythmic_displace', 'fragment'],
    'notes_on_use': (
        'Most universal snare pattern. AVOID with syncopated_kick_3_against_4 (collides at '
        'beat 1.5/2.25 pattern, kills polyrhythmic illusion). Use snare_offbeat_complement '
        'instead in that case.'
    ),
}


RHYTHMIC_MOTIFS['snare_with_ghost_notes_groove'] = {
    'id': 'snare_with_ghost_notes_groove',
    'sources': [
        ('Queens Of The Stone Age', 'A Song for the Dead', 'Grohl drum-clinic ghost-note groove'),
        ('Soundgarden', 'My Wave', 'Cameron pocket-drumming with ghost-notes'),
        ('Trip-hop tradition', 'Massive Attack drummer Damon Reece', 'live-feel ghost-notes for atmospheric groove'),
    ],
    'advisor_recipes': [
        'drum_clinic_quality_drumming_within_song_context',
        'groove_over_complexity_compositional_priority',
        'compositional_drum_feature_within_heavy_rock_arc',
    ],
    'drum_pitch': SNARE,
    # Backbeat (beat 2 + 4) PLUS ghost-notes at "e"+"a" of beat 3 (16ths #9 + #11)
    'rhythm_beats': [
        (1.0, 0.25),       # primary backbeat
        (2.25, 0.0625),    # ghost on the "e" of beat 3
        (2.75, 0.0625),    # ghost on the "a" of beat 3
        (3.0, 0.25),       # primary backbeat
    ],
    'velocity_contour': [115, 45, 50, 118],   # primaries strong, ghosts felt-not-heard
    'character_tags': ['backbeat', 'ghost_notes', 'pocket', 'live_feel', 'session_drummer_quality'],
    'duration_total_beats': 4.0,
    'time_sig': (4, 4),
    'target_genres': ['trip_hop', 'downtempo', 'neo_classical_electronic', 'electronic_pop'],
    'micro_variation_rules': {
        'timing_jitter_ms': (-12, 12),
        'velocity_jitter': (-8, 8),
        'occasional_skip': {
            'every_n_cycles': 4,
            'skip_indices': [1],
        },
    },
    'transformations_allowed': ['rhythmic_displace', 'fragment'],
    'notes_on_use': (
        'Ghost-notes at velocity 45-50 = the live-drummer signature. Best at 80-110 BPM. '
        'Pair with boom_bap_kick_groove for full Massive Attack / QOTSA "Songs for the Deaf" '
        'pocket. Skip-rule on ghost #1 every 4 cycles for breathing.'
    ),
}


RHYTHMIC_MOTIFS['snare_16th_roll_fill'] = {
    'id': 'snare_16th_roll_fill',
    'sources': [
        ('Smashing Pumpkins', 'Soma', '16th snare-fill into explosion chorus'),
        ('Soundgarden', 'Jesus Christ Pose', 'aggressive snare-roll transition'),
        ('NIN', "We're In This Together", 'dynamic-arc snare-roll into final chorus'),
    ],
    'advisor_recipes': [
        'density_arc_arrangement_sparse_to_wall',
        'explosion_chorus_as_cathartic_release_not_just_loud_section',
        'extensive_section_specific_mix_automation_for_character_shifts',
    ],
    'drum_pitch': SNARE,
    # 16th-note roll on beats 3+4 — crescendo into next-bar downbeat
    'rhythm_beats': [(2.0 + i * 0.25, 0.125) for i in range(8)],
    'velocity_contour': [80, 85, 90, 95, 100, 110, 120, 125],
    'character_tags': ['fill', 'transition', 'roll', 'crescendo', 'sectional'],
    'duration_total_beats': 4.0,
    'time_sig': (4, 4),
    'target_genres': ['techno', 'electronic_pop', 'dark_electronic'],
    'micro_variation_rules': {
        'timing_jitter_ms': (-2, 2),
        'velocity_jitter': (-3, 3),
    },
    'transformations_allowed': [
        'rhythmic_displace', 'augment_diminish', 'fragment',
    ],
    'notes_on_use': (
        'TRANSITION TOOL — deploy at END of 4/8/16-bar phrase to lift listener into next '
        'section. Do NOT use mid-pattern. Last hit (vel 125) at beat 3.75 lands on next-bar '
        'kick downbeat. For 32nd-note version: augment_diminish ×0.5 (16 hits in 2 beats).'
    ),
}


# ============================================================================
# HAT FAMILY — 8th-accent, 16th micro-variation, 32nd-mania
# ============================================================================

RHYTHMIC_MOTIFS['hat_8th_accent_house'] = {
    'id': 'hat_8th_accent_house',
    'sources': [
        ('Daft Punk', 'Around the World', 'closed-hat 8ths with downbeat accent'),
        ('Daft Punk', 'Harder Better Faster Stronger', 'house-tradition 8th-note hat groove'),
        ('Soundgarden', 'Fell On Black Days', 'rock 8th-note hi-hat anchor'),
    ],
    'advisor_recipes': [
        'four_on_the_floor_120_bpm_house_foundation',
        'tr_909_drum_machine_as_compositional_instrument',
        'programmed_drums_as_compositional_engine',
    ],
    'drum_pitch': HAT_CL,
    # 8 hats per bar at 8th-note positions {0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5}
    # Velocity accent: downbeat strongest, "and"-positions weakest, beats 2/3/4 medium
    'rhythm_beats': [(i * 0.5, 0.125) for i in range(8)],
    'velocity_contour': [108, 64, 80, 64, 80, 64, 80, 64],   # accent on each beat (positions 0, 2, 4, 6)
    'character_tags': ['8th_notes', 'house_groove', 'predictable', 'foundation', 'closed_hat'],
    'duration_total_beats': 4.0,
    'time_sig': (4, 4),
    'target_genres': ['filter_house', 'deep_house', 'techno', 'electronic_pop'],
    'micro_variation_rules': {
        'timing_jitter_ms': (-4, 4),
        'velocity_jitter': (-6, 6),
    },
    'transformations_allowed': ['rhythmic_displace', 'augment_diminish', 'fragment'],
    'notes_on_use': (
        'Most universal hat pattern. Pair with four_on_floor_house_pure for classic house, '
        'or with snare_backbeat_pure for rock-electronic. The downbeat-accent (108 vs 64) '
        'creates the "swing" feel even at perfect timing. For OPEN-hat variation: replace '
        'every 4th note (positions 1, 3, 5, 7 = "and" positions) with HAT_OP at vel 90.'
    ),
}


RHYTHMIC_MOTIFS['hat_16th_micro_variation_robot_rock'] = {
    'id': 'hat_16th_micro_variation_robot_rock',
    'sources': [
        ('Queens Of The Stone Age', 'First It Giveth', 'robot-rock 16th hat with documented micro-variations'),
        ('Daft Punk', 'Around the World', 'tight 16th-note hat groove'),
        ('NIN', 'The Hand That Feeds', '16th hat under industrial-rock kit'),
    ],
    'advisor_recipes': [
        'robot_rock_hypnotic_repetitive_riff_with_micro_variations',
        'tr_909_drum_machine_as_compositional_instrument',
        'tighter_layering_for_rhythmic_clarity_genre_blend',
    ],
    'drum_pitch': HAT_CL,
    # 16 hats per bar at 16th-note positions
    'rhythm_beats': [(i * 0.25, 0.0625) for i in range(16)],
    # Velocity accent on beats 1+3, secondary on 2+4, weakest on "e"+"a"
    # Pattern: STRONG e a + STRONG e a + STRONG e a + STRONG e a
    'velocity_contour': [
        108, 60, 70, 60,    # beat 1 + 16ths 2-4
        90, 60, 70, 60,     # beat 2 + 16ths 6-8
        100, 60, 70, 60,    # beat 3 + 16ths 10-12
        90, 60, 70, 60,     # beat 4 + 16ths 14-16
    ],
    'character_tags': ['16th_notes', 'robot_rock', 'micro_variation', 'tight', 'foundation'],
    'duration_total_beats': 4.0,
    'time_sig': (4, 4),
    'target_genres': ['techno', 'dark_electronic', 'EBM', 'IDM'],
    'micro_variation_rules': {
        'timing_jitter_ms': (-3, 3),     # tighter than 8th-note hats — robot_rock precision
        'velocity_jitter': (-10, 10),    # MORE velocity humanization — that's where the "breathing" lives
        'occasional_skip': {
            'every_n_cycles': 4,
            'skip_indices': [3, 7],     # drop 16ths #4 and #8 every 4 cycles for syncopation surprise
        },
    },
    'transformations_allowed': ['rhythmic_displace', 'fragment'],
    'notes_on_use': (
        'CORE robot_rock hat pattern. The big-velocity-jitter (±10) is the secret: tight '
        'timing + breathing velocity = "groove that feels human even though it is programmed". '
        'Every 4 cycles, two 16ths drop out (positions 3 + 7) — creates rhythmic surprise '
        'without breaking the foundation. Pair with syncopated_kick_3_against_4 OR '
        'four_on_floor_house_pure (both work).'
    ),
}


RHYTHMIC_MOTIFS['hat_32nd_mania_drop'] = {
    'id': 'hat_32nd_mania_drop',
    'sources': [
        ('NIN', 'March of the Pigs', 'dense hi-hat at extreme tempo'),
        ('Soundgarden', 'Jesus Christ Pose', 'aggressive hat density at peak intensity'),
        ('Daft Punk', 'Harder Better Faster Stronger', 'peak-section dense hat for energy lift'),
    ],
    'advisor_recipes': [
        'unrelenting_aggression_no_dynamic_arc',
        'density_arc_arrangement_sparse_to_wall',
        'fast_tempo_148_156_bpm_aggressive_heavy_rock',
    ],
    'drum_pitch': HAT_CL,
    # 32 hats per bar at 32nd-note positions
    'rhythm_beats': [(i * 0.125, 0.0625) for i in range(32)],
    # Velocity: pulsing accent on each 8th-note position (every 4th 32nd) for grouping
    # Pattern: pulse the 8ths via accents
    'velocity_contour': [
        # Beat 1: STRONG soft soft soft, MEDIUM soft soft soft (8th-pulse subdivision)
        115, 50, 60, 50,  85, 55, 60, 50,
        # Beat 2:
        100, 55, 60, 50,  85, 55, 60, 50,
        # Beat 3:
        110, 55, 60, 50,  85, 55, 60, 50,
        # Beat 4:
        100, 55, 60, 50,  85, 55, 60, 50,
    ],
    'character_tags': ['32nd_notes', 'mania', 'peak_density', 'drop_only', 'aggressive'],
    'duration_total_beats': 4.0,
    'time_sig': (4, 4),
    'target_genres': ['dark_electronic', 'EBM', 'techno', 'IDM'],
    'micro_variation_rules': {
        'timing_jitter_ms': (-2, 2),    # very tight — at 32nd-density jitter becomes blur
        'velocity_jitter': (-8, 8),
    },
    'transformations_allowed': ['fragment', 'augment_diminish'],
    'notes_on_use': (
        'DROP-ONLY pattern — deploy ONLY in peak 4-8 bars. Using this for verse-density '
        'destroys the dynamic arc. Pair with kick (any of the kick patterns) and '
        'snare_backbeat OR snare_with_ghost. The 8th-pulse velocity accent (115/100/110/100 '
        'on beats 1-4) keeps the 32nds from sounding like white noise. At >150 BPM it becomes '
        'cymbal-roll territory; at <130 BPM it sounds gabber-cliche — sweet spot 130-150 BPM.'
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
