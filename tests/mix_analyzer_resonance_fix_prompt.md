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

## What to build

### Design principle

**Keep both algorithms.** The existing `analyze_spectrum()` function still produces `peak_list` as a *descriptive* feature of the spectral contour. It remains unchanged and continues to feed the PDF report, the Excel report, and any other consumer. This is a descriptive output, not a prescriptive one, and it is useful as-is.

**Add a new prescriptive function** `detect_resonance_anomalies(spectrum_mean, freqs, sr)` that uses a local-contour-comparison approach and is used **only** in the anomaly detection pipeline (lines 777-781). The result: the same track can have rich "peaks" in its descriptive report while correctly reporting zero anomalies in its prescriptive warning list.

### New function specification

```python
def detect_resonance_anomalies(spectrum_mean, freqs, sr):
    """
    Detect peaks in the spectrum that rise significantly above their LOCAL
    spectral contour. Unlike the descriptive peak detection in analyze_spectrum(),
    this function compares each candidate peak to a moving-average baseline of
    its immediate frequency neighborhood, so it correctly handles:

      - Tracks with naturally concentrated spectra (percussion tonal modes, 
        filtered synths) where the "max" IS the natural content and should 
        NOT trigger warnings.
      - Tracks with wideband content where a real resonance sits well below
        the global spectral max but sticks out clearly in its local context.

    Parameters
    ----------
    spectrum_mean : np.ndarray
        Magnitude spectrum (linear, time-averaged) produced by STFT. Same
        array as used in analyze_spectrum().
    freqs : np.ndarray
        Frequency bins corresponding to spectrum_mean (Hz).
    sr : int
        Sample rate.

    Returns
    -------
    list of (freq_hz, excess_db) tuples, sorted by excess_db descending,
    truncated to RESONANCE_MAX_REPORTED_PEAKS entries. Empty list if no
    anomalous peaks found.

    The excess_db value is how many dB above the local contour the peak
    rises. A value of +12 dB means the peak is 12 dB above the moving
    average of its ± RESONANCE_LOCAL_WINDOW_OCTAVES neighborhood.
    """
```

### Algorithm

1. Convert `spectrum_mean` to dBFS using the track's absolute level, **not** normalized to its max:
   ```
   spectrum_dbfs = 20 * log10(spectrum_mean / ref) 
   ```
   where `ref` is a fixed full-scale reference (use `max(spectrum_mean)` to get a relative dB scale is fine — the algorithm cares about *differences* from the local baseline, not absolute levels).

2. Compute a smoothed **local contour** by applying a moving average over the dB spectrum, where the window width is ± `RESONANCE_LOCAL_WINDOW_OCTAVES` octaves around each bin. Because FFT bins are linearly spaced but octaves are logarithmic, the window width in bins depends on the frequency:
   ```
   For each frequency f:
     low_f  = f / (2 ** RESONANCE_LOCAL_WINDOW_OCTAVES)
     high_f = f * (2 ** RESONANCE_LOCAL_WINDOW_OCTAVES)
     contour[f] = mean of spectrum_dbfs in [low_f, high_f]
   ```
   Implement this efficiently using variable-width sliding windows or numpy broadcasting. The contour excludes the central bin (or gives it low weight) so that a peak does not "raise its own baseline". A simple approach: use the median or trimmed mean of the neighborhood excluding the center bin, OR use a mean with central ~5% weight suppression. **Prefer median over mean** because the median is robust to the presence of the peak itself — a peak contributes one sample to its own neighborhood but does not shift the median significantly.

3. Compute `excess[f] = spectrum_dbfs[f] - contour[f]` for every frequency bin.

4. Find peaks in `excess` using `scipy.signal.find_peaks` with minimum height equal to `RESONANCE_MIN_EXCESS_DB`. Also require minimum absolute level so we ignore noise-floor artifacts: a peak must also satisfy `spectrum_dbfs[f] >= RESONANCE_MIN_ABSOLUTE_DBFS`.

5. Apply the frequency floor: exclude peaks with `freq < RESONANCE_MIN_FREQ_HZ`.

6. Sort resulting peaks by `excess_db` descending, keep top `RESONANCE_MAX_REPORTED_PEAKS`.

