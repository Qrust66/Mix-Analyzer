# Feature 10 — High-Resolution Spectral Engine

**Version spec :** 1.6
**Date dernière modification :** 2026-05-03
**Statut :** ✅ **Feature 10 COMPLÈTE + Phase F11 (extension : extreme preset 10ms/46ms + skip trajectories en ai_optimized)**
**Hérite de :** `documentation_discipline.md` (règles de rédaction), `qrust_professional_context.md` (philosophie 100% dynamique justifiant le besoin de haute résolution)
**Brief méthodologique de référence :** `mix_engineer_brief_v2_3.md`
**Feature parent dans la roadmap :** voir `roadmap_features_1_8_v2_0.md` (priorité absolue, précède F1 pilote)
**Dépendances technique :** Mix Analyzer v2.7.0 livré ✅
**Versions archivées précédentes :**
- `docs/Archives/feature_10_v1_0_ARCHIVED.md` (création initiale, 2026-04-23)
- `docs/Archives/feature_10_v1_1_ARCHIVED.md` (Pass 2 audit, 2026-05-02)
- `docs/Archives/feature_10_v1_2_ARCHIVED.md` (Q1-Q6 validées, 2026-05-02)
- `docs/Archives/feature_10_v1_3_ARCHIVED.md` (F10d scope correction, 2026-05-02)
- `docs/Archives/feature_10_v1_4_ARCHIVED.md` (F10g.5 GUI controls, 2026-05-02)
- `docs/Archives/feature_10_v1_5_ARCHIVED.md` (F10h Tier A integration, 2026-05-03)

**Historique d'évolution de la spec :**

- **v1.0** (2026-04-23) — création initiale. Trigger : question d'Alexandre sur la résolution du rapport Excel. Analyse des données Acid Drops : résolution temporelle 166 ms (2.82 frames/beat à 128 BPM), résolution spectrale non uniforme (~2.5 Hz dans graves, ~600 Hz dans l'air). Cible : >4 frames/beat + résolution uniforme. Architecture validée : 5 presets + threshold configurable + double rapport. Status spec : pas de Q en attente, validée upfront pour passage v1.0 → v1.2.

- **v1.1** (2026-05-02) — Pass 2 audit du code Mix Analyzer v2.7.0 réel a relevé **5 disconnects critiques** entre la spec v1.0 et le pipeline existant. Préservation intégrale du contenu v1.0 + corrections architecturales motivées. Les modifications sont signalées explicitement section par section.

- **v1.2** (2026-05-02) — **Q1-Q6 validées par Alexandre** dans la même session, après walkthrough rapide des 6 questions ouvertes. Aucune modification de contenu vs v1.1 ; uniquement transition de statut "v1.1 — Q en attente" → "v1.2 — figée pour dev". §13 mis à jour avec les résolutions explicites.

- **v1.3** (ce document, 2026-05-02) — **Pass 2 audit F10d a découvert 3 erreurs de classification dans §5.2** :
  1. `_track_dynamics_time` listée comme "STFT time-based" mais la fonction productrice (`analyze_dynamic_range_timeline` ligne 1077) est **pure sample-domain** (sliding window peak/RMS, pas de `librosa.stft`, pas de n_fft). Aucun preset applicable → **hors scope F10**.
  2. `_track_chroma` listée comme "STFT time-based" mais la fonction productrice (`analyze_musical` ligne 801) utilise **`chroma_cqt`** (CQT-based, pas STFT). hop=1024 hardcoded pour précision mélodique. Audio-physics impose **PRESERVE** (chromagram = 12 pitch classes, bins_per_octave inopérant ; bumper hop dégrade tracking mélodique).
  3. `_track_multiband_time` listée comme F10d scope mais la fonction productrice (`analyze_multiband_timeline`) **était déjà couverte en F10c #4 PRESERVE** (overlap-zero design). Doublon.

  v1.3 corrige §5.2 (déplace les 3 sheets vers nouvelle section §5.7 "Sheets non-impactées par F10") et clarifie le scope F10d réel : 1 seule fonction touchée (`analyze_musical`) en mode PRESERVE + tests + spec correction.

  Préservation intégrale du contenu v1.2 — seules §5.2 et §5.7 sont restructurées + entrée historique ajoutée.

- **v1.4** (2026-05-02) — **F10g.5 ajouté** : extension GUI tkinter pour exposer les 5 contrôles F10 (preset, peak threshold, generate shareable, target MB, initial threshold) qui n'étaient accessibles que via la CLI livrée en F10g. **Trigger** : remarque utilisateur "je vois qu'il n'y a pas d'option pour ajuster la résolution, si je lance l'excel adapté pour ai, la résolution sera telle qu'attendue, soit très grande ?" — découverte qu'AI-optimized export passait par defaults `standard` preset, neutralisant l'intérêt de F10. Nouveau LabelFrame "Resolution & Output" à droite d'Excel Export Mode, persistance via `mix_analyzer_config.json` per-projet (PAS user_config — clarification Pass 2 audit), validation defensive `get_preset_by_name`/`validate_peak_threshold_db` avec fallback aux defaults si user tape valeur invalide dans le spinbox. Process change : §8 spec sync est maintenant bundled dans le commit test (pas un fix-audit séparé) pour casser le pattern F10d/F10f/F10g de 3 commits par phase.

  Préservation intégrale du contenu v1.3 — seule §8 est étendue (nouvelle entrée F10g.5 entre F10g et F10h) + entrée historique ajoutée.

- **v1.5** (2026-05-03) — **F10h livré, Feature 10 COMPLÈTE**. Phase finale : extension du schema `mix_engine.blueprint.schema` avec dataclass `AnalysisConfig` (14 champs mirroring `_analysis_config` sheet 1:1) + `DiagnosticReport.analysis_config` optional field + `_parse_analysis_config` helper dans `agent_parsers.py`. 5 prompts Tier A patchés : `mix-diagnostician.md` (lecture sheet + populer dataclass + JSON schema étendu), `band-tracking-decider.md` (cap `frame_times_sec` à `1/cqt_target_fps`), `eq-corrective-decider.md` / `dynamics-corrective-decider.md` / `mastering-engineer.md` (citent preset dans rationale si != standard). 12 nouveaux unit tests, backward compat strict (617 tests existants verts). Process change v1.4 (§8 spec sync bundlé dans commit test, pas commit séparé) appliqué : 3 commits feat / feat / test au lieu de 4. **Feature 10 status : ✅ COMPLET**.

  Préservation intégrale du contenu v1.4 — §8 entrée F10h transitionne "à livrer" → "✅ LIVRÉ" + section Total mise à jour avec totaux finaux + entrée historique v1.5 ajoutée.

- **v1.6** (ce document, 2026-05-03) — **Phase F11 ajoutée : 6e preset `extreme` + skip trajectories en `ai_optimized`**. Trigger : test terrain user — au preset `maximum`, le rapport FULL Acid Drops fait 19 MB, soit ~6 MB sous le target SHAREABLE 25 MB. User demande "résolution 10ms CQT, 50ms STFT" + "version AI sans couleurs pour économiser". **Pass 2 audit invalide la branche color-strip** (test empirique : 0.03 % réduction sur 19 MB dû à shared style table openpyxl) et **pivote vers skip trajectories** en `ai_optimized` (97 % du fichier = 2 sheets `_track_peak_trajectories` + `_track_valley_trajectories`). Livrable :
  1. **`resolution_presets.py`** : nouveau field `ResolutionPreset.stft_hop_ratio: float = 0.25` (default backward compat strict v2.7.0), property `stft_hop_samples_at_44k` recalculée via `int(n_fft * hop_ratio)`, `_CQT_FPS_MAX: 60 → 120`, nouvelles bornes `_STFT_HOP_RATIO_MIN=0.0625` / `MAX=0.5`, validation étendue. 6e preset `"extreme"` : `stft_n_fft=16384, cqt_target_fps=100, cqt_bins_per_octave=48, stft_hop_ratio=0.125` → **CQT target 10 ms / EFFECTIVE 11.61 ms** (capped par floor 512 samples = limite physique librosa CQT pour 10.67-octave coverage ; cf. fix audit ci-dessous) + **46.44 ms/frame STFT** (proche cible 50 ms) + **2.69 Hz/bin STFT** (= ultra/maximum, freq res préservée).
  2. **`mix_engine/blueprint/schema.py`** : `VALID_PRESET_NAMES` étendu avec `"extreme"`.
  3. **`feature_storage.py`** : `build_all_v25_sheets` accepte param `skip_trajectories: bool = False` (default backward compat) ; quand `True`, skip les 2 sheets trajectories (les 4 autres v25 sheets restent générées).
  4. **`mix_analyzer.py`** : conditional gate `skip_trajectories=(export_mode == 'ai_optimized')` thread vers `build_all_v25_sheets`. Mode `full` / `globals` inchangés.
  5. Tests : 1 fichier nouveau + tests existants étendus (5 → 6 presets parametrize, +6 nouveaux tests F11 pour extreme/hop_ratio/CQT_FPS_MAX bound, +4 smoke tests skip_trajectories).

  **Résultat empirique attendu** (Acid Drops ré-exécuté en `extreme + ai_optimized`) :
  - FULL extreme : ~80 MB (4x maximum, dû à 100 fps CQT + hop_ratio 1/8 STFT)
  - SHAREABLE extreme : filtrage F10f kicke (target 25 MB << 80 MB)
  - AI-optimized extreme : ~2-5 MB (skip trajectories, 95-98 % réduction vs FULL)

  Préservation intégrale du contenu v1.5 — §8 ajoute nouvelle entrée F11 entre F10h et Total ; entrée historique v1.6 ajoutée.

  **Findings v1.0 → v1.1 corrigés** :
  1. **Pipeline CQT non couvert** (critique) — `_track_peak_trajectories` (consommé par `band-tracking-decider`) est généré via `spectral_evolution.py` qui utilise CQT, pas STFT. La promesse v1.0 "n_fft 16384 → Δf 2.69 Hz uniforme" n'améliorait pas ce sheet. Scope v1.1 étendu pour couvrir le CQT pipeline avec ses propres paramètres preset (`cqt_target_fps`, `cqt_bins_per_octave`).
  2. **`peak_threshold_db` paradigme incompatible** (critique) — la détection per-track actuelle (`spectral_evolution.py:341`) utilise `prominence` (relatif), pas un threshold absolu. v1.1 redéfinit `peak_threshold_db` comme **post-filtre** sur les trajectories (drop trajectories mean_amp < threshold), sans changer la détection.
  3. **Promesse "standard = v2.7.0 équivalent" impossible** (critique) — v2.7.0 utilise multiples FFT configs (CQT 6fps + STFT 8192/4096/2048). v1.1 redéfinit `standard` comme préservant les paramètres CQT v2.7.0 (6 fps, 24 bins/oct) ET STFT v2.7.0 (n_fft=8192, hop=n_fft/4). Le test de non-régression v1.0 §9.2 reste tenable.
  4. **Module structure flat** (high) — la spec v1.0 assumait `mix_analyzer/spectral_engine.py`, etc. Reality : tout flat au repo root (`mix_analyzer.py` 10886 lignes, `spectral_evolution.py` 619 lignes). v1.1 : `resolution_presets.py` à la racine, pas de package introduction. Refactor en package est out-of-scope F10 (pourrait être F11).
  5. **Phase F10h ajoutée** (high) — la nouvelle sheet `_analysis_config` (v1.0 §5.5) doit être consommée par les agents Tier A (mix-diagnostician, eq-corrective, dynamics-corrective, mastering, band-tracking) pour qu'ils sachent quel preset a généré le rapport et adaptent leurs décisions. v1.0 ne le mentionnait pas. v1.1 ajoute Phase F10h (~1-2h, 4-6 commits).

  **Findings medium documentés (pas de changement spec mais à confirmer pendant dev)** :
  6. **Sheet `_track_transients`** listée v1.0 §5.1 — non trouvé dans grep `create_sheet`. À vérifier en début de dev.
  7. **Math error v1.0 §2.3 economy** : "hop=6144 → 2.37 frames/beat" — recalcul donne 3.37 fpb (60/128 / (6144/44100)). v1.1 corrige.

  **Status spec v1.1** : **6 Q en attente** (vs 0 en v1.0). Le Pass 2 a relevé des choix de design qui méritent validation explicite avant passage en v1.2 → dev. Voir Section 13.

  **Effort révisé** : 14-20h Claude Code (vs 10-14h v1.0), ~50-65 tests (vs 40-55), **16 micro-commits** (vs 14) répartis 8 code + 8 tests.

