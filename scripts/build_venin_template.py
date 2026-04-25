"""Build `Venin.als` — venomous slow-burn arrangement scaffold.

Brief: vibe blend of Alice In Chains (slow dirgy dissonant), Nine Inch Nails
(tension/release, silence as instrument), Rob Zombie (tribal toms, cluster
stabs, cinema swagger). Tempo 95 BPM, drop-C# tuning, C# Phrygian Dominant
scale (C# D F F# G# A B — the snake-charmer aug-2nd D->F lives here).

Metre: pure 4/4 throughout (no mixed meters). Cluster stabs are syncopated
16ths within the 4/4 grid — this gives the Rob Zombie / NIN tight punch
without the prog-y feel of metre changes.

Design principles (per the brief):

1. ELEGANCE THROUGH REPETITION + SILENCE. No scalar up-down runs. Notes
   repeat, breathe, then move a half-step. Tension rises by rhythmic
   DENSITY (closer hits in time), not by pitch climbing.

2. CLUSTER STABS SYNCHRONIZED ACROSS TRACKS. On Drops, multiple tracks
   (kick + snare + bass lead + syn lead + perc metal) hit EXACTLY the
   same syncopated beats (e.g. 0, 0.25, 2.5, 3.75 per bar) — a unified
   punch. Silence between = impact amplified.

3. DYNAMIC: SUPPORT THEN HOLLOW. Layers build to support the melody
   (Verse -> Drop); then a bar or section strips back to near-nothing
   ("Hollow" section, 4 bars only) before rebuilding bigger. The Final
   Drop catches fire — closer clusters every beat + riser continuous.

STEPS A1-A2/9 — scaffold + helpers + main. Serum stripped, empty device
chains, track-level Annotation holds the stock-instrument hint.
"""

from __future__ import annotations

import gzip
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Template.als"
DST = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Venin.als"

TEMPO = 95

# 9 sections, ALL 4/4. Beats cumulative:
#   Intro       8  bars  =  32 beats   t=  0   atmosphere + tom isolation
#   Verse 1    16  bars  =  64 beats   t= 32   slow groove establishes
#   Drop 1      8  bars  =  32 beats   t= 96   cluster stabs synchronized
#   Hollow      4  bars  =  16 beats   t=128   strip-back, post-drop void
#   Verse 2    16  bars  =  64 beats   t=144   rebuild, vocal enters
#   Drop 2     12  bars  =  48 beats   t=208   bigger, closer clusters
#   Bridge      8  bars  =  32 beats   t=256   chromatic half-step climb
#   Final Drop 20  bars  =  80 beats   t=288   CATCHES FIRE
#   Outro       8  bars  =  32 beats   t=368   slow decay
SECTIONS = [
    ("Intro",       0,   32),
    ("Verse 1",     32,  64),
    ("Drop 1",      96,  32),
    ("Hollow",      128, 16),
    ("Verse 2",     144, 64),
    ("Drop 2",      208, 48),
    ("Bridge",      256, 32),
    ("Final Drop",  288, 80),
    ("Outro",       368, 32),
]