7. Return the list.

### Constants to add at the top of `mix_analyzer.py`

Add a clearly-marked section near the top of the file (before the first function definition), with explanatory comments so the producer can tune them empirically without needing to understand the algorithm's internals:

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
#   roughly corresponds to a paramétric EQ with Q=4-6).
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

### Integration

Replace the current anomaly detection block (lines 777-781) with a call to the new function. The new block should look like:

```python
# Strong resonance peaks (v1.6.1: local-contour-based detection)
resonance_peaks = detect_resonance_anomalies(
    S['spectrum_mean'], S['freqs'], sr
)
if len(resonance_peaks) >= RESONANCE_MIN_PEAKS_FOR_WARNING:
    freqs_str = ', '.join(f"{p[0]:.0f}Hz" for p in resonance_peaks)
    anomalies.append(('warning', f"Strong resonance peaks detected at: {freqs_str}"))
```

Note: `detect_anomalies()` currently receives `analysis` as argument, and accesses the spectrum data through `S = analysis['spectrum']`. You need to ensure that `spectrum_mean`, `freqs`, and `sr` are all available from `S`. Check `analyze_spectrum()`'s return dict — `spectrum_mean` and `freqs` are already in there (lines 456-466). The sample rate `sr` needs to be passed through. Either:

- **Option A (preferred)**: store `sr` in the spectrum dict in `analyze_spectrum()` so `S['sr']` is available. Minimal change.
- **Option B**: pass `sr` as a second argument to `detect_anomalies()`. Requires updating the caller.

Use Option A. In `analyze_spectrum()`, add `'sr': sr` to the returned dictionary. Do not change anything else in that function.

---

## Validation protocol

### Test fixtures

The validation uses 9 synthetic audio fixtures with known ground truth, located in the repository at `Test/resonance_fixtures/`. 

**CRITICAL — repository hygiene instructions**:

- The `Test/` folder at the repository root **contains pre-existing files from prior test phases**. **Do not delete, move, or modify** any of those pre-existing files.
- Work **only** with the files in the new subfolder `Test/resonance_fixtures/`, which contains 9 `.wav` files plus one `fixtures_metadata.json`.
- **Do not add new files to `Test/` outside of `resonance_fixtures/`**. Any temporary scripts or outputs generated during validation should go in a transient folder (e.g., `/tmp/` or a gitignored `_tmp/` at repo root) and **must not be committed**.

### Fixture inventory

The 9 fixtures cover the failure modes of the current algorithm and the success cases the new algorithm must preserve. Each fixture's ground truth is declared in `Test/resonance_fixtures/fixtures_metadata.json` under the keys `expected_anomalies_hz` (list of Hz values) and `expected_count` (integer).

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

### Validation procedure

