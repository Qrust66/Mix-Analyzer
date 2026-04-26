"""Build Banger v2 .als from Template.als + v2 note-data + locators."""
import gzip
import re
import sys
from pathlib import Path

sys.path.insert(0, '/home/user/Mix-Analyzer/ableton')
from build_banger_v2 import (
    TRACKS_V2, LOCATORS, TEMPO, CLIP_END_BEATS,
)


# Reuse XML builders from v1 (build_banger_als imports them via shim)

def build_midi_clip_xml(track_name, color_idx, note_builder, clip_local_id=0):
    notes_by_pitch = note_builder.by_pitch()
    keytracks_xml = []
    keytrack_local_id = 0
    for pitch in sorted(notes_by_pitch.keys()):
        notes = notes_by_pitch[pitch]
        events = '\n              '.join(
            f'<MidiNoteEvent Time="{n["time"]}" Duration="{n["duration"]}" '
            f'Velocity="{n["velocity"]}" OffVelocity="64" NoteId="{n["noteid"]}" />'
            for n in notes
        )
        keytrack = f"""        <KeyTrack Id="{keytrack_local_id}">
          <Notes>
              {events}
          </Notes>
          <MidiKey Value="{pitch}" />
        </KeyTrack>"""
        keytracks_xml.append(keytrack)
        keytrack_local_id += 1
    keytracks_block = '\n'.join(keytracks_xml)
    next_note_id = note_builder.next_id

    return f"""<MidiClip Id="{clip_local_id}" Time="0">
    <LomId Value="0" />
    <LomIdView Value="0" />
    <CurrentStart Value="0" />
    <CurrentEnd Value="{CLIP_END_BEATS}" />
    <Loop>
      <LoopStart Value="0" />
      <LoopEnd Value="{CLIP_END_BEATS}" />
      <StartRelative Value="0" />
      <LoopOn Value="false" />
      <OutMarker Value="{CLIP_END_BEATS}" />
      <HiddenLoopStart Value="0" />
      <HiddenLoopEnd Value="{CLIP_END_BEATS}" />
    </Loop>
    <Name Value="{track_name}" />
    <Annotation Value="" />
    <Color Value="{color_idx}" />
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
      <RightTime Value="{CLIP_END_BEATS}" />
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
    <IsInKey Value="false" />
    <ScaleInformation>
      <Root Value="0" />
      <Name Value="0" />
    </ScaleInformation>
    <Notes>
      <KeyTracks>
{keytracks_block}
      </KeyTracks>
      <PerNoteEventStore>
        <EventLists />
      </PerNoteEventStore>
      <NoteProbabilityGroups />
      <ProbabilityGroupIdGenerator>
        <NextId Value="1" />
      </ProbabilityGroupIdGenerator>
      <NoteIdGenerator>
        <NextId Value="{next_note_id}" />
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
  </MidiClip>"""


def find_track_xml(xml, track_id):
    m = re.search(rf'<MidiTrack Id="{track_id}"', xml)
    if not m:
        raise ValueError(f'MidiTrack {track_id} not found')
    start = m.start()
    end = xml.find('</MidiTrack>', start) + len('</MidiTrack>')
    return start, end


def set_tempo(xml, bpm):
    return re.sub(
        r'(<Tempo>.*?<Manual Value=")[\d.]+(")',
        rf'\g<1>{bpm}\g<2>',
        xml, count=1, flags=re.DOTALL,
    )


def rename_track(track_xml, new_name):
    track_xml = re.sub(r'<EffectiveName Value="[^"]*"', f'<EffectiveName Value="{new_name}"', track_xml, count=1)
    track_xml = re.sub(r'<UserName Value="[^"]*"', f'<UserName Value="{new_name}"', track_xml, count=1)
    track_xml = re.sub(r'<MemorizedFirstClipName Value="[^"]*"', f'<MemorizedFirstClipName Value="{new_name}"', track_xml, count=1)
    return track_xml


def set_track_color(track_xml, color_idx):
    return re.sub(r'<Color Value="\d+"', f'<Color Value="{color_idx}"', track_xml, count=1)


def inject_clip_into_track(track_xml, clip_xml):
    pattern = r'(<ClipTimeable>\s*<ArrangerAutomation>\s*)<Events />'
    replacement = rf'\g<1><Events>{clip_xml}</Events>'
    new_xml, count = re.subn(pattern, replacement, track_xml, count=1)
    if count == 0:
        raise ValueError('Could not find empty <Events /> in ArrangerAutomation')
    return new_xml


def clone_track_with_offset(template_track_xml, id_offset, new_track_id):
    def shift_id(m):
        n = int(m.group(1))
        return f'Id="{n + id_offset}"' if n >= 10 else m.group(0)
    shifted = re.sub(r'Id="(\d+)"', shift_id, template_track_xml)

    def shift_pointee(m):
        n = int(m.group(1))
        return f'PointeeId Value="{n + id_offset}"' if n >= 10 else m.group(0)
    shifted = re.sub(r'PointeeId Value="(\d+)"', shift_pointee, shifted)

    def shift_track_ref(m):
        n = int(m.group(1))
        return f'<Track Value="{n + id_offset}"' if n >= 10 else m.group(0)
    shifted = re.sub(r'<Track Value="(\d+)"', shift_track_ref, shifted)

    shifted = re.sub(r'<MidiTrack Id="\d+"', f'<MidiTrack Id="{new_track_id}"', shifted, count=1)
    return shifted


