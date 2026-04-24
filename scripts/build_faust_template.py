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
    """Groovy kick — two-bar loops with dotted push feel and chromatic pockets."""
    notes: list[Note] = []
    level = INTENSITY[section]
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        ab = bar % 2  # alternate two-bar A / B for groove variation
        if level == 2:  # verse groove — half-time with dotted push
            if ab == 0:
                notes += [(t, 36, 0.25, 115), (t + 1.75, 36, 0.125, 96),
                          (t + 2.5, 36, 0.125, 100), (t + 3, 36, 0.25, 110)]
            else:
                notes += [(t, 36, 0.25, 115), (t + 0.75, 36, 0.125, 92),
                          (t + 2, 36, 0.25, 108), (t + 3.25, 36, 0.125, 98),
                          (t + 3.75, 36, 0.125, 90)]
        elif level == 3:  # pre-drop build — density ramps across 4 bars
            bar_in_4 = bar % 4
            if bar_in_4 < 2:
                notes += [(t, 36, 0.25, 105), (t + 2, 36, 0.25, 105),
                          (t + 3.5, 36, 0.125, 92)]
            elif bar_in_4 == 2:
                notes += [(t, 36, 0.25, 110), (t + 1.5, 36, 0.125, 94),
                          (t + 2, 36, 0.25, 110), (t + 3, 36, 0.25, 105),
                          (t + 3.5, 36, 0.125, 98), (t + 3.75, 36, 0.125, 104)]
            else:
                for s in range(16):  # 16th roll with rising velocity
                    notes.append((t + s * 0.25, 36, 0.1, 75 + s * 3))
        elif level == 4:  # drop — busy groove, two-bar alternation
            if ab == 0:
                notes += [(t, 36, 0.25, 120), (t + 0.75, 36, 0.125, 92),
                          (t + 1.5, 36, 0.25, 105), (t + 2, 36, 0.25, 118),
                          (t + 2.75, 36, 0.125, 94), (t + 3.5, 36, 0.125, 100)]
            else:
                notes += [(t, 36, 0.25, 120), (t + 1, 36, 0.125, 90),
                          (t + 1.75, 36, 0.125, 98), (t + 2, 36, 0.25, 118),
                          (t + 3, 36, 0.25, 108), (t + 3.75, 36, 0.125, 102)]
    return notes


def _snare(section: str, length: int) -> list[Note]:
    """Backbeat with anticipation ghosts and fills at phrase ends."""
    notes: list[Note] = []
    level = INTENSITY[section]
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        # main backbeat always
        notes += [(t + 1, 38, 0.25, 112), (t + 3, 38, 0.25, 116)]
        # anticipation ghost right before beat 3
        notes.append((t + 2.75, 38, 0.0625, 55))
        if level == 4:
            # extra ghosts + push on "a" of 4
            notes += [(t + 1.75, 38, 0.0625, 58),
                      (t + 3.75, 38, 0.0625, 72)]
        if level == 3 and bar == bars - 1:
            # snare roll on the last bar of pre-drop (quarters -> 16ths)
            for s in range(8):
                notes.append((t + 2 + s * 0.25, 38, 0.1, 72 + s * 5))
        # at end of every 4-bar phrase, fill on beat 4.5+
        if level >= 2 and bar % 4 == 3:
            notes += [(t + 3.25, 38, 0.0625, 75), (t + 3.5, 38, 0.0625, 85)]
    return notes


def _hats(section: str, length: int) -> list[Note]:
    """Groovy hat pattern — closed on downbeats, open on & of 2/4 in verses,
    dense 16ths with velocity accents in drops."""
    notes: list[Note] = []
    level = INTENSITY[section]
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        if level <= 2:  # verse/ambient — 8ths with open hat accents
            for s in range(8):
                pos = s * 0.5
                if s in (3, 7):  # "& of 2" and "& of 4" -> open hat 46
                    notes.append((t + pos, 46, 0.5, 95))
                else:
                    vel = 92 if s % 2 == 0 else 72
                    notes.append((t + pos, 42, 0.25, vel))
        elif level == 3:  # pre-drop — 16ths with strong accents
            for s in range(16):
                pos = s * 0.25
                vel = 105 if s % 4 == 0 else (78 if s % 2 == 0 else 62)
                pitch = 46 if s == 6 else 42  # open hat on "& of 2"
                notes.append((t + pos, pitch, 0.15, vel))
        else:  # drop — driving 16ths with humanized accents
            accent_pattern = [118, 60, 80, 62, 95, 60, 85, 62,
                              100, 60, 80, 62, 95, 60, 90, 75]
            for s in range(16):
                pitch = 46 if s in (6, 14) else 42
                notes.append((t + s * 0.25, pitch, 0.15, accent_pattern[s]))
    return notes


