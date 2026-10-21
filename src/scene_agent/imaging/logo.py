"""Logo stamping onto a branded image copy, with correct alpha compositing."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, UnidentifiedImageError

from scene_agent.config import LogoConfig
from scene_agent.errors import LogoError

_CORNER_HANDLERS = {
    "top-left": lambda w, h, lw, lh, m: (m, m),
    "top-right": lambda w, h, lw, lh, m: (w - lw - m, m),
    "bottom-left": lambda w, h, lw, lh, m: (m, h - lh - m),
    "bottom-right": lambda w, h, lw, lh, m: (w - lw - m, h - lh - m),
}


def apply_logo(base_image: Image.Image, config: LogoConfig) -> Image.Image:
    """Return a copy of ``base_image`` with the configured logo stamped onto it.

    The logo's aspect ratio is preserved, it is scaled relative to the base
    image's width, clamped to stay fully within the image bounds, and
    composited using its alpha channel at the configured opacity.

    Args:
        base_image: Source image (will not be mutated).
        config: Logo placement configuration.

    Returns:
        A new RGBA :class:`PIL.Image.Image` with the logo applied.

    Raises:
        LogoError: If the logo file is missing or cannot be decoded as an image.
    """
    logo_path = Path(config.path)
    if not logo_path.is_file():
        raise LogoError(f"Logo file not found: {logo_path}")

    try:
        with Image.open(logo_path) as logo_file:
            logo = logo_file.convert("RGBA")
    except UnidentifiedImageError as exc:
        raise LogoError(f"Logo file is not a valid image: {logo_path} ({exc})") from exc

    result = base_image.convert("RGBA")
    base_w, base_h = result.size

    target_w = max(1, round(base_w * (config.scale_pct / 100)))
    scale_ratio = target_w / logo.width
    target_h = max(1, round(logo.height * scale_ratio))
    target_w = min(target_w, base_w)
    target_h = min(target_h, base_h)
    logo = logo.resize((target_w, target_h), Image.LANCZOS)

    if config.opacity_pct < 100:
        alpha = logo.getchannel("A").point(lambda a: int(a * (config.opacity_pct / 100)))
        logo.putalpha(alpha)

    handler = _CORNER_HANDLERS[config.corner]
    x, y = handler(base_w, base_h, target_w, target_h, config.margin_px)
    x = max(0, min(x, base_w - target_w))
    y = max(0, min(y, base_h - target_h))

    result.alpha_composite(logo, dest=(x, y))
    return result