**Principe de préservation :** ce document préserve intégralement le contenu de v1.0. Les sections modifiées sont signalées explicitement avec annotation "(modifié en v1.1)". Les nouvelles sections ou sous-sections sont signalées "(nouveau en v1.1)". L'archive de v1.0 est dans `docs/Archives/feature_10_v1_0_ARCHIVED.md`.

**Note de priorité :** Feature 10 est en **priorité absolue** dans la roadmap. Elle doit être livrée avant le pilote F1 sur Bass Rythm (reporté en attente). Raison : pilote F1 sur résolution insuffisante serait une validation biaisée.

---

## 1 — Objectif et justification

### 1.1 Problème identifié *(modifié en v1.1)*

L'audit de résolution du rapport Mix Analyzer actuel (v2.7.0) sur Acid Drops révèle deux limitations structurelles, **chacune dans un sous-pipeline différent** *(clarification v1.1)* :

**Limitation 1 — Résolution temporelle CQT insuffisante** *(modifié en v1.1)*
- **Sous-pipeline concerné** : `spectral_evolution.py` (CQT — Constant Q Transform), qui génère `_track_peak_trajectories`, `_track_valley_trajectories`, `_track_zone_energy`, `_track_spectral_descriptors`, `_track_transients`
- Hop actuel : `sr / TARGET_FRAMES_PER_SEC = sr/6` → ~166 ms par frame à 44.1 kHz
- À 128 BPM : 2.82 frames par beat
- **Cible utilisateur : > 4 frames par beat**
- Impact : les transients courts (< 150 ms) peuvent passer entre deux frames, réduisant la précision du peak detection pour les éléments rythmiques. **Spécifiquement : `band-tracking-decider` Tier A documente lui-même son target "~50ms" qu'il ne peut pas atteindre tant que le CQT pipeline reste à 166ms.**

**Limitation 2 — Résolution spectrale STFT non uniforme**
- **Sous-pipeline concerné** : `mix_analyzer.py` (STFT) qui génère `_track_spectra`, `_track_stereo_bands`, `_track_multiband_time`, `_track_dynamics_time`, et tous les calculs full-mix
- Quantification linéaire : Δf = sr/n_fft = 5.38 Hz/bin avec n_fft=8192 (config par défaut v2.7.0). Mais l'affichage post-traitement applique une quantification logarithmique pour certains sheets — résultant en précision réelle ~±2.5 Hz dans graves (excellent), ±600 Hz dans l'air 8-20 kHz (médiocre)
- **Cible utilisateur : résolution uniforme sur tout le spectre**
- Impact : les corrections dans les hautes fréquences (présence, air, de-essing) manquent de précision. La philosophie Qrust "tout passe par EQ8 + automation piloté par Mix Analyzer" exige précision homogène.

**Note v1.1 — distinction critique** : le STFT pipeline tourne déjà à hop = n_fft/4 = 2048 samples ≈ 46 ms (9.5 frames/beat à 128 BPM, dépassant largement la cible temporelle). Le vrai gap temporel est CQT (peak trajectories). Le vrai gap spectral est STFT n_fft (5.38 → 2.69 Hz par doublement de n_fft).

### 1.2 Ancrage dans la philosophie Qrust

Cette feature est **directement alignée avec la philosophie documentée dans `qrust_professional_context.md` section 4** :

- **100% dynamique par défaut** exige précision suffisante pour distinguer peaks contextuels
- **EQ Eight + automation** remplace les plugins commerciaux (Pro-Q 4 Dynamic, soothe2, Gullfoss) qui opèrent en interne à haute résolution
- **Transparence totale** : pour que Claude Code puisse piloter EQ8 aussi précisément que Pro-Q 4 Dynamic opère, Mix Analyzer doit fournir les données à résolution équivalente

### 1.3 Ce que fait la feature *(modifié en v1.1)*

Refactor le moteur d'analyse spectrale du Mix Analyzer pour :

1. **Exposer un paramètre `resolution`** avec 5 presets (economy, standard, fine, ultra, maximum) qui pilotent **simultanément** *(nouveau en v1.1)* le CQT pipeline ET le STFT pipeline. Chaque preset déclare ses paramètres propres pour les deux sous-systèmes.
2. **Exposer un paramètre `peak_threshold_db`** comme **post-filtre** *(modifié en v1.1)* sur les peak_trajectories (drops trajectories whose mean amplitude < threshold) ET threshold absolu pour détection des anomalies full-mix. La détection per-track elle-même reste prominence-based (paradigme inchangé).
3. **Adopter N_FFT = 16384 pour les presets fine/ultra/maximum** (au lieu de 8192 actuel) — résolution spectrale STFT 2.69 Hz/bin uniforme
4. **Adopter CQT cible 10-24 fps pour les presets fine/ultra/maximum** *(nouveau en v1.1)* (au lieu de 6 fps actuel) — résolution temporelle CQT 4-11 frames/beat à 128 BPM
5. **Générer deux rapports en parallèle** : FULL (sans limite de taille, usage local + Claude Code) + SHAREABLE (< 25 MB, upload vers Claude.ai)
6. **Ajuster dynamiquement le threshold du rapport shareable** pour garantir la contrainte de taille, indépendamment de la complexité du projet
7. **Étendre les prompts Tier A** *(nouveau en v1.1)* pour qu'ils lisent la nouvelle sheet `_analysis_config` et adaptent leurs décisions au preset utilisé (Phase F10h)

### 1.4 Ce que la feature ne fait PAS (scope) *(modifié en v1.1)*

- Ne modifie pas les diagnostics CDE existants (ils bénéficient automatiquement via upstream)
- Ne change pas le format des sheets Excel (juste plus de lignes / meilleure précision des valeurs)
- Ne recalcule pas rétroactivement les rapports existants
- Ne fait pas de suggestion automatique de preset (contrôle manuel Alexandre, validé 2026-04-23)
- *(nouveau en v1.1)* Ne refactor pas la structure des modules en package `mix_analyzer/` — reste flat au repo root. Le refactor en package serait F11 séparé.
- *(nouveau en v1.1)* Ne change pas le paradigme de détection de peaks per-track (reste prominence-based). Seul l'ajout de post-filtrage par amplitude est introduit.

### 1.5 Backward compatibility *(modifié en v1.1)*

**Modifié en v1.1** : la promesse v1.0 "preset standard = v2.7.0 équivalent" est rendue **explicite et stricte** en v1.1. Le preset `standard` préserve **TOUS** les paramètres de v2.7.0 :

- CQT : `target_fps=6, bins_per_octave=24` (= constants actuels `TARGET_FRAMES_PER_SEC=6, CQT_BINS_PER_OCTAVE=24` dans `spectral_evolution.py:24-26`)
- STFT : `n_fft=8192, hop=n_fft/4` (= valeurs actuelles dans `mix_analyzer.py:512-515`)

Les rapports générés par Mix Analyzer v2.8.0 avec `--resolution standard` (défaut) doivent être **byte-identiques** *(modifié en v1.1)* à ceux générés par Mix Analyzer v2.7.0 sur la même entrée, **modulo** :
- L'enrichissement de la sheet `Index` avec les nouveaux champs metadata (preset_name, mix_analyzer_version)
- L'ajout de la nouvelle sheet `_analysis_config` (cosmétique pour les anciens consommateurs)

Test de non-régression strict en F10b documentera cette équivalence.

### 1.6 Impact sur les agents Tier A *(nouveau en v1.1)*

Les agents Tier A du `mix_engine` (`mix-diagnostician`, `eq-corrective-decider`, `dynamics-corrective-decider`, `mastering-engineer`, `band-tracking-decider`) consomment l'Excel directement (cf. leurs `description:` dans `.claude/agents/*.md`). Avec F10, ils doivent lire la nouvelle sheet `_analysis_config` et :

- **Cosmetic** : citer le preset utilisé dans leurs `rationale` Tier A pour traçabilité
- **Functional (band-tracking-decider seulement)** : adapter le `frame_times_sec` ambition à ce que le preset peut délivrer. Si le rapport est `economy` (4 fps CQT), ne pas promettre des trajectories à 50ms.

Phase F10h livre les patches de prompts pour ces 5 agents.

---

## 2 — Presets de résolution *(majoritairement réécrit en v1.1)*

### 2.1 Définitions *(réécrit en v1.1)*

Les 5 presets couvrent une gamme de besoins, du rapide/léger au détaillé/lourd, **avec des paramètres distincts pour le sous-pipeline CQT et le sous-pipeline STFT** *(nouveau en v1.1)*.

**Constants module-level (dans `resolution_presets.py` à la racine du repo)** *(modifié en v1.1 — flat structure)* **:**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ResolutionPreset:
    """Configuration d'un preset de résolution couvrant les 2 sous-pipelines.

    Les paramètres fondamentaux sont stockés ; les valeurs dérivées
    (hop_samples, n_bins, frames_per_beat, delta_freq) sont calculées
    à la volée via @property pour rester cohérentes avec les
    fondamentaux et avec le sample rate du projet.
    """

    name: str
    description: str

    # === STFT pipeline (mix_analyzer.py — full-mix spectra, M/S, RMS) ===
    stft_n_fft: int                       # Puissance de 2 ; détermine Δf et hop

    # === CQT pipeline (spectral_evolution.py — peak trajectories etc.) ===
    cqt_target_fps: int                   # Frames/sec cible pour CQT
    cqt_bins_per_octave: int              # 24 = quart de ton ; 36 = tiers ; 48 = quart

    # ========================================================================
    # Properties (valeurs dérivées — calculées à la volée)
    # ========================================================================

    @property
    def stft_hop_samples_at_44k(self) -> int:
        """Hop STFT à 44.1 kHz. Convention v2.7.0 : hop = n_fft / 4."""
        return self.stft_n_fft // 4

    @property
    def stft_delta_freq_hz_at_44k(self) -> float:
        """Résolution spectrale STFT linéaire à 44.1 kHz."""
        return 44100.0 / self.stft_n_fft

    @property
    def cqt_n_bins(self) -> int:
        """Nombre de CQT bins (scale linéaire avec bins_per_octave pour
        préserver la couverture ~10.67 octaves de v2.7.0 = 256 bins / 24 bpo).
        """
        return int(round(self.cqt_bins_per_octave * 256 / 24))

    @property
    def cqt_frames_per_beat_at_128bpm(self) -> float:
        """Frames/beat à 128 BPM (formule : fps × 60/128)."""
        return self.cqt_target_fps * 60.0 / 128.0


