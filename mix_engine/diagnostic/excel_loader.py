"""excel_loader — slice the Mix Analyzer Excel report for mix agents.

Phase 4.0 = skeleton. Phase 4.1+ exposes:

    load_report(path) -> dict
    get_full_mix_metrics(report)        -> Full Mix LUFS, TP, crest, PLR, LRA
    get_per_track_dashboard(report)     -> per-track metrics
    get_anomalies(report, severity=None) -> filtered anomalies
    get_freq_conflicts(report)          -> masking matrix
    get_health_score(report)            -> weighted score + breakdown
    get_sections_timeline(report)       -> section boundaries (Feature 3)

Mirrors how song_loader exposes a sliced API over inspirations.json.
The Excel itself stays untouched — this loader is read-only.

Why a dedicated loader rather than letting each agent open the Excel:
- Single source of truth for sheet/column names (the Excel format
  evolves with mix_analyzer.py versions)
- Caching (parsing 80+ sheet workbooks is non-trivial)
- Consistent slicing — every agent gets the same view
"""
from __future__ import annotations
