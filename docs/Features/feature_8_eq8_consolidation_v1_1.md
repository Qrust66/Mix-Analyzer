# Feature 8 — EQ8 consolidation / reconciliation

**Version spec :** 1.1
**Date dernière modification :** 2026-04-23
**Statut :** Planifiée, non démarrée — Q1-Q4 en attente de validation utilisateur (voir section 13)
**Hérite de :** `documentation_discipline.md` (règles de rédaction), `qrust_professional_context.md` (philosophie 100% dynamique et règle 3 EQ8 max justifiant la feature)
**Brief méthodologique de référence :** `mix_engineer_brief_v2_3.md` (notamment règle 5.9 EQ8 max, Phase 7 consolidation)
**Feature parent dans la roadmap :** voir `roadmap_features_1_8.md`
**Dépendances technique :** Features 1, 6, 7 idéalement livrées pour avoir matière à consolider

**Historique d'évolution de la spec :**
- v1.0 — création initiale (2026-04-23 après-midi). Première rédaction post-validation philosophie 100% dynamique et règle 3 EQ8 max. Couvrait objectif, cas typiques (4), classification, algorithme de consolidation, API, CLI, plan de livraison, validation, risques, hors scope, questions Q1-Q4.
- v1.1 (ce document) — audit complétude pour Claude Code. Préservation intégrale du contenu v1.0 + 19 ajouts/clarifications signalés explicitement : header conforme à `documentation_discipline.md`, correction effort estimé incohérent (8-10h confirmé), spécification complète des règles de fusion d'automations (plus de "à arbitrer"), spec du reordering XML avec garde sidechains, clarification du mode de déclenchement (manuel + check automatique en Phase 7), seuils explicites pour heuristique de classification, gestion opérationnelle du cas 4 (dépassement irréductible), garde-fous mode batch `--all-tracks`, rétrocompatibilité avec re-runs des features amont, définition modules sources, stratégie anti-timeout détaillée (12 commits avec séparation code/tests), section "Tests d'acceptation", guidance sur format arbitrage interactif, enrichissement `ConsolidationAction` avec attributs additionnels, format de persistance du plan (YAML), spec du mode `auto-best-effort`, distinction `ConsolidationReport` vs `ConsolidationPlan`, ajout quick card.

**Principe de préservation :** cette spec préserve intégralement le contenu de v1.0. Aucune section, aucun exemple, aucune décision validée n'a été supprimée — seulement étendue ou clarifiée. Les ajouts et clarifications de v1.1 sont signalés explicitement avec annotation "(nouveau en v1.1)" ou "(clarifié en v1.1)".

**Effort estimé :** 8h-10h Claude Code, ~39-51 tests, 12 micro-commits (6 code + 6 tests, séparés pour anti-timeout). **Note v1.1 :** correction de l'incohérence v1.0 qui mentionnait "6-8 heures / 7-10 micro-commits" en header puis "8-10h / 6 micro-commits" en Section 7 — la valeur correcte est 8-10h, désormais 12 commits.

**Feature la plus complexe et délicate des trois (F6, F7, F8).** À planifier en dernier de la roadmap pour bénéficier de tout le travail antérieur et de l'expérience accumulée des autres features.

---

## 1 — Objectif et justification

### 1.1 Ce que fait la feature

Consolide intelligemment les EQ8 accumulés sur une track au fil des features correctives pour respecter la règle Qrust "maximum 3 EQ8 correctifs par track" (+1 Musical Enhancement optionnel), tout en **préservant intégralement l'intention et le comportement** de chaque traitement.

### 1.2 Pourquoi cette feature

Au fil de l'utilisation des features 1, 6, 7 et des re-runs de `write_resonance_suppression`, une track peut finir avec plus de 3 EQ8 correctifs.

**Exemple concret de scénario d'accumulation :**

Imagine la track `[H/M] Lead Vocal Shhh` après plusieurs sessions :

- Peak Resonance (v1, généré il y a 1 semaine via `write_resonance_suppression`)
- Peak Resonance (v2, re-généré hier après nouveau bounce — l'ancien n'a pas été supprimé)
- CDE Correction (v1, appliqué en Phase 2 via Feature 1)
- CDE Correction (v2, enrichi en Phase 3 après ajout de nouveaux diagnostics)
- HPF/LPF Dynamic (Feature 6, créé séparément si Q2 de F6 = nouveau EQ8)
- Musical Enhancement (Feature 7)

**6 EQ8 sur une track. Trop. Viole la règle 5.9 du brief.**

Feature 8 réconcilie :
- **Les multiples versions d'un même rôle** (2× Peak Resonance → 1 Peak Resonance fusionné)
- **Les rôles similaires qui peuvent coexister dans un même EQ8** (si CDE Correction a seulement 2 bandes et Peak Resonance en a 4, on peut tout caser dans un seul EQ8 si nécessaire)
- **Les bandes redondantes ou qui se chevauchent** (si deux bandes cuttent à des fréquences très proches, on fusionne en combinant leurs gains)
- **L'ordre incorrect des EQ8 dans la device chain** (Static doit précéder Peak Resonance qui doit précéder CDE Correction)

### 1.3 Contraintes philosophiques

Feature 8 respecte **strictement** :

- **La règle "dynamique par défaut"** — aucune automation perdue dans le process de consolidation
- **La séparation épistémique si possible** — si on peut garder 3 EQ8 distincts (Static / Peak Resonance / CDE), on préfère ça à 1 EQ8 fourre-tout
- **La préservation du travail existant** — jamais perdre une bande sans consentement explicite
- **Le principe de réversibilité** — backup complet avant, revert possible après
- **Le principe de transparence** — toute action est documentée dans le report et logguée pour audit

### 1.4 Positionnement dans la roadmap (clarifié en v1.1)

F8 est la **dernière feature** de la roadmap parce que :
- Elle traite des EQ8 produits par les autres features (F1, F1.5, F6, F7)
- Sans F1+F6+F7 livrées, F8 a peu de matière à consolider
- C'est la feature la plus délicate techniquement (manipulation d'automations existantes)
- Elle bénéficie de l'expérience accumulée sur les API d'écriture EQ8

**Néanmoins, F8 peut être déclenchée manuellement par l'utilisateur ou suggérée par le brief méthodologique en Phase 1.b** (audit) si une track présente déjà > 3 EQ8 correctifs (cas typique : utilisateur a un .als avec historique manuel d'EQ8).

### 1.5 Modes de déclenchement (nouveau en v1.1)

**Mode 1 — Manuel par l'utilisateur**

L'utilisateur lance `consolidate_eq8_chain` quand il identifie un besoin (track avec trop d'EQ8).

**Mode 2 — Suggestion automatique en Phase 1 du brief**

Lors de l'audit architectural (Phase 1.b du brief v2.3), si une track est détectée avec > 3 EQ8 correctifs, la session signale qu'un appel à F8 serait pertinent. **F8 ne se lance pas automatiquement** — c'est l'utilisateur qui décide.

**Mode 3 — Vérification post-feature (recommandé en v1.1)**