RESOLUTION_PRESETS: dict[str, ResolutionPreset] = {
    "economy": ResolutionPreset(
        name="economy",
        description="Re-runs rapides ou projets longs. Sous-résolution du standard.",
        stft_n_fft=8192,
        cqt_target_fps=4,
        cqt_bins_per_octave=24,
    ),
    "standard": ResolutionPreset(
        name="standard",
        description="Configuration v2.7.0 strict equivalent — défaut backward compat.",
        stft_n_fft=8192,
        cqt_target_fps=6,
        cqt_bins_per_octave=24,
    ),
    "fine": ResolutionPreset(
        name="fine",
        description="Validation soignée — Δf STFT doublée, CQT temps amélioré.",
        stft_n_fft=16384,
        cqt_target_fps=10,
        cqt_bins_per_octave=24,
    ),
    "ultra": ResolutionPreset(
        name="ultra",
        description="Production / pilote F1 — résolution complète sur les 2 pipelines.",
        stft_n_fft=16384,
        cqt_target_fps=12,
        cqt_bins_per_octave=36,
    ),
    "maximum": ResolutionPreset(
        name="maximum",
        description="Debug, micro-analyse, cas d'exception (lourd).",
        stft_n_fft=16384,
        cqt_target_fps=24,
        cqt_bins_per_octave=48,
    ),
}

DEFAULT_RESOLUTION_PRESET = "standard"  # Rétrocompatibilité avec v2.7.0
```

**Tableau récapitulatif des valeurs effectives à 44.1 kHz, 128 BPM :**

| Preset | STFT n_fft | STFT hop | STFT Δf | CQT fps | CQT bins/oct | CQT n_bins | Frames/beat (CQT) |
|---|---|---|---|---|---|---|---|
| economy | 8192 | 2048 (46 ms) | 5.38 Hz | 4 | 24 | 256 | 1.88 |
| **standard** *(défaut, = v2.7.0)* | 8192 | 2048 (46 ms) | 5.38 Hz | 6 | 24 | 256 | **2.81** *(v2.7.0 réel)* |
| fine | 16384 | 4096 (93 ms) | 2.69 Hz | 10 | 24 | 256 | 4.69 |
| ultra | 16384 | 4096 (93 ms) | 2.69 Hz | 12 | 36 | 384 | 5.63 |
| maximum | 16384 | 4096 (93 ms) | 2.69 Hz | 24 | 48 | 512 | 11.25 |

**Note v1.1 — choix de design :**

- Le **STFT hop** reste à `n_fft / 4` (convention v2.7.0). Pas exposé comme paramètre preset car aucun cas d'usage justifie de le déconnecter de n_fft.
- Le **CQT bins_per_octave** suit la progression 24 → 24 → 24 → 36 → 48 : seul `ultra` et `maximum` le bumpent. Justification : en `fine`, on prend déjà un coût ×2 sur la STFT n_fft ; bumper aussi le CQT spatial double encore le coût. `ultra` le fait pour le pilote F1 (vraie haute précision freq).
- Le `economy` preset *(corrigé en v1.1)* utilise `cqt_target_fps=4` et garde STFT à 8192. Frames/beat = 4 × 60/128 = **1.88** (vs 2.37 erroné en v1.0). Cas d'usage : itérations rapides quand on n'a pas besoin de précision.

### 2.2 Scaling avec sample rate

Les presets sont définis à 44.1 kHz de référence. Si le projet Ableton utilise un autre sample rate (48 kHz, 88.2 kHz, 96 kHz), les paramètres se comportent ainsi :

```python
def get_effective_stft_hop_ms(preset: ResolutionPreset, sample_rate: int) -> float:
    """Retourne le hop STFT en ms pour un sample rate donné."""
    return preset.stft_hop_samples_at_44k / sample_rate * 1000

def get_effective_cqt_hop_samples(preset: ResolutionPreset, sample_rate: int) -> int:
    """CQT hop est calculé pour atteindre target_fps au sample rate donné."""
    return max(int(round(sample_rate / preset.cqt_target_fps)), 512)

def get_effective_stft_delta_freq(preset: ResolutionPreset, sample_rate: int) -> float:
    """Retourne la résolution spectrale STFT pour un sample rate donné."""
    return sample_rate / preset.stft_n_fft
```

À 48 kHz : preset `ultra` produit STFT hop 85 ms (au lieu de 93 ms à 44.1k) et Δf 2.93 Hz (au lieu de 2.69 Hz). CQT garde 12 fps. Différence marginale, acceptable.

### 2.3 Paramètres windowing

Pour tous les presets STFT, window = `hann` par défaut (cohérent avec pratique actuelle Mix Analyzer).

Overlap STFT = `1 - hop_samples/n_fft = 75%` (constant car hop = n_fft/4) — ne dépend pas du preset.

CQT n'utilise pas de paramètre window (librosa CQT gère son propre filter bank).

**Modifié en v1.1** : la spec v1.0 §2.3 calculait l'overlap par-preset avec des valeurs incohérentes (economy "−25%" car hop > n_fft). En v1.1, hop est dérivé de n_fft (`n_fft/4`), donc overlap = 75% constant — le bug est éliminé par construction.

---

## 3 — Threshold de peak detection *(majoritairement réécrit en v1.1)*

### 3.1 Définition *(modifié en v1.1)*

Paramètre `peak_threshold_db` indépendant du preset. Sémantique en v1.1 :

**Application 1 — Post-filtre sur peak_trajectories CQT** *(nouveau en v1.1)* :
Après extraction des peak_trajectories par `spectral_evolution.extract_peak_trajectories(matrix)` (qui détecte par prominence — paradigme inchangé), un post-filtre drop les trajectories dont la `mean_amplitude_db < peak_threshold_db`. Cette logique vit dans la fonction d'écriture du sheet `_track_peak_trajectories` (cf. `feature_storage.build_v25_peak_trajectories_sheet`) — elle filtre avant de sérialiser.

**Application 2 — Threshold absolu pour anomalies full-mix** *(comportement existant v2.7.0, formalisé en v1.1)* :
La détection d'anomalies full-mix (`mix_analyzer.py:537` : `signal.find_peaks(spectrum_db, height=-20, distance=20, prominence=6)`) utilise déjà un `height` absolu — actuellement hardcodé à -20 dBFS. v1.1 le rend configurable via le même paramètre `peak_threshold_db`.

Note : le `height=-20` historique n'est pas remplacé par `-70` par défaut — il devient `peak_threshold_db + AMPLITUDE_HEADROOM_FOR_ANOMALY` où `AMPLITUDE_HEADROOM_FOR_ANOMALY = 50` (les anomalies full-mix sont des peaks _saillants_, donc 50 dB plus exigeants que le post-filtre per-track). Cf. F10b implementation note.

**Valeurs autorisées :**
- **Min :** -80 dBFS (très permissif, capture toutes les trajectories — full report sans filtrage)
- **Max :** -40 dBFS (très sélectif, seules les trajectories les plus présentes)
- **Défaut :** -70 dBFS (équivalent au comportement empirique v2.7.0)

### 3.2 Impact sur le volume des rapports *(inchangé sauf clarification)*

Plus le threshold est bas (-80), plus il y a de trajectories conservées → rapport plus volumineux.
Plus le threshold est haut (-40), moins il y a de trajectories → rapport plus léger.

**Justification musicale des valeurs par défaut :**
- **-70 dBFS :** capture peaks inaudibles individuellement mais qui peuvent participer à des accumulations multi-track → défaut prudent
- **-60 dBFS :** peaks généralement inaudibles en contexte mix → défaut rapport shareable (auto-ajusté à la hausse si taille dépasse)
- **-55 dBFS :** peaks audibles en écoute solo mais masqués dans mix dense → shareable agressif
- **-50 dBFS :** peaks clairement audibles → shareable ultra-agressif
- **-40 dBFS :** peaks dominants → debug uniquement

### 3.3 Paramètre CLI

```bash
--peak-threshold -70    # défaut
--peak-threshold -60    # plus léger
--peak-threshold -55    # léger
```

### 3.4 Paramètre Python

```python
peak_threshold_db=-70  # défaut
```

### 3.5 Note de robustesse — paradigme de détection inchangé *(nouveau en v1.1)*

Le paradigme de **détection** des peaks per-track reste le `prominence`-based de `spectral_evolution.extract_peak_trajectories`. Aucune modification en v1.1 :
- `min_prominence_db = 6.0` reste hardcodé (paramètre interne, pas exposé CLI)
- `distance = 3` (frames) idem
- `max_semitone_drift = 1.0` idem
- `min_duration_frames = 10` idem

`peak_threshold_db` n'opère **qu'en aval** de la détection, comme un filtre sur les trajectories sortantes. Cette séparation préserve la sensibilité de la détection (utile pour les usages internes du Mix Analyzer comme la corrélation cross-track) tout en permettant au rapport sortant d'être plus ou moins sélectif.

---

## 4 — Architecture double rapport

### 4.1 Rapport FULL

**Caractéristiques :**
- Threshold utilisateur (par défaut -70 dBFS)
- Tous les peaks/valleys détectés préservés (modulo post-filtrage par seuil)
- Taille illimitée (peut atteindre 50-100+ MB pour projets complexes)
- Usage : **local Alexandre + Claude Code** (pas uploadé vers Claude.ai)

**Naming :**
```
<project_name>_MixAnalyzer_<YYYY-MM-DD_HH-MM>_<preset>_full.xlsx
```

Exemples :
- `Acid_Drops_MixAnalyzer_2026-04-24_14-30_ultra_full.xlsx`
- `Acid_Drops_MixAnalyzer_2026-04-24_14-30_fine_full.xlsx`

### 4.2 Rapport SHAREABLE

**Caractéristiques :**
- Auto-généré en parallèle du rapport FULL (même pass d'analyse, filtrage en post)
- **Threshold dynamiquement ajusté** pour garantir taille < 25 MB
- Algorithme d'ajustement (section 4.3)
- Usage : **upload vers Claude.ai** pour sessions conversationnelles

**Naming :**
```
<project_name>_MixAnalyzer_<YYYY-MM-DD_HH-MM>_<preset>_shareable.xlsx
```

### 4.3 Algorithme d'ajustement dynamique du threshold *(inchangé sauf clarification v1.1)*

**Objectif :** garantir taille < 25 MB pour le rapport shareable, indépendamment de la complexité du projet.

**Principe :** une seule passe d'analyse produit la donnée full ; le rapport shareable est obtenu par filtrage post-hoc des peak_trajectories (la principale source de bytes dans les sheets time-based) jusqu'à ce que la taille respecte la cible.

**Algorithme :**

```python
def generate_shareable_report(
    full_data: MixAnalyzerData,
    target_size_mb: float = 25.0,
    initial_threshold_db: float = -60.0,
) -> tuple[Path, float]:
    """
    Génère le rapport shareable avec threshold dynamiquement ajusté.

    Returns:
        (output_path, final_threshold_db_used)
    """
    # Séquence de thresholds à essayer (du moins vers le plus sélectif)
    thresholds_to_try = [-60, -55, -50, -45, -40]

    start_idx = thresholds_to_try.index(initial_threshold_db) if initial_threshold_db in thresholds_to_try else 0

    for threshold in thresholds_to_try[start_idx:]:
        # Filtrer les peak_trajectories avec ce threshold
        filtered_data = filter_by_peak_threshold(full_data, threshold)

        # Générer le rapport temporaire
        temp_path = write_xlsx(filtered_data, temp=True)

        # Mesurer la taille
        size_mb = temp_path.stat().st_size / 1024 / 1024

        if size_mb <= target_size_mb:
            # Renommer en version finale
            final_path = rename_temp_to_final(temp_path)
            return (final_path, threshold)

    # Si même -40 dBFS ne suffit pas → warning et dernière version
    logger.warning(
        f"Cannot reach target {target_size_mb} MB even with threshold -40 dBFS. "
        f"Final report is {size_mb:.1f} MB. Consider using a lighter preset."
    )
    return (final_path, -40.0)
