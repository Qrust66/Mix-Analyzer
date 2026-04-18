# Feature 1 — Correction conditionnelle

## Référence : Mix Analyzer v3.1 / Feature 1 de 6

---

## 1. Problème métier

Le système actuel applique des corrections spectrales (notches, HPF, LPF, boosts) dès qu'un symptôme est détecté : un peak de résonance → notch, de l'énergie sous le rolloff → HPF, etc. Il ne vérifie jamais si la correction est musicalement justifiée.

**Conséquences mesurées sur Acid Drops :**
- Le 248 Hz de l'Acid Bass serait coupé alors que c'est la fondamentale du son acid — le character du patch.
- Des HPF seraient appliqués sur des tracks dont le contenu basse fréquence ne dérange personne (guitare dans l'intro sans kick).
- Des notches seraient appliqués sur des résonances qui font partie de l'esthétique industrielle (distortion, saturation).

Un ingénieur de mix ne fait jamais ça. Il écoute le contexte avant de couper. Le système doit faire pareil.

---

## 2. Objectif

Chaque fonction `write_*` dans `eq8_automation.py` doit vérifier si la correction est justifiée AVANT d'écrire dans le `.als`. Si la correction n'est pas justifiée, la fonction retourne un rapport explicatif sans rien écrire.

La justification repose sur des critères mesurables, pas sur du jugement subjectif. Les seuils sont calibrés par genre et type de track via `genre_profiles.json`.

---

## 3. Critères de justification

Une correction est justifiée si AU MOINS UN des critères suivants est rempli :

### Critère A — Masking actif

Le contenu ciblé par la correction est en conflit fréquentiel avec une ou plusieurs autres tracks au même moment.

**Mesure :** score de masking entre la track corrigée et chaque autre track, dans la bande fréquentielle concernée, par bucket temporel. Un masking_score > seuil (défini par genre × track_type) déclenche la justification.

**Exemple :** Toms Rack 248 Hz masque Acid Bass 248 Hz dans le drop (score 0.65 > seuil 0.5 pour Drums/Tom en Industrial) → correction justifiée.

**Contre-exemple :** Acid Bass 248 Hz ne masque personne dans l'intro (kick absent) → correction NON justifiée dans cette section.

### Critère B — Peak isolé extrême

Le peak dépasse significativement le spectre moyen de sa propre track. Même sans masking, une résonance extrême fatigue l'oreille et réduit le headroom.

**Mesure :** amplitude du peak en dB MOINS la moyenne spectrale de la track dans un voisinage de ±1 octave. Si le delta dépasse le seuil (ex: 8 dB pour Drums en Industrial, 6 dB pour Pad, 10 dB pour Bass), le peak est considéré extrême.

**Exemple :** Toms Rack a un room mode à 180 Hz qui dépasse le spectre moyen de +11 dB → correction justifiée même sans masking.

**Contre-exemple :** Acid Bass 248 Hz est +5 dB au-dessus de la moyenne (seuil Bass Industrial = 10 dB) → la fondamentale est naturellement proéminente, pas un problème.

### Critère C — Accumulation multi-track

Plusieurs tracks (4+) ont de l'énergie significative à la même fréquence au même moment. Individuellement aucune paire ne se masque, mais le cumul dans le full mix crée du mud.

**Mesure :** compter les tracks dont l'énergie dans la bande ciblée est > -30 dB au même bucket temporel. Si le compte dépasse le seuil d'accumulation (ex: 4 tracks), la correction est justifiée sur les tracks les MOINS prioritaires (selon le genre_profiles : kick et bass sont prioritaires, pads et textures sont sacrifiables).

**Exemple :** 248 Hz a de l'énergie sur Acid Bass, Toms Rack, ARP Glitter Box, Xylo Texture, Guitar Distorted, Roaming — 6 tracks. Acid Bass et Guitar sont prioritaires. Le notch s'applique sur ARP Glitter, Xylo, Roaming (les moins prioritaires).

### Critère D — Contenu inaudible

Le contenu ciblé est sous le seuil d'audibilité dans le contexte du mix. Couper du bruit de plancher est toujours justifié — ça ne retire rien de musical.

**Mesure :** énergie dans la bande < -60 dB en permanence (pas juste un bucket) → correction statique OK.

**Ce critère justifie les safety HPF et les LPF sur du bruit.** Il ne justifie PAS un HPF sur du contenu à -35 dB qui ne masque personne.

---

## 4. Cascade de décision

```
ENTRÉE : track, fréquence/zone ciblée, type de correction, features

ÉTAPE 1 — Audibilité (déjà implémenté)
  is_audible == False → skip ce bucket
  
ÉTAPE 2 — Contenu présent ?
  énergie dans la zone < content_threshold (-60 dB)
    → Correction statique autorisée (coupe du bruit)
    → Flag: "static_noise_removal"
    → FIN

ÉTAPE 3 — Masking ?
  Pour chaque autre track jouant au même moment :
    masking_score dans la zone > masking_threshold du genre/track_type ?
    → Oui : correction dynamique justifiée
    → Flag: "masking_conflict" + nom de la track conflictuelle
    
ÉTAPE 4 — Peak isolé extrême ?
  peak_amplitude - mean_spectrum > isolated_threshold du genre/track_type ?
    → Oui : correction dynamique justifiée
    → Flag: "extreme_isolated_peak"

ÉTAPE 5 — Accumulation ?
  Nombre de tracks avec énergie > -30 dB à cette freq > accumulation_threshold ?
    → Oui ET la track courante est basse priorité : correction justifiée
    → Oui MAIS la track courante est haute priorité : skip (corriger les autres)
    → Flag: "multi_track_accumulation"

ÉTAPE 6 — Aucun critère rempli
    → Pas de correction
    → Retourner AutomationReport(success=False, warnings=["..."])
```

---

## 5. Structure de données

### CorrectionContext (nouveau dataclass)

```python
@dataclass
class CorrectionContext:
    """Contexte du mix pour décider si une correction est justifiée."""
    
    # Audibilité de la track (déjà implémenté)
    is_audible: np.ndarray                # bool[64] par bucket temporel
    
    # Énergie dans la zone ciblée
    zone_energy: np.ndarray               # dB[64] pour la zone concernée
    content_threshold_db: float           # en-dessous = bruit (défaut: -60)
    
    # Masking — énergie des AUTRES tracks dans la même zone
    other_tracks_energy: dict[str, np.ndarray]  # {track_name: dB[64]}
    masking_threshold: float              # score min pour justifier (depuis genre_profiles)
    
    # Spectre moyen de la track (pour peaks isolés)
    track_mean_spectrum: np.ndarray | None  # dB[freq_bins] moyenné sur la durée
    isolated_threshold_db: float          # dépassement min (depuis genre_profiles)
    
    # Accumulation
    tracks_active_count: np.ndarray | None  # int[64] nombre de tracks avec énergie > -30 dB
    accumulation_threshold: int           # min tracks pour justifier (défaut: 4)
    track_priority: int                   # priorité de cette track (1=haute kick/bass, 5=basse noise/pad)
    
    # Contrôle
    require_justification: bool           # True = vérifie, False = rétro-compatible
```

### JustificationResult (nouveau dataclass)

```python
@dataclass
class JustificationResult:
    """Résultat de l'évaluation de justification."""
    
    justified: bool
    flags: list[str]          # ex: ["masking_conflict:Sub Bass", "extreme_isolated_peak"]
    severity: float           # 0.0 à 1.0, combine les scores des critères remplis
    dynamic_mask: np.ndarray  # bool[64] — True = corriger ce bucket, False = laisser
    explanation: str          # texte lisible pour le rapport
```

Le `dynamic_mask` est la pièce clé : au lieu de corriger uniformément sur toute la durée, la correction s'applique seulement aux buckets où elle est justifiée. Le HPF sur la guitare s'active dans le drop (masking avec kick) et se désactive dans l'intro (pas de conflit).

---

## 6. Fonctions impactées

### Nouveau module : `correction_logic.py`

```python
def evaluate_justification(
    track_name: str,
    track_type: str,
    correction_type: str,        # "hpf", "lpf", "notch", "bell_cut", "boost"
    target_freq_hz: float,
    context: CorrectionContext,
    genre_profile: dict,
) -> JustificationResult:
    """Évalue si une correction est justifiée selon la cascade de critères."""

def build_correction_context(
    track_name: str,
    report_path: Path,           # rapport Excel Mix Analyzer
    als_path: Path,              # pour l'automation_map
    genre: str,
    target_zone: str,            # "sub", "low", "mud", "mid", etc.
) -> CorrectionContext:
    """Construit le CorrectionContext pour une track depuis le rapport Excel."""

def compute_masking_score(
    track_a_energy: np.ndarray,  # dB[64]
    track_b_energy: np.ndarray,  # dB[64]
) -> np.ndarray:
    """Score de masking frame par frame entre deux tracks dans une zone."""

def get_track_priority(
    track_type: str,
    genre_profile: dict,
) -> int:
    """Retourne la priorité de la track (1=kick/bass, 5=noise/pad)."""
```

### Modifications à `eq8_automation.py`

Chaque fonction `write_*` reçoit un paramètre optionnel `context: CorrectionContext = None` :

- Si `context is None` → comportement actuel (rétro-compatible)
- Si `context is not None` et `context.require_justification == True` → appelle `evaluate_justification()` avant d'écrire
- Si `justified == False` → retourne `AutomationReport(success=False, warnings=[explanation])`
- Si `justified == True` → utilise `dynamic_mask` pour ne corriger que les buckets justifiés, et scale la réduction par `severity`

**Fonctions concernées :**
- `write_adaptive_hpf()` — HPF seulement si masking ou bruit
- `write_adaptive_lpf()` — LPF seulement si masking ou bruit
- `write_safety_hpf()` — OK tel quel (critère D = bruit de plancher)
- `write_dynamic_notch()` — notch seulement si masking, peak extrême, ou accumulation
- `write_dynamic_bell_cut()` — idem
- `write_resonance_suppression()` — filtre les peaks non-justifiés avant traitement
- `write_adaptive_presence_boost()` — boost seulement si le full mix manque de présence
- `write_adaptive_air_boost()` — boost seulement si le full mix manque d'air
- `write_masking_reciprocal_cuts()` — déjà basé sur masking, pas de changement majeur
- `write_targeted_sidechain_eq()` — idem
- `write_transient_aware_cut()` — vérifier que le cut sous-jacent est justifié
- `write_section_aware_eq()` — intègre naturellement le contexte section
- `write_dynamic_deesser()` — justifié si sibilance masque d'autres éléments ou est extrême
- `write_spectral_match()` — justifié si le full mix a un déficit mesurable

---

## 7. Intégration avec genre_profiles.json

Nouveaux champs à ajouter par track_type dans chaque style :

```json
{
  "Kick": {
    "hpf_max_hz": 30,
    "resonance_reduction_max_db": -3.0,
    "masking_tolerance": 0.7,
    "isolated_peak_threshold_db": 10,
    "content_threshold_db": -55,
    "priority": 1,
    "notes": "..."
  },
  "Pad/Drone": {
    "masking_tolerance": 0.3,
    "isolated_peak_threshold_db": 6,
    "content_threshold_db": -50,
    "priority": 4,
    "notes": "..."
  }
}
```

Les champs `masking_tolerance` et `resonance_reduction_max_db` existent déjà. On ajoute `isolated_peak_threshold_db`, `content_threshold_db`, et `priority`.

---

## 8. Données nécessaires

| Donnée | Source | Disponible ? |
|---|---|---|
| Zone energy par track × 64 buckets | `_track_zone_energy` | ✅ |
| Peak trajectories | `_track_peak_trajectories` | ✅ |
| Spectre moyen par track | `_track_spectra` (v2.4) | ✅ |
| Audibilité | `_track_automation_map` → `is_audible` | ✅ |
| Liste des tracks actives par bucket | Calculable depuis `_track_zone_energy` | Nouveau calcul |
| Masking scores par paire × zone | `detect_masking()` | ✅ (fonction existe) |
| Profil genre × track_type | `genre_profiles.json` | ✅ |

**Aucune nouvelle analyse audio nécessaire.** Tout est dans le rapport Excel existant.

---

## 9. Tests d'acceptance

### Test 1 — Peak non-justifié → skip
- Track : Acid Bass, peak 248 Hz
- Masking score avec toutes les autres tracks < seuil
- Peak delta vs mean = +5 dB (seuil Bass Industrial = 10 dB)
- Accumulation = 6 tracks mais Acid Bass est priorité 1
- **Attendu :** `JustificationResult(justified=False, explanation="peak 248 Hz: no masking conflict, below isolated threshold, high priority track")`

### Test 2 — Peak justifié par masking → correction dynamique
- Track : Toms Rack, peak 248 Hz
- Masking score avec Acid Bass = 0.65 (seuil Drums Industrial = 0.5)
- **Attendu :** `JustificationResult(justified=True, flags=["masking_conflict:Acid Bass"], severity=0.65, dynamic_mask=[..True dans le drop, False dans l'intro..])`

### Test 3 — HPF justifié par bruit
- Track : ARP Glitter Box, sub energy < -60 dB permanent
- **Attendu :** correction statique, flag "static_noise_removal"

### Test 4 — HPF NON justifié
- Track : Guitar Distorted dans l'intro, sub energy = -35 dB, pas de masking
- **Attendu :** skip, explanation "sub content present but no conflict"

### Test 5 — HPF dynamique par section
- Track : Guitar Distorted dans le drop, sub energy = -35 dB, masking avec Kick = 0.55
- **Attendu :** HPF actif dans le drop, inactif dans l'intro. `dynamic_mask` reflète ça.

### Test 6 — Accumulation → correction sur basse priorité
- 248 Hz : énergie sur 6 tracks simultanément
- Acid Bass (priorité 1), Kick (priorité 1), Toms Rack (priorité 2), ARP Glitter (priorité 3), Xylo (priorité 4), Roaming (priorité 4)
- **Attendu :** correction sur ARP Glitter, Xylo, Roaming. Skip sur Acid Bass, Kick, Toms Rack.

### Test 7 — Rétro-compatibilité
- `context=None` → comportement identique à avant, aucune vérification
- `context.require_justification=False` → idem

---

## 10. Hors scope

- La détection de sections (Feature 3 séparée) — ici on utilise les buckets temporels existants
- Le Q dynamique (Feature 2 séparée)
- L'EQ M/S (Feature 5 séparée)
- L'UI de l'orchestrateur — cette feature est API seulement
- Le calcul du masking lui-même — `detect_masking()` existe déjà, on le consomme

---

## 11. Plan de développement

### Phase A — correction_logic.py + CorrectionContext
- Nouveau module avec `evaluate_justification()`, `build_correction_context()`, `compute_masking_score()`
- Dataclasses `CorrectionContext` et `JustificationResult`
- Tests unitaires sur les 7 cas d'acceptance

### Phase B — Intégration dans eq8_automation.py
- Ajouter `context: CorrectionContext = None` à toutes les fonctions `write_*`
- Brancher `evaluate_justification()` au début de chaque fonction
- Tests d'intégration : write_dynamic_notch avec context justifié vs non-justifié

### Phase C — Mise à jour genre_profiles.json
- Ajouter `isolated_peak_threshold_db`, `content_threshold_db`, `priority` à chaque track_type
- Valider les seuils sur Acid Drops (les résultats doivent matcher le tableau de la section 3)

### Phase D — build_correction_context depuis le rapport Excel
- `mix_context.py` ou intégré dans `correction_logic.py`
- Lit les sheets v2.5 + automation_map
- Construit le CorrectionContext complet pour chaque track
- Test : context pour Acid Bass doit retourner priority=1, masking scores réels
