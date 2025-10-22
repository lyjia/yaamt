#!/usr/bin/env python3
"""
Consolidate audio datasets from multiple sources into a single dataset.

The datasets are expected to be in the following folders:
1. giantsteps-key-dataset: Key annotations https://github.com/GiantSteps/giantsteps-key-dataset
2. giantsteps-tempo-dataset: BPM annotations https://github.com/GiantSteps/giantsteps-tempo-dataset
3. ZenodoBeatportEDMKeyDataset: Full metadata with key annotations https://zenodo.org/records/1101082

By default, the script looks for these folders in the same directory as the script.
Use --path to specify a different base directory.

Outputs:
- Consolidated audio files in 'consolidated_audio' folder
- CSV file with all metadata

TODO: Incorporate https://mirdata.readthedocs.io/en/0.3.6/source/tutorial.html#tutorial ?

Usage:
    python consolidate_datasets.py                    # Uses script directory
    python consolidate_datasets.py --path /some/path  # Uses custom path
"""

import os
import re
import json
import csv
import shutil
import argparse
from pathlib import Path
from collections import defaultdict
import pandas as pd


def extract_id_from_filename(filename):
    """Extract the numeric ID from a filename."""
    match = re.match(r'^(\d+)', filename)
    if match:
        return match.group(1)
    return None


def parse_beatport_filename(filename):
    """
    Parse Beatport filename format: 'ID Artist - Title (Mix).mp3'
    Returns dict with id, artist, title, mix
    """
    # Remove extension
    name = filename.rsplit('.', 1)[0]

    # Extract ID
    match = re.match(r'^(\d+)\s+(.+)$', name)
    if not match:
        return None

    track_id = match.group(1)
    rest = match.group(2)

    # Split artist and title
    if ' - ' in rest:
        artist_part, title_part = rest.split(' - ', 1)

        # Extract mix info from parentheses
        mix_match = re.search(r'\(([^)]+)\)$', title_part)
        if mix_match:
            mix = mix_match.group(1)
            title = title_part[:mix_match.start()].strip()
        else:
            mix = 'Original Mix'
            title = title_part
    else:
        artist_part = rest
        title = ''
        mix = ''

    return {
        'id': track_id,
        'artist': artist_part,
        'title': title,
        'mix': mix
    }


def parse_title_with_mix(title_str):
    """
    Parse a title string that may contain mix info in parentheses.
    Returns tuple of (title, mix)
    """
    if not title_str or pd.isna(title_str):
        return '', ''

    title_str = str(title_str).strip()

    # Extract mix info from parentheses
    mix_match = re.search(r'\(([^)]+)\)$', title_str)
    if mix_match:
        mix = mix_match.group(1)
        title = title_str[:mix_match.start()].strip()
    else:
        title = title_str
        mix = ''

    return title, mix


def read_giantsteps_excel_metadata(giantsteps_key_dir):
    """Read artist/title metadata from giantsteps sources.xlsx file."""
    excel_file = giantsteps_key_dir / "sources.xlsx"
    metadata = {}

    if not excel_file.exists():
        return metadata

    try:
        df = pd.read_excel(excel_file)

        for _, row in df.iterrows():
            track_id = str(row.get('TRACK', '')).strip()
            if not track_id or track_id == 'nan':
                continue

            artist = row.get('ARTIST', '')
            title_raw = row.get('TRACK.1', '')  # Column is named TRACK.1
            genre = row.get('SUBGENRE', '')

            # Handle NaN values
            if pd.isna(artist):
                artist = ''
            else:
                artist = str(artist).strip()

            if pd.isna(genre):
                genre = ''
            else:
                genre = str(genre).strip()

            # Parse title to extract mix info
            title, mix = parse_title_with_mix(title_raw)

            metadata[track_id] = {
                'artist': artist,
                'title': title,
                'mix': mix,
                'genre_excel': genre,
            }

    except Exception as e:
        print(f"  Warning: Could not read Excel file: {e}")

    return metadata


