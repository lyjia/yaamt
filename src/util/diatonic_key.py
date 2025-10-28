# Key conversion maps
# Standard format uses: root (C, D, E, F, G, A, B), accidental (♭, ♯, or nothing), mode (major, minor)
# Internal representation: (root, accidental, is_minor) where:
#   root: 0=C, 1=C♯/D♭, 2=D, 3=D♯/E♭, 4=E, 5=F, 6=F♯/G♭, 7=G, 8=G♯/A♭, 9=A, 10=A♯/B♭, 11=B
#   accidental: 0=natural, 1=sharp, -1=flat
#   is_minor: True/False
from enum import Enum
from typing import Optional, Tuple

# Camelot wheel mapping: (pitch_class, is_minor) -> Camelot notation
CAMELOT_MAP = {
    # Minor keys (A suffix)
    (0, True): "5A",   # C minor
    (1, True): "12A",  # C♯/D♭ minor
    (2, True): "7A",   # D minor
    (3, True): "2A",   # D♯/E♭ minor
    (4, True): "9A",   # E minor
    (5, True): "4A",   # F minor
    (6, True): "11A",  # F♯/G♭ minor
    (7, True): "6A",   # G minor
    (8, True): "1A",   # G♯/A♭ minor
    (9, True): "8A",   # A minor
    (10, True): "3A",  # A♯/B♭ minor
    (11, True): "10A", # B minor
    # Major keys (B suffix)
    (0, False): "8B",  # C major
    (1, False): "3B",  # C♯/D♭ major
    (2, False): "10B", # D major
    (3, False): "5B",  # D♯/E♭ major
    (4, False): "12B", # E major
    (5, False): "7B",  # F major
    (6, False): "2B",  # F♯/G♭ major
    (7, False): "9B",  # G major
    (8, False): "4B",  # G♯/A♭ major
    (9, False): "11B", # A major
    (10, False): "6B", # A♯/B♭ major
    (11, False): "1B", # B major
}

# Open Key mapping: (pitch_class, is_minor) -> Open Key notation
OPEN_KEY_MAP = {
    # Minor keys (m suffix)
    (0, True): "5m",   # C minor
    (1, True): "12m",  # C♯/D♭ minor
    (2, True): "7m",   # D minor
    (3, True): "2m",   # D♯/E♭ minor
    (4, True): "9m",   # E minor
    (5, True): "4m",   # F minor
    (6, True): "11m",  # F♯/G♭ minor
    (7, True): "6m",   # G minor
    (8, True): "1m",   # G♯/A♭ minor
    (9, True): "8m",   # A minor
    (10, True): "3m",  # A♯/B♭ minor
    (11, True): "10m", # B minor
    # Major keys (d suffix)
    (0, False): "8d",  # C major
    (1, False): "3d",  # C♯/D♭ major
    (2, False): "10d", # D major
    (3, False): "5d",  # D♯/E♭ major
    (4, False): "12d", # E major
    (5, False): "7d",  # F major
    (6, False): "2d",  # F♯/G♭ major
    (7, False): "9d",  # G major
    (8, False): "4d",  # G♯/A♭ major
    (9, False): "11d", # A major
    (10, False): "6d", # A♯/B♭ major
    (11, False): "1d", # B major
}

# Note name to pitch class mapping -- accidental will modify these numbers +1/-1
NOTE_TO_PITCH = {
    'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11
}


class NotationFormat(Enum):
    StandardAbbrev = "standard_abbrev"
    StandardSingle = "standard_single"
    Standard = "standard"
    Camelot = "camelot"
    OpenKey = "open_key"

