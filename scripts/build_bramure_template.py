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

STEP A1/9 — constants + stubs only. No helpers, no main, no notes yet.
"""

from __future__ import annotations

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


# STEP A2/9 will add: ALS helpers (reindent, shift_big_ids PluginDesc-safe,
# build_locators_block, rename_track, set_plugin_username, inject_clips,
# notes_to_keytracks_xml, midi_clip with TIME SIGNATURE per section), then
# main() + execution + validation.
#
# STEP A3/9 will reinforce per-section time signatures (fallback to local-
# clip metre if project-level injection proves unsafe).
