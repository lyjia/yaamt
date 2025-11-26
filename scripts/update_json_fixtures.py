#!/usr/bin/env python
"""
Updates the JSON sidecar files for all audio fixtures in the test fixtures directory
by running the yaamt CLI and capturing its JSON output.
"""
import json
import os
import subprocess
import sys


def main():
    """
    Updates the JSON sidecar files for all audio fixtures by running the main
    command-line script and capturing its JSON output.
    """
    # Get the absolute path of the directory where this script resides.
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the absolute path to the yaamt.py script.
    main_py_path = os.path.abspath(os.path.join(script_dir, '..', 'src', 'yaamt.py'))

    # Construct the path to the fixtures directory.
    fixtures_dir = os.path.abspath(os.path.join(script_dir, '..', 'tests', 'fixtures', 'metadata'))

    # Verify that the yaamt.py script exists before proceeding.
    if not os.path.exists(main_py_path):
        print(f"Error: yaamt.py not found at expected path: {main_py_path}", file=sys.stderr)
        sys.exit(1)

    # Verify that the fixtures directory exists.
    if not os.path.isdir(fixtures_dir):
        print(f"Error: Fixtures directory not found at: {fixtures_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Using main script: {main_py_path}")
    print(f"Processing audio files in: {fixtures_dir}")

    # Define the audio file extensions to look for.
    audio_extensions = ['.mp3', '.flac', '.wav', '.ogg']

    # Iterate over all files in the fixtures directory.
    for filename in sorted(os.listdir(fixtures_dir)):
        # Check if the file has one of the target audio extensions.
        _, file_ext = os.path.splitext(filename)
        if file_ext.lower() in audio_extensions:
            audio_file_path = os.path.join(fixtures_dir, filename)
            json_output_path = audio_file_path + '.json'

            print(f"  -> Generating {os.path.basename(json_output_path)}...")

            # Prepare the command using the new CLI format:
            # yaamt.py read -f json <file>
            command = [
                sys.executable,       # Use the same python interpreter running this script.
                main_py_path,
                'read',               # The 'read' command
                '-f', 'json',         # Output format: JSON
                audio_file_path
            ]

            try:
                # Execute the command and capture the JSON output
                result = subprocess.run(
                    command,
                    capture_output=True,
                    check=True,
                    text=True,
                    encoding='utf-8'
                )

                # Parse the JSON output (yaamt.py outputs a list with one element per file)
                output_list = json.loads(result.stdout)

                # Extract the first (and only) element if it's a list with one item
                if isinstance(output_list, list) and len(output_list) == 1:
                    output_dict = output_list[0]
                else:
                    output_dict = output_list

                # Write the dict to the JSON file
                with open(json_output_path, 'w', encoding='utf-8') as json_file:
                    json.dump(output_dict, json_file, indent=4, ensure_ascii=False)

            except subprocess.CalledProcessError as e:
                # Report any errors that occur during the execution of the command.
                print(f"Error processing {filename}:", file=sys.stderr)
                print(f"  Command: {' '.join(command)}", file=sys.stderr)
                print(f"  Stderr: {e.stderr}", file=sys.stderr)
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON output for {filename}: {e}", file=sys.stderr)
            except Exception as e:
                print(f"An unexpected error occurred for {filename}: {e}", file=sys.stderr)

    print("JSON fixture update complete.")


if __name__ == "__main__":
    main()