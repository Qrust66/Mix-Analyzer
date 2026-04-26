"""Build Banger_v3_ambient.als from composer output.

Uses 3 MIDI tracks only (SUB + PAD + LEAD — no DRUMS/BASS).
Reuses the v3 ALS-assembly path; only difference is which composition is rendered.
"""
import gzip
import re
import sys
from pathlib import Path

sys.path.insert(0, '/home/user/Mix-Analyzer')

from ableton.banger_v3_ambient_design import BANGER_AMBIENT_COMPOSITION
from composition_engine.composer.composer import compose

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
from ableton.build_banger_v3_als import _NoteAdapter


TEMPLATE_PATH = '/home/user/Mix-Analyzer/ableton/projects/Template/Template Project/Template.als'
OUTPUT_PATH = '/home/user/Mix-Analyzer/ableton/projects/Banger_v3_ambient.als'

# Ambient: gentle informative locators
LOCATORS = [
    (0, 'OPENING'),                  # bars 1-8
    (32, 'PAD ESTABLISHED'),         # bars 9-32
    (128, 'PHRYGIAN DEPTH'),         # bars 33-42
    (168, 'RESOLUTION'),             # bars 43-58
    (232, 'OUTRO FADE'),             # bars 59-64
]

TRACK_COLORS = {
    'SUB': 1,      # orange (warmth)
    'PAD': 6,      # green (modal)
    'LEAD': 4,     # blue (atmospheric)
}


def main():
    print('=== Compose Banger v3 AMBIENT ===')
    result = compose(BANGER_AMBIENT_COMPOSITION)
    tracks = result['tracks']
    tempo_bpm = result['tempo_bpm']

    print(f'Tempo: {tempo_bpm} BPM')
    print(f'Total notes: {result["diagnostics"]["total_notes"]}')
    for tname, c in result['diagnostics']['note_count_per_track'].items():
        print(f'  {tname}: {c} notes')

    print('\n=== Loading Template ===')
    with gzip.open(TEMPLATE_PATH, 'rb') as f:
        xml = f.read().decode('utf-8')

    xml = set_tempo(xml, tempo_bpm)
    xml = re.sub(r'<NextPointeeId Value="\d+"', '<NextPointeeId Value="9999999"', xml, count=1)
    xml = inject_locators(xml, LOCATORS)
    print(f'Tempo {tempo_bpm} BPM, locators={len(LOCATORS)}')

    # Track 12 → SUB (drone foundation)
    s, e = find_track_xml(xml, 12)
    t12 = xml[s:e]
    t12 = rename_track(t12, 'SUB')
    t12 = set_track_color(t12, TRACK_COLORS['SUB'])
    t12 = inject_clip_into_track(
        t12, build_midi_clip_xml('SUB', TRACK_COLORS['SUB'], _NoteAdapter(tracks['SUB']))
    )
    xml = xml[:s] + t12 + xml[e:]
    print('Track 12 → SUB')

    # Track 13 → PAD
    s, e = find_track_xml(xml, 13)
    t13_template = xml[s:e]
    t13 = rename_track(t13_template, 'PAD')
    t13 = set_track_color(t13, TRACK_COLORS['PAD'])
    t13 = inject_clip_into_track(
        t13, build_midi_clip_xml('PAD', TRACK_COLORS['PAD'], _NoteAdapter(tracks['PAD']))
    )
    xml = xml[:s] + t13 + xml[e:]
    print('Track 13 → PAD')

    # Clone track 13 for LEAD
    clones = [
        ('LEAD', 100000, 100013, TRACK_COLORS['LEAD']),
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

    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUTPUT_PATH, 'wb', compresslevel=9) as f:
        f.write(xml.encode('utf-8'))

    with gzip.open(OUTPUT_PATH, 'rb') as f:
        head = f.read(80)
    assert head.startswith(b'<?xml'), 'Double compression!'

    size = Path(OUTPUT_PATH).stat().st_size
    with gzip.open(OUTPUT_PATH, 'rb') as f:
        out = f.read().decode('utf-8')
    note_count = len(re.findall(r'<MidiNoteEvent ', out))
    track_count = len(re.findall(r'<MidiTrack Id="\d+"', out))

    print(f'\nWrote {OUTPUT_PATH} ({size} bytes)')
    print(f'Verification OK: {track_count} MIDI tracks, {note_count} note events')


if __name__ == '__main__':
    main()
