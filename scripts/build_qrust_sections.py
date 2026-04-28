"""Build Qrust_7Sections.als — 7 driving sections at 128 BPM in C, composed
via the multi-agent sphere agents PLUS the banque MIDI Qrust v2 patterns.

The bank (`ableton/banque_midi_qrust_v2.xlsx`) provides:
  - 12 calibrated profiles ("Acid Drops cible", "EBM driving", ...)
  - 16-step rhythm patterns per genre (kick / snare / hat)
  - bassline degree sequences per style (e.g. "1, 1, b2, 1")
  - per-style velocity ranges
  - chord progressions per mood

Sections (all 16 bars @ 128 BPM, root = C):

  1. PEDAL  — Acid Drops cible profile (sheet 05 R5)
       Mode: C Phrygian  |  Progression: i-i-i-bII × 4 (pédale + bII tease)
       Kick: X...X...X...X...  |  Bass: 1, 1, b2, 1 (C C C Db)
       Vibe: dark industrial groovy, signature Qrust target sound.

  2. LOCK   — Industrial classic profile (sheet 02 R21-R24)
       Mode: C Aeolian  |  Progression: i-bVI-bVII-i × 4
       Kick: X...X...X.X.X... (variation step 11)
       Bass: 1, 1, b6, b7 (C C Ab Bb — NIN-style heavy)
       1-bar dropout at bar 12 -> slam back at 13.

  3. DRIVE  — EBM driving profile (sheet 02 R25-R27)
       Mode: C Phrygian  |  Progression: i-bII-bVII-i × 4
       Kick: X.X.X.X.X.X.X.X. (8ths driving)
       Bass: 1, 1, b2, 1, 5, 1, b3, 1 (EBM mélodique 8ths)

  4. TEASE  — Phrygian dom dark profile (sheet 05 R14)
       Mode: C Phrygian DOMINANT (maj 3 = E natural — venom)
       Progression: I-I-bII-I-I-I-bII-I-I-bII-I-I-bII-I-bII-I (densifying bII)
       Kick: X...X...X...X... 4x4  |  Hat: ..X...X.a.X...X. (accent step 9)
       Bass: 1, b2, 3, 1 (C Db E C — the major 3rd snake-charmer)
       Voicing: I_dominant7_no5 (C-E-Bb venom voicing)
       Vibe: exotic peak — modal contrast on same root.

  5. BRIDGE — Industrial breakbeat profile (sheet 05 R15)
       Mode: C Phrygian (return home)  |  Progression: i-bII-i-bvii° × 4
       Kick: X.........X..... (broken — 1 and "and of 3")
       Snare: ....X.........X. (displaced — 1 and 3.5 off)
       Hat: X.X.X.XgX.X.X.X. (Amen-style ghost-dense breakbeat)
       1-bar stop_time at bar 12 -> final_push 13-16 -> abrupt cut.

  6. PULSE  — Dark techno minimal profile (sheet 05 R10)
       Mode: C LOCRIAN (b5 = Gb introduced, peak modal darkness)
       Progression: i° pedal × 14 + bII × 2 + biii × 1 (16 events)
       Kick: X...X...X...X... 4-on-floor  |  Snare: ABSENT (per profile)
       Hat: off-beat + accents random  |  Voicing: i_dim_no5 hides b5
       Asymmetric phrasing 5+5+6 (Locrian instability at structural level)
       Vibe: maximum darkness — "le groove vient des accents" (bank R10).

  7. CLIMB  — Industrial groovy profile (sheet 05 R6)
       Mode: C Phrygian (HOME after Pulse's Locrian darkness)
       Progression: i → bVII → bVI → bII × 4 (descending chromatic)
       Kick: X...X...X..gX... (variation with GHOST kick on 2.75)
       Snare: 1+3 backbeat  |  Hat: 16ths denses
       Voicing: power i, drop_2 bVI, chromatic_neighbor_pad bII
       Cadence: modal (bII -> i loop — Phrygian fingerprint closes EP)
       Vibe: encore / final climax with ghost-kick swagger.

Timeline: Pedal 0-64, Lock 64-128, Drive 128-192, Tease 192-256,
Bridge 256-320, Pulse 320-384, Climb 384-448. 448 beats = 112 bars
@ 4/4 = ~3:30 at 128 BPM.

Sphere agents invoked: structure-decider + harmony-decider per section
(14 agent calls total). Rhythm/arrangement/dynamics come from the bank
profile mapping — the agents at Phase 2.6 are descriptive at those
spheres anyway, so the bank does the substantive work.

Note generators read the bank's 16-step grids and bassline degree
sequences directly — no improvising from scratch.
"""
from __future__ import annotations

import gzip
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple

from composition_engine.blueprint import SectionBlueprint, check_cohesion
from composition_engine.blueprint.agent_parsers import (
    parse_harmony_decision_from_response,
    parse_structure_decision_from_response,
)

from scripts.build_multi_agent_demo import (
    _build_midi_clip,
    _clone_midi_track,
    _insert_tracks_after,
    _set_project_tempo,
    _bump_next_pointee_id,
)


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Template.als"
DST = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Qrust_7Sections.als"

PROJECT_TEMPO = 128
BARS_PER_SECTION = 16
BEATS_PER_BAR = 4
SECTION_BEATS = BARS_PER_SECTION * BEATS_PER_BAR  # 64
N_SECTIONS = 7
TOTAL_BEATS = N_SECTIONS * SECTION_BEATS  # 448


# ============================================================================
# Hardcoded agent JSONs (verbatim from the 6 sphere-decider runs)
# ============================================================================

PEDAL_STRUCTURE = """
{"schema_version":"1.0","structure":{"total_bars":16,"sub_sections":[{"name":"pedal_locked","start_bar":0,"end_bar":8,"role":"loop"},{"name":"bII_tease","start_bar":8,"end_bar":16,"role":"drop"}],"breath_points":[15],"transition_in":"abrupt_full_band_entry_no_anticipation","transition_out":"abrupt_termination_mid_cycle"},"rationale":"16 bars in 8+8 punk-economy phrasing, drive max from bar 0, breath_point at bar 15 for the bII tease moment.","inspired_by":[{"song":"Nine_Inch_Nails/March_Of_The_Pigs","path":"stylistic_figures.transitions_between_sections","excerpt":"abrupt_full_band_entry_no_anticipation_device"},{"song":"Queens_Of_The_Stone_Age/Six_Shooter","path":"composition.phrase_symmetry","excerpt":"Symmetric short-phrase punk structure — 4-bar and 8-bar units"}],"confidence":0.82}
"""

PEDAL_HARMONY = """
{"schema_version":"1.0","harmony":{"mode":"Phrygian","key_root":"C","progression":["i","i","i","bII","i","i","i","bII","i","i","i","bII","i","i","i","bII"],"harmonic_rhythm":1.0,"voicing_strategy":"power chord on Cm (root + 5th, no 3rd) for 12 bars; Db (bII) voiced as chromatic_neighbor_pad with Db major triad over C pedal — Reznor false-relation. Db resolves by dropping back to Cm, no cadential motion away from tonic.","cadence_at_end":"open"},"rationale":"i-i-i-bII repeated 4 times across 16 bars at hr=1.0 encodes the pedal+tease pattern explicitly. 4-bar phrase preferred over 8+8 — at 128 BPM the bII return every 4 bars maintains the Phrygian pressure.","inspired_by":[{"song":"Nine_Inch_Nails/March_Of_The_Pigs","path":"composition.modal_choice","excerpt":"C# minor (Aeolian) with Phrygian-tinged inflections"},{"song":"Queens_Of_The_Stone_Age/Six_Shooter","path":"composition.harmonic_motion","excerpt":"Minor-modal with chromatic punk-style riff motion"}],"confidence":0.91}
"""

LOCK_STRUCTURE = """
{"schema_version":"1.0","structure":{"total_bars":16,"sub_sections":[{"name":"lock_A","start_bar":0,"end_bar":12,"role":"drive"},{"name":"dropout","start_bar":12,"end_bar":13,"role":"drop"},{"name":"slam_back","start_bar":13,"end_bar":16,"role":"build"}],"breath_points":[11],"transition_in":"full_band_slam_on_bar_0_no_intro","transition_out":"compact_lock_cut"},"rationale":"lock_A 0-12 = sustained drive industrial (THTF 16-bar verse template); dropout 12-13 = JCP-style guitar_dropout_micro_breakdown without dynamic collapse; slam_back 13-16 = THTF live_drum_kit_smash_entry. Breath at bar 11 for last-phrase resolution before the drop.","inspired_by":[{"song":"Nine_Inch_Nails/The_Hand_That_Feeds","path":"composition.section_count_and_lengths","excerpt":"verses: ~16 bars each at 122-128 BPM"},{"song":"Soundgarden/Jesus_Christ_Pose","path":"stylistic_figures.drops_and_breakdowns","excerpt":"rhythm_sparsen_for_a_few_bars — drums and bass continue, guitar drops out before slamming back in"}],"confidence":0.91}
"""

LOCK_HARMONY = """
{"schema_version":"1.0","harmony":{"mode":"Aeolian","key_root":"C","progression":["i","bVI","bVII","i","i","bVI","bVII","i","i","bVI","bVII","i","i","bVI","bVII","i"],"harmonic_rhythm":1.0,"voicing_strategy":"power chord (root + 5th) on i and bVII; drop_2 voicing on bVI (Ab) for spread; sus4 substitution on bar 12 (i replaced by Csus4) for pre-dropout tension.","cadence_at_end":"open"},"rationale":"C Aeolian — i-bVI-bVII-i is canonical Aeolian, all 3 refs converge on Aeolian (THTF B minor, Wretched G minor, JCP D minor). Cycle 4 times = 16 chord events. sus4 at bar 12 = pre-dropout tension device (THTF suspended voicings).","inspired_by":[{"song":"Nine_Inch_Nails/The_Wretched","path":"composition.modal_choice","excerpt":"G minor (Aeolian) with chromatic verse inflections"},{"song":"Soundgarden/Jesus_Christ_Pose","path":"composition.harmonic_motion","excerpt":"drop D power chord movements emphasizing low D root with movements to bVII"}],"confidence":0.93}
"""

DRIVE_STRUCTURE = """
{"schema_version":"1.0","structure":{"total_bars":16,"sub_sections":[{"name":"engine_lock","start_bar":0,"end_bar":4,"role":"drive"},{"name":"push_1","start_bar":4,"end_bar":8,"role":"drive"},{"name":"push_2","start_bar":8,"end_bar":12,"role":"drive"},{"name":"push_3","start_bar":12,"end_bar":16,"role":"drive"}],"breath_points":[],"transition_in":"abrupt_full_band_entry_no_riser","transition_out":"compact_lock_cut"},"rationale":"16 bars in 4 four-bar pushes (HBFS / THTF model). Each push thickens via additive layer without ever cutting propulsion. Zero breath_points by brief constraint.","inspired_by":[{"song":"Nine_Inch_Nails/The_Hand_That_Feeds","path":"composition.phrase_symmetry","excerpt":"Symmetric 4-bar and 8-bar phrasing throughout. Sustained intensity — no extended quiet sections"},{"song":"Daft_Punk/Harder_Better_Faster_Stronger","path":"stylistic_figures.risers_and_builds","excerpt":"additive_synth_layer_lift — additional synth pad/lead enters above the sample to thicken the harmonic field"}],"confidence":0.88}
"""

