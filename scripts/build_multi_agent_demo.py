"""Build Multi_Agent_Demo.als — 2 sections composed via composition_engine
multi-agent pipeline (Phase 2.6).

Brief: 2 sections at 96 BPM, modal pivot Aeolian → Mixolydian on tonic A.

  Section 1 'Pressure' — 16 bars, A Aeolian, ambient build to industrial
  pressure. Refs: Pyramid_Song + The_Wretched + Fell_On_Black_Days.
  16/8 (3+3+4+3+3) feel, late drum entry at bar 6, exponential dB arc.

  Section 2 'Release' — 16 bars, A Mixolydian, heavy half-time chorus with
  drum-spotlight breakdown and full-band slam-back. Refs:
  A_Song_For_The_Dead + Jesus_Christ_Pose + Heart_Shaped_Box. 4/4 grid,
  valley dB arc.

Each sphere decision is the RAW JSON output of its sphere-decider subagent
(structure / harmony / rhythm / arrangement / dynamics) — no manual
construction of Decision objects in Python. The parsers in
composition_engine.blueprint.agent_parsers consume the raw text.

Pipeline:
  1. Parse 10 raw JSON payloads (5 spheres × 2 sections) into Decisions.
  2. Assemble 2 SectionBlueprint with .with_decision().
  3. check_cohesion() must be clean for both.
  4. compose_to_midi() — produce out/Pressure.mid and out/Release.mid.
  5. compose_from_blueprint() — get note dicts, flatten layers per section.
  6. Copy Template.als → Multi_Agent_Demo.als, inject 2 MidiClips into the
     existing '1-MIDI' track (Pressure at beat 0, Release at beat 64).
  7. Set project tempo to 96, recompress, post-write verify.
"""
from __future__ import annotations

import gzip
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List

from composition_engine.blueprint import SectionBlueprint, check_cohesion
from composition_engine.blueprint.agent_parsers import (
    parse_arrangement_decision_from_response,
    parse_dynamics_decision_from_response,
    parse_harmony_decision_from_response,
    parse_rhythm_decision_from_response,
    parse_structure_decision_from_response,
)
from composition_engine.blueprint.composer_adapter import (
    compose_from_blueprint,
    compose_to_midi,
)


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Template.als"
DST = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Multi_Agent_Demo.als"
OUT_DIR = ROOT / "out"

PROJECT_TEMPO = 96
BARS_PER_SECTION = 16
BEATS_PER_BAR = 4  # composer_adapter hardcodes 4-beat cycles regardless of time_signature
SECTION_LENGTH_BEATS = BARS_PER_SECTION * BEATS_PER_BAR  # 64


# ============================================================================
# Raw agent JSON outputs (verbatim from sphere-decider subagent runs)
# ============================================================================

# --- Section 1 'Pressure' ---------------------------------------------------

PRESSURE_STRUCTURE = """
{"schema_version":"1.0","structure":{"total_bars":16,"sub_sections":[{"name":"drone_breath","start_bar":0,"end_bar":5,"role":"breath"},{"name":"stagger_build","start_bar":5,"end_bar":11,"role":"build"},{"name":"menace_peak","start_bar":11,"end_bar":16,"role":"drop"}],"breath_points":[4,9],"transition_in":"drone_alone_no_anticipation","transition_out":"integrated_textural_transformation_into_release"},"rationale":"5+6+5 asymmetric phrasing inspired by Pyramid_Song and Fell_On_Black_Days, breath_points at 4 and 9 mark drum-less openings, density rises via The_Wretched-style integration not a brutal drop.","inspired_by":[{"song":"Radiohead/Pyramid_Song","path":"composition.structural_blueprint","excerpt":"piano_alone_intro ... drums_enter_late"},{"song":"Nine_Inch_Nails/The_Wretched","path":"stylistic_figures.transitions_between_sections","excerpt":"integrated_textural_transformation_via_simultaneous_thin_and_rise"},{"song":"Soundgarden/Fell_On_Black_Days","path":"composition.section_count_and_lengths","excerpt":"verses: 8 bars each in 6/4 — gives the verses extra breath"}],"confidence":0.88}
"""

PRESSURE_HARMONY = """
{"schema_version":"1.0","harmony":{"mode":"Aeolian","key_root":"A","progression":["i","bVII","bVI","v"],"harmonic_rhythm":0.25,"voicing_strategy":"drone-rooted open fifth on A across bars 0-5 (pedal tone à la Fell_On_Black_Days drop-D); bVII at bar 5 spread voicing + sustained pad; bVI at bar 9 chromatic inner-voice descent (Wretched chromatic inflection); v at bar 11 voiced as bare fifth E-B with no third — ambiguous, no resolution, tension held open for Mixolydian handoff","cadence_at_end":"open"},"rationale":"A Aeolian anchored on A pedal for 5 bars (drone_breath) — pacing 0.25 chords/bar from Pyramid_Song. i→bVII at bar 5, bVI at bar 9 (breath_point), v at bar 11 with bare fifth (no third) leaves Mixolydian pivot open. Asymmetric durations 5+4+2+5 follow sub-sections.","inspired_by":[{"song":"Radiohead/Pyramid_Song","path":"composition.harmonic_pacing","excerpt":"one harmonic event every 12-15 seconds"},{"song":"Soundgarden/Fell_On_Black_Days","path":"composition.harmonic_motion","excerpt":"Modal Aeolian with sus chord coloring; drop D pedal under moving upper voices"},{"song":"Nine_Inch_Nails/The_Wretched","path":"composition.harmonic_motion","excerpt":"Verse harmonic motion is DENSE and DARK — chromatic chord shifts, small neighbor moves"}],"confidence":0.88}
"""

