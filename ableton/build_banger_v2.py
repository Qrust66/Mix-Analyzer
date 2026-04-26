"""Banger v2 — note-data generator per BANGER_V2_DESIGN.md.

Implements EXACT patterns documented in advisor recipes:
- syncopated_kick: kick at {0, 0.75, 1.5, 2.25} per bar
- robot_rock micro-variations: octave-jumps, gate-length variation, occasional reverse
- descending_riff: D2-C2-Bb1-A1 per bar
- drone_foundation: D1 sustained 60 bars
- modal_voicings: Dsus2/Dm/Phrygian/Dsus4/Dm7
- hard_soft_hard: full drums drop in BREAKDOWN (Phrygian melodic)
- density_arc: 1→2→4→3→4→5→2 layer count per section
"""

# ===== Constants =====
TEMPO = 108.0
END_BAR = 65   # exclusive
CLIP_END_BEATS = (END_BAR - 1) * 4   # 256 beats

# Pitches
KICK = 36
SNARE = 38
HAT_CL = 42
HAT_OP = 46
SUB_D1 = 26
SUB_D0 = 14
BASS_D2 = 38
BASS_C2 = 36
BASS_BB1 = 34
BASS_A1 = 33
BASS_A2 = 45
BASS_D3 = 50
PAD_D3 = 50
PAD_E3 = 52        # for Dsus2
PAD_EB3 = 51       # for Phrygian
PAD_F3 = 53        # Aeolian
PAD_G3 = 55        # for Dsus4
PAD_A3 = 57
PAD_C4 = 60        # for Dm7
PAD_BB2 = 46       # for Bb-stack in drop
LEAD_A4 = 69
LEAD_BB4 = 70
LEAD_C5 = 72
LEAD_D5 = 74
LEAD_EB5 = 75      # Phrygian inflection

# ===== Section bar boundaries =====
INTRO_BARS = (1, 5)         # 1-4 inclusive (5 exclusive)
BUILD_A_BARS = (5, 13)      # 5-12
VERSE_A_BARS = (13, 29)     # 13-28
BREAKDOWN_BARS = (29, 37)   # 29-36
VERSE_B_BARS = (37, 53)     # 37-52
DROP_BARS = (53, 61)        # 53-60
OUTRO_BARS = (61, 65)       # 61-64


def bar(b):
    """Bar (1-indexed) → beat position."""
    return (b - 1) * 4


# ===== NoteBuilder =====
class NoteBuilder:
    def __init__(self):
        self.notes = []
        self.next_id = 1

    def add(self, time, duration, velocity, pitch):
        self.notes.append({
            'time': float(time),
            'duration': float(duration),
            'velocity': max(1, min(127, int(velocity))),
            'pitch': int(pitch),
            'noteid': self.next_id,
        })
        self.next_id += 1

    def by_pitch(self):
        groups = {}
        for n in self.notes:
            groups.setdefault(n['pitch'], []).append(n)
        for p in groups:
            groups[p].sort(key=lambda n: n['time'])
        return groups


# ===== DRUMS (KICK + SNARE + HATS) =====

