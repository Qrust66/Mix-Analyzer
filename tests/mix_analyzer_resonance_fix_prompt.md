# Mix Analyzer — Fix: Resonance anomaly detection false positives

## Context

Mix Analyzer is a Python desktop tool (`mix_analyzer.py`, single file, 8323 lines, version 1.6) that analyzes audio bounces from Ableton Live and produces diagnostic PDF/Excel reports. The tool is used by a music producer to drive mix and mastering decisions on industrial/electronic music projects.

This task fixes a specific bug in the resonance anomaly detection that generates false positives on tracks with naturally concentrated spectra (percussive instruments with tonal modes, claps, filtered synths), while simultaneously missing real resonance anomalies on wideband content.

**Target file**: `mix_analyzer.py` (root of the repo)
**Target version**: bump to **v1.6.1** (patch release, no feature addition, bug fix only)
**Scope**: surgical — one function modified, one new function added, constants section added. No refactoring, no behavior change outside resonance anomaly detection.

---

## The bug in detail

### Current algorithm (lines 447-454 of `mix_analyzer.py`, inside `analyze_spectrum()`)

```python
spectrum_db = db(spectrum_mean / (np.max(spectrum_mean) + 1e-12))
peaks, properties = signal.find_peaks(spectrum_db, height=-20, distance=20, prominence=6)
peak_freqs = freqs[peaks][:8]
peak_heights = spectrum_db[peaks][:8]
peak_list = sorted(
    [(float(f), float(h)) for f, h in zip(peak_freqs, peak_heights)],
    key=lambda x: x[1], reverse=True
)[:6]
```

### Current anomaly rule (lines 777-781, inside `detect_anomalies()`)

```python
# Strong resonance peaks
strong_peaks = [p for p in S['peaks'] if p[1] > -3 and p[0] > 100]
if len(strong_peaks) >= 2:
    freqs_str = ', '.join(f"{p[0]:.0f}Hz" for p in strong_peaks[:3])
    anomalies.append(('warning', f"Strong resonance peaks detected at: {freqs_str}"))
```

### Why it's broken

Line 447 normalizes the spectrum to its **global maximum** (`spectrum / max(spectrum)`). Line 778 then flags peaks that fall **within 3 dB of that global max**. This creates two symmetric failure modes:

1. **False positives on narrow-spectrum tracks.** A percussion sound with tonal modes at, say, 2500 Hz and 3800 Hz has its global spectral max at one of those modes. The other mode is naturally within 3 dB of the first. The algorithm flags these as "strong resonance peaks" — but they are not resonance *anomalies*, they are the instrument's natural timbre. No amount of EQ surgery by the mix engineer fixes this warning, because the warning is not describing a fixable problem.

2. **False negatives on wideband tracks.** A synth with wideband content and a real narrow resonance at 1500 Hz has its global spectral max elsewhere (spectral centroid of the broadband content). The 1500 Hz resonance sits 10-20 dB below that global max and never meets the `> -3 dB` criterion. The algorithm misses the real anomaly.

The core issue: **the algorithm uses a global reference (max of spectrum) when it should use a local reference (contour around the peak)**. A resonance anomaly is a peak that is spiky relative to its *immediate neighborhood*, not relative to the loudest feature of the whole spectrum.

### Secondary issue: frequency floor

Line 778 also excludes peaks below 100 Hz (`p[0] > 100`). This is a sensible exclusion for sub-bass rumble but it is too aggressive for industrial/electronic music where kick drums and bass instruments have meaningful spectral content in the 60-100 Hz range. The floor should be lowered to 60 Hz (the lower boundary of the "Bass" band in `FREQ_BANDS`).

---

## Multi-phase execution protocol

**This task is split into 3 phases.** Each phase has explicit deliverables and a **STOP point** where you must wait for user confirmation before proceeding to the next phase. Do not chain phases automatically. After each phase, produce the required summary message and then halt.

The phases are:
- **Phase 1** — Scaffold (structure + placeholder function, no algorithmic logic)
- **Phase 2** — Algorithm implementation + fixture validation
- **Phase 3** — Harness script + regression check + versioning + final summary

Each phase has its own Git commits on the same feature branch.

**Branch name**: `fix/resonance-detection-v1.6.1`

Create the branch at the start of Phase 1:
```
git checkout main
git pull
git checkout -b fix/resonance-detection-v1.6.1
```

Do not merge to `main` at any point. The branch stays open for user review after all three phases are complete.

