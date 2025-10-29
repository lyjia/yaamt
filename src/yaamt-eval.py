#!/usr/bin/env python3
"""
Analyzer Evaluation CLI Tool

Compares analyzer outputs against hand-reviewed reference data and calculates
MIREX scores for key detection and custom scores for BPM detection.
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import pandas as pd

# Add src directory to path for imports (since we're in src/)
sys.path.insert(0, str(Path(__file__).parent))

from util.eval_scoring import (
    calculate_key_relationship,
    calculate_bpm_score,
    KeyRelationship,
    BPMCategory
)
from util.diatonic_key import parse_key, format_key, NotationFormat


class EvaluationResult:
    """Holds evaluation results for a single file."""

    def __init__(self, filename: str):
        self.filename = filename
        self.reference_value: Optional[str] = None
        self.analyzed_value: Optional[str] = None
        self.score: float = 0.0
        self.category: str = ""
        self.notes: str = ""
        self.skipped: bool = False


class AnalyzerEvaluation:
    """Holds all evaluation results for a single analyzer."""

    def __init__(self, analyzer_name: str, criteria: str):
        self.analyzer_name = analyzer_name
        self.criteria = criteria
        self.results: List[EvaluationResult] = []
        self.total_files = 0
        self.scored_files = 0
        self.skipped_files = 0
        self.total_score = 0.0

        # Category counts (for key evaluation)
        self.same_key_count = 0
        self.perfect_fifth_count = 0
        self.relative_count = 0
        self.parallel_count = 0
        self.other_count = 0

    def add_result(self, result: EvaluationResult):
        """Add a result and update statistics."""
        self.results.append(result)
        self.total_files += 1

        if result.skipped:
            self.skipped_files += 1
        else:
            self.scored_files += 1
            self.total_score += result.score

            # Update category counts for key evaluation
            if self.criteria == "key":
                if result.category == KeyRelationship.SAME_KEY.value:
                    self.same_key_count += 1
                elif result.category == KeyRelationship.PERFECT_FIFTH.value:
                    self.perfect_fifth_count += 1
                elif result.category == KeyRelationship.RELATIVE_MAJOR_MINOR.value:
                    self.relative_count += 1
                elif result.category == KeyRelationship.PARALLEL_MAJOR_MINOR.value:
                    self.parallel_count += 1
                elif result.category == KeyRelationship.OTHER.value:
                    self.other_count += 1

    @property
    def max_score(self) -> float:
        """Maximum possible score."""
        return float(self.scored_files)

    @property
    def average_score(self) -> float:
        """Average score (total_score / max_score)."""
        if self.max_score == 0:
            return 0.0
        return self.total_score / self.max_score


def load_reference_data(reference_path: Path, criteria: str) -> pd.DataFrame:
    """
    Load and validate reference CSV data.

    Args:
        reference_path: Path to reference CSV file
        criteria: Either "key" or "bpm"

    Returns:
        DataFrame with reference data
    """
    try:
        df = pd.read_csv(reference_path)
    except Exception as e:
        print(f"Error loading reference file: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate required columns
    required_cols = ['output_filename', criteria]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error: Reference CSV missing required columns: {missing_cols}", file=sys.stderr)
        sys.exit(1)

    return df


def load_analysis_data(analysis_paths: List[Path], criteria: str) -> Dict[str, pd.DataFrame]:
    """
    Load and validate analysis CSV data.

    Args:
        analysis_paths: List of paths to analysis CSV files
        criteria: Either "key" or "bpm"

    Returns:
        Dictionary mapping analyzer names to their DataFrames
    """
    analysis_data = {}

    for path in analysis_paths:
        try:
            df = pd.read_csv(path)
        except Exception as e:
            print(f"Warning: Error loading analysis file {path}: {e}", file=sys.stderr)
            continue

        # Validate required columns
        if 'filename' not in df.columns or 'status' not in df.columns:
            print(f"Warning: Analysis CSV {path} missing required columns (filename, status)", file=sys.stderr)
            continue

        # Find analyzer column (format: AnalyzerName_field)
        analyzer_col = None
        for col in df.columns:
            if col.endswith(f'_{criteria}'):
                analyzer_col = col
                break

        if analyzer_col is None:
            print(f"Warning: Analysis CSV {path} missing column for criteria '{criteria}'", file=sys.stderr)
            continue

        # Extract analyzer name
        analyzer_name = analyzer_col.replace(f'_{criteria}', '')

        # Store with analyzer name as key
        analysis_data[analyzer_name] = df
        print(f"Loaded analyzer: {analyzer_name}")

    if not analysis_data:
        print("Error: No valid analysis files loaded", file=sys.stderr)
        sys.exit(1)

    return analysis_data


def evaluate_key(ref_key_str: str, analyzed_key_str: str) -> Tuple[float, str, str, str, str]:
    """
    Evaluate key detection for a single file.

    Args:
        ref_key_str: Reference key string
        analyzed_key_str: Analyzed key string

    Returns:
        Tuple of (score, category, notes, ref_standard, analyzed_standard)
        - ref_standard: Reference key in Standard notation
        - analyzed_standard: Analyzed key in Standard notation
    """
    # Parse reference key
    ref_parsed = parse_key(ref_key_str)
    if ref_parsed is None:
        return (0.0, KeyRelationship.OTHER.value, f"Failed to parse reference key: '{ref_key_str}'", ref_key_str, "")

    ref_pitch_class, ref_is_minor = ref_parsed
    ref_standard = format_key(ref_pitch_class, ref_is_minor, NotationFormat.Standard)

    # Parse analyzed key
    analyzed_parsed = parse_key(analyzed_key_str)
    if analyzed_parsed is None:
        return (0.0, KeyRelationship.OTHER.value, f"Failed to parse analyzed key: '{analyzed_key_str}'", ref_standard, analyzed_key_str)

    analyzed_pitch_class, analyzed_is_minor = analyzed_parsed
    analyzed_standard = format_key(analyzed_pitch_class, analyzed_is_minor, NotationFormat.Standard)

    # Calculate score (returns enum)
    score, category_enum = calculate_key_relationship(
        ref_pitch_class, ref_is_minor,
        analyzed_pitch_class, analyzed_is_minor
    )

    # Convert enum to string for storage
    return (score, category_enum.value, "", ref_standard, analyzed_standard)


def evaluate_bpm(ref_bpm: float, analyzed_bpm: float) -> Tuple[float, str, str]:
    """
    Evaluate BPM detection for a single file.

    Args:
        ref_bpm: Reference BPM value
        analyzed_bpm: Analyzed BPM value

    Returns:
        Tuple of (score, category, notes)
    """
    # Calculate score (returns enum)
    score, category_enum = calculate_bpm_score(ref_bpm, analyzed_bpm)

    delta = abs(ref_bpm - analyzed_bpm)
    notes = f"Delta: {delta:.2f} BPM"

    # Convert enum to string for storage
    return (score, category_enum.value, notes)


def evaluate_analyzer(
    analyzer_name: str,
    analysis_df: pd.DataFrame,
    reference_df: pd.DataFrame,
    criteria: str,
    audio_dir: Optional[Path]
) -> AnalyzerEvaluation:
    """
    Evaluate a single analyzer against reference data.

    Args:
        analyzer_name: Name of the analyzer
        analysis_df: DataFrame with analysis results
        reference_df: DataFrame with reference data
        criteria: Either "key" or "bpm"
        audio_dir: Directory containing audio files (optional, for validation)

    Returns:
        AnalyzerEvaluation object with results
    """
    evaluation = AnalyzerEvaluation(analyzer_name, criteria)

    # Create lookup dict for reference data
    ref_lookup = {}
    for _, row in reference_df.iterrows():
        filename = row['output_filename']
        ref_value = row.get(criteria)

        # Skip if reference value is missing or invalid
        if pd.isna(ref_value) or (isinstance(ref_value, str) and not ref_value.strip()):
            print(f"Warning: Skipping {filename} - missing reference {criteria}", file=sys.stderr)
            continue

        ref_lookup[filename] = ref_value

    # Iterate through analysis results
    analyzer_col = f"{analyzer_name}_{criteria}"

    for _, row in analysis_df.iterrows():
        # Extract filename (strip directory)
        full_path = row['filename']
        filename = os.path.basename(full_path)

        result = EvaluationResult(filename)

        # Check if file is in reference data
        if filename not in ref_lookup:
            result.skipped = True
            result.notes = "File not in reference dataset"
            evaluation.add_result(result)
            continue

        # Check if audio file exists (if audio_dir provided)
        if audio_dir:
            audio_path = audio_dir / filename
            if not audio_path.exists():
                result.skipped = True
                result.notes = "Audio file not found in audio directory"
                evaluation.add_result(result)
                continue

        # Get reference value
        ref_value = ref_lookup[filename]

        # Get analyzed value
        status = row.get('status', '')
        analyzed_value = row.get(analyzer_col)

        # Check if analysis succeeded
        if status != 'success' or pd.isna(analyzed_value) or \
           (isinstance(analyzed_value, str) and not analyzed_value.strip()):
            result.analyzed_value = ""
            result.score = 0.0
            # Use appropriate default category based on criteria
            if criteria == "key":
                result.category = KeyRelationship.OTHER.value
                # For key, still try to format reference in Standard notation if possible
                ref_parsed = parse_key(str(ref_value))
                if ref_parsed:
                    ref_pitch_class, ref_is_minor = ref_parsed
                    result.reference_value = format_key(ref_pitch_class, ref_is_minor, NotationFormat.Standard)
                else:
                    result.reference_value = str(ref_value)
            else:
                result.category = BPMCategory.OTHER.value
                result.reference_value = str(ref_value)
            result.notes = f"Analysis failed or missing (status: {status})"
            evaluation.add_result(result)
            continue

        # Evaluate based on criteria
        if criteria == "key":
            score, category, notes, ref_standard, analyzed_standard = evaluate_key(str(ref_value), str(analyzed_value))
            result.reference_value = ref_standard
            result.analyzed_value = analyzed_standard
        else:  # bpm
            result.reference_value = str(ref_value)
            result.analyzed_value = str(analyzed_value)
            try:
                ref_bpm = float(ref_value)
                analyzed_bpm = float(analyzed_value)
                score, category, notes = evaluate_bpm(ref_bpm, analyzed_bpm)
            except ValueError as e:
                score = 0.0
                category = "other"
                notes = f"Failed to parse BPM values: {e}"

        result.score = score
        result.category = category
        result.notes = notes

        evaluation.add_result(result)

    return evaluation


def write_summary_csv(
    evaluations: List[AnalyzerEvaluation],
    output_dir: Path,
    criteria: str
) -> Path:
    """
    Write combined summary CSV for all analyzers.

    Args:
        evaluations: List of AnalyzerEvaluation objects
        output_dir: Directory to write output file
        criteria: Either "key" or "bpm"

    Returns:
        Path to written CSV file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"eval_summary_{criteria}_{timestamp}.csv"

    # Build summary data
    summary_data = []
    for eval in evaluations:
        row = {
            'analyzer_name': eval.analyzer_name,
            'total_files': eval.total_files,
            'scored_files': eval.scored_files,
            'skipped_files': eval.skipped_files,
            'total_score': f"{eval.total_score:.2f}",
            'max_score': f"{eval.max_score:.2f}",
            'average_score': f"{eval.average_score:.4f}",
        }

        # Add category counts for key evaluation
        if criteria == "key":
            row.update({
                'same_key_count': eval.same_key_count,
                'perfect_fifth_count': eval.perfect_fifth_count,
                'relative_count': eval.relative_count,
                'parallel_count': eval.parallel_count,
                'other_count': eval.other_count,
            })

        summary_data.append(row)

    # Write CSV
    df = pd.DataFrame(summary_data)
    df.to_csv(output_path, index=False)

    return output_path


