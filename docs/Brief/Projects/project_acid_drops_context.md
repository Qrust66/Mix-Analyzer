# Project Context — Acid Drops

**Version :** 1.0
**Date de création :** 2026-04-23
**Statut du projet :** Phase mastering / finalisation — priorité absolue avant tout autre projet musical
**Hérite de :** `qrust_professional_context.md` (socle invariant) + `documentation_discipline.md` (règles rédaction)

**À l'attention de :** Alexandre Couture (auteur), toute IA conversationnelle (Claude Opus en session), toute IA d'exécution (Claude Code), tout futur collaborateur sur le projet Acid Drops.

---

## 1 — Périmètre de ce document

### 1.1 Ce que ce document couvre

Ce document contient **tout ce qui est spécifique au morceau Acid Drops** :

- Identité du morceau (genre, tempo, tonalité, structure)
- Références musicales pour ce morceau précis
- Targets techniques (loudness, width, balance spectrale)
- État courant du mix (Mix Health Score, master chain existante, décisions validées)
- Éléments à protéger (signature sounds, choix créatifs validés)
- Historique des décisions et notes de session

### 1.2 Ce que ce document ne couvre pas

Ce document **n'inclut pas** :

- L'identité de l'artiste Qrust (voir `qrust_professional_context.md`)
- Le setup technique d'Alexandre (voir `qrust_professional_context.md`)
- La philosophie de production générale (voir `qrust_professional_context.md`)
- Les règles de collaboration avec l'IA (voir `qrust_professional_context.md`)
- La méthodologie mix/mastering (voir `mix_engineer_brief_v2_2.md`)
- Les détails techniques des features Mix-Analyzer (voir specs `feature_*.md`)
- Le changelog des modifications du .als (voir `Acid_Drops_CHANGELOG.md`)

### 1.3 Convention d'utilisation

**Pour démarrer une session sur Acid Drops, charger conjointement :**

1. `qrust_professional_context.md` — socle invariant (toujours)
2. `mix_engineer_brief_v<latest>.md` — méthodologie mix/mastering (toujours)
3. **Ce document** (`project_acid_drops_context.md`) — spécifique au projet
4. Le fichier `.als` du projet (`Acid_Drops_Sections_STD.als` ou variante courante)
5. Le rapport Mix Analyzer Excel le plus récent
6. Le JSON diagnostics CDE le plus récent
7. `Acid_Drops_CHANGELOG.md` — historique des sessions

**En cas de contradiction** entre ce document et le professional context : le professional context prime sur les principes invariants (philosophie 100% dynamique, règle 3 EQ8 max, format réponse). Ce document spécialise pour Acid Drops sans contredire les fondamentaux.

---

## 2 — Identité du morceau

### 2.1 Métadonnées

**Titre :** Acid Drops
**Artiste :** Qrust
**Format :** Single (release prévue SoundCloud prioritaire, DistroKid éventuel)
**Genre primaire :** Industrial / dark electro
**Genre famille (genre_music_profiles.json) :** electronic_aggressive
**Style spécifique :** Industrial

### 2.2 Caractéristiques musicales

