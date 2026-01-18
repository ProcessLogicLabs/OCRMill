#!/usr/bin/env python3
"""
Generate wizard images for OCRMill Inno Setup installer.
Creates the large wizard image (164x314) and small wizard image (55x55).
"""

import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Please install Pillow: pip install Pillow")
    exit(1)

OUTPUT_DIR = Path(__file__).parent

# Colors
TEAL = (95, 158, 160)
TEAL_LIGHT = (122, 184, 186)
PURPLE = (107, 91, 149)
PURPLE_LIGHT = (139, 123, 181)
WHITE = (255, 255, 255)
DARK_BG = (35, 40, 45)


def draw_mill_wheel(draw, cx, cy, radius, angle=0):
    """Draw the OCRMill mill wheel."""
    # Wheel background
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=TEAL_LIGHT, outline=(74, 138, 140), width=max(1, radius // 15)
    )

    # Spokes
    spoke_len = radius - 3
    for i in range(4):
        spoke_angle = math.radians(angle + i * 90)
        x2 = int(cx + spoke_len * math.cos(spoke_angle))
        y2 = int(cy + spoke_len * math.sin(spoke_angle))
        width = max(2, radius // 8)
        if i >= 2:
            width = max(1, width - 1)
        draw.line([(cx, cy), (x2, y2)], fill=WHITE, width=width)

    # Diagonal spokes
    for i in range(4):
        spoke_angle = math.radians(angle + 45 + i * 90)
        x2 = int(cx + (spoke_len * 0.8) * math.cos(spoke_angle))
        y2 = int(cy + (spoke_len * 0.8) * math.sin(spoke_angle))
        draw.line([(cx, cy), (x2, y2)], fill=(255, 255, 255, 180), width=max(1, radius // 12))

    # Center hub
    hub_radius = max(3, radius // 4)
    draw.ellipse(
        [cx - hub_radius, cy - hub_radius, cx + hub_radius, cy + hub_radius],
        fill=PURPLE_LIGHT, outline=(90, 74, 133), width=1
    )

    # White center
    center_r = max(1, hub_radius // 2)
    draw.ellipse([cx - center_r, cy - center_r, cx + center_r, cy + center_r], fill=WHITE)


def create_wizard_large():
    """Create the large wizard image (164x314 pixels)."""
    width, height = 164, 314
    img = Image.new('RGB', (width, height), DARK_BG)
    draw = ImageDraw.Draw(img)

    # Gradient background
    for y in range(height):
        ratio = y / height
        r = int(35 + ratio * 15)
        g = int(40 + ratio * 15)
        b = int(45 + ratio * 20)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Draw orbiting characters
    try:
        font = ImageFont.truetype("segoeui.ttf", 14)
        title_font = ImageFont.truetype("segoeuib.ttf", 18)
    except:
        try:
            font = ImageFont.truetype("arial.ttf", 14)
            title_font = ImageFont.truetype("arialbd.ttf", 18)
        except:
            font = ImageFont.load_default()
            title_font = font

    cx, cy = width // 2, 120
    chars = ['A', '0', '1', 'B', '0', 'C', '1', 'D']

    # Draw characters in orbit
    for i, char in enumerate(chars):
        angle = math.radians(i * 360 / len(chars) - 90)
        x = int(cx + 55 * math.cos(angle))
        y = int(cy + 55 * math.sin(angle))
        color = PURPLE if i % 2 == 0 else TEAL
        draw.text((x - 5, y - 7), char, font=font, fill=color)

    # Draw circular arrows (simplified)
    arrow_radius = 40
    for i in range(4):
        start = i * 90 + 10
        end = start + 70
        # Draw arc approximation
        for j in range(8):
            a1 = math.radians(start + j * (end - start) / 8)
            a2 = math.radians(start + (j + 1) * (end - start) / 8)
            x1 = int(cx + arrow_radius * math.cos(a1))
            y1 = int(cy + arrow_radius * math.sin(a1))
            x2 = int(cx + arrow_radius * math.cos(a2))
            y2 = int(cy + arrow_radius * math.sin(a2))
            color = PURPLE if i % 2 == 0 else TEAL
            draw.line([(x1, y1), (x2, y2)], fill=color, width=2)

    # Draw mill wheel
    draw_mill_wheel(draw, cx, cy, 28)

    # Draw "OCRMill" text
    text_y = 200
    draw.text((width // 2 - 40, text_y), "OCRMill", font=title_font, fill=WHITE)

    # Draw version
    draw.text((width // 2 - 25, text_y + 30), "Invoice", font=font, fill=TEAL_LIGHT)
    draw.text((width // 2 - 35, text_y + 48), "Processing", font=font, fill=TEAL_LIGHT)
    draw.text((width // 2 - 20, text_y + 66), "Suite", font=font, fill=TEAL_LIGHT)

    # Save
    output_path = OUTPUT_DIR / "wizard_image.bmp"
    img.save(output_path, "BMP")
    print(f"Created: {output_path}")


def create_wizard_small():
    """Create the small wizard image (55x55 pixels)."""
    size = 55
    img = Image.new('RGB', (size, size), DARK_BG)
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2

    # Draw mill wheel
    draw_mill_wheel(draw, cx, cy, 22)

    # Save
    output_path = OUTPUT_DIR / "wizard_small.bmp"
    img.save(output_path, "BMP")
    print(f"Created: {output_path}")


def main():
    """Generate all wizard images."""
    print("Generating Inno Setup wizard images...")
    create_wizard_large()
    create_wizard_small()
    print("Done!")


if __name__ == "__main__":
    main()
