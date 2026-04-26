"""Harmonic progression library — Phase 1c of composition_engine.

A progression is a SEQUENCE OF CHORDS, each with root + voicing + duration.
All pitches are RELATIVE to a tonal center (tonic), so the progression can be
transposed to any key with a single parameter.

Schema:
    {
        'id': str,
        'sources': List[(artist, song, what)],
        'advisor_recipes': List[str],
        'mode': str,                 # 'aeolian' / 'phrygian' / 'dorian' / 'major' / etc.
        'chords': List[{
            'root_interval': int,    # semitones from tonic (0 = tonic, 5 = IV, 7 = V, 8 = ♭VI, 10 = ♭VII)
            'voicing': str,           # one of VOICINGS dict below
            'duration_beats': float,
            'roman': str,             # 'i', 'VI', 'VII', 'iv', etc. (lower = minor, upper = major)
            'inversion': int,         # 0 = root position, 1 = 1st inversion (3rd in bass), 2 = 2nd inv
        }],
        'duration_total_beats': float,
        'time_sig': Tuple[int, int],
        'character_tags': List[str],
        'transformations_allowed': List[str],
        'notes_on_use': str,
    }

Voicing dict: maps voicing-name -> list of interval offsets (semitones from chord root).
"""

from typing import List, Dict, Any, Tuple


VOICINGS: Dict[str, List[int]] = {
    # Triads
    'maj_triad': [0, 4, 7],            # major: root + maj3 + 5
    'min_triad': [0, 3, 7],            # minor: root + min3 + 5
    'dim_triad': [0, 3, 6],            # diminished: root + min3 + ♭5
    'aug_triad': [0, 4, 8],            # augmented: root + maj3 + #5

    # Power chords (no 3rd)
    'power': [0, 7],                   # root + 5
    'power_oct': [0, 7, 12],           # root + 5 + octave

    # Sus / quartal / quintal voicings
    'sus2': [0, 2, 7],                 # root + 2 + 5
    'sus4': [0, 5, 7],                 # root + 4 + 5
    'quartal': [0, 5, 10],             # stacked 4ths (root, 4th, ♭7) — contemporary jazz
    'quintal': [0, 7, 14],             # stacked 5ths (root, 5, 9 — open + ambiguous)

    # 7th chords
    'maj7': [0, 4, 7, 11],
    'min7': [0, 3, 7, 10],
    'dom7': [0, 4, 7, 10],
    'min_maj7': [0, 3, 7, 11],         # minor with major 7 (Hitchcock/dark color)
    'm7b5': [0, 3, 6, 10],             # half-diminished
    'dim7': [0, 3, 6, 9],              # fully diminished

    # Modal/extended
    'sus_4_with_9': [0, 2, 5, 7],      # sus4 with added 9 (modal openness, Eno tradition)
    'min_add9': [0, 3, 7, 14],         # minor + 9 (lush)
    'maj_add9': [0, 4, 7, 14],         # major + 9
    'maj9': [0, 4, 7, 11, 14],         # full maj9 (Veridis Quo / classical-electronic)
}


HARMONIC_PROGRESSIONS: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# AEOLIAN PROGRESSIONS — minor-key foundational
# ============================================================================

