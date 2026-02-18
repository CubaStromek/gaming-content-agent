#!/usr/bin/env python3
"""
GAMEfo.cz Facebook Post Image Generator

Layers (bottom to top):
  1. Background (FB_LAYOUT_pozadi.png)
  2. Thumbnail image
  3. Logo (gamefo_logo_transparent.png) — overlaps top of thumbnail
  4. Separator line (FB_LAYOUT_cara.png) — overlaps bottom of thumbnail
  5. Title + subtitle text below separator

Usage:
    python3 generate_fb_post.py -t photo.jpg --title "NÁZEV HRY" --subtitle "Zajímavý titulek"
"""

import argparse
import os
from PIL import Image, ImageDraw, ImageFont

# --- Paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BG_PATH = os.path.join(SCRIPT_DIR, "FB_LAYOUT_pozadi.png")
LOGO_PATH = os.path.join(SCRIPT_DIR, "gamefo_logo_transparent.png")
CARA_PATH = os.path.join(SCRIPT_DIR, "FB_LAYOUT_cara.png")
FONT_PATH = os.path.expanduser("~/Library/Fonts/Digitalt.ttf")

# --- Layout (canvas 940x788) ---
CANVAS_W = 940
CANVAS_H = 788

# Thumbnail area (between guide lines: top y=103, bottom y=762)
THUMB_MARGIN_X = 55
THUMB_TOP = 115  # below top guide line
THUMB_BOTTOM = 510  # well above separator area
THUMB_W = CANVAS_W - (THUMB_MARGIN_X * 2)  # 830px
THUMB_H = THUMB_BOTTOM - THUMB_TOP  # 480px

# Logo: centered at top, partially overlapping thumbnail
LOGO_DISPLAY_W = 140  # width on canvas
LOGO_TOP_Y = 5

# Separator: centered on bottom edge of thumbnail
CARA_DISPLAY_W = 760  # width on canvas
CARA_CENTER_Y = THUMB_BOTTOM + 5  # slightly below thumbnail edge

# Text
TEXT_START_Y = CARA_CENTER_Y + 35
TEXT_PADDING_X = 40  # padding from canvas edges
TEXT_MAX_W = CANVAS_W - (TEXT_PADDING_X * 2)  # 860px
TEXT_BOTTOM_Y = CANVAS_H - 15  # max Y for text
TITLE_FONT_SIZE = 52
TITLE_MIN_FONT_SIZE = 30
SUBTITLE_FONT_SIZE = 36
SUBTITLE_MIN_FONT_SIZE = 22
TITLE_COLOR = (255, 255, 255)
SUBTITLE_COLOR = (255, 230, 0)


def load_and_scale_preserving_alpha(path, target_width):
    """Load a transparent PNG and scale it proportionally."""
    img = Image.open(path).convert("RGBA")
    # Crop to content bounding box first
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    ratio = target_width / img.width
    new_h = int(img.height * ratio)
    return img.resize((target_width, new_h), Image.LANCZOS)


def _wrap_text(draw, text, font, max_width):
    """Zalomí text na řádky, které se vejdou do max_width."""
    words = text.split()
    if not words:
        return []
    lines = []
    current = words[0]
    for word in words[1:]:
        test = current + " " + word
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            current = test
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_wrapped_text(draw, text, font_path, start_size, min_size, max_width, max_height, start_y, color):
    """
    Vykreslí text se zalomením. Pokud se nevejde, zmenšuje font.
    Vrací Y pozici pod posledním řádkem.
    """
    size = start_size
    while size >= min_size:
        try:
            font = ImageFont.truetype(font_path, size)
        except OSError:
            font = ImageFont.load_default()
            break

        lines = _wrap_text(draw, text, font, max_width)
        line_height = size + 6
        total_height = len(lines) * line_height

        if start_y + total_height <= max_height:
            break
        size -= 2
    else:
        # I s minimálním fontem se nevejde — použij minimum
        try:
            font = ImageFont.truetype(font_path, min_size)
        except OSError:
            font = ImageFont.load_default()
        lines = _wrap_text(draw, text, font, max_width)
        line_height = min_size + 6

    y = start_y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        lx = (CANVAS_W - lw) // 2
        # Shadow
        draw.text((lx + 2, y + 2), line, fill=(0, 0, 0), font=font)
        draw.text((lx, y), line, fill=color, font=font)
        y += line_height

    return y


