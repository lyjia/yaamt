# Resource Download System Design Specification

## Overview

The Resource Download System provides a generic, thread-safe mechanism for downloading and caching external resources (models, data files, databases) needed by various components of the application. It ensures safe concurrent access in the multithreaded analyzer environment, provides progress feedback, and manages resource storage in platform-appropriate locations.

## Design Decisions Summary

1. **Generic Design**: System is not specific to any analyzer or component - any part of the application can register and request resources
2. **Thread-Safety**: File-based locking ensures safe concurrent access across threads and processes
3. **Cache Location**: Platform-specific cache directories with user-configurable overrides
4. **Progress Reporting**: Unified progress reporting for both GUI and CLI modes
5. **Validation**: Checksum validation ensures resource integrity
6. **Atomic Operations**: Temporary files with atomic rename prevent partial file corruption
7. **Lazy Loading**: Resources downloaded only when first requested
8. **Process Isolation**: Works correctly with ProcessPoolExecutor used by analyzer system
9. **Fallback Strategy**: Development mode fallbacks for missing resources
10. **Resource Registration**: Components register resources with metadata (URL, size, checksum)
11. **Lock Timeout**: Configurable timeouts prevent indefinite blocking
12. **Error Recovery**: Automatic retry with exponential backoff for transient failures

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Components                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │CNN Analyzer  │  │Future Model  │  │Data Provider │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
            │               │               │
            └───────────────┴───────────────┘
                            │
                            ↓
                ┌───────────────────────────┐
                │    Resource Manager        │
                │  - Resource registration   │
                │  - Cache management        │
                │  - Thread synchronization  │
                └───────────────────────────┘
                            │
                ┌───────────┴────────────┐
                ↓                        ↓
        ┌──────────────┐        ┌──────────────┐
        │File Lock     │        │Download      │
        │Wrapper       │        │Utilities     │
        └──────────────┘        └──────────────┘
                                        │
                            ┌───────────┴────────────┐
                            ↓                        ↓
                    ┌──────────────┐        ┌──────────────┐
                    │GUI Progress  │        │CLI Progress  │
                    │Dialog        │        │Reporter      │
                    └──────────────┘        └──────────────┘
```

### Thread-Safety Model

The system handles multiple concurrent access patterns:

1. **Single Process, Multiple Threads**: QThreadPool with QRunnable workers
2. **Multiple Processes**: ProcessPoolExecutor for parallel analysis
3. **Mixed Access**: GUI thread + worker threads + subprocess analyzers

Protection is achieved through:
- File-based locks that work across processes
- Double-check locking pattern to minimize contention
- Atomic file operations using temp files and rename
- Process-unique temporary file names using PID

### Resource Lifecycle

1. **Registration**: Component registers resource requirements at initialization
2. **Request**: Component requests resource when needed
3. **Cache Check**: System checks cache for existing valid resource
4. **Download**: If missing, acquires lock and downloads
5. **Validation**: Verifies checksum after download
6. **Storage**: Atomically moves to final cache location
7. **Return**: Returns path to cached resource

### Cache Management

#### Directory Structure
```
<cache_root>/
├── models/
│   ├── keynet.pt
│   └── keynet.pt.lock
├── data/
│   └── fingerprint_db.sqlite
└── resources/
    └── other_resources
```

#### Platform-Specific Locations
- **Windows**: `%LOCALAPPDATA%\YAAMT\cache\`
- **Linux**: `~/.cache/YAAMT/`
- **macOS**: `~/Library/Caches/YAAMT/`
- **Development**: `<project_root>/cache/`

## Integration Points

### Analyzer Integration

Analyzers request resources during analysis:
1. Check if resource required
2. Call resource_manager.ensure_resource()
3. Handle download progress if in GUI
4. Use returned path to load resource
5. Continue with analysis

### Settings Integration

User-configurable options:
- Cache directory location
- Auto-download preference
- Download timeout
- Maximum cache size
- Proxy configuration

### Progress Reporting

#### GUI Mode
- Modal dialog with progress bar
- Resource name and size display
- Cancel button with cleanup
- Queue support for multiple downloads

#### CLI Mode
- Console progress bar
- Non-blocking updates
- Clean output formatting
- Quiet mode support

## Resource Registration

Resources are registered with metadata:
- Unique identifier
- Download URL
- Expected file size
- SHA256 checksum
- Version information
- Optional dependencies

## Error Handling

### Network Errors
- Retry with exponential backoff
- Maximum retry count
- Clear error messages
- Fallback to local resources if available

### File System Errors
- Disk space checks
- Permission verification
- Cleanup of partial files
- Alternative cache locations

### Lock Timeouts
- Configurable timeout duration
- Graceful degradation
- Lock cleanup for stale locks
- Process crash recovery

## Performance Considerations

1. **Fast Path**: Lock-free check for existing resources
2. **Lazy Loading**: Download only when needed
3. **One-Time Cost**: Resources cached permanently
4. **Parallel Downloads**: Support for concurrent resource downloads
5. **Chunked Transfer**: Efficient memory usage during download
6. **Resume Support**: Partial download recovery

## Testing Strategy

### Unit Tests
- Resource registration and lookup
- Cache directory management
- Checksum validation
- Download utilities
- Lock mechanism

### Integration Tests
- Concurrent access scenarios
- Process pool compatibility
- GUI/CLI progress reporting
- Settings integration
- Error recovery

### Stress Tests
- Multiple process download attempts
- Network interruption handling
- Lock contention scenarios
- Cache cleanup behavior

## Future Extensions

The generic design enables future capabilities:
- Resource versioning and updates
- Differential downloads
- Compression support
- Mirror/CDN support
- Resource bundling
- Offline mode
- Resource preloading
- Automatic cache cleanup
- Resource sharing between users
- Cloud storage integration

## Implementation Priority

1. **Core Infrastructure**: File locking, download utilities, resource manager
2. **Progress UI**: CLI and GUI progress reporting
3. **CNN Analyzer Integration**: Update to use new system
4. **Settings**: Add configuration options
5. **Testing**: Comprehensive test coverage
6. **Documentation**: User and developer documentation

## Dependencies

- `filelock`: Cross-platform file locking (new dependency)
- `urllib`: HTTP downloads (Python standard library)
- `hashlib`: Checksum validation (Python standard library)
- `PySide6.QtCore.QStandardPaths`: Platform-specific paths (existing)
- `threading/multiprocessing`: Concurrency support (Python standard library)