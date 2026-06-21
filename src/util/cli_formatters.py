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
import os
import json
import csv
import io
from typing import Any, TextIO
from pathlib import Path

from providers import get_analyzers_by_category, get_all_categories, get_analyzer_by_name, ProviderType
from providers.analysis import AnalyzerBase, AnalyzerCategory
from util.analyzer_options import AnalyzerOption, get_common_analyzer_options


def format_analyzer_list(category_filter: str | None = None) -> str:
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


def format_help_for_analyzer(analyzer_class: type[AnalyzerBase]) -> str:
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


def _format_as_json(data: Any) -> str:
    """Format data as JSON."""
    return json.dumps(data, indent=2)


def _format_as_csv(
    rows: list[dict[str, Any]],
    columns: list[str],
    filepath_key: str = 'filepath'
) -> str:
    """
    Format data as CSV with directory and filename separated.

    Args:
        rows: List of row dictionaries containing data to display
        columns: List of column names (excluding directory and filename)
        filepath_key: Key in row dict that contains the full file path

    Returns:
        CSV formatted string
    """
    if not rows:
        return ""

    # Build CSV header with separate directory and filename columns
    header = ['directory', 'filename'] + columns

    # Build CSV rows using StringIO
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)

    for row in rows:
        filepath = row.get(filepath_key, '')
        path_obj = Path(filepath)

        csv_row = [
            str(path_obj.parent) if path_obj.parent != Path('.') else '',
            path_obj.name
        ]

        # Add other column values
        for col in columns:
            csv_row.append(row.get(col, ''))

        writer.writerow(csv_row)

    return output.getvalue()


def _format_as_list(
    rows: list[dict[str, Any]],
    columns: list[str],
    filepath_key: str = 'filepath',
    title_prefix: str = "Data for"
) -> str:
    """
    Format data as a detailed list showing one file at a time.

    Args:
        rows: List of row dictionaries containing data to display
        columns: List of column names to display
        filepath_key: Key in row dict that contains the full file path
        title_prefix: Prefix for the title line (e.g., "Metadata for", "Results for")

    Returns:
        List formatted string
    """
    if not rows:
        return "No results"

    output_lines = []

    for row in rows:
        path_obj = Path(row.get(filepath_key, ''))
        directory = str(path_obj.parent) if path_obj.parent != Path('.') else '.'
        filename = path_obj.name
        output_lines.append(f"{title_prefix}: {directory}{os.sep}{filename}")

        # Show data for each column
        has_data = False
        for col in columns:
            value = row.get(col)
            if value is not None and value != '':
                if not has_data:
                    output_lines.append("")
                    has_data = True
                output_lines.append(f"  {col}: {value}")

        if not has_data:
            output_lines.append("  No data")

        if len(rows) > 1:
            output_lines.append("-" * 50)

    return '\n'.join(output_lines)


def _format_as_table(
    rows: list[dict[str, Any]],
    columns: list[str],
    filepath_key: str = 'filepath'
) -> str:
    """
    Format data as a columnar table with directory and filename separated.

    Args:
        rows: List of row dictionaries containing data to display
        columns: List of column names (excluding Directory and Filename which are added automatically)
        filepath_key: Key in row dict that contains the full file path

    Returns:
        Formatted table string
    """
    if not rows:
        return "No results"

    # Build table header with Directory and Filename first
    all_columns = ['Directory', 'Filename'] + columns

    # Calculate column widths
    col_widths = [len(col) for col in all_columns]

    # Update widths based on data
    for row in rows:
        filepath = str(row.get(filepath_key, ''))
        path_obj = Path(filepath)

        directory = str(path_obj.parent) if path_obj.parent != Path('.') else ''
        filename = path_obj.name

        col_widths[0] = max(col_widths[0], len(directory))
        col_widths[1] = max(col_widths[1], len(filename))

        # Update widths for other columns
        for idx, col in enumerate(columns, start=2):
            value_str = str(row.get(col, '-'))
            col_widths[idx] = max(col_widths[idx], len(value_str))

    # Format header
    header_parts = []
    separator_parts = []
    for idx, col in enumerate(all_columns):
        header_parts.append(col.ljust(col_widths[idx]))
        separator_parts.append('-' * col_widths[idx])

    output_lines = [
        ' | '.join(header_parts),
        '-|-'.join(separator_parts)
    ]

    # Format rows
    for row in rows:
        row_parts = []

        # Directory and Filename
        filepath = str(row.get(filepath_key, ''))
        path_obj = Path(filepath)

        directory = str(path_obj.parent) if path_obj.parent != Path('.') else ''
        filename = path_obj.name

        row_parts.append(directory.ljust(col_widths[0]))
        row_parts.append(filename.ljust(col_widths[1]))

        # Other columns
        for idx, col in enumerate(columns, start=2):
            value_str = str(row.get(col, '-'))
            row_parts.append(value_str.ljust(col_widths[idx]))

        output_lines.append(' | '.join(row_parts))

    return '\n'.join(output_lines)


