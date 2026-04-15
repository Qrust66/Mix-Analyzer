# 🎯 Prompt Claude Code — Acid Drops P14 : Plan unifié (Master Rebalance + EQ8 Reorder + Surgical Fixes)

## Contexte

Projet **Acid Drops** (industriel, target -14 LUFS streaming). Le `.als` actuel est `Acid_drops_Code.als` dans le repo `Qrust66/Mix-Analyzer` (branche `claude/setup-music-github-repo-93B3R`, dossier `ableton/projects/`). Il s'agit du même fichier que `Acid_drops_P13_surgical_fixes.als` (MD5 identique, vérifié — c'est le résultat d'une itération P13 précédente qui a appliqué des EQ8 chirurgicaux + élargi Acid Bass).

**Diagnostic post-P13 (rapport Mix Analyzer 18:36) :**
- Mix Health Score global : **54.6 / 100**
- **Spectral Score : 30.9** (Uneven) — pct_bass = 61% du Full Mix, pct_air = 0.21%, pct_presence = 0.64% → mix bass-heavy, manque cruellement d'air et de présence
- Stereo Score : 68.2 (Too narrow) — width Full Mix = 0.135
- 14 anomalies persistent après P13, dont 12 résonance + 2 phase + 1 RMS très bas
- **Le master bus N'A PAS de Limiter actif** (smartLimit existe en position 5 mais a été bypass au moment du bounce)
- 3 EQ8 carving sont placés AVANT un saturator (Saturn 2) → leur effet est annulé en aval, ce qui explique pourquoi les anomalies de résonance n'ont pas disparu malgré P13

**Mapping JSON** : `ableton_devices_mapping.json` est dans le contexte du projet GitHub. Il mappe les paramètres XML des devices natifs Ableton (StereoGain, EQ Eight, Compressor2, Limiter, etc.) avec toutes les conventions de transformation, validation, et règles d'écriture (`$write_rules`, `$device_insertion_rules`, `$ableton_conventions`).

**Scope strict** : on ne modifie QUE les devices natifs Ableton mappés dans le JSON. Les VST3 tiers non mappés (Pro-Q 4, Saturn 2, Trackspacer, smartComp2, Cyberdrive, ValhallaSupermassive, etc.) **ne doivent PAS être touchés** — ni leurs paramètres internes, ni leur position dans la chaîne (sauf exception explicite mentionnée ci-dessous pour le réordering).

## Objectif global

Livrer **`Acid_drops_Code_P14.als`** (nouveau fichier, l'original n'est jamais écrasé) intégrant 3 actions complémentaires :

1. **P14a — Master rebalance** : ajouter un EQ Eight master pour rééquilibrer le spectre (descendre Bass, ajouter Presence + Air)
2. **P14b — EQ8 reorder** : déplacer les 3 EQ8 carving qui sont mangés par un saturator en aval pour qu'ils soient effectifs
3. **P14c — Surgical fixes** : corriger les 2 problèmes de phase et investiguer Solo Noise

Ces 3 actions sont indépendantes mais conçues pour être appliquées en un seul passage sur le `.als` afin de produire un seul nouveau fichier à tester.

## Investigation préalable obligatoire (à faire AVANT de coder)

