"""Mix Director — sequences mix agents according to MIX_DEPENDENCIES.

Mirrors composition_engine.director.director. Phase 4.0 ships the DAG
declaration; the LIVE / GHOST / INTERACTIVE modes land Phase 4.1+ with
the first concrete mix agents.

The DAG below is the canonical ordering. Lanes on the same level can
run in parallel; lanes on later levels consume the typed output of
earlier ones (no agent re-reads the .als once mix-diagnostician has
produced its report).
"""
from __future__ import annotations

# Mix lane DAG. Each key is a lane; its value is the tuple of lanes
# that must be filled before this lane's agent can run.
#
# Rationale per edge:
# - everything depends on diagnostic (you don't move blind)
# - routing runs second because broken refs (No Output / No Input)
#   poison everything downstream
# - corrective lanes (dynamics/eq/stereo) are parallelisable
# - creative color (eq_creative, saturation) waits for corrective
#   so you don't decorate a still-broken signal
# - chain composes the per-device decisions into a track chain order
# - automation writes envelopes onto already-decided params
# - mastering is last-mile, master bus only
MIX_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "diagnostic":          (),
    "routing":             ("diagnostic",),
    "dynamics_corrective": ("diagnostic", "routing"),
    "eq_corrective":       ("diagnostic", "routing"),
    "stereo_spatial":      ("diagnostic", "routing"),
    "eq_creative":         ("eq_corrective",),
    "saturation_color":    ("eq_corrective", "dynamics_corrective"),
    "chain":               ("eq_corrective", "eq_creative",
                            "dynamics_corrective", "saturation_color"),
    "automation":          ("chain",),
    "mastering":           ("automation",),
}