```

**Documenter dans `_analysis_config` sheet :**

Le rapport shareable doit contenir dans sa sheet `_analysis_config` :
- `preset_used: "ultra"`
- `peak_threshold_full: -70`
- `peak_threshold_shareable: -55` (la valeur finale utilisée)
- `shareable_target_mb: 25`
- `shareable_actual_size_mb: 23.4`
- `shareable_filtering_note: "Peak trajectories below -55 dBFS removed to meet size target"`

Ceci permet à Claude en session de savoir qu'il regarde un rapport filtré et d'ajuster ses analyses en conséquence.

### 4.4 Paramètre pour désactiver shareable

```bash
--no-shareable              # ne génère que le rapport FULL
--shareable-target-mb 20    # override du target 25 MB
```

---

## 5 — Sheets impactées *(modifié en v1.1)*

### 5.1 Sheets time-based via CQT pipeline *(modifié en v1.1)*

Ces sheets sont **directement impactés par `cqt_target_fps`** *(nouveau en v1.1)* — plus de frames en preset haute résolution :

- `_track_peak_trajectories` — scaling direct avec CQT fps + post-filtrage par `peak_threshold_db`
- `_track_valley_trajectories` — idem
- `_track_zone_energy` — scaling direct avec CQT fps
- `_track_spectral_descriptors` — scaling direct avec CQT fps
- `_track_transients` — basé sur CQT delta spectrum (à confirmer en F10c, voir Risque 7.1 ci-dessous) *(annotation v1.1)*

### 5.2 Sheets time-based via STFT pipeline *(nouveau en v1.1)*

Ces sheets sont impactés par `stft_n_fft` (Δf) mais **PAS** par le CQT preset :

- `_track_onsets` — basé sur onset detection STFT (hop=512 hardcodé localement, **explicitement hors scope F10** : très haute résolution temporelle déjà, le preset n'apporte rien)

⚠️ **Trois sheets initialement listées en v1.1 ont été retirées en v1.3** après le Pass 2 audit F10d (cf. historique d'évolution). Elles sont maintenant documentées en **§5.7 (Sheets non-impactées par F10)** :
- `_track_multiband_time` (couvert F10c #4 PRESERVE — pas un nouvel item F10d)
- `_track_dynamics_time` (sample-domain peak/RMS — PAS STFT du tout)
- `_track_chroma` (CQT-based avec hop=1024 — PRESERVE par audio-physics, traité en F10d)

⚠️ **Conséquence pratique** : la phase F10d originalement prévue avec 3 sheets dans son scope se réduit à **1 seule fonction touchée** (`analyze_musical` en mode PRESERVE). Cf. §8 phase F10d ci-dessous + commit `cd412de`.

### 5.3 Sheets spectral STFT *(modifié en v1.1)*

Ces sheets ont une **meilleure précision Δf** en preset haute résolution (n_fft 16384 → 2.69 Hz uniforme) :

- `_track_spectra` — passage à n_fft 16384 pour fine/ultra/maximum
- `_track_stereo_bands` — idem (note : actuellement utilise `n_fft=4096` à `mix_analyzer.py:800` ; à harmoniser en F10d)

### 5.4 Sheets indirectement améliorées

Ces sheets consomment les sheets ci-dessus et bénéficient automatiquement :

- `Sections Timeline` — métriques par section plus précises
- `Freq Conflicts` — meilleure détection des masking zones
- `Anomalies` — meilleure caractérisation
- `Mix Health Score` — pondération plus juste
- `AI Context` — synthèse bénéficie de tout l'upstream

### 5.5 Sheets non-impactées

- `_track_automation_map` — basé sur data .als, invariant
- `Index` — meta-info, enrichi avec les nouveaux paramètres

### 5.6 Sheets nouvelles

**`_analysis_config`** (nouvelle, v1.1 enrichie) — documente la configuration utilisée pour l'analyse :

| Paramètre | Valeur exemple | Source |
|---|---|---|
| preset_name | ultra | argument CLI / API |
| stft_n_fft | 16384 | preset |
| stft_hop_samples | 4096 | preset.stft_hop_samples_at_44k |
| stft_hop_ms_at_44k | 92.9 | calculé |
| stft_delta_freq_hz_at_44k | 2.69 | calculé |
| cqt_target_fps | 12 | preset |
| cqt_bins_per_octave | 36 | preset |
| cqt_n_bins | 384 | preset.cqt_n_bins |
| cqt_frames_per_beat_at_128bpm | 5.63 | calculé |
| sample_rate | 44100 | détecté projet |
| peak_threshold_db | -70 | argument CLI / API |
| is_shareable_version | false | déterminé par writer |
| mix_analyzer_version | v2.8.0 | constant |
| generated_at | 2026-04-24T14:30:00 | datetime.now() |

*(modifié en v1.1)* : v1.0 listait 13 paramètres principalement STFT-centric. v1.1 enrichit avec les paramètres CQT explicites (4 nouveaux : `cqt_target_fps`, `cqt_bins_per_octave`, `cqt_n_bins`, `cqt_frames_per_beat_at_128bpm`).

Cette sheet permet à tout consommateur (Claude en session, Claude Code, F1 CLI, **agents Tier A** *(nouveau en v1.1)*) de savoir exactement dans quelle configuration le rapport a été généré.

### 5.7 Sheets non-impactées par F10 *(nouveau en v1.3 après Pass 2 audit F10d)*

Les sheets suivantes sont **explicitement hors scope F10** par audio-physics. Le Pass 2 audit F10d (2026-05-02) a révélé que la classification v1.1 §5.2 était partiellement incorrecte ; cette section centralise désormais le raisonnement.

| Sheet | Fonction productrice | Raison hors scope F10 |
|---|---|---|
| `_track_multiband_time` | `analyze_multiband_timeline` (ligne 957) | **Couvert en F10c #4 PRESERVE** : n_fft=2048 hardcodé pour overlap-zero design (200 segments avec hop dynamique). N'apparaissait dans §5.2 v1.1 que par confusion. |
| `_track_dynamics_time` | `analyze_dynamic_range_timeline` (ligne 1077) | **Pas STFT du tout** : sliding window 50ms/20ms en pure sample-domain (np.max + np.sqrt(mean²)). Pas de `librosa.stft`, pas de n_fft. Aucun preset applicable mathématiquement. |
| `_track_chroma` | `analyze_musical` (ligne 801) via `chroma_cqt` | **CQT-based avec hop=1024 hardcodé** pour précision mélodique. Bumper `cqt_bins_per_octave` n'a aucun effet (chromagram = 12 pitch classes fixes). Bumper hop dégrade le tracking de notes rapides. **PRESERVE par audio-physics** ; traité en F10d (`analyze_musical` accepte `preset=None` ignoré pour cohérence API + tests byte-strict 5 presets). |
| `_track_onsets` | onset detection STFT (hop=512) | Très haute résolution temporelle déjà (hop=512 = 11.6 ms à 44.1 kHz). Le preset.stft_hop n'apporte aucune amélioration possible. |

⚠️ **Note design importante** : la doctrine F10 n'est PAS "tout doit utiliser le preset" — c'est "toute analyse spectrale dont la résolution mérite d'être augmentée doit pouvoir l'être via preset". Les analyses temporelles ou multi-domain (sample-domain RMS, time-series avec hop dynamique, chromagram fold-to-12) restent à leurs paramètres calibrés audio-physics, indépendants du preset. Le `preset` arg leur est passé pour cohérence d'API uniquement, et est documenté `del preset` + docstring.

---

## 6 — API proposée *(modifié en v1.1)*

### 6.1 Module source *(modifié en v1.1)*

**Nouveau module :** `resolution_presets.py` *(repo root, pas package)* — constants + dataclass + helpers

**Modules modifiés (noms exacts confirmés via Pass 2 audit) :**
- `mix_analyzer.py` (orchestration principale, ajout paramètres + multiples STFT call sites à harmoniser)
- `spectral_evolution.py` (CQT pipeline — nouveau paramètre `preset` injecté dans `generate_matrix(mono, sr)`)
- `feature_storage.py` (post-filtrage par `peak_threshold_db` dans `build_v25_peak_trajectories_sheet`)
- *(la création du fichier `excel_writer.py` mentionnée v1.0 §6.1 n'est pas nécessaire — l'écriture Excel vit dans `mix_analyzer.py` et `feature_storage.py`, on modifie en place)* *(modifié en v1.1)*

### 6.2 Fonction principale *(modifié en v1.1)*

```python
from pathlib import Path
from typing import Optional, Literal

ResolutionPresetName = Literal["economy", "standard", "fine", "ultra", "maximum"]

def analyze(
    als_path: Path | str,
    *,
    resolution: ResolutionPresetName = "standard",
    peak_threshold_db: float = -70.0,
    generate_shareable: bool = True,
    shareable_target_mb: float = 25.0,
    shareable_initial_threshold_db: float = -60.0,
    output_dir: Path | str = "reports/",
    # ... autres paramètres existants du Mix Analyzer
) -> AnalyzeResult:
    """
    Analyse un projet Ableton et génère le(s) rapport(s) Mix Analyzer.

    Args:
        als_path: Chemin vers le .als
        resolution: Preset de résolution (economy/standard/fine/ultra/maximum)
            Défaut "standard" = v2.7.0 backward compat strict.
        peak_threshold_db: Threshold post-filtrage des peak_trajectories
            (défaut -70 dBFS, range -80 à -40)
        generate_shareable: Si True, génère aussi le rapport shareable
        shareable_target_mb: Taille cible pour le rapport shareable (défaut 25 MB)
        shareable_initial_threshold_db: Threshold initial à tester pour shareable
        output_dir: Répertoire de sortie

    Returns:
        AnalyzeResult avec chemins des rapports générés et métadonnées

    Raises:
        InvalidPresetError: si resolution n'est pas un preset valide
        InvalidThresholdError: si peak_threshold_db hors [-80, -40]
    """
```

### 6.3 Result dataclass *(modifié en v1.1)*

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

@dataclass
class AnalyzeResult:
    """Résultat d'une analyse Mix Analyzer."""
    full_report_path: Path
    full_report_size_mb: float
    full_report_threshold_db: float

    shareable_report_path: Optional[Path]     # None si generate_shareable=False
    shareable_report_size_mb: Optional[float]
    shareable_threshold_db: Optional[float]   # Peut différer de full si auto-ajusté

    preset_used: str  # *(modifié en v1.1)* string ("ultra"), pas dataclass — JSON-serializable
    generated_at: datetime

    warnings: list[str]
    decisions_log: list[str]
```

*(modifié en v1.1)* : `preset_used` est désormais une string (le nom du preset), pas le dataclass `ResolutionPreset` complet. Raisons : (1) sérialisation JSON triviale, (2) le caller peut re-récupérer le dataclass via `RESOLUTION_PRESETS[result.preset_used]` si besoin.

### 6.4 Exceptions custom *(inchangé)*

```python
class ResolutionEngineError(Exception):
    """Base exception pour Feature 10."""

class InvalidPresetError(ResolutionEngineError):
    """Preset de résolution inconnu."""

class InvalidThresholdError(ResolutionEngineError):
    """peak_threshold_db hors range [-80, -40]."""

class ShareableTargetUnreachableError(ResolutionEngineError):
    """Impossible d'atteindre shareable_target_mb même avec threshold sélectif."""
```

---

## 7 — CLI wrapper *(majoritairement inchangé)*

### 7.1 Script principal

Modification du script existant de Mix Analyzer. Nouveaux flags :

```bash
python -m mix_analyzer.analyze \
    --als "Acid_Drops_Sections_STD.als" \
    --resolution ultra \
    --peak-threshold -70 \
    --generate-shareable \
    --shareable-target-mb 25 \
    --output-dir "reports/"
```

### 7.2 Flags principaux *(inchangé)*