1. Clone ou rapatrie `Acid_drops_Code.als` depuis le repo et décompresse-le en XML (gunzip).
2. Lis et **internalise** les sections suivantes du `ableton_devices_mapping.json` :
   - `$file_format` (gzip + XML)
   - `$addressing` (track_lookup, device_lookup, instance_index)
   - `$xml_pattern` (standard_param avec `<Manual Value="...">`, exceptions inline_value, self_closing_tags, tag d'une seule lettre)
   - `$write_rules` (must_preserve, must_do, must_not — particulièrement "sauvegarder sous un nouveau nom de fichier, jamais écraser l'original")
   - `$device_insertion_rules` (id_renumbering avec NextPointeeId, template_purity)
   - `$validation` (float_tolerance 0.01)
   - `$ableton_conventions` (gain_convention log, percent_convention, panning_convention)
   - Les sections devices `Eq8` et `StereoGain` du JSON (paramètres complets)
3. Inspecte le `.als` actuel pour vérifier l'état réel (chaîne du Main, position des EQ8 sur les tracks ciblées, état des Utility existants).
4. **Résume dans le chat** :
   - Ta compréhension des 3 sous-actions et leur ordre d'exécution
   - L'état actuel de chaque track ciblée (chaîne avant intervention)
   - Le plan d'écriture précis (quels nouveaux Id vont être alloués, quel sera le NextPointeeId final)
   - Les risques identifiés
   - **Attends mon GO avant d'écrire quoi que ce soit dans le `.als`.**

## Spec détaillée des 3 sous-actions

### P14a — Master Rebalance via EQ Eight (Master Track)

**Objectif :** rééquilibrer le spectre du Full Mix qui est actuellement à 61% Bass / 0.85% Presence+Air. Cible : ramener Bass autour de 50%, monter Presence à 3-5%, monter Air à 1-3%.

**Position du nouveau device :** **Position 1 du Main bus** (avant tous les autres devices, donc avant le smartLimit qui est en position 5). Le nouveau device sera le tout premier de la chaîne du Main.

**État actuel du Main (vérifié dans le .als)** :
```
1. VST3:smartEQ4   [BYPASS]
2. VST3:Pro-Q 4    [BYPASS]
3. VST3:smartcomp2 [BYPASS]
4. StereoGain      [BYPASS]
5. VST3:smartLimit [ON]      ← seul plugin actif
6. SpectrumAnalyzer [BYPASS]
7. StereoGain      [BYPASS]
```

**Nouveau device à insérer :** un **EQ Eight** natif Ableton, positionné en **position 1** du Main bus, avec les paramètres suivants :

- `On` = true (device actif)
- `Mode_global` (channel processing) = 0 (Stereo)
- `EditMode` = false (canal L par défaut)
- `Precision` (Haute Qualité / Oversampling) = 1 (ON, qualité prioritaire vu qu'on est sur le master)
- `AdaptiveQ` = true (laisse le défaut)
- `GlobalGain` = 0.0 dB
- `Scale` = 1.0 (100%)

**Bandes actives :**

| Band | Mode | Freq (Hz) | Gain (dB) | Q | Justification |
|---|---|---|---|---|---|
| 1 | 2 (Low Shelf) | 200 | **-2.5** | 0.7 | Descend la masse Bass de 61% à ~52-54% |
| 2 | 3 (Bell) | 400 | -1.0 | 1.0 | Léger nettoyage Low-Mid (currently 11.6%) |
| 3 | 3 (Bell) | 1000 | 0.0 | 0.7 | Bypass effectif (laisser pour ajustement futur) |
| 4 | 3 (Bell) | 3000 | +1.5 | 1.0 | Bump léger Mid-Hi |
| 5 | 3 (Bell) | 5000 | **+2.0** | 0.7 | Bump Presence (currently 0.64%) |
| 6 | 5 (High Shelf) | 8000 | **+3.5** | 0.7 | **Air boost** (currently 0.21%) — c'est le mouvement le plus important |
| 7 | OFF | — | — | — | Inactive |
| 8 | OFF | — | — | — | Inactive |

**Toutes les autres bandes (7, 8) :** `IsOn = false`, valeurs par défaut de Live (Mode=3 Bell, Freq variable, Gain=0, Q=0.7).

**Garde-fous spécifiques P14a :**
- C'est une **insertion** de device, donc applique strictement `$device_insertion_rules` :
  - Renumérote tous les `Id="N"` du nouveau bloc EQ8 au-dessus du `max(Id)` global du fichier
  - Mets à jour `<NextPointeeId Value="N"/>` au niveau racine du LiveSet à `(max global final + 1000)`
- Utilise un template VIERGE d'EQ Eight (défaut Ableton), puis applique les overrides ci-dessus. Ne copie PAS un EQ Eight existant du projet, qui pourrait avoir des paramètres globaux hérités.
- Ne touche PAS aux 6 autres devices déjà présents sur le Main (smartEQ4, Pro-Q 4, smartcomp2, StereoGain, smartLimit, SpectrumAnalyzer, StereoGain). Ne change pas leur état On/Off, ne modifie aucun de leurs paramètres.

### P14b — EQ8 Reorder (3 tracks individuelles)

**Objectif :** rendre effectif le carving EQ qui est actuellement annulé par un saturator en aval.

**Tracks ciblées (validées par cross-référence anomalies / chaîne) :**

| Track | EQ8 actuel (position) | Saturator en aval | Action | Cible position |
|---|---|---|---|---|
| **ARP Glitter Box** | pos 1 | Saturn 2 (pos 3) | Déplacer EQ8 après Saturn 2 et après les 2 Trackspacer | pos 6 (juste avant GlueCompressor pos 6) |
| **ARP Intense** | pos 1 | Saturn 2 (pos 3) | Déplacer EQ8 après Saturn 2 | pos 4 (juste avant GlueCompressor pos 4) |
| **Harmony Vocal Female** | pos 1 (la 1ère instance EQ8) | Saturn 2 (pos 7) | Déplacer EQ8 après Saturn 2 | pos 8 (juste avant le Limiter final pos 8) |

**État précis attendu après réordering :**

#### ARP Glitter Box
```
AVANT : EQ8 → Pro-Q4 → Saturn 2 → Trackspacer → Trackspacer → GlueComp → Limiter
APRÈS : Pro-Q4 → Saturn 2 → Trackspacer → Trackspacer → EQ8 → GlueComp → Limiter
```
L'EQ8 garde ses 4 bandes existantes : B1(Bell 248Hz -6dB Q12), B2(Bell 366Hz -6dB Q12), B3(Bell 124Hz -5dB Q10), B4(Bell 495Hz -4dB Q8).

#### ARP Intense
```
AVANT : EQ8 → Pro-Q4 → Saturn 2 → GlueComp → Limiter → Trackspacer
APRÈS : Pro-Q4 → Saturn 2 → EQ8 → GlueComp → Limiter → Trackspacer
```
L'EQ8 garde ses 6 bandes : B1(Bell 732Hz -4dB Q8), B2(877Hz), B3(1163Hz -5dB Q10), B4(980Hz), B5(1464Hz), B6(581Hz).

#### Harmony Vocal Female
```
AVANT : EQ8(carving) → Utility → GlueComp → EQ8(tonal shaping) → Limiter → Nectar 3 → Saturn 2 → Limiter
APRÈS : Utility → GlueComp → EQ8(tonal shaping) → Limiter → Nectar 3 → Saturn 2 → EQ8(carving) → Limiter
```
La 1ère instance EQ8 (5 bandes de carving Bell entre 371-1184 Hz à -3 à -5 dB Q 6-10) est déplacée juste avant le Limiter final. La 2ème instance EQ8 (Low Shelf 30Hz / Bell 200Hz / Bell 1112Hz / High Shelf 3593Hz, tous à 0 dB sauf High Shelf à +3.6dB) reste à sa position actuelle (elle n'est pas mangée par Saturn 2, qui est en aval d'elle).

**Garde-fous spécifiques P14b :**
- Le réordering se fait **par déplacement du bloc XML existant**, pas par insertion d'un nouveau device. Donc :
  - **NE PAS renuméroter les Id** du bloc EQ8 déplacé — il garde tous ses Id internes (AutomationTarget/@Id, etc.) intacts pour préserver les éventuelles automations
  - Le `NextPointeeId` n'a pas à être modifié (pas d'insertion)
- Conserve l'indentation tabulée d'origine du bloc déplacé
- Vérifie après écriture que l'EQ8 déplacé contient toujours toutes ses bandes avec valeurs identiques (tolérance flottante 0.01)
- N'altère AUCUN autre device dans la chaîne (Pro-Q 4, Saturn 2, Trackspacer, GlueCompressor, Limiter restent à l'identique en valeurs, juste leur position dans la chaîne est décalée)
- **Cas particulier Xylo Percussion** : initialement listé comme candidat (EQ8 pos 1 → Saturn 2 pos 2) mais aucune anomalie de résonance n'est détectée par Mix Analyzer dessus. **Donc on NE TOUCHE PAS à Xylo Percussion** dans P14b.

