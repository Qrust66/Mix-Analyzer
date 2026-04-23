# Documentation Discipline — Règles de rédaction partagées

**Version :** 1.0
**Date :** 2026-04-23
**Statut :** Permanent, partagé par les 3 intervenants du projet Mix-Analyzer

**À l'attention de :** Alexandre Couture, toute IA conversationnelle (Claude Opus en session), toute IA d'exécution (Claude Code), et tout futur collaborateur humain ou IA.

---

## 1 — Contexte et nécessité

### 1.1 Le triangle d'intervenants

Le projet Mix-Analyzer + Corrector Qrust est développé par **trois intervenants** qui collaborent de manière asynchrone et se succèdent dans le temps :

**Alexandre Couture** — auteur du projet, juge final, utilisateur de l'outil, décideur sur l'architecture et les priorités. Garde la vision artistique et technique.

**L'IA conversationnelle (Claude Opus)** — partenaire de lucidité, architecte d'options, rédacteur des documents, traducteur de la vision en spécifications techniques. Varie d'une session à l'autre (nouvelles conversations, nouvelles instances). N'a pas de mémoire persistante au-delà de ce qui est documenté.

**L'IA d'exécution (Claude Code)** — exécutant technique, développeur, manipulateur des fichiers sources, responsable de l'implémentation fidèle des specs. Varie également d'une session à l'autre.

### 1.2 Pourquoi cette discipline est critique

Les trois intervenants ne travaillent **jamais ensemble en temps réel**. Ils communiquent via :

- Les documents du repo (briefs, contextes, specs, changelogs)
- Les commits git et leurs messages
- Les conversations passées qu'un intervenant peut relire mais pas modifier
- L'état actuel du code et des fichiers

**Chaque document est un point de rendez-vous partagé.** Si un document est incomplet, ambigu, ou dégradé :

- Alexandre perd la trace de décisions validées dans des sessions antérieures
- L'IA conversationnelle (en nouvelle session) redécouvre des règles sans comprendre leur justification
- L'IA d'exécution peut prendre des décisions incohérentes avec l'intention d'origine
- Le projet perd en cohésion et accumule de la dette documentaire

### 1.3 Le standard visé

Le projet vise un **"travail exemplaire, élégant, inspirant, qui fonctionne du premier coup"**. Ce standard s'applique au code **et à la documentation**. Une documentation dégradée sabote la qualité du code qu'elle encadre.

**"Fonctionne du premier coup"** signifie notamment : quand Claude Code reçoit un document de spec, il peut implémenter la feature sans avoir à deviner, inférer, ou demander clarification sur des points qui auraient dû être explicites.

---

## 2 — Règles permanentes de rédaction

### 2.1 Jamais condenser silencieusement

**Interdit :** raccourcir, simplifier, résumer, ou reformuler un document existant sans annonce explicite.

**Obligatoire :** si une section est raccourcie ou reformulée, le signaler explicitement dans l'historique d'évolution du document et justifier pourquoi.

**Cas concret :** le brief v2.1 faisait 35 Ko. Une première tentative de brief v2.2 faisait 16 Ko — résultat d'une condensation silencieuse non annoncée. Cette réduction a perdu des détails validés : format `CorrectionDiagnostic`, règles de sécurité d'écriture .als, exemples de Phase 2, etc. La version correcte du brief v2.2 préservait les 35 Ko du v2.1 et ajoutait par-dessus pour atteindre ~45 Ko.

### 2.2 Préserver intégralement les versions antérieures

**Principe :** une nouvelle version d'un document est l'ancienne version **intégrale** plus les additions et modifications signalées.

**Interdit :**
- Supprimer une règle d'une version précédente sans marquer "(obsolète en vX.Y, remplacée par section Z)"
- Réécrire from scratch sur la base d'un résumé mental — toujours partir du document existant
- Supprimer des exemples concrets "parce qu'ils sont évidents" — s'ils étaient nécessaires à la version N, ils le sont à la version N+1

**Obligatoire :**
- Ouvrir le document précédent, le lire intégralement avant modification
- Appliquer les changements par additions et modifications in-place
- Si une section doit être supprimée, la marquer explicitement obsolète plutôt que la retirer

**Exception :** correction d'une erreur factuelle clairement identifiée (ex: un chemin XML faux). Dans ce cas, la correction est mentionnée dans l'historique d'évolution avec l'ancienne valeur et la nouvelle.

