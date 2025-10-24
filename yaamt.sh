#!/bin/bash
# YAAMT CLI launcher for Linux/macOS
# This script activates the virtual environment and runs the YAAMT CLI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/src/yaamt.py" "$@"
