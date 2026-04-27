# MIX_ENGINE_ARCHITECTURE.md — Phase 4.0 design doc

Plan d'architecture pour le module `mix_engine/`, parallèle de
`composition_engine/`. Ce document est la **North Star** — il pose le
contrat sur lequel tous les futurs mix agents s'aligneront. Aucun agent
mix n'est buildé ici ; on pose les rails.

> **Statut** : design — module skeleton créé, agents à builder
> graduellement (rule-with-consumer, comme côté compo).

## 1. Pourquoi un mix_engine séparé du composition_engine

| Composition | Mix |
|---|---|
| Génère du MIDI à partir d'un brief | Sculpte un .als existant à partir d'un diagnostic |
| Output : `.mid` puis injection .als | Output : `.als` patché in-place (avec backup) |
| Lit `inspirations.json` (corpus de chansons) | Lit `ableton_devices_mapping.json` + Excel report |
| 7 sphère agents (structure, harmony, …) | 12 mix agents + 2 oracles |
| Director DAG dans `composition_engine/director/` | Director DAG dans `mix_engine/director/` |

Mêmes patterns, mêmes disciplines — module séparé pour ne pas mélanger
les concerns. Une session compo ne charge pas le mix_engine et vice-versa.

## 2. Couche partagée : ableton_bridge

`composition_engine/ableton_bridge/catalog_loader.py` existe déjà.
Phase 4.0 promeut conceptuellement cette couche en **infrastructure
partagée** entre les deux engines — physiquement, le module reste
sous `composition_engine/` jusqu'à ce qu'un mix agent concret en ait
besoin (déplacement = atomic move quand le moment vient, pas
maintenant).

Les deux oracles (cf. §4) s'appuient sur :
- `catalog_loader` (slice JSON déterministe) → `device-mapping-oracle`
  (interface LLM proactive)
- `als_utils.py` + `ALS_MANIPULATION_GUIDE.md` → `als-manipulation-oracle`
  (interface LLM proactive)

## 3. Structure du module mix_engine/

```
mix_engine/
├── __init__.py                 — public API
├── blueprint/
│   ├── __init__.py
│   ├── schema.py               — MixBlueprint, MixDecision[T], 12 *Decision
│   ├── cohesion.py             — @mix_cohesion_rule decorator + registry
│   ├── agent_parsers.py        — parse_*_decision(), AgentOutputError
│   └── als_writer.py           — applique un MixBlueprint sur un .als
├── director/
│   ├── __init__.py
│   └── director.py             — Mix Director, MIX_DEPENDENCIES DAG, modes
├── diagnostic/
│   ├── __init__.py
│   └── excel_loader.py         — read-only access au rapport Excel Mix Analyzer
└── README.md                   — pointer vers ce doc
```

Aucun fichier n'est implémenté Phase 4.0. Les modules sont des
skeletons avec docstrings claires.

## 4. Les 2 oracles (couche Ableton-expertise)

Pattern identique à `song_loader` (Python déterministe) +
`structure-decider` (LLM) côté compo :

| Oracle | Backed by | Rôle |
|---|---|---|
| **device-mapping-oracle** | `catalog_loader.py` | Donne la slice exacte d'`ableton_devices_mapping.json` pour un param/device. Synthétise XML pattern + write rules + validation + bugs connus + interactions. Évite aux mix agents de re-charger 5500 lignes |
| **als-manipulation-oracle** | `ALS_MANIPULATION_GUIDE.md` + `als_utils.py` | Procédures sûres pour toute opération .als (gunzip → patch → gzip). Cite les 5 pièges. Source d'autorité pour "comment faire X dans un .als" sans casser |

