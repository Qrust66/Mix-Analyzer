"""Melodic motif library — Phase 1a of composition_engine.

Each motif is a CONTOUR + RHYTHM + CHARACTER, encoded with INTERVAL-RELATIVE pitches
(semitones from tonal center) so transposition is trivial. Cut & assemble friendly:
each motif is a SHORT fragment (1-4 bars) drawn from MULTIPLE source songs
documented in the advisor (anti-copyright by construction — no motif is a literal
copy of a single source phrase).

Schema:
    {
        'id': str,                              # snake_case unique identifier
        'sources': List[(artist, song, what)],   # multi-source provenance
        'advisor_recipes': List[str],            # which composition_advisor recipes
        'pitch_intervals_from_tonic': List[int], # semitones (negative = below tonic)
        'rhythm_beats': List[(start, duration)], # in beats; (4,4) default time-sig
        'velocity_contour': List[int],           # 1-127, parallel to pitch list
        'character_tags': List[str],             # 'descending', 'aeolian', 'lament', ...
        'duration_total_beats': float,
        'time_sig': Tuple[int, int],
        'transformations_allowed': List[str],
        'notes_on_use': str,
    }

Three lists (pitch_intervals, rhythm_beats, velocity_contour) MUST be same length.
"""

from typing import List, Tuple, Dict, Any


MELODIC_MOTIFS: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# DESCENDING MOTIFS — Aeolian / Phrygian / chromatic
# ============================================================================

MELODIC_MOTIFS['aeolian_descending_4_steps'] = {
    'id': 'aeolian_descending_4_steps',
    'sources': [
        ('Nirvana', 'All Apologies', 'verse vocal: D-C-Bb-A descending Aeolian phrase'),
        ('Soundgarden', 'Head Down', 'modal motion descending above drone'),
        ('Daft Punk', 'Veridis Quo', 'classical-influenced descending bass anchor'),
        ('Smashing Pumpkins', 'Soma', 'verse melodic descent before explosion'),
    ],
    'advisor_recipes': [
        'descending_riff_as_song_identity',
        'modal_voicings_above_drone_replace_chord_progression',
        'classical_influenced_chord_progression_in_electronic_context',
    ],
    # D minor relative: 1-♭7-♭6-5 = 0, -2, -4, -5 semitones (D, C, Bb, A)
    'pitch_intervals_from_tonic': [0, -2, -4, -5],
    # 1 beat each, total 4 beats = 1 bar in 4/4
    'rhythm_beats': [(0.0, 1.0), (1.0, 1.0), (2.0, 1.0), (3.0, 1.0)],
    'velocity_contour': [110, 100, 95, 92],   # softening descent — natural decay
    'character_tags': ['descending', 'aeolian', 'lament', 'foundational'],
    'duration_total_beats': 4.0,
    'time_sig': (4, 4),
    'transformations_allowed': [
        'transpose',           # change tonic
        'invert',              # mirror around tonic
        'retrograde',          # reverse direction
        'fragment',            # take any sub-sequence
        'octave_jump',         # shift any single note ±12
        'rhythmic_displace',   # shift all timing by N beats
        'augment_diminish',    # scale duration ×0.5 / ×2
    ],
    'notes_on_use': (
        'Foundational lament gesture. Strongest as bass-line at slow tempo (60-100 BPM) '
        'or as vocal/lead phrase at mid-tempo (100-130 BPM). Pairs with sustained drone '
        'on tonic. Becomes "robot_rock" engine when looped with micro-variations every '
        '4-8 bars (octave-jump on last note, retrograde once per 16-bar cycle).'
    ),
}


MELODIC_MOTIFS['phrygian_inflection_dark_color'] = {
    'id': 'phrygian_inflection_dark_color',
    'sources': [
        ('Radiohead', 'Pyramid Song', 'F#m chromatic chord roots inspired by Mingus Freedom — Eb flat-2 inflection'),
        ('NIN', 'The Day The World Went Away', 'sustained dark-modal vocal moment'),
        ('Soundgarden', 'Head Down', 'modal voicings exploring dark color above drone'),
        ('NIN', 'The Wretched', 'Phrygian-adjacent chromatic shift in atmospheric verses'),
    ],
    'advisor_recipes': [
        'mingus_freedom_chromatic_harmony_inspiration',
        'modal_voicings_above_drone_replace_chord_progression',
        'piano_composition_with_chromatic_harmony',
    ],
    # D Phrygian inflection: 1 → ♭2 → 1 (D - Eb - D) — 0, +1, 0 semitones
    # Then push down to 5 — adds the lament resolution: 0, +1, 0, -5
    'pitch_intervals_from_tonic': [0, 1, 0, -5],
    # Long-short-long-very-long: a sigh figure (intuitive, not gridded)
    'rhythm_beats': [(0.0, 1.5), (1.5, 0.5), (2.0, 1.0), (3.0, 5.0)],
    # Velocity contour: enter softly, lean into the Eb (the "dark" pitch), resolve gentle, sustain low
    'velocity_contour': [85, 102, 90, 78],
    'character_tags': ['phrygian', 'dark', 'sigh', 'chromatic_inflection', 'lament'],
    'duration_total_beats': 8.0,   # 2 bars in 4/4
    'time_sig': (4, 4),
    'transformations_allowed': [
        'transpose', 'invert', 'fragment', 'octave_jump',
        'augment_diminish', 'rhythmic_displace',
    ],
    'notes_on_use': (
        'The flat-2 (Eb above D tonic) is the soul of this motif — leaning into it and '
        'releasing creates the Phrygian "sigh". Use sparingly: once per breakdown or '
        'once mid-verse. Voice as lead-line, not bass. Pairs with sustained Dm Phrygian '
        'pad (D-Eb-A) underneath. Avoid in rhythm-driven dance contexts (fights groove).'
    ),
}


