# Feature 8 — EQ8 consolidation / reconciliation

**Version spec :** 1.0 (draft)
**Date :** 2026-04-23
**Statut :** Planifiée, non démarrée
**Dépendances :** Features 1, 6, 7 idéalement livrées pour avoir matière à consolider
**Effort estimé :** 6-8 heures Claude Code (7-10 micro-commits — complexité élevée)

---

## 1 — Objectif et justification

### Ce que fait la feature

Consolide intelligemment les EQ8 accumulés sur une track au fil des features correctives pour respecter la règle Qrust "maximum 3 EQ8 correctifs par track" (+1 Musical Enhancement optionnel), tout en **préservant intégralement l'intention et le comportement** de chaque traitement.

### Pourquoi cette feature

Au fil de l'utilisation des features 1, 6, 7 et des re-runs de `write_resonance_suppression`, une track peut finir avec plus de 3 EQ8 correctifs :

- Peak Resonance (v1, généré il y a 1 semaine)
- Peak Resonance (v2, re-généré hier après nouveau bounce)
- CDE Correction (v1, appliqué en Phase 2)
- CDE Correction (v2, enrichi en Phase 3)
- HPF/LPF Dynamic (Feature 6)
- Musical Enhancement (Feature 7)

6 EQ8 sur une track. Trop. Viole la règle Qrust.

Feature 8 réconcilie :
- Les multiples versions d'un même rôle (2× Peak Resonance → 1 Peak Resonance fusionné)
- Les rôles similaires qui peuvent coexister dans un même EQ8 (si CDE Correction a seulement 2 bandes et Peak Resonance en a 4, on peut tout caser dans un seul EQ8 si nécessaire)
- Les bandes redondantes ou qui se chevauchent (si deux bandes cuttent à des fréquences très proches, on fusionne en combinant leurs gains)

### Contraintes philosophiques

Feature 8 respecte **strictement** :

- La règle "dynamique par défaut" — aucune automation perdue dans le process de consolidation
- La séparation épistémique si possible — si on peut garder 3 EQ8 distincts (Static / Peak Resonance / CDE), on préfère ça à 1 EQ8 fourre-tout
- La préservation du travail existant — jamais perdre une bande sans consentement explicite
- Le principe de réversibilité — backup complet avant, revert possible après

### Résultat attendu

Une fonction `consolidate_eq8_chain` qui :

1. Analyse tous les EQ8 d'une track
2. Classifie chaque EQ8 dans un des 3+1 rôles (Static / Peak Resonance / CDE / Musical)
3. Si surnombre, propose un plan de consolidation
4. Si validation utilisateur, exécute la consolidation avec préservation des automations
5. Si conflits irrésolus (ex: deux enhancements musicaux sur la même bande), demande arbitrage utilisateur

---

## 2 — Cas de consolidation typiques

### Cas 1 — Doublons du même rôle

Track a 2 EQ8 "Peak Resonance" (v1 et v2). Le plus récent gagne, l'ancien est supprimé. Si le plus ancien a des bandes que le récent n'a plus (ex: v2 a re-détecté moins de peaks), **demander arbitrage utilisateur** : "l'ancien avait une correction à 247 Hz qui a disparu de v2, veux-tu la garder ?"

### Cas 2 — Rôles compatibles à faible usage

Track a :
- Peak Resonance avec 3 bandes actives (bandes 1, 2, 3)
- CDE Correction avec 2 bandes actives (bandes 4, 5)

Total : 5 bandes actives. Rentre dans un seul EQ8 (capacité 8 bandes). Feature 8 peut proposer une fusion :

- Option A : garder séparés (3 EQ8 correctifs : Static, Peak Resonance, CDE). C'est l'option par défaut, cohérente avec la philosophie séparation épistémique.
- Option B : fusionner en un seul EQ8 "Cleanup" avec 5 bandes (2 EQ8 correctifs totaux : Static, Cleanup). Gain de CPU et clarté visuelle mais perte de séparation épistémique.

