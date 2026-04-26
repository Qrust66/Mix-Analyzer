# Banger v2 — COMPOSITION SPEC

Documenté avant code, validé contre advisor. Key principle: every note placement
references a documented advisor recipe.

## Tempo & key
- BPM: **108** (`mid_tempo_aggression_not_hardcore_speed`)
- Key: **D minor Aeolian**, Phrygian inflection (Eb) in BREAKDOWN
- Time: **4/4** throughout (asymmetric implication via `syncopated_kick_creates_implied_meter_within_4_4`)
- Total: **64 bars / 2:22**
- End: **abrupt cut bar 64 beat 4** (`abrupt_song_end_no_fade`)

## 5 tracks (reduced from 7)
1. **DRUMS** — KICK(36) + SNARE(38) + HAT_CL(42) + HAT_OP(46) — single track Drum-Rack
2. **SUB** — D1 (26) drone (`drone_foundation_as_compositional_anchor`)
3. **BASS** — descending riff (`descending_riff_as_song_identity` + `robot_rock_hypnotic_repetitive_riff_with_micro_variations`)
4. **PAD** — modal voicings (`modal_voicings_above_drone_replace_chord_progression`)
5. **LEAD** — counter-melody (BREAKDOWN+DROP only)

## Sections (locked, with Live Locators)
| # | Name | Bars | Beat range | Active | Identity |
|---|------|------|-----------|--------|----------|
| 1 | INTRO | 1-4 | 0-15 | SUB | minimum-element, drone-alone |
| 2 | BUILD A | 5-12 | 16-47 | +BASS, +sparse KICK | density_arc start |
| 3 | VERSE A | 13-28 | 48-111 | +full DRUMS, +PAD Dsus2→Dm | unrelenting_aggression |
| 4 | BREAKDOWN | 29-36 | 112-143 | DRUMS DROP. SUB+PAD Phrygian+LEAD | hard_soft_hard contrast |
| 5 | VERSE B | 37-52 | 144-207 | full + LEAD continues | density returns |
| 6 | DROP | 53-60 | 208-239 | MAX. BASS octave-up. LEAD ascending | density-peak |
| 7 | OUTRO | 61-64 | 240-255 | strip to SUB+PAD only, cut bar 64.5 | abrupt_end |

## RHYTHMS (note patterns)

### KICK — syncopated_kick (NOT 4-on-floor)
Advisor pattern: "kick on 1, 1.75, 2.5, 3.25 across 4 beats" → 0-indexed beats: **{0.0, 0.75, 1.5, 2.25}** per bar.
Implies 3-against-4 polyrhythm.

| Section | Pattern |
|---------|---------|
| BUILD A | beat 0 only, every other bar (sparse) |
| VERSE A | full syncopated set every bar |
| VERSE B | same + ghost beat 3.5 every 4th bar |
| DROP | full + ghost beat 3.75 every bar (intensification) |
| OUTRO | drops out bar 61 |

### SNARE — backbeat
- VERSE A: beats 1 + 3 (1-indexed) = beat-position 1.0, 3.0
- VERSE B: + ghost beat 3.5 every 4 bars
- DROP: + 16th-note crescendo last bar (bar 60)

### HAT
- VERSE A: 8th-notes closed, velocity-accent on downbeat (108 / 64 / 80 / 64 / 80 / 64 / 80 / 64)
- VERSE B: 16th-note closed
- DROP last 4 bars: 32nd-notes for mania
- Open hat (46) on offbeat-end every 4 bars in VERSE A/B/DROP

## MELODIES (pitch patterns)

### BASS RIFF — descending_riff + robot_rock micro-variations
Base 1-bar motif: **D2 (38) → C2 (36) → Bb1 (34) → A1 (33)** at 1 note per beat.

Variations per 4-bar cycle (16 bars total per verse):

| Bar offset | Variation |
|-----------|-----------|
| +0 (base) | D2 C2 Bb1 A1 |
| +1 | base |
| +2 | base + D2 doubled on beat 1 (gate 50% then 50%) |
| +3 | base — last note OCTAVE UP (A1→A2=45) every 8 bars |

VERSE B specials:
- Bar 44: REVERSE pattern (A1 Bb1 C2 D2 ascending) — robot_rock "occasional different note"
- Bar 52: last note SUSTAINED into bar 53 (transition into DROP)

DROP variations (bars 53-60):
- Pattern: D2 C2 Bb1 A1 + octave-up doubling on beat 4 (A1+A2 stacked)
- Bar 60 final: D2+C2+Bb1+A1 all on beat 1 simultaneously (power-chord stack release)

### PAD — modal_voicings_above_drone
Advisor voicings used:
- **Dsus2**: D3(50) E3(52) A3(57)
- **Dm Aeolian**: D3(50) F3(53) A3(57)
- **Dm Phrygian**: D3(50) Eb3(51) A3(57)  ← dark modal shift in BREAKDOWN
- **Dsus4**: D3(50) G3(55) A3(57)
- **Dm7**: D3(50) F3(53) A3(57) C4(60)  ← outro resolution

