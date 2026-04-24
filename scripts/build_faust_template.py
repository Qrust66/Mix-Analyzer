"""Build an experimental Ableton arrangement based on Mick Gordon's "Faust".

Reads `ableton/projects/Template/Template Project/Template.als` (empty 4-track
template), and writes a new `.als` alongside it with:

- Tempo set to 115 BPM (4/4)
- Named locators for each song section (Intro, Build, Verse, Drop, ...)
- 13 MIDI tracks covering the industrial / metal / electronic palette
- MIDI clips placed in the arrangement at the sections each track plays,
  pre-filled with original note patterns in D minor inspired by the rhythmic
  feel of the genre (no notes copied from any protected work)

Pattern intensity ramps with section role: intro/break = drones only, verses =
groove, pre-drops = tension build, drops = full arrangement.
"""

from __future__ import annotations

import gzip
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Template.als"
DST = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Faust_Structure.als"

TEMPO = 115

# (name, start_beat, length_beat) — 4/4, one bar = 4 beats
SECTIONS = [
    ("Intro",      0,   32),   # bars 1-8
    ("Build 1",    32,  32),   # bars 9-16
    ("Verse 1",    64,  64),   # bars 17-32
    ("Pre-Drop 1", 128, 32),   # bars 33-40
    ("Drop 1",     160, 64),   # bars 41-56
    ("Break",      224, 32),   # bars 57-64
    ("Verse 2",    256, 64),   # bars 65-80
    ("Pre-Drop 2", 320, 32),   # bars 81-88
    ("Drop 2",     352, 64),   # bars 89-104
    ("Bridge",     416, 64),   # bars 105-120
    ("Final Drop", 480, 64),   # bars 121-136
    ("Outro",      544, 32),   # bars 137-144 -> ends at 576
]

