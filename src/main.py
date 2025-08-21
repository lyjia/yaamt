import argparse
import sys
import json
import traceback
from models.media_file import MediaFile
from util.const import ALL_TAGS
from util.logging import log

SYS_RETURN_UNKNOWN_FATAL_ERROR = 1
SYS_RETURN_FILE_INVALID = 2
SYS_RETURN_FILE_NOT_FOUND = 3

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

    if not args.file_path:
        print("For the GUI, run: python src/gui.py")
        parser.print_help()
        sys.exit(0)

    try:
        media_file = MediaFile(args.file_path)

        if not media_file.is_readable():
            if args.json:
                print(json.dumps({"error": "File is not readable"}, indent=4))
            else:
                print(f"Error: File is not readable: {args.file_path}", file=sys.stderr)
            sys.exit(SYS_RETURN_FILE_INVALID)
        
        write_ops = []
        if args.update_tag:
            for key, value in args.update_tag:
                media_file.set_tag(key, value)
                write_ops.append(key)

        # Process shortcut tag arguments
        for tag_name in ALL_TAGS:
            if getattr(args, tag_name, None) is not None:
                value = getattr(args, tag_name)
                media_file.set_tag(tag_name, value)
                write_ops.append(tag_name)

        if args.update_internal_tag:
            for key, value in args.update_internal_tag:
                media_file.set_tag(key, value, internal=True)
                write_ops.append(key)

        if write_ops:
            media_file.save()
            if not args.json:
                print(f"Successfully updated {', '.join(write_ops)} for {args.file_path}")

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
            traceback.print_exc()
            print(f"Error: File not found at '{args.file_path}'", file=sys.stderr)
        sys.exit(SYS_RETURN_FILE_NOT_FOUND)
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=4))
        else:
            traceback.print_exc()
            print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(SYS_RETURN_UNKNOWN_FATAL_ERROR)

    sys.exit(0)

if __name__ == "__main__":
    main()