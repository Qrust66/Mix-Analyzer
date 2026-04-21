# Feature 3.5 — Track Function Profile (TFP)

## Contexte et vision

Mix Analyzer accumule des mesures objectives sur les tracks et les sections. Mais au moment de **diagnostiquer** ou **qualifier un conflit**, il manque le **rôle musical** de chaque track dans chaque section.

Sans cette qualification, un conflit Kick vs Sub-Bass dans un drop est traité comme n'importe quel autre conflit, alors que musicalement c'est très différent d'un conflit entre deux atmosphères en arrière-plan.

L'utilisateur a classifié manuellement ses 35 tracks sur son projet Acid Drops avec un code `[Importance/Fonction]` dans les noms Ableton. Feature 3.5 = Mix Analyzer lit ces codes et enrichit le rapport avec les rôles.

Cette feature est la fondation de Feature 3.6 (Correction Diagnostic Engine) qui suivra.

## Taxonomie TFP

**Dimension 1 — Importance (rôle dans le mix)**

| Code | Nom | Description |
|---|---|---|
| `H` | Hero | Élément central, porte la section |
| `S` | Support | Renforce les hero, structure |
| `A` | Atmos | Ambiance, texture, non-essentiel |

**Dimension 2 — Fonction (rôle musical)**

| Code | Nom | Description |
|---|---|---|
| `R` | Rhythm | Porte la pulsation, le groove |
| `H` | Harmonic | Porte l'harmonie, les accords |
| `M` | Melodic | Porte une mélodie identifiable |
| `T` | Textural | Apporte une texture, une atmosphère |

**Format dans les noms de tracks :** `[Importance/Fonction] Nom de la track`

Exemples réels du projet Acid Drops :
- `[H/R] Kick 1` — Hero rhythmique
- `[H/M] Acid Bass` — Hero mélodique
- `[S/H] Sub Bass` — Support harmonique
- `[A/T] Ambience` — Atmos textural

## Distribution observée (Acid Drops, 35 tracks classifiées)

Pour contexte de validation :
- Importance : 13 Hero (37%) · 20 Support (57%) · 2 Atmos (6%)
- Fonction : 13 Rhythm (37%) · 2 Harmonic (6%) · 10 Melodic (29%) · 10 Textural (29%)
- Combo le plus fréquent : `[S/R]` (9 tracks) — Support rythmique

---

## Règles de lecture

### R1 — Parsing du préfixe TFP dans les noms

**Format attendu strict :** `^\[([HSAhsa])/([RHMTrhmt])\]\s+(.+)$`

- Crochets obligatoires
- Slash séparateur obligatoire
- **Espace obligatoire** entre `]` et le nom
- Insensible à la casse (mais normaliser en MAJUSCULES en interne)

**Cas limites tranchés :**

| Input | Output | Commentaire |
|---|---|---|
| `[H/R] Kick 1` | `(H, R, "Kick 1")` | Format standard |
| `[h/r] kick 1` | `(H, R, "kick 1")` | Casse ignorée, nom préservé |
| `[H/R]Kick 1` | `None` | Espace manquant → pas de match |
| `[X/Y] Kick 1` | `None` + warning | Codes invalides |
| `[H] Kick 1` | `None` + warning | Format incomplet |
| `Kick 1` | `None` | Pas de préfixe — déclenche défaut |
| `[H/R] [draft] Kick 1` | `(H, R, "[draft] Kick 1")` | Second crochet fait partie du nom |
| `  [H/R] Kick 1` | Trim puis parse | Whitespace leading OK |

### R2 — Défaut pour tracks sans préfixe

Track sans préfixe TFP → classifiée `[S/R]` (Support Rhythm) par défaut.

**Comportement :**
- Le rapport fonctionne normalement
- Un **warning** est loggé et affiché dans le rapport (section "Warnings" ou similaire si elle existe, sinon nouvelle section en tête de Sections Timeline) listant toutes les tracks sans préfixe
- Le warning mentionne : nom exact des tracks, nombre total

### R3 — Parsing des overrides dans les annotations de Locators

Format strict : `override: NomTrack1=X-Y, NomTrack2=X, NomTrack3=*-Y`