Après application de F1, F6 ou F7, le report inclut un check : "Cette track a maintenant N EQ8 correctifs. Si N > 3, considérer F8 consolidation."

### 1.6 Résultat attendu

Une fonction `consolidate_eq8_chain` qui :

1. **Analyse** tous les EQ8 d'une track
2. **Classifie** chaque EQ8 dans un des 3+1 rôles (Static / Peak Resonance / CDE / Musical)
3. **Détecte** les cas de consolidation possible (doublons, chevauchements, surnombre)
4. **Produit un plan** de consolidation détaillé
5. **Si validation utilisateur** : exécute la consolidation avec préservation des automations
6. **Si conflits irrésolus** : demande arbitrage utilisateur (ou skip selon mode)

---

## 2 — Cas de consolidation typiques

### 2.1 Cas 1 — Doublons du même rôle

**Configuration initiale :** track a 2 EQ8 "Peak Resonance" (v1 ancienne et v2 récente).

**Comportement F8 :**
- Le plus récent gagne (le "canonical")
- L'ancien est candidat à suppression
- **Si l'ancien a des bandes que le récent n'a plus** (ex: v2 a re-détecté moins de peaks parce que le mix a évolué) :
  - Demander arbitrage utilisateur : "L'ancien Peak Resonance avait une correction à 247 Hz qui a disparu de v2, veux-tu la garder ?"
  - Réponses possibles : `garder` (transfert vers v2) / `ignorer` (suppression) / `skip` (pas de consolidation)

### 2.2 Cas 2 — Rôles compatibles à faible usage

**Configuration initiale :**
- Peak Resonance avec 3 bandes actives (bandes 1, 2, 3)
- CDE Correction avec 2 bandes actives (bandes 4, 5)

**Total :** 5 bandes actives. Rentre dans un seul EQ8 (capacité 6 bandes utiles, 1-6).

**Feature 8 propose deux options :**

**Option A — Garder séparés (par défaut)**
- 3 EQ8 correctifs : Static, Peak Resonance, CDE Correction
- Cohérent avec la philosophie séparation épistémique
- Bypass indépendant possible
- Pas de risque

**Option B — Fusionner**
- 2 EQ8 correctifs : Static, "Cleanup" (combine Peak Resonance + CDE)
- Gain de CPU minime + clarté visuelle
- Perte de séparation épistémique (un EQ8 mixte)

**Décision :** Feature 8 **propose** les deux options avec leurs trade-offs, l'utilisateur tranche. Recommandation par défaut : Option A.

### 2.3 Cas 3 — Bandes qui se chevauchent

**Configuration initiale :**
- Peak Resonance bande 1 : cut -3 dB à 248 Hz Q=8
- CDE Correction bande 1 : cut -2 dB à 247 Hz Q=7

**Détection :** chevauchement < 1/3 semitone, même signe de gain → candidat fusion.

**Feature 8 propose trois options :**

**Option A — Garder les deux** (pas de consolidation, acceptable si ça sonne bien)

**Option B — Fusionner** en une seule bande :
- `freq` = moyenne pondérée par |gain| → `(248×3 + 247×2) / (3+2) = 247.6 Hz`
- `gain` = somme des gains → `-3 + -2 = -5 dB` (cappé à -3 dB par règle Qrust max_cut Hero rôle)
- `Q` = moyenne pondérée par |gain| → `(8×3 + 7×2) / (3+2) = 7.6`

**Option C — Garder une seule** et supprimer l'autre (choix utilisateur laquelle)

**Décision :** arbitrage utilisateur requis. Pas de fusion automatique sans validation.

### 2.4 Cas 4 — Dépassement irréductible (clarifié en v1.1)

**Configuration initiale :**
- Static Cleanup : 1 bande
- Peak Resonance : 6 bandes actives
- CDE Correction : 4 bandes actives
- Musical Enhancement : 2 bandes actives

**Total :** 13 bandes sur 4 EQ8.

**Analyse :** respecte la règle 3+1 en nombre d'EQ8, mais individuellement chaque EQ8 est sous son max de bandes utiles (6 max sur les bandes 1-6, en supposant 0 et 7 réservées HPF/LPF). **Pas de consolidation nécessaire.**

**Mais si la situation s'aggrave :**
- Peak Resonance avec 7 bandes actives
- CDE Correction avec 7 bandes actives

**Total :** 14 bandes. **Impossible de tout caser dans un EQ8 unique** (max 6 bandes utiles + 2 réservées HPF/LPF = 8 max par EQ8).

**Comportement F8 (clarifié en v1.1) :**

1. **Détecter le dépassement irréductible** dès l'analyse (Section 3)
2. **Émettre un warning explicite** dans le report :
   ```
   IRREDUCIBLE_OVERFLOW: Track '<name>' has 14 active bands across roles, 
   exceeds max single-EQ8 capacity (6 useful bands per EQ8).
   Options:
   1. Accept 4 separate EQ8 (current state, violates 3 EQ8 max rule)
   2. Reduce Peak Resonance bands via re-run with --max_bands=4
   3. Reduce CDE Correction bands via Feature 1 with stricter severity filter
   4. Manual intervention to remove non-critical bands
   ```
3. **Refuser l'opération automatique** — F8 ne tente pas de consolidation forcée qui casserait le résultat audio
4. **Suggérer les options à l'utilisateur** dans le `ConsolidationReport`
5. **Exit code spécifique** (code 4 : irreducible overflow)

L'utilisateur peut alors prendre une action correctrice avant de relancer F8.

---

## 3 — Algorithme de classification des EQ8 existants

### 3.1 Détection par UserName (étape 1, plus fiable)

Feature 8 lit le `UserName` de chaque EQ8 et applique le mapping suivant :

| UserName pattern | Rôle classifié |
|---|---|
| `"Peak Resonance"` ou `"Peak Resonance (* bands)"` | Peak Resonance |
| `"CDE Correction"` ou `"CDE Correction (* bands)"` | CDE Correction |
| `"Musical Enhancement"` ou `"Musical Enhancement (* bands)"` | Musical Enhancement |
| `"Static Cleanup"` ou `"HPF/LPF Dynamic"` | Static |
| Vide ou autre | À classifier par heuristique (étape 2) |

### 3.2 Heuristique si UserName ambigu (étape 2, clarifiée en v1.1)

Pour un EQ8 sans UserName évocateur, examen du contenu pour estimer le rôle.

**Seuils explicites (clarifiés en v1.1) :**

```python
# Constants pour heuristique de classification
HEURISTIC_MAJORITY_THRESHOLD = 0.6  # 60% des bandes actives doivent matcher le pattern
HEURISTIC_CONFIDENCE_THRESHOLD = 0.75  # 75% de confiance pour classification automatique
```

**Algorithme :**

