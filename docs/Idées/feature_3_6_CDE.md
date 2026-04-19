# Feature 3.6 — Correction Diagnostic Engine (CDE)

## Référence : Mix Analyzer v3.1 / Feature 3.6 de N

---

## 1. Problème métier

Feature 1 produit `JustificationResult(justified=bool, flags=[], dynamic_mask=[])` — un verdict booléen avec des flags. C'est utile pour décider si on agit, mais insuffisant pour :

1. **Tracer la décision** : pourquoi cette correction a été choisie ? Quelles données consultées ? Quelles règles appliquées ?
2. **Comparer des alternatives** : si la correction primaire ne convient pas, qu'est-ce qu'on peut faire d'autre ?
3. **Estimer l'impact** : qu'est-ce que cette correction est censée améliorer ? De combien ?
4. **Annuler proprement** : si l'utilisateur n'aime pas, comment on revient en arrière sans casser le reste ?

Les ingénieurs de mix tiennent un journal mental ou écrit de chaque move : "j'ai cut 3 dB à 248 Hz sur Bass parce que ça masquait Pluck Lead, ratio risque/bénéfice acceptable, je peux annuler en remontant la bande à 0". Le système doit produire la même chose.

**Conséquences de l'absence du CDE :**
- Les corrections sont des boîtes noires
- Pas d'audit possible des décisions passées
- Impossible de comparer deux versions d'un mix au niveau des décisions (juste au niveau du résultat)
- L'utilisateur doit faire confiance ou tout réviser à l'oreille

---

## 2. Objectif

Pour chaque correction potentielle identifiée par le pipeline, générer un **diagnostic structuré** qui contient :

1. Le problème mesuré
2. Le contexte (TFP, section, conflits)
3. Une recommandation primaire singulière
4. Un fallback unique
5. Un impact estimé sur le Health Score
6. Un audit trail (sources + règles + version)
7. Un patch réversible

Tous les diagnostics sont stockés et accessibles. Feature 1 (justification), Feature 4 (M/S), Feature 5 (autres devices) consomment le CDE pour leurs décisions.

---

## 3. Structure d'un diagnostic

```python
@dataclass
class CorrectionDiagnostic:
    # Identification
    diagnostic_id: str                    # ex: "RES_BR_247_DROP"
    timestamp: datetime
    cde_version: str                      # ex: "1.0"

    # Problème
    track: str
    section: str | None                   # None = toute la durée
    issue_type: str                       # "resonance_buildup" | "masking_conflict" | etc.
    measurement: ProblemMeasurement       # données objectives

    # Contexte
    tfp_context: TFPContext               # extrait du TFP
    conflict_context: ConflictContext | None

    # Diagnostic textuel
    diagnosis: str                        # explication en langage naturel

    # Recommandations
    primary_correction: CorrectionRecipe
    fallback_correction: CorrectionRecipe | None

    # Impact estimé
    estimated_impact: ImpactEstimate

    # Application
    skip_in_sections: list[str]           # sections où ne pas appliquer
    application_status: str               # "proposed" | "applied" | "rejected" | "reverted"

    # Audit
    audit_trail: AuditTrail

    # Patch réversible
    patch: CorrectionPatch
```

### Sous-types