DRIVE_HARMONY = """
{"schema_version":"1.0","harmony":{"mode":"Phrygian","key_root":"C","progression":["i","bII","bVII","i","i","bII","bVII","i","i","bII","bVII","i","i","bII","bVII","i"],"harmonic_rhythm":1.0,"voicing_strategy":"i (Cm) power chord distorted; bII (Db) chromatic_neighbor_pad (b3 held in upper voice for permanent b2 dissonance); bVII (Bb) open_fifth_dyad spread wide in low register (no third) before return to i.","cadence_at_end":"open"},"rationale":"C Phrygien from the bank brief. i-bII-bVII-i × 4 cycles = 16 events at hr=1.0. Open cadence on i return — section relaunches without resolution.","inspired_by":[{"song":"Nine_Inch_Nails/Copy_Of_A","path":"composition.modal_choice","excerpt":"C minor with chromatic ornamentation. Modal stability over filter-modulated patterns"},{"song":"Daft_Punk/Harder_Better_Faster_Stronger","path":"composition.harmonic_motion","excerpt":"loop a small chord set i-bVII-bVI-v. Non-functional in dance-music sense"}],"confidence":0.92}
"""

TEASE_STRUCTURE = """
{"schema_version":"1.0","structure":{"total_bars":16,"sub_sections":[{"name":"drive_carry","start_bar":0,"end_bar":12,"role":"loop"},{"name":"venom","start_bar":12,"end_bar":16,"role":"build"}],"breath_points":[15],"transition_in":"full_band_slam_at_downbeat_zero","transition_out":"riff_punch_re_engagement"},"rationale":"16 bars in 12+4 — drive carry from Drive's intensity, then venom (max-3 lands hardest in last 4 bars). Single breath at bar 15 to not break EP momentum.","inspired_by":[{"song":"Nine_Inch_Nails/Were_In_This_Together","path":"composition.section_count_and_lengths","excerpt":"Each chorus approximately 16 bars; multiple iterations across runtime"},{"song":"Soundgarden/Jesus_Christ_Pose","path":"stylistic_figures.transitions_between_sections","excerpt":"section_change_via_riff_pattern_only_no_dynamic_event"},{"song":"Smashing_Pumpkins/Bodies","path":"composition.structural_blueprint","excerpt":"fast_riff_opening_full_band_immediate"}],"confidence":0.88}
"""

TEASE_HARMONY = """
{"schema_version":"1.0","harmony":{"mode":"Phrygian dominant","key_root":"C","progression":["I","I","bII","I","I","I","bII","I","I","bII","I","I","bII","I","bII","I"],"harmonic_rhythm":1.0,"voicing_strategy":"I_dominant7_no5 (root C + maj3 E + b7 Bb — venom voicing, no 5th, lets the maj3-vs-b7 tritone snap) on every I bar; bII (Db) as power chord root+5th in mid register, no 3rd; bII appearances densify toward end of section (bars 3, 7, 10, 13, 15) for tension acceleration without losing tonic gravity.","cadence_at_end":"open"},"rationale":"C Phrygien Dominant — same root C as Pedal/Lock/Drive but with raised maj-3 (E natural) creating snake-charmer venom. Familiar I-bII shape but with tierce relevée — listener hears 'lumière inattendue dans un geste connu'. bII densifies toward end (5 occurrences in 16 bars, accelerating) for tension build into the venom sub-section. Cadence ouverte sur I dominant — tritone E/Bb left in suspension, not resolved.","inspired_by":[{"song":"Nine_Inch_Nails/Were_In_This_Together","path":"composition.harmonic_motion","excerpt":"dark chromatic chord shifts (small chromatic neighbor moves rather than functional V-I cadences)"},{"song":"Soundgarden/Jesus_Christ_Pose","path":"composition.harmonic_motion","excerpt":"The chord cycle stays minimal — drop D power chord movements emphasizing low D root with occasional movements to bVII. Harmonic content subordinate to RHYTHMIC identity"}],"confidence":0.91}
"""

BRIDGE_STRUCTURE = """
{"schema_version":"1.0","structure":{"total_bars":16,"sub_sections":[{"name":"broken_groove","start_bar":0,"end_bar":12,"role":"loop"},{"name":"stop_time","start_bar":12,"end_bar":13,"role":"drop"},{"name":"final_push","start_bar":13,"end_bar":16,"role":"build"}],"breath_points":[12],"transition_in":"abrupt_full_band_entry_no_riser","transition_out":"abrupt_termination_mid_cycle"},"rationale":"16 bars in 3 phases — broken groove (kick 0+2.5 + snare 1+3.5 displaced + Amen-style ghosted hats) for 12 bars, 1-bar stop_time freeze at 12, 3-bar final_push, then abrupt cut (March_Of_The_Pigs ending model). EP closer.","inspired_by":[{"song":"Nine_Inch_Nails/March_Of_The_Pigs","path":"stylistic_figures.transitions_between_sections","excerpt":"abrupt_termination_mid_cycle — the song ENDS rather than concludes. No fade, no held note, no resolution"},{"song":"Nine_Inch_Nails/Copy_Of_A","path":"stylistic_figures.drops_and_breakdowns","excerpt":"no_drops_pattern_evolution_only — compositional motion is via pattern evolution + filter modulation throughout"},{"song":"Radiohead/The_National_Anthem","path":"composition.phrase_symmetry","excerpt":"Symmetric foundation + asymmetric overlay = the compositional engine"}],"confidence":0.88}
"""

BRIDGE_HARMONY = """
{"schema_version":"1.0","harmony":{"mode":"Phrygian","key_root":"C","progression":["i","bII","i","bvii°","i","bII","i","bvii°","i","bII","i","bvii°","i","bII","i","bvii°"],"harmonic_rhythm":1.0,"voicing_strategy":"power chord (root + 5th, no 3rd) on i — defeat Tease's bright maj-3rd by reasserting cold minor tonic; chromatic_neighbor_pad on bII (Db major Db-F-Ab held against C5 for max Phrygian rub); diminished triad on bvii° (Bb-Db-E enharmonic) — the section ends each cycle on bvii° as a COLLAPSE (no resolution). Bar 12 stop_time bar replaces bII with sus4 voicing (Db-Gb-Ab) — suspended breathing moment before final cycle.","cadence_at_end":"modal"},"rationale":"C Phrygien — return home after Tease's Phrygian Dominant. The i power chord (no 3rd) on opening defeats Tease's bright maj-3rd. bvii° (Bb diminished) as the closing chord of each cycle does not resolve — it COLLAPSES, functioning as punctuation. EP closer logic: bridge ends on bvii° rather than i to feel like an expiration, not a relaunch (March_Of_The_Pigs abrupt-termination model).","inspired_by":[{"song":"Nine_Inch_Nails/March_Of_The_Pigs","path":"composition.modal_choice","excerpt":"C# minor (Aeolian) with Phrygian-tinged inflections"},{"song":"Nine_Inch_Nails/Copy_Of_A","path":"composition.harmonic_motion","excerpt":"Chord shifts often expressed via filter-cutoff modulation — modal-static with texture as motion engine"},{"song":"Radiohead/The_National_Anthem","path":"composition.harmonic_pacing","excerpt":"Zero at the chord level (one mode for the entire track). Generated entirely by BRASS DENSITY"}],"confidence":0.91}
"""

PULSE_STRUCTURE = """
{"schema_version":"1.0","structure":{"total_bars":16,"sub_sections":[{"name":"dark_pulse_entry","start_bar":0,"end_bar":5,"role":"loop"},{"name":"accent_accumulation","start_bar":5,"end_bar":10,"role":"build"},{"name":"locrian_sink","start_bar":10,"end_bar":16,"role":"drop"}],"breath_points":[9],"transition_in":"abrupt_drum_entry_no_riser","transition_out":"loop_open_no_resolution"},"rationale":"5+5+6 asymmetric phrasing reflects Locrian's harmonic instability at the structural level — no symmetric phrase ever resolves, mirroring the b2/b5 that prevent tonic consonance. Inspired by Everything_In_Its_Right_Place's 10/4 'asymmetry as compositional payload' principle.","inspired_by":[{"song":"Radiohead/Everything_In_Its_Right_Place","path":"composition.phrase_symmetry","excerpt":"asymmetry is at the meter level (10/4 against expectations of 4/4), not at the phrase level"},{"song":"Nine_Inch_Nails/The_Day_The_World_Went_Away","path":"stylistic_figures.drops_and_breakdowns","excerpt":"TDTWWA has no drops — only gradual subtraction"},{"song":"Nine_Inch_Nails/Copy_Of_A","path":"composition.characteristic_riff_construction","excerpt":"Pattern is short (1-2 bar cycle), modular-synth, evolves via filter-cutoff and envelope changes"}],"confidence":0.88}
"""

PULSE_HARMONY = """
{"schema_version":"1.0","harmony":{"mode":"Locrian","key_root":"C","progression":["i°","i°","i°","i°","i°","i°","bII","i°","i°","i°","biii","i°","i°","i°","bII","i°"],"harmonic_rhythm":1.0,"voicing_strategy":"i° voiced as i_dim_no5 (C + Eb only — the b5 Gb is HIDDEN to create pseudo-stability, per sheet 11 Locrian recipe). bII (Db major) sustained as chromatic_neighbor_pad — chromatic rub against tonic. biii (Ebm = Eb + Gb + Bb) FORCES Gb (b5) into the voicing — this is the one bar of pure Locrian unrest at bar 11. Internal motion via filter-cutoff modulation, not chord changes (Copy_Of_A philosophy).","cadence_at_end":"open"},"rationale":"C Locrian — same root C as all other sections but the b5 (Gb) appears for the first time at bar 11 (biii voicing). 14 bars on i° pedal with i_dim_no5 voicing creates pseudo-stability that DEFIES Locrian's instability at the surface, with two brief bII intrusions (bars 7 and 15) and one full biii dissonance (bar 11) as the 'moment of pure Locrian unrest'. Cadence ouverte hands tension to Climb — Locrian refuses resolution by definition.","inspired_by":[{"song":"Nine_Inch_Nails/Copy_Of_A","path":"composition.harmonic_motion","excerpt":"Chord shifts often expressed via filter-cutoff modulation rather than via discrete chord changes"},{"song":"Radiohead/Everything_In_Its_Right_Place","path":"composition.harmonic_motion","excerpt":"Static modal with no functional progression. Tension-release happens textually — the b2 dissonance creates a constant chromatic rub against tonic"},{"song":"Nine_Inch_Nails/The_Day_The_World_Went_Away","path":"composition.harmonic_motion","excerpt":"Long pad sustains hold a chord for many bars before resolving slightly to a neighbor"}],"confidence":0.91}
"""

