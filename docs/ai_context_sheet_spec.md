# AI Context Sheet — Specification (v1.8.0)

> **Status**: Design document — Phase 1 deliverable  
> **Author**: Claude (automated from prompt `v1_8_ai_context_sheet_prompt.md`)  
> **Date**: 2026-04-15  
> **Target file**: `mix_analyzer.py`  
> **Sheet name**: `AI Context`

---

## Section A — Sheet Layout

The sheet is organized top-to-bottom in four sections, separated by blank rows.

### Position in workbook

Insert immediately after the **Dashboard** sheet (which is already moved to position 2, after Index). The AI Context sheet will be the 3rd sheet in the workbook.

### A.1 — Header block (rows 1–4)

| Row | Col A | Col B |
|-----|-------|-------|
| 1 | `AI CONTEXT — CONSOLIDATED TRACK METRICS` | *(merged A1:Z1)* |
| 2 | `Generated:` | `2026-04-15 14:30` |
| 3 | `Tracks:` | `12 Individual + 1 Full Mix` |
| 4 | `Style:` | `Techno` |

Title row uses `MA_FONT_TITLE` styling. Rows 2–4 use `MA_FONT_DIM`.

### A.2 — Legend block (rows 6–N)

Two sub-blocks separated by a blank row:

**A.2.1 — Anomaly codes legend** (starting row 6)

| Row | Col A | Col B |
|-----|-------|-------|
| 6 | `ANOMALY CODES LEGEND` | |
| 7 | `OK` | `No anomalies detected` |
| 8 | `RES:f1,f2,f3` | `Resonance peaks at listed frequencies (Hz)` |
| 9 | `PHASE:val` | `Phase correlation concern (mono compat warning, val = correlation)` |
| 10 | `PHASE_CRIT:val` | `Phase correlation critical (serious mono compat issue, val = correlation)` |
| 11 | `RMS_LOW:val` | `RMS level very low — track nearly silent (val = RMS in dBFS)` |
| 12 | `PEAK_HOT:val` | `Peak level close to clipping (val = peak in dBFS)` |
| 13 | `PEAK_CLIP:val` | `Peak level at/above clipping threshold (val = peak in dBFS)` |
| 14 | `TP_OVER:val` | `True peak exceeds 0 dBFS — inter-sample clipping (val = TP in dBFS)` |
| 15 | `CREST_LOW:val` | `Very low crest factor — heavy compression (val = crest in dB)` |
| 16 | `WIDTH_HIGH:val` | `Very wide stereo image — verify mono compat (val = width 0-1)` |

**A.2.2 — Column abbreviations legend** (starting after a blank row)

| Row | Col A | Col B |
|-----|-------|-------|
| N+1 | `COLUMN LEGEND` | |
| N+2 | `lufs_int` | `Integrated LUFS (loudness units full scale)` |
| N+3 | `lufs_st_max` | `Maximum short-term LUFS (3s window)` |
| ... | *(one row per column, see Section B)* | |

### A.3 — Track table (Section 1 + Section 2)

Starts after the legend block + 1 blank row.

- **Header row**: column names from Section B, styled with `header_fill` + `MA_FONT_TABLE_HEADER`.
- **Individual track rows**: one row per Individual track, sorted by the order they appear in `analyses_with_info`.
- **BUS track rows**: one row per BUS track, same columns, immediately after individuals.
- **Full Mix row** (Section 2): one row with `track_name = "*** FULL MIX ***"`, visually distinct with a purple background fill (`B967FF`). Same columns as individuals.

All numeric cells use raw numeric values (not formatted strings) so Excel sorting/filtering works correctly. The `anomaly_codes` column is a string.

Auto-filter is enabled on the header row covering all columns.

### A.4 — Health Score breakdown (Section 3)

Starts after the track table + 2 blank rows. Sub-header row: `MIX HEALTH SCORE BREAKDOWN`.

Key-value pairs, 3 columns:

| Col A (key) | Col B (value) | Col C (notes) |
|-------------|---------------|---------------|
| `SCORE_TOTAL` | `54.2` | |
| `SCORE_LOUDNESS` | `67.3` | `weight=0.20, contrib=13.5` |
| `SCORE_DYNAMICS` | `85.6` | `weight=0.20, contrib=17.1` |
| `SCORE_SPECTRAL` | `31.2` | `weight=0.25, contrib=7.8` |
| `SCORE_STEREO` | `65.4` | `weight=0.15, contrib=9.8` |
| `SCORE_ANOMALIES` | `30.0` | `weight=0.20, contrib=6.0` |

The health score is computed by `generate_health_score_sheet()` logic (reuse the same `_calc_*_score()` functions). The values in col B are numeric, not strings.

