# Changelog

## [1.8.0] - 2026-04-15

### Added
- New `AI Context` sheet in the Excel report. This sheet consolidates all 
  per-track metrics into a single dense table optimized for AI-assisted 
  mix conversations. Includes:
    - One row per individual track with full loudness, spectral, stereo, 
      and tonal metrics (38 columns).
    - Full Mix row with the same columns.
    - Mix Health Score breakdown as key-value pairs.
    - Per-family aggregates (Drums, Bass, Synth, etc.) with mean, 
      std, and consensus dominant band.
    - Anomalies encoded as compact codes (`RES:`, `PHASE:`, `RMS_LOW:`, 
      etc.) with a legend block at the top of the sheet.
- The new sheet is generated automatically as part of the existing report 
  pipeline. No new CLI argument or configuration needed.
- New folder `docs/` for project documentation, including the AI Context 
  sheet specification and design prompts.

### Notes
- This sheet is additive only. All existing sheets (`Summary`, `Anomalies`, 
  `Mix Health Score`, `Full Mix Analysis`, `Track Comparison`, etc.) remain 
  identical to v1.7. Producers who do not use AI assistance can simply 
  ignore the new sheet.
- The AI Context sheet is positioned near the start of the workbook for 
  visibility but does not replace the human-facing sheets.
- Sheet specification is documented in `docs/ai_context_sheet_spec.md`.
