"""
ALS assembler — build Banger_Cobain30_Reznor30_v1.als from Template.als.

Strategy:
- Read Template.als (Live 12.3.7 baseline with MidiTrack 12 + 13 + 2 audio + 2 returns).
- Update tempo to 108.
- Rename track 12 → "KICK", track 13 → "SUB". Inject MidiClip into each.
- Clone MidiTrack 13 five times with offset IDs (avoids collision):
    BASS RIFF (offset 100000)
    SNARE      (offset 200000)
    HATS       (offset 300000)
    LEAD       (offset 400000)
    PAD        (offset 500000)
- Update NextPointeeId to 9999999.
- Save as Banger_Cobain30_Reznor30_v1.als.

Composition (per advisor top-30 + dark_electronic_hybrid template):
- 108 BPM, D minor, 64 bars 4/4, 6 sections (intro/verseA/breakdown/verseB/drop/outro)
- Recipes: descending_riff_as_song_identity + mid_tempo_aggression + hard_soft_hard +
  programmed_drums_as_engine + bass_line_first + density_arc + abrupt_end
"""
import gzip
import re
from pathlib import Path

# Import composition spec
import sys
sys.path.insert(0, '/home/user/Mix-Analyzer/ableton')
from build_banger import (
    build_kick, build_sub, build_bass_riff, build_snare, build_hats, build_lead, build_pad,
    TEMPO, CLIP_END_BEATS,
)

# ===== MidiClip XML generator =====