---

## Design principle (applies to all phases)

**Keep both algorithms.** The existing `analyze_spectrum()` function still produces `peak_list` as a *descriptive* feature of the spectral contour. It remains unchanged and continues to feed the PDF report, the Excel report, and any other consumer. This is a descriptive output, not a prescriptive one, and it is useful as-is.

**Add a new prescriptive function** `detect_resonance_anomalies(spectrum_mean, freqs, sr)` that uses a local-contour-comparison approach and is used **only** in the anomaly detection pipeline (lines 777-781). The result: the same track can have rich "peaks" in its descriptive report while correctly reporting zero anomalies in its prescriptive warning list.

---

## Phase 1 — Scaffold

### Goal

Put the structure in place without changing any behavior yet. At the end of Phase 1, Mix Analyzer runs and produces reports that are identical to v1.6 **except that the resonance anomaly warning never fires** (because the new function is a placeholder that returns an empty list).

### Tasks

1. **Add the constants section** near the top of `mix_analyzer.py`, before the first function definition:

   ```python
   # ============================================================================
   # Resonance anomaly detection (v1.6.1)
   # ============================================================================
   # These constants control the detection of abnormal resonance peaks in the
   # anomaly report. They do NOT affect the descriptive spectral peak list shown
   # in the PDF reports — that uses a separate algorithm in analyze_spectrum().
   #
   # Tune these if the resonance warnings in your reports are too sensitive
   # (too many false positives) or too lax (missing obvious ringing).

   # Width of the local spectral contour window, in octaves on each side of the
   # target frequency. A peak is compared to the spectral average over
   # [f / 2^W, f * 2^W]. Smaller = more sensitive to narrow spikes, larger = only
   # flags isolated peaks.
   #   Recommended: 1/3 octave (matches audio engineering conventions and
   #   roughly corresponds to a parametric EQ with Q=4-6).
   RESONANCE_LOCAL_WINDOW_OCTAVES = 1.0 / 3.0

   # Minimum dB by which a peak must rise above its local contour to be flagged
   # as a resonance anomaly. +9 dB corresponds to "clearly audible and typically
   # problematic". +6 dB is the threshold of musical/natural emphasis. +12 dB is
   # conservative (only extreme ringing).
   RESONANCE_MIN_EXCESS_DB = 9.0

   # Minimum absolute level (in dB relative to the spectrum's peak) for a bin
   # to be eligible as a resonance candidate. This filters out noise-floor
   # artifacts and near-silent regions where small excess values are not
   # audibly meaningful.
   RESONANCE_MIN_ABSOLUTE_DBFS = -50.0

   # Lower frequency floor for resonance detection. Below this, peaks are
   # considered either sub-bass rumble or fundamental frequencies of bass
   # instruments (not anomalies). 60 Hz matches the lower boundary of the
   # "Bass" band in FREQ_BANDS.
   RESONANCE_MIN_FREQ_HZ = 60.0

   # Maximum number of anomalous peaks reported per track. If more peaks are
   # detected, only the top N (highest excess_db) are reported. If a track has
   # more than this many true resonances, it has a structural problem that
   # requires manual inspection rather than band-by-band EQ surgery.
   RESONANCE_MAX_REPORTED_PEAKS = 3

   # Minimum number of anomalous peaks required to raise a warning. With 1
   # isolated peak, a track usually just has one corrective cut to make. The
   # warning is meant to signal tracks with multiple concurrent issues.
   RESONANCE_MIN_PEAKS_FOR_WARNING = 2
   # ============================================================================
   ```

2. **Add the placeholder function** anywhere near `analyze_spectrum()` in the file:

   ```python
   def detect_resonance_anomalies(spectrum_mean, freqs, sr):
       """
       Detect peaks in the spectrum that rise significantly above their LOCAL
       spectral contour.

       Returns a list of (freq_hz, excess_db) tuples, sorted by excess_db
       descending, truncated to RESONANCE_MAX_REPORTED_PEAKS entries. Empty
       list if no anomalous peaks found.
       """
       # Phase 1 placeholder — algorithm will be implemented in Phase 2.
       return []
   ```

3. **Extend `analyze_spectrum()` return dict**: add `'sr': sr` to the returned dictionary. This is the only permitted change to `analyze_spectrum()`. Do not touch anything else in that function.

