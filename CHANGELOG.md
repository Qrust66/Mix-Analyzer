# Changelog

## [Unreleased — banque_bridge Bloc 0] - 2026-04-27

First step of the AGENT_DEPTH_ROADMAP. Adds a deterministic Python
interface to `ableton/banque_midi_qrust.xlsx` (10 sheets : drum
mapping, rhythm patterns, scales/modes, chord progressions, Qrust
profiles, velocity dynamics, tempo reference, bassline patterns,
notes usage). Without this loader, no agent can pick from the user's
hand-curated material library — they'd have to invent their own
notes / patterns / velocities, which is exactly today's 70/30 problem.

### Added — `composition_engine/banque_bridge/banque_loader.py`

Mirrors `song_loader` and `catalog_loader` patterns: cached load,
sliced read-only access. The .xlsx itself stays untouched.

API:
- `load_banque()` / `get_meta()`
- **Drums**: `get_drum_mapping()`, `get_drum_note_for_role(role)` — maps
  "kick" → 36, "snare" → 38, "hat" → 42, etc. via priority-ordered
  alias matching (kick principal beats sub kick)
- **Rhythm**: `list_rhythm_genres()`, `get_rhythm_pattern(genre, element)`,
  `parse_pattern_16(pattern)` — decodes "X...X...X...X..." into step events
- **Scales**: `list_scales()`, `get_scale(name)`, `list_qrust_starred_scales(min_stars)`,
  `parse_intervals(intervals_str)`
- **Chords**: `list_chord_progressions(mood=None)`
- **Profiles**: `list_qrust_profiles()`, `get_qrust_profile(name)` — full
  presets (tempo + scale + kick/snare/hat patterns + velocity range)
- **Velocity**: `get_velocity_range(style, element=None)`
- **Tempo**: `get_tempo_for_genre(genre)`, `list_tempo_genres()`
- **Bassline**: `list_basslines(style=None)`

### Tests — 30 in `tests/test_banque_loader.py`

Trip-wire invariants on the user's curation: expected sheet set, MIDI
35-64 drum range coverage, 16-char pattern format, all diatonic modes
present, Phrygien/Locrien/Phrygien-dominant rated 3-stars, Acid Drops
profile = 128 BPM Phrygien, etc. Any future user edit that breaks
loader assumptions surfaces immediately.

### Roadmap status

Bloc 0 (préalable bloquant) → ✅ shipped. Bloc 1 (contrat de
profondeur machine-vérifiable) is next.

## [Unreleased — mix_engine Phase 4.1] - 2026-04-27

First lane agent of the mix-side multi-agent system. Lands the
**diagnostic foundation**: every downstream mix agent consumes
mix-diagnostician's structured output instead of re-reading the .als
or the Excel report from scratch.

### Added — `.claude/agents/mix-diagnostician.md`

Reads a `.als` + a Mix Analyzer `.xlsx` report and produces a
`DiagnosticReport`:
- `full_mix` : LUFS / TP / crest / PLR / LRA / dominant_band /
  correlation / stereo_width / spectral_entropy
- `tracks` : per-track inventory (TrackInfo)
- `anomalies` : pre-classified by severity, with `suggested_fix_lane`
  hint per anomaly (routes to the right downstream lane)
- `health_score` : overall + breakdown per category
- `routing_warnings` : broken sidechain refs, stale routing targets

Read-only — observes, structures, surfaces. Makes no mix moves.
Symmetric to composition-side `structure-decider` (first sphere agent
of Phase 2.2).

### Added — schema in `mix_engine/blueprint/schema.py`

Activates the foundation types previously stubbed Phase 4.0 plus the
diagnostic-lane dataclasses:
- `MixCitation` (kind ∈ {diagnostic, device_mapping, manipulation_guide,
  pdf, user_brief, als_state})
- `MixDecision[T]` (provenance-carrying envelope, parallel to
  composition-side `Decision[T]`)
- `MixBlueprint` with immutable `with_decision(lane, decision)` and
  `filled_lanes()` API
- `TrackInfo`, `FullMixMetrics`, `Anomaly`, `HealthScore`, `DiagnosticReport`

### Added — parser in `mix_engine/blueprint/agent_parsers.py`

