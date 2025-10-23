"""
CLI Formatting Utilities

This module provides formatting functions for CLI output, including:
- Analyzer list formatting
- Help text generation for analyzers
- Analysis results formatting (table, CSV, JSON)
- Metadata output formatting
- Generic output writing (file or stdout)
"""

import sys
import json
import csv
import io
from typing import List, Dict, Any, Optional, Type, TextIO
from pathlib import Path

from providers import get_analyzers_by_category, get_all_categories, get_analyzer_by_name, ProviderType
from providers.analysis import AnalyzerBase, AnalyzerCategory
from util.analyzer_options import AnalyzerOption, get_common_analyzer_options


def format_analyzer_list(category_filter: Optional[str] = None) -> str:
    """
    Format a list of available analyzers for display.

    Args:
        category_filter: Optional category name to filter by (e.g., 'bpm', 'key')
                        If None, all analyzers are shown

    Returns:
        Formatted string showing analyzers grouped by category
    """
    output_lines = []

    # Get categories to display
    if category_filter:
        # Try to find matching category
        try:
            filter_cat = AnalyzerCategory[category_filter.upper()]
            categories = [filter_cat]
        except KeyError:
            return f"Error: Unknown analyzer category '{category_filter}'"
    else:
        categories = get_all_categories(ProviderType.ANALYZER)

    if not categories:
        return "No analyzers available"

    # Format each category
    for category in sorted(categories, key=lambda c: c.value):
        analyzers = get_analyzers_by_category(category)

        if not analyzers:
            continue

        # Category header
        output_lines.append(f"{category.value} Analyzers:")

        # List analyzers in this category
        for analyzer_class in sorted(analyzers, key=lambda a: a.name):
            output_lines.append(f"  {analyzer_class.__name__} (v{analyzer_class.version})")
            if analyzer_class.description:
                # Indent description
                desc_lines = analyzer_class.description.split('\n')
                for desc_line in desc_lines:
                    output_lines.append(f"    {desc_line}")

        output_lines.append("")  # Blank line between categories

    return '\n'.join(output_lines)


def format_help_for_analyzer(analyzer_class: Type[AnalyzerBase]) -> str:
    """
    Generate comprehensive help text for a specific analyzer.

    Args:
        analyzer_class: The analyzer class to generate help for

    Returns:
        Formatted help text showing analyzer info and all available options
    """
    output_lines = []

    # Header
    output_lines.append(f"Analyzer: {analyzer_class.name}")
    output_lines.append(f"Class: {analyzer_class.__name__}")
    output_lines.append(f"Version: {analyzer_class.version}")
    output_lines.append(f"Category: {analyzer_class.category}")
    output_lines.append("")

    # Description
    if analyzer_class.description:
        output_lines.append("Description:")
        output_lines.append(f"  {analyzer_class.description}")
        output_lines.append("")

    # Common analyzer options
    common_options = get_common_analyzer_options()
    if common_options:
        output_lines.append("Common Options:")
        for option in common_options:
            output_lines.append(_format_option_help(option))
        output_lines.append("")

    # Analyzer-specific options
    analyzer_options = analyzer_class.get_options_metadata()
    if analyzer_options:
        output_lines.append("Analyzer-Specific Options:")
        for option in analyzer_options:
            output_lines.append(_format_option_help(option))
        output_lines.append("")
    else:
        output_lines.append("This analyzer has no configurable options.")
        output_lines.append("")

    # Thread count info
    thread_count = analyzer_class.get_thread_count()
    if thread_count > 1:
        output_lines.append(f"Note: This analyzer uses {thread_count} threads per file")
        output_lines.append("")

    return '\n'.join(output_lines)