def build_drums():
    """Combined Drum Rack track."""
    nb = NoteBuilder()

    # KICK pattern: syncopated_kick at {0, 0.75, 1.5, 2.25}
    KICK_PATTERN = [0.0, 0.75, 1.5, 2.25]

    # BUILD A bars 5-12: kick on beat 0 only every other bar
    for b in range(*BUILD_A_BARS):
        if (b - BUILD_A_BARS[0]) % 2 == 0:   # bars 5, 7, 9, 11
            nb.add(bar(b), 0.25, 90, KICK)

    # VERSE A bars 13-28: full syncopated pattern every bar
    for b in range(*VERSE_A_BARS):
        for i, off in enumerate(KICK_PATTERN):
            vel = 118 if i == 0 else 105
            nb.add(bar(b) + off, 0.25, vel, KICK)

    # BREAKDOWN bars 29-36: NO KICK (hard_soft contrast)

    # VERSE B bars 37-52: pattern + ghost on 3.5 every 4th bar
    for b in range(*VERSE_B_BARS):
        for i, off in enumerate(KICK_PATTERN):
            vel = 120 if i == 0 else 108
            nb.add(bar(b) + off, 0.25, vel, KICK)
        if (b - VERSE_B_BARS[0]) % 4 == 3:   # bars 40, 44, 48, 52
            nb.add(bar(b) + 3.5, 0.25, 88, KICK)

    # DROP bars 53-60: full + ghost on 3.75 every bar
    for b in range(*DROP_BARS):
        for i, off in enumerate(KICK_PATTERN):
            vel = 124 if i == 0 else 113
            nb.add(bar(b) + off, 0.25, vel, KICK)
        nb.add(bar(b) + 3.75, 0.25, 92, KICK)

    # OUTRO: no kick

    # SNARE pattern
    # VERSE A: beats 1 + 3 (1-indexed) = 0-indexed beats 1.0 + 3.0
    for b in range(*VERSE_A_BARS):
        nb.add(bar(b) + 1.0, 0.25, 110, SNARE)
        nb.add(bar(b) + 3.0, 0.25, 110, SNARE)

    # VERSE B: same + ghost on 3.5 every 4 bars
    for b in range(*VERSE_B_BARS):
        nb.add(bar(b) + 1.0, 0.25, 115, SNARE)
        nb.add(bar(b) + 3.0, 0.25, 115, SNARE)
        if (b - VERSE_B_BARS[0]) % 4 == 3:
            nb.add(bar(b) + 3.5, 0.25, 80, SNARE)

    # DROP: backbeat + 16th-note crescendo on bar 60 (last bar)
    for b in range(*DROP_BARS):
        nb.add(bar(b) + 1.0, 0.25, 122, SNARE)
        nb.add(bar(b) + 3.0, 0.25, 122, SNARE)
    # Bar 60 crescendo roll: 16ths on beats 3-4
    for i in range(8):
        t = bar(60) + 2.0 + i * 0.25
        vel = 90 + i * 4
        nb.add(t, 0.125, vel, SNARE)

    # HAT pattern (closed)
    # VERSE A: 8th-notes with velocity-accent
    accent_pattern = [108, 64, 80, 64, 80, 64, 80, 64]
    for b in range(*VERSE_A_BARS):
        for i in range(8):
            nb.add(bar(b) + i * 0.5, 0.125, accent_pattern[i], HAT_CL)
        # Open hat every 4 bars at beat 3.75
        if (b - VERSE_A_BARS[0]) % 4 == 3:
            nb.add(bar(b) + 3.5, 0.5, 100, HAT_OP)

    # VERSE B: 16th-notes
    sixteenth_accent = [105, 60, 70, 60, 80, 60, 70, 60, 90, 60, 70, 60, 80, 60, 70, 60]
    for b in range(*VERSE_B_BARS):
        for i in range(16):
            nb.add(bar(b) + i * 0.25, 0.0625, sixteenth_accent[i], HAT_CL)
        if (b - VERSE_B_BARS[0]) % 4 == 3:
            nb.add(bar(b) + 3.5, 0.5, 105, HAT_OP)

    # DROP: 16ths first 4 bars, 32nds last 4 bars
    for b in range(53, 57):   # bars 53-56: 16ths
        for i in range(16):
            nb.add(bar(b) + i * 0.25, 0.0625, 110 if i % 4 == 0 else 75, HAT_CL)
    for b in range(57, 61):   # bars 57-60: 32nds (mania)
        for i in range(32):
            vel = 115 if i % 8 == 0 else (85 if i % 4 == 0 else 60)
            nb.add(bar(b) + i * 0.125, 0.0625, vel, HAT_CL)

    return nb


# ===== SUB DRONE =====

def build_sub():
    """D1 sustained drone bars 1-60, plus D0 octave-down in DROP only."""
    nb = NoteBuilder()
    # Continuous D1 sustained — but Live's note-events have a max duration; chunk into 4-bar segments for safety
    for chunk_start_bar in range(1, 61, 4):   # bars 1, 5, 9, ..., 57
        chunk_end_bar = min(chunk_start_bar + 4, 61)
        dur_beats = (chunk_end_bar - chunk_start_bar) * 4
        # Velocity ramps with section: intro=80, build=85, verse_a=95, breakdown=70, verse_b=100, drop=120
        if chunk_start_bar < 5:
            v = 80
        elif chunk_start_bar < 13:
            v = 85
        elif chunk_start_bar < 29:
            v = 95
        elif chunk_start_bar < 37:
            v = 70
        elif chunk_start_bar < 53:
            v = 100
        else:
            v = 120
        nb.add(bar(chunk_start_bar), dur_beats, v, SUB_D1)

    # D0 deep-sub layer in DROP only
    for chunk_start_bar in range(53, 61, 4):
        nb.add(bar(chunk_start_bar), 16.0, 110, SUB_D0)

    # OUTRO: D1 sustained bars 61-64, abrupt cut at end of bar 64 (beat 256)
    nb.add(bar(61), 15.5, 95, SUB_D1)   # 4 bars - 0.5 beats = abrupt cut before the absolute end

    return nb