- `parse_diagnostic_decision(payload)` + companion
  `parse_diagnostic_decision_from_response(text)`. Strict validation:
    * Schema versioning (`SUPPORTED_DIAGNOSTIC_SCHEMA_VERSIONS`)
    * Track type ∈ `VALID_TRACK_TYPES` frozenset
    * Severity ∈ `VALID_ANOMALY_SEVERITIES` frozenset
    * Citation kind ∈ `VALID_CITATION_KINDS` frozenset
    * Range checks: pan ∈ [-1, 1], correlation ∈ [-1, 1], stereo_width
      ∈ [0, 1], health overall ∈ [0, 100], confidence ∈ [0, 1]
    * `health_score.breakdown` accepts both `{category, score}` objects
      and `[category, score]` pairs (lenient on input)
- `MixAgentOutputError` raised on contract violation, with a `where=...`
  pointer per the composition-side convention

### Tests
- `tests/test_mix_engine_schema.py` — 8 tests on dataclasses, MixBlueprint
  immutability, lane validation, single-source-of-truth invariant
- `tests/test_mix_engine_agent_parsers.py` — 39 tests : minimum-valid
  payload, all valid track_types parametrized, all valid severities
  parametrized, all valid citation kinds parametrized, range violations
  (pan/correlation/stereo_width/health/confidence), refusal payload,
  fences + prose support, blueprint integration, sidechain target
  text preservation

47/47 mix_engine tests pass. 832 total tests pass (composition-side
unchanged).

## [Unreleased — mix_engine Phase 4.0] - 2026-04-27

Foundation for the mix-side multi-agent system. **Architecture-only**
release: zero functional code, the rails are posed. Concrete agents
land Phase 4.1+ rule-with-consumer style, same discipline as the
composition engine's incremental sphere build-out.

### Added — design doc

- **`docs/MIX_ENGINE_ARCHITECTURE.md`** — Phase 4.0 North Star.
  Justifies the parallel module layout, defines `MixBlueprint` /
  `MixDecision[T]`, lays out the 12-lane DAG (mix-diagnostician →
  routing → corrective lanes → creative color → chain → automation →
  mastering → safety-guardian), specifies the 2-oracle pattern,
  enumerates the planned cohesion rules, sketches the hook integration
  points, and plans the gradual evolution of `ableton_devices_mapping.json`.

### Added — `mix_engine/` module skeleton

Parallel to `composition_engine/`. All files ship with docstrings only
(no implementation):
- `mix_engine/__init__.py`
- `mix_engine/blueprint/{__init__,schema,cohesion,agent_parsers,als_writer}.py`
- `mix_engine/director/{__init__,director}.py` — `MIX_DEPENDENCIES` DAG
  declared in full, ready to be consumed once concrete agents land
- `mix_engine/diagnostic/{__init__,excel_loader}.py` — read-only Excel
  report interface (skeleton)
- `mix_engine/README.md`

### Added — 2 Ableton-expertise oracles

The `.claude/agents/` family gains its first **oracle** pattern (active
LLM interface on top of curated documentation):

- **`device-mapping-oracle.md`** — fronts `ableton_devices_mapping.json`
  (5500 lines). Returns synthesized, citation-backed slices for any
  device/param query. Backed deterministically by the existing
  `catalog_loader.py`.
- **`als-manipulation-oracle.md`** — fronts `ALS_MANIPULATION_GUIDE.md`
  + `als_utils.py`. Returns step-by-step safe procedures for any .als
  operation, with the 5 canonical pitfalls cited inline.

Together with the existing `als-safety-guardian` they form the
**Ableton-expertise layer**: oracles teach before the action, guardian
validates after. Mix agents (Phase 4.1+) consult oracles instead of
re-loading raw JSON or markdown.

### Updated — hub

- `CLAUDE.md` references the new architecture doc + oracles
- `docs/CLAUDE_AGENTS.md` carries a complete agent hierarchy table
  (housekeeping × 4 / composition spheres × 7 / oracles × 2 / mix
  lanes × 12) plus full per-oracle entries

### Phase 4.1 cohort planned (not in this release)

1. `device-mapping-oracle` — wire it into a real query workflow
2. `mix-diagnostician` — produces the structured report all other
   mix agents consume
3. `eq-corrective-engineer` — first lane agent (Eq8 is the most
   thoroughly mapped device + most testable via Mix Analyzer)

