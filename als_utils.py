#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ALS Utilities - Ableton Live Set file manipulation tools.

Ableton .als files are gzip-compressed XML. This module provides tools to:
- Decompress .als -> .xml (for reading/editing/version control)
- Recompress .xml -> .als (for loading back into Ableton)
- Inspect and modify ALS content programmatically

Usage (CLI):
    python als_utils.py decompress project.als              # -> project.als.xml
    python als_utils.py compress project.als.xml            # -> project.als
    python als_utils.py info project.als                    # show project summary
"""

import gzip
import sys
import os
import xml.etree.ElementTree as ET
from pathlib import Path


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


def save_als_from_tree(tree: ET.ElementTree, output_path: str) -> str:
    """Save an ElementTree back to a gzip-compressed .als file.

    Args:
        tree: The ElementTree to save.
        output_path: Path for the output .als file.

    Returns:
        Path to the saved file.
    """
    output_path = Path(output_path)
    xml_bytes = ET.tostring(tree.getroot(), encoding="unicode", xml_declaration=True)

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
