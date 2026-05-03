#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test for Phase F11 part 2 — skip _track_peak/valley_trajectories
in excel_export_mode='ai_optimized' to deliver a small AI-friendly file.

Pass 2 audit established that these 2 sheets weight 97% of FULL file
size on real projects (Acid Drops : 19 MB on 19.5 MB total). Skipping
them in ai_optimized mode delivers ~95-98% file size reduction without
losing data Tier A agents actually consume.
"""
from __future__ import annotations

import inspect

import pytest

import feature_storage
from feature_storage import build_all_v25_sheets


class TestSkipTrajectoriesAiOptimized:
    """Verify the F11 skip_trajectories param + the gate logic."""

    def test_build_all_v25_sheets_has_skip_trajectories_param(self):
        sig = inspect.signature(build_all_v25_sheets)
        assert "skip_trajectories" in sig.parameters, (
            "F11 part 2 : build_all_v25_sheets must accept "
            "skip_trajectories parameter"
        )
        # Default must be False to preserve v2.7.0 behavior
        assert sig.parameters["skip_trajectories"].default is False, (
            "Backward compat strict : skip_trajectories must default to "
            "False so existing callers (full / globals modes) keep "
            "generating all sheets"
        )

    def test_skip_trajectories_excludes_2_heaviest_sheets(self):
        """When skip_trajectories=True, the 2 build_v25_*_trajectories_sheet
        functions must NOT be called — verified via source inspection
        (avoids constructing a real openpyxl workbook + audio fixture)."""
        src = inspect.getsource(build_all_v25_sheets)
        # The conditional gate must reference both sheet builders
        assert "build_v25_peak_trajectories_sheet" in src
        assert "build_v25_valley_trajectories_sheet" in src
        assert "skip_trajectories" in src
        assert "if skip_trajectories" in src or "if not skip_trajectories" in src, (
            "F11 part 2 : skip_trajectories must gate the 2 trajectory "
            "build calls"
        )

    def test_skip_trajectories_keeps_other_v25_sheets(self):
        """The 4 other v25 sheets (zone_energy, spectral_descriptors,
        crest_by_zone, transients) are small and useful — they must
        STILL be built in ai_optimized mode."""
        src = inspect.getsource(build_all_v25_sheets)
        for kept in ["build_v25_zone_energy_sheet",
                     "build_v25_spectral_descriptors_sheet",
                     "build_v25_crest_by_zone_sheet",
                     "build_v25_transients_sheet"]:
            assert kept in src, (
                f"F11 part 2 : {kept} must still be called regardless "
                f"of skip_trajectories — only the 2 heaviest sheets are "
                f"skipped"
            )


class TestMixAnalyzerGate:
    """Verify mix_analyzer.py:generate_excel_report wires the gate
    correctly : skip_trajectories=True iff export_mode='ai_optimized'."""

    def test_generate_excel_report_threads_export_mode_to_skip_traj(self):
        import mix_analyzer
        src = inspect.getsource(mix_analyzer.generate_excel_report)
        # The gate must reference both export_mode and skip_trajectories
        assert "skip_trajectories" in src, (
            "F11 part 2 : generate_excel_report must thread "
            "skip_trajectories to build_all_v25_sheets"
        )
        assert "export_mode == 'ai_optimized'" in src or \
               "export_mode==\"ai_optimized\"" in src or \
               "export_mode == \"ai_optimized\"" in src, (
            "F11 part 2 : the skip gate must be conditional on "
            "export_mode == 'ai_optimized'"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