MELODIC_MOTIFS['chromatic_descent_4_step'] = {
    'id': 'chromatic_descent_4_step',
    'sources': [
        ('Radiohead', 'Pyramid Song', 'piano chord-root chromatic descent'),
        ('NIN', 'March of the Pigs', 'fast chromatic bass-line descent at extreme tempo'),
        ('Daft Punk', 'Veridis Quo', 'classical-influenced chromatic passing tones'),
        ('Smashing Pumpkins', 'Soma', 'pre-explosion chromatic tension descent'),
    ],
    'advisor_recipes': [
        'piano_composition_with_chromatic_harmony',
        'classical_influenced_chord_progression_in_electronic_context',
        'mingus_freedom_chromatic_harmony_inspiration',
        'descending_riff_as_song_identity',
    ],
    # Chromatic descent: 1 → ♭7 → ♭7- → ♭6 = 0, -2, -3, -4 (each step semitone or whole-step)
    # In D minor: D - C - B - Bb (the chromatic passing through B natural before Bb)
    'pitch_intervals_from_tonic': [0, -2, -3, -4],
    # Even quarters first, then a tied half-note: tension builds, releases on the lowest
    'rhythm_beats': [(0.0, 0.75), (0.75, 0.75), (1.5, 0.75), (2.25, 1.75)],
    'velocity_contour': [108, 102, 100, 115],   # cresc into the chromatic landing
    'character_tags': ['descending', 'chromatic', 'tension', 'classical_influenced'],
    'duration_total_beats': 4.0,
    'time_sig': (4, 4),
    'transformations_allowed': [
        'transpose', 'invert', 'retrograde', 'fragment',
        'octave_jump', 'augment_diminish', 'rhythmic_displace',
    ],
    'notes_on_use': (
        'The B natural (chromatic passing) is the surprise. Drives best as bass-line at '
        'mid-tempo (90-130 BPM) where the listener can hear the chromatic motion clearly. '
        'At extreme tempo (200+ BPM, MOTP-style), augment_diminish ×0.5 (eighth-note feel) '
        'and the chromatic detail BLURS into texture — different effect, both valid. '
        'Strongest as 2-bar lead-up before resolution (downbeat of bar 3 = tonic return).'
    ),
}


MELODIC_MOTIFS['pachelbel_descending_bass_8_chord'] = {
    'id': 'pachelbel_descending_bass_8_chord',
    'sources': [
        ('Daft Punk', 'Veridis Quo', 'Pachelbel-adjacent classical-electronic descending bass — D-A-Bm-F#m-G-D-G-A'),
        ('Radiohead', 'The National Anthem', 'D-rooted bass-line that Yorke wrote at age 16'),
        ('Smashing Pumpkins', 'Soma', 'extended pre-explosion bass descent'),
    ],
    'advisor_recipes': [
        'classical_influenced_chord_progression_in_electronic_context',
        'voice_leading_clarity_via_synth_pad_layers',
        'bass_line_first_compositional_method',
        'classical_electronic_crossover_via_duo_auteur_framework',
    ],
    # Pachelbel-canon-adjacent in D minor: I - V - vi - iii - IV - I - IV - V
    # Bass roots from D as 0: D(0) A(7) B(2 if natural-minor= +2 above D, but we want bass DOWN
    # so use -2 octave-down logic: D=0, A=-5, B=-3, F#=-8, G=-7, D=-12 (octave below), G=-5, A=-3
    # Actually for clarity: use raw pitch intervals from D in the original octave
    # D=0, A=-5 (descending fifth down), Bm root B=-3, F#m root F#=-8, G=-7, D=-12, G=-5 octave up, A=-3 octave up
    # Simpler: think of bass-line moving DOWN by step or third
    # D - A - B - F# - G - D - G - A as bass-roots (one note per chord, half-note each)
    'pitch_intervals_from_tonic': [0, -5, -10, -8, -7, -12, -7, -5],
    # Each chord-root sustained 2 beats (half note) → 16 beats total = 4 bars in 4/4
    'rhythm_beats': [
        (0.0, 2.0), (2.0, 2.0), (4.0, 2.0), (6.0, 2.0),
        (8.0, 2.0), (10.0, 2.0), (12.0, 2.0), (14.0, 2.0),
    ],
    'velocity_contour': [105, 100, 95, 95, 100, 110, 100, 105],   # subtle arc
    'character_tags': ['descending', 'classical_influenced', 'bass_line', 'extended_form', 'voice_leading'],
    'duration_total_beats': 16.0,   # 4 bars
    'time_sig': (4, 4),
    'transformations_allowed': [
        'transpose', 'fragment',
        'octave_jump',
        'augment_diminish',          # ×0.5 for 2-bar version, ×2 for 8-bar slow version
        'rhythmic_displace',
        # NOT retrograde or invert — disrupts the voice-leading logic
    ],
    'notes_on_use': (
        'Use as compositional FOUNDATION, not ornament. Place this bass-line first, '
        'then build pad voicings + drums + lead AROUND it (bass_line_first_compositional_method). '
        'Pairs with sustained Dm pad above on each chord-root (voice-leading clarity). '
        'At slow tempo (80-100 BPM) feels classical/cinematic; at house tempo (120-128) feels '
        'filter-house-classical-crossover (Veridis Quo territory). The descending arc IS the '
        'compositional movement — chord progression alone provides "perceived motion" without '
        'filter automation needed.'
    ),
}


