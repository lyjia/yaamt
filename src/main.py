import argparse
import sys
import json
import traceback
from models.media_file import MediaFile

def main():
    """
    Main function to parse command-line arguments and display audio file metadata.
    """
    parser = argparse.ArgumentParser(description="Read or write metadata from an audio file.")
    parser.add_argument("file_path", nargs='?', default=None, help="The path to the audio file.")
    parser.add_argument("--json", action="store_true", help="Output metadata in JSON format.")
    # parser.add_argument("--title", help="Set the title of the track.")
    # parser.add_argument("--artist", help="Set the artist of the track.")
    # parser.add_argument("--album", help="Set the album of the track.")
    # parser.add_argument("--genre", help="Set the genre of the track.")
    # parser.add_argument("--bpm", type=float, help="Set the BPM of the track.")
    # parser.add_argument("--key", help="Set the musical key of the track.")
    args = parser.parse_args()

    if not args.file_path:
        print("For the GUI, run: python src/gui.py")
        parser.print_help()
        sys.exit(0)

    try:
        media_file = MediaFile(args.file_path)
        
        write_ops = []
        # if args.title:
        #     media_file.title = args.title
        #     write_ops.append("title")
        # if args.artist:
        #     media_file.artist = args.artist
        #     write_ops.append("artist")
        # if args.album:
        #     media_file.album = args.album
        #     write_ops.append("album")
        # if args.genre:
        #     media_file.genre = args.genre
        #     write_ops.append("genre")
        # if args.bpm:
        #     media_file.bpm = args.bpm
        #     write_ops.append("bpm")
        # if args.key:
        #     media_file.key = args.key
        #     write_ops.append("key")

        # if write_ops:
        #     media_file.save()
        #     if not args.json:
        #         print(f"Successfully updated {', '.join(write_ops)} for {args.file_path}")

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
        sys.exit(1)
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=4))
        else:
            traceback.print_exc()
            print(f"An error occurred: {e}", file=sys.stderr)

    sys.exit(0)

if __name__ == "__main__":
    main()