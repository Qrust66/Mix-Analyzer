# CLAUDE_AGENTS.md — Subagents, hooks, composition engine architecture

Document chargé à la demande pour les détails du système multi-agent et des
hooks Claude Code / git. Le hub `CLAUDE.md` à la racine du repo y pointe.

## Hooks git automatiques (filet de sécurité)

Le projet versionne ses hooks git dans `.githooks/`. Configurer une fois
par clone :

```bash
git config core.hooksPath .githooks
```

Sans cette commande, **les hooks ne s'exécutent pas**. Le `git status`
n'avertit pas — penser à le refaire après un fresh clone.

### Hooks installés

| Hook | Rôle |
|------|------|
| `pre-commit` | Lance `check_version_sync.py` si un fichier de prod est staged. Bloque le commit en cas de drift de version. Bypass avec `--no-verify` (déconseillé). |
| `pre-push` | Lance `check_regression.py` qui choisit entre la **suite rapide** (3 fichiers test : `test_spectral_evolution`, `test_eq8_automation`, `test_v25_integration`, ~10-15s) et la **suite complète** (`pytest tests/`, ~2 min). Critère : si un des 8 fichiers de prod ou un fichier `tests/*.py` est dans le push → suite complète, sinon suite rapide. Bloque le push en cas d'échec. Bypass avec `--no-verify` (déconseillé). |
| `post-commit` | Hook graphify : rebuild AST-only de `graphify-out/graph.json` après chaque commit. Sans LLM, gratuit. |
| `post-checkout` | Idem au changement de branche. |

### Hooks Claude Code (`.claude/hooks/`)

`UserPromptSubmit` (configuré dans `.claude/settings.json`) lance deux
scripts à chaque prompt :

1. **`graphify_reminder.py`** : si le prompt matche des patterns
   d'architecture / dépendance / cross-module, injecte un rappel pour
   consulter `graphify-out/graph.json` avant tout grep/Read.
2. **`cost_discipline_reminder.py`** : si le prompt matche un pattern à
   risque coût (scale-without-pilot, brief ouvert), injecte un rappel
   pointant vers `.claude/COST_DISCIPLINE.md`.

Coût : ~50 tokens par prompt qui matche, 0 sinon.

Les hooks sont des **filets de sécurité déterministes** (pas de LLM, pas
de magie) qui complètent les agents Claude Code. Si un check est purement
mécanique, il vaut mieux l'avoir comme hook que comme agent — l'agent peut
être oublié, le hook ne peut pas.

## Hiérarchie complète des agents

| Catégorie | Agents | Phase | État |
|---|---|---|---|
| **Housekeeping** | als-safety-guardian, version-sync-checker, graph-first-explorer, regression-detector | toutes | ✅ |
| **Composition spheres** | structure, harmony, rhythm, arrangement, dynamics deciders | 2.2-2.6 | ✅ |
| **Composition spheres restantes** | performance-decider, fx-decider | 2.7-2.8 | ⏳ |
| **Ableton-expertise oracles** | device-mapping-oracle, als-manipulation-oracle | 4.0 | ✅ |
| **Mix lanes** | mix-diagnostician, routing-and-sidechain-architect, eq-corrective-engineer, eq-creative-colorist, dynamics-corrective-engineer, saturation-and-color-engineer, stereo-and-spatial-engineer, automation-engineer, chain-builder, mastering-engineer, mix-orchestrator, mix-safety-guardian | 4.1+ | ⏳ |

Les **oracles** (Phase 4.0) sont la couche d'expertise active sur la
documentation Ableton (device mapping JSON + manipulation guide). Tout
mix agent les interroge plutôt que de re-charger 5500 lignes de JSON.
Symétrie : oracle = prof avant l'action, guardian = correcteur après.

Voir **`docs/MIX_ENGINE_ARCHITECTURE.md`** pour le design Phase 4.0+.

## Agents automatiques

Le projet déclare des subagents Claude Code dans `.claude/agents/`. Certains
doivent être invoqués proactivement aux moments listés ci-dessous, sans
attendre que l'utilisateur les demande.

### als-safety-guardian (`.claude/agents/als-safety-guardian.md`)

**Invoquer automatiquement** dans ces cas :

1. **Après l'exécution d'un script qui produit un `.als`** : tout script de
   `composition_engine/`, `scripts/build_*`, `ableton/build_*`, ou tout
   appel à `als_utils.compress_to_als()` qui écrit un nouveau fichier.
2. **Avant un commit qui modifie ou ajoute un `.als`** (`git status`
   montre un `.als` staged ou modified).