def read_giantsteps_key_dataset(giantsteps_key_dir):
    """Read key annotations from giantsteps-key-dataset."""
    data = {}

    # Read Excel metadata (artist, title, genre)
    print("  Reading Excel metadata...")
    excel_metadata = read_giantsteps_excel_metadata(giantsteps_key_dir)
    print(f"  Found metadata for {len(excel_metadata)} tracks in Excel")

    # Read key files
    key_dir = giantsteps_key_dir / "annotations" / "key"
    if key_dir.exists():
        for key_file in key_dir.glob("*.key"):
            track_id = extract_id_from_filename(key_file.name)
            if track_id:
                with open(key_file, 'r', encoding='utf-8') as f:
                    key = f.read().strip()
                    data[track_id] = {'key': key}

                # Add Excel metadata if available
                if track_id in excel_metadata:
                    data[track_id].update(excel_metadata[track_id])

    # Read JAMS files for additional metadata (genre as fallback)
    jams_dir = giantsteps_key_dir / "annotations" / "jams"
    if jams_dir.exists():
        for jams_file in jams_dir.glob("*.jams"):
            track_id = extract_id_from_filename(jams_file.name)
            if track_id:
                try:
                    with open(jams_file, 'r', encoding='utf-8') as f:
                        jams_data = json.load(f)

                    # Extract genre from tag_open namespace
                    genre_jams = None
                    for annotation in jams_data.get('annotations', []):
                        if annotation.get('namespace') == 'tag_open':
                            if annotation.get('data'):
                                genre_jams = annotation['data'][0].get('value', '')

                    if track_id not in data:
                        data[track_id] = {}
                    # Use Excel genre if available, otherwise use JAMS genre
                    if 'genre_excel' not in data[track_id] or not data[track_id].get('genre_excel'):
                        data[track_id]['genre'] = genre_jams
                    else:
                        data[track_id]['genre'] = data[track_id].get('genre_excel')
                except (json.JSONDecodeError, KeyError):
                    pass

    # Find audio files
    audio_dir = giantsteps_key_dir / "audio"
    if audio_dir.exists():
        for audio_file in audio_dir.glob("*.mp3"):
            track_id = extract_id_from_filename(audio_file.name)
            if track_id:
                if track_id not in data:
                    data[track_id] = {}
                data[track_id]['audio_file_key'] = str(audio_file)

    return data


def read_giantsteps_tempo_dataset(giantsteps_tempo_dir):
    """Read BPM annotations from giantsteps-tempo-dataset."""
    data = {}

    # Read BPM files
    bpm_dir = giantsteps_tempo_dir / "annotations" / "tempo"
    if bpm_dir.exists():
        for bpm_file in bpm_dir.glob("*.bpm"):
            track_id = extract_id_from_filename(bpm_file.name)
            if track_id:
                with open(bpm_file, 'r', encoding='utf-8') as f:
                    bpm = f.read().strip()
                    data[track_id] = {'bpm': bpm}

    # Find audio files
    audio_dir = giantsteps_tempo_dir / "audio"
    if audio_dir.exists():
        for audio_file in audio_dir.glob("*.mp3"):
            track_id = extract_id_from_filename(audio_file.name)
            if track_id:
                if track_id not in data:
                    data[track_id] = {}
                data[track_id]['audio_file_tempo'] = str(audio_file)

    return data