4. **Replace lines 777-781 in `detect_anomalies()`** with the new call pattern:

   ```python
   # Strong resonance peaks (v1.6.1: local-contour-based detection)
   resonance_peaks = detect_resonance_anomalies(
       S['spectrum_mean'], S['freqs'], S['sr']
   )
   if len(resonance_peaks) >= RESONANCE_MIN_PEAKS_FOR_WARNING:
       freqs_str = ', '.join(f"{p[0]:.0f}Hz" for p in resonance_peaks)
       anomalies.append(('warning', f"Strong resonance peaks detected at: {freqs_str}"))
   ```

5. **Verify the tool still runs**. Open `mix_analyzer.py` with `python -c "import mix_analyzer"` (or equivalent smoke test) to confirm no syntax errors or import errors. Do not run a full analysis yet.

### Commits for Phase 1

Three commits, in order:

1. `fix(resonance): add tunable constants section at top of mix_analyzer.py`
2. `fix(resonance): add placeholder detect_resonance_anomalies() and pass sr through spectrum dict`
3. `fix(resonance): replace legacy anomaly detection block with new function call`

Push the branch to origin at the end of Phase 1.

### Phase 1 output — required

Produce a summary message with:

1. **Files touched** — should be exactly `mix_analyzer.py`.
2. **Constants added** — confirm the 6 constants are at the top of the file with their default values.
3. **Placeholder function** — confirm the function exists and returns `[]`.
4. **`analyze_spectrum()` change** — confirm only `'sr': sr` was added to the return dict, nothing else touched.
5. **Anomaly block replacement** — show the diff (before/after) of lines 777-781.
6. **Smoke test result** — confirm the file imports without error.
7. **Branch name** — `fix/resonance-detection-v1.6.1`
8. **Commit log** — list the 3 commits pushed.

Then **STOP**. Wait for the user to confirm "proceed to Phase 2" before starting Phase 2. Do not chain.

---

## Phase 2 — Algorithm implementation & fixture validation

### Goal

Replace the placeholder function body with the real algorithm, and validate against 9 test fixtures. At the end of Phase 2, running the detection on the 9 fixtures gives 9/9 correct verdicts.

### Tasks

#### 2.1 Implement `detect_resonance_anomalies()`

Replace the placeholder body with a real implementation following this algorithm:

**Algorithm**:

1. Convert `spectrum_mean` to a dB scale. Use `20 * log10(spectrum_mean / max(spectrum_mean))` so the peak of the spectrum is 0 dB and everything else is negative. This gives a **relative dB scale** — the algorithm cares about *differences* from the local baseline, not absolute levels.

2. Compute a smoothed **local contour** by computing, for each frequency bin, a statistic over the neighborhood `[f / 2^W, f * 2^W]` where `W = RESONANCE_LOCAL_WINDOW_OCTAVES`. Because FFT bins are linearly spaced but octaves are logarithmic, the window width in bins depends on the frequency: at 100 Hz it spans ~40 Hz, at 10 kHz it spans ~4000 Hz.

   **Use the median of the neighborhood**, not the mean. The median is robust to the presence of the peak itself contaminating its own baseline — a sharp peak contributes one sample to its neighborhood but does not shift the median significantly. The mean would be pulled up by the peak.

   Precompute `(bin_low, bin_high)` indices for each target bin in a single pass before iterating. This avoids recomputing octave boundaries 4000+ times.

   **Edge handling**: at frequencies near the low edge (60-80 Hz) and high edge (>15 kHz), the window may extend outside the spectrum range. Clip the window to valid bins. Do not pad with zeros (that would bias the contour downward).

3. Compute `excess[f] = spectrum_db[f] - contour[f]` for every frequency bin. This is "how many dB above the local baseline this bin sits".

4. Find peaks in the `excess` array using `scipy.signal.find_peaks` with minimum height equal to `RESONANCE_MIN_EXCESS_DB`. Also require minimum absolute level so we ignore noise-floor artifacts: a peak must also satisfy `spectrum_db[f] >= RESONANCE_MIN_ABSOLUTE_DBFS`.

5. Apply the frequency floor: exclude peaks with `freqs[f] < RESONANCE_MIN_FREQ_HZ`.

6. Sort resulting peaks by `excess_db` descending, keep top `RESONANCE_MAX_REPORTED_PEAKS`.

7. Return the list of `(freq_hz, excess_db)` tuples.