def write_detailed_csv(
    evaluation: AnalyzerEvaluation,
    output_dir: Path,
    criteria: str
) -> Path:
    """
    Write detailed per-analyzer CSV.

    Args:
        evaluation: AnalyzerEvaluation object
        output_dir: Directory to write output file
        criteria: Either "key" or "bpm"

    Returns:
        Path to written CSV file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    analyzer_safe = evaluation.analyzer_name.replace(' ', '_')
    output_path = output_dir / f"eval_{analyzer_safe}_{criteria}_{timestamp}.csv"

    # Build detailed data
    detailed_data = []
    for result in evaluation.results:
        if criteria == "key":
            row = {
                'filename': result.filename,
                'reference_key': result.reference_value or "",
                'analyzed_key': result.analyzed_value or "",
                'score': f"{result.score:.2f}",
                'category': result.category,
                'notes': result.notes,
            }
        else:  # bpm
            row = {
                'filename': result.filename,
                'reference_bpm': result.reference_value or "",
                'analyzed_bpm': result.analyzed_value or "",
                'score': f"{result.score:.2f}",
                'category': result.category,
                'notes': result.notes,
            }

        detailed_data.append(row)

    # Write CSV
    df = pd.DataFrame(detailed_data)
    df.to_csv(output_path, index=False)

    return output_path


def main():
    """Main entry point for evaluation script."""
    parser = argparse.ArgumentParser(
        description="Evaluate analyzer performance against reference data"
    )

    # Create subparsers for verb-based commands
    subparsers = parser.add_subparsers(dest='command', help='Evaluation criteria', required=True)

    # Common arguments for both commands
    common_args = {
        'audio-dir': {
            'type': Path,
            'help': 'Directory containing audio files (optional, for validation)'
        },
        'reference': {
            'type': Path,
            'required': True,
            'help': 'Reference CSV file (consolidated dataset format)'
        },
        'analysis': {
            'type': Path,
            'nargs': '+',
            'required': True,
            'help': 'Analysis result CSV file(s) (report format from CLI)'
        },
        'output-dir': {
            'type': Path,
            'default': Path.cwd(),
            'help': 'Directory to write result CSVs (default: current directory)'
        }
    }

    # ========================================================================
    # key command
    # ========================================================================
    key_parser = subparsers.add_parser('key', help='Evaluate key detection')
    for arg_name, arg_config in common_args.items():
        key_parser.add_argument(f'--{arg_name}', **arg_config)

    # ========================================================================
    # bpm command
    # ========================================================================
    bpm_parser = subparsers.add_parser('bpm', help='Evaluate BPM detection')
    for arg_name, arg_config in common_args.items():
        bpm_parser.add_argument(f'--{arg_name}', **arg_config)

    args = parser.parse_args()

    # Map command to criteria
    criteria = args.command

    # Get output_dir with underscore (since argparse converts hyphens)
    output_dir = getattr(args, 'output_dir', Path.cwd())

    # Validate paths
    if not args.reference.exists():
        print(f"Error: Reference file not found: {args.reference}", file=sys.stderr)
        sys.exit(1)

    for analysis_path in args.analysis:
        if not analysis_path.exists():
            print(f"Error: Analysis file not found: {analysis_path}", file=sys.stderr)
            sys.exit(1)

    audio_dir = getattr(args, 'audio_dir', None)
    if audio_dir and not audio_dir.is_dir():
        print(f"Error: Audio directory not found: {audio_dir}", file=sys.stderr)
        sys.exit(1)

    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    # Load data
    print(f"Loading reference data from: {args.reference}")
    reference_df = load_reference_data(args.reference, criteria)
    print(f"Loaded {len(reference_df)} reference entries")

    print(f"\nLoading analysis data...")
    analysis_data = load_analysis_data(args.analysis, criteria)

    # Evaluate each analyzer
    print(f"\nEvaluating analyzers for {criteria} detection")
    print("-" * 60)

    evaluations = []
    for analyzer_name, analysis_df in analysis_data.items():
        print(f"\nEvaluating: {analyzer_name}")
        evaluation = evaluate_analyzer(
            analyzer_name,
            analysis_df,
            reference_df,
            criteria,
            audio_dir
        )
        evaluations.append(evaluation)

        # Print summary
        print(f"  Total files: {evaluation.total_files}")
        print(f"  Scored files: {evaluation.scored_files}")
        print(f"  Skipped files: {evaluation.skipped_files}")
        print(f"  Total score: {evaluation.total_score:.2f}")
        print(f"  Max score: {evaluation.max_score:.2f}")
        print(f"  Average score: {evaluation.average_score:.4f}")

        if criteria == "key":
            print(f"  Same key: {evaluation.same_key_count}")
            print(f"  Perfect fifth: {evaluation.perfect_fifth_count}")
            print(f"  Relative major/minor: {evaluation.relative_count}")
            print(f"  Parallel major/minor: {evaluation.parallel_count}")
            print(f"  Other: {evaluation.other_count}")

    # Write output files
    print(f"\n{'-' * 60}")
    print("Writing output files...")

    summary_path = write_summary_csv(evaluations, output_dir, criteria)
    print(f"Summary CSV: {summary_path}")

    for evaluation in evaluations:
        detailed_path = write_detailed_csv(evaluation, output_dir, criteria)
        print(f"Detailed CSV ({evaluation.analyzer_name}): {detailed_path}")

    print("\nEvaluation complete!")


if __name__ == '__main__':
    main()