HARMONIC_PROGRESSIONS['aeolian_i_VI_VII_i'] = {
    'id': 'aeolian_i_VI_VII_i',
    'sources': [
        ('Nirvana', 'Dumb', 'Aeolian-rooted verse-chorus pad foundation'),
        ('Soundgarden', 'Head Down', 'modal voicings above drone — i-VI-VII-i family'),
        ('NIN', 'The Day The World Went Away', 'sustained Aeolian pad foundation'),
        ('Radiohead', 'Everything In Its Right Place', 'modal-Aeolian color palette'),
    ],
    'advisor_recipes': [
        'modal_voicings_above_drone_replace_chord_progression',
        'drone_foundation_as_compositional_anchor',
        'atmospheric_sustain_as_compositional_foundation',
        'sus_voicings_verse_with_drop_tuning_pedal',
    ],
    'mode': 'aeolian',
    # Dm – Bb – C – Dm (i – ♭VI – ♭VII – i)
    # Root intervals from D tonic: 0, 8, 10, 0
    # Major triads on ♭VI and ♭VII (Bb major, C major), minor triad on i (Dm)
    'chords': [
        {'root_interval': 0,  'voicing': 'min_triad', 'duration_beats': 4.0, 'roman': 'i',  'inversion': 0},
        {'root_interval': 8,  'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': 'VI', 'inversion': 0},
        {'root_interval': 10, 'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': 'VII','inversion': 0},
        {'root_interval': 0,  'voicing': 'min_triad', 'duration_beats': 4.0, 'roman': 'i',  'inversion': 0},
    ],
    'duration_total_beats': 16.0,   # 4 bars in 4/4
    'time_sig': (4, 4),
    'character_tags': ['aeolian', 'minor_modal', 'foundational', 'dark', 'cinematic', 'rock_modal'],
    'transformations_allowed': [
        'transpose',
        'voicing_swap',          # swap min_triad → sus2/sus4/min7 for color variation
        'inversion_swap',        # change inversions for voice-leading variation
        'augment_diminish',      # ×0.5 = 8-beat version, ×2 = 32-beat version
        'fragment',              # take 2-chord sub-sequence
    ],
    'notes_on_use': (
        'THE foundational minor-modal progression. Voice on Diva pad with slow attack '
        '(200-500ms) and long release (3-5sec) so chords BLEND. Pair with sustained tonic '
        'drone in sub-bass underneath (D1 if rendered in Dm). Each chord 4 beats = 1 bar '
        'in 4/4 — slow enough that voice-leading is audible. For voice-leading variation: '
        'use sus2 voicing on i (D-E-A) instead of triad — adds modal openness. Retrograde '
        'the progression once mid-track for harmonic surprise.'
    ),
}


HARMONIC_PROGRESSIONS['phrygian_dark_descending'] = {
    'id': 'phrygian_dark_descending',
    'sources': [
        ('Radiohead', 'Pyramid Song', 'piano chromatic chords inspired by Mingus Freedom'),
        ('NIN', 'The Wretched', 'Phrygian-adjacent chromatic motion in atmospheric verses'),
        ('Soundgarden', 'Head Down', 'modal voicings exploring dark color above drone'),
    ],
    'advisor_recipes': [
        'mingus_freedom_chromatic_harmony_inspiration',
        'modal_voicings_above_drone_replace_chord_progression',
        'piano_composition_with_chromatic_harmony',
    ],
    'mode': 'phrygian',
    # D Phrygian: ♭2 is the defining color (D-Eb-F-G-A-Bb-C)
    # Progression: i → ♭II → ♭VII → i (Dm – Eb – C – Dm)
    # The ♭II (Eb major) on top of D Phrygian is the dark/exotic flavor
    'chords': [
        {'root_interval': 0,  'voicing': 'min_triad', 'duration_beats': 4.0, 'roman': 'i',  'inversion': 0},
        {'root_interval': 1,  'voicing': 'maj_triad', 'duration_beats': 2.0, 'roman': '♭II','inversion': 0},
        {'root_interval': 10, 'voicing': 'maj_triad', 'duration_beats': 2.0, 'roman': '♭VII','inversion': 0},
        {'root_interval': 0,  'voicing': 'min_add9',  'duration_beats': 8.0, 'roman': 'i',  'inversion': 0},
    ],
    'duration_total_beats': 16.0,
    'time_sig': (4, 4),
    'character_tags': ['phrygian', 'dark', 'chromatic', 'exotic', 'tension_resolution', 'modal_color'],
    'transformations_allowed': [
        'transpose', 'voicing_swap', 'inversion_swap', 'augment_diminish',
    ],
    'notes_on_use': (
        'The ♭II (Eb major in Dm Phrygian) is the SOUL of this progression — leaning into '
        'it for 2 beats then releasing creates the Phrygian "sigh". The final chord uses '
        'min_add9 (Dm + E natural) for unresolved hovering color — pairs with sustained '
        'lead-line on the tonic above. Use sparingly (once per breakdown / transition '
        'section) — overuse desensitizes the ♭II color.'
    ),
}


