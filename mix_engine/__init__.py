"""mix_engine — multi-agent mix & mastering engine for Ableton Live projects.

Parallel module to `composition_engine/`. Where composition_engine generates
new MIDI from a brief, mix_engine sculpts an existing .als from a diagnostic.

Phase 4.0 ships only the **architecture** — the public types and module
layout. Concrete agents (12 mix lanes + 2 oracles) land in Phase 4.1+
following the rule-with-consumer principle: no agent is written until a
real project motivates its existence.

See `docs/MIX_ENGINE_ARCHITECTURE.md` for the full design rationale.

Public API (Phase 4.0 — minimal):
    Phase 4.0 ships skeleton modules only. Imports below will fail with
    NotImplementedError until the underlying classes are built.
"""
from __future__ import annotations
