class SomethingsReallyFuckedUpException(Exception):
    """Exception raised when something goes catastrophically wrong in the system."""
    pass

class InvalidFileError(Exception):
    """Exception raised when a file is invalid."""
    pass

class UnwritableTagsError(Exception):
    """Raised by MediaFile.save() when some staged tags have no provider that can
    write them. All other tags in the same save were written; ``tags`` names the
    ones that were not, so callers can keep exactly those staged."""

    def __init__(self, tags: list[str]):
        self.tags = list(tags)
        super().__init__(f"No metadata provider can write these tags for this file: {', '.join(self.tags)}")
