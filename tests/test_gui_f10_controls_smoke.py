#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smoke tests for Phase F10g.5 — GUI tkinter controls for F10 settings
(Mix Analyzer v2.8.0+).

These tests do NOT instantiate a real Tk root (would require display +
heavy mocking). Instead they inspect the source code of MixAnalyzerApp
to verify the 5 F10g.5 tk Variables, the validation block, the new
LabelFrame widget, and the persistence wiring are all present.

Approach (Pass 1 Q5 = "option b smoke") :
- Brittleness is the feature : if someone removes self.resolution_preset
  or renames the LabelFrame label, the test fails immediately.
- Pass 2 audit fix #5 : test on variable NAMES not exact formatting.
- Total runtime < 1 sec.
"""

import inspect

import pytest

import mix_analyzer
from mix_analyzer import MixAnalyzerApp


F10_TK_VARS = [
    'resolution_preset',
    'peak_threshold_db',
    'generate_shareable',
    'shareable_target_mb',
    'shareable_initial_threshold',
]


class TestF10g5GuiControls:
    """Verify the 5 F10g.5 GUI controls are wired into MixAnalyzerApp."""

    def test_all_five_tk_vars_in_init(self):
        """__init__ defines self.<var> for each of the 5 F10 controls."""
        src = inspect.getsource(MixAnalyzerApp.__init__)
        for var in F10_TK_VARS:
            assert f"self.{var}" in src, (
                f"F10g.5 tk Variable self.{var} missing from "
                f"MixAnalyzerApp.__init__"
            )

    def test_resolution_labelframe_exists_in_build_analysis_tab(self):
        """The new 'Resolution & Output' LabelFrame is built somewhere
        in MixAnalyzerApp (locating which method is brittle, scan the
        whole class source)."""
        src = inspect.getsource(MixAnalyzerApp)
        assert "Resolution & Output" in src, (
            "F10g.5 LabelFrame text 'Resolution & Output' not found in "
            "MixAnalyzerApp source — the new widget block was likely "
            "removed or renamed."
        )

    def test_validation_fallback_in_do_analysis(self):
        """_do_analysis (the worker called from _run_analysis thread) uses
        get_preset_by_name + validate_peak_threshold_db (Pass 2 audit fix
        #2 — defensive validation with fallback)."""
        src = inspect.getsource(MixAnalyzerApp._do_analysis)
        assert "get_preset_by_name" in src, (
            "F10g.5 audit fix #2 : _do_analysis must call "
            "get_preset_by_name to validate the GUI preset selection"
        )
        assert "validate_peak_threshold_db" in src, (
            "F10g.5 audit fix #2 : _do_analysis must call "
            "validate_peak_threshold_db to validate the GUI threshold"
        )

    def test_shareable_call_in_do_analysis(self):
        """_do_analysis conditionally calls generate_shareable_report
        based on self.generate_shareable.get()."""
        src = inspect.getsource(MixAnalyzerApp._do_analysis)
        assert "generate_shareable_report" in src, (
            "F10g.5 : _do_analysis must call generate_shareable_report "
            "when self.generate_shareable is True"
        )
        assert "self.generate_shareable.get()" in src, (
            "F10g.5 : conditional gate on self.generate_shareable.get() "
            "missing from _do_analysis"
        )

    def test_save_config_persists_all_five_keys(self):
        """_save_config writes the 5 F10g.5 keys to mix_analyzer_config.json
        (per-project persistence per Pass 2 audit clarification)."""
        src = inspect.getsource(MixAnalyzerApp._save_config)
        for var in F10_TK_VARS:
            assert f"self.{var}.get()" in src, (
                f"F10g.5 persistence : _save_config must serialize "
                f"self.{var}.get() into the per-project config dict"
            )

    def test_imports_resolution_helpers(self):
        """mix_analyzer.py imports the validation helpers from
        resolution_presets (added in F10g.5 alongside the existing
        F10c imports)."""
        for symbol in ['get_preset_by_name', 'validate_peak_threshold_db',
                       'InvalidPresetError', 'InvalidThresholdError']:
            assert hasattr(mix_analyzer, symbol), (
                f"F10g.5 : mix_analyzer.py must import {symbol} from "
                f"resolution_presets (used by the GUI validation block)"
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
