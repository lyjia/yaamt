from PySide6.QtCore import QObject, Signal

class EditManager(QObject):
    """
    A singleton class to manage metadata edits across the application.
    """
    staged_changes_exist = Signal(bool)
    autosave_changed = Signal(bool)

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EditManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._staged_changes = {}
        self._autosave = False
        self._initialized = True

    @property
    def autosave(self) -> bool:
        return self._autosave

    @autosave.setter
    def autosave(self, value: bool):
        if self._autosave != value:
            self._autosave = value
            self.autosave_changed.emit(self._autosave)

    def stage_change(self, file_paths: list[str], tag: str, value: any):
        """
        Stage a change for one or more files.
        """
        for file_path in file_paths:
            if file_path not in self._staged_changes:
                self._staged_changes[file_path] = {}
            self._staged_changes[file_path][tag] = value
        self.staged_changes_exist.emit(self.has_staged_changes())

    def commit_changes(self):
        """
        Commit all staged changes to the files.
        """
        # This will be implemented in a later task.
        # For now, we just clear the staged changes.
        self.reset_changes()

    def reset_changes(self):
        """
        Reset all staged changes.
        """
        self._staged_changes.clear()
        self.staged_changes_exist.emit(False)

    def has_staged_changes(self) -> bool:
        """
        Check if there are any staged changes.
        """
        return bool(self._staged_changes)