Section assignment:
| Section | Voicing | Bars | Sustain duration |
|---------|---------|------|-----------------|
| BUILD A | Dsus2 | 5-12 | 32 beats sustain |
| VERSE A | Dm Aeolian | 13-28 | 64 beats |
| BREAKDOWN | Dm Phrygian (29-32) → Dsus4 (33-36) | 29-36 | 16+16 beats |
| VERSE B | Dm Aeolian | 37-52 | 64 beats |
| DROP | Dm + Bb stack (D-F-A + Bb-D-F = clusters Bb2+D3+F3+A3) | 53-60 | 32 beats |
| OUTRO | Dm7 sustained | 61-64 | 14 beats then cut |

### LEAD — counter-melody (BREAKDOWN + DROP only)

**BREAKDOWN** (bars 29-36): Phrygian chant
- A4(69) sustained 2 bars (29-30)
- Eb5(75) bar 31  ← Phrygian flat-2 inflection (advisor: dark-modal color)
- D5(74) bar 32
- C5(72) bar 33
- Bb4(70) bar 34
- A4(69) bar 35
- silence bar 36 (transition prep)

**DROP** (bars 53-60): ascending counter to descending bass
- 1 note per beat: A4 → Bb4 → C5 → D5 each bar
- Bars 53-56: ascending × 4 cycles
- Bars 57-60: doubled with D5 octave anchor every 2nd 8th — call/response pattern

### SUB DRONE
D1(26) sustained:
- bars 1-60 (continuous, single note sustained 240 beats)
- DROP (bars 53-60): octave layer D2(38) added — but D2 conflicts with BASS, instead use D0(14) deep-sub layer
- bar 61-64: D1 only, cut on bar 64 beat 4

## ADVISOR RECIPES MAPPED (banger checklist)

| Recipe | Where applied | Status |
|--------|--------------|--------|
| `mid_tempo_aggression_not_hardcore_speed` | 108 BPM | ✅ |
| `syncopated_kick_creates_implied_meter_within_4_4` | KICK pattern {0, 0.75, 1.5, 2.25} | ✅ NEW |
| `robot_rock_hypnotic_repetitive_riff_with_micro_variations` | BASS variations every 4 bars | ✅ NEW |
| `descending_riff_as_song_identity` | BASS D2-C2-Bb1-A1 | ✅ |
| `drone_foundation_as_compositional_anchor` | SUB D1 sustained 60 bars | ✅ NEW |
| `modal_voicings_above_drone_replace_chord_progression` | PAD Dsus2/Dm/Phrygian/Dsus4/Dm7 | ✅ NEW |
| `hard_soft_hard_contrast_within_song` | DRUMS drop in BREAKDOWN + Phrygian shift | ✅ |
| `density_arc_arrangement_sparse_to_wall` | INTRO 1 → BUILD 2 → VERSE 4 → BREAK 3 → VERSE 4 → DROP 5 → OUTRO 2 | ✅ |
| `programmed_drums_as_compositional_engine` | DRUMS Drum Rack | ✅ |
| `tr_909_drum_machine_as_compositional_instrument` | GM 909 pitches 36/38/42/46 | ✅ |
| `bass_line_first_compositional_method` | BASS designed first, drums respond to bass rhythm | ✅ |
| `compressed_economy_under_three_minutes_in_long_album` | 2:22 | ✅ |
| `abrupt_song_end_no_fade` | bar 64 beat 4 cut | ✅ |
| `industrial_textural_aggression_via_processed_guitar_layers` | LEAD synth in DROP (textural-aggression layer) | ✅ |
| `compositional_movement_via_filter_not_via_chord_change` | chord-stasis (Dm with modal shifts only) — filter automation user-side | 🟡 |
| `unrelenting_aggression_no_dynamic_arc` | DROP density max | ✅ |
| `rhythmic_emphasis_over_harmonic_movement_industrial_lesson` | rhythm-tracks density > harmonic | ✅ |
| `mingus_freedom_chromatic_harmony_inspiration` | Phrygian flat-2 inflection (Eb5) in BREAKDOWN — documented inspiration source | ✅ NEW |

**18 recipes integrated** (vs 13 in v1). v1 score: 96%. v2 design integrates 5 NEW recipes never used in v1.

## LIVE-SPECIFIC: Locator markers
Inject `<Locator>` elements at section boundaries so Arrangement view shows song structure:
- Beat 0: "INTRO"
- Beat 16: "BUILD A"
- Beat 48: "VERSE A"
- Beat 112: "BREAKDOWN"
- Beat 144: "VERSE B"
- Beat 208: "DROP"
- Beat 240: "OUTRO"

## Total note counts (estimated)
- DRUMS: ~600 notes (32 bars × ~20 hits/bar mid-density)
- SUB: 4 notes (sustained-4-bar segments)
- BASS: ~250 notes
- PAD: 35 notes (modal voicings sustained)
- LEAD: ~50 notes
**Total: ~940 notes** in 5 tracks (denser per-track than v1's 7-track distribution).
