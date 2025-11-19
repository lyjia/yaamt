import pytest
from unittest.mock import Mock, patch, MagicMock
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox
from util.const import IN_GITHUB_RUNNER
from models.settings import Favorite


@pytest.fixture
def test_settings():
    """
    Fixture that provides a clean QSettings instance for testing.
    Uses a test organization and application name to avoid conflicts.
    """
    # Create test settings instance
    settings = QSettings("LyjiaTest", "Audio Metadata Tool Test")

    # Clear any existing data
    settings.clear()

    yield settings

    # Clean up after test
    settings.clear()


@pytest.mark.skipif(IN_GITHUB_RUNNER, reason="Qt widgets crash in GitHub Actions runner")
class TestMainWindowFavorites:
    """Test suite for MainWindow favorites functionality."""

    @pytest.fixture
    def main_window(self, qapp, test_settings):
        """Create a MainWindow instance for testing."""
        # Patch the settings to use test settings
        with patch('windows.main_window.settings', test_settings):
            from windows.main_window import MainWindow
            window = MainWindow()
            yield window
            window.close()

    def test_load_empty_favorites(self, main_window):
        """Test loading an empty favorites list."""
        favorites = main_window._load_favorites()
        assert favorites == []

    def test_save_and_load_favorites(self, main_window):
        """Test saving and loading favorites."""
        # Create test favorites
        test_favorites = [
            Favorite(path="/home/user/music"),
            Favorite(path="/home/user/documents")
        ]

        # Save favorites
        main_window._save_favorites(test_favorites)

        # Load favorites and verify
        loaded_favorites = main_window._load_favorites()
        assert len(loaded_favorites) == 2
        assert loaded_favorites[0].path == "/home/user/music"
        assert loaded_favorites[1].path == "/home/user/documents"

    def test_add_favorite_success(self, main_window):
        """Test adding a favorite successfully."""
        # Set current path
        main_window._current_path = "/home/user/music"

        # Add favorite
        main_window._on_add_favorite()

        # Verify favorite was added
        favorites = main_window._load_favorites()
        assert len(favorites) == 1
        assert favorites[0].path == "/home/user/music"

    def test_add_favorite_duplicate(self, main_window):
        """Test that adding a duplicate favorite shows a message."""
        # Set current path
        main_window._current_path = "/home/user/music"

        # Add favorite first time
        main_window._on_add_favorite()

        # Mock QMessageBox to capture the dialog
        with patch.object(QMessageBox, 'information') as mock_info:
            # Try to add the same favorite again
            main_window._on_add_favorite()

            # Verify information dialog was shown
            mock_info.assert_called_once()
            assert "already in your favorites" in mock_info.call_args[0][2]

        # Verify only one favorite exists
        favorites = main_window._load_favorites()
        assert len(favorites) == 1

    def test_add_favorite_no_directory(self, main_window):
        """Test that adding a favorite with no directory shows a warning."""
        # Clear current path
        main_window._current_path = ""

        # Mock QMessageBox to capture the dialog
        with patch.object(QMessageBox, 'warning') as mock_warning:
            main_window._on_add_favorite()

            # Verify warning dialog was shown
            mock_warning.assert_called_once()
            assert "No directory is currently selected" in mock_warning.call_args[0][2]

        # Verify no favorite was added
        favorites = main_window._load_favorites()
        assert len(favorites) == 0

    def test_add_favorite_max_limit(self, main_window):
        """Test that adding more than 25 favorites shows a warning."""
        # Add 25 favorites
        test_favorites = [Favorite(path=f"/home/user/dir{i}") for i in range(25)]
        main_window._save_favorites(test_favorites)

        # Set current path
        main_window._current_path = "/home/user/new_dir"

        # Mock QMessageBox to capture the dialog
        with patch.object(QMessageBox, 'warning') as mock_warning:
            main_window._on_add_favorite()

            # Verify warning dialog was shown
            mock_warning.assert_called_once()
            assert "maximum number of favorites" in mock_warning.call_args[0][2]

        # Verify no additional favorite was added
        favorites = main_window._load_favorites()
        assert len(favorites) == 25

    def test_remove_favorite_confirmed(self, main_window):
        """Test removing a favorite when user confirms."""
        # Add a favorite
        test_favorites = [
            Favorite(path="/home/user/music"),
            Favorite(path="/home/user/documents")
        ]
        main_window._save_favorites(test_favorites)

        # Mock QMessageBox.question to return Yes
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            main_window._on_remove_favorite("/home/user/music")

        # Verify favorite was removed
        favorites = main_window._load_favorites()
        assert len(favorites) == 1
        assert favorites[0].path == "/home/user/documents"

    def test_remove_favorite_cancelled(self, main_window):
        """Test that cancelling favorite removal keeps the favorite."""
        # Add favorites
        test_favorites = [
            Favorite(path="/home/user/music"),
            Favorite(path="/home/user/documents")
        ]
        main_window._save_favorites(test_favorites)

        # Mock QMessageBox.question to return No
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
            main_window._on_remove_favorite("/home/user/music")

        # Verify favorite was not removed
        favorites = main_window._load_favorites()
        assert len(favorites) == 2

    def test_create_favorites_menu_empty(self, main_window):
        """Test creating favorites menu with no favorites."""
        menu = main_window._create_favorites_menu()

        # Menu should have "Add Favorite..." action
        actions = menu.actions()
        assert len(actions) == 1
        assert actions[0].text() == "Add Favorite"

    def test_create_favorites_menu_with_favorites(self, main_window):
        """Test creating favorites menu with favorites."""
        # Add favorites
        test_favorites = [
            Favorite(path="/home/user/music"),
            Favorite(path="/home/user/documents")
        ]
        main_window._save_favorites(test_favorites)

        menu = main_window._create_favorites_menu()
        actions = menu.actions()

        # Should have: 2 favorite actions + separator + "Add Favorite..." + "Remove Favorite" submenu
        assert len(actions) >= 4

        # Check that favorites are sorted alphabetically
        assert "/home/user/documents" in actions[0].text()
        assert "/home/user/music" in actions[1].text()

    def test_favorites_menu_navigation(self, main_window):
        """Test that clicking a favorite navigates to that path."""
        # Add a favorite
        test_favorites = [Favorite(path="/home/user/music")]
        main_window._save_favorites(test_favorites)

        # Mock set_path to verify it's called
        with patch.object(main_window, 'set_path') as mock_set_path:
            menu = main_window._create_favorites_menu()
            actions = menu.actions()

            # Trigger the first action (the favorite)
            actions[0].trigger()

            # Verify set_path was called with the favorite path
            mock_set_path.assert_called_once_with("/home/user/music")

    def test_refresh_favorites_menu(self, main_window):
        """Test that refreshing the menu updates its contents."""
        # Create initial menu
        menu = main_window._create_favorites_menu()
        initial_actions = len(menu.actions())

        # Add a favorite
        test_favorites = [Favorite(path="/home/user/music")]
        main_window._save_favorites(test_favorites)

        # Refresh the menu
        main_window._refresh_favorites_menu(menu)

        # Verify menu was updated
        updated_actions = len(menu.actions())
        assert updated_actions > initial_actions
