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
