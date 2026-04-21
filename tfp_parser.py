#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tfp_parser.py — Track Function Profile (TFP) parsing for Feature 3.5.

Parses the user-authored role codes that live in Ableton track names and in
Locator annotations, and resolves a track's final role per section.

Taxonomy:
    Importance = H (Hero) / S (Support) / A (Atmos)
    Function   = R (Rhythm) / H (Harmonic) / M (Melodic) / T (Textural)

Three public helpers:
    - ``parse_tfp_prefix(name)``        → ``(Importance, Function, clean_name)`` or ``None``
    - ``parse_tfp_overrides(annotation)`` → ``dict[str, tuple[Importance|None, Function|None]]``
    - ``resolve_track_role(name, overrides, default)`` → ``(Importance, Function)``

Designed as a pure, dependency-free module so it can be unit-tested
exhaustively and reused by Feature 3.6 (Correction Diagnostic Engine)
without pulling in the audio / openpyxl stack.
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Dict, Optional, Tuple


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

class Importance(Enum):
    """Dimension 1 — role in the mix."""
    H = "H"  # Hero
    S = "S"  # Support
    A = "A"  # Atmos


class Function(Enum):
    """Dimension 2 — musical function."""
    R = "R"  # Rhythm
    H = "H"  # Harmonic
    M = "M"  # Melodic
    T = "T"  # Textural


# Default role for tracks that have no TFP prefix — see R2 in the spec.
DEFAULT_ROLE: Tuple[Importance, Function] = (Importance.S, Function.R)


