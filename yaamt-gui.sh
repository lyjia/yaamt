#!/bin/bash
# YAAMT GUI launcher for Linux/macOS
# This script activates the virtual environment and runs the YAAMT GUI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/src/yaamt-gui.py" "$@"