### 2.3 Signaler explicitement les nouveautés et modifications

**Format obligatoire dans le document :**

- Nouvelle section : `## Section X — Titre (nouveau en vX.Y)`
- Nouveau paragraphe dans section existante : `**Sous-titre (nouveau en vX.Y)**`
- Règle ajoutée : `### 5.X Règle XXX (nouveau en vX.Y)`
- Contenu modifié (pas juste ajouté) : commenter explicitement "Modifié en vX.Y : ancienne formulation remplacée par..."

**Raison :** permet au lecteur (humain ou IA) de voir en un coup d'œil ce qui a évolué depuis la version précédente, sans avoir à faire un diff binaire.

### 2.4 Documenter même ce qui paraît évident

**Principe :** ce qui est évident à la rédaction pour l'intervenant courant n'est pas nécessairement évident pour les autres ou pour soi-même en session future.

**Interdit :**
- "Cette règle est évidente, je la passe"
- "C'est standard, tout le monde sait ça"
- "J'ai dit ça dans une section précédente, je ne répète pas"

**Obligatoire :**
- Documenter les règles même si elles paraissent triviales
- Répéter une règle critique dans plusieurs sections si c'est utile contextuellement
- Inclure des exemples concrets même pour les règles "simples"

**Raison :** les IA d'exécution (Claude Code) n'ont pas toujours le contexte implicite d'une conversation. Les Alexandre des sessions futures non plus (le cerveau humain oublie). La documentation doit être **autoportante**.

### 2.5 Signaler les coupures et demander confirmation

**Si un document commence à devenir très volumineux** et qu'une restructuration est envisagée :

**Interdit :** restructurer et couper silencieusement sous prétexte d'organisation.

**Obligatoire :**
1. Signaler à Alexandre : "Ce document atteint X Ko, je propose une restructuration qui impliquerait A, B, C"
2. Lister précisément ce qui serait déplacé, fusionné, ou coupé
3. Attendre validation explicite avant de procéder
4. Si restructuration validée, préserver le contenu original dans une archive `docs/archive/` avec le nom de la version

### 2.6 Tester la complétude avant de livrer

**Avant de considérer un document comme "prêt" :**

**Test du nouvel intervenant :** un intervenant neuf (humain ou IA) qui reçoit ce document seul (sans le contexte de la conversation courante) peut-il :

- Comprendre l'objectif du document ?
- Exécuter ce qui est demandé sans poser de questions sur des points non couverts ?
- Identifier où trouver les informations complémentaires si besoin ?

Si la réponse est "non" sur l'un de ces points, le document est incomplet — il faut compléter avant de livrer.

**Test appliqué aux specs de features :** un autre ingénieur (ou Claude Code) qui reçoit le spec peut-il implémenter la feature sans ambiguïté ? Les APIs, les dataclasses, les algorithmes, les cas limites sont-ils tous décrits ?

### 2.7 Archivage plutôt que suppression

**Quand une version devient obsolète :**

**Interdit :** supprimer le fichier de l'ancienne version.

**Obligatoire :**
- Déplacer l'ancienne version dans `docs/archive/`
- Renommer avec suffixe de version (ex: `mix_engineer_brief_v2_1.md`)
- Ajouter un header indiquant "ARCHIVÉ — remplacé par vX.Y" avec pointeur vers la nouvelle version

**Raison :** la traçabilité historique est précieuse. Un changement de décision peut avoir besoin d'être compris en remontant à la version qui justifiait l'ancienne décision.

---

## 3 — Règles spécifiques par type de document

### 3.1 Briefs et contextes artistiques

**Documents concernés :** `mix_engineer_brief_vX.Y.md`, `qrust_artistic_context_vX.Y.md`

**Règles spécifiques :**

- Toute modification incrémente la version (v1.0 → v1.1, v2.1 → v2.2)
- L'historique d'évolution en tête du document liste toutes les versions antérieures avec leurs ajouts principaux
- Les règles numérotées (ex: Section 5.1, 5.2, ...) ne sont **jamais renumérotées** — ajouter des règles en fin (5.9, 5.10, ...) plutôt que réorganiser
- Les exemples concrets (ex: "Diagnostic propose -5 dB → profil cap -2 → on applique -2") sont **sacrés** — jamais supprimés

### 3.2 Specs de features

**Documents concernés :** `feature_N.M_*.md`

**Structure minimale obligatoire pour toute spec de feature :**

