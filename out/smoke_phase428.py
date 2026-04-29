"""Smoke test for Phase 4.2.8 — full DiagnosticReport with CDE + Freq Conflicts."""
from mix_engine.blueprint import parse_diagnostic_decision

payload = {
    "schema_version": "1.0",
    "diagnostic": {
        "project_name": "Acid_Drops_P11",
        "full_mix": {
            "integrated_lufs": -13.64, "true_peak_dbtp": -0.3,
            "crest_factor_db": 12.4, "plr_db": 13.34, "lra_db": 8.2,
            "dominant_band": "low-mid", "correlation": 0.78,
            "stereo_width": 0.14, "spectral_entropy": 4.1,
        },
        "tracks": [
            {"name": "Kick A", "track_type": "Audio", "parent_bus": "Drums", "color": "",
             "devices": ["Eq8", "GlueCompressor"], "volume_db": -3.2, "pan": 0.0,
             "sidechain_targets": [], "activator": True},
            {"name": "Bass A", "track_type": "Audio", "parent_bus": None, "color": "",
             "devices": ["Eq8", "Compressor2", "Saturator"], "volume_db": -6.0, "pan": 0.0,
             "sidechain_targets": ["Kick A"], "activator": True},
        ],
        "anomalies": [
            {"severity": "warning", "category": "shared_resonance",
             "description": "Strong resonance peaks detected at: 247Hz, 1200Hz",
             "affected_tracks": ["Bass A"], "suggested_fix_lane": "eq_corrective"},
        ],
        "health_score": {"overall": 52.2, "breakdown": [
            {"category": "Spectral Balance", "score": 62.0},
            {"category": "Anomalies", "score": 50.0},
        ]},
        "routing_warnings": [],
        "cde_diagnostics": [
            {
                "diagnostic_id": "cde-007",
                "issue_type": "masking_conflict",
                "severity": "critical",
                "section": "drop_1",
                "track_a": "Kick A", "track_b": "Bass A",
                "measurement": {"frequency_hz": 247.0},
                "tfp_context": {"track_a_role": ["H", "R"], "track_b_role": ["S", "L"], "role_compatibility": "high"},
                "primary_correction": {
                    "target_track": "Bass A", "device": "EQ8 - Peak Resonance", "approach": "static_dip",
                    "parameters": {"frequency_hz": 247.0, "gain_db": -3.0, "q": 4.0, "active_in_sections": [2, 3, 4]},
                    "applies_to_sections": [2, 3, 4], "rationale": "Static dip on Bass A.", "confidence": "high",
                },
                "fallback_correction": {
                    "target_track": "Bass A", "device": "Kickstart 2", "approach": "sidechain",
                    "parameters": {"trigger_track": "Kick A", "depth_db": -6.0},
                    "applies_to_sections": [2, 3, 4], "rationale": "Sidechain alt.", "confidence": "medium",
                },
                "expected_outcomes": ["Bass clears 247Hz by 3dB", "Mono compat +0.05"],
                "potential_risks": ["Bass may lose body cross-section"],
                "application_status": "pending",
            },
            {
                "diagnostic_id": "cde-rejected",
                "issue_type": "masking_conflict", "severity": "moderate",
                "track_a": "Pad", "track_b": None,
                "measurement": None, "tfp_context": None,
                "primary_correction": None, "fallback_correction": None,
                "expected_outcomes": [], "potential_risks": [],
                "application_status": "rejected",  # filtered by defer mode
            },
        ],
        "freq_conflicts_meta": {"threshold_pct": 30.0, "min_tracks": 2},
        "freq_conflicts_bands": [
            {"band_label": "sub (20-60Hz)",
             "energy_per_track": {"Kick A": 45.0, "Bass A": 38.0, "Guitar L": 18.0},
             "conflict_count": 2, "status": "Conflict"},
            {"band_label": "low-mid (200-500Hz)",
             "energy_per_track": {"Kick A": 22.0, "Bass A": 38.0, "Synth Pad": 32.0},
             "conflict_count": 2, "status": "Conflict"},
        ],
    },
    "cited_by": [{"kind": "diagnostic", "path": "mix_analyzer", "excerpt": "P11"}],
    "rationale": "Phase 4.2.8 absorption smoke test",
    "confidence": 0.9,
}

d = parse_diagnostic_decision(payload)
report = d.value

print(f"Project: {report.project_name}")
print(f"Tracks: {len(report.tracks)}")
print(f"Anomalies: {len(report.anomalies)}")
print(f"CDE diagnostics: {len(report.cde_diagnostics)}")
for cd in report.cde_diagnostics:
    primary_dev = cd.primary_correction.device if cd.primary_correction else "None"
    fallback_dev = cd.fallback_correction.device if cd.fallback_correction else "None"
    print(f"  - {cd.diagnostic_id} ({cd.issue_type}/{cd.severity}) ; "
          f"primary={primary_dev} ; fallback={fallback_dev} ; status={cd.application_status}")
    if cd.tfp_context and cd.tfp_context.track_a_role:
        print(f"    tfp roles: {cd.tfp_context.track_a_role} / {cd.tfp_context.track_b_role}")
    if cd.expected_outcomes:
        print(f"    {len(cd.expected_outcomes)} outcomes, {len(cd.potential_risks)} risks")

print()
meta = report.freq_conflicts_meta
print(f"Freq Conflicts threshold: {meta.threshold_pct}%, min={meta.min_tracks}")
for b in report.freq_conflicts_bands:
    print(f"  - {b.band_label} : conflict_count={b.conflict_count}, status={b.status}")

actionable = [c for c in report.cde_diagnostics if c.application_status not in {"rejected"}]
eq8_relevant = [c for c in actionable
                if c.primary_correction and "EQ8" in c.primary_correction.device]
print()
print(f"After filter: actionable={len(actionable)} (rejected filtered) ; EQ8-relevant={len(eq8_relevant)}")
print()
print("OK: typed CDE + Freq Conflicts available end-to-end via DiagnosticReport.")
