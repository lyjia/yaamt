# Debug Mode System

**Epic:** Debug Mode Implementation

## Overview
Implement a debug mode system with both runtime and build-time controls to manage debug-only features and exclude troublesome dependencies (like scipy) from release builds.

## Key Requirements
- Runtime `--debug` flag for CLI and GUI
- Debug builds default to debug mode ON, release builds default OFF
- Debug menu visibility controlled by debug mode
- Debug-only analyzers excluded from release builds entirely
- Separate output directories for debug and release builds
- Log level: DEBUG when debug mode on, INFO when off
- Build from temporary copy to prevent corrupting source tree
- Preserve temp workspace on failure for debugging

## Implementation Steps

### 1. Add Build Mode Constant (util/const.py)
- Add `IS_DEBUG_BUILD = True` constant (patched by build system)
- This determines default debug mode for the binary

### 2. Create Debug Mode State Manager (util/debug.py)
- Create new module to track runtime debug mode
- `is_debug_mode()` function to check current state
- `set_debug_mode(enabled: bool)` to set state
- Initialize from `IS_DEBUG_BUILD` constant

### 3. Update Logging System (util/logging.py)
- Modify `configure_logger()` to accept a `log_level` parameter (string: 'debug', 'info', 'warning', 'error')
- Map string to logging constants (logging.DEBUG, logging.INFO, etc.)
- Set handler level based on provided parameter
- Keep abstracted so other flags can control log level independently

### 4. Update CLI Entrypoint (src/yaamt.py)
- Add `--debug` flag to argparse (optional, defaults to `IS_DEBUG_BUILD`)
- Call `set_debug_mode()` based on flag value
- Determine log level: 'debug' if debug mode, else 'info'
- Call `configure_logger(log_level)` with determined level
- Keep log level determination separate from debug mode for future extensibility (e.g., --log-level flag)

### 5. Update GUI Entrypoint (src/yaamt-gui.py)
- Add `--debug` flag to argparse (optional, defaults to `IS_DEBUG_BUILD`)
- Call `set_debug_mode()` based on flag value
- Determine log level: 'debug' if debug mode, else 'info'
- Call `configure_logger(log_level)` with determined level
- Pass debug mode state to MainWindow initialization

### 6. Update GUI Debug Menu (windows/main_window.py)
- Modify `_create_debug_menu()` to only create menu if `is_debug_mode()` returns True
- Conditionally add to menubar based on debug mode

### 7. Add Runtime Filtering for debug_only Analyzers (providers/__init__.py)
- Modify `get_analyzers_by_category()` to filter out analyzers with `debug_only=True` when debug mode is OFF
- Even if present in binary, hide them from UI/CLI when not in debug mode

### 8. Implement Manifest Template System (providers/analysis/_manifest.py)
- Add `# DEBUG_ONLY` marker comments to debug-only analyzer imports
- Example: `from .bpm.multiband_spectral_bpm import MultibandSpectralBPMAnalyzer  # noqa  # DEBUG_ONLY`

### 9. Create Build Preparation System (build.py)

**New helper functions:**
- `create_build_workspace(build_mode)` - Copy source tree to temp location, return temp path
- `prepare_source_for_build(temp_src_path, build_mode)` - Modify copied source based on build mode
  - Patch `IS_DEBUG_BUILD` in util/const.py
  - Patch `VERSION_STRING` in util/const.py
  - For release builds: Remove lines marked with `# DEBUG_ONLY` from _manifest.py
- `cleanup_build_workspace(temp_path)` - Delete temporary build directory

**Build workflow:**
1. Parse `--release` flag (default is debug mode)
2. Create temp workspace: `temp_src = create_build_workspace(build_mode)`
3. Prepare source: `prepare_source_for_build(temp_src, build_mode)`
4. Try:
   - Run build from temp location (PyInstaller)
   - Copy output to `build/debug/` or `build/release/`
   - Cleanup temp workspace on SUCCESS only
5. Except:
   - Print error message with temp workspace path
   - DO NOT cleanup - leave for debugging
   - Re-raise exception

**Implementation details:**
- Use `tempfile.mkdtemp()` with prefix like `yaamt_build_debug_` or `yaamt_build_release_`
- Use `shutil.copytree()` for source copy with ignore patterns
- Ignore patterns: `.git`, `__pycache__`, `*.pyc`, `build/`, `dist/`, `.pytest_cache/`, `.venv/`
- On success: cleanup temp workspace
- On failure: print "Build failed. Temp workspace preserved at: {temp_path}" and leave it

### 10. Wire the temp source path through to PyInstaller
- The PyInstaller spec resolves source paths relative to `SPECPATH`, which is the workspace `build.py` invokes from.
- `build.py` runs PyInstaller from the temp workspace's project root, so no `setup.py` patching is needed.
- Output is placed in the build-mode-specific timestamped directory under `build/`.

### 11. Documentation Updates
- Update README with --debug flag usage
- Add build instructions for debug vs release builds
- Document debug_only flag for analyzer developers
- Document build workspace system and manual cleanup process

## File Changes Summary

**New Files:**
- `src/util/debug.py` - Debug mode state management

**Modified Files:**
- `src/util/const.py` - Add IS_DEBUG_BUILD constant
- `src/yaamt.py` - Add --debug flag, set log level
- `src/yaamt-gui.py` - Add --debug flag, set log level
- `src/util/logging.py` - Accept log_level parameter (string)
- `src/windows/main_window.py` - Conditional debug menu creation
- `src/providers/__init__.py` - Runtime filtering of debug_only analyzers
- `src/providers/analysis/_manifest.py` - Add DEBUG_ONLY markers
- `build.py` - Implement workspace copy system, conditional cleanup
- `setup.py` - Accept source path via environment variable

## Testing Strategy
1. Test debug build with default behavior (debug mode ON)
2. Test debug build with `--debug` flag explicitly OFF
3. Test release build with default behavior (debug mode OFF)
4. Test release build with `--debug` flag explicitly ON
5. Verify debug menu visibility in each scenario
6. Verify debug_only analyzers are not in release binary
7. Verify logging levels in each mode
8. Test successful build (verify temp workspace cleaned up)
9. Test failed build (verify temp workspace preserved and path printed)
10. Verify source tree unchanged after build completes or fails

## Migration Path
1. Initially default debug mode to TRUE in both builds (as requested)
2. Later, change default for release builds to FALSE
3. Debug builds always default to TRUE

## Future Extensibility
- Build workspace system supports future version string injection
- Log level system supports future --log-level or --verbose flags
- Marker system (`# DEBUG_ONLY`) can be extended for other conditional features

## Developer Notes

### Using debug_only Flag
To mark an analyzer as debug-only (excluded from release builds):

```python
class MyDebugAnalyzer(AnalyzerBase):
    name = "My Debug Analyzer"
    debug_only = True  # This analyzer will only be available in debug builds
```

Then add the `# DEBUG_ONLY` marker in `_manifest.py`:

```python
from .my_debug_analyzer import MyDebugAnalyzer  # noqa  # DEBUG_ONLY
```

### Manual Cleanup of Failed Builds
If a build fails, the temporary workspace is preserved for debugging. To manually clean up:

1. Note the temp workspace path from the error message
2. Inspect the files to debug the build issue
3. Delete the directory when done: `rm -rf /tmp/yaamt_build_debug_xxxxx`

### Build Examples

**Debug build:**
```bash
python build.py
```

**Release build:**
```bash
python build.py --release
```

Output locations:
- Debug: `build/debug/`
- Release: `build/release/`
