"""
Tests for the resource download system.

These tests verify the resource manager's ability to:
- Register and track resources
- Download resources from URLs
- Cache resources appropriately
- Handle concurrent access safely
- Validate checksums
- Recover from errors
"""

import pytest
import tempfile
import hashlib
import os
import http.server
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

from util.resource_manager import (
    ResourceManager,
    ResourceMetadata,
    ProgressReporter,
    CLIProgressReporter,
    get_resource_manager
)


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def resource_manager(temp_cache_dir):
    """Create a ResourceManager instance with temporary cache."""
    return ResourceManager(cache_root=temp_cache_dir)


@pytest.fixture
def sample_resource_metadata():
    """Create sample resource metadata for testing."""
    return ResourceMetadata(
        resource_id="test_resource",
        url="https://example.com/test_file.dat",
        filename="test_file.dat",
        expected_size=1024,
        checksum=None,
        category="test"
    )


class TestResourceManager:
    """Test ResourceManager functionality."""

    def test_initialization(self, temp_cache_dir):
        """Test ResourceManager initialization."""
        manager = ResourceManager(cache_root=temp_cache_dir)
        assert manager.get_cache_root() == temp_cache_dir
        assert temp_cache_dir.exists()

    def test_default_cache_root(self):
        """Test default cache root location."""
        manager = ResourceManager()
        cache_root = manager.get_cache_root()
        assert cache_root is not None
        assert isinstance(cache_root, Path)

    def test_set_cache_root(self, resource_manager, temp_cache_dir):
        """Test setting custom cache root."""
        new_cache = temp_cache_dir / "new_cache"
        resource_manager.set_cache_root(new_cache)
        assert resource_manager.get_cache_root() == new_cache
        assert new_cache.exists()

    def test_register_resource(self, resource_manager, sample_resource_metadata):
        """Test resource registration."""
        resource_manager.register_resource(sample_resource_metadata)
        assert not resource_manager.is_resource_cached(sample_resource_metadata.resource_id)

    def test_register_duplicate_resource(self, resource_manager, sample_resource_metadata):
        """Test registering a resource twice (should replace)."""
        resource_manager.register_resource(sample_resource_metadata)

        # Register again with different metadata
        new_metadata = ResourceMetadata(
            resource_id=sample_resource_metadata.resource_id,
            url="https://example.com/different.dat",
            filename="different.dat",
            expected_size=2048,
            category="test"
        )
        resource_manager.register_resource(new_metadata)

        # Should have replaced the first registration
        assert resource_manager._registry[sample_resource_metadata.resource_id].url == new_metadata.url

    def test_is_resource_cached_nonexistent(self, resource_manager):
        """Test checking if non-registered resource is cached."""
        assert not resource_manager.is_resource_cached("nonexistent")

    def test_is_resource_cached_exists(self, resource_manager, sample_resource_metadata, temp_cache_dir):
        """Test checking if cached resource exists."""
        resource_manager.register_resource(sample_resource_metadata)

        # Create the cached file
        cache_file = temp_cache_dir / sample_resource_metadata.category / sample_resource_metadata.filename
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("test content")

        assert resource_manager.is_resource_cached(sample_resource_metadata.resource_id)

    def test_checksum_validation(self, resource_manager, temp_cache_dir):
        """Test checksum validation for cached resources."""
        test_content = b"test content for checksum"
        expected_checksum = hashlib.sha256(test_content).hexdigest()

        metadata = ResourceMetadata(
            resource_id="checksum_test",
            url="https://example.com/test.dat",
            filename="test.dat",
            expected_size=len(test_content),
            checksum=expected_checksum,
            category="test"
        )

        resource_manager.register_resource(metadata)

        # Create file with correct content
        cache_file = temp_cache_dir / metadata.category / metadata.filename
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(test_content)

        # Should validate successfully
        assert resource_manager.is_resource_cached(metadata.resource_id)

        # Corrupt the file
        cache_file.write_bytes(b"corrupted content")

        # Should fail validation
        assert not resource_manager.is_resource_cached(metadata.resource_id)

    def test_ensure_resource_not_registered(self, resource_manager):
        """Test ensuring unregistered resource raises error."""
        with pytest.raises(ValueError, match="Unknown resource"):
            resource_manager.ensure_resource("nonexistent")

    def test_get_cached_resources(self, resource_manager, sample_resource_metadata, temp_cache_dir):
        """Test getting list of cached resources."""
        resource_manager.register_resource(sample_resource_metadata)

        # Initially no cached resources
        cached = resource_manager.get_cached_resources()
        assert len(cached) == 0

        # Create the cached file
        cache_file = temp_cache_dir / sample_resource_metadata.category / sample_resource_metadata.filename
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("test content")

        # Now should show as cached
        cached = resource_manager.get_cached_resources()
        assert len(cached) == 1
        assert sample_resource_metadata.resource_id in cached

    def test_clear_cache_category(self, resource_manager, temp_cache_dir):
        """Test clearing specific cache category."""
        # Create files in different categories
        test_dir = temp_cache_dir / "test"
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / "file1.dat").write_text("content")

        models_dir = temp_cache_dir / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        (models_dir / "file2.dat").write_text("content")

        # Clear only test category
        resource_manager.clear_cache(category="test")

        assert not test_dir.exists()
        assert models_dir.exists()

    def test_clear_entire_cache(self, resource_manager, temp_cache_dir):
        """Test clearing entire cache."""
        # Create files in different categories
        test_dir = temp_cache_dir / "test"
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / "file1.dat").write_text("content")

        models_dir = temp_cache_dir / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        (models_dir / "file2.dat").write_text("content")

        # Clear entire cache
        resource_manager.clear_cache()

        # Cache root should exist but be empty
        assert temp_cache_dir.exists()
        assert not test_dir.exists()
        assert not models_dir.exists()