```python
@dataclass
class ProblemMeasurement:
    frequency_hz: float | None            # None pour problèmes large-bande
    peak_db: float | None
    duration_ratio_in_section: float      # 0-1
    severity_score: float                 # 0-1, normalisé

@dataclass
class TFPContext:
    track_function_in_section: str        # de Feature 3.5
    is_in_protect_zone: bool
    is_in_aggressive_cut_zone: bool
    is_in_signature_freq: bool
    max_cut_allowed_db: float             # 0 si protégé absolument

@dataclass
class ConflictContext:
    competing_tracks: list[CompetingTrack]
    masking_score: float                  # 0-1
    accumulation_count: int               # nombre de tracks à cette freq

@dataclass
class CompetingTrack:
    track_name: str
    energy_db_at_freq: float
    function_in_section: str              # leur rôle (de leur TFP)
    priority: int                         # leur sidechain_priority

@dataclass
class CorrectionRecipe:
    device: str                           # ex: "EQ8 — Peak Resonance"
    approach: str                         # "dynamic_cut" | "static_dip" | "surgical_notch" | etc.
    parameters: dict                      # freq, gain, Q, mode, trigger
    rationale: str                        # pourquoi cette approche
    applies_to_sections: list[str]        # sections où la correction agit

@dataclass
class ImpactEstimate:
    health_score_delta_qualitative: str   # "minor improvement" | "moderate" | "significant"
    health_score_delta_range: tuple[float, float] | None  # (+1, +3) si quantitatif
    affected_categories: list[str]        # "Spectral Balance", "Dynamics", etc.
    perceptual_description: str           # langage naturel
    risks: list[str]                      # effets secondaires possibles

@dataclass
class AuditTrail:
    data_sources: list[str]               # sheets Excel + sections + TFP
    decision_rules_applied: list[RuleApplication]
    cde_version: str

@dataclass
class RuleApplication:
    rule_id: str                          # ex: "protection_zone_check"
    rule_version: str                     # ex: "1.2"
    inputs: dict                          # ce qui a été passé à la règle
    output: str                           # le verdict de la règle

@dataclass
class CorrectionPatch:
    """Représente une modification réversible du .als."""
    target_track: str
    target_device: str | None             # None = device à créer
    operations: list[PatchOperation]      # ce qu'on applique
    inverse_operations: list[PatchOperation]  # ce qui annule

@dataclass
class PatchOperation:
    op_type: str                          # "create_device" | "set_param" | "write_envelope"
    target_path: str                      # XPath dans le XML
    new_value: any
    old_value: any                        # pour réversibilité
```

---

## 4. Génération de diagnostics

### Pipeline de génération

```
INPUT : .als + report Excel + sections (F3) + TFP (F3.5)

POUR chaque track :
  POUR chaque section où la track est active :

    # Détecter les problèmes potentiels
    problems = []
    problems += detect_resonance_buildups(track, section, peak_trajectories)
    problems += detect_masking_conflicts(track, section, copresence)
    problems += detect_accumulation_risks(track, section, copresence)
    problems += detect_phase_issues(track, section, stereo_bands)
    problems += detect_dynamic_imbalance(track, section, dynamics_time)

    POUR chaque problème :
      diag = generate_diagnostic(problem, track, section, tfp, context)

      Si diag.tfp_context.max_cut_allowed_db == 0 :
        diag.application_status = "rejected"
        diag.diagnosis += " — protected by TFP, skipped"
      Sinon :
        diag.application_status = "proposed"
        diag.primary_correction = compute_primary(problem, tfp, context)
        diag.fallback_correction = compute_fallback(problem, tfp, context)
        diag.estimated_impact = estimate_impact(problem, primary)
        diag.patch = build_patch(diag.primary_correction)
```

### Détection des problèmes

Chaque type de problème a son détecteur :

```python
def detect_resonance_buildups(track, section, peak_trajectories) -> list[ProblemMeasurement]:
    """Peaks persistants qui dépassent le spectre moyen."""

def detect_masking_conflicts(track, section, copresence) -> list[ProblemMeasurement]:
    """Zones où la track masque (ou est masquée par) une autre."""

def detect_accumulation_risks(track, section, copresence) -> list[ProblemMeasurement]:
    """Fréquences où 4+ tracks ont de l'énergie simultanément."""

def detect_phase_issues(track, section, stereo_bands) -> list[ProblemMeasurement]:
    """Bandes avec corrélation de phase < 0."""

def detect_dynamic_imbalance(track, section, dynamics_time) -> list[ProblemMeasurement]:
    """Crest factor anormal pour le rôle de la track."""
```

### Logique de recommandation primaire

Pour chaque problème, choisir UNE approche selon des règles documentées :

