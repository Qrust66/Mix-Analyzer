# DEVICE_MAPPING_EXTENSION_GUIDE.md

**Procédure canonique pour ajouter un nouveau device/plugin au mix_engine.**

Ce guide existe pour qu'AUCUNE session Claude Code (passée, présente, ou
future) n'oublie une étape lors de l'intégration d'un nouveau device.
Suivre l'ordre — chaque étape dépend de la précédente.

---

## Quand utiliser ce guide

- L'utilisateur partage un nouveau plugin Ableton stock pas encore mappé
  (ex: MultibandDynamics, Auto Pan, Beat Repeat)
- L'utilisateur partage un VST3 third-party (ex: FabFilter Pro-L 2,
  Soothe2, bx_xl V2, iZotope Ozone)
- Une session précédente a flag un device manquant qu'un agent réclame

**Avant de commencer** : interroger `device-mapping-oracle` agent pour
vérifier si le device est PARTIELLEMENT mappé. Souvent un device a déjà
quelques params dans le catalog mais incomplet.

---

## Triage initial (obligatoire avant code)

Classer le device dans une catégorie de complexité :

| Niveau | Critère | Effort estimé | Méthodologie |
|---|---|---|---|
| 🟢 **FACILE** | Plugin similaire à un device déjà mappé (autre limiter, autre comp, autre EQ) | 30-60 min, 1 commit | Direct code → tests → commit |
| 🟡 **MOYEN** | Nouveau type fonctionnel mais rentre dans schema existant (multiband, transient designer, M/S phase-coherent) | 2-4h, 2-3 commits | Pass 1 mini design → validation user → code |
| 🔴 **COMPLEXE** | Paradigme unique (Soothe2 spectral, Ozone multi-module, reference matching) | 1-2 jours | Pass 1 + audit + Pass 2 + Pass 3 (méthodologie complète Tier A) |

Documenter le niveau dans le commit message + rationale.

---

## Inputs requis (à demander à l'utilisateur si manquants)

1. **Nom + manufacturer** (exact, ex: "FabFilter Pro-L 2", "Ableton MultibandDynamics")
2. **Type fonctionnel** (limiter / comp / EQ / multiband / saturator / stereo / transient / FX / autre)
3. **Liste des paramètres** :
   - Nom XML exact tel qu'il apparaît dans `<PluginDesc>` ou `<DeviceData>` block
   - Range min/max + unité (dB, ms, Hz, %, 0..1, enum, ...)
   - Type (float / int / enum / bool)
   - Default value
4. **Use case** ("limiter true peak référence", "drum bus transient enhancer", ...)
5. **Lane(s) Tier A impactée(s)** (mastering, dynamics-corrective, eq-corrective, stereo-and-spatial, automation, chain-builder)
6. **Bizarreries XML write** (params en log scale, wrapper requis, sidechain block, etc.)

**Méthode la plus rapide** : utilisateur fournit un `.als` test avec le
plugin instancié + valeurs connues → extraire mapping XML automatiquement
via `als_utils.py` decompress + grep.

---

## Checklist obligatoire (12 étapes ordonnées)

### 1. Mapping JSON source-of-truth

**Fichier** : `ableton/ableton_devices_mapping.json`

- [ ] Ajouter entry top-level pour le device
- [ ] Pour chaque paramètre :
  - [ ] `xml_pattern` (template XML écriture)
  - [ ] `value_range` (tuple [min, max])
  - [ ] `value_type` ("float" | "int" | "enum" | "bool")
  - [ ] `default` (valeur par défaut Ableton)
  - [ ] `automation_compatible` (bool)
  - [ ] `envelope_kind` ("FloatEvent" | "BoolEvent" | "EnumEvent")
