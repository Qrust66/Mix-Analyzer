# Multi-agent section demo — prompt réutilisable

But : composer N sections d'une toune via le multi-agent
`composition_engine` (Phase 2.6+) et injecter les sections dans une COPIE
de `Template.als`, sans toucher au fichier source.

À coller tel quel dans une nouvelle conversation Claude Code, puis donner
le brief créatif (vibe/refs/tempo/durée) en message suivant.

---

```
Mission : composer 2 sections d'une toune via le multi-agent composition_engine
(Phase 2.6 fraîchement landed) et injecter les sections dans une COPIE de
Template.als — sans toucher au fichier source.

## Contexte projet à charger d'abord

1. Lire `CLAUDE.md` (hub) puis :
   - `docs/CLAUDE_AGENTS.md` (agents disponibles, architecture multi-agent)
   - `docs/CLAUDE_PROJECT.md` (section "Pièges critiques déjà rencontrés"
     — 5 pièges .als à connaître par cœur avant toute manipulation)
   - `ableton/ALS_MANIPULATION_GUIDE.md` (manipulation .als)
2. Lire un script de référence existant pour voir le pattern d'injection :
   `scripts/build_bramure_template.py` (copie Template.als → Bramure.als,
   injecte sections, écrit, vérifie).

## Le fichier source

Path : `ableton/projects/Template/Template Project/Template.als`
**NE JAMAIS l'écraser.** Output sous un nouveau nom, par exemple
`ableton/projects/Template/Template Project/Multi_Agent_Demo.als` (ou autre
nom non-existant que tu choisis).

## Mode "exagéré" — usage maximal des agents

Pour CHAQUE des 2 sections, invoke via le Agent tool (subagent_type =
nom de l'agent) les 5 sphere agents wired aujourd'hui, dans l'ordre du
DAG (`composition_engine/director/director.py` `SPHERE_DEPENDENCIES`) :

  1. structure-decider  → StructureDecision
  2. harmony-decider    → HarmonyDecision  (après structure)
  3. rhythm-decider     → RhythmDecision   (après structure+harmony)
  4. arrangement-decider → ArrangementDecision (après les 3 ci-dessus —
     **seule sphère qui produit du MIDI audible** aujourd'hui)
  5. dynamics-decider   → DynamicsDecision  (Phase 2.6, descriptif —
     loggera un WARNING composer, c'est NORMAL)

Chaque agent reçoit :
- un **brief humain** précis (style, durée en bars, intent)
- une liste de **chansons de référence** EXISTANTES dans le corpus
  inspirations.json (vérifier via `composition_engine.advisor_bridge.song_loader.list_songs()`
  avant d'invoquer — ne pas inventer de refs)
- la **structure déjà décidée** quand pertinent (total_bars pour bornes)

L'agent retourne du JSON pur. Parser via les fonctions dans
`composition_engine/blueprint/agent_parsers.py` :
  parse_{structure|harmony|rhythm|arrangement|dynamics}_decision_from_response()

## Pipeline d'assemblage par section

```python
from composition_engine.blueprint import SectionBlueprint, check_cohesion
from composition_engine.blueprint.agent_parsers import (
    parse_structure_decision_from_response,
    parse_harmony_decision_from_response,
    parse_rhythm_decision_from_response,
    parse_arrangement_decision_from_response,
    parse_dynamics_decision_from_response,
)
from composition_engine.blueprint.composer_adapter import compose_to_midi

bp = (SectionBlueprint(name="<section_name>")
      .with_decision("structure",   structure_decision)
      .with_decision("harmony",     harmony_decision)
      .with_decision("rhythm",      rhythm_decision)
      .with_decision("arrangement", arrangement_decision)
      .with_decision("dynamics",    dynamics_decision))

report = check_cohesion(bp)
assert report.is_clean, f"Cohesion blockers: {report.blockers}"

mid_path = compose_to_midi(bp, f"out/{section_name}.mid")
```

## Injection dans le .als

Suivre le pattern de `scripts/build_bramure_template.py` :
1. `shutil.copy(Template.als, Multi_Agent_Demo.als)`
2. Décompresser le .als (gzip → XML)
3. Injecter les MIDI clips dans les tracks appropriées (mapper layer.role
   → track Ableton)
4. Recompresser (gzip ; **attention au piège #1 : pas de double gzip**)
5. Vérifier post-écriture (premiers octets `<?xml` après gunzip)

## Garde-fou obligatoire avant livraison

Lancer l'agent **als-safety-guardian** (subagent_type=als-safety-guardian)
sur le `.als` produit. Si verdict FAIL, NE PAS livrer — fix d'abord.

## Definition of done

- [ ] 2 SectionBlueprint complets, chacun avec les 5 sphères remplies
      par invocation réelle de leur sphere-decider (PAS de Decision
      construit manuellement en Python)
- [ ] check_cohesion(bp).is_clean == True pour chaque section
- [ ] 2 fichiers .mid générés via compose_to_midi
- [ ] 1 fichier .als nouveau (Template.als intact)
- [ ] als-safety-guardian verdict = PASS
- [ ] Le fichier .als s'ouvre dans Ableton sans crash (l'utilisateur
      vérifiera côté DAW — toi tu ne peux que valider la structure XML)

## Brief créatif libre

L'utilisateur te dira le vibe / refs / tempo / longueur souhaités. Si pas
de précision, demande-lui en 1 phrase : style/refs/tempo/durée. Pas plus.

## Commit policy

Commit séparé pour le script + le .als après chaque section validée.
Ne pas push sans demander.
```