CLIMB_STRUCTURE = """
{"schema_version":"1.0","structure":{"total_bars":16,"sub_sections":[{"name":"slam_in","start_bar":0,"end_bar":4,"role":"build"},{"name":"lock_groove","start_bar":4,"end_bar":8,"role":"loop"},{"name":"layer_stack","start_bar":8,"end_bar":12,"role":"build"},{"name":"full_drive","start_bar":12,"end_bar":16,"role":"climax"}],"breath_points":[],"transition_in":"full_band_slam_downbeat_zero","transition_out":"abrupt_cut_or_loop_back_to_Pedal"},"rationale":"4×4 symmetric phrasing anchors listener after Pulse's Locrian instability. Slam at bar 0 (NIN/Six_Shooter), groove with ghost-kick variation at bars 4-8, additive layer stacking bars 8-12 (HBFS vocoder_phrase_stack model), max density bars 12-16. Zero breath_points — encore doesn't pause.","inspired_by":[{"song":"Nine_Inch_Nails/The_Hand_That_Feeds","path":"composition.phrase_symmetry","excerpt":"Symmetric 4-bar and 8-bar phrasing throughout. 16-bar verses, 16-bar choruses"},{"song":"Queens_Of_The_Stone_Age/Six_Shooter","path":"stylistic_figures.transitions_between_sections","excerpt":"abrupt_punk_style_ending — Track ENDS rather than concludes, abrupt cut on final beat, no fade"},{"song":"Daft_Punk/Harder_Better_Faster_Stronger","path":"stylistic_figures.risers_and_builds","excerpt":"vocoder_phrase_stack_as_riser — gradual accumulation, each bar adds a new layer"}],"confidence":0.91}
"""

CLIMB_HARMONY = """
{"schema_version":"1.0","harmony":{"mode":"Phrygian","key_root":"C","progression":["i","bVII","bVI","bII","i","bVII","bVI","bII","i","bVII","bVI","bII","i","bVII","bVI","bII"],"harmonic_rhythm":1.0,"voicing_strategy":"power chord (root + 5th) on i, descending chromatic motion through bVII (Bb power) and bVI (Ab drop_2 voicing for jazz spread), landing on bII (Db chromatic_neighbor_pad held against bass C pedal). Final 2 cycles add i_with_b9 voicing on i for climactic dissonance.","cadence_at_end":"modal"},"rationale":"C Phrygian — return home from Pulse's Locrian. Progression i→bVII→bVI→bII (Cm-Bb-Ab-Db) is a descending chromatic variant — DIFFERENT from Drive's i-bII-bVII-i (which moves up-down). Climb moves DOWN-DOWN-DOWN-DOWN-loop, creating a falling-spiral feel that builds tension via inevitability. Ends on bII as Phrygian fingerprint cadence: bII→i loop is the most Phrygian close possible (more characteristic than authentic V-i, which doesn't exist in Phrygian).","inspired_by":[{"song":"Daft_Punk/Harder_Better_Faster_Stronger","path":"composition.harmonic_motion","excerpt":"commonly read as i - bVII - bVI - v in the chosen minor or close variants. No V-i resolution"},{"song":"Nine_Inch_Nails/The_Hand_That_Feeds","path":"composition.characteristic_riff_construction","excerpt":"b-minor tonic with descending chromatic tail — chromatic descent is the song's identity"},{"song":"Queens_Of_The_Stone_Age/Six_Shooter","path":"composition.harmonic_motion","excerpt":"Tonic minor with movement to relative areas via chromatic chord shifts. Voice-leading punk-rock-craft"}],"confidence":0.88}
"""


# ============================================================================
# Section blueprints (built from the agent JSONs)
# ============================================================================


def assemble_blueprints() -> Tuple[SectionBlueprint, ...]:
    bp_pedal = (
        SectionBlueprint(
            name="Pedal",
            references=("Nine_Inch_Nails/March_Of_The_Pigs", "Queens_Of_The_Stone_Age/Six_Shooter"),
            brief="Acid Drops cible — 16 bars, C Phrygian, kick four-on-floor, pedal + bII tease",
        )
        .with_decision("structure", parse_structure_decision_from_response(PEDAL_STRUCTURE))
        .with_decision("harmony", parse_harmony_decision_from_response(PEDAL_HARMONY))
    )
    bp_lock = (
        SectionBlueprint(
            name="Lock",
            references=("Nine_Inch_Nails/The_Hand_That_Feeds",
                        "Soundgarden/Jesus_Christ_Pose",
                        "Nine_Inch_Nails/The_Wretched"),
            brief="Industrial classic — 16 bars, C Aeolian, kick variation step 11, dropout bar 12",
        )
        .with_decision("structure", parse_structure_decision_from_response(LOCK_STRUCTURE))
        .with_decision("harmony", parse_harmony_decision_from_response(LOCK_HARMONY))
    )
    bp_drive = (
        SectionBlueprint(
            name="Drive",
            references=("Nine_Inch_Nails/The_Hand_That_Feeds",
                        "Nine_Inch_Nails/Copy_Of_A",
                        "Daft_Punk/Harder_Better_Faster_Stronger"),
            brief="EBM driving — 16 bars, C Phrygian, kick 8ths, relentless propulsion",
        )
        .with_decision("structure", parse_structure_decision_from_response(DRIVE_STRUCTURE))
        .with_decision("harmony", parse_harmony_decision_from_response(DRIVE_HARMONY))
    )
    bp_tease = (
        SectionBlueprint(
            name="Tease",
            references=("Nine_Inch_Nails/Were_In_This_Together",
                        "Soundgarden/Jesus_Christ_Pose",
                        "Smashing_Pumpkins/Bodies"),
            brief="Phrygian dom dark — 16 bars, C Phrygian Dominant, venom voicing with maj-3 surprise",
        )
        .with_decision("structure", parse_structure_decision_from_response(TEASE_STRUCTURE))
        .with_decision("harmony", parse_harmony_decision_from_response(TEASE_HARMONY))
    )
    bp_bridge = (
        SectionBlueprint(
            name="Bridge",
            references=("Nine_Inch_Nails/March_Of_The_Pigs",
                        "Nine_Inch_Nails/Copy_Of_A",
                        "Radiohead/The_National_Anthem"),
            brief="Industrial breakbeat — 16 bars, C Phrygian, broken kick + displaced snare + ghost hats, EP closer",
        )
        .with_decision("structure", parse_structure_decision_from_response(BRIDGE_STRUCTURE))
        .with_decision("harmony", parse_harmony_decision_from_response(BRIDGE_HARMONY))
    )
    bp_pulse = (
        SectionBlueprint(
            name="Pulse",
            references=("Nine_Inch_Nails/Copy_Of_A",
                        "Nine_Inch_Nails/The_Day_The_World_Went_Away",
                        "Radiohead/Everything_In_Its_Right_Place"),
            brief="Dark techno minimal — 16 bars, C Locrian, kick 4x4 no snare, accent-driven groove, peak modal darkness",
        )
        .with_decision("structure", parse_structure_decision_from_response(PULSE_STRUCTURE))
        .with_decision("harmony", parse_harmony_decision_from_response(PULSE_HARMONY))
    )
    bp_climb = (
        SectionBlueprint(
            name="Climb",
            references=("Nine_Inch_Nails/The_Hand_That_Feeds",
                        "Queens_Of_The_Stone_Age/Six_Shooter",
                        "Daft_Punk/Harder_Better_Faster_Stronger"),
            brief="Industrial groovy — 16 bars, C Phrygian, ghost-kick variation, descending chromatic progression i-bVII-bVI-bII",
        )
        .with_decision("structure", parse_structure_decision_from_response(CLIMB_STRUCTURE))
        .with_decision("harmony", parse_harmony_decision_from_response(CLIMB_HARMONY))
    )
    return bp_pedal, bp_lock, bp_drive, bp_tease, bp_bridge, bp_pulse, bp_climb


# ============================================================================
# Banque MIDI patterns (transcribed verbatim from the xlsx)
# ============================================================================
#
# 16-step grid syntax (sheet 02_Rhythm_Patterns):
#   X = main hit (full velocity)
#   a = accent (slight bump)
#   g = ghost (very low velocity)
#   . = silence
# Each step is a 16th note. 16 steps = 4 beats = 1 bar at 4/4.

# --- PEDAL : Acid Drops cible profile ---
PEDAL_KICK   = "X...X...X...X..."   # four-on-floor (sheet 02 / profile 05)
PEDAL_HAT    = "..X...X...X...X."   # off-beat hats (Acid Drops hat)
PEDAL_SNARE  = "....g.......g..."   # subtle ghost on 2 and 4
# Acid Drops bass: 1, 1, b2, 1 across the 4-bar cycle
# In C Phrygian: 1=C, b2=Db. So bars 0/1/2 = C, bar 3 = Db.
PEDAL_BASS_DEGREES = ("1", "1", "1", "b2")  # one degree per bar

# --- LOCK : Industrial classic profile ---
LOCK_KICK    = "X...X...X.X.X..."   # variation step 11 (sheet 02 R21)
LOCK_HAT     = "X.X.X.X.X.X.X.X."   # 8ths droits
LOCK_SNARE   = "....X.......X..."   # backbeat saturé
LOCK_METAL   = "........X......."   # metal hit on step 9 (sheet 02 R24)
# NIN-style heavy bass: 1, 1, b6, b7 (Closer/Hurt style). In C Aeolian:
# 1=C, b6=Ab, b7=Bb. Cycle of 4 bars = C, C, Ab, Bb.
LOCK_BASS_DEGREES = ("1", "1", "b6", "b7")

# --- DRIVE : EBM driving profile ---
DRIVE_KICK   = "X.X.X.X.X.X.X.X."   # 8ths driving (sheet 02 R25)
DRIVE_HAT    = "..X...X...X...X."   # off-beat (sheet 02 R27)
DRIVE_SNARE  = "....X.......X..."   # backbeat droit
# EBM (DAF) bass: 1, 1, b2, 1, 5, 1, b3, 1 — 8 8th-notes per bar (1 bar cycle).
# In C Phrygian: 1=C, b2=Db, b3=Eb, 5=G. So per bar:
#   8th 1: C   2: C   3: Db  4: C   5: G   6: C   7: Eb  8: C
DRIVE_BASS_8THS = ("1", "1", "b2", "1", "5", "1", "b3", "1")

# --- TEASE : Phrygian dom dark profile (sheet 05 R14) ---
TEASE_KICK   = "X...X...X...X..."   # four-on-floor (Acid Drops kick)
TEASE_HAT    = "..X...X.a.X...X."   # dark techno hat with accent step 9 (sheet 02 R16)
TEASE_SNARE  = "....X.......X..."   # backbeat 1, 3
# Phrygian dom dark bass: 1, b2, 3, 1 (sheet 08 R11) - the major 3rd in bass.
# In C Phr Dom: 1=C, b2=Db, 3=E (NATURAL), 1=C
TEASE_BASS_DEGREES = ("1", "b2", "3", "1")  # one degree per bar in 4-bar cycle

# --- BRIDGE : Industrial breakbeat profile (sheet 05 R15) ---
# Kick "0, 2.5 (broken)" -> beats 0.0 and 2.5 -> steps 0 and 10
BRIDGE_KICK  = "X.........X....."
# Snare "1, 3.5 (off)" -> beats 1.0 and 3.5 -> steps 4 and 14
BRIDGE_SNARE = "....X.........X."
# Hat "breakbeat ghosted" - Amen-style 16ths (sheet 02 R33)
BRIDGE_HAT   = "X.X.X.XgX.X.X.X."

# --- PULSE : Dark techno minimal profile (sheet 05 R10) ---
PULSE_KICK         = "X...X...X...X..."   # 4-on-floor (per profile)
# No snare per profile — but we use industrial perc on step 9 for accent
PULSE_INDUSTRIAL   = "........X......."   # metal hit step 9 (sheet 02 R17)
# "off-beat + accents random" — two patterns alternating per bar for irregular feel
PULSE_HAT_BAR_EVEN = "..X.aX....X.aX.."   # off-beat with accents at steps 4 and 12
PULSE_HAT_BAR_ODD  = ".aX...X...X.aX.."   # accents at steps 1 and 12

