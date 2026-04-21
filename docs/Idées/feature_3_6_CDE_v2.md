# Feature 3.6 — Correction Diagnostic Engine (CDE)

## Référence : Mix Analyzer v3.1 / Feature 3.6 de N

**Version du document : 2.0**
**Dernière mise à jour : 2026-04-21**
**Révision post-livraison Feature 3.5**

---

## 1. Contexte et changements depuis v1.0

Ce document est une réécriture du `feature_3_6_CDE.md` original suite aux livraisons de Features 3 et 3.5, et aux décisions prises pendant leur développement. Les changements principaux :

**Changement de cadrage fondamental :** Feature 3.6 n'est pas un moteur d'automatisation qui écrit des corrections dans l'ALS. C'est un **moteur de diagnostic qui produit des candidats de correction pour consommation collaborative** (utilisateur + Claude via API, qui est Feature 1). L'application finale dans l'ALS reste pilotée par décision humaine, pas par le CDE seul.

**Nouvelles sources de données validées :** les sheets `Sections Timeline` (bloc CONFLITS DE FRÉQUENCES et ACCUMULATIONS) et la structure `Section.track_roles` (Feature 3.5) sont les sources primaires, remplaçant les `_track_copresence` mentionnés dans la v1 qui n'existent pas dans le rapport actuel.

**Simplifications actées :** le système de règles versionnées et l'estimation d'impact chiffrée de la v1 sont reportés en v2 du CDE. La v1 se concentre sur la génération de diagnostics utiles pour une conversation structurée avec Claude.

**Learnings intégrés :** is_audible (automation Utility.Gain binaire), post-fader comme vérité, filtrage 10%, matching 3 nommages (WAV / auto_map / Ableton TFP-prefixé).

---

## 2. Problème métier

### Ce que le rapport actuel (post-Feature 3.5) produit

Le rapport Excel contient des **mesures brutes structurées** : conflits fréquentiels par section, rôles TFP par track, score de cohérence, peaks par track et par bande, etc.

### Ce qui manque

L'utilisateur lit le rapport et voit :
- "Drop 1 : 8 conflits critiques H×H, score 52, messages diagnostiques génériques"
- "CRITICAL conflit Kick 1 ↔ Sub Bass à 62 Hz (score 0.87)"

**Mais le rapport ne lui dit pas :**
- "Que faire concrètement ?"
- "Est-ce que cette correction proposée est sûre ?"
- "Quelle est l'alternative si elle ne marche pas ?"
- "Sur quelles bases le système a-t-il choisi cette recommandation ?"

Pour chaque conflit détecté, il faut actuellement que l'utilisateur (ou Claude en conversation) **interprète les données brutes, applique des règles de mixage mentales, et décide d'une action**. Ce travail est répété pour les dizaines de conflits d'un morceau.

### Ce qu'on veut

Un **moteur qui pré-mâche ce travail** en produisant, pour chaque problème détecté :
1. Un diagnostic structuré et lisible
2. Une recommandation primaire avec justification
3. Un fallback conservateur si la primaire est risquée
4. Les sources et règles qui ont mené à la décision (audit trail)
5. Une estimation qualitative des conséquences attendues
6. Un identifiant unique pour référencer le diagnostic dans une conversation

### Résultat attendu

L'utilisateur peut dire à Claude : *"Regarde le diag RES_BR_247_DROP, qu'en penses-tu ?"* et Claude peut accéder au diagnostic complet via l'API Feature 1, le discuter avec l'utilisateur, et éventuellement demander à Feature 1 de l'écrire dans l'ALS.

---

## 3. Cadrage strict du périmètre

### Dans le scope

- Génération de diagnostics structurés pour 5 types de problèmes
- Règles de recommandation basées sur les rôles TFP
- Logique de fallback conservatrice
- Estimation d'impact qualitative (liste de conséquences observables)
- Stockage JSON + sheet Excel pour consultation
- Intégration avec le système de backup ALS automatique (déjà présent dans Mix Analyzer)

### Hors scope (reporté en v2 du CDE ou en autre feature)

