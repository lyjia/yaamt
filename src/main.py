#!/usr/bin/env python

"""
YAAMT Command-Line Interface

This module implements the CLI with verb-based commands:
- help: Show help for commands and analyzers
- list: List available analyzers
- read: Read and display metadata
- write: Write metadata to files
- analyze: Analyze audio files
"""

import argparse
import sys
import os
from typing import List, Optional, Dict, Any

from models.edit_manager import EditManager
from models.media_file import MediaFile
from models.settings import settings as qsettings
from providers import get_analyzer_by_name, get_analyzers_by_category, AnalyzerCategory
from providers.analysis.base import AnalyzerBase
from workers.analyzer_dispatcher import AnalyzerDispatcher
from util.const import ALL_TAGS
from util.logging import log, configure_logger
from util.version import get_version
from util.cli_formatters import (
    format_analyzer_list,
    format_help_for_analyzer,
    format_analysis_results,
    format_metadata_output,
    write_output
)
from util.analyzer_options import add_option_to_argparse, get_common_analyzer_options

# Exit codes
SYS_RETURN_SUCCESS = 0
SYS_RETURN_ERROR = 1
SYS_RETURN_FILE_INVALID = 2
SYS_RETURN_FILE_NOT_FOUND = 3

# Supported file extensions
SUPPORTED_EXTENSIONS = ['.mp3', '.flac', '.wav']

# Output formats
OUTPUT_FORMATS = ['list', 'table', 'csv', 'json']


def get_files(paths: List[str], recursive: bool = False) -> List[str]:
    """
    Collect audio file paths from the given paths.

    Args:
        paths: List of file or directory paths
        recursive: If True, scan directories recursively

    Returns:
        List of audio file paths
    """
    files = []

    for path in paths:
        if os.path.isfile(path):
            if os.path.splitext(path)[-1].lower() in SUPPORTED_EXTENSIONS:
                files.append(path)
        elif os.path.isdir(path):
            if recursive:
                for root, _, filenames in os.walk(path):
                    for filename in filenames:
                        if os.path.splitext(filename)[-1].lower() in SUPPORTED_EXTENSIONS:
                            files.append(os.path.join(root, filename))
            else:
                for filename in os.listdir(path):
                    filepath = os.path.join(path, filename)
                    if os.path.isfile(filepath) and os.path.splitext(filename)[-1].lower() in SUPPORTED_EXTENSIONS:
                        files.append(filepath)

    return files


def load_media_files(file_paths: List[str], enable_write: bool = False) -> List[MediaFile]:
    """
    Load MediaFile instances from file paths.

    Args:
        file_paths: List of file paths to load
        enable_write: If True, enable write mode on MediaFiles

    Returns:
        List of successfully loaded MediaFile instances
    """
    media_files = []

    for file_path in file_paths:
        try:
            media_file = MediaFile(file_path, enable_write=enable_write)
            if not media_file.is_readable():
                log.error(f"File is not readable: {file_path}")
                continue
            media_files.append(media_file)
        except Exception as e:
            log.error(f"Failed to load {file_path}: {e}")

    return media_files


# ============================================================================
# Command Handlers
# ============================================================================

