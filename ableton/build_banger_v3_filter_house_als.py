"""Build Banger_v3_filter_house.als from composer output."""
import gzip
import re
import sys
from pathlib import Path

sys.path.insert(0, '/home/user/Mix-Analyzer')

from ableton.banger_v3_filter_house_design import BANGER_FILTER_HOUSE_COMPOSITION
from composition_engine.composer.composer import compose

from ableton.build_banger_v2_als import (
    build_midi_clip_xml, find_track_xml, set_tempo, rename_track,
    set_track_color, inject_clip_into_track, clone_track_with_offset, inject_locators,
)
from ableton.build_banger_v3_als import _NoteAdapter


TEMPLATE_PATH = '/home/user/Mix-Analyzer/ableton/projects/Template/Template Project/Template.als'
OUTPUT_PATH = '/home/user/Mix-Analyzer/ableton/projects/Banger_v3_filter_house.als'

# Filter-house: dance-floor section markers
LOCATORS = [
    (0, 'INTRO'),                    # bars 1-4
    (16, 'BUILD'),                   # bars 5-12
    (32, 'KICK ENTERS'),             # bars 13-24
    (96, 'VOCODED PHRASE'),          # bars 25-40
    (160, 'BREAK'),                  # bars 41-48
    (192, 'PEAK'),                   # bars 49-56
    (224, 'OUTRO'),                  # bars 57-64
]

TRACK_COLORS = {
    'SUB': 1,      # orange
    'BASS': 2,     # yellow
    'DRUMS': 0,    # red/pink
    'PAD': 6,      # green
    'LEAD': 5,     # purple
}


def main():
    print('=== Compose Banger v3 FILTER HOUSE ===')
    result = compose(BANGER_FILTER_HOUSE_COMPOSITION)
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

    # Track 12 → DRUMS
    s, e = find_track_xml(xml, 12)
    t12 = xml[s:e]
    t12 = rename_track(t12, 'DRUMS')
    t12 = set_track_color(t12, TRACK_COLORS['DRUMS'])
    t12 = inject_clip_into_track(
        t12, build_midi_clip_xml('DRUMS', TRACK_COLORS['DRUMS'], _NoteAdapter(tracks['DRUMS']))
    )
    xml = xml[:s] + t12 + xml[e:]
    print('Track 12 → DRUMS')

    # Track 13 → SUB
    s, e = find_track_xml(xml, 13)
    t13_template = xml[s:e]
    t13 = rename_track(t13_template, 'SUB')
    t13 = set_track_color(t13, TRACK_COLORS['SUB'])
    t13 = inject_clip_into_track(
        t13, build_midi_clip_xml('SUB', TRACK_COLORS['SUB'], _NoteAdapter(tracks['SUB']))
    )
    xml = xml[:s] + t13 + xml[e:]
    print('Track 13 → SUB')

    # Clone for BASS, PAD, LEAD
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
