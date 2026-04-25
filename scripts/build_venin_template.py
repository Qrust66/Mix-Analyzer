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

STEPS A1-C2/9 — Phase B done + automations. Volume sweeps on FX Riser
(Bridge ramp 0->1 then sustain through Final Drop), FX Tension (multi-
section crescendo Intro/Hollow/Bridge then Outro fade), SYN Drone Dark
(Bridge crescendo echoing the Riser, Outro fade). Pan oscillation on
VOX Lead during Bridge (growing amplitude — spatial tension).
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


# Section intensity (0=ambient/void, 2=verse, 3=tension build, 4=drop)
INTENSITY = {
    "Intro": 0, "Outro": 0, "Hollow": 0,
    "Verse 1": 2, "Verse 2": 2,
    "Bridge": 3,
    "Drop 1": 4, "Drop 2": 4, "Final Drop": 4,
}


def cluster_beats(section: str) -> list[float]:
    """Per-bar list of beats where the cluster-stab tracks hit together."""
    if section == "Drop 1":
        return [0.0, 0.25, 2.5, 3.75]
    if section == "Drop 2":
        return [0.0, 0.25, 1.75, 2.5, 3.75]
    if section == "Final Drop":
        return [0.0, 0.25, 1.0, 1.25, 2.5, 2.75, 3.5, 3.75]
    return []


# --- Drums (B1) -----------------------------------------------------------

def _kick(section: str, length: int) -> list[Note]:
    """Slow, weighty kick. Verses are SPARSE (every bar beat 1, push a-of-4
    every other bar — slow burn). Drops use cluster_beats verbatim — the
    kick LOCKS with snare/perc-metal/bass-lead on the same syncopated 16ths.
    Pitch: 36 (drum-rack convention)."""
    notes: list[Note] = []
    bars = length // 4
    cluster = cluster_beats(section)
    if cluster:
        # Drop sections: cluster stabs only — silence elsewhere
        for bar in range(bars):
            t = bar * 4
            for c in cluster:
                vel = 122 if c in (0.0, 2.5) else 110  # accent on 1 and 3
                notes.append((t + c, 36, 0.25, vel))
        return notes
    if section in ("Verse 1", "Verse 2"):
        for bar in range(bars):
            t = bar * 4
            notes.append((t, 36, 0.25, 115))             # downbeat always
            if bar % 2 == 1:
                notes.append((t + 3.75, 36, 0.125, 95))  # push every other bar
        if section == "Verse 2":
            # Audacity push: bar 4 of each phrase adds beat-3 articulation
            for bar in range(3, bars, 4):
                notes.append((bar * 4 + 2, 36, 0.125, 100))
    return notes


def _snare(section: str, length: int) -> list[Note]:
    """Discipline: backbeat 2 & 4 in Verses, NO fills (elegance).
    Drops use cluster_beats — the snare hits the same syncopated grid as
    kick/perc-metal. Bridge is HALF-TIME (snare on beat 3 only) for slow
    burn. Pitch: 38."""
    notes: list[Note] = []
    bars = length // 4
    cluster = cluster_beats(section)
    if cluster:
        for bar in range(bars):
            t = bar * 4
            for c in cluster:
                vel = 118 if c in (0.0, 2.5) else 100
                notes.append((t + c, 38, 0.25, vel))
        return notes
    if section in ("Verse 1", "Verse 2"):
        for bar in range(bars):
            t = bar * 4
            notes += [(t + 1, 38, 0.25, 110), (t + 3, 38, 0.25, 115)]
            if section == "Verse 2" and (bar + 1) % 4 == 0:
                # Audacity: ONE ghost anticipation on bar 4 of phrase
                notes.append((t + 2.75, 38, 0.0625, 60))
    elif section == "Bridge":
        # Half-time: snare only on beat 3 of each bar (slow burn)
        for bar in range(bars):
            notes.append((bar * 4 + 2, 38, 0.5, 100))
    return notes