- [ ] Section `write_rules` (règles d'écriture XML, ex: "Manual Value attribute is the static value")
- [ ] Section `validation` (cross-checks, ex: "1.0 ≤ ratio ≤ 100.0")
- [ ] Section `known_bugs` (bug_id, summary, mitigation)
- [ ] Section `interactions` (effets cross-device, ex: "After Saturator: ratio behaviour shifts")

**Vérification** : `device-mapping-oracle` doit pouvoir répondre à une
query sur le nouveau device sans erreur.

### 2. ALS Manipulation Guide (si bizarreries XML)

**Fichier** : `ableton/ALS_MANIPULATION_GUIDE.md`

- [ ] Ajouter pitfall si write rule non-trivial (ex: VST3 wrapper, ID range
      collision, BoolEvent vs FloatEvent confusion)
- [ ] Référencer le bug_id du mapping JSON

Skip si le device est trivial (params simples, pas de wrapper).

### 3. Schema constants — `mix_engine/blueprint/schema.py`

**Selon le type de plugin** (peut toucher plusieurs sections) :

#### Si automatable :
- [ ] Ajouter à `VALID_AUTOMATION_TARGET_DEVICES`
- [ ] Ajouter entry à `COMMON_AUTOMATION_PARAMS_BY_DEVICE`
  (tuple de noms de params typiquement automatés)

#### Si dynamics-relevant :
- [ ] Ajouter à `VALID_DYNAMICS_DEVICES`
- [ ] Si nouveau type d'action : ajouter à `VALID_DYNAMICS_TYPES`
- [ ] Ranges de params dynamics si distincts (rare)

#### Si mastering-relevant :
- [ ] Ajouter à `MASTER_DEVICES_BY_TYPE[<existing_type>]` (limiter_target, glue_compression, etc.)
- [ ] OU si nouveau move type :
  - [ ] Ajouter à `VALID_MASTER_MOVE_TYPES`
  - [ ] Créer entry `MASTER_DEVICES_BY_TYPE[<new_type>]`
  - [ ] Créer entry `MASTER_CHAIN_POSITION_BY_TYPE[<new_type>]`
  - [ ] Ajouter chain_positions à `VALID_MASTER_CHAIN_POSITIONS` si nouveau slot
  - [ ] Ajouter Optional fields à `MasterMove` dataclass si params spécifiques
  - [ ] Constants ranges parser-enforced (`MASTER_<X>_MIN/MAX`)

#### Si chain-buildable :
- [ ] Ajouter à `VALID_CHAIN_DEVICES`
- [ ] Si chain_position spécifique requis : `VALID_CHAIN_POSITIONS` ou `VALID_DYNAMICS_CHAIN_POSITIONS`

#### Si EQ-replacement :
- [ ] Décision : nouveau type ou wrapper sur Eq8 ? Pour VST3 EQ (FabFilter Pro-Q), garder Eq8 comme device par défaut ; ajouter le VST3 comme `device` choice dans `MASTER_DEVICES_BY_TYPE["master_eq_band"]` si master scope.

#### Universel :
- [ ] Ajouter le nom du device aux exports `__all__` à la fin du fichier

### 4. Parser cross-field — `mix_engine/blueprint/agent_parsers.py`

- [ ] Imports des nouvelles constants depuis `schema.py`
- [ ] Si nouveau move type : entry `_<TYPE>_VALUE_FIELDS_BY_TYPE` (mastering)
      ou équivalent (spatial, dynamics)
- [ ] Cross-field check pour required fields du nouveau type
- [ ] Cross-field check pour mutual exclusion avec autres types
- [ ] Mise à jour `__all__` parser exports si nouveau symbol exporté

### 5. Module __init__.py — `mix_engine/blueprint/__init__.py`

- [ ] Re-exports des nouvelles constants depuis `schema.py`
- [ ] Re-exports des nouveaux parsers / dataclasses
- [ ] `__all__` mis à jour

**Piège fréquent** : oublier les exports `__init__.py` → tests passent
mais imports user-side cassent.

### 6. Tests parser — `tests/test_mix_engine_agent_parsers.py`

- [ ] Happy path test pour chaque scenario use case (1 minimum par
      scenario nouvellement supporté)
- [ ] Cross-field rejection test pour chaque check ajouté
- [ ] Test que le nouveau device est dans `VALID_<X>_DEVICES`
- [ ] Test schema_version unsupported reject
- [ ] Test depth-light (rationale ≥ 50 chars + cite ≥ 1) si applicable

**Convention** : nommer les tests `test_<lane>_<phase>_<device>_<scenario>`
(ex: `test_mastering_phase49x_multibanddynamics_low_band_threshold_valid`)

### 7. Agent prompts impactés — `.claude/agents/*.md`

Lister explicitement quels agents doivent citer le nouveau device.
Standard : tout agent dont la lane est dans la matrice ci-dessous :

| Type plugin | Agents prompts à toucher |
|---|---|
| Limiter / Multiband / Comp | `mastering-engineer.md`, `dynamics-corrective-decider.md`, `automation-engineer.md`, `chain-builder.md` |
| EQ / Resonance suppressor | `eq-corrective-decider.md`, `mastering-engineer.md`, `automation-engineer.md` |
| Saturator / Exciter | `mastering-engineer.md`, `automation-engineer.md` |
| Stereo / M/S | `stereo-and-spatial-engineer.md`, `mastering-engineer.md`, `automation-engineer.md` |
| Transient | `dynamics-corrective-decider.md`, `mastering-engineer.md` |
| FX (reverb/delay/etc) | OUT-OF-SCOPE actuel — Phase 4.X+ futurs lanes |

Pour chaque agent prompt :
- [ ] Ajouter le device au tableau "Devices mappés" de la section
      catalog/intake
- [ ] Mentionner le device dans le scenario où il s'applique (sans
      hardcoding de targets — cf. Phase 4.9.1 rule)