# Long-form aliases accepted in Locator override annotations (R3).
_IMPORTANCE_LONG: Dict[str, Importance] = {
    "hero": Importance.H,
    "support": Importance.S,
    "atmos": Importance.A,
}
_FUNCTION_LONG: Dict[str, Function] = {
    "rhythm": Function.R,
    "harmonic": Function.H,
    "melodic": Function.M,
    "textural": Function.T,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_importance(code: str) -> Optional[Importance]:
    """Accept a short ('h'/'s'/'a') or long ('hero'/'support'/'atmos') code.

    Returns None for anything else — callers handle rejection.
    """
    s = code.strip().lower()
    if len(s) == 1:
        upper = s.upper()
        try:
            return Importance(upper)
        except ValueError:
            return None
    return _IMPORTANCE_LONG.get(s)


def _to_function(code: str) -> Optional[Function]:
    """Accept a short ('r'/'h'/'m'/'t') or long code."""
    s = code.strip().lower()
    if len(s) == 1:
        upper = s.upper()
        try:
            return Function(upper)
        except ValueError:
            return None
    return _FUNCTION_LONG.get(s)


# Strict prefix regex — R1 of the spec:
#   - Optional leading whitespace (trimmed before matching)
#   - Square brackets mandatory
#   - Slash separator mandatory
#   - Exactly one letter per dimension in the bracket
#   - Mandatory whitespace between closing bracket and the name
# Case-insensitive in input (the match groups lowercase-compare later).
_PREFIX_RE = re.compile(
    r"^\[\s*([HSAhsa])\s*/\s*([RHMTrhmt])\s*\]\s+(.+)$"
)

# Token parser for one "name=value" override pair — R3 format rules.
# We use a pre-parse split on "," to isolate pairs, then this regex enforces
# the strict "no spaces around `=`" rule on each pair.
_OVERRIDE_PAIR_RE = re.compile(
    r"^(?P<name>[^=]+?)=(?P<value>[^=]+)$"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_tfp_prefix(
    name: str,
) -> Optional[Tuple[Importance, Function, str]]:
    """Extract the TFP prefix from an Ableton track name.

    Args:
        name: Raw track name, e.g. ``"[H/R] Kick 1"``.

    Returns:
        ``(importance, function, clean_name)`` when the prefix matches the
        strict R1 format, where ``clean_name`` is the name with the prefix
        and its separating whitespace removed. Returns ``None`` when the
        prefix is absent or malformed (the caller decides what to do —
        typically fall back to :data:`DEFAULT_ROLE` and warn).

    Notes:
        Case-insensitive on the role codes; letter case inside ``clean_name``
        is preserved. Trailing bracket notation in the name body is kept
        (e.g. ``"[H/R] [draft] Kick 1"`` yields ``clean_name="[draft] Kick 1"``).
    """
    if not isinstance(name, str):
        return None
    stripped = name.strip()
    if not stripped:
        return None

    match = _PREFIX_RE.match(stripped)
    if match is None:
        return None

    imp_code, fn_code, body = match.group(1), match.group(2), match.group(3)
    importance = _to_importance(imp_code)
    function = _to_function(fn_code)
    if importance is None or function is None:
        # The regex character class should keep us from landing here, but
        # being defensive guards against future regex edits.
        logger.warning("TFP: invalid role codes in prefix %r", name)
        return None

    return importance, function, body


def parse_tfp_overrides(
    annotation: str,
) -> Dict[str, Tuple[Optional[Importance], Optional[Function]]]:
    """Parse the ``override:`` clause of a Locator annotation.

    Format (R3 of the spec):
        ``override: Track1=X-Y, Track2=X, Track3=*-Y``

    Rules:
        - No spaces around ``=`` (strict); any pair violating this is rejected.
        - Comma-separated pairs; leading spaces after commas are tolerated.
        - Right-hand side forms: ``X-Y`` (both dims), ``X`` (importance only),
          ``*-Y`` (function only). Short codes and long words both accepted.
        - Track names on the left-hand side are trimmed and stored as-is
          (case normalisation is the caller's job — ``resolve_track_role``
          matches case-insensitively).
        - Duplicate track names: the **last** value wins, matching the R3 rule.
        - Malformed pairs are logged and skipped; they do not abort the parse.

    Args:
        annotation: Raw annotation text from a Locator; may be empty.

    Returns:
        ``{track_name: (importance_or_None, function_or_None)}`` — ``None``
        on a dimension means "do not override that dimension". An empty
        dict is returned when the annotation is empty, does not start with
        ``override:``, or contains only malformed pairs.
    """
    if not isinstance(annotation, str):
        return {}
    text = annotation.strip()
    if not text:
        return {}

    # R3 requires a literal "override:" prefix followed by at least one
    # whitespace. No space → reject the whole clause.
    if not text.lower().startswith("override:"):
        return {}
    after_prefix = text[len("override:"):]
    if not after_prefix.startswith((" ", "\t")):
        logger.warning(
            "TFP override: missing space after ':' — whole clause ignored (%r)",
            annotation,
        )
        return {}

    payload = after_prefix.lstrip()
    if not payload:
        return {}

    result: Dict[str, Tuple[Optional[Importance], Optional[Function]]] = {}
    for raw_pair in payload.split(","):
        pair = raw_pair.strip()
        if not pair:
            continue

        match = _OVERRIDE_PAIR_RE.match(pair)
        if match is None:
            logger.warning("TFP override: malformed pair %r — skipped", pair)
            continue

        name_raw = match.group("name")
        value_raw = match.group("value")

        # Strict "no spaces around =" rule: if the captured name has
        # trailing whitespace, or the value has leading whitespace, the
        # original had spaces around the equal sign.
        if name_raw != name_raw.rstrip() or value_raw != value_raw.lstrip():
            logger.warning(
                "TFP override: spaces around '=' in %r — pair rejected", pair
            )
            continue

        name = name_raw.rstrip()
        value = value_raw.strip()
        if not name or not value:
            continue

        parsed = _parse_override_value(value)
        if parsed is None:
            logger.warning(
                "TFP override: invalid value %r for %r — pair rejected",
                value, name,
            )
            continue

        # Duplicate name: last one wins (R3).
        result[name] = parsed

    return result


def resolve_track_role(
    name: str,
    section_overrides: Dict[str, Tuple[Optional[Importance], Optional[Function]]],
    default: Tuple[Importance, Function] = DEFAULT_ROLE,
) -> Tuple[Importance, Function]:
    """Resolve a track's final role for one section (R4 of the spec).

    Steps:
        1. Parse the prefix embedded in ``name``. If found, the prefix
           becomes the base role; otherwise ``default`` is the base.
        2. Look up ``section_overrides`` by the **clean** name
           (without prefix), case-insensitively. A matching entry replaces
           whichever dimensions it specifies; unspecified dimensions keep
           the base value.

    Args:
        name: The track name *with* any TFP prefix still attached
            (e.g. ``"[H/R] Kick 1"`` or ``"Kick 1"``).
        section_overrides: Mapping returned by :func:`parse_tfp_overrides`.
        default: Role used when ``name`` has no prefix. Defaults to
            :data:`DEFAULT_ROLE` (Support / Rhythm), as specified in R2.

    Returns:
        ``(importance, function)`` — the effective role for this track in
        this section. Used both by the DUREE ACTIVE / PEAK MAX columns and
        by :mod:`tfp_coherence` when computing the section score.
    """
    parsed = parse_tfp_prefix(name)
    if parsed is not None:
        imp, fn, clean = parsed
    else:
        imp, fn = default
        clean = name.strip()

    if section_overrides:
        override_imp, override_fn = _lookup_override(clean, section_overrides)
        if override_imp is not None:
            imp = override_imp
        if override_fn is not None:
            fn = override_fn

    return imp, fn


# ---------------------------------------------------------------------------
# Private: override value parsing
# ---------------------------------------------------------------------------

def _parse_override_value(
    value: str,
) -> Optional[Tuple[Optional[Importance], Optional[Function]]]:
    """Parse the right-hand side of a ``name=value`` override pair.

    Accepts ``X-Y``, ``X``, ``*-Y`` forms in both short and long variants.
    Returns ``None`` on any unrecognised shape — the caller logs and skips.
    """
    if "-" in value:
        parts = value.split("-", 1)
        if len(parts) != 2:
            return None
        imp_part, fn_part = parts[0].strip(), parts[1].strip()
        if not imp_part or not fn_part:
            return None

        # Wildcard on the importance side = "keep base importance, set function"
        if imp_part == "*":
            fn = _to_function(fn_part)
            return (None, fn) if fn is not None else None

        imp = _to_importance(imp_part)
        fn = _to_function(fn_part)
        if imp is None or fn is None:
            return None
        return (imp, fn)

    # No dash → importance-only override
    imp = _to_importance(value)
    if imp is None:
        return None
    return (imp, None)


def _lookup_override(
    clean_name: str,
    section_overrides: Dict[str, Tuple[Optional[Importance], Optional[Function]]],
) -> Tuple[Optional[Importance], Optional[Function]]:
    """Case-insensitive lookup into the override dict.

    The override dict keys preserve the user's original casing; the stored
    track name (from Ableton's ``EffectiveName``) may differ in case, so
    we normalise both sides before comparing.
    """
    needle = clean_name.strip().lower()
    for key, value in section_overrides.items():
        if key.strip().lower() == needle:
            return value
    return (None, None)
