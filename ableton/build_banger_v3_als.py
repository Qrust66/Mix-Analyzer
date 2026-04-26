"""Build Banger v3 .als from composer output.

Reuses the proven .als-assembly path from build_banger_v2_als.py but consumes
the composition_engine's composer.compose() output instead of hand-coded notes.
"""

import gzip
import re
import sys
from pathlib import Path

sys.path.insert(0, '/home/user/Mix-Analyzer')

from ableton.banger_v3_design import BANGER_V3_COMPOSITION
from composition_engine.composer.composer import compose


# Reuse XML utilities from build_banger_v2_als
from ableton.build_banger_v2_als import (
    build_midi_clip_xml,
    find_track_xml,
    set_tempo,
    rename_track,
    set_track_color,
    inject_clip_into_track,
    clone_track_with_offset,
    inject_locators,
)


TEMPLATE_PATH = '/home/user/Mix-Analyzer/ableton/projects/Template/Template Project/Template.als'
OUTPUT_PATH = '/home/user/Mix-Analyzer/ableton/projects/Banger_v3.als'

# Section locators for Live Arrangement view (informative only — no compositional impact)
LOCATORS = [
    (0, 'INTRO'),                    # bars 1-4
    (16, 'BUILD'),                   # bars 5-12
    (32, 'VERSE A'),                 # bars 13-28
    (112, 'BREAKDOWN (Phrygian)'),   # bars 29-36
    (144, 'VERSE B'),                # bars 37-52
    (208, 'DROP'),                   # bars 53-60
    (240, 'OUTRO'),                  # bars 61-64
]

TRACK_COLORS = {
    'SUB': 1,      # orange
    'BASS': 2,     # yellow
    'DRUMS': 0,    # red/pink
    'PAD': 6,      # green
    'LEAD': 5,     # purple
}


class _NoteAdapter:
    """Adapter so composer's notes (dicts) work with build_midi_clip_xml's
    NoteBuilder API (next_id + by_pitch).
    """
    def __init__(self, notes):
        self.notes = notes
        # Assign sequential note IDs for the MIDI clip
        for i, n in enumerate(self.notes):
            n['noteid'] = i + 1
        self.next_id = len(self.notes) + 1

    def by_pitch(self):
        groups = {}
        for n in self.notes:
            groups.setdefault(n['pitch'], []).append(n)
        for p in groups:
            groups[p].sort(key=lambda n: n['time'])
        return groups


def main():
    print('=== Compose Banger v3 ===')
    result = compose(BANGER_V3_COMPOSITION)
    tracks = result['tracks']
    tempo_bpm = result['tempo_bpm']

    print(f'Tempo: {tempo_bpm} BPM')
    print(f'Total notes: {result["diagnostics"]["total_notes"]}')

    # ===== Load Template =====
    print('\n=== Loading Template ===')
    with gzip.open(TEMPLATE_PATH, 'rb') as f:
        xml = f.read().decode('utf-8')
    print(f'Template XML: {len(xml)} chars')

    xml = set_tempo(xml, tempo_bpm)
    print(f'Tempo set to {tempo_bpm}')

    xml = re.sub(r'<NextPointeeId Value="\d+"', '<NextPointeeId Value="9999999"', xml, count=1)

    # Inject locators
    xml = inject_locators(xml, LOCATORS)
    print(f'Injected {len(LOCATORS)} locator markers')

    # ===== Track 12 → DRUMS =====
    s, e = find_track_xml(xml, 12)
    t12 = xml[s:e]
    t12 = rename_track(t12, 'DRUMS')
    t12 = set_track_color(t12, TRACK_COLORS['DRUMS'])
    t12 = inject_clip_into_track(
        t12, build_midi_clip_xml('DRUMS', TRACK_COLORS['DRUMS'], _NoteAdapter(tracks['DRUMS']))
    )
    xml = xml[:s] + t12 + xml[e:]
    print('Track 12 → DRUMS')

    # ===== Track 13 → SUB =====
    s, e = find_track_xml(xml, 13)
    t13_template = xml[s:e]
    t13 = rename_track(t13_template, 'SUB')
    t13 = set_track_color(t13, TRACK_COLORS['SUB'])
    t13 = inject_clip_into_track(
        t13, build_midi_clip_xml('SUB', TRACK_COLORS['SUB'], _NoteAdapter(tracks['SUB']))
    )
    xml = xml[:s] + t13 + xml[e:]
    print('Track 13 → SUB')

    # ===== Clone track 13 for BASS, PAD, LEAD =====
    clones = [
        ('BASS', 100000, 100013, TRACK_COLORS['BASS']),
        ('PAD',  200000, 200013, TRACK_COLORS['PAD']),
        ('LEAD', 300000, 300013, TRACK_COLORS['LEAD']),
    ]
    cloned_xml = []
    for name, offset, track_id, color in clones:
        clone = clone_track_with_offset(t13_template, offset, track_id)
        clone = rename_track(clone, name)
        clone = set_track_color(clone, color)
        clone = inject_clip_into_track(
            clone, build_midi_clip_xml(name, color, _NoteAdapter(tracks[name]))
        )
        cloned_xml.append(clone)
        print(f'Cloned → {name}')

    s13, e13 = find_track_xml(xml, 13)
    inserted = '\n'.join(cloned_xml)
    xml = xml[:e13] + '\n' + inserted + xml[e13:]
    print(f'Inserted {len(clones)} cloned tracks')

    # ===== Save =====
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUTPUT_PATH, 'wb', compresslevel=9) as f:
        f.write(xml.encode('utf-8'))
    size = Path(OUTPUT_PATH).stat().st_size
    print(f'\nWrote {OUTPUT_PATH} ({size} bytes)')

    # Verify integrity
    with gzip.open(OUTPUT_PATH, 'rb') as f:
        head = f.read(80)
    assert head.startswith(b'<?xml'), 'Double compression!'
    print('Verification: <?xml header OK')

    # Re-read & summarize
    with gzip.open(OUTPUT_PATH, 'rb') as f:
        out = f.read().decode('utf-8')
    track_count = len(re.findall(r'<(MidiTrack|AudioTrack|GroupTrack|ReturnTrack) Id="\d+"', out))
    clip_count = len(re.findall(r'<MidiClip Id="\d+"', out))
    note_count = len(re.findall(r'<MidiNoteEvent ', out))
    locator_count = len(re.findall(r'<Locator Id="\d+"', out))
    print(f'\n=== Output verification ===')
    print(f'Tracks: {track_count}')
    print(f'MidiClips: {clip_count}')
    print(f'MidiNoteEvents: {note_count}')
    print(f'Locators: {locator_count}')


if __name__ == '__main__':
    main()