Everything else (dynamics-corrective, automation-engineer, mastering,
…) lands when a real project demands it.

## [Unreleased — composition_engine Phase 2.6.1] - 2026-04-27

Audit-driven cleanup of the 4 high+medium weaknesses found in Phase 2.6.
Same pattern as Phase 2.5.1: weakness → force, with rule-with-consumer
discipline (constraints land in the parser that produces the values they
police, not in speculative cohesion rules).

### Changed — `parse_dynamics_decision` tightened

- **`inflection_points` must be strictly bar-ascending** (no duplicate
  bars). Out-of-order lists were silently accepted in Phase 2.6 — they
  would have been a latent bug as soon as Phase 3+ wires the velocity
  envelope, which assumes ordered timestamps. Sort-and-warn was rejected
  in favor of raise-on-violation: silent reordering hides upstream
  agent bugs.
- **Per-shape minimum inflection points** enforced:
    * `valley` → ≥ 1 inflection (sinon pas de creux)
    * `sawtooth` → ≥ 2 inflections (sinon pas de cycles)
    * Other shapes unchanged (well-defined by start/end/peak alone).
- **`start_db` / `end_db` now formally optional**, defaulting to the
  section baseline. Phase 2.6 had `dyn_dict.get(field, -12.0)` while
  the agent .md said the fields were required — contract divergence.
  Phase 2.6.1 aligns: parser accepts the omission and falls back to
  `DYNAMICS_BASELINE_DB`, agent .md documents this explicitly.

### Added — `DYNAMICS_BASELINE_DB` constant

The literal `-12.0` appeared in 6 places across `schema.py`,
`agent_parsers.py`, and `composer_adapter.py` (dataclass default,
parser fallbacks, composer "non-default?" check). Single source of
truth hoisted into `schema.py`; the schema is the canonical owner of
the dataclass default value. Both other modules import the constant.
Re-exported through `composition_engine.blueprint.__init__`.

Same anti-pattern Phase 2.4.1 fixed for `VALID_SUBDIVISIONS`. Today,
changing the baseline is one edit; before, it was six places to keep
in lockstep.

### Updated — `.claude/agents/dynamics-decider.md`

- Documents `start_db` / `end_db` as optional (default = baseline) — was
  silently optional in Phase 2.6, now formally so.
- Documents the strict ascending-bar requirement for `inflection_points`.
- Documents the per-shape minimum inflection count.
- Adds 3 new pitfalls to the "Pièges courants à éviter" section.

### Tests
- 9 new dynamics parser tests covering: constant equals dataclass
  default, missing start/end_db defaults to baseline, valley with 0
  inflections rejected / with 1 accepted, sawtooth with 1 rejected /
  with 2 accepted, unsorted bars rejected, duplicate bar rejected,
  sorted happy path.

### Audit fixes — 4 weaknesses → 4 forces

| Phase 2.6 weakness | Phase 2.6.1 force |
|---|---|
| ① 4/7 arc_shapes not validated | Per-shape min inflection enforced (parser raises) |
| ② inflection_points unsorted accepted | Strict ascending-bar check (parser raises) |
| ③ Magic -12.0 in 6 places | `DYNAMICS_BASELINE_DB` exported, used everywhere |
| ④ start/end_db default divergence | Agent .md + parser aligned: optional, default = baseline |

The remaining 3 lower-severity weaknesses (peak/inflection collision,
pre-existing test_raises_on_wrong_type_for_total_bars failure, warning
noise on multi-section composition) are deferred — they don't justify
a release of their own and will land when Phase 3+ wires dynamics to
real velocity envelopes.

## [Unreleased — composition_engine Phase 2.6] - 2026-04-27

Adds **dynamics-decider**, the 5th sphere agent. Phase 2.6 ships fully
wired parsing + cohesion guard rails, but the resulting decisions remain
**descriptive** at the MIDI rendering layer — `composer_adapter` now logs
a WARNING when `dynamics` contains non-default values, identical pattern
to Phase 2.4.1's rhythm warning. Phase 3+ will wire the arc to a per-note
velocity envelope.

### Added — `.claude/agents/dynamics-decider.md`

