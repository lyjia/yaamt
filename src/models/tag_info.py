from dataclasses import dataclass


@dataclass
class TagInfo:
    """
    A data class that encapsulates all the necessary information about a tag.
    """
    name: str
    is_writable: bool
    is_generic: bool