from functools import lru_cache

from settings.app import AppSettings
from settings.logging import LoggingSettings


@lru_cache
def get_app_settings() -> AppSettings:
    return AppSettings()


@lru_cache
def get_logging_settings() -> LoggingSettings:
    return LoggingSettings()


__all__ = [
    "AppSettings",
    "LoggingSettings",
    "get_app_settings",
    "get_logging_settings",
]