5th sphere agent. Decides:
- `arc_shape` ∈ {flat, rising, descending, valley, peak, exponential, sawtooth}
- `start_db`, `end_db` (float ∈ [-60.0, 0.0], baseline = 0)
- `peak_bar` (Optional[int] ∈ [0, total_bars), required when `arc_shape="peak"`)
- `inflection_points` (list of `[bar, db]` pairs)

Reads `arrangement.dynamic_arc_overall`, `stylistic_figures.climax_moments`,
`stylistic_figures.transitions_between_sections`,
`composition.harmonic_pacing` from references (optionally `tension_release.*`
from rules layer). Includes 4 in-context examples (rising/Pyramid_Song,
sawtooth/March_Of_The_Pigs, flat/Veridis_Quo, refusal).

### Added — Parser in `agent_parsers.py`

- **`parse_dynamics_decision(payload)`** + companion
  `parse_dynamics_decision_from_response(text)`. Strict validation:
    * `arc_shape` must be in `VALID_ARC_SHAPES` frozenset
    * `start_db`, `end_db` ∈ [-60.0, 0.0] (`DB_MIN`/`DB_MAX`)
    * Cross-field consistency: rising → end > start, descending → end < start,
      flat → equal
    * `arc_shape="peak"` requires non-null `peak_bar`
    * `peak_bar` ≥ 0 (cohesion rule enforces upper bound)
    * `inflection_points` accepts both `[bar, db]` pairs and `{bar, db}` objects
- **Public constants**: `SUPPORTED_DYNAMICS_SCHEMA_VERSIONS`,
  `VALID_ARC_SHAPES`, `DB_MIN`, `DB_MAX`. Single source of truth between
  parser, tests, and any future cohesion rule that needs them.

### Added — Cohesion rule `dynamics_within_structure_bounds`

(severity: BLOCK) Rejects `peak_bar` outside `[0, total_bars)` or any
`inflection_points[*].bar` outside `[0, total_bars]`. Fires only when
both `structure` and `dynamics` are filled. Even though dynamics is
currently descriptive at the renderer, out-of-bounds bars are nonsensical
regardless and would silently misrepresent the section if/when wired.

### Added — Composer warning for non-default dynamics

`compose_from_blueprint` now logs a WARNING listing the dynamics fields
when `arc_shape != "flat"`, levels deviate from defaults, or peak/inflections
are present. Mirrors the Phase 2.4.1 rhythm warning pattern (descriptive-only
fields surface their non-application explicitly).

### Tests
- ~20 new dynamics parser tests in `test_blueprint_agent_parsers.py`
  (all `VALID_ARC_SHAPES` parametrized, dB range edges, cross-field
  consistency rules, peak_bar required for `arc_shape="peak"`,
  inflection_points list/dict input shapes, blueprint integration, error
  payload, fences).
- 6 new cohesion tests in `test_blueprint_cohesion.py` covering peak_bar
  bounds, inflection_points bounds, peak_bar=None case, boundary
  (bar == total_bars allowed for inflection).
- Sanity test renamed from `test_phase251_ships_concrete_rules` to
  `test_concrete_rules_registered` and updated to assert 4 production rules.

## [Unreleased — composition_engine Phase 2.5.1] - 2026-04-27

Transforms the 5 self-audit weaknesses of Phase 2.5 into active guard
rails. First concrete cohesion rules in the project — they land
**alongside the agent that produces the values they constrain**, per
the project's "rule-with-consumer" principle (Phase 1 cleanup retired
all speculative rules; these are the first earned ones).

### Added — 3 concrete cohesion rules in `cohesion.py`

These fire only when both `structure` and `arrangement` spheres are
filled (silently skip otherwise, per the partial-blueprint discipline):

- **`arrangement_layers_within_structure_bounds`** (severity: BLOCK)
    Rejects layers that overflow the section: `exits_at_bar > total_bars`
    or `enters_at_bar < 0` or `enters_at_bar >= total_bars` (latter
    means the layer never becomes active).
- **`instrumentation_changes_within_structure_bounds`** (severity: BLOCK)
    Rejects `inst_change.bar` outside `[0, total_bars]` — invisible to
    the renderer.
- **`arrangement_coverage_check`** (severity: WARN)
    Surfaces sections where more than half the bars have zero active
    layers. Sometimes intentional (compositional rest), so it warns
    rather than blocks.

