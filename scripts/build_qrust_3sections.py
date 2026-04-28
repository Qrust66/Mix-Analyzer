"""Build Qrust_3Sections.als — 3 driving sections at 128 BPM in C, composed
via the multi-agent sphere agents PLUS the banque MIDI Qrust v2 patterns.

The bank (`ableton/banque_midi_qrust_v2.xlsx`) provides:
  - 12 calibrated profiles ("Acid Drops cible", "EBM driving", ...)
  - 16-step rhythm patterns per genre (kick / snare / hat)
  - bassline degree sequences per style (e.g. "1, 1, b2, 1")
  - per-style velocity ranges
  - chord progressions per mood

Sections (all 16 bars @ 128 BPM, root = C):

  1. PEDAL  — Acid Drops cible profile
       Mode: C Phrygian  |  Progression: i-i-i-bII × 4 (pédale + bII tease)
       Kick: X...X...X...X...  |  Bass: 1, 1, b2, 1 (C C Db C)
       Hats: off-beat (..X...X...X...X.)
       Vibe: dark industrial groovy, signature Qrust target sound.

  2. LOCK   — Industrial classic profile
       Mode: C Aeolian  |  Progression: i-bVI-bVII-i × 4
       Kick: X...X...X.X.X... (variation step 11)
       Bass: 1, 1, b6, b7 (C C Ab Bb — NIN-style heavy)
       1-bar dropout at bar 12 -> slam back at 13.
       Vibe: layered industrial with micro-breakdown.

  3. DRIVE  — EBM driving profile
       Mode: C Phrygian  |  Progression: i-bII-bVII-i × 4
       Kick: X.X.X.X.X.X.X.X. (8ths driving)
       Bass: 1, 1, b2, 1, 5, 1, b3, 1 (EBM mélodique driving 8ths)
       Vibe: relentless EBM forward propulsion, no breaks.

Timeline: Pedal beats 0-64, Lock 64-128, Drive 128-192. 192 beats total.

Sphere agents invoked: structure-decider + harmony-decider per section
(6 agent calls total). Rhythm/arrangement/dynamics come from the bank
profile mapping — the agents at Phase 2.6 are descriptive at those
spheres anyway, so the bank does the substantive work.

Note generators read the bank's 16-step grids and bassline degree
sequences directly — no improvising from scratch like build_pivot_demo.
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
DST = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Qrust_3Sections.als"

PROJECT_TEMPO = 128
BARS_PER_SECTION = 16
BEATS_PER_BAR = 4
SECTION_BEATS = BARS_PER_SECTION * BEATS_PER_BAR  # 64
TOTAL_BEATS = 3 * SECTION_BEATS  # 192


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


# ============================================================================
# Section blueprints (built from the agent JSONs)
# ============================================================================


def assemble_blueprints() -> Tuple[SectionBlueprint, SectionBlueprint, SectionBlueprint]:
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
    return bp_pedal, bp_lock, bp_drive


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


# ============================================================================
# Section / role / generator dispatch table
# ============================================================================


SECTIONS = ("Pedal", "Lock", "Drive")

# Live color codes (0-69) — all sections share the same role-color mapping
ROLE_COLOR = {
    "DRUM_KIT": 2,    # red
    "BASS":    14,    # teal
    "LEAD":    25,    # purple
    "PAD":     19,    # light blue
    "FX":      38,    # gray
}

SECTION_COLOR = {
    "Pedal": 4,    # orange
    "Lock":  10,   # dark
    "Drive": 14,   # teal
}

# (section_name, role) -> generator function
GENERATORS: Dict[Tuple[str, str], callable] = {
    ("Pedal", "DRUM_KIT"): gen_pedal_drum,
    ("Pedal", "BASS"):     gen_pedal_bass,
    ("Pedal", "LEAD"):     gen_pedal_lead,
    ("Pedal", "PAD"):      gen_pedal_pad,
    ("Pedal", "FX"):       gen_pedal_fx,
    ("Lock",  "DRUM_KIT"): gen_lock_drum,
    ("Lock",  "BASS"):     gen_lock_bass,
    ("Lock",  "LEAD"):     gen_lock_lead,
    ("Lock",  "PAD"):      gen_lock_pad,
    ("Lock",  "FX"):       gen_lock_fx,
    ("Drive", "DRUM_KIT"): gen_drive_drum,
    ("Drive", "BASS"):     gen_drive_bass,
    ("Drive", "LEAD"):     gen_drive_lead,
    ("Drive", "PAD"):      gen_drive_pad,
    ("Drive", "FX"):       gen_drive_fx,
}

ROLES = ("DRUM_KIT", "BASS", "LEAD", "PAD", "FX")


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    print("=== Qrust 3-sections build ===")

    # --- Phase 1: blueprints ---
    print("\n[1/4] Parse 6 sphere-decider JSONs -> 3 SectionBlueprints")
    bp_pedal, bp_lock, bp_drive = assemble_blueprints()
    for bp in (bp_pedal, bp_lock, bp_drive):
        filled = bp.filled_spheres()
        print(f"  OK {bp.name}: spheres={filled}, "
              f"key={bp.harmony.value.key_root} {bp.harmony.value.mode}")

    # --- Phase 2: cohesion ---
    print("\n[2/4] Cohesion checks")
    for bp in (bp_pedal, bp_lock, bp_drive):
        report = check_cohesion(bp)
        if not report.is_clean:
            for v in report.blockers:
                print(f"  FAIL {bp.name} / {v.rule}: {v.message}")
            raise SystemExit(1)
        print(f"  OK {bp.name}: clean")

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
    print(f"Timeline: 3 sections * {SECTION_BEATS} beats = {TOTAL_BEATS} beats total")


if __name__ == "__main__":
    main()