**Performance note**: the median-over-variable-window computation must handle 4097 frequency bins (8192 FFT / 2 + 1) efficiently. If computing the median from scratch for each bin is too slow (> 200 ms per track), fall back to mean-with-central-suppression: exclude the ± 2 bins around each target bin from the average. Document the fallback choice in a code comment.

#### 2.2 Run fixture validation

The validation fixtures are in the repository at `Test/resonance_fixtures/`.

**CRITICAL — repository hygiene instructions**:

- The `Test/` folder at the repository root **contains pre-existing files from prior test phases**. **Do not delete, move, or modify** any of those pre-existing files.
- Work **only** with the files in the subfolder `Test/resonance_fixtures/`, which contains 9 `.wav` files plus one `fixtures_metadata.json`.
- **Do not add new files to `Test/` outside of `resonance_fixtures/`**. Any temporary scripts or debug output generated during Phase 2 exploration should go in a transient folder (e.g., `/tmp/` or a gitignored `_tmp/` at repo root) and **must not be committed**.

**Fixture inventory**:

| # | File | Expected | Purpose |
|---|---|---|---|
| 01 | `01_flat_wideband.wav` | 0 | Negative control — no peaks above contour |
| 02 | `02_wideband_one_resonance_500hz.wav` | 1 @ 500 Hz | True resonance that old algo misses |
| 03 | `03_wideband_three_resonances.wav` | 3 @ 500, 1500, 4000 Hz | Multiple true resonances |
| 04 | `04_spoon_percussion_no_anomaly.wav` | 0 | **Canonical false positive case** — old algo flags 3, new algo must flag 0 |
| 05 | `05_spoon_percussion_with_real_anomaly.wav` | 1 @ 1200 Hz | Narrow-spectrum track with one real anomaly added |
| 06 | `06_sub_bass_80hz_resonance.wav` | 1 @ 80 Hz | Tests new 60 Hz frequency floor |
| 07 | `07_mild_resonance_below_threshold.wav` | 0 | +6 dB mild peak below +9 dB threshold |
| 08 | `08_cluster_close_resonances.wav` | 3 @ 800, 900, 1000 Hz | Tests moving-average window width |
| 09 | `09_realistic_mix_one_anomaly.wav` | 1 @ 2500 Hz | Realistic mix: kick + bass + synth + hi-hat, one real resonance |

Each fixture's ground truth is also declared in `Test/resonance_fixtures/fixtures_metadata.json` under `expected_anomalies_hz` and `expected_count`.

**Validation loop** — during development, run the detector on each fixture manually (scripted in a throwaway file under `_tmp/` or `/tmp/`) and compare to expected:

- Load the WAV with `soundfile`, sum to mono.
- Run `analyze_spectrum()` to get `spectrum_mean`, `freqs`, `sr`.
- Call `detect_resonance_anomalies(spectrum_mean, freqs, sr)`.
- Compare detected frequencies to `expected_anomalies_hz` with ± 5% tolerance.

**Acceptance criterion**: **9/9 fixtures must pass.**

#### 2.3 Tuning policy

If fewer than 9 fixtures pass on the first attempt, tune the constants **in this order of preference**:

1. **First try**: adjust `RESONANCE_LOCAL_WINDOW_OCTAVES` in steps of 1/12 octave (e.g., 1/3 → 1/4 → 1/6 → 1/2). The window width is the most impactful parameter for pass/fail on the cluster fixture (08) and the spoon fixtures (04, 05).
2. **Second try**: adjust `RESONANCE_MIN_EXCESS_DB` in steps of 1.5 dB (e.g., 9 → 7.5 → 10.5). This affects sensitivity.
3. **Third try**: adjust `RESONANCE_MIN_ABSOLUTE_DBFS` in steps of 5 dB if a fixture fails due to noise-floor issues.
4. **Last resort**: fix a bug in the implementation logic. If you find yourself adjusting constants by extreme values (window < 1/12 octave or > 2 octaves, threshold < 3 dB or > 20 dB), the algorithm itself has a bug — debug the implementation instead.

Do NOT adjust the fixtures to make them pass. The fixtures are the spec.

#### 2.4 Document the tuning trajectory

Keep a log in memory of every parameter value you tried and the corresponding fixture pass rate. Even if you land on the default values (1/3 octave, 9 dB) on the first try, document that the default worked. This log goes into the Phase 2 output summary.

### Commits for Phase 2

One or two commits:

1. `fix(resonance): implement detect_resonance_anomalies() with local-contour detection`
2. (If constants needed tuning) `fix(resonance): tune detection constants to pass validation fixtures`

