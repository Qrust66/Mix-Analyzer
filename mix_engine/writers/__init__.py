"""mix_engine.writers — Tier B XML writers (deterministic .als modifications).

Tier A agents (eq-corrective-decider, dynamics-corrective-decider, etc.)
produce typed MixDecision[T] JSON. Tier B writers consume these decisions
and translate them into XML patches applied to .als files.

Design tenets :

1. **Deterministic** — same MixDecision input always produces the same
   .als output. Verifiable via pytest XML assertions.
2. **Idempotent** — applying the same decision twice does not duplicate
   devices or envelopes. Re-runs are no-ops.
3. **Reuse als_utils primitives** — decompress/compress, find_track_by_name,
   find_or_create_eq8, configure_eq8_band, write_automation_envelope are
   already battle-tested ; writers wrap them at decision-level granularity.
4. **Typed exceptions** — TrackNotFoundError, EQ8SlotFullError (existing),
   plus per-writer error subclasses (EqConfiguratorError, etc.) for
   actionable failure modes.
5. **Audit-friendly** — every applied operation traceable back to the
   originating MixDecision via report dataclass.
6. **Safety-guardian integration** — writers can optionally invoke
   als-safety-guardian post-write to verify .als integrity.

Phase 4.10 (eq8-configurator) ships first. Other writers land one-by-one
following the Tier B writers roadmap (cf. docs/MIX_ENGINE_ROADMAP.md).
"""
from __future__ import annotations

from mix_engine.writers.eq8_configurator import (
    EqConfiguratorError,
    EqConfiguratorReport,
    apply_eq_corrective_decision,
)
from mix_engine.writers.dynamics_configurator import (
    DynamicsConfiguratorError,
    DynamicsConfiguratorReport,
    DynamicsDeviceNotFoundError,
    apply_dynamics_corrective_decision,
)
from mix_engine.writers.spatial_configurator import (
    SpatialConfiguratorError,
    SpatialConfiguratorReport,
    SpatialDeviceNotFoundError,
    apply_spatial_decision,
)
from mix_engine.writers.routing_configurator import (
    RoutingConfiguratorError,
    RoutingConfiguratorReport,
    SidechainBlockNotFoundError,
    apply_routing_decision,
)
from mix_engine.writers.master_bus_configurator import (
    MasterBusConfiguratorError,
    MasterBusConfiguratorReport,
    MasterDeviceNotFoundError,
    MasterTrackNotFoundError,
    apply_mastering_decision,
)
from mix_engine.writers.chain_assembler import (
    ChainAssemblerError,
    ChainAssemblerReport,
    apply_chain_decision,
)

__all__ = [
    "EqConfiguratorError",
    "EqConfiguratorReport",
    "apply_eq_corrective_decision",
    "DynamicsConfiguratorError",
    "DynamicsConfiguratorReport",
    "DynamicsDeviceNotFoundError",
    "apply_dynamics_corrective_decision",
    "SpatialConfiguratorError",
    "SpatialConfiguratorReport",
    "SpatialDeviceNotFoundError",
    "apply_spatial_decision",
    "RoutingConfiguratorError",
    "RoutingConfiguratorReport",
    "SidechainBlockNotFoundError",
    "apply_routing_decision",
    "MasterBusConfiguratorError",
    "MasterBusConfiguratorReport",
    "MasterDeviceNotFoundError",
    "MasterTrackNotFoundError",
    "apply_mastering_decision",
    "ChainAssemblerError",
    "ChainAssemblerReport",
    "apply_chain_decision",
]