class TestProgressReporter:
    """Test progress reporter functionality."""

    def test_cli_progress_reporter(self, capsys):
        """Test CLI progress reporter."""
        reporter = CLIProgressReporter()

        reporter.start("test_file.dat", 1000)
        captured = capsys.readouterr()
        assert "Downloading test_file.dat" in captured.out

        reporter.update(500, 1000)
        captured = capsys.readouterr()
        assert "50%" in captured.out

        reporter.complete()
        captured = capsys.readouterr()
        assert "complete" in captured.out.lower()

    def test_cli_progress_reporter_error(self, capsys):
        """Test CLI progress reporter error reporting."""
        reporter = CLIProgressReporter()
        reporter.error("Test error message")
        captured = capsys.readouterr()
        assert "Test error message" in captured.err


class TestResourceDownload:
    """Test actual resource download functionality."""

    @pytest.fixture
    def simple_http_server(self):
        """Start a simple HTTP server for testing downloads."""

        class TestHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                # Set directory to serve from
                self.test_content = b"Test file content for download"
                super().__init__(*args, directory=tempfile.gettempdir(), **kwargs)

            def do_GET(self):
                if self.path == "/test_file.dat":
                    self.send_response(200)
                    self.send_header("Content-type", "application/octet-stream")
                    self.send_header("Content-Length", str(len(self.test_content)))
                    self.end_headers()
                    self.wfile.write(self.test_content)
                else:
                    self.send_error(404)

            def log_message(self, format, *args):
                # Suppress server logs during tests
                pass

        # Find an available port
        port = 8765
        server = http.server.HTTPServer(('localhost', port), TestHandler)

        # Start server in background thread
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()

        # Give server time to start
        time.sleep(0.1)

        yield f"http://localhost:{port}"

        # Clean up
        server.shutdown()

    def test_download_resource(self, resource_manager, simple_http_server, temp_cache_dir):
        """Test downloading a resource from HTTP server."""
        test_content = b"Test file content for download"
        expected_checksum = hashlib.sha256(test_content).hexdigest()

        metadata = ResourceMetadata(
            resource_id="download_test",
            url=f"{simple_http_server}/test_file.dat",
            filename="test_file.dat",
            expected_size=len(test_content),
            checksum=expected_checksum,
            category="test"
        )

        resource_manager.register_resource(metadata)

        # Download the resource
        downloaded_path = resource_manager.ensure_resource(
            metadata.resource_id,
            progress_reporter=None  # Silent for test
        )

        # Verify download
        assert downloaded_path.exists()
        assert downloaded_path.read_bytes() == test_content

        # Verify it's cached
        assert resource_manager.is_resource_cached(metadata.resource_id)

    def test_download_already_cached(self, resource_manager, temp_cache_dir):
        """Test that already-cached resources are not re-downloaded."""
        test_content = b"Pre-cached content"

        metadata = ResourceMetadata(
            resource_id="cached_test",
            url="https://example.com/should_not_download.dat",
            filename="cached.dat",
            expected_size=len(test_content),
            category="test"
        )

        resource_manager.register_resource(metadata)

        # Pre-create the cached file
        cache_file = temp_cache_dir / metadata.category / metadata.filename
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(test_content)

        # Ensure resource (should not download)
        result_path = resource_manager.ensure_resource(metadata.resource_id)

        # Should return cached file
        assert result_path == cache_file
        assert result_path.read_bytes() == test_content


