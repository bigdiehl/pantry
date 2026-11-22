#!/bin/bash

# Generate placeholder PWA icons for the recipe app
# Requires ImageMagick (install with: sudo apt install imagemagick)

cd "$(dirname "$0")/../web/static/icons" || exit 1

echo "Generating placeholder icons..."

# Icon sizes needed for PWA
SIZES=(72 96 128 144 152 192 384 512)

# Background color (dark blue)
BG_COLOR="#2c3e50"

# Check if ImageMagick is installed
if ! command -v convert &> /dev/null; then
    echo "Error: ImageMagick is not installed."
    echo "Install with: sudo apt install imagemagick"
    exit 1
fi

# Generate each icon size
for SIZE in "${SIZES[@]}"; do
    echo "Generating icon-${SIZE}.png..."

    # Calculate font size (about half the icon size)
    FONT_SIZE=$((SIZE / 2))

    # Create icon with colored background and white "R" text
    convert -size "${SIZE}x${SIZE}" \
            xc:"${BG_COLOR}" \
            -pointsize "${FONT_SIZE}" \
            -fill white \
            -gravity center \
            -annotate +0+0 "R" \
            "icon-${SIZE}.png"
done

echo "Done! Generated ${#SIZES[@]} icon files."
echo ""
echo "To use a custom icon instead:"
echo "1. Create a square PNG image (512x512 or larger)"
echo "2. Save it as icon-source.png in this directory"
echo "3. Run: ./generate_icons_from_source.sh"
