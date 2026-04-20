"""Tests for persisted user paths (input/output/.als) across runs.

Covers `user_config.load_user_paths` and `user_config.save_user_paths`
introduced in v2.6.x. Tests isolate the global config file location with
monkeypatch so the developer's real ~/.mix_analyzer/config.json is never
touched.
"""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import user_config  # noqa: E402


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Redirect USER_CONFIG_DIR/FILE to a temp path for the test."""
    cfg_dir = tmp_path / '.mix_analyzer'
    cfg_file = cfg_dir / 'config.json'
    monkeypatch.setattr(user_config, 'USER_CONFIG_DIR', cfg_dir)
    monkeypatch.setattr(user_config, 'USER_CONFIG_FILE', cfg_file)
    return cfg_file


def test_load_returns_empty_defaults_when_no_file(isolated_config):
    assert user_config.load_user_paths() == {
        'input_folder': '',
        'output_folder': '',
        'als_path': '',
    }


def test_save_then_load_roundtrip(isolated_config):
    user_config.save_user_paths(
        input_folder='/wav/bounces',
        output_folder='/wav/reports',
        als_path='/wav/project.als',
    )
    assert isolated_config.is_file()
    loaded = user_config.load_user_paths()
    assert loaded == {
        'input_folder': '/wav/bounces',
        'output_folder': '/wav/reports',
        'als_path': '/wav/project.als',
    }


def test_load_tolerates_obsolete_paths(isolated_config):
    """Paths that no longer exist on disk are still returned as-is —
    the user can fix them in the UI rather than starting from scratch."""
    user_config.save_user_paths(
        input_folder='/gone/wav',
        output_folder='/vanished/reports',
        als_path='/deleted/song.als',
    )
    loaded = user_config.load_user_paths()
    assert loaded['input_folder'] == '/gone/wav'
    assert loaded['output_folder'] == '/vanished/reports'
    assert loaded['als_path'] == '/deleted/song.als'


def test_load_tolerates_corrupt_json(isolated_config):
    isolated_config.parent.mkdir(parents=True, exist_ok=True)
    isolated_config.write_text('{ not valid json')
    assert user_config.load_user_paths() == {
        'input_folder': '',
        'output_folder': '',
        'als_path': '',
    }


def test_load_tolerates_partial_keys(isolated_config):
    """Config written by an older version may lack als_path."""
    isolated_config.parent.mkdir(parents=True, exist_ok=True)
    isolated_config.write_text(json.dumps({
        'input_folder': '/wav',
        'output_folder': '/out',
    }))
    loaded = user_config.load_user_paths()
    assert loaded['input_folder'] == '/wav'
    assert loaded['output_folder'] == '/out'
    assert loaded['als_path'] == ''


def test_save_empty_overwrites_previous(isolated_config):
    user_config.save_user_paths('/a', '/b', '/c.als')
    user_config.save_user_paths()  # all defaults: empty
    loaded = user_config.load_user_paths()
    assert loaded == {
        'input_folder': '',
        'output_folder': '',
        'als_path': '',
    }


def test_save_creates_parent_directory(tmp_path, monkeypatch):
    """Dir does not exist yet — save must create it."""
    cfg_dir = tmp_path / 'nested' / '.mix_analyzer'
    cfg_file = cfg_dir / 'config.json'
    monkeypatch.setattr(user_config, 'USER_CONFIG_DIR', cfg_dir)
    monkeypatch.setattr(user_config, 'USER_CONFIG_FILE', cfg_file)
    assert not cfg_dir.exists()
    user_config.save_user_paths('/x', '/y', '')
    assert cfg_file.is_file()
