#!/usr/bin/env python3
"""
Generate animated spinner GIF for OCRMill installer.
This creates a spinning mill wheel animation with orbiting characters.
"""

import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Please install Pillow: pip install Pillow")
    exit(1)

# Output path
OUTPUT_PATH = Path(__file__).parent / "spinner.gif"

# Animation parameters
SIZE = 200
CENTER = SIZE // 2
FRAMES = 36
DURATION = 50  # ms per frame

# Colors
TEAL = (95, 158, 160)
TEAL_LIGHT = (122, 184, 186)
PURPLE = (107, 91, 149)
PURPLE_LIGHT = (139, 123, 181)
WHITE = (255, 255, 255)
BG_COLOR = (30, 30, 30, 220)


def create_frame(angle, char_angle):
    """Create a single frame of the animation."""
    # Create RGBA image
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = CENTER, CENTER

    # Background circle
    draw.ellipse([cx - 90, cy - 90, cx + 90, cy + 90], fill=BG_COLOR)

    # Try to get a font, fall back to default
    try:
        font = ImageFont.truetype("segoeui.ttf", 16)
        small_font = ImageFont.truetype("segoeui.ttf", 12)
    except:
        try:
            font = ImageFont.truetype("arial.ttf", 16)
            small_font = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
            small_font = font

    # Draw orbiting characters
    chars = ['A', '0', '1', 'B', '0', 'C', '1', 'D']
    radius = 70
    for i, char in enumerate(chars):
        char_a = math.radians(char_angle + (i * 360 / len(chars)))
        x = int(cx + radius * math.cos(char_a))
        y = int(cy + radius * math.sin(char_a))
        color = PURPLE if i % 2 == 0 else TEAL
        draw.text((x - 6, y - 8), char, font=font, fill=color)

    # Second ring (opposite direction)
    chars2 = ['E', '1', 'F', '0', 'G', '1', 'H', '0']
    radius2 = 55
    for i, char in enumerate(chars2):
        char_a = math.radians(-char_angle * 1.2 + (i * 360 / len(chars2)))
        x = int(cx + radius2 * math.cos(char_a))
        y = int(cy + radius2 * math.sin(char_a))
        color = TEAL if i % 2 == 0 else PURPLE
        # Add some transparency via color lightening
        color = tuple(min(255, c + 50) for c in color)
        draw.text((x - 5, y - 6), char, font=small_font, fill=color)

    # Draw mill wheel (spinning)
    wheel_radius = 35

    # Wheel background
    draw.ellipse(
        [cx - wheel_radius, cy - wheel_radius, cx + wheel_radius, cy + wheel_radius],
        fill=TEAL_LIGHT, outline=(74, 138, 140), width=3
    )

    # Rotating spokes
    spoke_len = wheel_radius - 5
    for i in range(4):
        spoke_angle = math.radians(angle + i * 90)
        x1 = cx
        y1 = cy
        x2 = int(cx + spoke_len * math.cos(spoke_angle))
        y2 = int(cy + spoke_len * math.sin(spoke_angle))

        width = 5 if i < 2 else 3
        draw.line([(x1, y1), (x2, y2)], fill=WHITE, width=width)

    # Diagonal spokes (fainter)
    for i in range(4):
        spoke_angle = math.radians(angle + 45 + i * 90)
        x2 = int(cx + (spoke_len - 5) * math.cos(spoke_angle))
        y2 = int(cy + (spoke_len - 5) * math.sin(spoke_angle))
        draw.line([(cx, cy), (x2, y2)], fill=(255, 255, 255, 150), width=2)

    # Center hub (stationary)
    hub_radius = 12
    draw.ellipse(
        [cx - hub_radius, cy - hub_radius, cx + hub_radius, cy + hub_radius],
        fill=PURPLE_LIGHT, outline=(90, 74, 133), width=2
    )

    # White center
    draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=WHITE)

    return img


def main():
    """Generate the animated GIF."""
    print("Generating OCRMill spinner animation...")

    frames = []
    for i in range(FRAMES):
        wheel_angle = (i * 360 / FRAMES) * 1.5  # Wheel spins faster
        char_angle = i * 360 / FRAMES
        frame = create_frame(wheel_angle, char_angle)
        frames.append(frame)

    # Save as GIF
    frames[0].save(
        OUTPUT_PATH,
        save_all=True,
        append_images=frames[1:],
        duration=DURATION,
        loop=0,
        transparency=0,
        disposal=2
    )

    print(f"Saved: {OUTPUT_PATH}")
    print(f"Frames: {FRAMES}, Duration: {DURATION}ms/frame, Total: {FRAMES * DURATION}ms")


if __name__ == "__main__":
    main()
