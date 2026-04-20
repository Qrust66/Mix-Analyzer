#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
user_config.py — persisted user paths for Mix Analyzer v2.6.x

Stores the 3 paths the user selects at launch (input folder, output folder,
Ableton .als file) in ~/.mix_analyzer/config.json so they survive a restart.

Kept as a tiny dependency-free module so it can be imported (and unit-tested)
without pulling in numpy / librosa / tkinter.
"""

import json
from pathlib import Path


USER_CONFIG_DIR = Path.home() / '.mix_analyzer'
USER_CONFIG_FILE = USER_CONFIG_DIR / 'config.json'

_KEYS = ('input_folder', 'output_folder', 'als_path')


def load_user_paths():
    """Return last-used {input_folder, output_folder, als_path}.

    Missing file, unreadable file, or corrupt JSON all yield empty strings —
    the UI simply starts blank and the user proceeds normally.
    """
    defaults = {k: '' for k in _KEYS}
    try:
        if USER_CONFIG_FILE.is_file():
            with open(USER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return {k: str(data.get(k, '') or '') for k in _KEYS}
    except Exception as e:
        print(f"[Mix Analyzer] Could not load user config: {e}")
    return defaults


def save_user_paths(input_folder='', output_folder='', als_path=''):
    """Persist paths to ~/.mix_analyzer/config.json. Never raises."""
    try:
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            'input_folder': input_folder or '',
            'output_folder': output_folder or '',
            'als_path': als_path or '',
        }
        with open(USER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Mix Analyzer] Could not save user config: {e}")