def parse_key(key_str: str) -> Optional[Tuple[int, bool]]:
    """
    Parse a key string into internal representation.

    Args:
        key_str: Key string in various formats (e.g., "Cmin", "C minor", "Cm", "6A", "1m")

    Returns:
        Tuple of (pitch_class, is_minor) or None if parsing fails
    """
    if not key_str or not isinstance(key_str, str):
        return None

    key_str = key_str.strip()

    # Try Camelot format (e.g., "6A", "8B")
    if len(key_str) >= 2:
        try:
            # Extract number and letter
            num_part = ""
            letter_part = ""
            for char in key_str:
                if char.isdigit():
                    num_part += char
                elif char.isalpha():
                    letter_part += char.upper()

            if num_part and letter_part in ["A", "B"]:
                # Reverse lookup in Camelot map
                for (pitch, is_minor), camelot in CAMELOT_MAP.items():
                    if camelot == f"{num_part}{letter_part}":
                        return (pitch, is_minor)
        except (ValueError, KeyError):
            pass

    # Try Open Key format (e.g., "6m", "8d")
    if len(key_str) >= 2:
        try:
            num_part = ""
            letter_part = ""
            for char in key_str:
                if char.isdigit():
                    num_part += char
                elif char.isalpha():
                    letter_part += char.lower()

            if num_part and letter_part in ["m", "d"]:
                # Reverse lookup in Open Key map
                for (pitch, is_minor), open_key in OPEN_KEY_MAP.items():
                    if open_key == f"{num_part}{letter_part}":
                        return (pitch, is_minor)
        except (ValueError, KeyError):
            pass

    # Try standard notation (e.g., "Cmin", "C minor", "Cm", "C", "Dbmaj", "F#")
    key_upper = key_str.upper()

    # Extract root note
    root_note = None
    accidental = 0  # 0=natural, 1=sharp, -1=flat
    remainder = ""

    if len(key_upper) >= 1:
        first_char = key_upper[0]
        if first_char in NOTE_TO_PITCH:
            root_note = first_char
            remainder = key_upper[1:]

            # Check for accidental, remove from remainder if found
            # Note: 'B' here means flat (♭), not the note B. This works because
            # the root note was already extracted, so any 'B' in the remainder
            # must be a flat symbol. For example: "Bb" -> root='B', remainder='b' (uppercase = 'B')
            if remainder and remainder[0] in ['#', '♯']:
                accidental = 1
                remainder = remainder[1:]
            elif remainder and remainder[0] in ['B', '♭']:
                accidental = -1
                remainder = remainder[1:]

    if root_note is None:
        return None

    # Calculate pitch class
    pitch_class = (NOTE_TO_PITCH[root_note] + accidental) % 12

    # Determine if minor
    remainder = remainder.strip().lower()
    is_minor = False
    if remainder in ['min', 'minor', 'm']:
        is_minor = True
    elif remainder in ['maj', 'major', '']:
        is_minor = False
    else:
        # Unknown suffix, assume major
        is_minor = False

    return pitch_class, is_minor

def format_key(pitch_class: int, is_minor: bool, notation_format: NotationFormat) -> str:
    """
    Format a key according to the selected notation format.

    Args:
        pitch_class: Pitch class (0-11)
        is_minor: Whether the key is minor
        notation_format: NotationFormat enum value (Camelot, OpenKey, Standard, StandardAbbrev, StandardSingle)

    Returns:
        Formatted key string
    """
    if notation_format == NotationFormat.Camelot:
        return CAMELOT_MAP.get((pitch_class, is_minor), "")

    elif notation_format == NotationFormat.OpenKey:
        return OPEN_KEY_MAP.get((pitch_class, is_minor), "")

    else:
        # Standard notation (standard_abbrev or standard_single)
        # Use sharp notation by default (could be made configurable)
        note_names = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
        root = note_names[pitch_class]

        if notation_format == NotationFormat.StandardAbbrev:
            mode = "min" if is_minor else "maj"
            return f"{root}{mode}"
        elif notation_format == NotationFormat.StandardSingle:
            mode = "m" if is_minor else ""
            return f"{root}{mode}"
        else:  #Standard
            mode = "minor" if is_minor else "major"
            return f"{root} {mode}"
