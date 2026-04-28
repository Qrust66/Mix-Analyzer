# Build Motif-Decider — l'agent qui descend au niveau de la note

But : combler le **vrai trou** du composition_engine. Aujourd'hui (Phase
2.6.1), 5 sphere agents décident le squelette (bars, key, tempo, layers,
dB arc) mais **aucun agent ne décide les notes**. Le composer adapter
applique des stubs (`tonic-12` pour bass, kick-on-1 pour drums) — d'où
le résultat plat. Cette phase ajoute un **motif-decider** : la sphère
qui produit des séquences de notes concrètes par layer.

À coller tel quel dans une nouvelle conversation Claude Code.

---

```
Mission : ajouter un sphere agent `motif-decider` au composition_engine
multi-agent. C'est la 6e sphère, **celle qui décide les notes** — pitch,
duration, velocity, microtiming, par layer. Aujourd'hui le composer
applique des stubs (tonique+12 pour bass, kick-sur-le-1 pour drums) ;
cet agent remplace ces stubs par des séquences MIDI substantielles
inspirées des chansons de référence.

## Diagnostic à comprendre AVANT de coder

État Phase 2.6.1 actuel : 5 sphere agents wired (structure, harmony,
rhythm, arrangement, dynamics). **Mais 70% du contenu musical sort de
hand-craft post-hoc et de la connaissance stylistique du LLM**, pas
d'une décision agent traçable. Les agents fixent le SQUELETTE (16 bars,
E Dorian, layers, arc -18 → -6 dB) mais le composer applique des motifs
placeholder. C'est pour ça que les compos sortent plates.

Le motif-decider corrige ça en consommant le blueprint et produisant
les notes concrètes.

## Contexte projet à charger

1. `CLAUDE.md` (hub) puis :
   - `docs/CLAUDE_AGENTS.md` (architecture multi-agent compo + rule
     "un agent ne délègue jamais à un autre agent")
   - `docs/CODING_PRINCIPLES.md` (5 principes : Think Before, Simplicity,
     Surgical, Goal-Driven, Use Graph)

2. Lire **un sphere agent existant** comme template :
   - `.claude/agents/dynamics-decider.md` — le plus récent, pattern à
     copier exactement (in-context examples, pièges, schema strict)

3. Lire le parser pattern :
   - `composition_engine/blueprint/agent_parsers.py` — regarder en
     particulier `parse_dynamics_decision()` et ses helpers `_coerce_*`

4. Lire le schema pattern :
   - `composition_engine/blueprint/schema.py` — regarder comment
     `DynamicsDecision` et `LayerSpec` sont structurés

5. Lire la wiring composer :
   - `composition_engine/blueprint/composer_adapter.py` — où les stubs
     (`_default_motif` par rôle) sont appliqués. C'est là que le
     motif-decider remplacera les stubs.

6. Lire le corpus :
   - `composition_advisor/inspirations.json` — chercher les champs
     `composition.characteristic_riff_construction`,
     `composition.melodic_motifs`, `performance.drum_pattern_detail`,
     `stylistic_figures.signature_phrases`. C'est de là que les notes
     citent leur provenance.

## Le contrat de l'agent

### Input
- Un `SectionBlueprint` avec **au minimum** structure, harmony, rhythm,
  arrangement, dynamics filled (le motif a besoin du squelette complet)
- Liste de chansons de référence (vérifier existence via `song_loader`)
- Brief humain optionnel

### Output : `Decision[MotifsDecision]` JSON

Schema (schema_version 1.0) :

```json
{
  "schema_version": "1.0",
  "motifs": {
    "by_layer": [
      {
        "layer_role": "bass",
        "layer_instrument": "sub",
        "notes": [
          {"bar": 0, "beat": 0.0, "pitch": 36, "duration_beats": 0.25, "velocity": 110},
          {"bar": 0, "beat": 1.5, "pitch": 36, "duration_beats": 0.5,  "velocity": 95},
          {"bar": 0, "beat": 3.0, "pitch": 38, "duration_beats": 0.5,  "velocity": 102},
          {"bar": 1, "beat": 0.0, "pitch": 36, "duration_beats": 0.25, "velocity": 115}
        ],
        "rationale": "Pattern offbeat sub-bass à la Pyramid_Song bar 7 — ghost notes 1.5 et 3.0, accent reset bar 1.",
        "inspired_by": [
          {"song": "Radiohead/Pyramid_Song", "path": "composition.characteristic_riff_construction",
           "excerpt": "Ostinato sub on root + 5th, asymmetric accents"}
        ]
      },
      {
        "layer_role": "drum_kit",
        "layer_instrument": "kit_industrial",
        "notes": [...],
        "rationale": "...",
        "inspired_by": [...]
      }
    ]
  },
  "rationale": "Pattern global section : bass + drums anchor le 4-on-floor avec ghost-notes Pyramid_Song.",
  "inspired_by": [...],
  "confidence": 0.82
}
```

### Contraintes du contenu

- `notes[]` non-vide pour chaque layer de `arrangement.layers`. Si un
  layer n'a pas de notes, omettre ou raise refus.
- `bar` : int ≥ 0, < `structure.total_bars`
- `beat` : float ∈ [0.0, time_signature_numerator). Pour 4/4, [0.0, 4.0).
- `pitch` : int ∈ [0, 127] (MIDI). Doit être dans la gamme de
  `harmony.mode` + `harmony.key_root` (avec tolérance pour
  passing-tones documentés).
- `duration_beats` : float > 0.
- `velocity` : int ∈ [1, 127]. La vélocité absolue est shapée par
  `dynamics.arc_shape` au composer level — la valeur ici est l'**accent
  relatif** du note (ghost = 50-70, normal = 90-110, accent = 120-127).
- `inspired_by` non-vide par layer (provenance obligatoire).

## Build sequence (pattern Phase 2.X éprouvé)

Suivre exactement ce qu'a fait Phase 2.6 (dynamics) :

### A. Schema (5 min)
1. Ajouter `MotifsDecision`, `LayerMotif`, `Note` dataclasses
   (frozen, tuples) dans `composition_engine/blueprint/schema.py`
2. Re-exporter dans `composition_engine/blueprint/__init__.py`
3. Tests dataclass dans `tests/test_blueprint_schema.py`

### B. Parser (15 min)
1. `parse_motifs_decision(payload)` +
   `parse_motifs_decision_from_response(text)` dans
   `composition_engine/blueprint/agent_parsers.py`
2. `SUPPORTED_MOTIFS_SCHEMA_VERSIONS = frozenset({"1.0"})`
3. Constantes publiques (single source of truth) :
   - `MOTIF_PITCH_MIN = 0`, `MOTIF_PITCH_MAX = 127`
   - `MOTIF_VELOCITY_MIN = 1`, `MOTIF_VELOCITY_MAX = 127`
   - `MOTIF_BEAT_TOLERANCE = 1e-6` pour les comparaisons float
4. Validation stricte : ranges, beat dans [0, numerator), bar dans
   [0, total_bars) si structure connu. Ne pas check la gamme dans le
   parser (le motif-decider peut produire passing-tones — la cohesion
   rule s'en charge si nécessaire).
5. Tests parser dans `tests/test_blueprint_agent_parsers.py` :
   minimum-valid, ranges, fences, error payload, blueprint integration

### C. Cohesion rules (10 min) — rule-with-consumer
Au moins une règle BLOCK :
- `motifs_layer_coverage_matches_arrangement` : chaque
  `arrangement.layers[i]` doit avoir un `motifs.by_layer[?]` dont le
  role + instrument matchent. Sinon BLOCK.

Et une WARN :
- `motifs_pitches_in_harmony_scale` : warn si > 30% des pitches sont
  hors gamme (passing tones tolérés mais pas une mélodie atonale).

Tests cohesion dans `tests/test_blueprint_cohesion.py`.

### D. Agent .md (20 min)

`.claude/agents/motif-decider.md` — copier exactement la structure de
`dynamics-decider.md` :
- Mission
- Source de vérité (avec accent sur les champs riff/motif/pattern de
  inspirations.json)
- Schema de sortie (avec contraintes)
- Procédure (5 étapes : parse brief, lire refs, identifier patterns,
  synthétiser notes par layer, citer)
- 4 in-context examples DIFFÉRENTS, par exemple :
  1. Pattern bass simple (1 ref) sub-bass tonic + offbeats
  2. Drum pattern industriel (NIN-style) — kick + snare + ghost-hats
  3. Lead motif modal (Aeolian, Pyramid_Song-style) — mélodie 4-bar
     avec rest sur les beats forts
  4. Refus (refs absentes du corpus)
- Pièges courants : pitches hors range, beats > numerator, velocities=0,
  inspired_by vide, layer manquant
- Règles de comportement : output JSON pur, read-only, français dans
  rationale, confidence honnête

### E. Composer wiring (15 min)
Dans `composition_engine/blueprint/composer_adapter.py` :
1. Si `bp.motifs is not None` :
   - Pour chaque layer dans `arrangement.layers`, chercher la
     `LayerMotif` matchante dans `motifs.by_layer`
   - Convertir `notes[]` en NoteEvents pour le composer (qui consomme
     déjà des Note objects via `track_layerer`)
   - **REMPLACER `_default_motif`** par les notes de l'agent
2. Si `bp.motifs is None` ET `bp.arrangement is not None` :
   - Garder `_default_motif` comme fallback ET log un WARNING explicite
     : "no motif decision — falling back to placeholder motifs (output
     will sound flat)"
3. Si `bp.dynamics` est filled, appliquer le velocity envelope sur les
   notes (multiplier velocity par le coefficient dB→linear à chaque
   bar). C'est le moment de wirer dynamics réellement (Phase 3+
   anticipé).

### F. Tests d'intégration (10 min)
Dans `tests/test_v25_integration.py` ou un nouveau test :
1. Build un MotifsDecision à la main (3 layers × 4 bars)
2. Ajouter à un blueprint complet (5 sphères + motifs)
3. `compose_to_midi(bp, output.mid)`
4. Lire le .mid produit
5. Asserter que les notes du .mid match les notes décidées (pitch,
   timing, velocity)

### G. Doc + CHANGELOG + commit
1. Ajouter motif-decider à `docs/CLAUDE_AGENTS.md`
2. CHANGELOG entry "Phase 2.7 — motif-decider" (note : décale les
   phases planifiées : performance devient 2.8, fx devient 2.9)
3. Commit avec format conventionnel `feat(blueprint): Phase 2.7 — ...`

## Audit obligatoire après build

Comme Phase 2.6.1 a fait pour Phase 2.6 :

1. Lister les 5-7 faiblesses du build initial (severity HIGH/MED/LOW)
2. Présenter en table "faiblesse → force"
3. Proposer Phase 2.7.1 cleanup pour les HIGH+MED
4. Attendre go user avant de cleanup

## Definition of done

- [ ] `motif-decider.md` complet (4 in-context examples min)
- [ ] `MotifsDecision`, `LayerMotif`, `Note` dataclasses + tests schema
- [ ] `parse_motifs_decision` + tests parser (≥ 15 tests, parametrize
      sur ranges/edges)
- [ ] `motifs_layer_coverage_matches_arrangement` cohesion rule + tests
- [ ] composer_adapter wire les motifs à la place des stubs
- [ ] **dynamics velocity envelope wirée** (bonus) — le composer
      multiplie velocity de chaque note par le coefficient dynamique
- [ ] Test d'intégration end-to-end : .mid produit a les bonnes notes
- [ ] CLAUDE_AGENTS.md mis à jour
- [ ] CHANGELOG.md entry Phase 2.7
- [ ] Audit Phase 2.7 livré (5-7 faiblesses identifiées)
- [ ] Commit propre, ne pas pusher sans demander

## Brief créatif minimal pour tester

Si l'utilisateur ne fournit pas, demande en 1 phrase : "donne-moi 1
section (genre / refs / 8-16 bars) pour tester l'agent end-to-end".
Puis fais un test réel avec invocation du motif-decider (Agent tool,
subagent_type=motif-decider).

## Pourquoi cette phase est critique

Avant cet agent :
- 70% de la musique vient de hand-craft post-hoc + connaissance LLM
- 30% vient des agents (squelette uniquement)
- Le pipeline multi-agent est cérémonieux

Après cet agent :
- Les notes citent des passages réels du corpus de références
- La provenance est traçable (chaque note référence un riff existant)
- Les compos sont substantielles parce que c'est *du vrai matériel
  cité*, pas du préfab
- Le pipeline justifie son coût en tokens

C'est la phase qui transforme le système d'un outil de squelette en
outil de composition.
```

---

Une fois cet agent shippé, les phases planifiées suivantes deviennent :
- **Phase 2.8** = performance-decider (feel, humanization, articulation)
  — peut maintenant nuancer les notes du motif-decider
- **Phase 2.9** = fx-decider (reverb, filter, sidechain)
- **Phase 3+** = wirage Ableton-side (mix_engine déjà commencé Phase 4.X)