- [ ] Anti-patterns spécifiques au device (ex: "Limiter avant Glue =
      anti-pattern, Limiter toujours dernier")

### 8. Mémoire méthodologie

**Fichier** : `~/.claude/projects/.../memory/tier_a_mix_agent_methodology.md`

- [ ] Si leçon nouvelle apprise pendant l'intégration → enrichir
      "Anti-patterns" ou "Validation Phase X.Y" section
- [ ] Si pattern d'extension réutilisable → documenter pour futures
      sessions

### 9. Vérification globale

- [ ] `python -c "from mix_engine.blueprint import <new_constants>; print('OK')"` (sanity check imports)
- [ ] `python -m pytest tests/test_mix_engine_agent_parsers.py -q` doit passer
- [ ] `python -m pytest tests/ -q` (full suite) doit passer (no regression)
- [ ] `git diff --stat` review : tous les fichiers attendus modifiés ?
      Aucun fichier inattendu touché ?

### 10. Cohérence inter-agents (cross-lane review)

Si le nouveau device touche plusieurs lanes, vérifier :

- [ ] Les ranges sont cohérents entre agents (ex: Compressor2 ratio
      cap dans `mastering-engineer` MASTER_GLUE_RATIO_MAX=4.0 vs
      `dynamics-corrective` DYN_RATIO_MAX=100.0 — différent par scope)
- [ ] Les chain_position vocabulaires se référencent sans collision
- [ ] Pas de cross-field check qui contredit un autre agent

### 11. Commit + push

Format du commit message :

```
feat(mix_engine): Phase X.Y.Z — <DeviceName> mapped + integrated

Niveau de complexité : 🟢/🟡/🔴

Lanes impactées : <liste>
Schema additions :
- VALID_<X>_DEVICES extension
- (nouveaux constants si applicable)

Parser additions :
- Cross-field check #N : <description>

Tests : N nouveaux (X happy paths + Y rejection)

Source mapping : <référence à .als test ou catalog VST3>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

- [ ] Push vers `origin/main`
- [ ] Communiquer à l'user : "Pull dans GitHub Desktop"

### 12. Documentation post-intégration (si 🟡 ou 🔴)

- [ ] Mettre à jour `docs/MIX_ENGINE_ARCHITECTURE.md` si nouveau move type
- [ ] Si nouveau cas d'usage non couvert par scenarios existants : doc dans agent prompt
- [ ] Si bug Ableton découvert pendant l'intégration : mention dans `ALS_MANIPULATION_GUIDE.md`

---

## Pièges fréquents

### Piège 1 — Oublier `__init__.py` exports
Tests parser passent (imports relatifs) mais l'utilisateur final fait
`from mix_engine.blueprint import NewDevice` → ImportError. **Toujours**
ajouter aux deux : `schema.__all__` + `__init__.py` re-exports + `__init__.__all__`.

### Piège 2 — Hardcoder un target dans le prompt agent
Ex: "FabFilter Pro-L 2 default ceiling = -0.3 dBTP for streaming". **NON**.
Le ceiling vient de `brief.target_lufs_i` ou `genre_context`. Le prompt
mentionne seulement les **caps absolus** (parser-enforced), pas les targets.
Cf. règle Phase 4.9.1 mémoire `tier_a_mix_agent_methodology.md`.

### Piège 3 — Cross-field check trop laxiste
Ex: ne pas vérifier que `target_track == MASTER_TRACK_NAME` quand le
device est master-only. Tier B se retrouve avec un move qui ne fait pas
sens, échec silencieux ou erreur cryptique.

### Piège 4 — Tests happy path seulement
Pour chaque cross-field check ajouté, **un test rejection** correspondant.
Sinon les checks parser-enforced pourrissent silencieusement (pas de
detection si quelqu'un les casse plus tard).

### Piège 5 — VST3 wrapper Ableton vs native device
Les VST3 sont encodés différemment (`<PluginDesc>` block) des Ableton
natives (`<DeviceData>`). `device-mapping-oracle` doit clarifier le
pattern XML. Si VST3 : prévoir le `<PluginDesc>` wrapper dans `xml_pattern`.

### Piège 6 — Sidechain routing path text fragile
Si le nouveau device a un sidechain (ex: comp avec sidechain externe),
le path texte `AudioIn/Track.N/PostFxOut` est sensible aux renommages.
Bug connu B-CMP-04 — référencer dans `interactions`.

### Piège 7 — Chain_position collision
Si le nouveau device introduit une nouvelle position dans la chaîne (ex:
"master_dynamic_eq" pour un Soothe2 master), s'assurer que la position
existe dans le `VALID_MASTER_CHAIN_POSITIONS` ET dans le tableau de chain
order canonique du prompt agent.

---

## Exemple concret : ajout SmartLimit Phase 4.8.3 (🟢)

**Référence commit** : `7e777a8 feat(mix_engine): Phase 4.8.3 — automation
device coverage extension + Eq8 band_type compatibility`

Étapes appliquées :
1. Mapping JSON : déjà mappé partiellement (oracle a confirmé)
2. Schema : ajout à `VALID_AUTOMATION_TARGET_DEVICES` + entry dans
   `COMMON_AUTOMATION_PARAMS_BY_DEVICE` avec params `General_inputGain`,
   `General_outputGain`, `General_limiterThreshold`, `General_attack`,
   `General_release`, `General_saturation`
3. Parser : aucun cross-field check spécifique requis (paramètres simples)
4. Tests : test_automation_phase483_smartlimit_mastering_envelope (happy)
5. Agent prompts : automation-engineer.md scenario MASTERING-A mentionne
   SmartLimit comme alternative à Limiter natif

**Total** : 1 commit, ~45 min, no regression.

Phase 4.9 ensuite a référencé SmartLimit dans `mastering-engineer.md` sans
re-mapping (catalog déjà à jour).

---

## Checklist condensée (à coller en TODO si tu démarres une intégration)

```
- [ ] Triage 🟢/🟡/🔴
- [ ] device-mapping-oracle query (déjà mappé partiellement ?)
- [ ] Inputs user complets (nom, type, params, range, lane)
- [ ] 1. ableton_devices_mapping.json (xml_pattern + ranges + write_rules)
- [ ] 2. ALS_MANIPULATION_GUIDE.md (si bizarrerie)
- [ ] 3. schema.py (VALID_*_DEVICES + dataclass fields + ranges + __all__)
- [ ] 4. agent_parsers.py (imports + cross-field checks + __all__)
- [ ] 5. __init__.py (re-exports + __all__)
- [ ] 6. tests (happy + rejection + import test)
- [ ] 7. agent prompts impactés (table devices + scenarios + anti-patterns)
- [ ] 8. mémoire méthodologie (si leçon nouvelle)
- [ ] 9. python -m pytest tests/ -q passes
- [ ] 10. cross-lane cohérence (ranges, chain_positions)
- [ ] 11. commit + push (format Phase X.Y.Z)
- [ ] 12. docs MIX_ENGINE_ARCHITECTURE.md (si 🟡/🔴)
```

---

## Liens canoniques

- `device-mapping-oracle` agent : `.claude/agents/device-mapping-oracle.md`
- `als-manipulation-oracle` agent : `.claude/agents/als-manipulation-oracle.md`
- Mapping JSON : `ableton/ableton_devices_mapping.json`
- ALS pitfalls : `ableton/ALS_MANIPULATION_GUIDE.md`
- Méthodologie Tier A : `~/.claude/projects/.../memory/tier_a_mix_agent_methodology.md`
- Schema source-of-truth : `mix_engine/blueprint/schema.py`
- Parser source-of-truth : `mix_engine/blueprint/agent_parsers.py`
- Architecture mix_engine : `docs/MIX_ENGINE_ARCHITECTURE.md`
- Coding principles : `docs/CODING_PRINCIPLES.md`