HARMONIC_PROGRESSIONS['dorian_sus_floating'] = {
    'id': 'dorian_sus_floating',
    'sources': [
        ('Radiohead', 'Everything In Its Right Place', 'modal floating arpeggio above sustained pad'),
        ('Daft Punk', 'Veridis Quo', 'sus voicings creating floating harmonic ambiguity'),
        ('Soundgarden', 'Fell On Black Days', 'sus2/sus4 voicings before resolution'),
    ],
    'advisor_recipes': [
        'sus_voicings_verse_with_drop_tuning_pedal',
        'modal_voicings_above_drone_replace_chord_progression',
        'voice_leading_clarity_via_synth_pad_layers',
    ],
    'mode': 'dorian',
    # D Dorian: D-E-F-G-A-B-C — the natural 6 (B) distinguishes from Aeolian
    # Progression: i_sus2 → IV → ii → i_sus4 (Dm9-G-Em-Dsus4)
    # Sus voicings + IV major (G major in D Dorian) gives the floating-bright Dorian feel
    'chords': [
        {'root_interval': 0, 'voicing': 'sus2',     'duration_beats': 4.0, 'roman': 'i^sus2', 'inversion': 0},
        {'root_interval': 5, 'voicing': 'maj_triad','duration_beats': 4.0, 'roman': 'IV',     'inversion': 0},
        {'root_interval': 2, 'voicing': 'min_triad','duration_beats': 4.0, 'roman': 'ii',     'inversion': 0},
        {'root_interval': 0, 'voicing': 'sus4',     'duration_beats': 4.0, 'roman': 'i^sus4', 'inversion': 0},
    ],
    'duration_total_beats': 16.0,
    'time_sig': (4, 4),
    'character_tags': ['dorian', 'sus', 'floating', 'ambiguous', 'modal_bright'],
    'transformations_allowed': [
        'transpose', 'voicing_swap', 'inversion_swap', 'augment_diminish',
    ],
    'notes_on_use': (
        'The IV major (G in D Dorian) is what distinguishes Dorian from Aeolian — without '
        'it, this is just minor. Progression starts and ends on sus voicings (no 3rd) so '
        'tonic identity stays AMBIGUOUS — listener feels modal-floating, not minor-rooted. '
        'Pair with sustained drone on tonic D underneath (any of the rhythmic motifs in low '
        'register). At slow tempo (60-90 BPM) this becomes Eno-tradition ambient; at house '
        'tempo (120-128) becomes filter-house-ambiguous.'
    ),
}


HARMONIC_PROGRESSIONS['lydian_brightness_color'] = {
    'id': 'lydian_brightness_color',
    'sources': [
        ('Daft Punk', 'Veridis Quo', 'classical-influenced lifts via #4 / Lydian color'),
        ('Smashing Pumpkins', 'Soma', 'pre-explosion harmonic lift toward bright color'),
        ('Radiohead', 'Optimistic', 'rock-anchor with bright modal color'),
    ],
    'advisor_recipes': [
        'classical_influenced_chord_progression_in_electronic_context',
        'voice_leading_clarity_via_synth_pad_layers',
        'pre_chorus_ascending_arc_compositional_pairing',
    ],
    'mode': 'lydian',
    # D Lydian: D-E-F#-G#-A-B-C# — the #4 (G#) is the defining color
    # Progression: I → II → I_maj7 → V (D-E-Dmaj7-A) — using II major for the Lydian #4 hint
    # In D Lydian: II = E major (with the F# raised to G# as Lydian #4 in melody)
    'chords': [
        {'root_interval': 0, 'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': 'I',     'inversion': 0},
        {'root_interval': 2, 'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': 'II',    'inversion': 0},
        {'root_interval': 0, 'voicing': 'maj7',      'duration_beats': 4.0, 'roman': 'I^maj7','inversion': 0},
        {'root_interval': 7, 'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': 'V',     'inversion': 0},
    ],
    'duration_total_beats': 16.0,
    'time_sig': (4, 4),
    'character_tags': ['lydian', 'bright', 'lifting', 'classical_color', 'major_modal'],
    'transformations_allowed': [
        'transpose', 'voicing_swap', 'inversion_swap', 'augment_diminish',
    ],
    'notes_on_use': (
        'Use SPARINGLY — Lydian color is potent and overused becomes new-age cliché. The '
        'II major (E in D Lydian) is the surprise: in any major key II would be minor; '
        'making it MAJOR signals Lydian. The maj7 voicing on I in chord 3 emphasizes the '
        'major-modal lift. Pairs with pre_chorus_ascending_arc melodic motif (Phase 1a). '
        'Best at moderate tempo (80-110 BPM) where the lift is felt; at fast tempo it '
        'becomes wallpaper.'
    ),
}


