# Mix Analyzer v1.8 — AI Context sheet

## Context

Mix Analyzer is a Python desktop tool (mix_analyzer.py, single file, 8000+ lines) that analyzes audio bounces from Ableton Live and produces diagnostic Excel reports. The Excel report currently contains 14+ sheets (Summary, Anomalies, Mix Health Score, Full Mix Analysis, Track Comparison, Freq Conflicts, etc.), each with its own purpose and formatting.

This task adds one new sheet to the existing Excel report: a dense, AI-readable consolidation of all per-track metrics in a single place. The goal is token economy for AI-assisted mix conversations: when the user shares the Excel report with an AI (Claude, ChatGPT, etc.), the AI can read this single sheet and have full context on every track in one ingestion pass, instead of having to traverse 14 sheets and reconstruct the per-track picture.

This is an additive feature — no existing sheet is modified, removed, or restructured. The new sheet sits alongside the others.

**Target file**: `mix_analyzer.py`  
**Target version**: 1.8.0 (minor version bump — new feature, no breaking changes)  
**Branch name**: `feat/ai-context-sheet-v1.8`  
**Starting state**: main branch with v1.6.1 (resonance fix) merged. The Excel export pipeline is functional and produces all current sheets. Adjust the version bump in Phase 3 if v1.7 has been released between the time this prompt is written and the time it is executed.

This prompt is autonomous. You do not need to read other prompts.

## Repository structure

The relevant files in the repo root are:

```
Mix-Analyzer/
├── .gitignore
├── README.md
├── CHANGELOG.md           (added in v1.6.1)
├── mix_analyzer.py
├── tests/
│   ├── 01_flat_wideband.wav  ... 09_realistic_mix_one_anomaly.wav  (9 fixtures)
│   ├── fixtures_metadata.json
│   ├── validate.py        (added in v1.6.1 — the resonance harness)
│   └── mix_analyzer_resonance_fix_prompt.md
└── (no docs/ folder yet — Phase 1 will create it if needed)
```

The 9 test fixtures live directly in `tests/`. There is no subfolder. All paths in this prompt use `tests/` as the directory.

### Where to commit this prompt itself

When Phase 1 commits the spec document (see 1.2), it should also commit this prompt file itself alongside the spec, in a new `docs/prompts/` folder. The intent is to keep all design documents and prompts grouped under `docs/` rather than scattered between `tests/` and the root.

