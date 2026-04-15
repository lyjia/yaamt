"""
Base classes for audio file analyzers.

This module defines the abstract base class and result class that all audio
file analyzers must implement or use.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class AnalyzerResult:
    """
    Encapsulates the result of an analysis operation.

    Attributes:
        success: Whether the analysis completed successfully
        data: Dictionary of generic_tag_name: value pairs for successful analysis
        error: Error message if analysis failed or was skipped
        skipped: Whether the analysis was skipped (e.g., data already exists)
    """

    def __init__(self,
                 success: bool,
                 data: Optional[Dict[str, Any]] = None,
                 error: Optional[str] = None,
                 skipped: bool = False):
        """
        Initialize an AnalyzerResult.

        Args:
            success: True if analysis completed successfully, False otherwise
            data: Dictionary of generic tag names to values (e.g., {'bpm': 120})
            error: Error message describing what went wrong
            skipped: True if analysis was skipped (e.g., value already exists)
        """
        self.success = success
        self.data = data or {}
        self.error = error
        self.skipped = skipped

    def __repr__(self) -> str:
        if self.success and not self.skipped:
            return f"AnalyzerResult(success=True, data={self.data})"
        elif self.skipped:
            return f"AnalyzerResult(skipped=True, reason={self.error})"
        else:
            return f"AnalyzerResult(success=False, error={self.error})"


class AnalyzerBase(ABC):
    """
    Abstract base class for all audio file analyzers.

    Analyzers extract specific metadata from audio files (e.g., BPM, key, gain).
    Each analyzer operates on a single MediaFile instance and returns results
    as an AnalyzerResult object.

    Class Attributes:
        name: Human-readable name of the analyzer
        description: Brief description of what the analyzer does
        category: Category/module name (e.g., 'bpm', 'key', 'gain')
        version: Version string for the analyzer
    """

    # Class attributes for metadata (must be overridden by subclasses)
    name: str = "Unnamed Analyzer"
    description: str = ""
    category: str = "uncategorized"
    version: str = "1.0.0"
    debug_only: bool = False  # If True, this analyzer is only available in debug builds

    def __init__(self, media_file, options: Optional[Dict[str, Any]] = None):
        """
        Initialize analyzer with a MediaFile.

        Args:
            media_file: The MediaFile instance to analyze
            options: Dictionary of analyzer options. Common options:
                    - 'overwrite_existing' (bool): If True, overwrite existing metadata.
                      If False, skip analysis if value already exists. Default: False
                    Analyzers may define their own additional options.
        """
        self.media_file = media_file
        self.options = options or {}
        self._cancelled = False

    @abstractmethod
    def analyze(self) -> AnalyzerResult:
        """
        Perform analysis on the audio file.

        This method should be implemented by all analyzer subclasses to perform
        their specific analysis. Implementations should:
        - Get audio stream via self.media_file.get_audio_stream() if needed
        - Check for cancellation periodically via self.is_cancelled
        - Return AnalyzerResult with appropriate success/error/skip status
        - Handle exceptions internally and return AnalyzerResult with error
        - Close audio stream in a finally block if opened

        Returns:
            AnalyzerResult containing success status and data/error
        """
        pass

    def cancel(self) -> None:
        """Request cancellation of the analysis."""
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled

    # Common guard-clause helpers used at the top of analyze() methods.
    # Keeping them here eliminates the identical prologue that was previously
    # duplicated across every AnalyzerBase subclass.

    _CANCELLATION_MESSAGE = "Analysis cancelled by user"
    _SKIP_IF_EXISTS_OPTION = 'skip_if_tag_exists'

    def _check_cancellation(self) -> Optional['AnalyzerResult']:
        """
        Return a failure AnalyzerResult if cancellation was requested, else None.

        Intended for use as a one-line guard at the top of ``analyze()``:

            cancelled = self._check_cancellation()
            if cancelled is not None:
                return cancelled
        """
        if self.is_cancelled:
            return AnalyzerResult(success=False, error=self._CANCELLATION_MESSAGE)
        return None

    def _check_skip_if_exists(
        self,
        tag_name: str,
        skipped_message: Optional[str] = None,
    ) -> Optional['AnalyzerResult']:
        """
        Return a 'skipped' AnalyzerResult if the given tag already has a value
        and the ``skip_if_tag_exists`` option is set, else None.

        Args:
            tag_name: Generic tag name to check via ``MediaFile.get_tag_simple``.
            skipped_message: Optional explanatory string for the skip result.
                             Defaults to ``f"{tag_name} already set"``.
        """
        if not self.options.get(self._SKIP_IF_EXISTS_OPTION, False):
            return None
        if not self.media_file.get_tag_simple(tag_name):
            return None
        return AnalyzerResult(
            success=True,
            skipped=True,
            error=skipped_message or f"{tag_name} already set",
        )

    def _check_skip_if(
        self,
        value_exists: bool,
        skipped_message: str,
    ) -> Optional['AnalyzerResult']:
        """
        Variant of :meth:`_check_skip_if_exists` for analyzers that need a
        custom existence check (e.g. scanning the comments field rather than
        a single tag).

        Args:
            value_exists: Result of the analyzer-specific existence check.
            skipped_message: Explanatory string for the skip result.
        """
        if value_exists and self.options.get(self._SKIP_IF_EXISTS_OPTION, False):
            return AnalyzerResult(success=True, skipped=True, error=skipped_message)
        return None

    @classmethod
    def get_options_metadata(cls) -> List:
        """
        Return metadata about this analyzer's configurable options.

        Subclasses should override this to define their specific options.
        This metadata is used by both CLI (argparse) and GUI (widget generation).

        The default implementation returns an empty list (no options).

        Returns:
            List of AnalyzerOption instances defining this analyzer's options
        """
        return []

    @classmethod
    def get_settings_widget(cls) -> Optional[Any]:
        """
        Return a QWidget for analyzer-specific settings.

        Default implementation: auto-generate widget from get_options_metadata().

        Subclasses can:
        1. Use default auto-generation (don't override this method)
        2. Override for custom layout but use build_widget_from_option() helper
           to maintain consistency with option metadata

        Returns:
            QWidget instance or None if no options
        """
        from util.analyzer_options import build_widget_from_option

        options = cls.get_options_metadata()
        if not options:
            return None

        # Import here to avoid circular dependency
        from PySide6.QtWidgets import QWidget, QVBoxLayout

        widget = QWidget()
        layout = QVBoxLayout()

        # Build widget for each option
        settings_group = f"analyzers/{cls.__name__}"
        for option in options:
            option_widget = build_widget_from_option(option, settings_group)
            layout.addWidget(option_widget)

        widget.setLayout(layout)
        return widget

    @classmethod
    def get_thread_count(cls, options: Optional[Dict[str, Any]] = None) -> int:
        """
        Return the number of threads this analyzer requires.

        This method allows analyzers to report how many threads they need
        for processing. The dispatcher uses this to determine how many
        analyzer instances can run concurrently within the thread pool limit.

        Args:
            options: Analyzer options that might affect thread count

        Returns:
            Number of threads required (default: 1)
        """
        return 1

    @classmethod
    def validate_file(cls, media_file) -> tuple[bool, Optional[str]]:
        """
        Check if this analyzer can process the given file.

        Args:
            media_file: The MediaFile instance to validate

        Returns:
            Tuple of (is_valid, reason). reason is None if valid,
            or a string explaining why the file is incompatible.
        """
        return (True, None)

    @classmethod
    def get_required_resources(cls) -> List:
        """
        Return list of resources required by this analyzer.

        Subclasses that require external resources (models, databases, etc.)
        should override this method to return their requirements as a list
        of ResourceMetadata instances.

        These resources are registered with the global ResourceManager
        when providers are discovered via discover_providers().

        Returns:
            List of ResourceMetadata instances describing required resources.
            Default implementation returns an empty list (no resources required).
        """
        return []
