# Feature 2 — Q dynamique

## Référence : Mix Analyzer v3.1 / Feature 2 de 6

---

## 1. Problème métier

Le Q (facteur de qualité / largeur de bande) des corrections EQ8 est actuellement fixe. Un notch à Q=8 coupe un trou étroit identique du début à la fin, peu importe que le peak soit étroit ou large à un moment donné.

**Conséquences audibles :**
- Un notch trop étroit rate une résonance qui s'élargit dans les sections denses.
- Un notch trop large coupe du contenu musical utile autour de la fréquence ciblée.
- Le résultat sonne "artificiel" — l'oreille humaine détecte les corrections statiques dans un contexte dynamique.

Un ingénieur ajuste le Q en continu pendant le mix. Le Q serré pour un peak chirurgical, large pour un nettoyage global, et il varie selon les sections.

---

## 2. Objectif

Chaque correction EQ8 qui écrit des automations Freq et Gain doit aussi écrire une automation Q quand c'est pertinent. Le Q s'adapte à la largeur du phénomène corrigé — peak étroit → Q serré, zone de mud large → Q large, et le Q peut varier dans le temps.

---

## 3. Règles de calcul du Q

### Pour les notches (peaks de résonance)

Le Q est inversement proportionnel à la largeur du peak :

```
peak_bandwidth_hz = fréquence où l'amplitude du peak tombe de 3 dB de chaque côté
Q = freq_center / peak_bandwidth_hz
```

Si le peak fait 30 Hz de large à 248 Hz → Q = 248/30 = 8.3
Si le peak fait 80 Hz de large à 248 Hz → Q = 248/80 = 3.1

**Limites :** clampé entre Q_min (0.5) et Q_max (18.0) selon les capacités de l'EQ8.

**Variation temporelle :** le peak peut s'élargir dans les sections denses (plus d'harmoniques) et se resserrer dans les sections calmes. Le Q suit.

### Pour les bell cuts (zone energy)

Le Q est proportionnel à la précision de la correction souhaitée :

| Contexte | Q |
|---|---|
| Masking chirurgical (conflit étroit entre 2 tracks) | 6–12 |
| Nettoyage de zone (mud 200-500 Hz) | 1–3 |
| Présence/air boost | 0.5–1.5 |
| De-essing | 4–8 |

Le Q peut varier si la largeur du conflit change dans le temps.

### Pour les filtres (HPF/LPF)

Le Q des filtres LC48/HC48 contrôle la résonance au point de coupure. Généralement fixe à 0.71 (Butterworth, pas de résonance). Pas d'automation Q sauf cas créatif spécifique. **Q fixe = pas de troisième envelope pour les filtres.**

---

## 4. Source des données pour le calcul

### Largeur de peak

Déjà mesurable depuis la matrice CQT transitoire (dans `spectral_evolution.py`). Pour chaque frame où un peak est détecté, on peut calculer la largeur à -3 dB en comptant les bins CQT adjacents au-dessus de (peak_amplitude - 3 dB).

**Nouvelle feature à extraire :** `peak_bandwidth_hz` par point de trajectoire. Stocké dans `_track_peak_trajectories` en colonne supplémentaire.

### Largeur de conflit de masking

Calculable depuis `detect_masking()` — au lieu de retourner juste un score par zone, retourner aussi la sous-bande précise du conflit. Le Q est calculé depuis la largeur du conflit.

---

## 5. Modifications

### spectral_evolution.py

`extract_peak_trajectories()` retourne actuellement des points `(frame_idx, freq_hz, amplitude_db)`. Ajouter un 4e champ : `bandwidth_hz`.

```python
# Actuel
PeakPoint = (frame_idx, freq_hz, amplitude_db)

# Nouveau
PeakPoint = (frame_idx, freq_hz, amplitude_db, bandwidth_hz)
```

**Calcul du bandwidth :** dans la matrice CQT, pour chaque peak détecté, chercher les bins adjacents dont l'amplitude est > (peak_amplitude - 3 dB). La distance en Hz entre le bin le plus bas et le plus haut donne le bandwidth.

### feature_storage.py

`_track_peak_trajectories` passe de 6 colonnes à 7 (ajout `bandwidth_hz`).

### eq8_automation.py

Toutes les fonctions qui écrivent Freq + Gain écrivent aussi Q :

