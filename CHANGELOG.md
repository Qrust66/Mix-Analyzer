# Changelog

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
