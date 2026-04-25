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

STEP A1/9 — constants + stubs only. No helpers, no main, no notes yet.
"""

from __future__ import annotations

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


# STEP A2/9 will add: ALS helpers + main() + 1st execution producing
# Venin.als with empty clips (15 tracks + cloned Serum 2 per track with
# preset hints in UserName).