Push after Phase 2.

### Phase 2 output — required

Produce a summary message with:

1. **Implementation summary** — which approach used for the local contour (median vs mean-with-central-suppression), any performance notes, any edge cases handled.
2. **Fixture validation results** — a table showing each fixture, expected count, detected count, detected frequencies, and PASS/FAIL verdict:
   ```
   | Fixture | Expected | Detected        | Verdict |
   | 01      | 0        | 0               | PASS    |
   | 02      | [500]    | [501]           | PASS    |
   | ...
   ```
3. **Final constant values** — list the values of all 6 constants as they stand at the end of Phase 2.
4. **Tuning trajectory** — the log of parameter values attempted, with pass rates. Example:
   ```
   Attempt 1: window=1/3 oct, excess=9 dB → 7/9 (fixtures 04, 08 failed)
   Attempt 2: window=1/4 oct, excess=9 dB → 9/9
   Retained.
   ```
   If you passed 9/9 on attempt 1, say so explicitly.
5. **Commit log** — the commits pushed in Phase 2.

Then **STOP**. Wait for the user to confirm "proceed to Phase 3" before starting Phase 3. Do not chain.

---

## Phase 3 — Harness script, regression check, versioning, final summary

### Goal

Promote the validation loop to a permanent, committed test harness. Verify no regression on `analyze_spectrum()`. Bump the version string. Produce the final deliverable summary.

### Tasks

#### 3.1 Create the validation script

Create `Test/resonance_fixtures/validate.py` as a permanent test harness. This script is committed as part of the fix and becomes the reference validator for any future changes to the resonance detection. It must:

1. Load `fixtures_metadata.json` from the same directory.
2. For each fixture:
   - Load the WAV file with `soundfile`.
   - Sum to mono.
   - Run `analyze_spectrum()` (imported from `mix_analyzer`) to get the spectrum data.
   - Call `detect_resonance_anomalies()` on the spectrum data.
   - Compare the detected frequencies to `expected_anomalies_hz` with ± 5% tolerance.
3. Print per-fixture verdict (PASS / FAIL — missing / FAIL — extra / FAIL — wrong count).
4. Print a final summary: `X/9 fixtures passed`.
5. Exit with code 0 if all pass, 1 if any fail.

The script must be runnable as `python Test/resonance_fixtures/validate.py` from the repo root. It should add the repo root to `sys.path` if needed to import `mix_analyzer`.

The script should be well-commented — it is both a test and a documentation artifact explaining what each fixture exercises.

**Run the script and confirm it outputs 9/9 PASS.** If the script itself has bugs that cause failures while the actual detection is correct, fix the script.

#### 3.2 Non-regression check on `analyze_spectrum()`

Verify that the descriptive `peak_list` produced by `analyze_spectrum()` is **identical to v1.6 behavior** for all 9 fixtures. The `'sr'` key added in Phase 1 is the only permitted change.

Procedure:

1. In a throwaway script (not committed), temporarily re-define the original `analyze_spectrum()` as `analyze_spectrum_original()` (copy-paste from the v1.6 source or from the Git history of `main`).
2. For each of the 9 fixtures, run both functions and assert:
   - The `peak_list` key in both dicts contains identical tuples.
   - All other keys in the original dict exist in the new dict.
   - The new dict has exactly one additional key: `'sr'`.
3. Print `Regression check: PASS` if all 9 fixtures agree, or `Regression check: FAIL` with a diff for any that don't.
4. Delete the throwaway script. Do not commit it.

#### 3.3 Version bump

Find the version string in `mix_analyzer.py` (likely a module-level variable or a docstring at the top of the file — search for "1.6" or "version"). Bump to `1.6.1`.

If the project uses a separate version file (like `__version__.py` or `VERSION`), update that as well.

#### 3.4 Changelog entry