### P14c — Surgical Fixes (2 tracks pour la phase, 1 investigation pour Solo Noise)

#### Fix 1 — Arp Roaming : phase correlation -0.19

**Diagnostic :** width = 0.586, phase = -0.192. Stéréo très large mais corrélation négative → mono-compat compromis.

**Action :** insérer un nouveau **StereoGain (Utility)** en **fin de chaîne**, juste avant le Limiter (qui est en dernière position). État actuel :
```
EQ8 → Trackspacer → Utility → Pro-Q4 → GlueComp → Limiter
```
Nouveau :
```
EQ8 → Trackspacer → Utility → Pro-Q4 → GlueComp → [NEW Utility] → Limiter
```

Paramètres du nouveau Utility :
- `On` = true
- `ChannelMode` = 1 (Stereo)
- `BassMono` = true
- `BassMonoFrequency` = 120.0 Hz
- `BassMonoAudition` = false
- `StereoWidth` = 0.85 (= 85%, narrow légèrement la stéréo de 100% à 85%)
- `Gain` = 0 dB (XML = 1.0)
- Tous les autres paramètres aux défauts du JSON (Mute=false, DcFilter=false, Balance=0, etc.)

**Garde-fous :** insertion de device → applique `$device_insertion_rules` (Id renumbering + NextPointeeId update). Utilise un template vierge.

