"""Logo placement tests: all four corners, scale, opacity."""

from __future__ import annotations

import pytest
from PIL import Image

from scene_agent.config import LogoConfig
from scene_agent.errors import LogoError
from scene_agent.imaging.logo import apply_logo


def _base_image() -> Image.Image:
    return Image.new("RGBA", (800, 600), (255, 255, 255, 255))


@pytest.mark.parametrize("corner", ["top-left", "top-right", "bottom-left", "bottom-right"])
def test_logo_placed_in_each_corner(sample_logo_path, corner: str) -> None:
    config = LogoConfig(path=str(sample_logo_path), corner=corner, margin_px=10, scale_pct=10, opacity_pct=100)
    base = _base_image()
    result = apply_logo(base, config)
    assert result.size == base.size

    # The logo region should differ from the plain white background near the expected corner.
    target_w = round(base.width * 0.10)
    if "left" in corner:
        x = config.margin_px + target_w // 2
    else:
        x = base.width - config.margin_px - target_w // 2
    if "top" in corner:
        y = config.margin_px + target_w // 2
    else:
        y = base.height - config.margin_px - target_w // 2
    pixel = result.getpixel((x, y))
    assert pixel[:3] != (255, 255, 255)


def test_logo_scale_pct_controls_width(sample_logo_path) -> None:
    base = _base_image()
    config = LogoConfig(path=str(sample_logo_path), scale_pct=25, margin_px=0, opacity_pct=100)
    result = apply_logo(base, config)
    # Logo pixels (alpha-blended red-on-white) should appear; count reddish pixels and
    # sanity check the affected area against the expected logo footprint.
    reddish_pixels = sum(
        1
        for x in range(base.width)
        for y in range(base.height)
        if (lambda p: p[0] > 200 and p[1] < 200 and p[2] < 200)(result.getpixel((x, y)))
    )
    expected_width = round(base.width * 0.25)
    assert reddish_pixels > 0
    assert reddish_pixels <= expected_width * expected_width * 1.2


def test_logo_opacity_blends_with_background(sample_logo_path) -> None:
    base = _base_image()
    config_full = LogoConfig(path=str(sample_logo_path), opacity_pct=100, margin_px=0, scale_pct=50)
    config_half = LogoConfig(path=str(sample_logo_path), opacity_pct=50, margin_px=0, scale_pct=50)

    full = apply_logo(base, config_full)
    half = apply_logo(base, config_half)

    cx, cy = base.width - 10, base.height - 10
    full_pixel = full.getpixel((cx, cy))
    half_pixel = half.getpixel((cx, cy))
    # Half-opacity red-on-white should be lighter (higher green/blue channel) than full opacity.
    assert half_pixel[1] > full_pixel[1]


def test_missing_logo_raises_logo_error(tmp_path) -> None:
    config = LogoConfig(path=str(tmp_path / "missing.png"))
    with pytest.raises(LogoError):
        apply_logo(_base_image(), config)


def test_corrupt_logo_raises_logo_error(tmp_path) -> None:
    corrupt_path = tmp_path / "corrupt.png"
    corrupt_path.write_bytes(b"not a real png")
    config = LogoConfig(path=str(corrupt_path))
    with pytest.raises(LogoError):
        apply_logo(_base_image(), config)


def test_logo_stays_within_bounds_for_large_scale(sample_logo_path) -> None:
    base = _base_image()
    config = LogoConfig(path=str(sample_logo_path), scale_pct=100, margin_px=0, opacity_pct=100)
    result = apply_logo(base, config)
    assert result.size == base.size
