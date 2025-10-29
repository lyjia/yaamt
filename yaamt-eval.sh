#!/bin/bash
# YAAMT Analyzer Evaluation launcher for Linux/macOS
# This script activates the virtual environment and runs the analyzer evaluator

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/src/yaamt-eval.py" "$@"