# --- CLIMB : Industrial groovy profile (sheet 05 R6) ---
# Kick "0, 1, 2, 2.75, 3" -> beats 0, 1, 2, 2.75, 3 -> steps 0, 4, 8, 11, 12
# step 11 is the GHOST kick (low velocity), distinguishing it from Pedal's plain 4x4
CLIMB_KICK   = "X...X...X..gX..."
CLIMB_SNARE  = "....X.......X..."   # 1+3 backbeat
# 16ths denses (per profile R6) — full 16th-note hi-hat
CLIMB_HAT    = "XXXXXXXXXXXXXXXX"


# ============================================================================
# Pitch resolution (degree -> MIDI pitch)
# ============================================================================
#
# Degree-to-semitone offset from the root. We support both Phrygian and
# Aeolian palettes — both share most degrees.
#
#   Phrygian: 1=0, b2=1, b3=3, 4=5, 5=7, b6=8, b7=10
#   Aeolian:  1=0, 2=2, b3=3, 4=5, 5=7, b6=8, b7=10
#
# We use the same chord roots regardless of mode (the difference is in the
# 2nd which we don't use for bass roots). For the bII chord we use Db = +1.

DEGREE_SEMI: Dict[str, int] = {
    "1": 0, "b2": 1, "2": 2, "b3": 3, "3": 4, "4": 5, "b5": 6,
    "5": 7, "b6": 8, "6": 9, "b7": 10, "7": 11, "8": 12,
}


def degree_to_pitch(degree: str, root_pitch: int) -> int:
    return root_pitch + DEGREE_SEMI[degree]


# Chord root MIDI pitches (low octave for bass = C1 = 24)
ROOT_C1 = 24
ROOT_C2 = 36
ROOT_C3 = 48


# ============================================================================
# Pattern grid -> notes
# ============================================================================


def grid_to_drum_notes(
    grid: str, *,
    pitch: int,
    bar_offset_beats: float,
    velocity_main: int,
    velocity_ghost: int = 50,
    velocity_accent: int | None = None,
    note_dur: float = 0.20,
) -> List[Dict]:
    """Convert a 16-step grid to a list of note dicts in one bar.

    Char meanings: X=main, a=accent (or main+5), g=ghost, .=silent.
    """
    if velocity_accent is None:
        velocity_accent = min(127, velocity_main + 8)
    out: List[Dict] = []
    if len(grid) != 16:
        raise ValueError(f"grid must be 16 chars, got {len(grid)}: {grid!r}")
    for step, ch in enumerate(grid):
        if ch == ".":
            continue
        time = bar_offset_beats + step * 0.25  # 16th = 0.25 quarter-beat
        if ch == "X":
            vel = velocity_main
        elif ch == "a":
            vel = velocity_accent
        elif ch == "g":
            vel = velocity_ghost
        else:
            continue
        out.append({"time": time, "pitch": pitch, "duration": note_dur, "velocity": vel})
    return out


# ============================================================================
# Per-section per-role generators
# ============================================================================
#
# All sections are 16 bars, 4/4. Each generator returns notes whose times
# are SECTION-RELATIVE (bar 0 = beat 0 of the clip). The injection wraps
# them in a clip starting at beat 0 of that clip's track-position.

# --- PEDAL ----------------------------------------------------------------


def gen_pedal_drum() -> List[Dict]:
    out: List[Dict] = []
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        out.extend(grid_to_drum_notes(PEDAL_KICK, pitch=36, bar_offset_beats=b,
                                      velocity_main=115, note_dur=0.25))
        out.extend(grid_to_drum_notes(PEDAL_HAT, pitch=42, bar_offset_beats=b,
                                      velocity_main=95, note_dur=0.18))
        # subtle snare ghosts only on every other bar (per profile "snare subtil")
        if bar % 2 == 0:
            out.extend(grid_to_drum_notes(PEDAL_SNARE, pitch=38, bar_offset_beats=b,
                                          velocity_main=85, velocity_ghost=55,
                                          note_dur=0.12))
    return out


def gen_pedal_bass() -> List[Dict]:
    """4-bar cycle Acid Drops bass: 1, 1, 1, b2. Each bar = sustained
    root over 4 beats with a punch-attack on beat 1 and 3."""
    out: List[Dict] = []
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        degree = PEDAL_BASS_DEGREES[bar % 4]
        pitch = degree_to_pitch(degree, ROOT_C1)
        # Pulse 4-on-floor: hit on each quarter-beat (locked with kick)
        for beat in (0.0, 1.0, 2.0, 3.0):
            vel = 110 if beat == 0.0 else 100
            out.append({"time": b + beat, "pitch": pitch, "duration": 0.85, "velocity": vel})
    return out


def gen_pedal_lead() -> List[Dict]:
    """4-bar phrase repeated 4 times. Phrygian descent into bII tease.

    Bar 1 (i):  rest first 2 beats, Eb-Db-C 8ths on beats 3, 3.5, 4
    Bar 2 (i):  C sustained on beat 1, then Eb-Db on beats 3, 3.5
    Bar 3 (i):  rest -> Db-Db-Db rapid neighbor on the off-beats
                (the Phrygian 'wrongness' interval pinging)
    Bar 4 (bII):Db-C-Db-Eb on beats 1, 1.5, 2, 2.5; then Eb sustained
    """
    out: List[Dict] = []
    # E_b3 = 51, D_b3 = 50, C3 = 48 (high-mid riff register)
    Eb, Db, C, F = 51, 49, 48, 53
    for cycle in range(4):
        b = cycle * 4 * BEATS_PER_BAR
        # Bar 1
        out.append({"time": b + 2.0, "pitch": Eb, "duration": 0.45, "velocity": 95})
        out.append({"time": b + 2.5, "pitch": Db, "duration": 0.45, "velocity": 100})
        out.append({"time": b + 3.0, "pitch": C,  "duration": 0.95, "velocity": 105})
        # Bar 2
        out.append({"time": b + 4.0, "pitch": C,  "duration": 1.5,  "velocity": 90})
        out.append({"time": b + 6.0, "pitch": Eb, "duration": 0.45, "velocity": 92})
        out.append({"time": b + 6.5, "pitch": Db, "duration": 1.4,  "velocity": 95})
        # Bar 3 — Phrygian neighbor figure (Db pinging)
        for off in (8.5, 9.5, 10.5, 11.5):
            out.append({"time": b + off, "pitch": Db, "duration": 0.35, "velocity": 88})
        # Bar 4 — bII tease release
        out.append({"time": b + 12.0, "pitch": Db, "duration": 0.45, "velocity": 110})
        out.append({"time": b + 12.5, "pitch": C,  "duration": 0.45, "velocity": 100})
        out.append({"time": b + 13.0, "pitch": Db, "duration": 0.45, "velocity": 105})
        out.append({"time": b + 13.5, "pitch": Eb, "duration": 1.45, "velocity": 110})
    return out


def gen_pedal_pad() -> List[Dict]:
    """Sustained Cm power chord (C+G) for 3 bars, Db major triad chromatic
    neighbor pad on bar 4 of each 4-bar phrase. Voicing per agent decision."""
    out: List[Dict] = []
    for cycle in range(4):
        b = cycle * 4 * BEATS_PER_BAR
        # Bars 1-3: Cm power = C3 + G3 (48, 55)
        for bar_idx in range(3):
            t = b + bar_idx * BEATS_PER_BAR
            out.append({"time": t, "pitch": 48, "duration": float(BEATS_PER_BAR), "velocity": 75})
            out.append({"time": t, "pitch": 55, "duration": float(BEATS_PER_BAR), "velocity": 70})
        # Bar 4: Db major triad chromatic_neighbor_pad = Db + F + Ab (49, 53, 56)
        t = b + 3 * BEATS_PER_BAR
        for p in (49, 53, 56):
            out.append({"time": t, "pitch": p, "duration": float(BEATS_PER_BAR), "velocity": 80})
    return out


def gen_pedal_fx() -> List[Dict]:
    """Sub C drone (C0 = 12) sustained throughout the section."""
    return [{"time": 0.0, "pitch": 12, "duration": float(SECTION_BEATS), "velocity": 90}]


# --- LOCK -----------------------------------------------------------------


def gen_lock_drum() -> List[Dict]:
    out: List[Dict] = []
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        if bar == 12:
            # 1-bar dropout: drums silent except a single soft kick on beat 1
            out.append({"time": b, "pitch": 36, "duration": 0.5, "velocity": 60})
            continue
        # Lock kick variation step 11
        out.extend(grid_to_drum_notes(LOCK_KICK, pitch=36, bar_offset_beats=b,
                                      velocity_main=115, note_dur=0.22))
        # 8ths hat
        out.extend(grid_to_drum_notes(LOCK_HAT, pitch=42, bar_offset_beats=b,
                                      velocity_main=92, note_dur=0.18))
        # Snare backbeat saturé
        out.extend(grid_to_drum_notes(LOCK_SNARE, pitch=38, bar_offset_beats=b,
                                      velocity_main=110, note_dur=0.20))
        # Metal hit on step 9 every 2 bars (industrial accent)
        if bar % 2 == 0:
            out.extend(grid_to_drum_notes(LOCK_METAL, pitch=49, bar_offset_beats=b,
                                          velocity_main=120, note_dur=0.5))
    return out


def gen_lock_bass() -> List[Dict]:
    """NIN-style heavy bass: 1, 1, b6, b7 cycle (C C Ab Bb). Syncopated
    pattern '1 and "and of 3"' from sheet 08."""
    out: List[Dict] = []
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        if bar == 12:
            # Dropout — single soft note (cliff marker)
            out.append({"time": b, "pitch": ROOT_C1, "duration": 1.0, "velocity": 50})
            continue
        degree = LOCK_BASS_DEGREES[bar % 4]
        pitch = degree_to_pitch(degree, ROOT_C1)
        # NIN-style syncope on 1 and 'and of 3' (= beat 2.5)
        out.append({"time": b + 0.0, "pitch": pitch,    "duration": 1.45, "velocity": 110})
        out.append({"time": b + 2.5, "pitch": pitch,    "duration": 1.0,  "velocity": 100})
        # Octave punch on beat 4 for forward push
        out.append({"time": b + 3.5, "pitch": pitch + 12, "duration": 0.40, "velocity": 95})
    return out