3. **Avant de livrer un `.als` à l'utilisateur** — passer la checklist en
   silence avant la livraison.

L'agent est read-only (tools restreints à `Read, Bash, Grep, Glob`). Reporte
PASS / FAIL / WARN par règle puis verdict global. Si verdict = FAIL,
**ne pas livrer le `.als`** sans fix manuel.

Référence : `ableton/ALS_MANIPULATION_GUIDE.md` + section "Pièges critiques"
de `docs/CLAUDE_PROJECT.md`.

### version-sync-checker (`.claude/agents/version-sync-checker.md`)

**Invoquer automatiquement** dans ces cas :

1. **Avant tout commit qui touche `mix_analyzer.py`** — la constante
   canonique `VERSION` peut avoir bougé sans que les 7 autres docstrings
   suivent.
2. **Avant tout commit dont le message contient `bump`, `version` ou
   `release`**.
3. **Avant un push sur `main`** — dernière vérif avant publication.

L'agent compare la constante `VERSION` dans `mix_analyzer.py` aux docstrings
des 7 autres fichiers (cf. section "Versioning" de `docs/CLAUDE_PROJECT.md`).
Reporte un tableau PASS/FAIL et refuse de patcher (read-only).

Si verdict = OUT-OF-SYNC, **ne pas push** sans aligner manuellement les
fichiers en drift.

### graph-first-explorer (`.claude/agents/graph-first-explorer.md`)

**Invoquer automatiquement** quand l'utilisateur pose une question :

1. **D'architecture / cross-module** : "comment fonctionne la pipeline X",
   "qui dépend de Y", "lien entre A et B", "trace le flux de … à …".
2. **Multi-query** : la réponse nécessite de croiser plusieurs concepts ou
   modules (>2 fichiers à explorer).
3. **De premier contact avec un module inconnu** : avant de plonger dans
   un dossier que je n'ai pas encore visité dans la session.

L'agent consulte `graphify-out/graph.json` **avant** tout grep/Read et
revient avec une synthèse citée. Ne pas l'invoquer pour les questions
triviales (1 Read suffit) ou pour les détails algorithmiques d'une
fonction (graph donne la structure, pas le détail).

Le hook `UserPromptSubmit` (cf. plus haut) injecte automatiquement un
rappel quand le prompt matche les patterns d'architecture — filet de
sécurité pour ne pas oublier l'agent.

### arrangement-decider (`.claude/agents/arrangement-decider.md`)

**Sphere agent arrangement (Phase 2.5).** **THE ONLY SPHERE** dont les
décisions traversent réellement vers le `.mid` rendu — les autres
(rhythm, dynamics, performance, fx) sont actuellement descriptives.

**Invoquer** typiquement après structure-decider + harmony-decider +
rhythm-decider (tous les 3 contextes utiles : `total_bars`, `key_root`,
`tempo_bpm`).

L'agent décide :
- `layers` (liste **non-vide** de LayerSpec : role, instrument,
  enters_at_bar, exits_at_bar, base_velocity 0-127)
- `density_curve` ∈ {sparse, medium, dense, build, valley, sawtooth}
- `instrumentation_changes` (liste de {bar, change})
- `register_strategy` (string libre)

Lit les `arrangement.instrumentation_complete / section_instrumentation /
vocal_layering_strategy / harmonic_density_per_section /
instrumental_role_assignment / arrangement_anti_patterns_avoided` des
références. Optionnel : `density_curves.*` du rules layer.

Validation stricte : layers non-vide, enters_at_bar ≥ 0, exits_at_bar >
enters_at_bar, base_velocity ∈ [0, 127], density_curve dans la
frozenset canonique.

**Effet sur le rendu** : chaque LayerSpec devient une track MIDI
(drum_kit → kick on 36, bass → tonic-12, lead → tonic+7, pad → minor
triad). Décisions vraies = MIDI vrai.

### device-mapping-oracle (`.claude/agents/device-mapping-oracle.md`)

**Ableton-expertise oracle (Phase 4.0).** Interface LLM proactive sur
`ableton/ableton_devices_mapping.json`. Quand n'importe quel agent ou
session a besoin de connaître le pattern XML, write rules, validation,
automation compatibility, bugs connus, ou interactions device-à-device
pour un paramètre Ableton, il interroge cet oracle.

**Invoquer** typiquement avant tout move sur un device : eq-corrective
qui veut connaître l'attribut XML pour `Frequency.Band1`, automation-engineer
qui veut savoir si un param est automatable et avec quel envelope kind,
chain-builder qui veut les warnings d'interaction Saturator → Compressor.

