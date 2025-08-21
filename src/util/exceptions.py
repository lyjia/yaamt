class SomethingsReallyFuckedUpException(Exception):
    """Exception raised when something goes catastrophically wrong in the system."""
    pass

class InvalidFileError(Exception):
    """Exception raised when a file is invalid."""
    pass