#### Fix 2 — Solo Lead Synth : phase correlation -0.08

**Diagnostic :** width = 0.540, phase = -0.081. Mono-compat dégradé mais moins grave qu'Arp Roaming.

**Action :** insérer un nouveau **StereoGain (Utility)** en **fin de chaîne**, juste avant l'Auto Filter qui est en dernière position. État actuel :
```
Utility → Pro-Q4 → EQ8 → smartComp2 → AutoFilter
```
Nouveau :
```
Utility → Pro-Q4 → EQ8 → smartComp2 → [NEW Utility] → AutoFilter
```

Paramètres identiques à Arp Roaming sauf :
- `BassMonoFrequency` = 120.0 Hz
- `StereoWidth` = 0.90 (90%, narrow plus léger car phase moins critique)

**Garde-fous :** identiques à Fix 1.

#### Fix 3 — Solo Noise : RMS -63.5 dBFS (investigation, PAS de modification)

**Diagnostic :** RMS extrêmement bas (LUFS = -44.4, RMS = -63.5 dBFS). Trois hypothèses :
- (a) Volume oublié à -inf dans une automation
- (b) Plugin qui mute en pratique (Trackspacer en bout de chaîne ducke à 100%)
- (c) Intentionnel (track de bruit de fond très subtil)

