"""Validated, side-effect-free application configuration loading."""

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class AppMode(StrEnum):
    LIVE = "LIVE"
    HYBRID = "HYBRID"
    OFFLINE = "OFFLINE"


class Settings(BaseModel):
    """Settings that are safe to load before any external service is configured."""

    model_config = ConfigDict(extra="forbid")

    mode: AppMode = AppMode.OFFLINE
    timezone: str = "Europe/London"
    default_forecast_horizon_hours: PositiveInt = 168
    cache_stale_after_hours: PositiveInt = 24
    openai_model: str = Field(min_length=1)


def load_settings(path: str | Path) -> Settings:
    """Load a YAML settings file and reject unknown or invalid fields."""

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        values = yaml.safe_load(handle) or {}
    return Settings.model_validate(values)
