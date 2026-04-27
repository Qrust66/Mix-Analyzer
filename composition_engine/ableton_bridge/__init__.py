"""Ableton-side integration for the composition_engine.

Bridges blueprint decisions to Ableton .als manipulation. Currently
exposes only the catalog_loader (read-only access to
ableton/ableton_devices_mapping.json). Phase 3+ will add the actual
Ableton-side agents (device-config, chain-builder, track-manipulator,
automation-engineer) that consume this catalog.
"""
from composition_engine.ableton_bridge.catalog_loader import (
    get_automation_conventions,
    get_device_spec,
    get_known_bugs,
    get_validation_rules,
    get_xml_pattern,
    list_devices,
    load_catalog,
)

__all__ = [
    "get_automation_conventions",
    "get_device_spec",
    "get_known_bugs",
    "get_validation_rules",
    "get_xml_pattern",
    "list_devices",
    "load_catalog",
]