PRESSURE_RHYTHM = """
{"schema_version":"1.0","rhythm":{"tempo_bpm":96,"time_signature":"16/8 with 3+3+4+3+3 internal grouping","drum_pattern":"BARS 0-5 (drone_breath): no drums, sub-threshold pulse only. BARS 5-6: drum entry without anticipation/fill — Selway-style. Cross-stick on the 4 of the 3+3+4 grouping, pp; single kick on next downbeat. BARS 6-11 (stagger_build): floating kit implying 4/4 against the 16/8 grid (Pyramid_Song polyrhythmic strategy). Closed hat 8ths, cross-stick on grouping 2, kick fragmented on 8ths 1 and 9 (no four-on-floor). Ghost snare on off-8ths. BARS 11-16 (menace_peak): industrial drive — kick programmed-tight on 8ths 1, 5, 9, 13, hard snare on groupings 2 and 4, closed 16th hats, processed metal hits on off-8ths of the 3+3 groupings.","subdivisions":16,"swing":0.0,"polyrhythms":["drum kit implying 4/4 against strict 16/8 3+3+4+3+3 piano grid (bars 6-11)","industrial percussion hits on off-8ths of 3+3 groupings against 4-on-floor kick (bars 11-16)"]},"rationale":"96 BPM upstream-fixed. 16/8 with 3+3+4+3+3 grouping is the Pyramid_Song signature — strict meter without a square downbeat. Late drum entry at bar 5-6 mirrors Selway's late_drum_entry_as_structural_pivot. Industrial drive at bar 11 imports The_Wretched programmed kick + metal-hit vocabulary. Swing 0.0 because all three refs converge on machine-tight or strict notation.","inspired_by":[{"song":"Radiohead/Pyramid_Song","path":"time_signature","excerpt":"16/8 with internal grouping 3+3+4+3+3"},{"song":"Radiohead/Pyramid_Song","path":"stylistic_figures.transitions_between_sections","excerpt":"late_drum_entry_as_structural_pivot_no_anticipation"},{"song":"Nine_Inch_Nails/The_Wretched","path":"performance.drum_style","excerpt":"Programmed kick + snare backbone + industrial percussion samples layered for verse aggression"}],"confidence":0.88}
"""

PRESSURE_ARRANGEMENT = """
{"schema_version":"1.0","arrangement":{"layers":[{"role":"pad","instrument":"drone synth — sustained A Aeolian tone, low + mid register","enters_at_bar":0,"exits_at_bar":16,"base_velocity":65},{"role":"fx","instrument":"ondes Martenot atmospheric shimmer","enters_at_bar":2,"exits_at_bar":16,"base_velocity":55},{"role":"sub","instrument":"sub bass pedal — A drone, very low register","enters_at_bar":3,"exits_at_bar":16,"base_velocity":80},{"role":"bass","instrument":"distorted bass synth — clean at entry, saturated by bar 9","enters_at_bar":4,"exits_at_bar":16,"base_velocity":90},{"role":"drum_kit","instrument":"programmed industrial kit — sparse brushed at entry, full drive by bar 11","enters_at_bar":6,"exits_at_bar":16,"base_velocity":78},{"role":"perc","instrument":"industrial metal percussion — found-sound processing","enters_at_bar":11,"exits_at_bar":16,"base_velocity":108},{"role":"lead","instrument":"distorted lead — chromatic menace phrase, high-register bite","enters_at_bar":11,"exits_at_bar":16,"base_velocity":100}],"density_curve":"build","instrumentation_changes":[{"bar":2,"change":"fx ondes-shimmer enters over drone — no fill, no anticipation"},{"bar":3,"change":"sub bass A pedal enters — very low, barely audible"},{"bar":4,"change":"bass enters sparse, sustained — bVII region approached, distortion minimal"},{"bar":6,"change":"drum_kit enters late, Selway-style restraint — no riser, no fill"},{"bar":9,"change":"bass distortion saturates as v-chord region darkens (Wretched bass adapting)"},{"bar":11,"change":"menace_peak: industrial perc and distorted lead enter simultaneously, 4-on-floor engaged"},{"bar":13,"change":"lead chromatic phrase intensifies, drum density maxed"}],"register_strategy":"Bars 0-5: sub + low pad only, spectral void above 200 Hz. Bars 6-10: drum_kit fills low-mid, upper register absent. Bars 11-16: full spectrum opens via industrial perc and distorted lead, narrow-bottom to wide-full."},"rationale":"Three phases mapped to sub-sections. Drone_breath (0-5): pad + fx + sub only — Pyramid_Song no-drum-from-start principle. Stagger_build (5-11): bass anchors at bar 4, drums enter late at bar 6, Selway-floating velocity 78. Menace_peak (11-16): perc + lead enter simultaneously at bar 11 — Wretched vocabulary_overlay_bridge_entry plus Fell_On_Black_Days clean-to-distorted shift. density_curve='build'.","inspired_by":[{"song":"Radiohead/Pyramid_Song","path":"arrangement.arrangement_anti_patterns_avoided","excerpt":"No drum kit from the start (the late drum entry is itself a structural event)"},{"song":"Nine_Inch_Nails/The_Wretched","path":"stylistic_figures.transitions_between_sections","excerpt":"vocabulary_overlay_bridge_entry: aggressive vocabulary BACK while atmospheric chorus elements REMAIN"},{"song":"Soundgarden/Fell_On_Black_Days","path":"arrangement.section_instrumentation","excerpt":"chorus: DISTORTION ENGAGES on guitars + drums hit fuller + vocal opens up"}],"confidence":0.88}
"""

