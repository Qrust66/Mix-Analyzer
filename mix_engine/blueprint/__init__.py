"""mix_engine.blueprint — typed contract between mix agents and the .als writer.

Mirrors composition_engine.blueprint but for mix-side decisions: routing,
EQ corrections, dynamics, automation envelopes, mastering moves.

Phase 4.0 = skeleton. Concrete dataclasses materialize one-by-one as their
producing agent (eq-corrective-engineer, etc.) gets built.
"""
from __future__ import annotations