# ============================================================================
# ASCENDING / ARC MOTIFS — pre-chorus build, ascending counter, voice-leading
# ============================================================================

MELODIC_MOTIFS['pre_chorus_ascending_arc'] = {
    'id': 'pre_chorus_ascending_arc',
    'sources': [
        ('Smashing Pumpkins', 'Soma', 'pre-explosion ascending build before cathartic chorus'),
        ('NIN', "We're In This Together", 'anthemic build into multi-chorus iterations'),
        ('Soundgarden', 'Fell On Black Days', 'verse-to-chorus ascending vocal lift'),
    ],
    'advisor_recipes': [
        'density_arc_arrangement_sparse_to_wall',
        'explosion_chorus_as_cathartic_release_not_just_loud_section',
        'multiple_chorus_iterations_with_intensification',
        'extended_dynamic_arc_six_plus_minutes_patient_build',
    ],
    # 1 → 3 → 4 → 5 → ♭7 → 1 (octave) — ascending Aeolian arc that lifts past tonic to flat-7 then home
    # Semitones from tonic: 0, +3, +5, +7, +10, +12
    'pitch_intervals_from_tonic': [0, 3, 5, 7, 10, 12],
    # Accelerating rhythm — quarters slowing into the peak (eighth-eighth-quarter-quarter-half-whole)
    # Total: 0.5 + 0.5 + 1 + 1 + 2 + 4 = 9 beats — fits 2.25 bars in 4/4
    'rhythm_beats': [(0.0, 0.5), (0.5, 0.5), (1.0, 1.0), (2.0, 1.0), (3.0, 2.0), (5.0, 4.0)],
    # Velocity ramp — building intensity into the peak, sustained at top
    'velocity_contour': [85, 92, 100, 110, 120, 125],
    'character_tags': ['ascending', 'arc', 'cathartic', 'pre_chorus', 'cresc', 'patient_build'],
    'duration_total_beats': 9.0,
    'time_sig': (4, 4),
    'transformations_allowed': [
        'transpose', 'fragment', 'octave_jump',
        'augment_diminish',          # ×2 for slow-burn (extended_dynamic_arc), ×0.5 for compressed
        # NOT invert (would be descending, defeats purpose) or retrograde
    ],
    'notes_on_use': (
        'Use as 2-bar lead-in to a chorus/drop. The accelerating-then-sustained rhythm is the '
        'KEY: most generic ascending motifs use even quarters which feel mechanical. The '
        'eighth-eighth-quarter-quarter-half-whole pattern PHYSICALLY lifts the listener. '
        'Voice as lead-synth or vocal in mid-register. Pairs with synchronized risers/snare-fill '
        'in last bar. Avoid in compressed-economy contexts (this motif WANTS the chorus payoff).'
    ),
}


