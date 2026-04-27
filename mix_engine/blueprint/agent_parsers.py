"""Mix-side agent parsers — JSON → MixDecision[T].

Mirrors composition_engine.blueprint.agent_parsers. Each mix agent
(eq-corrective-engineer, automation-engineer, …) emits a JSON payload
that this module parses into a typed MixDecision.

Phase 4.0 ships zero concrete parsers. Each one lands with the agent
that produces values for it — rule-with-consumer.

Conventions inherited from the composition side:

- Lenient on input, strict on output (markdown fences, prose around,
  mild type drift all tolerated; the resulting MixDecision is fully
  typed and validated).
- Schema versioning via "schema_version": "1.0" at top level.
- Public canonical constants (no magic numbers in tests).
- AgentOutputError raised on contract violation, with a `where=...`
  pointer to the offending field for actionable messages.
"""
from __future__ import annotations


class MixAgentOutputError(ValueError):
    """Raised when a mix agent's JSON payload doesn't match the expected schema."""
