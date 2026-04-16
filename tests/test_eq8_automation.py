#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for eq8_automation.py — EQ8 automation engine.

Uses a synthetic minimal ALS fixture (gzipped XML) rather than real
Ableton project files.
"""

import gzip
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eq8_automation import (
    _freq_to_eq8_value,
    _gain_to_eq8_value,
    _q_to_eq8_value,
    _find_available_band,
    _remove_existing_envelope,
    _feature_to_breakpoints,
    _extract_tempo,
    TrackNotFoundError,
    EQ8SlotFullError,
    AutomationReport,
    write_adaptive_hpf,
    write_adaptive_lpf,
    write_safety_hpf,
    write_dynamic_notch,
    write_dynamic_bell_cut,
    write_resonance_suppression,
    write_adaptive_presence_boost,
    write_adaptive_air_boost,
    detect_masking,
    write_masking_reciprocal_cuts,
    write_targeted_sidechain_eq,
    write_transient_aware_cut,
    write_section_aware_eq,
    write_dynamic_deesser,
    MaskingReport,
)
from spectral_evolution import PeakTrajectory, TransientEvent
from als_utils import (
    parse_als,
    find_track_by_name,
    get_eq8_band,
    get_automation_target_id,
)


# ---------------------------------------------------------------------------
# Fixture helper
# ---------------------------------------------------------------------------

def _create_minimal_als(path, track_names=None, tempo=128.0):
    """Create a minimal valid .als file with EQ8 on each track.

    Each EQ8 has 8 bands, all with IsOn=false and Gain=0.
    Returns the path for chaining.
    """
    track_names = track_names or ["Track1", "Track2"]

    root = ET.Element("Ableton")
    root.set("Creator", "Test")
    root.set("SchemaChangeCount", "1")

    live_set = ET.SubElement(root, "LiveSet")

    # Tempo
    tempo_container = ET.SubElement(live_set, "Tempo")
    ET.SubElement(tempo_container, "Manual").set("Value", str(tempo))

    # Tracks
    tracks = ET.SubElement(live_set, "Tracks")

    next_id = 1000

    for _ti, name in enumerate(track_names):
        track = ET.SubElement(tracks, "AudioTrack")
        track.set("Id", str(next_id))
        next_id += 1

        ET.SubElement(track, "EffectiveName").set("Value", name)

        # DeviceChain/DeviceChain/Devices
        dc_outer = ET.SubElement(track, "DeviceChain")
        dc_inner = ET.SubElement(dc_outer, "DeviceChain")
        devices = ET.SubElement(dc_inner, "Devices")

        # EQ8
        eq8 = ET.SubElement(devices, "Eq8")
        eq8.set("Id", str(next_id))
        next_id += 1

        ET.SubElement(eq8, "LomId").set("Value", "0")

        eq8_ison = ET.SubElement(eq8, "IsOn")
        ET.SubElement(eq8_ison, "Manual").set("Value", "true")
        ET.SubElement(eq8_ison, "AutomationTarget").set("Id", str(next_id))
        next_id += 1

        default_freqs = [80, 200, 400, 1000, 2500, 5000, 10000, 16000]

        for band_idx in range(8):
            band = ET.SubElement(eq8, f"Bands.{band_idx}")
            param_a = ET.SubElement(band, "ParameterA")

            ison = ET.SubElement(param_a, "IsOn")
            ET.SubElement(ison, "Manual").set("Value", "false")
            ET.SubElement(ison, "AutomationTarget").set("Id", str(next_id))
            next_id += 1

            mode = ET.SubElement(param_a, "Mode")
            ET.SubElement(mode, "Manual").set("Value", "3")
            ET.SubElement(mode, "AutomationTarget").set("Id", str(next_id))
            next_id += 1

            freq = ET.SubElement(param_a, "Freq")
            ET.SubElement(freq, "Manual").set(
                "Value", str(float(default_freqs[band_idx]))
            )
            ET.SubElement(freq, "AutomationTarget").set("Id", str(next_id))
            next_id += 1

            gain = ET.SubElement(param_a, "Gain")
            ET.SubElement(gain, "Manual").set("Value", "0")
            ET.SubElement(gain, "AutomationTarget").set("Id", str(next_id))
            next_id += 1

            q_elem = ET.SubElement(param_a, "Q")
            ET.SubElement(q_elem, "Manual").set("Value", "0.7071067690849304")
            ET.SubElement(q_elem, "AutomationTarget").set("Id", str(next_id))
            next_id += 1

        # AutomationEnvelopes
        auto_env = ET.SubElement(track, "AutomationEnvelopes")
        ET.SubElement(auto_env, "Envelopes")

    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)
    with gzip.open(str(path), "wb") as f:
        f.write(xml_str.encode("utf-8"))

    return path


# ---------------------------------------------------------------------------
# Tests — Value conversion helpers
# ---------------------------------------------------------------------------

class TestFreqToEq8Value:
    def test_440hz(self):
        assert _freq_to_eq8_value(440.0) == 440.0

    def test_100hz(self):
        assert _freq_to_eq8_value(100.0) == 100.0

    def test_10000hz(self):
        assert _freq_to_eq8_value(10000.0) == 10000.0

    def test_clamp_low(self):
        assert _freq_to_eq8_value(1.0) == 10.0

    def test_clamp_high(self):
        assert _freq_to_eq8_value(30000.0) == 22050.0


class TestGainToEq8Value:
    def test_zero(self):
        assert _gain_to_eq8_value(0.0) == 0.0

    def test_clamp_low(self):
        assert _gain_to_eq8_value(-20.0) == -15.0

    def test_clamp_high(self):
        assert _gain_to_eq8_value(20.0) == 15.0


class TestQToEq8Value:
    def test_normal(self):
        assert _q_to_eq8_value(1.0) == 1.0

    def test_clamp_low(self):
        assert _q_to_eq8_value(0.01) == 0.1

    def test_clamp_high(self):
        assert _q_to_eq8_value(25.0) == 18.0


# ---------------------------------------------------------------------------
# Tests — Tempo extraction
# ---------------------------------------------------------------------------

class TestExtractTempo:
    def test_reads_tempo(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path, tempo=140.0)
        tree = parse_als(str(als_path))
        assert _extract_tempo(tree) == 140.0

    def test_default_tempo(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path, tempo=128.0)
        tree = parse_als(str(als_path))
        assert _extract_tempo(tree) == 128.0


# ---------------------------------------------------------------------------
# Tests — Feature to breakpoints
# ---------------------------------------------------------------------------

class TestFeatureToBreakpoints:
    def test_converts_seconds_to_beats(self):
        values = np.array([100.0, 200.0, 300.0])
        times = np.array([0.0, 1.0, 2.0])
        tempo = 120.0
        bps = _feature_to_breakpoints(values, times, tempo)
        assert len(bps) == 3
        assert bps[0] == (0.0, 100.0)
        assert bps[1] == (2.0, 200.0)
        assert bps[2] == (4.0, 300.0)

    def test_thins_if_too_many(self):
        values = np.ones(1000)
        times = np.linspace(0, 100, 1000)
        bps = _feature_to_breakpoints(values, times, 120.0, max_points=50)
        assert len(bps) <= 50


# ---------------------------------------------------------------------------
# Tests — Find available band
# ---------------------------------------------------------------------------

class TestFindAvailableBand:
    def test_all_free_returns_band_1(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)
        tree = parse_als(str(als_path))
        track = tree.getroot().find(".//AudioTrack")
        eq8 = track.find(".//Eq8")
        band = _find_available_band(eq8, track)
        assert band == 1

    def test_band_1_occupied_returns_band_2(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)
        tree = parse_als(str(als_path))
        track = tree.getroot().find(".//AudioTrack")
        eq8 = track.find(".//Eq8")

        band1_param = get_eq8_band(eq8, 1)
        freq_target_id = get_automation_target_id(band1_param, "Freq")

        envelopes = track.find("AutomationEnvelopes/Envelopes")
        env = ET.SubElement(envelopes, "AutomationEnvelope")
        target = ET.SubElement(env, "EnvelopeTarget")
        ET.SubElement(target, "PointeeId").set("Value", freq_target_id)

        band = _find_available_band(eq8, track)
        assert band == 2

    def test_all_occupied_raises(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)
        tree = parse_als(str(als_path))
        track = tree.getroot().find(".//AudioTrack")
        eq8 = track.find(".//Eq8")

        for i in range(8):
            band_param = get_eq8_band(eq8, i)
            gain_manual = band_param.find("Gain/Manual")
            gain_manual.set("Value", "-3.0")

        with pytest.raises(EQ8SlotFullError):
            _find_available_band(eq8, track)

    def test_exclude_skips_bands(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)
        tree = parse_als(str(als_path))
        track = tree.getroot().find(".//AudioTrack")
        eq8 = track.find(".//Eq8")

        band = _find_available_band(eq8, track, exclude=[1, 2, 3])
        assert band == 4


# ---------------------------------------------------------------------------
# Tests — Remove existing envelope
# ---------------------------------------------------------------------------

class TestRemoveExistingEnvelope:
    def test_removes_matching_envelope(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)
        tree = parse_als(str(als_path))
        track = tree.getroot().find(".//AudioTrack")

        envelopes = track.find("AutomationEnvelopes/Envelopes")
        env = ET.SubElement(envelopes, "AutomationEnvelope")
        target = ET.SubElement(env, "EnvelopeTarget")
        ET.SubElement(target, "PointeeId").set("Value", "99999")

        assert len(envelopes.findall("AutomationEnvelope")) == 1
        removed = _remove_existing_envelope(track, "99999")
        assert removed is True
        assert len(envelopes.findall("AutomationEnvelope")) == 0

    def test_no_match_returns_false(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)
        tree = parse_als(str(als_path))
        track = tree.getroot().find(".//AudioTrack")

        removed = _remove_existing_envelope(track, "99999")
        assert removed is False

    def test_preserves_other_envelopes(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)
        tree = parse_als(str(als_path))
        track = tree.getroot().find(".//AudioTrack")

        envelopes = track.find("AutomationEnvelopes/Envelopes")
        for pid in ["11111", "22222", "33333"]:
            env = ET.SubElement(envelopes, "AutomationEnvelope")
            target = ET.SubElement(env, "EnvelopeTarget")
            ET.SubElement(target, "PointeeId").set("Value", pid)

        assert len(envelopes.findall("AutomationEnvelope")) == 3
        _remove_existing_envelope(track, "22222")
        assert len(envelopes.findall("AutomationEnvelope")) == 2

        remaining_ids = []
        for env in envelopes.findall("AutomationEnvelope"):
            p = env.find("EnvelopeTarget/PointeeId")
            remaining_ids.append(p.get("Value"))
        assert "11111" in remaining_ids
        assert "33333" in remaining_ids
        assert "22222" not in remaining_ids


# ---------------------------------------------------------------------------
# Tests — Phase 3: Adaptive filters
# ---------------------------------------------------------------------------

class TestAdaptiveHPF:
    def test_writes_envelope(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        rolloff = np.full(10, 80.0)
        times = np.linspace(0, 5, 10)

        report = write_adaptive_hpf(als_path, "Track1", rolloff, times, band_index=1)
        assert report.success
        assert report.breakpoints_written == 10
        assert report.eq8_band_index == 1

        tree = parse_als(str(als_path))
        track = find_track_by_name(tree, "Track1")
        eq8 = track.find(".//Eq8")
        band_param = get_eq8_band(eq8, 1)

        mode_val = band_param.find("Mode/Manual").get("Value")
        assert mode_val == "0"

        freq_target_id = get_automation_target_id(band_param, "Freq")
        env_count = sum(
            1 for env in track.iter("AutomationEnvelope")
            if env.find("EnvelopeTarget/PointeeId") is not None
            and env.find("EnvelopeTarget/PointeeId").get("Value") == freq_target_id
        )
        assert env_count == 1

    def test_safety_margin_applied(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        rolloff = np.full(5, 100.0)
        times = np.linspace(0, 2, 5)

        write_adaptive_hpf(als_path, "Track1", rolloff, times,
                           safety_hz=20.0, band_index=1)

        tree = parse_als(str(als_path))
        track = find_track_by_name(tree, "Track1")
        eq8 = track.find(".//Eq8")
        band_param = get_eq8_band(eq8, 1)
        freq_target_id = get_automation_target_id(band_param, "Freq")

        for env in track.iter("AutomationEnvelope"):
            pointee = env.find("EnvelopeTarget/PointeeId")
            if pointee is not None and pointee.get("Value") == freq_target_id:
                events = env.findall(".//FloatEvent")
                for ev in events:
                    t = float(ev.get("Time"))
                    if t > 0:
                        assert float(ev.get("Value")) == pytest.approx(80.0, abs=1.0)

    def test_track_not_found_raises(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)
        with pytest.raises(TrackNotFoundError):
            write_adaptive_hpf(als_path, "NonExistent",
                               np.ones(5), np.linspace(0, 2, 5))


class TestAdaptiveLPF:
    def test_writes_envelope(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        rolloff = np.full(10, 12000.0)
        times = np.linspace(0, 5, 10)

        report = write_adaptive_lpf(als_path, "Track1", rolloff, times, band_index=2)
        assert report.success
        assert report.breakpoints_written == 10

        tree = parse_als(str(als_path))
        track = find_track_by_name(tree, "Track1")
        eq8 = track.find(".//Eq8")
        band_param = get_eq8_band(eq8, 2)

        mode_val = band_param.find("Mode/Manual").get("Value")
        assert mode_val == "7"

    def test_safety_margin_applied(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        rolloff = np.full(5, 10000.0)
        times = np.linspace(0, 2, 5)

        write_adaptive_lpf(als_path, "Track1", rolloff, times,
                           safety_hz=1000.0, band_index=2)

        tree = parse_als(str(als_path))
        track = find_track_by_name(tree, "Track1")
        eq8 = track.find(".//Eq8")
        band_param = get_eq8_band(eq8, 2)
        freq_target_id = get_automation_target_id(band_param, "Freq")

        for env in track.iter("AutomationEnvelope"):
            pointee = env.find("EnvelopeTarget/PointeeId")
            if pointee is not None and pointee.get("Value") == freq_target_id:
                events = env.findall(".//FloatEvent")
                for ev in events:
                    if float(ev.get("Time")) > 0:
                        assert float(ev.get("Value")) == pytest.approx(11000.0, abs=1.0)


class TestSafetyHPF:
    def test_toggles_on_low_energy(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        sub_energy = np.array([-40.0, -40.0, -20.0, -20.0, -40.0])
        times = np.linspace(0, 2, 5)

        report = write_safety_hpf(als_path, "Track1", sub_energy, times,
                                  threshold_db=-30.0, band_index=3)
        assert report.success

        tree = parse_als(str(als_path))
        track = find_track_by_name(tree, "Track1")
        eq8 = track.find(".//Eq8")
        band_param = get_eq8_band(eq8, 3)
        ison_target_id = get_automation_target_id(band_param, "IsOn")

        for env in track.iter("AutomationEnvelope"):
            pointee = env.find("EnvelopeTarget/PointeeId")
            if pointee is not None and pointee.get("Value") == ison_target_id:
                events = env.findall(".//FloatEvent")
                real_events = [e for e in events if float(e.get("Time")) >= 0]
                values = [float(e.get("Value")) for e in real_events]
                assert values == [1.0, 1.0, 0.0, 0.0, 1.0]


# ---------------------------------------------------------------------------
# Tests — Phase 4: Dynamic notches/bells
# ---------------------------------------------------------------------------

class TestDynamicNotch:
    def test_tracks_frequency(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        points = [(i, 500.0 + i * 10, -30.0) for i in range(20)]
        traj = PeakTrajectory(points=points)
        times = np.linspace(0, 10, 20)

        report = write_dynamic_notch(als_path, "Track1", traj, times,
                                     reduction_db=-4.0, band_index=1)
        assert report.success
        assert report.breakpoints_written > 0

        tree = parse_als(str(als_path))
        track = find_track_by_name(tree, "Track1")
        eq8 = track.find(".//Eq8")
        band_param = get_eq8_band(eq8, 1)
        assert band_param.find("Mode/Manual").get("Value") == "4"

        freq_target_id = get_automation_target_id(band_param, "Freq")
        gain_target_id = get_automation_target_id(band_param, "Gain")

        freq_envs = sum(
            1 for env in track.iter("AutomationEnvelope")
            if env.find("EnvelopeTarget/PointeeId") is not None
            and env.find("EnvelopeTarget/PointeeId").get("Value") == freq_target_id
        )
        gain_envs = sum(
            1 for env in track.iter("AutomationEnvelope")
            if env.find("EnvelopeTarget/PointeeId") is not None
            and env.find("EnvelopeTarget/PointeeId").get("Value") == gain_target_id
        )
        assert freq_envs == 1
        assert gain_envs == 1


class TestDynamicBellCut:
    def test_proportional_cut(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        energy = np.array([-10.0, -15.0, -25.0, -30.0, -10.0])
        times = np.linspace(0, 2, 5)

        report = write_dynamic_bell_cut(
            als_path, "Track1", energy, times,
            zone_center_hz=1000.0, threshold_db=-20.0,
            max_cut_db=-6.0, band_index=2,
        )
        assert report.success

        tree = parse_als(str(als_path))
        track = find_track_by_name(tree, "Track1")
        eq8 = track.find(".//Eq8")
        band_param = get_eq8_band(eq8, 2)
        assert band_param.find("Mode/Manual").get("Value") == "3"

        gain_target_id = get_automation_target_id(band_param, "Gain")
        for env in track.iter("AutomationEnvelope"):
            pointee = env.find("EnvelopeTarget/PointeeId")
            if pointee is not None and pointee.get("Value") == gain_target_id:
                events = env.findall(".//FloatEvent")
                real = [e for e in events if float(e.get("Time")) >= 0]
                vals = [float(e.get("Value")) for e in real]
                assert vals[0] < 0, "Should cut when energy > threshold"
                assert vals[2] == 0.0, "No cut when energy < threshold"


class TestResonanceSuppression:
    def test_multi_band(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        trajs = []
        for base_freq in [500.0, 1500.0, 4000.0]:
            points = [(i, base_freq, -20.0) for i in range(20)]
            trajs.append(PeakTrajectory(points=points))

        times = np.linspace(0, 10, 20)

        reports = write_resonance_suppression(
            als_path, "Track1", trajs, times,
            sensitivity=0.5, max_bands=3,
        )
        assert len(reports) == 3
        bands_used = {r.eq8_band_index for r in reports}
        assert len(bands_used) == 3
        for r in reports:
            assert r.success
            assert r.breakpoints_written > 0

    def test_no_peaks_returns_empty_report(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        short_traj = PeakTrajectory(points=[(0, 500.0, -20.0)])
        times = np.linspace(0, 5, 10)

        reports = write_resonance_suppression(
            als_path, "Track1", [short_traj], times,
        )
        assert len(reports) == 1
        assert reports[0].breakpoints_written == 0
        assert "No resonant peaks found" in reports[0].warnings


# ---------------------------------------------------------------------------
# Tests — Phase 5: Adaptive boosts
# ---------------------------------------------------------------------------

class TestAdaptivePresenceBoost:
    def test_engages_when_low(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        energy = np.array([-25.0, -25.0, -10.0, -10.0, -25.0])
        times = np.linspace(0, 2, 5)

        report = write_adaptive_presence_boost(
            als_path, "Track1", energy, times,
            threshold_db=-18.0, max_boost_db=3.0, band_index=4,
        )
        assert report.success

        tree = parse_als(str(als_path))
        track = find_track_by_name(tree, "Track1")
        eq8 = track.find(".//Eq8")
        band_param = get_eq8_band(eq8, 4)
        assert band_param.find("Mode/Manual").get("Value") == "3"

        gain_target_id = get_automation_target_id(band_param, "Gain")
        for env in track.iter("AutomationEnvelope"):
            pointee = env.find("EnvelopeTarget/PointeeId")
            if pointee is not None and pointee.get("Value") == gain_target_id:
                events = env.findall(".//FloatEvent")
                real = [e for e in events if float(e.get("Time")) >= 0]
                vals = [float(e.get("Value")) for e in real]
                assert vals[0] > 0, "Should boost when energy is low"
                assert vals[2] == 0.0, "No boost when energy is high"

    def test_respects_max_boost(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        energy = np.full(5, -50.0)
        times = np.linspace(0, 2, 5)

        write_adaptive_presence_boost(
            als_path, "Track1", energy, times,
            threshold_db=-18.0, max_boost_db=3.0, band_index=4,
        )

        tree = parse_als(str(als_path))
        track = find_track_by_name(tree, "Track1")
        eq8 = track.find(".//Eq8")
        band_param = get_eq8_band(eq8, 4)
        gain_target_id = get_automation_target_id(band_param, "Gain")

        for env in track.iter("AutomationEnvelope"):
            pointee = env.find("EnvelopeTarget/PointeeId")
            if pointee is not None and pointee.get("Value") == gain_target_id:
                events = env.findall(".//FloatEvent")
                for e in events:
                    assert float(e.get("Value")) <= 3.0


class TestAdaptiveAirBoost:
    def test_follows_rolloff(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        rolloff = np.array([12000.0, 6000.0, 4000.0, 10000.0, 12000.0])
        times = np.linspace(0, 2, 5)

        report = write_adaptive_air_boost(
            als_path, "Track1", rolloff, times,
            threshold_hz=8000.0, max_boost_db=2.0, band_index=5,
        )
        assert report.success

        tree = parse_als(str(als_path))
        track = find_track_by_name(tree, "Track1")
        eq8 = track.find(".//Eq8")
        band_param = get_eq8_band(eq8, 5)
        assert band_param.find("Mode/Manual").get("Value") == "5"

        gain_target_id = get_automation_target_id(band_param, "Gain")
        for env in track.iter("AutomationEnvelope"):
            pointee = env.find("EnvelopeTarget/PointeeId")
            if pointee is not None and pointee.get("Value") == gain_target_id:
                events = env.findall(".//FloatEvent")
                real = [e for e in events if float(e.get("Time")) >= 0]
                vals = [float(e.get("Value")) for e in real]
                assert vals[0] == 0.0, "No boost when rolloff is high"
                assert vals[1] > 0, "Should boost when rolloff is low"


# ---------------------------------------------------------------------------
# Tests — Phase 6: Cross-track masking
# ---------------------------------------------------------------------------

class TestDetectMasking:
    def test_identifies_overlap(self):
        times = np.linspace(0, 5, 10)
        a_energy = {"low": np.full(10, -10.0), "mud": np.full(10, -10.0)}
        b_energy = {"low": np.full(10, -10.0), "mud": np.full(10, -50.0)}

        report = detect_masking(a_energy, b_energy, times,
                                zones=["low", "mud"])

        assert "low" in report.scores
        assert "mud" in report.scores
        assert float(np.mean(report.scores["low"])) > 0.5
        assert float(np.mean(report.scores["mud"])) < 0.1
        assert report.severity > 0

    def test_no_masking_when_one_silent(self):
        times = np.linspace(0, 5, 10)
        a = {"low": np.full(10, -10.0)}
        b = {"low": np.full(10, -100.0)}

        report = detect_masking(a, b, times, zones=["low"])
        assert float(np.mean(report.scores["low"])) < 0.01


class TestMaskingReciprocalCuts:
    def test_both_tracks_get_cuts(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        times = np.linspace(0, 5, 10)
        scores = {"low": np.full(10, 0.8)}
        masking = MaskingReport(
            zones=["low"], scores=scores, severity=0.8, times=times,
        )

        ra, rb = write_masking_reciprocal_cuts(
            als_path, "Track1", "Track2", masking,
            zone_center_hz=200.0, times=times, reduction_db=-3.0,
            band_index_a=1, band_index_b=1,
        )
        assert ra.success and rb.success
        assert ra.breakpoints_written > 0
        assert rb.breakpoints_written > 0


class TestSidechainEQ:
    def test_follows_trigger(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        trigger = np.array([-30.0, -10.0, -5.0, -30.0, -30.0])
        times = np.linspace(0, 2, 5)

        report = write_targeted_sidechain_eq(
            als_path, "Track1", trigger, times,
            zone_center_hz=200.0, reduction_db=-6.0,
            threshold_db=-20.0, band_index=3,
        )
        assert report.success

        tree = parse_als(str(als_path))
        track = find_track_by_name(tree, "Track1")
        eq8 = track.find(".//Eq8")
        band_param = get_eq8_band(eq8, 3)
        gain_target_id = get_automation_target_id(band_param, "Gain")

        for env in track.iter("AutomationEnvelope"):
            pointee = env.find("EnvelopeTarget/PointeeId")
            if pointee is not None and pointee.get("Value") == gain_target_id:
                events = env.findall(".//FloatEvent")
                real = [e for e in events if float(e.get("Time")) >= 0]
                vals = [float(e.get("Value")) for e in real]
                assert vals[0] == 0.0, "No cut when trigger is low"
                assert vals[2] < 0, "Should cut when trigger is high"


# ---------------------------------------------------------------------------
# Tests — Phase 7: Events / vocal
# ---------------------------------------------------------------------------

class TestTransientAwareCut:
    def test_releases_on_attack(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        times = np.linspace(0, 5, 30)
        transients = [
            TransientEvent(frame_idx=10, time_sec=1.67,
                           dominant_zone="mid", magnitude_db=5.0),
        ]

        report = write_transient_aware_cut(
            als_path, "Track1", base_cut_db=-4.0, freq_hz=1000.0,
            transient_events=transients, times=times,
            release_ms=100.0, band_index=1,
        )
        assert report.success

        tree = parse_als(str(als_path))
        track = find_track_by_name(tree, "Track1")
        eq8 = track.find(".//Eq8")
        band_param = get_eq8_band(eq8, 1)
        gain_target_id = get_automation_target_id(band_param, "Gain")

        for env in track.iter("AutomationEnvelope"):
            pointee = env.find("EnvelopeTarget/PointeeId")
            if pointee is not None and pointee.get("Value") == gain_target_id:
                events = env.findall(".//FloatEvent")
                real = [e for e in events if float(e.get("Time")) >= 0]
                vals = [float(e.get("Value")) for e in real]
                assert vals[10] == 0.0, "Gain should be 0 at transient"
                assert vals[0] < 0, "Base cut should be active elsewhere"


class TestSectionAwareEQ:
    def test_creates_steps(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        delta = np.array([0.0, 0.1, 0.1, 0.5, 0.1, 0.1, 0.1, 0.6, 0.1, 0.1])
        times = np.linspace(0, 5, 10)

        report = write_section_aware_eq(
            als_path, "Track1", delta, times,
            threshold=0.3, band_index=2,
        )
        assert report.success
        assert report.breakpoints_written > 0


class TestDynamicDeesser:
    def test_activates_on_sibilance(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        sibilance = np.array([-25.0, -25.0, -10.0, -10.0, -25.0])
        times = np.linspace(0, 2, 5)

        report = write_dynamic_deesser(
            als_path, "Track1", sibilance, times,
            threshold_db=-18.0, reduction_db=-4.0, band_index=4,
        )
        assert report.success

        tree = parse_als(str(als_path))
        track = find_track_by_name(tree, "Track1")
        eq8 = track.find(".//Eq8")
        band_param = get_eq8_band(eq8, 4)
        gain_target_id = get_automation_target_id(band_param, "Gain")

        for env in track.iter("AutomationEnvelope"):
            pointee = env.find("EnvelopeTarget/PointeeId")
            if pointee is not None and pointee.get("Value") == gain_target_id:
                events = env.findall(".//FloatEvent")
                real = [e for e in events if float(e.get("Time")) >= 0]
                vals = [float(e.get("Value")) for e in real]
                assert vals[0] == 0.0, "No cut when sibilance is low"
                assert vals[2] == -4.0, "Full cut when sibilance exceeds threshold"


class TestIdempotency:
    def test_hpf_does_not_duplicate(self, tmp_path):
        als_path = tmp_path / "test.als"
        _create_minimal_als(als_path)

        rolloff = np.full(10, 80.0)
        times = np.linspace(0, 5, 10)

        write_adaptive_hpf(als_path, "Track1", rolloff, times, band_index=1)
        write_adaptive_hpf(als_path, "Track1", rolloff, times, band_index=1)

        tree = parse_als(str(als_path))
        track = find_track_by_name(tree, "Track1")
        eq8 = track.find(".//Eq8")
        band_param = get_eq8_band(eq8, 1)
        freq_target_id = get_automation_target_id(band_param, "Freq")

        count = sum(
            1 for env in track.iter("AutomationEnvelope")
            if env.find("EnvelopeTarget/PointeeId") is not None
            and env.find("EnvelopeTarget/PointeeId").get("Value") == freq_target_id
        )
        assert count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
