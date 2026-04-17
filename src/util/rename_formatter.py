"""
Format-string parser for the "Rename files based on metadata" feature.

Format language:

    %TOKEN%                 Substitute the tag value associated with TOKEN.
                            Matching is case-insensitive against the uppercase
                            form of each KEY_ constant's string value (see
                            util.const.ALL_FORMATTING_TAGS).
    %TOKEN:000%             Pad a numeric value to N digits with leading zeros,
                            where N is the number of '0' characters after the
                            colon. Non-numeric values render unchanged, and
                            values exceeding the pad width render unchanged.
    [section]?              Optional section. Renders only if every TAG token
                            directly inside the section resolves to a non-empty
                            value. Sections may be nested; a nested section
                            that collapses to empty does NOT poison its parent
                            section's presence check.

The sanitizer strips path separators, Windows-reserved chars, and control
characters so the rendered filename is safe to apply with os.rename.
"""

from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from models.media_file import MediaFile

from util.const import (
    ALL_FORMATTING_TAGS,
    ALL_TAGS,
    EXTRA_RENAME_TAGS,
    RENAME_SECTION_STREAM_INFO,
    RENAME_SECTION_TAGS,
    STREAM_INFO_LABELS,
)
from util.logging import log


# Characters that are invalid in filenames on at least one supported OS. We
# strip them unconditionally to keep output portable.
FILENAME_RESERVED_CHARS = r'/\:*?"<>|'
FILENAME_REPLACEMENT_CHAR = "_"

# AST node kinds for the parsed format string.
_NODE_LITERAL = "literal"
_NODE_TAG = "tag"
_NODE_OPTIONAL = "optional"


def _token_name_for_key(key: str) -> str:
    """Uppercase-normalized token name used in format strings for a KEY_ constant."""
    return key.upper()


def list_tokens_by_section() -> dict[str, list[tuple[str, str]]]:
    """
    Return tokens grouped by display section.

    Each entry is (token_text, description). Used by the token-reference dialog.
    """
    out: dict[str, list[tuple[str, str]]] = {}
    for section, keys in ALL_FORMATTING_TAGS.items():
        rows: list[tuple[str, str]] = []
        for key in keys:
            if section == RENAME_SECTION_TAGS:
                label = ALL_TAGS.get(key) or EXTRA_RENAME_TAGS.get(key, key)
            elif section == RENAME_SECTION_STREAM_INFO:
                label = STREAM_INFO_LABELS.get(key, key)
            else:
                label = key
            rows.append((f"%{_token_name_for_key(key)}%", label))
        out[section] = rows
    return out


def _all_known_tokens() -> set[str]:
    """Set of upper-cased token names recognized by the formatter."""
    tokens: set[str] = set()
    for keys in ALL_FORMATTING_TAGS.values():
        for key in keys:
            tokens.add(_token_name_for_key(key))
    return tokens


def _coerce_value(value: Any) -> str:
    """Convert a tag or stream-info value to a string suitable for a filename."""
    if value is None:
        return ""
    if isinstance(value, bool):
        # Bool is a subclass of int in Python; handle before numerics.
        return "1" if value else "0"
    if isinstance(value, float):
        # Drop trailing zeros and decimal point when whole. Round length values.
        if value.is_integer():
            return str(int(value))
        return f"{value:g}"
    if isinstance(value, (int,)):
        return str(value)
    return str(value)


def build_token_map(media_file: "MediaFile") -> dict[str, str]:
    """
    Build an uppercase-keyed token map for a MediaFile.

    Every token listed in ALL_FORMATTING_TAGS is populated (empty string if
    absent on the file) so that optional-section collapse logic works uniformly.
    """
    out: dict[str, str] = {}
    for key in ALL_FORMATTING_TAGS.get(RENAME_SECTION_TAGS, []):
        value = media_file.get_tag_simple(key)
        out[_token_name_for_key(key)] = _coerce_value(value)
    for key in ALL_FORMATTING_TAGS.get(RENAME_SECTION_STREAM_INFO, []):
        value = media_file.get_stream_info_value(key)
        out[_token_name_for_key(key)] = _coerce_value(value)
    return out


def build_token_map_from_dict(raw: dict[str, Any]) -> dict[str, str]:
    """Variant of build_token_map that reads a plain dict (used by sample data)."""
    out: dict[str, str] = {}
    for keys in ALL_FORMATTING_TAGS.values():
        for key in keys:
            out[_token_name_for_key(key)] = _coerce_value(raw.get(key))
    return out


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

# Matches %TOKEN% or %TOKEN:0000%. Token chars: A-Z, 0-9, underscore.
_TAG_RE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)(?::(0+))?%")


class FormatParseError(ValueError):
    """Raised when the format string is malformed."""


def _parse(format_string: str) -> list[dict[str, Any]]:
    """Parse the format string into a flat list of AST nodes."""
    nodes, pos = _parse_section(format_string, 0, top_level=True)
    if pos != len(format_string):
        raise FormatParseError(
            f"Unexpected trailing content at position {pos}: {format_string[pos:]!r}"
        )
    return nodes


