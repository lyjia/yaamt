#!/usr/bin/env bash
#
# Build a macOS .dmg installer from the PyInstaller-built YAAMT.app.
#
# Invoked by build.py's _create_macos_installer. The .app bundle itself
# (Info.plist, icon, ad-hoc signature) is produced by the BUNDLE step in
# yaamt.spec; this script only lays it out in a drag-to-Applications
# disk image with create-dmg.
#
# Usage:
#   build_dmg.sh --app <YAAMT.app> --dmg <output.dmg> --volname <name>

set -euo pipefail

APP=""
DMG_PATH=""
VOLNAME=""

while [ $# -gt 0 ]; do
    case "$1" in
        --app)     APP="$2";      shift 2 ;;
        --dmg)     DMG_PATH="$2"; shift 2 ;;
        --volname) VOLNAME="$2";  shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

for v in APP DMG_PATH VOLNAME; do
    if [ -z "${!v}" ]; then
        echo "Missing required argument for $v" >&2
        exit 2
    fi
done

if [ ! -d "$APP" ]; then
    echo "App bundle not found: $APP" >&2
    exit 1
fi

APP_NAME="$(basename "$APP")"
mkdir -p "$(dirname "$DMG_PATH")"
rm -f "$DMG_PATH"

# create-dmg copies the *contents* of its source folder into the volume,
# so stage the .app alone in a scratch directory.
STAGE_DIR="$(mktemp -d -t yaamt-dmg.XXXXXX)"
trap 'rm -rf "$STAGE_DIR"' EXIT
cp -R "$APP" "$STAGE_DIR/"

echo "Building $(basename "$DMG_PATH")..."
create-dmg \
    --volname "$VOLNAME" \
    --window-size 540 360 \
    --icon-size 96 \
    --icon "$APP_NAME" 140 180 \
    --app-drop-link 400 180 \
    --no-internet-enable \
    "$DMG_PATH" \
    "$STAGE_DIR"

echo "Created: $DMG_PATH"