Specifically, in Phase 1, you will:
1. Create `docs/prompts/` if it doesn't exist
2. Commit `docs/prompts/v1_8_ai_context_sheet_prompt.md` (this file's content)
3. Commit `docs/ai_context_sheet_spec.md` (the spec you write)

This is the "logical place" for prompts and design documents, parallel to how `tests/` holds executable test code.

## Why this matters

The user produces Mix Analyzer reports across many bounces of the same project (P12 -> P13 -> P14 -> ... -> P19) and shares them with an AI for mix/mastering guidance. Currently each bounce takes the AI 3000-5000 tokens of context just to read the report. With the new AI Context sheet, the same information ingests in 800-1500 tokens, leaving more context budget for actual reasoning and conversation history.

The new sheet is also useful for the user directly: it is a single-page summary of every track's key metrics and anomalies, sortable and filterable in Excel.

## Design constraints

The new sheet must be:

1. **Lossless complete** — every metric that Mix Analyzer currently computes per track must appear in this sheet, even if niche. No silent omissions for "simplicity".
2. **Real Excel columns** — not CSV-in-a-cell, not formatted prose. The sheet uses standard Excel columns so it remains human-usable (sorting, filtering, copy-paste).
3. **Compact encoding for anomalies** — anomalies are encoded as short codes (`RES:`, `PHASE:`, `RMS_LOW:`) joined with `|`, not as full English sentences. A legend block at the top of the sheet documents the codes.
4. **Self-contained** — a reader who opens only this sheet (and nothing else in the file) should be able to understand every track's state. The legend block must include both the anomaly codes and a brief one-line description of what each numeric column means.

The new sheet must NOT:

- Replace or modify any existing sheet.
- Recompute any metric. It must reuse the data structures already built by `analyze_track()` and aggregated for the report. Reorganization only.
- Add new dependencies. Use the existing openpyxl (or whatever the current Excel writer is).
- Add a new entry point or CLI argument. It is generated automatically as part of the existing report pipeline.

**Sheet name**: `AI Context` (with a space, Excel handles this fine).

**Position in the workbook**: insert immediately after the Index sheet (so it is one of the first sheets a reader sees), or after the Dashboard sheet if Index is not the first sheet. The exact position can be decided in Phase 1.

## Multi-phase execution protocol

This task is split into 3 phases with mandatory STOP points. Do not chain phases automatically. After each phase, produce the required summary and halt until the user confirms "proceed to next phase".

- **Phase 1** — Discovery & schema design (no code changes, only a written spec)
- **Phase 2** — Implementation (the new sheet is generated as part of the report)
- **Phase 3** — Regression check, version bump, CHANGELOG, final summary

Create the feature branch at the start of Phase 1:

```bash
git checkout main
git pull
git checkout -b feat/ai-context-sheet-v1.8
```

Do not merge to main at any point. The branch stays open for the user to review and merge manually.

---

## Phase 1 — Discovery & schema design

### Goal

Before writing any code, map the existing data flow in `mix_analyzer.py`, identify exactly where the Excel report is generated, and produce a detailed written specification of the new sheet's columns, anomaly codes, and layout. The output of Phase 1 is a markdown spec document committed to the repo, NOT code.

### Tasks

#### 1.1 Discover the existing data flow

Read `mix_analyzer.py` and identify:

- The function (or set of functions) that builds the Excel report. Likely named something like `build_excel_report()`, `write_xlsx()`, `generate_report()`, etc.
- The data structure that holds per-track analysis results. Likely a list of dicts or a dict-of-dicts coming out of `analyze_track()` for each WAV file.
- Where the existing sheets are populated (e.g. Summary sheet population, Anomalies sheet population, Mix Health Score sheet population). Identify the function or block of code that writes each.
- The full set of metrics computed per track. Walk through `analyze_track()` (or equivalent) and `analyze_spectrum()` and `compute_stereo()` and any other analysis function. List every numeric metric, every text label, every list field.

Produce an inventory document at `_tmp/v1_8_discovery.md` (do not commit yet — this is for your own reference). It should contain:

- Path and line numbers of the main report-building function
- Path and line numbers of `analyze_track()` and any other analysis functions that produce track-level data
- The exact dict keys (or class attributes) used in the per-track data structure
- A complete list of every metric available per track, with its key name, type, and unit

#### 1.2 Write the AI Context sheet specification

Based on the discovery, write a specification document at `docs/ai_context_sheet_spec.md` (this WILL be committed in Phase 1 — it is part of the deliverable). The spec must contain:

**Section A — Sheet layout**

Describe the visual layout of the sheet, top to bottom:

1. **Header block** (rows 1-N): title, generation date, project name, total track count, link back to Index sheet.
2. **Legend block** (rows N+1 to M): explanation of anomaly codes (one row per code), explanation of any non-obvious column abbreviations.
3. **Track table — Section 1** (rows M+1 onward): one row per individual track, ~30-40 columns. Include a header row.
4. **Track table — Section 2** (one row): the Full Mix row, same columns as Section 1, with `track_name = "*** FULL MIX ***"` and a visually distinct row format (background color or border).
5. **Health Score breakdown — Section 3** (~15 rows): key-value pairs of the Mix Health Score components.
6. **Per-family aggregates — Section 4** (variable rows): one block per detected category.

**Section B — Track table column schema**

List every column that will appear in the track table (Sections 1 and 2). For each column, give:

- Column name (short, lowercase, underscores)
- Data type (string / int / float / list)
- Unit if numeric (Hz, dB, %, dBFS, LUFS, etc.)
- Source dict key in `analyze_track()` output
- Brief description (1 line)

**Section C — Anomaly codes legend**

Define the encoding for the `anomaly_codes` column with exact mapping from each anomaly type.

**Section D — Edge cases**

Document how the spec handles mono tracks, BUS tracks, NaN/missing values, long track names, and special characters.

#### 1.3 Commit the spec and the prompt

Once the spec is written, create the `docs/` and `docs/prompts/` directories if they don't exist, then commit both the spec and this prompt:

```bash
mkdir -p docs/prompts
git add docs/ai_context_sheet_spec.md docs/prompts/v1_8_ai_context_sheet_prompt.md
git commit -m "feat(ai-context): add v1.8 sheet specification and prompt"
git push -u origin feat/ai-context-sheet-v1.8
```

Do not commit the discovery file (`_tmp/v1_8_discovery.md`).

### Phase 1 deliverables

Produce a summary message containing:

1. **Discovery summary** — paths and line numbers of key functions
2. **Total metrics inventory** — count and list of metrics
3. **Schema spec link** — confirm spec exists and is committed
4. **Prompt copy committed** — confirm prompt file exists and is committed
5. **Anomaly mapping summary** — complete mapping confirmation
6. **Open questions** — any design decisions needing user input
7. **Commit pushed** — branch name and commit hash

Then STOP. Wait for the user to confirm "proceed to Phase 2" before starting the implementation. Do not chain.

---

## Phase 2 — Implementation

### Goal

Implement the AI Context sheet generation, integrated into the existing Excel report pipeline.

### Tasks

- **2.1** Add `build_ai_context_sheet()` function and `encode_anomalies()` helper
- **2.2** Wire into the report pipeline in `generate_excel_report()`
- **2.3** Smoke test on the 9 test fixtures
- **2.4** Commit and push (2 commits)

Then STOP. Wait for user to confirm "proceed to Phase 3".

---

## Phase 3 — Regression check, versioning, changelog

### Goal

Verify no existing sheet was modified, bump version, write CHANGELOG.

### Tasks

- **3.1** Regression check: cell-by-cell comparison of existing sheets between baseline and branch
- **3.2** Run `validate.py` — confirm 9/9 pass
- **3.3** Version bump to 1.8.0
- **3.4** CHANGELOG entry
- **3.5** Commit and push (2-3 commits)

Then HALT. Task complete.

---

## Constraints and non-goals

Do not:
- Modify any existing sheet
- Recompute any metric
- Add new dependencies
- Add new CLI arguments
- Change the existing Excel writer or template
- Touch analysis functions
- Touch the resonance detection code
- Commit anything in `_tmp/`
- Merge to main
- Chain phases automatically

## Summary of the three phases

| Phase | Scope | Deliverable | STOP? |
|-------|-------|-------------|-------|
| 1 | Discovery + written spec | 1 commit, spec document, no code changes | Wait for user |
| 2 | Implementation + smoke test | 2 commits, working sheet generation | Wait for user |
| 3 | Regression + version bump + CHANGELOG | 2-3 commits, all existing sheets identical | End of task |
