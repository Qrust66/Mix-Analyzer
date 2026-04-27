"""Director — orchestrates the per-sphere agents to produce a SectionBlueprint.

For Phase 1 only the 'ghost' mode is implemented: the Director accepts a
hand-filled blueprint and runs cohesion checks on it. This lets us validate
the entire blueprint -> composer -> .als pipeline end to end before any LLM
agent is wired in.

Phase 2+ adds 'live' mode: dispatch each sphere to a dedicated subagent,
collect their Decisions, merge into a blueprint, audit cohesion, loop on
violations.
"""
from composition_engine.director.director import Director, DirectorMode

__all__ = ["Director", "DirectorMode"]
