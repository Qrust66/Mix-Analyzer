"""Build `Nemesis.als` — aggressive industrial arrangement scaffold.

Brief: drop-C# djent / industrial. Simplicity woven with complexity, rhythmic
AND melodic surprises. 28 tracks across drums / perc / bass / synth / voice /
fx. Asymmetric section lengths (12-bar verse, 6-bar pre-drop, 2-bar silence,
20-bar final drop) to destabilize expectation. C# Phrygian primary, Dorian on
Bridge, half-step pitch-up on first 4 bars of Final Drop.

STEP 1/12 — constants + stubs only (no helpers, no main, no notes yet).
"""

from __future__ import annotations

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


# STEP 2/12 will add: helpers (reindent, shift_big_ids PluginDesc-safe,
# build_locators_block, rename_track, set_plugin_username, inject_clips,
# notes_to_keytracks_xml, midi_clip).
#
# STEP 3/12 will add: main() + execution + validation.