# 15 tracks. Field order: (name, ableton_color, preset_hint, active_sections).
# Preset hints target STOCK Ableton instruments so the user can do a 2-click
# manual swap from the cloned Serum 2 if they want native devices.
TRACKS = [
    # Drums — 6
    ("01 DRM Kick",        2,  "Drum Rack: Kick Deep (Heavy / Kick 1 thumpy)",
        ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Final Drop"]),
    ("02 DRM Snare",       4,  "Drum Rack: Snare Crack (Wood Snare with body)",
        ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Bridge", "Final Drop"]),
    ("03 DRM Tom High",    5,  "Drum Rack: Tom High (acoustic or tribal)",
        ["Intro", "Hollow", "Bridge", "Final Drop"]),
    ("04 DRM Tom Low",     5,  "Drum Rack: Tom Low (acoustic or tribal)",
        ["Intro", "Verse 1", "Verse 2", "Bridge", "Final Drop"]),
    ("05 DRM Hats",        8,  "Drum Rack: Closed Hat Tight",
        ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Final Drop"]),
    ("06 PRC Metal",       11, "Drum Rack: Industrial Metal Hit (for cluster stabs)",
        ["Drop 1", "Drop 2", "Final Drop"]),
    # Bass — 2
    ("07 BAS Sub",         14, "Operator: Sub Sine (B-Sub-Pure)",
        ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Bridge", "Final Drop"]),
    ("08 BAS Lead",        16, "Wavetable: Reese Distort (B-Reese-Venomous)",
        ["Drop 1", "Verse 2", "Drop 2", "Bridge", "Final Drop"]),
    # Synth — 3
    ("09 SYN Pad",         20, "Wavetable: Dark Evolving Pad (PAD-Slow-Shift)",
        ["Intro", "Verse 1", "Verse 2", "Outro"]),
    ("10 SYN Drone Dark",  22, "Wavetable: Deep Drone (PAD-Drone-Low)",
        ["Intro", "Hollow", "Bridge", "Outro"]),
    ("11 SYN Lead",        27, "Wavetable: Distorted Cry Lead (LEAD-Brass-Bite)",
        ["Verse 2", "Drop 2", "Bridge", "Final Drop"]),
    # Voice — 1
    ("12 VOX Lead",        30, "Wavetable: Formant Voice (VOX-Wail-Sustained)",
        ["Verse 2", "Bridge", "Final Drop", "Outro"]),
    # FX — 3
    ("13 FX Riser",        37, "Wavetable: Noise Riser (FX-Riser-Slow-Build)",
        ["Bridge", "Final Drop"]),
    ("14 FX Impact",       39, "Wavetable: Cinematic Impact (FX-Impact-Sub)",
        ["Drop 1", "Drop 2", "Final Drop"]),
    ("15 FX Tension",      42, "Wavetable: Noise Bed (FX-Tension-Sustained)",
        ["Intro", "Hollow", "Bridge", "Outro"]),
]


# --- Note pattern generators (stubs for A1 — real patterns in B1-B3) -------

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


# --- Cluster-stab rhythmic template (used across multiple tracks in B/C) ---
#
# These are the beats within ONE bar where multiple tracks hit TOGETHER.
# Kick + snare + bass-lead + syn-lead + perc-metal lock to these positions.
# Silence between hits = maximum impact.
CLUSTER_BEATS_DROP1 = [0.0, 0.25, 2.5, 3.75]       # medium density
CLUSTER_BEATS_DROP2 = [0.0, 0.25, 1.75, 2.5, 3.75] # tighter
CLUSTER_BEATS_FINAL = [0.0, 0.25, 1.0, 1.25, 2.5, 2.75, 3.5, 3.75]  # catches fire

# C# Phrygian Dominant pitches (root octave = MIDI 25 = C#1):
#   C#=25 D=26 F=29 F#=30 G#=32 A=33 B=35   (note: F is the MAJ-3, creating
#   the aug-2 interval from D to F — the venomous snake-charmer sound)
#
# Key tension pair for "elegance through repetition": hold C#, push a
# half-step to D (the b2), return. Or hold F, push down to E (chromatic
# leading tone), return. NO scalar runs.


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
    """Shift Id/Value/Pointee Id >= min_val by offset, skipping PluginDesc
    interiors (plugin binary state)."""
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
    out, cursor = [], 0
    for s, e in sorted(regions):
        out.append(_shift_chunk(block[cursor:s]))
        out.append(block[s:e])
        cursor = e
    out.append(_shift_chunk(block[cursor:]))
    return "".join(out)


def build_locators_block(indent: str = "\t\t") -> str:
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
    track_xml = re.sub(r'<MidiTrack Id="\d+"', f'<MidiTrack Id="{new_track_id}"', track_xml, count=1)
    track_xml = re.sub(r'<EffectiveName Value="[^"]*"', f'<EffectiveName Value="{name}"', track_xml, count=1)
    track_xml = re.sub(r'<Color Value="\d+"', f'<Color Value="{color}"', track_xml, count=1)
    return track_xml


def strip_serum(track_xml: str) -> str:
    """Remove the Serum PluginDevice entirely from the track's Devices chain.
    Leaves the chain self-closing (`<Devices />`) so Live shows an empty slot
    where the user drags their stock instrument."""
    # Remove <PluginDevice Id="N">...</PluginDevice> including surrounding whitespace
    track_xml = re.sub(
        r'\n[ \t]*<PluginDevice\s+Id="\d+"[^>]*>.*?</PluginDevice>',
        '', track_xml, flags=re.DOTALL,
    )
    # Normalize emptied <Devices> block to self-closing
    track_xml = re.sub(r'<Devices>\s*</Devices>', '<Devices />', track_xml)
    return track_xml


def set_track_annotation(track_xml: str, hint: str) -> str:
    """Set the track-level <Annotation> (visible in Live's track inspector)
    with the stock-instrument hint so the user knows what to drag in."""
    safe = (hint.replace('&', '&amp;').replace('"', '&quot;')
                .replace('<', '&lt;').replace('>', '&gt;'))
    # Target the FIRST <Annotation> inside the track's <Name> block (track-level)
    return re.sub(
        r'(<Name>\s*<EffectiveName[^/]+/>\s*<UserName[^/]+/>\s*<Annotation Value=")[^"]*(" />)',
        rf'\g<1>{safe}\g<2>',
        track_xml, count=1, flags=re.DOTALL,
    )


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
              notes: list[Note] | None = None) -> str:
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


# --- main ------------------------------------------------------------------

def main() -> None:
    print(f"Reading: {SRC}")
    with gzip.open(SRC, "rb") as f:
        xml = f.read().decode("utf-8")

    # Tempo
    m_tempo = re.search(r'(<Tempo>.*?<Manual Value=")(\d+)(")', xml, re.DOTALL)
    assert m_tempo, "Tempo block not found"
    xml = xml[:m_tempo.start(2)] + str(TEMPO) + xml[m_tempo.end(2):]
    print(f"  Tempo: {TEMPO} BPM")

    # Locators
    loc_pat = re.compile(r'([ \t]*)<Locators>\s*<Locators />\s*</Locators>', re.DOTALL)
    m_loc = loc_pat.search(xml)
    assert m_loc, "Empty <Locators> block not found"
    indent = m_loc.group(1)
    xml = xml[:m_loc.start()] + build_locators_block(indent) + xml[m_loc.end():]
    print(f"  Locators: {len(SECTIONS)} sections")

    # Splice: MidiTrack 12 (has Serum) is our template
    line_start_of = lambda pos: xml.rfind("\n", 0, pos) + 1
    m_t12 = re.search(r'<MidiTrack Id="12"', xml)
    t12_pos = line_start_of(m_t12.start())
    m_r2 = re.search(r'<ReturnTrack Id="2"', xml)
    r2_pos = line_start_of(m_r2.start())
    m_t12_end = xml.find("</MidiTrack>", m_t12.start())
    m_t13_open = xml.find('<MidiTrack Id="13"', m_t12_end)
    t12_end_line = xml.rfind("\n", 0, m_t13_open) + 1
    template_track = xml[t12_pos:t12_end_line]
    print(f"  Template MidiTrack: {len(template_track):,} chars (Serum will be stripped)")

    ID_OFFSET_BASE = 84170
    ID_OFFSET_STEP = 10000
    SECTION_BY_NAME = {name: (start, length) for name, start, length in SECTIONS}
    new_tracks: list[str] = []

    for i, (name, color, preset_hint, active_sections) in enumerate(TRACKS):
        clone = template_track
        offset = ID_OFFSET_BASE + i * ID_OFFSET_STEP
        clone = shift_big_ids(clone, offset, min_val=4000)
        clone = rename_track(clone, name, color, new_track_id=500 + i)
        clone = strip_serum(clone)                      # <-- NO plugin
        clone = set_track_annotation(clone, preset_hint)  # <-- hint in track inspector

        clips = []
        note_total = 0
        for slot_idx, section_name in enumerate(active_sections):
            start, length = SECTION_BY_NAME[section_name]
            notes = gen_notes(name, section_name, length)
            note_total += len(notes)
            clips.append(midi_clip(
                clip_id=slot_idx, start=start, length=length,
                name=section_name, color=color, notes=notes,
            ))
        clone = inject_clips(clone, clips, track_idx=i)
        new_tracks.append(clone)
        print(f"  #{i+1:2d} {name:<20} clips={len(clips):2d} notes={note_total:4d}  -> {preset_hint}")

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
    print(f"Wrote: {DST}  ({DST.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