# ============================================================================
# CLASSICAL-INFLUENCED PROGRESSIONS — descending bass, voice-leading, chromatic
# ============================================================================

HARMONIC_PROGRESSIONS['pachelbel_descending_bass_8'] = {
    'id': 'pachelbel_descending_bass_8',
    'sources': [
        ('Daft Punk', 'Veridis Quo', 'Pachelbel-adjacent classical-electronic descending bass anchor'),
        ('Smashing Pumpkins', 'Soma', 'extended pre-explosion descent with Pachelbel-tradition voice-leading'),
        ('Radiohead', 'Optimistic', 'rock-format with classical-influenced descending bass-line'),
    ],
    'advisor_recipes': [
        'classical_influenced_chord_progression_in_electronic_context',
        'classical_electronic_crossover_via_duo_auteur_framework',
        'voice_leading_clarity_via_synth_pad_layers',
        'bass_line_first_compositional_method',
    ],
    'mode': 'minor_or_major_dual',   # Pachelbel works in both; we render in D minor here
    # In D minor: Dm – A – Bb – F – Gm – Dm – Gm – A
    # Bass-line: D - A - Bb - F - G - D - G - A (descending then ascending steps)
    # Root intervals: 0, 7, 8, 5, 5(but minor), 0, 5(min), 7
    # Wait: rethink as D minor key:
    # D(i) - A(v in Dm) - Bb(♭VI) - F(♭III) - Gm(iv) - D(i) - Gm(iv) - A(V or v)
    # Root intervals: 0, 7, 8, 3, 5, 0, 5, 7
    'chords': [
        {'root_interval': 0, 'voicing': 'min_triad', 'duration_beats': 2.0, 'roman': 'i',  'inversion': 0},
        {'root_interval': 7, 'voicing': 'maj_triad', 'duration_beats': 2.0, 'roman': 'V',  'inversion': 0},
        {'root_interval': 8, 'voicing': 'maj_triad', 'duration_beats': 2.0, 'roman': '♭VI','inversion': 0},
        {'root_interval': 3, 'voicing': 'maj_triad', 'duration_beats': 2.0, 'roman': '♭III','inversion': 0},
        {'root_interval': 5, 'voicing': 'min_triad', 'duration_beats': 2.0, 'roman': 'iv', 'inversion': 0},
        {'root_interval': 0, 'voicing': 'min_triad', 'duration_beats': 2.0, 'roman': 'i',  'inversion': 0},
        {'root_interval': 5, 'voicing': 'min_triad', 'duration_beats': 2.0, 'roman': 'iv', 'inversion': 0},
        {'root_interval': 7, 'voicing': 'maj_triad', 'duration_beats': 2.0, 'roman': 'V',  'inversion': 0},
    ],
    'duration_total_beats': 16.0,   # 4 bars (2-beat chords × 8)
    'time_sig': (4, 4),
    'character_tags': ['classical_influenced', 'descending_bass', 'voice_leading', 'extended_form', 'cinematic'],
    'transformations_allowed': [
        'transpose', 'voicing_swap', 'inversion_swap',
        'augment_diminish',          # ×0.5 = 8-beat compressed, ×2 = 32-beat slow-cinematic
        # NOT retrograde — voice-leading direction matters
    ],
    'notes_on_use': (
        'Use as compositional FOUNDATION (bass_line_first_compositional_method). At 80-100 '
        'BPM feels classical/cinematic; at 120-128 feels filter-house-classical-crossover '
        '(Veridis Quo territory). Pair with melodic motif aeolian_descending_4_steps OR '
        'pachelbel_descending_bass_8_chord (the bass-line counterpart in Phase 1a). For '
        'inversion variation: alternate root and 1st-inversion chords for smoother voice-'
        'leading top-line — apply inversion_swap on chords 1, 3, 5, 7 (the V chords).'
    ),
}