```
SI issue_type == "resonance_buildup" :
  SI tfp.is_in_signature_freq :
    → static_dip Q=2 max -2 dB (correction minimale, préserver le caractère)
  SINON SI conflict.masking_score > 0.7 :
    → dynamic_cut Q=10 trigger="amp > -3 dB" (chirurgical, conditionnel)
  SINON SI tfp.is_in_aggressive_cut_zone :
    → surgical_notch Q=12 (cut net autorisé)
  SINON :
    → musical_dip Q=4 (cut musical, préserve)

SI issue_type == "masking_conflict" :
  SI les deux tracks sont hero (TFP) :
    → reciprocal_cuts (cut chacune dans la zone de l'autre)
  SINON :
    → cut sur la track de plus basse fonction (loser_takes_cut)

SI issue_type == "accumulation_risk" :
  → cut sur les N-3 tracks de plus basse priorité
  (garder les 3 plus prioritaires intactes)

SI issue_type == "phase_issue" :
  → ms_side_cut dans la bande problématique

SI issue_type == "dynamic_imbalance" :
  → adaptive_compression OU section_aware_gain
```

### Logique de fallback

Le fallback est toujours **plus conservateur** que la primaire :

```
SI primary == dynamic_cut :
  → fallback = static_dip (moins agressif, plus prévisible)

SI primary == surgical_notch :
  → fallback = musical_dip (plus large, moins chirurgical)

SI primary == reciprocal_cuts :
  → fallback = cut sur une seule des deux (moins disruptif)

SI primary == ms_side_cut :
  → fallback = stereo_cut (touche tout le signal mais simpler)
```

---

## 5. Estimation d'impact

### Approche v1.0 : qualitatif avec ranges

Pas de modèle prédictif validé encore. On utilise des **estimations qualitatives** basées sur des heuristiques :

```python
def estimate_impact(problem: ProblemMeasurement, correction: CorrectionRecipe) -> ImpactEstimate:
    affected_categories = []
    qualitative = "minor"

    if problem.issue_type == "resonance_buildup":
        affected_categories.append("Spectral Balance")
        if problem.severity_score > 0.7:
            qualitative = "moderate"
        if correction.approach == "surgical_notch":
            qualitative = "significant"

    if problem.issue_type == "masking_conflict":
        affected_categories.append("Spectral Balance")
        affected_categories.append("Loudness")  # peut affecter perceived loudness

    # Range conservateur
    range_map = {
        "minor": (0, 2),
        "moderate": (2, 4),
        "significant": (4, 7)
    }
    health_score_delta_range = range_map[qualitative]

    return ImpactEstimate(
        health_score_delta_qualitative=qualitative,
        health_score_delta_range=health_score_delta_range,
        affected_categories=affected_categories,
        perceptual_description=generate_perceptual_description(...),
        risks=identify_risks(correction, tfp_context),
    )
```

### Approche v2.0 (futur) : modèle prédictif

Accumuler les données : pour chaque correction appliquée, mesurer le delta réel du Health Score (run Mix Analyzer avant/après). Construire un modèle de régression. Remplacer les heuristiques.

---

## 6. Système de règles versionnées

Chaque règle est nommée et versionnée :

```python
RULES_REGISTRY = {
    "protection_zone_check": {
        "version": "1.0",
        "description": "Vérifie si la freq cible est dans tfp.protect_freqs",
        "function": check_protection_zone,
    },
    "masking_severity": {
        "version": "1.1",
        "description": "Calcule le score de masking entre 2 tracks dans une zone",
        "function": compute_masking_score,
    },
    "loser_takes_cut": {
        "version": "1.0",
        "description": "Identifie quelle track de la paire reçoit le cut",
        "function": determine_loser,
    },
    # ... etc
}
```

Quand une règle est appliquée à un diagnostic, on enregistre :
- Le rule_id
- La version utilisée
- Les inputs
- Le verdict

