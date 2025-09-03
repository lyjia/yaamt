import argparse

import sys
import json
import traceback
from PySide6.QtCore import QCoreApplication, QThread
from models.edit_manager import EditManager
from models.media_file import MediaFile
from util.const import ALL_TAGS
from util.logging import log, configure_logger

SYS_RETURN_UNKNOWN_FATAL_ERROR = 1
SYS_RETURN_FILE_INVALID = 2
SYS_RETURN_FILE_NOT_FOUND = 3


class CliApp:
    def __init__(self, media_file, changes):
        self.app = QCoreApplication.instance()
        if not self.app:
            self.app = QCoreApplication(sys.argv)

        self.media_file = media_file
        self.changes = changes
        self.edit_manager = EditManager()
        self.edit_manager.register_media_files([self.media_file])

        self.edit_manager.commit_finished.connect(self.on_commit_successful)
        self.edit_manager.commit_failed.connect(self.on_commit_failed)

    def run(self):
        log.debug(f"CliApp.run() called with changes: {self.changes}")
        for change in self.changes:
            self.edit_manager.stage_change([self.media_file], change['key'], change['value'], change.get('is_internal', False))

        self.edit_manager.commit_changes()
        return self.app.exec()

    def on_commit_successful(self, saved_files):
        log.debug(f"CliApp: commit successful for files: {saved_files}")
        log.debug(f"Successfully updated tags for {self.media_file.file_path}")
        self.app.quit()

    def on_commit_failed(self, errors):
        log.debug(f"CliApp: commit failed with errors: {errors}")
        log.debug(f"Failed to update tags for {self.media_file.file_path}:")
        for error in errors:
            log.debug(f"  - {error['error']}")
        self.app.quit()
        sys.exit(1)  # Exit with error code


def main():
    """
    Main function to parse command-line arguments and display audio file metadata.
    """
    parser = argparse.ArgumentParser(description="Read or write metadata from an audio file.")
    parser.add_argument("file_path", nargs='?', default=None, help="The path to the audio file.")
    parser.add_argument("--json", action="store_true", help="Output metadata in JSON format.")
    parser.add_argument("--update-tag", nargs=2, action='append', help="Update a tag. Provide key and value. Can be used multiple times.")
    parser.add_argument("--update-internal-tag", nargs=2, action='append', help="Update an internal tag. Provide key and value. Can be used multiple times.")
    # Add shortcut arguments for all tags
    for tag_name, display_name in ALL_TAGS.items():
        parser.add_argument(f"--{tag_name}", help=f"Set the {display_name.lower()} of the track.")

    args = parser.parse_args()

    if args.json:
        configure_logger(use_formatter=False)

    if not args.file_path:
            print("For the GUI, run: python src/gui.py")
            parser.print_help()
            sys.exit(0)

    try:
        media_file = MediaFile(args.file_path, enable_write=True)

        if not media_file.is_readable():
            if args.json:
                print(json.dumps({"error": "File is not readable"}, indent=4))
            else:
                print(f"Error: File is not readable: {args.file_path}", file=sys.stderr)
            sys.exit(SYS_RETURN_FILE_INVALID)

        write_ops = []
        if args.update_tag:
            for key, value in args.update_tag:
                write_ops.append({'key': key, 'value': value})

        # Process shortcut tag arguments
        for tag_name in ALL_TAGS:
            if getattr(args, tag_name, None) is not None:
                value = getattr(args, tag_name)
                write_ops.append({'key': tag_name, 'value': value})

        if args.update_internal_tag:
            for key, value in args.update_internal_tag:
                write_ops.append({'key': key, 'value': value, 'is_internal': True})

        if write_ops:
            log.debug(f"write_ops: {write_ops}")
            cli_app = CliApp(media_file, write_ops)
            sys.exit(cli_app.run())

        if args.json:
            print(json.dumps(media_file.to_dict(), indent=4))

        elif not write_ops:
            print(f"Metadata for: {args.file_path}")
            
            # Print all available tags
            print("\nTags:")
            if media_file._tag_provider_lookup['tags']:
                for key in sorted(media_file._tag_provider_lookup['tags'].keys()):
                    value = media_file.get_tag_simple(key)
                    if value:
                        print(f"  {key}: {value}")
            else:
                print("  No tags found.")

            # Print all available stream info
            print("\nStream Info:")
            if media_file._tag_provider_lookup['stream_info']:
                for key in sorted(media_file._tag_provider_lookup['stream_info'].keys()):
                    value = media_file.get_stream_info_value(key)
                    if value:
                        print(f"  {key}: {value}")
            else:
                print("  No stream info found.")

            # Print all internal data
            print("\nInternal Info:")
            if media_file._combined_metadata['internal']:
                for key, value in sorted(media_file._combined_metadata['internal'].items()):
                    if value:
                        print(f"  {key}: {value}")
            else:
                print("  No internal info found.")

    except FileNotFoundError:
        if args.json:
            print(json.dumps({"error": f"File not found at '{args.file_path}'"}, indent=4))
        else:
            traceback.print_exc(file=sys.stderr)
            print(f"Error: File not found at '{args.file_path}'", file=sys.stderr)
        sys.exit(SYS_RETURN_FILE_NOT_FOUND)
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=4))
        else:
            traceback.print_exc(file=sys.stderr)
            print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(SYS_RETURN_UNKNOWN_FATAL_ERROR)

    sys.exit(0)


if __name__ == "__main__":
    main()