```python
def _classify_eq8_by_heuristic(
    eq8_element,
    *,
    majority_threshold: float = HEURISTIC_MAJORITY_THRESHOLD,
    confidence_threshold: float = HEURISTIC_CONFIDENCE_THRESHOLD,
) -> tuple[Eq8Role, float]:
    """
    Returns (role, confidence_score).
    Si confidence < threshold, l'appelant doit demander à l'utilisateur.
    """
    active_bands = _get_active_bands(eq8_element)
    if not active_bands:
        return (Eq8Role.UNKNOWN, 0.0)
    
    n_active = len(active_bands)
    
    # Critère 1 : majorité de HPF/LPF → Static
    n_hpf_lpf = sum(1 for b in active_bands if b.mode_id in (0, 5))
    if n_hpf_lpf / n_active >= majority_threshold:
        return (Eq8Role.STATIC, 0.85)
    
    # Critère 2 : majorité de bandes avec Freq+Gain+Q tous animés → Peak Resonance ou CDE
    n_fully_animated = sum(
        1 for b in active_bands 
        if b.has_freq_automation and b.has_gain_automation and b.has_q_automation
    )
    if n_fully_animated / n_active >= majority_threshold:
        # Distinguer Peak Resonance vs CDE
        # Peak Resonance : automations longues continues (typique 200+ events sync)
        # CDE Correction : automations section-locked (variable)
        n_section_locked = sum(
            1 for b in active_bands 
            if _is_section_locked_pattern(b)
        )
        if n_section_locked / n_active >= majority_threshold:
            return (Eq8Role.CDE_CORRECTION, 0.70)
        else:
            return (Eq8Role.PEAK_RESONANCE, 0.75)
    
    # Critère 3 : majorité de Gain animé seulement (Freq fixe) → CDE section-locked
    n_gain_only = sum(
        1 for b in active_bands 
        if b.has_gain_automation and not b.has_freq_automation
    )
    if n_gain_only / n_active >= majority_threshold:
        return (Eq8Role.CDE_CORRECTION, 0.80)
    
    # Critère 4 : majorité de bandes avec Gain positif (boost) → Musical Enhancement
    n_positive_gain = sum(
        1 for b in active_bands 
        if b.gain_db > 0
    )
    if n_positive_gain / n_active >= majority_threshold:
        return (Eq8Role.MUSICAL_ENHANCEMENT, 0.75)
    
    # Aucun critère majoritaire → ambigu
    return (Eq8Role.UNKNOWN, 0.0)
```

**Si `confidence_score < HEURISTIC_CONFIDENCE_THRESHOLD` (75%) :** demander arbitrage utilisateur via prompt :
```
EQ8 device 'Id=42' on track '[H/M] Lead Vocal Shhh' has ambiguous classification.
Detected patterns:
  - 3 bands with full automation (could be Peak Resonance or CDE)
  - 2 bands with positive gain (could be Musical Enhancement)
What role does this EQ8 serve?
[1] Peak Resonance
[2] CDE Correction
[3] Musical Enhancement
[4] Static
[5] Skip (don't classify, leave as-is)
```

### 3.3 Détection des doublons du même rôle

Deux EQ8 classifiés dans le même rôle = doublons potentiels.

**Algorithme :**

```python
def _detect_role_duplicates(eq8_chain: list[ClassifiedEq8]) -> list[tuple[ClassifiedEq8, ClassifiedEq8]]:
    """Returns pairs of (canonical, duplicate) for each role with multiple EQ8s."""
    by_role = defaultdict(list)
    for eq8 in eq8_chain:
        if eq8.role != Eq8Role.UNKNOWN:
            by_role[eq8.role].append(eq8)
    
    duplicates = []
    for role, eq8s in by_role.items():
        if len(eq8s) > 1:
            # Le plus récent (position XML la plus tardive) est le canonical
            sorted_by_position = sorted(eq8s, key=lambda e: e.xml_position)
            canonical = sorted_by_position[-1]
            for older in sorted_by_position[:-1]:
                duplicates.append((canonical, older))
    
    return duplicates
```

**Note v1.1 :** la "position XML" est un proxy pour "ordre d'insertion temporel". L'EQ8 inséré le plus tard est en position XML la plus tardive. C'est une heuristique — si le user a manuellement réordonné les devices, le canonical détecté pourrait être l'ancien. Solution : afficher dans le report les deux candidats avec leur date approximative et laisser l'utilisateur choisir si non-confiance.

---

## 4 — Algorithme de consolidation

### 4.1 Mode non-destructif par défaut

Feature 8 **ne supprime rien** sans validation explicite. Workflow standard :

1. **Analyser** : classifie tous les EQ8 (Section 3)
2. **Détecter** : identifie les cas de consolidation possible (doublons, chevauchements, surnombre)
3. **Produire un `ConsolidationPlan`** : liste détaillée des actions proposées avec rationale
4. **Présenter** : afficher le plan à l'utilisateur
5. **Attendre validation** : explicit y/N par action ou globalement
6. **Exécuter** : seulement après validation, avec backup automatique
7. **Reporter** : `ConsolidationReport` avec actions effectivement appliquées

**Distinction `Plan` vs `Report` (clarifié en v1.1) :**

- **`ConsolidationPlan`** = ce que F8 propose de faire (avant exécution)
- **`ConsolidationReport`** = ce qui a été effectivement fait (après exécution)

Le Plan peut être sauvegardé en YAML pour examen ultérieur ou re-application (voir section 5.6).

### 4.2 Règles de merge de bandes (clarifié en v1.1)

**Note v1.1 :** la v1.0 disait "à arbitrer" pour la règle de fusion d'automations. Voici la spécification complète.

**Détection de bandes "similaires" (candidates à fusion) :**

```python
def _are_bands_similar(
    band_a: BandData,
    band_b: BandData,
    *,
    overlap_tolerance_semitones: float = 0.33,  # ~2% de différence en fréquence
    require_same_sign: bool = True,
) -> bool:
    # Vérifier overlap de fréquence
    semitones_diff = abs(12 * math.log2(band_a.freq / band_b.freq))
    if semitones_diff > overlap_tolerance_semitones:
        return False
    
    # Vérifier même signe de gain (cut+cut ou boost+boost, pas cut+boost)
    if require_same_sign and (band_a.gain * band_b.gain < 0):
        return False
    
    return True
```

**Calcul des paramètres de la bande fusionnée :**

```python
def _merge_two_bands(band_a: BandData, band_b: BandData) -> BandData:
    """Calcule les paramètres d'une bande issue de la fusion de deux."""
    # Pondération par |gain|
    weight_a = abs(band_a.gain) if band_a.gain != 0 else 0.5
    weight_b = abs(band_b.gain) if band_b.gain != 0 else 0.5
    total_weight = weight_a + weight_b
    
    merged_freq = (band_a.freq * weight_a + band_b.freq * weight_b) / total_weight
    merged_gain = band_a.gain + band_b.gain  # Sommation
    merged_q = (band_a.q * weight_a + band_b.q * weight_b) / total_weight
    
    # Cap du gain selon règle Qrust max_cut par rôle (à appliquer ailleurs)
    # ou par genre profile (à appliquer ailleurs)
    
    return BandData(
        freq=merged_freq,
        gain=merged_gain,
        q=merged_q,
        mode=band_a.mode,  # Assumé identique (sinon refuser merge en amont)
        is_on=True,
    )
```

