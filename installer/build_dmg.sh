#!/usr/bin/env bash
#
# Build a macOS .dmg installer from PyInstaller output.
#
# Invoked by build.py's _create_macos_installer. Wraps the PyInstaller
# binary folder into a Yaamt.app bundle, ad-hoc codesigns it, and runs
# create-dmg to produce the final disk image.
#
# Usage:
#   build_dmg.sh --source <pyinstaller-output> --output <dist-dir> \
#                --version <ver> --arch <x64|arm64>

set -euo pipefail

SOURCE=""
OUTPUT=""
VERSION=""
ARCH=""

while [ $# -gt 0 ]; do
    case "$1" in
        --source)  SOURCE="$2";  shift 2 ;;
        --output)  OUTPUT="$2";  shift 2 ;;
        --version) VERSION="$2"; shift 2 ;;
        --arch)    ARCH="$2";    shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

for v in SOURCE OUTPUT VERSION ARCH; do
    if [ -z "${!v}" ]; then
        echo "Missing required argument: --${v,,}" >&2
        exit 2
    fi
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_DIR="$SCRIPT_DIR/yaamt-macos"
ICON="$SCRIPT_DIR/../resources/icons/app-icon-gui.icns"

if [ ! -d "$SOURCE" ]; then
    echo "PyInstaller output not found: $SOURCE" >&2
    exit 1
fi
if [ ! -f "$TEMPLATE_DIR/Info.plist.template" ]; then
    echo "Info.plist template not found: $TEMPLATE_DIR/Info.plist.template" >&2
    exit 1
fi

# CFBundleShortVersionString must be 'M.m.p' with no local-version suffix
# (App Store Connect rejects '+' in version strings; Gatekeeper tolerates
# but warns). Strip everything from '+' onward.
VERSION_SHORT="${VERSION%%+*}"

WORK_DIR="$(mktemp -d -t yaamt-dmg.XXXXXX)"
trap 'rm -rf "$WORK_DIR"' EXIT

APP_DIR="$WORK_DIR/Yaamt.app"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"

echo "Assembling Yaamt.app..."

# Copy binaries from PyInstaller output into the bundle.
cp -R "$SOURCE"/. "$APP_DIR/Contents/MacOS/"

# Drop in the icon if it exists (skip silently if not - icon is cosmetic).
if [ -f "$ICON" ]; then
    cp "$ICON" "$APP_DIR/Contents/Resources/app-icon-gui.icns"
fi

# Render Info.plist from the template.
sed \
    -e "s/%VERSION%/$VERSION/g" \
    -e "s/%VERSION_SHORT%/$VERSION_SHORT/g" \
    "$TEMPLATE_DIR/Info.plist.template" > "$APP_DIR/Contents/Info.plist"

# Ad-hoc codesign so Gatekeeper presents a warning rather than a flat
# refusal. Real Developer ID signing is deferred per the release plan.
echo "Ad-hoc codesigning..."
codesign --sign - --deep --force --timestamp=none "$APP_DIR"

DMG_NAME="yaamt-${VERSION}-macos-${ARCH}.dmg"
DMG_PATH="$OUTPUT/$DMG_NAME"
mkdir -p "$OUTPUT"
rm -f "$DMG_PATH"

echo "Building $DMG_NAME..."
create-dmg \
    --volname "YAAMT $VERSION_SHORT" \
    --window-size 540 360 \
    --icon-size 96 \
    --icon "Yaamt.app" 140 180 \
    --app-drop-link 400 180 \
    --no-internet-enable \
    "$DMG_PATH" \
    "$APP_DIR"

echo "Created: $DMG_PATH"
