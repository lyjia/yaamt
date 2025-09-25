import argparse
import sys
import json
import traceback
import os
import csv
from models.edit_manager import EditManager
from models.media_file import MediaFile
from util.const import ALL_TAGS, KEY_STREAM_INFO, KEY_TAGS, KEY_VALUE, KEY_INTERNAL
from util.logging import log, configure_logger
from util.version import get_version

SYS_RETURN_UNKNOWN_FATAL_ERROR = 1
SYS_RETURN_FILE_INVALID = 2
SYS_RETURN_FILE_NOT_FOUND = 3
SUPPORTED_FORMATS = ['json', 'table', 'csv']
SUPPORTED_EXTENSIONS = ['.mp3', '.flac', '.wav']


def get_files(path, recursive=False):
    """
    Generates a list of file paths to be processed.
    If the path is a file, it returns a list containing just that path.
    If the path is a directory, it scans the directory for supported audio files.
    """
    files = []
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
                if os.path.splitext(filename)[-1].lower() in SUPPORTED_EXTENSIONS:
                    files.append(os.path.join(path, filename))
    return files


def print_output(media_files, output_format='table'):
    """
    Prints the output in the specified format.
    """
    if output_format == 'json':
        print(json.dumps([mf.to_dict() for mf in media_files], indent=4))
    elif output_format == 'csv':
        if not media_files:
            return
        writer = csv.writer(sys.stdout)
        # Get all possible keys from all files
        all_keys = set()
        for mf in media_files:
            all_keys.update(mf.to_dict()['tags'].keys())
            all_keys.update(mf.to_dict()['stream_info'].keys())
            all_keys.update(mf.to_dict()['internal'].keys())
        
        header = ['file_path'] + sorted(list(all_keys))
        writer.writerow(header)

        for mf in media_files:
            data = mf.to_dict()
            row = [mf.file_path]
            for key in sorted(list(all_keys)):
                value = (data['tags'].get(key, {}).get('value') or
                         data['stream_info'].get(key) or
                         data['internal'].get(key, ''))
                row.append(value)
            writer.writerow(row)

    else:  # table format
        for media_file in media_files:
            print(f"Metadata for: {media_file.file_path}")

            # Print all available tags
            print("\nTags:")
            metadata = media_file.to_dict()
            tags = metadata.get(KEY_TAGS, {})
            if tags:
                for key, value in sorted(tags.items()):
                    print(f"  {key}: {value.get(KEY_VALUE)}")
            else:
                print("  No tags found.")

            # Print all available stream info
            print("\nStream Info:")
            stream_info = metadata.get(KEY_STREAM_INFO, {})
            if stream_info:
                for key, value in sorted(stream_info.items()):
                    print(f"  {key}: {value.get(KEY_VALUE)}")
            else:
                print("  No stream info found.")

            # Print all internal data
            print("\nInternal Info:")
            internal_data = metadata.get(KEY_INTERNAL, {})
            if internal_data:
                for key, value in sorted(internal_data.items()):
                    print(f"  {key}: {value}")
            else:
                print("  No internal info found.")
            if len(media_files) > 1:
                print("-" * 20)


def main():
    """
    Main function to parse command-line arguments and display audio file metadata.
    """
    parser = argparse.ArgumentParser(description="Read or write metadata from an audio file or directory.")
    parser.add_argument("path", nargs='?', help="The path to the audio file or directory.")
    parser.add_argument("--recursive", action="store_true", help="Scan subdirectories when a directory is provided.")
    parser.add_argument("--format", choices=SUPPORTED_FORMATS, default='table', help="Output format.")
    parser.add_argument("--update-tag", nargs=2, action='append', help="Update a tag. Provide key and value. Can be used multiple times.")
    parser.add_argument("--update-internal-tag", nargs=2, action='append', help="Update an internal tag. Provide key and value. Can be used multiple times.")
    parser.add_argument("--version", action="store_true", help="Print the version number and exit.")

    for tag_name, display_name in ALL_TAGS.items():
        parser.add_argument(f"--{tag_name}", help=f"Set the {display_name.lower()} of the track.")

    args = parser.parse_args()

    # Handle version argument
    if args.version:
        print(get_version())
        sys.exit(0)

    # Check if path is provided when not using version
    if not args.path:
        parser.error("path is required when not using --version")

    if args.format == 'json' or args.format == 'csv':
        configure_logger(use_formatter=False)

    files = get_files(args.path, args.recursive)
    if not files:
        print(f"Error: No supported audio files found at '{args.path}'", file=sys.stderr)
        sys.exit(SYS_RETURN_FILE_NOT_FOUND)

    media_files = []
    for file_path in files:
        try:
            media_file = MediaFile(file_path, enable_write=True)
            if not media_file.is_readable():
                if args.format == 'json':
                    print(json.dumps({"error": f"File is not readable: {file_path}"}, indent=4), file=sys.stderr)
                else:
                    print(f"Error: File is not readable: {file_path}", file=sys.stderr)
                continue
            media_files.append(media_file)
        except Exception as e:
            if args.format == 'json':
                print(json.dumps({"error": f"Failed to process {file_path}: {e}"}, indent=4), file=sys.stderr)
            else:
                print(f"Error: Failed to process {file_path}: {e}", file=sys.stderr)

    if not media_files:
        sys.exit(SYS_RETURN_FILE_INVALID)

    write_ops = []
    if args.update_tag:
        for key, value in args.update_tag:
            write_ops.append({'key': key, 'value': value})

    for tag_name in ALL_TAGS:
        if getattr(args, tag_name, None) is not None:
            value = getattr(args, tag_name)
            write_ops.append({'key': tag_name, 'value': value})

    if args.update_internal_tag:
        for key, value in args.update_internal_tag:
            # For internal tags, we need to determine the appropriate provider
            # For now, we'll assume the first provider in the registered providers list
            provider = None
            if media_files and media_files[0]._registered_providers['tags']:
                provider = media_files[0]._registered_providers['tags'][0]['provider']
            write_ops.append({'key': key, 'value': value, 'is_internal': True, 'provider': provider})

    if write_ops:
        edit_manager = EditManager()
        edit_manager.register_media_files(media_files)
        for change in write_ops:
            if change.get('is_internal', False):
                edit_manager.stage_change(media_files, change['key'], change['value'], True, change['provider'])
            else:
                edit_manager.stage_change(media_files, change['key'], change['value'], False)
        
        # This is a synchronous operation now
        saved_files, errors = edit_manager.commit_changes_sync()

        if errors:
            log.debug(f"Commit failed with errors: {errors}")
            for error in errors:
                log.debug(f"  - {error}")
            sys.exit(1)
        
        log.debug(f"Commit successful for files: {saved_files}")

    print_output(media_files, args.format)

    sys.exit(0)


if __name__ == "__main__":
    main()