PRESSURE_DYNAMICS = """
{"schema_version":"1.0","dynamics":{"arc_shape":"exponential","start_db":-36.0,"end_db":-3.0,"peak_bar":null,"inflection_points":[[6,-18.0],[11,-3.0]]},"rationale":"Exponential crescendo: near-silence at bar 0 (drone alone, -36 dB), slow progression to drum entry at bar 6 (-18 dB, density milestone), then concentrated gain to menace_peak at bar 11 (-3 dB plateau held to end). The first 5 bars are nearly static; gain concentrates in stagger_build → menace_peak window — the 'Pressure' name is exactly that non-linear contour.","inspired_by":[{"song":"Radiohead/Pyramid_Song","path":"arrangement.dynamic_arc_overall","excerpt":"Slow, monotonically-rising swell. Spare opening to peak at full ensemble texture"},{"song":"Nine_Inch_Nails/The_Wretched","path":"stylistic_figures.climax_moments","excerpt":"Climax via fusion rather than via amplitude — both vocabularies at full strength simultaneously"},{"song":"Soundgarden/Fell_On_Black_Days","path":"arrangement.dynamic_arc_overall","excerpt":"TRADITIONAL loud-quiet-loud SHIFT between verse and chorus"}],"confidence":0.88}
"""

# --- Section 2 'Release' ----------------------------------------------------

RELEASE_STRUCTURE = """
{"schema_version":"1.0","structure":{"total_bars":16,"sub_sections":[{"name":"punch_A","start_bar":0,"end_bar":8,"role":"drop"},{"name":"breakdown_breath","start_bar":8,"end_bar":12,"role":"breath"},{"name":"punch_B_resurge","start_bar":12,"end_bar":16,"role":"build"}],"breath_points":[8,11],"transition_in":"modal_pivot_Am_to_A_Mixolydian_on_downbeat — full band slams in on bar 0 with no riser","transition_out":"vocal_subtraction_groove_persists_then_fade — Mixolydian b7 color resolves without fully closing"},"rationale":"punch_A reproduces QOTSA half-time chorus (same BPM, halved rhythmic surface). breakdown_breath cites drum_feature_break (spotlight_via_instrumentation_dropout) and JCP extended_bridge. breath_points 8+11 mark dropout entry and bottom. punch_B_resurge executes full_band_slam_back. 4+4/4+4 keeps 8-bar Nirvana symmetry while breaking linearity.","inspired_by":[{"song":"Queens_Of_The_Stone_Age/A_Song_For_The_Dead","path":"composition.structural_blueprint","excerpt":"CHORUS_HALF_TIME — same BPM but rhythmic surface HALVES"},{"song":"Soundgarden/Jesus_Christ_Pose","path":"composition.section_count_and_lengths","excerpt":"bridge: Extended 16+ bars instrumental — guitar work showcased"},{"song":"Nirvana/Heart_Shaped_Box","path":"stylistic_figures.transitions_between_sections","excerpt":"clean_to_distorted_engagement_on_downbeat"}],"confidence":0.91}
"""