# Track list: (name, ableton_color_index, [sections_where_it_plays])
# Naming: "NN CAT Short" -> NN = read order, CAT = DRM/BAS/SYN/VOX/FX
TRACKS = [
    ("01 DRM Kick",        2,  ["Verse 1", "Pre-Drop 1", "Drop 1", "Verse 2", "Pre-Drop 2", "Drop 2", "Final Drop"]),
    ("02 DRM Snare",       3,  ["Verse 1", "Pre-Drop 1", "Drop 1", "Verse 2", "Pre-Drop 2", "Drop 2", "Final Drop"]),
    ("03 DRM Hats",        4,  ["Build 1", "Verse 1", "Pre-Drop 1", "Drop 1", "Break", "Verse 2", "Pre-Drop 2", "Drop 2", "Final Drop"]),
    ("04 DRM Metal Perc",  5,  ["Build 1", "Drop 1", "Verse 2", "Drop 2", "Final Drop"]),
    ("05 BAS Sub",         8,  ["Build 1", "Verse 1", "Pre-Drop 1", "Drop 1", "Verse 2", "Pre-Drop 2", "Drop 2", "Bridge", "Final Drop"]),
    ("06 BAS Distorted",   11, ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Final Drop"]),
    ("07 SYN Lead",        12, ["Pre-Drop 1", "Drop 1", "Drop 2", "Final Drop"]),
    ("08 SYN Pad",         14, ["Intro", "Build 1", "Verse 1", "Pre-Drop 1", "Drop 1", "Break", "Verse 2", "Pre-Drop 2", "Drop 2", "Bridge", "Final Drop", "Outro"]),
    ("09 SYN Arp",         15, ["Verse 2", "Pre-Drop 2", "Drop 2", "Bridge", "Final Drop"]),
    ("10 VOX Lead",        16, ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Bridge", "Final Drop"]),
    ("11 VOX FX",          17, ["Build 1", "Break", "Drop 1", "Drop 2", "Bridge", "Final Drop", "Outro"]),
    ("12 FX Riser",        9,  ["Pre-Drop 1", "Pre-Drop 2"]),
    ("13 FX Noise",        19, ["Intro", "Build 1", "Break", "Bridge", "Outro"]),
]


# --- Note pattern generators (original, D minor) ---------------------------

# D natural minor: D E F G A Bb C
# MIDI reference (C3 = 60 convention): D2=38, D3=50, D4=62, D5=74
D_MINOR = [38, 40, 41, 43, 45, 46, 48]  # D E F G A Bb C (octave D2..)

# Section intensity (0 = ambient, 4 = peak)
INTENSITY = {
    "Intro": 0, "Outro": 0,
    "Break": 1, "Build 1": 1, "Bridge": 1,
    "Verse 1": 2, "Verse 2": 2,
    "Pre-Drop 1": 3, "Pre-Drop 2": 3,
    "Drop 1": 4, "Drop 2": 4, "Final Drop": 4,
}

# A MIDI note is (time_beat, pitch, duration_beat, velocity)
Note = tuple[float, int, float, int]


def _kick(section: str, length: int) -> list[Note]:
    """Original kick pattern — varies from half-time groove to busy syncopation."""
    notes: list[Note] = []
    level = INTENSITY[section]
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        if level == 2:  # verse: chunky half-time with a syncopated push
            notes += [(t, 36, 0.25, 112), (t + 2.5, 36, 0.125, 96), (t + 3, 36, 0.25, 108)]
        elif level == 3:  # pre-drop: steady foundation + 16th build on last bar
            notes += [(t, 36, 0.25, 108), (t + 2, 36, 0.25, 108)]
            if bar == bars - 1:
                for s in range(16):
                    notes.append((t + s * 0.25, 36, 0.1, 80 + s * 2))
        elif level == 4:  # drop: busy syncopated 4-on-the-floor feel
            notes += [
                (t, 36, 0.25, 118), (t + 0.75, 36, 0.125, 90),
                (t + 1.5, 36, 0.25, 105), (t + 2, 36, 0.25, 118),
                (t + 2.75, 36, 0.125, 92), (t + 3.5, 36, 0.125, 98),
            ]
    return notes


def _snare(section: str, length: int) -> list[Note]:
    notes: list[Note] = []
    level = INTENSITY[section]
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        # backbeat on 2 and 4 always
        notes += [(t + 1, 38, 0.25, 110), (t + 3, 38, 0.25, 114)]
        if level == 4:  # ghost notes in drops
            notes += [(t + 2.75, 38, 0.0625, 60), (t + 3.75, 38, 0.0625, 70)]
        if level == 3 and bar == bars - 1:
            # snare roll on the last bar of a pre-drop
            for s in range(8):
                notes.append((t + 2 + s * 0.25, 38, 0.1, 70 + s * 5))
    return notes


def _hats(section: str, length: int) -> list[Note]:
    notes: list[Note] = []
    level = INTENSITY[section]
    bars = length // 4
    step = 0.25 if level >= 3 else 0.5  # 16ths in drops/pre-drops, 8ths elsewhere
    for bar in range(bars):
        t = bar * 4
        steps = int(4 / step)
        for s in range(steps):
            on_beat = (s * step) % 1 == 0
            vel = 95 if on_beat else 70
            notes.append((t + s * step, 42, step * 0.5, vel))
    return notes


def _metal_perc(section: str, length: int) -> list[Note]:
    # sparse industrial accents on "& of 4" and bar 1 of every 4th bar
    notes: list[Note] = []
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        if bar % 4 == 0:
            notes.append((t, 56, 0.5, 115))  # downbeat metal hit
        notes.append((t + 3.5, 56, 0.25, 90))  # "& of 4" stab
    return notes


def _sub_bass(section: str, length: int) -> list[Note]:
    # sustained roots — D1 with occasional octave drop to A0
    notes: list[Note] = []
    bars = length // 4
    # 4-bar phrase: D hold, D hold, A hold, D hold
    phrase = [26, 26, 21, 26]  # D1, D1, A0, D1
    for bar in range(bars):
        t = bar * 4
        notes.append((t, phrase[bar % 4], 4.0, 100))
    return notes


def _distorted_bass(section: str, length: int) -> list[Note]:
    # follows kick rhythmically, pitches walk around the root
    level = INTENSITY[section]
    notes: list[Note] = []
    bars = length // 4
    # 2-bar pattern of root variations: D, D, A, D  |  D, F, D, C
    phrase_a = [38, 38, 33, 38]
    phrase_b = [38, 41, 38, 36]  # includes C2=36 for tension
    for bar in range(bars):
        t = bar * 4
        p = phrase_a if (bar // 2) % 2 == 0 else phrase_b
        if level == 2:  # verse: hits on 1 and 3
            notes += [(t, p[0], 0.25, 108), (t + 2, p[2], 0.5, 108)]
        elif level >= 3:  # drop: lock with kick syncopation
            notes += [
                (t, p[0], 0.25, 115), (t + 0.75, p[1], 0.125, 90),
                (t + 1.5, p[2], 0.25, 105), (t + 2, p[2], 0.25, 115),
                (t + 2.75, p[3], 0.125, 95), (t + 3.5, p[0], 0.125, 98),
            ]
    return notes


def _lead(section: str, length: int) -> list[Note]:
    # 2-bar melodic motif in Dm, repeated (original, not transcribed)
    # Bar 1: D-F-A climb with held high D. Bar 2: descending C-Bb-A answer.
    motif = [
        (0.0, 62, 0.5, 105),   # D4
        (0.5, 65, 0.5, 100),   # F4
        (1.0, 69, 1.0, 110),   # A4 (quarter-dotted)
        (2.5, 74, 1.5, 115),   # D5 (held)
        (4.0, 72, 1.0, 100),   # C5
        (5.0, 70, 1.0, 100),   # Bb4
        (6.0, 69, 2.0, 108),   # A4 held
    ]
    notes: list[Note] = []
    bars = length // 4
    for phrase_i in range(bars // 2):
        base_t = phrase_i * 8
        for (dt, pitch, dur, vel) in motif:
            notes.append((base_t + dt, pitch, dur, vel))
    return notes


def _pad(section: str, length: int) -> list[Note]:
    # 4-bar chord progression: Dm -> Bb -> F -> Gm, each chord held 4 bars
    # Voicings (3-note, mid register)
    chords = [
        [50, 53, 57],  # Dm   (D3 F3 A3)
        [50, 53, 58],  # Bb   (D3 F3 Bb3)  — shared top of Dm
        [53, 57, 60],  # F    (F3 A3 C4)
        [50, 55, 58],  # Gm   (D3 G3 Bb3)
    ]
    notes: list[Note] = []
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        chord = chords[bar % 4]
        for pitch in chord:
            notes.append((t, pitch, 4.0, 70))  # soft, sustained
    return notes


def _arp(section: str, length: int) -> list[Note]:
    # 16th-note arpeggio in Dm: D F A C D A F D (8 notes per beat cluster)
    pitches = [62, 65, 69, 72, 74, 69, 65, 62]  # D F A C D A F D
    notes: list[Note] = []
    total_steps = int(length / 0.25)
    for s in range(total_steps):
        t = s * 0.25
        pitch = pitches[s % len(pitches)]
        vel = 95 if s % 4 == 0 else 72  # accent on downbeats
        notes.append((t, pitch, 0.2, vel))
    return notes


def _vocal(section: str, length: int) -> list[Note]:
    # long sustained tones as a guide — 1 note per 2 bars, moving in Dm
    phrase = [62, 65, 69, 65]  # D4 F4 A4 F4
    notes: list[Note] = []
    bars = length // 4
    for i, bar in enumerate(range(0, bars, 2)):
        t = bar * 4
        notes.append((t, phrase[i % len(phrase)], 8.0, 85))
    return notes


def _vocal_fx(section: str, length: int) -> list[Note]:
    # sparse high accents every 4 bars
    notes: list[Note] = []
    bars = length // 4
    for bar in range(0, bars, 4):
        t = bar * 4
        notes.append((t, 74, 1.0, 95))   # D5 stab
        notes.append((t + 2, 77, 0.5, 85))  # F5 short
    return notes


def _riser(section: str, length: int) -> list[Note]:
    # single held note from start to end of the section (the synth patch
    # is expected to produce the riser timbre via automation)
    return [(0.0, 60, float(length), 90)]


def _noise(section: str, length: int) -> list[Note]:
    # single long drone
    return [(0.0, 48, float(length), 75)]


NOTE_GENERATORS = {
    "01 DRM Kick": _kick, "02 DRM Snare": _snare, "03 DRM Hats": _hats,
    "04 DRM Metal Perc": _metal_perc,
    "05 BAS Sub": _sub_bass, "06 BAS Distorted": _distorted_bass,
    "07 SYN Lead": _lead, "08 SYN Pad": _pad, "09 SYN Arp": _arp,
    "10 VOX Lead": _vocal, "11 VOX FX": _vocal_fx,
    "12 FX Riser": _riser, "13 FX Noise": _noise,
}


def gen_notes(track: str, section: str, length: int) -> list[Note]:
    gen = NOTE_GENERATORS[track]
    out = gen(section, length)
    # Clamp any note that would overshoot the clip length
    clipped = []
    for (t, p, d, v) in out:
        if t >= length:
            continue
        clipped.append((t, p, min(d, length - t), v))
    return clipped


def notes_to_keytracks_xml(notes: list[Note], indent: str) -> tuple[str, int]:
    """Group notes by pitch and build a `<KeyTracks>` XML block.

    Returns (xml_string, next_note_id) where next_note_id is the value to
    write into `<NoteIdGenerator><NextId>` for the clip.
    """
    if not notes:
        return f"{indent}<KeyTracks />", 1

    by_pitch: dict[int, list[tuple[float, float, int]]] = {}
    for t, pitch, dur, vel in notes:
        by_pitch.setdefault(pitch, []).append((t, dur, vel))

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


# --- MIDI clip template ----------------------------------------------------

def midi_clip(clip_id: int, start: int, length: int, name: str, color: int,
              notes: list[Note] | None = None) -> str:
    end = start + length
    # The <Notes><KeyTracks> block is placed inside the MidiClip. KeyTracks
    # are indented 3 tabs relative to the clip (matching the rest of the
    # f-string indentation here with "\t\t\t").
    kt_indent = "\t\t"
    kt_xml, next_nid = notes_to_keytracks_xml(notes or [], kt_indent)
    return f"""<MidiClip Id="{clip_id}" Time="{start}">
	<LomId Value="0" />
	<LomIdView Value="0" />
	<CurrentStart Value="{start}" />
	<CurrentEnd Value="{end}" />
	<Loop>
		<LoopStart Value="0" />
		<LoopEnd Value="{length}" />
		<StartRelative Value="0" />
		<LoopOn Value="false" />
		<OutMarker Value="{length}" />
		<HiddenLoopStart Value="0" />
		<HiddenLoopEnd Value="{length}" />
	</Loop>
	<Name Value="{name}" />
	<Annotation Value="" />
	<Color Value="{color}" />
	<LaunchMode Value="0" />
	<LaunchQuantisation Value="0" />
	<TimeSignature>
		<TimeSignatures>
			<RemoteableTimeSignature Id="0">
				<Numerator Value="4" />
				<Denominator Value="4" />
				<Time Value="0" />
			</RemoteableTimeSignature>
		</TimeSignatures>
	</TimeSignature>
	<Envelopes>
		<Envelopes />
	</Envelopes>
	<ScrollerTimePreserver>
		<LeftTime Value="0" />
		<RightTime Value="{length}" />
	</ScrollerTimePreserver>
	<TimeSelection>
		<AnchorTime Value="0" />
		<OtherTime Value="0" />
	</TimeSelection>
	<Legato Value="false" />
	<Ram Value="false" />
	<GrooveSettings>
		<GrooveId Value="-1" />
	</GrooveSettings>
	<Disabled Value="false" />
	<VelocityAmount Value="0" />
	<FollowAction>
		<FollowTime Value="4" />
		<IsLinked Value="true" />
		<LoopIterations Value="1" />
		<FollowActionA Value="4" />
		<FollowActionB Value="0" />
		<FollowChanceA Value="100" />
		<FollowChanceB Value="0" />
		<JumpIndexA Value="1" />
		<JumpIndexB Value="1" />
		<FollowActionEnabled Value="false" />
	</FollowAction>
	<Grid>
		<FixedNumerator Value="1" />
		<FixedDenominator Value="16" />
		<GridIntervalPixel Value="20" />
		<Ntoles Value="2" />
		<SnapToGrid Value="true" />
		<Fixed Value="false" />
	</Grid>
	<FreezeStart Value="0" />
	<FreezeEnd Value="0" />
	<IsWarped Value="true" />
	<TakeId Value="1" />
	<IsInKey Value="true" />
	<ScaleInformation>
		<Root Value="0" />
		<Name Value="0" />
	</ScaleInformation>
	<Notes>
{kt_xml}
		<PerNoteEventStore>
			<EventLists />
		</PerNoteEventStore>
		<NoteProbabilityGroups />
		<ProbabilityGroupIdGenerator>
			<NextId Value="1" />
		</ProbabilityGroupIdGenerator>
		<NoteIdGenerator>
			<NextId Value="{next_nid}" />
		</NoteIdGenerator>
	</Notes>
	<BankSelectCoarse Value="-1" />
	<BankSelectFine Value="-1" />
	<ProgramChange Value="-1" />
	<NoteEditorFoldInZoom Value="-1" />
	<NoteEditorFoldInScroll Value="0" />
	<NoteEditorFoldOutZoom Value="128" />
	<NoteEditorFoldOutScroll Value="-67" />
	<NoteEditorFoldScaleZoom Value="-1" />
	<NoteEditorFoldScaleScroll Value="0" />
	<NoteSpellingPreference Value="0" />
	<AccidentalSpellingPreference Value="3" />
	<PreferFlatRootNote Value="false" />
	<ExpressionGrid>
		<FixedNumerator Value="1" />
		<FixedDenominator Value="16" />
		<GridIntervalPixel Value="20" />
		<Ntoles Value="2" />
		<SnapToGrid Value="false" />
		<Fixed Value="false" />
	</ExpressionGrid>
</MidiClip>"""


# --- helpers ----------------------------------------------------------------

def reindent(block: str, target_indent: str) -> str:
    """Indent every line of `block` so its first line sits at `target_indent`.

    The block is assumed to use tabs for indentation. The first line's indent
    is treated as the baseline; all following lines keep their relative depth.
    """
    lines = block.split("\n")
    # baseline: leading tabs of first non-empty line
    base = ""
    for l in lines:
        if l.strip():
            base = l[: len(l) - len(l.lstrip("\t"))]
            break
    out = []
    for l in lines:
        if not l.strip():
            out.append(l)
            continue
        rel = l[len(base):] if l.startswith(base) else l
        out.append(target_indent + rel)
    return "\n".join(out)


def shift_big_ids(block: str, offset: int, min_val: int = 4000) -> str:
    """Add `offset` to every Id/Value integer >= `min_val` found in `block`.

    This is how we remap a cloned MidiTrack so its PointeeId / AutomationTarget /
    Pointee references stay unique across clones.
    """
    def sub(m: re.Match) -> str:
        key, val = m.group(1), int(m.group(2))
        if val >= min_val:
            return f'{key}="{val + offset}"'
        return m.group(0)
    return re.sub(r'(Id|Value|Pointee Id)="(\d+)"', sub, block)


def build_locators_block(indent: str = "\t\t") -> str:
    """Return the <Locators> XML block populated with named section markers."""
    inner = []
    for i, (name, start, _length) in enumerate(SECTIONS, start=1):
        inner.append(
            f"{indent}\t\t<Locator Id=\"{i}\">\n"
            f"{indent}\t\t\t<LomId Value=\"0\" />\n"
            f"{indent}\t\t\t<Time Value=\"{start}\" />\n"
            f"{indent}\t\t\t<Name Value=\"{name}\" />\n"
            f"{indent}\t\t\t<Annotation Value=\"\" />\n"
            f"{indent}\t\t\t<IsSongStart Value=\"false\" />\n"
            f"{indent}\t\t</Locator>"
        )
    return (
        f"{indent}<Locators>\n"
        f"{indent}\t<Locators>\n"
        + "\n".join(inner) + "\n"
        f"{indent}\t</Locators>\n"
        f"{indent}</Locators>"
    )


def rename_track(track_xml: str, name: str, color: int, new_track_id: int) -> str:
    """Rename a cloned MidiTrack and reassign its outer Id + Color."""
    # Outer <MidiTrack Id="..."> — first occurrence only
    track_xml = re.sub(
        r'<MidiTrack Id="\d+"', f'<MidiTrack Id="{new_track_id}"', track_xml, count=1,
    )
    # <EffectiveName Value="..." /> inside the first <Name> block
    track_xml = re.sub(
        r'<EffectiveName Value="[^"]*"', f'<EffectiveName Value="{name}"', track_xml, count=1,
    )
    # <Color Value="N" /> — first <Color ...> after the track open. The first
    # one is always the track color (before any device chain).
    track_xml = re.sub(
        r'<Color Value="\d+"', f'<Color Value="{color}"', track_xml, count=1,
    )
    return track_xml


def inject_clips(track_xml: str, clips: list[str], track_idx: int) -> str:
    """Replace the empty `<ArrangerAutomation><Events />` with populated Events."""
    # The Events tag we target is a child of ArrangerAutomation (inside
    # ClipTimeable, inside MainSequencer). In the template it's always
    # self-closing because the track is empty.
    m = re.search(
        r'(<ArrangerAutomation>\s*)<Events />',
        track_xml,
    )
    if not m:
        raise RuntimeError(f"Track #{track_idx}: couldn't find <Events /> inside ArrangerAutomation")

    # Compute indent from the line containing <Events />
    evt_pos = m.start(0) + len(m.group(1))
    line_start = track_xml.rfind("\n", 0, evt_pos) + 1
    indent = track_xml[line_start:evt_pos]
    inner_indent = indent + "\t"

    reindented = [reindent(c, inner_indent) for c in clips]
    replacement = (
        f"{m.group(1)}<Events>\n"
        + "\n".join(reindented) + "\n"
        + f"{indent}</Events>"
    )
    return track_xml[:m.start(0)] + replacement + track_xml[m.end(0):]


# --- main -------------------------------------------------------------------

def main() -> None:
    print(f"Reading: {SRC}")
    with gzip.open(SRC, "rb") as f:
        xml = f.read().decode("utf-8")

    # 1) Tempo 120 -> 115 (only the Manual value inside <Tempo>)
    tempo_match = re.search(r'(<Tempo>.*?<Manual Value=")(\d+)(")', xml, re.DOTALL)
    assert tempo_match, "Tempo block not found"
    xml = xml[: tempo_match.start(2)] + str(TEMPO) + xml[tempo_match.end(2):]
    print(f"  Tempo set to {TEMPO} BPM")

    # 2) Locators: replace `<Locators>\n\t<Locators />\n</Locators>` with named ones
    loc_pat = re.compile(r'([ \t]*)<Locators>\s*<Locators />\s*</Locators>', re.DOTALL)
    m_loc = loc_pat.search(xml)
    assert m_loc, "Empty <Locators> block not found"
    indent = m_loc.group(1)
    xml = xml[: m_loc.start()] + build_locators_block(indent) + xml[m_loc.end():]
    print(f"  Locators: {len(SECTIONS)} named markers")

    # 3) Grab MidiTrack 12 (full line, including leading indent) as template
    #    and find where the original Tracks region we want to replace ends
    #    (just before ReturnTrack 2).
    line_start_of = lambda pos: xml.rfind("\n", 0, pos) + 1
    m_t12 = re.search(r'<MidiTrack Id="12"', xml)
    t12_pos = line_start_of(m_t12.start())
    m_r2 = re.search(r'<ReturnTrack Id="2"', xml)
    r2_pos = line_start_of(m_r2.start())
    # Find end of MidiTrack 12: the line containing its `</MidiTrack>` closer
    m_t12_end = xml.find("</MidiTrack>", m_t12.start())
    m_t13_open = xml.find('<MidiTrack Id="13"', m_t12_end)
    t12_end_line = xml.rfind("\n", 0, m_t13_open) + 1  # start of line just after </MidiTrack>
    template_track = xml[t12_pos:t12_end_line]
    print(f"  Template MidiTrack: {len(template_track)} chars")

    # 4) Build the 13 new MIDI tracks by cloning the template
    ID_OFFSET_BASE = 84170       # shifts template big IDs from [15830..22155] into [100000..106325]
    ID_OFFSET_STEP = 10000       # each clone gets its own 10 000-wide band
    SECTION_BY_NAME = {name: (start, length) for name, start, length in SECTIONS}
    new_tracks: list[str] = []

    for i, (name, color, active_sections) in enumerate(TRACKS):
        clone = template_track
        offset = ID_OFFSET_BASE + i * ID_OFFSET_STEP
        clone = shift_big_ids(clone, offset, min_val=4000)
        clone = rename_track(clone, name, color, new_track_id=100 + i)

        # Build clips for this track, unique Id per track starts at 0
        clips = []
        note_total = 0
        for slot_idx, section_name in enumerate(active_sections):
            start, length = SECTION_BY_NAME[section_name]
            notes = gen_notes(name, section_name, length)
            note_total += len(notes)
            clips.append(midi_clip(
                clip_id=slot_idx,
                start=start,
                length=length,
                name=section_name,
                color=color,
                notes=notes,
            ))
        clone = inject_clips(clone, clips, track_idx=i)
        new_tracks.append(clone)
        print(f"  Track #{i + 1:2d}: {name:<15} color={color:2d}  clips={len(clips):2d}  notes={note_total}")

    # 5) Splice: replace [t12_pos .. r2_pos] with the 13 new tracks concatenated
    xml = xml[:t12_pos] + "".join(new_tracks) + xml[r2_pos:]

    # 6) Bump NextPointeeId well above everything we allocated
    max_used = ID_OFFSET_BASE + len(TRACKS) * ID_OFFSET_STEP + 22155 + 1
    xml = re.sub(
        r'(<NextPointeeId Value=")(\d+)(")',
        lambda m: m.group(1) + str(max_used + 100000) + m.group(3),
        xml,
        count=1,
    )

    # 7) Sanity: XML parses
    try:
        ET.fromstring(xml)
    except ET.ParseError as e:
        raise SystemExit(f"Generated XML is invalid: {e}")
    print(f"  XML parses OK ({len(xml)} chars)")

    # 8) Write (single-layer gzip)
    DST.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(DST, "wb", compresslevel=9) as f:
        f.write(xml.encode("utf-8"))

    # 9) Post-write verification (Claude.md rule: first bytes must be <?xml)
    with gzip.open(DST, "rb") as f:
        head = f.read(80)
    assert head.startswith(b"<?xml"), "Double gzip detected"
    size = DST.stat().st_size
    print(f"Wrote: {DST}  ({size:,} bytes)")


if __name__ == "__main__":
    main()