1. Version spec + date + statut (planifiée / en cours / livrée)
2. Dépendances sur autres features
3. Effort estimé (heures + nombre de commits + nombre de tests)
4. Objectif et justification (quoi + pourquoi)
5. Inputs consommés (fichiers, données, paramètres) avec formats
6. Algorithme principal (pseudo-code ou description détaillée)
7. API publique (signatures de fonctions, dataclasses, types de retour)
8. CLI wrapper (si applicable) avec exemples de commandes
9. Plan de livraison découpé en micro-commits (anti-timeout)
10. Validation terrain (comment tester après livraison)
11. Risques techniques identifiés + mitigations
12. Hors scope (ce que la feature ne fait pas explicitement)
13. Dépendances de validation utilisateur avant dev (questions ouvertes à trancher)

**Si une de ces sections est absente, la spec est incomplète et doit être enrichie avant livraison.**

### 3.3 Roadmaps et documents d'orchestration

**Documents concernés :** `roadmap_features_1_N.md`, documents de planification globale

**Règles spécifiques :**

- Mise à jour après chaque livraison de feature majeure
- Tableau d'état d'avancement systématique (Livrées / En cours / Planifiées)
- Graphe des dépendances explicite (ASCII art ou description textuelle claire)
- Ordre de livraison suggéré avec justification
- Mention des documents associés pour chaque feature

### 3.4 Changelogs de session

**Documents concernés :** `changelog_session_YYYY-MM-DD.md`

**Règles spécifiques :**

- Un fichier par session majeure (pas un fichier par conversation)
- Liste exhaustive des documents créés, modifiés, archivés
- Commandes git suggérées pour appliquer les changements
- Pointeur vers la prochaine décision attendue

### 3.5 Changelogs de projet

**Documents concernés :** `<project>_CHANGELOG.md` (ex: `Acid_Drops_CHANGELOG.md`)

**Règles spécifiques :**

- Mise à jour obligatoire à chaque phase d'un projet de mix/mastering
- Format : un bloc par phase, horodaté
- Liste track par track, device par device, paramètre par paramètre, ancien/nouveau, raison
- Inclusion du Git SHA du Mix Analyzer utilisé pour traçabilité
- Inclusion du Mix Health Score avant/après quand disponible

---

## 4 — Procédure recommandée pour modifier un document

**Étape 1 — Lire le document existant intégralement.**

Ne jamais modifier en se basant sur un souvenir ou un résumé mental. Ouvrir le fichier et lire ligne par ligne.

**Étape 2 — Identifier précisément ce qui doit changer.**

Lister :
- Sections à étendre
- Sections à corriger (avec ancien contenu et nouveau)
- Sections à ajouter
- Exemples à ajouter
- Rien ne doit être supprimé sans justification explicite

**Étape 3 — Si suppression ou restructuration envisagée : demander confirmation.**

Voir règle 2.5. Ne jamais procéder sans validation explicite d'Alexandre.

**Étape 4 — Produire le nouveau document en préservant le contenu existant.**

Appliquer les changements par additions et modifications in-place, sans reformulation destructrice.

**Étape 5 — Incrémenter la version et enrichir l'historique.**

Mettre à jour le header de version et ajouter une entrée dans l'historique d'évolution listant les additions/modifications de cette version.

**Étape 6 — Signaler les nouveautés explicitement.**

Annotations "(nouveau en vX.Y)" sur chaque ajout.

**Étape 7 — Tester la complétude.**

Appliquer le "test du nouvel intervenant" (règle 2.6). Corriger les manques.

**Étape 8 — Archiver l'ancienne version.**

Déplacer le fichier précédent dans `docs/archive/` avec header d'archivage.

**Étape 9 — Livrer avec annonce de changements.**

Dans la conversation, annoncer : "Version vX.Y produite avec les changements suivants : [liste]. Archive de l'ancienne version placée dans docs/archive/."

---

## 5 — Mécanismes de contrôle

### 5.1 Taille des documents comme indicateur

**Règle simple :** un document vivant ne rétrécit jamais (ou alors avec annonce explicite).

**Si tu observes qu'un document v2.2 fait moins de Ko que sa version v2.1, c'est un signal d'alerte** — il y a probablement eu condensation silencieuse. Vérifier immédiatement.

**Seules exceptions légitimes de réduction :**
- Suppression explicite et annoncée d'une section obsolète (avec archivage de l'ancienne version)
- Consolidation de redondances internes explicite et annoncée
- Correction d'erreurs factuelles qui étaient répétitives