Permet de :
- Reproduire un diagnostic sur une version antérieure du système
- Détecter les régressions quand on update une règle
- Auditer "pourquoi cette décision a changé entre les versions"

---

## 7. Patches réversibles

Chaque diagnostic génère un patch avec ses opérations + leurs inverses :

```python
patch = CorrectionPatch(
    target_track="Bass Rythm",
    target_device="EQ8 — Peak Resonance",
    operations=[
        PatchOperation(
            op_type="set_param",
            target_path="//Track[@Name='Bass Rythm']/Devices/EQ8[@Name='Peak Resonance']/Bands/Band[1]/Gain",
            new_value=-4.5,
            old_value=0.0,
        ),
        PatchOperation(
            op_type="write_envelope",
            target_path="//Track[@Name='Bass Rythm']/AutomationEnvelopes/Envelope[@PointeeId='12345']",
            new_value="<envelope_xml>...</envelope_xml>",
            old_value=None,  # pas d'envelope avant
        ),
    ],
    inverse_operations=[
        PatchOperation(
            op_type="set_param",
            target_path="...",
            new_value=0.0,
            old_value=-4.5,
        ),
        PatchOperation(
            op_type="delete_envelope",
            target_path="...",
            new_value=None,
            old_value="<envelope_xml>...</envelope_xml>",
        ),
    ],
)
```

API d'application/réversion :

```python
def apply_diagnostic(diag: CorrectionDiagnostic, als_path: Path) -> ApplicationResult:
    """Applique le patch primaire ou fallback."""

def revert_diagnostic(diag_id: str, als_path: Path) -> RevertResult:
    """Annule un diagnostic appliqué en exécutant ses inverse_operations."""

def list_applied_diagnostics(als_path: Path) -> list[CorrectionDiagnostic]:
    """Liste tous les diagnostics appliqués sur un .als."""
```

---

## 8. Stockage

### Fichier JSON par projet

`<projet>_diagnostics.json` à côté du `.als` :

```json
{
  "project": "Acid Drops",
  "cde_version": "1.0",
  "generated_at": "2026-04-18T16:35:00",
  "diagnostics": [
    {
      "diagnostic_id": "RES_BR_247_DROP",
      "track": "Bass Rythm",
      "section": "DROP",
      "issue_type": "resonance_buildup",
      // ... tout le contenu du dataclass sérialisé
    },
    // ... autres diagnostics
  ]
}
```

### Sheet Excel `_correction_diagnostics`

Pour visualisation rapide :

| ID | Track | Section | Issue | Severity | Primary | Status | Impact |
|---|---|---|---|---|---|---|---|
| RES_BR_247_DROP | Bass Rythm | DROP | resonance_buildup | 0.85 | dynamic_cut Q=10 -4.5 dB | proposed | Spectral +2-4 |
| MSK_KB_AB_DROP | Kick 1 ↔ Acid Bass | DROP | masking_conflict | 0.82 | reciprocal_cuts | applied | Spectral +3-5 |

---

## 9. Intégration avec autres features

### Feature 1 (refactor)

```python
def evaluate_justification(...) -> JustificationResult:
    """Devient un wrapper autour de CDE."""
    diag = cde.generate_diagnostic(...)
    return JustificationResult(
        justified=(diag.application_status == "proposed"),
        flags=[r.rule_id for r in diag.audit_trail.decision_rules_applied],
        dynamic_mask=compute_dynamic_mask_from_diagnostic(diag),
        explanation=diag.diagnosis,
    )
```

### Feature 4 (M/S) et Feature 5 (devices)

Chaque write_* device consulte CDE pour son diagnostic :

```python
def write_ms_side_cut(...):
    diag = cde.generate_diagnostic(
        track=track_id,
        issue_type="phase_issue",
        ...
    )
    if diag.application_status != "proposed":
        return AutomationReport(success=False, warnings=[diag.diagnosis])

    # Appliquer le patch
    return cde.apply_diagnostic(diag, als_path)
```

---

## 10. Tests d'acceptance

