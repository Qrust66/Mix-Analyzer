#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Phase F10h — AnalysisConfig dataclass + parser.

4 unit tests, total runtime < 1 sec. Tests verify :

1. AnalysisConfig can be instantiated from each of the 5 RESOLUTION_PRESETS
   with field values that mirror the _analysis_config sheet 1:1
2. cqt_frames_per_beat_at(bpm) scales correctly (at 64 BPM = 2x at_128bpm)
3. DiagnosticReport.analysis_config defaults to None (backward compat)
4. _parse_analysis_config does a full JSON dict roundtrip and rejects
   invalid preset_name + out-of-range peak_threshold_db
"""
from __future__ import annotations

import pytest

from mix_engine.blueprint.schema import (
    AnalysisConfig,
    DiagnosticReport,
    HealthScore,
    FullMixMetrics,
    VALID_PRESET_NAMES,
)
from mix_engine.blueprint.agent_parsers import (
    MixAgentOutputError,
    _parse_analysis_config,
)
from resolution_presets import RESOLUTION_PRESETS


def _build_analysis_config_from_preset(preset, *,
                                        sample_rate: int = 44100,
                                        peak_threshold_db: float = -70.0,
                                        is_shareable: bool = False):
    """Helper : construct AnalysisConfig from a ResolutionPreset, mirroring
    mix_analyzer.py:_build_analysis_config_sheet rows 1:1."""
    return AnalysisConfig(
        preset_name=preset.name,
        stft_n_fft=preset.stft_n_fft,
        stft_hop_samples=preset.stft_hop_samples_at_44k,
        stft_hop_ms_at_44k=preset.stft_hop_ms_at_44k,
        stft_delta_freq_hz_at_44k=preset.stft_delta_freq_hz_at_44k,
        cqt_target_fps=preset.cqt_target_fps,
        cqt_bins_per_octave=preset.cqt_bins_per_octave,
        cqt_n_bins=preset.cqt_n_bins,
        cqt_frames_per_beat_at_128bpm=preset.cqt_frames_per_beat_at_128bpm,
        sample_rate=sample_rate,
        peak_threshold_db=peak_threshold_db,
        is_shareable_version=is_shareable,
        mix_analyzer_version="v2.8.0",
        generated_at="2026-05-03T14:22:18",
    )


class TestAnalysisConfigInstantiation:
    """All 5 presets must round-trip into AnalysisConfig cleanly."""

    @pytest.mark.parametrize("preset_name", sorted(VALID_PRESET_NAMES))
    def test_can_instantiate_from_each_preset(self, preset_name):
        preset = RESOLUTION_PRESETS[preset_name]
        cfg = _build_analysis_config_from_preset(preset)
        assert cfg.preset_name == preset_name
        assert cfg.preset_name in VALID_PRESET_NAMES
        assert cfg.stft_n_fft == preset.stft_n_fft
        assert cfg.cqt_target_fps == preset.cqt_target_fps
        assert cfg.cqt_bins_per_octave == preset.cqt_bins_per_octave
        # is_shareable defaults to False (FULL report)
        assert cfg.is_shareable_version is False


class TestAnalysisConfigDerivedMethods:
    """Pure derivations from stored at-128/at-44k reference values."""

    def test_cqt_frames_per_beat_at_64_bpm_doubles_value(self):
        """At 64 BPM, beats are 2x longer → 2x more frames per beat."""
        preset = RESOLUTION_PRESETS["standard"]
        cfg = _build_analysis_config_from_preset(preset)
        at_128 = cfg.cqt_frames_per_beat_at_128bpm
        at_64 = cfg.cqt_frames_per_beat_at(64.0)
        assert at_64 == pytest.approx(at_128 * 2.0, rel=1e-6)

    def test_cqt_frames_per_beat_at_zero_bpm_raises(self):
        preset = RESOLUTION_PRESETS["standard"]
        cfg = _build_analysis_config_from_preset(preset)
        with pytest.raises(ValueError):
            cfg.cqt_frames_per_beat_at(0.0)

    def test_stft_delta_freq_hz_at_48k_scales(self):
        """At 48 kHz, delta freq is 48000/n_fft = 1.088x the 44100 value."""
        preset = RESOLUTION_PRESETS["ultra"]
        cfg = _build_analysis_config_from_preset(preset)
        at_44k = cfg.stft_delta_freq_hz_at_44k
        at_48k = cfg.stft_delta_freq_hz_at(48000)
        assert at_48k == pytest.approx(at_44k * (48000 / 44100.0), rel=1e-6)


class TestDiagnosticReportBackwardCompat:
    """The new analysis_config field must not break pre-F10h instantiations."""

    def test_diagnostic_report_analysis_config_default_none(self):
        report = DiagnosticReport(
            project_name="x",
            full_mix=FullMixMetrics(
                integrated_lufs=-14.0, true_peak_dbtp=-1.0, crest_factor_db=10.0,
                plr_db=12.0, lra_db=6.0, dominant_band="mid",
                correlation=0.8, stereo_width=0.4, spectral_entropy=4.0,
            ),
            tracks=(),
            anomalies=(),
            health_score=HealthScore(overall=70.0, breakdown=()),
        )
        assert report.analysis_config is None


class TestParseAnalysisConfig:
    """JSON roundtrip + rejection of invalid inputs (parser contract)."""

    def _valid_dict(self):
        return {
            "preset_name": "ultra",
            "stft_n_fft": 16384,
            "stft_hop_samples": 4096,
            "stft_hop_ms_at_44k": 92.879,
            "stft_delta_freq_hz_at_44k": 2.6917,
            "cqt_target_fps": 12,
            "cqt_bins_per_octave": 36,
            "cqt_n_bins": 252,
            "cqt_frames_per_beat_at_128bpm": 5.625,
            "sample_rate": 44100,
            "peak_threshold_db": -65.0,
            "is_shareable_version": False,
            "mix_analyzer_version": "v2.8.0",
            "generated_at": "2026-05-03T14:22:18",
        }

    def test_valid_dict_roundtrips(self):
        cfg = _parse_analysis_config(self._valid_dict(),
                                      where="diagnostic.analysis_config")
        assert cfg.preset_name == "ultra"
        assert cfg.stft_n_fft == 16384
        assert cfg.peak_threshold_db == -65.0
        assert cfg.is_shareable_version is False
        # Derived methods still work after parser reconstruction
        assert cfg.cqt_frames_per_beat_at(128.0) == pytest.approx(5.625, rel=1e-6)

    def test_invalid_preset_name_rejected(self):
        bad = self._valid_dict()
        bad["preset_name"] = "supersonic"
        with pytest.raises(MixAgentOutputError, match="preset_name"):
            _parse_analysis_config(bad, where="diagnostic.analysis_config")

    def test_peak_threshold_out_of_range_rejected(self):
        bad = self._valid_dict()
        bad["peak_threshold_db"] = -100.0
        with pytest.raises(MixAgentOutputError):
            _parse_analysis_config(bad, where="diagnostic.analysis_config")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
