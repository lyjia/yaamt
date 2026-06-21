from dataclasses import dataclass


@dataclass
class TagInfo:
    """
    A data class that encapsulates all the necessary information about a tag.
    """
    internal_tag_name: str
    is_writable: bool
    generic_tag_name: str | None