**Fusion des automations (algorithme complet, nouveau en v1.1) :**

```python
def _merge_automations(
    env_a: AutomationEnvelope,
    env_b: AutomationEnvelope,
    *,
    conflict_strategy: str = "request_arbitration",  # request_arbitration | average | aggressive | refuse
) -> AutomationEnvelope:
    """
    Fusion temporelle de deux enveloppes d'automation.
    
    Stratégies disponibles :
    - request_arbitration : demande à l'utilisateur si conflit temporel détecté (DÉFAUT)
    - average : prend la moyenne aux points de conflit
    - aggressive : prend la valeur la plus extrême (max abs)
    - refuse : refuse la fusion si conflit détecté, retourne None
    """
    # Combiner les timestamps des deux enveloppes
    all_times = sorted(set(
        [pt.time for pt in env_a.points] + [pt.time for pt in env_b.points]
    ))
    
    merged_points = []
    conflicts = []
    
    for t in all_times:
        val_a = env_a.value_at(t)  # Interpolation si pas de point exact
        val_b = env_b.value_at(t)
        
        if val_a is None and val_b is not None:
            merged_points.append(AutomationPoint(t, val_b))
        elif val_b is None and val_a is not None:
            merged_points.append(AutomationPoint(t, val_a))
        elif abs(val_a - val_b) < 0.01:  # Tolérance pour valeurs égales
            merged_points.append(AutomationPoint(t, (val_a + val_b) / 2))
        else:
            # Conflit détecté
            conflicts.append((t, val_a, val_b))
            if conflict_strategy == "average":
                merged_points.append(AutomationPoint(t, (val_a + val_b) / 2))
            elif conflict_strategy == "aggressive":
                merged_points.append(AutomationPoint(
                    t, val_a if abs(val_a) > abs(val_b) else val_b
                ))
            elif conflict_strategy == "refuse":
                return None
            elif conflict_strategy == "request_arbitration":
                # Marquer pour arbitrage, ne pas résoudre maintenant
                merged_points.append(AutomationPoint(t, val_a, conflict=True))
    
    return AutomationEnvelope(points=merged_points, has_conflicts=bool(conflicts))
```

**Comportement par défaut :** `conflict_strategy="request_arbitration"`. Les conflits temporels sont remontés dans le `ConsolidationPlan` pour arbitrage utilisateur avant exécution.

### 4.3 Règle de préservation des automations

**Principe absolu :** aucune automation ne doit être "perdue" par consolidation.

Si une bande A dans EQ8-1 a une automation Gain avec 200 events, et une bande B dans EQ8-2 a une automation Gain avec 150 events, la bande consolidée doit contenir une automation Gain qui **respecte les intentions** des deux.

**Validation post-merge :**

```python
def _validate_merged_automation(
    original_envs: list[AutomationEnvelope],
    merged_env: AutomationEnvelope,
) -> tuple[bool, list[str]]:
    """Vérifie que la fusion préserve les intentions des automations originales."""
    issues = []
    
    # Check 1 : durée totale couverte
    original_duration = sum(env.duration for env in original_envs)
    merged_duration = merged_env.duration
    if merged_duration < 0.95 * original_duration:
        issues.append(f"Merged duration {merged_duration} < 95% of original {original_duration}")
    
    # Check 2 : nombre de points significatifs
    original_significant = sum(env.count_significant_points() for env in original_envs)
    merged_significant = merged_env.count_significant_points()
    if merged_significant < 0.5 * original_significant:
        issues.append(f"Significant points reduced from {original_significant} to {merged_significant}")
    
    # Check 3 : conflits non résolus
    if merged_env.has_conflicts:
        issues.append(f"Merged envelope has {len(merged_env.conflicts)} unresolved temporal conflicts")
    
    return (len(issues) == 0, issues)
```

**Si validation échoue :** Feature 8 refuse la consolidation et recommande de garder les bandes séparées.

### 4.4 Reordering automatique dans la device chain (clarifié en v1.1)

Après consolidation, Feature 8 réordonne les EQ8 selon la convention Qrust :

```
Static Cleanup → Peak Resonance → CDE Correction → [effets non-correctifs] → Musical Enhancement → [glue final]
```

**Mécanisme XML pour déplacer un device dans Ableton (nouveau en v1.1) :**

Dans le XML d'un .als, les devices d'une track sont dans `Track/DeviceChain/DeviceChain/Devices/` comme enfants. L'ordre des éléments enfants détermine l'ordre dans la chain.

**Pour déplacer un device :**
1. Lire l'élément du device à déplacer
2. Le retirer de sa position actuelle
3. L'insérer à la nouvelle position

**Code Python (lxml) :**
```python
def _reorder_eq8_in_chain(devices_element, device_to_move, target_index):
    """Déplace un device à un index spécifique dans la device chain."""
    devices_element.remove(device_to_move)
    devices_element.insert(target_index, device_to_move)
```

**Garde sidechain (nouveau en v1.1) :**

**Risque :** si un autre device de la track ou d'une autre track utilise un sidechain qui référence l'EQ8 déplacé via son ID interne, le déplacement peut casser cette référence si Ableton garde des références par position plutôt que par ID.

**Mitigation :**
1. Avant reordering, scanner tout le .als pour détecter les références sidechain à l'EQ8 cible
2. Si références détectées : émettre warning et demander confirmation
3. Si aucune référence : procéder au reordering

```python
def _check_sidechain_references_to_device(als_tree, device_id: str) -> list[str]:
    """Returns list of sidechain references pointing to this device."""
    references = []
    # Chercher tous les SideChain elements ayant Track="<device_track>" 
    # et potentiellement device-specific routing
    for sc_elem in als_tree.findall(".//SideChain"):
        # Logique de matching à confirmer contre format Ableton réel
        if _references_device(sc_elem, device_id):
            references.append(_describe_reference(sc_elem))
    return references
```

**Note :** la spec exacte de ce check dépend du format XML Ableton. À valider lors du dev.

**Feature 8 ne déplace pas les effets non-correctifs** (saturation, compression, sidechain devices). Elle réordonne uniquement les EQ8 entre eux si nécessaire.

### 4.5 Cap par rôle Qrust

Lors de la fusion (Section 4.2), si le `merged_gain` dépasse le cap autorisé par le rôle Qrust ou par le genre profile, capper :

```python
def _apply_role_cap(merged_band: BandData, role: Eq8Role, genre_profile_cap: float) -> tuple[BandData, list[str]]:
    """Applique les caps de gain selon le rôle et le profile."""
    warnings = []
    
    # Cap par rôle (RULE_ROLE_APPROPRIATE_MAX_CUT)
    role_caps = {
        Eq8Role.HERO: -3.0,
        Eq8Role.SUPPORT: -6.0,
        Eq8Role.AMBIENT: -12.0,
    }
    role_cap = role_caps.get(role, -3.0)  # Default conservateur
    
    # Cap par genre profile (plus strict typiquement)
    final_cap = max(role_cap, genre_profile_cap)  # max car valeurs négatives (cuts)
    
    if merged_band.gain < final_cap:
        warnings.append(
            f"Merged gain {merged_band.gain}dB capped to {final_cap}dB "
            f"(role={role}, profile cap={genre_profile_cap}dB)"
        )
        merged_band = replace(merged_band, gain=final_cap)
    
    return merged_band, warnings
```