def build_midi_clip_xml(track_name, color_idx, note_builder, clip_local_id=0):
    """Generate a complete <MidiClip>...</MidiClip> XML.

    note_builder: NoteBuilder instance with notes added.
    Returns XML string suitable for embedding in <ArrangerAutomation><Events>.
    """
    notes_by_pitch = note_builder.by_pitch()

    keytracks_xml = []
    keytrack_local_id = 0
    for pitch in sorted(notes_by_pitch.keys()):
        notes = notes_by_pitch[pitch]
        note_events = []
        for n in notes:
            note_events.append(
                f'<MidiNoteEvent Time="{n["time"]}" Duration="{n["duration"]}" '
                f'Velocity="{n["velocity"]}" OffVelocity="64" NoteId="{n["noteid"]}" />'
            )
        events_block = '\n              '.join(note_events)

        keytrack = f"""        <KeyTrack Id="{keytrack_local_id}">
          <Notes>
              {events_block}
          </Notes>
          <MidiKey Value="{pitch}" />
        </KeyTrack>"""
        keytracks_xml.append(keytrack)
        keytrack_local_id += 1

    keytracks_block = '\n'.join(keytracks_xml)
    next_note_id = note_builder.next_id

    clip_xml = f"""<MidiClip Id="{clip_local_id}" Time="0">
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
    return clip_xml


# ===== Track manipulation =====

def find_track_xml(xml, track_id):
    """Return (start, end) of MidiTrack with given Id."""
    m = re.search(rf'<MidiTrack Id="{track_id}"', xml)
    if not m:
        raise ValueError(f'MidiTrack {track_id} not found')
    start = m.start()
    # Find matching </MidiTrack> at same nesting level — assume single occurrence forward
    # since track XML is well-formed
    end = xml.find('</MidiTrack>', start) + len('</MidiTrack>')
    return start, end


def set_tempo(xml, bpm):
    """Update the global tempo."""
    return re.sub(
        r'(<Tempo>.*?<Manual Value=")[\d.]+(")',
        rf'\g<1>{bpm}\g<2>',
        xml,
        count=1,
        flags=re.DOTALL,
    )


def rename_track(track_xml, new_name):
    """Replace EffectiveName + UserName + MemorizedFirstClipName."""
    track_xml = re.sub(r'<EffectiveName Value="[^"]*"', f'<EffectiveName Value="{new_name}"', track_xml, count=1)
    track_xml = re.sub(r'<UserName Value="[^"]*"', f'<UserName Value="{new_name}"', track_xml, count=1)
    track_xml = re.sub(r'<MemorizedFirstClipName Value="[^"]*"', f'<MemorizedFirstClipName Value="{new_name}"', track_xml, count=1)
    return track_xml


def set_track_color(track_xml, color_idx):
    """Replace first Color tag in the track header (track-level color, not clip)."""
    return re.sub(r'<Color Value="\d+"', f'<Color Value="{color_idx}"', track_xml, count=1)


def inject_clip_into_track(track_xml, clip_xml):
    """Replace empty <Events /> in ArrangerAutomation with <Events>{clip_xml}</Events>.

    Targets the FIRST <Events /> within ArrangerAutomation context (the arrangement clips list).
    """
    # The arrangement's empty <Events /> is right after <ArrangerAutomation>
    # We replace ONLY that first <Events /> inside the track's <ClipTimeable><ArrangerAutomation>
    pattern = r'(<ClipTimeable>\s*<ArrangerAutomation>\s*)<Events />'
    replacement = rf'\g<1><Events>{clip_xml}</Events>'
    new_xml, count = re.subn(pattern, replacement, track_xml, count=1)
    if count == 0:
        # Fallback: maybe ArrangerAutomation has Events on different format
        raise ValueError('Could not find empty <Events /> in ArrangerAutomation')
    return new_xml


def clone_track_with_offset(template_track_xml, id_offset, new_track_id):
    """Clone a MidiTrack XML with all internal IDs shifted by id_offset.

    Strategy: regex-replace `Id="N"` and `PointeeId Value="N"` and `<Track Value="N" />`
    references where N >= 10 (to avoid hitting LomId=0..9 which Live treats as enum).

    Then set the outer <MidiTrack Id="..."> to the new_track_id explicitly.
    """
    # Shift all Id="N" where N >= 10
    def shift_id(m):
        n = int(m.group(1))
        if n >= 10:
            return f'Id="{n + id_offset}"'
        return m.group(0)

    shifted = re.sub(r'Id="(\d+)"', shift_id, template_track_xml)

    # Shift PointeeId Value="N" where N >= 10
    def shift_pointee(m):
        n = int(m.group(1))
        if n >= 10:
            return f'PointeeId Value="{n + id_offset}"'
        return m.group(0)

    shifted = re.sub(r'PointeeId Value="(\d+)"', shift_pointee, shifted)

    # Shift <Track Value="N"/> references where N >= 10
    def shift_track_ref(m):
        n = int(m.group(1))
        if n >= 10:
            return f'<Track Value="{n + id_offset}"'
        return m.group(0)

    shifted = re.sub(r'<Track Value="(\d+)"', shift_track_ref, shifted)

    # Force outer track Id to the requested new_track_id (since it would be 13+offset by default)
    shifted = re.sub(
        r'<MidiTrack Id="\d+"',
        f'<MidiTrack Id="{new_track_id}"',
        shifted,
        count=1,
    )

    return shifted


# ===== Main build =====

TEMPLATE_PATH = '/home/user/Mix-Analyzer/ableton/projects/Template/Template Project/Template.als'
OUTPUT_PATH = '/home/user/Mix-Analyzer/ableton/projects/Banger_Cobain30_Reznor30_v1.als'


def main():
    print('=== Loading Template.als ===')
    with gzip.open(TEMPLATE_PATH, 'rb') as f:
        xml = f.read().decode('utf-8')
    print(f'Template XML: {len(xml)} chars')

    # Set tempo
    xml = set_tempo(xml, TEMPO)
    print(f'Tempo set to {TEMPO}')

    # Increase NextPointeeId well above all our offsets
    xml = re.sub(
        r'<NextPointeeId Value="\d+"',
        '<NextPointeeId Value="9999999"',
        xml,
        count=1,
    )
    print('NextPointeeId set to 9999999')

    # Build all 7 NoteBuilders
    builders = {
        'KICK': build_kick(),
        'SUB': build_sub(),
        'BASS RIFF': build_bass_riff(),
        'SNARE': build_snare(),
        'HATS': build_hats(),
        'LEAD': build_lead(),
        'PAD': build_pad(),
    }
    for name, nb in builders.items():
        print(f'  {name}: {len(nb.notes)} notes, {len(nb.by_pitch())} pitches')

    # === Modify track 12 → KICK ===
    s, e = find_track_xml(xml, 12)
    t12 = xml[s:e]
    t12 = rename_track(t12, 'KICK')
    t12 = set_track_color(t12, 0)
    clip_kick = build_midi_clip_xml('KICK', 0, builders['KICK'])
    t12 = inject_clip_into_track(t12, clip_kick)
    xml = xml[:s] + t12 + xml[e:]
    print('Track 12 → KICK injected')

    # === Modify track 13 → SUB ===
    s, e = find_track_xml(xml, 13)
    t13_template = xml[s:e]   # save BEFORE rename to use as clone source
    t13 = rename_track(t13_template, 'SUB')
    t13 = set_track_color(t13, 1)
    clip_sub = build_midi_clip_xml('SUB', 1, builders['SUB'])
    t13 = inject_clip_into_track(t13, clip_sub)
    xml = xml[:s] + t13 + xml[e:]
    print('Track 13 → SUB injected')

    # === Clone track 13 (template) for additional tracks ===
    clones_to_make = [
        ('BASS RIFF', 100000, 100013, 2),
        ('SNARE', 200000, 200013, 3),
        ('HATS', 300000, 300013, 4),
        ('LEAD', 400000, 400013, 5),
        ('PAD', 500000, 500013, 6),
    ]
    cloned_tracks_xml = []
    for name, offset, track_id, color in clones_to_make:
        clone = clone_track_with_offset(t13_template, offset, track_id)
        clone = rename_track(clone, name)
        clone = set_track_color(clone, color)
        clip = build_midi_clip_xml(name, color, builders[name])
        clone = inject_clip_into_track(clone, clip)
        cloned_tracks_xml.append(clone)
        print(f'Cloned track → {name} (Id={track_id}, offset={offset})')

    # Insert all cloned tracks RIGHT AFTER current track 13's </MidiTrack>
    # Find the end of track 13 in the modified xml
    s13, e13 = find_track_xml(xml, 13)
    inserted = '\n'.join(cloned_tracks_xml)
    xml = xml[:e13] + '\n' + inserted + xml[e13:]
    print(f'Inserted {len(clones_to_make)} cloned tracks after track 13')

    # === Save ===
    print(f'\nFinal XML: {len(xml)} chars')

    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUTPUT_PATH, 'wb', compresslevel=9) as f:
        f.write(xml.encode('utf-8'))
    size = Path(OUTPUT_PATH).stat().st_size
    print(f'Wrote {OUTPUT_PATH} ({size} bytes)')

    # Verification — first bytes after gunzip must be <?xml
    with gzip.open(OUTPUT_PATH, 'rb') as f:
        head = f.read(80)
    assert head.startswith(b'<?xml'), 'Double compression detected!'
    print('Verification: first bytes are <?xml — OK')

    # Re-parse to count tracks + clips + notes in output
    with gzip.open(OUTPUT_PATH, 'rb') as f:
        out_xml = f.read().decode('utf-8')
    tracks = re.findall(r'<(MidiTrack|AudioTrack|GroupTrack|ReturnTrack) Id="(\d+)"', out_xml)
    clips = len(re.findall(r'<MidiClip Id="\d+"', out_xml))
    notes = len(re.findall(r'<MidiNoteEvent ', out_xml))
    print(f'\n=== Output verification ===')
    print(f'Tracks: {len(tracks)}')
    for kind, tid in tracks:
        en = re.search(rf'<{kind} Id="{tid}".*?<EffectiveName Value="([^"]*)"', out_xml, re.DOTALL)
        name = en.group(1) if en else '?'
        print(f'  {kind} {tid}: "{name}"')
    print(f'MidiClips: {clips}')
    print(f'MidiNoteEvents: {notes}')


if __name__ == '__main__':
    main()
