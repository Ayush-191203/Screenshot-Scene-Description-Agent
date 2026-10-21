"""Caption band rendering: word-wraps text using real pixel measurement and
truncates (with an ellipsis) to respect both a character budget and a maximum
band-height fraction of the image.

Font fallback: if ``config.font_path`` cannot be loaded (missing file or
unsupported format), Pillow's built-in bitmap font
(:func:`PIL.ImageFont.load_default`) is used instead. That fallback font is a
single small fixed size and ignores ``font_size`` - this is logged by the
caller so operators know true-type rendering was unavailable.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

logger = logging.getLogger("scene_agent.imaging.caption")

_ELLIPSIS = "\u2026"


def _load_font(font_path: str, font_size: int) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, bool]:
    """Load the configured TrueType font, falling back to Pillow's default bitmap font."""
    try:
        if Path(font_path).is_file():
            return ImageFont.truetype(font_path, font_size), True
    except OSError:
        pass
    logger.warning("Caption font %r unavailable; falling back to default bitmap font.", font_path)
    return ImageFont.load_default(), False


def _truncate_to_length(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max(0, max_length - 1)].rstrip() + _ELLIPSIS


def _wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    """Word-wrap ``text`` so every line's rendered pixel width fits ``max_width``."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        width = draw.textlength(candidate, font=font)
        if width <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_lines_to_height(
    lines: list[str],
    line_height: float,
    padding_px: int,
    max_band_height: float,
) -> list[str]:
    """Drop trailing lines (adding an ellipsis to the last kept line) to respect max_band_height."""
    max_lines = max(1, int((max_band_height - 2 * padding_px) // line_height))
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    last = kept[-1].rstrip()
    if not last.endswith(_ELLIPSIS):
        last = last.rstrip(".,;: ") + _ELLIPSIS
    kept[-1] = last
    return kept


def render_caption_band(
    base_image: Image.Image,
    text: str,
    *,
    font_path: str,
    font_size: int,
    text_color: str,
    background_color: str,
    background_opacity_pct: float,
    padding_px: int,
    max_length: int,
    max_height_pct: float,
) -> Image.Image:
    """Append a caption band below ``base_image`` containing word-wrapped ``text``.

    Args:
        base_image: Source image (will not be mutated).
        text: Full description text (already the untrusted-content-safe LLM output).
        font_path: TrueType font path; falls back to a bitmap font if unusable.
        font_size: Point size for the TrueType font.
        text_color: Hex color for the caption text.
        background_color: Hex color for the caption band background.
        background_opacity_pct: Band background opacity, 0-100.
        padding_px: Padding around the wrapped text inside the band.
        max_length: Maximum characters kept in the image (longer text is ellipsized).
        max_height_pct: Maximum band height as a percentage of the image height.

    Returns:
        A new RGBA image with the caption band appended below the original content.
    """
    base = base_image.convert("RGBA")
    width, height = base.size

    display_text = _truncate_to_length(text, max_length)

    font, _is_truetype = _load_font(font_path, font_size)
    measurer = ImageDraw.Draw(base)
    max_text_width = max(1, width - 2 * padding_px)
    lines = _wrap_lines(measurer, display_text, font, max_text_width)

    bbox = font.getbbox("Ag")
    line_height = (bbox[3] - bbox[1]) * 1.3

    max_band_height = height * (max_height_pct / 100)
    lines = _fit_lines_to_height(lines, line_height, padding_px, max_band_height)

    band_height = min(max_band_height, round(len(lines) * line_height + 2 * padding_px))
    band_height = max(band_height, round(line_height + 2 * padding_px))

    canvas = Image.new("RGBA", (width, height + band_height), (0, 0, 0, 0))
    canvas.paste(base, (0, 0))

    bg_rgba = ImageColor.getcolor(background_color, "RGBA")
    alpha = int(255 * (background_opacity_pct / 100))
    band = Image.new("RGBA", (width, band_height), (*bg_rgba[:3], alpha))
    canvas.alpha_composite(band, dest=(0, height))

    draw = ImageDraw.Draw(canvas)
    y = height + padding_px
    for line in lines:
        draw.text((padding_px, y), line, font=font, fill=text_color)
        y += line_height

    return canvas