RELEASE_HARMONY = """
{"schema_version":"1.0","harmony":{"mode":"Mixolydian","key_root":"A","progression":["I","bVII","I","bVII","I","bVII","IV","I","I","IV","bVII","IV","I","bVII","IV","I"],"harmonic_rhythm":1.0,"voicing_strategy":"drop-tuned power chords (root + fifth, occasional octave doubling) in punch_A and punch_B_resurge — broad, open, sustained. breakdown_breath (bars 8-11) opens to semi-clean dyads with root + fourth, upper voice sustains bVII; no third in voicing preserves modal ambiguity. Bar 0 lands with full-band unison attack to mark the Aeolian→Mixolydian pivot.","cadence_at_end":"authentic"},"rationale":"A Mixolydian imposed upstream as release pivot. The I–bVII pair (A–G) is the modal signature and the Mixolydian functional-equivalent of the authentic cadence — bVII resolves to I without a leading-tone dominant. The IV (D) opens harmonically at the breath_points 8 and 11. harmonic_rhythm=1.0 (16 chords on 16 bars) calibrated on QOTSA half-time chorus and Soundgarden ~1-2 bars/chord.","inspired_by":[{"song":"Queens_Of_The_Stone_Age/A_Song_For_The_Dead","path":"composition.harmonic_motion","excerpt":"bVI-bVII-i type power-chord shifts. Harmonic motion is SECONDARY to rhythmic-textural content"},{"song":"Soundgarden/Jesus_Christ_Pose","path":"composition.harmonic_motion","excerpt":"drop D power chord movements emphasizing low D root with movements to bVII"},{"song":"Nirvana/Heart_Shaped_Box","path":"composition.harmonic_motion","excerpt":"section identity shift is dynamic + timbre, NOT modulation"}],"confidence":0.88}
"""

RELEASE_RHYTHM = """
{"schema_version":"1.0","rhythm":{"tempo_bpm":96,"time_signature":"4/4","drum_pattern":"BARS 0-8 (punch_A — half-time chorus): kick on beats 1 and 3, snare HEAVY on beat 3 only (one massive snare per bar for cathartic weight). 16th hats with ghost on the e/ah of beats 2 and 4, light accent every other 16th for swagger. Bass locked tight to kick. Tom-fill on bar 7 beat 4 to signal breakdown. BARS 8-12 (breakdown_breath — drum spotlight): guitars + bass drop. Ride cymbal quarters replaces hat (bright, open). Kick syncopated at 1, 2.5, 4 (Cameron-style displaced). Snare ghost cascades on 16ths at bars 9-10 build into cross-stick accents at 11-12. Bar 11 tom-roll density. Bar 12 beat 4: full descending tom-fill. BARS 12-16 (punch_B_resurge — slam): on bar 13 downbeat, full band slams back as in ASFTD's full_band_slam_back. Kick returns to 1+3 half-time. Snare HARDER (Grohl). Hat back to 16ths with crash on every bar's beat 1 for max cathartic release. Locked to end.","subdivisions":16,"swing":0.15,"polyrhythms":["syncopated kick implying metric ambiguity within 4/4 during bars 8-12 breakdown (Cameron-style displaced kick at 1, 2.5, 4)"]},"rationale":"96 BPM upstream-fixed. 4/4 retained: return to grid IS the catharsis after Section 1 asymmetry. ASFTD half-time pattern (kick 1+3, snare on 3 only) is the direct import. Bars 8-12 spotlight via instrumentation dropout, bar 12 full_band_slam_back. Swing 0.15 from ASFTD ghost-note swagger and HSB humanized feel.","inspired_by":[{"song":"Queens_Of_The_Stone_Age/A_Song_For_The_Dead","path":"time_signature","excerpt":"4/4 throughout. The chorus stays in 4/4 numerically but FEELS half-time"},{"song":"Queens_Of_The_Stone_Age/A_Song_For_The_Dead","path":"stylistic_figures.transitions_between_sections","excerpt":"full_band_slam_back: full band slams back in at maximum intensity on a downbeat after a final drum statement"},{"song":"Nirvana/Heart_Shaped_Box","path":"performance.drum_style.techniques_documented","excerpt":"Snare hits in chorus documented as physically HARDER (Grohl's strike intensity changes section to section)"}],"confidence":0.88}
"""

