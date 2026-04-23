# Template de démarrage de session — mix / mastering

**Usage :** Copier-coller le contenu ci-dessous dans une nouvelle conversation Claude (type Claude.ai avec code execution et file upload), en remplaçant les éléments entre `[CROCHETS]` et en joignant les fichiers listés.

Ce template garantit que chaque session démarre avec le même niveau de contexte et la même discipline méthodologique.

---

## Message de démarrage à copier-coller

Bonjour. Je démarre une nouvelle session de mix / mastering pour mon projet. Voici le contexte et les fichiers.

### Référence méthodologique

Je joins deux fichiers de référence que tu dois lire en priorité avant toute analyse :

1. `mix_engineer_brief_v2.md` — Méthodologie complète : rôle, philosophie, 4 checks holistiques, workflow en 3 étapes, architecture de phases, guardrails, livrables. Cette directive est la règle pour toute la session.

2. `qrust_artistic_context.md` — Identité artistique de l'artiste Qrust (targets loudness, width, références musicales, philosophie de production, ce qui est sacré / négociable / banni).

**Tu dois lire ces deux fichiers intégralement avant de me répondre. Tu dois suivre strictement le workflow défini en Section 3 du brief : analyse profonde d'abord, puis la réponse en 5 parties structurée (A État, B Likes, C Recalibration, D Plan sommaire, E Questions de décision). Pas de propositions de modifications dans la première réponse.**

### Inputs du projet

**Projet .als :** [nom_du_fichier.als] (gzippé Ableton Live 12)

**Rapport Mix Analyzer :** [nom_du_rapport.xlsx] (dernier bounce propre)

**Diagnostics CDE :** [nom_du_diagnostics.json] (si disponible — sortie de `cde_engine.py`)

**Device mapping :** [ableton_devices_mapping_vX_Y.json] (version courante)

### Contexte projet courant

**Nom du projet :** [Acid Drops / Summit Infinite / autre]

**Genre perçu :** [Industrial / dark electro / autre]

**Intention artistique :** [Décrire en 2-3 phrases ce que le track doit faire ressentir — ex: "Pression physique en club, mais intelligibilité des textures préservée. Le kick doit exploser, les leads acid doivent mordre sans agresser."]

**Préoccupations spécifiques :** [Liste les points qui t'inquiètent — ex: "Le mix sonne trop mono. Le kick manque de punch dans Drop 2. Les chorus 1 et 2 sont brouillons."]

**Plateforme de release :** [SoundCloud / DistroKid / club DJ pool / toutes]

**Target loudness :** [-10 LUFS club principal + -14 LUFS Spotify secondaire / autre selon qrust_artistic_context.md]

### Historique et modifications antérieures

[CHOISIR UNE OPTION :]

**Option A — Règle zero-baseline (recommandé si historique incertain) :**
J'ai modifié des éléments manuellement entre sessions sans changelog tracé. Faders, devices, routing ont pu bouger. Applique la règle zero-baseline de la Section 5.2 du brief : rejette toute proposition antérieure comme obsolète, audite la chaîne actuelle, reconstruis le plan à partir de l'état présent.

**Option B — Historique tracé :**
Voici le changelog des modifications antérieures : [pointer vers `<project>_CHANGELOG.md` ou décrire brièvement]. Tu peux prendre en compte ces modifications, mais audite-les quand même avant de faire confiance (règle 5.1).

**Option C — Projet neuf :**
Ce projet n'a jamais été traité par un AI. Pars du mix actuel comme baseline authoritative.

### Outils Feature 1 disponibles

Le CLI `scripts/apply_cde_corrections.py` est livré et utilisable. Il consomme le JSON diagnostics et applique automatiquement les corrections EQ programmatiques (static_dip, musical_dip, reciprocal_cuts). Je peux l'invoquer pour toi via back-and-forth — tu me donnes les paramètres, je lance, je te reviens avec le résultat.

**Les approches sidechain des diagnostics sont hors scope Feature 1** (Feature 1.5 à venir). Pour les cas sidechain identifiés, les recommandations restent manuelles via Kickstart 2 ou trigger routing Live natif.

### Démarrage

Lis le brief v2, lis le contexte artistique, lis le .als, lis le rapport Mix Analyzer, lis le JSON diagnostics, lis le device mapping. Puis livre-moi ta réponse en 5 parties structurée selon Section 3 Étape 2 du brief.

Attends mes réponses aux questions de décision avant de proposer un plan d'exécution détaillé. Effort maximum, précision primordiale.

---

## Guide d'adaptation du template

### Éléments à remplacer systématiquement

**[nom_du_fichier.als]** — Le .als du projet courant. Attention aux noms avec espaces (mettre entre guillemets si chemin).

**[nom_du_rapport.xlsx]** — Le dernier rapport Mix Analyzer. Préférer le plus récent possible, et s'il n'est pas fresh, générer un nouveau bounce avant la session.

**[nom_du_diagnostics.json]** — Produit par `cde_engine.py`. Peut manquer si le projet n'a pas encore été analysé par CDE — dans ce cas, le signaler explicitement.

**[ableton_devices_mapping_vX_Y.json]** — Version courante. Vérifier dans le repo Mix-Analyzer pour la dernière.

**[Nom du projet]** — Acid Drops, Summit Infinite, nouveau projet, etc.

**[Genre perçu]** — Peut être recalibré par Claude en Section C de sa réponse. Honnêteté sur le ressenti.

**[Intention artistique]** — Description courte, pas un roman. Deux à trois phrases suffisent.

**[Préoccupations spécifiques]** — Les points où ton oreille sent que quelque chose ne va pas. Même sans diagnostic précis, partager l'intuition.

**[Plateforme de release]** — Conditionne les targets loudness et les chaînes master.

**[Target loudness]** — Référer au contexte artistique pour Qrust. Pour autres projets, définir explicitement.

### Éléments à adapter selon le contexte

**Section "Historique" :** Choisir entre A, B, C selon l'état réel du projet. En cas de doute, A (zero-baseline) est le choix safe.

**Section "Outils Feature 1" :** Adapter selon l'état de livraison des features. Si Feature 1.5 est livrée, la mentionner. Si Feature 2 (Q dynamique) livrée, aussi.

**Section "Démarrage" :** Peut être raccourcie à "Démarre l'analyse." si le contexte est déjà dense.

### Quand NE PAS utiliser ce template

- **Microtweaks d'une session en cours** — Pas besoin de rebootstrapper, continuer la conversation existante.
- **Questions techniques isolées** — Si tu veux juste demander comment appliquer un sidechain, pas besoin de lancer une session complète.
- **Exploration créative** — Si tu cherches des idées de sound design, de structure, ce template est trop formel.

---

## Checklist avant de copier-coller

Avant de démarrer une session avec ce template, vérifier :

- [ ] Les 2 fichiers de référence sont à jour (`brief_v2.md`, `qrust_artistic_context.md`)
- [ ] Le `.als` est un bounce propre récent (pas une version WIP cassée)
- [ ] Le rapport Mix Analyzer a été généré sur le .als courant (vérifier timestamp)
- [ ] Le JSON diagnostics correspond au même .als que le rapport (même timestamp idéalement)
- [ ] Si règle zero-baseline : avoir en tête que les propositions d'anciennes sessions seront ignorées
- [ ] Si historique tracé : changelog à jour et joint
- [ ] Intention artistique formulée en 2-3 phrases
- [ ] Préoccupations spécifiques listées avec intuition honnête
- [ ] Target loudness clair (primary + secondary si dual delivery)
