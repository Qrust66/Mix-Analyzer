# mix_engine — multi-agent mix & mastering for Ableton Live

Parallel module to `composition_engine/`. See
**`docs/MIX_ENGINE_ARCHITECTURE.md`** for the full design.

Phase 4.0 = architecture rails posed. Phase 4.1+ = agents built one at
a time as concrete projects motivate them.

## First cohort planned (Phase 4.1)

1. `device-mapping-oracle` — active interface on
   `ableton_devices_mapping.json`
2. `mix-diagnostician` — produces the structured report every other
   mix agent consumes
3. `eq-corrective-engineer` — first lane agent (Eq8 is the most
   thoroughly mapped device + most testable via Mix Analyzer)

Everything else (dynamics-corrective, automation-engineer, mastering,
…) lands when a real project demands it — rule-with-consumer.
