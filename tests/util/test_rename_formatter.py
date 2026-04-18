"""Tests for util.rename_formatter."""
from util.rename_formatter import (
    FormatParseError,
    build_token_map_from_dict,
    format_filename,
    list_tokens_by_section,
    sanitize_filename,
    validate_format_string,
)
from util.const import (
    KEY_ALBUM,
    KEY_ALBUM_ARTIST,
    KEY_ARTIST,
    KEY_REMIXER,
    KEY_TITLE,
    KEY_TRACK_NUMBER,
    RENAME_SECTION_STREAM_INFO,
    RENAME_SECTION_TAGS,
    SAMPLE_RENAME_METADATA,
)


def _simple_tokens(**overrides):
    base = {"ARTIST": "", "TITLE": "", "ALBUM": "", "ALBUMARTIST": "",
            "TRACKNUMBER": "", "REMIXER": "", "YEAR": ""}
    base.update(overrides)
    return base


def test_plain_token_substitution():
    tokens = _simple_tokens(ARTIST="Raiden", TITLE="Infection")
    assert format_filename("%ARTIST% - %TITLE%", tokens) == "Raiden - Infection"


def test_token_matching_is_case_insensitive():
    tokens = _simple_tokens(ARTIST="Raiden", TITLE="Infection")
    assert format_filename("%artist% - %Title%", tokens) == "Raiden - Infection"


def test_unknown_token_renders_empty():
    tokens = _simple_tokens(ARTIST="Raiden")
    assert format_filename("%ARTIST% - %NOPE%", tokens) == "Raiden - "


def test_padding_numeric_value():
    tokens = _simple_tokens(TRACKNUMBER="7")
    assert format_filename("%TRACKNUMBER:00%", tokens) == "07"


def test_padding_value_exceeds_width_renders_unchanged():
    tokens = _simple_tokens(TRACKNUMBER="125")
    assert format_filename("%TRACKNUMBER:00%", tokens) == "125"


def test_padding_non_numeric_renders_unchanged():
    tokens = _simple_tokens(TRACKNUMBER="abc")
    assert format_filename("%TRACKNUMBER:00%", tokens) == "abc"


def test_padding_empty_value_stays_empty():
    tokens = _simple_tokens(TRACKNUMBER="")
    assert format_filename("%TRACKNUMBER:00%", tokens) == ""


def test_padding_negative_number():
    tokens = _simple_tokens(TRACKNUMBER="-3")
    assert format_filename("%TRACKNUMBER:000%", tokens) == "-003"


def test_optional_section_renders_when_present():
    tokens = _simple_tokens(ARTIST="Raiden", TITLE="Infection",
                            REMIXER="E-Sassin")
    out = format_filename("%ARTIST% - %TITLE%[ (%REMIXER% Remix)]?", tokens)
    assert out == "Raiden - Infection (E-Sassin Remix)"


def test_optional_section_collapses_when_any_token_missing():
    tokens = _simple_tokens(ARTIST="Raiden", TITLE="Infection", REMIXER="")
    out = format_filename("%ARTIST% - %TITLE%[ (%REMIXER% Remix)]?", tokens)
    assert out == "Raiden - Infection"


def test_nested_optional_section_collapse_preserves_parent():
    # Exact example from the spec: empty ALBUMARTIST must NOT prevent the
    # outer section from rendering.
    fmt = "[[%ALBUMARTIST% - ]? %ALBUM% - %TRACKNUMBER%]? %ARTIST% - %TITLE%"
    tokens = _simple_tokens(
        ALBUMARTIST="", ALBUM="Guide", TRACKNUMBER="7",
        ARTIST="Raiden", TITLE="Infection",
    )
    out = format_filename(fmt, tokens)
    # Outer present because ALBUM and TRACKNUMBER are both present; inner
    # collapses silently.
    assert out == " Guide - 7 Raiden - Infection"


def test_nested_optional_section_fully_present():
    fmt = "[[%ALBUMARTIST% - ]?%ALBUM% - %TRACKNUMBER%]? %ARTIST% - %TITLE%"
    tokens = _simple_tokens(
        ALBUMARTIST="Dieselboy", ALBUM="Guide", TRACKNUMBER="7",
        ARTIST="Raiden", TITLE="Infection",
    )
    out = format_filename(fmt, tokens)
    assert out == "Dieselboy - Guide - 7 Raiden - Infection"


def test_nested_optional_outer_collapses_when_direct_token_missing():
    fmt = "[[%ALBUMARTIST% - ]?%ALBUM% - %TRACKNUMBER%]? %ARTIST% - %TITLE%"
    tokens = _simple_tokens(
        ALBUMARTIST="Dieselboy", ALBUM="", TRACKNUMBER="7",
        ARTIST="Raiden", TITLE="Infection",
    )
    out = format_filename(fmt, tokens)
    # ALBUM empty -> outer collapses entirely.
    assert out == " Raiden - Infection"


