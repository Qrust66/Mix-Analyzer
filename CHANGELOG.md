# Changelog

## [Unreleased — Phase 3 prep: Ableton catalog_loader] - 2026-04-27

### Added
- **`composition_engine/ableton_bridge/`** package — bridges blueprint
  decisions to Ableton .als manipulation. Phase 3 will add the actual
  Ableton-side agents; this commit lands the read-only catalog access.
- **`composition_engine/ableton_bridge/catalog_loader.py`** — sliced
  access to `ableton/ableton_devices_mapping.json` (~5500-line hand-curated
  catalog of 9 stock devices + 2 VST3 plugins + automation conventions
  + 9 known bugs from past sessions). Loading the full catalog into a
  device-config agent's prompt would cost ~15K tokens per invocation;
  the loader carves it into actionable slices:
    * `get_device_spec(name)` → just the spec for one device (Eq8,
      Compressor2, …) or VST3 plugin (Trackspacer, SmartLimit).
    * `get_automation_conventions()` → for the future automation-engineer.
    * `get_validation_rules()` → write_rules + validation + e2e checks.
    * `get_xml_pattern()` → universal XML-shape conventions every Ableton-
      side agent should be primed with.
    * `get_known_bugs(device=None)` → filtered or full list of past bugs
      to prime into agent prompts so we don't repeat them.
    * `get_ableton_conventions()`, `get_tempo_mapping()`, `get_meta()`.
  The master JSON file stays monolithic (8+ versions of hand-curation by
  the user); the loader is the layer that makes it agent-friendly.
- **`tests/test_ableton_catalog_loader.py`** — 16 tests covering caching,
  device list / VST3 list, slice accessors, case-insensitive bug filtering,
  unknown-device error path, integration smoke for a hypothetical
  eq-eight-config agent priming.

### Architecture decision
Per user feedback (memory: ableton_agent_partitioning), all future
Ableton-side agents must split concerns strictly: device-config agents
DO NOT touch automation; a single dedicated `automation-engineer` agent
handles all envelopes. The catalog_loader's accessor split mirrors this
partitioning so each agent receives only what its scope requires.

## [Unreleased — composition_engine Phase 2.3.1] - 2026-04-27

### Added
- **`composition_engine/music_theory.py`** — single source of truth for
  note name → pitch class / MIDI mapping. Exports `KEY_ROOTS` (frozenset
  of 17 valid note names), `note_to_pitch_class()`, `key_root_to_midi()`.
- **`tests/test_music_theory.py`** — 10 tests covering enharmonic pairs,
  unknown notes, MIDI conversion, defensive fallback.
- **`tests/conftest.py::complete_blueprint`** fixture — fully-filled
  7-sphere blueprint with provenance citations, used by test_director.py
  end-to-end tests.
- **`docs/COMPOSITION_WORKFLOW.md`** — concrete end-to-end example from
  brief + refs to .mid file, showing structure-decider → harmony-decider
  → manual fill of remaining spheres → composer.compose_to_midi.
  Documents the recommended invocation order and cross-sphere coherence
  invariants.

### Changed
- **`composition_engine/blueprint/composer_adapter.py`** now imports
  `key_root_to_midi` from `music_theory` instead of redefining the
  pitch-class table locally. The local symbol is kept as a thin
  re-export for backward compatibility.
- **`composition_engine/blueprint/agent_parsers.py`** now imports
  `KEY_ROOTS` from `music_theory` instead of `_VALID_KEY_ROOTS`. Single
  source of truth for the 17 valid note names — no more drift risk
  between code and test parametrize.
- **`tests/test_blueprint_agent_parsers.py`** — `test_harmony_all_valid_roots_accepted`
  now parametrizes over `sorted(KEY_ROOTS)` from music_theory instead
  of hardcoding the 17 names.
- **`tests/test_director.py`** — `_complete_blueprint()` helper removed;
  tests now consume `complete_blueprint` fixture from conftest.py.
- **`tests/test_blueprint_composer_adapter.py`** — `_minimal_blueprint()`
  helper removed; tests now consume `minimal_blueprint` fixture.

### Audit-fix summary
This release closes the 3 sérieuses critiques from the Phase 2.3 self-audit:
1. ✅ `minimal_blueprint` fixture now actually used (was orphan)
2. ✅ Two music-theory sources of truth merged into one (`music_theory.py`)
3. ✅ `KEY_ROOTS` shared between code and test parametrize

Plus the most actionable point #5: end-to-end workflow now documented.

## [Unreleased — composition_engine Phase 2.3] - 2026-04-27

