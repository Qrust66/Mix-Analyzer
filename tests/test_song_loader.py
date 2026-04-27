"""Smoke tests for composition_engine.advisor_bridge.song_loader."""
import pytest

from composition_engine.advisor_bridge import song_loader as sl


def test_list_artists_returns_seven_artists():
    artists = sl.list_artists()
    assert len(artists) == 7
    assert "Nirvana" in artists
    assert "Radiohead" in artists


def test_list_songs_returns_34_real_songs():
    songs = sl.list_songs()
    # Was 35; Around_The_World removed by user request (out of stylistic scope).
    assert len(songs) == 34
    # _meta keys must be excluded
    for artist, song in songs:
        assert not song.startswith("_")


def test_list_songs_filtered_by_artist():
    nirvana_songs = sl.list_songs("Nirvana")
    assert all(a == "Nirvana" for a, _ in nirvana_songs)
    assert len(nirvana_songs) >= 1


def test_get_song_returns_full_dict():
    song = sl.get_song("Nirvana", "Heart_Shaped_Box")
    for key in ("album", "year", "composition", "arrangement", "performance",
                "recording", "mixing", "mastering"):
        assert key in song, f"Expected field {key!r} in song dict"
    assert song["album"] == "In Utero"


def test_get_song_unknown_artist_raises():
    with pytest.raises(KeyError, match="Unknown artist"):
        sl.get_song("Beatles", "Yesterday")


def test_get_song_unknown_song_raises():
    with pytest.raises(KeyError, match="Unknown song"):
        sl.get_song("Nirvana", "Nonexistent_Track")


def test_find_song_partial_name_match():
    artist, song, data = sl.find_song("Heart_Shaped_Box")
    assert artist == "Nirvana"
    assert song == "Heart_Shaped_Box"
    assert "album" in data


def test_find_song_unknown_raises():
    with pytest.raises(KeyError, match="No song matching"):
        sl.find_song("definitely_not_a_song")


def test_query_resolves_song_path():
    hm = sl.query("Nirvana.Heart_Shaped_Box.composition.harmonic_motion")
    assert isinstance(hm, str)
    assert len(hm) > 0


def test_query_resolves_top_level_path():
    dc = sl.query("density_curves")
    assert isinstance(dc, dict)


def test_query_unknown_path_raises():
    with pytest.raises(KeyError):
        sl.query("Nirvana.Heart_Shaped_Box.nonexistent_field")


def test_get_advisor_section_returns_dict():
    section = sl.get_advisor_section("voice_leading")
    assert isinstance(section, dict)


def test_advisor_loaded_only_once_via_cache():
    sl._load_advisor.cache_clear()
    sl.list_artists()
    info_before = sl._load_advisor.cache_info()
    sl.list_songs()
    sl.get_song("Nirvana", "Heart_Shaped_Box")
    info_after = sl._load_advisor.cache_info()
    # Hits should grow, not misses (file read happens once)
    assert info_after.hits > info_before.hits
    assert info_after.misses == info_before.misses