def format_analysis_results(
    results: list[dict[str, Any]],
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
        output_format: Output format - 'list', 'table', 'csv', or 'json'

    Returns:
        Formatted string ready for output
    """
    if output_format == 'json':
        return _format_as_json(results)

    # Collect all possible result keys
    all_keys = set()
    for result in results:
        if result.get('results'):
            all_keys.update(result['results'].keys())

    # Prepare rows with flattened data
    rows = []
    for result in results:
        row = {'filepath': result.get('filepath', '')}

        # Add result values
        result_data = result.get('results', {})
        for key in sorted(all_keys):
            col_name = f"{analyzer_name}_{key}"
            row[col_name] = result_data.get(key, '')

        # Add status and error
        status = result.get('status', '')
        if status == 'error' and result.get('error'):
            status_display = f"Error: {result['error']}"
        elif status == 'skipped' and result.get('error'):
            status_display = f"Skipped: {result['error']}"
        else:
            status_display = status

        row['status'] = status_display
        row['error'] = result.get('error', '')
        rows.append(row)

    # Build column list
    columns = []
    for key in sorted(all_keys):
        columns.append(f"{analyzer_name}_{key}")
    columns.extend(['status', 'error'])

    # Use appropriate formatter based on output_format
    if output_format == 'csv':
        return _format_as_csv(rows, columns, 'filepath')
    elif output_format == 'list':
        return _format_as_list(rows, columns, 'filepath', title_prefix="Results for")
    else:  # table format
        # For table, don't include 'error' as separate column (it's in status)
        table_columns = [col for col in columns if col != 'error']
        # Rename status column for display
        table_rows = []
        for row in rows:
            table_row = row.copy()
            table_row['Status'] = table_row.pop('status')
            table_rows.append(table_row)
        table_columns = [col if col != 'status' else 'Status' for col in table_columns]
        return _format_as_table(table_rows, table_columns, 'filepath')


def format_metadata_output(
    media_files: list,
    output_format: str = 'table',
    include_tags: bool = True,
    include_stream_info: bool = False,
    include_internal: bool = False,
    tag_filter: list[str] | None = None
) -> str:
    """
    Format metadata for display.

    Args:
        media_files: List of MediaFile instances
        output_format: Output format - 'list', 'table', 'csv', or 'json'
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

        return _format_as_json(output_data)

    # Collect all keys and flatten data into rows
    all_keys = set()
    rows = []

    for mf in media_files:
        data = mf.to_dict()

        # Collect keys
        if include_tags:
            all_keys.update(data.get('tags', {}).keys())
        if include_stream_info:
            all_keys.update(data.get('stream_info', {}).keys())
        if include_internal:
            all_keys.update(data.get('internal', {}).keys())

        # Prepare row
        row = {'filepath': mf.file_path}

        # Add tag values
        if include_tags:
            for key, value in data.get('tags', {}).items():
                row[key] = value.get('value', '')

        # Add stream info values
        if include_stream_info:
            for key, value in data.get('stream_info', {}).items():
                row[key] = value

        # Add internal values
        if include_internal:
            for key, value in data.get('internal', {}).items():
                row[key] = value

        rows.append(row)

    # Apply tag filter
    if tag_filter:
        all_keys = all_keys.intersection(set(tag_filter))
        # Remove non-filtered keys from rows
        filtered_rows = []
        for row in rows:
            filtered_row = {'filepath': row['filepath']}
            for key in all_keys:
                if key in row:
                    filtered_row[key] = row[key]
            filtered_rows.append(filtered_row)
        rows = filtered_rows

    # Build column list (sorted)
    columns = sorted(list(all_keys))

    # Use appropriate formatter based on output_format
    if output_format == 'csv':
        return _format_as_csv(rows, columns, 'filepath')
    elif output_format == 'list':
        return _format_as_list(rows, columns, 'filepath', title_prefix="Metadata for")
    else:  # table format
        return _format_as_table(rows, columns, 'filepath')


def write_output(content: str, output_file: str | None = None) -> None:
    """
    Write content to a file or stdout.

    Args:
        content: The content to write
        output_file: Optional file path. If None, writes to stdout
    """
    if output_file:
        output_path = Path(output_file)
        # Use newline='' to prevent double newline translation on Windows
        # (csv module already produces appropriate line endings)
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
            f.write('\n')
    else:
        print(content)
