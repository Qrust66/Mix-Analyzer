"""Build `Nemesis.als` — aggressive industrial arrangement scaffold.

Brief: drop-C# djent / industrial. Simplicity woven with complexity, rhythmic
AND melodic surprises. 28 tracks across drums / perc / bass / synth / voice /
fx. Asymmetric section lengths (12-bar verse, 6-bar pre-drop, 2-bar silence,
20-bar final drop) to destabilize expectation. C# Phrygian primary, Dorian on
Bridge, half-step pitch-up on first 4 bars of Final Drop.

STEPS 1-10/12 — drums + percussion + basses + pads + leads + arp + acid.
Arp Poly runs a 5-note Phrygian cell as 16ths against the 4/4 grid — the
5-over-4 hemiola means the cycle realigns every 5 bars, giving a
continuously-shifting feel without ever losing the groove. Acid is a
303-style 4-bar phrase featured solo in Break and used as a textural
layer underneath leads in Drop 2 / Final Drop.
"""

from __future__ import annotations

import gzip
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Template.als"
DST = ROOT / "ableton" / "projects" / "Template" / "Template Project" / "Nemesis.als"

TEMPO = 118

# (name, start_beat, length_beat) — 4/4, 1 bar = 4 beats.
# Asymmetric:
#   Verse 1 = 12 bars, Pre-Drop 1 = 6 bars,
#   Silence = 2 bars (total dropout surprise),
#   Final Drop = 20 bars (first 4 bars pitched up a half-step for shock).
SECTIONS = [
    ("Intro",       0,   32),   # 8 bars — atmosphere
    ("Build",       32,  32),   # 8 bars — layers enter
    ("Verse 1",     64,  48),   # 12 bars — groove establishes
    ("Pre-Drop 1",  112, 24),   # 6 bars — fast tension
    ("Drop 1",      136, 64),   # 16 bars — main heavy
    ("Silence",     200, 8),    # 2 bars — total cut (surprise)
    ("Break",       208, 32),   # 8 bars — bass/acid feature
    ("Verse 2",     240, 64),   # 16 bars — complexity adds (arp)
    ("Pre-Drop 2",  304, 32),   # 8 bars — full build
    ("Drop 2",      336, 64),   # 16 bars — Phrygian flavor
    ("Bridge",      400, 32),   # 8 bars — modal shift (Dorian)
    ("Final Drop",  432, 80),   # 20 bars — 4 up + 16 home
    ("Outro",       512, 32),   # 8 bars — fade to drone
]