### 5.2 Diff git obligatoire avant commit

Avant de commiter une modification de document, **toujours examiner le diff git** pour vérifier que :

- Les suppressions sont intentionnelles et justifiées
- Aucun passage n'a été supprimé par inadvertance
- Les additions sont bien positionnées et signalées

Si une IA conversationnelle produit un document dans un environnement où git n'est pas disponible (ex: /mnt/user-data/outputs), faire le diff textuel manuel avant livraison.

### 5.3 Revue croisée

**Quand possible :** faire relire les modifications par un autre intervenant avant livraison finale.

Ex: une IA conversationnelle peut demander à l'utilisateur de vérifier qu'un document nouveau est bien complet avant le commit.

---

## 6 — Règles spécifiques à l'IA conversationnelle

**À destination explicite de toute instance de Claude Opus travaillant sur ce projet :**

### 6.1 Ne jamais faire confiance à ta mémoire implicite

Tu n'as pas de mémoire persistante. Ce que tu "sais" du projet vient exclusivement :
- Des documents qu'on te montre dans la conversation courante
- Des uploads de l'utilisateur
- Éventuellement d'une mémoire partielle via le mécanisme de userMemories (non fiable pour les détails techniques)

**Avant de modifier un document, toujours le lire dans sa version actuelle.** Ne jamais réécrire "de mémoire" ou "sur la base de ce que j'ai compris".

### 6.2 Résister à l'instinct de condenser

L'instinct de raccourcir est fort quand un document paraît long. C'est un **biais d'économie cognitive** à résister.

Quand tu te sens attiré par une formulation du type "je vais résumer cette section en quelques phrases" ou "je peux simplifier ce passage", **stop**. Vérifier contre les règles 2.1 et 2.2. Probablement faut-il préserver le contenu tel quel.

### 6.3 Annoncer les changements avant de les faire

Si tu envisages une modification significative d'un document, **annoncer à l'utilisateur ce que tu comptes faire avant de le faire**. Demander validation sur :

- Les sections qui seront touchées
- Les ajouts prévus
- Les suppressions ou restructurations éventuelles (doivent être rares)

Cela permet à l'utilisateur de corriger la trajectoire avant que le travail soit fait.

### 6.4 Signaler explicitement les incertitudes

Si tu n'es pas sûr qu'un passage du document existant doit être préservé tel quel ou modifié :

- **Demander.** Pas présumer.
- Expliquer pourquoi tu hésites.
- Laisser l'utilisateur trancher.

---

## 7 — Règles spécifiques à l'IA d'exécution (Claude Code)

**À destination explicite de toute instance de Claude Code travaillant sur ce projet :**

### 7.1 Les specs sont la vérité

Les specs de features (documents `feature_N.M_*.md`) sont la source de vérité pour l'implémentation. Si une spec dit "la fonction prend ces paramètres et retourne cette dataclass", c'est ce qui doit être implémenté.

**Ne pas inventer.** Si une spec est ambiguë, demander clarification avant de procéder.

### 7.2 Respecter le découpage en micro-commits

Chaque spec de feature contient un "Plan de livraison" avec micro-commits. Respecter ce découpage pour éviter les timeouts API et permettre les validations granulaires.

### 7.3 Ne pas modifier la documentation de spec pendant l'implémentation

Pendant l'implémentation, si tu découvres que la spec est erronée ou incomplète :

- **Ne pas modifier la spec en silence.**
- Signaler le problème dans la conversation avec Alexandre ou l'IA conversationnelle.
- Laisser Alexandre ou l'IA conversationnelle mettre à jour la spec si nécessaire.
- Continuer l'implémentation selon la spec corrigée.

### 7.4 Commits explicites

Chaque commit doit avoir un message clair qui référence la feature et le micro-commit du plan.

Format suggéré : `feat(NN): <micro-commit description>` où NN est le numéro de feature.

Exemples :
- `feat(6): per-section frequency computation helpers`
- `feat(7): intent dataclasses + config loader`

### 7.5 Tests obligatoires par micro-commit

Chaque micro-commit doit inclure ses tests associés (nombre indiqué dans le plan de livraison). Les commits de code sans tests associés sont à éviter.

---

## 8 — Règles spécifiques à Alexandre

**À destination explicite de toi-même Alexandre, pour tes futures sessions :**