RELEASE_ARRANGEMENT = """
{"schema_version":"1.0","arrangement":{"layers":[{"role":"drum_kit","instrument":"full rock kit — kick/snare half-time backbeat, 16th hats with swing","enters_at_bar":0,"exits_at_bar":16,"base_velocity":112},{"role":"bass","instrument":"distorted pick-attack electric bass, drop-A low end","enters_at_bar":0,"exits_at_bar":8,"base_velocity":105},{"role":"lead","instrument":"distorted electric guitar — palm-muted drive, drop-A","enters_at_bar":0,"exits_at_bar":8,"base_velocity":108},{"role":"sub","instrument":"sub bass synth reinforcing low A fundamental","enters_at_bar":0,"exits_at_bar":8,"base_velocity":95},{"role":"vocal","instrument":"high-range belted lead vocal — Cornell-register sustained wail","enters_at_bar":8,"exits_at_bar":12,"base_velocity":90},{"role":"pad","instrument":"sparse sustained open-chord pad — Mixolydian IV-bVII","enters_at_bar":8,"exits_at_bar":12,"base_velocity":65},{"role":"bass","instrument":"distorted pick-attack electric bass — slam-back re-entry","enters_at_bar":12,"exits_at_bar":16,"base_velocity":110},{"role":"lead","instrument":"distorted electric guitar — full-band resurge, max density","enters_at_bar":12,"exits_at_bar":16,"base_velocity":115}],"density_curve":"valley","instrumentation_changes":[{"bar":0,"change":"punch_A: full band at max density — drum_kit + bass + lead + sub locked"},{"bar":8,"change":"breakdown_breath: bass + lead + sub DROP simultaneously (QOTSA spotlight_via_instrumentation_dropout); drum_kit foregrounded; vocal wail + sparse pad enter over IV-bVII"},{"bar":10,"change":"drum spotlight peak — extended fills with no harmonic competition; vocal pushes ceiling"},{"bar":12,"change":"punch_B resurge: bass + lead slam back at full velocity on downbeat (full_band_slam_back); sub returns; vocal exits cleanly"}],"register_strategy":"punch_A (0-8): full sub-to-air spread, max density. breakdown_breath (8-12): mids only — drums low-mid, vocal upper-mid, pad middle, sub absent. punch_B (12-16): full spectrum returns instantly on slam-back."},"rationale":"Built around QOTSA spotlight_via_instrumentation_dropout: at bar 8, bass/lead/sub vanish simultaneously to project drums to foreground. Vocal enters Cornell-register over the void. At bar 12 full_band_slam_back snaps shut. density_curve='valley' is the only label that describes a single dense→trough→dense contour.","inspired_by":[{"song":"Queens_Of_The_Stone_Age/A_Song_For_The_Dead","path":"stylistic_figures.transitions_between_sections","excerpt":"spotlight_via_instrumentation_dropout_not_fill"},{"song":"Queens_Of_The_Stone_Age/A_Song_For_The_Dead","path":"stylistic_figures.transitions_between_sections","excerpt":"full_band_slam_back_after_drum_spotlight"},{"song":"Soundgarden/Jesus_Christ_Pose","path":"arrangement.instrumental_role_assignment","excerpt":"drums_role: PRIMARY COMPOSITIONAL VOICE"}],"confidence":0.91}
"""

RELEASE_DYNAMICS = """
{"schema_version":"1.0","dynamics":{"arc_shape":"valley","start_db":-3.0,"end_db":-3.0,"peak_bar":null,"inflection_points":[[8,-11.0],[10,-16.0],[12,-4.0]]},"rationale":"Symmetric valley: section opens at -3 dB (punch_A, max density), collapses at bar 8 to -11 dB (breakdown start, instrumentation subtraction), reaches -16 dB nadir at bar 10 (drum spotlight, relative silence is the precondition for the slam to register), abruptly rebounds to -4 dB at bar 12 (full_band_slam_back), settles at -3 dB by bar 16. Without the -16 dB trough, the resurge is acoustically invisible — the valley contrast is what makes the slam-back perceptible.","inspired_by":[{"song":"Queens_Of_The_Stone_Age/A_Song_For_The_Dead","path":"arrangement.dynamic_arc_overall","excerpt":"Saw-tooth + extended-coda. Drum feature break breathes; intensified return rebuilds"},{"song":"Queens_Of_The_Stone_Age/A_Song_For_The_Dead","path":"stylistic_figures.transitions_between_sections","excerpt":"drum_feature_break -> intensified_return: full band slams back at maximum intensity on a downbeat"},{"song":"Nirvana/Heart_Shaped_Box","path":"stylistic_figures.transitions_between_sections","excerpt":"chorus -> verse: instant_drop_back_to_quiet"}],"confidence":0.91}
"""


# ============================================================================
# Blueprint assembly
# ============================================================================


def assemble_blueprints() -> tuple[SectionBlueprint, SectionBlueprint]:
    """Parse all 10 raw agent payloads, build 2 SectionBlueprint."""
    refs_pressure = (
        "Radiohead/Pyramid_Song",
        "Nine_Inch_Nails/The_Wretched",
        "Soundgarden/Fell_On_Black_Days",
    )
    refs_release = (
        "Queens_Of_The_Stone_Age/A_Song_For_The_Dead",
        "Soundgarden/Jesus_Christ_Pose",
        "Nirvana/Heart_Shaped_Box",
    )

    bp_pressure = (
        SectionBlueprint(
            name="Pressure",
            references=refs_pressure,
            brief="16-bar A Aeolian build → industrial menace, 96 BPM, 16/8 (3+3+4+3+3)",
        )
        .with_decision("structure",   parse_structure_decision_from_response(PRESSURE_STRUCTURE))
        .with_decision("harmony",     parse_harmony_decision_from_response(PRESSURE_HARMONY))
        .with_decision("rhythm",      parse_rhythm_decision_from_response(PRESSURE_RHYTHM))
        .with_decision("arrangement", parse_arrangement_decision_from_response(PRESSURE_ARRANGEMENT))
        .with_decision("dynamics",    parse_dynamics_decision_from_response(PRESSURE_DYNAMICS))
    )

    bp_release = (
        SectionBlueprint(
            name="Release",
            references=refs_release,
            brief="16-bar A Mixolydian heavy half-time chorus with valley breakdown, 96 BPM, 4/4",
        )
        .with_decision("structure",   parse_structure_decision_from_response(RELEASE_STRUCTURE))
        .with_decision("harmony",     parse_harmony_decision_from_response(RELEASE_HARMONY))
        .with_decision("rhythm",      parse_rhythm_decision_from_response(RELEASE_RHYTHM))
        .with_decision("arrangement", parse_arrangement_decision_from_response(RELEASE_ARRANGEMENT))
        .with_decision("dynamics",    parse_dynamics_decision_from_response(RELEASE_DYNAMICS))
    )

    return bp_pressure, bp_release


