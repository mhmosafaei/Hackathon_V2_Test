from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import AppMode, load_settings


def test_settings_load_and_validate() -> None:
    settings = load_settings(Path("config/settings.yaml"))
    assert settings.mode is AppMode.OFFLINE
    assert settings.default_forecast_horizon_hours == 168


def test_settings_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        load_settings("config/invalid_settings.yaml")
