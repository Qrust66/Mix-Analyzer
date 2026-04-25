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

STEPS A1-C2/9 — phase B complete + EQ8 injection on drums/basses (12
tracks). EQ8 reference cloned from tests/fixtures/reference_project.als
(the canonical Pluggin Mapping.als source isn't in this repo). Each
EQ8 gets its own ID range (offset 2M+ per track) so internal Automation
Targets don't collide across clones, and a UserName so Live's device
header tells the user the role at a glance.
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


# Per-section metre lookup
SECTION_METRE = {name: (num, denom) for name, _, _, num, denom in SECTIONS}

# Intensity (used by velocity envelopes)
INTENSITY = {
    "Intro": 0, "Outro": 0,
    "Break": 1, "Bridge": 1,
    "Verse 1": 2, "Verse 2": 2,
    "Pre-Drop 1": 3, "Pre-Drop 2": 3,
    "Drop 1": 4, "Drop 2": 4, "Final Drop": 4,
}


def bar_length(section: str) -> float:
    """Bar length in beats. 4/4=4, 7/4=7, 6/8=3 (six eighths = three quarters)."""
    num, denom = SECTION_METRE[section]
    if denom == 4:
        return float(num)
    if denom == 8:
        return num / 2.0
    return float(num)


def n_bars(section: str, length: int) -> int:
    return int(length / bar_length(section))


# --- Drum generators -------------------------------------------------------
#
# Drum-rack pitches (GM-ish):
#   Kick A=36  Kick B=37   (different sample slots so user can route to two
#                           distinct kicks in the same Drum Rack)
#   Snare A=38 Snare B=40  (different snare slots)
#   Clap=39  Rim=37 (alt slot — user can move)  Hat closed=42  Hat open=46
#   Perc=56 (cowbell / industrial slot)


def _kick_a(section: str, length: int) -> list[Note]:
    """Thumpy kick. 7/4 verses use a 4+3 grouping with kick on 1 + 4.5 + 6
    (anchors the asymmetric stagger). 4/4 drops keep it punch-and-breathe:
    beats 1 and 3 with a syncopated push variant every 2 bars. Audacity
    push: every 4th bar, kick disappears on beat 1 entirely (the soubresaut
    moment — drum dropout that snaps back)."""
    notes: list[Note] = []
    metre = SECTION_METRE[section]
    bars = n_bars(section, length)
    bl = bar_length(section)

    if metre == (7, 4):  # Verse — asymmetric 4+3 grouping
        for bar in range(bars):
            t = bar * 7
            # Audacity surprise: bar 4 of every 4-bar phrase drops beat 1
            if (bar + 1) % 4 == 0:
                notes += [(t + 3.5, 36, 0.25, 105),
                          (t + 5,   36, 0.25, 110)]
                continue
            ab = bar % 2
            if ab == 0:
                notes += [(t,       36, 0.25, 118),
                          (t + 3.5, 36, 0.25, 105),
                          (t + 5,   36, 0.25, 112)]
            else:
                notes += [(t,       36, 0.25, 118),
                          (t + 2,   36, 0.25, 100),
                          (t + 4.5, 36, 0.25, 108)]
    elif metre == (4, 4):  # Drop — punch + breathing
        for bar in range(bars):
            t = bar * 4
            ab = bar % 2
            if (bar + 1) % 4 == 0:
                # Soubresaut: skip beat 1, only beat 3 + push
                notes += [(t + 2,    36, 0.25, 115),
                          (t + 3.5,  36, 0.125, 95)]
                continue
            if ab == 0:
                notes += [(t,        36, 0.25, 120),
                          (t + 2,    36, 0.25, 115)]
            else:
                notes += [(t,        36, 0.25, 120),
                          (t + 2.5,  36, 0.125, 100),
                          (t + 3,    36, 0.25, 110)]
    return notes


def _kick_b(section: str, length: int) -> list[Note]:
    """Snap top-end kick. Plays where Kick A is silent or fills the space.
    Pre-Drop: carries alone (beat 1 of every bar plus 'a of 4' push).
    Drops: snaps on 'e of 2' and '& of 3' to interlace with Kick A."""
    notes: list[Note] = []
    metre = SECTION_METRE[section]
    bars = n_bars(section, length)

    if metre == (4, 4):
        if INTENSITY[section] == 3:  # Pre-Drop — carries alone
            for bar in range(bars):
                t = bar * 4
                notes += [(t,        37, 0.25, 110),
                          (t + 2,    37, 0.25, 108),
                          (t + 3.75, 37, 0.125, 95)]
        elif INTENSITY[section] == 4:  # Drop — fills gaps in Kick A
            for bar in range(bars):
                t = bar * 4
                ab = bar % 2
                if (bar + 1) % 4 == 0:
                    # Soubresaut bar — Kick B fills bar 1 of phrase
                    notes += [(t,       37, 0.25, 115),
                              (t + 1,   37, 0.125, 90),
                              (t + 3,   37, 0.25, 108)]
                    continue
                if ab == 0:
                    notes += [(t + 1.75, 37, 0.125, 95),
                              (t + 2.5,  37, 0.125, 102)]
                else:
                    notes += [(t + 0.75, 37, 0.125, 92),
                              (t + 2.25, 37, 0.125, 100),
                              (t + 3.75, 37, 0.125, 90)]
    return notes


def _snare_a(section: str, length: int) -> list[Note]:
    """Cracking snare. 7/4 verse: backbeat on beats 3 and 6 (4+3 grouping
    backbeats). 4/4 drop: standard 2/4 with anticipation ghost before beat 3.
    Audacity: bar 4 of phrase in verse SKIPS the beat-3 hit — only beat 6
    lands. Drops bar 4: snare displaced to beats 1.5 and 3.5."""
    notes: list[Note] = []
    metre = SECTION_METRE[section]
    bars = n_bars(section, length)

    if metre == (7, 4):
        for bar in range(bars):
            t = bar * 7
            if (bar + 1) % 4 == 0:
                # Audacity: skip beat 3, only beat 6
                notes.append((t + 5, 38, 0.25, 120))
                continue
            notes += [(t + 2, 38, 0.25, 115),  # beat 3
                      (t + 5, 38, 0.25, 118)]  # beat 6
            # Anticipation ghost before beat 6
            notes.append((t + 4.75, 38, 0.0625, 60))
    elif metre == (4, 4):
        for bar in range(bars):
            t = bar * 4
            if INTENSITY[section] >= 2:
                if (bar + 1) % 4 == 0 and INTENSITY[section] == 4:
                    # Audacity: displaced backbeat
                    notes += [(t + 1.5, 38, 0.25, 115),
                              (t + 3.5, 38, 0.25, 120)]
                    continue
                notes += [(t + 1, 38, 0.25, 118),
                          (t + 3, 38, 0.25, 122)]
                if INTENSITY[section] == 4:
                    notes.append((t + 2.75, 38, 0.0625, 55))
    return notes


def _snare_b(section: str, length: int) -> list[Note]:
    """Air/ghost layer. Sparse soft hits on the 'e' and 'a' positions to
    add breath under the main snare. Only in drops."""
    notes: list[Note] = []
    if INTENSITY[section] != 4:
        return notes
    bars = n_bars(section, length)
    for bar in range(bars):
        t = bar * 4
        notes += [(t + 0.75, 40, 0.0625, 58),
                  (t + 1.75, 40, 0.0625, 62),
                  (t + 3.25, 40, 0.0625, 60)]
    return notes


def _clap(section: str, length: int) -> list[Note]:
    """Layered clap on snare backbeats with a tick of delay (+16 ticks =
    +0.015 beat) for that stacked attack feel."""
    notes: list[Note] = []
    if INTENSITY[section] != 4:
        return notes
    bars = n_bars(section, length)
    for bar in range(bars):
        t = bar * 4
        notes += [(t + 1.015, 39, 0.25, 100),
                  (t + 3.015, 39, 0.25, 105)]
    return notes


def _rim(section: str, length: int) -> list[Note]:
    """Cross-stick. Verse 7/4: rim on the 'in-between' beats 2.5 and 4.5
    (creates polyrhythmic pull against the kick anchors). Bridge 6/8:
    rim on beat 1.5 of each bar (mid-bar accent)."""
    notes: list[Note] = []
    metre = SECTION_METRE[section]
    bars = n_bars(section, length)
    if metre == (7, 4):
        for bar in range(bars):
            t = bar * 7
            notes += [(t + 1.5, 37, 0.1, 88),
                      (t + 4.5, 37, 0.1, 92)]
    elif metre == (6, 8):
        for bar in range(bars):
            t = bar * 3
            notes.append((t + 1.5, 37, 0.1, 95))
    return notes


def _hats(section: str, length: int) -> list[Note]:
    """Closed hats. Time-keeper, density scales with intensity.
    Audacity rule: every 4th bar SKIPS the very last 8th to create a
    'hole' that resets the groove."""
    notes: list[Note] = []
    metre = SECTION_METRE[section]
    bars = n_bars(section, length)
    bl = bar_length(section)
    level = INTENSITY[section]

    for bar in range(bars):
        t = bar * bl
        if metre == (7, 4):
            # 8ths across 7 beats = 14 hats per bar
            steps = 14
            step_size = 0.5
        elif metre == (4, 4):
            # 16ths in drops, 8ths in pre-drop and verse-not-applicable here
            if level >= 4:
                steps = 16; step_size = 0.25
            else:
                steps = 8; step_size = 0.5
        elif metre == (6, 8):
            steps = 6; step_size = 0.5
        else:
            continue

        skip_last = ((bar + 1) % 4 == 0)
        for s in range(steps):
            if skip_last and s == steps - 1:
                continue
            on_beat = (s * step_size) % 1 == 0
            vel = 95 if on_beat else 70
            notes.append((t + s * step_size, 42, step_size * 0.6, vel))
    return notes


def _open_hat(section: str, length: int) -> list[Note]:
    """Open hat accents on '&' of 2 and '&' of 4 in drops only — that
    'chick' sound that locks with the snare backbeat."""
    notes: list[Note] = []
    if INTENSITY[section] != 4:
        return notes
    bars = n_bars(section, length)
    for bar in range(bars):
        t = bar * 4
        notes += [(t + 1.5, 46, 0.5, 92),
                  (t + 3.5, 46, 0.5, 98)]
    return notes


def _perc(section: str, length: int) -> list[Note]:
    """Industrial accents. Verse 7/4: irregular hits at unexpected beats
    (beat 4 of bar 1, beat 6.5 of bar 3) — soubresauts. Bridge 6/8: hit
    on beat 2 every 2 bars. Final Drop 4/4: downbeat slam every 4-bar."""
    notes: list[Note] = []
    metre = SECTION_METRE[section]
    bars = n_bars(section, length)
    if metre == (7, 4):
        for bar in range(bars):
            t = bar * 7
            if bar % 4 == 0:
                notes.append((t + 3, 56, 0.25, 110))   # bar 1 beat 4
            elif bar % 4 == 2:
                notes.append((t + 5.5, 56, 0.25, 105)) # bar 3 beat 6.5
    elif metre == (6, 8):
        for bar in range(bars):
            if bar % 2 == 0:
                notes.append((bar * 3 + 1, 56, 0.25, 100))
    elif section == "Final Drop":
        for bar in range(0, bars, 4):
            notes.append((bar * 4, 56, 0.5, 118))
    return notes


# --- Basses + Pad + Drone --------------------------------------------------
#
# Pitch reference (C#1=25, C#2=37, etc.):
#   C# Locrian  : C#  D   E   F#  G   A   B    (b2 b3 4 b5 b6 b7)
#   D Mixolydian: D   E   F#  G   A   B   C    (1 2 3 4 5 6 b7)
#   Shared      :     D   E   F#  G   A   B    (only roots differ)
#   Bridge      : anchors on E (the shared note that lives in both modes)


def _bas_sub(section: str, length: int) -> list[Note]:
    """Sub root drone. C#1 in Verses (Locrian), D1 in Drops (Mixolydian — the
    half-step pivot UP). Pre-Drops bridge it: hold C# for first half then D
    for second half (announces the pivot). Bridge anchors on E1 (shared
    note). AUDACITY: every 4th bar octave-drops to one octave below for
    weight punctuation."""
    notes: list[Note] = []
    bars = n_bars(section, length)
    bl = bar_length(section)

    if section in ("Pre-Drop 1", "Pre-Drop 2"):
        # 16-beat bridge: 8 beats C#, 8 beats D (announces the pivot)
        return [(0.0, 25, 8.0, 105), (8.0, 26, 8.0, 110)]

    if section in ("Verse 1", "Verse 2"):
        root = 25       # C#1
    elif section == "Bridge":
        root = 28       # E1 (shared anchor)
    else:               # Drops, Final Drop
        root = 26       # D1

    for bar in range(bars):
        t = bar * bl
        if bar % 4 == 3:
            notes.append((t, root - 12, bl, 95))   # octave-down weight
        else:
            notes.append((t, root, bl, 102))
    return notes


def _bas_punch(section: str, length: int) -> list[Note]:
    """Obsessive single-note articulation — repeated heartbeat. Verse 7/4
    pounds C#2 on backbeats 2.5/4.5/6. Drop 4/4 pounds D2 on every '&'.
    AUDACITY: every 4th bar swaps in the b2 (D2 in Verse Locrian, Eb2 in
    Drop Mixolydian) — instant menace via repetition with chromatic shift."""
    notes: list[Note] = []
    metre = SECTION_METRE[section]
    bars = n_bars(section, length)

    if section in ("Verse 1", "Verse 2"):
        for bar in range(bars):
            t = bar * 7
            pitch = 38 if (bar + 1) % 4 == 0 else 37     # D2 b2 surprise vs C#2
            notes += [(t + 1.5, pitch, 0.25, 100),
                      (t + 3.5, pitch, 0.25, 105),
                      (t + 5.0, pitch, 0.25, 108)]
    elif metre == (4, 4) and INTENSITY[section] == 4:
        for bar in range(bars):
            t = bar * 4
            pitch = 39 if (bar + 1) % 4 == 0 else 38     # Eb2 chromatic vs D2
            notes += [(t + 0.5, pitch, 0.25, 100),
                      (t + 1.5, pitch, 0.25, 100),
                      (t + 2.5, pitch, 0.25, 105),
                      (t + 3.5, pitch, 0.25, 108)]
    return notes


def _bas_distort(section: str, length: int) -> list[Note]:
    """Heavy sustain — long held dissonant notes with deliberate silence.
    Drop 4-bar phrase: D2 (2 bars) -> E2 (2 bars, the shared note) -> D2 hold.
    Bar 4 of each 4-bar = drop to C2 (Mixolydian b7 flavor). AUDACITY:
    Drop bar 5 of each 8-bar phrase TRANSPOSES UP an octave (D3) for one
    bar — momentary wail that breaks the low register."""
    notes: list[Note] = []
    metre = SECTION_METRE[section]
    bars = n_bars(section, length)

    if section == "Bridge":  # 6/8, 8 bars (24 beats)
        return [(0.0,  40, 12.0, 100),    # E2 (shared anchor) 4 bars
                (12.0, 42, 12.0, 105)]    # F#2 slide-up
    if metre != (4, 4) or INTENSITY[section] != 4:
        return notes

    for bar in range(bars):
        t = bar * 4
        phrase_pos = bar % 8
        if (bar + 1) % 4 == 0:
            pitch = 36                                  # C2 b7 Mixolydian flavor
        elif phrase_pos == 4:
            pitch = 50                                  # D3 wail (audacity push)
        elif phrase_pos in (0, 1):
            pitch = 38                                  # D2
        elif phrase_pos in (2, 3):
            pitch = 40                                  # E2 shared
        else:
            pitch = 38                                  # back to D2
        notes.append((t, pitch, 4.0, 105))
    return notes


# Pad voicings — sparse, deliberately dissonant
LOCRIAN_VOICING = [49, 52, 55, 57]      # C# E G A   (root + b3 + b5 + b6)
MIXOLYDIAN_VOICING = [50, 54, 57, 60]   # D F# A C   (Dom7 shell)
BRIDGE_VOICING = [52, 55, 59, 62]       # E G B D    (Em7 anchor)


def _pad(section: str, length: int) -> list[Note]:
    """Sparse pad. Audacity rule: silence as a feature.
    - Verse 7/4: chord rings 4 beats, then 3 beats SILENCE per bar.
    - Drops: chord rings 3 beats, 1 beat silence per bar.
    - Final Drop: ALTERNATES Locrian (clash) and Mixolydian (resolution)
      every 4 bars. AUDACITY PUSH: bar 4 (last bar of first Locrian phrase)
      drops to total SILENCE — the clash arrives in negative space."""
    notes: list[Note] = []
    metre = SECTION_METRE[section]
    bars = n_bars(section, length)

    if section in ("Intro", "Outro"):
        # Drone — single 3-note shell every 2 bars
        for bar in range(0, bars, 2):
            t = bar * 4
            for pitch in [49, 52, 55]:
                notes.append((t, pitch, 4.0, 55))
    elif section in ("Verse 1", "Verse 2"):
        for bar in range(bars):
            t = bar * 7
            for pitch in LOCRIAN_VOICING:
                notes.append((t, pitch, 4.0, 70))
    elif section in ("Pre-Drop 1", "Pre-Drop 2"):
        for pitch in LOCRIAN_VOICING:
            notes.append((0.0, pitch, 8.0, 70))
        for pitch in MIXOLYDIAN_VOICING:
            notes.append((8.0, pitch, 8.0, 75))
    elif section in ("Drop 1", "Drop 2"):
        for bar in range(bars):
            t = bar * 4
            if (bar + 1) % 4 == 0:
                # Bar 4: chord enters on beat 2 (silence on beat 1)
                for pitch in MIXOLYDIAN_VOICING:
                    notes.append((t + 1, pitch, 3.0, 75))
            else:
                for pitch in MIXOLYDIAN_VOICING:
                    notes.append((t, pitch, 3.0, 75))
    elif section == "Break":
        for bar in range(0, bars, 2):
            t = bar * 3
            for pitch in [40, 43, 47]:                  # Em (E G B)
                notes.append((t, pitch, 6.0, 60))
    elif section == "Bridge":
        for bar in range(0, bars, 2):
            t = bar * 3
            for pitch in BRIDGE_VOICING:
                notes.append((t, pitch, 6.0, 65))
    elif section == "Final Drop":
        for bar in range(bars):
            t = bar * 4
            phrase = (bar // 4) % 2
            # AUDACITY PUSH: bar 4 of first Locrian phrase = total silence
            if bar == 3:
                continue
            voicing = LOCRIAN_VOICING if phrase == 0 else MIXOLYDIAN_VOICING
            for pitch in voicing:
                notes.append((t, pitch, 3.0, 80))
    return notes


def _drone_dark(section: str, length: int) -> list[Note]:
    """Long sustained atmosphere. AUDACITY: Intro is ONE note for 16 beats
    — pure tension, no movement. Break: E2 -> F2 chromatic surprise mid-
    section. Bridge: C#3 -> D3 modal pivot ANNOUNCING the Final Drop clash.
    Outro: D2 fade."""
    if section == "Intro":
        return [(0.0, 40, float(length), 65)]            # pure E2
    if section == "Break":
        return [(0.0, 40, 9.0, 65),
                (9.0, 41, 9.0, 70)]                       # E2 -> F2 chromatic
    if section == "Bridge":
        return [(0.0,  49, 12.0, 70),
                (12.0, 50, 12.0, 75)]                     # C#3 -> D3 pivot
    if section == "Outro":
        return [(0.0, 38, float(length), 60)]            # D2 fade
    return []


NOTE_GENERATORS: dict[str, "callable"] = {name: _noop for (name, *_) in TRACKS}
NOTE_GENERATORS["01 DRM Kick A"]    = _kick_a
NOTE_GENERATORS["02 DRM Kick B"]    = _kick_b
NOTE_GENERATORS["03 DRM Snare A"]   = _snare_a
NOTE_GENERATORS["04 DRM Snare B"]   = _snare_b
NOTE_GENERATORS["05 DRM Clap"]      = _clap
NOTE_GENERATORS["06 DRM Rim"]       = _rim
NOTE_GENERATORS["07 DRM Hats"]      = _hats
NOTE_GENERATORS["08 DRM Open Hat"]  = _open_hat
NOTE_GENERATORS["09 DRM Perc"]      = _perc
NOTE_GENERATORS["10 BAS Sub"]       = _bas_sub
NOTE_GENERATORS["11 BAS Punch"]     = _bas_punch
NOTE_GENERATORS["12 BAS Distort"]   = _bas_distort
NOTE_GENERATORS["13 SYN Pad"]       = _pad
NOTE_GENERATORS["14 SYN Drone Dark"] = _drone_dark


# --- Leads, Voice, FX ------------------------------------------------------
#
# Lead pitch reference (mid-high register):
#   C#4=61  D4=62  E4=64  F#4=66  G4=67  G#4=68  A4=69  B4=71
#   C#5=73  D5=74  E5=76  F#5=78  G5=79  A5=81  B5=83  C#6=85
# Tritone pairs (for the tabarnak-clash tension):
#   C# <-> G       (Locrian b5)
#   D  <-> G#      (Mixolydian #4 — 'Lydian flavor on top')


def _lead_cry(section: str, length: int) -> list[Note]:
    """Main melodic voice. Sparse — pounds anchor pitch with deliberate
    silences and tritone pushes. Drop 1 anchors E5 (the shared note).
    Drop 2 pivots to D5 (Mixolydian root). Final Drop alternates anchors
    by 4-bar phrase. AUDACITY: bar 8 of every phrase ends with a single
    LONG note (4 beats) on the tritone — pure dissonance hold."""
    notes: list[Note] = []
    metre = SECTION_METRE[section]
    bars = n_bars(section, length)
    if metre != (4, 4):
        return notes

    def phrase_notes(base_t: float, anchor: int, tritone: int) -> list[Note]:
        # 8-bar phrase, ~24 events. Lots of silence.
        return [
            (base_t + 0.0,  anchor,  2.0,  110),     # statement: anchor 2 beats
            # silence 2 beats
            (base_t + 3.0,  anchor,  0.5,  102),     # echo
            (base_t + 3.5,  tritone, 0.5,  108),     # tritone push
            # silence ~3 beats
            (base_t + 6.0,  anchor + 2,  1.0, 100),  # F#/G nat (scale step up)
            (base_t + 7.0,  tritone,    0.5, 105),
            (base_t + 7.5,  anchor + 5, 4.0, 115),   # held high (peak)
            # silence then variation bar 5-8
            (base_t + 14.0, anchor,   1.0, 100),
            (base_t + 15.0, anchor - 2, 1.0, 95),
            (base_t + 16.0, anchor + 5, 2.0, 110),
            # silence bar 6
            (base_t + 22.0, tritone, 0.5, 100),
            (base_t + 22.5, anchor + 5, 0.5, 105),
            (base_t + 23.0, anchor + 7, 1.0, 112),
            # AUDACITY PUSH: bar 8 = held tritone (pure dissonance)
            (base_t + 28.0, tritone, 4.0, 118),
        ]

    # Anchor pitch per phrase
    if section in ("Pre-Drop 1", "Drop 1"):
        anchor, tritone = 76, 79                     # E5 anchor, G5 tritone push
    elif section == "Drop 2":
        anchor, tritone = 74, 80                     # D5 anchor, G#5 tritone (#4)
    elif section == "Final Drop":
        # Alternate per 8-bar phrase
        for p in range(max(1, bars // 8)):
            base_t = p * 32
            if base_t >= length:
                break
            if p % 2 == 0:
                a, tt = 76, 79
            else:
                a, tt = 74, 80
            for note in phrase_notes(base_t, a, tt):
                t, pitch, dur, vel = note
                if t < length:
                    notes.append((t, pitch, min(dur, length - t), vel))
        return notes
    else:
        return notes

    for p in range(max(1, bars // 8 + (1 if bars % 8 else 0))):
        base_t = p * 32
        if base_t >= length:
            break
        for note in phrase_notes(base_t, anchor, tritone):
            t, pitch, dur, vel = note
            if t < length:
                notes.append((t, pitch, min(dur, length - t), vel))
    return notes


def _lead_counter(section: str, length: int) -> list[Note]:
    """Counter-lead. Fills silences in Lead Cry (call/response) and gets a
    Bridge solo. Harmonizes a 4th below the Lead Cry's anchor — adds the
    'hollow' second voice. AUDACITY: Bridge solo is ONE held note (E4)
    that swells then fades — pure restraint."""
    notes: list[Note] = []
    metre = SECTION_METRE[section]
    bars = n_bars(section, length)

    if section == "Bridge":
        # 6/8, 8 bars (24 beats). AUDACITY: ONE long swell on E4.
        return [(0.0, 64, 24.0, 95)]                 # E4 held — pure restraint

    if metre != (4, 4) or INTENSITY[section] != 4:
        return notes

    # Drop sections — fill the gaps in Lead Cry
    for p in range(max(1, bars // 8 + (1 if bars % 8 else 0))):
        base_t = p * 32
        if base_t >= length:
            break
        # Bar 1 — silent (Lead Cry plays anchor)
        # Bar 2 — fill (Lead Cry silent here)
        # Bars 3-4 — sparse harmony underneath Lead Cry's climb
        # Bar 5 — silent
        # Bar 6 — fill
        # Bars 7-8 — silent (Lead Cry holds tritone)
        gap_pattern = [
            (base_t + 4.0,  62, 0.5, 92),            # D4 echo
            (base_t + 4.5,  64, 0.5, 95),            # E4
            (base_t + 5.0,  62, 1.0, 90),            # D4 hold
            (base_t + 12.0, 67, 1.0, 98),            # G4 (4th below G5 tritone)
            (base_t + 13.0, 64, 1.0, 92),            # E4 down
            (base_t + 20.0, 62, 0.5, 90),
            (base_t + 20.5, 64, 0.5, 95),
            (base_t + 21.0, 66, 1.0, 100),
        ]
        for t, pitch, dur, vel in gap_pattern:
            if t < length:
                notes.append((t, pitch, min(dur, length - t), vel))
    return notes


def _pluck_stab(section: str, length: int) -> list[Note]:
    """Sharp pluck stabs. Audacity = extreme silence. Verse 7/4: ONE stab
    on beat 4 of bar 1, then NOTHING for 3 bars, then one stab beat 6.5 of
    bar 5. Pre-Drop 2: 4 quick stabs in bar 4 (announces drop). Final Drop:
    sparse stabs every 2 bars."""
    notes: list[Note] = []
    metre = SECTION_METRE[section]
    bars = n_bars(section, length)

    if metre == (7, 4):  # Verse — extreme sparseness
        for bar in range(bars):
            t = bar * 7
            if bar % 8 == 0:
                notes.append((t + 3, 73, 0.25, 100))   # C#5 stab on beat 4
            elif bar % 8 == 4:
                notes.append((t + 5.5, 76, 0.25, 105)) # E5 stab on beat 6.5
    elif section == "Pre-Drop 2":
        # 4/4, 4 bars — 4 stabs in last bar (announce drop)
        t = (bars - 1) * 4
        notes += [(t + 0.0, 73, 0.125, 95),
                  (t + 1.0, 74, 0.125, 100),
                  (t + 2.0, 76, 0.125, 105),
                  (t + 3.0, 79, 0.125, 110)]   # rises C#-D-E-G
    elif section == "Final Drop":
        # 4/4 — sparse stabs every 2 bars
        for bar in range(0, bars, 2):
            t = bar * 4
            phrase = (bar // 4) % 2
            pitch = 73 if phrase == 0 else 74           # C#5 (Locrian) / D5 (Mixolydian)
            notes.append((t + 1.5, pitch, 0.125, 100))
    return notes


def _choir_wail(section: str, length: int) -> list[Note]:
    """Atmospheric vocal pad. Bridge: high held voicing E5 G5 B5 (Em9
    shell). Outro: descends to a single held C#3 (resolution). Sparse,
    breathing."""
    notes: list[Note] = []
    if section == "Bridge":
        # 6/8, 24 beats — held high voicing
        for pitch in [76, 79, 83]:                       # E5 G5 B5
            notes.append((0.0, pitch, 24.0, 60))
    elif section == "Outro":
        # Held C#4 fade (resolution)
        notes.append((0.0, 61, float(length), 55))
    return notes


def _vox_guide(section: str, length: int) -> list[Note]:
    """Vocal guide — phrases that climb and resolve. Verse 7/4: 14-beat
    phrase (2 bars), then 14 beats SILENCE per 4-bar phrase. Drop: 4-bar
    phrase. Final Drop alternates Locrian and Mixolydian phrases."""
    notes: list[Note] = []
    metre = SECTION_METRE[section]
    bars = n_bars(section, length)

    if metre == (7, 4):
        # Verse phrase over 2 bars (14 beats), silence next 2 bars
        for p in range(bars // 4):
            base_t = p * 28  # 4-bar phrase = 28 beats
            phrase = [
                (base_t + 0.0,  61, 2.0, 95),   # C#4 anchor
                (base_t + 3.0,  64, 1.5, 100),  # E4
                (base_t + 5.0,  66, 2.0, 108),  # F#4 peak
                (base_t + 9.0,  64, 2.0, 95),   # E4 descend
                (base_t + 12.0, 61, 2.0, 90),   # C#4 resolve
                # bars 3-4 = silence
            ]
            for t, pitch, dur, vel in phrase:
                if t < length:
                    notes.append((t, pitch, min(dur, length - t), vel))
    elif metre == (4, 4) and INTENSITY[section] == 4:
        # Drop phrase over 4 bars
        for p in range(max(1, bars // 4)):
            base_t = p * 16
            if base_t >= length:
                break
            phrase_idx = p % 2 if section == "Final Drop" else 0
            anchor = 64 if phrase_idx == 0 else 62        # E4 Locrian / D4 Mixolydian
            phrase = [
                (base_t + 0.0,  anchor,    2.0, 100),
                (base_t + 3.0,  anchor + 3, 1.0, 105),    # +m3
                (base_t + 5.0,  anchor + 5, 2.0, 110),    # +P4 peak
                (base_t + 8.0,  anchor + 3, 2.0, 95),
                (base_t + 12.0, anchor,    3.0, 90),      # resolve
            ]
            for t, pitch, dur, vel in phrase:
                if t < length:
                    notes.append((t, pitch, min(dur, length - t), vel))
    return notes


def _vox_wail(section: str, length: int) -> list[Note]:
    """Wail tones — long expressive notes. Bridge: A4 -> G4 descending
    over the section. Final Drop: high C#5 / D5 alternating with the Lead."""
    notes: list[Note] = []
    if section == "Bridge":
        # 6/8 24 beats — A4 then G4 then F#4 (descending wail)
        notes += [(0.0,  69, 8.0, 100),     # A4
                  (8.0,  67, 8.0, 95),      # G4
                  (16.0, 66, 8.0, 90)]      # F#4
    elif section == "Final Drop":
        # 4/4 — alternate C#5 (Locrian) and D5 (Mixolydian) every 4 bars
        bars = n_bars(section, length)
        for bar in range(0, bars, 4):
            t = bar * 4
            phrase = (bar // 4) % 2
            pitch = 73 if phrase == 0 else 74
            notes.append((t, pitch, 16.0, 100))
    return notes


def _fx_drone(section: str, length: int) -> list[Note]:
    """Single long held note per section — atmospheric continuity layer."""
    return [(0.0, 41, float(length), 65)]                 # F2 (different from Drone Dark)


def _fx_riser(section: str, length: int) -> list[Note]:
    """Single long note per section — synth patch + automation make the riser
    timbre. Pitch placeholder C4=60."""
    return [(0.0, 60, float(length), 90)]


def _fx_reverse(section: str, length: int) -> list[Note]:
    """Descending reverse swell on the LAST 2 beats of bar 4 of every 4-bar
    phrase. 8 sixteenths from B5 down to C#4. Aspirates into transitions."""
    notes: list[Note] = []
    bars = n_bars(section, length)
    descent = [(2.0,  83, 0.125, 75), (2.25, 80, 0.125, 78),
               (2.5,  78, 0.125, 80), (2.75, 76, 0.125, 82),
               (3.0,  73, 0.125, 85), (3.25, 71, 0.125, 88),
               (3.5,  68, 0.125, 90), (3.75, 61, 0.25, 92)]
    for bar in range(bars):
        if bar % 4 == 3 and bar < bars - 1:
            t = bar * 4
            for dt, pitch, dur, vel in descent:
                notes.append((t + dt, pitch, dur, vel))
    return notes


def _fx_impact(section: str, length: int) -> list[Note]:
    """Transition hits. Pre-Drops punch on 'a of 4' of last bar. Drops punch
    on beat 1 of bar 1 of every 4-bar phrase."""
    notes: list[Note] = []
    level = INTENSITY[section]
    bars = n_bars(section, length)
    if level == 3:
        notes.append(((bars - 1) * 4 + 3.75, 60, 0.5, 118))
    elif level == 4:
        for bar in range(0, bars, 4):
            notes.append((bar * 4, 60, 1.0, 120))
    return notes


def _fx_sub_boom(section: str, length: int) -> list[Note]:
    """Sub punctuation. Drop sections: boom on beat 1 of every 4th bar.
    AUDACITY: Final Drop adds an extra boom on beat 3 of the LAST bar
    only — single deep punctuation that closes the section."""
    notes: list[Note] = []
    if INTENSITY[section] != 4:
        return notes
    bars = n_bars(section, length)
    for bar in range(0, bars, 4):
        notes.append((bar * 4, 25, 1.0, 122))                # C#1 boom
    if section == "Final Drop":
        notes.append(((bars - 1) * 4 + 2, 25, 2.0, 118))     # closing boom
    return notes


def _fx_texture(section: str, length: int) -> list[Note]:
    """Granular texture. Sparse — 1 hit per 4 bars in Verses, 2 in Bridge,
    1 in Outro. Pitch wanders to avoid identification."""
    notes: list[Note] = []
    metre = SECTION_METRE[section]
    bars = n_bars(section, length)
    if metre == (7, 4):
        for bar in range(0, bars, 4):
            t = bar * 7
            pitch = 60 + (bar % 12)                           # wander
            notes.append((t + 3.5, pitch, 1.0, 70))
    elif section == "Bridge":
        for bar in range(0, bars, 4):
            t = bar * 3
            notes.append((t + 1.5, 67, 1.0, 75))
    elif section == "Outro":
        notes.append((4.0, 60, 4.0, 60))
    return notes


NOTE_GENERATORS["15 SYN Lead Cry"]   = _lead_cry
NOTE_GENERATORS["16 SYN Lead Counter"] = _lead_counter
NOTE_GENERATORS["17 SYN Pluck Stab"] = _pluck_stab
NOTE_GENERATORS["18 SYN Choir Wail"] = _choir_wail
NOTE_GENERATORS["19 VOX Guide"]      = _vox_guide
NOTE_GENERATORS["20 VOX Wail"]       = _vox_wail
NOTE_GENERATORS["21 FX Drone"]       = _fx_drone
NOTE_GENERATORS["22 FX Riser"]       = _fx_riser
NOTE_GENERATORS["23 FX Reverse"]     = _fx_reverse
NOTE_GENERATORS["24 FX Impact"]      = _fx_impact
NOTE_GENERATORS["25 FX Sub Boom"]    = _fx_sub_boom
NOTE_GENERATORS["26 FX Texture"]     = _fx_texture


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


# --- EQ8 injection helpers (C2) -------------------------------------------

EQ8_REFERENCE_PATH = ROOT / "tests" / "fixtures" / "reference_project.als"
_EQ8_TEMPLATE_CACHE: str | None = None


def load_eq8_template() -> str:
    """Read a clean EQ8 device XML from the reference project (cached)."""
    global _EQ8_TEMPLATE_CACHE
    if _EQ8_TEMPLATE_CACHE is not None:
        return _EQ8_TEMPLATE_CACHE
    import gzip as _gz
    with _gz.open(EQ8_REFERENCE_PATH, "rb") as f:
        xml = f.read().decode("utf-8")
    m = re.search(r'<Eq8 Id="\d+">.*?</Eq8>', xml, re.DOTALL)
    if not m:
        raise RuntimeError(f"No <Eq8> found in {EQ8_REFERENCE_PATH}")
    _EQ8_TEMPLATE_CACHE = m.group(0)
    return _EQ8_TEMPLATE_CACHE


def clone_eq8(eq8_xml: str, eq8_id_offset: int, new_device_id: int) -> str:
    """Shift every Id="N" (N>=1000) in the EQ8 by `eq8_id_offset` so this
    clone's AutomationTarget Ids etc. don't collide with other clones.
    Then set the outer <Eq8 Id> to `new_device_id` (small, position-in-chain).
    Value="N" attributes are NOT shifted because they often hold parameter
    values (Manual Freq=84.3, Mode=3, etc.) that would corrupt the device."""
    def sub(m: re.Match) -> str:
        n = int(m.group(1))
        if n >= 1000:
            return f'Id="{n + eq8_id_offset}"'
        return m.group(0)
    out = re.sub(r'Id="(\d+)"', sub, eq8_xml)
    out = re.sub(r'<Eq8 Id="\d+"', f'<Eq8 Id="{new_device_id}"', out, count=1)
    return out


def set_eq8_username(eq8_xml: str, name: str) -> str:
    """Set the EQ8's `<UserName Value=...>` so Live's device header shows
    the role (e.g. 'EQ / Kick A'). Touches only the FIRST UserName inside
    the device — the host-level one, not nested preset metadata."""
    safe = (name.replace('&', '&amp;').replace('"', '&quot;')
                .replace('<', '&lt;').replace('>', '&gt;'))
    return re.sub(r'<UserName Value="[^"]*" />',
                  f'<UserName Value="{safe}" />', eq8_xml, count=1)


def set_eq8_band(eq8_xml: str, band_idx: int, *,
                 mode: int | None = None, freq: float | None = None,
                 gain: float | None = None, q: float | None = None,
                 on: bool | None = None) -> str:
    """Set parameters on one EQ8 band by replacing the Manual Value of the
    matching <ParameterA><X> elements inside <Bands.{band_idx}>.

    Modes: 0=LowCut48 1=LowCut12 2=LowShelf 3=Bell 4=Notch 5=HighShelf
           6=HighCut12 7=HighCut48.
    """
    band_pat = re.compile(rf'(<Bands\.{band_idx}>.*?</Bands\.{band_idx}>)', re.DOTALL)
    bm = band_pat.search(eq8_xml)
    if not bm:
        return eq8_xml
    band = bm.group(1)

    def replace_manual(block: str, param_tag: str, new_value: str) -> str:
        # First Manual Value inside <param_tag> (the parameter's current value).
        # We capture: <param_tag> ... <Manual Value="..." /> and replace value.
        pat = re.compile(rf'(<{param_tag}>\s*<LomId Value="0" />\s*<Manual Value=")[^"]*(")', re.DOTALL)
        return pat.sub(rf'\g<1>{new_value}\g<2>', block, count=1)

    if on is not None:
        band = replace_manual(band, "IsOn", "true" if on else "false")
    if mode is not None:
        band = replace_manual(band, "Mode", str(mode))
    if freq is not None:
        band = replace_manual(band, "Freq", str(freq))
    if gain is not None:
        band = replace_manual(band, "Gain", str(gain))
    if q is not None:
        band = replace_manual(band, "Q", str(q))

    return eq8_xml[:bm.start(1)] + band + eq8_xml[bm.end(1):]


def inject_eq8(track_xml: str, eq8_xml: str) -> str:
    """Append the EQ8 device inside the track's first <Devices>...</Devices>
    block (right before its closing tag). The cloned MidiTrack template has
    Serum already inside that block, so the EQ8 ends up AFTER Serum in the
    chain — exactly where you'd put a corrective EQ."""
    closing = track_xml.find('</Devices>')
    if closing < 0:
        raise RuntimeError("No </Devices> in track")
    line_start = track_xml.rfind('\n', 0, closing) + 1
    indent = track_xml[line_start:closing]
    inner_indent = indent + '\t'
    reindented = reindent(eq8_xml, inner_indent)
    return track_xml[:closing] + reindented + '\n' + indent + track_xml[closing:]


# --- Automation envelope helpers (C3a) -------------------------------------
#
# Live stores automations per-TRACK inside <AutomationEnvelopes><Envelopes>.
# Each <AutomationEnvelope> points at a parameter via PointeeId = the param's
# AutomationTarget Id. Volume / Pan live in the track's Mixer (already present
# on every cloned track with their own AutomationTarget Ids).
#
# Value conventions (verified against Acid_Drops_Sections_TFP.als reference):
#   Volume: 0.0003162 = -inf (Min) .. 1.0 = 0 dB unity .. 1.99526 = +6 dB max
#   Pan:   -1.0 (left) .. 0.0 (center) .. +1.0 (right)
#
# An init event at Time=-63072000 sets the parameter's value BEFORE the song
# starts; Live requires this as the first event of every envelope.

def find_param_target_id(track_xml: str, param: str) -> int | None:
    """Find the AutomationTarget Id for a Mixer parameter by name.

    `param` should match the XML tag, e.g. 'Volume', 'Pan', 'SendsListWrapper'.
    Returns None if not found (track has no Mixer or no such param).
    """
    m = re.search(
        rf'<Mixer>.*?<{param}>.*?<AutomationTarget Id="(\d+)"',
        track_xml, re.DOTALL,
    )
    return int(m.group(1)) if m else None


def build_envelope(env_id: int, target_id: int,
                   events: list[tuple[float, float]],
                   event_id_base: int) -> str:
    """Build one <AutomationEnvelope> XML block.

    Args:
        env_id: Unique Id for the envelope itself (within the track).
        target_id: PointeeId — must match the parameter's AutomationTarget Id.
        events: [(time_beat, value), ...] — project-absolute beats.
        event_id_base: First FloatEvent Id; subsequent events use base+1, +2, ...
    """
    if not events:
        return ""
    init_val = events[0][1]
    lines = [
        f'<AutomationEnvelope Id="{env_id}">',
        '\t<EnvelopeTarget>',
        f'\t\t<PointeeId Value="{target_id}" />',
        '\t</EnvelopeTarget>',
        '\t<Automation>',
        '\t\t<Events>',
        f'\t\t\t<FloatEvent Id="{event_id_base}" Time="-63072000" Value="{init_val}" />',
    ]
    for i, (t, v) in enumerate(events):
        lines.append(
            f'\t\t\t<FloatEvent Id="{event_id_base + i + 1}" Time="{t}" Value="{v}" />'
        )
    lines += [
        '\t\t</Events>',
        '\t\t<AutomationTransformViewState>',
        '\t\t\t<IsTransformPending Value="false" />',
        '\t\t\t<TimeAndValueTransforms />',
        '\t\t</AutomationTransformViewState>',
        '\t</Automation>',
        '</AutomationEnvelope>',
    ]
    return '\n'.join(lines)


def inject_envelopes(track_xml: str, envelope_xmls: list[str]) -> str:
    """Replace `<AutomationEnvelopes><Envelopes /></AutomationEnvelopes>` with
    a populated form containing all envelopes. No-op if the track has no
    self-closing Envelopes tag (already populated or structure unexpected)."""
    if not envelope_xmls:
        return track_xml
    pat = re.compile(
        r'(<AutomationEnvelopes>\s*)<Envelopes />(\s*</AutomationEnvelopes>)',
        re.DOTALL,
    )
    m = pat.search(track_xml)
    if not m:
        return track_xml

    # Find the indent of the <Envelopes /> tag specifically
    env_tag_start = m.start(0) + len(m.group(1))
    line_start = track_xml.rfind('\n', 0, env_tag_start) + 1
    outer_indent = track_xml[line_start:env_tag_start]
    inner_indent = outer_indent + '\t'

    reindented = [reindent(env, inner_indent) for env in envelope_xmls]
    replacement = (
        m.group(1) + '<Envelopes>\n' +
        '\n'.join(reindented) + '\n' +
        outer_indent + '</Envelopes>' +
        m.group(2)
    )
    return track_xml[:m.start(0)] + replacement + track_xml[m.end(0):]



# Tuple per band: (band_idx, mode, freq_hz, gain_dB, q, on).
# Modes: 0=LC48 1=LC12 2=LowShelf 3=Bell 4=Notch 5=HighShelf 6=HC12 7=HC48.
EQ8_PRESETS: dict[str, list[tuple]] = {
    "01 DRM Kick A": [
        (0, 0, 30,   0,    0.7, True),    # HPF 30 Hz (subharmonic clean)
        (1, 2, 60,   2.0,  0.7, True),    # Low-shelf +2 dB at 60 Hz (weight)
        (2, 3, 400, -3.0,  1.5, True),    # Bell -3 dB at 400 Hz (mud cut)
    ],
    "02 DRM Kick B": [
        (0, 0, 50,   0,    0.7, True),    # HPF 50 Hz (less low than Kick A)
        (1, 3, 1500, 2.5,  1.2, True),    # Bell +2.5 dB at 1.5 kHz (click)
        (2, 5, 8000, 1.5,  0.7, True),    # High-shelf +1.5 dB (top-end air)
    ],
    "03 DRM Snare A": [
        (0, 0, 100,  0,    0.7, True),    # HPF 100 Hz
        (1, 3, 200,  1.5,  1.2, True),    # Bell +1.5 dB at 200 Hz (body)
        (2, 3, 3500, 2.0,  1.5, True),    # Bell +2 dB at 3.5 kHz (presence)
    ],
    "04 DRM Snare B": [
        (0, 0, 200,  0,    0.7, True),    # HPF 200 Hz (snap layer, no body)
        (1, 3, 5000, 2.5,  1.5, True),    # Bell +2.5 dB at 5 kHz (snap)
    ],
    "05 DRM Clap": [
        (0, 0, 150,  0,    0.7, True),
        (1, 3, 2000, 2.0,  1.2, True),    # presence
    ],
    "06 DRM Rim": [
        (0, 0, 200,  0,    0.7, True),
        (1, 3, 5000, 1.5,  1.5, True),
    ],
    "07 DRM Hats": [
        (0, 0, 250,  0,    0.7, True),    # HPF 250 Hz
        (1, 3, 600, -2.0,  1.5, True),    # cut harshness
        (2, 5, 8000, 2.0,  0.7, True),    # air
    ],
    "08 DRM Open Hat": [
        (0, 0, 300,  0,    0.7, True),
        (1, 5, 6000, 1.5,  0.7, True),
    ],
    "09 DRM Perc": [
        (0, 0, 80,   0,    0.7, True),
    ],
    "10 BAS Sub": [
        (0, 0, 25,   0,    0.7, True),    # HPF 25 Hz
        (1, 2, 50,   1.0,  0.7, True),    # Low-shelf +1 dB at 50 Hz
        (2, 3, 250, -2.0,  1.5, True),    # Bell -2 dB at 250 Hz (mud cut)
    ],
    "11 BAS Punch": [
        (0, 0, 60,   0,    0.7, True),
        (1, 3, 800,  3.0,  1.5, True),    # Bell +3 dB at 800 Hz (click)
        (2, 3, 2500, 1.5,  1.2, True),    # presence
    ],
    "12 BAS Distort": [
        (0, 0, 40,   0,    0.7, True),
        (1, 3, 500, -3.0,  1.5, True),    # mid scoop
        (2, 3, 2000, 2.0,  1.5, True),    # presence
    ],
}


# --- Volume envelope recipes (C3b) ----------------------------------------
#
# Values are on Live's 0.0-1.0 linear scale (0.85 approximates 0 dB unity,
# 0.4 approximates -8 dB, 0.0 is silence). The RISER envelope ramps the FX
# Riser volume up over each Pre-Drop, and does a slower sweep over the
# first 16 beats of the Final Drop. The PUMP envelope ducks the Pad volume
# on beat 1 of every bar during drops (sidechain-like effect without a
# compressor).

def build_volume_envelope_riser(env_id: int, target_id: int,
                                event_id_base: int) -> str:
    """FX Riser volume envelope — ramps up at each Pre-Drop + Final Drop.
    Values on Live's Volume scale: 0.0003 = silent, 1.0 = unity (0 dB)."""
    events = [
        (99.0,  1.0),    # rest at unity before Pre-Drop 1
        (100.0, 0.0003), # Pre-Drop 1 start: silent
        (116.0, 1.0),    # Pre-Drop 1 end: peak (unity) into Drop 1
        (281.0, 1.0),    # rest before Pre-Drop 2
        (282.0, 0.0003), # Pre-Drop 2 start: silent
        (298.0, 1.0),    # Pre-Drop 2 end: peak into Drop 2
        (385.0, 1.0),    # rest before Final Drop
        (386.0, 0.5),    # Final Drop start: ~ -6 dB duck (audible)
        (402.0, 1.0),    # Final Drop bar 4: back to unity
    ]
    return build_envelope(env_id, target_id, events, event_id_base)


def build_pan_envelope_bridge(env_id: int, target_id: int,
                              event_id_base: int) -> str:
    """Pan oscillation during the Bridge (beats 362..386). AUDACITY: three
    cycles with growing amplitude (±0.5 -> ±0.7 -> ±0.9) so the spatial
    motion INCREASES as tension rises into the Final Drop. Pan snaps back
    to center (0.0) right at the Final Drop entry so the peak lands solid.

    Pan value range: -1.0 (hard left) .. +1.0 (hard right). Init 0.0 =
    center (rest outside Bridge)."""
    events = [
        (0.0,   0.0),      # init rest at project start = center
        (361.0, 0.0),      # hold center up to Bridge
        (362.0, -0.5),     # Bridge start: soft left (cycle 1 begin)
        (366.0,  0.5),     # cycle 1 right
        (370.0, -0.7),     # cycle 2 left, bigger
        (374.0,  0.7),     # cycle 2 right
        (378.0, -0.9),     # cycle 3 left, wider
        (382.0,  0.9),     # cycle 3 right, widest
        (386.0,  0.0),     # Final Drop: snap back center
    ]
    return build_envelope(env_id, target_id, events, event_id_base)


def build_volume_envelope_pump(env_id: int, target_id: int,
                               event_id_base: int) -> str:
    """Pad sidechain-pump envelope. Ducks to 0.5 (~ -6 dB) on beat 1 of every
    bar across Drop 1, Drop 2, Final Drop. Recovers to 1.0 (unity) over 1 beat.

    Leading (0.0, 1.0) event keeps the init at unity so the Pad sits at 0 dB
    before the first drop instead of being silent. Values on Live's Volume
    scale: 0.0003 silent, 0.5 ~ -6 dB, 1.0 unity 0 dB."""
    events: list[tuple[float, float]] = [(0.0, 1.0)]    # rest at project start
    drops = [
        (116, 64),   # Drop 1
        (298, 64),   # Drop 2
        (386, 64),   # Final Drop
    ]
    for start, length in drops:
        for bar in range(length // 4):
            beat1 = start + bar * 4
            events.append((float(beat1),     0.5))     # duck ~ -6 dB
            events.append((float(beat1 + 1), 1.0))     # recover unity
    return build_envelope(env_id, target_id, events, event_id_base)


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

    # EQ8 template (loaded once, cloned per drum/bass track)
    eq8_template = load_eq8_template()
    eq8_count = 0

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

        # C2: inject EQ8 on drums + basses
        eq_marker = ""
        if name in EQ8_PRESETS:
            eq8_offset = 2_000_000 + i * 100_000
            eq8 = clone_eq8(eq8_template, eq8_id_offset=eq8_offset, new_device_id=1)
            eq8 = set_eq8_username(eq8, f"EQ / {name.split(' ', 1)[1]}")
            for band_idx, mode, freq, gain, q, on in EQ8_PRESETS[name]:
                eq8 = set_eq8_band(eq8, band_idx, mode=mode, freq=freq,
                                   gain=gain, q=q, on=on)
            clone = inject_eq8(clone, eq8)
            eq8_count += 1
            eq_marker = " + EQ8"

        # C3b: inject volume automation envelopes on FX Riser + Pad
        env_marker = ""
        env_xmls: list[str] = []
        event_id_base = 9_000_000 + i * 10_000
        if name == "22 FX Riser":
            tid = find_param_target_id(clone, "Volume")
            if tid is not None:
                env_xmls.append(build_volume_envelope_riser(
                    env_id=1, target_id=tid, event_id_base=event_id_base))
                env_marker = " + Riser-sweep"
        elif name == "13 SYN Pad":
            tid = find_param_target_id(clone, "Volume")
            if tid is not None:
                env_xmls.append(build_volume_envelope_pump(
                    env_id=1, target_id=tid, event_id_base=event_id_base))
                env_marker = " + Pump"
        elif name == "16 SYN Lead Counter":
            tid = find_param_target_id(clone, "Pan")
            if tid is not None:
                env_xmls.append(build_pan_envelope_bridge(
                    env_id=1, target_id=tid, event_id_base=event_id_base))
                env_marker = " + Pan-Bridge"
        if env_xmls:
            clone = inject_envelopes(clone, env_xmls)

        new_tracks.append(clone)
        print(f"  #{i+1:2d} {name:<22} clips={len(clips):2d} notes={note_total:4d}{eq_marker}{env_marker}")

    print(f"  Injected {eq8_count} EQ8 devices")

    xml = xml[:t12_pos] + "".join(new_tracks) + xml[r2_pos:]

    # Bump NextPointeeId above ALL allocated IDs. My envelope FloatEvent Ids
    # live in the 9M+ range (9_000_000 + i*10_000 + ~200 events per track),
    # so max reserved ~ 9M + 26*10k + 1000 = ~9.27M. Push to 10M + margin.
    max_used = max(
        ID_OFFSET_BASE + len(TRACKS) * ID_OFFSET_STEP + 22155 + 1,
        9_000_000 + len(TRACKS) * 10_000 + 10_000,
    )
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