def gen_lock_lead() -> List[Dict]:
    """4-bar phrase following i-bVI-bVII-i. Each bar has a melodic figure
    in the chord's arpeggio. Bar 12 (the dropout) is silent."""
    out: List[Dict] = []
    # Chord arpeggios (low-mid register, lead carries the hook)
    # i (Cm):  C-Eb-G-Bb (48, 51, 55, 58)
    # bVI (Ab): Ab-C-Eb (44, 48, 51)  (descending)
    # bVII (Bb): Bb-D-F (46, 50, 53)
    PHRASES = {
        "i":   [(0.0, 48, 0.45, 105), (0.5, 51, 0.45, 100), (1.0, 55, 0.45, 105),
                (1.5, 58, 0.45, 110), (2.5, 55, 0.45, 95),  (3.0, 51, 0.95, 90)],
        "bVI": [(0.0, 56, 0.45, 105), (0.5, 51, 0.45, 100), (1.0, 48, 0.45, 95),
                (2.0, 51, 0.45, 95),  (2.5, 49, 0.45, 95),  (3.0, 48, 0.95, 90)],
        "bVII":[(0.0, 58, 0.45, 105), (0.5, 53, 0.45, 100), (1.0, 50, 0.45, 100),
                (2.0, 53, 0.45, 100), (2.5, 50, 0.45, 95),  (3.0, 46, 0.95, 90)],
        "i_close": [(0.0, 48, 0.45, 115), (1.0, 55, 0.45, 110), (2.0, 60, 0.95, 115)],
    }
    chord_seq = ["i", "bVI", "bVII", "i_close"]
    for cycle in range(4):
        b = cycle * 4 * BEATS_PER_BAR
        for bar_idx, chord in enumerate(chord_seq):
            if cycle == 3 and bar_idx == 0:
                # Skip bar 12 (dropout)
                continue
            t_bar = b + bar_idx * BEATS_PER_BAR
            for offset, pitch, dur, vel in PHRASES[chord]:
                out.append({"time": t_bar + offset, "pitch": pitch,
                            "duration": dur, "velocity": vel})
    return out


def gen_lock_pad() -> List[Dict]:
    """Per agent voicing: power chord on i and bVII, drop_2 on bVI, sus4 at
    bar 12 (Csus4 = C-F-G). Each pad note is bar-sustained."""
    out: List[Dict] = []
    # i (Cm)  power = C3 + G3      (48, 55)
    # bVI (Ab) drop_2 = Ab2 + Eb3 + Ab3 + C4 (44, 51, 56, 60)
    # bVII (Bb) power = Bb2 + F3   (46, 53)
    # Csus4 (bar 12) = C3 + F3 + G3 (48, 53, 55)
    voicings = [
        [48, 55],            # i
        [44, 51, 56, 60],    # bVI
        [46, 53],            # bVII
        [48, 55],            # i (close of cycle)
    ]
    for cycle in range(4):
        b = cycle * 4 * BEATS_PER_BAR
        for bar_idx in range(4):
            t_bar = b + bar_idx * BEATS_PER_BAR
            if cycle == 3 and bar_idx == 0:
                # Bar 12 = sus4 tension (override the i)
                voicing = [48, 53, 55]
                vel = 70
            else:
                voicing = voicings[bar_idx]
                vel = 75
            for p in voicing:
                out.append({"time": t_bar, "pitch": p,
                            "duration": float(BEATS_PER_BAR), "velocity": vel})
    return out


def gen_lock_fx() -> List[Dict]:
    """Sub C drone with a 'whoosh' marker at bar 12 dropout entry and a
    high stab at bar 13 (slam-back entry)."""
    out: List[Dict] = []
    out.append({"time": 0.0, "pitch": 12, "duration": float(SECTION_BEATS), "velocity": 85})
    # Dropout whoosh — a high noise fragment over the silence
    out.append({"time": 12 * BEATS_PER_BAR, "pitch": 84, "duration": float(BEATS_PER_BAR),
                "velocity": 70})
    # Slam-back stab at bar 13
    out.append({"time": 13 * BEATS_PER_BAR, "pitch": 60, "duration": 0.5, "velocity": 122})
    return out


# --- DRIVE ----------------------------------------------------------------


def gen_drive_drum() -> List[Dict]:
    out: List[Dict] = []
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        # 8ths driving kick — every 8th note
        out.extend(grid_to_drum_notes(DRIVE_KICK, pitch=36, bar_offset_beats=b,
                                      velocity_main=110, note_dur=0.18))
        # Off-beat hat
        out.extend(grid_to_drum_notes(DRIVE_HAT, pitch=42, bar_offset_beats=b,
                                      velocity_main=98, note_dur=0.18))
        # Snare backbeat
        out.extend(grid_to_drum_notes(DRIVE_SNARE, pitch=38, bar_offset_beats=b,
                                      velocity_main=108, note_dur=0.18))
        # Push every 4 bars (open hat on beat 4 of bar 4/8/12/16)
        if (bar + 1) % 4 == 0:
            out.append({"time": b + 3.5, "pitch": 46, "duration": 0.4, "velocity": 105})
    return out


def gen_drive_bass() -> List[Dict]:
    """EBM (DAF) bass: 1, 1, b2, 1, 5, 1, b3, 1 — 8 8th-notes per bar.
    The chord progression i-bII-bVII-i shifts the ROOT every bar; the
    8th-note pattern is then transposed to that root."""
    out: List[Dict] = []
    chord_roots_degrees = ("1", "b2", "b7", "1")  # one per bar in 4-bar cycle
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        chord_root_degree = chord_roots_degrees[bar % 4]
        chord_root_pitch = degree_to_pitch(chord_root_degree, ROOT_C1)
        # 8 8th-notes through DRIVE_BASS_8THS pattern, transposed to current root
        for i, deg in enumerate(DRIVE_BASS_8THS):
            offset_beats = i * 0.5
            # Each 8th-note cell uses the degree relative to chord_root_pitch
            pitch = chord_root_pitch + DEGREE_SEMI[deg]
            vel = 108 if i % 2 == 0 else 95
            out.append({"time": b + offset_beats, "pitch": pitch,
                        "duration": 0.45, "velocity": vel})
    return out


def gen_drive_lead() -> List[Dict]:
    """Relentless 8th-note arpeggio of root + 5 + octave per chord.
    The constancy IS the drive."""
    out: List[Dict] = []
    chord_roots_degrees = ("1", "b2", "b7", "1")
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        chord_root_degree = chord_roots_degrees[bar % 4]
        chord_root_pitch = degree_to_pitch(chord_root_degree, ROOT_C3)  # mid register
        # Alternate root, 5th, octave, 5th — 8 8th-notes
        cycle = [chord_root_pitch,
                 chord_root_pitch + 7,
                 chord_root_pitch + 12,
                 chord_root_pitch + 7]
        for i in range(8):
            t = b + i * 0.5
            pitch = cycle[i % 4]
            vel = 110 if i in (0, 4) else (95 if i % 2 == 0 else 88)
            out.append({"time": t, "pitch": pitch, "duration": 0.40, "velocity": vel})
    return out


def gen_drive_pad() -> List[Dict]:
    """Per agent: power chord on i, chromatic_neighbor_pad on bII (b3 in
    upper voice for permanent b2 dissonance), open_fifth_dyad spread
    wide on bVII."""
    out: List[Dict] = []
    chord_seq = ["i", "bII", "bVII", "i"]
    voicings = {
        "i":    [48, 55],                      # Cm power
        "bII":  [49, 53, 56, 51],              # Db + F + Ab + Eb (Eb = b3 of Cm = held b2 over Db)
        "bVII": [22, 41, 53],                  # Bb1 + F2 + F3 spread (open_fifth_dyad wide)
    }
    for cycle in range(4):
        b = cycle * 4 * BEATS_PER_BAR
        for bar_idx, chord in enumerate(chord_seq):
            t_bar = b + bar_idx * BEATS_PER_BAR
            for p in voicings[chord]:
                out.append({"time": t_bar, "pitch": p,
                            "duration": float(BEATS_PER_BAR), "velocity": 78})
    return out


def gen_drive_fx() -> List[Dict]:
    """Sub C drone + push hits every 4 bars (boom on push transitions)."""
    out: List[Dict] = []
    out.append({"time": 0.0, "pitch": 12, "duration": float(SECTION_BEATS), "velocity": 95})
    for bar in (0, 4, 8, 12):
        out.append({"time": bar * BEATS_PER_BAR, "pitch": 60,
                    "duration": 0.5, "velocity": 118})
    return out


# --- TEASE -----------------------------------------------------------------


def gen_tease_drum() -> List[Dict]:
    """Phrygian dom dark profile — 4x4 kick, hat off-beat with accent step 9,
    snare 1+3 backbeat. Velocity range 95-120 per bank R14."""
    out: List[Dict] = []
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        out.extend(grid_to_drum_notes(TEASE_KICK, pitch=36, bar_offset_beats=b,
                                      velocity_main=115, note_dur=0.25))
        out.extend(grid_to_drum_notes(TEASE_HAT, pitch=42, bar_offset_beats=b,
                                      velocity_main=92, velocity_accent=110,
                                      note_dur=0.18))
        out.extend(grid_to_drum_notes(TEASE_SNARE, pitch=38, bar_offset_beats=b,
                                      velocity_main=108, note_dur=0.20))
        # Venom sub-section (bars 12-15): add metal hit on beat 1 for emphasis
        if 12 <= bar < 16:
            out.append({"time": b, "pitch": 49, "duration": 0.5, "velocity": 122})
    return out


def gen_tease_bass() -> List[Dict]:
    """Phrygian dom dark bass: 1, b2, 3, 1 cycle (C Db E C). The major 3rd
    in the bass IS the venom signature. 4-on-floor pulse locked with kick."""
    out: List[Dict] = []
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        degree = TEASE_BASS_DEGREES[bar % 4]
        pitch = degree_to_pitch(degree, ROOT_C1)
        # Pulse on each quarter, with octave punch on beat 4 for forward motion
        for beat in (0.0, 1.0, 2.0):
            vel = 110 if beat == 0.0 else 100
            out.append({"time": b + beat, "pitch": pitch, "duration": 0.85, "velocity": vel})
        # Octave-up on beat 4 — the venom signature (especially on the bar 3 = E natural)
        out.append({"time": b + 3.0, "pitch": pitch + 12, "duration": 0.85, "velocity": 105})
    return out


def gen_tease_lead() -> List[Dict]:
    """Lead phrase emphasizing the maj-3rd (E natural) — the venom note.
    Phrase descends C-Bb-Ab-G (b7-b6-5 Phrygian dom palette) then climbs
    back via C-Db-E (the b2-maj3 snake-charmer interval). Repeats with
    variation, intensifying in venom sub-section."""
    out: List[Dict] = []
    # E_b3 = 51, but here we want E natural = 52! That IS the venom.
    # Palette: C=48, Db=49, E=52, F=53, G=55, Ab=56, Bb=58
    C, Db, E, F, G, Ab, Bb = 48, 49, 52, 53, 55, 56, 58
    # 4-bar phrase template (cycles 4 times, with intensification in cycle 4)
    for cycle in range(4):
        b = cycle * 4 * BEATS_PER_BAR
        # Bar 1: descending Bb-Ab-G figure (b7-b6-5)
        out.append({"time": b + 0.5, "pitch": Bb, "duration": 0.45, "velocity": 100})
        out.append({"time": b + 1.0, "pitch": Ab, "duration": 0.45, "velocity": 95})
        out.append({"time": b + 1.5, "pitch": G,  "duration": 0.95, "velocity": 105})
        # Bar 2: snake-charmer climb C-Db-E (root, b2, maj3 — THE venom interval)
        out.append({"time": b + 4.0, "pitch": C,  "duration": 0.45, "velocity": 105})
        out.append({"time": b + 4.5, "pitch": Db, "duration": 0.45, "velocity": 110})
        out.append({"time": b + 5.0, "pitch": E,  "duration": 1.5,  "velocity": 115})
        out.append({"time": b + 6.5, "pitch": E,  "duration": 1.45, "velocity": 110})
        # Bar 3: tense interval E-Bb (the tritone of the venom voicing)
        out.append({"time": b + 8.0,  "pitch": E,  "duration": 0.95, "velocity": 100})
        out.append({"time": b + 9.0,  "pitch": Bb, "duration": 0.45, "velocity": 100})
        out.append({"time": b + 10.0, "pitch": E,  "duration": 0.95, "velocity": 105})
        out.append({"time": b + 11.0, "pitch": Bb, "duration": 0.95, "velocity": 105})
        # Bar 4: resolution to C — but in cycle 3+ stay on E to push venom forward
        if cycle < 2:
            out.append({"time": b + 12.0, "pitch": C, "duration": 1.95, "velocity": 110})
            out.append({"time": b + 14.0, "pitch": E, "duration": 1.95, "velocity": 100})
        else:
            # Cycles 3+ (venom sub-section starts at bar 12) — climb by step
            for i, p in enumerate([C, Db, E, F, G, Ab, Bb, E + 12]):
                t = b + 12.0 + i * 0.5
                vel = 95 + i * 4
                out.append({"time": t, "pitch": p, "duration": 0.45, "velocity": min(125, vel)})
    return out