def read_beatport_dataset(beatport_dir):
    """Read metadata and key annotations from ZenodoBeatportEDMKeyDataset."""
    data = {}

    # Read CSV metadata
    csv_file = beatport_dir / "Beatport-EDM-Key-Dataset.csv"
    if csv_file.exists():
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                track_id = row.get('id', '').strip()
                if track_id:
                    data[track_id] = {
                        'artist': row.get('artists', ''),
                        'title': row.get('title', ''),
                        'mix': row.get('mix', ''),
                        'album': row.get('label', ''),  # Using label as album
                        'genre': row.get('genres', ''),
                        'key': row.get('main_key', ''),
                    }

    # Read key annotations from txt files
    keys_dir = beatport_dir / "keys"
    if keys_dir.exists():
        for key_file in keys_dir.glob("*.txt"):
            parsed = parse_beatport_filename(key_file.name)
            if parsed:
                track_id = parsed['id']
                with open(key_file, 'r', encoding='utf-8') as f:
                    key = f.read().strip()

                if track_id not in data:
                    data[track_id] = {}
                    data[track_id].update(parsed)

                # Update key from file (overwrite CSV key if present)
                data[track_id]['key_txt'] = key

    # Find audio files
    audio_dir = beatport_dir / "audio"
    if audio_dir.exists():
        for audio_file in audio_dir.glob("*.mp3"):
            parsed = parse_beatport_filename(audio_file.name)
            if parsed:
                track_id = parsed['id']

                if track_id not in data:
                    data[track_id] = {}
                    data[track_id].update(parsed)

                data[track_id]['audio_file_beatport'] = str(audio_file)

    return data


def consolidate_datasets(base_dir):
    """Consolidate all datasets into a single data structure."""
    giantsteps_key_dir = base_dir / "giantsteps-key-dataset"
    giantsteps_tempo_dir = base_dir / "giantsteps-tempo-dataset"
    beatport_dir = base_dir / "ZenodoBeatportEDMKeyDataset"

    print("Reading giantsteps-key-dataset...")
    key_data = read_giantsteps_key_dataset(giantsteps_key_dir)
    print(f"  Found {len(key_data)} tracks")

    print("Reading giantsteps-tempo-dataset...")
    tempo_data = read_giantsteps_tempo_dataset(giantsteps_tempo_dir)
    print(f"  Found {len(tempo_data)} tracks")

    print("Reading ZenodoBeatportEDMKeyDataset...")
    beatport_data = read_beatport_dataset(beatport_dir)
    print(f"  Found {len(beatport_data)} tracks")

    # Merge all data by ID
    all_ids = set(key_data.keys()) | set(tempo_data.keys()) | set(beatport_data.keys())
    print(f"\nTotal unique track IDs: {len(all_ids)}")

    consolidated = {}
    for track_id in all_ids:
        track = {
            'id': track_id,
            'artist': '',
            'title': '',
            'mix': '',
            'album': '',
            'key': '',
            'bpm': '',
            'genre': '',
            'datasets': [],
            'audio_file': None,
        }

        # Merge data from each dataset
        # Start with giantsteps data (key dataset may have artist/title from Excel)
        if track_id in key_data:
            track['datasets'].append('giantsteps-key')
            kd = key_data[track_id]
            track['key'] = kd.get('key', track['key'])
            track['genre'] = kd.get('genre', track['genre'])
            track['artist'] = kd.get('artist', track['artist'])
            track['title'] = kd.get('title', track['title'])
            track['mix'] = kd.get('mix', track['mix'])
            if not track['audio_file'] and 'audio_file_key' in kd:
                track['audio_file'] = kd['audio_file_key']

        if track_id in tempo_data:
            track['datasets'].append('giantsteps-tempo')
            track['bpm'] = tempo_data[track_id].get('bpm', track['bpm'])
            if not track['audio_file'] and 'audio_file_tempo' in tempo_data[track_id]:
                track['audio_file'] = tempo_data[track_id]['audio_file_tempo']

        # Beatport data overrides giantsteps for artist/title/album (more complete)
        if track_id in beatport_data:
            track['datasets'].append('beatport-edm')
            bp = beatport_data[track_id]
            # Only override if beatport has non-empty values
            if bp.get('artist'):
                track['artist'] = bp['artist']
            if bp.get('title'):
                track['title'] = bp['title']
            if bp.get('mix'):
                track['mix'] = bp['mix']
            if bp.get('album'):
                track['album'] = bp['album']
            if bp.get('genre'):
                track['genre'] = bp['genre']
            # Prefer key from txt file, fall back to CSV, then existing
            track['key'] = bp.get('key_txt', bp.get('key', track['key']))
            if not track['audio_file'] and 'audio_file_beatport' in bp:
                track['audio_file'] = bp['audio_file_beatport']

        track['datasets'] = ', '.join(track['datasets'])
        consolidated[track_id] = track

    return consolidated