**Tempo :** 128 BPM
**Tonalité :** B (mineur probable, à confirmer en session)
**Fondamentale :** 246.94 Hz (détectée par CDE comme zone d'accumulation principale — ~10 conflits accumulation à cette fréquence)
**Time signature :** 4/4 (à confirmer)
**Durée approximative :** à confirmer en session

### 2.3 Esthétique sonore visée

**Caractère général :** dark industrielle groovy. Combine la précision contemporaine de la production (référence NIN) avec une physicalité club (référence Blade soundtrack). Pas de clean ostentatoire, pas de brutalité gratuite — densité contrôlée, agressivité chirurgicale.

**Mots-clés sonores :**
- Groove implacable mais pas robotique
- Sub physique présent en permanence
- Mid-range dense mais lisible
- Distorsion comme texture, pas comme bruit
- Espace stéréo modéré (pas wide à l'extrême, pas mono claustrophobique)

---

## 3 — Références musicales pour Acid Drops

### 3.1 Référence principale

**Nine Inch Nails — albums "Year Zero" (2007), "The Fragile" (1999), "Hesitation Marks" (2013)**

Ce qui est référencé :
- Précision production contemporaine sans perdre l'agressivité
- Attention au détail sur chaque élément
- Mid-range dense mais articulé
- Sub présent sans être brouillard
- Sound design industriel intégré au mix (pas plaqué dessus)

**Tracks de référence spécifiques (à valider/enrichir en session) :**
- "The Hand That Feeds" (Year Zero era) — pour le groove industrial direct
- "Came Back Haunted" (Hesitation Marks) — pour la production contemporaine
- "The Wretched" (The Fragile) — pour la densité contrôlée

### 3.2 Références secondaires

**Blade Soundtrack (1998) — esthétique :** industrial club qui fonctionne sur grosse PA. Référence pour la "physicalité club" du sub et du kick.

**Gesaffelstein — album "Aleph" (2013) :** pour la précision industrielle minimaliste, kick monolithique.

**Skinny Puppy :** pour l'héritage industrial classique (textures, layering, distortion).

**Author & Punisher :** pour la lourdeur mécanique, basse physique.

### 3.3 Anti-références (ce que Acid Drops N'EST PAS)

- **EDM festival clean** (Axwell, Tiësto) — trop poli, trop "fun"
- **Dubstep US** (Skrillex et dérivés) — trop bass-drop centric, dynamique sacrifiée
- **Pop industrielle** (Rammstein) — trop arena rock, trop linéaire
- **Ambient industriel** (Lustmord, Coph Nia) — trop atmosphérique, manque de groove
- **Techno minimal** (Ricardo Villalobos era) — trop dépouillé, manque de densité

**Si une recommandation IA pousse Acid Drops vers l'une de ces directions, le push back est obligatoire.**

---

## 4 — Targets techniques

### 4.1 Loudness

**Master principal : -10 LUFS intégré** (club-ready dark electro / industrial)
- PLR attendu : 8 à 10 dB
- True Peak : -1.0 dBFS maximum
- Usage : SoundCloud (plateforme primaire), club DJ pool, DistroKid éventuel

**Master secondaire : -14 LUFS intégré** (Spotify-safe, streaming normalisé)
- PLR attendu : 10 à 13 dB
- True Peak : -1.0 dBFS maximum
- Usage : plateformes streaming avec normalisation, référence "headphones listening"

**Important :** les deux versions partagent le **même mix**. Seule la chaîne master diffère. Jamais de remix ni de remaster artistique pour la version -14 — ajustement uniquement de la dernière étape (saturation finale + limiter).

### 4.2 Stereo width

**Cible width Full Mix : 0.35 à 0.50** (moderate)

**Distribution par zone fréquentielle :**
- Sub (< 150-200 Hz) reste mono : width < 0.10
- Bass (150-500 Hz) : width 0.10-0.25
- Mids (500 Hz à 2 kHz) : width moderate 0.30-0.50
- High Mids (2-8 kHz) : width 0.40-0.55
- Air (> 8 kHz) : width open 0.40-0.70
- Correlation Full Mix > 0.5 en moyenne

**Principe :** largeur pour l'immersion casque/streaming, mais impact mono préservé pour club systems et car audio. Jamais de widening global sur l'ensemble du spectre.

**Outils privilégiés pour width :**
- EQ Eight Mid/Side natif Ableton
- Widener M/S avec split fréquence (au-dessus de 200 Hz uniquement)
- **Banni :** stereo enhancer global sans split

### 4.3 Dynamics

**Crest factor Full Mix : 10 à 14 dB** (dynamique préservée sous l'agressivité)
**Crest std individuel : < 4 dB** (cohérence du traitement par track)
**LRA : 6-9 LU** (typique club industrial)

**Le mix ne doit PAS sonner over-compressed.** L'agressivité vient de :
- La production (distortion intégrée au sound design)
- La saturation (Saturn 2 plutôt qu'au limiter)
- Le sidechain marqué (Kickstart 2 ou trigger natif)
- Le gain staging discipliné

Et **non** du limiteur final, qui doit être transparent et juste tenir la cible LUFS.

### 4.4 Spectral balance

**Distribution énergie par bande (cibles Industrial Acid Drops) :**

| Bande | Range | Cible % |
|---|---|---|
| Sub | 20-60 Hz | 3-8% — pression club sans brouillard |
| Bass | 60-250 Hz | 25-35% — section groove principal, jamais > 40% |
| Low Mids | 250-500 Hz | 15-25% — corps des instruments, zone à surveiller (boxiness) |
| Mids | 500-2k Hz | 20-30% — présence des leads, vocaux, textures |
| High Mids | 2k-8k Hz | 10-20% — mordant, attaque, intelligibility |
| Air | > 8 kHz | 3-8% — ouverture, sparkle |

**Spectral entropy minimum : 70%** — le mix doit utiliser le spectre, pas écraser une zone.

### 4.5 Caps de traitement spécifiques (du `genre_music_profiles.json` pour Industrial)

**Pour les corrections automatisées (Features 1, 6, 7) :**

Référer à `genre_music_profiles.json` section `electronic_aggressive.Industrial` pour les caps précis par track type. Exemples critiques pour Acid Drops :

**Sub Bass (Industrial) :**
- `hpf_max_hz: 20` — pas de HPF au-dessus de 20 Hz
- `lpf_min_hz: 200` — pas de LPF sous 200 Hz
- `resonance_reduction_max_db: -2.0` — cuts extrêmement modérés
- `masking_tolerance: 0.8` — le masking fait partie du son
- Note : "Fondation. Toucher avec extrême précaution. Le sub distordu EST le son."

**Kick (Industrial) :**
- `hpf_max_hz: 30` — HPF maximum à 30 Hz
- `transient_preserve: true` — jamais compresser/tasser les transients
- Note : à confirmer dans le profil

**Acid Bass (Industrial) :**
- `masking_tolerance: 0.7` — résonance 303 protégée

Toujours consulter le profil avant toute modification.

---

## 5 — Structure du morceau

### 5.1 Sections (via Locators)

**20 sections nommées :**

1. FX
2. Intro
3. Build 1
4. Acid 1
5. Build 2
6. Break 1
7. Drop 1
8. Fall 1
9. Chorus 1
10. Acid 2
11. Breakdown 1
12. Build 3
13. Fall 2
14. Drop 2
15. Fall 3
16. Drop Push
17. Climax
18. Chorus 2
19. Acid 3
20. Outro

### 5.2 Zones chaudes identifiées (CDE)

**Tracks problématiques par section :**

| Section | Conflits H×H critiques | Notes |
|---|---|---|
| Drop 2 | 19 | Zone la plus dense, priorité haute pour CDE |
| Chorus 1 | 11 | À surveiller |
| Chorus 2 | 11 | À surveiller |
| Drop 1 | 8 | Modéré |

**Total diagnostics CDE :** 1064 sur le state STD (au 22 avril 2026)
- Critical : à confirmer en session
- Moderate : à confirmer
- Minor : à confirmer

---

## 6 — Tracks du projet

### 6.1 Inventaire des 35 tracks TFP

Toutes préfixées selon la convention TFP (Track-Function-Profile) : `[X/Y]` où X = Hero (H) / Support (S) / Ambient (A) et Y = Rythmic (R) / Harmonic (H) / Melodic (M) / Textural (T).

**Ambient × Textural :**
- [A/T] Ambience
- [A/T] Noise

**Hero × Harmonic :**
- [H/H] Guitar Distorted

**Hero × Melodic :**
- [H/M] Acid Bass
- [H/M] Glider Lead Synth
- [H/M] Lead Vocal Shhh
- [H/M] NINja Lead Synth
- [H/M] Pluck Lead
- [H/M] Solo Lead Synth

**Hero × Rythmic :**
- [H/R] Bass Rythm
- [H/R] Kick 1
- [H/R] Kick 2
- [H/R] Xylo Percussion

**Hero × Textural :**
- [H/T] China
- [H/T] Xylo Texture

**Support × Harmonic :**
- [S/H] Sub Bass

**Support × Melodic :**
- [S/M] ARP Glitter Box
- [S/M] ARP Intense
- [S/M] Harmony Vocal Female
- [S/M] Lead Vocal Hey

**Support × Rythmic :**
- [S/R] Clap
- [S/R] Floor Toms
- [S/R] Guitar PM A
- [S/R] Guitar PM B
- [S/R] Snare Riser
- [S/R] Spoon Percussion
- [S/R] Tambourine Hi-Hat
- [S/R] Toms Overhead
- [S/R] Toms Rack

**Support × Textural :**
- [S/T] Arp Roaming
- [S/T] Riser
- [S/T] Solo Noise
- [S/T] Solo Pluck
- [S/T] Texture Acid Bass
- [S/T] Voice FX Dark Wihispers

### 6.2 Tracks avec EQ8 Peak Resonance déjà appliqué

**16 tracks sur 35 ont reçu un EQ8 "Peak Resonance" via `write_resonance_suppression` :**

1. [H/R] Kick 1
2. [H/R] Kick 2
3. [S/R] Toms Rack
4. [S/R] Floor Toms
5. [S/R] Toms Overhead
6. [H/R] Bass Rythm
7. [S/H] Sub Bass
8. [H/M] Glider Lead Synth
9. Analog (track utilitaire, à investiguer)
10. [H/T] Xylo Texture
11. [H/M] NINja Lead Synth
12. [H/H] Guitar Distorted
13. [H/M] Pluck Lead
14. [A/T] Ambience
15. [S/M] ARP Glitter Box
16. [S/T] Riser

**État typique :** 15 sur 16 tracks ont 6 bandes animées avec automations Freq + Gain + Q synchronisées. La track Ambience est un cas particulier : 2 bandes ON automatisées (123 Hz cut, 493 Hz boost) + 4 bandes OFF pré-configurées dans la zone 190-290 Hz (proche de la fondamentale B 246.94 Hz).

### 6.3 Tracks sans EQ8 Peak Resonance (à analyser)

**19 tracks n'ont pas encore reçu d'EQ8 Peak Resonance.** À investiguer en session si ces tracks bénéficieraient également d'une analyse via `write_resonance_suppression` ou si elles sont déjà saines spectralement.

### 6.4 Bus existants

À documenter en session :
- BUS Kick (probable, vu dans les WAV bouncés)
- BUS Solo (probable)
- BUS Toms (probable)
- Autres bus à inventorier

---

## 7 — État courant du mix

### 7.1 Mix Health Score actuel

**Score global : 51.1 / 100** (rapport Mix Analyzer du 22 avril 2026, 16:04)

**À confirmer en session :** breakdown par catégorie (Loudness, Dynamics, Spectral Balance, Stereo Image, Anomalies).

**Référence rapport :** `Acid_Drops_MixAnalyzer_2026-04-22_15-52.xlsx` (Git SHA Mix Analyzer be371f7, version 2.7.0)

### 7.2 Fichier .als de référence

**Fichier source courant :** `Acid_Drops_Sections_STD.als`

**Version Live :** Live 12.0_12300

**Caractéristiques :**
- 35 tracks TFP (préfixe [X/Y])
- 42 tracks au total (incluant utilitaires, returns, master)
- 17 EQ8 devices au total
- 16 EQ8 "Peak Resonance" (sur 16 tracks listées en 6.2)
- 0 EQ8 "CDE Correction" (Feature 1 pas encore appliquée)

**Variante :** `Acid_Drops_Sections_TFP.als` existe également, structurellement identique mais avec un timestamp diagnostics différent (TFP_diagnostics du 21 avril vs STD_diagnostics du 22 avril). Le rapport Mix Analyzer du 22 avril correspond à STD.als (validé par l'utilisateur).

**Règle absolue :** ne jamais modifier `Acid_Drops_Sections_STD.als` directement. Toute modification se fait sur une copie nommée selon convention `Acid_Drops_Phase<N>_<description>.als`.

### 7.3 Diagnostics CDE disponibles

**Fichier :** `Acid_Drops_Sections_STD_diagnostics.json`
- Généré : 2026-04-22 à 16:09:44
- Diagnostics totaux : 1064
- Format : `CorrectionDiagnostic` JSON sérialisé (voir `mix_engineer_brief_v2_2.md` section 2.3)

**Fichier alternatif (historique) :** `Acid_Drops_Sections_TFP_diagnostics.json`
- Généré : 2026-04-21 à 23:38:56
- Diagnostics totaux : 1095
- Représente un état antérieur du mix (avant ajustements du 22 avril)

**Pour la session courante : utiliser STD_diagnostics.json** (cohérent avec le rapport Excel et le .als courant).

### 7.4 Chaîne master existante (pré-mastering)

**Devices sur le Main bus actuellement :**

1. Sonible Smart:EQ → adaptive EQ pour balance générale
2. Sonible Smart:Compressor → compression bus adaptative
3. Sonible Smart:Limiter → limiter final

**Évaluation :**
- Chaîne fonctionnelle pour développement et écoutes intermédiaires
- Smart:Limiter à remplacer éventuellement par Pro-L 2 pour mastering final (oversampling, dither de qualité supérieure)
- À évaluer si garder Smart:EQ et Smart:Compressor en learn mode ou passer à des outils manuels pour le mastering final

**Targets master finaux (rappel) :**
- Master club : -10 LUFS intégré, PLR 8-10, TP -1.0 dBFS
- Master Spotify : -14 LUFS intégré, PLR 10-13, TP -1.0 dBFS

### 7.5 Phase actuelle du projet

**Phase mastering / finalisation — priorité absolue.**

Aucune nouvelle feature de production (sound design, layering supplémentaire, additions créatives) ne doit être démarrée tant que Acid Drops n'est pas livré. L'objectif est de **finir** ce morceau, pas de l'enrichir indéfiniment.

**Session 1 attendue :** validation terrain de Feature 1 (CDE corrections) sur une track choisie, pour confirmer que l'outil produit le résultat attendu sur le vrai mix avant déploiement à grande échelle.

---

## 8 — Décisions créatives validées

### 8.1 Décisions production (validées en sessions antérieures)

**Percussions :** one-shots manuels plutôt que drummers virtuels. Superior Drummer évalué et écarté car jugé "trop invasif" pour l'esthétique Acid Drops. Garder cette approche manuelle pour cohérence du grain percussif.

**Stack synth principal :**
- **Mid-bass :** Sérum 2 pour la couche mid-bass principale (acid bass, leads punchy)
- **Sub :** Operator natif Ableton pour le sub-bass (sine pure ou avec saturation contrôlée)
- **Saturation multibande :** Saturn 2 pour shaping spectral
- **Séparation kick/basse :** Trackspacer 2.5 pour ducking précis

**Évaluation NIN-style :** Sérum 2 vs Omnisphere vs Wavetable/Operator natifs Ableton — exploration faite, conclusion : Sérum 2 + Operator + Saturn 2 multiband + Trackspacer 2.5 couvre le besoin Acid Drops. Pas d'achat additionnel justifié pour ce projet.

**Vocaux :** approche traitement in-DAW recommandée plutôt que Waves Illugen 2. ElevenLabs envisagé pour génération de phrases vocales stylisées avec traitement in-DAW post-génération.

### 8.2 Décisions mix/mastering (validées en sessions antérieures)

**Gain staging établi :**
- Kick / Sub : peak entre -12 et -14 dBFS
- Éléments de soutien : descendant jusqu'à -32 dBFS pour les éléments d'arrière-plan

**Chaîne EQ8 Peak Resonance déjà appliquée sur 16 tracks** (voir section 6.2).

**Cibles loudness master confirmées** (voir section 4.1) :
- Club : -10 LUFS, PLR 8-10
- Spotify : -14 LUFS, PLR 10-13

**Workflow bounce établi :** dupliquer MIDI → bounce audio → archiver originaux dans dossier dédié. Cela permet de garder la possibilité de re-bouncer ou d'éditer le MIDI tout en travaillant sur les WAV pour le mix.

### 8.3 Sidechain et timing

**Sidechain principal :** Kickstart 2 (consommé par Feature 1.5 quand livrée).

**Note technique critique :** la **track kick MIDI doit rester active jusqu'au bounce des sidechains dépendants**. Désactiver la track kick MIDI prématurément casse le sidechain trigger sur les tracks qui en dépendent.

### 8.4 Latence Launchpad

**Diagnostic confirmé :** la latence Launchpad Pro MK3 dans Acid Drops est due à un PDC (Plugin Delay Compensation) projet-spécifique, pas à un problème hardware ou driver. À garder en tête lors de session intensives avec contrôleur.

---

## 9 — Concept vidéo (référence pour cohérence cross-medium)

### 9.1 Esthétique visuelle

**Style :** body horror surréaliste

**Palette chromatique :**
- Acid green
- Toxic yellow
- Rust orange
- Near-black

**Thème central :** soumission consciente au contrôle des élites

### 9.2 Workflow vidéo

**Outils prévus :**
- Grok Imagine pour génération initiale
- Flux 2 Pro pour itérations détaillées
- Kling pour animation
- DaVinci Resolve pour post-production

**Pertinence pour le mix/mastering :** assurer cohérence émotionnelle entre la palette sonore (dark, industriel, agressif chirurgical) et la palette visuelle (toxique, contrôle, body horror). Les choix de mix doivent supporter cette densité émotionnelle, pas la diluer.

---

## 10 — Ce qui est sacré pour Acid Drops

Au-delà des principes invariants Qrust (voir `qrust_professional_context.md`), spécifiquement pour ce morceau :

**Kick punch** — le kick est la fondation. Tout plie autour de lui. Compression douce uniquement, transients préservés (`transient_preserve: true` dans le profil).

**Sub weight** — le sub doit être physique au club, pas juste ressenti au casque. Pas de HPF au-dessus de 20 Hz sur Sub Bass. Saturation contrôlée mais préservée (le sub distordu EST le son).

**Acid Bass character** — la résonance 303 typique de l'acid bass est protégée. `masking_tolerance: 0.7` dans le profil. Ne pas sur-corriger les résonances qui sont en fait la signature.

**Glider Lead, NINja Lead, Pluck Lead** — leads distinctifs avec caractère propre. Si une recommandation EQ menace l'identité, c'est la recommandation qui plie.

**Texture Acid Bass + Solo Pluck + Arp Roaming** — éléments texturaux qui créent l'atmosphère. Ne pas les "cleaner" au point de perdre la rugosité voulue.

**Imperfections volontaires** — certaines distorsions, résonances, ou choix de Q large sont des signatures créatives. Distinguer "résonance problématique" (à corriger via Mix Analyzer / CDE) de "résonance signature" (à préserver).

---

## 11 — Ce qui est négociable pour Acid Drops

**Loudness exact** — -10 LUFS est un target, pas un plafond. Si -10.5 ou -9.5 sonne mieux à l'oreille pour le master final, on ajuste. Le PLR (8-10 dB) compte plus que le LUFS exact.

**Width exacte** — 0.35-0.50 est une fourchette. Si le morceau respire mieux à 0.42 ou 0.48, c'est dans la cible. Si on dérive vers 0.55 et que ça sonne mieux, on documente la décision et on garde.

**Balance spectrale exacte** — les pourcentages par bande sont indicatifs. Un mix à 32% Bass au lieu de 30% n'est pas rejeté automatiquement. La cohérence d'ensemble prime.

**Choix entre approches CDE** — pour un diagnostic donné, le choix entre `static_dip`, `musical_dip`, `reciprocal_cuts` peut être ajusté selon le résultat à l'oreille. Le Mix Analyzer propose, l'oreille tranche.

**Ordre exact des phases mix/mastering** — l'architecture en 11 phases du brief v2.2 est suggérée, pas dogmatique. Pour Acid Drops, on peut adapter selon les besoins observés.

---

## 12 — Ce qui est banni pour Acid Drops

Au-delà des bannis invariants Qrust, spécifiquement pour ce morceau :

**Clean pop mastering style** — pas de chaîne master "neutral" qui efface le caractère. Acid Drops doit avoir une signature sonore reconnaissable.

**Hyper-compression loudness war** — pas de limiter à -7 ou -8 LUFS avec crest 5 dB. La cible -10 est ferme, le PLR 8-10 est ferme.

**Over-widening** — pas de stereo imager global au-dessus de 0.55 sur l'ensemble du spectre. Width localisée par zone fréquentielle uniquement.

**Cuts EQ aveugles sur leads distinctifs** — si une recommandation propose -6 dB à 2 kHz sur Glider Lead ou NINja Lead, **challenger avant d'appliquer**. Ces sons ont une signature à préserver.

**Traitement statique sans justification** (voir philosophie 100% dynamique dans `qrust_professional_context.md`) — applicable rigoureusement à Acid Drops. Toute coupure ou enhancement doit être contextuel, sauf les 3 exceptions documentées.

**Refactoring d'infrastructure pendant la phase mastering** — si une optimisation des outils Mix-Analyzer émerge en session, la noter pour après livraison Acid Drops. Ne pas dévier vers du dev tant que le morceau n'est pas livré.

---

## 13 — Stratégie de release

### 13.1 Plateforme primaire

**SoundCloud** — release initiale, cible audience industrial/dark electro existante.

**Master à utiliser :** version club -10 LUFS (SoundCloud n'applique pas de normalisation agressive comme Spotify).

### 13.2 Plateforme secondaire

**DistroKid** — diffusion vers Spotify, Apple Music, autres streamers.

**Master à utiliser :** version Spotify -14 LUFS (compatible avec normalisation streaming).

### 13.3 Décision validée

**SoundCloud prioritaire sur DistroKid pour ce premier single Qrust.** Rationale : audience cible plus présente sur SoundCloud pour le genre, moins de friction de distribution, possibilité de feedback rapide de la communauté.

### 13.4 Artwork

**À développer en parallèle ou après le mix final.**

Cohérence avec l'esthétique visuelle (voir section 9.1) : palette acid green / rust orange / near-black, body horror surréaliste, thème contrôle.

**Workflow probable :** Grok Imagine → Flux 2 Pro pour iteration détaillée → DaVinci Resolve si vidéo associée.

---

## 14 — Notes de session et découvertes techniques

### 14.1 Découvertes archéologiques sur le .als

**Track Ambience — analyse du EQ8 Peak Resonance existant (Id 154) :**

Configuration trouvée dans `Acid_Drops_Sections_STD.als` :

- **Bande 0 [ON]** : freq 123.3 Hz, gain -3.5 dB, Q 8, mode 3 → Freq + Gain + Q tous animés (471 points par paramètre). Cut dynamique sur peak qui bouge autour de 123 Hz.
- **Bande 1 [ON]** : freq 493.5 Hz, gain +1.4 dB, Q 8, mode 3 → Freq + Gain + Q tous animés (462 points). Boost dynamique (enhancement) sur 493 Hz.
- **Bandes 2-5 [OFF]** : pré-configurées aux fréquences 290.2, 252.4, 262.1, 192.3 Hz (zone 190-290 Hz, proche de la fondamentale B 246.94 Hz). Bandes en standby pour activation future.

**Implication :** Mix Analyzer avait pré-positionné des bandes pour traiter les accumulations à 247 Hz mais ne les a pas activées. La décision validée est de **laisser ces bandes OFF intactes** (option B de Feature 1) et de créer un EQ8 "CDE Correction" séparé pour les corrections inter-track. Voir section 14.3.

### 14.2 Comportement Feature 1 sur Peak Resonance existant

**Décision validée (échange du 23 avril) :**

Quand Feature 1 traite une track qui a déjà un EQ8 "Peak Resonance" :

- **Option choisie : Feature 1 crée un EQ8 "CDE Correction" séparé en aval** plutôt que de modifier les bandes existantes du Peak Resonance.
- **Bandes OFF du Peak Resonance laissées intactes** comme trace historique des recommandations Mix Analyzer non activées.
- **Justification :** séparation épistémique (Peak Resonance = peaks de la track seule, CDE Correction = conflits inter-track), bypass indépendant, revert granulaire, pas de risque de casser le travail antérieur.

### 14.3 Cohérence rapport Excel / .als / diagnostics

**Validé en session du 23 avril :**

- Rapport `Acid_Drops_MixAnalyzer_2026-04-22_15-52.xlsx` correspond au .als `Acid_Drops_Sections_STD.als`
- Les 35 tracks TFP du .als matchent les 41 mentions WAV du rapport (après conversion `Acid_Drops [X_Y] Name.wav` → `[X/Y] Name`)
- Diagnostics `STD_diagnostics.json` (16:09 du 22 avril) cohérents avec le rapport (16:04 du 22 avril, 5 minutes avant)
- Diagnostics `TFP_diagnostics.json` (21 avril 23:38) représentent un état antérieur — **ne pas utiliser pour la session courante**

---

## 15 — Roadmap mix/mastering pour Acid Drops

### 15.1 Phases prévues (référence brief v2.2)

Application des 11 phases du `mix_engineer_brief_v2_2.md` adaptée à Acid Drops :

**Phase 1 — Audit architectural et cleanup**
- Inventaire EQ8 par track (vérifier conformité règle 3 max)
- Identification sidechains orphelins
- Normalisation ordre devices

**Phase 2 — Fixes chirurgicaux individuels (Feature 1)** ← Prochaine étape
- Application Feature 1 CDE corrections
- Approche **track-par-track** (pas de batch)
- Commencer par 1 track de test (TBD en session 1)
- Filtrage `severity=critical` initialement
- Validation à l'oreille après chaque track

**Phase 3 — Dynamic HPF/LPF (Feature 6 quand livrée)**
- Reportée jusqu'à livraison Feature 6
- En attendant : automation manuelle des bandes 0/7 d'EQ8 si besoin urgent

**Phase 4 — Gain staging par famille**
- Resserrer scatter LUFS
- Cible : < 4 LU std

**Phase 5 — Refactoring sidechain (Feature 1.5 quand livrée)**
- Reportée jusqu'à livraison Feature 1.5
- En attendant : ajustements manuels Kickstart 2 si critique

**Phase 6 — Dynamic musical enhancement (Feature 7 quand livrée)**
- Reportée

**Phase 7 — Consolidation EQ8 (Feature 8 quand livrée)**
- Reportée
- Vérifier en cours de route si tracks dépassent 3 EQ8 correctifs

**Phase 8 — Traitement bus intermédiaire**
- Drums bus, Synth bus, Vocals bus
- EQ léger + bus compression

**Phase 9 — Mix bus pré-master**
- EQ correctif master, saturation tape, widener M/S au-dessus de 200 Hz, glue compressor
- Cible intermédiaire : -16 LUFS clean balanced

**Phase 10 — Chaîne mastering**
- EQ final, multiband dynamics gentle, color/saturation, width finale
- **Dual master :** version club -10 LUFS + version Spotify -14 LUFS
- Limiter calibré (Pro-L 2 envisagé en remplacement de Smart:Limiter)

**Phase 11 — Validation et export**
- A/B contre version précédente
- Checks multi-système (casque, monitors, mono téléphone, car test mental)
- Bounce final WAV 24-bit/44.1k
- Re-run Mix Analyzer final pour gel des métriques

### 15.2 Approche session 1 (validation Feature 1)

**Objectif :** valider que Feature 1 produit un résultat audible satisfaisant sur Acid Drops avant de passer à l'échelle.

**Méthode validée :**

1. Diagnostic pré-session par Claude conversationnel (analyse du rapport + .als + diagnostics, sélection 1 track, justification, plan exécutable)
2. Validation du plan par Alexandre
3. Préparation technique (copie .als en working copy, ouverture Claude Code dans nouvelle conversation)
4. Briefing Claude Code (transmission du plan + contexte structuré)
5. Exécution par Claude Code (1 track uniquement, pas plus)
6. Vérification post-application (parse XML, visuel Ableton, playback isolé)
7. Décision keep / adjust / revert
8. Si keep : journal de session + décision continuer ou stop
9. Si nécessaire en mode A : passer à track 2 (avec connaissance accumulée)

**Tracks candidates pour session 1 (à arbitrer en Phase A du diagnostic) :**

- Une track avec diagnostics simples et indépendants (apprentissage safe)
- Une track au cœur d'une zone chaude (Drop 2, max impact)
- Une track avec Peak Resonance existant (validation comportement séparation EQ8)

**Sévérité initiale :** `critical` uniquement.

**Mode Feature 1 :** à arbitrer selon les diagnostics retenus (section-locked vs peak-following).

---

## 16 — Évolution de ce document

### 16.1 Quand mettre à jour ce document

Mise à jour de ce document **à chaque session de travail sur Acid Drops** qui produit :

- De nouvelles décisions créatives validées (section 8)
- Un nouveau Mix Health Score post-bounce (section 7.1)
- Un nouveau .als de référence (section 7.2)
- De nouveaux diagnostics CDE (section 7.3)
- Des modifications de la chaîne master (section 7.4)
- Une avancée dans la roadmap (section 15)
- Des découvertes techniques additionnelles (section 14)

### 16.2 Quand NE PAS mettre à jour ce document

Ne pas mettre à jour pour :

- Les changements de paramètres mineurs sur des tracks individuelles → `Acid_Drops_CHANGELOG.md`
- L'évolution des features Mix-Analyzer → `roadmap_features_1_8.md`
- L'évolution des règles de collaboration ou setup technique → `qrust_professional_context.md`

### 16.3 Procédure de mise à jour

Suivre `documentation_discipline.md` section 4 :

1. Lire ce document intégralement
2. Identifier ce qui doit changer
3. Si suppression ou restructuration → demander confirmation
4. Modifier in-place en préservant
5. Incrémenter version + enrichir historique
6. Signaler nouveautés explicitement
7. Tester complétude
8. Archiver ancienne version
9. Livrer avec annonce

### 16.4 Historique d'évolution

**v1.0 — Création initiale (2026-04-23)**
- Document fondateur séparé du `qrust_artistic_context_v1_1.md` qui mélangeait professional et project
- Identité du morceau Acid Drops (genre, tempo, tonalité, structure)
- Références musicales pour ce projet (NIN principal, Blade/Gesaffelstein/Skinny Puppy/Author & Punisher secondaires)
- Anti-références listées
- Targets techniques complets (loudness, width, dynamics, spectral balance)
- Caps Industrial du genre profile rappelés
- 20 sections du morceau listées
- 35 tracks TFP inventoriées avec catégorisation
- 16 tracks avec Peak Resonance déjà appliqué documentées
- Mix Health Score actuel (51.1/100)
- Chaîne master existante documentée
- Décisions créatives validées en sessions antérieures (percussions, stack synth, gain staging)
- Découvertes archéologiques (Ambience Peak Resonance config détaillée)
- Décision Feature 1 séparation EQ8 documentée
- Cohérence rapport/als/diagnostics validée
- Stratégie de release SoundCloud > DistroKid
- Concept vidéo cross-medium référencé
- Roadmap 11 phases adaptée à Acid Drops
- Approche session 1 validée

---

## 17 — Référence rapide (quick card)

**Ce document est :** le contexte spécifique au projet Acid Drops.

**Ce document n'est pas :** le contexte invariant Qrust (voir `qrust_professional_context.md`).

**Pour démarrer une session Acid Drops :**
1. Charger `qrust_professional_context.md` (toujours)
2. Charger `mix_engineer_brief_v<latest>.md` (toujours)
3. Charger ce document (`project_acid_drops_context.md`)
4. Charger `Acid_Drops_Sections_STD.als` (ou variante courante)
5. Charger `Acid_Drops_MixAnalyzer_<latest>.xlsx`
6. Charger `Acid_Drops_Sections_STD_diagnostics.json`
7. Charger `Acid_Drops_CHANGELOG.md`

**Targets ferment :**
- Genre : Industrial / dark electro
- Tempo : 128 BPM
- Tonalité : B (fondamentale 246.94 Hz)
- Master club : -10 LUFS, PLR 8-10, TP -1 dBFS
- Master Spotify : -14 LUFS, PLR 10-13, TP -1 dBFS
- Width : 0.35-0.50 (sub mono < 0.10)
- Crest : 10-14 dB

**Phase actuelle :** mastering / finalisation. Priorité absolue, pas de nouveau projet avant livraison.

**Prochaine étape :** session 1 validation Feature 1 sur 1 track choisie via Phase A diagnostic.

---

**Fin du document `project_acid_drops_context.md` v1.0. Mise à jour selon procédure définie en section 16.**