Write a `CHANGELOG.md` entry (either create the file if it doesn't exist, or prepend to it if it does). Use this exact content:

```markdown
## [1.6.1] - YYYY-MM-DD
### Fixed
- Resonance anomaly detection no longer generates false positives on tracks 
  with naturally concentrated spectra (percussive instruments with tonal 
  modes, claps, filtered synths). The detector now compares each candidate 
  peak to its local spectral contour instead of the global spectrum maximum.
- Lowered resonance detection frequency floor from 100 Hz to 60 Hz to cover 
  bass instrument fundamentals in industrial/electronic music.

### Added
- Six tunable constants at the top of `mix_analyzer.py` for resonance 
  detection (window width, excess threshold, floor frequency, etc.).
- Test fixtures and validation script in `Test/resonance_fixtures/`.
```

Replace `YYYY-MM-DD` with today's actual date.

### Commits for Phase 3

Three commits, in order:

1. `test(resonance): add validate.py harness in Test/resonance_fixtures/`
2. `chore: bump version to 1.6.1`
3. `docs: add CHANGELOG entry for 1.6.1`

Push after Phase 3.

### Phase 3 output — required

Produce a final summary message with:

1. **`validate.py` confirmation** — the full output of `python Test/resonance_fixtures/validate.py` showing 9/9 PASS and exit code 0.
2. **Regression check result** — confirmation that `analyze_spectrum()` returns identical `peak_list` for all 9 fixtures, and that only `'sr'` was added to its return dict.
3. **Version bump** — confirmation that the version string in `mix_analyzer.py` (and any separate version file) now reads `1.6.1`.
4. **Changelog entry** — confirmation that `CHANGELOG.md` has the new section.
5. **Final branch state** — total commit count on `fix/resonance-detection-v1.6.1`, list of all commits from Phase 1 through Phase 3.
6. **Instructions for the user to review** — a short note reminding the user to:
   - Pull the branch locally: `git fetch origin && git checkout fix/resonance-detection-v1.6.1`
   - Run the tool on their own bounces to validate real-world behavior.
   - Merge to main when satisfied (do not merge from Claude Code).

---

## Constraints and non-goals

**Do not**:
- Refactor any unrelated code.
- Change the PDF or Excel report generation.
- Modify `analyze_spectrum()` beyond adding `'sr'` to its return dict.
- Delete or modify any pre-existing file in the `Test/` folder outside `Test/resonance_fixtures/`.
- Add new files anywhere in `Test/` outside of `Test/resonance_fixtures/`.
- Commit temporary debug output, `__pycache__`, or any file not strictly needed for the fix.
- Chain phases automatically — each phase ends with STOP and waits for user approval.
- Merge to `main` at any point.
- Ship Phase 2 with fewer than 9/9 fixtures passing. If you cannot reach 9/9 after reasonable tuning attempts, halt and report the failure instead of proceeding.

**Do**:
- Keep all changes inside `mix_analyzer.py`, `CHANGELOG.md`, and `Test/resonance_fixtures/validate.py`.
- Preserve the file's existing coding style (no reformatting of untouched code).
- Write clear inline comments in the new function explaining the algorithm at each step.
- Make the constants genuinely tunable — a producer without Python expertise should be able to raise `RESONANCE_MIN_EXCESS_DB` from 9 to 12 and immediately see fewer warnings in their next analysis.
- Respect the STOP points between phases.

---

## Questions to resolve during implementation

If any of the following come up, decide in favor of the more conservative option and note the decision in the appropriate phase summary:

- **Median vs. mean for the local contour**: the spec prefers median for robustness against the peak itself contaminating its own baseline. If median turns out to be too slow for the spectrum sizes involved (8192 FFT bins, ~4097 frequency points), fall back to mean with central suppression (exclude the ± 2 bins around each target bin from the average). Document the choice in a Phase 2 comment.
- **Edge handling at spectrum boundaries**: at frequencies near the low edge (60-80 Hz) and high edge (>15 kHz), the window may extend outside the spectrum range. Clip the window to valid bins. Do not pad with zeros.
- **Log-frequency window on a linear-bin STFT**: the window width in bins grows with frequency. Precompute per-bin `(bin_low, bin_high)` indices once, before iterating.

---

## Summary of the three phases

| Phase | Scope | Deliverable | STOP? |
|---|---|---|---|
| **1** | Scaffold: constants, placeholder function, `sr` in dict, replace anomaly block | Branch created, 3 commits pushed, tool imports cleanly | ✓ Wait for user |
| **2** | Implementation of `detect_resonance_anomalies()` + fixture validation | 1-2 commits pushed, 9/9 fixtures passing, tuning log documented | ✓ Wait for user |
| **3** | Harness script + regression check + version bump + changelog | 3 commits pushed, `validate.py` runnable, ready for user review | End of task |

After Phase 3 completes, the branch `fix/resonance-detection-v1.6.1` is ready for the user to pull, test empirically on real bounces, and merge manually if satisfied.