def gen_tease_pad() -> List[Dict]:
    """I_dominant7_no5 (C+E+Bb) on I bars — the venom voicing.
    Db power chord (Db+Ab) on bII bars."""
    out: List[Dict] = []
    # Tease progression: I-I-bII-I-I-I-bII-I-I-bII-I-I-bII-I-bII-I
    # bII at bars 2, 6, 9, 12, 14
    bII_bars = {2, 6, 9, 12, 14}
    # Voicings
    I_venom = [48, 52, 58]       # C + E + Bb (no 5th)
    bII_power = [49, 56]         # Db + Ab
    for bar in range(BARS_PER_SECTION):
        t = bar * BEATS_PER_BAR
        voicing = bII_power if bar in bII_bars else I_venom
        for p in voicing:
            out.append({"time": t, "pitch": p,
                        "duration": float(BEATS_PER_BAR), "velocity": 78})
    return out


def gen_tease_fx() -> List[Dict]:
    """Sub C drone + cyber-desert metal sweep at venom entry bar 12."""
    out: List[Dict] = []
    out.append({"time": 0.0, "pitch": 12, "duration": float(SECTION_BEATS), "velocity": 90})
    # Venom entry: high E natural stab at bar 12 (the maj-3 spotlit)
    out.append({"time": 12 * BEATS_PER_BAR, "pitch": 76,
                "duration": float(BEATS_PER_BAR * 4), "velocity": 110})
    # Final accent at bar 15 (breath_point / venom peak)
    out.append({"time": 15 * BEATS_PER_BAR, "pitch": 64,
                "duration": 0.5, "velocity": 120})
    return out


# --- BRIDGE ----------------------------------------------------------------


def gen_bridge_drum() -> List[Dict]:
    """Industrial breakbeat — broken kick (1 + 'and of 3'), displaced
    snare (1 + 3.5 off), Amen-style ghost-dense hats. Bar 12 stop_time."""
    out: List[Dict] = []
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        if bar == 12:
            # Stop-time: drums silent except a held metal crash
            out.append({"time": b, "pitch": 49, "duration": float(BEATS_PER_BAR),
                        "velocity": 95})
            continue
        # Broken kick
        out.extend(grid_to_drum_notes(BRIDGE_KICK, pitch=36, bar_offset_beats=b,
                                      velocity_main=115, note_dur=0.22))
        # Displaced snare
        out.extend(grid_to_drum_notes(BRIDGE_SNARE, pitch=38, bar_offset_beats=b,
                                      velocity_main=108, note_dur=0.20))
        # Amen-ghost hat
        out.extend(grid_to_drum_notes(BRIDGE_HAT, pitch=42, bar_offset_beats=b,
                                      velocity_main=92, velocity_ghost=55,
                                      note_dur=0.15))
        # Final push (bars 13-15): add ride accents
        if bar >= 13:
            for off in (0.0, 1.0, 2.0, 3.0):
                out.append({"time": b + off, "pitch": 51, "duration": 0.4,
                            "velocity": 105})
    return out


def gen_bridge_bass() -> List[Dict]:
    """Bass follows broken kick syncopation: hit on beat 0 and 2.5 matching
    kick, with chromatic walk on beat 3.75 (push toward bar boundary).
    Chord progression i-bII-i-bvii° per bar dictates the root."""
    out: List[Dict] = []
    # i = C (1=0), bII = Db (b2=1), bvii° = Bb (b7=10) — root pitches
    chord_roots_offset = [0, 1, 0, 10]  # i, bII, i, bvii°
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        if bar == 12:
            # Stop-time: single low sustained root
            out.append({"time": b, "pitch": ROOT_C1, "duration": float(BEATS_PER_BAR),
                        "velocity": 60})
            continue
        offset = chord_roots_offset[bar % 4]
        root_pitch = ROOT_C1 + offset
        # Hit on beat 0 (with kick)
        out.append({"time": b + 0.0, "pitch": root_pitch, "duration": 1.5, "velocity": 110})
        # Hit on beat 2.5 (with kick "and of 3")
        out.append({"time": b + 2.5, "pitch": root_pitch, "duration": 0.85, "velocity": 100})
        # Chromatic walk approach on beat 3.5 (push to next bar)
        # Use a passing tone leading to next bar's root
        next_offset = chord_roots_offset[(bar + 1) % 4] if bar < 15 else 0
        # Approach by half-step from below
        approach_pitch = ROOT_C1 + next_offset - 1
        out.append({"time": b + 3.5, "pitch": approach_pitch, "duration": 0.40, "velocity": 95})
    return out


def gen_bridge_lead() -> List[Dict]:
    """Lead phrase tracking i-bII-i-bvii° progression. Each cycle:
    Bar 1 (Cm): C-Eb stab
    Bar 2 (Db): Db-F neighbor stab
    Bar 3 (Cm): C punch + Eb pull
    Bar 4 (Bb°): Bb-Db-E (the diminished triad — collapse note)
    Bar 12 stop_time = silent."""
    out: List[Dict] = []
    # Phrygian palette: C=48, Db=49, Eb=51, F=53, G=55, Ab=56, Bb=58
    # bvii° = Bb diminished = Bb-Db-E (E natural, since Bb° has b3 of Bb = Db, b5 of Bb = E)
    chord_phrases = [
        # Bar i (Cm): C-Eb-G stab figure
        [(0.0, 48, 0.45, 105), (0.5, 51, 0.45, 100), (1.5, 55, 0.95, 105),
         (2.5, 51, 0.45, 95),  (3.0, 48, 0.95, 90)],
        # Bar bII (Db): Db-F-Ab stab + pull
        [(0.0, 49, 0.45, 110), (0.5, 53, 0.45, 105), (1.0, 56, 0.45, 100),
         (2.0, 53, 0.45, 100), (2.5, 49, 1.45, 95)],
        # Bar i (Cm): tighter — C punch + Eb pull
        [(0.0, 48, 0.95, 108), (1.0, 51, 0.45, 100), (2.0, 48, 0.95, 105),
         (3.0, 51, 0.95, 95)],
        # Bar bvii° (Bb° = Bb-Db-E): the COLLAPSE — diminished triad arpeggio
        [(0.0, 58, 0.45, 100), (0.5, 49, 0.45, 100), (1.0, 52, 0.95, 105),
         (2.0, 58, 0.45, 95),  (2.5, 52, 0.45, 90),  (3.0, 49, 0.95, 85)],
    ]
    for cycle in range(4):
        for bar_idx, phrase in enumerate(chord_phrases):
            bar = cycle * 4 + bar_idx
            if bar == 12:
                # Stop-time bar — silent (lead drops out for the freeze)
                continue
            t_bar = bar * BEATS_PER_BAR
            for offset, pitch, dur, vel in phrase:
                out.append({"time": t_bar + offset, "pitch": pitch,
                            "duration": dur, "velocity": vel})
    return out


def gen_bridge_pad() -> List[Dict]:
    """Per agent voicing: power chord on i, chromatic_neighbor_pad on bII,
    diminished triad on bvii°. Bar 12 stop_time = sus4 voicing for
    suspended breath."""
    out: List[Dict] = []
    # i power chord = C3 + G3 (48, 55)
    # bII chromatic_neighbor = Db + F + Ab (49, 53, 56)
    # bvii° diminished = Bb + Db + E (46, 49, 52) — Bb2 + Db3 + E3
    # sus4 (bar 12) = Db + F# + Ab — actually use Db + Gb + Ab (Db sus4)
    chord_voicings = [
        [48, 55],            # i (Cm power)
        [49, 53, 56],        # bII (Db chromatic_neighbor_pad)
        [48, 55],            # i again
        [46, 49, 52],        # bvii° (Bb° diminished)
    ]
    sus4 = [49, 54, 56]      # Db sus4 = Db + Gb + Ab
    for bar in range(BARS_PER_SECTION):
        t = bar * BEATS_PER_BAR
        if bar == 12:
            voicing = sus4
            vel = 70
        else:
            voicing = chord_voicings[bar % 4]
            vel = 75
        for p in voicing:
            out.append({"time": t, "pitch": p,
                        "duration": float(BEATS_PER_BAR), "velocity": vel})
    return out


def gen_bridge_fx() -> List[Dict]:
    """Sub C drone (with stop_time gap at bar 12), reverse swell into
    bar 13 final_push, abrupt cut at end."""
    out: List[Dict] = []
    # Drone bars 0-11 (12 bars, 48 beats)
    out.append({"time": 0.0, "pitch": 12, "duration": 12.0 * BEATS_PER_BAR, "velocity": 88})
    # Stop-time silence at bar 12 = no drone
    # Reverse swell on bar 12 (high pitch building toward bar 13 entry)
    out.append({"time": 12 * BEATS_PER_BAR, "pitch": 84,
                "duration": float(BEATS_PER_BAR), "velocity": 60})
    # Final push (bars 13-15): drone resumes + push hits
    out.append({"time": 13 * BEATS_PER_BAR, "pitch": 12,
                "duration": 3.0 * BEATS_PER_BAR, "velocity": 95})
    for bar in (13, 14, 15):
        out.append({"time": bar * BEATS_PER_BAR, "pitch": 60,
                    "duration": 0.5, "velocity": 115})
    # Final cut accent on bar 15 last beat
    out.append({"time": 15 * BEATS_PER_BAR + 3.5, "pitch": 24,
                "duration": 0.5, "velocity": 125})
    return out


# --- PULSE -----------------------------------------------------------------


def gen_pulse_drum() -> List[Dict]:
    """Dark techno minimal — kick 4x4, NO snare (per profile), hat off-beat
    with random accents. Industrial metal hit on step 9 every other bar
    for accent-driven groove ('le groove vient des accents'). Velocity
    range 90-110 per bank R10."""
    out: List[Dict] = []
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        out.extend(grid_to_drum_notes(PULSE_KICK, pitch=36, bar_offset_beats=b,
                                      velocity_main=110, note_dur=0.25))
        # Alternating hat patterns for "random" accent feel
        hat_grid = PULSE_HAT_BAR_EVEN if bar % 2 == 0 else PULSE_HAT_BAR_ODD
        out.extend(grid_to_drum_notes(hat_grid, pitch=42, bar_offset_beats=b,
                                      velocity_main=88, velocity_accent=108,
                                      note_dur=0.16))
        # Industrial metal hit accent on step 9 every other bar (49 = crash)
        if bar % 2 == 1:
            out.extend(grid_to_drum_notes(PULSE_INDUSTRIAL, pitch=49, bar_offset_beats=b,
                                          velocity_main=105, note_dur=0.4))
    # Locrian sink (bars 10-15): add deeper metal hit on biii bar 10 + bII bar 14
    out.append({"time": 10 * BEATS_PER_BAR, "pitch": 56, "duration": float(BEATS_PER_BAR),
                "velocity": 115})  # cowbell-slot industrial deep hit
    out.append({"time": 14 * BEATS_PER_BAR, "pitch": 56, "duration": float(BEATS_PER_BAR),
                "velocity": 110})
    return out