**Action :** **AUCUNE modification dans le `.als` pour Solo Noise.** Dans ton summary final, donne-moi simplement :
- L'état actuel du fader Mixer.Volume (en dB)
- L'état On/Off de chaque device de la chaîne
- Pour le Trackspacer en pos 4, indique son `Ratio` actuel si tu peux le lire (paramètre `Ratio` dans le ProcessorState ou ParameterList du PluginDevice — c'est un VST3, donc lis ce que tu peux extraire sans le modifier)

Je déciderai après inspection s'il faut agir ou pas dans une itération suivante.

## Workflow technique consolidé

1. Crée une branche `claude/p14-rebalance-reorder-fixes-XXX` depuis `main` (ou la branche par défaut du repo).
2. Rapatrie `ableton/projects/Acid_drops_Code.als`, décompresse en XML.
3. Lis le mapping JSON et le XML, fais l'investigation en 4 points listée plus haut.
4. **Résume dans le chat ton plan complet et attends mon GO.**
5. Implémente dans cet ordre strict :
   - **Étape 1 — P14b en premier** (réordering, le moins risqué, ne touche pas aux Id) : déplace les 3 EQ8 (ARP Glitter Box, ARP Intense, Harmony Vocal Female).
   - **Étape 2 — P14c Fix 1+2** (insertion de 2 Utility) : applique `$device_insertion_rules` pour Arp Roaming et Solo Lead Synth.
   - **Étape 3 — P14a en dernier** (insertion EQ8 Master) : applique `$device_insertion_rules` pour le Main bus. Cette étape doit être faite après les 2 précédentes pour que la renumérotation des Id soit cohérente avec le `max(Id)` final.
   - **Étape 4 — Solo Noise investigation** : lecture seule, rapporte dans le summary.
6. Mets à jour `<NextPointeeId Value="N"/>` une seule fois en fin de processus, à `(nouveau max global + 1000)`.
7. Sauvegarde sous **`Acid_drops_Code_P14.als`** (nouveau fichier dans `ableton/projects/`), recompressé gzip. **N'écrase JAMAIS `Acid_drops_Code.als`.**
8. **Validation programmatique post-écriture** : ouvre `Acid_drops_Code_P14.als`, vérifie :
   - Le Main bus contient bien 8 devices, le 1er étant le nouvel EQ Eight avec les 6 bandes correctes (tolérance 0.01 sur les fréquences et gains)
   - ARP Glitter Box : EQ8 est bien à la position 5 (et plus à la position 1)
   - ARP Intense : EQ8 est bien à la position 3 (et plus à la position 1)
   - Harmony Vocal Female : la 1ère instance EQ8 (carving 5 bandes) est bien à la position 7 (et plus à la position 1)
   - Arp Roaming : un nouveau Utility est en position 6 (juste avant Limiter), avec BassMono=true, BassMonoFrequency=120, StereoWidth=0.85
   - Solo Lead Synth : un nouveau Utility est en position 5 (juste avant AutoFilter), avec BassMono=true, BassMonoFrequency=120, StereoWidth=0.90
   - Aucun Id en doublon dans tout le fichier (`grep` rapide)
   - `NextPointeeId` cohérent avec le nouveau max
9. Commit : `P14: master rebalance + EQ8 reorder (3 tracks) + 2 phase fixes`
10. Push, ouvre la PR. **NE PAS merger automatiquement** — j'ouvrirai le `.als` dans Ableton pour validation à l'oreille avant de merger.

## Format de retour attendu

```
## P14 — Plan unifié — Summary

### Branche
claude/p14-rebalance-reorder-fixes-XXX

### Commit
[hash] P14: master rebalance + EQ8 reorder (3 tracks) + 2 phase fixes

### PR
#XX (status: open, awaiting Alex's listening test before merge)

### Fichier produit
ableton/projects/Acid_drops_Code_P14.als (taille gzip: X KB)

### Étape 1 — P14b EQ8 Reorder (3 tracks)
- ARP Glitter Box : EQ8 déplacé pos 1 → pos 5  ✓
- ARP Intense : EQ8 déplacé pos 1 → pos 3  ✓
- Harmony Vocal Female : 1ère instance EQ8 déplacée pos 1 → pos 7  ✓

### Étape 2 — P14c Phase Fixes (2 tracks)
- Arp Roaming : nouveau Utility inséré en pos 6 (BassMono on @120Hz, Width 85%)  ✓
- Solo Lead Synth : nouveau Utility inséré en pos 5 (BassMono on @120Hz, Width 90%)  ✓

### Étape 3 — P14a Master Rebalance
- EQ Eight inséré en pos 1 du Main bus  ✓
- 6 bandes actives configurées (Low Shelf -2.5dB @200Hz, Bell -1dB @400Hz, ... High Shelf +3.5dB @8kHz)  ✓
- Precision (Oversampling) activé  ✓
- Tous les autres devices du Main bus inchangés (smartEQ4, Pro-Q4, smartcomp2, StereoGain ×2, smartLimit, SpectrumAnalyzer)  ✓

### Étape 4 — Solo Noise investigation (read-only)
- Mixer.Volume: X.X dB
- Chaîne actuelle: [list devices avec état On/Off]
- Trackspacer (pos 4): Ratio = X.X% (si lisible)
- Hypothèse retenue: [a/b/c]
- Pas de modification appliquée

### NextPointeeId
- Avant : 335885
- Après : XXXXXX

### Id renumbering summary
- 3 nouveaux blocs insérés (1 EQ8 master + 2 Utility)
- N nouveaux Id alloués au-dessus du max global
- Bloc EQ8 réordonnés conservent leurs Id originaux

### Validation post-écriture (programmatique)
- Tous les checks ont passé : ✓ / ✗ [détailler si ✗]

### Hors scope (non touché)
- Tous les VST3 tiers (Pro-Q 4, Saturn 2, Trackspacer, smartComp2, smartLimit, etc.)
- Solo Noise (lecture seule, à décider après inspection)
- Xylo Percussion (initialement candidat reorder mais pas d'anomalie réelle)
- Toute autre track non listée explicitement
- L'original Acid_drops_Code.als (préservé tel quel)

### Prochaine étape recommandée
Alex ouvre Acid_drops_Code_P14.als dans Ableton, écoute, et :
- Si OK → merge la PR + nouveau bounce + Mix Analyzer pour mesurer l'impact sur Spectral Score, Stereo Score, et anomalies
- Si KO → on revert ou on ajuste les valeurs
```

## Garde-fous globaux (récap)

- **Ne JAMAIS écraser `Acid_drops_Code.als`**. Sortie = `Acid_drops_Code_P14.als`.
- **Aucune modification de VST3 tiers** (paramètres internes ou ProcessorState). Le réordering autorisé concerne uniquement le déplacement de blocs `<Eq8>` natifs au sein de la chaîne `<Devices>`.
- **Préserver tous les `AutomationTarget/@Id`** des paramètres existants des EQ8 réordonnés (pas de renumérotation sur les blocs déplacés).
- **Renuméroter les `Id` UNIQUEMENT pour les 3 nouveaux blocs insérés** (1 EQ8 master + 2 Utility).
- **Mettre à jour `NextPointeeId` une seule fois** à la fin du processus.
- **Recompresser en gzip** la sortie (Live n'ouvre pas le XML brut sans extension).
- **Préserver l'indentation tabulée** (`\t`) à l'écriture.
- Si un test de validation programmatique échoue après écriture, **ne pas commit** et explique l'erreur dans le chat.