def copy_audio_files(consolidated_data, output_audio_dir):
    """Copy audio files to consolidated directory."""
    print(f"\nCreating output directory: {output_audio_dir}")
    output_audio_dir.mkdir(exist_ok=True)

    copied = 0
    missing = 0

    for track_id, track in consolidated_data.items():
        if track['audio_file'] and os.path.exists(track['audio_file']):
            src = Path(track['audio_file'])

            # Create a better filename if we have metadata
            if track['artist'] and track['title']:
                if track['mix']:
                    filename = f"{track_id} {track['artist']} - {track['title']} ({track['mix']}).mp3"
                else:
                    filename = f"{track_id} {track['artist']} - {track['title']}.mp3"
            else:
                filename = f"{track_id}.mp3"

            # Sanitize filename
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

            dst = output_audio_dir / filename

            try:
                shutil.copy2(src, dst)
                track['output_filename'] = filename
                copied += 1
                if copied % 100 == 0:
                    print(f"  Copied {copied} files...")
            except Exception as e:
                print(f"  Error copying {src}: {e}")
                missing += 1
        else:
            missing += 1

    print(f"Copied {copied} audio files")
    print(f"Missing {missing} audio files")


def write_csv(consolidated_data, output_csv):
    """Write consolidated data to CSV."""
    print(f"\nWriting CSV: {output_csv}")

    fieldnames = [
        'id',
        'artist',
        'title',
        'mix',
        'album',
        'key',
        'bpm',
        'genre',
        'datasets',
        'output_filename'
    ]

    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for track_id in sorted(consolidated_data.keys(), key=lambda x: int(x)):
            track = consolidated_data[track_id]
            writer.writerow({
                'id': track['id'],
                'artist': track['artist'],
                'title': track['title'],
                'mix': track['mix'],
                'album': track['album'],
                'key': track['key'],
                'bpm': track['bpm'],
                'genre': track['genre'],
                'datasets': track['datasets'],
                'output_filename': track.get('output_filename', ''),
            })

    print(f"CSV written with {len(consolidated_data)} tracks")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Consolidate audio datasets from multiple sources.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                         # Use script directory
  %(prog)s --path /path/to/data    # Use custom directory
        """
    )

    parser.add_argument(
        '--path',
        type=str,
        default=None,
        help='Base directory containing the datasets (default: script directory)'
    )

    return parser.parse_args()


def main():
    # Parse arguments
    args = parse_arguments()

    # Determine base directory
    if args.path:
        base_dir = Path(args.path).resolve()
    else:
        # Use the directory where this script is located
        base_dir = Path(__file__).parent.resolve()

    output_audio_dir = base_dir / "consolidated_audio"
    output_csv = base_dir / "consolidated_dataset.csv"

    print("=" * 70)
    print("Audio Dataset Consolidation Script")
    print("=" * 70)
    print(f"Base directory: {base_dir}")
    print()

    # Consolidate metadata
    consolidated_data = consolidate_datasets(base_dir)

    # Copy audio files
    copy_audio_files(consolidated_data, output_audio_dir)

    # Write CSV
    write_csv(consolidated_data, output_csv)

    print("\n" + "=" * 70)
    print("Consolidation complete!")
    print(f"Audio files: {output_audio_dir}")
    print(f"Metadata CSV: {output_csv}")
    print("=" * 70)


if __name__ == '__main__':
    main()