**`write_dynamic_notch()`** :
```python
# Calculer Q depuis le bandwidth du peak
q_values = freq_values / bandwidth_values  # Q = f/bw par frame
q_values = np.clip(q_values, 0.5, 18.0)

# Écrire 3 envelopes
write_automation_envelope(tree, track, freq_target_id, freq_breakpoints)
write_automation_envelope(tree, track, gain_target_id, gain_breakpoints)
write_automation_envelope(tree, track, q_target_id, q_breakpoints)      # NOUVEAU
```

**`write_dynamic_bell_cut()`** :
- Q calculé depuis la largeur du conflit de masking si `CorrectionContext` est fourni
- Sinon Q par défaut depuis `genre_profiles.json`

**`write_resonance_suppression()`** :
- Q par peak, basé sur le bandwidth de chaque peak

**`write_adaptive_presence_boost()`**, **`write_adaptive_air_boost()`** :
- Q fixe (0.8–1.5), pas d'automation. Le boost est large par nature.

**`write_dynamic_deesser()`** :
- Q adaptatif basé sur la largeur de la sibilance (varie entre tracks et sections)

---

## 6. Contrainte technique EQ8

Le mapping JSON confirme :
```json
"Q": {
    "transform_kind": "direct",
    "range_xml": [0.1, 18.0]
}
```

Les automations Q utilisent la valeur Q brute. Pas de conversion nécessaire. Le Q dans le XML = le Q affiché dans Ableton.

**Attention :** la résolution de l'automation Q dans Ableton est continue mais l'oreille humaine ne distingue pas des changements de Q < 0.5. Limiter le taux de changement du Q pour éviter des artefacts (pas plus de 2 unités de Q par seconde).

---

## 7. Tests d'acceptance

### Test 1 — Peak étroit → Q serré
- Peak à 248 Hz, bandwidth 25 Hz
- **Attendu :** Q = 248/25 = 9.9, clampé à 9.9

### Test 2 — Peak large → Q large
- Peak à 248 Hz, bandwidth 100 Hz
- **Attendu :** Q = 248/100 = 2.5

### Test 3 — Q varie dans le temps
- Peak dont le bandwidth passe de 30 Hz (intro) à 80 Hz (drop)
- **Attendu :** Q passe de 8.3 à 3.1, automation Q non constante

### Test 4 — Q clampé aux limites
- Bandwidth très étroit (5 Hz) → Q = 49.6 → clampé à 18.0
- Bandwidth très large (500 Hz) → Q = 0.5 → clampé à 0.5

### Test 5 — Pas d'automation Q sur les filtres
- `write_adaptive_hpf()` ne doit PAS écrire d'envelope Q
- Band en mode LC48 → Q fixe

### Test 6 — Rétro-compatibilité
- Si `bandwidth_hz` absent des peak trajectories (ancien format) → Q fixe par défaut (8.0 pour notch, 1.0 pour bell)

---

## 8. Dépendances

- **Feature 1 (correction conditionnelle)** : indépendant. Le Q dynamique peut être implémenté avant ou après. Si Feature 1 est présent, le Q s'adapte aussi au `dynamic_mask`.
- **spectral_evolution.py** : modification de `extract_peak_trajectories()` pour ajouter `bandwidth_hz`.
- **genre_profiles.json** : pas de nouveau champ nécessaire. Le Q est calculé, pas configuré.

---

## 9. Plan de développement

### Phase A — Bandwidth dans les peak trajectories
- Modifier `extract_peak_trajectories()` dans `spectral_evolution.py`
- Ajouter la colonne `bandwidth_hz` dans `feature_storage.py`
- Tests : vérifier que le bandwidth d'un sinus pur est très étroit (~2 bins CQT)

### Phase B — Q dynamique dans eq8_automation.py
- Modifier `write_dynamic_notch()` pour écrire 3 envelopes
- Modifier `write_resonance_suppression()` idem
- Modifier `write_dynamic_bell_cut()` et `write_dynamic_deesser()`
- Tests : vérifier que le `.als` contient 3 envelopes (Freq, Gain, Q) par bande corrigée

### Phase C — Rate limiting du Q
- Lisser les variations brusques de Q (max 2 unités/sec)
- Tests : vérifier que la courbe Q n'a pas de sauts > 2 entre breakpoints adjacents
