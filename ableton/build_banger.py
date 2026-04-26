"""
Build a "banger" .als from Template.als — composition designed via composition_advisor.json
top-30 + dark_electronic_hybrid_album_centerpiece template.

User blend: Cobain 30 / Reznor 30 / Daft Punk 25 / Yorke 15.
Style applied: mid-tempo aggression (108 BPM), descending bass-riff identity,
hard-soft-hard contrast within song, programmed-drums-as-engine, 6-section form
spanning intro → verse-A → breakdown → verse-B → drop → outro with abrupt end.

Output: ableton/projects/Banger_Cobain30_Reznor30_v1.als
"""
import gzip
import re
import shutil
from pathlib import Path

# ===== Composition constants =====
TEMPO = 108.0
TIME_SIG_NUMERATOR = 4
TIME_SIG_DENOMINATOR = 4

KICK = 36
SNARE = 38
HAT_CL = 42
HAT_OP = 46
SUB_D1 = 26
BASS_D2 = 38
BASS_C2 = 36
BASS_BB1 = 34
BASS_A1 = 33
LEAD_D5 = 74
LEAD_C5 = 72
LEAD_BB4 = 70
LEAD_A4 = 69
PAD_D3 = 50
PAD_F3 = 53
PAD_A3 = 57
PAD_C4 = 60

INTRO_START = 1
VERSE_A_START = 9
BREAKDOWN_START = 25
VERSE_B_START = 31
DROP_START = 47
OUTRO_START = 59
END_BAR = 65   # exclusive

CLIP_END_BEATS = (END_BAR - 1) * 4   # 256 beats


def bar(b):
    """Bar number (1-indexed) to beat position."""
    return (b - 1) * 4


# ===== Note-list builders for each track =====

class NoteBuilder:
    """Accumulate MIDI notes for one clip; assigns NoteIds globally per clip."""
    def __init__(self):
        self.notes = []
        self.next_id = 1

    def add(self, time, duration, velocity, pitch):
        self.notes.append({
            'time': float(time),
            'duration': float(duration),
            'velocity': int(velocity),
            'pitch': int(pitch),
            'noteid': self.next_id,
        })
        self.next_id += 1

    def by_pitch(self):
        """Group notes by pitch for KeyTrack assembly."""
        groups = {}
        for n in self.notes:
            groups.setdefault(n['pitch'], []).append(n)
        for p in groups:
            groups[p].sort(key=lambda n: n['time'])
        return groups


def build_kick():
    nb = NoteBuilder()
    # Intro 5-8 half density (1+3)
    for b in range(5, 9):
        for off in [0, 2]:
            nb.add(bar(b) + off, 0.25, 110, KICK)
    # Verse A 9-24 full 4-on-floor
    for b in range(9, 25):
        for off in range(4):
            nb.add(bar(b) + off, 0.25, 118 if off == 0 else 105, KICK)
    # Breakdown 25-30 — silent
    # Verse B 31-46 full
    for b in range(31, 47):
        for off in range(4):
            nb.add(bar(b) + off, 0.25, 120 if off == 0 else 108, KICK)
    # Drop 47-58 full + ghost-kick on 1.5 every 2 bars
    for b in range(47, 59):
        for off in range(4):
            nb.add(bar(b) + off, 0.25, 124 if off == 0 else 112, KICK)
        if b % 2 == 0:
            nb.add(bar(b) + 1.5, 0.25, 90, KICK)
    # Outro fade out bars 59-60, silent 61-64
    for b in [59, 60]:
        for off in range(4):
            nb.add(bar(b) + off, 0.25, max(60, 100 - off * 8), KICK)
    return nb


def build_sub():
    nb = NoteBuilder()
    # Sustained D1 in bars 5-24, 31-46, 47-58, fade 59-60
    def sustain(start_bar, end_bar, vel):
        for b in range(start_bar, end_bar):
            nb.add(bar(b), 4.0, vel, SUB_D1)
    sustain(5, 9, 90)
    sustain(9, 25, 105)
    # Breakdown: thin sub
    sustain(25, 31, 70)
    sustain(31, 47, 110)
    sustain(47, 59, 118)
    # Outro
    nb.add(bar(59), 4.0, 95, SUB_D1)
    nb.add(bar(60), 4.0, 70, SUB_D1)
    return nb


def build_bass_riff():
    nb = NoteBuilder()
    # Descending pattern within 1 bar: D2 (1 beat) → C2 (1) → Bb1 (1) → A1 (1)
    pattern = [(0, 1.0, BASS_D2), (1, 1.0, BASS_C2), (2, 1.0, BASS_BB1), (3, 1.0, BASS_A1)]
    # Intro bars 1-4 alone, 5-8 with kick joining
    for b in range(1, 9):
        vel = 95 if b <= 4 else 105
        for off, dur, p in pattern:
            nb.add(bar(b) + off, dur, vel, p)
    # Verse A bars 9-24
    for b in range(9, 25):
        for off, dur, p in pattern:
            nb.add(bar(b) + off, dur, 110, p)
    # Breakdown 25-30: silent (drums + bass drop)
    # Verse B 31-46
    for b in range(31, 47):
        for off, dur, p in pattern:
            nb.add(bar(b) + off, dur, 115, p)
    # Drop 47-58 — accentuate octave-up variation last note every 4 bars
    for b in range(47, 59):
        for i, (off, dur, p) in enumerate(pattern):
            v = 122
            # Octave-up variation on the last beat of every 4th bar
            if (b - 47) % 4 == 3 and i == 3:
                nb.add(bar(b) + off, dur, v, BASS_A1 + 12)
            else:
                nb.add(bar(b) + off, dur, v, p)
    # Outro 59-60 fade then silent
    for b in [59, 60]:
        for off, dur, p in pattern:
            nb.add(bar(b) + off, dur, 95 - (b - 59) * 30, p)
    return nb


