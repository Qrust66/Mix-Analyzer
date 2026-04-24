# Session Bootstrap Template

**Version :** 1.0
**Date de création :** 2026-04-23
**Statut :** Permanent, point d'entrée pour toute nouvelle session sur le projet Mix-Analyzer + Qrust
**Hérite de :** `documentation_discipline.md` (règles de rédaction)

**À l'attention de :** Alexandre Couture (auteur), toute IA conversationnelle (Claude Opus en session), toute IA d'exécution (Claude Code), tout futur collaborateur.

**Purpose :** garantir qu'aucune session ne démarre sur une base incomplète ou incorrecte. Centralise les checklists, templates de prompt, et rappels critiques pour les 3 types d'intervenants.

**Historique d'évolution :**
- v0 (avant 2026-04-23) — version initiale courte (126 lignes, 7 Ko) couvrant uniquement le cas mix/mastering avec un single template. Archivée comme `session_bootstrap_template_v0_ARCHIVED.md` pour traçabilité historique.
- v1.0 (ce document) — restructuration complète post-audit de l'architecture documentaire. Couvre 5 types de sessions (mix/mastering, dev feature, audit documentaire, planification, exploration), avec checklists pré-session et post-session par type, conventions de nommage, anti-patterns identifiés, structure repo. Conformité totale à `documentation_discipline.md`.

**Principe de préservation :** ce document évoluera au fil des apprentissages de session. Toute modification suit `documentation_discipline.md` section 4. Les ajouts seront annotés "(nouveau en vX.Y)".

---

## 1 — Quand utiliser ce document

### 1.1 Tu démarres une nouvelle conversation sur le projet Mix-Analyzer ou Qrust

**Action :** ouvrir ce document, identifier le type de session, suivre le template correspondant.

### 1.2 Tu reprends une session après pause prolongée

**Action :** suivre le template "Reprise de session" (Section 7) qui re-vérifie l'état du repo et des documents.

### 1.3 Tu onboardes un nouveau collaborateur

**Action :** lui faire lire ce document en premier, puis `documentation_discipline.md`, puis `qrust_professional_context.md`.

### 1.4 Tu fais une session courte / question rapide

**Action :** template "Quick question" (Section 8) — version allégée pour ne pas alourdir inutilement.

---

## 2 — Identification du type de session

Les 5 types de sessions identifiés et leur template correspondant :

| Type de session | Template | Documents à charger | Durée typique |
|---|---|---|---|
| **Mix / Mastering** sur un projet Qrust | Section 3 | Lourd | 1-2h |
| **Développement** d'une feature Mix-Analyzer | Section 4 | Lourd | 30 min - 2h |
| **Audit / Mise à jour documentaire** | Section 5 | Variable | 30 min - 1h |
| **Planification / Décision architecturale** | Section 6 | Léger | 30 min - 1h |
| **Exploration / Brainstorming** créatif | Section 8 | Très léger | Variable |

---

## 3 — Template : Session Mix / Mastering

### 3.1 Documents à charger (dans l'ordre)

**Couche méta (toujours) :**
1. `documentation_discipline.md` — règles de rédaction si modification de docs
2. `qrust_professional_context.md` v1.0 — socle invariant Qrust

**Couche méthodologique (toujours) :**
3. `mix_engineer_brief_v2_3.md` — méthodologie mix/mastering générique

**Couche projet (toujours) :**
4. `project_<nom_projet>_context.md` — contexte spécifique du projet

**Données techniques projet :**
5. Le fichier `.als` du projet (ex: `Acid_Drops_Sections_STD.als`)
6. Le rapport Mix Analyzer Excel le plus récent
7. Le JSON diagnostics CDE le plus récent
8. Le `<project>_CHANGELOG.md` pour l'historique des sessions

**Données techniques partagées :**
9. `genre_music_profiles.json` — calibration par genre × track type
10. `ableton_devices_mapping_v2_2.json` — mapping programmatique des devices

### 3.2 Template de prompt à copier