def _format_option_help(option: AnalyzerOption, indent: str = "  ") -> str:
    """
    Format a single option's help text.

    Args:
        option: The AnalyzerOption to format
        indent: Indentation string (default: "  ")

    Returns:
        Formatted help text for the option
    """
    # Option name (convert underscores to hyphens for CLI)
    cli_name = f"--{option.name.replace('_', '-')}"

    # Build the option line
    parts = [f"{indent}{cli_name}"]

    # Add type/value info
    if option.type == 'bool':
        # Boolean flags don't take values
        pass
    elif option.type == 'choice':
        # Show choices
        if option.choices:
            choice_values = []
            for choice in option.choices:
                if isinstance(choice, tuple):
                    choice_values.append(str(choice[0]))
                else:
                    choice_values.append(str(choice))
            parts.append(f"{{{','.join(choice_values)}}}")
    elif option.type in ('int', 'slider'):
        parts.append("N")
    elif option.type == 'float':
        parts.append("F")

    option_line = ' '.join(parts)

    # Add help text and default value
    help_parts = [f"{indent}  {option.help}"]

    # Add default value
    if option.type == 'bool':
        default_str = "enabled" if option.default else "disabled"
        help_parts.append(f" (default: {default_str})")
    else:
        help_parts.append(f" (default: {option.default})")

    # Add range info for numeric types
    if option.type in ('int', 'float', 'slider'):
        if option.min is not None and option.max is not None:
            help_parts.append(f" range: {option.min}-{option.max}")
        elif option.min is not None:
            help_parts.append(f" min: {option.min}")
        elif option.max is not None:
            help_parts.append(f" max: {option.max}")

    help_line = ''.join(help_parts)

    return f"{option_line}\n{help_line}"


def format_analysis_results(
    results: List[Dict[str, Any]],
    analyzer_name: str,
    output_format: str = 'table'
) -> str:
    """
    Format analysis results for display.

    Args:
        results: List of result dictionaries, each containing:
                - 'filepath': path to the file
                - 'results': dict of tag_name -> value
                - 'status': 'success', 'error', or 'skipped'
                - 'error': error message (if status is 'error')
        analyzer_name: Name of the analyzer (used as column prefix)
        output_format: Output format - 'table', 'csv', or 'json'

    Returns:
        Formatted string ready for output
    """
    if output_format == 'json':
        return json.dumps(results, indent=2)

    elif output_format == 'csv':
        if not results:
            return ""

        # Collect all possible result keys
        all_keys = set()
        for result in results:
            if result.get('results'):
                all_keys.update(result['results'].keys())

        # Build CSV header
        header = ['filepath']
        for key in sorted(all_keys):
            header.append(f"{analyzer_name}_{key}")
        header.extend(['status', 'error'])

        # Build CSV rows using StringIO
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(header)

        for result in results:
            row = [result.get('filepath', '')]

            # Add result values
            result_data = result.get('results', {})
            for key in sorted(all_keys):
                row.append(result_data.get(key, ''))

            # Add status and error
            row.append(result.get('status', ''))
            row.append(result.get('error', ''))

            writer.writerow(row)

        return output.getvalue()

    else:  # table format
        if not results:
            return "No results"

        # Collect all possible result keys
        all_keys = set()
        for result in results:
            if result.get('results'):
                all_keys.update(result['results'].keys())

        # Build table header
        columns = ['File']
        for key in sorted(all_keys):
            columns.append(f"{analyzer_name}_{key}")
        columns.append('Status')

        # Calculate column widths
        col_widths = [len(col) for col in columns]

        # Update widths based on data
        for result in results:
            filepath = str(result.get('filepath', ''))
            col_widths[0] = max(col_widths[0], len(filepath))

            result_data = result.get('results', {})
            for idx, key in enumerate(sorted(all_keys), start=1):
                value_str = str(result_data.get(key, '-'))
                col_widths[idx] = max(col_widths[idx], len(value_str))

            status = result.get('status', '')
            if status == 'error' and result.get('error'):
                status = f"Error: {result['error']}"
            elif status == 'skipped' and result.get('error'):
                status = f"Skipped: {result['error']}"

            col_widths[-1] = max(col_widths[-1], len(status))

        # Format header
        header_parts = []
        separator_parts = []
        for idx, col in enumerate(columns):
            header_parts.append(col.ljust(col_widths[idx]))
            separator_parts.append('-' * col_widths[idx])

        output_lines = [
            ' | '.join(header_parts),
            '-|-'.join(separator_parts)
        ]

        # Format rows
        for result in results:
            row_parts = []

            # Filepath
            filepath = str(result.get('filepath', ''))
            row_parts.append(filepath.ljust(col_widths[0]))

            # Result values
            result_data = result.get('results', {})
            for idx, key in enumerate(sorted(all_keys), start=1):
                value_str = str(result_data.get(key, '-'))
                row_parts.append(value_str.ljust(col_widths[idx]))

            # Status
            status = result.get('status', '')
            if status == 'error' and result.get('error'):
                status = f"Error: {result['error']}"
            elif status == 'skipped' and result.get('error'):
                status = f"Skipped: {result['error']}"

            row_parts.append(status.ljust(col_widths[-1]))

            output_lines.append(' | '.join(row_parts))

        return '\n'.join(output_lines)


