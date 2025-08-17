# Testing Guide for Audio Metadata Tool

This directory contains tests for the Audio Metadata Tool project. The testing environment is set up using pytest.

## Test Structure

- All tests are located in the `tests` directory at the project root
- Test files should be named with the prefix `test_` (e.g., `test_audio_metadata.py`)
- Test functions should also be named with the prefix `test_` (e.g., `test_import_works()`)

## Import Structure

The testing environment is configured to allow importing modules from the `src` directory without needing to include the `src` prefix in import statements. This ensures that imports in tests are consistent with imports in the actual code.

For example, instead of:
```python
from src.app.audio_metadata import MediaFile
```

You should use:
```python
from app.audio_metadata import MediaFile
```

This configuration is handled by the `conftest.py` file in the tests directory.

## Running Tests

To run all tests:
```
python -m pytest
```

To run a specific test file:
```
python -m pytest tests/test_audio_metadata.py
```

To run tests with verbose output:
```
python -m pytest -v
```

## Writing Tests

When writing tests, consider the following:

1. Use mocking to avoid actual file system operations or external dependencies
2. Write tests for both success and failure cases
3. Keep tests independent of each other
4. Use descriptive test names that explain what is being tested

Example:
```python
import pytest
from unittest.mock import patch, MagicMock
from app.audio_metadata import MediaFile

@patch('app.audio_metadata.MutagenProvider')
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
```

## Test Coverage

To run tests with coverage reporting:
```
python -m pytest --cov=src
```

This requires the `pytest-cov` package, which can be installed with:
```
pip install pytest-cov
```