Backed par `composition_engine/ableton_bridge/catalog_loader.py` (slice
JSON déterministe). Output JSON structuré avec `cited_from[]`. Ne dump
**jamais** le catalog brut — synthétise.

Read-only. Voir `docs/MIX_ENGINE_ARCHITECTURE.md` §4.

### als-manipulation-oracle (`.claude/agents/als-manipulation-oracle.md`)

**Ableton-expertise oracle (Phase 4.0).** Interface LLM proactive sur
`ableton/ALS_MANIPULATION_GUIDE.md` + `als_utils.py`. Quand n'importe
quel agent s'apprête à modifier un .als, il interroge cet oracle pour
obtenir la procédure SAFE étape par étape, avec citation explicite des
5 pièges canoniques relevant.

**Invoquer** typiquement avant toute opération .als : injection de
device, patch param, écriture d'automation envelope, modification de
routing. L'oracle enseigne avant l'action ; **als-safety-guardian**
valide après l'action — ne pas confondre les rôles.

Output JSON procédural (steps + watch_out_for + verification_after +
save_path_recommendation non-destructif). Cite toujours les pièges
relevant parmi les 5 canoniques (double_gzip, devices_self_closing,
envelopes_self_closing, post_write_verification, name_every_injected_device).

Read-only — l'oracle ne modifie jamais un .als lui-même. Voir
`docs/MIX_ENGINE_ARCHITECTURE.md` §4.

### dynamics-decider (`.claude/agents/dynamics-decider.md`)

**Sphere agent dynamics (Phase 2.6).** **Currently descriptive** — ses
décisions ne traversent pas encore au MIDI rendu (le composer log un
WARNING quand `dynamics` contient des valeurs non-default). Phase 3+
wirera l'arc à un velocity envelope par-note.

**Invoquer** typiquement après `structure-decider` (le `total_bars` est
fixé, ce qui permet de placer `peak_bar` et `inflection_points` dans les
bornes correctes). L'agent décide :
- `arc_shape` ∈ {flat, rising, descending, valley, peak, exponential, sawtooth}
- `start_db` / `end_db` (float ∈ [-60.0, 0.0], baseline = 0)
- `peak_bar` (Optional[int] ∈ [0, total_bars), requis si `arc_shape="peak"`)
- `inflection_points` (liste de `[bar, db]`, bar ∈ [0, total_bars], db ∈ [-60, 0])

Lit les `arrangement.dynamic_arc_overall`, `stylistic_figures.climax_moments`,
`stylistic_figures.transitions_between_sections`,
`composition.harmonic_pacing` des références. Optionnel :
`tension_release.*` du rules layer.

Validation stricte : arc_shape dans la frozenset canonique, dB dans
[-60, 0], cohérence shape/levels (rising → end > start, descending →
end < start, flat → equal), `arc_shape="peak"` requiert `peak_bar`.
Cohesion rule `dynamics_within_structure_bounds` (Phase 2.6.1) bloque
peak_bar / inflection bars hors borne.

### rhythm-decider (`.claude/agents/rhythm-decider.md`)

**Sphere agent rythmique (Phase 2.4).**

**Invoquer** typiquement après `structure-decider` et `harmony-decider`.
L'agent décide :
- `tempo_bpm` (40-300, validé strictement)
- `time_signature` (string libre — accepte "4/4", "10/4", "16/8 with 3+3+4+3+3 internal grouping" pour Pyramid_Song / March_Of_The_Pigs style)
- `drum_pattern` (prose libre — pattern décrit, anti-générique)
- `subdivisions` (∈ {4, 8, 16, 32, 64} — puissances de 2)
- `swing` (∈ [0.0, 1.0))
- `polyrhythms` (liste descriptive, peut être vide)

Lit les `performance.tempo_feel_description`, `performance.drum_style`,
`tempo_bpm_documented_range`, `time_signature`,
`composition.phrase_symmetry`, `stylistic_figures.special_effects_*` des
références. Optionnel : `rhythm_theory` + `rhythm_advanced` du rules layer.

Output parsé via `parse_rhythm_decision()` ou
`parse_rhythm_decision_from_response()`. Validation stricte : tempo dans
plage musicale, subdivisions = puissance de 2, swing strictement < 1.0.

### harmony-decider (`.claude/agents/harmony-decider.md`)

**Sphere agent harmonique (Phase 2.3).**

