# Contexte artistique Qrust

**Version :** 1.1 (ajout philosophie traitement dynamique, 2026-04-23)
**Version précédente :** 1.0 (création initiale)

## Identité du projet

**Artiste :** Qrust (alias "Peel the Qrust" sur certaines plateformes)
**Créateur :** Alexandre Couture
**Genre primaire :** Industrial / dark electro
**Esthétique sonore :** Agressivité contrôlée, textures métalliques, bas du spectre dense, distorsion chirurgicale. Pas de prétention à la virtuosité mélodique — la puissance vient du groove, du sound design et de la pression sonore.
**Esthétique visuelle :** Body horror surréaliste, palette acid green / toxic yellow / rust orange / near-black, soumission consciente au contrôle des élites comme thème central.

## Références musicales de positionnement

**Référence principale :** Nine Inch Nails — notamment "Year Zero", "The Fragile", "Hesitation Marks". Le son NIN combine une précision production contemporaine avec une agressivité mid-range et une attention au détail sur chaque élément.

**Références secondaires :** Blade soundtrack aesthetic (industrial club qui fonctionne sur grosse PA), Gesaffelstein période "Aleph", Skinny Puppy, Author & Punisher.

**Ce qui n'est PAS la référence :** EDM festival clean (Axwell, Tiësto), dubstep US (Skrillex), pop industrielle (Rammstein), ambient industriel (Lustmord). Qrust n'est ni trop clean ni trop brutal.

## Targets techniques

### Loudness

**Master principal : -10 LUFS intégré** (club-ready dark electro / industrial)
- PLR attendu : 8 à 10 dB
- True Peak : -1.0 dBFS maximum
- Usage : SoundCloud (plateforme primaire), club DJ pool, DistroKid éventuel

**Master secondaire : -14 LUFS intégré** (Spotify-safe, streaming normalisé)
- PLR attendu : 10 à 13 dB
- True Peak : -1.0 dBFS maximum
- Usage : plateformes streaming avec normalisation, référence "headphones listening"

Les deux versions partagent le même mix — seule la chaîne master diffère. Jamais de remix ni de remaster artistique pour la version -14.

### Stereo width

**Cible width Full Mix : 0.35 à 0.50** (moderate)
- Sub (< 150-200 Hz) reste mono (width < 0.10)
- Mids (200 Hz à 2 kHz) moderate (0.30 à 0.50)
- Highs (> 2 kHz) open (0.40 à 0.70)
- Correlation Full Mix > 0.5 en moyenne

**Principe :** largeur pour l'immersion, mais impact mono préservé pour club systems et cars. Jamais de widening global sur l'ensemble du spectre.

### Dynamics

