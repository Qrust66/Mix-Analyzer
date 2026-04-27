# CLAUDE.md — Instructions récurrentes pour Claude Code

## Projet

Mix Analyzer v2.7.0 — Outil d'analyse audio qui génère des rapports Excel
et des automations EQ8 dynamiques pour Ableton Live. Depuis v2.7.0, produit
également un fichier `<projet>_diagnostics.json` à côté du `.als` via le
Correction Diagnostic Engine (Feature 3.6 B1, cf. `cde_engine.py`).

## Versioning

La version canonique est la constante `VERSION` dans `mix_analyzer.py`.
Tous les fichiers .py de production doivent afficher la même version.
Endroits à maintenir synchronisés si la version change :

- `mix_analyzer.py` `VERSION = 'X.Y.Z'` (constante canonique)
- `mix_analyzer.py` ligne 4 (docstring)
- `mix_analyzer.py` titre fenêtre, Help, logo subtitle (utilisent `VERSION`)
- `als_utils.py` docstring ligne 4
- `spectral_evolution.py` docstring ligne 4
- `feature_storage.py` docstring ligne 4
- `eq8_automation.py` docstring ligne 4
- `automation_map.py` docstring ligne 4
- `section_detector.py` docstring ligne 4
- `cde_engine.py` docstring ligne 4 (depuis v2.7.0)

La version est estampillée dans chaque rapport Excel (Index + AI Context).
Ne jamais laisser des versions désynchronisées entre fichiers.

## Communication avec l'utilisateur

- **Toujours indiquer si les changements sont disponibles sur `main`** après un commit/push.
  L'utilisateur utilise **GitHub Desktop** pour synchroniser. Dire explicitement :
  "C'est pushé sur main, tu peux faire **Pull** dans GitHub Desktop."
- Si le travail est sur une branche feature, le préciser : "C'est sur la branche X,
  pas encore sur main. Je te dirai quand merger."
- L'utilisateur n'est pas familier avec git/GitHub — toujours guider simplement,
  pas de jargon inutile. Le workflow est :
  1. On travaille ici dans Claude Code
  2. Je push sur GitHub quand c'est prêt
  3. L'utilisateur fait **Pull** dans GitHub Desktop → fichiers locaux à jour

## Knowledge Graph (graphify)

Le projet a un knowledge graph persistant à `graphify-out/graph.json` (4334 nœuds,
10757 arêtes, 96 communautés). Couvre code Python + docs + briefs + composition_engine.

### Quand consulter le graph (réflexe à adopter)

- **Avant d'explorer le code par grep/Glob/Read** pour répondre à une question
  d'architecture ou trouver "qui appelle quoi" — `13×` moins de tokens en moyenne,
  jusqu'à `100×+` pour les questions cross-module.
- **Avant de modifier un fichier de production** : vérifier ses connexions sortantes
  (qui en dépend) pour estimer le rayon de blast.
- **Quand l'utilisateur référence un concept abstrait** (ex. "le moteur CDE",
  "les sections", "TFP") plutôt qu'un fichier précis — le graph trouve le bon
  point d'entrée.

### Commandes

- `/graphify query "<question>"` — réponse cross-fichiers via traversée BFS
- `/graphify query "<question>" --dfs` — trace une chaîne de dépendances précise
- `/graphify path "X" "Y"` — chemin le plus court entre deux concepts
- `/graphify explain "X"` — tout ce qui se connecte au nœud X

### God nodes (abstractions centrales — toucher avec précaution)

`Section`, `CorrectionDiagnostic`, `CorrectionRecipe`, `ProblemMeasurement`,
`PeakTrajectory`, `TFPContext`, `SectionContext`. Modifier l'un de ces types
propage à >130 voisins — toujours vérifier via `/graphify explain` avant.

### Maintenance du graph

- **Code modifié** : si un commit a été fait, le post-commit hook (s'il est
  installé via `graphify hook install`) recalcule l'AST automatiquement —
  rien à faire. Sinon, `/graphify . --update` après une session de modifs.
- **Docs / briefs / features modifiés ou ajoutés** : nécessite re-extraction
  sémantique (LLM). Lancer `/graphify . --update` manuellement.
- **Ne jamais commit `graphify-out/`** : c'est un artefact local, déjà
  ignoré dans `.gitignore`.

## Hooks git automatiques (filet de sécurité)

Le projet versionne ses hooks git dans `.githooks/`. Configurer une fois
par clone :

```bash
git config core.hooksPath .githooks
```

Sans cette commande, **les hooks ne s'exécutent pas**. Le `git status`
n'avertit pas — penser à le refaire après un fresh clone.

### Hooks installés

