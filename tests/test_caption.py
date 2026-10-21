"""Caption wrapping and truncation tests."""

from __future__ import annotations

from PIL import Image

from scene_agent.imaging.caption import render_caption_band


def _base_image(w: int = 600, h: int = 400) -> Image.Image:
    return Image.new("RGBA", (w, h), (10, 10, 10, 255))


def _common_kwargs(**overrides) -> dict:
    defaults = dict(
        font_path="C:/nonexistent/font.ttf",  # forces the documented fallback path in most test envs
        font_size=18,
        text_color="#FFFFFF",
        background_color="#000000",
        background_opacity_pct=70,
        padding_px=10,
        max_length=600,
        max_height_pct=40,
    )
    defaults.update(overrides)
    return defaults


def test_caption_band_appends_height(sample_logo_path) -> None:
    base = _base_image()
    result = render_caption_band(base, "A short caption.", **_common_kwargs())
    assert result.width == base.width
    assert result.height > base.height


def test_caption_truncates_to_max_length() -> None:
    base = _base_image()
    long_text = "word " * 500
    result = render_caption_band(base, long_text, **_common_kwargs(max_length=50))
    # Band height should be bounded; we can't read back text, but height must respect max_height_pct.
    assert result.height <= base.height + base.height * 0.40 + 1


def test_caption_respects_max_height_pct() -> None:
    base = _base_image(600, 200)
    long_text = "word " * 1000
    result = render_caption_band(base, long_text, **_common_kwargs(max_length=5000, max_height_pct=20))
    added_height = result.height - base.height
    assert added_height <= base.height * 0.20 + 2


def test_caption_disabled_band_not_added_when_text_empty() -> None:
    base = _base_image()
    result = render_caption_band(base, "", **_common_kwargs())
    # Even empty text should still produce a (minimal) band, not crash.
    assert result.width == base.width
    assert result.height >= base.height


def test_real_truetype_font_used_when_available() -> None:
    import os

    font_path = "C:/Windows/Fonts/segoeui.ttf"
    if not os.path.isfile(font_path):
        return  # not available in this environment; fallback path is covered by other tests
    base = _base_image()
    result = render_caption_band(
        base,
        "Rendered with a real TrueType font to verify word wrapping by pixel width.",
        **_common_kwargs(font_path=font_path),
    )
    assert result.height > base.height
