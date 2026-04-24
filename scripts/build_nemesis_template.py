"""Build `Nemesis.als` — aggressive industrial arrangement scaffold.

Brief: drop-C# djent / industrial. Simplicity woven with complexity, rhythmic
AND melodic surprises. 28 tracks across drums / perc / bass / synth / voice /
fx. Asymmetric section lengths (12-bar verse, 6-bar pre-drop, 2-bar silence,
20-bar final drop) to destabilize expectation. C# Phrygian primary, Dorian on
Bridge, half-step pitch-up on first 4 bars of Final Drop.

STEPS 1-6/12 — core drums + texture drums + percussion (Metal/Glitch/Triplet).
The Triplet track introduces an 8th-note triplet polyrhythm (12 notes/bar
over the 4/4 grid) — the 'complexity' layer that enters in Verse 2 and
peaks as 16th-triplets during Final Drop bars 1-4.
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


NOTE_GENERATORS: dict[str, "callable"] = {name: _noop for (name, *_) in TRACKS}
NOTE_GENERATORS["01 DRM Kick"]     = _kick
NOTE_GENERATORS["02 DRM Sub Kick"] = _sub_kick
NOTE_GENERATORS["03 DRM Snare"]    = _snare
NOTE_GENERATORS["04 DRM Clap"]     = _clap
NOTE_GENERATORS["05 DRM Rim"]      = _rim
NOTE_GENERATORS["06 DRM Hats"]     = _hats
NOTE_GENERATORS["07 DRM Open Hat"] = _open_hat
NOTE_GENERATORS["08 DRM Ride"]     = _ride
NOTE_GENERATORS["09 PRC Metal"]    = _metal
NOTE_GENERATORS["10 PRC Glitch"]   = _glitch
NOTE_GENERATORS["11 PRC Triplet"]  = _triplet


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