---

## 5 — API proposée

### 5.1 Modules sources (nouveau en v1.1)

**Nouveau module :** `mix_analyzer/eq8_consolidation.py`

Justification : feature suffisamment complexe et distincte pour mériter son propre module. Évite la pollution des modules existants.

**Modules existants utilisés (imports) :**
- `mix_analyzer.als_utils` — helpers XML, lecture devices
- `mix_analyzer.eq8_automation` — helpers d'écriture EQ8 et lecture automations
- `mix_analyzer.cde_apply` — patterns réutilisables (find_or_create EQ8, etc.)

**Sub-modules suggérés :**
- `mix_analyzer/eq8_consolidation_classifier.py` — logique de classification
- `mix_analyzer/eq8_consolidation_merger.py` — logique de merge bandes et automations
- `mix_analyzer/eq8_consolidation_planner.py` — génération du plan
- `mix_analyzer/eq8_consolidation.py` — fonction publique orchestratrice

### 5.2 Fonction principale

```python
from pathlib import Path
from typing import Optional, Literal

def consolidate_eq8_chain(
    als_path: Path | str,
    track_name: str,
    *,
    max_correctifs: int = 3,
    max_total_eq8: int = 4,                       # 3 correctifs + 1 musical
    preserve_separation: bool = True,              # Préférer séparés si possible
    merge_overlap_tolerance_semitones: float = 0.33,
    interactive: bool = True,                      # Demander arbitrage si conflits
    on_conflict: Literal["request", "skip", "fail", "auto-best-effort"] = "request",
    dry_run: bool = True,                          # DÉFAUT : dry-run pour cette feature sensible
    plan_output_path: Optional[Path] = None,       # Sauvegarder le plan en YAML
) -> "ConsolidationReport":
    """
    Analyse et consolide les EQ8 d'une track.
    
    Args:
        als_path: Chemin vers le .als (sera modifié sauf si dry_run=True)
        track_name: Nom Ableton de la track
        max_correctifs: Maximum d'EQ8 correctifs autorisés (default: 3)
        max_total_eq8: Maximum total d'EQ8 (correctifs + musical) (default: 4)
        preserve_separation: Si True, préfère garder les EQ8 séparés quand possible
        merge_overlap_tolerance_semitones: Seuil pour détection bandes similaires
        interactive: Si True, demande arbitrage interactif sur conflits
        on_conflict: Stratégie pour conflits non résolus
        dry_run: Si True, calcule le plan sans appliquer (DÉFAUT)
        plan_output_path: Si fourni, sauvegarde le plan en YAML pour examen ultérieur
    
    Returns:
        ConsolidationReport avec analyse, plan, et actions appliquées
    """
```

### 5.3 ConsolidationReport vs ConsolidationPlan (clarifié en v1.1)

**`ConsolidationPlan`** — ce que F8 propose AVANT exécution :

```python
@dataclass
class ConsolidationPlan:
    """Plan de consolidation à exécuter ou examiner."""
    track_name: str
    analysis: dict                                 # Classification de chaque EQ8 existant
    actions_proposed: list["ConsolidationAction"]  # Actions à exécuter
    conflicts_needing_arbitration: list[dict]      # À résoudre avec utilisateur
    warnings: list[str]
    estimated_risk: Literal["low", "medium", "high"]
    is_irreducible_overflow: bool                  # True si cas 4 (Section 2.4)
    
    def save_to_yaml(self, path: Path) -> None:
        """Sauvegarde le plan en YAML pour examen ou re-application."""
        ...
    
    @classmethod
    def load_from_yaml(cls, path: Path) -> "ConsolidationPlan":
        """Charge un plan depuis YAML."""
        ...
```

**`ConsolidationReport`** — ce qui a été fait APRÈS exécution :

```python
@dataclass
class ConsolidationReport:
    """Rapport d'exécution de la consolidation."""
    track_name: str
    plan: ConsolidationPlan                        # Le plan d'origine
    actions_applied: list["ConsolidationAction"]   # Actions effectivement appliquées
    actions_skipped: list[tuple["ConsolidationAction", str]]  # Actions skipped + raison
    automations_preserved: bool                    # True si toutes les automations OK
    
    eq8_count_before: int
    eq8_count_after: int
    bands_count_before: int
    bands_count_after: int
    
    backup_path: Optional[Path]
    warnings: list[str]
    decisions_log: list[str]
    dry_run: bool
```

### 5.4 ConsolidationAction enrichie (clarifié en v1.1)

```python
@dataclass
class ConsolidationAction:
    """Une action atomique du plan de consolidation."""
    
    # Type d'action
    action_type: Literal[
        "merge_bands",          # Fusionner deux bandes en une
        "remove_doublet",       # Supprimer un EQ8 doublon
        "transfer_band",        # Déplacer une bande d'un EQ8 vers un autre
        "reorder_chain",        # Réordonner les EQ8 dans la chain
        "rename_eq8",           # Renommer un EQ8 (cohérence convention)
        "fuse_eq8s",            # Fusionner deux EQ8s (option B Cas 2)
    ]
    
    # Sources et cibles
    source_device_ids: list[str]
    target_device_id: Optional[str]
    source_bands: list[int]
    target_band: Optional[int]
    
    # Métadonnées (nouveau en v1.1)
    rationale: str                                  # Explication humaine
    priority: Literal["high", "medium", "low"]      # Priorité d'exécution
    risk_level: Literal["low", "medium", "high"]    # Risque d'effet audible
    is_reversible: bool                             # True si action revertible facilement
    requires_user_arbitration: bool                 # True si demande validation user
    
    # Préservation
    preserves_all_automations: bool
    automation_count_before: int                    # Nombre d'events avant
    automation_count_after: int                     # Nombre d'events après
    
    # Avertissements spécifiques à cette action
    warnings: list[str] = field(default_factory=list)
```

### 5.5 Exceptions custom (nouveau en v1.1)

```python
class ConsolidationError(Exception):
    """Base exception pour Feature 8."""

class IrreducibleOverflowError(ConsolidationError):
    """Cas 4 : impossible de consolider (trop de bandes)."""

class AutomationLossError(ConsolidationError):
    """Une fusion entraînerait perte d'automation, refusée."""

class ClassificationAmbiguousError(ConsolidationError):
    """Heuristique incapable de classifier un EQ8 (et mode non-interactif)."""

class SidechainReferenceError(ConsolidationError):
    """Reordering bloqué par références sidechain non résolvables."""
```

### 5.6 Persistance du plan en YAML (nouveau en v1.1)

**Format proposé :**