def cmd_help(args):
    """Handle the 'help' command."""
    if args.subcommand:
        # Help for specific command
        if args.subcommand == 'list':
            print("Usage: main.py list analyzers [category]")
            print()
            print("List available analyzers, optionally filtered by category.")
            print()
            print("Categories: bpm, key, loudness, fingerprint")

        elif args.subcommand == 'read':
            print("Usage: main.py read [options] <paths...>")
            print()
            print("Read and display metadata from audio files.")
            print()
            print("Options:")
            print("  -R, --recursive       Scan subdirectories")
            print("  -f, --output-format   Output format: list, table, csv, json (default: table)")
            print("  -o, --output-file     Write to file instead of stdout")
            print("  --tags TAG1,TAG2,...  Show only specified tags")
            print("  --stream-info         Include stream information")
            print("  --internal            Include internal file info")
            print()
            print("Formats:")
            print("  list   - Detailed view showing one file at a time")
            print("  table  - Columnar table with directory and filename separated")
            print("  csv    - Comma-separated values")
            print("  json   - JSON format")

        elif args.subcommand == 'write':
            print("Usage: main.py write [options] <paths...>")
            print()
            print("Write metadata to audio files.")
            print()
            print("Options:")
            print("  -R, --recursive       Scan subdirectories")
            print("  --tag KEY=VALUE       Set tag (can be used multiple times)")
            print()
            print("Tag Shortcuts:")
            for tag_name, display_name in sorted(ALL_TAGS.items()):
                print(f"  --{tag_name} VALUE    Set {display_name}")

        elif args.subcommand == 'analyze':
            if args.analyzer:
                # Help for specific analyzer
                analyzer_class = get_analyzer_by_name(args.analyzer)
                if analyzer_class:
                    print(format_help_for_analyzer(analyzer_class))
                else:
                    print(f"Error: Unknown analyzer '{args.analyzer}'")
                    return SYS_RETURN_ERROR
            else:
                # General analyze help
                print("Usage: main.py analyze <AnalyzerName> [options] <paths...>")
                print()
                print("Analyze audio files using the specified analyzer.")
                print()
                print("Common Options:")
                print("  -R, --recursive              Scan subdirectories")
                print("  -w, --write-tags             Write results to file metadata")
                print("  -f, --output-format FORMAT   Display format: list, table, csv, json")
                print("  -o, --output-file FILE       Write output to file")
                print("  --skip-if-tag-exists         Skip files that already have tag values")
                print("  --threads N                  Thread pool size (default: 1)")
                print("  --use-saved-prefs            Load options from GUI preferences")
                print()
                print("Formats:")
                print("  list   - Detailed view showing one file at a time")
                print("  table  - Columnar table with directory and filename separated")
                print("  csv    - Comma-separated values")
                print("  json   - JSON format")
                print()
                print("Available Analyzers:")
                print(format_analyzer_list())
                print()
                print("For analyzer-specific options, use: main.py help analyze <AnalyzerName>")

        else:
            print(f"Unknown command: {args.subcommand}")
            return SYS_RETURN_ERROR

    else:
        # Main help
        print("YAAMT - Yet Another Audio Metadata Tool")
        print()
        print("Usage: main.py [--version] [--verbose] <command> [options] [arguments]")
        print()
        print("Commands:")
        print("  help [command] [subcommand]  Show help")
        print("  list <type> [filter]         List available modules")
        print("  read [options] <paths...>    Read and display metadata")
        print("  write [options] <paths...>   Write metadata to files")
        print("  analyze <analyzer> [opts...] <paths...>  Analyze audio files")
        print()
        print("Global Options:")
        print("  --version    Show version and exit")
        print("  --verbose    Enable verbose output")
        print()
        print("Use 'main.py help <command>' for more information on a specific command.")

    return SYS_RETURN_SUCCESS


def cmd_list(args):
    """Handle the 'list' command."""
    if args.type == 'analyzers':
        output = format_analyzer_list(args.filter)
        print(output)
        return SYS_RETURN_SUCCESS
    else:
        print(f"Error: Unknown list type '{args.type}'")
        print("Available types: analyzers")
        return SYS_RETURN_ERROR


def cmd_read(args):
    """Handle the 'read' command."""
    # Collect files
    file_paths = get_files(args.paths, args.recursive)
    if not file_paths:
        print("Error: No supported audio files found", file=sys.stderr)
        return SYS_RETURN_FILE_NOT_FOUND

    # Load media files
    media_files = load_media_files(file_paths)
    if not media_files:
        print("Error: Failed to load any media files", file=sys.stderr)
        return SYS_RETURN_FILE_INVALID

    # Parse tag filter if provided
    tag_filter = None
    if args.tags:
        tag_filter = [tag.strip() for tag in args.tags.split(',')]

    # Format output
    output = format_metadata_output(
        media_files,
        output_format=args.output_format,
        include_tags=True,
        include_stream_info=args.stream_info,
        include_internal=args.internal,
        tag_filter=tag_filter
    )

    # Write output
    write_output(output, args.output_file)

    return SYS_RETURN_SUCCESS


def cmd_write(args):
    """Handle the 'write' command."""
    # Collect files
    file_paths = get_files(args.paths, args.recursive)
    if not file_paths:
        print("Error: No supported audio files found", file=sys.stderr)
        return SYS_RETURN_FILE_NOT_FOUND

    # Load media files with write enabled
    media_files = load_media_files(file_paths, enable_write=True)
    if not media_files:
        print("Error: Failed to load any media files", file=sys.stderr)
        return SYS_RETURN_FILE_INVALID

    # Collect write operations
    write_ops = []

    # Tag shortcuts
    for tag_name in ALL_TAGS:
        value = getattr(args, tag_name, None)
        if value is not None:
            write_ops.append({'key': tag_name, 'value': value})

    # --tag KEY=VALUE arguments
    if args.tag:
        for tag_spec in args.tag:
            if '=' not in tag_spec:
                print(f"Error: Invalid tag specification '{tag_spec}'. Use KEY=VALUE format.")
                return SYS_RETURN_ERROR
            key, value = tag_spec.split('=', 1)
            write_ops.append({'key': key.strip(), 'value': value.strip()})

    if not write_ops:
        print("Error: No tags specified to write")
        return SYS_RETURN_ERROR

    # Write tags
    edit_manager = EditManager()
    edit_manager.register_media_files(media_files)

    for change in write_ops:
        edit_manager.stage_change(media_files, change['key'], change['value'], False)

    # Commit changes
    saved_files, errors = edit_manager.commit_changes_sync()

    if errors:
        log.error("Commit failed with errors:")
        for error in errors:
            log.error(f"  - {error}")
        return SYS_RETURN_ERROR

    print(f"Successfully updated {len(saved_files)} file(s)")
    return SYS_RETURN_SUCCESS