def _metal_perc(section: str, length: int) -> list[Note]:
    """Industrial accents — downbeat hits and off-beat stabs that pull the groove."""
    notes: list[Note] = []
    level = INTENSITY[section]
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        if bar % 4 == 0:
            notes.append((t, 56, 0.5, 118))       # big downbeat hit
        if bar % 2 == 1:
            notes.append((t + 3.75, 56, 0.125, 92))  # "a of 4" push
        if level == 4 and bar % 4 == 2:
            notes += [(t + 1.5, 56, 0.125, 88), (t + 2.75, 56, 0.125, 94)]
    return notes


def _sub_bass(section: str, length: int) -> list[Note]:
    """Sub foundation with breathing — held roots plus an octave flip every 4 bars."""
    notes: list[Note] = []
    bars = length // 4
    # 4-bar phrase: D1 hold, D1 hold with chromatic push, A0 hold, D1 + octave stab
    phrase = [26, 26, 21, 26]  # D1 D1 A0 D1
    for bar in range(bars):
        t = bar * 4
        p = phrase[bar % 4]
        notes.append((t, p, 3.5, 100))
        if bar % 4 == 1:
            notes.append((t + 3.5, 27, 0.5, 90))   # chromatic Eb1 push
        elif bar % 4 == 3:
            notes.append((t + 3.5, 38, 0.5, 95))   # octave up stab to D2
    return notes


def _distorted_bass(section: str, length: int) -> list[Note]:
    """Groovy low bass locked to the kick, walking through D-Eb-A-F-C with
    chromatic approach tones for industrial weight."""
    notes: list[Note] = []
    level = INTENSITY[section]
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        ab = bar % 2
        if level == 2:  # verse — sparse but with push
            if ab == 0:
                notes += [(t, 38, 0.5, 110), (t + 0.75, 39, 0.125, 90),  # D, chromatic Eb push
                          (t + 1.5, 38, 0.25, 100), (t + 2.5, 33, 0.5, 105),  # A below
                          (t + 3.5, 36, 0.25, 95)]   # C2 leading back
            else:
                notes += [(t, 38, 0.25, 112), (t + 1, 38, 0.25, 100),
                          (t + 2, 41, 0.5, 105),    # F2
                          (t + 3.25, 38, 0.25, 98), (t + 3.75, 39, 0.125, 88)]
        elif level >= 3:  # drop — locked to kick, chromatic coloring
            if ab == 0:
                notes += [(t, 38, 0.25, 118), (t + 0.75, 39, 0.125, 92),   # D-Eb push
                          (t + 1.5, 38, 0.25, 105), (t + 2, 38, 0.25, 118),
                          (t + 2.75, 36, 0.125, 94), (t + 3.5, 33, 0.25, 108)]   # C-A descent
            else:
                notes += [(t, 38, 0.25, 118), (t + 1, 41, 0.125, 94),    # F2 stab
                          (t + 1.75, 38, 0.125, 100), (t + 2, 38, 0.25, 118),
                          (t + 3, 39, 0.25, 108), (t + 3.75, 38, 0.125, 102)]
    return notes


def _lead(section: str, length: int) -> list[Note]:
    """Melodic phrase — 4-bar call, 4-bar answer, with rests + wide intervals.
    Call climbs Dm triad with a chromatic bend, answer descends with tension."""
    call = [  # bar 1-2: climb and peak
        (0.0, 62, 0.5,  102),   # D4
        (0.5, 65, 0.5,  100),   # F4
        (1.0, 69, 0.25, 108),   # A4
        (1.5, 72, 0.25, 110),   # C5
        (2.0, 74, 1.75, 118),   # D5 held (peak)
        (4.0, 70, 0.5,  102),   # Bb4
        (4.5, 72, 0.5,  104),   # C5
        (5.0, 74, 0.25, 110),   # D5
        (5.25, 77, 0.75, 115),  # F5 (accent high)
        (6.5, 74, 1.5,  108),   # D5 held
    ]
    answer = [  # bar 3-4: descending with chromatic tension
        (0.0, 77, 0.5,  112),   # F5
        (0.5, 76, 0.5,  105),   # E5 (chromatic tension)
        (1.0, 74, 0.5,  108),   # D5
        (1.5, 72, 0.5,  100),   # C5
        (2.0, 70, 1.0,  105),   # Bb4
        (3.5, 69, 0.5,  98),    # A4
        (4.0, 65, 1.0,  100),   # F4
        (5.5, 64, 0.25, 92),    # E4 (chromatic)
        (6.0, 62, 2.0,  105),   # D4 resolve
    ]
    notes: list[Note] = []
    bars = length // 4
    phrases = bars // 4
    for p in range(phrases):
        base = p * 16
        for (dt, pitch, dur, vel) in call:
            notes.append((base + dt, pitch, dur, vel))
        for (dt, pitch, dur, vel) in answer:
            notes.append((base + 8 + dt, pitch, dur, vel))
    return notes