def build_snare():
    nb = NoteBuilder()
    # Beats 2 + 4 in verses + drop
    def add_section(start_bar, end_bar, vel):
        for b in range(start_bar, end_bar):
            nb.add(bar(b) + 1, 0.25, vel, SNARE)
            nb.add(bar(b) + 3, 0.25, vel, SNARE)
    add_section(9, 25, 110)   # Verse A
    # Breakdown 25-30 silent
    add_section(31, 47, 115)  # Verse B
    add_section(47, 59, 122)  # Drop
    # Drop snare-roll fill end of bar 58 (last 16ths)
    for off in [3.0, 3.25, 3.5, 3.75]:
        nb.add(bar(58) + off, 0.25, 105 + int((off - 3) * 20), SNARE)
    return nb


def build_hats():
    nb = NoteBuilder()
    # Closed hats on 8ths in verse A, 16ths in drop
    def eighths(start_bar, end_bar, vel_base, accent_each_4):
        for b in range(start_bar, end_bar):
            for i in range(8):
                v = vel_base + 15 if (i % 4 == 0 and accent_each_4) else vel_base
                nb.add(bar(b) + i * 0.5, 0.125, v, HAT_CL)
    def sixteenths(start_bar, end_bar, vel_base):
        for b in range(start_bar, end_bar):
            for i in range(16):
                v = vel_base + 18 if i % 4 == 0 else vel_base
                nb.add(bar(b) + i * 0.25, 0.0625, v, HAT_CL)
    eighths(9, 25, 80, True)            # Verse A
    # Breakdown silent
    eighths(31, 47, 88, True)           # Verse B
    sixteenths(47, 59, 95)              # Drop with 16ths
    # Open hat accent every 4 bars in drop
    for b in [50, 54, 58]:
        nb.add(bar(b) + 3.5, 0.5, 110, HAT_OP)
    return nb


def build_lead():
    nb = NoteBuilder()
    # Lead descending motif octave higher, only in DROP + a teaser hint in VERSE B last 4 bars
    pattern = [(0, 1.0, LEAD_D5), (1, 1.0, LEAD_C5), (2, 1.0, LEAD_BB4), (3, 1.0, LEAD_A4)]
    # Verse B last 4 bars — quiet preview
    for b in range(43, 47):
        for off, dur, p in pattern:
            nb.add(bar(b) + off, dur, 85, p)
    # Drop bars 47-58 — full power
    for b in range(47, 59):
        vel = 115
        for off, dur, p in pattern:
            nb.add(bar(b) + off, dur, vel, p)
    return nb


def build_pad():
    """Sustained Dm chord pad. Quiet bed in verses, prominent in BREAKDOWN + OUTRO tail."""
    nb = NoteBuilder()
    chord = [PAD_D3, PAD_F3, PAD_A3]
    # Intro 1-4: sustained Dm chord soft bed
    for p in chord:
        nb.add(bar(1), 16.0, 70, p)   # 4 bars long
    # Verse A 9-24: minimal pad
    for b in [9, 17]:
        for p in chord:
            nb.add(bar(b), 32.0, 60, p)   # 8 bars sustained
    # Breakdown 25-30: PROMINENT pad chord change Dm → Bb (parallel chord shift)
    # Bars 25-27: Dm
    for p in chord:
        nb.add(bar(25), 12.0, 105, p)   # 3 bars
    # Bars 28-30: Bb major (Bb-D-F = soft modal shift)
    bb_chord = [46, 50, 53]   # Bb2 D3 F3
    for p in bb_chord:
        nb.add(bar(28), 12.0, 110, p)   # 3 bars
    # Verse B 31-46: minimal pad
    for b in [31, 39]:
        for p in chord:
            nb.add(bar(b), 32.0, 65, p)
    # Drop 47-58: minimal pad (drums + bass dominate)
    for b in [47, 51, 55]:
        for p in chord:
            nb.add(bar(b), 16.0, 70, p)
    # Outro 59-64: PROMINENT pad sustains as everything else strips
    # Add pad with C as 7th for resolution color (Dm7 = D-F-A-C)
    final_chord = chord + [PAD_C4]
    for p in final_chord:
        nb.add(bar(59), 24.0, 100, p)   # 6 bars sustained — last sound of track
    return nb


# ===== Build all tracks =====
TRACKS = [
    {'name': 'KICK', 'color': 0, 'builder': build_kick, 'midikey_label_pitch': KICK},
    {'name': 'SUB', 'color': 1, 'builder': build_sub, 'midikey_label_pitch': SUB_D1},
    {'name': 'BASS RIFF', 'color': 2, 'builder': build_bass_riff, 'midikey_label_pitch': BASS_A1},
    {'name': 'SNARE', 'color': 3, 'builder': build_snare, 'midikey_label_pitch': SNARE},
    {'name': 'HATS', 'color': 4, 'builder': build_hats, 'midikey_label_pitch': HAT_CL},
    {'name': 'LEAD', 'color': 5, 'builder': build_lead, 'midikey_label_pitch': LEAD_A4},
    {'name': 'PAD', 'color': 6, 'builder': build_pad, 'midikey_label_pitch': PAD_D3},
]

if __name__ == '__main__':
    print('=== Track summary ===')
    for t in TRACKS:
        nb = t['builder']()
        groups = nb.by_pitch()
        print(f'{t["name"]:10s} {len(nb.notes):4d} notes  {len(groups):2d} pitches')