# ===== BASS RIFF — descending_riff + robot_rock micro-variations =====

def build_bass():
    """Descending D2-C2-Bb1-A1 with documented variations."""
    nb = NoteBuilder()
    base = [(0, 1.0, BASS_D2), (1, 1.0, BASS_C2), (2, 1.0, BASS_BB1), (3, 1.0, BASS_A1)]

    def add_pattern(b, pattern, vel_base):
        for off, dur, p in pattern:
            nb.add(bar(b) + off, dur, vel_base, p)

    # BUILD A bars 5-12: base pattern, low velocity
    for b in range(*BUILD_A_BARS):
        add_pattern(b, base, 90)

    # VERSE A bars 13-28: 4-bar variation cycle × 4
    for cycle in range(4):
        bs = VERSE_A_BARS[0] + cycle * 4   # 13, 17, 21, 25
        # Bar 0 of cycle: base
        add_pattern(bs, base, 110)
        # Bar 1: base
        add_pattern(bs + 1, base, 110)
        # Bar 2: D2 doubled on beat 1 (gate variation: half + half)
        var2 = [(0, 0.5, BASS_D2), (0.5, 0.5, BASS_D2),
                (1, 1.0, BASS_C2), (2, 1.0, BASS_BB1), (3, 1.0, BASS_A1)]
        add_pattern(bs + 2, var2, 113)
        # Bar 3: octave-up on last note (A2 instead of A1) every 8 bars
        if cycle % 2 == 1:   # cycles 1 and 3 (bars 17-20, 25-28)
            var3 = base[:3] + [(3, 1.0, BASS_A2)]
            add_pattern(bs + 3, var3, 115)
        else:
            add_pattern(bs + 3, base, 110)

    # BREAKDOWN: BASS DROPS OUT (hard_soft contrast)

    # VERSE B bars 37-52: more variations
    for cycle in range(4):
        bs = VERSE_B_BARS[0] + cycle * 4   # 37, 41, 45, 49
        # Bar 0
        if cycle == 1:   # bar 41: octave-jump on bar 1 last note
            var = base[:3] + [(3, 1.0, BASS_A2)]
            add_pattern(bs, var, 117)
        else:
            add_pattern(bs, base, 115)
        # Bar 1
        add_pattern(bs + 1, base, 115)
        # Bar 2: REVERSE (ascending — robot_rock surprise) only on cycle 2 (bar 47)
        if cycle == 2:   # bar 47
            reverse = [(0, 1.0, BASS_A1), (1, 1.0, BASS_BB1), (2, 1.0, BASS_C2), (3, 1.0, BASS_D2)]
            add_pattern(bs + 2, reverse, 118)
        else:
            add_pattern(bs + 2, base, 115)
        # Bar 3
        if cycle == 3:   # bar 52: octave-up + last note sustained into DROP
            var = base[:3] + [(3, 4.0, BASS_D3)]   # D3 sustained 4 beats → into DROP
            add_pattern(bs + 3, var, 120)
        else:
            add_pattern(bs + 3, base, 115)

    # DROP bars 53-60: pattern + octave-up doubling on beat 4 every bar
    for b in range(*DROP_BARS):
        for i, (off, dur, p) in enumerate(base):
            nb.add(bar(b) + off, dur, 122, p)
            if i == 3:   # beat 4: also play octave-up
                nb.add(bar(b) + off, dur, 105, p + 12)

    # Bar 60 final: power-stack on beat 1 — D2+C2+Bb1+A1 ALL hit simultaneously
    # (this OVERWRITES the bar 60 base pattern at beat 1; conceptually it's a layered chord)
    # Actually let me keep base + add the stack on beat 0
    for p in [BASS_C2, BASS_BB1, BASS_A1]:
        nb.add(bar(60), 1.0, 115, p)

    # OUTRO: BASS silent

    return nb


# ===== PAD — modal_voicings_above_drone =====