**Symétrie** : oracles = profs (avant l'action) ; `als-safety-guardian`
(existe déjà) = correcteur (après l'action). Aucun mix agent ne lit
directement le JSON ou le MD — ils interrogent les oracles.

## 5. MixBlueprint — contrat de données

Mirror du `SectionBlueprint`. Un `MixBlueprint` immuable porte la
décomposition d'une décision mix par lane :

```python
@dataclass(frozen=True)
class MixBlueprint:
    name: str                          # nom de la session ou track
    diagnostic: Optional[MixDecision[DiagnosticReport]] = None
    routing: Optional[MixDecision[RoutingDecision]] = None
    eq_corrective: Optional[MixDecision[EqCorrectiveDecision]] = None
    eq_creative: Optional[MixDecision[EqCreativeDecision]] = None
    dynamics_corrective: Optional[MixDecision[DynamicsCorrectiveDecision]] = None
    saturation_color: Optional[MixDecision[SaturationColorDecision]] = None
    stereo_spatial: Optional[MixDecision[StereoSpatialDecision]] = None
    automation: Optional[MixDecision[AutomationDecision]] = None
    chain: Optional[MixDecision[ChainBuildDecision]] = None
    mastering: Optional[MixDecision[MasteringDecision]] = None
```

Chaque `*Decision` porte sa **provenance** : qui décide, sur quoi
(citations du diagnostic), pourquoi (rationale), confidence.

## 6. Mix Director — DAG d'exécution

```
mix-diagnostician                                   ← Phase 1 obligatoire
        │
        ▼
routing-and-sidechain-architect                     ← foundation (broken refs first)
        │
        ▼
[ dynamics-corrective | eq-corrective | stereo-spatial ]   ← parallélisables
        │
        ▼
[ eq-creative | saturation-color ]                  ← parallélisables (couleur)
        │
        ▼
chain-builder                                        ← compose les devices choisis
        │
        ▼
automation-engineer (modes creative + corrective)    ← écrit les enveloppes
        │
        ▼
mastering-engineer                                   ← last-mile, master bus only
        │
        ▼
mix-safety-guardian                                  ← gate de livraison
```

Chaque flèche = sortie typée d'un agent → input d'un autre. Aucun agent
n'a besoin de relire le `.als` brut une fois `mix-diagnostician` a
produit son rapport.

Modes du Director (parallèle au compo) :
- `GHOST` : `MixBlueprint` pré-rempli, validation seule (utile pour tests)
- `LIVE` : LLM agents invoqués séquentiellement
- `INTERACTIVE` : utilisateur valide chaque lane avant la suivante

## 7. Cohesion — règles cross-lane

Pattern identique à `composition_engine/blueprint/cohesion.py`.
Exemples concrets de règles mix :

| Règle | Sévérité | Lanes |
|---|---|---|
| `eq_cuts_dont_create_phase_holes_with_neighbours` | warn | eq_corrective × eq_corrective (cross-track) |
| `sidechain_target_exists_in_routing` | block | dynamics_corrective × routing |
| `master_ceiling_below_minus_03_dbtp` | block | mastering |
| `automation_envelope_targets_active_param` | block | automation × any device |
| `chain_order_respects_signal_flow` | warn | chain × all devices |

Toujours **rule-with-consumer** : pas de règle écrite avant que l'agent
qui produit la valeur existe.

## 8. Hooks d'intégration

Pour que les agents soient tissés et pas juste posés :

| Hook | Type | Action |
|---|---|---|
| `UserPromptSubmit` → `mix_engine_router.py` | Suggestion | Patterns "résonance à X Hz", "écrête au master", "trop large stéréo" → suggère l'agent |
| `PostToolUse` (Write/Edit sur `.als`) | Auto-invoke | Lance `als-safety-guardian` après chaque écriture |
| `pre-commit` | Block | Refuse les commits qui touchent `.als` sans tag de l'agent producteur dans le message |
| `pre-push` | Block | Si le commit modifie `mix_engine/` → suite tests mix obligatoire |

Le hook `mix_engine_router.py` rejoindra `graphify_reminder.py` et
`cost_discipline_reminder.py` dans `.claude/hooks/`.

## 9. Améliorations prévues du JSON catalog

(à appliquer **graduellement** quand un mix agent les motive — pas
en bulk preemptif)

| Faiblesse actuelle | Force | Quand |
|---|---|---|
| Shape hétérogène par device (`Eq8.global_params` vs `Saturator.main_section`) | Schéma uniforme `sections: { name: { params: [...] } }` | Quand chain-builder en aura besoin |
| `automation_compatibility` éparpillé | Champ explicite par param | Quand automation-engineer démarrera |
| Pas de range par genre | `genre_recommended_ranges: {industrial, ambient, …}` | Quand un 2e projet de genre opposé arrivera |
| Interactions device-à-device non capturées | `interaction_warnings: [...]` | Quand chain-builder choisira l'ordre |
| `$end_to_end_validation` en prose | Predicates exécutables | Quand les cohesion rules les consommeront |

L'oracle absorbe l'inconsistance en attendant — c'est sa raison d'être.

## 10. Première cohorte à builder (Phase 4.1)

Les 3 sans qui les autres travaillent à l'aveugle :

1. **device-mapping-oracle** — interface active sur `catalog_loader`
2. **mix-diagnostician** — produit le rapport structuré que tous les
   autres consomment
3. **eq-corrective-engineer** — premier mix agent à valeur immédiate
   (Eq8 est le device le plus mappé, le plus testé via Mix Analyzer)

Tout le reste arrive **quand un projet réel le demande**, pas avant.

## 11. Définition de "haute qualité" pour cet environnement

5 axes que toute session mix-side doit respecter :

1. **Backups automatiques** : tout `.als` patché s'écrit sous un
   nouveau nom + le précédent est conservé dans `Backup/`
2. **Provenance citée** : chaque move est traçable au diagnostic qui
   l'a motivé (pas de mouvement "réflexe")
3. **4 checks holistiques avant chaque move** (cf. PDF mix engineer) :
   collateral impacts, compensations, exploit data, justification
4. **Idempotence** : ré-appliquer le même MixBlueprint sur le même
   `.als` produit le même résultat
5. **Reversibility** : chaque move est annotable + supprimable (audit
   trail dans le `.als` ou en sidecar JSON)

## 12. Ce qui n'est PAS dans le scope Phase 4.0

- ❌ Implémenter les 12 mix agents
- ❌ Réorganiser `composition_engine/ableton_bridge/` (atomic move plus tard)
- ❌ Refactor de `ableton_devices_mapping.json` (graduel)
- ❌ MixBlueprint Python implémenté (skeleton avec docstrings seulement)
- ❌ Mix Director Python implémenté (skeleton)

Phase 4.0 = **rails posés**. Phase 4.1+ = trains qui roulent dessus.