### Added — Public canonical roles + warnings in composer_adapter

- **`KNOWN_LAYER_ROLES`** frozenset exposed in `composer_adapter.py`:
    `{drum_kit, perc, bass, sub, lead, vocal, pad, fx}`. Layers with
    role outside this set fall through to `_default_motif` (tonic
    only) but the adapter now logs a WARNING listing the unknown roles
    and the canonical set.
- **Warning when arrangement-side fields are descriptive-only** —
    `density_curve != "medium"`, non-empty `instrumentation_changes`,
    or non-empty `register_strategy` trigger a WARNING explaining
    they're not yet wired to MIDI rendering. Same pattern as Phase 2.4.1
    did for rhythm fields.

### Tests
- 11 new test functions in `test_blueprint_cohesion.py`:
    * `test_phase251_ships_concrete_rules` — sanity invariant on the
      registered rules
    * 4 tests for `arrangement_layers_within_structure_bounds` (within
      bounds passes, exits past blocks with helpful message, negative
      enters blocks, enters >= total_bars blocks)
    * 2 tests for `instrumentation_changes_within_structure_bounds`
    * 4 tests for `arrangement_coverage_check` (full cov passes, 12/16
      silent warns, exactly half does NOT warn — boundary, overlapping
      layers count once)

### Audit fixes — 5 weaknesses → 5 forces

| Phase 2.5 weakness | Phase 2.5.1 force |
|---|---|
| ① Cross-sphere bounds not enforced | BLOCK rule via cohesion |
| ② density_curve descriptive-only | WARN at composer_adapter |
| ③ role free-string fallback silent | WARN + KNOWN_LAYER_ROLES public |
| ④ Coverage gaps unsignaled | WARN rule via cohesion |
| ⑤ Test count imprecise | (deferred — count varies with parametrize) |

## [Unreleased — composition_engine Phase 2.5] - 2026-04-27

### Added
- **`.claude/agents/arrangement-decider.md`** — fourth sphere agent
  (arrangement). **THE ONLY SPHERE WHOSE DECISIONS PRODUCE AUDIBLE
  CHANGES IN THE RENDERED MIDI** (composer_adapter consumes
  `arrangement.layers` directly to build the per-track MIDI). The
  other 3 wired sphere (structure/harmony/rhythm) only contribute
  total_bars / tonic_pitch / tempo_bpm to the renderer; arrangement
  is what determines which voices play and when.
- **`parse_arrangement_decision(payload)`** + companion
  `parse_arrangement_decision_from_response(text)` in agent_parsers.py.
  Strict validation:
    * `layers` MUST be non-empty (a section with no layers cannot be
      rendered to MIDI)
    * each layer: `enters_at_bar >= 0`, `exits_at_bar > enters_at_bar`,
      `base_velocity ∈ [0, 127]`, `role` non-empty
    * `density_curve` ∈ {sparse, medium, dense, build, valley, sawtooth}
    * `instrumentation_changes[*].bar >= 0`
- **Public constants** `VALID_DENSITY_CURVES`, `VELOCITY_MIN`,
  `VELOCITY_MAX` exposed via `__all__` per the Phase 2.4.1 single-source-
  of-truth pattern. Test parametrize imports them — no drift between
  code and tests.

### Tests
- 19 new test functions in `test_blueprint_agent_parsers.py` covering
  arrangement parser. Parametrize tests (density_curves, velocities)
  anchor on the public constants. Notably:
    * `test_arrangement_layers_must_be_non_empty` — the only sphere
      where empty is rejected
    * `test_arrangement_all_valid_density_curves_accepted` — auto-syncs
      with VALID_DENSITY_CURVES
    * `test_arrangement_layers_with_overlapping_roles_kept_separate` —
      multiple bass voices stay distinct, composer groups them downstream

### End-to-end pipeline verified
Smoke test:
```
4 spheres filled → compose_to_midi() →
  1141-byte Format-1 MIDI, 5 tracks (1 tempo + 4 instrument tracks)
  for layers [drum_kit(0-16), bass(4-16), pad(0-16), lead(8-16)]
```
Different arrangement decisions now yield different MIDI files.

### Status after Phase 2.5
4/7 sphere agents wired: structure, harmony, rhythm, **arrangement**.
Remaining: dynamics (Phase 2.6), performance (Phase 2.7), fx (Phase 2.8).