**Crest factor Full Mix : 10 à 14 dB** (dynamique préservée sous l'agressivité)
**Crest std individuel : < 4 dB** (cohérence du traitement par track)

Le mix ne doit PAS sonner over-compressed. L'agressivité vient de la production (distorsion, saturation, sidechain marqué) et non du limiteur final.

### Spectral balance

**Sub Energy (20-60 Hz) : 3-8%** — pression club sans brouillard
**Bass (60-250 Hz) : 25-35%** — la section groove principal, mais jamais dominante > 40%
**Low Mids (250-500 Hz) : 15-25%** — corps des instruments, zone à surveiller (boxiness)
**Mids (500-2k Hz) : 20-30%** — présence des leads, vocaux, textures
**High Mids (2k-8k Hz) : 10-20%** — mordant, attaque, intelligibility
**Air (> 8 kHz) : 3-8%** — ouverture, sparkle

**Spectral entropy minimum : 70%** — le mix doit utiliser le spectre, pas écraser une zone.

## Philosophie de production — Le traitement dynamique avant tout (nouveau en v1.1)

**Principe fondamental :** dans un projet Qrust, **aucun traitement spectral ne doit être figé sans justification**. Toute correction, coupure, enhancement ou shelf doit être piloté par automation contextuelle qui tient compte de :

- La section musicale active (une correction qui s'applique en Drop peut être nuisible en Breakdown)
- Ce que la track fait réellement à ce moment (si elle est silencieuse, zéro traitement ; si elle émerge, traitement adapté à son contenu réel)
- Ce que les autres tracks font en parallèle (conflits de masking qui naissent de combinaisons spécifiques)
- Les peaks audio détectés dans l'audio réel (pas des bandes devinées à l'avance)

**Pourquoi cette philosophie :**

Une coupure statique à 40 Hz sur une voix peut sembler anodine, mais si la voix a un grognement harmonique à 45 Hz en Drop 2 qui ajoute du caractère, la coupure figée le sacrifie. Le traitement dynamique permet de garder ce caractère quand il sert le morceau et de le discipliner ailleurs.

Les processeurs commerciaux modernes (Pro-Q 4 Dynamic EQ, soothe2, Gullfoss) font du traitement adaptatif en interne. L'approche Qrust est de **reproduire ce comportement par automation externe précise** dans Ableton, avec :

- Transparence totale (les courbes d'automation sont visibles, pas cachées dans une boîte noire DSP)
- Contrôle de l'ingénieur (chaque automation est modifiable à la main)
- Cohérence avec l'analyse amont (Mix Analyzer drive directement les automations)
- Réversibilité (chaque étape peut être bypass indépendamment)

**Application concrète :**

Règle par défaut — Dynamique contextuelle. Toute correction fréquentielle (cut résonance, masking, accumulation, enhancement, HPF, LPF, shelf) est automatisée par section et/ou par peak-follow.

Exception argumentée — Statique autorisé uniquement dans 3 cas stricts, toujours documentés dans le changelog :

- Sub-sonique hors spectre audible (< 20 Hz) — cap fonctionnel, pas musical
- Ultra-sonique hors spectre audible (> 20 kHz) — idem
- Parasites constants connus et ponctuels (bourdonnement 60 Hz ligne secteur, interférence confirmée) — documentés avec la source

Toute autre coupure ou enhancement est contextuel. Si une correction semble relever du "toujours applicable", elle doit être remise en question — probablement qu'elle est en réalité dépendante du contexte musical et mérite une automation.

## Ce qui est sacré

- **Kick punch** : le kick est la fondation. Tout plie autour de lui.
- **Sub weight** : le sub doit être physique au club, pas juste ressenti au casque.
- **Signature sounds** : les textures et leads distinctifs de Qrust ne doivent jamais être over-processed au point de perdre leur caractère. Si une recommandation EQ menace l'identité d'un son, c'est la recommandation qui plie, pas le son.
- **Imperfections volontaires** : certaines distorsions, résonances, ou choix de Q large sont des signatures créatives. Distinguer "résonance problématique" de "résonance signature".
- **Contextualité** (nouveau en v1.1) — aucun traitement qui sculpte le son ne doit être constant à travers tout le morceau. Chaque section a ses besoins, chaque track évolue dans le temps.

## Ce qui est négociable

- **Loudness absolu** : -10 LUFS est un target, pas un plafond. Si -11 sonne mieux, on va à -11.
- **Width** : 0.35-0.50 est une fourchette, pas une contrainte rigide.
- **Balance spectrale exacte** : les pourcentages sont des indicatifs, pas des lois. Un mix qui sonne bien avec 40% Bass n'est pas rejeté automatiquement.

## Ce qui est banni

- **Clean pop mastering** : pas de chaîne master "SmartEQ4 learn → neutral". Qrust n'est pas neutre.
- **Hyper-compression loudness war** : pas de limiter à -6 LUFS avec crest 5 dB. On a une dynamique préservée même forts.
- **Over-widening** : pas de stereo imager global. Width localisée par zone spectrale.
- **Cut EQ aveugles** : si une recommandation coupe -6 dB à 2 kHz sur un lead distinctif, on challenge avant d'appliquer.
- **Traitement statique sans justification** (nouveau en v1.1) — aucun HPF figé, aucun LPF figé, aucun shelf constant sauf dans les 3 exceptions documentées. Un traitement fixe demande justification écrite dans le changelog.

## Organisation de la device chain par track

**Règle Qrust : maximum 3 EQ8 correctifs par track** (nouveau en v1.1), organisés par rôle épistémique clair :

**EQ8 Static Cleanup — AUCUN en pratique pour Qrust** — Compte tenu du principe 100% dynamique, cet EQ8 reste vide ou n'existe pas. S'il existe, il contient **uniquement** les 3 exceptions statiques autorisées (rumble <20 Hz, ultra-sonique >20 kHz, parasite constant documenté). Placé au début de chain. Contient idéalement 0 ou 1 bande active, jamais plus.

**EQ8 Peak Resonance** — Automations dynamiques multi-bandes sur peaks spectraux de la track individuelle. Généré par Mix Analyzer via `write_resonance_suppression`. Suit les peaks qui émergent à travers tout le morceau sur la track seule. Placé après Static Cleanup. Contient typiquement 2-6 bandes ON avec Freq + Gain + Q tous animés.

**EQ8 CDE Correction** — Corrections ciblées Mix Analyzer CDE pour résoudre des conflits masking ou accumulation inter-track. Section-locked ou peak-following selon le type de conflit. Chaque bande correspond à un cluster de diagnostics CDE. Placé après Peak Resonance.

**EQ8 Musical Enhancement** — (optionnel, 4ème device autorisé uniquement en post-chaîne correction) Enhancement créatif : boosts de présence, ajout d'air, excitation harmonique. Placé après les effets non-correctifs (saturation, compression, sidechain). Toujours avec automations contextuelles par section.

**Ordre dans la chain complète :**

Static (0-1 bande) → Peak Resonance (Feature native Mix Analyzer) → CDE Correction (Feature 1) → HPF/LPF Dynamic (Feature 6 à venir) → Saturation → Compression → Sidechain → Musical Enhancement (Feature 7 à venir) → Glue → Limiter

Note : l'ordre exact peut varier selon les contraintes de la track, mais la règle générale est "correction avant processing créatif avant glue final".

## Interlocuteur

Alexandre est technique et direct. Tolérance zéro pour le flou ou la survente. Attend un rôle de partenaire de lucidité et d'architecte d'options : diagnostiquer → proposer des options → recommander → fournir les étapes cliquables précises.

- Communication en français québécois, zéro jargon France. Sacres dosés OK.
- Préférence marquée pour **Ableton natif + plugins ciblés** plutôt que gros bundles.
- Priorise **Ableton Stock + JMG/Sonible** avant Waves / iZotope pour le traitement contemporain.
- **Pro-Q 4 disponible** mais n'est pas le plugin par défaut — EQ Eight natif est préféré pour les corrections pilotées par Mix Analyzer / CDE, car EQ Eight est mappé et automatisable programmatiquement avec précision totale.

**Approche avant-gardiste (nouveau en v1.1)** — le choix d'EQ Eight natif + automation précise plutôt que plugins commerciaux dynamiques n'est pas une limitation technique mais une philosophie. L'automation externe visible bat la boîte noire DSP sur les axes transparence, contrôle, auditabilité, réversibilité. Le fait que cette approche soit rare dans l'industrie ne la disqualifie pas — c'est un angle commercialisable à terme.

## Éléments de composition d'Acid Drops (exemple de contexte projet)

**Tempo :** 128 BPM
**Tonalité :** B (fondamentale 246.94 Hz détectée par CDE comme zone d'accumulation)
**Structure :** 20 sections nommées via Locators (FX, Intro, Build 1, Acid 1, Build 2, Break 1, Drop 1, Fall 1, Chorus 1, Acid 2, Breakdown 1, Build 3, Fall 2, Drop 2, Fall 3, Drop Push, Climax, Chorus 2, Acid 3, Outro)
**Nombre de tracks :** 35 pistes préfixées TFP (Hero / Support / Ambient × Rythmic / Harmonic / Melodic / Textural)
**Zones chaudes :** Drop 2 (19 conflits H×H critiques), Chorus 1 et Chorus 2 (11 conflits chacun), Drop 1 (8 conflits)

## Historique d'évolution

**v1.0 — Création initiale (2026-04-23 matin)**
- Identité Qrust définie
- Références musicales listées
- Targets techniques confirmés
- Philosophie de production posée

**v1.1 — Ajout philosophie 100% dynamique (2026-04-23 après-midi)**
- Section "Philosophie de production — Le traitement dynamique avant tout" ajoutée
- Règle "max 3 EQ8 correctifs par track" ajoutée avec rôles épistémiques
- Liste des bannis étendue avec "traitement statique sans justification"
- 3 exceptions statiques autorisées documentées
- Ordre de device chain proposé
- Approche "avant-gardiste" clarifiée