def _tom_high(section: str, length: int) -> list[Note]:
    """Tribal high tom — sparse, eerie. AUDACITY: Hollow has ONE single hit
    at bar 2 beat 1.5 — pure restraint, lets the void breathe. Pitch 50."""
    notes: list[Note] = []
    bars = length // 4
    if section == "Intro":
        # 4 hits across 8 bars (sparse, isolated, snake-charmer call)
        notes += [(0.0,  50, 1.0,  95),
                  (10.0, 50, 1.0, 100),
                  (20.0, 50, 1.0, 105),
                  (24.0, 50, 1.0,  95)]
    elif section == "Hollow":
        notes.append((6.0, 50, 2.0, 100))   # ONE hit (audacity = restraint)
    elif section == "Bridge":
        # Ascending tribal — density grows toward Final Drop
        for bar in range(bars):
            t = bar * 4
            if bar < 2:
                notes.append((t, 50, 0.5, 95))
            elif bar < 4:
                notes += [(t, 50, 0.25, 100), (t + 2.5, 50, 0.25, 105)]
            elif bar < 6:
                notes += [(t, 50, 0.25, 105),
                          (t + 1, 50, 0.25, 100),
                          (t + 2, 50, 0.25, 105)]
            else:
                # Last 2 bars: 8th-note roll into Final Drop
                for s in range(8):
                    notes.append((t + s * 0.5, 50, 0.2, 90 + s * 4))
    elif section == "Final Drop":
        # Tribal machine-gun pattern every 2 bars + extended fill every 4
        for bar in range(0, bars, 2):
            t = bar * 4
            notes += [(t,       50, 0.25, 110),
                      (t + 0.5, 50, 0.25, 100),
                      (t + 1,   50, 0.25, 105)]
            if bar % 4 == 0:
                notes += [(t + 3,   50, 0.5,  115),
                          (t + 3.5, 50, 0.25, 100)]
    return notes


def _tom_low(section: str, length: int) -> list[Note]:
    """Tribal low tom — anchor for the high tom's call. Single hit per
    2-bar phrase in Intro, one hit per 4-bar phrase in Verse 1 (rare
    punctuation), more frequent in Verse 2, big hits in Final Drop.
    Pitch 47."""
    notes: list[Note] = []
    bars = length // 4
    if section == "Intro":
        for bar in (1, 3, 5, 7):
            notes.append((bar * 4, 47, 1.0, 105))
    elif section == "Verse 1":
        for bar in range(3, bars, 4):
            notes.append((bar * 4 + 3, 47, 0.5, 110))   # tribal punctuation
    elif section == "Verse 2":
        for bar in range(1, bars, 2):
            notes.append((bar * 4 + 3, 47, 0.5, 108))
    elif section == "Bridge":
        # Counter to Tom High — fills the gaps between its calls
        for bar in range(bars):
            t = bar * 4
            if bar % 2 == 0:
                notes.append((t + 1.5, 47, 0.5, 95))
            else:
                notes.append((t + 3, 47, 0.5, 100))
    elif section == "Final Drop":
        for bar in range(bars):
            t = bar * 4
            notes.append((t, 47, 0.5, 115))
            if bar % 2 == 1:
                notes.append((t + 2, 47, 0.5, 110))
    return notes


def _hats(section: str, length: int) -> list[Note]:
    """Steady 8th-note hats with VARIED velocity (no 16ths — let drops breathe).
    Active only in Verses + Final Drop. AUDACITY: Drops have NO hats at all
    so the cluster stabs sit naked. Pitch 42."""
    notes: list[Note] = []
    bars = length // 4
    if section in ("Verse 1", "Verse 2", "Final Drop"):
        for bar in range(bars):
            t = bar * 4
            for s in range(8):
                if s % 4 == 0:
                    vel = 90    # downbeat 1, 3
                elif s % 2 == 0:
                    vel = 70    # 2, 4
                else:
                    vel = 55    # offbeat &
                notes.append((t + s * 0.5, 42, 0.25, vel))
    return notes


def _prc_metal(section: str, length: int) -> list[Note]:
    """Industrial metal hit — the cluster-stab voice. Silent everywhere
    except Drops. Pitch 56."""
    notes: list[Note] = []
    bars = length // 4
    cluster = cluster_beats(section)
    if not cluster:
        return notes
    for bar in range(bars):
        t = bar * 4
        for c in cluster:
            vel = 110 if c in (0.0, 2.5) else 95
            notes.append((t + c, 56, 0.125, vel))
    return notes


NOTE_GENERATORS: dict[str, "callable"] = {name: _noop for (name, *_) in TRACKS}
NOTE_GENERATORS["01 DRM Kick"]      = _kick
NOTE_GENERATORS["02 DRM Snare"]     = _snare
NOTE_GENERATORS["03 DRM Tom High"]  = _tom_high
NOTE_GENERATORS["04 DRM Tom Low"]   = _tom_low
NOTE_GENERATORS["05 DRM Hats"]      = _hats
NOTE_GENERATORS["06 PRC Metal"]     = _prc_metal


