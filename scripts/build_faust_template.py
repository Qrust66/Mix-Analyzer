"""Build an experimental Ableton arrangement based on Mick Gordon's "Faust".

Reads `ableton/projects/Template/Template Project/Template.als` (empty 4-track
template), and writes a new `.als` alongside it with:

- Tempo set to 115 BPM (4/4)
- Named locators for each song section (Intro, Build, Verse, Drop, ...)
- 13 empty MIDI tracks covering the industrial / metal / electronic palette
- Empty MIDI clips placed in the arrangement at the sections each track plays

The goal is a structural scaffold: no melodies, no devices — only the song map
so the user can write ideas guided by a precise arrangement they enjoy.
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
TRACKS = [
    ("Kick",           2,  ["Verse 1", "Pre-Drop 1", "Drop 1", "Verse 2", "Pre-Drop 2", "Drop 2", "Final Drop"]),
    ("Snare",          3,  ["Verse 1", "Pre-Drop 1", "Drop 1", "Verse 2", "Pre-Drop 2", "Drop 2", "Final Drop"]),
    ("Hats",           4,  ["Build 1", "Verse 1", "Pre-Drop 1", "Drop 1", "Break", "Verse 2", "Pre-Drop 2", "Drop 2", "Final Drop"]),
    ("Metal Perc",     5,  ["Build 1", "Drop 1", "Verse 2", "Drop 2", "Final Drop"]),
    ("Sub Bass",       8,  ["Build 1", "Verse 1", "Pre-Drop 1", "Drop 1", "Verse 2", "Pre-Drop 2", "Drop 2", "Bridge", "Final Drop"]),
    ("Distorted Bass", 11, ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Final Drop"]),
    ("Lead Synth",     12, ["Pre-Drop 1", "Drop 1", "Drop 2", "Final Drop"]),
    ("Pad",            14, ["Intro", "Build 1", "Verse 1", "Pre-Drop 1", "Drop 1", "Break", "Verse 2", "Pre-Drop 2", "Drop 2", "Bridge", "Final Drop", "Outro"]),
    ("Arp",            15, ["Verse 2", "Pre-Drop 2", "Drop 2", "Bridge", "Final Drop"]),
    ("Vocal",          16, ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Bridge", "Final Drop"]),
    ("Vocal FX",       17, ["Build 1", "Break", "Drop 1", "Drop 2", "Bridge", "Final Drop", "Outro"]),
    ("Riser FX",       9,  ["Pre-Drop 1", "Pre-Drop 2"]),
    ("Noise/Texture",  19, ["Intro", "Build 1", "Break", "Bridge", "Outro"]),
]


# --- MIDI clip template ----------------------------------------------------

def empty_midi_clip(clip_id: int, start: int, length: int, name: str, color: int) -> str:
    end = start + length
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
		<KeyTracks />
		<PerNoteEventStore>
			<EventLists />
		</PerNoteEventStore>
		<NoteProbabilityGroups />
		<ProbabilityGroupIdGenerator>
			<NextId Value="1" />
		</ProbabilityGroupIdGenerator>
		<NoteIdGenerator>
			<NextId Value="1" />
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
        for slot_idx, section_name in enumerate(active_sections):
            start, length = SECTION_BY_NAME[section_name]
            clips.append(empty_midi_clip(
                clip_id=slot_idx,
                start=start,
                length=length,
                name=section_name,
                color=color,
            ))
        clone = inject_clips(clone, clips, track_idx=i)
        new_tracks.append(clone)
        print(f"  Track #{i + 1:2d}: {name:<15} color={color:2d}  clips={len(clips)}")

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