### Test 1 — Diagnostic généré pour résonance simple
- Bass Rythm, peak 247 Hz, +9 dB, 85% du DROP
- **Attendu :** diagnostic avec primary=`dynamic_cut Q=10 -4.5 dB`, fallback=`static_dip -2 dB`

### Test 2 — Protection TFP respectée
- Bass Rythm avec `protect_freqs: [{freq: 127, max_cut: -1}]`
- Détection peak à 127 Hz
- **Attendu :** diagnostic généré avec `application_status="rejected"` ET diagnosis explique le skip

### Test 3 — Audit trail complet
- Diagnostic généré
- **Attendu :** `audit_trail.data_sources` liste les sheets consultés, `decision_rules_applied` liste 3+ règles avec versions

### Test 4 — Patch réversible
- Appliquer un diagnostic
- Revert
- **Attendu :** le `.als` post-revert est byte-identique au `.als` pré-application

### Test 5 — Estimation d'impact cohérente
- Diagnostic résolution_buildup severity=0.5
- **Attendu :** qualitative="moderate", range=(2,4), categories=["Spectral Balance"]

### Test 6 — Versioning des règles
- Génération d'un diagnostic avec rule "loser_takes_cut" v1.0
- Mise à jour de la règle vers v1.1
- Re-génération du même diagnostic
- **Attendu :** nouveau diagnostic note v1.1, ancien diagnostic toujours accessible avec v1.0

### Test 7 — Intégration Feature 1
- evaluate_justification() appelée
- **Attendu :** retourne un JustificationResult équivalent au comportement précédent (rétro-compatibilité)

---

## 11. Dépendances

- **Feature 3 (sections)** : OBLIGATOIRE
- **Feature 3.5 (TFP)** : OBLIGATOIRE
- **Feature 1** : sera refactorisé pour consommer CDE
- **`_track_peak_trajectories`, `_track_zone_energy`, `_track_copresence`, `_track_stereo_bands`, `_track_dynamics_time`** : sources des problèmes détectés

---

## 12. Plan de développement

### Phase A — Détecteurs de problèmes
- Module `problem_detectors.py`
- 5 détecteurs (resonance, masking, accumulation, phase, dynamics)
- Tests : Acid Drops doit produire les problèmes connus

### Phase B — Logique de recommandation
- Module `recommendation_engine.py`
- Tables de règles primary/fallback par issue_type
- Tests : Test 1

### Phase C — Estimation d'impact (qualitatif)
- Module `impact_estimator.py`
- Heuristiques v1.0
- Tests : Test 5

### Phase D — Système de règles versionnées
- Module `rules_registry.py`
- Décorateur @rule(name, version)
- Tests : Test 6

### Phase E — Patches réversibles
- Module `correction_patch.py`
- apply_diagnostic, revert_diagnostic, list_applied
- Tests : Test 4

### Phase F — Stockage et visualisation
- JSON I/O
- Sheet Excel
- Tests : sérialisation/désérialisation round-trip

### Phase G — Intégration Feature 1
- Refactor de evaluate_justification
- Tests : Test 7

---

## 13. Décisions techniques par défaut

1. **Recommandation primaire singulière, pas un buffet** : choix clair, alternative seule en fallback. Évite la paralysie d'analyse.

2. **Impact qualitatif d'abord, quantitatif plus tard** : pas de chiffres inventés. Ranges conservateurs basés sur sévérité.

3. **Audit trail obligatoire** : chaque diagnostic doit pouvoir être expliqué et reproduit.

4. **Patches réversibles obligatoires** : zéro modification non-réversible. L'utilisateur doit toujours pouvoir annuler.

5. **JSON pour la sérialisation** : pas YAML ici (pas édité à la main, contient des données sérialisées).

6. **CDE est le moteur, Feature 1 est l'orchestrateur** : Feature 1 ne devient pas obsolète, elle se simplifie en consumer de CDE.

7. **Versioning explicite des règles** : essentiel pour reproductibilité et audit longitudinal.