```yaml
# consolidation_plan_<timestamp>.yaml
version: "1.0"
track_name: "[H/M] Lead Vocal Shhh"
generated_at: "2026-04-23T22:45:00"
estimated_risk: "medium"
is_irreducible_overflow: false

analysis:
  eq8_count: 5
  bands_count: 12
  classified:
    - device_id: "42"
      role: "Peak Resonance"
      confidence: 1.0
      band_count: 4
    - device_id: "67"
      role: "Peak Resonance"
      confidence: 1.0
      band_count: 3
    # ...

actions:
  - action_type: "remove_doublet"
    source_device_ids: ["67"]  # Ancien Peak Resonance
    target_device_id: "42"     # Canonical Peak Resonance
    rationale: "Duplicate Peak Resonance EQ8 detected. Older one (Id=67) candidate for removal."
    priority: "high"
    risk_level: "low"
    is_reversible: true
    requires_user_arbitration: true
    preserves_all_automations: true
    warnings:
      - "Old Peak Resonance has band at 247Hz not present in canonical. Confirm transfer or discard."
  
  - action_type: "reorder_chain"
    source_device_ids: ["89"]  # Musical Enhancement
    target_device_id: null
    rationale: "Musical Enhancement should be after compression in chain order."
    priority: "low"
    risk_level: "low"
    is_reversible: true
    # ...

warnings:
  - "Track has 5 EQ8 (max 4 recommended). After consolidation: 3."
```

**Use cases :**
- Sauvegarder un plan pour examen offline
- Partager le plan avec l'utilisateur via fichier
- Re-appliquer le plan plus tard sans recalculer
- Audit trail (qui a décidé quoi)

---

## 6 — CLI wrapper

### 6.1 Mode preview (recommandé en premier usage)

```bash
python scripts/consolidate_eq8_chain.py \
    --als "Acid_Drops_Sections_STD.als" \
    --track "[H/M] Lead Vocal Shhh" \
    --dry-run \
    --preserve-separation \
    --merge-tolerance 0.33 \
    --plan-output "plan.yaml"
```

Affiche le plan dans stdout + sauvegarde en YAML pour examen.

### 6.2 Mode exécution avec arbitrage interactif

```bash
python scripts/consolidate_eq8_chain.py \
    --als "Acid_Drops_Sections_STD.als" \
    --track "[H/M] Lead Vocal Shhh" \
    --execute \
    --interactive
```

Pour chaque conflit, l'utilisateur est prompté :
```
Conflict: Bands at 247Hz and 248Hz on same track, both with cuts.
Options:
  [1] Keep both (no merge)
  [2] Merge into one band at 247.5Hz
  [3] Keep only band 247Hz, remove 248Hz
  [4] Keep only band 248Hz, remove 247Hz
  [5] Skip this action
Choice (1-5):
```

### 6.3 Mode exécution non-interactif avec stratégie

```bash
python scripts/consolidate_eq8_chain.py \
    --als "Acid_Drops_Sections_STD.als" \
    --track "[H/M] Lead Vocal Shhh" \
    --execute \
    --on-conflict skip      # ou: fail | auto-best-effort
```

**Modes `on_conflict` (clarifiés en v1.1) :**

- **`request`** (défaut, équivalent `--interactive`) : demander à l'utilisateur
- **`skip`** : skipper l'action en conflit, continuer les autres actions sans conflit
- **`fail`** : arrêter immédiatement avec exit code d'erreur
- **`auto-best-effort`** (nouveau, à valider Q1) : appliquer les actions sans conflit, et pour les conflits, choisir l'option la plus conservatrice (typiquement "garder les bandes séparées" plutôt que merger)

### 6.4 Mode batch `--all-tracks` avec garde-fous (renforcé en v1.1)

```bash
python scripts/consolidate_eq8_chain.py \
    --als "Acid_Drops_Sections_STD.als" \
    --all-tracks \
    --dry-run
```

**Garde-fous du mode batch (nouveau en v1.1) :**

```
⚠️  MODE BATCH ACTIVÉ
   This will analyze 35 tracks and may propose modifications on multiple of them.
   Recommendation: process tracks one by one for validation in mix.
   
   Detected: 3 tracks with > 3 EQ8 correctifs
   Tracks affected by potential consolidation:
     - [H/M] Lead Vocal Shhh (5 EQ8)
     - [H/R] Kick 1 (4 EQ8)
     - [S/H] Sub Bass (4 EQ8)
   
   Continue with batch analysis? [y/N]
```

**Mode batch n'exécute jamais directement** : il produit un plan global qui peut être examiné, et l'application doit être lancée séparément, track par track de préférence.

### 6.5 Mode load plan

```bash
python scripts/consolidate_eq8_chain.py \
    --als "Acid_Drops_Sections_STD.als" \
    --load-plan "plan.yaml" \
    --execute \
    --interactive
```

Charge un plan préalablement sauvegardé et l'exécute.

### 6.6 Mode revert

```bash
python scripts/consolidate_eq8_chain.py \
    --als "Acid_Drops_F8.als" \
    --revert
```

Restaure le backup créé avant la consolidation.

### 6.7 Exit codes

- `0` : succès
- `1` : erreur input (track absente, fichier invalide)
- `2` : erreur écriture .als
- `3` : utilisateur a refusé / annulé
- `4` : irreducible overflow (Cas 4)
- `5` : automation loss détectée, opération refusée
- `6` : sidechain reference bloquante

---

## 7 — Plan de livraison

**Stratégie anti-timeout (clarifié en v1.1) :** 12 commits (6 code + 6 tests) avec séparation stricte. Feature la plus complexe — plus de tests que les autres pour couvrir les edge cases de fusion d'automations.

### F8a — Classification et analyse des EQ8 existants

**Fichiers créés :**
- `mix_analyzer/eq8_consolidation.py` (skeleton avec dataclasses, exceptions, enums)
- `mix_analyzer/eq8_consolidation_classifier.py` (logique de classification)

**Fonctions implémentées :**
- Enums `Eq8Role` (STATIC, PEAK_RESONANCE, CDE_CORRECTION, MUSICAL_ENHANCEMENT, UNKNOWN)
- `ClassifiedEq8` dataclass
- `ConsolidationPlan`, `ConsolidationReport`, `ConsolidationAction` dataclasses
- Exceptions custom
- `_classify_eq8_by_username`
- `_classify_eq8_by_heuristic` (avec seuils explicites)
- `_analyze_eq8_chain(track)` orchestration

**Durée :** 1.5h-2h
**Tests :** 8-10 (commit séparé)
**Commits :**
- `feat(F8): EQ8 classification and chain analysis`
- `test(F8): unit tests for classification`

### F8b — Détection des cas de consolidation

**Fichiers créés :** `mix_analyzer/eq8_consolidation_planner.py`

**Fonctions implémentées :**
- `_detect_role_duplicates`
- `_detect_overlapping_bands` (utilise `_are_bands_similar`)
- `_detect_compatible_merges`
- `_detect_overflow` (détecte cas 4 irréductible)
- `_propose_consolidation_plan` (orchestration)

**Durée :** 1.5h-2h
**Tests :** 8-10
**Commits :**
- `feat(F8): consolidation case detection and plan generation`
- `test(F8): unit tests for case detection`