- Application automatique des corrections dans l'ALS (c'est Feature 1)
- Système de règles versionnées avec decorator (complexité excessive pour v1)
- Estimation d'impact chiffrée avec ranges (+2 à +4 dB) — sans modèle prédictif validé, ces chiffres seraient inventés
- Patches réversibles granulaires avec inverse_operations (on utilise backup ALS complet)
- Refactor de Feature 1 pour consommer le CDE (séparé)
- Calcul de delta réel du Health Score post-correction (nécessite run before/after, v2)

### Règles absolues

- Le CDE n'écrit jamais dans l'ALS. Point final.
- Le CDE ne recommande jamais de correction qui violerait un rôle TFP (ex: couper à la fondamentale d'une track Hero Melodic)
- Le CDE ne recommande jamais une correction sans audit trail complet
- Les diagnostics sont déterministes : mêmes inputs → mêmes outputs

---

## 4. Structure d'un diagnostic (simplifiée vs v1)

```python
@dataclass
class CorrectionDiagnostic:
    # Identification
    diagnostic_id: str                # ex: "CONF_DROP1_KICK1_SUBBASS_62HZ"
    timestamp: datetime
    cde_version: str                  # ex: "1.0"

    # Problème
    track_a: str                      # track principale concernée
    track_b: str | None               # track secondaire si conflit
    section: str | None               # None = toute la durée
    issue_type: str
    severity: str                     # "critical" | "moderate" | "minor"
    measurement: ProblemMeasurement

    # Contexte
    tfp_context: TFPContext
    section_context: SectionContext

    # Recommandations
    diagnosis_text: str               # explication en langage naturel
    primary_correction: CorrectionRecipe
    fallback_correction: CorrectionRecipe | None

    # Impact qualitatif (pas chiffré)
    expected_outcomes: list[str]      # "Le kick aura plus de punch dans Drop 1"
    potential_risks: list[str]        # "Acid Bass pourrait perdre du body"
    verification_steps: list[str]     # "Écouter Drop 1 à 1:19, le kick doit claquer"

    # Application
    application_status: str           # "proposed" | "applied" | "rejected" | "reverted"
    rejection_reason: str | None      # si rejected, pourquoi
    applied_backup_path: str | None   # chemin du backup ALS si appliqué

    # Audit
    data_sources: list[str]           # sheets consultés
    rules_applied: list[str]          # noms des règles (pas versions pour v1)
```

### Sous-types

```python
@dataclass
class ProblemMeasurement:
    frequency_hz: float | None
    peak_db: float | None
    duration_in_section_s: float
    duration_ratio_in_section: float  # 0-1
    is_audible_fraction: float        # fraction où track réellement audible
    severity_score: float             # 0-1 normalisé
    masking_score: float | None       # si conflit

@dataclass
class TFPContext:
    track_a_role: tuple[str, str]    # ex: ("H", "R")
    track_b_role: tuple[str, str] | None
    role_compatibility: str           # "compatible" | "conflict" | "dominant_support"

@dataclass
class SectionContext:
    section_name: str
    section_duration_s: float
    tracks_active_count: int
    conflicts_in_section: int
    coherence_score: int | None       # du TFP coherence

@dataclass
class CorrectionRecipe:
    target_track: str
    device: str                       # ex: "EQ8 — Peak Resonance" ou "Kickstart 2"
    approach: str                     # "dynamic_cut" | "static_dip" | "sidechain" | etc.
    parameters: dict                  # freq, gain, Q, trigger, depth, release, etc.
    applies_to_sections: list[str]    # si correction section-locale
    rationale: str                    # pourquoi cette approche
    confidence: str                   # "high" | "medium" | "low"
```

---

## 5. Les 5 détecteurs de problèmes

### 5.1 Masking conflicts (prioritaire)

**Source :** bloc "CONFLITS DE FRÉQUENCES" dans Sections Timeline (déjà calculé par Mix Analyzer).

**Logique :** pour chaque conflit CRITICAL ou MODERATE dans une section, générer un diagnostic. Le rôle TFP des deux tracks oriente la recommandation.

### 5.2 Accumulation risks (prioritaire)

**Source :** bloc "ACCUMULATIONS" dans Sections Timeline (déjà calculé).

**Logique :** quand 4+ tracks ont de l'énergie simultanée dans une même bande sur au moins 3 buckets, proposer un cut sur les tracks de plus basse importance TFP.

### 5.3 Resonance buildups

**Source :** `_track_peak_trajectories` (déjà dans le rapport).

**Logique :** détecter les peaks persistants qui dépassent le spectre moyen de la track. Pour track Hero Melodic, vérifier si le peak correspond à une fréquence signature avant de recommander un cut.

### 5.4 Phase issues

**Source :** `_track_stereo_bands` (déjà dans le rapport) + sheet `Anomalies` qui liste les tracks avec PHASE_CRIT.

**Logique :** corrélation de phase négative dans une bande → recommander M/S side cut (en notant dépendance à Feature 4 pour application).

### 5.5 Dynamic imbalance

**Source :** `_track_dynamics_time` + `AI Context` (crest_db par track).

**Logique :** crest factor anormal pour le rôle TFP de la track. Exemple : track Hero Rhythm avec crest > 30 dB dans une section (trop dynamique pour un groove), ou Hero Melodic avec crest < 10 dB (trop compressée, perte d'expression).

### Priorisation pour v1 livré

**Phase 1 livrable :** masking + accumulation (80% de la valeur, 40% de la complexité)
**Phase 2 livrable :** resonance buildups
**Phase 3 livrable :** phase issues (dépend de Feature 4 pour application)
**Phase 4 livrable :** dynamic imbalance (logique floue, à affiner)

---

## 6. Logique de recommandation

### 6.1 Matrice de décision pour masking conflicts

Pour un conflit entre track A et track B dans une section donnée :

| Rôle A | Rôle B | Recommandation primaire |
|---|---|---|
| Hero (H/*) | Hero (H/*) | reciprocal_cuts : cut léger sur chaque dans la zone de l'autre |
| Hero (H/*) | Support (S/*) | sidechain : B ducke quand A joue |
| Hero (H/*) | Atmos (A/*) | cut sur B dans la zone de conflit |
| Support (S/*) | Support (S/*) | cut sur B (secondaire à A par convention alphabétique si égalité) |
| Support (S/*) | Atmos (A/*) | cut sur B dans la zone de conflit |
| Atmos (A/*) | Atmos (A/*) | laisser (atmos vs atmos = rarement un vrai problème) |

**Exceptions :**
- Si une des tracks est Hero Rhythm (H/R) et l'autre Hero Harmonic (H/H), privilégier sidechain de H/H sur H/R (classique kick + bass).
- Si fonction Textural est impliquée, cut dans la zone spécifique plutôt que sidechain (les textures sont continues).

### 6.2 Fallback conservateur

Pour chaque recommandation primaire, un fallback moins agressif :

| Primaire | Fallback |
|---|---|
| dynamic_cut Q=10 | static_dip Q=4 moins profond |
| surgical_notch Q=12 | musical_dip Q=4 |
| reciprocal_cuts | cut sur une seule des deux |
| sidechain depth -8dB | sidechain depth -4dB |
| ms_side_cut | stereo_cut |

### 6.3 Règles de protection

Avant d'émettre une recommandation, le CDE vérifie :

**Règle 1 — Signature frequency protection**
Pour les tracks Hero Melodic ou Hero Harmonic, ne pas recommander de cut > 2 dB dans leur bande dominante (calculée depuis `pct_*` dans AI Context).

**Règle 2 — Sub integrity for Hero Rhythm**
Pour les kicks classifiés H/R, ne pas recommander de cut dans la zone Sub (20-80 Hz).

**Règle 3 — Role-appropriate max cut**
- Track [H/*] : max cut -3 dB
- Track [S/*] : max cut -6 dB
- Track [A/*] : max cut -12 dB

Si la correction logique nécessiterait un cut plus profond, la recommandation primaire est recalibrée au max autorisé et un warning est ajouté : "Correction au max autorisé pour une track Hero, conflit probablement non résolu totalement."

---

## 7. Estimation d'impact qualitative

**Pas de chiffres inventés.** Le CDE produit une liste de conséquences observables :

### 7.1 Expected outcomes (ce qui va changer)

Généré à partir du type de correction et du contexte :

- "Le kick aura plus d'espace dans la bande 60-80 Hz pendant Drop 1"
- "Le sub-mix sera moins boueux dans les drops"
- "Les vocaux gagneront en présence dans Chorus 1"

### 7.2 Potential risks (ce qui pourrait mal tourner)

- "L'Acid Bass pourrait perdre du body si le HPF est trop haut"
- "La réduction Side pourrait faire paraître le Pluck Lead plus centré"
- "Le sidechain pourrait créer un pumping audible si le release est trop long"

### 7.3 Verification steps (comment vérifier)

Instructions concrètes pour que l'utilisateur valide à l'oreille :

- "Écouter Drop 1 à partir de 1:19 — le kick doit sentir plus punchy"
- "Vérifier que l'Acid Bass garde son character dans Acid 1 (celui qui t'intéresse)"
- "Comparer A/B avec la version avant correction"

---

## 8. Workflow utilisateur

### 8.1 Flux typique

```
ÉTAPE 1 — Génération
Utilisateur run Mix Analyzer normalement.
Le CDE génère automatiquement les diagnostics pour tous les problèmes détectés.
Résultat : rapport Excel enrichi + <projet>_diagnostics.json créé.

ÉTAPE 2 — Consultation
Utilisateur ouvre le rapport, va sur le sheet "Correction Diagnostics".
Il voit la liste des diagnostics triés par sévérité :
  "15 diagnostics CRITICAL, 28 MODERATE, 7 MINOR"

ÉTAPE 3 — Conversation avec Claude
Utilisateur ouvre Claude : "Regarde le diag CONF_DROP1_KICK1_SUBBASS_62HZ."
Claude accède au JSON diagnostics, lit le contexte complet.
Discussion : Claude explique, l'utilisateur décide.

ÉTAPE 4 — Application (si décision positive)
L'utilisateur demande à Claude d'appliquer via Feature 1.
Feature 1 utilise le patch du diagnostic, backup automatique de l'ALS,
puis écriture des modifications.

ÉTAPE 5 — Vérification
Utilisateur pull le nouvel ALS, écoute, valide ou revert.
Si validé : diagnostic passe à status="applied".
Si revert : status="reverted", backup restauré.
```

### 8.2 Attention particulière

Le workflow collaboratif (étapes 3-5) est **hors scope strict de Feature 3.6**. Feature 3.6 livre seulement les étapes 1-2. La suite est livrée par :
- **Feature 1** : API de validation et application
- **Intégration Claude** : conversation naturelle (pas de code dédié)

---

## 9. Stockage et visualisation

### 9.1 Fichier JSON

`<projet>_diagnostics.json` créé à côté du `.als` :

```json
{
  "project": "Acid Drops",
  "cde_version": "1.0",
  "generated_at": "2026-04-21T16:00:00",
  "als_analyzed": "Acid_Drops_Sections_TFP.als",
  "summary": {
    "critical": 15,
    "moderate": 28,
    "minor": 7
  },
  "diagnostics": [
    {
      "diagnostic_id": "CONF_DROP1_KICK1_SUBBASS_62HZ",
      "issue_type": "masking_conflict",
      "severity": "critical",
      "track_a": "Kick 1",
      "track_b": "Sub Bass",
      "section": "Drop 1",
      "measurement": {
        "frequency_hz": 62,
        "peak_db": 0.87,
        "duration_ratio_in_section": 1.0,
        "masking_score": 0.87
      },
      "tfp_context": {
        "track_a_role": ["H", "R"],
        "track_b_role": ["S", "H"],
        "role_compatibility": "dominant_support"
      },
      "diagnosis_text": "Conflit critique à 62 Hz entre Kick 1 (Hero Rhythm) et Sub Bass (Support Harmonic). Le Sub Bass occupe la fondamentale du Kick, créant du masking dans toute la durée de Drop 1.",
      "primary_correction": {
        "target_track": "Sub Bass",
        "device": "Kickstart 2",
        "approach": "sidechain",
        "parameters": {
          "trigger_track": "Kick 1",
          "depth_db": -8,
          "release_ms": 150,
          "active_in_sections": ["Drop 1"]
        },
        "rationale": "Le Sub Bass étant support du Kick (rôle harmonique), un sidechain permet à chaque kick de créer de l'espace pour le sub sans toucher à l'EQ.",
        "confidence": "high"
      },
      "fallback_correction": {
        "target_track": "Sub Bass",
        "device": "EQ8 — Peak Resonance",
        "approach": "static_dip",
        "parameters": {
          "frequency_hz": 62,
          "gain_db": -3,
          "q": 3,
          "active_in_sections": ["Drop 1"]
        },
        "rationale": "Alternative sans sidechain : léger dip statique à la fondamentale du Kick.",
        "confidence": "medium"
      },
      "expected_outcomes": [
        "Le kick aura plus de punch dans Drop 1",
        "Le sub-mix sera plus propre pendant les frappes",
        "L'auditeur percevra mieux la pulsation rythmique"
      ],
      "potential_risks": [
        "Le Sub Bass pourrait paraître moins soutenu si le sidechain est trop prononcé",
        "Un release trop court peut créer un pumping audible"
      ],
      "verification_steps": [
        "Écouter Drop 1 à 1:19 — le kick doit sentir plus clair",
        "Vérifier que le Sub Bass reste audible entre les frappes",
        "Tester sur enceintes ET casque (le sidechain s'entend différemment)"
      ],
      "application_status": "proposed",
      "data_sources": [
        "Sections Timeline:CONFLITS DE FRÉQUENCES",
        "Section.track_roles (Feature 3.5)",
        "AI Context:Kick 1",
        "AI Context:Sub Bass"
      ],
      "rules_applied": [
        "hero_vs_support_sidechain_rule",
        "signature_freq_protection_check",
        "sub_integrity_hero_rhythm_rule"
      ]
    }
  ]
}
```

### 9.2 Sheet Excel `Correction Diagnostics`

Nouveau sheet dans le rapport, après Mix Health Score :

```
Correction Diagnostics
─────────────────────────────────────────────────────────────────
Priorité : CRITICAL (15) | MODERATE (28) | MINOR (7)

#  | ID                                | Sévérité | Section | Track A | Track B  | Issue          | Primary              | Status
1  | CONF_DROP1_KICK1_SUBBASS_62HZ     | CRITICAL | Drop 1  | Kick 1  | Sub Bass | masking_conflict | sidechain -8dB      | proposed
2  | CONF_DROP1_KICK1_ACIDB_85HZ       | CRITICAL | Drop 1  | Kick 1  | Acid Bass| masking_conflict | reciprocal_cuts     | proposed
...
```

Pour les diagnostics les plus importants, une ligne détaillée avec le diagnosis_text et la primary_correction étendue.

### 9.3 API de consultation

Fonctions publiques accessibles par Feature 1 et par l'utilisateur via Claude :

```python
def load_diagnostics(project_path: Path) -> list[CorrectionDiagnostic]
def get_diagnostic_by_id(diag_id: str, project_path: Path) -> CorrectionDiagnostic
def filter_diagnostics(
    project_path: Path,
    severity: str | None = None,
    section: str | None = None,
    track: str | None = None,
    issue_type: str | None = None,
    status: str | None = None,
) -> list[CorrectionDiagnostic]
```

---

## 10. Livraison en phases

**Règle absolue : STOP après chaque phase, validation utilisateur, puis suite.**

### Phase A — Reconnaissance technique (pas de code)

**Durée estimée : 30-45 min**

Claude Code répond aux questions sans écrire de code :

1. Où sont lus les blocs "CONFLITS DE FRÉQUENCES" et "ACCUMULATIONS" de Sections Timeline actuellement ? Sont-ils accessibles en tant que structures de données ou seulement rendus en texte ?

2. La dataclass `Section` (post-Feature 3.5) contient-elle toutes les données nécessaires (track_roles, conflicts, accumulations) ou faut-il l'étendre ?

3. Le sheet `_track_peak_trajectories` est-il un output final ou une structure intermédiaire accessible dans le pipeline ?

4. Où est le meilleur endroit pour insérer le module `cde_engine.py` ? Proposer une structure de dossier.

5. Le système de backup ALS existe-t-il déjà quelque part (pour quand Feature 1 appliquera les corrections) ou faut-il le créer ?

6. Risques identifiés avec mitigations proposées.

7. Proposition de découpage en sous-commits (B1, B2, B3, B4).

**Livrable :** un message structuré qui répond aux 7 questions. **Pas de code**.

**STOP Phase A — Attente validation utilisateur**

### Phase B — Implémentation du CDE en 4 sous-commits

**Ne commence que si Phase A validée.**

#### B1 — Infrastructure CDE + détecteur masking

**Scope :**
- Nouveau module `cde_engine.py` avec dataclasses (CorrectionDiagnostic, ProblemMeasurement, TFPContext, etc.)
- Fonction `detect_masking_conflicts(section, sections_data)` qui lit le bloc CONFLITS de Sections Timeline
- Fonction `generate_diagnostic_for_masking(conflict, tfp_data, section_data)`
- Fonction `compute_primary_recommendation(diagnostic)` avec matrice H×H vs H×S etc.
- Fonction `compute_fallback_recommendation(diagnostic)` avec règles conservatrices
- Sérialisation JSON basique
- 15 tests unitaires :
  - 5 tests parsing conflits
  - 5 tests matrice décision (chaque combinaison de rôles)
  - 5 tests fallback

**Exclus de B1 :** sheet Excel, autres détecteurs, API de consultation.

**Commit :** `feat(cde): core engine + masking conflict detector`

**Durée estimée : 3-4h**

**STOP B1 — Attente validation**

#### B2 — Détecteur accumulation + sheet Excel

**Scope :**
- Fonction `detect_accumulation_risks(section)` qui lit le bloc ACCUMULATIONS
- Fonction `generate_diagnostic_for_accumulation(accumulation, tfp_data)`
- Intégration dans le pipeline principal (`mix_analyzer.py` génère automatiquement les diagnostics après l'analyse)
- Nouveau sheet `Correction Diagnostics` dans le rapport Excel
- Sérialisation JSON `<projet>_diagnostics.json`
- 10 tests :
  - 5 tests parsing accumulations
  - 3 tests intégration pipeline
  - 2 tests sérialisation JSON round-trip

**Exclus de B2 :** détecteurs resonance/phase/dynamics, API de consultation.

**Commit :** `feat(cde): accumulation detector + Excel sheet + JSON output`

**Durée estimée : 2-3h**

**STOP B2 — Attente validation**

#### B3 — API de consultation

**Scope :**
- Module `cde_api.py` avec fonctions `load_diagnostics`, `get_diagnostic_by_id`, `filter_diagnostics`
- Docstrings détaillées pour utilisation par Claude en conversation
- 8 tests :
  - 3 tests load/get
  - 5 tests filter avec différents critères

**Exclus de B3 :** application des corrections (c'est Feature 1).

**Commit :** `feat(cde): consultation API for collaborative use`

**Durée estimée : 1-2h**

**STOP B3 — Attente validation**

#### B4 — Détecteurs étendus (resonance, phase, dynamics)

**Scope :**
- Fonction `detect_resonance_buildups(track, peak_trajectories)` en lisant `_track_peak_trajectories`
- Fonction `detect_phase_issues(track, stereo_bands)` en lisant `_track_stereo_bands`
- Fonction `detect_dynamic_imbalance(track, dynamics_time, tfp_role)` en lisant `_track_dynamics_time`
- Règles de recommandation pour ces 3 types
- 12 tests :
  - 4 tests par type de détecteur
  - Vérification sur Acid_Drops : les résonances connues (248 Hz sur plusieurs tracks) doivent être détectées

**Commit :** `feat(cde): extended detectors - resonance, phase, dynamic imbalance`

**Durée estimée : 3-4h**

**STOP B4 — Attente validation**

### Phase C — Validation sur Acid Drops

**Objectif :** vérifier que le CDE produit des diagnostics cohérents avec la réalité du morceau.

**Actions :**
1. Re-run Mix Analyzer sur `Acid_Drops_Sections_TFP.als` avec toutes les phases B livrées
2. Vérifier :
   - Le sheet Correction Diagnostics est présent
   - Le JSON diagnostics est généré
   - Nombre de diagnostics CRITICAL cohérent avec les conflits détectés par Feature 3.5
   - Vérifications spot-check sur 5-10 diagnostics représentatifs

**Contrôles précis attendus :**
- Drop 2 (19 conflits H×H critiques) : doit générer 19+ diagnostics CRITICAL masking
- Chorus 1 (11 conflits H×H) : doit générer 11+ diagnostics CRITICAL masking
- Acid 3 (100% hero, 5 conflits H×H) : tous les diagnostics doivent proposer des corrections adaptées aux Hero
- Intro (3H/1S/1A) : diagnostic du Kick 1 vs Kick 2 doit proposer reciprocal_cuts (hero vs hero), pas sidechain

**Durée estimée : 1-2h pour validation**

**STOP Phase C — Si validé, merge sur main**

---

## 11. Estimations agrégées

**Développement total : 9-13h de travail Claude Code**, découpé en 4 sous-commits validables indépendamment.

**Temps utilisateur :**
- Validations entre phases : ~15 min chacune
- Validation finale Phase C : 1h
- **Total utilisateur : ~2h**

**Délai calendaire recommandé :**
- Phase A + B1 en une session (4-5h)
- Pause, validation, digestion
- B2 + B3 en une deuxième session (3-4h)
- B4 dans une troisième session (3-4h)
- Phase C en standalone (1-2h)

**Répartition sur 1 semaine ouvrable si concentré.**

---

## 12. Risques et mitigations

### Risque 1 — Trop de diagnostics générés (bruit)

**Symptôme :** le rapport génère 200+ diagnostics, l'utilisateur est paralysé.

**Mitigation :** filtrage par défaut à CRITICAL uniquement dans le sheet Excel. Les autres sont dans le JSON, accessibles via l'API de filtrage. L'utilisateur peut demander à Claude "montre-moi les MODERATE pour Drop 1" et obtenir un subset ciblé.

### Risque 2 — Règles de recommandation inadaptées à l'esthétique industrielle

**Symptôme :** le CDE recommande systématiquement de "nettoyer" des résonances qui font partie du character Qrust.

**Mitigation :** règles de protection TFP (Règle 1 en section 6.3) qui limitent les cuts sur Hero. Les tracks Hero Melodic (Acid Bass, leads) sont protégées de cuts agressifs dans leur bande dominante. L'utilisateur peut toujours forcer une correction via Feature 1 si désiré.

### Risque 3 — Interaction non prévue avec Feature 3.5 après nouvelles versions

**Symptôme :** une future modification de Feature 3.5 casse le parsing TFP du CDE.

**Mitigation :** le CDE consomme les données Feature 3.5 via les structures publiques (Section.track_roles, etc.), pas via parsing. Si Feature 3.5 évolue, le CDE ne se casse pas tant que l'interface publique reste stable. Ajouter tests d'intégration pour éviter les régressions.

### Risque 4 — Timeout pendant B4 (détecteurs étendus)

**Symptôme :** Claude Code timeout en essayant d'implémenter les 3 détecteurs dans un seul commit.

**Mitigation :** si ça arrive, découper B4 en B4a (resonance), B4b (phase), B4c (dynamics). Chacun est indépendant et peut être commité séparément.

### Risque 5 — Diagnostics pour tracks MIDI sans WAV

**Symptôme :** le CDE plante si une track MIDI (pas bouncée en WAV) apparaît dans les conflits.

**Mitigation :** vérifier l'existence du WAV dans les détecteurs. Si pas de WAV, skip le diagnostic avec un warning log.

---

## 13. Tests d'acceptance

### Test 1 — Diagnostic masking généré correctement

Input : conflit CRITICAL Kick 1 ↔ Sub Bass à 62 Hz dans Drop 1, score 0.87.
Attendu :
- 1 diagnostic généré
- `issue_type = "masking_conflict"`
- `severity = "critical"`
- `primary_correction.approach = "sidechain"` (car H/R vs S/H = dominant_support)
- `fallback_correction.approach = "static_dip"`

### Test 2 — Protection signature frequency

Input : track `[H/M] Acid Bass`, peak à 62 Hz (supposé être sa fondamentale car dom_band = Sub).
Attendu :
- Diagnostic généré avec `application_status = "rejected"` si la correction dépasse -2 dB
- `rejection_reason` mentionne "signature frequency protection"

### Test 3 — Matrice H vs H génère reciprocal_cuts

Input : conflit Kick 1 `[H/R]` vs Kick 2 `[H/R]` à 57 Hz.
Attendu :
- `primary_correction.approach = "reciprocal_cuts"` (pas sidechain)
- Deux opérations planifiées : cut léger sur chaque track dans la zone de l'autre

### Test 4 — Accumulation détectée et traitée

Input : 5 tracks simultanées dans Mud (200-500 Hz) dans Chorus 1.
Attendu :
- Diagnostic accumulation_risk généré
- Recommandation : cut sur les 2 tracks de plus basse importance TFP
- Les 3 tracks les plus importantes sont préservées

### Test 5 — JSON round-trip

Input : 20 diagnostics générés.
Action : sauvegarde JSON, puis load_diagnostics() depuis le fichier.
Attendu :
- 20 diagnostics retrouvés à l'identique
- Tous les champs préservés

### Test 6 — Filtrage par critères multiples

Input : 50 diagnostics.
Action : `filter_diagnostics(severity="critical", section="Drop 1")`.
Attendu :
- Subset correctement filtré
- Ordre préservé selon la sévérité

### Test 7 — Aucun crash sur projet sans TFP

Input : un ALS sans préfixes TFP (donc tout classifié [S/R] par défaut).
Attendu :
- Le CDE fonctionne
- Tous les diagnostics considèrent les tracks comme Support Rhythm
- Warning ajouté : "Diagnostics générés avec rôles TFP par défaut, précision limitée"

### Test 8 — Compat backward Feature 3

Input : un ALS sans Locators (pas de sections détectées).
Attendu :
- Le CDE ne crashe pas
- Les diagnostics sont générés pour "toute la durée" (section=None)
- Nombre de diagnostics potentiellement plus faible

---

## 14. Décisions techniques par défaut

1. **Le CDE ne peut pas écrire dans l'ALS.** Point final. Feature 1 est le seul module autorisé.

2. **Règles de recommandation hardcodées en v1.** Pas de système de règles versionnées avec décorateurs. Simplicité avant extensibilité.

3. **JSON comme source de vérité, Excel comme vue consultation.** Pas de base de données.

4. **Audit trail obligatoire mais simplifié.** Liste de sources + liste de règles appliquées, pas de versions.

5. **Diagnostics déterministes.** Mêmes inputs → mêmes outputs. Pas de randomness, pas de ML.

6. **Protection TFP systématique.** Aucune recommandation ne peut violer un rôle Hero sans approbation explicite.

7. **Pas de seuil configurable en v1.** Les 5 règles de protection (6.3) sont fixes. Si besoin d'ajuster, c'est une modification de code, pas de config.

8. **Les diagnostics d'une track sans WAV matchable sont skippés silencieusement.** Éviter les crashes, log un warning.

9. **Le sheet Correction Diagnostics affiche CRITICAL par défaut.** MODERATE et MINOR accessibles via le JSON ou via demande explicite à Claude.

10. **L'identifiant du diagnostic est human-readable.** Format : `<TYPE>_<SECTION>_<TRACK>_<FREQ>` ou similaire. Permet à l'utilisateur de dire "regarde CONF_DROP1_KICK1_SUBBASS_62HZ" sans passer par un UUID.

---

## 15. Dépendances

- **Feature 3 (sections Locators)** : OBLIGATOIRE ✅ livré
- **Feature 3.5 (TFP)** : OBLIGATOIRE ✅ livré
- **Feature 1 (validation + écriture)** : pas prérequis pour CDE v1, mais nécessaire pour workflow complet
- **Données des sheets existants** : `Sections Timeline`, `_track_peak_trajectories`, `_track_stereo_bands`, `_track_dynamics_time`, `AI Context`, `Anomalies`, `Freq Conflicts` — tous ✅ présents dans le rapport actuel

---

## 16. Post-CDE : ce qui vient après

### Feature 1 (API collaborative de correction)

Avec le CDE livré, Feature 1 devient le module qui :
1. Reçoit un `diagnostic_id` à appliquer
2. Vérifie une dernière fois la justification (règles de protection)
3. Crée un backup automatique de l'ALS
4. Applique la correction (écriture XML)
5. Met à jour le status du diagnostic à "applied"
6. Fournit une fonction revert

### CDE v2 (futur lointain)

- Estimation d'impact chiffrée via modèle prédictif (données accumulées)
- Règles versionnées avec decorator
- Patches réversibles granulaires (sans backup complet)
- Détecteurs étendus : phase multi-bande, crest factor par section, etc.
- Suggestions d'ajouts (ex: "ajouter un pad pour respirer dans cette section")

### Feature 2 (Q dynamique)

Intégration : les corrections CDE peuvent spécifier un Q dynamique qui varie selon l'enveloppe du conflit.

### Feature 4 (M/S)

Intégration : les diagnostics phase_issue du CDE pointent vers ms_side_cut (Feature 4).

### Feature 5 (autres devices)

Intégration : les recommandations CDE peuvent inclure des actions sur Utility (Width), Gate, Compressor, etc.

---

## Fin de la spécification Feature 3.6 v2.0
