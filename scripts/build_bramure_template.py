"""Build `Bramure.als` — organic angry/wry/intense arrangement scaffold.

Brief: vibe blend of Radiohead (cerebral off-kilter), NIN (industrial dark),
Nirvana (raw second-degree), QOTSA (heavy swagger). Tempo 118 BPM. Mixed
metres: VERSES in 7/4 (Money-style asymmetric stagger), DROPS in 4/4
(landing/release), BREAK and BRIDGE in 6/8 (ternary breath). Modal blend
C# Locrian (i°, instability — the "tabarnak") on verses + D Mixolydian
(b7 with major root, bittersweet relief) on drops. The half-step pivot
C#->D is the primary CLASH that resolves because shared tones (E F# G A B)
keep the line.

Design rules:
- 26 tracks. 2 KICKS (A thumpy + B snap, perceived at different moments).
  2 SNARES (A claqué + B air/ghost layer). 3 BASSES (sub/punch/distort).
- Audacity meta-rule: silence as a feature. Repeated notes are OK.
  Don't fill every 16th. Punch + breathe.
- After writing each pattern, REVIEW and push it ONE step further (not a
  loop — once. Then ship it.)
- Per-section TIME SIGNATURE stored on each clip (since project-level
  metre changes are fragile — local-clip metre is the safe path).

STEPS A1-A2/9 — constants + ALS helpers + main. Empty clips, time
signature locked per clip (so a 7/4 Verse clip plays in 7/4 even if
project default stays 4/4).
"""

from __future__ import annotations

import gzip
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Template.als"
DST = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Bramure.als"

TEMPO = 118

# (name, start_beat, length_beat, numerator, denominator).
# Beats are absolute (cumulative). 7/4 bar = 7 beats, 4/4 = 4 beats,
# 6/8 = 3 beats (six 8ths counted as three quarter-beats in Ableton).
#
# Layout (~4:00 @ 118 BPM):
#   Intro       4 bars 4/4  =  16 beats   t=  0
#   Verse 1    12 bars 7/4  =  84 beats   t= 16   ← angry asymmetric stagger
#   Pre-Drop 1  4 bars 4/4  =  16 beats   t=100   ← recover the meter
#   Drop 1     16 bars 4/4  =  64 beats   t=116   ← punch + release
#   Break       6 bars 6/8  =  18 beats   t=180   ← ternary breath
#   Verse 2    12 bars 7/4  =  84 beats   t=198
#   Pre-Drop 2  4 bars 4/4  =  16 beats   t=282
#   Drop 2     16 bars 4/4  =  64 beats   t=298   ← modal pivot to D Mixolydian
#   Bridge      8 bars 6/8  =  24 beats   t=362
#   Final Drop 16 bars 4/4  =  64 beats   t=386   ← clash + sustain
#   Outro       6 bars 4/4  =  24 beats   t=450
SECTIONS = [
    ("Intro",       0,   16,  4, 4),
    ("Verse 1",     16,  84,  7, 4),
    ("Pre-Drop 1",  100, 16,  4, 4),
    ("Drop 1",      116, 64,  4, 4),
    ("Break",       180, 18,  6, 8),
    ("Verse 2",     198, 84,  7, 4),
    ("Pre-Drop 2",  282, 16,  4, 4),
    ("Drop 2",      298, 64,  4, 4),
    ("Bridge",      362, 24,  6, 8),
    ("Final Drop",  386, 64,  4, 4),
    ("Outro",       450, 24,  4, 4),
]