# ============================================================================
# .als injection
# ============================================================================

# A MIDI note from composer output: dict with keys time/duration/velocity/pitch.
NoteDict = Dict[str, Any]


def _flatten_notes(tracks: Dict[str, List[NoteDict]]) -> List[NoteDict]:
    """Flatten composer per-track notes into one list, sorted by time."""
    flat: List[NoteDict] = []
    for track_notes in tracks.values():
        flat.extend(track_notes)
    flat.sort(key=lambda n: (float(n["time"]), int(n["pitch"])))
    return flat


def _notes_to_keytracks_xml(notes: List[NoteDict], indent: str) -> tuple[str, int]:
    """Emit <KeyTracks> XML grouping notes by pitch. Returns (xml, next_note_id)."""
    if not notes:
        return f"{indent}<KeyTracks />", 1

    by_pitch: Dict[int, List[tuple[float, float, int]]] = {}
    for n in notes:
        t = float(n["time"])
        d = float(n["duration"])
        v = max(1, min(127, int(round(float(n["velocity"])))))
        p = int(n["pitch"])
        by_pitch.setdefault(p, []).append((t, d, v))

    lines = [f"{indent}<KeyTracks>"]
    nid = 1
    kt_id = 0
    for pitch in sorted(by_pitch):
        events = sorted(by_pitch[pitch])
        lines.append(f"{indent}\t<KeyTrack Id=\"{kt_id}\">")
        lines.append(f"{indent}\t\t<Notes>")
        for t, dur, vel in events:
            lines.append(
                f"{indent}\t\t\t<MidiNoteEvent Time=\"{t}\" Duration=\"{dur}\" "
                f"Velocity=\"{vel}\" OffVelocity=\"64\" NoteId=\"{nid}\" />"
            )
            nid += 1
        lines.append(f"{indent}\t\t</Notes>")
        lines.append(f"{indent}\t\t<MidiKey Value=\"{pitch}\" />")
        lines.append(f"{indent}\t</KeyTrack>")
        kt_id += 1
    lines.append(f"{indent}</KeyTracks>")
    return "\n".join(lines), nid


