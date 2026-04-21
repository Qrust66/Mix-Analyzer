#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration test for Feature 3.6 B1 wired into the main pipeline (v2.7.0).

This test does not run ``generate_excel_report`` end-to-end — that would
drag in tkinter + librosa pipeline for a smoke check worth a few
seconds. Instead it exercises the same sequence the wiring block in
``mix_analyzer.py`` does, in the exact order:

    build_sections_timeline_sheet(...)     # persists section.conflicts
        -> for s in sections:
               detect_masking_conflicts(s, all_tracks_zone_energy)
        -> dump_diagnostics_to_json(diagnostics, <als_stem>_diagnostics.json)

and verifies the artefact on disk matches the shape the user will see
next to their `.als`. Also verifies the stamping list contains
``cde_engine.py`` so future module renames are caught.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import List

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import Workbook  # noqa: E402

from section_detector import (  # noqa: E402
    Section,
    build_sections_timeline_sheet,
    get_zone_order,
)
from cde_engine import (  # noqa: E402
    detect_masking_conflicts,
    dump_diagnostics_to_json,
)


def _make_section(index: int, start: int, end: int, total_energy_db: float,
                  name: str = None) -> Section:
    return Section(
        index=index,
        name=name or f"Section {index}",
        start_bucket=start,
        end_bucket=end,
        start_seconds=float(start),
        end_seconds=float(end),
        start_beats=float(start * 2),
        end_beats=float(end * 2),
        total_energy_db=total_energy_db,
    )


def _zone_arrays_for(level_db: float, n_frames: int,
                     zones_with_energy: List[str]) -> dict:
    zones = {z: np.full(n_frames, -120.0, dtype=float)
             for z in get_zone_order()}
    for z in zones_with_energy:
        zones[z] = np.full(n_frames, float(level_db), dtype=float)
    return zones


def test_pipeline_produces_diagnostics_json_next_to_als(tmp_path: Path):
    """Mirror of the mix_analyzer.py wiring: build the timeline sheet
    (which now persists section.conflicts), then iterate sections
    through the CDE and dump JSON next to a simulated .als path.
    """
    n = 30
    sections = [
        _make_section(1, 0, n - 1, total_energy_db=-10.0, name="Drop 1"),
    ]
    # Two close-level tracks in the same zone → at least one conflict.
    all_tracks = {
        "Kick 1":   _zone_arrays_for(-5.0, n, ["low"]),
        "Sub Bass": _zone_arrays_for(-6.0, n, ["low"]),
    }

    wb = Workbook()
    build_sections_timeline_sheet(
        workbook=wb, sections=sections,
        all_tracks_zone_energy=all_tracks,
    )
    # B1a persistence must kick in — conflicts on the Section instance.
    assert sections[0].conflicts, "build_sheet must persist conflicts"

    # Mirror of the mix_analyzer wiring block.
    diagnostics = []
    for s in sections:
        diagnostics.extend(detect_masking_conflicts(
            s, all_tracks_zone_energy=all_tracks,
        ))
    assert diagnostics, "the detector must produce at least one diagnostic"

    als_path = tmp_path / "TestProject.als"
    als_path.write_bytes(b"")  # placeholder, the dumper only needs the stem
    json_path = als_path.with_name(f"{als_path.stem}_diagnostics.json")
    dump_diagnostics_to_json(diagnostics, json_path)

    assert json_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["diagnostic_count"] == len(diagnostics)
    assert payload["diagnostics"][0]["issue_type"] == "masking_conflict"
    # Wiring contract: the JSON filename follows <als_stem>_diagnostics.json.
    assert json_path.name == "TestProject_diagnostics.json"


# The remaining two tests read ``mix_analyzer.py`` as text so they do
# not drag in tkinter (which is absent from some headless environments
# like CI runners). A full import would require a GUI stack the CDE
# feature does not depend on.

_MIX_ANALYZER_SRC = Path(__file__).resolve().parent.parent / "mix_analyzer.py"


def test_cde_engine_is_in_the_build_stamped_modules_list():
    """v2.7.0 wiring adds cde_engine.py to the Index Build Info stamp.
    This test guards the convention — if someone removes it, the Index
    sheet stops showing the CDE hash and we silently lose traceability.
    """
    src = _MIX_ANALYZER_SRC.read_text(encoding="utf-8")
    assert "_BUILD_STAMPED_MODULES" in src, (
        "expected the stamped-modules list to exist"
    )
    assert "'cde_engine.py'" in src, (
        "cde_engine.py must appear in _BUILD_STAMPED_MODULES"
    )


def test_version_is_bumped_to_2_7_0():
    """v2.7.0 bump — the canonical VERSION constant and the cde_engine
    docstring tag must be in lockstep per CLAUDE.md."""
    import cde_engine  # noqa: E402

    src = _MIX_ANALYZER_SRC.read_text(encoding="utf-8")
    assert "VERSION = '2.7.0'" in src, (
        "mix_analyzer.VERSION must be '2.7.0'"
    )
    # cde_engine carries its version tag in the module docstring.
    assert "v2.7.0" in (cde_engine.__doc__ or "")