```
Hello Claude. Démarrage d'une session de mix/mastering sur le projet [NOM_PROJET].

Documents joints :
- qrust_professional_context.md (socle invariant)
- mix_engineer_brief_v2_3.md (méthodologie)
- project_[nom_projet]_context.md (contexte projet)
- [nom_projet].als (fichier Ableton)
- [nom_projet]_MixAnalyzer_[date].xlsx (rapport)
- [nom_projet]_diagnostics.json (diagnostics CDE)
- [nom_projet]_CHANGELOG.md (historique)
- genre_music_profiles.json (calibration genre)
- ableton_devices_mapping_v2_2.json (mapping devices)

Session number : [X] (relativement au projet)
Phase actuelle : [Phase 1 audit / Phase 2 fixes / Phase 3 HPF/LPF / etc.]
Modifications antérieures auditées : [oui / non / partiellement]

Préoccupations spécifiques pour cette session :
- [Ex: La voix se perd dans Drop 2]
- [Ex: Le sub manque de pression au club]
- [Ex: Validation Feature 1 avant déploiement à grande échelle]

Plateforme de release prévue : [SoundCloud / DistroKid / autre]

Suis le workflow du brief méthodologique section 3 :
1. Analyse profonde (charger profile genre, inventaire EQ8 par track, etc.)
2. Réponse en 5 parties (état, likes, recalibration, plan sommaire, questions de décision)
3. Attendre mes réponses aux questions de décision
4. Exécution phase par phase avec validation entre chaque

IMPORTANT :
- Format réponse : Diagnostiquer → Options → Recommandation → Étapes cliquables
- Étapes cliquables précises (chemins menus, noms boutons, valeurs)
- Liens vers documentation officielle si plugin/concept référencé
- Track-par-track recommandé, pas batch sauf demande explicite
- Honnêteté inconfortable préférée à la réassurance
```

### 3.3 Checklist pré-session (Alexandre)

Avant de coller le prompt, vérifier :