## [Unreleased — composition_engine Phase 2.4.1] - 2026-04-27

Closes 4 critiques from the Phase 2.4 self-audit:

### Changed
- **`agent_parsers.py`** — renamed `_VALID_SUBDIVISIONS`, `_TEMPO_MIN_BPM`,
  `_TEMPO_MAX_BPM` to public `VALID_SUBDIVISIONS`, `TEMPO_MIN_BPM`,
  `TEMPO_MAX_BPM` and added them to `__all__`. Single source of truth —
  the test parametrize now imports them instead of re-hardcoding the
  values. Same fix as Phase 2.3.1 did for `KEY_ROOTS`. Audit critique #1.

- **`tests/test_blueprint_agent_parsers.py`** — `test_rhythm_valid_subdivisions_accepted`
  now parametrizes over `sorted(VALID_SUBDIVISIONS)`. Boundary tests
  expanded: tempo invalid set now covers negatives + `TEMPO_MIN_BPM-1`
  + `TEMPO_MAX_BPM+1` + absurd; tempo valid set anchors to the actual
  bounds. Subdivisions invalid set covers negatives + below-floor +
  non-power-of-2 + above-ceiling.

### Fixed
- **`compose_from_blueprint` warning** when rhythm-sphere fields are
  set to non-default values (time_signature ≠ "4/4", non-empty
  drum_pattern, subdivisions ≠ 16, swing ≠ 0.0, non-empty polyrhythms).
  The composer pipeline currently hardcodes 4/4 + 16th grid + zero
  swing in track_layerer + motif renderers, so these blueprint fields
  are descriptive only at Phase 2.4. The warning surfaces this so users
  don't silently get a 4/4 .mid from a 10/4 blueprint. Audit critique #2.

- **`.claude/agents/rhythm-decider.md`** — added a 4th in-context
  example demonstrating multi-ref fusion (Daft_Punk/Veridis_Quo +
  Nine_Inch_Nails/March_Of_The_Pigs combined into a 110 BPM electronic
  groove with industrial accent dynamics). Pedagogical parity with
  structure-decider and harmony-decider, both of which had a fusion
  example. Audit critique #4.

- **CHANGELOG count** — Phase 2.4 entry said "23 new tests". Actual
  count is **17 test functions** which generate **47 cases** when the
  parametrize expansions are counted. Phase 2.4.1 adds 0 net functions
  but expands several parametrize sets (boundary tests). Audit
  critique #3.

## [Unreleased — composition_engine Phase 2.4] - 2026-04-27

### Added
- **`.claude/agents/rhythm-decider.md`** — third sphere agent (rhythm).
  Given a brief + reference songs, decides tempo_bpm, time_signature
  (including asymmetric meters like "16/8 with 3+3+4+3+3 internal
  grouping"), drum_pattern (prose), subdivisions, swing, polyrhythms.
  Reads `performance.tempo_feel_description / drum_style`,
  `tempo_bpm_documented_range`, `time_signature`,
  `composition.phrase_symmetry`, `stylistic_figures.special_effects_*`
  from inspirations.json. Includes 3 in-context examples (single ref,
  asymmetric meter signature, refusal payload) and a "Common pitfalls"
  section.
- **`parse_rhythm_decision(payload)`** + companion
  `parse_rhythm_decision_from_response(text)` in `agent_parsers.py`.
  Strict validation:
    * `tempo_bpm` ∈ [40, 300] (out-of-range = almost certainly LLM bug)
    * `subdivisions` ∈ {4, 8, 16, 32, 64} (powers of 2)
    * `swing` ∈ [0.0, 1.0) — half-open interval, exactly 1.0 rejected
    * `time_signature` non-empty (defaults to "4/4" if blank)

### Tests
- 23 new tests in `test_blueprint_agent_parsers.py` covering rhythm
  parser: minimum-valid happy path, asymmetric meter accepted, optional
  fields, 5 invalid tempos rejected, 7 valid tempos accepted, 9 invalid
  subdivisions rejected, 5 valid subdivisions accepted, 4 invalid swing
  values rejected, 6 valid swing values accepted, string coercion for
  tempo and swing, polyrhythms list shape, error payload, raw-text →
  Decision via *_from_response.

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
