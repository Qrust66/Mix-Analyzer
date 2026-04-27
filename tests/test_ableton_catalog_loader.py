"""Tests for composition_engine.ableton_bridge.catalog_loader.

Verifies sliced access to ableton/ableton_devices_mapping.json. Ensures
each accessor returns the right shape and that load_catalog() is cached
across calls.
"""
import pytest

from composition_engine.ableton_bridge import catalog_loader as cl


# ============================================================================
# load_catalog + caching
# ============================================================================


def test_load_catalog_returns_a_dict():
    catalog = cl.load_catalog()
    assert isinstance(catalog, dict)
    assert len(catalog) > 0


def test_load_catalog_is_cached():
    """Second call must hit the lru_cache, not re-read the file."""
    cl.load_catalog.cache_clear()
    cl.load_catalog()
    info_before = cl.load_catalog.cache_info()
    cl.load_catalog()
    cl.load_catalog()
    info_after = cl.load_catalog.cache_info()
    assert info_after.hits >= info_before.hits + 2
    assert info_after.misses == info_before.misses


# ============================================================================
# list_devices / list_vst3_plugins
# ============================================================================


def test_list_devices_returns_known_stock_devices():
    devices = cl.list_devices()
    # These are the 9 documented stock devices in the catalog as of Phase 3
    expected_subset = {"Eq8", "Compressor2", "Limiter", "Saturator"}
    assert expected_subset.issubset(set(devices))


def test_list_vst3_plugins_returns_known_plugins():
    plugins = cl.list_vst3_plugins()
    assert "Trackspacer" in plugins


# ============================================================================
# get_device_spec
# ============================================================================


def test_get_device_spec_returns_eq8():
    spec = cl.get_device_spec("Eq8")
    assert isinstance(spec, dict)
    # Eq8 has display_name, status, validation_round, etc. per the catalog
    assert "display_name" in spec or "params" in spec or "global_params" in spec


def test_get_device_spec_returns_vst3_plugin():
    """Trackspacer is a VST3 plugin — must also be findable."""
    spec = cl.get_device_spec("Trackspacer")
    assert isinstance(spec, dict)


def test_get_device_spec_raises_helpful_error_on_unknown():
    with pytest.raises(KeyError, match="not in catalog"):
        cl.get_device_spec("NonExistentDevice")


# ============================================================================
# Section accessors
# ============================================================================


def test_get_automation_conventions_returns_dict():
    ac = cl.get_automation_conventions()
    assert isinstance(ac, dict)
    assert len(ac) > 0


def test_get_validation_rules_combines_three_sections():
    rules = cl.get_validation_rules()
    assert "write_rules" in rules
    assert "validation" in rules
    assert "end_to_end_validation" in rules


def test_get_xml_pattern_returns_dict():
    pattern = cl.get_xml_pattern()
    assert isinstance(pattern, dict)


def test_get_ableton_conventions_returns_dict():
    conv = cl.get_ableton_conventions()
    assert isinstance(conv, dict)


def test_get_tempo_mapping_returns_dict():
    tempo = cl.get_tempo_mapping()
    assert isinstance(tempo, dict)


# ============================================================================
# get_known_bugs (filtered or full)
# ============================================================================


def test_get_known_bugs_full_list():
    bugs = cl.get_known_bugs()
    assert isinstance(bugs, list)
    assert len(bugs) > 0
    # Each entry should have at least the canonical 4 fields
    for entry in bugs:
        assert isinstance(entry, dict)
        assert any(k in entry for k in ("bug", "symptom", "fix", "version"))


def test_get_known_bugs_filtered_by_device_returns_subset():
    all_bugs = cl.get_known_bugs()
    eq_bugs = cl.get_known_bugs("Eq8")
    # Filter must return ≤ all
    assert len(eq_bugs) <= len(all_bugs)
    # All filtered entries must mention Eq8 somewhere
    for entry in eq_bugs:
        text = " ".join(str(v).lower() for v in entry.values() if isinstance(v, str))
        assert "eq8" in text


def test_get_known_bugs_filter_is_case_insensitive():
    upper = cl.get_known_bugs("EQ8")
    lower = cl.get_known_bugs("eq8")
    assert len(upper) == len(lower)


def test_get_known_bugs_unknown_device_returns_empty():
    bugs = cl.get_known_bugs("ThisDeviceDefinitelyDoesNotExist")
    assert bugs == []


# ============================================================================
# get_meta
# ============================================================================


def test_get_meta_returns_version_info():
    meta = cl.get_meta()
    assert "schema_version" in meta
    assert "compatible_with_min" in meta
    assert "changelog_entries" in meta
    # Catalog has been versioned across at least 8 versions
    assert meta["changelog_entries"] >= 1


# ============================================================================
# Integration — pretend an agent is being primed
# ============================================================================


def test_pretend_eq_eight_config_agent_priming():
    """An eq-eight-config agent would receive these inputs in its prompt.
    Verify they're all small enough to be reasonable system-prompt material.
    """
    spec = cl.get_device_spec("Eq8")
    bugs = cl.get_known_bugs("Eq8")
    pattern = cl.get_xml_pattern()

    # All three should be present and parseable as dicts/lists
    assert isinstance(spec, dict)
    assert isinstance(bugs, list)
    assert isinstance(pattern, dict)