class TestSingleton:
    """Test global singleton functionality."""

    def test_get_resource_manager_singleton(self):
        """Test that get_resource_manager returns singleton."""
        manager1 = get_resource_manager()
        manager2 = get_resource_manager()
        assert manager1 is manager2

    def test_singleton_persists_state(self):
        """Test that singleton maintains state across calls."""
        manager = get_resource_manager()

        metadata = ResourceMetadata(
            resource_id="singleton_test",
            url="https://example.com/test.dat",
            filename="test.dat",
            expected_size=100,
            category="test"
        )

        manager.register_resource(metadata)

        # Get manager again and verify resource is still registered
        manager2 = get_resource_manager()
        assert "singleton_test" in manager2._registry


class TestNewResourceMetadataFields:
    """Test new fields added to ResourceMetadata."""

    def test_display_name_field(self):
        """Test display_name field."""
        metadata = ResourceMetadata(
            resource_id="test",
            url="https://example.com/test.dat",
            filename="test.dat",
            expected_size=100,
            display_name="Test Resource"
        )
        assert metadata.display_name == "Test Resource"

    def test_display_name_default(self):
        """Test display_name default value."""
        metadata = ResourceMetadata(
            resource_id="test",
            url="https://example.com/test.dat",
            filename="test.dat",
            expected_size=100
        )
        assert metadata.display_name == ""

    def test_download_type_default(self):
        """Test download_type default value."""
        metadata = ResourceMetadata(
            resource_id="test",
            url="https://example.com/test.dat",
            filename="test.dat",
            expected_size=100
        )
        assert metadata.download_type == "direct"

    def test_download_type_browser(self):
        """Test browser download type."""
        metadata = ResourceMetadata(
            resource_id="test",
            url="https://example.com/test.dat",
            filename="test.dat",
            expected_size=100,
            download_type="browser"
        )
        assert metadata.download_type == "browser"

    def test_subdirectory_field(self):
        """Test subdirectory field."""
        metadata = ResourceMetadata(
            resource_id="test",
            url="https://example.com/test.dat",
            filename="test.dat",
            expected_size=100,
            subdirectory="keynet"
        )
        assert metadata.subdirectory == "keynet"

    def test_required_by_field(self):
        """Test required_by field."""
        metadata = ResourceMetadata(
            resource_id="test",
            url="https://example.com/test.dat",
            filename="test.dat",
            expected_size=100,
            required_by="MusicalKeyCNNAnalyzer"
        )
        assert metadata.required_by == "MusicalKeyCNNAnalyzer"