def _pad(section: str, length: int) -> list[Note]:
    """4-bar chord progression with color tones — Dm9, Bb(add9), F(add9), Gm11.
    Voicings rotate for smoother voice leading."""
    # (chord_name, pitches)
    chords = [
        [50, 53, 57, 64],  # Dm9:    D3 F3 A3 E4
        [46, 53, 58, 62],  # Bb9:    Bb2 F3 Bb3 D4  (root low, add 9 on top)
        [53, 57, 60, 67],  # F(add9):F3 A3 C4 G4
        [43, 55, 58, 62],  # Gm11:   G2 G3 Bb3 D4
    ]
    notes: list[Note] = []
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        chord = chords[bar % 4]
        # sustained chord
        for pitch in chord:
            notes.append((t, pitch, 4.0, 70))
        # on bar 4 of phrase, add a top-note swell that anticipates the next chord
        if bar % 4 == 3 and bar < bars - 1:
            next_top = chords[(bar + 1) % 4][-1]
            notes.append((t + 3.5, next_top, 0.5, 78))
    return notes


def _arp(section: str, length: int) -> list[Note]:
    """Broken Dm arp with octave displacement + hemiola-feel accents.
    Pattern: D A F C | A D A F | octave leap every 2 bars for movement."""
    # 16-note cycle over 2 beats (we step 1/8 for breathing room, not full 1/16)
    # Step is 0.25 (16th). Pattern length = 16 steps over 4 beats = 1 bar.
    pattern_a = [62, 69, 65, 72, 69, 74, 69, 65,
                 62, 69, 65, 72, 77, 74, 69, 65]   # bar A
    pattern_b = [74, 69, 65, 72, 69, 74, 77, 72,
                 74, 81, 77, 74, 72, 69, 65, 62]   # bar B (higher, resolving down)
    # Hemiola-style accent pattern (accent every 3 steps for groove feel)
    vel_pattern = [105, 68, 72, 92, 70, 68, 96, 72, 68, 98, 72, 68, 100, 72, 70, 88]
    notes: list[Note] = []
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        pattern = pattern_a if bar % 2 == 0 else pattern_b
        for s in range(16):
            notes.append((t + s * 0.25, pattern[s], 0.2, vel_pattern[s]))
    return notes


def _vocal(section: str, length: int) -> list[Note]:
    """Melodic guide — 4-bar rise-and-fall phrase that breathes with the arrangement."""
    phrase = [
        (0.0, 57,  2.0, 88),   # A3 hold
        (2.0, 62,  1.5, 95),   # D4
        (4.0, 65,  2.0, 100),  # F4
        (6.0, 69,  1.5, 105),  # A4 (peak)
        (8.0, 67,  1.0, 98),   # G4
        (9.0, 65,  1.0, 92),   # F4
        (10.0, 62, 3.0, 90),   # D4 resolve
        (13.5, 60, 0.5, 82),   # C4 pickup
        (14.0, 62, 2.0, 88),   # D4 again
    ]
    notes: list[Note] = []
    bars = length // 4
    phrases = bars // 4  # 16-beat phrase
    for p in range(phrases):
        base = p * 16
        for (dt, pitch, dur, vel) in phrase:
            notes.append((base + dt, pitch, dur, vel))
    return notes


def _vocal_fx(section: str, length: int) -> list[Note]:
    """Short glitchy stabs on off-beats, every 4 bars."""
    notes: list[Note] = []
    bars = length // 4
    for bar in range(0, bars, 4):
        t = bar * 4
        notes += [(t + 0.75, 74, 0.25, 102),    # D5 stab on "e of 1"
                  (t + 2.5, 77, 0.25, 95),      # F5 on "& of 3"
                  (t + 3.75, 72, 0.125, 88)]    # C5 tail on "a of 4"
    return notes


def _riser(section: str, length: int) -> list[Note]:
    # Long held note — the riser timbre is shaped by the synth patch / automation
    return [(0.0, 60, float(length), 90)]


def _noise(section: str, length: int) -> list[Note]:
    # Single long drone
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