MELODIC_MOTIFS['ascending_counter_to_descending_bass'] = {
    'id': 'ascending_counter_to_descending_bass',
    'sources': [
        ('Soundgarden', 'Head Down', 'lead vocal ascending against drone descending modal-shifts'),
        ('NIN', 'The Wretched', 'hybrid section with melodic line moving counter to bass'),
        ('Radiohead', 'Pyramid Song', 'lead vocal in BREAKDOWN ascending against piano roots'),
        ('Daft Punk', 'Veridis Quo', 'voice-leading top-line opposing descending bass'),
    ],
    'advisor_recipes': [
        'voice_leading_clarity_via_synth_pad_layers',
        'industrial_textural_aggression_via_processed_guitar_layers',
        'classical_influenced_chord_progression_in_electronic_context',
        'hybrid_vocabulary_integration_within_sections',
    ],
    # Ascending tetrachord: 5 → 6 → ♭7 → 1 (octave-up landing)
    # In D minor: A → Bb → C → D (above tonic) = +7, +8, +10, +12 semitones
    'pitch_intervals_from_tonic': [7, 8, 10, 12],
    # Each note dotted-quarter EXCEPT the last (whole) — pulls the line skyward
    'rhythm_beats': [(0.0, 1.5), (1.5, 1.5), (3.0, 1.0), (4.0, 4.0)],
    'velocity_contour': [95, 100, 110, 118],
    'character_tags': ['ascending', 'counter_melody', 'voice_leading', 'tension_resolution'],
    'duration_total_beats': 8.0,   # 2 bars in 4/4
    'time_sig': (4, 4),
    'transformations_allowed': [
        'transpose', 'fragment', 'octave_jump',
        'augment_diminish', 'rhythmic_displace',
    ],
    'notes_on_use': (
        'CRITICAL pairing: deploy this UNDER OR OVER a descending bass-line motif (e.g. '
        'aeolian_descending_4_steps OR pachelbel_descending_bass_8_chord). The contrary '
        'motion creates compositional density without adding more layers. Voice as lead-synth '
        'in upper register (octave above tonic). The dotted-quarter rhythm prevents the line '
        'from sounding gridded — it BREATHES across barlines.'
    ),
}


MELODIC_MOTIFS['modal_voice_leading_smooth_pad'] = {
    'id': 'modal_voice_leading_smooth_pad',
    'sources': [
        ('Soundgarden', 'Head Down', 'modal voicings shifting smoothly above B drone'),
        ('Soundgarden', 'Fell On Black Days', 'sus voicings with smooth voice-leading'),
        ('NIN', 'The Day The World Went Away', 'sustained pad voicings with subtle internal motion'),
        ('Daft Punk', 'Veridis Quo', 'voice-leading clarity via synth pad layers'),
    ],
    'advisor_recipes': [
        'voice_leading_clarity_via_synth_pad_layers',
        'modal_voicings_above_drone_replace_chord_progression',
        'sus_voicings_verse_with_drop_tuning_pedal',
        'atmospheric_sustain_as_compositional_foundation',
    ],
    # Voice-leading exercise: ONE voice (the soprano) moves SMOOTHLY by step
    # Across 4 chord changes: 5 → 6 → ♭6 → 5 (=the inner motion of Dsus2→Dm→Dphrygian→Dm)
    # Semitones: +7, +9, +8, +7 (A → B → Bb → A)
    'pitch_intervals_from_tonic': [7, 9, 8, 7],
    # Each note sustained 4 beats (whole bar each) — slow modal motion
    'rhythm_beats': [(0.0, 4.0), (4.0, 4.0), (8.0, 4.0), (12.0, 4.0)],
    'velocity_contour': [80, 85, 88, 82],   # subtle swell
    'character_tags': ['voice_leading', 'modal', 'smooth', 'sustained', 'atmospheric'],
    'duration_total_beats': 16.0,   # 4 bars
    'time_sig': (4, 4),
    'transformations_allowed': [
        'transpose', 'fragment', 'augment_diminish', 'octave_jump',
        # NOT invert or retrograde — voice-leading direction matters
    ],
    'notes_on_use': (
        'This is the SOPRANO line of a 4-chord modal progression. To deploy: render the '
        'full pad chords UNDERNEATH (PAD track playing Dsus2-Dm-Dphrygian-Dm with one chord '
        'per bar) — this motif then highlights the moving voice. The "movement" the listener '
        'hears is this single voice stepping by minor 2nd / major 2nd. Subtle, professional, '
        'avoids the static-pad feel of Banger v2. Best at slow tempo (60-100 BPM) atmospheric '
        'contexts. At higher tempos, augment_diminish ×0.5 (each note holds 2 beats instead).'
    ),
}


# ============================================================================
# STATIC / OSCILLATING MOTIFS — minimal-element, asymmetric meters, pedal foundations
# ============================================================================