Feature 8 **propose** les deux options avec leurs trade-offs, utilisateur tranche.

### Cas 3 — Bandes qui se chevauchent

Dans Peak Resonance bande 1 : cut -3 dB à 248 Hz Q=8.
Dans CDE Correction bande 1 : cut -2 dB à 247 Hz Q=7.

Les deux cuttent quasi la même fréquence. Feature 8 détecte le chevauchement et propose :

- Option A : garder les deux (pas de consolidation, acceptable si ça sonne bien)
- Option B : fusionner en une seule bande avec cut -4 dB à 247.5 Hz Q=7.5 (pondéré)
- Option C : garder une seule et supprimer l'autre (choix utilisateur laquelle)

Arbitrage utilisateur requis.

### Cas 4 — Dépassement irréductible

Track a :
- Static Cleanup avec 1 bande
- Peak Resonance avec 6 bandes actives
- CDE Correction avec 4 bandes actives
- Musical Enhancement avec 2 bandes actives

Total : 13 bandes sur 4 EQ8. Respecte la règle 3+1 en nombre d'EQ8, mais individuellement chaque EQ8 est sous son max. Pas de consolidation nécessaire.

Mais si :
- Peak Resonance avec 7 bandes actives
- CDE Correction avec 7 bandes actives

Total : 14 bandes. Impossible de tout caser dans un EQ8 unique (max 6 bandes utiles + 2 réservées HPF/LPF). Consolidation impossible sans perte. Feature 8 signale l'incompatibilité : "Cette track nécessite 14 bandes, consolidation impossible. Option : accepter 4 EQ8 (Static / Peak Resonance / CDE / Musical), ou réviser Peak Resonance pour garder moins de peaks (via `--max_bands=4`)."

---

## 3 — Algorithme de classification des EQ8 existants

### 3.1 Détection par UserName

Feature 8 lit le `UserName` de chaque EQ8 pour classifier :
- "Peak Resonance" ou "Peak Resonance*" → rôle Peak Resonance
- "CDE Correction*" ou commence par "CDE" → rôle CDE
- "Musical Enhancement*" → rôle Musical
- "Static Cleanup*" ou "HPF/LPF Dynamic*" → rôle Static
- Autre nom ou vide → classification par heuristique (voir 3.2)

### 3.2 Heuristique si UserName ambigu

Pour un EQ8 sans UserName évocateur, examen du contenu :

- Si majorité des bandes actives sont en Mode=0 (HPF) ou Mode=5 (LPF) → probablement Static ou dérivé
- Si bandes avec Freq + Gain + Q tous animés synchronisés → probablement Peak Resonance ou CDE
- Si bandes avec Gain animé uniquement (Freq fixe) → probablement CDE section-locked
- Si bandes avec Gain positif (boost) → probablement Musical

Si ambigu irrémédiablement : demander à l'utilisateur.

### 3.3 Détection des doublons du même rôle

Deux EQ8 classifiés dans le même rôle (ex: 2 Peak Resonance) = doublons. Le plus récent par position XML (insertion tardive = plus récent en général) est le "canonical", l'autre est "candidat à merge ou suppression".

---

## 4 — Algorithme de consolidation

### 4.1 Mode non-destructif par défaut

Feature 8 **ne supprime rien** sans validation. Elle :

1. Analyse et classifie tous les EQ8
2. Identifie les cas de consolidation possible
3. Produit un **plan de consolidation** avec options
4. Attend validation utilisateur
5. Exécute uniquement après go explicite

### 4.2 Règles de merge de bandes

**Fusion de deux bandes similaires (overlap < 1/3 semitone et même signe de gain) :**

Résultat : une bande unique avec :
- `freq` = moyenne pondérée par `|gain|`
- `gain` = somme des gains (avec cap sur la règle Qrust max_cut par rôle)
- `Q` = moyenne pondérée par `|gain|`
- Automations : **concaténation temporelle respectueuse** — pour chaque frame, prendre la valeur la plus agressive des deux ou la moyenne selon le contexte (à arbitrer)