### A.5 — Per-family aggregates (Section 4)

Starts after health score block + 2 blank rows. Sub-header row: `PER-FAMILY AGGREGATES`.

One block per detected category family (from `CATEGORY_FAMILY` mapping: Drums, Bass, Synth, Guitar, Vocal, FX & Other, Unknown). Only families with at least 1 Individual track are included.

Each block:

| Row | Col A | Col B | Col C | Col D | Col E | Col F |
|-----|-------|-------|-------|-------|-------|-------|
| header | `FAMILY: Drums (n=8)` | | | | | |
| data | `lufs_mean` | `lufs_std` | `crest_mean` | `width_mean` | `dom_band_consensus` | |
| values | `-23.4` | `4.2` | `22.1` | `0.18` | `Bass (60-250 Hz)` | |
| tracks | `Tracks:` | `Kick.wav, Snare.wav, HH.wav, ...` | | | | |

- `dom_band_consensus`: the most common `dominant_band` among tracks in the family.
- `lufs_mean`, `lufs_std`: computed from `lufs_integrated` of Individual tracks in the family (excluding -inf values).
- `crest_mean`: mean of `crest_factor` for tracks in the family.
- `width_mean`: mean of `width_overall` for stereo tracks in the family.

---

## Section B — Track Table Column Schema

### B.1 — Identity columns

| # | Column name | Type | Unit | Source key | Description |
|---|-------------|------|------|------------|-------------|
| 1 | `track_name` | string | — | `analysis['filename']` | Audio file name |
| 2 | `type` | string | — | `track_info['type']` | `Individual`, `BUS`, or `Full Mix` |
| 3 | `category` | string | — | `track_info['category']` | Instrument category (e.g. `Kick`, `Pad / Drone`) |
| 4 | `family` | string | — | `CATEGORY_FAMILY[category]` | Category family (e.g. `Drums`, `Synth`) |

### B.2 — Loudness columns

| # | Column name | Type | Unit | Source key | Description |
|---|-------------|------|------|------------|-------------|
| 5 | `lufs_int` | float | LUFS | `analysis['loudness']['lufs_integrated']` | Integrated loudness (full track) |
| 6 | `lufs_st_max` | float | LUFS | `analysis['loudness']['lufs_short_term_max']` | Maximum short-term loudness (3s window) |
| 7 | `peak_db` | float | dBFS | `analysis['loudness']['peak_db']` | Sample peak level |
| 8 | `true_peak_db` | float | dBFS | `analysis['loudness']['true_peak_db']` | Inter-sample true peak level (4x oversampled) |
| 9 | `rms_db` | float | dBFS | `analysis['loudness']['rms_db']` | RMS level (average energy) |
| 10 | `crest_db` | float | dB | `analysis['loudness']['crest_factor']` | Crest factor: peak minus RMS |
| 11 | `plr_db` | float | dB | `analysis['loudness']['plr']` | Peak-to-Loudness Ratio: peak minus LUFS |
| 12 | `psr_db` | float | dB | `analysis['loudness']['psr']` | Peak-to-Short-term Ratio |
| 13 | `lra_lu` | float | LU | `analysis['loudness']['lra']` | Loudness Range (macro dynamics) |

### B.3 — Spectral columns

| # | Column name | Type | Unit | Source key | Description |
|---|-------------|------|------|------------|-------------|
| 14 | `dom_band` | string | — | `BAND_LABELS[analysis['spectrum']['dominant_band']]` | Frequency band with highest energy |
| 15 | `centroid_hz` | float | Hz | `analysis['spectrum']['centroid']` | Spectral centroid (brightness indicator) |
| 16 | `rolloff_hz` | float | Hz | `analysis['spectrum']['rolloff']` | 85% spectral rolloff frequency |
| 17 | `flatness` | float | — | `analysis['spectrum']['flatness']` | Spectral flatness (0=tonal, 1=noise) |
| 18 | `pct_sub` | float | % | `analysis['spectrum']['band_energies']['sub']` | Energy in Sub band (20-60 Hz) |
| 19 | `pct_bass` | float | % | `analysis['spectrum']['band_energies']['bass']` | Energy in Bass band (60-250 Hz) |
| 20 | `pct_low_mid` | float | % | `analysis['spectrum']['band_energies']['low_mid']` | Energy in Low-Mid band (250-500 Hz) |
| 21 | `pct_mid` | float | % | `analysis['spectrum']['band_energies']['mid']` | Energy in Mid band (500-2000 Hz) |
| 22 | `pct_high_mid` | float | % | `analysis['spectrum']['band_energies']['high_mid']` | Energy in High-Mid band (2-4 kHz) |
| 23 | `pct_presence` | float | % | `analysis['spectrum']['band_energies']['presence']` | Energy in Presence band (4-8 kHz) |
| 24 | `pct_air` | float | % | `analysis['spectrum']['band_energies']['air']` | Energy in Air band (8-20 kHz) |