### Added
- **`.claude/agents/harmony-decider.md`** — second sphere agent
  (harmony). Given a brief + reference songs, decides mode, key_root,
  progression, harmonic_rhythm, voicing_strategy, cadence_at_end.
  Reads `composition.harmonic_motion / modal_choice / harmonic_pacing /
  characteristic_riff_construction / key_area`. Includes 3 in-context
  examples (single ref, fusion of 2 refs, refusal payload) and a
  "Common pitfalls" section.
- **`parse_harmony_decision(payload)`** + companion
  `parse_harmony_decision_from_response(text)` in `agent_parsers.py`.
  Strict validation: `key_root` must be a canonical note name (one of
  17 letter+accidental combinations); `harmonic_rhythm` strictly > 0;
  `mode` non-empty.
- **`tests/conftest.py`** — shared `minimal_blueprint` fixture
  consolidating the 4-sphere setup that was duplicated across
  test_director.py, test_blueprint_composer_adapter.py, and
  test_blueprint_agent_parsers.py. Audit fix from Phase 2.2 self-review.

### Changed
- **Refactor `agent_parsers.py`** — extracted `_parse_envelope(payload,
  supported_versions)` to handle the cross-sphere fields (error path,
  schema_version, inspired_by, rationale, confidence). Each sphere's
  public parser now reduces to the 5-10 lines of sphere-specific
  validation. Avoids 6× duplication when the remaining 5 sphere agents
  land.

### Tests
- 18 new tests in `test_blueprint_agent_parsers.py` covering harmony
  parser: minimum-valid happy path, all 17 valid key_roots accepted, 6
  invalid key_root strings rejected, zero/negative harmonic_rhythm
  rejected, empty mode rejected, optional fields, default
  harmonic_rhythm, string coercion, error payload, end-to-end raw text
  → Decision.

## [Unreleased — composition_engine Phase 2.2.1] - 2026-04-27

### Added
- **`extract_json_payload(text)`** in `agent_parsers.py` — strips
  markdown fences, extracts JSON object from prose-wrapped LLM output.
  Real-world LLM agents occasionally produce ```json fences or prose
  preludes despite explicit instructions; the orchestrator-side parser
  now handles those cases gracefully.
- **`parse_structure_decision_from_response(text)`** — convenience
  one-shot for raw LLM text → `Decision[StructureDecision]`.
- **Schema versioning** — agent payloads now SHOULD include
  `"schema_version": "1.0"`. Parser warns (does not error) on missing
  or unknown versions to ease transition.
- **3 in-context examples** in `.claude/agents/structure-decider.md`
  (simple brief, multi-ref fusion, refusal) and a "Common pitfalls"
  section. Concrete examples are crucial for LLM agent reliability.

### Changed
- **Parser is now lenient on input, strict on output**:
    * `null` for `sub_sections` / `breath_points` → empty tuple
    * Integral floats (`16.0`) coerced to int for bar counts
    * Float `breath_points` (`[7.0, 15.0]`) coerced to ints
    * String numerics (`"0.85"`) coerced to float for confidence
    * `bool` explicitly rejected as int (Python's `isinstance(True, int)`
      is True, but musically a boolean is not a bar count)
- **Low confidence warning** — parser logs a WARNING when the agent
  returns `confidence < 0.5`, to surface fragile decisions early.

### Tests
- `tests/test_blueprint_agent_parsers.py` — 14 new tests covering
  fence-stripping, prose extraction, null coercion, float-to-int for
  bar counts, string-to-float for confidence, schema-version warning
  paths, end-to-end raw-text → Decision pipeline.

## [Unreleased — composition_engine Phase 2.2] - 2026-04-27

### Added
- **`.claude/agents/structure-decider.md`** — first sphere agent of the
  multi-agent composition system. Given a brief + reference songs,
  synthesizes a `Decision[StructureDecision]` JSON by reading
  `composition.structural_blueprint` and `section_count_and_lengths`
  from each reference via `song_loader`. Read-only.
- **`composition_engine/blueprint/agent_parsers.py`** — orchestrator-side
  parsers that validate and convert agent JSON payloads into typed
  `Decision[T]` objects. Phase 2.2 ships `parse_structure_decision()`;
  raises `AgentOutputError` on malformed payloads.

### Tests
- `tests/test_blueprint_agent_parsers.py` — 16 tests covering the happy
  path, all error paths (missing keys, wrong types, out-of-range
  confidence, agent-error refusal), and integration with
  `SectionBlueprint.with_decision()`.

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