HARMONIC_PROGRESSIONS['circle_of_fifths_4_chord'] = {
    'id': 'circle_of_fifths_4_chord',
    'sources': [
        ('Daft Punk', 'Harder Better Faster Stronger', 'pop-electronic with classical voice-leading'),
        ('Smashing Pumpkins', 'Soma', 'pre-chorus tension via dominant chain'),
        ('NIN', "We're In This Together", 'anthemic build with V-of-V tonal pull'),
    ],
    'advisor_recipes': [
        'classical_influenced_chord_progression_in_electronic_context',
        'pop_song_structure_within_electronic_vocabulary',
        'multiple_chorus_iterations_with_intensification',
    ],
    'mode': 'major',
    # Circle-of-fifths motion (each chord moves DOWN a fifth = up a fourth)
    # In D major: D - G - C - F - D (each chord 4 beats — dominant tension chain)
    # But we want a 4-chord LOOP, so: D → G → C → F (then loop back to D)
    # Root intervals from D: 0, 5, 10, 3 (each step is descending fifth = +5 semitones up an octave / -7 down)
    # Equivalently: 0, -7+12=5, -14+12=10? Let me recompute.
    # D = 0; descending fifth → G = -7+12 = 5 (or 7-12 = -5, same pitch class)
    # G to C = descending fifth → C = 5-7+12 = 10
    # C to F = descending fifth → F = 10-7+12 = 15-12 = 3
    'chords': [
        {'root_interval': 0,  'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': 'I',   'inversion': 0},
        {'root_interval': 5,  'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': 'IV',  'inversion': 0},
        {'root_interval': 10, 'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': '♭VII','inversion': 0},
        {'root_interval': 3,  'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': '♭III','inversion': 0},
    ],
    'duration_total_beats': 16.0,
    'time_sig': (4, 4),
    'character_tags': ['circle_of_fifths', 'classical_voice_leading', 'major_modal', 'cyclic'],
    'transformations_allowed': [
        'transpose', 'voicing_swap', 'augment_diminish',
        # NOT retrograde — fifths motion direction matters
    ],
    'notes_on_use': (
        'CYCLIC progression — each chord pulls toward the next via descending-fifth motion. '
        'Loops naturally (chord 4 pulls back to chord 1). Voice-leading is automatic in this '
        'motion: each chord shares 2 common tones with the next. Use as VERSE foundation '
        '(stays harmonically interesting without modulating). For pop-electronic: voice with '
        'sus_4_with_9 voicing on chords 1-2 (open + cyclic), revert to maj_triad on 3-4 for '
        'arrival.'
    ),
}


HARMONIC_PROGRESSIONS['chromatic_descending_bass_4'] = {
    'id': 'chromatic_descending_bass_4',
    'sources': [
        ('Radiohead', 'Pyramid Song', 'piano chord-roots descending chromatically'),
        ('NIN', 'The Wretched', 'chromatic-passing-tone in atmospheric verses'),
        ('Smashing Pumpkins', 'Soma', 'pre-explosion chromatic tension'),
        ('Daft Punk', 'Veridis Quo', 'classical-influenced chromatic passing'),
    ],
    'advisor_recipes': [
        'piano_composition_with_chromatic_harmony',
        'mingus_freedom_chromatic_harmony_inspiration',
        'classical_influenced_chord_progression_in_electronic_context',
    ],
    'mode': 'minor_chromatic',
    # Bass descends chromatically: D → C# → C → B (in Dm key)
    # Chord qualities chosen for maximum tension-resolution flavor:
    # Dm (i) → A/C# (1st inv V) → C maj (♭VII) → B dim (vii°)
    # Bass intervals from D tonic: 0, -1, -2, -3
    # Voicings reflect each chord's character
    'chords': [
        {'root_interval': 0,  'voicing': 'min_triad', 'duration_beats': 4.0, 'roman': 'i',     'inversion': 0},
        # A major chord with C# in bass = inversion 1 of V (V/i)
        {'root_interval': 7,  'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': 'V_inv', 'inversion': 1},
        # C major (♭VII)
        {'root_interval': 10, 'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': '♭VII',  'inversion': 0},
        # B diminished (vii°) — leading-tone tension before resolution
        {'root_interval': 9,  'voicing': 'dim_triad', 'duration_beats': 4.0, 'roman': 'vii°',  'inversion': 0},
    ],
    'duration_total_beats': 16.0,
    'time_sig': (4, 4),
    'character_tags': ['chromatic', 'descending', 'classical_voice_leading', 'tension', 'piano_tradition'],
    'transformations_allowed': [
        'transpose', 'voicing_swap', 'augment_diminish',
    ],
    'notes_on_use': (
        'The CHROMATIC BASS-LINE D-C#-C-B is the focal point — voice with explicit bass-line '
        'in low octave (sub-bass or piano left-hand). The vii° on chord 4 creates strong pull '
        'back to i (Dm) for next loop iteration — this is classical-tradition leading-tone '
        'resolution. At slow tempo (60-80 BPM) feels Mingus-Freedom-tradition (Yorke '
        'inspiration). At faster tempo the chromatic detail blurs. Pair with piano-Rhodes '
        'voicing on top + sub-bass D pedal underneath (drone foundation) — the descending '
        'CHROMATIC bass + sustained tonic drone creates the "two-bass-lines" tension that '
        'makes Pyramid Song work.'
    ),
}


