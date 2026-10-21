"""Pydantic v2 configuration models and YAML loader for the Scene Agent.

Configuration is a single YAML file. Secrets (API keys) are never read from
YAML; they come only from environment variables, optionally loaded from a
``.env`` file via python-dotenv.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from scene_agent.errors import ConfigError


class CaptureWebConfig(BaseModel):
    """Configuration for the Playwright-based web capture backend."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field("https://www.finviz.com", description="URL to capture.")
    viewport_width: int = Field(1920, gt=0)
    viewport_height: int = Field(1080, gt=0)
    full_page: bool = False
    timeout_ms: int = Field(30_000, gt=0)
    headless: bool = True
    settle_delay_ms: int = Field(2_500, ge=0)
    ready_selector: str | None = None
    dismiss_consent_selectors: list[str] = Field(default_factory=list)


class CaptureWindowConfig(BaseModel):
    """Configuration for the desktop window capture backend (Windows only)."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    process_name: str | None = None
    timeout_ms: int = Field(5_000, gt=0)


class CaptureConfig(BaseModel):
    """Top-level capture configuration selecting a backend."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["web", "window"] = "web"
    web: CaptureWebConfig = Field(default_factory=lambda: CaptureWebConfig())
    window: CaptureWindowConfig = Field(default_factory=lambda: CaptureWindowConfig())

    @model_validator(mode="after")
    def _check_window_selector(self) -> CaptureConfig:
        if self.mode == "window" and not (self.window.title or self.window.process_name):
            raise ValueError(
                "capture.window.title or capture.window.process_name is required "
                "when capture.mode is 'window'"
            )
        return self


class AnthropicProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = "claude-sonnet-4-20250514"


class OpenAIProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = "gpt-4o"


class MockProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixed_text: str = "This is a deterministic mock description used for offline testing."


class ProviderConfig(BaseModel):
    """Vision-LLM provider selection and shared request settings."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["anthropic", "openai", "mock"] = "mock"
    prompt: str = "Read this image and explain exactly what is happening in this scene."
    timeout_s: int = Field(60, gt=0)
    max_retries: int = Field(3, ge=1, le=10)
    anthropic: AnthropicProviderConfig = Field(default_factory=AnthropicProviderConfig)
    openai: OpenAIProviderConfig = Field(default_factory=OpenAIProviderConfig)
    mock: MockProviderConfig = Field(default_factory=MockProviderConfig)


class LogoConfig(BaseModel):
    """Logo stamping configuration."""

    model_config = ConfigDict(extra="forbid")

    path: str = "assets/logo.png"
    on_missing: Literal["fail", "continue_without_logo"] = "continue_without_logo"
    corner: Literal["top-left", "top-right", "bottom-left", "bottom-right"] = "bottom-right"
    margin_px: int = Field(24, ge=0)
    scale_pct: float = Field(12, gt=0, le=100)
    opacity_pct: float = Field(90, ge=0, le=100)


class CaptionConfig(BaseModel):
    """Caption band configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    font_path: str = "C:/Windows/Fonts/segoeui.ttf"
    font_size: int = Field(22, gt=0)
    text_color: str = "#FFFFFF"
    background_color: str = "#000000"
    background_opacity_pct: float = Field(70, ge=0, le=100)
    padding_px: int = Field(16, ge=0)
    max_length: int = Field(600, gt=0)
    max_height_pct: float = Field(40, gt=0, le=100)


class PathsConfig(BaseModel):
    """Filesystem locations. Created automatically if missing."""

    model_config = ConfigDict(extra="forbid")

    input_dir: str = "data/input"
    output_dir: str = "data/output"
    log_dir: str = "logs"


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produce_logo_only_on_llm_failure: bool = True


class AppConfig(BaseModel):
    """Root configuration object."""

    model_config = ConfigDict(extra="forbid")

    paths: PathsConfig = Field(default_factory=PathsConfig)
    capture: CaptureConfig
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    logo: LogoConfig = Field(default_factory=LogoConfig)
    caption: CaptionConfig = Field(default_factory=CaptionConfig)
    run: RunConfig = Field(default_factory=RunConfig)


def load_config(config_path: str | Path) -> AppConfig:
    """Load, validate, and return the application configuration.

    Args:
        config_path: Path to a YAML configuration file.

    Returns:
        A validated :class:`AppConfig` instance. Configured directories are
        created on disk as a side effect.

    Raises:
        ConfigError: If the file is missing, is not valid YAML, or fails
            pydantic validation. The message lists every field error.
    """
    path = Path(config_path)
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    try:
        config = AppConfig.model_validate(raw)
    except Exception as exc:  # pydantic.ValidationError
        raise ConfigError(f"Invalid configuration in {path}:\n{exc}") from exc

    for directory in (config.paths.input_dir, config.paths.output_dir, config.paths.log_dir):
        Path(directory).mkdir(parents=True, exist_ok=True)

    return config


def apply_overrides(
    config: AppConfig,
    *,
    provider: str | None = None,
    input_dir: str | None = None,
    output_dir: str | None = None,
    url: str | None = None,
    headless: bool | None = None,
    prompt: str | None = None,
) -> AppConfig:
    """Return a copy of ``config`` with CLI flag overrides applied.

    Args:
        config: Base, already-validated configuration.
        provider: Override ``provider.name``.
        input_dir: Override ``paths.input_dir``.
        output_dir: Override ``paths.output_dir``.
        url: Override ``capture.web.url``.
        headless: Override ``capture.web.headless``.
        prompt: Override ``provider.prompt``.

    Returns:
        A new, re-validated :class:`AppConfig`.
    """
    data = config.model_dump()
    if provider is not None:
        data["provider"]["name"] = provider
    if input_dir is not None:
        data["paths"]["input_dir"] = input_dir
    if output_dir is not None:
        data["paths"]["output_dir"] = output_dir
    if url is not None:
        data["capture"]["web"]["url"] = url
    if headless is not None:
        data["capture"]["web"]["headless"] = headless
    if prompt is not None:
        data["provider"]["prompt"] = prompt

    try:
        updated = AppConfig.model_validate(data)
    except Exception as exc:
        raise ConfigError(f"Invalid configuration after applying overrides:\n{exc}") from exc

    for directory in (updated.paths.input_dir, updated.paths.output_dir, updated.paths.log_dir):
        Path(directory).mkdir(parents=True, exist_ok=True)

    return updated
