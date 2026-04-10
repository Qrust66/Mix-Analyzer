# Mix Analyzer v1.7

Visual audio mix analysis tool for music producers. Analyzes bounced audio tracks from a DAW and generates detailed PDF and Excel diagnostic reports.

## Installation

**Python 3.13+** required.

```bash
py -m pip install numpy scipy librosa matplotlib soundfile openpyxl reportlab pyloudnorm
```

> On Windows, if `py` is not recognized, ensure Python was added to PATH during installation.

## Usage

```bash
python mix_analyzer.py
```

### Workflow

1. **Setup tab** — Load the folder containing your exported WAV/AIFF bounces. Choose your musical style.
2. **Track Identification tab** — Mark your full song bounce as "Full Mix". Run "Auto-detect all" to categorize tracks by name. Review/correct.
3. **Full Mix tab** — Set mix completion state, active master bus plugins, loudness target, notes.
4. **Analysis tab** — Choose output format (PDF, Excel, or Both). Click RUN ANALYSIS. Open output folder or generate AI prompt when done.
5. **HELP button** — Located in the top header bar, next to "MIX ANALYZER v1.7". Opens a scrollable help window.

### Sharing with AI

After analysis, click "Generate AI Analysis Prompt", copy it, open a Claude conversation, attach the PDF/XLSX files, and paste the prompt.

## Output

### Report naming convention

```
{SongName}_MixAnalyzer_{YYYY-MM-DD}_{TrackName}.pdf
{SongName}_MixAnalyzer_{YYYY-MM-DD}_GLOBAL.pdf
{SongName}_MixAnalyzer_{YYYY-MM-DD}.xlsx
```

Song name is auto-detected from the Full Mix track, with fallback to the input folder name. Existing reports are overwritten on regeneration.

### Output format selector

The Analysis tab provides a dropdown to choose:
- **PDF** — Individual track PDFs + global PDF (default)
- **Excel** — Single .xlsx workbook with 8 sheets (Index, Summary, Anomalies, Full Mix Context, per-track sheets with embedded charts, Global Comparison, Full Mix Analysis, AI Prompt)
- **Both** — Generates PDF and Excel

## v1.7 Changes

### UI Improvements
- **#2** Strip song prefix from Track Identification list display (Full Mix keeps full name)
- **#3** Conditional scrollbar — only shows when content overflows
- **#4** Max-height dropdowns — no internal scrolling in any combobox
- **#5** Larger global titles (Title 20pt, SubTitle 15pt, Section 13pt)
- **#6** HELP button in app header with 4-section scrollable help window
- **#11** Inverted tab visual behavior — selected tab is bigger (14pt bold) than unselected (11pt)
- **#12** Output folder button grouped next to Generate AI Prompt

### Analysis Improvements
- **#7** Frequency masking matrix upgraded to 22 third-octave bands (was 7 broad bands)
- **#8** Full mix structure detection: 3-pass multi-feature novelty (chroma + spectral flux + MFCC), targets 12-16 sections

### Infrastructure
- **#9** Auto-detect confirmation popup before overwriting manual categories
- **#10** Auto-detect strips project name prefix before pattern matching
- Output format selector (PDF / Excel / Both)
- Multi-level progress display (progress bar + step/substep/counter/ETA)
- Cancel button with partial file cleanup
- Thread-safe UI updates from worker thread

### Excel Export (new)
- 8-sheet workbook with cyberpunk theme
- Conditional formatting (color scales on LUFS, crest factor)
- Sortable anomalies with autofilter
- Per-track sheets with metrics tables + 9 embedded matplotlib visualizations (200 DPI, 1600x900)
- Global comparison charts (masking matrix, LUFS bars, crest bars, spectral balance)
- AI prompt sheet ready to copy

## Dependencies

| Package | Purpose |
|---------|---------|
| numpy | Numerical computation |
| scipy | Signal processing |
| librosa | Audio analysis |
| matplotlib | Visualization |
| soundfile | Audio I/O |
| pyloudnorm | LUFS/loudness measurement |
| reportlab | PDF generation |
| openpyxl | Excel generation (new in v1.7) |