# ============================================================================
# DANCE / ELECTRONIC PROGRESSIONS — chord-stab loops, static-with-shifts, stacked clusters
# ============================================================================

HARMONIC_PROGRESSIONS['filter_house_i_vi_IV_V_loop'] = {
    'id': 'filter_house_i_vi_IV_V_loop',
    'sources': [
        ('Daft Punk', 'Around the World', 'filter-house chord-stab loop with filter modulation'),
        ('Daft Punk', 'Harder Better Faster Stronger', 'pop-electronic with classical voice-leading'),
    ],
    'advisor_recipes': [
        'four_on_the_floor_120_bpm_house_foundation',
        'compositional_movement_via_filter_not_via_chord_change',
        'pop_song_structure_within_electronic_vocabulary',
        'filter_modulation_as_compositional_engine',
    ],
    'mode': 'minor',
    # Filter-house pop progression: i - ♭VI - IV - V → loop
    # In D minor: Dm - Bb - G - A (each chord 1 bar = 4 beats, full loop = 4 bars)
    # Voicings use power chord on i for tight energy, triads on chord-stabs
    'chords': [
        {'root_interval': 0, 'voicing': 'power_oct',  'duration_beats': 4.0, 'roman': 'i',  'inversion': 0},
        {'root_interval': 8, 'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': '♭VI','inversion': 0},
        {'root_interval': 5, 'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': 'IV', 'inversion': 0},
        {'root_interval': 7, 'voicing': 'maj_triad', 'duration_beats': 4.0, 'roman': 'V',  'inversion': 0},
    ],
    'duration_total_beats': 16.0,
    'time_sig': (4, 4),
    'character_tags': ['filter_house', 'dance', 'cyclic_loop', 'pop_electronic', 'chord_stabs'],
    'transformations_allowed': [
        'transpose', 'voicing_swap', 'augment_diminish',
        # NOT inversion (chord-stab loops want clean root-position attacks)
    ],
    'notes_on_use': (
        'CHORD-STAB loop — each chord rendered as a SHORT ATTACK rhythmic stab, NOT '
        'sustained pad. To deploy: render each chord but reduce the duration to 0.5 beats '
        '(8th-note stab) and place 8 stabs per bar (1 per 8th-note) for filter-house feel. '
        'PAIR WITH FILTER MODULATION: open the filter cutoff over the full 16-bar loop '
        '(advisor: filter_modulation_as_compositional_engine). The chords stay STATIC; the '
        'filter does the compositional movement. This is the Around-the-World template.'
    ),
}