def gen_pulse_bass() -> List[Dict]:
    """Drone-like bass emphasizing the Locrian b5 (Gb).
    Pattern per bar: root sustained on beat 0, b5 (Gb) on beat 2.5
    for the tritone tension. On bII bars (6, 14): bass walks to Db.
    On biii bar 10: bass goes to Eb (the b3 of Locrian, ground note of Ebm)."""
    out: List[Dict] = []
    # Locrian palette: 1=C(0), b2=Db(1), b3=Eb(3), 4=F(5), b5=Gb(6), b6=Ab(8), b7=Bb(10)
    GB = ROOT_C1 + 6   # b5 — the Locrian fingerprint
    DB = ROOT_C1 + 1   # b2
    EB = ROOT_C1 + 3   # b3 (root of biii)
    bII_bars = {6, 14}
    biii_bar = 10
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        if bar in bII_bars:
            # bII bar: bass on Db sustained
            out.append({"time": b + 0.0, "pitch": DB, "duration": 1.95, "velocity": 105})
            out.append({"time": b + 2.0, "pitch": DB, "duration": 1.95, "velocity": 95})
        elif bar == biii_bar:
            # biii bar: bass on Eb (forces the b3 into ground)
            out.append({"time": b + 0.0, "pitch": EB, "duration": 1.95, "velocity": 110})
            out.append({"time": b + 2.0, "pitch": GB, "duration": 1.95, "velocity": 105})
            # The Gb in the bass is the FULL Locrian moment — bar 10 unrest peak
        else:
            # i° bar: root C on beat 0, then b5 Gb on beat 2.5 (tritone tension)
            out.append({"time": b + 0.0, "pitch": ROOT_C1, "duration": 1.95, "velocity": 100})
            out.append({"time": b + 2.5, "pitch": GB, "duration": 0.85, "velocity": 90})
            out.append({"time": b + 3.5, "pitch": ROOT_C1, "duration": 0.40, "velocity": 95})
    return out


def gen_pulse_lead() -> List[Dict]:
    """Sparse lead — Locrian doesn't sustain melodic ideas. Phrase based on
    the b5 (Gb) and b2 (Db) — the destabilizing notes. Most of the section
    has minimal lead; the biii bar (10) has a longer phrase exposing Gb."""
    out: List[Dict] = []
    # Mid-register Locrian palette: C=48, Db=49, Eb=51, F=53, Gb=54, Ab=56, Bb=58
    C, Db, Eb, F, Gb, Ab, Bb = 48, 49, 51, 53, 54, 56, 58
    # Phrase template (4-bar cycles): minimal stab on beat 1, neighbor figure on bar 4
    for cycle in range(4):
        b = cycle * 4 * BEATS_PER_BAR
        # Bar 1: single stab on Eb (b3) — pseudo-stable
        out.append({"time": b + 0.0, "pitch": Eb, "duration": 1.5, "velocity": 95})
        # Bar 2: pause then C-Db neighbor (b2 chromatic rub)
        out.append({"time": b + 6.0, "pitch": C, "duration": 0.45, "velocity": 88})
        out.append({"time": b + 6.5, "pitch": Db, "duration": 1.45, "velocity": 92})
        # Bar 3: rest (silence sustains tension)
        # Bar 4: single Bb (b7) sustained
        out.append({"time": b + 12.0, "pitch": Bb, "duration": 1.95, "velocity": 90})
    # Bar 10 (biii — Locrian unrest peak): 4-note phrase exposing b5 Gb
    b10 = 10 * BEATS_PER_BAR
    out.append({"time": b10 + 0.0, "pitch": Eb, "duration": 0.95, "velocity": 105})
    out.append({"time": b10 + 1.0, "pitch": Gb, "duration": 0.95, "velocity": 115})  # b5!
    out.append({"time": b10 + 2.0, "pitch": Bb, "duration": 0.95, "velocity": 110})
    out.append({"time": b10 + 3.0, "pitch": Gb, "duration": 0.95, "velocity": 108})
    return out


def gen_pulse_pad() -> List[Dict]:
    """Per agent voicing: i_dim_no5 (C+Eb) on i° bars, chromatic_neighbor_pad
    Db major on bII bars, Ebm (Eb-Gb-Bb) on biii bar 10 (forces b5)."""
    out: List[Dict] = []
    # i_dim_no5 = C3 + Eb3 (48, 51)
    # bII (Db major chromatic_neighbor_pad) = Db3 + F3 + Ab3 (49, 53, 56)
    # biii (Ebm — forces b5 Gb) = Eb3 + Gb3 + Bb3 (51, 54, 58)
    i_dim_no5 = [48, 51]
    bII_pad   = [49, 53, 56]
    biii_pad  = [51, 54, 58]
    bII_bars = {6, 14}
    for bar in range(BARS_PER_SECTION):
        t = bar * BEATS_PER_BAR
        if bar in bII_bars:
            voicing, vel = bII_pad, 80
        elif bar == 10:
            voicing, vel = biii_pad, 88
        else:
            voicing, vel = i_dim_no5, 72
        for p in voicing:
            out.append({"time": t, "pitch": p,
                        "duration": float(BEATS_PER_BAR), "velocity": vel})
    return out


def gen_pulse_fx() -> List[Dict]:
    """Sub C drone + glitch hit at bar 10 (the Locrian unrest peak).
    Add a high stab at bar 9 (breath_point) marking the pivot."""
    out: List[Dict] = []
    out.append({"time": 0.0, "pitch": 12, "duration": float(SECTION_BEATS), "velocity": 85})
    # Breath_point bar 9 — a noise wash signaling the locrian_sink entry
    out.append({"time": 9 * BEATS_PER_BAR, "pitch": 80,
                "duration": 1.0, "velocity": 100})
    # Bar 10 unrest peak — high Gb stab (the full Locrian b5)
    out.append({"time": 10 * BEATS_PER_BAR, "pitch": 78,
                "duration": float(BEATS_PER_BAR), "velocity": 115})
    return out


# --- CLIMB -----------------------------------------------------------------


def gen_climb_drum() -> List[Dict]:
    """Industrial groovy — kick with ghost on 2.75, snare backbeat 1+3,
    hat 16ths denses. Velocity range 85-120 per bank R6."""
    out: List[Dict] = []
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        out.extend(grid_to_drum_notes(CLIMB_KICK, pitch=36, bar_offset_beats=b,
                                      velocity_main=115, velocity_ghost=70,
                                      note_dur=0.20))
        out.extend(grid_to_drum_notes(CLIMB_SNARE, pitch=38, bar_offset_beats=b,
                                      velocity_main=110, note_dur=0.20))
        # 16ths hat with subtle velocity variation (every 4th step accented)
        for step in range(16):
            t = b + step * 0.25
            vel = 105 if step % 4 == 0 else (90 if step % 2 == 0 else 78)
            out.append({"time": t, "pitch": 42, "duration": 0.12, "velocity": vel})
        # Layer_stack subsection (bars 8-11): add open hat on beat 4 for lift
        if 8 <= bar < 12:
            out.append({"time": b + 3.5, "pitch": 46, "duration": 0.4, "velocity": 105})
        # Full_drive subsection (bars 12-15): crash on beat 1 of every bar
        if bar >= 12:
            out.append({"time": b + 0.0, "pitch": 49, "duration": 0.5, "velocity": 122})
    return out


def gen_climb_bass() -> List[Dict]:
    """Bass follows descending progression i-bVII-bVI-bII (C-Bb-Ab-Db).
    Drives 8th-notes with the ghost-kick variation: hits on beat 0, 1, 2,
    2.75 (ghost), 3, plus push-octave on beat 3.5 toward next bar."""
    out: List[Dict] = []
    # Phrygian palette degrees for the 4-bar cycle:
    # i=C(0), bVII=Bb(10), bVI=Ab(8), bII=Db(1)
    chord_offsets = [0, 10, 8, 1]
    for bar in range(BARS_PER_SECTION):
        b = bar * BEATS_PER_BAR
        chord_offset = chord_offsets[bar % 4]
        root_pitch = ROOT_C1 + chord_offset
        # Hits matching the kick pattern
        for beat, dur, vel in [(0.0, 0.85, 110), (1.0, 0.85, 100),
                                (2.0, 0.65, 105), (2.75, 0.20, 75),  # ghost!
                                (3.0, 0.85, 110)]:
            out.append({"time": b + beat, "pitch": root_pitch,
                        "duration": dur, "velocity": vel})
        # Octave push on beat 3.5 toward next bar (drive forward)
        out.append({"time": b + 3.5, "pitch": root_pitch + 12,
                    "duration": 0.40, "velocity": 105})
    return out


def gen_climb_lead() -> List[Dict]:
    """Lead phrase tracking i-bVII-bVI-bII descending progression.
    Each chord gets a 1-bar stab figure with descending shape that
    matches the chord descent. Final cycle (bars 12-15) doubles density
    for full_drive climax."""
    out: List[Dict] = []
    # Chord arpeggios (high register for memorable hook)
    # i (Cm):     C-Eb-G   (60, 63, 67)
    # bVII (Bb):  Bb-D-F   (58, 62, 65)
    # bVI (Ab):   Ab-C-Eb  (56, 60, 63)
    # bII (Db):   Db-F-Ab  (61, 65, 68)
    PHRASES_NORMAL = [
        # i (Cm): root + b3 + 5 stab figure
        [(0.0, 60, 0.45, 105), (0.5, 63, 0.45, 100), (1.0, 67, 0.95, 105),
         (2.5, 63, 0.45, 95), (3.0, 60, 0.95, 95)],
        # bVII (Bb): descending figure
        [(0.0, 58, 0.45, 105), (0.5, 62, 0.45, 100), (1.0, 65, 0.45, 100),
         (2.0, 62, 0.45, 95), (2.5, 58, 0.95, 100), (3.5, 60, 0.40, 90)],
        # bVI (Ab): drop a third — descending continues
        [(0.0, 56, 0.45, 105), (0.5, 60, 0.45, 100), (1.0, 63, 0.95, 100),
         (2.5, 60, 0.45, 95), (3.0, 56, 0.95, 100)],
        # bII (Db): the Phrygian hook — Db neighbor figure, climbs to Ab
        [(0.0, 61, 0.45, 110), (0.5, 65, 0.45, 105), (1.0, 68, 0.45, 100),
         (2.0, 65, 0.45, 100), (2.5, 61, 0.45, 105), (3.0, 60, 0.95, 110)],
        # the trailing 60 (C) is the resolution to next i
    ]
    # Climactic phrases for final cycle (bars 12-15) — denser, higher
    PHRASES_CLIMAX = [
        # i: octave high — ascending
        [(0.0, 72, 0.45, 115), (0.5, 75, 0.45, 110), (1.0, 79, 0.45, 115),
         (1.5, 75, 0.45, 105), (2.0, 72, 0.45, 110), (2.5, 75, 0.45, 105),
         (3.0, 79, 0.95, 115)],
        # bVII: descending fast
        [(0.0, 70, 0.45, 115), (0.5, 74, 0.45, 110), (1.0, 77, 0.45, 110),
         (1.5, 74, 0.45, 105), (2.0, 70, 0.45, 110), (2.5, 67, 0.95, 105)],
        # bVI: descending continues
        [(0.0, 68, 0.45, 115), (0.5, 72, 0.45, 110), (1.0, 75, 0.45, 110),
         (1.5, 72, 0.45, 105), (2.0, 68, 0.45, 110), (2.5, 65, 0.95, 105)],
        # bII: final dissonance — Db climbing to F-Ab octave
        [(0.0, 73, 0.45, 120), (0.5, 77, 0.45, 115), (1.0, 80, 0.95, 115),
         (2.0, 77, 0.45, 115), (2.5, 73, 0.45, 115), (3.0, 72, 0.95, 122)],
    ]
    for cycle in range(4):
        b = cycle * 4 * BEATS_PER_BAR
        phrases = PHRASES_CLIMAX if cycle == 3 else PHRASES_NORMAL
        for bar_idx in range(4):
            t_bar = b + bar_idx * BEATS_PER_BAR
            for offset, pitch, dur, vel in phrases[bar_idx]:
                out.append({"time": t_bar + offset, "pitch": pitch,
                            "duration": dur, "velocity": vel})
    return out