# --- Basses + Pad + Drone + Tension (B2) ----------------------------------
#
# C# Phrygian Dominant pitch reference:
#   C#1=25  D1=26  F1=29  F#1=30  G#1=32  A1=33  B1=35
#   C#2=37  D2=38  F2=41  F#2=42  G#2=44  A2=45  B2=47
#   C#3=49  D3=50  F3=53  F#3=54  G#3=56  A3=57
#   The maj-3 (F nat) is the venomous snake-charmer note (creates aug-2
#   from D b2). Pad avoids committing it; Bass Lead delivers it.

def _bas_sub(section: str, length: int) -> list[Note]:
    """Sub foundation. Verses: C#1 held long, pivots to D1 (b2) on the
    LAST 2 BARS to ANNOUNCE the Drop. Drops: cluster sync — sub locks with
    kick on identical beats. Bridge: D1 held entire section (announces
    fire). Final Drop: alternates C#1 / D1 every 4 bars (venomous oscill.)."""
    notes: list[Note] = []
    bars = length // 4
    cluster = cluster_beats(section)

    if section == "Verse 1":
        # 16 bars: C#1 held 14 bars, D1 last 2 (drop announce)
        notes += [(0.0,  25, 56.0, 105),
                  (56.0, 26, 8.0,  110)]
    elif section == "Verse 2":
        # Mid-section push to D1 + final 2-bar D1 announce
        notes += [(0.0,  25, 28.0, 105),
                  (28.0, 26, 4.0,  100),
                  (32.0, 25, 24.0, 105),
                  (56.0, 26, 8.0,  110)]
    elif section == "Bridge":
        # D1 held entire 8-bar section (the b2 carries the fire announce)
        notes.append((0.0, 26, float(length), 110))
    elif cluster:
        for bar in range(bars):
            t = bar * 4
            base_pitch = 25
            if section == "Final Drop" and (bar // 4) % 2 == 1:
                base_pitch = 26   # alternate root / b2 every 4 bars
            for c in cluster:
                vel = 122 if c in (0.0, 2.5) else 105
                notes.append((t + c, base_pitch, 0.25, vel))
    return notes


def _bas_lead(section: str, length: int) -> list[Note]:
    """Distorted bass lead — the maj-3 voice (F nat = snake-charmer venom).
    Verse 2: held F2 with a half-step F#2 push every 4 bars. Bridge: chromatic
    climb C#2 -> D2 -> D#2 -> F2 (skips E, snake jump). Drops: cluster sync at
    C#2. Final Drop: octave jumps to C#3 on bar-4 of each phrase for accent."""
    notes: list[Note] = []
    bars = length // 4
    cluster = cluster_beats(section)

    if section == "Verse 2":
        # 16 bars: 4 phrases of [F2 hold 3 bars + F#2 push 1 bar]
        for phrase in range(bars // 4):
            t = phrase * 16
            notes += [(t + 0.0,  41, 12.0, 100),    # F2  hold 3 bars
                      (t + 12.0, 42, 4.0,  105)]    # F#2 push 1 bar
    elif section == "Bridge":
        # Chromatic ascending climb (audacity: SKIPS E, jumps D# -> F)
        notes += [(0.0,  37, 8.0,  100),    # C#2 bars 1-2
                  (8.0,  38, 8.0,  105),    # D2  bars 3-4
                  (16.0, 39, 8.0,  110),    # D#2 bars 5-6 (chromatic OUT-of-scale)
                  (24.0, 41, 8.0,  115)]    # F2  bars 7-8 (skip E, snake jump)
    elif cluster:
        for bar in range(bars):
            t = bar * 4
            base = 37    # C#2 default
            # Final Drop: bar-4 of every 4-bar phrase = octave up to C#3
            if section == "Final Drop" and (bar % 4) == 3:
                base = 49
            for c in cluster:
                vel = 118 if c in (0.0, 2.5) else 100
                notes.append((t + c, base, 0.25, vel))
    return notes


# Pad voicings: sus4 avoids committing to maj/min; venom voicing pushes
# the b2 + maj-3 + 4 cluster (D-F-A) for max dissonance against C# root.
PAD_SUS4  = [49, 54, 56]    # C#3 F#3 G#3
PAD_VENOM = [50, 53, 57]    # D3  F3  A3  -> b2 / maj3 / 4 — the push

def _pad(section: str, length: int) -> list[Note]:
    """Sparse pad. Hold C# sus4 for full Intro / Verse 1 / Outro. Verse 2
    pushes the LAST 4 BARS to D-F-A (b2 + maj3 + 4 cluster) for venom."""
    notes: list[Note] = []
    if section in ("Intro", "Verse 1", "Outro"):
        for pitch in PAD_SUS4:
            notes.append((0.0, pitch, float(length), 60))
    elif section == "Verse 2":
        # 12 bars sus4 + 4 bars venom push
        for pitch in PAD_SUS4:
            notes.append((0.0, pitch, 48.0, 60))
        for pitch in PAD_VENOM:
            notes.append((48.0, pitch, 16.0, 72))
    return notes


def _drone_dark(section: str, length: int) -> list[Note]:
    """Single long sustained note per section. AUDACITY: Bridge shifts
    E1 -> F1 mid-section (aug-2 chromatic step OUT of scale that announces
    the fire). Outro fades on D1 (b2 unresolved — sting in the tail)."""
    if section == "Intro":
        return [(0.0, 28, float(length), 65)]                  # E1 ambiguous tension
    if section == "Hollow":
        return [(0.0, 25, float(length), 70)]                  # C#1 root drone (void)
    if section == "Bridge":
        half = length / 2
        return [(0.0,  28, half, 70),                          # E1 first half
                (half, 29, half, 80)]                          # F1 second half (aug-2)
    if section == "Outro":
        return [(0.0, 26, float(length), 60)]                  # D1 b2 unresolved
    return []


def _fx_tension(section: str, length: int) -> list[Note]:
    """Single held note per section — the synth patch / automation creates
    the noise-bed timbre, MIDI just provides a constant trigger."""
    return [(0.0, 60, float(length), 75)]


NOTE_GENERATORS["07 BAS Sub"]       = _bas_sub
NOTE_GENERATORS["08 BAS Lead"]      = _bas_lead
NOTE_GENERATORS["09 SYN Pad"]       = _pad
NOTE_GENERATORS["10 SYN Drone Dark"] = _drone_dark
NOTE_GENERATORS["15 FX Tension"]    = _fx_tension


# --- Leads + Voice + FX (B3) ----------------------------------------------
#
# Lead pitch reference (mid-high register, C4=60 convention):
#   C#4=61  D4=62  E4=64  F4=65  F#4=66  G#4=68  A4=69  B4=71
#   C#5=73  D5=74  E5=76  F5=77  F#5=78  G#5=80  A5=81  C#6=85
# F nat in lead register = the maj-3 = snake-charmer venom note.

def _syn_lead(section: str, length: int) -> list[Note]:
    """Sparse lead. Verse 2: held F4 (the venom maj-3) with one chromatic
    descent to E4 mid-section. Bridge: 4-note motif [low-high-low-high]
    that half-steps UP each iteration — AUDACITY: climbs OUT of scale via
    D# in iter 3 (C# Phrygian Dom doesn't have D#). Drops: cluster sync at
    C#5 alternating with F5 (root-vs-maj3 venom oscillation)."""
    notes: list[Note] = []
    bars = length // 4
    cluster = cluster_beats(section)

    if section == "Verse 2":
        # 16 bars: F4 (32) -> E4 (16) -> F4 (16). Three long notes total.
        notes += [(0.0,  65, 32.0, 100),    # F4 held 8 bars
                  (32.0, 64, 16.0, 95),     # E4 chromatic descent 4 bars
                  (48.0, 65, 16.0, 100)]    # F4 return 4 bars
    elif section == "Bridge":
        # 8 bars = 4 iterations of 2-bar motif. Climbs half-step each iter.
        # Iteration N: [low, high, low, high] held 2 beats each.
        # iter 1: C#4 / F4   (root + maj-3)
        # iter 2: D4  / F4   (b2 + maj-3)
        # iter 3: D#4 / F#4  (OUT-OF-SCALE chromatic push)
        # iter 4: F4  / G#4  (maj-3 + 5 — peak before fire)
        iters = [(61, 65), (62, 65), (63, 66), (65, 68)]
        for i, (lo, hi) in enumerate(iters):
            t = i * 8
            notes += [(t + 0.0, lo, 2.0, 100),
                      (t + 2.0, hi, 2.0, 105),
                      (t + 4.0, lo, 2.0, 100),
                      (t + 6.0, hi, 2.0, 110)]   # rising velocity per iter end
    elif section == "Drop 2" and cluster:
        # 12 bars: 4-bar phrases alternating C#5 / F5
        for bar in range(bars):
            t = bar * 4
            base = 73 if (bar // 4) % 2 == 0 else 77      # C#5 / F5
            for c in cluster:
                vel = 115 if c in (0.0, 2.5) else 100
                notes.append((t + c, base, 0.25, vel))
    elif section == "Final Drop" and cluster:
        # 20 bars: cluster sync at C#5; bar-4 of each phrase = octave up C#6
        for bar in range(bars):
            t = bar * 4
            phrase_pos = bar % 4
            if phrase_pos == 3:
                base = 85    # C#6 — accent octave-up
            elif (bar // 4) % 2 == 1:
                base = 77    # F5 — venom on alternate phrases
            else:
                base = 73    # C#5
            for c in cluster:
                vel = 118 if c in (0.0, 2.5) else 102
                notes.append((t + c, base, 0.25, vel))
    return notes


def _vox_lead(section: str, length: int) -> list[Note]:
    """Sustained vocal voice. Verse 2: held A4 (the 6, planante) -> G#4
    (5) at end. Bridge: slow crescendo half-step climb F4 -> F#4 -> G#4 ->
    B4 -> D5 (peak). AUDACITY: skips A and C, jumps straight from G# to B
    then B to D — anticipates the fire. Final Drop: held wail alternating
    C#5 / D5 every 4 bars."""
    notes: list[Note] = []

    if section == "Verse 2":
        # 16 bars: A4 hold 12, G#4 hold 4
        notes += [(0.0,  69, 48.0, 95),
                  (48.0, 68, 16.0, 100)]
    elif section == "Bridge":
        # 8-bar climb: 2+2+2+1+1 bars
        notes += [(0.0,  65, 8.0,  90),     # F4 bars 1-2
                  (8.0,  66, 8.0,  95),     # F#4 bars 3-4
                  (16.0, 68, 8.0, 100),     # G#4 bars 5-6 (skip G — in-scale)
                  (24.0, 71, 4.0, 110),     # B4 bar 7 (skip A, audacity)
                  (28.0, 74, 4.0, 118)]     # D5 bar 8 (skip C, peak)
    elif section == "Final Drop":
        # 20 bars: alternate C#5 / D5 every 4 bars
        bars = length // 4
        for phrase in range(bars // 4 + (1 if bars % 4 else 0)):
            t = phrase * 16
            if t >= length:
                break
            pitch = 73 if phrase % 2 == 0 else 74
            dur = min(16.0, length - t)
            notes.append((t, pitch, dur, 105))
    elif section == "Outro":
        # F4 held entire section — maj-3 lingering fade
        notes.append((0.0, 65, float(length), 80))
    return notes


def _fx_riser(section: str, length: int) -> list[Note]:
    """Single sustained note covering the whole section — synth patch /
    Volume automation in C2 makes the actual riser timbre."""
    return [(0.0, 60, float(length), 90)]


def _fx_impact(section: str, length: int) -> list[Note]:
    """Transition impact hits. Drop 1 / Drop 2 enter with a single punch.
    AUDACITY: Final Drop opens with THREE CLOSE HITS (beats 0, 1, 2 of
    bar 1) — a triple-trigger ignition that mirrors the cluster density
    of the section. Then sparse marker hits every 4 bars."""
    notes: list[Note] = []
    bars = length // 4
    if section == "Drop 1":
        notes.append((0.0, 60, 1.0, 120))
    elif section == "Drop 2":
        notes += [(0.0, 60, 1.0, 120),
                  (16.0, 60, 1.0, 115)]
    elif section == "Final Drop":
        # Triple-hit ignition (beats 0, 1, 2 of bar 1)
        notes += [(0.0, 60, 0.75, 124),
                  (1.0, 60, 0.75, 122),
                  (2.0, 60, 0.75, 120)]
        # Sparse markers at bar 5, 9, 17
        for bar in (4, 8, 16):
            if bar < bars:
                notes.append((bar * 4, 60, 1.0, 115))
    return notes


NOTE_GENERATORS["11 SYN Lead"]      = _syn_lead
NOTE_GENERATORS["12 VOX Lead"]      = _vox_lead
NOTE_GENERATORS["13 FX Riser"]      = _fx_riser
NOTE_GENERATORS["14 FX Impact"]     = _fx_impact


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


# --- EQ8 injection helpers (A3) -------------------------------------------

EQ8_REFERENCE_PATH = ROOT / "tests" / "fixtures" / "reference_project.als"
_EQ8_TEMPLATE_CACHE: str | None = None


def load_eq8_template() -> str:
    """Read a clean EQ8 device XML from reference_project.als (cached)."""
    global _EQ8_TEMPLATE_CACHE
    if _EQ8_TEMPLATE_CACHE is not None:
        return _EQ8_TEMPLATE_CACHE
    with gzip.open(EQ8_REFERENCE_PATH, "rb") as f:
        ref = f.read().decode("utf-8")
    m = re.search(r'<Eq8 Id="\d+">.*?</Eq8>', ref, re.DOTALL)
    if not m:
        raise RuntimeError(f"No <Eq8> in {EQ8_REFERENCE_PATH}")
    _EQ8_TEMPLATE_CACHE = m.group(0)
    return _EQ8_TEMPLATE_CACHE


def clone_eq8(eq8_xml: str, eq8_id_offset: int, new_device_id: int) -> str:
    """Shift Id="N" (N>=1000) by eq8_id_offset; set outer <Eq8 Id> to
    new_device_id. Value="N" is NOT shifted (parameter values like Manual
    Freq=84.3 must not change)."""
    def sub(m: re.Match) -> str:
        n = int(m.group(1))
        return f'Id="{n + eq8_id_offset}"' if n >= 1000 else m.group(0)
    out = re.sub(r'Id="(\d+)"', sub, eq8_xml)
    out = re.sub(r'<Eq8 Id="\d+"', f'<Eq8 Id="{new_device_id}"', out, count=1)
    return out


def set_eq8_username(eq8_xml: str, name: str) -> str:
    """Set the EQ8 device-level UserName (first UserName tag inside <Eq8>)."""
    safe = (name.replace('&', '&amp;').replace('"', '&quot;')
                .replace('<', '&lt;').replace('>', '&gt;'))
    return re.sub(r'<UserName Value="[^"]*" />',
                  f'<UserName Value="{safe}" />', eq8_xml, count=1)


def set_eq8_band(eq8_xml: str, band_idx: int, *,
                 mode: int | None = None, freq: float | None = None,
                 gain: float | None = None, q: float | None = None,
                 on: bool | None = None) -> str:
    """Set parameters on one EQ8 band by replacing the Manual Value of the
    target params inside <Bands.{band_idx}>. Modes: 0=LC48 1=LC12 2=LowShelf
    3=Bell 4=Notch 5=HighShelf 6=HC12 7=HC48."""
    band_pat = re.compile(rf'(<Bands\.{band_idx}>.*?</Bands\.{band_idx}>)', re.DOTALL)
    bm = band_pat.search(eq8_xml)
    if not bm:
        return eq8_xml
    band = bm.group(1)

    def replace_manual(block: str, param_tag: str, new_value: str) -> str:
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
    """Inject EQ8 into the track's <Devices> chain.

    Handles BOTH forms:
    - <Devices />            (self-closing, after Serum strip — Venin case)
        replaced with <Devices><EQ8/></Devices>
    - <Devices>...</Devices> (populated, e.g. Bramure with Serum present)
        EQ8 inserted before the closing tag

    Patched vs Bramure to support the self-closing case introduced by
    strip_serum() in Venin's pipeline.
    """
    # Self-closing form first
    sc_pat = re.compile(r'([ \t]*)<Devices />')
    m = sc_pat.search(track_xml)
    if m:
        indent = m.group(1)
        inner_indent = indent + '\t'
        reindented = reindent(eq8_xml, inner_indent)
        replacement = (f'{indent}<Devices>\n'
                       f'{reindented}\n'
                       f'{indent}</Devices>')
        return track_xml[:m.start(0)] + replacement + track_xml[m.end(0):]

    # Populated form fallback
    closing = track_xml.find('</Devices>')
    if closing < 0:
        raise RuntimeError("No <Devices> block in track")
    line_start = track_xml.rfind('\n', 0, closing) + 1
    indent = track_xml[line_start:closing]
    inner_indent = indent + '\t'
    reindented = reindent(eq8_xml, inner_indent)
    return track_xml[:closing] + reindented + '\n' + indent + track_xml[closing:]


# Per-track EQ8 band recipes — drums + basses only (8 tracks).
# (band_idx, mode, freq_hz, gain_dB, q, on). Modes: 0=LC48 1=LC12 2=LowShelf
# 3=Bell 4=Notch 5=HighShelf 6=HC12 7=HC48.
EQ8_PRESETS: dict[str, list[tuple]] = {
    "01 DRM Kick": [
        (0, 0, 30,    0,    0.7, True),    # HPF 30 Hz (subharmonic clean)
        (1, 2, 65,    2.5,  0.7, True),    # Low-shelf +2.5 dB at 65 Hz (weight)
        (2, 3, 350,  -3.0,  1.5, True),    # Bell -3 dB at 350 Hz (mud)
        (3, 3, 4000,  1.5,  1.2, True),    # Bell +1.5 dB at 4 kHz (click)
    ],
    "02 DRM Snare": [
        (0, 0, 110,   0,    0.7, True),    # HPF 110 Hz
        (1, 3, 220,   2.0,  1.2, True),    # Body
        (2, 3, 800,  -2.0,  1.5, True),    # Boxiness cut
        (3, 3, 4000,  2.5,  1.4, True),    # Presence
    ],
    "03 DRM Tom High": [
        (0, 0, 90,    0,    0.7, True),
        (1, 3, 250,   1.5,  1.2, True),    # Tone
        (2, 3, 4000,  2.0,  1.3, True),    # Attack
    ],
    "04 DRM Tom Low": [
        (0, 0, 50,    0,    0.7, True),
        (1, 3, 100,   2.0,  1.0, True),    # Boom
        (2, 3, 3000,  1.5,  1.3, True),    # Attack
    ],
    "05 DRM Hats": [
        (0, 0, 350,   0,    0.7, True),    # HPF 350 Hz
        (1, 3, 800,  -2.0,  1.5, True),    # De-harsh
        (2, 5, 8000,  2.0,  0.7, True),    # Air shelf
    ],
    "06 PRC Metal": [
        (0, 0, 250,   0,    0.7, True),    # HPF 250 Hz
        (1, 3, 2000,  2.5,  1.2, True),    # Presence (cluster stab clarity)
        (2, 5, 7000,  1.5,  0.7, True),
    ],
    "07 BAS Sub": [
        (0, 0, 25,    0,    0.7, True),    # HPF 25 Hz
        (1, 2, 55,    2.0,  0.7, True),    # Low-shelf weight
        (2, 3, 280,  -3.0,  1.5, True),    # Mud cut
    ],
    "08 BAS Lead": [
        (0, 0, 50,    0,    0.7, True),
        (1, 3, 700,   3.0,  1.5, True),    # Growl (snake-charmer growl)
        (2, 3, 2000,  2.0,  1.5, True),    # Bite
        (3, 3, 4000,  1.0,  1.2, True),    # Top edge
    ],
}


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


# --- Automation envelope helpers (C2) -------------------------------------
#
# Live volume scale (verified on Acid_Drops reference):
#   Min  0.0003162277571 (~ -inf, silent)
#   1.0  unity (0 dB)
#   Max  1.99526238       (~ +6 dB)
# Pan: -1.0 (left) .. 0.0 (center) .. +1.0 (right)
#
# Init event at Time=-63072000 = pre-song state. Required.

def find_param_target_id(track_xml: str, param: str) -> int | None:
    """Find the Mixer parameter's AutomationTarget Id by name (Volume/Pan)."""
    m = re.search(
        rf'<Mixer>.*?<{param}>.*?<AutomationTarget Id="(\d+)"',
        track_xml, re.DOTALL,
    )
    return int(m.group(1)) if m else None


def build_envelope(env_id: int, target_id: int,
                   events: list[tuple[float, float]],
                   event_id_base: int) -> str:
    """Build one <AutomationEnvelope> block. The init Value is taken from
    events[0][1] — caller must arrange for the first event to set the rest
    state (e.g. unity 1.0) so the parameter sits there before the first
    real change."""
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
    """Replace <AutomationEnvelopes><Envelopes /> with a populated block.
    No-op if the track has no self-closing tag (already populated)."""
    if not envelope_xmls:
        return track_xml
    pat = re.compile(
        r'(<AutomationEnvelopes>\s*)<Envelopes />(\s*</AutomationEnvelopes>)',
        re.DOTALL,
    )
    m = pat.search(track_xml)
    if not m:
        return track_xml
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


# Volume envelope recipes — values use Live's 0.0003-1.99 scale.

def volume_envelope_riser(env_id: int, target_id: int, eid_base: int) -> str:
    """FX Riser: silent rest -> 32-beat ramp across Bridge -> sustain at peak
    through Final Drop. Bridge starts at beat 256, Final Drop at 288, ends
    at 368."""
    events = [
        (0.0,   0.0003),    # rest at song start (silent)
        (255.0, 0.0003),    # rest until just before Bridge
        (256.0, 0.0003),    # Bridge start: silent
        (288.0, 1.0),       # Bridge end / Final Drop start: peak
        (368.0, 1.0),       # Final Drop end: sustain
    ]
    return build_envelope(env_id, target_id, events, eid_base)


def volume_envelope_tension(env_id: int, target_id: int, eid_base: int) -> str:
    """FX Tension: multi-section crescendo across Intro / Hollow / Bridge,
    then fade in Outro. Active sections (per TRACKS): Intro 0..32, Hollow
    128..144, Bridge 256..288, Outro 368..400."""
    events = [
        (0.0,   0.4),       # Intro start: low ambient
        (32.0,  0.5),       # Intro end
        (128.0, 0.5),       # Hollow start
        (144.0, 0.8),       # Hollow end (void rises ominous)
        (256.0, 0.8),       # Bridge start
        (288.0, 1.0),       # Bridge end: peak (just before fire)
        (368.0, 1.0),       # Final Drop end / Outro start
        (400.0, 0.0003),    # Outro end: fade silent
    ]
    return build_envelope(env_id, target_id, events, eid_base)


def volume_envelope_drone_dark(env_id: int, target_id: int, eid_base: int) -> str:
    """SYN Drone Dark: steady through Intro / Hollow, dip + crescendo in
    Bridge (echoes Riser), fade in Outro."""
    events = [
        (0.0,   0.7),       # Intro: audible drone
        (128.0, 0.7),       # Hollow: keep level (the void breathes)
        (256.0, 0.6),       # Bridge start: slight dip
        (288.0, 1.0),       # Bridge end: peak (matches Riser)
        (368.0, 0.7),       # Outro start: drop back
        (400.0, 0.0003),    # Outro end: fade silent
    ]
    return build_envelope(env_id, target_id, events, eid_base)


def pan_envelope_vox_bridge(env_id: int, target_id: int, eid_base: int) -> str:
    """VOX Lead pan oscillation during Bridge (beats 256..288). Two cycles
    with growing amplitude (-0.4 -> 0.4 -> -0.5 -> 0.6 -> 0.0). Snaps back
    to center at Final Drop entry."""
    events = [
        (0.0,   0.0),       # init centered
        (255.0, 0.0),       # hold center until Bridge
        (256.0, -0.4),      # cycle 1 left (soft)
        (264.0,  0.4),      # cycle 1 right
        (272.0, -0.5),      # cycle 2 left (wider)
        (280.0,  0.6),      # cycle 2 right (widest)
        (288.0,  0.0),      # snap center for Final Drop
    ]
    return build_envelope(env_id, target_id, events, eid_base)




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

    eq8_template = load_eq8_template()
    eq8_count = 0

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

        # A3: inject EQ8 on drums + basses (Venin case = self-closing <Devices />)
        eq_marker = ""
        if name in EQ8_PRESETS:
            eq8 = clone_eq8(eq8_template,
                            eq8_id_offset=2_000_000 + i * 100_000,
                            new_device_id=1)
            eq8 = set_eq8_username(eq8, f"EQ / {name.split(' ', 1)[1]}")
            for band_idx, mode, freq, gain, q, on in EQ8_PRESETS[name]:
                eq8 = set_eq8_band(eq8, band_idx, mode=mode, freq=freq,
                                   gain=gain, q=q, on=on)
            clone = inject_eq8(clone, eq8)
            eq8_count += 1
            eq_marker = " + EQ8"

        # C2b: inject volume automation envelopes (3 specific tracks)
        env_marker = ""
        env_xmls: list[str] = []
        eid_base = 9_000_000 + i * 10_000
        if name == "13 FX Riser":
            tid = find_param_target_id(clone, "Volume")
            if tid is not None:
                env_xmls.append(volume_envelope_riser(1, tid, eid_base))
                env_marker += " + Riser-sweep"
        elif name == "15 FX Tension":
            tid = find_param_target_id(clone, "Volume")
            if tid is not None:
                env_xmls.append(volume_envelope_tension(1, tid, eid_base))
                env_marker += " + Tension-cresc"
        elif name == "10 SYN Drone Dark":
            tid = find_param_target_id(clone, "Volume")
            if tid is not None:
                env_xmls.append(volume_envelope_drone_dark(1, tid, eid_base))
                env_marker += " + Drone-cresc"
        elif name == "12 VOX Lead":
            tid = find_param_target_id(clone, "Pan")
            if tid is not None:
                env_xmls.append(pan_envelope_vox_bridge(1, tid, eid_base))
                env_marker += " + Pan-Bridge"
        if env_xmls:
            clone = inject_envelopes(clone, env_xmls)

        new_tracks.append(clone)
        print(f"  #{i+1:2d} {name:<20} clips={len(clips):2d} notes={note_total:4d}{eq_marker}{env_marker}  -> {preset_hint}")
    print(f"  Injected {eq8_count} EQ8 devices")

    xml = xml[:t12_pos] + "".join(new_tracks) + xml[r2_pos:]

    # Bump NextPointeeId well above ALL allocated IDs:
    # - track-level shifts (~250k max)
    # - EQ8 internal Ids (~3.3M max for last track)
    # - future envelope FloatEvent Ids in 9M+ range (C2/C3)
    max_used = max(
        ID_OFFSET_BASE + len(TRACKS) * ID_OFFSET_STEP + 22155 + 1,
        2_000_000 + len(TRACKS) * 100_000 + 1_500_000,   # EQ8 max Id
        9_000_000 + len(TRACKS) * 10_000 + 10_000,        # envelope reserve
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
    print(f"Wrote: {DST}  ({DST.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