**Règles de matching des noms :**
- Nom **sans préfixe** (`Kick 1`, pas `[H/R] Kick 1`)
- **Insensible à la casse** (`kick 1` match `Kick 1`)
- **Pas d'espaces autour du `=`** (strict)
- Virgules séparent les overrides (espaces après la virgule tolérés)

**Formats acceptés pour la valeur (à droite du `=`) :**

| Format | Exemple | Signification |
|---|---|---|
| `X-Y` (court) | `H-R` | Override complet |
| `importance-fonction` (long) | `hero-rhythm` | Override complet |
| `X` (court) | `S` | Override importance uniquement |
| `importance` (long) | `support` | Override importance uniquement |
| `*-Y` (wildcard) | `*-T` | Override fonction uniquement |
| `*-fonction` | `*-textural` | Override fonction uniquement |

**Table de correspondance pour les formats longs :**
- `hero` → H, `support` → S, `atmos` → A
- `rhythm` → R, `harmonic` → H, `melodic` → M, `textural` → T

**Cas limites tranchés :**

| Annotation | Comportement |
|---|---|
| `override: Kick 1=S` | Kick 1 devient Support, fonction inchangée |
| `override: Kick 1=*-T` | Kick 1 devient textural, importance inchangée |
| `override: kick 1=hero-rhythm` | Case-insensitive, match |
| `override: Kick 1 = S` | Espaces autour du `=` → **rejet + warning** |
| `override: Kick 1=X-Y` | Codes invalides → **rejet + warning** |
| `override: Inexistant=H` | Track non trouvée → **warning log**, pas d'erreur |
| `override:Kick 1=S` | Espace manquant après `:` → **rejet + warning** |
| `override: Kick 1=S, Sub Bass=H` | Deux overrides → les deux appliqués |
| `override: Kick 1=S, Kick 1=A` | Même track deux fois → **dernière valeur gagne** |
| Annotation vide | Aucun override, pas de warning |
| Annotation sans "override:" | Aucun override, pas de warning |
| `override: Kick 1=hero-rhythm` et Kick 1 n'a pas de préfixe global | Override prend précédence, Kick 1 devient hero-rhythm dans cette section, défaut S/R ailleurs |

### R4 — Résolution du rôle final par section

Pour chaque section (Locator) et chaque track :

1. **Rôle de base** :
   - Si track a un préfixe → utiliser ce rôle
   - Sinon → `[S/R]` par défaut

2. **Chercher overrides** dans l'annotation du Locator de cette section :
   - Si override complet `X-Y` → remplace les deux dimensions
   - Si override importance seule `X` → remplace importance, garde fonction du base
   - Si override fonction seule `*-Y` → garde importance du base, remplace fonction

3. **Rôle final** = ce qui résulte de ces deux étapes

**Pas de propagation entre sections.** Chaque section part du rôle de base + ses propres overrides.

---

## Calcul du score de cohérence par section (R5)

**Total : 100 points, 4 composantes**

### Composante 1 — Ratio d'importance (40 points)