HARMONIC_PROGRESSIONS['dub_techno_static_modal_shift'] = {
    'id': 'dub_techno_static_modal_shift',
    'sources': [
        ('Soundgarden', 'Head Down', '7/4 drone-foundation with modal voicings shifting subtly'),
        ('NIN', 'The Day The World Went Away', 'sustained modal pad with subtle internal shifts'),
        ('Radiohead', 'Pyramid Song', 'static harmonic anchor with modal color drifts'),
    ],
    'advisor_recipes': [
        'drone_foundation_as_compositional_anchor',
        'compositional_movement_via_filter_not_via_chord_change',
        'atmospheric_sustain_as_compositional_foundation',
        'modal_voicings_above_drone_replace_chord_progression',
    ],
    'mode': 'aeolian_static',
    # STATIC: same chord (i = Dm) for 32 beats with VOICING SHIFTS as the compositional motion
    # The bass-root NEVER changes — only the upper-voice color shifts modal flavor
    # Sequence of voicings: sus2 (open) → min_add9 (lush) → sus_4_with_9 (modal-jazz) → min_triad (closed)
    'chords': [
        {'root_interval': 0, 'voicing': 'sus2',          'duration_beats': 8.0, 'roman': 'i^sus2',     'inversion': 0},
        {'root_interval': 0, 'voicing': 'min_add9',      'duration_beats': 8.0, 'roman': 'i^add9',     'inversion': 0},
        {'root_interval': 0, 'voicing': 'sus_4_with_9',  'duration_beats': 8.0, 'roman': 'i^sus4(9)',  'inversion': 0},
        {'root_interval': 0, 'voicing': 'min_triad',     'duration_beats': 8.0, 'roman': 'i (resolved)','inversion': 0},
    ],
    'duration_total_beats': 32.0,   # 8 bars in 4/4 — slow color drift
    'time_sig': (4, 4),
    'character_tags': ['dub_techno', 'static', 'modal_drift', 'drone_foundation', 'meditative', 'voice_leading'],
    'transformations_allowed': [
        'transpose', 'voicing_swap', 'augment_diminish',
        # NOT retrograde — color-drift direction matters (open → resolved)
    ],
    'notes_on_use': (
        'COMPOSITIONAL MOTION via voicing-only changes — the listener perceives harmonic '
        'evolution even though the BASS-ROOT IS ALWAYS THE SAME. Pair with sustained drone '
        'on tonic (D1) and BASS-LINE that traces the same root with rhythmic life. The '
        '8-bar-per-chord pacing is critical — at faster pacing the listener perceives "chord '
        'progression" instead of "modal drift" (different effect). Apply filter modulation '
        'on the pad-bus (open over 32 beats) for double-axis compositional motion. '
        'Basic Channel / Pole / Vladislav Delay tradition.'
    ),
}


HARMONIC_PROGRESSIONS['dark_electronic_quartal_stack'] = {
    'id': 'dark_electronic_quartal_stack',
    'sources': [
        ('NIN', 'The Wretched', 'quartal voicings + dark Aeolian color in atmospheric sections'),
        ('NIN', 'March of the Pigs', 'aggressive harmonic foundation with stacked-fourths'),
        ('Soundgarden', 'Head Down', 'modal voicings exploring quartal color above drone'),
    ],
    'advisor_recipes': [
        'industrial_textural_aggression_via_processed_guitar_layers',
        'modal_voicings_above_drone_replace_chord_progression',
        'hybrid_vocabulary_integration_within_sections',
        'rhythmic_emphasis_over_harmonic_movement_industrial_lesson',
    ],
    'mode': 'aeolian_quartal',
    # Dark-electronic 4-chord with QUARTAL voicings (stacked 4ths = D-G-C, C-F-Bb, etc.)
    # Quartal voicings have NO 3rd → no major/minor — pure modal openness
    # Roots: i - ♭VII - ♭VI - i (Dm-C-Bb-Dm with quartal voicings)
    'chords': [
        {'root_interval': 0,  'voicing': 'quartal',    'duration_beats': 4.0, 'roman': 'i^q',  'inversion': 0},
        {'root_interval': 10, 'voicing': 'quartal',    'duration_beats': 4.0, 'roman': '♭VII^q','inversion': 0},
        {'root_interval': 8,  'voicing': 'quartal',    'duration_beats': 4.0, 'roman': '♭VI^q', 'inversion': 0},
        # Final chord: return to tonic with min_maj7 voicing for that "Hitchcock" dark-jazz color
        {'root_interval': 0,  'voicing': 'min_maj7',   'duration_beats': 4.0, 'roman': 'i^minmaj7','inversion': 0},
    ],
    'duration_total_beats': 16.0,
    'time_sig': (4, 4),
    'character_tags': ['dark_electronic', 'quartal', 'industrial', 'aeolian_modal', 'dissonant_color'],
    'transformations_allowed': [
        'transpose', 'voicing_swap',
    ],
    'notes_on_use': (
        'Quartal voicings (D-G-C, C-F-Bb, Bb-Eb-Ab) have NO 3rd — sound is OPEN, MODAL, '
        'SLIGHTLY DISSONANT. Final chord uses min_maj7 (Dm with C# = D-F-A-C#) for the '
        '"Hitchcock" dark-jazz color that creates unresolved tension. Voice on Diva pad '
        'with FM modulation + drive saturation for industrial-electronic character. The '
        'progression sounds AGGRESSIVE-DARK without using power-chords or distortion — '
        'character lives in the voicings, not the volume. Pairs with rhythmic-emphasis-over-'
        'harmonic-movement: drums dominate foreground, harmony provides dark-color bed.'
    ),
}


