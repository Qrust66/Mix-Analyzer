"""als_writer — apply a MixBlueprint to a .als file safely.

Phase 4.0 = empty skeleton. Phase 4.1+ implements:

1. Read .als (gzip → XML, via als_utils)
2. For each filled lane in the MixBlueprint, apply the corresponding patch:
   - routing → AudioOutputRouting / SidechainRouting edits
   - eq_corrective / eq_creative → Eq8 device patches
   - dynamics_corrective → GlueCompressor / Compressor2 / Limiter / Gate / DrumBuss
   - saturation_color → Saturator / DrumBuss color
   - stereo_spatial → StereoGain + sends/returns
   - automation → AutomationEnvelope writes
   - chain → device order + new device insertions
   - mastering → master bus chain
3. Write to a NEW filename (never overwrite source — see CLAUDE_PROJECT.md
   pitfalls)
4. Verify post-write (first bytes after gunzip must be `<?xml`)
5. Return path + audit trail

The writer never decides WHAT to change — that's the agents' job. It
only knows HOW to apply a typed delta to the XML structure, using the
device-mapping-oracle's slices and the als-manipulation-oracle's
procedures.
"""
from __future__ import annotations