MELODIC_MOTIFS['eirp_floating_arpeggio_10_4'] = {
    'id': 'eirp_floating_arpeggio_10_4',
    'sources': [
        ('Radiohead', 'Everything In Its Right Place', 'Rhodes electric piano floating arpeggio in 10/4'),
        ('Radiohead', 'Pyramid Song', 'piano figure floating across ambiguous meter'),
        ('NIN', 'Copy of A', 'modular pattern repeating with subtle micro-variations'),
    ],
    'advisor_recipes': [
        'asymmetric_meter_as_album_opener_statement_of_intent',
        'fender_rhodes_electric_piano_as_compositional_foundation',
        'manipulated_vocal_samples_as_textural_color',
        'minimum_element_electronic_experimental_arrangement',
        'intentionally_ambiguous_rhythm_felt_not_counted',
    ],
    # 4-note arpeggio cell that reads in 10/4 as 5+5 OR 4+4+2 OR 2+3+2+3:
    # 1 → 3 → 5 → 3 → ♭7 → 5 → 3 → 1 → 5 → 3
    # Semitones from tonic in F minor (the actual EIRP key reference, but transposable):
    # F-Ab-C-Ab-Eb-C-Ab-F-C-Ab in 10 hits across 10 beats = 1 hit/beat
    # Intervals from tonic: 0, +3, +7, +3, +10, +7, +3, 0, +7, +3
    'pitch_intervals_from_tonic': [0, 3, 7, 3, 10, 7, 3, 0, 7, 3],
    # Each note 1 beat exactly = 10 beats total = 1 bar in 10/4
    'rhythm_beats': [(float(i), 1.0) for i in range(10)],
    # Subtle velocity contour — each new arpeggio peak slightly accented
    'velocity_contour': [88, 80, 92, 78, 95, 82, 78, 88, 90, 78],
    'character_tags': ['arpeggio', 'asymmetric_meter', 'floating', 'rhodes', 'minimal_element', 'ambiguous'],
    'duration_total_beats': 10.0,
    'time_sig': (10, 4),
    'transformations_allowed': [
        'transpose', 'fragment', 'rhythmic_displace',
        # NOT invert/retrograde — pattern character is in the contour
    ],
    'notes_on_use': (
        'Loop continuously across an entire section (8-16 bars in 10/4). The 10/4 grouping '
        '(perceived as 5+5 by most listeners) creates the asymmetric-felt-not-counted floating '
        'quality. Voice on Rhodes/electric-piano sample — NOT on saw-lead synth (kills the '
        'character). Pair with sustained tonic drone underneath (e.g. F1 if rendering in F). '
        'Apply micro-variations every 4-bar repetition: random velocity ±10, occasionally swap '
        'note positions 4 and 5 for variety. The repetition IS the song foundation.'
    ),
}


MELODIC_MOTIFS['head_down_modal_above_drone_7_4'] = {
    'id': 'head_down_modal_above_drone_7_4',
    'sources': [
        ('Soundgarden', 'Head Down', 'modal voicings shifting in 7/4 above sustained B drone'),
        ('Radiohead', 'Pyramid Song', 'modal motion above sustained piano roots'),
        ('NIN', 'The Day The World Went Away', 'sustained pad above held tonic'),
    ],
    'advisor_recipes': [
        'seven_four_asymmetric_meter_as_structural_device',
        'modal_voicings_above_drone_replace_chord_progression',
        'drone_foundation_as_compositional_anchor',
        'long_asymmetric_cycle_for_meditation_not_complexity',
    ],
    # 7/4 grouped as 4+3 (rolling). Modal motion: 5 → ♭7 → 1(oct) → 5 → ♭7 → 5 → 4
    # Each cell uses upper modal-tones above tonic
    # Semitones: +7, +10, +12, +7, +10, +7, +5
    'pitch_intervals_from_tonic': [7, 10, 12, 7, 10, 7, 5],
    # Long-short-long-short-medium-medium-long pattern ALIGNED with 4+3 grouping
    # Group 1 (4 beats): 2-1-1
    # Group 2 (3 beats): 1-0.5-1.5
    'rhythm_beats': [(0.0, 2.0), (2.0, 1.0), (3.0, 1.0),
                     (4.0, 1.0), (5.0, 0.5), (5.5, 0.5), (6.0, 1.0)],
    'velocity_contour': [88, 95, 100, 85, 92, 88, 75],
    'character_tags': ['modal', 'asymmetric_meter', 'drone_above', 'meditative', 'stately'],
    'duration_total_beats': 7.0,   # 1 bar in 7/4
    'time_sig': (7, 4),
    'transformations_allowed': [
        'transpose', 'fragment', 'rhythmic_displace',
    ],
    'notes_on_use': (
        'Voice as upper synth-pad melodic-line above sustained root drone (which lives in '
        'the SUB or BASS track). Feels meditative-stately at 80-95 BPM. The 4+3 grouping '
        '(beat 1, beat 5 = strong) makes the asymmetric meter FEEL natural rather than '
        'counted. Loop for 16 bars in 7/4 = 112 beats = ~84 sec at 80 BPM (a meditation '
        'cycle). At higher tempos the meditation breaks; better to fragment to 3-beat or '
        '4-beat sub-phrases.'
    ),
}