def test_unterminated_optional_raises():
    try:
        format_filename("[%ARTIST% - %TITLE%", _simple_tokens(ARTIST="x", TITLE="y"))
    except FormatParseError:
        return
    raise AssertionError("Expected FormatParseError")


def test_literal_bracket_without_question_mark():
    tokens = _simple_tokens(ARTIST="Raiden")
    # A bare ']' at the top level is a literal.
    assert format_filename("%ARTIST%]", tokens) == "Raiden]"


def test_literal_percent():
    tokens = _simple_tokens(ARTIST="Raiden")
    # A '%' not followed by a valid token is a literal.
    assert format_filename("100%% - %ARTIST%", tokens) == "100%% - Raiden"


def test_sanitize_filename_strips_path_separators():
    assert sanitize_filename("foo/bar") == "foo_bar"
    assert sanitize_filename("foo\\bar") == "foo_bar"


def test_sanitize_filename_strips_reserved_chars():
    assert sanitize_filename('a:b*c?d"e<f>g|h') == "a_b_c_d_e_f_g_h"


def test_sanitize_filename_collapses_whitespace():
    assert sanitize_filename("foo    bar\n\tbaz") == "foo bar baz"


def test_sanitize_filename_trims_dots_and_underscores():
    assert sanitize_filename("...hello...") == "hello"
    assert sanitize_filename("  ___ hello ___  ") == "hello"


def test_sanitize_filename_empty_input():
    assert sanitize_filename("") == ""
    assert sanitize_filename("...") == ""
    assert sanitize_filename("///") == ""


def test_build_token_map_from_dict_uses_uppercase_keys():
    tokens = build_token_map_from_dict(SAMPLE_RENAME_METADATA)
    assert tokens["ARTIST"] == "Raiden"
    assert tokens["TITLE"] == "Infection"
    assert tokens["ALBUMARTIST"] == "Dieselboy"
    assert tokens["REMIXER"] == "E-Sassin"
    assert tokens["TRACKNUMBER"] == "7"
    # Missing tags come back as empty strings.
    assert tokens.get("GROUPING", "x") == ""
    # Stream info is coerced to plain strings.
    assert tokens["BITRATE"] == "320000"


def test_build_token_map_handles_float_lengths():
    tokens = build_token_map_from_dict({"length": 342.5})
    assert tokens["LENGTH"] == "342.5"
    tokens = build_token_map_from_dict({"length": 342.0})
    assert tokens["LENGTH"] == "342"


def test_list_tokens_by_section_has_both_sections():
    sections = list_tokens_by_section()
    assert RENAME_SECTION_TAGS in sections
    assert RENAME_SECTION_STREAM_INFO in sections

    tag_tokens = {token for token, _desc in sections[RENAME_SECTION_TAGS]}
    assert "%ARTIST%" in tag_tokens
    assert "%TITLE%" in tag_tokens
    assert "%TRACKNUMBER%" in tag_tokens

    # Replaygain keys must not be exposed to the formatter.
    stream_tokens = {token for token, _desc in sections[RENAME_SECTION_STREAM_INFO]}
    assert "%BITRATE%" in stream_tokens
    assert not any("REPLAYGAIN" in t for t in stream_tokens)


def test_validate_format_string_reports_parse_errors():
    ok, msg = validate_format_string("[%ARTIST% - %TITLE%")
    assert ok is False
    assert msg


def test_validate_format_string_rejects_unknown_token():
    ok, msg = validate_format_string("%ARTIST% - %NOTATHING%")
    assert ok is False
    assert "NOTATHING" in msg


def test_validate_format_string_rejects_multiple_unknown_tokens():
    ok, msg = validate_format_string("%FOO% - %BAR% - %ARTIST%")
    assert ok is False
    # Both unknown tokens listed (alphabetized, deduped).
    assert "BAR" in msg
    assert "FOO" in msg


def test_validate_format_string_rejects_unknown_token_inside_optional():
    ok, msg = validate_format_string("[%NOTATHING% - ]?%ARTIST%")
    assert ok is False
    assert "NOTATHING" in msg


def test_validate_format_string_accepts_valid():
    ok, msg = validate_format_string("%ARTIST% - %TITLE%")
    assert ok is True
    assert msg == ""


def test_end_to_end_sample_metadata():
    tokens = build_token_map_from_dict(SAMPLE_RENAME_METADATA)
    fmt = "[%TRACKNUMBER:00% - ]?%ARTIST% - %TITLE%[ (%REMIXER% Remix)]?"
    out = format_filename(fmt, tokens)
    assert out == "07 - Raiden - Infection (E-Sassin Remix)"