def _build_midi_clip(
    *,
    clip_id: int,
    start_beat: int,
    length_beat: int,
    name: str,
    color: int,
    notes: List[NoteDict],
) -> str:
    """Assemble one <MidiClip> XML block at the given timeline position."""
    end = start_beat + length_beat
    kt_xml, next_nid = _notes_to_keytracks_xml(notes, indent="\t\t")
    return f"""<MidiClip Id="{clip_id}" Time="{start_beat}">
\t<LomId Value="0" />
\t<LomIdView Value="0" />
\t<CurrentStart Value="{start_beat}" />
\t<CurrentEnd Value="{end}" />
\t<Loop>
\t\t<LoopStart Value="0" />
\t\t<LoopEnd Value="{length_beat}" />
\t\t<StartRelative Value="0" />
\t\t<LoopOn Value="false" />
\t\t<OutMarker Value="{length_beat}" />
\t\t<HiddenLoopStart Value="0" />
\t\t<HiddenLoopEnd Value="{length_beat}" />
\t</Loop>
\t<Name Value="{name}" />
\t<Annotation Value="" />
\t<Color Value="{color}" />
\t<LaunchMode Value="0" />
\t<LaunchQuantisation Value="0" />
\t<TimeSignature>
\t\t<TimeSignatures>
\t\t\t<RemoteableTimeSignature Id="0">
\t\t\t\t<Numerator Value="4" />
\t\t\t\t<Denominator Value="4" />
\t\t\t\t<Time Value="0" />
\t\t\t</RemoteableTimeSignature>
\t\t</TimeSignatures>
\t</TimeSignature>
\t<Envelopes>
\t\t<Envelopes />
\t</Envelopes>
\t<ScrollerTimePreserver>
\t\t<LeftTime Value="0" />
\t\t<RightTime Value="{length_beat}" />
\t</ScrollerTimePreserver>
\t<TimeSelection>
\t\t<AnchorTime Value="0" />
\t\t<OtherTime Value="0" />
\t</TimeSelection>
\t<Legato Value="false" />
\t<Ram Value="false" />
\t<GrooveSettings>
\t\t<GrooveId Value="-1" />
\t</GrooveSettings>
\t<Disabled Value="false" />
\t<VelocityAmount Value="0" />
\t<FollowAction>
\t\t<FollowTime Value="4" />
\t\t<IsLinked Value="true" />
\t\t<LoopIterations Value="1" />
\t\t<FollowActionA Value="4" />
\t\t<FollowActionB Value="0" />
\t\t<FollowChanceA Value="100" />
\t\t<FollowChanceB Value="0" />
\t\t<JumpIndexA Value="1" />
\t\t<JumpIndexB Value="1" />
\t\t<FollowActionEnabled Value="false" />
\t</FollowAction>
\t<Grid>
\t\t<FixedNumerator Value="1" />
\t\t<FixedDenominator Value="16" />
\t\t<GridIntervalPixel Value="20" />
\t\t<Ntoles Value="2" />
\t\t<SnapToGrid Value="true" />
\t\t<Fixed Value="false" />
\t</Grid>
\t<FreezeStart Value="0" />
\t<FreezeEnd Value="0" />
\t<IsWarped Value="true" />
\t<TakeId Value="1" />
\t<IsInKey Value="true" />
\t<ScaleInformation>
\t\t<Root Value="0" />
\t\t<Name Value="0" />
\t</ScaleInformation>
\t<Notes>
{kt_xml}
\t\t<PerNoteEventStore>
\t\t\t<EventLists />
\t\t</PerNoteEventStore>
\t\t<NoteProbabilityGroups />
\t\t<ProbabilityGroupIdGenerator>
\t\t\t<NextId Value="1" />
\t\t</ProbabilityGroupIdGenerator>
\t\t<NoteIdGenerator>
\t\t\t<NextId Value="{next_nid}" />
\t\t</NoteIdGenerator>
\t</Notes>
\t<BankSelectCoarse Value="-1" />
\t<BankSelectFine Value="-1" />
\t<ProgramChange Value="-1" />
\t<NoteEditorFoldInZoom Value="-1" />
\t<NoteEditorFoldInScroll Value="0" />
\t<NoteEditorFoldOutZoom Value="128" />
\t<NoteEditorFoldOutScroll Value="-67" />
\t<NoteEditorFoldScaleZoom Value="-1" />
\t<NoteEditorFoldScaleScroll Value="0" />
\t<NoteSpellingPreference Value="0" />
\t<AccidentalSpellingPreference Value="3" />
\t<PreferFlatRootNote Value="false" />
\t<ExpressionGrid>
\t\t<FixedNumerator Value="1" />
\t\t<FixedDenominator Value="16" />
\t\t<GridIntervalPixel Value="20" />
\t\t<Ntoles Value="2" />
\t\t<SnapToGrid Value="false" />
\t\t<Fixed Value="false" />
\t</ExpressionGrid>
</MidiClip>"""


def _reindent(block: str, target_indent: str) -> str:
    """Re-indent a multi-line block to start at `target_indent`."""
    lines = block.split("\n")
    base = ""
    for line in lines:
        if line.strip():
            base = line[: len(line) - len(line.lstrip("\t"))]
            break
    out: List[str] = []
    for line in lines:
        if not line.strip():
            out.append(line)
            continue
        rel = line[len(base):] if line.startswith(base) else line
        out.append(target_indent + rel)
    return "\n".join(out)


def _set_project_tempo(xml: str, bpm: int) -> str:
    """Replace the project-level tempo (Live's <Tempo><Manual Value=...>)."""
    m = re.search(r"(<Tempo>.*?<Manual Value=\")[\d.]+(\")", xml, re.DOTALL)
    if not m:
        raise RuntimeError("Project <Tempo> Manual Value not found")
    return xml[: m.start(0)] + m.group(1) + str(bpm) + m.group(2) + xml[m.end(0):]


def _inject_clips_into_track(xml: str, midi_track_id: int, clips: List[str]) -> str:
    """Replace the track's `<ArrangerAutomation><Events />` with populated clips.

    Bound the search to the target MidiTrack to avoid matching other tracks.
    """
    track_open = re.search(rf'<MidiTrack Id="{midi_track_id}"', xml)
    if not track_open:
        raise RuntimeError(f"MidiTrack Id={midi_track_id} not found")
    track_start = track_open.start()
    track_end = xml.find("</MidiTrack>", track_start) + len("</MidiTrack>")
    if track_end < track_start:
        raise RuntimeError(f"</MidiTrack> close for Id={midi_track_id} not found")

    track_xml = xml[track_start:track_end]

    m = re.search(r"(<ArrangerAutomation>\s*)<Events />", track_xml)
    if not m:
        raise RuntimeError(
            f"MidiTrack Id={midi_track_id}: empty <ArrangerAutomation><Events /> not found "
            f"(track may already contain timeline clips)"
        )

    evt_pos = m.start(0) + len(m.group(1))
    line_start = track_xml.rfind("\n", 0, evt_pos) + 1
    indent = track_xml[line_start:evt_pos]
    inner_indent = indent + "\t"

    reindented = [_reindent(c, inner_indent) for c in clips]
    replacement = (
        m.group(1)
        + "<Events>\n"
        + "\n".join(reindented)
        + "\n"
        + indent
        + "</Events>"
    )
    new_track = track_xml[: m.start(0)] + replacement + track_xml[m.end(0):]
    return xml[:track_start] + new_track + xml[track_end:]


