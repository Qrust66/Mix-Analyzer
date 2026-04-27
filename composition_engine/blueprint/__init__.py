"""SectionBlueprint — the shared data structure that all 7 sphere agents
fill collaboratively, and that the composer consumes to produce MIDI.

Public API:
    SectionBlueprint, Decision, Citation
    StructureDecision, HarmonyDecision, RhythmDecision,
    ArrangementDecision, DynamicsDecision, PerformanceDecision, FxDecision
    SubSection, LayerSpec, InstChange
    SPHERES

    cohesion_rule, check_cohesion
    CohesionReport, CohesionViolation
"""
from composition_engine.blueprint.schema import (
    SPHERES,
    ArrangementDecision,
    Citation,
    Decision,
    DynamicsDecision,
    FxDecision,
    HarmonyDecision,
    InstChange,
    LayerSpec,
    PerformanceDecision,
    RhythmDecision,
    SectionBlueprint,
    StructureDecision,
    SubSection,
)
from composition_engine.blueprint.cohesion import (
    CohesionReport,
    CohesionViolation,
    check_cohesion,
    cohesion_rule,
)

__all__ = [
    "SPHERES",
    "ArrangementDecision",
    "Citation",
    "Decision",
    "DynamicsDecision",
    "FxDecision",
    "HarmonyDecision",
    "InstChange",
    "LayerSpec",
    "PerformanceDecision",
    "RhythmDecision",
    "SectionBlueprint",
    "StructureDecision",
    "SubSection",
    "CohesionReport",
    "CohesionViolation",
    "check_cohesion",
    "cohesion_rule",
]