| Hook | Rôle |
|------|------|
| `pre-commit` | Lance `check_version_sync.py` si un fichier de prod est staged. Bloque le commit en cas de drift de version. Bypass avec `--no-verify` (déconseillé). |
| `pre-push` | Lance `check_regression.py` qui choisit entre la **suite rapide** (3 fichiers test : `test_spectral_evolution`, `test_eq8_automation`, `test_v25_integration`, ~10-15s) et la **suite complète** (`pytest tests/`, ~2 min). Critère : si un des 8 fichiers de prod ou un fichier `tests/*.py` est dans le push → suite complète, sinon suite rapide. Bloque le push en cas d'échec. Bypass avec `--no-verify` (déconseillé). |
| `post-commit` | Hook graphify : rebuild AST-only de `graphify-out/graph.json` après chaque commit. Sans LLM, gratuit. |
| `post-checkout` | Idem au changement de branche. |

### Hook Claude Code (`.claude/hooks/`)

`UserPromptSubmit` (configuré dans `.claude/settings.json`) lance
`.claude/hooks/graphify_reminder.py` à chaque prompt. Si le prompt matche
des patterns d'architecture / dépendance / cross-module (regex sur
`how does X work`, `qui utilise`, `pipeline`, `relation entre`, etc.),
le hook **injecte un rappel** dans le contexte de Claude pour qu'il
consulte `graphify-out/graph.json` avant tout grep/Read. Coût : ~50
tokens par prompt qui matche, 0 sinon.

Les hooks sont des **filets de sécurité déterministes** (pas de LLM, pas
de magie) qui complètent les agents Claude Code. Si un check est purement
mécanique (grep + comparaison), il vaut mieux l'avoir comme hook que comme
agent — l'agent peut être oublié, le hook ne peut pas.

## Agents automatiques

Le projet déclare des subagents Claude Code dans `.claude/agents/`. Certains
doivent être invoqués proactivement aux moments listés ci-dessous, sans
attendre que l'utilisateur les demande.

### als-safety-guardian (`.claude/agents/als-safety-guardian.md`)

**Invoquer automatiquement** dans ces cas :

1. **Après l'exécution d'un script qui produit un `.als`** : tout script de
   `composition_engine/`, `scripts/build_*`, `ableton/build_*`, ou tout
   appel à `als_utils.compress_to_als()` qui écrit un nouveau fichier.
2. **Avant un commit qui modifie ou ajoute un `.als`** (`git status`
   montre un `.als` staged ou modified).
3. **Avant de livrer un `.als` à l'utilisateur** (par exemple : "voilà ton
   Banger_v3.als") — passer la checklist en silence avant la livraison.

L'agent est read-only (tools restreints à `Read, Bash, Grep, Glob`) — aucun
risque qu'il modifie le fichier. Il reporte PASS / FAIL / WARN par règle
puis un verdict global. Si verdict = FAIL, **ne pas livrer le `.als`** sans
fix manuel.

L'agent est défini en français et référence `ableton/ALS_MANIPULATION_GUIDE.md`
+ la section "Pièges critiques" du présent CLAUDE.md comme source de vérité.
Mettre à jour ces deux documents propage automatiquement aux validations.

### version-sync-checker (`.claude/agents/version-sync-checker.md`)

**Invoquer automatiquement** dans ces cas :

1. **Avant tout commit qui touche `mix_analyzer.py`** — la constante canonique
   `VERSION` peut avoir bougé sans que les 7 autres docstrings suivent.
2. **Avant tout commit dont le message contient `bump`, `version` ou `release`**
   — il s'agit explicitement d'un bump de version, validation obligatoire.
3. **Avant un push sur `main`** — dernière vérif avant publication.

L'agent compare la constante `VERSION` dans `mix_analyzer.py` aux docstrings
des 7 autres fichiers listés en section "Versioning" plus haut. Reporte un
tableau PASS/FAIL et refuse de patcher (read-only).

Si verdict = OUT-OF-SYNC, **ne pas push** sans aligner manuellement les
fichiers en drift. La règle projet est explicite : *"Ne jamais laisser des
versions désynchronisées entre fichiers."*

### graph-first-explorer (`.claude/agents/graph-first-explorer.md`)

**Invoquer automatiquement** quand l'utilisateur pose une question :

1. **D'architecture / cross-module** : "comment fonctionne la pipeline X",
   "qui dépend de Y", "lien entre A et B", "trace le flux de … à …".
2. **Multi-query** : la réponse nécessite de croiser plusieurs concepts ou
   modules (>2 fichiers à explorer).
3. **De premier contact avec un module inconnu** : avant de plonger dans
   un dossier que je n'ai pas encore visité dans la session.

L'agent consulte `graphify-out/graph.json` **avant** tout grep/Read et
revient avec une synthèse citée. Ne pas l'invoquer pour les questions
triviales (1 Read suffit) ou pour les détails algorithmiques d'une
fonction (graph donne la structure, pas le détail).

Le hook `UserPromptSubmit` (cf. section Hooks plus haut) injecte
automatiquement un rappel dans mon contexte quand le prompt matche les
patterns d'architecture — filet de sécurité pour ne pas oublier l'agent.

### regression-detector (`.claude/agents/regression-detector.md`)

**Invoquer automatiquement** dans ces cas :

1. **Avant tout commit qui touche un des 8 fichiers de prod** ou un
   `tests/*.py` — analyser le diff, calculer le blast radius via le
   graph, recommander les tests à lancer.
