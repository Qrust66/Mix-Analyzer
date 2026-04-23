# Qrust Professional Context

**Version :** 1.0
**Date de création :** 2026-04-23
**Statut :** Permanent, applicable à tous les projets Qrust (musique, vidéo, sound design, mastering)
**Hérite de :** `documentation_discipline.md` (règles de rédaction)

**À l'attention de :** Alexandre Couture (auteur), toute IA conversationnelle (Claude Opus en session), toute IA d'exécution (Claude Code), tout futur collaborateur sur les projets Qrust.

---

## 1 — Périmètre de ce document

### 1.1 Ce que ce document couvre

Ce document est le **socle invariant** qui définit **comment travailler avec Alexandre sur n'importe quel projet Qrust**. Il décrit :

- Identité professionnelle de l'artiste
- Setup technique disponible (DAW, hardware, plugins)
- Philosophie de production qui s'applique à tous les projets
- Règles de collaboration avec l'IA
- Patterns de travail à favoriser et à éviter

### 1.2 Ce que ce document ne couvre pas

Ce document **ne contient pas** les paramètres spécifiques à un projet donné (genre, tempo, target loudness, références musicales, état d'avancement). Ces éléments sont dans des documents séparés `project_<nom>_context.md`.

**Règle d'utilisation :**

Pour démarrer une session sur un projet Qrust spécifique, charger conjointement :
1. Ce document (`qrust_professional_context.md`) — toujours
2. Le document du projet courant (`project_<nom>_context.md`) — spécifique au projet

Le project context hérite de ce professional context. En cas de contradiction entre les deux, le project context précise/spécialise sans contredire les principes fondamentaux du professional context.

### 1.3 Convention de nommage des documents projets

`project_<nom_projet>_context.md`

Exemples :
- `project_acid_drops_context.md` (Industrial / dark electro, 128 BPM)
- `project_<future_track>_context.md` (peut être un autre genre, autres targets)

---

## 2 — Identité professionnelle

### 2.1 L'artiste

**Nom de scène :** Qrust (alias étendu "Peel the Qrust" sur certaines plateformes)
**Identité civile :** Alexandre Couture
**Domaine principal :** Production musicale industrielle / dark electro, sound design, composition électronique
**Statut professionnel :** Producteur indépendant en parallèle d'activité technique (analyste d'affaires, Hydro-Québec, télétravail partiel depuis Chertsey, QC)

### 2.2 Identité créative multidisciplinaire

Alexandre est un créateur multidisciplinaire avec une **double identité créative stable** qui informe son rapport au mix/mastering :

**Producteur musical Qrust** — focus de ce document. Production électronique sombre, esthétique industrielle contemporaine, attention au détail technique extrême.

**Auteur de fiction "Québec noir"** — *Reflets de Cendres*, trilogie horror psychologique paranormale québécoise. Pratique l'économie de mots, le sous-texte, "3 couches par scène". Cette discipline d'écriture transfère directement à sa production musicale : préférence pour le dense significatif plutôt que le complexe gratuit.

**Pertinence pour les sessions mix/mastering :**

L'approche "Québec noir" — sous-texte, économie, profondeur sous la surface — se retrouve dans son rapport à la production. Il rejette la complexité ostentatoire au profit de la précision invisible mais perceptible. Une décision technique qui "ajoute du sens" sera privilégiée à une décision qui "ajoute de l'effet".

### 2.3 Niveau d'expertise