def _parse_section(
    s: str, pos: int, top_level: bool
) -> tuple[list[dict[str, Any]], int]:
    """Parse until we hit a ']?' terminator (if not top-level) or end-of-string."""
    nodes: list[dict[str, Any]] = []
    buf: list[str] = []

    def flush_literal() -> None:
        if buf:
            nodes.append({"kind": _NODE_LITERAL, "text": "".join(buf)})
            buf.clear()

    while pos < len(s):
        ch = s[pos]

        if ch == "[":
            # Start a nested optional section.
            flush_literal()
            inner, new_pos = _parse_section(s, pos + 1, top_level=False)
            nodes.append({"kind": _NODE_OPTIONAL, "children": inner})
            pos = new_pos
            continue

        if ch == "]":
            # Must be followed by '?' to terminate an optional section.
            if not top_level and pos + 1 < len(s) and s[pos + 1] == "?":
                flush_literal()
                return nodes, pos + 2
            # Literal ']' (no terminator).
            buf.append(ch)
            pos += 1
            continue

        if ch == "%":
            m = _TAG_RE.match(s, pos)
            if m:
                flush_literal()
                token = m.group(1).upper()
                pad_width = len(m.group(2)) if m.group(2) else 0
                nodes.append(
                    {"kind": _NODE_TAG, "token": token, "pad": pad_width}
                )
                pos = m.end()
                continue
            # Literal '%' not part of a token.
            buf.append(ch)
            pos += 1
            continue

        buf.append(ch)
        pos += 1

    if not top_level:
        raise FormatParseError("Unterminated '[' - missing ']?'")

    flush_literal()
    return nodes, pos


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_tag(node: dict[str, Any], token_map: dict[str, str]) -> str:
    """Render a single TAG node, applying numeric padding if requested."""
    value = token_map.get(node["token"], "")
    pad = node["pad"]
    if pad and value:
        stripped = value.strip()
        if stripped and stripped.lstrip("-").isdigit():
            n = int(stripped)
            formatted = f"{abs(n):0{pad}d}"
            if n < 0:
                formatted = f"-{formatted}"
            return formatted
    return value


def _render_nodes(
    nodes: list[dict[str, Any]], token_map: dict[str, str]
) -> tuple[str, bool]:
    """
    Render a list of nodes.

    Returns (text, all_direct_tags_non_empty). Optional children contribute
    their rendered text when non-empty but are NOT considered for the parent's
    direct-tag presence check.
    """
    parts: list[str] = []
    all_direct_present = True
    has_direct_tag = False

    for node in nodes:
        kind = node["kind"]
        if kind == _NODE_LITERAL:
            parts.append(node["text"])
        elif kind == _NODE_TAG:
            has_direct_tag = True
            rendered = _render_tag(node, token_map)
            if not rendered:
                all_direct_present = False
            parts.append(rendered)
        elif kind == _NODE_OPTIONAL:
            child_text, child_ok = _render_nodes(node["children"], token_map)
            if child_ok:
                parts.append(child_text)
            # Collapsed nested sections don't affect parent presence.

    # A section with no direct tags at all is considered "present" (e.g. a
    # literal-only optional section renders unconditionally - odd but harmless).
    if not has_direct_tag:
        all_direct_present = True

    return "".join(parts), all_direct_present


def format_filename(format_string: str, token_map: dict[str, str]) -> str:
    """
    Render a format string against a token map.

    Raises FormatParseError if the format string is malformed.
    """
    nodes = _parse(format_string)
    text, _ = _render_nodes(nodes, token_map)
    return text


# ---------------------------------------------------------------------------
# Filename sanitization
# ---------------------------------------------------------------------------


def sanitize_filename(name: str) -> str:
    """
    Strip path separators, reserved chars, and control chars from a filename.

    Also collapses runs of whitespace and trims leading/trailing whitespace,
    dots, and underscores. Returns '' if nothing usable remains - callers
    should treat empty output as an error.
    """
    # Replace reserved/separator chars with the replacement char. Control
    # whitespace (tab/newline) gets normalized to a space so the subsequent
    # \s+ collapse merges it with surrounding whitespace instead of leaving
    # behind stranded underscores.
    cleaned_chars: list[str] = []
    for ch in name:
        if ch in FILENAME_RESERVED_CHARS:
            cleaned_chars.append(FILENAME_REPLACEMENT_CHAR)
        elif ord(ch) < 0x20:
            cleaned_chars.append(" " if ch.isspace() else FILENAME_REPLACEMENT_CHAR)
        else:
            cleaned_chars.append(ch)
    cleaned = "".join(cleaned_chars)

    # Collapse runs of whitespace.
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Strip leading/trailing dots to avoid creating hidden files or Windows
    # trailing-dot issues, and trailing replacement chars.
    cleaned = cleaned.strip(". ")
    cleaned = cleaned.strip(FILENAME_REPLACEMENT_CHAR + " ")

    # Guard against names that are solely '.' or ''.
    if cleaned in ("", ".", ".."):
        return ""
    return cleaned


def validate_format_string(format_string: str) -> tuple[bool, str]:
    """
    Quick validation helper for UI use.

    Returns (is_valid, error_message).
    """
    try:
        nodes = _parse(format_string)
    except FormatParseError as e:
        return False, str(e)

    # Warn on unknown tokens - not fatal (they just render empty), but surfacing
    # the name helps the user. Walk the AST to collect TAG tokens.
    unknown: list[str] = []
    known = _all_known_tokens()

    def _walk(nodes_: list[dict[str, Any]]) -> None:
        for n in nodes_:
            if n["kind"] == _NODE_TAG and n["token"] not in known:
                unknown.append(n["token"])
            elif n["kind"] == _NODE_OPTIONAL:
                _walk(n["children"])

    _walk(nodes)
    if unknown:
        unique = ", ".join(sorted(set(unknown)))
        log.debug(f"Unknown rename tokens: {unique}")
        return True, f"Unknown tokens will render empty: {unique}"
    return True, ""
