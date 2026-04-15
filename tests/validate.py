#!/usr/bin/env python3
"""
Resonance detection validation harness.

Loads each fixture WAV from fixtures_metadata.json, runs it through
analyze_spectrum() and detect_resonance_anomalies(), and checks the
detected frequencies against the ground-truth expected_anomalies_hz
with +/- 5% tolerance.

Run from repository root:
    python tests/validate.py

Exit code 0 = all fixtures passed, 1 = at least one failure.
"""

import json
import os
import sys

# ---------------------------------------------------------------------------
# Ensure the repo root is on sys.path so `from mix_analyzer import ...` works
# regardless of the working directory.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import numpy as np
import soundfile as sf

# mix_analyzer.py imports tkinter at module level (for the GUI). On headless
# systems where tkinter is unavailable, provide a lightweight stub so the
# analysis functions can still be imported without the GUI.
try:
    import tkinter  # noqa: F401
except ModuleNotFoundError:
    import types

    class _StubMeta(type):
        """Metaclass that makes attribute access on the CLASS return itself."""
        def __getattr__(cls, name):
            return cls

    class _TkStub(metaclass=_StubMeta):
        """Catch-all stub: any attribute access (on the class or instances)
        returns this class, so expressions like tk.Canvas, tk.Frame,
        tk.StringVar, tk.BooleanVar all resolve to a callable."""
        def __init__(self, *a, **kw):
            pass
        def __getattr__(self, name):
            return _TkStub
        def __call__(self, *a, **kw):
            return _TkStub()
        def __bool__(self):
            return False

    class _StubModule(types.ModuleType):
        """Module whose unknown attributes resolve to _TkStub."""
        def __getattr__(self, name):
            # Let standard module attributes fall through normally
            if name.startswith("__") and name.endswith("__"):
                raise AttributeError(name)
            return _TkStub

    for _mod_name in [
        "tkinter", "tkinter.ttk", "tkinter.filedialog",
        "tkinter.messagebox", "tkinter.scrolledtext",
    ]:
        _m = _StubModule(_mod_name)
        _m.__file__ = _mod_name
        _m.__loader__ = None
        _m.__package__ = _mod_name
        _m.__path__ = []
        _m.__spec__ = None
        sys.modules[_mod_name] = _m

from mix_analyzer import analyze_spectrum, detect_resonance_anomalies

# Frequency tolerance for matching detected peaks to expected peaks.
# A detected peak at f_det matches an expected peak at f_exp when
# abs(f_det - f_exp) / f_exp <= FREQ_TOLERANCE (i.e. within 5%).
FREQ_TOLERANCE = 0.05


def load_metadata():
    """Load fixtures_metadata.json from the same directory as this script."""
    meta_path = os.path.join(_SCRIPT_DIR, "fixtures_metadata.json")
    with open(meta_path, "r") as fh:
        return json.load(fh)


def freq_matches(detected_hz, expected_hz, tol=FREQ_TOLERANCE):
    """Return True if detected_hz is within +/- tol of expected_hz."""
    if expected_hz == 0:
        return False
    return abs(detected_hz - expected_hz) / expected_hz <= tol


def validate_fixture(fixture, fixture_dir):
    """
    Validate a single fixture.

    Returns (passed: bool, message: str).
    """
    wav_path = os.path.join(fixture_dir, fixture["file"])
    expected = fixture["expected_anomalies_hz"]
    expected_count = fixture["expected_count"]

    # Load WAV and sum to mono
    audio, sr = sf.read(wav_path)
    if audio.ndim > 1:
        mono = np.mean(audio, axis=1)
    else:
        mono = audio

    # Run the analysis pipeline
    spec = analyze_spectrum(mono, sr)
    detected = detect_resonance_anomalies(spec["spectrum_mean"], spec["freqs"], sr)
    detected_freqs = [f for f, _ in detected]

    # --- Check count ---
    if len(detected_freqs) != expected_count:
        if len(detected_freqs) < expected_count:
            missing = []
            for ef in expected:
                if not any(freq_matches(df, ef) for df in detected_freqs):
                    missing.append(ef)
            return False, (
                f"FAIL -- wrong count (expected {expected_count}, "
                f"got {len(detected_freqs)}); missing {missing}"
            )
        else:
            extra = []
            for df in detected_freqs:
                if not any(freq_matches(df, ef) for ef in expected):
                    extra.append(round(df, 1))
            return False, (
                f"FAIL -- wrong count (expected {expected_count}, "
                f"got {len(detected_freqs)}); extra {extra}"
            )

    # --- Check each expected frequency is matched ---
    unmatched_expected = []
    for ef in expected:
        if not any(freq_matches(df, ef) for df in detected_freqs):
            unmatched_expected.append(ef)

    unmatched_detected = []
    for df in detected_freqs:
        if not any(freq_matches(df, ef) for ef in expected):
            unmatched_detected.append(round(df, 1))

    if unmatched_expected:
        return False, f"FAIL -- missing {unmatched_expected}"
    if unmatched_detected:
        return False, f"FAIL -- extra {unmatched_detected}"

    return True, "PASS"


def main():
    meta = load_metadata()
    fixture_dir = _SCRIPT_DIR
    fixtures = meta["fixtures"]
    total = len(fixtures)
    passed = 0

    print(f"Resonance detection validation — {total} fixtures\n")

    for i, fixture in enumerate(fixtures, 1):
        name = fixture["file"]
        desc = fixture["description"]
        ok, msg = validate_fixture(fixture, fixture_dir)
        status = msg
        if ok:
            passed += 1
        print(f"  [{i}/{total}] {name}")
        print(f"          {desc}")
        print(f"          -> {status}\n")

    print(f"{passed}/{total} fixtures passed.")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