2. **Avant un push** qui contient des modifs de prod — recommander si
   la suite rapide suffit ou si la suite complète est nécessaire.
3. **À la demande explicite** : "audit régression sur ce changement".

L'agent fait l'**audit intelligent** (lit le diff, croise avec
`graphify-out/graph.json` pour identifier qui dépend des fonctions
modifiées, flagge HIGH RISK si un god node est touché). Il **ne lance
pas les tests** — c'est le rôle du hook `pre-push` (cf. section Hooks).

L'agent et le hook sont complémentaires :
- Hook = filet de sécurité automatique au moment du push
- Agent = audit raisonné, peut être invoqué avant le commit pour
  anticiper et choisir le scope de tests à lancer manuellement

## Fichiers de production (8 fichiers, même dossier)

| Fichier | Rôle |
|---------|------|
| `mix_analyzer.py` | App principale (UI tkinter + analyse + rapport Excel + orchestration CDE depuis v2.7.0) |
| `spectral_evolution.py` | Moteur CQT + extraction features v2.5 |
| `feature_storage.py` | Écriture des sheets cachés Excel v2.5 |
| `als_utils.py` | Manipulation des fichiers .als (lecture/écriture EQ8) |
| `eq8_automation.py` | 15 fonctions d'automation EQ8 dynamique |
| `section_detector.py` | Détection / lecture des sections Ableton + sheet Sections Timeline (Feature 3/3.5/3.6 hooks) |
| `tfp_parser.py` + `tfp_coherence.py` | TFP roles (Feature 3.5) — parsing + score de cohérence par section |
| `cde_engine.py` | Correction Diagnostic Engine (Feature 3.6 B1) — diagnostics masking + JSON dump |

## Tests

- `tests/test_spectral_evolution.py` — 22 tests (phases 1-2)
- `tests/test_eq8_automation.py` — 45 tests (phases 3-8)
- `tests/test_v25_integration.py` — 4 tests d'intégration pipeline
- Lancer : `python -m pytest tests/ -v`
- Toujours lancer les tests avant de push.

## Conventions

- Style : black, type hints, docstrings sur chaque fonction publique.
- Zéro régression v2.4 : les sheets et analyses existants ne doivent pas changer.
- Pas de nouvelle dépendance sans justification (stack : numpy, scipy, librosa,
  openpyxl, soundfile, pyloudnorm).
- Commits format conventionnel : `feat(scope):`, `fix(scope):`, `chore:`, `test:`.
- Anti-timeout : max 3 fichiers modifiés par réponse, checkpoint commits fréquents.

## Observations techniques ALS (référence)

- EQ8 bands : `Bands.0` à `Bands.7`, chaque band a `ParameterA` avec
  `IsOn`, `Mode`, `Freq`, `Gain`, `Q`
- Modes EQ8 : 0=LowCut48, 1=LowCut12, 2=LowShelf, 3=Bell, 4=Notch,
  5=HighShelf, 6=HighCut12, 7=HighCut48
- Automation : `AutomationEnvelopes/Envelopes/AutomationEnvelope` au niveau track
- FloatEvent : `Id` (unique), `Time` (en beats), `Value`
- Time=-63072000 = event pré-song (état initial)
- DeviceChain path = `DeviceChain/DeviceChain/Devices` (doublé)

## Guide technique manipulation .als

Voir **`ableton/ALS_MANIPULATION_GUIDE.md`** pour les APIs Python génériques
(applicable à tout projet Ableton, pas seulement Acid Drops) : lecture/écriture
gzip, bornage de track, injection de device avec `<Devices />` self-closing,
calcul de `safe_id`, règle des grands IDs, tempo map, automations.

**Pièges critiques déjà rencontrés** :

1. **Double gzip** : `gzip.open('wb').write(gzip.compress(...))` → Ableton
   refuse d'ouvrir. Utiliser soit `gzip.open('wb').write(xml.encode())` soit
   `open('wb').write(gzip.compress(...))`, pas les deux.

2. **`<Devices />` self-closing** : les tracks sans device ont `<Devices />`
   auto-fermant. `xml.find('<Devices>', ...)` ne matche pas cette forme et
   saute sur la track suivante → device injecté sur la mauvaise track.
   Toujours borner la recherche aux limites de la track et détecter les
   deux formes (`<Devices />` et `<Devices>`).

3. **`<Envelopes />` self-closing** : même piège côté AutomationEnvelopes
   pour une track sans automation existante.

4. **Vérification post-écriture obligatoire** : relire le fichier produit,
   premiers octets doivent être `<?xml` (sinon double-gzip), et vérifier
   que le nouveau device Id se trouve bien dans les bornes de la track cible.

5. **Nommer tout device injecté** : chaque device créé par Claude doit
   avoir un `<UserName Value="..." />` explicite révélant sa fonction
   (ex. `"Peak Resonance"`). Ne jamais laisser vide — l'utilisateur doit
   voir d'un coup d'œil à quoi sert chaque device dans sa chain. Voir
   `ableton/ALS_MANIPULATION_GUIDE.md` section "Nommer un device injecté".
