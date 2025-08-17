import pytest
from unittest.mock import patch, MagicMock

# Import directly from app package without 'src' prefix
from models.media_file import MediaFile
from providers.metadata.metadata_provider import MetadataProvider


def test_import_works():
    """Test that imports work correctly without the 'src' prefix."""
    # If this test runs without ImportError, the import system is working correctly
    assert MediaFile is not None
    assert MetadataProvider is not None


@patch('models.media_file.MutagenProvider')
def test_media_file_initialization(mock_provider_class):
    """Test that MediaFile can be initialized with a file path."""
    # Setup mock
    mock_provider = MagicMock()
    mock_provider_class.return_value = mock_provider
    
    # Create MediaFile instance
    file_path = "test_file.mp3"
    media_file = MediaFile(file_path)
    
    # Verify MutagenProvider was initialized with the correct file path
    mock_provider_class.assert_called_once_with(file_path)


@patch('models.media_file.MutagenProvider')
def test_media_file_properties(mock_provider_class):
    """Test that MediaFile properties work correctly."""
    # Setup mock with test values
    mock_provider = MagicMock()
    mock_provider.title = "Test Title"
    mock_provider.artist = "Test Artist"
    mock_provider.album = "Test Album"
    mock_provider_class.return_value = mock_provider
    
    # Create MediaFile instance
    media_file = MediaFile("test_file.mp3")
    
    # Verify properties are correctly retrieved from the provider
    assert media_file.title == "Test Title"
    assert media_file.artist == "Test Artist"
    assert media_file.album == "Test Album"