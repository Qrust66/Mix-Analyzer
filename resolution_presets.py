#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""resolution_presets.py — Mix Analyzer Phase F10 (v2.8.0).

5 presets de résolution pilotant SIMULTANÉMENT le sous-pipeline STFT
(``mix_analyzer.py``) et le sous-pipeline CQT (``spectral_evolution.py``).

Architecture :

- ``ResolutionPreset`` : dataclass figé portant 3 paramètres fondamentaux
  (``stft_n_fft``, ``cqt_target_fps``, ``cqt_bins_per_octave``) + 4
  ``@property`` dérivées (hop, Δf, n_bins, frames/beat).

- ``RESOLUTION_PRESETS`` : dict des 5 presets nommés
  (``economy / standard / fine / ultra / maximum``).

- ``DEFAULT_RESOLUTION_PRESET == "standard"`` : préserve les
  paramètres v2.7.0 strict (CQT 6 fps + 24 bins/oct + STFT 8192) pour
  backward compatibility byte-identique.

- Helpers ``get_*`` : valeurs effectives pour un sample rate arbitraire
  (presets définis à 44.1 kHz de référence — reset de hop_ms à 48k OK).

Documentation complète :
    docs/Features/feature_10_high_resolution_spectral_engine_v1_2.md
"""
from __future__ import annotations

from dataclasses import dataclass


# ============================================================================
# Typed exceptions (Phase F10 §6.4)
# ============================================================================


class ResolutionEngineError(Exception):
    """Base exception pour Feature 10."""


class InvalidPresetError(ResolutionEngineError):
    """Preset de résolution inconnu — name pas dans RESOLUTION_PRESETS."""


class InvalidThresholdError(ResolutionEngineError):
    """peak_threshold_db hors range [-80, -40]."""


# ============================================================================
# Validation bounds
# ============================================================================

# Range valide pour ``peak_threshold_db`` (cf. spec §3.1).
PEAK_THRESHOLD_MIN_DB: float = -80.0
PEAK_THRESHOLD_MAX_DB: float = -40.0

# STFT n_fft doit être une puissance de 2 ≥ 2048 (limite raisonnable
# pour analyse audio à sr=44.1kHz : 2048 = ~21 Hz/bin, 32768 = ~1.3 Hz/bin).
_STFT_N_FFT_MIN: int = 2048
_STFT_N_FFT_MAX: int = 32768

# CQT fps doit rester réaliste (1 fps = 1 frame/sec très lent ; 100 fps
# = 10 ms/frame, target user pour band-tracking ultra-fin ; 120 fps cap
# laisse 20 % de marge sans inviter des configs aberrantes).
_CQT_FPS_MIN: int = 1
_CQT_FPS_MAX: int = 120

# STFT hop_ratio : fraction du n_fft utilisée comme hop. Convention
# v2.7.0 = 0.25 (overlap 75 %, presets economy/standard/fine/ultra/maximum).
# Phase F11 : preset extreme override à 0.125 (overlap 87.5 %) pour
# gagner ~2x en résolution temporelle STFT sans toucher n_fft (= garde
# la même résolution fréquentielle).
_STFT_HOP_RATIO_MIN: float = 0.0625  # = 1/16, raisonnable upper bound CPU
_STFT_HOP_RATIO_MAX: float = 0.5     # = 1/2, lower bound utile (overlap 50 %)

# CQT bins_per_octave : 12 = semitone, 24 = quart de ton (v2.7.0),
# 36 = 1/3 ton, 48 = 1/4 ton. Au-delà, coût FFT prohibitif sans bénéfice.
_CQT_BINS_PER_OCTAVE_MIN: int = 12
_CQT_BINS_PER_OCTAVE_MAX: int = 96

# Référence : v2.7.0 utilise 256 bins à 24 bins/octave = 10.67 octaves
# de couverture. On scale n_bins linéairement avec bins_per_octave pour
# préserver cette couverture (cf. ResolutionPreset.cqt_n_bins).
_CQT_REFERENCE_N_BINS_AT_24_BPO: int = 256
_CQT_REFERENCE_BINS_PER_OCTAVE: int = 24

# Référence sample rate pour les valeurs de presets.
# Les presets sont définis avec ces valeurs ; les helpers ``get_effective_*``
# scale au sample rate du projet réel.
REFERENCE_SAMPLE_RATE: int = 44100


# ============================================================================
# ResolutionPreset dataclass
# ============================================================================


@dataclass(frozen=True)
class ResolutionPreset:
    """Configuration d'un preset de résolution (STFT + CQT).

    Seuls les paramètres fondamentaux sont stockés ; les valeurs dérivées
    sont calculées à la volée via ``@property`` pour rester cohérentes
    avec les fondamentaux (pas de drift entre champs).

    Attributes:
        name: identifiant du preset (clé dans :data:`RESOLUTION_PRESETS`).
        description: phrase courte décrivant le use case.
        stft_n_fft: taille de la fenêtre STFT (puissance de 2).
            Détermine ``stft_hop_samples_at_44k`` (= n_fft / 4) et
            ``stft_delta_freq_hz_at_44k`` (= sr / n_fft).
        cqt_target_fps: frames/sec cible pour le pipeline CQT
            (``spectral_evolution.py``). À sr=44.1 kHz, hop = sr / fps.
        cqt_bins_per_octave: résolution spectrale CQT
            (24 = quart de ton ; 36 = 1/3 ton ; 48 = 1/4 ton).

    Raises:
        ValueError: si les paramètres sont hors bornes raisonnables
            (cf. ``_validate_preset_params`` au build-time du dict).
    """

    name: str
    description: str
    stft_n_fft: int
    cqt_target_fps: int
    cqt_bins_per_octave: int
    # Phase F11 (v2.8.x) : stft_hop_ratio paramétrable per-preset.
    # Default 0.25 préserve la convention v2.7.0 (overlap 75%) pour les
    # 5 presets historiques. Preset ``extreme`` override à 0.125 (overlap
    # 87.5%) pour atteindre ~46 ms/frame STFT à n_fft=16384, sans
    # sacrifier la résolution fréquentielle.
    stft_hop_ratio: float = 0.25

    # ========================================================================
    # Properties (valeurs dérivées — calculées à la volée)
    # ========================================================================

    @property
    def stft_hop_samples_at_44k(self) -> int:
        """Hop STFT en samples à 44.1 kHz.

        Convention v2.7.0 = 0.25 (= ``n_fft / 4``, overlap 75 %). Phase
        F11 expose ``stft_hop_ratio`` per-preset pour permettre des
        ratios plus serrés (0.125 = overlap 87.5 % pour preset extreme)
        sans toucher n_fft (= garde la même résolution fréquentielle).
        """
        return int(self.stft_n_fft * self.stft_hop_ratio)

    @property
    def stft_hop_ms_at_44k(self) -> float:
        """Hop STFT en millisecondes à 44.1 kHz (utile pour logs)."""
        return self.stft_hop_samples_at_44k / REFERENCE_SAMPLE_RATE * 1000.0

    @property
    def stft_delta_freq_hz_at_44k(self) -> float:
        """Résolution spectrale STFT linéaire à 44.1 kHz (Hz/bin)."""
        return REFERENCE_SAMPLE_RATE / self.stft_n_fft

    @property
    def cqt_n_bins(self) -> int:
        """Nombre de bins CQT.

        Scale linéairement avec ``cqt_bins_per_octave`` pour préserver la
        couverture ~10.67 octaves de v2.7.0 (256 bins / 24 bpo).
        Couverture freq = ``FMIN`` × 2 ^ (n_bins / bins_per_octave) avec
        ``FMIN = 20 Hz`` → couvre toute la plage humaine.
        """
        ratio = self.cqt_bins_per_octave / _CQT_REFERENCE_BINS_PER_OCTAVE
        return int(round(_CQT_REFERENCE_N_BINS_AT_24_BPO * ratio))

    @property
    def cqt_frames_per_beat_at_128bpm(self) -> float:
        """Frames/beat CQT à 128 BPM (formule : fps × 60/128).

        Métrique principale d'amélioration temporelle pour
        ``band-tracking-decider`` Tier A. v2.7.0 = 2.81 fpb (preset
        standard). Cible utilisateur > 4 fpb → preset fine ou supérieur.
        """
        return self.cqt_target_fps * 60.0 / 128.0


# ============================================================================
# Validation au build-time du dict RESOLUTION_PRESETS
# ============================================================================


def _validate_preset_params(
    name: str,
    stft_n_fft: int,
    cqt_target_fps: int,
    cqt_bins_per_octave: int,
    stft_hop_ratio: float = 0.25,
) -> None:
    """Valide les paramètres d'un preset au build-time.

    Raises:
        ValueError: avec un message clair si un paramètre est hors bornes.
    """
    if not (_STFT_N_FFT_MIN <= stft_n_fft <= _STFT_N_FFT_MAX):
        raise ValueError(
            f"Preset {name!r}: stft_n_fft={stft_n_fft} hors range "
            f"[{_STFT_N_FFT_MIN}, {_STFT_N_FFT_MAX}]."
        )
    # n_fft doit être puissance de 2 (FFT efficace).
    if stft_n_fft & (stft_n_fft - 1) != 0:
        raise ValueError(
            f"Preset {name!r}: stft_n_fft={stft_n_fft} doit être une "
            f"puissance de 2."
        )
    if not (_CQT_FPS_MIN <= cqt_target_fps <= _CQT_FPS_MAX):
        raise ValueError(
            f"Preset {name!r}: cqt_target_fps={cqt_target_fps} hors "
            f"range [{_CQT_FPS_MIN}, {_CQT_FPS_MAX}]."
        )
    if not (_CQT_BINS_PER_OCTAVE_MIN <= cqt_bins_per_octave <= _CQT_BINS_PER_OCTAVE_MAX):
        raise ValueError(
            f"Preset {name!r}: cqt_bins_per_octave={cqt_bins_per_octave} "
            f"hors range [{_CQT_BINS_PER_OCTAVE_MIN}, "
            f"{_CQT_BINS_PER_OCTAVE_MAX}]."
        )
    if not (_STFT_HOP_RATIO_MIN <= stft_hop_ratio <= _STFT_HOP_RATIO_MAX):
        raise ValueError(
            f"Preset {name!r}: stft_hop_ratio={stft_hop_ratio} hors "
            f"range [{_STFT_HOP_RATIO_MIN}, {_STFT_HOP_RATIO_MAX}]."
        )


def _build_preset(
    name: str,
    description: str,
    stft_n_fft: int,
    cqt_target_fps: int,
    cqt_bins_per_octave: int,
    stft_hop_ratio: float = 0.25,
) -> ResolutionPreset:
    """Helper de construction qui valide AVANT instanciation."""
    _validate_preset_params(
        name=name,
        stft_n_fft=stft_n_fft,
        cqt_target_fps=cqt_target_fps,
        cqt_bins_per_octave=cqt_bins_per_octave,
        stft_hop_ratio=stft_hop_ratio,
    )
    return ResolutionPreset(
        name=name,
        description=description,
        stft_n_fft=stft_n_fft,
        cqt_target_fps=cqt_target_fps,
        cqt_bins_per_octave=cqt_bins_per_octave,
        stft_hop_ratio=stft_hop_ratio,
    )


# ============================================================================
# Les 5 presets — valeurs validées Q1-Q6 par Alexandre (2026-05-02)
# ============================================================================


RESOLUTION_PRESETS: dict[str, ResolutionPreset] = {
    "economy": _build_preset(
        name="economy",
        description="Re-runs rapides ou projets longs. Sous-résolution "
                    "du standard sur le pipeline CQT (4 fps vs 6).",
        stft_n_fft=8192,
        cqt_target_fps=4,
        cqt_bins_per_octave=24,
    ),
    "standard": _build_preset(
        name="standard",
        description="Configuration v2.7.0 strict equivalent — défaut "
                    "backward compat (CQT 6 fps + 24 bins/oct + STFT 8192).",
        stft_n_fft=8192,
        cqt_target_fps=6,
        cqt_bins_per_octave=24,
    ),
    "fine": _build_preset(
        name="fine",
        description="Validation soignée — Δf STFT doublée (16384), CQT "
                    "temps amélioré (10 fps).",
        stft_n_fft=16384,
        cqt_target_fps=10,
        cqt_bins_per_octave=24,
    ),
    "ultra": _build_preset(
        name="ultra",
        description="Production / pilote F1 — résolution complète sur "
                    "les 2 pipelines (STFT 16384, CQT 12 fps + 36 bins/oct).",
        stft_n_fft=16384,
        cqt_target_fps=12,
        cqt_bins_per_octave=36,
    ),
    "maximum": _build_preset(
        name="maximum",
        description="Debug, micro-analyse, cas d'exception — coût "
                    "élevé, usage ponctuel uniquement.",
        stft_n_fft=16384,
        cqt_target_fps=24,
        cqt_bins_per_octave=48,
    ),
    "extreme": _build_preset(
        name="extreme",
        description="Phase F11 — target_fps=100 demandé mais cap par "
                    "le floor CQT 512 samples (limite physique librosa "
                    "CQT pour 10.67 octaves de couverture). Effective "
                    "fps réel à sr=44.1k = 86.13 fps = 11.61 ms/frame "
                    "CQT. STFT : hop_ratio=0.125 sur n_fft=16384 = "
                    "46.44 ms/frame. Best CQT temporal resolution "
                    "atteignable sans perdre l'analyse < 254 Hz "
                    "(bass/kick zone). Coût compute ~4x maximum ; "
                    "fichier FULL ~5x ; SHAREABLE filtering kick in "
                    "systématique. Réservé band-tracking ultra-fin "
                    "terrain.",
        stft_n_fft=16384,
        cqt_target_fps=100,
        cqt_bins_per_octave=48,
        stft_hop_ratio=0.125,
    ),
}


DEFAULT_RESOLUTION_PRESET: str = "standard"
"""Preset par défaut. Préserve les paramètres v2.7.0 strict pour
backward compatibility byte-identique des rapports existants."""


# ============================================================================
# Public API — getters + helpers sample-rate-aware
# ============================================================================


def get_preset_by_name(name: str) -> ResolutionPreset:
    """Récupère un preset par son nom.

    Args:
        name: clé dans :data:`RESOLUTION_PRESETS` (e.g., ``"ultra"``).

    Returns:
        Le :class:`ResolutionPreset` correspondant.

    Raises:
        InvalidPresetError: si ``name`` ne correspond à aucun preset
            défini, avec message listant les 5 noms valides.
    """
    if name not in RESOLUTION_PRESETS:
        raise InvalidPresetError(
            f"Preset {name!r} inconnu. Valides : "
            f"{sorted(RESOLUTION_PRESETS)}."
        )
    return RESOLUTION_PRESETS[name]


def validate_peak_threshold_db(peak_threshold_db: float) -> None:
    """Valide qu'un threshold est dans la range autorisée.

    Args:
        peak_threshold_db: la valeur à valider.

    Raises:
        InvalidThresholdError: si hors ``[PEAK_THRESHOLD_MIN_DB,
            PEAK_THRESHOLD_MAX_DB]``.
    """
    if not (PEAK_THRESHOLD_MIN_DB <= peak_threshold_db <= PEAK_THRESHOLD_MAX_DB):
        raise InvalidThresholdError(
            f"peak_threshold_db={peak_threshold_db} hors range "
            f"[{PEAK_THRESHOLD_MIN_DB}, {PEAK_THRESHOLD_MAX_DB}]."
        )


def get_effective_stft_hop_samples(
    preset: ResolutionPreset, sample_rate: int,
) -> int:
    """Hop STFT en samples au sample rate du projet réel.

    Le hop STFT en samples est INVARIANT au sample rate (convention
    librosa : ``hop = n_fft / 4``). Donc on retourne simplement la
    valeur stockée. Helper exposé pour symétrie avec
    :func:`get_effective_cqt_hop_samples`.
    """
    del sample_rate  # noqa: F841 — paramètre exposé pour symétrie API
    return preset.stft_hop_samples_at_44k


def get_effective_stft_hop_ms(
    preset: ResolutionPreset, sample_rate: int,
) -> float:
    """Hop STFT en millisecondes au sample rate donné.

    Contrairement aux samples (invariants), le hop en ms VARIE avec sr.
    À 48 kHz : preset ``ultra`` produit hop ~85 ms (au lieu de 92.9 ms
    à 44.1 kHz). Différence marginale, acceptable.
    """
    return preset.stft_hop_samples_at_44k / sample_rate * 1000.0


def get_effective_stft_delta_freq_hz(
    preset: ResolutionPreset, sample_rate: int,
) -> float:
    """Résolution spectrale STFT (Hz/bin) au sample rate donné.

    Δf = sr / n_fft. À 48 kHz : preset ``ultra`` (n_fft=16384) produit
    Δf ~2.93 Hz (au lieu de 2.69 Hz à 44.1 kHz).
    """
    return sample_rate / preset.stft_n_fft


def get_effective_cqt_hop_samples(
    preset: ResolutionPreset, sample_rate: int,
) -> int:
    """Hop CQT en samples pour atteindre ``cqt_target_fps`` au sample rate
    donné.

    À sr=44.1 kHz, preset ``standard`` (6 fps) → hop = 7350 samples
    (~166 ms). À sr=48 kHz, même preset → hop = 8000 samples (~166 ms
    aussi en temps réel). Le preset garantit le frame rate target,
    INDÉPENDAMMENT du sample rate.

    Plancher à 512 samples (limite pratique librosa CQT).
    """
    target_hop = sample_rate / preset.cqt_target_fps
    return max(int(round(target_hop)), 512)


# ============================================================================
# Public API — exports
# ============================================================================


__all__ = [
    # Exceptions
    "ResolutionEngineError",
    "InvalidPresetError",
    "InvalidThresholdError",
    # Constants
    "PEAK_THRESHOLD_MIN_DB",
    "PEAK_THRESHOLD_MAX_DB",
    "REFERENCE_SAMPLE_RATE",
    # Dataclass + presets
    "ResolutionPreset",
    "RESOLUTION_PRESETS",
    "DEFAULT_RESOLUTION_PRESET",
    # API
    "get_preset_by_name",
    "validate_peak_threshold_db",
    "get_effective_stft_hop_samples",
    "get_effective_stft_hop_ms",
    "get_effective_stft_delta_freq_hz",
    "get_effective_cqt_hop_samples",
]