**Si les automations sont en conflit temporel (même section, valeurs différentes) :**

Demander arbitrage utilisateur. Ne jamais fusionner silencieusement.

### 4.3 Règle de préservation des automations

**Principe absolu :** aucune automation ne doit être "perdue" par consolidation.

Si une bande A dans EQ8-1 a une automation Gain avec 200 events, et une bande B dans EQ8-2 a une automation Gain avec 150 events, la bande consolidée doit contenir une automation Gain qui **respecte les intentions** des deux.

Si les deux automations ne peuvent pas être fusionnées sans perte (chevauchements temporels incompatibles), Feature 8 refuse la consolidation et recommande de garder les bandes séparées.

### 4.4 Reordering automatique dans la device chain

Après consolidation, Feature 8 réordonne les EQ8 selon la convention Qrust :

Static Cleanup → Peak Resonance → CDE Correction → [effets non-correctifs] → Musical Enhancement → [glue final]

Note : Feature 8 ne déplace pas les effets non-correctifs (saturation, compression, etc.). Elle réordonne uniquement les EQ8 entre eux si nécessaire.

---

## 5 — API proposée

### 5.1 Fonction principale

```python
def consolidate_eq8_chain(
    als_path: Path | str,
    track_name: str,
    *,
    max_correctifs: int = 3,
    max_total_eq8: int = 4,                      # 3 correctifs + 1 musical
    preserve_separation: bool = True,             # préférer séparés si possible
    merge_overlap_tolerance_semitones: float = 0.33,
    interactive: bool = True,                     # demander arbitrage si conflits
    dry_run: bool = True,                         # default dry-run pour cette feature sensible
) -> ConsolidationReport
```

### 5.2 Report dataclass

```python
@dataclass
class ConsolidationReport:
    analysis: dict                               # classification de chaque EQ8 existant
    actions_proposed: list[ConsolidationAction]  # ce que Feature 8 propose de faire
    actions_applied: list[ConsolidationAction]   # ce qui a été réellement fait (si non dry-run)
    conflicts_needing_arbitration: list[dict]    # à résoudre avec utilisateur
    warnings: list[str]
    backup_path: Optional[Path]
```

### 5.3 Action dataclass

```python
@dataclass
class ConsolidationAction:
    action_type: str         # "merge_bands", "remove_doublet", "reorder", "rename"
    source_device_ids: list[str]
    target_device_id: Optional[str]
    source_bands: list[int]
    target_band: Optional[int]
    rationale: str
    preserves_all_automations: bool
```

---

## 6 — CLI wrapper

```bash
python scripts/consolidate_eq8_chain.py \
    --als "project.als" \
    --track "[H/M] Lead Vocal Shhh" \
    --dry-run \
    --preserve-separation \
    --merge-tolerance 0.33

# Preview affiché. Si OK :
python scripts/consolidate_eq8_chain.py \
    --als "project.als" \
    --track "[H/M] Lead Vocal Shhh" \
    --execute \
    --interactive   # arbitrage en cours si besoin
```

Mode batch pour traiter toutes les tracks d'un projet d'un coup (après Phase 2, 6, 7) :

```bash
python scripts/consolidate_eq8_chain.py \
    --als "project.als" \
    --all-tracks \
    --dry-run
```

---

## 7 — Plan de livraison

### F8a — Classification et analyse des EQ8 existants

- `_classify_eq8_by_username`
- `_classify_eq8_by_heuristic`
- `_analyze_eq8_chain(track)`
- Tests unitaires

Durée : 1.5h-2h
Tests : 8-10
Commit : `feat(consolidate): EQ8 classification and chain analysis`

### F8b — Détection des cas de consolidation

- `_detect_doublons`
- `_detect_overlapping_bands`
- `_detect_compatible_merges`
- Tests

