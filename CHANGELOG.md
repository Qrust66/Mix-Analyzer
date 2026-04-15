## [1.6.1] - 2026-04-15

### Fixed
- Resonance anomaly detection no longer generates false positives on tracks 
  with naturally concentrated spectra (percussive instruments with tonal 
  modes, claps, filtered synths). The detector now compares each candidate 
  peak to its local spectral contour (median over a ±1/3 octave window) 
  instead of the global spectrum maximum.
- Lowered resonance detection frequency floor from 100 Hz to 60 Hz to cover 
  bass instrument fundamentals in industrial/electronic music.

### Added
- Six tunable constants at the top of `mix_analyzer.py` for resonance 
  detection: window width, excess threshold, absolute floor, frequency 
  floor, max reported peaks, minimum peaks for warning. Producers can 
  adjust these without modifying algorithm code.
- Test fixtures and validation script in `Test/resonance_fixtures/`. 
  Run `python Test/resonance_fixtures/validate.py` to verify the algorithm 
  on 9 synthetic ground-truth fixtures.

### Notes
- The default `RESONANCE_MIN_EXCESS_DB` is set to **6.0 dB** based on 
  synthetic fixture validation. On real-world bounces this may produce 
  more warnings than expected — particularly on tracks with broadband 
  but spectrally rich content. Users are encouraged to test empirically 
  with values between **6.0 and 10.0 dB** to find the sensitivity that 
  matches their workflow. The constant is exposed at the top of 
  `mix_analyzer.py` for easy tuning without code changes.
- The internal algorithm uses three additional filtering layers beyond 
  the basic local-contour comparison: spectral prominence validation, 
  broadband context gating, and a 16 kHz upper frequency ceiling. These 
  filters are not user-tunable and are documented inline in 
  `detect_resonance_anomalies()`.
