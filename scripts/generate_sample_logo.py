"""Generate assets/logo.png: a simple transparent-background sample logo.

Run with: python scripts/generate_sample_logo.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.png"
SIZE = 256


def generate_logo(output_path: Path = OUTPUT_PATH, size: int = SIZE) -> Path:
    """Create a small circular "SA" badge PNG with transparency.

    Args:
        output_path: Destination PNG path.
        size: Width/height of the square canvas in pixels.

    Returns:
        The path the logo was written to.
    """
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = size // 16
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(20, 90, 200, 235),
        outline=(255, 255, 255, 255),
        width=max(2, size // 40),
    )

    text = "SA"
    font_size = size // 2
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    position = ((size - text_w) / 2 - bbox[0], (size - text_h) / 2 - bbox[1])
    draw.text(position, text, font=font, fill=(255, 255, 255, 255))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")
    return output_path


if __name__ == "__main__":
    path = generate_logo()
    print(f"Sample logo written to {path}")