MELODIC_MOTIFS['national_anthem_pedal_bass_walking'] = {
    'id': 'national_anthem_pedal_bass_walking',
    'sources': [
        ('Radiohead', 'The National Anthem', 'D-rooted bass-line that Yorke wrote at age 16'),
        ('NIN', 'March of the Pigs', 'tonic-pedal anchored aggressive bass'),
        ('Daft Punk', 'Around the World', 'four-on-floor bass with pedal anchor'),
    ],
    'advisor_recipes': [
        'bass_line_first_compositional_method',
        'drone_foundation_as_compositional_anchor',
        'mingus_locked_rhythm_plus_free_horn_compositional_template',
        'rhythmic_emphasis_over_harmonic_movement_industrial_lesson',
    ],
    # Walking bass anchored on tonic D, with chromatic surprises
    # Pattern: 1 → 1 → ♭3 → 5 → 1 → 1 → ♭7 → ♭2 (the ♭2 is the Phrygian inflection / chromatic surprise)
    # Semitones: 0, 0, 3, 7, 0, 0, -2, 1 (or +1 = Eb, which becomes Phrygian color)
    'pitch_intervals_from_tonic': [0, 0, 3, 7, 0, 0, -2, 1],
    # Mostly 16th-notes locked-tight with TWO sustains — gives "pedal anchored" feel
    # Beat positions: 0 (sustain 1.5) → 1.5 (0.5) → 2 (0.5) → 2.5 (0.5) → 3 (sustain 1.5)
    # Wait, 8 notes total. Let me redesign timing for 8-note phrase:
    # 0 - 0.5 - 1 - 1.5 - 2 - 2.5 - 3 - 3.5 → all 8 hits each 0.5 long?
    # No — make rhythmically interesting: long-short pattern alternating
    'rhythm_beats': [
        (0.0, 1.0), (1.0, 0.5), (1.5, 0.5),    # bar 1 first half: long-short-short
        (2.0, 1.0), (3.0, 0.5), (3.5, 0.5),    # bar 1 second half: long-short-short
        (4.0, 1.5), (5.5, 2.5),                 # bar 2: dotted-quarter then sustained 2.5
    ],
    'velocity_contour': [115, 95, 100, 110, 100, 105, 118, 90],   # downbeats accent
    'character_tags': ['bass_line', 'pedal', 'walking', 'tonic_anchored', 'foundational', 'aggressive'],
    'duration_total_beats': 8.0,   # 2 bars in 4/4
    'time_sig': (4, 4),
    'transformations_allowed': [
        'transpose', 'fragment', 'octave_jump', 'rhythmic_displace',
    ],
    'notes_on_use': (
        'BASS-FIRST compositional seed — write THIS, then build everything else around it. '
        'Voice on Sub37 / Massive / TB-303 character bass synth. The Eb (Phrygian flat-2) '
        'in note 8 is the "wrong note" that grounds the song identity — Yorke-tradition. '
        'At 120-130 BPM this feels propulsive (NA-style). At 80-100 BPM feels heavy/dub. '
        'Loop 16 bars (= 8 cycles of 2-bar pattern) for verse foundation. Pair with '
        'unrelated lead-line on top (no need for harmonic chord-progression — bass + melody '
        'is enough).'
    ),
}


# ============================================================================
# SPECIAL CHARACTER MOTIFS — vocoded, robot-rock, chromatic-fast, chant-outro
# ============================================================================

MELODIC_MOTIFS['vocoded_phrase_call_response_2bar'] = {
    'id': 'vocoded_phrase_call_response_2bar',
    'sources': [
        ('Daft Punk', 'Harder Better Faster Stronger', 'vocoded vocal as primary melodic carrier'),
        ('Daft Punk', 'Around the World', 'vocoded phrase repeated hypnotically as instrument'),
    ],
    'advisor_recipes': [
        'vocoded_vocal_as_primary_melodic_carrier_full_song',
        'vocoded_vocal_phrase_as_instrument_not_lyric',
        'four_on_the_floor_120_bpm_house_foundation',
        'pop_song_structure_within_electronic_vocabulary',
    ],
    # Pop-electronic phrase: 1 → ♭3 → 5 → ♭7 → 5 → ♭3 → 1 (call: ascending, response: descending)
    # Semitones: 0, 3, 7, 10, 7, 3, 0
    'pitch_intervals_from_tonic': [0, 3, 7, 10, 7, 3, 0],
    # Rest of 2 beats between call (notes 1-4) and response (notes 5-7) — phrase that BREATHES
    'rhythm_beats': [
        (0.0, 0.5), (0.5, 0.5), (1.0, 0.5), (1.5, 0.5),    # call (4 hits, beats 0-2)
        # silent gap beats 2-4 (the breath)
        (4.0, 0.5), (4.5, 0.5), (5.0, 3.0),                  # response (3 hits, last sustained 3 beats)
    ],
    'velocity_contour': [110, 100, 105, 115, 110, 100, 95],
    'character_tags': ['vocoded', 'call_response', 'pop_electronic', 'hypnotic_repetition', 'phrase_with_breath'],
    'duration_total_beats': 8.0,   # 2 bars in 4/4 — the rest IS part of the motif
    'time_sig': (4, 4),
    'transformations_allowed': [
        'transpose', 'fragment', 'octave_jump',
        # NOT retrograde — call/response logic depends on direction
    ],
    'notes_on_use': (
        'The 2-BEAT REST between call and response is the secret — most loops never breathe. '
        'Voice through Output Vocoder / hardware Korg MS-2000 vocoder for that pop-electronic '
        'character. Loop 8-16 bars (4-8 cycles of this 2-bar phrase). Pair with 4-on-floor '
        'kick + filter modulation on the synth-pad. AVOID over-quantizing — let the voice '
        'breathe. The motif WANTS the silence; do not fill it.'
    ),
}