### B.4 — Stereo columns

| # | Column name | Type | Unit | Source key | Description |
|---|-------------|------|------|------------|-------------|
| 25 | `stereo_width` | float | 0-1 | `analysis['stereo']['width_overall']` | Mid/Side energy ratio (0=mono, 1=full side) |
| 26 | `phase_corr` | float | -1..1 | `analysis['stereo']['correlation']` | L/R phase correlation (+1=perfect mono compat) |
| 27 | `is_stereo` | string | — | `analysis['stereo']['is_stereo']` | `TRUE` or `FALSE` |

### B.5 — Tonal / musical columns

| # | Column name | Type | Unit | Source key | Description |
|---|-------------|------|------|------------|-------------|
| 28 | `dom_note` | string | — | `analysis['musical']['dominant_note']` | Dominant pitch class (e.g. `C#`, `A`) |
| 29 | `tonal_strength` | float | — | `analysis['musical']['tonal_strength']` | Tonal peak-to-mean ratio (>1.8 = tonal content) |
| 30 | `is_tonal` | string | — | `analysis['musical']['is_tonal']` | `TRUE` or `FALSE` |

### B.6 — Tempo columns

| # | Column name | Type | Unit | Source key | Description |
|---|-------------|------|------|------------|-------------|
| 31 | `tempo_bpm` | float | BPM | `analysis['tempo']['tempo_median']` | Median detected tempo |
| 32 | `tempo_conf` | string | — | `analysis['tempo']['confidence_label']` | Tempo confidence label |
| 33 | `tempo_reliable` | string | — | `analysis['tempo']['reliable']` | `TRUE` if tempo is reliable, `FALSE` otherwise |

### B.7 — Temporal columns

| # | Column name | Type | Unit | Source key | Description |
|---|-------------|------|------|------------|-------------|
| 34 | `num_onsets` | int | — | `analysis['temporal']['num_onsets']` | Number of detected transients |

### B.8 — Metadata columns

| # | Column name | Type | Unit | Source key | Description |
|---|-------------|------|------|------------|-------------|
| 35 | `duration_s` | float | s | `analysis['duration']` | Track duration in seconds |
| 36 | `sample_rate_hz` | int | Hz | `analysis['sample_rate']` | Audio sample rate |
| 37 | `num_channels` | int | — | `analysis['num_channels']` | Number of audio channels |

### B.9 — Anomaly column

| # | Column name | Type | Unit | Source key | Description |
|---|-------------|------|------|------------|-------------|
| 38 | `anomaly_codes` | string | — | `encode_anomalies(analysis['anomalies'])` | Compact anomaly codes joined with ` \| ` |

**Total columns: 38**

---

## Section C — Anomaly Codes Legend

### C.1 — Mapping from `detect_anomalies()` output to compact codes

The function `detect_anomalies()` (line 749) produces a list of `(severity, description)` tuples. Each description string is pattern-matched and encoded as follows:

| detect_anomalies() pattern | Severity | Code | Value extraction |
|----------------------------|----------|------|------------------|
| `"Peak level at {v} dBFS - clipping risk"` | critical | `PEAK_CLIP:{v}` | Extract dBFS value from description |
| `"Peak level at {v} dBFS - very little headroom"` | warning | `PEAK_HOT:{v}` | Extract dBFS value from description |
| `"True Peak at {v} dBFS - inter-sample clipping"` | critical | `TP_OVER:{v}` | Extract dBFS value from description |
| `"Phase correlation {v} - serious mono compatibility issue"` | critical | `PHASE_CRIT:{v}` | Extract correlation value |
| `"Phase correlation {v} - mono compatibility concern"` | warning | `PHASE:{v}` | Extract correlation value |
| `"RMS level very low ({v} dBFS)"` | warning | `RMS_LOW:{v}` | Extract RMS value |
| `"Strong resonance peaks detected at: {freqs}"` | warning | `RES:{f1},{f2},{f3}` | Extract Hz values, strip "Hz" suffix, join with `,` |
| `"Very low crest factor ({v} dB)"` | warning | `CREST_LOW:{v}` | Extract crest value |
| `"Very wide stereo image ({v})"` | info | `WIDTH_HIGH:{v}` | Extract width value |

### C.2 — Encoding rules