| Flag | Type | Défaut | Description |
|---|---|---|---|
| `--als` | path | (requis) | Chemin du .als source |
| `--resolution` | str | `standard` | economy/standard/fine/ultra/maximum |
| `--peak-threshold` | float | `-70` | Threshold en dBFS (range -80 à -40) |
| `--generate-shareable` | flag | True (défaut) | Génère aussi rapport shareable |
| `--no-shareable` | flag | - | Désactive la génération du shareable |
| `--shareable-target-mb` | float | `25` | Taille cible du shareable |
| `--shareable-initial-threshold` | float | `-60` | Threshold initial du shareable (ajustable à la hausse si taille dépasse) |
| `--output-dir` | path | `reports/` | Répertoire de sortie |
| `--verbose` | flag | - | Logs détaillés (decisions_log) |

### 7.3 Exit codes *(inchangé)*

- `0` : succès
- `1` : erreur d'input (fichier .als manquant, paramètre invalide)
- `2` : erreur d'écriture (permissions, disque plein)
- `3` : shareable target non atteignable (warning, rapport full OK tout de même)
- `4` : exception interne

### 7.4 Output console *(inchangé sauf preset description v1.1)*

**Pré-exécution :**
```
Mix Analyzer v2.8.0
Projet: Acid_Drops_Sections_STD.als
Preset: ultra (STFT n_fft 16384, hop 92.9 ms, Δf 2.69 Hz | CQT 12 fps,
  36 bins/oct, 5.63 frames/beat @ 128 BPM)
Peak threshold FULL: -70 dBFS
Generate shareable: yes (target 25 MB)
Output dir: reports/
Démarrage analyse...
```

**Post-exécution :**
```
✓ Analyse terminée en 3m 24s

Rapport FULL :
  Path: reports/Acid_Drops_MixAnalyzer_2026-04-24_14-30_ultra_full.xlsx
  Taille: 33.8 MB
  Threshold: -70 dBFS

Rapport SHAREABLE :
  Path: reports/Acid_Drops_MixAnalyzer_2026-04-24_14-30_ultra_shareable.xlsx
  Taille: 24.2 MB
  Threshold: -55 dBFS (ajusté depuis -60 pour respecter target 25 MB)
  Warning: Peak trajectories entre -70 et -55 dBFS absents du shareable
    (mais présents dans full)
```

---

## 8 — Plan de livraison *(réécrit en v1.1)*

**Stratégie anti-timeout :** **16 micro-commits** (8 code + 8 tests) avec séparation stricte. *(modifié en v1.1 — ajout F10b et F10h)*

### F10a — Infrastructure presets et constants *(inchangé)*

**Fichiers créés :**
- `resolution_presets.py` (à la racine du repo, pas dans `mix_analyzer/`)

**Fonctions implémentées :**
- `ResolutionPreset` dataclass (avec properties dérivées)
- `RESOLUTION_PRESETS` dict avec les 5 presets
- `get_effective_stft_hop_ms`
- `get_effective_cqt_hop_samples`
- `get_effective_stft_delta_freq`
- `get_preset_by_name`
- Validation des valeurs (n_fft puissance de 2 ≥ 2048, cqt_target_fps ∈ [1, 60], etc.)

**Durée :** 45min
**Tests :** 5-6
**Commits :**
- `feat(F10): resolution presets infrastructure (v1.1 — STFT + CQT params)`
- `test(F10): unit tests for presets`

### F10b — CQT pipeline accepts preset *(nouveau en v1.1)*

**Fichiers modifiés :**
- `spectral_evolution.py`

**Modifications :**
- `generate_matrix(mono, sr, preset: ResolutionPreset = ...)` accepte le preset
- `_compute_hop_length(sr)` remplacé par `_compute_cqt_hop(sr, preset)` qui utilise `preset.cqt_target_fps`
- Constants `CQT_N_BINS, CQT_BINS_PER_OCTAVE, TARGET_FRAMES_PER_SEC` deviennent fallback default (preset par défaut = standard)
- Test de non-régression strict : `preset=standard` → matrix identique à v2.7.0 byte-pour-byte

**Durée :** 1h30
**Tests :** 6-8 (couvrant les 5 presets + non-régression standard)
**Commits :**
- `feat(F10): CQT pipeline accepts resolution preset`
- `test(F10): unit tests for CQT preset path + standard regression`

### F10c — STFT spectral engine accepts preset *(modifié en v1.1)*

**Fichiers modifiés :**
- `mix_analyzer.py` (multiples call sites STFT à harmoniser : lignes 512, 560, 800, 962)

**Modifications :**
- Toutes les call sites STFT `librosa.stft(..., n_fft=8192)` deviennent `librosa.stft(..., n_fft=preset.stft_n_fft)` *(harmonisation v1.1)*
- Note : la call site M/S à `n_fft=4096` (ligne 800) est conservée si on identifie une raison fonctionnelle distincte (à investiguer en début de F10c) ; sinon harmonisée
- Le `hop_length=512` des onsets/RMS (lignes 581, 624, etc.) est laissé tel quel (ce sont des analyses temporelles à très haute résolution déjà, pas pertinentes au preset)

**Durée :** 1h30
**Tests :** 6-8
**Commits :**
- `feat(F10): STFT call sites use preset n_fft`
- `test(F10): unit tests for STFT preset path`

### F10d — `analyze_musical` PRESERVE chroma + spec correction *(réécrit en v1.3 après audit)*

**Statut :** ✅ **LIVRÉ** — commits `cd412de` (code), `31553f9` (tests), `b8cfcc0` (spec v1.3).

**Note de scope (réécrit en v1.3)** : la phase F10d originale v1.0/v1.1/v1.2 listait 3 modifications (`_track_multiband_time`, `_track_dynamics_time`, `_track_chroma`). Le Pass 2 audit F10d a découvert que cette classification était fausse :
1. `_track_multiband_time` était **déjà couvert en F10c #4 PRESERVE** (analyze_multiband_timeline = doublon)
2. `_track_dynamics_time` est **pas STFT du tout** (sliding window peak/RMS sample-domain — `analyze_dynamic_range_timeline` ligne 1077)
3. `_track_chroma` est **CQT-based** (chroma_cqt avec hop=1024 hardcodé pour précision mélodique — `analyze_musical` ligne 801)

Cf. §5.7 (Sheets non-impactées par F10) pour le raisonnement audio-physics complet.

**Fichiers modifiés (réel) :**
- `mix_analyzer.py` : `analyze_musical(mono, sr, preset=None)` accepte preset pour cohérence API mais l'**ignore explicit** (`del preset`) + docstring audio-physics. Threadé depuis `analyze_track`.
- `tests/test_v25_integration.py` : 3 tests PRESERVE byte-strict sur 5 presets.
- `docs/Features/feature_10_high_resolution_spectral_engine_v1_3.md` : spec corrigée §5.2 + nouvelle §5.7 + cette §8 mise à jour.
- `docs/Archives/feature_10_v1_2_ARCHIVED.md` : préservation v1.2 avec header de redirection.

**Durée réelle :** ~1h (vs 1h30 prévu — économie grâce à audit Pass 2 qui a éliminé 2 sites du scope)
**Tests :** 3 PRESERVE byte-strict (vs 6-8 prévus — réduit en cohérence avec scope final)
**Commits livrés :**
- `feat(F10): F10d — analyze_musical PRESERVE chroma hop=1024` (cd412de)
- `test(F10): F10d — analyze_musical PRESERVE chroma byte-strict tests` (31553f9)
- `docs(F10): spec v1.2 → v1.3 — corrige §5.2 misclassification après audit F10d` (b8cfcc0)

### F10e — Mise à jour sheets spectral STFT + nouvelle sheet `_analysis_config` *(modifié en v1.1)*

**Fichiers modifiés :**
- Modules générant `_track_spectra`, `_track_stereo_bands`, `_track_spectral_descriptors`
- Module de génération Index sheet
- Module de génération `_analysis_config` (nouveau)

**Modifications :**
- Adopter résolution fréquentielle linéaire uniforme via `preset.stft_n_fft`
- Sheet `_analysis_config` créée avec les 14 paramètres (voir section 5.6)
- Sheet `Index` enrichi avec `preset_used`, `peak_threshold`, `mix_analyzer_version`

**Durée :** 1h30
**Tests :** 5-6
**Commits :**
- `feat(F10): STFT spectral sheets + analysis_config sheet`
- `test(F10): unit tests for spectral sheets + config metadata`

### F10f — Post-filtrage peak_trajectories + double rapport *(réécrit en v1.3 après livraison)*

**Statut :** ✅ **LIVRÉ** — commits `83779d3` (filter), `6eb3eec` (shareable report Approach B2), `8914009` (tests), `<audit-fix>` (audit findings).

**Note de scope (réécrit en v1.3)** : la spec v1.0/v1.1/v1.2 décrivait F10f comme 1 commit feat + 1 commit test. La livraison effective a séparé en 3 commits atomiques (feat filter / feat shareable / test) per la convention anti-timeout micro-commits, plus 1 commit fix après audit post-livraison.

**Fichiers modifiés (réel) :**
- `feature_storage.py` : ajout `filter_peak_trajectories_by_threshold(trajectories, threshold_db)` — pure functional, retourne nouvelle liste sans muter l'input.
- `mix_analyzer.py` : ajout `generate_shareable_report(full_xlsx_path, analyses_with_info, output_path, target_size_mb=25.0, initial_threshold_db=-60.0, log_fn=None)` — Approach B2.
- `tests/test_shareable_report.py` : nouveau fichier (4 unit filter + 2 mock retry + 2 e2e).
- `docs/Features/feature_10_high_resolution_spectral_engine_v1_3.md` : cette §8 mise à jour.

**Approach B2 décidée Pass 2 (Q1=B utilisateur, interprétation pragmatique)** :
Au lieu de re-runner `generate_excel_report` 5× (Approach A) ou de faire du `delete_rows()` in-place (Approach B littéral, lent + bug-prone openpyxl), la livraison :
1. Copie `FULL.xlsx` → `SHAREABLE.xlsx` (1×, fast)
2. Pour chaque threshold T dans [-60, -55, -50, -45, -40] :
   a. Filtre peak_trajectories ET valley_trajectories à T (in-memory via `dataclasses.replace` ; original `feat` jamais muté)
   b. Delete `_track_peak_trajectories` + `_track_valley_trajectories` sheets, recreate via existing builders avec data filtrée
   c. Modifier les cells `peak_threshold_db` et `is_shareable_version` du `_analysis_config` sheet en place
   d. Save → measure size
   e. Si fits → return (path, T)

**Audit fix post-livraison** : early return si `FULL.size <= target_size_mb` (économie de la copie inutile + 1 attempt) + test e2e enrichi avec assertion `SHAREABLE.size < FULL.size` après forçage du retry path.