Write a validation script at `Test/resonance_fixtures/validate.py` (you may commit this script as part of the fix, it's the new permanent test harness for this feature). The script must:

1. Load `fixtures_metadata.json`.
2. For each fixture:
   - Load the WAV file with `soundfile`.
   - Sum to mono.
   - Run `analyze_spectrum()` to get the spectrum data.
   - Call `detect_resonance_anomalies()` directly on the spectrum data.
   - Compare the detected frequencies to `expected_anomalies_hz`.
3. Apply frequency matching tolerance: ± 5% of expected value (FFT bin resolution at 8192 samples / 44.1 kHz is ~5.4 Hz, and peaking EQ filters spread energy across multiple bins, so a 500 Hz peak may be detected anywhere in [475, 525]).
4. Report per-fixture verdict as one of:
   - `PASS` — detected frequencies match expected (within tolerance, same count)
   - `FAIL — missing`: expected frequencies not detected
   - `FAIL — extra`: unexpected frequencies detected
   - `FAIL — wrong count`: right frequencies but wrong count
5. Print a final summary: `X/9 fixtures passed`.

**Acceptance criterion**: **9/9 fixtures must pass.**

If fewer than 9 pass, iterate on the algorithm (tune constants, fix edge cases in the implementation) and re-run until 9/9. Do not ship a partial fix.

### Secondary validation: no regression on `analyze_spectrum()`

The descriptive peak list in `analyze_spectrum()` is used elsewhere in the tool (PDF reports, Excel reports, masking matrix). **It must not be modified** beyond adding `'sr': sr` to the returned dict. To prove no regression, after implementing the fix run the validation script and confirm:

- `analyze_spectrum()` still returns the same keys it did before plus `'sr'`.
- The `peak_list` returned by `analyze_spectrum()` for each fixture is **identical** to what the unmodified function would return. (You can verify this by keeping a temporary copy of the original function as `analyze_spectrum_original()` during development, running it alongside, and asserting equality on `peak_list`. Remove this temporary code before committing.)

---

## Git workflow

Follow the project's existing Git conventions for this patch:

1. Create a feature branch from `main`:
   ```
   git checkout -b fix/resonance-detection-v1.6.1
   ```
2. Make all changes on this branch. Commit in logical chunks:
   - First commit: constants section added at top of file.
   - Second commit: new `detect_resonance_anomalies()` function added.
   - Third commit: `analyze_spectrum()` return dict extended with `'sr'`.
   - Fourth commit: `detect_anomalies()` updated to use the new function.
   - Fifth commit: `Test/resonance_fixtures/validate.py` added.
   - Sixth commit: version bumped to 1.6.1 (wherever the version string lives in the code).
3. Each commit message should follow the format `fix(resonance): <short description>` or `test(resonance): <short description>`.
4. Push the branch to origin.
5. Do not merge to `main` directly. Leave the branch open for user review.

---

## Output expected

At the end of the task, produce a summary message with:

1. **Summary of changes** — list of files touched, functions added/modified, constants added.
2. **Validation report** — the output of `Test/resonance_fixtures/validate.py` showing X/9 fixtures passing. If not 9/9, explain why and what was tuned.
3. **Regression check** — confirmation that `analyze_spectrum()` returns identical `peak_list` for all 9 fixtures.
4. **Changelog entry** — a short markdown section suitable for inclusion in a CHANGELOG.md or release notes:
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
5. **Branch name and commit log** — the feature branch name and a list of commits in order.

---

## Constraints and non-goals

**Do not**:
- Refactor any unrelated code.
- Change the PDF or Excel report generation.
- Modify `analyze_spectrum()` beyond adding `'sr'` to its return dict.
- Delete or modify any pre-existing file in the `Test/` folder outside `resonance_fixtures/`.
- Commit temporary debug output, `__pycache__`, or any file not strictly needed for the fix.
- Ship the patch if fewer than 9/9 fixtures pass.
- Change the behavior of the descriptive `peak_list` in any way.

**Do**:
- Keep all changes inside `mix_analyzer.py` and `Test/resonance_fixtures/validate.py`.
- Preserve the file's existing coding style (no reformatting of untouched code).
- Write clear inline comments in the new function explaining the algorithm at each step.
- Make the constants genuinely tunable — a producer without Python expertise should be able to raise `RESONANCE_MIN_EXCESS_DB` from 9 to 12 and immediately see fewer warnings in their next analysis.

---

## Questions to resolve during implementation

If any of the following come up, decide in favor of the more conservative option and note the decision in the summary:

- **Moving average vs. median for the local contour**: the spec prefers median for robustness against the peak itself contaminating its own baseline. If median turns out to be too slow for the spectrum sizes involved (8192 FFT bins, ~4000 frequency points), fall back to mean with central suppression (exclude the ± 2 bins around each target bin from the average). Document the choice in a comment.
- **Edge handling at spectrum boundaries**: at frequencies near the low edge (60-80 Hz) and high edge (>15 kHz), the window may extend outside the spectrum range. Clip the window to valid bins. Do not pad with zeros (that would bias the contour downward).
- **Dealing with the log-frequency window on a linear-bin STFT**: the window width in bins grows with frequency. A ± 1/3 octave window at 100 Hz spans ~40 Hz of bins, at 10 kHz it spans ~4000 Hz of bins. Implement this with per-bin variable window width — you can precompute a list of `(bin_low, bin_high)` indices for each target bin in a single pass.

---

Ship the fix when all validation passes. The user will pull the branch, run the tool on their actual project bounce, and validate empirically. If the real-world behavior needs further tuning, the constants at the top of the file are the tuning surface — no further code changes expected.