### 8.1 Exiger la complétude

Tu as raison d'exiger que chaque document soit complet. C'est un standard professionnel, pas un caprice.

Quand tu observes une dégradation (taille suspecte, contenu perdu, imprécisions), **le signaler immédiatement**. L'IA conversationnelle corrigera.

### 8.2 Valider les changements avant commit

Quand l'IA conversationnelle livre un document modifié, **lire le changelog des modifications** avant de le commiter au repo.

Vérifier :
- Ce qui a été ajouté est bien signalé
- Ce qui a été modifié est justifié
- Rien d'essentiel n'a disparu silencieusement

### 8.3 Archiver plutôt que supprimer

Quand tu remplaces un document, déplace l'ancien dans `docs/archive/` plutôt que de le supprimer. La traçabilité historique est précieuse.

### 8.4 Commit granulaires et messages explicites

Même si tu travailles sur plusieurs documents à la fois, fais des commits séparés par groupe cohérent, avec messages explicites. Cela facilite les rollbacks éventuels et la lecture du git log.

---

## 9 — Sanction des violations

### 9.1 Si l'IA conversationnelle viole ces règles

Alexandre peut :
- Rejeter le document produit et exiger une nouvelle version complète
- Pointer explicitement la règle violée (référence à cette section)
- Demander une explication de pourquoi la règle a été violée

L'IA conversationnelle doit :
- Reconnaître la violation sans excuse défensive
- Produire immédiatement un document corrigé
- Identifier le biais qui a causé la violation pour s'en prémunir

### 9.2 Si Claude Code viole ces règles

Alexandre peut :
- Rejeter le commit et exiger un redo
- Demander à l'IA conversationnelle de revoir la spec si elle était ambiguë
- Revert le commit et reprendre depuis la dernière version propre

### 9.3 Prévention plutôt que sanction

L'objectif n'est pas de punir mais de **maintenir le standard**. La bonne réponse à une violation est toujours : reconnaissance, correction, mesure de prévention pour le futur.

---

## 10 — Évolution de cette discipline

### 10.1 Ce document est lui-même soumis à ses règles

Toute modification de ce `documentation_discipline.md` doit suivre les règles qu'il contient :

- Préservation intégrale des versions antérieures
- Signalement explicite des additions
- Archivage de l'ancienne version

### 10.2 Amendements

Si un intervenant identifie une règle manquante, ambiguë, ou contre-productive :

1. Proposer l'amendement à Alexandre via la conversation
2. Discuter de la formulation
3. Une fois validé, ajouter la règle avec annotation "(nouveau en vX.Y)"
4. Mettre à jour l'historique d'évolution

### 10.3 Historique d'évolution

**v1.0 — Création initiale (2026-04-23)**
- Document fondateur suite à la découverte d'une condensation silencieuse du brief v2.1 → v2.2
- Formalisation des principes de préservation intégrale, signalement explicite, test de complétude
- Règles spécifiques pour briefs, specs de features, roadmaps, changelogs
- Procédure de modification de document en 9 étapes
- Règles spécifiques par intervenant (IA conversationnelle, Claude Code, Alexandre)

---

## 11 — Référence rapide (quick card)

**Avant de modifier un document :**

1. ✅ Lire le document existant intégralement
2. ✅ Identifier précisément ce qui doit changer
3. ✅ Si suppression ou restructuration → demander confirmation à Alexandre
4. ✅ Modifier in-place en préservant l'existant
5. ✅ Incrémenter version + enrichir historique
6. ✅ Signaler nouveautés avec "(nouveau en vX.Y)"
7. ✅ Tester complétude (test du nouvel intervenant)
8. ✅ Archiver ancienne version dans docs/archive/
9. ✅ Livrer avec annonce de changements

**Red flags qui doivent déclencher une vérification :**

- ⚠️ Un document v2.2 plus petit que v2.1 en Ko
- ⚠️ L'envie de "résumer", "condenser", "simplifier"
- ⚠️ "Je vais réécrire ça plus proprement"
- ⚠️ "Cette section est évidente, je la passe"
- ⚠️ "J'ai dit ça plus haut, je ne répète pas"

**Mantra :**

*Dans le doute, préserver. La dette documentaire est plus coûteuse que la redondance.*

---

**Fin du document de discipline. Document permanent, à respecter par tous les intervenants du projet Mix-Analyzer + Corrector Qrust.**