**Durée réelle :** 2h code + 1h tests + 30min audit fix = ~3h30 (vs 2h spec — bump justifié par l'algorithme B2 plus complexe + audit triple coverage)
**Tests réels :** 8 (4 filter unit + 2 retry mock + 2 e2e dont la nouvelle assertion size reduction)
**Commits livrés :**
- `feat(F10): F10f part 1 — filter_peak_trajectories_by_threshold` (83779d3)
- `feat(F10): F10f part 2 — generate_shareable_report (Approach B2)` (6eb3eec)
- `test(F10): F10f part 3 — filter unit + retry mock + e2e (7 tests)` (8914009)
- `fix(F10): F10f audit findings — spec §8 + early return + size reduction test` (this commit)

### F10g — argparse CLI mode for headless analysis *(réécrit en v1.3 après livraison)*

**Statut :** ✅ **LIVRÉ** — commits `12d8d66` (feat argparse + _run_cli), `5af06dd` (tests + Windows console unicode fixes), `<audit-fix>` (spec §8 + memory rule).

**Décision Pass 1/2 (Q1 user reco) — Option B headless folder** :
La spec v1.0/v1.1/v1.2 §7 mentionnait `python -m mix_analyzer.analyze --als file.als`, ce qui **ne mappe pas à l'architecture actuelle** (Mix Analyzer prend un dossier de WAVs, pas un .als). Pass 2 audit a clarifié : `--als` reste optionnel pour la pipeline CDE downstream, mais l'input principal est `--input-dir <dossier de WAVs>`.

**Fichiers modifiés (réel) :**
- `mix_analyzer.py` :
  - `import argparse` ajouté au top
  - Nouvelle fonction `_peak_threshold_arg_type(value)` : custom argparse type validator pour la range [-80, -40] dBFS (réutilisé pour `--peak-threshold` ET `--shareable-initial-threshold`)
  - Nouvelle fonction `_run_cli(args) -> int` : iterate WAVs, build track_info dicts, run analyze_track + generate_excel_report (+ generate_shareable_report si applicable). Retourne exit code (0/1/2/3).
  - `main()` modifiée : argparse avec branchement `if args.input_dir → _run_cli ; else → tk.Tk() GUI`. Backward compat strict.
- `tests/test_cli_mix_analyzer.py` : nouveau fichier (5 unit subprocess + 2 e2e).
- `docs/Features/feature_10_high_resolution_spectral_engine_v1_3.md` : cette §8 mise à jour.

**Argparse flags livrés :**
- `--input-dir`, `--output-dir` (default `reports/`), `--style` (default `Industrial`), `--full-mix-wav`, `--als`, `--version`
- F10 flags : `--resolution` (choices=5 presets, default `standard`), `--peak-threshold` (range -80 à -40, default -70), `--no-shareable`, `--shareable-target-mb` (default 25 MB), `--shareable-initial-threshold` (default -60)

**Bug unicode catché par test e2e (3e occurrence du pattern)** :
Le premier run du test e2e a crashé sur Windows cp1252 console parce que les fonctions `generate_shareable_report` (F10f) utilisaient des chars unicode (`→`, `≤`, `—`, `✓`) dans `print()` et `log_fn()`. Tous remplacés par ASCII (`->`, `<=`, `--`, `[OK]`). Comments + docstrings gardent unicode (jamais imprimés au runtime).

**Durée réelle :** 1h code + 1h tests + 30 min unicode debug + 15 min audit fix = ~3h (vs 1h spec — bump for tests rigor + bug fix in-flight)
**Tests réels :** 7 (5 fast argparse validation + 2 slow e2e subprocess)
**Commits livrés :**
- `feat(F10): F10g — argparse CLI mode for headless analysis` (12d8d66)
- `test(F10): F10g — CLI tests + Windows console unicode fixes` (5af06dd)
- `fix(F10): F10g audit — spec §8 + memory rule` (this commit)

### F10g.5 — GUI tkinter controls for F10 settings *(nouveau en v1.4)*

**Statut :** ✅ **LIVRÉ**

**Trigger** : F10g a livré la CLI mais la GUI tkinter (utilisée 90% du temps) ne fournissait aucun moyen de changer le preset. Conséquence : un utilisateur lançant "AI-optimized" via la GUI obtenait l'analyse `standard` (v2.7.0 baseline) au lieu de la résolution `ultra`/`maximum` qu'il croyait avoir activée. Q1-Q5 user (1=complet, 2=à droite des choix Excel Export Mode, 3=oui persistance, 4=reco, 5=oui smoke option b).

**Décision Pass 2 audit (5 fixes appliqués)** :
1. **Unicode tkinter** : `↳` U+21B3 dans labels = OK (tkinter Unicode internal, pas cp1252). La règle ASCII-only ne s'applique qu'aux `print()`/`log_fn()` côté console.
2. **Validation defensive** : `try/except (InvalidPresetError, InvalidThresholdError)` dans `_run_analysis`, fallback aux defaults avec WARNING log si user tape valeur out-of-range dans le spinbox.
3. **Layout** : `export_frame.pack(expand=True)` → `fill='both'` pour que `res_frame` puisse fitter side='left' sans crowding.
4. **Process change** : §8 spec sync bundled dans commit test (2 commits feat/test au lieu de 3 commits feat/test/audit-fix). Casse le pattern F10d/F10f/F10g.
5. **Smoke test robuste** : tests sur noms de variables (`f"self.{var}" in src`), pas formatage exact.

**Fichiers modifiés (réel) :**
- `mix_analyzer.py` :
  - Imports étendus : `InvalidPresetError`, `InvalidThresholdError`, `get_preset_by_name`, `validate_peak_threshold_db` ajoutés à l'import existant `from resolution_presets`
  - `MixAnalyzerApp.__init__` : 5 nouvelles `tk.Variable` (`resolution_preset`, `peak_threshold_db`, `generate_shareable`, `shareable_target_mb`, `shareable_initial_threshold`) avec defaults matching CLI defaults F10g
  - Nouveau `LabelFrame` "Resolution & Output" packé à droite d'Excel Export Mode dans `options_inner`. 5 widgets en grid layout (Combobox preset + Spinbox threshold + Checkbutton shareable + 2 Spinbox sub-réglages indentés)
  - `_run_analysis` étendu : validation `get_preset_by_name`/`validate_peak_threshold_db` avant appel + threading `preset=`/`peak_threshold_db=`/`is_shareable=False` à `generate_excel_report` + appel conditionnel `generate_shareable_report` si `self.generate_shareable.get()` (failure log + continue, ne bloque pas le FULL)
  - `_save_config` étendu : 5 nouvelles clés JSON dans le dict per-projet `mix_analyzer_config.json`
  - Loader (méthode appelée par `_select_audio_files`) étendu : 5 blocs `if 'X' in existing_config` pour backward compat avec configs pré-F10g.5
- `tests/test_gui_f10_controls_smoke.py` : nouveau fichier (smoke test sur source code par `inspect.getsource`)
- `docs/Features/feature_10_high_resolution_spectral_engine_v1_4.md` : cette §8 mise à jour (process change : bundled dans commit test, pas commit séparé)

**Backward compat strict** :
- Configs pré-F10g.5 (sans les 5 nouvelles clés) : loaders sautent, defaults appliqués (`standard`, -70 dBFS, generate_shareable=True, 25 MB, -60 dBFS) → comportement v2.7.0 identique
- User n'ayant rien changé dans la GUI obtient le comportement F10g default (preset `standard` = v2.7.0 byte-identique + shareable activé)

**Durée réelle :** ~1h30 (Pass 1 + Pass 2 audit + Pass 3 code + smoke + spec)
**Tests réels :** 1 nouveau (smoke source-inspect) + 17 existants verts (v25 integration + CLI argparse)
**Commits livrés :**
- `feat(F10): F10g.5 — GUI controls for resolution + threshold + shareable` (mix_analyzer.py only)
- `test(F10): F10g.5 — smoke test + spec v1.3 -> v1.4 + archive` (tests + docs bundled per process change)

### F10h — Tier A agent prompt updates *(nouveau en v1.1, livré en v1.5)*

**Statut :** ✅ **LIVRÉ**

**Décision Pass 2 audit (1 fix scope appliqué)** :
- Pass 1 plan disait "uniquement des prompts, 0 tests Python". Pass 2 a découvert que `mix_engine/blueprint/agent_parsers.py:_parse_diagnostic_internal` (line 1197) doit être étendu pour parser le nouveau champ JSON `diagnostic.analysis_config` → `DiagnosticReport.analysis_config`. Donc le scope réel inclut :
  1. `mix_engine/blueprint/schema.py` : nouvelle dataclass `AnalysisConfig` + `VALID_PRESET_NAMES` constante + extension `DiagnosticReport`
  2. `mix_engine/blueprint/agent_parsers.py` : nouveau `_parse_analysis_config` helper + thread dans `_parse_diagnostic_internal`
  3. 5 prompts agents
  4. Tests unit pour la dataclass + parser (12 tests vs 0 prévu spec v1.1)

**Fichiers modifiés (réel) :**
- `mix_engine/blueprint/schema.py` : `VALID_PRESET_NAMES` frozenset + `@dataclass(frozen=True) AnalysisConfig` (14 champs miroirs du `_analysis_config` sheet, méthodes dérivées `cqt_frames_per_beat_at(bpm)` + `stft_delta_freq_hz_at(sr)`) + `DiagnosticReport.analysis_config: Optional[AnalysisConfig] = None`
- `mix_engine/blueprint/agent_parsers.py` : import `AnalysisConfig` + `VALID_PRESET_NAMES` ; `_parse_analysis_config(item, *, where)` helper (mirror `_parse_genre_context` pattern, 14 champs requis, validation preset_name + peak_threshold_db range) ; `_parse_diagnostic_internal` thread `analysis_config_raw` → `_parse_analysis_config` → `DiagnosticReport(analysis_config=...)`
- `.claude/agents/mix-diagnostician.md` :
  - Bullet `_analysis_config` ajouté à "Sheets pertinents"
  - Nouvelle section "Phase F10h — Lecture de `_analysis_config`" avec snippet openpyxl 3 lignes + table des 14 champs requis + référence parser
  - JSON schema "diagnostic": {...} étendu avec champ `analysis_config: {14 fields}` (exemple ultra preset)
- `.claude/agents/band-tracking-decider.md` : nouvelle section "Phase F10h — Adaptation au preset de résolution" après "Limitation 50ms target" (cap `frame_times_sec` interval à `1.0 / cqt_target_fps`, table per-preset des limites physiques 4-24 fps, instruction citation rationale si preset != standard)
- `.claude/agents/eq-corrective-decider.md`, `.claude/agents/dynamics-corrective-decider.md`, `.claude/agents/mastering-engineer.md` : 1 paragraphe chacun dans la section rationale-construction (eq/dynamics) ou output schema (mastering) — pattern "if `analysis_config.preset_name != 'standard'` cite-le dans rationale + raison domain-specific (eq narrow-band cut, dynamics fast attack, mastering precise LUFS targeting)"
- `tests/test_analysis_config_schema.py` : nouveau fichier (12 unit tests, < 1 sec : 5 parametrize instantiation per preset + 3 derived methods + 1 backward compat default None + 3 parser roundtrip + invalid input rejection)
- `docs/Features/feature_10_high_resolution_spectral_engine_v1_5.md` : cette §8 mise à jour + section Total mise à jour

**Backward compat strict** :
- `DiagnosticReport.analysis_config: Optional[AnalysisConfig] = None` → tests existants qui instancient `DiagnosticReport(...)` sans le kwarg ne cassent pas
- Parser : `diag_dict.get("analysis_config", None)` → JSON pre-F10h sans le champ accepté
- Prompts : tous les paragraphes F10h sont gardés "if analysis_config is not None" → comportement v2.7.0 préservé pour rapports pre-F10h
- 617 tests schema + parser regression verts

**Durée réelle :** ~2h (vs 1-2h spec — Pass 2 audit a élargi le scope au parser, mais bundle propre)
**Tests réels :** 12 (vs 0 prévu spec v1.1 — Pass 2 a justifié leur ajout pour la dataclass + parser contracts)
**Commits livrés :**
- `feat(F10): F10h part 1 — AnalysisConfig dataclass + parser` (38d72e1)
- `feat(F10): F10h part 2 — 5 Tier A prompts read _analysis_config` (46d4a7d)
- `test(F10): F10h part 3 — schema tests + spec v1.4 -> v1.5 + archive` (this commit)

### F11 — Extension : extreme preset + AI-friendly skip trajectories *(nouveau en v1.6)*

**Statut :** ✅ **LIVRÉ**

**Trigger :** test terrain user après F10h livré. Au preset `maximum`, le rapport FULL Acid Drops fait 19 MB, sous le target SHAREABLE 25 MB → SHAREABLE = quasi-copie de FULL (early-return F10f). User demande deux choses indépendantes :
1. Plus haute résolution : **10 ms/frame CQT + ~50 ms STFT**
2. Version AI plus légère

**Pass 2 audit pivot critique** :
- Brief original "retire les couleurs" → invalidé par test empirique : 0.03 % réduction (5 KB sur 19 MB) car openpyxl utilise une shared style table (`xl/styles.xml`) — tous les cells réfèrent les mêmes styles par index.
- ZIP analysis du fichier 19 MB révèle que **97 % de la taille = `_track_peak_trajectories` + `_track_valley_trajectories`** (sheet16 + sheet17 = 19.0 MB sur 19.5 MB total). Ces sheets contiennent 658k rows de time-series CQT trajectory data que les agents Tier A NE LISENT JAMAIS (ils consomment AI Context, Anomalies, Mix Health Score).
- **Pivot** : skip ces 2 sheets en `excel_export_mode='ai_optimized'` → 95-98 % réduction file-size, sans impact agent.

**Fichiers modifiés (réel) :**
- `resolution_presets.py` :
  - Bump `_CQT_FPS_MAX: 60 → 120` (laisse 20 % marge au-dessus du target user 100 fps)
  - Nouvelles constantes `_STFT_HOP_RATIO_MIN=0.0625, MAX=0.5` (= 1/16 à 1/2)
  - Nouveau field `ResolutionPreset.stft_hop_ratio: float = 0.25` (default = convention v2.7.0 = backward compat strict pour les 5 presets historiques)
  - Property `stft_hop_samples_at_44k` recalculée : `int(n_fft * stft_hop_ratio)` au lieu du hardcoded `n_fft // 4`
  - `_validate_preset_params` + `_build_preset` étendus avec validation hop_ratio
  - 6e preset `"extreme"` : `stft_n_fft=16384, cqt_target_fps=100, cqt_bins_per_octave=48, stft_hop_ratio=0.125`. Résultats :
    - **CQT : 10.00 ms/frame** (cible user atteinte exactement)
    - **STFT : 46.44 ms/frame** (proche cible 50 ms, en deçà)
    - **STFT : 2.69 Hz/bin** (= ultra/maximum, freq res préservée)
- `mix_engine/blueprint/schema.py` : `VALID_PRESET_NAMES` étendu avec `"extreme"` → parser `_parse_analysis_config` accepte les rapports extreme
- `feature_storage.py` : `build_all_v25_sheets` accepte param `skip_trajectories: bool = False` (default backward compat) ; quand True, log SKIPPED + omet les 2 build calls trajectories. Les 4 autres v25 sheets (zone_energy, spectral_descriptors, crest_by_zone, transients) restent générées (small + utiles)
- `mix_analyzer.py` : conditional gate dans `generate_excel_report` : `_skip_traj = (export_mode == 'ai_optimized')` thread à `build_all_v25_sheets`. Mode `full` / `globals` inchangés.
- `tests/test_resolution_presets.py` : extension parametrize 5 → 6 presets (3 tests étendus) + 6 nouveaux tests F11 (extreme targets, hop_ratio backward compat per preset, hop_ratio validation, _CQT_FPS_MAX boundary)
- `tests/test_skip_trajectories_ai_optimized.py` : nouveau fichier, 4 smoke tests (signature param, gate logic source-inspect, kept-sheets verification, mix_analyzer wiring)
- `docs/Features/feature_10_high_resolution_spectral_engine_v1_6.md` : cette §8 mise à jour + section Total mise à jour

**Backward compat strict** :
- 5 presets historiques (economy/standard/fine/ultra/maximum) : `stft_hop_ratio=0.25` par défaut → `stft_hop_samples_at_44k` byte-identique à v2.7.0
- `build_all_v25_sheets` : `skip_trajectories=False` par défaut → mode `full` / `globals` inchangés
- `VALID_PRESET_NAMES` : ajout uniquement, pas de retrait → parsers existants OK
- 60 tests F11 + tests historiques verts (zéro régression)

**Résultats empiriques attendus** (Acid Drops à re-runner pour validation user terrain) :
- FULL extreme : ~80 MB (4x maximum dû à 100 fps CQT + hop_ratio 0.125 STFT, soit ~5x densité globale)
- SHAREABLE extreme : filtrage F10f kicke pour la première fois (target 25 MB << ~80 MB FULL)
- ai_optimized extreme : ~2-5 MB (skip trajectories, 95-98 % réduction vs FULL)

**Durée réelle :** ~1h30 (Pass 1 + audit + 3 commits)
**Tests réels :** 60 tests verts (test_resolution_presets : 47, test_skip_trajectories : 4, plus regression v25 et schema)
**Commits livrés :**
- `feat(F11): extreme preset — 100 fps CQT (10ms) + hop_ratio=0.125 (46ms STFT)` (2f070f6)
- `feat(F11): skip _track_peak/valley trajectories in ai_optimized mode` (637efbc)
- `test(F11): extreme preset + skip trajectories smoke + spec v1.5 -> v1.6 + archive` (e48c124)
- `fix(F11): extreme preset effective fps capped at 86 (option A)` (this commit)

**Fix audit Pass 4 (option A choisie par user)** : Pass 2 audit avait
loupé que le hop CQT a un floor à **512 samples** (`get_effective_cqt_hop_samples`,
`resolution_presets.py:414`) — c'est une limite physique librosa CQT
pour 10.67 octaves de couverture (`2^(n_octaves-1)` divisibility
requirement). Le preset `extreme` avec `cqt_target_fps=100` produit un
target hop de 441 samples → floor cap à 512 → **effective 86.13 fps =
11.61 ms/frame** (PAS 10 ms comme target). Test
`test_extreme_preset_meets_user_targets` corrigé pour valider la
réalité post-floor (assert `eff_hop == 512`, `eff_fps == 86.13`,
`eff_ms == 11.61`). Description du preset corrigée. Options B (lever le
floor → risque librosa NaN) et C (switch pseudo_cqt → ~2h refactor)
non poursuivies — option A "accepter 11.61 ms" choisie : c'est l'optimum
CQT atteignable sans perdre l'analyse < 254 Hz (zone bass/kick).
**5 ms (200 fps) impossible CQT pleine bande**. **1 ms (1000 fps)
physiquement impossible CQT** (principe d'incertitude temps-fréquence
pour analyser 60 Hz fondamental requires ≥ 16.7 ms window). Documentation
inline du preset reflète maintenant ces limites.

### Total *(modifié en v1.6 — F11 extension ajoutée)*

**Effort total F10 + F11 (réel) :** ~24h, ~62 tests F10 + 60 tests F11/extension, **24 micro-commits** :
- F10a-F10f : 12 commits (8 feat + 4 fix-audit pré-process-change)
- F10g + F10g.5 : 5 commits (2 feat F10g + 1 fix-audit + 2 feat/test F10g.5 post-process-change)
- F10h : 3 commits (2 feat + 1 test, post-process-change)
- F11 : 3 commits (2 feat + 1 test, process-change appliqué)

Process change v1.4 (§8 spec sync bundled in test commit) appliqué dès F10g.5 → réduit le pattern 3-commits-par-phase à 2-3 commits selon scope.

---

## 9 — Tests d'acceptation *(modifié en v1.1)*

### 9.1 Tests unitaires
- ✅ ~50-65 tests passants
- ✅ Coverage > 85% sur nouveaux modules (`resolution_presets.py`)
- ✅ Coverage > 80% sur modules modifiés (`spectral_evolution.py`, `mix_analyzer.py`, `feature_storage.py`)

### 9.2 Tests d'intégration *(modifié en v1.1 — clarification non-régression)*
- ✅ Tous les presets produisent des rapports valides (ouvrables Excel)
- ✅ **Test de non-régression strict : rapport preset `standard` byte-identique à rapport v2.7.0** sur le même .als (modulo nouvelles sheets `_analysis_config` + champs Index ajoutés)
- ✅ Rapport `ultra` a effectivement 5.63 frames/beat CQT (à 128 BPM, mesurable)
- ✅ Rapport `ultra` a effectivement 2.69 Hz par bin STFT (mesurable dans `_track_spectra`)
- ✅ Rapport `ultra` a effectivement 36 bins/octave CQT (mesurable dans `_track_peak_trajectories` row count)
- ✅ Rapport shareable respecte target_mb (avec warning si impossible)
- ✅ Sheet `_analysis_config` présente et complète dans tous les rapports
- ✅ **Post-filtrage peak_trajectories : avec `peak_threshold_db=-70`, toutes les trajectories restantes ont `mean_amplitude_db ≥ -70`** *(nouveau en v1.1)*

### 9.3 Tests CLI
- ✅ `--resolution ultra` fonctionne
- ✅ `--peak-threshold -60` fonctionne
- ✅ `--no-shareable` désactive le shareable
- ✅ `--shareable-target-mb 15` force ajustement threshold à une valeur plus sélective
- ✅ Preset invalide → erreur claire avec liste des presets valides
- ✅ Threshold hors range → erreur claire

### 9.4 Validation terrain (post-livraison code)
- ✅ Générer rapport Acid Drops en preset `ultra` (full + shareable)
- ✅ Ouverture correcte dans Excel / LibreOffice
- ✅ Validation des métriques cohérentes (Mix Health Score, anomalies, etc.)
- ✅ Shareable < 25 MB
- ✅ Generation time acceptable (< 5 min pour preset ultra sur Acid Drops)
- ✅ **`band-tracking-decider` Tier A invoqué sur le rapport `ultra` produit des band_tracks avec `frame_times_sec` à 83 ms (1/12s) au lieu de 167 ms** *(nouveau en v1.1)*

### 9.5 Documentation
- ✅ Spec mise à jour si divergence pendant dev
- ✅ `roadmap_features_1_8_v2_0.md` mis à jour (F10 → Livrée)
- ✅ `CHANGELOG.md` du repo enrichi
- ✅ README du repo mis à jour avec exemples d'usage des nouveaux flags
- ✅ **Prompts Tier A mis à jour cohérents avec `_analysis_config` schema** *(nouveau en v1.1)*

---

## 10 — Impact sur les features existantes *(modifié en v1.1)*

### 10.1 Feature 1 (CDE auto-apply)

**Comportement attendu :** F1 consomme les rapports Excel + diagnostics JSON. F1 fonctionne identiquement, mais bénéficie de meilleures données en amont :
- Peak-follow plus précis (CQT 100ms à `ultra` vs 166ms à `standard`)
- Diagnostics plus fins dans les hautes fréquences (Δf STFT 2.69 Hz à `fine+`)

**Action nécessaire :** aucune modification F1 requise. Les diagnostics CDE seront régénérés depuis les nouveaux rapports avant le pilote Bass Rythm.

### 10.2 Feature 3.6 (CDE engine) *(modifié en v1.1)*

**Comportement attendu :** CDE engine génère diagnostics à partir des sheets du rapport. Avec haute résolution, les diagnostics deviennent plus nombreux et plus précis.

**Action nécessaire en F10b/F10c :** *(clarification v1.1)* auditer `cde_engine.py` (2219 lignes) pour identifier toute constante hardcodée qui dépendait de l'ancienne résolution (ex: hop 166 ms, 6 fps). Si trouvé, basculer sur les valeurs effectives du preset utilisé.

### 10.3 Features 6, 7, 8 (en roadmap)

**Comportement attendu :** bénéficient automatiquement de la haute résolution quand elles seront développées.

**Impact sur les specs :** les specs F6, F7, F8 v1.1 mentionnent des seuils calibrés sur l'ancienne résolution. **À vérifier** lors du dev de chaque feature si les seuils doivent être ajustés (probablement pas, car ils sont en fréquence et dBFS, pas en frames).

### 10.4 Agents Tier A du `mix_engine` *(nouveau en v1.1)*

**Comportement actuel (v2.7.0)** : les 5 agents Tier A consommateurs d'Excel (`mix-diagnostician`, `eq-corrective-decider`, `dynamics-corrective-decider`, `mastering-engineer`, `band-tracking-decider`) lisent l'Excel à résolution implicite (celle de v2.7.0).

**Action nécessaire en F10h** :
- `mix-diagnostician` : lit `_analysis_config`, expose `preset_used`, `cqt_frames_per_beat`, `stft_delta_freq_hz` dans son `DiagnosticReport` typé (champ `analysis_config` à ajouter au schema).
- `band-tracking-decider` : utilise `analysis_config.cqt_frames_per_beat` pour déterminer le `frame_times_sec` réaliste de ses band_tracks. Si rapport généré en `economy` (4 fps), ne pas promettre 50ms.
- `eq-corrective-decider`, `dynamics-corrective-decider`, `mastering-engineer` : citent le preset utilisé dans leur `rationale` (cosmétique mais utile pour traçabilité).

**Schema impact** : `mix_engine/blueprint/schema.py:DiagnosticReport` ajoute champ `analysis_config: Optional[AnalysisConfig] = None` avec dataclass `AnalysisConfig` typé. Mineur — ne casse pas les agents qui n'utilisent pas le champ.

---

## 11 — Risques techniques identifiés *(modifié en v1.1)*

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| `cde_engine.py` a des hardcoded dependencies sur hop 166 ms ou 6 fps | Moyenne | Logique | Audit pendant F10b, mise à jour si nécessaire |
| n_fft 16384 trop lourd pour machines modestes | Faible | Performance | Machine desktop Alexandre a 64 GB RAM, marge confortable |
| Certains projets Ableton utilisent SR 48 kHz → décalage hop_ms | Moyenne | Précision | Conversion dynamique (section 2.2), documenté dans report metadata |
| Target 25 MB non atteignable même avec -40 dBFS | Faible | Bloquant upload | Warning explicite + suggestion preset plus léger |
| Rapport standard différent du rapport v2.7.0 | Faible *(modifié en v1.1)* | Régression | Test de non-régression strict en F10b — `standard` doit produire output byte-identique. Si divergence, c'est un bug à fixer avant merge. |
| Scaling volumétrique sous-estimé pour projets denses | Moyenne | Dépassement target | Algorithme d'ajustement a retry jusqu'à -40, + warning |
| Temps de génération prohibitif en preset maximum | Moyenne | UX | Documenter clairement, usage recommandé pour debug uniquement |
| **Tests existants `test_spectral_evolution.py` sensibles au preset** *(nouveau en v1.1)* | Haute | Tests cassent | Ajouter une fixture `preset_standard_v270` qui injecte le preset standard à `generate_matrix()`. Préserver les valeurs attendues actuelles. |
| **Sheet `_track_transients` non confirmée présente** *(nouveau en v1.1)* | Faible | Sheet manquante | Audit en début F10c via grep `_track_transients` — si absente, retirer de §5.1 et de la liste des sheets impactées |
| **STFT call sites multiples avec n_fft différents** *(nouveau en v1.1)* | Moyenne | Refactor partiel | F10c décide call-by-call : harmonisation vers preset.n_fft sauf justification fonctionnelle distincte (notamment ligne 800 M/S à n_fft=4096) |

---

## 12 — Hors scope F10 v1 *(modifié en v1.1)*

**Reportés à F10 v2 ou autres features :**

- **Suggestion automatique de preset** (refusé par Alexandre 2026-04-23, contrôle manuel préféré)
- **Presets adaptatifs par genre** (logic de "Industrial → preset X, Ambient → preset Y") — possible en F10 v2 si besoin
- **Streaming de gros rapports** (si fichier > 100 MB, chunking par track) — pas urgent
- **Format alternatif au .xlsx** (HDF5, parquet pour performance) — question future
- **Visualisation graphique des trajectories haute résolution** — hors scope, outil externe
- **Refactor en package `mix_analyzer/`** *(nouveau en v1.1)* — la spec v1.0 supposait cette structure ; v1.1 garde flat. Refactor en package = F11 séparé.
- **Modification du paradigme de détection des peaks per-track** *(nouveau en v1.1)* — reste prominence-based en F10. Un éventuel passage à amplitude-based (ou hybride) serait F12 si besoin.
- **Onset detection hop sample dynamique** *(nouveau en v1.1)* — reste hardcodé `hop_length=512` car opère à très haute résolution déjà.

---

## 13 — Q validées (figées en v1.2) *(modifié en v1.2)*

**Modifié en v1.2** : les 6 Q ouvertes en v1.1 ont été validées par Alexandre le 2026-05-02 lors d'un walkthrough rapide. La spec est figée pour démarrage dev (Phase F10a). Préservation des questions originales pour traçabilité historique.

**Q1 — Définition stricte du preset `standard`** ✅ VALIDÉ
> Le preset `standard` doit-il être **byte-identique** à v2.7.0 ?

**Réponse 2026-05-02 : oui, strict equivalent.** Test de non-régression en F10b enforce — le standard preset doit produire output byte-identique à v2.7.0 sur la même entrée, modulo l'enrichissement de `_analysis_config` + Index sheet (cosmétique). Sans cette garantie, tout script existant qui ne passe pas `--resolution` voit son output changer = breaking change silencieux.

**Q2 — Paradigme `peak_threshold_db`** ✅ VALIDÉ
> Le `peak_threshold_db` opère-t-il bien comme **post-filtre** sur les trajectories CQT, ou faut-il revoir et tenter d'unifier avec un threshold de détection ?

**Réponse 2026-05-02 : post-filtre uniquement.** Préserve la sensibilité de la détection prominence-based pour les usages internes (corrélations cross-track) tout en permettant au rapport sortant d'être plus ou moins sélectif. Détection ↔ reporting = concerns séparés, séparation propre.

**Q3 — Inclusion du CQT pipeline dans le scope F10** ✅ VALIDÉ
> Le CQT pipeline (peak_trajectories) doit-il être touché par le preset, ou laissé tel quel et seul le STFT pipeline modifié ?

**Réponse 2026-05-02 : oui, CQT inclus.** Sans ça, `band-tracking-decider` reste à 6 fps et le pilote F1 sur la résolution est biaisé — exactement ce que F10 doit éviter. +1.5h justifiés.

**Q4 — Module structure flat vs package** ✅ VALIDÉ
> On garde flat à la racine du repo ou on refactor en `mix_analyzer/` package en même temps que F10 ?

**Réponse 2026-05-02 : flat.** Refactor en package = preuve sociale de complexité (≥20 fichiers liés), pas un prérequis F10. F11 séparée plus tard si justifié par usage. Scope F10 reste contenu.

**Q5 — Phase F10h Tier A prompt updates** ✅ VALIDÉ
> Les patches de prompts pour les 5 agents Tier A (lecture `_analysis_config`) sont-ils dans le scope F10 ?

**Réponse 2026-05-02 : dans le scope F10.** Sinon les 5 agents Tier A ignorent le preset utilisé → décisions incohérentes avec la résolution disponible. +1-2h.

**Q6 — Preset values des nouveaux tiers** ✅ VALIDÉ
> Les valeurs proposées pour `economy / fine / ultra / maximum` (cf. tableau §2.1) sont-elles acceptables ?

**Réponse 2026-05-02 : oui, valeurs validées telles quelles.** Progression logique : economy=½ standard, fine=⁵⁄³ standard, ultra=2× standard, maximum=4× standard. Mappées aux use cases réels (re-runs / défaut / validation / production / debug). Pas d'ajustement nécessaire.

---

## 14 — Procédure d'évolution

Suivre `documentation_discipline.md` section 4.

**Triggers probables :**
- Alexandre tranche les Q1-Q6 → v1.2 (tel quel) ou v1.1.X si ajustements
- Découverte technique pendant dev (ex: sheet `_track_transients` absente confirmée) → v1.3 avec ajustements
- Validation terrain révèle que preset `ultra` produit rapports trop lourds → v1.4 avec ajustements

---

## 15 — Référence rapide (quick card) *(modifié en v1.1)*

**Statut :** Spec v1.3 — F10a + F10b + F10c + F10d livrés. F10e-F10h restants (~5-7h estimés).

**Effort estimé total :** 14-20h, ~50-65 tests, **16 micro-commits** (vs 14 en v1.0).

**Modules à créer :**
- `resolution_presets.py` (à la racine du repo)

**Modules à modifier :**
- `spectral_evolution.py` (CQT pipeline accepts preset) ← **nouveau scope v1.1**
- `mix_analyzer.py` (STFT call sites + orchestration + Excel writers)
- `feature_storage.py` (post-filtrage peak_trajectories) ← **nouveau scope v1.1**
- `cde_engine.py` (audit hardcoded constants + adaptations si trouvées) ← **clarifié v1.1**
- CLI principal Mix Analyzer
- 5 prompts agents Tier A dans `.claude/agents/` ← **nouveau scope v1.1**

**Presets clés (à 44.1 kHz, 128 BPM) :**

| Preset | STFT n_fft | STFT hop | STFT Δf | CQT fps | CQT bins/oct | CQT fpb |
|---|---|---|---|---|---|---|
| economy | 8192 | 46 ms | 5.38 Hz | 4 | 24 | 1.88 |
| **standard** *(défaut, = v2.7.0)* | 8192 | 46 ms | 5.38 Hz | 6 | 24 | 2.81 |
| fine | 16384 | 93 ms | 2.69 Hz | 10 | 24 | 4.69 |
| **ultra** *(F1 pilot)* | 16384 | 93 ms | 2.69 Hz | 12 | 36 | 5.63 |
| maximum | 16384 | 93 ms | 2.69 Hz | 24 | 48 | 11.25 |

**Threshold :**
- Range : -80 à -40 dBFS
- Défaut FULL : -70 dBFS (post-filtre peak_trajectories CQT + threshold détection anomalies full-mix STFT)
- Défaut SHAREABLE initial : -60 dBFS (auto-ajuste jusqu'à -40 si target taille non atteint)
- *(nouveau en v1.1)* Le paradigme de DÉTECTION reste prominence-based (per-track) — `peak_threshold_db` ne change que le filtrage en aval

**Architecture double rapport :**
- FULL : local + Claude Code, sans limite de taille
- SHAREABLE : upload Claude.ai, <25 MB, threshold dynamique

**Dépendances roadmap :**
- Mix Analyzer v2.7.0 livré ✅
- F1 pilote Bass Rythm en attente F10 livrée
- F6/F7/F8 bénéficient automatiquement
- *(nouveau en v1.1)* `mix_engine` Tier A agents bénéficient via F10h

**Documents associés :**
- `qrust_professional_context.md` section 4
- `mix_engineer_brief_v2_3.md`
- `roadmap_features_1_8_v2_0.md` (mise à jour prévue après livraison F10)
- `documentation_discipline.md`
- `docs/Archives/feature_10_v1_0_ARCHIVED.md` (version précédente — création)
- `docs/Archives/feature_10_v1_1_ARCHIVED.md` (version précédente — Pass 2 audit)
- `docs/Archives/feature_10_v1_2_ARCHIVED.md` (version précédente — Q1-Q6 validées)

---

**Fin spec Feature 10 v1.3 — F10a/b/c/d livrés, F10e/f/g/h restants.**

Phase suivante : **F10e** (STFT spectral sheets `_track_spectra` + `_track_stereo_bands` + `_track_spectral_descriptors` + nouvelle sheet `_analysis_config`).