def generate_fb_post(thumbnail_path, title, subtitle="", output_path=None):
    """Generate a Facebook post image."""

    # LAYER 1: Background
    canvas = Image.open(BG_PATH).convert("RGBA")

    # LAYER 2: Thumbnail (cover fit + center crop)
    thumb = Image.open(thumbnail_path).convert("RGB")
    thumb_ratio = thumb.width / thumb.height
    target_ratio = THUMB_W / THUMB_H

    if thumb_ratio > target_ratio:
        new_h = THUMB_H
        new_w = int(new_h * thumb_ratio)
    else:
        new_w = THUMB_W
        new_h = int(new_w / thumb_ratio)

    thumb = thumb.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - THUMB_W) // 2
    top = (new_h - THUMB_H) // 2
    thumb = thumb.crop((left, top, left + THUMB_W, top + THUMB_H))

    canvas.paste(thumb, (THUMB_MARGIN_X, THUMB_TOP))

    # LAYER 3: Logo (transparent, overlaps top of thumbnail)
    logo = load_and_scale_preserving_alpha(LOGO_PATH, LOGO_DISPLAY_W)
    logo_x = (CANVAS_W - logo.width) // 2
    canvas.paste(logo, (logo_x, LOGO_TOP_Y), logo)

    # LAYER 4: Separator line (transparent, overlaps bottom of thumbnail)
    cara = load_and_scale_preserving_alpha(CARA_PATH, CARA_DISPLAY_W)
    cara_x = (CANVAS_W - cara.width) // 2
    cara_y = CARA_CENTER_Y - cara.height // 2
    canvas.paste(cara, (cara_x, cara_y), cara)

    # LAYER 5: Text (with wrapping)
    draw = ImageDraw.Draw(canvas)
    next_y = TEXT_START_Y

    # Title (game name, white, centered, wrapped)
    if title:
        next_y = _draw_wrapped_text(
            draw, title.upper(), FONT_PATH,
            TITLE_FONT_SIZE, TITLE_MIN_FONT_SIZE,
            TEXT_MAX_W, TEXT_BOTTOM_Y, TEXT_START_Y, TITLE_COLOR,
        )
        next_y += 8  # gap between title and subtitle

    # Subtitle (article headline, yellow, centered, wrapped)
    if subtitle:
        _draw_wrapped_text(
            draw, subtitle.upper(), FONT_PATH,
            SUBTITLE_FONT_SIZE, SUBTITLE_MIN_FONT_SIZE,
            TEXT_MAX_W, TEXT_BOTTOM_Y, next_y, SUBTITLE_COLOR,
        )

    # Save
    if output_path is None:
        base = os.path.splitext(os.path.basename(thumbnail_path))[0]
        output_path = os.path.join(SCRIPT_DIR, f"fb_post_{base}.png")

    canvas.save(output_path, "PNG")
    print(f"FB post vygenerován: {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GAMEfo.cz FB Post Generator")
    parser.add_argument("--thumbnail", "-t", required=True, help="Thumbnail image path")
    parser.add_argument("--title", required=True, help="Game name (white text)")
    parser.add_argument("--subtitle", "-s", default="", help="Article headline (yellow text)")
    parser.add_argument("--output", "-o", default=None, help="Output file path")

    args = parser.parse_args()
    generate_fb_post(args.thumbnail, args.title, args.subtitle, args.output)
