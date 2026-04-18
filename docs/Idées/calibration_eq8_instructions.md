# Calibration EQ8 — Instructions pas à pas

## Objectif

Créer un .als avec des automations EQ8 à valeurs CONNUES pour que le code puisse vérifier qu'il lit et écrit correctement.

## Setup initial

1. Ouvre Ableton Live 12
2. Crée un **nouveau Set vide** (Ctrl+N)
3. Le tempo par défaut (120 BPM) est correct — ne le change pas
4. Sauvegarde immédiatement sous le nom : `calibration_eq8_automations.als`

---

## TRACK 1 — "Freq Test"

### Créer la track
1. Crée une track Audio (Ctrl+T)
2. Double-clic sur le nom de la track → renomme-la exactement : `Freq Test`

### Ajouter l'EQ8
1. Dans le Browser à gauche, va dans **Audio Effects → EQ Eight**
2. Drag-and-drop l'EQ Eight sur la track

### Configurer Band 1
1. Clique sur le **bouton "1"** en bas de l'EQ Eight pour sélectionner la Band 1
2. Assure-toi que la Band 1 est **activée** (le bouton 1 est allumé/bleu)
3. Change le **Mode** de la Band 1 en **Bell** (menu déroulant sous le display, sélectionne "Bell" ou "Peak")
4. Mets la **Freq** à **1000 Hz** (clique sur la valeur Freq et tape 1000)
5. Mets le **Gain** à **0.00 dB** (devrait déjà être à 0)
6. Mets le **Q** à **1.00** (clique sur Q et tape 1)

### Dessiner l'automation de Freq
1. Passe en **vue Arrangement** (touche Tab si t'es en Session)
2. Dans le sélecteur d'automation en bas de la track (petit menu déroulant), sélectionne :
   - Device : **EQ Eight**
   - Parameter : **1 Frequency A**
3. Tu vois maintenant la lane d'automation de la fréquence
4. Avec le crayon (touche B pour activer), dessine **exactement 5 points** :

| Position (mesure:temps) | Valeur à dessiner |
|---|---|
| **1:1** (tout début) | **100 Hz** |
| **5:1** (mesure 5) | **500 Hz** |
| **9:1** (mesure 9) | **2000 Hz** |
| **13:1** (mesure 13) | **8000 Hz** |
| **17:1** (mesure 17) | **100 Hz** |

**Comment mettre des valeurs précises :** clique sur un point d'automation, puis dans le champ de valeur qui apparaît en bas, tape la valeur exacte. Si tu ne vois pas le champ, double-clique sur le point.

**Alternative si tu ne peux pas taper la valeur :** dessine la courbe approximativement en t'aidant de l'affichage de la valeur quand tu survoles le point. 100 Hz en bas, 8000 Hz en haut.

---

## TRACK 2 — "Gain Test"

### Créer la track
1. Crée une nouvelle track Audio (Ctrl+T)
2. Renomme-la : `Gain Test`

### Ajouter l'EQ8
1. Drag-and-drop un EQ Eight sur la track

### Configurer Band 1
1. Band 1 activée, Mode **Bell**, Freq **1000 Hz**, Q **1.00**, Gain **0 dB**

### Dessiner l'automation de Gain
1. Sélecteur d'automation → **EQ Eight → 1 Gain A**
2. Dessine **5 points** :

| Position | Valeur |
|---|---|
| **1:1** | **0 dB** (centre, pas de boost ni cut) |
| **5:1** | **-6 dB** |
| **9:1** | **-12 dB** |
| **13:1** | **+6 dB** |
| **17:1** | **0 dB** |

Le Gain va de -15 dB (tout en bas) à +15 dB (tout en haut). Le centre (ligne du milieu) = 0 dB.

---

## TRACK 3 — "Q Test"

### Créer la track
1. Crée une nouvelle track Audio
2. Renomme-la : `Q Test`

### Ajouter l'EQ8
1. Drag-and-drop un EQ Eight

### Configurer Band 1
1. Band 1 activée, Mode **Bell**, Freq **1000 Hz**, Q **1.00**, Gain **-6 dB** (mets -6 pour que la bande soit visible)

### Dessiner l'automation de Q
1. Sélecteur d'automation → **EQ Eight → 1 Resonance A** (le Q s'appelle "Resonance" dans le sélecteur d'automation d'Ableton)
2. Dessine **5 points** :

| Position | Valeur |
|---|---|
| **1:1** | **0.50** (Q large) |
| **5:1** | **1.00** |
| **9:1** | **4.00** |
| **13:1** | **12.00** |
| **17:1** | **0.50** |

Le Q va de 0.1 (très large) à 18.0 (très étroit).

---

## TRACK 4 — "IsOn Test"

### Créer la track
1. Crée une nouvelle track Audio
2. Renomme-la : `IsOn Test`

### Ajouter l'EQ8
1. Drag-and-drop un EQ Eight

### Configurer Band 1
1. Band 1 activée, Mode **Bell**, Freq **500 Hz**, Q **2.00**, Gain **-8 dB**

### Dessiner l'automation de IsOn
1. Sélecteur d'automation → **EQ Eight → 1 Filter On A**
2. C'est un toggle On/Off. Dessine :

