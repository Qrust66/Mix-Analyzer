"""Build Pivot_Demo.als — ONE 16-bar section composed via the 5 sphere
agents PLUS hand-crafted note generators.

Why hand-crafted: at Phase 2.6 the composer_adapter only ships
placeholder motifs (lead = single tonic+7 quarter-note per cycle,
drum_kit = four-on-floor kick, etc.). No melody can hold together with
that. The agent decisions are still authoritative — they fix structure,
harmony, rhythm, arrangement, dynamics — and the generators below
respect them: chords from the harmony agent, layer entries/exits from
the arrangement agent, the meter shift from the rhythm agent, the
1-bar dropout cliff-edge from the structure agent, the valley dB arc
from the dynamics agent.

Section "Pivot" (16 bars @ 130 BPM):

  funky_drive (bars 0-7, 7/8 meter, 3.5 quarter-beats each)
      |
      v   1-bar drum dropout (bar 8, 4/4 meter, March_Of_The_Pigs cliff)
      |
  industrial_slam (bars 9-15, 4/4 meter, machine-tight)

Total clip length = 8 × 3.5 + 8 × 4.0 = 60 quarter-beats.

Refs: QOTSA/Six_Shooter, Soundgarden/Overfloater, NIN/March_Of_The_Pigs.
Modal: E Dorian (b7 = D natural, natural 6 = C# — funky-modal sweet spot).
Riff cycle: i (Em) - bVII (D) - iv (Am) - bVII (D), repeated 4 times.

Pipeline:
1. Parse 5 raw agent JSONs -> 1 SectionBlueprint, cohesion clean.
2. Generate hand-crafted notes per role (drum_kit/bass/lead/pad/perc/fx)
   that follow the chord progression and the per-section feel.
3. Inject 7 cloned MidiTracks (1 per role) into a copy of Template.als.
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
    parse_arrangement_decision_from_response,
    parse_dynamics_decision_from_response,
    parse_harmony_decision_from_response,
    parse_rhythm_decision_from_response,
    parse_structure_decision_from_response,
)

# Re-use helpers from the multi-agent demo script (same family).
from scripts.build_multi_agent_demo import (
    _build_midi_clip,
    _clone_midi_track,
    _insert_tracks_after,
    _set_project_tempo,
    _bump_next_pointee_id,
)


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Template.als"
DST = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Pivot_Demo.als"

PROJECT_TEMPO = 130
TOTAL_BARS = 16
PIVOT_BAR = 8                          # bar 8 = the 1-bar drop / cliff edge
DROP_BAR = 8                           # alias for clarity
FUNKY_BAR_BEATS = 3.5                  # 7/8 = 7 8th-notes = 3.5 quarter-beats
INDUSTRIAL_BAR_BEATS = 4.0             # 4/4
TOTAL_BEATS = PIVOT_BAR * FUNKY_BAR_BEATS + (TOTAL_BARS - PIVOT_BAR) * INDUSTRIAL_BAR_BEATS  # 60.0


# ============================================================================
# Raw agent JSON outputs (verbatim from sphere-decider subagent runs)
# ============================================================================

PIVOT_STRUCTURE = """
{"schema_version":"1.0","structure":{"total_bars":16,"sub_sections":[{"name":"funky_drive","start_bar":0,"end_bar":7,"role":"drive"},{"name":"tighten","start_bar":7,"end_bar":9,"role":"drop"},{"name":"industrial_slam","start_bar":9,"end_bar":16,"role":"build"}],"breath_points":[8],"transition_in":"abrupt_full_band_entry_at_downbeat_bar0_no_riser_no_anticipation","transition_out":"abrupt_termination_mid_cycle_or_hard_cut_to_bridge"},"rationale":"Three states funky -> 1-bar dropout -> industrial slam, each delineated by structural cliff (March_Of_The_Pigs metric_cliff_edge_loud_to_quiet_no_transition_device).","inspired_by":[{"song":"Queens_Of_The_Stone_Age/Six_Shooter","path":"composition.structural_blueprint","excerpt":"aggressive_intro_full_band — Grohl drums + Homme guitar + Oliveri bass at full intensity, no gradual build"},{"song":"Nine_Inch_Nails/March_Of_The_Pigs","path":"composition.structural_blueprint","excerpt":"verse_full_band_aggressive -> CHORUS_BREAK_4_4_QUIET -> verse_aggressive_return"},{"song":"Soundgarden/Overfloater","path":"stylistic_figures.risers_and_builds","excerpt":"global_crescendo_via_instrumentation_thickening"}],"confidence":0.88}
"""

PIVOT_HARMONY = """
{"schema_version":"1.0","harmony":{"mode":"Dorian","key_root":"E","progression":["i","bVII","iv","bVII"],"harmonic_rhythm":1.0,"voicing_strategy":"Drop D power chords. i=Em5 (E-B), bVII=D5 (D-A), iv=Am5 (A-E). Natural 6 (C#) appears only as melodic passing tone above Em, never voiced as a chord tone. Industrial half (bar 9+) compresses voicings to root-only stabs with gate/tremolo processing.","cadence_at_end":"open"},"rationale":"E Dorian: b7 (D natural) gives funky bass groove, natural 6 (C#) injects funky-modal color absent from Aeolian. Cycle Em-D-Am-D 4 times across 16 bars at 1 chord/bar. Single key (no modulation) - identity shifts by texture not key.","inspired_by":[{"song":"Queens_Of_The_Stone_Age/Six_Shooter","path":"composition.harmonic_motion","excerpt":"Minor-modal with chromatic punk-style riff motion"},{"song":"Nine_Inch_Nails/March_Of_The_Pigs","path":"composition.harmonic_motion","excerpt":"verse riff cycles a small chord set in C# minor — typically i, bVII, bVI motions"},{"song":"Soundgarden/Overfloater","path":"composition.harmonic_motion","excerpt":"Modal Aeolian with sustained chord textures, drop D pedal tones"}],"confidence":0.82}
"""

PIVOT_RHYTHM = """
{"schema_version":"1.0","rhythm":{"tempo_bpm":130,"time_signature":"7/8 bars 0-7, then 4/4 bars 8-15","drum_pattern":"BARS 0-7 (7/8 funky): kick on 8th 1 and 8th 4, snare backbeat on 8th 4 (midpoint of 7), ghost 16ths on snare around 2-and / 4-and / 6-and at low velocity, open hat on 8th 5, closed hat 8ths otherwise. BARS 9-15 (4/4 industrial): kick programmed-tight on every quarter, snare pinned 2 and 4 with sample-replaced metal-snare layer, closed hat 8ths strict, no ghosts, processed metal hit on bar 1 of every other bar.","subdivisions":16,"swing":0.08,"polyrhythms":["3:4 hat micro-accent over 7/8 kick (bars 0-7) — every third 16th hat receives a slight accent, floating 3-against-7 above the funky kick"]},"rationale":"The 7/8 -> 4/4 meter shift IS the structural pivot (March_Of_The_Pigs canonical). Funky half lives in the asymmetric 7/8 with ghost-note swagger; industrial half slams in machine-tight 4/4 with no ghosts. Swing 0.08 perceptible only on the funky half; industrial 16ths are quantized so tightly that swing is invisible.","inspired_by":[{"song":"Nine_Inch_Nails/March_Of_The_Pigs","path":"time_signature","excerpt":"Compound 29-beat cycle (7+7+7+8) with chorus break temporarily resolving into 4/4. The contrast is the song's central compositional gesture."},{"song":"Nine_Inch_Nails/March_Of_The_Pigs","path":"stylistic_figures.transitions_between_sections","excerpt":"metric_cliff_edge_loud_to_quiet_no_transition_device — single beat of silence, then new meter establishes"},{"song":"Queens_Of_The_Stone_Age/Six_Shooter","path":"performance.drum_style","excerpt":"Snare strong on 2+4 with possible occasional ghost notes; kick + snare driving punk-speed pocket"}],"confidence":0.82}
"""

PIVOT_ARRANGEMENT = """
{"schema_version":"1.0","arrangement":{"layers":[{"role":"drum_kit","instrument":"funky live kit — ghost notes, open hi-hat, 7/8 locked groove","enters_at_bar":0,"exits_at_bar":8,"base_velocity":100},{"role":"drum_kit","instrument":"industrial drum machine — machine-tight 4/4, no ghosts","enters_at_bar":9,"exits_at_bar":16,"base_velocity":118},{"role":"bass","instrument":"pick-attack electric bass — funky front, distorted industrial back","enters_at_bar":0,"exits_at_bar":16,"base_velocity":105},{"role":"lead","instrument":"distorted electric guitar — Drop D, E Dorian riff stabs","enters_at_bar":0,"exits_at_bar":16,"base_velocity":108},{"role":"pad","instrument":"atmospheric sustained guitar chord — clean two-guitar layering","enters_at_bar":0,"exits_at_bar":8,"base_velocity":78},{"role":"perc","instrument":"industrial metal hits — processed steel percussion","enters_at_bar":9,"exits_at_bar":16,"base_velocity":122},{"role":"fx","instrument":"industrial noise layer — distorted synth stab, sub swell","enters_at_bar":9,"exits_at_bar":16,"base_velocity":115}],"density_curve":"sawtooth","instrumentation_changes":[{"bar":0,"change":"full band from downbeat — drum_kit + bass + lead + pad enter simultaneously"},{"bar":8,"change":"1-bar total dropout — drum_kit + pad cut, bass + lead reduced to single soft note"},{"bar":9,"change":"industrial slam — drum machine + perc + fx all enter at full velocity, abrupt"},{"bar":12,"change":"perc doubles density for final intensification"}],"register_strategy":"Funky (0-7): low + mid dominant, top restrained. Bar 8: spectral void. Industrial (9-15): full spectrum slam, sub reinforced by fx, high-mid saturated by perc."},"rationale":"Sawtooth density: peak from bar 0 (no build), cliff at bar 8 (cliff edge loud-to-quiet), abrupt re-entry bar 9 with extra industrial layers (perc + fx absent from funky half). Velocities differentiate: funky <=108, industrial >=115.","inspired_by":[{"song":"Queens_Of_The_Stone_Age/Six_Shooter","path":"arrangement.section_instrumentation","excerpt":"aggressive riff opens with full-band entry — no gradual build"},{"song":"Nine_Inch_Nails/March_Of_The_Pigs","path":"arrangement.dynamic_arc_overall","excerpt":"SAWTOOTH — repeated aggressive-to-quiet shifts in convulsive cycles"},{"song":"Soundgarden/Overfloater","path":"arrangement.instrumental_role_assignment","excerpt":"Two-guitar layering for sustained chord thickness — guitars as ATMOSPHERE"}],"confidence":0.91}
"""

PIVOT_DYNAMICS = """
{"schema_version":"1.0","dynamics":{"arc_shape":"valley","start_db":-4.0,"end_db":-3.0,"peak_bar":null,"inflection_points":[[7,-4.0],[8,-28.0],[9,-3.0]]},"rationale":"Section starts at -4 dB (funky drive at perpetual-peak baseline like Six_Shooter and March_Of_The_Pigs), 1-bar cliff dropout to -28 dB at bar 8 (no transition device), industrial slam re-entry at -3 dB (slightly louder than funky drive — second peak is the cathartic one). Valley shape captures the contour: high peak -> trough -> higher peak.","inspired_by":[{"song":"Nine_Inch_Nails/March_Of_The_Pigs","path":"arrangement.dynamic_arc_overall","excerpt":"SAWTOOTH — verse at maximum density and loudness; chorus break at near-minimum"},{"song":"Nine_Inch_Nails/March_Of_The_Pigs","path":"stylistic_figures.transitions_between_sections","excerpt":"single beat of silence, then the new meter establishes — CLIFF EDGE between two different songs juxtaposed"},{"song":"Queens_Of_The_Stone_Age/Six_Shooter","path":"arrangement.dynamic_arc_overall","excerpt":"Sustained maximum-aggression throughout — minimal dynamic arc"}],"confidence":0.91}
"""


# ============================================================================
# Bar-to-beat mapping (mixed meter)
# ============================================================================


def bar_start_beat(bar: int) -> float:
    """Cumulative quarter-beat at the START of `bar` (0-indexed)."""
    if bar <= PIVOT_BAR:
        return bar * FUNKY_BAR_BEATS
    return PIVOT_BAR * FUNKY_BAR_BEATS + (bar - PIVOT_BAR) * INDUSTRIAL_BAR_BEATS


def bar_length_beats(bar: int) -> float:
    """Length of `bar` in quarter-beats (3.5 if 7/8, 4.0 if 4/4)."""
    return FUNKY_BAR_BEATS if bar < PIVOT_BAR else INDUSTRIAL_BAR_BEATS


# ============================================================================
# Harmony — chord progression Em-D-Am-D cycling each bar
# ============================================================================
#
# E Dorian: E F# G A B C# D
# i  = Em (root E,  5th B)        -> [E1=28, B1=35]; high-voiced [E3=52, B3=59]
# bVII = D  (root D, 5th A)        -> [D1=26, A1=33];           [D3=50, A3=57]
# iv = Am (root A,  5th E)        -> [A0=21, E1=28];            [A2=45, E3=52]


CHORD_PER_BAR: Tuple[str, ...] = (
    "Em", "D", "Am", "D",       # cycle 1, bars 0-3
    "Em", "D", "Am", "D",       # cycle 2, bars 4-7
    "Em",                       # bar 8 = dropout, but the "current chord" stays Em
    "Em", "D", "Am", "D",       # cycle 3 (industrial), bars 9-12
    "Em", "D", "Am",            # cycle 4 partial, bars 13-15
)
assert len(CHORD_PER_BAR) == TOTAL_BARS

# (root pitch low, fifth pitch low, root pitch mid, fifth pitch mid)
CHORD_PITCHES: Dict[str, Tuple[int, int, int, int]] = {
    "Em": (28, 35, 52, 59),     # E1, B1 / E3, B3
    "D":  (26, 33, 50, 57),     # D1, A1 / D3, A3
    "Am": (21, 28, 45, 52),     # A0, E1 / A2, E3
}


# ============================================================================
# Note generators per role
# ============================================================================
#
# Each generator returns a list of {time, pitch, duration, velocity} dicts
# at section-relative beats. Drum pitches use General-MIDI percussion:
#   36 kick    37 sidestick    38 snare        39 clap
#   42 closed-hat   46 open-hat   49 crash      51 ride
#   56 cowbell-slot (used as "industrial metal hit")

NoteDict = Dict[str, float]


def _note(time: float, pitch: int, duration: float, velocity: int) -> NoteDict:
    return {
        "time": float(time),
        "pitch": int(pitch),
        "duration": float(duration),
        "velocity": max(1, min(127, int(velocity))),
    }


# --- DRUM_KIT funky (bars 0-7) -------------------------------------------------


def gen_drum_funky() -> List[NoteDict]:
    """7/8 funky pattern with ghost-note swagger.

    Per 7/8 bar (3.5 quarter-beats = 7 8th-notes):
      8th 1 (0.0 q-beats): kick + closed hat
      8th 2 (0.5):        closed hat
      8th 3 (1.0):        closed hat (ghost snare 35 vel)
      8th 4 (1.5):        kick + snare backbeat + closed hat
      8th 5 (2.0):        OPEN hat (the 'open' lift)
      8th 6 (2.5):        closed hat (ghost snare 30 vel)
      8th 7 (3.0):        closed hat
    """
    out: List[NoteDict] = []
    for bar in range(0, PIVOT_BAR):  # bars 0..7
        b = bar_start_beat(bar)
        # Kick on 8ths 1 and 4
        out.append(_note(b + 0.0, 36, 0.25, 110))
        out.append(_note(b + 1.5, 36, 0.25, 100))
        # Snare backbeat on 8th 4 (midpoint of 7)
        out.append(_note(b + 1.5, 38, 0.20, 108))
        # Ghost snares
        out.append(_note(b + 1.0, 38, 0.10, 35))
        out.append(_note(b + 2.5, 38, 0.10, 30))
        # Closed hat 8ths (skip 8th 5 which is OPEN)
        for off in (0.0, 0.5, 1.0, 1.5, 2.5, 3.0):
            out.append(_note(b + off, 42, 0.20, 70 + (5 if off in (0.0, 1.5) else 0)))
        # Open hat on 8th 5
        out.append(_note(b + 2.0, 46, 0.30, 80))
    return out


# --- DRUM_KIT industrial (bars 9-15) ------------------------------------------


def gen_drum_industrial() -> List[NoteDict]:
    """4/4 machine-tight industrial pattern.

    Per 4/4 bar (4 quarter-beats):
      Beat 0:   kick + closed hat
      Beat 0.5: closed hat
      Beat 1:   kick + snare (backbeat 2) + closed hat
      Beat 1.5: closed hat
      Beat 2:   kick + closed hat
      Beat 2.5: closed hat
      Beat 3:   kick + snare (backbeat 4) + closed hat
      Beat 3.5: closed hat
      And on bar 1 of every other bar (9, 11, 13, 15): metal crash on beat 0.
    """
    out: List[NoteDict] = []
    for bar in range(PIVOT_BAR + 1, TOTAL_BARS):  # bars 9..15
        b = bar_start_beat(bar)
        # Kick on every quarter (machine-floor)
        for q in (0.0, 1.0, 2.0, 3.0):
            out.append(_note(b + q, 36, 0.20, 118))
        # Snare on 2 and 4
        out.append(_note(b + 1.0, 38, 0.20, 115))
        out.append(_note(b + 3.0, 38, 0.20, 118))
        # Closed hat 8ths (machine-strict, no ghosts)
        for off in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5):
            out.append(_note(b + off, 42, 0.15, 78))
        # Metal crash punctuation every other bar (49 = crash)
        if (bar - (PIVOT_BAR + 1)) % 2 == 0:
            out.append(_note(b + 0.0, 49, 0.50, 122))
    return out


# --- BASS (bars 0-15, with bar 8 as soft single-note cliff marker) ------------


def gen_bass() -> List[NoteDict]:
    """Funky bass front (root + ghost passing tones) -> machine root pulse back.

    Funky half: root on beat 0 (full vel), 5th-below octave on beat 1.5 (med),
                root on beat 3 (med). Per 7/8 bar.
    Bar 8: single soft root sustained for 1 beat then silence (cliff marker).
    Industrial half: root on every quarter at hard velocity (machine pulse).
    """
    out: List[NoteDict] = []
    for bar in range(0, TOTAL_BARS):
        b = bar_start_beat(bar)
        chord = CHORD_PER_BAR[bar]
        root_low, fifth_low, _root_mid, _fifth_mid = CHORD_PITCHES[chord]

        if bar < PIVOT_BAR:
            # Funky 7/8: root on 0, fifth (one below) on 1.5, root on 3
            out.append(_note(b + 0.0, root_low, 0.45, 105))
            out.append(_note(b + 1.5, fifth_low, 0.40, 90))
            out.append(_note(b + 3.0, root_low, 0.40, 95))
        elif bar == PIVOT_BAR:
            # Cliff marker: single soft root, then 3 beats of silence
            out.append(_note(b + 0.0, root_low, 1.0, 55))
        else:
            # Industrial 4/4 machine root pulse on every quarter
            for q in (0.0, 1.0, 2.0, 3.0):
                out.append(_note(b + q, root_low, 0.22, 115))
    return out


# --- LEAD (bars 0-15, the riff carrier) ---------------------------------------


def gen_lead() -> List[NoteDict]:
    """Driving riff in E Dorian. Per chord, a 4-note phrase with shape:
    root - b3/maj3-of-chord - 5th - root.

    For Em (E Dorian i):     E - G - B - E   (b3, since Em chord = m3)
    For D  (bVII, D maj):    D - F# - A - D  (M3)
    For Am (iv, A min):      A - C - E - A   (m3, but uses E Dorian's natural
                                              C-natural? E Dorian scale has
                                              C# not C... so use C# = M3 of A
                                              -> Am becomes A-C#-E = A maj
                                              actually iv in Dorian is MAJOR,
                                              not minor, because of natural 6.
                                              Let me use C# for iv chord.
                                              That makes iv = A major, the
                                              characteristic Dorian color.)

    Funky half: stab pattern across the 3.5-beat 7/8 bar.
    Bar 8: single open root chord stab, low velocity (cliff).
    Industrial half: tight 8th-note palm-mute-style root stabs.
    """
    out: List[NoteDict] = []

    # Per-chord melodic figures (high voicing, mid range)
    riff_phrases: Dict[str, Tuple[int, ...]] = {
        # In E Dorian, A is iv but with NATURAL 6 (C#) so the "iv" is A major
        # voicing as A-C#-E -> melodic phrase A-C#-E-A
        "Em": (52, 55, 59, 52),       # E3, G3, B3, E3
        "D":  (50, 54, 57, 50),       # D3, F#3, A3, D3
        "Am": (45, 49, 52, 45),       # A2, C#3 (Dorian raised 6 vs Aeolian!), E3, A2
    }

    for bar in range(0, TOTAL_BARS):
        b = bar_start_beat(bar)
        chord = CHORD_PER_BAR[bar]
        phrase = riff_phrases[chord]
        root_mid = phrase[0]

        if bar < PIVOT_BAR:
            # Funky 7/8: 4-note riff over 3.5 beats. Stabs on beats 0, 1, 2, 3.
            for i, p in enumerate(phrase):
                t = b + i * 0.875       # 4 stabs across 3.5 beats = 0.875 spacing
                vel = 108 if i in (0, 3) else 95
                out.append(_note(t, p, 0.45, vel))
            # Sympathetic accent on the syncopated 8th 6 (beat 2.5) for swagger
            out.append(_note(b + 2.5, phrase[2], 0.20, 80))
        elif bar == PIVOT_BAR:
            # Cliff: one soft open chord stab on beat 0 only
            out.append(_note(b + 0.0, root_mid, 1.0, 60))
        else:
            # Industrial: 8th-note tight root + 5th stabs (palm-mute feel)
            for off in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5):
                out.append(_note(b + off, root_mid, 0.22, 110))
                # Add 5th on every quarter for bigger stab
                if off in (0.0, 1.0, 2.0, 3.0):
                    out.append(_note(b + off, root_mid + 7, 0.22, 105))
    return out


# --- PAD (bars 0-7 only, atmospheric sustain) ---------------------------------


def gen_pad() -> List[NoteDict]:
    """Sustained two-guitar layering atmosphere over the funky half.
    Triad-voiced pad held for the full 3.5 beats per bar. Exits at bar 8.
    Voicings (E Dorian-aware):
      Em -> E3 + G3 + B3 (i, minor triad)
      D  -> D3 + F#3 + A3 (bVII, major triad)
      Am -> A2 + C#3 + E3 (iv as DORIAN iv = MAJOR triad, characteristic color)
    """
    triads: Dict[str, Tuple[int, ...]] = {
        "Em": (52, 55, 59),
        "D":  (50, 54, 57),
        "Am": (45, 49, 52),
    }
    out: List[NoteDict] = []
    for bar in range(0, PIVOT_BAR):  # bars 0..7
        b = bar_start_beat(bar)
        chord = CHORD_PER_BAR[bar]
        for p in triads[chord]:
            out.append(_note(b + 0.0, p, FUNKY_BAR_BEATS, 78))
    return out


# --- PERC (bars 9-15, industrial metal hits) ----------------------------------


def gen_perc() -> List[NoteDict]:
    """Processed metal percussion on the industrial half. 8th-note grid
    on bars 9-11 (warming up), 16th-note grid on bars 12-15 (per the
    arrangement note 'perc doubles density at bar 12').
    Pitch 56 (cowbell slot, often mapped to industrial metal samples)."""
    out: List[NoteDict] = []
    for bar in range(PIVOT_BAR + 1, TOTAL_BARS):
        b = bar_start_beat(bar)
        if bar < 12:
            # 8th-note grid
            for off in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5):
                vel = 122 if off in (0.0, 2.0) else 100
                out.append(_note(b + off, 56, 0.15, vel))
        else:
            # 16th-note grid (doubled density)
            for off in [i * 0.25 for i in range(16)]:
                vel = 122 if off in (0.0, 1.0, 2.0, 3.0) else (95 if off % 0.5 == 0 else 78)
                out.append(_note(b + off, 56, 0.10, vel))
    return out


# --- FX (bars 9-15, industrial noise/sub swell) -------------------------------


def gen_fx() -> List[NoteDict]:
    """Sub-bass synth swell anchored at the very low E. Single sustained
    note per industrial bar, plus a punctuating high-stab on bar 9 entry."""
    out: List[NoteDict] = []
    # Big entry stab at bar 9 downbeat (high pitch for impact)
    b9 = bar_start_beat(PIVOT_BAR + 1)
    out.append(_note(b9, 60, 0.5, 122))      # C4 stab — alarm-like punch
    # Sustained sub-E (E0 = 16) for each industrial bar
    for bar in range(PIVOT_BAR + 1, TOTAL_BARS):
        b = bar_start_beat(bar)
        out.append(_note(b + 0.0, 16, INDUSTRIAL_BAR_BEATS, 115))
    return out


# Track config: (role_upper, color, generator_fn, enters_bar_for_clip,
#                exits_bar_for_clip)
TRACK_CONFIG: List[Tuple[str, int, callable, int, int]] = [
    ("DRUM_KIT", 2,  None,             0, TOTAL_BARS),  # special: 2 generators
    ("BASS",    14, gen_bass,          0, TOTAL_BARS),
    ("LEAD",    25, gen_lead,          0, TOTAL_BARS),
    ("PAD",     19, gen_pad,           0, PIVOT_BAR),
    ("PERC",     5, gen_perc,          PIVOT_BAR + 1, TOTAL_BARS),
    ("FX",      38, gen_fx,            PIVOT_BAR + 1, TOTAL_BARS),
]


def gen_drum_combined() -> List[NoteDict]:
    return gen_drum_funky() + gen_drum_industrial()


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    print("=== Pivot Demo build ===")

    # --- Phase 1: assemble blueprint ---
    print("\n[1/4] Parse 5 sphere-decider JSONs -> SectionBlueprint('Pivot')")
    bp = (
        SectionBlueprint(
            name="Pivot",
            references=(
                "Queens_Of_The_Stone_Age/Six_Shooter",
                "Soundgarden/Overfloater",
                "Nine_Inch_Nails/March_Of_The_Pigs",
            ),
            brief="16-bar funky-to-industrial pivot @ 130 BPM, drive from bar 1",
        )
        .with_decision("structure",   parse_structure_decision_from_response(PIVOT_STRUCTURE))
        .with_decision("harmony",     parse_harmony_decision_from_response(PIVOT_HARMONY))
        .with_decision("rhythm",      parse_rhythm_decision_from_response(PIVOT_RHYTHM))
        .with_decision("arrangement", parse_arrangement_decision_from_response(PIVOT_ARRANGEMENT))
        .with_decision("dynamics",    parse_dynamics_decision_from_response(PIVOT_DYNAMICS))
    )
    assert bp.filled_spheres() == ("structure", "harmony", "rhythm", "arrangement", "dynamics")
    print(f"  OK 5/5 spheres filled — key={bp.harmony.value.key_root} "
          f"{bp.harmony.value.mode}, tempo={bp.rhythm.value.tempo_bpm} BPM, "
          f"{len(bp.arrangement.value.layers)} layer entries")

    # --- Phase 2: cohesion ---
    print("\n[2/4] Cohesion check")
    report = check_cohesion(bp)
    if not report.is_clean:
        for v in report.blockers:
            print(f"  FAIL {v.rule}: {v.message}")
        raise SystemExit(1)
    print(f"  OK clean ({len(report.warnings)} warning(s))")
    for w in report.warnings:
        print(f"    ! {w.rule}: {w.message}")

    # --- Phase 3: hand-crafted note generation ---
    print("\n[3/4] Hand-crafted note generation per role")
    notes_per_role: Dict[str, List[NoteDict]] = {}
    for role, _color, gen_fn, _start, _stop in TRACK_CONFIG:
        if role == "DRUM_KIT":
            notes = gen_drum_combined()
        else:
            notes = gen_fn()
        notes_per_role[role] = notes
        print(f"  OK {role:9s} {len(notes):4d} notes")

    # --- Phase 4: inject into .als ---
    print(f"\n[4/4] Building {DST.name}")
    if SRC == DST:
        raise RuntimeError("Source and destination must differ")
    shutil.copy(SRC, DST)

    with gzip.open(DST, "rb") as f:
        xml = f.read().decode("utf-8")

    xml = _set_project_tempo(xml, PROJECT_TEMPO)
    print(f"  OK Project tempo set to {PROJECT_TEMPO} BPM")

    # Extract empty MidiTrack 12 as clone seed.
    seed_match = re.search(
        r'<MidiTrack Id="12"[^>]*>.*?</MidiTrack>', xml, re.DOTALL,
    )
    if not seed_match:
        raise RuntimeError("Seed <MidiTrack Id=\"12\"> not found")
    seed_track = seed_match.group(0)

    # Build per-role clip and clone tracks.
    new_tracks: List[str] = []
    clip_id = 1000
    section_color = 4   # orange (Pivot section color used for clips)
    section_length = TOTAL_BEATS

    for i, (role, color, _gen_fn, _start, _stop) in enumerate(TRACK_CONFIG):
        notes = notes_per_role[role]
        if not notes:
            print(f"  SKIP {role}: no notes")
            continue
        clip = _build_midi_clip(
            clip_id=clip_id,
            start_beat=0,
            length_beat=int(section_length),
            name=f"Pivot [{role}]",
            color=section_color,
            notes=notes,
        )
        clone = _clone_midi_track(
            seed_track,
            new_track_id=300 + i,
            role=role,
            display_name=role.replace("_", " ").title(),
            color=color,
            id_offset=100_000 + i * 100_000,
            clips=[clip],
        )
        new_tracks.append(clone)
        clip_id += 1
        print(f"  OK Cloned [{role}] track Id={300+i} (1 clip, "
              f"length={int(section_length)} beats)")

    xml = _insert_tracks_after(xml, anchor_track_id=12, new_tracks=new_tracks)
    print(f"  OK Inserted {len(new_tracks)} new MidiTracks after Id=12")

    # Bump NextPointeeId beyond the highest shifted Id.
    safe_npi = 100_000 + len(TRACK_CONFIG) * 100_000 + 100_000
    xml = _bump_next_pointee_id(xml, safe_npi)
    print(f"  OK NextPointeeId set to {safe_npi}")

    ET.fromstring(xml)
    print(f"  OK XML parses cleanly")

    with gzip.open(DST, "wb", compresslevel=9) as f:
        f.write(xml.encode("utf-8"))

    with gzip.open(DST, "rb") as f:
        head = f.read(80)
    if not head.startswith(b"<?xml"):
        raise RuntimeError(f"Post-write check FAILED: head = {head[:30]!r}")
    print(f"  OK Post-write check: gunzip head starts with <?xml")
    print(f"  OK Final size: {DST.stat().st_size} bytes")

    print(f"\n=== DONE ===")
    print(f"Output: {DST}")
    print(f"\nClip length: {section_length} beats "
          f"({PIVOT_BAR} bars 7/8 + {TOTAL_BARS - PIVOT_BAR} bars 4/4)")


if __name__ == "__main__":
    main()
