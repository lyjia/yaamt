import os
import subprocess
import sys

def main():
    """
    Updates the JSON sidecar files for all audio fixtures in this directory by
    running the main command-line script and capturing its JSON output.
    """
    # Get the absolute path of the directory where this script resides.
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the absolute path to the main.py script.
    main_py_path = os.path.abspath(os.path.join(script_dir, '..', '..', '..', 'src', 'main.py'))

    # Verify that the main.py script exists before proceeding.
    if not os.path.exists(main_py_path):
        log.debug(f"Error: main.py not found at expected path: {main_py_path}", file=sys.stderr)
        sys.exit(1)

    log.debug(f"Using main script: {main_py_path}")
    log.debug(f"Processing audio files in: {script_dir}")

    # Define the audio file extensions to look for.
    audio_extensions = ['.mp3', '.flac', '.wav', '.ogg']

    # Iterate over all files in the script's directory.
    for filename in sorted(os.listdir(script_dir)):
        # Check if the file has one of the target audio extensions.
        _, file_ext = os.path.splitext(filename)
        if file_ext.lower() in audio_extensions:
            audio_file_path = os.path.join(script_dir, filename)
            json_output_path = audio_file_path + '.json'

            log.debug(f"  -> Generating {os.path.basename(json_output_path)}...")

            # Prepare the command to be executed.
            command = [
                sys.executable,       # Use the same python interpreter running this script.
                main_py_path,
                audio_file_path,
                '--json'
            ]

            try:
                # Execute the command and redirect the standard output to the .json file.
                with open(json_output_path, 'w', encoding='utf-8') as json_file:
                    subprocess.run(
                        command,
                        stdout=json_file,
                        stderr=subprocess.PIPE,
                        check=True,         # Raise an exception if the command returns a non-zero exit code.
                        text=True,
                        encoding='utf-8'
                    )
            except subprocess.CalledProcessError as e:
                # Report any errors that occur during the execution of the command.
                log.debug(f"Error processing {filename}:", file=sys.stderr)
                log.debug(f"  Command: {' '.join(command)}", file=sys.stderr)
                log.debug(f"  Stderr: {e.stderr}", file=sys.stderr)
            except Exception as e:
                log.debug(f"An unexpected error occurred for {filename}: {e}", file=sys.stderr)

    log.debug("JSON fixture update complete.")

if __name__ == "__main__":
    main()