| Position | Valeur |
|---|---|
| **1:1** | **On** (haut) |
| **5:1** | **Off** (bas) |
| **9:1** | **On** (haut) |
| **13:1** | **Off** (bas) |
| **17:1** | **On** (haut) |

---

## TRACK 5 — "Multi Band Test"

### Créer la track
1. Crée une nouvelle track Audio
2. Renomme-la : `Multi Band Test`

### Ajouter l'EQ8
1. Drag-and-drop un EQ Eight

### Configurer PLUSIEURS bandes avec des valeurs FIXES (pas d'automation)

| Band | Activée | Mode | Freq | Gain | Q |
|---|---|---|---|---|---|
| 1 | Oui | Low Cut 48 | **50 Hz** | (inactif) | **0.71** |
| 2 | Oui | Low Shelf | **120 Hz** | **-3 dB** | **0.71** |
| 3 | Oui | Bell | **400 Hz** | **+2 dB** | **2.00** |
| 4 | Oui | Bell | **1000 Hz** | **-4 dB** | **4.00** |
| 5 | Oui | Notch | **2500 Hz** | (inactif) | **8.00** |
| 6 | Oui | High Shelf | **6000 Hz** | **+1.5 dB** | **0.71** |
| 7 | Oui | High Cut 48 | **16000 Hz** | (inactif) | **0.71** |
| 8 | Non | — | — | — | — |

**PAS d'automation sur cette track** — seulement des valeurs statiques. Ça sert à vérifier les Manual values.

---

## TRACK 6 — "Multi Param Test"

### Créer la track
1. Crée une nouvelle track Audio
2. Renomme-la : `Multi Param Test`

### Ajouter l'EQ8
1. Drag-and-drop un EQ Eight

### Configurer Band 2
1. **Band 2** activée, Mode **Bell**, Freq **800 Hz**, Gain **0 dB**, Q **2.00**

### Dessiner les 3 automations SIMULTANÉMENT sur Band 2

**Automation 1 — Freq :**
- Sélecteur → **EQ Eight → 2 Frequency A**
- 3 points : 1:1 = **200 Hz**, 9:1 = **2000 Hz**, 17:1 = **200 Hz**

**Automation 2 — Gain :**
- Sélecteur → **EQ Eight → 2 Gain A**
- 3 points : 1:1 = **0 dB**, 9:1 = **-8 dB**, 17:1 = **0 dB**

**Automation 3 — Q :**
- Sélecteur → **EQ Eight → 2 Resonance A**
- 3 points : 1:1 = **1.00**, 9:1 = **10.00**, 17:1 = **1.00**

---

## TRACK 7 — "Mode Test"

### Créer la track
1. Crée une nouvelle track Audio
2. Renomme-la : `Mode Test`

### Ajouter 2 EQ Eight (deux instances sur la même track)

**EQ Eight #1 :** renomme-le `EQ Mode A` (clic droit → Rename)
- Band 1 : Mode **Low Cut 48**, Freq **80 Hz**, activée
- Band 3 : Mode **Bell**, Freq **1000 Hz**, Gain **-3 dB**, Q **4**, activée
- Toutes les autres bandes désactivées

**EQ Eight #2 :** renomme-le `EQ Mode B`
- Band 1 : Mode **High Shelf**, Freq **8000 Hz**, Gain **+2 dB**, activée
- Band 3 : Mode **Notch**, Freq **3000 Hz**, Q **12**, activée (Gain sera inactif)
- Toutes les autres bandes désactivées

PAS d'automation — valeurs statiques seulement. Ça vérifie la lecture des modes sur plusieurs instances.

---

## Vérification finale avant de sauvegarder

Tu devrais avoir **7 tracks** :

| # | Nom | EQ8 instances | Automations |
|---|---|---|---|
| 1 | Freq Test | 1 | 1 Frequency A (5 points) |
| 2 | Gain Test | 1 | 1 Gain A (5 points) |
| 3 | Q Test | 1 | 1 Resonance A (5 points) |
| 4 | IsOn Test | 1 | 1 Filter On A (5 points) |
| 5 | Multi Band Test | 1 | Aucune (7 bandes statiques) |
| 6 | Multi Param Test | 1 | 3 automations sur Band 2 |
| 7 | Mode Test | 2 | Aucune (modes variés) |

## Sauvegarder

1. **Ctrl+S** pour sauvegarder
2. Le fichier doit s'appeler : `calibration_eq8_automations.als`
3. Upload-le moi

---

## Ce que je vais en faire

Je vais parser le XML et extraire :

1. **Chaque automation :** target ID, timestamps en beats, valeurs XML
2. **Chaque valeur statique :** Manual values pour Freq, Gain, Q, Mode, IsOn
3. **Comparaison :** valeurs XML vs valeurs Ableton que tu as mises
4. **Résultat :** confirmation que l'encodage est direct (Hz brut, dB brut, Q brut) ou découverte d'une transformation cachée

Si une seule valeur ne matche pas (ex: tu mets 1000 Hz et le XML dit 0.456), ça veut dire qu'il y a une transformation et le mapping actuel est faux. Si tout matche, le mapping est confirmé et on peut avancer.
