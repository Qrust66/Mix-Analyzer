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
    DYNAMICS_BASELINE_DB,
    MOTIF_PITCH_MAX,
    MOTIF_PITCH_MIN,
    MOTIF_VELOCITY_MAX,
    MOTIF_VELOCITY_MIN,
    SPHERES,
    ArrangementDecision,
    Citation,
    Decision,
    DynamicsDecision,
    FxDecision,
    HarmonyDecision,
    InstChange,
    LayerMotif,
    LayerSpec,
    MotifsDecision,
    Note,
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
    "DYNAMICS_BASELINE_DB",
    "MOTIF_PITCH_MAX",
    "MOTIF_PITCH_MIN",
    "MOTIF_VELOCITY_MAX",
    "MOTIF_VELOCITY_MIN",
    "SPHERES",
    "ArrangementDecision",
    "Citation",
    "Decision",
    "DynamicsDecision",
    "FxDecision",
    "HarmonyDecision",
    "InstChange",
    "LayerMotif",
    "LayerSpec",
    "MotifsDecision",
    "Note",
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
