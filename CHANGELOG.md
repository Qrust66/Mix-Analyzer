# Changelog

## [Unreleased — composition_engine Phase 2.1] - 2026-04-27

### Added
- **`composition_engine/blueprint/composer_adapter.py`** — wires a
  `SectionBlueprint` to the existing `composer.compose()` pipeline:
    * `key_root_to_midi(key_root, octave=3)` — note-name → MIDI pitch.
    * `blueprint_to_composition(bp)` — converts a blueprint to a
      `Composition` the composer can render. Maps the 4 essential spheres
      (structure, harmony, rhythm, arrangement); logs a warning when
      dynamics/performance/fx are filled but not yet wired.
    * `compose_from_blueprint(bp)` — convert + render to per-track note dict.
    * `compose_to_midi(bp, output_path)` — full pipeline ending in a `.mid`
      file on disk.
- **`composition_engine/blueprint/midi_export.py`** — pure-stdlib Standard
  MIDI File writer (Format 1, multi-track). No new dependency.
- **34/34 songs in `composition_advisor/inspirations.json`** now uniformly
  in Schema A v2 (with `stylistic_figures`). Includes the 9 original
  Nirvana/Soundgarden Schema A v1 entries harmonized in this pass.
- **`composition_advisor/inspirations.json`** split off from
  `composition_advisor.json` so the rules layer (theory, voice_leading,
  recipes_index, …) stays stable while the inspiration corpus grows.
- **25 reviewed song drafts** merged into `inspirations.json` (status
  `_REVIEWED_V1`).

### Changed
- **`composition_engine/advisor_bridge/song_loader.py`** — now merges
  rules + inspirations transparently. Public API unchanged; callers don't
  need to know about the file split.

### Tests
- `tests/test_blueprint_composer_adapter.py` — 13 tests (key mapping,
  partial-blueprint error path, layer-grouping, end-to-end pipeline).
- `tests/test_blueprint_midi_export.py` — VLQ encoding, MIDI chunk
  structure, velocity clamping, overlapping notes, end-to-end .mid output.

## [2.3.1] - 2026-04-15

### Fixed
- **tempo_bpm**: Individual tracks now show `N/A` instead of misleading `0.0`
  (tempo is not computed for individual tracks by design)
- **is_tonal**: Lowered tonal detection threshold from 1.8 to 1.3 so that
  bass, lead, pad, and vocal tracks are correctly marked `TRUE`
- **is_stereo**: Tracks with identical L/R channels (correlation >= 0.9999,
  width < 0.001) now show `FALSE (mono content)` instead of `TRUE`
- **tempo_bpm (Full Mix)**: Unreliable tempo values now display as
  `unreliable (was: X.X)` instead of raw number that could mislead AI

## [2.3.0] - 2026-04-15

### Added
- **PROJECT CONTEXT** section integrated at the top of AI Context sheet,
  organized as 4 horizontal blocks for visual separation:
    * Mix State (Rough/Final/etc.)
    * Master Plugins (active plugins on master bus)
    * Loudness Target (target LUFS for the release)
    * Style & Note (genre + free-form notes)

### Removed
- **Full Mix Context** sheet removed entirely. Its content is now part of
  AI Context sheet, eliminating redundancy and reducing sheet count by 1
  across all export modes.

### Changed
- `full` mode: 14 global sheets (was 15)
- `globals` mode: 14 global sheets (was 15)
- `ai_optimized` mode: 6 sheets (was 7), with Project Context data now
  in AI Context
- `build_ai_context_sheet()` now accepts `full_mix_info` parameter
- Index sheet: Full Mix Context no longer listed
- AI-optimized tooltip updated to reflect new sheet composition
- Version bump to v2.3

## [2.2.0] - 2026-04-15

### Added
- New **AI-optimized** Excel export mode — generates the smallest possible
  report containing only AI Context sheet and complementary global sheets
  (Anomalies, Full Mix Context, Mix Health Score, Freq Conflicts, AI Prompt).
  Excludes redundant or purely visual sheets to minimize token consumption
  during AI analysis.
- 3-way radio group selector in Analysis tab replaces the old checkbox:
  - `full`: all global sheets + one per track (complete report)
  - `globals`: all global sheets only, no individual tracks
  - `ai_optimized`: AI Context + essential data sheets only
- Coverage analysis documented in `_tmp/ai_context_coverage.md`

### Changed
- `generate_individual_sheets` BooleanVar replaced by `excel_export_mode`
  StringVar with values 'full' / 'globals' / 'ai_optimized'
- Backward compatibility property preserved for any code referencing
  `generate_individual_sheets`
- Old saved configs with `generate_individual_sheets` boolean are
  automatically migrated to the new `excel_export_mode` string
- Index sheet now only lists special sheets that are actually generated
  in the current export mode
- Navigation bar (`_xl_add_sheet_nav`) now accepts `nav_targets` parameter
  and adapts links per mode (excludes absent sheets)
- Excel report logging now includes export mode, sheets generated/skipped,
  and final file size
- Version bump to v2.2

## [2.1.0] - 2026-04-15

### Added
- New **AI Context** sheet in the Excel report — a dense, single-sheet 
  consolidation of all per-track metrics optimized for AI-assisted mix 
  conversations. Includes:
    - Header with generation date, track count, style
    - Anomaly codes legend (RES:, PHASE:, PEAK_HOT:, etc.)
    - Column legend (38 columns documented)
    - Track table: one row per Individual/BUS track + Full Mix row 
      with full loudness, spectral, stereo, tonal, and temporal metrics
    - Mix Health Score breakdown (reuses existing scoring engine)
    - Per-family aggregates (Drums, Bass, Synth, etc.) with mean, std, 
      and consensus dominant band
- AI Context sheet integrated with M7.5 navigation bar
- AI Context listed in Index sheet special links
- New `encode_anomalies()` helper for compact anomaly encoding
- New `docs/` folder with sheet specification and design prompt

### Changed
- Version bump: docstring aligned to v2.1 (UI was already at v2.0)

### Notes
- This sheet is additive only — all existing sheets remain unchanged
- AI Context and AI Prompt coexist (different purposes)
- Specification documented in `docs/ai_context_sheet_spec.md`