MELODIC_MOTIFS['robot_rock_riff_with_micro_variations'] = {
    'id': 'robot_rock_riff_with_micro_variations',
    'sources': [
        ('Queens Of The Stone Age', 'First It Giveth', 'robot-rock hypnotic repetitive riff with micro-variations'),
        ('Smashing Pumpkins', 'Quiet', 'sustained riff foundation with subtle drift'),
        ('Daft Punk', 'Around the World', 'looped pattern with documented micro-variations'),
    ],
    'advisor_recipes': [
        'robot_rock_hypnotic_repetitive_riff_with_micro_variations',
        'riff_as_both_hook_and_structural_backbone',
        'descending_riff_as_song_identity',
    ],
    # Base 1-bar riff in low register: 1-1-♭7-5-♭7-1-1-5
    # Semitones: 0, 0, -2, -7, -2, 0, 0, -7
    'pitch_intervals_from_tonic': [0, 0, -2, -7, -2, 0, 0, -7],
    # Gate-length variation built into rhythm: 0.5 (full) vs 0.4 (80% gate) — staccato/tenuto contrast
    'rhythm_beats': [
        (0.0, 0.5), (0.5, 0.4),
        (1.0, 0.5), (1.5, 0.5),
        (2.0, 0.4), (2.5, 0.5),
        (3.0, 0.4), (3.5, 0.5),
    ],
    'velocity_contour': [115, 105, 110, 95, 102, 113, 105, 90],
    'character_tags': ['robot_rock', 'hypnotic', 'staccato_tenuto_mix', 'low_register', 'foundational_riff'],
    'duration_total_beats': 4.0,   # 1 bar — designed to LOOP with VARIATIONS every 4-8 cycles
    'time_sig': (4, 4),
    'transformations_allowed': [
        'transpose', 'octave_jump',          # USE: octave-jump note 4 every 4th cycle
        'rhythmic_displace',                  # USE: ±5-15ms timing nudge per cycle
        'fragment',
    ],
    'notes_on_use': (
        'CORE RIFF for LOOPING with documented micro-variations: (a) octave-jump note 4 '
        'every 4th cycle, (b) retrograde notes 5-8 every 8th cycle for surprise, '
        '(c) random ±5-15ms timing nudge per cycle, (d) gate-length variation already '
        'built into rhythm. Voice on character-bass synth (Sub37 / Massive / Diva sub). '
        'Pair with syncopated_kick (NOT 4-on-floor) for industrial-techno feel.'
    ),
}


MELODIC_MOTIFS['chromatic_fast_descent_aggressive'] = {
    'id': 'chromatic_fast_descent_aggressive',
    'sources': [
        ('NIN', 'March of the Pigs', 'fast chromatic bass-line at extreme tempo'),
        ('Soundgarden', 'Jesus Christ Pose', 'aggressive descending chromatic riff'),
        ('Smashing Pumpkins', 'Bodies', 'fast-tempo chromatic descent'),
    ],
    'advisor_recipes': [
        'fast_tempo_148_156_bpm_aggressive_heavy_rock',
        'asymmetric_meter_at_extreme_tempo',
        'industrial_textural_aggression_via_processed_guitar_layers',
        'unrelenting_aggression_no_dynamic_arc',
    ],
    # Chromatic descent at speed: D → Eb → D → C → Bb → A → Bb → A
    # Semitones: 0, 1, 0, -2, -4, -5, -4, -5
    'pitch_intervals_from_tonic': [0, 1, 0, -2, -4, -5, -4, -5],
    # Sixteenth-note hits packed tight — at 150 BPM this becomes blurred-aggressive
    'rhythm_beats': [(i * 0.25, 0.25) for i in range(8)],
    'velocity_contour': [125, 105, 115, 110, 118, 122, 108, 120],
    'character_tags': ['chromatic', 'descending', 'aggressive', 'fast_tempo', 'industrial', 'high_density'],
    'duration_total_beats': 2.0,   # 1/2 bar in 4/4 — designed to LOOP fast
    'time_sig': (4, 4),
    'transformations_allowed': [
        'transpose', 'fragment',
        'augment_diminish',          # ×0.5 = 32nds (even faster), ×2 = mid-tempo version
    ],
    'notes_on_use': (
        'AT 145-160 BPM: iconic NIN MOTP / SG JCP fast-aggressive bass-line. The chromatic '
        'D→Eb→D wobble at start creates instability; descent to A then ♭6→5 oscillation '
        'traps the listener. Voice on heavily-saturated bass-synth (Decapitator + Trash 2). '
        'At 100 BPM this becomes ominous-walking-bass — different effect, both valid. '
        'Loop 4-8 bars. The 2-beat phrase length is critical — listener never gets footing.'
    ),
}


