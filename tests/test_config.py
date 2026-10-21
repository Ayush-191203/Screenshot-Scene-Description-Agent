"""Config validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from scene_agent.config import AppConfig, ConfigError, load_config


def test_valid_config_loads(base_config_dict: dict) -> None:
    config = AppConfig.model_validate(base_config_dict)
    assert config.capture.mode == "web"
    assert config.provider.name == "mock"


def test_window_mode_requires_title_or_process(base_config_dict: dict) -> None:
    base_config_dict["capture"] = {"mode": "window", "window": {}}
    with pytest.raises(ValidationError):
        AppConfig.model_validate(base_config_dict)


def test_window_mode_with_title_is_valid(base_config_dict: dict) -> None:
    base_config_dict["capture"] = {"mode": "window", "window": {"title": "Notepad"}}
    config = AppConfig.model_validate(base_config_dict)
    assert config.capture.window.title == "Notepad"


def test_unknown_field_rejected(base_config_dict: dict) -> None:
    base_config_dict["unknown_top_level_field"] = True
    with pytest.raises(ValidationError):
        AppConfig.model_validate(base_config_dict)


def test_load_config_missing_file_raises(tmp_path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "does_not_exist.yaml")


def test_load_config_invalid_yaml_raises(tmp_path) -> None:
    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text("capture: [unterminated", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(bad_file)


def test_load_config_creates_directories(tmp_path) -> None:
    config_file = tmp_path / "config.yaml"
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    log_dir = tmp_path / "logs"
    config_file.write_text(
        f"""
paths:
  input_dir: {input_dir}
  output_dir: {output_dir}
  log_dir: {log_dir}
capture:
  mode: web
  web:
    url: https://example.com
provider:
  name: mock
""",
        encoding="utf-8",
    )
    load_config(config_file)
    assert input_dir.is_dir()
    assert output_dir.is_dir()
    assert log_dir.is_dir()