Durée : 1.5h-2h
Tests : 8-10
Commit : `feat(consolidate): consolidation case detection`

### F8c — Merge de bandes avec préservation automations

Cœur technique de la feature, probablement le plus délicat.

- `_merge_two_bands(band_a, band_b)` — calcul freq/gain/Q mergés
- `_merge_automations(env_a, env_b)` — fusion des enveloppes avec détection de conflits
- Tests exhaustifs sur edge cases

Durée : 2h-3h
Tests : 12-15
Commit : `feat(consolidate): band merging with automation preservation`

### F8d — Planification et preview

- `_propose_consolidation_plan`
- Rendu du plan en texte pour preview
- Tests

Durée : 1h
Tests : 5-6
Commit : `feat(consolidate): plan generation and preview`

### F8e — Exécution avec arbitrage interactif

- `_execute_plan` orchestration
- `_request_arbitration` pour conflits
- Tests mock de l'interactivité

Durée : 1h-1.5h
Tests : 4-6
Commit : `feat(consolidate): plan execution with interactive arbitration`

### F8f — CLI wrapper avec batch mode

- Script principal
- Mode single-track et mode batch --all-tracks
- Tests smoke

Durée : 1h
Tests : 2-4
Commit : `feat(cli): EQ8 consolidation script`

**Total F8 :** 8h-10h, ~39-51 tests, 6 micro-commits.

**Feature la plus lourde des trois (F6, F7, F8).** À planifier en dernier pour bénéficier de tout le travail antérieur.

---

## 8 — Validation terrain

Après F8 livrée, test sur Acid Drops avec plusieurs tracks ayant accumulé des EQ8 :

1. Track avec 2× Peak Resonance (doublon classique)
2. Track avec Peak Resonance + CDE Correction ayant bandes qui se chevauchent
3. Track avec 5 EQ8 (cas extrême nécessitant consolidation)

Protocole : dry-run détaillé, analyse du plan proposé, exécution progressive, vérification que le son reste identique après consolidation (doit être bit-for-bit proche — les automations étant préservées).

---

## 9 — Risques techniques identifiés

| Risque | Mitigation |
|---|---|
| Perte d'automation pendant merge | Tests exhaustifs + dry-run default + interactive arbitration |
| Résultat audiblement différent de la somme des EQ8 originaux | Validation A/B obligatoire après consolidation |
| Arbitrage utilisateur complexe à gérer dans CLI non-interactif | Mode `--interactive` + fallback `--on-conflict skip` |
| Classification heuristique erronée | Logs verbeux + possibilité d'override via flag |
| Conflits d'automations temporels | Détection stricte + refus de merge automatique |
| XML mal formé après consolidation | Validation XML post-opération + backup safety |

---

## 10 — Hors scope F8

- Consolidation inter-track (ex: éliminer redondances entre plusieurs tracks) → hors scope
- Optimisation CPU avancée (fusion de plusieurs devices non-EQ) → scope autre feature
- Intelligence musicale pour suggérer des réorganisations (ex: "cette bande serait mieux dans Peak Resonance") → Feature 9 potentielle

---

## 11 — Dépendances validation utilisateur avant dev

**Q1 —** Le mode `interactive=True` par défaut te convient-il, ou préférer `interactive=False` avec fallback `--on-conflict=skip|fail|auto-best-effort` ?
**Q2 —** Faut-il un seuil de "confiance" pour la classification heuristique avant de demander arbitrage, ou demander dès le premier doute ?
**Q3 —** Le `dry_run=True` par défaut est-il acceptable, ou préférer `dry_run=False` avec preview obligatoire et prompt Y/N ?
**Q4 —** Priorité F8 vs autres features dans la roadmap ? (Ma recommandation : F8 en dernier, après F1.5, F6, F7.)

---

**Fin spec Feature 8. Validation utilisateur attendue avant démarrage dev.**
