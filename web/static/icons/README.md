# App Icons

This directory contains app icons for the PWA (Progressive Web App).

## Required Sizes

- 72x72 pixels
- 96x96 pixels
- 128x128 pixels
- 144x144 pixels
- 152x152 pixels
- 192x192 pixels (minimum for Android)
- 384x384 pixels
- 512x512 pixels (Android splash screen)

## Generating Icons

If you have a source image, you can generate all sizes using ImageMagick:

```bash
cd web/static/icons

# From a source image (e.g., icon-source.png)
for size in 72 96 128 144 152 192 384 512; do
  convert icon-source.png -resize ${size}x${size} icon-${size}.png
done
```

## Icon Guidelines

- Square aspect ratio (1:1)
- PNG format recommended
- Solid background or transparent
- Simple, recognizable design
- Readable at small sizes

## Placeholder Icons

Until custom icons are created, you can use placeholder images or simple colored squares:

```bash
# Create placeholder icons (solid color)
for size in 72 96 128 144 152 192 384 512; do
  convert -size ${size}x${size} xc:#2c3e50 -pointsize $((size/2)) -fill white -gravity center -annotate +0+0 "R" icon-${size}.png
done
```

This creates dark blue squares with a white "R" in the center.