- [ ] Le `.als` est sauvegardé sous une copie (ne jamais toucher l'original)
- [ ] Le rapport Mix Analyzer Excel correspond bien au state courant du `.als`
- [ ] Le `<project>_CHANGELOG.md` est à jour avec les modifications de la session précédente
- [ ] L'écoute (moniteurs ou casque) est calibrée
- [ ] Le contexte projet (`project_<nom>_context.md`) reflète l'état courant (Mix Health, master chain, décisions validées)

### 3.4 Checklist en fin de session (Alexandre)

Avant de fermer la session :

- [ ] `<project>_CHANGELOG.md` mis à jour avec les modifications de cette session
- [ ] Nouveau `.als` sauvegardé sous nom incrémenté (ex: `Acid_Drops_PhaseN_<description>.als`)
- [ ] Re-run Mix Analyzer si bounce a été fait pour fixer les nouvelles métriques
- [ ] `project_<nom>_context.md` mis à jour si :
  - Nouveau Mix Health Score
  - Nouvelles décisions créatives validées
  - Nouvelles découvertes techniques

---

## 4 — Template : Session Développement Feature

### 4.1 Documents à charger (dans l'ordre)

**Couche méta (toujours) :**
1. `documentation_discipline.md` — notamment Section 7 (règles spécifiques Claude Code)

**Couche projet :**
2. `qrust_professional_context.md` v1.0 — pour la philosophie générale

**Roadmap et spec :**
3. `roadmap_features_1_8_v2_0.md` — pour comprendre les dépendances
4. `feature_<N>_<nom>_v<latest>.md` — la spec de la feature à développer

**Code source :**
5. Le repo Mix-Analyzer (lecture des modules existants pertinents)

**Données techniques :**
6. `genre_music_profiles.json` (si feature consomme les profils)
7. `ableton_devices_mapping_v2_2.json` (si feature manipule des devices)

### 4.2 Template de prompt à copier

```
Hello Claude Code. Démarrage du développement de la Feature [N] : [NOM_FEATURE].

Spec à implémenter : feature_[N]_[nom]_v[latest].md

Documents joints :
- documentation_discipline.md (notamment Section 7)
- qrust_professional_context.md
- roadmap_features_1_8_v2_0.md
- feature_[N]_[nom]_v[latest].md (spec à implémenter)
- genre_music_profiles.json (si applicable)
- ableton_devices_mapping_v2_2.json (si applicable)

Repo : Mix-Analyzer
Branche de travail : [feature/F[N]_[nom_court] ou main si trivial]

Validation Q1-QN du user : [oui / partiellement / non, lister les Q non résolues]

Plan de livraison à suivre : Section 7 de la spec

IMPORTANT :
- Suivre exactement le découpage en micro-commits du plan de livraison
- Séparer les commits de code et les commits de tests
- Chaque micro-commit doit avoir un message clair format `feat(F[N]): <description>` ou `test(F[N]): <description>`
- Pas de modification silencieuse de la spec — si découverte technique nécessite ajustement, signaler dans la conversation
- Coverage cible : > 85% sur les nouveaux modules
- Tests d'acceptation à valider avant de considérer la feature terminée (Section 8 ou 9 de la spec)
- Backup automatique avant toute opération destructive sur un .als
- Anti-timeout : limit chaque commit à ~30 min de travail

Procédure :
1. Lire la spec intégralement
2. Confirmer ta compréhension en résumant les points clés
3. Identifier le premier micro-commit à exécuter
4. Implémenter et committer
5. STOP entre chaque micro-commit pour validation
```

### 4.3 Checklist pré-session (Alexandre)

- [ ] Q1-QN de la spec sont validées (ou explicitement marquées comme à trancher pendant le dev)
- [ ] Branche git créée si feature majeure
- [ ] Tests existants passent en baseline (`pytest` retourne tous green)
- [ ] Spec en version v1.2+ (Q validées) ou v1.1 si dev exploratoire

### 4.4 Checklist post-commit (Claude Code)

Après chaque micro-commit :

- [ ] Tests passent (`pytest tests/test_<module>.py`)
- [ ] Coverage maintenu > 85%
- [ ] Pas de régression sur les tests existants (`pytest`)
- [ ] Message de commit conforme (`feat(F[N]): <desc>` ou `test(F[N]): <desc>`)
- [ ] Documentation interne (docstrings) à jour
- [ ] Si découverte technique pendant le dev : signalée dans la conversation, pas modifiée silencieusement dans la spec

### 4.5 Checklist fin de feature

Avant de marquer une feature comme livrée :

- [ ] Tous les micro-commits du plan sont passés
- [ ] Tous les tests d'acceptation de la spec sont validés
- [ ] Validation terrain effectuée sur Acid Drops (ou autre projet pertinent)
- [ ] `roadmap_features_1_8_v2_0.md` mis à jour (passer la feature de "Planifiée" à "Livrée")
- [ ] `CHANGELOG.md` du repo Mix-Analyzer enrichi avec entrée de la feature
- [ ] Spec passée en version v1.2 ou v1.3 si ajustements pendant le dev

---

## 5 — Template : Session Audit / Mise à jour documentaire

### 5.1 Quand cette session ?

Tu modifies, étends ou audites un document du projet (brief, contexte, spec, roadmap).

### 5.2 Documents à charger (dans l'ordre)

**Couche méta obligatoire :**
1. `documentation_discipline.md` — règles permanentes de rédaction

**Document à modifier :**
2. Le document cible dans sa version courante

**Documents parents (selon hiérarchie) :**
3. Documents dont hérite le document cible (ex: si tu modifies une spec de feature, charger aussi `qrust_professional_context.md` et `roadmap_features_1_8_v2_0.md`)

### 5.3 Template de prompt à copier

```
Hello Claude. Audit / mise à jour du document [NOM_DOCUMENT].

Document cible : [nom_document_v<version_courante>.md]
Type de modification : [enrichissement / correction / restructuration / archivage]

Documents joints :
- documentation_discipline.md
- [document_cible].md (version courante)
- [documents parents pertinents]

Raison de la modification :
- [Ex: Q1-Q5 de Feature 6 ont été validées, intégrer les décisions]
- [Ex: Découverte technique pendant le dev a invalidé l'algorithme Section 4.2]
- [Ex: Nouvelle convention décidée à intégrer]

IMPORTANT — Conformité documentation_discipline.md :
- Lire le document intégralement avant modification
- Préserver intégralement le contenu existant (pas de condensation silencieuse)
- Si suppression ou restructuration envisagée, demander confirmation explicite avant
- Modifier in-place avec annotations "(nouveau en vX.Y)" ou "(clarifié en vX.Y)"
- Incrémenter version + enrichir historique d'évolution
- Tester complétude (test du nouvel intervenant)
- Archiver l'ancienne version dans docs/archive/ après livraison

Procédure :
1. Lire le document cible intégralement
2. Identifier précisément les sections à modifier
3. Si suppression/restructuration → me demander confirmation avant
4. Produire la nouvelle version
5. Vérifier la croissance de la taille (red flag si rétrécit)
6. Signaler explicitement les changements dans la conversation
```

### 5.4 Checklist pré-session

- [ ] La raison de la modification est claire et justifiée
- [ ] Le document cible est dans sa version vraiment courante (pas un fork périmé)
- [ ] Les documents parents qui pourraient nécessiter aussi une mise à jour sont identifiés

### 5.5 Checklist post-modification

- [ ] Taille du document n'a pas rétréci (sauf si justifié et annoncé)
- [ ] Annotations "(nouveau en vX.Y)" présentes sur tous les ajouts
- [ ] Historique d'évolution mis à jour
- [ ] Ancienne version archivée dans `docs/archive/` avec header de remplacement
- [ ] Documents parents qui référencent celui-ci sont mis à jour si nécessaire

---

## 6 — Template : Session Planification / Décision architecturale

### 6.1 Quand cette session ?

Tu prends une décision structurante pour le projet (priorisation, choix d'architecture, validation Q de feature, etc.).

### 6.2 Documents à charger

**Léger :**
1. `qrust_professional_context.md` — pour les principes invariants
2. `roadmap_features_1_8_v2_0.md` — pour l'état d'avancement
3. Document(s) directement concerné(s) par la décision

### 6.3 Template de prompt à copier

```
Hello Claude. Session de planification / décision architecturale.

Sujet : [Ex: Validation Q1-Q5 de Feature 6 / Choix de séquence de livraison / Priorisation des features]

Documents joints :
- qrust_professional_context.md
- roadmap_features_1_8_v2_0.md
- [document(s) directement concerné(s)]

Contexte :
- [Décrire la situation actuelle et le besoin de décision]

Mes préférences initiales (si déjà formées) :
- [Ex: Je préfère démarrer F6 avant F7 parce que...]
- [Ex: Q1 de F6 : oui aux bandes 0/7 réservées HPF/LPF]

Format réponse attendu :
- Pour chaque question/sujet, présenter Diagnostic → Options → Recommandation → Trade-offs
- Si tu détectes que ma préférence initiale a un point faible, le signaler honnêtement
- Si une décision impacte d'autres documents, lister les documents à mettre à jour ensuite
```

### 6.4 Checklist post-décision

- [ ] La décision est tracée dans le document approprié (typiquement `roadmap_features_1_8.md` Section 4 "Décisions architecturales validées")
- [ ] Si la décision affecte une spec de feature, la spec passe en version v1.2 (Q validées)
- [ ] Les documents impactés sont identifiés et mis à jour (ou planifiés pour mise à jour)
- [ ] La décision est annoncée explicitement dans la conversation (pas implicite)

---

## 7 — Template : Reprise de session après pause

### 7.1 Quand cette session ?

Tu reprends le projet après plusieurs jours/semaines sans y toucher. Risque de désynchronisation entre ta mémoire et l'état réel des documents/code.

### 7.2 Documents à charger (dans l'ordre)

1. `roadmap_features_1_8_v2_0.md` — pour voir l'état d'avancement
2. `<project>_CHANGELOG.md` du projet courant — pour voir les modifications récentes
3. Le brief, contexte et specs concernés selon la session que tu veux faire

### 7.3 Template de prompt à copier

```
Hello Claude. Reprise du projet Mix-Analyzer / Qrust après pause.

Dernière session approximative : [date]

Documents joints :
- roadmap_features_1_8_v2_0.md
- [project_nom]_CHANGELOG.md (si projet musical)
- [autres documents selon l'objectif de cette reprise]

Objectif de cette reprise :
- [Ex: Continuer la session mastering Acid Drops à la Phase 3]
- [Ex: Démarrer le dev de Feature 6 dont les Q ont été validées dans une session antérieure]
- [Ex: Faire le point sur l'état d'avancement et planifier les prochaines semaines]

Procédure :
1. Lire la roadmap et le changelog projet (si applicable)
2. Me résumer en 5-10 lignes :
   - L'état d'avancement actuel
   - Les décisions récentes
   - Les bloqueurs ou Q en attente
   - Ce qui semble logique de faire ensuite
3. Me proposer 2-3 options pour cette session
4. Attendre que je tranche
```

### 7.4 Checklist en début de reprise

- [ ] Vérifier la version courante de chaque document principal (peut avoir changé pendant la pause)
- [ ] Lire le changelog projet pour comprendre où le projet en est
- [ ] Identifier les Q en attente sur les specs des features
- [ ] Re-vérifier que le repo Mix-Analyzer est à jour (`git pull`)

---

## 8 — Template : Quick question / Exploration

### 8.1 Quand cette session ?

Question rapide qui ne nécessite pas tout l'arsenal documentaire (ex: "Comment Pro-Q 4 gère le Dynamic EQ ?", "Quelle différence entre soothe2 et Gullfoss ?").

### 8.2 Documents à charger

Aucun document obligatoire. Charger seulement si la question le justifie clairement.

Si la question concerne le projet Mix-Analyzer ou Qrust :
- `qrust_professional_context.md` (très court à charger, donne le contexte)

### 8.3 Template de prompt minimal

```
Hello Claude. Question rapide sur [SUJET].

[Ta question directement]

Contexte minimal :
- [Si pertinent : ex "dans le contexte du projet Qrust" / "pour Acid Drops" / etc.]

Format réponse attendu :
- [Court et factuel] OU [détaillé avec options]
- Si une recommandation : Diagnostic → Options → Recommandation
- Liens vers documentation officielle si plugin/concept référencé
```

---

## 9 — Rappels critiques pour toutes les sessions

### 9.1 Pour Alexandre

**Avant de démarrer :**
- Identifier le type de session (Section 2)
- Charger les documents requis selon le template
- Être clair sur l'objectif et le format réponse attendu

**Pendant la session :**
- Push back si une recommandation ne te convient pas
- Demander clarification si une réponse est ambiguë
- Valider avant que des modifications soient faites sur le `.als` ou le code

**Après la session :**
- Mettre à jour les changelog (projet et/ou repo)
- Archiver les anciennes versions de documents si modifiés
- Décider de la prochaine étape

### 9.2 Pour l'IA conversationnelle (Claude Opus)

**Au démarrage :**
- Lire les documents fournis dans l'ordre indiqué par le template
- Confirmer ta compréhension en résumant les points clés
- Identifier le format de session attendu
- Noter les Q en attente sur les specs si pertinent

**Pendant la session :**
- Format réponse : **Diagnostic → Options → Recommandation → Étapes cliquables**
- Précision : noms exacts de menus, boutons, paramètres, valeurs
- Liens vers documentation officielle des plugins/concepts
- Honnêteté inconfortable > réassurance lisse
- Si désaccord avec Alexandre, le dire avec raisonnement complet
- Pas de modification silencieuse (ni de docs ni de fichiers)

**À la fin :**
- Proposer la mise à jour des changelog
- Identifier la prochaine étape logique
- Lister les documents qui devraient être mis à jour suite à cette session

### 9.3 Pour Claude Code

**Au démarrage :**
- Lire la spec intégralement (pas un résumé)
- Confirmer ta compréhension du plan de livraison
- Identifier le premier micro-commit
- Vérifier que les Q1-QN de la spec sont résolues (sinon demander à Alexandre)

**Pendant le dev :**
- **Suivre exactement** le découpage en micro-commits du plan
- **Séparer** commits de code et commits de tests
- **Stratégie anti-timeout** : commits courts (~30 min)
- **Backup** avant toute opération destructive
- **Pas de modification silencieuse** de la spec — signaler à Alexandre si besoin d'ajustement
- **Tests** : maintenir coverage > 85%

**À la fin de chaque commit :**
- Tests passent (`pytest`)
- Pas de régression
- Message de commit clair (`feat(F[N]): <desc>`)
- STOP entre micro-commits pour validation

**À la fin de la feature :**
- Tous les tests d'acceptation validés
- `roadmap_features_1_8_v2_0.md` mis à jour
- `CHANGELOG.md` du repo enrichi

---

## 10 — Anti-patterns à éviter

Liste des erreurs récurrentes à éviter, identifiées au cours du projet :

### 10.1 Démarrer une session sans charger les documents requis

**Symptôme :** Claude répond sans connaître le contexte invariant Qrust ou la philosophie 100% dynamique.

**Conséquence :** réponses qui contredisent les principes établis, frustration, perte de temps.

**Mitigation :** suivre rigoureusement les templates de la Section 3-8.

### 10.2 Valider une feature sans validation terrain

**Symptôme :** une feature est codée et tous les tests passent, mais elle n'a jamais été testée sur un vrai mix.

**Conséquence :** code valide techniquement mais inutile musicalement.

**Mitigation :** Section 4.5 — checklist fin de feature inclut validation terrain obligatoire.

### 10.3 Batch multi-track non validé

**Symptôme :** lancer Feature 1 (ou F6/F7) sur 5+ tracks d'un coup pour gagner du temps.

**Conséquence :** erreurs cumulées impossibles à isoler, frustration.

**Mitigation :** approche track-par-track recommandée dans tous les briefs et specs.

### 10.4 Modification silencieuse de spec ou de document

**Symptôme :** la spec est mise à jour pendant le dev sans annonce, ou un document est condensé sans annonce.

**Conséquence :** incohérence entre ce que pense Alexandre et ce qu'a fait l'IA. Perte de confiance.

**Mitigation :** `documentation_discipline.md` règle 2.1 + signalement explicite des changements.

### 10.5 Démarrer le dev avant validation des Q de la spec

**Symptôme :** Claude Code démarre F6 sans que les Q1-Q5 soient résolues.

**Conséquence :** Claude Code prend des décisions par défaut qui pourraient ne pas correspondre à la vision d'Alexandre. Refactoring nécessaire.

**Mitigation :** vérification explicite dans Section 4.3 (Checklist pré-session dev).

### 10.6 Skip du `<project>_CHANGELOG.md`

**Symptôme :** session de mix terminée sans mise à jour du changelog projet.

**Conséquence :** prochaine session démarre dans le brouillard, ne sait pas ce qui a été fait, viole la règle zero-baseline.

**Mitigation :** Section 3.4 (Checklist fin de session) liste explicitement la mise à jour du changelog.

### 10.7 Confusion entre `qrust_artistic_context.md` (ancien) et nouveaux documents

**Symptôme :** chercher l'ancien nom alors que les nouveaux documents existent.

**Conséquence :** session démarre sur des références obsolètes.

**Mitigation :** fichier de redirection `qrust_artistic_context_v1_1_DEPRECATED.md` dans `docs/archive/` qui pointe vers les nouveaux noms.

---

## 11 — Conventions de nommage et structure du repo

### 11.1 Structure dossiers attendue

```
Mix-Analyzer/  (repo)
├── docs/
│   ├── documentation_discipline.md         (méta, règles rédaction)
│   ├── roadmap_features_1_8_v2_0.md        (vue d'ensemble)
│   ├── session_bootstrap_template.md        (ce document)
│   ├── brief/
│   │   ├── qrust_professional_context.md    (invariant Qrust)
│   │   ├── mix_engineer_brief_v2_3.md       (méthodologie)
│   │   ├── genre_music_profiles.json        (calibration genre)
│   │   ├── ableton_devices_mapping_v2_2.json (mapping devices)
│   │   └── projects/
│   │       ├── project_acid_drops_context.md (Acid Drops)
│   │       └── project_<futur>_context.md    (futurs projets)
│   ├── features/
│   │   ├── feature_1_correction_conditionnelle.md  (livrée)
│   │   ├── feature_1_5_sidechain.md                (à rédiger)
│   │   ├── feature_2_q_dynamique.md                (existante)
│   │   ├── feature_3_sections_locators.md          (livrée)
│   │   ├── feature_3_5_TFP.md                      (livrée)
│   │   ├── feature_3_6_CDE.md                      (livrée)
│   │   ├── feature_4_eq8_stereo_ms.md              (existante)
│   │   ├── feature_5_autres_devices.md             (existante)
│   │   ├── feature_6_dynamic_hpf_lpf_v1_1.md       (en attente Q)
│   │   ├── feature_7_dynamic_enhancement_v1_1.md   (en attente Q)
│   │   └── feature_8_eq8_consolidation_v1_1.md     (en attente Q)
│   └── archive/
│       ├── qrust_artistic_context_v1_0.md
│       ├── qrust_artistic_context_v1_1_DEPRECATED.md (redirection)
│       ├── mix_engineer_brief_v2.md
│       ├── mix_engineer_brief_v2_1.md
│       ├── mix_engineer_brief_v2_2.md (défectueux)
│       ├── mix_engineer_brief_v2_2_complet.md
│       ├── feature_6_dynamic_hpf_lpf.md (v1.0)
│       ├── feature_7_dynamic_enhancement.md (v1.0)
│       ├── feature_8_eq8_consolidation.md (v1.0)
│       ├── roadmap_features_1_8_v1_0.md
│       └── session_bootstrap_template_v0_ARCHIVED.md
├── mix_analyzer/  (modules Python)
├── scripts/  (CLI)
├── tests/  (tests pytest)
├── CHANGELOG.md  (changelog du repo)
└── README.md
```

### 11.2 Convention de nommage des fichiers projet musicaux

Pour Acid Drops (template pour futurs projets) :
- `Acid_Drops_Sections_STD.als` — fichier source de référence
- `Acid_Drops_Sections_STD_diagnostics.json` — diagnostics CDE générés
- `Acid_Drops_MixAnalyzer_<YYYY-MM-DD_HH-MM>.xlsx` — rapports datés
- `Acid_Drops_PhaseN_<description>.als` — versions intermédiaires par phase
- `Acid_Drops_CHANGELOG.md` — changelog du projet (à la racine du projet musical)

### 11.3 Convention de nommage des branches git

- `main` — branche principale, état stable
- `feature/F[N]_<nom_court>` — développement d'une feature (ex: `feature/F6_dynamic_hpf_lpf`)
- `docs/<description>` — modifications documentaires importantes
- `fix/<description>` — corrections de bugs

### 11.4 Convention de messages git

- `feat(F[N]): <description>` — code feature
- `test(F[N]): <description>` — tests feature
- `docs(<scope>): <description>` — modification documentaire
- `fix(<scope>): <description>` — correction
- `refactor(<scope>): <description>` — refactoring sans changement comportemental
- `chore(<scope>): <description>` — maintenance, dépendances

---

## 12 — Évolution de ce document

### 12.1 Quand mettre à jour

- Identification d'un nouveau type de session non couvert par les templates actuels
- Ajout de règles ou checklists découvertes utiles
- Mise à jour des références documentaires (versions courantes)
- Découverte de nouveaux anti-patterns à documenter

### 12.2 Procédure

Suivre `documentation_discipline.md` section 4 :
1. Lire ce document intégralement
2. Identifier ce qui doit changer
3. Si suppression/restructuration → demander confirmation
4. Modifier in-place en préservant
5. Incrémenter version + enrichir historique
6. Signaler nouveautés explicitement
7. Tester complétude (test du nouvel intervenant)
8. Archiver ancienne version dans `docs/archive/`
9. Livrer avec annonce de changements

---

## 13 — Référence rapide (quick card)

**Avant de démarrer une session :**

1. Identifier le type de session (5 types : mix, dev, audit, planification, exploration)
2. Charger les documents selon le template correspondant
3. Copier-coller le template de prompt approprié
4. Personnaliser les placeholders [...]
5. Vérifier les checklists pré-session

**Pendant la session :**

- IA suit les conventions de réponse (Diagnostiquer → Options → Recommandation → Étapes cliquables)
- Honnêteté inconfortable > réassurance
- Pas de modification silencieuse
- Track-par-track pour les opérations sur multiples tracks

**Après la session :**

- Mettre à jour `<project>_CHANGELOG.md` si modification du `.als`
- Mettre à jour `roadmap_features_1_8_v2_0.md` si livraison de feature
- Archiver les versions précédentes des documents modifiés
- Décider de la prochaine étape

**Documents à charger pour TOUTES les sessions :**
- `documentation_discipline.md`
- `qrust_professional_context.md`

**Documents additionnels selon type de session :**
- Mix/Mastering : brief méthodologique + project context + données projet
- Dev feature : roadmap + spec de la feature
- Audit doc : document à modifier + documents parents
- Planification : roadmap + documents concernés par la décision
- Exploration : minimal

---

**Fin du `session_bootstrap_template.md` v1.0. Document permanent, à respecter par tous les intervenants pour démarrer une nouvelle session sur le projet Mix-Analyzer / Qrust. Mise à jour selon procédure définie en Section 12.**