Pour la section, calculer les **proportions de tracks actives** par importance (seuil de présence 10% comme dans le filtre d'affichage).

**Ratios idéaux :**
- Hero : entre 15% et 30%
- Support : entre 30% et 50%
- Atmos : entre 20% et 40%

**Formule :**

```python
def importance_points(ratios: dict[str, float]) -> float:
    """ratios = {'H': 0.40, 'S': 0.40, 'A': 0.20}"""
    ideal = {
        'H': (0.15, 0.30),
        'S': (0.30, 0.50),
        'A': (0.20, 0.40),
    }
    points_per_dim = 40 / 3  # 13.33 points par dimension
    total = 0
    for dim in ['H', 'S', 'A']:
        r = ratios.get(dim, 0)
        low, high = ideal[dim]
        if low <= r <= high:
            total += points_per_dim  # plage idéale
        else:
            # Distance à la plage, normalisée
            if r < low:
                distance = (low - r) / low if low > 0 else 1
            else:
                distance = (r - high) / (1 - high) if high < 1 else 0
            # Pénalité proportionnelle, max 100% de pénalité
            penalty = min(distance, 1.0)
            total += points_per_dim * (1 - penalty)
    return round(total, 1)
```

**Exemples chiffrés :**

Section "Intro" avec 4 tracks : 1H, 2S, 1A
- Ratios : H=25%, S=50%, A=25%
- H dans [15%, 30%] ✓ → 13.3 points
- S à la frontière haute de [30%, 50%] ✓ → 13.3 points
- A dans [20%, 40%] ✓ → 13.3 points
- **Total : 40/40**

Section "Chorus 1" avec 14 tracks : 8H, 5S, 1A
- Ratios : H=57%, S=36%, A=7%
- H à 57%, plage [15%, 30%] : distance = (57-30)/(100-30) = 0.386, penalty = 0.386
  - Points : 13.3 × (1 - 0.386) = 8.2
- S à 36%, plage [30%, 50%] ✓ → 13.3 points
- A à 7%, plage [20%, 40%] : distance = (20-7)/20 = 0.65, penalty = 0.65
  - Points : 13.3 × (1 - 0.65) = 4.7
- **Total : 26.2 / 40**

### Composante 2 — Diversité des fonctions (20 points)

Idéal : les 4 fonctions (R, H, M, T) sont représentées dans la section.

**Barème simple :**
- 4 fonctions présentes → 20 points
- 3 fonctions présentes → 15 points
- 2 fonctions présentes → 10 points
- 1 seule présente → 5 points
- 0 fonctions (section vide) → 0 points

### Composante 3 — Pénalité conflits Hero-vs-Hero (30 points)

Partir de 30 points. Retirer 5 points par conflit **critique** hero-vs-hero identifié dans la section (référence au sheet Freq Conflicts existant, severity CRITICAL + rôles des deux tracks = H/X).

- 0 conflit H×H → 30 points
- 1 conflit H×H → 25 points
- 2 → 20 points
- ...
- 6+ conflits H×H → 0 points (plancher)

**Note :** utilise uniquement les conflits marqués CRITICAL, pas les MODERATE.

### Composante 4 — Diversité minimale des rôles (10 points)

Pénalité si trop peu de fonctions différentes.

- ≥3 fonctions → 10 points
- 2 fonctions → 5 points
- 1 fonction → 0 points
- 0 fonctions → 0 points

### Score total et diagnostic

**Diagnostic textuel basé sur le score total :**

| Score | Diagnostic générique |
|---|---|
| 80-100 | "Équilibre OK" |
| 60-79 | "Quelques déséquilibres à surveiller" |
| 40-59 | "Problèmes de composition des rôles" |
| 0-39 | "Problèmes structurels importants" |

**En plus : jusqu'à 3 messages spécifiques** selon les pénalités les plus importantes :

| Condition | Message |
|---|---|
| Ratio H > 35% | "N tracks hero simultanées — risque de masking et surcharge" |
| Ratio H < 10% | "Très peu de tracks hero — section sans leader clair" |
| Ratio A < 10% | "Peu d'éléments atmosphériques — manque d'espace et respiration" |
| Conflits H×H ≥ 3 | "N conflits critiques entre tracks hero — priorité de correction" |
| Fonction absente | "Aucun élément [Rhythm/Harmonic/Melodic/Textural] — section unidimensionnelle" |
| Section à 1 seule fonction | "Section sur une seule dimension fonctionnelle — manque de variété" |

**Règles d'affichage des messages spécifiques :**
- Tri par impact : conflits H×H > déséquilibre importance > diversité manquante
- Max 3 messages affichés
- Si score ≥ 85 et aucun message spécifique, afficher uniquement "Équilibre OK"

---

## Où enrichir le rapport

### Zone 1 — Sections Timeline

**Bloc "TRACKS ACTIVES PAR ZONE D'ENERGIE DOMINANTE" :**

Les tracks affichées gardent leur préfixe TFP. Exemple :

```
Sub (20-80 Hz) | [H/R] Kick 1 (-2 dB), [H/R] Kick 2 (-5 dB), [S/H] Sub Bass (-8 dB)
```

Si override appliqué pour cette section, afficher le rôle final (pas le global). Optionnellement : marquer avec un astérisque `*` si overridé.

**Bloc "PEAK MAX PAR TRACK DANS CETTE SECTION" :**

Nouvelle colonne "RÔLE" entre le nom et la fréquence.

```
TRACK              | RÔLE | FREQ    | AMP ZONE | TRACK PEAK | DUREE
[H/R] Kick 1       | H/R  | 87 Hz   | -7.2 dB  | -7.5 dB    | 15/15s (100%)
[H/M] Acid Bass    | H/M  | 62 Hz   | -12.5    | -12.8      | 14/15s (93%)
[S/H] Sub Bass     | S/H* | 41 Hz   | -20.3    | -20.5      | 15/15s (100%)
```

L'astérisque indique un override actif. Si pas d'override, juste `S/H` sans marqueur.

### Zone 2 — Freq Conflicts

Ajouter deux colonnes :
- `ROLE_A` : rôle de la première track
- `ROLE_B` : rôle de la seconde track
- `COMBO` : combinaison formatée (ex: `H/R × S/H`)

```
SEVERITE | ZONE    | TRACKS EN CONFLIT                       | COMBO    | SCORE
CRITICAL | Sub     | [H/R] Kick 1 <-> [S/H] Sub Bass         | H/R × S/H | 0.87
CRITICAL | Low     | [H/R] Kick 1 <-> [H/M] Acid Bass        | H/R × H/M | 0.81
MODERATE | Body    | [A/T] Ambience <-> [S/T] Arp Roaming    | A/T × S/T | 0.55
```

### Zone 3 — Mix Health Score

**Nouvelle zone "Cohérence TFP par section"** après les métriques existantes.

**Format exact attendu :**

```
Cohérence TFP par section
─────────────────────────────────────────────────────────────────────
Section    | Score | H/S/A    | R/H/M/T  | H×H crit. | Diagnostic
Intro      |  85   | 1/2/1    | 1/0/1/2  |     0     | Équilibre OK
Build 1    |  72   | 2/3/1    | 2/1/1/2  |     1     | Quelques déséquilibres à surveiller
Drop 1     |  58   | 5/2/0    | 3/1/1/1  |     3     | Problèmes de composition des rôles
                                                       | • 5 tracks hero simultanées — risque masking
                                                       | • Peu d'atmos — manque d'espace
                                                       | • 3 conflits H×H — priorité correction
Breakdown 1|  78   | 1/2/1    | 1/1/1/1  |     0     | Équilibre OK
Outro      |  —    | 0/1/0    | 0/0/0/1  |     0     | Section trop courte ou sparse
```

**Notes de format :**
- Score affiché en entier (arrondi)
- H/S/A = **nombres absolus** de tracks (pas pourcentages)
- R/H/M/T = nombres absolus
- H×H crit. = nombre de conflits critiques hero-vs-hero
- Diagnostic sur une ligne générique + lignes supplémentaires pour messages spécifiques (indentées avec `•`)
- Sections à < 3 tracks actives OU très courtes (< 3s) : score = "—" (pas calculable proprement)

### Zone 4 — AI Context

**Ne pas modifier.** Ce sheet est consolidé par track entière, pas par section. Les rôles globaux peuvent être ajoutés dans une colonne dédiée si simple à faire, mais ce n'est pas prioritaire.

### Zone 5 — Warning "tracks sans préfixe"

Dans le sheet Sections Timeline, **en tête** (ligne 1-3), afficher un bloc visible si des tracks sans préfixe ont été détectées :

```
⚠ WARNING TFP — TRACKS SANS PRÉFIXE
─────────────────────────────────────────
N tracks n'ont pas de préfixe TFP dans leur nom :
  • Nouvelle Track 1
  • Nouvelle Track 2
Ces tracks ont été classifiées par défaut [S/R]. 
Pour les classifier correctement, renommer dans Ableton avec le format [X/Y] avant les prochaines analyses.
```

Si toutes les tracks ont un préfixe, ce bloc n'apparaît pas du tout.

---

## Contexte technique du projet

### État actuel du repo (que tu connais déjà)

- Branche principale : `main`
- Derniers commits pertinents : filtrage track_peak, UX persistance, Sections Timeline renommé
- Tests : autour de 198/198 passent
- Fichier JSON mapping devices : `ableton_devices_mapping.json` (nom stable, versioning interne)

### Fichiers clés

- `section_detector.py` : détection et lecture des Locators, dataclass Section
- `feature_storage.py` : construction du sheet Sections Timeline
- `mix_analyzer.py` : orchestration générale + construction des sheets Health Score, Freq Conflicts, AI Context
- `als_utils.py` : lecture XML du `.als`, extraction des noms de tracks (EffectiveName/UserName)

### Fichier de test

`/chemin/local/Acid_Drops_Sections_TFP.als` (utilisateur doit te le fournir au moment de la Phase C). Contient :
- 35 tracks individuelles préfixées TFP (+3 BUS, +1 Main = 39 total dans le `.als`)
- 20 Locators manuels (sans overrides pour l'instant)
- Un `.als` valide et testé

### Distribution par défaut attendue sur Acid Drops

- Warning "tracks sans préfixe" : **ne doit pas apparaître** (toutes les 35 tracks sont classifiées)
- Nombre de sections analysées : 20
- Sections probablement identifiées comme équilibrées : Intro, Breakdown 1, plusieurs Build
- Sections probablement problématiques : Chorus 1 (14 tracks dont beaucoup de hero), Drop 2

---

## Livraison en 3 phases avec STOP obligatoire

**Règle non-négociable : STOP après chaque phase, attente validation avant suite.**

### PHASE A — Reconnaissance technique (pas de code)

**Objectif :** comprendre l'architecture existante avant de coder.

**Questions à répondre :**

1. **Lecture des noms de tracks** : où, dans `als_utils.py` ou équivalent, les noms `EffectiveName`/`UserName` sont-ils lus ? Ces noms sont-ils propagés jusqu'aux sheets du rapport, ou transformés en cours de route ?

2. **Annotations de Locators** : dans `section_detector.py`, la dataclass `Section` a-t-elle déjà un champ pour stocker l'annotation du Locator ? Sinon, où la récupérer ?

3. **Structure Section** : quels champs faudrait-il ajouter à la dataclass `Section` pour porter les rôles résolus par track ? Proposition : `track_roles: dict[str, tuple[str, str]]` (track_name → (importance, function))

4. **Fonctions builder de sheets** : les blocs qui listent des tracks sont-ils construits par des fonctions réutilisables ou en string concat inline ?

5. **Score de cohérence — emplacement** : mieux de calculer dans `section_detector.py` (en enrichissant Section) ou dans un nouveau module `tfp_coherence.py` ou dans `mix_analyzer.py` ?

6. **Conflits H×H** : le sheet Freq Conflicts expose-t-il une structure de données accessible (dict, dataframe) qu'on peut itérer pour compter les H×H par section ? Ou faut-il re-calculer ?

7. **Risques identifiés** : anticipe 2-3 pièges spécifiques à cette intégration, avec mitigation proposée.

**Format de réponse :**

```
RECONNAISSANCE PHASE A — Feature 3.5 TFP

Q1 — Lecture noms tracks : [fichier:fonction:ligne]
Q2 — Annotations Locators : [OUI/NON, détails]
Q3 — Extension Section : [champs à ajouter]
Q4 — Fonctions builder : [OUI/NON, détails]
Q5 — Emplacement score : [recommandation + justification]
Q6 — Conflits H×H accessibles : [OUI/NON, comment]
Q7 — Risques :
  - [Risque 1 + mitigation]
  - [Risque 2 + mitigation]

DÉCOUPAGE EN COMMITS PROPOSÉ :
  B1 : [titre]
  B2 : [titre]
  B3 : [titre]

ESTIMATION : [X minutes par commit]
```

**STOP. N'écris aucune ligne de code.**

### PHASE B — Implémentation en 3 sous-commits

**Ne commence qu'après validation Phase A.**

#### B1 — Parser TFP (module isolé)

**Scope :**
- Nouveau module `tfp_parser.py` (ou intégré si plus logique ailleurs)
- Fonction `parse_tfp_prefix(name: str) -> tuple[Importance, Function, clean_name] | None`
- Fonction `parse_tfp_overrides(annotation: str) -> dict[str, tuple[Importance|None, Function|None]]`
- Fonction `resolve_track_role(name: str, section_overrides: dict, default=('S','R')) -> tuple[Importance, Function]`
- Énumérations ou constantes pour Importance et Function
- Tests unitaires exhaustifs : tous les cas limites tranchés dans R1 et R3

**Tests minimum attendus :**
- 10 tests de parsing du préfixe (cas R1)
- 10 tests de parsing des overrides (cas R3)
- 5 tests de résolution complète (R4)

**Commit :** `feat(tfp): add parser for TFP prefixes and overrides with exhaustive tests`

#### B2 — Intégration dans sections et enrichissement du rapport

**Scope :**
- Ajouter `track_roles: dict[str, tuple[Importance, Function]]` à Section
- Peupler au moment de la construction des sections
- Enrichir Sections Timeline (bloc "TRACKS ACTIVES" avec préfixes + bloc "PEAK MAX" avec colonne RÔLE + astérisque pour overrides)
- Enrichir Freq Conflicts avec colonnes ROLE_A, ROLE_B, COMBO
- Warning "tracks sans préfixe" en tête de Sections Timeline

**Tests :**
- 2 tests d'intégration : track avec préfixe, track avec override
- 1 test du warning (track sans préfixe détectée)

**Commit :** `feat(tfp): integrate roles into sections and enrich report sheets`

#### B3 — Score de cohérence

**Scope :**
- Fonction `compute_section_coherence(section) -> dict` retournant score, composantes, diagnostic
- Nouvelle zone "Cohérence TFP par section" dans Mix Health Score
- Format exact spécifié dans "Zone 3" ci-dessus
- Gestion du cas "section trop courte/sparse" (score = "—")

**Tests :**
- 2 tests de calcul du score : section équilibrée (attendu 85+), section déséquilibrée (attendu < 60)
- 1 test des messages de diagnostic
- Validation manuelle : les exemples chiffrés de R5 doivent produire les valeurs attendues

**Commit :** `feat(tfp): add section coherence score in Mix Health Score`

### PHASE C — Validation sur Acid Drops

**Ne commence qu'après validation Phase B (3 commits).**

**Objectif :** confirmer que Feature 3.5 fonctionne sur le cas réel.

**Actions :**

1. Re-run Mix Analyzer sur `Acid_Drops_Sections_TFP.als`
2. Vérifier :
   - ✓ Aucun warning "tracks sans préfixe" (toutes classifiées)
   - ✓ Sections Timeline affiche les préfixes dans "TRACKS ACTIVES" et colonne RÔLE dans "PEAK MAX"
   - ✓ Freq Conflicts a les colonnes ROLE_A, ROLE_B, COMBO avec des valeurs
   - ✓ Mix Health Score contient "Cohérence TFP par section" avec scores pour les 20 sections
3. Contrôles de cohérence :
   - Drop 1 (Pluck Lead, NINja, beaucoup de hero) : score attendu 55-70, message "hero simultanés"
   - Intro (4 tracks équilibrées) : score attendu 80+
   - Outro (1 track seule) : score = "—" (trop sparse)
   - Chorus 1 (14 tracks) : score attendu 50-65, messages "hero simultanés" + "conflits H×H"

**Livrable Phase C :**

```
PHASE C — Validation Feature 3.5

Re-run : [OK/échec]
Vérifications visuelles : [détails par zone]
Contrôles cohérence :
  - Drop 1 : score [X] — [messages affichés]
  - Intro : score [X] — [messages]
  - Outro : score [X ou —]
  - Chorus 1 : score [X] — [messages]

Verdict : [Prêt pour merge / Ajustements]
```

---

## Règles générales

### Anti-timeout
- Commit WIP si limite approche
- Sous-phases B1 / B2 / B3 indépendantes — validation séparée

### Hors scope absolu
- Pas de modification du `.als` par Mix Analyzer
- Pas de suggestions automatiques de classification
- Pas d'actions correctives (c'est Feature 3.6)
- Pas de refactor opportuniste

### Compat ascendante
- Un `.als` sans préfixes continue à fonctionner (tout `[S/R]` + warning visible)
- Les sheets existants gardent leur structure, juste enrichis
- Les tests existants doivent continuer à passer

### Documentation code
- Docstrings claires sur les 3 fonctions principales du parser
- Commentaires sur les valeurs numériques du score (pourquoi 40/20/30/10)

## Priorité

Cette feature finalise l'infrastructure d'analyse contextuelle. Elle débloque Feature 3.6 (CDE) qui utilisera les rôles pour qualifier les corrections.

**Commence par la Phase A.**
