"""Base class for preference panes."""
from abc import ABCMeta, abstractmethod
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QIcon
from PySide6.QtCore import QObject, Signal


class ABCQWidgetMeta(type(QWidget), ABCMeta):
    """Metaclass that combines Qt's metaclass with ABC's metaclass."""
    pass


class PreferencePaneBase(QWidget, metaclass=ABCQWidgetMeta):
    """
    Abstract base class for preference panes.

    All preference panes must inherit from this class and implement
    the required abstract methods to participate in the preferences system.

    Continuous validity:
        Panes that expose user input which can be in an "in-progress"
        state (e.g. an unverified API key) should override
        :meth:`is_ready_to_save` and emit :attr:`validity_changed` whenever
        their answer changes. The PreferencesWindow listens to all panes'
        signals and disables the Save button whenever any pane is not
        ready. Panes that have no continuous-validity concern can leave
        the defaults alone — the base implementation always reports True.
    """

    # Emitted whenever the pane's "ready to save" state changes. Panes
    # that don't care simply never emit; the default validity is True.
    validity_changed = Signal(bool)

    def is_ready_to_save(self) -> bool:
        """Return True when the pane's current input is acceptable to save.

        Distinct from :meth:`validate`, which is invoked once when the
        user clicks Save. ``is_ready_to_save`` is polled every time the
        Save button needs to update its enabled state and must therefore
        be cheap (no network calls).
        """
        return True

    @abstractmethod
    def get_name(self) -> str:
        """
        Return the display name for this preference category.

        Returns:
            Display name (e.g., "General", "Metadata")
        """
        pass

    @abstractmethod
    def get_icon(self) -> QIcon:
        """
        Return the icon for the sidebar.

        Returns:
            QIcon for this preference category
        """
        pass

    @abstractmethod
    def load_from_settings(self) -> None:
        """
        Read from QSettings and populate all widgets with current values.

        This method is called when the preferences window opens.
        """
        pass

    @abstractmethod
    def save_to_settings(self) -> None:
        """
        Write widget values to QSettings.

        This method is called when the user clicks Save and validation passes.
        """
        pass

    @abstractmethod
    def validate(self) -> tuple[bool, str]:
        """
        Validate all settings in this pane.

        Returns:
            Tuple of (is_valid, error_message).
            If valid, error_message should be empty string.
            If invalid, error_message should describe the problem.
        """
        pass

    @abstractmethod
    def load_defaults(self) -> None:
        """
        Set all widgets to their default values.

        This method is called when the user clicks "Reset to Default".
        It should NOT write to QSettings - only update widget values.
        """
        pass