def cmd_analyze(args):
    """Handle the 'analyze' command."""
    # Get analyzer class
    analyzer_class = get_analyzer_by_name(args.analyzer)
    if not analyzer_class:
        print(f"Error: Unknown analyzer '{args.analyzer}'", file=sys.stderr)
        print("Use 'main.py list analyzers' to see available analyzers")
        return SYS_RETURN_ERROR

    # Collect files
    file_paths = get_files(args.paths, args.recursive)
    if not file_paths:
        print("Error: No supported audio files found", file=sys.stderr)
        return SYS_RETURN_FILE_NOT_FOUND

    # Load media files (with write enabled if --write-tags is set)
    media_files = load_media_files(file_paths, enable_write=args.write_tags)
    if not media_files:
        print("Error: Failed to load any media files", file=sys.stderr)
        return SYS_RETURN_FILE_INVALID

    # Build analyzer options
    analyzer_options = {
        'skip_if_tag_exists': args.skip_if_tag_exists
    }

    # Add analyzer-specific options
    option_metadata = analyzer_class.get_options_metadata()
    for option in option_metadata:
        # Get value from args (argparse uses option name as dest)
        value = getattr(args, option.name, None)
        if value is not None:
            analyzer_options[option.name] = value
        elif args.use_saved_prefs:
            # Load from QSettings
            settings_group = f"analyzers/{analyzer_class.__name__}"
            qsettings.beginGroup(settings_group)
            if option.type == 'bool':
                saved_value = qsettings.value(option.name, option.default, type=bool)
            elif option.type in ('int', 'slider'):
                saved_value = qsettings.value(option.name, option.default, type=int)
            elif option.type == 'float':
                saved_value = qsettings.value(option.name, option.default, type=float)
            else:
                saved_value = qsettings.value(option.name, option.default)
            qsettings.endGroup()
            analyzer_options[option.name] = saved_value
        else:
            # Use default
            analyzer_options[option.name] = option.default

    # Run analysis
    print(f"Analyzing {len(media_files)} file(s) with {analyzer_class.name}...")

    # Create dispatcher
    dispatcher = AnalyzerDispatcher()

    # Queue analysis tasks
    from workers.analyzer_dispatcher import AnalysisTask
    tasks = []
    for media_file in media_files:
        task = AnalysisTask(analyzer_class, media_file, analyzer_options)
        tasks.append(task)

    # Execute analysis (synchronously for CLI)
    thread_pool_size = args.threads
    results = []

    for idx, task in enumerate(tasks, 1):
        print(f"  [{idx}/{len(tasks)}] {task.media_file.file_path}...", end=' ', flush=True)

        # Run analysis
        analyzer = task.analyzer_class(task.media_file, task.options)
        result = analyzer.analyze()
        task.result = result

        # Format result for display
        result_dict = {
            'filepath': task.media_file.file_path,
            'results': result.data if result.success else {},
            'status': 'success' if result.success else ('skipped' if result.skipped else 'error'),
            'error': result.error if (not result.success or result.skipped) else None
        }
        results.append(result_dict)

        # Show status
        if result.success and not result.skipped:
            print("OK")
            # Write to tags if requested
            if args.write_tags and result.data:
                for tag_name, tag_value in result.data.items():
                    task.media_file.set_tag_simple(tag_name, tag_value)
                # Save
                try:
                    task.media_file.save()
                except Exception as e:
                    log.error(f"Failed to save tags for {task.media_file.file_path}: {e}")
        elif result.skipped:
            print(f"SKIPPED ({result.error})")
        else:
            print(f"ERROR ({result.error})")

    # Format and output results
    output = format_analysis_results(
        results,
        analyzer_class.__name__,
        args.output_format
    )

    write_output(output, args.output_file)

    # Return success if at least one file succeeded
    success_count = sum(1 for r in results if r['status'] == 'success')
    if success_count > 0:
        print(f"\nSuccessfully analyzed {success_count}/{len(results)} file(s)")
        return SYS_RETURN_SUCCESS
    else:
        print(f"\nFailed to analyze any files")
        return SYS_RETURN_ERROR


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main CLI entry point."""
    # Create main parser
    parser = argparse.ArgumentParser(
        description="YAAMT - Yet Another Audio Metadata Tool",
        add_help=False  # We handle help ourselves
    )

    # Global options
    parser.add_argument('--version', action='store_true', help='Show version and exit')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # ========================================================================
    # help command
    # ========================================================================
    help_parser = subparsers.add_parser('help', help='Show help')
    help_parser.add_argument('subcommand', nargs='?', help='Command to get help for')
    help_parser.add_argument('analyzer', nargs='?', help='Analyzer to get help for')

    # ========================================================================
    # list command
    # ========================================================================
    list_parser = subparsers.add_parser('list', help='List available modules')
    list_parser.add_argument('type', choices=['analyzers'], help='Type of module to list')
    list_parser.add_argument('filter', nargs='?', help='Optional filter (e.g., category name)')

    # ========================================================================
    # read command
    # ========================================================================
    read_parser = subparsers.add_parser('read', help='Read and display metadata')
    read_parser.add_argument('-R', '--recursive', action='store_true', help='Scan subdirectories')
    read_parser.add_argument('-f', '--output-format', choices=OUTPUT_FORMATS, default='table',
                           help='Output format (default: table)')
    read_parser.add_argument('-o', '--output-file', help='Write to file instead of stdout')
    read_parser.add_argument('--tags', help='Comma-separated list of tags to show')
    read_parser.add_argument('--stream-info', action='store_true', help='Include stream information')
    read_parser.add_argument('--internal', action='store_true', help='Include internal file info')
    read_parser.add_argument('paths', nargs='+', help='Files or directories to read')

    # ========================================================================
    # write command
    # ========================================================================
    write_parser = subparsers.add_parser('write', help='Write metadata to files')
    write_parser.add_argument('-R', '--recursive', action='store_true', help='Scan subdirectories')
    write_parser.add_argument('--tag', action='append', help='Set tag KEY=VALUE (can be used multiple times)')

    # Add tag shortcuts
    for tag_name, display_name in ALL_TAGS.items():
        write_parser.add_argument(f'--{tag_name}', help=f'Set {display_name}')

    write_parser.add_argument('paths', nargs='+', help='Files or directories to write')

    # ========================================================================
    # analyze command
    # ========================================================================
    analyze_parser = subparsers.add_parser('analyze', help='Analyze audio files')
    analyze_parser.add_argument('analyzer', help='Analyzer class name')
    analyze_parser.add_argument('-R', '--recursive', action='store_true', help='Scan subdirectories')
    analyze_parser.add_argument('-w', '--write-tags', action='store_true',
                              help='Write results to file metadata')
    analyze_parser.add_argument('-f', '--output-format', choices=OUTPUT_FORMATS, default='table',
                              help='Display format (default: table)')
    analyze_parser.add_argument('-o', '--output-file', help='Write output to file')
    analyze_parser.add_argument('--threads', type=int, default=1, help='Thread pool size (default: 1)')
    analyze_parser.add_argument('--use-saved-prefs', action='store_true',
                              help='Load analyzer options from GUI preferences')

    # Analyzer-specific options will be added dynamically after we know which analyzer
    # Common options like --overwrite-existing are added dynamically too
    analyze_parser.add_argument('paths', nargs='+', help='Files or directories to analyze')

    # Parse args (first pass to get command and analyzer)
    args, unknown = parser.parse_known_args()

    # Handle --version
    if args.version:
        print(get_version())
        return SYS_RETURN_SUCCESS

    # Configure logging
    if args.verbose:
        configure_logger(use_formatter=True)

    # Handle analyze command specially to add dynamic options
    if args.command == 'analyze' and hasattr(args, 'analyzer'):
        analyzer_class = get_analyzer_by_name(args.analyzer)
        if analyzer_class:
            # Add common analyzer options
            for option in get_common_analyzer_options():
                add_option_to_argparse(analyze_parser, option)

            # Add analyzer-specific options
            for option in analyzer_class.get_options_metadata():
                add_option_to_argparse(analyze_parser, option)

            # Re-parse with dynamic options
            args = parser.parse_args()

    # Handle no command
    if not args.command:
        cmd_help(argparse.Namespace(subcommand=None, analyzer=None))
        return SYS_RETURN_SUCCESS

    # Dispatch to command handler
    if args.command == 'help':
        return cmd_help(args)
    elif args.command == 'list':
        return cmd_list(args)
    elif args.command == 'read':
        return cmd_read(args)
    elif args.command == 'write':
        return cmd_write(args)
    elif args.command == 'analyze':
        return cmd_analyze(args)
    else:
        print(f"Unknown command: {args.command}")
        return SYS_RETURN_ERROR


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(SYS_RETURN_ERROR)
