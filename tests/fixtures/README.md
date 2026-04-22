# tests/fixtures/

## `reference_project.als`

Real Ableton Live project used as a fixture for Feature 1 tests
(`tests/test_cde_f1b.py` and later `test_cde_f1c.py`).

Sourced from `ableton/projects/Acid_Drops_Sections_TFP.als` — the Acid
Drops project on which the CDE was developed. Carries a realistic
spread of:

* ~38 audio tracks with TFP prefixes (`[H/R] Kick 1`, `[A/T] Ambience`,
  etc.) so `find_track_by_name` resolves them directly.
* Pre-existing `Peak Resonance` EQ8 devices on several tracks — used
  by `test_insertion_position_after_peak_resonance` to verify the
  anchor-based insertion path.
* A full set of section Locators (`Intro`, `Build 1`, `Drop 1`,
  `Chorus 1`, `Drop 2`, …) — needed by the section-locked gain
  envelope builder.
* Tempo 128 BPM, time signature 4/4.

## **Do not modify this file.**

Tests copy this fixture to `tmp_path` before mutating it. The copy is
discarded at the end of each test, so the original remains a pristine
reference. If the fixture ever needs updating (new Ableton version,
new mandatory XML block), replace it with a freshly re-exported
project rather than editing the existing file in place.

If you add a new `.als` fixture for a dedicated test scenario, name
it descriptively (e.g. `project_without_peak_resonance.als`) and
document its purpose in this README.