### F8c — Merge de bandes avec préservation automations

**Cœur technique de la feature, le plus délicat.**

**Fichiers créés :** `mix_analyzer/eq8_consolidation_merger.py`

**Fonctions implémentées :**
- `_are_bands_similar`
- `_merge_two_bands` (calcul freq/gain/Q mergés)
- `_merge_automations` (avec stratégies de conflit)
- `_apply_role_cap` (caps Qrust + genre profile)
- `_validate_merged_automation` (validation post-merge)

**Durée :** 2h-3h
**Tests :** 12-15 (couvrant tous les edge cases : overlap exact, signe différent, conflit temporel, cap, etc.)
**Commits :**
- `feat(F8): band merging with automation preservation`
- `test(F8): exhaustive unit tests for band merging`

### F8d — Reordering avec garde sidechains

**Fichiers modifiés :** `mix_analyzer/eq8_consolidation.py`

**Fonctions implémentées :**
- `_reorder_eq8_in_chain`
- `_check_sidechain_references_to_device`
- `_compute_target_chain_order` (selon convention Qrust)

**Durée :** 1h
**Tests :** 4-6
**Commits :**
- `feat(F8): chain reordering with sidechain protection`
- `test(F8): unit tests for reordering and sidechain checks`

### F8e — Exécution avec arbitrage interactif et persistance plan

**Fichiers modifiés :** `mix_analyzer/eq8_consolidation.py`

**Fonctions implémentées :**
- `_execute_plan` orchestration
- `_request_arbitration` interactive prompt
- `ConsolidationPlan.save_to_yaml`
- `ConsolidationPlan.load_from_yaml`
- Backup automatique avant exécution
- Mode `on_conflict` (request, skip, fail, auto-best-effort)

**Durée :** 1.5h-2h
**Tests :** 5-6
**Commits :**
- `feat(F8): plan execution with interactive arbitration and persistence`
- `test(F8): integration tests for execution`

### F8f — CLI wrapper

**Fichiers créés :** `scripts/consolidate_eq8_chain.py`

**Fonctions implémentées :**
- Parsing flags
- Mode dry-run
- Mode execute interactif
- Mode execute non-interactif avec on_conflict
- Mode `--all-tracks` avec garde-fous
- Mode `--load-plan`
- Mode `--revert`
- Affichage du plan/report

**Durée :** 1h-1.5h
**Tests :** 2-4 (smoke tests CLI)
**Commits :**
- `feat(F8-cli): EQ8 consolidation script with all modes`
- `test(F8-cli): smoke tests for CLI`

### Total

**Effort total F8 :** 8h-10h, ~39-51 tests, **12 commits** (6 code + 6 tests).

---

## 8 — Tests d'acceptation (nouveau en v1.1)

### 8.1 Tests unitaires
- ✅ Tous les tests unitaires passent (cible ~40)
- ✅ Coverage > 90% sur `eq8_consolidation*.py` (feature critique)

### 8.2 Tests d'intégration
- ✅ Test fixture : .als avec doublons Peak Resonance, F8 détecte et propose suppression
- ✅ Test fixture : .als avec bandes chevauchantes, F8 détecte et propose merge
- ✅ Test fixture : .als avec 5 EQ8, F8 propose plan respectant règle 3+1
- ✅ Test fixture : .als avec irreducible overflow (14 bandes), F8 refuse et signale
- ✅ Test rétrocompatibilité : .als consolidé reste compatible avec re-runs F1/F6/F7
- ✅ Test préservation automations : aucune perte d'event automation après consolidation

### 8.3 Tests CLI
- ✅ Mode dry-run produit un plan sans modifier le .als
- ✅ Mode execute interactif demande arbitrage sur conflits
- ✅ Mode `on_conflict=skip` skip les actions en conflit, continue les autres
- ✅ Mode `on_conflict=fail` arrête à la première conflit
- ✅ Mode `on_conflict=auto-best-effort` applique stratégie conservatrice
- ✅ Mode `--all-tracks` demande confirmation avant procéder
- ✅ Mode `--load-plan` charge et applique un plan YAML
- ✅ Mode `--revert` restaure le backup

### 8.4 Validation terrain (post-livraison code)
- ✅ Application sur 1 track Acid Drops avec doublon Peak Resonance
- ✅ Vérification visuelle dans Ableton (1 EQ8 Peak Resonance restant, automations OK)
- ✅ Bounce avant/après identique (bit-for-bit ou très proche)
- ✅ Validation auditive par Alexandre

### 8.5 Documentation
- ✅ Cette spec mise à jour si l'implémentation diverge
- ✅ `roadmap_features_1_8.md` mis à jour (F8 livrée)
- ✅ `CHANGELOG.md` du repo Mix-Analyzer enrichi
- ✅ Exemple `consolidation_plan_example.yaml` ajouté dans `docs/examples/`

---

## 9 — Rétrocompatibilité (nouveau en v1.1)

### 9.1 Re-runs des features amont après consolidation

**Cas problématique :** F1 a été appliquée, puis F8 a consolidé l'EQ8 CDE Correction avec Peak Resonance. L'utilisateur veut re-lancer F1 plus tard avec de nouveaux diagnostics.

**Comportement attendu :**