def build_pad():
    """Modal voicings sustained per section."""
    nb = NoteBuilder()

    def chord(start_bar, num_bars, voicing, vel):
        for p in voicing:
            nb.add(bar(start_bar), num_bars * 4.0, vel, p)

    # INTRO: silent (drone + nothing else)

    # BUILD A bars 5-12 (8 bars): Dsus2 sustained
    chord(5, 8, [PAD_D3, PAD_E3, PAD_A3], 75)

    # VERSE A bars 13-28 (16 bars): Dm Aeolian (split into 2× 8-bar holds for envelope-friendliness)
    chord(13, 8, [PAD_D3, PAD_F3, PAD_A3], 90)
    chord(21, 8, [PAD_D3, PAD_F3, PAD_A3], 95)

    # BREAKDOWN bars 29-32 (4 bars): Dm Phrygian (Eb inflection)
    chord(29, 4, [PAD_D3, PAD_EB3, PAD_A3], 105)
    # BREAKDOWN bars 33-36 (4 bars): Dsus4
    chord(33, 4, [PAD_D3, PAD_G3, PAD_A3], 100)

    # VERSE B bars 37-52 (16 bars): Dm Aeolian
    chord(37, 8, [PAD_D3, PAD_F3, PAD_A3], 95)
    chord(45, 8, [PAD_D3, PAD_F3, PAD_A3], 100)

    # DROP bars 53-60 (8 bars): Dm + Bb stack (cluster — Bb-D-F-A)
    chord(53, 8, [PAD_BB2, PAD_D3, PAD_F3, PAD_A3], 110)

    # OUTRO bars 61-64 (4 bars): Dm7 sustained, abrupt cut bar 64.5
    # Use 3.5-beat bar (15-beat total instead of 16) for abrupt cut just before beat 256
    nb.add(bar(61), 15.5, 100, PAD_D3)
    nb.add(bar(61), 15.5, 100, PAD_F3)
    nb.add(bar(61), 15.5, 100, PAD_A3)
    nb.add(bar(61), 15.5, 100, PAD_C4)

    return nb


# ===== LEAD — counter-melody (BREAKDOWN + DROP only) =====

def build_lead():
    nb = NoteBuilder()

    # BREAKDOWN bars 29-36: Phrygian descent chant
    # Bars 29-30: A4 sustained 2 bars
    nb.add(bar(29), 8.0, 95, LEAD_A4)
    # Bar 31: Eb5 (Phrygian flat-2 inflection)
    nb.add(bar(31), 4.0, 105, LEAD_EB5)
    # Bar 32: D5
    nb.add(bar(32), 4.0, 100, LEAD_D5)
    # Bar 33: C5
    nb.add(bar(33), 4.0, 92, LEAD_C5)
    # Bar 34: Bb4
    nb.add(bar(34), 4.0, 88, LEAD_BB4)
    # Bar 35: A4
    nb.add(bar(35), 4.0, 85, LEAD_A4)
    # Bar 36: silence (transition to verse B)

    # DROP bars 53-60: ascending counter-melody (against descending bass)
    # Pattern A4-Bb4-C5-D5 1 note per beat
    asc = [LEAD_A4, LEAD_BB4, LEAD_C5, LEAD_D5]
    for b in range(53, 57):
        for i, p in enumerate(asc):
            nb.add(bar(b) + i, 1.0, 110, p)
    # Bars 57-60: doubled — D5 octave anchor every 2nd 8th
    for b in range(57, 61):
        for i, p in enumerate(asc):
            nb.add(bar(b) + i, 1.0, 115, p)
            # Add D5 anchor on the "and" of each beat
            nb.add(bar(b) + i + 0.5, 0.5, 90, LEAD_D5)

    return nb


# ===== Track manifest =====
TRACKS_V2 = [
    {'name': 'DRUMS', 'color': 0, 'builder': build_drums},
    {'name': 'SUB', 'color': 1, 'builder': build_sub},
    {'name': 'BASS', 'color': 2, 'builder': build_bass},
    {'name': 'PAD', 'color': 6, 'builder': build_pad},
    {'name': 'LEAD', 'color': 5, 'builder': build_lead},
]


# ===== Locator markers per section =====
LOCATORS = [
    (0, 'INTRO'),
    (16, 'BUILD A'),
    (48, 'VERSE A'),
    (112, 'BREAKDOWN'),
    (144, 'VERSE B'),
    (208, 'DROP'),
    (240, 'OUTRO'),
]


if __name__ == '__main__':
    print('=== Banger v2 note-data summary ===')
    total = 0
    for t in TRACKS_V2:
        nb = t['builder']()
        groups = nb.by_pitch()
        n = len(nb.notes)
        total += n
        print(f"{t['name']:8s} {n:4d} notes  pitches={sorted(groups.keys())}")
    print(f'\nTOTAL: {total} notes across {len(TRACKS_V2)} tracks')
    print(f'Locators: {len(LOCATORS)} section markers')