# ============================================================================
# Main pipeline
# ============================================================================


def main() -> None:
    print(f"=== Multi-Agent Demo build ===")
    print(f"Source : {SRC.name}")
    print(f"Target : {DST.name}")

    # --- Phase 1: assemble blueprints ---
    print("\n[1/5] Parsing 10 sphere-decider JSON payloads -> 2 SectionBlueprints")
    bp_pressure, bp_release = assemble_blueprints()
    for bp in (bp_pressure, bp_release):
        filled = bp.filled_spheres()
        assert filled == ("structure", "harmony", "rhythm", "arrangement", "dynamics"), (
            f"{bp.name}: expected 5 spheres filled, got {filled}"
        )
        print(f"  OK {bp.name}: 5/5 spheres filled "
              f"(key={bp.harmony.value.key_root} {bp.harmony.value.mode}, "
              f"tempo={bp.rhythm.value.tempo_bpm}, "
              f"layers={len(bp.arrangement.value.layers)})")

    # --- Phase 2: cohesion checks ---
    print("\n[2/5] Cohesion checks")
    for bp in (bp_pressure, bp_release):
        report = check_cohesion(bp)
        if not report.is_clean:
            print(f"  FAIL {bp.name}: BLOCKERS:")
            for b in report.blockers:
                print(f"      - {b.rule}: {b.message}")
            raise SystemExit(1)
        warns = list(report.warnings)
        print(f"  OK {bp.name}: clean ({len(warns)} warning{'s' if len(warns) != 1 else ''})")
        for w in warns:
            print(f"      ! {w.rule}: {w.message}")

    # --- Phase 3: render .mid files ---
    print("\n[3/5] Rendering .mid files via compose_to_midi()")
    OUT_DIR.mkdir(exist_ok=True)
    for bp in (bp_pressure, bp_release):
        mid = compose_to_midi(bp, OUT_DIR / f"{bp.name}.mid")
        print(f"  OK {mid.relative_to(ROOT)} ({mid.stat().st_size} bytes)")

    # --- Phase 4: composer notes for .als injection ---
    print("\n[4/5] Compose notes for .als injection")
    notes_per_section: Dict[str, List[NoteDict]] = {}
    for bp in (bp_pressure, bp_release):
        result = compose_from_blueprint(bp)
        flat = _flatten_notes(result["tracks"])
        notes_per_section[bp.name] = flat
        print(f"  OK {bp.name}: {len(flat)} notes across {len(result['tracks'])} tracks")

    # --- Phase 5: inject into .als copy ---
    print(f"\n[5/5] Building {DST.name}")
    if SRC == DST:
        raise RuntimeError("Source and destination must differ")
    shutil.copy(SRC, DST)
    print(f"  OK Copied Template.als -> {DST.name}")

    with gzip.open(DST, "rb") as f:
        xml = f.read().decode("utf-8")

    xml = _set_project_tempo(xml, PROJECT_TEMPO)
    print(f"  OK Project tempo set to {PROJECT_TEMPO} BPM")

    # Color codes: 4 = orange (Pressure, tense), 14 = violet (Release, heavy)
    pressure_clip = _build_midi_clip(
        clip_id=1000,
        start_beat=0,
        length_beat=SECTION_LENGTH_BEATS,
        name="Pressure",
        color=4,
        notes=notes_per_section["Pressure"],
    )
    release_clip = _build_midi_clip(
        clip_id=1001,
        start_beat=SECTION_LENGTH_BEATS,
        length_beat=SECTION_LENGTH_BEATS,
        name="Release",
        color=14,
        notes=notes_per_section["Release"],
    )

    xml = _inject_clips_into_track(xml, midi_track_id=12, clips=[pressure_clip, release_clip])
    print(f"  OK Injected 2 MidiClips into MidiTrack Id=12 "
          f"(Pressure @ beat 0, Release @ beat {SECTION_LENGTH_BEATS})")

    # XML sanity: parse the full document before writing.
    ET.fromstring(xml)
    print(f"  OK XML parses cleanly via ET.fromstring")

    # Single gzip write — Option A from ALS_MANIPULATION_GUIDE.md
    with gzip.open(DST, "wb", compresslevel=9) as f:
        f.write(xml.encode("utf-8"))

    # Post-write verification (mandatory per docs/CLAUDE_PROJECT.md piege #4)
    with gzip.open(DST, "rb") as f:
        head = f.read(80)
    if not head.startswith(b"<?xml"):
        raise RuntimeError(
            f"Post-write check FAILED: decompressed head = {head[:30]!r} "
            f"(expected '<?xml'). Possible double-gzip."
        )
    print(f"  OK Post-write check: gunzip head starts with <?xml")
    print(f"  OK Final size: {DST.stat().st_size} bytes")
    print(f"\n=== DONE ===")
    print(f"Output: {DST}")


if __name__ == "__main__":
    main()
