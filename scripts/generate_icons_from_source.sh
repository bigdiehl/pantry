#!/bin/bash

# Generate PWA icons from a source image
# Requires ImageMagick (install with: sudo apt install imagemagick)
# Usage: Place your source image as icon-source.png in web/static/icons/
#        then run this script

ICONS_DIR="$(dirname "$0")/../web/static/icons"
SOURCE="${ICONS_DIR}/icon-source.png"

cd "${ICONS_DIR}" || exit 1

# Check if source image exists
if [ ! -f "icon-source.png" ]; then
    echo "Error: icon-source.png not found in ${ICONS_DIR}"
    echo ""
    echo "Please create a square source image (512x512 or larger) and save it as:"
    echo "  ${ICONS_DIR}/icon-source.png"
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Check if ImageMagick is installed
if ! command -v convert &> /dev/null; then
    echo "Error: ImageMagick is not installed."
    echo "Install with: sudo apt install imagemagick"
    exit 1
fi

echo "Generating icons from icon-source.png..."

# Icon sizes needed for PWA
SIZES=(72 96 128 144 152 192 384 512)

# Generate each icon size
for SIZE in "${SIZES[@]}"; do
    echo "Generating icon-${SIZE}.png..."
    convert icon-source.png -resize "${SIZE}x${SIZE}" "icon-${SIZE}.png"
done

echo "Done! Generated ${#SIZES[@]} icon files from source."