# 28 tracks. Field order: (name, ableton_color_idx, serum_preset_hint, active_sections).
# The preset hint goes into each cloned Serum 2's <UserName> so Live's device
# header tells the user which patch to load in the Serum browser.
# "→ Drum Rack (...)" means: replace Serum with a Drum Rack of that role.
TRACKS = [
    # Drums — 8 tracks
    ("01 DRM Kick",         2,  "→ Drum Rack (Kick)",
        ["Verse 1", "Pre-Drop 1", "Drop 1", "Verse 2", "Pre-Drop 2", "Drop 2", "Bridge", "Final Drop"]),
    ("02 DRM Sub Kick",     2,  "Sub Kick 808",
        ["Drop 1", "Drop 2", "Final Drop"]),
    ("03 DRM Snare",        3,  "→ Drum Rack (Snare)",
        ["Verse 1", "Pre-Drop 1", "Drop 1", "Verse 2", "Pre-Drop 2", "Drop 2", "Final Drop"]),
    ("04 DRM Clap",         3,  "→ Drum Rack (Clap)",
        ["Drop 1", "Drop 2", "Final Drop"]),
    ("05 DRM Rim",          3,  "→ Drum Rack (Rimshot)",
        ["Verse 1", "Verse 2", "Final Drop"]),
    ("06 DRM Hats",         4,  "→ Drum Rack (Hats)",
        ["Build", "Verse 1", "Pre-Drop 1", "Drop 1", "Break", "Verse 2", "Pre-Drop 2", "Drop 2", "Final Drop"]),
    ("07 DRM Open Hat",     4,  "→ Drum Rack (Open Hat)",
        ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Final Drop"]),
    ("08 DRM Ride",         4,  "→ Drum Rack (Ride)",
        ["Drop 1", "Drop 2", "Final Drop"]),
    # Percussion — 3 tracks
    ("09 PRC Metal",        5,  "Metal Hit FX",
        ["Build", "Drop 1", "Verse 2", "Pre-Drop 2", "Drop 2", "Bridge", "Final Drop"]),
    ("10 PRC Glitch",       6,  "Noise Glitch",
        ["Build", "Pre-Drop 1", "Break", "Pre-Drop 2", "Final Drop"]),
    ("11 PRC Triplet",      6,  "Short Pluck",
        ["Verse 2", "Drop 2", "Final Drop"]),
    # Bass — 4 tracks
    ("12 BAS Sub",          8,  "Sub Sine",
        ["Build", "Verse 1", "Pre-Drop 1", "Drop 1", "Break", "Verse 2", "Pre-Drop 2", "Drop 2", "Bridge", "Final Drop"]),
    ("13 BAS Growl",        11, "Reese Growl",
        ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Final Drop"]),
    ("14 BAS Stab",         11, "FM Bass Stab",
        ["Pre-Drop 1", "Drop 1", "Pre-Drop 2", "Drop 2", "Bridge", "Final Drop"]),
    ("15 BAS Chug",         11, "Drop-C# Chug (djent)",
        ["Drop 1", "Drop 2", "Final Drop"]),
    # Synth — 6 tracks
    ("16 SYN Pad Warm",     14, "Warm Analog Pad",
        ["Intro", "Build", "Verse 1", "Pre-Drop 1", "Drop 1", "Break", "Verse 2", "Pre-Drop 2", "Drop 2", "Bridge", "Final Drop", "Outro"]),
    ("17 SYN Choir Dark",   14, "Dark Choir",
        ["Intro", "Break", "Bridge", "Outro"]),
    ("18 SYN Lead A",       12, "Aggressive Lead",
        ["Pre-Drop 1", "Drop 1", "Drop 2", "Final Drop"]),
    ("19 SYN Lead B",       12, "Counter Harmony Lead",
        ["Drop 1", "Drop 2", "Bridge", "Final Drop"]),
    ("20 SYN Arp Poly",     15, "Pluck Arp (3-over-4)",
        ["Verse 2", "Pre-Drop 2", "Drop 2", "Bridge", "Final Drop"]),
    ("21 SYN Acid",         15, "Acid 303",
        ["Break", "Drop 2", "Final Drop"]),
    # Voice — 2 tracks
    ("22 VOX Guide",        16, "Formant Voice",
        ["Verse 1", "Drop 1", "Verse 2", "Drop 2", "Bridge", "Final Drop"]),
    ("23 VOX Chops",        17, "Chop Texture",
        ["Build", "Break", "Drop 1", "Drop 2", "Bridge", "Final Drop", "Outro"]),
    # FX — 5 tracks
    ("24 FX Drone",         19, "Atmosphere Drone",
        ["Intro", "Build", "Silence", "Break", "Bridge", "Outro"]),
    ("25 FX Riser",         9,  "Noise Riser",
        ["Pre-Drop 1", "Pre-Drop 2", "Final Drop"]),
    ("26 FX Impact",        9,  "Noise Impact",
        ["Pre-Drop 1", "Drop 1", "Pre-Drop 2", "Drop 2", "Final Drop"]),
    ("27 FX Reverse",       9,  "Reverse Swell",
        ["Pre-Drop 1", "Break", "Pre-Drop 2", "Bridge", "Final Drop"]),
    ("28 FX Noise Burst",   19, "Noise Burst",
        ["Build", "Drop 1", "Pre-Drop 2", "Drop 2", "Final Drop"]),
]


# --- Note pattern generators (all empty stubs for STEP 1 — filled in STEPS 4-11) ---

# A MIDI note is (time_beat, pitch, duration_beat, velocity)
Note = tuple[float, int, float, int]


def _noop(section: str, length: int) -> list[Note]:
    return []


# Intensity table: 0=ambient, 1=texture, 2=verse, 3=pre-drop, 4=drop
INTENSITY = {
    "Intro": 0, "Outro": 0, "Silence": 0,
    "Build": 1, "Break": 1, "Bridge": 1,
    "Verse 1": 2, "Verse 2": 2,
    "Pre-Drop 1": 3, "Pre-Drop 2": 3,
    "Drop 1": 4, "Drop 2": 4, "Final Drop": 4,
}


# --- Drums pilier ----------------------------------------------------------

def _kick(section: str, length: int) -> list[Note]:
    """Aggressive djent kick. Two-bar A/B alternation in verses/drops.
    Surprises: 'hole' on bar 12 of Verse 1 (skip beat 1); bar 15 of Drop 1
    is a displaced pattern (hemiola illusion); Final Drop bars 1-4 punch
    harder to announce the half-step pitch up."""
    notes: list[Note] = []
    level = INTENSITY[section]
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        ab = bar % 2

        if level == 2:  # Verse — half-time with push
            # SURPRISE: Verse 1 last bar -> skip beat 1 entirely
            if section == "Verse 1" and bar == bars - 1:
                notes += [(t + 2.5, 36, 0.125, 95), (t + 3, 36, 0.25, 108)]
                continue
            if ab == 0:
                notes += [(t, 36, 0.25, 115),
                          (t + 0.75, 36, 0.125, 95),
                          (t + 2, 36, 0.25, 108)]
            else:
                notes += [(t, 36, 0.25, 115),
                          (t + 1.75, 36, 0.125, 92),
                          (t + 2, 36, 0.25, 108),
                          (t + 2.5, 36, 0.125, 95)]

        elif level == 3:  # Pre-Drop — density ramps; 16th roll on last bar
            if bar == bars - 1:
                for s in range(16):
                    notes.append((t + s * 0.25, 36, 0.1, 80 + s * 2))
            elif bar == bars - 2:
                notes += [(t, 36, 0.25, 115),
                          (t + 1, 36, 0.25, 105),
                          (t + 2, 36, 0.25, 115),
                          (t + 2.5, 36, 0.125, 100),
                          (t + 3, 36, 0.25, 110),
                          (t + 3.75, 36, 0.125, 105)]
            elif bar >= 1:
                notes += [(t, 36, 0.25, 108),
                          (t + 2, 36, 0.25, 108),
                          (t + 3.75, 36, 0.125, 95)]
            else:
                notes += [(t, 36, 0.25, 105), (t + 2, 36, 0.25, 105)]

        elif level == 4:  # Drop — busy gallop
            # SURPRISE: Drop 1 bar 15 -> displaced pattern (kick off beat 1)
            if section == "Drop 1" and bar == 14:
                notes += [(t + 0.5, 36, 0.125, 110),
                          (t + 1.5, 36, 0.25, 108),
                          (t + 2, 36, 0.25, 115),
                          (t + 2.75, 36, 0.125, 98)]
                continue
            # Final Drop bars 1-4: pitched-up section, punch harder
            if section == "Final Drop" and bar < 4:
                notes += [(t, 36, 0.25, 122),
                          (t + 0.5, 36, 0.125, 88),
                          (t + 1, 36, 0.125, 95),
                          (t + 1.5, 36, 0.25, 108),
                          (t + 2, 36, 0.25, 122),
                          (t + 2.75, 36, 0.125, 95),
                          (t + 3, 36, 0.25, 112),
                          (t + 3.75, 36, 0.125, 100)]
                continue
            if ab == 0:
                notes += [(t, 36, 0.25, 120),
                          (t + 0.5, 36, 0.125, 90),
                          (t + 1, 36, 0.25, 108),
                          (t + 1.75, 36, 0.125, 95),
                          (t + 2, 36, 0.25, 118),
                          (t + 2.75, 36, 0.125, 95),
                          (t + 3, 36, 0.25, 110)]
            else:
                notes += [(t, 36, 0.25, 120),
                          (t + 0.75, 36, 0.125, 88),
                          (t + 1, 36, 0.25, 108),
                          (t + 2, 36, 0.25, 118),
                          (t + 2.5, 36, 0.125, 98),
                          (t + 3, 36, 0.25, 110),
                          (t + 3.75, 36, 0.125, 102)]

        elif section == "Bridge":  # sparse, just gravitas on every 2 bars
            if bar % 2 == 0:
                notes.append((t, 36, 0.5, 115))
    return notes


def _sub_kick(section: str, length: int) -> list[Note]:
    """808 sub layer — downbeats and beat 3 in drops. Pitch is C#1 (25),
    except Final Drop bars 1-4 pitch up to D1 (26). Drop 2 last bar has a
    Phrygian chromatic descent C#->C->B to reset tension."""
    notes: list[Note] = []
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        pitch = 25
        if section == "Final Drop" and bar < 4:
            pitch = 26
        # Drop 2 last bar: chromatic descent
        if section == "Drop 2" and bar == bars - 1:
            notes += [(t, 25, 0.5, 122),
                      (t + 1.5, 24, 0.25, 115),
                      (t + 2, 24, 0.25, 115),
                      (t + 3, 23, 1.0, 112)]
            continue
        notes += [(t, pitch, 0.5, 122), (t + 2, pitch, 0.5, 118)]
    return notes


def _snare(section: str, length: int) -> list[Note]:
    """Backbeat with ghost anticipations. Surprises: Verse 1 last bar skips
    beat 2; Drop 1 bar 15 displaces the snare to push the groove sideways."""
    notes: list[Note] = []
    level = INTENSITY[section]
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        if level == 2:  # Verse
            # SURPRISE: Verse 1 last bar -> only beat 4
            if section == "Verse 1" and bar == bars - 1:
                notes += [(t + 3, 38, 0.25, 118), (t + 3.5, 38, 0.0625, 80)]
                continue
            notes += [(t + 1, 38, 0.25, 112), (t + 3, 38, 0.25, 115)]
            notes.append((t + 2.75, 38, 0.0625, 55))
        elif level == 3:  # Pre-Drop
            notes += [(t + 1, 38, 0.25, 110), (t + 3, 38, 0.25, 115)]
            if bar == bars - 1:
                for s in range(8):
                    notes.append((t + 2 + s * 0.25, 38, 0.1, 80 + s * 5))
        elif level == 4:  # Drop
            # SURPRISE: Drop 1 bar 15 -> displaced
            if section == "Drop 1" and bar == 14:
                notes += [(t + 1.25, 38, 0.25, 115),
                          (t + 2, 38, 0.25, 108),
                          (t + 2.75, 38, 0.125, 88),
                          (t + 3.25, 38, 0.25, 120)]
                continue
            notes += [(t + 1, 38, 0.25, 118), (t + 3, 38, 0.25, 122)]
            notes += [(t + 1.75, 38, 0.0625, 60),
                      (t + 2.75, 38, 0.0625, 58),
                      (t + 3.75, 38, 0.0625, 70)]
    return notes


def _clap(section: str, length: int) -> list[Note]:
    """Clap stacked on snare in drops only. Slight +16 tick lag gives the
    layered attack feel. Final Drop bars 5-20 add 'a of 4' push claps."""
    notes: list[Note] = []
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        notes += [(t + 1.015, 39, 0.25, 100),
                  (t + 3.015, 39, 0.25, 105)]
        if section == "Final Drop" and bar >= 4:
            notes.append((t + 3.75, 39, 0.125, 85))
    return notes


# --- Drums texture ---------------------------------------------------------

def _hats(section: str, length: int) -> list[Note]:
    """Closed hats as time-keeper. 8ths in verses/build, 16ths in drops with
    humanized velocity accent pattern. SURPRISE: Drop 1 bar 15 drops out for
    the first half-beat so the kick displacement breathes."""
    notes: list[Note] = []
    level = INTENSITY[section]
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        # Drop 1 bar 15: dropout for first 2 16th-steps
        if section == "Drop 1" and bar == 14:
            for s in range(2, 16):
                pos = s * 0.25
                vel = 105 if s % 4 == 0 else (78 if s % 2 == 0 else 62)
                notes.append((t + pos, 42, 0.15, vel))
            continue
        if level == 0:
            continue
        if level == 1:  # Build / Break — quiet 8ths
            for s in range(8):
                notes.append((t + s * 0.5, 42, 0.3, 72 if s % 2 == 0 else 55))
        elif level == 2:  # Verse — 8ths
            for s in range(8):
                notes.append((t + s * 0.5, 42, 0.25, 94 if s % 2 == 0 else 72))
        elif level == 3:  # Pre-Drop — 16ths, ramping
            for s in range(16):
                vel = 108 if s % 4 == 0 else (80 if s % 2 == 0 else 64)
                notes.append((t + s * 0.25, 42, 0.15, vel))
        elif level == 4:  # Drop — driving 16ths, humanized accent pattern
            accent = [118, 62, 82, 64, 98, 62, 88, 64,
                      105, 62, 82, 64, 98, 62, 92, 78]
            for s in range(16):
                notes.append((t + s * 0.25, 42, 0.15, accent[s]))
    return notes


def _open_hat(section: str, length: int) -> list[Note]:
    """Open hat accents on '&' of 2 and '&' of 4 in verses/drops — the classic
    chick groove that locks with snare backbeat. Bridge: single downbeat
    open per bar for gravitas. Final Drop adds 'a of 4' push."""
    notes: list[Note] = []
    level = INTENSITY[section]
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        if section == "Bridge":
            notes.append((t, 46, 0.5, 92))
            continue
        if level == 2:  # Verse
            notes += [(t + 1.5, 46, 0.5, 92), (t + 3.5, 46, 0.5, 98)]
        elif level == 4:  # Drop
            notes += [(t + 1.5, 46, 0.5, 95), (t + 3.5, 46, 0.5, 102)]
            if section == "Final Drop" and bar >= 4:
                notes.append((t + 3.75, 46, 0.25, 85))
    return notes


def _rim(section: str, length: int) -> list[Note]:
    """Cross-stick pull on 'e of 3' (beat 2.25) — creates a subtle
    polyrhythmic drag against the main groove. Bar 4 of every phrase adds
    an 'a of 1' pickup (beat 0.75) so the 4-bar loop breathes."""
    notes: list[Note] = []
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        if section in ("Verse 1", "Verse 2"):
            notes.append((t + 2.25, 37, 0.1, 88))
            if bar % 4 == 3:
                notes.append((t + 0.75, 37, 0.1, 78))
        elif section == "Final Drop":
            notes.append((t + 2.25, 37, 0.1, 92))
            if bar % 4 == 3:
                notes.append((t + 3.75, 37, 0.1, 82))
    return notes


def _ride(section: str, length: int) -> list[Note]:
    """Ride bell in drops — 8ths with 1/3 accents normally, 16ths during the
    Final Drop pitched-up bars (1-4) for that extra intensity on the surprise."""
    notes: list[Note] = []
    if INTENSITY[section] != 4:
        return notes
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        if section == "Final Drop" and bar < 4:
            for s in range(16):
                vel = 115 if s % 4 == 0 else 75
                notes.append((t + s * 0.25, 51, 0.2, vel))
        else:
            for s in range(8):
                on_beat = (s * 0.5) % 2 == 0
                notes.append((t + s * 0.5, 51, 0.4, 112 if on_beat else 82))
    return notes


# --- Percussion ------------------------------------------------------------

def _metal(section: str, length: int) -> list[Note]:
    """Industrial metal hit (cowbell slot, pitch 56). Big downbeat on bar 1
    of every 4-bar phrase + 'a of 4' push on odd bars. Drops get mid-bar
    stabs every 4th bar; Bridge gets a beat-3 accent per phrase."""
    notes: list[Note] = []
    bars = length // 4
    level = INTENSITY[section]
    for bar in range(bars):
        t = bar * 4
        if bar % 4 == 0:
            notes.append((t, 56, 0.5, 118))
        if bar % 2 == 1:
            notes.append((t + 3.75, 56, 0.125, 92))
        if level == 4 and bar % 4 == 2:
            notes += [(t + 1.5, 56, 0.125, 95),
                      (t + 2.75, 56, 0.125, 98)]
        if section == "Bridge" and bar % 4 == 0:
            notes.append((t + 3, 56, 0.25, 100))
    return notes


def _glitch(section: str, length: int) -> list[Note]:
    """Stuttered noise bursts. Pitch climbs 60 -> 64 -> 67 -> 72 for tension.
    Pre-Drops escalate then finish with a 16th stutter roll on the last bar
    to smash into the drop."""
    notes: list[Note] = []
    bars = length // 4
    pitches = [60, 64, 67, 72]
    if section == "Build":
        for t, p, d, v in [(6, 60, 0.125, 85), (10, 64, 0.125, 90),
                            (18, 67, 0.125, 95), (26, 72, 0.25, 100)]:
            notes.append((float(t), p, d, v))
    elif section in ("Pre-Drop 1", "Pre-Drop 2"):
        for bar in range(bars - 1):
            t = bar * 4
            notes.append((t + 1.75, pitches[bar % 4], 0.125, 80 + bar * 8))
            notes.append((t + 3.5,  pitches[(bar + 1) % 4], 0.125, 85 + bar * 6))
        tl = (bars - 1) * 4
        for s in range(16):
            notes.append((tl + s * 0.25, 72, 0.1, 70 + s * 3))
    elif section == "Break":
        for bar in range(bars):
            t = bar * 4
            if bar % 2 == 0:
                notes.append((t + 0.75, 60, 0.125, 78))
            else:
                notes.append((t + 2.25, 64, 0.125, 72))
    elif section == "Bridge":
        for bar in range(bars):
            if bar % 2 == 1:
                notes.append((bar * 4 + 3.75, 67, 0.125, 82))
    return notes


def _triplet(section: str, length: int) -> list[Note]:
    """Polyrhythmic layer — 8th-note triplets over the 4/4 grid (3-over-2 feel).
    Enters gently in Verse 2 (every other bar), full density in Drop 2 and
    Final Drop 5+, peaks as 16th-triplets (24 notes/bar) in Final Drop bars
    1-4 to match the pitched-up surprise."""
    notes: list[Note] = []
    bars = length // 4
    third = 1.0 / 3.0
    sixth = 1.0 / 6.0
    for bar in range(bars):
        t = bar * 4
        if section == "Verse 2":
            if bar % 2 != 0:
                continue
            for beat in range(4):
                for s in range(3):
                    vel = 92 if s == 0 else 62
                    notes.append((round(t + beat + s * third, 12), 60, 0.2, vel))
        elif section == "Final Drop" and bar < 4:
            for s in range(24):
                vel = 95 if s % 6 == 0 else 65
                notes.append((round(t + s * sixth, 12), 60, 0.15, vel))
        else:  # Drop 2, Final Drop bars 5+
            for beat in range(4):
                for s in range(3):
                    vel = 102 if s == 0 else 72
                    notes.append((round(t + beat + s * third, 12), 60, 0.2, vel))
    return notes


# --- Basses (C# Phrygian: C# D E F# G# A B) --------------------------------
#
# Key MIDI pitches:
#   C#1=25  D1=26  E1=28  F#1=30  G#1=32  A1=33  B1=35
#   C#2=37  D2=38  E2=40  F#2=42  G#2=44  A2=45  B2=47
#
# Phrygian tension notes: flat-2 (D against root C#), flat-6 (A).

def _bas_sub(section: str, length: int) -> list[Note]:
    """Sub foundation. 4-bar phrase C# -> C# -> A (flat-6) -> G# (dominant).
    Drops add octave-down stab on 'a of 4'. Drop 2 substitutes D (flat-2)
    on bars 4 and 12 for Phrygian push. Final Drop bars 1-4 pitch up to D."""
    notes: list[Note] = []
    bars = length // 4
    prog = [25, 25, 33, 32]  # C#1, C#1, A1, G#1
    for bar in range(bars):
        t = bar * 4
        root = prog[bar % 4]
        if section == "Final Drop" and bar < 4:
            root = 26  # D1 up-shift
        if section == "Drop 2" and bar in (3, 11):
            root = 26  # D1 flat-2 Phrygian push
        notes.append((t, root, 4.0, 108))
        if INTENSITY[section] == 4 and bar % 4 == 3:
            notes.append((t + 3.75, root - 12, 0.25, 92))
    return notes


def _bas_growl(section: str, length: int) -> list[Note]:
    """Reese-style drone. 2-bar phrase alternating C#2 / A2 (root / flat-6).
    Retriggered every 2 beats in drops for density. Drop 2 last bar has a
    chromatic slide B2 -> C2 -> C#2 to snap back to root."""
    notes: list[Note] = []
    level = INTENSITY[section]
    bars = length // 4
    prog = [37, 45]  # C#2, A2
    for bar in range(bars):
        t = bar * 4
        root = prog[bar % 2]
        if section == "Drop 2" and bar == 11:
            root = 38  # D2 flat-2 push
        if section == "Final Drop" and bar < 4:
            root = 38  # D2 up-shift
        if level == 2:
            notes.append((t, root, 4.0, 100))
        else:
            notes += [(t, root, 2.0, 112), (t + 2, root, 2.0, 108)]
    if section == "Drop 2":
        last = (bars - 1) * 4
        notes = [n for n in notes if n[0] < last]
        notes += [(last,       47, 1.0, 105),   # B2
                  (last + 1,   48, 1.0, 108),   # C3 (chromatic)
                  (last + 2,   37, 2.0, 118)]   # C#2 resolve
    return notes


def _bas_stab(section: str, length: int) -> list[Note]:
    """Chromatic stabs — the menace layer. Default: C#2 on 'a of 2', D2
    (flat-2 Phrygian) on 'e of 4'. Bridge swaps to Dorian flavor (D#2).
    Final Drop bars 1-4 fully pitch up to D2 / D#2."""
    notes: list[Note] = []
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        if section == "Final Drop" and bar < 4:
            notes += [(t + 1.75, 38, 0.125, 105),  # D2
                      (t + 3.25, 39, 0.125, 100)]  # D#2
        elif section == "Bridge":
            notes += [(t + 1.75, 37, 0.125, 98),   # C#2
                      (t + 3.25, 39, 0.125, 95)]   # D#2 (Dorian)
        else:
            notes += [(t + 1.75, 37, 0.125, 102),  # C#2
                      (t + 3.25, 38, 0.125, 98)]   # D2 (Phrygian)
    return notes


def _bas_chug(section: str, length: int) -> list[Note]:
    """Djent palm-mute chug — the guitar mirror. 16th chug at low velocity
    (68) with power-chord ring-outs (vel 115, duration 0.75) on beats 1/3.
    'Respiratory silence': every 2nd bar skips the 16ths around beat 3
    (steps 8-11) so the kick punches through and the track breathes.
    SURPRISE: Drop 1 bar 15 is fully silent (complements kick displacement).
    Drop 2: bar 4 of each 4-bar phrase pitches to D (flat-2). Final Drop
    bars 1-4 pitch to D (up-shift)."""
    notes: list[Note] = []
    bars = length // 4
    for bar in range(bars):
        t = bar * 4
        if section == "Drop 1" and bar == 14:
            continue  # full silence — negative space surprise
        base = 25  # C#1
        if section == "Final Drop" and bar < 4:
            base = 26  # D1
        if section == "Drop 2" and bar % 4 == 3:
            base = 26  # flat-2 push
        for s in range(16):
            if bar % 2 == 1 and 8 <= s <= 11:
                continue  # respiratory silence around beat 3
            pos = s * 0.25
            if s in (0, 8):
                notes.append((t + pos, base, 0.75, 115))  # ring-out power
            elif s in (6, 14):
                notes.append((t + pos, base, 0.15, 88))   # accented pickup
            else:
                notes.append((t + pos, base, 0.12, 68))   # palm-mute chug
    return notes


# --- Pads & choir ----------------------------------------------------------
#
# Four-note voicings. Pad main progression is a C# Phrygian loop with the
# signature bII (D major) push on the second chord. Bridge modulates to C#
# Dorian (raised 6 = A#/Bb nat) for modal relief. Final Drop bars 1-4 shift
# the whole progression up a half-step to D Phrygian, then bars 5-20 return
# home to C# Phrygian.

PAD_CS_PHRYGIAN = [
    [49, 52, 56, 62],   # C#m(b9)   : C#3 E3 G#3 D4   (root + b9 on top = signature)
    [50, 54, 57, 62],   # Dmaj      : D3 F#3 A3 D4    (bII push)
    [54, 57, 61, 66],   # F#m       : F#3 A3 C#4 F#4  (minor iv)
    [56, 59, 62, 66],   # G#sus2    : G#3 B3 D4 F#4   (v sus for breath)
]

PAD_CS_DORIAN = [
    [49, 52, 56, 62],   # C#m       : C#3 E3 G#3 D4
    [54, 58, 61, 66],   # F#maj     : F#3 A#3 C#4 F#4 (Dorian IV = raised 6!)
    [51, 54, 58, 61],   # D#m       : D#3 F#3 A#3 C#4 (ii of Dorian)
    [56, 59, 63, 66],   # G#m       : G#3 B3 D#4 F#4
]

PAD_D_PHRYGIAN = [
    [50, 53, 57, 63],   # Dm(b9)    : D3 F3 A3 Eb4    (up-shifted signature)
    [51, 55, 58, 63],   # Ebmaj     : Eb3 G3 Bb3 Eb4  (bII up-shift)
    [55, 58, 62, 67],   # Gm        : G3 Bb3 D4 G4
    [57, 60, 64, 69],   # Am        : A3 C4 E4 A4
]


def _pad_warm(section: str, length: int) -> list[Note]:
    """Main harmonic pad. 4-note voicings, 4 bars per chord. Anticipation
    swell on bar 4 of each phrase (top note of the NEXT chord, 0.5 beats
    before the barline) so the change lands with momentum."""
    bars = length // 4

    def chord_for_bar(bar: int) -> list[int]:
        if section == "Bridge":
            return PAD_CS_DORIAN[bar % 4]
        if section == "Final Drop" and bar < 4:
            return PAD_D_PHRYGIAN[bar % 4]
        if section == "Final Drop":  # bars 5+
            return PAD_CS_PHRYGIAN[(bar - 4) % 4]
        if section in ("Intro", "Outro"):
            return [49, 52, 56]  # 3-note C#m drone, no top extension
        return PAD_CS_PHRYGIAN[bar % 4]

    notes: list[Note] = []
    for bar in range(bars):
        t = bar * 4
        chord = chord_for_bar(bar)
        vel = 62 if section in ("Intro", "Outro") else 75
        for pitch in chord:
            notes.append((t, pitch, 4.0, vel))
        # Anticipation swell on bar 4 of each 4-bar phrase
        if bar % 4 == 3 and bar < bars - 1:
            next_top = chord_for_bar(bar + 1)[-1]
            notes.append((t + 3.5, next_top, 0.5, 82))
    return notes


def _choir_dark(section: str, length: int) -> list[Note]:
    """Low-register 3-note drone. Phrygian shell C#2 G#2 C#3 by default.
    Bridge cycles a 4-bar Dorian progression (C#m -> F#maj -> C#m -> G#m)
    in a low voicing, echoing the pad a register down."""
    bars = length // 4
    if section == "Bridge":
        voicings = [[37, 44, 49], [42, 46, 54],
                    [37, 44, 49], [44, 47, 56]]
    else:
        voicings = [[37, 44, 49]]
    notes: list[Note] = []
    for bar in range(bars):
        t = bar * 4
        for pitch in voicings[bar % len(voicings)]:
            notes.append((t, pitch, 4.0, 60))
    return notes


NOTE_GENERATORS: dict[str, "callable"] = {name: _noop for (name, *_) in TRACKS}
NOTE_GENERATORS["01 DRM Kick"]      = _kick
NOTE_GENERATORS["02 DRM Sub Kick"]  = _sub_kick
NOTE_GENERATORS["03 DRM Snare"]     = _snare
NOTE_GENERATORS["04 DRM Clap"]      = _clap
NOTE_GENERATORS["05 DRM Rim"]       = _rim
NOTE_GENERATORS["06 DRM Hats"]      = _hats
NOTE_GENERATORS["07 DRM Open Hat"]  = _open_hat
NOTE_GENERATORS["08 DRM Ride"]      = _ride
NOTE_GENERATORS["09 PRC Metal"]     = _metal
NOTE_GENERATORS["10 PRC Glitch"]    = _glitch
NOTE_GENERATORS["11 PRC Triplet"]   = _triplet
NOTE_GENERATORS["12 BAS Sub"]       = _bas_sub
NOTE_GENERATORS["13 BAS Growl"]     = _bas_growl
NOTE_GENERATORS["14 BAS Stab"]      = _bas_stab
NOTE_GENERATORS["15 BAS Chug"]      = _bas_chug
NOTE_GENERATORS["16 SYN Pad Warm"]  = _pad_warm
NOTE_GENERATORS["17 SYN Choir Dark"] = _choir_dark
# --- Leads -----------------------------------------------------------------
#
# Lead A pitches in C# Phrygian (lead register):
#   C#4=61  D4=62  E4=64  F#4=66  G#4=68  A4=69  B4=71
#   C#5=73  D5=74  E5=76  F#5=78  G#5=80  A5=81  B5=83  C#6=85
# Tritone-from-C# = G natural (G4=67, G5=79) — the chromatic SURPRISE note.

# 8-bar (32-beat) Lead A phrase — original. Beats relative to phrase start.
# Bars 1-2: climb to C#5 peak, descend to G nat (tritone surprise).
# Bar 3: question ending. Bar 4: rest (negative space).
# Bars 5-6: plunge from G4 down through A3, with G nat chromatic in bar 6.
# Bars 7-8: resolution arc up to C#5 tail.
LEAD_A_PHRASE = [
    # Bar 1 — climb
    (0.0,  61, 0.5,  105),  # C#4
    (0.5,  64, 0.5,  100),  # E4
    (1.0,  68, 1.0,  110),  # G#4
    (2.0,  73, 2.0,  118),  # C#5 PEAK held
    # Bar 2 — re-trigger and descend with tritone surprise
    (4.0,  73, 1.0,  110),  # C#5
    (5.0,  71, 0.5,  100),  # B4
    (5.5,  69, 0.5,   95),  # A4
    (6.0,  67, 1.5,  105),  # G nat 4 — TRITONE SURPRISE
    (7.5,  66, 0.5,   90),  # F#4
    # Bar 3 — question ending
    (8.0,  64, 1.5,   98),  # E4
    (9.5,  62, 0.5,   92),  # D4
    (10.0, 61, 2.0,  100),  # C#4 (rests on bar 4)
    # Bar 4 — silence (negative space)
    # Bar 5 — plunge from G nat
    (16.0,  67, 0.25, 102),  # G nat 4 (echo)
    (16.25, 66, 0.25,  95),
    (16.5,  64, 0.25,  95),
    (16.75, 62, 0.25,  95),
    (17.0,  61, 1.0,  105),  # C#4
    (18.0,  59, 1.0,  100),  # B3
    (19.0,  57, 1.0,  100),  # A3
    # Bar 6 — chromatic descent
    (20.0,  56, 1.0,   95),  # G#3
    (21.0,  57, 0.5,   92),  # A3 (turn)
    (21.5,  55, 0.5,   88),  # G nat 3 (chromatic)
    (22.0,  54, 1.0,   92),  # F#3
    (23.0,  52, 1.0,   95),  # E3
    # Bar 7 — resolution arc up
    (24.0,  61, 0.5,  100),  # C#4
    (24.5,  64, 0.5,  100),  # E4
    (25.0,  68, 1.0,  105),  # G#4
    (26.0,  69, 2.0,  110),  # A4
    # Bar 8 — tail
    (28.0,  73, 4.0,  100),  # C#5
]


def _lead_a(section: str, length: int) -> list[Note]:
    """Main lead. Repeats the 8-bar phrase as many times as the section
    affords. Drop 2 phrase 2 displaces the call up an octave for ascent.
    Final Drop bars 1-4 (first 16 beats) pitch up a half-step (D Phrygian)."""
    notes: list[Note] = []
    n_phrases = max(1, length // 32 + (1 if length % 32 else 0))
    for p in range(n_phrases):
        base_t = p * 32
        if base_t >= length:
            break
        for (dt, pitch, dur, vel) in LEAD_A_PHRASE:
            t = base_t + dt
            if t >= length:
                continue
            new_pitch = pitch
            # Drop 2 phrase 2: octave-up call portion (bars 1-3 of phrase)
            if section == "Drop 2" and p == 1 and dt < 12:
                new_pitch += 12
            # Final Drop bars 1-4 (= first 16 beats): half-step up to D
            if section == "Final Drop" and t < 16:
                new_pitch += 1
            notes.append((t, new_pitch, min(dur, length - t), vel))
    return notes


def _lead_b(section: str, length: int) -> list[Note]:
    """Counter-lead. In drops: silent during Lead A's call (bars 1-3), fills
    bar 4 with a quick arp, then harmonizes a third below on bars 5-8.
    Bridge gives it an exposed solo phrase in C# Dorian, using A#4 (the
    raised-6 signature) as the tonal peak."""
    notes: list[Note] = []

    if section == "Bridge":
        # 8-bar solo in C# Dorian (C# D# E F# G# A# B)
        bridge_phrase = [
            (0.0,   61, 1.0, 105),   # C#4
            (1.0,   63, 1.0, 100),   # D#4 (Dorian)
            (2.0,   64, 0.5, 102),   # E4
            (2.5,   66, 0.5, 100),   # F#4
            (3.0,   68, 1.0, 108),   # G#4
            (4.0,   70, 2.0, 112),   # A#4 — Dorian raised-6 PEAK
            (6.0,   71, 1.0, 100),   # B4
            (7.0,   73, 1.0, 110),   # C#5 octave resolve
            (8.0,   71, 1.0,  95),
            (9.0,   68, 1.0,  95),
            (10.0,  70, 2.0, 100),   # A#4 hold
            (12.0,  66, 1.0,  92),
            (13.0,  64, 1.0,  90),
            (14.0,  63, 0.5,  88),
            (14.5,  61, 1.5, 100),   # C#4 resolve
            (16.0,  61, 4.0,  95),   # tail
            # Second half — sparser echo
            (24.0,  73, 2.0, 105),   # C#5
            (26.0,  70, 2.0, 100),   # A#4
            (28.0,  68, 4.0,  95),   # G#4 fade
        ]
        for (dt, pitch, dur, vel) in bridge_phrase:
            if dt < length:
                notes.append((dt, pitch, min(dur, length - dt), vel))
        return notes

    # Drops: counter-phrasing with Lead A
    n_phrases = max(1, length // 32 + (1 if length % 32 else 0))
    for p in range(n_phrases):
        base_t = p * 32
        if base_t >= length:
            break
        # Bar 4 fill (Lead A rests) — quick arp C#-E-G#-C#-G#-E-C#
        fill = [
            (12.0,  61, 0.5,  95),
            (12.5,  64, 0.5,  95),
            (13.0,  68, 0.5, 100),
            (13.5,  73, 0.5, 105),
            (14.0,  68, 0.5, 100),
            (14.5,  64, 0.5,  95),
            (15.0,  61, 0.5,  90),
        ]
        # Bars 7-8 harmony (third below Lead A's peak)
        harm = [
            (24.0,  57, 0.5,  92),   # A3 (m3 below C#4)
            (24.5,  61, 0.5,  92),   # C#4
            (25.0,  64, 1.0,  98),   # E4
            (26.0,  66, 2.0, 105),   # F#4 (m3 below A4)
            (28.0,  69, 4.0,  95),   # A4 (m3 below C#5)
        ]
        for (dt, pitch, dur, vel) in fill + harm:
            t = base_t + dt
            if t >= length:
                continue
            new_pitch = pitch
            if section == "Final Drop" and t < 16:
                new_pitch += 1  # up-shift
            notes.append((t, new_pitch, min(dur, length - t), vel))
    return notes


# --- Arp Poly & Acid -------------------------------------------------------

def _arp_poly(section: str, length: int) -> list[Note]:
    """5-over-4 hemiola arp. 5-note cell repeated as 16ths against the 4/4
    grid — realigns every 5 bars. Phrygian cell C#4 E4 G#4 B4 C#5 normally;
    Bridge swaps to Dorian cell with A#4 raised-6. Verse 2 plays every other
    bar (gentler intro). Drop 2 last bar: all pitches +12 for octave surprise.
    Final Drop bars 1-4: all pitches +1 for up-shift."""
    if section == "Bridge":
        cell = [61, 63, 66, 68, 70]   # C#4 D#4 F#4 G#4 A#4 (Dorian)
    else:
        cell = [61, 64, 68, 71, 73]   # C#4 E4 G#4 B4 C#5 (Phrygian)
    vel_cell = [100, 72, 80, 72, 88]

    notes: list[Note] = []
    total_steps = int(length / 0.25)
    bars = length // 4
    for s in range(total_steps):
        t = s * 0.25
        bar_idx = int(t) // 4
        if section == "Verse 2" and bar_idx % 2 != 0:
            continue
        offset = 0
        if section == "Drop 2" and bar_idx == bars - 1:
            offset = 12
        if section == "Final Drop" and bar_idx < 4:
            offset = 1
        notes.append((t, cell[s % 5] + offset, 0.2, vel_cell[s % 5]))
    return notes


# 4-bar acid phrase (16 beats). Original 303-style line with octave jumps,
# G natural chromatic tension, and a tail slide back to root.
ACID_PHRASE = [
    # Bar 1
    (0.0,  61, 0.25, 105), (0.25, 61, 0.25,  70),
    (0.5,  73, 0.25, 115), (0.75, 64, 0.25,  85),
    (1.0,  68, 0.25,  95), (1.25, 68, 0.25,  70),
    (1.5,  71, 0.25, 100), (1.75, 73, 0.25, 110),
    (2.0,  61, 0.5,  105), (2.5,  64, 0.25,  85),
    (2.75, 66, 0.25,  90), (3.0,  67, 0.25,  95),   # G nat chromatic
    (3.25, 68, 0.25, 100), (3.5,  73, 0.5,  115),
    # Bar 2
    (4.0,  71, 0.25, 102), (4.25, 69, 0.25,  90),
    (4.5,  68, 0.25,  95), (4.75, 66, 0.25,  88),
    (5.0,  64, 0.25,  92), (5.25, 62, 0.25,  85),
    (5.5,  61, 0.5,  102), (6.0,  73, 0.25, 115),
    (6.25, 71, 0.25,  92), (6.5,  68, 0.25,  95),
    (6.75, 69, 0.25,  88), (7.0,  68, 0.5,   98),
    (7.5,  66, 0.5,   88),
    # Bar 3
    (8.0,  64, 0.5,  102), (8.5,  61, 0.25,  90),
    (8.75, 62, 0.25,  85), (9.0,  64, 0.25,  95),
    (9.25, 66, 0.25,  95), (9.5,  67, 0.25,  98),   # G nat
    (9.75, 68, 0.25, 105), (10.0, 73, 0.5,  118),
    (10.5, 71, 0.25,  95), (10.75, 69, 0.25, 90),
    (11.0, 68, 0.25,  95), (11.25, 66, 0.25, 85),
    (11.5, 64, 0.5,   95),
    # Bar 4
    (12.0, 61, 0.25, 110), (12.25, 49, 0.25, 85),   # octave drop
    (12.5, 61, 0.25,  90), (12.75, 73, 0.25, 115),  # octave up
    (13.0, 68, 0.25, 100), (13.25, 69, 0.25, 88),
    (13.5, 68, 0.25,  95), (13.75, 66, 0.25, 85),
    (14.0, 64, 0.25,  90), (14.25, 62, 0.25, 85),
    (14.5, 61, 1.5,  105),                          # tail slide
]


def _acid(section: str, length: int) -> list[Note]:
    """303-style acid sequence. Featured solo in Break (full volume).
    Textural layer in Drop 2 / Final Drop (velocity x 0.75 to sit under
    the leads). Final Drop bars 1-4 up-shift."""
    notes: list[Note] = []
    vel_scale = 1.0 if section == "Break" else 0.75
    for phrase_start in range(0, length, 16):
        for (dt, pitch, dur, vel) in ACID_PHRASE:
            t = phrase_start + dt
            if t >= length:
                continue
            new_pitch = pitch
            if section == "Final Drop" and t < 16:
                new_pitch += 1
            notes.append((t, new_pitch, min(dur, length - t), int(vel * vel_scale)))
    return notes


NOTE_GENERATORS["18 SYN Lead A"]    = _lead_a
NOTE_GENERATORS["19 SYN Lead B"]    = _lead_b
NOTE_GENERATORS["20 SYN Arp Poly"]  = _arp_poly
NOTE_GENERATORS["21 SYN Acid"]      = _acid


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
    """Re-indent a multiline tab-indented block so its first non-empty line
    sits at `target_indent`, preserving relative depth of remaining lines."""
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
    """Add `offset` to every Id/Value/Pointee Id integer >= `min_val` in
    `block`, but SKIP content inside `<PluginDesc>...</PluginDesc>` — those
    Value= attributes are plugin-internal binary state (Serum 2 preset data,
    VST chunks) and shifting them would corrupt the loaded plugin.
    """
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
        out.append(block[s:e])  # PluginDesc interior left untouched
        cursor = e
    out.append(_shift_chunk(block[cursor:]))
    return "".join(out)


def build_locators_block(indent: str = "\t\t") -> str:
    """Build the <Locators> XML block populated with named section markers."""
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
    """Rename a cloned MidiTrack and set its outer Id + Color to unique values."""
    track_xml = re.sub(
        r'<MidiTrack Id="\d+"', f'<MidiTrack Id="{new_track_id}"', track_xml, count=1,
    )
    track_xml = re.sub(
        r'<EffectiveName Value="[^"]*"', f'<EffectiveName Value="{name}"', track_xml, count=1,
    )
    track_xml = re.sub(
        r'<Color Value="\d+"', f'<Color Value="{color}"', track_xml, count=1,
    )
    return track_xml


def set_plugin_username(track_xml: str, preset_hint: str) -> str:
    """Set the `<UserName>` of the first PluginDevice in the track to the
    preset hint so Live's device header tells the user which patch to load.

    The first UserName inside a PluginDevice lives BEFORE the <PluginDesc>
    block (it's the host-level name), so we can touch it safely.
    """
    m = re.search(r'<PluginDevice\s+Id="\d+"[^>]*>', track_xml)
    if not m:
        return track_xml
    pd_end = track_xml.find('</PluginDevice>', m.end())
    un_match = re.search(r'<UserName Value="[^"]*" />', track_xml[m.end():pd_end])
    if not un_match:
        return track_xml
    un_start = m.end() + un_match.start()
    un_stop = m.end() + un_match.end()
    safe = (preset_hint
            .replace('&', '&amp;')
            .replace('"', '&quot;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))
    return track_xml[:un_start] + f'<UserName Value="{safe}" />' + track_xml[un_stop:]


def inject_clips(track_xml: str, clips: list[str], track_idx: int) -> str:
    """Replace the empty `<ArrangerAutomation><Events />` self-closing with a
    populated `<Events>...</Events>` block containing the given MIDI clips."""
    m = re.search(r'(<ArrangerAutomation>\s*)<Events />', track_xml)
    if not m:
        raise RuntimeError(f"Track #{track_idx}: no <Events /> in ArrangerAutomation")
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


def notes_to_keytracks_xml(notes: list[Note], indent: str) -> tuple[str, int]:
    """Group notes by pitch into <KeyTrack> elements and return
    (keytracks_xml, next_note_id). `next_note_id` feeds the clip's
    <NoteIdGenerator><NextId>."""
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
    """Build an arrangement MidiClip XML block. Pass `notes` to prefill the
    clip's <KeyTracks>; omit (or pass []) for an empty clip."""
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

    # 1) Tempo 120 -> 118
    m_tempo = re.search(r'(<Tempo>.*?<Manual Value=")(\d+)(")', xml, re.DOTALL)
    assert m_tempo, "Tempo block not found"
    xml = xml[: m_tempo.start(2)] + str(TEMPO) + xml[m_tempo.end(2):]
    print(f"  Tempo: {TEMPO} BPM")

    # 2) Locators: replace the empty placeholder with named section markers
    loc_pat = re.compile(r'([ \t]*)<Locators>\s*<Locators />\s*</Locators>', re.DOTALL)
    m_loc = loc_pat.search(xml)
    assert m_loc, "Empty <Locators> block not found"
    indent = m_loc.group(1)
    xml = xml[: m_loc.start()] + build_locators_block(indent) + xml[m_loc.end():]
    print(f"  Locators: {len(SECTIONS)} sections")

    # 3) Identify MidiTrack 12 (the one with Serum 2) as our clone template.
    #    Splice range: from MidiTrack 12 start -> ReturnTrack 2 start.
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

    # 4) Clone 28 tracks
    ID_OFFSET_BASE = 84170          # shifts big IDs from [15830..22155] into [100000..]
    ID_OFFSET_STEP = 10000
    SECTION_BY_NAME = {name: (start, length) for name, start, length in SECTIONS}
    new_tracks: list[str] = []

    for i, (name, color, preset_hint, active_sections) in enumerate(TRACKS):
        clone = template_track
        offset = ID_OFFSET_BASE + i * ID_OFFSET_STEP
        clone = shift_big_ids(clone, offset, min_val=4000)
        clone = rename_track(clone, name, color, new_track_id=200 + i)
        clone = set_plugin_username(clone, preset_hint)

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
        print(f"  #{i+1:2d} {name:<20} clips={len(clips):2d} notes={note_total:4d}  → {preset_hint}")

    # 5) Splice the new tracks in place of the 4 template tracks
    xml = xml[:t12_pos] + "".join(new_tracks) + xml[r2_pos:]

    # 6) Bump NextPointeeId safely above everything we allocated
    max_used = ID_OFFSET_BASE + len(TRACKS) * ID_OFFSET_STEP + 22155 + 1
    xml = re.sub(
        r'(<NextPointeeId Value=")(\d+)(")',
        lambda m: m.group(1) + str(max_used + 100000) + m.group(3),
        xml, count=1,
    )

    # 7) Validate
    try:
        ET.fromstring(xml)
    except ET.ParseError as e:
        raise SystemExit(f"Generated XML is invalid: {e}")
    print(f"  XML parses OK ({len(xml):,} chars)")

    # 8) Write (single-layer gzip)
    DST.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(DST, "wb", compresslevel=9) as f:
        f.write(xml.encode("utf-8"))

    # 9) Sanity check: first bytes must be <?xml (not double-gzipped)
    with gzip.open(DST, "rb") as f:
        head = f.read(80)
    assert head.startswith(b"<?xml"), "Double gzip detected"
    size = DST.stat().st_size
    print(f"Wrote: {DST}  ({size:,} bytes)")


if __name__ == "__main__":
    main()