MELODIC_MOTIFS['outro_chant_fragment_repeating'] = {
    'id': 'outro_chant_fragment_repeating',
    'sources': [
        ('Nirvana', 'All Apologies', 'outro chant: short 2-3 note vocal fragment repeated'),
        ('NIN', "We're In This Together", 'multi-chorus iterations with intensification'),
        ('Soundgarden', 'Overfloater', 'extended atmospheric outro fragment'),
    ],
    'advisor_recipes': [
        'outro_chant_extension_via_repetition_not_fade',
        'vocal_layering_as_chant_build_mechanism',
        'multiple_chorus_iterations_with_intensification',
        'album_closer_resolution_function',
    ],
    # 3-note chant fragment: 1 → ♭3 → 1
    'pitch_intervals_from_tonic': [0, 3, 0],
    # Long-medium-long: a sigh / breath. 4 beats = 1 bar.
    'rhythm_beats': [(0.0, 1.5), (1.5, 1.0), (2.5, 1.5)],
    'velocity_contour': [85, 90, 88],
    'character_tags': ['chant', 'outro', 'repetition', 'vocal_layering', 'minimal'],
    'duration_total_beats': 4.0,   # 1 bar — designed to repeat 8-16x for outro
    'time_sig': (4, 4),
    'transformations_allowed': [
        'transpose', 'fragment',
    ],
    'notes_on_use': (
        'OUTRO TOOL: loop 8-16 bars to BUILD an outro WITHOUT FADING. Each iteration ADD '
        'ONE LAYER: cycle 1 = single voice, cycle 2 = + octave-doubled, cycle 3 = + '
        'harmonized 3rd, cycle 4 = + reverb-drenched whisper layer. Velocity stays SOFT '
        '(80-95) — build is in LAYER COUNT, not loudness. End with abrupt cut on final 1.'
    ),
}


# ============================================================================
# Render API — turn a motif into concrete MIDI notes
# ============================================================================

def render(motif: Dict[str, Any], tonic_pitch: int, start_beat: float = 0.0,
           octave_offset: int = 0, velocity_scale: float = 1.0) -> List[Dict[str, Any]]:
    """Render a motif into a list of concrete MIDI notes.

    Args:
        motif: a dict from MELODIC_MOTIFS
        tonic_pitch: MIDI pitch of the tonal center (e.g. 50 = D3)
        start_beat: where in the song this motif starts (0.0 = bar 1 beat 1)
        octave_offset: shift all pitches by N octaves (±12 semitones each)
        velocity_scale: multiply velocities by this (clamped 1-127)

    Returns:
        List of {'time', 'duration', 'velocity', 'pitch'} dicts ready for MIDI.
    """
    notes = []
    for i, interval in enumerate(motif['pitch_intervals_from_tonic']):
        rel_start, dur = motif['rhythm_beats'][i]
        vel = motif['velocity_contour'][i]
        notes.append({
            'time': float(start_beat + rel_start),
            'duration': float(dur),
            'velocity': max(1, min(127, int(vel * velocity_scale))),
            'pitch': int(tonic_pitch + interval + 12 * octave_offset),
        })
    return notes


def list_motifs(filter_tags: List[str] = None,
                filter_recipes: List[str] = None) -> List[str]:
    """List motif IDs matching given character tags or advisor recipes."""
    out = []
    for mid, m in MELODIC_MOTIFS.items():
        if filter_tags and not any(t in m['character_tags'] for t in filter_tags):
            continue
        if filter_recipes and not any(r in m['advisor_recipes'] for r in filter_recipes):
            continue
        out.append(mid)
    return out


# Self-test
if __name__ == '__main__':
    print(f'Melodic motifs: {len(MELODIC_MOTIFS)}')
    for mid, m in MELODIC_MOTIFS.items():
        print(f'\n=== {mid} ===')
        print(f'  Sources: {len(m["sources"])} ({", ".join(s[0] for s in m["sources"])})')
        print(f'  Advisor recipes: {m["advisor_recipes"]}')
        print(f'  Tags: {m["character_tags"]}')
        # Render in D minor at quarter note
        rendered = render(m, tonic_pitch=50, start_beat=0)
        print(f'  Rendered in D minor:')
        for n in rendered:
            print(f'    pitch={n["pitch"]} time={n["time"]} dur={n["duration"]} vel={n["velocity"]}')
