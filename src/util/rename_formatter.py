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
                            If the actual value is a decimal (e.g. "174.5"),
                            the fractional portion is always preserved, so
                            "174.5" with :000 renders as "174.5" (not "174").
                            Special case: %INITIALKEY:00% pads the leading
                            numeric portion of a Camelot-notation key while
                            preserving the trailing letter (e.g. "7A" -> "07A",
                            "11B" stays "11B"). No other token has a mixed
                            numeric/alphabetic pad behavior.
    %TOKEN:000.0%           Pad the integer portion like :000, and force at
                            least one decimal place. The decimal-pad count is
                            a minimum: if the actual value has more decimal
                            digits, they are preserved verbatim. So "174" with
                            :000.0 renders as "174.0", "90" becomes "090.0",
                            "174.55" with :000.0 stays "174.55".
    <section>               Optional section. Renders only if every TAG token
                            directly inside the section resolves to a non-empty
                            value. Sections may be nested; a nested section
                            that collapses to empty does NOT poison its parent
                            section's presence check. '[' and ']' are always
                            literal characters.

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
    KEY_INITIAL_KEY,
    RENAME_SECTION_STREAM_INFO,
    RENAME_SECTION_TAGS,
    STREAM_INFO_LABELS,
)
from util.logging import log


# Token for KEY_INITIAL_KEY - used by the special Camelot padding rule.
_INITIAL_KEY_TOKEN = KEY_INITIAL_KEY.upper()

# Matches a run of digits at the very start of a string, optionally preceded
# by a minus sign. Used for both the default numeric pad and the mixed
# numeric/alphabetic pad that the Camelot special case relies on.
_LEADING_NUMERIC_RE = re.compile(r"^(-?)(\d+)(.*)$", re.DOTALL)


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

# Matches %TOKEN%, %TOKEN:0000%, or %TOKEN:0000.000%. Token chars: A-Z, 0-9,
# underscore. The optional pad spec is one run of zeros for integer padding,
# then optionally a '.' followed by another run of zeros for minimum-decimal
# padding.
_TAG_RE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)(?::(0+)(?:\.(0+))?)?%")


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
    """Parse until we hit a '>' terminator (if not top-level) or end-of-string."""
    nodes: list[dict[str, Any]] = []
    buf: list[str] = []

    def flush_literal() -> None:
        if buf:
            nodes.append({"kind": _NODE_LITERAL, "text": "".join(buf)})
            buf.clear()

    while pos < len(s):
        ch = s[pos]

        if ch == "<":
            # Start a nested optional section.
            flush_literal()
            inner, new_pos = _parse_section(s, pos + 1, top_level=False)
            nodes.append({"kind": _NODE_OPTIONAL, "children": inner})
            pos = new_pos
            continue

        if ch == ">":
            if not top_level:
                flush_literal()
                return nodes, pos + 1
            # Literal '>' at top level (no matching opener).
            buf.append(ch)
            pos += 1
            continue

        if ch == "%":
            m = _TAG_RE.match(s, pos)
            if m:
                flush_literal()
                token = m.group(1).upper()
                pad_width = len(m.group(2)) if m.group(2) else 0
                decimal_pad = len(m.group(3)) if m.group(3) else 0
                nodes.append(
                    {
                        "kind": _NODE_TAG,
                        "token": token,
                        "pad": pad_width,
                        "decimal_pad": decimal_pad,
                    }
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
        raise FormatParseError("Unterminated '<' - missing '>'")

    flush_literal()
    return nodes, pos


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _split_numeric(value: str) -> tuple[str, str, str] | None:
    """
    Split a fully-numeric value into (sign, int_part, frac_part).

    Returns None if value isn't a plain signed integer or decimal. Accepts
    "123", "-7", "174.5", "-0.25". Rejects leading-dot ".5", trailing-dot
    "5.", or anything with non-numeric tail.
    """
    stripped = value.strip()
    if not stripped:
        return None
    sign = ""
    rest = stripped
    if rest.startswith(("-", "+")):
        sign = "-" if rest[0] == "-" else ""
        rest = rest[1:]
    if "." in rest:
        int_part, _, frac_part = rest.partition(".")
        if not int_part or not frac_part:
            return None
        if not int_part.isdigit() or not frac_part.isdigit():
            return None
    else:
        if not rest.isdigit():
            return None
        int_part = rest
        frac_part = ""
    return sign, int_part, frac_part


def _pad_fully_numeric(value: str, pad: int, decimal_pad: int) -> str:
    """
    Pad an integer-or-decimal value.

    - Leading zeros pad the integer portion to `pad` digits.
    - Decimal portion is preserved verbatim when present.
    - When `decimal_pad` > 0, the output is guaranteed to have at least
      `decimal_pad` fractional digits (padded with trailing zeros). Actual
      decimal digits, if any, are always preserved regardless of
      `decimal_pad`; the spec is a minimum, never a truncation.
    """
    parsed = _split_numeric(value)
    if parsed is None:
        return value
    sign, int_part, frac_part = parsed
    int_n = int(int_part)
    padded_int = f"{int_n:0{pad}d}"
    target_frac_len = max(decimal_pad, len(frac_part))
    if target_frac_len > 0:
        frac_padded = frac_part.ljust(target_frac_len, "0")
        return f"{sign}{padded_int}.{frac_padded}"
    return f"{sign}{padded_int}"


def _pad_leading_numeric(value: str, pad: int) -> str:
    """
    Pad the leading numeric portion of value, preserving any trailing content.

    Used exclusively for Camelot-notation keys (e.g. "7A" -> "07A"). If the
    value has no leading digits the input is returned unchanged. Decimal-pad
    spec is ignored here since Camelot notation isn't a decimal number.
    """
    m = _LEADING_NUMERIC_RE.match(value.strip())
    if m is None:
        return value
    sign, digits, rest = m.groups()
    n = int(digits)
    return f"{sign}{n:0{pad}d}{rest}"


def _render_tag(node: dict[str, Any], token_map: dict[str, str]) -> str:
    """Render a single TAG node, applying numeric padding if requested."""
    value = token_map.get(node["token"], "")
    pad = node["pad"]
    decimal_pad = node.get("decimal_pad", 0)
    if (not pad and not decimal_pad) or not value:
        return value
    if node["token"] == _INITIAL_KEY_TOKEN:
        # Camelot / mixed notation: pad leading digits, keep letter suffix.
        return _pad_leading_numeric(value, pad)
    return _pad_fully_numeric(value, pad, decimal_pad)


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

    # Unknown tokens are treated as a hard validation failure so the dialog
    # can disable OK and the user knows the format won't do what they think.
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
        return False, f"Unknown token(s): {unique}"
    return True, ""
