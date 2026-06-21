#!/usr/bin/env python3
"""
RIFF file structure inspector.

Parses RIFF (WAV, AVI, etc.) files and displays chunk structure
with offsets, sizes, and content previews.
"""

import argparse
import glob
import json
import os
import shutil
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Iterator


@dataclass
class Chunk:
    """Represents a RIFF chunk."""
    id: str
    offset: int  # Offset of chunk data (after header)
    size: int
    header_offset: int  # Offset of chunk ID
    data: bytes | None = None
    children: list["Chunk"] = field(default_factory=list)
    list_type: str | None = None  # For LIST/RIFF chunks


def get_terminal_width() -> int:
    """Get terminal width, defaulting to 120 if unavailable."""
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 120


def is_printable_ascii(data: bytes) -> bool:
    """Check if bytes are mostly printable ASCII."""
    if not data:
        return False
    printable_count = sum(1 for b in data if 32 <= b < 127 or b in (9, 10, 13))
    return printable_count / len(data) > 0.8


def format_preview(data: bytes, max_width: int) -> str:
    """Format a preview of chunk data as string or hex."""
    if not data:
        return "(empty)"

    if is_printable_ascii(data):
        # String preview - strip nulls and control chars
        text = data.decode('latin-1')
        text = text.rstrip('\x00')
        text = ''.join(c if 32 <= ord(c) < 127 else '.' for c in text)
        if len(text) > max_width:
            return f'"{text[:max_width-4]}..."'
        return f'"{text}"'
    else:
        # Hex preview
        hex_str = data[:max_width // 3].hex(' ')
        if len(data) > max_width // 3:
            hex_str += " ..."
        return hex_str


def read_chunk_header(f: BinaryIO) -> tuple[str, int] | None:
    """Read a chunk header, returning (id, size) or None at EOF."""
    chunk_id = f.read(4)
    if len(chunk_id) < 4:
        return None

    size_data = f.read(4)
    if len(size_data) < 4:
        return None

    chunk_id_str = chunk_id.decode('latin-1')
    size = struct.unpack('<I', size_data)[0]
    return chunk_id_str, size


def parse_list_chunk(f: BinaryIO, offset: int, size: int) -> Chunk:
    """Parse a LIST chunk and its sub-chunks."""
    header_offset = offset - 8

    # Read list type (first 4 bytes of data)
    list_type = f.read(4).decode('latin-1')

    chunk = Chunk(
        id="LIST",
        offset=offset,
        size=size,
        header_offset=header_offset,
        list_type=list_type,
    )

    # Parse sub-chunks
    bytes_remaining = size - 4  # Subtract list type
    while bytes_remaining > 8:  # Minimum chunk header size
        sub_header = read_chunk_header(f)
        if sub_header is None:
            break

        sub_id, sub_size = sub_header
        sub_offset = f.tell()

        # Read sub-chunk data
        sub_data = f.read(sub_size) if sub_size <= 65536 else None
        if sub_data is None:
            f.seek(sub_size, os.SEEK_CUR)

        # Handle padding
        if sub_size % 2:
            f.read(1)
            bytes_remaining -= 1

        sub_chunk = Chunk(
            id=sub_id,
            offset=sub_offset,
            size=sub_size,
            header_offset=sub_offset - 8,
            data=sub_data,
        )
        chunk.children.append(sub_chunk)

        bytes_remaining -= 8 + sub_size

    return chunk


def parse_riff_file(filepath: Path) -> tuple[str, int, list[Chunk]] | None:
    """
    Parse a RIFF file and return (form_type, file_size, chunks).
    Returns None if not a valid RIFF file.
    """
    chunks = []

    with open(filepath, 'rb') as f:
        # Read RIFF header
        header = read_chunk_header(f)
        if header is None:
            return None

        riff_id, riff_size = header
        if riff_id != "RIFF":
            return None

        # Read form type
        form_type = f.read(4).decode('latin-1')

        # Parse chunks
        while True:
            chunk_header_offset = f.tell()
            header = read_chunk_header(f)
            if header is None:
                break

            chunk_id, chunk_size = header
            chunk_offset = f.tell()

            if chunk_id == "LIST":
                chunk = parse_list_chunk(f, chunk_offset, chunk_size)
                chunks.append(chunk)
            else:
                # Read data for small chunks, skip large ones
                if chunk_size <= 65536:
                    data = f.read(chunk_size)
                else:
                    data = None
                    f.seek(chunk_size, os.SEEK_CUR)

                chunks.append(Chunk(
                    id=chunk_id,
                    offset=chunk_offset,
                    size=chunk_size,
                    header_offset=chunk_header_offset,
                    data=data,
                ))

            # Handle padding
            if chunk_size % 2:
                f.read(1)

    return form_type, riff_size, chunks


def format_size(size: int) -> str:
    """Format size with human-readable suffix."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"


def print_chunks_text(chunks: list[Chunk], indent: int = 0, term_width: int = 120):
    """Print chunks in human-readable text format."""
    prefix = "  " * indent

    # Calculate preview width (leave room for other columns)
    # Format: "  CHUNK  @0x00000000  12345 B  preview..."
    fixed_width = len(prefix) + 4 + 2 + 12 + 2 + 12 + 2
    preview_width = max(20, term_width - fixed_width)

    for chunk in chunks:
        size_str = format_size(chunk.size).rjust(10)

        if chunk.list_type:
            print(f"{prefix}{chunk.id} ({chunk.list_type})  @0x{chunk.header_offset:08X}  {size_str}")
            print_chunks_text(chunk.children, indent + 1, term_width)
        else:
            preview = ""
            if chunk.data is not None:
                preview = "  " + format_preview(chunk.data, preview_width)
            elif chunk.size > 65536:
                preview = f"  (skipped, >{format_size(65536)})"

            print(f"{prefix}{chunk.id}  @0x{chunk.header_offset:08X}  {size_str}{preview}")


def chunk_to_dict(chunk: Chunk) -> dict:
    """Convert a Chunk to a JSON-serializable dict."""
    result = {
        "id": chunk.id,
        "header_offset": chunk.header_offset,
        "data_offset": chunk.offset,
        "size": chunk.size,
    }

    if chunk.list_type:
        result["list_type"] = chunk.list_type
        result["children"] = [chunk_to_dict(c) for c in chunk.children]
    elif chunk.data is not None:
        if is_printable_ascii(chunk.data):
            result["preview"] = chunk.data.rstrip(b'\x00').decode('latin-1')
        else:
            result["preview_hex"] = chunk.data[:64].hex()

    return result


def print_chunks_json(form_type: str, file_size: int, chunks: list[Chunk], filepath: str):
    """Print chunks in JSON format."""
    result = {
        "file": filepath,
        "format": "RIFF",
        "form_type": form_type,
        "file_size": file_size,
        "chunks": [chunk_to_dict(c) for c in chunks],
    }
    print(json.dumps(result, indent=2))


def resolve_paths(patterns: list[str]) -> list[Path]:
    """Resolve file patterns to actual paths, handling globs."""
    paths = []
    for pattern in patterns:
        if any(c in pattern for c in '*?[]'):
            paths.extend(Path(p) for p in glob.glob(pattern))
        else:
            paths.append(Path(pattern))
    return paths


def main():
    parser = argparse.ArgumentParser(
        description="Inspect RIFF file structure (WAV, AVI, etc.)"
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="File path(s) or glob pattern(s) to inspect"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    args = parser.parse_args()

    paths = resolve_paths(args.files)
    if not paths:
        print("No files matched.", file=sys.stderr)
        sys.exit(1)

    term_width = get_terminal_width()

    results = []
    for filepath in paths:
        if not filepath.exists():
            print(f"Error: {filepath} not found", file=sys.stderr)
            continue

        result = parse_riff_file(filepath)
        if result is None:
            print(f"Error: {filepath} is not a valid RIFF file", file=sys.stderr)
            continue

        form_type, file_size, chunks = result

        if args.json:
            results.append({
                "file": str(filepath),
                "format": "RIFF",
                "form_type": form_type,
                "file_size": file_size,
                "chunks": [chunk_to_dict(c) for c in chunks],
            })
        else:
            print(f"\n{filepath}")
            print(f"RIFF/{form_type}  {format_size(file_size)}")
            print("-" * min(60, term_width))
            print_chunks_text(chunks, term_width=term_width)

    if args.json:
        if len(results) == 1:
            print(json.dumps(results[0], indent=2))
        else:
            print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()