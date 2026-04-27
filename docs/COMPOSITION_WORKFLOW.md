# Workflow de composition end-to-end

Ce document montre la chaîne complète depuis un brief utilisateur
jusqu'à un fichier `.mid` jouable, en utilisant le multi-agent system
et le composer pipeline.

État actuel (Phase 2.3.1) : `structure-decider` et `harmony-decider`
agents sont implémentés. Les 5 autres sphère agents (rhythm,
arrangement, dynamics, performance, fx) viendront en Phase 2.4+. En
attendant, le user (ou l'orchestrateur Claude) **remplit ces sphères
manuellement** dans le SectionBlueprint avant de rendre le MIDI.

## Vue d'ensemble

```
   user brief + refs
       │
       ▼
   ┌─────────────────────┐
   │ structure-decider   │  (LLM, lit composition.structural_blueprint des refs)
   │ → JSON              │
   └─────────────────────┘
       │
       ▼
   parse_structure_decision_from_response(json)
       → Decision[StructureDecision]
       │
       ▼
   bp.with_decision("structure", decision)
       │
       ▼
   ┌─────────────────────┐
   │ harmony-decider     │  (LLM, lit composition.harmonic_motion / modal_choice / etc.)
   │ → JSON              │
   └─────────────────────┘
       │
       ▼
   parse_harmony_decision_from_response(json)
       → Decision[HarmonyDecision]
       │
       ▼
   bp.with_decision("harmony", decision)
       │
       ▼  (autres sphères remplies à la main pour l'instant)
       ▼
   ┌─────────────────────┐
   │ Director (GHOST)    │  (cohésion checks)
   └─────────────────────┘
       │
       ▼
   ┌─────────────────────┐
   │ compose_to_midi     │  (composer.compose + write_midi_file)
   └─────────────────────┘
       │
       ▼
   .mid file on disk
```

## Exemple concret en Python

Code orchestrateur typique (à exécuter par toi via Claude Code, ou par
un script Python plus tard) :

```python
from pathlib import Path

from composition_engine.blueprint import (
    SectionBlueprint,
    Decision,
    RhythmDecision, ArrangementDecision, LayerSpec,
)
from composition_engine.blueprint.agent_parsers import (
    parse_structure_decision_from_response,
    parse_harmony_decision_from_response,
)
from composition_engine.blueprint.composer_adapter import compose_to_midi

# ---- 1. Brief + refs (input utilisateur)

brief = "intro 16 bars introspective avec build subtil"
refs = ("Radiohead/Pyramid_Song", "Nirvana/Heart_Shaped_Box")

# ---- 2. Invoque structure-decider via Claude Code subagent
#         (en pratique : Task tool, ici en pseudo-code)
#
# structure_response = invoke_subagent(
#     "structure-decider",
#     prompt=f"brief: {brief}\nrefs: {refs}"
# )
#
# Pour cet exemple, on suppose qu'il a retourné :
structure_response = """
{"schema_version":"1.0","structure":{"total_bars":16,
 "sub_sections":[{"name":"hush","start_bar":0,"end_bar":8,"role":"breath"},
                 {"name":"build","start_bar":8,"end_bar":16,"role":"build"}],
 "breath_points":[7,15],
 "transition_in":"vocal_drop_in_no_anticipation",
 "transition_out":"layer_subtraction_into_climax"},
 "rationale":"16 bars binaire 8+8 inspiré de Pyramid_Song.",
 "inspired_by":[{"song":"Radiohead/Pyramid_Song",
                 "path":"composition.structural_blueprint",
                 "excerpt":"piano_alone_intro -> vocal_entry"}],
 "confidence":0.85}
"""

structure_decision = parse_structure_decision_from_response(structure_response)

bp = SectionBlueprint(name="intro", brief=brief, references=refs)
bp = bp.with_decision("structure", structure_decision)

# ---- 3. Invoque harmony-decider en passant le total_bars du structure
#
# harmony_response = invoke_subagent(
#     "harmony-decider",
#     prompt=f"brief: {brief}\nrefs: {refs}\ntotal_bars: {structure_decision.value.total_bars}"
# )
#
# Pour cet exemple :
harmony_response = """
{"schema_version":"1.0","harmony":{"mode":"Aeolian","key_root":"F#",
 "progression":["i","bVI","bVII","i"],"harmonic_rhythm":0.5,
 "voicing_strategy":"close-voiced piano middle register",
 "cadence_at_end":"open"},
 "rationale":"F# Aeolian comme Pyramid_Song, progression descendante en 0.5 chord/bar.",
 "inspired_by":[{"song":"Radiohead/Pyramid_Song",
                 "path":"composition.modal_choice",
                 "excerpt":"F# Aeolian/Phrygian area"}],
 "confidence":0.85}
"""

harmony_decision = parse_harmony_decision_from_response(harmony_response)
bp = bp.with_decision("harmony", harmony_decision)

# ---- 4. Remplir manuellement les sphères restantes (Phase 2.3 stage)
#         Phase 2.4+ aura des agents pour rhythm/arrangement/etc.

bp = bp.with_decision("rhythm",
    Decision(value=RhythmDecision(tempo_bpm=75, time_signature="16/8"),
             sphere="rhythm"))

bp = bp.with_decision("arrangement",
    Decision(
        value=ArrangementDecision(
            layers=(
                LayerSpec(role="pad", instrument="warm pad",
                          enters_at_bar=0, exits_at_bar=16),
                LayerSpec(role="drum_kit", instrument="kit",
                          enters_at_bar=8, exits_at_bar=16, base_velocity=80),
            ),
            density_curve="sparse",
        ),
        sphere="arrangement",
    ),
)

# ---- 5. (Optionnel) Cohésion check via Director ghost mode

from composition_engine.director import Director, DirectorMode

director = Director(mode=DirectorMode.GHOST)
result = director.compose_section(
    name="intro",
    brief=brief,
    references=refs,
    ghost_blueprint=bp,
)

if not result.cohesion.is_clean:
    for v in result.cohesion.violations:
        print(f"[{v.severity}] {v.rule}: {v.message}")

# ---- 6. Render le .mid

out_path = Path("output/my_intro.mid")
out_path.parent.mkdir(exist_ok=True)
midi_path = compose_to_midi(bp, out_path)
print(f"MIDI written: {midi_path}")
```

## Quoi faire avec le `.mid`

- Drag-and-drop dans Ableton Live, Logic, FL Studio, Reaper.
- Charger les pistes sur tes propres synthés / samples.
- Le composer-adapter assigne 1 channel MIDI par track (DRUM_KIT,
  BASS, LEAD, PAD…). Les pitches sont conformes : kick = 36, bass =
  octave below tonic, lead = perfect 5th above tonic, pad = minor
  triad. Tu peux mapper tes propres instruments dessus.

## Ordre d'invocation des sphère agents

Phase 2.3 ship : `structure-decider`, `harmony-decider`. L'ordre
recommandé (encodé dans `SPHERE_DEPENDENCIES` du Director) :

1. **structure** — fixe le squelette (bars, sub-sections).
2. **harmony** — fixe la palette tonale.
3. **rhythm** — (Phase 2.4) fixe le tempo + drum patterns.
4. **arrangement** — (Phase 2.5) place les layers.
5. **dynamics** — (Phase 2.6) modèle l'arc d'intensité.
6. **performance** — (Phase 2.7) feel + humanization.
7. **fx** — (Phase 2.8) reverb / filter / saturation.

Quand le director live mode sera implémenté, il dispatchera ces agents
dans l'ordre topologique automatiquement.

## Schéma de cohérence cross-sphère

À surveiller (non-enforced en code pour l'instant) :

- `structure.total_bars × harmony.harmonic_rhythm` doit donner un
  nombre cohérent de chord events (genre entre 4 et 32 — pas 1, pas
  500).
- `arrangement.layers[*].enters_at_bar` doit être dans
  `[0, structure.total_bars)` ; `.exits_at_bar` dans
  `(0, structure.total_bars]`.
- `dynamics.peak_bar` doit être dans `[0, structure.total_bars)`.
- `harmony.key_root` doit être un nom de note canonique (validé
  strictement par le parser).

Phase 2.X+ ajoutera des `@cohesion_rule` qui automatisent ces vérifs
quand chaque sphère est remplie.