F1 doit pouvoir détecter qu'un EQ8 CDE Correction n'existe plus en tant que tel (consolidé) et :
- Soit créer un nouveau EQ8 CDE Correction (revient à l'état pré-F8)
- Soit ajouter ses bandes au EQ8 consolidé (préserver le travail F8)

**Décision (v1.1) :** F8 marque le EQ8 consolidé avec un attribute UserName indiquant son origine (ex: `"Cleanup (Peak Resonance + CDE)"`). F1 détecte ce marqueur et **propose à l'utilisateur** comment procéder.

**Mécanisme suggéré :** Feature 8 ajoute un comment XML dans le device consolidé pour traçabilité, et un attribute custom (si Ableton le permet) pour marquer "consolidated_from".

### 9.2 Mises à jour Mix Analyzer après consolidation

**Cas :** rapport Mix Analyzer généré après application F8 doit refléter correctement l'état consolidé.

**Vérification :** Mix Analyzer compte les EQ8 par track. Après F8, le compte doit baisser. Aucune action particulière requise sur Mix Analyzer si la classification par UserName fonctionne.

### 9.3 Réversibilité

**Backup :** F8 crée un backup `.als.F8.bak` avant chaque exécution. Mode `--revert` restaure ce backup.

**Limitation :** si plusieurs F8 sont appliquées en série sans revert intermédiaire, seul le backup le plus récent est conservé. Pour multiple revert, l'utilisateur doit gérer ses backups manuellement.

---

## 10 — Risques techniques identifiés

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Perte d'automation pendant merge | Moyenne | Audible | Tests exhaustifs + dry-run par défaut + interactive arbitration + validation post-merge |
| Résultat audiblement différent de la somme des EQ8 originaux | Élevée | Audible | Validation A/B obligatoire après consolidation, test bit-for-bit en CI |
| Arbitrage utilisateur complexe à gérer dans CLI non-interactif | Moyenne | UX | Mode `--interactive` + fallback `--on-conflict` avec stratégies claires |
| Classification heuristique erronée | Moyenne | Logique | Logs verbeux + possibilité d'override via flag + seuil de confiance 75% |
| Conflits d'automations temporels | Élevée | Bloquant | Détection stricte + refus de merge automatique sans arbitrage |
| XML mal formé après consolidation | Faible | Bloquant | Validation XML post-opération + backup safety + revert facile |
| Sidechain références cassées par reordering | Moyenne | Bloquant | Check préalable et warning + skip reorder si références détectées |
| Re-run F1/F6/F7 sur un .als consolidé | Faible | Confusion | Marquage explicite des EQ8 consolidés + détection en amont |
| Mode batch `--all-tracks` modifie trop | Élevée | Bloquant | Garde-fou strict + jamais d'exécution directe en batch |
| Heuristique misclassifie un EQ8 manuel custom de l'utilisateur | Moyenne | Mauvaise consolidation | Confidence threshold 75% + arbitrage user en cas de doute |

---

## 11 — Hors scope F8 v1

**Reportés à F8 v2 ou autres features :**

- **Consolidation inter-track** (ex: éliminer redondances entre plusieurs tracks) → hors scope, complexité × 35
- **Optimisation CPU avancée** (fusion de plusieurs devices non-EQ) → scope autre feature future
- **Intelligence musicale** pour suggérer des réorganisations (ex: "cette bande serait mieux dans Peak Resonance") → Feature 9 potentielle
- **Auto-detection du moment optimal pour lancer F8** → manuel pour l'instant
- **Visualisation graphique du plan** → outil externe, hors scope

---

## 12 — Dépendances validation utilisateur avant dev

### Q1 — Mode interactive=True par défaut ou non ?

**Question :** F8 demande arbitrage interactif par défaut, ou mode non-interactif avec stratégie automatique ?

**Trade-offs :**
- **interactive=True (défaut) :** sécurité maximale, l'utilisateur valide chaque conflit, mais session plus longue
- **interactive=False avec on_conflict=skip :** rapide, mais skip silencieux peut frustrer
- **interactive=False avec on_conflict=auto-best-effort :** rapide, applique stratégie conservatrice par défaut

**Recommandation :** `interactive=True` par défaut pour cette feature sensible. L'utilisateur peut switcher en `--on-conflict skip|auto-best-effort` selon son besoin.

**Réponse Alexandre :** _____ (à remplir)

### Q2 — Seuil de confiance pour classification heuristique

**Question :** seuil de 75% confidence pour demander arbitrage est-il approprié ?

**Trade-offs :**
- **75% (proposition) :** demande arbitrage modérément, équilibre vitesse/sécurité
- **90% :** très peu d'arbitrages mais risque de mauvaise classification
- **50% :** beaucoup d'arbitrages, plus sûr mais plus lent

**Recommandation :** 75% par défaut, configurable via flag.

**Réponse Alexandre :** _____ (à remplir)

### Q3 — dry_run=True par défaut

**Question :** F8 démarre en dry-run par défaut (l'utilisateur doit explicitement passer `--execute`) ?

**Trade-offs :**
- **dry_run=True (défaut) :** sécurité maximale, jamais de modification accidentelle
- **dry_run=False avec preview obligatoire :** un peu plus rapide pour usage répété
- **dry_run=False avec confirm Y/N :** balance entre sécurité et vitesse

**Recommandation :** `dry_run=True` par défaut pour cette feature sensible. Cohérent avec l'approche conservatrice.

**Réponse Alexandre :** _____ (à remplir)

### Q4 — Priorité dans la roadmap

**Question :** F8 doit-elle être développée après toutes les autres features ?

**Roadmap suggérée actuelle (`roadmap_features_1_8.md`) :**
1. F1.5 (sidechain)
2. F6 (HPF/LPF dynamique)
3. F7 (enhancement)
4. **F8 (consolidation)** — en dernier

**Recommandation :** F8 en dernier comme dans la roadmap. Elle bénéficie de l'expérience accumulée et de la matière à consolider produite par les autres features.

**Réponse Alexandre :** _____ (à remplir)

---

## 13 — Procédure d'évolution de cette spec

Suivre `documentation_discipline.md` section 4. Triggers d'évolution :
- Réponses Q1-Q4 reçues → enrichir spec
- Découverte technique pendant dev → mise à jour algorithme
- Validation terrain → ajustement
- Cas non couvert identifié → extension scope

---

## 14 — Référence rapide (quick card, nouveau en v1.1)

**Statut :** Spec en attente de validation utilisateur (Q1-Q4)

**Effort estimé total :** 8h-10h, ~39-51 tests, 12 commits

**Modules à créer :**
- `mix_analyzer/eq8_consolidation.py` (fonction publique + dataclasses + exceptions)
- `mix_analyzer/eq8_consolidation_classifier.py` (classification)
- `mix_analyzer/eq8_consolidation_planner.py` (détection + plan)
- `mix_analyzer/eq8_consolidation_merger.py` (merge bandes + automations)
- `scripts/consolidate_eq8_chain.py` (CLI)

**Inputs requis :**
- `.als` source
- `track_name` (ou `--all-tracks` avec garde-fou)

**Output :**
- `ConsolidationPlan` (avant exécution)
- `ConsolidationReport` (après exécution)
- `.als` modifié (avec EQ8 consolidés et réordonnés selon convention Qrust)
- Optionnel : plan sauvegardé en YAML

**Stratégies disponibles :**
- `on_conflict=request` (défaut) — arbitrage utilisateur
- `on_conflict=skip` — skip actions en conflit
- `on_conflict=fail` — arrêt à la première conflit
- `on_conflict=auto-best-effort` — stratégie conservatrice automatique

**Convention Qrust appliquée :**
- Max 3 EQ8 correctifs + 1 Musical Enhancement par track
- Ordre : Static → Peak Resonance → CDE Correction → [non-correctifs] → Musical Enhancement → glue

**Cas couverts :**
1. Doublons du même rôle (suppression du moins récent)
2. Rôles compatibles à faible usage (proposition fusion ou séparation)
3. Bandes chevauchantes (proposition merge ou suppression)
4. Dépassement irréductible (refus + suggestions)

**Garanties :**
- Aucune automation perdue (validation post-merge)
- Backup automatique avant exécution
- Revert facile via `--revert`
- Sidechain références préservées (check préalable)

**Dépendances roadmap :**
- F1, F6, F7 idéalement livrées avant F8
- F8 = dernière feature de la roadmap

**Documents associés :**
- `qrust_professional_context.md` section 4.2 (règle 3 EQ8 max)
- `mix_engineer_brief_v2_3.md` section 5.9, Phase 7
- `roadmap_features_1_8.md`
- `documentation_discipline.md`

---

**Fin spec Feature 8 v1.1. Validation utilisateur attendue sur Q1-Q4 avant démarrage dev. Une fois Q1-Q4 résolues, incrémenter en v1.2 avec les décisions intégrées et démarrer le développement selon le plan de livraison de la section 7.**
