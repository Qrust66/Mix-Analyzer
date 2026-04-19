#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ALS Utilities v2.6.0 - Ableton Live Set file manipulation tools.

Ableton .als files are gzip-compressed XML. This module provides tools to:
- Decompress .als -> .xml (for reading/editing/version control)
- Recompress .xml -> .als (for loading back into Ableton)
- Inspect and modify ALS content programmatically

Usage (CLI):
    python als_utils.py decompress project.als              # -> project.als.xml
    python als_utils.py compress project.als.xml            # -> project.als
    python als_utils.py info project.als                    # show project summary
"""

import copy
import gzip
import re
import sys
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Union

TempoEvents = Sequence[Tuple[float, float]]
TempoLike = Union[float, int, TempoEvents]


def decompress_als(als_path: str, output_path: str | None = None) -> str:
    """Decompress an .als file to readable XML.

    Args:
        als_path: Path to the .als file.
        output_path: Optional output path. Defaults to <als_path>.xml

    Returns:
        Path to the decompressed XML file.
    """
    als_path = Path(als_path)
    if not als_path.exists():
        raise FileNotFoundError(f"File not found: {als_path}")

    if output_path is None:
        output_path = str(als_path) + ".xml"
    output_path = Path(output_path)

    with gzip.open(als_path, "rb") as f:
        xml_data = f.read()

    output_path.write_bytes(xml_data)
    print(f"Decompressed: {als_path} -> {output_path} ({len(xml_data):,} bytes)")
    return str(output_path)


def compress_to_als(xml_path: str, output_path: str | None = None) -> str:
    """Compress an XML file back to .als format.

    Args:
        xml_path: Path to the XML file.
        output_path: Optional output path. Defaults to removing .xml extension.

    Returns:
        Path to the compressed .als file.
    """
    xml_path = Path(xml_path)
    if not xml_path.exists():
        raise FileNotFoundError(f"File not found: {xml_path}")

    if output_path is None:
        if xml_path.suffix == ".xml" and xml_path.stem.endswith(".als"):
            output_path = xml_path.with_suffix("")  # Remove .xml -> keep .als
        else:
            output_path = xml_path.with_suffix(".als")
    output_path = Path(output_path)

    xml_data = xml_path.read_bytes()

    with gzip.open(output_path, "wb") as f:
        f.write(xml_data)

    compressed_size = output_path.stat().st_size
    print(f"Compressed: {xml_path} -> {output_path} ({compressed_size:,} bytes)")
    return str(output_path)


def parse_als(als_path: str) -> ET.ElementTree:
    """Parse an .als file and return the XML ElementTree.

    Args:
        als_path: Path to the .als file.

    Returns:
        Parsed ElementTree object.
    """
    with gzip.open(als_path, "rb") as f:
        return ET.parse(f)


def get_als_xml_string(als_path: str) -> str:
    """Read an .als file and return its XML content as a string.

    Args:
        als_path: Path to the .als file.

    Returns:
        XML content as a string.
    """
    with gzip.open(als_path, "rb") as f:
        return f.read().decode("utf-8")


def _bump_next_pointee_id(tree: ET.ElementTree) -> int | None:
    """Update ``<NextPointeeId>`` so it exceeds the max ``Id`` in the tree.

    Ableton refuses to open a file with the error
    ``"NextPointeeId is too low: X must be bigger than Y"`` whenever the
    counter is not strictly greater than the highest Id present in the
    project.  We must bump it every time we add new EQ8 devices or
    automation envelopes.

    Returns the new counter value, or None if the element is missing.
    """
    next_pid_elem = tree.getroot().find(".//NextPointeeId")
    if next_pid_elem is None:
        return None

    max_id = 0
    for elem in tree.getroot().iter():
        raw = elem.get("Id")
        if raw is not None:
            try:
                v = int(raw)
                if v > max_id:
                    max_id = v
            except ValueError:
                pass

    new_value = max_id + 1
    next_pid_elem.set("Value", str(new_value))
    return new_value


def save_als_from_tree(tree: ET.ElementTree, output_path: str) -> str:
    """Save an ElementTree back to a gzip-compressed .als file.

    Args:
        tree: The ElementTree to save.
        output_path: Path for the output .als file.

    Returns:
        Path to the saved file.
    """
    # Keep <NextPointeeId> strictly above max(Id) — Live refuses to load
    # a project whose counter is stale.
    _bump_next_pointee_id(tree)

    output_path = Path(output_path)
    # Manually prepend the XML declaration that matches Ableton's native format
    # (double-quoted attributes, uppercase UTF-8) so Live's parser sees the same
    # header it produces itself.
    xml_body = ET.tostring(tree.getroot(), encoding="unicode")
    xml_bytes = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_body

    with gzip.open(output_path, "wb") as f:
        f.write(xml_bytes.encode("utf-8"))

    print(f"Saved: {output_path} ({output_path.stat().st_size:,} bytes)")
    return str(output_path)


def als_info(als_path: str) -> dict:
    """Extract summary information from an .als file.

    Args:
        als_path: Path to the .als file.

    Returns:
        Dictionary with project info.
    """
    tree = parse_als(als_path)
    root = tree.getroot()

    info = {
        "file": als_path,
        "file_size_bytes": os.path.getsize(als_path),
        "ableton_version": root.get("Creator", "Unknown"),
        "schema_version": root.get("SchemaChangeCount", "Unknown"),
    }

    # Count tracks
    live_set = root.find("LiveSet")
    if live_set is not None:
        tracks_node = live_set.find("Tracks")
        if tracks_node is not None:
            audio_tracks = tracks_node.findall("AudioTrack")
            midi_tracks = tracks_node.findall("MidiTrack")
            return_tracks = tracks_node.findall("ReturnTrack")
            group_tracks = tracks_node.findall("GroupTrack")

            info["audio_tracks"] = len(audio_tracks)
            info["midi_tracks"] = len(midi_tracks)
            info["return_tracks"] = len(return_tracks)
            info["group_tracks"] = len(group_tracks)
            info["total_tracks"] = (
                len(audio_tracks) + len(midi_tracks)
                + len(return_tracks) + len(group_tracks)
            )

            # Extract track names
            track_names = []
            for track in list(tracks_node):
                name_elem = track.find(".//EffectiveName")
                if name_elem is not None:
                    track_names.append(name_elem.get("Value", "Unnamed"))
                else:
                    name_elem = track.find(".//UserName")
                    if name_elem is not None:
                        track_names.append(name_elem.get("Value", "Unnamed"))
            info["track_names"] = track_names

        # Tempo
        tempo = live_set.find(".//Tempo/Manual")
        if tempo is not None:
            info["tempo"] = float(tempo.get("Value", 0))

        # Time signature
        time_sig_num = live_set.find(".//TimeSignatures//RemoteableTimeSignature/Numerator")
        time_sig_den = live_set.find(".//TimeSignatures//RemoteableTimeSignature/Denominator")
        if time_sig_num is not None and time_sig_den is not None:
            info["time_signature"] = (
                f"{time_sig_num.get('Value', '4')}/{time_sig_den.get('Value', '4')}"
            )

    return info


def print_als_info(als_path: str) -> None:
    """Print formatted info about an .als file."""
    info = als_info(als_path)

    print(f"\n{'=' * 60}")
    print(f"  Ableton Live Set: {Path(info['file']).name}")
    print(f"{'=' * 60}")
    print(f"  File size:       {info['file_size_bytes']:,} bytes")
    print(f"  Ableton version: {info.get('ableton_version', 'N/A')}")
    print(f"  Tempo:           {info.get('tempo', 'N/A')} BPM")
    print(f"  Time signature:  {info.get('time_signature', 'N/A')}")
    print(f"  Total tracks:    {info.get('total_tracks', 'N/A')}")
    print(f"    Audio:         {info.get('audio_tracks', 0)}")
    print(f"    MIDI:          {info.get('midi_tracks', 0)}")
    print(f"    Return:        {info.get('return_tracks', 0)}")
    print(f"    Group:         {info.get('group_tracks', 0)}")

    if "track_names" in info and info["track_names"]:
        print(f"\n  Track listing:")
        for i, name in enumerate(info["track_names"], 1):
            print(f"    {i:3d}. {name}")

    print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# EQ8 Automation Helpers
# ---------------------------------------------------------------------------

# EQ8 Mode integer -> label mapping (for reference/documentation)
EQ8_MODES = {
    0: "LowCut48",
    1: "LowCut12",
    2: "LowShelf",
    3: "Bell",
    4: "Notch",
    5: "HighShelf",
    6: "HighCut12",
    7: "HighCut48",
}

# The "pre-song" default event time used by Ableton for initial automation state
_DEFAULT_EVENT_TIME = -63072000


def find_track_by_name(tree: ET.ElementTree, track_name: str) -> ET.Element:
    """Find a track element by its EffectiveName or UserName.

    Searches all track types (AudioTrack, MidiTrack, ReturnTrack, GroupTrack)
    under LiveSet/Tracks and returns the first match.

    Args:
        tree: Parsed ElementTree of the .als file.
        track_name: The track name to search for (case-sensitive).

    Returns:
        The matching track Element.

    Raises:
        ValueError: If no track with the given name is found.
    """
    root = tree.getroot()
    live_set = root.find("LiveSet")
    if live_set is None:
        raise ValueError("No LiveSet element found in the ALS file.")

    tracks_node = live_set.find("Tracks")
    if tracks_node is None:
        raise ValueError("No Tracks element found under LiveSet.")

    for track in tracks_node:
        effective = track.find(".//EffectiveName")
        if effective is not None and effective.get("Value") == track_name:
            return track
        user = track.find(".//UserName")
        if user is not None and user.get("Value") == track_name:
            return track

    raise ValueError(f"No track named '{track_name}' found in the project.")


_EQ8_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "ableton" / "projects" / "Pluggin Mapping.als"
)
_EQ8_TEMPLATE_CACHE: ET.Element | None = None


def _load_eq8_template() -> ET.Element:
    """Load and cache a real EQ8 element from Pluggin Mapping.als.

    A hand-rolled EQ8 is missing too many Ableton-private fields
    (ParameterB, MidiControllerRange, ModulationTarget, SpectrumAnalyzer,
    AdaptiveQ, GlobalGain, Scale, ...) for Live to recognise it as a
    functional device — the resulting XML parses but its AutomationTargets
    receive no audio, so envelopes end up connected to nothing.

    The canonical fix is to clone a real EQ8 from a reference project.

    Raises:
        RuntimeError: If the reference .als is missing or contains no EQ8.
    """
    global _EQ8_TEMPLATE_CACHE
    if _EQ8_TEMPLATE_CACHE is not None:
        return _EQ8_TEMPLATE_CACHE

    if not _EQ8_TEMPLATE_PATH.exists():
        raise RuntimeError(
            f"EQ8 template file not found: {_EQ8_TEMPLATE_PATH}. "
            "This .als ships an EQ8 instance that find_or_create_eq8() "
            "clones when a track has no EQ8 yet."
        )
    with gzip.open(_EQ8_TEMPLATE_PATH, "rt", encoding="utf-8") as f:
        ref_tree = ET.parse(f)
    eq8 = ref_tree.getroot().find(".//Eq8")
    if eq8 is None:
        raise RuntimeError(
            f"No <Eq8> element found in reference file {_EQ8_TEMPLATE_PATH}."
        )
    _EQ8_TEMPLATE_CACHE = eq8
    return eq8


def _clone_eq8_with_unique_ids(
    tree: ET.ElementTree, user_name: str | None = None
) -> ET.Element:
    """Deep-copy the EQ8 template and renumber non-zero Id attributes.

    The cloned subtree is returned detached; the caller appends it to the
    target Devices container. Only ``Id`` attributes with values > 0 are
    rewritten to values above ``get_next_id(tree)`` to avoid collisions.
    ``Id="0"`` is a special placeholder value in Ableton's format (used on
    ``BranchSourceContext`` and ``AbletonDefaultPresetRef`` inside
    ``SourceContext``/``LastPresetRef``) and must be preserved as 0 so Live
    recognises the device as a default browser instance rather than an
    unknown reference.

    Args:
        tree: Destination ElementTree (used only for ID allocation).
        user_name: Optional value to set on the EQ8 ``<UserName>`` element so
            the cloned device is identifiable in Ableton's UI.
    """
    eq8 = copy.deepcopy(_load_eq8_template())
    next_id = get_next_id(tree)
    for elem in eq8.iter():
        raw = elem.get("Id")
        if raw is not None and raw != "0":
            elem.set("Id", str(next_id))
            next_id += 1

    if user_name is not None:
        un = eq8.find("UserName")
        if un is not None:
            un.set("Value", user_name)

    return eq8


def find_or_create_eq8(
    track_element: ET.Element,
    tree: ET.ElementTree,
    user_name: str | None = None,
) -> ET.Element:
    """Find the first EQ8 device in a track's DeviceChain, or create one.

    Searches for an existing ``Eq8`` element inside the track's
    ``DeviceChain/DeviceChain/Devices`` subtree.  If none is found, a new
    EQ8 is cloned from the reference device in Pluggin Mapping.als and
    appended with fresh, collision-free ``Id`` attributes.

    Args:
        track_element: The track Element (e.g. from :func:`find_track_by_name`).
        tree: The full ElementTree, required for ID allocation when creating.
        user_name: Optional UserName to set on a NEWLY created EQ8 (used to
            tag devices generated by the smoke test).

    Returns:
        The ``Eq8`` Element (existing or newly created).

    Raises:
        ValueError: If the track has no DeviceChain/Devices container.
        RuntimeError: If the reference EQ8 template cannot be loaded.
    """
    existing = track_element.find(".//Eq8")
    if existing is not None:
        return existing

    devices = track_element.find(".//DeviceChain/DeviceChain/Devices")
    if devices is None:
        devices = track_element.find(".//DeviceChain/Devices")
    if devices is None:
        raise ValueError(
            "Cannot locate a Devices container in the track's DeviceChain. "
            "The track structure is unexpected."
        )

    eq8 = _clone_eq8_with_unique_ids(tree, user_name=user_name)
    devices.append(eq8)
    return eq8


def get_eq8_band(eq8_element: ET.Element, band_index: int) -> ET.Element:
    """Return the ``ParameterA`` element for a specific EQ8 band.

    Args:
        eq8_element: The ``Eq8`` Element.
        band_index: Band number (0–7).

    Returns:
        The ``ParameterA`` child of ``Bands.<band_index>``.

    Raises:
        ValueError: If band_index is out of range or the element is missing.
    """
    if not (0 <= band_index <= 7):
        raise ValueError(f"band_index must be 0–7, got {band_index}.")

    band = eq8_element.find(f"Bands.{band_index}")
    if band is None:
        raise ValueError(f"Bands.{band_index} not found in EQ8 element.")

    param_a = band.find("ParameterA")
    if param_a is None:
        raise ValueError(f"ParameterA not found inside Bands.{band_index}.")

    return param_a


def configure_eq8_band(
    band_param: ET.Element,
    mode: int | None = None,
    freq: float | None = None,
    gain: float | None = None,
    q: float | None = None,
) -> None:
    """Set the Manual (static) values for an EQ8 band's parameters.

    Only the parameters whose arguments are not ``None`` are updated.
    ``mode`` must be an integer 0–7 (see :data:`EQ8_MODES`).

    Args:
        band_param: The ``ParameterA`` Element returned by :func:`get_eq8_band`.
        mode: Filter type integer (0–7), or ``None`` to leave unchanged.
        freq: Centre/corner frequency in Hz, or ``None`` to leave unchanged.
        gain: Gain in dB, or ``None`` to leave unchanged.
        q: Q / bandwidth factor, or ``None`` to leave unchanged.

    Raises:
        ValueError: If ``mode`` is not in the range 0–7.
    """
    if mode is not None:
        if not (0 <= mode <= 7):
            raise ValueError(f"mode must be 0–7, got {mode}.")
        manual = band_param.find("Mode/Manual")
        if manual is not None:
            manual.set("Value", str(mode))

    if freq is not None:
        manual = band_param.find("Freq/Manual")
        if manual is not None:
            manual.set("Value", str(float(freq)))

    if gain is not None:
        manual = band_param.find("Gain/Manual")
        if manual is not None:
            manual.set("Value", str(float(gain)))

    if q is not None:
        manual = band_param.find("Q/Manual")
        if manual is not None:
            manual.set("Value", str(float(q)))


def get_automation_target_id(param_element: ET.Element, param_name: str) -> str:
    """Return the ``AutomationTarget`` Id for a named sub-parameter.

    Given a ``ParameterA`` element (from :func:`get_eq8_band`) and a
    parameter name such as ``"Freq"``, ``"Gain"``, or ``"Q"``, this function
    walks into ``<param_name>/AutomationTarget`` and returns the ``Id``
    attribute value.

    Args:
        param_element: The ``ParameterA`` (or any parent) Element.
        param_name: Sub-element name, e.g. ``"Freq"``, ``"Gain"``, ``"Q"``,
            ``"Mode"``, or ``"IsOn"``.

    Returns:
        The ``Id`` attribute value as a string.

    Raises:
        ValueError: If the expected XML path does not exist.
    """
    target = param_element.find(f"{param_name}/AutomationTarget")
    if target is None:
        raise ValueError(
            f"AutomationTarget not found at '{param_name}/AutomationTarget' "
            f"inside the given element."
        )
    id_val = target.get("Id")
    if id_val is None:
        raise ValueError(
            f"AutomationTarget element at '{param_name}/AutomationTarget' "
            f"has no 'Id' attribute."
        )
    return id_val


def write_automation_envelope(
    track_element: ET.Element,
    pointee_id: str,
    events: list[tuple[float, float]],
    next_id_counter: list[int],
    event_type: str = "FloatEvent",
) -> ET.Element:
    """Write a list of breakpoint events as an AutomationEnvelope on a track.

    Creates a new ``AutomationEnvelope`` element inside the track's
    ``AutomationEnvelopes/Envelopes`` container.  A "default" pre-song event
    at ``Time=-63072000`` is prepended automatically (using the first event's
    value), so callers should **not** include it in ``events``.

    Args:
        track_element: The track Element that owns the automation.
        pointee_id: The ``AutomationTarget Id`` this envelope targets (from
            :func:`get_automation_target_id`).
        events: List of ``(time_beats, value)`` tuples for the automation
            breakpoints.  Times are in Ableton beat units (floats).
        next_id_counter: A single-element list ``[int]`` used as a mutable
            counter so callers can share the ID namespace across multiple
            calls.  The counter is incremented in-place for every new event.
        event_type: ``"FloatEvent"`` for continuous parameters (Freq/Gain/Q),
            ``"BoolEvent"`` for boolean parameters (IsOn).  Confirmed by
            calibration v1.8 (2026-04-18): IsOn MUST use BoolEvent — Live
            silently ignores FloatEvent for boolean targets.

    Returns:
        The newly created ``AutomationEnvelope`` Element.

    Raises:
        ValueError: If ``AutomationEnvelopes`` is not found on the track or
            ``event_type`` is unsupported.
    """
    if event_type not in ("FloatEvent", "BoolEvent"):
        raise ValueError(
            f"event_type must be 'FloatEvent' or 'BoolEvent', got {event_type!r}."
        )

    def _format_value(v: float) -> str:
        if event_type == "BoolEvent":
            return "true" if float(v) >= 0.5 else "false"
        return str(float(v))

    # Locate or create AutomationEnvelopes/Envelopes
    auto_envelopes_node = track_element.find("AutomationEnvelopes")
    if auto_envelopes_node is None:
        auto_envelopes_node = ET.SubElement(track_element, "AutomationEnvelopes")

    envelopes_node = auto_envelopes_node.find("Envelopes")
    if envelopes_node is None:
        envelopes_node = ET.SubElement(auto_envelopes_node, "Envelopes")

    # Ableton requires every AutomationEnvelope in an Envelopes container to
    # carry a unique Id attribute; the numbering is local to the track.
    existing_env_ids = [
        int(e.get("Id", "-1"))
        for e in envelopes_node.findall("AutomationEnvelope")
        if e.get("Id") is not None
    ]
    envelope_local_id = max(existing_env_ids) + 1 if existing_env_ids else 0

    # Build the envelope element
    envelope = ET.SubElement(envelopes_node, "AutomationEnvelope")
    envelope.set("Id", str(envelope_local_id))

    env_target = ET.SubElement(envelope, "EnvelopeTarget")
    ET.SubElement(env_target, "PointeeId").set("Value", str(pointee_id))

    automation = ET.SubElement(envelope, "Automation")
    events_node = ET.SubElement(automation, "Events")

    # Pre-song default event (Ableton convention)
    initial_value = events[0][1] if events else 0.0
    default_event = ET.SubElement(events_node, event_type)
    default_event.set("Id", str(next_id_counter[0]))
    default_event.set("Time", str(_DEFAULT_EVENT_TIME))
    default_event.set("Value", _format_value(initial_value))
    next_id_counter[0] += 1

    # Actual breakpoints
    for time_beats, value in events:
        ev = ET.SubElement(events_node, event_type)
        ev.set("Id", str(next_id_counter[0]))
        ev.set("Time", str(float(time_beats)))
        ev.set("Value", _format_value(value))
        next_id_counter[0] += 1

    # Required Ableton metadata — without this block Live silently ignores
    # the envelope (observed: Gain envelopes near 0 dB would stay flat).
    view_state = ET.SubElement(automation, "AutomationTransformViewState")
    is_pending = ET.SubElement(view_state, "IsTransformPending")
    is_pending.set("Value", "false")
    ET.SubElement(view_state, "TimeAndValueTransforms")

    return envelope


_DEFAULT_TEMPO_BPM = 120.0


def _normalize_tempo_events(tempo) -> List[Tuple[float, float]]:
    """Return a sorted (time_s, bpm) list starting at t=0.

    Accepts a single BPM (float/int), a list of ``(time_s, bpm)`` events,
    or ``None`` / an empty sequence (falls back to a constant 120 BPM map).
    """
    if tempo is None:
        return [(0.0, _DEFAULT_TEMPO_BPM)]
    if isinstance(tempo, (int, float)):
        if tempo <= 0:
            return [(0.0, _DEFAULT_TEMPO_BPM)]
        return [(0.0, float(tempo))]

    cleaned: List[Tuple[float, float]] = []
    for t, bpm in tempo:
        if bpm is None or bpm <= 0:
            continue
        cleaned.append((float(max(t, 0.0)), float(bpm)))

    if not cleaned:
        return [(0.0, _DEFAULT_TEMPO_BPM)]

    cleaned.sort(key=lambda e: e[0])
    if cleaned[0][0] > 0.0:
        cleaned.insert(0, (0.0, cleaned[0][1]))
    return cleaned


def seconds_to_beats(seconds: float, tempo: TempoLike) -> float:
    """Convert a time in seconds to Ableton beat units (quarter notes).

    ``tempo`` can be a single BPM (backwards-compatible single-tempo form)
    or a piecewise-constant tempo map ``[(time_s, bpm), ...]``.

    Technical debt: the ``float BPM`` form is kept only to preserve the
    existing eq8_automation.py call sites (see ``eq8_automation.py:349``).
    Once those callers are migrated to the tempo-events signature, the
    float branch of :func:`_normalize_tempo_events` should be removed
    and the ``TempoLike`` alias narrowed to ``TempoEvents``.
    """
    if seconds <= 0.0:
        return 0.0
    events = _normalize_tempo_events(tempo)
    beats = 0.0
    for i, (t_start, bpm) in enumerate(events):
        t_end = events[i + 1][0] if i + 1 < len(events) else float("inf")
        if seconds <= t_start:
            break
        segment_end = min(seconds, t_end)
        beats += (segment_end - t_start) * (bpm / 60.0)
        if seconds <= t_end:
            break
    return beats


def beats_to_seconds(beats: float, tempo: TempoLike) -> float:
    """Inverse of :func:`seconds_to_beats` over a piecewise-constant tempo map."""
    if beats <= 0.0:
        return 0.0
    events = _normalize_tempo_events(tempo)
    accumulated = 0.0
    t_cursor = 0.0
    for i, (t_start, bpm) in enumerate(events):
        t_end = events[i + 1][0] if i + 1 < len(events) else float("inf")
        segment_seconds = t_end - t_start if t_end != float("inf") else None
        segment_beats = (
            segment_seconds * (bpm / 60.0) if segment_seconds is not None else float("inf")
        )
        if accumulated + segment_beats >= beats:
            remaining = beats - accumulated
            return t_start + remaining * (60.0 / bpm)
        accumulated += segment_beats
        t_cursor = t_end
    return t_cursor


# ---------------------------------------------------------------------------
# Locator I/O (Feature 3)
# ---------------------------------------------------------------------------

_LOCATOR_BLOCK_RE = re.compile(
    r"<Locators>\s*<Locators>(?P<body>.*?)</Locators>\s*</Locators>",
    re.DOTALL,
)
_LOCATOR_ENTRY_RE = re.compile(
    r"<Locator\s+Id=\"(?P<id>\d+)\">(?P<inner>.*?)</Locator>",
    re.DOTALL,
)


def _read_als_xml(als_path: Path) -> str:
    with gzip.open(als_path, "rb") as f:
        return f.read().decode("utf-8")


def _extract_value(tag: str, xml_fragment: str) -> Optional[str]:
    m = re.search(rf"<{tag}\s+Value=\"(?P<v>[^\"]*)\"\s*/>", xml_fragment)
    return m.group("v") if m else None


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
    )


def read_locators(als_path) -> List[dict]:
    """Read every Locator from ``LiveSet/Locators/Locators`` in the .als.

    Returns a list of dicts ``{id, time_beats, name, annotation}`` in document
    order. Returns ``[]`` when no Locators block or no entries are found.
    """
    xml = _read_als_xml(Path(als_path))
    block = _LOCATOR_BLOCK_RE.search(xml)
    if not block:
        return []
    locators: List[dict] = []
    for m in _LOCATOR_ENTRY_RE.finditer(block.group("body")):
        inner = m.group("inner")
        locators.append(
            {
                "id": int(m.group("id")),
                "time_beats": float(_extract_value("Time", inner) or 0.0),
                "name": _extract_value("Name", inner) or "",
                "annotation": _extract_value("Annotation", inner) or "",
            }
        )
    return locators


def _build_locator_block(new_locators: Iterable[dict], existing_max_id: int) -> str:
    """Build the XML fragment for newly appended Locator entries."""
    lines: List[str] = []
    next_id = existing_max_id + 1
    for loc in new_locators:
        time_beats = float(loc.get("time_beats", 0.0))
        name = _xml_escape(str(loc.get("name", "")))
        annotation = _xml_escape(str(loc.get("annotation", "")))
        lines.append(
            f"\t\t\t<Locator Id=\"{next_id}\">\n"
            f"\t\t\t\t<Time Value=\"{time_beats}\" />\n"
            f"\t\t\t\t<Name Value=\"{name}\" />\n"
            f"\t\t\t\t<Annotation Value=\"{annotation}\" />\n"
            f"\t\t\t\t<IsSongStart Value=\"false\" />\n"
            f"\t\t\t\t<LockEnvelope Value=\"0\" />\n"
            f"\t\t\t</Locator>"
        )
        next_id += 1
    return "\n".join(lines)


def _inject_locators(xml: str, new_locators: List[dict]) -> Tuple[str, int]:
    """Append Locators to the existing block, preserving every existing entry.

    Returns ``(new_xml, count_appended)``. When ``new_locators`` is empty the
    XML is returned unchanged and the count is 0.
    """
    if not new_locators:
        return xml, 0

    existing_block = _LOCATOR_BLOCK_RE.search(xml)
    existing_max_id = -1
    if existing_block:
        for m in _LOCATOR_ENTRY_RE.finditer(existing_block.group("body")):
            existing_max_id = max(existing_max_id, int(m.group("id")))

    new_entries = _build_locator_block(new_locators, existing_max_id)

    if existing_block:
        body = existing_block.group("body").rstrip()
        merged_body = (
            f"{body}\n{new_entries}\n\t\t"
            if body.strip()
            else f"\n{new_entries}\n\t\t"
        )
        new_block = (
            f"<Locators>\n\t\t<Locators>{merged_body}</Locators>\n\t</Locators>"
        )
        return (
            xml[: existing_block.start()]
            + new_block
            + xml[existing_block.end() :],
            len(new_locators),
        )

    # No Locators block at all: inject a fresh one right before </LiveSet>.
    fresh = (
        f"<Locators>\n\t\t<Locators>\n{new_entries}\n\t\t</Locators>\n\t</Locators>"
    )
    idx = xml.rfind("</LiveSet>")
    if idx == -1:
        return xml + fresh, len(new_locators)
    return xml[:idx] + "\t" + fresh + "\n" + xml[idx:], len(new_locators)


def write_locators(
    als_path,
    new_locators: List[dict],
    output_path=None,
) -> int:
    """Append Locators to the .als, preserving all existing Locators.

    Args:
        als_path: Path to the source .als file (never overwritten).
        new_locators: List of ``{time_beats, name, annotation?}`` dicts.
            Ids are auto-assigned using ``max(existing_ids) + 1``. An empty
            list is a no-op: the file is left untouched and 0 is returned.
        output_path: Destination for the modified .als. Defaults to
            ``<als_path stem>_with_sections.als`` alongside the source.

    Returns:
        Number of Locators appended.
    """
    als_path = Path(als_path)
    if not new_locators:
        return 0

    xml = _read_als_xml(als_path)
    new_xml, count = _inject_locators(xml, list(new_locators))

    if output_path is None:
        output_path = als_path.with_name(als_path.stem + "_with_sections.als")
    output_path = Path(output_path)

    # gzip.compress() standard — NEVER double-gzip (cf. CLAUDE.md piège 1).
    output_path.write_bytes(gzip.compress(new_xml.encode("utf-8")))
    return count


def backup_als(als_path: str) -> Path:
    """Create a timestamped backup of an .als file before modification.

    The backup is written alongside the original with the suffix
    ``.v24.bak``.  If a file with that name already exists it is
    overwritten.

    Args:
        als_path: Path to the .als file to back up.

    Returns:
        Path to the backup file.

    Raises:
        FileNotFoundError: If ``als_path`` does not exist.
    """
    als_path = Path(als_path)
    if not als_path.exists():
        raise FileNotFoundError(f"File not found: {als_path}")

    backup_path = als_path.with_suffix(".als.v24.bak")
    import shutil
    shutil.copy2(als_path, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


def get_next_id(tree: ET.ElementTree) -> int:
    """Scan every element in the tree for ``Id`` attributes and return max + 1.

    This ensures newly created elements do not collide with existing IDs.
    Project files use IDs up to roughly 335 000; this function is safe for
    any project size.

    Args:
        tree: The full parsed ElementTree of the .als file.

    Returns:
        An integer one greater than the highest ``Id`` attribute found,
        or ``335001`` as a conservative floor if no IDs are present.
    """
    max_id = 335000  # conservative floor per ALS spec notes
    for elem in tree.getroot().iter():
        raw = elem.get("Id")
        if raw is not None:
            try:
                val = int(raw)
                if val > max_id:
                    max_id = val
            except ValueError:
                pass
    return max_id + 1


def thin_breakpoints(
    events: list[tuple[float, float]], max_count: int = 500
) -> list[tuple[float, float]]:
    """Downsample a breakpoint list to at most ``max_count`` points.

    Uses uniform stride sub-sampling while always preserving the first and
    last points so the automation envelope's start and end values are never
    lost.  If ``len(events) <= max_count`` the original list is returned
    unchanged.

    Args:
        events: List of ``(time_beats, value)`` tuples.
        max_count: Maximum number of breakpoints to keep (default 500).

    Returns:
        A new list of at most ``max_count`` ``(time_beats, value)`` tuples,
        or the original list if no thinning is needed.
    """
    if len(events) <= max_count:
        return events

    # Always keep first and last; distribute the remaining slots evenly
    if max_count < 2:
        return [events[0]]

    indices = set()
    indices.add(0)
    indices.add(len(events) - 1)

    # Uniform stride across the interior
    step = (len(events) - 1) / (max_count - 1)
    for i in range(1, max_count - 1):
        indices.add(round(i * step))

    return [events[i] for i in sorted(indices)]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()
    filepath = sys.argv[2]

    if command == "decompress":
        output = sys.argv[3] if len(sys.argv) > 3 else None
        decompress_als(filepath, output)

    elif command == "compress":
        output = sys.argv[3] if len(sys.argv) > 3 else None
        compress_to_als(filepath, output)

    elif command == "info":
        print_als_info(filepath)

    else:
        print(f"Unknown command: {command}")
        print("Available commands: decompress, compress, info")
        sys.exit(1)


if __name__ == "__main__":
    main()