1. Each anomaly is encoded as a single code string (e.g. `RES:533,1147`).
2. Multiple codes are joined with ` | ` (space-pipe-space).
3. If no anomalies exist, the cell value is the string `OK`.
4. Empty string is never used — `OK` or a code is always present.
5. Values are rounded to match what `detect_anomalies()` outputs (typically 1-2 decimal places).

### C.3 — Implementation: `encode_anomalies(anomaly_list)`

The helper function takes the raw `anomalies` list from `analyze_track()` output and returns a single string. It uses regex or string matching on the description to determine the code type. If a description does not match any known pattern (future-proofing), it falls back to `WARN:{first_40_chars}`.

---

## Section D — Edge Cases

### D.1 — Mono tracks

- `stereo_width`: set to `0.0` (the `analyze_stereo()` function already returns `width_overall=0.0` for mono).
- `phase_corr`: set to `1.0` (already returned as `1.0` for mono by `analyze_stereo()`).
- `is_stereo`: set to `FALSE`.
- These values are real numbers, not empty cells, because they represent the actual mono state.

### D.2 — BUS tracks

- BUS tracks use the same columns as Individual tracks. They are distinguished by `type = "BUS"`.
- BUS tracks appear in the track table after Individual tracks, before the Full Mix row.
- BUS tracks are NOT included in per-family aggregates (Section 4), consistent with how the existing health score excludes BUS.

### D.3 — NaN / missing values

- `lufs_integrated` can be `-inf` when the track is extremely quiet. In this case, the cell is left empty (`None` in openpyxl) rather than writing `-inf`, which is not a valid Excel number.
- `lufs_short_term_max` follows the same rule.
- All other numeric metrics always produce finite values in the current codebase.
- For metrics that don't apply (e.g. tempo for individual tracks where `confidence_label = 'not computed (individual track)'`), the numeric cell (`tempo_bpm`) is set to `0.0` (as returned by the analysis) and `tempo_reliable` is `FALSE`. This preserves the actual data rather than hiding it.

### D.4 — Long track names

- Track names are written as-is (no truncation). Excel handles long strings in cells natively.
- Column A (`track_name`) width is set to 45 characters. Overflow is visible when the cell is selected.

### D.5 — Special characters in track names

- Unicode, accented letters, and special characters are passed through as-is. openpyxl handles UTF-8 natively.
- No sanitization is applied to cell values (only sheet names require sanitization via `_safe_sheet_name()`).

### D.6 — No Full Mix track

- If no Full Mix track exists in the analysis, Section 2 (Full Mix row) is omitted entirely.
- Health Score breakdown (Section 3) still appears — the `_calc_*_score()` functions handle the `full_mix=None` case.

### D.7 — No Individual tracks

- If only a Full Mix track exists (no individuals), Section 1 has zero rows, Section 2 has the Full Mix row, Section 4 (per-family aggregates) is omitted.

---

## Section E — Styling

The AI Context sheet follows the existing cyberpunk dark theme used by all other sheets:

- Background: `0A0A12` (deep navy)
- Panel fill for data cells: `1A1A24`
- Header fill: `1A3A5A`
- Full Mix row fill: `2A1A3A` (distinct purple tint)
- Tab color: `00D9FF` (cyan, matching the Index sheet)
- All fonts use the `MA_FONT_*` constants
- `_apply_dark_background()` is called at the end
- `_apply_clean_layout()` is called at sheet creation

---

## Section F — Integration Point

### F.1 — Where to insert the call

In `generate_excel_report()` (line 3860), after the Dashboard sheet is moved to position 2 (line 4660), and before the Frequency Conflicts sheet (line 4662). Specifically, insert the call between lines 4660 and 4662:

```python
# ---- AI Context Sheet ----
build_ai_context_sheet(wb, analyses_with_info, style_name, log_fn=log_fn)
```

### F.2 — Function signature

```python
def build_ai_context_sheet(workbook, analyses_with_info, style_name, log_fn=None):
```

The function receives the same `analyses_with_info` list that all other sheet generators receive. No additional data structures need to be passed — the health score is recomputed internally using the existing `_calc_*_score()` functions (same as `generate_health_score_sheet()` does).

### F.3 — Helper function

```python
def encode_anomalies(anomaly_list):
    """Encode a list of (severity, description) anomaly tuples into compact codes.
    Returns 'OK' if no anomalies, otherwise codes joined with ' | '.
    """
```

### F.4 — Sheet positioning

After creation, move the sheet to be immediately after Dashboard:

```python
wb.move_sheet(ws, offset=-(len(wb.sheetnames) - 3))
```

The exact offset will be calculated at implementation time to place it as the 3rd sheet.
