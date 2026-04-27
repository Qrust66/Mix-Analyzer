"""catalog_loader — read-only access to ableton/ableton_devices_mapping.json.

Why this exists:

The master catalog (~5500 lines) documents 9 Ableton stock devices, 2 VST3
plugins, plus extensive meta-knowledge about XML patterns, automation
envelopes, validation rules, and 9 known bugs from past sessions.

Loading the entire file into a device-config agent's prompt would cost
~15K tokens per invocation. With 7+ Ableton-side agents planned (one per
device + automation-engineer + chain-builder + track-manipulator), that
inflation compounds fast.

This loader slices the catalog so each agent receives only the section
relevant to its scope:

  device-config agent for Eq8       → get_device_spec("Eq8") + get_known_bugs("Eq8")
  automation-engineer               → get_automation_conventions() + get_xml_pattern()
  chain-builder                     → get_validation_rules() + xml conventions
  track-manipulator                 → get_xml_pattern() + ableton_conventions
  any agent that touches XML        → get_known_bugs() (filtered or full)

The catalog file itself stays monolithic — it's hand-curated by the user
across 8+ versions. Splitting it physically would create migration churn
without changing the per-agent token cost (which the loader handles).

Mirrors the song_loader pattern from composition_engine.advisor_bridge.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

_CATALOG_JSON = (
    Path(__file__).resolve().parents[2]
    / "ableton"
    / "ableton_devices_mapping.json"
)


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    """Load and cache the master catalog (~5500 lines, ~110 KB).

    Loaded once per process; subsequent calls are free. Tests may call
    `load_catalog.cache_clear()` between modifications.
    """
    return json.loads(_CATALOG_JSON.read_text(encoding="utf-8"))


# ============================================================================
# Sliced accessors
# ============================================================================


def list_devices() -> list[str]:
    """Return all stock device names declared in `devices.*`."""
    return list(load_catalog().get("devices", {}).keys())


def list_vst3_plugins() -> list[str]:
    """Return all VST3 plugin names declared in `vst3_plugins.*`."""
    return list(load_catalog().get("vst3_plugins", {}).keys())


def get_device_spec(name: str) -> dict:
    """Return the catalog slice for a single device or VST3 plugin.

    Searches both `devices.*` (Ableton stock) and `vst3_plugins.*`.
    Raises KeyError with a helpful message if not found.
    """
    catalog = load_catalog()

    if name in catalog.get("devices", {}):
        return catalog["devices"][name]
    if name in catalog.get("vst3_plugins", {}):
        return catalog["vst3_plugins"][name]

    available = sorted(list_devices() + list_vst3_plugins())
    raise KeyError(
        f"Device {name!r} not in catalog. "
        f"Known devices ({len(available)}): {available}"
    )


def get_automation_conventions() -> dict:
    """Return the `$automation_envelopes` section.

    Used by the future automation-engineer agent. Contains XML location,
    envelope structure, AutomationTarget Id rules, event types, time
    format, and a worked example.
    """
    return load_catalog().get("$automation_envelopes", {})


def get_validation_rules() -> dict:
    """Return validation + write rules combined.

    Used by any agent that emits XML to `.als`: write_rules sets the
    invariants the XML must satisfy; validation specifies how to check
    afterwards.
    """
    catalog = load_catalog()
    return {
        "write_rules": catalog.get("$write_rules", {}),
        "validation": catalog.get("$validation", {}),
        "end_to_end_validation": catalog.get("$end_to_end_validation", {}),
    }


def get_xml_pattern() -> dict:
    """Return the `$xml_pattern` section: how Ableton structures the
    `.als` XML at the device-chain level. Universal — every Ableton-side
    agent should be primed with this to avoid the self-closing-element
    pitfalls documented in `$known_bugs_resolved`."""
    return load_catalog().get("$xml_pattern", {})


def get_known_bugs(device: Optional[str] = None) -> list[dict]:
    """Return the `$known_bugs_resolved` list.

    If `device` is given, return only the bugs whose entry mentions that
    device name (case-insensitive substring match across bug fields).
    If `device` is None, return all known bugs.

    These should be primed into every Ableton-side agent's system prompt
    so past mistakes aren't repeated.
    """
    bugs = load_catalog().get("$known_bugs_resolved", [])
    if device is None:
        return list(bugs)
    needle = device.lower()
    out: list[dict] = []
    for entry in bugs:
        if not isinstance(entry, dict):
            continue
        haystack = " ".join(
            str(v).lower() for v in entry.values() if isinstance(v, str)
        )
        if needle in haystack:
            out.append(entry)
    return out


def get_ableton_conventions() -> dict:
    """Return the `$ableton_conventions` section: file naming, addressing,
    track-level rules, etc."""
    return load_catalog().get("$ableton_conventions", {})


def get_tempo_mapping() -> dict:
    """Return the `$tempo_mapping` section."""
    return load_catalog().get("$tempo_mapping", {})


def get_meta() -> dict:
    """Return version + compatibility metadata."""
    catalog = load_catalog()
    return {
        "schema_version": catalog.get("$schema_version"),
        "compatible_with_min": catalog.get("$compatible_with_min"),
        "milestone": catalog.get("$milestone"),
        "purpose": catalog.get("$purpose"),
        "changelog_entries": len(catalog.get("$changelog", [])),
    }


__all__ = [
    "load_catalog",
    "list_devices",
    "list_vst3_plugins",
    "get_device_spec",
    "get_automation_conventions",
    "get_validation_rules",
    "get_xml_pattern",
    "get_known_bugs",
    "get_ableton_conventions",
    "get_tempo_mapping",
    "get_meta",
]


if __name__ == "__main__":
    meta = get_meta()
    print(f"Catalog schema {meta['schema_version']} (Ableton min {meta['compatible_with_min']})")
    print(f"Purpose: {meta['purpose'][:80]}...")
    print()
    print(f"Stock devices ({len(list_devices())}): {list_devices()}")
    print(f"VST3 plugins  ({len(list_vst3_plugins())}): {list_vst3_plugins()}")
    print()
    print(f"Known bugs total: {len(get_known_bugs())}")
    eq_bugs = get_known_bugs("Eq8")
    print(f"Bugs mentioning Eq8: {len(eq_bugs)}")
    if eq_bugs:
        print(f"  example: {eq_bugs[0].get('bug', '')[:60]}")