class TestCustomLocations:
    """Test custom location functionality."""

    def test_set_custom_location(self, resource_manager, sample_resource_metadata, temp_cache_dir):
        """Test setting custom location for a resource."""
        resource_manager.register_resource(sample_resource_metadata)

        # Create a file at custom location
        custom_file = temp_cache_dir / "custom_model.dat"
        custom_file.write_bytes(b"test content")

        result = resource_manager.set_custom_location(
            sample_resource_metadata.resource_id,
            custom_file
        )
        assert result is True

        # Verify custom location is used
        path = resource_manager.get_resource_path(sample_resource_metadata.resource_id)
        assert path == custom_file

    def test_set_custom_location_nonexistent(self, resource_manager, sample_resource_metadata, temp_cache_dir):
        """Test setting custom location with nonexistent file."""
        resource_manager.register_resource(sample_resource_metadata)

        result = resource_manager.set_custom_location(
            sample_resource_metadata.resource_id,
            temp_cache_dir / "nonexistent.dat"
        )
        assert result is False

    def test_get_custom_location(self, resource_manager, sample_resource_metadata, temp_cache_dir):
        """Test getting custom location."""
        resource_manager.register_resource(sample_resource_metadata)

        # Create a file at custom location
        custom_file = temp_cache_dir / "custom_model.dat"
        custom_file.write_bytes(b"test content")

        resource_manager.set_custom_location(
            sample_resource_metadata.resource_id,
            custom_file
        )

        location = resource_manager.get_custom_location(sample_resource_metadata.resource_id)
        assert location == custom_file

    def test_get_custom_location_not_set(self, resource_manager, sample_resource_metadata):
        """Test getting custom location when not set."""
        resource_manager.register_resource(sample_resource_metadata)

        location = resource_manager.get_custom_location(sample_resource_metadata.resource_id)
        assert location is None

    def test_clear_custom_location(self, resource_manager, sample_resource_metadata, temp_cache_dir):
        """Test clearing custom location."""
        resource_manager.register_resource(sample_resource_metadata)

        # Create a file at custom location
        custom_file = temp_cache_dir / "custom_model.dat"
        custom_file.write_bytes(b"test content")

        resource_manager.set_custom_location(
            sample_resource_metadata.resource_id,
            custom_file
        )

        resource_manager.clear_custom_location(sample_resource_metadata.resource_id)

        location = resource_manager.get_custom_location(sample_resource_metadata.resource_id)
        assert location is None


class TestGetAllRegisteredResources:
    """Test get_all_registered_resources method."""

    def test_returns_all_resources(self, resource_manager):
        """Test that all registered resources are returned."""
        metadata1 = ResourceMetadata(
            resource_id="res1",
            url="https://example.com/res1.dat",
            filename="res1.dat",
            expected_size=100
        )
        metadata2 = ResourceMetadata(
            resource_id="res2",
            url="https://example.com/res2.dat",
            filename="res2.dat",
            expected_size=200
        )

        resource_manager.register_resource(metadata1)
        resource_manager.register_resource(metadata2)

        all_resources = resource_manager.get_all_registered_resources()
        assert len(all_resources) == 2
        assert "res1" in all_resources
        assert "res2" in all_resources
        assert all_resources["res1"] == metadata1
        assert all_resources["res2"] == metadata2

    def test_returns_empty_dict_when_no_resources(self, resource_manager):
        """Test that empty dict is returned when no resources registered."""
        all_resources = resource_manager.get_all_registered_resources()
        assert all_resources == {}


class TestIsResourceLoadable:
    """Test is_resource_loadable method (alias for is_resource_cached)."""

    def test_resource_not_loadable_when_not_cached(self, resource_manager, sample_resource_metadata):
        """Test resource is not loadable when not cached."""
        resource_manager.register_resource(sample_resource_metadata)

        assert resource_manager.is_resource_loadable(sample_resource_metadata.resource_id) is False

    def test_resource_loadable_when_cached(self, resource_manager, sample_resource_metadata, temp_cache_dir):
        """Test resource is loadable when cached."""
        resource_manager.register_resource(sample_resource_metadata)

        # Create the cached file
        cache_file = temp_cache_dir / sample_resource_metadata.category / sample_resource_metadata.filename
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(b"test content")

        assert resource_manager.is_resource_loadable(sample_resource_metadata.resource_id) is True


class TestSubdirectorySupport:
    """Test subdirectory support in resource paths."""

    def test_subdirectory_in_path(self, resource_manager, temp_cache_dir):
        """Test that subdirectory is included in resource path."""
        metadata = ResourceMetadata(
            resource_id="test",
            url="https://example.com/test.dat",
            filename="test.dat",
            expected_size=100,
            category="models",
            subdirectory="keynet"
        )
        resource_manager.register_resource(metadata)

        path = resource_manager.get_resource_path(metadata.resource_id)
        expected_path = temp_cache_dir / "models" / "keynet" / "test.dat"
        assert path == expected_path
