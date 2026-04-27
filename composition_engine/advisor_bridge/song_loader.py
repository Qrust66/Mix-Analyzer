"""
song_loader — Read access to the 35 reference song dissections.

Bridges composition_engine to composition_advisor/composition_advisor.json,
specifically to song_dissection_exhaustive.by_artist.{ARTIST}.{SONG}.

Designed as the single source-of-truth loader for any future agent or
module that wants to consume reference-song data (structure, harmony,
arrangement, dynamic arc, mixing, …) instead of hardcoding rules.

The JSON is loaded once via lru_cache; subsequent calls are free.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_ADVISOR_JSON = (
    Path(__file__).resolve().parents[2]
    / "composition_advisor"
    / "composition_advisor.json"
)


@lru_cache(maxsize=1)
def _load_advisor() -> dict:
    """Load and cache the full advisor JSON (~2.2 MB)."""
    return json.loads(_ADVISOR_JSON.read_text(encoding="utf-8"))


def _by_artist() -> dict:
    return _load_advisor()["song_dissection_exhaustive"]["by_artist"]


def list_artists() -> list[str]:
    """Return the 7 artists with exhaustive dissections."""
    return list(_by_artist().keys())


def list_songs(artist: str | None = None) -> list[tuple[str, str]]:
    """Return (artist, song) pairs for the 35 real songs.

    Skips `_meta` keys (per-artist metadata, not a song).
    If `artist` is given, filters to that artist only.
    """
    by_artist = _by_artist()
    artists = [artist] if artist else list(by_artist.keys())
    pairs: list[tuple[str, str]] = []
    for a in artists:
        if a not in by_artist:
            continue
        for s in by_artist[a]:
            if s.startswith("_"):
                continue
            pairs.append((a, s))
    return pairs


def get_song(artist: str, song: str) -> dict:
    """Return the full dissection dict for a song.

    Raises KeyError with a helpful message if the artist or song is unknown.
    """
    by_artist = _by_artist()
    if artist not in by_artist:
        raise KeyError(
            f"Unknown artist: {artist!r}. Available: {list(by_artist.keys())}"
        )
    if song not in by_artist[artist]:
        available = [s for s in by_artist[artist] if not s.startswith("_")]
        raise KeyError(
            f"Unknown song {song!r} for {artist}. Available: {available}"
        )
    return by_artist[artist][song]


def find_song(name: str) -> tuple[str, str, dict]:
    """Find a song by partial/case-insensitive name across all artists.

    Returns (artist, song_key, song_dict). Raises:
    - KeyError if no match
    - ValueError if ambiguous (multiple matches)
    """
    needle = name.lower().replace(" ", "_")
    matches: list[tuple[str, str]] = []
    for a, s in list_songs():
        if needle == s.lower() or needle in s.lower():
            matches.append((a, s))
    if not matches:
        raise KeyError(f"No song matching {name!r}")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous song name {name!r}: matches {matches}. "
            f"Use get_song(artist, song) explicitly."
        )
    a, s = matches[0]
    return a, s, get_song(a, s)


def query(path: str) -> Any:
    """Resolve a dotted path against the advisor JSON.

    Two forms accepted:
    - Top-level: "density_curves", "voice_leading.cadence_table", etc.
    - Song path: "Nirvana.Heart_Shaped_Box.composition.harmonic_motion"

    Lists are indexed by integer ("recipes_index.recipes.0").
    """
    advisor = _load_advisor()
    parts = path.split(".")

    # Decide which root to start from. If first part is a known top-level
    # key (and not the song dissection containers), start at advisor root.
    # Otherwise treat first two parts as artist + song.
    if parts[0] in advisor and parts[0] not in (
        "song_dissection",
        "song_dissection_exhaustive",
    ):
        node: Any = advisor
        remaining = parts
    else:
        if len(parts) < 2:
            raise KeyError(
                f"Path {path!r}: expected 'artist.song[.field…]' or a top-level key. "
                f"Available top-level keys: {list(advisor.keys())}"
            )
        node = get_song(parts[0], parts[1])
        remaining = parts[2:]

    for p in remaining:
        if isinstance(node, dict):
            if p not in node:
                raise KeyError(
                    f"Path {path!r}: key {p!r} not found. "
                    f"Available: {list(node.keys())}"
                )
            node = node[p]
        elif isinstance(node, list):
            try:
                node = node[int(p)]
            except (ValueError, IndexError) as exc:
                raise KeyError(
                    f"Path {path!r}: cannot index list with {p!r} ({exc})"
                ) from exc
        else:
            raise KeyError(
                f"Path {path!r} stopped at {p!r}: parent is {type(node).__name__}"
            )
    return node


def get_advisor_section(key: str) -> Any:
    """Direct access to a top-level advisor key.

    Convenience over query() when you just want a whole section
    (e.g. `get_advisor_section('density_curves')`).
    """
    advisor = _load_advisor()
    if key not in advisor:
        raise KeyError(
            f"Unknown advisor key {key!r}. Available: {list(advisor.keys())}"
        )
    return advisor[key]


__all__ = [
    "list_artists",
    "list_songs",
    "get_song",
    "find_song",
    "query",
    "get_advisor_section",
]


if __name__ == "__main__":
    print(f"Artists ({len(list_artists())}): {list_artists()}")
    print(f"Total real songs: {len(list_songs())}")
    print()
    a, s, song = find_song("Heart_Shaped_Box")
    print(f"Found: {a} / {s}")
    print(f"  album: {song['album']} ({song['year']})")
    print(f"  key:   {song['key_area'][:60]}…")
    print(f"  tempo: {song['tempo_bpm_documented_range']}")
    print(f"  composition keys: {list(song['composition'].keys())}")
    print()
    hm = query("Nirvana.Heart_Shaped_Box.composition.harmonic_motion")
    print(f"harmonic_motion preview: {str(hm)[:100]}…")
