import pytest
from PySide6.QtCore import QSettings
from models.settings import Favorite, FavoritesSettings, Settings
from util.const import IN_GITHUB_RUNNER


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


class TestFavorite:
    """Test suite for the Favorite dataclass."""

    def test_favorite_creation(self):
        """Test creating a Favorite instance."""
        favorite = Favorite(path="/home/user/music")
        assert favorite.path == "/home/user/music"

    def test_favorite_equality(self):
        """Test that Favorites with same path are equal."""
        fav1 = Favorite(path="/home/user/music")
        fav2 = Favorite(path="/home/user/music")
        assert fav1 == fav2


class TestFavoritesSettings:
    """Test suite for the FavoritesSettings dataclass."""

    def test_default_favorites_settings(self):
        """Test default FavoritesSettings initialization."""
        settings = FavoritesSettings()
        assert settings.locations == []
        assert isinstance(settings.locations, list)

    def test_favorites_settings_with_locations(self):
        """Test FavoritesSettings with locations."""
        locations = [
            Favorite(path="/home/user/music"),
            Favorite(path="/home/user/documents")
        ]
        settings = FavoritesSettings(locations=locations)
        assert len(settings.locations) == 2
        assert settings.locations[0].path == "/home/user/music"
        assert settings.locations[1].path == "/home/user/documents"


class TestSettings:
    """Test suite for the Settings dataclass."""

    def test_settings_has_favorites(self):
        """Test that Settings includes favorites field."""
        settings = Settings()
        assert hasattr(settings, 'favorites')
        assert isinstance(settings.favorites, FavoritesSettings)
        assert settings.favorites.locations == []


class TestFavoritesPersistence:
    """Test suite for favorites persistence in QSettings."""

    def test_save_and_load_empty_favorites(self, test_settings):
        """Test saving and loading empty favorites list."""
        # Save empty favorites
        test_settings.beginGroup("Favorites")
        test_settings.beginWriteArray("locations", 0)
        test_settings.endArray()
        test_settings.endGroup()

        # Load favorites
        test_settings.beginGroup("Favorites")
        favorites = []
        num_favorites = test_settings.beginReadArray("locations")
        assert num_favorites == 0
        for i in range(num_favorites):
            test_settings.setArrayIndex(i)
            path = test_settings.value("path", type=str)
            if path:
                favorites.append(Favorite(path=path))
        test_settings.endArray()
        test_settings.endGroup()

        assert len(favorites) == 0

    def test_save_and_load_single_favorite(self, test_settings):
        """Test saving and loading a single favorite."""
        # Save a favorite
        test_favorites = [Favorite(path="/home/user/music")]

        test_settings.beginGroup("Favorites")
        test_settings.beginWriteArray("locations", len(test_favorites))
        for i, favorite in enumerate(test_favorites):
            test_settings.setArrayIndex(i)
            test_settings.setValue("path", favorite.path)
        test_settings.endArray()
        test_settings.endGroup()

        # Load favorites
        test_settings.beginGroup("Favorites")
        loaded_favorites = []
        num_favorites = test_settings.beginReadArray("locations")
        for i in range(num_favorites):
            test_settings.setArrayIndex(i)
            path = test_settings.value("path", type=str)
            if path:
                loaded_favorites.append(Favorite(path=path))
        test_settings.endArray()
        test_settings.endGroup()

        assert len(loaded_favorites) == 1
        assert loaded_favorites[0].path == "/home/user/music"

    def test_save_and_load_multiple_favorites(self, test_settings):
        """Test saving and loading multiple favorites."""
        # Save multiple favorites
        test_favorites = [
            Favorite(path="/home/user/music"),
            Favorite(path="/home/user/documents"),
            Favorite(path="/home/user/pictures")
        ]

        test_settings.beginGroup("Favorites")
        test_settings.beginWriteArray("locations", len(test_favorites))
        for i, favorite in enumerate(test_favorites):
            test_settings.setArrayIndex(i)
            test_settings.setValue("path", favorite.path)
        test_settings.endArray()
        test_settings.endGroup()

        # Load favorites
        test_settings.beginGroup("Favorites")
        loaded_favorites = []
        num_favorites = test_settings.beginReadArray("locations")
        for i in range(num_favorites):
            test_settings.setArrayIndex(i)
            path = test_settings.value("path", type=str)
            if path:
                loaded_favorites.append(Favorite(path=path))
        test_settings.endArray()
        test_settings.endGroup()

        assert len(loaded_favorites) == 3
        assert loaded_favorites[0].path == "/home/user/music"
        assert loaded_favorites[1].path == "/home/user/documents"
        assert loaded_favorites[2].path == "/home/user/pictures"

    def test_overwrite_favorites(self, test_settings):
        """Test that saving new favorites overwrites old ones."""
        # Save initial favorites
        initial_favorites = [
            Favorite(path="/home/user/music"),
            Favorite(path="/home/user/documents")
        ]

        test_settings.beginGroup("Favorites")
        test_settings.beginWriteArray("locations", len(initial_favorites))
        for i, favorite in enumerate(initial_favorites):
            test_settings.setArrayIndex(i)
            test_settings.setValue("path", favorite.path)
        test_settings.endArray()
        test_settings.endGroup()

        # Save new favorites (overwriting)
        new_favorites = [
            Favorite(path="/home/user/pictures")
        ]

        test_settings.beginGroup("Favorites")
        test_settings.beginWriteArray("locations", len(new_favorites))
        for i, favorite in enumerate(new_favorites):
            test_settings.setArrayIndex(i)
            test_settings.setValue("path", favorite.path)
        test_settings.endArray()
        test_settings.endGroup()

        # Load favorites and verify only new ones exist
        test_settings.beginGroup("Favorites")
        loaded_favorites = []
        num_favorites = test_settings.beginReadArray("locations")
        for i in range(num_favorites):
            test_settings.setArrayIndex(i)
            path = test_settings.value("path", type=str)
            if path:
                loaded_favorites.append(Favorite(path=path))
        test_settings.endArray()
        test_settings.endGroup()

        assert len(loaded_favorites) == 1
        assert loaded_favorites[0].path == "/home/user/pictures"
