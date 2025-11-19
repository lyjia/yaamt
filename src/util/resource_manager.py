"""
Resource Download System

This module provides a generic, thread-safe mechanism for downloading and caching
external resources (models, data files, databases) needed by various components of
the application. It ensures safe concurrent access in the multithreaded analyzer
environment, provides progress feedback, and manages resource storage in
platform-appropriate locations.

Design:
- Generic design: not specific to any analyzer or component
- Thread-safe: file-based locking for concurrent access across threads and processes
- Platform-specific cache directories with user-configurable overrides
- Progress reporting for both GUI and CLI modes
- Checksum validation for resource integrity
- Atomic operations to prevent partial file corruption
- Lazy loading: resources downloaded only when first requested
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Callable
import hashlib
import tempfile
import os
import sys
import urllib.request
import urllib.error
import time
from filelock import FileLock, Timeout

from util.logging import log


@dataclass
class ResourceMetadata:
    """
    Metadata for a downloadable resource.

    Attributes:
        resource_id: Unique identifier for this resource
        url: Download URL for the resource
        filename: Name of the file in cache
        expected_size: Expected file size in bytes (for progress reporting)
        checksum: SHA256 checksum for validation (optional)
        category: Resource category (e.g., "models", "data", "resources")
        version: Version identifier (optional)
    """
    resource_id: str
    url: str
    filename: str
    expected_size: int
    checksum: Optional[str] = None
    category: str = "resources"
    version: Optional[str] = None


class ProgressReporter:
    """
    Abstract interface for reporting download progress.

    Implementations can provide GUI dialogs, CLI progress bars, or silent operation.
    """

    def start(self, resource_name: str, total_size: int):
        """Called when download starts."""
        pass

    def update(self, bytes_downloaded: int, total_size: int):
        """Called periodically during download."""
        pass

    def complete(self):
        """Called when download completes successfully."""
        pass

    def error(self, message: str):
        """Called if download fails."""
        pass


class CLIProgressReporter(ProgressReporter):
    """Console progress reporter for CLI mode."""

    def __init__(self):
        self.resource_name = ""
        self.last_percent = -1

    def start(self, resource_name: str, total_size: int):
        self.resource_name = resource_name
        self.last_percent = -1
        size_mb = total_size / (1024 * 1024)
        print(f"Downloading {resource_name} ({size_mb:.1f} MB)...")

    def update(self, bytes_downloaded: int, total_size: int):
        if total_size > 0:
            percent = int((bytes_downloaded / total_size) * 100)
            if percent != self.last_percent and percent % 10 == 0:
                print(f"  {percent}% complete...")
                self.last_percent = percent

    def complete(self):
        print(f"Download complete: {self.resource_name}")

    def error(self, message: str):
        print(f"Download failed: {message}", file=sys.stderr)


class ResourceManager:
    """
    Manages downloading, caching, and access to external resources.

    This class provides thread-safe and process-safe resource management with:
    - Automatic cache directory management
    - File-based locking for concurrent access
    - Progress reporting callbacks
    - Checksum validation
    - Atomic file operations
    - Retry logic with exponential backoff

    Usage:
        manager = ResourceManager()

        # Register a resource
        manager.register_resource(ResourceMetadata(
            resource_id="keynet_model",
            url="https://example.com/keynet.pt",
            filename="keynet.pt",
            expected_size=50 * 1024 * 1024,  # 50 MB
            checksum="abc123...",
            category="models"
        ))

        # Ensure resource is available (downloads if needed)
        model_path = manager.ensure_resource(
            "keynet_model",
            progress_reporter=CLIProgressReporter()
        )
    """

    def __init__(self, cache_root: Optional[Path] = None):
        """
        Initialize the resource manager.

        Args:
            cache_root: Root directory for cached resources. If None, uses
                       platform-appropriate default location.
        """
        self._registry: Dict[str, ResourceMetadata] = {}
        self._cache_root = cache_root or self._get_default_cache_root()

        # Ensure cache root exists
        self._cache_root.mkdir(parents=True, exist_ok=True)

        log.debug(f"ResourceManager initialized with cache root: {self._cache_root}")

    def _get_default_cache_root(self) -> Path:
        """
        Get platform-appropriate default cache directory.

        Returns:
            Path to cache root directory
        """
        # Check if running in development mode (references folder exists)
        try:
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            references_dir = project_root / "references"

            # If references directory exists, we're in development mode
            if references_dir.exists():
                cache_dir = project_root / "cache"
                log.debug("Using development cache directory")
                return cache_dir
        except Exception as e:
            log.warning(f"Error detecting development mode: {e}")

        # Use platform-specific cache directory
        try:
            from PySide6.QtCore import QStandardPaths

            cache_location = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.CacheLocation
            )

            if cache_location:
                return Path(cache_location) / "YAAMT"
        except Exception as e:
            log.warning(f"Error getting QStandardPaths cache location: {e}")

        # Fallback to user's home directory
        from pathlib import Path
        fallback = Path.home() / ".cache" / "YAAMT"
        log.debug(f"Using fallback cache directory: {fallback}")
        return fallback

    def set_cache_root(self, cache_root: Path):
        """
        Set a custom cache root directory.

        Args:
            cache_root: Path to cache root directory
        """
        self._cache_root = cache_root
        self._cache_root.mkdir(parents=True, exist_ok=True)
        log.info(f"Cache root set to: {self._cache_root}")

    def get_cache_root(self) -> Path:
        """
        Get the current cache root directory.

        Returns:
            Path to cache root directory
        """
        return self._cache_root

    def register_resource(self, metadata: ResourceMetadata):
        """
        Register a resource with metadata.

        Args:
            metadata: Resource metadata
        """
        if metadata.resource_id in self._registry:
            log.warning(f"Resource '{metadata.resource_id}' already registered, replacing")

        self._registry[metadata.resource_id] = metadata
        log.debug(f"Registered resource: {metadata.resource_id} ({metadata.filename})")

    def is_resource_cached(self, resource_id: str) -> bool:
        """
        Check if a resource is already cached.

        Args:
            resource_id: Resource identifier

        Returns:
            True if resource exists in cache and passes validation
        """
        if resource_id not in self._registry:
            return False

        metadata = self._registry[resource_id]
        resource_path = self._get_resource_path(metadata)

        if not resource_path.exists():
            return False

        # Validate checksum if provided
        if metadata.checksum:
            try:
                actual_checksum = self._compute_checksum(resource_path)
                if actual_checksum != metadata.checksum:
                    log.warning(f"Checksum mismatch for {resource_id}, will re-download")
                    return False
            except Exception as e:
                log.error(f"Error validating checksum for {resource_id}: {e}")
                return False

        return True

    def ensure_resource(
        self,
        resource_id: str,
        progress_reporter: Optional[ProgressReporter] = None,
        timeout: float = 300.0
    ) -> Path:
        """
        Ensure a resource is available, downloading if necessary.

        This method is thread-safe and process-safe. If multiple threads or
        processes request the same resource simultaneously, only one will
        download while others wait for completion.

        Args:
            resource_id: Resource identifier
            progress_reporter: Optional progress reporter
            timeout: Lock timeout in seconds (default: 5 minutes)

        Returns:
            Path to cached resource file

        Raises:
            ValueError: If resource_id is not registered
            RuntimeError: If download fails or timeout occurs
        """
        if resource_id not in self._registry:
            raise ValueError(f"Unknown resource: {resource_id}")

        metadata = self._registry[resource_id]
        resource_path = self._get_resource_path(metadata)

        # Fast path: resource already exists and is valid
        if self.is_resource_cached(resource_id):
            log.debug(f"Resource {resource_id} already cached at {resource_path}")
            return resource_path

        # Acquire lock for download
        lock_path = resource_path.with_suffix(resource_path.suffix + '.lock')
        lock = FileLock(lock_path, timeout=timeout)

        try:
            with lock:
                # Double-check: another process may have downloaded while we waited
                if self.is_resource_cached(resource_id):
                    log.debug(f"Resource {resource_id} downloaded by another process")
                    return resource_path

                # Download the resource
                log.info(f"Downloading resource: {resource_id} from {metadata.url}")
                self._download_resource(metadata, resource_path, progress_reporter)

                # Validate checksum
                if metadata.checksum:
                    actual_checksum = self._compute_checksum(resource_path)
                    if actual_checksum != metadata.checksum:
                        # Clean up invalid file
                        resource_path.unlink(missing_ok=True)
                        raise RuntimeError(
                            f"Checksum validation failed for {resource_id}. "
                            f"Expected {metadata.checksum}, got {actual_checksum}"
                        )
                    log.debug(f"Checksum validated for {resource_id}")

                log.info(f"Resource {resource_id} downloaded successfully")
                return resource_path

        except Timeout:
            raise RuntimeError(
                f"Timeout acquiring lock for {resource_id}. "
                f"Another process may be downloading."
            )
        except Exception as e:
            if progress_reporter:
                progress_reporter.error(str(e))
            raise RuntimeError(f"Failed to ensure resource {resource_id}: {e}") from e
        finally:
            # Clean up lock file if it exists
            try:
                if lock_path.exists():
                    lock_path.unlink()
            except Exception as e:
                log.warning(f"Error cleaning up lock file: {e}")

    def _get_resource_path(self, metadata: ResourceMetadata) -> Path:
        """
        Get the path where a resource should be cached.

        Args:
            metadata: Resource metadata

        Returns:
            Path to cached resource file
        """
        category_dir = self._cache_root / metadata.category
        category_dir.mkdir(parents=True, exist_ok=True)
        return category_dir / metadata.filename

    def _download_resource(
        self,
        metadata: ResourceMetadata,
        target_path: Path,
        progress_reporter: Optional[ProgressReporter]
    ):
        """
        Download a resource from URL to target path.

        Uses atomic operations (temp file + rename) to prevent partial files.

        Args:
            metadata: Resource metadata
            target_path: Destination path
            progress_reporter: Optional progress reporter
        """
        # Create temporary file in same directory for atomic rename
        temp_fd, temp_path = tempfile.mkstemp(
            dir=target_path.parent,
            prefix=f".{metadata.filename}.",
            suffix=".tmp"
        )
        temp_file = Path(temp_path)

        try:
            if progress_reporter:
                progress_reporter.start(metadata.filename, metadata.expected_size)

            # Download with retry logic
            max_retries = 3
            retry_delay = 2.0  # seconds

            for attempt in range(max_retries):
                try:
                    self._download_with_progress(
                        metadata.url,
                        temp_fd,
                        metadata.expected_size,
                        progress_reporter
                    )
                    break  # Success
                except urllib.error.URLError as e:
                    if attempt < max_retries - 1:
                        log.warning(
                            f"Download attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {retry_delay}s..."
                        )
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        raise  # Final attempt failed

            # Close the temp file
            os.close(temp_fd)
            temp_fd = -1

            # Atomically move to final location
            temp_file.replace(target_path)

            if progress_reporter:
                progress_reporter.complete()

        except Exception as e:
            log.error(f"Download failed: {e}")
            raise
        finally:
            # Clean up temp file if it still exists
            if temp_fd >= 0:
                try:
                    os.close(temp_fd)
                except Exception:
                    pass

            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception as e:
                    log.warning(f"Error cleaning up temp file: {e}")

    def _download_with_progress(
        self,
        url: str,
        fd: int,
        expected_size: int,
        progress_reporter: Optional[ProgressReporter]
    ):
        """
        Download URL to file descriptor with progress reporting.

        Args:
            url: URL to download
            fd: File descriptor to write to
            expected_size: Expected file size in bytes
            progress_reporter: Optional progress reporter
        """
        # Open URL
        response = urllib.request.urlopen(url, timeout=30)

        # Get actual size from headers if available
        content_length = response.headers.get('Content-Length')
        total_size = int(content_length) if content_length else expected_size

        # Download in chunks
        chunk_size = 8192
        bytes_downloaded = 0

        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break

            os.write(fd, chunk)
            bytes_downloaded += len(chunk)

            if progress_reporter:
                progress_reporter.update(bytes_downloaded, total_size)

    def _compute_checksum(self, file_path: Path) -> str:
        """
        Compute SHA256 checksum of a file.

        Args:
            file_path: Path to file

        Returns:
            Hex-encoded SHA256 checksum
        """
        sha256 = hashlib.sha256()

        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)

        return sha256.hexdigest()

    def clear_cache(self, category: Optional[str] = None):
        """
        Clear cached resources.

        Args:
            category: If specified, only clear resources in this category.
                     If None, clear entire cache.
        """
        if category:
            category_dir = self._cache_root / category
            if category_dir.exists():
                import shutil
                shutil.rmtree(category_dir)
                log.info(f"Cleared cache category: {category}")
        else:
            import shutil
            if self._cache_root.exists():
                shutil.rmtree(self._cache_root)
                self._cache_root.mkdir(parents=True, exist_ok=True)
                log.info("Cleared entire cache")

    def get_cached_resources(self) -> Dict[str, Path]:
        """
        Get all currently cached resources.

        Returns:
            Dictionary mapping resource_id to cached file path
        """
        cached = {}
        for resource_id in self._registry:
            if self.is_resource_cached(resource_id):
                metadata = self._registry[resource_id]
                cached[resource_id] = self._get_resource_path(metadata)
        return cached


# Global singleton instance
_resource_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """
    Get the global ResourceManager singleton.

    Returns:
        Global ResourceManager instance
    """
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


def set_cache_root(cache_root: Path):
    """
    Set the cache root for the global ResourceManager.

    Args:
        cache_root: Path to cache root directory
    """
    get_resource_manager().set_cache_root(cache_root)