**Invoquer** typiquement après `structure-decider` (le `total_bars` et
`sub_sections` sont déjà fixés). L'agent décide :
- `mode` (Aeolian, Dorian, Phrygian, Major, etc.)
- `key_root` (note seule : C, F#, A, etc. — validé strictement)
- `progression` (chiffres romains ou noms d'accords, peut être vide
  pour harmonie statique-modale)
- `harmonic_rhythm` (chords par bar, > 0)
- `voicing_strategy` + `cadence_at_end`

Lit les `composition.harmonic_motion`, `modal_choice`, `harmonic_pacing`,
`characteristic_riff_construction`, `key_area` des références.

Output parsé via `parse_harmony_decision()` (ou
`parse_harmony_decision_from_response()` pour le raw text). Validation
stricte : `key_root` doit être une note canonique, `harmonic_rhythm`
strictement positif, `mode` non-vide.

### structure-decider (`.claude/agents/structure-decider.md`)

**Premier sphere agent du composition_engine (Phase 2.2).**

**Invoquer** quand l'utilisateur demande de composer une section et
fournit au moins une chanson de référence ("intro 16 bars ambient
inspirée de Pyramid_Song et Heart_Shaped_Box").

L'agent :
1. Lit les `composition.structural_blueprint` et
   `section_count_and_lengths` des références via `song_loader`
2. Synthétise une `StructureDecision` (total_bars, sub_sections,
   breath_points, transition_in/out)
3. Cite explicitement les passages des refs qui ont informé chaque choix
4. Retourne un JSON pur que l'orchestrateur parse via
   `composition_engine.blueprint.agent_parsers.parse_structure_decision()`

Le JSON parsé donne directement un `Decision[StructureDecision]`
assignable à un `SectionBlueprint` via `bp.with_decision("structure", decision)`.

Read-only. Ne modifie jamais le repo.

### regression-detector (`.claude/agents/regression-detector.md`)

**Invoquer automatiquement** dans ces cas :

1. **Avant tout commit qui touche un des 8 fichiers de prod** ou un
   `tests/*.py` — analyser le diff, calculer le blast radius via le
   graph, recommander les tests à lancer.
2. **Avant un push** qui contient des modifs de prod — recommander si
   la suite rapide suffit ou si la suite complète est nécessaire.
3. **À la demande explicite** : "audit régression sur ce changement".

L'agent fait l'**audit intelligent** (lit le diff, croise avec
`graphify-out/graph.json` pour identifier qui dépend des fonctions
modifiées, flagge HIGH RISK si un god node est touché). Il **ne lance
pas les tests** — c'est le rôle du hook `pre-push`.

L'agent et le hook sont complémentaires :
- Hook = filet de sécurité automatique au moment du push
- Agent = audit raisonné, peut être invoqué avant le commit pour
  anticiper et choisir le scope de tests à lancer manuellement

## Composition Engine — Architecture multi-agent (Phase 1 en place)

L'objectif : générer des compositions originales en s'inspirant de plusieurs
chansons à la fois, section par section, avec une équipe d'agents spécialisés
par sphère et un audit de cohérence.

### Séparation rules / inspirations (depuis 2026-04-27)

Le projet sépare les deux couches de données pour stabilité :

| Fichier | Contenu | Volatilité |
|---------|---------|------------|
| `composition_advisor/composition_advisor.json` | **Règles** : theory, voice_leading, tension_release, voicings_recipes, silence_protocol, rhythm_theory, density_curves, recipes_index, philosophy | Stable (rarement modifié) |
| `composition_advisor/inspirations.json` | **Data** : song_dissection_exhaustive (chansons en Schema A v2), song_dissection (light), reference_albums | Croît à chaque ajout de chanson |

`song_loader.py` charge transparent les deux et expose une API unifiée. Pour
ajouter une chanson, on touche **uniquement** `inspirations.json`.

### Sphères

7 sphères couvrent les aspects d'une section :

| Sphère | Décide | Source JSON |
|--------|--------|-------------|
| `structure` | bars, sub-sections, breath points | `composition.structural_blueprint`, `section_count_and_lengths` |
| `harmony` | mode, progression, voicings, harmonic_rhythm | `composition.harmonic_motion`, `modal_choice`, `voicings_recipes` |
| `rhythm` | drum pattern, BPM, swing, polyrhythms | `performance.drum_style`, `rhythm_theory`, `rhythm_advanced` |
| `arrangement` | layers, density_curve, instrumentation_changes | `arrangement.section_instrumentation`, `harmonic_density_per_section`, `density_curves` |
| `dynamics` | arc_shape, start/end dB, peak_bar | `arrangement.dynamic_arc_overall`, `tension_release` |
| `performance` | feel, humanization, articulation, anti-patterns | `performance.tempo_feel_description`, `performance.guitar_style` |
| `fx` | reverb, filter, saturation, stéréo, sidechain | `mixing.compression_philosophy`, `stereo_image_strategy`, `vocal_treatment` |

### Modules clés (Phase 1)

| Module | Rôle |
|--------|------|
| `composition_engine/advisor_bridge/song_loader.py` | Pont read-only vers les chansons (`list_songs`, `get_song`, `find_song`, `query`, `get_advisor_section`). |
| `composition_engine/blueprint/schema.py` | `SectionBlueprint` immuable avec un `Decision[T]` par sphère + provenance (`Citation`, `rationale`, `confidence`). |
| `composition_engine/blueprint/cohesion.py` | Infrastructure de cohésion via `@cohesion_rule` decorator (registry auto-collectée, partial-fill safe). **Phase 1 ne ship aucune règle concrète** — chaque règle naît avec l'agent qui motive son existence (couplage rule-with-consumer, anti-speculative). |
| `composition_engine/director/director.py` | Orchestrateur avec DAG des sphères, mode `GHOST` (blueprint pré-rempli, validation seule). Live mode (LLM agents) ajouté en Phase 2 avec les agents eux-mêmes. |
| `composition_engine/blueprint/composer_adapter.py` | **Phase 2.1** : wire un `SectionBlueprint` au `composer.compose()` existant. API : `blueprint_to_composition(bp)`, `compose_from_blueprint(bp)`, `compose_to_midi(bp, path)`. Phase 2.1 consomme les 4 sphères essentielles (structure, harmony, rhythm, arrangement) ; les 3 autres (dynamics, performance, fx) sont loggées comme "not yet wired" si remplies. |
| `composition_engine/blueprint/midi_export.py` | **Phase 2.1** : writer Standard MIDI File (Format 1, multi-track) en stdlib pur. Permet l'export `.mid` direct depuis un blueprint via `compose_to_midi()`. |
| `composition_engine/blueprint/agent_parsers.py` | **Phase 2.2** : parsers du JSON émis par les sphere agents. Phase 2.2 ship `parse_structure_decision()` qui valide et construit un `Decision[StructureDecision]` à partir du payload de `structure-decider`. Lève `AgentOutputError` si le payload est mal formé. |
| `composition_engine/ableton_bridge/catalog_loader.py` | **Phase 3 prep** : sliced read-only access à `ableton/ableton_devices_mapping.json` (~5500 lignes). Permet à un device-config agent de charger UNIQUEMENT la slice pertinente (~500-800 lignes) au lieu du catalog complet. API : `get_device_spec(name)`, `get_automation_conventions()`, `get_xml_pattern()`, `get_known_bugs(device=None)`, `get_validation_rules()`, etc. Single source of truth — le fichier JSON reste hand-curated par l'utilisateur. |

### Règle d'or : un agent ne délègue jamais à un autre agent

Les agents ne s'invoquent **pas** entre eux. Chaque agent retourne sa
décision pour sa sphère, le **Director** (code Python, déterministe)
agrège et audite. Cela évite les chaînes de subagents et les boucles.

### Comment ajouter une chanson au corpus

1. Édite `composition_advisor/inspirations.json`, ajoute une entrée
   sous `song_dissection_exhaustive.by_artist.<ARTIST>.<SONG>` en suivant
   le schéma des chansons existantes.
2. Vérifie : `python -m composition_engine.advisor_bridge.song_loader`
   doit afficher le nouveau total et retrouver la nouvelle chanson via
   `find_song`.
3. Aucun code Python à toucher : tous les agents lisent automatiquement
   via `song_loader`.

### Comment ajouter une sphère

1. Ajoute un dataclass `XyzDecision` dans `blueprint/schema.py`.
2. Ajoute le nom dans la tuple `SPHERES`.
3. Ajoute un champ `xyz: Optional[Decision[XyzDecision]] = None` sur
   `SectionBlueprint`.
4. Mets à jour `SPHERE_DEPENDENCIES` dans `director/director.py` pour
   placer la nouvelle sphère dans le DAG.
5. (Optionnel) Ajoute des `@cohesion_rule` qui croisent la nouvelle
   sphère avec les existantes.
6. (Phase 2+) Crée `.claude/agents/<xyz>-decider.md` quand prêt à wirer
   le LLM.