def format_metadata_output(
    media_files: List,
    output_format: str = 'table',
    include_tags: bool = True,
    include_stream_info: bool = False,
    include_internal: bool = False,
    tag_filter: Optional[List[str]] = None
) -> str:
    """
    Format metadata for display.

    Args:
        media_files: List of MediaFile instances
        output_format: Output format - 'table', 'csv', or 'json'
        include_tags: Include tag metadata
        include_stream_info: Include stream information
        include_internal: Include internal file info
        tag_filter: Optional list of specific tags to show (if None, show all)

    Returns:
        Formatted string ready for output
    """
    if output_format == 'json':
        output_data = []
        for mf in media_files:
            data = mf.to_dict()
            # Filter if requested
            if not include_tags:
                data.pop('tags', None)
            if not include_stream_info:
                data.pop('stream_info', None)
            if not include_internal:
                data.pop('internal', None)

            # Apply tag filter
            if tag_filter and 'tags' in data:
                filtered_tags = {k: v for k, v in data['tags'].items() if k in tag_filter}
                data['tags'] = filtered_tags

            output_data.append(data)

        return json.dumps(output_data, indent=2)

    elif output_format == 'csv':
        if not media_files:
            return ""

        # Collect all keys
        all_keys = set()
        for mf in media_files:
            data = mf.to_dict()
            if include_tags:
                all_keys.update(data.get('tags', {}).keys())
            if include_stream_info:
                all_keys.update(data.get('stream_info', {}).keys())
            if include_internal:
                all_keys.update(data.get('internal', {}).keys())

        # Apply tag filter
        if tag_filter:
            all_keys = all_keys.intersection(set(tag_filter))

        # Build CSV using StringIO
        header = ['file_path'] + sorted(list(all_keys))

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(header)

        for mf in media_files:
            data = mf.to_dict()
            row = [mf.file_path]

            for key in sorted(list(all_keys)):
                # Check in tags first, then stream_info, then internal
                value = None
                if include_tags and key in data.get('tags', {}):
                    value = data['tags'][key].get('value', '')
                elif include_stream_info and key in data.get('stream_info', {}):
                    value = data['stream_info'][key]
                elif include_internal and key in data.get('internal', {}):
                    value = data['internal'][key]

                row.append(value if value is not None else '')

            writer.writerow(row)

        return output.getvalue()

    else:  # table format
        output_lines = []

        for media_file in media_files:
            output_lines.append(f"Metadata for: {media_file.file_path}")

            metadata = media_file.to_dict()

            # Tags
            if include_tags:
                output_lines.append("\nTags:")
                tags = metadata.get('tags', {})

                # Apply tag filter
                if tag_filter:
                    tags = {k: v for k, v in tags.items() if k in tag_filter}

                if tags:
                    for key, value in sorted(tags.items()):
                        output_lines.append(f"  {key}: {value.get('value')}")
                else:
                    output_lines.append("  No tags found.")

            # Stream info
            if include_stream_info:
                output_lines.append("\nStream Info:")
                stream_info = metadata.get('stream_info', {})
                if stream_info:
                    for key, value in sorted(stream_info.items()):
                        output_lines.append(f"  {key}: {value}")
                else:
                    output_lines.append("  No stream info found.")

            # Internal data
            if include_internal:
                output_lines.append("\nInternal Info:")
                internal_data = metadata.get('internal', {})
                if internal_data:
                    for key, value in sorted(internal_data.items()):
                        output_lines.append(f"  {key}: {value}")
                else:
                    output_lines.append("  No internal info found.")

            if len(media_files) > 1:
                output_lines.append("-" * 50)

        return '\n'.join(output_lines)


def write_output(content: str, output_file: Optional[str] = None) -> None:
    """
    Write content to a file or stdout.

    Args:
        content: The content to write
        output_file: Optional file path. If None, writes to stdout
    """
    if output_file:
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
            f.write('\n')
    else:
        print(content)