# ============================================================================
# Render API — turn a harmonic progression into concrete MIDI notes
# ============================================================================

def render(progression: Dict[str, Any], tonic_pitch: int, start_beat: float = 0.0,
           octave_offset: int = 0, velocity: int = 90,
           voicing_override: Dict[int, str] = None) -> List[Dict[str, Any]]:
    """Render a harmonic progression into concrete MIDI notes.

    Each chord becomes a SET of simultaneous sustained notes (one per voicing-tone).

    Args:
        progression: a dict from HARMONIC_PROGRESSIONS
        tonic_pitch: MIDI pitch of the tonal center (e.g. 50 = D3)
        start_beat: where in the song this progression starts
        octave_offset: shift all chord-tones by N octaves
        velocity: base velocity (1-127) — clamped
        voicing_override: dict of chord_index -> voicing_name to override

    Returns:
        List of {'time', 'duration', 'velocity', 'pitch'} dicts.
    """
    notes = []
    cursor = start_beat
    for i, chord in enumerate(progression['chords']):
        root_pitch = tonic_pitch + chord['root_interval'] + 12 * octave_offset
        voicing_name = chord['voicing']
        if voicing_override and i in voicing_override:
            voicing_name = voicing_override[i]
        intervals = VOICINGS[voicing_name]
        # Apply inversion: rotate intervals so the Nth interval becomes the bass
        inv = chord.get('inversion', 0)
        if inv > 0 and inv < len(intervals):
            # Each rotation: lowest interval gets +12
            intervals = list(intervals)
            for _ in range(inv):
                lowest_idx = intervals.index(min(intervals))
                intervals[lowest_idx] += 12
        for iv in intervals:
            notes.append({
                'time': float(cursor),
                'duration': float(chord['duration_beats']),
                'velocity': max(1, min(127, int(velocity))),
                'pitch': int(root_pitch + iv),
            })
        cursor += chord['duration_beats']
    return notes


def list_progressions(filter_tags: List[str] = None,
                      filter_recipes: List[str] = None,
                      filter_mode: str = None) -> List[str]:
    """List progression IDs matching given filters."""
    out = []
    for pid, p in HARMONIC_PROGRESSIONS.items():
        if filter_tags and not any(t in p['character_tags'] for t in filter_tags):
            continue
        if filter_recipes and not any(r in p['advisor_recipes'] for r in filter_recipes):
            continue
        if filter_mode and p.get('mode') != filter_mode:
            continue
        out.append(pid)
    return out


# Self-test
if __name__ == '__main__':
    print(f'Harmonic progressions: {len(HARMONIC_PROGRESSIONS)}')
    print(f'Voicings available: {len(VOICINGS)}')
    for pid, p in HARMONIC_PROGRESSIONS.items():
        print(f'\n=== {pid} ===')
        print(f'  Mode: {p["mode"]}, total = {p["duration_total_beats"]} beats ({p["time_sig"]})')
        print(f'  Chord progression:')
        for c in p['chords']:
            print(f'    {c["roman"]:<5} root_offset={c["root_interval"]:+3d}  voicing={c["voicing"]:<12} dur={c["duration_beats"]}b inv={c["inversion"]}')

    # Render canonical progression in D minor (tonic_pitch=50 = D3)
    print('\n=== aeolian_i_VI_VII_i rendered in D minor at tonic D3 (50) ===')
    notes = render(HARMONIC_PROGRESSIONS['aeolian_i_VI_VII_i'], tonic_pitch=50, velocity=85)
    chord_times = sorted(set(n['time'] for n in notes))
    for t in chord_times:
        chord_notes = sorted([n['pitch'] for n in notes if n['time'] == t])
        print(f'  beat {t:5.1f}: pitches={chord_notes}')

    # Demo voicing_override: swap chord 0 to sus2
    print('\n=== Same progression with chord 0 voiced as sus2 ===')
    notes2 = render(HARMONIC_PROGRESSIONS['aeolian_i_VI_VII_i'], tonic_pitch=50, velocity=85,
                    voicing_override={0: 'sus2', 3: 'sus2'})
    chord_times = sorted(set(n['time'] for n in notes2))
    for t in chord_times:
        chord_notes = sorted([n['pitch'] for n in notes2 if n['time'] == t])
        print(f'  beat {t:5.1f}: pitches={chord_notes}')