def inject_locators(xml, locators):
    """Inject Live Arrangement-view section markers via <Locators> block.

    Locators sit at the top level of <LiveSet>. Find existing <Locators> block
    (or insert one) with each <Locator Time="..." Name="..." />.
    """
    locator_xml_items = []
    for i, (time_beats, name) in enumerate(locators):
        locator_xml_items.append(f"""        <Locator Id="{i}">
          <Time Value="{time_beats}" />
          <Name Value="{name}" />
          <Annotation Value="" />
          <IsSongStart Value="false" />
        </Locator>""")
    locators_block = '\n'.join(locator_xml_items)
    new_locators_xml = f"""<Locators>
      <Locators>
{locators_block}
      </Locators>
    </Locators>"""

    # Replace existing <Locators>...</Locators> if present, else insert before </LiveSet>
    if re.search(r'<Locators>.*?</Locators>', xml, re.DOTALL):
        xml = re.sub(r'<Locators>.*?</Locators>', new_locators_xml, xml, count=1, flags=re.DOTALL)
    else:
        # Insert before </LiveSet>
        xml = xml.replace('</LiveSet>', f'    {new_locators_xml}\n</LiveSet>', 1)
    return xml


# ===== Main build =====

TEMPLATE_PATH = '/home/user/Mix-Analyzer/ableton/projects/Template/Template Project/Template.als'
OUTPUT_PATH = '/home/user/Mix-Analyzer/ableton/projects/Banger_Cobain30_Reznor30_v2.als'


def main():
    print('=== Loading Template ===')
    with gzip.open(TEMPLATE_PATH, 'rb') as f:
        xml = f.read().decode('utf-8')
    print(f'Template XML: {len(xml)} chars')

    xml = set_tempo(xml, TEMPO)
    print(f'Tempo set to {TEMPO}')

    xml = re.sub(r'<NextPointeeId Value="\d+"', '<NextPointeeId Value="9999999"', xml, count=1)

    # Inject locators
    xml = inject_locators(xml, LOCATORS)
    print(f'Injected {len(LOCATORS)} locator markers')

    # Build all 5 NoteBuilders
    builders = {t['name']: t['builder']() for t in TRACKS_V2}
    for name, nb in builders.items():
        print(f'  {name:8s} {len(nb.notes):4d} notes, {len(nb.by_pitch())} pitches')

    # Track 12 → DRUMS
    s, e = find_track_xml(xml, 12)
    t12 = xml[s:e]
    t12 = rename_track(t12, 'DRUMS')
    t12 = set_track_color(t12, 0)
    t12 = inject_clip_into_track(t12, build_midi_clip_xml('DRUMS', 0, builders['DRUMS']))
    xml = xml[:s] + t12 + xml[e:]
    print('Track 12 → DRUMS')

    # Track 13 → SUB (use as clone-source TEMPLATE before injecting clip)
    s, e = find_track_xml(xml, 13)
    t13_template = xml[s:e]
    t13 = rename_track(t13_template, 'SUB')
    t13 = set_track_color(t13, 1)
    t13 = inject_clip_into_track(t13, build_midi_clip_xml('SUB', 1, builders['SUB']))
    xml = xml[:s] + t13 + xml[e:]
    print('Track 13 → SUB')

    # Clone track 13 for: BASS, PAD, LEAD
    clones = [
        ('BASS', 100000, 100013, 2),
        ('PAD',  200000, 200013, 6),
        ('LEAD', 300000, 300013, 5),
    ]
    cloned_xml = []
    for name, offset, track_id, color in clones:
        clone = clone_track_with_offset(t13_template, offset, track_id)
        clone = rename_track(clone, name)
        clone = set_track_color(clone, color)
        clone = inject_clip_into_track(clone, build_midi_clip_xml(name, color, builders[name]))
        cloned_xml.append(clone)
        print(f'Cloned → {name}')

    # Insert cloned tracks after track 13
    s13, e13 = find_track_xml(xml, 13)
    inserted = '\n'.join(cloned_xml)
    xml = xml[:e13] + '\n' + inserted + xml[e13:]
    print(f'Inserted {len(clones)} cloned tracks')

    # Save
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUTPUT_PATH, 'wb', compresslevel=9) as f:
        f.write(xml.encode('utf-8'))
    size = Path(OUTPUT_PATH).stat().st_size
    print(f'\nWrote {OUTPUT_PATH} ({size} bytes)')

    # Verify first bytes
    with gzip.open(OUTPUT_PATH, 'rb') as f:
        head = f.read(80)
    assert head.startswith(b'<?xml'), 'Double compression!'
    print('Verification: <?xml header OK')

    # Re-read & summarize
    with gzip.open(OUTPUT_PATH, 'rb') as f:
        out = f.read().decode('utf-8')
    tracks = re.findall(r'<(MidiTrack|AudioTrack|GroupTrack|ReturnTrack) Id="(\d+)"', out)
    clips = len(re.findall(r'<MidiClip Id="\d+"', out))
    notes = len(re.findall(r'<MidiNoteEvent ', out))
    locators_found = len(re.findall(r'<Locator Id="\d+"', out))
    print(f'\n=== Output verification ===')
    print(f'Tracks: {len(tracks)}')
    for kind, tid in tracks:
        en = re.search(rf'<{kind} Id="{tid}".*?<EffectiveName Value="([^"]*)"', out, re.DOTALL)
        print(f'  {kind} {tid}: "{en.group(1) if en else "?"}"')
    print(f'MidiClips: {clips}')
    print(f'MidiNoteEvents: {notes}')
    print(f'Locators: {locators_found}')


if __name__ == '__main__':
    main()