def gen_climb_pad() -> List[Dict]:
    """Per agent voicing: power chord on i, drop_2 on bVI (jazz spread),
    chromatic_neighbor_pad on bII. Final cycle uses i_with_b9 for
    climactic dissonance."""
    out: List[Dict] = []
    # i power = C3 + G3 (48, 55)
    # bVII power = Bb2 + F3 (46, 53)
    # bVI drop_2 = Ab2 + Eb3 + Ab3 + C4 (44, 51, 56, 60)
    # bII chromatic_neighbor = Db3 + F3 + Ab3 (49, 53, 56)
    # i_with_b9 (Phrygian voicing) = C3 + Eb3 + G3 + Db4 (48, 51, 55, 61)
    voicings_normal = [
        [48, 55],            # i
        [46, 53],            # bVII
        [44, 51, 56, 60],    # bVI drop_2
        [49, 53, 56],        # bII chromatic_neighbor
    ]
    voicings_climax = [
        [48, 51, 55, 61],    # i_with_b9
        [46, 53, 58],        # bVII open
        [44, 51, 56, 60, 63],  # bVI drop_2 + 5
        [49, 53, 56, 60],    # bII + b9 high
    ]
    for cycle in range(4):
        b = cycle * 4 * BEATS_PER_BAR
        voicings = voicings_climax if cycle == 3 else voicings_normal
        for bar_idx in range(4):
            t_bar = b + bar_idx * BEATS_PER_BAR
            voicing = voicings[bar_idx]
            vel = 82 if cycle == 3 else 75
            for p in voicing:
                out.append({"time": t_bar, "pitch": p,
                            "duration": float(BEATS_PER_BAR), "velocity": vel})
    return out


def gen_climb_fx() -> List[Dict]:
    """Sub C drone + push hits at each layer_stack and full_drive boundary
    (bars 4, 8, 12). Final cathartic stab on bar 15 last beat."""
    out: List[Dict] = []
    out.append({"time": 0.0, "pitch": 12, "duration": float(SECTION_BEATS), "velocity": 95})
    for bar in (0, 4, 8, 12):
        out.append({"time": bar * BEATS_PER_BAR, "pitch": 60,
                    "duration": 0.5, "velocity": 118})
    # Final climax stab on last bar last beat
    out.append({"time": 15 * BEATS_PER_BAR + 3.0, "pitch": 72,
                "duration": 1.0, "velocity": 125})
    return out


# ============================================================================
# Section / role / generator dispatch table
# ============================================================================


SECTIONS = ("Pedal", "Lock", "Drive", "Tease", "Bridge", "Pulse", "Climb")

# Live color codes (0-69) — all sections share the same role-color mapping
ROLE_COLOR = {
    "DRUM_KIT": 2,    # red
    "BASS":    14,    # teal
    "LEAD":    25,    # purple
    "PAD":     19,    # light blue
    "FX":      38,    # gray
}

SECTION_COLOR = {
    "Pedal":  4,    # orange  — Acid Drops signature
    "Lock":  10,    # dark teal — industrial layered
    "Drive": 14,    # teal — relentless EBM
    "Tease": 25,    # purple — exotic venom
    "Bridge": 7,    # red — broken closer
    "Pulse": 22,    # dark gray — Locrian darkness peak
    "Climb": 41,    # gold — encore climax
}

# (section_name, role) -> generator function
GENERATORS: Dict[Tuple[str, str], callable] = {
    ("Pedal",  "DRUM_KIT"): gen_pedal_drum,
    ("Pedal",  "BASS"):     gen_pedal_bass,
    ("Pedal",  "LEAD"):     gen_pedal_lead,
    ("Pedal",  "PAD"):      gen_pedal_pad,
    ("Pedal",  "FX"):       gen_pedal_fx,
    ("Lock",   "DRUM_KIT"): gen_lock_drum,
    ("Lock",   "BASS"):     gen_lock_bass,
    ("Lock",   "LEAD"):     gen_lock_lead,
    ("Lock",   "PAD"):      gen_lock_pad,
    ("Lock",   "FX"):       gen_lock_fx,
    ("Drive",  "DRUM_KIT"): gen_drive_drum,
    ("Drive",  "BASS"):     gen_drive_bass,
    ("Drive",  "LEAD"):     gen_drive_lead,
    ("Drive",  "PAD"):      gen_drive_pad,
    ("Drive",  "FX"):       gen_drive_fx,
    ("Tease",  "DRUM_KIT"): gen_tease_drum,
    ("Tease",  "BASS"):     gen_tease_bass,
    ("Tease",  "LEAD"):     gen_tease_lead,
    ("Tease",  "PAD"):      gen_tease_pad,
    ("Tease",  "FX"):       gen_tease_fx,
    ("Bridge", "DRUM_KIT"): gen_bridge_drum,
    ("Bridge", "BASS"):     gen_bridge_bass,
    ("Bridge", "LEAD"):     gen_bridge_lead,
    ("Bridge", "PAD"):      gen_bridge_pad,
    ("Bridge", "FX"):       gen_bridge_fx,
    ("Pulse",  "DRUM_KIT"): gen_pulse_drum,
    ("Pulse",  "BASS"):     gen_pulse_bass,
    ("Pulse",  "LEAD"):     gen_pulse_lead,
    ("Pulse",  "PAD"):      gen_pulse_pad,
    ("Pulse",  "FX"):       gen_pulse_fx,
    ("Climb",  "DRUM_KIT"): gen_climb_drum,
    ("Climb",  "BASS"):     gen_climb_bass,
    ("Climb",  "LEAD"):     gen_climb_lead,
    ("Climb",  "PAD"):      gen_climb_pad,
    ("Climb",  "FX"):       gen_climb_fx,
}

ROLES = ("DRUM_KIT", "BASS", "LEAD", "PAD", "FX")


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    print(f"=== Qrust {N_SECTIONS}-sections build ===")

    # --- Phase 1: blueprints ---
    print(f"\n[1/4] Parse {2*N_SECTIONS} sphere-decider JSONs -> {N_SECTIONS} SectionBlueprints")
    blueprints = assemble_blueprints()
    for bp in blueprints:
        filled = bp.filled_spheres()
        print(f"  OK {bp.name:7s}: spheres={filled}, "
              f"key={bp.harmony.value.key_root} {bp.harmony.value.mode}")

    # --- Phase 2: cohesion ---
    print("\n[2/4] Cohesion checks")
    for bp in blueprints:
        report = check_cohesion(bp)
        if not report.is_clean:
            for v in report.blockers:
                print(f"  FAIL {bp.name} / {v.rule}: {v.message}")
            raise SystemExit(1)
        print(f"  OK {bp.name:7s}: clean")

    # --- Phase 3: generate notes per (section, role) ---
    print("\n[3/4] Generate notes per (section, role)")
    notes: Dict[Tuple[str, str], List[Dict]] = {}
    for sec in SECTIONS:
        for role in ROLES:
            notes[(sec, role)] = GENERATORS[(sec, role)]()
            print(f"  OK {sec:6s} / {role:9s} {len(notes[(sec, role)]):4d} notes")

    # --- Phase 4: build .als ---
    print(f"\n[4/4] Building {DST.name}")
    if SRC == DST:
        raise RuntimeError("Source and destination must differ")
    shutil.copy(SRC, DST)
    with gzip.open(DST, "rb") as f:
        xml = f.read().decode("utf-8")
    xml = _set_project_tempo(xml, PROJECT_TEMPO)
    print(f"  OK Project tempo set to {PROJECT_TEMPO} BPM")

    seed_match = re.search(r'<MidiTrack Id="12"[^>]*>.*?</MidiTrack>', xml, re.DOTALL)
    if not seed_match:
        raise RuntimeError("Seed MidiTrack Id=12 not found")
    seed_track = seed_match.group(0)

    new_tracks: List[str] = []
    clip_id = 1000
    for i, role in enumerate(ROLES):
        clips: List[str] = []
        for sec_idx, sec in enumerate(SECTIONS):
            sec_notes = notes[(sec, role)]
            if not sec_notes:
                continue
            clips.append(_build_midi_clip(
                clip_id=clip_id,
                start_beat=sec_idx * SECTION_BEATS,
                length_beat=SECTION_BEATS,
                name=f"{sec} [{role}]",
                color=SECTION_COLOR[sec],
                notes=sec_notes,
            ))
            clip_id += 1

        clone = _clone_midi_track(
            seed_track,
            new_track_id=300 + i,
            role=role,
            display_name=role.replace("_", " ").title(),
            color=ROLE_COLOR[role],
            id_offset=100_000 + i * 100_000,
            clips=clips,
        )
        new_tracks.append(clone)
        print(f"  OK Cloned [{role}] track Id={300+i} ({len(clips)} clips)")

    xml = _insert_tracks_after(xml, anchor_track_id=12, new_tracks=new_tracks)
    safe_npi = 100_000 + len(ROLES) * 100_000 + 100_000
    xml = _bump_next_pointee_id(xml, safe_npi)
    print(f"  OK Inserted {len(new_tracks)} tracks, NextPointeeId={safe_npi}")

    ET.fromstring(xml)
    print(f"  OK XML parses cleanly")

    with gzip.open(DST, "wb", compresslevel=9) as f:
        f.write(xml.encode("utf-8"))
    with gzip.open(DST, "rb") as f:
        head = f.read(80)
    if not head.startswith(b"<?xml"):
        raise RuntimeError(f"Post-write FAIL: head = {head[:30]!r}")
    print(f"  OK Post-write check: gunzip head = <?xml")
    print(f"  OK Final size: {DST.stat().st_size} bytes")
    print(f"\n=== DONE ===")
    print(f"Output: {DST}")
    print(f"Timeline: {N_SECTIONS} sections * {SECTION_BEATS} beats = {TOTAL_BEATS} beats total")


if __name__ == "__main__":
    main()