# 26 tracks. Field order: (name, ableton_color, preset_hint, active_sections).
# Preset hint targets STOCK ABLETON instruments (Wavetable, Operator, Drum
# Rack) — phase C1 will attempt to swap the cloned Serum for the stock
# device when feasible; fallback = leave Serum + the hint guides a 2-click
# manual swap.
TRACKS = [
    # Drums — 9
    ("01 DRM Kick A",       2,  "Drum Rack: Kick Deep (Hybrid Studio Kit / Kick 1)",
        ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Final Drop"]),
    ("02 DRM Kick B",       2,  "Drum Rack: Kick Snap (Hybrid Studio Kit / Kick 2 high)",
        ["Pre-Drop 1", "Drop 1", "Pre-Drop 2", "Drop 2", "Final Drop"]),
    ("03 DRM Snare A",      4,  "Drum Rack: Snare Crack (Hybrid Studio / Snare 1)",
        ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Final Drop"]),
    ("04 DRM Snare B",      4,  "Drum Rack: Snare Air/Ghost (Hybrid Studio / Snare 2 brushed)",
        ["Drop 1", "Drop 2", "Final Drop"]),
    ("05 DRM Clap",         6,  "Drum Rack: Clap (909 Clap)",
        ["Drop 1", "Drop 2", "Final Drop"]),
    ("06 DRM Rim",          7,  "Drum Rack: Rimshot / Cross-stick",
        ["Verse 1", "Verse 2", "Bridge"]),
    ("07 DRM Hats",         8,  "Drum Rack: Closed Hat (Hybrid Studio / Hat tight)",
        ["Verse 1", "Pre-Drop 1", "Drop 1", "Verse 2", "Pre-Drop 2", "Drop 2", "Final Drop"]),
    ("08 DRM Open Hat",     8,  "Drum Rack: Open Hat (Hybrid Studio / Hat open)",
        ["Drop 1", "Drop 2", "Final Drop"]),
    ("09 DRM Perc",         5,  "Drum Rack: Industrial Perc (Found Sounds)",
        ["Verse 1", "Verse 2", "Bridge", "Final Drop"]),
    # Bass — 3
    ("10 BAS Sub",          14, "Operator: Sub Sine (B-Sub-Pure)",
        ["Verse 1", "Pre-Drop 1", "Drop 1", "Verse 2", "Pre-Drop 2", "Drop 2", "Bridge", "Final Drop"]),
    ("11 BAS Punch",        15, "Operator: FM Punch Bass (B-Punch-Mono)",
        ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Final Drop"]),
    ("12 BAS Distort",      16, "Wavetable: Reese Distort (B-Reese-Heavy)",
        ["Drop 1", "Drop 2", "Bridge", "Final Drop"]),
    # Synth — 6
    ("13 SYN Pad",          19, "Wavetable: Pad Movement (Strings PAD)",
        ["Intro", "Verse 1", "Pre-Drop 1", "Drop 1", "Break", "Verse 2", "Pre-Drop 2", "Drop 2", "Bridge", "Final Drop", "Outro"]),
    ("14 SYN Drone Dark",   21, "Wavetable: Cinematic Drone (PAD-Drone-Dark)",
        ["Intro", "Break", "Bridge", "Outro"]),
    ("15 SYN Lead Cry",     25, "Wavetable: Distorted Cry Lead (LEAD-Brass-Bite)",
        ["Pre-Drop 1", "Drop 1", "Drop 2", "Final Drop"]),
    ("16 SYN Lead Counter", 26, "Wavetable: Sub Octave Lead (LEAD-Hollow)",
        ["Drop 1", "Drop 2", "Bridge", "Final Drop"]),
    ("17 SYN Pluck Stab",   28, "Wavetable: Sharp Attack Pluck (KEYS-Pluck-Hard)",
        ["Verse 1", "Verse 2", "Pre-Drop 2", "Final Drop"]),
    ("18 SYN Choir Wail",   30, "Wavetable: Aah Choir (VOX-Choir-Distant)",
        ["Bridge", "Outro"]),
    # Voice — 2
    ("19 VOX Guide",        33, "Wavetable: Formant Voice (VOX-Lead-Open)",
        ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Final Drop"]),
    ("20 VOX Wail",         34, "Wavetable: Cry Voice (VOX-Wail-Long)",
        ["Bridge", "Final Drop"]),
    # FX — 6
    ("21 FX Drone",         37, "Wavetable: Sub Drone (PAD-Sub-Hold)",
        ["Intro", "Break", "Bridge", "Outro"]),
    ("22 FX Riser",         38, "Wavetable: Noise Riser (FX-Riser-White)",
        ["Pre-Drop 1", "Pre-Drop 2", "Final Drop"]),
    ("23 FX Reverse",       39, "Wavetable: Reverse Swell (FX-Reverse-Pad)",
        ["Pre-Drop 1", "Break", "Pre-Drop 2", "Bridge"]),
    ("24 FX Impact",        40, "Wavetable: Impact / Hit (FX-Impact-Sub)",
        ["Pre-Drop 1", "Drop 1", "Pre-Drop 2", "Drop 2", "Final Drop"]),
    ("25 FX Sub Boom",      41, "Operator: 808 Sub Boom (B-Sub-808)",
        ["Drop 1", "Drop 2", "Final Drop"]),
    ("26 FX Texture",       42, "Wavetable: Granular Noise (TEXTURE-Grain)",
        ["Verse 1", "Bridge", "Outro"]),
]


# --- Note pattern generators (all empty stubs for STEP A1) ----------------

# A MIDI note is (time_beat, pitch, duration_beat, velocity)
Note = tuple[float, int, float, int]


def _noop(section: str, length: int) -> list[Note]:
    return []


NOTE_GENERATORS: dict[str, "callable"] = {name: _noop for (name, *_) in TRACKS}


def gen_notes(track: str, section: str, length: int) -> list[Note]:
    gen = NOTE_GENERATORS[track]
    out = gen(section, length)
    clipped = []
    for (t, p, d, v) in out:
        if t >= length:
            continue
        clipped.append((t, p, min(d, length - t), v))
    return clipped


# --- ALS helpers -----------------------------------------------------------

def reindent(block: str, target_indent: str) -> str:
    lines = block.split("\n")
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
    """Shift Id/Value/PointeeId integers >= min_val by `offset`, but skip
    content inside <PluginDesc>...</PluginDesc> (Serum 2 binary state)."""
    regions = []
    for m in re.finditer(r'<PluginDesc', block):
        s = m.start()
        e = block.find('</PluginDesc>', s)
        if e >= 0:
            regions.append((s, e + len('</PluginDesc>')))

    def _shift_chunk(chunk: str) -> str:
        def sub(m: re.Match) -> str:
            key, val = m.group(1), int(m.group(2))
            if val >= min_val:
                return f'{key}="{val + offset}"'
            return m.group(0)
        return re.sub(r'(Id|Value|Pointee Id)="(\d+)"', sub, chunk)

    if not regions:
        return _shift_chunk(block)
    out = []
    cursor = 0
    for s, e in sorted(regions):
        out.append(_shift_chunk(block[cursor:s]))
        out.append(block[s:e])
        cursor = e
    out.append(_shift_chunk(block[cursor:]))
    return "".join(out)


def build_locators_block(indent: str = "\t\t") -> str:
    inner = []
    for i, (name, start, _length, _num, _denom) in enumerate(SECTIONS, start=1):
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
    track_xml = re.sub(r'<MidiTrack Id="\d+"',
                       f'<MidiTrack Id="{new_track_id}"', track_xml, count=1)
    track_xml = re.sub(r'<EffectiveName Value="[^"]*"',
                       f'<EffectiveName Value="{name}"', track_xml, count=1)
    track_xml = re.sub(r'<Color Value="\d+"',
                       f'<Color Value="{color}"', track_xml, count=1)
    return track_xml


def set_plugin_username(track_xml: str, preset_hint: str) -> str:
    """Set the host-level <UserName> of the first PluginDevice."""
    m = re.search(r'<PluginDevice\s+Id="\d+"[^>]*>', track_xml)
    if not m:
        return track_xml
    pd_end = track_xml.find('</PluginDevice>', m.end())
    un_match = re.search(r'<UserName Value="[^"]*" />', track_xml[m.end():pd_end])
    if not un_match:
        return track_xml
    s = m.end() + un_match.start()
    e = m.end() + un_match.end()
    safe = (preset_hint
            .replace('&', '&amp;').replace('"', '&quot;')
            .replace('<', '&lt;').replace('>', '&gt;'))
    return track_xml[:s] + f'<UserName Value="{safe}" />' + track_xml[e:]


def inject_clips(track_xml: str, clips: list[str], track_idx: int) -> str:
    m = re.search(r'(<ArrangerAutomation>\s*)<Events />', track_xml)
    if not m:
        raise RuntimeError(f"Track #{track_idx}: no <Events /> in ArrangerAutomation")
    evt_pos = m.start(0) + len(m.group(1))
    line_start = track_xml.rfind("\n", 0, evt_pos) + 1
    indent = track_xml[line_start:evt_pos]
    inner_indent = indent + "\t"
    reindented = [reindent(c, inner_indent) for c in clips]
    replacement = (f"{m.group(1)}<Events>\n"
                   + "\n".join(reindented) + "\n"
                   + f"{indent}</Events>")
    return track_xml[:m.start(0)] + replacement + track_xml[m.end(0):]


def notes_to_keytracks_xml(notes: list[Note], indent: str) -> tuple[str, int]:
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


def midi_clip(clip_id: int, start: int, length: int, name: str, color: int,
              num: int = 4, denom: int = 4,
              notes: list[Note] | None = None) -> str:
    """Build a MidiClip XML block. The TimeSignature is locked per clip,
    so a 7/4 Verse clip plays in 7/4 even if project default stays 4/4."""
    end = start + length
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
				<Numerator Value="{num}" />
				<Denominator Value="{denom}" />
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


# --- Main ------------------------------------------------------------------

def main() -> None:
    print(f"Reading: {SRC}")
    with gzip.open(SRC, "rb") as f:
        xml = f.read().decode("utf-8")

    # Tempo
    m_tempo = re.search(r'(<Tempo>.*?<Manual Value=")(\d+)(")', xml, re.DOTALL)
    assert m_tempo, "Tempo block not found"
    xml = xml[: m_tempo.start(2)] + str(TEMPO) + xml[m_tempo.end(2):]
    print(f"  Tempo: {TEMPO} BPM")

    # Locators
    loc_pat = re.compile(r'([ \t]*)<Locators>\s*<Locators />\s*</Locators>', re.DOTALL)
    m_loc = loc_pat.search(xml)
    assert m_loc, "Empty <Locators> block not found"
    indent = m_loc.group(1)
    xml = xml[: m_loc.start()] + build_locators_block(indent) + xml[m_loc.end():]
    print(f"  Locators: {len(SECTIONS)} sections")

    # Identify MidiTrack 12 (with Serum 2) as clone template
    line_start_of = lambda pos: xml.rfind("\n", 0, pos) + 1
    m_t12 = re.search(r'<MidiTrack Id="12"', xml)
    t12_pos = line_start_of(m_t12.start())
    m_r2 = re.search(r'<ReturnTrack Id="2"', xml)
    r2_pos = line_start_of(m_r2.start())
    m_t12_end = xml.find("</MidiTrack>", m_t12.start())
    m_t13_open = xml.find('<MidiTrack Id="13"', m_t12_end)
    t12_end_line = xml.rfind("\n", 0, m_t13_open) + 1
    template_track = xml[t12_pos:t12_end_line]
    print(f"  Template MidiTrack (with Serum 2): {len(template_track):,} chars")

    # Clone N tracks
    ID_OFFSET_BASE = 84170
    ID_OFFSET_STEP = 10000
    SECTION_BY_NAME = {name: (start, length, num, denom)
                       for name, start, length, num, denom in SECTIONS}
    new_tracks: list[str] = []

    for i, (name, color, preset_hint, active_sections) in enumerate(TRACKS):
        clone = template_track
        offset = ID_OFFSET_BASE + i * ID_OFFSET_STEP
        clone = shift_big_ids(clone, offset, min_val=4000)
        clone = rename_track(clone, name, color, new_track_id=300 + i)
        clone = set_plugin_username(clone, preset_hint)

        clips = []
        note_total = 0
        for slot_idx, section_name in enumerate(active_sections):
            start, length, num, denom = SECTION_BY_NAME[section_name]
            notes = gen_notes(name, section_name, length)
            note_total += len(notes)
            clips.append(midi_clip(
                clip_id=slot_idx, start=start, length=length,
                name=section_name, color=color,
                num=num, denom=denom,
                notes=notes,
            ))
        clone = inject_clips(clone, clips, track_idx=i)
        new_tracks.append(clone)
        print(f"  #{i+1:2d} {name:<22} clips={len(clips):2d} notes={note_total:4d}")

    xml = xml[:t12_pos] + "".join(new_tracks) + xml[r2_pos:]

    max_used = ID_OFFSET_BASE + len(TRACKS) * ID_OFFSET_STEP + 22155 + 1
    xml = re.sub(
        r'(<NextPointeeId Value=")(\d+)(")',
        lambda m: m.group(1) + str(max_used + 100000) + m.group(3),
        xml, count=1,
    )

    try:
        ET.fromstring(xml)
    except ET.ParseError as e:
        raise SystemExit(f"Generated XML is invalid: {e}")
    print(f"  XML parses OK ({len(xml):,} chars)")

    DST.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(DST, "wb", compresslevel=9) as f:
        f.write(xml.encode("utf-8"))
    with gzip.open(DST, "rb") as f:
        head = f.read(80)
    assert head.startswith(b"<?xml"), "Double gzip detected"
    size = DST.stat().st_size
    print(f"Wrote: {DST}  ({size:,} bytes)")


if __name__ == "__main__":
    main()