**Avancé en :**
- Synthèse sonore (Sérum 2, Omnisphere, Operator, Wavetable, hardware Summit)
- Sound design industriel (textures, distorsion, layering)
- Compréhension technique des outils Ableton (au-delà de l'opérateur lambda)
- Réflexion philosophique critique sur l'IA et ses usages

**En développement :**
- Mix engineering pur (sait ce qu'il veut, en apprentissage des techniques optimales)
- Mastering (explore les chaînes, calibration des targets, A/B avec références)
- Architecture de session avancée (groupes, bus, automation cascade)

**Implication pour l'IA :**

Calibrer les explications par topic. Sur la synthèse, tu peux aller dans les détails techniques sans préambule. Sur le mastering, prendre le temps d'expliquer les concepts qui sous-tendent une recommandation.

---

## 3 — Setup technique

### 3.1 Stations de travail

**PC Desktop principal (studio) :**
- OS : Windows 11
- CPU : AMD Ryzen 9 5900XT
- RAM : 64 GB
- GPU : NVIDIA RTX 5070 Ti 16 GB
- Audio output : Sonos Arc Ultra
- Display : LG C2 65"
- Usage : sessions de production longues, mix/mastering, dev (Claude Code, Mix Analyzer)

**Laptop secondaire (mobile) :**
- Modèle : Lenovo Legion 5i Gen9
- CPU : Intel i9-14900HX
- RAM : 32 GB DDR5
- GPU : NVIDIA RTX 4070 8 GB
- Usage : production en déplacement, prototyping

### 3.2 Interface audio et écoute

**Interface audio :** Focusrite Scarlett 2i2 3rd gen
**Microphones :** Blue Spark (condensateur grand-membrane), Shure SM57 (dynamique)

**Écoute :** à confirmer en session si pertinent (moniteurs studio, casque, écoute Sonos Arc pour validation grand public).

### 3.3 Contrôleurs MIDI et hardware

**Synthétiseur principal :** Novation Summit (60-voix, hardware analog/digital hybride)

**Contrôleurs MIDI :**
- Novation Launch Control XL3 (faders/encoders pour mixer Live)
- Arturia BeatStep Pro (séquenceur)
- Novation Launchpad Pro MK3 (clip launching, drum programming)

**Accessoire :** iFi iDefender+ (isolation USB pour réduire bruits de masse)

**Note Launchpad :** latence diagnostiquée comme PDC projet-spécifique, à surveiller en session intensive.

### 3.4 DAW principal

**Ableton Live 12 Suite + Max for Live**

Choix justifié par :
- Workflow non-linéaire (Session view + Arrangement)
- Automation système robuste et auditable
- Max for Live pour modulateurs avancés (LFO, Envelope Follower, Shaper, Drift)
- Mappage programmatique des devices natifs (consommé par Mix Analyzer)
- Stabilité long-terme

**DAW secondaire potentiel :** Reaper (utilisé pour le projet *Summit Infinite* ~70 pistes, actuellement en pause). Si reprise, workflow stem bounce WAV 24-bit avec point de départ synchronisé, structure groupe/bus prébâtie dans Ableton avec color coding.

### 3.5 Arsenal plugins disponible

**Évaluation globale :** stack déjà au niveau professionnel. Pro-Q 4 a été identifié comme seul achat prioritaire pertinent et acquis. Pro-L 2 noté comme upgrade futur potentiel pour remplacer Smart:Limiter sur master (oversampling/dither).

**EQ et processing fréquentiel :**
- **Ableton EQ Eight (natif)** — **plugin par défaut pour les corrections pilotées par Mix Analyzer / CDE / Features 1-8.** Mappé programmatiquement, automatisable avec précision totale. Voir section 4 pour la rationale.
- FabFilter Pro-Q 4 (acquis) — disponible avec Dynamic EQ, Collision Detection. Utilisé en complément quand le besoin dépasse les capacités d'EQ Eight ou pour analyse spectrale visuelle.
- MEqualizer (Melda) — option additionnelle légère

**Saturation et color :**
- **FabFilter Saturn 2** — plugin saturation principal. Couvre entièrement le besoin. Decapitator considéré comme inutile dans ce contexte.
- JMG Sound CyberDrive — drive caractéristique
- United Plugins — bundle complet disponible

**Compression et dynamique :**
- Sonible smart:Comp — compression adaptative
- Sonible smart:Limiter — limiter actuel sur master (Pro-L 2 envisagé en upgrade)
- Sonible smart:EQ — EQ adaptatif pour références
- Sonible smart:Reverb — reverb adaptative
- Drawmer S73 — multibande compression style hardware

**Sound design et synthèse :**
- **Xfer Serum 2** — synthé wavetable principal, mid-bass et sound design
- **Spectrasonics Omnisphere + Omnisphere FX** — synthé pads/textures, FX module séparé
- Ableton Operator (natif) — sub-bass, sounds simples
- Ableton Wavetable (natif) — sound design spécifique

**Drums et percussions :**
- Native Instruments Kontakt 7 avec libraries : Ambigus, Antibruit Machine, Apocalypse Elements, Glitch Hero, Hyperion
- Approche actuelle : **percussions par one-shots manuels** plutôt que drummers virtuels (Superior Drummer jugé trop invasif pour l'esthétique Qrust)

**Vocal processing :**
- iZotope Nectar 3 — chaîne vocale complète
- iZotope VocalSynth 2 — vocal synthesis et effets
- iZotope RX7 Breath Control — nettoyage breaths

**Sidechain et utilities :**
- **Cableguys Kickstart 2** — sidechain principal (consommé par Feature 1.5 future)
- Wavesfactory Trackspacer 2.5 — séparation kick/basse, EQ ducking
- Note technique : track kick MIDI doit rester active jusqu'au bounce des sidechains dépendants

**Reverb et delay :**
- Sonible smart:Reverb
- Valhalla Supermassive — reverb caractéristique gratuit
- iZotope Trash 2 — distortion creative

**Mastering tools :**
- iZotope EZmix — utilisé pour références et exploration
- iZotope EZbass — basse rapide pour démos
- Lancaster Pulse — limiter caractère

**Plugins sons spécifiques :**
- Pluralis (effet)
- Rhythmizer Fusion — patterns
- IK Multimedia AmpliTube 5 Lite — guitare

**À noter pour Claude Code :**

Quand une recommandation implique un plugin, **prioriser le plugin de l'arsenal d'Alexandre offrant la meilleure qualité sonore avant de considérer l'impact CPU**. Les machines (PC Desktop notamment) ont la puissance pour absorber des chaînes lourdes.

---

## 4 — Philosophie de production (invariant à tous les projets)

### 4.1 Principe fondamental — Traitement dynamique par défaut

**Pour tout projet Qrust, aucun traitement spectral ne doit être figé sans justification documentée.**

Toute correction, coupure, enhancement ou shelf doit être piloté par automation contextuelle qui tient compte de :

- La section musicale active
- Ce que la track fait réellement à ce moment
- Ce que les autres tracks font en parallèle
- Les peaks audio détectés dans l'audio réel

**Règle par défaut :** dynamique contextuelle.

**Exceptions argumentées autorisées (3 cas stricts) :**

1. **Sub-sonique hors spectre audible (< 20 Hz)** — nettoyage fonctionnel des zones inaudibles
2. **Ultra-sonique hors spectre audible (> 20 kHz)** — symétrique
3. **Parasites constants connus** (60 Hz secteur, interférence documentée) — avec traçabilité de la source

**Toute autre coupure ou enhancement est contextuel.**

**Justification de cette philosophie :**

Une coupure statique fige un compromis moyen qui n'est optimal nulle part dans le morceau. Le traitement dynamique permet une décision optimale à chaque moment. Voir section 4.4 pour l'approche avant-gardiste qui sous-tend ce choix.

### 4.2 Règle "max 3 EQ8 correctifs par track"

**Convention Qrust pour tous les projets :**

Chaque track porte au maximum **3 EQ8 correctifs**, organisés par rôle épistémique distinct :

**EQ8 Static Cleanup** — rarement présent. Contient uniquement les 3 exceptions statiques documentées (rumble, ultra-sonique, parasite). Souvent absent dans un projet Qrust idéal.

**EQ8 Peak Resonance** — automations dynamiques multi-bandes sur peaks spectraux de la track individuelle. Généré par Mix Analyzer via `write_resonance_suppression`. Suit les peaks qui émergent à travers tout le morceau sur la track seule.

**EQ8 CDE Correction** — corrections ciblées Mix Analyzer CDE pour résoudre des conflits masking ou accumulation inter-track. Généré par Feature 1 CLI.

**EQ8 Musical Enhancement** (optionnel, 4ème EQ8 autorisé mais non correctif) — enhancement créatif placé après les effets non-correctifs. Généré par Feature 7 quand livrée.

**Ordre conventionnel dans la device chain :**

`Static Cleanup → Peak Resonance → CDE Correction → Saturation → Compression → Sidechain → Musical Enhancement → Glue → Limiter`

**Pourquoi séparation plutôt que consolidation :**

- Bypass indépendant de chaque étape
- Clarté sur qui a fait quoi dans l'audit
- Revert granulaire possible
- Pas de risque de casser le travail précédent
- Permet aux features (1, 6, 7) de cibler leur EQ8 sans interférer

**Si une track dépasse 3 EQ8 correctifs après plusieurs sessions, Feature 8 (EQ8 Consolidation) doit être appliquée.**

### 4.3 Préférences workflow

**Approche track-par-track recommandée par défaut.**

Pour les phases touchant plusieurs tracks (Phase 2 Feature 1, Phase 3 Feature 6, Phase 6 Feature 7), préférer un traitement track par track avec validation après chaque, plutôt qu'un batch multi-track.

**Justification :** un essai antérieur de batch sur 4 tracks a généré des erreurs. Frileux à recommencer le batch tant qu'une maîtrise du workflow track-par-track n'est pas établie sur plusieurs tracks consécutifs.

Le batch n'est acceptable qu'après plusieurs tracks validées en single mode et démonstration de stabilité.

**Philosophie générale :** itération sur vitesse, pas vitesse sur itération. Une phase claire à la fois. Livrer, juger, ajuster, passer à la suivante.

### 4.4 Approche avant-gardiste — EQ Eight + automation précise

**Choix stratégique délibéré :** EQ Eight natif piloté par automation précise est préféré aux plugins commerciaux dynamiques (Pro-Q 4 Dynamic, soothe2, Gullfoss) pour les corrections pilotées par Mix Analyzer / CDE / Features 1-8.

**Rationale :**

| Axe | Plugins commerciaux dynamiques | EQ Eight + automation Mix Analyzer |
|---|---|---|
| Transparence | Boîte noire DSP propriétaire | Courbes visibles, modifiables |
| Contrôle | Algorithme adaptatif fixe | Chaque automation modifiable manuellement |
| Auditabilité | Difficile à reverse-engineer | Lisible dans le .als XML |
| Réversibilité | Bypass on/off uniquement | Bypass par bande, par section, par feature |
| Cohérence avec analyse amont | Indépendant | Drive direct par Mix Analyzer |
| Coût licence | Récurrent | Inclus dans Live Suite |

**Le fait que cette approche soit rare dans l'industrie ne la disqualifie pas — c'est un angle commercialisable à terme.** L'objectif n'est pas seulement "que ça sonne bien sur un morceau" mais "construire un outil qui pourrait servir d'autres producteurs industrial à terme".

**Implication pour Claude Code :**

Quand tu implémentes une feature qui touche au traitement spectral, **toujours privilégier la solution qui s'inscrit dans cette philosophie** : EQ Eight natif + automations précises lisibles dans le .als plutôt que paramétrage opaque d'un plugin commercial.

---

## 5 — Règles de collaboration avec l'IA

### 5.1 Format de réponse attendu

**Structure systématique : Diagnostiquer → Options → Recommandation → Étapes cliquables.**

Pas de liste molle. Pas de "voici plein d'options à explorer". Structurer toute proposition selon ce flux :

**Diagnostic** — quel est le problème, mesuré ou observé, factuellement.

**Options** — 2 à 4 chemins possibles, chacun avec ses trade-offs explicites (avantages/inconvénients).

**Recommandation** — une option recommandée avec justification claire.

**Étapes cliquables** — instructions précises pour exécuter (chemin de menus, noms de boutons, paramètres exacts).

### 5.2 Précision des étapes cliquables

Quand une étape implique une action dans Ableton ou un plugin :

**Obligatoire :**
- Nom exact du menu/sous-menu
- Nom exact du bouton/paramètre
- Valeur précise à entrer (avec unité)
- Position relative dans l'interface si pertinent ("en haut à droite", "panneau de gauche")

**Si l'emplacement est incertain :**
- Demander une capture d'écran à l'utilisateur plutôt que deviner
- Ne pas inventer un chemin de menu

### 5.3 Liens vers documentation officielle

**Obligatoire :** quand une recommandation implique un plugin, une fonctionnalité ou un concept qui a une page officielle, **inclure le lien direct vers la page documentation pertinente** (pas juste la homepage du produit).

**Exemples :**
- Pour Pro-Q 4 Dynamic EQ : lien vers la page du manuel FabFilter qui décrit Dynamic EQ, pas juste fabfilter.com
- Pour un module Max for Live : lien vers la documentation Ableton du device
- Pour une technique : lien vers un tutoriel reconnu (Sound on Sound, ADSR, etc.)

### 5.4 Liens vers articles d'achat

**Si une recommandation implique l'achat d'un plugin ou d'un produit :**

- Lien direct vers l'article sur le site officiel du fabricant (pas Amazon, pas revendeur tiers)
- Préciser le prix au moment de la recommandation si visible

### 5.5 Chaînes d'effets

**Mode standard par défaut :** ordre conventionnel respecté (EQ correctif → saturation → compression → sidechain → glue → limiter, voir section 4.2).

**Mode "Crazy" sur demande explicite uniquement :** combinaisons inattendues, sortir des conventions. À ne jamais proposer spontanément — uniquement si l'utilisateur demande explicitement "mode crazy" ou "approche non-conventionnelle".

### 5.6 Choix de plugins

**Hiérarchie de priorité :**

1. **Qualité sonore avant tout** — choisir le plugin de l'arsenal qui produit le meilleur résultat pour le besoin
2. **Impact CPU en second** — les machines ont la puissance, ne pas sacrifier la qualité par peur du CPU sauf cas extrême
3. **Mappage programmatique en troisième** — pour les corrections automatisées par Features 1-8, EQ Eight natif est préféré (voir section 4.4)

### 5.7 Pattern à surveiller — Sur-optimisation

**Tendance identifiée chez Alexandre :** propension à sur-optimiser, reconfigurer, explorer des alternatives au lieu de **produire et finir**.

**Rôle de l'IA :**

- Aider à figer des versions stables et avancer
- Rappeler que finir Acid Drops (ou tout projet en cours) prime sur les changements d'infrastructure
- Décourager les achats de plugins ou les refactoring tant que le projet courant n'est pas livré
- Proposer une décision claire plutôt qu'élargir le space d'options quand l'utilisateur hésite

**Quand l'utilisateur évoque une optimisation potentielle qui n'est pas critique pour finir le projet courant :**

Réponse type : "Cette optimisation est intéressante mais pas critique pour finir [projet en cours]. Je propose qu'on la note pour après livraison. Continuons sur [tâche actuelle]."

### 5.8 Ton de communication

**Communication en français québécois standard.** Zéro jargon France ("plouc", "kiffer", etc. à éviter). Sacres dosés acceptables si naturels au contexte.

**Tolérance zéro pour :**
- Bullshit, survente, flatterie creuse
- Hedging excessif ("peut-être", "probablement" quand la donnée est claire)
- Défense réflexive d'une décision rejetée par l'utilisateur

**Direct et structuré :**
- Pas de préambule inutile
- Aller à la décision rapidement
- Justifier sans s'excuser

### 5.9 Honnêteté inconfortable préférée à la réassurance

Alexandre a un rapport philosophiquement lucide et critique à l'IA. Il préfère :

- Une honnêteté inconfortable à une réassurance lisse
- Un push back justifié à un acquiescement réflexe
- Une admission d'incertitude à une affirmation faussement confiante
- Une question clarifiante à une interprétation hasardeuse

**Si tu es en désaccord avec l'utilisateur, le dire** — avec le raisonnement complet. C'est ce qui est attendu, pas l'inverse.

### 5.10 Pas de mémoire implicite

**À toute IA conversationnelle :** tu n'as pas de mémoire persistante entre sessions. Avant de prétendre te souvenir d'un détail technique précis, vérifier dans les documents partagés.

**Si une information dont tu as besoin n'est pas dans les documents partagés, demander à l'utilisateur.** Ne pas inventer.

---

## 6 — Patterns à favoriser et à éviter

### 6.1 À favoriser

**Travail incrémental validé :** une décision à la fois, validée à l'oreille ou au mesure, avant de passer à la suivante.

**Documentation au fil de l'eau :** chaque décision technique entrée dans le `<project>_CHANGELOG.md` immédiatement, pas en fin de session.

**Préservation du travail antérieur :** ne jamais écraser ou modifier le travail validé de sessions antérieures sans changelog explicite.

**Réversibilité systématique :** backup avant modification, possibilité de revert à tout moment.

**Précision quantitative :** quand tu peux mesurer, mesurer. Quand tu peux nommer une fréquence en Hz, le faire.

**Test à l'oreille comme arbitre final :** toutes les métriques du monde ne remplacent pas l'écoute. L'oreille de l'utilisateur tranche en dernier ressort.

### 6.2 À éviter

**Batch multi-track non validé :** sauf workflow maîtrisé, traiter une track à la fois.

**Accumulation d'EQ8 sans consolidation :** respecter la règle 3 max par track. Si on dépasse, soit on consolide (Feature 8), soit on justifie.

**Modifications silencieuses :** chaque changement doit être tracé dans le changelog.

**Refactoring d'infrastructure pendant qu'un projet est en cours de livraison :** finir le projet courant avant de toucher aux outils.

**Sur-explication des concepts maîtrisés :** Alexandre est avancé en synthèse et hardware. Pas besoin de réexpliquer ce que fait un LFO ou comment fonctionne une wavetable.

**Évitement du push back justifié :** dire "oui Alexandre" quand un désaccord serait utile est une forme de paresse intellectuelle, pas de respect.

---

## 7 — Outils du projet Mix-Analyzer (référence rapide)

### 7.1 Documents de référence à consulter

Pour toute session sur un projet musical Qrust :

**Toujours :**
1. `qrust_professional_context.md` (ce document)
2. `documentation_discipline.md` (règles de rédaction si modification de documents)
3. `mix_engineer_brief_v<latest>.md` (méthodologie mix/mastering)

**Spécifique au projet courant :**
4. `project_<projet>_context.md` (contexte du projet : genre, targets, état)
5. Le fichier `.als` du projet
6. Le rapport Mix Analyzer Excel le plus récent
7. Le JSON diagnostics CDE si disponible
8. Le `<project>_CHANGELOG.md` pour l'historique des sessions

**Référence outils :**
9. `genre_music_profiles.json` (calibration par genre)
10. `ableton_devices_mapping_v<latest>.json` (mapping programmatique des devices)
11. `roadmap_features_1_8.md` pour l'état d'avancement des features Mix-Analyzer

### 7.2 Features Mix-Analyzer disponibles

**Livrées et utilisables :**
- Mix Analyzer core (analyse spectrale, métriques, sheets Excel)
- TFP (Track-Function-Profile) — classification des rôles
- CDE (Correction Decision Engine) — diagnostics inter-track structurés
- Feature 1 CLI (`apply_cde_corrections.py`) — application automatique des corrections EQ
- Peak Resonance generator (`write_resonance_suppression`) — automations multi-bandes par track

**En roadmap (specs disponibles) :**
- Feature 1.5 (sidechain auto-apply via Kickstart 2)
- Feature 6 (HPF/LPF dynamique par section)
- Feature 7 (enhancement musical dynamique)
- Feature 8 (consolidation EQ8)

Voir `roadmap_features_1_8.md` pour détails et ordre suggéré.

---

## 8 — Évolution de ce document

### 8.1 Quand mettre à jour ce document

Ce document est **invariant** par nature. Il évolue seulement quand :

- Le setup technique d'Alexandre change significativement (nouvel arsenal, nouveau hardware majeur)
- Une nouvelle règle de collaboration est identifiée et validée
- Une philosophie de production évolue (rare — la philosophie 100% dynamique est censée tenir longtemps)
- Un nouveau pattern récurrent est identifié et mérite documentation

### 8.2 Quand NE PAS mettre à jour ce document

Ce document **ne change pas** quand :

- Un nouveau projet musical démarre (créer un `project_<nom>_context.md` à la place)
- Les targets changent pour un projet (project context, pas professional)
- Une décision créative spécifique est prise (changelog du projet, pas ce document)
- Une feature Mix-Analyzer est livrée (mettre à jour `roadmap_features_1_8.md` à la place)

### 8.3 Procédure de mise à jour

Suivre la procédure définie dans `documentation_discipline.md` section 4 :

1. Lire ce document intégralement
2. Identifier précisément ce qui doit changer
3. Si suppression ou restructuration → demander confirmation
4. Modifier in-place en préservant l'existant
5. Incrémenter version + enrichir historique
6. Signaler nouveautés avec annotation "(nouveau en v<version>)"
7. Tester complétude
8. Archiver ancienne version dans `docs/archive/`
9. Livrer avec annonce de changements

### 8.4 Historique d'évolution

**v1.0 — Création initiale (2026-04-23)**
- Document fondateur, séparé du `qrust_artistic_context_v1_1.md` qui mélangeait identité professionnelle et paramètres projet Acid Drops
- Identité professionnelle de l'artiste posée
- Setup technique complet documenté (PC Desktop, laptop, hardware, plugins)
- Philosophie de production invariante (dynamique par défaut, 3 EQ8 max, EQ Eight + automation)
- 10 règles de collaboration avec l'IA formalisées (issues des userMemories d'Alexandre)
- Patterns à favoriser et à éviter
- Référence aux outils Mix-Analyzer disponibles
- Procédure d'évolution du document

---

## 9 — Référence rapide (quick card)

**Ce document est :** le socle invariant pour tous les projets Qrust.

**Ce document n'est pas :** le contexte d'un projet spécifique (voir `project_<nom>_context.md`).

**Pour démarrer une session de mix/mastering :**
1. Charger ce document
2. Charger le project context du projet courant
3. Charger le brief méthodologique le plus récent
4. Charger les fichiers du projet (.als, rapport Mix Analyzer, diagnostics CDE)

**Règles d'or invariantes Qrust :**
- Traitement dynamique par défaut (3 exceptions statiques seulement)
- Maximum 3 EQ8 correctifs par track (+1 Musical Enhancement optionnel)
- Track-par-track avant batch
- Format réponse : Diagnostic → Options → Recommandation → Étapes cliquables
- Étapes cliquables précises (chemins menus, noms boutons, valeurs exactes)
- Liens vers doc officielle des plugins recommandés
- Honnêteté inconfortable > réassurance lisse
- Finir le projet courant avant refactoring d'infrastructure

---

**Fin du document `qrust_professional_context.md` v1.0. Document permanent, applicable à tous les projets Qrust. Mise à jour selon la procédure définie en section 8.**
