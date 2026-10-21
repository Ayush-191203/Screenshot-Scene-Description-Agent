"""Shared pytest fixtures: a minimal valid config dict and a sample logo for tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from scene_agent.config import AppConfig


@pytest.fixture
def sample_logo_path(tmp_path: Path) -> Path:
    """Create a small transparent-background PNG logo for tests."""
    logo_path = tmp_path / "logo.png"
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for x in range(64):
        for y in range(64):
            image.putpixel((x, y), (255, 0, 0, 200))
    image.save(logo_path, format="PNG")
    return logo_path


@pytest.fixture
def base_config_dict(tmp_path: Path, sample_logo_path: Path) -> dict:
    """Minimal valid configuration dict pointing at tmp_path directories."""
    return {
        "paths": {
            "input_dir": str(tmp_path / "input"),
            "output_dir": str(tmp_path / "output"),
            "log_dir": str(tmp_path / "logs"),
        },
        "capture": {
            "mode": "web",
            "web": {"url": "https://example.com"},
        },
        "provider": {"name": "mock"},
        "logo": {"path": str(sample_logo_path)},
        "caption": {},
        "run": {},
    }


@pytest.fixture
def base_config(base_config_dict: dict) -> AppConfig:
    """A validated :class:`AppConfig` built from :func:`base_config_dict`."""
    config = AppConfig.model_validate(base_config_dict)
    for directory in (config.paths.input_dir, config.paths.output_dir, config.paths.log_dir):
        Path(directory).mkdir(parents=True, exist_ok=True)
    return config
